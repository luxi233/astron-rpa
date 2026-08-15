import base64
import os
import sys
import threading
import time
from ast import literal_eval
import requests
from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, AtomicLevel, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.types import PATH, URL, WebPick
from astronverse.browser import *
from astronverse.browser.browser import Browser
from astronverse.browser.core.core_win import BrowserCore
from astronverse.browser.error import *
from astronverse.software.software import Software
from astronverse.browser.core.launcher import BrowserLauncher


def _copy_image_to_clipboard(image_path: str):
    """将图片文件复制到系统剪贴板"""
    if not os.path.exists(image_path):
        raise BaseException(BROWSER_EXTENSION_ERROR_FORMAT.format(f"图片文件不存在: {image_path}"), "图片文件不存在")
    if sys.platform == "win32":
        import io

        import win32clipboard
        from PIL import Image

        with Image.open(image_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            with io.BytesIO() as output:
                img.save(output, "BMP")
                bmp_data = output.getvalue()
        # BMP 文件头 14 字节，CF_DIB 不含文件头
        dib = bmp_data[14:]
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
        finally:
            win32clipboard.CloseClipboard()
    elif sys.platform == "darwin":
        import subprocess

        script = f'set the clipboard to (read (POSIX file "{image_path}") as JPEG picture)'
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise BaseException(
                BROWSER_EXTENSION_ERROR_FORMAT.format(f"复制图片到剪贴板失败: {result.stderr}"),
                "复制图片到剪贴板失败",
            )
    else:
        raise BaseException(
            BROWSER_EXTENSION_ERROR_FORMAT.format("当前系统不支持复制图片到剪贴板"),
            "当前系统不支持复制图片到剪贴板",
        )


class BrowserSoftware:
    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("wait_load_success", level=AtomicLevel.NORMAL, required=False),
            atomicMg.param(
                "browser_abs_path",
                level=AtomicLevel.NORMAL,
                required=False,
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"file_type": "file"},
                ),
            ),
            atomicMg.param("open_args", level=AtomicLevel.ADVANCED, required=False),
            atomicMg.param(
                "open_with_incognito",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                level=AtomicLevel.ADVANCED,
                required=False,
            ),
            atomicMg.param(
                "timeout",
                level=AtomicLevel.NORMAL,
                dynamics=[
                    DynamicsItem(
                        key="$this.timeout.show",
                        expression="return $this.wait_load_success.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "timeout_handle_type",
                level=AtomicLevel.NORMAL,
                dynamics=[
                    DynamicsItem(
                        key="$this.timeout_handle_type.show",
                        expression="return $this.wait_load_success.value == true",
                    )
                ],
            ),
        ],
        outputList=[
            atomicMg.param("web_open", types="Browser"),
        ],
    )
    def browser_open(
        url: URL,
        browser_type: CommonForBrowserType = CommonForBrowserType.BTChrome,
        browser_abs_path: PATH = "",
        open_args: str = "",
        open_with_incognito: bool = False,
        wait_load_success: bool = True,
        timeout: int = 20,
        timeout_handle_type: CommonForTimeoutHandleType = CommonForTimeoutHandleType.ExecError,
    ) -> Browser:
        start_time = time.time()

        # 检查browser_abs_path是否合法
        if browser_abs_path and sys.platform == "win32":
            app_exe = os.path.basename(browser_abs_path)
            software_tag = BROWSER_SOFTWARE_TAG.get(browser_type.value, None)
            if not (software_tag and software_tag.lower() in app_exe.lower()):
                raise BaseException(SELECT_MATCHING_APP_PATH.format(app_exe.lower()), "请选择跟浏览器匹配的应用路径")

        # 检查browser_abs_path的路径
        if not browser_abs_path:
            browser_abs_path = BrowserCore.get_browser_path(browser_type.value)
            if not browser_abs_path:
                raise BaseException(BROWSER_PATH_EMPTY, "注册表中未找到浏览器路径{}".format(browser_type))

        # 内置浏览器加载插件
        if browser_type == CommonForBrowserType.BTChromium:
            extension_path = (
                f"{os.getcwd()}/python_core/Lib/site-packages/astronverse/browser_plugin/plugins/chromium-extension"
            )
            extension_path = extension_path.replace("/", os.sep)
            open_args += f" --load-extension='{extension_path}'"

        # 默认新窗口
        if "--new-window" not in open_args:
            open_args += " --new-window"

        # 使用隐身模式
        if open_with_incognito:
            incognito_arg = BROWSER_PRIVATE_MAP.get(browser_type.value, "")
            if incognito_arg:
                open_args += f" --{incognito_arg}"

        # 打开浏览器
        is_open = True
        control = BrowserCore.get_browser_control(browser_type.value)
        if not control:
            is_open = False
            BrowserLauncher.open(browser_abs_path, str(url), open_args)

            open_timeout = timeout / 2
            while open_timeout >= 0:
                time.sleep(1)
                open_timeout -= 1
                control = BrowserCore.get_browser_control(browser_type.value)
                if control:
                    break
            if not control:
                raise BaseException(BROWSER_OPEN_TIMEOUT, "打开浏览器超时")

        try:
            # 置顶最大化
            BrowserCore.browser_top_and_max(control)
        except Exception as e:
            pass

        res = Browser()
        res.browser_type = browser_type
        res.browser_abs_path = browser_abs_path
        res.browser_control = control

        # 插件通信连接，打开Tab
        retry_count = 3
        retry_time = timeout / 2 / retry_count
        web_open_err = None
        while retry_count > 0:
            try:
                if is_open:
                    res.send_browser_extension(
                        browser_type=res.browser_type.value, key="openNewTab", data={"url": str(url)}
                    )
                    web_open_err = None
                    break
                else:
                    res.send_browser_extension(
                        browser_type=res.browser_type.value,
                        key="updateTab",
                        data={"url": str(url)},
                    )
                    web_open_err = None
                    break
            except Exception as e:
                web_open_err = e
                time.sleep(retry_time)
            finally:
                retry_count -= 1
        if web_open_err:
            raise web_open_err

        # 插件置顶最大化
        BrowserSoftware.browser_max_window(res)

        try:
            # 插件通信连接，等待网页加载完成
            elapsed = time.time() - start_time - timeout

            if wait_load_success:
                result = BrowserSoftware.wait_web_load(browser_obj=res, timeout=(5 if elapsed < 5 else elapsed))
                if not result and timeout_handle_type == CommonForTimeoutHandleType.ExecError:
                    BrowserSoftware.stop_web_load(browser_obj=res)
        except Exception as e:
            pass

        return res

    @staticmethod
    @atomicMg.atomic("BrowserSoftware")
    def browser_close(browser_obj: Browser):
        """
        close 关闭浏览器
        """
        if not browser_obj.browser_abs_path:
            browser_obj.browser_abs_path = BrowserCore.get_browser_path(browser_obj.browser_type.value)
        Software.close(browser_obj.browser_abs_path)

    @staticmethod
    def browser_max_window(browser_obj: Browser) -> bool:
        """最大化浏览器窗口"""
        try:
            browser_obj.send_browser_extension(browser_type=browser_obj.browser_type.value, key="maxWindow")
        except Exception:
            return False
        return True

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("cookie_path", required=False),
        ],
        outputList=[
            atomicMg.param("cookie_input", types="Str"),
        ],
    )
    def set_cookies(
        browser_obj: Browser,
        url: URL,
        cookie_name: str,
        cookie_val: str,
        cookie_path: str = "",
        page_timeout: float = 10,
    ):
        """
        设置cookies
        """
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="setCookies",
            data={
                "url": str(url),
                "name": cookie_name,
                "value": cookie_val,
                "path": cookie_path,
            },
            timeout=page_timeout,
        )
        return cookie_val

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("cookie_path", required=False),
        ],
        outputList=[
            atomicMg.param("get_cookie", types="Str"),
        ],
    )
    def get_cookies(
        browser_obj: Browser, url: URL, cookie_name: str, cookie_path: str = "", page_timeout: float = 10
    ) -> str:
        """
        获取cookies
        """
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getCookie",
            data={
                "url": str(url),
                "name": cookie_name,
                "path": cookie_path,
            },
            timeout=page_timeout,
        )
        if isinstance(data, list):
            result = str(data)
        elif isinstance(data, dict):
            result = data.get("value", "")
        else:
            result = ""
        return result

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("cookie_path", required=False),
        ],
        outputList=[],
    )
    def empty_cookies(
        browser_obj: Browser,
        url: URL,
        cookie_path: str = "",
        page_timeout: float = 10,
    ):
        """
        清空cookies
        """
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="emptyCookies",
            data={
                "url": str(url),
                "path": cookie_path,
            },
            timeout=page_timeout,
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("web_new_page", types="Browser"),
        ],
    )
    def web_open(browser_obj: Browser, new_tab_url: URL = "", wait_page: bool = True) -> "Browser":
        """打开新网页"""
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="openNewTab",
            data={"url": str(new_tab_url)},
        )
        if wait_page:
            BrowserSoftware.wait_web_load(browser_obj=browser_obj, timeout=20)
        return browser_obj

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param(
                "tab_url",
                dynamics=[
                    DynamicsItem(
                        key="$this.tab_url.show",
                        expression=f"return $this.switch_type.value == '{WebSwitchType.URL.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "tab_title",
                dynamics=[
                    DynamicsItem(
                        key="$this.tab_title.show",
                        expression=f"return $this.switch_type.value == '{WebSwitchType.TITLE.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "tab_id",
                types="Int",
                dynamics=[
                    DynamicsItem(
                        key="$this.tab_id.show",
                        expression=f"return $this.switch_type.value == '{WebSwitchType.TabId.value}'",
                    )
                ],
            ),
        ],
    )
    def web_switch(
        browser_obj: Browser,
        switch_type: WebSwitchType = WebSwitchType.URL,
        tab_url: str = "",
        tab_title: str = "",
        tab_id: int = 0,
    ):
        """切换网页"""
        if switch_type == WebSwitchType.URL:
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="switchTab",
                data={"url": tab_url},
            )
        elif switch_type == WebSwitchType.TabId:
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="switchTab",
                data={"id": tab_id},
            )
        else:
            browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="switchTab",
                data={"title": tab_title},
            )
        return tab_url if switch_type == WebSwitchType.URL else tab_title

    @staticmethod
    @atomicMg.atomic("BrowserSoftware")
    def wait_web_load(browser_obj: Browser, timeout: float = 20) -> bool:
        """
        等待页面加载完成，直到超时或页面加载完成。
        """
        if timeout < 0:
            raise BaseException(
                PARAMETER_INVALID_FORMAT.format(timeout),
                f"等待时间不能小于0！{timeout}",
            )

        end = time.time() + timeout
        while time.time() < end:
            try:
                data = browser_obj.send_browser_extension(
                    browser_type=browser_obj.browser_type.value, key="loadComplete"
                )
                if data:
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    @staticmethod
    @atomicMg.atomic("BrowserSoftware")
    def stop_web_load(browser_obj: Browser):
        """
        停止加载网页
        """
        browser_obj.send_browser_extension(browser_type=browser_obj.browser_type.value, key="stopLoad")

    @staticmethod
    @atomicMg.atomic("BrowserSoftware")
    def web_refresh(browser_obj: Browser):
        """
        刷新网页
        """
        browser_obj.send_browser_extension(browser_type=browser_obj.browser_type.value, key="reloadTab")

    @staticmethod
    @atomicMg.atomic("BrowserSoftware", inputList=[atomicMg.param("url", required=False)])
    def web_close(browser_obj: Browser, url: str = ""):
        """
        关闭网页
        """
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="closeTab",
            data={"url": url},
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param(
                "image_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "save_to_clipboard",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
            ),
        ],
        outputList=[
            atomicMg.param("web_screen", types="Str"),
        ],
    )
    def screenshot(
        browser_obj: Browser,
        shot_range: ScreenShotForShotRangeFlag = ScreenShotForShotRangeFlag.Visual,
        image_path: str = "",
        image_name: str = "",
        page_timeout: float = 10,
        save_to_clipboard: bool = False,
    ) -> str:
        """截图网页"""
        if not image_name.endswith((".png", ".jpg", ".jpeg")):
            image_name += ".jpg"
        dest_path = os.path.join(image_path, image_name)
        if shot_range == ScreenShotForShotRangeFlag.Visual:
            data = browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="captureScreen",
                data={"": ""},
                timeout=page_timeout,
            )
        elif shot_range == ScreenShotForShotRangeFlag.All:
            data = browser_obj.send_browser_extension(
                browser_type=browser_obj.browser_type.value,
                key="capturePage",
                data={"": ""},
                timeout=page_timeout,
            )
        else:
            raise NotImplementedError()
        if data:
            data = data.replace("data:image/jpeg;base64,", "")
        else:
            raise Exception("插件返回数据为空")
        with open(dest_path, "wb") as f:
            f.write(base64.b64decode(data))
        if save_to_clipboard:
            _copy_image_to_clipboard(dest_path)
        return dest_path

    @staticmethod
    @atomicMg.atomic("BrowserSoftware")
    def browser_forward(
        browser_obj: Browser,
    ):
        """前进网页"""
        browser_obj.send_browser_extension(browser_type=browser_obj.browser_type.value, key="forward")

    @staticmethod
    @atomicMg.atomic("BrowserSoftware")
    def browser_back(
        browser_obj: Browser,
    ):
        """后退网页"""
        browser_obj.send_browser_extension(browser_type=browser_obj.browser_type.value, key="backward")

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("browser_obj", types="Browser"),
        ],
    )
    def get_current_obj(
        browser_type: CommonForBrowserType = CommonForBrowserType.BTChrome,
    ) -> Browser:
        """获取当前浏览器对象"""

        control = None
        open_timeout = 10
        while open_timeout >= 0:
            control = BrowserCore.get_browser_control(browser_type.value)
            if control:
                break
            time.sleep(1)
            open_timeout -= 1
        if not control:
            raise BaseException(BROWSER_OPEN_TIMEOUT, "打开浏览器超时")

        try:
            # 置顶最大化
            BrowserCore.browser_top_and_max(control)
        except Exception as e:
            pass

        browser = Browser()
        browser.browser_type = browser_type
        browser.browser_abs_path = ""
        browser.browser_control = control
        return browser

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("get_url", types="Str"),
        ],
    )
    def get_current_url(browser_obj: Browser) -> str:
        """获取当前网页地址"""
        return browser_obj.get_url()

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("get_page_title", types="Str"),
        ],
    )
    def get_current_title(browser_obj: Browser) -> str:
        """获取当前网页标题"""
        return browser_obj.get_title()

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("get_tab_id", types="Int"),
        ],
    )
    def get_current_tab_id(browser_obj: Browser) -> int:
        """获取当前网页tabid"""
        return browser_obj.get_tabid()

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("custom_flag", required=False),
            atomicMg.param(
                "save_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"file_type": "folder"},
                ),
            ),
            atomicMg.param(
                "simulate_flag",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.simulate_flag.show",
                        expression=f"return $this.download_mode.value == '{DownloadModeForFlag.Click.value}'",
                    )
                ],
            ),
            atomicMg.param("is_wait", required=False),
            atomicMg.param(
                "time_out",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.time_out.show",
                        expression="return $this.is_wait.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "element_data",
                dynamics=[
                    DynamicsItem(
                        key="$this.element_data.show",
                        expression=f"return $this.download_mode.value == '{DownloadModeForFlag.Click.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "link_str",
                dynamics=[
                    DynamicsItem(
                        key="$this.link_str.show",
                        expression=f"return $this.download_mode.value == '{DownloadModeForFlag.Link.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "file_name",
                dynamics=[
                    DynamicsItem(
                        key="$this.file_name.show",
                        expression="return $this.custom_flag.value == true",
                    )
                ],
            ),
        ],
        outputList=[
            atomicMg.param("load_file", types="Str"),
        ],
    )
    def download_web_file(
        browser_obj: Browser,
        element_data: WebPick,
        download_mode: DownloadModeForFlag = DownloadModeForFlag.Click,
        link_str: str = "",
        save_path: str = "",
        custom_flag: bool = False,
        file_name: str = "",
        simulate_flag: bool = True,
        is_wait: bool = True,
        time_out: int = 60,
    ):
        """下载文件"""
        if download_mode == DownloadModeForFlag.Click:
            from astronverse.browser.browser_element import BrowserElement

            BrowserElement.click(
                browser_obj=browser_obj,
                element_data=element_data,
                simulate_flag=simulate_flag,
                assistive_key=ButtonForAssistiveKeyFlag.Nothing,
                button_type=ButtonForClickTypeFlag.Left,
                element_timeout=10,
            )
            dest_path = BrowserCore.download_window_operate(
                browser_type=browser_obj.browser_type,
                is_wait=is_wait,
                time_out=time_out,
                file_name=file_name,
                custom_flag=custom_flag,
                save_path=save_path,
            )
            return dest_path
        elif download_mode == DownloadModeForFlag.Link:
            file_path_arr = []
            if not (link_str and save_path):
                raise ValueError("请提供正确的url链接和文件存储路径")
            try:
                link_strs = literal_eval(link_str)
            except Exception:
                link_strs = [link_str]
            down_tag = []

            def download_from_req(file_name_out):
                for link_item in link_strs:
                    url_file = link_item.split("?")[0]
                    res = requests.get(link_item, timeout=300, allow_redirects=True, stream=True)
                    if res.status_code != 200:
                        raise requests.RequestException("请求的地址异常")
                    if not custom_flag:
                        file_name_out = url_file.split("/")[-1]
                    else:
                        file_name_out = file_name_out + "." + url_file.split("/")[-1].rsplit(".", 1)[-1]
                    file_path = os.path.join(save_path, file_name_out)
                    file_path_arr.append(file_path)
                    with open(file_path, "wb") as f:
                        for chunk in res.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                down_tag.append(1)

            if is_wait:
                if time_out == 0 or time_out == "":
                    download_from_req(file_name)
                else:
                    threading.Thread(target=download_from_req, args=(file_name,)).start()
                    try:
                        wait_time_download = int(time_out)
                    except Exception:
                        wait_time_download = 60
                    while wait_time_download > 0:
                        wait_time_download = wait_time_download - 3
                        if len(down_tag) > 0:
                            break
                        time.sleep(3)
                    # 需要确定好链接下载是多个还是单个
                    # if wait_time_download<=0 and not os.path.exists(file_name):
                    #     raise Exception("等待下载完成超时")
                return file_path_arr
            else:
                threading.Thread(target=download_from_req, args=(file_name,)).start()
                return save_path

    # 上传文件逻辑
    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("simulate_flag", required=False),
            atomicMg.param(
                "upload_path",
                formType=AtomicFormTypeMeta(
                    type=AtomicFormType.INPUT_VARIABLE_PYTHON_FILE.value,
                    params={"file_type": "file"},
                ),
            ),
        ],
        outputList=[
            atomicMg.param("download_file", types="Str"),
        ],
    )
    def upload_web_file(
        browser_obj: Browser,
        element_data: WebPick = None,
        upload_path: str = "",
        simulate_flag: bool = True,
    ):
        """上传文件"""

        from astronverse.browser.browser_element import BrowserElement

        BrowserElement.click(
            browser_obj=browser_obj,
            element_data=element_data,
            simulate_flag=simulate_flag,
            assistive_key=ButtonForAssistiveKeyFlag.Nothing,
            button_type=ButtonForClickTypeFlag.Left,
            element_timeout=10,
        )
        BrowserCore.upload_window_operate(browser_type=browser_obj.browser_type, upload_path=upload_path)

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("web_obj_list", types="List"),
        ],
    )
    def get_tab_list(browser_obj: Browser):
        """获取网页对象列表"""
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getAllTabs",
        )
        tab_list = []
        if isinstance(data, list):
            for tab in data:
                if not isinstance(tab, dict):
                    continue
                tab_list.append(
                    {
                        "tabId": tab.get("id"),
                        "url": tab.get("url", ""),
                        "title": tab.get("title", ""),
                        "active": bool(tab.get("active")),
                    }
                )
        return tab_list

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("cookie_name", required=False),
            atomicMg.param("cookie_domain", required=False),
            atomicMg.param("cookie_path", required=False),
        ],
        outputList=[
            atomicMg.param("cookie_list", types="List"),
        ],
    )
    def filter_cookies(
        browser_obj: Browser,
        url: URL,
        cookie_name: str = "",
        cookie_domain: str = "",
        cookie_path: str = "",
        page_timeout: float = 10,
    ):
        """获取筛选所有Cookie"""
        data = {"url": str(url)}
        if cookie_name:
            data["name"] = cookie_name
        if cookie_domain:
            data["domain"] = cookie_domain
        data["path"] = cookie_path if cookie_path else ""
        cookies = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getAllCookies",
            data=data,
            timeout=page_timeout,
        )
        return cookies if isinstance(cookies, list) else []

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("cookie_path", required=False),
        ],
    )
    def remove_cookie(
        browser_obj: Browser,
        url: URL,
        cookie_name: str,
        cookie_path: str = "",
        page_timeout: float = 10,
    ):
        """移除Cookie"""
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="removeCookie",
            data={"url": str(url), "name": cookie_name},
            timeout=page_timeout,
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("scroll_position", types="Int"),
        ],
    )
    def get_scroll_position(
        browser_obj: Browser,
        direction: ScrollDirection = ScrollDirection.Vertical,
        position: ScrollPositionTypeFlag = ScrollPositionTypeFlag.Current,
    ):
        """获取滚动条位置"""
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getScrollPosition",
            data={"direction": direction.value},
        )
        if not isinstance(data, dict):
            raise BaseException(BROWSER_EXTENSION_ERROR_FORMAT.format("获取滚动条位置失败"), "获取滚动条位置失败")
        value = data.get(position.value)
        return int(value) if value is not None else 0

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("web_info", types="Str"),
        ],
    )
    def get_web_info(
        browser_obj: Browser,
        info_type: WebInfoTypeFlag = WebInfoTypeFlag.Url,
    ):
        """获取网页信息"""
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getWebInfo",
            data={"infoType": info_type.value},
        )
        if isinstance(data, dict):
            return str(data.get("info", ""))
        return str(data or "")

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("url_filter", required=False),
        ],
    )
    def start_network_monitor(
        browser_obj: Browser,
        url_filter: str = "",
    ):
        """开始监听网页请求"""
        filters = []
        if url_filter:
            filters.append({"urlPattern": url_filter})
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="startNetworkMonitor",
            data={"filters": filters},
            timeout=30,
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param("url_filter", required=False),
            atomicMg.param("resource_type", required=False),
        ],
        outputList=[
            atomicMg.param("request_list", types="List"),
        ],
    )
    def get_network_data(
        browser_obj: Browser,
        url_filter: str = "",
        resource_type: str = "",
        clear: bool = True,
    ):
        """获取网页监听结果"""
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getNetworkData",
            data={"clear": clear},
            timeout=30,
        )
        result = data if isinstance(data, list) else []
        if url_filter:
            import re as _re

            pattern = _re.compile(url_filter)
            result = [item for item in result if pattern.search(str(item.get("url", "")))]
        if resource_type:
            result = [item for item in result if str(item.get("resourceType", "")) == resource_type]
        return result

    @staticmethod
    @atomicMg.atomic("BrowserSoftware")
    def stop_network_monitor(browser_obj: Browser):
        """停止监听网页请求"""
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="stopNetworkMonitor",
            timeout=30,
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        inputList=[
            atomicMg.param(
                "enable",
                formType=AtomicFormTypeMeta(type=AtomicFormType.CHECKBOX.value),
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.button.show",
                        expression="return $this.enable.value == true",
                    ),
                    DynamicsItem(
                        key="$this.prompt_text.show",
                        expression=f"return $this.enable.value == true && $this.button.value == '{DialogButtonTypeFlag.OK.value}'",
                    ),
                ],
            ),
            atomicMg.param(
                "button",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.button.show",
                        expression="return $this.enable.value == true",
                    )
                ],
            ),
            atomicMg.param(
                "prompt_text",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.prompt_text.show",
                        expression=f"return $this.enable.value == true && $this.button.value == '{DialogButtonTypeFlag.OK.value}'",
                    )
                ],
            ),
        ],
    )
    def set_dialog_handler(
        browser_obj: Browser,
        enable: bool = True,
        button: DialogButtonTypeFlag = DialogButtonTypeFlag.OK,
        prompt_text: str = "",
    ):
        """自动处理网页弹框（alert/confirm/prompt）"""
        browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="setDialogAuto",
            data={
                "enable": enable,
                "button": button.value,
                "promptText": prompt_text,
            },
            timeout=30,
        )

    @staticmethod
    @atomicMg.atomic(
        "BrowserSoftware",
        outputList=[
            atomicMg.param("dialog_list", types="List"),
        ],
    )
    def get_dialog_text(
        browser_obj: Browser,
        clear: bool = True,
    ):
        """提取网页对话框内容"""
        data = browser_obj.send_browser_extension(
            browser_type=browser_obj.browser_type.value,
            key="getDialogText",
            data={"clear": clear},
            timeout=30,
        )
        return data if isinstance(data, list) else []
