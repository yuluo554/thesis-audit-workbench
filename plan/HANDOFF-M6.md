# HANDOFF-M6：桌面交付（M5 收尾交接快照，2026-10-13）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M6.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md) → [03-架构与技术选型](03-架构与技术选型.md)（§五横切纪律、§六接口草案）→ [04-模块详设](04-模块详设.md)（§九=M2、§十=M3、§十一=M4、**§十二=M5 基准固化**）→ 本文。

## 当前进度（M5 末态）

**两线 14 指标全达标固化**（BENCH-01 已翻转 `done`，`test_registry`/`test_bench_full` 双锁定）：

| 线 | 指标 | 实测门槛结果 |
|---|---|---|
| 文献 9 | 分层解析 F1 | clean **1.0** / light **1.0** / heavy **0.9874**（门槛 0.99/0.97/0.95 全过） |
| | 格式检出率 / **误报率** | P=1.0、**FP=0**（clean FP=0）；R=0.6944 缺口 **55/55 全归因**（见下） |
| | 修正准确率 | **79/79 = 1.0**（修正闭合性） |
| | 对账准确率 | **1.0（4/4）**（悬空/幽灵/乱序/著者-年） |
| | 去重 P/R | P=1.0 R=1.0，**误合并率 0** |
| | 幻觉画像检出率 | HalluRef-Bench v1 **100/100**，genuine 误报 **0** |
| | 双标尺差异检出率 | **2/2 = 1.0** |
| | 推荐 Recall@5 / MRR | **0.7778 / 0.7222**（库内防幻觉闭环） |
| | 编号重排一致性 | **79/79 = 100%** |
| 全文 5 | 悬空/幽灵检出 + 重排 | 悬空 **2/2**、幽灵 **2/2**；对象编号矩阵 **100%** |
| | 样式核查检出 / **误报率** | TP=**3/3**、**FP=0** |
| | 术语一致性检出 | TP=**4/4**、FN=0（含千分位 + 伪空格变体） |
| | AIGC 植入检出 / **误报率** | TP=**3/3**、**FP=0**（伦理守卫断言通过） |
| | 综述聚类与预分组对账 | 簇纯度 **1.0**、研究空白命中一致 |

- **一门跑全**：`taw audit bench --line all --report reports/bench_all.json`（零 API 依赖；报告 `sort_keys`、无时间戳、两次落盘**位级一致**）。
- **M5 关键固化——指标 2 召回缺口逐处归因**（`refbench._fn_reason`）：FN=55 全部归因到 M3 判定纪律，`fn_unexplained == []`（**UNKNOWN=0**），由 `test_bench_full.py::test_metric2_recall_shortfall_fully_attributed` 钉死。归因分布：噪声门控 **18** / ris 载体豁免 **9** / 文件级编码制混用 **12** / 三著者带"等"歧义 **6** / DOI-year 不可观察 **6** / 载体签名不唯一 **2** / 载体语义 **2**。**不弱化 gate**（FR-02 验收线 = 误报 0 + 修正 1.0，均达标；召回以可解释缺口呈现）。
- **测试 292 → 299 项**（新增 `test_bench_full.py` 7 项：14 指标齐全 + gate 全过 + 归因完备 + 报告可重复 + 屏蔽 socket 全过；`test_registry` 改为 M5 全 done 锁定），**3.8 + 3.12 双解释器绿**。
- **三基线复跑留痕**：M2 F1（`{'clean':1.0,'light':1.0,'heavy':0.9874}`）+ M3 9 指标（all_pass）+ M4 5 指标（all_pass）——`reports/m5_baseline_trace.txt`（运行产物，不入仓）。
- **数据面无新增**（M5 只读冻结面：`frozen/` + `bench/halluref/`；未动任何冻结文件）。
- 扩展项（arXiv 见刊提示 / 文献 CI watch / 规则包导入导出 / 个人错误画像 / LLM 兜底 / 语义 rerank）**未收口 → 按 P2 顺延 M7 清零决策**（已登记 plan/00 决策表；plan/01 §六 明确其为"三个显式开关扩展项"，非 P0/P1 必达项）。
- 远端仍未建仓：D-1 仓库名 `thesis-audit-workbench` / D-2 署名 `yuluo554` 已拍板；建仓/push 留待 M7 脱敏发布，勿提前 push。

## M6 待办（桌面交付：GUI + COM 实机 + PyInstaller 双 exe）

M6 目标（plan/05 M6 行）：**PySide6 GUI（只消费引擎 API）+ Word/WPS COM 实机验证 + PyInstaller onedir 双 exe**；
DoD：GUI offscreen 测试批绿；构建红线断言（dist 无禁区成分 + 内嵌数据对账）；中立目录干净验证五连。

1. **PySide6 GUI（extras `gui`，只消费引擎 API）**：
   - 铁律：**CLI 是单一事实源，GUI 只消费既有引擎 API（`taw.refaudit`/`taw.fullaudit`/各模块函数），不另起第二套行为**（plan/03 §一）；不得让 GUI 复刻判定逻辑；
   - py3.8 上 pip 自动解析 **PySide6 6.6.3.1**（6.7+ 要求 ≥3.9）——版本随解析，勿硬钉 6.7+；
   - **offscreen 测试纪律**：`QT_QPA_PLATFORM=offscreen`；GUI 测试模块用**模块级 `pytest.importorskip("PySide6")` 声明式跳过**（缺装=整模块 skip；对账计数按 collect-only 折算，见环境坑）；
   - 建议覆盖面：文件选择 → 跑引擎 → findings 表格（三级判定 + 条款待核对标记）→ 报告导出；不追求功能全部 GUI 化，CLI 已覆盖的批处理能力不重复造。
2. **Word/WPS COM 实机验证（extras `com`，pywin32，`sys_platform=='win32'`）**：
   - 复用 M3 已落地的 `taw.docxutil` 批注回写 + 一键插入通路（确定性）；COM 层只是外挂触发；
   - **WPS 兼容范围实机验证**：本机同时装 Word/WPS 时分别实测打开、批注回写、一键插入；
   - 本机 3.8 装 pywin32（pip 解析 6.6.3.1）——实机验证走本机 Word/WPS；CI 无 GUI/Office，COM 测试须可跳过（`sys_platform` 标记 + importorskip）。
3. **PyInstaller onedir 双 exe（extras `pkg`）**：
   - 版本锁：**py3.8 `>=5.13,<6`；py3.9+ `>=6`**（6.x 在 3.8 上 modulegraph 随机崩，系列实录）；
   - **onedir 双 exe**：GUI（`console=False`）+ CLI（`console=True`）；
   - **内嵌数据对账**：`data/frozen/` + `data/bench/` + `data/knowledge/` + `data/rulesets/` 随包，`paths.py` 五分支已支持 `sys._MEIPASS/data`（PyInstaller 6）与 `_internal/data`（PyInstaller 5）；
   - **构建红线断言**：dist 目录扫描**无禁区成分**（无 `_private/`、无真实学校/人名、无 `.db`/`.env`）；exe 内嵌数据与仓库数据**逐文件对账**；
   - **中立目录干净验证五连**：把 dist 复制到**仓库树外**中立目录 + 剥离 `PATH` 环境变量跑 CLI（`selfcheck`/`demo`/`parse`/`audit refs`/`audit bench --line all`）**逐条取真实退出码**（不接管道，防 `PIPESTATUS` 被吞）。
4. **M6 DoD 逐项打勾** → 回写 plan/00 状态表 + 决策表 + plan/05 M6 行；**HANDOFF-M7 落盘**；
   registry 无新模块（16 项不变；M6 是交付层，不改模块注册表）；收尾复跑**三基线**（M2 F1 + M3 9 + M4 5）。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

1. CLI 退出码 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0（`test_cli` 锁定）；
   `parse` 子命令：0=全成功 / 1=部分失败或 docx 缺失降级 / 2=无路径或全失败；
   `audit refs`：0=跑通（含检出问题）/ 1=降级（数据目录缺）/ 2=用法输入错误；
   `audit thesis`：同 `audit refs` 语义；
   `audit bench --line {refs|full|all}`：默认 `refs`；`--json` 时**辅助信息走 stderr**（stdout 纯 JSON）。
2. 数据目录五分支顺序：explicit > `TAW_DATA_DIR` > `sys._MEIPASS/data` > exe`/_internal/data` > CWD 上溯（`test_paths` 锁定）；**改优先级 = 口径变更，须改测试**。
3. registry 16 项、ref 9 / full 6 / bench 1；**REF-01..09、FULL-01..06、BENCH-01 全 done**（`test_registry` 锁定 `test_m5_all_modules_done`）。
4. `.gitattributes` eol=lf；workflow YAML 可解析且 jobs 完整；dev extras=pytest+pyyaml；CI 与 README 装 `.[dev,docx,viz]`（`test_repo_gate` 锁定）；**`viz` extras 未装时拓扑走内置降级渲染器**（3.12 本机未装 pyvis，测试覆盖该路径）。
5. 包名 thesis-audit-workbench / 包目录 taw / CLI 名 taw；仓库根 = plan/data/code 三分；pyproject 在 code/；
   extras 组名 **dev/docx/viz/com/gui/pkg 不改**；**`gui`=PySide6（M6 起）、`com`=pywin32、`pkg`=PyInstaller**。
6. requires-python ≥3.8，全程 3.8 兼容写法（禁 `X|Y` union 注解、match、3.9+ stdlib）；**PyInstaller 按 python_version 分支版本约束**。
7. 里程碑编号 M0–M7；`taw demo`/`selfcheck` 输出含"16 项"计数。
8. **生成器真值语义**：主期望必须命中、also_expect 并入非 pass 集合、clean 条目零期望（任何非 pass=误报）。
9. **`data/frozen/` 禁手改**：改体例=固定 seed 重新生成整目录提交 + 全量测试绿；CR 守门跳过二进制（docx）；`frozen/audit/`、`frozen/review/`、`bench/halluref/` 同受此纪律。
10. **docx 产物确定性模式**：任何 docx 落盘必须重写 zip 固定时间戳 → 公共模块 `taw.docxutil`（`fix_zip_timestamps`/`finalize_comments`）。**COM 回写产物同样须走该收口**。
11. 知识库纪律：identity_status 与 clauses status 分离；verified 必有 sources/quote；无出处不落库；`terminology.json` 每条 canonical/variants/basis 齐备。
12. DOI 假前缀白名单 `10.9999`；HalluRef hallucinated 侧 `10.7777` 刻意不登记；ISBN 虚构出版者段白名单（15 段）。
13. **规则激活口径（M3 裁定）**：`status`(条款核对) 与 `activation`(检测生效) 正交；`activation=active` 必须挂 `basis`；缺 `activation` 回退 `status=="verified"`；findings 一律带 `clause_status`+`basis`，pending 条款标"条款待核对"。
14. **判定纪律（误报 0 优先，04 §十 10.2 + §十一 11.2 + §十二 12.2）**：编号断档只在同章同类内比较；AIGC 段落级 finding 仅由词汇型特征（aigc-02/03/04）越阈产出；术语只报变体字面；数字只在同值两形态并存时报；学校格式只判结构性可判项；**指标 2 的 55 处 FN 全部归因**（UNKNOWN=0，新 FN 即回归）。
15. **拓扑/报告 0 外链**：`reftopo.sanitize_external` 剥离 CDN 后过 `assert_no_external_refs` 硬断言；**GUI 若新增任何 HTML 产物同样必须过该断言**。
16. **F1 对账 canonical 侧**：`data/frozen/refs/refs_logic.json`（post-injection，缺陷态记录）——修正/修复类指标**不可**拿它当"正确目标"，用「修正闭合性」口径。
17. **AIGC 伦理边界（M4 硬编码）**：`aigccheck.ETHICS_STATEMENT` 强制声明 + `assert_no_rewrite_surface()` 守卫 + 守卫测试断言仓库不提供改写/降重通路；**不得为任何模块（含 GUI/COM）新增改写类 API**。
18. **M5 新增口径**：bench 报告 `sort_keys` + 无时间戳 + 位级可重复（`test_bench_full` 锁定）；指标 2 gate 只钉 FP=0，召回缺口以归因完备为准。

## 本机环境坑（只记实测过的）

- **段错误随机崩溃（M5 实测）**：`py -m pytest` 偶发**段错误 exit 139 且零输出**（同命令重跑即过）——判为环境崩溃，处置＝清 `__pycache__`（项目 + 系统 Python base）后**原样重跑**，不成批刷重试；见 crash-loop-rescue skill。
- `core.autocrlf=true` 实测存在 → CR 守门已就位（扩到 `data/bench/`、`frozen/review/`）；docx 属二进制需跳过；
- 默认 `py` = 3.8.8；`py -3.12` 可用；**README/CI 一律 `python -m`**；双入口测试用 sysconfig 定位 `taw.exe`；
- **python-docx writestr 把当前时间写进 zip 条目** → 任何 docx 落盘必须重写收口（`taw.docxutil`）；1.1.2(3.8)/1.2.0(3.12) 内容字节一致；默认模板页宽 215.9mm（Letter）非 A4；
- **本机 3.8 装了 pyvis、3.12 未装** → 拓扑测试需覆盖"pyvis 缺装走内置渲染器"路径（已覆盖）；
- 3.8 已装 python-docx 1.1.2、3.12 已装 1.2.0；pip 走 `NO_PROXY="*" no_proxy="*"` + 清华镜像；
- **M6 前置：本机 3.8 未装 PySide6/pywin32/PyInstaller** → M6 起装 `.[gui,com,pkg]`；**pip install 也是 python 调用，须带 `PYTHONDONTWRITEBYTECODE=1`**（否则写坏 pyc）；
- 系统代理 127.0.0.1:7897 实测失效（000）：外网直连通 api.crossref.org ✅ / doi.org ✅ / std.samr.gov.cn ✅；iso.org 403 ✗；raw.githubusercontent.com 000 ✗；
- 全程 `PYTHONDONTWRITEBYTECODE=1`；**测试 299 项整批可跑（3.8 约 7.6s）**；
- **控制台看中文用 `py -X utf8`**（`cat` 直读 UTF-8 会 mojibake，用 Python `read_text(encoding='utf-8')`）；
- **正则坑**：`str.format()` 会把 `\d{1,2}` 花括号当占位符 → 统一用 `%` 或拼接；字符类要含 ASCII `-`；
- **renumber 内核**对 `marker_id` 全局唯一有硬要求（`mk-<obj_idx>-<n>` 前缀）；
- 模块 docstring 含 `\s`/`\[` 等转义 → 用 `r"""..."""`；
- **M6 环境坑（预期，按 skill 纪律处置）**：GUI offscreen 需 `QT_QPA_PLATFORM=offscreen`；COM 需真实 Word/WPS；PyInstaller 6.x 在 3.8 上 modulegraph 易崩 → 锁 `<6`；**非 ASCII 输出到非 UTF-8 stdout** 会在 CI Windows 管道崩（cp1252）→ CLI 入口按编码探针 reconfigure（若尚未做，M6/M7 前对照检查）。

## M5 DoD（收尾逐项打勾，已回写 plan/00/05）— ✅ 全部达成 2026-10-13

- [x] 两线 **14 指标一门跑全**（`taw audit bench --line all`）全达标（误报 0 优先）；
- [x] 指标表写进 README（文献 9 + 全文 5，**含门槛列 + 复跑命令 + 环境**）；
- [x] 基准**零 API 可重复**（屏蔽 socket 全过；报告无时间戳、键序固定、两次位级一致）；
- [x] **指标 2 召回缺口逐处归因**（55/55，UNKNOWN=0；`test_bench_full` 钉死，不弱化 gate）；
- [x] 双基线复跑纪律生效（M2 F1 + M3 9 + M4 5 三基线一起复跑留痕）；
- [x] 扩展项按 P2 登记 M7 清零决策（plan/00 决策表）；
- [x] registry BENCH-01 翻转 done；plan/00/04/05 回写；**HANDOFF-M6 落盘**；
- [x] 全量 pytest 绿（3.8 + 3.12，**299 项**）+ **三基线复跑不回退**。

## 关键命令速查

```bash
cd <repo>/code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 全量测试（3.8，299 项）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 全量测试（3.12）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw selfcheck    # 环境自检
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw demo         # 数据面 + 16 模块注册表
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw parse ../data/frozen/refs/refs_clean.bib --json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw parse ../data/frozen/thesis/thesis_synthetic.docx --json

# 文献线全链
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit refs ../data/frozen/audit/refs_table.txt \
    --body ../data/frozen/audit/body.txt --report ../reports/audit.json \
    --topology ../reports/topo.html --library ../reports/lib.db

# 全文线全链
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit thesis ../data/frozen/thesis/thesis_synthetic.docx \
    --report ../reports/full.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit thesis ../data/frozen/thesis/thesis_synthetic.docx \
    --profile school-demo --review-topology ../reports/rev.html

# 基准（两线 14 指标一门跑全）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit bench --line all --report ../reports/bench_all.json

# 生成器（重生成，位级一致）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_references.py --force
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_thesis_docx.py --force
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_audit_fixtures.py --force
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_halluref_bench.py
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_review_corpus.py --force

# M6 装依赖（GUI/COM/打包）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev,docx,viz,gui,com,pkg]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

```bash
# 三基线复跑（收尾纪律：改历史等不动工作树操作后也要复跑；M5 实测留痕见 reports/m5_baseline_trace.txt）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -c "
import sys; sys.path.insert(0,'src')
from taw import f1bench, refbench, fullbench
r1 = f1bench.run('../data', detailed=True); f1bench.write_report(r1, '../reports/m2_parse_f1.json')
r2 = refbench.run('../data'); refbench.write_report(r2, '../reports/m3_refbench.json')
r3 = fullbench.run('../data'); fullbench.write_report(r3, '../reports/m4_fullbench.json')
print('M2 F1:', r1['gate']); print('M3 9指标:', r2['gate']['all_pass']); print('M4 5指标:', r3['gate']['all_pass'])"
```
