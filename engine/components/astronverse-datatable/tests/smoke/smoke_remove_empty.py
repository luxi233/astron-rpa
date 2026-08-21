"""数据表格删除空行/列原子(remove_empty_rows_cols)冒烟测试。

覆盖:
1. 基本功能: 中间空行、整列空列一次性删除, 数据完整性不受影响
2. 空行空列并存: 一次调用同时处理
3. 幻影空行: delete_rows 残留幻影行使 max_row 虚高时, 判定与数据不受影响
4. 列头同步: 删除空列时 PyxlHeadWrapper 同步删除
5. 参数分支: 仅删行/仅删列/全不勾选报错
6. 连续区间合并: _to_desc_ranges 正确性(多段连续区间从大到小)
7. 边界: 全空表格、无空行列表格

注意: openpyxl 中未物化的行/列不存在(不算空行/列), 测试用空字符串""物化空单元格。

运行: cd engine/components/astronverse-datatable && uv run python tests/smoke/smoke_remove_empty.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import astronverse.datatable.datatable as dt_mod  # noqa: E402
from astronverse.datatable.datatable import DataTable, _to_desc_ranges, last_nonempty_row  # noqa: E402
from astronverse.datatable.error import DATAFRAME_EXPECTION  # noqa: E402
from astronverse.datatable.openpyxl import OpenpyxlWrapper  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


def make_sheet(rows: list, cols: int):
    """创建临时 xlsx 并替换模块级 wrapper(与真实运行时同一入口);
    rows 中的 '' 会物化为空字符串单元格(模拟真实空行/列)"""
    td = tempfile.mkdtemp(prefix="rm_empty_")
    fp = os.path.join(td, "t.xlsx")
    hp = os.path.join(td, "head.xlsx")
    w = OpenpyxlWrapper(file_path=fp)
    for ri, row in enumerate(rows, start=1):
        for ci, value in enumerate(row, start=1):
            if value is not None:
                w.write_cell(row=ri, col=ci, value=value)
    w.save()
    hw = OpenpyxlWrapper(file_path=hp)
    for ci in range(1, cols + 1):
        hw.write_cell(row=1, col=ci, value=f"head{ci}")
    hw.save()
    dt_mod.PyxlWrapper = w
    dt_mod.PyxlHeadWrapper = hw
    dt_mod._xlsx_file_path = fp
    dt_mod._head_file_path = hp
    return w, hw


def grid_of(w: OpenpyxlWrapper) -> list:
    max_row = w.get_max_row()
    max_col = w.get_max_column()
    if max_row < 1 or max_col < 1:
        return []
    return [
        list(r) for r in w.sheet.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col, values_only=True)
    ]


# ============================================================
# 0. _to_desc_ranges 连续区间合并
# ============================================================
print("\n========== 0. _to_desc_ranges ==========")
check("区间: 单元素", _to_desc_ranges([3]) == [(3, 1)], str(_to_desc_ranges([3])))
check(
    "区间: 多段连续从大到小",
    _to_desc_ranges([1, 2, 3, 7, 9, 10]) == [(9, 2), (7, 1), (1, 3)],
    str(_to_desc_ranges([1, 2, 3, 7, 9, 10])),
)
check("区间: 乱序输入", _to_desc_ranges([10, 1, 2]) == [(10, 1), (1, 2)], str(_to_desc_ranges([10, 1, 2])))
check("区间: 空列表", _to_desc_ranges([]) == [], str(_to_desc_ranges([])))

# ============================================================
# 1. 基本功能: 空行 + 空列 一次性删除
# ============================================================
print("\n========== 1. 基本功能 ==========")
# 布局: A,B 有数据; C 整列空(物化); 第3/5行整行空(物化)
rows = [
    ["h1", "h2", ""],
    ["a1", "b1", ""],
    ["", "", ""],
    ["a2", "b2", ""],
    ["", "", ""],
]
w, hw = make_sheet(rows, cols=3)
removed_rows, removed_cols = DataTable.remove_empty_rows_cols()
check("基本: 删除2空行", removed_rows == 2, str(removed_rows))
check("基本: 删除1空列", removed_cols == 1, str(removed_cols))
grid = grid_of(w)
check(
    "基本: 数据完整(3行2列)",
    w.get_max_row() == 3 and w.get_max_column() == 2 and grid == [["h1", "h2"], ["a1", "b1"], ["a2", "b2"]],
    f"{w.get_max_row()}x{w.get_max_column()} {grid}",
)
check(
    "基本: 列头同步删除",
    hw.get_max_column() == 2 and hw.read_cell(row=1, col=1) == "head1" and hw.read_cell(row=1, col=2) == "head2",
    str(grid_of(hw)),
)

# ============================================================
# 2. 空行空列并存 + 空字符串/None 口径
# ============================================================
print("\n========== 2. 并存场景 ==========")
rows = [
    ["a1", "x", ""],
    ["", "", ""],
    ["a2", "y", ""],
]
w, hw = make_sheet(rows, cols=3)
removed_rows, removed_cols = DataTable.remove_empty_rows_cols()
check("并存: C空列删除", removed_cols == 1, str(removed_cols))
check("并存: 第2空行删除", removed_rows == 1, str(removed_rows))
check("并存: 剩余数据", grid_of(w) == [["a1", "x"], ["a2", "y"]], str(grid_of(w)))

# ============================================================
# 3. 幻影空行: max_row 虚高不影响判定
# ============================================================
print("\n========== 3. 幻影空行 ==========")
rows = [
    ["a1", "b1"],
    ["", ""],
    ["", ""],
]
w, hw = make_sheet(rows, cols=2)
# 直接走 wrapper 删行制造幻影残留(openpyxl delete_rows 后 max_row 不收缩)
w.delete_rows(idx=2, amount=2)
check("幻影: 前置删除后非空行=1", last_nonempty_row() == 1, str(last_nonempty_row()))
removed_rows, removed_cols = DataTable.remove_empty_rows_cols()
check("幻影: 无空行列可删", removed_rows == 0 and removed_cols == 0, f"{removed_rows},{removed_cols}")
check("幻影: 数据未受影响", grid_of(w) == [["a1", "b1"]], str(grid_of(w)))

# ============================================================
# 4. 参数分支
# ============================================================
print("\n========== 4. 参数分支 ==========")
rows = [
    ["a1", ""],
    ["", ""],
]
w, hw = make_sheet(rows, cols=2)
removed_rows, removed_cols = DataTable.remove_empty_rows_cols(remove_cols=False)
check(
    "分支: 仅删行(列保留)",
    removed_rows == 1 and removed_cols == 0 and w.get_max_column() == 2,
    f"{removed_rows},{removed_cols} cols={w.get_max_column()}",
)

w, hw = make_sheet(rows, cols=2)
removed_rows, removed_cols = DataTable.remove_empty_rows_cols(remove_rows=False)
check(
    "分支: 仅删列(空行保留)",
    removed_cols == 1 and removed_rows == 0 and w.get_max_row() == 2,
    f"{removed_rows},{removed_cols} rows={w.get_max_row()}",
)

try:
    DataTable.remove_empty_rows_cols(remove_rows=False, remove_cols=False)
    check("分支: 全不勾选报错", False, "未抛出异常")
except DATAFRAME_EXPECTION:
    check("分支: 全不勾选报错", True)

# ============================================================
# 5. 边界: 全空 / 无空行列
# ============================================================
print("\n========== 5. 边界 ==========")
w, hw = make_sheet([["", ""], ["", ""]], cols=2)
removed_rows, removed_cols = DataTable.remove_empty_rows_cols()
check("边界: 全空表", removed_rows == 2 and removed_cols == 2, f"{removed_rows},{removed_cols}")

w, hw = make_sheet([["a", "b"], ["c", "d"]], cols=2)
removed_rows, removed_cols = DataTable.remove_empty_rows_cols()
check(
    "边界: 无空行列不动数据",
    removed_rows == 0 and removed_cols == 0 and grid_of(w) == [["a", "b"], ["c", "d"]],
    f"{removed_rows},{removed_cols} {grid_of(w)}",
)

print(f"\n结果: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
