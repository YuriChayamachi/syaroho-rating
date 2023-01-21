# syaroho-rating

![release workflow](https://github.com/YuriChayamachi/syaroho-rating/actions/workflows/docker-image.yml/badge.svg)
![release version](https://img.shields.io/github/v/release/YuriChayamachi/syaroho-rating)
![last commit](https://img.shields.io/github/last-commit/YuriChayamachi/syaroho-rating)
![release date](https://img.shields.io/github/release-date/YuriChayamachi/syaroho-rating)

しゃろほーレーティングの運営ツールです。

## 使い方

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
