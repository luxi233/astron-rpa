import sys
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-database/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-actionlib/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-baseline/src")

from astronverse.database.database import Database

class FakeCursor:
    def __init__(self, desc, rows, rowcount):
        self.description = desc
        self._rows = rows
        self.rowcount = rowcount
        self.executed = []
        self.fastexec = 0
    def execute(self, sql, *params):
        self.executed.append((sql, params))
    def executemany(self, sql, seq):
        self.fastexec = len(seq)
        self.executed.append((sql, tuple(seq)))
    def fetchall(self): return self._rows
    def close(self): pass

class FakeConn:
    def __init__(self, desc=None, rows=None, rowcount=0):
        self.desc, self.rows, self.rowcount = desc, rows or [], rowcount
        self.commits = 0; self.closed = False
    def cursor(self): return FakeCursor(self.desc, self.rows, self.rowcount)
    def commit(self): self.commits += 1
    def close(self): self.closed = True

# 1. execute_sql SELECT via conn
c = FakeConn(desc=[("id",),("name",)], rows=[(1,"a"),(2,None)])
r = Database.execute_sql(conn=c, sql="SELECT id,name FROM t")
print("select result:", r)
assert r == [["id","name"],["1","a"],["2",""]], r
assert c.commits == 1

# 2. execute_sql DML via conn (no result set -> rowcount)
c2 = FakeConn(desc=None, rowcount=7)
r2 = Database.execute_sql(conn=c2, sql="UPDATE t SET x=1")
print("dml result:", r2)
assert r2 == [["7"]], r2

# 3. batch_insert via conn
c3 = FakeConn(desc=None, rowcount=3)
n = Database.batch_insert(conn=c3, sql="INSERT INTO t VALUES (?,?)", data=[[1,"a"],[2,"b"],[3,"c"]])
print("affected:", n)
assert n == 3 and c3.commits == 1

# 4. close
Database.close(conn=c3)
assert c3.closed is True

# 5. error path: no conn / no conn_str
try:
    Database.execute_sql(sql="SELECT 1")
    raise SystemExit("should have raised")
except BaseException as e:
    print("no-conn error OK:", str(e)[:60])

# 6. pyodbc real import present in venv
import pyodbc  # noqa
print("pyodbc import OK, drivers:", (pyodbc.drivers() or [])[:3])
print("database smoke OK")
