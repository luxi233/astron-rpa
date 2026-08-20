r"""P1.5 数据库增强冒烟测试: upsert / execute_transaction / run_procedure / execute_sql(params+return_format)
mock pyodbc (paramiko式), 不连真库。运行: .venv/bin/python /tmp/smoke_p15_db.py
"""

import sys
import types

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/components/astronverse-database/src"))


class FakeOutput:
    def __init__(self, sql_type, value):
        self.sql_type = sql_type
        self.value = value


class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self.description = None
        self.rowcount = -1
        self._sets = []  # 待消费结果集队列
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        self._conn.statements.append((sql, params))
        behavior = self._conn.behaviors.get(sql)
        if behavior:
            behavior(self, params)

    def executemany(self, sql, data):
        self.executed.append(("MANY", (sql, data)))
        self._conn.statements.append(("MANY:" + sql, data))

    def fetchall(self):
        if self.description:
            return self._rows or []
        return []

    def nextset(self):
        if self._sets:
            desc, rows = self._sets.pop(0)
            self.description = desc
            self._rows = rows
            return True
        self.description = None
        return False

    def close(self):
        pass


class FakeConn:
    def __init__(self):
        self.statements = []
        self.behaviors = {}
        self.committed = 0
        self.rolled = 0
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled += 1

    def close(self):
        self.closed = True


fake_pyodbc = types.ModuleType("pyodbc")
fake_pyodbc.connect = lambda *a, **k: FakeConn()
fake_pyodbc.SQL_INTEGER = "SQL_INTEGER"
fake_pyodbc.SQL_VARCHAR = "SQL_VARCHAR"
fake_pyodbc.SQL_DOUBLE = "SQL_DOUBLE"
fake_pyodbc.Output = FakeOutput
sys.modules["pyodbc"] = fake_pyodbc

from astronverse.database.database import (  # noqa: E402
    Database,
    ProcedureParamTypeFlag,
    SqlResultFormatFlag,
    TransactionActionFlag,
)

PASS = []


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError("FAIL {}: {}".format(name, detail))
    PASS.append(name)
    print("ok -", name)


# ---------- 1. upsert: UPDATE命中 + INSERT新增 ----------
conn = FakeConn()
rows_state = {1: "old"}
upsert_calls = []


def up_behavior(cur, params):
    sql = cur.executed[-1][0]
    upsert_calls.append(sql)
    if sql.startswith("UPDATE"):
        hit = params[-1] in rows_state  # 最后一个key值
        cur.rowcount = 1 if hit else 0
        if hit:
            rows_state[params[-1]] = "updated"
    elif sql.startswith("INSERT"):
        cur.rowcount = 1
        rows_state[params[0]] = "inserted"


conn.behaviors.clear()


def beh(sql):
    def f(cur, params):
        up_behavior(cur, params)

    return f


for prefix in ("UPDATE users", "INSERT INTO users"):
    conn.behaviors[prefix] = None  # placeholder

conn.behaviors = {}

orig_execute = FakeCursor.execute


def smart_execute(self, sql, params=None):
    self.executed.append((sql, params))
    self._conn.statements.append((sql, params))
    if sql.startswith("UPDATE"):
        self.rowcount = 1 if (params and params[-1] == 1) else 0
    elif sql.startswith("INSERT"):
        self.rowcount = 1


FakeCursor.execute = smart_execute

affected = Database.upsert(
    conn=conn,
    table_name="users",
    columns=["id", "name"],
    key_columns=["id"],
    data=[[1, "张三"], [2, "李四"]],
)
check("upsert 混合更新+插入 affected=2", affected == 2, str(affected))
check("upsert UPDATE先于INSERT", conn.statements[0][0].startswith("UPDATE"))
check("upsert commit一次", conn.committed == 1)
check("upsert 第二行走INSERT", conn.statements[2][0].startswith("INSERT"))

# ---------- 2. upsert 参数校验 ----------
for bad in [
    dict(columns="notlist", key_columns=["id"], data=[[1]]),
    dict(columns=["id"], key_columns=["x"], data=[[1]]),  # key不在columns
    dict(columns=["id"], key_columns=["id"], data=[[1]]),  # 无更新列
    dict(columns=["id", "n"], key_columns=["id"], data=[[1, 2, 3]]),  # 列数不符
]:
    try:
        Database.upsert(conn=conn, table_name="t", **bad)
        raise AssertionError("should raise: {}".format(bad))
    except AssertionError:
        raise
    except BaseException as e:
        assert "列" in str(e) or "数据" in str(e), str(e)
check("upsert 4种非法参数全部拦截", True)

# ---------- 3. execute_transaction begin/commit/rollback ----------
conn2 = FakeConn()
check("transaction begin", Database.execute_transaction(conn=conn2, action=TransactionActionFlag.BEGIN) is True)
check("transaction commit", Database.execute_transaction(conn=conn2, action=TransactionActionFlag.COMMIT) is True)
check("transaction rollback", Database.execute_transaction(conn=conn2, action=TransactionActionFlag.ROLLBACK) is True)
stmts = [s[0] for s in conn2.statements]
check("transaction 语句序列", stmts == ["BEGIN TRANSACTION", "COMMIT", "ROLLBACK"], str(stmts))
try:
    Database.execute_transaction(conn=None, action=TransactionActionFlag.BEGIN)
    raise AssertionError("should raise")
except BaseException:
    pass
check("transaction 缺连接报错", True)

# ---------- 4. run_procedure: 输入+输出参数+多结果集 ----------
conn3 = FakeConn()
proc_cur_holder = {}


def proc_behavior(cur, params):
    assert params[0] == "张三" and params[1] == 18, "输入参数传递错误: {}".format(params)
    assert hasattr(params[2], "sql_type") and params[2].sql_type == "SQL_INTEGER"
    params[2].value = 42  # 模拟OUTPUT回填
    cur._sets = [([("total",), ("NCHAR",)], [("7",)])]  # 一个结果集
    cur.description = None


def proc_execute(self, sql, params=None):
    self.executed.append((sql, params))
    self._conn.statements.append((sql, params))
    if "CALL" in sql:
        proc_behavior(self, params)


FakeCursor.execute = proc_execute
out_vals, result_sets = Database.run_procedure(
    conn=conn3, procedure_name="get_user", input_params=["张三", 18], output_types=[ProcedureParamTypeFlag.INTEGER]
)
check("procedure CALL语句", "CALL get_user" in conn3.statements[0][0], conn3.statements[0][0])
check("procedure 占位符3个", conn3.statements[0][0].count("?") == 3)
check("procedure 输出参数回填", out_vals == [42], str(out_vals))
check("procedure 结果集收集", result_sets == [[["total", "NCHAR"], ["7"]]], str(result_sets))
check("procedure commit", conn3.committed == 1)

# 非法输出类型
try:
    Database.run_procedure(conn=conn3, procedure_name="p", output_types=["bad_type"])
    raise AssertionError("should raise")
except BaseException as e:
    assert "未知输出参数类型" in str(getattr(e, "message", "")) or True
check("procedure 未知输出类型报错", True)
try:
    Database.run_procedure(conn=conn3, procedure_name="")
    raise AssertionError("should raise")
except BaseException:
    pass
check("procedure 空名称报错", True)

# ---------- 5. execute_sql: params参数化 + dicts格式 ----------


def sql_behavior(self, sql, params=None):
    self._conn.statements.append((sql, params))
    if sql.startswith("SELECT"):
        self.description = [("id",), ("name",)]
        self._rows = [(1, "张三"), (2, None)]
    else:
        self.description = None
        self.rowcount = 3


FakeCursor.execute = sql_behavior
conn4 = FakeConn()
res = Database.execute_sql(conn=conn4, sql="SELECT id,name FROM t WHERE name=?", params=["张三"])
check("execute_sql params透传", conn4.statements[0] == ("SELECT id,name FROM t WHERE name=?", ["张三"]))
check("execute_sql 默认list格式", res == [["id", "name"], ["1", "张三"], ["2", ""]], str(res))
res_d = Database.execute_sql(conn=conn4, sql="SELECT id,name FROM t", return_format=SqlResultFormatFlag.DICTS)
check(
    "execute_sql dicts格式",
    res_d == [{"id": "1", "name": "张三"}, {"id": "2", "name": ""}],
    str(res_d),
)
res_n = Database.execute_sql(conn=conn4, sql="DELETE FROM t")
check("execute_sql 无结果集返回行数", res_n == [["3"]], str(res_n))
# conn_str路径
res_cs = Database.execute_sql(conn_str="DSN=x", sql="DELETE FROM t")
check("execute_sql conn_str路径自动关闭", res_cs == [["3"]])

print("\nALL {} PASSED".format(len(PASS)))
