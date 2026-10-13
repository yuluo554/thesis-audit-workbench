# -*- coding: utf-8 -*-
"""REF-04 正文引用 ↔ 文献表对账（plan/04 §四 + §十；FR-04）。

两类输入：
- 文献表 → RefCard 序列（含 `evidence.label` = `[n]` 编号）；
- 正文 → 引用标记序列（顺序编码制 `[1]`/`[2,5-7]`/`[3-5]`，或著者-出版年制
  `张三等（2020）`/`(Smith et al., 2020)`）。

四类结论（与 04 §四对象审计同构：悬空 ↔ 幽灵）：
1. **悬空引用 dangling_citation**：正文标记指向的编号在文献表中不存在；
2. **幽灵文献 ghost_reference**：文献表条目在正文中从未被引用；
3. **乱序断档 order_gap**：首次引用顺序非升序（顺序编码制要求按引用先后编号），
   或文献表编号出现空档（1,2,4 缺 3）；
4. **著者-年份不匹配 author_year_mismatch**：著者-出版年制标记的著者/年份
   与文献表对应条目不符。

判定纪律（NFR-05）：无法确定对应条目（如多条同姓同年的歧义）→ `manual_confirm`。
"""

import re

from taw import engine

# 顺序编码制标记：方括号内数字与区间（, - ，－）组合
_NUM_BRACKET = re.compile(r"\[\s*(\d{1,3}(?:\s*[,\-\u2013\u2014\uff0d，]\s*\d{1,3})*)\s*\]")
_NUM_PART = re.compile(r"(\d{1,3})(?:\s*[-\u2013\u2014\uff0d]\s*(\d{1,3}))?")
# 著者-出版年制：(著者, 年) / 著者（年）/ 著者等（年）
# 著者段允许空格（西文 "SMITH J"），但不跨标点，避免吞掉整句
_AY_PAREN = re.compile(
    r"[(（]\s*([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff .&]*?)"
    r"(?:\s*(?:等|et al\.?))?\s*[,，]\s*((?:19|20)\d{2})\s*[)）]")
_AY_INLINE = re.compile(
    r"([A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff .&]{0,20}?)"
    r"(?:\s*(?:等|et al\.?))?\s*[（(]\s*((?:19|20)\d{2})\s*[)）]")


def expand_numbers(spec):
    """`2,5-7` → [2, 5, 6, 7]（区间升序展开；单值原样）。"""
    out = []
    for part in re.split(r"[,\uff0c]", spec):
        part = part.strip()
        if not part:
            continue
        m = _NUM_PART.fullmatch(part)
        if not m:
            continue
        a = int(m.group(1))
        if m.group(2) is None:
            out.append(a)
        else:
            b = int(m.group(2))
            lo, hi = (a, b) if a <= b else (b, a)
            out.extend(range(lo, hi + 1))
    return out


def _sentence_of(text, pos):
    """标记所在句（引用语境，REF-08 论证链复用）。"""
    start = max(text.rfind(c, 0, pos) for c in "。！？.!?；;\n") + 1
    end = min([i for i in (text.find(c, pos) for c in "。！？.!?；;\n") if i != -1] or [len(text)])
    return text[start:end].strip()


def parse_markers(text, doc_name="body"):
    """正文 → [marker]；marker = {kind, numbers|author,year, label, para, context}。

    kind ∈ {numeric, author_year}；para 为段落序号（纯文本按行/空行分段，
    docx 传段落列表时由调用方给出）。
    """
    markers = []
    for pi, para in enumerate(text.split("\n")):
        for m in _NUM_BRACKET.finditer(para):
            nums = expand_numbers(m.group(1))
            if not nums:
                continue
            markers.append({"kind": "numeric", "numbers": nums,
                            "label": re.sub(r"\s+", "", m.group(1)),
                            "para": pi, "context": _sentence_of(para, m.start())})
        for rx in (_AY_PAREN, _AY_INLINE):
            for m in rx.finditer(para):
                markers.append({"kind": "author_year",
                                "author": m.group(1).strip().rstrip(".,，"),
                                "year": m.group(2), "para": pi,
                                "context": _sentence_of(para, m.start())})
    return markers


def _refs_by_label(cards):
    """RefCard → {int(label): card}（label 形如 '1' 或 '1,2' 的合并编号取首值）。"""
    out = {}
    for c in cards:
        lab = c["evidence"].get("label")
        if not lab:
            continue
        nums = expand_numbers(str(lab))
        if nums:
            out[nums[0]] = c
    return out


def _author_key(name):
    """人名归一：取姓（中文首字 / 西文首 token），小写。"""
    name = (name or "").strip()
    if not name:
        return ""
    if re.search(r"[\u4e00-\u9fff]", name):
        return name[0]
    return name.split()[0].lower().rstrip(".,")


def reconcile(cards, markers, ruleset=None, doc_name="body"):
    """REF-04 主入口 → {findings, disclaimers, summary}。"""
    rules = {r["rule_id"]: r for r in ruleset["rules"]} if ruleset else {}

    def _rule(rid):
        r = rules.get(rid)
        if r is None or not engine.is_active(r):
            return None
        return r

    by_label = _refs_by_label(cards)
    findings = []
    cited_numbers = set()

    # 1. 悬空引用
    r_dangling = _rule("GBT7714-cite-dangling-01")
    if r_dangling is not None:
        for mk in markers:
            if mk["kind"] != "numeric":
                continue
            for n in mk["numbers"]:
                cited_numbers.add(n)
                if n not in by_label:
                    findings.append(engine.make_rule_finding(
                        r_dangling, "fail",
                        {"doc": doc_name, "para": mk["para"], "span": None,
                         "label": "[{}]".format(n), "ref_no": n},
                        suggestion="补入文献表或修正编号",
                        confidence=0.9,
                        detail="正文引用 [{}] 在文献表中不存在".format(n),
                        ))

    # 2. 幽灵文献（表内从未被引用）
    r_ghost = _rule("GBT7714-cite-ghost-01")
    if r_ghost is not None and cited_numbers:
        for n in sorted(by_label):
            if n not in cited_numbers:
                c = by_label[n]
                findings.append(engine.make_rule_finding(
                    r_ghost, "fail",
                    {"doc": doc_name, "para": None, "span": None,
                     "label": "[{}]".format(n), "ref_no": n,
                     "entry_id": c["card_id"]},
                    suggestion="在正文相应处引用该文献，或从文献表删除",
                    confidence=0.85,
                    detail="文献表条目 [{}] 在正文中从未被引用".format(n),
                ))

    # 3. 乱序断档：首次引用顺序须升序（顺序编码制按引用先后编号）
    r_order = _rule("GBT7714-cite-order-01")
    if r_order is not None:
        first_seen = []
        for mk in markers:
            if mk["kind"] != "numeric":
                continue
            for n in mk["numbers"]:
                if n not in first_seen:
                    first_seen.append(n)
        descending = [(a, b) for a, b in zip(first_seen, first_seen[1:]) if b < a]
        if descending:
            findings.append(engine.make_rule_finding(
                r_order, "fail",
                {"doc": doc_name, "para": None, "span": None, "label": None},
                suggestion="按正文首次引用顺序重排编号（renumber 内核）",
                confidence=0.85,
                detail="首次引用顺序非升序：{}（如 {} 先于 {}）".format(
                    first_seen, descending[0][0], descending[0][1]),
            ))
        if by_label:
            # 断档 = 文献表自身的编号序列不连续（1..max 内缺号）。
            # 只查表内范围，不把正文里的越界编号（那是悬空引用）算成断档。
            hi = max(by_label)
            missing = [n for n in range(1, hi + 1) if n not in by_label]
            if missing:
                findings.append(engine.make_rule_finding(
                    r_order, "fail",
                    {"doc": doc_name, "para": None, "span": None, "label": None},
                    suggestion="核对编号连续性（可能有条目丢失）",
                    confidence=0.8,
                    detail="文献表编号存在空档：缺 {}".format(missing),
                ))

    # 4. 著者-年份不匹配
    r_ay = _rule("GBT7714-cite-ay-01")
    if r_ay is not None:
        for mk in markers:
            if mk["kind"] != "author_year":
                continue
            key = _author_key(mk["author"])
            cands = [c for c in cards
                     if any(_author_key(a.get("family") or a["raw"]) == key
                            for a in c["authors"])]
            if not cands:
                findings.append(engine.make_rule_finding(
                    r_ay, "fail",
                    {"doc": doc_name, "para": mk["para"], "span": None,
                     "label": mk["author"]},
                    suggestion="补入文献表或修正著者名",
                    confidence=0.85,
                    detail="正文引用 '{}（{}）' 在文献表中无同著者条目".format(
                        mk["author"], mk["year"]),
                ))
                continue
            if not any(c["source"].get("year") == mk["year"] for c in cands):
                findings.append(engine.make_rule_finding(
                    r_ay, "fail",
                    {"doc": doc_name, "para": mk["para"], "span": None,
                     "label": mk["author"]},
                    suggestion="核对著者-年份与文献表条目",
                    confidence=0.8,
                    detail="正文 '{}（{}）' 与文献表年份不符（表内为 {}）".format(
                        mk["author"], mk["year"],
                        sorted({str(c["source"].get("year")) for c in cands})),
                ))

    return {"findings": findings, "disclaimers": list(engine.DISCLAIMERS),
            "summary": engine.summarize(findings),
            "cited_numbers": sorted(cited_numbers),
            "table_numbers": sorted(by_label)}


def extract_citation_context(cards, markers):
    """REF-08 论证链输入：{label/编号 → [引用语境...]}。"""
    by_label = _refs_by_label(cards)
    ctx = {}
    for mk in markers:
        if mk["kind"] == "numeric":
            for n in mk["numbers"]:
                c = by_label.get(n)
                if c is not None:
                    ctx.setdefault(c["card_id"], []).append(
                        {"para": mk["para"], "context": mk["context"]})
        else:
            key = _author_key(mk["author"])
            for c in cards:
                if any(_author_key(a.get("family") or a["raw"]) == key
                       for a in c["authors"]):
                    ctx.setdefault(c["card_id"], []).append(
                        {"para": mk["para"], "context": mk["context"]})
    return ctx
