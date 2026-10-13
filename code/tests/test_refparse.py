# -*- coding: utf-8 -*-
"""REF-01 文献解析器守门：四格式解析 + 噪声清洗 + 宁缺纪律 + F1 门槛。

F1 门槛（plan/05 M2 行 + plan/04 §九）：clean ≥0.99、light ≥0.97、heavy ≥0.95。
对账 canonical 侧 = 入仓的 `refs_logic.json`（生成器 post-injection 逻辑记录）。
"""

import json
from pathlib import Path

import pytest

from taw import f1bench, refparse

REPO_ROOT = Path(__file__).resolve().parents[2]
REFS = REPO_ROOT / "data" / "frozen" / "refs"
DATA = REPO_ROOT / "data"


def _read(name):
    return (REFS / name).read_text(encoding="utf-8")


def _logic_by_layer():
    data = json.loads(_read("refs_logic.json"))
    by_layer = {}
    for r in data["records"]:
        by_layer.setdefault(r["layer"], []).append(r)
    return by_layer


# ---- 清洗管线单元 ----


def test_fullwidth_normalization():
    flags = []
    out = refparse.clean_text("２０２４（A）", flags)
    assert "2024" in out
    assert "fullwidth_normalized" in flags


def test_linebreak_and_hyphen_repair():
    text, flags = refparse.join_broken_lines(["Annals of -", "Imaginary Co-", "mputing"])
    assert text == "Annals of Imaginary Computing"
    assert "hyphen_repaired" in flags


def test_join_broken_lines_flags_deduped():
    """flag 去重：多行断行只记一次（confidence 扣减不被行数放大）。"""
    _, flags = refparse.join_broken_lines(["a", "b", "c", "d"])
    assert flags.count("linebreak_repaired") == 1


def test_year_space_repair():
    """年份断字 '20 24' → '2024'（heavy 噪声实测到的伪影）。"""
    flags = []
    out = refparse.clean_text("数据臆测学报, 20 24, 36(4): 61-79.", flags)
    assert "2024" in out
    assert "year_space_repaired" in flags


def test_cjk_stray_space_collapsed():
    flags = []
    out = refparse.clean_text("机器 学习", flags)
    assert out == "机器学习"
    assert "cjk_space_collapsed" in flags


# ---- 四格式基础解析 ----


def test_parse_txt_clean_all_fields():
    cards = refparse.parse_txt(_read("refs_clean.txt"), "refs_clean.txt")
    assert len(cards) == 24
    first = cards[0]
    assert first["title"] == "基于强化学习的时序预测融合"
    assert first["source"]["container"] == "虚拟信息科学"
    assert first["source"]["year"] == "2019"
    assert first["source"]["volume"] == "39"
    assert first["source"]["issue"] == "5"
    assert first["source"]["pages"] == "160-166"
    assert first["evidence"]["label"] == "1"
    assert first["confidence"] >= 0.9
    # clean 文件不得被误标为跨行噪声（linebreak flag 只记真跨行的条目）
    assert "linebreak_repaired" not in first["flags"]


def test_parse_csv_uses_entry_id_as_card_id():
    cards = refparse.parse_csv(_read("refs_clean.csv"), "refs_clean.csv")
    assert len(cards) == 24
    assert cards[0]["card_id"] == "ref-0001"
    assert cards[0]["title"] == "基于强化学习的时序预测融合"


def test_parse_bib_fields():
    cards = refparse.parse_bib(_read("refs_clean.bib"), "refs_clean.bib")
    assert len(cards) == 24
    c = cards[0]
    assert c["identifiers"]["doi"] == "10.9999/fake.2019.001"
    assert c["source"]["container"] == "虚拟信息科学"
    assert c["source"]["issue"] == "5"
    assert c["flags"].count("authors_truncated") == 1  # "others" 截断标记


def test_parse_ris_sp_ep_merged_to_pages():
    cards = refparse.parse_ris(_read("refs_clean.ris"), "refs_clean.ris")
    assert len(cards) == 24
    assert cards[0]["source"]["pages"] == "160-166"
    assert cards[0]["title"] == "基于强化学习的时序预测融合"


def test_parse_ris_none_literal_normalized():
    """M1 生成器把缺失字段渲染为字面 'None'（ris 伪影）→ 归一为缺失 + 记 flag。"""
    text = _read("refs_clean.ris")
    cards = refparse.parse_ris(text, "refs_clean.ris")
    assert any("ris_none_value_artifact" in c["flags"] for c in cards)


# ---- 噪声鲁棒性 ----


def test_heavy_noise_still_parses_all_entries():
    """强噪层条目数必须与真值一致（不能因噪声漏条）。"""
    for fmt in ("txt", "csv", "bib", "ris"):
        cards = refparse.PARSERS[fmt](_read("refs_heavy." + fmt), "refs_heavy." + fmt)
        assert len(cards) == 24, "{} 强噪层条目数 {}".format(fmt, len(cards))


def test_heavy_label_with_inner_space_is_split():
    """'[1 7]' 标签内插空格（heavy 实测伪影）→ 仍能切成独立条目。"""
    entries = refparse.split_txt_entries(_read("refs_heavy.txt"))
    assert len(entries) == 24
    assert any(lbl == "17" for lbl, _b, _f in entries)


def test_encoding_mix_entry_has_author_year_form():
    """著者-出版年制条目：无 [n] 编号、年份紧跟著者。"""
    cards = refparse.parse_txt(_read("refs_clean.txt"), "refs_clean.txt")
    mixed = [c for c in cards if c["evidence"]["label"] is None]
    assert mixed, "未见著者-出版年制条目"
    assert any("author_year_form" in c["flags"] for c in mixed)


# ---- 宁缺纪律 ----


def test_low_confidence_fields_stay_none_not_guessed():
    """解析不出的字段必须 None + flag，不得猜值硬填。

    构造"结构完全不可辨"的 body（无年份/卷期/冒号/报告号/版次），确认它不会被
    强行塞进任何字段槽位。
    """
    flags = []
    out = refparse._walk_body("xxxx yyyy zzzz", "J", flags)
    assert out["year"] is None and out["volume"] is None and out["pages"] is None
    assert out["publisher"] is None and out["city"] is None


def test_unparseable_segments_are_flagged():
    """多余的非结构段（城市位已占）必须记 body_unparsed_segment，不静默吞掉。"""
    flags = []
    refparse._walk_body("甲, 乙, 丙, 丁", "J", flags)
    assert flags.count("body_unparsed_segment") == 2


def test_missing_marker_lowers_confidence():
    card = refparse.parse_citation("张三. 某题名. 某某刊, 2024.", "x", 1)
    assert card["entry_type"] is None
    assert "no_type_marker" in card["flags"]
    assert card["confidence"] < 0.9


# ---- F1 门槛 ----


def test_refs_f1_thresholds_met():
    report = f1bench.bench_refs(DATA)
    for layer, threshold in f1bench.F1_THRESHOLDS.items():
        f1 = report["layers"][layer]["f1"]
        assert f1 >= threshold, "{} 层 F1 {} < 门槛 {}".format(layer, f1, threshold)
    assert report["gate"]["refs_pass"]


def test_refs_clean_and_light_perfect_across_formats():
    """clean/light 层四格式 F1 应为 1.0（解析器在无/轻噪下零误差）。"""
    report = f1bench.bench_refs(DATA)
    for fmt in f1bench.FORMATS:
        for layer in ("clean", "light"):
            f1 = report["formats"][fmt][layer]["f1"]
            assert f1 == 1.0, "{} {} F1 = {}".format(fmt, layer, f1)


def test_entry_type_not_in_f1_scope():
    """文献类型标识错误是 M3 审计 finding，不进解析 F1（plan/04 §九口径）。"""
    logic = _logic_by_layer()["clean"]
    assert "entry_type" in logic[0], "逻辑记录仍带 entry_type（供 M3 消费）"
    assert "entry_type" not in f1bench.REF_FIELDS
