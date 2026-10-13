# -*- coding: utf-8 -*-
"""文献线基准（BENCH-01 文献面）：9 项指标 + 0 API 可重复（plan/01 §16、plan/02 FR-16）。

| # | 指标 | 口径 |
|---|---|---|
| 1 | 分层解析 F1 | 复用 `f1bench.bench_refs`（clean/light/heavy × 4 格式，逐字段） |
| 2 | 格式检出率 / 误报率 | REF-02 对 refs 真值：逐 (层,格式,条目) 的 check_type 命中/误报 |
| 3 | 修正准确率 | auto fix 对确定性缺陷（页码倒置/标识错/著者阈值）的字段修正正确率 |
| 4 | 对账准确率 | REF-04 对 audit 真值（悬空/幽灵/乱序/著者-年） |
| 5 | 去重 P/R | REF-05 对 audit 真值的重复簇（**误合并率 = 1-P**） |
| 6 | 幻觉画像检出率 | REF-06 对 HalluRef-Bench v1（分类别召回 + genuine 误报率） |
| 7 | 双标尺差异检出率 | REF-02 standard_currency 对被替代标准的检出 |
| 8 | 推荐 Recall@5 / MRR | REF-07 BM25 对合成 (句子→目标文献) 标注 |
| 9 | 编号重排一致性 | `renumber` 任意插入/删除矩阵回归通过率 |

零 API 依赖：全部读 `data/frozen/` 与 `data/bench/halluref/`，无网络调用。
"""

import json
import re
from pathlib import Path

from taw import (engine, f1bench, refcheck, refcite, refdedup, reffake, refparse,
                 refrec, renumber)

LAYERS = ("clean", "light", "heavy")
FORMATS = ("txt", "csv", "bib", "ris")
UNION = {"page_range_or_consistency": {"page_range", "consistency"}}


# ---- 通用小工具 ----


def _truth_maps(data_dir):
    refs = Path(data_dir) / "frozen" / "refs"
    logic = json.loads((refs / "refs_logic.json").read_text(encoding="utf-8"))["records"]
    truth = json.loads((refs / "refs_truth.json").read_text(encoding="utf-8"))["entries"]
    return logic, {e["entry_id"]: e for e in truth}


def _exp_cats(entry, fmt):
    """注入按 formats 可见性过滤后的期望 check_type 类别集合。"""
    out = set()
    pairs = []
    if entry["expect"]:
        pairs.append((entry["expect"]["check_type"], entry["injects"][0]))
    for a, inj in zip(entry["also_expect"], entry["injects"][1:]):
        pairs.append((a["check_type"], inj))
    for ct, inj in pairs:
        if fmt in inj.get("formats", []):
            out.add(ct)
    return out


# ---- 指标 2/7：格式检出率与误报率 ----


def _fn_reason(card, fmt, cat, inferred):
    """把一处格式检出 FN 归因到 M3 已裁定的判定纪律（plan/04 §十 10.2）。

    返回 reason 代码；`UNKNOWN` 表示**无法由任何既定纪律解释**（=回归信号，
    测试会把 UNKNOWN 计数钉为 0）。这使指标 2 的 recall 缺口成为可审计对象，
    而不是一个裸数字（M5 固化）。
    """
    n_auth = len(card["authors"])
    truncated = "authors_truncated" in card["flags"]
    risky = bool(set(card["flags"]) & set(refcheck.RISKY_FLAGS))
    year = card["source"].get("year")
    doi = card["identifiers"].get("doi")
    year_ok = bool(year) and bool(re.match(r"^(?:19|20)\d{2}$", str(year)))
    doi_ok = bool(doi) and bool(re.search(r"/(?:[a-z]+\.)?((?:19|20)\d{2})\.", doi))
    if cat == "citation_style":
        return "G1-file_level"
    if cat == "author_threshold":
        if fmt == "ris":
            return "G2-carrier_no_authors_ellipsis"
        if n_auth == 3 and truncated:
            return "G3-three_authors_with_ellipsis_ambiguous"
        return "UNKNOWN"
    if cat == "field_required":
        if risky:
            return "G4-noise_gated"
        # 载体可表达性：该字段在本载体从不渲染（如 txt/csv 不渲染 doi/edition）
        return "UNKNOWN"
    if cat == "type_marker":
        if inferred is None:
            return "G5-carrier_signature_not_unique"
        return "UNKNOWN"
    if cat == "page_range_or_consistency":
        if not doi_ok or not year_ok:
            return "G6-doi_or_year_unobservable"
        return "UNKNOWN"
    if cat == "punct":
        # csv 无原始块通路（清洗已归一全角标点）；bib 著者行被断行撕裂
        if fmt == "csv":
            return "G7-csv_no_raw_block_punct_normalized"
        if fmt == "bib" and "linebreak_repaired" in card["flags"]:
            return "G8-bib_author_line_broken"
        return "UNKNOWN"
    return "UNKNOWN"


def bench_format(data_dir, ruleset=None, detailed=False):
    data_dir = Path(data_dir)
    refs = data_dir / "frozen" / "refs"
    logic, truth = _truth_maps(data_dir)
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    tp = fp = fn = 0
    per_layer = {}
    clean_fp = 0
    fn_reasons = {}
    unknown_fn = []
    for fmt in FORMATS:
        for li, layer in enumerate(LAYERS):
            text = (refs / "refs_{}.{}".format(layer, fmt)).read_text(encoding="utf-8")
            cards = refparse.PARSERS[fmt](text, src_name="refs_{}.{}".format(layer, fmt))
            res = refcheck.check_format(cards, ruleset, fmt=fmt, src_text=text,
                                        doc_name="refs_{}.{}".format(layer, fmt),
                                        data_dir=data_dir)
            blocks = refcheck._raw_blocks(fmt, text)
            c2e = {c["card_id"]: logic[li * 24 + (c["evidence"]["ordinal"] - 1)]["entry_id"]
                   for c in cards}
            got = {}
            for f in res["findings"]:
                cid = (f["evidence"]["location"] or {}).get("entry_id")
                eid = c2e.get(cid)
                if eid is None:
                    continue
                got.setdefault(eid, set()).add(f["check_type"])
            for c in cards:
                eid = logic[li * 24 + (c["evidence"]["ordinal"] - 1)]["entry_id"]
                t = truth[eid]
                cats = _exp_cats(t, fmt)
                satisfied = set()
                for ct in cats:
                    satisfied |= UNION.get(ct, {ct})
                g = got.get(eid, set())
                is_clean = not t["injects"]
                for ct in g:
                    if ct in satisfied:
                        tp += 1
                    else:
                        fp += 1
                        if is_clean:
                            clean_fp += 1
                inferred = refcheck._infer_type(
                    c, fmt, refcheck._lookup_raw(fmt, blocks, c) or "")
                for ct in cats:
                    if not (UNION.get(ct, {ct}) & g):
                        fn += 1
                        reason = _fn_reason(c, fmt, ct, inferred)
                        fn_reasons[reason] = fn_reasons.get(reason, 0) + 1
                        if reason == "UNKNOWN":
                            unknown_fn.append({"layer": layer, "fmt": fmt,
                                               "entry_id": eid, "check_type": ct,
                                               "flags": sorted(c["flags"])})
                per_layer[layer] = per_layer.get(layer, [0, 0, 0])
                per_layer[layer][0] += tp
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    out = {"tp": tp, "fp": fp, "fn": fn, "clean_fp": clean_fp,
           "precision": round(precision, 4), "recall": round(recall, 4),
           "f1": round(f1, 4),
           "fn_reasons": dict(sorted(fn_reasons.items())),
           "fn_unexplained": unknown_fn,
           "gate": {"false_positive_zero": fp == 0, "clean_fp_zero": clean_fp == 0,
                    "recall_fully_attributed": not unknown_fn}}
    if detailed:
        out["per_layer"] = per_layer
    return out


# ---- 指标 3：修正准确率 ----


def bench_fix_accuracy(data_dir, ruleset=None):
    """auto fix 的修正准确率：应用 fix 后**重查该条目**，原 finding 须消失。

    口径说明：refs_logic.json 是 **post-injection** 记录（含注入后的缺陷值），
    故不能拿它当"修正目标"——修正本就该朝相反方向走（如页码倒置 127-123 → 123-127）。
    正确的可验证口径是**闭合性**：fix 应用后该条目的同类 finding 不再出现
    （修正确实解决了它声称解决的问题），且不引入新的同类问题。
    """
    data_dir = Path(data_dir)
    refs = data_dir / "frozen" / "refs"
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    total = correct = 0
    for fmt in FORMATS:
        for layer in LAYERS:
            text = (refs / "refs_{}.{}".format(layer, fmt)).read_text(encoding="utf-8")
            cards = refparse.PARSERS[fmt](text, src_name="refs_{}.{}".format(layer, fmt))
            res = refcheck.check_format(cards, ruleset, fmt=fmt, src_text=text,
                                        data_dir=data_dir)
            by_id = {c["card_id"]: c for c in cards}
            for f in res["findings"]:
                fix = f.get("fix")
                if not fix or f["status"] != "fail":
                    continue
                cid = (f["evidence"]["location"] or {}).get("entry_id")
                if cid not in by_id:
                    continue
                total += 1
                applied = refcheck.apply_fix(by_id[cid], fix)
                swapped = [applied if k == cid else c for k, c in by_id.items()]
                rere = refcheck.check_format(swapped, ruleset, fmt=fmt, src_text=text,
                                             data_dir=data_dir)
                still = [g for g in rere["findings"]
                         if ((g["evidence"]["location"] or {}).get("entry_id") == cid
                             and g["check_type"] == f["check_type"]
                             and g.get("detail") == f.get("detail"))]
                if not still:
                    correct += 1
    return {"total_fixes": total, "resolved": correct,
            "accuracy": round(correct / total, 4) if total else 1.0}


# ---- 指标 4：对账准确率 ----


def bench_citation(data_dir, ruleset=None):
    data_dir = Path(data_dir)
    audit = data_dir / "frozen" / "audit"
    truth = json.loads((audit / "audit_truth.json").read_text(encoding="utf-8"))
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    _, cards = refparse.parse_file(audit / "refs_table.txt")
    body = (audit / "body.txt").read_text(encoding="utf-8")
    res = refcite.reconcile(cards, refcite.parse_markers(body), ruleset)
    got = {}
    for f in res["findings"]:
        got.setdefault(f["check_type"], []).append(f)
    # 悬空
    dang = [int(f["detail"].split("[")[1].split("]")[0])
            for f in got.get("dangling_citation", []) if "[" in f["detail"]]
    exp_dang = truth["expect"]["dangling_citation"]
    # 幽灵
    ghosts = []
    for f in got.get("ghost_reference", []):
        lab = (f["evidence"]["location"] or {}).get("label") or ""
        if lab.startswith("[") and lab.endswith("]"):
            ghosts.append(int(lab.strip("[]")))
    by_label = {c["evidence"]["label"]: c for c in cards}
    exp_ghosts = [str(n) for n in truth["expect"]["ghost_reference"]]
    ghost_hit = sum(1 for n in truth["expect"]["ghost_reference"]
                    if any(str(n) == str(g) for g in ghosts))
    order_ok = bool(got.get("order_gap")) == bool(truth["expect"]["order_gap"])
    ay = got.get("author_year_mismatch", [])
    ay_hit = sum(1 for e in truth["expect"]["author_year_mismatch"]
                 if any(e["author"] in (f.get("detail") or "") for f in ay))
    checks = [
        ("dangling", set(dang) == set(exp_dang)),
        ("ghost", ghost_hit == len(exp_ghosts)),
        ("order", order_ok),
        ("author_year", ay_hit == len(truth["expect"]["author_year_mismatch"])),
    ]
    passed = sum(1 for _n, ok in checks if ok)
    return {"checks": [{"name": n, "ok": ok} for n, ok in checks],
            "accuracy": round(passed / len(checks), 4),
            "dangling_found": sorted(dang), "ghost_found": sorted(ghosts)}


# ---- 指标 5：去重 P/R ----


def bench_dedup(data_dir, ruleset=None):
    data_dir = Path(data_dir)
    audit = data_dir / "frozen" / "audit"
    truth = json.loads((audit / "audit_truth.json").read_text(encoding="utf-8"))
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    rule = next((r for r in ruleset["rules"]
                 if r.get("check_type") == "duplicate_entry"), None)
    _, cards = refparse.parse_file(audit / "refs_table.bib")
    res = refdedup.find_duplicates(cards, rule)
    label_of = {c["card_id"]: c["evidence"]["label"] for c in cards}
    got_pairs = set()
    for cl in res["clusters"]:
        ids = sorted(cl["entry_ids"])
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                got_pairs.add(frozenset((ids[i], ids[j])))
    exp_pairs = set()
    by_label = {c["evidence"]["label"]: c["card_id"] for c in cards}
    for cluster in truth["expect"]["duplicate_clusters"]:
        labs = ["ref{:03d}".format(n) for n in cluster]
        ids = [by_label[l] for l in labs if l in by_label]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                exp_pairs.add(frozenset((ids[i], ids[j])))
    tp = len(got_pairs & exp_pairs)
    fp = len(got_pairs - exp_pairs)
    fn = len(exp_pairs - got_pairs)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    # 误合并率 = 1 - P（fp 即误合并对）
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4), "recall": round(recall, 4),
            "false_merge_rate": round(fp / (tp + fp), 4) if tp + fp else 0.0,
            "gate": {"false_merge_zero": fp == 0}}


# ---- 指标 6：幻觉画像 ----


def bench_hallucination(data_dir):
    data_dir = Path(data_dir)
    bench = data_dir / "bench" / "halluref"
    entries = [json.loads(ln) for ln in
               (bench / "halluref_v1.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    known = reffake.load_known_prefixes(data_dir)
    fake_isbn = reffake.load_fake_isbn_ranges(data_dir)
    from taw.cards import make_author, make_ref_card

    def to_card(e):
        f = e["fields"]
        return make_ref_card(
            f["entry_type"], [make_author(a) for a in f["authors"]], f["title"],
            source={k: f.get(k) for k in ("container", "year", "volume", "issue",
                                          "pages", "publisher", "city")},
            identifiers={"doi": f.get("doi"), "isbn": f.get("isbn")},
            evidence={"src": "halluref_v1.jsonl", "ordinal": 1}, card_id=e["entry_id"])

    per_class = {}
    genuine_fp = 0
    detected = 0
    h_total = 0
    for e in entries:
        prof = reffake.profile_entry(to_card(e), known, fake_isbn_ranges=fake_isbn)
        got = {s["type"] for s in prof["signals"]}
        if e["label"] == "genuine":
            if got:
                genuine_fp += 1
            continue
        h_total += 1
        exp = set(e["classes"])
        if got & exp:
            detected += 1
        for cl in exp:
            slot = per_class.setdefault(cl, [0, 0])
            slot[1] += 1
            if cl in got:
                slot[0] += 1
    recall = detected / h_total if h_total else 0.0
    return {"hallucinated_total": h_total, "detected": detected,
            "detection_rate": round(recall, 4),
            "genuine_false_positive": genuine_fp,
            "per_class_recall": {k: round(v[0] / v[1], 4) for k, v in sorted(per_class.items())},
            "gate": {"genuine_fp_zero": genuine_fp == 0,
                     "detection_rate": round(recall, 4)}}


# ---- 指标 7：双标尺差异 ----


def bench_standard_currency(data_dir, ruleset=None):
    data_dir = Path(data_dir)
    ruleset = ruleset or engine.compose_ruleset(data_dir)
    reps = refcheck.load_replacements(data_dir)
    if not reps:
        return {"total": 0, "detected": 0, "detection_rate": 0.0,
                "gate": {"no_replacement_data": True}}
    from taw.cards import make_author, make_ref_card
    detected = 0
    for rep in reps:
        card = make_ref_card(
            "S", [make_author("国家虚构标准化委员会")],
            "合成数据通用要求: {}".format(rep["old"]),
            source={"container": "北京: 虚构出版社", "year": "2015"},
            identifiers={}, evidence={"src": "bench", "ordinal": 1},
            card_id="ref-000001")
        res = refcheck.check_format([card], ruleset, fmt="txt", src_text="",
                                    data_dir=data_dir)
        if any(f["check_type"] == "standard_currency" for f in res["findings"]):
            detected += 1
    return {"total": len(reps), "detected": detected,
            "detection_rate": round(detected / len(reps), 4),
            "gate": {"all_detected": detected == len(reps)}}


# ---- 指标 8：推荐 Recall@5 / MRR ----


def bench_recommend(data_dir, top_k=5):
    data_dir = Path(data_dir)
    audit = data_dir / "frozen" / "audit"
    _, cards = refparse.parse_file(audit / "refs_table.txt")
    # 合成标注：句子 → 目标文献（取题名核心词构造，确定可判）
    probes = []
    for c in cards:
        title = c.get("title") or ""
        if len(title) < 4:
            continue
        probes.append(("本文方法参考{}的相关工作".format(title[:8]), c["card_id"]))
    hits = 0
    rr_sum = 0.0
    for sentence, target in probes:
        recs = refrec.recommend(cards, sentence, top_k=top_k)
        ids = [r["card_id"] for r in recs]
        if target in ids:
            hits += 1
            rr_sum += 1.0 / (ids.index(target) + 1)
    n = len(probes) or 1
    return {"probes": len(probes), "recall_at_k": round(hits / n, 4),
            "mrr": round(rr_sum / n, 4), "k": top_k,
            "library_only": True,
            "gate": {"recall_at_k": round(hits / n, 4)}}


# ---- 指标 9：编号重排一致性 ----


def bench_renumber(n_items=6):
    base_ids, cases = refrec.edit_matrix(n_items)
    items = [{"item_id": b, "markers": [{"marker_id": "m-" + b}]} for b in base_ids]
    passed = 0
    failed = []
    for edits, desc in cases:
        plan = renumber.renumber(items, edits)
        if renumber.verify_plan(plan):
            passed += 1
        else:
            failed.append({"case": desc, "plan": plan["new_order"]})
    total = len(cases)
    return {"cases": total, "passed": passed,
            "consistency": round(passed / total, 4) if total else 1.0,
            "failed": failed[:5],
            "gate": {"consistency_100": passed == total}}


# ---- 合账 ----


def run(data_dir, detailed=False):
    """9 指标合账 → {metrics, gate}。"""
    data_dir = Path(data_dir)
    ruleset = engine.compose_ruleset(data_dir)
    parse_f1 = f1bench.bench_refs(data_dir, detailed=detailed)
    metrics = {
        "1_parse_f1": parse_f1,
        "2_format_detection": bench_format(data_dir, ruleset, detailed=detailed),
        "3_fix_accuracy": bench_fix_accuracy(data_dir, ruleset),
        "4_citation_reconcile": bench_citation(data_dir, ruleset),
        "5_dedup_pr": bench_dedup(data_dir, ruleset),
        "6_hallucination": bench_hallucination(data_dir),
        "7_standard_currency": bench_standard_currency(data_dir, ruleset),
        "8_recommend": bench_recommend(data_dir),
        "9_renumber_consistency": bench_renumber(),
    }
    gate = {
        "false_positive_zero": metrics["2_format_detection"]["gate"]["false_positive_zero"],
        "clean_fp_zero": metrics["2_format_detection"]["gate"]["clean_fp_zero"],
        "false_merge_zero": metrics["5_dedup_pr"]["gate"]["false_merge_zero"],
        "hallucination_genuine_fp_zero":
            metrics["6_hallucination"]["gate"]["genuine_fp_zero"],
        "hallucination_detection_100":
            metrics["6_hallucination"]["detection_rate"] >= 0.99,
        "renumber_consistency_100":
            metrics["9_renumber_consistency"]["gate"]["consistency_100"],
        "standard_currency_all":
            metrics["7_standard_currency"]["gate"]["all_detected"],
        "parse_gate": parse_f1["gate"]["refs_pass"],
    }
    gate["all_pass"] = all(gate.values())
    return {"metrics": metrics, "gate": gate}


def write_report(result, path):
    p = Path(str(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p
