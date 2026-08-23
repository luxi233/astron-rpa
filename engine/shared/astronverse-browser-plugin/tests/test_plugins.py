import os
import sys
from unittest import TestCase

import pytest

# 真机手动冒烟脚本(无断言, install() 会真实安装浏览器插件并写注册表):
# 仅 Windows 且手动执行才有意义, 自动化测试默认整体跳过;
# utils.py 顶层 import winreg, 非 Windows 收集期即 ImportError, 须在 import 之前跳过
if sys.platform != "win32" or os.environ.get("PLUGIN_SMOKE") != "1":
    pytest.skip("真机插件安装冒烟测试, 仅 Windows 手动执行(PLUGIN_SMOKE=1)", allow_module_level=True)

from astronverse.browser_plugin import BrowserType  # noqa: E402
from astronverse.browser_plugin.browser import ExtensionManager, UpdateManager  # noqa: E402


class TestPlugins(TestCase):

    # install plugin
    def test_install_360x(self):
        extension_manager = ExtensionManager(browser_type=BrowserType.BROWSER_360X)
        extension_manager.install()
        
    def test_install_edge(self):
        extension_manager = ExtensionManager(browser_type=BrowserType.MICROSOFT_EDGE)
        extension_manager.install()
        
    def test_install_chrome(self):
        extension_manager = ExtensionManager(browser_type=BrowserType.CHROME)
        extension_manager.install()
        
    def test_install_firefox(self):
        extension_manager = ExtensionManager(browser_type=BrowserType.FIREFOX)
        extension_manager.install()
    
    def test_install_360(self):
        extension_manager = ExtensionManager(browser_type=BrowserType.BROWSER_360)
        extension_manager.install()
    
    # check status 
    def test_check_360x_status(self):
        status = ExtensionManager(browser_type=BrowserType.BROWSER_360X).check_status()
        print(f"Plugin status: {status}")
    
    def test_check_edge_status(self):
        status = ExtensionManager(browser_type=BrowserType.MICROSOFT_EDGE).check_status()
        print(f"Plugin status: {status}")
    
    def test_check_chrome_status(self):
        status = ExtensionManager(browser_type=BrowserType.CHROME).check_status()
        print(f"Plugin status: {status}")
        
    def test_check_firefox_status(self):
        status = ExtensionManager(browser_type=BrowserType.FIREFOX).check_status()
        print(f"Plugin status: {status}")
        
    def test_check_360_status(self):
        status = ExtensionManager(browser_type=BrowserType.BROWSER_360).check_status()
        print(f"Plugin status: {status}")
    
    # update installed plugins
    def test_install_update(self):
        UpdateManager().update_installed_plugins()
    
    # get support browsers
    def test_get_support_browsers(self):
        browsers = UpdateManager().support_browsers
        print(f"Support browsers: {browsers}")

    def test_get_360_browser_path(self):
        from astronverse.browser_plugin.win.browser_360 import Browser360PluginManager
        b360 = Browser360PluginManager({})
        print(f"Browser : {b360.preferences_path_list}")