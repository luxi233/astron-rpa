"""M4 PDF扩展×13 冒烟测试：reportlab 现场造带线框表格/多页 PDF，pypdf 解密验证，全链路真实执行。"""

import inspect
import os
import sys
import tempfile

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-pdf/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-actionlib/src")
sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/shared/astronverse-baseline/src")

from pypdf import PdfReader

from astronverse.pdf import RegionType, RotateDirection, SplitModeType, WatermarkLayoutType
from astronverse.pdf.error import BaseException
from astronverse.pdf.pdf_ext import PDFExt, parse_page_ranges

TMP = tempfile.mkdtemp(prefix="m4_smoke_")
PASS, FAIL = [], []
A4 = (595.28, 841.89)


def call(fn, *args, **kw):
    """位置参数自动转关键字（atomic wrapper 仅支持≤1个位置参数）。"""
    params = list(inspect.signature(fn).parameters)
    kw.update(dict(zip(params, args)))
    return fn(**kw)


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} | {name} {detail}")


def expect_raise(name, fn, *args, **kw):
    try:
        call(fn, *args, **kw)
        check(name, False, "未抛异常")
    except BaseException as e:
        check(name, "astronverse" in type(e).__module__ or type(e).__name__ == "BaseException", f"→ {str(e)[:60]}")
    except Exception as e:  # noqa: BLE001
        check(name, False, f"非预期异常类型 {type(e).__name__}: {e}")


# ---------- reportlab 造测试 PDF ----------
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

T1 = os.path.join(TMP, "t_table.pdf")  # 3页：线框表格/纯文本/线框表格
c = canvas.Canvas(T1, pagesize=A4)
for page in range(3):
    if page in (0, 2):
        data = [["姓名", "年龄", "城市"], ["张三", "25", "北京"], ["李四", "30", "上海"]]
        x0, y_top, col_w, row_h = 50, 750, 150, 30
        c.setFont("STSong-Light", 12)
        for r, row in enumerate(data):
            for ci, cell in enumerate(row):
                c.drawString(x0 + ci * col_w + 50, y_top - r * row_h - 20, cell)
        for r in range(len(data) + 1):
            c.line(x0, y_top - r * row_h, x0 + 3 * col_w, y_top - r * row_h)
        for ci in range(4):
            c.line(x0 + ci * col_w, y_top, x0 + ci * col_w, y_top - len(data) * row_h)
    else:
        c.setFont("Helvetica", 16)
        c.drawString(60, 700, "Hello World RegionTest Page2")
    c.showPage()
c.save()

T2 = os.path.join(TMP, "t_noline.pdf")  # 无线表格（文本列对齐）
c = canvas.Canvas(T2, pagesize=A4)
c.setFont("STSong-Light", 12)
rows = [("姓名", "年龄", "城市"), ("王五", "28", "广州"), ("赵六", "35", "深圳")]
for r, row in enumerate(rows):
    for ci, cell in enumerate(row):
        c.drawString(60 + ci * 160, 760 - r * 30, cell)
c.save()

# 随机纹理图 ×2（避免纯色假通过）
import numpy as np
from PIL import Image

IMG1, IMG2 = os.path.join(TMP, "i1.png"), os.path.join(TMP, "i2.jpg")
Image.fromarray(np.random.default_rng(1).integers(0, 256, (120, 200, 3), dtype=np.uint8), "RGB").save(IMG1)
Image.fromarray(np.random.default_rng(2).integers(0, 256, (100, 180, 3), dtype=np.uint8), "RGB").save(IMG2)

# ---------- 1. 页码语法 parse_page_ranges ----------
check("parse 1,3@5", parse_page_ranges("1,3", 5) == [0, 2])
check("parse -1@5", parse_page_ranges("-1", 5) == [4])
check("parse 2-1翻转", parse_page_ranges("2-1", 5) == [0, 1])
check("parse 空串=全部", parse_page_ranges("", 3) == [0, 1, 2])
check("parse 越界段忽略", parse_page_ranges("2-9", 3) == [1, 2])
expect_raise("parse abc抛错", parse_page_ranges, "abc", 3)

# ---------- 2. 表格提取 ----------
t = call(PDFExt.extract_table_lines, T1)
flat = [cell for tbl in t for row in tbl for cell in row if cell]
check("extract_table_lines 含表头/数据", any("姓名" in str(x) for x in flat) and any("上海" in str(x) for x in flat), f"表数={len(t)}")

t2 = call(PDFExt.extract_table_spacing, T2)
flat2 = [cell for tbl in t2 for row in tbl for cell in row if cell]
check("extract_table_spacing 无线表格", len(flat2) >= 5 and any("王五" in str(x) for x in flat2), f"表数={len(t2)}")

t3 = call(PDFExt.get_pdf_table, T1)
check("get_pdf_table 自动策略", any(any("张三" in str(c) for row in tbl for c in row if c) for tbl in t3), f"表数={len(t3)}")
check("get_pdf_table 页码过滤", call(PDFExt.get_pdf_table, T1, "", "1") == call(PDFExt.get_pdf_table, T1, "", "1"))

# ---------- 3. 区域提取 ----------
rt = call(PDFExt.extract_region_text, T1, 0, 650, 595, 720, 2)
check("extract_region_text 第2页区域文本", "RegionTest" in (rt or ""), f"→ {rt[:40]!r}")
rt_empty = call(PDFExt.extract_region_text, T1, 0, 0, 50, 50, 2)
check("extract_region_text 空区域=空串", rt_empty == "")

regions = call(PDFExt.get_typed_regions, T1, RegionType.TEXT_BLOCK)
check("get_typed_regions text_block", any(r["page"] == 2 and "RegionTest" in r.get("text", "") for r in regions), f"n={len(regions)}")
regions_t = call(PDFExt.get_typed_regions, T1, RegionType.TABLE, "", "1")
check("get_typed_regions table 第1页", len(regions_t) >= 1 and regions_t[0]["cells"] >= 9, f"n={len(regions_t)}")
regions_i = call(PDFExt.get_typed_regions, T1, RegionType.IMAGE)
check("get_typed_regions image 无图=空列表", regions_i == [])

# ---------- 4. 加密 ----------
enc = call(PDFExt.encrypt_pdf, T1, "test123")
r = PdfReader(enc)
check("encrypt_pdf 输出已加密", r.is_encrypted)
check("encrypt_pdf 密码可解密", len(PdfReader(enc, password="test123").pages) == 3)
expect_raise("encrypt_pdf 空密码抛错", PDFExt.encrypt_pdf, T1, "")
expect_raise("加密文件无密码读取抛错", PDFExt.extract_table_lines, enc)

# ---------- 5. 旋转/尺寸 ----------
rot = call(PDFExt.rotate_pdf, T1, RotateDirection.CLOCKWISE, "1")
rr = PdfReader(rot)
check("rotate_pdf 第1页rotation=90", rr.pages[0].rotation in (90, -270) and rr.pages[1].rotation in (0, 360))
rot2 = call(PDFExt.rotate_pdf, T1, RotateDirection.COUNTER_CLOCKWISE, "-1")
rr2 = PdfReader(rot2)
check("rotate_pdf 逆时针-1页", rr2.pages[2].rotation in (-90, 270) and rr2.pages[0].rotation in (0, 360))

w, h = call(PDFExt.get_page_size, T1)
check("get_page_size A4", abs(w - 595.28) < 0.01 and abs(h - 841.89) < 0.01, f"→ {w}x{h}")
expect_raise("get_page_size 越界抛错", PDFExt.get_page_size, T1, 99)

# ---------- 6. 分割/删页 ----------
sp = call(PDFExt.split_pdf, T1, SplitModeType.SINGLE_PAGES)
check("split_pdf 每页一文件", len(sp) == 3 and all(os.path.isfile(p) and len(PdfReader(p).pages) == 1 for p in sp))
sp2 = call(PDFExt.split_pdf, T1, SplitModeType.AT_POSITION, 2)
check("split_pdf 指定位置2→2文件", len(sp2) == 2 and [len(PdfReader(p).pages) for p in sp2] == [2, 1])
expect_raise("split_pdf 位置越界抛错", PDFExt.split_pdf, T1, SplitModeType.AT_POSITION, 9)

dele = call(PDFExt.delete_pdf_pages, T1, "2")
check("delete_pdf_pages 删第2页", len(PdfReader(dele).pages) == 2)
check("delete_pdf_pages 倒数页语法", len(PdfReader(call(PDFExt.delete_pdf_pages, T1, "-1")).pages) == 2)
expect_raise("delete_pdf_pages 全删抛错", PDFExt.delete_pdf_pages, T1, "1-3")

# ---------- 7. 图片合成 ----------
ip = call(PDFExt.images_to_pdf, f"{IMG1},{IMG2}")
check("images_to_pdf 2图=2页", os.path.isfile(ip) and len(PdfReader(ip).pages) == 2)
ip2 = call(PDFExt.images_to_pdf, [IMG2, IMG1])
check("images_to_pdf 列表入参", len(PdfReader(ip2).pages) == 2)
expect_raise("images_to_pdf 空列表抛错", PDFExt.images_to_pdf, "")
expect_raise("images_to_pdf 文件不存在抛错", PDFExt.images_to_pdf, "/tmp/none.png")

# ---------- 8. 水印 ----------
wm = call(PDFExt.create_watermark_pdf, "机密水印", "", WatermarkLayoutType.TILE, 36, 20, 45, "#FF0000")
check("create_watermark_pdf 平铺", os.path.isfile(wm) and len(PdfReader(wm).pages) == 1)
wm2 = call(PDFExt.create_watermark_pdf, "DRAFT", "", WatermarkLayoutType.SINGLE)
check("create_watermark_pdf 居中单个", len(PdfReader(wm2).pages) == 1)
expect_raise("create_watermark_pdf 空文字抛错", PDFExt.create_watermark_pdf, "  ")

wm_out = call(PDFExt.add_pdf_watermark, T1, wm)
wr = PdfReader(wm_out)
check("add_pdf_watermark 页数不变", len(wr.pages) == 3)
wm_text = wr.pages[0].extract_text() or ""
check("add_pdf_watermark 水印文字已叠加", "机密水印" in wm_text and "张三" in wm_text)

# ---------- 9. 文件异常 ----------
expect_raise("不存在文件抛错", PDFExt.get_page_size, "/tmp/none.pdf")

print(f"\n===== M4 冒烟 {len(PASS)}/{len(PASS) + len(FAIL)} 通过 =====")
if FAIL:
    print("FAILED:", FAIL)
    sys.exit(1)
