"""数据转换处理模块"""

import ast
import json
from typing import Any

from astronverse.actionlib.atomic import atomicMg
from astronverse.dataprocess import JSONConvertType, StringConvertType


class DataConvertProcess:
    """数据转换处理组件"""

    @staticmethod
    @atomicMg.atomic(
        "DataConvertProcess",
        outputList=[atomicMg.param("json_convert_data", types="Any")],
    )
    def json_convertor(input_data: Any, convert_type: JSONConvertType = JSONConvertType.JSON_TO_STR):
        """
        JSON数据类型转换
        """
        if convert_type == JSONConvertType.JSON_TO_STR:
            return json.dumps(input_data, ensure_ascii=False)
        elif convert_type == JSONConvertType.STR_TO_JSON:
            return json.loads(input_data)

    @staticmethod
    @atomicMg.atomic(
        "DataConvertProcess",
        outputList=[atomicMg.param("other_convert_str", types="Any")],
    )
    def other_to_str(input_data: Any):
        """
        其他数据类型强转为字符串
        """
        try:
            return str(input_data)
        except Exception:
            raise ValueError("数据类型不支持强转str!")

    @staticmethod
    @atomicMg.atomic(
        "DataConvertProcess",
        outputList=[atomicMg.param("str_convert_other", types="Any")],
    )
    def str_to_other(input_data: Any, convert_type: StringConvertType = StringConvertType.STR_TO_INT):
        """
        字符串转其他数据类型
        """
        try:
            if convert_type == StringConvertType.STR_TO_INT:
                return int(str(input_data).split(".")[0])
            elif convert_type == StringConvertType.STR_TO_FLOAT:
                return float(input_data)
            elif convert_type == StringConvertType.STR_TO_BOOL:
                if input_data in ["1", "True", "true"]:
                    return True
                elif input_data in ["0", "False", "false"]:
                    return False
                else:
                    return bool(input_data)
            elif convert_type in [
                StringConvertType.STR_TO_LIST,
                StringConvertType.STR_TO_TUPLE,
                StringConvertType.STR_TO_DICT,
            ]:
                return ast.literal_eval(input_data)
        except Exception:
            raise Exception("请输入正确的待转换目标字符串")

    @staticmethod
    @atomicMg.atomic(
        "DataConvertProcess",
        inputList=[
            atomicMg.param("input_data", types="Any"),
            atomicMg.param("extract_key", types="Str"),
        ],
        outputList=[atomicMg.param("extracted_values", types="List")],
    )
    def extract_json_key(input_data: Any, extract_key: str):
        """
        递归提取JSON数据中指定键的所有值：遍历嵌套字典/列表，输入为字符串时先尝试按JSON解析，未匹配返回空列表
        """
        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)
            except (json.JSONDecodeError, ValueError):
                raise ValueError("输入字符串不是有效的JSON文本!")
        values = []

        def _walk(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k == extract_key:
                        values.append(v)
                    _walk(v)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        _walk(input_data)
        return values
