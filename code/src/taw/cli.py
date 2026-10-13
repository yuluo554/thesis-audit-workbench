"""taw 命令行入口——CLI 是单一事实源（GUI 只消费引擎 API，见 plan/03）。

CLI 契约（tests/test_cli.py 锁定，改动 = 口径变更须记决策）：
- 退出码 0 = 完成；1 = 降级完成（如数据目录缺失，仍输出可用信息）；
- 退出码 2 = 用法/输入错误（argparse 原生错误亦为 2）；
- 无子命令时打印帮助并返回 0（信息性，非错误）。
"""

import argparse
import importlib.util
import json
import platform
import sys
from pathlib import Path

from taw import __version__, registry
from taw.paths import find_data_dir_details

EXIT_OK = 0
EXIT_DEGRADED = 1
EXIT_USAGE = 2

# 可选依赖探测（find_spec 只查存在性，不触发重导入）；M0 未装属正常，只报告不改退出码
OPTIONAL_DEPS = [
    ("docx", "python-docx", "M2 docx 解析与批注回写"),
    ("pyvis", "pyvis", "M3 论证链拓扑可视化"),
    ("PySide6", "PySide6", "M6 桌面 GUI"),
    ("win32com", "pywin32", "M6 Word/WPS COM 联动"),
]


def build_parser():
    parser = argparse.ArgumentParser(
        prog="taw",
        description="毕业论文全流程审计工作台（文献审计线 + 全文审计线）",
    )
    parser.add_argument("--version", action="version", version="taw " + __version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("selfcheck", help="环境自检：版本 / 数据目录 / 可选依赖")
    sub.add_parser("demo", help="打印 16 模块注册表（进度跟踪）")
    gui_p = sub.add_parser("gui", help="启动 PySide6 桌面窗口（extras gui；只消费引擎 API）")
    gui_p.add_argument("--check", action="store_true",
                       help="只构造离屏窗口做启动自检（CI/无桌面环境用），不进事件循环")
    parse_p = sub.add_parser("parse", help="解析文献表 / 论文 docx（REF-01 与论文解析器）")
    parse_p.add_argument("paths", nargs="*", help="待解析文件（文献表 txt/csv/bib/ris，或论文 docx）")
    parse_p.add_argument("--format", choices=["auto", "txt", "csv", "bib", "ris"],
                         default="auto", help="文献表格式（默认按扩展名探测）")
    parse_p.add_argument("--json", action="store_true", help="以 JSON 输出解析结果")
    parse_p.add_argument("--summary", action="store_true",
                         help="打印解析概览（条目数 / 字段填充率 / 对象与标记计数）")
    audit_p = sub.add_parser("audit", help="审计：文献线全链（REF-02..09）与基准")
    audit_sub = audit_p.add_subparsers(dest="audit_target")
    refs_p = audit_sub.add_parser("refs", help="文献线全链审计（核查/对账/去重/画像/推荐/拓扑）")
    refs_p.add_argument("table", help="文献表文件（txt/csv/bib/ris）")
    refs_p.add_argument("--body", default=None,
                        help="正文文件（启用 REF-04 对账 / REF-07 推荐 / REF-08 拓扑）")
    refs_p.add_argument("--json", action="store_true", help="以 JSON 输出审计结果")
    refs_p.add_argument("--report", default=None, help="把审计结果落盘到该 JSON 路径")
    refs_p.add_argument("--topology", default=None,
                        help="把 0 外链拓扑 HTML 落盘到该路径（需给 --body）")
    refs_p.add_argument("--library", default=None,
                        help="本地文献库 SQLite 路径（入库并给复用提示）")
    refs_p.add_argument("--standard-year", default="2025", choices=["2015", "2025"],
                        help="双标尺：按哪一版国标判定（默认 2025 现行版）")
    refs_p.add_argument("--profile", default="default", help="规则 profile（默认 default）")
    bench_p = audit_sub.add_parser("bench", help="内置基准（文献线 9 指标 / 全文线 5 指标）")
    bench_p.add_argument("--line", choices=["refs", "full", "all"], default="refs",
                         help="基准线：refs=文献线 9 指标 / full=全文线 5 指标 / all=两线")
    bench_p.add_argument("--json", action="store_true", help="以 JSON 输出指标表")
    bench_p.add_argument("--report", default=None, help="把基准报告落盘到该 JSON 路径")
    thesis_p = audit_sub.add_parser(
        "thesis", help="全文线全链审计（交叉引用/学校格式/术语数字/AIGC/综述/结构）")
    thesis_p.add_argument("docx", help="论文 docx 文件")
    thesis_p.add_argument("--data-dir", default=None, help="数据目录（默认按 paths 五分支定位）")
    thesis_p.add_argument("--json", action="store_true", help="以 JSON 输出审计结果")
    thesis_p.add_argument("--report", default=None, help="把审计结果落盘到该 JSON 路径")
    thesis_p.add_argument("--standard-year", default="2025", choices=["2015", "2025"],
                          help="双标尺：按哪一版国标判定（默认 2025 现行版）")
    thesis_p.add_argument("--profile", default="default",
                          help="规则 profile（默认 default；学校模板用 school-<校名>）")
    thesis_p.add_argument("--no-review", action="store_true",
                          help="跳过 FULL-05 综述辅助（不消费库内语料）")
    thesis_p.add_argument("--review-topology", default=None,
                          help="把综述聚类 0 外链 HTML 落盘到该路径（需库内语料）")
    return parser


def _probe_optional_deps():
    lines = []
    for module_name, dist_name, purpose in OPTIONAL_DEPS:
        state = "已装" if importlib.util.find_spec(module_name) else "未装"
        lines.append("  [{}] {:<12} {}".format(state, dist_name, purpose))
    return lines


def _parse_one(path, fmt):
    """单文件解析 → (kind, payload)；文件不存在/格式不支持抛 ValueError。"""
    p = Path(str(path))
    if not p.is_file():
        raise ValueError("文件不存在：{}".format(p))
    suffix = p.suffix.lower()
    if suffix == ".docx":
        from taw import thesisparse
        return "thesis", thesisparse.parse_thesis(p)
    from taw import refparse
    use_fmt = None if fmt == "auto" else fmt
    fmt_name, cards = refparse.parse_file(p, fmt=use_fmt)
    return fmt_name, cards


def _ref_summary(cards):
    """文献卡片概览：条目数 / 字段填充率 / flag 分布 / 平均置信度。"""
    n = len(cards)
    fields = ("title", "year", "container", "pages")
    fill = {f: 0 for f in fields}
    for c in cards:
        if c["title"]:
            fill["title"] += 1
        for f in ("year", "container", "pages"):
            if c["source"].get(f):
                fill[f] += 1
    flags = {}
    for c in cards:
        for fl in c["flags"]:
            flags[fl] = flags.get(fl, 0) + 1
    conf = sum(c["confidence"] for c in cards) / n if n else 0.0
    return {"entries": n, "field_fill": fill, "flags": flags,
            "mean_confidence": round(conf, 4)}


def _thesis_summary(parsed):
    return {"paragraphs": len(parsed["style_tree"]),
            "fields": len(parsed["fields"]),
            "objects": len(parsed["objects"]),
            "markers": len(parsed["markers"]),
            "dangling": len(parsed["dangling"]),
            "ghosts": len(parsed["ghosts"])}


def cmd_parse(args):
    """taw parse：解析文献表/论文 → 概览或 JSON。

    退出码：0=全部解析成功；1=降级（部分文件失败或 docx 依赖缺失）；
    2=用法错误（无路径 / 所有文件失败）。
    """
    if not args.paths:
        print("用法错误：parse 需要至少一个文件路径（文献表 txt/csv/bib/ris 或论文 docx）")
        return EXIT_USAGE
    results = {}
    failed = []
    for path in args.paths:
        try:
            kind, payload = _parse_one(path, args.format)
        except RuntimeError as exc:  # docx 缺装等环境问题 → 降级
            failed.append((path, str(exc)))
            continue
        except (ValueError, OSError) as exc:
            failed.append((path, str(exc)))
            continue
        results[path] = (kind, payload)

    if not results and failed:
        for path, err in failed:
            print("[失败] {} -> {}".format(path, err))
        return EXIT_USAGE

    if args.json:
        out = {}
        for path, (kind, payload) in results.items():
            if kind == "thesis":
                out[path] = {"kind": "thesis", "result": payload}
            else:
                out[path] = {"kind": "refs", "format": kind, "cards": payload}
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        for path, (kind, payload) in results.items():
            if kind == "thesis":
                s = _thesis_summary(payload)
                print("{} [docx] 段 {} / 域 {} / 对象 {} / 标记 {} / 悬空 {} / 幽灵 {}".format(
                    path, s["paragraphs"], s["fields"], s["objects"], s["markers"],
                    s["dangling"], s["ghosts"]))
            else:
                s = _ref_summary(payload)
                print("{} [{}] 条目 {} 均置信度 {} 填充 {}".format(
                    path, kind, s["entries"], s["mean_confidence"], s["field_fill"]))
    for path, err in failed:
        print("[失败] {} -> {}".format(path, err))
    return EXIT_DEGRADED if failed else EXIT_OK


def cmd_audit(args):
    """taw audit refs|thesis|bench：文献线/全文线审计与基准。

    退出码：0=完成（含"跑通但检出问题"——检出非错误）；1=降级（数据目录缺失等）；
    2=用法/输入错误（缺路径、文件不存在）。
    """
    target = args.audit_target
    if target == "refs":
        return _audit_refs(args)
    if target == "thesis":
        return _audit_thesis(args)
    if target == "bench":
        return _audit_bench(args)
    print("用法错误：audit 需要子命令 refs、thesis 或 bench")
    return EXIT_USAGE


def _data_dir_or_degrade():
    try:
        data_dir, _src = find_data_dir_details()
    except FileNotFoundError as exc:
        print("数据目录配置错误：{}".format(exc))
        return None, False
    return data_dir, data_dir is not None


def _note(args, text):
    """辅助信息：--json 时走 stderr，保证 stdout 是纯 JSON（可机器解析）。"""
    if getattr(args, "json", False):
        print(text, file=sys.stderr)
    else:
        print(text)


def _audit_refs(args):
    from taw import refaudit
    try:
        report = refaudit.audit_refs(
            args.table, body_path=args.body, data_dir=_data_dir_or_degrade()[0],
            standard_year=args.standard_year, profile=args.profile)
    except (ValueError, OSError) as exc:
        print("失败：{}".format(exc))
        return EXIT_USAGE

    if args.topology:
        if not args.body:
            print("用法错误：--topology 需要同时给 --body")
            return EXIT_USAGE
        try:
            path = refaudit.write_topology(args.table, args.body, args.topology,
                                           report["findings"])
        except (ValueError, OSError) as exc:
            print("拓扑产出失败：{}".format(exc))
            return EXIT_USAGE
        _note(args, "拓扑 HTML（0 外链，已过硬断言）-> {}".format(path))

    if args.library:
        try:
            from taw import reflib, refparse
            _fmt, cards = refparse.parse_file(args.table)
            with reflib.Library(args.library) as lib:
                lib.save(str(args.table), cards, report.get("health_score"))
                stats = lib.stats()
            _note(args, "文献库入库完成：{} 条（去重后 {}）".format(
                stats["total_entries"], stats["distinct_entries"]))
        except (ValueError, OSError, RuntimeError) as exc:
            print("文献库写入失败：{}".format(exc))
            return EXIT_USAGE

    if args.report:
        refaudit.write_report(report, args.report)
        _note(args, "审计报告 -> {}".format(args.report))

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["summary"]
        print("文献线审计：{}（{} 条条目，体检分 {}）".format(
            args.table, report["table"]["entries"], report.get("health_score")))
        print("结论 {}：fail {} / manual_confirm {} / pass {}".format(
            s["total"], s["by_status"].get("fail", 0),
            s["by_status"].get("manual_confirm", 0), s["by_status"].get("pass", 0)))
        for name, info in sorted(report["modules"].items()):
            if "skipped" in info:
                print("  {:<22} 跳过（{}）".format(name, info["skipped"]))
            else:
                print("  {:<22} findings {}".format(name, info.get("findings", 0)))
        print("免责声明：{}".format(report["disclaimers"][0]))
    return EXIT_OK


def _audit_thesis(args):
    from taw import fullaudit
    data_dir = args.data_dir or _data_dir_or_degrade()[0]
    try:
        report = fullaudit.audit_thesis(
            args.docx, data_dir=data_dir, standard_year=args.standard_year,
            profile=args.profile, include_review=not args.no_review)
    except (ValueError, OSError, RuntimeError) as exc:
        print("失败：{}".format(exc))
        return EXIT_USAGE

    if args.report:
        fullaudit.write_report(report, args.report)
        _note(args, "全文线审计报告 -> {}".format(args.report))

    if args.review_topology:
        entries = fullaudit._load_review_entries(data_dir)
        if not entries:
            print("用法错误：--review-topology 需要库内综述语料（data/frozen/review/）")
            return EXIT_USAGE
        try:
            from taw import reviewcl
            html_text = reviewcl.render_review_html(entries)
            from pathlib import Path
            p = Path(args.review_topology)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(html_text, encoding="utf-8")
            _note(args, "综述聚类 HTML（0 外链，已过硬断言）-> {}".format(p))
        except (ValueError, OSError) as exc:
            print("综述可视化产出失败：{}".format(exc))
            return EXIT_USAGE

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        s = report["summary"]
        d = report["doc"]
        print("全文线审计：{}（{} 段，对象 {}，标记 {}）".format(
            d["path"], d["paragraphs"], d["objects"], d["markers"]))
        print("结论 {}：fail {} / manual_confirm {} / pass {}".format(
            s["total"], s["by_status"].get("fail", 0),
            s["by_status"].get("manual_confirm", 0), s["by_status"].get("pass", 0)))
        for name, info in sorted(report["modules"].items()):
            if "skipped" in info:
                print("  {:<22} 跳过（{}）".format(name, info["skipped"]))
            else:
                extra = ""
                if name == "FULL-05-review":
                    extra = " 簇 {} 纯度 {}".format(info.get("clusters"), info.get("purity"))
                elif name == "FULL-04-aigc":
                    extra = " 命中段 {}".format(
                        info.get("distribution", {}).get("paragraphs_flagged"))
                print("  {:<22} findings {}{}".format(name, info.get("findings", 0), extra))
        print("免责声明：{}".format(report["disclaimers"][0]))
        print("AIGC 伦理边界：{}".format(fullaudit.aigccheck.ETHICS_STATEMENT))
    return EXIT_OK


def _audit_bench(args):
    from taw import fullbench, refbench
    data_dir, ok = _data_dir_or_degrade()
    if not ok:
        print("基准需要数据目录（data/frozen/ + data/bench/），当前不可用")
        return EXIT_DEGRADED
    line = getattr(args, "line", "refs")
    if line == "refs":
        result = refbench.run(data_dir)
    elif line == "full":
        result = fullbench.run(data_dir)
    else:
        result = {"refs": refbench.run(data_dir), "full": fullbench.run(data_dir)}

    if args.report:
        _write_bench(result, args.report)
        _note(args, "基准报告 -> {}".format(args.report))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif line == "refs":
        _print_ref_bench(result)
    elif line == "full":
        _print_full_bench(result)
    else:
        _print_ref_bench(result["refs"])
        print("")
        _print_full_bench(result["full"])
    return EXIT_OK


def _write_bench(result, path):
    from pathlib import Path
    p = Path(str(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p


def _print_ref_bench(result):
    m = result["metrics"]
    print("文献线 9 指标（零 API 依赖）:")
    pf = m["1_parse_f1"]
    print("  1 分层解析 F1        clean/light/heavy 门槛: {}".format(pf["gate"]))
    fd = m["2_format_detection"]
    print("  2 格式检出/误报      P={} R={} F1={} FP={}（clean FP={}）".format(
        fd["precision"], fd["recall"], fd["f1"], fd["fp"], fd["clean_fp"]))
    fx = m["3_fix_accuracy"]
    print("  3 修正准确率         {}/{} = {}".format(fx["resolved"], fx["total_fixes"], fx["accuracy"]))
    print("  4 对账准确率         {}".format(m["4_citation_reconcile"]["accuracy"]))
    dd = m["5_dedup_pr"]
    print("  5 去重 P/R           P={} R={} 误合并率={}".format(
        dd["precision"], dd["recall"], dd["false_merge_rate"]))
    h = m["6_hallucination"]
    print("  6 幻觉画像检出率     {}（genuine 误报 {}）".format(h["detection_rate"], h["genuine_false_positive"]))
    print("  7 双标尺差异检出率   {}".format(m["7_standard_currency"]["detection_rate"]))
    rc = m["8_recommend"]
    print("  8 推荐 Recall@{} / MRR  {} / {}".format(rc["k"], rc["recall_at_k"], rc["mrr"]))
    rn = m["9_renumber_consistency"]
    print("  9 编号重排一致性     {}/{} = {}".format(rn["passed"], rn["cases"], rn["consistency"]))
    print("守门: {}".format("全过" if result["gate"]["all_pass"] else result["gate"]))


def _print_full_bench(result):
    m = result["metrics"]
    print("全文线 5 指标（零 API 依赖）:")
    x = m["1_xref_detection"]
    print("  1 悬空/幽灵检出      dangling {} / ghost {}，重排一致性 {}".format(
        sum(1 for h in x["dangling_hits"] if h["found"]), sum(1 for h in x["ghost_hits"] if h["found"]),
        x["renumber"]["consistency"]))
    s = m["2_style_check"]
    print("  2 样式核查检出/误报  TP={} FP={} recall={}".format(s["tp"], s["fp"], s["recall"]))
    t = m["3_term_consistency"]
    print("  3 术语一致性检出     TP={} FN={} recall={}（数字写法问题 {}）".format(
        t["tp"], t["fn"], t["recall"], len(t["number_issues"])))
    a = m["4_aigc_detection"]
    print("  4 AIGC 植入检出      TP={} FP={}（伦理守卫 {}）".format(
        a["tp"], a["fp"], a["gate"]["ethics_asserted"]))
    rv = m["5_review_cluster"]
    print("  5 综述聚类/预分组    簇 {} 纯度 {} / 空白命中 {}".format(
        rv["clusters"], rv["purity"], rv["gap_groups"]))
    print("守门: {}".format("全过" if result["gate"]["all_pass"] else result["gate"]))


def cmd_selfcheck(_args):
    print("taw {} (thesis-audit-workbench)".format(__version__))
    print("Python {}.{}.{} ({})".format(sys.version_info[0], sys.version_info[1], sys.version_info[2], platform.platform()))
    try:
        data_dir, source = find_data_dir_details()
    except FileNotFoundError as exc:
        print("数据目录: 配置错误 -> {}".format(exc))
        print("结果: DEGRADED")
        return EXIT_DEGRADED
    if data_dir is None:
        print("数据目录: 未找到（降级运行；数据依赖类命令不可用）")
        exit_code = EXIT_DEGRADED
    else:
        print("数据目录: {} (来源: {})".format(data_dir, source))
        exit_code = EXIT_OK
    print("可选依赖（M0 未装属正常）:")
    for line in _probe_optional_deps():
        print(line)
    print("模块注册: {} 项（{}）".format(registry.total(), registry.counts()))
    print("结果: {}".format("OK" if exit_code == EXIT_OK else "DEGRADED"))
    return exit_code


def _data_face_lines():
    """数据面展示：目录命中情况 + 冻结 fixtures 计数（M1 数据面可演示物）。"""
    try:
        data_dir, _source = find_data_dir_details()
    except FileNotFoundError as exc:
        return ["数据目录: 配置错误 -> {}（演示不受影响）".format(exc)]
    if data_dir is None:
        return ["数据目录: 未找到（演示不受影响）"]
    lines = ["数据目录: {}".format(data_dir)]
    refs = data_dir / "frozen" / "refs"
    thesis = data_dir / "frozen" / "thesis"
    audit = data_dir / "frozen" / "audit"
    review = data_dir / "frozen" / "review"
    hallu = data_dir / "bench" / "halluref" / "halluref_v1.jsonl"
    n_refs = len([p for p in refs.iterdir() if p.is_file()]) if refs.is_dir() else 0
    n_thesis = len([p for p in thesis.iterdir() if p.is_file()]) if thesis.is_dir() else 0
    n_audit = len([p for p in audit.iterdir() if p.is_file()]) if audit.is_dir() else 0
    n_review = len([p for p in review.iterdir() if p.is_file()]) if review.is_dir() else 0
    lines.append("冻结数据面: refs {} 文件 / thesis {} 文件 / audit {} 文件 / review {} 文件"
                 "（data/frozen/，位级一致守门）".format(n_refs, n_thesis, n_audit, n_review))
    if hallu.is_file():
        n_hallu = len([ln for ln in hallu.read_text(encoding="utf-8").splitlines() if ln.strip()])
        lines.append("HalluRef-Bench: v1 {} 条（bench/halluref/，固定 seed 位级一致）".format(n_hallu))
    return lines


def cmd_demo(_args):
    for line in _data_face_lines():
        print(line)
    print("模块注册表（{} 项，{}）:".format(registry.total(), registry.counts()))
    for mod in registry.MODULES:
        print(
            "  {:<8} [{}] {:<28} 计划:{}  状态:{}".format(
                mod["id"], registry.LINE_NAMES[mod["line"]], mod["name"],
                mod["milestone"], mod["status"],
            )
        )
    return EXIT_OK


def cmd_gui(args):
    """taw gui：启动 PySide6 桌面窗口（extras gui）。

    退出码：0=正常退出（含 --check 构造成功）；1=降级（PySide6 缺装）。
    --check 只构造离屏窗口即返回（CI/无桌面环境冒烟），不进事件循环。
    """
    try:
        from taw.gui import app as gui_app
    except ImportError as exc:
        print("GUI 需要 gui extras：python -m pip install -e './code[gui]'（{}）".format(exc))
        return EXIT_DEGRADED
    if getattr(args, "check", False):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _app, window = gui_app.build_app([])
        print("GUI 启动自检通过：{}".format(window.windowTitle()))
        return EXIT_OK
    return gui_app.main([])


def _ensure_utf8_stdout():
    """非 UTF-8 stdout（Windows CI 管道的 cp1252 等）会把中文输出打成 UnicodeEncodeError。

    处置：能 reconfigure 就切成 UTF-8；不能（被重定向的旧式流）则退化为
    `errors="replace"`——宁可显示成替换字符，也不让整条命令崩在打印上。
    `PYTHONIOENCODING` 已指定 Unicode 编码时不动（尊重调用方）。
    """
    import io
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
        # 兜底：包一层可替换错误的写流
        try:
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                setattr(sys, name, io.TextIOWrapper(
                    buffer, encoding="utf-8", errors="replace", line_buffering=True))
        except (ValueError, OSError, AttributeError):
            pass


def main(argv=None):
    _ensure_utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "selfcheck":
        return cmd_selfcheck(args)
    if args.command == "demo":
        return cmd_demo(args)
    if args.command == "gui":
        return cmd_gui(args)
    if args.command == "parse":
        return cmd_parse(args)
    if args.command == "audit":
        return cmd_audit(args)
    parser.print_help()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
