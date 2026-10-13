# -*- coding: utf-8 -*-
"""构建工具的控制台编码收口（M7：CI cp1252 实测坑）。

`code/tools/` 下的收口脚本（构建红线 / 中立目录验证 / 脱敏审计）都会打印中文；
Windows CI runner 的 stdout 默认 cp1252，直接 `print` 中文会抛 `UnicodeEncodeError`
并让整条命令**崩在打印上**（M6 只给 `taw.cli` 补了这个守卫，工具侧漏了——首次
push 跑 CI 才暴露）。

处置与 `taw.cli._ensure_utf8_stdout` 同口径：能 `reconfigure` 就切 UTF-8，不能
（被重定向的旧式流）则退化为 `errors="replace"`——宁可显示替换字符，也不让命令崩。
"""

import io
import sys


def ensure_utf8_stdout():
    """把 stdout/stderr 切到 UTF-8（或至少可替换错误），防非 UTF-8 控制台崩溃。"""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        enc = (getattr(stream, "encoding", None) or "").lower()
        if enc.replace("-", "") in ("utf8", "utf16", "utf32"):
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:          # Py3.7+ TextIOWrapper
            try:
                reconfigure(encoding="utf-8", errors="replace")
                continue
            except (ValueError, OSError):
                pass
        try:                                 # 兜底：包一层可替换错误的写流
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                setattr(sys, name, io.TextIOWrapper(
                    buffer, encoding="utf-8", errors="replace", line_buffering=True))
        except (ValueError, OSError, AttributeError):
            pass