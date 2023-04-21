# syaroho-rating

![release workflow](https://github.com/YuriChayamachi/syaroho-rating/actions/workflows/docker-image.yml/badge.svg)
![release version](https://img.shields.io/github/v/release/YuriChayamachi/syaroho-rating)
![last commit](https://img.shields.io/github/last-commit/YuriChayamachi/syaroho-rating)
![release date](https://img.shields.io/github/release-date/YuriChayamachi/syaroho-rating)

しゃろほーレーティングの運営ツールです。

## 事前準備

1. [Docker](https://docs.docker.com/engine/install/) をインストールしてください。
1. 本リポジトリをクローンし、カレントディレクトリに設定してください。
   ```
   git clone git@github.com:YuriChayamachi/syaroho-rating.git
   cd syaroho-rating
   ```
1. local.env.template をコピーして local.env というファイルに改名し、必要な環境変数を設定してください。  
   環境変数についての説明は、「環境変数」セクションを参照してください。
   ```
   cp local.env.template local.env
   ```
1. データがある場合
   `data/` 以下に過去の集計結果ファイルをコピーします。
   ファイルの構成は「データディレクトリの構造」セクションをご覧ください。

## 環境変数

| 環境変数名           | 必須                                                | 説明                                                     |
|----------------------|-----------------------------------------------------|----------------------------------------------------------|
| TWITTER_API_VERSION  | はい                                                | 1 or 2 or 1C                                             |
| CONSUMER_KEY         | はい                                                | Twitter API 管理画面から取得                             |
| CONSUMER_SECRET      | はい                                                | Twitter API 管理画面から取得                             |
| ACCESS_TOKEN_KEY     | はい                                                | Twitter API 管理画面から取得                             |
| ACCESS_TOKEN_SECRET  | はい                                                | Twitter API 管理画面から取得                             |
| ACCOUNT_NAME         | はい                                                | Twitter アカウント名 (@の後の文字列)                     |
| ENVIRONMENT_NAME     | いいえ(TWITTER_API_VERSION が 1 が 1C の時のみ必要) | dev environment の名前 (Premium Search API 用)           |
| LIST_SLUG            | いいえ(TWITTER_API_VERSION が 1 が 1C の時のみ必要) | しゃろほー集計用に作ったリスト名                         |
| TWITTER_BEARER_TOKEN | いいえ(TWITTER_API_VERSION が 2 の時のみ必要)       | Twitter API 管理画面から取得                             |
| SYAROHO_LIST_ID      | いいえ(TWITTER_API_VERSION が 2 の時のみ必要)       | しゃろほー集計用に作ったリストID                         |
| TWITTER_PASSWORD     | いいえ(TWITTER_API_VERSION が 1C の時のみ必要)      | Twitter アカウントのログインパスワード                   |
| STORAGE              | はい                                                | local or s3                                              |
| S3_BUCKET_NAME       | いいえ(STORAGE が s3 の時のみ必要)                  | AWS S3 のバケット名                                      |
| DO_RETWEET           | はい                                                | True の場合、優勝者のツイートをリツイートします          |
| DO_POST              | はい                                                | True の場合、結果をツイートします                        |
| DEBUG                | はい                                                | True の場合、0時0分まで待たずに集計を行います            |
| SLACK_NOTIFY         | はい                                                | True の場合、エラーが起きた時に slack に通知を飛ばします |
| SLACK_WEBHOOK_URL    | いいえ(SLACK_NOTIFY が True の時のみ必要)           | slack の webhook URL                                     |

## データディレクトリの構造

`data/` 以下のファイルの構成は以下のようになっています。

```
data
├── cookie.pkl  # API v1C を使用した時に保存された cookie 情報
├── member  # しゃろほーリストに追加されたメンバー
│         └── member.json
├── member_v2  # しゃろほーリストに追加されたメンバー(API v2 の時に作成)
│         └── member.json
├── rating_info  # 参加者のレーティング情報一覧
│         └── 20230418.json
├── statuses  # 取得したしゃろほーツイート
│         └── 20230418_1.json
├── statuses_dq  # 速報用にリストから取得したしゃろほーツイート
│         └── 20230418.json
├── statuses_dq_v2  # 取得したしゃろほーツイート(API v2 の時に作成)
│         └── 20230114.json
└── statuses_v2  # 速報用にリストから取得したしゃろほーツイート(API v2 の時に作成)
    └── 20230114_1.json
```

## 使い方

### 1日分のしゃろほーを観測

次のコマンドを実行すると、1日分のしゃろほーを観測します。  
環境変数 `DUBUG` が `True` になっている場合は即座に集計を行い、
`False` になっている場合は日付が変わるタイミングまで待機します。

```bash
make run
```

### 過去のしゃろほー集計の再実行

エラー等で正しくしゃろほーが集計できなかった日がある場合、期間を指定してしゃろほーを再集計することができます。  
次のコマンドで集計を実行できます。

```bash
make backfill DATE={date}
```

例: 2023年4月18日の集計を再実行したい場合

```bash
make backfill DATE=2023-04-18
```


## CLI の説明

手元に python の実行環境がある場合、直接コマンドを実行することもできます。

### 1日分のしゃろほーを観測

次のコマンドを実行すると、日付が変わる時刻まで待ってから1日分のしゃろほーを観測します:

```bash
python main.py run [--debug]
```

`--debug` フラグをつけると、日付が変わる時刻まで待たずに観測を行います。
この場合、観測されるしゃろほーは前日の分になります。

### 過去のしゃろほー集計の再実行

エラー等で正しくしゃろほーが集計できなかった日がある場合、期間を指定してしゃろほーを再集計することができます。
計算されるレーティングは前日の結果も影響するので、基本的には集計期間の後ろは、現在の日付に指定します。

次のコマンドで集計を実行できます。

```bash
python main.py backfill <start_date> <end_date> [--post] [--retweet] [--fetch-tweet]
```

各オプションの意味は以下のようになります:

- **start_date**: 集計を開始する日付。`2022-01-01` のような形式で入力します。
- **end_date**: 集計を終了する日付。`2022-01-01` のような形式で入力します。この日付も集計される期間に含まれます。
- **post**: このフラグを付けると、本番と同じように、再集計を行った日付のランクをTwitterでつぶやきます。
- **retweet**: このフラグを付けると、本番と同じように、再集計を行った日の優勝者のしゃろほーをTwitterでリツイートします。
- **fetch-tweet**: このフラグを付けると、当日のツイートを Twitter API を使って収集します。当日分のツイートが保存されている場合は、このフラグを除くことで、Twitter API を節約することができます。

### 過去のしゃろほーツイートの収集と保存

twitter の不具合などでしゃろほーツイートの取得に失敗した日付がある場合、その日付のしゃろほーツイートを取得して保存することができます。

次のコマンドで実行できます:

```bash
python main.py fetch-tweet <date> [--save]
```

`--save` オプションをつけない場合、取得結果を保存せずに表示だけします。
