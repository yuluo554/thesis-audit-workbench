# -*- coding: utf-8 -*-
"""FULL-03 术语与数字用法一致性守门（plan/01 §12；FR-12）。"""

import json
from pathlib import Path

import pytest

from taw import engine, termnum, thesisparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
THESIS = DATA / "frozen" / "thesis"


@pytest.fixture(scope="module")
def parsed():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("FULL-03 需要 docx extras：{}".format(exc))
    return thesisparse.parse_thesis(THESIS / "thesis_synthetic.docx")


@pytest.fixture(scope="module")
def ruleset():
    return engine.compose_ruleset(DATA)


def test_terminology_library_shape():
    """术语表纪律：每条挂 canonical/variants/basis；标准写法唯一。"""
    data = json.loads((DATA / "knowledge" / "terminology.json").read_text(encoding="utf-8"))
    assert len(data["terms"]) >= 3
    canonical = [t["canonical"] for t in data["terms"]]
    assert len(canonical) == len(set(canonical))
    for t in data["terms"]:
        assert t["canonical"] and t["variants"] and t["basis"]
        assert t["status"] in ("verified", "pending")
    assert data["number_usage"]["basis"]


def test_all_term_implants_detected(parsed, ruleset):
    """T1..T4 植入全检出（术语变体 4 处）。"""
    res = termnum.check_terms(parsed, ruleset, data_dir=DATA)
    got_paras = {f["evidence"]["location"]["para"] for f in res["findings"]}
    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    for imp in truth["implants"]:
        if imp["kind"] != "term_variant":
            continue
        assert any(p in got_paras for p in imp["paras"]), "术语植入未检出：{}".format(imp["id"])


def test_t2_stray_space_detected(parsed, ruleset):
    """T2 伪空格变体（'机器 学习'）检出。"""
    res = termnum.check_terms(parsed, ruleset, data_dir=DATA)
    details = " ".join(f["detail"] for f in res["findings"])
    assert "机器 学习" in details


def test_t4_missing_space_detected(parsed, ruleset):
    """T4 缺空格变体（'GB/T7714'）检出。"""
    res = termnum.check_terms(parsed, ruleset, data_dir=DATA)
    details = " ".join(f["detail"] for f in res["findings"])
    assert "GB/T7714" in details


def test_t3_number_thousands_inconsistent(parsed, ruleset):
    """T3 千分位不一致（3,500 vs 3500）检出，且只报同值两形态。"""
    res = termnum.check_terms(parsed, ruleset, data_dir=DATA)
    assert res["number_issues"], "千分位不一致未检出"
    issue = res["number_issues"][0]
    assert issue["value"] == "3500"
    assert issue["forms"]["sep"] and issue["forms"]["plain"]


def test_number_usage_single_form_not_reported():
    """单形态不报（误报 0 优先）：只有 3500 或只有 3,500 时无 finding。"""
    tree = [{"i": 0, "style": "Normal", "text": "共 3500 个样本。"}]
    assert termnum.scan_number_usage(tree, {"thousands_separators": [",", "，"]}) == []
    tree2 = [{"i": 0, "style": "Normal", "text": "共 3,500 个样本。"}]
    assert termnum.scan_number_usage(tree2, {"thousands_separators": [",", "，"]}) == []


def test_number_usage_exempts_references_and_headings():
    """参考文献条目与标题段不参与数字判定。"""
    tree = [{"i": 0, "style": "Normal", "text": "[1] 张合成. 题名[J]. 刊, 2025, 48(3): 1-12."},
            {"i": 1, "style": "Heading 1", "text": "第1章 绪论"},
            {"i": 2, "style": "Normal", "text": "共 3,500 个样本。"}]
    assert termnum.scan_number_usage(tree, {"thousands_separators": [",", "，"]}) == []


def test_heat_zones_shape(parsed, ruleset):
    res = termnum.check_terms(parsed, ruleset, data_dir=DATA)
    assert "by_para" in res["heat"] and "by_chapter" in res["heat"]
    assert sum(res["heat"]["by_chapter"].values()) >= 1


def test_findings_carry_clause_evidence(parsed, ruleset):
    res = termnum.check_terms(parsed, ruleset, data_dir=DATA)
    for f in res["findings"]:
        assert f["check_type"] == "term_consistency"
        assert f["clause_status"] == "pending" and f["basis"]
        assert f["severity"] == "warn"
