import os
import sys
import time

from astronverse.actionlib.atomic import atomicMg
from astronverse.datatable import ExcelOpenType, PivotFilterType, PivotValueFunc
from astronverse.datatable.error import *

# XlConsolidationFunction 枚举常量(数据透视表值字段的汇总函数)
# 数值来源: Microsoft Learn 官方文档 XlConsolidationFunction enumeration (Excel)
# https://learn.microsoft.com/en-gb/dotnet/api/microsoft.office.interop.excel.xlconsolidationfunction
# xlSum=-4157(求和), xlCount=-4112(计数), xlAverage=-4106(平均值), xlMax=-4136(最大值), xlMin=-4139(最小值)
PIVOT_FUNC = {
    PivotValueFunc.SUM.value: -4157,  # xlSum
    PivotValueFunc.COUNT.value: -4112,  # xlCount
    PivotValueFunc.AVERAGE.value: -4106,  # xlAverage
    PivotValueFunc.MAX.value: -4136,  # xlMax
    PivotValueFunc.MIN.value: -4139,  # xlMin
}

# 汇总方式中文名(数据字段标题后缀)
PIVOT_FUNC_CN = {
    PivotValueFunc.SUM.value: "求和",
    PivotValueFunc.COUNT.value: "计数",
    PivotValueFunc.AVERAGE.value: "平均值",
    PivotValueFunc.MAX.value: "最大值",
    PivotValueFunc.MIN.value: "最小值",
}

# COM ProgID 候选: Excel -> WPS表格(Ket) -> WPS表格(et)
_EXCEL_PROG_IDS = ("Excel.Application", "Ket.Application", "et.Application")

# 句柄注册表: {句柄名: {'app': com应用对象, 'created': 是否本进程创建}}
_handles: dict[str, dict] = {}
_counter = 0


def _next_handle() -> str:
    """自增生成句柄名, 如 excel_obj_1"""
    global _counter
    _counter += 1
    return f"excel_obj_{_counter}"


def _load_com():
    """懒加载 win32com 与 pythoncom, 仅 Windows 可用"""
    if sys.platform != "win32":
        raise DATAFRAME_EXPECTION(
            PARAMS_ERROR.format("Excel应用驱动仅支持Windows，且需安装Excel或WPS及pywin32"), "平台不支持"
        )
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        raise DATAFRAME_EXPECTION(
            PARAMS_ERROR.format("Excel应用驱动仅支持Windows，且需安装Excel或WPS及pywin32"), "平台不支持"
        )
    return pythoncom, win32com.client


def _get_app(excel_obj: str):
    """根据句柄取 COM 应用对象"""
    if not excel_obj or excel_obj not in _handles:
        raise DATAFRAME_EXPECTION(
            PARAMS_ERROR.format("Excel对象不存在或已关闭，请先执行打开Excel或获取当前激活的Excel对象"),
            "Excel对象不存在",
        )
    return _handles[excel_obj]["app"]


def _to_enum(value, enum_cls):
    """将参数规范化为枚举成员(兼容直接传枚举值字符串)"""
    if isinstance(value, enum_cls):
        return value
    return enum_cls(value)


def _sheet_exists(wb, sheet_name: str) -> bool:
    """检查工作簿中是否存在指定名称的工作表"""
    for ws in wb.Worksheets:
        if ws.Name == sheet_name:
            return True
    return False


def _resolve_sheet(app, sheet_name: str):
    """定位工作表: 名称空则用当前活动表, 不存在则抛错"""
    if not sheet_name:
        return app.ActiveSheet
    wb = app.ActiveWorkbook
    if not _sheet_exists(wb, sheet_name):
        raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"Sheet页不存在: {sheet_name}"), "Sheet页不存在")
    return wb.Worksheets(sheet_name)


def _iter_pivot_tables(wb, sheet_name: str = "", pivot_name: str = ""):
    """遍历数据透视表: sheet_name空遍历所有工作表, pivot_name空匹配该表全部透视表"""
    for ws in wb.Worksheets:
        if sheet_name and ws.Name != sheet_name:
            continue
        if not _sheet_exists(wb, ws.Name):
            continue
        for pt in ws.PivotTables():
            if pivot_name and pt.Name != pivot_name:
                continue
            yield pt


def _convert_macro_arg(raw: str):
    """宏参数类型转换: 数值尝试转int/float, 其余原样字符串"""
    raw = raw.strip()
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


class ExcelApp:
    """Excel应用(真实Excel/WPS表格COM驱动, 仅Windows可运行)"""

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[
            atomicMg.param("excel_obj", types="Str", required=True),
            atomicMg.param("file_path", required=False),
            atomicMg.param("open_type"),
            atomicMg.param("password", required=False),
            atomicMg.param("is_visible"),
        ],
        outputList=[atomicMg.param("excel_obj", types="Str")],
    )
    def open_or_create_excel(
        file_path: str = "",
        open_type: ExcelOpenType = ExcelOpenType.OPEN,
        password: str = "",
        is_visible: bool = True,
    ):
        """
        打开或新建Excel/WPS表格应用
        """
        pythoncom, client = _load_com()
        open_type = _to_enum(open_type, ExcelOpenType)
        app = None
        for prog_id in _EXCEL_PROG_IDS:
            try:
                app = client.DispatchEx(prog_id)
                break
            except Exception:
                continue
        if app is None:
            raise DATAFRAME_EXPECTION(
                PARAMS_ERROR.format("未检测到Excel或WPS，请先安装Excel或WPS表格"), "未检测到Excel或WPS"
            )
        try:
            app.Visible = bool(is_visible)
            app.DisplayAlerts = False
            if open_type == ExcelOpenType.NEW:
                app.Workbooks.Add()
                if file_path:
                    save_kwargs = {}
                    if password:
                        save_kwargs["Password"] = password
                    app.ActiveWorkbook.SaveAs(os.path.abspath(file_path), **save_kwargs)
            else:
                if not file_path:
                    raise DATAFRAME_EXPECTION(
                        PARAMS_ERROR.format("打开已有Excel时文件路径不能为空"), "文件路径不能为空"
                    )
                app.Workbooks.Open(Filename=os.path.abspath(file_path), Password=password)
        except DATAFRAME_EXPECTION:
            raise
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")
        handle = _next_handle()
        _handles[handle] = {"app": app, "created": True}
        return handle

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[],
        outputList=[atomicMg.param("excel_obj", types="Str")],
    )
    def get_active_excel():
        """
        获取当前正在运行的Excel/WPS表格应用
        """
        pythoncom, client = _load_com()
        app = None
        for prog_id in _EXCEL_PROG_IDS:
            try:
                app = client.GetActiveObject(prog_id)
                break
            except Exception:
                continue
        if app is None:
            raise DATAFRAME_EXPECTION(
                PARAMS_ERROR.format("当前没有正在运行的Excel/WPS，请先打开Excel或WPS表格"), "没有正在运行的Excel/WPS"
            )
        handle = _next_handle()
        _handles[handle] = {"app": app, "created": False}
        return handle

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[
            atomicMg.param("excel_obj", types="Str", required=True),
            atomicMg.param("is_save"),
        ],
        outputList=[],
    )
    def close_excel(excel_obj: str = "", is_save: bool = True):
        """
        关闭Excel/WPS表格应用
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        try:
            if is_save and app.Workbooks.Count > 0:
                try:
                    app.ActiveWorkbook.Save()
                except Exception:
                    pass  # 无可保存的工作簿时跳过
            app.Quit()
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")
        finally:
            _handles.pop(excel_obj, None)

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[
            atomicMg.param("excel_obj", types="Str", required=True),
            atomicMg.param("sheet_name", required=False),
            atomicMg.param("range_str", required=True),
        ],
        outputList=[],
    )
    def select_range(excel_obj: str = "", sheet_name: str = "", range_str: str = "A1"):
        """
        选中Excel中的单元格区域
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        if not range_str:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("单元格区域不能为空，例如A1:C10"), "区域不能为空")
        try:
            ws = _resolve_sheet(app, sheet_name)
            ws.Activate()
            ws.Range(range_str).Select()
        except DATAFRAME_EXPECTION:
            raise
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[atomicMg.param("excel_obj", types="Str", required=True)],
        outputList=[
            atomicMg.param("selected_range", types="Str"),
            atomicMg.param("selected_sheet", types="Str"),
        ],
    )
    def get_selected_range(excel_obj: str = ""):
        """
        获取Excel中当前选中的区域
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        try:
            selected_range = app.Selection.Address
            selected_sheet = app.ActiveSheet.Name
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")
        return selected_range, selected_sheet

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[
            atomicMg.param("excel_obj", types="Str", required=True),
            atomicMg.param("macro_name", required=True),
            atomicMg.param("macro_args", required=False),
        ],
        outputList=[],
    )
    def run_excel_macro(excel_obj: str = "", macro_name: str = "", macro_args: str = ""):
        """
        运行Excel中的宏
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        if not macro_name:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("宏名称不能为空"), "宏名称不能为空")
        args = [_convert_macro_arg(arg) for arg in macro_args.split(",")] if macro_args else []
        try:
            app.Run(macro_name, *args)
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[atomicMg.param("excel_obj", types="Str", required=True)],
        outputList=[],
    )
    def refresh_excel_data(excel_obj: str = ""):
        """
        刷新Excel当前工作簿的全部数据连接
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        try:
            app.ActiveWorkbook.RefreshAll()
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[
            atomicMg.param("excel_obj", types="Str", required=True),
            atomicMg.param("source_range", required=True),
            atomicMg.param("sheet_name", required=False),
            atomicMg.param("dest_sheet_name"),
            atomicMg.param("dest_cell"),
            atomicMg.param("row_fields", required=False),
            atomicMg.param("col_fields", required=False),
            atomicMg.param("value_fields", required=True),
            atomicMg.param("value_func"),
        ],
        outputList=[atomicMg.param("pivot_name", types="Str")],
    )
    def create_pivot_table(
        excel_obj: str = "",
        source_range: str = "A1:C10",
        sheet_name: str = "",
        dest_sheet_name: str = "数据透视表",
        dest_cell: str = "A3",
        row_fields: str = "",
        col_fields: str = "",
        value_fields: str = "",
        value_func: PivotValueFunc = PivotValueFunc.SUM,
    ):
        """
        在Excel中创建数据透视表
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        value_func = _to_enum(value_func, PivotValueFunc)
        if not source_range:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("源数据区域不能为空，例如A1:C10"), "源数据区域不能为空")
        if not value_fields:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("值字段不能为空，多个字段用逗号分隔"), "值字段不能为空")
        try:
            wb = app.ActiveWorkbook
            # 源区域支持 'A1:C10' 或 'Sheet1!A1:C10'
            if "!" in source_range:
                src_sheet_name, area = source_range.split("!", 1)
            else:
                src_sheet_name, area = sheet_name, source_range
            src_ws = _resolve_sheet(app, src_sheet_name)
            src_range = src_ws.Range(area)

            # PivotCache: SourceType=1 即 xlDatabase(数据库来源), 参考 Microsoft Learn XlSourceType
            pc = wb.PivotCaches().Create(SourceType=1, SourceData=src_range)

            # 目标工作表不存在则新建, 存在则复用
            if _sheet_exists(wb, dest_sheet_name):
                dest_ws = wb.Worksheets(dest_sheet_name)
            else:
                dest_ws = wb.Worksheets.Add(After=wb.Worksheets(wb.Worksheets.Count))
                dest_ws.Name = dest_sheet_name
            dest_ws.Activate()
            dest = dest_ws.Range(dest_cell)

            table_name = f"透视表{str(int(time.time()))[-4:]}"
            pt = pc.CreatePivotTable(TableDestination=dest, TableName=table_name)

            # 字段方向常量: xlRowField=1(行字段), xlColumnField=2(列字段), 参考 Microsoft Learn Xl PivotFieldOrientation
            for field in filter(None, [f.strip() for f in row_fields.split(",")]):
                pt.PivotFields(field).Orientation = 1  # xlRowField
            for field in filter(None, [f.strip() for f in col_fields.split(",")]):
                pt.PivotFields(field).Orientation = 2  # xlColumnField

            # 值字段: xlDataField=4, 汇总函数取 XlConsolidationFunction 常量(见 PIVOT_FUNC)
            func_name = PIVOT_FUNC_CN[value_func.value]
            for field in filter(None, [f.strip() for f in value_fields.split(",")]):
                data_field = pt.AddDataField(pt.PivotFields(field), f"{field}{func_name}")
                data_field.Function = PIVOT_FUNC[value_func.value]
            return pt.Name
        except DATAFRAME_EXPECTION:
            raise
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[
            atomicMg.param("excel_obj", types="Str", required=True),
            atomicMg.param("sheet_name", required=False),
            atomicMg.param("pivot_name", required=False),
        ],
        outputList=[],
    )
    def refresh_pivot_table(excel_obj: str = "", sheet_name: str = "", pivot_name: str = ""):
        """
        刷新Excel中的数据透视表
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        try:
            wb = app.ActiveWorkbook
            refreshed = 0
            for pt in _iter_pivot_tables(wb, sheet_name, pivot_name):
                pt.RefreshTable()
                refreshed += 1
            if refreshed == 0:
                raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("未找到指定的数据透视表"), "数据透视表不存在")
        except DATAFRAME_EXPECTION:
            raise
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")

    @staticmethod
    @atomicMg.atomic(
        "ExcelApp",
        inputList=[
            atomicMg.param("excel_obj", types="Str", required=True),
            atomicMg.param("sheet_name", required=False),
            atomicMg.param("pivot_name", required=False),
            atomicMg.param("field_name", required=True),
            atomicMg.param("filter_value", required=True),
            atomicMg.param("filter_type"),
        ],
        outputList=[],
    )
    def filter_pivot_table(
        excel_obj: str = "",
        sheet_name: str = "",
        pivot_name: str = "",
        field_name: str = "",
        filter_value: str = "",
        filter_type: PivotFilterType = PivotFilterType.INCLUDE,
    ):
        """
        筛选Excel数据透视表的字段项
        """
        app = _get_app(excel_obj)
        pythoncom, _ = _load_com()
        filter_type = _to_enum(filter_type, PivotFilterType)
        if not field_name:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("筛选字段名不能为空"), "字段名不能为空")
        if not filter_value:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("筛选值不能为空"), "筛选值不能为空")
        try:
            wb = app.ActiveWorkbook
            pt = next(_iter_pivot_tables(wb, sheet_name, pivot_name), None)
            if pt is None:
                raise DATAFRAME_EXPECTION(PARAMS_ERROR.format("未找到指定的数据透视表"), "数据透视表不存在")

            pf = None
            for field in pt.PivotFields():
                if field.Name == field_name:
                    pf = field
                    break
            if pf is None:
                raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"透视表字段不存在: {field_name}"), "字段不存在")

            if pf.Orientation == 3:  # xlPageField=3(筛选页字段), 直接设置当前页
                pf.CurrentPage = filter_value
            else:
                include = filter_type == PivotFilterType.INCLUDE
                targets = []
                for item in pf.PivotItems():
                    matched = item.Name == filter_value
                    targets.append((item, matched if include else not matched))
                if targets and not any(visible for _, visible in targets):
                    raise DATAFRAME_EXPECTION(
                        PARAMS_ERROR.format("不能隐藏所有项，至少保留一个可见项"), "不能隐藏所有项"
                    )
                for item, visible in targets:
                    item.Visible = visible
        except DATAFRAME_EXPECTION:
            raise
        except pythoncom.com_error as e:
            raise DATAFRAME_EXPECTION(PARAMS_ERROR.format(f"COM操作失败: {e}"), "Excel应用操作失败")
