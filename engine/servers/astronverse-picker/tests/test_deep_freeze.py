"""深度捕获树固定(Ctrl+点击 toggle)与自身窗口黑名单回归测试。

覆盖:
1. _push_live_tree 冻结短路: deep_tree_frozen=True 期间不随鼠标推树(保留快照)
2. deep START 会话重置 frozen 状态(上次会话的固定不残留到新会话)
3. _draw_element 黑名单跳过: 鼠标悬停拾取器自身窗口(主窗口/深度捕获面板)静默保活
4. EventCore.poll_fallback Ctrl+左键沿边检测 + reset_focus_flag(冻结 toggle 消费)
"""

import queue
import sys
import types
from types import SimpleNamespace

import pytest

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_capture_mode as _cm  # noqa: F401
from astronverse.picker import PickerSign, PickerType
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire
from test_live_tree import _chain, _core, _LiveEle
from test_ws_server import _FakeSvc, _FakeWS, _run, fake_ui  # noqa: F401

# ---------------- _push_live_tree 冻结短路 ----------------


def test_push_冻结期间不推树():
    _, _, btn = _chain()
    q = queue.Queue()
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q, deep_tree_frozen=True)
    core = _core()
    core._push_live_tree(svc, _LiveEle(btn))
    assert q.qsize() == 0  # 冻结: 树快照保持, 不随鼠标刷新


def test_push_解冻后恢复推树():
    _, _, btn = _chain()
    q = queue.Queue()
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q, deep_tree_frozen=True)
    core = _core()
    core._push_live_tree(svc, _LiveEle(btn))
    svc.deep_tree_frozen = False  # Ctrl+点击再次 toggle 解冻
    core._push_live_tree(svc, _LiveEle(btn))
    assert q.qsize() == 1


def test_push_无frozen属性兼容旧svc():
    """deep_tree_frozen 尚未注册的场景(异常路径)按未冻结处理, 不影响主流程"""
    _, _, btn = _chain()
    q = queue.Queue()
    svc = SimpleNamespace(deep_tree_ws=object(), deep_tree_queue=q)
    core = _core()
    core._push_live_tree(svc, _LiveEle(btn))
    assert q.qsize() == 1


# ---------------- ws 会话注册重置 frozen ----------------


def _start_req(**kw):
    return PickerRequire(pick_sign=PickerSign.START, pick_type=PickerType.ELEMENT, **kw)


def test_deep_START会话重置frozen状态(fake_ui):
    captured = {}

    def probe(sign, data):
        captured["frozen"] = getattr(svc, "deep_tree_frozen", None)
        return {"ok": 1}

    svc = _FakeSvc(sign_result=probe)
    svc.deep_tree_frozen = True  # 上次会话遗留的固定状态
    handler = PickerRequestHandler(svc)
    result = _run(handler._handle_pick_start(_FakeWS(), _start_req(pick_mode="DeepUIA")))
    assert result["success"] is True
    # 会话开始时已重置(推送泵挂起期间读到的即为 False)
    assert captured["frozen"] is False


# ---------------- _draw_element 黑名单跳过 ----------------


def _draw_env(monkeypatch, process_name):
    """绘制环境桩: 鼠标指向 pid=1234 的窗口, 进程名可编程"""
    from astronverse.picker.core import picker_core_win as pcw
    from astronverse.picker.utils import process as proc_mod

    monkeypatch.setattr(pcw.UIAOperate, "get_cursor_pos", classmethod(lambda cls: (10, 10)))
    monkeypatch.setattr(pcw.UIAOperate, "get_windows_by_point", classmethod(lambda cls, point: object()))
    monkeypatch.setattr(pcw.UIAOperate, "get_process_id", classmethod(lambda cls, control: 1234))
    monkeypatch.setattr(pcw, "_is_self_elevated", lambda: True)
    monkeypatch.setattr(proc_mod, "find_real_application_process", lambda pid: {"name": process_name})
    pcw._self_pid_name_cache.clear()
    return pcw


def test_draw_黑名单进程静默保活(monkeypatch):
    """鼠标悬停拾取器自身窗口(深度捕获面板/主窗口): 不画框不推树, 会话保活。
    进程名传入已剥 .exe 后缀的形式(与真实 get_process_info 输出一致, 黑名单按基名匹配)。"""
    pcw = _draw_env(monkeypatch, "astron-rpa")
    core = pcw.PickerCore()

    def _must_not_reach(**kw):
        raise AssertionError("黑名单分支应在此之前返回, 不应进入策略上下文生成")

    svc = SimpleNamespace(strategy=SimpleNamespace(gen_svc=_must_not_reach, run=lambda s: None))
    q = queue.Queue()
    svc.deep_tree_ws = object()
    svc.deep_tree_queue = q
    res = core._draw_element(svc, SimpleNamespace(draw_wnd=lambda *a, **k: None), {"pick_mode": "DeepUIA"})
    # 空 error_message = 会话保活(不终止拾取), 画框/树保持上次状态
    assert res.success is False
    assert res.error_message == ""
    assert q.qsize() == 0


def test_draw_非黑名单进程正常走策略(monkeypatch):
    pcw = _draw_env(monkeypatch, "notepad.exe")
    core = pcw.PickerCore()

    class _DrawEle:
        def rect(self):
            return SimpleNamespace(left=0, top=0, right=10, bottom=10)

        def tag(self):
            return "ButtonControl"

    class _FakeStrategy:
        def gen_svc(self, **kwargs):
            return SimpleNamespace(app=SimpleNamespace(value="x"))

        def run(self, strategy_svc):
            return _DrawEle()

    svc = SimpleNamespace(strategy=_FakeStrategy())
    res = core._draw_element(svc, SimpleNamespace(draw_wnd=lambda *a, **k: None), {"pick_mode": "DeepUIA"})
    assert res.success is True


def test_黑名单pid缓存只查一次(monkeypatch):
    """同 pid 悬停多轮绘制只做一次 psutil 进程查询(每轮 ~30ms, 不容许重复开销)"""
    pcw = _draw_env(monkeypatch, "astron-rpa")
    calls = []
    from astronverse.picker.utils import process as proc_mod

    monkeypatch.setattr(
        proc_mod,
        "find_real_application_process",
        lambda pid: (calls.append(pid), {"name": "astron-rpa"})[1],
    )
    pcw._self_pid_name_cache.clear()
    assert pcw._is_blacklisted_process(1234) is True
    assert pcw._is_blacklisted_process(1234) is True
    assert len(calls) == 1


# ---------------- EventCore 沿边检测与 focus 消费 ----------------


@pytest.fixture
def hook_stubs(monkeypatch):
    """event_core_win 的 Windows 依赖桩(pythoncom/pyWinhook/win32api)。

    必须 monkeypatch.setitem 安装(测试结束自动还原): 直接写 sys.modules 会永久污染,
    假 pythoncom 缺 CoInitialize 会让 BATCH_VALIDATE 等用例的 import 走到异常分支。
    """

    def _stub(name, **attrs):
        if name not in sys.modules:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        for k, v in attrs.items():
            # raising=False: venv 里可能已存在空壳模块(如跨平台安装的 pythoncom), 属性缺失也要能补上
            monkeypatch.setattr(sys.modules[name], k, v, raising=False)

    _stub("pythoncom", PumpMessages=lambda: None, CoInitialize=lambda: None, CoUninitialize=lambda: None)
    _stub(
        "pyWinhook",
        HookManager=type("HookManager", (), {"__init__": lambda self: None}),
        KeyboardEvent=object,  # event_core_win 顶层 from pyWinhook import KeyboardEvent
    )
    _stub("win32api", GetAsyncKeyState=lambda vk: 0)
    return sys.modules["win32api"]


class _KeySequence:
    """GetAsyncKeyState 可编程序列桩: vk → [返回值, ...], 耗尽后恒 0"""

    def __init__(self, script):
        self.script = script  # {vk: [返回值序列]}

    def __call__(self, vk):
        seq = self.script.get(vk)
        if not seq:
            return 0
        return seq.pop(0) if len(seq) > 1 else seq[0]


def _event_core():
    from astronverse.picker.core import event_core_win

    return event_core_win.EventCore()


def test_poll_fallback_Ctrl左键沿边触发一次(monkeypatch, hook_stubs):
    ec = _event_core()
    # Ctrl 三轮均按住(0x8000), 左键恒按住——沿边检测应只在第一轮置位
    script = {0xA2: [0x8000, 0x8000, 0x8000], 0x01: [0x8000]}
    monkeypatch.setattr(hook_stubs, "GetAsyncKeyState", _KeySequence(script))
    ec.poll_fallback()  # 未按 → 按下: 置位
    assert ec.is_focus() is True
    ec.reset_focus_flag()  # 冻结 toggle 消费
    ec.poll_fallback()  # 仍按住: 不再置位(旧行为为电平置位会反复触发)
    assert ec.is_focus() is False
    ec.poll_fallback()  # 仍按住: 同上
    assert ec.is_focus() is False


def test_poll_fallback_松开后再次按下可再次触发(monkeypatch, hook_stubs):
    ec = _event_core()
    # Ctrl 按下→松开→再按下, 左键恒按住(注意 any/and 短路: Ctrl 未按时不会读左键状态)
    script = {0xA2: [0x8000, 0, 0x8000], 0x01: [0x8000]}
    monkeypatch.setattr(hook_stubs, "GetAsyncKeyState", _KeySequence(script))
    ec.poll_fallback()
    assert ec.is_focus() is True
    ec.reset_focus_flag()
    ec.poll_fallback()  # 松开轮
    assert ec.is_focus() is False
    ec.poll_fallback()  # 再次按下: 新跳变, 再次置位(可二次 toggle 解冻)
    assert ec.is_focus() is True


def test_reset_focus_flag_复位(hook_stubs):
    ec = _event_core()
    ec.reset_focus_flag()
    assert ec.is_focus() is False
