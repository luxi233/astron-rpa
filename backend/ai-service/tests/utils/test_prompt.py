"""prompt 模板注册与格式化测试

场景:
T1 白名单注册: flow_generate/flow_fill_params/element_heal/element_search 均已注册且模板存在
T2 format_prompt 参数替换: flow_fill_params 的 $description/$steps 正确注入
T3 未知 prompt_type 抛 ValueError
"""

import pytest

from app.utils.prompt import PROMPTS_DIR, format_prompt, get_available_prompts, prompt_dict


def test_prompt_registry():
    # T1: AI 能力相关 prompt 均注册且模板文件存在
    for prompt_type in ("flow_generate", "flow_fill_params", "element_heal", "element_search"):
        assert prompt_type in prompt_dict
        assert (PROMPTS_DIR / prompt_dict[prompt_type]).exists()
    assert "flow_fill_params" in get_available_prompts()


def test_format_prompt_flow_fill_params():
    # T2: 占位符替换
    result = format_prompt(
        "flow_fill_params",
        {"description": "打开百度", "steps": "1. web_open|打开网页\n   url=网址(INPUT)"},
    )
    assert "打开百度" in result
    assert "url=网址(INPUT)" in result
    assert "$description" not in result
    assert "$steps" not in result


def test_format_prompt_unknown_type():
    # T3: 未知类型拒绝
    with pytest.raises(ValueError, match="Unknown prompt type"):
        format_prompt("no_such_prompt", {})
