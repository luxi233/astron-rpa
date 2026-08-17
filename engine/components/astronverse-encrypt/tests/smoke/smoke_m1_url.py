"""M1批次冒烟: P4-3 URL编码×2 (自 dataprocess/tests/smoke/smoke_m1.py 迁入, 全部kwargs调用)"""
# ruff: noqa: T201
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from astronverse.encrypt import UrlEncodingType
from astronverse.encrypt.encrypt import Encrypt as E  # noqa: N817

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


# ---------- P4-3 URL ----------
r = E.url_encode(source_str="你好 world")
check("url编码 中文+空格", r == "%E4%BD%A0%E5%A5%BD%20world", r)
r2 = E.url_decode(source_str=r)
check("url往返", r2 == "你好 world", r2)
r = E.url_encode(source_str="a/b:c?d=e&f", safe_chars="/:?&=")
check("url编码 保留字符集", r == "a/b:c?d=e&f", r)
r = E.url_encode(source_str="a+b c")
check("url编码 +号", r == "a%2Bb%20c", r)
r2 = E.url_decode(source_str="a%2Bb%20c")
check("url解码 %2B", r2 == "a+b c", r2)
r = E.url_decode(source_str="%C4%E3%BA%C3", encoding=UrlEncodingType.GBK)
check("url解码 GBK", r == "你好", r)

print(f"\n=== M1-URL 冒烟: {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
