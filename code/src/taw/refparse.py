# -*- coding: utf-8 -*-
"""REF-01 噪声鲁棒文献解析器：txt/csv/bib/ris → RefCard（plan/04 §一 1.1 / §九）。

噪声清洗管线（顺序敏感，全部记 flag）：
  1. 断行合并（任意断行 join；连字符断裂去 '-' 拼接）—— flags: linebreak_repaired/hyphen_repaired
  2. 全半角归一（U+FF01-FF5E / 全角空格）—— flag: fullwidth_normalized
  3. 中文标点归一（，→", "、：→": "，仅文献表语料；正文语料不适用）—— flag: fullwidth_punct_normalized
  4. 空格伪影（多空格压缩 / CJK 字间空格清除 / 年份断字修复）—— flags: space_collapsed/
     cjk_space_collapsed/year_space_repaired
宁缺纪律：字段解析不出 → None + 低置信 flag，绝不猜值；confidence 逐条扣减
（修复 flag -0.02、缺期望字段 -0.08、无类型标识 -0.15，截断到 [0,1]）。

对账口径（f1bench 消费，plan/04 §九）：
- F1 逐字段比较"解析值 vs 生成器重建的逻辑记录"（post-injection，build_entries 确定性重建）；
- entry_type 不进 F1（文献类型标识错误是 M3 审计 finding，不是解析错误），仅报告一致率；
- 真值声明 punct 注入命中本格式的条目从严格 F1 剔除、单独报 punct_damaged 桶
  （标点损伤是审计素材，不是解析器缺陷）；
- 著者截断语义：>3 著者按 GB/T 渲染为前三+等（文本中不存在第 4+ 著者）→
  尾部著者不计 FN，记 authors_truncated flag。
"""

import re

from taw.cards import make_author, make_ref_card

# ---- 清洗管线 ----

_CJK = r'\u4e00-\u9fff'

_REPAIR_FLAGS_ORDER = (
    "linebreak_repaired", "hyphen_repaired", "fullwidth_normalized",
    "fullwidth_punct_normalized", "space_collapsed", "cjk_space_collapsed",
    "year_space_repaired",
)


def normalize_fullwidth(text):
    """全角 ASCII 区（！-～）与全角空格 → 半角。有变化记 fullwidth_normalized。"""
    out = []
    changed = False
    for ch in text:
        o = ord(ch)
        if ch == "\u3000":
            out.append(" ")
            changed = True
        elif 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
            changed = True
        else:
            out.append(ch)
    return ("".join(out), changed)


def clean_text(text, flags, for_refs=True):
    """段内清洗管线（断行已在上层合并）。返回清洗后文本。"""
    t, changed = normalize_fullwidth(text)
    if changed:
        flags.append("fullwidth_normalized")
    if for_refs:
        if "，" in t:
            t = t.replace("，", ", ")
            flags.append("fullwidth_punct_normalized")
        if "：" in t:
            t = t.replace("：", ": ")
            flags.append("fullwidth_punct_normalized")
    t2 = re.sub(r"[ \t\u3000]{2,}", " ", t)
    if t2 != t:
        flags.append("space_collapsed")
    t = t2
    t2 = re.sub(r"(?<=[{}]) +(?=[{}])".format(_CJK, _CJK), "", t)
    if t2 != t:
        flags.append("cjk_space_collapsed")
    t = t2
    t2 = re.sub(r"((?:19|20)) ((?:\d{2}))(?!\d)", r"\1\2", t)
    if t2 != t:
        flags.append("year_space_repaired")
    t = t2
    return t.strip()


def join_broken_lines(lines):
    """断行合并：行尾连字符断裂去 '-' 拼接（hyphen_repaired），其余直接拼接
    （linebreak_repaired）。返回 (合并文本, 去重后 flags)。"""
    parts = []
    flags = []
    for ln in lines:
        ln = ln.rstrip("\r")
        if not ln.strip():
            continue
        if parts and parts[-1].endswith("-"):
            parts[-1] = parts[-1][:-1] + ln
            if "hyphen_repaired" not in flags:
                flags.append("hyphen_repaired")
        else:
            if parts and "linebreak_repaired" not in flags:
                flags.append("linebreak_repaired")
            parts.append(ln)
    return "".join(parts), flags


# ---- txt / csv（GB/T 7714 顺序编码制引文行）----

_LABEL_HEAD = re.compile(r"^\[\s*(\d{1,3}(?:\s+\d{1,3})*)\s*\]\s*")
_MARKER_BRACKET = re.compile(r"\[\s*([A-Z]{1,3})\s*\]")
_MIX_HEAD = re.compile(r"^(?P<auth>.+?),\s*(?P<yr>(?:19|20)\d{2})\.\s*(?P<title>.+)$")
# 无编号（著者-出版年制）条目粘在前一条目尾部时的切分锚：著者段（不含句点/方括号）
# + ", 年份." + 题名 + [标识]
_MIX_TAIL = re.compile(
    r"[A-Z\u4e00-\u9fff][^.,\[\]]*(?:,\s*[A-Z\u4e00-\u9fff][^.,\[\]]*)*"
    r",\s*(?:19|20)\d{2}\.\s*[^\[\]]+\[")
_REPORT_NO_TAIL = re.compile(r"[.,]?\s*([A-Z]{1,6}\s*-\s*\d{2,4}\s*-\s*\d{1,4})\s*\.?\s*$")
_PAGES_TAIL = re.compile(r"[:：]\s*(\d{1,4})\s*[-\u2013\u2014]\s*(\d{1,4})\s*\.?\s*$")
_EDITION_SEG = re.compile(r"^(\d+)\s*(?:\u7248|ed)\.?$")
_SEG_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_SEG_VOL_ISSUE = re.compile(r"^(\d+)\((\d+)\)$")
_SEG_ISSUE = re.compile(r"^\((\d+)\)$")
_SEG_VOL = re.compile(r"^(\d+)$")
_ET_AL = ("等", "et al")


def split_txt_entries(raw_text):
    """整篇 txt → [(label|None, 条目文本, flags)]。

    两阶段（口径关键）：先在**原始行**上按 [n] 标签切片，再对**每条自己的行**做
    断行合并——这样 linebreak_repaired 只在"某条目真的跨行"时记，而不是把
    "文件有多行"误报成噪声（clean 文件的 confidence 不被系统性压低）。
    无编号（著者-出版年制）条目粘在前一标签条目尾部，按 _MIX_TAIL 锚切出。
    """
    lines = raw_text.replace("\r\n", "\n").split("\n")
    chunks = []   # [(label|None, [行...])]
    for ln in lines:
        if not ln.strip():
            continue
        m = _LABEL_HEAD.match(ln.strip())
        if m:
            chunks.append((re.sub(r"\s+", "", m.group(1)),
                           [ln.strip()[m.end():]]))
        elif chunks:
            chunks[-1][1].append(ln)
        else:
            chunks.append((None, [ln]))
    entries = []
    for label, chunk_lines in chunks:
        joined, flags = join_broken_lines(chunk_lines)
        body = clean_text(joined, flags)
        cut = _MIX_TAIL.search(body)
        if cut:
            entries.append((label, body[:cut.start()].strip(), flags))
            entries.append((None, body[cut.start():].strip(), flags))
        else:
            entries.append((label, body.strip(), flags))
    return entries


def split_authors(head):
    """著者串 → (names[raw], et_al_flag)。切分符 ', '；末位 等/et al 摘出。"""
    names = []
    et_al = False
    for token in head.split(", "):
        token = token.strip()
        if not token:
            continue
        if token in _ET_AL:
            et_al = True
            continue
        names.append(token)
    return names, et_al


def _split_head(head):
    """head → (authors_raw_text, title)。分隔符 = 首个 '. '（著者内不含句点，
    et al 的句点即分隔点；解析不出 → (head, None) 宁缺）。"""
    pos = head.find(". ")
    if pos < 0:
        if head.endswith("."):
            pos = len(head) - 1
    if pos < 0:
        return head, None
    return head[:pos].strip(), head[pos + 1:].strip() or None


def _walk_body(body, marker, flags):
    """主体段字段抽取：先剥 报告号/页码，再按段（', ' 分隔）赋值。

    body 类型按**结构推断**（文献类型标识可能被误标——注入缺陷之一，不能信）：
    '//' 前缀→C；报告号→R；版次段→M；卷期段→J；其余→marker（D/M_edition1 分歧）。
    段语义：年份段/卷期段通用；含 ': ' 的段 = city: X，X 按 body 类型归
    publisher（C/M）或 container（D/R）；无冒号首段：C/M=city（缺出版社注入）、
    其余=container。
    """
    out = dict.fromkeys(("container", "year", "volume", "issue", "pages",
                         "publisher", "city", "edition", "report_no"), None)
    b = body.strip().lstrip(".\u3002\uff0c, ").strip()
    if not b:
        return out
    kind = None
    if b.startswith("//"):
        kind = "C"
        b = b[2:].strip()
    if kind is None:
        m = _REPORT_NO_TAIL.search(b)
        if m:
            kind = "R"
    if kind is None:
        first_m = _EDITION_SEG.match(b.split(", ")[0]) if b.split(", ")[0] else None
        if first_m:
            kind = "M"
    if kind is None:
        for seg in b.split(", "):
            if _SEG_VOL_ISSUE.match(seg) or _SEG_ISSUE.match(seg) or _SEG_VOL.match(seg):
                kind = "J"
                break
    if kind is None:
        kind = marker if marker in ("J", "C", "D", "M", "R") else "D"
    m = _REPORT_NO_TAIL.search(b)
    if m:
        out["report_no"] = re.sub(r"\s+", "", m.group(1))
        b = b[:m.start()].strip().rstrip(" .,，").strip()
    m = _PAGES_TAIL.search(b)
    if m:
        out["pages"] = "{}-{}".format(m.group(1), m.group(2))
        b = b[:m.start()].strip().rstrip(" .,，").strip()
    segs = [s.strip() for s in b.split(", ") if s.strip()]
    if segs and _EDITION_SEG.match(segs[0]):
        out["edition"] = _EDITION_SEG.match(segs[0]).group(1)
        segs = segs[1:]
    if not segs:
        return out
    first, rest = segs[0], segs[1:]

    def _assign_colon(seg):
        city, _, tail = seg.partition(":")
        city, tail = city.strip(), tail.strip()
        if city and not out["city"]:
            out["city"] = city
        if tail:
            if kind in ("C", "M"):
                if not out["publisher"]:
                    out["publisher"] = tail
            elif not out["container"]:
                out["container"] = tail

    if ":" in first:
        _assign_colon(first)
    elif kind in ("C", "M") and not any(":" in s for s in rest):
        out["city"] = first  # C/M 缺出版社注入时首段 = city
    else:
        out["container"] = first
    for seg in rest:
        seg = seg.rstrip(".")
        if _SEG_YEAR.match(seg):
            out["year"] = seg
        elif _SEG_VOL_ISSUE.match(seg):
            mm = _SEG_VOL_ISSUE.match(seg)
            out["volume"], out["issue"] = mm.group(1), mm.group(2)
        elif _SEG_ISSUE.match(seg):
            out["issue"] = _SEG_ISSUE.match(seg).group(1)
        elif _SEG_VOL.match(seg):
            out["volume"] = seg
        elif ":" in seg:
            _assign_colon(seg)
        elif not out["city"]:
            out["city"] = seg  # C 缺出版社注入时 rest 中夹的城市段
        else:
            flags.append("body_unparsed_segment")
    return out


def parse_citation(text, src_name, ordinal, label=None, base_flags=None,
                   card_id=None):
    """单条引文文本 → RefCard（宁缺：解析不出 = None + flag）。"""
    flags = list(base_flags or [])
    t = text.strip().rstrip(" ,.，。").strip() if text else ""
    card = dict.fromkeys(("title", "container", "year", "volume", "issue", "pages",
                          "publisher", "city", "edition", "report_no", "doi",
                          "isbn"), None)
    authors_raw = []
    et_al = False
    marker = None
    if not t:
        flags.append("empty_entry")
    else:
        m = _MARKER_BRACKET.search(t)
        if m:
            marker = m.group(1)
            head, body = t[:m.start()].strip(), t[m.end():].strip()
            auth_txt = None
            mm = _MIX_HEAD.match(head)  # 著者-出版年制：著者, 年. 题名（主体不重复年份）
            if mm:
                card["year"] = mm.group("yr")
                auth_txt = mm.group("auth")
                card["title"] = mm.group("title").strip() or None
                flags.append("author_year_form")
            else:
                auth_txt, title = _split_head(head)
                if title is None:
                    flags.append("authors_title_separator_missing")
                card["title"] = title
            authors_raw, et_al = split_authors(auth_txt or "")
            body_fields = _walk_body(body, marker, flags)
            for k, v in body_fields.items():
                if card.get(k) is None:
                    card[k] = v
        else:
            flags.append("no_type_marker")
    authors = []
    for raw in authors_raw:
        family, given = _split_name(raw)
        authors.append(make_author(raw, family=family, given=given))
    # confidence：修复 flag 扣减 + 期望字段缺失扣减 + 无标识重扣
    conf = 1.0
    for f in flags:
        if f in _REPAIR_FLAGS_ORDER:
            conf -= 0.02
    if marker is None:
        conf -= 0.15
    if et_al:
        flags.append("authors_truncated")
        conf -= 0.02
    missing = _expected_missing(card, marker, len(authors))
    conf -= 0.08 * missing
    conf -= 0.03 * len([f for f in flags if f in
                        ("authors_title_separator_missing", "body_unparsed_segment")])
    conf = max(0.0, min(1.0, conf))
    return make_ref_card(
        entry_type=marker,
        authors=authors,
        title=card["title"],
        source={k: card[k] for k in ("container", "year", "volume", "issue",
                                     "pages", "publisher", "city", "edition",
                                     "report_no")},
        identifiers={"doi": card["doi"], "isbn": card["isbn"], "url": None},
        evidence={"src": src_name, "ordinal": ordinal, "label": label,
                  "raw": text},
        confidence=conf,
        flags=flags,
        card_id=card_id,
    )


def _expected_missing(card, marker, n_authors):
    """期望字段缺失计数（confidence 扣减用；marker 未知时只查著者与题名）。
    authors/title 单独判——card 是**字段值 dict**，不含这两项，用 key 查会虚扣。"""
    keys = _EXPECTED_BY_MARKER.get(marker, ())
    n = 0 if n_authors else 1
    if not card["title"]:
        n += 1
    for k in keys:
        if card.get(k) is None:
            n += 1
    return n


def _split_name(raw):
    """raw → (family, given)：中文取首字为姓；西文取首 token 为姓。拆不出给 None。"""
    if not raw:
        return None, None
    if "," in raw:  # bib 西文 "Family, Given"
        fam, _, giv = raw.partition(",")
        return fam.strip(), giv.strip() or None
    parts = raw.split(" ")
    if len(parts) == 1:
        if re.match(r"^[\u4e00-\u9fff]+$", raw):
            return raw[0], raw[1:] or None
        return raw, None
    return parts[0], " ".join(parts[1:])


_EXPECTED_BY_MARKER = {
    "J": ("container", "year"),
    "C": ("container", "year"),
    "D": ("container", "year"),
    "M": ("year",),
    "R": ("container", "year"),
}


def parse_txt(raw_text, src_name="refs.txt"):
    """整篇 txt → [RefCard]（顺序 = 文档条目顺序）。"""
    cards = []
    for i, (label, body, flags) in enumerate(split_txt_entries(raw_text), 1):
        cards.append(parse_citation(body, src_name, i, label=label,
                                    base_flags=flags,
                                    card_id="ref-{:06d}".format(i)))
    return cards


def parse_csv(raw_text, src_name="refs.csv"):
    """csv（no,entry_id,entry_type,citation）→ [RefCard]；citation 列走 txt 同款
    清洗（单元格内也可能有断行/连字符噪声——csv writer 引号保住了它们）。"""
    import csv as _csv
    import io

    reader = _csv.reader(io.StringIO(raw_text))
    rows = list(reader)
    cards = []
    for i, row in enumerate(rows[1:], 1):  # 首行表头
        if not row or not "".join(row).strip():
            continue
        no, entry_id, _etype_declared, citation = (list(row) + ["", "", "", ""])[:4]
        joined, flags = join_broken_lines(citation.replace("\r\n", "\n").split("\n"))
        text = clean_text(joined, flags)
        label = None
        m = _LABEL_HEAD.match(text)
        if m:
            label = re.sub(r"\s+", "", m.group(1))
            text = text[m.end():].strip()
        cards.append(parse_citation(text, src_name, int(no) if no else i,
                                    label=label, base_flags=flags,
                                    card_id=entry_id or None))
    return cards


# ---- bib ----

BIB_TYPE_MAP = {"article": "J", "inproceedings": "C", "conference": "C",
                "phdthesis": "D", "mastersthesis": "D", "book": "M",
                "techreport": "R", "report": "R"}
_BIB_HEAD = re.compile(r"@\s*([A-Za-z]+(?:\s+[A-Za-z]+)*)\s*\{\s*([^,{}]+?)\s*,")
_BIB_FIELD = re.compile(r"([A-Za-z]+(?:\s+[A-Za-z]+)*)\s*=\s*\{([^{}]*)\}")


def _bib_key_norm(k):
    """bib 键/类型词内的噪声空格清除（"artic le"→"article"）。"""
    return re.sub(r"\s+", "", k)


_BIB_STRUCT_LINE = re.compile(r"^\s*(?:@|[A-Za-z]+\s*=|\})\s*,?\s*$|^\s*[A-Za-z]+\s*=")


def _join_block(block_lines, struct_pat):
    """块内合并：区分**结构换行**（匹配 struct_pat，格式本就多行）与**续行**
    （值被噪声折断）。只为续行记 linebreak_repaired/hyphen_repaired——
    否则 clean 的 bib/ris 每条都会被误标"噪声修复"、confidence 被系统性压低。"""
    parts = []
    flags = []
    for ln in block_lines:
        ln = ln.rstrip("\r")
        if not ln.strip():
            continue
        is_struct = bool(struct_pat.match(ln))
        if parts and not is_struct:
            if parts[-1].endswith("-"):
                parts[-1] = parts[-1][:-1] + ln.lstrip()
                if "hyphen_repaired" not in flags:
                    flags.append("hyphen_repaired")
            else:
                parts[-1] = parts[-1] + ln.lstrip()
                if "linebreak_repaired" not in flags:
                    flags.append("linebreak_repaired")
        else:
            parts.append(ln)
    return "".join(parts), flags


def parse_bib(raw_text, src_name="refs.bib"):
    """bib → [RefCard]。字段行缺逗号（punct 注入）不影响解析（按 key= 切）。
    按 @ 头条目在**原始行**上分块；块内只有"续行"被计为噪声修复。"""
    lines = raw_text.replace("\r\n", "\n").split("\n")
    chunk_lines = []
    chunks = []
    for ln in lines:
        if ln.lstrip().startswith("@"):
            if chunk_lines:
                chunks.append(chunk_lines)
            chunk_lines = [ln]
        elif chunk_lines:
            chunk_lines.append(ln)
    if chunk_lines:
        chunks.append(chunk_lines)
    cards = []
    idx = 0
    for block in chunks:
        blob, flags = _join_block(block, _BIB_STRUCT_LINE)
        blob = clean_text(blob, flags)
        m = _BIB_HEAD.search(blob)
        if not m:
            continue
        idx += 1
        btype, key = _bib_key_norm(m.group(1)).lower(), _bib_key_norm(m.group(2))
        fields = {_bib_key_norm(k): v.strip()
                  for k, v in _BIB_FIELD.findall(blob[m.end():])}
        cards.append(_bib_entry_to_card(btype, key, fields, src_name, idx, flags))
    return cards


def _bib_entry_to_card(btype, key, fields, src_name, ordinal, base_flags):
    flags = list(base_flags)
    marker = BIB_TYPE_MAP.get(btype)
    if marker is None:
        flags.append("unknown_bib_type")
    authors_raw = []
    et_al = False
    for name in (fields.get("author") or "").split(" and "):
        name = name.strip()
        if not name:
            continue
        if name == "others":
            et_al = True
            continue
        authors_raw.append(name)
    card = {
        "title": fields.get("title") or None,
        "container": (fields.get("journal") or fields.get("booktitle")
                      or fields.get("school") or fields.get("institution") or None),
        "year": fields.get("year") or None,
        "volume": fields.get("volume") or None,
        "issue": None,
        "pages": fields.get("pages") or None,
        "publisher": fields.get("publisher") or None,
        "city": fields.get("address") or None,
        "edition": fields.get("edition") or None,
        "report_no": None,
        "doi": fields.get("doi") or None,
        "isbn": fields.get("isbn") or fields.get("sn") or None,
    }
    # number 字段按内容分派（marker 可能被误标，不可信）：报告号模式 → report_no，否则 issue
    num = fields.get("number") or None
    if num:
        if re.match(r"^[A-Z]{1,6}-\d{2,4}-\d{1,4}$", num):
            card["report_no"] = num
        else:
            card["issue"] = num
    authors = [make_author(r, family=_split_name(r)[0], given=_split_name(r)[1])
               for r in authors_raw]
    conf = 1.0
    for f in flags:
        if f in _REPAIR_FLAGS_ORDER:
            conf -= 0.02
    if marker is None:
        conf -= 0.15
    if et_al:
        flags.append("authors_truncated")
        conf -= 0.02
    conf -= 0.08 * sum(1 for v in (card["title"], card["year"]) if not v)
    conf = max(0.0, min(1.0, conf))
    return make_ref_card(
        entry_type=marker,
        authors=authors,
        title=card["title"],
        source={k: card[k] for k in ("container", "year", "volume", "issue",
                                     "pages", "publisher", "city", "edition",
                                     "report_no")},
        identifiers={"doi": card["doi"], "isbn": card["isbn"], "url": None},
        evidence={"src": src_name, "ordinal": ordinal, "label": key, "raw": None},
        confidence=conf,
        flags=flags,
        card_id="ref-{:06d}".format(ordinal),
    )


# ---- ris ----

RIS_TYPE_MAP = {"JOUR": "J", "CONF": "C", "CPAPER": "C", "THES": "D",
                "BOOK": "M", "RPRT": "R", "REPORT": "R"}
_RIS_TAG = re.compile(r"([A-Z])\s?([A-Z0-9])\s+-\s?")

_KNOWN_ARTIFACTS = {
    "ris_none_value": "M1 生成器把缺失字段渲染为字面 'None'（ris 专用伪影，解析归一为缺失）",
}


def _clean_value(v, flags):
    """ris 标签值清洗：全角/空格伪影；字面 'None' → None（生成器已知伪影）。"""
    if v is None:
        return None
    v = clean_text(v, flags)
    if v == "None" or v == "":
        flags.append("ris_none_value_artifact")
        return None
    return v


_RIS_STRUCT_LINE = re.compile(r"^\s*[A-Z][A-Z0-9]?\s?[A-Z0-9]?\s+-\s?")
_RIS_LONE_FRAGMENT = re.compile(r"^[A-Z]$")
_RIS_TAG_TAIL = re.compile(r"^\s*[A-Z0-9]?\s+-\s?")


def _ris_merge_split_tags(lines):
    """预修复：标签被噪声换行劈开（"A" / "U  - name"）→ 合并回 "AU  - name"。"""
    out = []
    flags = []
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip("\r")
        if (_RIS_LONE_FRAGMENT.match(ln.strip()) and i + 1 < len(lines)
                and _RIS_TAG_TAIL.match(lines[i + 1])):
            out.append(ln.strip() + lines[i + 1].lstrip())
            if "linebreak_repaired" not in flags:
                flags.append("linebreak_repaired")
            i += 2
            continue
        out.append(ln)
        i += 1
    return out, flags


def _ris_blocks(raw_text):
    """ris 全文 → ([(tag, value, flags)] 序列, all_flags)：按 TY 行在原始行上分块；
    块内先修复被劈开的标签，再用结构行感知合并（只有真续行记噪声 flag）。"""
    lines = raw_text.replace("\r\n", "\n").split("\n")
    chunks = []
    cur = None
    for ln in lines:
        if ln.strip().startswith("TY"):
            cur = [ln]
            chunks.append(cur)
        elif cur is not None:
            cur.append(ln)
    tagged = []
    all_flags = []
    for block in chunks:
        merged, pre_flags = _ris_merge_split_tags(block)
        blob, flags = _join_block(merged, _RIS_STRUCT_LINE)
        for f in pre_flags:
            if f not in flags:
                flags.append(f)
        matches = list(_RIS_TAG.finditer(blob))
        for i, m in enumerate(matches):
            val_end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
            val = blob[m.end():val_end].strip()
            if val.endswith("-"):  # 值尾悬挂连字符 = 断行注入残留
                val = val[:-1].rstrip()
                if "hyphen_repaired" not in flags:
                    flags.append("hyphen_repaired")
            tagged.append((m.group(1) + m.group(2), val, list(flags)))
        for f in flags:
            if f not in all_flags:
                all_flags.append(f)
    return tagged, all_flags


def parse_ris(raw_text, src_name="refs.ris"):
    """ris（TY..ER 块）→ [RefCard]。SP/EP 合并为 pages；字面 'None' 值归一为缺失。"""
    tagged, join_flags = _ris_blocks(raw_text)
    blocks = []
    cur = None
    for tag, val, flags in tagged:
        if tag == "TY":
            cur = []
            blocks.append((cur, flags))
        if cur is not None:
            cur.append((tag, val))
    cards = []
    for i, (block, flags) in enumerate(blocks, 1):
        cards.append(_ris_block_to_card(block, src_name, i, flags))
    return cards


def _ris_block_to_card(block, src_name, ordinal, base_flags):
    flags = list(base_flags)
    val = {}
    for tag, v in block:
        v = _clean_value(v, flags)
        if v is not None:
            val.setdefault(tag, []).append(v)
    marker = RIS_TYPE_MAP.get((val.get("TY") or [""])[0])
    if marker is None:
        flags.append("unknown_ris_type")
    sp, ep = (val.get("SP") or [None])[0], (val.get("EP") or [None])[0]
    pages = "{}-{}".format(sp, ep) if sp and ep else (sp or None)
    # container/publisher 按标签存在性判定（marker 可能被误标，不可信）：
    # 有 JO/T2 → 它是 container、PB 是 publisher；PB 独占时按 NO（R）/SN（M）
    # 区分——M 恒有 SN、R 恒有 NO、D 两者皆无。
    jo = (val.get("JO") or val.get("JF") or [None])[0]
    t2 = (val.get("T2") or [None])[0]
    pb = (val.get("PB") or [None])[0]
    container = publisher = None
    if jo or t2:
        container = jo or t2
        publisher = pb
    elif pb is not None:
        if val.get("SN") and not val.get("NO"):
            publisher = pb
        else:
            container = pb
    card = {
        "title": (val.get("TI") or [None])[0],
        "container": container,
        "year": (val.get("PY") or [None])[0],
        "volume": (val.get("VL") or [None])[0],
        "issue": (val.get("IS") or [None])[0],
        "pages": pages,
        "publisher": publisher,
        "city": (val.get("CY") or [None])[0],
        "edition": None,  # ris 无 edition 标签（载体语义，见 plan/04 §九）
        "report_no": (val.get("NO") or [None])[0],
        "doi": (val.get("DO") or [None])[0],
        "isbn": (val.get("SN") or [None])[0],
    }
    authors = []
    for r in val.get("AU", []):
        family, given = _split_name(r)
        authors.append(make_author(r, family=family, given=given))
    conf = 1.0
    for f in flags:
        if f in _REPAIR_FLAGS_ORDER:
            conf -= 0.02
    if marker is None:
        conf -= 0.15
    conf -= 0.08 * sum(1 for v in (card["title"], card["year"]) if not v)
    conf = max(0.0, min(1.0, conf))
    return make_ref_card(
        entry_type=marker,
        authors=authors,
        title=card["title"],
        source={k: card[k] for k in ("container", "year", "volume", "issue",
                                     "pages", "publisher", "city", "edition",
                                     "report_no")},
        identifiers={"doi": card["doi"], "isbn": card["isbn"], "url": None},
        evidence={"src": src_name, "ordinal": ordinal, "label": None, "raw": None},
        confidence=conf,
        flags=flags,
        card_id="ref-{:06d}".format(ordinal),
    )


# ---- 统一入口 ----

PARSERS = {"txt": parse_txt, "csv": parse_csv, "bib": parse_bib, "ris": parse_ris}
FORMAT_BY_SUFFIX = {".txt": "txt", ".csv": "csv", ".bib": "bib", ".ris": "ris"}


def detect_format(path):
    from pathlib import Path
    suffix = Path(str(path)).suffix.lower()
    return FORMAT_BY_SUFFIX.get(suffix)


def parse_file(path, fmt=None):
    """文件 → (format, [RefCard])；fmt=None 时按扩展名探测（未知 → ValueError）。"""
    from pathlib import Path
    p = Path(str(path))
    fmt = fmt or detect_format(p)
    if fmt not in PARSERS:
        raise ValueError("无法识别的文献表格式: {!r}（支持 txt/csv/bib/ris）".format(fmt))
    text = p.read_text(encoding="utf-8")
    return fmt, PARSERS[fmt](text, src_name=p.name)
