"""
列表处理相关方法。
"""

import ast
import copy
import random
import re
from itertools import zip_longest
from typing import Any

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.dataprocess import (
    ContainModeType,
    ConvertDirectionType,
    DeleteMethodType,
    ExtremumType,
    Filter2DOperatorType,
    InsertMethodType,
    ListType,
    SortMethodType,
)
from astronverse.dataprocess.error import *


def list_legal_check(list_data: list, index: str = "", allow_empty: bool = True):
    """
    用于内部检查列表是否合法
    """
    if not allow_empty and len(list_data) == 0:
        raise ValueError("列表不能为空!")
    index_int = 0
    if index:
        try:
            if isinstance(index, str):
                # 将字符串按逗号分割并转换为整数列表
                index_list = [int(idx.strip()) for idx in index.split(",")]
                # 检查每个索引是否在有效范围内
                for idx in index_list:
                    if idx < -len(list_data) or idx >= len(list_data):
                        raise ValueError("数组索引值超出范围!")
                # 如果只有一个索引，返回第一个值
                if len(index_list) == 1:
                    index_int = index_list[0]
                else:
                    index_int = index_list
            else:
                # 如果不是字符串，直接转换为整数
                index_int = int(index)
                if index < -len(list_data) or index >= len(list_data):
                    raise ValueError("数组索引值超出范围!")
        except ValueError as e:
            raise ValueError("请提供有效的整数类型索引!")
        except Exception:
            raise ValueError("请提供整数类型的索引!")
    return list_data, index_int


class ListProcess:
    """列表处理流程类。"""

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param(
                "size",
                dynamics=[
                    DynamicsItem(
                        key="$this.size.show",
                        expression="return $this.list_type.value == '{}'".format(ListType.SAME_DATA.value),
                    )
                ],
            ),
            atomicMg.param(
                "value",
                types="Any",
                dynamics=[
                    DynamicsItem(
                        key="$this.value.show",
                        expression="return ['{}', '{}'].includes($this.list_type.value)".format(
                            ListType.SAME_DATA.value, ListType.USER_DEFINED.value
                        ),
                    )
                ],
            ),
            atomicMg.param(
                "custom_list",
                types="Any",
                dynamics=[
                    DynamicsItem(
                        key="$this.custom_list.show",
                        expression="return $this.list_type.value == '{}'".format(ListType.USER_DEFINED.value),
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("created_list_data", types="List")],
    )
    def create_new_list(list_type: ListType = ListType.EMPTY, size: int = 0, value: Any = "", custom_list: Any = ""):
        """
        创建新列表
        """
        if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
            try:
                value = ast.literal_eval(value)
            except Exception as e:
                raise BaseException(INVALID_LIST_FORMAT_ERROR_FORMAT.format(e), "请输入正确的列表格式")
        new_array = []
        if list_type == ListType.EMPTY:
            pass
        elif list_type == ListType.SAME_DATA:
            new_array = [value] * size
        elif list_type == ListType.USER_DEFINED:
            if isinstance(custom_list, str):
                if custom_list.startswith("[") and custom_list.endswith("]"):
                    try:
                        new_array = ast.literal_eval(custom_list)
                    except Exception as e:
                        new_array = [custom_list]
                else:
                    new_array = [custom_list]
            elif isinstance(custom_list, list):
                new_array = custom_list
            else:
                raise ValueError("用户自定义列表类型错误!")
        return new_array

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[atomicMg.param("list_data", types="List")],
        outputList=[atomicMg.param("cleared_list_data", types="List")],
    )
    def clear_list(list_data: list):
        """
        清空列表
        """
        list_data.clear()
        return list_data

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param(
                "index",
                dynamics=[
                    DynamicsItem(
                        key="$this.index.show",
                        expression="return $this.insert_method.value == '{}'".format(InsertMethodType.INDEX.value),
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("inserted_list_data", types="List")],
    )
    def insert_value_to_list(
        list_data: list,
        value: Any,
        insert_method: InsertMethodType = InsertMethodType.APPEND,
        index: str = "",
    ):
        """
        列表插入一项
        """
        index_int = 0
        if insert_method == InsertMethodType.APPEND:
            index = ""
        list_data, _ = list_legal_check(list_data, "", True)
        if insert_method == InsertMethodType.APPEND:  # 插入方式：末尾追加
            list_data.append(value)
        elif insert_method == InsertMethodType.INDEX:  # 插入方式：指定位置
            try:
                index_int = int(index)
            except:
                raise BaseException(INVALID_INDEX_ERROR_FORMAT.format(index), "需要提供整数类型的索引！")
            list_data.insert(index_int, value)
        return list_data

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("index", types="Any"),
        ],
        outputList=[atomicMg.param("changed_list_data", types="List")],
    )
    def change_value_in_list(list_data: list, index: str = "", new_value: Any = ""):
        """
        列表修改一项
        """
        index_int = 0
        list_data, index_int = list_legal_check(list_data, index, False)

        if isinstance(index_int, list):
            raise ValueError("请提供单个整数类型的索引！")
        else:
            list_data[index_int] = new_value
        return list_data

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("value", types="Any"),
        ],
        outputList=[atomicMg.param("get_list_position", types="Int")],
    )
    def get_list_position(list_data: list, value: Any):
        """
        列表获取一项的位置
        """
        try:
            list_pos = list_data.index(value)
            return list_pos
        except ValueError:
            raise ValueError("列表中不存在该对象!")

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param(
                "del_value",
                types="Any",
                dynamics=[
                    DynamicsItem(
                        key="$this.del_value.show",
                        expression="return $this.del_mode.value == '{}'".format(DeleteMethodType.VALUE.value),
                    )
                ],
            ),
            atomicMg.param(
                "del_pos",
                types="Any",
                dynamics=[
                    DynamicsItem(
                        key="$this.del_pos.show",
                        expression="return $this.del_mode.value == '{}'".format(DeleteMethodType.INDEX.value),
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("removed_list_data", types="List")],
    )
    def remove_value_from_list(
        list_data: list,
        del_mode: DeleteMethodType = DeleteMethodType.INDEX,
        del_value: Any = "",
        del_pos: str = "",
    ):
        """
        列表删除一项
        """
        del_pos_int = 0
        list_data, del_pos_int = list_legal_check(list_data, del_pos, False)
        if del_mode == DeleteMethodType.INDEX:
            if isinstance(del_pos_int, list):
                # 从大到小排序索引，避免删除时索引变化（del_pos 是原始字符串，须用解析后的 del_pos_int）
                sorted_indices = sorted(del_pos_int, reverse=True)
                for index in sorted_indices:
                    del list_data[int(index)]
            else:
                del list_data[del_pos_int]
            return list_data
        elif del_mode == DeleteMethodType.VALUE:
            try:
                index = list_data.index(del_value)
            except ValueError:
                raise ValueError("列表中未找到该元素！")
            del list_data[index]
            return list_data

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("sorted_list_data", types="List")],
    )
    def sort_list(list_data: list, sort_method: SortMethodType = SortMethodType.DESC):
        """
        列表排序
        """
        list_instance = []
        if sort_method == SortMethodType.ASC:
            try:
                list_instance = sorted(list_data)  # 升序
            except:
                raise ValueError("请提供元素数据类型一致的列表进行排序!")
        elif sort_method == SortMethodType.DESC:
            try:
                list_instance = sorted(list_data, reverse=True)  # 默认降序
            except:
                raise ValueError("请提供元素数据类型一致的列表进行排序!")
        return list_instance

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("shuffled_list_data", types="List")],
    )
    def random_shuffle_list(list_data: list):
        """
        列表随机排序
        :param list_data:
        :return:
        """
        random.shuffle(list_data)
        return list_data

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data_1", types="Any"),
            atomicMg.param("list_data_2", types="Any"),
        ],
        outputList=[atomicMg.param("filter_list_data", types="List")],
    )
    def filter_elements_from_list(list_data_1: list, list_data_2: list):
        """
        列表过滤
        """
        # 全可哈希时走 set 快路径 O(n+m); 含不可哈希项(嵌套list/dict)时回退线性扫描 O(n*m)
        try:
            exclude_set = set(list_data_2)
            return [i for i in list_data_1 if i not in exclude_set]
        except TypeError:
            return [i for i in list_data_1 if i not in list_data_2]

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("reversed_list_data", types="List")],
    )
    def reverse_list(list_data: list):
        """
        列表反转
        """
        list_data.reverse()
        return list_data

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data_1", types="Any"),
            atomicMg.param("list_data_2", types="Any"),
        ],
        outputList=[atomicMg.param("merged_list_data", types="List")],
    )
    def merge_list(list_data_1: list, list_data_2: list):
        """
        列表合并
        """
        result_list = list_data_1.copy()
        result_list.extend(list_data_2)
        return result_list

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("unique_list_data", types="List")],
    )
    def get_unique_list(list_data: list):
        """
        列表去重
        """
        list_data = list(set(list_data))
        return list_data

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data_1", types="Any"),
            atomicMg.param("list_data_2", types="Any"),
        ],
        outputList=[atomicMg.param("common_list_data", types="List")],
    )
    def get_common_elements_from_list(list_data_1: list, list_data_2: list):
        """
        列表获取共同元素
        """
        list_result = list(set(list_data_1) & set(list_data_2))
        return list_result

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("index", types="Any"),
        ],
        outputList=[atomicMg.param("get_list_value", types="Any")],
    )
    def get_value_from_list(list_data: list, index: str = ""):
        """
        列表获取一项
        """
        index_int = 0
        list_data, index_int = list_legal_check(list_data, index, False)
        if isinstance(index_int, list):
            raise ValueError("请提供单个整数类型的索引！")
        return list_data[index_int]

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("get_list_length", types="Int")],
    )
    def get_length_of_list(list_data: list):
        """
        列表获取长度
        """
        return len(list_data)


def _is_empty_value(value: Any) -> bool:
    """判断是否为空值（None、空字符串、纯空白字符串、空列表/字典/元组）。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple)):
        return len(value) == 0
    return False


def _to_number(value: Any):
    """尝试将值转换为数值，失败返回 None。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(text)
        except ValueError:
            try:
                return float(text)
            except ValueError:
                return None
    return None


def _cell_str(value: Any) -> str:
    """单元格值转字符串（None 转空串）。"""
    return "" if value is None else str(value)


def _iter_numbers(list_data: list) -> list:
    """提取列表中所有可转换为数值的项。"""
    numbers = [_to_number(item) for item in list_data]
    numbers = [n for n in numbers if n is not None]
    if not numbers:
        raise ValueError("列表中没有可参与计算的数值项!")
    return numbers


def _strip_items_deep(data: Any) -> Any:
    """递归去除所有字符串项两端的空格。"""
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        return [_strip_items_deep(item) for item in data]
    return data


def _flatten_deep(data: list) -> list:
    """递归展开多维列表。"""
    result = []
    for item in data:
        if isinstance(item, list):
            result.extend(_flatten_deep(item))
        else:
            result.append(item)
    return result


def _parse_indexes(indexes: Any) -> list:
    """解析逗号分隔的索引字符串为整数列表。"""
    if isinstance(indexes, (int, float)):
        return [int(indexes)]
    if isinstance(indexes, list):
        return [int(idx) for idx in indexes]
    text = str(indexes).strip()
    if not text:
        raise ValueError("请提供至少一个列索引!")
    try:
        return [int(idx.strip()) for idx in text.split(",") if idx.strip() != ""]
    except ValueError:
        raise ValueError("请提供逗号分隔的整数列索引，如：0,2")


def _norm_index(idx: int, length: int):
    """将负索引转换为正索引，越界返回 None。"""
    if idx < 0:
        idx += length
    if idx < 0 or idx >= length:
        return None
    return idx


def _match_condition(cell: Any, operator: Filter2DOperatorType, condition_value: Any) -> bool:
    """二维列表筛选：对单元格执行条件判断（数值感知）。"""
    cell_text = _cell_str(cell)
    target_text = _cell_str(condition_value)
    if operator == Filter2DOperatorType.IS_EMPTY:
        return _is_empty_value(cell)
    if operator == Filter2DOperatorType.NOT_EMPTY:
        return not _is_empty_value(cell)
    if operator == Filter2DOperatorType.EQUAL:
        a, b = _to_number(cell), _to_number(condition_value)
        if a is not None and b is not None:
            return a == b
        return cell_text == target_text
    if operator == Filter2DOperatorType.NOT_EQUAL:
        return not _match_condition(cell, Filter2DOperatorType.EQUAL, condition_value)
    a, b = _to_number(cell), _to_number(condition_value)
    left, right = (a, b) if (a is not None and b is not None) else (cell_text, target_text)
    if operator == Filter2DOperatorType.GREATER:
        return left > right
    if operator == Filter2DOperatorType.GREATER_EQUAL:
        return left >= right
    if operator == Filter2DOperatorType.LESS:
        return left < right
    if operator == Filter2DOperatorType.LESS_EQUAL:
        return left <= right
    if operator == Filter2DOperatorType.CONTAINS:
        return target_text in cell_text
    if operator == Filter2DOperatorType.NOT_CONTAINS:
        return target_text not in cell_text
    if operator == Filter2DOperatorType.STARTS_WITH:
        return cell_text.startswith(target_text)
    if operator == Filter2DOperatorType.ENDS_WITH:
        return cell_text.endswith(target_text)
    return False


def _convert_item(value: Any, direction: ConvertDirectionType, ignore_error: bool) -> Any:
    """递归转换列表项类型。"""
    if isinstance(value, list):
        return [_convert_item(item, direction, ignore_error) for item in value]
    if direction == ConvertDirectionType.STR_TO_NUMBER:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        number = _to_number(value)
        if number is not None:
            return number
        if ignore_error:
            return value
        raise ValueError(f"列表项 [{value}] 无法转换为数值!")
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    return value


class ListProcessExtend:
    """列表拓展处理流程类（一维/二维列表高级操作）。"""

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("filtered_list_data", types="List")],
    )
    def filter_empty_items(list_data: list, only_trim_trailing: bool = False):
        """
        过滤空值项

        一维列表：移除 None、空串、纯空白串；
        二维列表：移除整行均为空值的行。
        only_trim_trailing=True 时仅移除末尾连续的空值（项/行）。
        """
        is_2d = len(list_data) > 0 and isinstance(list_data[0], list)
        if is_2d:
            rows = list_data
            if only_trim_trailing:
                last = len(rows)
                while last > 0 and all(_is_empty_value(cell) for cell in rows[last - 1]):
                    last -= 1
                return [row for row in rows[:last] if any(not _is_empty_value(cell) for cell in row)]
            return [row for row in rows if any(not _is_empty_value(cell) for cell in row)]
        if only_trim_trailing:
            last = len(list_data)
            while last > 0 and _is_empty_value(list_data[last - 1]):
                last -= 1
            return [item for item in list_data[:last] if not _is_empty_value(item)]
        return [item for item in list_data if not _is_empty_value(item)]

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("stripped_list_data", types="List")],
    )
    def strip_text_items(list_data: list):
        """
        删除文本项两端空格

        递归处理列表中的所有字符串项，去除两端空格，返回新列表。
        """
        return _strip_items_deep(list_data)

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("sum_value", types="Float")],
    )
    def get_list_sum(list_data: list):
        """
        列表求和

        对列表中所有可转换为数值的项求和（数字字符串自动参与计算）。
        """
        return float(sum(_iter_numbers(list_data)))

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("average_value", types="Float")],
    )
    def get_list_average(list_data: list):
        """
        获取列表平均值

        计算列表中所有可转换为数值的项的平均值（数字字符串自动参与计算）。
        """
        numbers = _iter_numbers(list_data)
        return float(sum(numbers) / len(numbers))

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("extremum_value", types="Float")],
    )
    def get_list_extremum(list_data: list, extremum_type: ExtremumType = ExtremumType.MAX):
        """
        获取列表最值

        获取列表中所有数值的最大值或最小值（数字字符串自动参与计算）。
        """
        numbers = _iter_numbers(list_data)
        return float(max(numbers) if extremum_type == ExtremumType.MAX else min(numbers))

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("flattened_list_data", types="List")],
    )
    def flatten_list(list_data: list):
        """
        多维列表转一维列表

        将任意层级嵌套的列表展开为一维列表，如 [[1,2],[3,4]] 转成 [1,2,3,4]。
        """
        return _flatten_deep(list_data)

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("column_count", types="Int"),
        ],
        outputList=[atomicMg.param("reshaped_list_data", types="List")],
    )
    def reshape_list_to_2d(list_data: list, column_count: int = 1):
        """
        一维列表转二维列表

        将一维列表按固定列数转换为二维列表，如 [1,2,3,4,5,6] 按每行 2 列转成 [[1,2],[3,4],[5,6]]，
        不足一行的部分用 None 补齐。
        """
        column_count = int(column_count)
        if column_count <= 0:
            raise ValueError("列数必须为正整数!")
        result = []
        for start in range(0, len(list_data), column_count):
            chunk = list(list_data[start : start + column_count])
            while len(chunk) < column_count:
                chunk.append(None)
            result.append(chunk)
        return result

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("transposed_list_data", types="List")],
    )
    def transpose_list(list_data: list):
        """
        列表转置

        将二维列表行列互换，如 [[1,2],[3,4]] 转成 [[1,3],[2,4]]，行长度不齐时用 None 补齐。
        """
        if not list_data:
            return []
        return [list(row) for row in zip_longest(*list_data, fillvalue=None)]

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data_1", types="Any"),
            atomicMg.param("list_data_2", types="Any"),
            atomicMg.param(
                "as_dict",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
            ),
            atomicMg.param("fill_value", types="Any", required=False),
        ],
        outputList=[atomicMg.param("assembled_object", types="Any")],
    )
    def zip_two_lists(list_data_1: list, list_data_2: list, as_dict: bool = False, fill_value: Any = None):
        """
        列表组装

        将两个列表逐项对应组装为二维列表（[[a1,b1],[a2,b2]]）或字典（{a1:b1,a2:b2}）。
        长度不一致时用 fill_value 补齐。
        """
        length = max(len(list_data_1), len(list_data_2))
        list_1 = list(list_data_1) + [fill_value] * (length - len(list_data_1))
        list_2 = list(list_data_2) + [fill_value] * (length - len(list_data_2))
        if as_dict:
            result = {}
            for key, value in zip(list_1, list_2):
                if not isinstance(key, (str, int, float, bool, tuple)) and key is not None:
                    key = str(key)
                result[key] = value
            return result
        return [[a, b] for a, b in zip(list_1, list_2)]

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("dict_data", types="Dict")],
    )
    def list_to_dict_keys(list_data: list):
        """
        列表项转字典键

        将列表每一项作为字典的键，字典的值为 None。
        """
        result = {}
        for item in list_data:
            key = item
            if not isinstance(key, (str, int, float, bool, tuple)) and key is not None:
                key = str(key)
            result[key] = None
        return result

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("find_text", types="Str"),
            atomicMg.param("replace_text", types="Str"),
            atomicMg.param(
                "use_regex",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
            ),
        ],
        outputList=[atomicMg.param("replaced_list_data", types="List")],
    )
    def replace_text_in_list(
        list_data: list,
        find_text: str = "",
        replace_text: str = "",
        use_regex: bool = False,
    ):
        """
        多维列表文本替换

        递归替换列表（含多维）中所有字符串项的文本，支持正则表达式。
        """
        if not find_text:
            raise ValueError("查找内容不能为空!")
        if use_regex:
            pattern = re.compile(find_text)
        else:
            pattern = None

        def _replace(value: Any) -> Any:
            if isinstance(value, list):
                return [_replace(item) for item in value]
            if isinstance(value, str):
                return pattern.sub(replace_text, value) if pattern else value.replace(find_text, replace_text)
            return value

        return _replace(list_data)

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("converted_list_data", types="List")],
    )
    def convert_item_type(
        list_data: list,
        convert_direction: ConvertDirectionType = ConvertDirectionType.STR_TO_NUMBER,
        ignore_error: bool = True,
    ):
        """
        列表项类型转换

        将列表（含多维）中的字符串项与数值项互相转换；
        ignore_error=True 时跳过无法转换的项，否则报错。
        """
        return _convert_item(list_data, convert_direction, ignore_error)

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("start_index", types="Int"),
            atomicMg.param("end_index", types="Int"),
        ],
        outputList=[atomicMg.param("sliced_list_data", types="List")],
    )
    def slice_list(list_data: list, start_index: int = 0, end_index: int = -1):
        """
        截取列表项

        从列表中截取 [起始位置, 结束位置) 的项，支持负索引（-1 表示最后一项），返回新列表。
        """
        return list(list_data[int(start_index) : int(end_index)])

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("copied_list_data", types="List")],
    )
    def copy_list(list_data: list):
        """
        复制列表

        深拷贝列表，修改新列表不会影响原列表（含多维列表）。
        """
        return copy.deepcopy(list_data)

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("text", types="Str"),
        ],
        outputList=[
            atomicMg.param("contains_result", types="Any"),
            atomicMg.param("matched_items", types="List"),
            atomicMg.param("matched_indexes", types="List"),
        ],
    )
    def check_item_contains(
        list_data: list,
        text: str = "",
        contain_mode: ContainModeType = ContainModeType.ITEM_CONTAINS_TEXT,
    ):
        """
        列表项判断包含

        判断列表中是否有任意一项与文本存在包含关系：
        列表项包含文本（项中包含该字符串）或文本包含列表项（该字符串包含项）。
        返回判断结果、符合条件的项列表和索引列表。
        """
        matched_items = []
        matched_indexes = []
        if contain_mode == ContainModeType.ITEM_CONTAINS_TEXT:
            for index, item in enumerate(list_data):
                if text in _cell_str(item):
                    matched_items.append(item)
                    matched_indexes.append(index)
        else:
            for index, item in enumerate(list_data):
                if _cell_str(item) and _cell_str(item) in text:
                    matched_items.append(item)
                    matched_indexes.append(index)
        return len(matched_items) > 0, matched_items, matched_indexes

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("value", types="Any"),
        ],
        outputList=[
            atomicMg.param("item_count", types="Int"),
            atomicMg.param("position_list", types="List"),
        ],
    )
    def count_list_item(list_data: list, value: Any = ""):
        """
        列表计数

        找出一个项在列表中出现的次数和出现时的所有下标（值相等或字符串形式相等均计为匹配）。
        """
        position_list = []
        for index, item in enumerate(list_data):
            if item == value or _cell_str(item) == _cell_str(value):
                position_list.append(index)
        return len(position_list), position_list

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("column_index", types="Any"),
            atomicMg.param("condition_value", types="Any"),
        ],
        outputList=[atomicMg.param("filtered_2d_list", types="List")],
    )
    def filter_2d_list(
        list_data: list,
        column_index: Any = 0,
        operator: Filter2DOperatorType = Filter2DOperatorType.EQUAL,
        condition_value: Any = "",
    ):
        """
        筛选二维列表

        按指定列的条件筛选行（支持等于/大于/包含/为空等操作，数值自动感知），
        返回筛选后的二维列表。
        """
        col = int(column_index)
        return [
            row
            for row in list_data
            if isinstance(row, list)
            and _norm_index(col, len(row)) is not None
            and _match_condition(row[col], operator, condition_value)
        ]

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("column_index", types="Any"),
        ],
        outputList=[atomicMg.param("sorted_2d_list", types="List")],
    )
    def sort_2d_list(list_data: list, column_index: Any = 0, sort_method: SortMethodType = SortMethodType.ASC):
        """
        二维列表排序

        将二维列表的行按指定列排序（数值列按数值排，否则按文本排），支持负索引。
        """
        col = int(column_index)
        rows = list(list_data)

        def sort_key(row: list):
            if not isinstance(row, list) or _norm_index(col, len(row)) is None:
                return ""
            cell = row[col]
            number = _to_number(cell)
            return number if number is not None else _cell_str(cell)

        try:
            return sorted(rows, key=sort_key, reverse=(sort_method == SortMethodType.DESC))
        except TypeError:
            return sorted(rows, key=lambda row: _cell_str(sort_key(row)), reverse=(sort_method == SortMethodType.DESC))

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("column_index", types="Any"),
        ],
        outputList=[atomicMg.param("unique_2d_list", types="List")],
    )
    def unique_2d_list_by_column(list_data: list, column_index: Any = 0):
        """
        二维列表按列去重

        将指定列内容相同的行视为重复行，仅保留重复行中的第一行，保持原有顺序。
        """
        col = int(column_index)
        seen = set()
        result = []
        for row in list_data:
            if not isinstance(row, list):
                result.append(row)
                continue
            key = _cell_str(row[col]) if _norm_index(col, len(row)) is not None else ""
            if key not in seen:
                seen.add(key)
                result.append(row)
        return result

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("column_index", types="Any"),
        ],
        outputList=[atomicMg.param("grouped_list_data", types="List")],
    )
    def group_2d_list(list_data: list, column_index: Any = 0):
        """
        二维列表分组

        将二维列表按指定列的内容分组，返回三维列表（每组为该列值相同的所有行，按首次出现顺序）。
        """
        col = int(column_index)
        groups = {}
        for row in list_data:
            key = _cell_str(row[col]) if isinstance(row, list) and _norm_index(col, len(row)) is not None else ""
            groups.setdefault(key, []).append(row)
        return list(groups.values())

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("insert_position", types="Int"),
            atomicMg.param("column_data", types="Any"),
        ],
        outputList=[atomicMg.param("added_2d_list", types="List")],
    )
    def add_column_to_2d_list(list_data: list, insert_position: int = 0, column_data: list = None):
        """
        二维列表添加列

        在指定列索引前插入一列（列数据为一维列表，行数不足时用 None 补齐），支持负索引。
        """
        if column_data is None:
            column_data = []
        if not isinstance(column_data, list):
            column_data = [column_data]
        length = max(len(list_data), len(column_data))
        rows = list(list_data) + [[] for _ in range(length - len(list_data))]
        values = list(column_data) + [None] * (length - len(column_data))
        result = []
        for row, value in zip(rows, values):
            new_row = list(row)
            pos = int(insert_position)
            if pos < 0:
                pos += len(new_row) + 1
                if pos < 0:
                    raise ValueError("插入位置索引超出范围!")
            new_row.insert(pos, value)
            result.append(new_row)
        return result

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("column_indexes", types="Str"),
        ],
        outputList=[atomicMg.param("removed_2d_list", types="List")],
    )
    def remove_columns_from_2d_list(list_data: list, column_indexes: str = ""):
        """
        删除二维列表指定列

        删除每行中指定的一列或多列（列索引逗号分隔，如 "0,2"，支持负索引），返回新列表。
        """
        indexes = _parse_indexes(column_indexes)
        # 正索引归一结果与行无关, 提到循环外只算一次; 负索引依赖行长度, 逐行换算
        positive_remove = {idx for idx in indexes if idx >= 0}
        negative_indexes = [idx for idx in indexes if idx < 0]
        result = []
        for row in list_data:
            if not isinstance(row, list):
                result.append(row)
                continue
            remove_set = positive_remove
            if negative_indexes:
                remove_set = positive_remove | {_norm_index(idx, len(row)) for idx in negative_indexes}
            remove_set.discard(None)
            result.append([cell for i, cell in enumerate(row) if i not in remove_set])
        return result

    @staticmethod
    @atomicMg.atomic(
        "ListProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
            atomicMg.param("column_indexes", types="Str"),
        ],
        outputList=[atomicMg.param("selected_2d_list", types="List")],
    )
    def get_columns_from_2d_list(list_data: list, column_indexes: str = ""):
        """
        获取二维列表指定列

        获取一列或多列数据（列索引逗号分隔，如 "0,2"，支持负索引）；
        只要一列时返回一维列表，多列时返回二维列表，缺失该列的行将被跳过。
        """
        indexes = _parse_indexes(column_indexes)
        if len(indexes) == 1:
            col = indexes[0]
            return [row[col] for row in list_data if isinstance(row, list) and _norm_index(col, len(row)) is not None]
        result = []
        for row in list_data:
            if not isinstance(row, list):
                continue
            picked = []
            for idx in indexes:
                norm = _norm_index(idx, len(row))
                if norm is not None:
                    picked.append(row[norm])
            if picked:
                result.append(picked)
        return result
