# data/ 数据台账

> 规则（ai-tool-project-sprint 阶段1）：每份数据登记来源与许可；规范条目挂出处+status；程序化自制带真值数据是核心资产（固定 seed 可复现，可注入已知缺陷做配对评测）。`_private/` 目录不入仓。
> M1（2026-10-07）起登记表正式启用；冻结产物禁手改，改体例=固定 seed 重新生成整目录提交。

## 登记表

| 数据 | 类型 | 来源 | 许可/纪律 | 状态 |
|---|---|---|---|---|
| `frozen/refs/`（refs-synthetic-v1，14 文件） | 合成文献表 fixtures（五类条目×噪声分层×错误注入，txt/csv/bib/ris + 真值） | 自制：`code/tools/gen_references.py`，`taw.rng` seed=20261007，注入模式表固定 | 全部虚构；DOI 10.9999/ 假前缀（白名单）；无时间戳、两次运行位级一致 | ✅ 入仓冻结，守门 `test_data_gate.py` |
| `frozen/thesis/`（thesis-synthetic-v1，3 文件） | 合成论文 docx + 真值（62 段 style_tree、9 对象、14 植入：样式/悬空/术语/AI 模式） | 自制：`code/tools/gen_thesis_docx.py`，声明式内容模型；zip 时间戳固定 1980-01-01 | 全部虚构（校名/人名/学号）；python-docx 1.1.2/1.2.0 产出字节一致（实测） | ✅ 入仓冻结，守门同上 |
| `rulesets/layer1_national.json` | 国标层规则包（12 规则，check_type 对齐 refs 真值） | 自制骨架；依据 GB/T 7714 / 7713.1-2025 / 15835-2011（条款原文均待核对） | status=pending 不生效；verified 须挂原文 | ✅ 入仓 |
| `rulesets/layer2_year_2015.json` / `layer2_year_2025.json` | 年份增量层（双标尺） | 自制骨架 | 同上 | ✅ 入仓 |
| `rulesets/layer3_journal_default.json` | 期刊 profile 占位 | 自制示例 | 同上 | ✅ 入仓 |
| `rulesets/layer4_school_template.json` | 学校 profile 导入模板 | 自制模板（含导入说明） | 用户导入条目挂"用户提供+日期" | ✅ 入仓 |
| `knowledge/gbt7714_2015.json` | 标准身份（2015-05-15 发布、2015-12-01 实施、**废止**） | 官方：std.samr.gov.cn + openstd.samr.gov.cn（件存 `_private/sources/`） | 官方元数据逐字在案 | ✅ 身份 verified；条款 pending |
| `knowledge/gbt7714_2025.json` | 标准身份（2025-12-02 发布、2026-07-01 实施、现行；**采标，openstd 无在线阅读**） | 同上 | 同上 | ✅ 身份 verified；条款 pending |
| `knowledge/gbt7713_1.json` | 标准身份（**现行版本 = GB/T 7713.1-2025**《信息与文献 编写规则 第1部分：学位论文》，2026-02-01 实施；2006 版废止） | 官方：std.samr.gov.cn | 同上 | ✅ 身份 verified；条款 pending |
| `knowledge/gbt15835.json` | 标准身份（GB/T 15835-2011 现行，2011-11-01 实施） | 官方：std.samr.gov.cn | 同上 | ✅ 身份 verified；条款 pending |
| `knowledge/iso26324.json` | 标准身份（iso.org 403 反爬、代理不可用 → **pending**）；DOI 解析服务行为已官方实测（doi.org handle API 200） | doi.org 官方 API | 403 件存 `_private/sources/` | ⬜ pending（渠道在案） |
| `knowledge/crossref_api.json` | Crossref REST API 行为实测（api.crossref.org 200，字段形状在案）；完整文档待补 | 官方 API 响应本体 | 响应件存 `_private/sources/` | ✅ API 形状 verified；文档 pending |
| `knowledge/aigc_features.json` | AIGC 启发式特征库（4 特征，逐条挂观察记录 basis；风险提示≠判定） | 自制观察记录 | basis 齐备；severity=warn | ✅ 入仓（status=pending 待外部依据复核） |
| `knowledge/doi_fake_prefixes.json` | DOI 假前缀白名单（10.9999） | 自制合成纪律 | 真实注册前缀不得入内 | ✅ 入仓 |
| `bench/halluref/`（3 文件） | HalluRef-Bench 格式冻结 v0.1：FORMAT.md + 12 条示例 + MANIFEST（D-4：v1=200 条，M3 生成全量） | 自制公开基准 | 全部虚构；幻觉类目 6 类冻结 | ✅ 入仓 |
| `_private/sources/` | 官方渠道原始件（std.samr JSON ×3、openstd HTML ×2、doi.org JSON、crossref JSON/HTML、iso 403 件） | curl 落盘 | **不入仓**（gitignore） | ✅ 本地留存 |

## 依据查证记录（M1 收口，2026-10-07）

**文献审计线**
- GB/T 7714-2015：身份双渠道官方核实 ✅（发布 2015-05-15 / 实施 2015-12-01 / **废止**）；全文 openstd 官方明示"废止标准不提供标准文本阅读服务" → 条款 pending ⬜
- GB/T 7714-2025：身份双渠道官方核实 ✅（发布 2025-12-02 / 实施 2026-07-01 / 现行）；**采标** → openstd 官方明示"涉及版权保护问题，暂不提供在线阅读服务" → 条款 pending ⬜（渠道与官方声明原文在案）
- GB/T 7713.1：**发现换版** ✅ → 现行版本为 **GB/T 7713.1-2025《信息与文献 编写规则 第1部分：学位论文》**（2025-08-01 发布 / 2026-02-01 实施），2006 版废止；条款 pending ⬜
- GB/T 15835-2011：身份官方核实 ✅（现行）；条款 pending ⬜
- ISO 26324：iso.org 403（反爬）+ 系统代理不可用 → 编号/现行版本 pending ⬜（渠道在案，不空转）；doi.org handle API 官方行为实测 ✅
- Crossref REST API：官方 API 实测核验 ✅（响应形状在案）；完整对接文档因 raw.githubusercontent 不可达 + crossref.org 文档页 404 → pending ⬜
- 学校模板 profile：用户自定义导入（rulesets/layer4 模板就绪），条目挂"用户提供+日期" ⬜
- AIGC 启发式特征库：4 特征逐条挂观察记录 ✅（status=pending，接入更强结论前须公开研究复核）

**查证纪律执行情况**
- 渠道：std.samr.gov.cn JSON API ✅ / openstd.samr.gov.cn ✅（身份与全文可得性）/ doi.org handle API ✅ / api.crossref.org ✅ / iso.org ✗（403）/ raw.githubusercontent.com ✗（000）/ 系统代理 ✗（000）
- 条款原文两渠道全败（官方明示不提供/版权）→ 按纪律全部 pending 继续推进，渠道记入 plan/00 决策表，不空转 ✅

**合成数据纪律**
- 合成文献的作者/刊名/DOI 全部虚构（DOI 10.9999/ 假前缀并登记白名单）✅；错误类型清单（标点/缺项/类型标识/著者数/编码制混用/结构矛盾）随 gen_references.py 落盘（error_taxonomy）✅
- 合成论文 docx：学校名/作者名/学号全部虚构 ✅；四类植入（样式错误/悬空标记/术语变体/AI 模式）随 gen_thesis_docx.py 落盘（truth.implants）✅
- AIGC 自检基准：干净基线文本 + 程序化植入已知 AI 模式（特征对接 aigc-01..04），风险提示≠判定 ✅
- 确定性守门：splitmix64 金标测试；两生成器位级一致守门（重跑逐字节比对）；CR 守门（文本冻结件无 CR）✅
