# -*- coding: utf-8 -*-
"""GUI 服务层测试（**不依赖 PySide6**——service 模块刻意不 import Qt）。

守门对象（plan/03 §一「CLI 是单一事实源，GUI 只消费引擎 API」）：
- service 的编排调用与 CLI 完全同参同源，产出与直接调引擎**逐字段一致**；
- 摊平只做展示变换：行数 == findings 数、status 不被改写、pending 条款显式标注；
- 导出复用引擎写盘函数：报告 JSON 与 CLI 的 `--report` 位级一致，HTML 过 0 外链断言。

service 是纯 Python，故本文件在两个解释器上都跑（不 skip）。
"""

import json
from pathlib import Path

import pytest

from taw import refaudit
from taw.gui import service

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
AUDIT = DATA / "frozen" / "audit"
THESIS = DATA / "frozen" / "thesis"


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("GUI 服务层测试需要 docx extras（CI/README 已装；缺装=环境配置错误）：{}".format(exc))


# ---- 摊平只做展示变换 ----


def test_flatten_matches_engine_findings_one_to_one():
    """行数 == findings 数，且 status/rule_id 原样透传（不改判定）。"""
    report = refaudit.audit_refs(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"), data_dir=str(DATA))
    rows = service.flatten_findings(report)
    assert len(rows) == len(report["findings"]) == 6
    for row, finding in zip(rows, report["findings"]):
        assert row["rule_id"] == finding["rule_id"]
        assert row["status"] == finding["status"]
        assert row["raw"] is finding
    assert [r["status_label"] for r in rows] == ["不符", "待人工确认", "不符", "不符", "不符", "不符"]


def test_pending_clause_is_labelled_not_hidden():
    """条款 pending 必须在界面显式标注「条款待核对」（NFR-04 落到展示层）。"""
    report = refaudit.audit_refs(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"), data_dir=str(DATA))
    rows = service.flatten_findings(report)
    assert all(r["clause_status"] == "pending" for r in rows)
    assert all(r["clause_label"] == "条款待核对" for r in rows)
    assert service.clause_label(None) == "条款待核对"  # 缺字段也按待核对处理
    assert service.clause_label("verified") == "条款已核对"


def test_row_cells_shape_matches_columns():
    report = refaudit.audit_refs(
        str(AUDIT / "refs_table.txt"), data_dir=str(DATA))
    rows = service.flatten_findings(report)
    assert len(rows) >= 1
    for row in rows:
        cells = service.row_cells(row)
        assert len(cells) == len(service.COLUMNS) == 7
        assert cells[5] == row["clause_label"]  # 第 6 列固定为条款标记
    assert service.COLUMNS[-1] == "说明 / 建议"


def test_summary_lines_mirror_cli_counts():
    report = refaudit.audit_refs(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"), data_dir=str(DATA))
    text = "\n".join(service.summary_lines(report))
    s = report["summary"]
    assert "结论 {}：fail {} / manual_confirm {} / pass {}".format(
        s["total"], s["by_status"].get("fail", 0),
        s["by_status"].get("manual_confirm", 0), s["by_status"].get("pass", 0)) in text
    assert "REF-04-citation" in text
    assert "免责声明" in text


def test_data_dir_status_never_raises_on_bad_explicit(monkeypatch, tmp_path):
    """配置错误不抛到界面：返回 (None, 配置错误...) 由界面展示。"""
    monkeypatch.setenv("TAW_DATA_DIR", str(tmp_path / "nope"))
    path, source = service.data_dir_status()
    assert path is None
    assert source.startswith("配置错误")


# ---- 编排调用与 CLI 同源同参 ----


def test_run_ref_audit_equals_engine_direct_call():
    """service 的文献线产出与直接调 refaudit 完全一致（同一实现，非第二套行为）。"""
    expected = refaudit.audit_refs(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"),
        data_dir=str(DATA), standard_year="2025", profile="default")
    got = service.run_ref_audit(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"),
        data_dir=str(DATA))["report"]
    assert json.dumps(got, ensure_ascii=False, sort_keys=True) == \
        json.dumps(expected, ensure_ascii=False, sort_keys=True)


def test_run_ref_audit_requires_table():
    with pytest.raises(ValueError):
        service.run_ref_audit(None, data_dir=str(DATA))


def test_run_ref_audit_topology_rows_and_library():
    out = service.run_ref_audit(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"),
        data_dir=str(DATA), include_topology=True, include_library=True)
    assert out["topology_rows"]  # REF-08 矩阵（复用同一次审计）
    assert out["library_stats"]["total_entries"] >= 1


def test_run_full_audit_equals_engine_direct_call():
    _require_docx()
    from taw import fullaudit

    docx_path = str(THESIS / "thesis_synthetic.docx")
    expected = fullaudit.audit_thesis(docx_path, data_dir=str(DATA))
    got = service.run_full_audit(docx_path, data_dir=str(DATA))
    assert json.dumps(got, ensure_ascii=False, sort_keys=True) == \
        json.dumps(expected, ensure_ascii=False, sort_keys=True)
    assert got["doc"]["paragraphs"] == 62


def test_run_full_audit_requires_docx():
    with pytest.raises(ValueError):
        service.run_full_audit(None, data_dir=str(DATA))


def test_recommendations_require_both_inputs():
    with pytest.raises(ValueError):
        service.run_recommendations(None, None, data_dir=str(DATA))
    recs = service.run_recommendations(
        str(AUDIT / "body.txt"), str(AUDIT / "refs_table.txt"), data_dir=str(DATA))
    assert isinstance(recs, list)


# ---- 导出：复用引擎写盘 + HTML 0 外链 ----


def test_export_report_matches_cli_writer(tmp_path):
    """GUI 导出与 CLI `--report` 走同一写盘函数 → 产物位级一致。"""
    report = refaudit.audit_refs(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"), data_dir=str(DATA))
    gui_out = Path(service.export_report(report, tmp_path / "gui.json"))
    cli_out = Path(refaudit.write_report(report, tmp_path / "cli.json"))
    assert gui_out.read_bytes() == cli_out.read_bytes()
    data = json.loads(gui_out.read_text(encoding="utf-8"))
    assert data["summary"]["total"] == 6


def test_export_topology_zero_external(tmp_path):
    from taw import reftopo

    out = service.export_topology(
        str(AUDIT / "refs_table.txt"), str(AUDIT / "body.txt"), tmp_path / "topo.html")
    html_text = Path(out).read_text(encoding="utf-8")
    assert reftopo.assert_no_external_refs(html_text) is True


def test_export_review_topology_zero_external(tmp_path):
    from taw import reftopo

    out = service.export_review_topology(str(DATA), tmp_path / "rev.html")
    assert reftopo.assert_no_external_refs(Path(out).read_text(encoding="utf-8")) is True


def test_export_review_topology_without_corpus_raises(tmp_path):
    empty = tmp_path / "data"
    (empty / "frozen" / "review").mkdir(parents=True)
    with pytest.raises(ValueError):
        service.export_review_topology(str(empty), tmp_path / "rev.html")
