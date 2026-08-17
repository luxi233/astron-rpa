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
DATABASE_COLUMNS_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("列名或冲突判定列必须是列表，如：['id','name']"))
DATABASE_UPSERT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("更新插入数据失败，错误：{}"))
DATABASE_TRANSACTION_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("执行数据库事务失败，错误：{}"))
DATABASE_PROCEDURE_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("运行存储过程失败，错误：{}"))

SQLITE_CONNECT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("连接Sqlite3数据库失败，错误：{}"))
SQLITE_EXECUTE_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("执行Sqlite3语句失败，错误：{}"))
SQLITE_QUERY_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("查询Sqlite3数据表失败，错误：{}"))
SQLITE_BATCH_INSERT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("Sqlite3批量插入失败，错误：{}"))
SQLITE_EXPORT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("导出Sqlite3数据至CSV失败，错误：{}"))
SQLITE_CLOSE_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("关闭Sqlite3数据库失败，错误：{}"))
SQLITE_NO_CONNECTION_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("缺少Sqlite3数据库连接对象：请先使用【连接Sqlite3数据库】创建连接")
)
SQLITE_DATA_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("插入数据必须是二维列表，如：[['张三',18],['李四',20]]"))
SQLITE_COLUMNS_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("列名必须是列表，如：['name','age']"))

POSTGRES_CONNECT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("连接PostgreSQL数据库失败，错误：{}"))
POSTGRES_EXECUTE_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("执行PostgreSQL语句失败，错误：{}"))
POSTGRES_QUERY_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("查询PostgreSQL数据表失败，错误：{}"))
POSTGRES_INSERT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("PostgreSQL插入数据失败，错误：{}"))
POSTGRES_BATCH_INSERT_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("PostgreSQL批量插入失败，错误：{}"))
POSTGRES_CLOSE_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("关闭PostgreSQL数据库失败，错误：{}"))
POSTGRES_NO_CONNECTION_FORMAT: ErrorCode = ErrorCode(
    BizCode.LocalErr, _("缺少PostgreSQL数据库连接对象：请先使用【连接PostgreSQL数据库】创建连接")
)
POSTGRES_DATA_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("插入数据必须是字典，如：{'name':'张三','age':18}"))
POSTGRES_COLUMNS_FORMAT: ErrorCode = ErrorCode(BizCode.LocalErr, _("列名必须是列表，如：['name','age']"))
