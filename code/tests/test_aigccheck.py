# -*- coding: utf-8 -*-
"""FULL-04 AIGC 痕迹自检守门（plan/01 §13；FR-13；伦理边界硬断言）。"""

import json
from pathlib import Path

import pytest

from taw import aigccheck, engine, thesisparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
THESIS = DATA / "frozen" / "thesis"


@pytest.fixture(scope="module")
def parsed():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("FULL-04 需要 docx extras：{}".format(exc))
    return thesisparse.parse_thesis(THESIS / "thesis_synthetic.docx")


@pytest.fixture(scope="module")
def ruleset():
    return engine.compose_ruleset(DATA)


# ---- 检出 ----


def test_all_aigc_implants_detected(parsed, ruleset):
    """A1/A2/A3 三处 AI 模式植入全检出。"""
    res = aigccheck.check_aigc(parsed, ruleset, data_dir=DATA)
    flagged = {f["evidence"]["location"]["para"] for f in res["findings"]}
    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    for imp in truth["implants"]:
        if imp["kind"] != "aigc_pattern":
            continue
        assert any(p in flagged for p in imp["paras"]), "AIGC 植入未检出：{}".format(imp["id"])


def test_no_false_positive_on_clean_paras(parsed, ruleset):
    """误报 0：非植入段落不得进入风险清单。"""
    res = aigccheck.check_aigc(parsed, ruleset, data_dir=DATA)
    flagged = {f["evidence"]["location"]["para"] for f in res["findings"]}
    truth = json.loads((THESIS / "thesis_truth.json").read_text(encoding="utf-8"))
    implant_paras = {p for imp in truth["implants"] if imp["kind"] == "aigc_pattern"
                     for p in imp["paras"]}
    assert flagged - implant_paras == set(), "干净段落误报"


def test_risk_hints_are_manual_confirm(parsed, ruleset):
    """风险提示≠判定：所有 AIGC finding 为 manual_confirm，severity=warn。"""
    res = aigccheck.check_aigc(parsed, ruleset, data_dir=DATA)
    assert res["findings"]
    for f in res["findings"]:
        assert f["status"] == "manual_confirm"
        assert f["severity"] == "warn"
        assert "风险提示" in f["detail"]


def test_distribution_shape(parsed, ruleset):
    res = aigccheck.check_aigc(parsed, ruleset, data_dir=DATA)
    d = res["distribution"]
    assert d["paragraphs_scored"] > 0
    assert set(d["by_feature"]) == {"aigc-01", "aigc-02", "aigc-03", "aigc-04"}
    assert d["paragraphs_flagged"] == len(d["flagged_paras"])


# ---- 特征检测器 ----


def test_sentence_length_cv_detector():
    uniform = aigccheck.sentence_length_cv("甲乙丙丁。戊己庚辛。壬癸子丑。")
    assert uniform["cv"] == 0.0, "等长句 CV 应为 0"
    varied = aigccheck.sentence_length_cv("短。这是一个明显长很多的句子内容。中等长度句子。")
    assert varied["cv"] > uniform["cv"]


def test_template_and_cliche_detectors():
    t = "首先，我们做了A。其次，我们做了B。最后，我们做了C。"
    assert aigccheck.template_connectors(t)["count"] >= 3
    s = "综上所述，方法有效。总而言之，实验充分。"
    assert aigccheck.summary_cliches(s)["count"] >= 2


def test_features_library_grounded():
    """特征库纪律：4 特征逐条挂 basis，detector 名可解析到实现。"""
    data = json.loads((DATA / "knowledge" / "aigc_features.json").read_text(encoding="utf-8"))
    assert len(data["features"]) == 4
    implemented = {"sentence_length_cv", "template_connectors", "summary_cliches",
                   "parallel_structure"}
    for f in data["features"]:
        assert f["basis"]
        assert f["detector"] in implemented, "detector 未实现：{}".format(f["detector"])


# ---- 伦理边界（硬断言）----


def test_ethics_statement_hardcoded():
    assert aigccheck.ETHICS_STATEMENT
    assert "风险提示" in aigccheck.ETHICS_STATEMENT
    assert "不提供降重" in aigccheck.ETHICS_STATEMENT or "改写" in aigccheck.ETHICS_STATEMENT


def test_ethics_appended_to_disclaimers(parsed, ruleset):
    res = aigccheck.check_aigc(parsed, ruleset, data_dir=DATA)
    assert aigccheck.ETHICS_STATEMENT in res["disclaimers"]


def test_no_rewrite_surface_guard():
    """守卫：模块不提供任何改写/降重通路。"""
    assert aigccheck.assert_no_rewrite_surface() is True


def test_module_has_no_rewrite_functions():
    """模块公开名不得出现改写类**能力**（守卫函数本身除外）。"""
    allowed = {"assert_no_rewrite_surface"}
    for name in dir(aigccheck):
        if name.startswith("_") or name in allowed:
            continue
        low = name.lower()
        assert "rewrite" not in low, "出现改写函数：{}".format(name)
        assert "paraphrase" not in low, "出现改写函数：{}".format(name)


def test_no_rewrite_returns_text():
    """模块不返回"改写后文本"：检测器只返回统计量/计数，不含文本字段。"""
    for fid, fn in aigccheck.DETECTORS.items():
        out = fn("首先，我们做了实验。其次，验证了方法。")
        for k in out:
            assert k != "rewritten_text" and k != "suggestion_text"
