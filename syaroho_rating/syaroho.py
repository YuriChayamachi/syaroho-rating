from typing import List, Dict, Tuple

import pandas as pd
import pendulum

from syaroho_rating.io_handler import IOHandlerBase
from syaroho_rating.rating import Rating
from syaroho_rating.twitter import Twitter, is_valid_client
from syaroho_rating.utils import clean_html_tag, timedelta_to_ms, tweetid_to_datetime
from syaroho_rating.visualize.graph import GraphMaker
from syaroho_rating.visualize.table import TableMaker


def filter_and_sort(statuses: List, date: pendulum.date) -> List[Dict]:
    # 参加者リストの作成
    participants = []
    for s in statuses:
        if not (
            (s["text"] == "しゃろほー") and is_valid_client(clean_html_tag(s["source"]))
        ):
            continue

        rawtime = tweetid_to_datetime(s["id"])
        time = rawtime.strftime("%S.%f")[:-3]

        record = timedelta_to_ms(rawtime - date)
        bouns = 1000 if record >= 0 else 0
        score = bouns - abs(record)
        participants.append(
            {
                "screen_name": ("" + s["user"]["screen_name"]),
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
    def __init__(self, twitter_api: Twitter, io_handler: IOHandlerBase):
        self.twitter = twitter_api
        self.io = io_handler

    def _fetch_and_save_result(self, date) -> List:
        result = self.twitter.fetch_result(date)

        self.io.save_statuses(result, date)
        return result

    def _fetch_and_save_result_dq(self, date) -> List:
        result = self.twitter.fetch_result_dq()

        self.io.save_statuses_dq(result, date)
        return result

    def _fetch_and_save_member(self) -> List:
        result = self.twitter.fetch_member()

        self.io.save_members(result)
        return result

    def _add_new_member(self, statuses: List, users: List):
        existing_user_names = [u["screen_name"] for u in users]

        competitor_names = [
            s["user"]["screen_name"]
            for s in statuses
            if s["text"] == "しゃろほー"
            # s["source"] is like "<a href="url_to_client">client_name</a>"
            and is_valid_client(clean_html_tag(s["source"]))
        ]

        new_members = set(competitor_names) - set(existing_user_names)

        if len(new_members):
            self.twitter.add_members_to_list(list(new_members))
            print(f"{len(new_members)} members added to list.")
        else:
            print("no new members.")
        return

    def pre_observe(self, do_post: bool = False):
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
            self.twitter.api.update_status(message)
        return statuses

    def observe(
        self, dq_statuses: List, do_post: bool = False, do_retweet: bool = False
    ) -> Tuple[pd.DataFrame, Dict]:
        today = pendulum.today("Asia/Tokyo")
        statuses = self._fetch_and_save_result(today)

        # calc ratings
        rtg = Rating(io_handler=self.io)
        daily_ratings = rtg.calc_rating_for_date(today, statuses, dq_statuses)

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
        print(df)
        df = df.sort_values("Rank").reset_index(drop=True)
        df_result = df[["Rank", "Name", "Record", "Perf.", "Rating", "Change"]]

        if do_retweet:
            self._retweet_winners(df)

        # make table for result tweet
        tm = TableMaker(df_result, today)
        table_paths = tm.make()
        table_paths = [str(p) for p in table_paths]

        # create graphs for reply
        rtg = Rating(io_handler=self.io)
        summary_df, rating_infos = rtg.get_summary_dataframe_and_infos(today)
        attend_users = [u["screen_name"] for u in daily_ratings]
        gm = GraphMaker(rating_infos)
        gm.draw_graph_users(attend_users)

        # add members
        all_members = self._fetch_and_save_member()
        self._add_new_member(statuses, all_members)

        # ツイートからリプライ受付までの時間が短くなるよう最後にツイート処理を行う
        if do_post:
            message = tm._make_header()
            self.twitter.post_with_multiple_media(message, table_paths)

        return summary_df, rating_infos

    def _retweet_winners(self, df_ratings: pd.DataFrame):
        df_top = df_ratings[df_ratings["Rank"] == 1].reset_index()
        for i, row in df_top.iterrows():
            self.twitter.api.retweet(row.id)
        return

    def reply_to_mentions(self, summary_df: pd.DataFrame, rating_infos: Dict):
        self.twitter.listen_and_reply(rating_infos, summary_df)
        return


if __name__ == "__main__":
    # test
    from syaroho_rating.io_handler import LocalIOHandler

    today = pendulum.datetime(2020, 5, 6, tz="Asia/Tokyo")
    io_handler = LocalIOHandler()
    rtg = Rating(io_handler=io_handler)
    summary_df, rating_infos = rtg.get_summary_dataframe_and_infos(today)
    print(summary_df)
