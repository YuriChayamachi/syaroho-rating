import datetime
from time import ctime
from zoneinfo import ZoneInfo

import ntplib
import pendulum

from syaroho_rating.consts import (
    NTP_SERVER_URI,
    NTPLIB_FORMAT,
    NTPLIB_VERSION,
    TZ,
)

client = ntplib.NTPClient()


def get_now() -> pendulum.DateTime:
    response = client.request(NTP_SERVER_URI, NTPLIB_VERSION)
    nowtime = datetime.datetime.strptime(ctime(response.tx_time), NTPLIB_FORMAT)
    return pendulum.instance(nowtime.astimezone(ZoneInfo(TZ)))


def get_today() -> pendulum.DateTime:
    now = get_now()
    return pendulum.datetime(now.year, now.month, now.day, tz=TZ)
