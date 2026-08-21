"""E3 元素+图像融合降级。

元素定位失败(含自愈失败)且元素携带拾取时的截图(img.self base64)时,
对桌面截图做 CV 模板匹配获取元素区域, 返回基于坐标的定位器, 保障流程连续性。
多尺度匹配容忍界面缩放/DPI 差异; 多候选命中视为歧义, 告警并放弃降级防止误点。
依赖(opencv/pyautogui)缺失时优雅跳过, 不影响原报错语义。
"""

import base64
from io import BytesIO
from typing import List, Optional

from astronverse.baseline.logger.logger import logger
from astronverse.locator import ILocator, Rect

# CV 降级匹配阈值(与 vision-picker 唯一匹配阈值对齐)
CV_FALLBACK_SIMILARITY = 0.95
# 多尺度匹配的缩放序列(1.0 为原尺寸, 优先尝试; 含常见 DPI 缩放 125%/110%/90% 及其逆)
CV_FALLBACK_SCALES = (1.0, 0.9, 1.1, 0.8, 1.25, 5 / 6, 1.5)
# 候选重合度(IoU)超过该值视为同一命中, 用于跨尺度去重
CV_FALLBACK_NMS_IOU = 0.3


class CVFallbackLocator(ILocator):
    """基于 CV 模板匹配区域的坐标定位器(无控件句柄, 仅支持坐标类操作)"""

    def __init__(self, rect: Rect):
        self.__rect = rect

    def rect(self) -> Optional[Rect]:
        return self.__rect

    def control(self):
        return None


def _decode_template(img_data: dict):
    """解析拾取时保存的元素截图(base64), 失败返回 None"""
    b64 = img_data.get("self")
    if not b64:
        return None
    try:
        from PIL import Image

        return Image.open(BytesIO(base64.b64decode(b64))).convert("RGB")
    except Exception as e:
        logger.warning(f"CV 降级跳过: 元素截图解析失败: {e}")
        return None


def _match_single_scale(gray, tpl_gray, similarity: float):
    """单尺度全图匹配, 收集所有置信度达标的候选(供歧义判断)"""
    import cv2
    import numpy as np

    if gray.shape[0] < tpl_gray.shape[0] or gray.shape[1] < tpl_gray.shape[1]:
        return []
    result = cv2.matchTemplate(gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
    h, w = tpl_gray.shape[:2]
    candidates = []
    mask = result >= similarity
    for y, x in zip(*np.where(mask)):
        candidates.append((Rect(int(x), int(y), int(x) + w, int(y) + h), float(result[y, x])))
    # 相邻像素得分相近会产生大量重复候选, 按 IoU 聚合
    return _nms(candidates)


def _iou(r1: Rect, r2: Rect) -> float:
    inter_w = max(0, min(r1.right, r2.right) - max(r1.left, r2.left))
    inter_h = max(0, min(r1.bottom, r2.bottom) - max(r1.top, r2.top))
    inter = inter_w * inter_h
    if inter <= 0:
        return 0.0
    area1 = (r1.right - r1.left) * (r1.bottom - r1.top)
    area2 = (r2.right - r2.left) * (r2.bottom - r2.top)
    return inter / (area1 + area2 - inter)


def _nms(candidates: List[tuple]) -> List[tuple]:
    """按置信度降序保留非重合候选"""
    candidates = sorted(candidates, key=lambda c: -c[1])
    kept = []
    for rect, score in candidates:
        if all(_iou(rect, k) < CV_FALLBACK_NMS_IOU for k, _ in kept):
            kept.append((rect, score))
    return kept


def match_template_candidates(
    screen, template, similarity: float = CV_FALLBACK_SIMILARITY, scales=CV_FALLBACK_SCALES
) -> List[tuple]:
    """多尺度模板匹配, 返回全部去重后的候选 [(Rect, 置信度, 缩放)](按置信度降序)"""
    import cv2
    import numpy as np
    from PIL import Image

    gray = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2GRAY)
    tpl = np.array(template)
    candidates: List[tuple] = []
    for scale in scales:
        if scale == 1.0:
            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_RGB2GRAY)
        else:
            # 最近邻缩放: UI 截图为锐利像素块, 双线性插值会使边缘模糊, 降低匹配得分
            resized = np.array(
                Image.fromarray(tpl).resize(
                    (max(1, round(tpl.shape[1] * scale)), max(1, round(tpl.shape[0] * scale))), Image.NEAREST
                )
            )
            tpl_gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
        for rect, score in _match_single_scale(gray, tpl_gray, similarity):
            candidates.append((rect, score, scale))
    # 跨尺度去重: 同一位置不同缩放的命中只保留置信度最高者
    dedup: List[tuple] = []
    for rect, score, scale in sorted(candidates, key=lambda c: -c[1]):
        if all(_iou(rect, k) < CV_FALLBACK_NMS_IOU for k, _, _ in dedup):
            dedup.append((rect, score, scale))
    return dedup


def match_template(screen, template, similarity: float = CV_FALLBACK_SIMILARITY):
    """在屏幕截图中模板匹配。

    Returns:
        命中返回 (Rect, 置信度), 未命中返回 None
    """
    candidates = match_template_candidates(screen, template, similarity, scales=(1.0,))
    if not candidates:
        return None
    rect, score, _ = candidates[0]
    return rect, score


def cv_fallback(
    ele: dict, similarity: float = CV_FALLBACK_SIMILARITY, report: Optional[dict] = None
) -> Optional[CVFallbackLocator]:
    """元素+图像融合降级入口。

    Args:
        ele: 元素信息(需含 img.self 拾取截图)
        similarity: 匹配置信度阈值
        report: 传入时回写降级状态(如歧义候选数)供上层展示

    Returns:
        命中返回 CVFallbackLocator, 否则 None
    """
    template = _decode_template(ele.get("img") or {})
    if template is None:
        return None
    try:
        import cv2  # noqa: F401
        import pyautogui
    except ImportError as e:
        logger.warning(f"CV 降级跳过: 依赖缺失: {e}")
        return None
    try:
        screen = pyautogui.screenshot()
    except Exception as e:
        logger.warning(f"CV 降级失败: 截图异常: {e}")
        return None
    candidates = match_template_candidates(screen, template, similarity)
    if not candidates:
        logger.info("CV 降级未命中: 当前屏幕未找到元素截图")
        return None
    if len(candidates) > 1:
        # 多处高置信命中无法判定真实位置, 放弃降级避免误点; 候选数回传供上层提示
        logger.warning(f"CV 降级中止: 屏幕存在 {len(candidates)} 处相似命中(歧义), 请检查元素截图是否具备区分度")
        if isinstance(report, dict):
            report["cv_ambiguous"] = len(candidates)
            # I1: 候选位置+置信度一并回传, 供上层交互式消歧(用户点选其一)
            report["cv_candidates"] = [
                {"rect": [r.left, r.top, r.right, r.bottom], "score": round(s, 3)} for r, s, _ in candidates
            ]
        return None
    rect, score, scale = candidates[0]
    logger.info(
        f"CV 降级命中: 置信度 {score:.3f}, 缩放 {scale}, 区域 ({rect.left},{rect.top},{rect.right},{rect.bottom})"
    )
    return CVFallbackLocator(rect)


def cv_disambiguate(rect: list) -> CVFallbackLocator:
    """I1: 用户在歧义候选中选定其一后, 按候选区域构造坐标定位器。

    一次性人工决策, 不重新截图匹配, 也不写入自愈缓存(选择结果不可泛化)。
    """
    left, top, right, bottom = (int(v) for v in rect)
    logger.info(f"CV 消歧: 采用用户选定候选区域 ({left},{top},{right},{bottom})")
    return CVFallbackLocator(Rect(left, top, right, bottom))
