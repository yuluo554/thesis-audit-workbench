# HANDOFF-M7：脱敏发布（M6 收尾交接快照，2026-10-13）

> 续接方式：新对话输入 `/goal 读取 "<项目绝对路径>\plan\HANDOFF-M7.md" 继续完成任务`（绝对路径由用户侧拼接；**本文件内一律相对路径**，防发布期脱敏命中）。
> 项目：毕业论文全流程审计工作台。先读 [00-README总览](00-README总览.md) → [05-数据计划与里程碑](05-数据计划与里程碑.md)（M7 行）→ [03-架构与技术选型](03-架构与技术选型.md)（§五横切纪律）→ [04-模块详设](04-模块详设.md)（§九=M2、§十=M3、§十一=M4、§十二=M5、**§十三=M6 桌面交付**）→ 本文。

## 当前进度（M6 末态）

**M6 桌面交付全部达成**（16 项 registry 不变——M6 是交付层，不改模块注册表）：

| 交付面 | 实测结果 |
|---|---|
| PySide6 GUI | `taw.gui.service`（纯 Python，**不 import Qt**）+ `taw.gui.app`（窗口）；**只消费引擎 API**，与 CLI 逐字段 JSON 一致；offscreen 测试 15+8 项双解释器绿 |
| GUI 入口 | `taw gui`（子命令，含 `--check` 离屏自检）/ `taw-gui`（console_script）/ `python -m taw.gui` |
| Word/WPS COM 实机 | 本机 **Word 16.0 + WPS 12.1.0.28505 并存**；注入 6 条批注 → Word 读回 `Comments.Count=6`（条数一致）；WPS 同一 `inspect_document` 接口可用 |
| 一键插入 | `com.one_click_insert` = REF-07 重排内核 + `renumber.verify_plan` 独立复核（插入正确性可在无 Office 环境测） |
| PyInstaller onedir | `dist/taw/taw.exe`（8.2MB，console=True）+ `dist/taw/taw-gui.exe`（10.1MB，console=False）共用 COLLECT |
| 构建红线 | dist 禁区成分 **0 命中**（`_private/`、`.db`/`.env`/`.key`、真实实体关键词）；内嵌数据与仓库 `data/` **逐文件 SHA-256 一致** |
| 中立目录五连 | 仓库树外 + `PATH=""`；`selfcheck`/`demo`/`parse`/`audit refs`/`audit bench --line all` **五条退出码全 0**，数据来源 `pyinstaller-embedded` |
| 测试规模 | **361 项收集**；3.8: 360 通过/1 跳过；3.12: 356 通过/5 跳过 |
| 三基线复跑 | M2 F1 all_pass + M3 9 指标 all_pass + M4 5 指标 all_pass，**无回退**（`reports/m6_delivery_trace.txt`） |
| CLI 编码纪律 | cp1252 stdout 不再 `UnicodeEncodeError`（`_ensure_utf8_stdout` + 子进程测试钉死） |

- 远端**仍未建仓**：D-1 仓库名 `thesis-audit-workbench` / D-2 署名 `yuluo554` 已拍板；建仓/push 在 M7 脱敏后做，**勿提前 push**。
- 扩展项（arXiv 见刊提示 / 文献 CI watch / 规则包导入导出 / 个人错误画像 / LLM 兜底 / 语义 rerank）**未收口 → M7 清零决策**（plan/00 决策表已登记）。

## M7 待办（脱敏发布：四步脱敏 + 产物扫描 + 干净环境验证 + CI 绿 + Release）

M7 目标（plan/05 M7 行）：**脱敏四步 + 产物扫描 + 干净环境验证 + CI 绿 + GitHub Release + 收尾固化**；
DoD：终验三扫全 0；干净 clone 按 README 逐条跑通（**收集数对账**）；release+tag **经用户确认**。

1. **脱敏四步**（plan/03 §五第 10 条）：
   - ①**源码扫描**：真实人名/机构/路径/邮箱（发布前 `git log` 提交元数据邮箱检查）；
   - ②**数据扫描**：`data/` 全量（合成数据应已脱敏，但**逐条复核**；`_private/` 必须确认未被 `git add`——`.gitignore` 已覆盖，但要 `git status --ignored` 实证）；
   - ③**文档扫描**：plan/、README、HANDOFF 系列（**用法行一律相对路径**的纪律就是为此，逐份复核无绝对路径泄漏）；
   - ④**产物扫描**：exe / dist / reports（reports 已在 .gitignore，确认无意外入仓）。
2. **构建产物本体扫描**：`python code/tools/check_build_redline.py <dist>/taw`（已就位）——发布前在**最终构建**上再跑一次。
3. **干净环境验证**：新目录 `git clone`（或 `git archive` 导出的干净树）+ 按 README 逐条跑：
   - `python -m pip install -e "./code[dev,docx,viz]"` → `python -m pytest tests -q`
   - **收集数对账**：干净环境收集数必须 = 361（防"双绿但悄悄少跑"；本机 skip 数因 extras 而变，收集数不变）
   - CLI 速查命令逐条跑通（本文件末尾）
4. **CI 绿**：`.github/workflows/ci.yml` 现有 **test 四矩阵**（ubuntu/windows × 3.8/3.12）+ **package job**（windows py3.8：onedir 构建 + 红线 + 中立目录五连）——首次 push 后盯四矩阵 + package 全绿。
5. **GitHub Release + tag**：产物 = dist 双 exe（onedir 打包为 zip）+ 说明；**tag/release 动作必须经用户确认**（对外发布不可逆）。
6. **收尾固化**：plan/00 状态表 + 决策表 + plan/05 M7 行回写；**扩展项 P2 清零决策**（逐个给"做/不做 + 理由"，写入决策表）；`reports/m6_delivery_trace.txt` 与 M7 留痕（运行产物不入仓）。

## 既定口径清单（动了会打挂测试/基准，先对照再动手）

> M6 新增口径见 **04 §十三**；前序口径与 HANDOFF-M6 一致，此处只列 M6 增量与最易踩的几条。

1. CLI 退出码 0=完成 / 1=降级 / 2=用法错误；无子命令=帮助+0（`test_cli` 锁定）；`taw gui`：0=正常/离屏自检通过、**1=gui extras 缺装降级**；
2. 数据目录五分支顺序：explicit > `TAW_DATA_DIR` > `sys._MEIPASS/data` > exe`/_internal/data` > CWD 上溯（`test_paths` 锁定）；**改优先级 = 口径变更**；
3. registry 16 项、ref 9 / full 6 / bench 1，**全 done**（`test_registry::test_m5_all_modules_done` 锁定；M6 未新增模块）；
4. **GUI 单一事实源**（04 §十三 13.1）：`taw.gui.service` **禁止 import Qt**（禁止复刻判定逻辑）；GUI 产出的任何 HTML 必须过 `reftopo.assert_no_external_refs`；
5. **离屏纪律**（04 §十三 13.1）：`tests/conftest.py` 收集前置 `QT_QPA_PLATFORM=offscreen`；GUI 测试模块**模块级 skip**（**不用 `importorskip`**，pytest 9.1 起会变错误）；
6. **COM 边界**（04 §十三 13.2）：COM 层**不得新增任何判定或改写 API**（伦理守卫 `aigccheck.assert_no_rewrite_surface` 继续生效）；收集期只查注册表不 Dispatch；会话释放顺序固定（丢 Document+gc → Quit → 丢 app → CoFreeUnusedLibraries → CoUninitialize）；
7. **打包口径**（04 §十三 13.3）：EXE 必须 `exclude_binaries=True`（否则伪 onefile）；内嵌数据必须带 `data/README.md`（paths 数据根标志）；`DATA_DIRS` 白名单不含 `_private`；
8. **红线黑名单只钉真实实体**（04 §十三 13.3）：合成数据的"虚构理工大学/李虚构"**不得**进黑名单（否则打包必失败）；
9. 全程 3.8 兼容写法（禁 `X|Y` union 注解、match、3.9+ stdlib、`ast.unparse`）；
10. `data/frozen/` + `data/bench/` 禁手改；docx 落盘必须走 `docxutil` 收口（固定时间戳）；**CLI 与 GUI 与 COM 三条通路一律同一收口**；
11. 条款 `status`(pending) 与 `activation`(active) 正交；findings 一律带 `clause_status`+`basis`；**pending 在 GUI 也须渲染「条款待核对」**；
12. **误报 0 优先**判定纪律不变；指标 2 的 55 处 FN **全部归因**（UNKNOWN=0，新 FN 即回归）；
13. M5 不变量：bench 报告 `sort_keys` + 无时间戳 + **两次位级一致**（`test_bench_full` 锁定）。

## 本机环境坑（M6 新增，只记实测过的）

- **段错误随机崩溃**：`py -m pytest` 偶发段错误/零输出（同命令重跑即过）——处置＝清 `__pycache__` 后**原样重跑**；见 crash-loop-rescue skill；
- **WPS COM 收尾 RPC 异常**（`0x800706be/0x800706ba`）：非本层缺陷，是 WPS 自动化侧的启停毛刺。已按 §十三 13.2 两条处置（收集期查注册表 + 释放顺序），残余提示不影响退出码（实测 EXIT=0）；
- **pywin32 只在 3.8 装了**：3.12 未装 → COM 实机组在 3.12 上 skip 5 项（**这是设计行为**，不是少跑）；
- **pyvis 只在 3.8 装了**：3.12 走内置降级渲染器（测试已覆盖该路径）；
- **PyInstaller 版本**：3.8 → 5.13.2（锁 `<6`）；3.12 → 6.22.3（评测可跑，但**发布产物用 3.8 构建**）；
- **onedir 首版踩坑**：忘写 `exclude_binaries=True` → 产物 57MB 伪 onefile（解到 `_MEIxxxx`）；
- **cp1252 stdout 崩溃**：已修（`_ensure_utf8_stdout`）；控制台看中文仍建议 `py -X utf8`；
- 系统代理 127.0.0.1:7897 实测失效；外网直连可用（api.crossref.org / doi.org / std.samr.gov.cn ✅；iso.org 403 ✗；raw.githubusercontent.com 000 ✗）；
- **pip install 也是 python 调用**，须带 `PYTHONDONTWRITEBYTECODE=1`；
- M6 装依赖：`PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -m pip install -e "./code[dev,docx,viz,gui,com,pkg]" -i https://pypi.tuna.tsinghua.edu.cn/simple`。

## M6 DoD（收尾逐项打勾，已回写 plan/00/04/05）— ✅ 全部达成 2026-10-13

- [x] PySide6 GUI 只消费引擎 API（`taw.gui.service` 纯 Python 不 import Qt；与直接调引擎逐字段一致）；
- [x] GUI offscreen 测试批绿（`test_gui_service` 15 + `test_gui_app` 8，双解释器）；
- [x] Word/WPS COM 实机验证（批注读回条数一致、WPS 兼容接口一致、一键插入走内核 + 独立复核）；
- [x] PyInstaller onedir **双 exe**（CLI console=True + GUI console=False，共用 COLLECT）；
- [x] 构建红线断言（dist 禁区 0 命中 + 内嵌数据逐文件对账）；
- [x] 中立目录干净验证**五连**（仓库树外 + 剥离 PATH，逐条真实退出码）；
- [x] 全量 pytest 双解释器绿（**361 项收集**）+ 三基线复跑不回退；
- [x] plan/00/04/05 回写；**HANDOFF-M7 落盘**；registry 16 项不变。

## 关键命令速查

```bash
cd <repo>/code
PYTHONDONTWRITEBYTECODE=1 py -m pytest tests -q          # 全量（3.8，360 通过 / 1 跳过）
PYTHONDONTWRITEBYTECODE=1 py -3.12 -m pytest tests -q    # 全量（3.12，356 通过 / 5 跳过）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw selfcheck
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw demo
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw audit bench --line all --report ../reports/bench_all.json

# M6 GUI（离屏自检不进事件循环；无参则启动窗口）
QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw gui --check
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m taw gui

# M6 打包（仓库根跑）：构建 → 红线 → 中立目录五连
PYTHONDONTWRITEBYTECODE=1 py -m PyInstaller code/tools/taw.spec --noconfirm --clean \
    --distpath dist --workpath build
PYTHONDONTWRITEBYTECODE=1 py -X utf8 code/tools/check_build_redline.py dist/taw
PYTHONDONTWRITEBYTECODE=1 py -X utf8 code/tools/verify_neutral_dir.py dist --data-src data
```

```bash
# 三基线复跑（收尾纪律：任何不动工作树的操作后也要复跑；M6 留痕见 reports/m6_delivery_trace.txt）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -c "
import sys; sys.path.insert(0,'src')
from taw import f1bench, refbench, fullbench
r1 = f1bench.run('../data', detailed=True); f1bench.write_report(r1, '../reports/m2_parse_f1.json')
r2 = refbench.run('../data'); refbench.write_report(r2, '../reports/m3_refbench.json')
r3 = fullbench.run('../data'); fullbench.write_report(r3, '../reports/m4_fullbench.json')
print('M2 F1:', r1['gate']); print('M3 9指标:', r2['gate']['all_pass']); print('M4 5指标:', r3['gate']['all_pass'])"
```

```bash
# 双入口 / 双 exe 契约
PYTHONDONTWRITEBYTECODE=1 py -c "import sysconfig,os,subprocess,sys; d=sysconfig.get_path('scripts'); \
  exe=os.path.join(d,'taw.exe' if os.name=='nt' else 'taw'); \
  print(subprocess.run([exe,'--version'],capture_output=True,text=True).stdout)"
```
