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


def test_parse_without_path_is_usage_error(capsys):
    assert main(["parse"]) == 2
    assert "用法错误" in capsys.readouterr().out


def test_parse_refs_file_ok(capsys):
    refs = REPO_ROOT / "data" / "frozen" / "refs" / "refs_clean.bib"
    assert main(["parse", str(refs)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "条目 24" in out


def test_parse_missing_file_is_usage_error(capsys):
    assert main(["parse", str(REPO_ROOT / "data" / "no-such-file.txt")]) == 2
    assert "失败" in capsys.readouterr().out


def test_parse_thesis_docx_ok(capsys):
    docx_path = REPO_ROOT / "data" / "frozen" / "thesis" / "thesis_synthetic.docx"
    if not docx_path.is_file():
        pytest.skip("docx fixture 缺失")
    try:
        import docx  # noqa: F401
    except ImportError:
        pytest.fail("parse docx 测试需要 docx extras（CI/README 已装；缺装=环境配置错误）")
    assert main(["parse", str(docx_path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "段 62" in out and "对象 9" in out


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


# ---- M3：audit 子命令 ----


def test_audit_without_target_is_usage_error(capsys):
    assert main(["audit"]) == 2
    assert "用法错误" in capsys.readouterr().out


def test_audit_refs_ok_and_exit_zero(capsys):
    table = REPO_ROOT / "data" / "frozen" / "audit" / "refs_table.txt"
    body = REPO_ROOT / "data" / "frozen" / "audit" / "body.txt"
    assert main(["audit", "refs", str(table), "--body", str(body)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "文献线审计" in out and "REF-04-citation" in out


def test_audit_refs_missing_file_is_usage_error(capsys):
    assert main(["audit", "refs", str(REPO_ROOT / "data" / "no-such.txt")]) == 2
    assert "失败" in capsys.readouterr().out


def test_audit_refs_json_and_report(tmp_path, capsys):
    import json
    table = REPO_ROOT / "data" / "frozen" / "audit" / "refs_table.txt"
    body = REPO_ROOT / "data" / "frozen" / "audit" / "body.txt"
    report = tmp_path / "r.json"
    assert main(["audit", "refs", str(table), "--body", str(body),
                 "--json", "--report", str(report)]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["table"]["entries"] == 9
    assert report.is_file()


def test_audit_refs_topology_requires_body(capsys):
    table = REPO_ROOT / "data" / "frozen" / "audit" / "refs_table.txt"
    assert main(["audit", "refs", str(table), "--topology", "x.html"]) == 2
    assert "需要同时给 --body" in capsys.readouterr().out


def test_audit_refs_topology_zero_external(tmp_path, capsys):
    from taw import reftopo
    table = REPO_ROOT / "data" / "frozen" / "audit" / "refs_table.txt"
    body = REPO_ROOT / "data" / "frozen" / "audit" / "body.txt"
    out = tmp_path / "topo.html"
    assert main(["audit", "refs", str(table), "--body", str(body),
                 "--topology", str(out)]) == EXIT_OK
    assert reftopo.assert_no_external_refs(out.read_text(encoding="utf-8")) is True


def test_audit_refs_library_write(tmp_path, capsys):
    table = REPO_ROOT / "data" / "frozen" / "audit" / "refs_table.txt"
    db = tmp_path / "lib.db"
    assert main(["audit", "refs", str(table), "--library", str(db)]) == EXIT_OK
    assert db.is_file()
    assert "文献库入库完成" in capsys.readouterr().out


def test_audit_bench_ok(capsys):
    assert main(["audit", "bench"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "9 指标" in out or "9 指标" in out
    assert "守门: 全过" in out


def test_audit_bench_json(capsys):
    import json
    assert main(["audit", "bench", "--json"]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["gate"]["all_pass"] is True


def test_audit_bench_report(tmp_path, capsys):
    rep = tmp_path / "bench.json"
    assert main(["audit", "bench", "--report", str(rep)]) == EXIT_OK
    assert rep.is_file()


# ---- M4：audit thesis 与 bench --line ----


def _require_docx_cli():
    try:
        import docx  # noqa: F401
    except ImportError:
        pytest.fail("audit thesis 测试需要 docx extras（CI/README 已装；缺装=环境配置错误）")


def test_audit_thesis_ok_and_exit_zero(capsys):
    _require_docx_cli()
    docx_path = REPO_ROOT / "data" / "frozen" / "thesis" / "thesis_synthetic.docx"
    assert main(["audit", "thesis", str(docx_path)]) == EXIT_OK
    out = capsys.readouterr().out
    assert "全文线审计" in out and "FULL-01-xref" in out
    assert "AIGC 伦理边界" in out


def test_audit_thesis_missing_file_is_usage_error(capsys):
    assert main(["audit", "thesis", str(REPO_ROOT / "data" / "no-such.docx")]) == 2
    assert "失败" in capsys.readouterr().out


def test_audit_thesis_json_and_report(tmp_path, capsys):
    _require_docx_cli()
    import json
    docx_path = REPO_ROOT / "data" / "frozen" / "thesis" / "thesis_synthetic.docx"
    report = tmp_path / "full.json"
    assert main(["audit", "thesis", str(docx_path), "--json", "--report", str(report)]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["doc"]["paragraphs"] == 62
    assert report.is_file()


def test_audit_thesis_school_profile(capsys):
    _require_docx_cli()
    docx_path = REPO_ROOT / "data" / "frozen" / "thesis" / "thesis_synthetic.docx"
    assert main(["audit", "thesis", str(docx_path), "--profile", "school-demo"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "全文线审计" in out


def test_audit_bench_full_line_ok(capsys):
    assert main(["audit", "bench", "--line", "full"]) == EXIT_OK
    out = capsys.readouterr().out
    assert "全文线 5 指标" in out and "守门: 全过" in out


def test_audit_bench_all_json(capsys):
    import json
    assert main(["audit", "bench", "--line", "all", "--json"]) == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["refs"]["gate"]["all_pass"] is True
    assert data["full"]["gate"]["all_pass"] is True


def test_audit_thesis_review_topology_zero_external(tmp_path, capsys):
    """综述聚类 HTML（FULL-05 可视化）落盘且 0 外链。"""
    _require_docx_cli()
    from taw import reftopo
    docx_path = REPO_ROOT / "data" / "frozen" / "thesis" / "thesis_synthetic.docx"
    out = tmp_path / "rev.html"
    assert main(["audit", "thesis", str(docx_path), "--review-topology", str(out)]) == EXIT_OK
    assert out.is_file()
    assert reftopo.assert_no_external_refs(out.read_text(encoding="utf-8")) is True


# ---- M6：GUI 子命令与输出编码纪律 ----


def test_gui_check_degraded_or_ok(capsys):
    """`taw gui --check`：装了 gui extras → 0（构造离屏窗口）；缺装 → 1（降级）。

    两条都是合法结果，但绝不允许是别的码或抛异常——GUI 是显式 extras，
    缺装必须**明确降级**而不是静默按 CLI 跑。
    """
    from taw.cli import EXIT_DEGRADED
    code = main(["gui", "--check"])
    assert code in (EXIT_OK, EXIT_DEGRADED)
    out = capsys.readouterr().out
    if code == EXIT_OK:
        assert "启动自检通过" in out
    else:
        assert "gui extras" in out


def test_cli_survives_non_utf8_stdout():
    """非 UTF-8 stdout（Windows CI 管道 cp1252）不得把中文输出打成 UnicodeEncodeError。

    入口的编码探针（`_ensure_utf8_stdout`）负责 reconfigure；这条测试用子进程
    强制 `PYTHONIOENCODING=cp1252` 复现该环境。
    """
    import os
    import subprocess
    import sys

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for args in (["demo"], ["selfcheck"], ["audit", "bench"]):
        proc = subprocess.run([sys.executable, "-m", "taw"] + args,
                              capture_output=True, env=env, timeout=180)
        err = (proc.stderr or b"").decode("utf-8", "replace")
        assert proc.returncode == 0, "{} 在 cp1252 下退出码 {}：{}".format(
            args, proc.returncode, err[-300:])
        assert "UnicodeEncodeError" not in err, "{} 在 cp1252 下编码崩溃".format(args)
