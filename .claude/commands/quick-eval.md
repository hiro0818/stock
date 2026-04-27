---
description: 単一銘柄を即時評価(ファンダ + 技術指標 + 競合比較)。投資助言ではありません
argument-hint: "<ティッカー(例: AAPL, 7203.T)>"
---

# /quick-eval — 単一銘柄の即時評価

引数: `$ARGUMENTS`

`quick-eval` スキルを起動して、`$ARGUMENTS` で指定されたティッカーの即時評価を行ってください。

- yfinance API からファンダメンタルズと技術指標を取得
- find_competitors.py で同業他社を自動列挙、競合比較表を作成
- 強気/弱気の論点を整理
- モニタリング項目を提案
- 結果を `outputs/quick-eval/<ticker>_<YYYYMMDD-HHMM>.md` に保存

**冒頭・末尾で必ず免責事項(投資助言ではない旨)を表示すること。**

引数なしの場合は、何の銘柄を評価したいかユーザーに尋ねてください。
