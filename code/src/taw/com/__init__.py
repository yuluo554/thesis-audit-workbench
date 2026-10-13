# -*- coding: utf-8 -*-
"""Word/WPS COM 联动层（M6；extras `com`，pywin32，仅 win32）。

**外挂定位**（plan/03 §一）：判定与产物生成的确定性通路在 `taw.docxutil` /
`taw.reflib` / `taw.refrec`（M3 已落地并有基准回归）；本层**只是 COM 触发壳**——
用 Word/WPS 的自动化接口打开文档、调既有通路、保存，不新增任何判定或改写能力。

结构分两半，便于测试：
- `select_application` / `probe_office`：探测可用 Office（纯逻辑，无 COM 也能单测）；
- `ComSession`：真实 COM 驱动（`sys_platform=='win32'` + pywin32 齐备才可构造，
  否则 `ComUnavailable`；CI 无 Office → 测试整体跳过）；
- `one_click_insert`：一键插入的**计划**部分复用 `taw.refrec.insert_reference`
  重排内核（确定性），COM 只负责把重排结果落到文档。

WPS 兼容范围（M6 实机验证）：`KWPS.Application` 是与 Word 同源的 ProgID，
接口面到 `Documents.Open`/`Save`/`Quit` 层级一致；插入/批注等 OOXML 级改动仍走
python-docx 通路，故 WPS 只需保证「能打开与另存」即可完成一体化。
"""

import gc
import os

# 本机实测可用的 ProgID 候选（Word 优先，WPS 兜底）
WORD_PROGIDS = ("Word.Application",)
WPS_PROGIDS = ("KWPS.Application", "WPS.Application", "ET.Application")

# 会话可见性：静默自动化不放窗口（用户可显式要求可见）
def _progids(include_wps=True):
    out = list(WORD_PROGIDS)
    if include_wps:
        out += list(WPS_PROGIDS)
    return tuple(out)


def com_available():
    """当前环境是否能尝试 COM：Windows + pywin32 齐备。"""
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa: F401
        import pythoncom  # noqa: F401
    except ImportError:
        return False
    return True


def registered_progid(include_wps=True):
    """**查注册表**判断哪个 Office ProgID 已注册（不启动任何进程）。

    与 `probe_office` 的分工：注册表查询廉价且无副作用，适合"是否有 Office"
    的筛选（测试收集期）；`probe_office` 真正 Dispatch 一次，确认服务可起来。
    本机实测 WPS 的 COM 服务在自动化启停时会偶发 RPC 失败（0x800706be），
    故筛选阶段一律走注册表，避免无谓的进程启停。
    """
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    for progid in _progids(include_wps):
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\CLSID")
        except OSError:
            continue
        winreg.CloseKey(key)
        return progid
    return None


class ComUnavailable(RuntimeError):
    """COM 不可用（非 Windows / 缺 pywin32 / 未装 Office）。"""


def probe_office(include_wps=True):
    """探测哪个 Office 可用 → {available, progid, name, version, error}。

    **不抛异常**：无 Office 时返回 available=False（CI/无 Office 机器上，
    调用方据此降级），把"能不能用"变成数据而不是异常。
    """
    if not com_available():
        return {"available": False, "progid": None, "name": None, "version": None,
                "error": "COM 环境不可用（需 win32 + pywin32）"}
    import win32com.client as wc

    last_error = None
    for progid in _progids(include_wps):
        try:
            app = wc.DispatchEx(progid)
            name = str(app.Name)
            version = str(app.Version)
            try:
                app.Quit()
            except Exception:
                pass
            del app
            return {"available": True, "progid": progid, "name": name,
                    "version": version, "error": None}
        except Exception as exc:  # com_error / 类未注册
            last_error = "{}: {}".format(progid, exc)
    return {"available": False, "progid": None, "name": None, "version": None,
            "error": last_error}


class ComSession:
    """Word/WPS 自动化会话（上下文管理器）。

    ```python
    with ComSession() as session:
        session.open(path)
        session.save(path)
    ```
    退出时必定释放文档引用并 Quit（静默），异常路径不泄漏 COM 进程。
    """

    def __init__(self, progid=None, visible=False, include_wps=True):
        if not com_available():
            raise ComUnavailable("COM 环境不可用（需 win32 + pywin32）")
        self.progid = progid
        self.visible = visible
        self._include_wps = include_wps
        self._app = None
        self._docs = []
        self.probe = None

    def __enter__(self):
        import pythoncom
        import win32com.client as wc

        # COM 公寓初始化：缺这一步时，自动化对象在释放/Quit 阶段会抛
        # RPC 层异常（0x800706be/0x800706ba），Python 侧虽可捕获但会污染日志。
        self._need_uninit = False
        try:
            pythoncom.CoInitialize()
            self._need_uninit = True
        except Exception:
            pass

        candidates = (self.progid,) if self.progid else _progids(self._include_wps)
        last_error = None
        for progid in candidates:
            try:
                self._app = wc.DispatchEx(progid)
                self.progid = progid
                self.probe = {"progid": progid, "name": str(self._app.Name),
                              "version": str(self._app.Version)}
                break
            except Exception as exc:
                last_error = exc
        if self._app is None:
            self._uninitialize()
            raise ComUnavailable("无可用 Office COM 服务：{}".format(last_error))
        try:
            self._app.Visible = bool(self.visible)
            self._app.DisplayAlerts = 0
        except Exception:
            pass
        return self

    def open(self, path, read_only=False):
        """打开文档 → 返回 COM Document 对象（同时记账以便退出时释放）。"""
        doc = self._app.Documents.Open(str(path), ReadOnly=bool(read_only))
        self._docs.append(doc)
        return doc

    def save(self, path):
        """另存为 docx（格式码 16 = wdFormatDocumentDefault）。"""
        doc = self._docs[-1]
        doc.SaveAs2(str(path), FileFormat=16)
        return str(path)

    def close_all(self, save=False):
        for doc in list(self._docs):
            try:
                doc.Close(SaveChanges=1 if save else 0)
            except Exception:
                pass
        self._docs = []

    def __exit__(self, *exc):
        self.close_all()
        if self._app is not None:
            # 释放顺序实测定论（WPS）：先丢弃 Document 引用并 gc，再 Quit，
            # 再丢弃 app 引用，最后 CoFreeUnusedLibraries + CoUninitialize。
            # 任一步缺失都会让 WPS 的 COM 服务在收尾抛 RPC 异常
            # （0x800706be/0x800706ba）——Word 不在意，WPS 会。
            self._docs = []
            gc.collect()
            try:
                self._app.Quit()
            except Exception:
                pass
            self._app = None
            gc.collect()
            try:
                import pythoncom
                pythoncom.CoFreeUnusedLibraries()
            except Exception:
                pass
        self._uninitialize()
        return False

    def _uninitialize(self):
        if getattr(self, "_need_uninit", False):
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
            self._need_uninit = False


def one_click_insert(items, cards, new_card_id, before=False):
    """一键插入的**计划**：复用 REF-07 重排内核 → RenumberPlan（确定性）。

    与 COM 无关——计划先算好并通过 `renumber.verify_plan` 独立复核；
    COM 只负责把计划落到文档（`apply_markers`）。这样"插入正确性"可在
    无 Office 的环境里被基准回归（plan/04 §五一致性定义）。
    """
    from taw import refrec, renumber

    plan = refrec.insert_reference(items, cards, new_card_id, before=before)
    if not renumber.verify_plan(plan):
        raise ValueError("一键插入计划未通过独立复核（一致性校验失败）")
    return plan


def recompute_numbering(new_order, old_mapping):
    """由重排后的 item 序重算编号 → {item_id: 新编号}（1..N 连续）。

    `old_mapping` 为旧编号映射（{item_id: 旧号}），仅用于生成"旧→新"对照，
    不参与新编号计算——新编号严格由位置决定，与内核同口径。
    """
    new_map = {item_id: i + 1 for i, item_id in enumerate(new_order)}
    diff = {k: {"old": old_mapping.get(k), "new": v}
            for k, v in new_map.items() if old_mapping.get(k) != v}
    return {"numbering": new_map, "changed": diff, "n_items": len(new_order)}


# ---- 文档检视 / OOXML 产物实机验收（COM 的真实价值：让 Word/WPS 认账）----


def inspect_document(path, progid=None, include_wps=True):
    """用 Word/WPS 打开文档并回报结构计数 → dict。

    这是 COM 层最有价值的动作：**由真实 Office 认账我们生成的 OOXML**。
    `taw.docxutil` 手工注入的 `comments.xml` 是否合法、字段/题注是否可解析，
    只有在 Word/WPS 里打开并读到 `Comments.Count` / `Paragraphs.Count` 才算数。

    返回 {progid, name, version, paragraphs, comments, tables, inline_shapes,
    fields}；会话异常照常抛出（交由调用方处理）。
    """
    with ComSession(progid=progid, visible=False, include_wps=include_wps) as session:
        doc = session.open(path)
        info = {
            "progid": session.progid,
            "name": session.probe["name"],
            "version": session.probe["version"],
            "paragraphs": int(doc.Paragraphs.Count),
            "comments": int(doc.Comments.Count),
            "tables": int(doc.Tables.Count),
            "inline_shapes": int(doc.InlineShapes.Count),
            "fields": int(doc.Fields.Count),
            "revisions": int(doc.Revisions.Count),
        }
        # 显式关文档并丢引用：留着 `doc` 局部变量会让 WPS 的 Quit 撞 RPC 异常
        # （退出期本帧仍持有该 COM 引用，__exit__ 里的释放顺序救不回来）。
        session.close_all()
        doc = None
        gc.collect()
        return info


def rewrite_comments_via_office(docx_path, out_path):
    """打开并另存文档（COM 外挂触发，用于让 Office 重排/修复 OOXML 包）。

    与 `reflib.write_comments`（python-docx 注入通路）配套：注入后由 Office
    打开并另存，可实机验证批注包被接受、必要时由 Office 规范化。
    产物随后仍需走 `docxutil.finalize_comments` 收口固定时间戳（确定性纪律）。
    """
    with ComSession() as session:
        session.open(docx_path)
        session.save(out_path)
    return str(out_path)
