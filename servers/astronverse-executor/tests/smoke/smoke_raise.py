"""Code.Raise + Catch保存异常信息 端到端冒烟: 真实 Lexer/Parser/Params 生成代码并执行"""
import sys
import types

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/servers/astronverse-executor/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-actionlib/src")

from astronverse.executor.flow.params import Param
from astronverse.executor.flow.syntax.lexer import Lexer
from astronverse.executor.flow.syntax.parser import Parser


class MockSvc:
    def __init__(self):
        self.ast_curr_info = {"__project_id__": "p1", "__process_id__": "main"}
        self.ast_globals_dict = {
            "p1": types.SimpleNamespace(project_info=types.SimpleNamespace(global_var={}))
        }
        self.conf = types.SimpleNamespace(debug_mode=True)

    def add_atomic_info(self, *a, **k):
        pass

    def add_import_python(self, *a, **k):
        pass


svc = MockSvc()
svc.param = Param(svc)

flow = [
    {"key": "Code.Try", "id": "t1", "__line__": 1},
    {
        "key": "Code.Raise",
        "id": "r1",
        "__line__": 2,
        "inputList": [
            {"key": "reason", "name": "reason", "value": [{"type": "str", "value": "库存不足，无法下单"}]}
        ],
    },
    {
        "key": "Code.Catch",
        "id": "c1",
        "__line__": 3,
        "outputList": [{"key": "error_msg", "value": [{"type": "other", "value": "err_text"}]}],
    },
    {"key": "Code.Finally", "id": "f1", "__line__": 4},
    {"key": "Code.TryEnd", "id": "te1", "__line__": 5},
]

parser = Parser(Lexer(flow))
program = parser.parse_program()
assert not parser.errors, parser.errors
print("parse OK, statements:", [type(s).__name__ for s in program.statements])

lines = []
for stmt in program.statements:
    lines.extend(stmt.display(svc, 0))
code = "\n".join(("    " * l.tab_num) + l.code for l in lines)
print("--- generated ---")
print(code)

# 断言生成代码结构
assert "raise BaseException(IGNORE_ERROR_FORMAT.format(str" in code, code
assert '库存不足，无法下单' in code, code
assert "except Exception as e:" in code, code
assert "err_text = str(e)" in code, code

# --- 执行验证 ---
exec_ns = {}
wrapper = "from astronverse.actionlib.types import *\nerr_text = None\nfinally_done = False\ntry:\n    pass\n" + "\n".join(
    "    " + l for l in code.split("\n")
).replace("    try:", "try:").replace("    except", "except").replace("    finally:", "finally:") + "\nfinally_done = True\n"
# 上面替换不可靠, 改为直接构造
wrapper = "from astronverse.actionlib.types import *\n" + code + "\nfinally_done = True\n"
exec(wrapper, exec_ns)

print("--- runtime ---")
print("err_text =", repr(exec_ns.get("err_text")))
assert exec_ns["err_text"] == "库存不足，无法下单", exec_ns["err_text"]

# --- 未配置输出的 Catch: 生成 pass, 不赋值 ---
flow2 = [
    {"key": "Code.Try", "id": "t1", "__line__": 1},
    {"key": "Code.Raise", "id": "r1", "__line__": 2, "inputList": [
        {"key": "reason", "name": "reason", "value": [{"type": "python", "value": "1/0 的原因"}]}
    ]},
    {"key": "Code.Catch", "id": "c1", "__line__": 3},
    {"key": "Code.TryEnd", "id": "te1", "__line__": 4},
]
p2 = Parser(Lexer(flow2))
prog2 = p2.parse_program()
assert not p2.errors, p2.errors
lines2 = []
for stmt in prog2.statements:
    lines2.extend(stmt.display(svc, 0))
code2 = "\n".join(("    " * l.tab_num) + l.code for l in lines2)
print("--- no-output catch generated ---")
print(code2)
assert "err_text" not in code2
# python表达式参数: show_value 应产出表达式
assert "1/0 的原因" in code2, code2

# 空 Catch 块 + 有输出: 只有赋值行, 不生成 pass
flow3 = [
    {"key": "Code.Try", "id": "t1", "__line__": 1},
    {"key": "Code.Catch", "id": "c1", "__line__": 2, "outputList": [
        {"key": "error_msg", "value": [{"type": "other", "value": "em"}]}
    ]},
    {"key": "Code.TryEnd", "id": "te1", "__line__": 3},
]
p3 = Parser(Lexer(flow3))
prog3 = p3.parse_program()
lines3 = []
for stmt in prog3.statements:
    lines3.extend(stmt.display(svc, 0))
code3 = "\n".join(("    " * l.tab_num) + l.code for l in lines3)
print("--- empty catch with output ---")
print(code3)
assert "em = str(e)" in code3 and "pass" not in code3.split("except")[1].split("finally")[0]

print("ALL RAISE/CATCH SMOKE OK")
