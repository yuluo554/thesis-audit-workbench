# -*- coding: utf-8 -*-
"""编号重排内核（plan/04 §五 签名；REF-07 文献编号 与 M4 FULL-01 对象编号共用）。

```python
def renumber(items, edits) -> RenumberPlan
# NumberedItem: {item_id, markers: [MarkerRef]}      # 列表顺序即旧编号顺序
# Edit: {type: insert|delete, target: item_id, ...}
# RenumberPlan: {mappings, consistent, new_order, diagnostics}
```

**一致性定义**（plan/04 §五）：重排后
1. 正文每个标记都能解析到**唯一**新编号（无重复、无遗漏）；
2. 编号序列**连续无断档**（1..N）。

基准：任意插入/删除位置 × 组合矩阵回归 100%（M3 文献编号、M4 对象编号各一套）。

编辑语义（显式、确定）：
- `{"type": "insert", "new_item_id": X, "target": T, "before": bool=False}`：
  在 T 之后（`before=True` 则在之前）插入 X；
- `{"type": "delete", "target": T}`：删除 T。
"""


def _marker_ids(item):
    return [m.get("marker_id") for m in item.get("markers", [])]


def renumber(items, edits):
    """执行重排 → RenumberPlan。不修改入参（纯函数）。"""
    seq = [{"item_id": it["item_id"], "markers": [dict(m) for m in it.get("markers", [])]}
           for it in items]
    diagnostics = []

    for edit in edits:
        etype = edit.get("type")
        target = edit.get("target")
        idx = _index_of(seq, target)
        if etype == "insert":
            new_id = edit.get("new_item_id")
            if new_id is None:
                diagnostics.append({"kind": "insert_missing_new_item_id", "edit": edit})
                continue
            if idx is None:
                seq.append({"item_id": new_id, "markers": [dict(m) for m in edit.get("markers", [])]})
                diagnostics.append({"kind": "insert_target_missing_appended", "target": target})
                continue
            pos = idx if edit.get("before") else idx + 1
            seq.insert(pos, {"item_id": new_id,
                             "markers": [dict(m) for m in edit.get("markers", [])]})
        elif etype == "delete":
            if idx is None:
                diagnostics.append({"kind": "delete_target_missing", "target": target})
                continue
            seq.pop(idx)
        else:
            diagnostics.append({"kind": "unknown_edit_type", "edit": edit})

    # 旧编号：按**原始**列表序；新编号：按重排后序
    old_no = {it["item_id"]: i + 1 for i, it in enumerate(items)}
    mappings = []
    seen_new = {}
    for new_idx, it in enumerate(seq, 1):
        seen_new.setdefault(it["item_id"], []).append(new_idx)
    for new_idx, it in enumerate(seq, 1):
        for m in it["markers"]:
            mappings.append({
                "marker_id": m.get("marker_id"),
                "item_id": it["item_id"],
                "old_no": old_no.get(it["item_id"]),
                "new_no": new_idx,
            })

    # 一致性：新编号构造上即为 1..N 连续；再查 item_id 重复与标记归属冲突
    dups = sorted(k for k, v in seen_new.items() if len(v) > 1)
    if dups:
        diagnostics.append({"kind": "duplicate_item_id_after_edits", "items": dups})
    # 标记唯一性：同一 marker_id 不得出现在多个 item
    marker_owner = {}
    marker_dup = []
    for it in seq:
        for mid in _marker_ids(it):
            if mid is None:
                continue
            if mid in marker_owner and marker_owner[mid] != it["item_id"]:
                marker_dup.append(mid)
            marker_owner[mid] = it["item_id"]
    if marker_dup:
        diagnostics.append({"kind": "marker_claimed_by_multiple_items", "markers": marker_dup})

    consistent = not dups and not marker_dup
    return {
        "mappings": mappings,
        "consistent": consistent,
        "new_order": [it["item_id"] for it in seq],
        "n_items": len(seq),
        "diagnostics": diagnostics,
    }


def _index_of(seq, item_id):
    for i, it in enumerate(seq):
        if it["item_id"] == item_id:
            return i
    return None


def _first(v):
    return v[0] if v else 0


def verify_plan(plan):
    """独立复核 RenumberPlan（不信任构造期自报的 consistent）。

    检查：① 编号序列恰为 1..N 连续无断档（按 new_order 位置即编号）；
    ② 每个标记唯一新编号、无重复标记映射；③ 映射的 new_no 与其 item 的位置一致。
    """
    order = plan["new_order"]
    n = len(order)
    if sorted(set(order)) != sorted(order):
        return False                      # item_id 重复
    pos = {item_id: i + 1 for i, item_id in enumerate(order)}
    seen = {}
    for m in plan["mappings"]:
        if m["new_no"] != pos.get(m["item_id"]):
            return False                  # 映射与位置不符
        if not 1 <= m["new_no"] <= n:
            return False
        key = m["marker_id"]
        if key is None:
            continue
        if key in seen:
            return False                  # 标记重号
        seen[key] = m["item_id"]
    if n and sorted(pos.values()) != list(range(1, n + 1)):
        return False
    return bool(plan["consistent"])
