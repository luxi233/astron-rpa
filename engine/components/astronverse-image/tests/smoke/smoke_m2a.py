# -*- coding: utf-8 -*-
"""M2-A批次冒烟: P4-6 条码二维码×3 (生成二维码/生成条形码/识别) 正常+异常路径"""
import os
import sys
import tempfile

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-image/src")

from astronverse.baseline.error.error import BaseException  # noqa: E402
from astronverse.image import BarcodeType, QrErrorCorrectionType  # noqa: E402
from astronverse.image.barcode import Barcode as B  # noqa: E402

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


def expect_err(name, fn, kw, keyword):
    global passed, failed
    try:
        fn(**kw)
        failed += 1
        print(f"FAIL {name} 未抛异常")
    except BaseException as e:
        msg = str(e)
        if keyword in msg:
            passed += 1
            print(f"PASS {name}: {msg[:80]}")
        else:
            failed += 1
            print(f"FAIL {name} 关键词[{keyword}]不在: {msg[:120]}")
    except Exception as e:  # noqa: BLE001
        failed += 1
        print(f"FAIL {name} 异常类型不符: {type(e).__name__} {e}")


tmp = tempfile.mkdtemp(prefix="m2a_")

# ---------- 生成二维码 ----------
p1 = os.path.join(tmp, "qr.png")
r = B.create_qrcode(content="https://example.com/测试", size=300, error_correction=QrErrorCorrectionType.H, save_path=p1)
check("qrcode 生成成功返回路径", r == p1 and os.path.exists(p1), r)
from PIL import Image  # noqa: E402

with Image.open(p1) as img:
    check("qrcode 尺寸=300", img.size == (300, 300), img.size)
    check("qrcode PNG格式", img.format == "PNG", img.format)

p1b = B.create_qrcode(content="默认参数", save_path=os.path.join(tmp, "qr_default.png"))
check("qrcode 默认参数(M容错,300)", os.path.exists(p1b))

p1c = B.create_qrcode(content="小尺寸自动抬高到60", size=10, save_path=os.path.join(tmp, "qr_small.png"))
with Image.open(p1c) as img:
    check("qrcode 最小60像素", img.size == (60, 60), img.size)

expect_err("qrcode 空内容报错", B.create_qrcode, {"content": "  ", "save_path": os.path.join(tmp, "x.png")}, "生成内容无效")
expect_err("qrcode 坏路径报错", B.create_qrcode, {"content": "x", "save_path": "/nonexist_dir_abc/qr.png"}, "保存失败")

# ---------- 生成条形码 ----------
p2 = os.path.join(tmp, "bc128.png")
r = B.create_barcode(content="ABC-123456", barcode_type=BarcodeType.CODE128, save_path=p2)
check("barcode CODE128 成功", r == p2 and os.path.exists(p2), r)
with Image.open(p2) as img:
    check("barcode CODE128 PNG", img.format == "PNG")

p3 = os.path.join(tmp, "ean13.png")
r = B.create_barcode(content="6901234567892", barcode_type=BarcodeType.EAN13, save_path=p3)
check("barcode EAN13 13位成功", os.path.exists(p3))

p4 = B.create_barcode(content="690123456789", barcode_type=BarcodeType.EAN13, save_path=os.path.join(tmp, "ean12.png"))
check("barcode EAN13 12位自动补校验码", os.path.exists(p4))

expect_err("barcode EAN13 非数字报错", B.create_barcode, {"content": "abc", "barcode_type": BarcodeType.EAN13, "save_path": os.path.join(tmp, "x.png")}, "生成内容无效")
expect_err("barcode 空内容报错", B.create_barcode, {"content": "", "barcode_type": BarcodeType.CODE128, "save_path": os.path.join(tmp, "x.png")}, "生成内容无效")

# ---------- 识别 ----------
r = B.recognize_code(image_path=p1)
check("识别二维码 内容回读", len(r) == 1 and r[0]["内容"] == "https://example.com/测试", r)
check("识别二维码 类型QRCODE", r and r[0]["类型"] == "QRCODE", r)

r = B.recognize_code(image_path=p2)
check("识别条形码 CODE128回读", len(r) == 1 and r[0]["内容"] == "ABC-123456", r)
check("识别条形码 类型CODE128", r and r[0]["类型"] == "CODE128", r)

r = B.recognize_code(image_path=p3)
check("识别EAN13回读", len(r) == 1 and r[0]["内容"] == "6901234567892", r)

# 一图两码: 二维码+条形码拼一张图
from PIL import Image as PILImage  # noqa: E402

imgs = [PILImage.open(p) for p in (p1, p2)]
w = sum(i.width for i in imgs) + 10
h = max(i.height for i in imgs)
combo = PILImage.new("RGB", (w, h), "white")
x = 0
for i in imgs:
    combo.paste(i, (x, 0))
    x += i.width + 10
combo_path = os.path.join(tmp, "combo.png")
combo.save(combo_path)
for i in imgs:
    i.close()
r = B.recognize_code(image_path=combo_path)
check("一图多码识别到2个", len(r) == 2, r)

expect_err("识别 文件不存在报错", B.recognize_code, {"image_path": "/nonexist_dir_abc/x.png"}, "文件不存在")

# 空白图返回空列表
blank = os.path.join(tmp, "blank.png")
PILImage.new("RGB", (200, 100), "white").save(blank)
r = B.recognize_code(image_path=blank)
check("空白图返回空列表", r == [], r)

print(f"\n=== M2-A 冒烟: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
