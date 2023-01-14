import datetime as dt
import time
from typing import Dict, List

import pandas as pd
import pendulum
import tweepy
from tenacity import retry, wait_exponential
from tweepy import Cursor, Stream
from tweepy.models import Status

from syaroho_rating.consts import (
    ACCESS_TOKEN_KEY,
    ACCESS_TOKEN_SECRET,
    ACCOUNT_NAME,
    CONSUMER_KEY,
    CONSUMER_SECRET,
    ENVIRONMENT_NAME,
    LIST_SLUG,
    invalid_clients,
    reply_patience,
)
from syaroho_rating.utils import classes, tweetid_to_datetime
from syaroho_rating.visualize.graph import GraphMaker


def is_valid_client(client: str) -> bool:
    return client not in invalid_clients


class Twitter(object):
    def __init__(
        self,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token_key=ACCESS_TOKEN_KEY,
        access_token_secret=ACCESS_TOKEN_SECRET,
    ):
        self.__consumer_key = consumer_key
        self.__consumer_secret = consumer_secret
        self.__access_token_key = access_token_key
        self.__access_token_secret = access_token_secret
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token_key, access_token_secret)
        self.__api = tweepy.API(auth)

    @retry(wait=wait_exponential(multiplier=1, min=1, max=60))
    def fetch_result(self, date) -> List:
        target_date = pendulum.instance(date, "Asia/Tokyo")
        from_date = target_date.subtract(minutes=1)
        to_date = target_date.add(minutes=1)
        result = [
            x._json
            for x in Cursor(
                self.__api.search_30_day,
                label=ENVIRONMENT_NAME,
                query="しゃろほー",
                fromDate=from_date.in_tz("utc").strftime("%Y%m%d%H%M"),
                toDate=to_date.in_tz("utc").strftime("%Y%m%d%H%M"),
            ).items(500)
        ]
        return result

    @retry(wait=wait_exponential(multiplier=1, min=1, max=60))
    def fetch_result_dq(self) -> List:
        result = [
            x._json
            for x in Cursor(
                self.__api.list_timeline,
                owner_screen_name=ACCOUNT_NAME,
                slug=LIST_SLUG,
                include_rts=False,
            ).items(1000)
        ]
        return result

    @retry(wait=wait_exponential(multiplier=1, min=1, max=60))
    def fetch_member(self) -> List:
        result = [
            x._json
            for x in Cursor(
                self.__api.get_list_members,
                owner_screen_name=ACCOUNT_NAME,
                slug=LIST_SLUG,
            ).items(1000)
        ]
        return result

    @retry(wait=wait_exponential(multiplier=1, min=1, max=60))
    def add_members_to_list(self, screen_names: List[str]):
        self.__api.add_list_members(
            screen_name=screen_names, slug=LIST_SLUG, owner_screen_name=ACCOUNT_NAME
        )
        return

    @retry(wait=wait_exponential(multiplier=1, min=1, max=60))
    def post_with_multiple_media(self, message: str, media_list: List[str], **kwargs):
        media_ids = []
        for media in media_list:
            res = self.__api.media_upload(media)
            media_ids.append(res.media_id)

        self.__api.update_status(status=message, media_ids=media_ids, **kwargs)
        return

    def listen_and_reply(self, rating_infos, summary_df):
        stream = Listener(rating_infos, summary_df, self)
        # 大量のリプに対処するため非同期で処理
        stream.filter(track=["@" + ACCOUNT_NAME], threaded=True)

        # 10分後にストリーミングを終了
        time.sleep(dt.timedelta(minutes=10).total_seconds())
        stream.disconnect()
        return

    @retry(wait=wait_exponential(multiplier=1, min=1, max=60))
    def retweet(self, tweet_id):
        self.__api.retweet(tweet_id)
        return

    @retry(wait=wait_exponential(multiplier=1, min=1, max=60))
    def update_status(self, message):
        self.__api.update_status(message)
        return


class Listener(Stream):
    def __init__(
        self, rating_info: Dict, rating_summary: pd.DataFrame, twitter: Twitter
    ):
        super().__init__(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN_KEY,
            access_token_secret=ACCESS_TOKEN_SECRET,
        )
        self.rating_info = rating_info
        self.rating_summary = rating_summary.reset_index().set_index("User")
        self.twitter = twitter
        self.replied_list = []

    def on_status(self, status: Status):
        name_jp = status.author.name
        name = status.author.screen_name
        tweet_id = str(status.id)
        text = status.text
        reply_time = tweetid_to_datetime(status.id)  # type: pendulum.DateTime
        delta_second = (pendulum.now("Asia/Tokyo") - reply_time).total_seconds()

        if (
            (name in self.replied_list)
            or (status.favorited is True)
            or (delta_second >= reply_patience)
            or (name == ACCOUNT_NAME)
        ):
            print(f"skip replying to {name}: {text}")
            return

        if (
            (text.find("ランク") > -1)
            or (text.find("らんく") > -1)
            or (text.lower().find("rank") > -1)
        ):
            # 機械的に生成されるグラフファイル名を取得
            fname = GraphMaker.get_savepath(name)

            # グラフは参加者のものだけ生成しているので、ファイルの有無で当日の参加者か判別
            # 参加者でない場合はスキップ
            name_r = name.replace("@", "＠")
            if not fname.exists():
                print(f"@{name_r} didn't participate today. skip.")
                self.replied_list.append(name)
                return

            print("Sending a reply to @" + name)

            result = self.rating_info[name]
            best_time = result["best_time"]
            highest = result["highest"]
            rating = result["rate"]
            rank_all = len(self.rating_summary.index)
            rank = self.rating_summary["Rank"][name]
            match = self.rating_summary["Match"][name]
            win = self.rating_summary["Win"][name]

            s0 = "@" + name_r + "\n"
            s1 = name_jp + " (しゃろほー" + classes(highest) + ")\n"
            s2 = "レーティング: " + str(rating) + " (最高: " + str(highest) + ")" + "\n"
            s3 = "順位: " + str(rank) + " / " + str(rank_all) + "\n"
            s4 = "優勝 / 参加回数: " + str(win) + " / " + str(match) + "\n"
            s5 = "ベスト記録: " + str(best_time)
            s_all = s0 + s1 + s2 + s3 + s4 + s5

            self.twitter.post_with_multiple_media(
                s_all, media_list=[str(fname)], in_reply_to_status_id=tweet_id
            )
            self.replied_list.append(name)
            return
        else:
            print(f"skip replying to {name}: {text}")
            return


if __name__ == "__main__":
    # test(API を消費してしまうので単体テストは個別で行う)

    twitter = Twitter()
    res = twitter.fetch_result(pendulum.today("Asia/Tokyo"))
    print(res)
