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


def test_workflows_parse_and_have_jobs():
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
