# -*- coding: utf-8 -*-
"""M1批次冒烟: P3-0字典×6 + P4-2日期×3+1增强 + P5-3 json×1 (全部kwargs调用)

注: P4-3 URL×2 属 encrypt 组件，见 astronverse-encrypt/tests/smoke/smoke_m1_url.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from astronverse.actionlib.types import Date
from astronverse.dataprocess import DateListOutputType, TimeUnitType
from astronverse.dataprocess.dataconvert import DataConvertProcess as DC
from astronverse.dataprocess.dict import DictProcess as D
from astronverse.dataprocess.time import TimeProcess as T

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


def d(ts):
    x = Date()
    x.time = ts
    return x


from datetime import datetime  # noqa: E402

# ---------- P3-0 字典 ----------
d1 = {"a": 1, "b": 2}
d2 = {"b": 99, "c": 3}
r = D.merge_dict(dict_data=d1, merge_dict_data=d2)
check("merge 冲突键后者覆盖", r == {"a": 1, "b": 99, "c": 3}, r)
check("merge 就地修改", d1 is r and d1["b"] == 99)

d3 = {"x": 1}
r = D.clear_dict(dict_data=d3)
check("clear 清空", r == {} and d3 == {})

d4 = {" k1 ": 1, "k2 ": 2, 3: "int-key", "nested": {" n ": "v"}}
r = D.strip_dict_keys(dict_data=d4)
check("strip_keys 一级键", set(r.keys()) == {"k1", "k2", 3, "nested"}, r)
check("strip_keys 嵌套不递归", r["nested"] == {" n ": "v"}, r["nested"])
check("strip_keys 非str键保持", 3 in r)

d5 = {"a": " v1 ", "b": 2, "c": [" x "]}
r = D.strip_dict_values(dict_data=d5)
check("strip_values 一级值", r["a"] == "v1", r)
check("strip_values 非str保持", r["b"] == 2 and r["c"] == [" x "], r)

check("key_exist True", D.dict_key_exist(dict_data={"a": 1}, dict_key="a") is True)
check("key_exist False", D.dict_key_exist(dict_data={"a": 1}, dict_key="z") is False)

r = D.dict_to_text(dict_data={"a": 1, "b": 2}, item_connect=";", kv_connect="=")
check("dict_to_text", r == "a=1;b=2", r)
r = D.dict_to_text(dict_data={"a": 1})
check("dict_to_text 默认连接符", r == "a:1", r)

for bad in ("merge_dict", "clear_dict", "strip_dict_keys", "strip_dict_values", "dict_key_exist", "dict_to_text"):
    extra = {"merge_dict_data": {}} if bad == "merge_dict" else {"dict_key": "k"} if bad == "dict_key_exist" else {}
    try:
        getattr(D, bad)(dict_data=[1, 2], **extra)
        check(f"{bad} 非dict报错", False)
    except Exception as e:
        check(f"{bad} 非dict报错", "字典" in str(e), str(e))

# ---------- P4-2 日期 ----------
r = T.date_to_chinese(time=d(datetime(2023, 5, 1)))
check("汉字日期 2023-5-1", r == "二零二三年五月一日", r)
r = T.date_to_chinese(time=d(datetime(2023, 10, 21)))
check("汉字日期 十月/二十一", r == "二零二三年十月二十一日", r)
r = T.date_to_chinese(time=d(datetime(2023, 12, 31)))
check("汉字日期 十二月/三十一", r == "二零二三年十二月三十一日", r)
r = T.date_to_chinese(time=d(datetime(2020, 1, 10)))
check("汉字日期 二零二零年一月十日", r == "二零二零年一月十日", r)

# get_datetime_list
lst = T.get_datetime_list(start_time=d(datetime(2023, 1, 1)), end_time=d(datetime(2023, 1, 5)), interval=2, interval_unit=TimeUnitType.DAY, output_type=DateListOutputType.TEXT)
check("list 文本输出", lst == ["2023-01-01 00:00:00", "2023-01-03 00:00:00", "2023-01-05 00:00:00"], lst)
lst = T.get_datetime_list(start_time=d(datetime(2023, 1, 1)), end_time=d(datetime(2023, 1, 3)), interval=1, interval_unit=TimeUnitType.DAY, output_type=DateListOutputType.TEXT, without_zeros=True)
check("list 去零", lst == ["2023-1-1 0:0:0", "2023-1-2 0:0:0", "2023-1-3 0:0:0"], lst)
lst = T.get_datetime_list(start_time=d(datetime(2023, 1, 1)), end_time=d(datetime(2023, 1, 3)), interval=1, interval_unit=TimeUnitType.DAY, output_type=DateListOutputType.DATETIME)
check("list 对象输出", [x.time.day for x in lst] == [1, 2, 3], lst)
lst = T.get_datetime_list(start_time=d(datetime(2023, 1, 1)), end_time=d(datetime(2023, 1, 3)), interval=1, interval_unit=TimeUnitType.DAY, output_type=DateListOutputType.TEXT, reverse=True)
check("list 倒序", lst == ["2023-01-03 00:00:00", "2023-01-02 00:00:00", "2023-01-01 00:00:00"], lst)
lst = T.get_datetime_list(start_time=d(datetime(2023, 1, 31)), end_time=d(datetime(2023, 3, 31)), interval=1, interval_unit=TimeUnitType.MONTH, output_type=DateListOutputType.TEXT)
check("list 月末步进1.31→2.28", [x[:10] for x in lst] == ["2023-01-31", "2023-02-28", "2023-03-31"], lst)
lst = T.get_datetime_list(start_time=d(datetime(2023, 1, 1)), end_time=d(datetime(2023, 1, 1, 0, 0, 5)), interval=2, interval_unit=TimeUnitType.SECOND, output_type=DateListOutputType.TEXT)
check("list 秒步进", len(lst) == 3, lst)
try:
    T.get_datetime_list(start_time=d(datetime(2023, 2, 1)), end_time=d(datetime(2023, 1, 1)), interval=1, interval_unit=TimeUnitType.DAY)
    check("list 起止倒挂报错", False)
except ValueError as e:
    check("list 起止倒挂报错", "开始时间" in str(e), str(e))
try:
    T.get_datetime_list(start_time=d(datetime(2023, 1, 1)), end_time=d(datetime(2023, 1, 2)), interval=0, interval_unit=TimeUnitType.DAY)
    check("list 间隔0报错", False)
except ValueError as e:
    check("list 间隔0报错", "间隔" in str(e), str(e))

# modify_datetime
r = T.modify_datetime(time=d(datetime(2023, 5, 20, 10, 30, 15)), month=6)
check("modify 替换月", r.time == datetime(2023, 6, 20, 10, 30, 15), r.time)
r = T.modify_datetime(time=d(datetime(2023, 5, 20, 10, 30, 15)), year=2024, day=1, hour=0, minute=0, second=0)
check("modify 多域替换", r.time == datetime(2024, 5, 1, 0, 0, 0), r.time)
r = T.modify_datetime(time=d(datetime(2023, 5, 20)))
check("modify 不填保持原值", r.time == datetime(2023, 5, 20), r.time)

# format_datetime 增强
r = T.format_datetime(time=d(datetime(2023, 5, 1, 9, 8, 7)))
check("format 默认", r == "2023-05-01 09:08:07", r)
r = T.format_datetime(time=d(datetime(2023, 5, 1)), custom_format="%Y年%m月%d日")
check("format 自定义模板", r == "2023年05月01日", r)
r = T.format_datetime(time=d(datetime(2023, 5, 1, 9, 8, 7)), without_zeros=True)
check("format 去零", r == "2023-5-1 9:8:7", r)
r = T.format_datetime(time=d(datetime(2023, 5, 1)), custom_format="%Y/%m/%d", without_zeros=True)
check("format 自定义+去零", r == "2023/5/1", r)

# ---------- P5-3 json提取 ----------
data = {"a": {"name": "x", "list": [{"name": "y"}, {"b": {"name": "z"}}]}}
r = DC.extract_json_key(input_data=data, extract_key="name")
check("json提取 嵌套3层", r == ["x", "y", "z"], r)
r = DC.extract_json_key(input_data='{"a": [{"k": 1}, {"k": 2}]}', extract_key="k")
check("json提取 str输入+列表内dict", r == [1, 2], r)
r = DC.extract_json_key(input_data={"a": 1}, extract_key="zzz")
check("json提取 无匹配空列表", r == [], r)
try:
    DC.extract_json_key(input_data="not-json{", extract_key="k")
    check("json提取 非法str报错", False)
except ValueError as e:
    check("json提取 非法str报错", "JSON" in str(e), str(e))

print(f"\n=== M1 冒烟: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
