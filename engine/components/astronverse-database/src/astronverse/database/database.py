"""数据库操作: 通过 ODBC 连接字符串连接数据库、执行SQL、批量插入、关闭连接"""

from enum import Enum

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.database.error import *


class SqlResultFormatFlag(Enum):
    """SQL查询结果格式枚举"""

    LIST = "list"  # 二维列表(第一行为列名)
    DICTS = "dicts"  # 字典列表(每行一个字典)


class TransactionActionFlag(Enum):
    """事务操作类型枚举"""

    BEGIN = "begin"  # 开始事务
    COMMIT = "commit"  # 提交事务
    ROLLBACK = "rollback"  # 回滚事务


class ProcedureParamTypeFlag(Enum):
    """存储过程输出参数类型枚举"""

    INTEGER = "integer"  # 整数
    VARCHAR = "varchar"  # 字符串
    FLOAT = "float"  # 浮点数


__all__ = ["Database"]


class Database:
    @staticmethod
    @atomicMg.atomic(
        "Database",
        inputList=[
            atomicMg.param(
                "conn_str",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("conn", types="Str")],
    )
    def connect(conn_str: str = ""):
        """
        连接数据库(ODBC连接字符串)
        :param conn_str: ODBC连接字符串，如 Driver={MySQL ODBC 8.0 Unicode Driver};Server=127.0.0.1;Database=test;UID=root;PWD=123456
        :return: 数据库连接对象
        """
        import pyodbc

        try:
            return pyodbc.connect(conn_str, timeout=30)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DATABASE_CONNECT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Database",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "conn_str",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
            atomicMg.param(
                "sql",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
            atomicMg.param(
                "params",
                types="List",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=False,
            ),
            atomicMg.param("time_out", types="Int", required=False),
            atomicMg.param(
                "return_format",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
        ],
        outputList=[atomicMg.param("result", types="List")],
    )
    def execute_sql(
        conn=None,
        conn_str: str = "",
        sql: str = "",
        params: list = None,
        time_out: int = 30,
        return_format: SqlResultFormatFlag = SqlResultFormatFlag.LIST,
    ):
        """
        执行SQL语句(Insert/Update/Delete/Select)
        :param conn: 数据库连接对象(与连接字符串二选一)
        :param conn_str: 数据库连接字符串(未填连接对象时使用，将自动连接并在执行后关闭)
        :param sql: SQL语句
        :param params: 参数化查询的参数列表(SQL中用?占位)，如 ['张三', 18]
        :param time_out: 超时秒数
        :param return_format: 查询结果格式(二维列表/字典列表)
        :return: 查询结果: SELECT时二维列表第一行为列名(或字典列表); 无结果集语句返回受影响行数(第0行第0列)
        """
        import pyodbc

        def _execute(cursor_obj):
            if params:
                cursor_obj.execute(sql, params)
            else:
                cursor_obj.execute(sql)
            rows = cursor_obj.fetchall()
            if cursor_obj.description:
                columns = [desc[0] for desc in cursor_obj.description]
                if return_format == SqlResultFormatFlag.DICTS:
                    return [
                        {columns[i]: (str(col) if col is not None else "") for i, col in enumerate(row)} for row in rows
                    ]
                result = [columns]
                result.extend([[str(col) if col is not None else "" for col in row] for row in rows])
                return result
            return [[str(cursor_obj.rowcount)]]

        try:
            if conn is not None:
                cursor = conn.cursor()
                try:
                    result = _execute(cursor)
                    conn.commit()
                    return result
                finally:
                    cursor.close()
            if conn_str:
                local_conn = pyodbc.connect(conn_str, timeout=time_out)
                try:
                    cursor = local_conn.cursor()
                    try:
                        result = _execute(cursor)
                        local_conn.commit()
                        return result
                    finally:
                        cursor.close()
                finally:
                    local_conn.close()
            raise BaseException(
                DATABASE_NO_CONNECTION_FORMAT,
                "缺少数据库连接",
            )
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DATABASE_EXECUTE_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Database",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "conn_str",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
            atomicMg.param(
                "sql",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
            atomicMg.param(
                "data",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("affected_rows", types="Int")],
    )
    def batch_insert(conn=None, conn_str: str = "", sql: str = "", data=None):
        """
        数据库批量插入数据(事务: 全部成功或全部失败)
        :param conn: 数据库连接对象(与连接字符串二选一)
        :param conn_str: 数据库连接字符串(未填连接对象时使用，将自动连接并在执行后关闭)
        :param sql: 插入SQL语句(参数用?占位)，如 INSERT INTO users(name,age) VALUES(?,?)
        :param data: 插入数据(二维列表)，如 [['影刀',1],['RPA',2]]
        :return: 受影响行数
        """
        import pyodbc

        if not data or not isinstance(data, (list, tuple)) or not all(isinstance(r, (list, tuple)) for r in data):
            raise BaseException(
                DATABASE_DATA_FORMAT,
                "插入数据必须是二维列表",
            )

        def _insert(conn_obj):
            cursor_obj = conn_obj.cursor()
            try:
                cursor_obj.executemany(sql, data)
                affected = cursor_obj.rowcount
                conn_obj.commit()
                return affected
            except Exception:
                conn_obj.rollback()
                raise
            finally:
                cursor_obj.close()

        try:
            if conn is not None:
                return _insert(conn)
            if conn_str:
                local_conn = pyodbc.connect(conn_str, timeout=30)
                try:
                    return _insert(local_conn)
                finally:
                    local_conn.close()
            raise BaseException(
                DATABASE_NO_CONNECTION_FORMAT,
                "缺少数据库连接",
            )
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DATABASE_BATCH_INSERT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Database",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "conn_str",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=False,
            ),
            atomicMg.param(
                "table_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "columns",
                types="List",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
            atomicMg.param(
                "key_columns",
                types="List",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
            atomicMg.param(
                "data",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("affected_rows", types="Int")],
    )
    def upsert(
        conn=None, conn_str: str = "", table_name: str = "", columns: list = None, key_columns: list = None, data=None
    ):
        """
        更新插入数据(主键冲突时更新)
        :param conn: 数据库连接对象(与连接字符串二选一)
        :param conn_str: 数据库连接字符串(未填连接对象时使用，将自动连接并在执行后关闭)
        :param table_name: 表名
        :param columns: 列名列表，如 ['id','name','age']
        :param key_columns: 冲突判定列(主键/唯一键)，如 ['id']
        :param data: 数据(二维列表)，如 [[1,'张三',18],[2,'李四',20]]
        :return: 受影响行数
        """
        import pyodbc

        if not columns or not isinstance(columns, (list, tuple)):
            raise BaseException(DATABASE_COLUMNS_FORMAT, "列名必须是列表，如 ['id','name']")
        if not key_columns or not isinstance(key_columns, (list, tuple)):
            raise BaseException(DATABASE_COLUMNS_FORMAT, "冲突判定列必须是列表，如 ['id']")
        if not data or not isinstance(data, (list, tuple)) or not all(isinstance(r, (list, tuple)) for r in data):
            raise BaseException(DATABASE_DATA_FORMAT, "数据必须是二维列表")
        key_set = set(key_columns)
        if not key_set.issubset(set(columns)):
            raise BaseException(DATABASE_COLUMNS_FORMAT, "冲突判定列必须包含在列名列表中")
        update_cols = [c for c in columns if c not in key_set]
        if not update_cols:
            raise BaseException(DATABASE_COLUMNS_FORMAT, "除冲突判定列外至少需要一个更新列")

        col_index = {c: i for i, c in enumerate(columns)}

        def _upsert(conn_obj):
            total = 0
            cursor_obj = conn_obj.cursor()
            try:
                for row in data:
                    if len(row) != len(columns):
                        raise BaseException(
                            DATABASE_DATA_FORMAT, "数据列数({})与列名数({})不一致".format(len(row), len(columns))
                        )
                    key_vals = [row[col_index[k]] for k in key_columns]
                    set_clause = ", ".join(["{} = ?".format(c) for c in update_cols])
                    where_clause = " AND ".join(["{} = ?".format(k) for k in key_columns])
                    cursor_obj.execute(
                        "UPDATE {} SET {} WHERE {}".format(table_name, set_clause, where_clause),
                        [row[col_index[c]] for c in update_cols] + key_vals,
                    )
                    if cursor_obj.rowcount and cursor_obj.rowcount > 0:
                        total += cursor_obj.rowcount
                    else:
                        placeholders = ", ".join(["?"] * len(columns))
                        cursor_obj.execute(
                            "INSERT INTO {} ({}) VALUES ({})".format(table_name, ", ".join(columns), placeholders),
                            list(row),
                        )
                        total += 1
                conn_obj.commit()
                return total
            except Exception:
                conn_obj.rollback()
                raise
            finally:
                cursor_obj.close()

        try:
            if conn is not None:
                return _upsert(conn)
            if conn_str:
                local_conn = pyodbc.connect(conn_str, timeout=30)
                try:
                    return _upsert(local_conn)
                finally:
                    local_conn.close()
            raise BaseException(
                DATABASE_NO_CONNECTION_FORMAT,
                "缺少数据库连接",
            )
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DATABASE_UPSERT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Database",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "action",
                formType=AtomicFormTypeMeta(type=AtomicFormType.RADIO.value),
            ),
        ],
        outputList=[atomicMg.param("success", types="Bool")],
    )
    def execute_transaction(conn=None, action: TransactionActionFlag = TransactionActionFlag.BEGIN) -> bool:
        """
        执行数据库事务(开始/提交/回滚)
        :param conn: 数据库连接对象
        :param action: 事务操作(begin开始/commit提交/rollback回滚)
        :return: 是否执行成功
        """
        if conn is None:
            raise BaseException(
                DATABASE_NO_CONNECTION_FORMAT,
                "缺少数据库连接",
            )
        try:
            cursor = conn.cursor()
            try:
                if action == TransactionActionFlag.BEGIN:
                    cursor.execute("BEGIN TRANSACTION")
                elif action == TransactionActionFlag.COMMIT:
                    cursor.execute("COMMIT")
                elif action == TransactionActionFlag.ROLLBACK:
                    cursor.execute("ROLLBACK")
                else:
                    raise BaseException(DATABASE_TRANSACTION_FORMAT, "未知事务操作: {}".format(action))
                return True
            finally:
                cursor.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DATABASE_TRANSACTION_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Database",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "procedure_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "input_params",
                types="List",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=False,
            ),
            atomicMg.param(
                "output_types",
                types="List",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=False,
            ),
            atomicMg.param("time_out", types="Int", required=False),
        ],
        outputList=[
            atomicMg.param("output_values", types="List"),
            atomicMg.param("result_sets", types="List"),
        ],
    )
    def run_procedure(
        conn=None,
        procedure_name: str = "",
        input_params: list = None,
        output_types: list = None,
        time_out: int = 30,
    ):
        """
        运行存储过程
        :param conn: 数据库连接对象
        :param procedure_name: 存储过程名称
        :param input_params: 输入参数列表，如 ['张三', 18]
        :param output_types: 输出参数类型列表(枚举值列表)，如 ['integer','varchar']，依次对应存储过程的OUTPUT参数
        :param time_out: 超时秒数
        :return: (输出参数值列表, 结果集二维列表)
        """
        import pyodbc

        if conn is None:
            raise BaseException(
                DATABASE_NO_CONNECTION_FORMAT,
                "缺少数据库连接",
            )
        if not procedure_name:
            raise BaseException(DATABASE_PROCEDURE_FORMAT, "存储过程名称不能为空")

        inputs = list(input_params or [])
        out_type_map = {
            ProcedureParamTypeFlag.INTEGER.value: pyodbc.SQL_INTEGER,
            ProcedureParamTypeFlag.VARCHAR.value: pyodbc.SQL_VARCHAR,
            ProcedureParamTypeFlag.FLOAT.value: pyodbc.SQL_DOUBLE,
        }
        outputs = []
        for t in output_types or []:
            t_val = t.value if hasattr(t, "value") else str(t)
            sql_type = out_type_map.get(t_val)
            if sql_type is None:
                raise BaseException(DATABASE_PROCEDURE_FORMAT, "未知输出参数类型: {}".format(t_val))
            outputs.append(pyodbc.Output(sql_type, None))

        placeholders = ", ".join(["?"] * (len(inputs) + len(outputs)))
        call_sql = "{{CALL {}({})}}".format(procedure_name, placeholders)

        try:
            cursor = conn.cursor()
            try:
                cursor.execute(call_sql, tuple(inputs) + tuple(outputs))
                # 消费全部结果集(部分驱动在未取完结果集前不回填OUTPUT参数)
                result_sets = []
                while True:
                    if cursor.description:
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        sheet = [columns]
                        sheet.extend([[str(col) if col is not None else "" for col in row] for row in rows])
                        result_sets.append(sheet)
                    if not cursor.nextset():
                        break
                conn.commit()
                output_values = [o.value if o.value is not None else "" for o in outputs]
                return output_values, result_sets
            finally:
                cursor.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DATABASE_PROCEDURE_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Database",
        inputList=[
            atomicMg.param("conn", types="Str"),
        ],
    )
    def close(conn=None) -> None:
        """
        关闭数据库连接
        :param conn: 数据库连接对象
        """
        try:
            if conn is not None:
                conn.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(DATABASE_CLOSE_FORMAT.format(str(e)), str(e))
