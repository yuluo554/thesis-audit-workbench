"""数据目录解析：五分支冻结顺序（plan/03 §五第 8 条口径，tests/test_paths.py 锁定）。

顺序：显式参数 > TAW_DATA_DIR 环境变量 > sys._MEIPASS/data（PyInstaller 6 内嵌）
> exe 目录/_internal/data（PyInstaller 5 兼容）> CWD 上溯找 data/。
改优先级 = 口径变更，必须同步修改测试并记决策。
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

ENV_VAR = "TAW_DATA_DIR"
MARKER_NAME = "README.md"


def _is_valid(path):
    return path.is_dir() and (path / MARKER_NAME).is_file()


def _branches(explicit):
    yield "explicit", None if explicit is None else Path(explicit)
    env = os.environ.get(ENV_VAR)
    yield "env", None if not env else Path(env)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        yield "pyinstaller-embedded", Path(meipass) / "data"
    exe_dir = Path(sys.executable).parent
    yield "pyinstaller-sidecar", exe_dir / "_internal" / "data"
    cwd = Path.cwd()
    for base in [cwd] + list(cwd.parents):
        yield "cwd-walk", base / "data"


def find_data_dir_details(explicit=None) -> Tuple[Optional[Path], str]:
    """返回 (数据目录, 命中来源)；找不到返回 (None, 'not-found')。

    显式参数与环境变量设置但无效时抛 FileNotFoundError——配置错误必须大声失败，
    静默落到下一分支会掩盖打包环境的数据内嵌问题。
    """
    for source, candidate in _branches(explicit):
        if candidate is None:
            continue
        if not _is_valid(candidate):
            if source in ("explicit", "env"):
                raise FileNotFoundError(
                    "数据目录无效（{} = {!r}）：需为目录且含 {}".format(
                        source, str(candidate), MARKER_NAME
                    )
                )
            continue
        return candidate, source
    return None, "not-found"


def find_data_dir(explicit=None) -> Optional[Path]:
    path, _ = find_data_dir_details(explicit)
    return path
