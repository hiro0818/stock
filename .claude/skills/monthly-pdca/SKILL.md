---
name: monthly-pdca
description: 月次 PDCA レビューを自動実行する。過去予測の検証 → 重み再学習 → 改善方針提示までを一括処理。ユーザーが「月次レビューやって」「PDCA 月次」「予測の振り返り」「精度チェック」「重み学習やって」と言った時、または /monthly-pdca を叩いた時に呼び出す。
---

# monthly-pdca — 月次 PDCA 自動実行

予測モデルの精度を検証し、重みを更新し、改善方針を立てる月次ルーチン。
所要時間: 1〜3 分。

## 手順

### Step 1: 検証待ち予測の自動検証

`tools/prediction_log.py` の `list_pending_predictions()` で目標日経過した予測を取得。
各予測について、現在の終値で `verify_prediction()` を呼び、誤差を計算 + 保存。

実行例:
```python
import sys; sys.path.insert(0, 'tools')
from prediction_log import list_pending_predictions, verify_prediction
from fetch_stock import get_summary

pending = list_pending_predictions()
for rec in pending:
    actual = get_summary(rec['ticker']).get('current_price')
    if actual:
        verify_prediction(rec, actual)
```

### Step 2: 検証済みデータの集計

`prediction_log.aggregate_accuracy()` を呼んで、モデル別の平均誤差・ヒット率を集計。
結果を Markdown 表で表示。

### Step 3: 重み学習 20 サイクル PDCA を実行

```bash
cd <project root> && python tools/pdca_loop.py 20
```

サイクル 1 vs サイクル 20 の改善幅を表示し、新しい重みを `predict.py` の
`WALK_FORWARD_WEIGHTS` に提案する形で出力。

### Step 4: 改善方針の自動提案

集計結果から以下を判定:

- **誤差が大きいモデル**:除外候補として提示
- **方向当たり率が低いモデル**:重み低下候補
- **ヒット率が異常に低い銘柄**:該当銘柄向けの専用モデル検討候補
- **バイアスが大きい場合**(過大予測/過小予測):クリッピング閾値の見直し

### Step 5: レポート保存

結果を `outputs/monthly_pdca/<YYYYMM>.md` に保存。
構成:
- 検証済み件数 / 新規検証件数
- モデル別精度
- 重み学習結果(サイクル 1 → 20)
- 改善方針(具体的アクション 3 つまで)

### Step 6: ユーザーへの最終報告

```markdown
# 🔄 月次 PDCA レポート — YYYY-MM

## 検証
- 新規検証: N 件
- 累計検証: M 件
- モデル別精度: (表)

## 重み学習(サイクル 1 → 20)
- 誤差: X% → Y%(改善 Zpt)
- 方向当たり率: A% → B%(改善 Cpt)
- 新重み: ...

## 改善方針(次月実行候補)
1. ...
2. ...
3. ...
```

## ルール

- 検証待ちが 0 件でも、重み学習は実行する(サンプル数があれば)
- 改善方針は実行可能な具体アクション(「○○を○○に変更」)で書く
- 投資助言ではないことを冒頭・末尾に明記

## 関連ツール

- `tools/prediction_log.py`(検証 + 集計)
- `tools/pdca_loop.py`(20 サイクル重み学習)
- `tools/predict.py`(WALK_FORWARD_WEIGHTS 更新候補)
- `outputs/monthly_pdca/<YYYYMM>.md`(出力先)
