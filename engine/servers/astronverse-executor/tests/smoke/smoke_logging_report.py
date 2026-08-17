"""运行日志 Report 单元测试。

覆盖日志落盘核心链路的稳定性:
1. 初始化: 目录/文件创建
2. info/warning/error: JSONL 格式/log_level 字段/中文不转义
3. Tip 过滤: START 状态(tag=tip)与 ReportTip 不落盘
4. 占位符替换: {process}/{atomic} 及 process_meta 填充(atomic/key/line_id)
5. 非本工程 process_id 回退到 last_process_id
6. flush 即时性 + close 后容错
7. 并发写入完整性

运行: cd engine/servers/astronverse-executor && .venv/bin/python tests/smoke/smoke_logging_report.py
"""

import json
import os
import sys
import tempfile
import threading

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

from astronverse.actionlib import ReportCode, ReportCodeStatus, ReportType  # noqa: E402
from astronverse.actionlib.report import report  # noqa: E402
from astronverse.executor.debug.report import Report  # noqa: E402


# ---------- fake svc ----------
class FakeProc:
    def __init__(self, process_id, process_name, process_meta=None):
        self.process_id = process_id
        self.process_name = process_name
        # process_meta 原始为 list: [[line, line_id, atomic, key], ...], Report 初始化时转 dict
        self.process_meta = process_meta or []


class FakeDebug:
    def find_log_position(self):
        return ("p1", 3)


class FakeConf:
    def __init__(self, log_path, project_id, exec_id, retention=30):
        self.log_path = log_path
        self.project_id = project_id
        self.exec_id = exec_id
        self.log_retention_days = retention
        self.open_log_ws = False  # 关ws, 只测文件落盘


class FakeAstGlobals:
    def __init__(self, process_info):
        self.process_info = process_info


class FakeSvc:
    def __init__(self, conf, process_info):
        self.conf = conf
        self.ast_globals = FakeAstGlobals(process_info)
        self.debug = FakeDebug()


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def make_report(td, pinfo=None, exec_id="exec1"):
    if pinfo is None:
        pinfo = {
            "p1": FakeProc(
                "p1",
                "主流程",
                [[7, "line-7-id", "打开表格", "kdocs.open"]],
            )
        }
    svc = FakeSvc(FakeConf(td, "proj1", exec_id), pinfo)
    return Report(svc), os.path.join(td, "report", "proj1", f"{exec_id}.txt")


# ---------- 1. 初始化 ----------
with tempfile.TemporaryDirectory() as td:
    r, log_file = make_report(td)
    check("初始化: 目录创建", os.path.isdir(os.path.join(td, "report", "proj1")))
    check("初始化: 文件创建", os.path.isfile(log_file))
    check("初始化: 文件为空", os.path.getsize(log_file) == 0)
    r.close()

# 重复初始化(目录已存在)不崩
with tempfile.TemporaryDirectory() as td:
    r1, f1 = make_report(td)
    r1.close()
    r2, f2 = make_report(td, exec_id="exec2")
    check("初始化: 目录已存在时复用", os.path.isfile(f2))
    r2.close()

# ---------- 2. info/warning/error JSONL ----------
with tempfile.TemporaryDirectory() as td:
    r, log_file = make_report(td)
    r.info(ReportCode(process_id="p1", line=7, msg_str="步骤开始 {process} 第{line}行"))
    r.warning(ReportCode(process_id="p1", line=7, msg_str="警告消息"))
    r.error(ReportCode(process_id="p1", line=7, msg_str="错误消息", error_traceback="Traceback...", cost_ms=12))

    lines = read_lines(log_file)
    check("JSONL: 写入3行", len(lines) == 3, f"got {len(lines)}")
    check("JSONL: 每行含event_time与data", all("event_time" in l and "data" in l for l in lines))
    check("log_level: info/warning/error", [l["data"]["log_level"] for l in lines] == ["info", "warning", "error"])
    check("log_type: code", all(l["data"]["log_type"] == ReportType.Code.value for l in lines))
    check("占位符: {process}已替换", lines[0]["data"]["msg_str"] == "步骤开始 主流程 第{line}行")
    check("meta: atomic填充", lines[0]["data"].get("atomic") == "打开表格")
    check("meta: key填充", lines[0]["data"].get("key") == "kdocs.open")
    check("meta: line_id填充", lines[0]["data"].get("line_id") == "line-7-id")
    check("错误: traceback保留", lines[2]["data"]["error_traceback"] == "Traceback...")
    check("错误: cost_ms保留", lines[2]["data"]["cost_ms"] == 12)
    r.close()

# ---------- 3. Tip 过滤 ----------
with tempfile.TemporaryDirectory() as td:
    r, log_file = make_report(td)
    r.info(ReportCode(process_id="p1", line=7, status=ReportCodeStatus.START, msg_str="start"))
    r.info(ReportCode(process_id="p1", line=7, status=ReportCodeStatus.RES, msg_str="res"))

    from astronverse.actionlib import ReportTip

    r.info(ReportTip(msg_str="tip消息"))

    lines = read_lines(log_file)
    check("Tip: START不落盘", not any(l["data"].get("status") == ReportCodeStatus.START.value for l in lines))
    check("Tip: ReportTip不落盘", not any("tip消息" in str(l["data"].get("msg_str")) for l in lines))
    check("Tip: RES正常落盘", len(lines) == 1 and lines[0]["data"]["msg_str"] == "res")
    r.close()

# ---------- 4. 中文不转义 ----------
with tempfile.TemporaryDirectory() as td:
    r, log_file = make_report(td)
    r.info(ReportCode(process_id="p1", line=7, msg_str="中文消息内容测试"))
    with open(log_file, encoding="utf-8") as f:
        raw = f.read()
    check("中文: 原样写入不转义", "中文消息内容测试" in raw)
    r.close()

# ---------- 5. 非本工程 process_id 回退 ----------
with tempfile.TemporaryDirectory() as td:
    pinfo = {"p1": FakeProc("p1", "主流程", [[7, "lid", "原子A", "akey"]])}
    r, log_file = make_report(td, pinfo)
    # 先写一条本工程的, 建立 last_process_id
    r.info(ReportCode(process_id="p1", line=7, msg_str="本工程"))
    # 再写一条外部工程 id (子流程/组件)
    r.info(ReportCode(process_id="other_proj_proc", line=99, msg_str="外部"))
    lines = read_lines(log_file)
    check("回退: 外部process_id归一到p1", lines[1]["data"]["process_id"] == "p1" and lines[1]["data"]["line"] == 7)
    check("回退: process名填主流程", lines[1]["data"]["process"] == "主流程")
    r.close()

# ---------- 6. flush 即时性 + close 容错 ----------
with tempfile.TemporaryDirectory() as td:
    r, log_file = make_report(td)
    r.info(ReportCode(process_id="p1", line=7, msg_str="flush测试"))
    check("flush: 不close立即可读", len(read_lines(log_file)) == 1)
    r.close()
    check("close: 句柄关闭", r.log_local_file.closed)
    # close 后再写不崩(静默跳过)
    r.info(ReportCode(process_id="p1", line=7, msg_str="after close"))
    check("close: 后续写入容错", len(read_lines(log_file)) == 1)

# ---------- 7. 并发写入完整性 ----------
with tempfile.TemporaryDirectory() as td:
    r, log_file = make_report(td)
    N_T, N_M = 10, 20

    def worker(tid):
        for i in range(N_M):
            r.info(ReportCode(process_id="p1", line=7, msg_str=f"t{tid}-m{i}"))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(N_T)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    lines = read_lines(log_file)
    check("并发: 200条全部落盘", len(lines) == N_T * N_M, f"got {len(lines)}")
    msgs = {l["data"]["msg_str"] for l in lines}
    expect = {f"t{t}-m{i}" for t in range(N_T) for i in range(N_M)}
    check("并发: 无丢失无重复", msgs == expect)
    r.close()

# ---------- 8. 普通字符串消息(ReportScript 路径) ----------
with tempfile.TemporaryDirectory() as td:
    r, log_file = make_report(td)
    report.set_code(r)
    try:
        report.info("裸字符串消息")
    finally:
        report.set_code(None)
    lines = read_lines(log_file)
    check("字符串: 转ReportScript落盘", len(lines) == 1 and lines[0]["data"]["msg_str"] == "裸字符串消息")
    check("字符串: 挂到当前位置p1:3", lines[0]["data"]["process_id"] == "p1" and lines[0]["data"]["line"] == 3)
    check("字符串: log_type=script", lines[0]["data"]["log_type"] == ReportType.Script.value)
    r.close()

print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
