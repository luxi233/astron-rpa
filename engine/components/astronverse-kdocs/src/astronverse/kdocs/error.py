from astronverse.baseline.error.error import BaseException, BizCode, ErrorCode
from astronverse.baseline.i18n.i18n import _

BaseException = BaseException

WPS_HOOK_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("WPS在线表格操作失败") + ": {}")
WPS_CLIENT_INVALID_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("WPS连接对象无效") + ": {}")


def wps_hook_error(detail: str) -> ErrorCode:
    """每次抛错构造新的 ErrorCode。

    ErrorCode.format() 会原地污染模块级模板（教训#49：同一 FORMAT 第二次 format
    静默返回首次插值文本，导致连续错误"张冠李戴"），因此这里不复用常量。
    """
    return ErrorCode(BizCode.LocalErr, _("WPS在线表格操作失败") + ": " + str(detail))
