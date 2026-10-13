# -*- coding: utf-8 -*-
"""FULL-05 综述辅助（plan/01 §14、plan/02 FR-14）。

三件能力：
1. **TF-IDF 主题聚类**：库内文献按标题/关键词做 TF-IDF 向量化，余弦相似度
   阈值聚类（纯本地、确定性；不引第三方 ML 依赖）；
2. **年代时间线**：逐主题的年代分布（复用 reftopo 的可视化渲染路径）；
3. **规则可判研究空白提示**：主题内最近年份 ≤ now_year-3 → "近 3 年无新增"
   （规则明确、可复核，非 LLM 推断）。

聚类阈值口径：余弦相似度 ≥ `THRESHOLD`（默认 0.30）判同簇——阈值由
`data/frozen/review/review_truth.json` 的预分组在 `fullbench` 里实测校准
（误报 0 优先：分错簇记为不达标）。

确定性：词项排序、簇内排序、簇间排序全部显式（不依赖 set 迭代序）。
"""

import math
import re

from taw import engine

# 中英混排分词（与 refrec 同口径：西文按词 + CJK 逐字 bigram）
_CJK = r"\u4e00-\u9fff"
_TOKEN_EN = re.compile(r"[A-Za-z][A-Za-z\-]*|\d+(?:\.\d+)?")
_TOKEN_CJK = re.compile("[{}]+".format(_CJK))

THRESHOLD = 0.30          # 余弦相似度聚类阈值（校准见模块 docstring）


def tokenize(text):
    if not text:
        return []
    out = [t.lower() for t in _TOKEN_EN.findall(text)]
    for run in _TOKEN_CJK.findall(text):
        out.extend(list(run))
        out.extend(run[i:i + 2] for i in range(len(run) - 1))
    return out


def _entry_text(entry):
    parts = [entry.get("title") or "", entry.get("venue") or ""]
    parts.extend(entry.get("keywords") or [])
    parts.extend(entry.get("authors") or [])
    return " ".join(p for p in parts if p)


def tfidf_vectors(entries):
    """库内文献 → [{entry_id, vector{term: weight}, norm}]（TF-IDF，L2 归一）。"""
    docs = [(e["entry_id"], tokenize(_entry_text(e))) for e in entries]
    n = len(docs)
    df = {}
    for _did, toks in docs:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    vectors = []
    for did, toks in docs:
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        vec = {}
        for t, f in tf.items():
            idf = math.log((n + 1.0) / (df.get(t, 0) + 1.0)) + 1.0
            vec[t] = (f / len(toks)) * idf if toks else 0.0
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({"entry_id": did, "vector": vec, "norm": norm})
    return vectors


def cosine(a, b):
    """两个 {term: weight} 向量的余弦相似度（sparse dot / (|a||b|)）。"""
    va, vb = a["vector"], b["vector"]
    # 小字典直接对短边遍历
    if len(va) > len(vb):
        va, vb = vb, va
    dot = 0.0
    for t, w in va.items():
        if t in vb:
            dot += w * vb[t]
    return dot / (a["norm"] * b["norm"]) if a["norm"] and b["norm"] else 0.0


def cluster(entries, threshold=THRESHOLD):
    """余弦阈值聚类（single-linkage 贪心，确定性）→ [{cluster_id, entry_ids}]。"""
    vectors = tfidf_vectors(entries)
    order = sorted(vectors, key=lambda v: v["entry_id"])
    assigned = {}
    clusters = []
    for i, v in enumerate(order):
        placed = False
        for cl in clusters:
            if any(cosine(v, order[j]) >= threshold for j in cl):
                cl.append(i)
                placed = True
                break
        if not placed:
            clusters.append([i])
    for ci, cl in enumerate(clusters):
        for j in cl:
            assigned[order[j]["entry_id"]] = "c{}".format(ci)
    out = []
    for ci, cl in enumerate(clusters):
        ids = sorted(order[j]["entry_id"] for j in cl)
        out.append({"cluster_id": "c{}".format(ci), "entry_ids": ids})
    out.sort(key=lambda c: (-len(c["entry_ids"]), c["cluster_id"]))
    return out


def cluster_purity(clusters, by_entry, truth_groups):
    """聚类对预分组的一致性（簇纯度）：每簇取其多数真值组，占比加权平均。

    by_entry: {entry_id: {group}}；truth_groups: {group: [entry_ids]}。
    返回 {purity, clusters: [{cluster_id, size, majority, purity}]}。
    """
    group_of = {}
    for g, ids in truth_groups.items():
        for i in ids:
            group_of[i] = g
    details = []
    total = 0
    correct = 0
    for cl in clusters:
        sizes = {}
        for i in cl["entry_ids"]:
            g = group_of.get(i)
            if g is None:
                continue
            sizes[g] = sizes.get(g, 0) + 1
        if not sizes:
            continue
        majority = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        size = len(cl["entry_ids"])
        total += size
        correct += majority[1]
        details.append({"cluster_id": cl["cluster_id"], "size": size,
                        "majority": majority[0], "purity": round(majority[1] / size, 4)})
    return {"purity": round(correct / total, 4) if total else 0.0,
            "clusters": details}


def timeline(entries):
    """年代时间线：{group 或 overall → {year: count}}。"""
    out = {}
    for e in entries:
        g = e.get("group") or "(unspecified)"
        out.setdefault(g, {})
        y = str(e.get("year"))
        out[g][y] = out[g].get(y, 0) + 1
    return {g: dict(sorted(years.items())) for g, years in sorted(out.items())}


def research_gaps(entries, now_year, recent_years=3):
    """规则可判研究空白：某主题内最近年份 ≤ now_year-recent_years+1 判无新增。

    返回 [{group, latest_year, reason}]（按 group 排序，确定性）。
    """
    groups = {}
    for e in entries:
        g = e.get("group") or "(unspecified)"
        groups.setdefault(g, []).append(e.get("year") or 0)
    cutoff = now_year - recent_years + 1
    out = []
    for g, years in sorted(groups.items()):
        latest = max(years) if years else 0
        if latest and latest < cutoff:
            out.append({"group": g, "latest_year": latest,
                        "reason": "主题'{}'库内最近年份 {}，近 {} 年（{} 起）无新增".format(
                            g, latest, recent_years, cutoff)})
    return out


# ---- 主入口 ----


def build_review(entries, now_year=None, threshold=THRESHOLD):
    """FULL-05 主入口 → {clusters, purity, timeline, gaps, disclaimers}。"""
    entries = list(entries)
    clusters = cluster(entries, threshold=threshold)
    truth_groups = {}
    for e in entries:
        if e.get("group"):
            truth_groups.setdefault(e["group"], []).append(e["entry_id"])
    purity = cluster_purity(clusters, None, truth_groups)
    years = [e["year"] for e in entries if e.get("year")]
    if now_year is None:
        now_year = max(years) if years else 0
    return {"clusters": clusters, "cluster_count": len(clusters),
            "purity": purity,
            "timeline": timeline(entries),
            "research_gaps": research_gaps(entries, now_year),
            "now_year": now_year,
            "disclaimers": list(engine.DISCLAIMERS)}


# ---- 综述可视化（复用 reftopo 的 0 外链渲染路径，NFR-07）----


def to_nodes(entries, result=None, now_year=None, threshold=THRESHOLD):
    """综述聚类 → reftopo 节点结构（每簇一个节点；研究空白簇标红）。"""
    entries = list(entries)
    result = result or build_review(entries, now_year=now_year, threshold=threshold)
    gap_groups = {g["group"] for g in result["research_gaps"]}
    by_id = {e["entry_id"]: e for e in entries}
    nodes = []
    for cl in result["clusters"]:
        members = [by_id[i] for i in cl["entry_ids"] if i in by_id]
        years = [m.get("year") for m in members if m.get("year")]
        groups = sorted({m.get("group") for m in members if m.get("group")})
        topic = groups[0] if len(groups) == 1 else "/".join(groups)
        nodes.append({
            "id": cl["cluster_id"],
            "label": "{}（{}）".format(topic, len(members)),
            "title": "；".join(m.get("title") or "" for m in members[:3]),
            "year": "{}–{}".format(min(years), max(years)) if years else "",
            "cite_count": len(members),
            "claims": [m.get("title") or "" for m in members],
            "audit": ["研究空白"] if topic in gap_groups else [],
        })
    return nodes


def render_review_html(entries, result=None, now_year=None, title="综述主题聚类与年代分布"):
    """渲染综述聚类 HTML（**0 外链硬断言**：复用 reftopo.render_nodes 消毒路径）。"""
    from taw import reftopo
    nodes = to_nodes(entries, result=result, now_year=now_year)
    html_text = reftopo.render_nodes(nodes, title)
    return html_text
