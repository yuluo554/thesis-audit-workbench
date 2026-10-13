# -*- coding: utf-8 -*-
"""构建红线扫描与内嵌数据对账（M6 DoD：dist 无禁区成分 + 内嵌数据对账）。

三个独立检查，任何一个失败都以**非零退出码**收场（构建收尾必跑）：

1. `scan_dist_forbidden`：扫描 dist 目录**文件名**，命中禁区成分即失败——
   含 `_private/`、`.db`/`.sqlite`、`.env`/`.key` 与真实学校/人名关键词；
2. `reconcile_embedded_data`：exe 内嵌数据与仓库 `data/` **逐文件对账**
   （相对路径集合一致 + 逐字节一致）——防"打进去了但打的是旧版/漏文件"；
3. `assert_redline`：两者合并的收口断言，返回结构化结果供测试与 CLI 复用。

红线口径来自 plan/03 §五第 9 条与 plan/00 D-1/D-2：发布产物不得含私有材料、
数据库、密钥与真实机构/人员信息（合成数据一律标"虚构"）。
"""

import hashlib
import json
from pathlib import Path

# 禁区成分（按**路径片段**匹配，大小写不敏感）
FORBIDDEN_PATH_PARTS = ("_private",)
FORBIDDEN_FILENAMES = (".env",)
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".key")

# 真实机构/人名关键词黑名单。
# 注意：**合成数据里出现的"虚构理工大学""李虚构"等不在黑名单**——那是虚构值，
# 正是为了可辨识而造的；黑名单只钉真实实体名（示例：本机用户名/真实校名）。
REAL_NAME_BLOCKLIST = ("yuluo554", "asus")

# 内嵌数据必须覆盖的目录（与 spec 的 DATA_DIRS 一致）
EMBEDDED_DIRS = ("frozen", "bench", "knowledge", "rulesets")

# 不进对账的目录（运行产物 / 私有件）
SKIP_DIRS = {"_private", "__pycache__"}


def _sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_files(root, skip_dirs=SKIP_DIRS):
    """root 下的相对路径 → 绝对路径（跳过 skip_dirs）。"""
    root = Path(root)
    out = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        out[rel.as_posix()] = p
    return out


def scan_dist_forbidden(dist_dir):
    """扫描 dist 目录 → {ok, offenders}（文件名/路径级红线）。"""
    dist_dir = Path(dist_dir)
    offenders = []
    if not dist_dir.is_dir():
        return {"ok": False, "offenders": [{"path": str(dist_dir), "reason": "dist 目录不存在"}]}
    for p in sorted(dist_dir.rglob("*")):
        rel = p.relative_to(dist_dir).as_posix()
        low = rel.lower()
        if not p.is_file():
            continue
        for part in FORBIDDEN_PATH_PARTS:
            if part in low.split("/"):
                offenders.append({"path": rel, "reason": "禁区目录/文件：{}".format(part)})
        if low.rsplit("/", 1)[-1] in FORBIDDEN_FILENAMES:
            offenders.append({"path": rel, "reason": "禁区文件名：{}".format(low.rsplit("/", 1)[-1])})
        if low.endswith(FORBIDDEN_SUFFIXES):
            offenders.append({"path": rel, "reason": "禁区后缀：{}".format(Path(low).suffix)})
        for name in REAL_NAME_BLOCKLIST:
            if name in low:
                offenders.append({"path": rel, "reason": "真实实体关键词：{}".format(name)})
    return {"ok": not offenders, "offenders": offenders}


def find_embedded_data_root(dist_dir):
    """在 dist 里定位内嵌数据根（PyInstaller 6: `_internal/data`；5: `<exe>/data`）。

    onedir 下 `paths.py` 走的是 `exe目录/_internal/data` 分支；同时兼容
    旧布局，返回第一个含 `README.md` 标志的候选。
    """
    dist_dir = Path(dist_dir)
    candidates = [
        dist_dir / "taw" / "_internal" / "data",
        dist_dir / "taw" / "data",
        dist_dir / "_internal" / "data",
        dist_dir / "data",
    ]
    for c in candidates:
        if (c / "README.md").is_file():
            return c
    return None


def reconcile_embedded_data(dist_dir, repo_data_dir):
    """内嵌数据 vs 仓库 data/ **逐文件对账**（只比对 EMBEDDED_DIRS）。"""
    embedded_root = find_embedded_data_root(dist_dir)
    if embedded_root is None:
        return {"ok": False, "reason": "未在 dist 中找到内嵌数据根（缺 README.md 标志）",
                "root": None, "missing": [], "extra": [], "mismatched": []}

    repo_data_dir = Path(repo_data_dir)
    missing, extra, mismatched = [], [], []

    for sub in EMBEDDED_DIRS:
        repo_files = _rel_files(repo_data_dir / sub)
        emb_files = _rel_files(embedded_root / sub)
        for rel in sorted(repo_files):
            if rel not in emb_files:
                missing.append("{}/{}".format(sub, rel))
            elif _sha256(repo_files[rel]) != _sha256(emb_files[rel]):
                mismatched.append("{}/{}".format(sub, rel))
        for rel in sorted(emb_files):
            if rel not in repo_files:
                extra.append("{}/{}".format(sub, rel))

    ok = not (missing or extra or mismatched)
    return {"ok": ok, "root": str(embedded_root), "missing": missing,
            "extra": extra, "mismatched": mismatched, "reason": None if ok else "内嵌数据与仓库不一致"}


def assert_redline(dist_dir, repo_data_dir, out_json=None):
    """构建红线总收口：禁区扫描 + 内嵌数据对账 → {ok, forbidden, data}。"""
    forbidden = scan_dist_forbidden(dist_dir)
    data = reconcile_embedded_data(dist_dir, repo_data_dir)
    result = {"ok": bool(forbidden["ok"] and data["ok"]),
              "forbidden": forbidden, "data": data}
    if out_json:
        p = Path(out_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8")
    return result


def _repo_root():
    return Path(__file__).resolve().parents[2]


def main(argv=None):
    """CLI：`python tools/check_build_redline.py <dist_dir> [--json out.json]`。

    退出码：0=红线全过；1=有违例（打印明细）。
    """
    import argparse

    from _console import ensure_utf8_stdout

    ensure_utf8_stdout()      # 非 UTF-8 控制台（Windows CI cp1252）打印中文不再崩
    parser = argparse.ArgumentParser(description="构建红线扫描与内嵌数据对账（M6 DoD）")
    parser.add_argument("dist_dir", help="PyInstaller dist 目录（含 taw/ onedir）")
    parser.add_argument("--data-dir", default=None, help="仓库数据目录（默认自动定位）")
    parser.add_argument("--json", default=None, help="把结果落盘为 JSON")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir) if args.data_dir else _repo_root() / "data"
    result = assert_redline(args.dist_dir, data_dir, out_json=args.json)

    if result["forbidden"]["ok"]:
        print("[OK] 禁区成分扫描：0 命中")
    else:
        print("[FAIL] 禁区成分扫描：{} 命中".format(len(result["forbidden"]["offenders"])))
        for off in result["forbidden"]["offenders"][:20]:
            print("   - {}: {}".format(off["path"], off["reason"]))

    data = result["data"]
    if data["ok"]:
        print("[OK] 内嵌数据对账：{} 逐文件一致".format(data["root"]))
    else:
        print("[FAIL] 内嵌数据对账：{}".format(data["reason"]))
        for key in ("missing", "extra", "mismatched"):
            for item in data.get(key, [])[:20]:
                print("   - {}: {}".format(key, item))

    print("结果: {}".format("PASS" if result["ok"] else "FAIL"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
