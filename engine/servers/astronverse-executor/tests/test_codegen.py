"""代码生成链路 golden 测试(E7)。

流程 JSON → Lexer → Parser → AST.display 全链路:
以"生成代码可被 compile 编译"为强不变量, 叠加关键结构断言固化现状。
"""

import pytest
from conftest import PROCESS_ID, atom, ctrl, gen, inp, out


def _compile(code: str):
    compile(code, "<generated>", "exec")


class TestAtomic:
    def test_单原子生成调用与行映射(self):
        _, code, map_res = gen([atom("Mouse.click", src="astronverse.system.mouse.click", inputs=[inp("x", 10, "python")])])
        _compile(code)
        assert "astronverse.system.mouse.click(x=10" in code
        assert f"__info__=[1, '{PROCESS_ID}']" in code
        # map 记录 生成行号:流程行号, 流程行1必须存在
        assert ":1" in map_res
        assert "def main(args):" in code

    def test_原子带输出变量(self):
        _, code, _ = gen([atom("Data.get", src="astronverse.fake.data.get", outputs=[out("res", "my_var")])])
        _compile(code)
        assert "my_var = astronverse.fake.data.get(" in code

    def test_group与note节点被词法过滤(self):
        _, code, _ = gen([ctrl("Code.Note"), ctrl("Code.Group"), atom("A.b", src="astronverse.fake.a.b"), ctrl("Code.GroupEnd")])
        _compile(code)
        assert "astronverse.fake.a.b(" in code
        assert "Note" not in code

    def test_重试包装(self):
        inputs = [
            inp("__skip_err__", "retry"),
            inp("__retry_time__", 2, "other"),
            inp("__retry_interval__", 0.5, "other"),
        ]
        _, code, _ = gen([atom("A.b", src="astronverse.fake.a.b", inputs=inputs)])
        _compile(code)
        assert "__retry_count_1__ = 2" in code
        assert "while True:" in code
        assert "__in_external_retry__=True" in code
        assert "time.sleep(0.5)" in code
        # 重试展开后 import 自动补齐
        assert "import time" in code

    def test_跳过包装(self):
        _, code, _ = gen([atom("A.b", src="astronverse.fake.a.b", inputs=[inp("__skip_err__", "skip")])])
        _compile(code)
        assert '执行跳过' in code
        assert "__in_external_retry__=True" in code
        assert "raise" not in code.split("except Exception")[1]

    def test_debug模式禁用重试包装(self):
        _, code, _ = gen(
            [atom("A.b", src="astronverse.fake.a.b", inputs=[inp("__skip_err__", "retry"), inp("__retry_time__", 2, "other")])],
            debug_mode=True,
        )
        _compile(code)
        assert "while True:" not in code
        assert '__skip_err__="exit"' in code
        assert "__retry_time__" not in code


class TestControlFlow:
    def test_if_elif_else(self):
        flow = [
            ctrl("Code.If", inputs=[inp("condition", "1==1", "python")]),
            atom("A.b", src="astronverse.fake.a.b"),
            ctrl("Code.ElseIf", inputs=[inp("condition", "2==2", "python")]),
            atom("A.c", src="astronverse.fake.a.c"),
            ctrl("Code.Else"),
            atom("A.d", src="astronverse.fake.a.d"),
            ctrl("Code.IfEnd"),
        ]
        _, code, _ = gen(flow)
        _compile(code)
        # 控制流调用同样携带 __info__ 尾参, 用前缀匹配固化
        assert "if consequence(condition=1==1, __info__=" in code
        assert "elif consequence(condition=2==2, __info__=" in code
        assert "else:" in code

    def test_多条件if使用consequence_multi(self):
        flow = [ctrl("Code.IfMulti", inputs=[inp("condition", "1==1", "python")]), atom("A.b", src="astronverse.fake.a.b"), ctrl("Code.IfEnd")]
        _, code, _ = gen(flow)
        _compile(code)
        assert "if consequence_multi(" in code

    def test_空if体补pass(self):
        flow = [ctrl("Code.If", inputs=[inp("condition", "1==1", "python")]), ctrl("Code.IfEnd")]
        _, code, _ = gen(flow)
        _compile(code)
        assert "pass" in code

    def test_while条件循环与break(self):
        flow = [
            ctrl("Code.While", inputs=[inp("condition", "x<3", "python")]),
            ctrl("Code.Break"),
            ctrl("Code.ForEnd"),
        ]
        _, code, _ = gen(flow)
        _compile(code)
        assert "while consequence(condition=x<3, __info__=" in code
        assert "break" in code

    def test_无限循环(self):
        flow = [ctrl("Code.Infinite"), ctrl("Code.Continue"), ctrl("Code.ForEnd")]
        _, code, _ = gen(flow)
        _compile(code)
        assert "while True:" in code
        assert "continue" in code

    def test_for步长循环(self):
        flow = [
            ctrl("Code.ForStep", inputs=[inp("start", 0, "python"), inp("end", 10, "python"), inp("step", 1, "python")], outputs=[out("i", "idx")]),
            atom("A.b", src="astronverse.fake.a.b"),
            ctrl("Code.ForEnd"),
        ]
        _, code, _ = gen(flow)
        _compile(code)
        assert "for idx in range(" in code

    def test_for列表循环双输出(self):
        flow = [
            ctrl("Code.ForList", inputs=[inp("lists", "[1,2]", "python")], outputs=[out("index", "i"), out("item", "v")]),
            atom("A.b", src="astronverse.fake.a.b"),
            ctrl("Code.ForEnd"),
        ]
        _, code, _ = gen(flow)
        _compile(code)
        assert "for i, v in enumerate(" in code

    def test_try_catch_finally(self):
        flow = [
            ctrl("Code.Try"),
            atom("A.b", src="astronverse.fake.a.b"),
            ctrl("Code.Catch", outputs=[out("err", "err_msg")]),
            atom("A.c", src="astronverse.fake.a.c"),
            ctrl("Code.Finally"),
            atom("A.d", src="astronverse.fake.a.d"),
            ctrl("Code.TryEnd"),
        ]
        _, code, _ = gen(flow)
        _compile(code)
        assert "try:" in code
        assert "except Exception as e:" in code
        assert "err_msg = str(e)" in code
        assert "finally:" in code

    def test_循环外break报语法错误(self):
        with pytest.raises(Exception) as exc_info:
            gen([ctrl("Code.Break")])
        assert "语法错误" in str(exc_info.value)

    def test_循环外continue报语法错误(self):
        with pytest.raises(Exception) as exc_info:
            gen([ctrl("Code.Continue")])
        assert "语法错误" in str(exc_info.value)


class TestSpecialAtomic:
    def test_存在判断原子生成if(self):
        flow = [
            atom("BrowserElement.element_visible", src="astronverse.fake.be.visible", inputs=[inp("ele", "{}", "element")]),
            atom("A.b", src="astronverse.fake.a.b"),
            ctrl("Code.IfEnd"),
        ]
        _, code, _ = gen(flow)
        _compile(code)
        assert "if astronverse.fake.be.visible(" in code

    def test_相似元素循环原子生成for(self):
        flow = [
            atom("WinEle.loop_similar", src="astronverse.fake.win.loop", outputs=[out("index", "i"), out("item", "ele")]),
            atom("A.b", src="astronverse.fake.a.b"),
            ctrl("Code.ForEnd"),
        ]
        _, code, _ = gen(flow)
        _compile(code)
        assert "for i,ele in astronverse.fake.win.loop(" in code or "for i, ele in astronverse.fake.win.loop(" in code

    def test_禁用节点跳过但保留行号(self):
        flow = [atom("A.b", src="astronverse.fake.a.b", disabled=True), atom("A.c", src="astronverse.fake.a.c")]
        _, code, map_res = gen(flow)
        _compile(code)
        assert "astronverse.fake.a.b(" not in code
        # 第二个节点流程行号为2(disabled占行号)
        assert ":2" in map_res


class TestMainParams:
    def test_流程参数注入与输出回写(self):
        param_list = [
            {"varName": "url", "varType": "Str", "varValue": "http://a", "varDirection": 0},
            {"varName": "result", "varType": "Str", "varValue": "", "varDirection": 1},
        ]
        _, code, _ = gen([atom("A.b", src="astronverse.fake.a.b")], param_list=param_list)
        _compile(code)
        assert 'url = args.get("url"' in code
        assert 'args["result"] = result' in code
