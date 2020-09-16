import time

import pendulum

from syaroho_rating.consts import DO_POST, DO_RETWEET, DEBUG
from syaroho_rating.io_handler import S3IOHandler
from syaroho_rating.syaroho import Syaroho
from syaroho_rating.twitter import Twitter

TZ = "Asia/Tokyo"


def main(debug=False):
    """0時0分JSTに呼ばれる"""
    twitter = Twitter()
    io_handler = S3IOHandler()
    syaroho = Syaroho(twitter, io_handler)

    today = pendulum.today(TZ)

    # wait until 00:00:05 JST
    if not debug:
        dur = pendulum.now(TZ) - today.replace(second=5)
        if dur.total_seconds() > 0:
            time.sleep(dur.total_seconds())

    # pre observe
    print("pre observe")
    dq_statuses = syaroho.pre_observe(do_post=DO_POST)

    # wait until 00:02:00 JST
    if not debug:
        dur = pendulum.now(TZ) - today.replace(minute=2)
        if dur.total_seconds() > 0:
            time.sleep(dur.total_seconds())

    # observe
    print("observe")
    attend_users = syaroho.observe(dq_statuses, do_post=DO_POST, do_retweet=DO_RETWEET)

    # reply to mentions(10分間実行)
    print("reply")
    syaroho.reply_to_mentions(attend_users)
    return


if __name__ == "__main__":
    main(debug=DEBUG)
