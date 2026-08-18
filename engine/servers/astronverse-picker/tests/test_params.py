"""复杂参数解析器单测 (utils/params.py)"""

import pytest

from astronverse.picker.utils.params import (
    ComplexParamParser,
    GlobalVarRewriter,
    ParamType,
    _compile_expression,
    complex_param_parser,
    refactor_globals,
)


class TestPreParamHandler:
    def test_结构化列表data优先于value(self):
        ls = ComplexParamParser.pre_param_handler([{"type": "str", "value": "old", "data": "new"}])
        assert ls == [{"type": "str", "data": "new"}]

    def test_缺data回退value且删除value键(self):
        ls = ComplexParamParser.pre_param_handler([{"type": "str", "value": "v"}])
        assert ls == [{"type": "str", "data": "v"}]
        assert "value" not in ls[0]

    def test_空data段被过滤(self):
        ls = ComplexParamParser.pre_param_handler([{"type": "str", "value": "a"}, {"type": "str", "value": ""}])
        assert ls == [{"type": "str", "data": "a"}]

    def test_全空时保留首段(self):
        ls = ComplexParamParser.pre_param_handler([{"type": "str", "value": ""}])
        assert ls == [{"type": "str", "data": ""}]

    def test_单段python空值转None(self):
        ls = ComplexParamParser.pre_param_handler([{"type": "python", "value": ""}])
        assert ls[0]["data"] is None

    def test_非结构化输入回退other(self):
        assert ComplexParamParser.pre_param_handler("纯文本") == [{"type": "other", "data": "纯文本"}]
        assert ComplexParamParser.pre_param_handler(123) == [{"type": "other", "data": 123}]
        assert ComplexParamParser.pre_param_handler([]) == [{"type": "other", "data": []}]
        assert ComplexParamParser.pre_param_handler([{"no_type": 1}]) == [{"type": "other", "data": [{"no_type": 1}]}]


class TestParamToEval:
    def test_单段str无需eval(self):
        code, need_eval = ComplexParamParser.param_to_eval([{"type": "str", "data": "abc"}])
        assert (code, need_eval) == ("abc", False)

    def test_多段str直接拼接(self):
        """回归: 曾误返回3元组导致上游解包 ValueError"""
        code, need_eval = ComplexParamParser.param_to_eval([{"type": "str", "data": "a"}, {"type": "str", "data": "b"}])
        assert (code, need_eval) == ("ab", False)

    def test_python段触发eval(self):
        code, need_eval = ComplexParamParser.param_to_eval([{"type": "python", "data": "1+1"}])
        assert need_eval is True
        assert code == "1+1"

    def test_var段触发eval(self):
        for t in ["var", "p_var", "g_var"]:
            _, need_eval = ComplexParamParser.param_to_eval([{"type": t, "data": "x"}])
            assert need_eval is True, f"{t} 应触发 eval"

    def test_多段混合eval用str拼接(self):
        code, need_eval = ComplexParamParser.param_to_eval(
            [{"type": "str", "data": "ID:"}, {"type": "python", "data": "100*2"}]
        )
        assert need_eval is True
        assert code == "str('ID:')+str(100*2)"

    def test_gv白名单变量改写(self):
        code, _ = ComplexParamParser.param_to_eval([{"type": "python", "data": "name"}], gv={"name": "tom", "age": 3})
        # astor 代码生成统一使用单引号
        assert code == "gv['name']"


class TestRefactorGlobals:
    def test_白名单改写_gv下标(self):
        assert refactor_globals("x + y", ["x"]) == "gv['x'] + y"

    def test_非白名单不改写(self):
        assert refactor_globals("a + b", []) == "a + b"

    def test_赋值目标同样改写但保留ctx(self):
        out = refactor_globals("x = 1", ["x"])
        assert "gv['x'] = 1" in out


class TestParseAndEvaluate:
    def test_rpa_special_生成表达式对象(self):
        out = ComplexParamParser.parse_params({"rpa": "special", "value": [{"type": "python", "value": "1+2"}]})
        assert hasattr(out, "eval")
        assert ComplexParamParser.evaluate_params(out) == 3

    def test_普通dict递归处理(self):
        src = {"a": {"rpa": "special", "value": [{"type": "python", "value": "2*3"}]}, "b": "文本"}
        out = ComplexParamParser.parse_params(src)
        assert ComplexParamParser.evaluate_params(out) == {"a": 6, "b": "文本"}

    def test_list递归处理(self):
        src = [{"rpa": "special", "value": [{"type": "python", "value": "'x'*2"}]}]
        out = ComplexParamParser.parse_params(src)
        assert ComplexParamParser.evaluate_params(out) == ["xx"]

    def test_非列表value直接返回(self):
        out = ComplexParamParser.parse_params({"rpa": "special", "value": 42})
        assert out == 42

    def test_表达式求值上下文注入(self):
        out = ComplexParamParser.parse_params({"rpa": "special", "value": [{"type": "python", "value": "v1+1"}]})
        assert ComplexParamParser.evaluate_params(out, {"v1": 9}) == 10

    def test_表达式对象缓存(self):
        assert _compile_expression("1") is _compile_expression("1")


class TestComplexParamParserEndToEnd:
    def test_端到端_全局变量注入(self):
        source = {"rpa": "special", "value": [{"type": "python", "value": "greet + name"}]}
        globals_data = [
            {"varName": "greet", "varValue": '"你好 "'},
            {"varName": "name", "varValue": '"世界"'},
        ]
        assert complex_param_parser(source, globals_data) == "你好 世界"

    def test_端到端_纯文本参数(self):
        assert complex_param_parser("hello", []) == "hello"

    def test_端到端_全局变量JSON对象被repr为python字面量(self):
        """实现现状: JSON 对象全局变量经非 eval 路径序列化为 python repr 字符串(单引号),
        非 JSON 格式, 表达式中需 eval 字面量取值"""
        expr = "eval(cfg)['k']"
        source = {"rpa": "special", "value": [{"type": "python", "value": expr}]}
        globals_data = [{"varName": "cfg", "varValue": '{"k": "v"}'}]
        assert complex_param_parser(source, globals_data) == "v"

    def test_端到端_全局变量空值为空串(self):
        source = {"rpa": "special", "value": [{"type": "python", "value": "gv.get('x') == ''"}]}
        assert complex_param_parser(source, [{"varName": "x", "varValue": ""}]) is True


class TestParamType:
    def test_枚举与字典(self):
        assert ParamType.PYTHON.value == "python"
        d = ParamType.to_dict()
        assert d == {v: v for v in d.values()}
        assert set(d) == {"python", "var", "p_var", "g_var", "str", "other", "element"}
