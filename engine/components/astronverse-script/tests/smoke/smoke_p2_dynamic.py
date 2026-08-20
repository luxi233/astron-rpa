r"""P2 动态调用×3冒烟测试: run_process_dynamic / run_module_dynamic / run_command_dynamic
构造 /tmp/p2_dyn 工程结构(包+子流程+模块v1/v2+组件c-id), 从 main() 帧提供 __package__ 上下文。
运行: cd astronverse-script && uv run python /tmp/smoke_p2_dynamic.py
"""

import os
import sys

ROOT = "/tmp/p2_dyn"
PKG = os.path.join(ROOT, "dynpkg")
COMP_DIR = os.path.join(ROOT, "c1990298105483890688")
for d in (PKG, COMP_DIR):
    os.makedirs(d, exist_ok=True)


def w(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


w(os.path.join(PKG, "__init__.py"), "")
w(os.path.join(COMP_DIR, "__init__.py"), "")
# 子流程(v2: main(args) 修改args模拟输出参数回填)
w(
    os.path.join(PKG, "sub_proc.py"),
    "def main(args):\n    args['out_total'] = args['a'] + args['b']\n    return args['a'] + args['b']\n",
)
# 模块v2: main(args)
w(os.path.join(PKG, "my_util.py"), "def main(args):\n    return {'doubled': args['x'] * 2}\n")
# 模块v1: main(**kwargs)
w(os.path.join(PKG, "my_util_v1.py"), "def main(**kwargs):\n    return kwargs.get('x', 0) + 1\n")
# 模块无main
w(os.path.join(PKG, "no_main.py"), "VALUE = 1\n")
# 组件: c-id/main.py
w(
    os.path.join(COMP_DIR, "main.py"),
    "def main(args):\n    args['res'] = str(args.get('q', '')) + '_done'\n    return None\n",
)

sys.path.insert(0, ROOT)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/components/astronverse-script/src"))
# 模拟工程包上下文(_get_auto_context 从 main 帧取 __package__)
__package__ = "dynpkg"  # noqa: A001
# stub: actionlib 依赖 report/i18n 等真实包已在 venv(editable), 直接导入
from astronverse.script.script import Script  # noqa: E402

PASS = []


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError("FAIL {}: {}".format(name, detail))
    PASS.append(name)
    print("ok -", name)


def main():
    # 1. 动态子流程: 名称变量 + 参数字典 + 输出回填
    res = Script.run_process_dynamic(process_name="sub_proc", process_param={"a": 3, "b": 4})
    check("process_dynamic v2 输出参数回填", res.get("out_total") == 7, str(res))
    check("process_dynamic 保留输入参数", res.get("a") == 3, str(res))

    # 2. 动态模块 v2: main(args)
    r2 = Script.run_module_dynamic(module_name="my_util", module_param={"x": 21})
    check("module_dynamic v2 返回值", r2 == {"doubled": 42}, str(r2))

    # 3. 动态模块 v1: main(**kwargs)
    r3 = Script.run_module_dynamic(module_name="my_util_v1", module_param={"x": 41})
    check("module_dynamic v1 兼容", r3 == 42, str(r3))

    # 4. 动态模块无参数
    r4 = Script.run_module_dynamic(module_name="my_util_v1")
    check("module_dynamic 缺省参数", r4 == 1, str(r4))

    # 5. 动态自定义指令: 编码(裸c-id) + 编码.main 两种写法
    r5 = Script.run_command_dynamic(component="c1990298105483890688", command_param={"q": "job"})
    check("command_dynamic 裸编码", r5.get("res") == "job_done", str(r5))
    r5b = Script.run_command_dynamic(component="c1990298105483890688.main", command_param={"q": "x"})
    check("command_dynamic 编码.main", r5b.get("res") == "x_done", str(r5b))

    # 6. __开头参数被过滤
    r6 = Script.run_command_dynamic(component="c1990298105483890688", command_param={"__info__": "z", "q": "k"})
    check("command_dynamic 过滤__参数", r6.get("res") == "k_done" and "__info__" not in r6, str(r6))

    # 7. 错误分支
    for name, fn in [
        ("空子流程名", lambda: Script.run_process_dynamic(process_name="")),
        ("空模块名", lambda: Script.run_module_dynamic(module_name="")),
        ("空编码", lambda: Script.run_command_dynamic(component="")),
        ("不存在子流程", lambda: Script.run_process_dynamic(process_name="ghost_proc")),
        ("不存在模块", lambda: Script.run_module_dynamic(module_name="ghost_util")),
        ("无main模块", lambda: Script.run_module_dynamic(module_name="no_main")),
        ("不存在组件", lambda: Script.run_command_dynamic(component="c000.main")),
    ]:
        try:
            fn()
            raise AssertionError("should raise: " + name)
        except AssertionError:
            raise
        except BaseException as e:
            assert "模块" in str(e) or "导入" in str(e) or "main" in str(e) or "字符串" in str(e), "{}: {}".format(
                name, e
            )
    check("7种错误分支全部拦截", True)


main()
print("\nALL {} PASSED".format(len(PASS)))
