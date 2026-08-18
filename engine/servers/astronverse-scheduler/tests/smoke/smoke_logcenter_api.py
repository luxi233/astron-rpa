"""统一日志中心(logcenter) API 冒烟测试: 分类列表/下载/尾读/分类清理/路径穿越防护/保留配置。

依赖 httpx(TestClient 需要), 缺失时 SKIP。

运行: cd engine/servers/astronverse-scheduler && uv run --with httpx python tests/smoke/smoke_logcenter_api.py
"""

import json
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

from astronverse.scheduler.apis.connector.logcenter import (  # noqa: E402
    load_retention_config,
    router,
)

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


# LOG_BASE_DIR/RUNLOG_DIR 相对 cwd, 切到临时目录隔离(避免 startup 自动清理真实日志)
os.chdir(tempfile.mkdtemp())
app = FastAPI()
app.include_router(router, prefix="/logcenter")
client = TestClient(app)


def touch_run(rel, content="x", age_days=None):
    p = os.path.join("logs", "report", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(content)
    if age_days is not None:
        t = time.time() - age_days * 86400
        os.utime(p, (t, t))
    return p


def touch_engine(name, content="x", age_days=None):
    os.makedirs("logs", exist_ok=True)
    p = os.path.join("logs", name)
    with open(p, "w") as f:
        f.write(content)
    if age_days is not None:
        t = time.time() - age_days * 86400
        os.utime(p, (t, t))
    return p


# ---------- 1. run 列表 ----------
touch_run("proj1/exec_a.txt", "log-a")
touch_run("proj2/exec_b.txt", "log-b")

r = client.get("/logcenter/list", params={"category": "run"}).json()
check("run list: 全部2条", r["data"]["total"] == 2, str(r))
check("run list: exec_id正确", {i["exec_id"] for i in r["data"]["list"]} == {"exec_a", "exec_b"})
check("run list: project_id正确", {i["project_id"] for i in r["data"]["list"]} == {"proj1", "proj2"})

r = client.get("/logcenter/list", params={"category": "run", "project_id": "proj2"}).json()
check("run list: 按工程过滤", r["data"]["total"] == 1 and r["data"]["list"][0]["exec_id"] == "exec_b")

r = client.get("/logcenter/list", params={"category": "run", "project_id": "no_such"}).json()
check("run list: 不存在的工程空列表", r["data"]["total"] == 0)

# ---------- 2. engine 列表 ----------
today = time.strftime("%Y-%m-%d")
touch_engine(f"executor-{today}.log", "e-today")
touch_engine("executor-2020-01-01.log", "e-old", age_days=1)
touch_engine("main.log", "electron-main")

r = client.get("/logcenter/list", params={"category": "engine"}).json()
names = {i["name"] for i in r["data"]["list"]}
check("engine list: 3条日志文件", r["data"]["total"] == 3, str(r))
check("engine list: 含设计器main.log", "main.log" in names)
check("engine list: 返回目录字段", bool(r["data"]["dir"]))

# 默认类别=run
r = client.get("/logcenter/list").json()
check("list: 默认类别run", r["data"]["total"] == 2, str(r))

# ---------- 3. download ----------
r = client.get("/logcenter/download", params={"category": "run", "path": "proj1/exec_a.txt"})
check("download: run内容一致", r.status_code == 200 and r.text == "log-a")

r = client.get("/logcenter/download", params={"category": "engine", "path": "main.log"})
check("download: engine内容一致", r.status_code == 200 and r.text == "electron-main")

r = client.get("/logcenter/download", params={"category": "run", "path": "proj1/nope.txt"})
check("download: 不存在报错", r.status_code == 200 and r.json()["code"] != 0)

r = client.get("/logcenter/download", params={"category": "run", "path": "../../etc/passwd"})
check("download: 路径穿越拦截", r.status_code != 200 or "root:" not in r.text)

r = client.get("/logcenter/download", params={"category": "run", "path": "/etc/passwd"})
check("download: 绝对路径拦截", r.status_code != 200 or "root:" not in r.text)

r = client.get("/logcenter/download", params={"category": "engine", "path": "report/x.txt"})
check("download: engine裸文件名校验", r.status_code == 200 and r.json()["code"] != 0)

# ---------- 4. engine 尾读 ----------
r = client.post("/logcenter/read", json={"filename": "main.log", "tail_lines": 10}).json()
check("read: 读取成功", r["code"] == "0000" and r["data"]["lines"] == ["electron-main"], str(r))

r = client.post("/logcenter/read", json={"filename": "../report/proj1/exec_a.txt", "tail_lines": 10}).json()
check("read: 路径穿越拦截", r["code"] != 0)

r = client.post("/logcenter/read", json={"filename": "no_such.log", "tail_lines": 10}).json()
check("read: 不存在报错", r["code"] != 0)

# 大文件截断: 写 >4MB, 验证只返回尾部
big = touch_engine("big.log", "a" * 200 + "\n" + "tail-line\n" * 100)
with open(big, "w") as f:
    f.write("first\n" + "x" * (5 * 1024 * 1024) + "\nlast\n")
r = client.post("/logcenter/read", json={"filename": "big.log", "tail_lines": 5000}).json()
check("read: 大文件truncated标记", r["data"]["truncated"] is True, str(r.get("data", {}).get("truncated")))
check("read: 尾部含last", "last" in r["data"]["lines"], str(r["data"]["lines"][-2:]))
check("read: 截断首行被丢弃", "first" not in r["data"]["lines"])

# ---------- 5. clear: engine 当天保护 + before_days ----------
r = client.post("/logcenter/clear", json={"category": "engine", "before_days": 0}).json()
check("clear engine: 跳过当天与main.log", r["data"]["removed"] == 2, str(r))  # 2020旧log+big.log
check(
    "clear engine: 当天文件保留",
    os.path.exists(f"logs/executor-{today}.log") and os.path.exists("logs/main.log"),
)

touch_engine("executor-2020-01-02.log", age_days=1)
r = client.post("/logcenter/clear", json={"category": "engine", "before_days": 30}).json()
check("clear engine: before_days=30不删1天前", r["data"]["removed"] == 0, str(r))

# ---------- 6. clear: run 过期/按工程/全部 ----------
touch_run("proj3/old.txt", age_days=40)
touch_run("proj3/new.txt")
r = client.post("/logcenter/clear", json={"category": "run", "before_days": 30}).json()
check("clear run: 只删过期", r["data"]["removed"] == 1, str(r))
check(
    "clear run: 过期已删/未过期保留",
    not os.path.exists("logs/report/proj3/old.txt") and os.path.exists("logs/report/proj3/new.txt"),
)

r = client.post("/logcenter/clear", json={"category": "run", "project_id": "proj1"}).json()
check("clear run: 按工程删除", r["data"]["removed"] == 1 and not os.path.exists("logs/report/proj1/exec_a.txt"))
check("clear run: 其他工程不受影响", os.path.exists("logs/report/proj2/exec_b.txt"))

r = client.post("/logcenter/clear", json={"category": "all"}).json()
leftover = [os.path.join(d, f) for d, _, fs in os.walk("logs/report") for f in fs if f.endswith(".txt")]
check("clear all: run全部删除", not leftover, str(leftover))
check(
    "clear all: 引擎侧只剩保护文件",
    sorted(os.listdir("logs")) == ["executor-" + today + ".log", "main.log", "report"],
    str(os.listdir("logs")),
)

# ---------- 7. 保留配置读取(优先级/旧字段迁移) ----------
with open(".setting.json", "w") as f:
    json.dump({"logSetting": {"runRetentionDays": 90, "engineRetentionDays": 15}}, f)
rd, ed = load_retention_config()
check("config: 分类字段读取", (rd, ed) == (90, 15), f"{rd},{ed}")

with open(".setting.json", "w") as f:
    json.dump({"logSetting": {"retentionDays": 90}}, f)
rd, ed = load_retention_config()
check("config: 旧字段迁移(run=90, engine=min(90,7))", (rd, ed) == (90, 7), f"{rd},{ed}")

with open(".setting.json", "w") as f:
    f.write("{invalid json")
rd, ed = load_retention_config()
check("config: 异常回退默认(30,7)", (rd, ed) == (30, 7), f"{rd},{ed}")

# ---------- 8. 空目录容错 ----------
os.makedirs("empty_dir", exist_ok=True)
os.chdir("empty_dir")
r = client.get("/logcenter/list", params={"category": "run"}).json()
check("list: 无日志目录时空列表", r["data"]["total"] == 0)
r = client.get("/logcenter/list", params={"category": "engine"}).json()
check("list: 引擎日志目录不存在时空列表", r["data"]["total"] == 0)
r = client.post("/logcenter/clear", json={"category": "all"}).json()
check("clear: 无日志目录不报错", r["data"]["removed"] == 0)

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
