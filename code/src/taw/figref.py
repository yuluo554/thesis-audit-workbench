# -*- coding: utf-8 -*-
"""FULL-01 图表/公式/交叉引用审计与编号重排（plan/01 §10、plan/04 §四/§五）。

消费 `taw.thesisparse` 的对象/标记/悬空/幽灵产出，复用 REF-04 的对账模式：

1. **悬空标记（dangling_reference）**：正文提及的编号解析不到任何对象——
   两类载体，手打编号（`表 9-1`）与 Word REF 域（域指向的书签不存在）；
2. **幽灵对象（ghost_object）**：对象存在但全文零提及（题注段自身编号**不计**
   为提及；公式段自身即提及——与 thesisparse 一次锁定的口径一致）；
3. **编号断档（xref_order）**：同章同类对象编号须连续无断档。

**编号重排内核复用**（plan/04 §五）：`taw.renumber` 的 `NumberedItem`/`MarkerRef`
结构通用——本模块把对象与标记映射到同一内核，任意插入/删除位置矩阵回归 100%
（与 REF-07 文献编号共用内核，各一套真值）。

判定纪律（误报 0 优先）：悬空/幽灵直接取解析器的确定性产出；断档只在**同类
同章**编号上判，不跨章比较（章间编号本就各自重新起编）。
"""

import re

from taw import engine, renumber

KIND_ZH = {"figure": "图", "table": "表", "equation": "式"}

_LABEL_NO = re.compile(r"^(?:图|表|式\()\s*(\d{1,2})[-\uFF0D\u2014\u2013]\s*(\d{1,2})\s*\)?$")


def _loc(doc_name, para, label, extra=None):
    loc = {"doc": doc_name, "para": para, "span": None, "label": label}
    if extra:
        loc.update(extra)
    return loc


def audit_xref(parsed, ruleset, doc_name="thesis"):
    """FULL-01 主入口 → {findings, disclaimers, summary, objects, markers}。

    三类结论与 ruleset 的 check_type 一一对应（dangling_reference / ghost_object /
    xref_order），仅 `activation=active` 的规则运行。
    """
    rules = {}
    if ruleset:
        for r in ruleset["rules"]:
            rules.setdefault(r.get("check_type"), r)

    def _rule(ct):
        r = rules.get(ct)
        if r is None or not engine.is_active(r):
            return None
        return r

    findings = []

    # 1. 悬空标记
    r_dang = _rule("dangling_reference")
    if r_dang is not None:
        for d in parsed.get("dangling", []):
            mode = "REF 域" if d.get("kind") == "ref_field" else "手打编号"
            detail = "正文{}提及 '{}'，全文不存在该对象".format(
                mode, d.get("raw") or d["label"])
            if d.get("kind") == "ref_field" and d.get("target_bookmark"):
                detail = "REF 域指向的书签 {} 在文档中不存在（显示为 '{}'）".format(
                    d["target_bookmark"], d.get("raw") or d["label"])
            findings.append(engine.make_rule_finding(
                r_dang, "fail",
                _loc(doc_name, d.get("para_index"), d["label"], {"mode": d.get("kind")}),
                suggestion="补入对象或修正编号/书签",
                confidence=0.95, detail=detail,
            ))

    # 2. 幽灵对象
    r_ghost = _rule("ghost_object")
    if r_ghost is not None:
        for g in parsed.get("ghosts", []):
            findings.append(engine.make_rule_finding(
                r_ghost, "fail",
                _loc(doc_name, g.get("caption_para"), g["label"], {"kind": g["kind"]}),
                suggestion="在正文相应处引用该对象，或删除该对象",
                confidence=0.9,
                detail="对象 '{}' 存在但全文无任何提及".format(g["label"]),
            ))

    # 3. 同类同章编号断档
    r_order = _rule("xref_order")
    if r_order is not None:
        for gap in number_gaps(parsed.get("objects", [])):
            findings.append(engine.make_rule_finding(
                r_order, "fail",
                _loc(doc_name, gap["caption_para"], gap["label"], {"kind": gap["kind"]}),
                suggestion="核对编号连续性（renumber 内核可整体重排）",
                confidence=0.85,
                detail="{} 在'第{}章'的编号断档：缺 {}".format(
                    KIND_ZH.get(gap["kind"], gap["kind"]), gap["chapter"], gap["missing"]),
            ))

    return {"findings": findings, "disclaimers": list(engine.DISCLAIMERS),
            "summary": engine.summarize(findings),
            "objects": parsed.get("objects", []),
            "markers": parsed.get("markers", [])}


# ---- 编号连续性 ----


def parse_label_no(label):
    """'图3-1' / '表4-2' / '式(3-1)' → (chapter, number)；解析不出 → None。"""
    if not label:
        return None
    m = _LABEL_NO.match(label.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def number_gaps(objects):
    """同章同类对象的编号断档：→ [{kind, chapter, missing, label, caption_para}]。

    只在**同章同类**内部比较（章间各自重新起编）；某组编号非从 1 起或有缺号即报。
    """
    groups = {}
    for o in objects:
        pn = parse_label_no(o.get("label"))
        if pn is None:
            continue
        chapter, num = pn
        groups.setdefault((o["kind"], chapter), []).append((num, o))
    out = []
    for (kind, chapter), items in sorted(groups.items()):
        nums = sorted(n for n, _o in items)
        hi = max(nums)
        missing = [n for n in range(1, hi + 1) if n not in nums]
        if missing:
            sample = next(o for n, o in items if n == nums[0])
            out.append({"kind": kind, "chapter": chapter, "missing": missing,
                        "label": sample.get("label"),
                        "caption_para": sample.get("caption_para")})
    return out


# ---- 编号重排内核复用（任意插入/删除矩阵）----


def object_items(parsed):
    """解析结果 → NumberedItem 序列（item_id=对象标签，markers=该对象的正文标记）。

    marker_id 全局唯一（`mk-<obj_idx>-<n>`）——同一 marker 只能归属一个 item，
    否则 renumber 内核会判"标记被多个条目占用"。
    """
    objects = parsed.get("objects", [])
    by_label = {}
    for mk in parsed.get("markers", []):
        by_label.setdefault(mk["label"], []).append(mk)
    items = []
    for oi, o in enumerate(objects):
        mks = by_label.get(o["label"], [])
        markers = [{"marker_id": "mk-{}-{}".format(oi, i), "para": m["para_index"]}
                   for i, m in enumerate(mks)]
        items.append({"item_id": o["label"], "markers": markers})
    return items


def renumber_objects(parsed, edits):
    """对对象编号执行重排 → RenumberPlan（复用 renumber 内核）。"""
    return renumber.renumber(object_items(parsed), edits)


def object_edit_matrix(n_items, max_edits=2):
    """对象编号的插入/删除矩阵（与 REF-07 同一内核、同一位置覆盖）。"""
    from taw import refrec
    return refrec.edit_matrix(n_items, max_edits=max_edits)


def object_renumber_bench(parsed=None, n_items=6):
    """任意插入/删除矩阵回归：全部用例过 verify_plan 即 100%。

    parsed 给定且对象数 ≥2 时用真实对象编号；否则用合成占位（矩阵形状一致）。
    """
    if parsed is not None and len(parsed.get("objects", [])) >= 2:
        base_ids = [it["item_id"] for it in object_items(parsed)]
    else:
        base_ids = ["obj{}".format(i + 1) for i in range(n_items)]
    items = [{"item_id": b, "markers": [{"marker_id": "m-" + b}]} for b in base_ids]
    _ids, cases = object_edit_matrix(len(base_ids))
    passed = 0
    failed = []
    for edits, desc in cases:
        plan = renumber.renumber(items, edits)
        if renumber.verify_plan(plan):
            passed += 1
        else:
            failed.append({"case": desc, "plan": plan["new_order"]})
    total = len(cases)
    return {"cases": total, "passed": passed,
            "consistency": round(passed / total, 4) if total else 1.0,
            "failed": failed[:5],
            "gate": {"consistency_100": passed == total}}
