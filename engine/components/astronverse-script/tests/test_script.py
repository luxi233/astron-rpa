import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from astronverse.script.script import Script


class TestScriptModule(unittest.TestCase):
    """测试 Script 模块调用（当前 API: _module_call / _call，content 为模块名非源码）"""

    def test_module_call_v2_returns_main_result(self):
        """V2 modules should return main(args), not the input argument mapping."""
        process_module = SimpleNamespace(main=lambda args: {"result": args["value"].upper()})

        with patch("astronverse.script.script.importlib.import_module", return_value=process_module):
            result = Script._module_call(
                ".example",
                package="test_package",
                out_kwargs={"value": "input"},
                out_param_meta=[],
                inn_kwargs={},
            )

        assert result == {"result": "INPUT"}

    def test_module_call_v1_spreads_kwargs(self):
        """V1 modules (main(*args, **kwargs)) receive inn_kwargs as keyword args."""
        captured = {}

        def v1_main(**kwargs):
            captured.update(kwargs)
            return "v1-ok"

        process_module = SimpleNamespace(main=v1_main)

        with patch("astronverse.script.script.importlib.import_module", return_value=process_module):
            result = Script._module_call(
                ".example",
                package="test_package",
                out_kwargs={},
                out_param_meta=[],
                inn_kwargs={"a": 1, "b": 2},
            )

        assert result == "v1-ok"
        assert captured == {"a": 1, "b": 2}

    def test_module_call_import_failure_raises(self):
        """导入失败应包装为 BaseException 并带模块路径信息。"""
        with patch("astronverse.script.script.importlib.import_module", side_effect=RuntimeError("boom")):
            with pytest.raises(BaseException, match=".missing"):
                Script._module_call(".missing", package="pkg", out_kwargs={}, out_param_meta=[], inn_kwargs={})

    def test_module_call_missing_main_raises(self):
        """模块无 main 函数应报 MODULE_MAIN_FUNCTION_NOT_FOUND。"""
        with patch("astronverse.script.script.importlib.import_module", return_value=SimpleNamespace()):
            with pytest.raises(BaseException, match="main"):
                Script._module_call(
                    ".nomain",
                    package="pkg",
                    out_kwargs={},
                    out_param_meta=[],
                    inn_kwargs={},
                )


if __name__ == "__main__":
    unittest.main()
