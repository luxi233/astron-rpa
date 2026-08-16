from enum import Enum


class BaseOperateType(Enum):
    CELL = "cell"  # 单元格操作
    ROW = "row"  # 行操作
    COLUMN = "column"  # 列操作
    AREA = "area"  # 区域操作


ReadType = BaseOperateType
WriteType = BaseOperateType
CopyType = BaseOperateType
PasteType = BaseOperateType
DeleteType = BaseOperateType


class WriteMode(Enum):
    OVERWRITE = "overwrite"  # 覆盖写入
    INSERT = "insert"  # 插入写入
    APPEND = "append"  # 追加写入


class CellInsertShift(Enum):
    """单元格插入，指定插入时其他单元格的移动方向"""

    DOWN = "down"  # 向下移动
    RIGHT = "right"  # 向右移动


class RowInsertShift(Enum):
    """行插入，指定插入到指定行的上方还是下方"""

    UP = "up"  # 向上插入
    DOWN = "down"  # 向下插入


class ColumnInsertShift(Enum):
    """列插入，指定插入到指定列的左侧还是右侧"""

    LEFT = "left"  # 向左插入
    RIGHT = "right"  # 向右插入


class AppendShift(Enum):
    ROW = "row"  # 行追加
    COLUMN = "column"  # 列追加


class InsertType(Enum):
    ROW = "row"  # 插入行
    COLUMN = "column"  # 插入列


class PasteValueType(Enum):
    VALUE = "value"  # 仅粘贴值
    FORMULA = "formula"  # 仅粘贴公式


class DeleteCellMove(Enum):
    LEFT = "left"  # 向左移动
    UP = "up"  # 向上移动
    NOT_MOVE = "not"  # 不移动


class SortOrder(Enum):
    ASCENDING = "ascending"  # 升序
    DESCENDING = "descending"  # 降序


class ExportFileType(Enum):
    XLSX = "xlsx"  # Excel 文件 .xlsx
    XLS = "xls"  # Excel 文件 .xls
    CSV = "csv"  # CSV 文件 .csv
    JSON = "json"  # JSON 文件 .json


class FileEncodingType(Enum):
    AUTO = "auto"  # 自动识别
    ANSI = "ansi"  # ANSI(GBK)
    UTF8 = "utf8"  # UTF-8
    UTF8_BOM = "utf8_bom"  # 带有BOM的UTF-8


class CsvWriteType(Enum):
    OVERWRITE = "overwrite"  # 覆盖写入
    APPEND = "append"  # 追加写入


class FilterType(Enum):
    ROW = "row"  # 按行过滤
    COLUMN = "column"  # 按列过滤
    TABLE = "table"  # 按表格过滤


class LoopType(Enum):
    ROW = "row"  # 按行遍历
    COLUMN = "column"  # 按列遍历
    AREA = "area"  # 按区域遍历


class ConditionType(Enum):
    EQUALS = "equals"  # 等于
    NOT_EQUALS = "not_equals"  # 不等于
    GREATER_THAN = "greater_than"  # 大于
    LESS_THAN = "less_than"  # 小于
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"  # 大于等于
    LESS_THAN_OR_EQUAL = "less_than_or_equal"  # 小于等于
    CONTAINS = "contains"  # 包含
    NOT_CONTAINS = "not_contains"  # 不包含
    IS_EMPTY = "is_empty"  # 为空
    IS_NOT_EMPTY = "is_not_empty"  # 不为空
    STARTS_WITH = "starts_with"  # 以...开头
    ENDS_WITH = "ends_with"  # 以...结尾
    DATE_BEFORE = "date_before"  # 日期在...之前
    DATE_AFTER = "date_after"  # 日期在...之后
    DATE_BETWEEN = "date_between"  # 日期在...之间


class FindType(Enum):
    COLUMN = "column"  # 按列查找
    TABLE = "table"  # 按表格查找


class ColumnInfoGetType(Enum):
    """获取列信息方式"""

    BY_COL = "byCol"  # 根据列号获取列描述
    BY_TITLE = "byTitle"  # 根据列描述获取列号


class ValidateType(Enum):
    """数据验证类型"""

    WHOLE = "whole"  # 整数
    DECIMAL = "decimal"  # 小数
    LIST = "list"  # 列表
    DATE = "date"  # 日期
    TIME = "time"  # 时间
    TEXT_LENGTH = "textLength"  # 文本长度
    CUSTOM = "custom"  # 自定义公式


class ValidateOperator(Enum):
    """数据验证操作符"""

    BETWEEN = "between"  # 介于
    NOT_BETWEEN = "notBetween"  # 不介于
    EQUAL = "equal"  # 等于
    NOT_EQUAL = "notEqual"  # 不等于
    GREATER_THAN = "greaterThan"  # 大于
    LESS_THAN = "lessThan"  # 小于
    GREATER_OR_EQUAL = "greaterThanOrEqual"  # 大于等于
    LESS_OR_EQUAL = "lessThanOrEqual"  # 小于等于


class HAlignType(Enum):
    """水平对齐方式"""

    NONE = "none"  # 不设置
    LEFT = "left"  # 左对齐
    CENTER = "center"  # 居中
    RIGHT = "right"  # 右对齐


class VAlignType(Enum):
    """垂直对齐方式"""

    NONE = "none"  # 不设置
    TOP = "top"  # 顶部对齐
    CENTER = "center"  # 垂直居中
    BOTTOM = "bottom"  # 底部对齐


class UnderlineType(Enum):
    """下划线类型"""

    NONE = "none"  # 无下划线
    SINGLE = "single"  # 单下划线
    DOUBLE = "double"  # 双下划线


class BorderStyleType(Enum):
    """边框样式"""

    NONE = "none"  # 无边框
    THIN = "thin"  # 细边框
    MEDIUM = "medium"  # 中边框
    DASHED = "dashed"  # 虚线边框
    DOTTED = "dotted"  # 点线边框
    DOUBLE = "double"  # 双线边框


class HideTargetType(Enum):
    """隐藏目标类型"""

    ROW = "row"  # 行
    COLUMN = "column"  # 列


class ExcelOpenType(Enum):
    """Excel打开方式"""

    NEW = "new"  # 新建Excel
    OPEN = "open"  # 打开已有Excel


class PivotValueFunc(Enum):
    """数据透视表值汇总方式"""

    SUM = "sum"  # 求和
    COUNT = "count"  # 计数
    AVERAGE = "average"  # 平均值
    MAX = "max"  # 最大值
    MIN = "min"  # 最小值


class PivotFilterType(Enum):
    """数据透视表筛选方式"""

    INCLUDE = "include"  # 仅显示该项
    EXCLUDE = "exclude"  # 隐藏该项
