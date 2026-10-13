# -*- coding: utf-8 -*-
"""PySide6 窗口离屏测试（**模块级 importorskip：缺装=整模块 skip**，plan/03 §四）。

离屏纪律：模块导入期先置 `QT_QPA_PLATFORM=offscreen`，再建 QApplication——
无桌面/无显示器的 CI 上也能构造与刷新窗口（不调 exec()，不进事件循环）。

守门：窗口只做「选文件 → 调 service → 摊平展示 → 导出」，结论与引擎一致；
`taw gui --check` 走同一条构造路径（CI 冒烟）。
"""

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # 模块级声明式跳过：缺装=整模块 skip（计为 skip 而非 fail）
    import PySide6  # noqa: F401
except ImportError:
    pytest.skip("GUI 测试需要 gui extras（缺装=整模块跳过）", allow_module_level=True)

from taw.cli import EXIT_OK, main  # noqa: E402
from taw.gui import app as gui_app  # noqa: E402
from taw.gui import service  # noqa: E402
from taw.gui.app import FindingsView, MainWindow  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
AUDIT = DATA / "frozen" / "audit"
THESIS = DATA / "frozen" / "thesis"


@pytest.fixture(scope="module")
def qapp():
    app, _window = gui_app.build_app([])
    return app


@pytest.fixture()
def window(qapp):
    win = MainWindow(data_dir=str(DATA))
    yield win
    win.close()


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("GUI docx 路径测试需要 docx extras（CI/README 已装；缺装=环境配置错误）：{}".format(exc))


# ---- 窗口构造与展示 ----


def test_main_window_constructs_offscreen(window):
    assert "毕业论文全流程审计工作台" in window.windowTitle()
    assert window.tabs.count() == 2
    assert window.tabs.tabText(0) == "文献审计线"
    assert window.tabs.tabText(1) == "全文审计线"
    assert str(DATA) in window.data_label.text()


def test_run_refs_audit_fills_table_and_status(window):
    window.refs_table.setText(str(AUDIT / "refs_table.txt"))
    window.refs_body.setText(str(AUDIT / "body.txt"))
    report = window.run_refs_audit()
    assert report is not None and report["summary"]["total"] == 6
    assert window.refs_view.row_count() == 6
    assert window.refs_view.cell_text(0, 2) == "不符"
    assert window.refs_view.cell_text(1, 2) == "待人工确认"
    assert window.refs_view.cell_text(0, 5) == "条款待核对"
    assert "findings 6 条" in window.statusBar().currentMessage()


def test_table_matches_service_flatten(window):
    """界面表格逐格等于 service 摊平结果（展示层零改写）。"""
    window.refs_table.setText(str(AUDIT / "refs_table.txt"))
    window.refs_body.setText(str(AUDIT / "body.txt"))
    report = window.run_refs_audit()
    expected = service.flatten_findings(report)
    for r, row in enumerate(expected):
        for c, text in enumerate(service.row_cells(row)):
            assert window.refs_view.cell_text(r, c) == text


def test_run_full_audit_fills_table(qapp):
    _require_docx()
    win = MainWindow(data_dir=str(DATA))
    try:
        win.full_docx.setText(str(THESIS / "thesis_synthetic.docx"))
        report = win.run_full_audit()
        assert report is not None
        assert win.full_view.row_count() == len(report["findings"])
        assert "全文线审计完成" in win.statusBar().currentMessage()
    finally:
        win.close()


def test_selection_shows_evidence_chain(window):
    """选中行 → 详情面板出完整证据链 JSON（含 basis 与 location）。"""
    window.refs_table.setText(str(AUDIT / "refs_table.txt"))
    window.refs_body.setText(str(AUDIT / "body.txt"))
    window.run_refs_audit()
    window.refs_view.table.selectRow(0)
    window.refs_view._on_select()
    detail = json.loads(window.refs_view.detail.toPlainText())
    assert detail["evidence"]["location"]["entry_id"] == "ref-000004"
    assert detail["basis"]


def test_findings_view_set_report_is_pure(qapp):
    """FindingsView 单独构造也能刷新（视图不依赖主窗口）。"""
    view = FindingsView()
    report = service.run_ref_audit(
        str(AUDIT / "refs_table.txt"), data_dir=str(DATA))["report"]
    n = view.set_report(report)
    assert n == view.row_count() == len(report["findings"])
    view.set_report({"findings": [], "summary": {"total": 0, "by_status": {}}, "modules": {}})
    assert view.row_count() == 0


# ---- 导出按钮路径（不弹对话框，直接调槽函数所委托的 service）----


def test_window_exports_report_and_topology(window, tmp_path):
    from taw import reftopo

    window.refs_table.setText(str(AUDIT / "refs_table.txt"))
    window.refs_body.setText(str(AUDIT / "body.txt"))
    window.run_refs_audit()
    window.report = window.report or None
    report_path = service.export_report(window.report, tmp_path / "r.json")
    assert json.loads(Path(report_path).read_text(encoding="utf-8"))["summary"]["total"] == 6
    topo_path = service.export_topology(
        str(AUDIT / "refs_table.txt"), str(AUDIT / "body.txt"), tmp_path / "t.html")
    assert reftopo.assert_no_external_refs(Path(topo_path).read_text(encoding="utf-8")) is True


# ---- CLI 冒烟入口（taw gui --check 与窗口同一条构造路径）----


def test_cli_gui_check_exits_zero(capsys):
    assert main(["gui", "--check"]) == EXIT_OK
    assert "启动自检通过" in capsys.readouterr().out


# ---- 演示 GIF 工具（plan/05 M6 可演示物：exe + 演示 GIF）----


def test_demo_gif_builder_assembles_frames(tmp_path):
    """演示 GIF 合成器：多帧 PNG → 单文件动画（M6 可演示物的产物路径）。

    Pillow 未装时跳过（演示脚本按需运行，不进 CI 依赖面）。
    """
    PIL = pytest.importorskip("PIL.Image", reason="演示 GIF 合成需要 Pillow（按需运行）")
    sys.path.insert(0, str(REPO_ROOT / "code" / "tools"))
    import make_demo_gif

    frames = []
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)]):
        img = PIL.new("RGB", (200, 120), color)
        p = tmp_path / "f{}.png".format(i)
        img.save(str(p))
        frames.append((p, "frame{}".format(i)))

    out = make_demo_gif.build_gif(frames, tmp_path / "demo.gif", duration_ms=100)
    assert out.is_file()
    gif = PIL.open(str(out))
    assert gif.n_frames == 3
    assert gif.size[0] <= 1180
