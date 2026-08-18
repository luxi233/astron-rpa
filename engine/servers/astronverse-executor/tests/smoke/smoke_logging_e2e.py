"""运行日志全流程集成测试: 原子执行 → atomic_run 埋点 → Report 落盘。

验证作为排查工具的核心链路端到端有效:
1. standard: 成功原子无落盘(START是tip), 失败原子落盘error+堆栈+耗时
2. debug: 成功原子落盘参数摘要(敏感掩码)+结果, 失败原子同standard
3. off: 完全不落盘
4. 非法级别回退 standard
5. 级别切换运行时即时生效
6. 落盘行可解析且字段完整(process_id/line/atomic/key)

运行: cd engine/servers/astronverse-executor && .venv/bin/python tests/smoke/smoke_logging_e2e.py
"""

import json
import os
import sys
import tempfile

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


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from astronverse.actionlib import ReportCodeStatus  # noqa: E402
from astronverse.actionlib.atomic import atomicMg  # noqa: E402
from astronverse.actionlib.report import report  # noqa: E402
from astronverse.executor.debug.report import Report  # noqa: E402


# ---------- fake svc (复用 smoke_logging_report 的结构) ----------
class FakeProc:
    def __init__(self, process_id, process_name, process_meta=None):
        self.process_id = process_id
        self.process_name = process_name
        self.process_meta = process_meta or []


class FakeDebug:
    def find_log_position(self):
        return ("p1", 3)


class FakeAstGlobals:
    def __init__(self, process_info):
        self.process_info = process_info


class FakeSvc:
    def __init__(self, conf, process_info):
        self.conf = conf
        self.ast_globals = FakeAstGlobals(process_info)
        self.debug = FakeDebug()


@atomicMg.atomic("SmokeE2E", outputList=[atomicMg.param("res", types="Str")])
def e2e_step(url: str = "", password: str = "", fail: bool = False):
    if fail:
        raise ValueError("连接失败")
    return "done"


def make_report(td, exec_id="execE"):
    pinfo = {"p1": FakeProc("p1", "主流程", [[7, "line-7-id", "测试原子", "SmokeE2E.e2e_step"]])}
    conf = type(
        "C",
        (),
        {"log_path": td, "project_id": "proj1", "exec_id": exec_id, "log_retention_days": 30, "open_log_ws": False},
    )()
    r = Report(FakeSvc(conf, pinfo))
    report.set_code(r)  # 全局 report 单例挂到真实 Report → 文件落盘
    return r, os.path.join(td, "report", "proj1", f"{exec_id}.txt")


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_step(**kwargs):
    return e2e_step(__info__=[7, "p1"], **kwargs)


with tempfile.TemporaryDirectory() as td:
    reports = []
    try:
        # ---------- 1. standard ----------
        r, log_file = make_report(td, "execS")
        reports.append(r)
        atomicMg.cfg()["LOG_LEVEL"] = "standard"
        run_step(url="http://a", password="secret")
        lines = read_lines(log_file)
        check("standard成功: 无落盘(START为tip)", len(lines) == 0, f"got {len(lines)}")

        try:
            run_step(fail=True)
        except ValueError:
            pass
        lines = read_lines(log_file)
        check("standard失败: error落盘", len(lines) == 1 and lines[0]["data"]["log_level"] == "error")
        err = lines[0]["data"] if lines else {}
        check(
            "standard失败: 消息含异常类型与文本",
            "ValueError" in str(err.get("msg_str")) and "连接失败" in str(err.get("msg_str")),
        )
        check("standard失败: 堆栈落盘", "Traceback" in str(err.get("error_traceback", "")))
        check("standard失败: cost_ms落盘", err.get("cost_ms") is not None)
        check("standard失败: 行号7/流程p1", err.get("line") == 7 and err.get("process_id") == "p1")
        check("standard失败: atomic/key填充", err.get("atomic") == "测试原子" and err.get("key") == "SmokeE2E.e2e_step")

        # ---------- 2. debug (独立exec_id, 避免句柄指向被删inode) ----------
        r, log_file = make_report(td, "execD")
        reports.append(r)
        atomicMg.cfg()["LOG_LEVEL"] = "debug"
        run_step(url="http://a", password="secret")
        r.flush()  # 缓冲写: 读取前显式刷盘
        lines = read_lines(log_file)
        params = [l["data"] for l in lines if "参数:" in str(l["data"].get("msg_str"))]
        results = [l["data"] for l in lines if l["data"].get("msg_str") == "done"]
        check("debug成功: 参数摘要落盘", len(params) == 1)
        if params:
            p = str(params[0]["msg_str"])
            check("debug成功: 敏感参数掩码", "password=***" in p and "secret" not in p, p)
            check("debug成功: 非敏感参数明文", "url=http://a" in p, p)
        check("debug成功: 结果落盘", len(results) == 1 and results[0].get("cost_ms") is not None)

        # ---------- 3. off ----------
        r, log_file = make_report(td, "execO")
        reports.append(r)
        atomicMg.cfg()["LOG_LEVEL"] = "off"
        run_step(url="http://a")
        try:
            run_step(fail=True)
        except ValueError:
            pass
        check("off: 成功与失败均不落盘", len(read_lines(log_file)) == 0)

        # ---------- 4. 非法级别回退 ----------
        r, log_file = make_report(td, "execX")
        reports.append(r)
        atomicMg.cfg()["LOG_LEVEL"] = "verbose"
        try:
            run_step(fail=True)
        except ValueError:
            pass
        check("非法级别: 回退standard(error仍落盘)", len(read_lines(log_file)) == 1)

        # ---------- 5. 运行时切换级别即时生效 ----------
        r, log_file = make_report(td, "execW")
        reports.append(r)
        atomicMg.cfg()["LOG_LEVEL"] = "off"
        run_step(url="http://a")
        check("切换前: off无落盘", len(read_lines(log_file)) == 0)
        atomicMg.cfg()["LOG_LEVEL"] = "debug"
        run_step(url="http://b")
        r.flush()  # 缓冲写: 读取前显式刷盘
        after = read_lines(log_file)
        check(
            "级别切换: off→debug 即时生效",
            len(after) == 2 and any("url=http://b" in str(l["data"].get("msg_str")) for l in after),
            f"got {len(after)}",
        )

        # ---------- 6. 级别不影响执行结果 ----------
        atomicMg.cfg()["LOG_LEVEL"] = "off"
        res = run_step(url="http://x")
        check("执行: off级别返回值不受影响", res == "done")
    finally:
        report.set_code(None)
        atomicMg.cfg()["LOG_LEVEL"] = "standard"
        for rr in reports:
            rr.close()

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
