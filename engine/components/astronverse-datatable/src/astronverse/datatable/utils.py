import os
from datetime import datetime

import openpyxl
from astronverse.baseline.error.error import BizCode, ErrorCode
from astronverse.datatable import ConditionType, FilterType
from astronverse.datatable.error import (
    COL_FORMAT_ERROR,
    DATAFRAME_EXPECTION,
    FORMULA_FORMAT_ERROR,
    ROW_FORMAT_ERROR,
)


def validate(row=1, col="A"):
    """
    验证行列格式
    :param row: 行号
    :param col: 列标
    """
    print(f"Validating row: {row}, col: {col}")
    try:
        row = int(row)
    except ValueError:
        pass
    if isinstance(col, str):
        if not (col.isalpha() and col.upper() >= "A"):
            raise DATAFRAME_EXPECTION(COL_FORMAT_ERROR.format(col), "列格式错误")
    if not isinstance(row, int) or row < 1:
        raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(row), "行格式错误")


def validate_row_param(row, name="行号"):
    """
    行号参数校验: 区分"未填写"与"填了0"两种情况, 给出精确报错
    (循环索引从0开始, 直接绑定到行号会在首次迭代得到0)
    :param row: 行号 (int/str)
    :param name: 参数中文名, 用于报错信息
    :return: 转换后的 int 行号
    """

    def _err(msg: str):
        # 每次构造新 ErrorCode, 规避模块级单例 .format() 原地污染模板的框架缺陷
        return DATAFRAME_EXPECTION(ErrorCode(BizCode.LocalErr, "参数有误: " + msg), "参数有误: " + msg)

    if row is None or row == "":
        raise _err(f"{name}不能为空")
    try:
        row_int = int(row)
    except (ValueError, TypeError):
        raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(row), f"{name}格式错误: {row}") from None
    if row_int < 1:
        raise _err(f"{name}从1开始, 当前为{row}(若绑定的是循环索引请+1)")
    return row_int


def validate_row(row):
    try:
        row = int(row)
    except (ValueError, TypeError):
        pass
    if isinstance(row, int):
        if row < 1:
            raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(row), "行格式错误")
    else:
        raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(row), "行格式错误")


def validate_col(col):
    if not isinstance(col, str):
        raise DATAFRAME_EXPECTION(COL_FORMAT_ERROR.format(col), "列格式错误")
    col = col.upper()
    if not (col.isalpha() and col >= "A"):
        raise DATAFRAME_EXPECTION(COL_FORMAT_ERROR.format(col), "列格式错误")


def validate_end_col(start_col, end_col):
    if end_col is None or end_col == "" or start_col is None or start_col == "":
        return
    start_index = col_to_index(start_col)
    end_index = col_to_index(end_col)
    if end_index < start_index:
        raise ValueError("结束列不能小于开始列")


def validate_end_row(start_row, end_row):
    try:
        start_row = int(start_row)
        end_row = int(end_row)
    except ValueError:
        raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(end_row), "行格式错误")
    if end_row < start_row:
        raise ValueError("结束行不能小于开始行")


def col_to_index(col="A") -> int:
    """将列标转换为索引"""
    try:
        col = int(col)
    except ValueError:
        pass
    if isinstance(col, int):
        if col < 1:
            raise DATAFRAME_EXPECTION(COL_FORMAT_ERROR.format(col), "列格式错误")
        return col
    else:
        col = col.upper()
        index = 0
        for i, char in enumerate(reversed(col)):
            index += (ord(char) - ord("A") + 1) * (26**i)
        return index


def resolve_negative_row(row) -> int:
    """
    行号标准化: 支持负数(-1表示最后一行, -2表示倒数第二行)
    :return: 1-based正数行号
    """
    from astronverse.datatable.datatable import PyxlWrapper

    row = int(row)
    if row == 0:
        raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(row), "行格式错误")
    if row < 0:
        actual = PyxlWrapper.get_max_row() + 1 + row
        if actual < 1:
            raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(row), "行格式错误")
        return actual
    return row


def normalize_end_row(end_row):
    """
    区域结束行归一化: None/''/'0'/0→最后一行, 负数→倒数(-1=最后一行), 正数原样
    (装饰器只转换显式传入的kwargs, 函数默认值与0兼容值在此统一处理)
    """
    from astronverse.datatable.datatable import PyxlWrapper

    if end_row is None or end_row in ("", 0, "0"):
        return PyxlWrapper.get_max_row()
    if isinstance(end_row, int) and end_row > 0:
        return end_row
    return resolve_negative_row(end_row)


def normalize_end_col(end_col):
    """
    区域结束列归一化: None/''/'0'/0→最后一列, 负数→倒数(-1=最后一列), 其余转字母列标
    """
    from astronverse.datatable.datatable import PyxlWrapper

    if end_col is None or end_col in ("", 0, "0"):
        return index_to_col(PyxlWrapper.get_max_column() - 1)
    converted = resolve_negative_col(end_col)
    if isinstance(converted, int):
        converted = index_to_col(converted - 1)
    return converted


def resolve_negative_col(col):
    """
    列号标准化: 支持'A'/1/-1(-1表示最后一列)
    :return: 正数int列号或原字母列标
    """
    from astronverse.datatable.datatable import PyxlWrapper

    try:
        c = int(col)
    except (ValueError, TypeError):
        return col
    if c == 0:
        raise DATAFRAME_EXPECTION(COL_FORMAT_ERROR.format(col), "列格式错误")
    if c < 0:
        actual = PyxlWrapper.get_max_column() + 1 + c
        if actual < 1:
            raise DATAFRAME_EXPECTION(COL_FORMAT_ERROR.format(col), "列格式错误")
        return actual
    return c


def is_batch_spec(value) -> bool:
    """判断是否为批量语法('1,3,5:7' / 'A:C,E')"""
    return isinstance(value, str) and ("," in value or ":" in value)


def _parse_number_segments(spec: str, resolver) -> list:
    """解析'1,3,5:7'格式为去重升序数字列表, 每段经resolver转换(支持负数)"""
    result = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            a, b = part.split(":", 1)
            start, end = resolver(a.strip()), resolver(b.strip())
            if start > end:
                start, end = end, start
            result.extend(range(start, end + 1))
        else:
            result.append(resolver(part))
    if not result:
        raise DATAFRAME_EXPECTION(ROW_FORMAT_ERROR.format(spec), "格式错误")
    return sorted(set(result))


def parse_row_numbers(row_spec) -> list:
    """解析行号: '1,3,5:7'或int, 支持负数(-1=最后一行), 返回1-based去重升序列表"""

    def resolver(v):
        return resolve_negative_row(v)

    if is_batch_spec(row_spec):
        return _parse_number_segments(row_spec, resolver)
    return [resolve_negative_row(row_spec)]


def parse_col_numbers(col_spec) -> list:
    """解析列号: 'A,C,E:G'或'1,3,5:7', 支持负数(-1=最后一列), 返回1-based索引去重升序列表"""

    def resolver(v):
        v = str(v).strip().upper()
        try:
            return resolve_negative_col(int(v))
        except ValueError:
            return col_to_index(v)

    if is_batch_spec(col_spec):
        return _parse_number_segments(col_spec, resolver)
    return [resolver(col_spec)]


def index_to_col(index=1) -> str:
    """将索引转换为列标"""
    col = ""
    index += 1  # 转换为1-based索引
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        col = chr(65 + remainder) + col
    return col


def validate_formula(formula: str):
    """
    验证公式格式
    :param formula: 公式字符串
    """
    if not isinstance(formula, str) or not formula.startswith("="):
        raise DATAFRAME_EXPECTION(FORMULA_FORMAT_ERROR.format(formula), "公式格式错误")


def filter_data(
    data: list,
    filter_type: FilterType,
    condition_type: ConditionType,
    condition_value: str,
    date_value: str,
    date_range: str,
    is_case_sensitive: bool,
) -> list:
    filtered_data = []
    if not data:
        return []
    if filter_type == FilterType.TABLE:  # 过滤表格数据
        for row in data:
            filtered_row = []
            for item in row:
                if value_check(
                    value=item,
                    condition_type=condition_type,
                    condition_value=condition_value,
                    date_value=date_value,
                    date_range=date_range,
                    is_case_sensitive=is_case_sensitive,
                ):
                    filtered_row.append(item)
            if filtered_row:
                filtered_data.append(filtered_row)
    else:
        for item in data:
            if value_check(
                value=item,
                condition_type=condition_type,
                condition_value=condition_value,
                date_value=date_value,
                date_range=date_range,
                is_case_sensitive=is_case_sensitive,
            ):
                if isinstance(item, datetime):
                    item = item.strftime("%Y-%m-%d %H:%M:%S")
                filtered_data.append(item)
    return filtered_data


def value_check(
    value, condition_type: ConditionType, condition_value: str, date_value, date_range, is_case_sensitive: bool
) -> bool:
    """过滤处理器"""
    val = value
    cond_val = condition_value

    # Handle case sensitivity for string operations
    if isinstance(val, str) and isinstance(cond_val, str) and not is_case_sensitive:
        val = val.lower()
        cond_val = cond_val.lower()

    if condition_type == ConditionType.EQUALS:
        return str(val) == str(cond_val)
    elif condition_type == ConditionType.NOT_EQUALS:
        return str(val) != str(cond_val)
    elif condition_type == ConditionType.GREATER_THAN:
        try:
            val_num = float(val)
            cond_val_num = float(cond_val)
            return val_num > cond_val_num
        except (ValueError, TypeError):
            return False
    elif condition_type == ConditionType.LESS_THAN:
        try:
            val_num = float(val)
            cond_val_num = float(cond_val)
            return val_num < cond_val_num
        except (ValueError, TypeError):
            return False
    elif condition_type == ConditionType.GREATER_THAN_OR_EQUAL:
        try:
            val_num = float(val)
            cond_val_num = float(cond_val)
            return val_num >= cond_val_num
        except (ValueError, TypeError):
            return False
    elif condition_type == ConditionType.LESS_THAN_OR_EQUAL:
        try:
            val_num = float(val)
            cond_val_num = float(cond_val)
            return val_num <= cond_val_num
        except (ValueError, TypeError):
            return False
    elif condition_type == ConditionType.CONTAINS:
        return str(val).find(str(cond_val)) != -1
    elif condition_type == ConditionType.NOT_CONTAINS:
        return str(val).find(str(cond_val)) == -1
    elif condition_type == ConditionType.IS_EMPTY:
        return val is None or val == ""
    elif condition_type == ConditionType.IS_NOT_EMPTY:
        return val is not None and val != ""
    elif condition_type == ConditionType.STARTS_WITH:
        return str(val).startswith(str(cond_val))
    elif condition_type == ConditionType.ENDS_WITH:
        return str(val).endswith(str(cond_val))
    elif condition_type == ConditionType.DATE_AFTER:
        try:
            val_date = val if isinstance(val, datetime) else datetime.strptime(val, "%Y-%m-%d")
            cond_date = datetime.strptime(date_value, "%Y-%m-%d")
            return val_date > cond_date
        except (ValueError, TypeError):
            return False
    elif condition_type == ConditionType.DATE_BEFORE:
        try:
            val_date = val if isinstance(val, datetime) else datetime.strptime(val, "%Y-%m-%d")
            cond_date = datetime.strptime(date_value, "%Y-%m-%d")
            return val_date < cond_date
        except (ValueError, TypeError):
            return False
    elif condition_type == ConditionType.DATE_BETWEEN:
        try:
            val_date = val if isinstance(val, datetime) else datetime.strptime(val, "%Y-%m-%d")
            start_date_str, end_date_str = date_range.split(",")
            start_date = datetime.strptime(start_date_str.strip(), "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str.strip(), "%Y-%m-%d")
            return start_date <= val_date <= end_date
        except (ValueError, TypeError):
            return False
    return False


def ensure_xlsx_file(file_path):
    # 如果文件不存在或不是合法xlsx，则新建一个
    if not os.path.exists(file_path) or not is_valid_xlsx(file_path):
        parent_dir = os.path.dirname(file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        wb = openpyxl.Workbook()
        wb.save(file_path)


def is_valid_xlsx(file_path):
    try:
        openpyxl.load_workbook(file_path)
        return True
    except Exception:
        return False
