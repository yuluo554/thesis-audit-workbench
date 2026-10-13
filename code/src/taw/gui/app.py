# -*- coding: utf-8 -*-
"""PySide6 桌面窗口（M6 交付层）。

**单一事实源纪律**：本模块不含任何判定逻辑——所有结论都来自
`taw.gui.service`（其内部只调 `taw.refaudit` / `taw.fullaudit` 等引擎 API）。
窗口的职责仅限：选文件 → 触发引擎 → 摊平展示 → 导出产物。

离屏测试纪律（plan/03 §四）：测试置 `QT_QPA_PLATFORM=offscreen`，模块级
`pytest.importorskip("PySide6")` 声明式跳过；窗口构造与刷新都不需要显示屏幕。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from taw import __version__
from taw.gui import service


def _pick_file(parent, title, name_filter):
    path, _selected = QFileDialog.getOpenFileName(parent, title, "", name_filter)
    return path or None


def _pick_save(parent, title, name_filter, default_name):
    path, _selected = QFileDialog.getSaveFileName(parent, title, default_name, name_filter)
    return path or None


class FindingsView(QWidget):
    """概览 + findings 表格 + 选中详情的三合一视图（两个标签页共用）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.summary = QPlainTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(140)
        self.summary.setPlaceholderText("运行审计后在此显示结论概览")

        self.table = QTableWidget(0, len(service.COLUMNS))
        self.table.setHorizontalHeaderLabels(list(service.COLUMNS))
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(
            len(service.COLUMNS) - 1, QHeaderView.Stretch)

        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("选中一行查看完整证据链（条款 / 依据 / 位置）")

        split = QSplitter(Qt.Horizontal)
        holder = QWidget()
        h = QVBoxLayout(holder)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.summary)
        h.addWidget(self.table)
        split.addWidget(holder)
        split.addWidget(self.detail)
        split.setSizes([700, 400])

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(split)

        self.table.itemSelectionChanged.connect(self._on_select)
        self._rows = []

    def set_report(self, report):
        """由引擎 report 刷新视图（纯展示，不改任何字段）。"""
        self._rows = service.flatten_findings(report)
        self.summary.setPlainText("\n".join(service.summary_lines(report)))
        self.table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            for c, text in enumerate(service.row_cells(row)):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        self.detail.setPlainText("")
        return len(self._rows)

    def row_count(self):
        return self.table.rowCount()

    def cell_text(self, row, col):
        item = self.table.item(row, col)
        return "" if item is None else item.text()

    def _on_select(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._rows):
            self.detail.setPlainText(service.finding_detail_text(self._rows[idx]))


class MainWindow(QMainWindow):
    def __init__(self, data_dir=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("毕业论文全流程审计工作台 taw {}".format(__version__))
        self.resize(1180, 740)
        self.report = None
        self._data_dir = data_dir if data_dir is not None else self._auto_data_dir()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        self.data_label = QLabel()
        root.addWidget(self.data_label)
        self._refresh_data_label()

        self.tabs = QTabWidget()
        self.refs_view = FindingsView()
        self.full_view = FindingsView()
        self.tabs.addTab(self._build_refs_tab(), "文献审计线")
        self.tabs.addTab(self._build_full_tab(), "全文审计线")
        root.addWidget(self.tabs)
        self.statusBar().showMessage("就绪")

    # ---- 数据目录 ----

    def _auto_data_dir(self):
        path, source = service.data_dir_status()
        self._data_source = source
        return path

    def _refresh_data_label(self):
        path, source = service.data_dir_status()
        if self._data_dir is None:
            self._data_dir = path
        if self._data_dir:
            self.data_label.setText("数据目录：{}（来源：{}）".format(self._data_dir, source))
        else:
            self.data_label.setText("数据目录：未找到（{}）——数据依赖类功能降级".format(source))

    # ---- 文献审计线 ----

    def _build_refs_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self.refs_table = QLineEdit()
        self.refs_body = QLineEdit()
        form.addRow("文献表", self._file_row(self.refs_table, "选择文献表", "文献表 (*.txt *.csv *.bib *.ris)"))
        form.addRow("正文（可选）", self._file_row(self.refs_body, "选择正文", "文本 (*.txt)"))

        self.refs_year = QComboBox()
        self.refs_year.addItems(["2025", "2015"])
        self.refs_profile = QLineEdit("default")
        self.refs_topology = QCheckBox("同时导出拓扑（需正文）")
        row = QHBoxLayout()
        row.addWidget(self.refs_year)
        row.addWidget(QLabel("profile"))
        row.addWidget(self.refs_profile)
        row.addWidget(self.refs_topology)
        row.addStretch(1)
        form.addRow("标尺 / profile", self._wrap(row))
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.refs_run = QPushButton("运行审计")
        self.refs_run.clicked.connect(self.run_refs_audit)
        self.refs_export = QPushButton("导出报告 JSON")
        self.refs_export.clicked.connect(self.export_refs_report)
        self.refs_topo = QPushButton("导出拓扑 HTML")
        self.refs_topo.clicked.connect(self.export_refs_topology)
        self.refs_comment = QPushButton("批注回写 docx")
        self.refs_comment.clicked.connect(self.export_refs_comments)
        for b in (self.refs_run, self.refs_export, self.refs_topo, self.refs_comment):
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.refs_view)
        return page

    # ---- 全文审计线 ----

    def _build_full_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self.full_docx = QLineEdit()
        form.addRow("论文 docx", self._file_row(self.full_docx, "选择论文", "Word 文档 (*.docx)"))
        self.full_year = QComboBox()
        self.full_year.addItems(["2025", "2015"])
        self.full_profile = QLineEdit("default")
        self.full_review = QCheckBox("启用综述辅助（FULL-05）")
        self.full_review.setChecked(True)
        row = QHBoxLayout()
        row.addWidget(self.full_year)
        row.addWidget(QLabel("profile"))
        row.addWidget(self.full_profile)
        row.addWidget(self.full_review)
        row.addStretch(1)
        form.addRow("标尺 / profile", self._wrap(row))
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.full_run = QPushButton("运行审计")
        self.full_run.clicked.connect(self.run_full_audit)
        self.full_export = QPushButton("导出报告 JSON")
        self.full_export.clicked.connect(self.export_full_report)
        self.full_review_html = QPushButton("导出综述聚类 HTML")
        self.full_review_html.clicked.connect(self.export_review_topology)
        for b in (self.full_run, self.full_export, self.full_review_html):
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addWidget(self.full_view)
        return page

    def _file_row(self, line_edit, title, name_filter):
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(line_edit)
        btn = QPushButton("浏览…")

        def _choose():
            path = _pick_file(self, title, name_filter)
            if path:
                line_edit.setText(path)

        btn.clicked.connect(_choose)
        row.addWidget(btn)
        return holder

    def _wrap(self, layout):
        holder = QWidget()
        holder.setLayout(layout)
        return holder

    # ---- 动作（全部委托 service，不做二次判定）----

    def run_refs_audit(self):
        try:
            result = service.run_ref_audit(
                self.refs_table.text().strip() or None,
                body_path=self.refs_body.text().strip() or None,
                standard_year=self.refs_year.currentText(),
                profile=self.refs_profile.text().strip() or "default",
                data_dir=self._data_dir)
        except (ValueError, OSError, RuntimeError) as exc:
            self._warn("文献线审计失败", str(exc))
            return None
        self.report = result["report"]
        n = self.refs_view.set_report(self.report)
        self.statusBar().showMessage("文献线审计完成：findings {} 条".format(n))
        return self.report

    def run_full_audit(self):
        try:
            report = service.run_full_audit(
                self.full_docx.text().strip() or None,
                standard_year=self.full_year.currentText(),
                profile=self.full_profile.text().strip() or "default",
                data_dir=self._data_dir,
                include_review=self.full_review.isChecked())
        except (ValueError, OSError, RuntimeError) as exc:
            self._warn("全文线审计失败", str(exc))
            return None
        self.report = report
        n = self.full_view.set_report(report)
        self.statusBar().showMessage("全文线审计完成：findings {} 条".format(n))
        return report

    def export_refs_report(self):
        if self.report is None:
            self._warn("导出失败", "请先运行审计")
            return None
        path = _pick_save(self, "导出报告", "JSON (*.json)", "refs_audit.json")
        if not path:
            return None
        out = service.export_report(self.report, path)
        self.statusBar().showMessage("报告 → {}".format(out))
        return out

    def export_full_report(self):
        if self.report is None:
            self._warn("导出失败", "请先运行审计")
            return None
        path = _pick_save(self, "导出报告", "JSON (*.json)", "full_audit.json")
        if not path:
            return None
        out = service.export_report(self.report, path)
        self.statusBar().showMessage("报告 → {}".format(out))
        return out

    def export_refs_topology(self):
        table = self.refs_table.text().strip()
        body = self.refs_body.text().strip()
        if not (table and body):
            self._warn("导出失败", "拓扑需要文献表与正文")
            return None
        path = _pick_save(self, "导出拓扑 HTML", "HTML (*.html)", "topology.html")
        if not path:
            return None
        out = service.export_topology(table, body, path)
        self.statusBar().showMessage("拓扑（0 外链）→ {}".format(out))
        return out

    def export_review_topology(self):
        if not self._data_dir:
            self._warn("导出失败", "数据目录不可用（缺综述语料）")
            return None
        path = _pick_save(self, "导出综述聚类 HTML", "HTML (*.html)", "review.html")
        if not path:
            return None
        try:
            out = service.export_review_topology(self._data_dir, path)
        except (ValueError, OSError) as exc:
            self._warn("导出失败", str(exc))
            return None
        self.statusBar().showMessage("综述聚类（0 外链）→ {}".format(out))
        return out

    def export_refs_comments(self):
        docx_path = self.refs_body.text().strip()
        if self.report is None:
            self._warn("回写失败", "请先运行审计")
            return None
        if not docx_path.lower().endswith(".docx"):
            self._warn("回写失败", "批注回写需要目标 docx（在「正文」处选择 docx）")
            return None
        try:
            out = service.write_comment_report(docx_path, self.report)
        except (ValueError, OSError, RuntimeError) as exc:
            self._warn("回写失败", str(exc))
            return None
        self.statusBar().showMessage("批注回写 → {}".format(out))
        return out

    def _warn(self, title, text):
        QMessageBox.warning(self, title, text)


def build_app(argv=None):
    """构造 QApplication + 主窗口（离屏测试与真实启动共用）。"""
    app = QApplication.instance() or QApplication(argv or [])
    window = MainWindow()
    return app, window


def main(argv=None):
    app, window = build_app(argv)
    window.show()
    return app.exec()
