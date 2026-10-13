# -*- coding: utf-8 -*-
"""REF-08 拓扑 / REF-09 文献库与指纹 / 基准与编排守门（plan/04 §十；FR-08/09、BENCH-01）。"""

import json
from pathlib import Path

import pytest

from taw import reflib, refparse, reftopo

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
AUDIT = DATA / "frozen" / "audit"


@pytest.fixture(scope="module")
def audit_fixtures():
    _fmt, cards = refparse.parse_file(AUDIT / "refs_table.txt")
    body = (AUDIT / "body.txt").read_text(encoding="utf-8")
    return cards, body


# ---- REF-08 拓扑 ----


def test_assert_no_external_refs_rejects_cdn():
    bad = '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0/bootstrap.min.css">'
    with pytest.raises(AssertionError):
        reftopo.assert_no_external_refs(bad)
    bad2 = '<script src="//cdn.example.com/x.js"></script>'
    with pytest.raises(AssertionError):
        reftopo.assert_no_external_refs(bad2)


def test_assert_no_external_refs_accepts_inline():
    ok = '<html><style>body{color:red}</style><script>var x=1;</script></html>'
    assert reftopo.assert_no_external_refs(ok) is True


def test_render_html_passes_hard_assertion(audit_fixtures):
    cards, body = audit_fixtures
    from taw import refcite
    ctx = refcite.extract_citation_context(cards, refcite.parse_markers(body))
    html_text = reftopo.render_html(cards, ctx)
    assert reftopo.assert_no_external_refs(html_text) is True
    # 无任何外部资源标签
    import re
    assert not re.search(r'<(?:script|link|img)[^>]*(?:src|href)\s*=\s*["\']\s*(?:https?:)?//',
                         html_text, re.I)


def test_build_matrix_counts_citations(audit_fixtures):
    cards, body = audit_fixtures
    from taw import refcite
    ctx = refcite.extract_citation_context(cards, refcite.parse_markers(body))
    matrix = reftopo.build_matrix(cards, ctx)
    by_label = {m["label"]: m for m in matrix}
    assert by_label["7"]["cite_count"] == 0, "幽灵条目引用数应为 0"
    assert by_label["1"]["cite_count"] >= 1
    assert matrix == sorted(matrix, key=lambda r: (-r["cite_count"], str(r["label"] or "")))


def test_render_html_builtin_fallback(audit_fixtures, monkeypatch):
    """pyvis 缺装时的内置降级渲染器同样 0 外链。"""
    cards, body = audit_fixtures
    from taw import refcite
    ctx = refcite.extract_citation_context(cards, refcite.parse_markers(body))
    nodes = reftopo._node_payload(cards, ctx)
    html_text = reftopo._render_builtin(nodes, "测试")
    assert reftopo.assert_no_external_refs(html_text) is True
    assert "taw-topology" in html_text


# ---- REF-09 文献库 / 指纹 ----


def test_fingerprint_stable_and_order_independent(audit_fixtures):
    cards, _ = audit_fixtures
    a = reflib.manifest_fingerprint(cards)
    b = reflib.manifest_fingerprint(list(reversed(cards)))
    assert a == b, "指纹应与会话内顺序无关（防仅重排误报）"


def test_fingerprint_changes_on_content_change(audit_fixtures):
    cards, _ = audit_fixtures
    before = reflib.manifest_fingerprint(cards)
    mutated = [dict(c) for c in cards]
    mutated[0] = dict(mutated[0])
    mutated[0]["title"] = "被改动的题名"
    assert reflib.manifest_fingerprint(mutated) != before


def test_detect_tampering_reports_modified(audit_fixtures):
    cards, _ = audit_fixtures
    manifest = reflib.build_manifest(cards, "x.txt")
    assert reflib.detect_tampering(manifest, cards)["intact"] is True
    mutated = [dict(c) for c in cards]
    mutated[1] = dict(mutated[1])
    mutated[1]["title"] = "另一个题名"
    result = reflib.detect_tampering(manifest, mutated)
    assert result["intact"] is False
    assert result["modified"]


def test_detect_tampering_added_removed(audit_fixtures):
    cards, _ = audit_fixtures
    manifest = reflib.build_manifest(cards, "x.txt")
    assert reflib.detect_tampering(manifest, cards[:-1])["removed"]
    assert reflib.detect_tampering(manifest, cards + [cards[0]])["intact"] is True


def test_library_roundtrip(audit_fixtures, tmp_path):
    cards, _ = audit_fixtures
    db = tmp_path / "lib.db"
    with reflib.Library(db) as lib:
        lib.save("paper-a.txt", cards, 97.7)
        stats = lib.stats()
        assert stats["total_entries"] == len(cards)
        loaded = lib.load_paper("paper-a.txt")
        assert len(loaded) == len(cards)
        reuse = lib.find_reuse(cards[0])
        assert reuse and reuse[0]["source_doc"] == "paper-a.txt"


def test_library_cross_paper_reuse(tmp_path):
    from taw.cards import make_author, make_ref_card
    c = make_ref_card("J", [make_author("张三")], "跨论文复用题名",
                      source={"year": "2024", "container": "刊"},
                      identifiers={"doi": "10.9999/x.2024.1"},
                      evidence={"src": "p1", "ordinal": 1})
    db = tmp_path / "lib.db"
    with reflib.Library(db) as lib:
        lib.save("p1.txt", [c])
        lib.save("p2.txt", [c])
        stats = lib.stats()
    assert stats["total_entries"] == 2
    assert stats["distinct_entries"] == 1
    assert stats["reused"], "应报跨论文复用"


def test_library_sqlite_is_local_file(tmp_path):
    db = tmp_path / "lib.db"
    with reflib.Library(db) as lib:
        lib.save("p.txt", [])
    assert db.is_file(), "文献库须为本地 SQLite 文件（隐私红线：全本地零上传）"


# ---- REF-09 Word 批注回写 ----


def test_write_comments_produces_valid_deterministic_docx(tmp_path):
    """批注回写：comments.xml + body 引用齐备，重跑字节一致，docx 可重开。"""
    import zipfile

    from docx import Document

    from taw import engine, refaudit

    thesis = REPO_ROOT / "data" / "frozen" / "thesis" / "thesis_synthetic.docx"
    if not thesis.is_file():
        pytest.fail("docx fixture 缺失（环境配置错误，不允许静默跳过）")
    report = refaudit.audit_refs(AUDIT / "refs_table.txt",
                                 body_path=AUDIT / "body.txt", data_dir=DATA)
    findings = report["findings"][:3]
    assert findings, "应有 finding 用于回写"

    outs = []
    for i in (1, 2):
        out = tmp_path / "a{}.docx".format(i)
        reflib.write_comments(thesis, findings, out)
        outs.append(out.read_bytes())
    assert outs[0] == outs[1], "批注回写须确定性（zip 时间戳固定）"

    z = zipfile.ZipFile(str(tmp_path / "a1.docx"))
    assert "word/comments.xml" in z.namelist()
    assert "comments+xml" in z.read("[Content_Types].xml").decode("utf-8")
    xml = z.read("word/comments.xml").decode("utf-8")
    assert xml.count("<w:comment ") == len(findings)
    assert z.read("word/document.xml").decode("utf-8").count("commentReference") == len(findings)
    assert len(Document(str(tmp_path / "a1.docx")).paragraphs) == 62, "文档须仍可正常打开"
