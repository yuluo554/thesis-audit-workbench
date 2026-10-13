# -*- coding: utf-8 -*-
"""pytest 全局配置：GUI 离屏纪律前置（plan/03 §四）。

在**测试收集之前**把 `QT_QPA_PLATFORM` 置为 `offscreen`——测试模块里的
`os.environ.setdefault` 只在该模块导入时生效，若将来有别的模块先导入 Qt，
显示后端就会在无显示器环境上崩。此处统一前置，保证任何 Qt 导入都走离屏。

不影响非 GUI 测试：未装 PySide6 时该环境变量无害（GUI 模块整体 skip）。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
