# -*- coding: utf-8 -*-
"""M6 冒烟: Postgres 6 原子全链路 (mock psycopg2 全接口, 仿 pyodbc mock 模式)"""
import os
import sys
import types

COMP = "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-database"
sys.path.insert(0, os.path.join(COMP, "src"))
os.chdir(COMP)


# ---- Fake psycopg2 ----
class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self.description = conn.desc
        self.rowcount = -1
        self.execute_calls = []
        self.executemany_calls = []
        self.closed = False

    def execute(self, sql, params=None):
        if self._conn.fail_execute:
            raise RuntimeError("syntax error at or near FROM")
        self.execute_calls.append((sql, params))
        self.rowcount = self._conn.report_rowcount

    def executemany(self, sql, seq):
        if self._conn.fail_executemany:
            raise RuntimeError("duplicate key value violates unique constraint")
        seq = list(seq)
        self.executemany_calls.append((sql, seq))
        self.rowcount = len(seq)

    def fetchall(self):
        return self._conn.fetch_rows

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, **kwargs):
        self.connect_kwargs = kwargs
        self.commits = 0
        self.rollbacks = 0
        self.closes = 0
        self.cursors = []
        self.fetch_rows = []
        self.desc = None
        self.report_rowcount = -1
        self.fail_execute = False
        self.fail_executemany = False

    def cursor(self):
        c = FakeCursor(self)
        self.cursors.append(c)
        return c

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closes += 1


FAIL_CONNECT = {"on": False}


def fake_connect(**kwargs):
    if FAIL_CONNECT["on"]:
        raise RuntimeError("connection refused")
    return FakeConnection(**kwargs)


pg_mod = types.ModuleType("psycopg2")
pg_mod.connect = fake_connect
sys.modules["psycopg2"] = pg_mod

from astronverse.database.postgresql import Postgres  # noqa: E402

RESULTS = []


def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


def expect_error(name, fn, contains):
    try:
        fn()
        check(name, False)
    except BaseException as e:
        check(name, contains in str(e))


# 1. connect 成功 + kwargs 捕获 + 端口字符串转int
conn = Postgres.connect(host="127.0.0.1", port="5433", user="postgres", password="pwd", dbname="test")
check("connect 返回连接对象", isinstance(conn, FakeConnection))
check("connect 参数透传", conn.connect_kwargs.get("host") == "127.0.0.1" and conn.connect_kwargs.get("port") == 5433
      and conn.connect_kwargs.get("user") == "postgres" and conn.connect_kwargs.get("password") == "pwd"
      and conn.connect_kwargs.get("dbname") == "test")

# 2. connect 端口空 → 默认5432
conn2 = Postgres.connect(host="h", user="u", password="p", dbname="d")
check("connect 空端口默认5432", conn2.connect_kwargs.get("port") == 5432)

# 3. connect 失败 (database 组件 BaseException 是内置名, except BaseException:raise 前置 → 驱动错误原样抛, 与 Database/Sqlite 一致)
FAIL_CONNECT["on"] = True
expect_error("connect 失败抛原始异常", lambda: Postgres.connect(host="x", user="u", password="p", dbname="d"),
             "connection refused")
FAIL_CONNECT["on"] = False

# 4. execute_sql 受影响行数 + commit + 游标关闭
conn.report_rowcount = 3
n = Postgres.execute_sql(conn=conn, sql="UPDATE users SET age=20")
check("execute_sql 返回受影响行数", n == 3)
check("execute_sql 提交事务", conn.commits == 1)
check("execute_sql 关闭游标", conn.cursors[-1].closed)

# 5. execute_sql DDL rowcount=-1 → 0
conn.report_rowcount = -1
n = Postgres.execute_sql(conn=conn, sql="CREATE TABLE t(id int)")
check("execute_sql DDL 行数归0", n == 0)

# 6. execute_sql 缺连接
expect_error("execute_sql 缺连接", lambda: Postgres.execute_sql(conn=None, sql="SELECT 1"), "缺少PostgreSQL数据库连接对象")

# 7. execute_sql 执行异常 (原样抛出驱动错误)
conn.fail_execute = True
expect_error("execute_sql 执行异常", lambda: Postgres.execute_sql(conn=conn, sql="BAD SQL"), "syntax error")
conn.fail_execute = False

# 8. query_table 字段+条件
conn.desc = [("name",), ("age",)]
conn.fetch_rows = [("张三", 18), ("李四", 20)]
r = Postgres.query_table(conn=conn, table_name="users", fields=["name", "age"], where="age > 15")
sql_captured = conn.cursors[-1].execute_calls[0][0]
check("query_table SQL拼接", sql_captured == 'SELECT "name", "age" FROM "users" WHERE age > 15')
check("query_table 首行列名", r[0][0] == "name" and r[0][1] == "age")
check("query_table 数据行", len(r) == 3 and r[1] == ["张三", 18])

# 9. query_table 空 fields/空 where → SELECT *
conn.desc = []
conn.fetch_rows = []
r2 = Postgres.query_table(conn=conn, table_name="users")
sql2 = conn.cursors[-1].execute_calls[0][0]
check("query_table 全字段无条件", sql2 == 'SELECT * FROM "users"')

# 10. query_table 标识符双引号转义
Postgres.query_table(conn=conn, table_name='us"ers', fields=["a"])
sql3 = conn.cursors[-1].execute_calls[0][0]
check("query_table 标识符防注入", sql3 == 'SELECT "a" FROM "us""ers"')

# 11. query_table 空表名
expect_error("query_table 空表名", lambda: Postgres.query_table(conn=conn, table_name=""), "表名不能为空")

# 12. insert_dict 字典参数化
conn.report_rowcount = 1
d = {"name": "张三", "age": 18}
n = Postgres.insert_dict(conn=conn, table_name="users", data=d)
sql_i, params_i = conn.cursors[-1].execute_calls[0]
check("insert_dict SQL", sql_i == 'INSERT INTO "users" ("name", "age") VALUES (%(name)s, %(age)s)')
check("insert_dict 字典绑定", params_i is d)
check("insert_dict 行数", n == 1)

# 13. insert_dict 非字典
expect_error("insert_dict 非字典", lambda: Postgres.insert_dict(conn=conn, table_name="users", data=["x"]), "必须是字典")

# 14. insert_dict 失败回滚
conn.fail_execute = True
expect_error("insert_dict 失败报错", lambda: Postgres.insert_dict(conn=conn, table_name="users", data={"a": 1}), "syntax error")
check("insert_dict 失败回滚", conn.rollbacks >= 1)
conn.fail_execute = False

# 15. batch_insert 分批: 5行上限2 → executemany×3, commit×3
conn_b = FakeConnection()
data5 = [["n%d" % i, i] for i in range(5)]
total = Postgres.batch_insert(conn=conn_b, table_name="users", columns=["name", "age"], data=data5, batch_size=2)
calls = conn_b.cursors[-1].executemany_calls
check("batch_insert 分3批", len(calls) == 3)
check("batch_insert 批大小", [len(c[1]) for c in calls] == [2, 2, 1])
check("batch_insert 累计行数", total == 5)
check("batch_insert 每批提交", conn_b.commits == 3)
sql_b = calls[0][0]
check("batch_insert 占位符%s", sql_b == 'INSERT INTO "users" ("name", "age") VALUES (%s, %s)')
check("batch_insert 行转元组", all(isinstance(row, tuple) for row in calls[0][1]))

# 16. batch_insert 空上限 → 默认单批
conn_c = FakeConnection()
Postgres.batch_insert(conn=conn_c, table_name="t", columns=["a"], data=[[1], [2]], batch_size=None)
check("batch_insert 默认单批", len(conn_c.cursors[-1].executemany_calls) == 1)

# 17/18. batch_insert 参数校验
expect_error("batch_insert 非二维", lambda: Postgres.batch_insert(conn=conn_b, table_name="t", columns=["a"], data=["x"]),
             "必须是二维列表")
expect_error("batch_insert 列名非列表", lambda: Postgres.batch_insert(conn=conn_b, table_name="t", columns="a", data=[[1]]),
             "列名必须是列表")

# 19. batch_insert 中途失败回滚
conn_d = FakeConnection()
conn_d.fail_executemany = True
expect_error("batch_insert 失败报错",
             lambda: Postgres.batch_insert(conn=conn_d, table_name="t", columns=["a"], data=[[1], [2]]), "duplicate key")
check("batch_insert 失败回滚", conn_d.rollbacks == 1)

# 20/21. close
Postgres.close(conn=conn_b)
check("close 关闭连接", conn_b.closes == 1)
Postgres.close(conn=None)
check("close 空连接不报错", True)

ok = sum(1 for _, c in RESULTS if c)
print("\n===== %d/%d PASS =====" % (ok, len(RESULTS)))
sys.exit(0 if ok == len(RESULTS) else 1)
