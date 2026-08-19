from dataclasses import dataclass
from enum import Enum


class BizCode(Enum):
    LocalOK = "0000"
    LocalErr = "1001"


@dataclass
class ErrorCode:
    code: BizCode  # Business code
    message: str
    httpcode: int = 200

    def format(self, *args, **kwargs):
        # 返回新对象而非原地改写: 模块级共享的 ErrorCode(如 PARAMS_ERROR)若被原地
        # 污染, 第二次 format 时模板已无占位符, 会静默返回首次插值文本(错误信息张冠李戴)
        return ErrorCode(self.code, self.message.format(*args, **kwargs), self.httpcode)


class BaseException(Exception):
    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        self.message = message
        super().__init__(self.code.message)
