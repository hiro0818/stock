"""
predict.py — 1 ヶ月先株価予測(5 モデル + アンサンブル)

⚠️ 重要: 株価の 1 ヶ月先予測は学術的にもほぼ不可能とされている(ランダムウォーク仮説)。
本モジュールが返す値は「複数の素朴モデルが想定するレンジ」であり、的中を保証しない。
投資助言ではなく、議論のたたき台用。

5 モデル:
  A. linear         — 直近 30 日のトレンドを線形外挿
  B. mean_reversion — 現在値が MA200 に向けて部分回帰する仮定
  C. analyst        — yfinance のアナリスト目標株価(複数アナリストの平均)
  D. technical      — RSI/MACD/トレンド から方向感を仮定
  E. monte_carlo    — ヒストリカルボラティリティで価格分布を生成し中央値を返す

アンサンブル: 5 モデルの中央値(外れ値耐性)+ 加重平均(過去精度がある場合)
"""

from __future__ import annotations

import math
import statistics
from typing import Iterable

# ───────── ウォークフォワード検証から導出した重み(PDCA の Act)─────────
# 5 銘柄 × 50 サンプルの walk-forward 検証(2026-04-28 実施)で
# 各モデルの平均絶対誤差から導出した重み付き平均用の係数。
# 詳細: outputs/pdca_5stocks_report.md
WALK_FORWARD_WEIGHTS: dict[str, float] = {
    "technical": 0.35,        # 平均誤差 7.21%(最小)
    "mean_reversion": 0.25,   # 平均誤差 7.73%
    "monte_carlo": 0.25,      # 平均誤差 8.14%(方向当たり率は最高 54.4%)
    "linear": 0.15,           # 平均誤差 10.39%(最大、トレンド時に過大予測しがち)
    # アナリスト目標は時点が固定で walk-forward と整合しないため重みなし(参考値扱い)
}


# ───────── 個別モデル ─────────


def predict_linear(history: list[dict], days_ahead: int = 30) -> float | None:
    """直近 30 営業日の線形回帰でトレンド外挿。"""
    closes = [h["close"] for h in history[-30:] if h.get("close") is not None]
    if len(closes) < 10:
        return None
    n = len(closes)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(closes) / n
    cov = sum((xs[i] - mean_x) * (closes[i] - mean_y) for i in range(n))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return closes[-1]
    slope = cov / var_x
    intercept = mean_y - slope * mean_x
    return slope * (n - 1 + days_ahead) + intercept


def predict_mean_reversion(history: list[dict], days_ahead: int = 30) -> float | None:
    """現在値が MA200 に向けて部分回帰する仮定。
    30 営業日で MA200 まで距離の 30% を埋めると仮定。"""
    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 200:
        return None
    ma200 = sum(closes[-200:]) / 200
    current = closes[-1]
    pull = (ma200 - current) * 0.30 * (days_ahead / 30)
    return current + pull


def predict_analyst(summary: dict) -> float | None:
    """yfinance のアナリスト目標株価平均(target_mean_price)。"""
    return summary.get("target_mean_price")


def predict_technical(history: list[dict], technical: dict, days_ahead: int = 30) -> float | None:
    """RSI / MACD / トレンドから方向感を推定。
    最大 ±5% / 月 のレンジに収める保守的な式。"""
    closes = [h["close"] for h in history if h.get("close") is not None]
    if not closes:
        return None
    current = closes[-1]
    direction = 0.0

    rsi = technical.get("rsi14")
    if rsi is not None:
        if rsi < 30:
            direction += 0.4  # 売られすぎ → 反発
        elif rsi < 40:
            direction += 0.2
        elif rsi > 70:
            direction -= 0.4  # 買われすぎ → 調整
        elif rsi > 60:
            direction -= 0.1

    macd_hist = technical.get("macd_hist")
    if macd_hist is not None:
        if macd_hist > 0:
            direction += 0.2
        elif macd_hist < 0:
            direction -= 0.2

    trend = technical.get("trend") or ""
    if "完全強気配列" in trend:
        direction += 0.3
    elif "中期上昇" in trend:
        direction += 0.15
    elif "中期下降" in trend:
        direction -= 0.15
    elif "完全弱気配列" in trend:
        direction -= 0.3

    range_pos = technical.get("range_position")
    if range_pos is not None:
        if range_pos > 0.85:
            direction -= 0.15  # 上端は調整圧
        elif range_pos < 0.15:
            direction += 0.15

    # 最大 ±5% / 30 日に収める
    direction = max(-1.0, min(1.0, direction))
    pct = direction * 0.05 * (days_ahead / 30)
    return current * (1 + pct)


def predict_monte_carlo(history: list[dict], days_ahead: int = 30, n_paths: int = 500) -> dict | None:
    """ヒストリカルボラティリティで価格分布を生成し、中央値・25/75 パーセンタイルを返す。
    µ = 過去 90 日の対数リターン平均、σ = 過去 90 日の対数リターン標準偏差。
    """
    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 90:
        return None
    log_returns = []
    for i in range(1, len(closes[-91:])):
        log_returns.append(math.log(closes[-91 + i] / closes[-91 + i - 1]))
    if not log_returns:
        return None
    mu = statistics.mean(log_returns)
    sigma = statistics.stdev(log_returns) if len(log_returns) > 1 else 0
    current = closes[-1]

    # 簡易: 正規乱数 N 本のパス、最終日の中央値・分位点
    import random

    rng = random.Random(0)  # 再現性のため固定シード
    finals = []
    for _ in range(n_paths):
        s = current
        for _ in range(days_ahead):
            r = rng.gauss(mu, sigma)
            s *= math.exp(r)
        finals.append(s)
    finals.sort()
    p25 = finals[int(n_paths * 0.25)]
    p50 = finals[int(n_paths * 0.50)]
    p75 = finals[int(n_paths * 0.75)]
    return {
        "median": p50,
        "p25": p25,
        "p75": p75,
        "mu_daily": mu,
        "sigma_daily": sigma,
    }


# ───────── アンサンブル ─────────


def predict_all(
    history: list[dict],
    summary: dict,
    technical: dict,
    days_ahead: int = 30,
) -> dict:
    """全モデルを実行してまとめる。"""
    closes = [h["close"] for h in history if h.get("close") is not None]
    current = closes[-1] if closes else None

    out: dict = {
        "current": current,
        "days_ahead": days_ahead,
        "models": {},
        "ensemble": None,
        "ensemble_band": None,
    }

    out["models"]["linear"] = {
        "label": "線形回帰(直近30日)",
        "predicted": predict_linear(history, days_ahead),
        "method": "直近 30 営業日の終値を線形外挿",
    }
    out["models"]["mean_reversion"] = {
        "label": "平均回帰(MA200)",
        "predicted": predict_mean_reversion(history, days_ahead),
        "method": "現在値が MA200 に向けて 30 日で 30% 回帰すると仮定",
    }
    out["models"]["analyst"] = {
        "label": "アナリスト目標株価",
        "predicted": predict_analyst(summary),
        "method": "yfinance.target_mean_price(アナリスト平均、12 ヶ月目標)",
    }
    out["models"]["technical"] = {
        "label": "テクニカル方向感",
        "predicted": predict_technical(history, technical, days_ahead),
        "method": "RSI / MACD / MA配置 / レンジ位置から ±5%/月 内で推定",
    }
    mc = predict_monte_carlo(history, days_ahead)
    out["models"]["monte_carlo"] = {
        "label": "モンテカルロ(対数正規)",
        "predicted": mc["median"] if mc else None,
        "method": "過去 90 日の対数リターンで N=500 パス生成、中央値",
        "p25": mc["p25"] if mc else None,
        "p75": mc["p75"] if mc else None,
    }

    # アンサンブル(中央値): 外れ値耐性
    valid_preds = [m["predicted"] for m in out["models"].values() if m["predicted"] is not None]
    if valid_preds:
        out["ensemble"] = statistics.median(valid_preds)
        out["ensemble_band"] = {
            "low": min(valid_preds),
            "high": max(valid_preds),
        }

    # 重み付きアンサンブル(walk-forward 精度ベースの Act 反映版)
    weighted_sum = 0.0
    weight_total = 0.0
    contributions = {}
    for model_name, w in WALK_FORWARD_WEIGHTS.items():
        m = out["models"].get(model_name)
        if m and m.get("predicted") is not None:
            weighted_sum += m["predicted"] * w
            weight_total += w
            contributions[model_name] = w
    if weight_total > 0:
        out["weighted_ensemble"] = weighted_sum / weight_total
        out["weighted_ensemble_weights"] = contributions

    # 上昇率
    if out["ensemble"] and current:
        out["ensemble_change_pct"] = (out["ensemble"] - current) / current * 100
    if out.get("weighted_ensemble") and current:
        out["weighted_ensemble_change_pct"] = (out["weighted_ensemble"] - current) / current * 100

    return out
