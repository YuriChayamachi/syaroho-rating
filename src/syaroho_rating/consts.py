# -*- coding: utf-8 -*-

import os

import numpy as np

TZ = "Asia/Tokyo"

# twitter configs
TWITTER_API_VERSION = os.environ["TWITTER_API_VERSION"]
CONSUMER_KEY = os.environ["CONSUMER_KEY"]
CONSUMER_SECRET = os.environ["CONSUMER_SECRET"]
ACCESS_TOKEN_KEY = os.environ["ACCESS_TOKEN_KEY"]
ACCESS_TOKEN_SECRET = os.environ["ACCESS_TOKEN_SECRET"]
ACCOUNT_NAME = os.environ["ACCOUNT_NAME"]
# APIv1
ENVIRONMENT_NAME = os.environ.get("ENVIRONMENT_NAME")
LIST_SLUG = os.environ.get("LIST_SLUG")
# APIv2
SYAROHO_LIST_ID = os.environ.get("SYAROHO_LIST_ID")
# APIv1C
TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD")
TWITTER_COOKIE_PATH = "data/cookie.pkl"

# data storage configs
STORAGE = os.environ["STORAGE"]
# s3 configs
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

# slack configs
SLACK_NOTIFY = True if os.environ["SLACK_NOTIFY"] == "True" else False
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

# run configs
DO_RETWEET = True if os.environ["DO_RETWEET"] == "True" else False
DO_POST = True if os.environ["DO_POST"] == "True" else False
DEBUG = True if os.environ["DEBUG"] == "True" else False

reply_patience = 900  # 投稿からこの秒数以上経過したツイートには返信しない
id_hist_max = 100  # 返信済のツイートIDの最大保持数

# グラフのレーティングの色
graph_colors = [  # (colorname, low_rate, high_rate)
    ("#808080", 0, 400),  # gray
    ("#804000", 400, 800),  # brown
    ("#008000", 800, 1200),  # green
    ("#00C0C0", 1200, 1600),  # cyan
    ("#0000FF", 1600, 2000),  # blue
    ("#C0C000", 2000, 2400),  # yellow
    ("#FF8005", 2400, 2800),  # orange
    ("#FF0000", 2800, 3200),  # red
]

# 表のレーティング色
table_bg_colors = [  # (colordef, low_rate, high_rate)
    ((128 / 255.0, 128 / 255.0, 128 / 255.0), -np.inf, 400),  # gray
    ((128 / 255.0, 64 / 255.0, 0 / 255.0), 400, 800),  # brown
    ((0 / 255.0, 128 / 255.0, 0 / 255.0), 800, 1200),  # green
    ((0 / 255.0, 192 / 255.0, 192 / 255.0), 1200, 1600),  # cyan
    ((0 / 255.0, 0 / 255.0, 255 / 255.0), 1600, 2000),  # blue
    ((192 / 255.0, 192 / 255.0, 0 / 255.0), 2000, 2400),  # yellow
    ((255 / 255.0, 128 / 255.0, 5 / 255.0), 2400, 2800),  # orange
    ((255 / 255.0, 0 / 255.0, 0 / 255.0), 2800, np.inf),  # red
]

class_list = [
    "極伝",
    "皆伝",
    "十段",
    "九段",
    "八段",
    "七段",
    "六段",
    "五段",
    "四段",
    "三段",
    "二段",
    "初段",
    "1級",
    "2級",
    "3級",
    "4級",
    "5級",
    "6級",
    "7級",
    "8級",
    "9級",
    "10級",
    "11級",
    "12級",
    "13級",
    "14級",
    "15級",
    "16級",
    "17級",
    "18級",
    "19級",
    "20級",
    "",
]

month_name = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
