# -*- coding: utf-8 -*-
"""FULL-06 结构检查单守门（plan/01 §15；FR-15）。"""

from pathlib import Path

import pytest

from taw import engine, structcheck, thesisparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
THESIS = DATA / "frozen" / "thesis"


@pytest.fixture(scope="module")
def parsed():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("FULL-06 需要 docx extras：{}".format(exc))
    return thesisparse.parse_thesis(THESIS / "thesis_synthetic.docx")


@pytest.fixture(scope="module")
def ruleset():
    return engine.compose_ruleset(DATA)


def test_checklist_shape(parsed, ruleset):
    res = structcheck.check_structure(parsed, ruleset)
    ids = {c["id"] for c in res["checklist"]}
    assert {"abstract_present", "abstract_elements", "keywords_count",
            "english_abstract", "chapters_complete", "chapter_summary",
            "conclusion_echo", "heading_levels"} <= ids
    for c in res["checklist"]:
        assert c["name"] and c["evidence"] is not None


def test_clean_items_pass(parsed, ruleset):
    """合成论文结构完整：摘要/四要素/关键词/英文摘要/章节/小结/呼应 均通过。"""
    res = structcheck.check_structure(parsed, ruleset)
    by_id = {c["id"]: c for c in res["checklist"]}
    for item in ("abstract_present", "abstract_elements", "keywords_count",
                 "english_abstract", "chapters_complete", "chapter_summary",
                 "conclusion_echo"):
        assert by_id[item]["ok"] is True, "{} 应通过：{}".format(item, by_id[item]["evidence"])


def test_heading_level_failure_detected(parsed, ruleset):
    """S1 章标题降级 → 结构检查单 heading_levels 不通过 + structure_order finding。"""
    res = structcheck.check_structure(parsed, ruleset)
    by_id = {c["id"]: c for c in res["checklist"]}
    assert by_id["heading_levels"]["ok"] is False
    order_findings = [f for f in res["findings"] if f["check_type"] == "structure_order"]
    assert any("第4章" in f["detail"] for f in order_findings)


def test_structure_order_matches_s1_also_expect(parsed, ruleset):
    """S1 的 also_expect（structure_order 层级断档）由 FULL-06 命中——跨模块对账。"""
    res = structcheck.check_structure(parsed, ruleset)
    combos = {(f["check_type"], f["evidence"]["location"].get("field"))
              for f in res["findings"]}
    assert ("structure_order", "heading_sequence") in combos


def test_level_jump_detection():
    tree = [
        {"i": 0, "style": "Heading 1", "text": "第1章 绪论"},
        {"i": 1, "style": "Heading 3", "text": "1.1.1 小节"},
    ]
    headings = structcheck.parse_structure(tree)["headings"]
    jumps = structcheck._level_jumps(headings)
    assert jumps and jumps[0]["from"] == 1 and jumps[0]["to"] == 3


def test_checklist_findings_only_for_failures(parsed, ruleset):
    res = structcheck.check_structure(parsed, ruleset)
    failed = {c["id"] for c in res["checklist"] if not c["ok"]}
    got = {f["evidence"]["location"]["field"] for f in res["findings"]
           if f["check_type"] == "structure_checklist"}
    assert got == failed


def test_parse_structure_keywords(parsed):
    st = structcheck.parse_structure(parsed["style_tree"])
    assert st["keyword_counts"]["zh"] == 3
    assert st["keyword_counts"]["en"] == 3
    assert len(st["chapters"]) >= 5
