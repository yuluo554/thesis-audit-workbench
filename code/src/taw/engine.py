# -*- coding: utf-8 -*-
"""判定引擎骨架（plan/04 §三/§十）：ruleset 装载叠加 + 规则生效门控 + 证据链 Finding。

三层职责：
1. **ruleset 四层叠加**（plan/04 §二）：国标 → 年份 → 期刊 profile → 学校 profile；
   后层同 rule_id 覆盖前层，覆盖动作记入 `overrides`（迁移清单展示面）；
2. **规则生效门控**（plan/04 §十的关键裁定，见模块末注释）；
3. **证据链 Finding 构造**：三级判定 + 条款/依据 + 位置，供 REF-02..09 与报告复用。

条款纪律（NFR-04）在此落地：`status=pending` 的规则**不得**冒充标准原文——
findings 带 `clause_status="pending"` 与 `basis`，报告层显式标注「条款待核对」，
只展示工程口径/合成真值契约作为依据，绝不伪造条号与原文摘录。
"""

import fnmatch
import json
from pathlib import Path

from taw import cards

# 检测规则的实际生效开关（与"条款核对状态"正交，裁定见 plan/04 §十）
ACTIVATION_ACTIVE = "active"
ACTIVATION_GATED = "gated"

REF_RULESET_LAYERS = ("layer1_national.json", "layer2_year_2015.json",
                      "layer2_year_2025.json", "layer3_journal_default.json",
                      "layer4_school_template.json")

# 学校 profile 导入命名（plan/04 §二 + layer4 模板 import_instructions）：
# 用户把模板复制为 `layer4_school_<校名>.json` 并改 profile=school-<校名>，
# 本模块按通配装载，后层增量覆盖（同 rule_id 覆盖国标层，记 overrides）。M4 新增。
SCHOOL_PROFILE_GLOB = "layer4_school_*.json"


def load_ruleset_files(data_dir):
    """读四条层级文件 + 双年份增量 + 学校 profile 导入件，返回按叠加序的层列表。"""
    ruleset_dir = Path(data_dir) / "rulesets"
    names = list(REF_RULESET_LAYERS)
    # 学校 profile 导入件排在模板之后（模板本身 rules=[]，作占位与说明）
    for p in sorted(ruleset_dir.glob(SCHOOL_PROFILE_GLOB)):
        if p.name not in names:
            names.append(p.name)
    out = []
    for name in names:
        p = ruleset_dir / name
        if not p.is_file():
            raise FileNotFoundError("规则包缺失：{}".format(p))
        data = json.loads(p.read_text(encoding="utf-8"))
        out.append({"layer": data.get("layer"), "name": data.get("name"),
                    "rules": data.get("rules", []), "path": str(p)})
    return out


def _gate_match(gate_values, wanted):
    """gate 列表匹配：支持 `journal-*` 这类前缀通配（fnmatch）。"""
    for g in gate_values or ():
        if g == wanted or fnmatch.fnmatch(wanted, g):
            return True
    return False


def is_active(rule):
    """规则是否参与判定。

    显式 `activation` 优先；缺省回退到 `status == "verified"`（兼容 M1 骨架口径）。
    """
    act = rule.get("activation")
    if act is not None:
        return act == ACTIVATION_ACTIVE
    return rule.get("status") == "verified"


def compose_ruleset(data_dir, standard_year="2025", profile="default",
                    scope_prefix=None):
    """四层叠加 → {rules, overrides, standard_year, profile, layers}。

    - 门控：`gates.standard_year` 含所选年份、`gates.profile` 含所选 profile；
    - 叠加：同 rule_id 后层覆盖前层，记入 overrides（含被覆盖规则的 source layer）；
    - 只做增量覆盖，不做字段合并（规则是整体覆盖，避免半新半旧）。
    """
    layers = load_ruleset_files(data_dir)
    merged = []
    index = {}
    overrides = []
    for layer in layers:
        for rule in layer["rules"]:
            gates = rule.get("gates") or {}
            if not _gate_match(gates.get("standard_year"), standard_year):
                continue
            if not _gate_match(gates.get("profile"), profile):
                continue
            if scope_prefix and not str(rule.get("scope", "")).startswith(scope_prefix):
                continue
            rid = rule["rule_id"]
            if rid in index:
                slot = index[rid]
                from_layer = merged[slot]["_layer"]
                merged[slot] = dict(rule, _layer=layer["layer"])
                overrides.append({"rule_id": rid, "from_layer": from_layer,
                                  "to_layer": layer["layer"],
                                  "reason": "后层增量覆盖（profile/年份）"})
            else:
                index[rid] = len(merged)
                merged.append(dict(rule, _layer=layer["layer"]))
    return {"rules": merged, "overrides": overrides,
            "standard_year": standard_year, "profile": profile,
            "layers": [{"layer": l["layer"], "name": l["name"], "path": l["path"]} for l in layers]}


def active_rules(ruleset):
    return [r for r in ruleset["rules"] if is_active(r)]


def find_rule(ruleset, rule_id):
    for r in ruleset["rules"]:
        if r["rule_id"] == rule_id:
            return r
    return None


def make_rule_finding(rule, status, location, suggestion=None, confidence=1.0,
                      detail=None, fix=None):
    """由规则生成长证据链 finding（plan/04 §三 schema + 条款状态/依据扩展字段）。

    条款待核对（status=pending）时 quote 恒为空、clause_status 标 pending，
    报告层据此渲染「条款待核对」而不冒充标准原文（NFR-04）。
    """
    clause_status = rule.get("status", "pending")
    finding = cards.make_finding(
        rule_id=rule["rule_id"],
        status=status,
        location=location,
        clause=rule.get("clause"),
        quote=rule.get("quote") or None,
        suggestion=suggestion,
        confidence=confidence,
    )
    finding["severity"] = rule.get("severity", "info")
    finding["check_type"] = rule.get("check_type")
    finding["standard"] = rule.get("standard")
    finding["clause_status"] = clause_status
    finding["basis"] = rule.get("basis")
    finding["detail"] = detail
    if fix is not None:
        finding["fix"] = fix
    return finding


def make_finding(rule_id, status, location, clause=None, quote=None,
                 suggestion=None, confidence=1.0, severity="info",
                 check_type=None, clause_status="pending", basis=None, detail=None,
                 fix=None):
    """无规则对象时的直接构造（工程规则/文件级 finding）。"""
    finding = cards.make_finding(rule_id, status, location, clause, quote,
                                 suggestion, confidence)
    finding["severity"] = severity
    finding["check_type"] = check_type
    finding["clause_status"] = clause_status
    finding["basis"] = basis
    finding["detail"] = detail
    if fix is not None:
        finding["fix"] = fix
    return finding


def summarize(findings):
    """报告概览：按状态 / severity / check_type 计数。"""
    by_status = {}
    by_severity = {}
    by_type = {}
    for f in findings:
        by_status[f["status"]] = by_status.get(f["status"], 0) + 1
        by_severity[f["severity"]] = by_severity.get(f["severity"], 0) + 1
        ct = f.get("check_type") or "n/a"
        by_type[ct] = by_type.get(ct, 0) + 1
    return {"total": len(findings), "by_status": by_status,
            "by_severity": by_severity, "by_check_type": by_type}


# 报告硬编码免责声明（plan/02 §四.5、plan/01 §六：报告模板强制声明）
DISCLAIMERS = (
    "审计结果供参考，格式与真实性以学校/期刊及原文为准。",
    "标注「条款待核对」的结论仅按工程口径/合成真值契约给出，未引用标准原文条号。",
    "风险提示≠真伪判定；本工具不提供降重/改写通路。",
)


M3_RULE_ACTIVATION = """
M3 关键裁定（plan/04 §十）：规则「条款核对状态」与「检测生效开关」正交
------------------------------------------------------------------------
M1 落库的四层 ruleset 规则 status 全为 pending（GB/T 7714 全文官方不可得，
无法摘录原文 —— 渠道与官方声明原文在案）。若按字面「pending 一律不生效」，
M3 的 REF-02 将零产出、DoD 无法达成；而 plan/05 里程碑表对 REF-03 的表述是
「M1 骨架 / **M3 生效**」。

故 M3 起把两件事拆开（新增字段不改既有语义）：
- `status`（verified|pending）= **条款核对状态**：决定 finding 能否引用
  标准条号与原文摘录作为规范依据。官方原文不可得 → 保持 pending；
- `activation`（active|gated）= **检测生效开关**：决定该检测是否运行。
  M3 需要生效的规则置 active 并挂 `basis`（工程口径 / 合成真值契约）。

findings 一律携带 `clause_status` 与 `basis`：pending 条款的结论在报告中显式
标注「条款待核对」，只展示工程依据，绝不冒充标准原文（NFR-04 不被削弱）。
`activation` 缺省时回退 `status=="verified"`，M1 骨架口径完全兼容。
"""
