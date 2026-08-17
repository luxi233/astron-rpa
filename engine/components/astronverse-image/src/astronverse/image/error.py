"""
错误码与异常定义。
"""

from astronverse.baseline.error.error import BaseException, BizCode, ErrorCode
from astronverse.baseline.i18n.i18n import _

BaseException = BaseException

FILE_NOT_FOUND_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件不存在") + ": {}")
INVALID_IMAGE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("图片文件无效或格式不支持") + ": {}")
INVALID_CONTENT_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("生成内容无效") + ": {}")
SAVE_FAILED_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件保存失败") + ": {}")
RECOGNIZE_FAILED_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("识别失败") + ": {}")
IMAGE_PROCESS_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("图片处理失败") + ": {}")
INVALID_PARAMS_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("参数有误") + ": {}")
