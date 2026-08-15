from enum import Enum


class TargetType(Enum):
    ROW = "row"
    COLUMN = "column"


class OpType(Enum):
    ROW = "row"
    COLUMN = "column"
    CELL = "cell"


class ClearType(Enum):
    CONTENTS = "contents"
    FORMATS = "formats"
    ALL = "all"


class MergeType(Enum):
    MERGE = "merge"
    UNMERGE = "unmerge"


class FitType(Enum):
    ROW = "row"
    COLUMN = "column"
    BOTH = "both"


class FormulaMode(Enum):
    GET = "get"
    SET = "set"


class FuncName(Enum):
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    LARGE = "large"
    SMALL = "small"
