# -*- coding: utf-8 -*-
"""F1 解析基准：对冻结真值逐条对账，产出台阶门槛判定 + 分层 F1 + 差异清单。

两个面（plan/04 §九口径）：
  A. 文献面：`refs_*.{txt,csv,bib,ris}` × clean/light/heavy，逐字段与**生成器重建的
     逻辑记录**（`gen_references.build_entries(SplitMix64(20261007))`）比对——
     比 refs_truth.json 更细：真值只记注入期望，逻辑记录才含全字段。
     门槛：clean ≥0.99、light ≥0.97、heavy ≥0.95（plan/05 M2 行 + §九裁量）。
  B. 论文面：`thesis_synthetic.docx` vs `thesis_truth.json`——style_tree 逐段
     (style,text) 必须全等；objects/fields/悬空/幽灵按集合对账。

对账规则（plan/04 §九逐条）：
  - entry_type 不进 F1（类型标识错误是 M3 审计 finding）；
  - 真值声明 punct 命中本格式的条目剔除出严格 F1（标点损伤是审计素材）；
  - 载体语义豁免：ris 无 edition、txt/csv 不渲染 edition==1；
  - 著者截断（前三+等）时尾部著者不计 FN；DOI/ISBN/页码去空白后比较。

零依赖（stdlib）；docx 见 B 面惰性导入。
CLI 消费：`taw parse --report <file>`。
"""

import json
from pathlib import Path

from taw import refparse, thesisparse

SEED = 20261007
# 门槛：clean/light/heavy（plan/05 M2 行锁 clean≥0.99 与 heavy≥0.95；light 取 0.97）
F1_THRESHOLDS = {"clean": 0.99, "light": 0.97, "heavy": 0.95}

REF_FIELDS = ("title", "year", "container", "volume", "issue", "pages",
              "publisher", "city", "edition", "report_no")
REF_FIELDS_WITH_ID = REF_FIELDS + ("doi", "isbn")
FORMATS = ("txt", "csv", "bib", "ris")


def _name_key(n):
    return "".join(ch for ch in n if ch.isalnum()).lower()


def _page_norm(v):
    if not v:
        return v
    for d in ("\u2013", "\u2014", "\uff0d"):
        v = v.replace(d, "-")
    return v


def _carrier_skip(fmt, field, want):
    """载体语义豁免（该格式文本中本就不存在的字段不进 F1 分母）。"""
    if field == "edition":
        if fmt == "ris":
            return True
        if fmt in ("txt", "csv") and str(want) == "1":
            return True
    return False


def _canon_entries(data_dir):
    """生成器重建逻辑记录（post-injection 全字段），按层分组。

    优先读入仓的 `refs_logic.json`（打包后可用、零 tools 依赖）；文件缺失时回退到
    运行期调用生成器（仅开发仓库内可用）。
    """
    logic_path = Path(str(data_dir)) / "frozen" / "refs" / "refs_logic.json"
    if logic_path.is_file():
        data = json.loads(logic_path.read_text(encoding="utf-8"))
        by_layer = {}
        for r in data["records"]:
            by_layer.setdefault(r["layer"], []).append(r)
        return by_layer
    import sys
    repo_root = Path(str(data_dir)).resolve().parents[1]
    tools = repo_root / "code" / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import gen_references
    from taw.rng import SplitMix64

    entries = gen_references.build_entries(SplitMix64(SEED))
    by_layer = {}
    for e in entries:
        by_layer.setdefault(e["layer"], []).append(e)
    return by_layer


def _truth_by_layer(data_dir):
    truth = json.loads((Path(str(data_dir)) / "frozen" / "refs" / "refs_truth.json")
                       .read_text(encoding="utf-8"))
    by_layer = {}
    for e in truth["entries"]:
        by_layer.setdefault(e["layer"], []).append(e)
    return by_layer


def _punct_exempt(truth_entry, fmt):
    for inj in truth_entry["injects"]:
        if inj["type"] == "punct" and fmt in inj.get("formats", []):
            return True
    return False


def _compare_card(card, rec, fmt):
    """单条卡片 vs 逻辑记录 → (tp, fp, fn, diffs)。"""
    tp = fp = fn = 0
    diffs = []
    got = [_name_key(a["raw"]) for a in card["authors"]]
    want = [_name_key(a) for a in rec["authors"]]
    trunc = "authors_truncated" in card["flags"]
    if len(got) <= len(want) and all(got[i] == want[i] for i in range(len(got))) and got:
        tp += len(got)  # 截断（前三+等）或全列均视为命中
    else:
        for i in range(min(len(got), len(want))):
            if got[i] == want[i]:
                tp += 1
            else:
                fp += 1
                fn += 1
                diffs.append("authors[{}] {!r} != {!r}".format(i, got[i], want[i]))
        for i in range(len(want), len(got)):
            fp += 1
            diffs.append("authors[{}] 多出 {!r}".format(i, got[i]))
        if not trunc:
            for i in range(min(len(got), len(want)), len(want)):
                fn += 1
                diffs.append("authors[{}] 漏 {!r}".format(i, want[i]))
    fields = REF_FIELDS_WITH_ID if fmt in ("bib", "ris") else REF_FIELDS
    for f in fields:
        if f == "title":
            g = card["title"]
        elif f in ("doi", "isbn"):
            g = card["identifiers"].get(f)
        else:
            g = card["source"].get(f)
        w = rec.get(f)
        w = str(w) if w is not None else None
        if f == "pages":
            g, w = _page_norm(g), _page_norm(w)
        if _carrier_skip(fmt, f, w):
            continue
        if w is None and g is None:
            continue
        if w is None and g is not None:
            fp += 1
            diffs.append("{} 多出 {!r}".format(f, g))
        elif g is None:
            fn += 1
            diffs.append("{} 漏 {!r}".format(f, w))
        elif g != w:
            fp += 1
            fn += 1
            diffs.append("{} {!r} != {!r}".format(f, g, w))
        else:
            tp += 1
    return tp, fp, fn, diffs


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 1.0
    r = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return round(p, 4), round(r, 4), round(f1, 4)


def bench_refs(data_dir, detailed=False):
    """文献面 F1：四格式 × 三层。返回报告 dict（含逐格式逐层 F1 与门槛判定）。"""
    refs_dir = Path(str(data_dir)) / "frozen" / "refs"
    canon = _canon_entries(data_dir)
    truth = _truth_by_layer(data_dir)
    report = {"thresholds": F1_THRESHOLDS, "formats": {}, "layers": {}, "gate": {}}
    layer_agg = {layer: {"tp": 0, "fp": 0, "fn": 0} for layer in F1_THRESHOLDS}
    for fmt in FORMATS:
        report["formats"][fmt] = {}
        for layer in F1_THRESHOLDS:
            text = (refs_dir / "refs_{}.{}".format(layer, fmt)).read_text(encoding="utf-8")
            cards = refparse.PARSERS[fmt](text, src_name="refs_{}.{}".format(layer, fmt))
            recs = canon[layer]
            tents = truth[layer]
            tp = fp = fn = 0
            diffs = []
            for i, (card, rec, tent) in enumerate(zip(cards, recs, tents)):
                if _punct_exempt(tent, fmt):
                    continue
                a, b, c, ds = _compare_card(card, rec, fmt)
                tp += a
                fp += b
                fn += c
                if detailed:
                    for d in ds:
                        diffs.append({"ordinal": i + 1, "entry_id": rec.get("entry_id"), "diff": d})
            p, r, f1 = _prf(tp, fp, fn)
            report["formats"][fmt][layer] = {
                "precision": p, "recall": r, "f1": f1,
                "tp": tp, "fp": fp, "fn": fn,
                "entries_parsed": len(cards), "entries_expected": len(recs),
                "threshold": F1_THRESHOLDS[layer],
                "pass": f1 >= F1_THRESHOLDS[layer],
            }
            if detailed:
                report["formats"][fmt][layer]["diffs"] = diffs[:30]
            layer_agg[layer]["tp"] += tp
            layer_agg[layer]["fp"] += fp
            layer_agg[layer]["fn"] += fn
    for layer, agg in layer_agg.items():
        p, r, f1 = _prf(agg["tp"], agg["fp"], agg["fn"])
        report["layers"][layer] = {"precision": p, "recall": r, "f1": f1,
                                   "threshold": F1_THRESHOLDS[layer],
                                   "pass": f1 >= F1_THRESHOLDS[layer]}
        report["gate"][layer] = report["layers"][layer]["pass"]
    report["gate"]["refs_pass"] = all(report["gate"][l] for l in F1_THRESHOLDS)
    return report


def bench_thesis(data_dir, detailed=False):
    """论文面对账：style_tree 逐段 + fields + objects + 悬空/幽灵。"""
    thesis_dir = Path(str(data_dir)) / "frozen" / "thesis"
    truth = json.loads((thesis_dir / "thesis_truth.json").read_text(encoding="utf-8"))
    parsed = thesisparse.parse_thesis(thesis_dir / "thesis_synthetic.docx")
    report = {"gate": {}, "checks": {}}

    tree_ok = len(parsed["style_tree"]) == len(truth["style_tree"])
    style_diffs = []
    if tree_ok:
        for got, want in zip(parsed["style_tree"], truth["style_tree"]):
            if got["text"] != want["text"] or got["style"] != want["style"]:
                tree_ok = False
                style_diffs.append({"para": want["i"], "got": got, "want": want})
    report["checks"]["style_tree"] = {
        "paras": len(parsed["style_tree"]), "expected": len(truth["style_tree"]),
        "exact_match": tree_ok, "diffs": style_diffs[:20],
    }

    f_ok = len(parsed["fields"]) == len(truth["fields"])
    for got, want in zip(parsed["fields"], truth["fields"]):
        if not (got["para_index"] == want["para_index"] and got["instr"] == want["instr"]
                and got["display"] == want["display"]
                and got["target_bookmark"] == want["target_bookmark"]
                and got["bookmark_exists"] == want["bookmark_exists"]):
            f_ok = False
    report["checks"]["fields"] = {"got": len(parsed["fields"]),
                                  "expected": len(truth["fields"]), "exact_match": f_ok}

    want_objs = {(o["kind"], o["label"]): o for o in truth["objects"]}
    got_objs = {(o["kind"], o["label"]): o for o in parsed["objects"]}
    obj_diffs = []
    for key, w in want_objs.items():
        g = got_objs.get(key)
        if g is None:
            obj_diffs.append({"object": list(key), "problem": "missing"})
            continue
        if set(g["mentioned_paras"]) != set(w["mentioned_paras"]):
            obj_diffs.append({"object": list(key), "problem": "mentions",
                              "got": g["mentioned_paras"], "want": w["mentioned_paras"]})
        if g["caption_para"] != w["caption_para"]:
            obj_diffs.append({"object": list(key), "problem": "caption_para",
                              "got": g["caption_para"], "want": w["caption_para"]})
        if g["bookmark"] != w["bookmark"]:
            obj_diffs.append({"object": list(key), "problem": "bookmark",
                              "got": g["bookmark"], "want": w["bookmark"]})
    for key in got_objs:
        if key not in want_objs:
            obj_diffs.append({"object": list(key), "problem": "extra"})
    report["checks"]["objects"] = {"got": len(got_objs), "expected": len(want_objs),
                                   "exact_match": not obj_diffs, "diffs": obj_diffs[:20]}

    # 悬空：真值 dangling_marker 植入（D1 手打"表 9-1"、D3 REF 域悬空指向 _Ref99900099）
    # 真值 expect.field 是"人读描述"（含 bookmark 名与显示标签），判定用标签包含匹配。
    want_dangling = [i["expect"]["field"] for i in truth["implants"]
                     if i["kind"] == "dangling_marker"]
    got_dangling = []
    for d in parsed["dangling"]:
        got_dangling.append({"kind": d["kind"], "label": d["label"],
                             "raw": d["raw"], "para_index": d["para_index"]})
    def _found(want):
        want_compact = want.replace(" ", "")
        for d in parsed["dangling"]:
            if d["label"] in want_compact or d["raw"].replace(" ", "") in want_compact:
                return True
            if d.get("target_bookmark") and d["target_bookmark"] in want_compact:
                return True
        return False
    report["checks"]["dangling"] = {
        "detected": got_dangling,
        "expected": want_dangling,
        "all_found": all(_found(w) for w in want_dangling),
        "missing": [w for w in want_dangling if not _found(w)],
    }
    # 幽灵：真值 ghost_object 植入必须出现在检出集合中（真值中 mentioned=[] 的对象）
    want_ghosts = {i["expect"]["field"] for i in truth["implants"]
                   if i["kind"] == "ghost_object"}
    got_ghosts = {g["label"] for g in parsed["ghosts"]}
    report["checks"]["ghosts"] = {
        "detected": sorted(got_ghosts), "expected": sorted(want_ghosts),
        "all_found": want_ghosts <= got_ghosts,
        "extra_detected": sorted(got_ghosts - want_ghosts),
    }
    report["gate"]["thesis_pass"] = (
        report["checks"]["style_tree"]["exact_match"]
        and report["checks"]["fields"]["exact_match"]
        and report["checks"]["objects"]["exact_match"]
        and report["checks"]["dangling"]["all_found"]
        and report["checks"]["ghosts"]["all_found"]
    )
    return report


def run(data_dir, detailed=False):
    """两面合账 → {refs, thesis, gate}。"""
    refs = bench_refs(data_dir, detailed=detailed)
    thesis = bench_thesis(data_dir, detailed=detailed)
    return {"refs": refs, "thesis": thesis,
            "gate": {"refs_pass": refs["gate"]["refs_pass"],
                     "thesis_pass": thesis["gate"]["thesis_pass"],
                     "all_pass": refs["gate"]["refs_pass"] and thesis["gate"]["thesis_pass"]}}


def write_report(result, path):
    """报告落盘（UTF-8、缩进、无时间戳——可重复生成，位级可比对）。"""
    p = Path(str(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p
