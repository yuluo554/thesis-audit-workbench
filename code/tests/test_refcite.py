# -*- coding: utf-8 -*-
"""REF-04 正文引用对账守门（plan/04 §十；FR-04）。

对 audit 夹具真值逐项对账：悬空引用 / 幽灵文献 / 乱序断档 / 著者-年份不匹配。
"""

import json
from pathlib import Path

import pytest

from taw import engine, refcite, refparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
AUDIT = DATA / "frozen" / "audit"


@pytest.fixture(scope="module")
def fixtures():
    truth = json.loads((AUDIT / "audit_truth.json").read_text(encoding="utf-8"))
    _fmt, cards = refparse.parse_file(AUDIT / "refs_table.txt")
    body = (AUDIT / "body.txt").read_text(encoding="utf-8")
    markers = refcite.parse_markers(body)
    rs = engine.compose_ruleset(DATA)
    res = refcite.reconcile(cards, markers, rs, doc_name="body.txt")
    return {"truth": truth, "cards": cards, "markers": markers, "res": res}


def test_expand_numbers_ranges():
    assert refcite.expand_numbers("1") == [1]
    assert refcite.expand_numbers("2,5-7") == [2, 5, 6, 7]
    assert refcite.expand_numbers("3-5,9") == [3, 4, 5, 9]
    assert refcite.expand_numbers("7-5") == [5, 6, 7]     # 逆向区间升序展开


def test_markers_parsed_both_styles(fixtures):
    kinds = {m["kind"] for m in fixtures["markers"]}
    assert kinds == {"numeric", "author_year"}
    nums = [n for m in fixtures["markers"] if m["kind"] == "numeric" for n in m["numbers"]]
    assert 99 in nums and 3 in nums and 1 in nums


def test_dangling_citation_detected(fixtures):
    exp = set(fixtures["truth"]["expect"]["dangling_citation"])
    got = set()
    for f in fixtures["res"]["findings"]:
        if f["check_type"] == "dangling_citation":
            got.add(int(f["detail"].split("[")[1].split("]")[0]))
    assert got == exp, "悬空引用检出不符：{} vs {}".format(got, exp)


def test_ghost_reference_detected(fixtures):
    exp = {str(n) for n in fixtures["truth"]["expect"]["ghost_reference"]}
    got = set()
    for f in fixtures["res"]["findings"]:
        if f["check_type"] == "ghost_reference":
            lab = (f["evidence"]["location"] or {}).get("label") or ""
            got.add(lab.strip("[]"))
    assert got == exp, "幽灵文献检出不符：{} vs {}".format(got, exp)


def test_order_gap_detected(fixtures):
    assert fixtures["truth"]["expect"]["order_gap"] is True
    assert any(f["check_type"] == "order_gap" for f in fixtures["res"]["findings"])


def test_author_year_mismatch_detected(fixtures):
    ay = [f for f in fixtures["res"]["findings"] if f["check_type"] == "author_year_mismatch"]
    assert any("王杜撰" in (f.get("detail") or "") for f in ay), "著者-年份不匹配未检出"


def test_author_year_correct_citation_not_flagged(fixtures):
    """命中的著者-年份引用（SMITH J（2022））不得被报为不匹配。"""
    ay = [f for f in fixtures["res"]["findings"] if f["check_type"] == "author_year_mismatch"]
    assert not any("SMITH" in (f.get("detail") or "") and "无同著者" in (f.get("detail") or "")
                   for f in ay)


def test_no_ghost_when_all_cited():
    """所有条目都被引用时不得报幽灵（反例守卫）。"""
    _fmt, cards = refparse.parse_file(AUDIT / "refs_table.txt")
    labels = [c["evidence"]["label"] for c in cards]
    body = " ".join("[{}]".format(l) for l in labels)
    rs = engine.compose_ruleset(DATA)
    res = refcite.reconcile(cards, refcite.parse_markers(body), rs)
    assert not any(f["check_type"] == "ghost_reference" for f in res["findings"])


def test_extract_citation_context_maps_entries(fixtures):
    ctx = refcite.extract_citation_context(fixtures["cards"], fixtures["markers"])
    assert ctx, "引用语境为空"
    for cid, items in ctx.items():
        for it in items:
            assert "para" in it and "context" in it


def test_no_citation_no_findings_without_numeric_markers():
    """正文无任何引用标记 → 无悬空/乱序（空输入守门）。"""
    _fmt, cards = refparse.parse_file(AUDIT / "refs_table.txt")
    rs = engine.compose_ruleset(DATA)
    res = refcite.reconcile(cards, refcite.parse_markers("本节不引用任何文献。"), rs)
    assert not any(f["check_type"] in ("dangling_citation", "order_gap")
                   for f in res["findings"])
