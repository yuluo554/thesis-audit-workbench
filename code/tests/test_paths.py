"""数据目录五分支冻结顺序测试（plan/03 §五第 8 条口径，改动须记决策）。"""

import sys
from pathlib import Path

import pytest

from taw import paths

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_DATA = REPO_ROOT / "data"


def _make_data_dir(base):
    data = base / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / paths.MARKER_NAME).write_text("data root\n", encoding="utf-8")
    return data


def test_repo_data_dir_present():
    assert (REPO_DATA / paths.MARKER_NAME).is_file()


def test_explicit_branch_and_wins_over_env(monkeypatch, tmp_path):
    a = _make_data_dir(tmp_path / "a")
    b = _make_data_dir(tmp_path / "b")
    monkeypatch.setenv(paths.ENV_VAR, str(b))
    found, source = paths.find_data_dir_details(str(a))
    assert found == a
    assert source == "explicit"


def test_env_branch(monkeypatch, tmp_path):
    fake = _make_data_dir(tmp_path)
    monkeypatch.setenv(paths.ENV_VAR, str(fake))
    found, source = paths.find_data_dir_details()
    assert found == fake
    assert source == "env"


def test_env_invalid_is_loud(monkeypatch, tmp_path):
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path / "nope"))
    with pytest.raises(FileNotFoundError):
        paths.find_data_dir_details()


def test_explicit_invalid_is_loud(tmp_path):
    with pytest.raises(FileNotFoundError):
        paths.find_data_dir_details(tmp_path / "nope")


def test_pyinstaller_embedded_branch(monkeypatch, tmp_path):
    emb = _make_data_dir(tmp_path / "meipass")
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)
    monkeypatch.chdir(tmp_path / "meipass")  # 即使 CWD 上溯无果，分支序也保证 MEIPASS 先中
    found, source = paths.find_data_dir_details()
    assert found == emb
    assert source == "pyinstaller-embedded"


def test_pyinstaller_sidecar_branch(monkeypatch, tmp_path):
    sidecar = _make_data_dir(tmp_path / "app" / "_internal")
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "taw.exe"))
    monkeypatch.chdir(tmp_path)
    found, source = paths.find_data_dir_details()
    assert found == sidecar
    assert source == "pyinstaller-sidecar"


def test_cwd_walk_finds_repo_data(monkeypatch):
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.chdir(REPO_ROOT / "code")  # code/ 下无 data/，上溯命中仓库根
    found, source = paths.find_data_dir_details()
    assert found == REPO_DATA
    assert source == "cwd-walk"


def test_not_found_is_none_not_raise(monkeypatch, tmp_path):
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    monkeypatch.delenv(paths.ENV_VAR, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(isolated / "python.exe"))
    monkeypatch.chdir(isolated)
    found, source = paths.find_data_dir_details()
    assert found is None
    assert source == "not-found"
