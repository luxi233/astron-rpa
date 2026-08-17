"""字符串处理相关功能。"""

import math
import re
from copy import deepcopy
from typing import Optional

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem
from astronverse.actionlib.atomic import atomicMg
from astronverse.dataprocess import (
    CaseChangeType,
    ChineseNumberType,
    ConcatStringType,
    CutStringType,
    ExtractType,
    FillStringType,
    PercentConvertType,
    ReplaceType,
    StripStringType,
)
from astronverse.dataprocess.error import *


def get_pattern(pattern_type, regex_formula: str) -> Optional[str]:
    """根据类型选择对应的正则表达式。"""
    pattern: Optional[str] = None
    if pattern_type in [ReplaceType.DIGIT, ExtractType.DIGIT]:
        pattern = r"\d+"
    elif pattern_type in [ReplaceType.EMAIL, ExtractType.EMAIL]:
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})*"
    elif pattern_type in [ReplaceType.PHONE_NUMBER, ExtractType.PHONE_NUMBER]:
        pattern = r"1[3-9]\d{9}"
    elif pattern_type in [ReplaceType.URL, ExtractType.URL]:
        pattern = r"(?:http[s]?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[a-zA-Z0-9-._?&=]*)?"
    elif pattern_type in [ReplaceType.ID_NUMBER, ExtractType.ID_NUMBER]:
        pattern = r"\d{17}[\dXx]"
    elif pattern_type in [ReplaceType.REGEX, ReplaceType.STRING, ExtractType.REGEX]:
        pattern = regex_formula

    return pattern


class StringProcess:
    """字符串处理工具集合。"""

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param(
                "regex_formula",
                dynamics=[
                    DynamicsItem(
                        key="$this.regex_formula.show",
                        expression=f"return $this.extract_type.value == '{ExtractType.REGEX.value}'",
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("extract_from_string", types="List")],
    )
    def extract_content_from_string(
        text: str,
        extract_type: ExtractType = ExtractType.DIGIT,
        regex_formula: str = "",
        first_flag: bool = True,
    ):
        """从文本中提取匹配内容。"""
        if regex_formula:
            try:
                re.compile(regex_formula)
                pass
            except re.error:
                raise BaseException(INVALID_REGEX_ERROR_FORMAT.format(regex_formula), "请重新输入")

        pattern = get_pattern(extract_type, regex_formula) or ""
        result = re.findall(pattern, text)
        if first_flag:
            result = result[0] if result else []
        return result

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param(
                "replaced_string",
                dynamics=[
                    DynamicsItem(
                        key="$this.replaced_string.show",
                        expression=f"return $this.replace_type.value == '{ReplaceType.STRING.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "regex_formula",
                dynamics=[
                    DynamicsItem(
                        key="$this.regex_formula.show",
                        expression=f"return $this.replace_type.value == '{ReplaceType.REGEX.value}'",
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("replaced_content_string", types="List")],
    )
    def replace_content_in_string(
        text: str = "",
        replace_type: ReplaceType = ReplaceType.STRING,
        replaced_string: str = "",
        regex_formula: str = "",
        new_value: str = "",
        first_flag: bool = True,
        ignore_case_flag: bool = False,
    ):
        """替换字符串中匹配的内容。"""
        if regex_formula:
            try:
                re.compile(regex_formula)
                pass
            except re.error:
                raise BaseException(INVALID_REGEX_ERROR_FORMAT.format(regex_formula), "请重新输入")

        if replace_type == ReplaceType.REGEX:
            old_value = regex_formula
        elif replace_type == ReplaceType.STRING:
            old_value = replaced_string
        else:
            old_value = ""

        count = 1 if first_flag else 0
        pattern = get_pattern(replace_type, old_value) or ""
        return re.sub(
            pattern,
            new_value,
            text,
            count=count,
            flags=re.IGNORECASE if ignore_case_flag else 0,
        )

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("list_data", types="Any"),
        ],
        outputList=[atomicMg.param("merged_string_from_list", types="Str")],
    )
    def merge_list_to_string(list_data: list, separator: str = ""):
        """
        列表聚合成文本
        """
        return str(separator).join(str(x) for x in list_data)

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[],
        outputList=[atomicMg.param("split_list_from_string", types="List")],
    )
    def split_string_to_list(string_data: str, separator: str = "", filter_empty: bool = False):
        """
        文本分割为列表
        """
        if separator == "":
            result = list(string_data)
        else:
            result = string_data.split(separator)
        if filter_empty:
            result = [item for item in result if str(item).strip() != ""]
        return result

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("string_data_1", types="Str"),
            atomicMg.param("string_data_2", types="Str"),
            atomicMg.param(
                "separator",
                types="Str",
                dynamics=[
                    DynamicsItem(
                        key="$this.separator.show",
                        expression=f"return $this.concat_type.value == '{ConcatStringType.OTHER.value}'",
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("concat_string", types="Str")],
    )
    def concatenate_string(
        string_data_1: str,
        string_data_2: str,
        concat_type: ConcatStringType = ConcatStringType.NONE,
        separator: str = "",
    ):
        """拼接两个字符串，按 concat_type 确定分隔符。"""
        if concat_type == ConcatStringType.NONE:
            separator = ""
        elif concat_type == ConcatStringType.SPACE:
            separator = " "
        elif concat_type == ConcatStringType.HYPHEN:
            separator = "-"
        elif concat_type == ConcatStringType.UNDERLINE:
            separator = "_"
        elif concat_type == ConcatStringType.LINEBREAK:
            separator = "\n"
        elif concat_type == ConcatStringType.OTHER:
            separator = str(separator)
        return string_data_1 + separator + string_data_2

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("string_data", types="Str"),
        ],
        outputList=[atomicMg.param("complete_string", types="Str")],
    )
    def fill_string_to_length(
        string_data: str = "",
        add_str: str = "",
        total_length: str = "",
        fill_type: FillStringType = FillStringType.RIGHT,
    ):
        """按指定方向填充字符串到目标长度。"""
        if (not string_data) or (not add_str):
            raise ValueError("目标文本或补充文本不能为空!")
        try:
            total_length_int = int(total_length)
            assert total_length_int >= 0
        except Exception as e:
            raise ValueError("长度输入不合法,请提供整数类型数据!")

        result_str = deepcopy(str(string_data))
        if total_length_int <= len(string_data):
            return result_str
        n = math.ceil((total_length_int - len(string_data)) / len(add_str))  # 向上取整获得重复次数
        if fill_type == FillStringType.LEFT:  # 左端补齐
            result_str = (add_str * n)[0 : total_length_int - len(string_data)] + string_data
        elif fill_type == FillStringType.RIGHT:  # 右端补齐
            result_str = (string_data + add_str * n)[0:total_length_int]
        return result_str

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("string_data", types="Str"),
        ],
        outputList=[atomicMg.param("stripped_string", types="Str")],
    )
    def strip_string(string_data: str, strip_method: StripStringType = StripStringType.BOTH):
        """移除字符串空白。"""
        if not string_data:
            return ""

        result_str = deepcopy(string_data)
        if strip_method == StripStringType.BOTH:  # 默认删除两端的空格
            result_str = string_data.strip()
        elif strip_method == StripStringType.LEFT:  # 删除左端的空格
            result_str = string_data.lstrip()
        elif strip_method == StripStringType.RIGHT:  # 删除右端的空格
            result_str = string_data.rstrip()
        return result_str

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("string_data", types="Str"),
            atomicMg.param(
                "index",
                dynamics=[
                    DynamicsItem(
                        key="$this.index.show",
                        expression=f"return $this.cut_type.value == '{CutStringType.INDEX.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "find_str",
                dynamics=[
                    DynamicsItem(
                        key="$this.find_str.show",
                        expression=f"return $this.cut_type.value == '{CutStringType.STRING.value}'",
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("cut_string", types="Str")],
    )
    def cut_string_to_length(
        string_data: str,
        length: int,
        cut_type: CutStringType = CutStringType.FIRST,
        index: int = 0,
        find_str: str = "",
    ):
        """按照指定方式截取字符串。"""
        if not string_data:
            raise ValueError("目标文本不能为空!")
        if length < 0:
            raise ValueError("长度输入不合法,请提供整数类型数据!")

        result_str = ""
        if cut_type == CutStringType.FIRST:
            result_str = string_data[:length]
        elif cut_type == CutStringType.INDEX:
            result_str = string_data[index : index + length]
        elif cut_type == CutStringType.STRING:
            index = string_data.find(find_str)
            if index == -1:
                raise ValueError("未找到指定字符串!")
            result_str = string_data[index : index + length]
        return result_str

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("string_data", types="Str"),
        ],
        outputList=[atomicMg.param("change_case_string", types="Str")],
    )
    def change_case_of_string(string_data: str, case_type: CaseChangeType = CaseChangeType.LOWER):
        """转换字符串大小写。"""
        if not string_data:
            return ""
        if case_type == CaseChangeType.LOWER:
            return string_data.lower()
        if case_type == CaseChangeType.UPPER:
            return string_data.upper()
        if case_type == CaseChangeType.CAPS:
            return string_data.capitalize()
        raise ValueError("不支持的大小写转换类型")

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("string_data", types="Str"),
        ],
        outputList=[atomicMg.param("string_length", types="Int")],
    )
    def get_string_length(string_data: str):
        """返回字符串长度。"""
        return len(string_data) if string_data else 0

    # ==================== 文本扩展 ====================

    _CN_NUM_DIGITS = "零一二三四五六七八九"
    _CN_NUM_UNITS = ["", "十", "百", "千"]
    _CN_NUM_BIGUNITS = ["", "万", "亿", "万亿"]
    _CN_AMOUNT_DIGITS = "零壹贰叁肆伍陆柒捌玖"
    _CN_AMOUNT_UNITS = ["", "拾", "佰", "仟"]

    _CN_TO_EN_SYMBOLS = {
        "【": "[",
        "】": "]",
        "｛": "{",
        "｝": "}",
        "（": "(",
        "）": ")",
        "，": ",",
        "。": ".",
        "？": "?",
        "！": "!",
        "；": ";",
        "：": ":",
        "＂": '"',
        "＂": '"',
        "＇": "'",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "／": "/",
        "＼": "\\",
        "～": "~",
        "－": "-",
        "＋": "+",
        "＝": "=",
        "＊": "*",
        "＃": "#",
        "＠": "@",
        "＆": "&",
        "《": "<",
        "》": ">",
        "「": '"',
        "」": '"',
        "『": '"',
        "』": '"',
    }

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("length", types="Int"),
            atomicMg.param("include_chinese", types="Bool", required=False),
            atomicMg.param("include_upper", types="Bool", required=False),
            atomicMg.param("include_lower", types="Bool", required=False),
            atomicMg.param("include_digit", types="Bool", required=False),
            atomicMg.param("include_special", types="Bool", required=False),
        ],
        outputList=[atomicMg.param("random_string", types="Str")],
    )
    def generate_random_string(
        length: int = 8,
        include_chinese: bool = False,
        include_upper: bool = True,
        include_lower: bool = True,
        include_digit: bool = True,
        include_special: bool = False,
    ) -> str:
        """
        生成随机字符串
        :param length: 字符串长度
        :param include_chinese: 包含汉字
        :param include_upper: 包含大写字母
        :param include_lower: 包含小写字母
        :param include_digit: 包含数字
        :param include_special: 包含特殊字符(!@#$%^&*等)
        """
        import random
        import string as _string

        if length <= 0:
            raise BaseException(INVALID_NUMBER_RANGE_ERROR_FORMAT, "字符串长度必须大于0")
        pools = []
        if include_chinese:
            pools.append(
                "的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所同日手又行意动方期它头经长儿回位分爱老因很给名法间斯知世什两次使身者被高已亲其进此话常与活正感"
            )
        if include_upper:
            pools.append(_string.ascii_uppercase)
        if include_lower:
            pools.append(_string.ascii_lowercase)
        if include_digit:
            pools.append(_string.digits)
        if include_special:
            pools.append("!@#$%^&*()-_=+[]{};:,.?~")
        if not pools:
            raise BaseException(VALUE_ERROR_FORMAT, "请至少勾选一种字符类型")
        chars = []
        for _ in range(length):
            pool = random.choice(pools)
            chars.append(random.choice(pool))
        return "".join(chars)

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("value", types="Str"),
            atomicMg.param("convert_type"),
            atomicMg.param("precision", types="Int", required=False),
        ],
        outputList=[atomicMg.param("convert_result", types="Any")],
    )
    def convert_percent(value, convert_type: PercentConvertType = PercentConvertType.TO_PERCENT, precision: int = 2):
        """
        转换数字和百分比
        :param value: 数字(如0.1234)或百分比字符串(如12.34%)
        :param convert_type: 转换类型(数字转百分比/百分比转数字)
        :param precision: 保留小数位数
        """
        if convert_type == PercentConvertType.TO_PERCENT:
            try:
                num = float(str(value).strip().rstrip("%"))
            except ValueError:
                raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "请输入有效的数字")
            return f"{round(num * 100, precision)}%"
        try:
            num = float(str(value).strip().rstrip("%"))
        except ValueError:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "请输入有效的百分比(如12.34%)")
        return round(num / 100, precision + 2)

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param(
                "address",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("address_parts", types="List")],
    )
    def split_address(address: str = ""):
        """
        切分省市区地址
        :param address: 地址字符串，如 广东省深圳市南山区科技园路1号
        :return: [省, 市, 区县] 列表(含详细地址时为第4项)
        """
        if not address or not str(address).strip():
            raise BaseException(VALUE_ERROR_FORMAT, "地址不能为空")
        text = str(address).strip()
        province = city = district = ""
        rest = text
        m = re.match(r"^(.*?(?:省|自治区|北京市|天津市|上海市|重庆市|香港特别行政区|澳门特别行政区))", rest)
        if m:
            province = m.group(1)
            rest = rest[len(province) :]
        elif re.match(r"^(北京市|天津市|上海市|重庆市)", rest):
            province = rest[:3]
            rest = rest[3:]
        m = re.match(r"^(.*?(?:市|自治州|地区|盟))", rest)
        if m and len(m.group(1)) > 1:
            city = m.group(1)
            rest = rest[len(city) :]
        m = re.match(r"^(.*?(?:区|县|县级市|旗|市|镇|乡|街道))", rest)
        if m and len(m.group(1)) > 1:
            district = m.group(1)
            rest = rest[len(district) :]
        # 直辖市: 市级行复制省名(北京市朝阳区 → [北京市, 北京市, 朝阳区])
        municipalities = ("北京市", "天津市", "上海市", "重庆市")
        if not city and province in municipalities:
            city = province
        parts = [province, city, district]
        if rest:
            parts.append(rest)
        return parts

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param(
                "source_text",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param(
                "samples",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
            atomicMg.param("threshold", types="Float", required=False),
        ],
        outputList=[
            atomicMg.param("match_list", types="List"),
            atomicMg.param("best_match", types="Str"),
            atomicMg.param("best_ratio", types="Float"),
        ],
    )
    def match_similar_text(source_text: str = "", samples=None, threshold: float = 0.6):
        """
        相似文本匹配(找出样本列表中与原文本最相似的文本)
        :param source_text: 原文本
        :param samples: 样本列表，如 ['苹果手机','华为手机']
        :param threshold: 相似度阈值(0-1，低于阈值的样本被过滤)
        :return: (超过阈值的样本列表, 最相似文本, 最相似度)
        """
        from difflib import SequenceMatcher

        if not samples or not isinstance(samples, (list, tuple)):
            raise BaseException(INVALID_LIST_FORMAT_ERROR_FORMAT, "样本必须是列表")
        scored = [(str(s), SequenceMatcher(None, str(source_text), str(s)).ratio()) for s in samples]
        match_list = [s for s, r in scored if r >= threshold]
        best = max(scored, key=lambda x: x[1])
        return match_list, best[0], round(best[1], 4)

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("text1", types="Str"),
            atomicMg.param("text2", types="Str"),
        ],
        outputList=[atomicMg.param("similarity", types="Float")],
    )
    def compare_text_similarity(text1: str = "", text2: str = ""):
        """
        比较两个文本的相似度
        :param text1: 文本1
        :param text2: 文本2
        :return: 相似度百分比(0-100)
        """
        from difflib import SequenceMatcher

        return round(SequenceMatcher(None, str(text1), str(text2)).ratio() * 100, 2)

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[atomicMg.param("text", types="Str")],
        outputList=[atomicMg.param("half_width_text", types="Str")],
    )
    def full_to_half(text: str = "") -> str:
        """
        中文全角转半角(如 ＡＢＣ123 → ABC123)
        """
        result = []
        for ch in str(text):
            code = ord(ch)
            if code == 0x3000:
                result.append(" ")
            elif 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            else:
                result.append(ch)
        return "".join(result)

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[atomicMg.param("text", types="Str")],
        outputList=[atomicMg.param("converted_text", types="Str")],
    )
    def cn_symbol_to_en(text: str = "") -> str:
        """
        中文符号转英文(如 【】 → []、， → ,)
        """
        table = StringProcess._CN_TO_EN_SYMBOLS
        return "".join(table.get(ch, ch) for ch in str(text))

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[atomicMg.param("text", types="Str")],
        outputList=[atomicMg.param("converted_text", types="Str")],
    )
    def en_symbol_to_cn(text: str = "") -> str:
        """
        英文符号转中文(如 [] → 【】、, → ，)
        """
        table = {v: k for k, v in StringProcess._CN_TO_EN_SYMBOLS.items()}
        fixed = {}
        for en, cn in table.items():
            fixed.setdefault(en, cn)
        return "".join(fixed.get(ch, ch) for ch in str(text))

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[atomicMg.param("text", types="Str")],
        outputList=[atomicMg.param("cleaned_text", types="Str")],
    )
    def remove_blank_lines(text: str = "") -> str:
        """
        去除文本中的空白行
        """
        return "\n".join(line for line in str(text).splitlines() if line.strip())

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("text", types="Str"),
            atomicMg.param("separator", types="Str", required=False),
            atomicMg.param("remove_blank", types="Bool", required=False),
        ],
        outputList=[atomicMg.param("merged_text", types="Str")],
    )
    def merge_lines_to_one(text: str = "", separator: str = " ", remove_blank: bool = True):
        """
        多行文本合并成一行
        :param text: 多行文本
        :param separator: 行之间的分隔符(默认空格)
        :param remove_blank: 合并时去除空白行
        """
        lines = str(text).splitlines()
        if remove_blank:
            lines = [line for line in lines if line.strip()]
        return separator.join(lines)

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param(
                "chinese_number",
                types="Str",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON.value),
                required=True,
            ),
        ],
        outputList=[atomicMg.param("number", types="Int")],
    )
    def chinese_to_number(chinese_number: str = ""):
        """
        汉字转阿拉伯数字(如 一千二百三十 → 1230、三百零五 → 305)
        """
        text = str(chinese_number).strip()
        if not text:
            raise BaseException(VALUE_ERROR_FORMAT, "汉字数字不能为空")
        digit_map = {c: i for i, c in enumerate("零一二三四五六七八九")}
        digit_map.update({"两": 2, "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9})
        unit_map = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
        big_map = {"万": 10000, "萬": 10000, "亿": 100000000, "億": 100000000}

        def parse_segment(seg):
            total, num = 0, 0
            for ch in seg:
                if ch in digit_map:
                    num = digit_map[ch]
                elif ch in unit_map:
                    total += (num or 1) * unit_map[ch]
                    num = 0
            return total + num

        result, segment = 0, ""
        for ch in text:
            if ch in big_map:
                seg_val = parse_segment(segment)
                result += seg_val * big_map[ch] if seg_val else big_map[ch]
                segment = ""
            else:
                segment += ch
        result += parse_segment(segment)
        if result == 0 and text not in ("零", "〇"):
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, f"无法解析汉字数字: {text}")
        return result

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("number", types="Str"),
            atomicMg.param("case_type"),
        ],
        outputList=[atomicMg.param("chinese_text", types="Str")],
    )
    def number_to_chinese(number, case_type: ChineseNumberType = ChineseNumberType.NORMAL):
        """
        阿拉伯数字转汉字(如 123 → 一百二十三；大写金额模式 123 → 壹佰贰拾叁元整)
        :param number: 数字或数字字符串
        :param case_type: 转换模式(普通/大写金额)
        """
        try:
            value = int(str(number).strip())
        except ValueError:
            raise BaseException(INVALID_NUMBER_FORMAT_ERROR_FORMAT, "请输入整数")
        if abs(value) >= 10**12:
            raise BaseException(INVALID_NUMBER_RANGE_ERROR_FORMAT, "数字过大(最大支持千亿级)")

        digits = (
            StringProcess._CN_NUM_DIGITS if case_type == ChineseNumberType.NORMAL else StringProcess._CN_AMOUNT_DIGITS
        )
        units = StringProcess._CN_NUM_UNITS if case_type == ChineseNumberType.NORMAL else StringProcess._CN_AMOUNT_UNITS
        bigunits = ["", "万", "亿"]

        def four_to_cn(n4):
            if n4 == 0:
                return ""
            parts = []
            zero_flag = False
            for i in range(3, -1, -1):
                d = n4 // (10**i) % 10
                if d == 0:
                    if parts and not zero_flag:
                        zero_flag = True
                    continue
                if zero_flag:
                    parts.append(digits[0])
                    zero_flag = False
                parts.append(digits[d] + (units[i] if i else ""))
            return "".join(parts)

        if value == 0:
            result = digits[0]
        else:
            negative = value < 0
            value = abs(value)
            segs = []
            while value > 0:
                segs.append(value % 10000)
                value //= 10000
            segs.reverse()  # 高位段在前
            parts = []
            zero_between = False
            for i, seg in enumerate(segs):
                if seg == 0:
                    zero_between = True
                    continue
                text = four_to_cn(seg)
                if i > 0 and (zero_between or seg < 1000):
                    text = digits[0] + text
                parts.append(text + bigunits[len(segs) - 1 - i])
                zero_between = False
            result = "".join(parts)
            # 中文习惯: "一十"开头省"一"(如 10→十、100000→十万)；大写金额保留壹拾
            if case_type == ChineseNumberType.NORMAL and result.startswith(digits[1] + units[1]):
                result = result[len(digits[1]) :]
            if negative:
                result = "负" + result
        if case_type == ChineseNumberType.AMOUNT:
            result += "元整"
        return result

    @staticmethod
    @atomicMg.atomic(
        "StringProcess",
        inputList=[
            atomicMg.param("upper", types="Bool", required=False),
            atomicMg.param("with_hyphen", types="Bool", required=False),
        ],
        outputList=[atomicMg.param("uuid_string", types="Str")],
    )
    def generate_uuid(upper: bool = False, with_hyphen: bool = True) -> str:
        """
        生成UUID唯一标识符
        :param upper: 输出大写
        :param with_hyphen: 保留连字符
        """
        import uuid as _uuid

        text = str(_uuid.uuid4())
        if not with_hyphen:
            text = text.replace("-", "")
        if upper:
            text = text.upper()
        return text
