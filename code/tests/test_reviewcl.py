# -*- coding: utf-8 -*-
"""FULL-05 综述辅助守门（plan/01 §14；FR-14）。"""

import json
from pathlib import Path

from taw import reviewcl

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
REVIEW = DATA / "frozen" / "review"


def _corpus():
    return json.loads((REVIEW / "review_corpus.json").read_text(encoding="utf-8"))


def _truth():
    return json.loads((REVIEW / "review_truth.json").read_text(encoding="utf-8"))


def _entries():
    return _corpus()["entries"]


# ---- TF-IDF 聚类 ----


def test_tfidf_vectors_normalized():
    vecs = reviewcl.tfidf_vectors(_entries()[:3])
    assert len(vecs) == 3
    for v in vecs:
        assert v["norm"] > 0 and v["vector"]


def test_cosine_self_is_one():
    vecs = reviewcl.tfidf_vectors(_entries())
    assert abs(reviewcl.cosine(vecs[0], vecs[0]) - 1.0) < 1e-9


def test_cluster_matches_truth_groups():
    """聚类对预分组：4 簇、纯度 1.0（同主题条目聚到一起）。"""
    clusters = reviewcl.cluster(_entries())
    truth = _truth()
    assert len(clusters) == truth["counts"]["groups"]
    purity = reviewcl.cluster_purity(clusters, None, truth["groups"])
    assert purity["purity"] == 1.0
    for cl in clusters:
        assert len(cl["entry_ids"]) == 5


def test_cluster_deterministic():
    a = reviewcl.cluster(_entries())
    b = reviewcl.cluster(list(reversed(_entries())))
    assert [c["entry_ids"] for c in a] == [c["entry_ids"] for c in b]


# ---- 时间线 ----


def test_timeline_shape():
    tl = reviewcl.timeline(_entries())
    truth = _truth()
    assert set(tl.keys()) == set(truth["groups"].keys())
    for g, years in tl.items():
        assert sum(years.values()) == 5


# ---- 研究空白（规则可判）----


def test_research_gaps_match_truth():
    gaps = reviewcl.research_gaps(_entries(), _truth()["now_year"])
    assert [g["group"] for g in gaps] == [g["group"] for g in _truth()["research_gaps"]]


def test_gap_rule_is_deterministic():
    """空白判据 = 主题内最近年份 < now_year-2（规则可判，非语义推断）。"""
    entries = [{"group": "g1", "year": 2020}, {"group": "g1", "year": 2021},
               {"group": "g2", "year": 2025}]
    gaps = reviewcl.research_gaps(entries, 2026)
    assert [g["group"] for g in gaps] == ["g1"]


def test_build_review_bundle():
    res = reviewcl.build_review(_entries(), now_year=_truth()["now_year"])
    assert res["cluster_count"] == 4
    assert res["purity"]["purity"] == 1.0
    assert res["research_gaps"]
    assert res["timeline"]
    assert res["disclaimers"]


def test_review_corpus_frozen_shape():
    corp = _corpus()
    assert len(corp["entries"]) == 20
    assert corp["now_year"] == 2026
    assert len({e["entry_id"] for e in corp["entries"]}) == 20
    for e in corp["entries"]:
        assert e["doi"].startswith("10.9999/")
        assert e["group"] and e["year"] and e["title"]


# ---- 综述可视化（复用 reftopo 0 外链路径）----


def test_to_nodes_one_per_cluster():
    nodes = reviewcl.to_nodes(_entries())
    assert len(nodes) == 4
    for n in nodes:
        assert n["id"].startswith("c")
        assert n["cite_count"] == 5


def test_review_html_passes_zero_external_assert():
    """综述聚类 HTML 复用 reftopo 渲染路径，过 0 外链硬断言（NFR-07）。"""
    from taw import reftopo
    html_text = reviewcl.render_review_html(_entries(), now_year=_truth()["now_year"])
    assert reftopo.assert_no_external_refs(html_text) is True


def test_review_nodes_flag_research_gap():
    """研究空白主题的簇节点带 audit 标记（可视化联动）。"""
    nodes = reviewcl.to_nodes(_entries())
    flagged = [n for n in nodes if n["audit"]]
    assert len(flagged) == 1
    assert "interpretability" in flagged[0]["label"]
