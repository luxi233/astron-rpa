"""字典处理相关类型定义模块"""

from typing import Any

from astronverse.actionlib import DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.dataprocess import NoKeyOptionType
from astronverse.dataprocess.error import INVALID_DICT_FORMAT_ERROR_FORMAT, BaseException


class DictProcess:
    """字典处理组件"""

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any", required=False),
        ],
        outputList=[atomicMg.param("created_new_dict_data", types="Dict")],
    )
    def create_new_dict(dict_data: dict):
        """
        创建一个新的字典
        """
        return dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
            atomicMg.param("dict_key", types="Any", required=False),
            atomicMg.param("value", types="Any", required=False),
        ],
        outputList=[atomicMg.param("inserted_dict_data", types="Dict")],
    )
    def set_value_to_dict(dict_data: dict, dict_key: Any, value: Any):
        """
        字典插入一项
        """
        # dict_key 为None时, 转换为空字符串
        if dict_key is None:
            dict_key = ""
        dict_data[dict_key] = value
        return dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
        ],
        outputList=[atomicMg.param("deleted_dict_data", types="Dict")],
    )
    def delete_value_from_dict(dict_data: dict, dict_key: str):
        """
        字典删除一项
        """
        if dict_key in dict_data:
            del dict_data[dict_key]
        return dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
            atomicMg.param(
                "default_value",
                dynamics=[
                    DynamicsItem(
                        key="$this.default_value.show",
                        expression="return $this.fail_option.value == '{}'".format(
                            NoKeyOptionType.RETURN_DEFAULT.value
                        ),
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("get_dict_value", types="Any")],
    )
    def get_value_from_dict(
        dict_data: dict,
        dict_key: str,
        fail_option: NoKeyOptionType = NoKeyOptionType.RAISE_ERROR,
        default_value: Any = "",
    ):
        """
        字典获取一项
        """
        if dict_data.get(dict_key) is not None:
            return dict_data[dict_key]
        else:
            if fail_option == NoKeyOptionType.RAISE_ERROR:
                raise ValueError("字典中不存在该键!")
            elif fail_option == NoKeyOptionType.RETURN_DEFAULT:
                return default_value

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
        ],
        outputList=[atomicMg.param("get_dict_keys", types="Dict")],
    )
    def get_keys_from_dict(dict_data: dict):
        """
        字典获取所有键
        """
        return list(dict_data.keys())

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
        ],
        outputList=[atomicMg.param("get_dict_values", types="Dict")],
    )
    def get_values_from_dict(dict_data: dict):
        """
        字典获取所有值
        """
        return list(dict_data.values())

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
            atomicMg.param("merge_dict_data", types="Any"),
        ],
        outputList=[atomicMg.param("merged_dict_data", types="Dict")],
    )
    def merge_dict(dict_data: dict, merge_dict_data: dict):
        """
        合并字典：将被合并字典的键值对更新到字典（同名键后者覆盖），就地修改
        """
        if not isinstance(dict_data, dict):
            raise BaseException(INVALID_DICT_FORMAT_ERROR_FORMAT, "目标字典必须是字典类型")
        if not isinstance(merge_dict_data, dict):
            raise BaseException(INVALID_DICT_FORMAT_ERROR_FORMAT, "被合并字典必须是字典类型")
        dict_data.update(merge_dict_data)
        return dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
        ],
        outputList=[atomicMg.param("cleared_dict_data", types="Dict")],
    )
    def clear_dict(dict_data: dict):
        """
        清空字典：清空全部键值对，就地修改
        """
        if not isinstance(dict_data, dict):
            raise BaseException(INVALID_DICT_FORMAT_ERROR_FORMAT, "目标必须是字典类型")
        dict_data.clear()
        return dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
        ],
        outputList=[atomicMg.param("stripped_keys_dict_data", types="Dict")],
    )
    def strip_dict_keys(dict_data: dict):
        """
        删除字典键两端空格：仅处理字符串键（非字符串键保持原样），就地重建
        """
        if not isinstance(dict_data, dict):
            raise BaseException(INVALID_DICT_FORMAT_ERROR_FORMAT, "目标必须是字典类型")
        new_dict = {}
        for k, v in dict_data.items():
            new_key = k.strip() if isinstance(k, str) else k
            new_dict[new_key] = v
        dict_data.clear()
        dict_data.update(new_dict)
        return dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
        ],
        outputList=[atomicMg.param("stripped_values_dict_data", types="Dict")],
    )
    def strip_dict_values(dict_data: dict):
        """
        删除字典值两端空格：仅处理字符串值（非字符串值保持原样），就地修改
        """
        if not isinstance(dict_data, dict):
            raise BaseException(INVALID_DICT_FORMAT_ERROR_FORMAT, "目标必须是字典类型")
        for k in dict_data:
            if isinstance(dict_data[k], str):
                dict_data[k] = dict_data[k].strip()
        return dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
            atomicMg.param("dict_key", types="Any"),
        ],
        outputList=[atomicMg.param("key_exist", types="Bool")],
    )
    def dict_key_exist(dict_data: dict, dict_key: Any):
        """
        判断字典中指定键是否存在，输出布尔值
        """
        if not isinstance(dict_data, dict):
            raise BaseException(INVALID_DICT_FORMAT_ERROR_FORMAT, "目标必须是字典类型")
        return dict_key in dict_data

    @staticmethod
    @atomicMg.atomic(
        "DictProcess",
        inputList=[
            atomicMg.param("dict_data", types="Any"),
            atomicMg.param("item_connect", types="Str", required=False),
            atomicMg.param("kv_connect", types="Str", required=False),
        ],
        outputList=[atomicMg.param("dict_text", types="Str")],
    )
    def dict_to_text(dict_data: dict, item_connect: str = "\n", kv_connect: str = ":"):
        """
        字典格式化为文本：按"键+键值连接符+值"生成每项，项之间用项连接符拼接
        """
        if not isinstance(dict_data, dict):
            raise BaseException(INVALID_DICT_FORMAT_ERROR_FORMAT, "目标必须是字典类型")
        return item_connect.join(f"{k}{kv_connect}{v}" for k, v in dict_data.items())
