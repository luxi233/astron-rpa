"""Strategy.run 参数分发回归测试。

回归缺陷: UIA/MSAA 策略函数签名为 (strategy_svc) 单参数, 而 Strategy.run 曾对
非 WEB 域统一传 3 个参数, 导致:
    TypeError: uia_default_strategy() takes 1 positional argument but 3 were given

各策略函数真实签名(须与本文件断言保持一致):
- uia_default_strategy(strategy_svc)                          1 参
- msaa_default_strategy(strategy_svc)                         1 参
- web_default_strategy(service, strategy_svc, cache=None)     2 参
- auto_default_strategy(service, strategy, strategy_svc)      3 参
- auto_default_strategy_desk/service 同上                     3 参
"""

import pytest

from astronverse.picker import PickerDomain
from astronverse.picker.strategy import (
    auto_strategy,
    auto_strategy_desk,
    auto_strategy_web,
    msaa_strategy,
    uia_strategy,
    web_strategy,
)
from astronverse.picker.strategy.manager import Strategy
from astronverse.picker.strategy.types import StrategySvc


def _svc(domain):
    return StrategySvc(domain=domain, data={})


def _mk(captured, result="ELE"):
    def _fn(*args):
        captured["args"] = args
        return result

    return _fn


class TestRunDispatchArgCount:
    def test_UIA域只传strategy_svc(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(uia_strategy, "uia_default_strategy", _mk(captured))
        svc = _svc(PickerDomain.UIA)
        result = Strategy(service_context="SVC").run(svc)
        assert result == "ELE"
        assert captured["args"] == (svc,)

    def test_MSAA域只传strategy_svc(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(msaa_strategy, "msaa_default_strategy", _mk(captured))
        svc = _svc(PickerDomain.MSAA)
        result = Strategy(service_context="SVC").run(svc)
        assert result == "ELE"
        assert captured["args"] == (svc,)

    def test_WEB域传service与strategy_svc(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(web_strategy, "web_default_strategy", _mk(captured))
        svc = _svc(PickerDomain.WEB)
        result = Strategy(service_context="SVC").run(svc)
        assert result == "ELE"
        assert captured["args"] == ("SVC", svc)

    def test_AUTO域传三个参数(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(auto_strategy, "auto_default_strategy", _mk(captured))
        svc = _svc(PickerDomain.AUTO)
        strat = Strategy(service_context="SVC")
        result = strat.run(svc)
        assert result == "ELE"
        assert captured["args"] == ("SVC", strat, svc)

    def test_AUTO_DESK域传三个参数(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(auto_strategy_desk, "auto_default_strategy_desk", _mk(captured))
        svc = _svc(PickerDomain.AUTO_DESK)
        strat = Strategy(service_context="SVC")
        assert strat.run(svc) == "ELE"
        assert captured["args"] == ("SVC", strat, svc)

    def test_AUTO_WEB域传三个参数(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(auto_strategy_web, "auto_default_strategy_web", _mk(captured))
        svc = _svc(PickerDomain.AUTO_WEB)
        strat = Strategy(service_context="SVC")
        assert strat.run(svc) == "ELE"
        assert captured["args"] == ("SVC", strat, svc)


class TestRunDispatchBehavior:
    def test_策略返回None时run返回None(self, monkeypatch):
        monkeypatch.setattr(uia_strategy, "uia_default_strategy", _mk({}, result=None))
        assert Strategy(service_context="SVC").run(_svc(PickerDomain.UIA)) is None

    def test_未注册域返回None(self):
        # SAP/JAB 等无对应策略函数, 不应抛异常
        assert Strategy(service_context="SVC").run(_svc(PickerDomain.SAP)) is None

    def test_策略异常被向上抛出(self, monkeypatch):
        def _boom(*args):
            raise RuntimeError("pick failed")

        monkeypatch.setattr(uia_strategy, "uia_default_strategy", _boom)
        with pytest.raises(RuntimeError, match="pick failed"):
            Strategy(service_context="SVC").run(_svc(PickerDomain.UIA))


class TestRealSignatureContract:
    """校验真实策略函数签名与分发约定一致, 防止签名漂移再次引入参数不匹配"""

    def test_uia与msaa为单参(self):
        import inspect

        assert len(inspect.signature(uia_strategy.uia_default_strategy).parameters) == 1
        assert len(inspect.signature(msaa_strategy.msaa_default_strategy).parameters) == 1

    def test_web至少两参(self):
        import inspect

        params = inspect.signature(web_strategy.web_default_strategy).parameters
        assert len(params) >= 2

    def test_auto系为三参(self):
        import inspect

        for fn in (
            auto_strategy.auto_default_strategy,
            auto_strategy_desk.auto_default_strategy_desk,
            auto_strategy_web.auto_default_strategy_web,
        ):
            assert len(inspect.signature(fn).parameters) == 3
