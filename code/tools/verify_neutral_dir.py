# -*- coding: utf-8 -*-
"""中立目录干净验证（M6 DoD「扩展清单」）——把 dist 复制到**仓库树外**，剥离 PATH 跑 CLI。

为什么必须这样验（plan/03 §五第 9 条）：在仓库树内跑 exe 会因 CWD 上溯命中
仓库自己的 `data/` 而"看起来正常"，掩盖"内嵌数据没打进去"的真问题；剥掉 PATH
则顺带证明 exe 不依赖开发环境的 Python/脚本目录。

九条命令（逐条取**真实退出码**；覆盖 CLI 主路径 + 两个拓扑产物 + GUI 自检）：
1. `selfcheck`（必 0：数据目录命中 + 依赖探测）
2. `demo`（必 0：16 模块注册表）
3. `parse <bib>`（必 0）
4. `audit refs <table> --body <body>`（必 0：跑通，含检出问题）
5. `audit refs ... --topology <out>`（必 0：REF-08 论证链拓扑，内置降级渲染器）
6. `audit thesis <docx> --report <out>`（必 0：全文线主路径）
7. `audit thesis <docx> --review-topology <out>`（必 0：FULL-05 综述可视化）
8. `audit bench --line all`（必 0：两线 14 指标全过）
9. `gui --check`（必 0：gui extras 与 Qt 平台插件可用）

**退出码采集纪律**：每条命令单独 `subprocess.run` 并读 `returncode`，
不接管道（管道会吞掉真实状态，`PIPESTATUS` 在 Windows 上也不适用）。

用法：`python tools/verify_neutral_dir.py <dist_dir> [--data-src <repo data>]`
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _exe(dist_dir, name):
    p = Path(dist_dir) / (name + (".exe" if os.name == "nt" else ""))
    return str(p)


def _clean_env():
    """剥离 PATH 的环境（防误用系统 Python/脚本目录；保留 Windows 必需项）。"""
    env = dict(os.environ)
    keep = {}
    for key in ("SYSTEMROOT", "windir", "TEMP", "TMP", "SystemDrive",
                "PROGRAMDATA", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
                "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "COMSPEC"):
        if key in env:
            keep[key] = env[key]
    keep["PATH"] = ""                     # 显式清空，验证不依赖外部可执行
    # GUI 自检在无显示器的 runner/CI 上走离屏平台插件
    keep["QT_QPA_PLATFORM"] = "offscreen"
    # 防 exe 从别处探到数据（本次要验的就是"内嵌数据"）
    keep.pop("TAW_DATA_DIR", None)
    env.update(keep)
    for key in list(env):
        if key not in keep:
            env.pop(key, None)
    return env


def run_case(label, argv, expect=0, cwd=None, env=None, timeout=300):
    """跑一条命令 → {label, argv, returncode, ok, stdout_tail}（不接管道）。"""
    proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                          timeout=timeout)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace")
    return {
        "label": label,
        "argv": argv,
        "returncode": proc.returncode,
        "ok": proc.returncode == expect,
        "expect": expect,
        "stdout_tail": "\n".join(out.strip().splitlines()[-6:]),
        "stderr_tail": "\n".join(err.strip().splitlines()[-4:]),
    }


def verify(dist_dir, data_src, neutral_dir=None):
    """复制 dist 到中立目录并跑扩展清单 → {ok, neutral_dir, cases}。"""
    dist_dir = Path(dist_dir).resolve()
    data_src = Path(data_src).resolve()
    bundle = dist_dir / "taw" if (dist_dir / "taw").is_dir() else dist_dir

    if neutral_dir is None:
        neutral_dir = Path(tempfile.mkdtemp(prefix="taw-neutral-"))
    else:
        neutral_dir = Path(neutral_dir)
        if neutral_dir.exists():
            shutil.rmtree(str(neutral_dir))
        neutral_dir.mkdir(parents=True)
    target = neutral_dir / "taw"
    shutil.copytree(str(bundle), str(target))

    exe = _exe(target, "taw")
    env = _clean_env()
    cases = []
    refs_table = data_src / "frozen" / "audit" / "refs_table.txt"
    body = data_src / "frozen" / "audit" / "body.txt"
    thesis_docx = data_src / "frozen" / "thesis" / "thesis_synthetic.docx"
    out_topo = str(Path(neutral_dir) / "topo.html")
    out_thesis = str(Path(neutral_dir) / "thesis_report.json")
    out_review = str(Path(neutral_dir) / "review_topology.html")

    cases.append(run_case("selfcheck", [exe, "selfcheck"], cwd=str(neutral_dir), env=env))
    cases.append(run_case("demo", [exe, "demo"], cwd=str(neutral_dir), env=env))
    cases.append(run_case(
        "parse", [exe, "parse", str(data_src / "frozen" / "refs" / "refs_clean.bib")],
        cwd=str(neutral_dir), env=env))
    cases.append(run_case(
        "audit refs",
        [exe, "audit", "refs", str(refs_table), "--body", str(body)],
        cwd=str(neutral_dir), env=env))
    cases.append(run_case(
        "audit refs --topology",
        [exe, "audit", "refs", str(refs_table), "--body", str(body),
         "--topology", out_topo],
        cwd=str(neutral_dir), env=env))
    cases.append(run_case(
        "audit thesis --report",
        [exe, "audit", "thesis", str(thesis_docx), "--report", out_thesis],
        cwd=str(neutral_dir), env=env))
    cases.append(run_case(
        "audit thesis --review-topology",
        [exe, "audit", "thesis", str(thesis_docx), "--profile", "school-demo",
         "--review-topology", out_review],
        cwd=str(neutral_dir), env=env))
    cases.append(run_case(
        "audit bench --line all", [exe, "audit", "bench", "--line", "all"],
        cwd=str(neutral_dir), env=env))
    cases.append(run_case("gui --check", [exe, "gui", "--check"],
                          cwd=str(neutral_dir), env=env))

    return {"ok": all(c["ok"] for c in cases), "neutral_dir": str(neutral_dir),
            "exe": exe, "cases": cases}


def main(argv=None):
    from _console import ensure_utf8_stdout

    ensure_utf8_stdout()      # 非 UTF-8 控制台（Windows CI cp1252）打印中文不再崩
    parser = argparse.ArgumentParser(description="中立目录干净验证（M6 扩展清单）")
    parser.add_argument("dist_dir", help="PyInstaller dist 目录（含 taw/ 或即 taw/）")
    parser.add_argument("--data-src", default=None, help="仓库 data 目录（取测试夹具用）")
    parser.add_argument("--neutral-dir", default=None, help="指定中立目录（默认临时目录）")
    parser.add_argument("--json", default=None, help="结果落盘 JSON")
    args = parser.parse_args(argv)

    data_src = Path(args.data_src) if args.data_src else \
        Path(__file__).resolve().parents[2] / "data"
    result = verify(args.dist_dir, data_src, args.neutral_dir)

    for case in result["cases"]:
        mark = "OK  " if case["ok"] else "FAIL"
        print("[{}] {:<24} exit={} (期望 {})".format(
            mark, case["label"], case["returncode"], case["expect"]))
        if not case["ok"]:
            print("      stdout: {}".format(case["stdout_tail"].replace("\n", " | ")))
            if case["stderr_tail"]:
                print("      stderr: {}".format(case["stderr_tail"].replace("\n", " | ")))
    print("中立目录: {}".format(result["neutral_dir"]))
    print("结果: {}".format("PASS" if result["ok"] else "FAIL"))

    if args.json:
        import json
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
