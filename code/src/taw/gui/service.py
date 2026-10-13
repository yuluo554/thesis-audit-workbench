# -*- coding: utf-8 -*-
"""GUI 服务层：把引擎 API 的产出摊平成界面可直接渲染的行/文本。

**铁律（plan/03 §一）**：CLI 是单一事实源，GUI 只消费既有引擎 API
（`taw.refaudit` / `taw.fullaudit` / `taw.reftopo` 等），不另起第二套行为、
不复刻任何判定逻辑。故本模块只做三件事：

1. **调用**编排函数（`audit_refs` / `audit_thesis`），参数与 CLI 一一对应；
2. **摊平**：把 report 的 findings 转成表格行（纯展示，不改判定）；
3. **导出**：报告 JSON / 拓扑 HTML 一律走引擎既有写盘函数（HTML 过 0 外链断言）。

本模块**不 import Qt**，因此没有 PySide6 也能跑，行为可直接单测。
"""

import json
from pathlib import Path

from taw.paths import find_data_dir_details

# 三级判定 → 界面标签（plan/04 §三：pass/fail/manual_confirm）
STATUS_LABELS = {
    "pass": "通过",
    "fail": "不符",
    "manual_confirm": "待人工确认",
}

# 条款核对状态（plan/04 §十 10.1）：pending 必须在界面上显式标注，绝不冒充标准原文
CLAUSE_LABELS = {
    "pending": "条款待核对",
    "verified": "条款已核对",
}

# 表格列（顺序即界面列序；测试按此断言）
COLUMNS = ("序号", "规则", "状态", "类型", "位置", "条款", "说明 / 建议")


def data_dir_status():
    """数据目录探测（与 CLI 同为 paths 五分支）→ (路径 str|None, 来源)。

    配置错误（显式/env 指向无效目录）返回 (None, "配置错误: ...")，不抛异常——
    界面要先把状态显示出来，而不是崩在启动路径上。
    """
    try:
        path, source = find_data_dir_details()
    except FileNotFoundError as exc:
        return None, "配置错误: {}".format(exc)
    return (None if path is None else str(path)), source


def status_label(status):
    return STATUS_LABELS.get(status, status or "?")


def clause_label(clause_status):
    """条款标记：pending → 「条款待核对」（NFR-04 在界面层的落地）。"""
    return CLAUSE_LABELS.get(clause_status or "pending", "条款待核对")


def _location_text(location):
    """位置字段摊平：条目编号 / 段落号 / 标记，按可得性拼接。"""
    if not location:
        return ""
    parts = []
    if location.get("label"):
        # 标记类 label 自带方括号（"[99]"），避免渲染成 "[[99]]"
        label = str(location["label"])
        parts.append("标记 {}".format(label if label.startswith("[") else "[{}]".format(label)))
    if location.get("ref_no") is not None:
        parts.append("编号 {}".format(location["ref_no"]))
    if location.get("entry_id"):
        parts.append(location["entry_id"])
    if location.get("para") is not None:
        parts.append("段 {}".format(location["para"]))
    if location.get("doc"):
        parts.append(str(location["doc"]))
    return " / ".join(parts)


def flatten_findings(report):
    """report → 表格行列表（每行 dict，键见 COLUMNS 的语义对应）。

    纯展示变换：不筛选、不排序、不改变任何 status。
    """
    rows = []
    for i, f in enumerate(report.get("findings", []), 1):
        ev = f.get("evidence") or {}
        rows.append({
            "index": i,
            "rule_id": f.get("rule_id"),
            "status": f.get("status"),
            "status_label": status_label(f.get("status")),
            "check_type": f.get("check_type") or "",
            "location": _location_text(ev.get("location")),
            "clause_status": f.get("clause_status"),
            "clause_label": clause_label(f.get("clause_status")),
            "detail": f.get("detail") or "",
            "suggestion": f.get("suggestion") or "",
            "confidence": f.get("confidence"),
            "basis": f.get("basis"),
            "raw": f,
        })
    return rows


def row_cells(row):
    """表格行的 7 列文本（COLUMNS 顺序）。"""
    explain = row["detail"] or row["suggestion"] or ""
    if row["detail"] and row["suggestion"]:
        explain = "{} → {}".format(row["detail"], row["suggestion"])
    return (
        str(row["index"]),
        row["rule_id"] or "",
        row["status_label"],
        row["check_type"],
        row["location"],
        row["clause_label"],
        explain,
    )


def summary_lines(report):
    """概览文本行（与 CLI 打印口径一致：总数控 + 三级判定计数 + 模块计数）。"""
    s = report.get("summary") or {}
    by_status = s.get("by_status") or {}
    lines = ["结论 {}：fail {} / manual_confirm {} / pass {}".format(
        s.get("total", 0), by_status.get("fail", 0),
        by_status.get("manual_confirm", 0), by_status.get("pass", 0))]
    for name in sorted(report.get("modules") or {}):
        info = report["modules"][name]
        if "skipped" in info:
            lines.append("  {:<22} 跳过（{}）".format(name, info["skipped"]))
        else:
            lines.append("  {:<22} findings {}".format(name, info.get("findings", 0)))
    for text in report.get("disclaimers") or []:
        lines.append("免责声明：{}".format(text))
    return lines


def finding_detail_text(row):
    """单条 finding 的详情（右侧详情面板）——完整证据链 JSON。"""
    return json.dumps(row["raw"], ensure_ascii=False, indent=2)


# ---- 引擎调用（参数与 CLI 子命令一一对应）----


def run_ref_audit(table_path, body_path=None, standard_year="2025", profile="default",
                  data_dir=None, include_topology=False, include_library=False):
    """文献线审计（`refaudit.audit_refs`）。

    返回 {"report":..., "topology_rows":..., "library_stats":...}；
    拓扑与文献库为可选动作（与 CLI 的 --topology/--library 同语义）。
    """
    from taw import refaudit

    if not table_path:
        raise ValueError("请选择文献表文件（txt/csv/bib/ris）")
    report = refaudit.audit_refs(
        table_path, body_path=body_path or None, data_dir=data_dir,
        standard_year=standard_year, profile=profile)
    out = {"report": report, "topology_rows": None, "library_stats": None}
    if include_topology and body_path:
        # 复用同一次审计的 REF-08 矩阵（不重复跑引擎）
        out["topology_rows"] = (report["modules"].get("REF-08-topology") or {}).get("matrix")
    if include_library:
        from taw import refparse, reflib
        _fmt, cards = refparse.parse_file(table_path)
        with reflib.Library(":memory:") as lib:
            lib.save(str(table_path), cards, report.get("health_score"))
            out["library_stats"] = lib.stats()
    return out


def run_full_audit(docx_path, standard_year="2025", profile="default",
                   data_dir=None, include_review=True):
    """全文线审计（`fullaudit.audit_thesis`）→ report dict。"""
    from taw import fullaudit

    if not docx_path:
        raise ValueError("请选择论文 docx 文件")
    return fullaudit.audit_thesis(
        docx_path, data_dir=data_dir, standard_year=standard_year,
        profile=profile, include_review=include_review)


def run_recommendations(body_path, table_path, top_k=5, data_dir=None):
    """句子级推荐（REF-07 展示面，`refaudit.recommend_for`）——只从库内选取。"""
    from taw import refaudit

    if not (body_path and table_path):
        raise ValueError("推荐需要同时给出文献表与正文文件")
    return refaudit.recommend_for(body_path, table_path, top_k=top_k, data_dir=data_dir)


# ---- 导出（一律复用引擎写盘函数；HTML 产物过 0 外链硬断言）----


def export_report(report, path):
    """报告 JSON 落盘（sort_keys、无时间戳——与 CLI --report 同一实现）。"""
    from taw import refaudit
    return str(refaudit.write_report(report, path))


def export_topology(table_path, body_path, out_path):
    """拓扑 HTML 落盘（0 外链，内部过 sanitize + assert）。"""
    from taw import refaudit
    return str(refaudit.write_topology(table_path, body_path, out_path))


def export_review_topology(data_dir, out_path):
    """综述聚类 HTML 落盘（FULL-05 可视化，同样 0 外链硬断言）。"""
    from taw import fullaudit, reftopo, reviewcl

    entries = fullaudit._load_review_entries(data_dir)
    if not entries:
        raise ValueError("缺库内综述语料（data/frozen/review/）")
    html_text = reviewcl.render_review_html(entries)
    reftopo.assert_no_external_refs(html_text)
    p = Path(str(out_path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_text, encoding="utf-8")
    return str(p)


def write_comment_report(docx_path, report, out_path=None):
    """把 findings 回写为 Word 批注（复用 REF-09 `reflib.write_comments`）。

    产物走 `docxutil.finalize_comments` 收口（固定时间戳），COM 通路只是外挂触发。
    """
    from taw import reflib

    findings = report.get("findings", [])
    if not findings:
        raise ValueError("无可回写 findings（先跑审计）")
    return str(reflib.write_comments(docx_path, findings, out_path=out_path))
