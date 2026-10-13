# -*- coding: utf-8 -*-
"""参数卡与证据链 schema（plan/04 §一/§三的实现级定稿，决策记录见 plan/04 §九）。

M2 口径（骨架级 → 实现级的差异全部记录在 plan/04 §九）：
- 参数卡用 dict 构造器产出 + validate_* 校验（M0 起零依赖，不上 dataclass/pydantic）；
- 字段"宁缺"：解析不出的槽位一律 None + flag，禁止猜值硬填；
- confidence ∈ [0,1]，逐条计算（修复性 flag 扣减，缺字段扣减）；
- 证据链 finding：三级判定 pass/fail/manual_confirm，evidence 必挂 location；
  M2 只落地 schema 与构造器，判定引擎 M3/M4 接入。

 RefCard 字段（plan/04 §一 1.1 实现化）：
   card_id / entry_type / authors[{family,given,raw}] / title /
   source{container,year,volume,issue,pages,publisher,city} /
   identifiers{doi,isbn,url} / evidence{src,ordinal,label,raw} /
   confidence / flags[]
 DocObjectCard 字段（plan/04 §一 1.2 实现化）：
   card_id / kind(figure|table|equation|chapter|citation_marker) / label /
   anchor{para_index,style,is_ref_field} / mentions[{para_index,mode,raw}] /
   caption{para_index}（骨架级 caption_span 落地为单段题注位置，学位论文题注单段足够）
"""

# ---- RefCard ----

REF_ENTRY_TYPES = ("J", "C", "D", "M", "R", "N", "P", "S", "A", "DB", "OL")
DOC_OBJECT_KINDS = ("figure", "table", "equation", "chapter", "citation_marker")
FINDING_STATUS = ("pass", "fail", "manual_confirm")

REF_SOURCE_FIELDS = ("container", "year", "volume", "issue", "pages",
                     "publisher", "city", "edition", "report_no")
REF_IDENTIFIER_FIELDS = ("doi", "isbn", "url")


def make_author(raw, family=None, given=None):
    """著者项：raw 为文献表原文写法；family/given 为拆分（拆不出时为 None，宁缺）。"""
    return {"family": family, "given": given, "raw": raw}


def _strip_ws(v):
    return "".join(v.split()) if isinstance(v, str) else v


def make_ref_card(entry_type, authors, title, source=None, identifiers=None,
                  evidence=None, confidence=1.0, flags=None, card_id=None):
    """RefCard 构造器：source/identifiers 缺槽位补 None（宁缺口径的落点）。
    doi/isbn/pages/report_no 属"无空格字段"，构造期集中清除内部空白
    （噪声伪影 vs 字段本义：DOI/ISBN/页码/报告号按定义不含空格）。"""
    src = dict.fromkeys(REF_SOURCE_FIELDS)
    if source:
        src.update({k: source[k] for k in REF_SOURCE_FIELDS if k in source})
    ids = dict.fromkeys(REF_IDENTIFIER_FIELDS)
    if identifiers:
        ids.update({k: identifiers[k] for k in REF_IDENTIFIER_FIELDS if k in identifiers})
    for k in ("doi", "isbn"):
        ids[k] = _strip_ws(ids[k])
    for k in ("pages", "report_no"):
        src[k] = _strip_ws(src[k])
    ev = {"src": None, "ordinal": None, "label": None, "raw": None}
    if evidence:
        ev.update(evidence)
    card = {
        "card_id": card_id,
        "entry_type": entry_type,
        "authors": list(authors or []),
        "title": title,
        "source": src,
        "identifiers": ids,
        "evidence": ev,
        "confidence": round(float(confidence), 3),
        "flags": list(flags or []),
    }
    validate_ref_card(card)
    return card


def validate_ref_card(card):
    if card["entry_type"] is not None and card["entry_type"] not in REF_ENTRY_TYPES:
        raise ValueError("entry_type 非法: {!r}".format(card["entry_type"]))
    if not 0.0 <= card["confidence"] <= 1.0:
        raise ValueError("confidence 越界: {!r}".format(card["confidence"]))
    for a in card["authors"]:
        if "raw" not in a or not a["raw"]:
            raise ValueError("author 项缺 raw: {!r}".format(a))
    if card["evidence"]["src"] is None:
        raise ValueError("evidence.src 必填（证据链纪律：无出处不落卡）")


# ---- DocObjectCard ----

def make_doc_object(kind, label, anchor, mentions=None, caption=None, card_id=None):
    """DocObjectCard 构造器。anchor={para_index,style,is_ref_field}；
    mentions=[{para_index,mode(ref_field|handwritten),raw}]；caption={para_index}|None。"""
    card = {
        "card_id": card_id,
        "kind": kind,
        "label": label,
        "anchor": {"para_index": anchor.get("para_index"),
                   "style": anchor.get("style"),
                   "is_ref_field": bool(anchor.get("is_ref_field", False))},
        "mentions": list(mentions or []),
        "caption": caption,
    }
    validate_doc_object(card)
    return card


def validate_doc_object(card):
    if card["kind"] not in DOC_OBJECT_KINDS:
        raise ValueError("kind 非法: {!r}".format(card["kind"]))
    if not card["label"]:
        raise ValueError("label 必填（归一化标签）")
    if card["anchor"]["para_index"] is None:
        raise ValueError("anchor.para_index 必填")


# ---- 证据链 finding（plan/04 §三；M2 schema 落地，M3/M4 判定引擎消费）----

def make_finding(rule_id, status, location, clause=None, quote=None,
                 suggestion=None, confidence=1.0):
    """三级判定 finding：status ∈ pass|fail|manual_confirm；location={doc,para,span}。"""
    if status not in FINDING_STATUS:
        raise ValueError("status 非法（三级判定）: {!r}".format(status))
    return {
        "rule_id": rule_id,
        "status": status,
        "evidence": {"clause": clause, "quote": quote, "location": location},
        "suggestion": suggestion,
        "confidence": round(float(confidence), 3),
    }
