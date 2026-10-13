# -*- coding: utf-8 -*-
"""综述辅助语料生成器（FULL-05 的数据面，声明式确定性）。

产出 `data/frozen/review/`：
- `review_corpus.json`：文献库内 20 条虚构文献（4 个主题簇 × 5 条 + 年份分布）；
- `review_truth.json`：预分组真值（主题→条目）、年代分布、**研究空白真值**
  （哪些主题近 3 年无新增）。

设计纪律与既有生成器一致：内容全部虚构、声明式（无随机）、无时间戳、
两次运行位级一致、无 CR。

研究空白真值口径：以 corpus 的 `now_year`（数据集声明口径年）为基准，
主题内**最近年份 ≤ now_year - 3** 即判"近 3 年无新增"（FULL-05 规则可判口径）。
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = 1
DATASET_ID = "review-corpus-v1"
NOW_YEAR = 2026          # 数据集口径年（研究空白判定的基准）

# 4 个主题簇（每簇 5 条）；主题词决定聚类归属，年份决定时间线/空白。
# topic-4（"可解释性"）刻意全部落在 2020-2022（近 3 年无新增）→ 研究空白真值。
TOPICS = {
    "synthetic_data": {
        "label": "合成数据生成",
        "keywords": ["合成数据", "生成模型", "数据增强"],
        "entries": [
            {"no": 1, "title": "基于生成对抗网络的合成数据构建方法", "year": 2021},
            {"no": 2, "title": "面向表格数据的可控合成数据生成", "year": 2022},
            {"no": 3, "title": "合成数据质量评估指标体系研究", "year": 2023},
            {"no": 4, "title": "扩散模型驱动的合成数据增强", "year": 2024},
            {"no": 5, "title": "面向小样本场景的合成数据生成框架", "year": 2025},
        ],
    },
    "graph_learning": {
        "label": "图神经网络",
        "keywords": ["图神经网络", "消息传递", "节点表示"],
        "entries": [
            {"no": 6, "title": "图神经网络的消息传递机制综述", "year": 2020},
            {"no": 7, "title": "面向异质图的节点表示学习方法", "year": 2022},
            {"no": 8, "title": "图神经网络在推荐系统中的应用", "year": 2023},
            {"no": 9, "title": "大规模图上的可扩展图神经网络训练", "year": 2024},
            {"no": 10, "title": "图神经网络的特征学习与过平滑缓解", "year": 2025},
        ],
    },
    "federated": {
        "label": "联邦学习",
        "keywords": ["联邦学习", "隐私保护", "分布式训练"],
        "entries": [
            {"no": 11, "title": "联邦学习的隐私保护机制研究", "year": 2021},
            {"no": 12, "title": "非独立同分布数据下的联邦学习优化", "year": 2022},
            {"no": 13, "title": "联邦学习中的通信效率优化方法", "year": 2023},
            {"no": 14, "title": "面向边缘设备的联邦学习部署", "year": 2024},
            {"no": 15, "title": "联邦学习与合成数据结合的隐私增强", "year": 2025},
        ],
    },
    "interpretability": {
        "label": "模型可解释性",
        "keywords": ["可解释性", "注意力可视化", "归因分析"],
        "entries": [
            {"no": 16, "title": "深度模型的可解释性归因分析方法", "year": 2020},
            {"no": 17, "title": "注意力机制可视化与解释", "year": 2021},
            {"no": 18, "title": "基于代理模型的可解释性评估", "year": 2021},
            {"no": 19, "title": "神经网络决策过程的解释性综述", "year": 2022},
            {"no": 20, "title": "可解释性方法在医疗诊断中的应用", "year": 2022},
        ],
    },
}

VENUES = ("虚构学报", "合成科学进展", "虚拟信息科学", "幻想计算学报")


def _entry_id(no):
    return "rev-{:03d}".format(no)


def build_corpus():
    """主题簇 → 平铺条目列表（含预分组真值的 group 字段）。"""
    entries = []
    for gkey, topic in sorted(TOPICS.items()):
        for e in topic["entries"]:
            entries.append({
                "entry_id": _entry_id(e["no"]),
                "group": gkey,
                "title": e["title"],
                "authors": ["虚构作者{}".format(e["no"])],
                "year": e["year"],
                "venue": VENUES[e["no"] % len(VENUES)],
                "keywords": list(topic["keywords"]),
                "doi": "10.9999/review.{}.{:03d}".format(e["year"], e["no"]),
            })
    entries.sort(key=lambda x: x["entry_id"])
    return entries


def build_truth():
    entries = build_corpus()
    groups = {}
    for e in entries:
        groups.setdefault(e["group"], []).append(e["entry_id"])
    # 研究空白：主题内最近年份 ≤ NOW_YEAR-3
    gaps = []
    for gkey, topic in sorted(TOPICS.items()):
        years = [e["year"] for e in topic["entries"]]
        recent = max(years)
        if recent <= NOW_YEAR - 3:
            gaps.append({"group": gkey, "label": topic["label"],
                         "latest_year": recent,
                         "reason": "主题'{}'库内最近年份 {}，近 3 年（{} 起）无新增".format(
                             topic["label"], recent, NOW_YEAR - 2)})
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "generator": "code/tools/gen_review_corpus.py",
        "rng": "declarative（声明式内容模型，无随机抽取）",
        "now_year": NOW_YEAR,
        "gap_rule": "主题内最近年份 ≤ now_year-3 即判'近 3 年无新增'（规则可判口径）",
        "counts": {"entries": len(entries), "groups": len(groups), "gaps": len(gaps)},
        "groups": {k: sorted(v) for k, v in sorted(groups.items())},
        "group_labels": {k: t["label"] for k, t in sorted(TOPICS.items())},
        "years_by_group": {k: sorted(e["year"] for e in t["entries"])
                           for k, t in sorted(TOPICS.items())},
        "research_gaps": gaps,
    }


def _dump(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def generate(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "review_corpus.json").write_bytes(_dump({
        "schema_version": SCHEMA_VERSION, "dataset": DATASET_ID,
        "generator": "code/tools/gen_review_corpus.py", "now_year": NOW_YEAR,
        "entries": build_corpus()}))
    (out_dir / "review_truth.json").write_bytes(_dump(build_truth()))
    return sorted(["review_corpus.json", "review_truth.json"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="综述辅助语料生成器（声明式确定性）")
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "frozen" / "review"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists() and any(out.iterdir()) and not args.force:
        print("[gen_review_corpus] 目录非空且未给 --force：{}".format(out))
        return 1
    written = generate(out)
    print("[gen_review_corpus] 写出 {} 个文件 -> {}".format(len(written), out))
    for name in written:
        print("  {}".format(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
