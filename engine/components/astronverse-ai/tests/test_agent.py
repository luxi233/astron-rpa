"""xcAgent 客户端与 Agent 原子组件测试(全 mock 外呼, 不依赖真实星环服务)。"""

import json
import unittest
from unittest import mock

from astronverse.ai.agent import Agent
from astronverse.ai.api import xcagent as xc_mod
from astronverse.ai.api.xcagent import xcAgent


class _FakeHttpResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeHttpConnection:
    """模拟 http.client.HTTPSConnection: 捕获请求并返回星环流式首行响应"""

    last_payload = None

    def __init__(self, *args, **kwargs):
        pass

    def request(self, method, path, payload, headers, **kwargs):
        type(self).last_payload = json.loads(payload)

    def getresponse(self):
        response = mock.Mock()
        response.readline.return_value = json.dumps(
            {"choices": [{"delta": {"content": "执行结果"}}]}
        ).encode("utf-8")
        return response


class TestRunFlowWithParams(unittest.TestCase):
    def test_参数字典直传(self):
        agent = xcAgent("key", "secret")
        with mock.patch.object(xc_mod.http.client, "HTTPSConnection", _FakeHttpConnection):
            result = agent.run_flow_with_params(
                "flow-1", {"AGENT_USER_INPUT": "你好", "ext": "附加参数"}, False
            )
        self.assertEqual(result, "执行结果")
        self.assertEqual(
            _FakeHttpConnection.last_payload,
            {"flow_id": "flow-1", "parameters": {"AGENT_USER_INPUT": "你好", "ext": "附加参数"}, "stream": False},
        )


class TestRunFlow(unittest.TestCase):
    def test_无变量名仅用户输入(self):
        agent = xcAgent("key", "secret")
        with mock.patch.object(xc_mod.http.client, "HTTPSConnection", _FakeHttpConnection):
            result = agent.run_flow("flow-1", "你好", False, False, "", "", "")
        self.assertEqual(result, "执行结果")
        self.assertEqual(
            _FakeHttpConnection.last_payload["parameters"], {"AGENT_USER_INPUT": "你好"}
        )

    def test_文件变量上传后传URL(self):
        agent = xcAgent("key", "secret")
        upload_resp = _FakeHttpResponse({"data": {"url": "https://oss/file.pdf"}})
        with (
            mock.patch.object(agent, "upload_file", return_value=upload_resp),
            mock.patch.object(xc_mod.http.client, "HTTPSConnection", _FakeHttpConnection),
        ):
            agent.run_flow("flow-1", "解析附件", False, True, "doc", "", "/tmp/a.pdf")
        self.assertEqual(
            _FakeHttpConnection.last_payload["parameters"],
            {"AGENT_USER_INPUT": "解析附件", "doc": "https://oss/file.pdf"},
        )


class TestGetContentType(unittest.TestCase):
    def test_常见扩展映射(self):
        self.assertEqual(xcAgent.get_content_type("a.png"), "image/png")
        self.assertEqual(xcAgent.get_content_type("b.PDF"), "application/pdf")
        self.assertEqual(xcAgent.get_content_type("c.unknownext"), "application/octet-stream")


class TestCallAstronAgent(unittest.TestCase):
    """AI 工作流原子组件: inputs 列表转参数字典并调用星环(修复前调不存在方法必抛 AttributeError)"""

    def _run(self):
        workflow = {
            "authId": "auth-1",
            "agentId": "flow-1",
            "inputs": [
                {"key": "AGENT_USER_INPUT", "value": "生成周报", "type": "string"},
                {"key": "doc", "value": "https://oss/x.pdf", "type": "file"},
            ],
        }
        return Agent.call_astron_agent(workflow)

    def test_inputs转参数字典执行(self):
        auth_resp = _FakeHttpResponse({"data": {"api_key": "k", "api_secret": "s"}})
        with (
            mock.patch("astronverse.ai.agent.requests.get", return_value=auth_resp) as get,
            mock.patch.object(xcAgent, "run_flow_with_params", return_value="执行结果") as run,
        ):
            result = self._run()
        self.assertEqual(result, "执行结果")
        self.assertIn("get-astron-by-id", get.call_args[0][0])
        self.assertEqual(get.call_args[1]["params"], {"id": "auth-1"})
        self.assertEqual(
            run.call_args[0][1],
            {"AGENT_USER_INPUT": "生成周报", "doc": "https://oss/x.pdf"},
        )
        self.assertFalse(run.call_args[0][2])


if __name__ == "__main__":
    unittest.main()
