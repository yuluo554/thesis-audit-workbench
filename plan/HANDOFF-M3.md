# HANDOFF-M3：文献线引擎（M2 收尾交接快照，2026-10-07）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M3.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md) → [04-模块详设](04-模块详设.md)（§九 = M2 实现级定稿，**M3 直接在其上扩展**）→ 本文。

## 当前进度（M2 末态）

- **解析层全部就位**（M2 DoD 逐项达成，见 [HANDOFF-M2 §DoD](HANDOFF-M2.md)）：
  - `taw.cards`：RefCard / DocObjectCard / `make_finding` 证据链 schema（dict 构造器 + 校验；core 仍零依赖）；
  - `taw.refparse`：REF-01 四格式解析器（txt/csv/bib/ris），清洗管线 + 结构推断 body 语义 + confidence 分层 + 宁缺纪律；
  - `taw.thesisparse`：论文 docx 解析器（style_tree / REF 域 / 对象 / 标记 / 悬空 / 幽灵）；
  - `taw.f1bench`：F1 对账器（文献面 + 论文面，报告可由 `write_report` 落盘）；
  - `taw.cli`：新增 `taw parse <file> [--format] [--json] [--summary]`；
  - 测试 45 → **89 项**（`test_cards.py` / `test_refparse.py` / `test_thesisparse.py` 新增；test_cli 增 parse 用例）。
- **M2 F1 实测（`reports/m2_parse_f1.json`，运行产物不入仓）**：
  - 文献面逐格式逐层 F1：clean 全 1.0 / light 全 1.0 / heavy 0.98–0.9945；分层合计 clean·light=1.0、heavy=0.9874；门槛（clean≥0.99 / light≥0.97 / heavy≥0.95）**全过**；
  - 论文面：style_tree 62 段逐段一致、REF 域 2/2、对象 9/9（含 caption_para/mentioned/bookmark）、悬空 2/2、幽灵全对账；`gate.all_pass = true`。
- **数据面变动（冻结纪律内）**：
  - refs 目录新增 `refs_logic.json`（15 文件）——post-injection 逻辑记录，F1 对账 canonical 侧（使 f1bench 零 `code/tools/` 依赖，打包后可用）；
  - thesis 目录因修 M1 真值矛盾三处**整目录重生成**（详见 04 §九 9.5）；
  - `test_data_gate` 位级一致/CR/真值自洽守门全部仍绿。
- 远端仍未建仓：**D-1 仓库名 = `thesis-audit-workbench`、D-2 署名 = `yuluo554` 已拍板**（2026-10-07 用户确认，沿用系列惯例 `yuluo554/<kebab-name>`，LICENSE/pyproject 已一致）；建仓/push 仍按计划留待 M7 脱敏发布，勿提前 push。

## M3 待办（文献线引擎 REF-02/04/05/06/07/08/09，按序）

1. **判定引擎骨架**（`taw.engine`）：消费 RefCard + 四层 ruleset，产出 `[Finding]`（三级判定）；
   规则 status=pending 的一律不生效（"可展示不进判定"）；
2. **REF-02 格式核查与自动修正**：必著录项/标点/页码卷期/著者阈值/类型标识；
   机械项 auto 修正带 diff，逐条接受/回退；**类型标识错误在此产出**（M2 已把它排除出解析 F1）；
3. **REF-04 正文引用对账**：幽灵文献（正文引用而表无）、悬空引用、乱序断档、著者-年份不匹配；
4. **REF-05 去重合并**：DOI 精确 + 标题归一模糊 + 辅助证据；误合并率 0；
5. **REF-06 AI 幻觉画像**：DOI 校验位、时间逻辑矛盾、字段组合不可能统计特征；
   对接 `data/knowledge/doi_fake_prefixes.json` 与 HalluRef-Bench；
6. **REF-07 反向引用推荐 + 编号重排**：库内 BM25（自实现）+ `renumber` 内核（04 §五 签名）；
   任意插入/删除矩阵回归 100%；
7. **REF-08 论证链拓扑**：引用语境 → 论点支撑矩阵 → pyvis `cdn_resources="in_line"`（0 外链硬断言）；
8. **REF-09 本地文献库（SQLite）+ 独特功能组**（HalluRef-Bench 全量 200 条生成、批注回写、指纹、体检分）；
9. HalluRef-Bench 全量随 M3 以固定 seed 生成（D-4：v1=200 条 = genuine 100 + hallucinated 100）；
10. M3 DoD 回写 + registry 翻转 + HANDOFF-M4（含重排内核回归与 0 外链守门结果）。
    M3 收尾时复跑 **M2 F1 基线**（防解析层回退，纪律见 05 §五第 2 条）。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

1. CLI 退出码 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0（`test_cli` 锁定）；
   **`parse` 子命令**：0=全成功 / 1=部分失败或 docx 缺失降级 / 2=无路径或全失败；
2. 数据目录五分支顺序：explicit > `TAW_DATA_DIR` > `sys._MEIPASS/data` > exe`/_internal/data` > CWD 上溯（`test_paths` 锁定）；
3. registry 16 项、ref 9 / full 6 / bench 1；**REF-01=done、REF-03=done**，其余 planned（`test_registry` 锁定）；
4. `.gitattributes` eol=lf；workflow YAML 可解析且 jobs 完整；dev extras=pytest+pyyaml（`test_repo_gate` 锁定）；**CI 与 README 装 `.[dev,docx]`**（M1/M2 守门需要）；
5. 包名 thesis-audit-workbench / 包目录 taw / CLI 名 taw；仓库根 = plan/data/code 三分；pyproject 在 code/；
6. requires-python ≥3.8，全程 3.8 兼容写法（禁 `X|Y` union 注解、match、3.9+ stdlib）；extras 组名 dev/docx/viz/com/gui/pkg 不改；
7. 里程碑编号 M0–M7；`taw demo`/`selfcheck` 输出含"16 项"计数；
8. **生成器真值语义**（M1 定清）：主期望必须命中、also_expect 并入非 pass 集合、clean 条目零期望（任何非 pass=误报）；
9. **`data/frozen/` 禁手改**：改体例=固定 seed 重新生成整目录提交，且须全量测试绿；CR 守门跳过二进制（docx 压缩流合法含 \r）；
   **M2 新增 `refs_logic.json` 亦随生成器落盘**（改生成器逻辑记录格式=改口径，重跑守门）；
10. **docx 产物确定性模式**：保存后重写 zip 固定时间戳（`gen_thesis_docx._save_deterministic`），后续任何 docx 产物复用此法；
11. 知识库纪律：identity_status 与 clauses status 分离；verified 必有 sources/quote；无出处不落库（pending 可展示不生效）；
12. DOI 假前缀白名单 `10.9999`（`data/knowledge/doi_fake_prefixes.json`）；新合成数据集用新假前缀先登记；
13. **M2 解析口径**（04 §九，M3 消费时须遵守）：
    - 文献 body 段语义**按结构推断**（`//`→C / 报告号→R / 版次段→M / 卷期段→J），**不信文献类型标识**——标识错误是 REF-02 的 finding；
    - 噪声 flag 只记真跨行的条目；ris 字面 `"None"` 归一为缺失并记 `ris_none_value_artifact`；
    - F1 载体语义豁免（ris 无 edition、txt/csv 不渲染 edition==1）；
    - `entry_type` 不进解析 F1，但**在 `refs_logic.json` 中保留**供 REF-02 对账；
    - 论文对象提及：题注段自身编号不计为提及；公式段自身即提及；幽灵=零提及（含真值中 mentioned=[] 的第三个对象表3-1）。

## 本机环境坑（只记实测过的）

- `core.autocrlf=true` 实测存在 → CR 守门已就位；**docx 属二进制需跳过**（压缩流合法含 \r）；
- 默认 `py` = 3.8.8；`py -3.12` 可用；**README/CI 一律 `python -m`**；双入口测试用 sysconfig 定位 `taw.exe`（勿改回裸 `taw`）；
- **python-docx writestr 把当前时间写进 zip 条目**——任何 docx 落盘必须重写收口；1.1.2(3.8)/1.2.0(3.12) 内容字节一致；默认模板含 Caption/Heading 1-3/Table Grid 样式；
- 3.8 已装 python-docx 1.1.2、3.12 已装 1.2.0；pip 走 `NO_PROXY="*" no_proxy="*"` + 清华镜像；
- **系统代理 127.0.0.1:7897 实测失效（000）**：外网直连通 api.crossref.org ✅ / doi.org ✅ / std.samr.gov.cn ✅ / openstd.samr.gov.cn ✅；iso.org 403 反爬 ✗；raw.githubusercontent.com 000 ✗；
- std.samr.gov.cn 检索端点模式：`https://std.samr.gov.cn/gb/search/gbQueryPage?searchText=<URL编码标准号>&pageNumber=1&pageSize=10`（JSON，`C_STD_CODE` 含 `<sacinfo>` 标签需清洗）——后续查证复用；
- 全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip install）；Git Bash `/tmp` 与 Windows Python 互通以 Python `tempfile` 为准；**测试 89 项仍可整批跑，M3 起若 >120 项分批**；
- 生成器可直接跑（tools 脚本自带 `sys.path` 引导，无需 editable 安装）；
- **控制台看中文用 `py -X utf8`**（`cat`/`head` 直读 UTF-8 文件会 mojibake，用 Python `read_text(encoding='utf-8')` 读）；
- **M2 实测正则坑**：正则里用 `str.format()` 会把 `\d{1,2}` 的花括号当占位符报 KeyError → 统一改 `%` 格式化；破折号字符类要含 ASCII `-`（`[-\u2014\u2013\uff0d]`）。

## M3 DoD（收尾逐项打勾，回写 plan/00/05）

- [ ] 判定引擎骨架（三级判定 + 证据链消费 ruleset）落地；
- [ ] REF-02/04/05/06/07/08/09 全部实现；
- [ ] 文献线 9 指标基准达标（误报 0 优先）；
- [ ] 编号重排一致性：任意插入/删除矩阵回归 100%；
- [ ] 拓扑 HTML 0 外链硬断言；BM25 检索防幻觉闭环（推荐条目必经库内命中）；
- [ ] HalluRef-Bench v1 全量 200 条固定 seed 生成入库；
- [ ] registry 对应项翻转 done；台账登记新增数据；plan/00/05 回写；HANDOFF-M4 落盘；
- [ ] 全量 pytest 绿（3.8 + 3.12，测试数对账）+ **M2 F1 基线复跑不回退**。

## 关键命令速查

```bash
cd <repo>/code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 全量测试（3.8，89 项）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 全量测试（3.12）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw selfcheck    # 环境自检
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw demo         # 模块注册表
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw parse ../data/frozen/refs/refs_clean.bib --json  # 解析文献表
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_references.py --force   # 重生成文献表（位级一致）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_thesis_docx.py --force  # 重生成合成论文（位级一致）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev,docx]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

```bash
# M2 F1 基线复跑（收尾纪律：改历史等不动工作树操作后也要复跑）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -c "
import sys; sys.path.insert(0,'src')
from taw import f1bench
res = f1bench.run('../data', detailed=True)
f1bench.write_report(res, '../reports/m2_parse_f1.json')
print(res['gate'])"
```
