import copy
import math
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import pendulum

from syaroho_rating.model import Tweet
from syaroho_rating.twitter import is_valid_client
from syaroho_rating.utils import clean_html_tag, timedelta_to_ms


def calc_rating_for_date(
    date: pendulum.date,
    statuses: List[Tweet],
    dq_statuses: List[Tweet],
    rating_infos: Dict,
    exag: float,
) -> Tuple[List, Dict]:

    # ある日の参加者リストの作成
    daily_infos = []
    player_list = []

    ymd = date.strftime("%Y%m%d")

    for s in statuses:
        user_name = s.author.username
        if (s.text == "しゃろほー") and is_valid_client(clean_html_tag(s.source)):
            rawtime = s.created_at_ms
            time = rawtime.strftime("%H:%M:%S.%f")[:-3]

            record = timedelta_to_ms(rawtime - date)
            bouns = 1000 if record >= 0 else 0
            score = bouns - abs(record)
            daily_infos.append(
                {
                    "screen_name": ("" + user_name),
                    "rank_normal": 1,
                    "rank": 0.5,
                    "perf": -1,
                    "time": time,
                    "score": score,
                    "id": s.id,
                }
            )
            player_list.append(user_name)

            if not user_name in rating_infos:
                rating_infos[user_name] = {
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
            if score >= rating_infos[user_name]["best_score"]:
                rating_infos[user_name]["best_score"] = score
                rating_infos[user_name]["best_time"] = time

    # ツイ消しを見た場合
    for s in dq_statuses:
        user_name = s.author.username
        if (s.text == "しゃろほー") and is_valid_client(clean_html_tag(s.source)):
            rawtime = s.created_at_ms
            time = rawtime.strftime("%H:%M:%S.%f")[:-3]

            record = timedelta_to_ms(rawtime - date)

            if (not (user_name in player_list)) and (abs(record) <= 60000):
                player_list.append(user_name)
                bouns = 1000 if record >= 0 else 0
                score = bouns - abs(record)
                daily_infos.append(
                    {
                        "screen_name": ("" + user_name),
                        "rank_normal": 1,
                        "rank": 0.5,
                        "perf": -1,
                        "time": time,
                        "score": score,
                        "id": r["id"],
                    }
                )

                if not user_name in rating_infos:
                    rating_infos[user_name] = {
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
                if score >= rating_infos[user_name]["best_score"]:
                    rating_infos[user_name]["best_score"] = score
                    rating_infos[user_name]["best_time"] = time

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
            perf_hist = np.array(rating_infos[daily_infos[i]["screen_name"]]["perf"])
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
        perf_lists = copy.deepcopy(rating_infos[daily_infos[i]["screen_name"]]["perf"])
        numer = 0.0
        denom = 0.0

        for p, j in zip(perf_lists[::-1], range(1, len(perf_lists) + 1)):
            numer += 2.0 ** (p / 800.0) * 0.9**j
            denom += 0.9**j

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
            * (((1.0 - 0.81**att) ** 0.5) / (1.0 - 0.9**att) - 1.0)
            / (19.0**0.5 - 1.0)
        )
        new_rate = new_inner_rate - penalty
        new_rate = (
            (400.0) / (math.exp((400.0 - new_rate) / 400.0))
            if new_rate <= 400
            else new_rate
        )

        # リストのrateを更新
        delta = (
            int(new_rate + 0.5) - rating_infos[daily_infos[i]["screen_name"]]["rate"]
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
            rating_infos[daily_infos[i]["screen_name"]]["highest"] = int(new_rate + 0.5)

    return daily_infos, rating_infos


def summarize_rating_info(rating_infos: Dict) -> pd.DataFrame:
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

    df = pd.DataFrame(final_lists, columns=["User", "Rating", "Match", "Win", "Best"])
    df = df.sort_values("Rating", ascending=False)
    df["Rank"] = (
        df["Rating"].rank(ascending=False, method="min").apply(lambda x: int(x))
    )
    df = df.set_index("Rank")

    return df
