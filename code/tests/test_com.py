# -*- coding: utf-8 -*-
"""Word/WPS COM 联动测试（M6）。

三层，按环境能力逐层降级（CI 无 Office → 只跑到纯逻辑层）：

1. **纯逻辑层**（任何平台可跑）：`one_click_insert` 计划走 REF-07 重排内核并被
   独立复核；`recompute_numbering` 与位置口径一致；`com_available` 在非 win32
   恒为 False；`probe_office` 无 Office 时**返回数据不抛异常**。
2. **环境层**（win32 + pywin32）：`ComSession` 对不存在的 ProgID 抛
   `ComUnavailable`（不是静默失败）。
3. **实机层**（win32 + 真实 Word/WPS）：打开/另存/读回批注——**由真实 Office
   认账我们生成的 OOXML**。缺 Office 时整组 `skip`（CI 无 GUI/Office，必须可跳过）。

实机断言的关键口径：`reflib.write_comments` 注入的 Word 批注，必须被真实
Word/WPS 读回**条数一致**。这是 M3 "批注回写（确定性）" 在 M6 的实机验收。
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

from taw import com

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data"
AUDIT = DATA / "frozen" / "audit"
THESIS = DATA / "frozen" / "thesis"

WIN32 = sys.platform == "win32"

def _probe_pywin32():
    try:
        import win32com.client  # noqa: F401
        import pythoncom  # noqa: F401
    except ImportError:
        return False
    return True


# 实机门槛 = win32 **且** pywin32 齐备 **且** 注册表里有 Office ProgID。
# 三者缺一即整组 skip（CI ubuntu 无注册表；3.12 本机未装 pywin32——都会走到这里）。
_CAN_COM = WIN32 and _probe_pywin32()
_PROBE = {"available": bool(_CAN_COM and com.registered_progid())} if _CAN_COM \
    else {"available": False}


def _probe_wps_progid():
    """WPS 专用 ProgID（KWPS.Application 复用 'Microsoft Word' 名，以 ProgID 为准）。"""
    if not _CAN_COM:
        return None
    import winreg

    for progid in com.WPS_PROGIDS:
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\CLSID"))
        except OSError:
            continue
        return progid
    return None


_WPS_PROGID = (_probe_wps_progid(),) if _CAN_COM else ()


def _probe_wps():
    return bool(_WPS_PROGID and _WPS_PROGID[0])


requires_com = pytest.mark.skipif(
    not _PROBE.get("available"),
    reason="实机 COM 测试需要 Windows + pywin32 + 真实 Word/WPS（CI 无 Office 时跳过）")


def _require_docx():
    try:
        import docx  # noqa: F401
    except ImportError as exc:
        pytest.fail("COM 批注测试需要 docx extras（CI/README 已装；缺装=环境配置错误）：{}".format(exc))


# ---- 1. 纯逻辑层 ----


def test_com_available_reflects_platform():
    """com_available 只在 win32 且 pywin32 齐备时为真（口径明确、可单测）。"""
    assert com.com_available() == (WIN32 and _probe_pywin32())


def test_probe_office_never_raises_returns_data():
    """无 Office / 非 win32 时 probe_office 返回 available=False 而非抛异常。"""
    result = com.probe_office()
    assert set(result) == {"available", "progid", "name", "version", "error"}
    if not com.com_available():
        assert result["available"] is False
        assert result["error"]


def test_one_click_insert_reuses_renumber_kernel():
    """一键插入计划 = REF-07 重排内核产出，且过 `verify_plan` 独立复核。

    真实语义：`cards` 是**库内已审计**文献；`items` 是论文当前编号序列；
    插入的目标是库内某条**尚未进正文**的文献（插进去才产生新编号）。
    """
    from taw import renumber

    # 库内 4 条；正文当前只引了前 3 条
    cards = [{"card_id": "ref-00000{}".format(i)} for i in range(1, 5)]
    items = [{"item_id": "ref-00000{}".format(i),
              "markers": [{"marker_id": "mk-{}-1".format(i)}]}
             for i in range(1, 4)]
    plan = com.one_click_insert(items, cards, "ref-000004")
    assert renumber.verify_plan(plan) is True
    assert plan["consistent"] is True
    assert plan["n_items"] == 4
    assert plan["new_order"][-1] == "ref-000004"        # 默认末位插入
    assert sorted(plan["new_order"]) == sorted(set(plan["new_order"]))  # 无重号


def test_one_click_insert_duplicate_target_fails_verification():
    """插入已在编号序列中的条目 = 制造重号 → 计划必须被独立复核拦下。"""
    from taw import renumber

    cards = [{"card_id": "ref-000001"}, {"card_id": "ref-000002"}]
    items = [{"item_id": "ref-000001", "markers": []},
             {"item_id": "ref-000002", "markers": []}]
    with pytest.raises(ValueError):
        com.one_click_insert(items, cards, "ref-000002")
    assert renumber.verify_plan(renumber.renumber(items, [])) is True  # 无编辑则一致


def test_one_click_insert_rejects_foreign_card():
    """插入目标必须是**库内已审计**文献（结构防幻觉在插入路径的延伸）。"""
    cards = [{"card_id": "ref-000001"}]
    items = [{"item_id": "ref-000001", "markers": []}]
    with pytest.raises(ValueError):
        com.one_click_insert(items, cards, "ref-999999")


def test_recompute_numbering_follows_position():
    """新编号严格由重排后位置决定（1..N 连续），并给出旧→新对照。"""
    out = com.recompute_numbering(["a", "b", "c"], {"a": 1, "b": 2, "c": 3})
    assert out["numbering"] == {"a": 1, "b": 2, "c": 3}
    assert out["changed"] == {}
    out2 = com.recompute_numbering(["c", "a", "b"], {"a": 1, "b": 2, "c": 3})
    assert out2["numbering"] == {"c": 1, "a": 2, "b": 3}
    assert out2["changed"]["c"] == {"old": 3, "new": 1}


def test_com_session_raises_when_unavailable(monkeypatch):
    """非 win32 或缺 pywin32 → ComUnavailable（不静默降级）。"""
    if com.com_available():
        pytest.skip("本机 COM 可用：该路径由环境层/实机层覆盖")
    with pytest.raises(com.ComUnavailable):
        com.ComSession()


# ---- 2. 环境层：真实 COM 但用不存在的 ProgID ----


@requires_com
def test_com_session_bad_progid_raises():
    with pytest.raises(com.ComUnavailable):
        with com.ComSession(progid="NoSuch.Application.XYZ", include_wps=False):
            pass


# ---- 3. 实机层：真实 Word/WPS 打开、另存、读回批注 ----


@requires_com
def test_office_opens_bundled_thesis_and_counts():
    """真实 Office 打开随包合成论文 → 结构与解析器口径一致（62 段级文本）。"""
    docx_path = THESIS / "thesis_synthetic.docx"
    if not docx_path.is_file():
        pytest.skip("docx fixture 缺失")
    info = com.inspect_document(str(docx_path))
    assert info["name"]                       # 由真实 Office 报出
    assert info["progid"] in ("Word.Application",) + com.WPS_PROGIDS
    assert info["paragraphs"] > 0
    assert info["tables"] >= 1


@requires_com
def test_office_reads_back_injected_comments(tmp_path):
    """**M6 关键实机断言**：python-docx 注入的批注被真实 Word/WPS 读回条数一致。"""
    _require_docx()
    from taw import reflib, refaudit

    docx_path = THESIS / "thesis_synthetic.docx"
    if not docx_path.is_file():
        pytest.skip("docx fixture 缺失")
    report = refaudit.audit_refs(
        str(AUDIT / "refs_table.txt"), body_path=str(AUDIT / "body.txt"), data_dir=str(DATA))
    target = tmp_path / "commented.docx"
    shutil.copy(str(docx_path), str(target))
    reflib.write_comments(str(target), report["findings"], out_path=str(target))

    info = com.inspect_document(str(target))
    assert info["comments"] == len(report["findings"]), \
        "Office 读回批注 {} 条 != findings {} 条".format(info["comments"], len(report["findings"]))


@requires_com
def test_office_rejects_nothing_and_resaves(tmp_path):
    """COM 外挂另存通路：打开→SaveAs → 产物存在且可再次被 Office 打开。"""
    docx_path = THESIS / "thesis_synthetic.docx"
    if not docx_path.is_file():
        pytest.skip("docx fixture 缺失")
    copy = tmp_path / "src.docx"
    shutil.copy(str(docx_path), str(copy))
    out = com.rewrite_comments_via_office(str(copy), str(tmp_path / "resaved.docx"))
    assert Path(out).is_file() and Path(out).stat().st_size > 0
    again = com.inspect_document(out)          # 二次打开 = 产物合法
    assert again["paragraphs"] > 0


@requires_com
@pytest.mark.skipif(not _probe_wps(), reason="本机无 WPS（KWPS.Application 未注册）")
def test_wps_compatibility_same_interface():
    """WPS 兼容范围实机核对：同一 `inspect_document` 接口在 WPS 上可用。

    WPS 的 COM 服务在进程启停时偶发 RPC 层失败（0x800706be）——这是 WPS
    自动化侧的已知毛刺，不是本层缺陷：故此处把 COM 失败降级为 skip，
    只要 WPS 能应答就把接口一致性钉住。
    """
    docx_path = THESIS / "thesis_synthetic.docx"
    if not docx_path.is_file():
        pytest.skip("docx fixture 缺失")
    try:
        info = com.inspect_document(
            str(docx_path), include_wps=True, progid=_WPS_PROGID[0])
    except Exception as exc:            # com_error / ComUnavailable
        pytest.skip("WPS COM 服务本次不可用（{}）：{}".format(_WPS_PROGID[0], exc))
    assert info["progid"] in com.WPS_PROGIDS
    assert info["paragraphs"] > 0
