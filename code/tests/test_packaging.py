# -*- coding: utf-8 -*-
"""M6 打包交付守门（构建红线 + 内嵌数据对账 + spec 纪律）。

这些测试**不跑真实 PyInstaller 构建**（几分钟级，属发布流水线），而是把
构建工具的判定逻辑与 spec 的关键约束钉成可执行断言——构建收尾由
`tools/check_build_redline.py` / `tools/verify_neutral_dir.py` 在真实 dist 上跑：

- 红线扫描：`_private` / `.db` / `.env` / 真实实体名命中即失败（假 dist 夹具）；
- 内嵌数据对账：缺文件 / 多文件 / 内容不符三种偏差全都能检出来；
- spec 纪律：onedir（EXE `exclude_binaries=True`）、双 exe（CLI console=True +
  GUI console=False）、**必须带 `data/README.md`**（paths.py 数据根标志）；
- 中立验证工具：命令清单恰为五连、退出码按真实 `returncode` 判定（不接管道）。
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE = REPO_ROOT / "code"
TOOLS = CODE / "tools"
sys.path.insert(0, str(TOOLS))

import check_build_redline as redline  # noqa: E402
import verify_neutral_dir as neutral  # noqa: E402


# ---- 红线扫描 ----


def _make_fake_dist(tmp_path, with_data=True, extra=None, tamper=None, missing=None):
    """造一个假 dist：`<dist>/taw/data/{README.md,frozen,...}`。"""
    bundle = tmp_path / "dist" / "taw"
    data = bundle / "data"
    (data / "frozen" / "refs").mkdir(parents=True)
    (data / "README.md").write_text("# data\n", encoding="utf-8")
    (data / "frozen" / "refs" / "a.txt").write_text("A\n", encoding="utf-8")
    (data / "frozen" / "refs" / "b.txt").write_text("B\n", encoding="utf-8")
    (bundle / "taw.exe").write_bytes(b"MZ")
    for rel, content in (extra or {}).items():
        p = bundle / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    for rel in (tamper or []):
        (data / rel).write_text("TAMPERED\n", encoding="utf-8")
    for rel in (missing or []):
        (data / rel).unlink()
    return tmp_path / "dist", data


def _make_repo_data(tmp_path):
    """造一份"仓库 data/"：与假 dist 的 frozen 完全一致的源。"""
    repo_data = tmp_path / "repo_data"
    (repo_data / "frozen" / "refs").mkdir(parents=True)
    (repo_data / "README.md").write_text("# data\n", encoding="utf-8")
    (repo_data / "frozen" / "refs" / "a.txt").write_text("A\n", encoding="utf-8")
    (repo_data / "frozen" / "refs" / "b.txt").write_text("B\n", encoding="utf-8")
    for sub in ("bench", "knowledge", "rulesets"):
        (repo_data / sub).mkdir(parents=True)
    return repo_data


def test_redline_scan_clean_dist_passes(tmp_path):
    dist, _data = _make_fake_dist(tmp_path)
    result = redline.scan_dist_forbidden(dist)
    assert result["ok"] is True
    assert result["offenders"] == []


@pytest.mark.parametrize("rel,reason_part", [
    ("_private/sources/x.html", "_private"),
    ("lib.db", ".db"),
    ("conf/.env", ".env"),
    ("keys/server.key", ".key"),
])
def test_redline_scan_rejects_forbidden_paths(tmp_path, rel, reason_part):
    dist, _data = _make_fake_dist(tmp_path, extra={rel: "x"})
    result = redline.scan_dist_forbidden(dist)
    assert result["ok"] is False
    assert any(reason_part in off["reason"] for off in result["offenders"])


def test_redline_scan_rejects_real_entity_keywords(tmp_path):
    """真实实体关键词（发布脱敏红线）命中即失败。"""
    dist, _data = _make_fake_dist(tmp_path, extra={"notes_yuluo554.txt": "x"})
    result = redline.scan_dist_forbidden(dist)
    assert result["ok"] is False
    assert any("真实实体关键词" in off["reason"] for off in result["offenders"])


def test_bundled_fictional_names_are_not_flagged(tmp_path):
    """合成数据的虚构校名/人名**不得**被红线误伤（否则打包无法通过）。"""
    dist, _data = _make_fake_dist(
        tmp_path, extra={"frozen/thesis/school_note.txt": "虚构理工大学 李虚构"})
    assert redline.scan_dist_forbidden(dist)["ok"] is True


def test_redline_scan_missing_dist_fails(tmp_path):
    assert redline.scan_dist_forbidden(tmp_path / "nope")["ok"] is False


# ---- 内嵌数据对账 ----


def test_reconcile_embedded_data_ok(tmp_path):
    dist, _data = _make_fake_dist(tmp_path)
    repo = _make_repo_data(tmp_path)
    result = redline.reconcile_embedded_data(dist, repo)
    assert result["ok"] is True
    assert result["missing"] == [] and result["extra"] == [] and result["mismatched"] == []


def test_reconcile_detects_missing_file(tmp_path):
    """漏打一个数据文件 = 构建事故，必须被检出。"""
    dist, _data = _make_fake_dist(tmp_path, missing=["frozen/refs/b.txt"])
    repo = _make_repo_data(tmp_path)
    result = redline.reconcile_embedded_data(dist, repo)
    assert result["ok"] is False
    assert "frozen/refs/b.txt" in result["missing"]


def test_reconcile_detects_content_mismatch(tmp_path):
    """打入的是旧版数据（路径齐但字节不符）→ 必须被检出。"""
    dist, _data = _make_fake_dist(tmp_path, tamper=["frozen/refs/a.txt"])
    repo = _make_repo_data(tmp_path)
    result = redline.reconcile_embedded_data(dist, repo)
    assert result["ok"] is False
    assert "frozen/refs/a.txt" in result["mismatched"]


def test_reconcile_detects_extra_file(tmp_path):
    """内嵌数据里多出文件（混入不该进包的东西）→ 必须被检出。"""
    dist, _data = _make_fake_dist(tmp_path, extra={"data/frozen/refs/zz.txt": "Z\n"})
    repo = _make_repo_data(tmp_path)
    result = redline.reconcile_embedded_data(dist, repo)
    assert result["ok"] is False
    assert "frozen/refs/zz.txt" in result["extra"]


def test_reconcile_reports_missing_data_root(tmp_path):
    dist = tmp_path / "dist"
    (dist / "taw").mkdir(parents=True)
    repo = _make_repo_data(tmp_path)
    result = redline.reconcile_embedded_data(dist, repo)
    assert result["ok"] is False
    assert "内嵌数据根" in result["reason"]


def test_assert_redline_combines_and_writes_json(tmp_path):
    dist, _data = _make_fake_dist(tmp_path)
    repo = _make_repo_data(tmp_path)
    out = tmp_path / "redline.json"
    result = redline.assert_redline(dist, repo, out_json=out)
    assert result["ok"] is True
    import json
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["ok"] is True and saved["forbidden"]["ok"] is True


def test_embedded_dirs_match_spec_data_dirs():
    """spec 的 DATA_DIRS 与对账工具口径必须一致（改一处忘另一处 = 假绿）。"""
    spec_text = (TOOLS / "taw.spec").read_text(encoding="utf-8")
    for name in redline.EMBEDDED_DIRS:
        assert '"{}"'.format(name) in spec_text, "spec 缺数据目录: {}".format(name)


# ---- spec 纪律 ----


def _spec_source():
    return (TOOLS / "taw.spec").read_text(encoding="utf-8")


def _spec_code():
    """剥离 docstring 与注释后的 spec 源码（断言只针对**可执行代码**）。

    用 ast 找出各作用域首个 docstring 的行号区间并剔除；另按 tokenize 去掉
    `#` 注释（"`_private` 绝不入包"这类话只应出现在注释里，不该被当成
    违规命中，也不该因注释而通过）。3.8 无 ast.unparse，故按行/标记过滤。
    """
    import ast
    import io
    import tokenize

    source = _spec_source()
    tree = ast.parse(source)
    drop = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                for lineno in range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1):
                    drop.add(lineno)
    lines = [line for i, line in enumerate(source.splitlines(), 1) if i not in drop]
    kept = "\n".join(lines)
    # 去 `#` 注释（保留字符串内的 # 由 tokenize 判定）
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(kept).readline):
        if tok.type == tokenize.COMMENT:
            continue
        out.append(tok)
    return tokenize.untokenize(out)


def test_spec_is_onedir_not_onefile():
    """onedir 关键：EXE 必须 exclude_binaries=True（否则变成伪 onefile 内嵌全包）。"""
    code = _spec_code()
    assert code.count("exclude_binaries=True") == 2, "两个 exe 都须 exclude_binaries=True"
    assert "COLLECT(" in code
    assert 'name="taw"' in code


def test_spec_dual_exe_console_flags():
    """双 exe：CLI console=True（管道可用）+ GUI console=False（无黑窗）。"""
    code = _spec_code()
    assert 'name="taw"' in code and 'name="taw-gui"' in code
    assert code.count("console=True") == 1
    assert code.count("console=False") == 1


def test_spec_bundles_data_readme_marker():
    """`data/README.md` 是 paths.py 的数据根标志，spec 必须显式带上。"""
    code = _spec_code()
    assert "README.md" in code


def test_spec_collects_gui_and_lazy_submodules():
    """GUI 入口与惰性子模块显式收集（PyInstaller 静态分析会漏掉惰性导入）。"""
    code = _spec_code()
    assert "collect_submodules" in code
    for name in ("taw.gui", "taw.gui.__main__", "docx"):
        assert name in code


def test_spec_excludes_heavy_optional_and_never_private():
    """spec 不得把 `_private` 打进包；重依赖（tkinter 等）排除以控体积。"""
    code = _spec_code()
    assert "_private" not in code
    assert "tkinter" in code


def test_spec_data_dirs_never_include_private():
    """DATA_DIRS 是随包数据的白名单——`_private` 不在其中。"""
    code = _spec_code()
    assert "DATA_DIRS" in code
    for name in redline.EMBEDDED_DIRS:
        assert '"{}"'.format(name) in code
    assert "_private" not in code


# ---- 中立目录验证工具 ----


def test_neutral_env_strips_path():
    """剥离 PATH：验证 exe 不依赖开发环境的 Python/脚本目录。"""
    env = neutral._clean_env()
    assert env.get("PATH") == ""
    assert "TAW_DATA_DIR" not in env


def test_neutral_cases_are_exactly_the_five_commanded(tmp_path, monkeypatch):
    """五连的**命令清单**钉死（DoD 逐条对账，改清单 = 改验收口径）。"""
    recorded = []

    def fake_run_case(label, argv, **kwargs):
        recorded.append((label, argv))
        return {"label": label, "argv": argv, "returncode": 0, "ok": True,
                "expect": 0, "stdout_tail": "", "stderr_tail": ""}

    monkeypatch.setattr(neutral, "run_case", fake_run_case)
    dist, _data = _make_fake_dist(tmp_path)
    repo = _make_repo_data(tmp_path)
    result = neutral.verify(dist, repo, neutral_dir=tmp_path / "neutral")
    labels = [c[0] for c in recorded]
    assert labels == ["selfcheck", "demo", "parse", "audit refs", "audit bench --line all"]
    assert result["ok"] is True
    # 命令本身仍走真实子命令名（防只在 label 上做文章）
    assert [c[1][1] for c in recorded] == ["selfcheck", "demo", "parse", "audit", "audit"]


def test_neutral_run_case_uses_real_returncode(tmp_path):
    """退出码取真实 `returncode`（不接管道）：非零会如实判 fail。"""
    exe = sys.executable
    ok = neutral.run_case("ok", [exe, "-c", "import sys; sys.exit(0)"])
    bad = neutral.run_case("bad", [exe, "-c", "import sys; sys.exit(1)"])
    assert ok["ok"] is True and ok["returncode"] == 0
    assert bad["ok"] is False and bad["returncode"] == 1


def test_neutral_verify_copies_outside_repo(tmp_path, monkeypatch):
    """dist 被复制到中立目录后再跑（不在仓库树内验证内嵌数据）。

    假 dist 的 `taw.exe` 是占位字节，真跑会失败，故此处只验**复制布局**，
    执行用 stub 替掉（真实执行由 `tools/verify_neutral_dir.py` 在真 dist 上跑）。
    """
    monkeypatch.setattr(neutral, "run_case", lambda label, argv, **kw: {
        "label": label, "argv": argv, "returncode": 0, "ok": True,
        "expect": 0, "stdout_tail": "", "stderr_tail": ""})
    dist, _data = _make_fake_dist(tmp_path)
    repo = _make_repo_data(tmp_path)
    neutral_dir = tmp_path / "outside"
    result = neutral.verify(dist, repo, neutral_dir=neutral_dir)
    assert result["ok"] is True
    assert (neutral_dir / "taw" / "taw.exe").is_file()
    assert (neutral_dir / "taw" / "data" / "README.md").is_file()
    # 中立目录必须在仓库树之外
    assert REPO_ROOT not in neutral_dir.resolve().parents
