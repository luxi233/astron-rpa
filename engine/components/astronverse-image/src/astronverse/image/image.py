"""图片处理原子能力：信息/缩放/切割/水印/相似度/证件照等（Pillow）。"""

import os
import string
import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.image import (
    DirectionType,
    IdPhotoBgColorType,
    ImageFormatType,
    WatermarkPositionType,
)
from astronverse.image.error import (
    FILE_NOT_FOUND_ERROR_FORMAT,
    IMAGE_PROCESS_ERROR_FORMAT,
    INVALID_IMAGE_ERROR_FORMAT,
    INVALID_PARAMS_ERROR_FORMAT,
    SAVE_FAILED_ERROR_FORMAT,
    BaseException,
)

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _abs(path: str) -> str:
    return os.path.abspath(path)


def _check_file(path: str):
    if not path or not os.path.isfile(path):
        raise BaseException(FILE_NOT_FOUND_ERROR_FORMAT, str(path))


def _open_image(path: str):
    """校验并打开图片，失败抛 INVALID_IMAGE。"""
    from PIL import Image

    _check_file(path)
    try:
        img = Image.open(path)
        img.load()
        return img
    except BaseException:
        raise
    except Exception as e:
        raise BaseException(INVALID_IMAGE_ERROR_FORMAT, f"{path}: {e}")


def _iter_images(src) -> list:
    """输入归一：单文件 | 文件列表 | 文件夹（一级遍历）→ 图片路径列表。"""
    if isinstance(src, (list, tuple)):
        if not src:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, "图片列表为空")
        for p in src:
            _check_file(str(p))
        return [str(p) for p in src]
    src = str(src)
    if os.path.isdir(src):
        files = sorted(
            os.path.join(src, f)
            for f in os.listdir(src)
            if os.path.isfile(os.path.join(src, f)) and os.path.splitext(f)[1].lower() in _IMAGE_EXTS
        )
        if not files:
            raise BaseException(FILE_NOT_FOUND_ERROR_FORMAT, f"{src} 下无图片文件")
        return files
    _check_file(src)
    return [src]


def _out_path(src: str, suffix: str, ext: str = "", out_dir: str = "") -> str:
    """生成输出路径：默认与源文件同目录，文件名加后缀；ext 形如 '.png'。"""
    d = out_dir or os.path.dirname(_abs(src))
    os.makedirs(d, exist_ok=True)
    name = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(d, f"{name}_{suffix}{ext or os.path.splitext(src)[1]}")


def _save_image(img, path: str, fmt: str = "", quality: int = 0, dpi=None) -> str:
    """统一保存：JPEG/BMP 不支持 alpha → 转 RGB；父目录自动创建。"""
    try:
        parent = os.path.dirname(_abs(path))
        os.makedirs(parent, exist_ok=True)
        fmt = (fmt or os.path.splitext(path)[1][1:] or "png").lower()
        if fmt in ("jpg", "jpeg", "bmp") and img.mode not in ("RGB", "L", "1", "P"):
            img = img.convert("RGB")
        kwargs = {}
        if quality:
            kwargs["quality"] = int(quality)
        if dpi:
            kwargs["dpi"] = (int(dpi), int(dpi))
        img.save(path, format=None if os.path.splitext(path)[1] else fmt, **kwargs)
        return path
    except BaseException:
        raise
    except Exception as e:
        raise BaseException(SAVE_FAILED_ERROR_FORMAT, str(e))


def _split(img, src: str, bw: int, bh: int, out_dir: str) -> list:
    w, h = img.size
    cols = (w + bw - 1) // bw
    paths = []
    try:
        for r in range(rows := (h + bh - 1) // bh):
            for c in range(cols):
                box = (c * bw, r * bh, min((c + 1) * bw, w), min((r + 1) * bh, h))
                if box[2] - box[0] < 1 or box[3] - box[1] < 1:
                    continue
                p = _out_path(src, f"r{r}c{c}", out_dir=out_dir)
                paths.append(_save_image(img.crop(box), p))
    except BaseException:
        raise
    except Exception as e:
        raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
    return paths


def _load_font(font_path: str, size: int):
    """加载字体：自定义路径 → 平台常见中文字体 → Pillow 内置位图字体放大。"""
    from PIL import ImageFont

    if font_path and os.path.isfile(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"字体文件无法加载: {font_path}: {e}")
    import sys

    candidates = []
    if sys.platform == "win32":
        candidates = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arial.ttf"]
    elif sys.platform == "darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    for f in candidates:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
    return ImageFont.load_default(size=size)


def _read_clipboard_image_bytes(platform: str) -> bytes:
    """读取剪贴板图片原始字节：Windows DIB(补 BMP 文件头) / macOS TIFF(AppKit 或 osascript)。"""
    if platform == "win32":
        try:
            import win32clipboard
        except ImportError as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, f"缺少 pywin32: {e}")
        import struct

        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
                dib = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                # 构造 BITMAPFILEHEADER(14B) + DIB → BMP
                header = b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, 14 + struct.unpack("<I", dib[12:16])[0])
                return header + dib
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIBV5):
                dib = win32clipboard.GetClipboardData(win32clipboard.CF_DIBV5)
                header = b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, 14 + 124)
                return header + dib
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, "剪贴板中无图片数据")
        finally:
            win32clipboard.CloseClipboard()
    if platform == "darwin":
        try:
            from AppKit import NSPasteboard

            pb = NSPasteboard.generalPasteboard()
            types = pb.types()
            for t in ("public.tiff", "public.png", "NeXT transparent TIFF type"):
                if t in types:
                    data = pb.dataForType_(t)
                    if data:
                        return bytes(data)
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, "剪贴板中无图片数据")
        except ImportError:
            # 无 pyobjc 时回退 osascript 提取 TIFF hex
            import re
            import subprocess

            try:
                out = subprocess.run(
                    ["osascript", "-e", "the clipboard as «class TIFF»"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                ).stdout
                hexstr = re.sub(r"\s", "", out or "")
                m = re.search(r"«dataTIFF([0-9A-Fa-f]+)»", hexstr)
                if m:
                    return bytes.fromhex(m.group(1))
            except Exception as e:
                raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, f"读取剪贴板失败: {e}")
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, "剪贴板中无图片数据")
    raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, f"当前平台不支持剪贴板图片读取: {platform}")


def _parse_hex_color(color: str, default=(255, 255, 255)):
    c = (color or "").strip().lstrip("#")
    if len(c) == 6 and all(ch in string.hexdigits for ch in c):
        return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))
    if len(c) == 3 and all(ch in string.hexdigits for ch in c):
        return tuple(int(ch * 2, 16) for ch in c)
    return default


def _position_xy(pos: WatermarkPositionType, base_w: int, base_h: int, wm_w: int, wm_h: int, margin: int):
    p = pos.value if isinstance(pos, WatermarkPositionType) else str(pos)
    row, col = p.split("_")[0], p.split("_")[1]
    x = {"top": margin, "middle": (base_w - wm_w) // 2, "bottom": base_w - wm_w - margin}[row]
    y = {"left": margin, "center": (base_h - wm_h) // 2, "right": base_h - wm_h - margin}[col]
    return max(0, x), max(0, y)


class ImageProcess:
    """图片处理原子能力集合。"""

    # ---------- 信息类 ----------
    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param(
                "image_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("dpi", types="Int")],
    )
    def get_image_dpi(image_path: str):
        """获取图片DPI（水平分辨率），无DPI信息时返回72"""
        img = _open_image(image_path)
        dpi = img.info.get("dpi") or (72, 72)
        return max(1, int(round(float(dpi[0]))))

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param(
                "image_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
            atomicMg.param("dpi", types="Int"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def set_image_dpi(image_path: str, dpi: int = 300, save_path: str = ""):
        """设置图片DPI并另存，返回新图路径"""
        dpi = int(dpi)
        if dpi < 1 or dpi > 10000:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"DPI 须在 1-10000 之间: {dpi}")
        img = _open_image(image_path)
        path = save_path or _out_path(image_path, f"dpi{dpi}")
        return _save_image(img, path, dpi=dpi)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param(
                "image_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[
            atomicMg.param("width", types="Int"),
            atomicMg.param("height", types="Int"),
        ],
    )
    def get_image_size(image_path: str):
        """获取图片宽高（像素）"""
        img = _open_image(image_path)
        return img.size[0], img.size[1]

    # ---------- 缩放类 ----------
    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param(
                "image_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
            atomicMg.param("width", types="Int"),
            atomicMg.param("height", types="Int"),
            atomicMg.param("keep_ratio", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def resize_image_pixels(
        image_path: str, width: int = 0, height: int = 0, keep_ratio: bool = False, save_path: str = ""
    ):
        """按像素调整图片大小；keep_ratio 为 True 时等比缩放至宽高框内"""
        width, height = int(width), int(height)
        if width <= 0 or height <= 0:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"宽高须为正整数: {width}x{height}")
        img = _open_image(image_path)
        if keep_ratio:
            ratio = min(width / img.size[0], height / img.size[1])
            size = (max(1, int(img.size[0] * ratio)), max(1, int(img.size[1] * ratio)))
        else:
            size = (width, height)
        try:
            out = img.resize(size)
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        path = save_path or _out_path(image_path, f"{size[0]}x{size[1]}")
        return _save_image(out, path)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param(
                "image_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
            atomicMg.param("scale", types="Int"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def resize_image_scale(image_path: str, scale: int = 100, save_path: str = ""):
        """按百分比缩放图片（100=原大小），返回新图路径"""
        scale = int(scale)
        if scale < 1 or scale > 10000:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"缩放比例须在 1-10000 之间: {scale}")
        img = _open_image(image_path)
        size = (max(1, int(img.size[0] * scale / 100)), max(1, int(img.size[1] * scale / 100)))
        out = img.resize(size)
        path = save_path or _out_path(image_path, f"scale{scale}")
        return _save_image(out, path)

    # ---------- 转换/切割/裁剪/拼接/叠加类 ----------
    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("image_format", required=False),
            atomicMg.param("save_dir", types="Str", required=False),
        ],
        outputList=[atomicMg.param("image_paths_out", types="List")],
    )
    def convert_image_format(image_path, image_format: ImageFormatType = ImageFormatType.PNG, save_dir: str = ""):
        """批量转换图片格式（png/jpeg/bmp/webp），输入支持 单文件|列表|文件夹，返回新图路径列表"""
        fmt = (image_format.value if isinstance(image_format, ImageFormatType) else str(image_format or "png")).lower()
        if fmt not in ("png", "jpeg", "jpg", "bmp", "webp"):
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"不支持的目标格式: {fmt}")
        if fmt == "jpg":
            fmt = "jpeg"
        paths = _iter_images(image_path)
        out_paths = []
        try:
            for p in paths:
                img = _open_image(p)
                out = _out_path(p, fmt, f".{fmt}", save_dir)
                out_paths.append(_save_image(img, out, fmt=fmt))
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        return out_paths

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("block_width", types="Int"),
            atomicMg.param("block_height", types="Int"),
            atomicMg.param("out_dir", types="Str", required=False),
        ],
        outputList=[atomicMg.param("image_paths_out", types="List")],
    )
    def split_image_size(image_path: str, block_width: int = 0, block_height: int = 0, out_dir: str = ""):
        """按块宽高切割图片（每块 block_width×block_height 像素，边缘不足保留），返回切块路径列表（先行后列）"""
        block_width, block_height = int(block_width), int(block_height)
        if block_width <= 0 or block_height <= 0:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"切块宽高须为正整数: {block_width}x{block_height}")
        img = _open_image(image_path)
        if img.size[0] < block_width or img.size[1] < block_height:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"图片尺寸 {img.size[0]}x{img.size[1]} 小于切块尺寸")
        return _split(img, image_path, block_width, block_height, out_dir)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("rows", types="Int", required=False),
            atomicMg.param("cols", types="Int", required=False),
            atomicMg.param("out_dir", types="Str", required=False),
        ],
        outputList=[atomicMg.param("image_paths_out", types="List")],
    )
    def split_image_ratio(image_path: str, rows: int = 1, cols: int = 1, out_dir: str = ""):
        """按行列数等分切割图片（rows 行 cols 列），返回切块路径列表（先行后列）"""
        rows, cols = int(rows), int(cols)
        if rows < 1 or cols < 1 or rows > 100 or cols > 100:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"行列数须在 1-100 之间: {rows}x{cols}")
        img = _open_image(image_path)
        bw = max(1, img.size[0] // cols)
        bh = max(1, img.size[1] // rows)
        return _split(img, image_path, bw, bh, out_dir)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("left", types="Int"),
            atomicMg.param("top", types="Int"),
            atomicMg.param("right", types="Int"),
            atomicMg.param("bottom", types="Int"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def crop_image(image_path: str, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0, save_path: str = ""):
        """按左/上/右/下边界裁剪图片（像素坐标），返回新图路径"""
        left, top, right, bottom = int(left), int(top), int(right), int(bottom)
        img = _open_image(image_path)
        w, h = img.size
        if left < 0 or top < 0 or right > w or bottom > h or right - left < 1 or bottom - top < 1:
            raise BaseException(
                INVALID_PARAMS_ERROR_FORMAT,
                f"裁剪区域越界: ({left},{top},{right},{bottom}) 图片 {w}x{h}",
            )
        try:
            out = img.crop((left, top, right, bottom))
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        path = save_path or _out_path(image_path, f"crop{left}_{top}_{right}_{bottom}")
        return _save_image(out, path)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_paths", types="List"),
            atomicMg.param("direction", required=False),
            atomicMg.param("gap", types="Int", required=False),
            atomicMg.param("bg_color", types="Str", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def join_images(
        image_paths,
        direction: DirectionType = DirectionType.HORIZONTAL,
        gap: int = 0,
        bg_color: str = "#FFFFFF",
        save_path: str = "",
    ):
        """拼接多张图片（横向/纵向，间隔 gap 像素，背景色 bg_color），返回新图路径"""
        from PIL import Image

        paths = _iter_images(list(image_paths or []))
        if len(paths) < 2:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, "拼接至少需要2张图片")
        gap = max(0, int(gap or 0))
        bg = _parse_hex_color(bg_color, (255, 255, 255))
        horizontal = (direction.value if isinstance(direction, DirectionType) else str(direction)) != "vertical"
        try:
            imgs = [_open_image(p).convert("RGBA") for p in paths]
            if horizontal:
                w = sum(i.size[0] for i in imgs) + gap * (len(imgs) - 1)
                h = max(i.size[1] for i in imgs)
            else:
                w = max(i.size[0] for i in imgs)
                h = sum(i.size[1] for i in imgs) + gap * (len(imgs) - 1)
            canvas = Image.new("RGBA", (w, h), bg + (255,))
            x = y = 0
            for i in imgs:
                canvas.paste(i, (x, y), i)
                if horizontal:
                    x += i.size[0] + gap
                else:
                    y += i.size[1] + gap
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        first = paths[0]
        path = save_path or _out_path(first, f"join{len(paths)}")
        return _save_image(canvas, path)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("base_path", types="Str"),
            atomicMg.param("overlay_path", types="Str"),
            atomicMg.param("position", required=False),
            atomicMg.param("opacity", types="Int", required=False),
            atomicMg.param("margin", types="Int", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def overlay_images(
        base_path: str,
        overlay_path: str = "",
        position: WatermarkPositionType = WatermarkPositionType.MIDDLE_CENTER,
        opacity: int = 100,
        margin: int = 10,
        save_path: str = "",
    ):
        """将 overlay 图片叠加到 base 图片指定位置（九宫格+透明度），返回新图路径；叠图大于底图时自动等比缩小"""

        opacity = min(100, max(1, int(opacity or 100)))
        margin = max(0, int(margin or 0))
        base = _open_image(base_path).convert("RGBA")
        wm = _open_image(overlay_path).convert("RGBA")
        try:
            bw, bh = base.size
            if wm.size[0] > bw - 2 * margin or wm.size[1] > bh - 2 * margin:
                ratio = min((bw - 2 * margin) / wm.size[0], (bh - 2 * margin) / wm.size[1])
                if ratio > 0:
                    wm = wm.resize((max(1, int(wm.size[0] * ratio)), max(1, int(wm.size[1] * ratio))))
            if opacity < 100:
                alpha = wm.getchannel("A").point(lambda a: int(a * opacity / 100))
                wm.putalpha(alpha)
            x, y = _position_xy(position, bw, bh, wm.size[0], wm.size[1], margin)
            out = base.copy()
            out.paste(wm, (x, y), wm)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        path = save_path or _out_path(base_path, "overlay")
        return _save_image(out, path)

    # ---------- 水印/修饰类 ----------
    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("border", types="Int"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def trim_image_border(image_path: str, border: int = 0, save_path: str = ""):
        """去除图片边框（四边各裁掉 border 像素），返回新图路径"""
        border = int(border)
        if border < 0:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"边框像素须≥0: {border}")
        img = _open_image(image_path)
        w, h = img.size
        if 2 * border >= w or 2 * border >= h:
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"裁剪量超出图片尺寸: {border} 图片 {w}x{h}")
        out = img.crop((border, border, w - border, h - border))
        path = save_path or _out_path(image_path, f"trim{border}")
        return _save_image(out, path)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("watermark_path", types="Str"),
            atomicMg.param("x", types="Int", required=False),
            atomicMg.param("y", types="Int", required=False),
            atomicMg.param("opacity", types="Int", required=False),
            atomicMg.param("save_dir", types="Str", required=False),
        ],
        outputList=[atomicMg.param("image_paths_out", types="List")],
    )
    def add_image_watermark(
        image_path,
        watermark_path: str = "",
        x: int = 10,
        y: int = 10,
        opacity: int = 100,
        save_dir: str = "",
    ):
        """批量添加图片水印（x/y 定位，负值表示距右/下边缘），输入支持 单文件|列表|文件夹，返回新图路径列表"""
        opacity = min(100, max(1, int(opacity or 100)))
        wm = _open_image(watermark_path).convert("RGBA")
        if opacity < 100:
            alpha = wm.getchannel("A").point(lambda a: int(a * opacity / 100))
            wm.putalpha(alpha)
        paths = _iter_images(image_path)
        out_paths = []
        try:
            for p in paths:
                base = _open_image(p).convert("RGBA")
                bw, bh = base.size
                px = int(bw - wm.size[0] + int(x)) if int(x) < 0 else int(x)
                py = int(bh - wm.size[1] + int(y)) if int(y) < 0 else int(y)
                px = min(max(px, -wm.size[0]), bw)
                py = min(max(py, -wm.size[1]), bh)
                canvas = base.copy()
                canvas.paste(wm, (px, py), wm)
                out_paths.append(_save_image(canvas, _out_path(p, "wm", out_dir=save_dir)))
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        return out_paths

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("text", types="Str"),
            atomicMg.param("x", types="Int", required=False),
            atomicMg.param("y", types="Int", required=False),
            atomicMg.param("font_size", types="Int", required=False),
            atomicMg.param("color", types="Str", required=False),
            atomicMg.param("opacity", types="Int", required=False),
            atomicMg.param("font_path", types="Str", required=False),
            atomicMg.param("save_dir", types="Str", required=False),
        ],
        outputList=[atomicMg.param("image_paths_out", types="List")],
    )
    def add_text_watermark(
        image_path,
        text: str = "",
        x: int = 10,
        y: int = 10,
        font_size: int = 32,
        color: str = "#FF0000",
        opacity: int = 100,
        font_path: str = "",
        save_dir: str = "",
    ):
        """批量添加文字水印（x/y 定位负值距右/下，支持自定义字体文件），输入支持 单文件|列表|文件夹，返回新图路径列表"""
        from PIL import Image, ImageDraw

        if not text or not str(text).strip():
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, "水印文字不能为空")
        opacity = min(100, max(1, int(opacity or 100)))
        font_size = max(8, int(font_size or 32))
        rgb = _parse_hex_color(color, (255, 0, 0))
        font = _load_font(font_path, font_size)
        try:
            layer_txt = Image.new("RGBA", (font_size * (len(str(text)) + 1), font_size * 3), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer_txt)
            draw.text((0, 0), str(text), font=font, fill=rgb + (int(255 * opacity / 100),))
            wm = layer_txt.crop(layer_txt.getbbox() or (0, 0, 1, 1))
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        paths = _iter_images(image_path)
        out_paths = []
        try:
            for p in paths:
                base = _open_image(p).convert("RGBA")
                bw, bh = base.size
                px = int(bw - wm.size[0] + int(x)) if int(x) < 0 else int(x)
                py = int(bh - wm.size[1] + int(y)) if int(y) < 0 else int(y)
                px = min(max(px, -wm.size[0]), bw)
                py = min(max(py, -wm.size[1]), bh)
                canvas = base.copy()
                canvas.paste(wm, (px, py), wm)
                out_paths.append(_save_image(canvas, _out_path(p, "txtwm", out_dir=save_dir)))
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        return out_paths

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path1", types="Str"),
            atomicMg.param("image_path2", types="Str"),
        ],
        outputList=[atomicMg.param("similarity", types="Float")],
    )
    def image_similarity(image_path1: str, image_path2: str = ""):
        """比较两张图片相似度（0-1，1=完全相同；不同尺寸自动归一，灰度逐像素相关系数）"""
        import numpy as np

        a = _open_image(image_path1).convert("L").resize((256, 256))
        b = _open_image(image_path2).convert("L").resize((256, 256))
        try:
            va = np.asarray(a, dtype=np.float64).ravel()
            vb = np.asarray(b, dtype=np.float64).ravel()
            va -= va.mean()
            vb -= vb.mean()
            denom = float(np.sqrt((va * va).sum()) * np.sqrt((vb * vb).sum()))
            score = 0.0 if denom == 0 else float((va * vb).sum() / denom)
            return round(min(1.0, max(0.0, score)), 6)
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param(
                "save_path",
                types="Str",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def save_clipboard_image(save_path: str = ""):
        """保存剪贴板中的图片到指定路径（Windows DIB / macOS TIFF），返回图片路径"""
        import io
        import sys

        from PIL import Image

        path = save_path or os.path.join(os.getcwd(), f"clipboard_{int(time.time() * 1000)}.png")
        data = _read_clipboard_image_bytes(sys.platform)
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.load()
                return _save_image(img, path, fmt="png")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, f"剪贴板图片数据无效: {e}")

    # ---------- 高级类 ----------
    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("quality", types="Int", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def compress_image(image_path: str, quality: int = 85, save_path: str = ""):
        """压缩图片（质量1-100默认85，仅支持 jpg/png 且保持原格式），返回新图路径"""
        quality = min(100, max(1, int(quality or 85)))
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png"):
            raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"仅支持 jpg/png 压缩: {ext}")
        img = _open_image(image_path)
        path = save_path or _out_path(image_path, f"q{quality}")
        if ext == ".png":
            # png 无质量参数：compress_level 由质量反推（质量越低压缩越强）
            out = img.copy()
            parent = os.path.dirname(_abs(path))
            os.makedirs(parent, exist_ok=True)
            try:
                out.save(path, "PNG", compress_level=max(0, min(9, (100 - quality) // 11)), optimize=True)
                return path
            except Exception as e:
                raise BaseException(SAVE_FAILED_ERROR_FORMAT, str(e))
        return _save_image(img, path, fmt="jpeg", quality=quality)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("opacity", types="Int"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def set_image_opacity(image_path: str, opacity: int = 100, save_path: str = ""):
        """调整图片整体不透明度（0-100，输出带 alpha 通道的 PNG），返回新图路径"""

        opacity = min(100, max(0, int(opacity)))
        img = _open_image(image_path).convert("RGBA")
        try:
            alpha = img.getchannel("A").point(lambda a: int(a * opacity / 100))
            img.putalpha(alpha)
            out = img
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        path = save_path or _out_path(image_path, f"opacity{opacity}", ".png")
        return _save_image(out, path, fmt="png")

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("overwrite", required=False),
        ],
        outputList=[atomicMg.param("image_paths_out", types="List")],
    )
    def correct_extension(image_path, overwrite: bool = False):
        """批量更正图片扩展名为真实格式（嗅探 JPEG/PNG/BMP/GIF/WEBP），返回路径列表；目标已存在且不覆盖时保留原路径"""
        fmt_ext = {"JPEG": ".jpg", "PNG": ".png", "BMP": ".bmp", "GIF": ".gif", "WEBP": ".webp"}
        paths = _iter_images(image_path)
        out = []
        for p in paths:
            img = _open_image(p)
            real = fmt_ext.get((img.format or "").upper())
            if not real:
                out.append(p)
                continue
            cur = os.path.splitext(p)[1].lower()
            if cur == real or (cur == ".jpeg" and real == ".jpg"):
                out.append(p)
                continue
            dst = os.path.splitext(p)[0] + real
            if os.path.exists(dst):
                if not overwrite:
                    out.append(p)
                    continue
                os.remove(dst)
            os.rename(p, dst)
            out.append(dst)
        return out

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def image_to_sketch(image_path: str, save_path: str = ""):
        """彩图转线稿（灰度→反色→高斯模糊→颜色减淡），返回新图路径"""
        import numpy as np
        from PIL import Image, ImageFilter

        img = _open_image(image_path).convert("L")
        try:
            inv = Image.eval(img, lambda v: 255 - v)
            blur = inv.filter(ImageFilter.GaussianBlur(radius=10))
            base = np.asarray(img, dtype=np.float64)
            blend = np.asarray(blur, dtype=np.float64)
            denom = 255.0 - blend
            dodge = np.where(denom == 0, 255, np.minimum(255.0, base * 255.0 / np.maximum(denom, 1e-6)))
            out = Image.fromarray(dodge.astype("uint8"), mode="L")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        path = save_path or _out_path(image_path, "sketch")
        return _save_image(out, path)

    @staticmethod
    @atomicMg.atomic(
        "ImageProcess",
        inputList=[
            atomicMg.param("image_path", types="Str"),
            atomicMg.param("bg_color", required=False),
            atomicMg.param("custom_color", types="Str", required=False),
            atomicMg.param("tolerance", types="Int", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("image_path_out", types="Str")],
    )
    def replace_id_photo_bg(
        image_path: str,
        bg_color: IdPhotoBgColorType = IdPhotoBgColorType.BLUE,
        custom_color: str = "",
        tolerance: int = 30,
        save_path: str = "",
    ):
        """证件照换底色（蓝/红/白/自定义，色差容差10-50），返回新图路径"""
        import numpy as np

        colors = {"blue": (67, 133, 244), "red": (228, 40, 60), "white": (255, 255, 255)}
        key = bg_color.value if isinstance(bg_color, IdPhotoBgColorType) else str(bg_color or "blue")
        if key == "custom":
            target = _parse_hex_color(custom_color, (67, 133, 244))
        else:
            if key not in colors:
                raise BaseException(INVALID_PARAMS_ERROR_FORMAT, f"不支持的底色: {key}")
            target = colors[key]
        tolerance = min(50, max(10, int(tolerance or 30)))
        img = _open_image(image_path).convert("RGB")
        try:
            arr = np.asarray(img, dtype=np.int16)
            h, w = arr.shape[:2]
            corners = np.concatenate([arr[:2, :, :].reshape(-1, 3), arr[-2:, :, :].reshape(-1, 3)])
            bg = np.median(corners, axis=0)
            dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
            mask = dist < tolerance * 4.42  # RGB 欧氏距离阈值
            out = arr.astype(np.int16).copy()
            out[mask] = np.array(target, dtype=np.int16)
            from PIL import Image

            result = Image.fromarray(np.clip(out, 0, 255).astype("uint8"), mode="RGB")
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(IMAGE_PROCESS_ERROR_FORMAT, str(e))
        path = save_path or _out_path(image_path, f"idbg_{key}")
        return _save_image(result, path)
