"""runlog 管理 API 冒烟测试: 列表/下载/手动清理/路径穿越防护。

依赖 httpx(TestClient 需要), 缺失时 SKIP。

运行: cd engine/servers/astronverse-scheduler && uv run --with httpx python tests/smoke/smoke_runlog_api.py
"""

import os
import sys
import tempfile
import time

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    print("[SKIP] 缺少 fastapi/TestClient 依赖")
    sys.exit(0)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

from astronverse.scheduler.apis.connector.runlog import router  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {detail}")


# RUNLOG_DIR 相对 cwd, 切到临时目录隔离
os.chdir(tempfile.mkdtemp())
app = FastAPI()
app.include_router(router, prefix="/runlog")
client = TestClient(app)


def touch(rel, content="x", age_days=None):
    p = os.path.join("logs", "report", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)
    if age_days is not None:
        t = time.time() - age_days * 86400
        os.utime(p, (t, t))
    return p


# ---------- 1. list ----------
touch("proj1/exec_a.txt", "log-a")
touch("proj2/exec_b.txt", "log-b")

r = client.get("/runlog/list").json()
check("list: 全部2条", r["data"]["total"] == 2, str(r))
check("list: exec_id正确", {i["exec_id"] for i in r["data"]["list"]} == {"exec_a", "exec_b"})
check("list: project_id正确", {i["project_id"] for i in r["data"]["list"]} == {"proj1", "proj2"})
check("list: size/mtime非空", all(i["size"] == 5 and i["mtime"] > 0 for i in r["data"]["list"]))

r = client.get("/runlog/list", params={"project_id": "proj2"}).json()
check("list: 按工程过滤", r["data"]["total"] == 1 and r["data"]["list"][0]["exec_id"] == "exec_b")

r = client.get("/runlog/list", params={"project_id": "no_such"}).json()
check("list: 不存在的工程空列表", r["data"]["total"] == 0)

# ---------- 2. download ----------
r = client.get("/runlog/download", params={"path": "proj1/exec_a.txt"})
check("download: 内容一致", r.status_code == 200 and r.text == "log-a")

r = client.get("/runlog/download", params={"path": "proj1/nope.txt"})
check("download: 不存在报错", r.status_code == 200 and r.json()["code"] != 0)

r = client.get("/runlog/download", params={"path": "../../etc/passwd"})
check("download: 路径穿越拦截", r.status_code != 200 or "root:" not in r.text)

r = client.get("/runlog/download", params={"path": "/etc/passwd"})
check("download: 绝对路径拦截", r.status_code != 200 or "root:" not in r.text)

# ---------- 3. clear before_days ----------
touch("proj3/old.txt", age_days=40)
touch("proj3/new.txt")
r = client.post("/runlog/clear", json={"before_days": 30}).json()
check("clear: before_days只删过期", r["data"]["removed"] == 1, str(r))
check(
    "clear: 过期已删/未过期保留",
    not os.path.exists("logs/report/proj3/old.txt") and os.path.exists("logs/report/proj3/new.txt"),
)

# ---------- 4. clear 全部/按工程 ----------
r = client.post("/runlog/clear", json={"project_id": "proj1"}).json()
check("clear: 按工程删除", r["data"]["removed"] == 1 and not os.path.exists("logs/report/proj1/exec_a.txt"))
check("clear: 其他工程不受影响", os.path.exists("logs/report/proj2/exec_b.txt"))

r = client.post("/runlog/clear", json={}).json()
check("clear: 清空全部", r["data"]["removed"] >= 2, str(r))
leftover = [os.path.join(d, f) for d, _, fs in os.walk("logs/report") for f in fs if f.endswith(".txt")]
check("clear: 全部已删", not leftover, str(leftover))

# ---------- 5. 空目录容错 ----------
os.makedirs("empty_dir")
os.chdir(os.path.join("empty_dir"))
r = client.get("/runlog/list").json()
check("list: 无日志目录时空列表", r["data"]["total"] == 0)
r = client.post("/runlog/clear", json={}).json()
check("clear: 无日志目录不报错", r["data"]["removed"] == 0)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
