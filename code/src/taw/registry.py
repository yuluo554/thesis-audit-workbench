"""模块注册表：16 个审计模块的进度跟踪单一事实源（plan/04 §八）。

`taw demo` 打印本表；tests/test_registry.py 锁定 16 项与字段完整性。
模块实现后翻转 status 并在提交说明留痕——翻转与测试/文档计数同步，一处不漏。
"""

MODULES = [
    {"id": "REF-01", "line": "ref", "name": "噪声鲁棒解析", "milestone": "M2", "status": "done"},
    {"id": "REF-02", "line": "ref", "name": "格式核查与自动修正", "milestone": "M3", "status": "done"},
    {"id": "REF-03", "line": "ref", "name": "versioned ruleset 四层", "milestone": "M1", "status": "done"},
    {"id": "REF-04", "line": "ref", "name": "正文引用对账", "milestone": "M3", "status": "done"},
    {"id": "REF-05", "line": "ref", "name": "重复条目检测与合并", "milestone": "M3", "status": "done"},
    {"id": "REF-06", "line": "ref", "name": "AI 幻觉文献风险画像", "milestone": "M3", "status": "done"},
    {"id": "REF-07", "line": "ref", "name": "反向引用推荐与一键插入", "milestone": "M3", "status": "done"},
    {"id": "REF-08", "line": "ref", "name": "论证链矩阵与引用拓扑", "milestone": "M3", "status": "done"},
    {"id": "REF-09", "line": "ref", "name": "本地文献库与独特功能组", "milestone": "M3", "status": "done"},
    {"id": "FULL-01", "line": "full", "name": "图表/公式/交叉引用审计与编号重排", "milestone": "M4", "status": "done"},
    {"id": "FULL-02", "line": "full", "name": "学校格式模板核查", "milestone": "M4", "status": "done"},
    {"id": "FULL-03", "line": "full", "name": "术语与数字用法一致性", "milestone": "M4", "status": "done"},
    {"id": "FULL-04", "line": "full", "name": "AIGC 痕迹自检（风险提示版）", "milestone": "M4", "status": "done"},
    {"id": "FULL-05", "line": "full", "name": "综述辅助", "milestone": "M4", "status": "done"},
    {"id": "FULL-06", "line": "full", "name": "结构检查单", "milestone": "M4", "status": "done"},
    # BENCH-01 文献面（9 指标）M3 达成；全文面（5 指标）M4 达成；M5 复跑固化（14 指标一门跑全 +
    # 报告位级可重复 + 召回缺口逐处归因）→ done（test_registry/test_bench_full 双锁定）
    {"id": "BENCH-01", "line": "bench", "name": "内置评测基准（零 API 依赖）", "milestone": "M5", "status": "done"},
]

LINE_NAMES = {"ref": "文献审计线", "full": "全文审计线", "bench": "评测基准"}


def total():
    return len(MODULES)


def counts():
    """按线统计，如 '文献审计线 9 / 全文审计线 6 / 评测基准 1'。"""
    parts = []
    for line_key, line_name in LINE_NAMES.items():
        n = sum(1 for m in MODULES if m["line"] == line_key)
        if n:
            parts.append("{} {}".format(line_name, n))
    return " / ".join(parts)
