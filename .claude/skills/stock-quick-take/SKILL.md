---
name: stock-quick-take
description: 個別銘柄の即時評価。「AAPL どう?」「7203 評価して」「NVDA の状況は?」「○○について教えて」のような自然言語の質問に対し、ファンダ + テクニカル + 競合 + 1ヶ月予測 + 方向予測を 1 ターンで返す。/quick-eval スラッシュコマンドの自然言語版。
---

# stock-quick-take — 個別銘柄の即時評価(自然言語版)

ユーザーの「AAPL どう?」「7203 評価して」のような問いに、構造化したミニ評価で答える。
所要時間: 10〜30 秒(yfinance 取得 + LightGBM 学習込み)。

## トリガーパターン(自然言語で起動)

以下のような発話で起動:
- 「AAPL どう?」「アップル どう?」
- 「7203 評価して」「トヨタ評価」
- 「NVDA の状況は?」「エヌビディア今どう?」
- 「○○ について教えて」(○○ が銘柄名 or ティッカーの場合)
- 「○○ 買い時?」「○○ 持っといていい?」

## ティッカーの正規化

入力からティッカーを抽出し、正規化:
- 「AAPL」「アップル」「Apple」→ `AAPL`
- 「7203」「トヨタ」→ `7203.T`
- 「6758」「ソニー」「ソニーG」→ `6758.T`
- 「NVDA」「エヌビディア」「nvidia」→ `NVDA`

不明な銘柄名はユーザーに確認。

## 手順

### Step 1: データ取得(並列)

Bash で以下を実行(可能な限り並列):

```bash
python tools/fetch_stock.py <TICKER> --mode summary
python tools/fetch_stock.py <TICKER> --mode technical
python tools/find_competitors.py <TICKER> --limit 3
```

### Step 2: 総合スコア計算

Python で以下を実行:

```python
import sys; sys.path.insert(0, 'tools')
from fetch_stock import get_summary, get_technical, get_history
from scoring import total_score
from predict import predict_all
from predict_direction_v2 import predict_direction_v2

summary = get_summary(ticker)
technical = get_technical(ticker)
score = total_score(summary, technical)

# 1ヶ月予測
history = get_history(ticker, '2y')
prediction = predict_all(history, summary, technical, days_ahead=30)

# 方向予測(キャリブレーション + アンサンブル)
direction = predict_direction_v2(history, None, days_ahead=21)
```

### Step 3: ミニ評価レポートを出力

```markdown
# 📈 {会社名} `{TICKER}` のクイック評価

> ⚠️ 投資助言ではありません

## 🎯 総合判定
{score['判定']}({score['総合スコア']}/100)

## 💰 主要指標
- 現在値: $X.XX
- PER: X.X(forward Y.Y)
- ROE: X.X%
- 売上成長率: X.X%
- 配当利回り: X.X%

## 📈 テクニカル
- トレンド: ...(MA配置)
- RSI(14): X.X(過熱/中立/過売)
- MACD: ...
- 52週レンジ位置: ...
- 主要シグナル: ...(あれば)

## 🔮 1ヶ月予測
- アンサンブル予測: $X.XX(現在から +X.XX%)
- 重み付き予測: $X.XX
- 方向予測(LightGBM): {🟢 プラス / 🔴 マイナス}(確率 X.X%、確信度 X%)

## 🏢 同業他社(自動列挙)
- COMP1, COMP2, COMP3

## ✅ 強み
- ...

## ⚠️ 警戒
- ...

## 一言まとめ
(全体を 1〜2 行で)
```

## ルール

- 投資助言ではない旨を毎回冒頭に表示
- ヒット率 / 過去精度については簡潔に(詳細は PDCA タブへ誘導)
- 確信度が低い時は「予測の信頼性は低め」と明記
- 出力は**読みやすさ最優先**(冗長にしない)
- 暗号銘柄(COIN/MSTR/MARA など)では追加で BTC との連動度を表示

## 関連ツール

- `tools/fetch_stock.py`(データ取得)
- `tools/find_competitors.py`(同業他社)
- `tools/scoring.py`(総合スコア)
- `tools/predict.py`(1ヶ月予測)
- `tools/predict_direction_v2.py`(方向予測 v7)
