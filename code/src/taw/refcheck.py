# -*- coding: utf-8 -*-
"""REF-02 格式核查与自动修正（plan/04 §十 10.2，口径逐条实测校准）。

判定总原则：**只判确定性可判项；证据不充分一律 manual_confirm，不硬判**（NFR-05）。
六类检测（每类挂 ruleset 规则与 basis）：

1. 必著录项缺失（field_required）：按类型取缺项池 + **载体可表达性**校准
   （字段须在同文件同批次其他条目出现过，豁免 ris 无 edition 这类载体语义差异）
   + **噪声门控**（断行/连字符/空格类修复 flag 时不出结论，`year` 抗噪豁免）；
2. 文献类型标识错误（type_marker）：**声明标识 vs 载体原生结构签名**不符；
3. 著者阈值（author_threshold）：双向可判；「恰 3 位带等」为多值歧义 → manual_confirm；
4. 页码倒置（page_range）：起页 > 止页；
5. 编码制混用（citation_style）：无 [n] 标签的著者-出版年制条目混入顺序编码制表；
6. 标点（punct）：清洗会把全角标点归一，故在**残留 flag 与原文**上判
   （题名分隔丢失 / 逗号紧邻 CJK / 末尾多余标点 / bib 著者字段缺逗号）。

机械项（2/3/4 与部分 6）产出 `fixes` 字段级 diff，供逐条接受/回退。
"""

import copy
import json
import re
from pathlib import Path

from taw import engine
from taw.cards import make_author

# ---- 类型 → 缺项池（合成真值契约口径；basis 记在 ruleset） ----
REQUIRED_POOL = {
    "J": ("year", "pages", "volume"),
    "C": ("year", "publisher", "pages"),
    "D": ("year", "city"),
    "M": ("year", "publisher", "pages"),
    "R": ("year", "city"),
}
FIELD_ZH = {"year": "年份", "pages": "页码", "volume": "卷号", "issue": "期号",
            "publisher": "出版社", "city": "出版地", "container": "刊名/书名",
            "edition": "版次", "report_no": "报告号"}

# 噪声风险 flag：带这些 flag 说明解析可能丢字段，不据此判缺项（year 豁免）
RISKY_FLAGS = ("linebreak_repaired", "hyphen_repaired", "space_collapsed",
               "cjk_space_collapsed")
YEAR_EXEMPT = "year"

# 著者阈值判定的载体可见性：ris 渲染器**逐条列出全部著者**、从不渲染"等/others"，
# 故「未截断」与「误加等」在 ris 载体上均不可观察 → ris 不做该判定（载体语义豁免，
# 与 M2 的 ris 无 edition 同类）。txt/csv 用"，等"、bib 用 "others" 表达截断。
AUTHOR_VISIBLE_FORMATS = ("txt", "csv", "bib")

# 载体原生结构签名（marker 无关）：bib 字段名 → 类型
BIB_KEY_SIG = (("journal", "J"), ("booktitle", "C"), ("school", "D"),
               ("isbn", "M"), ("edition", "M"), ("institution", "R"), ("number", "R"))
# ris 标签 → 类型（JO/JF 刊名、T2 会议论文集、SN 图书、NO 报告）
RIS_TAG_SIG = (("JO", "J"), ("JF", "J"), ("T2", "C"), ("SN", "M"), ("NO", "R"))


def _compact(s):
    return re.sub(r"\s+", "", s or "")


def _carrier_fields(cards):
    """本批次卡片实际出现过的字段集合（载体可表达性校准）。"""
    present = set()
    for c in cards:
        for k, v in c["source"].items():
            if v:
                present.add(k)
    return present


def _infer_type(card, fmt, raw_block):
    """载体原生结构签名 → 类型；签名不唯一/缺失 → None（保守，不判）。

    不依赖被注入的标识本身：bib 字段集与 ris 标签集由**真类型**渲染，
    txt/csv 的 body 结构分支同理（`//`→C、报告号→R、版次段→M、卷期段→J）。
    """
    if fmt == "bib":
        blob = _compact(raw_block)
        hits = set()
        for key, t in BIB_KEY_SIG:
            if (key + "={") in blob:
                hits.add(t)
        # number 在 J(期号) 与 R(报告号) 共用：有 journal 时归 J
        if "J" in hits and "R" in hits and "booktitle" not in blob:
            hits.discard("R")
        return hits.pop() if len(hits) == 1 else None
    if fmt == "ris":
        blob = _compact(raw_block)
        hits = set()
        for tag, t in RIS_TAG_SIG:
            if re.search(re.escape(tag) + r"-", blob):
                hits.add(t)
        return hits.pop() if len(hits) == 1 else None
    # txt / csv：用清洗后 raw 的结构分支（与 refparse._walk_body 同口径）
    from taw import refparse
    raw = card["evidence"]["raw"] or ""
    b = (raw.split("]", 1)[-1] if "]" in raw else raw).strip().lstrip(".\u3002\uff0c, ").strip()
    if not b:
        return None
    if b.startswith("//"):
        return "C"
    if refparse._REPORT_NO_TAIL.search(b):
        return "R"
    segs = b.split(", ")
    if segs and segs[0] and refparse._EDITION_SEG.match(segs[0]):
        return "M"
    for seg in segs:
        if (refparse._SEG_VOL_ISSUE.match(seg) or refparse._SEG_ISSUE.match(seg)
                or refparse._SEG_VOL.match(seg)):
            return "J"
    return None


def _raw_blocks(fmt, src_text):
    """原始文本 → {ordinal: 块文本}（bib 按 @ 块、ris 按 TY..ER、txt/csv 按标签/行）。"""
    if src_text is None:
        return {}
    text = src_text.replace("\r\n", "\n")
    out = {}
    if fmt == "bib":
        idx = 0
        for blk in re.split(r"\n(?=@)", text):
            if "@" not in blk:
                continue
            idx += 1
            out[idx] = blk
        return out
    if fmt == "ris":
        idx = 0
        cur = None
        for ln in text.split("\n"):
            if ln.strip().startswith("TY"):
                idx += 1
                cur = [ln]
                out[idx] = cur
            elif cur is not None:
                cur.append(ln)
        return {k: "\n".join(v) for k, v in out.items()}
    if fmt == "txt":
        cur = None
        label_to_block = {}
        for ln in text.split("\n"):
            if not ln.strip():
                continue
            m = re.match(r"^\[\s*(\d{1,3}(?:\s+\d{1,3})*)\s*\]\s*", ln.strip())
            if m:
                cur = re.sub(r"\s+", "", m.group(1))
                label_to_block[cur] = [ln.strip()[m.end():]]
            elif cur is not None:
                label_to_block[cur].append(ln)
        return label_to_block
    return {}


def _lookup_raw(fmt, blocks, card):
    """按 card 的标签（txt）/序位（bib/ris）取原始块；取不到给 None。"""
    if not blocks:
        return None
    if fmt == "txt":
        return "".join(blocks.get(card["evidence"]["label"] or "", [])) or None
    return blocks.get(card["evidence"]["ordinal"])


def _effective_type(card, fmt, blocks):
    """该卡片用于缺项判定的类型：结构签名优先（与 type_marker 判据一致）。"""
    inferred = _infer_type(card, fmt, _lookup_raw(fmt, blocks, card) or "")
    return inferred if inferred is not None else card["entry_type"]


# ---- 各类检测 ----


def _check_field_required(cards, rule, doc_name, carrier, entry_type=None):
    """缺项：类型池 + 载体可表达性 + 噪声门控（year 豁免）。

    entry_type 给定时按该类型的缺项池判（标识错条目已由调用方按结构推断归位）。
    """
    findings = []
    for c in cards:
        t = entry_type if entry_type is not None else c["entry_type"]
        pool = REQUIRED_POOL.get(t)
        if pool is None:
            continue
        risky = bool(set(c["flags"]) & set(RISKY_FLAGS))
        for f in pool:
            if f not in carrier:
                continue
            if risky and f != YEAR_EXEMPT:
                continue
            if c["source"].get(f):
                continue
            findings.append(engine.make_rule_finding(
                rule, "fail",
                _loc(doc_name, c, f),
                suggestion="补齐{}或标注缺项".format(FIELD_ZH.get(f, f)),
                confidence=0.9,
                detail="{}条目缺少{}".format(t, FIELD_ZH.get(f, f)),
            ))
    return findings


def _check_type_marker(cards, rule, doc_name, fmt, blocks):
    """标识错误：声明标识 vs 载体原生结构签名不符（签名唯一才判）。"""
    findings = []
    for c in cards:
        declared = c["entry_type"]
        inferred = _infer_type(c, fmt, _lookup_raw(fmt, blocks, c) or "")
        if inferred is None or declared is None or inferred == declared:
            continue
        findings.append(engine.make_rule_finding(
            rule, "fail",
            _loc(doc_name, c, "entry_type"),
            suggestion="按载体与内容改写标识为 [{}]".format(inferred),
            confidence=0.9,
            detail="声明标识 [{}] 与载体结构（{} 型）不符".format(declared, inferred),
            fix={"type": "auto", "field": "entry_type",
                 "before": declared, "after": inferred},
        ))
    return findings


def _check_author_threshold(cards, rule, doc_name, fmt, strict=False):
    """著者阈值：>3 未截断 / <3 误加'等' → fail。

    「恰列出 3 位且带'等'」不可判：既有可能是"3 位著者误加等"，也可能是
    "题名>"前三+等"的正确截断（两者渲染串完全相同）。按"误报 0 优先"默认**静默**，
    `strict=True` 时以 manual_confirm 进入人工复核队列。
    """
    if fmt not in AUTHOR_VISIBLE_FORMATS:
        return []
    findings = []
    for c in cards:
        n = len(c["authors"])
        truncated = "authors_truncated" in c["flags"]
        if n > 3 and not truncated:
            listed = [a["raw"] for a in c["authors"]]
            west = bool(listed) and not re.search(r"[\u4e00-\u9fff]", " ".join(listed))
            findings.append(engine.make_rule_finding(
                rule, "fail", _loc(doc_name, c, "authors"),
                suggestion="按前三 + '{}' 截断".format("et al" if west else "等"),
                confidence=0.9,
                detail="列出 {} 位著者未按'前三+等'截断".format(n),
                fix={"type": "auto", "field": "authors", "before": listed,
                     "after": listed[:3] + ["et al" if west else "等"]},
            ))
        elif truncated and n < 3:
            findings.append(engine.make_rule_finding(
                rule, "fail", _loc(doc_name, c, "authors"),
                suggestion="删除多余的'等/et al'",
                confidence=0.9,
                detail="仅 {} 位著者却使用'等'".format(n),
                fix={"type": "auto", "field": "authors",
                     "before": [a["raw"] for a in c["authors"]] + ["等"],
                     "after": [a["raw"] for a in c["authors"]]},
            ))
        elif truncated and n == 3 and strict:
            findings.append(engine.make_rule_finding(
                rule, "manual_confirm", _loc(doc_name, c, "authors"),
                suggestion="核对原文著者总数后决定是否保留'等'",
                confidence=0.4,
                detail="恰列出 3 位著者且带'等'：原著者数可能恰为 3（误加），"
                       "也可能 >3（正确截断），引文字面不可区分",
            ))
    return findings


def _check_page_range(cards, rule, doc_name):
    findings = []
    for c in cards:
        pages = c["source"].get("pages")
        if not pages:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", pages)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            findings.append(engine.make_rule_finding(
                rule, "fail", _loc(doc_name, c, "pages"),
                suggestion="起止页升序重排为 {}-{}".format(b, a),
                confidence=0.99,
                detail="页码倒置 {}-{}".format(a, b),
                fix={"type": "auto", "field": "pages",
                     "before": pages, "after": "{}-{}".format(b, a)},
            ))
    return findings


def _check_citation_style(cards, rule, doc_name):
    """编码制混用：文件级 finding（无 [n] 标签的著者-出版年制条目混入）。"""
    mixed = [c for c in cards
             if c["evidence"]["label"] is None and "author_year_form" in c["flags"]]
    if not mixed:
        return []
    return [engine.make_rule_finding(
        rule, "fail",
        {"doc": doc_name, "para": None, "span": None,
         "entry_id": None, "label": None},
        suggestion="按主体编码制统一重排（或改为顺序编码制）",
        confidence=0.85,
        detail="文献表混入 {} 条著者-出版年制条目（顺序编码制表中无 [n] 编号）".format(len(mixed)),
    )]


def _check_standard_currency(cards, rule, doc_name, replacements):
    """双标尺：条目引用的标准若已被新版替代 → fail（迁移清单展示面）。

    依据 `data/knowledge/standard_replacements.json`（替代关系逐条挂官方来源，
    identity_status=verified）。这是"新旧版双标尺"的可判子集：被引标准本身换版。
    """
    if not replacements:
        return []
    by_old = {r["old"]: r for r in replacements}
    findings = []
    for c in cards:
        text = " ".join(filter(None, [c.get("title"), c["source"].get("container"),
                                      c["source"].get("report_no")]))
        for old, rep in sorted(by_old.items()):
            if old in text:
                findings.append(engine.make_rule_finding(
                    rule, "fail", _loc(doc_name, c, "standard_ref"),
                    suggestion="改用现行版 {}".format(rep["new"]),
                    confidence=0.9,
                    detail="引用的标准 {} 已废止（{} 于 {} 实施替代）".format(
                        old, rep["new"], rep.get("new_implement_date") or "已实施"),
                    fix={"type": "suggest", "field": "standard_ref",
                         "before": old, "after": rep["new"]},
                ))
    return findings


def _check_consistency(cards, rule, doc_name):
    """结构矛盾：DOI 年份段与出版年不一致（合成注入的"时间逻辑矛盾"确定性子集）。

    守门：year 必须是规范 4 位年份、doi 必须含年份段——两者之一被噪声污染
    （如 ris SP/EP 撕裂把 "2019SP- 16" 混入 year）时不出结论，避免误报。
    """
    findings = []
    for c in cards:
        doi = c["identifiers"].get("doi")
        year = c["source"].get("year")
        if not doi or not year or not re.match(r"^(?:19|20)\d{2}$", str(year)):
            continue
        m = re.search(r"/(?:[a-z]+\.)?((?:19|20)\d{2})\.", doi)
        if not m:
            continue
        doi_year = m.group(1)
        if doi_year != year:
            findings.append(engine.make_rule_finding(
                rule, "fail", _loc(doc_name, c, "doi"),
                suggestion="核对 DOI 年份段与出版年（二者应一致）",
                confidence=0.9,
                detail="DOI 年份段 {} 与出版年 {} 矛盾".format(doi_year, year),
            ))
    return findings


def _check_punct(cards, rule, doc_name, fmt, blocks):
    """标点：清洗已归一全角，故在残留 flag / 原文 / bib 字段行上判。"""
    findings = []
    for c in cards:
        raw_clean = c["evidence"]["raw"] or ""
        raw_orig = _lookup_raw(fmt, blocks, c)
        detail = None
        if fmt in ("txt", "csv"):
            if "authors_title_separator_missing" in c["flags"]:
                detail = "题名前著录分隔（'. '）缺失"
            else:
                m = re.search(r"[\u4e00-\u9fff],(?=[\u4e00-\u9fff])", raw_clean)
                if m:
                    detail = "中文逗号残留（应为', '）"
                elif re.search(r"[,.]\s*[,.]\s*$", raw_clean.rstrip()):
                    detail = "条目末尾多余标点"
                elif raw_orig is not None and re.search(r"[\uff0c\uff1a]", raw_orig):
                    detail = "著录标点使用全角（，/：）"
        elif fmt == "bib" and raw_orig is not None:
            for ln in raw_orig.replace("\r", "").split("\n"):
                if re.match(r"^\s*auth?or\s*=", ln):
                    s = ln.rstrip()
                    if s.endswith("}") and not s.endswith("},"):
                        detail = "著者字段行末缺逗号"
                    break
        if detail:
            findings.append(engine.make_rule_finding(
                rule, "fail", _loc(doc_name, c, "punctuation"),
                suggestion="按 GB/T 7714 著录标点归一（条款待核对）",
                confidence=0.85, detail=detail,
            ))
    return findings


_RULE_IDS = {
    "punct": "GBT7714-punct-01",
    "author_threshold": "GBT7714-author-01",
    "type_marker": "GBT7714-marker-01",
    "page_range": "GBT7714-pagerange-01",
    "citation_style": "GBT7714-citestyle-01",
}


def _fieldreq_rule_id(entry_type):
    return "GBT7714-fieldreq-{}-01".format(entry_type)


def _loc(doc_name, card, field):
    return {"doc": doc_name, "para": card["evidence"]["ordinal"],
            "span": None, "entry_id": card["card_id"], "field": field,
            "label": card["evidence"]["label"]}


def check_format(cards, ruleset, fmt=None, src_text=None, doc_name=None,
                 data_dir=None):
    """REF-02 主入口 → {findings, fixes, disclaimers, summary}。

    规则生效以 ruleset 的 `activation` 为准（engine.is_active）：仅 active 的规则运行；
    findings 携带 clause_status/basis，pending 条款在报告中标注"条款待核对"。
    """
    doc_name = doc_name or (cards[0]["evidence"]["src"] if cards else "refs")
    blocks = _raw_blocks(fmt, src_text)
    carrier = _carrier_fields(cards)
    rules = {r["rule_id"]: r for r in ruleset["rules"]} if ruleset else {}
    findings = []

    def _rule_for(check_type):
        for r in rules.values():
            if r.get("check_type") == check_type and engine.is_active(r):
                return r
        return None

    r = _rule_for("field_required")
    if r is not None:
        # 每条卡片只在**一个**有效类型池下判：标识与结构签名不符时以结构签名为准
        # （标识错误本身另由 type_marker 报；按声明类型再判一次会连锁误报，
        #  实测：误标 C 的 J 条目在 C 池下"缺出版社"= 纯误报）。
        for t in REQUIRED_POOL:
            sub = [c for c in cards if _effective_type(c, fmt, blocks) == t]
            if not sub:
                continue
            findings.extend(_check_field_required(sub, r, doc_name, carrier, entry_type=t))

    for check_type, fn, kwargs in (
        ("type_marker", _check_type_marker, {"fmt": fmt, "blocks": blocks}),
        ("author_threshold", _check_author_threshold, {"fmt": fmt}),
        ("page_range", _check_page_range, {}),
        ("consistency", _check_consistency, {}),
        ("citation_style", _check_citation_style, {}),
        ("punct", _check_punct, {"fmt": fmt, "blocks": blocks}),
    ):
        r = _rule_for(check_type)
        if r is None:
            continue
        findings.extend(fn(cards, r, doc_name, **kwargs))

    # 双标尺：被引标准换版（依据 data/knowledge/standard_replacements.json）
    r = _rule_for("standard_currency")
    if r is not None:
        findings.extend(_check_standard_currency(
            cards, r, doc_name, load_replacements(data_dir)))

    return {
        "findings": findings,
        "fixes": [f["fix"] for f in findings if f.get("fix")],
        "disclaimers": list(engine.DISCLAIMERS),
        "summary": engine.summarize(findings),
    }


def load_replacements(data_dir=None):
    """读标准替代关系（无出处不入库；文件缺失时返回空表，不静默造假）。"""
    if data_dir is None:
        return []
    p = Path(data_dir) / "knowledge" / "standard_replacements.json"
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    return [r for r in data.get("replacements", [])
            if r.get("identity_status") == "verified" and r.get("source")]


def apply_fix(card, fix):
    """把一条字段级 fix 落到卡片副本（供"逐条接受/回退"）。返回新卡片。

    修正不仅改字段值，还要同步该判定所依赖的派生标志——否则"接受修正"后
    重查仍会命中同一 finding（自相矛盾）。目前涉及 `authors_truncated`
    （著者截断状态的记录）。
    """
    new = copy.deepcopy(card)
    field = fix["field"]
    if field == "entry_type":
        new["entry_type"] = fix["after"]
    elif field == "pages":
        new["source"]["pages"] = fix["after"]
    elif field == "authors":
        built = []
        truncated = bool(fix.get("after")) and fix["after"][-1] in ("等", "et al")
        for raw in fix["after"]:
            if raw in ("等", "et al"):
                prev = built[-1]
                built[-1] = make_author(prev["raw"] + ", " + raw,
                                        prev["family"], prev["given"])
            else:
                built.append(make_author(raw))
        new["authors"] = built
        # 同步截断标志（判定依据）
        if truncated and "authors_truncated" not in new["flags"]:
            new["flags"] = sorted(set(new["flags"]) | {"authors_truncated"})
        elif not truncated and "authors_truncated" in new["flags"]:
            new["flags"] = [f for f in new["flags"] if f != "authors_truncated"]
    return new
