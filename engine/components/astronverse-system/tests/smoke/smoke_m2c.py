# -*- coding: utf-8 -*-
"""M2-C批次冒烟: P5-5 系统×8 屏幕分辨率/缩放/IP/计算机信息/显示桌面/声音/回收站
macOS 上: 跨平台原子(IP/计算机信息)真实执行, Win专有原子验证平台守卫+参数校验"""
import sys

sys.path.insert(0, "/Users/infinitelab/Desktop/astron-rpa/engine/components/astronverse-system/src")

from astronverse.baseline.error.error import BaseException  # noqa: E402
from astronverse.system.device import Device as D  # noqa: E402
from astronverse.system.screen import Screen as S  # noqa: E402

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
            print(f"PASS {name}: {msg[:70]}")
        else:
            failed += 1
            print(f"FAIL {name} 关键词[{keyword}]不在: {msg[:100]}")
    except Exception as e:  # noqa: BLE001
        failed += 1
        print(f"FAIL {name} 异常类型不符: {type(e).__name__} {e}")


assert sys.platform != "win32", "本机应为 macOS"

# ---------- 跨平台原子: 真实执行 ----------
ip, host = D.get_ip_address()
check("get_ip IP非空", bool(ip and ip.strip()), ip)
check("get_ip host非空", bool(host and host.strip()), host)
import socket  # noqa: E402

check("get_ip 与socket一致", ip == socket.gethostbyname(host), (ip, host))

name, os_ver, cpu, sysdir, bits = D.get_computer_info()
check("info 名称非空", bool(name), name)
check("info OS含Darwin/macOS", "Darwin" in os_ver or "macOS" in os_ver, os_ver)
check("info 处理器非空", bool(cpu), cpu)
check("info 系统目录=/", sysdir == "/", sysdir)
check("info 位数64bit", "64" in bits, bits)

# ---------- Win 专有原子: 平台守卫 ----------
expect_err("get_resolution macOS不支持", S.get_screen_resolution, {}, "仅在 Windows")
expect_err("set_resolution macOS不支持", S.set_screen_resolution, {"width": 1920, "height": 1080}, "仅在 Windows")
expect_err("set_scale macOS不支持", S.set_screen_scale, {"scale": 150}, "仅在 Windows")
expect_err("show_desktop macOS不支持", D.show_desktop, {}, "仅在 Windows")
expect_err("play_sound macOS不支持", D.play_sound, {"frequency": 1000, "duration": 300}, "仅在 Windows")
expect_err("empty_recycle macOS不支持", D.empty_recycle_bin, {}, "仅在 Windows")

# ---------- 参数校验(平台检查前, 全平台生效) ----------
expect_err("set_resolution 宽过小", S.set_screen_resolution, {"width": 100, "height": 1080}, "屏幕设置失败")
expect_err("set_resolution 高过大", S.set_screen_resolution, {"width": 1920, "height": 99999}, "屏幕设置失败")
expect_err("set_scale 非25倍数", S.set_screen_scale, {"scale": 130}, "屏幕设置失败")
expect_err("set_scale 超500", S.set_screen_scale, {"scale": 525}, "屏幕设置失败")
expect_err("play_sound 频率过低", D.play_sound, {"frequency": 20, "duration": 100}, "系统设备操作失败")
expect_err("play_sound 时长非正", D.play_sound, {"frequency": 500, "duration": 0}, "系统设备操作失败")

# ---------- set_scale 步进表覆盖 ----------
from astronverse.system.screen import _SCALE_STEPS  # noqa: E402

check("scale表 100→96", _SCALE_STEPS[100] == 96)
check("scale表 150→144", _SCALE_STEPS[150] == 144)
check("scale表 500→480", _SCALE_STEPS[500] == 480)
check("scale表 覆盖常用档", all(s in _SCALE_STEPS for s in (100, 125, 150, 200, 250, 300)))

print(f"\n=== M2-C 冒烟: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
