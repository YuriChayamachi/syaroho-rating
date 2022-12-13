from syaroho_rating.utils import classes


def create_reply_message(
    name_r: str,
    name_jp: str,
    best_time: str,
    highest: int,
    rating: int,
    rank_all: int,
    rank: int,
    match: int,
    win: int,
) -> str:
    return "\n".join(
        [
            "@" + name_r,
            name_jp + " (しゃろほー" + classes(highest) + ")",
            "レーティング: " + str(rating) + " (最高: " + str(highest) + ")",
            "順位: " + str(rank) + " / " + str(rank_all),
            "優勝 / 参加回数: " + str(win) + " / " + str(match),
            "ベスト記録: " + str(best_time),
        ]
    )
