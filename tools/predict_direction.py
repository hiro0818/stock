"""
predict_direction.py — 方向(プラス / マイナス)2 値分類器

参照論文:
  - Patel et al. (2015): "Predicting stock market index using fusion of machine learning techniques"
    → SVM/ANN/RF で方向予測、特徴量にテクニカル指標を採用
  - Krauss, Do, Huck (2017): "Deep neural networks, gradient-boosted trees, random forests:
    Statistical arbitrage on the S&P 500"
    → GB が DNN とほぼ同等性能 → 本実装は LightGBM 採用
  - Fischer & Krauss (2018): LSTM 方向予測 → 計算重いため不採用
  - Kim (2003): SVM 金融時系列分類 → 古典の発想を踏襲
  - Atsalakis & Valavanis (2009): 手法サーベイ

実装:
  - LightGBM Classifier(2 値分類)
  - 目的変数: 21 営業日後のリターンが正(1) / 負(0)
  - 特徴量: predict_ml.build_features() を流用 + テクニカル指標
  - 確率出力 → 閾値 0.5 で分類、確率 |p - 0.5| でシグナル強度

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False

from predict_ml import build_features  # noqa: E402


def build_classification_data(
    history: list[dict],
    macro_histories: dict[str, list[dict]] | None = None,
    forecast_days: int = 21,
    min_idx: int = 252,
) -> tuple[list[dict], list[int]] | None:
    """過去履歴から(X, y)を生成。y=1 が上昇、y=0 が下降。"""
    n = len(history)
    if n < min_idx + forecast_days + 1:
        return None
    Xs = []
    ys = []
    for i in range(min_idx, n - forecast_days):
        feat = build_features(history, macro_histories, end_idx=i)
        if not feat:
            continue
        c_now = history[i].get("close")
        c_future = history[i + forecast_days].get("close")
        if c_now is None or c_future is None or c_now <= 0 or c_future <= 0:
            continue
        ys.append(1 if c_future > c_now else 0)
        Xs.append(feat)
    return Xs, ys


def predict_direction_lgbm(
    history: list[dict],
    macro_histories: dict[str, list[dict]] | None = None,
    days_ahead: int = 21,
) -> dict | None:
    """LightGBM Classifier で 21 営業日先の方向を予測。

    Returns:
      {
        "direction": "up" or "down",
        "probability_up": 0.0-1.0,
        "confidence": |p - 0.5| × 2(0=コイン投げ、1=完全確信),
        "signal": 強気 / 中立 / 弱気,
        ...
      }
    """
    if not HAS_LGBM:
        return None
    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 350:
        return None

    train = build_classification_data(history, macro_histories, forecast_days=days_ahead)
    if not train or len(train[0]) < 50:
        return None
    Xs, ys = train

    feature_names = list(Xs[0].keys())
    X_arr = [[x.get(f, 0.0) for f in feature_names] for x in Xs]

    try:
        model = lgb.LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=15,
            min_child_samples=5,
            verbose=-1,
            random_state=42,
        )
        model.fit(X_arr, ys)

        latest_feat = build_features(history, macro_histories, end_idx=len(history) - 1)
        if not latest_feat:
            return None
        x_latest = [[latest_feat.get(f, 0.0) for f in feature_names]]
        prob_up = float(model.predict_proba(x_latest)[0][1])
        confidence = abs(prob_up - 0.5) * 2

        if prob_up >= 0.60:
            signal = "強気(プラス予測 高確度)"
        elif prob_up >= 0.55:
            signal = "やや強気"
        elif prob_up >= 0.45:
            signal = "中立(ほぼコイン投げ)"
        elif prob_up >= 0.40:
            signal = "やや弱気"
        else:
            signal = "弱気(マイナス予測 高確度)"

        # 訓練データでの精度(in-sample、参考値)
        train_pred = model.predict(X_arr)
        train_acc = sum(1 for p, t in zip(train_pred, ys) if p == t) / len(ys)

        # 特徴量重要度
        importances = dict(zip(feature_names, model.feature_importances_.tolist()))
        importances = dict(
            sorted(importances.items(), key=lambda kv: kv[1], reverse=True)[:10]
        )

        return {
            "direction": "up" if prob_up >= 0.5 else "down",
            "probability_up": prob_up,
            "probability_down": 1 - prob_up,
            "confidence": confidence,
            "signal": signal,
            "train_accuracy": train_acc,
            "n_train_samples": len(Xs),
            "top_features": importances,
        }
    except Exception as e:
        return {"error": str(e)}
