"""
视频处理错误码与异常定义。
"""

from astronverse.baseline.error.error import BaseException, BizCode, ErrorCode
from astronverse.baseline.i18n.i18n import _

BaseException = BaseException

FILE_NOT_FOUND_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件不存在") + ": {}")
INVALID_VIDEO_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("视频文件无效或格式不支持") + ": {}")
INVALID_PARAMS_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("参数有误") + ": {}")
VIDEO_PROCESS_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("视频处理失败") + ": {}")
VIDEO_SAVE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("视频保存失败") + ": {}")
FFMPEG_NOT_FOUND_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("ffmpeg不可用") + ": {}")
