# -*- coding: utf-8 -*-
"""PyInstaller onedir 打包 spec（M6）——**双 exe 共用一个 onedir 目录**：

    dist/taw/taw.exe        （CLI，console=True）
    dist/taw/taw-gui.exe    （GUI，console=False）
    dist/taw/_internal/     （依赖 + 内嵌 data/；PyInstaller 5 为扁平布局）

版本纪律（plan/03 §三）：py3.12 起统一 `pyinstaller>=6.22,<7`（3.8 的
modulegraph 崩溃分支已随运行时下限抬升删除）。

onedir 要点（首版踩坑实录）：EXE 必须 `exclude_binaries=True`，把 binaries/datas
交给 COLLECT——否则 EXE 会把整包嵌进 exe 本体（产出 57MB 的伪 onefile，
且运行时解到 `_MEIxxxx` 临时目录）。

内嵌数据（plan/03 §五第 9 条）：`data/README.md`（数据根标志，**必须带**）+
`frozen/`、`bench/`、`knowledge/`、`rulesets/`。`taw/paths.py` 五分支已覆盖
PyInstaller 5（exe 目录 `_internal/data`）与 6（`sys._MEIPASS/data`）两布局。

用法：

    pyinstaller code/tools/taw.spec --noconfirm --clean --distpath <dist>
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# spec 在 code/tools/ 下；仓库根 = 上溯两级
REPO_ROOT = Path(SPECPATH).resolve().parents[1]  # noqa: F821 (PyInstaller 注入)
DATA_ROOT = REPO_ROOT / "data"
SRC = REPO_ROOT / "code" / "src"

# 随包数据：四目录全量（与 CLI 数据面同源；_private/ 绝不入包）
DATA_DIRS = ("frozen", "bench", "knowledge", "rulesets")


def _data_files():
    """→ PyInstaller datas 列表：把 data/<dir> 映射到包内 data/<dir>。

    **必须带上 `data/README.md`**：`taw/paths.py` 的 `_is_valid` 以它为数据根
    标志（`is_dir() and (dir/'README.md').is_file()`）；漏了它，打包后
    `find_data_dir` 会认为内嵌数据无效而整体降级。
    """
    out = []
    readme = DATA_ROOT / "README.md"
    if readme.is_file():
        out.append((str(readme), "data"))
    for name in DATA_DIRS:
        src = DATA_ROOT / name
        if src.is_dir():
            out.append((str(src), os.path.join("data", name)))
    return out


# taw 包内按需导入的子模块（GUI/COM 惰性导入）显式收集，防静态分析漏接。
# 注意：**不收集 pyvis**（D-2 A）——冻结 exe 走 reftopo 内置降级渲染器；
# pyvis 依赖链会拖入 IPython→jedi/parso 等 2,000+ 无关文件。
hidden = []
hidden += collect_submodules("taw")
hidden += ["taw.gui", "taw.gui.app", "taw.gui.__main__", "taw.gui.service"]
hidden += ["docx"]

# 重依赖排除（红线 check_build_redline.py 会再按产物目录断言一次，
# 因为 PyInstaller 的 excludes 对 hook 拉入的包不总是生效）。
HEAVY_EXCLUDES = [
    "tkinter", "matplotlib", "numpy", "PIL",
    "pyvis",              # D-2 A：冻结 exe 走 reftopo 内置降级渲染器
    "IPython", "jedi", "parso", "prompt_toolkit",
    "Pythonwin", "pythonwin", "pywin", "pywin.dialogs", "pywin.mfc", "win32ui",
    # ↑ D-3 A：保留 pywin32/win32com，去掉 Pythonwin IDE 壳（pywin32 实际模块名小写）
]

block_cipher = None

# CLI 侧 Analysis：拿到全量 binaries/datas，供 COLLECT 使用
a_cli = Analysis(
    [str(SRC / "taw" / "cli.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=_data_files(),
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=list(HEAVY_EXCLUDES),
    cipher=block_cipher,
    noarchive=False,
)
pyz_cli = PYZ(a_cli.pure, a_cli.zipped_data, cipher=block_cipher)
# exclude_binaries=True → EXE 只做引导壳，依赖与数据交给 COLLECT（真 onedir）
exe_cli = EXE(
    pyz_cli, a_cli.scripts, [],
    exclude_binaries=True,
    name="taw",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

# GUI 侧 Analysis：只需补齐 GUI 入口的纯 Python 模块（依赖同 CLI）
a_gui = Analysis(
    [str(SRC / "taw" / "gui" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=_data_files(),
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=list(HEAVY_EXCLUDES),
    cipher=block_cipher,
    noarchive=False,
)
pyz_gui = PYZ(a_gui.pure, a_gui.zipped_data, cipher=block_cipher)
exe_gui = EXE(
    pyz_gui, a_gui.scripts, [],
    exclude_binaries=True,
    name="taw-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI 无控制台窗口
)

# onedir：两个引导壳 + CLI 侧全量 binaries/datas（GUI 的依赖是 CLI 的子集）
coll = COLLECT(
    exe_cli, exe_gui,
    a_cli.binaries, a_cli.datas,
    a_gui.binaries, a_gui.datas,
    strip=False,
    upx=False,
    name="taw",
)
