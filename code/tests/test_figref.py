# -*- coding: utf-8 -*-
"""FULL-01 交叉引用/编号重排守门（plan/01 §10；FR-10）。"""

import json
from pathlib import Path

import pytest

from taw import engine, figref, thesisparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
THESIS = DATA / "frozen" / "thesis"


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("FULL-01 需要 docx extras：{}".format(exc))


@pytest.fixture(scope="module")
def parsed():
    _require_docx()
    return thesisparse.parse_thesis(THESIS / "thesis_synthetic.docx")


@pytest.fixture(scope="module")
def ruleset():
    return engine.compose_ruleset(DATA)


def _by_type(findings):
    out = {}
    for f in findings:
        out.setdefault(f["check_type"], []).append(f)
    return out


def test_dangling_detected_both_modes(parsed, ruleset):
    """悬空标记两载体（手打 + REF 域）全检出。"""
    res = figref.audit_xref(parsed, ruleset)
    got = _by_type(res["findings"])["dangling_reference"]
    assert len(got) == 2
    modes = {f["evidence"]["location"].get("mode") for f in got}
    assert modes == {"handwritten", "ref_field"}
    blob = " ".join(f["detail"] for f in got)
    assert "表 9-1" in blob or "表9-1" in blob
    assert "_Ref99900099" in blob


def test_ghost_objects_detected(parsed, ruleset):
    """幽灵对象 = 真值植入 G1/G2（图4-2/表4-2）全检出；表3-1 亦零提及。"""
    res = figref.audit_xref(parsed, ruleset)
    ghosts = {f["evidence"]["location"]["label"] for f in res["findings"]
              if f["check_type"] == "ghost_object"}
    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    want = {i["expect"]["field"] for i in truth["implants"] if i["kind"] == "ghost_object"}
    assert want <= ghosts
    # 表3-1 真值 mentioned=[] → 也应作为幽灵报出
    assert "表3-1" in ghosts


def test_findings_carry_clause_status_and_basis(parsed, ruleset):
    """证据链纪律：pending 条款不出原文，带 basis。"""
    res = figref.audit_xref(parsed, ruleset)
    assert res["findings"]
    for f in res["findings"]:
        assert f["clause_status"] == "pending"
        assert f["evidence"]["clause"]
        assert f["basis"]
        assert f["evidence"]["quote"] is None


def test_number_gaps_within_chapter():
    """同章同类编号断档：图3-1/图3-3（缺 3-2）应报，图3-1/图3-2 不报。"""
    objs = [{"kind": "figure", "label": "图3-1", "caption_para": 1},
            {"kind": "figure", "label": "图3-3", "caption_para": 2}]
    gaps = figref.number_gaps(objs)
    assert len(gaps) == 1 and gaps[0]["missing"] == [2]
    ok = [{"kind": "figure", "label": "图3-1", "caption_para": 1},
          {"kind": "figure", "label": "图3-2", "caption_para": 2}]
    assert figref.number_gaps(ok) == []


def test_number_gaps_not_cross_chapter():
    """章间不比较（各章重新起编）：每章从 1 起即无断档，不因跨章编号回退而误报。"""
    objs = [{"kind": "figure", "label": "图3-1", "caption_para": 1},
            {"kind": "figure", "label": "图3-2", "caption_para": 2},
            {"kind": "figure", "label": "图4-1", "caption_para": 3},
            {"kind": "figure", "label": "图4-2", "caption_para": 4}]
    assert figref.number_gaps(objs) == []


def test_parse_label_no_variants():
    assert figref.parse_label_no("图3-1") == (3, 1)
    assert figref.parse_label_no("表4-2") == (4, 2)
    assert figref.parse_label_no("式(3-1)") == (3, 1)
    assert figref.parse_label_no("图3\u20131") == (3, 1)  # en-dash 归一
    assert figref.parse_label_no("正文不含编号") is None


def test_object_renumber_matrix_100(parsed):
    """任意插入/删除矩阵回归 100%（与 REF-07 同一内核）。"""
    bench = figref.object_renumber_bench(parsed)
    assert bench["gate"]["consistency_100"] is True
    assert bench["passed"] == bench["cases"]
    assert bench["cases"] > 20, "矩阵须覆盖插入/删除 × 位置组合"


def test_renumber_plan_reused_inner_kernel(parsed):
    """插入对象 → 编号重排映射正确，plan 通过独立复核。"""
    plan = figref.renumber_objects(parsed, [{"type": "delete", "target": "图4-2"}])
    assert plan["n_items"] == len(parsed["objects"]) - 1
    from taw import renumber
    assert renumber.verify_plan(plan) is True


def test_inactive_rules_produce_nothing(parsed):
    """规则未激活（gated）时零产出——activation 门控纪律。"""
    fake = {"rules": [{"rule_id": "TAW-xref-dangling-01", "check_type": "dangling_reference",
                       "status": "pending", "activation": "gated"}]}
    res = figref.audit_xref(parsed, fake)
    assert res["findings"] == []
