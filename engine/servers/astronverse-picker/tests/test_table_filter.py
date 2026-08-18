"""批量抓取数据筛选/处理单测 (utils/table_filter.py)"""

import pandas as pd
import pytest

from astronverse.picker.utils.table_filter import (
    DataFilter,
    page_values_merge,
    parse_datetime,
    table_df_to_out,
    table_json_merge_values,
    table_values_to_table_dict,
    values_to_row_list,
)


def _table_data(values=None, **overrides):
    """构造 table 类型抓取数据: 两列各三行"""
    base = {
        "produceType": "table",
        "values": values
        or [
            {"title": "名称", "value": ["苹果", "香蕉", "橙子"]},
            {"title": "价格", "value": ["10", "20", "30"]},
        ],
    }
    base.update(overrides)
    return base


class TestParseDatetime:
    def test_标准日期时间(self):
        assert parse_datetime("2026-08-17 10:30:00") == pd.Timestamp("2026-08-17 10:30:00")

    def test_斜杠与点分隔(self):
        assert parse_datetime("2026/08/17") == pd.Timestamp("2026-08-17")
        assert parse_datetime("2026.08.17") == pd.Timestamp("2026-08-17")

    def test_中文格式(self):
        assert parse_datetime("2026年08月17日") == pd.Timestamp("2026-08-17")
        assert parse_datetime("08月17日 10:30") == pd.Timestamp("1900-08-17 10:30")

    def test_纯时间格式(self):
        assert parse_datetime("10:30:00") == pd.Timestamp("1900-01-01 10:30:00")

    def test_无法解析返回原串(self):
        assert parse_datetime("not-a-date") == "not-a-date"

    def test_空串返回空(self):
        assert parse_datetime("") == ""


class TestDataFilterTable:
    def test_无配置_原样通过(self):
        df_filter = DataFilter(_table_data())
        # 转置后: 行x列
        assert df_filter.data_table.shape == (3, 3)  # index + 2列
        got = df_filter.get_filtered_data()
        assert [v["value"] for v in got["values"]] == [["苹果", "香蕉", "橙子"], ["10", "20", "30"]]
        # 无配置时配置键被清空
        assert got["values"][0]["filterConfig"] == []

    def test_等于数字筛选(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "香蕉", "橙子"]},
                {"title": "价格", "value": ["10", "20", "30"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "==", "parameter": "20"},
                ]},
            ]
        )
        got = DataFilter(data).get_filtered_data()
        assert got["values"][0]["value"] == ["香蕉"]
        assert got["values"][1]["value"] == ["20"]

    def test_不等于筛选(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "香蕉", "橙子"]},
                {"title": "价格", "value": ["10", "20", "30"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "!=", "parameter": "20"},
                ]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["苹果", "橙子"]

    def test_大于数值比较(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "香蕉", "橙子"]},
                {"title": "价格", "value": ["10", "20", "30"], "filterConfig": [
                    {"filterAssociation": "and", "logical": ">", "parameter": "15"},
                ]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["香蕉", "橙子"]

    def test_包含与不包含(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "芒果", "橙子"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "contains", "parameter": "果"},
                ]},
                {"title": "价格", "value": ["10", "20", "30"]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["苹果", "芒果"]

    def test_正则特殊字符contains被转义(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["a.c", "abc", "axc"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "contains", "parameter": "a.c"},
                ]},
                {"title": "x", "value": ["1", "2", "3"]},
            ]
        )
        # '.' 被转义后只匹配字面 "a.c"
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["a.c"]

    def test_开头结尾匹配(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果汁", "香蕉", "苹果"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "startswith", "parameter": "苹果"},
                ]},
                {"title": "x", "value": ["1", "2", "3"]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["苹果汁", "苹果"]

    def test_空与非空(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "", "橙子"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "isnull", "parameter": ""},
                ]},
                {"title": "x", "value": ["1", "2", "3"]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == [""]

    def test_枚举筛选(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "香蕉", "橙子"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "enumerate", "parameter": "['苹果', '橙子']"},
                ]},
                {"title": "x", "value": ["1", "2", "3"]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["苹果", "橙子"]

    def test_正则筛选(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["a1", "bb", "c3"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "regular", "parameter": r"\d"},
                ]},
                {"title": "x", "value": ["1", "2", "3"]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["a1", "c3"]

    def test_多条件or(self):
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "香蕉", "橙子"], "filterConfig": [
                    {"filterAssociation": "or", "logical": "==", "parameter": "苹果"},
                    {"filterAssociation": "or", "logical": "==", "parameter": "橙子"},
                ]},
                {"title": "x", "value": ["1", "2", "3"]},
            ]
        )
        assert DataFilter(data).get_filtered_data()["values"][0]["value"] == ["苹果", "橙子"]

    def test_不支持的条件抛ValueError(self):
        data = _table_data(
            values=[
                {"title": "x", "value": ["1"], "filterConfig": [
                    {"filterAssociation": "and", "logical": "bad_op", "parameter": "1"},
                ]},
            ]
        )
        with pytest.raises(ValueError, match="暂不支持该筛选条件"):
            DataFilter(data).get_filtered_data()

    def test_单元格过滤_不影响其他列(self):
        """cellFilterConfig 输入键为 colFilterConfig"""
        data = _table_data(
            values=[
                {"title": "名称", "value": ["苹果", "香蕉", "橙子"]},
                {"title": "价格", "value": ["10", "20", "30"], "colFilterConfig": [
                    {"filterAssociation": "and", "logical": "==", "parameter": "20"},
                ]},
            ]
        )
        got = DataFilter(data).get_filtered_data()
        # 名称列保持原样, 价格列只留 20
        assert got["values"][0]["value"] == ["苹果", "香蕉", "橙子"]
        assert got["values"][1]["value"] == ["20"]


class TestDataFilterDataProcess:
    def _process(self, processes, col_values=None):
        data = _table_data(
            values=[
                {"title": "名称", "value": col_values or ["  a1  ", "b2\n", "c3"],
                 "colDataProcessConfig": [p for p in processes if p["isEnable"]]},
                {"title": "价格", "value": ["1", "2", "3"]},
            ]
        )
        return DataFilter(data).get_filtered_data()

    def test_trim清洗空白(self):
        got = self._process([{"processType": "Trim", "isEnable": True, "parameters": []}])
        assert got["values"][0]["value"] == ["a1", "b2", "c3"]

    def test_提取数字(self):
        got = self._process([{"processType": "ExtractNum", "isEnable": True, "parameters": []}], ["a1b2", "cc33", "无"])
        assert got["values"][0]["value"] == ["12", "33", ""]

    def test_字符替换(self):
        got = self._process(
            [{"processType": "Replace", "isEnable": True,
              "parameters": [{"text": "苹果", "replaceText": "梨"}]}],
            ["苹果1", "苹果2", "x"],
        )
        assert got["values"][0]["value"] == ["梨1", "梨2", "x"]

    def test_前后缀(self):
        got = self._process(
            [
                {"processType": "Prefix", "isEnable": True, "parameters": [{"val": "ID-"}]},
                {"processType": "Suffix", "isEnable": False, "parameters": [{"val": "-END"}]},
            ],
            ["a", "b", "c"],
        )
        assert got["values"][0]["value"] == ["ID-a", "ID-b", "ID-c"]

    def test_正则提取(self):
        """已知行为: 无匹配行会让后续提取结果整体上移(行错位), 尾部补空"""
        got = self._process(
            [{"processType": "Regular", "isEnable": True, "parameters": [{"val": r"\d+"}]}],
            ["a1b2", "cc", "d33"],
        )
        assert got["values"][0]["value"] == ["1 2", "33", ""]

    def test_正则提取全命中不错位(self):
        got = self._process(
            [{"processType": "Regular", "isEnable": True, "parameters": [{"val": r"\d+"}]}],
            ["a1", "b2", "c3"],
        )
        assert got["values"][0]["value"] == ["1", "2", "3"]

    def test_格式化时间(self):
        got = self._process(
            [{"processType": "FormatTime", "isEnable": True, "parameters": [{"val": "%Y/%m/%d"}]}],
            ["2026-08-17 10:00:00", "bad-date", "2026-01-02"],
        )
        assert got["values"][0]["value"][0] == "2026/08/17"
        assert got["values"][0]["value"][1] == ""  # 解析失败填空
        assert got["values"][0]["value"][2] == "2026/01/02"

    def test_必填参数缺失抛ValueError(self):
        with pytest.raises(ValueError, match="缺少参数"):
            self._process([{"processType": "Replace", "isEnable": True, "parameters": []}])


class TestDataFilterSimilar:
    def _similar_data(self, filter_config=None):
        return {
            "produceType": "similar",
            "values": [
                {
                    "title": "标题",
                    "value_type": "text",
                    "value": [
                        {"text": "", "attrs": {"text": "第一项", "href": "/1"}},
                        {"text": "", "attrs": {"text": "第二项", "href": "/2"}},
                    ],
                    **({"filterConfig": filter_config} if filter_config else {}),
                }
            ],
        }

    def test_文本提取自attrs(self):
        got = DataFilter(self._similar_data()).get_filtered_data()
        assert [v["text"] for v in got["values"][0]["value"]] == ["第一项", "第二项"]

    def test_value_type指定其他属性(self):
        data = self._similar_data()
        data["values"][0]["value_type"] = "href"
        df = DataFilter(data)
        # 文本列变为 href 值
        assert list(df.data_table[0]) == ["/1", "/2"]

    def test_不等长补齐(self):
        data = self._similar_data()
        data["values"].append(
            {"title": "备注", "value_type": "text", "value": [{"text": "", "attrs": {"text": "仅一条"}}]}
        )
        df = DataFilter(data)
        assert df.data_table.shape[0] == 2  # 以最长列为准

    def test_筛选回写text字段(self):
        cfg = [{"filterAssociation": "and", "logical": "contains", "parameter": "第一"}]
        got = DataFilter(self._similar_data(cfg)).get_filtered_data()
        assert [v["text"] for v in got["values"][0]["value"]] == ["第一项"]


class TestMergeUtils:
    def test_table_json_merge_values_正常合并(self):
        data_json = {"values": [{"title": "a", "value": ["old"]}]}
        values = [{"value": ["new1", "new2"]}]
        merged = table_json_merge_values(data_json, values)
        assert merged["values"][0]["value"] == ["new1", "new2"]

    def test_table_json_merge_values_空侧覆盖(self):
        assert table_json_merge_values({"values": []}, [{"value": [1]}])["values"] == [{"value": [1]}]
        assert table_json_merge_values({"values": [{"value": [1]}]}, None)["values"] is None

    def test_page_values_merge_补齐与合并(self):
        pre = [{"title": "a", "value": ["1"]}, {"title": "b", "value": ["x", "y"]}]
        cur = [{"title": "a", "value": ["2"]}, {"title": "b", "value": ["z"]}]
        out = page_values_merge(pre, cur, "table")
        assert out[0]["value"] == ["1", "2"]
        assert out[1]["value"] == ["x", "y", "z"]

    def test_page_values_merge_空pre直接返回(self):
        cur = [{"title": "a", "value": ["1"]}]
        assert page_values_merge([], cur, "table") is cur

    def test_page_values_merge_similar补齐结构体(self):
        cur = [{"title": "a", "value": [{"text": "1"}]}, {"title": "b", "value": [{"text": "2"}, {"text": "3"}]}]
        out = page_values_merge([], cur, "similar")
        assert out[0]["value"][1] == {"text": "", "attrs": {}}

    def test_values_to_row_list_table(self):
        values = [{"title": "c1", "value": ["a", "b"]}, {"title": "c2", "value": ["1", "2"]}]
        assert values_to_row_list(values, "table") == [["a", "1"], ["b", "2"]]

    def test_values_to_row_list_similar保留结构体(self):
        """similar 类型行数组保留 {text, attrs} 结构体(由消费方自行提取)"""
        values = [{"title": "c1", "value": [{"text": "a"}, {"text": "b"}]}]
        assert values_to_row_list(values, "similar") == [[{"text": "a"}], [{"text": "b"}]]

    def test_table_df_to_out_table(self):
        df = table_df_to_out({"produceType": "table", "values": [
            {"title": "c1", "value": ["a", "b"]}, {"title": "c2", "value": ["1", "2"]},
        ]})
        assert df.values.tolist() == [["a", "1"], ["b", "2"]]
        assert list(df.columns) == ["c1", "c2"]

    def test_table_df_to_out_similar(self):
        df = table_df_to_out({"produceType": "similar", "values": [
            {"title": "c1", "value": [{"text": "a"}, {"text": "b"}]},
        ]})
        assert df["c1"].tolist() == ["a", "b"]

    def test_table_values_to_table_dict(self):
        out = table_values_to_table_dict(
            [{"title": "c1", "value": ["a", "b"]}, {"title": "c2", "value": ["1", "2"]}], "table"
        )
        assert out == {"c1": ["a", "b"], "c2": ["1", "2"]}
