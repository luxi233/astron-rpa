"""参数解析单测(E1 回归 + E8)。

覆盖 pre_param_handler 过滤规则 / _param_to_eval 三分支 / parse_param 特殊标记 /
parse_input 默认值过滤 / refactor_globals 全局变量改写。
"""

from conftest import PROJECT_ID, make_svc

from astronverse.executor.flow.params import Param, refactor_globals
from astronverse.executor.flow.syntax import Token


class TestPreParamHandler:
    def test_data优先并过滤空值(self):
        ls = Param.pre_param_handler([{"type": "str", "value": "x"}, {"type": "str", "value": ""}])
        assert ls == [{"type": "str", "data": "x"}]

    def test_全空保留首项(self):
        ls = Param.pre_param_handler([{"type": "str", "value": ""}])
        assert len(ls) == 1
        assert ls[0]["data"] == ""

    def test_python空值转None(self):
        ls = Param.pre_param_handler([{"type": "python", "value": ""}])
        assert ls[0]["data"] is None

    def test_非列表包装为other(self):
        ls = Param.pre_param_handler("abc")
        assert ls == [{"type": "other", "data": "abc"}]


class TestParamToEval:
    def test_单段直接返回(self):
        value, need_eval = Param(None)._param_to_eval([{"type": "str", "data": "hello"}])
        assert value == "hello"
        assert need_eval is False

    def test_多段纯文本拼接返回2元组(self):
        # E1 回归: 历史版本此分支误返 3 元组, 调用方解包即崩溃
        value, need_eval = Param(None)._param_to_eval(
            [{"type": "str", "data": "hello "}, {"type": "str", "data": "world"}]
        )
        assert value == "hello world"
        assert need_eval is False

    def test_混排表达式走eval拼接(self):
        value, need_eval = Param(None)._param_to_eval(
            [{"type": "str", "data": "count="}, {"type": "python", "data": "1+2"}]
        )
        assert need_eval is True
        assert value == "str('count=')+str(1+2)"


class TestParseParam:
    def test_多段纯文本端到端不崩溃(self):
        # E1 回归: parse_param 按 2 元组解包 _param_to_eval
        svc = make_svc()
        res = svc.param.parse_param(
            {"name": "x", "value": [{"type": "str", "value": "a"}, {"type": "str", "value": "b"}]}
        )
        assert res.value == "ab"
        assert res.need_eval is False

    def test_元素参数特殊标记(self):
        svc = make_svc()
        res = svc.param.parse_param({"name": "ele", "value": [{"type": "element", "value": "{}"}]})
        assert res.special == "element"

    def test_json_str解析(self):
        svc = make_svc()
        res = svc.param.parse_param({"name": "cfg", "value": '{"a": 1}', "need_parse": "json_str"})
        assert res.value == {"a": 1}
        assert res.need_eval is True

    def test_json_str空值转空列表(self):
        svc = make_svc()
        res = svc.param.parse_param({"name": "cfg", "value": "", "need_parse": "json_str"})
        assert res.value == []


class TestParseInput:
    def test_默认高级选项被过滤(self):
        svc = make_svc()
        token = Token(
            type="A.b",
            value={
                "key": "A.b",
                "__line__": 1,
                "__process_id__": "p",
                "inputList": [
                    {"key": "__delay_before__", "name": "__delay_before__", "value": [{"type": "other", "value": 0}]},
                    {"key": "__skip_err__", "name": "__skip_err__", "value": "exit"},
                    {"key": "url", "name": "url", "title": "地址", "value": [{"type": "str", "value": "http://a"}]},
                ],
            },
        )
        res = svc.param.parse_input(token)
        assert "__delay_before__" not in res
        assert "__skip_err__" not in res
        assert "url" in res
        # 行号/流程id 恒注入: 结果 dict 的 key 为 "info", 参数 key 仍保留 __info__ 原名
        assert "info" in res
        assert res["info"].key == "__info__"
        assert res["info"].value == [1, "p"]
        assert svc.ast_globals_dict[PROJECT_ID].atomic_info["A.b"].params_name == {"url": "地址"}

    def test_非默认高级选项保留(self):
        svc = make_svc()
        token = Token(
            type="A.b",
            value={
                "key": "A.b",
                "__line__": 1,
                "__process_id__": "p",
                "inputList": [
                    {"key": "__delay_before__", "name": "__delay_before__", "value": [{"type": "other", "value": 2}]},
                ],
            },
        )
        res = svc.param.parse_input(token)
        assert "__delay_before__" in res

    def test_show_false被过滤(self):
        svc = make_svc()
        token = Token(
            type="A.b",
            value={
                "key": "A.b",
                "__line__": 1,
                "__process_id__": "p",
                "inputList": [
                    {"key": "hidden", "name": "hidden", "show": False, "value": [{"type": "str", "value": "x"}]},
                ],
            },
        )
        res = svc.param.parse_input(token)
        assert "hidden" not in res


class TestRefactorGlobals:
    def test_变量改写为gv下标(self):
        # astor 重生成使用单引号字符串
        assert refactor_globals("x + 1", ["x"]) == "gv['x'] + 1"

    def test_非白名单变量不改写(self):
        assert refactor_globals("y + 1", ["x"]) == "y + 1"
