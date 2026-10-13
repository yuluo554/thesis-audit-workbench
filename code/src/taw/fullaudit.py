# -*- coding: utf-8 -*-
"""FULL 线编排（`taw audit thesis` 的引擎侧实现）。

把 FULL-01..06 串成一次可复现的全文审计：解析 docx → 交叉引用审计 →
学校格式核查（样式 + 学校 profile）→ 术语/数字一致性 → AIGC 痕迹自检 →
综述辅助（文献库语料）→ 结构检查单；输出统一报告结构（findings + 各模块详情 +
免责声明）。CLI 与 GUI 都只消费本模块。

`doc_format` 与 `review` 为可选输入（缺 docx 节属性/综述语料时相应模块跳过，
并在报告中标注 skipped，不静默编造结论）。
"""

import json
from pathlib import Path

from taw import (aigccheck, engine, figref, schoolfmt, structcheck, termnum,
                 thesisparse)


def _load_ruleset(data_dir, standard_year, profile):
    """装载 ruleset；数据目录缺失/None 时返回 None（降级：无规则则不产规则类结论）。"""
    if data_dir is None:
        return None
    try:
        return engine.compose_ruleset(data_dir, standard_year=standard_year,
                                      profile=profile)
    except (FileNotFoundError, OSError, TypeError):
        return None


def audit_thesis(docx_path, data_dir=None, standard_year="2025",
                 profile="default", ruleset=None, include_review=True,
                 review_entries=None):
    """全文线全链审计 → 报告 dict。"""
    docx_path = Path(str(docx_path))
    if not docx_path.is_file():
        raise ValueError("论文 docx 不存在：{}".format(docx_path))
    parsed = thesisparse.parse_thesis(docx_path)
    doc_format = schoolfmt.read_doc_format(docx_path)
    ruleset = ruleset or _load_ruleset(data_dir, standard_year, profile)

    report = {
        "schema_version": 1,
        "doc": {"path": str(docx_path),
                "paragraphs": len(parsed["style_tree"]),
                "objects": len(parsed["objects"]),
                "markers": len(parsed["markers"])},
        "ruleset": None if ruleset is None else {
            "standard_year": ruleset["standard_year"], "profile": ruleset["profile"],
            "rules_total": len(ruleset["rules"]),
            "rules_active": len(engine.active_rules(ruleset)),
            "overrides": ruleset["overrides"]},
        "disclaimers": list(engine.DISCLAIMERS),
        "findings": [],
        "modules": {},
    }

    def _collect(name, res):
        report["modules"][name] = {
            "findings": len(res["findings"]),
            "summary": res["summary"],
        }
        report["findings"].extend(res["findings"])

    _collect("FULL-01-xref", figref.audit_xref(parsed, ruleset, doc_name=docx_path.name))
    _collect("FULL-02-school", schoolfmt.audit_school(parsed, doc_format, ruleset,
                                                      doc_name=docx_path.name))
    _collect("FULL-03-termnum", termnum.check_terms(parsed, ruleset, data_dir=data_dir,
                                                    doc_name=docx_path.name))
    aigc = aigccheck.check_aigc(parsed, ruleset, data_dir=data_dir,
                                doc_name=docx_path.name)
    _collect("FULL-04-aigc", aigc)
    report["modules"]["FULL-04-aigc"]["distribution"] = aigc["distribution"]
    report["modules"]["FULL-04-aigc"]["ethics"] = aigc["ethics"]

    struct = structcheck.check_structure(parsed, ruleset, doc_name=docx_path.name)
    _collect("FULL-06-structure", struct)
    report["modules"]["FULL-06-structure"]["checklist"] = struct["checklist"]

    # FULL-05 综述辅助：消费库内语料（缺语料则跳过，不编造）
    if include_review:
        from taw import reviewcl
        entries = review_entries if review_entries is not None else _load_review_entries(data_dir)
        if entries:
            rv = reviewcl.build_review(entries)
            report["modules"]["FULL-05-review"] = {
                "findings": 0, "clusters": rv["cluster_count"],
                "purity": rv["purity"]["purity"],
                "research_gaps": rv["research_gaps"],
                "timeline": rv["timeline"]}
        else:
            report["modules"]["FULL-05-review"] = {"skipped": "无综述语料"}
    else:
        report["modules"]["FULL-05-review"] = {"skipped": "未启用"}

    report["summary"] = engine.summarize(report["findings"])
    return report


def _load_review_entries(data_dir):
    if data_dir is None:
        return None
    p = Path(str(data_dir)) / "frozen" / "review" / "review_corpus.json"
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("entries")


def write_report(report, path):
    p = Path(str(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p
