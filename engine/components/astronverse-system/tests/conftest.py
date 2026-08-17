"""system 组件测试 conftest: 非 Windows 平台 stub win32* 模块

printer_core 等模块顶层 import win32com/win32print, macOS 上收集即失败;
stub 后用例若真实触达 Windows-only 功能会显式失败, 便于区分。
"""

import importlib.machinery
import sys
import types

if sys.platform != "win32":

    class _StubFinder:
        PREFIXES = ("win32", "pythoncom", "_winapi", "pywintypes")

        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0].startswith(self.PREFIXES):
                spec = importlib.machinery.ModuleSpec(name, self)
                spec.loader = self
                return spec
            return None

        def create_module(self, spec):
            mod = types.ModuleType(spec.name)

            def _getattr(attr):
                if attr.startswith("__"):
                    raise AttributeError(attr)
                return lambda *a, **kw: None

            mod.__getattr__ = _getattr
            return mod

        def exec_module(self, module):
            module.__path__ = []

    sys.meta_path.insert(0, _StubFinder())
