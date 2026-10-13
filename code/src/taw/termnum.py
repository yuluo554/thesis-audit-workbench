# -*- coding: utf-8 -*-
r"""FULL-03 术语与数字用法一致性（plan/01 §12、plan/02 FR-12）。

两件能力，共用 check_type `term_consistency`：

1. **术语一致性**：读术语表（`data/knowledge/terminology.json`，标准写法 ↔ 变体
   清单）→ 全文扫描，**只报变体字面出现处**（canonical 出现不报，误报 0 优先）；
2. **数字用法一致性**（与 GB/T 15835-2011 互补）：同一整数值**同时**以带千分位与
   不带千分位两种形态出现时判不一致；只在同值两形态并存时报，单形态不报。

两者都输出**变体分布热区**（按段落与按章节统计），供报告展示。

判定纪律（误报 0 优先）：
- 术语只扫变体（canonical 之外的写法）；句读/上下文不参与，纯字面包含；
- 数字只在"同值两形态并存"时报，且**跳过参考文献表条目**（形如 `[1] 张合成…`）与
  标题段（章节号如 "1.1" 与年份等不是千分位素材）；
- 一个变体在段内出现多次仍只产一条 finding（按段落聚合），避免重复计数。
"""

import re

from taw import engine

# 千分位分隔符（半角逗号 / 全角逗号）
_THOUSANDS = ",\uFF0C"
# 节号/标题前缀（如 "1.1 研究背景"）与参考文献条目标签（如 "[1] 张合成…"）
_REF_LABEL = re.compile(r"^\s*\[\s*\d{1,3}\s*\]")
_HEADING_NO = re.compile(r"^\s*\d{1,2}(?:\.\d{1,2})*[\s\u3000]")
_SEP_NUM = re.compile(r"\d{1,3}(?:[%s]\d{3})+" % _THOUSANDS)
_PLAIN_NUM = re.compile(r"\d{4,}")


def _norm_ws(s):
    return re.sub(r"\s+", "", s or "")


def load_terminology(data_dir):
    """读术语表（无出处/无依据不生效由数据守门约束；此处只做形状过滤）。"""
    import json
    from pathlib import Path
    p = Path(str(data_dir)) / "knowledge" / "terminology.json"
    if not p.is_file():
        return {"terms": [], "number_usage": None}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"terms": [t for t in data.get("terms", []) if t.get("canonical")
                      and t.get("variants")],
            "number_usage": data.get("number_usage")}


def _is_exempt(text, style):
    """豁免上下文：标题段（章节号）、参考文献条目、题注。"""
    if style and (style.startswith("Heading") or style in ("Title", "Caption")):
        return True
    if _REF_LABEL.match(text):
        return True
    return False


# ---- 术语扫描 ----


def scan_terms(style_tree, terms):
    """全文扫术语变体 → [{term_id, canonical, variant, para, kind}]（段内去重）。"""
    hits = []
    for t in terms:
        canonical = t["canonical"]
        for variant in t["variants"]:
            if _norm_ws(variant) == _norm_ws(canonical):
                continue        # 空白归一后同形：交由数字/空格变体逻辑处理，避免双报
            for p in style_tree:
                if _is_exempt(p["text"], p["style"]):
                    continue
                if variant in p["text"]:
                    hits.append({"term_id": t.get("term_id"), "canonical": canonical,
                                 "variant": variant, "para": p["i"],
                                 "kind": t.get("kind")})
    return hits


def scan_stray_space_terms(style_tree, terms):
    """空白型变体（归一后与 canonical 同形：多余空格或缺失空格，如 '机器 学习'/'GB/T7714'）。

    判据：按 canonical 的字符序列（字符间允许任意空白）在正文匹配，命中段
    **字面不等于** canonical 即判空白写法不一致（双向覆盖：多空格 T2 与缺空格 T4）。
    """
    hits = []
    for t in terms:
        canonical = t["canonical"]
        variants = [v for v in t["variants"]
                    if _norm_ws(v) == _norm_ws(canonical)]
        if not variants:
            continue
        pat = re.compile(r"\s*".join(re.escape(c) for c in canonical if not c.isspace()))
        for p in style_tree:
            if _is_exempt(p["text"], p["style"]):
                continue
            for m in pat.finditer(p["text"]):
                seg = m.group(0)
                if seg != canonical:
                    hits.append({"term_id": t.get("term_id"), "canonical": canonical,
                                 "variant": seg, "para": p["i"],
                                 "kind": t.get("kind", "stray_space_in_term")})
    return hits


# ---- 数字用法扫描 ----


def scan_number_usage(style_tree, number_usage):
    """同一整数值两形态并存 → 不一致；返回 [{value, forms, paras}]。

    forms: {"sep": [paras...], "plain": [paras...]}；仅当两形态都非空才判。
    """
    if not number_usage:
        return []
    groups = {}
    for p in style_tree:
        text = p["text"]
        if _is_exempt(text, p["style"]):
            continue
        for m in _SEP_NUM.finditer(text):
            val = m.group(0)
            num = re.sub(r"[%s]" % _THOUSANDS, "", val)
            groups.setdefault(num, {"sep": [], "plain": []})
            groups[num]["sep"].append(p["i"])
        for m in _PLAIN_NUM.finditer(text):
            val = m.group(0)
            groups.setdefault(val, {"sep": [], "plain": []})
            groups[val]["plain"].append(p["i"])
    out = []
    for num in sorted(groups):
        forms = groups[num]
        if forms["sep"] and forms["plain"]:
            out.append({"value": num,
                        "forms": {"sep": sorted(set(forms["sep"])),
                                  "plain": sorted(set(forms["plain"]))}})
    return out


# ---- 热区 ----


def heat_zones(hits, style_tree):
    """变体分布热区：按段落与按章节统计命中数。"""
    by_para = {}
    for h in hits:
        by_para[h["para"]] = by_para.get(h["para"], 0) + 1
    # 章节归属：段落之前最近的 Heading 1
    chapter_of = {}
    current = None
    for p in sorted(style_tree, key=lambda x: x["i"]):
        if p["style"] == "Heading 1" and p["text"].strip():
            current = p["text"].strip()
        chapter_of[p["i"]] = current
    by_chapter = {}
    for para, n in by_para.items():
        ch = chapter_of.get(para) or "(篇首)"
        by_chapter[ch] = by_chapter.get(ch, 0) + n
    return {"by_para": dict(sorted(by_para.items())),
            "by_chapter": dict(sorted(by_chapter.items(), key=lambda kv: -kv[1]))}


# ---- 主入口 ----


def check_terms(parsed, ruleset, data_dir=None, doc_name="thesis", terminology=None):
    """FULL-03 主入口 → {findings, hits, number_issues, heat, disclaimers, summary}。"""
    rules = {}
    if ruleset:
        for r in ruleset["rules"]:
            if r.get("check_type") == "term_consistency":
                rules.setdefault(r["rule_id"], r)
    rule = None
    for r in rules.values():
        if engine.is_active(r):
            rule = r
            break

    terminology = terminology or load_terminology(data_dir)
    style_tree = parsed.get("style_tree", [])
    findings = []
    if rule is not None:
        hits = scan_terms(style_tree, terminology["terms"])
        hits += scan_stray_space_terms(style_tree, terminology["terms"])
        for h in hits:
            findings.append(engine.make_rule_finding(
                rule, "fail",
                {"doc": doc_name, "para": h["para"], "span": None,
                 "label": h["variant"], "field": "term"},
                suggestion="统一为术语表标准写法：{}".format(h["canonical"]),
                confidence=0.85,
                detail="术语 '{}' 出现变体写法 '{}'（标准写法：{}）".format(
                    h["canonical"], h["variant"], h["canonical"]),
            ))
        num_issues = scan_number_usage(style_tree, terminology["number_usage"])
        for issue in num_issues:
            paras = sorted(set(issue["forms"]["sep"] + issue["forms"]["plain"]))
            for para in paras:
                other = (issue["forms"]["plain"] if para in issue["forms"]["sep"]
                         else issue["forms"]["sep"])
                findings.append(engine.make_rule_finding(
                    rule, "fail",
                    {"doc": doc_name, "para": para, "span": None,
                     "label": issue["value"], "field": "number_form"},
                    suggestion="同一量值统一数字写法（千分位一致）",
                    confidence=0.85,
                    detail="数值 {} 写法不一致：本处与段落 {} 的千分位用法不同".format(
                        issue["value"], sorted(set(other))),
                ))
    else:
        hits, num_issues = [], []

    heat = heat_zones(hits + [{"para": p} for p in
                              [x for i in num_issues for x in
                               i["forms"]["sep"] + i["forms"]["plain"]]], style_tree)
    return {"findings": findings, "hits": hits, "number_issues": num_issues,
            "heat": heat, "disclaimers": list(engine.DISCLAIMERS),
            "summary": engine.summarize(findings)}
