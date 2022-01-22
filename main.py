import time

import click
import pendulum

from syaroho_rating.consts import DO_POST, DO_RETWEET, DEBUG
from syaroho_rating.io_handler import get_io_handler
from syaroho_rating.syaroho import Syaroho
from syaroho_rating.twitter import Twitter

TZ = "Asia/Tokyo"


@click.group()
def cli():
    pass


@cli.command()
def run():
    """0時0分JSTに呼ばれる"""
    twitter = Twitter()
    io_handler = get_io_handler()
    syaroho = Syaroho(twitter, io_handler)

    today = pendulum.today(TZ)

    # wait until 00:00:05 JST
    if not DEBUG:
        dur = pendulum.now(TZ) - today.replace(second=5)
        if dur.total_seconds() > 0:
            time.sleep(dur.total_seconds())

    # pre observe
    print(">>>>> pre observe")
    dq_statuses = syaroho.run_dq(do_post=DO_POST)

    # wait until 00:02:00 JST
    if not DEBUG:
        dur = pendulum.now(TZ) - today.replace(minute=2)
        if dur.total_seconds() > 0:
            time.sleep(dur.total_seconds())

    # observe
    print(">>>>> observe")
    summary_df, rating_infos = syaroho.run(today, dq_statuses, fetch_tweet=True, 
                                           do_post=DO_POST, do_retweet=DO_RETWEET)

    # reply to mentions(10分間実行)
    print(">>>>> reply")
    syaroho.reply_to_mentions(summary_df, rating_infos)
    return


@cli.command()
@click.argument("start", type=str)
@click.argument("end", type=str)
@click.option("--eg-start", is_flag=True, type=bool)
@click.option("--fetch-tweet", is_flag=True, type=bool)
@click.option("--post", is_flag=True, type=bool)
@click.option("--retweet", is_flag=True, type=bool)
def backfill(start: str, end: str, eg_start: bool, fetch_tweet: bool,
             post: bool, retweet: bool):
    start_date = pendulum.parse(start, tz=TZ)
    end_date = pendulum.parse(end, tz=TZ)

    twitter = Twitter()
    io_handler = get_io_handler()
    syaroho = Syaroho(twitter, io_handler)

    syaroho.backfill(start_date, end_date, post, retweet, fetch_tweet, eg_start)
    return


@cli.command()
@click.argument("date", type=str)
@click.option("--save", is_flag=True, type=bool)
def fetch_tweet(date: str, save: bool):
    date = pendulum.parse(date, tz=TZ)

    twitter = Twitter()
    io_handler = get_io_handler()
    syaroho = Syaroho(twitter, io_handler)

    syaroho.fetch_and_save_tweet(date, save)


if __name__ == "__main__":
    cli()
