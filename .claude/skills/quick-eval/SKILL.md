---
name: quick-eval
description: 単一銘柄の即時評価。ユーザーが「AAPLどう?」「7203.Tを評価して」「この株分析して」と聞いた時、または /quick-eval <ティッカー> を叩いた時に呼び出す。yfinance API でファンダメンタルズと技術指標を取得し、同業他社の競合比較を含めた簡易レポートをチャットに返す。/select-stocks より軽量で即応性重視。
---

# quick-eval — 単一銘柄の即時評価

ユーザーが個別銘柄について「どう?」「評価して」「分析して」と聞いた時の標準応答フロー。

## 起動条件

- スラッシュコマンド: `/quick-eval <ティッカー>`(例: `/quick-eval AAPL`)
- 自然言語: 「AAPL どう?」「7203.T はどうかな」「ソニーの株を評価して」など、特定銘柄の評価依頼

ユーザーの自然言語に企業名しかない場合は、まず一般知識でティッカーを推定する(例: ソニー → 6758.T、Apple → AAPL)。確信が持てなければユーザーに「`6758.T`(ソニーグループ)で合っていますか?」と確認する。

## 手順

### Step 0: 準備

- ティッカーを正規化(米国株はそのまま、日本株は `XXXX.T`)
- `outputs/quick-eval/` を `New-Item -ItemType Directory -Force` で作成

### Step 1: データ取得(Bash で並列実行)

同一アシスタントメッセージ内で以下を**並列に Bash 呼び出し**(3 つ):

```bash
python tools/fetch_stock.py <TICKER> --mode summary
python tools/fetch_stock.py <TICKER> --mode technical
python tools/find_competitors.py <TICKER> --limit 5
```

### Step 2: 競合比較データ取得

find_competitors.py の出力から競合ティッカーを取り出し、上位 3 銘柄について **並列で** summary を取得:

```bash
python tools/fetch_stock.py <competitor1> --mode summary
python tools/fetch_stock.py <competitor2> --mode summary
python tools/fetch_stock.py <competitor3> --mode summary
```

### Step 3: 評価レポート生成

以下の構成でチャットにマークダウン出力 + 同内容を `outputs/quick-eval/<ticker>_<YYYYMMDD-HHMM>.md` にも保存。

```
# 銘柄評価: <name> (<ticker>)
取得日時: <fetched_at>(yfinance、15分以上の遅延あり)

> ⚠️ 投資助言ではありません。判断材料を整理した結果です。

## 1. ひとこと評価
- 1〜2 行のサマリ(強気/中立/弱気のバランス)

## 2. ファンダメンタルズ(yfinance 一次データ)
- 株価: $X.XX(または ¥X,XXX)
- 時価総額: 
- Trailing PER: / Forward PER: 
- ROE: / 営業利益率: 
- 売上成長率: / EPS成長率: 
- 配当利回り: 
- 一言: `推論:` …(数値の評価)

## 3. 技術分析(直近 1 年)
- 終値: 
- 移動平均: MA20 / MA50 / MA200(配置から判断するトレンド)
- RSI(14): (買われすぎ / 売られすぎ / 中立)
- MACD: (プラス圏 / マイナス圏)
- 出来高: 平均比 X.X 倍
- 52週レンジ位置: 上端 / 中央 / 下端
- シグナル: (signals 配列を箇条書き)
- 一言: `推論:` …

## 4. 競合比較
| 銘柄 | PER | ROE | 売上成長率 | コメント |
|---|---|---|---|---|
| <自社> | | | | |
| <競合1> | | | | |
| <競合2> | | | | |
| <競合3> | | | | |
- 一言: `推論:` 競合に対して相対的にどう位置づくか

## 5. 強気の論点 / 弱気の論点
### 強気
- (3 点)
### 弱気
- (3 点)

## 6. モニタリング項目(翌日以降の追跡用)
- 株価が <X> を上抜け/下抜けしたら注目
- 次の決算で確認すべき指標
- 競合のニュース監視ポイント

## 7. 不確実性
- yfinance データの最新性に依存
- 一次資料(IR, 決算短信)で必ず裏取り

> ⚠️ 改めて: これは情報整理であり投資推奨ではありません。最終判断は自己責任で。
```

### Step 4: ユーザーへの提案

レポート末尾に、次の選択肢を提示:

```
---
**次のアクション候補:**
- 翌日以降も追跡したい場合: `inputs/watchlist.md` にこの銘柄を追記してください(README参照)
- もっと深いリサーチをしたい場合: `/select-stocks` でフル5体エージェント分析が可能
- チャート画像を見たい場合: 別途 `tools/fetch_stock.py <ticker> --mode history` で生データ取得
```

## ルール

- **完全に投資助言ではない**ことを冒頭・末尾に必ず表示。
- 数値は必ず yfinance の取得時刻と併記。
- ハルシネーション防止: API で取れなかった項目は「該当データなし」と明記、推測で埋めない。
- 競合が見つからない場合(industry 未登録)は、その旨明記して比較セクションは省略。
- ユーザー要求に「翌日に再評価」がある場合: watchlist 運用を案内するが、自動再実行は OS スケジューラ依存のため別途セットアップが必要(README にスケジューラ例あり)。

## 完了報告

最終アシスタントメッセージで:「[quick-eval] 評価完了。同内容を `outputs/quick-eval/<ticker>_<YYYYMMDD-HHMM>.md` に保存しました。」
