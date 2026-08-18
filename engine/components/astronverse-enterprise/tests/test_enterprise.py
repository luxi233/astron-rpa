import platform
import sys
import unittest
from unittest import TestCase

from astronverse.enterprise import Enterprise, ReportLevelType


class TestEnterprise(TestCase):
    @unittest.skip("print 能力已迁移至 Report 组件，Enterprise 无 print 方法")
    def test_print(self):
        enterprise = Enterprise()
        res = enterprise.print(print_type=ReportLevelType.INFO, print_msg="hello")
        if sys.platform == "win32":
            self.assertEqual(res, "[info] win hello")
        elif platform.system() == "Linux":
            self.assertEqual(res, "[info] linux hello")

    @unittest.skipIf(sys.platform != "win32", "依赖 Windows 路径与网关服务，macOS 跳过")
    def test_shareholder_upload(self):
        enterprise = Enterprise()
        enterprise.upload_to_sharefolder(r"D:\new-rpa2\data\logs\rpa_browser_connector-2025-08-21.log")

    @unittest.skipIf(sys.platform != "win32", "依赖 Windows 路径与网关服务，macOS 跳过")
    def test_shareholder_download(self):
        enterprise = Enterprise()
        enterprise.download_from_sharefolder(file_path=1958825462281179136, save_folder=r"D:\new-rpa2\data")
