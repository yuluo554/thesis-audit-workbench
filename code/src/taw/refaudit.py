# -*- coding: utf-8 -*-
"""文献线审计编排（`taw audit refs` 的引擎侧实现）。

把 REF-02/04/05/06/07/08 串成一次可复现的审计：载入 fixtures → 核查修正 →
对账 → 去重 → 幻觉画像 → 推荐 → 拓扑；输出统一报告结构（findings 汇总 +
各模块详情 + 免责声明）。CLI 与 GUI 都只消费本模块，不另起行为。
"""

from pathlib import Path

from taw import (engine, refcheck, refcite, refdedup, reffake, refparse,
                 refrec, reftopo)


def _load_ruleset(data_dir, standard_year, profile):
    try:
        return engine.compose_ruleset(data_dir, standard_year=standard_year,
                                      profile=profile)
    except (FileNotFoundError, OSError):
        return None


def audit_refs(table_path, body_path=None, data_dir=None, standard_year="2025",
               profile="default", ruleset=None):
    """文献线全链审计 → 报告 dict。

    body_path 为 None 时跳过 REF-04/07/08（无正文语境），其余照跑。
    """
    table_path = Path(str(table_path))
    if not table_path.is_file():
        raise ValueError("文献表文件不存在：{}".format(table_path))
    fmt, cards = refparse.parse_file(table_path)
    src_text = table_path.read_text(encoding="utf-8")
    ruleset = ruleset or _load_ruleset(data_dir, standard_year, profile)

    report = {
        "schema_version": 1,
        "table": {"path": str(table_path), "format": fmt, "entries": len(cards)},
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
            "summary": res.get("summary"),
        }
        report["findings"].extend(res["findings"])

    if ruleset is not None:
        _collect("REF-02-format", refcheck.check_format(
            cards, ruleset, fmt=fmt, src_text=src_text, doc_name=table_path.name,
            data_dir=data_dir))

    dedup_rule = None
    hallu_rule = None
    if ruleset is not None:
        for r in ruleset["rules"]:
            if r.get("check_type") == "duplicate_entry":
                dedup_rule = r
            elif r.get("check_type") == "hallucination_signal":
                hallu_rule = r

    # REF-05 去重（始终可跑，不依赖正文）
    dedup = refdedup.find_duplicates(cards, dedup_rule)
    report["modules"]["REF-05-dedup"] = {
        "clusters": dedup["clusters"], "manual_pairs": dedup["manual_pairs"],
        "findings": len(dedup["findings"])}
    report["findings"].extend(dedup["findings"])

    # REF-06 幻觉画像
    fake = reffake.profile_refs(cards, ruleset, data_dir=data_dir,
                                doc_name=table_path.name)
    report["modules"]["REF-06-hallucination"] = {
        "health_score": fake["health_score"],
        "high_risk": [p["entry_id"] for p in fake["profiles"] if p["risk"] == "high"],
        "medium_risk": [p["entry_id"] for p in fake["profiles"] if p["risk"] == "medium"],
        "findings": len(fake["findings"])}
    report["findings"].extend(fake["findings"])

    # 正文相关：REF-04 对账 / REF-07 推荐 / REF-08 拓扑
    if body_path:
        body_path = Path(str(body_path))
        body = body_path.read_text(encoding="utf-8")
        markers = refcite.parse_markers(body, doc_name=body_path.name)
        cite = refcite.reconcile(cards, markers, ruleset, doc_name=body_path.name)
        report["modules"]["REF-04-citation"] = {
            "markers": len(markers), "cited_numbers": cite["cited_numbers"],
            "table_numbers": cite["table_numbers"], "findings": len(cite["findings"])}
        report["findings"].extend(cite["findings"])

        context = refcite.extract_citation_context(cards, markers)
        report["modules"]["REF-08-topology"] = {
            "nodes": len(cards), "cited_nodes": len(context),
            "matrix": reftopo.build_matrix(cards, context)}
    else:
        report["modules"]["REF-04-citation"] = {"skipped": "未提供 --body"}
        report["modules"]["REF-08-topology"] = {"skipped": "未提供 --body"}

    report["summary"] = engine.summarize(report["findings"])
    report["health_score"] = fake["health_score"]
    return report


def recommend_for(body_path, table_path, top_k=5, data_dir=None):
    """句子级推荐：给定正文（按段落），逐段给库内 Top-K（REF-07 展示面）。"""
    _, cards = refparse.parse_file(table_path)
    out = []
    for pi, para in enumerate(Path(str(body_path)).read_text(encoding="utf-8").split("\n")):
        if not para.strip():
            continue
        recs = refrec.recommend(cards, para, top_k=top_k)
        if recs:
            out.append({"para": pi, "sentence": para[:80], "recommendations": recs})
    return out


def write_topology(table_path, body_path, out_path, findings=None):
    """产出 0 外链拓扑 HTML（内部过 sanitize + assert）。"""
    _, cards = refparse.parse_file(table_path)
    markers = refcite.parse_markers(Path(str(body_path)).read_text(encoding="utf-8"))
    context = refcite.extract_citation_context(cards, markers)
    html_text = reftopo.render_html(cards, context, findings)
    p = Path(str(out_path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html_text, encoding="utf-8")
    return p


def write_report(report, path):
    import json
    p = Path(str(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p
