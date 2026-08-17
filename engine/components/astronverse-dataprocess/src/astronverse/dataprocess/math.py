"""数学与数值处理相关功能。"""

import math
import re
from typing import Any

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.dataprocess import AddSubType, MathOperatorType, MathRoundType, NumberType
from astronverse.dataprocess.error import *


def _to_number(value):
    """将输入转换为int/float，无法转换时抛出异常"""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if re.match(r"^-?\d+$", text):
        return int(text)
    if re.match(r"^-?\d+\.\d+$", text):
        return float(text)
    raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "请输入整数或浮点数")


def random_number(
    start,
    end,
    number_type: NumberType = NumberType.INTEGER,
    size: int = 1,
) -> list:
    """随机数生成。

    返回指定范围与类型的随机数列表。
    """
    import numpy  # type: ignore

    if number_type == NumberType.INTEGER:
        return numpy.random.randint(start, end, size).tolist()
    if number_type == NumberType.FLOAT:
        return numpy.random.uniform(start, end, size).tolist()
    raise ValueError("不支持的 number_type")


class MathProcess:
    """数学处理原子能力集合。"""

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("size", types="Int", required=False)],
        outputList=[atomicMg.param("generated_random_numbers", types="Any")],
    )
    def generate_random_number(
        number_type: NumberType = NumberType.INTEGER,
        size: int = 1,
        start: float = 0,
        end: float = 101,
    ):
        """
        生成随机数，可以指定整数，小数
        """
        if start > end:
            raise BaseException(INVALID_NUMBER_RANGE_ERROR_FORMAT, "开始值必须小于结束值")
        res = random_number(number_type=number_type, start=start, end=end, size=size)
        return res[0] if len(res) == 1 else res

    @staticmethod
    @atomicMg.atomic("MathProcess", outputList=[atomicMg.param("rounding_number", types="Any")])
    def get_rounding_number(number: float, precision: int = 2):
        """
        四舍五入
        """
        if precision <= 0:
            return int(round(float(number), int(precision)))
        if float(number).is_integer():
            return int(round(float(number), int(precision)))
        return round(float(number), int(precision))

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        outputList=[atomicMg.param("self_calculation_number", types="Int")],
    )
    def self_calculation_number(number: int, add_sub: AddSubType = AddSubType.ADD, add_sub_number: int = 1):
        """
        自增自减
        """
        if add_sub == AddSubType.ADD:
            return number + add_sub_number
        if add_sub == AddSubType.SUB:
            return number - add_sub_number
        raise ValueError("不支持的加减类型")

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("raw_number", types="Any")],
        outputList=[atomicMg.param("absolute_number", types="Any")],
    )
    def get_absolute_number(raw_number: Any):
        """
        获取绝对值
        """
        if isinstance(raw_number, str):
            if re.match(r"^-?\d+$", raw_number):
                raw_number = int(raw_number)
            elif re.match(r"^-?\d+\.\d+$", raw_number):  # 浮点数
                raw_number = float(raw_number)
            else:
                raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "请输入整数或浮点数")
        return abs(raw_number)

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[
            atomicMg.param(
                "precision",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.precision.show",
                        expression=f"return $this.handle_method.value == '{MathRoundType.ROUND.value}'",
                    )
                ],
            )
        ],
        outputList=[atomicMg.param("calculation_number", types="Any")],
    )
    def calculate_expression(
        left: str = "",
        operator: MathOperatorType = MathOperatorType.ADD,
        right: str = "",
        handle_method: MathRoundType = MathRoundType.NONE,
        precision: int = 0,
    ):
        """
        表达式计算
        """
        if not left:
            left = "0"
        if not right:
            right = "0"
        try:
            calc_res = eval(str(left) + operator.value + str(right))
        except Exception as e:
            raise BaseException(
                INVALID_MATH_EXPRESSION_ERROR_FORMAT.format(e),
                str(left) + operator.value + str(right),
            )
        if handle_method == MathRoundType.ROUND:
            if precision <= 0:
                return int(round(float(calc_res), int(precision)))
            else:
                if float(calc_res).is_integer():
                    return int(round(float(calc_res), int(precision)))
                else:
                    return round(float(calc_res), int(precision))
        elif handle_method == MathRoundType.FLOOR:
            calc_res = math.floor(calc_res)
        elif handle_method == MathRoundType.CEIL:
            calc_res = math.ceil(calc_res)
        return calc_res

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Any")],
        outputList=[atomicMg.param("ceil_number", types="Int")],
    )
    def get_ceil(number):
        """
        大于取整(向上取整，如4.1→5、-4.9→-4)
        """
        return math.ceil(_to_number(number))

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Any")],
        outputList=[atomicMg.param("floor_number", types="Int")],
    )
    def get_floor(number):
        """
        小于取整(向下取整，如4.9→4、-4.1→-5)
        """
        return math.floor(_to_number(number))

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Any")],
        outputList=[atomicMg.param("trunc_number", types="Int")],
    )
    def get_trunc(number):
        """
        舍去取整(向零取整，如4.9→4、-4.9→-4)
        """
        return math.trunc(_to_number(number))

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[
            atomicMg.param("number1", types="Any"),
            atomicMg.param("number2", types="Any"),
            atomicMg.param("float_mode", types="Bool", required=False),
        ],
        outputList=[atomicMg.param("remainder", types="Any")],
    )
    def get_remainder(number1, number2, float_mode: bool = False):
        """
        取余(如7对2取余=1)
        :param number1: 被除数
        :param number2: 除数
        :param float_mode: 浮点数取余(结果符号跟随被除数，如-7对3取余=-1)
        """
        n1, n2 = _to_number(number1), _to_number(number2)
        if n2 == 0:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "除数不能为0")
        if float_mode:
            return math.fmod(n1, n2)
        if isinstance(n1, int) and isinstance(n2, int):
            return n1 % n2
        return math.fmod(n1, n2)

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number1", types="Any"), atomicMg.param("number2", types="Any")],
        outputList=[atomicMg.param("floor_div_number", types="Any")],
    )
    def get_floor_div(number1, number2):
        """
        取整除(商向下取整，如7除以2=3、-7除以2=-4)
        :param number1: 被除数
        :param number2: 除数
        """
        n1, n2 = _to_number(number1), _to_number(number2)
        if n2 == 0:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "除数不能为0")
        result = n1 // n2
        if isinstance(n1, float) or isinstance(n2, float):
            return float(result)
        return result

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number1", types="Int"), atomicMg.param("number2", types="Int")],
        outputList=[atomicMg.param("gcd_number", types="Int")],
    )
    def get_gcd(number1: int = 0, number2: int = 0):
        """
        获取公约数(最大公约数，如12和18的公约数=6)
        """
        n1, n2 = _to_number(number1), _to_number(number2)
        if not isinstance(n1, int) or not isinstance(n2, int):
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "公约数仅支持整数")
        return math.gcd(abs(n1), abs(n2))

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[
            atomicMg.param("number", types="Any"),
            atomicMg.param("base", types="Any", required=False),
        ],
        outputList=[atomicMg.param("log_number", types="Float")],
    )
    def get_log(number, base=0):
        """
        获取对数(不填底数时为自然对数)
        :param number: 真数
        :param base: 底数(不填为自然对数e)
        """
        n = _to_number(number)
        if n <= 0:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "真数必须大于0")
        if base:
            b = _to_number(base)
            if b <= 0 or b == 1:
                raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "底数必须大于0且不等于1")
            return math.log(n, b)
        return math.log(n)

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Any")],
        outputList=[atomicMg.param("log10_number", types="Float")],
    )
    def get_log10(number):
        """
        获取以10为底的对数
        """
        n = _to_number(number)
        if n <= 0:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "真数必须大于0")
        return math.log10(n)

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Any"), atomicMg.param("exponent", types="Any")],
        outputList=[atomicMg.param("power_number", types="Any")],
    )
    def get_power(number, exponent):
        """
        获取x的y次方(如2的10次方=1024)
        :param number: 底数x
        :param exponent: 指数y
        """
        return math.pow(_to_number(number), _to_number(exponent))

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Any")],
        outputList=[atomicMg.param("sqrt_number", types="Float")],
    )
    def get_sqrt(number):
        """
        获取平方根(如9的平方根=3)
        """
        n = _to_number(number)
        if n < 0:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "负数没有平方根")
        return math.sqrt(n)

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Any")],
        outputList=[atomicMg.param("exp_number", types="Float")],
    )
    def get_exp(number):
        """
        获取e的x次方(自然常数e约等于2.718)
        """
        return math.exp(_to_number(number))

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[atomicMg.param("number", types="Int")],
        outputList=[atomicMg.param("factorial_number", types="Int")],
    )
    def get_factorial(number: int = 0):
        """
        获取阶乘(如5的阶乘=120)
        """
        n = _to_number(number)
        if not isinstance(n, int) or n < 0:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "阶乘仅支持非负整数")
        return math.factorial(n)

    @staticmethod
    @atomicMg.atomic(
        "MathProcess",
        inputList=[
            atomicMg.param(
                "data",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            )
        ],
        outputList=[atomicMg.param("random_item", types="Any")],
    )
    def get_random_item(data=None):
        """
        获取随机元素(从列表或字符串中随机取一个)
        :param data: 列表(如['a','b','c'])或字符串(如'abc')
        """
        import random

        if data is None or (isinstance(data, (str, list, tuple)) and len(data) == 0):
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "待随机的列表或字符串不能为空")
        return random.choice(data)
