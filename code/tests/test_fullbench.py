# -*- coding: utf-8 -*-
"""全文线基准与编排守门（BENCH-01 全文面；5 指标 + 全链审计）。"""

import json
from pathlib import Path

import pytest

from taw import fullaudit, fullbench

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
THESIS = DATA / "frozen" / "thesis"


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("全文线基准需要 docx extras：{}".format(exc))


# ---- 5 指标 ----


def test_metric1_xref_detection_and_renumber():
    _require_docx()
    res = fullbench.bench_xref(DATA)
    assert res["gate"]["all_detected"] is True
    assert res["gate"]["renumber_100"] is True
    assert all(h["found"] for h in res["dangling_hits"])
    assert all(h["found"] for h in res["ghost_hits"])


def test_metric2_style_detection_and_fp_zero():
    _require_docx()
    res = fullbench.bench_style(DATA)
    assert res["tp"] == 3 and res["fn"] == 0
    assert res["gate"]["false_positive_zero"] is True


def test_metric3_term_detection():
    _require_docx()
    res = fullbench.bench_terms(DATA)
    assert res["tp"] == 4 and res["fn"] == 0
    assert res["number_issues"], "数字写法不一致应检出"


def test_metric4_aigc_detection_and_ethics():
    _require_docx()
    res = fullbench._bench_aigc_impl(DATA)
    assert res["tp"] == 3 and res["fp"] == 0
    assert res["gate"]["ethics_asserted"] is True


def test_metric5_review_cluster():
    res = fullbench.bench_review(DATA)
    assert res["gate"]["purity_100"] is True
    assert res["gate"]["cluster_count_match"] is True
    assert res["gate"]["gaps_match"] is True


def test_fullbench_gate_all_pass():
    _require_docx()
    result = fullbench.run(DATA)
    assert result["gate"]["all_pass"] is True, result["gate"]
    assert set(result["metrics"]) == {
        "1_xref_detection", "2_style_check", "3_term_consistency",
        "4_aigc_detection", "5_review_cluster"}


def test_fullbench_report_reproducible(tmp_path):
    _require_docx()
    r1 = fullbench.run(DATA)
    r2 = fullbench.run(DATA)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    p = fullbench.write_report(r1, tmp_path / "b.json")
    assert p.is_file()
    assert "timestamp" not in json.dumps(r1)


# ---- 全链编排 ----


def test_audit_thesis_all_modules():
    _require_docx()
    report = fullaudit.audit_thesis(THESIS / "thesis_synthetic.docx", data_dir=DATA)
    mods = report["modules"]
    for name in ("FULL-01-xref", "FULL-02-school", "FULL-03-termnum",
                 "FULL-04-aigc", "FULL-05-review", "FULL-06-structure"):
        assert name in mods, "缺模块：{}".format(name)
    types = report["summary"]["by_check_type"]
    assert types.get("dangling_reference") == 2
    assert types.get("ghost_object", 0) >= 2
    assert types.get("style") == 3
    assert types.get("aigc_signal") == 3


def test_audit_thesis_disclaimers_and_ethics():
    _require_docx()
    report = fullaudit.audit_thesis(THESIS / "thesis_synthetic.docx", data_dir=DATA)
    assert report["disclaimers"]
    aigc = report["modules"]["FULL-04-aigc"]
    assert "ethics" in aigc and "风险提示" in aigc["ethics"]


def test_audit_thesis_skip_review():
    _require_docx()
    report = fullaudit.audit_thesis(THESIS / "thesis_synthetic.docx", data_dir=DATA,
                                    include_review=False)
    assert report["modules"]["FULL-05-review"].get("skipped")


def test_audit_thesis_missing_file():
    with pytest.raises(ValueError):
        fullaudit.audit_thesis(DATA / "no-such.docx", data_dir=DATA)


def test_audit_thesis_degrades_without_ruleset():
    """数据目录缺失（None）时降级：不抛异常、无规则类结论、结构仍产出。"""
    _require_docx()
    report = fullaudit.audit_thesis(THESIS / "thesis_synthetic.docx", data_dir=None)
    assert report["ruleset"] is None
    assert report["findings"] == [], "无规则时不应产出规则类结论"
    assert "FULL-01-xref" in report["modules"]
    # 综述语料随数据目录缺失而跳过（不编造）
    assert report["modules"]["FULL-05-review"].get("skipped")


def test_audit_thesis_report_reproducible(tmp_path):
    _require_docx()
    r1 = fullaudit.audit_thesis(THESIS / "thesis_synthetic.docx", data_dir=DATA)
    r2 = fullaudit.audit_thesis(THESIS / "thesis_synthetic.docx", data_dir=DATA)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    p = fullaudit.write_report(r1, tmp_path / "audit.json")
    assert p.is_file()
