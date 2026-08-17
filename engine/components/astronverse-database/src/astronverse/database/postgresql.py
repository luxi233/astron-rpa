"""PostgreSQL数据库操作: 连接PostgreSQL数据库、执行SQL、条件查询、字典插入、批量插入、关闭连接"""

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.database.error import *

__all__ = ["Postgres"]


def _quote_ident(name) -> str:
    """标识符加双引号防注入(内部双引号双写)。"""
    return '"{}"'.format(str(name).replace('"', '""'))


class Postgres:
    @staticmethod
    @atomicMg.atomic(
        "Postgres",
        inputList=[
            atomicMg.param(
                "host",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("port", types="Int", required=False),
            atomicMg.param(
                "user",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "password",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "dbname",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("conn", types="Str")],
    )
    def connect(host: str = "", port: int = 5432, user: str = "", password: str = "", dbname: str = ""):
        """
        连接PostgreSQL数据库
        :param host: 主机地址，如 127.0.0.1
        :param port: 端口号，默认5432
        :param user: 用户名
        :param password: 密码
        :param dbname: 数据库名
        :return: PostgreSQL数据库连接对象
        """
        import psycopg2

        try:
            return psycopg2.connect(
                host=host,
                port=int(port or 5432),
                user=user,
                password=password,
                dbname=dbname,
                connect_timeout=30,
            )
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(POSTGRES_CONNECT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Postgres",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "sql",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("affected_rows", types="Int")],
    )
    def execute_sql(conn=None, sql: str = ""):
        """
        执行PostgreSQL语句(Insert/Update/Delete/Create等非查询语句)
        :param conn: PostgreSQL数据库连接对象
        :param sql: SQL语句
        :return: 受影响行数
        """
        try:
            if conn is None:
                raise BaseException(POSTGRES_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
            cursor = conn.cursor()
            try:
                cursor.execute(sql)
                conn.commit()
                # DDL语句rowcount为-1，统一按0返回
                return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
            finally:
                cursor.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(POSTGRES_EXECUTE_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Postgres",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "table_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "fields",
                types="List",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=False,
            ),
            atomicMg.param(
                "where",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=False,
            ),
        ],
        outputList=[atomicMg.param("result", types="List")],
    )
    def query_table(conn=None, table_name: str = "", fields: list = None, where: str = ""):
        """
        查询PostgreSQL数据表(表名+字段列表+where条件式查询)
        :param conn: PostgreSQL数据库连接对象
        :param table_name: 表名，如 users
        :param fields: 字段列表，如 ['name','age']；为空时查询全部字段
        :param where: 查询条件(WHERE后的条件式)，如 age > 18；为空时查询全部
        :return: 查询结果(list[list]): 第一行为列名，之后每行为一条记录
        """
        try:
            if conn is None:
                raise BaseException(POSTGRES_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
            if not table_name:
                raise BaseException(POSTGRES_QUERY_FORMAT, "表名不能为空")
            cols = ", ".join(_quote_ident(f) for f in fields) if fields else "*"
            sql = "SELECT {} FROM {}".format(cols, _quote_ident(table_name))
            if where and str(where).strip():
                sql += " WHERE {}".format(str(where).strip())
            cursor = conn.cursor()
            try:
                cursor.execute(sql)
                if cursor.description:
                    result = [[desc[0] for desc in cursor.description]]
                    result.extend([list(row) for row in cursor.fetchall()])
                    return result
                return []
            finally:
                cursor.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(POSTGRES_QUERY_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Postgres",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "table_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
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
    def insert_dict(conn=None, table_name: str = "", data: dict = None):
        """
        添加数据记录到PostgreSQL表(字典方式INSERT)
        :param conn: PostgreSQL数据库连接对象
        :param table_name: 表名，如 users
        :param data: 插入数据(字典)，如 {'name':'张三','age':18}
        :return: 受影响行数
        """
        try:
            if conn is None:
                raise BaseException(POSTGRES_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
            if not table_name:
                raise BaseException(POSTGRES_INSERT_FORMAT, "表名不能为空")
            if not data or not isinstance(data, dict):
                raise BaseException(POSTGRES_DATA_FORMAT, "插入数据必须是字典，如 {'name':'张三','age':18}")
            cols = ", ".join(_quote_ident(k) for k in data.keys())
            values = ", ".join(["%({})s".format(k) for k in data.keys()])
            sql = "INSERT INTO {} ({}) VALUES ({})".format(_quote_ident(table_name), cols, values)
            cursor = conn.cursor()
            try:
                cursor.execute(sql, data)
                affected = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
                conn.commit()
                return affected
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(POSTGRES_INSERT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Postgres",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "table_name",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "columns",
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
            atomicMg.param("batch_size", types="Int", required=False),
        ],
        outputList=[atomicMg.param("affected_rows", types="Int")],
    )
    def batch_insert(conn=None, table_name: str = "", columns: list = None, data=None, batch_size: int = 1000):
        """
        批量添加记录到PostgreSQL表(二维列表+单次执行上限)
        :param conn: PostgreSQL数据库连接对象
        :param table_name: 表名，如 users
        :param columns: 列名列表，如 ['name','age']
        :param data: 插入数据(二维列表)，如 [['张三',18],['李四',20]]
        :param batch_size: 单次执行上限(每批提交一次)，默认1000
        :return: 受影响行数
        """
        if not data or not isinstance(data, (list, tuple)) or not all(isinstance(r, (list, tuple)) for r in data):
            raise BaseException(
                POSTGRES_DATA_FORMAT,
                "插入数据必须是二维列表，如 [['张三',18],['李四',20]]",
            )
        if not columns or not isinstance(columns, (list, tuple)):
            raise BaseException(
                POSTGRES_COLUMNS_FORMAT,
                "列名必须是列表，如 ['name','age']",
            )

        try:
            if conn is None:
                raise BaseException(POSTGRES_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
            if not table_name:
                raise BaseException(POSTGRES_BATCH_INSERT_FORMAT, "表名不能为空")
            size = max(1, int(batch_size or 1000))
            cols = ", ".join(_quote_ident(c) for c in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            sql = "INSERT INTO {} ({}) VALUES ({})".format(_quote_ident(table_name), cols, placeholders)
            cursor = conn.cursor()
            total = 0
            try:
                for i in range(0, len(data), size):
                    chunk = [tuple(row) for row in data[i : i + size]]
                    cursor.executemany(sql, chunk)
                    total += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
                    conn.commit()
                return total
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(POSTGRES_BATCH_INSERT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Postgres",
        inputList=[
            atomicMg.param("conn", types="Str"),
        ],
    )
    def close(conn=None) -> None:
        """
        关闭PostgreSQL数据库连接
        :param conn: PostgreSQL数据库连接对象
        """
        try:
            if conn is not None:
                conn.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(POSTGRES_CLOSE_FORMAT.format(str(e)), str(e))
