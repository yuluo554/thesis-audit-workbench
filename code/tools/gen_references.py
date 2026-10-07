# -*- coding: utf-8 -*-
"""合成文献表生成器（M1 核心资产，plan/05 §二）。

产出 data/frozen/refs/：五类条目（期刊J/会议C/学位D/图书M/报告R）× 噪声分层
（clean/light/heavy）× 错误注入（标点/缺项/类型标识/著者数/编码制混用/结构矛盾），
以 txt/csv/bib/ris 四格式落盘，附逐条真值 JSON。

真值语义（plan/04 §七，一次定清）：
- expect      = 注入缺陷的【主期望】——引擎对该条目必须产出的主 finding；
- also_expect = 同一注入隐含/伴生的其余结论；复合注入（一次两条错误）时为次错误期望；
- 基准对账按"文档全部非 pass 集合"对照：主期望必须命中，also_expect 允许并入集合；
  clean 条目（expect=null 且 also_expect=[]）出现任何非 pass 判定即为误报；
- 互斥坑规避：标点注入按格式选 glyph（bib=字段逗号缺失、ris=标签短横），保证
  "真值声明的错误在落盘文本中真实可见"，杜绝真值与产物不一致的假缺陷；
- 全部注入类型清单见 error_taxonomy（真值 JSON 内），评测报告可逐类归因。

确定性纪律：内容细节全部来自 taw.rng.SplitMix64（固定 seed）；注入位置/类型
用代码内固定模式表（覆盖全部六类，不交给随机数）；产物无时间戳，两次运行
逐字节一致。全部作者/刊名/机构/DOI 虚构；DOI 一律 10.9999/ 假前缀。

用法：
    python code/tools/gen_references.py [--out DIR] [--force]
不带 --force 且目标目录已有文件时拒绝覆盖（exit 1）。
"""

import argparse
import csv
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "code" / "src"))

from taw.rng import SplitMix64  # noqa: E402

SEED = 20261007
SCHEMA_VERSION = 1
DATASET_ID = "refs-synthetic-v1"

LAYERS = ("clean", "light", "heavy")
FORMATS = ("txt", "csv", "bib", "ris")

# 每层 24 条：类型序列（J6/C5/D4/M5/R4）× 注入模式（覆盖六类错误 + 2 条复合 + 7 条干净）。
# 注入模式固定不随机——真值覆盖面是审计契约，不交给随机数。
TYPE_SEQUENCE = ["J", "J", "J", "J", "J", "J",
                 "C", "C", "C", "C", "C",
                 "D", "D", "D", "D",
                 "M", "M", "M", "M", "M",
                 "R", "R", "R", "R"]
INJECT_SEQUENCE = [
    None, ("punct",), ("missing",), None, ("marker",), ("author",),
    None, ("structure",), ("encoding",), ("punct",), None, ("missing",),
    ("author",), ("compound", "punct", "missing"), None, ("marker",),
    ("structure",), None, ("encoding",), ("punct",),
    ("compound", "missing", "marker"), None, ("author",), ("structure",),
]

ERROR_TAXONOMY = {
    "punct": {"check_type": "punct", "label": "著录标点错误"},
    "missing": {"check_type": "field_required", "label": "缺项"},
    "marker": {"check_type": "type_marker", "label": "文献类型标识错误"},
    "author": {"check_type": "author_threshold", "label": "著者数与'等'使用错误"},
    "encoding": {"check_type": "citation_style", "label": "编码制混用"},
    "structure": {"check_type": "page_range_or_consistency", "label": "结构矛盾"},
}

# ---- 虚构内容池（全部杜撰；台账已登记虚构纪律）----

CN_SURNAMES = ["张", "李", "王", "赵", "陈", "周", "吴", "郑", "冯", "蒋", "沈", "韩", "杨", "朱", "许", "何"]
CN_GIVEN = ["三", "思远", "四", "明轩", "五", "雨桐", "博文", "六", "嘉树", "静怡", "志强", "七", "晓峰", "雅琴", "文博", "天宇"]
EN_FAMILY = ["SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER", "DAVIS", "WILSON", "ANDERSON"]
EN_INITIALS = ["A", "B", "C", "D", "E", "F", "G", "H", "J", "K"]

CN_JOURNALS = ["虚构学报", "合成科学进展", "幻想计算机研究", "数据臆测学报", "虚拟信息科学", "编造工程学报"]
EN_JOURNALS = ["Journal of Synthetic Data", "Transactions on Fabricated Systems", "Annals of Imaginary Computing"]
CN_CONFS = ["全国虚构计算会议论文集", "国际合成数据大会论文集", "幻想系统研讨会论文集"]
EN_CONFS = ["Proceedings of the Conference on Synthetic Data", "Proceedings of the International Workshop on Fabricated Systems"]
CN_UNIVERSITIES = ["虚构理工大学", "合成师范大学", "幻想大学", "编造科技大学"]
EN_UNIVERSITIES = ["Synthetic Institute of Technology", "University of Fabrication"]
CN_PUBLISHERS = ["虚构出版社", "幻想书局", "合成学术出版社"]
EN_PUBLISHERS = ["Fake Academic Press", "Imaginary Book House"]
CN_CITIES = ["北京", "上海", "南京", "武汉", "成都"]
EN_CITIES = ["New York", "London", "Berlin"]
CN_AGENCIES = ["虚构研究院", "国家合成数据中心", "幻想信息技术研究所"]
EN_AGENCIES = ["Institute of Synthetic Studies", "National Fabricated Data Center"]

TOPICS_CN = ["深度学习", "知识图谱", "联邦学习", "图神经网络", "大语言模型", "数据增强", "对比学习", "强化学习", "多模态学习", "因果推断"]
OBJECTS_CN = ["文本分类方法研究", "推荐系统优化", "低资源场景适配", "时序预测融合", "医学影像分析", "边缘计算部署", "缺陷检测改进", "查询扩展应用"]
TOPICS_EN = ["Deep Learning", "Knowledge Graphs", "Federated Learning", "Graph Neural Networks", "Contrastive Learning"]
OBJECTS_EN = ["Text Classification", "Recommender Systems", "Low-Resource Adaptation", "Time-Series Forecasting", "Defect Detection"]
EN_HYPHEN_WORDS = ["Cross-Lingual", "Transformer-Based", "Self-Supervised", "Task-Oriented", "End-To-End"]

TYPE_LABEL = {"J": "期刊", "C": "会议", "D": "学位", "M": "图书", "R": "报告"}


# ---- 条目构造 ----


def _mk_names(rng, n, chinese):
    """n 个虚构著者；中文'姓名'连写，西文 FAMILY + 缩写名。"""
    names = []
    for _ in range(n):
        if chinese:
            names.append(rng.choice(CN_SURNAMES) + rng.choice(CN_GIVEN))
        else:
            k = rng.randrange(1, 3)
            names.append("{} {}".format(rng.choice(EN_FAMILY), " ".join(rng.choice(EN_INITIALS) for _ in range(k))))
    return names


def _mk_title(rng, chinese, force_hyphen=False):
    if chinese:
        return "基于{}的{}".format(rng.choice(TOPICS_CN), rng.choice(OBJECTS_CN))
    if force_hyphen:
        return "{} {} for {}".format(rng.choice(EN_HYPHEN_WORDS), rng.choice(TOPICS_EN), rng.choice(OBJECTS_EN))
    return "{} for {}".format(rng.choice(TOPICS_EN), rng.choice(OBJECTS_EN))


def _mk_record(rng, seq_no, entry_type):
    """逻辑完整的虚构条目（未注入任何错误）。"""
    chinese = rng.chance(0.6)
    year = rng.randrange(2018, 2026)
    rec = {
        "entry_id": "ref-{:04d}".format(seq_no),
        "entry_type": entry_type,
        "lang": "zh" if chinese else "en",
        "authors": _mk_names(rng, rng.randrange(1, 6), chinese),
        "title": _mk_title(rng, chinese, force_hyphen=rng.chance(0.3)),
        "year": str(year),
        "doi": "10.9999/fake.{}.{:03d}".format(year, seq_no),
    }
    if entry_type == "J":
        rec["container"] = rng.choice(CN_JOURNALS if chinese else EN_JOURNALS)
        rec["volume"] = str(rng.randrange(30, 71))
        rec["issue"] = str(rng.randrange(1, 13))
        start = rng.randrange(1, 200)
        rec["pages"] = "{}-{}".format(start, start + rng.randrange(5, 20))
    elif entry_type == "C":
        rec["container"] = rng.choice(CN_CONFS if chinese else EN_CONFS)
        rec["publisher"] = rng.choice(CN_PUBLISHERS if chinese else EN_PUBLISHERS)
        rec["city"] = rng.choice(CN_CITIES if chinese else EN_CITIES)
        start = rng.randrange(1, 400)
        rec["pages"] = "{}-{}".format(start, start + rng.randrange(4, 12))
    elif entry_type == "D":
        rec["container"] = rng.choice(CN_UNIVERSITIES if chinese else EN_UNIVERSITIES)
        rec["city"] = rng.choice(CN_CITIES if chinese else EN_CITIES)
    elif entry_type == "M":
        rec["publisher"] = rng.choice(CN_PUBLISHERS if chinese else EN_PUBLISHERS)
        rec["city"] = rng.choice(CN_CITIES if chinese else EN_CITIES)
        rec["isbn"] = "978-7-{:04d}-{:04d}-{:01d}".format(rng.randrange(0, 10000), rng.randrange(0, 10000), rng.randrange(0, 10))
        rec["edition"] = rng.randrange(1, 4)
        start = rng.randrange(1, 250)
        rec["pages"] = "{}-{}".format(start, start + rng.randrange(10, 60))
    elif entry_type == "R":
        rec["container"] = rng.choice(CN_AGENCIES if chinese else EN_AGENCIES)
        rec["city"] = rng.choice(CN_CITIES if chinese else EN_CITIES)
        rec["report_no"] = "RR-{}-{:03d}".format(year, rng.randrange(1, 999))
    return rec


# ---- 错误注入（逻辑层）----


def _inject_missing(rec, rng):
    """缺项：从该类型可缺字段中选一个置 None。"""
    pools = {"J": ["year", "pages", "volume"], "C": ["year", "publisher", "pages"],
             "D": ["year", "city"], "M": ["year", "publisher", "pages"], "R": ["year", "city"]}
    field = rng.choice(pools[rec["entry_type"]])
    rec[field] = None
    return {"type": "missing", "field": field, "detail": "删除字段 {}".format(field), "formats": list(FORMATS)}


def _inject_marker(rec, rng):
    """类型标识错误：J↔C、M↔R 互换（txt 用错 [X]，bib 用错条目类型，ris 用错 TY）。"""
    swap = {"J": "C", "C": "J", "M": "R", "R": "M", "D": "M"}[rec["entry_type"]]
    rec["_marker_wrong"] = swap
    return {"type": "marker", "field": "type_marker",
            "detail": "标识 {} 误标为 {}".format(rec["entry_type"], swap), "formats": list(FORMATS)}


def _inject_author(rec, rng):
    """著者数错误：(a) >3 全列不给'等'；(b) ≤3 反而加了'等'。"""
    if len(rec["authors"]) > 3:
        rec["_author_over_full"] = True
        return {"type": "author", "field": "authors",
                "detail": "{} 位著者未按'前三+等'截断".format(len(rec["authors"])), "formats": list(FORMATS)}
    rec["_author_premature_deng"] = True
    return {"type": "author", "field": "authors",
            "detail": "仅 {} 位著者却使用'等'".format(len(rec["authors"])), "formats": list(FORMATS)}


def _inject_structure(rec, rng):
    """结构矛盾：(a) 页码倒置；(b) DOI 假前缀年份段与出版年矛盾（无页码类型走 b）。"""
    if rec.get("pages"):
        start, end = rec["pages"].split("-")
        rec["pages"] = "{}-{}".format(end, start)
        return {"type": "structure", "field": "pages", "detail": "页码倒置 {}-{}".format(end, start), "formats": list(FORMATS)}
    old = rec["year"]
    rec["doi"] = rec["doi"].replace("/fake.{}.".format(old), "/fake.{}.".format(int(old) - rng.randrange(1, 5)))
    return {"type": "structure", "field": "doi", "detail": "DOI 年份段与出版年 {} 矛盾".format(old), "formats": list(FORMATS)}


def _inject_encoding(rec):
    """编码制混用：该条目按著者-出版年制渲染且不占顺序编号（txt/csv 可见）。"""
    rec["_encoding_mix"] = True
    return {"type": "encoding", "field": "citation_style",
            "detail": "著者-出版年制条目混入顺序编码制文献表", "formats": ["txt", "csv"]}


def _inject_punct(rec, rng, fmt):
    """标点错误：按格式选必然可见的 glyph（互斥坑：bib/ris 无', '上下文，专用 glyph）。"""
    if fmt in ("txt", "csv"):
        glyph = rng.choice(["comma_cn", "dot_missing", "colon_cn", "comma_extra"])
    elif fmt == "bib":
        glyph = "field_comma_missing"
    else:
        glyph = "tag_dash_short"
    rec.setdefault("_punct", {})[fmt] = glyph
    return {"type": "punct", "field": "punctuation", "detail": "{}: {}".format(fmt, glyph), "formats": [fmt]}


# ---- 著者串（GB/T 7714 著录规则：≤3 全列；>3 前三 + 等/et al）----


def _author_string(rec, inject_aware=True):
    names = rec["authors"]
    chinese = rec["lang"] == "zh"
    if inject_aware and rec.get("_author_over_full"):
        return ", ".join(names)
    if len(names) <= 3:
        base = ", ".join(names)
        if inject_aware and rec.get("_author_premature_deng"):
            return base + (", 等" if chinese else ", et al")
        return base
    tail = ", 等" if chinese else ", et al"
    return ", ".join(names[:3]) + tail


# ---- 噪声分层（clean 原样 / light 单处伪影 / heavy 2-4 处）----


def _fullwidth(text):
    for y in range(2018, 2026):
        text = text.replace(str(y), "".join(chr(ord(c) + 0xFEE0) for c in str(y)))
    return text


def _apply_noise(text, rng, layer):
    if layer == "clean":
        return text
    if layer == "light":
        pick = rng.randrange(0, 3)
        if pick == 0:
            return text.replace(". ", ".  ", 1)
        if pick == 1 and "（" not in text and "(" in text:
            return text.replace("(", "（", 1).replace(")", "）", 1)
        if pick == 1:
            return text.replace(". ", ".  ", 1)
        return text.replace("[", "[ ", 1).replace("]", " ]", 1)
    # heavy：2-4 个伪影依次套用
    out = text
    for _ in range(rng.randrange(2, 5)):
        pick = rng.randrange(0, 5)
        if pick == 0:  # CJK 内插空格
            idx = rng.randrange(0, len(out))
            out = out[:idx] + " " + out[idx:]
        elif pick == 1:  # 双空格
            out = out.replace(". ", ".   ", 1)
        elif pick == 2:  # 全角数字
            out = _fullwidth(out)
        elif pick == 3:  # 任意断行
            pos = rng.randrange(6, max(8, len(out) - 2))
            out = out[:pos] + "\n" + out[pos:]
        else:  # 连字符断裂（断行点带连字符）
            pos = rng.randrange(5, max(7, len(out) - 2))
            out = out[:pos] + "-\n" + out[pos:]
    return out


def _punct_glitch_text(text, glyph):
    """txt/csv 的标点注入（全部保证可见）。"""
    if glyph == "comma_cn":
        return text.replace(", ", "，", 1)
    if glyph == "dot_missing":
        return text.replace(". ", " ", 1)
    if glyph == "colon_cn":
        return text.replace(": ", "：", 1) if ": " in text else text.replace(", ", "，", 1)
    if glyph == "comma_extra":
        return text[:-1] + ",." if text.endswith(".") else text + ","
    return text


# ---- txt/csv 渲染（顺序编码制；encoding_mix 条目走著者-出版年制且不占编号）----


def _txt_body(rec, include_year=True):
    """[标识] 之后的著录主体（按逻辑类型取字段；缺项字段自然缺席）。

    C 类返回值不含 '//\\u524d\\u7f00'（调用方以 title[C]//body 拼接）。
    include_year=False 用于著者-出版年制条目（年份已在著者后出现，正文不重复）。
    """
    etype = rec["entry_type"]
    pages, year = rec.get("pages"), rec.get("year") if include_year else None
    if etype == "J":
        vi = ""
        if rec.get("volume") and rec.get("issue"):
            vi = "{}({})".format(rec["volume"], rec["issue"])
        elif rec.get("volume"):
            vi = rec["volume"]
        elif rec.get("issue"):
            vi = "({})".format(rec["issue"])
        head = ", ".join(x for x in (rec.get("container"), year, vi) if x)
        if pages and head:
            return "{}: {}.".format(head, pages)
        return "{}.".format(head or (pages or ""))
    if etype == "C":
        if rec.get("city") and rec.get("publisher"):
            loc = "{}: {}".format(rec["city"], rec["publisher"])
        else:
            loc = rec.get("city") or rec.get("publisher") or ""
        parts = [x for x in (rec.get("container"), loc, year) if x]
        s = ", ".join(parts)
        if pages and s:
            return "{}: {}.".format(s, pages)
        return "{}.".format(s or (pages or ""))
    if etype in ("D", "R"):
        if rec.get("city"):
            loc = "{}: {}".format(rec["city"], rec.get("container"))
        else:
            loc = rec.get("container") or ""
        s = ", ".join(x for x in (loc, year) if x)
        if etype == "D":
            return "{}.".format(s) if s else "."
        rn = rec.get("report_no")
        if rn:
            return "{}. {}.".format(s, rn) if s else "{}.".format(rn)
        return "{}.".format(s) if s else "."
    # M
    ed = ""
    if rec.get("edition") and rec["edition"] > 1:
        ed = "{}版. ".format(rec["edition"]) if rec["lang"] == "zh" else "{} ed. ".format(rec["edition"])
    if rec.get("city") and rec.get("publisher"):
        loc = "{}: {}".format(rec["city"], rec["publisher"])
    else:
        loc = rec.get("city") or rec.get("publisher") or ""
    parts = [x for x in (ed.rstrip(". "), loc, year) if x]
    s = ", ".join(parts)
    if pages and s:
        return "{}: {}.".format(s, pages)
    return "{}.".format(s or (": " + pages if pages else ""))


def _txt_citation(rec, label, layer, rng, punct_glyph):
    authors = _author_string(rec)
    marker = rec.get("_marker_wrong") or rec["entry_type"]
    encoding = rec.get("_encoding_mix")
    body = _txt_body(rec, include_year=not encoding)
    if encoding:
        text = "{}, {}. {}[{}]. {}".format(authors, rec.get("year") or "", rec["title"], marker, body)
    elif rec["entry_type"] == "C":
        text = "{}. {}[{}]//{}".format(authors, rec["title"], marker, body)
        if label:
            text = "[{}] ".format(label) + text
    else:
        text = "{}. {}[{}]. {}".format(authors, rec["title"], marker, body)
        if label:
            text = "[{}] ".format(label) + text
    if punct_glyph:
        text = _punct_glitch_text(text, punct_glyph)
    return _apply_noise(text, rng, layer)


def _numeric_labels(entries):
    """顺序编码制编号：仅对非 encoding_mix 条目连续计数（真实混排文献表口径）。"""
    labels = []
    no = 0
    for rec in entries:
        if rec.get("_encoding_mix"):
            labels.append(None)
        else:
            no += 1
            labels.append(str(no))
    return labels


def render_txt(entries, layer, rng):
    lines = []
    for rec, label in zip(entries, _numeric_labels(entries)):
        glyph = (rec.get("_punct") or {}).get("txt")
        lines.append(_txt_citation(rec, label, layer, rng, glyph))
    return "\n".join(lines) + "\n"


def render_csv(entries, layer, rng):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["no", "entry_id", "entry_type", "citation"])
    for i, (rec, label) in enumerate(zip(entries, _numeric_labels(entries)), 1):
        glyph = (rec.get("_punct") or {}).get("csv")
        writer.writerow([i, rec["entry_id"], rec["entry_type"], _txt_citation(rec, label, layer, rng, glyph)])
    return buf.getvalue()


# ---- bib / ris 渲染 ----

BIB_TYPE = {"J": "article", "C": "inproceedings", "D": "phdthesis", "M": "book", "R": "techreport"}
RIS_TYPE = {"J": "JOUR", "C": "CONF", "D": "THES", "M": "BOOK", "R": "RPRT"}


def _bib_fields(rec):
    etype = rec["entry_type"]
    fields = [("author", _bib_author_value(rec)), ("title", rec["title"])]
    if etype == "J":
        fields += [("journal", rec.get("container")), ("year", rec.get("year")),
                   ("volume", rec.get("volume")), ("number", rec.get("issue")), ("pages", rec.get("pages"))]
    elif etype == "C":
        fields += [("booktitle", rec.get("container")), ("address", rec.get("city")),
                   ("publisher", rec.get("publisher")), ("year", rec.get("year")), ("pages", rec.get("pages"))]
    elif etype == "D":
        fields += [("address", rec.get("city")), ("school", rec.get("container")), ("year", rec.get("year"))]
    elif etype == "M":
        fields += [("address", rec.get("city")), ("publisher", rec.get("publisher")),
                   ("edition", str(rec["edition"]) if rec.get("edition") else None),
                   ("year", rec.get("year")), ("pages", rec.get("pages")), ("isbn", rec.get("isbn"))]
    else:
        fields += [("address", rec.get("city")), ("institution", rec.get("container")),
                   ("year", rec.get("year")), ("number", rec.get("report_no"))]
    fields.append(("doi", rec.get("doi")))
    return [f for f in fields if f[1] is not None]


def _bib_author_value(rec):
    out = []
    for a in rec["authors"]:
        if rec["lang"] == "zh":
            out.append(a)
        else:
            family, given = a.split(" ", 1)
            out.append("{}, {}".format(family, given.replace(" ", "")))
    if len(out) > 3:
        out = out[:3] + ["others"]
    elif rec.get("_author_premature_deng"):
        out = out + ["others"]
    return " and ".join(out)


def _render_bib_entry(rec, layer, rng, punct_glyph):
    marker = rec.get("_marker_wrong") or rec["entry_type"]
    lines = ["@{}{{{},".format(BIB_TYPE[marker], rec["entry_id"].replace("-", ""))]
    fields = _bib_fields(rec)
    for i, (key, val) in enumerate(fields):
        comma = "," if i < len(fields) - 1 else ""
        if punct_glyph == "field_comma_missing" and key == "author":
            comma = ""
        lines.append("  {} = {{{}}}{}".format(key, val, comma))
    return _apply_noise("\n".join(lines) + "\n}", rng, layer)


def render_bib(entries, layer, rng):
    out = []
    for rec in entries:
        glyph = (rec.get("_punct") or {}).get("bib")
        out.append(_render_bib_entry(rec, layer, rng, glyph))
    return "\n".join(out) + "\n"


def _render_ris_entry(rec, layer, rng, punct_glyph):
    marker = rec.get("_marker_wrong") or rec["entry_type"]
    lines = ["TY  - {}".format(RIS_TYPE[marker])]
    for a in rec["authors"]:
        lines.append("AU  - {}".format(a))
    lines.append("TI  - {}".format(rec["title"]))
    etype = rec["entry_type"]
    if etype == "J":
        lines += ["JO  - {}".format(rec.get("container")), "VL  - {}".format(rec.get("volume")), "IS  - {}".format(rec.get("issue"))]
    elif etype == "C":
        lines += ["T2  - {}".format(rec.get("container")), "CY  - {}".format(rec.get("city")), "PB  - {}".format(rec.get("publisher"))]
    elif etype == "D":
        lines += ["CY  - {}".format(rec.get("city")), "PB  - {}".format(rec.get("container"))]
    elif etype == "M":
        lines += ["CY  - {}".format(rec.get("city")), "PB  - {}".format(rec.get("publisher")), "SN  - {}".format(rec.get("isbn"))]
    else:
        lines += ["CY  - {}".format(rec.get("city")), "PB  - {}".format(rec.get("container")), "NO  - {}".format(rec.get("report_no"))]
    if rec.get("year"):
        lines.append("PY  - {}".format(rec["year"]))
    if rec.get("pages"):
        sp, ep = rec["pages"].split("-")
        lines += ["SP  - {}".format(sp), "EP  - {}".format(ep)]
    if rec.get("doi"):
        lines.append("DO  - {}".format(rec["doi"]))
    lines.append("ER  - ")
    body = "\n".join(lines)
    if punct_glyph == "tag_dash_short":
        body = body.replace("AU  - ", "AU - ", 1)
    return _apply_noise(body, rng, layer)


def render_ris(entries, layer, rng):
    out = []
    for rec in entries:
        glyph = (rec.get("_punct") or {}).get("ris")
        out.append(_render_ris_entry(rec, layer, rng, glyph))
    return "\n\n".join(out) + "\n"


RENDERERS = {"txt": render_txt, "csv": render_csv, "bib": render_bib, "ris": render_ris}


# ---- 主流程 ----


def _apply_inject(rec, kind, rng):
    if kind == "missing":
        return _inject_missing(rec, rng)
    if kind == "marker":
        return _inject_marker(rec, rng)
    if kind == "author":
        return _inject_author(rec, rng)
    if kind == "structure":
        return _inject_structure(rec, rng)
    if kind == "encoding":
        return _inject_encoding(rec)
    if kind == "punct":
        return _inject_punct(rec, rng, rng.choice(["txt", "csv", "bib", "ris"]))
    raise ValueError("未知注入类型: {}".format(kind))


def build_entries(rng):
    """72 条：每层 24 条，类型/注入模式取固定序列（真值覆盖契约），内容细节由 rng 决定。"""
    entries = []
    seq = 1
    for layer in LAYERS:
        for i, etype in enumerate(TYPE_SEQUENCE):
            rec = _mk_record(rng, seq, etype)
            rec["layer"] = layer
            spec = INJECT_SEQUENCE[i]
            injects = []
            if spec is None:
                pass
            elif spec[0] == "compound":
                for kind in spec[1:]:
                    injects.append(_apply_inject(rec, kind, rng))
            else:
                injects.append(_apply_inject(rec, spec[0], rng))
            rec["_injects"] = injects
            entries.append(rec)
            seq += 1
    return entries


def build_truth(entries):
    """真值 JSON：expect=主期望 / also_expect=伴生结论（语义见模块 docstring）。"""
    out_entries = []
    for rec in entries:
        injects = rec["_injects"]
        expect = None
        also = []
        if injects:
            first = injects[0]
            expect = {"check_type": ERROR_TAXONOMY[first["type"]]["check_type"], "field": first["field"],
                      "severity": "error", "detail": first["detail"]}
            for other in injects[1:]:
                also.append({"check_type": ERROR_TAXONOMY[other["type"]]["check_type"],
                             "field": other["field"], "detail": other["detail"]})
        out_entries.append({"entry_id": rec["entry_id"], "layer": rec["layer"], "entry_type": rec["entry_type"],
                            "lang": rec["lang"], "injects": injects, "expect": expect, "also_expect": also})
    by_layer = {layer: sum(1 for e in out_entries if e["layer"] == layer) for layer in LAYERS}
    by_type = {t: sum(1 for e in out_entries if e["entry_type"] == t) for t in ("J", "C", "D", "M", "R")}
    injected = sum(1 for e in out_entries if e["expect"] is not None)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "generator": "code/tools/gen_references.py",
        "rng": "taw.rng.SplitMix64",
        "seed": SEED,
        "truth_semantics": {
            "main_expect": "注入缺陷的主 finding 期望（check_type/field/severity），引擎对该条目必须产出",
            "also_expect": "同一注入隐含的其余非 pass 结论；复合注入为次错误期望；对账按全部非 pass 集合",
            "clean_entries": "expect=null 且 also_expect=[]，任何非 pass 判定计误报",
        },
        "error_taxonomy": {k: v["label"] for k, v in ERROR_TAXONOMY.items()},
        "doi_fake_prefix": "10.9999/",
        "counts": {"total": len(out_entries), "by_layer": by_layer, "by_type": by_type,
                   "injected": injected, "clean": len(out_entries) - injected,
                   "compound": sum(1 for e in out_entries if len(e["injects"]) > 1)},
        "entries": out_entries,
    }


def build_manifest(entries):
    files = ["refs_{}.{}".format(layer, fmt) for layer in LAYERS for fmt in FORMATS]
    enc_layers = [l for l in LAYERS if any(e.get("_encoding_mix") for e in entries if e["layer"] == l)]
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": DATASET_ID,
        "generator": "code/tools/gen_references.py",
        "rng": "taw.rng.SplitMix64",
        "seed": SEED,
        "files": files + ["refs_truth.json", "refs_manifest.json"],
        "file_expect": [{
            "scope": "file",
            "files": ["refs_{}.txt".format(l) for l in enc_layers] + ["refs_{}.csv".format(l) for l in enc_layers],
            "check_type": "citation_style",
            "detail": "含著者-出版年制条目混入顺序编码制文献表；文件级 finding 与条目级 expect 同源，不重复计",
        }],
        "noise_definition": {
            "clean": "无噪声，canonical 文本",
            "light": "单处伪影（双空格/全角括号/[ 标识 ]内空格）",
            "heavy": "2-4 处伪影（CJK 内插空格/双空格/全角数字/任意断行/连字符断裂）",
        },
    }


def _dump_json(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def generate(out_dir):
    out_dir = Path(out_dir)
    entries = build_entries(SplitMix64(SEED))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for layer in LAYERS:
        layer_entries = [e for e in entries if e["layer"] == layer]
        for fmt in FORMATS:
            # 每文件独立子 RNG（seed 由层/格式序导出），文件间内容互不耦合
            frng = SplitMix64(SEED + LAYERS.index(layer) * 1000 + FORMATS.index(fmt))
            text = RENDERERS[fmt](layer_entries, layer, frng)
            path = out_dir / "refs_{}.{}".format(layer, fmt)
            path.write_bytes(text.encode("utf-8"))
            written.append(path.name)
    (out_dir / "refs_truth.json").write_bytes(_dump_json(build_truth(entries)))
    (out_dir / "refs_manifest.json").write_bytes(_dump_json(build_manifest(entries)))
    written += ["refs_truth.json", "refs_manifest.json"]
    return sorted(written)


def main(argv=None):
    parser = argparse.ArgumentParser(description="合成文献表生成器（确定性，seed={}）".format(SEED))
    default_out = REPO_ROOT / "data" / "frozen" / "refs"
    parser.add_argument("--out", default=str(default_out), help="输出目录（默认 {}）".format(default_out))
    parser.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print("[gen_references] 目标目录非空且未给 --force，拒绝覆盖：{}".format(out_dir))
        return 1
    written = generate(out_dir)
    print("[gen_references] 写出 {} 个文件 -> {}".format(len(written), out_dir))
    for name in written:
        print("  {}".format(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
