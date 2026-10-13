# HANDOFF-M5：基准全集（M4 收尾交接快照，2026-10-13）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M5.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md) → [04-模块详设](04-模块详设.md)（§九 = M2、§十 = M3、**§十一 = M4 定稿，M5 直接在其上收口**）→ 本文。

## 当前进度（M4 末态）

**全文审计线 6 模块全部 done**（`registry.py` 已翻转，`test_registry` 新锁定）：REF-01..09 与 FULL-01..06 全 done，BENCH-01 仍 in_progress（M5 收口）。

| 模块 | 文件 | 能力 |
|---|---|---|
| FULL-01 交叉引用审计与重排 | `taw.figref` | 悬空（手打 + REF 域双载体）/ 幽灵对象 / 同类同章编号断档；对象编号重排复用 `taw.renumber` 内核（插入/删除矩阵 172 例 **100%**） |
| FULL-02 学校格式核查 | `taw.schoolfmt` | 样式核查三判据（章标题层级 / 题注样式 / 正文误用标题）；`read_doc_format` 抽节属性/页边距/纸张/页眉页脚/目录/封面要素；学校 profile（`layer4_school_*.json`）驱动模板核查 |
| FULL-03 术语与数字一致性 | `taw.termnum` + `knowledge/terminology.json` | 术语变体（含伪空格/缺空格双向）+ GB/T 15835 千分位不一致 + 变体热区（按段落/章节） |
| FULL-04 AIGC 痕迹自检 | `taw.aigccheck` + `knowledge/aigc_features.json` | 四特征（句长 CV / 模板连接词 / 总结套话 / 排比）；段落级 finding 仅词汇型特征越阈；**伦理边界硬编码 + `assert_no_rewrite_surface` 守卫** |
| FULL-05 综述辅助 | `taw.reviewcl` + `frozen/review/` | 自实现 TF-IDF + 余弦阈值聚类（纯度 1.0）+ 年代时间线 + 规则可判研究空白；**可视化复用 reftopo 0 外链路径**（`render_review_html` / CLI `--review-topology`） |
| FULL-06 结构检查单 | `taw.structcheck` | 8 项检查单（摘要四要素/关键词数/英文摘要/章节完整/章小结/结论呼应/标题层级） |
| 基准与编排 | `taw.fullbench` + `taw.fullaudit` | 全文线 5 指标 `run`/`write_report`；`audit_thesis` 全链 |

- **全文线 5 指标实测（`taw audit bench --line full`，零 API）**：
  1 悬空/幽灵检出 **2/2 + 2/2**（对象编号矩阵 172 例 **100%**）；
  2 样式核查 **TP=3/3 FP=0**；3 术语一致性 **TP=4/4**（+千分位 1 处）；
  4 AIGC 植入 **TP=3/3 FP=0**（伦理守卫通过）；5 综述聚类纯度 **1.0**、研究空白命中一致。
- **规则翻转（M3 §十 裁定落地）**：五条全文线国标规则 `gated`→`active`（各挂 basis，条款仍 pending）；
  M4 新增 4 条：`TAW-style-01`/`TAW-term-01`/`TAW-xref-order-01`/`TAW-struct-checklist-01`（见 04 §十一 11.1）。
- **测试 208 → 292 项**（新增 `test_figref/test_schoolfmt/test_termnum/test_aigccheck/test_reviewcl/test_structcheck/test_fullbench`；
  test_cli/test_data_gate/test_registry 扩展），**3.8 + 3.12 双解释器绿**。
- **数据面变动（冻结纪律内，全部位级一致守门）**：
  - 新增 `data/frozen/review/`（2 文件：`review_corpus.json` 20 条 + `review_truth.json`），生成器 `code/tools/gen_review_corpus.py`（声明式）；
  - 新增 `data/knowledge/terminology.json`（术语表 5 条 + 数字用法判据）；
  - 新增 `data/rulesets/layer4_school_demo.json`（示例学校 profile，虚构理工大学）；
  - `engine.load_ruleset_files` 扩为按 `layer4_school_*.json` 通配装载学校 profile（叠加序在模板之后）。
- 远端仍未建仓：D-1 仓库名 `thesis-audit-workbench` / D-2 署名 `yuluo554` 已拍板；建仓/push 留待 M7 脱敏发布，勿提前 push。

## M5 待办（基准全集收口）

M5 目标是**两线 14 指标全达标复跑固化**（plan/05 M5 行）：

1. **两线指标一次跑全与固化**：`taw audit bench --line all` 已有；M5 需
   - 把 14 指标表**写进 README**（M4 已写 9+5 两表，M5 复核并补"复跑命令 + 环境"）；
   - 确认 `--json` 报告落盘无时间戳、可重复（`reports/` 为运行产物不入仓）；
   - 双基线复跑纪律（见 §收尾）在 M5 收口时再跑一遍并留痕。
2. **扩展项收口（plan/05 依赖关系：M3/M4 之后、M5 前收口）**：arXiv 见刊提示 / 文献 CI watch / 规则包导入导出 / 个人错误画像 / LLM 兜底 / 语义 rerank——按 P2 处理，来不及则 M7 清零决策（在 plan/00 决策表登记）。
3. **指标达标复核**：确认每一项的"门槛"与 plan/01 §16、plan/02 §五 对账（误报 0 优先）；
   两线 14 指标清单：
   - 文献 9：分层解析 F1 / 格式检出率·误报率 / 修正准确率 / 对账准确率 / 去重 P·R / 幻觉画像检出率 / 双标尺差异检出率 / 推荐 Recall@5·MRR / 编号重排一致性；
   - 全文 5：悬空·幽灵检出 / 样式核查检出·误报率 / 术语一致性检出 / AIGC 植入检出 / 综述聚类与预分组对账。
4. **M5 DoD 回写** plan/00 状态表 + 决策表 + plan/05 M5 行；**HANDOFF-M6 落盘**；registry BENCH-01 视 M5 达成翻转 done（或保持 in_progress 至 M6 前）。
5. 收尾复跑 **M2 F1 基线 + M3 9 指标 + M4 5 指标**（三基线一起跑，见下）。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

1. CLI 退出码 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0（`test_cli` 锁定）；
   `parse` 子命令：0=全成功 / 1=部分失败或 docx 缺失降级 / 2=无路径或全失败；
   `audit refs`：0=跑通（含检出问题）/ 1=降级（数据目录缺）/ 2=用法输入错误；
   **`audit thesis`（M4 新增）**：同 `audit refs` 语义（0=跑通含检出 / 2=文件不存在或 docx 缺装）；
   **`audit bench --line {refs|full|all}`（M4 扩展）**：默认 `refs`（兼容既有调用）；
   `--json` 时**辅助信息走 stderr**（保证 stdout 是纯 JSON）。
2. 数据目录五分支顺序：explicit > `TAW_DATA_DIR` > `sys._MEIPASS/data` > exe`/_internal/data` > CWD 上溯（`test_paths` 锁定）；
3. registry 16 项、ref 9 / full 6 / bench 1；**REF-01..09 与 FULL-01..06 全 done、BENCH-01 in_progress**（`test_registry` 锁定）；
4. `.gitattributes` eol=lf；workflow YAML 可解析且 jobs 完整；dev extras=pytest+pyyaml；CI 与 README 装 `.[dev,docx]`（`test_repo_gate` 锁定）；
   **`viz` extras 未装时拓扑走内置降级渲染器**（3.12 本机未装 pyvis，测试覆盖该路径）；
5. 包名 thesis-audit-workbench / 包目录 taw / CLI 名 taw；仓库根 = plan/data/code 三分；pyproject 在 code/；
6. requires-python ≥3.8，全程 3.8 兼容写法（禁 `X|Y` union 注解、match、3.9+ stdlib）；extras 组名 dev/docx/viz/com/gui/pkg 不改；
7. 里程碑编号 M0–M7；`taw demo`/`selfcheck` 输出含"16 项"计数；`taw demo` 数据面行已含 review 文件数；
8. **生成器真值语义**：主期望必须命中、also_expect 并入非 pass 集合、clean 条目零期望（任何非 pass=误报）；
9. **`data/frozen/` 禁手改**：改体例=固定 seed 重新生成整目录提交 + 全量测试绿；CR 守门跳过二进制（docx）；
   `frozen/audit/`、`frozen/review/`、`bench/halluref/halluref_v1.*` 同受此纪律（守门已扩到 `data/bench/` 与 `frozen/review/`）；
10. **docx 产物确定性模式**：任何 docx 落盘必须重写 zip 固定时间戳 → 公共模块 `taw.docxutil`（`fix_zip_timestamps`/`finalize_comments`）；
11. 知识库纪律：identity_status 与 clauses status 分离；verified 必有 sources/quote；无出处不落库；
    **M4 新增 `terminology.json`** 每条 canonical/variants/basis 齐备（守门 `test_data_gate::test_terminology_library_grounded`）；
12. DOI 假前缀白名单 `10.9999`；HalluRef hallucinated 侧 `10.7777` 刻意不登记；ISBN 虚构出版者段白名单（15 段）；新合成数据集先登记再生成；
13. **规则激活口径（M3 裁定）**：`status`(条款核对) 与 `activation`(检测生效) 正交；
    `activation=active` 的规则**必须挂 `basis`**（守门 `test_data_gate::test_ruleset_activation_discipline`）；
    缺 `activation` 时回退 `status=="verified"`；findings 一律带 `clause_status`+`basis`，pending 条款报告标"条款待核对"；
14. **判定纪律（误报 0 优先，04 §十 10.2 + §十一 11.2）**：
    - 编号断档只在**同章同类**内比较（章间各自起编）；
    - **AIGC 段落级 finding 仅由词汇型特征（aigc-02/03/04）越阈产出**，句长 CV（aigc-01）只进全文风险分布（中文段落 CV 天然偏低）；
    - 术语只报变体字面出现处；空白型变体（归一后同形）双向判（伪空格 T2 + 缺空格 T4）；
    - 数字只在同值两形态并存（带/不带千分位）时报，跳过参考文献条目与标题段；
    - 学校格式核查只判结构性可判项（章标题层级 / 题注样式 / 正文误用标题）；
    - `page_range_or_consistency` 是**类别**（引擎产 `page_range` 或 `consistency` 之一即算命中）；
15. **拓扑/报告 0 外链**：`reftopo.sanitize_external` 剥离 pyvis 的 bootstrap CDN 标签后过 `assert_no_external_refs` 硬断言；
    新增任何 HTML 产物都必须过该断言（M4 未新增独立 HTML 产物，综述时间线走报告内 JSON）；
16. **F1 对账 canonical 侧**：`data/frozen/refs/refs_logic.json`（post-injection，缺陷态记录）——修正/修复类指标**不可**拿它当"正确目标"，用「修正闭合性」口径；
17. **AIGC 伦理边界（M4 硬编码）**：`aigccheck.ETHICS_STATEMENT` 强制声明 + `assert_no_rewrite_surface()` 守卫 +
    守卫测试断言仓库不提供改写/降重通路（NFR/边界守卫 §四.4）；不得为任何模块新增改写类 API。

## 本机环境坑（只记实测过的）

- `core.autocrlf=true` 实测存在 → CR 守门已就位（扩到 `data/bench/` 与 `frozen/review/`）；docx 属二进制需跳过；
- 默认 `py` = 3.8.8；`py -3.12` 可用；**README/CI 一律 `python -m`**；双入口测试用 sysconfig 定位 `taw.exe`；
- **python-docx writestr 把当前时间写进 zip 条目** → 任何 docx 落盘必须重写收口（`taw.docxutil`）；
  1.1.2(3.8)/1.2.0(3.12) 内容字节一致；默认模板含 Caption/Heading 1-3/Table Grid 样式；
  **默认模板页宽 215.9mm（Letter）非 A4** → `layer4_school_demo` 的 A4 规则据此报不符合（示例数据，非缺陷）；
- **本机 3.8 装了 pyvis、3.12 未装** → 拓扑测试需覆盖"pyvis 缺装走内置渲染器"路径（已覆盖）；
- 3.8 已装 python-docx 1.1.2、3.12 已装 1.2.0；pip 走 `NO_PROXY="*" no_proxy="*"` + 清华镜像；
- 系统代理 127.0.0.1:7897 实测失效（000）：外网直连通 api.crossref.org ✅ / doi.org ✅ / std.samr.gov.cn ✅；iso.org 403 ✗；raw.githubusercontent.com 000 ✗；
- std.samr.gov.cn 检索端点模式：`https://std.samr.gov.cn/gb/search/gbQueryPage?searchText=<URL编码标准号>&pageNumber=1&pageSize=10`；
- 全程 `PYTHONDONTWRITEBYTECODE=1`；**测试 292 项整批可跑（3.8 约 6.5s）**；
- 生成器可直接跑（tools 脚本自带 `sys.path` 引导，无需 editable 安装）；
- **控制台看中文用 `py -X utf8`**（`cat` 直读 UTF-8 会 mojibake，用 Python `read_text(encoding='utf-8')`）；
- **M2/M3 实测正则坑**：正则用 `str.format()` 会把 `\d{1,2}` 花括号当占位符 → 统一用 `%` 或拼接；
  字符类要含 ASCII `-`（`[-\u2014\u2013\uff0d]`）；源码写含引号/反斜杠的字符类正则用 raw 字符串 + 拆行拼接；
- **M4 实测坑**：`renumber` 内核对 `marker_id` 全局唯一有硬要求——对象/文献映射到内核时
  marker_id 必须带 item 前缀（`mk-<obj_idx>-<n>`），否则同段多对象共用 `mk-0` 会判"标记被多条目占用"（`figref.object_items` 已修正）；
- **M4 实测坑**：模块 docstring 含 `\s`/`\[` 等转义 → 用 `r"""..."""`，否则 DeprecationWarning（termnum 已修正）；
- **M4 实测坑**：守卫/自检函数名本身含被禁词（`assert_no_rewrite_surface` 含 "rewrite"）→ 结构守卫的扫描须显式排除自身名（`aigccheck.assert_no_rewrite_surface` 已排除）。

## M4 DoD（收尾逐项打勾，回写 plan/00/05）— ✅ 全部达成 2026-10-13

- [x] FULL-01 图表/公式/交叉引用审计与编号重排（`taw.figref`；悬空双载体 + 幽灵 + 同类同章断档；renumber 内核复用，矩阵 172 例 **100%**）；
- [x] FULL-02 学校格式模板核查（`taw.schoolfmt`；样式三判据 + docx 节属性/页眉页脚/目录 + 学校 profile 导入通路）；
- [x] FULL-03 术语与数字用法一致性（`taw.termnum` + `terminology.json`；T1..T4 全检出 + 千分位 + 变体热区）；
- [x] FULL-04 AIGC 痕迹自检（`taw.aigccheck`；A1/A2/A3 检出、干净段 FP=0、**伦理边界硬编码 + 守卫断言**）；
- [x] FULL-05 综述辅助（`taw.reviewcl` + `frozen/review/`；TF-IDF 聚类纯度 **1.0** + 时间线 + 规则可判研究空白）；
- [x] FULL-06 结构检查单（`taw.structcheck`；8 项检查单，全字面/样式确定性判据）；
- [x] 全文线 **5 指标基准达标**（`taw audit bench --line full`：悬空/幽灵 2/2+2/2、样式 FP=0、术语 4/4、AIGC 3/3 且 FP=0、聚类纯度 1.0）；
- [x] 类目门控测试（inactive/gated 规则零产出，`test_figref::test_inactive_rules_produce_nothing`）；
- [x] registry FULL-01..06 翻转 done；`frozen/review/`、`terminology.json`、`layer4_school_demo.json` 台账登记；plan/00/05/04 回写；**HANDOFF-M5 落盘**；
- [x] 全量 pytest 绿（3.8 + 3.12，**292 项**）+ **M2 F1 + M3 9 指标 + M4 5 指标复跑不回退**。

## 关键命令速查

```bash
cd <repo>/code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 全量测试（3.8，292 项）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 全量测试（3.12）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw selfcheck    # 环境自检
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw demo         # 数据面 + 模块注册表
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw parse ../data/frozen/refs/refs_clean.bib --json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw parse ../data/frozen/thesis/thesis_synthetic.docx --json

# 文献线全链
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit refs ../data/frozen/audit/refs_table.txt \
    --body ../data/frozen/audit/body.txt --report ../reports/audit.json \
    --topology ../reports/topo.html --library ../reports/lib.db

# 全文线全链（M4 新增）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit thesis ../data/frozen/thesis/thesis_synthetic.docx \
    --report ../reports/full.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit thesis ../data/frozen/thesis/thesis_synthetic.docx \
    --profile school-demo --report ../reports/full_school.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit thesis ../data/frozen/thesis/thesis_synthetic.docx \
    --review-topology ../reports/rev.html   # 综述聚类 0 外链 HTML（FULL-05 可视化）

# 基准（M4 扩展 --line）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit bench --line refs --report ../reports/refbench.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit bench --line full --report ../reports/fullbench.json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit bench --line all  --report ../reports/bench_all.json

# 生成器（重生成，位级一致）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_references.py --force      # 文献表
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_thesis_docx.py --force     # 合成论文
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_audit_fixtures.py --force  # 对账夹具
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_halluref_bench.py          # HalluRef-Bench v1
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_review_corpus.py --force   # 综述语料（M4 新增）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev,docx,viz]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

```bash
# 三基线复跑（收尾纪律：改历史等不动工作树操作后也要复跑）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -c "
import sys; sys.path.insert(0,'src')
from taw import f1bench, refbench, fullbench
r1 = f1bench.run('../data', detailed=True); f1bench.write_report(r1, '../reports/m2_parse_f1.json')
r2 = refbench.run('../data'); refbench.write_report(r2, '../reports/m3_refbench.json')
r3 = fullbench.run('../data'); fullbench.write_report(r3, '../reports/m4_fullbench.json')
print('M2 F1:', r1['gate']); print('M3 9指标:', r2['gate']['all_pass']); print('M4 5指标:', r3['gate']['all_pass'])"
```
