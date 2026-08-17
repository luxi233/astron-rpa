"""PDF 扩展原子能力：表格提取/区域文本/加密/旋转/分割/删页/水印等（pypdf + pdfplumber + reportlab，跨平台）。"""

import os
import string
import time

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta
from astronverse.actionlib.atomic import atomicMg
from astronverse.pdf import (
    RegionType,
    RotateDirection,
    SplitModeType,
    WatermarkLayoutType,
)
from astronverse.pdf.error import (
    FILE_PATH_ERROR_FORMAT,
    INVALID_PARAMS_PDF_ERROR_FORMAT,
    PDF_PROCESS_ERROR_FORMAT,
    PDF_READ_ERROR_FORMAT,
    PDF_SAVE_ERROR_FORMAT,
    TABLE_EXTRACT_ERROR_FORMAT,
    BaseException,
)


def _check_pdf(path: str):
    if not path or not os.path.isfile(path):
        raise BaseException(FILE_PATH_ERROR_FORMAT.format(str(path)), "PDF文件不存在")


def _open_plumber(path: str, password: str = ""):
    """打开 pdfplumber（密码页自动解密），失败区分损坏/密码错误。"""
    import pdfplumber

    _check_pdf(path)
    try:
        pdf = pdfplumber.open(path, password=password or None)
        return pdf
    except Exception as e:
        msg = str(e)
        if "encrypt" in msg.lower() or "password" in msg.lower() or "decrypt" in msg.lower():
            raise BaseException(PDF_READ_ERROR_FORMAT.format(str(path)), "文件已加密且密码错误或未提供")
        raise BaseException(PDF_READ_ERROR_FORMAT.format(f"{path}: {e}"), "PDF文件读取失败")


def _open_pypdf(path: str, password: str = ""):
    """打开 pypdf PdfReader（自动解密）。"""
    from pypdf import PdfReader

    _check_pdf(path)
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            if not reader.decrypt(password or ""):
                raise BaseException(PDF_READ_ERROR_FORMAT.format(str(path)), "文件已加密且密码错误或未提供")
        return reader
    except BaseException:
        raise
    except Exception as e:
        raise BaseException(PDF_READ_ERROR_FORMAT.format(f"{path}: {e}"))


def parse_page_ranges(spec: str, total: int) -> list:
    """页码语法解析：'1,3,5-7'，负数倒数（-1=最后一页），空串=全部页。返回排序去重的 0-based 页列表。"""
    spec = (spec or "").strip()
    if not spec:
        return list(range(total))
    pages = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part[1:]:
            a, _, b = part.partition("-")
            try:
                start = int(a.strip())
                end = int(b.strip())
            except ValueError:
                raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(part), "页码格式有误，示例: 1,3,5-7 或 -1")
            if start < 0:
                start = total + start + 1
            if end < 0:
                end = total + end + 1
            if start > end:
                start, end = end, start
            for p in range(start, end + 1):
                if 1 <= p <= total:
                    pages.add(p - 1)
        else:
            try:
                p = int(part)
            except ValueError:
                raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(part), "页码格式有误，示例: 1,3,5-7 或 -1")
            if p < 0:
                p = total + p + 1
            if not (1 <= p <= total):
                raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(f"{part}"), f"页码超出范围 1-{total}")
            pages.add(p - 1)
    if not pages:
        raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(spec), "未解析到有效页码")
    return sorted(pages)


def _out_pdf_path(src: str, suffix: str, save_dir: str = "") -> str:
    d = save_dir or os.path.dirname(os.path.abspath(src))
    os.makedirs(d, exist_ok=True)
    name = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(d, f"{name}_{suffix}.pdf")


def _write_pages(reader, page_indices, out_path: str) -> str:
    from pypdf import PdfWriter

    try:
        writer = PdfWriter()
        for i in page_indices:
            writer.add_page(reader.pages[i])
        parent = os.path.dirname(os.path.abspath(out_path))
        os.makedirs(parent, exist_ok=True)
        with open(out_path, "wb") as f:
            writer.write(f)
        return out_path
    except BaseException:
        raise
    except Exception as e:
        raise BaseException(PDF_SAVE_ERROR_FORMAT.format(str(e)))


def _parse_hex_color(color: str, default=(0.5, 0.5, 0.5)):
    """'#RRGGBB' → reportlab 0-1 RGB。"""
    c = (color or "").strip().lstrip("#")
    if len(c) == 6 and all(ch in string.hexdigits for ch in c):
        return tuple(int(c[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return default


class PDFExt:
    """PDF 扩展原子能力集合（表格/区域/加密/旋转/分割/水印）。"""

    # ---------- 表格提取 ----------
    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param("page_range", types="Str", required=False),
        ],
        outputList=[atomicMg.param("tables", types="List")],
    )
    def extract_table_spacing(file_path: str = "", password: str = "", page_range: str = ""):
        """按文本间距启发式提取PDF表格（无线框表格），输出二维列表的列表（每页多个表格）"""
        return _extract_tables(file_path, password, page_range, "text")

    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param("page_range", types="Str", required=False),
        ],
        outputList=[atomicMg.param("tables", types="List")],
    )
    def extract_table_lines(file_path: str = "", password: str = "", page_range: str = ""):
        """按表格线提取PDF表格（有线框/横线的表格），输出二维列表的列表（每页多个表格）"""
        return _extract_tables(file_path, password, page_range, "lines")

    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param("page_range", types="Str", required=False),
        ],
        outputList=[atomicMg.param("tables", types="List")],
    )
    def get_pdf_table(file_path: str = "", password: str = "", page_range: str = ""):
        """获取PDF表格内容（自动策略：优先按线，无线时按文本间距），输出二维列表的列表"""
        tables = _extract_tables(file_path, password, page_range, "lines")
        if not any(t for t in tables):
            tables = _extract_tables(file_path, password, page_range, "text")
        return tables

    # ---------- 区域提取 ----------
    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("x0", types="Int"),
            atomicMg.param("top", types="Int"),
            atomicMg.param("x1", types="Int"),
            atomicMg.param("bottom", types="Int"),
            atomicMg.param("page_number", types="Int", required=False),
            atomicMg.param("password", types="Str", required=False),
        ],
        outputList=[atomicMg.param("region_text", types="Str")],
    )
    def extract_region_text(
        file_path: str = "",
        x0: int = 0,
        top: int = 0,
        x1: int = 0,
        bottom: int = 0,
        page_number: int = 1,
        password: str = "",
    ):
        """提取PDF指定页面矩形区域内的文字（左上原点，pt坐标），输出文本"""
        x0, top, x1, bottom = int(x0), int(top), int(x1), int(bottom)
        page_number = int(page_number or 1)
        pdf = _open_plumber(file_path, password)
        try:
            if not (1 <= page_number <= len(pdf.pages)):
                raise BaseException(
                    INVALID_PARAMS_PDF_ERROR_FORMAT.format(f"{page_number}"),
                    f"页码超出范围 1-{len(pdf.pages)}",
                )
            page = pdf.pages[page_number - 1]
            ph = float(page.height)
            # 前端左上原点 → pdfplumber 左下原点
            bbox = (float(x0), ph - float(bottom), float(x1), ph - float(top))
            region = page.crop(bbox)
            return region.extract_text() or ""
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_PROCESS_ERROR_FORMAT.format(str(e)))
        finally:
            pdf.close()

    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("region_type", required=False),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param("page_range", types="Str", required=False),
        ],
        outputList=[atomicMg.param("regions", types="List")],
    )
    def get_typed_regions(
        file_path: str = "",
        region_type: RegionType = RegionType.TEXT_BLOCK,
        password: str = "",
        page_range: str = "",
    ):
        """获取指定类型的区域（文本块/图片/表格），输出区域列表（每项含 页码/bbox坐标/内容）"""
        rt = region_type.value if isinstance(region_type, RegionType) else str(region_type or "text_block")
        pdf = _open_plumber(file_path, password)
        try:
            total = len(pdf.pages)
            indices = parse_page_ranges(page_range, total)
            regions = []
            for i in indices:
                page = pdf.pages[i]
                ph = float(page.height)
                if rt == "text_block":
                    # 词按行聚类 → 行块
                    words = page.extract_words()
                    lines = {}
                    for w in words:
                        key = round(float(w["top"]) / 3)
                        lines.setdefault(key, []).append(w)
                    for key in sorted(lines):
                        ws = sorted(lines[key], key=lambda w: float(w["x0"]))
                        regions.append(
                            {
                                "page": i + 1,
                                "bbox": [
                                    round(min(float(w["x0"]) for w in ws)),
                                    round(ph - max(float(w["bottom"]) for w in ws)),
                                    round(max(float(w["x1"]) for w in ws)),
                                    round(ph - min(float(w["top"]) for w in ws)),
                                ],
                                "text": " ".join(w["text"] for w in ws),
                            }
                        )
                elif rt == "image":
                    for im in page.images:
                        regions.append(
                            {
                                "page": i + 1,
                                "bbox": [
                                    round(float(im["x0"])),
                                    round(ph - float(im["bottom"])),
                                    round(float(im["x1"])),
                                    round(ph - float(im["top"])),
                                ],
                                "name": im.get("name", ""),
                            }
                        )
                elif rt == "table":
                    for t in page.find_tables():
                        regions.append(
                            {
                                "page": i + 1,
                                "bbox": [round(v) for v in (t.bbox[0], ph - t.bbox[3], t.bbox[2], ph - t.bbox[1])],
                                "cells": len(t.cells),
                            }
                        )
                else:
                    raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(rt), "不支持的区域类型")
            return regions
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_PROCESS_ERROR_FORMAT.format(str(e)))
        finally:
            pdf.close()

    # ---------- 加密/旋转/尺寸 ----------
    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("password", types="Str"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("pdf_path_out", types="Str")],
    )
    def encrypt_pdf(file_path: str = "", password: str = "", save_path: str = ""):
        """加密PDF文件（设置打开密码），输出新文件路径"""
        from pypdf import PdfWriter

        if not password or not str(password).strip():
            raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(""), "密码不能为空")
        reader = _open_pypdf(file_path)
        try:
            writer = PdfWriter(clone_from=reader)
            writer.encrypt(str(password))
            out = save_path or _out_pdf_path(file_path, "encrypted")
            parent = os.path.dirname(os.path.abspath(out))
            os.makedirs(parent, exist_ok=True)
            with open(out, "wb") as f:
                writer.write(f)
            return out
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_SAVE_ERROR_FORMAT.format(str(e)))

    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("direction", required=False),
            atomicMg.param("page_range", types="Str", required=False),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("pdf_path_out", types="Str")],
    )
    def rotate_pdf(
        file_path: str = "",
        direction: RotateDirection = RotateDirection.CLOCKWISE,
        page_range: str = "",
        password: str = "",
        save_path: str = "",
    ):
        """旋转PDF指定页面（顺时针/逆时针90度），输出新文件路径"""
        from pypdf import PdfWriter

        clockwise = (
            direction.value if isinstance(direction, RotateDirection) else str(direction)
        ) != "counter_clockwise"
        reader = _open_pypdf(file_path, password)
        try:
            total = len(reader.pages)
            indices = set(parse_page_ranges(page_range, total))
            writer = PdfWriter(clone_from=reader)
            for i in indices:
                page = writer.pages[i]
                page.rotate(90 if clockwise else -90)
            out = save_path or _out_pdf_path(file_path, "rotated")
            parent = os.path.dirname(os.path.abspath(out))
            os.makedirs(parent, exist_ok=True)
            with open(out, "wb") as f:
                writer.write(f)
            return out
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_SAVE_ERROR_FORMAT.format(str(e)))

    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("page_number", types="Int", required=False),
            atomicMg.param("password", types="Str", required=False),
        ],
        outputList=[
            atomicMg.param("width", types="Float"),
            atomicMg.param("height", types="Float"),
        ],
    )
    def get_page_size(file_path: str = "", page_number: int = 1, password: str = ""):
        """获取PDF指定页面的宽和高（pt磅），返回宽与高"""
        reader = _open_pypdf(file_path, password)
        total = len(reader.pages)
        page_number = int(page_number or 1)
        if not (1 <= page_number <= total):
            raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(f"{page_number}"), f"页码超出范围 1-{total}")
        box = reader.pages[page_number - 1].mediabox
        return round(float(box.width), 2), round(float(box.height), 2)

    # ---------- 分割/删页 ----------
    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("split_mode", required=False),
            atomicMg.param("position", types="Int", required=False),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param(
                "save_dir",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "folder"}
                ),
            ),
        ],
        outputList=[atomicMg.param("pdf_paths_out", types="List")],
    )
    def split_pdf(
        file_path: str = "",
        split_mode: SplitModeType = SplitModeType.SINGLE_PAGES,
        position: int = 1,
        password: str = "",
        save_dir: str = "",
    ):
        """分割PDF（单页分割 / 在第N页处分成两个文件），输出文件路径列表"""
        mode = split_mode.value if isinstance(split_mode, SplitModeType) else str(split_mode or "single_pages")
        reader = _open_pypdf(file_path, password)
        total = len(reader.pages)
        out_dir = save_dir or os.path.dirname(os.path.abspath(file_path))
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(file_path))[0]
        try:
            paths = []
            if mode == "single_pages":
                for i in range(total):
                    p = os.path.join(out_dir, f"{base}_p{i + 1}.pdf")
                    _write_pages(reader, [i], p)
                    paths.append(p)
            elif mode == "at_position":
                pos = int(position or 1)
                if not (1 <= pos <= total):
                    raise BaseException(
                        INVALID_PARAMS_PDF_ERROR_FORMAT.format(f"{pos}"), f"分割位置须在 1-{total} 之间"
                    )
                for idx, rng in enumerate([(0, pos), (pos, total)]):
                    if rng[0] >= rng[1]:
                        continue
                    p = os.path.join(out_dir, f"{base}_part{idx + 1}.pdf")
                    _write_pages(reader, list(range(rng[0], rng[1])), p)
                    paths.append(p)
            else:
                raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(mode), "不支持的分割模式")
            return paths
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_SAVE_ERROR_FORMAT.format(str(e)))

    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("page_range", types="Str"),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("pdf_path_out", types="Str")],
    )
    def delete_pdf_pages(file_path: str = "", page_range: str = "", password: str = "", save_path: str = ""):
        """删除PDF指定页面，输出新文件路径"""

        reader = _open_pypdf(file_path, password)
        total = len(reader.pages)
        drop = set(parse_page_ranges(page_range, total))
        keep = [i for i in range(total) if i not in drop]
        if not keep:
            raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(page_range), "不能删除全部页面")
        out = save_path or _out_pdf_path(file_path, "deleted")
        return _write_pages(reader, keep, out)

    # ---------- 图片合成PDF ----------
    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("image_files", types="List"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("pdf_path_out", types="Str")],
    )
    def images_to_pdf(image_files="", save_path: str = ""):
        """将多张图片合并为一个PDF文件（每页一图，按EXIF自动纠正方向），输出PDF文件路径"""
        from PIL import Image

        if isinstance(image_files, str):
            files = [p.strip() for p in image_files.split(",") if p.strip()]
        elif isinstance(image_files, (list, tuple)):
            files = [str(p).strip() for p in image_files if str(p).strip()]
        else:
            files = []
        if not files:
            raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(str(image_files)), "图片列表不能为空")
        for p in files:
            if not os.path.isfile(p):
                raise BaseException(FILE_PATH_ERROR_FORMAT.format(p), "图片文件不存在")
        out = save_path or os.path.join(os.path.dirname(os.path.abspath(files[0])), "images_merged.pdf")
        parent = os.path.dirname(os.path.abspath(out))
        os.makedirs(parent, exist_ok=True)
        try:
            imgs = []
            for p in files:
                im = Image.open(p)
                if im.mode != "RGB":
                    im = im.convert("RGB")
                orientation = im.getexif().get(274)  # 274=Orientation
                if orientation == 6:
                    im = im.transpose(Image.ROTATE_270)
                elif orientation == 8:
                    im = im.transpose(Image.ROTATE_90)
                imgs.append(im)
            imgs[0].save(out, "PDF", save_all=True, append_images=imgs[1:])
            for im in imgs:
                im.close()
            return out
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_SAVE_ERROR_FORMAT.format(str(e)))

    # ---------- 水印 ----------
    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("text", types="Str"),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
            atomicMg.param("layout", required=False),
            atomicMg.param("font_size", types="Int", required=False),
            atomicMg.param("opacity", types="Int", required=False),
            atomicMg.param("rotation", types="Int", required=False),
            atomicMg.param("color", types="Str", required=False),
        ],
        outputList=[atomicMg.param("watermark_path", types="Str")],
    )
    def create_watermark_pdf(
        text: str = "",
        save_path: str = "",
        layout: WatermarkLayoutType = WatermarkLayoutType.TILE,
        font_size: int = 36,
        opacity: int = 20,
        rotation: int = 45,
        color: str = "#808080",
    ):
        """生成文字水印PDF文件（A4单页，平铺/居中，可调字号/透明度/旋转/颜色），输出路径（配合 添加PDF水印 使用）"""
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas

        if not text or not str(text).strip():
            raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(""), "水印文字不能为空")
        tile = (layout.value if isinstance(layout, WatermarkLayoutType) else str(layout or "tile")) != "single"
        font_size = max(6, int(font_size or 36))
        opacity = min(100, max(1, int(opacity or 20)))
        rotation = int(((int(rotation or 45) % 360) + 360) % 360)
        rgb = _parse_hex_color(color, (0.5, 0.5, 0.5))
        path = save_path or os.path.join(os.getcwd(), "astron", f"watermark_{int(time.time() * 1000)}.pdf")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))  # 内置CID中文字体
            c = canvas.Canvas(path, pagesize=(595.28, 841.89))  # A4
            w, h = 595.28, 841.89
            c.setFont("STSong-Light", font_size)
            c.setFillColorRGB(*rgb)
            c.setFillAlpha(opacity / 100.0)
            if tile:
                step_x = max(font_size * len(str(text)) * 0.6, 120)
                step_y = max(font_size * 3, 90)
                y = 0
                row = 0
                while y < h + step_y:
                    x = (row % 2) * (step_x / 2)
                    while x < w + step_x:
                        c.saveState()
                        c.translate(x, y)
                        c.rotate(rotation)
                        c.drawString(0, 0, str(text))
                        c.restoreState()
                        x += step_x
                    y += step_y
                    row += 1
            else:
                c.saveState()
                c.translate(w / 2, h / 2)
                c.rotate(rotation)
                tw = c.stringWidth(str(text), "STSong-Light", font_size)
                c.drawString(-tw / 2, -font_size / 2, str(text))
                c.restoreState()
            c.save()
            return path
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_SAVE_ERROR_FORMAT.format(str(e)))

    @staticmethod
    @atomicMg.atomic(
        "PDFExt",
        inputList=[
            atomicMg.param("file_path", types="Str"),
            atomicMg.param("watermark_path", types="Str"),
            atomicMg.param("password", types="Str", required=False),
            atomicMg.param(
                "save_path",
                types="Str",
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value, params={"filters": [], "file_type": "file"}
                ),
            ),
        ],
        outputList=[atomicMg.param("pdf_path_out", types="Str")],
    )
    def add_pdf_watermark(file_path: str = "", watermark_path: str = "", password: str = "", save_path: str = ""):
        """将水印PDF叠加到源PDF每一页（先水印后文档），输出新文件路径"""
        from pypdf import PdfWriter

        reader = _open_pypdf(file_path, password)
        wm_reader = _open_pypdf(watermark_path)
        if not wm_reader.pages:
            raise BaseException(INVALID_PARAMS_PDF_ERROR_FORMAT.format(watermark_path), "水印PDF无页面")
        try:
            wm_page = wm_reader.pages[0]
            writer = PdfWriter(clone_from=reader)
            for page in writer.pages:
                page.merge_page(wm_page)
            out = save_path or _out_pdf_path(file_path, "watermarked")
            parent = os.path.dirname(os.path.abspath(out))
            os.makedirs(parent, exist_ok=True)
            with open(out, "wb") as f:
                writer.write(f)
            return out
        except BaseException:
            raise
        except Exception as e:
            raise BaseException(PDF_SAVE_ERROR_FORMAT.format(str(e)))


def _extract_tables(file_path: str, password: str, page_range: str, strategy: str) -> list:
    """表格提取公共实现：strategy = text(间距) | lines(线)。"""
    settings = {"vertical_strategy": strategy, "horizontal_strategy": strategy}
    pdf = _open_plumber(file_path, password)
    try:
        total = len(pdf.pages)
        indices = parse_page_ranges(page_range, total)
        result = []
        for i in indices:
            try:
                tables = pdf.pages[i].extract_tables(settings)
            except Exception as e:
                raise BaseException(TABLE_EXTRACT_ERROR_FORMAT.format(f"第{i + 1}页: {e}"))
            result.extend([t if isinstance(t, list) else [list(row) for row in t] for t in (tables or [])])
        return result
    finally:
        pdf.close()
