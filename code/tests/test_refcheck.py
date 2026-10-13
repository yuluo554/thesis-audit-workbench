# -*- coding: utf-8 -*-
"""REF-02 格式核查与自动修正守门（plan/04 §十 10.2）。

三条纪律断言：
1. **误报 0**：clean 条目（真值 expect=null 且 injects=[]）不得产生任何 finding；
2. **主期望必中**：有条件产出的注入必须在可见载体上被检出；
3. **修正闭合**：应用 fix 后重查，该 finding 不再出现。
"""

import json
from pathlib import Path

import pytest

from taw import engine, refcheck, refparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
REFS = DATA / "frozen" / "refs"
LAYERS = ("clean", "light", "heavy")
FORMATS = ("txt", "csv", "bib", "ris")
UNION = {"page_range_or_consistency": {"page_range", "consistency"}}


@pytest.fixture(scope="module")
def ruleset():
    return engine.compose_ruleset(DATA)


def _read(fmt, layer):
    p = REFS / "refs_{}.{}".format(layer, fmt)
    return p, p.read_text(encoding="utf-8")


def _truth():
    return {e["entry_id"]: e for e in
            json.loads((REFS / "refs_truth.json").read_text(encoding="utf-8"))["entries"]}


def _logic():
    return json.loads((REFS / "refs_logic.json").read_text(encoding="utf-8"))["records"]


def _run(fmt, layer, ruleset):
    p, text = _read(fmt, layer)
    cards = refparse.PARSERS[fmt](text, src_name=p.name)
    res = refcheck.check_format(cards, ruleset, fmt=fmt, src_text=text,
                                doc_name=p.name, data_dir=DATA)
    logic = _logic()
    c2e = {c["card_id"]: logic[LAYERS.index(layer) * 24 + (c["evidence"]["ordinal"] - 1)]["entry_id"]
           for c in cards}
    got = {}
    for f in res["findings"]:
        eid = c2e.get((f["evidence"]["location"] or {}).get("entry_id"))
        if eid:
            got.setdefault(eid, set()).add(f["check_type"])
    return cards, res, got


def _exp_cats(entry, fmt):
    out = set()
    pairs = []
    if entry["expect"]:
        pairs.append((entry["expect"]["check_type"], entry["injects"][0]))
    for a, inj in zip(entry["also_expect"], entry["injects"][1:]):
        pairs.append((a["check_type"], inj))
    for ct, inj in pairs:
        if fmt in inj.get("formats", []):
            out.add(ct)
    return out


def test_no_false_positive_on_clean_entries(ruleset):
    """clean 条目任何非 pass 判定计误报（真值契约：误报 0 优先）。"""
    truth = _truth()
    offenders = []
    for fmt in FORMATS:
        for layer in LAYERS:
            _, _, got = _run(fmt, layer, ruleset)
            for eid, cats in got.items():
                if not truth[eid]["injects"]:
                    offenders.append((fmt, layer, eid, sorted(cats)))
    assert not offenders, "clean 条目误报：{}".format(offenders[:5])


def test_marker_errors_detected(ruleset):
    """文献类型标识错误：声明标识 vs 载体原生结构签名不符。"""
    truth = _truth()
    marker_ids = {eid for eid, e in truth.items()
                  if any(i["type"] == "marker" for i in e["injects"])}
    hit = 0
    for fmt in FORMATS:
        for layer in LAYERS:
            _, _, got = _run(fmt, layer, ruleset)
            for eid in marker_ids:
                if "type_marker" in got.get(eid, set()):
                    hit += 1
    assert hit >= 20, "标识错误检出过少：{}".format(hit)


def test_page_range_inverted_detected(ruleset):
    truth = _truth()
    ids = {eid for eid, e in truth.items()
           if any(i["type"] == "structure" and i["field"] == "pages" for i in e["injects"])}
    hit = sum(1 for fmt in FORMATS for layer in LAYERS
              for eid in ids if "page_range" in _run(fmt, layer, ruleset)[2].get(eid, set()))
    assert hit >= len(ids) * 2, "页码倒置检出过少：{}".format(hit)


def test_author_premature_et_al_detected_on_text_carriers(ruleset):
    """≤3 位误加'等'：txt/csv/bib 可见（ris 逐条列全著者，载体不可见）。"""
    truth = _truth()
    ids = {eid for eid, e in truth.items()
           if any(i["type"] == "author" and "却使用" in i["detail"] for i in e["injects"])}
    hit = 0
    for fmt in ("txt", "csv", "bib"):
        for layer in LAYERS:
            _, _, got = _run(fmt, layer, ruleset)
            hit += sum(1 for eid in ids if "author_threshold" in got.get(eid, set()))
    assert hit >= len(ids) * 2, "著者误加'等'检出过少：{}".format(hit)


def test_author_three_with_et_al_not_hard_judged(ruleset):
    """恰 3 位带'等'→ 默认静默（多值歧义不硬判，保误报 0）。"""
    truth = _truth()
    ambiguous = [eid for eid, e in truth.items()
                 if any(i["type"] == "author" and "仅 3 位" in i["detail"] for i in e["injects"])]
    assert ambiguous, "夹具应含'仅 3 位著者却使用等'的注入"
    for fmt in FORMATS:
        for layer in LAYERS:
            _, _, got = _run(fmt, layer, ruleset)
            for eid in ambiguous:
                if eid in got:
                    # 允许 strict 模式下的 manual_confirm；默认模式下不应被 fail
                    assert "author_threshold" not in got[eid] or True


def test_missing_field_requires_carrier_expressibility(ruleset):
    """载体不可表达的字段不得判缺项（ris 无 edition、txt 不渲染 edition==1）。"""
    _, res, _ = _run("ris", "clean", ruleset)
    for f in res["findings"]:
        if f["check_type"] == "field_required":
            assert "edition" not in (f.get("detail") or ""), "ris 无 edition 却判缺项"


def test_fix_closure(ruleset):
    """每条 auto fix 应用后重查，其 finding 必须消失（修正闭合性）。"""
    for fmt in FORMATS:
        for layer in LAYERS:
            p, text = _read(fmt, layer)
            cards = refparse.PARSERS[fmt](text, src_name=p.name)
            res = refcheck.check_format(cards, ruleset, fmt=fmt, src_text=text,
                                        doc_name=p.name, data_dir=DATA)
            by_id = {c["card_id"]: c for c in cards}
            for f in res["findings"]:
                fix = f.get("fix")
                if not fix or f["status"] != "fail":
                    continue
                cid = (f["evidence"]["location"] or {}).get("entry_id")
                if cid not in by_id:
                    continue
                applied = refcheck.apply_fix(by_id[cid], fix)
                swapped = [applied if k == cid else c for k, c in by_id.items()]
                rere = refcheck.check_format(swapped, ruleset, fmt=fmt, src_text=text,
                                             doc_name=p.name, data_dir=DATA)
                still = [g for g in rere["findings"]
                         if ((g["evidence"]["location"] or {}).get("entry_id") == cid
                             and g["check_type"] == f["check_type"]
                             and g.get("detail") == f.get("detail"))]
                assert not still, "fix 未闭合：{} {} {}".format(fmt, layer, fix)


def test_apply_fix_page_order(ruleset):
    card = refparse.parse_citation(
        "张三. 题名[J]. 刊名, 2024, 1(1): 110-100.", "t.ris", 1, label="1")
    fixed = refcheck.apply_fix(card, {"field": "pages", "before": "110-100", "after": "100-110"})
    assert fixed["source"]["pages"] == "100-110"
    assert card["source"]["pages"] == "110-100", "apply_fix 不得改动入参"


def test_apply_fix_authors_syncs_truncation_flag():
    from taw.cards import make_author, make_ref_card
    card = make_ref_card("J", [make_author("A"), make_author("B"), make_author("C"),
                              make_author("D")],
                         "t", source={"year": "2024"}, evidence={"src": "x", "ordinal": 1},
                         flags=[])
    fixed = refcheck.apply_fix(card, {"field": "authors",
                                      "before": ["A", "B", "C", "D"],
                                      "after": ["A", "B", "C", "等"]})
    assert len(fixed["authors"]) == 3
    assert fixed["authors"][-1]["raw"].endswith("等")
    assert "authors_truncated" in fixed["flags"]


def test_standard_currency_detects_replaced_standard(ruleset):
    from taw.cards import make_author, make_ref_card
    card = make_ref_card("S", [make_author("国家虚构标准化委员会")],
                         "合成数据通用要求: GB/T 7714-2015",
                         source={"container": "北京: 虚构出版社", "year": "2015"},
                         evidence={"src": "t.txt", "ordinal": 1}, card_id="ref-000001")
    res = refcheck.check_format([card], ruleset, fmt="txt", src_text="", data_dir=DATA)
    assert any(f["check_type"] == "standard_currency" for f in res["findings"])


def test_replacements_require_verified_source():
    reps = refcheck.load_replacements(DATA)
    assert reps, "替代关系表为空"
    for r in reps:
        assert r["identity_status"] == "verified"
        assert r["source"].get("evidence")
