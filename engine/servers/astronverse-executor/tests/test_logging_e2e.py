"""J2: 运行日志全流程集成测试 pytest 版(原 tests/smoke/smoke_logging_e2e.py)。

原子执行 → atomic_run 埋点 → Report 落盘端到端:
1. standard: 成功原子无落盘(START是tip), 失败原子落盘error+堆栈+耗时
2. debug: 成功原子落盘参数摘要(敏感掩码)+结果
3. off: 完全不落盘
4. 非法级别回退 standard
5. 级别切换运行时即时生效
6. 落盘行可解析且字段完整(process_id/line/atomic/key)
"""

import json
import os

import pytest

from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.report import report
from astronverse.executor.debug.report import Report


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


def _run(**kwargs):
    return e2e_step(__info__=[7, "p1"], **kwargs)


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture
def env(tmp_path):
    """真实 Report 挂全局 report 单例 → 文件落盘; 收尾还原级别并关闭句柄"""
    td = str(tmp_path)
    created = []
    counter = {"n": 0}

    def make():
        # 每个用例独立 exec_id, 避免句柄指向被删 inode
        counter["n"] += 1
        exec_id = f"exec{counter['n']}"
        pinfo = {"p1": FakeProc("p1", "主流程", [[7, "line-7-id", "测试原子", "SmokeE2E.e2e_step"]])}
        conf = type(
            "C",
            (),
            {"log_path": td, "project_id": "proj1", "exec_id": exec_id, "log_retention_days": 30, "open_log_ws": False},
        )()
        r = Report(FakeSvc(conf, pinfo))
        report.set_code(r)
        created.append(r)
        return r, os.path.join(td, "report", "proj1", f"{exec_id}.txt")

    old_level = atomicMg.cfg().get("LOG_LEVEL")
    yield make
    report.set_code(None)
    atomicMg.cfg()["LOG_LEVEL"] = old_level or "standard"
    for r in created:
        r.close()


def test_standard成功无落盘失败落盘error(env):
    r, log_file = env()
    atomicMg.cfg()["LOG_LEVEL"] = "standard"
    _run(url="http://a", password="secret")
    assert read_lines(log_file) == []  # START 为 tip 不落盘

    with pytest.raises(ValueError):
        _run(fail=True)
    lines = read_lines(log_file)
    assert len(lines) == 1 and lines[0]["data"]["log_level"] == "error"
    err = lines[0]["data"]
    assert "ValueError" in str(err.get("msg_str")) and "连接失败" in str(err.get("msg_str"))
    assert "Traceback" in str(err.get("error_traceback", ""))
    assert err.get("cost_ms") is not None
    assert err.get("line") == 7 and err.get("process_id") == "p1"
    assert err.get("atomic") == "测试原子" and err.get("key") == "SmokeE2E.e2e_step"


def test_debug成功落盘参数摘要与结果(env):
    r, log_file = env()
    atomicMg.cfg()["LOG_LEVEL"] = "debug"
    _run(url="http://a", password="secret")
    r.flush()  # 缓冲写: 读取前显式刷盘
    lines = read_lines(log_file)
    params = [l["data"] for l in lines if "参数:" in str(l["data"].get("msg_str"))]
    results = [l["data"] for l in lines if l["data"].get("msg_str") == "done"]
    assert len(params) == 1
    p = str(params[0]["msg_str"])
    assert "password=***" in p and "secret" not in p
    assert "url=http://a" in p  # 非敏感参数明文
    assert len(results) == 1 and results[0].get("cost_ms") is not None


def test_off成功与失败均不落盘(env):
    _, log_file = env()
    atomicMg.cfg()["LOG_LEVEL"] = "off"
    _run(url="http://a")
    with pytest.raises(ValueError):
        _run(fail=True)
    assert read_lines(log_file) == []


def test_非法级别回退standard(env):
    _, log_file = env()
    atomicMg.cfg()["LOG_LEVEL"] = "verbose"
    with pytest.raises(ValueError):
        _run(fail=True)
    assert len(read_lines(log_file)) == 1  # error 仍落盘


def test_级别切换运行时即时生效(env):
    r, log_file = env()
    atomicMg.cfg()["LOG_LEVEL"] = "off"
    _run(url="http://a")
    assert read_lines(log_file) == []

    atomicMg.cfg()["LOG_LEVEL"] = "debug"
    _run(url="http://b")
    r.flush()
    after = read_lines(log_file)
    assert len(after) == 2  # 参数摘要+结果
    assert any("url=http://b" in str(l["data"].get("msg_str")) for l in after)


def test_off级别不影响执行结果(env):
    env()
    atomicMg.cfg()["LOG_LEVEL"] = "off"
    assert _run(url="http://x") == "done"
