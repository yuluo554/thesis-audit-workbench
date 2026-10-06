"""CLI 契约测试：退出码语义与双入口（plan/03 §五第 7 条口径，改动须记决策）。"""

import subprocess
import sys
from pathlib import Path

import pytest

from taw import __version__
from taw.cli import EXIT_OK, main

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_prints_help_exit_zero(capsys):
    assert main([]) == EXIT_OK
    out = capsys.readouterr().out
    assert "selfcheck" in out and "demo" in out


def test_unknown_command_exits_two():
    with pytest.raises(SystemExit) as excinfo:
        main(["no-such-command"])
    assert excinfo.value.code == 2


def test_selfcheck_ok_inside_repo(monkeypatch, capsys):
    monkeypatch.chdir(REPO_ROOT)  # data/ 以 CWD 上溯分支命中
    assert main(["selfcheck"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "16" in out and "数据目录" in out


def test_demo_lists_all_lines(capsys):
    assert main(["demo"]) == EXIT_OK
    out = capsys.readouterr().out
    for module_id in ("REF-01", "REF-09", "FULL-01", "FULL-06", "BENCH-01"):
        assert module_id in out


def test_both_entry_points_run():
    """console_script `taw` 与 `python -m taw` 双入口契约（要求 editable 安装）。

    console script 用 sysconfig 定位绝对路径——验证"已装且可跑"的契约本身，
    不依赖本机 PATH 是否包含 Scripts 目录（CI 的 PATH 含它，直调亦可）。
    """
    import os
    import sysconfig

    scripts_dir = Path(sysconfig.get_path("scripts"))
    exe = scripts_dir / ("taw.exe" if os.name == "nt" else "taw")
    assert exe.exists(), "console_script 未安装: {}".format(exe)
    for cmd in ([sys.executable, "-m", "taw", "--version"], [str(exe), "--version"]):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, "入口失败: {} -> {}".format(cmd, proc.stderr)
        assert __version__ in proc.stdout
