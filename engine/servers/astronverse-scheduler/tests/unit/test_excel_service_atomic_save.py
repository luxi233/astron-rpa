"""ExcelService._atomic_save 原子替换(os.replace)的瞬时锁重试单元测试。

运行: cd engine/servers/astronverse-scheduler && .venv/bin/python -m unittest tests.unit.test_excel_service_atomic_save
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from astronverse.scheduler.core.datatable import excel_service
from openpyxl import Workbook


class TestAtomicSaveReplaceRetry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = os.path.realpath(tempfile.mkdtemp(prefix="dt_atomic_save_"))
        self.file_path = os.path.join(self.tmpdir, "t.xlsx")

    def tearDown(self):
        for name in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, name))
        os.rmdir(self.tmpdir)

    def _tmp_files(self):
        return [n for n in os.listdir(self.tmpdir) if n.endswith(".tmp")]

    def _new_wb_with_value(self, value):
        wb = Workbook()
        wb.active.cell(row=1, column=1, value=value)
        return wb

    def test_transient_lock_recovered(self):
        """前 2 次 replace 报 PermissionError(执行器写/读并发), 第 3 次成功"""
        real_replace = os.replace
        calls = {"n": 0}

        def flaky_replace(src, dst):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError(5, "Access is denied")
            return real_replace(src, dst)

        wb = self._new_wb_with_value("v1")
        with (
            mock.patch.object(excel_service.os, "replace", side_effect=flaky_replace),
            mock.patch.object(excel_service.time, "sleep") as sleep_mock,
        ):
            excel_service._atomic_save(wb, self.file_path)
        wb.close()

        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleep_mock.call_count, 2)
        self.assertEqual(self._tmp_files(), [])

    def test_persistent_lock_raises_and_cleans_tmp(self):
        """持久锁: 重试耗尽后抛出原始 PermissionError 并清理临时文件"""
        calls = {"n": 0}

        def locked_replace(src, dst):
            calls["n"] += 1
            raise PermissionError(5, "Access is denied")

        wb = self._new_wb_with_value("v2")
        with (
            mock.patch.object(excel_service.os, "replace", side_effect=locked_replace),
            mock.patch.object(excel_service.time, "sleep"),
        ):
            with self.assertRaises(PermissionError):
                excel_service._atomic_save(wb, self.file_path)
        wb.close()

        self.assertEqual(calls["n"], excel_service._REPLACE_RETRY_TIMES)
        self.assertEqual(self._tmp_files(), [])

    def test_save_via_service_roundtrip(self):
        """常规路径: 落盘成功且内容可读回, 无残留临时文件"""
        svc = excel_service.ExcelService(self.tmpdir)
        svc.write_file("t", {"sheets": [{"name": "Sheet1", "data": [["a", "b"], [1, 2]]}]})
        result = svc.read_file("t")
        self.assertEqual(result["sheets"][0]["data"], [["a", "b"], [1, 2]])
        self.assertEqual(self._tmp_files(), [])


if __name__ == "__main__":
    unittest.main()
