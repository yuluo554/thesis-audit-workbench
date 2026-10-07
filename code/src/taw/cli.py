"""taw 命令行入口——CLI 是单一事实源（GUI 只消费引擎 API，见 plan/03）。

CLI 契约（tests/test_cli.py 锁定，改动 = 口径变更须记决策）：
- 退出码 0 = 完成；1 = 降级完成（如数据目录缺失，仍输出可用信息）；
- 退出码 2 = 用法/输入错误（argparse 原生错误亦为 2）；
- 无子命令时打印帮助并返回 0（信息性，非错误）。
"""

import argparse
import importlib.util
import platform
import sys

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
    return parser


def _probe_optional_deps():
    lines = []
    for module_name, dist_name, purpose in OPTIONAL_DEPS:
        state = "已装" if importlib.util.find_spec(module_name) else "未装"
        lines.append("  [{}] {:<12} {}".format(state, dist_name, purpose))
    return lines


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
    n_refs = len([p for p in refs.iterdir() if p.is_file()]) if refs.is_dir() else 0
    n_thesis = len([p for p in thesis.iterdir() if p.is_file()]) if thesis.is_dir() else 0
    lines.append("冻结数据面: refs {} 文件 / thesis {} 文件（data/frozen/，位级一致守门）".format(n_refs, n_thesis))
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


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "selfcheck":
        return cmd_selfcheck(args)
    if args.command == "demo":
        return cmd_demo(args)
    parser.print_help()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
