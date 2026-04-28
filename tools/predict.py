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

from correlation import find_top_correlations  # noqa: E402

# ───────── 20 サイクル PDCA で収束した重み(Act の自動学習結果)─────────
# 10 銘柄(AAPL/NVDA/MSFT/7203.T/6758.T/XOM/CVX/NEM/COIN/MSTR)× 5 年の
# walk-forward サンプルを使い、20 サイクルの重み更新ループ(誤差逆数比例 + 学習率 0.15)で
# 自動収束させた重み。詳細: outputs/pdca_loop_*.json と outputs/pdca_v2_report.md
#
# 5 モデル(マクロ連動を含む):
WALK_FORWARD_WEIGHTS: dict[str, float] = {
    # v3: 10 銘柄 × 7 モデル × 20 サイクル PDCA で自動収束した重み(2026-04-28、outputs/pdca_loop_20260428-1502.json)
    # 結果: 誤差 10.32%(v2: 10.47%)、方向当たり率 54.6%(v2: 53.2%)
    "crypto_linked": 0.171,   # 全銘柄での誤差最小 10.16%(暗号以外でも穏当な予測になる)
    "technical": 0.170,       # 既存最良、誤差 10.18%
    "lightgbm_ml": 0.152,     # ML、方向当たり率 56.2%(全モデル最良)
    "macro_linked": 0.151,    # マクロ連動 11.08%
    "mean_reversion": 0.144,  # 平均回帰 11.11%
    "monte_carlo": 0.126,     # MC 11.92%
    "linear": 0.085,          # 誤差 14.65% で最大、最小重み
}


# ───────── 個別モデル ─────────


def predict_linear(history: list[dict], days_ahead: int = 30, window: int = 45) -> float | None:
    """線形回帰でトレンド外挿。
    PDCA cycle 2: 窓を 30 → 45 日に拡張(短期過剰反応を抑制)。"""
    closes = [h["close"] for h in history[-window:] if h.get("close") is not None]
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


def predict_monte_carlo(history: list[dict], days_ahead: int = 30, n_paths: int = 1000) -> dict | None:
    # PDCA cycle 3: N=200 → 1000 でモンテカルロのノイズ削減
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


def predict_macro_linked(
    history: list[dict],
    macro_histories: dict[str, list[dict]],
    days_ahead: int = 30,
) -> dict | None:
    """銘柄と高相関のマクロ指標を特定し、それぞれの線形外挿を相関係数で加重して銘柄予測を作る。

    Args:
      history: 銘柄の履歴
      macro_histories: {macro_ticker: history}(マクロ指標の履歴)
      days_ahead: 何日先を予測するか

    Returns:
      {"predicted": float, "correlations": [...], "macro_changes": [...]}
    """
    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 90 or not macro_histories:
        return None

    current = closes[-1]

    # 相関計算(PDCA cycle 4: 閾値 0.3 → 0.35 で雑音相関を除外)
    correlations = find_top_correlations(
        history, macro_histories, window=90, min_abs_corr=0.35, top_n=5
    )
    if not correlations:
        return None

    # 各マクロ指標の対数リターンを線形外挿
    macro_log_predictions = {}
    macro_change_pcts = {}
    for c in correlations:
        m_ticker = c["ticker"]
        m_hist = macro_histories.get(m_ticker, [])
        m_closes = [h["close"] for h in m_hist if h.get("close") is not None]
        if len(m_closes) < 30:
            continue
        m_pred = predict_linear(m_hist, days_ahead)
        if m_pred is None or m_closes[-1] <= 0 or m_pred <= 0:
            continue
        log_return = math.log(m_pred / m_closes[-1])
        macro_log_predictions[m_ticker] = log_return
        macro_change_pcts[m_ticker] = (m_pred - m_closes[-1]) / m_closes[-1] * 100

    if not macro_log_predictions:
        return None

    # 加重平均(相関係数の絶対値で重み付け)
    weighted_sum = 0.0
    weight_sum = 0.0
    contributions = []
    for c in correlations:
        m_ticker = c["ticker"]
        if m_ticker not in macro_log_predictions:
            continue
        weight = abs(c["correlation"])
        macro_lr = macro_log_predictions[m_ticker]
        # 銘柄ログリターン = 相関係数 × マクロログリターン
        stock_lr = c["correlation"] * macro_lr
        weighted_sum += stock_lr * weight
        weight_sum += weight
        contributions.append(
            {
                "macro_ticker": m_ticker,
                "macro_label": c["label"],
                "correlation": c["correlation"],
                "macro_change_pct": macro_change_pcts[m_ticker],
                "stock_implied_change_pct": (math.exp(stock_lr) - 1) * 100,
            }
        )

    if weight_sum == 0:
        return None

    predicted_log_return = weighted_sum / weight_sum
    predicted = current * math.exp(predicted_log_return)

    return {
        "predicted": predicted,
        "predicted_change_pct": (predicted - current) / current * 100,
        "correlations": correlations,
        "contributions": contributions,
    }


# ───────── アンサンブル ─────────


def predict_all(
    history: list[dict],
    summary: dict,
    technical: dict,
    days_ahead: int = 30,
    macro_histories: dict[str, list[dict]] | None = None,
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

    # マクロ連動予測(macro_histories が提供されている場合のみ)
    if macro_histories:
        macro_pred = predict_macro_linked(history, macro_histories, days_ahead)
        if macro_pred:
            out["models"]["macro_linked"] = {
                "label": "マクロ連動(相関上位 5 指標の加重)",
                "predicted": macro_pred["predicted"],
                "method": "相関の高いマクロ指標(原油/金/BTC/金利/為替/ETF など)を線形外挿し、相関係数で加重",
                "correlations": macro_pred["correlations"],
                "contributions": macro_pred["contributions"],
            }
        else:
            out["models"]["macro_linked"] = {
                "label": "マクロ連動",
                "predicted": None,
                "method": "高相関(|r|≥0.35)のマクロ指標が見つからず実行不可",
            }

        # LightGBM ML 予測(PDCA cycle 7、データが十分な場合のみ)
        try:
            from predict_ml import predict_crypto_linked, predict_lightgbm
            ml_pred = predict_lightgbm(history, macro_histories, days_ahead)
            if ml_pred and "predicted" in ml_pred:
                out["models"]["lightgbm_ml"] = {
                    "label": "LightGBM ML(15特徴量+マクロ)",
                    "predicted": ml_pred["predicted"],
                    "method": (
                        "勾配ブースティング回帰。特徴量: 過去リターン(1d/5d/20d/60d/252d) + "
                        "ボラ + RSI + MA比 + MACD + 出来高比 + レンジ位置 + マクロログリターン。"
                        f"学習サンプル数 {ml_pred.get('n_train_samples')}"
                    ),
                    "top_features": ml_pred.get("top_features", {}),
                }
            # 暗号銘柄向け専用モデル(BTC が macro_histories に含まれる場合)
            btc_hist = macro_histories.get("BTC-USD")
            if btc_hist:
                crypto_pred = predict_crypto_linked(history, btc_hist, days_ahead)
                if crypto_pred:
                    out["models"]["crypto_linked"] = {
                        "label": "暗号連動(BTC ベータ)",
                        "predicted": crypto_pred["predicted"],
                        "method": (
                            f"銘柄 vs BTC のベータ ({crypto_pred['beta']:.2f}) × BTC 線形外挿。"
                            "暗号関連銘柄(COIN/MSTR)向けの専用モデル"
                        ),
                    }
        except Exception:
            pass

    # 予測値の極端値クリッピング(PDCA cycle 11: 月 ±20% を超える予測を抑制)
    if current:
        for m_name, m_data in out["models"].items():
            p = m_data.get("predicted")
            if p is not None and current > 0:
                change = (p - current) / current
                if change > 0.20:
                    m_data["predicted"] = current * 1.20
                    m_data["clipped"] = "上限+20%"
                elif change < -0.20:
                    m_data["predicted"] = current * 0.80
                    m_data["clipped"] = "下限-20%"

    # アンサンブル(PDCA cycle 5: median → trimmed mean(両端 20%トリム)で外れ値除外しつつ中心化)
    valid_preds = [m["predicted"] for m in out["models"].values() if m["predicted"] is not None]
    if valid_preds:
        sorted_preds = sorted(valid_preds)
        n = len(sorted_preds)
        if n >= 5:
            # 両端 20% を除外
            trim = max(1, int(n * 0.2))
            trimmed = sorted_preds[trim:-trim] if n - 2 * trim > 0 else sorted_preds
            out["ensemble"] = sum(trimmed) / len(trimmed)
        else:
            out["ensemble"] = statistics.median(sorted_preds)
        out["ensemble_band"] = {
            "low": sorted_preds[0],
            "high": sorted_preds[-1],
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
