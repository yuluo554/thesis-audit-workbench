# -*- coding: utf-8 -*-
"""docx 工具：确定性落盘（固定 zip 时间戳）+ OOXML 批注注入。

确定性纪律（plan/04 §九 10，M1 实测）：python-docx `save` 会把**当前时间**写进
zip 条目 → 同秒两次才一致。任何 docx 产物落盘后一律调 `fix_zip_timestamps`
重写 zip 为固定 1980-01-01。M6 PyInstaller 打包与 GUI 导出复用本模块。

批注（comments）：python-docx 无原生 API，故按 OOXML 注入
`word/comments.xml` + `[Content_Types].xml` 覆盖 + 文档体内 `w:commentRangeStart/
End` 与 `w:commentReference`。M6 以 Word/WPS COM 实机验证。
"""

import re
import shutil
import zipfile
from pathlib import Path

FIXED_DATE = (1980, 1, 1, 0, 0, 0)

_COMMENTS_CT = ('<Override PartName="/word/comments.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument'
                '.wordprocessingml.comments+xml"/>')

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def fix_zip_timestamps(path):
    """重写 zip：条目内容原样，时间戳固定 FIXED_DATE（跨平台字节一致）。"""
    path = Path(path)
    tmp = path.with_name(path.name + ".fix.tmp")
    shutil.move(str(path), str(tmp))
    with zipfile.ZipFile(str(tmp)) as src:
        entries = [(info.filename, src.read(info.filename)) for info in src.infolist()]
    tmp.unlink()
    with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            # create_system 随平台变（Windows=0 / Unix=3）并写进 zip "version made by"：
            # 不钉死则同一份数据在 Linux 上落盘与 Windows 差一个字节（跨平台位级一致破功）。
            info.create_system = 0
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            out.writestr(info, data)
    return str(path)


def _esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _comments_xml(comments):
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<w:comments xmlns:w="{}">'.format(_W_NS)]
    for c in comments:
        parts.append(
            '<w:comment w:id="{id}" w:author="{author}" w:initials="TW" '
            'w:date="1980-01-01T00:00:00Z"><w:p><w:r><w:t xml:space="preserve">'
            '{text}</w:t></w:r></w:p></w:comment>'.format(
                id=_esc(str(c["id"])), author=_esc(c.get("author", "taw")),
                text=_esc(c["text"])))
    parts.append("</w:comments>")
    return "".join(parts).encode("utf-8")


_CT_OVERRIDE = re.compile(r"<Override\b[^>]*/>")
_SECTPR = re.compile(r"(<w:sectPr\b)", re.I)


def add_comments(doc, comments):
    """把批注注入 python-docx 文档（内存态：comments.xml + body 标记）。

    `comments` = [{id, author, text, para}]；`para` 为段落序号（None → 挂文末）。
    """
    if not comments:
        return doc
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    body = doc.element.body
    paras = doc.paragraphs
    # 1) comments.xml part
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI
    partname = PackURI("/word/comments.xml")
    ct = ("application/vnd.openxmlformats-officedocument."
          "wordprocessingml.comments+xml")
    part = Part(partname, ct, _comments_xml(comments), doc.part.package)
    doc.part.relate_to(
        part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments")

    # 2) body: commentRangeStart/End + commentReference
    for c in comments:
        idx = c.get("para")
        target = paras[idx] if (isinstance(idx, int) and 0 <= idx < len(paras)) else paras[-1]
        p = target._p
        start = OxmlElement("w:commentRangeStart")
        start.set(qn("w:id"), str(c["id"]))
        end = OxmlElement("w:commentRangeEnd")
        end.set(qn("w:id"), str(c["id"]))
        ref_run = OxmlElement("w:r")
        ref = OxmlElement("w:commentReference")
        ref.set(qn("w:id"), str(c["id"]))
        ref_run.append(ref)
        # 插入到段落末尾（段内无 run 时也能挂住）
        p.append(start)
        p.append(end)
        p.append(ref_run)
    return doc


def _ensure_content_types(zf_in, zf_out_entries, names):
    """在 [Content_Types].xml 补 comments 覆盖（如缺）。"""
    out = []
    for name, data in zf_out_entries:
        if name == "[Content_Types].xml":
            text = data.decode("utf-8")
            if "comments+xml" not in text:
                text = text.replace("</Types>", _COMMENTS_CT + "</Types>")
            data = text.encode("utf-8")
        out.append((name, data))
    return out


def finalize_comments(path):
    """落盘收口：补 Content_Types 覆盖 + 固定时间戳。"""
    path = Path(path)
    tmp = path.with_name(path.name + ".ct.tmp")
    shutil.move(str(path), str(tmp))
    with zipfile.ZipFile(str(tmp)) as src:
        entries = [(info.filename, src.read(info.filename)) for info in src.infolist()]
    tmp.unlink()
    entries = _ensure_content_types(None, entries, None)
    with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.create_system = 0            # 跨平台字节一致（见 fix_zip_timestamps）
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            out.writestr(info, data)
    return str(path)
