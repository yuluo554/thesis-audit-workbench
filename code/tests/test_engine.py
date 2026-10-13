# -*- coding: utf-8 -*-
"""判定引擎骨架守门（plan/04 §三/§十）：ruleset 叠加 + 生效门控 + 证据链。"""

import json
from pathlib import Path

import pytest

from taw import engine

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"


def test_compose_loads_five_layer_files():
    rs = engine.compose_ruleset(DATA)
    assert rs["layers"], "四层规则文件未装载"
    ids = [r["rule_id"] for r in rs["rules"]]
    assert len(ids) == len(set(ids)), "叠加后 rule_id 重复"


def test_standard_year_gate_filters_rules():
    rs2015 = engine.compose_ruleset(DATA, standard_year="2015")
    rs2025 = engine.compose_ruleset(DATA, standard_year="2025")
    ids15 = {r["rule_id"] for r in rs2015["rules"]}
    ids25 = {r["rule_id"] for r in rs2025["rules"]}
    assert "GBT7714-2015-diff-01" in ids15
    assert "GBT7714-2015-diff-01" not in ids25
    assert "GBT7714-2025-diff-01" in ids25
    assert "GBT7714-2025-diff-01" not in ids15


def test_profile_gate_journal_only_in_default():
    rs = engine.compose_ruleset(DATA, profile="default")
    ids = {r["rule_id"] for r in rs["rules"]}
    assert "JOURNAL-default-style-01" in ids
    rs_j = engine.compose_ruleset(DATA, profile="journal-x")
    assert "JOURNAL-default-style-01" not in {r["rule_id"] for r in rs_j["rules"]}


def test_activation_is_orthogonal_to_clause_status():
    """M3 裁定：status=pending 不得阻止 activation=active 的检测生效。"""
    rs = engine.compose_ruleset(DATA)
    punct = engine.find_rule(rs, "GBT7714-punct-01")
    assert punct["status"] == "pending", "条款状态应保持 pending（官方原文不可得）"
    assert punct["activation"] == "active"
    assert engine.is_active(punct) is True
    assert punct["basis"], "active 规则必须挂 basis"


def test_status_fallback_when_activation_absent():
    """缺 activation 时回退 status=='verified'（M1 骨架口径兼容）。"""
    rule = {"rule_id": "x", "status": "pending"}
    assert engine.is_active(rule) is False
    assert engine.is_active({"rule_id": "x", "status": "verified"}) is True
    assert engine.is_active({"rule_id": "x", "status": "pending",
                             "activation": "active"}) is True


def test_scope_prefix_filter():
    rs = engine.compose_ruleset(DATA, scope_prefix="reference.")
    for r in rs["rules"]:
        assert r["scope"].startswith("reference.")


def test_active_rules_only_returns_active():
    rs = engine.compose_ruleset(DATA)
    for r in engine.active_rules(rs):
        assert engine.is_active(r)


def test_make_rule_finding_carries_clause_status_and_basis():
    rs = engine.compose_ruleset(DATA)
    rule = engine.find_rule(rs, "GBT7714-punct-01")
    f = engine.make_rule_finding(rule, "fail", {"doc": "d", "para": 1},
                                 suggestion="补标点", detail="缺逗号")
    assert f["status"] == "fail"
    assert f["clause_status"] == "pending"
    assert f["basis"]
    assert f["check_type"] == "punct"
    assert f["severity"] == "error"
    # pending 条款不得冒出原文摘录（NFR-04）
    assert f["evidence"]["quote"] is None


def test_finding_rejects_bad_status():
    with pytest.raises(ValueError):
        engine.make_finding("r", "maybe", {"doc": "d", "para": 0})


def test_summarize_counts():
    findings = [
        {"status": "fail", "severity": "error", "check_type": "punct"},
        {"status": "manual_confirm", "severity": "warn", "check_type": "punct"},
        {"status": "fail", "severity": "error", "check_type": "type_marker"},
    ]
    s = engine.summarize(findings)
    assert s["total"] == 3
    assert s["by_status"] == {"fail": 2, "manual_confirm": 1}
    assert s["by_check_type"] == {"punct": 2, "type_marker": 1}


def test_disclaimers_hardcoded():
    """报告强制免责声明（边界守卫 §四.5）。"""
    assert engine.DISCLAIMERS
    assert any("参考" in d for d in engine.DISCLAIMERS)
    assert any("条款待核对" in d for d in engine.DISCLAIMERS)


def test_later_layer_overrides_same_rule_id(tmp_path):
    """四层叠加：后层同 rule_id 覆盖前层，覆盖动作留痕（overrides）。

    学校 profile 是最高层——本校细则可覆盖国标层同名规则（plan/04 §二）。
    """
    import json
    import shutil

    shutil.copytree(DATA / "rulesets", tmp_path / "rulesets")
    shutil.copy(DATA / "README.md", tmp_path / "README.md")
    layer4 = tmp_path / "rulesets" / "layer4_school_template.json"
    data = json.loads(layer4.read_text(encoding="utf-8"))
    data["rules"] = [{
        "rule_id": "GBT7714-author-01", "scope": "reference.format",
        "standard": "本校学位论文格式细则", "clause": "本校要求全列著者", "quote": "",
        "status": "pending", "activation": "active", "basis": "用户提供（校模板）",
        "severity": "warn", "check_type": "author_threshold",
        "detect": {}, "fix": {}, "only_if_text": [],
        "gates": {"standard_year": ["2015", "2025"], "profile": ["school-*"]},
    }]
    layer4.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rs = engine.compose_ruleset(tmp_path, profile="school-x")
    rule = engine.find_rule(rs, "GBT7714-author-01")
    assert rule["_layer"] == 4, "后层未覆盖前层"
    assert rule["standard"] == "本校学位论文格式细则"
    assert rs["overrides"] and rs["overrides"][0]["rule_id"] == "GBT7714-author-01"
    assert rs["overrides"][0]["from_layer"] == 1 and rs["overrides"][0]["to_layer"] == 4
