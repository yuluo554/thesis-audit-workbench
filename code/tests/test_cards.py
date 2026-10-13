# -*- coding: utf-8 -*-
"""参数卡与证据链 schema 守门（plan/04 §一/§三/§九）。"""

import pytest

from taw import cards


def test_ref_card_shape_and_defaults():
    card = cards.make_ref_card(
        entry_type="J", authors=[cards.make_author("张三", "张", "三")],
        title="题名", source={"container": "某刊", "year": "2024"},
        identifiers={"doi": "10.9999/fake.2024.001"},
        evidence={"src": "refs.txt", "ordinal": 1, "label": "1", "raw": "原文"},
    )
    assert card["entry_type"] == "J"
    assert card["title"] == "题名"
    # 缺槽位一律 None（宁缺口径的落点）
    assert card["source"]["volume"] is None
    assert card["source"]["edition"] is None
    assert card["source"]["report_no"] is None
    assert card["identifiers"]["isbn"] is None
    assert card["flags"] == []
    assert card["confidence"] == 1.0


def test_ref_card_strips_whitespace_in_identifier_fields():
    """doi/isbn/pages/report_no 属无空格字段：噪声伪影在构造期清除。"""
    card = cards.make_ref_card(
        entry_type="J", authors=[], title="t",
        source={"pages": "95-10 5", "report_no": "RR-2024 -194"},
        identifiers={"doi": "10.9999 /fake.2024.001", "isbn": "978-7 0487"},
        evidence={"src": "x", "ordinal": 1},
    )
    assert card["identifiers"]["doi"] == "10.9999/fake.2024.001"
    assert card["identifiers"]["isbn"] == "978-70487"
    assert card["source"]["pages"] == "95-105"
    assert card["source"]["report_no"] == "RR-2024-194"


def test_ref_card_rejects_bad_entry_type_and_confidence():
    with pytest.raises(ValueError):
        cards.make_ref_card(entry_type="ZZ", authors=[], title="t",
                            evidence={"src": "x", "ordinal": 1})
    with pytest.raises(ValueError):
        cards.make_ref_card(entry_type="J", authors=[], title="t",
                            confidence=1.5, evidence={"src": "x", "ordinal": 1})


def test_ref_card_requires_evidence_src():
    """证据链纪律：无出处不落卡。"""
    with pytest.raises(ValueError):
        cards.make_ref_card(entry_type="J", authors=[], title="t")


def test_doc_object_card_shape():
    card = cards.make_doc_object(
        kind="figure", label="图3-1",
        anchor={"para_index": 27, "style": "Caption", "is_ref_field": False},
        mentions=[{"para_index": 26, "mode": "handwritten", "raw": "如图3-1所示"}],
        caption={"para_index": 27},
    )
    assert card["kind"] == "figure"
    assert card["label"] == "图3-1"
    assert card["anchor"]["is_ref_field"] is False
    assert card["mentions"][0]["mode"] == "handwritten"


def test_doc_object_card_rejects_bad_kind_and_missing_label():
    with pytest.raises(ValueError):
        cards.make_doc_object(kind="widget", label="x", anchor={"para_index": 0})
    with pytest.raises(ValueError):
        cards.make_doc_object(kind="figure", label="", anchor={"para_index": 0})


def test_finding_three_level_status():
    f = cards.make_finding("GBT7714-2015-punct-01", "manual_confirm",
                           {"doc": "refs.txt", "para": 1, "span": [0, 5]},
                           clause="示例条号", quote="原文", suggestion="补逗号")
    assert f["status"] == "manual_confirm"
    assert f["evidence"]["location"]["doc"] == "refs.txt"
    with pytest.raises(ValueError):
        cards.make_finding("r", "maybe", {"doc": "d", "para": 0, "span": [0, 1]})
