"""深度捕获实时树节点点选拾取(TREE_PICK)回归测试。

覆盖:
1. 无活动会话拒绝点选 / 空属性链拒绝
2. 定位成功: 写 TREE_PICK_DONE 信号供主循环消费, ack 带 located:True, 元素结构与 CONTROL_TREE pick 对齐
3. 定位失败/异常: 不写信号不结束会话, ack 带 located:False 供前端提示重试
"""

import json
import sys

# 导入即安装 win32/uiautomation 依赖桩(复用现有套件)
import test_uia_similar_locator as _similar  # noqa: F401
from astronverse.picker import PickerSign
from astronverse.picker.server.ws_server import PickerRequestHandler, PickerRequire
from astronverse.picker.svc import SyncMap
from test_ws_server import _make_mod, _run

_CHAIN = [
    {"tag_name": "WindowControl", "cls": "DocFrame", "name": "Doc1", "automation_id": "win1"},
    {"tag_name": "ButtonControl", "cls": "Btn", "name": "确定", "automation_id": "ok"},
]


class _TreePickSvc:
    """伪 svc: sign() 返回可编程信号映射(模拟活动会话)"""

    def __init__(self, active_session: bool = True):
        self._sign = SyncMap()
        if active_session:
            self._sign[PickerSign.START.value] = {"pick_mode": "DeepUIA"}

    def sign(self):
        return self._sign


def _patch_lm(monkeypatch, locate_result):
    class _FakeLM:
        def locator(self, element, **kwargs):
            if isinstance(locate_result, Exception):
                raise locate_result
            return locate_result

    monkeypatch.setitem(sys.modules, "astronverse.locator.locator", _make_mod(LocatorManager=_FakeLM))


def _req(chain) -> PickerRequire:
    return PickerRequire(pick_sign=PickerSign.TREE_PICK, data=json.dumps(chain, ensure_ascii=False))


def test_无活动会话拒绝点选():
    handler = PickerRequestHandler(_TreePickSvc(active_session=False))
    result = _run(handler._handle_tree_pick(_req(_CHAIN)))
    assert result["success"] is False
    assert "无进行中的拾取会话" in result["error"]


def test_空属性链拒绝():
    handler = PickerRequestHandler(_TreePickSvc())
    result = _run(handler._handle_tree_pick(_req([])))
    assert result["success"] is False
    assert "属性链为空" in result["error"]


def test_定位成功写入主循环消费信号(monkeypatch):
    _patch_lm(monkeypatch, object())  # locator 返回非 None 即视为定位成功
    svc = _TreePickSvc()
    handler = PickerRequestHandler(svc)
    result = _run(handler._handle_tree_pick(_req(_CHAIN)))
    assert result["success"] is True
    ack = json.loads(result["data"])
    assert ack == {"tree_pick": True, "located": True}
    # 主循环消费信号已写入, 元素结构与正常捕获对齐
    element = svc.sign()["TREE_PICK_DONE"]
    assert element["app"] == "Doc1"
    assert element["type"] == "uia"
    assert [n["tag_name"] for n in element["path"]] == ["WindowControl", "ButtonControl"]
    assert all(n["checked"] is True and n["disable_keys"] == [] for n in element["path"])


def test_定位失败不结束会话提示重试(monkeypatch):
    _patch_lm(monkeypatch, None)  # locator 返回 None 即定位失败
    svc = _TreePickSvc()
    handler = PickerRequestHandler(svc)
    result = _run(handler._handle_tree_pick(_req(_CHAIN)))
    assert result["success"] is True  # 会话继续, 前端凭 located 提示
    ack = json.loads(result["data"])
    assert ack == {"tree_pick": True, "located": False}
    assert "TREE_PICK_DONE" not in svc.sign()
    # 会话字典未被触碰
    assert svc.sign()[PickerSign.START.value] == {"pick_mode": "DeepUIA"}


def test_定位异常按失败处理不冒泡(monkeypatch):
    _patch_lm(monkeypatch, RuntimeError("COM 异常"))
    svc = _TreePickSvc()
    handler = PickerRequestHandler(svc)
    result = _run(handler._handle_tree_pick(_req(_CHAIN)))
    assert result["success"] is True
    assert json.loads(result["data"])["located"] is False
    assert "TREE_PICK_DONE" not in svc.sign()
