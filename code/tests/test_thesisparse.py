# -*- coding: utf-8 -*-
"""论文解析器守门：style_tree / REF 域 / 四类标记 / 悬空 / 幽灵（plan/04 §四/§九）。

口径（M1 真值一次锁定）：style_tree 的 text 与 python-docx `.text` 一致——
fldSimple 内的 run 不计入。docx 缺装时大声失败（不静默跳过）。
"""

import json
from pathlib import Path

import pytest

from taw import f1bench, thesisparse

REPO_ROOT = Path(__file__).resolve().parents[2]
THESIS = REPO_ROOT / "data" / "frozen" / "thesis"
DATA = REPO_ROOT / "data"


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("论文解析器需要 docx extras：python -m pip install -e './code[docx]'（{}）".format(exc))


@pytest.fixture(scope="module")
def truth():
    return json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parsed():
    _require_docx()
    return thesisparse.parse_thesis(THESIS / "thesis_synthetic.docx")


# ---- 标签归一化 ----


def test_normalize_label_dashes_and_spaces():
    assert thesisparse.normalize_label("figure", "3-1") == "图3-1"
    assert thesisparse.normalize_label("figure", "3\u20141") == "图3-1"   # 全角破折号
    assert thesisparse.normalize_label("table", "9 1") == "表91"          # 空格清除
    assert thesisparse.normalize_label("equation", "4-1") == "式(4-1)"


def test_marker_regex_finds_handwritten_variants():
    assert thesisparse._MARK_FIG.search("如图3-1所示").group(1).replace(" ", "") == "3-1"
    assert thesisparse._MARK_TAB.search("见表 9-1").group(1).replace(" ", "") == "9-1"


# ---- style_tree ----


def test_style_tree_matches_truth_paragraph_by_paragraph(parsed, truth):
    got, want = parsed["style_tree"], truth["style_tree"]
    assert len(got) == len(want) == 62
    for g, w in zip(got, want):
        assert g["text"] == w["text"], "第 {} 段文本不一致".format(w["i"])
        assert g["style"] == w["style"], "第 {} 段样式不一致".format(w["i"])


def test_field_display_text_excluded_from_paragraph_text(parsed, truth):
    """域口径：fldSimple 内 run 不进 .text（真值一次锁定的语义）。"""
    assert parsed["fields"], "未解析到 REF 域"
    for f in parsed["fields"]:
        assert f["display"]
        assert f["display"] not in parsed["style_tree"][f["para_index"]]["text"]


# ---- REF 域 ----


def test_fields_match_truth(parsed, truth):
    assert len(parsed["fields"]) == len(truth["fields"]) == 2
    for got, want in zip(parsed["fields"], truth["fields"]):
        assert got["para_index"] == want["para_index"]
        assert got["instr"] == want["instr"]
        assert got["target_bookmark"] == want["target_bookmark"]
        assert got["bookmark_exists"] == want["bookmark_exists"]


def test_dangling_ref_field_detected(parsed):
    ref_dangling = [d for d in parsed["dangling"] if d["kind"] == "ref_field"]
    assert len(ref_dangling) == 1
    assert ref_dangling[0]["target_bookmark"] == "_Ref99900099"
    assert ref_dangling[0]["label"] == "图9-9"


# ---- 对象与提及 ----


def test_objects_match_truth(parsed, truth):
    want = {(o["kind"], o["label"]): o for o in truth["objects"]}
    got = {(o["kind"], o["label"]): o for o in parsed["objects"]}
    assert set(got) == set(want)
    for key, w in want.items():
        g = got[key]
        assert g["caption_para"] == w["caption_para"], key
        assert set(g["mentioned_paras"]) == set(w["mentioned_paras"]), key
        assert g["bookmark"] == w["bookmark"], key
        assert g["referenced"] == w["referenced"], key


def test_object_kind_distribution(parsed):
    kinds = {}
    for o in parsed["objects"]:
        kinds[o["kind"]] = kinds.get(o["kind"], 0) + 1
    assert kinds == {"figure": 4, "table": 3, "equation": 2}


def test_caption_body_paragraph_not_mistaken_for_caption(parsed):
    """正文段落 "表4-1给出…" 不得被误判为题注对象（真值只 9 个对象）。"""
    assert len(parsed["objects"]) == 9, "正文段被误判为题注：{}".format(
        [o["label"] for o in parsed["objects"]])


def test_mentions_include_handwritten_and_ref_field(parsed):
    modes = {m["mode"] for m in parsed["markers"]}
    assert "handwritten" in modes
    assert "ref_field" in modes


# ---- 悬空 / 幽灵 ----


def test_handwritten_dangling_marker_detected(parsed):
    hand = [d for d in parsed["dangling"] if d["kind"] == "handwritten"]
    assert any(d["label"] == "表9-1" for d in hand), parsed["dangling"]


def test_ghost_objects_detected(parsed):
    ghosts = {g["label"] for g in parsed["ghosts"]}
    assert {"图4-2", "表4-2"} <= ghosts
    # 真值中 mentioned=[] 的第三个对象（表3-1）同样应被检出
    assert "表3-1" in ghosts


# ---- 参数卡形态 ----


def test_doc_objects_produce_cards(parsed):
    cards = thesisparse.doc_objects(parsed)
    assert len(cards) == 9
    assert all(c["card_id"].startswith("obj-") for c in cards)
    fig31 = next(c for c in cards if c["label"] == "图3-1")
    assert fig31["kind"] == "figure"
    assert fig31["mentions"], "图3-1 应带提及"


# ---- 论文面 F1 全对账 ----


def test_thesis_f1_all_checks_pass():
    report = f1bench.bench_thesis(DATA)
    assert report["checks"]["style_tree"]["exact_match"]
    assert report["checks"]["fields"]["exact_match"]
    assert report["checks"]["objects"]["exact_match"]
    assert report["checks"]["dangling"]["all_found"]
    assert report["checks"]["ghosts"]["all_found"]
    assert report["gate"]["thesis_pass"]
