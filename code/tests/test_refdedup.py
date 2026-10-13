# -*- coding: utf-8 -*-
"""REF-05 去重与合并守门（plan/04 §十；FR-05，**误合并率 0**）。

核心断言：冲突字段（DOI/年份不同）的一律降级 manual_confirm，绝不自动合并；
DOI 精确 / 标题归一 + 辅助证据才自动合并。
"""

import json
from pathlib import Path

import pytest

from taw import refdedup, refparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
AUDIT = DATA / "frozen" / "audit"


def _cards(name):
    _fmt, cards = refparse.parse_file(AUDIT / name)
    return cards


def test_norm_title_ignores_spacing_case_punct():
    assert refdedup.norm_title("Synthetic Data  Methods") == refdedup.norm_title("synthetic-data methods")
    assert refdedup.norm_title("合成数据方法") == refdedup.norm_title("合成数据 方法")


def test_doi_exact_match_auto_merge_bib():
    """bib 载体携带 DOI → 精确匹配路径。"""
    cards = _cards("refs_table.bib")
    res = refdedup.find_duplicates(cards)
    labels = {tuple(sorted(c["labels"])) for c in res["clusters"]}
    assert ("ref003", "ref004") in labels, res["clusters"]


def test_title_normalized_merge_txt():
    """txt 载体无 DOI → 标题归一 + 著者交集 + 年份一致路径。"""
    cards = _cards("refs_table.txt")
    res = refdedup.find_duplicates(cards)
    labels = {tuple(sorted(c["labels"])) for c in res["clusters"]}
    assert ("3", "4") in labels, res["clusters"]


def test_conflicting_pair_never_auto_merged():
    """[8]/[9] 年份/DOI 冲突 → 严禁自动合并，只能 manual_confirm。"""
    cards = _cards("refs_table.txt")
    res = refdedup.find_duplicates(cards)
    for cluster in res["clusters"]:
        assert set(cluster["labels"]) != {"8", "9"}, "冲突对不得自动合并"
    manual = {tuple(sorted(m["labels"])) for m in res["manual_pairs"]}
    assert ("8", "9") in manual, res["manual_pairs"]


def test_false_merge_rate_zero_on_truth():
    truth = json.loads((AUDIT / "audit_truth.json").read_text(encoding="utf-8"))
    cards = _cards("refs_table.txt")
    res = refdedup.find_duplicates(cards)
    by_label = {c["evidence"]["label"]: c["card_id"] for c in cards}
    exp_pairs = set()
    for cluster in truth["expect"]["duplicate_clusters"]:
        ids = [by_label["[{}]".format(n) if False else str(n)] for n in cluster]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                exp_pairs.add(frozenset((ids[i], ids[j])))
    got_pairs = set()
    for cl in res["clusters"]:
        ids = sorted(cl["entry_ids"])
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                got_pairs.add(frozenset((ids[i], ids[j])))
    fp = got_pairs - exp_pairs
    assert not fp, "误合并：{}".format(fp)


def test_manual_confirm_status_not_fail():
    cards = _cards("refs_table.txt")
    res = refdedup.find_duplicates(cards, rule={
        "rule_id": "GBT7714-dedup-01", "status": "pending", "activation": "active",
        "severity": "error", "check_type": "duplicate_entry", "standard": "GB/T 7714",
        "clause": "重复著录", "quote": "", "basis": "x"})
    manual_findings = [f for f in res["findings"] if f["status"] == "manual_confirm"]
    assert manual_findings, "冲突对应产 manual_confirm finding"
    for f in manual_findings:
        assert f["status"] != "fail"


def test_merge_cluster_absorbs_missing_fields():
    cards = _cards("refs_table.bib")
    res = refdedup.find_duplicates(cards)
    cluster = res["clusters"][0]
    merged = refdedup.merge_cluster(cards, cluster)
    assert merged["card_id"] == cluster["keep"]
    assert merged["absorbed_from"]


def test_no_duplicates_on_distinct_cards():
    from taw.cards import make_author, make_ref_card
    a = make_ref_card("J", [make_author("张三")], "题名甲",
                      source={"year": "2024", "container": "刊甲"},
                      identifiers={"doi": "10.9999/a"}, evidence={"src": "x", "ordinal": 1})
    b = make_ref_card("J", [make_author("李四")], "题名乙",
                      source={"year": "2023", "container": "刊乙"},
                      identifiers={"doi": "10.9999/b"}, evidence={"src": "x", "ordinal": 2})
    res = refdedup.find_duplicates([a, b])
    assert res["clusters"] == [] and res["manual_pairs"] == []


def test_conflict_blocks_auto_merge_even_with_same_title():
    """标题同名但年份冲突 → 不得自动合并（宁可漏合不可误合）。"""
    from taw.cards import make_author, make_ref_card
    a = make_ref_card("J", [make_author("李疑似")], "图神经网络的特征学习",
                      source={"year": "2022", "container": "刊"}, identifiers={},
                      evidence={"src": "x", "ordinal": 1})
    b = make_ref_card("J", [make_author("李疑似")], "图神经网络的特征学习",
                      source={"year": "2023", "container": "刊"}, identifiers={},
                      evidence={"src": "x", "ordinal": 2})
    res = refdedup.find_duplicates([a, b])
    assert res["clusters"] == []
    assert len(res["manual_pairs"]) == 1
