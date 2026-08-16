from astronverse.baseline.error.error import BaseException, BizCode, ErrorCode
from astronverse.baseline.i18n.i18n import _

BaseException = BaseException

MSG_EMPTY_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("内容为空"))
FILE_PATH_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件路径:{}有误，请输入正确的路径！"))
SAVE_TYPE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("保存格式:{}有误，文件扩展名需为{}！"))
FILE_READ_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件读取失败，请检查文件是否损坏！") + ": {}")
FILE_WRITE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件写入失败，请检查文件是否损坏！") + ": {}")
FILE_TYPE_ERROR_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("文件拓展名缺失，请检查文件名称输入是否正确！") + ": {}"
)
FILE_DELETE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件删除失败") + ": {}")
PermissionError_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件：{}被占用，请关闭文件后重试"))
CMD_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("CMD命令:{}执行失败:{}"))

READ_TYPE_ERROR_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("当前文件格式：{}不支持读取，当前仅支持{}格式，请检查文件格式")
)
RENAME_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("新名称：{}和原名称一致，请检查重命名内容"))
ENCODE_TYPE_ERROR_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr,
    _("当前文件编码格式({})与指定的解码类型({})发生冲突，请重新选择编码类型或者以二进制方式读取！"),
)

FOLDER_PATH_ERROR_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("文件夹不存在，请检查文件夹路径是否正确！") + ": {}"
)
CONTENT_TYPE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("获取剪切板内容类型错误"))
FOLDER_DELETE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("文件夹删除失败") + ": {}")
SCREENSHOT_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("截图保存失败") + ": {}")
SCREENLOCK_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("屏幕锁定失败") + ": {}")
SYSTEM_FOLDER_NOT_SUPPORTED_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("当前操作系统不支持获取系统文件夹:{}，请检查文件夹类型")
)
SYSTEM_FOLDER_GET_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("获取系统文件夹:{}路径失败") + ": {}")
SELECTED_FILES_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("获取选中文件(夹)列表失败") + ": {}")
SELECTED_FILES_NOT_FOUND_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("未找到选中的文件(夹)，请先在资源管理器或桌面中选择后再执行")
)
IME_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("输入法操作失败") + ": {}")
IME_NOT_SUPPORTED_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("当前操作系统不支持输入法中英文状态获取/设置，仅支持Windows")
)
SCREENSAVER_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("屏幕保护操作失败") + ": {}")
SCREENSAVER_NOT_RUNNING_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("未找到已唤起的屏幕保护"))
SCREENSAVER_TIP_EMPTY_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("未设置屏保提示文字"))
CUSTOM_DATA_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("自定义数据操作失败") + ": {}")
APP_PARAM_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("获取应用参数失败") + ": {}")
APP_PARAM_NOT_IN_EXECUTOR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("当前不在应用执行环境中，无法获取应用参数"))
RESOURCE_FILE_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("资源文件操作失败") + ": {}")
RESOURCE_FILE_NOT_FOUND_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("资源文件不存在: {}"))
LOG_EXPORT_ERROR_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("导出日志失败") + ": {}")
