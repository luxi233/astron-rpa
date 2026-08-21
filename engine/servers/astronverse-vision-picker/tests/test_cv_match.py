"""L3: cv_match 模板匹配核心算法测试(合成图像, 无平台依赖)。

覆盖:
1. _limit_roi_bounds 边界裁剪纯逻辑
2. check_if_multiple_elements 唯一性判定(单命中/多命中/无命中)
3. process_image 全局匹配(命中坐标/阈值不达标/比例缩放)
4. process_image 锚点 ROI 匹配路径
"""

import numpy as np
import pytest
from astronverse.vision_picker.core.cv_match import AnchorMatch

PATCH_SIZE = 20


def _make_canvas(width=200, height=150, value=128) -> np.ndarray:
    """均匀灰底画布(RGB, uint8)"""
    return np.full((height, width, 3), value, dtype=np.uint8)


def _make_patch(seed=1) -> np.ndarray:
    """确定性纹理块(避免纯色块在 CCOEFF_NORMED 下方差为零)"""
    ys, xs = np.mgrid[0:PATCH_SIZE, 0:PATCH_SIZE]
    base = ((ys * 7 + xs * 3 + seed * 11) % 251).astype(np.uint8)
    g = ((base.astype(int) + 85) % 256).astype(np.uint8)
    b = ((base.astype(int) + 170) % 256).astype(np.uint8)
    return np.dstack([base, g, b]).astype(np.uint8)


def _embed(canvas: np.ndarray, patch: np.ndarray, x: int, y: int):
    h, w = patch.shape[:2]
    canvas[y : y + h, x : x + w] = patch


# ---------------- _limit_roi_bounds ----------------


class TestLimitRoiBounds:
    def test越界坐标被裁剪到图像内(self):
        am = AnchorMatch()
        tl, br = am._limit_roi_bounds((-10, -20), (500, 400), (100, 200, 3))
        assert tl == (0, 0)
        assert br == (199, 99)

    def test退化区域保证右下角大于左上角(self):
        am = AnchorMatch()
        tl, br = am._limit_roi_bounds((50, 50), (50, 50), (100, 200, 3))
        assert br[0] == tl[0] + 1 and br[1] == tl[1] + 1

    def test合法区域原样保留(self):
        am = AnchorMatch()
        tl, br = am._limit_roi_bounds((10, 20), (30, 40), (100, 200, 3))
        assert tl == (10, 20) and br == (30, 40)


# ---------------- check_if_multiple_elements ----------------


class TestCheckIfMultipleElements:
    def test单命中返回True(self):
        canvas = _make_canvas()
        _embed(canvas, _make_patch(), 60, 40)
        assert AnchorMatch.check_if_multiple_elements(canvas, _make_patch(), 0.95) is True

    def test多命中返回False(self):
        canvas = _make_canvas(width=300)
        patch = _make_patch()
        _embed(canvas, patch, 30, 40)
        _embed(canvas, patch, 200, 90)
        assert AnchorMatch.check_if_multiple_elements(canvas, patch, 0.95) is False

    def test无命中返回False(self):
        canvas = _make_canvas()
        assert AnchorMatch.check_if_multiple_elements(canvas, _make_patch(seed=9), 0.95) is False


# ---------------- process_image 全局匹配 ----------------


class TestProcessImageGlobal:
    def test命中返回精确左上角与尺寸(self):
        canvas = _make_canvas(width=240, height=180)
        patch = _make_patch()
        _embed(canvas, patch, 100, 70)
        am = AnchorMatch()
        _, match_box = am.process_image(canvas, patch, ratio="1,1", match_similarity=0.95)
        assert match_box is not None
        x, y, w, h = match_box
        assert (abs(x - 100), abs(y - 70)) <= (1, 1)
        assert (w, h) == (PATCH_SIZE, PATCH_SIZE)

    def test低相似度阈值不达标返回None(self):
        canvas = _make_canvas()
        am = AnchorMatch()
        # 反色块与画布中不存在相似目标, 阈值拉满应返回 None
        _, match_box = am.process_image(canvas, 255 - _make_patch(seed=5), ratio="1,1", match_similarity=0.99)
        assert match_box is None

    def test比例缩放后仍能命中(self):
        # ratio=2,2: 模板按 2 倍缩放后匹配 2 倍尺寸的画布目标
        canvas = _make_canvas(width=300, height=240)
        import cv2

        big_patch = cv2.resize(_make_patch(), (PATCH_SIZE * 2, PATCH_SIZE * 2), interpolation=cv2.INTER_CUBIC)
        _embed(canvas, big_patch, 80, 60)
        am = AnchorMatch()
        _, match_box = am.process_image(canvas, _make_patch(), ratio="2,2", match_similarity=0.9)
        assert match_box is not None
        x, y, w, h = match_box
        assert abs(x - 80) <= 2 and abs(y - 60) <= 2
        assert (w, h) == (PATCH_SIZE * 2, PATCH_SIZE * 2)


# ---------------- process_image 锚点 ROI 匹配 ----------------


class TestProcessImageAnchor:
    def test锚点相对位移定位目标(self):
        canvas = _make_canvas(width=300, height=220)
        anchor_patch = _make_patch(seed=3)
        target_patch = _make_patch(seed=4)
        _embed(canvas, anchor_patch, 40, 50)  # 锚点左上角 (40,50), 中心 (50,60)
        _embed(canvas, target_patch, 100, 90)  # 目标左上角 (100,90), 中心 (110,100)
        am = AnchorMatch()
        _, match_box = am.process_image(
            canvas,
            target_patch,
            anchor=anchor_patch,
            center_coords_aim="110,100",
            center_coords_anchor="50,60",
            ratio="1,1",
            match_similarity=0.9,
            line_width_match=2,
        )
        assert match_box is not None
        x, y, w, h = match_box
        assert abs(x - 100) <= 1 and abs(y - 90) <= 1
        assert (w, h) == (PATCH_SIZE, PATCH_SIZE)

    def test锚点缺失时全局兜底仍命中(self):
        # 画布中无锚点但有目标: ROI 路径失败后走全局匹配兜底
        canvas = _make_canvas(width=300, height=220)
        target_patch = _make_patch(seed=4)
        _embed(canvas, target_patch, 150, 120)
        am = AnchorMatch()
        _, match_box = am.process_image(
            canvas,
            target_patch,
            anchor=_make_patch(seed=8),
            center_coords_aim="160,130",
            center_coords_anchor="50,60",
            ratio="1,1",
            match_similarity=0.9,
            line_width_match=2,
        )
        assert match_box is not None
        x, y, _, _ = match_box
        assert abs(x - 150) <= 1 and abs(y - 120) <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
