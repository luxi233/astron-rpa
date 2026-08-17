"""M3 图片处理×21 冒烟测试（Pillow 现场生成随机纹理图，避免纯色图假通过）。"""

import inspect
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-image/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-actionlib/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-baseline/src")

import numpy as np
from PIL import Image

from astronverse.image import DirectionType, IdPhotoBgColorType, ImageFormatType, WatermarkPositionType
from astronverse.image.image import ImageProcess

TMP = tempfile.mkdtemp(prefix="m3_smoke_")
PASS = []
FAIL = []


def call(fn, *args, **kw):
    """位置参数自动转关键字（atomic wrapper 仅支持≤1个位置参数）。"""
    params = list(inspect.signature(fn).parameters)
    kw.update(dict(zip(params, args)))
    return fn(**kw)


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} | {name} {detail}")


def rand_img(w, h, seed, path=None):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, (h, w, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    if path:
        img.save(path)
    return img


# 造随机纹理测试图
A = os.path.join(TMP, "a.png")
B = os.path.join(TMP, "b.jpg")
A2 = os.path.join(TMP, "a_copy.png")
rand_img(200, 120, 1, path=A)
rand_img(200, 120, 1, path=A2)  # 同 seed 同内容
rand_img(200, 120, 2, path=B)
IDPHOTO = os.path.join(TMP, "id.png")
arr = np.full((150, 100, 3), (67, 133, 244), dtype=np.uint8)  # 蓝底
rng = np.random.default_rng(9)
arr[40:120, 25:75] = rng.integers(80, 200, (80, 50, 3), dtype=np.uint8)  # "人脸"随机纹理
Image.fromarray(arr, "RGB").save(IDPHOTO)

# 1-5 基础信息类
dpi = call(ImageProcess.get_image_dpi, A)
check("get_image_dpi", dpi == 72, f"dpi={dpi}")
out = call(ImageProcess.set_image_dpi, A, 300)
with Image.open(out) as im:
    d = im.info.get("dpi", (0,))[0]
    check("set_image_dpi", abs(d - 300) < 1, f"dpi={d}")  # PNG px/m 换算存在±0.01浮点误差
w, h = call(ImageProcess.get_image_size, A)
check("get_image_size", (w, h) == (200, 120), f"{w}x{h}")
out = call(ImageProcess.resize_image_pixels, A, 100, 50)
with Image.open(out) as im:
    check("resize_image_pixels", im.size == (100, 50), f"{im.size}")
out = call(ImageProcess.resize_image_pixels, A, 100, 100, True)
with Image.open(out) as im:
    check("resize_pixels_keep_ratio", im.size == (100, 60), f"{im.size}")
out = call(ImageProcess.resize_image_scale, A, 50)
with Image.open(out) as im:
    check("resize_image_scale", im.size == (100, 60), f"{im.size}")

# 6 转换格式（单文件+文件夹批量）
out = call(ImageProcess.convert_image_format, A, ImageFormatType.JPEG)
check("convert_single", len(out) == 1 and out[0].endswith(".jpeg") and os.path.exists(out[0]), out[0] if out else "")
FDIR = os.path.join(TMP, "batch")
os.makedirs(FDIR, exist_ok=True)
rand_img(50, 50, 3, path=os.path.join(FDIR, "x1.png"))
rand_img(50, 50, 4, path=os.path.join(FDIR, "x2.png"))
outs = call(ImageProcess.convert_image_format, FDIR, ImageFormatType.BMP)
check("convert_folder_batch", len(outs) == 2 and all(p.endswith(".bmp") for p in outs), str(outs))

# 7-8 切割
outs = call(ImageProcess.split_image_size, A, 100, 60)
check("split_size", len(outs) == 4 and all(os.path.exists(p) for p in outs), f"n={len(outs)}")
with Image.open(outs[0]) as im:
    check("split_size_block", im.size == (100, 60), f"{im.size}")
outs = call(ImageProcess.split_image_ratio, A, 2, 2)
check("split_ratio", len(outs) == 4, f"n={len(outs)}")

# 9 裁剪
out = call(ImageProcess.crop_image, A, 10, 20, 110, 100)
with Image.open(out) as im:
    check("crop_image", im.size == (100, 80), f"{im.size}")
try:
    call(ImageProcess.crop_image, A, 0, 0, 999, 100)
    check("crop_invalid", False)
except Exception:
    check("crop_invalid", True)

# 10 拼接
outs = call(ImageProcess.split_image_ratio, A, 1, 2)
out = call(ImageProcess.join_images, outs, DirectionType.HORIZONTAL)
with Image.open(out) as im:
    check("join_horizontal", im.size == (200, 120), f"{im.size}")
out = call(ImageProcess.join_images, outs, DirectionType.VERTICAL, 10)
with Image.open(out) as im:
    check("join_vertical_gap", im.size == (100, 250), f"{im.size}")

# 11 叠加
out = call(ImageProcess.overlay_images, A, B, WatermarkPositionType.BOTTOM_RIGHT, 80)
check("overlay_images", os.path.exists(out), out)

# 12 去边框
out = call(ImageProcess.trim_image_border, A, 10)
with Image.open(out) as im:
    check("trim_border", im.size == (180, 100), f"{im.size}")

# 13 图片水印（负值定位 + 批量列表）
outs = call(ImageProcess.add_image_watermark, [A, A2], B, -5, -5, 50)
check("img_watermark_batch", len(outs) == 2 and all(os.path.exists(p) for p in outs), f"n={len(outs)}")

# 14 文字水印
outs = call(ImageProcess.add_text_watermark, A, "水印测试", -10, 10, 24, "#FF0000")
check("text_watermark", len(outs) == 1 and os.path.exists(outs[0]), outs[0] if outs else "")
try:
    call(ImageProcess.add_text_watermark, A, "  ")
    check("text_watermark_empty", False)
except Exception:
    check("text_watermark_empty", True)

# 15 相似度
s1 = call(ImageProcess.image_similarity, A, A2)
s2 = call(ImageProcess.image_similarity, A, B)
check("similarity_same", s1 > 0.99, f"s={s1}")
check("similarity_diff", s2 < 0.5, f"s={s2}")

# 16 剪贴板图片
subprocess.run(["osascript", "-e", 'set the clipboard to "m3-smoke-text"'], timeout=5)
try:
    call(ImageProcess.save_clipboard_image, os.path.join(TMP, "clip.png"))
    check("clipboard_no_image_err", False, "应报错无图片")
except Exception as e:
    msg = getattr(e, "message", str(e))
    check("clipboard_no_image_err", "剪贴板" in msg, msg[:80])
clip_src = os.path.join(TMP, "clip_src.png")
rand_img(64, 48, 7, path=clip_src)
subprocess.run(["osascript", "-e", f'set the clipboard to (read (POSIX file "{clip_src}") as «class PNGf»)'], timeout=5)
out = call(ImageProcess.save_clipboard_image, os.path.join(TMP, "clip_out.png"))
with Image.open(out) as im:
    check("save_clipboard_image", im.size in [(64, 48)], f"{im.size}")

# 17 压缩
big = os.path.join(TMP, "big.jpg")
rand_img(800, 600, 11, path=big)
out = call(ImageProcess.compress_image, big, 30)
check(
    "compress_jpg_smaller",
    os.path.getsize(out) < os.path.getsize(big),
    f"{os.path.getsize(out)} < {os.path.getsize(big)}",
)
out = call(ImageProcess.compress_image, A, 60)
check("compress_png", os.path.exists(out), out)
try:
    gifp = os.path.join(TMP, "g.gif")
    rand_img(30, 30, 5).save(gifp)
    call(ImageProcess.compress_image, gifp, 60)  # gif 不支持压缩
    check("compress_format_guard", False)
except Exception:
    check("compress_format_guard", True)

# 18 透明度
out = call(ImageProcess.set_image_opacity, A, 50)
with Image.open(out) as im:
    alphas = list(im.convert("RGBA").getchannel("A").getdata())
    check("set_opacity", im.format == "PNG" and max(alphas) == 127, f"max={max(alphas)} fmt={im.format}")

# 19 更正扩展名（伪扩展名 png→实际 jpg）
fake = os.path.join(TMP, "fake.png")
shutil.copy(B, fake)
outs = call(ImageProcess.correct_extension, fake)
check("correct_ext_rename", outs[0].endswith(".jpg") and os.path.exists(outs[0]), str(outs))
fake2 = os.path.join(TMP, "fake2.png")
shutil.copy(B, fake2)
outs2 = call(ImageProcess.correct_extension, fake2)
check("correct_ext_list_input", outs2[0].endswith(".jpg"), str(outs2))

# 20 线稿
out = call(ImageProcess.image_to_sketch, A)
with Image.open(out) as im:
    check("image_to_sketch", im.mode == "L" and im.size == (200, 120), f"{im.mode}{im.size}")

# 21 证件照换底色（蓝→白，验证角落变白而"人脸"保留）
out = call(ImageProcess.replace_id_photo_bg, IDPHOTO, IdPhotoBgColorType.WHITE, "", 20)
with Image.open(out) as im:
    corner = im.getpixel((5, 5))
    face = im.getpixel((50, 80))
    check("idphoto_bg", corner == (255, 255, 255), f"corner={corner}")
    check("idphoto_face_kept", face != (255, 255, 255), f"face={face}")

# 参数校验负路径
for name, fn in [
    ("resize_scale_invalid", lambda: call(ImageProcess.resize_image_scale, A, 0)),
    ("split_size_invalid", lambda: call(ImageProcess.split_image_size, A, 0, 10)),
    ("split_ratio_invalid", lambda: call(ImageProcess.split_image_ratio, A, 0, 1)),
    ("join_needs2", lambda: call(ImageProcess.join_images, [A])),
    ("dpi_invalid", lambda: call(ImageProcess.set_image_dpi, A, 0)),
    ("file_not_found", lambda: call(ImageProcess.get_image_size, "/no/such/file.png")),
]:
    try:
        fn()
        check(name, False, "应报错")
    except Exception as e:
        check(name, True, str(e)[:60])

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n===== PASS {len(PASS)} / FAIL {len(FAIL)} =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
