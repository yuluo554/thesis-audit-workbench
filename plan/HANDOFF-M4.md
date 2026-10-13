# HANDOFF-M4：全文线引擎（M3 收尾交接快照，2026-10-13）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M4.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md) → [04-模块详设](04-模块详设.md)（§九 = M2 定稿，**§十 = M3 定稿，M4 直接在其上扩展**）→ 本文。

## 当前进度（M3 末态）

**文献审计线 9 模块全部 done**（`registry.py` 已翻转，`test_registry` 新锁定）：

| 模块 | 文件 | 能力 |
|---|---|---|
| 判定引擎骨架 | `taw.engine` | 四层 ruleset 叠加（国标→年份→期刊→学校，`overrides` 留痕）；**`activation`/`basis` 与条款 `status` 正交**；证据链 finding 构造；免责声明 |
| REF-02 格式核查与自动修正 | `taw.refcheck` | 六类检测：缺项 / 标识错误 / 著者阈值 / 页码倒置 / 编码制混用 / 标点；双标尺换版检测；字段级 fix（接受/回退） |
| REF-04 正文引用对账 | `taw.refcite` | 引用标记解析（`[1]`/`[2,5-7]` + 著者-年份双制）；悬空/幽灵/乱序/断档/著者-年不匹配；引用语境提取 |
| REF-05 去重合并 | `taw.refdedup` | DOI 精确 + 标题归一模糊 + 著者-年份辅助；冲突字段→manual_confirm（**误合并 0**） |
| REF-06 幻觉画像 | `taw.reffake` | HalluRef 六类信号 + 风险分级 + 体检分；DOI/ISBN 合成白名单 |
| REF-07 推荐+重排 | `taw.refrec` + `taw.renumber` | 自实现 BM25（库内防幻觉闭环）；编号重排内核（插入/删除矩阵 100%） |
| REF-08 论证链拓扑 | `taw.reftopo` | 引用语境→支撑矩阵→pyvis `in_line` HTML；**0 外链硬断言** + CDN 消毒 |
| REF-09 文献库+独特功能组 | `taw.reflib` + `taw.docxutil` | SQLite 跨论文库/复用提示/常引统计；指纹防篡改；Word 批注回写（确定性）；体检分 |
| 基准与编排 | `taw.refbench` + `taw.refaudit` | 文献线 9 指标；`taw audit refs` 全链 |

- **9 指标基准实测（`taw audit bench`，零 API）**：
  1 分层解析 F1 clean/light/heavy 门槛全过（**M2 基线复跑不回退**）；
  2 格式检出 P=1.0 / **FP=0（clean FP=0）**；
  3 修正准确率 **79/79 = 1.0**；
  4 对账准确率 1.0（悬空/幽灵/乱序/著者-年四项全中）；
  5 去重 P=1.0 R=1.0 **误合并率 0**；
  6 幻觉画像 **检出 100/100、genuine 误报 0**；
  7 双标尺差异检出 2/2；
  8 推荐 Recall@5=0.7778 / MRR=0.7222；
  9 编号重排一致性 **79/79 = 100%**。
- **测试 89 → 208 项**（新增 `test_engine/test_refcheck/test_refcite/test_refdedup/test_reffake/test_refrec/test_reftopo_reflib/test_refbench`；test_cli/test_data_gate/test_registry 扩展），**3.8 + 3.12 双解释器绿**。
- **数据面变动（冻结纪律内，全部位级一致守门）**：
  - 新增 `data/frozen/audit/`（4 文件：refs_table.txt/.bib + body.txt + audit_truth.json）；
  - `data/bench/halluref/` 由 v0.1（12 示例）升级为 **v1 全量 200 条**（genuine 100 + hallucinated 100 = 6 单类×16 + 复合 4），D-4 达成；
  - 新增 `data/knowledge/standard_replacements.json`（双标尺替代关系，官方来源在案）；
  - `doi_fake_prefixes.json` 增 `isbn_fake_publisher_ranges`（15 段）。
- 远端仍未建仓：D-1 仓库名 `thesis-audit-workbench` / D-2 署名 `yuluo554` 已拍板；建仓/push 留待 M7 脱敏发布，勿提前 push。

## M4 待办（全文线引擎 FULL-01..06）

1. **FULL-01 图表/公式/交叉引用审计与重排**：复用 `refcite` 对账模式 + `renumber` 内核
   （M3 已泛化，`NumberedItem`/`MarkerRef` 结构通用）；消费 `taw.thesisparse` 的对象/标记/悬空/幽灵；
   任意插入/删除矩阵回归 100%（对象编号一套真值，M2 的 `thesis_truth` 已有 9 对象+2 悬空+2 幽灵）；
2. **FULL-02 学校格式模板核查**：docx 样式树/节属性/页眉页脚/目录 → 核对 `ruleset` 第四层
   （学校 profile，`layer4_school_template.json` 已有导入模板）；不符合项挂条款；GB/T 7713.1-2025；
3. **FULL-03 术语与数字用法一致性**：术语表（标准↔变体）+ GB/T 15835 数字用法 → 全文扫描 + 热区；
   M2 `thesis_truth` 已植入 4 处术语变体（T1-T4）+ 数字写法 2 处（T3 3500/3,500）；
4. **FULL-04 AIGC 痕迹自检**：消费 `data/knowledge/aigc_features.json`（4 特征 aigc-01..04，逐条挂 basis）；
   M2 植入 3 处 AI 模式（A1-A3）；**伦理边界硬编码**（报告强制声明"提示≠判定"、仓库不提供改写通路，守卫测试断言）；
5. **FULL-05 综述辅助**：TF-IDF 主题聚类 + 年代时间线（复用 `reftopo` 可视化）+ 规则可判研究空白提示；
6. **FULL-06 结构检查单**：摘要四要素/关键词数/章小结/结论呼应 → 挂 GB/T 7713.1-2025 的交互式检查单；
7. 全文线 5 指标基准（**扩展 `taw.refbench` 模式为 `taw.fullbench`**，或统一为 `taw.bench`）；
8. M4 DoD 回写 + registry 翻转（FULL-01..06）+ HANDOFF-M5；收尾复跑 **M3 文献线 9 指标 + M2 F1 基线**。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

1. CLI 退出码 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0（`test_cli` 锁定）；
   `parse` 子命令：0=全成功 / 1=部分失败或 docx 缺失降级 / 2=无路径或全失败；
   **`audit` 子命令（M3 新增）**：0=跑通（含检出问题）；1=降级（数据目录缺）；2=用法/输入错误；
   `audit refs --json` 时**辅助信息走 stderr**（保证 stdout 是纯 JSON，可机器解析）；
2. 数据目录五分支顺序：explicit > `TAW_DATA_DIR` > `sys._MEIPASS/data` > exe`/_internal/data` > CWD 上溯（`test_paths` 锁定）；
3. registry 16 项、ref 9 / full 6 / bench 1；**REF-01..09 全 done、FULL-01..06 全 planned、BENCH-01 in_progress**（`test_registry` 锁定，M4 翻转 FULL 时同步改）；
4. `.gitattributes` eol=lf；workflow YAML 可解析且 jobs 完整；dev extras=pytest+pyyaml；CI 与 README 装 `.[dev,docx]`（`test_repo_gate` 锁定）；**`viz` extras 未装时拓扑走内置降级渲染器**（3.12 本机未装 pyvis，测试覆盖该路径）；
5. 包名 thesis-audit-workbench / 包目录 taw / CLI 名 taw；仓库根 = plan/data/code 三分；pyproject 在 code/；
6. requires-python ≥3.8，全程 3.8 兼容写法（禁 `X|Y` union 注解、match、3.9+ stdlib）；extras 组名 dev/docx/viz/com/gui/pkg 不改；
7. 里程碑编号 M0–M7；`taw demo`/`selfcheck` 输出含"16 项"计数；
8. **生成器真值语义**：主期望必须命中、also_expect 并入非 pass 集合、clean 条目零期望（任何非 pass=误报）；
9. **`data/frozen/` 禁手改**：改体例=固定 seed 重新生成整目录提交 + 全量测试绿；CR 守门跳过二进制（docx）；
   **M3 新增 `frozen/audit/` 与 `bench/halluref/halluref_v1.*` 同受此纪律**（守门已扩到 `data/bench/`）；
10. **docx 产物确定性模式**：任何 docx 落盘必须重写 zip 固定时间戳 →
    **M3 抽为公共模块 `taw.docxutil`**（`fix_zip_timestamps` / `finalize_comments`），M4 复用；
11. 知识库纪律：identity_status 与 clauses status 分离；verified 必有 sources/quote；无出处不落库；
12. DOI 假前缀白名单 `10.9999`；**HalluRef hallucinated 侧 10.7777 刻意不登记**（须作可检信号）；
    **M3 新增 ISBN 虚构出版者段白名单**（`isbn_fake_publisher_ranges`，15 段）；新合成数据集先登记再生成；
13. **规则激活口径（M3 关键裁定，见 04 §十 10.1）**：`status`(条款核对) 与 `activation`(检测生效) 正交；
    `activation=active` 的规则**必须挂 `basis`**（守门 `test_data_gate::test_ruleset_activation_discipline`）；
    缺 `activation` 时回退 `status=="verified"`；findings 一律带 `clause_status`+`basis`，pending 条款报告标"条款待核对"；
14. **判定纪律（误报 0 优先，见 04 §十 10.2）**：只判确定性可判项；
    - 缺项：类型池 + **载体可表达性**（字段须在同文件同批次出现过）+ **噪声门控**（带修复 flag 不判，`year` 豁免）；
    - 著者「恰 3 位带等」→ 默认静默（不可区分），`strict=True` 才产 manual_confirm；
    - 标点：M2 清洗会归一全角 → 须在残留 flag/原文上判，**不能只看 card**；
    - `page_range_or_consistency` 是**类别**：引擎产 `page_range` 或 `consistency` 之一即算命中（基准口径）；
15. **拓扑/报告 0 外链**：`reftopo.sanitize_external` 剥离 pyvis 的 bootstrap CDN 标签后过
    `assert_no_external_refs` 硬断言；新增任何 HTML 产物都必须过该断言；
16. **F1 对账 canonical 侧**：`data/frozen/refs/refs_logic.json`（post-injection）——它是**缺陷态**记录，
    修正/修复类指标**不可**拿它当"正确目标"（M3 实测踩坑：fix 正确方向恰与 logic 相反），
    修复类指标应用「修正闭合性」口径（应用 fix 后重查该 finding 消失）。

## 本机环境坑（只记实测过的）

- `core.autocrlf=true` 实测存在 → CR 守门已就位（**M3 已扩到 `data/bench/`**）；docx 属二进制需跳过；
- 默认 `py` = 3.8.8；`py -3.12` 可用；**README/CI 一律 `python -m`**；双入口测试用 sysconfig 定位 `taw.exe`；
- **python-docx writestr 把当前时间写进 zip 条目** → 任何 docx 落盘必须重写收口（M3 收进 `taw.docxutil`）；
  1.1.2(3.8)/1.2.0(3.12) 内容字节一致；默认模板含 Caption/Heading 1-3/Table Grid 样式；
- **本机 3.8 装了 pyvis、3.12 未装** → 拓扑测试需覆盖"pyvis 缺装走内置渲染器"路径（已覆盖）；
- 3.8 已装 python-docx 1.1.2、3.12 已装 1.2.0；pip 走 `NO_PROXY="*" no_proxy="*"` + 清华镜像；
- **系统代理 127.0.0.1:7897 实测失效（000）**：外网直连通 api.crossref.org ✅ / doi.org ✅ /
  std.samr.gov.cn ✅ / openstd.samr.gov.cn ✅；iso.org 403 ✗；raw.githubusercontent.com 000 ✗；
- std.samr.gov.cn 检索端点模式：`https://std.samr.gov.cn/gb/search/gbQueryPage?searchText=<URL编码标准号>&pageNumber=1&pageSize=10`；
- 全程 `PYTHONDONTWRITEBYTECODE=1`；**测试 208 项可整批跑（3.8 约 4s），M4 起若 >300 项分批**；
- 生成器可直接跑（tools 脚本自带 `sys.path` 引导，无需 editable 安装）；
- **控制台看中文用 `py -X utf8`**（`cat` 直读 UTF-8 会 mojibake，用 Python `read_text(encoding='utf-8')`）；
- **M2 实测正则坑**：正则里用 `str.format()` 会把 `\d{1,2}` 花括号当占位符 → 统一用 `%` 或拼接；
  字符类要含 ASCII `-`（`[-\u2014\u2013\uff0d]`）；
- **M3 实测坑**：源码里写含引号/反斜杠的字符类正则时，**用 raw 字符串 + 拆行拼接**，
  否则 `"..."` 与 `r"..."` 混用会踩 `EOL while scanning string literal`（refdedup 原生字符串 `\s` 也会告警）；
- **M3 实测坑**：pyvis `cdn_resources="in_line"` 产出的 HTML **仍含 bootstrap CDN 引用**（必须消毒）；
- **M3 实测坑**：`--json` 模式下任何 `print` 辅助信息都会污染 stdout，须走 stderr。

## M3 DoD（收尾逐项打勾，回写 plan/00/05）— ✅ 全部达成 2026-10-13

- [x] 判定引擎骨架（三级判定 + 证据链消费 ruleset）落地（`taw.engine`；activation/basis 与 status 正交，04 §十 10.1）；
- [x] REF-02/04/05/06/07/08/09 全部实现（`taw.refcheck/refcite/refdedup/reffake/refrec/renumber/reftopo/reflib`）；
- [x] 文献线 9 指标基准达标（**误报 0 优先**：格式 FP=0 / clean FP=0 / 误合并 0 / 幻觉 genuine 误报 0）；
- [x] 编号重排一致性：任意插入/删除矩阵回归 **79/79 = 100%**；
- [x] 拓扑 HTML **0 外链硬断言**（`sanitize_external` + `assert_no_external_refs`）；BM25 检索防幻觉闭环（推荐条目必经库内命中，`insert_reference` 拒绝库外 id）；
- [x] HalluRef-Bench v1 全量 **200 条**固定 seed 生成入库（位级一致 + CR 守门）；
- [x] registry 对应项翻转 done（REF-02..09；BENCH-01 in_progress，全文面待 M4）；台账登记新增数据；plan/00/05 回写；**HANDOFF-M4 落盘**；
- [x] 全量 pytest 绿（3.8 + 3.12，**208 项**）+ **M2 F1 基线复跑不回退**（clean/light/heavy 门槛全过、thesis pass）。

> M3 关键裁定与实测坑均在 plan/04 §十 与 plan/00 决策表留痕；三处判定纪律（载体可表达性/恰 3 位歧义/标点须看原文）见 04 §十 10.2。

## 关键命令速查

```bash
cd <repo>/code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 全量测试（3.8，208 项）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 全量测试（3.12）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw selfcheck    # 环境自检
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw demo         # 数据面 + 模块注册表
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw parse ../data/frozen/refs/refs_clean.bib --json
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit refs ../data/frozen/audit/refs_table.txt \
    --body ../data/frozen/audit/body.txt --report ../reports/audit.json \
    --topology ../reports/topo.html --library ../reports/lib.db   # 文献线全链
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit bench --report ../reports/refbench.json   # 9 指标
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_references.py --force      # 重生成文献表（位级一致）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_thesis_docx.py --force     # 重生成合成论文（位级一致）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_audit_fixtures.py --force  # 重生成对账夹具
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_halluref_bench.py          # 重生成 HalluRef-Bench v1
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev,docx,viz]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

```bash
# 双基线复跑（收尾纪律：改历史等不动工作树操作后也要复跑）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -c "
import sys; sys.path.insert(0,'src')
from taw import f1bench, refbench
r1 = f1bench.run('../data', detailed=True); f1bench.write_report(r1, '../reports/m2_parse_f1.json')
r2 = refbench.run('../data'); refbench.write_report(r2, '../reports/m3_refbench.json')
print('M2 F1:', r1['gate']); print('M3 9指标:', r2['gate'])"
```
