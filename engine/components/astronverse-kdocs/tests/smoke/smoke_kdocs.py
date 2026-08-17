"""WPS 组件冒烟测试 (v1.2.1 wps_client 强类型修复后建立)

覆盖:
1. WpsHookClient 构造校验 (hook_url/token 为空抛错)
2. send_request 对 6 种 webhook 响应结构的解析 (mock requests.post)
3. _client 兜底: 字符串/None/int 传入抛带指引的 WpsHookError (防静默失败)
4. __validate__ 类型注册 (meta 强类型推断入口)
5. meta.json: 26 原子 wps_client 参数/输出 types 全部为 WpsHookClient, 无 Any 残留
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

COMP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COMP / "src"))

from astronverse.actionlib.error import ParamException
from astronverse.kdocs.core_kdocs import WpsHookClient, WpsHookError
from astronverse.kdocs.kdocs import Kdocs, _client

PASSED = 0


def ok(name):
    global PASSED
    PASSED += 1
    print(f"  ✓ {name}")


# ---- 1. 构造校验 ----
for bad_args in [(None, "t"), ("http://w", "")]:
    try:
        WpsHookClient(*bad_args)
        raise AssertionError(f"{bad_args} 应抛错")
    except WpsHookError:
        pass
ok("构造校验: hook_url/token 为空抛 WpsHookError")

# ---- 2. webhook 响应解析 ----
client = WpsHookClient("http://fake/w", "tok", timeout=5)
CASES = {
    "data.result 数组 -> 列表": ({"code": 0, "data": {"result": ["Sheet1", "Sheet2"]}}, ["Sheet1", "Sheet2"]),
    "data 直接数组 -> 列表": ({"code": 0, "data": ["A"]}, ["A"]),
    "data.result null -> None": ({"code": 0, "data": {"result": None}}, None),
    "error 字段 -> 抛错": ({"code": 0, "error": "boom"}, WpsHookError),
    "status 非 finished -> 抛错": ({"code": 0, "status": "running"}, WpsHookError),
    "HTTP 500 -> 抛错": ("HTTP_ERR", WpsHookError),
}
for name, (payload, expect) in CASES.items():
    if payload == "HTTP_ERR":
        resp = MagicMock()
        resp.status_code = 500
        resp.text = "server error"
    else:
        resp = MagicMock()
        resp.status_code = 200
        resp.text = json.dumps(payload)
        resp.json.return_value = payload
    with patch("astronverse.kdocs.core_kdocs.requests.post", return_value=resp):
        try:
            out = client.list_sheets()
            assert out == expect, f"{name}: {out!r} != {expect!r}"
        except WpsHookError:
            assert expect is WpsHookError, f"{name}: 不应抛错"
ok("webhook 解析: 6 种响应结构(正常/异常)行为正确")

# ---- 3. _client 兜底 (本次修复核心) ----
for bad in ("连接A", None, 123):
    try:
        _client(bad)
        raise AssertionError(f"{bad!r} 应抛错")
    except WpsHookError as e:
        assert "变量选择器" in e.detail, f"错误指引缺失: {e.detail}"
ok("_client 兜底: str/None/int 抛带修复指引的明确错误")

try:
    Kdocs.list_sheets("连接A")
    raise AssertionError("原子层应抛错")
except Exception as e:  # kdocs.py 统一转引擎 BaseException(code, message)
    # 关键回归: 必须是 Exception 子类(可被执行器捕获上报), 且带 code/message
    assert isinstance(e, Exception), "引擎错误必须是 Exception 子类, 否则执行器静默退出"
    assert e.code.message.startswith("WPS在线表格操作失败"), e.code.message
    assert "变量选择器" in e.message, f"错误指引缺失: {e.message}"
ok("原子层: 字符串 wps_client 显式报错且可被 except Exception 捕获(不再静默退出)")

c = WpsHookClient("http://w", "t")
assert _client(c) is c
assert isinstance(WpsHookClient.__validate__("wps_client", c), WpsHookClient)
try:
    WpsHookClient.__validate__("wps_client", "x")
    raise AssertionError("__validate__ 失配应抛错")
except ParamException:
    pass
ok("__validate__: 对象通过/字符串抛 ParamException(对齐 actionlib 约定)")

# ---- 4. meta.json 一致性 ----
meta = json.load(open(COMP / "meta.json", encoding="utf-8"))
wps_atoms = {k: a for k, a in meta.items() if k.startswith("WPS.")}
assert len(wps_atoms) >= 26, f"WPS 原子数 {len(wps_atoms)} < 26"
bad_any = [
    k
    for k, a in wps_atoms.items()
    for i in a.get("inputList", [])
    if i.get("key") == "wps_client" and i.get("types") != "WpsHookClient"
]
assert not bad_any, f"wps_client 输入仍是弱类型: {bad_any}"
cc_out = wps_atoms["WPS.create_client"]["outputList"][0]
assert cc_out["types"] == "WpsHookClient", f"create_client 输出 types={cc_out['types']}"
ok(f"meta.json: {len(wps_atoms)} 原子 wps_client 全部强类型 WpsHookClient")

print(f"\n全部通过: {PASSED}/6 组")
