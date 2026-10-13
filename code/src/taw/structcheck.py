# -*- coding: utf-8 -*-
"""FULL-06 结构检查单（plan/01 §15、plan/02 FR-15）。

挂 GB/T 7713.1-2025 的**交互式检查单**：逐条给出"结构要素是否齐备"的确定性
判定与位置证据。检查项（engine check_type = `structure_order` / `structure_checklist`）：

| 检查项 | 判据 | 依据 |
|---|---|---|
| 摘要存在 | 有"摘要"标题段与摘要正文 | GB/T 7713.1 |
| 摘要四要素 | 摘要正文含目的/方法/结果/结论指向（四类关键词命中） | 同上 |
| 关键词数量 | 关键词行 3-8 个（学位论文常见区间） | 同上 |
| 英文摘要 | 有 Abstract 标题与 Keywords 行 | 同上 |
| 章节完整 | 绪论/方法/实验或结果/结论 四类章齐备 | 同上 |
| 每章小结 | 非末章有本节/章小结或过渡段 | 工程口径 |
| 结论呼应摘要 | 结论章与摘要共有≥1 个主题词 | 工程口径 |

另产出 **heading 层级序列**检查（`structure_order`）：章级标题恒为 Heading 1，
节级 Heading 2；层级断档（H1 直接跳 H3，或章标题降级）即报。

判定纪律（误报 0 优先）：全部检查项基于**字面与样式**的确定性判据；
"结论呼应摘要"用共词比例阈值而非语义推断。
"""

import re

from taw import engine

# 摘要四要素的指向词（命中即视为该要素有指向；宽口径但确定性）
_ABSTRACT_ELEMENTS = {
    "purpose": ("针对", "目的", "旨在", "为了"),
    "method": ("方法", "提出", "设计", "构建", "采用"),
    "result": ("结果", "表明", "验证", "取得", "显示"),
    "conclusion": ("结论", "因此", "说明", "证明"),
}

# 章节类别的标题关键词（命中即归类；用于"章节完整"与"每章小结"）
_CHAPTER_KINDS = {
    "intro": ("绪论", "引言", "研究背景"),
    "related": ("相关工作", "文献综述", "研究现状"),
    "method": ("方法", "框架", "模型", "设计"),
    "experiment": ("实验", "结果", "分析", "验证"),
    "conclusion": ("总结", "结论", "展望"),
}

_CN_NUM = "一二三四五六七八九十"
_CHAPTER_HEAD = re.compile(r"^第\s*[%s\d]{1,3}\s*章" % _CN_NUM)
_SECTION_HEAD = re.compile(r"^\d{1,2}(?:\.\d{1,2})+\s+\S")
_KEYWORD_LINE = re.compile(r"^\s*关键词\s*[:：]\s*(.+)$")
_EN_KEYWORD_LINE = re.compile(r"^\s*Keywords\s*[:：]\s*(.+)$", re.I)
_ABSTRACT_HEAD = re.compile(r"^摘\s*要$")
_ABSTRACT_EN_HEAD = re.compile(r"^Abstract$", re.I)


def parse_structure(style_tree):
    """样式树 → 结构模型：标题层级序列 / 摘要 / 关键词 / 章节 / 段落角色。"""
    headings = []          # [{para, level, text}]
    abstract_paras = []
    keyword_counts = {"zh": None, "en": None}
    chapter_titles = []
    for p in style_tree:
        text = p["text"].strip()
        style = p["style"]
        lvl = _heading_level(style)
        if lvl:
            headings.append({"para": p["i"], "level": lvl, "text": text})
            if lvl == 1:
                chapter_titles.append({"para": p["i"], "text": text})
        if _ABSTRACT_HEAD.match(text):
            headings.append({"para": p["i"], "level": 1, "text": text})
        m = _KEYWORD_LINE.match(text)
        if m:
            keyword_counts["zh"] = _count_keywords(m.group(1))
        m = _EN_KEYWORD_LINE.match(text)
        if m:
            keyword_counts["en"] = _count_keywords(m.group(1))
        if _ABSTRACT_EN_HEAD.match(text):
            headings.append({"para": p["i"], "level": 1, "text": text})
    return {"headings": headings, "chapters": chapter_titles,
            "keyword_counts": keyword_counts,
            "style_tree": style_tree}


def _heading_level(style):
    m = re.match(r"^Heading\s+(\d)$", style or "")
    return int(m.group(1)) if m else None


def _count_keywords(s):
    parts = [x.strip() for x in re.split(r"[；;，,、]", s) if x.strip()]
    return len(parts)


def _abstract_text(style_tree, headings):
    """摘要正文：'摘要'标题之后、下一个标题之前的全部段落。"""
    start = None
    for h in headings:
        if _ABSTRACT_HEAD.match(h["text"]):
            start = h["para"]
            break
    if start is None:
        return ""
    out = []
    for p in style_tree:
        if p["i"] <= start:
            continue
        if _heading_level(p["style"]) or _ABSTRACT_EN_HEAD.match(p["text"].strip()):
            break
        out.append(p["text"])
    return " ".join(out)


def _abstract_elements(text):
    return sorted(k for k, words in _ABSTRACT_ELEMENTS.items()
                  if any(w in text for w in words))


def _chapter_categories(chapters):
    cats = set()
    for c in chapters:
        t = c["text"]
        for cat, words in _CHAPTER_KINDS.items():
            if any(w in t for w in words):
                cats.add(cat)
    return cats


def _theme_words(text):
    """主题词（CJK bigram 集合）——用于结论-摘要呼应（确定性，无语义模型）。"""
    runs = re.findall(r"[{}]+".format(r"\u4e00-\u9fff"), text or "")
    out = set()
    for r in runs:
        out.update(r[i:i + 2] for i in range(len(r) - 1))
    return out


# ---- 检查项 ----


def check_structure(parsed, ruleset, doc_name="thesis"):
    """FULL-06 主入口 → {findings, checklist, disclaimers, summary}。

    checklist 为**交互式检查单**（逐项 {id, name, ok, evidence}）；
    findings 只对未通过项产出（structure_order / structure_checklist 两类规则）。
    """
    rules = {}
    if ruleset:
        for r in ruleset["rules"]:
            rules.setdefault(r.get("check_type"), r)

    def _active(ct):
        r = rules.get(ct)
        if r is None or not engine.is_active(r):
            return None
        return r

    style_tree = parsed.get("style_tree", [])
    st = parse_structure(style_tree)
    headings = st["headings"]
    abstract_text = _abstract_text(style_tree, headings)
    elements = _abstract_elements(abstract_text)
    chapters = st["chapters"]
    cats = _chapter_categories(chapters)

    # 章标题降级（Heading != 1）
    degraded = [h for h in headings
                if _CHAPTER_HEAD.match(h["text"]) and h["level"] != 1]
    level_jumps = _level_jumps(headings)

    checklist = [
        {"id": "abstract_present", "name": "摘要存在",
         "ok": bool(abstract_text.strip()),
         "evidence": "摘要正文 {} 字".format(len(abstract_text))},
        {"id": "abstract_elements", "name": "摘要四要素（目的/方法/结果/结论）",
         "ok": len(elements) >= 3,
         "evidence": "命中要素：{}".format("、".join(elements) or "无")},
        {"id": "keywords_count", "name": "关键词数量（3-8）",
         "ok": st["keyword_counts"]["zh"] is not None
         and 3 <= st["keyword_counts"]["zh"] <= 8,
         "evidence": "关键词 {} 个".format(st["keyword_counts"]["zh"])},
        {"id": "english_abstract", "name": "英文摘要与 Keywords",
         "ok": st["keyword_counts"]["en"] is not None
         and any(_ABSTRACT_EN_HEAD.match(h["text"]) for h in headings),
         "evidence": "English keywords {} 个".format(st["keyword_counts"]["en"])},
        {"id": "chapters_complete", "name": "章节完整（绪论/方法/实验/结论）",
         "ok": {"intro", "method", "conclusion"} <= cats,
         "evidence": "识别章节类别：{}".format("、".join(sorted(cats)) or "无")},
        {"id": "chapter_summary", "name": "每章小结",
         "ok": _has_chapter_summary(style_tree, chapters),
         "evidence": "小结段 {} 处".format(_count_chapter_summaries(style_tree, chapters))},
        {"id": "conclusion_echo", "name": "结论与摘要呼应",
         "ok": _conclusion_echo(style_tree, chapters, abstract_text),
         "evidence": "结论-摘要共现主题词 {}".format(
             _echo_overlap(style_tree, chapters, abstract_text))},
        {"id": "heading_levels", "name": "章级标题层级（恒 Heading 1）",
         "ok": not degraded,
         "evidence": "降级章标题 {} 处".format(len(degraded))},
    ]

    findings = []
    r_struct = _active("structure_order")
    if r_struct is not None:
        for h in degraded:
            findings.append(engine.make_rule_finding(
                r_struct, "fail",
                {"doc": doc_name, "para": h["para"], "span": None,
                 "field": "heading_sequence", "label": h["text"]},
                suggestion="章级标题改用 Heading 1（层级序列连续）",
                confidence=0.9,
                detail="章标题 '{}' 使用 Heading {}，层级序列断档（章级应为 Heading 1）".format(
                    h["text"], h["level"]),
            ))
        for j in level_jumps:
            findings.append(engine.make_rule_finding(
                r_struct, "fail",
                {"doc": doc_name, "para": j["para"], "span": None,
                 "field": "heading_sequence", "label": j["text"]},
                suggestion="补齐中间层级或调整标题级别",
                confidence=0.85,
                detail="标题层级从 H{} 跳到 H{}（'{}'）".format(
                    j["from"], j["to"], j["text"]),
            ))

    r_check = _active("structure_checklist")
    if r_check is not None:
        for item in checklist:
            if item["ok"]:
                continue
            findings.append(engine.make_rule_finding(
                r_check, "fail",
                {"doc": doc_name, "para": None, "span": None,
                 "field": item["id"], "label": item["name"]},
                suggestion="按 GB/T 7713.1-2025 结构要求补全（条款待核对）",
                confidence=0.8,
                detail="结构检查项未通过：{}（{}）".format(item["name"], item["evidence"]),
            ))

    return {"findings": findings, "checklist": checklist,
            "structure": {"chapters": chapters, "headings": headings,
                          "kw": st["keyword_counts"]},
            "disclaimers": list(engine.DISCLAIMERS),
            "summary": engine.summarize(findings)}


def _level_jumps(headings):
    """相邻标题层级跳跃（跳级 ≥2）——H1→H3 之类；同段重复不计。"""
    out = []
    prev = None
    for h in headings:
        if prev is not None and h["level"] - prev["level"] >= 2:
            out.append({"para": h["para"], "text": h["text"],
                        "from": prev["level"], "to": h["level"]})
        prev = h
    return out


def _count_chapter_summaries(style_tree, chapters):
    """每章小结：章末段落含"小结/本章/由此可见"等收束词的章数（去掉末章）。"""
    if len(chapters) < 2:
        return 0
    bounds = [c["para"] for c in chapters] + [len(style_tree)]
    n = 0
    for i in range(len(chapters) - 1):
        seg = [p["text"] for p in style_tree if bounds[i] < p["i"] < bounds[i + 1]]
        if any(re.search(r"(小结|本章|以上|由此可见|综上)", t) for t in seg):
            n += 1
    return n


def _has_chapter_summary(style_tree, chapters):
    return _count_chapter_summaries(style_tree, chapters) >= 1


def _echo_overlap(style_tree, chapters, abstract_text):
    if not chapters:
        return 0
    last = chapters[-1]["para"]
    concl_text = " ".join(p["text"] for p in style_tree if p["i"] > last)
    return len(_theme_words(concl_text) & _theme_words(abstract_text))


def _conclusion_echo(style_tree, chapters, abstract_text):
    return _echo_overlap(style_tree, chapters, abstract_text) >= 3
