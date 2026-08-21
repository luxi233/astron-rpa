#!/usr/bin/env python3

"""ComplexParamParser 复杂参数解析/求值单测。

注意: parse_params/evaluate_params 依赖 _get_auto_context 沿调用栈寻找名为
main 的帧收集流程变量(生产环境由 executor 编译出的 main.py 提供);
因此用例必须把解析/求值调用包在名为 main 的函数内, 否则自动上下文为空。
"""

from astronverse.workflowlib.params import ComplexParamParser

_SOURCE_DICT = {
    "python_expr": {"rpa": "special", "value": [{"type": "python", "data": "len(user_list)"}]},
    "flow_var": {"rpa": "special", "value": [{"type": "var", "data": "current_user"}]},
    "global_var": {"rpa": "special", "value": [{"type": "g_var", "data": "api_base_url"}]},
    "mixed": {"rpa": "special", "value": [
        {"type": "var", "data": "prefix"},
        {"type": "str", "data": "_"},
        {"type": "g_var", "data": "suffix"}
    ]},

    "nested": {
        "deep": [
            {"rpa": "special", "value": [{"type": "var", "data": "deep_var"}]},
            {"rpa": "special", "value": [{"type": "other", "data": "deep_var"}]},
            {"rpa": "special", "value": [{"type": "str", "data": "deep_var"}]},
        ]
    }
}

# _get_auto_context 从 main 帧的模块全局(f_globals)取 gv, 故 gv 必须是模块级变量
# (生产环境 main.py 的 gv 由 from .package import gv 导入, 同为模块全局)
gv = {
    "api_base_url": "https://api.example.com",
    "suffix": "_end"
}


def main():
    # 模拟运行时变量(main 帧局部变量会被 _get_auto_context 经栈帧反射收集,
    # 代码中不直接引用, 故静态检查报未使用, 此处显式豁免)
    user_list = ["a", "b"]  # noqa: F841
    current_user = "A()"  # noqa: F841
    prefix = "order"  # noqa: F841
    deep_var = "nested_value"  # noqa: F841

    _processor = ComplexParamParser()
    template = _processor.parse_params(_SOURCE_DICT)

    # 提供额外的变量上下文(覆盖同名 main 帧变量)
    ctx = {
        'prefix': "order2",  # 覆盖原来的值
    }
    return _processor.evaluate_params(template, ctx)


def test_complex_param_parser():
    """测试复杂参数解析器: 表达式求值/流变量/全局变量改写/混合拼接/嵌套结构"""
    result = main()

    assert result["python_expr"] == 2  # len(user_list)
    assert result["flow_var"] == "A()"
    assert result["global_var"] == "https://api.example.com"  # g_var 经 gv 改写后命中
    assert result["mixed"] == "order2__end"  # ctx 的 prefix 覆盖 main 帧值
    assert result["nested"]["deep"] == ["nested_value", "deep_var", "deep_var"]
    # 注: 仅 var/python/g_var/p_var 参与变量求值; str/other 在混合表达式中
    # 按字面量原样输出("deep_var" 而非变量值)


def test_无main帧时自动上下文降级为空字典():
    """无 main 帧(如非执行环境)时 _get_auto_context 降级返回空字典, 不应抛异常"""
    assert ComplexParamParser._get_auto_context() == {}


def test_纯字符串参数免eval直出():
    """全 str 片段不需要 eval, parse 阶段即得最终字符串"""
    source = {"k": {"rpa": "special", "value": [{"type": "str", "data": "a"}, {"type": "str", "data": "b"}]}}
    template = ComplexParamParser.parse_params(source)
    assert template["k"] == "ab"


if __name__ == "__main__":
    test_complex_param_parser()
