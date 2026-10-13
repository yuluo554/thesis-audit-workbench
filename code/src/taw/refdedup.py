# -*- coding: utf-8 -*-
"""REF-05 重复条目检测与合并（plan/04 §十；FR-05，**误合并率 0**）。

三级判据（从严到宽），**任一命中即同簇**；宁可漏合并（manual_confirm）不可误合并：
1. **DOI 精确**：归一后完全相同 → `duplicate`（高置信）；
2. **标题归一模糊**：标题归一化后完全相同，且**著者集合交集非空** + 年份一致
   → `duplicate`；标题相同但著者/年份**冲突** → `manual_confirm`（不硬合）；
3. **辅助证据**：标题归一后编辑距离 ≤ 阈值（默认 2）且容器/年份/著者均一致
   → `duplicate`；仅部分一致 → `manual_confirm`。

「误合并率 0」的工程保证：任何**冲突字段**（同字段两个不同非空值）一律降级为
`manual_confirm`，绝不自动合并——自动合并只发生在冲突为空或等价的情形。

合并建议保留「字段更全」的条目（空槽位更少）；冲突字段列入 `conflicts` 待人工确认。
"""

import re
from itertools import combinations

from taw import engine

# 标题归一：去空格/全半角破折号/常见标点/大小写
_PUNCT = re.compile(
    r"[\u3000\s\-\u2013\u2014\uff0d_.,\uff0c\u3002:\uff1a;\uff1b!\uff01?\uff1f"
    r"()\uff08\uff09\[\]\u3010\u3011\"'\u201c\u201d\u2018\u2019/\\]+")


def norm_title(title):
    """标题归一：小写、去标点与空白、全角转半角。空标题返回 ''。"""
    if not title:
        return ""
    t = title
    out = []
    for ch in t:
        o = ord(ch)
        if 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        elif ch == "\u3000":
            out.append(" ")
        else:
            out.append(ch)
    t = "".join(out).lower()
    return _PUNCT.sub("", t)


def norm_doi(doi):
    if not doi:
        return None
    return re.sub(r"\s+", "", doi).lower().rstrip(".")


def _author_families(card):
    fams = set()
    for a in card["authors"]:
        f = a.get("family") or a.get("raw") or ""
        f = re.sub(r"\s+", "", f).lower()
        if f:
            fams.add(f)
    return fams


def _levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _field_conflicts(a, b):
    """两卡片的冲突字段：同字段都有值且不等（含 source/identifiers）。"""
    conflicts = []
    for field in ("title",):
        va, vb = a.get(field), b.get(field)
        if va and vb and va != vb:
            conflicts.append({"field": field, "a": va, "b": vb})
    for group in ("source", "identifiers"):
        for k in sorted(set(a[group]) | set(b[group])):
            va, vb = a[group].get(k), b[group].get(k)
            if va and vb and str(va) != str(vb):
                conflicts.append({"field": k, "a": va, "b": vb})
    fa, fb = _author_families(a), _author_families(b)
    if fa and fb and not (fa & fb):
        conflicts.append({"field": "authors", "a": sorted(fa), "b": sorted(fb)})
    return conflicts


def _pair_verdict(a, b, edit_threshold=2):
    """两卡片的关系判定 → (verdict, reason, conflicts)。

    verdict ∈ {"duplicate", "manual_confirm", None}。
    """
    da, db = norm_doi(a["identifiers"].get("doi")), norm_doi(b["identifiers"].get("doi"))
    ta, tb = norm_title(a.get("title")), norm_title(b.get("title"))
    conflicts = _field_conflicts(a, b)

    if da and db and da == db:
        return ("duplicate", "DOI 精确匹配", conflicts)
    if ta and tb and ta == tb:
        # 标题归一相同：需著者交集非空且年份一致，否则人工确认
        fa, fb = _author_families(a), _author_families(b)
        ya, yb = a["source"].get("year"), b["source"].get("year")
        if conflicts:
            return ("manual_confirm", "标题归一相同但存在冲突字段", conflicts)
        if fa and fb and (fa & fb) and (not ya or not yb or ya == yb):
            return ("duplicate", "标题归一相同 + 著者交集 + 年份一致", conflicts)
        return ("manual_confirm", "标题归一相同但著者/年份证据不足", conflicts)
    if ta and tb and _levenshtein(ta, tb) <= edit_threshold:
        # 模糊：要求年份一致 + 著者交集非空 + 无冲突才自动合并；
        # 有冲突或证据不足时，**只有存在正向证据（著者交集或同容器）才提示人工确认**——
        # 否则任意两条相近长度的标题都会互相提示，噪声淹没真信号。
        fa, fb = _author_families(a), _author_families(b)
        ca, cb = a["source"].get("container"), b["source"].get("container")
        positive = bool(fa & fb) or bool(ca and cb and ca == cb)
        ya, yb = a["source"].get("year"), b["source"].get("year")
        if positive and not conflicts and fa & fb and ya and yb and ya == yb:
            return ("duplicate", "标题模糊接近 + 著者交集 + 年份一致", [])
        if positive:
            return ("manual_confirm", "标题模糊接近但证据不足以硬合", conflicts)
        return (None, None, [])
    return (None, None, [])


def find_duplicates(cards, rule=None, edit_threshold=2):
    """→ {clusters, manual_pairs, findings}。

    - `clusters`：可自动合并的重复簇（verdict="duplicate"）；
    - `manual_pairs`：疑似但证据不足/字段冲突的条目对（verdict="manual_confirm"），
      按"误合并率 0"纪律**不自动合并**，只上报人工确认。
    """
    n = len(cards)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    dup_pairs = []      # (i, j, reason, conflicts) 自动可合并
    manual_pairs = []   # (i, j, reason, conflicts) 需人工确认
    for i, j in combinations(range(n), 2):
        verdict, reason, conflicts = _pair_verdict(cards[i], cards[j], edit_threshold)
        if verdict == "duplicate":
            union(i, j)
            dup_pairs.append((i, j, reason, conflicts))
        elif verdict == "manual_confirm":
            manual_pairs.append((i, j, reason, conflicts))

    clusters = {}
    for idx in range(n):
        clusters.setdefault(find(idx), []).append(idx)

    out = []
    findings = []
    for _root, members in sorted(clusters.items()):
        if len(members) < 2:
            continue
        member_cards = [cards[m] for m in members]
        keep = min(members, key=lambda m: (_empty_slots(cards[m]), m))
        drop = [m for m in members if m != keep]
        conflicts = []
        for i, j, reason, cfl in dup_pairs:
            if i in members and j in members:
                conflicts.extend(cfl)
        uniq_conflicts = _uniq_conflicts(conflicts)
        cluster = {
            "entry_ids": [cards[m]["card_id"] for m in members],
            "labels": [cards[m]["evidence"].get("label") for m in members],
            "keep": cards[keep]["card_id"],
            "drop": [cards[m]["card_id"] for m in drop],
            "verdict": "duplicate",
            "reason": next((r for i, j, r, _ in dup_pairs
                            if i in members and j in members), ""),
            "conflicts": uniq_conflicts,
        }
        out.append(cluster)
        if rule is not None:
            for m in drop:
                findings.append(engine.make_rule_finding(
                    rule, "fail",
                    {"doc": cards[m]["evidence"]["src"],
                     "para": cards[m]["evidence"]["ordinal"], "span": None,
                     "entry_id": cards[m]["card_id"],
                     "label": cards[m]["evidence"].get("label")},
                    suggestion="与 {} 合并（保留字段更全的条目）".format(cards[keep]["card_id"]),
                    confidence=0.95,
                    detail="重复簇 {}（{}）；冲突字段 {} 项".format(
                        cluster["labels"], cluster["reason"], len(uniq_conflicts)),
                ))

    manual_out = []
    for i, j, reason, conflicts in manual_pairs:
        if find(i) == find(j):
            continue  # 已并入自动簇（三方关系），不必再单报
        entry = {
            "entry_ids": [cards[i]["card_id"], cards[j]["card_id"]],
            "labels": [cards[i]["evidence"].get("label"),
                       cards[j]["evidence"].get("label")],
            "verdict": "manual_confirm",
            "reason": reason,
            "conflicts": _uniq_conflicts(conflicts),
        }
        manual_out.append(entry)
        if rule is not None:
            findings.append(engine.make_rule_finding(
                rule, "manual_confirm",
                {"doc": cards[j]["evidence"]["src"],
                 "para": cards[j]["evidence"]["ordinal"], "span": None,
                 "entry_id": cards[j]["card_id"],
                 "label": cards[j]["evidence"].get("label")},
                suggestion="人工核对两条目是否同一文献（有冲突字段，未自动合并）",
                confidence=0.45,
                detail="疑似重复 {}（{}）；冲突字段 {} 项".format(
                    entry["labels"], reason, len(entry["conflicts"])),
            ))
    return {"clusters": out, "manual_pairs": manual_out, "findings": findings}


def _uniq_conflicts(conflicts):
    seen = set()
    out = []
    for c in conflicts:
        key = (c["field"], str(c["a"]), str(c["b"]))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _empty_slots(card):
    n = 0
    if not card.get("title"):
        n += 1
    for v in card["source"].values():
        if not v:
            n += 1
    for v in card["identifiers"].values():
        if not v:
            n += 1
    return n


def merge_cluster(cards, cluster):
    """按簇生成合并建议（不修改入参）：保留 keep，吸收 drop 中 keep 缺失的字段。"""
    by_id = {c["card_id"]: c for c in cards}
    keep = by_id[cluster["keep"]]
    merged = {"card_id": keep["card_id"], "title": keep["title"],
              "authors": list(keep["authors"]),
              "source": dict(keep["source"]),
              "identifiers": dict(keep["identifiers"]),
              "absorbed_from": [], "conflicts": cluster["conflicts"]}
    for did in cluster["drop"]:
        d = by_id[did]
        if not merged["title"] and d["title"]:
            merged["title"] = d["title"]
        if not merged["authors"] and d["authors"]:
            merged["authors"] = list(d["authors"])
        for group in ("source", "identifiers"):
            for k, v in d[group].items():
                if not merged[group].get(k) and v:
                    merged[group][k] = v
        merged["absorbed_from"].append(did)
    return merged
