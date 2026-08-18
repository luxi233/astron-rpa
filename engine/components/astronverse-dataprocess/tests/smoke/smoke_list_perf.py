"""dataprocess 列表性能优化冒烟测试。

覆盖(P11):
1. filter_elements_from_list: set 快路径 O(n+m) 与旧线性扫描结果一致; 不可哈希项回退
2. remove_columns_from_2d_list: 正索引集合提到循环外, 负索引逐行换算, 行为与归一化语义一致
3. filter_empty_items(only_trim_trailing=True): 不再先做全量非空行扫描

运行: cd engine/components/astronverse-dataprocess && .venv/bin/python tests/smoke/smoke_list_perf.py
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from astronverse.dataprocess.list import ListProcess, ListProcessExtend  # noqa: E402

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


# ---------- 1. 列表过滤: 快路径与线性扫描等价 ----------
cases = [
    ([1, 2, 3, 2], [2], [1, 3]),
    (["a", "b"], ["b", "c"], ["a"]),
    ([], [], []),
    ([1, "1", True], [1], ["1"]),  # 1 == True 哈希语义与线性 in 一致
    ([None, ""], [None], [""]),
]
for l1, l2, want in cases:
    got = ListProcess.filter_elements_from_list(list_data_1=list(l1), list_data_2=list(l2))
    check(f"过滤等价: {l1} - {l2}", got == want, f"got {got}")

# 不可哈希回退
got = ListProcess.filter_elements_from_list(list_data_1=[[1, 2], [3, 4], [5]], list_data_2=[[3, 4]])
check("过滤回退: 不可哈希项", got == [[1, 2], [5]], f"got {got}")

# 大列表等价 + 提速
random.seed(42)
big1 = [random.randint(0, 5000000) for _ in range(10000)]
big2 = [random.randint(0, 5000000) for _ in range(10000)]
t0 = time.perf_counter()
r_new = ListProcess.filter_elements_from_list(list_data_1=big1, list_data_2=big2)
t1 = time.perf_counter()
t2 = time.perf_counter()
r_old = [i for i in big1 if i not in big2]
t3 = time.perf_counter()
check("过滤: 1万x1万结果一致", r_new == r_old, f"{len(r_new)} vs {len(r_old)}")
check(f"过滤: 提速({(t1 - t0) * 1000:.1f}ms vs 旧{(t3 - t2) * 1000:.1f}ms)", (t1 - t0) < (t3 - t2) / 10)

# ---------- 2. 删列: 正索引预计算 + 负索引逐行 ----------
rows = [[f"c{r}-{c}" for c in range(10)] for r in range(5)]
out = ListProcessExtend.remove_columns_from_2d_list(list_data=rows, column_indexes="0,2")
check("删列: 正索引0,2", out[0] == ["c0-1", "c0-3", "c0-4", "c0-5", "c0-6", "c0-7", "c0-8", "c0-9"], str(out[0]))
neg = ListProcessExtend.remove_columns_from_2d_list(list_data=[[1, 2, 3], [4, 5]], column_indexes="-1")
check("删列: 负索引-1", neg == [[1, 2], [4]], str(neg))
mixed = ListProcessExtend.remove_columns_from_2d_list(list_data=[[1, 2, 3]], column_indexes="0,-1")
check("删列: 正负混合", mixed == [[2]], str(mixed))
oob = ListProcessExtend.remove_columns_from_2d_list(list_data=[[1, 2]], column_indexes="5")
check("删列: 越界索引无副作用", oob == [[1, 2]], str(oob))
nonlist = ListProcessExtend.remove_columns_from_2d_list(list_data=[[1, 2], "x"], column_indexes="0")
check("删列: 非列表行原样保留", nonlist == [[2], "x"], str(nonlist))

# ---------- 3. 过滤空值: 尾部裁剪语义不变 ----------
data = [[1, ""], [None, None], ["a", "b"], [None, None]]
out = ListProcessExtend.filter_empty_items(list_data=[r[:] for r in data], only_trim_trailing=True)
check("空值裁剪: 尾部空行移除且中间空行也过滤", out == [[1, ""], ["a", "b"]], str(out))
out = ListProcessExtend.filter_empty_items(list_data=[r[:] for r in data], only_trim_trailing=False)
check("空值过滤: 全部空行移除", out == [[1, ""], ["a", "b"]], str(out))
out1d = ListProcessExtend.filter_empty_items(list_data=["a", "", None, " ", "b"], only_trim_trailing=True)
check("空值裁剪: 一维", out1d == ["a", "b"], str(out1d))

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
