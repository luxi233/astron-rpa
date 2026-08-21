"""存储层单测(E2/E3 回归 + merge_dicts)。

覆盖: 缺 key 节点防护 / 网关请求超时与异常转换 / merge_dicts 字段合并。
"""

import json

import pytest
import requests
from conftest import make_svc

import astronverse.executor.flow.storage as storage_mod
from astronverse.executor.flow.storage import HttpStorage, merge_dicts


class TestProcessDetail:
    def test_缺key节点被跳过且不崩溃(self):
        # E2 回归: 历史版本 None.startswith 直接 AttributeError 拖垮整个工程生成
        storage = HttpStorage(make_svc())
        flow_list = [
            {"key": "A.b", "inputList": [], "outputList": []},
            {"title": "无key节点"},
            {"key": "A.c", "inputList": [], "outputList": []},
        ]

        def fake_http(self, url, params, data, meta="post"):
            if "process-json" in url:
                return json.dumps(flow_list)
            return []  # atom-new/list

        monkey_ok = pytest.MonkeyPatch()
        monkey_ok.setattr(HttpStorage, "__http__", fake_http)
        try:
            res = storage.process_detail("p", "", "", "proc")
        finally:
            monkey_ok.undo()

        assert [f["key"] for f in res] == ["A.b", "A.c"]

    def test_兼容key改写生效(self):
        storage = HttpStorage(make_svc())
        flow_list = [{"key": "Code.Process", "inputList": [], "outputList": []}]

        def fake_http(self, url, params, data, meta="post"):
            if "process-json" in url:
                return json.dumps(flow_list)
            return []

        monkey = pytest.MonkeyPatch()
        monkey.setattr(HttpStorage, "__http__", fake_http)
        try:
            res = storage.process_detail("p", "", "", "proc")
        finally:
            monkey.undo()

        assert res[0]["key"] == "Script.process"


class TestHttpTimeout:
    def test_请求携带超时参数(self):
        # E3 回归: 网关无响应时必须快速失败而非无限挂起
        captured = {}

        class FakeResp:
            status_code = 200

            def json(self):
                return {"code": "000000", "data": {"ok": 1}}

        def fake_post(url, json=None, params=None, timeout=None):
            captured["timeout"] = timeout
            return FakeResp()

        monkey = pytest.MonkeyPatch()
        monkey.setattr(requests, "post", fake_post)
        try:
            res = HttpStorage(make_svc()).__http__("/x", None, {})
        finally:
            monkey.undo()

        assert captured["timeout"] == (5, 30)
        assert res == {"ok": 1}

    def test_请求异常转业务异常(self):
        def fake_post(*a, **k):
            raise requests.ConnectTimeout("timeout")

        monkey = pytest.MonkeyPatch()
        monkey.setattr(requests, "post", fake_post)
        monkey.setattr(storage_mod.time, "sleep", lambda _s: None)  # 跳过重试退避等待
        try:
            with pytest.raises(Exception) as exc_info:
                HttpStorage(make_svc()).__http__("/x", None, {})
        finally:
            monkey.undo()

        assert "服务器错误" in str(exc_info.value)
        assert "已重试" in exc_info.value.message  # J3: 重试耗尽后报错携带重试次数

    def test_连接失败重试后成功(self):
        # J3: 首次连接失败(网关重启/抖动), 第二次成功则流程正常
        calls = {"n": 0}

        class FakeResp:
            status_code = 200

            def json(self):
                return {"code": "000000", "data": {"ok": 1}}

        def fake_post(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise requests.ConnectionError("refused")
            return FakeResp()

        monkey = pytest.MonkeyPatch()
        monkey.setattr(requests, "post", fake_post)
        monkey.setattr(storage_mod.time, "sleep", lambda _s: None)
        try:
            res = HttpStorage(make_svc()).__http__("/x", None, {})
        finally:
            monkey.undo()

        assert res == {"ok": 1}
        assert calls["n"] == 2

    def test_重试耗尽后报业务异常(self):
        calls = {"n": 0}

        def fake_post(*a, **k):
            calls["n"] += 1
            raise requests.ConnectTimeout("timeout")

        monkey = pytest.MonkeyPatch()
        monkey.setattr(requests, "post", fake_post)
        monkey.setattr(storage_mod.time, "sleep", lambda _s: None)
        try:
            with pytest.raises(Exception):
                HttpStorage(make_svc()).__http__("/x", None, {})
        finally:
            monkey.undo()

        assert calls["n"] == len(HttpStorage.HTTP_RETRY_DELAYS) + 1  # 共 3 次尝试

    def test_非连接类请求异常不重试(self):
        # 业务错误不重试, 避免掩盖真实网关故障
        calls = {"n": 0}

        def fake_post(*a, **k):
            calls["n"] += 1
            raise requests.RequestException("bad")

        monkey = pytest.MonkeyPatch()
        monkey.setattr(requests, "post", fake_post)
        monkey.setattr(storage_mod.time, "sleep", lambda _s: None)
        try:
            with pytest.raises(Exception):
                HttpStorage(make_svc()).__http__("/x", None, {})
        finally:
            monkey.undo()

        assert calls["n"] == 1

    def test_非000000业务码抛异常(self):
        class FakeResp:
            status_code = 200

            def json(self):
                return {"code": "500000", "message": "boom"}

        monkey = pytest.MonkeyPatch()
        monkey.setattr(requests, "post", lambda *a, **k: FakeResp())
        try:
            with pytest.raises(Exception) as exc_info:
                HttpStorage(make_svc()).__http__("/x", None, {})
        finally:
            monkey.undo()

        assert "boom" in str(exc_info.value)


class TestMergeDicts:
    def test_高级与异常参数并入inputList(self):
        flow = {
            "title": "t1",
            "inputList": [{"key": "url", "title": "old"}],
            "advanced": [{"key": "__delay_before__", "title": "执行前延迟(秒)"}],
            "exception": [{"key": "__skip_err__", "title": "执行异常时"}],
        }
        full = {
            "title": "t2",
            "src": "astronverse.fake.a.b",
            "inputList": [{"key": "url", "title": "地址", "types": "Str", "need_parse": None, "show": True}],
            "outputList": [],
        }
        merged = merge_dicts(flow, full)
        keys = [i["key"] for i in merged["inputList"]]
        assert keys == ["url", "__delay_before__", "__skip_err__"]
        # 完整元数据按 keep_list 回填
        url_item = merged["inputList"][0]
        assert url_item["title"] == "地址"
        assert url_item["types"] == "Str"
        # title/src 从 full 合并
        assert merged["title"] == "t2"
        assert merged["src"] == "astronverse.fake.a.b"
