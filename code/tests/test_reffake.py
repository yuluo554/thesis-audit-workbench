# -*- coding: utf-8 -*-
"""REF-06 AI 幻觉风险画像守门（plan/04 §十；FR-06 + HalluRef-Bench）。

断言：六类信号逐一可检；genuine 条目**零误报**；风险分级正确；
合成数据白名单（DOI 10.9999 / ISBN 虚构出版者段）不被误报。
"""

import json
from pathlib import Path

import pytest

from taw import reffake
from taw.cards import make_author, make_ref_card

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
BENCH = DATA / "bench" / "halluref"


def _card(**kw):
    kwargs = dict(entry_type="J", authors=[make_author("张三")], title="题名",
                  source={"year": "2024"}, identifiers={},
                  evidence={"src": "t", "ordinal": 1})
    kwargs.update(kw)
    return make_ref_card(**kwargs)


@pytest.fixture(scope="module")
def known():
    return reffake.load_known_prefixes(DATA)


@pytest.fixture(scope="module")
def fake_isbn():
    return reffake.load_fake_isbn_ranges(DATA)


def test_synthetic_doi_prefix_not_flagged(known):
    """10.9999 白名单 → 不得报 doi_prefix_unknown。"""
    c = _card(identifiers={"doi": "10.9999/fake.2024.001"})
    prof = reffake.profile_entry(c, known)
    assert not any(s["type"] == "doi_prefix_unknown" for s in prof["signals"])


def test_unknown_doi_prefix_flagged(known, fake_isbn):
    c = _card(identifiers={"doi": "10.7777/halluref.2024.0101"})
    prof = reffake.profile_entry(c, known, fake_isbn_ranges=fake_isbn)
    assert any(s["type"] == "doi_prefix_unknown" for s in prof["signals"])
    assert prof["risk"] == "medium"


def test_synthetic_isbn_range_not_flagged(known, fake_isbn):
    """合成出版者段的 ISBN 校验位非真实 → 白名单豁免，不报校验位错。"""
    c = _card(entry_type="M", identifiers={"isbn": "978-7-0652-2883-7"})
    prof = reffake.profile_entry(c, known, fake_isbn_ranges=fake_isbn)
    assert not any(s["type"] == "isbn_checksum_invalid" for s in prof["signals"])


def test_isbn_checksum_invalid_detected(known, fake_isbn):
    c = _card(entry_type="M", identifiers={"isbn": "978-9-9999-9999-9"})
    prof = reffake.profile_entry(c, known, fake_isbn_ranges=fake_isbn)
    assert any(s["type"] == "isbn_checksum_invalid" for s in prof["signals"])
    assert prof["risk"] == "high"


def test_isbn_checksum_algorithm():
    assert reffake._isbn_checksum_ok("978-7-0100-1234-8") in (True, False)
    assert reffake._isbn_checksum_ok("0306406152") is True   # 经典合法 ISBN-10
    assert reffake._isbn_checksum_ok("0306406153") is False
    assert reffake._isbn_checksum_ok("123") is None          # 长度不对 → 不判


def test_year_out_of_range(known):
    c = _card(source={"year": "2030"})
    prof = reffake.profile_entry(c, known)
    assert any(s["type"] == "year_out_of_range" for s in prof["signals"])


def test_page_range_inverted(known):
    c = _card(source={"year": "2024", "pages": "150-145"})
    prof = reffake.profile_entry(c, known)
    assert any(s["type"] == "page_range_inverted" for s in prof["signals"])


def test_impossible_field_combo_journal_with_isbn(known):
    c = _card(entry_type="J", identifiers={"isbn": "978-7-0100-1234-8"},
              source={"year": "2024"})
    prof = reffake.profile_entry(c, known)
    assert any(s["type"] == "impossible_field_combo" for s in prof["signals"])


def test_impossible_field_combo_book_with_volume(known):
    c = _card(entry_type="M", source={"year": "2024", "volume": "12"})
    prof = reffake.profile_entry(c, known)
    assert any(s["type"] == "impossible_field_combo" for s in prof["signals"])


def test_self_referential_title(known):
    c = _card(title="虚构学报", source={"year": "2024", "container": "虚构学报"})
    prof = reffake.profile_entry(c, known)
    assert any(s["type"] == "self_referential_title" for s in prof["signals"])


def test_clean_entry_low_risk_no_signals(known):
    c = _card(entry_type="J", title="正常题名", source={"year": "2024",
              "container": "虚构学报", "pages": "10-20"},
              identifiers={"doi": "10.9999/fake.2024.001"})
    prof = reffake.profile_entry(c, known)
    assert prof["signals"] == []
    assert prof["risk"] == "low"


def test_health_score_bounds():
    profiles = [{"penalty": 30}, {"penalty": 0}, {"penalty": 25}]
    s = reffake.health_score(profiles)
    assert 0.0 <= s <= 100.0
    assert reffake.health_score([{"penalty": 1000}]) == 0.0
    assert reffake.health_score([]) == 100.0


def test_halluref_bench_perfect_detection():
    """HalluRef-Bench v1：hallucinated 全检出，genuine 零误报。"""
    entries = [json.loads(ln) for ln in
               (BENCH / "halluref_v1.jsonl").read_text(encoding="utf-8").splitlines()
               if ln.strip()]
    assert len(entries) == 200
    known = reffake.load_known_prefixes(DATA)
    fake = reffake.load_fake_isbn_ranges(DATA)
    genuine_fp = 0
    detected = 0
    total_h = 0
    for e in entries:
        f = e["fields"]
        c = make_ref_card(f["entry_type"], [make_author(a) for a in f["authors"]],
                          f["title"],
                          source={k: f.get(k) for k in ("container", "year", "volume",
                                                        "issue", "pages", "publisher", "city")},
                          identifiers={"doi": f.get("doi"), "isbn": f.get("isbn")},
                          evidence={"src": "bench", "ordinal": 1})
        got = {s["type"] for s in reffake.profile_entry(c, known,
                                                        fake_isbn_ranges=fake)["signals"]}
        if e["label"] == "genuine":
            if got:
                genuine_fp += 1
        else:
            total_h += 1
            if got & set(e["classes"]):
                detected += 1
    assert genuine_fp == 0, "genuine 条目误报 {}".format(genuine_fp)
    assert detected == total_h == 100, "hallucinated 检出 {}/{}".format(detected, total_h)


def test_taxonomy_covers_all_frozen_classes():
    manifest = json.loads((BENCH / "halluref_v1_manifest.json").read_text(encoding="utf-8"))
    frozen = set(manifest["classes_v1"])
    implemented = {"doi_prefix_unknown", "isbn_checksum_invalid", "year_out_of_range",
                   "page_range_inverted", "impossible_field_combo",
                   "self_referential_title"}
    assert frozen == implemented
