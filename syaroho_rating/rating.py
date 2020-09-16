import argparse
import copy
import math
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
import pendulum

from syaroho_rating.io_handler import IOHandlerBase
from syaroho_rating.twitter import is_valid_client
from syaroho_rating.utils import tweetid_to_datetime, clean_html_tag, timedelta_to_ms


class Rating(object):
    def __init__(self, io_handler: IOHandlerBase):
        self.io = io_handler

    def calc_rating_for_date(
        self,
        date: pendulum.date,
        statuses: List,
        dq_statuses: List = None,
        exag: float = 1.0,
    ) -> List:

        # 前日のレーティング結果を読み込む
        try:
            prev_rating_infos = self.io.get_rating_info(date.subtract(days=1))
        except FileNotFoundError:
            print("no prev rating info found")
            prev_rating_infos = dict()

        daily_infos, rating_infos = self._calc_rating_for_date(
            date, statuses, dq_statuses, prev_rating_infos, exag
        )

        self.io.save_rating_info(rating_infos, date)

        return daily_infos

    def _calc_rating_for_date(
        self,
        date: pendulum.date,
        statuses: List,
        dq_statuses: List,
        rating_infos: Dict,
        exag: float,
    ) -> Tuple[List, Dict]:

        # ある日の参加者リストの作成
        daily_infos = []
        player_list = []

        ymd = date.strftime("%Y%m%d")

        result = statuses
        for r in result:
            if (r["text"] == "しゃろほー") and is_valid_client(clean_html_tag(r["source"])):
                rawtime = tweetid_to_datetime(r["id"])
                time = rawtime.strftime("%H:%M:%S.%f")[:-3]

                record = timedelta_to_ms(rawtime - date)
                bouns = 1000 if record >= 0 else 0
                score = bouns - abs(record)
                daily_infos.append(
                    {
                        "screen_name": ("" + r["user"]["screen_name"]),
                        "rank_normal": 1,
                        "rank": 0.5,
                        "perf": -1,
                        "time": time,
                        "score": score,
                        "id": r["id"],
                    }
                )
                player_list.append(r["user"]["screen_name"])

                if not r["user"]["screen_name"] in rating_infos:
                    rating_infos[r["user"]["screen_name"]] = {
                        "best_time": "None",
                        "best_score": -1000000,
                        "highest": 0,
                        "rate": 0,
                        "inner_rate": 1600,
                        "attend": 0,
                        "win": 0,
                        "attend_date": [],
                        "record": [],
                        "standing": [],
                        "perf": [],
                        "rate_hist": [],
                    }

                # ベストスコア、ベストタイムの更新
                if score >= rating_infos[r["user"]["screen_name"]]["best_score"]:
                    rating_infos[r["user"]["screen_name"]]["best_score"] = score
                    rating_infos[r["user"]["screen_name"]]["best_time"] = time

        # ツイ消しを見た場合
        result_dq = dq_statuses
        for r in result_dq:
            if (r["text"] == "しゃろほー") and is_valid_client(clean_html_tag(r["source"])):
                rawtime = tweetid_to_datetime(r["id"])
                time = rawtime.strftime("%H:%M:%S.%f")[:-3]

                record = timedelta_to_ms(rawtime - date)

                if (not (r["user"]["screen_name"] in player_list)) and (
                    abs(record) <= 60000
                ):
                    player_list.append(r["user"]["screen_name"])
                    bouns = 1000 if record >= 0 else 0
                    score = bouns - abs(record)
                    daily_infos.append(
                        {
                            "screen_name": ("" + r["user"]["screen_name"]),
                            "rank_normal": 1,
                            "rank": 0.5,
                            "perf": -1,
                            "time": time,
                            "score": score,
                            "id": r["id"],
                        }
                    )

                    if not r["user"]["screen_name"] in rating_infos:
                        rating_infos[r["user"]["screen_name"]] = {
                            "best_time": "None",
                            "best_score": -1000000,
                            "highest": 0,
                            "rate": 0,
                            "inner_rate": 1600,
                            "attend": 0,
                            "win": 0,
                            "attend_date": [],
                            "record": [],
                            "standing": [],
                            "perf": [],
                            "rate_hist": [],
                        }

                    # ベストスコア、ベストタイムの更新
                    if score >= rating_infos[r["user"]["screen_name"]]["best_score"]:
                        rating_infos[r["user"]["screen_name"]]["best_score"] = score
                        rating_infos[r["user"]["screen_name"]]["best_time"] = time

        for i in range(len(daily_infos)):
            # inner_rateの読み込み
            daily_infos[i]["inner_rate"] = rating_infos[daily_infos[i]["screen_name"]][
                "inner_rate"
            ]
            attend_time = len(rating_infos[daily_infos[i]["screen_name"]]["perf"])
            if attend_time == 0:
                daily_infos[i]["aperf"] = 1600
            else:
                weight = np.ones(attend_time) * 0.9
                weight = weight ** np.arange(attend_time, 0, -1)
                perf_hist = np.array(
                    rating_infos[daily_infos[i]["screen_name"]]["perf"]
                )
                daily_infos[i]["aperf"] = perf_hist @ weight / sum(weight)

            # 順位付け
            for j in range(len(daily_infos)):
                if daily_infos[i]["score"] < daily_infos[j]["score"]:
                    daily_infos[i]["rank"] += 1.0
                    daily_infos[i]["rank_normal"] += 1
                elif daily_infos[i]["score"] == daily_infos[j]["score"]:
                    daily_infos[i]["rank"] += 0.5

        # パフォーマンスの計算
        for i in range(len(daily_infos)):
            x_max = 10000.0
            x_min = -10000.0
            x_mid = (x_max + x_min) / 2.0
            x_delta = x_max - x_min

            # 二分探査
            while x_delta >= 0.01:
                rank_est = 0
                for j in range(len(daily_infos)):
                    rank_est += 1.0 / (
                        1.0 + 6.0 ** ((x_mid - daily_infos[j]["aperf"]) / 400.0)
                    )

                # 期待順位と実際の順位との比較
                if rank_est >= daily_infos[i]["rank"] - 0.5:
                    x_min = x_mid
                else:
                    x_max = x_mid

                x_delta = x_max - x_min
                x_mid = (x_max + x_min) / 2.0

            daily_infos[i]["perf"] = int((x_mid - 1600.0) * exag + 1600.0 + 0.5)

            # 優勝回数の更新
            if daily_infos[i]["rank_normal"] == 1:
                rating_infos[daily_infos[i]["screen_name"]]["win"] += 1

            # 参加日、順位、記録を追加
            rating_infos[daily_infos[i]["screen_name"]]["attend_date"].append(
                date.strftime("%Y/%m/%d")
            )
            rating_infos[daily_infos[i]["screen_name"]]["record"].append(
                daily_infos[i]["time"]
            )
            rating_infos[daily_infos[i]["screen_name"]]["standing"].append(
                daily_infos[i]["rank_normal"]
            )

            # パフォーマンスを追加、出場回数の更新
            rating_infos[daily_infos[i]["screen_name"]]["perf"].append(
                daily_infos[i]["perf"]
            )
            rating_infos[daily_infos[i]["screen_name"]]["attend"] += 1

        for i in range(len(daily_infos)):
            # inner_rateを更新
            perf_lists = copy.deepcopy(
                rating_infos[daily_infos[i]["screen_name"]]["perf"]
            )
            numer = 0.0
            denom = 0.0

            for p, j in zip(perf_lists[::-1], range(1, len(perf_lists) + 1)):
                numer += 2.0 ** (p / 800.0) * 0.9 ** j
                denom += 0.9 ** j

            new_inner_rate = 800.0 * math.log2(numer / denom)
            rating_infos[daily_infos[i]["screen_name"]]["inner_rate"] = int(
                new_inner_rate + 0.5
            )

            # リストのinner_rateを更新
            daily_infos[i]["new_inner_rate"] = int(new_inner_rate + 0.5)

            # 参加回数＋初心者補正したrateを更新
            att = len(perf_lists)
            penalty = (
                1200.0
                * (((1.0 - 0.81 ** att) ** 0.5) / (1.0 - 0.9 ** att) - 1.0)
                / (19.0 ** 0.5 - 1.0)
            )
            new_rate = new_inner_rate - penalty
            new_rate = (
                (400.0) / (math.exp((400.0 - new_rate) / 400.0))
                if new_rate <= 400
                else new_rate
            )

            # リストのrateを更新
            delta = (
                int(new_rate + 0.5)
                - rating_infos[daily_infos[i]["screen_name"]]["rate"]
            )
            delta_sig = "+" if delta >= 0 else "-"
            if rating_infos[daily_infos[i]["screen_name"]]["rate"] > 0:
                delta_str = delta_sig + str(abs(delta))
            else:
                delta_str = "NEW"
            daily_infos[i]["rating"] = str(int(new_rate + 0.5))
            daily_infos[i]["change"] = delta_str

            # 辞書のrateを更新
            rating_infos[daily_infos[i]["screen_name"]]["rate"] = int(new_rate + 0.5)
            rating_infos[daily_infos[i]["screen_name"]]["rate_hist"].append(
                int(new_rate + 0.5)
            )

            # highestを更新
            if (
                int(new_rate + 0.5)
                >= rating_infos[daily_infos[i]["screen_name"]]["highest"]
            ):
                rating_infos[daily_infos[i]["screen_name"]]["highest"] = int(
                    new_rate + 0.5
                )

        return daily_infos, rating_infos

    def backfill(
        self,
        start_date: pendulum.date,
        end_date: pendulum.date,
        exag_start: bool = False,
    ):
        for i, day in enumerate(pendulum.period(start_date, end_date).range("days")):
            print(f"executing backfill for {day}...")
            statuses = self.io.get_statuses(day)
            try:
                dq_statuses = self.io.get_statuses_dq(day)
            except FileNotFoundError:
                print("no status_dq file found")
                dq_statuses = []
                pass
            if i == 0 and exag_start:
                self.calc_rating_for_date(day, statuses, dq_statuses, exag=1.5)
            else:
                self.calc_rating_for_date(day, statuses, dq_statuses)
        print("done.")
        return

    def get_summary_dataframe_and_infos(self, date) -> Tuple[pd.DataFrame, Dict]:
        rating_infos = self.io.get_rating_info(date)
        summary_df = self._summarize_result(rating_infos)
        return summary_df, rating_infos

    def _summarize_result(self, rating_infos: Dict) -> pd.DataFrame:
        # 過去の参加状況をDataFrameにして見やすくする
        final_lists = []
        for name in rating_infos:
            final_lists.append(
                [
                    name,
                    rating_infos[name]["rate"],
                    rating_infos[name]["attend"],
                    rating_infos[name]["win"],
                    rating_infos[name]["best_time"],
                ]
            )

        df = pd.DataFrame(
            final_lists, columns=["User", "Rating", "Match", "Win", "Best"]
        )
        df = df.sort_values("Rating", ascending=False)
        df["Rank"] = (
            df["Rating"].rank(ascending=False, method="min").apply(lambda x: int(x))
        )
        df = df.set_index("Rank")

        return df


if __name__ == "__main__":
    # backfill
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--eg-start", action="store_true")
    args = parser.parse_args()

    from syaroho_rating.io_handler import LocalIOHandler

    io_handler = LocalIOHandler()
    rtg = Rating(io_handler)
    start_date = pendulum.parse(args.start, tz="Asia/Tokyo")
    end_date = pendulum.parse(args.end, tz="Asia/Tokyo")
    rtg.backfill(start_date, end_date, args.eg_start)
