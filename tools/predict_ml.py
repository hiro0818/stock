"""
predict_ml.py — 機械学習ベースの予測モデル(LightGBM + 特徴量エンジニアリング)

PDCA cycle 7-10 で導入:
  - LightGBM 回帰でログリターンを予測
  - 特徴量: 過去リターン(1d/5d/20d/60d/252d), ボラティリティ, RSI, MA 比, MACD,
    出来高比, レンジ位置, モメンタム(12m), リバーサル(60d), マクロのログリターン
  - 学習データ: 同じ銘柄の過去サンプル(walk_forward 形式と整合)

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import math
from typing import Any

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False


def safe_div(a, b, default=0.0):
    return a / b if b not in (0, 0.0, None) else default


def build_features(
    history: list[dict],
    macro_histories: dict[str, list[dict]] | None = None,
    end_idx: int | None = None,
) -> dict | None:
    """指定時点(end_idx)までの履歴から特徴量を計算する。
    end_idx=None なら最新時点。"""
    if end_idx is None:
        end_idx = len(history) - 1
    if end_idx < 252:
        return None

    closes = [h["close"] for h in history[: end_idx + 1] if h.get("close") is not None]
    volumes = [h.get("volume", 0) for h in history[: end_idx + 1]]
    if len(closes) < 252:
        return None

    last = closes[-1]

    # 過去リターン(対数)
    def log_return(n_back):
        if len(closes) <= n_back or closes[-n_back - 1] <= 0:
            return 0.0
        return math.log(last / closes[-n_back - 1])

    feat = {
        "log_ret_1d": log_return(1),
        "log_ret_5d": log_return(5),
        "log_ret_20d": log_return(20),
        "log_ret_60d": log_return(60),
        "log_ret_252d": log_return(252),
    }

    # ボラティリティ(過去 20 日 / 60 日の対数リターン標準偏差)
    def vol(n):
        if len(closes) <= n + 1:
            return 0.0
        rets = [
            math.log(closes[-i] / closes[-i - 1])
            for i in range(1, n + 1)
            if closes[-i - 1] > 0 and closes[-i] > 0
        ]
        if len(rets) < 2:
            return 0.0
        m = sum(rets) / len(rets)
        var = sum((r - m) ** 2 for r in rets) / len(rets)
        return math.sqrt(var)

    feat["vol_20d"] = vol(20)
    feat["vol_60d"] = vol(60)

    # MA 比
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50
    ma200 = sum(closes[-200:]) / 200
    feat["ma20_ratio"] = safe_div(last, ma20, 1.0) - 1.0
    feat["ma50_ratio"] = safe_div(last, ma50, 1.0) - 1.0
    feat["ma200_ratio"] = safe_div(last, ma200, 1.0) - 1.0
    feat["ma50_vs_ma200"] = safe_div(ma50, ma200, 1.0) - 1.0

    # RSI(14)
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-14:]]
    losses = [-d if d < 0 else 0 for d in deltas[-14:]]
    avg_g = sum(gains) / 14
    avg_l = sum(losses) / 14
    if avg_l == 0:
        feat["rsi14"] = 100.0
    else:
        feat["rsi14"] = 100 - (100 / (1 + avg_g / avg_l))

    # MACD(12, 26)
    def ema(xs, span):
        k = 2 / (span + 1)
        e = xs[0]
        for x in xs[1:]:
            e = e * (1 - k) + x * k
        return e

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    feat["macd"] = ema12 - ema26
    feat["macd_norm"] = safe_div(feat["macd"], last, 0.0)  # 価格規模で正規化

    # 出来高比(直近 20 日平均 vs 60 日平均)
    if len(volumes) >= 60:
        vol20 = sum(volumes[-20:]) / 20 if any(volumes[-20:]) else 0
        vol60 = sum(volumes[-60:]) / 60 if any(volumes[-60:]) else 0
        feat["volume_ratio"] = safe_div(vol20, vol60, 1.0) if vol60 > 0 else 1.0
    else:
        feat["volume_ratio"] = 1.0

    # 52 週レンジ位置
    week52_window = closes[-min(252, len(closes)):]
    high = max(week52_window)
    low = min(week52_window)
    feat["range_pos"] = safe_div(last - low, high - low, 0.5) if high > low else 0.5

    # マクロ特徴量(指定時点での過去 20 日対数リターン)
    if macro_histories:
        for m_ticker, m_hist in macro_histories.items():
            m_closes = [h["close"] for h in m_hist if h.get("date") and h["date"] <= history[end_idx]["date"]]
            m_closes = [c for c in m_closes if c is not None]
            if len(m_closes) > 21 and m_closes[-21] > 0:
                feat[f"macro_{m_ticker}_20d"] = math.log(m_closes[-1] / m_closes[-21])
            else:
                feat[f"macro_{m_ticker}_20d"] = 0.0

    return feat


def build_training_data(
    history: list[dict],
    macro_histories: dict[str, list[dict]] | None = None,
    forecast_days: int = 21,
    min_idx: int = 252,
) -> tuple[list[dict], list[float]] | None:
    """過去履歴から学習データ(X, y)を作る。
    各時点 i について feature(i) → log_return(i+forecast_days, i)。"""
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
        target = math.log(c_future / c_now)
        Xs.append(feat)
        ys.append(target)
    return Xs, ys


def predict_lightgbm(
    history: list[dict],
    macro_histories: dict[str, list[dict]] | None = None,
    days_ahead: int = 21,
) -> dict | None:
    """LightGBM で 21 営業日先のログリターンを予測。学習データは同じ銘柄の過去サンプル。

    Returns: {"predicted": price, "predicted_log_return": ret, "feature_importance": {...}}
    """
    if not HAS_LGBM:
        return None
    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 350:
        return None  # 学習用データが少なすぎる

    train = build_training_data(history, macro_histories, forecast_days=days_ahead)
    if not train or len(train[0]) < 50:
        return None
    Xs, ys = train

    # 辞書 → 配列に
    feature_names = list(Xs[0].keys())
    X_arr = [[x.get(f, 0.0) for f in feature_names] for x in Xs]

    try:
        model = lgb.LGBMRegressor(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=15,
            min_child_samples=5,
            verbose=-1,
            random_state=42,
        )
        model.fit(X_arr, ys)

        # 現在の特徴量で予測
        latest_feat = build_features(history, macro_histories, end_idx=len(history) - 1)
        if not latest_feat:
            return None
        x_latest = [[latest_feat.get(f, 0.0) for f in feature_names]]
        pred_log_return = float(model.predict(x_latest)[0])
        # 過大予測抑制(月 ±15% にクリップ)
        pred_log_return = max(-0.15, min(0.15, pred_log_return))
        last = closes[-1]
        predicted = last * math.exp(pred_log_return)

        importances = dict(zip(feature_names, model.feature_importances_.tolist()))
        importances = dict(
            sorted(importances.items(), key=lambda kv: kv[1], reverse=True)[:10]
        )

        return {
            "predicted": predicted,
            "predicted_log_return": pred_log_return,
            "n_train_samples": len(Xs),
            "top_features": importances,
        }
    except Exception as e:
        return {"error": str(e)}


def predict_crypto_linked(
    history: list[dict],
    btc_history: list[dict] | None,
    days_ahead: int = 21,
) -> dict | None:
    """暗号関連銘柄(COIN/MSTR)用の専用モデル。BTC との直接連動を仮定。
    PDCA cycle 6 で導入。"""
    closes = [h["close"] for h in history if h.get("close") is not None]
    if not closes or not btc_history:
        return None
    btc_closes = [h["close"] for h in btc_history if h.get("close") is not None]
    if len(btc_closes) < 90 or len(closes) < 90:
        return None

    # BTC 自身の線形外挿(過去 45 日)
    n = min(45, len(btc_closes))
    xs = list(range(n))
    btc_recent = btc_closes[-n:]
    mean_x = sum(xs) / n
    mean_y = sum(btc_recent) / n
    cov = sum((xs[i] - mean_x) * (btc_recent[i] - mean_y) for i in range(n))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None
    slope = cov / var_x
    intercept = mean_y - slope * mean_x
    btc_pred = slope * (n - 1 + days_ahead) + intercept
    btc_log_return = math.log(btc_pred / btc_closes[-1]) if btc_pred > 0 and btc_closes[-1] > 0 else 0

    # 銘柄と BTC のログリターン相関 + ベータ
    n_corr = min(90, len(btc_closes), len(closes))
    stock_rets = [
        math.log(closes[-i] / closes[-i - 1])
        for i in range(1, n_corr)
        if closes[-i - 1] > 0 and closes[-i] > 0
    ]
    btc_rets = [
        math.log(btc_closes[-i] / btc_closes[-i - 1])
        for i in range(1, n_corr)
        if btc_closes[-i - 1] > 0 and btc_closes[-i] > 0
    ]
    n_eff = min(len(stock_rets), len(btc_rets))
    if n_eff < 30:
        return None
    stock_rets, btc_rets = stock_rets[:n_eff], btc_rets[:n_eff]

    # ベータ = cov(stock, btc) / var(btc)
    mean_s = sum(stock_rets) / n_eff
    mean_b = sum(btc_rets) / n_eff
    cov_sb = sum((stock_rets[i] - mean_s) * (btc_rets[i] - mean_b) for i in range(n_eff))
    var_b = sum((b - mean_b) ** 2 for b in btc_rets)
    if var_b == 0:
        return None
    beta = cov_sb / var_b

    # 銘柄の予測 = ベータ × BTC ログリターン
    stock_log_return = beta * btc_log_return
    stock_log_return = max(-0.30, min(0.30, stock_log_return))  # 月 ±30% でクリップ
    predicted = closes[-1] * math.exp(stock_log_return)

    return {
        "predicted": predicted,
        "predicted_log_return": stock_log_return,
        "btc_predicted_log_return": btc_log_return,
        "beta": beta,
    }
