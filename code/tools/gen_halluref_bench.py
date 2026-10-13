# -*- coding: utf-8 -*-
"""HalluRef-Bench v1 全量生成器（D-4：200 条 = genuine 100 + hallucinated 100）。

结构（FORMAT.md v0.1 冻结口径）：
- genuine 100：全部自洽，DOI 前缀 `10.9999`（白名单，不计信号）；
- hallucinated 100 = 6 单类 × 16 + 复合 4：
  `doi_prefix_unknown` / `isbn_checksum_invalid` / `year_out_of_range` /
  `page_range_inverted` / `impossible_field_combo` / `self_referential_title`；
- 每条给出 `citation`（GB/T 7714 顺序编码制单条著录）+ `fields`（结构化展开）+
  可检信号清单 `signals`（{type, field, detail}）。

确定性：`taw.rng.SplitMix64` 固定 seed；无时间戳；两次运行位级一致；无 CR。
伦理：只测"幻觉文献检测能力"，不提供生成幻觉文献的通路（本生成器仅产出评测数据）。
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
DATASET_ID = "halluref-bench-v1"
GENUINE_DOI_PREFIX = "10.9999"
HALLU_DOI_PREFIX = "10.7777"
CURRENT_YEAR = 2026

CLASSES = ("doi_prefix_unknown", "isbn_checksum_invalid", "year_out_of_range",
           "page_range_inverted", "impossible_field_combo", "self_referential_title")

SURNAMES = ["张", "李", "王", "赵", "陈", "周", "吴", "郑", "冯", "蒋", "沈", "韩"]
GIVEN = ["三", "思远", "四", "明轩", "五", "雨桐", "博文", "六", "嘉树", "静怡", "志强"]
EN_FAMILY = ["SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER",
             "DAVIS", "WILSON", "ANDERSON"]
EN_INITIAL = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K"]
JOURNALS_CN = ["虚构学报", "合成科学进展", "幻想计算机研究", "数据臆测学报", "虚拟信息科学"]
JOURNALS_EN = ["Journal of Synthetic Data", "Transactions on Fabricated Systems",
               "Annals of Imaginary Computing"]
CONFS_CN = ["全国虚构计算会议论文集", "国际合成数据大会论文集"]
PUBLISHERS_CN = ["虚构出版社", "幻想书局", "合成学术出版社"]
UNIS_CN = ["虚构理工大学", "合成师范大学", "幻想大学"]
CITIES_CN = ["北京", "上海", "南京", "武汉", "成都"]
AGENCIES_CN = ["虚构研究院", "国家合成数据中心"]
TOPICS = ["深度学习", "知识图谱", "联邦学习", "图神经网络", "大语言模型",
          "数据增强", "对比学习", "强化学习", "多模态学习", "因果推断"]
OBJECTS = ["文本分类方法研究", "推荐系统优化", "低资源场景适配", "时序预测融合",
           "医学影像分析", "边缘计算部署", "缺陷检测改进", "查询扩展应用"]
TOPICS_EN = ["Deep Learning", "Knowledge Graphs", "Federated Learning",
             "Graph Neural Networks", "Contrastive Learning"]
OBJECTS_EN = ["Text Classification", "Recommender Systems", "Low-Resource Adaptation",
              "Time-Series Forecasting", "Defect Detection"]


class Gen:
    def __init__(self, rng):
        self.rng = rng

    def pick(self, seq):
        return seq[self.rng.randrange(0, len(seq))]

    def authors(self, chinese, n):
        out = []
        for _ in range(n):
            if chinese:
                out.append(self.pick(SURNAMES) + self.pick(GIVEN))
            else:
                out.append("{} {}".format(self.pick(EN_FAMILY), self.pick(EN_INITIAL)))
        return out

    def title(self, chinese):
        if chinese:
            return "基于{}{}".format(self.pick(TOPICS), self.pick(OBJECTS)) \
                if self.rng.randrange(0, 2) else "{}{}".format(self.pick(TOPICS), self.pick(OBJECTS))
        return "{} for {}".format(self.pick(TOPICS_EN), self.pick(OBJECTS_EN))

    def base_record(self, etype, chinese, idx, genuine=True):
        rec = {"entry_type": etype, "lang": "zh" if chinese else "en",
               "authors": self.authors(chinese, self.rng.randrange(1, 6)),
               "title": self.title(chinese),
               "year": str(self.rng.randrange(2017, 2026)),
               "container": None, "volume": None, "issue": None, "pages": None,
               "publisher": None, "city": None, "isbn": None, "doi": None}
        if etype == "J":
            rec["container"] = self.pick(JOURNALS_CN) if chinese else self.pick(JOURNALS_EN)
            rec["volume"] = str(self.rng.randrange(10, 70))
            rec["issue"] = str(self.rng.randrange(1, 13))
            sp = self.rng.randrange(1, 200)
            rec["pages"] = "{}-{}".format(sp, sp + self.rng.randrange(5, 40))
        elif etype == "C":
            rec["container"] = self.pick(CONFS_CN)
            rec["publisher"] = self.pick(PUBLISHERS_CN)
            rec["city"] = self.pick(CITIES_CN)
            sp = self.rng.randrange(1, 300)
            rec["pages"] = "{}-{}".format(sp, sp + self.rng.randrange(4, 20))
        elif etype == "M":
            rec["publisher"] = self.pick(PUBLISHERS_CN)
            rec["city"] = self.pick(CITIES_CN)
            sp = self.rng.randrange(1, 400)
            rec["pages"] = "{}-{}".format(sp, sp + self.rng.randrange(10, 60))
            rec["isbn"] = _isbn13_valid(self.rng)
        elif etype == "D":
            rec["container"] = self.pick(UNIS_CN)
            rec["city"] = self.pick(CITIES_CN)
        else:  # R
            rec["container"] = self.pick(AGENCIES_CN)
            rec["city"] = self.pick(CITIES_CN)
            rec["report_no"] = "RR-{}-{:03d}".format(rec["year"], self.rng.randrange(1, 400))
        return rec


def _isbn13_valid(rng):
    """按正确校验位构造 ISBN-13（genuine 用）。"""
    body = [9, 7, 8, 7] + [rng.randrange(0, 10) for _ in range(8)]
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
    check = (10 - total % 10) % 10
    digits = body + [check]
    s = "".join(str(d) for d in digits)
    return "{}-{}-{}-{}-{}".format(s[:3], s[3], s[4:8], s[8:12], s[12])


def _isbn13_broken(rng):
    """刻意破坏校验位（hallucinated 用）。"""
    valid = _isbn13_valid(rng)
    digits = [int(c) for c in valid if c.isdigit()]
    digits[-1] = (digits[-1] + rng.randrange(1, 10)) % 10
    s = "".join(str(d) for d in digits)
    return "{}-{}-{}-{}-{}".format(s[:3], s[3], s[4:8], s[8:12], s[12])


def doi_for(prefix, year, idx):
    return "{}/halluref.{}.{:04d}".format(prefix, year, idx)


# ---- 注入（每类产生 signals） ----

def inject_doi_prefix(rec, idx):
    rec["doi"] = doi_for(HALLU_DOI_PREFIX, rec["year"], idx)
    return [{"type": "doi_prefix_unknown", "field": "doi",
             "detail": "DOI 前缀 10.7777 不在已知注册前缀集"}]


def inject_isbn(rec, idx, rng):
    rec["entry_type"] = "M"
    if not rec.get("isbn") or _isbn_checksum_ok(rec["isbn"]):
        rec["isbn"] = _isbn13_broken(rng)
    else:
        rec["isbn"] = _isbn13_broken(rng)
    return [{"type": "isbn_checksum_invalid", "field": "isbn",
             "detail": "ISBN {} 校验位不合法".format(rec["isbn"])}]


def inject_year(rec, idx, rng):
    rec["year"] = str(CURRENT_YEAR + rng.randrange(1, 9))
    return [{"type": "year_out_of_range", "field": "year",
             "detail": "年份 {} 超前于基准时点 {}".format(rec["year"], CURRENT_YEAR)}]


def inject_pages(rec, idx, rng):
    if rec["entry_type"] in ("D", "R") or not rec.get("pages"):
        rec["entry_type"] = "J"
        rec["container"] = rec.get("container") or "虚构学报"
        sp = rng.randrange(50, 400)
        rec["pages"] = "{}-{}".format(sp, sp - rng.randrange(1, 40))
    else:
        a, b = rec["pages"].split("-")
        rec["pages"] = "{}-{}".format(b, a)
    a, b = rec["pages"].split("-")
    return [{"type": "page_range_inverted", "field": "pages",
             "detail": "起页 {} 大于止页 {}".format(a, b)}]


def inject_combo(rec, idx, rng):
    """期刊条目带 ISBN（类型-字段矩阵矛盾）。"""
    rec["entry_type"] = "J"
    if not rec.get("container"):
        rec["container"] = "虚构学报"
    rec["isbn"] = _isbn13_valid(rng)
    return [{"type": "impossible_field_combo", "field": "isbn",
             "detail": "期刊条目不应著录 ISBN"}]


def inject_self_ref(rec, idx):
    rec["container"] = rec["title"]
    return [{"type": "self_referential_title", "field": "title",
             "detail": "题名与载体名完全相同"}]


def _isbn_checksum_ok(isbn):
    digits = [c for c in isbn if c.isdigit()]
    if len(digits) != 13:
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    return total % 10 == 0


def assign_doi(rec, idx, genuine):
    if genuine:
        rec["doi"] = doi_for(GENUINE_DOI_PREFIX, rec["year"], idx)
    elif rec.get("doi") is None:
        rec["doi"] = doi_for(GENUINE_DOI_PREFIX, rec["year"], idx)


# ---- citation 渲染（GB/T 7714 顺序编码制单条） ----

def render_citation(rec, label):
    chinese = rec["lang"] == "zh"
    names = rec["authors"]
    if len(names) > 3:
        auth = ", ".join(names[:3]) + (", 等" if chinese else ", et al")
    else:
        auth = ", ".join(names)
    et = rec["entry_type"]
    marker = "[{}]".format(et)
    body = ""
    if et == "J":
        vi = ""
        if rec.get("volume") and rec.get("issue"):
            vi = "{}({})".format(rec["volume"], rec["issue"])
        elif rec.get("volume"):
            vi = rec["volume"]
        head = ", ".join(x for x in (rec.get("container"), rec.get("year"), vi) if x)
        body = "{}: {}.".format(head, rec["pages"]) if rec.get("pages") else "{}.".format(head)
    elif et == "C":
        loc = "{}: {}".format(rec["city"], rec["publisher"]) if rec.get("city") and rec.get("publisher") \
            else (rec.get("city") or rec.get("publisher") or "")
        s = ", ".join(x for x in (rec.get("container"), loc, rec.get("year")) if x)
        body = "{}: {}.".format(s, rec["pages"]) if rec.get("pages") else "{}.".format(s)
    elif et == "D":
        loc = "{}: {}".format(rec["city"], rec.get("container")) if rec.get("city") else (rec.get("container") or "")
        s = ", ".join(x for x in (loc, rec.get("year")) if x)
        body = "{}.".format(s)
    elif et == "M":
        loc = "{}: {}".format(rec["city"], rec.get("publisher")) if rec.get("city") and rec.get("publisher") \
            else (rec.get("city") or rec.get("publisher") or "")
        s = ", ".join(x for x in (loc, rec.get("year")) if x)
        body = "{}: {}.".format(s, rec["pages"]) if rec.get("pages") else "{}.".format(s)
    else:  # R
        loc = "{}: {}".format(rec["city"], rec.get("container")) if rec.get("city") else (rec.get("container") or "")
        s = ", ".join(x for x in (loc, rec.get("year")) if x)
        body = "{}. {}.".format(s, rec["report_no"]) if rec.get("report_no") else "{}.".format(s)
    if et == "C":
        return "{} {} {}{}//{}".format(label, auth + ".", rec["title"], marker, body)
    return "{} {} {}{}. {}".format(label, auth + ".", rec["title"], marker, body).rstrip()


def build_entries(rng):
    g = Gen(rng)
    entries = []

    # genuine 100
    for i in range(1, 101):
        etype = ["J", "C", "D", "M", "R"][i % 5]
        chinese = (i % 2 == 0)
        rec = g.base_record(etype, chinese, i, genuine=True)
        assign_doi(rec, i, genuine=True)
        entries.append({"entry_id": "hr-{:04d}".format(i), "label": "genuine",
                        "classes": [], "signals": [], "rec": rec})

    # hallucinated 100 = 6 单类 × 16 + 复合 4
    n = 100
    plan = []
    for cls in CLASSES:
        plan.extend([cls] * 16)
    plan.extend([["page_range_inverted", "impossible_field_combo"]] * 1)
    plan.extend([["doi_prefix_unknown", "year_out_of_range"]] * 1)
    plan.extend([["self_referential_title", "isbn_checksum_invalid"]] * 1)
    plan.extend([["year_out_of_range", "page_range_inverted"]] * 1)
    assert len(plan) == 100, len(plan)

    for k, spec in enumerate(plan):
        idx = 101 + k
        classes = spec if isinstance(spec, list) else [spec]
        primary = classes[0]
        # 复合中的 isbn/组合类需要 M；其余按类特点选类型
        if "isbn_checksum_invalid" in classes or primary == "isbn_checksum_invalid":
            etype = "M"
        elif primary in ("doi_prefix_unknown", "self_referential_title"):
            etype = "J"
        elif primary == "impossible_field_combo":
            etype = "J"
        else:
            etype = ["J", "C", "D", "M", "R"][idx % 5]
        chinese = (idx % 2 == 1)
        rec = g.base_record(etype, chinese, idx, genuine=False)
        signals = []
        for cls in classes:
            if cls == "doi_prefix_unknown":
                signals.extend(inject_doi_prefix(rec, idx))
            elif cls == "isbn_checksum_invalid":
                signals.extend(inject_isbn(rec, idx, rng))
            elif cls == "year_out_of_range":
                signals.extend(inject_year(rec, idx, rng))
            elif cls == "page_range_inverted":
                signals.extend(inject_pages(rec, idx, rng))
            elif cls == "impossible_field_combo":
                signals.extend(inject_combo(rec, idx, rng))
            elif cls == "self_referential_title":
                signals.extend(inject_self_ref(rec, idx))
        # 非 doi_prefix_unknown 的条目用白名单前缀（不引入额外信号）
        if "doi_prefix_unknown" not in classes:
            rec["doi"] = doi_for(GENUINE_DOI_PREFIX, rec["year"], idx)
        entries.append({"entry_id": "hr-{:04d}".format(idx), "label": "hallucinated",
                        "classes": classes, "signals": signals, "rec": rec})

    # 渲染 citation + fields
    out = []
    for e in entries:
        rec = e["rec"]
        fields = {k: rec.get(k) for k in ("entry_type", "authors", "title", "container",
                                          "year", "volume", "issue", "pages", "publisher",
                                          "city", "isbn", "doi")}
        out.append({"entry_id": e["entry_id"], "label": e["label"],
                    "classes": e["classes"], "signals": e["signals"],
                    "citation": render_citation(rec, "[{}]".format(len(out) + 1)),
                    "fields": fields})
    return out


def build_manifest(entries):
    genuine = [e for e in entries if e["label"] == "genuine"]
    hallucinated = [e for e in entries if e["label"] == "hallucinated"]
    by_class = {}
    singles = {}
    for e in hallucinated:
        for c in e["classes"]:
            by_class[c] = by_class.get(c, 0) + 1
        if len(e["classes"]) == 1:
            singles[e["classes"][0]] = singles.get(e["classes"][0], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "bench_id": "halluref-bench",
        "version": "v1",
        "dataset": DATASET_ID,
        "generator": "code/tools/gen_halluref_bench.py",
        "rng": "taw.rng.SplitMix64",
        "seed": SEED,
        "files": ["halluref_v1.jsonl", "halluref_v1_manifest.json"],
        "format": {"spec": "FORMAT.md",
                   "serialization": "jsonl（UTF-8 无 BOM，每行一个 JSON 对象）",
                   "entry_id_pattern": "hr-[0-9]{4}",
                   "doi_genuine_prefix": GENUINE_DOI_PREFIX,
                   "doi_hallucinated_prefix": HALLU_DOI_PREFIX},
        "scale": {"total": len(entries), "genuine": len(genuine),
                  "hallucinated": len(hallucinated),
                  "hallucinated_composition": "6 单类 × 16 + 复合 4",
                  "singles_total": sum(singles.values()),
                  "composite_total": sum(1 for e in hallucinated if len(e["classes"]) > 1)},
        "classes_v1": list(CLASSES),
        "class_counts_single": singles,
        "class_counts_all": by_class,
        "class_counts_note": ("class_counts_single = 每类仅该类别的条目数（各 16）；"
                              "class_counts_all 另计复合条目带入的类别出现次数"),
        "determinism": "无时间戳；两次运行位级一致；CR 守门（test_data_gate）",
        "note": ("公开基准：只测幻觉文献检测能力，不提供任何生成幻觉文献的通路；"
                 "全部条目为程序化虚构，作者/刊名/DOI 均不指向真实出版物。"),
    }


def generate(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = build_entries(SplitMix64(SEED))
    lines = [json.dumps(e, ensure_ascii=False, sort_keys=True) for e in entries]
    (out_dir / "halluref_v1.jsonl").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    (out_dir / "halluref_v1_manifest.json").write_bytes(
        (json.dumps(build_manifest(entries), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return sorted(["halluref_v1.jsonl", "halluref_v1_manifest.json"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="HalluRef-Bench v1 生成器（seed={}）".format(SEED))
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "bench" / "halluref"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out)
    written = generate(out)
    print("[gen_halluref_bench] 写出 {} 个文件 -> {}".format(len(written), out))
    for name in written:
        print("  {}".format(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
