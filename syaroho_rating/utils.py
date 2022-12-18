import datetime as dt
import re
from typing import Union

import numpy as np
import pendulum

from syaroho_rating.consts import TZ, class_list, graph_colors, table_bg_colors


# 最高レーティングから段位を返す関数
def classes(rate: float) -> str:
    rate = int(rate)
    if rate >= 2000:
        rate_raw = rate + 1
        rank = max(0, int((4400.0 - rate_raw) / 200.0))
    elif rate >= 400:
        rate_raw = rate
        rank = max(0, int((4400.0 - rate_raw) / 200.0))
    elif rate > 0:
        rate_raw = 400.0 * (1.0 + np.log(rate / 400.0))
        rank = min(31, int((4400.0 - rate_raw) / 200.0))
    else:
        rank = -1
    return class_list[rank]


# 最新レーティングから色を返す関数
def colors(rate: float) -> str:
    for clr, low_rate, high_rate in graph_colors:
        if low_rate <= rate < high_rate:
            return clr
    return None


def perf_to_color(perf: Union[int, float]) -> np.ndarray:
    for c_def, low_rate, high_rate in table_bg_colors:
        if low_rate <= perf < high_rate:
            return np.array(c_def)
    return None


# timedeltaをミリ秒に変換する関数
def timedelta_to_ms(delta: dt.timedelta) -> float:
    ms = (delta.days * 86400 + delta.seconds) * 1000 + (delta.microseconds / 1000)
    return ms


def tweetid_to_datetime(tweetid: str) -> pendulum.DateTime:
    rawtime = pendulum.datetime(1970, 1, 1, tz="UTC") + dt.timedelta(
        milliseconds=int(int(tweetid) / 2**22) + 1288834974657
    )
    return rawtime.in_timezone("Asia/Tokyo")


def clean_html_tag(text: str) -> str:
    cleanr = re.compile("<.*?>")
    cleantext = re.sub(cleanr, "", text)
    return cleantext


def parse_date_string(date_str: str) -> pendulum.DateTime:
    parsed_date = pendulum.parse(date_str, tz=TZ)
    if not isinstance(parsed_date, pendulum.DateTime):
        raise RuntimeError(f"Failed parsing date string to DateTime: {date_str}")
    return parsed_date
