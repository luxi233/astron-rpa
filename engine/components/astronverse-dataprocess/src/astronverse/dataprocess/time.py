"""时间处理工具集。"""

import calendar
import copy
from datetime import UTC, datetime

from astronverse.actionlib import AtomicFormType, AtomicFormTypeMeta, DynamicsItem, TimeFormatType
from astronverse.actionlib.atomic import atomicMg
from astronverse.actionlib.types import Date
from astronverse.dataprocess import ParseTimeType, TimeChangeType, TimestampUnitType, TimeUnitType, TimeZoneType
from dateutil import parser
from dateutil.relativedelta import relativedelta


class TimeProcess:
    """时间相关原子能力集合。"""

    @staticmethod
    @atomicMg.atomic("TimeProcess", outputList=[atomicMg.param("current_time", types="Date")])
    def get_current_time(time_format: TimeFormatType = TimeFormatType.YMD_HMS):
        """获取当前时间对象并应用格式。"""
        res = Date()
        res.format = time_format
        return res

    @staticmethod
    @atomicMg.atomic(
        "TimeProcess",
        inputList=[
            atomicMg.param(
                "time",
                types="Date",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON_DATETIME.value),
            ),
            atomicMg.param(
                "seconds",
                dynamics=[
                    DynamicsItem(
                        key="$this.seconds.show",
                        expression=f"return $this.change_type.value != '{TimeChangeType.MAINTAIN.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "minutes",
                dynamics=[
                    DynamicsItem(
                        key="$this.minutes.show",
                        expression=f"return $this.change_type.value != '{TimeChangeType.MAINTAIN.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "hours",
                dynamics=[
                    DynamicsItem(
                        key="$this.hours.show",
                        expression=f"return $this.change_type.value != '{TimeChangeType.MAINTAIN.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "days",
                dynamics=[
                    DynamicsItem(
                        key="$this.days.show",
                        expression=f"return $this.change_type.value != '{TimeChangeType.MAINTAIN.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "months",
                dynamics=[
                    DynamicsItem(
                        key="$this.months.show",
                        expression=f"return $this.change_type.value != '{TimeChangeType.MAINTAIN.value}'",
                    )
                ],
            ),
            atomicMg.param(
                "years",
                dynamics=[
                    DynamicsItem(
                        key="$this.years.show",
                        expression=f"return $this.change_type.value != '{TimeChangeType.MAINTAIN.value}'",
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("set_time", types="Date")],
    )
    def set_time(
        time: Date,
        change_type: TimeChangeType = TimeChangeType.MAINTAIN,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        months: int = 0,
        years: int = 0,
    ):
        """对给定时间按增减方式进行偏移。"""
        res = copy.deepcopy(time)
        delta = relativedelta(
            years=years,
            months=months,
            days=days,
            hours=hours,
            minutes=minutes,
            seconds=seconds,
        )
        if change_type == TimeChangeType.ADD:
            res.time += delta
        elif change_type == TimeChangeType.SUB:
            res.time -= delta
        return res

    @staticmethod
    @atomicMg.atomic(
        "TimeProcess",
        inputList=[
            atomicMg.param(
                "time",
                types="Date",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON_DATETIME.value),
            )
        ],
        outputList=[atomicMg.param("converted_timestamp", types="Int")],
    )
    def time_to_timestamp(time: Date, timestamp_unit: TimestampUnitType = TimestampUnitType.SECOND):
        """时间对象转时间戳。"""
        base = time.time.timestamp()
        if timestamp_unit == TimestampUnitType.SECOND:
            return int(base)
        if timestamp_unit == TimestampUnitType.MILLISECOND:
            return int(base * 1000)
        if timestamp_unit == TimestampUnitType.MICROSECOND:
            return int(base * 1_000_000)
        raise ValueError("不支持的时间戳单位")

    @staticmethod
    @atomicMg.atomic("TimeProcess", outputList=[atomicMg.param("converted_time", types="Date")])
    def timestamp_to_time(timestamp: int, time_zone: TimeZoneType = TimeZoneType.LOCAL):
        """时间戳转换为时间对象。支持秒/毫秒/微秒自动判定。"""
        ts_str = str(timestamp)
        length = len(ts_str)
        if length <= 10:
            timestamp_float = timestamp
        elif 10 < length <= 13:  # 毫秒
            timestamp_float = timestamp / 1000
        elif 13 < length <= 16:  # 微秒
            timestamp_float = timestamp / 1_000_000
        else:
            raise ValueError("时间戳长度不支持")
        time_obj = Date()
        if time_zone == TimeZoneType.UTC:
            time_obj.time = datetime.fromtimestamp(timestamp_float, tz=UTC)
        else:  # 本地
            time_obj.time = datetime.fromtimestamp(timestamp_float)
        return time_obj

    @staticmethod
    @atomicMg.atomic(
        "TimeProcess",
        inputList=[
            atomicMg.param(
                "time_1",
                types="Date",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON_DATETIME.value),
            ),
            atomicMg.param(
                "time_2",
                types="Date",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON_DATETIME.value),
            ),
        ],
        outputList=[atomicMg.param("time_difference", types="Int")],
    )
    def get_time_difference(time_1: Date, time_2: Date, time_unit: TimeUnitType = TimeUnitType.SECOND):
        """计算两个时间的差值并按单位返回。"""
        diff_seconds = abs((time_2.time - time_1.time).total_seconds())
        if time_unit == TimeUnitType.SECOND:
            return int(diff_seconds)
        if time_unit == TimeUnitType.MINUTE:
            return int(diff_seconds / 60)
        if time_unit == TimeUnitType.HOUR:
            return int(diff_seconds / 3600)
        if time_unit == TimeUnitType.DAY:
            return int(diff_seconds / 86400)
        if time_unit in {TimeUnitType.MONTH, TimeUnitType.YEAR}:
            delta = relativedelta(time_2.time, time_1.time)
            if time_unit == TimeUnitType.MONTH:
                return delta.years * 12 + delta.months
            return delta.years
        raise ValueError("不支持的时间单位")

    @staticmethod
    @atomicMg.atomic(
        "TimeProcess",
        inputList=[
            atomicMg.param(
                "time",
                types="Date",
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON_DATETIME.value),
            ),
        ],
        outputList=[atomicMg.param("format_datetime", types="Str")],
    )
    def format_datetime(time: Date, format_type: TimeFormatType = TimeFormatType.YMD_HMS):
        """格式化时间为字符串。"""
        time.format = format_type
        return str(time)

    @staticmethod
    @atomicMg.atomic(
        "TimeProcess",
        inputList=[
            atomicMg.param("text", types="Str"),
            atomicMg.param(
                "custom_format",
                types="Str",
                required=False,
                dynamics=[
                    DynamicsItem(
                        key="$this.custom_format.show",
                        expression=f"return $this.parse_type.value == '{ParseTimeType.CUSTOM.value}'",
                    )
                ],
            ),
        ],
        outputList=[atomicMg.param("parsed_time", types="Date")],
    )
    def parse_datetime(text: str, parse_type: ParseTimeType = ParseTimeType.AUTO, custom_format: str = "%Y-%m-%d"):
        """将文本转换为日期时间对象。"""
        if not text or not str(text).strip():
            raise ValueError("待转换文本不能为空")
        text = str(text).strip()
        if parse_type == ParseTimeType.CUSTOM and custom_format:
            parsed = datetime.strptime(text, custom_format)
        else:
            normalized = text
            for cn, en in (("年", "-"), ("月", "-"), ("日", " "), ("时", ":"), ("分", ":"), ("秒", "")):
                normalized = normalized.replace(cn, en)
            parsed = parser.parse(normalized)
        res = Date()
        res.time = parsed
        return res

    @staticmethod
    @atomicMg.atomic(
        "TimeProcess",
        inputList=[
            atomicMg.param(
                "time",
                types="Date",
                required=False,
                formType=AtomicFormTypeMeta(AtomicFormType.INPUT_VARIABLE_PYTHON_DATETIME.value),
            ),
        ],
        outputList=[atomicMg.param("datetime_info", types="Dict")],
    )
    def get_datetime_info(time: Date = None):
        """获取日期时间的详细信息。"""
        if time is None:
            time = Date()
        t = time.time
        weekday_names = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
        return {
            "年份": t.year,
            "月份": t.month,
            "天数": t.day,
            "小时": t.hour,
            "分钟": t.minute,
            "秒数": t.second,
            "星期": weekday_names[t.weekday()],
            "当月最后一天": calendar.monthrange(t.year, t.month)[1],
            "当年第几周": t.isocalendar()[1],
            "当年第几天": t.timetuple().tm_yday,
        }
