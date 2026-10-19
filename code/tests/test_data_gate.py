"""数据面守门（M1 DoD：CR 守门 / 位级一致守门 / 真值与知识库纪律）。

- CR 守门：data/frozen/ 任何文件出现 CR 即大声失败（对抗本机 autocrlf=true
  检出污染，plan/03 §五第 2 条）；
- 位级一致守门：把两个生成器各重跑一遍，与入仓冻结文件逐字节比对——
  生成器被"顺手改了输出"或运行环境引入随机性时在此拦下；
- 真值纪律：refs 真值六类错误全覆盖、clean 条目零期望；thesis 真值与
  style_tree/objects 自洽；ruleset/条款库无出处不落库（pending 不生效）。
"""

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
FROZEN = DATA / "frozen"
REFS = FROZEN / "refs"
THESIS = FROZEN / "thesis"
AUDIT = FROZEN / "audit"
REVIEW = FROZEN / "review"
BENCH = DATA / "bench" / "halluref"

sys.path.insert(0, str(REPO_ROOT / "code" / "src"))
sys.path.insert(0, str(REPO_ROOT / "code" / "tools"))

import gen_references  # noqa: E402
import gen_thesis_docx  # noqa: E402
import gen_audit_fixtures  # noqa: E402
import gen_halluref_bench  # noqa: E402
import gen_review_corpus  # noqa: E402


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("M1 守门需要 docx extras：python -m pip install -e './code[docx]'（{}）。"
                    "CI 已随 dev 一并安装；本地缺装=环境配置错误，不允许静默跳过。".format(exc))


def _generate_to_tmp(module, tmp_path):
    out = tmp_path / module.__name__
    module.generate(out)
    return out


# ---- CR 守门 ----


def test_frozen_files_have_no_cr():
    """冻结纪律：data/ 下全部文本件无 CR（含 M3 新增 audit/ 与 halluref 全量库）。"""
    frozen_files = sorted(p for p in FROZEN.rglob("*") if p.is_file())
    frozen_files += sorted(p for p in BENCH.rglob("*") if p.is_file())
    assert frozen_files, "data/frozen/ 为空：生成器未运行？"
    offenders = []
    for p in frozen_files:
        blob = p.read_bytes()
        if b"\x00" in blob:
            continue  # 二进制（docx 压缩流合法含 \r）；git 对其不做 eol 转换
        if b"\r" in blob:
            offenders.append(str(p.relative_to(REPO_ROOT)))
    assert not offenders, "冻结文本文件出现 CR（autocrlf 检出污染？）：{}".format(offenders)


# ---- 位级一致守门 ----


def test_refs_regeneration_bit_identical(tmp_path):
    out = _generate_to_tmp(gen_references, tmp_path)
    committed = {p.name: p.read_bytes() for p in REFS.iterdir() if p.is_file()}
    regenerated = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    assert set(committed) == set(regenerated), "文件集合漂移：{} vs {}".format(sorted(committed), sorted(regenerated))
    for name in sorted(committed):
        assert committed[name] == regenerated[name], "refs/{} 与重新生成不一致（生成器被改动或产物被手改）".format(name)


def test_thesis_regeneration_bit_identical(tmp_path):
    _require_docx()
    out = _generate_to_tmp(gen_thesis_docx, tmp_path)
    for name in ("thesis_synthetic.docx", "thesis_truth.json", "thesis_manifest.json"):
        assert (THESIS / name).read_bytes() == (out / name).read_bytes(), "thesis/{} 与重新生成不一致".format(name)


def test_audit_fixtures_regeneration_bit_identical(tmp_path):
    """M3 新增：正文引用对账夹具（REF-04/05/07 数据面）位级一致守门。"""
    out = tmp_path / "audit"
    gen_audit_fixtures.generate(out)
    for name in ("refs_table.txt", "refs_table.bib", "body.txt", "audit_truth.json"):
        assert (AUDIT / name).read_bytes() == (out / name).read_bytes(), \
            "audit/{} 与重新生成不一致（生成器被改动或产物被手改）".format(name)


def test_halluref_bench_regeneration_bit_identical(tmp_path):
    """M3 新增：HalluRef-Bench v1 全量 200 条位级一致守门（D-4 冻结）。"""
    out = tmp_path / "halluref"
    gen_halluref_bench.generate(out)
    for name in ("halluref_v1.jsonl", "halluref_v1_manifest.json"):
        assert (BENCH / name).read_bytes() == (out / name).read_bytes(), \
            "bench/halluref/{} 与重新生成不一致".format(name)


def test_review_corpus_regeneration_bit_identical(tmp_path):
    """M4 新增：综述辅助语料（FULL-05 数据面）位级一致守门。"""
    out = tmp_path / "review"
    gen_review_corpus.generate(out)
    for name in ("review_corpus.json", "review_truth.json"):
        assert (REVIEW / name).read_bytes() == (out / name).read_bytes(), \
            "review/{} 与重新生成不一致（生成器被改动或产物被手改）".format(name)


# ---- refs 真值纪律 ----


def test_refs_truth_covers_taxonomy_and_clean_is_silent():
    truth = json.loads((REFS / "refs_truth.json").read_text(encoding="utf-8"))
    entries = truth["entries"]
    assert len(entries) == truth["counts"]["total"] == 72
    assert len({e["entry_id"] for e in entries}) == 72
    assert {e["layer"] for e in entries} == {"clean", "light", "heavy"}
    assert {e["entry_type"] for e in entries} == {"J", "C", "D", "M", "R"}
    # 六类错误全部作为主期望出现（真值覆盖契约）
    main_types = {e["expect"]["check_type"] for e in entries if e["expect"]}
    assert main_types == {"punct", "field_required", "type_marker", "author_threshold",
                          "citation_style", "page_range_or_consistency"}
    # clean 条目（无注入）必须零期望——任何非 pass 判定都是误报
    for e in entries:
        if e["expect"] is None:
            assert e["injects"] == [] and e["also_expect"] == [], "clean 条目带期望: {}".format(e["entry_id"])
    # 复合注入才有 also_expect
    for e in entries:
        if e["also_expect"]:
            assert len(e["injects"]) > 1, "单注入却带 also_expect: {}".format(e["entry_id"])
    assert truth["counts"]["clean"] + truth["counts"]["injected"] == 72
    # DOI 假前缀
    assert truth["doi_fake_prefix"] == "10.9999/"


def test_refs_manifest_matches_files_on_disk():
    manifest = json.loads((REFS / "refs_manifest.json").read_text(encoding="utf-8"))
    on_disk = {p.name for p in REFS.iterdir() if p.is_file()}
    assert on_disk == set(manifest["files"]), "refs 目录与 manifest 不一致：{} vs {}".format(sorted(on_disk), sorted(manifest["files"]))


# ---- thesis 真值纪律 ----


def test_thesis_truth_self_consistent():
    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    tree = truth["style_tree"]
    texts = [p["text"] for p in tree]
    # 植入类目齐全（plan/05 四类：样式/悬空（含幽灵对象）/术语/AI 模式）
    kinds = {i["kind"] for i in truth["implants"]}
    assert kinds == {"style_error", "dangling_marker", "ghost_object", "term_variant", "aigc_pattern"}
    # text_anchor 真实落在对应位置：段落文本或该段 REF 域（域 run 不计入 .text）
    for imp in truth["implants"]:
        for idx in imp["paras"]:
            assert 0 <= idx < len(tree)
        anchor = imp["text_anchor"]
        target = texts[imp["paras"][0]]
        field_hit = any(
            f["para_index"] in imp["paras"] and f["target_bookmark"] in anchor
            for f in truth["fields"]
        )
        assert anchor in target or field_hit, "锚点未落在段落或域: {} ({})".format(imp["id"], anchor)
    # 幽灵对象 ↔ referenced 标志一致
    for obj in truth["objects"]:
        assert obj["referenced"] == bool(obj["mentioned_paras"])
        ghost_implanted = any(i["id"] in ("G1", "G2") and i["expect"]["field"] == obj["label"] for i in truth["implants"])
        if ghost_implanted:
            assert not obj["referenced"], "幽灵植入却 referenced: {}".format(obj["label"])
    # 段落 style 都是 python-docx 已知样式
    assert {p["style"] for p in tree} <= {"Normal", "Title", "Caption", "Heading 1", "Heading 2"}


def test_thesis_docx_matches_truth_style_tree():
    """以 python-docx 实读入仓 docx，逐段比对 style_tree——真值对产物本身的承诺。"""
    _require_docx()
    from docx import Document

    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    doc = Document(str(THESIS / "thesis_synthetic.docx"))
    paras = doc.paragraphs
    assert len(paras) == len(truth["style_tree"])
    for p, rec in zip(paras, truth["style_tree"]):
        assert p.text == rec["text"], "第 {} 段文本与真值不一致".format(rec["i"])
        assert p.style.name == rec["style"], "第 {} 段样式与真值不一致：{} vs {}".format(rec["i"], p.style.name, rec["style"])
    # 域：instr 与书签存在性与真值一致
    xml = doc.element.xml
    for fld in truth["fields"]:
        assert fld["instr"] in xml, "域 instr 不在文档中: {}".format(fld["instr"])
        bookmark_in_doc = 'w:name="{}"'.format(fld["target_bookmark"]) in xml
        assert bookmark_in_doc == fld["bookmark_exists"], "书签存在性与真值不一致: {}".format(fld["target_bookmark"])


def test_thesis_manifest_matches_files_on_disk():
    manifest = json.loads((THESIS / "thesis_manifest.json").read_text(encoding="utf-8"))
    on_disk = {p.name for p in THESIS.iterdir() if p.is_file()}
    assert on_disk == set(manifest["files"])


# ---- ruleset / 条款库纪律（无出处不落库）----


RULESET_FILES = sorted((DATA / "rulesets").glob("*.json"))
KNOWLEDGE_FILES = sorted((DATA / "knowledge").glob("*.json"))


def test_rulesets_discipline():
    assert len(RULESET_FILES) >= 4, "ruleset 缺失：{}".format([p.name for p in RULESET_FILES])
    assert {json.loads(f.read_text(encoding="utf-8"))["layer"] for f in RULESET_FILES} == {1, 2, 3, 4}, "四层编号不齐"
    all_ids = []
    for f in RULESET_FILES:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["layer"] in (1, 2, 3, 4)
        for rule in data["rules"]:
            assert rule["status"] in ("verified", "pending"), "{}#{}".format(f.name, rule["rule_id"])
            if rule["status"] == "verified":
                assert rule["quote"], "{}#{} verified 却无原文摘录".format(f.name, rule["rule_id"])
            assert rule["check_type"] and rule["severity"] in ("error", "warn", "info")
            assert "standard_year" in rule["gates"] and "profile" in rule["gates"]
            all_ids.append(rule["rule_id"])
    assert len(all_ids) == len(set(all_ids)), "rule_id 跨文件重复"


def test_ruleset_activation_discipline():
    """M3 裁定（plan/04 §十）：activation 与 status 正交；active 规则必须挂 basis。"""
    for f in RULESET_FILES:
        data = json.loads(f.read_text(encoding="utf-8"))
        for rule in data["rules"]:
            act = rule.get("activation")
            assert act in (None, "active", "gated"), "{}#{}".format(f.name, rule["rule_id"])
            if act == "active":
                assert rule.get("basis"), "{}#{} active 却无 basis（依据）".format(f.name, rule["rule_id"])


def test_standard_replacements_grounded():
    """双标尺替代关系：每条须 verified + 挂官方来源。"""
    path = DATA / "knowledge" / "standard_replacements.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["replacements"], "替代关系表为空"
    for r in data["replacements"]:
        assert r["identity_status"] == "verified"
        assert r["source"]["evidence"] and r["source"]["url"]


def test_audit_truth_self_consistent():
    truth = json.loads((AUDIT / "audit_truth.json").read_text(encoding="utf-8"))
    table = (AUDIT / "refs_table.txt").read_text(encoding="utf-8")
    for n in truth["expect"]["ghost_reference"]:
        assert "[{}]".format(n) in table, "幽灵条目不在文献表: {}".format(n)
    for n in truth["expect"]["dangling_citation"]:
        assert "[{}]".format(n) not in table, "悬空引用不应在文献表: {}".format(n)
    assert truth["table_entries"] == len([l for l in table.splitlines() if l.strip()])


def test_halluref_full_library_frozen():
    """HalluRef-Bench v1 全量（D-4：200 = genuine 100 + hallucinated 100）。"""
    manifest = json.loads((BENCH / "halluref_v1_manifest.json").read_text(encoding="utf-8"))
    lines = [ln for ln in (BENCH / "halluref_v1.jsonl").read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    entries = [json.loads(ln) for ln in lines]
    assert len(entries) == 200 == manifest["scale"]["total"]
    genuine = [e for e in entries if e["label"] == "genuine"]
    hallucinated = [e for e in entries if e["label"] == "hallucinated"]
    assert len(genuine) == 100 and len(hallucinated) == 100
    # 6 单类 × 16 + 复合 4：单类计数（class_counts_single）各恰 16；
    # 复合条目会把其类别计入 class_counts_all，故两者不同。
    from collections import Counter
    per_class = Counter(c for e in hallucinated for c in e["classes"])
    singles = Counter(e["classes"][0] for e in hallucinated if len(e["classes"]) == 1)
    assert set(per_class) == set(manifest["classes_v1"])
    assert manifest["class_counts_single"] == dict(singles)
    for cls in manifest["classes_v1"]:
        assert singles[cls] == 16, "单类样本数不符: {}={}".format(cls, singles[cls])
    composites = [e for e in hallucinated if len(e["classes"]) > 1]
    assert len(composites) == 4, "复合条目应 4 条"
    assert manifest["scale"]["singles_total"] == 96
    assert manifest["scale"]["composite_total"] == 4
    assert sum(per_class.values()) == 100 + sum(len(c["classes"]) for c in composites) - len(composites)
    # 唯一性 + genuine 零缺陷
    assert len({e["entry_id"] for e in entries}) == 200
    for e in genuine:
        assert e["classes"] == [] and e["signals"] == []
        assert e["fields"]["doi"].startswith("10.9999")
    for e in hallucinated:
        assert e["classes"] and e["signals"]


def test_halluref_full_library_no_timestamp():
    """冻结纪律：产物无时间戳字段（可重复生成）。"""
    for ln in (BENCH / "halluref_v1.jsonl").read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        obj = json.loads(ln)
        assert not any(k in obj for k in ("timestamp", "generated_at", "date"))


def test_knowledge_discipline():
    for f in KNOWLEDGE_FILES:
        data = json.loads(f.read_text(encoding="utf-8"))
        identity = data.get("identity")
        if identity is not None:
            assert identity["identity_status"] in ("verified", "pending"), f.name
            assert identity.get("next_review"), "{} 缺 next_review（标准身份复核日期）".format(f.name)
            assert re.match(r"^\d{4}-\d{2}-\d{2}$", identity["next_review"]), \
                "{} next_review 非 YYYY-MM-DD: {}".format(f.name, identity["next_review"])
            if identity["identity_status"] == "verified":
                assert identity["identity_sources"], "{} verified 却无出处渠道".format(f.name)
        for clause in data.get("clauses", []):
            assert clause["status"] in ("verified", "pending")
            if clause["status"] == "verified":
                assert clause["quote"] and clause.get("source"), "{}#{} verified 缺原文或出处".format(f.name, clause["clause_id"])
    # DOI 假前缀白名单必须含 10.9999（refs 真值与之对账）
    prefixes = json.loads((DATA / "knowledge" / "doi_fake_prefixes.json").read_text(encoding="utf-8"))
    assert "10.9999" in [p["prefix"] for p in prefixes["prefixes"]]
    # AIGC 特征：无 basis 不入库
    aigc = json.loads((DATA / "knowledge" / "aigc_features.json").read_text(encoding="utf-8"))
    assert len(aigc["features"]) >= 4
    for feat in aigc["features"]:
        assert feat["basis"], "特征 {} 缺依据".format(feat["feature_id"])
        assert feat["status"] in ("verified", "pending")


# ---- HalluRef-Bench 示例 ----


def test_halluref_examples_match_manifest():
    bench = DATA / "bench" / "halluref"
    manifest = json.loads((bench / "MANIFEST.json").read_text(encoding="utf-8"))
    lines = [ln for ln in (bench / "halluref_v1_examples.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    entries = [json.loads(ln) for ln in lines]
    assert len(entries) == manifest["counts"]["examples_total"]
    genuine = [e for e in entries if e["label"] == "genuine"]
    hallucinated = [e for e in entries if e["label"] == "hallucinated"]
    assert len(genuine) == manifest["counts"]["examples_genuine"]
    assert len(hallucinated) == manifest["counts"]["examples_hallucinated"]
    ids = [e["entry_id"] for e in entries]
    assert len(ids) == len(set(ids))
    for e in genuine:
        assert e["classes"] == [] and e["signals"] == []
        assert e["fields"]["doi"].startswith(manifest["format"]["doi_genuine_prefix"])
    for e in hallucinated:
        assert e["classes"], "hallucinated 无类目: {}".format(e["entry_id"])
        assert e["signals"], "hallucinated 无可检信号: {}".format(e["entry_id"])
        assert all(c in manifest["classes_v1"] for c in e["classes"]), "未冻结类目: {}".format(e["classes"])


# ---- M4：综述语料与全文线知识库纪律 ----


def test_review_truth_self_consistent():
    """综述真值自洽：分组与语料一致、年份分布吻合、空白按规则可判。"""
    corpus = json.loads((REVIEW / "review_corpus.json").read_text(encoding="utf-8"))
    truth = json.loads((REVIEW / "review_truth.json").read_text(encoding="utf-8"))
    entries = corpus["entries"]
    assert len(entries) == truth["counts"]["entries"] == 20
    assert corpus["now_year"] == truth["now_year"] == 2026
    # 分组覆盖语料全部条目
    grouped = [e for ids in truth["groups"].values() for e in ids]
    assert sorted(grouped) == sorted(e["entry_id"] for e in entries)
    # 年份分布与分组一致
    by_group = {}
    for e in entries:
        by_group.setdefault(e["group"], []).append(e["year"])
    for g, years in truth["years_by_group"].items():
        assert sorted(by_group[g]) == years
    # 空白真值 = 该组最近年份 < now_year-2（规则可判）
    for gap in truth["research_gaps"]:
        assert gap["latest_year"] < truth["now_year"] - 2
        assert max(by_group[gap["group"]]) == gap["latest_year"]


def test_review_corpus_content_fictional():
    """综述语料全部虚构、DOI 用登记假前缀。"""
    corpus = json.loads((REVIEW / "review_corpus.json").read_text(encoding="utf-8"))
    for e in corpus["entries"]:
        assert e["doi"].startswith("10.9999/")
        assert e["title"] and e["year"] and e["authors"]


def test_aigc_feature_library_grounded_m4():
    """AIGC 特征库 M4 复核：4 特征 basis 齐备、detector 名在已实现集合内。"""
    data = json.loads((DATA / "knowledge" / "aigc_features.json").read_text(encoding="utf-8"))
    implemented = {"sentence_length_cv", "template_connectors", "summary_cliches",
                   "parallel_structure"}
    assert len(data["features"]) == 4
    for f in data["features"]:
        assert f["basis"], "特征 {} 缺依据".format(f["feature_id"])
        assert f["detector"] in implemented, "特征 detector 无实现：{}".format(f["detector"])
    assert data["ethics_boundary"], "AIGC 库须硬编码伦理边界说明"


def test_terminology_library_grounded():
    """术语表纪律：canonical 唯一、每条挂 basis 与 status。"""
    data = json.loads((DATA / "knowledge" / "terminology.json").read_text(encoding="utf-8"))
    canonical = [t["canonical"] for t in data["terms"]]
    assert canonical and len(canonical) == len(set(canonical))
    for t in data["terms"]:
        assert t["canonical"] and t["variants"] and t["basis"]
        assert t["status"] in ("verified", "pending")
    assert data["number_usage"]["basis"], "数字用法判据须挂依据"


def test_school_profile_discipline():
    """学校 profile（模板 + 示例）：layer=4、profile 门控为 school-*、active 挂 basis。"""
    import fnmatch
    for name in ("layer4_school_template.json", "layer4_school_demo.json"):
        data = json.loads((DATA / "rulesets" / name).read_text(encoding="utf-8"))
        assert data["layer"] == 4
        gates = data["gates"]["profile"]
        # 模板声明通配 school-*；示例 profile 声明 school-demo（同属 school-* 门控域）
        assert all(fnmatch.fnmatch(g, "school-*") for g in gates), gates
        for rule in data["rules"]:
            assert rule.get("activation") in (None, "active", "gated")
            if rule.get("activation") == "active":
                assert rule.get("basis"), "{}#{} active 却无 basis".format(name, rule["rule_id"])


def test_full_line_rules_active_after_m4():
    """M4 收尾：全文线五条国标规则由 gated 翻转为 active（并挂 basis）。"""
    data = json.loads((DATA / "rulesets" / "layer1_national.json").read_text(encoding="utf-8"))
    by_id = {r["rule_id"]: r for r in data["rules"]}
    for rid in ("GBT7713-struct-01", "GBT15835-num-01", "TAW-xref-dangling-01",
                "TAW-xref-ghost-01", "TAW-aigc-signal-01"):
        assert by_id[rid]["activation"] == "active", "{} 未翻转 active".format(rid)
        assert by_id[rid]["basis"]
        assert by_id[rid]["status"] == "pending", "条款状态应保持 pending（原文不可得）"
    # M4 新增规则
    for rid in ("TAW-style-01", "TAW-term-01", "TAW-xref-order-01",
                "TAW-struct-checklist-01"):
        assert rid in by_id, "M4 新增规则缺失：{}".format(rid)
        assert by_id[rid]["activation"] == "active" and by_id[rid]["basis"]
