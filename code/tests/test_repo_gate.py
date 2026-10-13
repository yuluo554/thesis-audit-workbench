"""仓库卫生守门（plan/03 §五横切纪律的前置约定，"动了会打挂后续里程碑"）。

- 换行纪律：.gitattributes 强制 LF（对抗本机 autocrlf=true，字节冻结 fixtures 的前置）；
- workflow YAML 合法性：非法 YAML 在 GitHub 端表现为"jobs=0 静默不建 job"（系列实录），
  本地 PyYAML 解析是唯一便宜的真验；
- 依赖声明：dev extras 必须覆盖测试期 import，防"双绿但悄悄少跑"。
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_gitattributes_forces_lf():
    text = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "eol=lf" in text


def test_gitignore_covers_env_and_private():
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in text
    assert "*_private/" in text


def test_ci_workflow_and_publish_gate():
    """CI workflow 合法性 + M7 发布门接线与审计器自检（合并为一测，收集总数不变）。

    - workflow 非法 YAML 在 GitHub 端表现为"jobs=0 静默不建 job"，本地解析是唯一便宜真验；
    - 发布纪律（plan/03 §五第 10 条）：CI 必须真跑脱敏审计，否则脱敏退化成
      "本机人工跑过一次"；另须 `fetch-depth: 0`（浅克隆会让历史扫描静默空跑 = 假绿）；
    - 审计器本体（`code/tools/desensitize_audit.py`）**自检 + 跟踪树硬门**：
      `--selftest` 用程序化合成夹具做阳性/阴性对照（不读仓库、不落真实敏感值）；
      `run_tracked()` 对本跟踪树跑一遍硬门——测试自身也在被扫范围内，
      即扫描器不会误伤正常源码。全历史/提交元数据/dist 三面由 CI `--mode all|dist` 真跑。
    """
    import importlib.util
    import io

    wf_dir = REPO_ROOT / ".github" / "workflows"
    files = sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml"))
    assert files, "CI workflow 缺失"
    for wf in files:
        data = yaml.safe_load(wf.read_text(encoding="utf-8"))
        assert isinstance(data, dict), "{} 顶层不是映射".format(wf.name)
        jobs = data.get("jobs") or {}
        assert jobs, "{} 无 job（YAML 非法时 GitHub 端就是这个症状）".format(wf.name)
        for job_name, job in jobs.items():
            assert job.get("runs-on"), "{}#{} 缺 runs-on".format(wf.name, job_name)
            assert job.get("steps"), "{}#{} 缺 steps".format(wf.name, job_name)

    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "desensitize_audit.py --mode all" in workflow, \
        "CI 未跑 --mode all（跟踪树/全历史/提交元数据）"
    assert "desensitize_audit.py --mode dist" in workflow, \
        "CI 未跑 --mode dist（构建产物本体）"
    assert re.search(r"fetch-depth:\s*0\b", workflow), \
        "actions/checkout 未配 fetch-depth: 0（历史脱敏扫描会静默空跑）"

    spec = importlib.util.spec_from_file_location(
        "desensitize_audit", REPO_ROOT / "code" / "tools" / "desensitize_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    stream = io.StringIO()
    assert module.selftest(stream) == 0, stream.getvalue()
    assert "selftest][OK]" in stream.getvalue()

    fatal = module.hard_hits([("tracked", hit) for hit in module.run_tracked()])
    assert not fatal, "跟踪树存在硬门命中：%s" % [str(h) for _, h in fatal]


def test_pyproject_contract():
    text = (REPO_ROOT / "code" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'requires-python = ">=3.8"' in text
    dev = re.search(r"^dev\s*=\s*\[(.*?)\]", text, re.S | re.M)
    assert dev, "dev extras 缺失"
    for pkg in ("pytest", "pyyaml"):
        assert pkg in dev.group(1), "dev extras 缺测试期依赖: {}".format(pkg)


def test_readme_states_both_lines():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "文献审计线" in text and "全文审计线" in text
