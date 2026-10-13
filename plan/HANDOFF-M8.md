# HANDOFF-M8：发布收尾（M7 脱敏发布交接快照，2026-10-13）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M8.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md)（M7 行）→ [03-架构与技术选型](03-架构与技术选型.md)（§五横切纪律）→ 本文。

## 当前进度（M7 末态）

**M7 脱敏发布主体全部达成**（16 项 registry 不变——M7 是发布层，不改模块注册表）：

| 交付面 | 实测结果 |
|---|---|
| 公开仓库 | **https://github.com/yuluo554/thesis-audit-workbench**（public，main 分支，`gh repo create` 建仓 + `git push`） |
| GitHub Release | **v0.1.0 已发布**（经用户确认）：[releases/tag/v0.1.0](https://github.com/yuluo554/thesis-audit-workbench/releases/tag/v0.1.0)，附件 `thesis-audit-workbench-v0.1.0-win64.zip`（70,115,631 字节，dist onedir 双 exe） |
| 脱敏四步 | `code/tools/desensitize_audit.py`：跟踪树 + **全历史 blob** + 提交元数据 + dist 产物 **四扫硬门 0 命中**（唯一复核项 = plan/00 系列表述，前作均已公开） |
| 提交元数据 | 10 个提交 author/committer **已由个人邮箱改写为 GitHub noreply**（`filter-branch` + gc，`git log` 实证 0 残留） |
| 发布门接线 | CI `test` job `--mode all`（`fetch-depth:0`）+ `package` job `--mode dist`；`test_repo_gate` 接线守门（**收集总数保持 362**） |
| 产物本体扫描 | `check_build_redline.py` dist 禁区 0 命中 + 内嵌数据逐文件 SHA-256 一致；`--mode dist` 0 命中 |
| 干净环境验证 | `git archive` 导出树 + 独立 venv 按 README 逐条跑通（**收集数对账 = 362**；3.8/3.12 双解释器 356 通过/6 跳过） |
| CI 五 job | **全绿**（test 四矩阵 ubuntu/windows × 3.8/3.12 + package：onedir 构建 + 红线 + dist 脱敏 + 中立目录五连） |
| 构建产物 | `dist/taw/taw.exe`（8.2MB，console=True）+ `dist/taw/taw-gui.exe`（10.1MB，console=False） |
| 测试规模 | **362 项收集**；本机 3.8: 361 通过/1 跳过；3.12: 357 通过/5 跳过 |
| 三基线复跑 | M2 F1 all_pass + M3 9 指标 all_pass + M4 5 指标 all_pass，**无回退** |
| 扩展项 P2 | **六项全「不做」清零决策**，理由入 plan/00 决策表 |

- **Release/tag 已完成**：`v0.1.0`（与 `pyproject.toml` version=0.1.0 一致）已打 tag + 建 Release，
  附 dist onedir zip；**经用户确认后执行**（DoD 要求）。

## 待办（无阻塞项）

M7 全部达成。后续若继续：可考虑把 `reports/m7_release_trace.txt` 的脱敏留痕归档，
或按需推进 plan/00 决策表里被清零的扩展项（当前结论：六项全不做）。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

> M7 新增口径见下；前序口径与 HANDOFF-M7 一致。

1. **发布门（03 §五.10）**：`desensitize_audit.py` 四步（源码/数据/文档/产物）+ 提交元数据盲区；
   硬门类别：email / user-dir-path / personal-marker / phone / id-card / secret-key /
   sensitive-filename / forbidden-component；复核项（非硬门）：abs-path / series-mention；
2. **脱敏扫描器纪律**：模式**片段拼接**构造（源码不含完整敏感字面值，扫描器自过）；
   输出**不回显敏感串原文**；`--selftest` 阳性 6 类 + 阴性（noreply/克隆 URL）对照；
   无 git（`git archive` 导出树）时 `_tracked_files()` 退回剪枝遍历（按 `pyvenv.cfg` 剪 venv）；
3. **dist 禁区规则只匹配顶层**：`plan|tests|code|docs|reports|_private|.git`、顶层 `__pycache__`、
   `*.egg-info`、`*.pyc`——依赖包内部同名子目录/缓存**不算**（实测 IPython 自带 tests/__pycache__）；
   任意 `.pyc` 内嵌本地绝对路径由字节级个人标记扫描兜住；
4. **提交元数据邮箱 = GitHub noreply**（`<id>+yuluo554@users.noreply.github.com`）：
   非 noreply 邮箱即硬门命中（`test_repo_gate` + `messages` 模式锁定）；
5. **收集数对账 = 362**：README 快速开始必须装 `[dev,docx,viz,gui]`（缺 `[gui]` → `test_gui_app`
   模块级 skip、收集数掉到 353）。**收集数不随 extras 变，跳过数才变**；
6. **docx 跨平台位级一致**：`ZipInfo.create_system` 必须显式钉 `0`（默认随平台变，Windows=0/Unix=3，
   写进 zip "version made by"）——`gen_thesis_docx._save_deterministic` + `docxutil` 两处落盘点；
7. **构建工具 stdout 编码**：`code/tools/` 收口脚本一律 `from _console import ensure_utf8_stdout`
   并在 `main()` 首行调用（Windows CI cp1252 打印中文会崩）；
8. CI 五 job 结构：test 四矩阵 + package（windows py3.8 onedir）；`actions/checkout` 必 `fetch-depth:0`；
9. 前序不变：CLI 退出码 0/1/2；数据目录五分支；registry 16 项；GUI 单一事实源（service 不 import Qt）；
   COM 边界（不新增判定 API）；打包 `exclude_binaries=True` + 内嵌带 `data/README.md`；
   误报 0 优先；bench 报告 `sort_keys` + 无时间戳 + 两次位级一致；全程 3.8 兼容写法。

## 本机环境坑（M7 新增，只记实测过的）

- **git push 到 github.com 间歇性失败**（`Failed to connect ... port 443` / `Connection was reset`）：
  `gh api` / `curl https://github.com` 同时可用 → 属网络毛刺，非配置问题。处置＝**重试循环**
  （失败后 sleep 15s 再试，用 `git ls-remote --heads origin main | grep <sha>` 判真成功，
  别信 `git push` 的退出码——偶发"已推送但报错"）；
- **首跑 CI 才暴露的潜伏缺陷**（本机 Windows 开发环境全跑不出来，务必记住这条）：
  ①docx `create_system` 跨平台位级一致；②构建工具 cp1252 stdout；③dist 禁区规则误伤依赖缓存。
  **教训：本机全绿 ≠ CI 绿**；改动构建/落盘/编码相关代码后，优先看 CI；
- **`git archive` 干净树无 `.git`**：干净环境验证用它时，脱敏扫描器的 `run_tracked` 走文件系统兜底
  （按 `pyvenv.cfg` 剪 venv——在导出树里就地建 venv 会带进第三方 site-packages 的邮箱，成片误报）；
- M6 装依赖：`PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev,docx,viz,gui,com,pkg]" -i https://pypi.tuna.tsinghua.edu.cn/simple`。

## M7 DoD（收尾逐项打勾，已回写 plan/00/05）

- [x] 脱敏四步 + 提交元数据邮箱改写（四扫硬门 0 命中）；
- [x] 产物本体扫描（红线 + dist 脱敏，0 命中）；
- [x] 干净环境验证（`git archive` + 独立 venv，README 逐条退出码 0，**收集数对账 362**）；
- [x] CI 五 job 全绿（含首跑暴露三处潜伏缺陷的修复）；
- [x] 公开仓库建仓 + push（`yuluo554/thesis-audit-workbench`）；
- [x] 362 项双解释器绿 + 三基线复跑不回退；
- [x] 扩展项 P2 六项清零决策入 plan/00；
- [x] plan/00/05 回写；**HANDOFF-M8 落盘**；registry 16 项不变；
- [x] **GitHub Release + tag**（`v0.1.0`，经用户确认后执行，附 dist zip）。

## 关键命令速查

```bash
# 全量测试（开发仓）
cd code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 362 收集（本机 3.8: 361 通过/1 跳过）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 362 收集（3.12: 357 通过/5 跳过）

# 脱敏发布门（仓库根）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 code/tools/desensitize_audit.py --selftest
PYTHONDONTWRITEBYTECODE=1 py -X utf8 code/tools/desensitize_audit.py --mode all     # 跟踪树+历史+元数据
PYTHONDONTWRITEBYTECODE=1 py -X utf8 code/tools/desensitize_audit.py --mode dist    # 产物本体

# 构建 + 两条构建红线
PYTHONDONTWRITEBYTECODE=1 py -m PyInstaller code/tools/taw.spec --noconfirm --clean \
    --distpath dist --workpath build
PYTHONDONTWRITEBYTECODE=1 py -X utf8 code/tools/check_build_redline.py dist/taw
PYTHONDONTWRITEBYTECODE=1 py -X utf8 code/tools/verify_neutral_dir.py dist --data-src data

# 三基线复跑（收尾纪律）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -c "
import sys; sys.path.insert(0,'src')
from taw import f1bench, refbench, fullbench
r1 = f1bench.run('../data', detailed=True); f1bench.write_report(r1, '../reports/m2_parse_f1.json')
r2 = refbench.run('../data'); refbench.write_report(r2, '../reports/m3_refbench.json')
r3 = fullbench.run('../data'); fullbench.write_report(r3, '../reports/m4_fullbench.json')
print('M2 F1:', r1['gate']); print('M3 9指标:', r2['gate']['all_pass']); print('M4 5指标:', r3['gate']['all_pass'])"
```

```bash
# Release 产物打包（待用户确认后执行；仓库根）
cd dist
py -c "import shutil; shutil.make_archive(r'<输出目录>/thesis-audit-workbench-v0.1.0-win64', 'zip', '.', 'taw')"
# 建 tag + Release（示例；tag 名与 pyproject version 一致）
git tag -a v0.1.0 -m "v0.1.0 毕业论文全流程审计工作台（CLI + PySide6 桌面 + 免安装 exe）"
git push origin v0.1.0
gh release create v0.1.0 <zip路径> -R yuluo554/thesis-audit-workbench \
    --title "v0.1.0 毕业论文全流程审计工作台（桌面版 + CLI）" --notes-file <说明文件>
```

```bash
# CI 状态（gh 可用）
gh run list -R yuluo554/thesis-audit-workbench --limit 3
gh run view <run-id> -R yuluo554/thesis-audit-workbench
```