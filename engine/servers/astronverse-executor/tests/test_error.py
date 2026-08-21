"""错误翻译(E9)与版本缓存逻辑单测。

python_base_error 把 Python 原生异常翻译为用户可读中文, 正则漂移会静默失效, 需测试背书;
flow_start 的版本相同跳过重新生成逻辑同样无覆盖。
"""

from types import SimpleNamespace

import pytest
from astronverse.baseline.error.error import BaseException as BizException
from astronverse.baseline.error.error import BizCode, ErrorCode
from astronverse.executor import start as start_mod
from astronverse.executor.error import SERVER_ERROR_FORMAT, python_base_error
from astronverse.executor.start import flow_start


class TestPythonBaseError:
    def test_NameError(self):
        assert python_base_error(NameError("name 'foo' is not defined")) == "未定义的名称 'foo'"

    def test_TypeError_运算符(self):
        res = python_base_error(TypeError("unsupported operand type(s) for +: 'int' and 'str'"))
        assert "不支持的操作数类型" in res and "'int'" in res and "'str'" in res

    def test_TypeError_不可调用(self):
        assert python_base_error(TypeError("'int' object is not callable")) == "'int' 对象不可调用"

    def test_TypeError_缺位置参数(self):
        res = python_base_error(TypeError("f() missing 1 required positional argument: 'x'"))
        assert res == "函数 'f' 缺少 1 个位置参数"

    def test_IndexError(self):
        assert python_base_error(IndexError("list index out of range")) == "列表索引超出范围"

    def test_KeyError(self):
        assert python_base_error(KeyError("foo")) == "字典中不存在键 'foo'"

    def test_ValueError(self):
        res = python_base_error(ValueError("invalid literal for int() with base 10: 'abc'"))
        assert res == "无效的字面量 'abc' 不能转换为整数"

    def test_AttributeError(self):
        res = python_base_error(AttributeError("'NoneType' object has no attribute 'x'"))
        assert res == "'NoneType' 对象没有属性 'x'"

    def test_ZeroDivisionError(self):
        assert python_base_error(ZeroDivisionError("division by zero")) == "除零错误,除数不能为零"

    def test_ImportError_无模块(self):
        assert python_base_error(ImportError("No module named 'foo'")) == "没有名为 'foo' 的模块"

    def test_SyntaxError(self):
        assert python_base_error(SyntaxError("bad syntax")) == "语法错误, 检查后重试"

    def test_RecursionError(self):
        assert python_base_error(RecursionError()) == "递归深度超限, 检查流程否循环引用"

    def test_业务异常取code消息(self):
        code = ErrorCode(BizCode.LocalErr, "自定义业务错误")
        assert python_base_error(BizException(code, "detail")) == "自定义业务错误"

    def test_未知异常原样返回(self):
        assert python_base_error(RuntimeError("boom")) == "boom"


class _FlowRecorder:
    """记录 gen_component/gen_code 是否被调用"""

    calls = []

    def __init__(self, svc):
        self.svc = svc

    def gen_component(self, **kwargs):
        _FlowRecorder.calls.append("component")

    def gen_code(self, **kwargs):
        _FlowRecorder.calls.append("code")


def _svc_with_package_version(version: str):
    conf = SimpleNamespace(gen_component_path="/tmp/c", gen_core_path="/tmp/g")
    return SimpleNamespace(conf=conf, load_package_info=lambda: {"project_info": {"version": version}})


def _args(version="5"):
    return SimpleNamespace(
        version=version, project_id="p", mode="", process_id="proc", line="1", end_line="2"
    )


class TestFlowStartVersionCache:
    def setup_method(self):
        _FlowRecorder.calls = []

    def test_版本相同跳过重新生成(self, monkeypatch):
        monkeypatch.setattr(start_mod, "Flow", _FlowRecorder)
        flow_start(_svc_with_package_version("5"), _args(version="5"))
        assert _FlowRecorder.calls == []

    def test_版本不同重新生成(self, monkeypatch):
        monkeypatch.setattr(start_mod, "Flow", _FlowRecorder)
        flow_start(_svc_with_package_version("4"), _args(version="5"))
        assert _FlowRecorder.calls == ["component", "code"]

    def test_本地版本无效时重新生成(self, monkeypatch):
        monkeypatch.setattr(start_mod, "Flow", _FlowRecorder)
        flow_start(_svc_with_package_version(""), _args(version="5"))
        assert _FlowRecorder.calls == ["component", "code"]

    def test_新参数版本无效时重新生成(self, monkeypatch):
        monkeypatch.setattr(start_mod, "Flow", _FlowRecorder)
        flow_start(_svc_with_package_version("5"), _args(version="abc"))
        assert _FlowRecorder.calls == ["component", "code"]

    def test_双零版本仍重新生成(self, monkeypatch):
        # 0 < old_version 为 False, 不走缓存(防止空版本号误命中)
        monkeypatch.setattr(start_mod, "Flow", _FlowRecorder)
        flow_start(_svc_with_package_version(""), _args(version=""))
        assert _FlowRecorder.calls == ["component", "code"]


class TestErrorCodeFormat:
    def test_服务器错误格式化(self):
        assert "服务器错误" in SERVER_ERROR_FORMAT.format("timeout").message
