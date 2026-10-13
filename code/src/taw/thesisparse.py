# -*- coding: utf-8 -*-
"""论文解析器：docx → 样式树 / REF 域 / 四类标记 → DocObjectCard（plan/04 §四 / §九）。

三类产出（对齐 thesis_truth.json 的对账面）：
  1. style_tree：逐段 {i, style, text}——text 走 python-docx `.text` 口径
     （**fldSimple 内的 run 不计入**，与 M1 真值一次锁定的口径一致）；
  2. fields：段落内 `w:fldSimple` 域 {para_index, instr, display, target_bookmark,
     bookmark_exists}——instr 形如 " REF _Ref30001 \\h "；
     书签全集来自文档 XML 的 `w:bookmarkStart/@w:name`；
  3. objects/markers：题注段（Caption 样式，或整段以 图/表/式 开头）识别对象；
     正文正则找标记（手打编号），标记落空 = 悬空，对象零提及 = 幽灵。

标签归一化：全半角破折号（—/–/－）→ '-'、中文数字变体、词内伪空格清除；
"图 3-1"/"图3－1"→ "图3-1"。

docx 依赖惰性导入；缺装时抛 RuntimeError（测试与 CLI 大声失败，不静默跳过）。
"""

import re

from taw.cards import make_doc_object

# ---- 标签与标记 ----

DASHES = "-\u2014\u2013\uff0d\u2212"  # - — – － −（含 ASCII 连字符）
_DASH_CLASS = r"\-" + DASHES[1:]
_NUM = r"\d{1,2}\s*[%s]?\s*\d{1,2}" % _DASH_CLASS
_LABEL_FIG = re.compile(r"图\s*(%s)" % _NUM)
_LABEL_TAB = re.compile(r"表\s*(%s)" % _NUM)
_LABEL_EQ = re.compile(r"式\s*\(?\s*(%s)\s*\)?" % _NUM)
_LABEL_CHAP = re.compile(r"第\s*(\d{1,2})\s*章")


def normalize_label(kind, raw_no):
    """编号归一化：破折号统一 '-'、去所有空白（含伪空格）。"""
    no = raw_no
    for d in DASHES:
        no = no.replace(d, "-")
    no = re.sub(r"\s+", "", no)
    if kind == "chapter":
        return "第{}章".format(no)
    if kind == "equation":
        return "式({})".format(no)
    return "{}{}".format("图" if kind == "figure" else "表", no)


# 正文标记（含"如图 3-1 所示"/"表 9-1"/"式(4-1)"）；题注段自身在对象识别时排除
_MARK_FIG = re.compile(r"图\s*(%s)" % _NUM)
_MARK_TAB = re.compile(r"表\s*(%s)" % _NUM)
_MARK_EQ = re.compile(r"式\s*\(?\s*(%s)\s*\)?" % _NUM)

_MARKERS = (("figure", _MARK_FIG), ("table", _MARK_TAB), ("equation", _MARK_EQ))

# REF 域显示文本形如 "图3-1"（域内 run 不进 .text，需从 instr/display 侧解析）
_FIELD_LABEL = re.compile(r"^(图|表|式)\s*\(?\s*(%s)\s*\)?" % _NUM)


def _ensure_docx():
    try:
        from docx import Document  # noqa: F401
    except ImportError:
        raise RuntimeError("缺少 python-docx：python -m pip install -e './code[docx]'")


# ---- docx 读取 ----

def read_style_tree(doc):
    """逐段 {i, style, text}（.text 口径：fldSimple 内 run 不计入）。"""
    tree = []
    for i, p in enumerate(doc.paragraphs):
        tree.append({"i": i, "style": p.style.name, "text": p.text})
    return tree


def read_fields(doc):
    """段落内 REF 域 + 书签全集 → fields 列表。"""
    bookmarks = set()
    for el in doc.element.iter():
        if el.tag.endswith("}bookmarkStart"):
            name = el.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}name")
            if name:
                bookmarks.add(name)
    fields = []
    for i, p in enumerate(doc.paragraphs):
        for fld in p._p.iter():
            if not fld.tag.endswith("}fldSimple"):
                continue
            instr = fld.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr") or ""
            m = re.search(r"REF\s+(\S+)", instr)
            target = m.group(1) if m else None
            display = "".join(t.text or "" for t in fld.iter() if t.tag.endswith("}t"))
            fields.append({
                "para_index": i,
                "instr": instr,
                "display": display.strip(),
                "target_bookmark": target,
                "bookmark_exists": bool(target) and target in bookmarks,
            })
    return fields


# ---- 对象识别 ----

_CAPTION_STOP = re.compile(r"[,，。；;：:]")


def _caption_kind(text, style):
    """题注段判定：Caption 样式，或整段"图/表编号 + 标题"——非 Caption 样式时
    含句读标点（逗号/句号/分号/冒号）即判为正文（防"表4-1给出…，式(4-1)…"误判）。"""
    t = text.strip()
    is_caption_style = style == "Caption"
    for kind, pat in (("figure", _LABEL_FIG), ("table", _LABEL_TAB)):
        m = pat.match(t)
        if not m or not t.startswith(("图", "表")):
            continue
        if is_caption_style or not _CAPTION_STOP.search(t):
            return kind, normalize_label(kind, m.group(1))
    return None


def _equation_para(text):
    """公式段落判定：形如 "F1 = 2PR/(P+R)    （3-1）" —— 末尾括号编号。"""
    m = re.search(r"[（(]\s*(\d{1,2}\s*[%s]?\s*\d{1,2})\s*[)）]\s*$" % DASHES, text)
    if m:
        return normalize_label("equation", m.group(1))
    return None


def _mentions_in_text(text, para_index, skip_span=None):
    """正文文本里的标记 → [{para_index, mode, raw, label, kind}]；mode=handwritten。"""
    out = []
    for kind, pat in _MARKERS:
        for m in pat.finditer(text):
            if skip_span and skip_span[0] <= m.start() < skip_span[1]:
                continue
            out.append({"para_index": para_index, "mode": "handwritten",
                        "raw": m.group(0),
                        "label": normalize_label(kind, m.group(1)), "kind": kind})
    return out


def parse_thesis(path):
    """docx → {style_tree, fields, objects, markers}（M2 论文解析器主入口）。"""
    _ensure_docx()
    from docx import Document

    doc = Document(str(path))
    tree = read_style_tree(doc)
    fields = read_fields(doc)

    # 域提及（display "图3-1" → 对象 label；悬空域按 target_bookmark 归组）
    field_mentions = []
    for f in fields:
        m = _FIELD_LABEL.match(f["display"])
        if m:
            kind = {"图": "figure", "表": "table", "式": "equation"}[m.group(1)]
            field_mentions.append({"para_index": f["para_index"], "mode": "ref_field",
                                   "raw": f["display"],
                                   "label": normalize_label(kind, m.group(2)),
                                   "kind": kind,
                                   "target_bookmark": f["target_bookmark"],
                                   "bookmark_exists": f["bookmark_exists"]})

    # 对象：题注段（图/表）+ 公式段
    objects = []
    caption_paras = set()
    for p in tree:
        cap = _caption_kind(p["text"], p["style"])
        if cap:
            kind, label = cap
            objects.append({"kind": kind, "label": label, "caption_para": p["i"],
                            "bookmark": None, "mentioned_paras": [], "referenced": False})
            caption_paras.add(p["i"])
            continue
        eq = _equation_para(p["text"])
        if eq:
            objects.append({"kind": "equation", "label": eq, "caption_para": p["i"],
                            "bookmark": None, "mentioned_paras": [p["i"]],
                            "referenced": True,
                            # 公式编号在段内：自身即提及（计入正文标记）
                            "_self_mention": p["i"]})

    # 书签归属：题注段挂的书签回填到对应对象
    bookmark_by_para = _bookmarks_by_para(doc)
    for obj in objects:
        bm = bookmark_by_para.get(obj["caption_para"])
        if bm:
            obj["bookmark"] = bm

    # 正文标记（手打）+ 域提及；题注段内的自身编号不计为提及
    markers = []
    for p in tree:
        if p["i"] in caption_paras:
            continue
        markers.extend(_mentions_in_text(p["text"], p["i"]))
    markers.extend(field_mentions)

    # 归属对象
    by_label = {o["label"]: o for o in objects}
    for mk in markers:
        obj = by_label.get(mk["label"])
        if obj is not None and mk["para_index"] not in obj["mentioned_paras"]:
            obj["mentioned_paras"].append(mk["para_index"])
    for obj in objects:
        obj["referenced"] = bool(obj["mentioned_paras"])
        obj.pop("_self_mention", None)
        obj["mentioned_paras"].sort()

    dangling = _dangling_markers(markers, by_label)
    ghosts = [o for o in objects if not o["referenced"]]
    return {
        "style_tree": tree,
        "fields": fields,
        "objects": objects,
        "markers": markers,
        "dangling": dangling,
        "ghosts": [{"kind": o["kind"], "label": o["label"], "caption_para": o["caption_para"]}
                   for o in ghosts],
    }


def _bookmarks_by_para(doc):
    """题注段落 → 该书签名（题注段挂载的交叉引用目标）。"""
    out = {}
    for i, p in enumerate(doc.paragraphs):
        names = []
        for el in p._p.iter():
            if el.tag.endswith("}bookmarkStart"):
                name = el.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}name")
                if name and not name.startswith("_GoBack"):
                    names.append(name)
        if names:
            out[i] = names[0]
    return out


def _dangling_markers(markers, by_label):
    """悬空标记：手打/域提及的 label 在对象集中不存在；域另有 bookmark 缺失判定。"""
    out = []
    for mk in markers:
        if mk["mode"] == "ref_field":
            if not mk.get("bookmark_exists", True):
                out.append({"kind": "ref_field", "label": mk["label"],
                            "para_index": mk["para_index"], "raw": mk["raw"],
                            "target_bookmark": mk["target_bookmark"]})
            continue
        if mk["label"] not in by_label:
            out.append({"kind": "handwritten", "label": mk["label"],
                        "para_index": mk["para_index"], "raw": mk["raw"]})
    return out


def doc_objects(parsed):
    """解析结果 → [DocObjectCard]（参数卡形态，供引擎层消费）。"""
    cards = []
    for i, o in enumerate(parsed["objects"], 1):
        cap = next((p for p in parsed["style_tree"] if p["i"] == o["caption_para"]), {})
        cards.append(make_doc_object(
            kind=o["kind"], label=o["label"],
            anchor={"para_index": o["caption_para"], "style": cap.get("style"),
                    "is_ref_field": False},
            mentions=[{"para_index": m["para_index"], "mode": m["mode"], "raw": m["raw"]}
                      for m in parsed["markers"] if m["label"] == o["label"]],
            caption={"para_index": o["caption_para"]},
            card_id="obj-{:06d}".format(i),
        ))
    return cards
