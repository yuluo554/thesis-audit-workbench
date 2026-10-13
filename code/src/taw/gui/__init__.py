# -*- coding: utf-8 -*-
"""PySide6 桌面交付层（M6；extras `gui`）。

- `service`：**纯 Python 服务层**（不 import Qt）——只调引擎 API、摊平 findings、
  导出产物；GUI 的一切结论都经由它，杜绝"GUI 第二套判定逻辑"。
- `app`：PySide6 窗口（惰性依赖，仅当 extras `gui` 装上时可导入）。

铁律：CLI 是单一事实源（plan/03 §一）；本层不做任何判定。
"""

from taw.gui import service  # noqa: F401

__all__ = ["service"]
