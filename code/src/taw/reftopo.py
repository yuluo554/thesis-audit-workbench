# -*- coding: utf-8 -*-
"""REF-08 论证链矩阵与引用拓扑（plan/04 §十；FR-08，**0 外链硬断言**）。

流程：正文引用语境提取（REF-04 `extract_citation_context`）→ 论点支撑矩阵 →
pyvis 拓扑 HTML（`cdn_resources="in_line"`，断网可开）。

**0 外链纪律**（NFR-07 / plan/03 §五.3）：产物 HTML 不得含任何外部资源引用
（http(s):// 的 script/link/img/字体）。`assert_no_external_refs` 为硬断言，
测试与 CLI 收尾都调用它；pyvis 未装时用内置降级渲染器（同样 0 外链）。
"""

import html
import json
import re
import sys

# 外链检测：src/href 指向 http(s):// 或协议相对 // 的标签
_EXT_SRC = re.compile(r"""<(?:script|link|img|iframe|source|audio|video)\b[^>]*?"""
                      r"""(?:src|href)\s*=\s*(?:["'](?:\s*)?(?:https?:)?//)""",
                      re.I)
_EXT_ANY = re.compile(r"""(?:https?:)?//(?!\s*["'])[^\s"'>]*\.(?:js|css|woff2?|ttf|png|jpe?g|svg)""",
                      re.I)


def assert_no_external_refs(html_text):
    """0 外链硬断言：命中即抛 AssertionError（构建收尾必调）。"""
    m = _EXT_SRC.search(html_text)
    if m:
        raise AssertionError("拓扑 HTML 含外链资源引用：{}".format(m.group(0)[:120]))
    m2 = _EXT_ANY.search(html_text)
    if m2:
        raise AssertionError("拓扑 HTML 含外部资源路径：{}".format(m2.group(0)[:120]))
    return True


def build_matrix(cards, context):
    """论点支撑矩阵：{card_id: {cite_count, paras, contexts}}。"""
    matrix = []
    for c in cards:
        ctx = context.get(c["card_id"], [])
        matrix.append({
            "card_id": c["card_id"],
            "label": c["evidence"].get("label"),
            "title": c.get("title"),
            "year": c["source"].get("year"),
            "cite_count": len(ctx),
            "paras": sorted({x["para"] for x in ctx}),
            "contexts": [x["context"] for x in ctx][:5],
        })
    matrix.sort(key=lambda r: (-r["cite_count"], str(r["label"] or "")))
    return matrix


def _node_payload(cards, context, findings=None):
    findings = findings or []
    by_entry = {}
    for f in findings:
        eid = (f.get("evidence", {}).get("location") or {}).get("entry_id")
        if eid:
            by_entry.setdefault(eid, []).append(f.get("check_type"))
    nodes = []
    for c in cards:
        ctx = context.get(c["card_id"], [])
        nodes.append({
            "id": c["card_id"],
            "label": "[{}] {}".format(c["evidence"].get("label") or "?",
                                      (c.get("title") or "")[:24]),
            "title": c.get("title"),
            "year": c["source"].get("year"),
            "cite_count": len(ctx),
            "claims": sorted({x["context"][:60] for x in ctx if x.get("context")}),
            "audit": sorted(set(by_entry.get(c["card_id"], []))),
        })
    return nodes


def render_html(cards, context, findings=None, title="引用论证链拓扑"):
    """渲染 0 外链拓扑 HTML（优先 pyvis in_line，缺装时内置降级渲染器）。"""
    return render_nodes(_node_payload(cards, context, findings), title)


def render_nodes(nodes, title="引用论证链拓扑"):
    """由**预构造节点**渲染 0 外链 HTML（M4 FULL-05 综述可视化复用同一路径）。

    nodes = [{id, label, title, year, cite_count, claims, audit}]；
    与 render_html 共用 pyvis / 内置降级渲染器 + `sanitize_external` 消毒路径，
    产物同样过 `assert_no_external_refs` 硬断言（NFR-07：任何 HTML 产物 0 外链）。
    """
    try:
        raw = _render_pyvis(nodes, title)
    except (ImportError, OSError):
        # 冻结 exe：pyvis 模块可 import 但 templates/ 未随包时，Jinja2 抛
        # TemplateNotFound（OSError 子类），不是 ImportError——两都要降级。
        print("pyvis 不可用，改用内置渲染器", file=sys.stderr)
        raw = _render_builtin(nodes, title)
    return sanitize_external(raw)


# 外链标签移除：<link ...href="http(s)://..."> 与 <script src="http(s)://...">
_EXT_TAG = re.compile(
    r"""<(?:link|script)\b[^>]*?(?:href|src)\s*=\s*["']\s*(?:https?:)?//[^"']*["'][^>]*>""",
    re.I | re.S)


def sanitize_external(html_text):
    """剥离外部资源标签（pyvis `in_line` 仍会带 bootstrap CDN 引用——已知坑）。

    保留内联的 vis-network JS/CSS；移除的标签只是 pyvis 的 UI 外壳样式，
    不影响图形本体渲染。产物随后过 `assert_no_external_refs` 硬断言。
    """
    out = _EXT_TAG.sub("<!-- taw: external resource removed -->", html_text)
    assert_no_external_refs(out)
    return out


def _render_pyvis(nodes, title):
    from pyvis.network import Network  # 惰性导入（extras viz）

    net = Network(height="640px", width="100%", directed=False,
                  cdn_resources="in_line", notebook=False)
    for n in nodes:
        color = "#e57373" if n["audit"] else ("#81c784" if n["cite_count"] else "#bdbdbd")
        tip = "{}<br/>年份: {}<br/>被引用: {} 次<br/>审计: {}".format(
            html.escape(n["title"] or ""), html.escape(str(n["year"] or "")),
            n["cite_count"], ", ".join(n["audit"]) or "无")
        net.add_node(n["id"], label=n["label"], title=tip, color=color)
    # 边：共享同一引用段落的文献之间连边（论证链共现）
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            shared = set(a["claims"]) & set(b["claims"])
            if shared:
                net.add_edge(a["id"], b["id"], title="共现段落")
    return net.generate_html(notebook=False)


def _render_builtin(nodes, title):
    """零依赖降级渲染：纯内联 CSS/JS 的静态 HTML（0 外链）。"""
    data = json.dumps(nodes, ensure_ascii=False)
    rows = []
    for n in nodes:
        color = "#e57373" if n["audit"] else ("#81c784" if n["cite_count"] else "#bdbdbd")
        rows.append(
            '<tr><td style="border-left:6px solid {c}">{lab}</td><td>{t}</td>'
            '<td>{y}</td><td>{n}</td><td>{a}</td></tr>'.format(
                c=color, lab=html.escape(n["label"]), t=html.escape(n["title"] or ""),
                y=html.escape(str(n["year"] or "")), n=n["cite_count"],
                a=html.escape(", ".join(n["audit"]) or "无")))
    return (
        "<!DOCTYPE html>\n<html lang=\"zh\"><head><meta charset=\"utf-8\">"
        "<title>{title}</title><style>"
        "body{{font-family:sans-serif;margin:24px}}"
        "table{{border-collapse:collapse;width:100%}}"
        "th,td{{border:1px solid #ddd;padding:6px 10px;text-align:left}}"
        "</style></head><body>"
        "<h1>{title}</h1>"
        "<p>节点数 {n}；绿色=被正文引用，灰色=未被引用（幽灵），红色=有审计结论。</p>"
        "<table><thead><tr><th>文献</th><th>题名</th><th>年份</th>"
        "<th>被引次数</th><th>审计结论</th></tr></thead><tbody>{rows}</tbody></table>"
        "<script type=\"application/json\" id=\"taw-topology\">{data}</script>"
        "</body></html>\n"
    ).format(title=html.escape(title), n=len(nodes), rows="".join(rows), data=data)
