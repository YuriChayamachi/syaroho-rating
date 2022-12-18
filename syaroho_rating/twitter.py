import datetime as dt
import time
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple, Union

import pandas as pd
import pendulum
import tweepy
from tenacity import retry, stop_after_attempt, wait_exponential
from tweepy import Cursor, Stream
from tweepy.models import Status

from syaroho_rating.consts import (ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET,
                                   ACCOUNT_NAME, BEARER_TOKEN, CONSUMER_KEY,
                                   CONSUMER_SECRET, ENVIRONMENT_NAME,
                                   LIST_SLUG, SYAROHO_LIST_ID, invalid_clients,
                                   reply_patience)
from syaroho_rating.message import create_reply_message
from syaroho_rating.model import Tweet, User
from syaroho_rating.utils import tweetid_to_datetime
from syaroho_rating.visualize.graph import GraphMaker


def get_twitter(version: int) -> "Twitter":
    if version == 1:
        return TwitterV1()
    elif version == 2:
        return TwitterV2()
    else:
        raise ValueError(f"Unsupported version: {version}.")


def is_valid_client(client: str) -> bool:
    return client not in invalid_clients


RawInfo = Union[List[Dict[str, Any]], Dict[str, Any]]


class Twitter(Protocol):
    def fetch_result(self, date: pendulum.DateTime) -> Tuple[List[Tweet], RawInfo]:
        ...

    def fetch_result_dq(self) -> Tuple[List[Tweet], RawInfo]:
        ...

    def fetch_member(self) -> Tuple[List[User], RawInfo]:
        ...

    def add_members_to_list(self, users: List[User]) -> None:
        ...

    def post_with_multiple_media(
        self, message: str, media_list: List[str], **kwargs: Any
    ) -> None:
        ...

    def listen_and_reply(
        self, rating_infos: Dict[str, Any], summary_df: pd.DataFrame
    ) -> None:
        ...

    def update_status(self, message: str) -> None:
        ...

    def retweet(self, tweet_id: str) -> None:
        ...


class TwitterV1(Twitter):
    def __init__(
        self,
        consumer_key: str = CONSUMER_KEY,
        consumer_secret: str = CONSUMER_SECRET,
        access_token_key: str = ACCESS_TOKEN_KEY,
        access_token_secret: str = ACCESS_TOKEN_SECRET,
    ) -> None:
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


def handle_reply(
    tweet: Tweet,
    replied_list: List[str],
    rating_info: Dict[str, Any],
    rating_summary: pd.DataFrame,
    twitter: Twitter,
) -> None:
    name_jp = tweet.author.name
    name = tweet.author.username
    tweet_id = str(tweet.id)
    text = tweet.text
    reply_time = tweetid_to_datetime(tweet_id)  # type: pendulum.DateTime
    delta_second = (pendulum.now("Asia/Tokyo") - reply_time).total_seconds()

    already_replied = name in replied_list
    is_text_valid = (
        (text.find("ランク") > -1)
        or (text.find("らんく") > -1)
        or (text.lower().find("rank") > -1)
    )
    if (
        already_replied
        or (delta_second >= reply_patience)
        or (name == ACCOUNT_NAME)
        or not is_text_valid
    ):
        print(f"skip replying to {name}: {text}")
        return

    # 機械的に生成されるグラフファイル名を取得
    fname = GraphMaker.get_savepath(name)

    # グラフは参加者のものだけ生成しているので、ファイルの有無で当日の参加者か判別
    # 参加者でない場合はスキップ
    name_r = name.replace("@", "＠")
    if not fname.exists():
        print(f"@{name_r} didn't participate today. skip.")
        replied_list.append(name)
        return

    print("Sending a reply to @" + name)
    result = rating_info[name]
    message = create_reply_message(
        name_r=name_r,
        name_jp=name_jp,
        best_time=result["best_time"],
        highest=result["highest"],
        rating=result["rate"],
        rank_all=len(rating_summary.index),
        rank=rating_summary["Rank"][name],
        match=rating_summary["Match"][name],
        win=rating_summary["Win"][name],
    )
    twitter.post_with_multiple_media(
        message, media_list=[str(fname)], in_reply_to_status_id=tweet_id
    )
    replied_list.append(name)
    return


class Listener(Stream):
    def __init__(
        self,
        rating_info: Dict[str, Any],
        rating_summary: pd.DataFrame,
        twitter: TwitterV1,
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
        tweet = Tweet.from_responses_v1([status._json])

        if not tweet:
            return

        handle_reply(
            tweet=tweet[0],
            replied_list=self.replied_list,
            rating_info=self.rating_info,
            rating_summary=self.rating_summary,
            twitter=self.twitter,
        )


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
    # "non_public_metrics",  # these are private attributes
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


class TwitterV2(Twitter):
    def __init__(self) -> None:
        # api v1.1 (v2 でサポートされていない機能用)
        auth = tweepy.OAuth1UserHandler(
            CONSUMER_KEY,
            CONSUMER_SECRET,
            ACCESS_TOKEN_KEY,
            ACCESS_TOKEN_SECRET,
        )
        self.apiv1 = tweepy.API(auth)

        # api v2
        self.client = tweepy.Client(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=ACCESS_TOKEN_KEY,
            access_token_secret=ACCESS_TOKEN_SECRET,
        )

    def update_status(self, message: str) -> None:
        self.client.create_tweet(text=message)
        return

    def retweet(self, tweet_id: str) -> None:
        self.client.retweet(tweet_id)
        return

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
            max_results=100,  # system limit
            expansions=EXPANSIONS,
            media_fields=MEDIA_FIELDS,
            place_fields=PLACE_FIELDS,
            poll_fields=POLL_FIELDS,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            start_time=start_time,
            end_time=end_time,
            limit=5,
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

    @staticmethod
    def resp_to_dict(
        data: Union[Iterable[tweepy.Tweet], Iterable[tweepy.User]],
        medias: Iterable[tweepy.Media],
        places: Iterable[tweepy.Place],
        polls: Iterable[tweepy.Poll],
        tweets: Iterable[tweepy.Tweet],
        users: Iterable[tweepy.User],
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

    def fetch_result(
        self, date: pendulum.DateTime
    ) -> Tuple[List[Tweet], Dict[str, Any]]:
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
            limit=5,
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

    def fetch_result_dq(self) -> Tuple[List[Tweet], Dict[str, Any]]:
        tweets, all_info_dict = self.fetch_list_tweets(list_id=SYAROHO_LIST_ID)
        return tweets, all_info_dict

    def fetch_list_member(self, list_id: str) -> Tuple[List[User], Dict[str, Any]]:
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
            limit=5,
        ):
            data += response.data
            tweets += response.includes.get("tweets", [])
        users = User.from_responses_v2(users=data)
        all_info_dict = self.resp_to_dict(
            data=data, medias=None, places=None, polls=None, tweets=tweets, users=None
        )
        return users, all_info_dict

    def fetch_member(self) -> Tuple[List[User], Dict[str, Any]]:
        users, all_info_dict = self.fetch_list_member(list_id=SYAROHO_LIST_ID)
        return users, all_info_dict

    def add_members_to_list(self, users: List[User]) -> None:
        for u in users:
            self.client.add_list_member(
                id=SYAROHO_LIST_ID,
                user_id=u.id,
            )

    def post_with_multiple_media(
        self, message: str, media_list: List[str], **kwargs: Any
    ) -> None:
        media_ids = []
        for media in media_list:
            res = self.apiv1.media_upload(media)
            media_ids.append(res.media_id)

        self.apiv1.update_status(status=message, media_ids=media_ids, **kwargs)
        return

    def close_stream(self, client: tweepy.StreamingClient) -> None:
        rules = client.get_rules()
        client.delete_rules(rules.data)
        client.disconnect()

    def listen_and_reply(
        self, rating_infos: Dict[str, Any], summary_df: pd.DataFrame
    ) -> None:
        client = ReplyStreaming(
            rating_info=rating_infos,
            rating_summary=summary_df,
            twitter=self,
        )

        # リプとメンションを拾う
        query = f"to:{ACCOUNT_NAME} OR @{ACCOUNT_NAME}"
        client.add_rules(tweepy.StreamRule(query))
        client.filter(
            expansions=EXPANSIONS,
            media_fields=MEDIA_FIELDS,
            place_fields=PLACE_FIELDS,
            poll_fields=POLL_FIELDS,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            threaded=True,
        )

        # 10分後にストリーミングを終了
        time.sleep(dt.timedelta(minutes=10).total_seconds())
        self.close_stream(client)

    def listen_to_syaroho(self) -> tweepy.StreamingClient:
        client = SyarohoStreaming()
        query = ""
        client.add_rules(tweepy.StreamRule(query))

        client.filter(
            expansions=EXPANSIONS,
            media_fields=MEDIA_FIELDS,
            place_fields=PLACE_FIELDS,
            poll_fields=POLL_FIELDS,
            tweet_fields=TWEET_FIELDS,
            user_fields=USER_FIELDS,
            threaded=True,
        )
        return client


class ReplyStreaming(tweepy.StreamingClient):
    def __init__(
        self,
        rating_info: Dict[str, Any],
        rating_summary: pd.DataFrame,
        twitter: TwitterV2,
    ):
        super(ReplyStreaming, self).__init__(BEARER_TOKEN)
        self.rating_info = rating_info
        self.rating_summary = rating_summary.reset_index().set_index("User")
        self.twitter = twitter
        self.replied_list: List[str] = []

    def on_response(self, response: tweepy.Response) -> None:
        data = response.data
        users = response.includes["users"]
        tweet = Tweet.from_responses_v2(tweets=[data], users=users)
        print(tweet)

        if not tweet:
            return

        handle_reply(
            tweet=tweet[0],
            replied_list=self.replied_list,
            rating_info=self.rating_info,
            rating_summary=self.rating_summary,
            twitter=self.twitter,
        )


class SyarohoStreaming(tweepy.StreamingClient):
    def __init__(self) -> None:
        super(SyarohoStreaming, self).__init__(BEARER_TOKEN)
        # for syaroho
        self.tweets: List[Tweet] = []

        # for saving information
        self.raw_data: List[tweepy.Tweet] = []
        self.raw_medias: List[tweepy.Media] = []
        self.raw_places: List[tweepy.Place] = []
        self.raw_polls: List[tweepy.Poll] = []
        self.raw_tweets: List[tweepy.Tweet] = []
        self.raw_users: List[tweepy.User] = []

    def on_response(self, response: tweepy.Response) -> None:
        print(f"[on_response] {response}")
        data = response.data
        users = response.includes["users"]
        tweets = Tweet.from_responses_v2(tweets=[data], users=users)
        self.tweets += tweets

        self.raw_data.append(response.data)
        self.raw_medias += response.includes.get("medias", [])
        self.raw_places += response.includes.get("places", [])
        self.raw_polls += response.includes.get("polls", [])
        self.raw_tweets += response.includes.get("tweets", [])
        self.raw_users += response.includes.get("users", [])

    def get_data_dict(self) -> Dict[str, Any]:
        return TwitterV2.resp_to_dict(
            data=self.raw_data,
            medias=self.raw_medias,
            places=self.raw_places,
            polls=self.raw_polls,
            tweets=self.raw_tweets,
            users=self.raw_users,
        )
