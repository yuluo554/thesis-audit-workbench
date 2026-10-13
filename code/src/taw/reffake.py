# -*- coding: utf-8 -*-
"""REF-06 AI 幻觉文献风险画像（plan/04 §十 + data/bench/halluref/FORMAT.md；FR-06）。

**风险提示 ≠ 真伪判定**（伦理边界）：本模块只给可检信号与风险分级，报告强制声明；
不联网、不做真伪结论。

六个信号（与 HalluRef-Bench v1 冻结类目一一对应）：

| signal | 判据 |
|---|---|
| `doi_prefix_unknown`  | DOI 前缀不在白名单/已知注册前缀集（合成数据白名单见 doi_fake_prefixes.json） |
| `isbn_checksum_invalid`| ISBN-10/13 校验位错误（GB/T 5792 加权算法） |
| `year_out_of_range`    | 年份超前于基准时点，或早于合理下界 |
| `page_range_inverted`  | 起页 > 止页 |
| `impossible_field_combo`| 类型-字段矩阵矛盾（期刊条目带 ISBN / 图书条目带卷期页 等） |
| `self_referential_title`| 题名与载体名相同或题名内嵌载体名 |

风险分级：`high`（≥1 个确定性结构信号）/ `medium`（1 个弱信号）/ `low`（无信号）。
体检分（REF-09 复用）：100 - Σ 权重，clamp [0, 100]。
"""

import json
import re
from pathlib import Path

from taw import engine

# 已知注册 DOI 前缀（真实注册机构示例；合成白名单另从数据目录读）
KNOWN_DOI_PREFIXES = ("10.1000", "10.1002", "10.1016", "10.1038", "10.1109",
                      "10.1145", "10.1007", "10.1088", "10.1080", "10.1093",
                      "10.1063", "10.1111", "10.1049", "10.1149", "10.1051")

# 幻觉类目 → 风险权重（体检分扣减）
SIGNAL_WEIGHT = {
    "doi_prefix_unknown": 30,
    "isbn_checksum_invalid": 25,
    "year_out_of_range": 20,
    "page_range_inverted": 15,
    "impossible_field_combo": 25,
    "self_referential_title": 10,
}
STRUCTURAL_SIGNALS = ("page_range_inverted", "impossible_field_combo",
                      "isbn_checksum_invalid")
WEAK_SIGNALS = ("doi_prefix_unknown", "year_out_of_range", "self_referential_title")

# 基准时点（年份上界）：晚于该年视为"超前"（合成数据全为 2018-2025，取 2026 为上界）
YEAR_UPPER = 2026
YEAR_LOWER = 1900


def load_known_prefixes(data_dir=None):
    """白名单 + 假前缀表 → 已知前缀集合。"""
    prefixes = set(KNOWN_DOI_PREFIXES)
    if data_dir is None:
        return prefixes
    p = Path(data_dir) / "knowledge" / "doi_fake_prefixes.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for item in data.get("prefixes", []):
                if item.get("prefix"):
                    prefixes.add(item["prefix"])
        except (ValueError, OSError):
            pass
    return prefixes


def doi_prefix(doi):
    if not doi:
        return None
    m = re.match(r"^\s*(10\.\d{4,9})/", doi)
    return m.group(1) if m else None


def load_fake_isbn_ranges(data_dir=None):
    """合成数据专用 ISBN 出版者段白名单（命中视为已知虚构，不报校验位错）。

    M1 生成器以虚构出版者段造 ISBN，校验位非真实——这是合成数据纪律的产物，
    不是幻觉信号；与 DOI 的 `10.9999` 白名单同一口径（data/knowledge/doi_fake_prefixes.json）。
    """
    ranges = set()
    if data_dir is None:
        return ranges
    p = Path(data_dir) / "knowledge" / "doi_fake_prefixes.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            block = data.get("isbn_fake_publisher_ranges") or {}
            for r in block.get("ranges", []):
                ranges.add(r)
        except (ValueError, OSError):
            pass
    return ranges


def _isbn_publisher_range(isbn):
    """取 ISBN-13 出版者段（978-7-XXXX）。"""
    digits = re.sub(r"[^0-9Xx]", "", isbn or "")
    if len(digits) != 13:
        return None
    return "{}-{}-{}".format(digits[0:3], digits[3], digits[4:8])


def _isbn_checksum_ok(isbn):
    """ISBN-10 / ISBN-13 校验位（GB/T 5792 算法）。"""
    digits = re.sub(r"[^0-9Xx]", "", isbn or "")
    if len(digits) == 10:
        total = 0
        for i, ch in enumerate(digits):
            v = 10 if ch in "Xx" else int(ch)
            total += (10 - i) * v
        return total % 11 == 0
    if len(digits) == 13:
        total = 0
        for i, ch in enumerate(digits):
            total += int(ch) * (1 if i % 2 == 0 else 3)
        return total % 10 == 0
    return None  # 长度不对 → 不判（可能是噪声或非 ISBN）


def check_doi(data_dir):
    """DOI 数据面自检：白名单空 = 配置错误（大声失败，不静默降级）。"""
    prefixes = load_known_prefixes(data_dir)
    if not prefixes:
        raise RuntimeError("DOI 已知前缀集为空（数据目录配置错误）")
    return prefixes


def profile_entry(card, known_prefixes, fmt=None, fake_isbn_ranges=None):
    """单条目 → {signals, risk, penalty}。"""
    signals = []
    fake_isbn_ranges = fake_isbn_ranges or set()

    # 1. DOI 前缀未知
    doi = card["identifiers"].get("doi")
    if doi:
        pref = doi_prefix(doi)
        if pref and pref not in known_prefixes:
            signals.append({"type": "doi_prefix_unknown", "field": "doi",
                            "detail": "DOI 前缀 {} 不在已知注册前缀/白名单内".format(pref)})

    # 2. ISBN 校验位（合成数据白名单段豁免——合成纪律产物，非幻觉信号）
    isbn = card["identifiers"].get("isbn")
    if isbn:
        rng = _isbn_publisher_range(isbn)
        if not (rng and rng in fake_isbn_ranges):
            ok = _isbn_checksum_ok(isbn)
            if ok is False:
                signals.append({"type": "isbn_checksum_invalid", "field": "isbn",
                                "detail": "ISBN {} 校验位不合法".format(isbn)})

    # 3. 年份越界
    year = card["source"].get("year")
    if year and re.match(r"^\d{4}$", str(year)):
        y = int(year)
        if y > YEAR_UPPER or y < YEAR_LOWER:
            signals.append({"type": "year_out_of_range", "field": "year",
                            "detail": "年份 {} 超出合理范围 [{}, {}]".format(y, YEAR_LOWER, YEAR_UPPER)})

    # 4. 页码倒置
    pages = card["source"].get("pages")
    if pages:
        m = re.match(r"^(\d+)-(\d+)$", pages)
        if m and int(m.group(1)) > int(m.group(2)):
            signals.append({"type": "page_range_inverted", "field": "pages",
                            "detail": "起页 {} > 止页 {}".format(m.group(1), m.group(2))})

    # 5. 类型-字段组合不可能
    combo = _impossible_combo(card)
    if combo:
        signals.append({"type": "impossible_field_combo", "field": combo[0],
                        "detail": combo[1]})

    # 6. 题名自指
    if _self_referential(card):
        signals.append({"type": "self_referential_title", "field": "title",
                        "detail": "题名与载体名相同或题名内嵌载体名"})

    risk = _grade(signals)
    return {"signals": signals, "risk": risk,
            "penalty": sum(SIGNAL_WEIGHT.get(s["type"], 0) for s in signals)}


def _impossible_combo(card):
    """类型-字段矩阵：期刊条目不得有 ISBN；图书条目不得带卷/期。"""
    et = card["entry_type"]
    src = card["source"]
    ids = card["identifiers"]
    if et == "J" and ids.get("isbn"):
        return ("isbn", "期刊条目不应著录 ISBN")
    if et == "M" and (src.get("volume") or src.get("issue")):
        return ("volume", "图书条目不应著录卷/期")
    if et in ("D", "R") and ids.get("isbn"):
        return ("isbn", "{} 条目不应著录 ISBN".format(et))
    return None


def _self_referential(card):
    title = card.get("title") or ""
    container = card["source"].get("container") or ""
    if not title or not container:
        return False
    if title.strip() == container.strip():
        return True
    return container.strip() in title.strip() and len(container.strip()) >= 4


def _grade(signals):
    if any(s["type"] in STRUCTURAL_SIGNALS for s in signals):
        return "high"
    if signals:
        return "medium"
    return "low"


def health_score(profiles):
    """文献表体检分（Lighthouse 式，0-100）：100 - 平均扣减，下限 0。"""
    if not profiles:
        return 100.0
    total = sum(p["penalty"] for p in profiles)
    return max(0.0, round(100.0 - total / len(profiles), 1))


def profile_refs(cards, ruleset=None, data_dir=None, doc_name=None):
    """REF-06 主入口 → {findings, profiles, health_score, disclaimers, summary}。"""
    known = load_known_prefixes(data_dir)
    if not known:
        raise RuntimeError("DOI 已知前缀集为空（数据目录配置错误）")
    fake_isbn = load_fake_isbn_ranges(data_dir)
    rules = {r["rule_id"]: r for r in ruleset["rules"]} if ruleset else {}
    rule = rules.get("TAW-hallu-signal-01")
    active = rule is not None and engine.is_active(rule)

    profiles = []
    findings = []
    for c in cards:
        prof = profile_entry(c, known, fake_isbn_ranges=fake_isbn)
        prof["entry_id"] = c["card_id"]
        prof["label"] = c["evidence"].get("label")
        profiles.append(prof)
        if not active or not prof["signals"]:
            continue
        status = "manual_confirm" if prof["risk"] == "medium" else "fail"
        for sig in prof["signals"]:
            findings.append(engine.make_rule_finding(
                rule, status,
                {"doc": doc_name or c["evidence"]["src"],
                 "para": c["evidence"]["ordinal"], "span": None,
                 "entry_id": c["card_id"], "field": sig["field"],
                 "label": c["evidence"].get("label")},
                suggestion="人工核对原文/数据库（风险提示，非真伪判定）",
                confidence=0.7 if prof["risk"] == "high" else 0.4,
                detail="[{}] {}".format(sig["type"], sig["detail"]),
            ))
    return {"findings": findings, "profiles": profiles,
            "health_score": health_score(profiles),
            "disclaimers": list(engine.DISCLAIMERS),
            "summary": engine.summarize(findings)}
