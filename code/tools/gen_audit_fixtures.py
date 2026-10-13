# -*- coding: utf-8 -*-
"""正文引用对账审计夹具生成器（REF-04/05/07 的带真值数据面，确定性）。

产出 `data/frozen/audit/`：
- `refs_table.txt`：顺序编码制文献表（含 1 条重复条目对 + 1 条幽灵条目）；
- `body.txt`：正文（含悬空引用 [99]、乱序首次引用、著者-年份不匹配）；
- `audit_truth.json`：逐项植入真值（悬空/幽灵/乱序/断档/著者年不匹配/重复对）。

设计纪律与 gen_references 一致：固定 seed、无时间戳、两次运行位级一致、无 CR。
内容全部虚构；DOI 用已登记假前缀 10.9999/。
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "code" / "src"))

from taw.rng import SplitMix64  # noqa: E402

SEED = 20261013
SCHEMA_VERSION = 1
DATASET_ID = "refs-audit-v1"
DOI_PREFIX = "10.9999/"

DOC = "虚构场景下的合成数据审计方法研究"

# 文献表：[1]..[9] 顺序编码制。
#   [3]/[4] = **可自动合并**的重复对（DOI 完全相同，标题仅空格伪影差异）；
#   [8]/[9] = **不可自动合并**的疑似对（标题/著者/年份全同，但 DOI 冲突）
#              → 按"误合并率 0"纪律降级 manual_confirm，绝不自动合并；
#   [7]     = 幽灵条目（正文从不引用）。
TABLE = [
    {"no": 1, "authors": "张合成, 李虚构", "title": "虚构场景下的合成数据生成框架",
     "marker": "J", "rest": "虚构学报, 2024, 48(3): 1-12.",
     "year": "2024", "doi": "10.9999/fake.2024.001"},
    {"no": 2, "authors": "王杜撰", "title": "合成数据质量评估综述",
     "marker": "J", "rest": "合成科学进展, 2023, 15(2): 33-45.",
     "year": "2023", "doi": "10.9999/fake.2023.002"},
    {"no": 3, "authors": "SMITH J", "title": "Synthetic Data Methods",
     "marker": "M", "rest": "New York: Fake Academic Press, 2022: 33-45.",
     "year": "2022", "doi": "10.9999/fake.2022.003"},
    {"no": 4, "authors": "SMITH J", "title": "Synthetic Data  Methods",
     "marker": "M", "rest": "New York: Fake Academic Press, 2022: 33-45.",
     "year": "2022", "doi": "10.9999/fake.2022.003"},
    {"no": 5, "authors": "赵虚构", "title": "面向表格数据的扩散模型研究",
     "marker": "D", "rest": "北京: 虚构理工大学, 2024.",
     "year": "2024", "doi": "10.9999/fake.2024.005"},
    {"no": 6, "authors": "国家虚构标准化委员会", "title": "合成数据通用要求: GB/T 99999",
     "marker": "S", "rest": "北京: 虚构出版社, 2025.",
     "year": "2025", "doi": None},
    {"no": 7, "authors": "陈幽灵", "title": "从未被引用的合成数据综述",
     "marker": "J", "rest": "幻想学报, 2021, 9(1): 7-19.",
     "year": "2021", "doi": "10.9999/fake.2021.007"},
    {"no": 8, "authors": "李疑似", "title": "图神经网络的特征学习",
     "marker": "J", "rest": "虚拟信息科学, 2022, 41(4): 55-66.",
     "year": "2022", "doi": "10.9999/fake.2022.008"},
    {"no": 9, "authors": "李疑似", "title": "图神经网络的特征学习",
     "marker": "J", "rest": "虚拟信息科学, 2023, 41(4): 55-66.",
     "year": "2023", "doi": "10.9999/fake.2023.009"},
]

# bib 变体：同内容但携带 DOI（txt 载体不著录 DOI，DOI 精确匹配路径由 bib 变体覆盖）
BIB_TYPE = {"J": "article", "M": "book", "D": "phdthesis", "R": "techreport",
            "C": "inproceedings", "S": "misc"}

# 正文段落：植入顺序——首次引用顺序 = 3,1,2,...（乱序）；[99] 悬空；
# [3]/[4] 均被引用（与去重结论解耦）；[7] 幽灵（零引用）；
# 著者-年份 "王杜撰（2020）" 与表内 2023 不符；"SMITH J（2022）" 命中。
BODY = [
    "本章提出{}的总体框架，相关方法参考[3]与[1]。".format(DOC),
    "合成数据的质量控制流程见[2]，扩展讨论见[99]。",
    "实验设置参考[1,5-6]，基线方法另见[4]。",
    "相似工作另见[8]与[9]。",
    "王杜撰（2020）曾给出质量评估的初步框架。",
    "SMITH J（2022）的方法提供了基线。",
    "本节内容不构成对其他文献的引用。",
]


def render_table():
    lines = []
    for r in TABLE:
        lines.append("[{no}] {authors}. {title}[{marker}]. {rest}".format(**r))
    return "\n".join(lines) + "\n"


def _bib_fields(r):
    """按 entry_type 生成 bib 字段（DOI 精确匹配路径需要 DOI 落进可解析载体）。"""
    etype = r["marker"]
    fams = [a.strip() for a in r["authors"].split(",")]
    author = " and ".join(fams)
    out = ["  author = {{{}}}".format(author), "  title = {{{}}}".format(r["title"])]
    if etype == "J":
        out += ["  journal = {{{}}}".format(r["rest"].split(",")[0].strip())]
    elif etype == "M":
        out += ["  address = {{{}}}".format(r["rest"].split(":")[0].strip()),
                "  publisher = {{{}}}".format(r["rest"].split(":")[1].split(",")[0].strip())]
    elif etype == "D":
        out += ["  address = {{{}}}".format(r["rest"].split(":")[0].strip()),
                "  school = {{{}}}".format(r["rest"].split(":")[1].split(",")[0].strip())]
    out += ["  year = {{{}}}".format(r["year"])]
    if r["doi"]:
        out.append("  doi = {{{}}}".format(r["doi"]))
    return out


def render_table_bib():
    blocks = []
    for r in TABLE:
        btype = BIB_TYPE[r["marker"]]
        fields = _bib_fields(r)
        body = ",\n".join(fields)
        blocks.append("@{}{{{},\n{}\n}}".format(btype, "ref{:03d}".format(r["no"]), body))
    return "\n\n".join(blocks) + "\n"


def build_truth():
    cited = [3, 1, 2, 1, 99, 1, 5, 6, 4, 8, 9]
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "generator": "code/tools/gen_audit_fixtures.py",
        "rng": "taw.rng.SplitMix64",
        "seed": SEED,
        "truth_semantics": (
            "逐项植入真值：main=主期望（引擎必须产出）；clean 项任何非 pass 计误报。"
            "REF-04 对账按「首次引用集合 / 文献表标签集合 / 著者-年份标记」三口径。"),
        "table_entries": len(TABLE),
        "body_paragraphs": len(BODY),
        "expect": {
            "dangling_citation": [99],
            "ghost_reference": [7],
            "order_gap": True,
            "number_gap": [],
            "author_year_mismatch": [{"author": "王杜撰", "cited_year": "2020",
                                      "table_year": "2023"}],
            "author_year_ok": [{"author": "SMITH", "year": "2022"}],
            "duplicate_clusters": [[3, 4]],
            "manual_confirm_pairs": [[8, 9]],
            "unique_entries": [1, 2, 3, 5, 6, 7, 8, 9],
        },
        "cited_numbers": sorted(set(cited)),
        "note": ("[7] 幽灵（正文零引用）；[3]/[4] 可自动合并（DOI 相同）；"
                 "[8]/[9] DOI 冲突 → manual_confirm（误合并 0 纪律）。"),
    }


def _dump_json(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def generate(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "refs_table.txt").write_bytes(render_table().encode("utf-8"))
    (out_dir / "refs_table.bib").write_bytes(render_table_bib().encode("utf-8"))
    (out_dir / "body.txt").write_bytes(("\n".join(BODY) + "\n").encode("utf-8"))
    (out_dir / "audit_truth.json").write_bytes(_dump_json(build_truth()))
    return sorted(["refs_table.txt", "refs_table.bib", "body.txt", "audit_truth.json"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="正文引用对账夹具生成器（seed={}）".format(SEED))
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "frozen" / "audit"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists() and any(out.iterdir()) and not args.force:
        print("[gen_audit_fixtures] 目录非空且未给 --force：{}".format(out))
        return 1
    written = generate(out)
    print("[gen_audit_fixtures] 写出 {} 个文件 -> {}".format(len(written), out))
    for name in written:
        print("  {}".format(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
