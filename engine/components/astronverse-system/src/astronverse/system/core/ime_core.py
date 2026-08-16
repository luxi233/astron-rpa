"""输入法中英文状态核心模块(Windows imm32)"""


def _get_ime_hwnd():
    """获取前台窗口对应的默认IME窗口句柄, 失败返回None"""
    import ctypes

    user32 = ctypes.windll.user32
    imm32 = ctypes.windll.imm32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    # ImmGetDefaultIMEWnd(未公开但广泛使用): 取窗口所属线程的默认IME窗口
    imm_hwnd = imm32.ImmGetDefaultIMEWnd(hwnd)
    return imm_hwnd or None


def get_ime_status() -> str:
    """获取前台窗口输入法中英文输入状态

    :return: english(英文)/chinese(中文)/unknow(未知)
    """
    import ctypes

    user32 = ctypes.windll.user32
    WM_IME_CONTROL = 0x0283
    IMC_GETCONVERSIONMODE = 0x0001

    imm_hwnd = _get_ime_hwnd()
    if not imm_hwnd:
        return "unknow"
    mode = user32.SendMessageW(imm_hwnd, WM_IME_CONTROL, IMC_GETCONVERSIONMODE, 0)
    # IME_CMODE_ALPHANUMERIC(0)=英文, IME_CMODE_NATIVE(1)=中文, 其他=未知
    if mode == 0:
        return "english"
    if mode == 1:
        return "chinese"
    return "unknow"


def set_ime_status(status: str) -> None:
    """设置前台窗口输入法中英文输入状态

    :param status: english(英文)/chinese(中文)
    """
    import ctypes

    user32 = ctypes.windll.user32
    WM_IME_CONTROL = 0x0283
    IMC_SETCONVERSIONMODE = 0x0002
    IME_CMODE_ALPHANUMERIC = 0x0000
    IME_CMODE_NATIVE = 0x0001

    mode = IME_CMODE_NATIVE if status == "chinese" else IME_CMODE_ALPHANUMERIC
    imm_hwnd = _get_ime_hwnd()
    if not imm_hwnd:
        raise RuntimeError("未找到前台窗口的输入法窗口")
    result = user32.SendMessageW(imm_hwnd, WM_IME_CONTROL, IMC_SETCONVERSIONMODE, mode)
    if result != 0 and result != 1:
        # 部分IME返回值不规范, 不作为硬性失败条件
        pass
