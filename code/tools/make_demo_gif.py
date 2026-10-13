# -*- coding: utf-8 -*-
"""生成 M6 演示 GIF：离屏/原生渲染 PySide6 窗口，逐帧抓图合成 GIF（plan/05 M6 可演示物）。

用途：M6 DoD 的"可演示物 = exe + 演示 GIF"。脚本**不改任何判定**——只驱动
`taw.gui` 的既有槽函数（选文件 → 跑审计 → 选行看证据链 → 切全文线），
把真实窗口逐帧抓下来合成动画。

用法（本机有 PySide6 + Pillow 时）：
    python tools/make_demo_gif.py --out ../reports/demo.gif

CI/无图形环境不跑（运行时依赖 PySide6 + Pillow；产物是运行产物，不入仓）。
"""

import argparse
from pathlib import Path

FONT_HINT = "（若中文渲染为方块，请安装中文字体后重跑）"


def _shots(window, app, out_dir):
    """驱动窗口走一遍主流程，逐帧抓图 → [(png_path, caption)]。"""
    frames = []

    def snap(name):
        for _ in range(6):
            app.processEvents()
        pm = window.grab()
        path = out_dir / "{}.png".format(name)
        pm.save(str(path), "PNG")
        frames.append((path, name))
        return path

    # 帧 1：启动态（数据目录已探明）
    window.show()
    snap("01_start")

    # 帧 2：文献线跑完（findings 表格填充）
    window.tabs.setCurrentIndex(0)
    window.refs_table.setText(str(REFS_TABLE))
    window.refs_body.setText(str(BODY))
    window.run_refs_audit()
    snap("02_refs_audit")

    # 帧 3：选中一行 → 详情面板出证据链
    if window.refs_view.row_count():
        window.refs_view.table.selectRow(0)
        window.refs_view._on_select()
    snap("03_evidence")

    # 帧 4：全文线跑完
    window.tabs.setCurrentIndex(1)
    window.full_docx.setText(str(THESIS_DOCX))
    window.run_full_audit()
    snap("04_full_audit")

    # 帧 5：全文线选中一行看证据链
    if window.full_view.row_count():
        window.full_view.table.selectRow(0)
        window.full_view._on_select()
    snap("05_full_evidence")
    return frames


def build_gif(frames, out_path, duration_ms=1400, max_width=1180):
    """把 PNG 帧合成 GIF（等比缩放到 max_width，Pillow 去重调色板）。"""
    from PIL import Image

    images = []
    for path, _name in frames:
        img = Image.open(str(path)).convert("RGB")
        if img.width > max_width:
            h = int(img.height * max_width / img.width)
            img = img.resize((max_width, h), Image.LANCZOS)
        images.append(img)

    # 统一到最小尺寸（各帧窗口尺寸应一致，防御性裁剪/填充）
    w = min(i.width for i in images)
    h = min(i.height for i in images)
    images = [i.resize((w, h), Image.LANCZOS) for i in images]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(str(out_path), save_all=True, append_images=images[1:],
                   duration=duration_ms, loop=0, optimize=True)
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成 M6 GUI 演示 GIF")
    parser.add_argument("--out", default="../reports/demo.gif", help="GIF 输出路径")
    parser.add_argument("--keep-frames", action="store_true", help="保留中间 PNG 帧")
    args = parser.parse_args(argv)

    global REFS_TABLE, BODY, THESIS_DOCX
    repo_root = Path(__file__).resolve().parents[2]
    REFS_TABLE = repo_root / "data" / "frozen" / "audit" / "refs_table.txt"
    BODY = repo_root / "data" / "frozen" / "audit" / "body.txt"
    THESIS_DOCX = repo_root / "data" / "frozen" / "thesis" / "thesis_synthetic.docx"

    from taw.gui import app as gui_app

    out_path = Path(args.out)
    frame_dir = out_path.parent / (out_path.stem + "_frames")
    frame_dir.mkdir(parents=True, exist_ok=True)

    app, window = gui_app.build_app([])
    window.setWindowTitle("毕业论文全流程审计工作台 —— 演示")
    frames = _shots(window, app, frame_dir)
    gif = build_gif(frames, out_path)
    print("GIF -> {}（{} 帧，{} 字节）".format(gif, len(frames), gif.stat().st_size))
    if not args.keep_frames:
        for path, _ in frames:
            path.unlink()
        try:
            frame_dir.rmdir()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
