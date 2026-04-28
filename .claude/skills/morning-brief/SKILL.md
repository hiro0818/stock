---
name: morning-brief
description: 毎朝のマーケット状況レビュー。watchlist の全銘柄について前日比 / シグナル発火 / PDCA 検証待ちを 1 コマンドで整理する。ユーザーが「今朝の状況見せて」「モーニングブリーフ」「今日の watchlist」「朝のチェック」「watchlist 一覧」と言った時、または /morning-brief を叩いた時に呼び出す。
---

# morning-brief — 毎朝の状況一括レビュー

ユーザー(富樫さん)の毎朝のルーチンを 1 コマンドにする。
所要時間: 30〜60 秒(yfinance 取得込み)。

## 手順

### Step 1: Watchlist の読み込み

`inputs/watchlist.md` を Read。コメント行(`#`)を除外、ティッカーを抽出。
ファイルが空 or 存在しない場合はユーザーに警告して終了。

### Step 2: daily_check.py で全銘柄を一括取得

Bash で以下を実行(全銘柄の summary + technical + competitors を取得):

```bash
cd <project root> && python tools/daily_check.py
```

これで `outputs/daily/<YYYYMMDD>/` に最新データが保存される。

### Step 3: outputs/daily/<今日>/_index.md を読み込んで整形

`_index.md` には全銘柄の表形式サマリ(株価/PER/RSI/トレンド/シグナル)が入っている。
これを Markdown としてユーザーに表示。

### Step 4: シグナル発火銘柄の抽出

各銘柄の `<ticker>_technical.json` を確認し、以下の条件で**注目銘柄**としてピックアップ:
- RSI > 70(買われすぎ)or < 30(売られすぎ)
- 出来高 > 50 日平均の 2 倍
- 52 週レンジ上端付近(>0.85)or 下端付近(<0.15)
- ゴールデン/デッドクロス近辺

注目銘柄をユーザー向けに「⭐ 今日チェックすべき銘柄」として列挙。

### Step 5: PDCA 検証待ちの予測がないか確認

`tools/prediction_log.py` の `list_pending_predictions()` を呼び、
目標日経過 × 未検証の予測があれば「🔄 検証待ち N 件」として表示。

### Step 6: 全体まとめ(チャット出力)

```markdown
# 🌅 モーニングブリーフ — YYYY-MM-DD HH:MM

## 全銘柄サマリ
(_index.md の表をそのまま表示)

## ⭐ 今日チェックすべき銘柄
- TICKER1:理由
- TICKER2:理由
...

## 🔄 PDCA 検証待ち
- N 件の予測が目標日を過ぎています。「PDCA」タブで検証してください。

## ☕ 一言メモ
全体トレンド(NASDAQ/日経の前日比)を 1 行で。
```

## ルール

- Watchlist が空なら、サンプル提案を出す(AAPL/NVDA/MSFT/7203.T/6758.T)
- 取引時間外は遅延データの可能性を警告
- 投資助言ではない旨を末尾に毎回明記
- 出力は **30 秒で読める**長さに(冗長にしない)

## 関連ツール

- `inputs/watchlist.md`(入力)
- `tools/daily_check.py`(データ取得)
- `tools/prediction_log.py`(検証待ちチェック)
- `outputs/daily/<date>/`(出力先)
