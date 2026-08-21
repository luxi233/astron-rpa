"""Browser.send_browser_extension 单测: 重试/错误映射/透传逻辑 (utils/browser.py)"""

from unittest import mock

import pytest

from astronverse.picker.utils import browser as browser_mod
from astronverse.picker.utils.browser import Browser, BrowserControlFinder


def _resp(json_data=None, status=200):
    """构造伪 requests.Response"""
    resp = mock.MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


class TestSendBrowserExtension:
    """通过 monkeypatch requests.post 驱动全部分支, 不发起真实网络请求"""

    def test_成功返回data(self, monkeypatch):
        resp = _resp({"code": "0000", "data": {"code": "0000", "data": {"ok": 1}}})
        monkeypatch.setattr(browser_mod.requests, "post", mock.MagicMock(return_value=resp))
        assert Browser.send_browser_extension("chrome", {}, "clickElement", 8003) == {"ok": 1}

    def test_res_data为空返回None(self, monkeypatch):
        resp = _resp({"code": "0000", "data": None})
        monkeypatch.setattr(browser_mod.requests, "post", mock.MagicMock(return_value=resp))
        assert Browser.send_browser_extension("chrome", {}, "runJS", 8003) is None

    def test_非200抛连接器异常(self, monkeypatch):
        monkeypatch.setattr(browser_mod.requests, "post", mock.MagicMock(return_value=_resp(status=500)))
        with pytest.raises(Exception, match="通信通道出错"):
            Browser.send_browser_extension("chrome", {}, "runJS", 8003)

    def test_1001重试3次后抛插件未装异常(self, monkeypatch):
        resp = _resp({"code": "1001"})
        post = mock.MagicMock(return_value=resp)
        monkeypatch.setattr(browser_mod.requests, "post", post)
        monkeypatch.setattr(browser_mod.time, "sleep", mock.MagicMock())
        with pytest.raises(Exception, match="请检查插件是否安装"):
            Browser.send_browser_extension("chrome", {}, "runJS", 8003)
        assert post.call_count == 3
        assert browser_mod.time.sleep.call_count == 2  # 前两次重试间隔 sleep

    def test_1001重试后成功(self, monkeypatch):
        responses = [_resp({"code": "1001"}), _resp({"code": "0000", "data": {"code": "0000", "data": "ok"}})]
        post = mock.MagicMock(side_effect=responses)
        monkeypatch.setattr(browser_mod.requests, "post", post)
        monkeypatch.setattr(browser_mod.time, "sleep", mock.MagicMock())
        assert Browser.send_browser_extension("chrome", {}, "runJS", 8003) == "ok"
        assert post.call_count == 2

    def test_外层code非0000抛异常带msg(self, monkeypatch):
        resp = _resp({"code": "2000", "data": {"msg": "tab丢失"}})
        monkeypatch.setattr(browser_mod.requests, "post", mock.MagicMock(return_value=resp))
        with pytest.raises(Exception, match=r"\[chrome\] tab丢失"):
            Browser.send_browser_extension("chrome", {}, "runJS", 8003)

    @pytest.mark.parametrize("data_code", ["5001", "5002", "5003", "5004"])
    def test_插件错误码透传具体原因(self, monkeypatch, data_code):
        """回归: 5002/5003 优先透传插件具体错误而非兜底文案"""
        resp = _resp({"code": "0000", "data": {"code": data_code, "msg": "该元素不是相似元素", "data": ""}})
        monkeypatch.setattr(browser_mod.requests, "post", mock.MagicMock(return_value=resp))
        with pytest.raises(Exception, match="该元素不是相似元素"):
            Browser.send_browser_extension("chrome", {}, "similarElement", 8003)

    def test_插件错误msg为空时用兜底文案(self, monkeypatch):
        resp = _resp({"code": "0000", "data": {"code": "5002", "msg": "", "data": ""}})
        monkeypatch.setattr(browser_mod.requests, "post", mock.MagicMock(return_value=resp))
        with pytest.raises(Exception, match="网页元素查找失败"):
            Browser.send_browser_extension("chrome", {}, "similarElement", 8003)

    def test_getElement豁免插件错误码(self, monkeypatch):
        """拾取阶段(getElement)的 5002 不抛异常, 空结果归一化为 None 由上层判定未命中"""
        resp = _resp({"code": "0000", "data": {"code": "5002", "msg": "没找到", "data": ""}})
        monkeypatch.setattr(browser_mod.requests, "post", mock.MagicMock(return_value=resp))
        assert Browser.send_browser_extension("chrome", {"x": 1, "y": 2}, "getElement", 8003) is None

    def test_请求体结构(self, monkeypatch):
        resp = _resp({"code": "0000", "data": {"code": "0000", "data": "x"}})
        post = mock.MagicMock(return_value=resp)
        monkeypatch.setattr(browser_mod.requests, "post", post)
        Browser.send_browser_extension("edge", {"a": 1}, "getTitle", 9000, data_path="/tmp/x", timeout=5)
        req = post.call_args[1]["json"] if post.call_args[1] and "json" in post.call_args[1] else post.call_args.kwargs["json"]
        assert req == {"browser_type": "edge", "data": {"a": 1}, "key": "getTitle", "data_path": "/tmp/x"}
        assert "127.0.0.1:9000" in post.call_args.kwargs["url"] if "url" in post.call_args.kwargs else True


class TestBrowserControlFinderMaps:
    def test_进程映射与窗口类映射键一致(self):
        assert set(BrowserControlFinder.PROCESS_MAP) == set(BrowserControlFinder.CLASS_NAME_MAP)

    def test_映射覆盖chromium系(self):
        for key in ["chrome", "edge", "chromium", "360se", "360chromex", "360chrome", "firefox", "iexplore"]:
            assert key in BrowserControlFinder.PROCESS_MAP, f"{key} 缺少进程映射"
            assert BrowserControlFinder.PROCESS_MAP[key].endswith(".exe")
