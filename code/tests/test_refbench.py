# -*- coding: utf-8 -*-
"""文献线 9 指标基准 + 审计编排守门（BENCH-01 文献面 + `taw audit refs` 引擎侧）。

硬指标断言（M3 DoD）：误报 0 / 误合并 0 / 幻觉 genuine 误报 0 /
重排一致性 100% / 双标尺全检出 / 解析 F1 不回退。
"""

from pathlib import Path

import pytest

from taw import refaudit, refbench

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
AUDIT = DATA / "frozen" / "audit"


@pytest.fixture(scope="module")
def bench_result():
    return refbench.run(DATA)


def test_nine_metrics_present(bench_result):
    keys = set(bench_result["metrics"])
    assert keys == {
        "1_parse_f1", "2_format_detection", "3_fix_accuracy", "4_citation_reconcile",
        "5_dedup_pr", "6_hallucination", "7_standard_currency", "8_recommend",
        "9_renumber_consistency",
    }


def test_gate_all_pass(bench_result):
    assert bench_result["gate"]["all_pass"] is True, bench_result["gate"]


def test_false_positive_zero(bench_result):
    m = bench_result["metrics"]["2_format_detection"]
    assert m["fp"] == 0, "格式核查误报非 0：{}".format(m)
    assert m["clean_fp"] == 0, "clean 条目误报非 0"


def test_false_merge_zero(bench_result):
    m = bench_result["metrics"]["5_dedup_pr"]
    assert m["false_merge_rate"] == 0.0
    assert m["fp"] == 0


def test_hallucination_no_genuine_fp(bench_result):
    m = bench_result["metrics"]["6_hallucination"]
    assert m["genuine_false_positive"] == 0
    assert m["detection_rate"] >= 0.99


def test_renumber_consistency_100(bench_result):
    m = bench_result["metrics"]["9_renumber_consistency"]
    assert m["consistency"] == 1.0 and m["passed"] == m["cases"]


def test_parse_f1_not_regressed(bench_result):
    pf = bench_result["metrics"]["1_parse_f1"]
    assert pf["gate"]["refs_pass"] is True
    for layer, ok in (("clean", True), ("light", True), ("heavy", True)):
        assert pf["gate"][layer] is True


def test_standard_currency_all_detected(bench_result):
    m = bench_result["metrics"]["7_standard_currency"]
    assert m["gate"]["all_detected"] is True


def test_fix_accuracy_high(bench_result):
    m = bench_result["metrics"]["3_fix_accuracy"]
    assert m["accuracy"] == 1.0, m


def test_benchmark_is_api_free(monkeypatch):
    """零 API 依赖：屏蔽 socket 后基准仍须跑通。"""
    import socket

    def _boom(*_a, **_k):
        raise AssertionError("基准不得触网")

    monkeypatch.setattr(socket, "socket", _boom)
    res = refbench.run(DATA)
    assert res["gate"]["all_pass"] is True


def test_report_written_deterministically(bench_result, tmp_path):
    p1 = refbench.write_report(bench_result, tmp_path / "a.json")
    p2 = refbench.write_report(bench_result, tmp_path / "b.json")
    assert p1.read_bytes() == p2.read_bytes(), "报告应可重复生成（无时间戳）"


# ---- 审计编排 ----


def test_audit_refs_full_chain():
    report = refaudit.audit_refs(AUDIT / "refs_table.txt",
                                 body_path=AUDIT / "body.txt",
                                 data_dir=DATA)
    mods = report["modules"]
    for key in ("REF-02-format", "REF-04-citation", "REF-05-dedup",
                "REF-06-hallucination", "REF-08-topology"):
        assert key in mods, "缺模块 {}".format(key)
    assert report["table"]["entries"] == 9
    assert report["summary"]["total"] >= 1
    assert report["disclaimers"]
    # REF-04 检出的四类
    cts = {f["check_type"] for f in report["findings"]}
    assert {"dangling_citation", "ghost_reference", "order_gap"} <= cts


def test_audit_refs_without_body_skips_citation():
    report = refaudit.audit_refs(AUDIT / "refs_table.txt", data_dir=DATA)
    assert "skipped" in report["modules"]["REF-04-citation"]
    assert "skipped" in report["modules"]["REF-08-topology"]
    # 去重与画像仍跑
    assert report["modules"]["REF-05-dedup"]["clusters"]


def test_audit_refs_missing_file_is_error():
    with pytest.raises(ValueError):
        refaudit.audit_refs(AUDIT / "no-such-file.txt", data_dir=DATA)


def test_write_topology_is_zero_external(tmp_path):
    out = tmp_path / "topo.html"
    refaudit.write_topology(AUDIT / "refs_table.txt", AUDIT / "body.txt", out)
    from taw import reftopo
    assert reftopo.assert_no_external_refs(out.read_text(encoding="utf-8")) is True


def test_recommend_for_subject(tmp_path):
    recs = refaudit.recommend_for(AUDIT / "body.txt", AUDIT / "refs_table.txt", top_k=3)
    assert recs, "应有推荐"
    for item in recs:
        assert item["recommendations"]
        for r in item["recommendations"]:
            assert r["card_id"]
