# -*- coding: utf-8 -*-
"""P0-6 CSV分隔符冒烟(datatable组件)"""

import sys
import os
import tempfile

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-datatable/src")

from astronverse.datatable import datatable as dt_mod
from astronverse.datatable.datatable import DataTable
from astronverse.datatable import ExportFileType, ReadType

PyxlWrapper = dt_mod.PyxlWrapper

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


workdir = tempfile.mkdtemp()
semi_csv = os.path.join(workdir, "semi.csv")
with open(semi_csv, "w", encoding="utf-8") as f:
    f.write("a;b;c\n1;2;3\n4;5;6\n")

ensure_xlsx = None  # datatable模块导入时已自动初始化
PyxlWrapper.sheet.delete_rows(1, PyxlWrapper.sheet.max_row)
DataTable.import_data_table_from_file(import_file_path=semi_csv, csv_delimiter=";")
vals = DataTable.read_data(read_type=ReadType.AREA, start_row=1, start_col="A", end_row=3, end_col="C")
check("csv import semicolon", vals == [["a", "b", "c"], ["1", "2", "3"], ["4", "5", "6"]], vals)

out = DataTable.export_data_table_to_file(
    export_dest_path=workdir, export_file_name="tab_out", export_file_type=ExportFileType.CSV, csv_delimiter="\\t"
)
content = open(out, encoding="utf-8").read()
check("csv export tab", "a\tb\tc" in content and "1\t2\t3" in content, content[:80])

out2 = DataTable.export_data_table_to_file(
    export_dest_path=workdir, export_file_name="semi_out", export_file_type=ExportFileType.CSV, csv_delimiter=";"
)
content2 = open(out2, encoding="utf-8").read()
check("csv export semicolon", "a;b;c" in content2, content2[:80])

try:
    DataTable.export_data_table_to_file(
        export_dest_path=workdir, export_file_name="bad", export_file_type=ExportFileType.CSV, csv_delimiter=";;"
    )
    check("csv delimiter invalid raises", False)
except BaseException:
    check("csv delimiter invalid raises", True)

# 默认逗号不受影响
out3 = DataTable.export_data_table_to_file(
    export_dest_path=workdir, export_file_name="def_out", export_file_type=ExportFileType.CSV
)
content3 = open(out3, encoding="utf-8").read()
check("csv default comma", "a,b,c" in content3, content3[:80])

print(f"\n=== {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
