import re
from enum import Enum

from astronverse.actionlib.types import Any, Bool, Dict, List


class CondType(Enum):
    C_TRUE = "true"
    C_FALSE = "false"
    C_EMPTY = "empty"
    C_NOT_EMPTY = "notempty"
    C_GT = ">"
    C_LT = "<"
    C_GE = ">="
    C_LE = "<="
    C_IN = "in"
    C_NOT_IN = "notin"
    C_EQ = "=="
    C_NE = "!="
    C_IS_NONE = "isnone"
    C_NOT_NONE = "notnone"
    C_EMPTY_STR = "emptystr"
    C_NOT_EMPTY_STR = "notemptystr"
    C_STARTSWITH = "startswith"
    C_NOT_STARTSWITH = "notstartswith"
    C_ENDSWITH = "endswith"
    C_NOT_ENDSWITH = "notendswith"


def str_is_integer(s):
    return bool(re.match(r"^-?\d+$", s))


def str_is_float(s):
    return bool(re.match(r"^-?\d*\.\d+$", s))


def str_is_list(s):
    return bool(s.startswith("[") and s.endswith("]"))


def str_is_dict(s):
    return bool(s.startswith("{") and s.endswith("}"))


def consequence_multi(*args, **kwargs):
    """
    多条件判断：将任意多组(args1_N, condition_N, args2_N)按 且/或 组合
    - 新格式: 关键字参数 args1_1/condition_1/args2_1, args1_2/... 数量不限(N>=1连续编号)
    - 旧格式兼容: 位置参数按 (args1_1, condition_1, args2_1, ..., relation) 顺序
    - relation: "and"=符合以下全部条件, "or"=符合以下任意条件
    """
    relation = str(kwargs.get("relation", "and"))

    # 收集 kwargs 中的任意数量条件组
    groups = {}
    for k, v in kwargs.items():
        m = re.match(r"^(args1|condition|args2)_(\d+)$", k)
        if m:
            groups.setdefault(int(m.group(2)), {})[m.group(1)] = v

    # 旧格式位置参数兜底(生成代码为关键字调用, 通常不走此分支)
    if not groups and args:
        names = ("args1", "condition", "args2")
        for i in range(0, len(args) - 1, 3):
            n = i // 3 + 1
            for j, name in enumerate(names):
                if i + j < len(args):
                    groups.setdefault(n, {})[name] = args[i + j]

    results = []
    for n in sorted(groups):
        g = groups[n]
        a1 = g.get("args1")
        cond = str(g.get("condition", "true"))
        # 未填行跳过: 空字符串=前端默认未填; None 仅在 None 判断类操作符下有意义,
        # 其余操作符(如 >)直接比较 None 会 TypeError, 视为未填跳过(与旧版一致)
        if isinstance(a1, str) and a1.strip() == "":
            continue
        if a1 is None and cond not in (
            CondType.C_IS_NONE.value,
            CondType.C_NOT_NONE.value,
            CondType.C_EMPTY.value,
            CondType.C_NOT_EMPTY.value,
            CondType.C_EMPTY_STR.value,
            CondType.C_NOT_EMPTY_STR.value,
        ):
            continue
        results.append(consequence(a1, cond, g.get("args2")))

    if not results:
        return True
    if relation == "or":
        return any(results)
    return all(results)


def consequence(args1: Any, condition: str, args2: Any = None, **kwargs):
    match condition:
        case CondType.C_TRUE.value | CondType.C_FALSE.value:
            res = bool(Bool.__validate__("arg1", args1))
            if condition == CondType.C_TRUE.value:
                return res
            else:
                return not res
        case CondType.C_EMPTY.value | CondType.C_NOT_EMPTY.value:
            if args1 is None:
                res = True
            elif isinstance(args1, str):
                res = not bool(args1.strip())
            else:
                res = False
            if condition == CondType.C_EMPTY.value:
                return res
            else:
                return not res
        case CondType.C_IS_NONE.value | CondType.C_NOT_NONE.value:
            if condition == CondType.C_IS_NONE.value:
                return args1 is None
            return args1 is not None
        case CondType.C_EMPTY_STR.value | CondType.C_NOT_EMPTY_STR.value:
            # 严格字符串判断: None 不算空字符串(区别于 empty 的宽松语义)
            res = isinstance(args1, str) and args1 == ""
            if condition == CondType.C_EMPTY_STR.value:
                return res
            return not res
        case (
            CondType.C_STARTSWITH.value
            | CondType.C_NOT_STARTSWITH.value
            | CondType.C_ENDSWITH.value
            | CondType.C_NOT_ENDSWITH.value
        ):
            s1, s2 = str(args1), str(args2)
            if condition in (CondType.C_STARTSWITH.value, CondType.C_NOT_STARTSWITH.value):
                res = s1.startswith(s2)
            else:
                res = s1.endswith(s2)
            if condition in (CondType.C_STARTSWITH.value, CondType.C_ENDSWITH.value):
                return res
            return not res
        case CondType.C_GT.value | CondType.C_LT.value | CondType.C_GE.value | CondType.C_LE.value:
            if isinstance(args1, str) and (str_is_integer(args1) or str_is_float(args1)):
                if str_is_integer(args1):
                    args1 = int(args1)
                else:
                    args1 = float(args1)
            elif isinstance(args1, (float, int)):
                pass
            else:
                args1 = str(args1)

            if isinstance(args2, str) and (str_is_integer(args2) or str_is_float(args2)):
                if str_is_integer(args2):
                    args2 = int(args2)
                else:
                    args2 = float(args2)
            elif isinstance(args2, (float, int)):
                pass
            else:
                args2 = str(args2)

            if condition == CondType.C_GT.value:
                return args1 > args2
            elif condition == CondType.C_LT.value:
                return args1 < args2
            elif condition == CondType.C_GE.value:
                return args1 >= args2
            elif condition == CondType.C_LE.value:
                return args1 <= args2
        case CondType.C_EQ.value | CondType.C_NE.value:
            args1_t = type(args1)
            args2_t = type(args2)
            if args1_t == args2_t:
                pass
            else:
                args1 = str(args1)
                args2 = str(args2)

            res = args1 == args2
            if condition == CondType.C_EQ.value:
                return res
            else:
                return not res
        case CondType.C_IN.value | CondType.C_NOT_IN.value:
            if isinstance(args1, str) and str_is_list(args1):
                args1 = list(List.__validate__("args1", args1))
            elif isinstance(args1, str) and str_is_dict(args1):
                args1 = dict(Dict.__validate__("args1", args1))
            else:
                pass

            if isinstance(args1, list):
                args1 = [str(x) for x in args1]

            if str(args2) in args1:
                res = True
            else:
                res = False

            if condition == CondType.C_IN.value:
                return res
            else:
                return not res
        case _:
            return False
