"""LLM 客户端测试: 网关端口解析链 / 对话接口成功与失败路径。"""

import json
import os
import unittest
from unittest import mock

from astronverse.ai.api import llm
from astronverse.ai.error import LLM_REQUEST_ERROR, LLM_RESPONSE_FORMAT_ERROR


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError("HTTP {}".format(self.status_code))

    def json(self):
        return self._payload


class TestResolveGatewayPort(unittest.TestCase):
    """网关端口解析链: 流程配置 → 环境变量 → gateway.json → 默认"""

    def test_默认端口(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch.dict(os.environ, {"ASTRON_GATEWAY_PORT": ""}, clear=False):
                with mock.patch.object(llm.atomicMg, "cfg", return_value={}):
                    with mock.patch.object(llm.Path, "home", staticmethod(lambda: home)):
                        self.assertEqual(llm.resolve_gateway_port(), llm.DEFAULT_GATEWAY_PORT)

    def test_流程配置优先(self):
        with mock.patch.object(llm.atomicMg, "cfg", return_value={"GATEWAY_PORT": 17777}):
            with mock.patch.dict(os.environ, {"ASTRON_GATEWAY_PORT": "18888"}, clear=False):
                self.assertEqual(llm.resolve_gateway_port(), "17777")

    def test_环境变量优先(self):
        with mock.patch.object(llm.atomicMg, "cfg", return_value={}):
            with mock.patch.dict(os.environ, {"ASTRON_GATEWAY_PORT": "18888"}, clear=False):
                self.assertEqual(llm.resolve_gateway_port(), "18888")

    def test_gateway_json兜底(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".astronverse").mkdir()
            (home / ".astronverse" / "gateway.json").write_text(json.dumps({"route_port": 20000}))
            with mock.patch.dict(os.environ, {"ASTRON_GATEWAY_PORT": ""}, clear=False):
                with mock.patch.object(llm.atomicMg, "cfg", return_value={}):
                    with mock.patch.object(llm.Path, "home", staticmethod(lambda: home)):
                        self.assertEqual(llm.resolve_gateway_port(), "20000")


class TestChatNormal(unittest.TestCase):
    def test_原格式响应(self):
        resp = _FakeResponse({"choices": [{"message": {"content": "你好"}}]})
        with mock.patch.object(llm.requests, "post", return_value=resp) as post:
            self.assertEqual(llm.chat_normal("hi"), "你好")
            url = post.call_args[0][0]
            self.assertIn("/api/rpa-ai-service/v1/chat/completions", url)

    def test_新格式响应(self):
        resp = _FakeResponse({"data": {"choices": [{"message": {"content": "你好"}}]}})
        with mock.patch.object(llm.requests, "post", return_value=resp):
            self.assertEqual(llm.chat_normal("hi"), "你好")

    def test_请求失败抛明确异常(self):
        import requests

        with mock.patch.object(llm.requests, "post", side_effect=requests.exceptions.ConnectionError("refused")):
            with self.assertRaises(Exception) as ctx:
                llm.chat_normal("hi")
            self.assertIn("大模型请求失败", str(ctx.exception))

    def test_响应格式错误抛明确异常(self):
        resp = _FakeResponse({"unexpected": True})
        with mock.patch.object(llm.requests, "post", return_value=resp):
            with self.assertRaises(Exception) as ctx:
                llm.chat_normal("hi")
            self.assertIn(LLM_RESPONSE_FORMAT_ERROR.message, str(ctx.exception))


class TestChatPrompt(unittest.TestCase):
    def test_成功返回data(self):
        resp = _FakeResponse({"code": "0000", "data": "结构化结果"})
        with mock.patch.object(llm.requests, "post", return_value=resp) as post:
            self.assertEqual(llm.chat_prompt("contract", {"factors": "[]"}), "结构化结果")
            url = post.call_args[0][0]
            self.assertIn("/api/rpa-ai-service/v1/chat/prompt", url)

    def test_请求失败抛明确异常(self):
        import requests

        with mock.patch.object(llm.requests, "post", side_effect=requests.exceptions.Timeout("timeout")):
            with self.assertRaises(Exception):
                llm.chat_prompt("contract", {})

    def test_响应缺data抛格式异常(self):
        resp = _FakeResponse({"code": "5000", "msg": "error"})
        with mock.patch.object(llm.requests, "post", return_value=resp):
            with self.assertRaises(Exception) as ctx:
                llm.chat_prompt("contract", {})
            self.assertIn(LLM_RESPONSE_FORMAT_ERROR.message, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
