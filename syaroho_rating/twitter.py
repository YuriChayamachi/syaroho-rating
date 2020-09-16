import datetime as dt
from typing import List, Dict

import pandas as pd
import pendulum
import tweepy
from tweepy import Cursor
from timeout_decorator import timeout

from syaroho_rating.consts import (
    invalid_clients,
    CONSUMER_KEY,
    CONSUMER_SECRET,
    ACCESS_TOKEN_KEY,
    ACCESS_TOKEN_SECRET,
    ENVIRONMENT_NAME,
    ACCOUNT_NAME,
    LIST_SLUG,
    reply_patience,
)
from syaroho_rating.utils import tweetid_to_datetime, classes
from syaroho_rating.visualize.graph import GraphMaker


def is_valid_client(client: str) -> bool:
    return client not in invalid_clients


class Twitter(object):
    def __init__(self):
        auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        auth.set_access_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
        self.api = tweepy.API(auth)

    def fetch_result(self, date) -> List:
        target_date = pendulum.instance(date, "Asia/Tokyo")
        from_date = target_date.subtract(minutes=1)
        to_date = target_date.add(minutes=1)
        result = [
            x._json
            for x in Cursor(
                self.api.search_30_day,
                environment_name=ENVIRONMENT_NAME,
                query="しゃろほー",
                fromDate=from_date.in_tz("utc").strftime("%Y%m%d%H%M"),
                toDate=to_date.in_tz("utc").strftime("%Y%m%d%H%M"),
            ).items(500)
        ]
        return result

    def fetch_result_dq(self) -> List:
        result = [
            x._json
            for x in Cursor(
                self.api.list_timeline,
                owner_screen_name=ACCOUNT_NAME,
                slug=LIST_SLUG,
                include_rts=False,
            ).items(1000)
        ]
        return result

    def fetch_member(self) -> List:
        result = [
            x._json
            for x in Cursor(
                self.api.list_members, owner_screen_name=ACCOUNT_NAME, slug=LIST_SLUG
            ).items(1000)
        ]
        return result

    def add_members_to_list(self, screen_names: List[str]):
        self.api.add_list_members(
            screen_name=screen_names, slug=LIST_SLUG, owner_screen_name=ACCOUNT_NAME
        )
        return

    def post_with_multiple_media(self, message: str, media_list: List[str], **kwargs):
        media_ids = []
        for media in media_list:
            res = self.api.media_upload(media)
            media_ids.append(res.media_id)

        self.api.update_status(status=message, media_ids=media_ids, **kwargs)
        return

    @timeout(60 * 10)
    def listen_and_reply(self, rating_infos, summary_df):
        listener = Listener(rating_infos, summary_df, self)
        stream = tweepy.Stream(self.api.auth, listener)
        stream.filter(track=["@" + ACCOUNT_NAME])


class Listener(tweepy.StreamListener):
    def __init__(
        self, rating_info: Dict, rating_summary: pd.DataFrame, twitter: Twitter
    ):
        super().__init__(self)
        self.rating_info = rating_info
        self.rating_summary = rating_summary
        self.twitter = twitter
        self.replied_list = []

    def on_status(self, status: Dict):
        name_jp = status["user"]["name"]
        name = status["user"]["screen_name"]
        tweet_id = str(status["id"])
        text = status["text"]
        reply_time = tweetid_to_datetime(status["id"])
        delta_second = (dt.datetime.now() - reply_time).seconds

        if (
            (tweet_id in self.replied_list)
            or (status["favorited"] == True)
            or (delta_second >= reply_patience)
            or (name == ACCOUNT_NAME)
        ):
            print(f"skip replying to {name}")
            return

        if (
            (text.find("ランク") > -1)
            or (text.find("らんく") > -1)
            or (text.lower().find("rank") > -1)
        ):
            print("Sending a reply to @" + name)

            result = self.rating_info[name]
            best_time = result["best_time"]
            highest = result["highest"]
            rating = result["rate"]
            rank_all = len(self.rating_summary.index)
            rank = self.rating_summary["Rank"][name]
            match = self.rating_summary["Match"][name]
            win = self.rating_summary["Win"][name]

            name_r = name.replace("@", "＠")

            s0 = "@" + name_r + "\n"
            s1 = name_jp + " (しゃろほー" + classes(highest) + ")\n"
            s2 = "レーティング: " + str(rating) + " (最高: " + str(highest) + ")" + "\n"
            s3 = "順位: " + str(rank) + " / " + str(rank_all) + "\n"
            s4 = "優勝 / 参加回数: " + str(win) + " / " + str(match) + "\n"
            s5 = "ベスト記録: " + str(best_time)
            s_all = s0 + s1 + s2 + s3 + s4 + s5

            fname = GraphMaker.get_savepath(name)

            self.twitter.post_with_multiple_media(
                s_all, media_list=[str(fname)], in_reply_to_status_id=tweet_id
            )
            self.replied_list.append(tweet_id)
            return


if __name__ == "__main__":
    # test(API を消費してしまうので単体テストは個別で行う)

    twitter = Twitter()
    res = twitter.fetch_result(pendulum.today("Asia/Tokyo"))
    print(res)
