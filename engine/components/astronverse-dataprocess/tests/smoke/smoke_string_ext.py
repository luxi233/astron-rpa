# -*- coding: utf-8 -*-
"""P0-5 文本扩展×13原子 冒烟测试(全部kwargs调用)"""

import sys

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "engine/components/astronverse-dataprocess/src"))

from astronverse.dataprocess.string import StringProcess as S
from astronverse.dataprocess import ChineseNumberType, PercentConvertType

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name} {detail}")


# 1. generate_random_string
r = S.generate_random_string(length=16, include_upper=True, include_lower=True, include_digit=True)
check("random_string len", len(r) == 16, r)
check("random_string ascii", all(c.isalnum() and ord(c) < 128 for c in r), r)
r2 = S.generate_random_string(
    length=10, include_chinese=True, include_upper=False, include_lower=False, include_digit=False
)
check("random_string chinese", all("\u4e00" <= c <= "\u9fff" for c in r2), r2)
try:
    S.generate_random_string(
        length=5,
        include_upper=False,
        include_lower=False,
        include_digit=False,
        include_chinese=False,
        include_special=False,
    )
    check("random_string empty-pool raises", False)
except BaseException:
    check("random_string empty-pool raises", True)

# 2. convert_percent
check(
    "percent to_percent",
    S.convert_percent(value=0.1234, convert_type=PercentConvertType.TO_PERCENT, precision=2) == "12.34%",
    S.convert_percent(value=0.1234, convert_type=PercentConvertType.TO_PERCENT, precision=2),
)
check(
    "percent to_number",
    S.convert_percent(value="12.34%", convert_type=PercentConvertType.TO_NUMBER, precision=2) == 0.1234,
    S.convert_percent(value="12.34%", convert_type=PercentConvertType.TO_NUMBER, precision=2),
)

# 3. split_address
parts = S.split_address(address="广东省深圳市南山区科技园路1号")
check("address 4parts", parts == ["广东省", "深圳市", "南山区", "科技园路1号"], parts)
parts2 = S.split_address(address="北京市朝阳区")
check("address beijing", parts2 == ["北京市", "北京市", "朝阳区"], parts2)
parts3 = S.split_address(address="内蒙古自治区赤峰市")
check("address autonomous", parts3[0] == "内蒙古自治区", parts3)

# 4. match_similar_text
ml, best, ratio = S.match_similar_text(
    source_text="苹果手机12", samples=["苹果手机", "华为手机", "苹果耳机"], threshold=0.3
)
check("similar best", best == "苹果手机", f"{best}/{ratio}")
check("similar best_ratio", ratio >= 0.3, (ml, ratio))

# 5. compare_text_similarity
sim = S.compare_text_similarity(text1="abcdef", text2="abcdxyz")
check("similarity range", 0 <= sim <= 100 and sim > 0, sim)

# 6. full_to_half
check("full2half", S.full_to_half(text="ＡＢＣ１２３　ｘ") == "ABC123 x", S.full_to_half(text="ＡＢＣ１２３　ｘ"))

# 7/8. symbols
v = S.cn_symbol_to_en(text="【a】，b")
check("cn2en mixed", v == "[a],b", v)
v2 = S.en_symbol_to_cn(text="[a],b")
check("en2cn mixed", v2 == "【a】，b", v2)
v3 = S.cn_symbol_to_en(text="第一《书》")
check("cn2en book", v3 == "第一<书>", v3)

# 9. remove_blank_lines
check(
    "remove_blank", S.remove_blank_lines(text="a\n\n  \nb\n") == "a\nb", repr(S.remove_blank_lines(text="a\n\n  \nb\n"))
)

# 10. merge_lines_to_one
check(
    "merge_lines",
    S.merge_lines_to_one(text="a\n\nb\nc", separator=";", remove_blank=True) == "a;b;c",
    S.merge_lines_to_one(text="a\n\nb\nc", separator=";", remove_blank=True),
)

# 11. chinese_to_number
for cn, num in [
    ("一千零二十三", 1023),
    ("三百零五", 305),
    ("一千二百三十", 1230),
    ("两", 2),
    ("拾", 10),
    ("一万", 10000),
    ("零", 0),
]:
    got = S.chinese_to_number(chinese_number=cn)
    check(f"cn2num {cn}", got == num, got)

# 12. number_to_chinese
for num, expect in [
    (123, "一百二十三"),
    (0, "零"),
    (10, "十"),
    (110, "一百一十"),
    (100000, "十万"),
    (10000, "一万"),
    (10001, "一万零一"),
    (100000001, "一亿零一"),
    (100000000, "一亿"),
    (100020003, "一亿零二万零三"),
    (-15, "负十五"),
]:
    got = S.number_to_chinese(number=num, case_type=ChineseNumberType.NORMAL)
    check(f"num2cn {num}", got == expect, got)
check(
    "num2cn amount",
    S.number_to_chinese(number=123, case_type=ChineseNumberType.AMOUNT) == "壹佰贰拾叁元整",
    S.number_to_chinese(number=123, case_type=ChineseNumberType.AMOUNT),
)

# 13. generate_uuid
u1, u2 = S.generate_uuid(), S.generate_uuid(upper=True, with_hyphen=False)
check("uuid unique", u1 != u2 and len(u1) == 36 and u1.count("-") == 4, (u1, u2))
check("uuid upper-nohyphen", len(u2) == 32 and u2.isupper() and "-" not in u2, u2)

print(f"\n=== {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
