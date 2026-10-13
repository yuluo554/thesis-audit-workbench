# -*- coding: utf-8 -*-
"""`python -m taw.gui` 与 `taw-gui` 入口：启动 PySide6 桌面窗口。

缺 PySide6 时大声失败并给出安装命令（GUI 是显式 extras，不静默降级为 CLI）。
"""

import sys


def main():
    try:
        from taw.gui.app import main as run
    except ImportError as exc:
        print("GUI 需要 gui extras：python -m pip install -e './code[gui]'（{}）".format(exc))
        return 1
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
