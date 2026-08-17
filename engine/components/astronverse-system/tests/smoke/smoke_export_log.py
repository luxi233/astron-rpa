import json, os, sys, time, types
import importlib.machinery


class _StubFinder:
    """macOS 下 stub win32* 模块（printer_core 顶层 import win32com，本冒烟不触达打印机逻辑）"""

    PREFIXES = ("win32", "pythoncom", "_winapi", "pywintypes")

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0].startswith(self.PREFIXES):
            spec = importlib.machinery.ModuleSpec(name, self)
            spec.loader = self
            return spec
        return None

    def create_module(self, spec):
        mod = types.ModuleType(spec.name)
        mod.__getattr__ = lambda attr: (lambda *a, **kw: None) if not attr.startswith("__") else (_ for _ in ()).throw(AttributeError(attr))
        return mod

    def exec_module(self, module):
        module.__path__ = []  # 允许 import win32com.client 等子模块


sys.meta_path.insert(0, _StubFinder())

# stub executor config module path used by app_core lazy import
fake_config = types.ModuleType("astronverse.executor.config")
class _C:
    log_path = "/tmp/smoke_logs/"
    project_id = "proj1"
    exec_id = "exec1"
fake_config.Config = _C
sys.modules["astronverse.executor.config"] = fake_config

os.makedirs("/tmp/smoke_logs/report/proj1", exist_ok=True)
jsonl = "/tmp/smoke_logs/report/proj1/exec1.txt"
now = time.time()
with open(jsonl, "w", encoding="utf-8") as f:
    f.write(json.dumps({"event_time": now, "data": {"log_type": "INFO", "msg_str": "开始执行", "process_id": "main"}}) + "\n")
    f.write(json.dumps({"event_time": now, "data": {"log_type": "ERROR", "msg_str": "某步骤失败"}}) + "\n")
    f.write("not-a-json-line\n")

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-system/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-actionlib/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-baseline/src")
from astronverse.system.core import app_core

log_file = app_core.get_run_log_file()
print("log_file:", log_file)
assert log_file == jsonl, log_file

content = app_core.format_run_log(log_file)
print("--- formatted ---")
print(content)
assert "开始执行" in content and "某步骤失败" in content and "not-a-json-line" in content

from astronverse.system.system import System
out = System.export_log(folder_path="/tmp/smoke_out", file_name="log1")
print("exported:", out)
assert os.path.isfile(out) and open(out, encoding="utf-8").read() == content
print("export_log smoke OK")
