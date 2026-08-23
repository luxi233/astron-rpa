"""LLM API client helpers: streaming and normal chat plus prompt interface."""

import json
import os
from pathlib import Path
from typing import Any

import requests
import sseclient
from astronverse.actionlib.atomic import atomicMg
from astronverse.ai.error import (
    LLM_NO_RESPONSE_ERROR,
    LLM_REQUEST_ERROR,
    LLM_RESPONSE_FORMAT_ERROR,
)
from astronverse.baseline.error.error import BaseException
from astronverse.baseline.logger.logger import logger

DEFAULT_MODEL = "xopdeepseekv32"
DEFAULT_GATEWAY_PORT = "13159"


def resolve_gateway_port() -> str:
    """网关端口解析链: 流程注入配置 → 环境变量 → gateway.json(scheduler 启动写) → 默认。"""
    try:
        port = atomicMg.cfg().get("GATEWAY_PORT")
        if port:
            return str(port)
    except Exception:
        pass
    port = os.environ.get("ASTRON_GATEWAY_PORT")
    if port:
        return port
    try:
        data = json.loads((Path.home() / ".astronverse" / "gateway.json").read_text(encoding="utf-8"))
        if data.get("route_port"):
            return str(data["route_port"])
    except Exception:
        pass
    return DEFAULT_GATEWAY_PORT


def _api_url(path: str) -> str:
    return "http://127.0.0.1:{}/api/rpa-ai-service{}".format(resolve_gateway_port(), path)


def chat_streamable(messages: Any, model: str = DEFAULT_MODEL):
    """
    调用远端大模型

    :param
    messages: 历史问题
    model: 模型id

    - example
        inputs = [
            {"role": "assistant", "content": "请模仿李白的口吻"},
            {"role": "user", "content": "写一首咏鹅诗"}
        ]

        outputs = {"content":"笔","reasoning_content":null}

    """
    chat_json = {"messages": messages, "model": model, "stream": True}

    response = requests.post(_api_url("/v1/chat/completions"), json=chat_json)
    if response.status_code == 200:
        client = sseclient.SSEClient(response)  # type: ignore
        for event in client.events():
            if event.data and event.data != "[DONE]":
                response_json = json.loads(event.data)
                if response_json.get("choices"):
                    yield response_json["choices"][0]["delta"]["content"]
    else:
        raise BaseException(LLM_NO_RESPONSE_ERROR.format(response), "")


def chat_normal(user_input, system_input="", model=DEFAULT_MODEL):
    """非流式对话, 返回模型回复文本; 请求失败/响应异常抛出明确错误"""
    data = {
        "model": model,  # 选择大模型，替换为实际模型标识
        "messages": [
            {"role": "system", "content": system_input},
            {"role": "user", "content": user_input},
        ],
        "stream": False,
    }

    try:
        response = requests.post(_api_url("/v1/chat/completions"), json=data)
        response.raise_for_status()  # 检查请求是否成功

        # 返回模型生成的回复
        response_json = response.json()

        # 兼容两种响应格式
        if "data" in response_json and "choices" in response_json["data"]:
            # 新格式
            return response_json["data"]["choices"][0]["message"]["content"]
        elif "choices" in response_json:
            # 原格式
            return response_json["choices"][0]["message"]["content"]
        raise BaseException(LLM_RESPONSE_FORMAT_ERROR, "")

    except requests.exceptions.RequestException as e:
        logger.info(f"请求错误: {e}")
        raise BaseException(LLM_REQUEST_ERROR.format(e), "")
    except (KeyError, IndexError, TypeError):
        raise BaseException(LLM_RESPONSE_FORMAT_ERROR, "")


def chat_prompt(prompt_type, params, model=DEFAULT_MODEL):
    """调用预设 prompt 模板, 返回模型回复文本; 请求失败/响应异常抛出明确错误"""
    data = {
        "model": model,  # 选择大模型，替换为实际模型标识
        "prompt_type": prompt_type,
        "params": params,
    }

    try:
        response = requests.post(_api_url("/v1/chat/prompt"), json=data)
        response.raise_for_status()  # 检查请求是否成功

        # 返回模型生成的回复
        response_json = response.json()
        if "data" not in response_json:
            raise BaseException(LLM_RESPONSE_FORMAT_ERROR, "")
        return response_json["data"]

    except requests.exceptions.RequestException as e:
        logger.info(f"请求错误: {e}")
        raise BaseException(LLM_REQUEST_ERROR.format(e), "")
    except (KeyError, IndexError, TypeError):
        raise BaseException(LLM_RESPONSE_FORMAT_ERROR, "")
