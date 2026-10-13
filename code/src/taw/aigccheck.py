# -*- coding: utf-8 -*-
"""FULL-04 AIGC 痕迹自检（风险提示版，plan/01 §13、plan/04 §六）。

**伦理边界（硬编码，守卫测试断言）**：
- 输出**只有风险提示**，`status` 恒为 `manual_confirm`（风险提示≠AIGC 判定，NFR-05）；
- 模块内**不存在**任何改写/降重/润色通路（不返回被修改的文本，不生成替换建议）；
- `ETHICS_STATEMENT` 为报告强制声明段，`assert_no_rewrite_surface()` 为运行时守卫。

四个启发式特征（逐条挂 `basis`，见 `data/knowledge/aigc_features.json`）：
1. `aigc-01` 句长均匀性（变异系数 CV）：**全文统计量**，进入风险分布；单独不产段落级
   finding（中文论文正常段落 CV 天然偏低，单用会大面积误报——M4 口径裁定，误报 0 优先）；
2. `aigc-02` 模板连接词与套话重复（每千字命中密度）；
3. `aigc-03` 总结套话（段首/段内套话密度）；
4. `aigc-04` 排比结构（同构句式密度）。

段落级 finding 仅在**词汇型特征**（aigc-02/03/04）越过阈值时产出——判据为字面、
确定性、可复核；aigc-01 只参与全文风险画像，不单独定罪。
"""

import re

from taw import engine

# 报告强制声明段（硬编码；守卫测试断言其存在与措辞）
ETHICS_STATEMENT = (
    "风险提示≠AIGC 判定：本模块为本地启发式痕迹提示，仅供作者自查，"
    "不构成任何学术诚信结论；本工具不提供降重/改写/润色功能。"
)

# 明确禁止的通路（守卫测试据此断言仓库不提供改写能力）
FORBIDDEN_SURFACES = ("rewrite", "paraphrase", "改写", "降重", "润色")

# 词汇型套话库（判据为字面命中，逐条可复核）
_TEMPLATE_CONNECTORS = ("首先", "其次", "再次", "最后", "第一，", "第二，", "第三，",
                        "值得注意的是", "需要注意的是", "不难发现", "众所周知")
_SUMMARY_CLICHES = ("综上所述", "总而言之", "总的来说", "综上", "由此可见",
                    "总之", "一言以蔽之")
_PARALLEL_MARKERS = ("不仅", "而且", "一方面", "另一方面", "既", "又", "不但")


def _sentences(text):
    return [s for s in re.split(r"[。！？!?；;]", text) if s.strip()]


def _cv(values):
    """变异系数（总体标准差 / 均值）；样本不足 → None。"""
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean <= 0:
        return None
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return (var ** 0.5) / mean


def _density(count, n_chars):
    """每千字命中密度。"""
    if n_chars <= 0:
        return 0.0
    return count * 1000.0 / n_chars


def _count_markers(text, markers):
    n = 0
    for mk in markers:
        n += text.count(mk)
    return n


# ---- 特征检测器（纯本地统计，对应 aigc_features.json 的 detector 名）----


def sentence_length_cv(text):
    sents = _sentences(text)
    return {"sentences": len(sents), "lengths": [len(s) for s in sents],
            "cv": _cv([len(s) for s in sents])}


def template_connectors(text):
    return {"count": _count_markers(text, _TEMPLATE_CONNECTORS),
            "density": _density(_count_markers(text, _TEMPLATE_CONNECTORS), len(text))}


def summary_cliches(text):
    return {"count": _count_markers(text, _SUMMARY_CLICHES),
            "density": _density(_count_markers(text, _SUMMARY_CLICHES), len(text))}


def parallel_structure(text):
    return {"count": _count_markers(text, _PARALLEL_MARKERS),
            "density": _density(_count_markers(text, _PARALLEL_MARKERS), len(text))}


DETECTORS = {
    "aigc-01": lambda text: sentence_length_cv(text),
    "aigc-02": lambda text: template_connectors(text),
    "aigc-03": lambda text: summary_cliches(text),
    "aigc-04": lambda text: parallel_structure(text),
}

# 仅词汇型特征产段落级 finding（aigc-01 只进全文风险分布，口径见模块 docstring）
LEXICAL_FEATURES = ("aigc-02", "aigc-03", "aigc-04")


def load_features(data_dir):
    """读特征库（无 basis 不入库由数据守门约束；此处按 feature_id 建立索引）。"""
    import json
    from pathlib import Path
    p = Path(str(data_dir)) / "knowledge" / "aigc_features.json"
    if not p.is_file():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {f["feature_id"]: f for f in data.get("features", [])}


def _band(value, th):
    """按阈值定档：>= high 阈值为 high，>= warn 阈值为 warn，否则 None。"""
    if th is None:
        return None
    high = th.get("high")
    warn = th.get("warn")
    if high is not None and value >= high:
        return "high"
    if warn is not None and value >= warn:
        return "warn"
    return None


def profile_paragraphs(parsed, features):
    """逐段计算四特征实测值 + 档位（aigc-01 用 CV 的**低值**方向定档）。"""
    out = []
    for p in parsed.get("style_tree", []):
        text = p["text"]
        if not text.strip() or p["style"].startswith("Heading") or p["style"] in (
                "Title", "Caption"):
            continue
        row = {"para": p["i"], "style": p["style"], "n_chars": len(text)}
        bands = {}
        for fid, fn in DETECTORS.items():
            feat = features.get(fid, {})
            val = fn(text)
            row[fid] = val
            th = feat.get("threshold") or {}
            if fid == "aigc-01":
                cv = val.get("cv")
                # 均匀性判据：CV **越小**风险越高 → 用 (1 - cv) 方向性；阈值语义为上限
                if cv is None:
                    bands[fid] = None
                elif "high" in th and cv <= th["high"]:
                    bands[fid] = "high"
                elif "warn" in th and cv <= th["warn"]:
                    bands[fid] = "warn"
                else:
                    bands[fid] = None
            else:
                bands[fid] = _band(val.get("density", 0.0), th)
        row["bands"] = bands
        row["score"] = _risk_score(row, features)
        out.append(row)
    return out


def _risk_score(row, features):
    """加权风险分（0..1）：命中特征的权重之和，按档位折算。"""
    total = 0.0
    for fid, feat in features.items():
        band = row["bands"].get(fid)
        if not band:
            continue
        w = float(feat.get("weight") or 0.0)
        total += w * (1.0 if band == "high" else 0.6)
    return round(min(total, 1.0), 4)


def check_aigc(parsed, ruleset, data_dir=None, doc_name="thesis", features=None):
    """FULL-04 主入口 → {findings, paragraphs, distribution, ethics, disclaimers, summary}。

    段落级 finding 仅在词汇型特征（aigc-02/03/04）越阈时产出；aigc-01 进风险分布。
    """
    features = features if features is not None else load_features(data_dir)
    rule = None
    if ruleset:
        for r in ruleset["rules"]:
            if r.get("check_type") == "aigc_signal" and engine.is_active(r):
                rule = r
                break

    rows = profile_paragraphs(parsed, features) if features else []
    findings = []
    if rule is not None:
        for row in rows:
            fired = [fid for fid in LEXICAL_FEATURES
                     if row["bands"].get(fid) in ("warn", "high")]
            if not fired:
                continue
            band = "high" if any(row["bands"][f] == "high" for f in fired) else "warn"
            names = "、".join("{}（{}）".format(f, features[f].get("name", ""))
                             for f in fired)
            findings.append(engine.make_rule_finding(
                rule, "manual_confirm",
                {"doc": doc_name, "para": row["para"], "span": None,
                 "field": fired[0], "label": names},
                suggestion="仅供作者自查：可复核该段的句式重复与套话使用",
                confidence=0.5,          # 风险提示，非判定 → 低置信度
                detail="段落命中 AIGC 痕迹特征（{}，风险档 {}）：{}；"
                       "注意，这是风险提示而非 AIGC 判定".format(
                           ",".join(fired), band,
                           "；".join(_feature_evidence(row, f) for f in fired)),
            ))

    distribution = _distribution(rows)
    return {"findings": findings, "paragraphs": rows,
            "distribution": distribution,
            "ethics": ETHICS_STATEMENT,
            "disclaimers": list(engine.DISCLAIMERS) + [ETHICS_STATEMENT],
            "summary": engine.summarize(findings)}


def _feature_evidence(row, fid):
    val = row[fid]
    if fid == "aigc-01":
        return "句长 CV={}".format(val.get("cv"))
    if fid == "aigc-02":
        return "模板连接词 {} 次（密度 {:.1f}/千字）".format(val["count"], val["density"])
    if fid == "aigc-03":
        return "总结套话 {} 次（密度 {:.1f}/千字）".format(val["count"], val["density"])
    return "排比标记 {} 次（密度 {:.1f}/千字）".format(val["count"], val["density"])


def _distribution(rows):
    """全文风险分布：段落数 / 命中数 / 逐特征命中段数 / 分值直方。"""
    by_feature = {}
    for fid in DETECTORS:
        by_feature[fid] = sum(1 for r in rows if r["bands"].get(fid) in ("warn", "high"))
    fired = [r for r in rows if any(r["bands"].get(f) in ("warn", "high")
                                   for f in LEXICAL_FEATURES)]
    return {"paragraphs_scored": len(rows),
            "paragraphs_flagged": len(fired),
            "by_feature": by_feature,
            "max_score": max([r["score"] for r in rows] or [0.0]),
            "flagged_paras": [r["para"] for r in fired]}


# ---- 伦理边界运行时守卫 ----


def assert_no_rewrite_surface():
    """断言本模块**不提供**任何改写/降重通路（返回 True，违反即抛 AssertionError）。

    检查面：模块公开名字中不得出现改写类标识（守卫函数自身的名字除外）；
    不得存在以 rewrite/paraphrase 命名、会返回文本的函数。
    """
    guard_name = "assert_no_rewrite_surface"
    for n in dir():
        if n.startswith("_") or n == guard_name:
            continue
        low = n.lower()
        for bad in FORBIDDEN_SURFACES:
            if bad in ("改写", "降重", "润色", "humanize"):
                if bad in n:
                    raise AssertionError("AIGC 模块出现改写类通路：{}".format(n))
            elif bad in low:
                raise AssertionError("AIGC 模块出现改写类通路：{}".format(n))
    return True
