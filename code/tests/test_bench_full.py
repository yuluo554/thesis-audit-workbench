# -*- coding: utf-8 -*-
"""M5 基准全集固化守门：两线 **14 指标**一次跑全 + 报告可重复 + 召回缺口全归因。

M5 目标（plan/05 M5 行）= 两线 14 指标全达标复跑固化。本文件把"达标"钉成
可执行断言，防后续里程碑（M6 GUI/打包）改引擎时静默回退：

- `test_fourteen_metrics_present_and_gated`：14 项齐全、两线 gate 全过；
- `test_metric2_recall_shortfall_fully_attributed`：指标 2 的 recall 缺口
  **逐处归因到 M3 既定判定纪律**（UNKNOWN=0）——把"误报 0 优先、召回缺口
  是载体/噪声门控所致"从结论变成被测试的不变量；
- `test_bench_all_report_reproducible`：`--line all` 报告无时间戳、两次位级一致。

零 API 依赖（读 `data/frozen/` + `data/bench/`）；docx 缺装大声失败不静默。
"""

import json
from pathlib import Path

import pytest

from taw import fullbench, refbench

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("M5 基准需要 docx extras（CI/README 已装；缺装=环境配置错误）：{}".format(exc))


@pytest.fixture(scope="module")
def all_result():
    _require_docx()
    return {"refs": refbench.run(DATA), "full": fullbench.run(DATA)}


def test_fourteen_metrics_present_and_gated(all_result):
    """两线 14 指标齐全且 gate 全过（9 文献 + 5 全文）。"""
    refs, full = all_result["refs"], all_result["full"]
    assert set(refs["metrics"]) == {
        "1_parse_f1", "2_format_detection", "3_fix_accuracy", "4_citation_reconcile",
        "5_dedup_pr", "6_hallucination", "7_standard_currency", "8_recommend",
        "9_renumber_consistency"}
    assert set(full["metrics"]) == {
        "1_xref_detection", "2_style_check", "3_term_consistency",
        "4_aigc_detection", "5_review_cluster"}
    assert refs["gate"]["all_pass"] is True, refs["gate"]
    assert full["gate"]["all_pass"] is True, full["gate"]


def test_metric2_recall_shortfall_fully_attributed(all_result):
    """指标 2 的召回缺口必须**全部**由既定判定纪律解释（UNKNOWN=0）。

    这是 M5 的关键固化：recall<1.0 不是遗留缺陷，而是"误报 0 优先"下
    载体可表达性 + 噪声门控 + 三著者歧义的确定性后果；任何未归因 FN 出现
    即视为解析/检测回归。
    """
    m = all_result["refs"]["metrics"]["2_format_detection"]
    assert m["fp"] == 0 and m["clean_fp"] == 0, "误报必须为 0"
    assert m["gate"]["recall_fully_attributed"] is True, m["fn_unexplained"]
    assert len(m["fn_unexplained"]) == 0, m["fn_unexplained"]
    # 归因明细必须覆盖全部 FN（不漏计）
    assert sum(m["fn_reasons"].values()) == m["fn"]
    for reason in m["fn_reasons"]:
        assert not reason.startswith("UNKNOWN"), reason


def test_metric1_parse_f1_thresholds(all_result):
    """指标 1：clean/light/heavy 解析 F1 门槛全过（plan/05 M2 行口径）。"""
    pf = all_result["refs"]["metrics"]["1_parse_f1"]
    assert pf["gate"]["refs_pass"] is True
    assert pf["gate"]["clean"] and pf["gate"]["light"] and pf["gate"]["heavy"]


def test_metric3_to_9_hard_gates(all_result):
    """指标 3..9 硬门槛：修正/对账/去重/幻觉/双标尺/推荐/重排。"""
    m = all_result["refs"]["metrics"]
    assert m["3_fix_accuracy"]["accuracy"] == 1.0
    assert m["4_citation_reconcile"]["accuracy"] == 1.0
    assert m["5_dedup_pr"]["false_merge_rate"] == 0.0
    assert m["6_hallucination"]["genuine_false_positive"] == 0
    assert m["6_hallucination"]["detection_rate"] >= 0.99
    assert m["7_standard_currency"]["gate"]["all_detected"] is True
    assert m["8_recommend"]["recall_at_k"] >= 0.75
    assert m["9_renumber_consistency"]["consistency"] == 1.0


def test_full_line_5_metrics_hard_gates(all_result):
    """全文线 5 指标硬门槛：xref/样式/术语/AIGC/综述。"""
    m = all_result["full"]["metrics"]
    assert m["1_xref_detection"]["gate"]["all_detected"] is True
    assert m["1_xref_detection"]["gate"]["renumber_100"] is True
    assert m["2_style_check"]["tp"] == 3 and m["2_style_check"]["fp"] == 0
    assert m["3_term_consistency"]["tp"] == 4 and m["3_term_consistency"]["fn"] == 0
    assert m["4_aigc_detection"]["tp"] == 3 and m["4_aigc_detection"]["fp"] == 0
    assert m["4_aigc_detection"]["gate"]["ethics_asserted"] is True
    assert m["5_review_cluster"]["gate"]["purity_100"] is True
    assert m["5_review_cluster"]["gate"]["gaps_match"] is True


def test_bench_all_report_reproducible(tmp_path):
    """`--line all` 报告：无时间戳键、两次落盘位级一致（M5 固化纪律）。"""
    _require_docx()
    r1 = {"refs": refbench.run(DATA), "full": fullbench.run(DATA)}
    r2 = {"refs": refbench.run(DATA), "full": fullbench.run(DATA)}
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    blob = json.dumps(r1)
    assert "timestamp" not in blob and "generated_at" not in blob
    p1 = refbench.write_report(r1, tmp_path / "a.json")
    p2 = refbench.write_report(r2, tmp_path / "b.json")
    assert p1.read_bytes() == p2.read_bytes()


def test_benchmark_is_api_free(monkeypatch):
    """零 API 依赖：屏蔽 socket 后两线基准仍须全过（冒烟）。"""
    import socket

    def _boom(*_a, **_k):
        raise AssertionError("基准不得触网")

    monkeypatch.setattr(socket, "socket", _boom)
    assert refbench.run(DATA)["gate"]["all_pass"] is True
