"""
backtest.py — 過去のデータでモデル精度を即評価(疑似 PDCA の Check 部分)

「もし 30 営業日前の時点で各モデルを使って予測していたら、
今と比べてどのくらいズレていたか」を計算する。

返り値: 各モデルの実績(予測値、実際値、誤差%、ヒット可否)+ 集計

⚠️ 過去精度は将来精度を保証しない。
"""

from __future__ import annotations

from predict import (
    predict_analyst,
    predict_linear,
    predict_mean_reversion,
    predict_monte_carlo,
    predict_technical,
)


HIT_THRESHOLD_PCT = 5.0  # 誤差 ±5% 以内をヒット扱い


def _technical_from_history(history: list[dict]) -> dict:
    """履歴(指定時点までのスライス)から、その時点での技術指標を簡易再計算。
    fetch_stock.get_technical のロジックを最低限再現する。"""
    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 30:
        return {}
    # MA
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    last = closes[-1]
    # RSI(14)
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-14:]]
    losses = [-d if d < 0 else 0 for d in deltas[-14:]]
    avg_gain = sum(gains) / 14 if gains else 0
    avg_loss = sum(losses) / 14 if losses else 0
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    # MACD(12, 26, 9) ─ 簡易 EMA
    def ema(xs, span):
        k = 2 / (span + 1)
        e = xs[0]
        for x in xs[1:]:
            e = e * (1 - k) + x * k
        return e

    if len(closes) >= 26:
        ema12 = ema(closes, 12)
        ema26 = ema(closes, 26)
        macd_line = ema12 - ema26
        # signal は単純化: 直近9日のMACDラインのEMA(再計算が重いので近似)
        macd_hist = macd_line  # 近似(真値より雑、バックテスト用)
    else:
        macd_line = 0
        macd_hist = 0
    # トレンド判定
    trend = "不明"
    if ma20 and ma50 and ma200:
        if last > ma20 > ma50 > ma200:
            trend = "上昇トレンド(完全強気配列)"
        elif last < ma20 < ma50 < ma200:
            trend = "下降トレンド(完全弱気配列)"
        elif ma50 > ma200:
            trend = "中期上昇優勢"
        elif ma50 < ma200:
            trend = "中期下降優勢"
        else:
            trend = "もみ合い"
    # 52 週レンジ位置
    week52_high = max(closes[-min(252, len(closes)):])
    week52_low = min(closes[-min(252, len(closes)):])
    range_pos = (last - week52_low) / (week52_high - week52_low) if week52_high > week52_low else None

    return {
        "rsi14": rsi,
        "macd_hist": macd_hist,
        "trend": trend,
        "range_position": range_pos,
    }


def backtest_one_month(history: list[dict], summary: dict, days_back: int = 30) -> dict:
    """30 営業日前にモデル予測を回したら、現在とどれだけズレたかを集計。"""
    if len(history) < days_back + 60:
        return {"error": "履歴が短すぎてバックテスト不能(最低 90 日必要)"}

    past_history = history[: -days_back]
    past_closes = [h["close"] for h in past_history if h.get("close") is not None]
    actual_closes = [h["close"] for h in history if h.get("close") is not None]
    actual_now = actual_closes[-1]
    past_now = past_closes[-1]

    past_tech = _technical_from_history(past_history)

    results = {}

    p = predict_linear(past_history, days_back)
    results["linear"] = _eval(p, actual_now, past_now)

    p = predict_mean_reversion(past_history, days_back)
    results["mean_reversion"] = _eval(p, actual_now, past_now)

    # アナリスト目標は過去時点の値が取れないため、「現在の target_mean_price」で代用(参考値)
    p = predict_analyst(summary)
    results["analyst"] = _eval(p, actual_now, past_now)
    results["analyst"]["note"] = "アナリスト目標は過去時点の値が取れないため参考値"

    p = predict_technical(past_history, past_tech, days_back)
    results["technical"] = _eval(p, actual_now, past_now)

    mc = predict_monte_carlo(past_history, days_back)
    results["monte_carlo"] = _eval(mc["median"] if mc else None, actual_now, past_now)

    # アンサンブル(中央値)
    import statistics

    valid = [r["predicted"] for r in results.values() if r.get("predicted") is not None]
    ensemble_pred = statistics.median(valid) if valid else None
    results["ensemble"] = _eval(ensemble_pred, actual_now, past_now)

    # 集計
    hits = sum(1 for r in results.values() if r.get("hit"))
    total = sum(1 for r in results.values() if r.get("predicted") is not None)
    avg_abs_error_pct = (
        sum(abs(r["error_pct"]) for r in results.values() if r.get("error_pct") is not None)
        / max(1, total)
    )

    return {
        "days_back": days_back,
        "past_close": past_now,
        "actual_now": actual_now,
        "actual_change_pct": (actual_now - past_now) / past_now * 100 if past_now else None,
        "models": results,
        "summary": {
            "hit_count": hits,
            "total_models": total,
            "hit_rate_pct": hits / total * 100 if total else 0,
            "avg_abs_error_pct": avg_abs_error_pct,
            "hit_threshold_pct": HIT_THRESHOLD_PCT,
        },
    }


def _eval(predicted, actual, past_close) -> dict:
    if predicted is None:
        return {"predicted": None, "error_pct": None, "hit": None}
    error_pct = (predicted - actual) / actual * 100
    hit = abs(error_pct) <= HIT_THRESHOLD_PCT
    direction_pred = predicted > past_close
    direction_actual = actual > past_close
    direction_hit = direction_pred == direction_actual
    return {
        "predicted": predicted,
        "actual": actual,
        "error_pct": error_pct,
        "hit": hit,
        "direction_hit": direction_hit,  # 上昇/下降の方向だけ当たったか
    }


def derive_weights_from_backtest(backtest_result: dict) -> dict:
    """バックテスト結果から、PDCA の Act にあたる「精度の高いモデルに重みを多く配分」を計算。"""
    models = backtest_result.get("models", {}) if isinstance(backtest_result, dict) else {}
    weights = {}
    for name, r in models.items():
        if name == "ensemble":
            continue
        err = r.get("error_pct")
        if err is None:
            weights[name] = 0
        else:
            # 誤差 0% でスコア 1.0、誤差 20% で 0.0(線形減衰)、それ以上は 0
            score = max(0.0, 1.0 - abs(err) / 20.0)
            weights[name] = score
    total_w = sum(weights.values())
    if total_w == 0:
        # 全部 0 なら均等
        n = len(weights)
        return {k: 1 / n for k in weights} if n else {}
    return {k: v / total_w for k, v in weights.items()}
