# -*- coding: utf-8 -*-
"""FULL-02 学校格式核查守门（plan/01 §11；FR-11）。"""

import json
from pathlib import Path

import pytest

from taw import engine, schoolfmt, thesisparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
THESIS = DATA / "frozen" / "thesis"


@pytest.fixture(scope="module")
def parsed():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("FULL-02 需要 docx extras：{}".format(exc))
    return thesisparse.parse_thesis(THESIS / "thesis_synthetic.docx")


def test_style_checks_detect_all_implants(parsed):
    """S1（章标题降级）/S2（题注用 Normal）/S3（正文误用 H2）全检出。"""
    ruleset = engine.compose_ruleset(DATA)
    findings = schoolfmt.check_style(parsed, ruleset)
    paras = {f["evidence"]["location"]["para"] for f in findings}
    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    for imp in truth["implants"]:
        if imp["kind"] != "style_error":
            continue
        assert any(p in paras for p in imp["paras"]), "样式植入未检出：{}".format(imp["id"])


def test_style_checks_no_false_positive(parsed):
    """误报 0：非植入段落不得有 style finding。"""
    ruleset = engine.compose_ruleset(DATA)
    findings = schoolfmt.check_style(parsed, ruleset)
    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    implant_paras = {p for imp in truth["implants"] if imp["kind"] == "style_error"
                     for p in imp["paras"]}
    fp = [f for f in findings if f["evidence"]["location"]["para"] not in implant_paras]
    assert fp == [], "样式核查误报：{}".format([f["detail"] for f in fp])


def test_style_findings_carry_clause_evidence(parsed):
    ruleset = engine.compose_ruleset(DATA)
    for f in schoolfmt.check_style(parsed, ruleset):
        assert f["check_type"] == "style"
        assert f["clause_status"] == "pending"
        assert f["basis"]
        assert f["evidence"]["quote"] is None


def test_read_doc_format_model():
    fmt = schoolfmt.read_doc_format(THESIS / "thesis_synthetic.docx")
    assert fmt["page_width_mm"] and fmt["page_height_mm"]
    assert fmt["margin_left_mm"] and fmt["margin_top_mm"]
    assert fmt["has_title_style"] is True
    assert fmt["has_author"] and fmt["has_school"] and fmt["has_supervisor"]
    assert isinstance(fmt["sections"], list) and fmt["sections"]


def test_school_profile_loaded_and_overrides_traceable():
    """学校 profile 装载：sch-demo 规则进入 ruleset；叠加层序在案。"""
    rs = engine.compose_ruleset(DATA, profile="school-demo")
    ids = {r["rule_id"] for r in rs["rules"]}
    assert "SCHOOL-DEMO-paper-01" in ids
    assert "SCHOOL-DEMO-toc-01" in ids
    # profile=default 时不装载学校规则
    rs_def = engine.compose_ruleset(DATA, profile="default")
    assert "SCHOOL-DEMO-paper-01" not in {r["rule_id"] for r in rs_def["rules"]}


def test_format_check_reports_nonconformance():
    """模板核查：A4 纸/页边距/目录三条不符合项挂规则（示例 profile）。"""
    fmt = schoolfmt.read_doc_format(THESIS / "thesis_synthetic.docx")
    rs = engine.compose_ruleset(DATA, profile="school-demo")
    findings = schoolfmt.check_format(fmt, rs)
    rule_ids = {f["rule_id"] for f in findings}
    assert "SCHOOL-DEMO-paper-01" in rule_ids   # 页面宽度（Letter 215.9 ≠ 210）
    assert "SCHOOL-DEMO-toc-01" in rule_ids     # 无目录
    for f in findings:
        assert f["check_type"] == "format"
        assert f["evidence"]["location"]["field"]


def test_format_check_evaluators():
    """求值算子：eq 容差 / gte / lte / present。"""
    model = {"a": 30.0, "b": 5, "c": True}
    assert schoolfmt._eval(30.4, "eq", 30.0, 0.5)[0] is True
    assert schoolfmt._eval(30.6, "eq", 30.0, 0.5)[0] is False
    assert schoolfmt._eval(5, "gte", 5, 0)[0] is True
    assert schoolfmt._eval(4, "gte", 5, 0)[0] is False
    assert schoolfmt._eval(True, "present", True, None)[0] is True
    assert schoolfmt._eval(False, "present", True, None)[0] is False
    assert schoolfmt._eval(None, "eq", 1.0, 0.1)[0] is False


def test_audit_school_combines(parsed):
    fmt = schoolfmt.read_doc_format(THESIS / "thesis_synthetic.docx")
    rs = engine.compose_ruleset(DATA, profile="school-demo")
    res = schoolfmt.audit_school(parsed, fmt, rs)
    types = {f["check_type"] for f in res["findings"]}
    assert "style" in types and "format" in types
