from typing import Dict, List, Tuple

import pandas as pd
import pendulum
from tweepy.errors import Forbidden

from syaroho_rating.io_handler import IOHandler
from syaroho_rating.model import Tweet, User
from syaroho_rating.rating import calc_rating_for_date, summarize_rating_info
from syaroho_rating.twitter import Twitter
from syaroho_rating.utils import timedelta_to_ms, tweetid_to_datetime
from syaroho_rating.visualize.graph import GraphMaker
from syaroho_rating.visualize.table import TableMaker


def filter_and_sort(
    statuses: List[Tweet], date: pendulum.DateTime
) -> List[Dict]:
    # 参加者リストの作成
    participants = []
    for s in statuses:
        if not ((s.text == "しゃろほー")):
            continue

        rawtime = tweetid_to_datetime(s.id)
        time = rawtime.strftime("%S.%f")[:-3]

        record = timedelta_to_ms(rawtime - date)
        bouns = 1000 if record >= 0 else 0
        score = bouns - abs(record)
        participants.append(
            {
                "screen_name": ("" + s.author.username),
                "time": time,
                "score": score,
            }
        )
    df = (
        pd.DataFrame(participants, columns=["screen_name", "time", "score"])
        .sort_values("score", ascending=False)
        .reset_index(drop=True)
    )
    sorted_posts = df.iloc[:5].to_dict(orient="records")
    return sorted_posts


class Syaroho(object):
    def __init__(self, twitter: Twitter, io_handler: IOHandler):
        self.twitter = twitter
        self.io = io_handler

    def _fetch_and_save_result(self, date: pendulum.DateTime) -> List[Tweet]:
        statuses, raw_response = self.twitter.fetch_result(date)

        self.io.save_statuses(raw_response, date)
        return statuses

    def _fetch_and_save_result_dq(self, date: pendulum.DateTime) -> List[Tweet]:
        statuses, raw_response = self.twitter.fetch_result_dq()

        self.io.save_statuses_dq(raw_response, date)
        return statuses

    def _fetch_and_save_member(self) -> List[User]:
        users, raw_response = self.twitter.fetch_member()

        self.io.save_members(raw_response)
        return users

    def _add_new_member(self, statuses: List[Tweet], users: List[User]) -> None:
        existing_user_names = [u.username for u in users]

        competitor_names = [
            s.author.username for s in statuses if s.text == "しゃろほー"
        ]

        new_member_names = set(competitor_names) - set(existing_user_names)
        new_members = [u for u in users if u.username in new_member_names]

        if len(new_members):
            self.twitter.add_members_to_list(list(new_members))
            print(f"{len(new_members)} members added to list.")
        else:
            print("no new members.")
        return

    def run_dq(self, do_post: bool = False) -> List[Tweet]:
        today = pendulum.today("Asia/Tokyo")
        statuses = self._fetch_and_save_result_dq(today)
        posts = filter_and_sort(statuses, today)

        messages = [f"SYAROHO PRE-RESULT ({today.strftime('%Y/%m/%d')})"]
        if len(posts) == 0:
            messages.append("速報データを取得できませんでした。")
        else:
            for p in posts[:5]:
                messages.append(f"{p['time']} {p['screen_name']}")

        message = "\n".join(messages)
        if do_post:
            self.twitter.update_status(message)
        return statuses

    def run(
        self,
        date: pendulum.DateTime,
        dq_statuses: List[Tweet],
        fetch_tweet: bool = True,
        do_post: bool = False,
        do_retweet: bool = False,
        exag: float = 1.0,
    ) -> Tuple[pd.DataFrame, Dict]:
        if fetch_tweet:
            print(f"Fetching tweets of date {date} ...")
            statuses = self._fetch_and_save_result(date)
            print(f"Loaded {len(statuses)} tweets.")
        else:
            print(f"Loading tweets of date {date} from storage ...")
            statuses = self.io.get_statuses(date)
            print(f"Loaded {len(statuses)} tweets.")

        # 前日のレーティング結果を読み込む
        try:
            print(f"Loading previous rating infos...")
            prev_rating_infos = self.io.get_rating_info(date.subtract(days=1))
            print(
                f"Loaded previous rating containing {len(prev_rating_infos)} rows."
            )
        except FileNotFoundError:
            print("No prev rating info found. Use empty list instead.")
            prev_rating_infos = dict()

        # 当日のレーティングを計算
        print(f"Calculating rating for date {date}...")
        daily_ratings, rating_infos = calc_rating_for_date(
            date, statuses, dq_statuses, prev_rating_infos, exag
        )
        print(f"Saving rating info...")
        self.io.save_rating_info(rating_infos, date)
        print("Done.")

        # convert rating results to dataframe
        pd.options.display.notebook_repr_html = True
        df = pd.json_normalize(daily_ratings)
        df = df.rename(
            columns={
                "rank_normal": "Rank",
                "screen_name": "Name",
                "time": "Record",
                "perf": "Perf.",
                "rating": "Rating",
                "change": "Change",
            }
        )
        print(f">>>>>>>>>> The Result for date {date} >>>>>>>>>>")
        print(df)
        df = df.sort_values("Rank").reset_index(drop=True)
        df_result = df[["Rank", "Name", "Record", "Perf.", "Rating", "Change"]]
        print(df_result)
        print(f"<<<<<<<<<< The Result for date {date} <<<<<<<<<<")

        # add members
        if fetch_tweet:
            print("Fetching current list members...")
            all_members = self._fetch_and_save_member()
            print("Done.")
        else:
            print("Loading current list members from storage...")
            all_members = self.io.get_members()
            print("Done.")
        print(f"Adding today's participants to member list...")
        self._add_new_member(statuses, all_members)
        print("Done.")

        if do_retweet:
            print("Retweeting winner's status...")
            self._retweet_winners(df)
            print("Done.")

        if do_post:
            # make table for result tweet
            print("Creating result table...")
            tm = TableMaker(df_result, date)
            table_paths = tm.make()
            table_paths_str = [str(p) for p in table_paths]
            print("Done.")

            print("Posting today's result...")
            message = tm._make_header()
            self.twitter.post_with_multiple_media(message, table_paths_str)
            print("Created table paths: ", table_paths)
            print("Done.")

            # create graphs for reply
            print("Creating result graph for each participants...")
            attend_users = [u["screen_name"] for u in daily_ratings]
            gm = GraphMaker(rating_infos)
            gm.draw_graph_users(attend_users)
            print("Done.")

        print("Summarizing result...")
        summary_df = summarize_rating_info(rating_infos)
        print("Done.")

        return summary_df, rating_infos

    def _retweet_winners(self, df_ratings: pd.DataFrame) -> None:
        df_top = df_ratings[df_ratings["Rank"] == 1].reset_index()
        for i, row in df_top.iterrows():
            try:
                print(f"Retweeting tweet id {row.id}")
                self.twitter.retweet(row.id)
            except Forbidden as e:
                print(e)
                print(f"Retweet is not permissive for user {row.id}. Skip.")
        return

    def reply_to_mentions(
        self, summary_df: pd.DataFrame, rating_infos: Dict
    ) -> None:
        self.twitter.listen_and_reply(rating_infos, summary_df)
        return

    def backfill(
        self,
        start_date: pendulum.DateTime,
        end_date: pendulum.DateTime,
        do_post: bool = False,
        do_retweet: bool = False,
        fetch_tweet: bool = False,
        exag_start: bool = False,
    ) -> None:
        for i, date in enumerate(
            pendulum.period(start_date, end_date).range("days")
        ):
            print(f"Executing backfill for {date}...")
            try:
                dq_statuses = self.io.get_statuses_dq(date)
            except FileNotFoundError:
                print("no status_dq file found")
                dq_statuses = []
                pass
            if i == 0 and exag_start:
                self.run(
                    date,
                    dq_statuses,
                    fetch_tweet,
                    do_post,
                    do_retweet,
                    exag=1.5,
                )
            else:
                self.run(date, dq_statuses, fetch_tweet, do_post, do_retweet)
        print("done.")

    def fetch_and_save_tweet(
        self, date: pendulum.DateTime, save: bool = False
    ) -> None:
        _, raw_response = self.twitter.fetch_result(date)
        print(raw_response)
        if save:
            self.io.save_statuses(raw_response, date)
        return
