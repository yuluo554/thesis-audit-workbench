# HANDOFF-M2：解析层（M1 收尾交接快照，2026-10-07）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M2.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md) → 本文。

## 当前进度（M1 末态）

- **数据面全部就位**（M1 DoD 逐项达成，见 [05 §四](05-数据计划与里程碑.md) 里程碑表 M1 行）：
  - `taw.rng`：splitmix64 确定性 RNG，金标序列锁定（seed=42 八值 + seed=0 公开向量），3.8/3.12 各自命中同一金标 = 跨解释器一致；
  - `code/tools/gen_references.py`：72 条（五类 J/C/D/M/R × clean/light/heavy × 六类错误注入 + 6 复合注入），txt/csv/bib/ris 四格式 14 文件入 `data/frozen/refs/`；真值 `refs_truth.json`（主期望/also_expect 语义，模块 docstring 一次定清）；
  - `code/tools/gen_thesis_docx.py`：合成论文 62 段（样式树完整）+ 9 对象 + 14 植入（样式错误 3 / 悬空 2 / 幽灵 2 / 术语变体 4 / AI 模式 3）+ REF 域 2（一有效一悬空）入 `data/frozen/thesis/`；真值含 style_tree（M2 解析器 F1 基线）；
  - **确定性实测**：两生成器重跑逐字节一致 + 跨解释器（1.1.2/1.2.0）一致；守门测试 `code/tests/test_data_gate.py` 11 项（CR 守门跳过二进制 docx）；
  - 四层 ruleset 骨架 `data/rulesets/`（layer1 12 规则 + layer2 双年份 + 期刊占位 + 学校导入模板）；条款库 `data/knowledge/` 8 文件（4 项国标身份 verified / 条款全部 pending；aigc_features 4 特征；DOI 假前缀白名单）；
  - HalluRef-Bench 格式冻结 v0.1（`data/bench/halluref/`：FORMAT.md + 12 示例 + MANIFEST；**D-4 拍板 v1=200 条**，全量随 M3 生成）；
  - 条文查证收口：std.samr.gov.cn + openstd 官方核实四项国标身份；**发现 GB/T 7713.1 已换版为 2025 版**（2026-02-01 实施）；GB/T 7714 两版全文官方不可得（2015 废止 / 2025 采标版权，官方声明原文在案）→ 条款 pending 不空转；原始件存 `data/_private/sources/`（不入仓）。
- **45 测试双解释器全绿**（3.8.8 / 3.12.10；CLI 冒烟含内）；CI 增装 docx extras；REF-03 已翻转 done。
- 远端仍未建仓（D-1 仓库名 / D-2 署名待用户确认，见 00 决策表）。

## M2 待办（解析层，按序）

1. 参数卡 schema 定稿：RefCard/DocObjectCard（[04 §一](04-模块详设.md) 骨架级 → 实现级），在 04 追加小节记决策；
2. REF-01 文献解析器：txt/csv/bib/ris → RefCard；噪声清洗（断行合并、连字符断裂、全半角归一、空格伪影）+ confidence 分层 + 宁缺纪律（低置信不留值）；
3. 论文解析器：docx → 样式树/REF 域（fldSimple instr）/四类标记（图/表/公式/章）→ DocObjectCard；注意 fldSimple 内 run 不计入 python-docx `.text`（真值口径已锁定）；
4. 证据链 schema 落地（[04 §三](04-模块详设.md)）；
5. F1 基准：对 `refs_truth.json` 逐条对账（clean 条目任何非 pass=误报，主期望必须命中）；无噪 ≥0.99、强噪 ≥0.95；论文解析器对 style_tree 逐段一致 + 对象/标记/幽灵全对账；
6. `taw parse` 命令 + F1 报告（CLI 退出码契约不变；新子命令走 argparse 注册）；
7. registry REF-01 翻转 done（提交说明留痕）；plan/00/05 回写；台账登记新增数据；写 HANDOFF-M3。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

1. CLI 退出码 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0（`test_cli` 锁定）；
2. 数据目录五分支顺序：explicit > `TAW_DATA_DIR` > `sys._MEIPASS/data` > exe`/_internal/data` > CWD 上溯（`test_paths` 锁定）；
3. registry 16 项、ref 9 / full 6 / bench 1；REF-03=**done**，其余 planned（`test_registry` 锁定）；
4. `.gitattributes` eol=lf；workflow YAML 可解析且 jobs 完整；dev extras=pytest+pyyaml（`test_repo_gate` 锁定）；**CI 与 README 装 `.[dev,docx]`**（M1 守门需要）；
5. 包名 thesis-audit-workbench / 包目录 taw / CLI 名 taw；仓库根 = plan/data/code 三分；pyproject 在 code/；
6. requires-python ≥3.8，全程 3.8 兼容写法（禁 `X|Y` union 注解、match、3.9+ stdlib）；extras 组名 dev/docx/viz/com/gui/pkg 不改；
7. 里程碑编号 M0–M7；`taw demo`/`selfcheck` 输出含"16 项"计数；
8. **生成器真值语义**（M1 定清）：主期望必须命中、also_expect 并入非 pass 集合、clean 条目零期望（任何非 pass=误报）；语义改动=改口径记决策并重跑守门；
9. **`data/frozen/` 禁手改**：改体例=固定 seed 重新生成整目录提交，且须全量测试绿；CR 守门跳过二进制（docx 压缩流合法含 \r）；
10. **docx 产物确定性模式**：保存后重写 zip 固定时间戳（`gen_thesis_docx._save_deterministic`），后续任何 docx 产物复用此法；
11. 知识库纪律：identity_status 与 clauses status 分离；verified 必有 sources/quote；无出处不落库（pending 可展示不生效）；
12. DOI 假前缀白名单 `10.9999`（`data/knowledge/doi_fake_prefixes.json`）；新合成数据集用新假前缀先登记。

## 本机环境坑（只记实测过的）

- `core.autocrlf=true` 实测存在 → CR 守门已就位；**docx 属二进制需跳过**（压缩流合法含 \r）；
- 默认 `py` = 3.8.8；`py -3.12` 可用；**README/CI 一律 `python -m`**；双入口测试用 sysconfig 定位 `taw.exe`（勿改回裸 `taw`）；
- **python-docx writestr 把当前时间写进 zip 条目**（同秒两次构建才一致）——任何 docx 落盘必须重写收口；1.1.2(3.8)/1.2.0(3.12) 内容字节一致（重写后实测）；默认模板含 Caption/Heading 1-3/Table Grid 样式；
- 3.12 已装 python-docx 1.2.0（M1 装的）；pip 走 `NO_PROXY="*" no_proxy="*"` + 清华镜像；
- **系统代理 127.0.0.1:7897 实测失效（000）**：外网直连通 api.crossref.org ✅ / doi.org ✅ / std.samr.gov.cn ✅ / openstd.samr.gov.cn ✅；iso.org 403 反爬 ✗；raw.githubusercontent.com 000 ✗；
- std.samr.gov.cn 检索端点模式：`https://std.samr.gov.cn/gb/search/gbQueryPage?searchText=<URL编码标准号>&pageNumber=1&pageSize=10`（JSON，`C_STD_CODE` 含 `<sacinfo>` 标签需清洗）——后续查证复用；
- 全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip install）；Git Bash `/tmp` 与 Windows Python 互通以 Python `tempfile` 为准；**测试 45 项仍可整批跑，M2 起若 >120 项分批**；
- 生成器可直接跑（tools 脚本自带 `sys.path` 引导，无需 editable 安装）。

## M2 DoD（收尾逐项打勾，回写 plan/00/05）

- [ ] RefCard/DocObjectCard schema 定稿并记入 plan/04 追加小节；
- [ ] REF-01 四格式解析器实现；clean 层 F1 ≥0.99、强噪层 ≥0.95（对 refs_truth 对账报告落盘）；
- [ ] 论文解析器：style_tree 逐段一致（含 fldSimple 域口径）；对象/标记/悬空/幽灵全对账 thesis_truth；
- [ ] 证据链 schema 落地（三级判定 + location + quote）；
- [ ] `taw parse` 命令可用且退出码契约不变；
- [ ] 每解析器配生成样例回归（frozen fixtures 即回归输入，跑两次位级一致仍在）；
- [ ] registry REF-01 翻转 done；台账登记新增数据；plan/00/05 回写；HANDOFF-M3 落盘；
- [ ] 全量 pytest 绿（3.8 + 3.12，测试数对账防静默少跑）。

## 关键命令速查

```bash
cd <repo>/code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 全量测试（3.8，45 项）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 全量测试（3.12）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw selfcheck    # 环境自检
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw demo         # 模块注册表
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_references.py --force   # 重生成文献表（位级一致）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 tools/gen_thesis_docx.py --force  # 重生成合成论文（位级一致）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev,docx]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```
