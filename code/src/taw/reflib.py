# -*- coding: utf-8 -*-
"""REF-09 本地文献库与独特功能组（plan/04 §十；FR-09）。

四件：
1. **跨论文 SQLite 文献库**（stdlib sqlite3，零依赖）：入库/检索/复用提示/常引统计；
2. **文献表指纹与篡改检测**：内容归一 SHA-256 指纹（无语义漂移的稳定指纹）+
   逐条指纹清单，任意改动可定位到具体条目；
3. **Word 批注回写**：把 findings 转成 docx comments（python-docx 可行性见 04 §十，
   缺装时报明确错误，不静默）；
4. **论文级文献体检分**：复用 REF-06 `health_score`，Lighthouse 式呈现。

隐私红线（NFR-03）：全本地，无任何网络调用。
"""

import hashlib
import json
import re
import sqlite3

SCHEMA_VERSION = 1


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_library(path):
    """建库/升级 schema（幂等）。"""
    conn = _connect(path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refs (
                card_id     TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                entry_type  TEXT,
                title       TEXT,
                container   TEXT,
                year        TEXT,
                doi         TEXT,
                isbn        TEXT,
                authors     TEXT,
                source_doc  TEXT,
                payload     TEXT NOT NULL
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                doc_fingerprint TEXT PRIMARY KEY,
                doc_name        TEXT,
                entry_count     INTEGER,
                health_score    REAL,
                payload         TEXT
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                card_id   TEXT NOT NULL,
                paper     TEXT NOT NULL,
                cites     INTEGER DEFAULT 0,
                PRIMARY KEY (card_id, paper)
            )""")
    return conn


def _norm_for_fingerprint(card):
    """指纹归一：只取语义字段，剔除证据/flag/置信度等审计元数据与顺序噪声。"""
    return json.dumps({
        "entry_type": card.get("entry_type"),
        "title": re.sub(r"\s+", "", card.get("title") or ""),
        "authors": sorted(re.sub(r"\s+", "", a.get("raw") or "")
                          for a in card.get("authors", [])),
        "source": {k: card["source"].get(k) for k in sorted(card["source"])},
        "identifiers": {k: card["identifiers"].get(k) for k in sorted(card["identifiers"])},
    }, ensure_ascii=False, sort_keys=True)


def entry_fingerprint(card):
    """单条指纹 = 语义字段归一的 SHA-256 前 16 位。"""
    return hashlib.sha256(_norm_for_fingerprint(card).encode("utf-8")).hexdigest()[:16]


def manifest_fingerprint(cards):
    """文献表指纹 = 逐条指纹排序后再哈希（与**输入顺序无关**，防"仅重排"误报）。"""
    parts = sorted(entry_fingerprint(c) for c in cards)
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("ascii"))
    return h.hexdigest()


def build_manifest(cards, doc_name=None):
    """指纹清单：{doc, count, fingerprint, entries:[{card_id,fingerprint,title}]}。"""
    entries = [{"card_id": c["card_id"], "fingerprint": entry_fingerprint(c),
                "title": c.get("title"), "label": c["evidence"].get("label")}
               for c in cards]
    return {"schema_version": SCHEMA_VERSION, "doc": doc_name,
            "count": len(cards), "fingerprint": manifest_fingerprint(cards),
            "entries": entries}


def detect_tampering(old_manifest, new_cards):
    """篡改检测：→ {unchanged, added, removed, modified}（按逐条指纹集合）。"""
    old = {e["card_id"]: e["fingerprint"] for e in old_manifest.get("entries", [])}
    new = {c["card_id"]: entry_fingerprint(c) for c in new_cards}
    old_fp = set(old.values())
    new_fp = set(new.values())
    # 指纹相同但 card_id 变化（重排/重编号）→ 视为未变
    unchanged = len(old_fp & new_fp)
    added = sorted(new_fp - old_fp)
    removed = sorted(old_fp - new_fp)
    modified = []
    for cid, fp in new.items():
        if cid in old and old[cid] != fp and fp not in old_fp:
            modified.append({"card_id": cid, "old": old[cid], "new": fp})
    return {"unchanged": unchanged, "added": added, "removed": removed,
            "modified": modified,
            "intact": not added and not removed and not modified,
            "manifest_changed": manifest_fingerprint(new_cards) != old_manifest.get("fingerprint")}


def save_paper(conn, doc_name, cards, health_score=None):
    """把一次审计的文献表存入库；返回文档指纹。"""
    manifest = build_manifest(cards, doc_name)
    with conn:
        for c in cards:
            conn.execute(
                "INSERT OR REPLACE INTO refs (card_id, fingerprint, entry_type, title,"
                " container, year, doi, isbn, authors, source_doc, payload)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (c["card_id"], entry_fingerprint(c), c.get("entry_type"), c.get("title"),
                 c["source"].get("container"), c["source"].get("year"),
                 c["identifiers"].get("doi"), c["identifiers"].get("isbn"),
                 "|".join(a.get("raw") or "" for a in c.get("authors", [])),
                 doc_name, json.dumps(c, ensure_ascii=False)))
        conn.execute(
            "INSERT OR REPLACE INTO papers (doc_fingerprint, doc_name, entry_count,"
            " health_score, payload) VALUES (?,?,?,?,?)",
            (manifest["fingerprint"], doc_name, len(cards), health_score,
             json.dumps(manifest, ensure_ascii=False)))
    return manifest["fingerprint"]


def library_stats(conn):
    """跨论文库统计：总数 / 去重后 / 常引（按 DOI 或标题归并）。"""
    cur = conn.execute("SELECT COUNT(*) FROM refs")
    total = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(DISTINCT fingerprint) FROM refs")
    distinct = cur.fetchone()[0]
    cur = conn.execute("""SELECT title, container, year, COUNT(*) c FROM refs
                          GROUP BY fingerprint HAVING c > 1 ORDER BY c DESC, title""")
    reused = [{"title": r[0], "container": r[1], "year": r[2], "count": r[3]}
              for r in cur.fetchall()]
    return {"total_entries": total, "distinct_entries": distinct, "reused": reused}


def find_reuse(conn, card):
    """复用提示：该文献在其他论文中出现过（按指纹）。"""
    fp = entry_fingerprint(card)
    cur = conn.execute("SELECT card_id, source_doc FROM refs WHERE fingerprint = ?", (fp,))
    return [{"card_id": r[0], "source_doc": r[1]} for r in cur.fetchall()]


class Library:
    """本地文献库句柄（with 用法；close 幂等）。"""

    def __init__(self, path):
        self.path = str(path)
        self.conn = init_library(path)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def save(self, doc_name, cards, health_score=None):
        return save_paper(self.conn, doc_name, cards, health_score)

    def stats(self):
        return library_stats(self.conn)

    def find_reuse(self, card):
        return find_reuse(self.conn, card)

    def load_paper(self, doc_name):
        cur = self.conn.execute("SELECT payload FROM refs WHERE source_doc = ?", (doc_name,))
        return [json.loads(r[0]) for r in cur.fetchall()]


# ---- Word 批注回写（docx comments）----

def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("批注回写需要 docx extras：pip install -e './code[docx]'（{}）".format(exc))


def write_comments(docx_path, findings, out_path=None):
    """把 findings 回写为 Word 批注（python-docx）。

    实现方式：python-docx 无原生 comments API，故以 OOXML 直接注入
    `word/comments.xml` 与 `w:commentReference`（M6 实机验证 COM 通路）。
    此处实现文件级落盘；docx 落盘后重写 zip 固定时间戳（确定性纪律，plan/04 §九 10）。
    返回写出路径。
    """
    _require_docx()
    from docx import Document
    from taw import docxutil

    docx_path = str(docx_path)
    out_path = str(out_path or docx_path)
    doc = Document(docx_path)
    comments = []
    for i, f in enumerate(findings, 1):
        loc = (f.get("evidence", {}).get("location") or {})
        para_idx = loc.get("para")
        text = "[{}] {}: {}".format(f.get("check_type") or f.get("rule_id"),
                                    f.get("status"), f.get("detail") or f.get("suggestion") or "")
        comments.append({"id": str(i), "author": "taw", "text": text,
                         "para": para_idx})
    docxutil.add_comments(doc, comments)
    doc.save(out_path)
    docxutil.finalize_comments(out_path)
    return out_path
