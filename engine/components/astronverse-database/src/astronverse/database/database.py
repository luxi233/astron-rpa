"""数据库操作: 通过 ODBC 连接字符串连接数据库、执行SQL、批量插入、关闭连接"""

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.database.error import *

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
            atomicMg.param("time_out", types="Int", required=False),
        ],
        outputList=[atomicMg.param("result", types="List")],
    )
    def execute_sql(conn=None, conn_str: str = "", sql: str = "", time_out: int = 30):
        """
        执行SQL语句(Insert/Update/Delete/Select)
        :param conn: 数据库连接对象(与连接字符串二选一)
        :param conn_str: 数据库连接字符串(未填连接对象时使用，将自动连接并在执行后关闭)
        :param sql: SQL语句
        :param time_out: 超时秒数
        :return: 查询结果(list[list]): SELECT时第一行为列名; 无结果集语句返回受影响行数(第0行第0列)
        """
        import pyodbc

        def _execute(cursor_obj):
            cursor_obj.execute(sql)
            rows = cursor_obj.fetchall()
            if cursor_obj.description:
                result = [[desc[0] for desc in cursor_obj.description]]
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
