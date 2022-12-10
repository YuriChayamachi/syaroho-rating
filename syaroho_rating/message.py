def create_reply_message(
    name,
    name_jp,
    best_time,
    highest,
    rating,
    rank_all,
    rank,
    match,
    win,
):
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
