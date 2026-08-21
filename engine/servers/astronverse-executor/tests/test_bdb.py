"""J1 bdb 调试链路单测。

覆盖 .map 行映射加载与双向转换、断点设置/清除(含 E5 修复的"一个流程行
映射多个 Python 行"场景)、user_line 各分支与强制中断; 全部纯 Python, macOS 可跑。
"""

import os
import threading
from types import SimpleNamespace

from astronverse.executor.debug.bdb import CustomBdb


def _make_bdb(tmp_path, maps=None, py_files=("main.py",), notify=None):
    """构造最小工程目录与 CustomBdb 实例, 返回 (bdb, events, project_dir)

    注意: macOS 下 tmp_path 是 /private/var 符号链接, bdb 内部对文件路径做
    realpath 规范化, 故项目路径统一取 realpath 保证两侧匹配一致。
    """
    # 桩文件写足行数: bdb.set_break 会用 linecache 校验行是否存在, 行不存在时静默不设断点
    source = "x = 1\n" * 120
    for name in py_files:
        (tmp_path / name).write_text(source, encoding="utf-8")
    for name, content in (maps or {}).items():
        (tmp_path / name).write_text(content, encoding="utf-8")

    project = os.path.realpath(str(tmp_path))
    events = []
    notify = notify or (lambda *a, **k: events.append((a, k)))
    b = CustomBdb(project, project, notify=notify, err_handler=lambda e: str(e))
    return b, events, project


def _frame(filename, lineno, locals_=None, globals_=None):
    """伪造帧对象(user_line 仅读取这四个属性)"""
    return SimpleNamespace(
        f_code=SimpleNamespace(co_filename=filename),
        f_lineno=lineno,
        f_locals=locals_ or {},
        f_globals=globals_ or {},
    )


def _start(b):
    """置入运行态标志(bdb.Bdb 仅在 run 后才有 botframe,
    set_continue/set_next/set_quit 依赖它)"""
    b.botframe = None


class TestMapLoading:
    def test_正向与反向映射加载(self, tmp_path):
        b, _, project = _make_bdb(tmp_path, maps={"main.map": "5:1,6:1,7:2"})
        main = os.path.join(project, "main.py")
        assert b.file_line_maps[main] == {5: 1, 6: 1, 7: 2}
        # 反向映射按流程行分组且升序
        assert b.file_rev_maps[main] == {1: [5, 6], 2: [7]}

    def test_空map文件记为空映射(self, tmp_path):
        b, _, project = _make_bdb(tmp_path, maps={"main.map": ""})
        main = os.path.join(project, "main.py")
        assert b.file_line_maps[main] == {}
        assert main not in b.file_rev_maps

    def test_畸形map片段跳过(self, tmp_path):
        b, _, project = _make_bdb(tmp_path, maps={"main.map": "5:1,bad,7:2"})
        main = os.path.join(project, "main.py")
        assert b.file_line_maps[main] == {5: 1, 7: 2}

    def test_无map的py仍登记file_map(self, tmp_path):
        b, _, project = _make_bdb(tmp_path, maps={"main.map": "5:1"}, py_files=("main.py", "util.py"))
        main = os.path.join(project, "main.py")
        util = os.path.join(project, "util.py")
        assert b.file_map.get(main) is True
        assert b.file_map.get(util) is True
        assert util not in b.file_line_maps

    def test_含package名的py不入file_map(self, tmp_path):
        b, _, project = _make_bdb(tmp_path, py_files=("main.py", "package.py"))
        assert os.path.join(project, "package.py") not in b.file_map


class TestPathConvert:
    def test_相对与绝对路径互转(self, tmp_path):
        b, _, project = _make_bdb(tmp_path)
        assert b._to_abs_path("main.py") == os.path.join(project, "main.py")
        assert b._to_abs_path("/x/y.py") == "/x/y.py"
        assert b._to_project_path(os.path.join(project, "main.py")) == "main.py"


class TestLineConvert:
    def test_正向转换(self, tmp_path):
        b, _, project = _make_bdb(tmp_path, maps={"main.map": "5:1,6:1,7:2"})
        main = os.path.join(project, "main.py")
        assert b._to_flow_line(main, 5) == 1
        # 已映射文件但行号不在映射表 → None(user_line 据此跳过非可视化行)
        assert b._to_flow_line(main, 99) is None
        # 未映射文件按原行号透传
        assert b._to_flow_line(os.path.join(project, "util.py"), 3) == 3

    def test_反向转换一对多(self, tmp_path):
        b, _, project = _make_bdb(tmp_path, maps={"main.map": "5:1,6:1,7:2"})
        main = os.path.join(project, "main.py")
        assert b._to_py_lines(main, 1) == [5, 6]
        # 未映射的流程行/文件按原行号回退
        assert b._to_py_lines(main, 42) == [42]
        assert b._to_py_lines(os.path.join(project, "util.py"), 42) == [42]


class TestBreakpoint:
    def test_断点覆盖全部映射行(self, tmp_path):
        # E5 修复语义: 一个流程行映射多个 Python 行时, 断点需全部设置/清除
        b, _, project = _make_bdb(tmp_path, maps={"main.map": "5:1,6:1,7:2"})
        main = os.path.join(project, "main.py")

        b.set_breakpoint("main.py", 1)
        assert b.get_breaks(main, 5)
        assert b.get_breaks(main, 6)
        assert not b.get_breaks(main, 7)

        b.clear_breakpoint("main.py", 1)
        assert not b.get_breaks(main, 5)
        assert not b.get_breaks(main, 6)

    def test_无映射流程行按原行号设置(self, tmp_path):
        b, _, project = _make_bdb(tmp_path)
        main = os.path.join(project, "main.py")
        b.set_breakpoint("main.py", 99)
        assert b.get_breaks(main, 99)

    def test_清除无断点行不报错(self, tmp_path):
        b, _, _ = _make_bdb(tmp_path)
        b.clear_breakpoint("main.py", 99)  # 无断点时静默通过


class TestUserLine:
    def test_强制中断直接返回(self, tmp_path):
        b, events, project = _make_bdb(tmp_path, maps={"main.map": "5:1"})
        b._force_stop = True
        b.user_line(_frame(os.path.join(project, "main.py"), 5))
        assert events == []
        assert b.paused is False

    def test_工程外文件跳过(self, tmp_path):
        b, events, _ = _make_bdb(tmp_path)
        b.user_line(_frame("/other/x.py", 5))
        assert events == []

    def test_首停清初始trace不通知(self, tmp_path):
        b, events, project = _make_bdb(tmp_path)
        _start(b)
        assert b._first_stop is True
        b.user_line(_frame(os.path.join(project, "main.py"), 5))
        assert events == []
        assert b._first_stop is False
        assert b.paused is False

    def test_映射文件中未映射行跳过(self, tmp_path):
        b, events, project = _make_bdb(tmp_path, maps={"main.map": "5:1"})
        _start(b)
        main = os.path.join(project, "main.py")
        b.user_line(_frame(main, 5))  # 消费首停
        b.user_line(_frame(main, 99))  # 不在映射表 → 不暂停不通知
        assert events == []
        assert b.paused is False

    def test_步骤暂停与变量聚合(self, tmp_path):
        b, events, project = _make_bdb(tmp_path, maps={"main.map": "5:1"})
        _start(b)

        main = os.path.join(project, "main.py")
        b.user_line(_frame(main, 5))  # 消费首停
        # user_line 在 notify 之后才 clear+wait(生产上由前端命令另起线程放行),
        # 测试用定时器线程模拟稍后放行, 避免阻塞
        threading.Timer(0.05, b._go_event.set).start()
        b.user_line(_frame(main, 5, locals_={"x": 1, "__info__": [1]}, globals_={"gv": {"y": "z"}}))

        assert len(events) == 1
        args, kwargs = events[0]
        assert args[0] == "step"  # 无断点时为单步语义
        assert kwargs["file"] == "main.py"
        assert kwargs["line"] == 1  # 已转换为流程行
        assert kwargs["py_line"] == 5
        # gv 与 locals 合并, 双下划线变量(__info__)不外泄
        assert "x" in kwargs["merged_vars"] and "y" in kwargs["merged_vars"]
        assert "__info__" not in kwargs["merged_vars"]
        assert b.paused is True

    def test_断点暂停reason为breakpoint(self, tmp_path):
        b, events, project = _make_bdb(tmp_path, maps={"main.map": "5:1,6:1"})
        _start(b)

        main = os.path.join(project, "main.py")
        b.user_line(_frame(main, 5))  # 消费首停

        b.set_breakpoint("main.py", 1)
        # 同一流程行展开的第 2 个 Python 行也能命中断点(E5)
        threading.Timer(0.05, b._go_event.set).start()
        b.user_line(_frame(main, 6))
        assert events[-1][0][0] == "breakpoint"


class TestForceStop:
    def test_强制中断置位(self, tmp_path):
        b, _, _ = _make_bdb(tmp_path)
        _start(b)
        b.cmd_force_stop()
        assert b._force_stop is True
        assert b.paused is True
        assert b.quitting is True
