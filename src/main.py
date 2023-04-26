import time
from datetime import timedelta

import click
import pendulum

from syaroho_rating.consts import (
    DEBUG,
    DO_POST,
    DO_RETWEET,
    SLACK_NOTIFY,
    TWITTER_API_VERSION,
    TZ,
)
from syaroho_rating.io_handler import get_io_handler
from syaroho_rating.slack import get_slack_notifier
from syaroho_rating.syaroho import Syaroho
from syaroho_rating.time import get_now, get_today
from syaroho_rating.twitter import get_twitter
from syaroho_rating.utils import parse_date_string


@click.group()
def cli() -> None:
    pass


@cli.command()
def run() -> None:
    """しゃろほーの集計"""
    now = get_now()
    today = get_today()  # 時刻を 0時0分 にした DateTime
    delta = now - today  # 日付が変わってから経過した時刻

    # 集計を行う日付
    if DEBUG:
        target_date = today
    else:
        if timedelta(seconds=0) < delta < timedelta(minutes=2):
            target_date = today
        else:
            target_date = today.add(days=1)
    target_date_str = target_date.strftime("%Y-%m-%d")
    print(
        f"========== Run Syaroho Rating. Target Date: {target_date_str} =========="
    )

    get_dummy_slack = not SLACK_NOTIFY
    slack = get_slack_notifier(dummy=get_dummy_slack)

    twitter = get_twitter(TWITTER_API_VERSION)
    io_handler = get_io_handler(TWITTER_API_VERSION)
    syaroho = Syaroho(twitter, io_handler)

    slack.notify_info(title=f"{target_date_str} しゃろほー観測開始", text="")

    try:
        # wait until 00:00:05 JST
        if not DEBUG and not (
            timedelta(seconds=5) < delta < timedelta(minutes=2)
        ):
            print(f"wait Until {target_date.add(seconds=5)}...")
            dur = target_date.add(seconds=5) - get_now()
            if dur.total_seconds() > 0:
                time.sleep(dur.total_seconds())

        # pre observe
        print(">>>>> pre observe")
        dq_statuses = syaroho.run_dq(do_post=DO_POST)

        # wait until 00:02:00 JST
        if not DEBUG:
            print(f"wait Until {target_date.add(minutes=2)}...")
            dur = target_date.add(minutes=2) - get_now()
            if dur.total_seconds() > 0:
                time.sleep(dur.total_seconds())

        # observe
        print(">>>>> observe")
        summary_df, rating_infos = syaroho.run(
            target_date,
            dq_statuses,
            fetch_tweet=True,
            do_post=DO_POST,
            do_retweet=DO_RETWEET,
        )

        # reply to mentions(10分間実行)
        print(">>>>> reply")
        syaroho.reply_to_mentions(summary_df, rating_infos)
        slack.notify_success(title=f"{target_date_str} しゃろほー観測完了", text="")
    except:
        import traceback

        trace = traceback.format_exc()
        errmsg = "\n".join(["<!channel>", trace])  # channel にメンション
        slack.notify_failed(title=f"{target_date_str} しゃろほーでエラー発生", text=errmsg)
        raise

    return


@cli.command()
@click.argument("start", type=str)
@click.argument("end", type=str)
@click.option("--eg-start", is_flag=True, type=bool)
@click.option("--fetch-tweet", is_flag=True, type=bool)
@click.option("--post", is_flag=True, type=bool)
@click.option("--retweet", is_flag=True, type=bool)
def backfill(
    start: str,
    end: str,
    eg_start: bool,
    fetch_tweet: bool,
    post: bool,
    retweet: bool,
) -> None:
    start_date = parse_date_string(start)
    end_date = parse_date_string(end)

    twitter = get_twitter(TWITTER_API_VERSION)
    io_handler = get_io_handler(TWITTER_API_VERSION)
    syaroho = Syaroho(twitter, io_handler)

    syaroho.backfill(start_date, end_date, post, retweet, fetch_tweet, eg_start)
    return


@cli.command()
@click.argument("date", type=str)
@click.option("--save", is_flag=True, type=bool)
def fetch_tweet(date: str, save: bool) -> None:
    date_parsed = parse_date_string(date)

    twitter = get_twitter(TWITTER_API_VERSION)
    io_handler = get_io_handler(TWITTER_API_VERSION)
    syaroho = Syaroho(twitter, io_handler)

    syaroho.fetch_and_save_tweet(date_parsed, save)


@cli.command(hidden=True)
def test_reply() -> None:
    today = get_today()
    twitter = get_twitter(TWITTER_API_VERSION)
    io_handler = get_io_handler(TWITTER_API_VERSION)
    syaroho = Syaroho(twitter, io_handler)
    rating_infos = io_handler.get_rating_info(today)

    from syaroho_rating.rating import summarize_rating_info

    summary_df = summarize_rating_info(rating_infos)
    print(summary_df)

    # reply to mentions(10分間実行)
    print(">>>>> reply")
    syaroho.reply_to_mentions(summary_df, rating_infos)
    return


if __name__ == "__main__":
    cli()
