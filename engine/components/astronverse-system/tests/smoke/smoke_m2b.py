# -*- coding: utf-8 -*-
"""M2-B批次冒烟: P5-2 打印机×6 macOS守卫 + fake win32print 逻辑验证"""

import sys
import types

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/components/astronverse-system/src"))

from astronverse.baseline.error.error import BaseException  # noqa: E402

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


def expect_err(name, fn, kw, keyword):
    global passed, failed
    try:
        fn(**kw)
        failed += 1
        print(f"FAIL {name} 未抛异常")
    except BaseException as e:
        msg = str(e)
        if keyword in msg:
            passed += 1
            print(f"PASS {name}: {msg[:70]}")
        else:
            failed += 1
            print(f"FAIL {name} 关键词[{keyword}]不在: {msg[:100]}")
    except Exception as e:  # noqa: BLE001
        failed += 1
        print(f"FAIL {name} 异常类型不符: {type(e).__name__} {e}")


# ---------- 1. macOS 守卫: 非Windows直接报不支持 ----------
from astronverse.system.printer import Printer as P  # noqa: E402

assert sys.platform != "win32", "本机应为 macOS"
expect_err("macOS get_list 不支持", P.get_printer_list, {}, "仅在 Windows")
expect_err("macOS clear_jobs 不支持", P.clear_printer_jobs, {"printer_name": "X"}, "仅在 Windows")

# ---------- 2. fake win32print 逻辑验证 ----------
state = {"default": "FakePrinter", "purge_cmds": [], "set_default_calls": []}


def make_job(jid, doc, owner, status, printed, total):
    return {
        "JobId": jid,
        "pDocument": doc,
        "pUserName": owner,
        "Status": status,
        "PagesPrinted": printed,
        "TotalPages": total,
        "Submitted": "2026/08/16 20:00:00",
    }


fake_win32print = types.ModuleType("win32print")
fake_win32print.PRINTER_ENUM_LOCAL = 2
fake_win32print.PRINTER_ENUM_CONNECTIONS = 4
fake_win32print.PRINTER_ALL_ACCESS = 0xF000C
fake_win32print.GetDefaultPrinter = lambda: state["default"]
fake_win32print.SetDefaultPrinter = lambda name: state["set_default_calls"].append(name) or state.update(default=name)
fake_win32print.EnumPrinters = lambda flags: [(None, "Fake", "FakePrinter"), (None, "Fake2", "PDF")]
fake_win32print.OpenPrinter = lambda name, defaults=None: f"handle::{name}"
fake_win32print.ClosePrinter = lambda h: None
fake_win32print.GetPrinter = lambda h, level: {"Status": state.get("printer_status", 0x10)}
fake_win32print.EnumJobs = lambda h, first, last, level: state.get("jobs", [])
fake_win32print.SetPrinter = lambda h, level, d, cmd: state["purge_cmds"].append(cmd)

fake_win32com = types.ModuleType("win32com")
fake_wc = types.ModuleType("win32com.client")
fake_win32com.client = fake_wc
fake_win32ui = types.ModuleType("win32ui")
fake_imagewin = types.ModuleType("PIL.ImageWin")

sys.modules["win32print"] = fake_win32print
sys.modules["win32com"] = fake_win32com
sys.modules["win32com.client"] = fake_wc
sys.modules["win32ui"] = fake_win32ui
sys.modules["PIL.ImageWin"] = fake_imagewin

# 清掉可能已缓存的 printer_core
for mod in list(sys.modules):
    if "printer_core" in mod:
        del sys.modules[mod]

sys.platform = "win32"  # 模拟 Windows

# 重新触发懒加载
from astronverse.system.core.printer_core import PrinterCore  # noqa: E402, F401

r = P.get_printer_list()
check("get_list 返回2台", r == ["FakePrinter", "PDF"], r)

r = P.get_default_printer()
check("get_default", r == "FakePrinter", r)

r = P.set_default_printer(printer_name="PDF")
check("set_default 成功", r is True and state["default"] == "PDF" and state["set_default_calls"] == ["PDF"], r)
expect_err("set_default 名称不存在", P.set_default_printer, {"printer_name": "NoExist"}, "未发现")
expect_err("set_default 空名称", P.set_default_printer, {"printer_name": "  "}, "打印机操作失败")

# 状态: 默认打印机(PDF) 缺纸 0x10
code, text = P.get_printer_status(printer_name="")
check("status 缺纸码", code == 0x10, code)
check("status 缺纸文本", text == "缺纸", text)

state["printer_status"] = 0x00000400 | 0x00000800  # 正在打印 + 出纸槽已满
code, text = P.get_printer_status(printer_name="FakePrinter")
check("status 组合码", code == 0xC00, hex(code))
check("status 组合文本", text == "正在打印、出纸槽已满", text)

state["printer_status"] = 0
code, text = P.get_printer_status(printer_name="FakePrinter")
check("status 空闲", code == 0 and text == "空闲", (code, text))

# 作业队列
state["jobs"] = [make_job(5, "doc1.docx", "user1", 0x10 | 0x80, 3, 10), make_job(6, "doc2.pdf", "user2", 0x8, 0, 5)]
jobs = P.get_printer_jobs(printer_name="FakePrinter")
check("jobs 2项", len(jobs) == 2, jobs)
check(
    "jobs[0] 字段",
    jobs[0]["job_id"] == 5 and jobs[0]["document"] == "doc1.docx" and jobs[0]["owner"] == "user1",
    jobs[0],
)
check("jobs[0] 状态文本", jobs[0]["status_text"] == "正在打印、已打印", jobs[0]["status_text"])
check("jobs[0] 页数", jobs[0]["pages_printed"] == 3 and jobs[0]["total_pages"] == 10, jobs[0])
check("jobs[0] 提交时间", jobs[0]["submitted"] == "2026/08/16 20:00:00", jobs[0])
check("jobs[1] 后台处理", jobs[1]["status_text"] == "正在后台处理", jobs[1])

state["jobs"] = []
check("jobs 空队列", P.get_printer_jobs(printer_name="FakePrinter") == [])

r = P.clear_printer_jobs(printer_name="FakePrinter")
check("clear 成功且PURGE=3", r is True and state["purge_cmds"] == [3], state["purge_cmds"])

print(f"\n=== M2-B 冒烟: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
