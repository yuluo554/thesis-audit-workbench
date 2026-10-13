# -*- coding: utf-8 -*-
"""REF-07 推荐 + 编号重排内核守门（plan/04 §五/§十；FR-07）。

关键断言：
1. **防幻觉**：推荐候选 card_id 恒为输入库子集，库外 id 一律拒绝；
2. **检索质量**：合成标注的句子能召回目标文献（Recall@5）；
3. **重排一致性 100%**：任意插入/删除矩阵回归（M3 文献编号，M4 复用同内核）。
"""

import json
from pathlib import Path

import pytest

from taw import refparse, refrec, renumber

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT = REPO_ROOT / "data" / "frozen" / "audit"


@pytest.fixture(scope="module")
def cards():
    _fmt, cards = refparse.parse_file(AUDIT / "refs_table.txt")
    return cards


def test_tokenize_mixed_script():
    toks = refrec.tokenize("深度学习 Deep Learning 2024")
    assert any(t == "de" for t in toks) or "deep" in toks
    assert "2024" in toks
    assert any("\u4e00" <= t <= "\u9fff" for t in toks), "应含 CJK 词项"


def test_bm25_ranking_relevant_first(cards):
    recs = refrec.recommend(cards, "面向表格数据的扩散模型方法", top_k=3)
    assert recs, "应有推荐"
    assert recs[0]["label"] == "5", "扩散模型条目应排第一：{}".format(recs[0])


def test_recommendations_are_library_only(cards):
    """结构防幻觉：候选恒为库内卡片。"""
    ids = {c["card_id"] for c in cards}
    recs = refrec.recommend(cards, "任意查询句子图神经网络", top_k=50)
    assert recs
    for r in recs:
        assert r["card_id"] in ids
        assert r["in_library"] is True


def test_recommend_has_hit_evidence(cards):
    recs = refrec.recommend(cards, "合成数据质量评估", top_k=2)
    assert recs
    for r in recs:
        assert r["hits"], "推荐须附命中证据"
        for h in r["hits"]:
            assert {"term", "tf", "idf", "contrib"} <= set(h)


def test_recommend_empty_on_no_overlap(cards):
    recs = refrec.recommend(cards, "zzzzz qqqqq", top_k=3)
    assert recs == []


def test_recall_at_5_on_synthetic_probes(cards):
    hits = 0
    probes = 0
    for c in cards:
        title = c.get("title") or ""
        if len(title) < 4:
            continue
        probes += 1
        recs = refrec.recommend(cards, "本文参考{}的相关工作".format(title[:8]), top_k=5)
        if c["card_id"] in [r["card_id"] for r in recs]:
            hits += 1
    assert probes >= 5
    assert hits / probes >= 0.7, "Recall@5 过低：{}/{}".format(hits, probes)


def test_insert_rejects_out_of_library(cards):
    items = [{"item_id": "a", "markers": []}]
    with pytest.raises(ValueError):
        refrec.insert_reference(items, cards, "ref-999999")


def test_insert_library_entry_ok(cards):
    items = [{"item_id": c["card_id"], "markers": []} for c in cards[:3]]
    plan = refrec.insert_reference(items, cards, cards[5]["card_id"])
    assert cards[5]["card_id"] in plan["new_order"]
    assert renumber.verify_plan(plan)


# ---- 编号重排内核 ----


def _items(n):
    return [{"item_id": "it{}".format(i + 1),
             "markers": [{"marker_id": "m{}".format(i + 1)}]} for i in range(n)]


def test_renumber_delete_shifts_numbers():
    plan = renumber.renumber(_items(3), [{"type": "delete", "target": "it1"}])
    assert plan["new_order"] == ["it2", "it3"]
    m = {x["item_id"]: x["new_no"] for x in plan["mappings"] if x["marker_id"] == "m2"}
    assert m["it2"] == 1
    assert plan["consistent"] and renumber.verify_plan(plan)


def test_renumber_insert_after_and_before():
    items = _items(3)
    after = renumber.renumber(items, [{"type": "insert", "new_item_id": "x",
                                       "target": "it2"}])
    assert after["new_order"] == ["it1", "it2", "x", "it3"]
    before = renumber.renumber(items, [{"type": "insert", "new_item_id": "y",
                                        "target": "it1", "before": True}])
    assert before["new_order"] == ["y", "it1", "it2", "it3"]
    assert renumber.verify_plan(after) and renumber.verify_plan(before)


def test_renumber_does_not_mutate_input():
    items = _items(3)
    snapshot = json.dumps(items, sort_keys=True)
    renumber.renumber(items, [{"type": "delete", "target": "it2"}])
    assert json.dumps(items, sort_keys=True) == snapshot


def test_renumber_plan_maps_old_to_new():
    plan = renumber.renumber(_items(4), [{"type": "delete", "target": "it2"}])
    pairs = {(x["marker_id"], x["old_no"], x["new_no"])
             for x in plan["mappings"] if x["marker_id"] in ("m1", "m3", "m4")}
    assert ("m1", 1, 1) in pairs
    assert ("m3", 3, 2) in pairs
    assert ("m4", 4, 3) in pairs


def test_renumber_missing_target_diagnostic():
    plan = renumber.renumber(_items(2), [{"type": "delete", "target": "nope"}])
    assert any(d["kind"] == "delete_target_missing" for d in plan["diagnostics"])


def test_renumber_unknown_edit_type_diagnostic():
    plan = renumber.renumber(_items(2), [{"type": "frobnicate", "target": "it1"}])
    assert any(d["kind"] == "unknown_edit_type" for d in plan["diagnostics"])


def test_edit_matrix_consistency_100_percent():
    """任意插入/删除位置 × 组合矩阵回归 100%（M3 DoD 硬指标）。"""
    base_ids, cases = refrec.edit_matrix(6)
    items = [{"item_id": b, "markers": [{"marker_id": "m-" + b}]} for b in base_ids]
    failed = []
    for edits, desc in cases:
        plan = renumber.renumber(items, edits)
        if not renumber.verify_plan(plan):
            failed.append(desc)
    assert not failed, "重排不一致：{}".format(failed[:5])
    assert len(cases) >= 50, "矩阵规模过小：{}".format(len(cases))


def test_verify_plan_detects_inconsistent():
    bad = {"mappings": [{"marker_id": "a", "item_id": "x", "new_no": 2},
                        {"marker_id": "a", "item_id": "y", "new_no": 1}],
           "consistent": True, "new_order": ["x", "y"], "n_items": 2}
    assert renumber.verify_plan(bad) is False       # 标记重号
