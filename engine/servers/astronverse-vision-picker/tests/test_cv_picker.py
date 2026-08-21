"""L3: cv_picker ImageDetector 纯算法测试(IoU/NMS/图像预处理, 无平台依赖)。"""

import numpy as np
import pytest
from astronverse.vision_picker.core.cv_picker import ImageDetector
from PIL import Image


# ---------------- compute_iou ----------------


class TestComputeIou:
    def test完全重合为1(self):
        assert ImageDetector.compute_iou([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(1.0)

    def test不相交为0(self):
        assert ImageDetector.compute_iou([0, 0, 10, 10], [20, 20, 10, 10]) == pytest.approx(0.0)

    def test半重叠(self):
        # 两个 10x10 框水平错开 5px: 交集 5x10=50, 并集 200-50=150
        assert ImageDetector.compute_iou([0, 0, 10, 10], [5, 0, 10, 10]) == pytest.approx(50 / 150)


# ---------------- apply_nms ----------------


class TestApplyNms:
    def test空输入返回空(self):
        assert ImageDetector.apply_nms([]) == []

    def test不相交框全部保留(self):
        boxes = [[0, 0, 10, 10], [50, 50, 10, 10], [100, 0, 20, 20]]
        assert len(ImageDetector.apply_nms(boxes)) == 3

    def test高重叠框被抑制(self):
        boxes = [[0, 0, 20, 20], [2, 2, 20, 20]]  # IoU 远高于 0.3
        assert len(ImageDetector.apply_nms(boxes)) == 1

    def test包含但IoU中等的小框不被抑制(self):
        # 实际行为: 仅当 IoU>=阈值 或 IoU<0.0003(退化重叠)才抑制;
        # 包含关系小框 IoU=100/1600=0.0625 落在保留区间
        boxes = [[0, 0, 40, 40], [5, 5, 10, 10]]
        kept = ImageDetector.apply_nms(boxes)
        assert len(kept) == 2

    def test退化重叠框被抑制(self):
        # IoU 极小(<0.0003)的退化重叠也会被抑制(源码既定行为)
        boxes = [[0, 0, 1000, 1000], [999, 999, 1000, 1000]]  # 交集 1x1, IoU≈1e-6
        kept = ImageDetector.apply_nms(boxes)
        assert len(kept) == 1


# ---------------- get_image / 预处理算子 ----------------


class TestImagePipeline:
    def _make_pil_image(self):
        # 白底黑框的简单图(有明确边缘供 Canny/Sobel 检测)
        arr = np.full((60, 80, 3), 255, dtype=np.uint8)
        arr[20:40, 30:50] = 0
        return Image.fromarray(arr)

    def test_get_image返回BGR原图与灰度图(self):
        image, gray = ImageDetector.get_image(self._make_pil_image())
        assert image.shape == (60, 80, 3)
        assert gray.shape == (60, 80)

    def test_get_image无图抛错(self):
        with pytest.raises(ValueError):
            ImageDetector.get_image(None)

    def test构造函数初始化双图(self):
        detector = ImageDetector(self._make_pil_image())
        assert detector.original_img is not None
        assert detector.gray_img is not None

    def test_canny边缘输出二值(self):
        detector = ImageDetector(self._make_pil_image())
        edges = detector.compute_canny_edge(detector.gray_img)
        assert set(np.unique(edges)) <= {0, 255}
        assert (edges == 255).sum() > 0  # 黑框边缘应被检出

    def test_sobel梯度与阈值管线可运行(self):
        detector = ImageDetector(self._make_pil_image())
        grad = detector.compute_sobel_gradient(detector.gray_img)
        thresh = detector.apply_threshold_and_blur(grad)
        assert set(np.unique(thresh)) <= {0, 255}


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
