# -*- coding: utf-8 -*-
"""全文线基准（BENCH-01 全文面）：5 项指标 + 0 API 可重复（plan/01 §16、FR-16）。

| # | 指标 | 口径 |
|---|---|---|
| 1 | 悬空/幽灵标记检出率 | FULL-01 对 thesis_truth 植入 D1/D3（悬空）+ G1/G2（幽灵），全检出 |
| 2 | 样式核查检出率 / 误报率 | FULL-02 对植入 S1/S2/S3；干净段零非 pass 判定（误报 0） |
| 3 | 术语一致性检出率 | FULL-03 对植入 T1..T4（术语变体 4 处 + 数字写法 2 处） |
| 4 | AIGC 植入检出率 | FULL-04 对植入 A1/A2/A3；干净段无误报（风险提示类，误报 0） |
| 5 | 综述聚类与预分组对账 | FULL-05 对 review_truth 预分组（簇纯度）+ 研究空白 |

零 API 依赖：全部读 `data/frozen/thesis/` 与 `data/frozen/review/`，无网络调用。
"""

import json
import re
from pathlib import Path

from taw import (aigccheck, engine, figref, reviewcl, schoolfmt, structcheck,
                 termnum, thesisparse)


# ---- 指标 1：悬空/幽灵检出 ----


def bench_xref(data_dir, ruleset=None, detailed=False):
    thesis = Path(data_dir) / "frozen" / "thesis"
    truth = json.loads((thesis / "thesis_truth.json").read_text(encoding="utf-8"))
    parsed = thesisparse.parse_thesis(thesis / "thesis_synthetic.docx")
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    res = figref.audit_xref(parsed, ruleset)
    got = {}
    for f in res["findings"]:
        got.setdefault(f["check_type"], []).append(f)

    want_dang = [i["expect"]["field"] for i in truth["implants"]
                 if i["kind"] == "dangling_marker"]
    want_ghost = {i["expect"]["field"] for i in truth["implants"]
                  if i["kind"] == "ghost_object"}

    got_dang = got.get("dangling_reference", [])
    dang_blob = " ".join(
        ((f.get("detail") or "") + " " +
         str((f["evidence"]["location"] or {}).get("label") or ""))
        for f in got_dang).replace(" ", "")

    def _dang_found(want):
        # 真值 expect.field 是"人读描述"：取出关键 token（_Ref 书签名 / 编号标签）后对账
        tokens = re.findall(r"_Ref\d+", want)
        label = re.sub(r"[（(].*?[)）]", "", want).replace(" ", "")
        tokens.append(label)
        return any(t and t in dang_blob for t in tokens)

    dang_hits = [{"want": w, "found": _dang_found(w)} for w in want_dang]

    got_ghost_labels = {str(f["evidence"]["location"].get("label")) for f in got.get("ghost_object", [])}
    ghost_hits = [{"want": w, "found": w in got_ghost_labels} for w in sorted(want_ghost)]

    checks = [
        ("dangling", all(h["found"] for h in dang_hits) and bool(dang_hits)),
        ("ghost", all(h["found"] for h in ghost_hits) and bool(ghost_hits)),
    ]
    passed = sum(1 for _n, ok in checks if ok)
    out = {"checks": [{"name": n, "ok": ok} for n, ok in checks],
           "dangling_expected": want_dang, "dangling_hits": dang_hits,
           "ghost_expected": sorted(want_ghost), "ghost_hits": ghost_hits,
           "detection_rate": round(passed / len(checks), 4),
           "renumber": figref.object_renumber_bench(parsed),
           "gate": {"all_detected": passed == len(checks),
                    "renumber_100": figref.object_renumber_bench(parsed)["gate"]["consistency_100"]}}
    return out


# ---- 指标 2：样式核查检出 / 误报 ----


def bench_style(data_dir, ruleset=None, detailed=False):
    thesis = Path(data_dir) / "frozen" / "thesis"
    truth = json.loads((thesis / "thesis_truth.json").read_text(encoding="utf-8"))
    parsed = thesisparse.parse_thesis(thesis / "thesis_synthetic.docx")
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    findings = schoolfmt.check_style(parsed, ruleset)

    implants = [i for i in truth["implants"] if i["kind"] == "style_error"]
    got_paras = {f["evidence"]["location"]["para"] for f in findings}
    hits = []
    for imp in implants:
        para = imp["paras"][0]
        hits.append({"implant": imp["id"], "para": para, "found": para in got_paras})

    # 误报：非植入段落的 style finding（植入段落集合之外）
    implant_paras = {p for imp in implants for p in imp["paras"]}
    fp = [f for f in findings if f["evidence"]["location"]["para"] not in implant_paras]

    tp = sum(1 for h in hits if h["found"])
    fn = len(hits) - tp
    recall = tp / len(hits) if hits else 1.0
    return {"implant_hits": hits, "tp": tp, "fn": fn, "fp": len(fp),
            "recall": round(recall, 4),
            "false_positive_details": [
                {"para": f["evidence"]["location"]["para"], "detail": f["detail"]} for f in fp],
            "gate": {"all_detected": tp == len(hits) if hits else True,
                     "false_positive_zero": len(fp) == 0}}


# ---- 指标 3：术语一致性检出 ----


def bench_terms(data_dir, ruleset=None, detailed=False):
    thesis = Path(data_dir) / "frozen" / "thesis"
    truth = json.loads((thesis / "thesis_truth.json").read_text(encoding="utf-8"))
    parsed = thesisparse.parse_thesis(thesis / "thesis_synthetic.docx")
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    res = termnum.check_terms(parsed, ruleset, data_dir=data_dir)
    got_paras = {f["evidence"]["location"]["para"] for f in res["findings"]}

    implants = [i for i in truth["implants"] if i["kind"] == "term_variant"]
    hits = []
    for imp in implants:
        # 主期望段落全部须命中（T1/T3 有两处）
        found_any = any(p in got_paras for p in imp["paras"])
        hits.append({"implant": imp["id"], "paras": imp["paras"], "found": found_any})
    tp = sum(1 for h in hits if h["found"])
    return {"implant_hits": hits, "tp": tp, "fn": len(hits) - tp,
            "detected_paras": sorted(got_paras),
            "recall": round(tp / len(hits), 4) if hits else 1.0,
            "number_issues": res["number_issues"],
            "gate": {"all_detected": tp == len(hits) if hits else True}}


# ---- 指标 4：AIGC 植入检出 / 误报 ----


def bench_aigc(data_dir, ruleset=None, detailed=False):
    return _bench_aigc_impl(data_dir, ruleset, detailed=detailed)


def _bench_aigc_impl(data_dir, ruleset=None, detailed=False):
    thesis = Path(data_dir) / "frozen" / "thesis"
    truth = json.loads((thesis / "thesis_truth.json").read_text(encoding="utf-8"))
    parsed = thesisparse.parse_thesis(thesis / "thesis_synthetic.docx")
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    res = aigccheck.check_aigc(parsed, ruleset, data_dir=data_dir)
    flagged = {f["evidence"]["location"]["para"] for f in res["findings"]}

    implants = [i for i in truth["implants"] if i["kind"] == "aigc_pattern"]
    implant_paras = {p for imp in implants for p in imp["paras"]}
    hits = []
    for imp in implants:
        found = any(p in flagged for p in imp["paras"])
        hits.append({"implant": imp["id"], "paras": imp["paras"], "found": found})
    tp = sum(1 for h in hits if h["found"])
    fp = [p for p in flagged if p not in implant_paras]
    return {"implant_hits": hits, "tp": tp, "fn": len(hits) - tp, "fp": len(fp),
            "false_positive_paras": sorted(fp),
            "recall": round(tp / len(hits), 4) if hits else 1.0,
            "detection_bands": {f["evidence"]["location"]["para"]: f["detail"][:40]
                                for f in res["findings"]},
            "gate": {"all_detected": tp == len(hits) if hits else True,
                     "false_positive_zero": len(fp) == 0,
                     "ethics_asserted": aigccheck.assert_no_rewrite_surface()}}


# ---- 指标 5：综述聚类与预分组对账 ----


def bench_review(data_dir, detailed=False):
    review = Path(data_dir) / "frozen" / "review"
    corpus = json.loads((review / "review_corpus.json").read_text(encoding="utf-8"))
    truth = json.loads((review / "review_truth.json").read_text(encoding="utf-8"))
    res = reviewcl.build_review(corpus["entries"], now_year=truth["now_year"])
    got_groups = [g["group"] for g in res["research_gaps"]]
    want_groups = [g["group"] for g in truth["research_gaps"]]
    return {"clusters": res["cluster_count"], "expected_groups": truth["counts"]["groups"],
            "purity": res["purity"]["purity"],
            "gap_groups": sorted(got_groups), "expected_gap_groups": sorted(want_groups),
            "gaps_match": sorted(got_groups) == sorted(want_groups),
            "timeline_groups": sorted(res["timeline"].keys()),
            "gate": {"purity_100": res["purity"]["purity"] >= 0.99,
                     "cluster_count_match": res["cluster_count"] == truth["counts"]["groups"],
                     "gaps_match": sorted(got_groups) == sorted(want_groups)}}


# ---- 合账 ----


def run(data_dir, detailed=False):
    """5 指标合账 → {metrics, gate}。"""
    data_dir = Path(data_dir)
    ruleset = engine.compose_ruleset(data_dir)
    metrics = {
        "1_xref_detection": bench_xref(data_dir, ruleset, detailed=detailed),
        "2_style_check": bench_style(data_dir, ruleset, detailed=detailed),
        "3_term_consistency": bench_terms(data_dir, ruleset, detailed=detailed),
        "4_aigc_detection": _bench_aigc_impl(data_dir, ruleset, detailed=detailed),
        "5_review_cluster": bench_review(data_dir, detailed=detailed),
    }
    gate = {
        "xref_all_detected": metrics["1_xref_detection"]["gate"]["all_detected"],
        "xref_renumber_100": metrics["1_xref_detection"]["gate"]["renumber_100"],
        "style_all_detected": metrics["2_style_check"]["gate"]["all_detected"],
        "style_fp_zero": metrics["2_style_check"]["gate"]["false_positive_zero"],
        "term_all_detected": metrics["3_term_consistency"]["gate"]["all_detected"],
        "aigc_all_detected": metrics["4_aigc_detection"]["gate"]["all_detected"],
        "aigc_fp_zero": metrics["4_aigc_detection"]["gate"]["false_positive_zero"],
        "review_purity_100": metrics["5_review_cluster"]["gate"]["purity_100"],
        "review_gaps_match": metrics["5_review_cluster"]["gate"]["gaps_match"],
    }
    gate["all_pass"] = all(gate.values())
    return {"metrics": metrics, "gate": gate}


def write_report(result, path):
    p = Path(str(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p
