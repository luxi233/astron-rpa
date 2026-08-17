# -*- coding: utf-8 -*-
"""P0-6 file_info单位 + get_pid空名称 冒烟(system组件)"""
import sys
import os
import tempfile

# stub win32* 模块
import importlib.machinery
import types


class _Stub:
    def __init__(self, name):
        object.__setattr__(self, "_name", name)

    def __getattr__(self, attr):
        if attr.startswith("__"):
            raise AttributeError(attr)
        return _Stub(f"{self._name}.{attr}")

    def __call__(self, *args, **kwargs):
        if "mimetypes" in self._name:
            return None
        raise NotImplementedError(f"stubbed: {self._name}")


class _StubFinder:
    PREFIXES = ("win32", "pythoncom", "_winapi", "pywintypes", "uiautomation", "pyautogui", "mouseinfo", "tkinter")

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0].startswith(self.PREFIXES):
            spec = importlib.machinery.ModuleSpec(name, self)
            spec.loader = self
            return spec
        return None

    def create_module(self, spec):
        mod = types.ModuleType(spec.name)
        mod.__getattr__ = _Stub(spec.name).__getattr__
        return mod

    def exec_module(self, module):
        pass


sys.meta_path.insert(0, _StubFinder())
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-system/src")

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


from astronverse.system.file import File
from astronverse.system.process import Process
from astronverse.system import FileSizeUnitType, InfoType

tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
tmp.write(b"x" * 2048)
tmp.close()
info_b = File.file_info(file_path=tmp.name, info_type=InfoType.ALL, size_unit=FileSizeUnitType.B)
check("file_info B", info_b["size"] == 2048, info_b.get("size"))
info_kb = File.file_info(file_path=tmp.name, info_type=InfoType.SIZE, size_unit=FileSizeUnitType.KB)
check("file_info KB", info_kb == 2.0, info_kb)
info_mb = File.file_info(file_path=tmp.name, info_type=InfoType.ALL, size_unit=FileSizeUnitType.MB)
check("file_info MB", abs(info_mb["size"] - 2048 / 1048576) < 1e-4, info_mb.get("size"))
info_default = File.file_info(file_path=tmp.name, info_type=InfoType.SIZE)
check("file_info default B", info_default == 2048, info_default)
os.unlink(tmp.name)

all_procs = Process.get_pid(process_name="")
check("get_pid empty returns list", isinstance(all_procs, list) and len(all_procs) > 5, len(all_procs) if isinstance(all_procs, list) else all_procs)
check("get_pid empty item format", all(isinstance(p, (list, tuple)) and len(p) == 2 and isinstance(p[1], int) for p in all_procs[:20]), all_procs[:3])
one_pid = Process.get_pid(process_name="python", search_type=__import__("astronverse.system", fromlist=["SearchType"]).SearchType.FUZZY, pid_type=__import__("astronverse.system", fromlist=["PidType"]).PidType.ALL)
check("get_pid fuzzy still works", isinstance(one_pid, list), one_pid)

print(f"\n=== {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
