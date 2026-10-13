# 10-7-thesis-audit-workbench 项目计划总览

**项目**：毕业论文全流程审计工作台（学术写作工具，桌面+CLI 双形态）
**两条审计线**：①文献审计线（GB/T 7714 双标尺·对账·去重·AI 幻觉画像·反向引用+一键插入·论证链拓扑·本地文献库）②全文审计线（图表/公式/交叉引用审计重排·学校格式核查·术语与数字用法·AIGC 痕迹自检·综述辅助·结构检查单）
**方法论**：ai-tool-project-sprint（条款库+四层 versioned ruleset+合成真值基准+证据链+离线交付）
**项目系列**：①建造（已发布）②电力 ③医疗 ④招投标 ⑤食品 ⑥发票 ⑦简历 ⑧结构加固 ⑨钢结构 ⑩脚手架 → ⑪本项目 → ⑫个税计算器
**命名约定**：本地目录 `10-7-thesis-audit-workbench`（`10-7`=2026-10-07 日期标签，用户指定；v3 时由 `10-7-gbt7714-reference-checker` 改名）；**GitHub 仓库名 = `thesis-audit-workbench`（纯净名，去日期前缀）**，沿用系列惯例 `yuluo554/<kebab-name>`；署名 `yuluo554`（LICENSE/pyproject 一致）。
**定位宣言（v3）**：覆盖开题→写作→完稿→送审全流程的确定性论文审计台——LLM 聊天给不了持久状态、可审计证据与全量批处理，本工具是 AI 时代的论文质量防线。

## 文档索引

| 文档 | 内容 | 状态 |
|---|---|---|
| [01-题目详细定义.md](01-题目详细定义.md) | 项目题全文 v3（双审计线 16 模块/评分/锚点/边界） | ✅ v3 定稿 2026-10-07 |
| [02-需求解读.md](02-需求解读.md) | 痛点→能力转译、FR 清单带优先级、NFR、边界守卫、验收口径 | ✅ M0 定稿 2026-10-07 |
| [03-架构与技术选型.md](03-架构与技术选型.md) | 双审计线引擎 + 条款库 + 四层 ruleset + COM 外挂；目录布局与横切纪律 | ✅ M0 定稿 2026-10-07 |
| [04-模块详设.md](04-模块详设.md) | 条目/论文参数卡 schema、规则表、标记体系解析、AIGC 特征表；§九=M2 实现级定稿，§十=M3 文献线引擎实现级定稿，§十一=M4 全文线引擎实现级定稿，§十二=M5 基准全集固化，**§十三=M6 桌面交付实现级定稿** | ✅ M0 定稿+M2 §九+M3 §十+M4 §十一+M5 §十二+M6 §十三 |
| [05-数据计划与里程碑.md](05-数据计划与里程碑.md) | 生成器双件套、确定性纪律、M0–M7 DoD 与收尾纪律 | ✅ M0 定稿（里程碑行随 M 回写） |
| 06-决策记录.md | 重大决策表 | ✅ 初始化（见下） |
| [HANDOFF-M1.md](HANDOFF-M1.md) | M1 数据先行交接快照（进度/待办/既定口径/环境坑/DoD/命令速查） | ✅ M0 收尾落盘 2026-10-07 |
| [HANDOFF-M2.md](HANDOFF-M2.md) | M2 解析层交接快照（进度/待办/既定口径/环境坑/DoD/命令速查） | ✅ M1 收尾落盘 2026-10-07 |
| [HANDOFF-M3.md](HANDOFF-M3.md) | M3 文献线引擎交接快照 | ✅ M2 收尾落盘 2026-10-07 |
| [HANDOFF-M4.md](HANDOFF-M4.md) | M4 全文线引擎交接快照 | ✅ M3 收尾落盘 2026-10-13 |
| [HANDOFF-M5.md](HANDOFF-M5.md) | M5 基准全集交接快照 | ✅ M4 收尾落盘 2026-10-13 |
| [HANDOFF-M6.md](HANDOFF-M6.md) | M6 桌面交付交接快照 | ✅ M5 收尾落盘 2026-10-13 |
| [HANDOFF-M7.md](HANDOFF-M7.md) | M7 脱敏发布交接快照 | ✅ M6 收尾落盘 2026-10-13 |
| [HANDOFF-M8.md](HANDOFF-M8.md) | M8 发布收尾交接快照（M7 末态：仓库已建/CI 五 job 绿，仅余 Release） | ✅ M7 收尾落盘 2026-10-13 |

## 决策记录

| 日期 | 决策 | 结论 |
|---|---|---|
| 2026-10-07 | 选题 | 系列第 11 题（不参赛）：参考文献格式检查器 v1 |
| 2026-10-07 | 发现 | GB/T 7714-2025 已于 2026-07-01 实施替代 2015 版 → 双标尺核心亮点 |
| 2026-10-07 | v2 升级 | "AI 时代为什么装工具"四支柱（全量批处理/可审计/状态沉淀/反向武器）→ 全流程审计工作台 |
| 2026-10-07 | v2.1 | 独特功能组：HalluRef-Bench 公开基准、Word 批注回写、指纹防篡改、体检分、扩展项四件 |
| 2026-10-07 | v2.2 | 反向引用推荐+一键插入：库内 BM25 防幻觉闭环、顺序编码制编号重排、Word/WPS COM 联动 |
| 2026-10-07 | **v3 升级（用户拍板）** | 毕业论文热门需求 A-F 全部并入、升级为**论文工作台**（方案一）：A 图表/公式/交叉引用审计重排（复用对账+重排内核）、B 学校格式模板核查（GB/T 7713.1→学校 profile，ruleset 第四档）、C 术语与数字用法一致性（GB/T 15835）、D AIGC 痕迹自检（风险提示版，启发式特征逐条挂依据）、E 综述辅助（聚类时间线+空白提示）、F 结构检查单（并入 B 条款库）；目录改名 `10-7-thesis-audit-workbench`；明确排除查重/降重/病句改写/答辩PPT |
| 2026-10-07 | 条文纪律 | GB/T 7714-2015/2025 实施信息✅；GB/T 7713.1、GB/T 15835-2011、ISO 26324、Crossref 文档待核对入库；规则未挂原文核对不得落库生效 |
| 2026-10-07 | **M0 骨架架构** | 目录三分 plan/data/code；代码根 code/（pyproject 在 code/，src 布局）；包名 thesis-audit-workbench、包 `taw`、CLI 名 `taw`；README/LICENSE/CI/.gitattributes 在仓库根 |
| 2026-10-07 | 运行时口径 | requires-python ≥3.8（本机 3.8.8 默认 + 3.12.10）；CI 四矩阵 ubuntu/windows × 3.8/3.12；全程 3.8 兼容写法；README/CI 一律 `python -m`（py 启动器无视 venv） |
| 2026-10-07 | CLI 契约 | exit 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0；`taw` 与 `python -m taw` 双入口（test_cli 锁定） |
| 2026-10-07 | 依赖分层 | extras：dev/docx/viz/gui/com/pkg；M0 core 零依赖；dev=pytest+pyyaml（测试期 import 覆盖守门） |
| 2026-10-07 | 换行纪律 | 本机 core.autocrlf=true 实测 → `.gitattributes * text=auto eol=lf` 入仓 + test_repo_gate 守门（字节冻结 fixtures 的前置） |
| 2026-10-07 | M0 交付范围 | 本会话=计划（plan/02-05）+骨架+本地提交；**远端建仓/push 待用户确认**（连同 D-1 仓库名、D-2 署名拍板） |
| 2026-10-07 | **D-1/D-2 拍板（用户确认）** | 仓库名 = `thesis-audit-workbench`（去日期前缀的纯净名，沿用系列惯例 `yuluo554/<kebab-name>`）；署名 = `yuluo554`（与既有项目一致，LICENSE/pyproject 无需改）。**远端建仓与 push 仍按计划留待 M7 脱敏发布**（M0 行"待确认"至此解除） |
| 2026-10-07 | **M1 数据先行完成** | 双生成器（gen_references seed=20261007 五类×噪声×错误注入 / gen_thesis_docx 声明式四类植入）+ 字节冻结 fixtures 入仓 + 位级一致/CR/真值守门；45 测试双解释器绿；REF-03 翻转 done |
| 2026-10-07 | **查证发现：GB/T 7713.1 已换版** | 现行版本 = **GB/T 7713.1-2025《信息与文献 编写规则 第1部分：学位论文》**（2025-08-01 发布 / 2026-02-01 实施，std.samr.gov.cn 在案）；2006 版《学位论文编写规则》废止；学校格式核查条款按 2025 版核对 |
| 2026-10-07 | **条文查证渠道收口（M1）** | 身份核实 ✅：std.samr.gov.cn（JSON API）+ openstd.samr.gov.cn；GB/T 7714 两版**全文官方不可得**（2015 废止不提供 / 2025 采标版权不提供——openstd 官方声明原文在案）→ 条款按纪律 pending，不空转；ISO 26324 pending（iso.org 403、代理 127.0.0.1:7897 实测失效）；doi.org handle API + api.crossref.org 官方行为实测 ✅；抓取原始件存 data/_private/sources/（不入仓） |
| 2026-10-07 | **D-4 HalluRef-Bench 规模拍板** | v1 = 200 条（genuine 100 + hallucinated 100 = 6 单类×16 + 复合 4）；格式冻结 v0.1（FORMAT.md + 12 条示例）；全量随 M3 以固定 seed 生成入库 |
| 2026-10-07 | docx 确定性收口（M1 实测） | python-docx writestr 会把**当前时间**写进 zip 条目（同秒两次才一致）→ 保存后重写 zip 固定 1980-01-01；重写后 1.1.2(3.8)/1.2.0(3.12) 产出字节一致；守门测试缺 docx **大声失败不静默跳过**，CI/README 增装 docx extras |
| 2026-10-07 | **M2 解析层完成** | RefCard/DocObjectCard/证据链 schema 落地（04 §九）；REF-01 四格式解析器 clean/light F1=1.0、heavy≥0.98；论文解析器 style_tree 62 段逐段一致+域/对象/悬空/幽灵全对账；`taw parse` 命令；89 测试双解释器绿；REF-01 翻转 done |
| 2026-10-07 | **M2 口径裁定（04 §九）** | ①文献解析 body 段语义**按结构推断不信类型标识**（标识错误是 M3 finding）；②噪声 flag 只记真跨行的条目（防 clean 文件 confidence 被系统性压低）；③F1 载体语义豁免（ris 无 edition、txt/csv 不渲染 edition==1）；④entry_type 不进解析 F1；⑤f1bench 对账 canonical 侧用入仓 `refs_logic.json`（零 tools 依赖，打包可用） |
| 2026-10-07 | **M2 发现 M1 合成论文真值矛盾三处** | 正文含真值未记录的提及（段22 图3-1、段41 式(4-1)）、声明的幽灵对象被正文提及（段49 图4-2）→ 改生成器措辞 + **整目录重生成**（冻结纪律）；新增生成器措辞纪律注释：幽灵对象正文零编号提及 |
| 2026-10-13 | **M3 规则激活裁定（关键）** | 四层 ruleset 规则 status 全 pending（GB/T 7714 全文官方不可得）→ 拆分为**正交双字段**：`status`=条款核对状态（决定能否引标准原文，保持 pending）、`activation`（active/gated）=检测生效开关（M3 文献线规则置 active 并挂 basis）。缺 activation 时回退 `status=="verified"`（M1 口径兼容）；findings 一律带 `clause_status`+`basis`，报告标注「条款待核对」，**NFR-04 不被削弱**（见 04 §十 10.1） |
| 2026-10-13 | **M3 判定纪律（误报 0 优先）** | 只判确定性可判项；证据不充分→manual_confirm 不硬判。三处实测裁定：①缺项判定须过「载体可表达性」（字段须在同文件同批次出现过，豁免 ris 无 edition 类差异）+「噪声门控」（带断行/连字符/空格修复 flag 时不判，year 抗噪豁免）；②著者「恰 3 位带等」不可区分（3 位误加 vs >3 正确截断，渲染串相同）→ 默认静默；③标点损伤被 M2 清洗归一，须在残留 flag/原文上判（见 04 §十 10.2） |
| 2026-10-13 | **M3 实测坑：pyvis in_line 仍带 CDN** | pyvis `cdn_resources="in_line"` 生成的 HTML 仍含 bootstrap CDN 的 `<link>/<script>`（plan/03 §五.3 预警的坑）→ 新增 `reftopo.sanitize_external` 剥离外部资源标签并过 `assert_no_external_refs` 硬断言；pyvis 缺装时走零依赖内置渲染器 |
| 2026-10-13 | **M3 合成数据白名单扩展** | M1 生成器所造 ISBN 校验位非真实（合成纪律产物，非幻觉信号）→ 登记 15 个虚构出版者段白名单，与 DOI `10.9999` 同一口径；HalluRef hallucinated 侧的 `10.7777` **刻意保持未登记**（须作可检信号，FORMAT.md 冻结口径） |
| 2026-10-13 | **M3 文献线引擎完成** | REF-02..09 全部实现；判定引擎骨架（activation/basis 与 status 正交）；taw.refcheck/refcite/refdedup/reffake/refrec/renumber/reftopo/reflib/docxutil/refbench/refaudit 落地；HalluRef-Bench v1 全量 200 条固定 seed 入库；`taw audit refs`/`audit bench` 命令；9 指标全过（误报 0 / 误合并 0 / 幻觉 genuine 误报 0 / 重排 100% / 双标尺全检出）；208 项双解释器绿；M2 F1 基线不回退 |
| 2026-10-13 | **M4 全文线规则翻转（gated→active）** | 五条全文线国标规则（TAW-xref-dangling/ghost、GBT15835-num、GBT7713-struct、TAW-aigc-signal）由 `gated` 翻转 `active`（各挂 basis，条款仍 pending）；M4 新增 4 条：TAW-style-01（样式）/TAW-term-01（术语）/TAW-xref-order-01（编号断档）/TAW-struct-checklist-01（结构检查单）；见 04 §十一 11.1 |
| 2026-10-13 | **M4 判定口径裁定（误报 0 优先）** | ①编号断档只在**同章同类**内比较（章间各自起编）；②AIGC 段落级 finding **仅由词汇型特征（aigc-02/03/04）越阈产出**，句长 CV（aigc-01）只进全文风险分布（中文段落 CV 天然偏低，单用会大面积误报）；③术语只报变体字面出现处，空白型变体（归一后同形）双向判（伪空格 T2 + 缺空格 T4）；④数字只在同值两形态并存时报，跳过参考文献与标题段；⑤学校格式核查只判结构性可判项（章标题层级/题注样式/正文误用标题）；见 04 §十一 11.2 |
| 2026-10-13 | **M4 AIGC 伦理边界硬编码** | FULL-04 输出恒为 `manual_confirm`（风险提示≠判定）；`ETHICS_STATEMENT` 强制声明段 + `assert_no_rewrite_surface()` 运行时守卫 + 守卫测试断言仓库不提供任何改写/降重通路（NFR/边界守卫 §四.4） |
| 2026-10-13 | **M4 全文线引擎完成** | FULL-01..06 全部实现；taw.figref/schoolfmt/termnum/aigccheck/reviewcl/structcheck/fullbench/fullaudit 落地；`frozen/review/`（综述语料 20 条）与 `knowledge/terminology.json`、`rulesets/layer4_school_demo.json` 新增；全文线 **5 指标全过**（悬空/幽灵 2/2+2/2、样式 FP=0、术语 4/4、AIGC 3/3 且 FP=0、聚类纯度 1.0）；`taw audit thesis` 全链 + `bench --line refs\|full\|all`；292 项双解释器绿；**M2 F1 + M3 9 指标复跑不回退** |
| 2026-10-13 | **M5 基准全集收口（14 指标固化）** | 两线 **14 指标一门跑全**（`taw audit bench --line all`）全达标（误报 0 优先）；README 指标表重写（含**复跑命令 + 环境**：离线/双解释器/报告无时间戳）；**指标 2 召回缺口 55/55 逐处归因**到 M3 既定判定纪律（UNKNOWN=0，新增 `test_bench_full.py` 钉死：14 指标齐全 + gate 全过 + 报告位级可重复 + 屏蔽 socket 全过）；M2 F1 + M3 9 + M4 5 三基线复跑留痕（`reports/m5_baseline_trace.txt`）；299 项双解释器绿；BENCH-01 翻转 done |
| 2026-10-13 | **M5 指标 2 召回缺口裁定** | 格式检出 recall=0.6944（FN=55）不是缺陷而是**误报 0 优先**的确定性后果：缺口逐处归因——噪声门控 18（带断行/连字符/空格修复 flag 的缺项不判）+ ris 载体豁免 9（ris 不渲染"等/others"）+ 文件级编码制混用 12（引擎按文件级报，逐条归因不到）+ 三著者带"等"歧义 6（渲染串不可区分）+ DOI/year 被噪声污染不可观察 6 + 载体签名不唯一 2 + 载体语义 2。**不弱化 gate**（FP=0 优先）；归因由 `refbench._fn_reason` 产出、`test_bench_full` 断言 UNKNOWN=0，任何新未归因 FN 即回归（见 04 §十二 12.2） |
| 2026-10-13 | **扩展项 P2 顺延（M7 清零决策）** | plan/05 依赖关系所列扩展项——arXiv 见刊提示 / 文献 CI watch / 自定义规则包导入导出 / 个人错误画像 / LLM 兜底 / 语义 rerank——**M5 前未收口**，按 P2 顺延至 M7 做清零决策（plan/01 §六 明确其为"三个显式开关扩展项"，非验收 P0/P1 必达项；P0/P1 = 两线 14 指标 + 两线功能闭环，均已达标）。M5 只固化**离线零 API 的 14 指标基准**，不引入联网通路（NFR-01/03 不受影响） |
| 2026-10-13 | **M6 GUI 单一事实源裁定（结构性落地）** | "GUI 只消费引擎 API"从口号变成结构保证：`taw.gui` 拆两半——`service`（**纯 Python 不 import Qt**：调编排 / 摊平 findings / 调引擎写盘函数）+ `app`（PySide6 窗口）。故"GUI 结论 == CLI 结论"可被无 GUI 环境单测（`test_gui_service` 断言与直接调 `refaudit` **逐字段 JSON 一致**）；条款 `pending` 在界面恒渲染「条款待核对」（NFR-04 不被削弱）；GUI 导出的任何 HTML 同样过 0 外链硬断言。见 04 §十三 13.1 |
| 2026-10-13 | **M6 离屏测试纪律裁定** | ①`tests/conftest.py` 在**收集前**置 `QT_QPA_PLATFORM=offscreen`（模块内 setdefault 管不了别处的导入顺序）；②GUI 测试模块用**模块级 try-import + `pytest.skip(allow_module_level=True)`** 声明式跳过——**不用 `pytest.importorskip`**（pytest 9.1 起其 ImportError 行为将升级为错误）；③CI 只在 Windows 装 `[gui]`（ubuntu 无系统图形库 → 整模块 skip，不伪装成通过） |
| 2026-10-13 | **M6 COM 定位与实机验收裁定** | COM 层 = **外挂触发壳**，判定通路仍在 `docxutil`/`reflib`/`refrec`（M3 已落地并有基准回归），本层不新增任何判定或改写能力（伦理边界继续生效）。实机验收断言：`reflib.write_comments` 注入的 Word 批注被**真实 Word/WPS 读回条数一致**（本机实测 6 findings → `Comments.Count=6`）；WPS 兼容范围以同一 `inspect_document` 接口实测（Word 16.0 + WPS 12.1.0.28505 并存各自应答）。CI 无 Office → 三条件（win32 + pywin32 + 注册表有 Office ProgID）缺一即整组 skip。见 04 §十三 13.2 |
| 2026-10-13 | **M6 WPS COM 收尾毛刺（实测坑）** | WPS 的 COM 服务在进程启停时偶发 RPC 异常 `0x800706be/0x800706ba`。两条处置：①**收集期只查注册表**（`registered_progid`），不 Dispatch——避免收集阶段启动/关闭 WPS 进程污染测试输出；②**会话释放顺序**定型：丢 Document 引用 + `gc.collect()` → `Quit()` → 丢 app 引用 → `CoFreeUnusedLibraries()` + `CoUninitialize()`（顺序错则 WPS 于收尾抛异常；Word 不在意，WPS 会）。见 04 §十三 13.2 |
| 2026-10-13 | **M6 onedir 打包裁定（首版踩坑）** | "onedir 双 exe"必须 EXE `exclude_binaries=True` + 交给 `COLLECT`：否则 EXE 把整包嵌进本体，产出 **57MB 的伪 onefile**（运行时解到 `_MEIxxxx`），违背 onedir 与"中立目录验内嵌数据"的前提。正确形态引导壳仅 8-10MB、`dist/taw/data/` 就地可读（`来源: pyinstaller-embedded`）。另：**内嵌数据必须带 `data/README.md`**（`paths.py::_is_valid` 的数据根标志），漏了则打包后数据目录判定失效而整体降级。见 04 §十三 13.3 |
| 2026-10-13 | **M6 构建红线与中立目录五连** | 两条构建收口脚本（`code/tools/`）：①`check_build_redline.py`——dist 禁区成分扫描（`_private/`、`.db`/`.env`/`.key`、真实实体关键词）+ 内嵌数据与仓库 `data/` **逐文件 SHA-256 对账**（missing/extra/mismatched 三类偏差全检出）；**合成数据里的虚构校名/人名不在黑名单**（防止红线误伤打包）。②`verify_neutral_dir.py`——dist 复制到**仓库树外** + **剥离 PATH**，五条命令逐条取**真实 returncode**（不接管道）。见 04 §十三 13.3 |
| 2026-10-13 | **M6 补 CLI 编码纪律（历史坑）** | 非 UTF-8 stdout（Windows CI 管道 cp1252）会把中文输出打成 `UnicodeEncodeError` 并崩在打印上（M5 交接的"预期环境坑"实测复现）。`cli._ensure_utf8_stdout()` 在 `main` 入口先 reconfigure（能切 UTF-8 则切，不能则 `errors="replace"`；`PYTHONIOENCODING` 已指 Unicode 时不动），`test_cli_survives_non_utf8_stdout` 用子进程复现 cp1252 钉死 |
| 2026-10-13 | **M6 桌面交付完成** | PySide6 GUI（`taw.gui.service` 纯 Python 服务层 + `app` 窗口；`taw gui` / `taw-gui` / `python -m taw.gui` 三入口 + `--check` 离屏自检）；COM 实机验证（Word/WPS 并存、批注读回条数一致、一键插入走 REF-07 内核）；PyInstaller onedir 双 exe + 构建红线 + 中立目录五连；**362 项双解释器绿**（3.8: 361 通过/1 跳过；3.12: 357 通过/5 跳过）；三基线复跑不回退（`reports/m6_delivery_trace.txt`）；registry 不变（16 项，M6 是交付层不改模块注册表）；**HANDOFF-M7 落盘** |
| 2026-10-13 | **M7 脱敏四步收口（发布门常驻）** | `code/tools/desensitize_audit.py`——脱敏四步（①源码 ②数据 ③文档 ④产物）+ 提交元数据盲区，一次 `--mode all` 覆盖跟踪树 + **全历史 blob** + 提交信息，`--mode dist` 覆盖构建产物本体。设计纪律：模式一律**片段拼接**构造（源码里不出现完整敏感字面值，扫描器自己过自己的扫描）、输出**不回显敏感串原文**（报告可随仓留档）、`--selftest` 阳性（6 类合成夹具）+ 阴性（GitHub noreply / 克隆 URL 不误判）对照。**实测四扫硬门 0 命中**，唯一复核项 = plan/00 的「系列第」表述（前作均已公开，保留）。接线：CI `test` job 跑 `--mode all`（**`fetch-depth:0`** 防浅克隆让历史扫描静默空跑）+ `package` job 跑 `--mode dist`；`test_repo_gate` 断言接线与自检（**收集总数保持 362**，不新增测试模块）。见 03 §五.10 |
| 2026-10-13 | **M7 提交元数据邮箱改写** | 发布前检查发现 10 个提交的 author/committer 邮箱为**个人邮箱**（内容级扫描覆盖不到的盲区）。远端尚未建仓 → 本地 `git filter-branch --env-filter` 统一改写为 **GitHub noreply**（`<id>+yuluo554@users.noreply.github.com`，与既有 12 个公开仓库惯例一致），清 `refs/original` + reflog expire + gc 后 `git log --all --format=%ae%ce` 实证 0 残留。`desensitize_audit` 的 `messages` 模式 + `test_commit_metadata` 口径自此常驻守门（非 noreply 邮箱即硬门命中） |
| 2026-10-13 | **M7 干净环境验证口径（收集数对账 = 362）** | `git archive HEAD` 导出干净树（内容 == 跟踪树，天然不含 `_private/`、无 `.git`）+ 独立 venv 按 README 逐条跑：`selfcheck`/`demo`/`parse`/`audit refs`/`audit thesis`/`bench all` 退出码全 0；`pip install -e "./code[dev,docx,viz,gui]"` 后 **收集数 = 362**（3.8/3.12 双解释器 356 通过/6 跳过）。**发现并修口径**：README 原只装 `[dev,docx,viz]` → `test_gui_app` 模块级 skip、收集数掉到 **353**（"双绿但悄悄少跑"的典型形态），故快速开始补 `[gui]` 并把「收集数对账」写成明示纪律（**收集数不随 extras 变，跳过数才变**） |
| 2026-10-13 | **M7 首跑 CI 暴露三处潜伏缺陷（已修）** | 建仓后**第一次**真跑 CI，5 job 全红，逐条定位到三处从未在本机 Windows 开发环境显形的缺陷：①**docx 跨平台位级一致破功**（ubuntu 两个 job）——`ZipInfo.create_system` 默认随平台变（Windows=0/Unix=3）并写进 zip "version made by"，冻结件在 Linux 重生成差一个字节（`\x00` vs `\x03`）；`gen_thesis_docx._save_deterministic` 与 `docxutil` 两处落盘点一律**钉 `create_system=0`**，已用 `create_system=3` 模拟 Linux 复现并验证。②**构建工具 cp1252 stdout 崩溃**（windows 三个 job）——M6 只给 `taw.cli` 补了 `_ensure_utf8_stdout`，`code/tools/` 收口脚本漏了；新增 `tools/_console.py` 共享收口，三个工具 `main()` 调用。③**dist 禁区规则误伤依赖缓存**——`--mode dist` 命中 `IPython/**/__pycache__/*.pyc`（pyvis 拉进的依赖自带缓存），按"只匹配 dist 顶层条目"收窄（依赖内部同名子目录/缓存不算；任意 `.pyc` 内嵌本地路径由字节级个人标记扫描兜住）。修后 **CI 五 job 全绿** |
| 2026-10-13 | **M7 扩展项 P2 清零决策（六项全不做）** | plan/05 依赖关系所列六项扩展项，M5 顺延至 M7 逐项清零（plan/01 §六 明确其为"三个显式开关扩展项"，**非 P0/P1 必达**；P0/P1 = 两线 14 指标 + 两线功能闭环，均已达标）。**结论：六项全部「不做」**——①**arXiv 见刊提示**：需联网 + 外部 API，违背 NFR-01「全本地离线零上传」主轴，且属"锦上添花"；②**文献 CI watch**：面向个人 GitHub Actions 的持续监控，与"桌面审计工具"定位不符，且需用户仓库写权限；③**自定义规则包导入导出**：`rulesets/layer4_*` 模板 + 用户导入通路**已就绪**（学校 profile 示例可跑），完整 UI 化导入导出属 P2 便利性，非验收项；④**个人错误画像**：需跨论文持久统计，涉及个人写作数据聚合，隐私面扩大且无验收价值；⑤**LLM 兜底**：违背「零 API、判定零 LLM」核心纪律（plan/03 §五.5：LLM 只可填"宁缺"槽位且不得产生/修改判定），引入即破坏确定性基线；⑥**语义 rerank**：需嵌入模型 + 联网或大模型权重，同理破坏离线确定性与 NFR-01/03。**共同理由**：六项均**不属 P0/P1 验收**、且多数与「全本地离线 + 零 API + 判定确定性」三条主轴冲突；M7 发布以此冻结范围。详见 03 §五 |

## 里程碑（M0–M7，详见 05）

- **M0 计划定稿+可运行骨架 ✅ 2026-10-07**：plan/02–05 定稿；taw 包（cli/registry/paths）+ 25 测试绿（3.8/3.12 双验证）+ CLI 冒烟 + CI 四矩阵 + 仓库卫生守门
- **M1 数据先行 ✅ 2026-10-07**：taw.rng splitmix64（金标跨解释器一致）；双生成器+真值入 `data/frozen/`（位级一致/CR 守门）；四层 ruleset 骨架+条款库（身份 verified/条款 pending 纪律）；HalluRef-Bench 格式冻结（D-4）；条文查证双渠道收口（7713.1-2025 换版发现）；45 测试双解释器绿
- **M2 解析层 ✅ 2026-10-07**：RefCard/DocObjectCard/证据链 schema 落地（04 §九）；REF-01 四格式解析器（txt/csv/bib/ris × clean/light/heavy，clean·light F1=1.0 / heavy ≥0.98）；论文解析器（style_tree 62 段逐段一致 + REF 域 2 + 对象 9 + 悬空 2 + 幽灵全对账）；`taw parse` 命令；89 测试双解释器绿；发现并修 M1 真值矛盾三处
- **M3 文献线引擎 ✅ 2026-10-13**：判定引擎骨架（`taw.engine`：四层叠加 + activation/basis 与条款 status 正交）；REF-02 格式核查与自动修正（六类检测，**误报 0**、修正 79/79 闭合）；REF-04 引用对账（悬空/幽灵/乱序/断档/著者-年）；REF-05 去重（**误合并率 0**，冲突→manual_confirm）；REF-06 幻觉画像（HalluRef-Bench v1 检出 100/100、genuine 误报 0）；REF-07 库内 BM25 防幻觉推荐 + 编号重排内核（一致性 **79/79=100%**）；REF-08 论证链拓扑（**0 外链硬断言**）；REF-09 SQLite 文献库/指纹防篡改/Word 批注回写；HalluRef-Bench v1 全量 200 条入库；`taw audit refs`/`audit bench`；208 项双解释器绿；M2 F1 基线不回退
- M4 全文线引擎 ✅ 2026-10-13：FULL-01 交叉引用审计与编号重排（悬空 2/2 + 幽灵 2/2，对象编号矩阵回归 **100%**，与 REF-07 同内核）；FULL-02 学校格式核查（样式检出 FP=0 + docx 节属性/页眉页脚/目录 + 学校 profile 导入）；FULL-03 术语与数字一致性（T1..T4 全检出 + GB/T 15835 千分位 + 变体热区）；FULL-04 AIGC 痕迹自检（A1/A2/A3 检出、干净段 FP=0、伦理边界硬编码 + 守卫断言）；FULL-05 综述辅助（TF-IDF 聚类纯度 **1.0** + 时间线 + 规则可判研究空白）；FULL-06 结构检查单（8 项）；全文线 **5 指标全过**；`taw audit thesis` + `bench --line refs\|full\|all`；292 项双解释器绿；M2 F1 + M3 9 指标不回退
- **M5 基准全集 ✅ 2026-10-13**：两线 **14 指标一门跑全**（`taw audit bench --line all`）全达标（误报 0 优先：解析 F1 1.0/1.0/0.9874、格式 FP=0、修正 79/79、对账 1.0、去重误合并 0、幻觉 100/100 genuine 误报 0、双标尺 2/2、推荐 R@5 0.7778/MRR 0.7222、重排 100%；全文线 悬空幽灵 2/2+2/2、样式 TP=3 FP=0、术语 4/4、AIGC 3/3 FP=0、聚类纯度 1.0）；README 评测表（14 指标 + 复跑命令 + 环境）；**指标 2 召回缺口 55/55 全归因**（UNKNOWN=0，`test_bench_full.py` 钉死）；报告无时间戳可重复；299 项双解释器绿；三基线复跑不回退；扩展项 P2 顺延 M7 清零
- **M6 桌面交付 ✅ 2026-10-13**：PySide6 GUI（`taw.gui.service` 纯 Python 服务层不 import Qt + `app` 窗口**只消费引擎 API**——与 CLI 逐字段一致，判定零复刻；条款 pending 恒渲染「条款待核对」；导出 HTML 过 0 外链断言；`taw gui` / `taw-gui` / `python -m taw.gui` 三入口 + `--check` 离屏自检）；**COM 实机验证**（本机 Word 16.0 + WPS 12.1.0.28505 并存：注入批注被真实 Office 读回条数一致、WPS 同一接口可用、一键插入走 REF-07 内核 + 独立复核）；**PyInstaller onedir 双 exe**（`taw.exe` + `taw-gui.exe` 共用 COLLECT，`exclude_binaries=True` 修掉伪 onefile 坑）；**构建红线**（dist 禁区 0 命中 + 内嵌数据逐文件 SHA-256 一致）+ **中立目录五连**（仓库树外 + 剥离 PATH，五条真实退出码全 0）；补 CLI 编码纪律（cp1252 不再崩）；362 项双解释器绿；三基线复跑不回退
- **M7 脱敏发布 ✅ 2026-10-13**：脱敏四步 + 产物扫描 + 干净环境验证 + CI 绿 + 公开仓库/Release + 收尾固化。**脱敏审计器**（`code/tools/desensitize_audit.py`：跟踪树/全历史/提交元数据/dist 产物四扫，`--selftest` 阳性+阴性对照，片段拼接防自命中）**四扫硬门 0 命中**；**提交元数据邮箱改写**（10 提交 → GitHub noreply）；**发布门接线 CI**（`--mode all|dist` + `fetch-depth:0` + `test_repo_gate` 接线守门）；**干净环境验证**（`git archive` 导出树 + 独立 venv 按 README 逐条跑通，**收集数对账 362**，双解释器 356 通过/6 跳过）；**CI 五 job 全绿**（首跑暴露并修掉三处潜伏缺陷：docx `create_system` 跨平台位级一致 / 构建工具 cp1252 stdout / dist 禁区规则误伤依赖缓存）；三基线复跑不回退；**362 项双解释器绿**；扩展项 P2 六项**清零决策**（全"不做+理由"）；公开仓库 [yuluo554/thesis-audit-workbench](https://github.com/yuluo554/thesis-audit-workbench)
