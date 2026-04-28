"""
technical_advanced.py — 文献ベースのテクニカル指標(7 種)+ 短期予測モデル

採用論文:
  - Brock, Lakonishok, LeBaron (1992) — MA クロスオーバーの有効性
  - Lo, Mamaysky, Wang (2000) — パターン認識(本実装では数値指標で代替)
  - Park & Irwin (2007) — テクニカル分析の有効性メタ分析
  - Han, Yang, Zhou (2013) — MA 戦略は高ボラ銘柄で特に有効
  - Jensen, Kelly, Pedersen (2023) — モメンタム/低ボラは再現可能なファクター

実装する指標:
  1. Bollinger Bands(±2σ、過熱・底値判定)
  2. Stochastic Oscillator(%K, %D、短期過熱)
  3. ADX(Average Directional Index、トレンド強度)
  4. ATR(Average True Range、ボラティリティ)
  5. OBV(On-Balance Volume、出来高累積)
  6. Donchian Channel(20 日高安、ブレイクアウト)
  7. CCI(Commodity Channel Index、価格偏差)

加えて:
  - predict_short_term: 5/10/21 営業日先の短期予測(投資スタイル 1 年未満向け)

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import math
import statistics


def bollinger_bands(closes: list[float], window: int = 20, n_std: float = 2.0) -> dict | None:
    """Bollinger Bands。中心 = MA20、上下 = MA20 ± 2σ。"""
    if len(closes) < window:
        return None
    recent = closes[-window:]
    mean = sum(recent) / window
    std = statistics.stdev(recent) if len(recent) > 1 else 0
    upper = mean + n_std * std
    lower = mean - n_std * std
    last = closes[-1]
    # %B(0=下端、1=上端、>1 上抜け、<0 下抜け)
    pct_b = (last - lower) / (upper - lower) if upper > lower else 0.5
    # バンド幅(ボラティリティ指標)
    bandwidth = (upper - lower) / mean if mean > 0 else 0
    return {
        "upper": upper,
        "middle": mean,
        "lower": lower,
        "last": last,
        "pct_b": pct_b,
        "bandwidth": bandwidth,
        "signal": (
            "上抜け(過熱)" if pct_b > 1.0
            else "下抜け(過売)" if pct_b < 0.0
            else "上端付近" if pct_b > 0.85
            else "下端付近" if pct_b < 0.15
            else "中立"
        ),
    }


def stochastic_oscillator(
    highs: list[float], lows: list[float], closes: list[float], k_window: int = 14, d_window: int = 3
) -> dict | None:
    """Stochastic Oscillator。%K と %D(SMA)。70/30 で過熱・過売。"""
    if len(closes) < k_window + d_window:
        return None
    k_values = []
    for i in range(k_window - 1, len(closes)):
        h = max(highs[i - k_window + 1: i + 1])
        l = min(lows[i - k_window + 1: i + 1])
        c = closes[i]
        k = 100 * (c - l) / (h - l) if h > l else 50
        k_values.append(k)
    if len(k_values) < d_window:
        return None
    last_k = k_values[-1]
    last_d = sum(k_values[-d_window:]) / d_window
    return {
        "%K": last_k,
        "%D": last_d,
        "signal": (
            "買われすぎ" if last_k > 80
            else "売られすぎ" if last_k < 20
            else "中立"
        ),
        "cross": (
            "買い(K>D)" if last_k > last_d else "売り(K<D)"
        ),
    }


def true_range(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    """各日の True Range(高安幅 + 前日終値からのギャップ)。"""
    out = []
    for i in range(len(closes)):
        if i == 0:
            out.append(highs[i] - lows[i])
            continue
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        out.append(tr)
    return out


def atr(highs: list[float], lows: list[float], closes: list[float], window: int = 14) -> float | None:
    """Average True Range(ボラティリティ指標)。"""
    trs = true_range(highs, lows, closes)
    if len(trs) < window:
        return None
    return sum(trs[-window:]) / window


def adx(highs: list[float], lows: list[float], closes: list[float], window: int = 14) -> dict | None:
    """ADX(Average Directional Index)。トレンドの強さ(0-100)。25 超えで強いトレンド。"""
    if len(closes) < window * 2:
        return None
    trs = true_range(highs, lows, closes)
    plus_dm = []
    minus_dm = []
    for i in range(1, len(highs)):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if up > down and up > 0 else 0)
        minus_dm.append(down if down > up and down > 0 else 0)
    if len(plus_dm) < window:
        return None
    tr_w = sum(trs[-window:])
    if tr_w == 0:
        return None
    plus_di = 100 * sum(plus_dm[-window:]) / tr_w
    minus_di = 100 * sum(minus_dm[-window:]) / tr_w
    di_sum = plus_di + minus_di
    if di_sum == 0:
        return None
    dx = 100 * abs(plus_di - minus_di) / di_sum
    # ADX は DX の SMA だが、簡易的に直近 DX を返す(Wilders smoothing 省略)
    return {
        "ADX": dx,
        "+DI": plus_di,
        "-DI": minus_di,
        "trend_strength": (
            "強いトレンド" if dx > 25
            else "弱いトレンド/もみ合い" if dx < 20
            else "中立"
        ),
        "direction": (
            "上昇優勢" if plus_di > minus_di else "下降優勢"
        ),
    }


def obv(closes: list[float], volumes: list[float]) -> list[float]:
    """On-Balance Volume(出来高累積)。価格上昇時は出来高加算、下降時は減算。"""
    out = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            out.append(out[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            out.append(out[-1] - volumes[i])
        else:
            out.append(out[-1])
    return out


def obv_signal(closes: list[float], volumes: list[float], window: int = 20) -> dict | None:
    """OBV の傾きで上昇/下降を判定 + 価格との乖離(ダイバージェンス)を検出。"""
    if len(closes) < window or len(volumes) < window:
        return None
    obv_series = obv(closes, volumes)
    if len(obv_series) < window:
        return None
    obv_recent = obv_series[-window:]
    price_recent = closes[-window:]
    # 線形回帰で傾き
    n = window
    xs = list(range(n))
    mx = sum(xs) / n
    my_o = sum(obv_recent) / n
    my_p = sum(price_recent) / n
    vx = sum((x - mx) ** 2 for x in xs)
    if vx == 0:
        return None
    slope_obv = sum((xs[i] - mx) * (obv_recent[i] - my_o) for i in range(n)) / vx
    slope_price = sum((xs[i] - mx) * (price_recent[i] - my_p) for i in range(n)) / vx
    obv_up = slope_obv > 0
    price_up = slope_price > 0
    divergence = obv_up != price_up
    return {
        "obv_slope": slope_obv,
        "price_slope": slope_price,
        "obv_trend": "上昇" if obv_up else "下降",
        "price_trend": "上昇" if price_up else "下降",
        "divergence": divergence,
        "signal": (
            "OBV/価格ダイバージェンス警戒" if divergence
            else "出来高一致(トレンド裏付け)"
        ),
    }


def donchian_channel(highs: list[float], lows: list[float], closes: list[float], window: int = 20) -> dict | None:
    """Donchian Channel(N 日高安)+ ブレイクアウト判定。"""
    if len(closes) < window:
        return None
    high_n = max(highs[-window:])
    low_n = min(lows[-window:])
    last = closes[-1]
    breakout = (
        f"上方ブレイクアウト({window}日高値更新)" if last >= high_n
        else f"下方ブレイクアウト({window}日安値更新)" if last <= low_n
        else "レンジ内"
    )
    return {
        "high": high_n,
        "low": low_n,
        "middle": (high_n + low_n) / 2,
        "last": last,
        "breakout": breakout,
        "position": (last - low_n) / (high_n - low_n) if high_n > low_n else 0.5,
    }


def cci(highs: list[float], lows: list[float], closes: list[float], window: int = 20) -> dict | None:
    """Commodity Channel Index(価格の偏差ベース)。±100 で過熱/過売。"""
    if len(closes) < window:
        return None
    tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
    recent_tp = tp[-window:]
    mean_tp = sum(recent_tp) / window
    md = sum(abs(p - mean_tp) for p in recent_tp) / window
    if md == 0:
        return None
    last_cci = (tp[-1] - mean_tp) / (0.015 * md)
    return {
        "CCI": last_cci,
        "signal": (
            "強い買われすぎ" if last_cci > 200
            else "買われすぎ" if last_cci > 100
            else "強い売られすぎ" if last_cci < -200
            else "売られすぎ" if last_cci < -100
            else "中立"
        ),
    }


def all_advanced(history: list[dict]) -> dict:
    """7 指標を一括計算。"""
    closes = [h["close"] for h in history if h.get("close") is not None]
    highs = [h["high"] for h in history if h.get("high") is not None]
    lows = [h["low"] for h in history if h.get("low") is not None]
    volumes = [h.get("volume", 0) for h in history]
    n = min(len(closes), len(highs), len(lows), len(volumes))
    closes, highs, lows, volumes = closes[-n:], highs[-n:], lows[-n:], volumes[-n:]
    return {
        "bollinger": bollinger_bands(closes),
        "stochastic": stochastic_oscillator(highs, lows, closes),
        "adx": adx(highs, lows, closes),
        "atr": atr(highs, lows, closes),
        "obv": obv_signal(closes, volumes),
        "donchian": donchian_channel(highs, lows, closes),
        "cci": cci(highs, lows, closes),
    }


# ───────── 短期予測モデル(投資スタイル 1 年未満)─────────


def predict_technical_advanced(history: list[dict], days_ahead: int = 21) -> dict | None:
    """7 つのテクニカル指標を統合した方向感推定モデル。
    短期(5/10/21 営業日)向け。各指標の方向を投票して、加重平均で価格変化率を出す。

    投票ルール:
      - Bollinger %B > 0.85: 過熱(-)、< 0.15: 反発期待(+)
      - Stochastic %K > 80: 過熱(-)、< 20: 反発(+)
      - ADX > 25 + +DI > -DI: 強い上昇(+)、ADX > 25 + -DI > +DI: 強い下降(-)
      - OBV ダイバージェンス: 警戒(逆方向)
      - Donchian 上抜け: 強気(+)、下抜け: 弱気(-)
      - CCI > 100: 過熱(-)、< -100: 反発(+)
    """
    closes = [h["close"] for h in history if h.get("close") is not None]
    if len(closes) < 50:
        return None

    indicators = all_advanced(history)
    score = 0.0  # 正なら強気、負なら弱気
    votes = []

    bb = indicators.get("bollinger")
    if bb:
        if bb["pct_b"] > 1.0:
            score -= 0.5
            votes.append(("Bollinger 上抜け", -0.5))
        elif bb["pct_b"] > 0.85:
            score -= 0.2
            votes.append(("Bollinger 上端", -0.2))
        elif bb["pct_b"] < 0.0:
            score += 0.5
            votes.append(("Bollinger 下抜け", 0.5))
        elif bb["pct_b"] < 0.15:
            score += 0.2
            votes.append(("Bollinger 下端", 0.2))

    stoch = indicators.get("stochastic")
    if stoch:
        k = stoch["%K"]
        if k > 80:
            score -= 0.3
            votes.append(("Stochastic 過熱", -0.3))
        elif k < 20:
            score += 0.3
            votes.append(("Stochastic 過売", 0.3))
        if stoch["%K"] > stoch["%D"]:
            score += 0.1
            votes.append(("Stochastic K>D", 0.1))
        else:
            score -= 0.1
            votes.append(("Stochastic K<D", -0.1))

    ad = indicators.get("adx")
    if ad:
        if ad["ADX"] > 25:
            if ad["+DI"] > ad["-DI"]:
                score += 0.4
                votes.append(("ADX 強上昇", 0.4))
            else:
                score -= 0.4
                votes.append(("ADX 強下降", -0.4))

    ob = indicators.get("obv")
    if ob and ob["divergence"]:
        # ダイバージェンス: 価格と OBV が逆方向
        if ob["price_trend"] == "上昇":
            # 価格上昇だが出来高減 → 上昇続かない
            score -= 0.3
            votes.append(("OBV 逆ダイバージェンス", -0.3))
        else:
            score += 0.3
            votes.append(("OBV 正ダイバージェンス", 0.3))

    dc = indicators.get("donchian")
    if dc:
        if "上方" in dc["breakout"]:
            score += 0.4
            votes.append(("Donchian 上方 BO", 0.4))
        elif "下方" in dc["breakout"]:
            score -= 0.4
            votes.append(("Donchian 下方 BO", -0.4))

    ci = indicators.get("cci")
    if ci:
        if ci["CCI"] > 200:
            score -= 0.4
            votes.append(("CCI 強過熱", -0.4))
        elif ci["CCI"] > 100:
            score -= 0.15
            votes.append(("CCI 過熱", -0.15))
        elif ci["CCI"] < -200:
            score += 0.4
            votes.append(("CCI 強過売", 0.4))
        elif ci["CCI"] < -100:
            score += 0.15
            votes.append(("CCI 過売", 0.15))

    # スコアを月 ±5% に変換(クリップ)
    score = max(-2.0, min(2.0, score))
    pct_change = score / 2.0 * 0.05 * (days_ahead / 21)
    current = closes[-1]
    predicted = current * (1 + pct_change)

    return {
        "predicted": predicted,
        "predicted_change_pct": pct_change * 100,
        "score": score,
        "votes": votes,
        "indicators": indicators,
    }
