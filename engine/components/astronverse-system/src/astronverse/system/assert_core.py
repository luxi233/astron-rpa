"""断言操作: 条件断言、空值断言、文件/文件夹断言，断言失败时抛出异常中断流程"""

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.baseline.error.error import BizCode, ErrorCode
from astronverse.system import AssertEmptyMode, AssertOperator, AssertTargetType, ExistType
from astronverse.system.error import *

__all__ = ["Assert"]


def _to_num(value):
    try:
        if isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare(value1, operator: AssertOperator, value2) -> bool:
    n1, n2 = _to_num(value1), _to_num(value2)
    if operator == AssertOperator.CONTAINS:
        return str(value2) in str(value1)
    if operator == AssertOperator.NOT_CONTAINS:
        return str(value2) not in str(value1)
    if operator == AssertOperator.EQ:
        if value1 == value2:
            return True
        return n1 is not None and n2 is not None and n1 == n2
    if operator == AssertOperator.NEQ:
        return not _compare(value1, AssertOperator.EQ, value2)
    # 大小比较: 数值优先, 否则按字符串比较
    if n1 is not None and n2 is not None:
        a, b = n1, n2
    else:
        a, b = str(value1), str(value2)
    if operator == AssertOperator.GT:
        return a > b
    if operator == AssertOperator.GTE:
        return a >= b
    if operator == AssertOperator.LT:
        return a < b
    if operator == AssertOperator.LTE:
        return a <= b
    return False


def _is_empty(value, include_whitespace: bool) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "" if include_whitespace else value == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _raise_assert_fail(error_message: str, default_detail: str):
    if error_message:
        raise BaseException(ErrorCode(BizCode.LocalErr, error_message), default_detail)
    raise BaseException(ASSERT_FAILED_FORMAT, default_detail)


class Assert:
    @staticmethod
    @atomicMg.atomic(
        "Assert",
        inputList=[
            atomicMg.param(
                "value1",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("operator", types="Str"),
            atomicMg.param(
                "value2",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "error_message",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
        ],
    )
    def assert_condition(
        value1=None, operator: AssertOperator = AssertOperator.EQ, value2=None, error_message: str = ""
    ) -> None:
        """
        条件断言(断言失败时抛出异常并中断流程)
        :param value1: 对象1
        :param operator: 运算符(等于/不等于/大于/大于等于/小于/小于等于/包含/不包含)
        :param value2: 对象2
        :param error_message: 断言失败时的自定义错误信息(不填使用默认信息)
        """
        try:
            passed = _compare(value1, operator, value2)
            if not passed:
                op_text = operator.value
                _raise_assert_fail(
                    error_message,
                    "条件断言失败: {} {} {}".format(value1, op_text, value2),
                )
        except BaseException:
            raise

    @staticmethod
    @atomicMg.atomic(
        "Assert",
        inputList=[
            atomicMg.param(
                "value",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("assert_mode", types="Str"),
            atomicMg.param("include_whitespace", types="Bool", required=False),
            atomicMg.param(
                "error_message",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
        ],
    )
    def assert_empty(
        value=None,
        assert_mode: AssertEmptyMode = AssertEmptyMode.NOT_EMPTY,
        include_whitespace: bool = True,
        error_message: str = "",
    ) -> None:
        """
        空值断言(断言失败时抛出异常并中断流程)
        :param value: 待判断的值(支持任意类型)
        :param assert_mode: 断言模式(断言不为空/断言为空)
        :param include_whitespace: 空白字符串视为空(如"  ")
        :param error_message: 断言失败时的自定义错误信息(不填使用默认信息)
        """
        is_empty = _is_empty(value, include_whitespace)
        if assert_mode == AssertEmptyMode.EMPTY:
            if not is_empty:
                _raise_assert_fail(error_message, "空值断言失败: 值不为空({})".format(value))
        else:
            if is_empty:
                _raise_assert_fail(error_message, "空值断言失败: 值为空")

    @staticmethod
    @atomicMg.atomic(
        "Assert",
        inputList=[
            atomicMg.param(
                "path",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("target_type", types="Str"),
            atomicMg.param("exist_mode", types="Str"),
            atomicMg.param(
                "error_message",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
        ],
    )
    def assert_file_folder(
        path: str = "",
        target_type: AssertTargetType = AssertTargetType.ANY,
        exist_mode: ExistType = ExistType.EXIST,
        error_message: str = "",
    ) -> None:
        """
        文件/文件夹断言(断言失败时抛出异常并中断流程)
        :param path: 文件/文件夹路径
        :param target_type: 目标类型(文件/文件夹/文件或文件夹)
        :param exist_mode: 断言模式(存在/不存在)
        :param error_message: 断言失败时的自定义错误信息(不填使用默认信息)
        """
        import os

        try:
            if target_type == AssertTargetType.FILE:
                exists = os.path.isfile(path)
                type_text = "文件"
            elif target_type == AssertTargetType.FOLDER:
                exists = os.path.isdir(path)
                type_text = "文件夹"
            else:
                exists = os.path.exists(path)
                type_text = "文件/文件夹"
            if exist_mode == ExistType.EXIST and not exists:
                _raise_assert_fail(error_message, "{}断言失败: {}不存在".format(type_text, path))
            if exist_mode == ExistType.NOT_EXIST and exists:
                _raise_assert_fail(error_message, "{}断言失败: {}已存在".format(type_text, path))
        except BaseException:
            raise
