from astronverse.baseline.error.error import BaseException, BizCode, ErrorCode
from astronverse.baseline.i18n.i18n import _

import builtins

BaseException = BaseException


IGNORE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("{}"))
TYPE_KIND_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("类型错误: {}"))

CONFIG_LOAD_ERROR: ErrorCode = ErrorCode(BizCode.LocalErr, _("配置文件加载出错: {}"))
CONFIG_TYPE_ERROR: ErrorCode = ErrorCode(BizCode.LocalErr, _("配置文件解析不支持该类型: {}"))

REQUIRED_PARAM_MISSING: ErrorCode = ErrorCode(BizCode.LocalErr, _("缺少必填参数: {}"))
PARAM_ARGS_NO_SUPPORT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("参数不支持args: {}"))

PARAM_REQUIRED_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("参数 {} 必填"))
PARAM_VALUE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("参数 {} 的值错误{}"))
PARAM_TYPE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("{} 的值类型错误{}"))
PARAM_CONVERT_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("参数 {} 的值转换成 {} 失败，原始值: {}"))
PARAM_VERIFY_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("参数 {} 验证失败: {}"))
VALUE_IS_EMPTY: ErrorCode = ErrorCode(BizCode.LocalErr, _("{} 参数值不能为空"))

ReportStartMsgFormat = _("{} 执行第{}条指令 [{}]")
ReportCodeError = _("执行错误")
ReportCodeSkip = _("执行错误跳过")
ReportCodeRetry = _("执行错误重试")


class IgnoreException(BaseException):
    """内部已经处理了错误, 外部可忽略错误细节的错误"""

    pass


class ParamException(BaseException):
    """参数错误，额外携带出错的参数名"""

    pass


class TerminateAppSignal(builtins.BaseException):
    """终止应用信号: 由 System.terminate_app 原子抛出, 穿透流程错误处理(Try/except Exception), 由执行器捕获后以 CANCEL 状态结束整个应用

    注意: 本文件顶部 `BaseException = BaseException` 已将内置名遮蔽为业务异常(其父类为 Exception), 因此必须显式继承 builtins.BaseException, 否则会被流程的异常捕获节点吞掉导致终止失效
    """

    def __init__(self, message: str = ""):
        self.message = message
        super().__init__(message)
