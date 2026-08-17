"""运行日志系统冒烟测试。

覆盖:
1. AtomicManager._fmt_value/_fmt_params: 敏感参数掩码 + 超长截断 + 换行转义
2. atomic_run 三级日志(off/standard/debug)行为: START/参数摘要/结果/错误堆栈
3. Report.clean_expired_logs: 过期删除 + 保留时限内不删 + 0=不清理

运行: cd engine/servers/astronverse-executor && .venv/bin/python tests/smoke/smoke_logging.py
"""

import os
import sys
import tempfile
import time

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


# ---------- 1. 参数摘要掩码/截断 ----------
from astronverse.actionlib.atomic import AtomicManager  # noqa: E402

check("掩码: password", AtomicManager._fmt_value("password", "abc123") == "***")
check("掩码: api_key", AtomicManager._fmt_value("api_key", "sk-xxx") == "***")
check("掩码: 普通参数不掩码", AtomicManager._fmt_value("url", "http://a.b") == "http://a.b")

long_val = "x" * 500
masked = AtomicManager._fmt_value("data", long_val)
check("截断: 超长值截断到200+提示", len(masked) < 250 and "共500字符" in masked, f"got len={len(masked)}")
check("换行转义", "\\n" in AtomicManager._fmt_value("text", "a\nb"))


class _BadStr:
    def __str__(self):
        raise RuntimeError("no str")


check("不可打印对象容错", AtomicManager._fmt_value("obj", _BadStr()) == "<unprintable>")

fmt_params = AtomicManager._fmt_params({"url": "http://a", "password": "secret", "b": 2})
check("参数摘要排序+掩码", fmt_params == "b=2, password=***, url=http://a", f"got {fmt_params}")

# ---------- 2. atomic_run 三级日志 ----------
from astronverse.actionlib import ReportCodeStatus  # noqa: E402
from astronverse.actionlib.atomic import atomicMg  # noqa: E402
from astronverse.actionlib.report import report  # noqa: E402


class CaptureReport:
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


cap = CaptureReport()
report.set_code(cap)


@atomicMg.atomic("SmokeLog", outputList=[atomicMg.param("res", types="Str")])
def smoke_step(url: str = "", password: str = "", fail: bool = False):
    if fail:
        raise ValueError("boom")
    return "ok"


def run_step(**kwargs):
    return smoke_step(__info__=[7, "p1"], **kwargs)


# standard: START 有, 参数摘要无, 结果无
atomicMg.cfg()["LOG_LEVEL"] = "standard"
cap.clear()
run_step(url="http://a", password="secret")
check("standard: 有 START 日志", any(i.status == ReportCodeStatus.START for i in cap.infos))
check("standard: 无参数摘要", not any("参数:" in str(i.msg_str) for i in cap.infos))
check("standard: 无结果日志", not any(i.status == ReportCodeStatus.RES for i in cap.infos))

# debug: START + 参数摘要(掩码) + 结果
atomicMg.cfg()["LOG_LEVEL"] = "debug"
cap.clear()
run_step(url="http://a", password="secret")
param_logs = [str(i.msg_str) for i in cap.infos if "参数:" in str(i.msg_str)]
check("debug: 有参数摘要", len(param_logs) == 1)
check("debug: 参数摘要掩码", param_logs and "password=***" in param_logs[0] and "secret" not in param_logs[0])
check("debug: 有结果日志", any(i.status == ReportCodeStatus.RES and "ok" in str(i.msg_str) for i in cap.infos))

# off: 完全无步骤日志
atomicMg.cfg()["LOG_LEVEL"] = "off"
cap.clear()
run_step(url="http://a")
check("off: 无任何日志", len(cap.infos) == 0 and len(cap.errors) == 0)

# 异常: 错误日志带异常类型+堆栈+耗时
atomicMg.cfg()["LOG_LEVEL"] = "standard"
cap.clear()
try:
    run_step(fail=True)
except ValueError:
    pass
check("异常: 捕获error日志", len(cap.errors) == 1)
if cap.errors:
    e = cap.errors[0]
    check("异常: 含异常类型和消息", "ValueError" in str(e.msg_str) and "boom" in str(e.msg_str))
    check("异常: 含堆栈", "Traceback" in str(getattr(e, "error_traceback", "")))
    check("异常: 含耗时ms", getattr(e, "cost_ms", None) is not None)

# 直接调用(无__info__): 不产生日志、正常执行
cap.clear()
res = smoke_step(url="http://x")
check("直接调用: 返回值正常", res == "ok")
check("直接调用: 无日志", len(cap.infos) == 0)

# ---------- 3. 过期日志清理 ----------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from astronverse.executor.debug.report import Report  # noqa: E402

with tempfile.TemporaryDirectory() as td:
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

    Report.clean_expired_logs(td, 30)
    check("清理: 过期txt已删除", not os.path.exists(old_f))
    check("清理: 未过期txt保留", os.path.exists(new_f))
    check("清理: 非txt不动", os.path.exists(log_f))

    Report.clean_expired_logs(td, 0)
    check("清理: retention=0不清理", os.path.exists(new_f))

    Report.clean_expired_logs(td, -1)
    check("清理: 负数不清理", os.path.exists(new_f))

    Report.clean_expired_logs("", 30)  # 空路径不抛错
    check("清理: 空路径容错", True)

report.set_code(None)
print(f"\n结果: {PASS} 通过, {FAIL} 失败")
sys.exit(1 if FAIL else 0)
