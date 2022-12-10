import datetime as dt
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pendulum
import tweepy
from tenacity import retry, stop_after_attempt, wait_exponential
from tweepy import Cursor, Stream
from tweepy.models import Status

from syaroho_rating.consts import (ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET,
                                   ACCOUNT_NAME, BEARER_TOKEN, CONSUMER_KEY,
                                   CONSUMER_SECRET, ENVIRONMENT_NAME,
                                   LIST_SLUG, invalid_clients, reply_patience)
from syaroho_rating.model import Tweet, User
from syaroho_rating.utils import classes, tweetid_to_datetime
from syaroho_rating.visualize.graph import GraphMaker


def is_valid_client(client: str) -> bool:
    return client not in invalid_clients


class Twitter(object):
    def __init__(
        self,
        consumer_key: str = CONSUMER_KEY,
        consumer_secret: str = CONSUMER_SECRET,
        access_token_key: str = ACCESS_TOKEN_KEY,
        access_token_secret: str = ACCESS_TOKEN_SECRET,
    ) -> None:
        self.__consumer_key = consumer_key
        self.__consumer_secret = consumer_secret
        self.__access_token_key = access_token_key
        self.__access_token_secret = access_token_secret
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token_key, access_token_secret)
        self.__api = tweepy.API(auth)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60), stop=stop_after_attempt(5)
    )
    def fetch_result(
        self, date: pendulum.DateTime
    ) -> Tuple[List[Tweet], List[Dict[str, Any]]]:
        target_date = pendulum.instance(date, "Asia/Tokyo")
        from_date = target_date.subtract(minutes=1)
        to_date = target_date.add(minutes=1)
        raw_response = [
            x._json
            for x in Cursor(
                self.__api.search_30_day,
                label=ENVIRONMENT_NAME,
                query="しゃろほー",
                fromDate=from_date.in_tz("utc").strftime("%Y%m%d%H%M"),
                toDate=to_date.in_tz("utc").strftime("%Y%m%d%H%M"),
            ).items(500)
        ]
        tweets = Tweet.from_responses_v1(raw_response)
        return tweets, raw_response

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60), stop=stop_after_attempt(5)
    )
    def fetch_result_dq(self) -> Tuple[List[Tweet], List[Dict[str, Any]]]:
        raw_response = [
            x._json
            for x in Cursor(
                self.__api.list_timeline,
                owner_screen_name=ACCOUNT_NAME,
                slug=LIST_SLUG,
                include_rts=False,
            ).items(1000)
        ]
        tweets = Tweet.from_responses_v1(raw_response)
        return tweets, raw_response

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60), stop=stop_after_attempt(5)
    )
    def fetch_member(self) -> Tuple[List[User], List[Dict[str, Any]]]:
        raw_response = [
            x._json
            for x in Cursor(
                self.__api.get_list_members,
                owner_screen_name=ACCOUNT_NAME,
                slug=LIST_SLUG,
            ).items(1000)
        ]
        users = User.from_responses_v1(raw_response)
        return users, raw_response

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60), stop=stop_after_attempt(5)
    )
    def add_members_to_list(self, users: List[User]) -> None:
        screen_names = [u.username for u in users]
        self.__api.add_list_members(
            screen_name=screen_names, slug=LIST_SLUG, owner_screen_name=ACCOUNT_NAME
        )
        return

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60), stop=stop_after_attempt(5)
    )
    def post_with_multiple_media(
        self, message: str, media_list: List[str], **kwargs: Any
    ) -> None:
        media_ids = []
        for media in media_list:
            res = self.__api.media_upload(media)
            media_ids.append(res.media_id)

        self.__api.update_status(status=message, media_ids=media_ids, **kwargs)
        return

    def listen_and_reply(
        self, rating_infos: Dict[str, Any], summary_df: pd.DataFrame
    ) -> None:
        stream = Listener(rating_infos, summary_df, self)
        # 大量のリプに対処するため非同期で処理
        stream.filter(track=["@" + ACCOUNT_NAME], threaded=True)

        # 10分後にストリーミングを終了
        time.sleep(dt.timedelta(minutes=10).total_seconds())
        stream.disconnect()
        return

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60), stop=stop_after_attempt(5)
    )
    def retweet(self, tweet_id: str) -> None:
        self.__api.retweet(tweet_id)
        return

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=60), stop=stop_after_attempt(5)
    )
    def update_status(self, message: str) -> None:
        self.__api.update_status(message)
        return


class Listener(Stream):
    def __init__(
        self,
        rating_info: Dict[str, Any],
        rating_summary: pd.DataFrame,
        twitter: Twitter,
    ) -> None:
        super().__init__(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN_KEY,
            access_token_secret=ACCESS_TOKEN_SECRET,
        )
        self.rating_info = rating_info
        self.rating_summary = rating_summary.reset_index().set_index("User")
        self.twitter = twitter
        self.replied_list: List[str] = []

    def on_status(self, status: Status) -> None:
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


EXPANSIONS = [
    "attachments.poll_ids",
    "attachments.media_keys",
    "author_id",
    "edit_history_tweet_ids",
    "entities.mentions.username",
    "geo.place_id",
    "in_reply_to_user_id",
    "referenced_tweets.id",
    "referenced_tweets.id.author_id",
]
MEDIA_FIELDS = [
    "duration_ms",
    "height",
    "media_key",
    "preview_image_url",
    "type",
    "url",
    "width",
    "public_metrics",
    # "non_public_metrics",
    # "organic_metrics",
    # "promoted_metrics",
    "alt_text",
    "variants",
]
PLACE_FIELDS = [
    "contained_within",
    "country",
    "country_code",
    "full_name",
    "geo",
    "id",
    "name",
    "place_type",
]
POLL_FIELDS = ["duration_minutes", "end_datetime", "id", "options", "voting_status"]
TWEET_FIELDS = [
    "attachments",
    "author_id",
    "context_annotations",
    "conversation_id",
    "created_at",
    "edit_controls",
    "entities",
    "geo",
    "id",
    "in_reply_to_user_id",
    "lang",
    # "non_public_metrics",
    "public_metrics",
    # "organic_metrics",
    # "promoted_metrics",
    "possibly_sensitive",
    "referenced_tweets",
    "reply_settings",
    "source",
    "text",
    "withheld",
]
USER_FIELDS = [
    "created_at",
    "description",
    "entities",
    "id",
    "location",
    "name",
    "pinned_tweet_id",
    "profile_image_url",
    "protected",
    "public_metrics",
    "url",
    "username",
    "verified",
    "withheld",
]


class TwitterV2:
    def __init__(self):
        self.client = tweepy.Client(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN_KEY,
            access_token_secret=ACCESS_TOKEN_SECRET,
        )

    def update_status(self, message: str):
        response = self.client.create_tweet(text=message)
        return response

    def retweet(self, tweet_id: str):
        response = self.client.retweet(tweet_id)
        return response

    def fetch_tweets(
        self,
        query: str,
        start_time: Optional[pendulum.DateTime] = None,
        end_time: Optional[pendulum.DateTime] = None,
    ) -> Tuple[List[Tweet], Dict[str, Any]]:
        data: List[tweepy.Tweet] = []
        medias: List[tweepy.Media] = []
        places: List[tweepy.Place] = []
        polls: List[tweepy.Poll] = []
        tweets: List[tweepy.Tweet] = []
        users: List[tweepy.User] = []

        for response in tweepy.Paginator(
            self.client.search_recent_tweets,
            query=query,
            user_auth=True,
            max_results=500,  # system limit
            expansions=EXPANSIONS,
            media_fields=MEDIA_FIELDS,
            place_fields=PLACE_FIELDS,
            poll_fields=POLL_FIELDS,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            start_time=start_time,
            end_time=end_time,
        ):
            data += response.data
            medias += response.includes.get("medias", [])
            places += response.includes.get("places", [])
            polls += response.includes.get("polls", [])
            tweets += response.includes.get("tweets", [])
            users += response.includes.get("users", [])

        tweet_objects = Tweet.from_responses_v2(tweets=data, users=users)
        all_info_dict = self.resp_to_dict(data, medias, places, polls, tweets, users)
        return tweet_objects, all_info_dict

    def resp_to_dict(
        self, data, medias, places, polls, tweets, users
    ) -> Dict[str, Any]:
        # それぞれ data attribute に全情報の dict が入っている
        info_dict = {
            "data": [tweet.data for tweet in data],
            "includes": {},
        }
        if medias is not None:
            info_dict["includes"]["medias"] = [media.data for media in medias]
        if places is not None:
            info_dict["includes"]["places"] = [place.data for place in places]
        if polls is not None:
            info_dict["includes"]["polls"] = [poll.data for poll in polls]
        if tweets is not None:
            info_dict["includes"]["tweets"] = [tweet.data for tweet in tweets]
        if users is not None:
            info_dict["includes"]["users"] = [user.data for user in users]
        return info_dict

    def fetch_result(self, date) -> Tuple[List[Tweet], Dict[str, Any]]:
        target_date = pendulum.instance(date, "Asia/Tokyo")
        start_time = target_date.subtract(minutes=1)
        end_time = target_date.add(minutes=1)
        tweets, all_info_dict = self.fetch_tweets(
            query="しゃろほー -is:retweet",
            start_time=start_time,
            end_time=end_time,
        )
        return tweets, all_info_dict

    def fetch_list_tweets(self, list_id: str) -> Tuple[List[Tweet], Dict[str, Any]]:
        data: List[tweepy.Tweet] = []
        medias: List[tweepy.Media] = []
        places: List[tweepy.Place] = []
        polls: List[tweepy.Poll] = []
        tweets: List[tweepy.Tweet] = []
        users: List[tweepy.User] = []

        for response in tweepy.Paginator(
            self.client.get_list_tweets,
            id=list_id,
            user_auth=True,
            max_results=100,  # system limit
            expansions=EXPANSIONS,
            media_fields=MEDIA_FIELDS,
            place_fields=PLACE_FIELDS,
            poll_fields=POLL_FIELDS,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
        ):
            data += response.data
            medias += response.includes.get("medias", [])
            places += response.includes.get("places", [])
            polls += response.includes.get("polls", [])
            tweets += response.includes.get("tweets", [])
            users += response.includes.get("users", [])

        tweet_objects = Tweet.from_responses_v2(tweets=data, users=users)
        all_info_dict = self.resp_to_dict(data, medias, places, polls, tweets, users)
        return tweet_objects, all_info_dict

    def fetch_result_dq(self, date) -> Tuple[List[Tweet], Dict[str, Any]]:
        tweets, all_info_dict = self.fetch_list_tweets(list_id="")
        return tweets, all_info_dict

    def fetch_list_member(self, list_id: str):
        data: List[tweepy.User] = []
        tweets: List[tweepy.Tweet] = []
        for response in tweepy.Paginator(
            self.client.get_list_members,
            id=list_id,
            user_auth=True,
            max_results=100,  # system limit
            expansions=["pinned_tweet_id"],
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
        ):
            data += response.data
            tweets += response.includes.get("tweets", [])
        users = User.from_responses_v2(users=data)
        all_info_dict = self.resp_to_dict(
            data=data, medias=None, places=None, polls=None, tweets=tweets, users=None
        )
        return users, all_info_dict

    def fetch_member(self):
        users, all_info_dict = self.fetch_list_member(list_id="")
        return users, all_info_dict

    def add_members_to_list(self, users: List[User]):
        raise NotImplementedError

    def post_with_multiple_media(self, message: str, media_list: List[str], **kwargs):
        raise NotImplementedError

    def listen_and_reply(self, rating_infos, summary_df):
        raise NotImplementedError

    def listen(self, query: str):
        streaming_client = MyStreaming(BEARER_TOKEN)
        streaming_client.add_rules(tweepy.StreamRule(query))
        streaming_client.filter(
            expansions=EXPANSIONS,
            media_fields=MEDIA_FIELDS,
            place_fields=PLACE_FIELDS,
            poll_fields=POLL_FIELDS,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            threaded=True,
        )
        import time

        while True:
            time.sleep(10)
            print(
                f"Len of tweets: {len(streaming_client.tweets)}, len of users: {len(streaming_client.users)}"
            )


class MyStreaming(tweepy.StreamingClient):
    def __init__(self, *args, **kwargs):
        super(MyStreaming, self).__init__(*args, **kwargs)
        self.tweets = []
        self.users = []

    # def on_data(self, raw_data):
    #     super(MyStreaming, self).on_data(raw_data)
    #     print(f"[on_data] {raw_data}")

    # def on_tweet(self, tweet):
    #     print(f"[on_tweet] {tweet}")

    # def on_includes(self, includes):
    #     print(f"[on_includes] {includes}")

    # def on_matching_rules(self, matching_rules):
    #     print(f"[on_matching_rules] {matching_rules}")

    def on_response(self, response):
        print(f"[on_response] {response}")
        tweet = response.data
        users = response.includes["users"]
        print(tweet)
        print(users)
        self.tweets.append(tweet)
        self.users.append(users)
