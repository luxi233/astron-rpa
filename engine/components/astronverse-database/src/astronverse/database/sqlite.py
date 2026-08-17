"""Sqlite3数据库操作: 连接本地Sqlite3数据库文件、执行SQL、查询、批量插入、导出CSV、关闭连接"""

from enum import Enum

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.database.error import *

__all__ = ["Sqlite", "SqliteCsvEncoding"]


class SqliteCsvEncoding(Enum):
    UTF8 = "utf8"  # UTF-8
    UTF8_BOM = "utf8_bom"  # 带有BOM的UTF-8
    GBK = "gbk"  # GBK(ANSI)


class Sqlite:
    @staticmethod
    @atomicMg.atomic(
        "Sqlite",
        inputList=[
            atomicMg.param(
                "db_path",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("conn", types="Str")],
    )
    def connect(db_path: str = ""):
        """
        连接Sqlite3数据库
        :param db_path: 数据库文件路径，如 C:/data/test.db；文件不存在时将自动创建
        :return: Sqlite3数据库连接对象
        """
        import sqlite3

        try:
            conn = sqlite3.connect(db_path, timeout=30)
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SQLITE_CONNECT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Sqlite",
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
        执行Sqlite3数据库语句(Insert/Update/Delete/Create等)
        :param conn: Sqlite3数据库连接对象
        :param sql: SQL语句
        :return: 受影响行数
        """
        try:
            if conn is None:
                raise BaseException(SQLITE_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
            cursor = conn.cursor()
            try:
                cursor.execute(sql)
                conn.commit()
                return cursor.rowcount
            finally:
                cursor.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SQLITE_EXECUTE_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Sqlite",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "sql",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("result", types="List")],
    )
    def query_table(conn=None, sql: str = ""):
        """
        查询Sqlite3数据库数据表
        :param conn: Sqlite3数据库连接对象
        :param sql: SELECT查询语句
        :return: 查询结果(list[list]): 第一行为列名，之后每行为一条记录
        """
        try:
            if conn is None:
                raise BaseException(SQLITE_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
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
            raise BaseException(SQLITE_QUERY_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Sqlite",
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
        ],
        outputList=[atomicMg.param("affected_rows", types="Int")],
    )
    def batch_insert(conn=None, table_name: str = "", columns=None, data=None):
        """
        批量插入数据到Sqlite3数据库表(事务: 全部成功或全部失败)
        :param conn: Sqlite3数据库连接对象
        :param table_name: 表名，如 users
        :param columns: 列名列表，如 ['name','age']
        :param data: 插入数据(二维列表)，如 [['张三',18],['李四',20]]
        :return: 受影响行数
        """
        if not data or not isinstance(data, (list, tuple)) or not all(isinstance(r, (list, tuple)) for r in data):
            raise BaseException(
                SQLITE_DATA_FORMAT,
                "插入数据必须是二维列表",
            )
        if not columns or not isinstance(columns, (list, tuple)):
            raise BaseException(
                SQLITE_COLUMNS_FORMAT,
                "列名必须是列表，如 ['name','age']",
            )

        try:
            if conn is None:
                raise BaseException(SQLITE_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
            col_str = ", ".join([str(c) for c in columns])
            placeholders = ", ".join(["?"] * len(columns))
            sql = "INSERT INTO {} ({}) VALUES ({})".format(table_name, col_str, placeholders)
            cursor = conn.cursor()
            try:
                cursor.executemany(sql, data)
                affected = cursor.rowcount
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
            raise BaseException(SQLITE_BATCH_INSERT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Sqlite",
        inputList=[
            atomicMg.param("conn", types="Str"),
            atomicMg.param(
                "sql",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_PYTHON_TEXTAREAMODAL_VARIABLE.value),
                required=True,
            ),
            atomicMg.param(
                "csv_path",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("file_encoding", types="Str"),
        ],
    )
    def export_to_csv(
        conn=None, sql: str = "", csv_path: str = "", file_encoding: SqliteCsvEncoding = SqliteCsvEncoding.UTF8_BOM
    ):
        """
        导出Sqlite3查询结果至CSV文件
        :param conn: Sqlite3数据库连接对象
        :param sql: SELECT查询语句
        :param csv_path: CSV文件保存路径
        :param file_encoding: 文件编码
        """
        import csv
        import os

        try:
            if conn is None:
                raise BaseException(SQLITE_NO_CONNECTION_FORMAT, "缺少数据库连接对象")
            encoding = "utf-8"
            if file_encoding == SqliteCsvEncoding.UTF8_BOM:
                encoding = "utf-8-sig"
            elif file_encoding == SqliteCsvEncoding.GBK:
                encoding = "gbk"
            cursor = conn.cursor()
            try:
                cursor.execute(sql)
                if not cursor.description:
                    raise BaseException(
                        SQLITE_EXPORT_FORMAT,
                        "查询语句无结果集，无法导出",
                    )
                col_names = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
            finally:
                cursor.close()
            dir_name = os.path.dirname(csv_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(csv_path, "w", newline="", encoding=encoding) as f:
                writer = csv.writer(f)
                writer.writerow(col_names)
                writer.writerows(rows)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SQLITE_EXPORT_FORMAT.format(str(e)), str(e))

    @staticmethod
    @atomicMg.atomic(
        "Sqlite",
        inputList=[
            atomicMg.param("conn", types="Str"),
        ],
    )
    def close(conn=None) -> None:
        """
        关闭Sqlite3数据库连接
        :param conn: Sqlite3数据库连接对象
        """
        try:
            if conn is not None:
                conn.close()
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(SQLITE_CLOSE_FORMAT.format(str(e)), str(e))
