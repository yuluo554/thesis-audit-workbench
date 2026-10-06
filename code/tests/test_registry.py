"""模块注册表守门：16 项、id 唯一、字段完整（plan/04 §八口径）。"""

from taw import registry


def test_total_is_16():
    assert registry.total() == 16


def test_ids_unique():
    ids = [m["id"] for m in registry.MODULES]
    assert len(ids) == len(set(ids))


def test_line_distribution():
    counts = {}
    for m in registry.MODULES:
        counts[m["line"]] = counts.get(m["line"], 0) + 1
    assert counts == {"ref": 9, "full": 6, "bench": 1}


def test_fields_complete():
    valid_milestones = {"M1", "M2", "M3", "M4", "M5", "M6", "M7"}
    for m in registry.MODULES:
        assert m["id"], "缺 id"
        assert m["name"], "缺名称: {}".format(m["id"])
        assert m["line"] in registry.LINE_NAMES
        assert m["milestone"] in valid_milestones
        assert m["status"] in ("planned", "in_progress", "done")


def test_counts_string_has_all_lines():
    text = registry.counts()
    for line_name in registry.LINE_NAMES.values():
        assert line_name in text
