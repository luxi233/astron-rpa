from astronverse.actionlib.error import IGNORE_ERROR_FORMAT
from astronverse.baseline.error.error import BizCode, ErrorCode
from astronverse.baseline.i18n.i18n import _

PHONE_CONNECT_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("连接手机失败，错误：{}"))
PHONE_NO_CONNECTION_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("手机连接对象为空：请先使用【连接手机】创建连接对象")
)
PHONE_ELEMENT_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("手机元素定位失败，错误：{}"))
PHONE_ELEMENT_NOT_FOUND_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("未找到匹配的手机元素: {}"))
PHONE_IMAGE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("手机图像匹配失败，错误：{}"))
PHONE_IMAGE_NOT_FOUND_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("未在手机屏幕上匹配到目标图像"))
PHONE_FILE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("手机文件传输失败，错误：{}"))
PHONE_EXECUTE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("手机指令执行失败，错误：{}"))
PHONE_DEVICE_LIST_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("获取手机设备列表失败，错误：{}"))

__all__ = [
    "IGNORE_ERROR_FORMAT",
    "PHONE_CONNECT_ERROR_FORMAT",
    "PHONE_NO_CONNECTION_FORMAT",
    "PHONE_ELEMENT_ERROR_FORMAT",
    "PHONE_ELEMENT_NOT_FOUND_FORMAT",
    "PHONE_IMAGE_ERROR_FORMAT",
    "PHONE_IMAGE_NOT_FOUND_FORMAT",
    "PHONE_FILE_ERROR_FORMAT",
    "PHONE_EXECUTE_ERROR_FORMAT",
    "PHONE_DEVICE_LIST_ERROR_FORMAT",
]
