"""数据面守门（M1 DoD：CR 守门 / 位级一致守门 / 真值与知识库纪律）。

- CR 守门：data/frozen/ 任何文件出现 CR 即大声失败（对抗本机 autocrlf=true
  检出污染，plan/03 §五第 2 条）；
- 位级一致守门：把两个生成器各重跑一遍，与入仓冻结文件逐字节比对——
  生成器被"顺手改了输出"或运行环境引入随机性时在此拦下；
- 真值纪律：refs 真值六类错误全覆盖、clean 条目零期望；thesis 真值与
  style_tree/objects 自洽；ruleset/条款库无出处不落库（pending 不生效）。
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
FROZEN = DATA / "frozen"
REFS = FROZEN / "refs"
THESIS = FROZEN / "thesis"

sys.path.insert(0, str(REPO_ROOT / "code" / "src"))
sys.path.insert(0, str(REPO_ROOT / "code" / "tools"))

import gen_references  # noqa: E402
import gen_thesis_docx  # noqa: E402


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
    frozen_files = sorted(p for p in FROZEN.rglob("*") if p.is_file())
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


def test_knowledge_discipline():
    for f in KNOWLEDGE_FILES:
        data = json.loads(f.read_text(encoding="utf-8"))
        identity = data.get("identity")
        if identity is not None:
            assert identity["identity_status"] in ("verified", "pending"), f.name
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
