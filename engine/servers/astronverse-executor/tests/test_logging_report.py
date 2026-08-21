"""J2: 运行日志 Report 落盘单测 pytest 版(原 tests/smoke/smoke_logging_report.py)。

覆盖日志落盘核心链路的稳定性:
1. 初始化: 目录/文件创建与复用
2. info/warning/error: JSONL 格式/log_level 字段/占位符替换/meta 填充
3. Tip 过滤: START 状态(tag=tip)与 ReportTip 不落盘
4. 中文不转义
5. 非本工程 process_id 回退到 last_process_id
6. flush 即时性 + close 后容错
7. 并发写入完整性
8. 裸字符串消息走 ReportScript 路径
"""

import json
import os
import threading

import pytest

from astronverse.actionlib import ReportCode, ReportCodeStatus, ReportTip, ReportType
from astronverse.actionlib.report import report
from astronverse.executor.debug.report import Report


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


@pytest.fixture
def factory(tmp_path):
    """Report 工厂: 会话结束统一 close, 避免句柄泄漏"""
    td = str(tmp_path)
    created = []

    def make(pinfo=None, exec_id="exec1"):
        if pinfo is None:
            pinfo = {"p1": FakeProc("p1", "主流程", [[7, "line-7-id", "打开表格", "kdocs.open"]])}
        r = Report(FakeSvc(FakeConf(td, "proj1", exec_id), pinfo))
        created.append(r)
        return r, os.path.join(td, "report", "proj1", f"{exec_id}.txt")

    yield make
    for r in created:
        r.close()


def test_初始化目录与文件创建(factory, tmp_path):
    r, log_file = factory()
    assert os.path.isdir(os.path.join(str(tmp_path), "report", "proj1"))
    assert os.path.isfile(log_file)
    assert os.path.getsize(log_file) == 0


def test_目录已存在时复用(factory):
    factory()
    _, f2 = factory(exec_id="exec2")
    assert os.path.isfile(f2)


def test_jsonl格式与meta填充(factory):
    r, log_file = factory()
    r.info(ReportCode(process_id="p1", line=7, msg_str="步骤开始 {process} 第{line}行"))
    r.warning(ReportCode(process_id="p1", line=7, msg_str="警告消息"))
    r.error(ReportCode(process_id="p1", line=7, msg_str="错误消息", error_traceback="Traceback...", cost_ms=12))
    r.flush()  # 缓冲写: 读取前显式刷盘(首条已即时刷, 后续2s窗口合并)

    lines = read_lines(log_file)
    assert len(lines) == 3
    assert all("event_time" in l and "data" in l for l in lines)
    assert [l["data"]["log_level"] for l in lines] == ["info", "warning", "error"]
    assert all(l["data"]["log_type"] == ReportType.Code.value for l in lines)
    # {process} 已替换; {line} 不在占位符替换范围保留原样
    assert lines[0]["data"]["msg_str"] == "步骤开始 主流程 第{line}行"
    assert lines[0]["data"].get("atomic") == "打开表格"
    assert lines[0]["data"].get("key") == "kdocs.open"
    assert lines[0]["data"].get("line_id") == "line-7-id"
    assert lines[2]["data"]["error_traceback"] == "Traceback..."
    assert lines[2]["data"]["cost_ms"] == 12


def test_tip过滤(factory):
    r, log_file = factory()
    r.info(ReportCode(process_id="p1", line=7, status=ReportCodeStatus.START, msg_str="start"))
    r.info(ReportCode(process_id="p1", line=7, status=ReportCodeStatus.RES, msg_str="res"))
    r.info(ReportTip(msg_str="tip消息"))
    r.flush()

    lines = read_lines(log_file)
    assert not any(l["data"].get("status") == ReportCodeStatus.START.value for l in lines)
    assert not any("tip消息" in str(l["data"].get("msg_str")) for l in lines)
    assert len(lines) == 1 and lines[0]["data"]["msg_str"] == "res"


def test_中文原样写入不转义(factory):
    r, log_file = factory()
    r.info(ReportCode(process_id="p1", line=7, msg_str="中文消息内容测试"))
    with open(log_file, encoding="utf-8") as f:
        assert "中文消息内容测试" in f.read()


def test_非本工程process_id回退(factory):
    pinfo = {"p1": FakeProc("p1", "主流程", [[7, "lid", "原子A", "akey"]])}
    r, log_file = factory(pinfo)
    # 先写一条本工程的, 建立 last_process_id
    r.info(ReportCode(process_id="p1", line=7, msg_str="本工程"))
    # 再写一条外部工程 id (子流程/组件)
    r.info(ReportCode(process_id="other_proj_proc", line=99, msg_str="外部"))
    r.flush()
    lines = read_lines(log_file)
    assert lines[1]["data"]["process_id"] == "p1" and lines[1]["data"]["line"] == 7
    assert lines[1]["data"]["process"] == "主流程"


def test_flush即时性与close容错(factory):
    r, log_file = factory()
    r.info(ReportCode(process_id="p1", line=7, msg_str="flush测试"))
    assert len(read_lines(log_file)) == 1  # 不 close 立即可读(首条即时刷)
    r.close()
    assert r.log_local_file.closed
    # close 后再写不崩(静默跳过)
    r.info(ReportCode(process_id="p1", line=7, msg_str="after close"))
    assert len(read_lines(log_file)) == 1


def test_并发写入完整性(factory):
    r, log_file = factory()
    n_t, n_m = 10, 20

    def worker(tid):
        for i in range(n_m):
            r.info(ReportCode(process_id="p1", line=7, msg_str=f"t{tid}-m{i}"))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_t)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    r.flush()
    lines = read_lines(log_file)
    assert len(lines) == n_t * n_m
    msgs = {l["data"]["msg_str"] for l in lines}
    assert msgs == {f"t{t}-m{i}" for t in range(n_t) for i in range(n_m)}


def test_裸字符串消息走ReportScript(factory):
    r, log_file = factory()
    report.set_code(r)
    try:
        report.info("裸字符串消息")
    finally:
        report.set_code(None)
    lines = read_lines(log_file)
    assert len(lines) == 1 and lines[0]["data"]["msg_str"] == "裸字符串消息"
    # 挂到 FakeDebug.find_log_position 返回的位置 p1:3
    assert lines[0]["data"]["process_id"] == "p1" and lines[0]["data"]["line"] == 3
    assert lines[0]["data"]["log_type"] == ReportType.Script.value
