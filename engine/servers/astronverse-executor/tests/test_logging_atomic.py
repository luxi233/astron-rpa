"""J2: 运行日志系统 pytest 版(原 tests/smoke/smoke_logging.py)。

覆盖:
1. AtomicManager._fmt_value/_fmt_params: 敏感参数掩码 + 超长截断 + 换行转义
2. atomic_run 三级日志(off/standard/debug)行为: START/参数摘要/结果/错误堆栈
3. Report.clean_expired_logs: 过期删除 + 保留时限内不删 + 0/负数不清理
"""

import os
import time

import pytest

from astronverse.actionlib import ReportCodeStatus
from astronverse.actionlib.atomic import AtomicManager, atomicMg
from astronverse.actionlib.report import report
from astronverse.executor.debug.report import Report


class _CaptureReport:
    """捕获 report 调用"""

    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        pass

    def error(self, message):
        self.errors.append(message)

    def clear(self):
        self.infos.clear()
        self.errors.clear()


@atomicMg.atomic("SmokeLog", outputList=[atomicMg.param("res", types="Str")])
def smoke_step(url: str = "", password: str = "", fail: bool = False):
    if fail:
        raise ValueError("boom")
    return "ok"


def _run(**kwargs):
    return smoke_step(__info__=[7, "p1"], **kwargs)


@pytest.fixture
def cap():
    """挂捕获 report + 还原日志级别, 避免污染其他套件"""
    c = _CaptureReport()
    report.set_code(c)
    old_level = atomicMg.cfg().get("LOG_LEVEL")
    yield c
    report.set_code(None)
    atomicMg.cfg()["LOG_LEVEL"] = old_level or "standard"


class TestFmtValue:
    def test_敏感参数掩码(self):
        assert AtomicManager._fmt_value("password", "abc123") == "***"
        assert AtomicManager._fmt_value("api_key", "sk-xxx") == "***"

    def test_普通参数不掩码(self):
        assert AtomicManager._fmt_value("url", "http://a.b") == "http://a.b"

    def test_超长值截断(self):
        masked = AtomicManager._fmt_value("data", "x" * 500)
        assert len(masked) < 250 and "共500字符" in masked

    def test_换行转义(self):
        assert "\\n" in AtomicManager._fmt_value("text", "a\nb")

    def test_不可打印对象容错(self):
        class _BadStr:
            def __str__(self):
                raise RuntimeError("no str")

        assert AtomicManager._fmt_value("obj", _BadStr()) == "<unprintable>"

    def test_参数摘要排序加掩码(self):
        fmt = AtomicManager._fmt_params({"url": "http://a", "password": "secret", "b": 2})
        assert fmt == "b=2, password=***, url=http://a"


class TestAtomicRunLevel:
    def test_standard有START无参数摘要无结果(self, cap):
        atomicMg.cfg()["LOG_LEVEL"] = "standard"
        _run(url="http://a", password="secret")
        assert any(i.status == ReportCodeStatus.START for i in cap.infos)
        assert not any("参数:" in str(i.msg_str) for i in cap.infos)
        assert not any(i.status == ReportCodeStatus.RES for i in cap.infos)

    def test_debug有参数摘要掩码与结果(self, cap):
        atomicMg.cfg()["LOG_LEVEL"] = "debug"
        _run(url="http://a", password="secret")
        param_logs = [str(i.msg_str) for i in cap.infos if "参数:" in str(i.msg_str)]
        assert len(param_logs) == 1
        assert "password=***" in param_logs[0] and "secret" not in param_logs[0]
        assert any(i.status == ReportCodeStatus.RES and "ok" in str(i.msg_str) for i in cap.infos)

    def test_off无任何日志(self, cap):
        atomicMg.cfg()["LOG_LEVEL"] = "off"
        _run(url="http://a")
        assert len(cap.infos) == 0 and len(cap.errors) == 0

    def test_异常日志带类型堆栈耗时(self, cap):
        atomicMg.cfg()["LOG_LEVEL"] = "standard"
        with pytest.raises(ValueError):
            _run(fail=True)
        assert len(cap.errors) == 1
        e = cap.errors[0]
        assert "ValueError" in str(e.msg_str) and "boom" in str(e.msg_str)
        assert "Traceback" in str(getattr(e, "error_traceback", ""))
        assert getattr(e, "cost_ms", None) is not None

    def test_直接调用无info不产生日志(self, cap):
        res = smoke_step(url="http://x")
        assert res == "ok"
        assert len(cap.infos) == 0


class TestCleanExpiredLogs:
    def _prepare(self, td):
        proj = os.path.join(td, "report", "proj1")
        os.makedirs(proj)
        old_f = os.path.join(proj, "old.txt")
        new_f = os.path.join(proj, "new.txt")
        log_f = os.path.join(proj, "other.log")
        for f in (old_f, new_f, log_f):
            with open(f, "w") as fh:
                fh.write("x")
        expired_mtime = time.time() - 40 * 86400  # 40 天前
        os.utime(old_f, (expired_mtime, expired_mtime))
        os.utime(log_f, (expired_mtime, expired_mtime))
        return old_f, new_f, log_f

    def test_过期txt删除且其余保留(self, tmp_path):
        td = str(tmp_path)
        old_f, new_f, log_f = self._prepare(td)
        Report.clean_expired_logs(td, 30)
        assert not os.path.exists(old_f)
        assert os.path.exists(new_f)
        assert os.path.exists(log_f)  # 非 txt 不动

    def test_零或负数保留天数不清理(self, tmp_path):
        td = str(tmp_path)
        _, new_f, _ = self._prepare(td)
        Report.clean_expired_logs(td, 0)
        assert os.path.exists(new_f)
        Report.clean_expired_logs(td, -1)
        assert os.path.exists(new_f)

    def test_空路径容错(self):
        Report.clean_expired_logs("", 30)  # 不抛错
