"""E4 AI 修复元素: 规则自愈(E2)/CV 降级(E3)未命中后, 交 LLM 分析并修正定位路径。

调用本地网关 rpa-ai-service 的 element_heal 预设 prompt。网关不可达/未配置
上游/响应无法解析时静默放弃, 不影响原定位失败链路(宁可不修, 不可修坏);
Web 域无 E2/E3 规则降级, AI 修复是其唯一的元素自愈手段。
"""

import json
import os
import re
from pathlib import Path

import requests

from astronverse.baseline.logger.logger import logger

# LLM 修复是定位失败后的最后尝试, 不宜阻塞流程太久
AI_HEAL_TIMEOUT = 15
# prompt 中单个字段序列化后的截断长度, 防止超大元素撑爆上下文
FIELD_MAX_LEN = 2000


def resolve_gateway_port() -> str:
    """网关端口解析链: 流程注入配置 → 环境变量 → gateway.json(scheduler 启动写) → 默认。

    流程上下文由 package.tpl 注入 GATEWAY_PORT; 非流程上下文(组件独立调试等)
    依赖 scheduler 落盘的 ~/.astronverse/gateway.json 兜底(见 B9)。
    """
    try:
        from astronverse.actionlib.atomic import atomicMg

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
    return "13159"


def _element_context(element: dict) -> str:
    """精简元素上下文: 剔除 img 等大字段, 超长字段截断, 控制 prompt 体积。"""
    slim = {}
    for key, value in element.items():
        if key in ("img",):
            continue
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            continue
        slim[key] = value if len(text) <= FIELD_MAX_LEN else text[:FIELD_MAX_LEN] + "...(截断)"
    return json.dumps(slim, ensure_ascii=False, default=str)


def _build_failure_report(last_error: Exception | None, report: dict | None) -> str:
    """组装定位失败报告: 定位器异常 + 已尝试过的规则自愈/CV 降级信息。"""
    lines = []
    if last_error is not None:
        lines.append(f"定位器异常: {last_error}")
    if isinstance(report, dict):
        if report.get("relaxations"):
            lines.append("已尝试规则自愈(未命中): " + " → ".join(report["relaxations"]))
        if report.get("cv_ambiguous"):
            lines.append(f"图像降级中止: 屏幕存在 {report['cv_ambiguous']} 处相似命中")
    return "\n".join(lines) if lines else "定位失败(无异常详情)"


def _extract_path(content) -> list | dict | None:
    """从 LLM 输出解析修正 path; 非法/放弃输出返回 None。

    UIA 元素 path 为层级数组(非空且每层为 dict); Web 元素 path 为含 xpath 等字段的对象。
    """
    if not isinstance(content, str) or not content.strip():
        return None
    # 容错: 模型偶尔在 JSON 外裹说明文字/代码块, 提取首个平衡的 JSON 对象
    match = re.search(r"\{[\s\S]*\}", content.strip())
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    path = data.get("path") if isinstance(data, dict) else None
    if isinstance(path, list) and path and all(isinstance(node, dict) for node in path):
        return path
    if isinstance(path, dict) and path:
        return path
    return None


def ai_heal(element: dict, locator_type: str, last_error: Exception | None = None, report: dict | None = None):
    """LLM 修正元素定位路径。

    Returns:
        {"element": 修正后的元素副本, "repair_hint": 提示文案}; 放弃时 None。
        本函数不重新验证定位, 由调用方(LocatorManager)用修正元素重试并决定去留。
    """
    if os.environ.get("ASTRON_AI_HEAL") == "0":
        # 全局关闭开关(紧急止血用, 默认开启)
        return None

    url = "http://127.0.0.1:{}/api/rpa-ai-service/v1/chat/prompt".format(resolve_gateway_port())
    payload = {
        "prompt_type": "element_heal",
        "params": {
            "type": locator_type,
            "element": _element_context(element),
            "report": _build_failure_report(last_error, report),
        },
        "stream": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=AI_HEAL_TIMEOUT)
        response.raise_for_status()
        body = response.json()
    except Exception as e:
        logger.info(f"AI 修复元素放弃(网关不可达/超时/未配置): {e}")
        return None

    path = _extract_path(body.get("data") if isinstance(body, dict) else None)
    if path is None:
        logger.info("AI 修复元素放弃(LLM 未给出有效修正路径)")
        return None

    fixed = dict(element)
    fixed["path"] = path
    logger.info(f"AI 修复元素获得修正路径, 交回定位器验证(type={locator_type})")
    return {
        "element": fixed,
        "repair_hint": "元素已通过 AI 修复定位路径并验证成功; 建议重新拾取更新元素属性",
    }
