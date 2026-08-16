from astronverse.baseline.error.error import BizCode, ErrorCode
from astronverse.baseline.i18n.i18n import _

DATABASE_CONNECT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("连接数据库失败，错误：{}"))
DATABASE_EXECUTE_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("执行SQL语句失败，错误：{}"))
DATABASE_BATCH_INSERT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("数据库批量插入失败，错误：{}"))
DATABASE_CLOSE_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("关闭数据库失败，错误：{}"))
DATABASE_NO_CONNECTION_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("缺少数据库连接：请先使用【连接数据库】创建连接对象，或直接填写连接字符串")
)
DATABASE_DATA_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("插入数据必须是二维列表，如：[['影刀',1],['RPA',2]]"))
