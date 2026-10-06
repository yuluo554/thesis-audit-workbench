# HANDOFF-M1：数据先行（M0 收尾交接快照，2026-10-07）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M1.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md) → 本文。

## 当前进度（M0 末态）

- **plan/ 六份文档定稿**：00 总览 / 01 题目 v3 / 02 需求解读 / 03 架构与技术选型 / 04 模块详设 / 05 数据与里程碑；本 HANDOFF 为 M1 交接。
- **骨架可运行**（code/ 为代码根，src 布局）：
  - `code/src/taw/`：`__init__`(0.1.0)、`__main__`、`cli.py`（selfcheck + demo；exit 0/1/2 契约）、`registry.py`（16 模块注册表）、`paths.py`（数据目录五分支冻结顺序）；
  - `code/pyproject.toml`：包名 thesis-audit-workbench，CLI 名 `taw`，extras = dev/docx/viz/gui/com/pkg，core 零依赖；
  - 测试 4 模块 **25 项全绿**（py3.8.8 与 py3.12.10 双解释器验证）；CLI 冒烟 OK（数据目录 cwd-walk 命中，注册表 16 项）。
- **仓库卫生**：`.gitattributes`（`* text=auto eol=lf`）、`.gitignore`（含 `!code/tools/*.spec` 例外）、LICENSE(MIT)、README（🚧 M0 状态）、`.github/workflows/ci.yml`（ubuntu/windows × 3.8/3.12 四矩阵，dev extras 安装 + pytest + CLI 冒烟）。
- 本地 git 已提交；**远端未建**——建仓+push 属对外动作，待用户确认（连同 D-1 仓库名、D-2 署名，见 00 决策表）。

## M1 待办（数据先行，按序）

1. `taw.rng`：splitmix64 确定性 RNG + 跨解释器序列一致测试（3.8/3.12 同 seed 同序列）；
2. `gen_references.py`：五类条目（期刊/会议/学位/图书/报告）× 噪声分层（无噪/轻噪/强噪）× 错误注入（标点/缺项/类型标识/著者数/编码制混用/结构矛盾）；真值 JSON（**主期望 + also_expect 语义见 plan/04 §七**）；DOI 一律 `10.9999/` 假前缀；
3. `gen_thesis_docx.py`：合成论文 docx 四类植入（样式错误/悬空标记/术语变体/AI 模式）+ 真值；启用 extras `docx`；
4. 四层 ruleset 骨架 JSON 落 `data/rulesets/` + 条款库落 `data/knowledge/`（status=verified/pending 纪律）；
5. 条文查证：GB/T 7714-2015/2025、GB/T 7713.1、GB/T 15835、ISO 26324、Crossref——curl 落盘本地提取，禁摘要工具转述；**两渠道全败 → 标 pending 继续推进**，已查渠道记入 00 决策表（不空转）；
6. HalluRef-Bench 目录与条目格式定稿（`data/bench/halluref/`；规模拍板 = 00 决策 D-4）；
7. `data/frozen/` 首批字节冻结 fixtures 入仓 + **位级一致守门**（生成两次逐字节比对）+ **CR 守门测试**（冻结文件出现 CR 即大声失败）；
8. `data/README.md` 台账登记；`registry.py` REF-03 状态翻转；plan/00/05 回写；写 HANDOFF-M2。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

1. CLI 退出码 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0（`test_cli` 锁定）；
2. 数据目录五分支顺序：explicit > `TAW_DATA_DIR` > `sys._MEIPASS/data` > exe`/_internal/data` > CWD 上溯；explicit/env 设置但无效**大声抛 FileNotFoundError**（`test_paths` 锁定）；
3. registry 16 项、ref 9 / full 6 / bench 1（`test_registry` 锁定）；模块 id 体系 REF-01..09 / FULL-01..06 / BENCH-01；
4. `.gitattributes` eol=lf；workflow YAML 可解析且 jobs 完整；dev extras 覆盖测试期 import（pytest+pyyaml）（`test_repo_gate` 锁定）；
5. 包名 thesis-audit-workbench / 包目录 taw / CLI 名 taw；仓库根 = plan/data/code 三分；pyproject 在 code/；
6. requires-python ≥3.8，全程 3.8 兼容写法（禁 `X|Y` union 注解、match、3.9+ stdlib）；extras 组名 dev/docx/viz/com/gui/pkg 不改；
7. 里程碑编号 M0–M7；`taw demo`/`selfcheck` 输出含"16 项"计数；
8. 落盘产物**无时间戳**、生成**确定性**（M1 起配守门）；台账/条款**无出处不落库**（pending 可展示、不生效）。

## 本机环境坑（只记实测过的）

- `core.autocrlf=true` 实测存在 → `.gitattributes` 已配；M1 冻结 fixtures 落地后必须加 CR 守门测试；
- 默认 `py` = 3.8.8；`py -3.12` 可用（pytest 已装）；**README/CI 一律 `python -m`**（`py` 启动器无视 venv，系列实录）；
- pip 25.0.1 / setuptools 75.3.4 够新；pip 装包走 `NO_PROXY="*" no_proxy="*"` + 清华镜像（注册表系统代理污染 `127.0.0.1:7897`）；
- 本机系统 3.8 已装 python-docx / pyvis / PySide6（前作遗留）——`selfcheck` 显示"已装"是本机现象，**不代表 extras 已声明**；干净环境验证在 M7；
- `Python38/Scripts` 不在 PATH → 双入口测试用 `sysconfig` 绝对路径定位 `taw.exe`（已如此实现，勿改回裸 `taw` 调用）；
- 全程 `PYTHONDONTWRITEBYTECODE=1`（含 pip install，防 pyc 损坏）；Git Bash `/tmp` 与 Windows Python 不通，临时文件用工作区相对路径；测试多时分批（M2 起）。

## M1 DoD（收尾逐项打勾，回写 plan/00/05）

- [ ] splitmix64 跨解释器（3.8/3.12）序列一致测试绿；
- [ ] 两个生成器 `--force` 连跑两次**位级一致**（git status 零变化）；
- [ ] `data/frozen/` 首批入仓；CR 守门测试绿；位级一致守门测试绿；
- [ ] ruleset/条款库骨架 JSON 入库，每条挂出处+status；无出处条目 status=pending（不生效）；
- [ ] 条文查证：每条已核对 ✅ 或"待核对"留档（渠道记入 00 决策表），无空转；
- [ ] HalluRef-Bench 目录+格式+规模定稿并登记台账；
- [ ] 台账登记全部新数据；registry/plan 回写；HANDOFF-M2 落盘；
- [ ] 全量 pytest 绿（3.8 + 3.12）；（解析 F1 基准 M2 起才有，本次无基准项）。

## 关键命令速查

```bash
cd <repo>/code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 全量测试（3.8）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 全量测试（3.12）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw selfcheck    # 环境自检
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw demo         # 模块注册表
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```
