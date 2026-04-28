"""
correlation.py — 銘柄とマクロ指標(ETF・先物・コモディティ・暗号通貨など)の相関分析

予測精度向上のため、銘柄ごとに「どのマクロ指標と連動しているか」を
動的に特定する。相関の高いマクロ指標を予測の根拠に採用する。

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import math
from datetime import datetime

# 候補となるマクロ指標(yfinance ティッカー)
MACRO_CANDIDATES: dict[str, dict] = {
    # 株式指数
    "^GSPC": {"label": "S&P 500", "category": "米株指数"},
    "^IXIC": {"label": "NASDAQ", "category": "米株指数"},
    "^DJI": {"label": "Dow 30", "category": "米株指数"},
    "^N225": {"label": "日経 225", "category": "日本株指数"},
    "^RUT": {"label": "Russell 2000", "category": "小型株指数"},
    # ボラティリティ
    "^VIX": {"label": "VIX(恐怖指数)", "category": "ボラティリティ"},
    # 金利
    "^TNX": {"label": "米 10 年金利", "category": "金利"},
    "^FVX": {"label": "米 5 年金利", "category": "金利"},
    # 為替
    "JPY=X": {"label": "ドル円", "category": "為替"},
    "EURUSD=X": {"label": "ユーロドル", "category": "為替"},
    # コモディティ(先物)
    "CL=F": {"label": "原油 WTI", "category": "コモディティ"},
    "BZ=F": {"label": "ブレント原油", "category": "コモディティ"},
    "GC=F": {"label": "金", "category": "コモディティ"},
    "SI=F": {"label": "銀", "category": "コモディティ"},
    "HG=F": {"label": "銅", "category": "コモディティ"},
    "NG=F": {"label": "天然ガス", "category": "コモディティ"},
    # 暗号通貨
    "BTC-USD": {"label": "ビットコイン", "category": "暗号通貨"},
    "ETH-USD": {"label": "イーサリアム", "category": "暗号通貨"},
    # 米国セクター ETF(連動株の特定に有用)
    "XLK": {"label": "Tech ETF", "category": "セクター ETF"},
    "XLF": {"label": "Financials ETF", "category": "セクター ETF"},
    "XLE": {"label": "Energy ETF", "category": "セクター ETF"},
    "XLV": {"label": "Healthcare ETF", "category": "セクター ETF"},
    "XLI": {"label": "Industrials ETF", "category": "セクター ETF"},
    "XLP": {"label": "Cons. Staples ETF", "category": "セクター ETF"},
    "XLY": {"label": "Cons. Discr. ETF", "category": "セクター ETF"},
    "XLB": {"label": "Materials ETF", "category": "セクター ETF"},
    "XLRE": {"label": "Real Estate ETF", "category": "セクター ETF"},
    "XLU": {"label": "Utilities ETF", "category": "セクター ETF"},
    "XLC": {"label": "Communications ETF", "category": "セクター ETF"},
    # その他
    "GLD": {"label": "金 ETF(GLD)", "category": "コモディティ ETF"},
    "USO": {"label": "原油 ETF(USO)", "category": "コモディティ ETF"},
    "TLT": {"label": "米長期債 ETF", "category": "債券 ETF"},
    "HYG": {"label": "ハイイールド社債 ETF", "category": "債券 ETF"},
    "DXY": {"label": "ドルインデックス", "category": "為替指数"},
}


def _close_series(history: list[dict]) -> list[float]:
    """履歴から終値配列を取り出す。"""
    return [h["close"] for h in history if h.get("close") is not None]


def _log_returns(closes: list[float]) -> list[float]:
    """対数リターンに変換。"""
    out = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0 and closes[i] > 0:
            out.append(math.log(closes[i] / closes[i - 1]))
    return out


def correlation(a: list[float], b: list[float]) -> float | None:
    """ピアソン相関係数。長さが違えば短い方に揃える。"""
    n = min(len(a), len(b))
    if n < 10:
        return None
    a, b = a[-n:], b[-n:]
    mean_a, mean_b = sum(a) / n, sum(b) / n
    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((x - mean_b) ** 2 for x in b)
    if var_a <= 0 or var_b <= 0:
        return None
    return cov / math.sqrt(var_a * var_b)


def find_top_correlations(
    stock_history: list[dict],
    macro_histories: dict[str, list[dict]],
    window: int = 90,
    min_abs_corr: float = 0.3,
    top_n: int = 5,
) -> list[dict]:
    """銘柄と複数マクロ指標の相関を計算し、上位 N を返す。

    Args:
      stock_history: 銘柄の history(get_history の出力)
      macro_histories: {マクロティッカー: history}
      window: 相関計算の窓(直近 N 日)
      min_abs_corr: 相関係数の絶対値がこれ以上のものだけ採用
      top_n: 上位 N 銘柄まで

    Returns:
      [{"ticker": "CL=F", "label": "原油 WTI", "category": "コモディティ", "correlation": 0.65, "n": 90}, ...]
    """
    stock_closes = _close_series(stock_history)
    if len(stock_closes) < window:
        return []
    stock_returns = _log_returns(stock_closes[-window:])

    results = []
    for m_ticker, m_hist in macro_histories.items():
        m_closes = _close_series(m_hist)
        if len(m_closes) < window:
            continue
        m_returns = _log_returns(m_closes[-window:])
        corr = correlation(stock_returns, m_returns)
        if corr is None:
            continue
        if abs(corr) >= min_abs_corr:
            info = MACRO_CANDIDATES.get(m_ticker, {})
            results.append(
                {
                    "ticker": m_ticker,
                    "label": info.get("label", m_ticker),
                    "category": info.get("category", "?"),
                    "correlation": round(corr, 3),
                    "abs_correlation": abs(corr),
                    "n": min(len(stock_returns), len(m_returns)),
                }
            )

    results.sort(key=lambda r: r["abs_correlation"], reverse=True)
    return results[:top_n]


def correlation_to_macro_change(
    correlations: list[dict],
    macro_predictions: dict[str, float],
) -> dict:
    """相関と各マクロの予測変化率(対数リターンベース)から、
    銘柄の予測変化率を加重平均で算出。

    Args:
      correlations: find_top_correlations の出力
      macro_predictions: {マクロティッカー: 予測対数リターン(例: 0.03 = +3%)}

    Returns:
      {"predicted_log_return": float, "weights": {ticker: weight}, "details": [...]}
    """
    if not correlations:
        return {"predicted_log_return": None, "weights": {}, "details": []}

    weighted_sum = 0.0
    total_weight = 0.0
    details = []
    weights = {}
    for c in correlations:
        m_ticker = c["ticker"]
        if m_ticker not in macro_predictions:
            continue
        macro_log_return = macro_predictions[m_ticker]
        # 相関係数を重みとして、銘柄リターン = 相関 × マクロリターン
        contribution = c["correlation"] * macro_log_return
        weight = abs(c["correlation"])
        weighted_sum += contribution * weight
        total_weight += weight
        weights[m_ticker] = weight
        details.append(
            {
                "macro_ticker": m_ticker,
                "macro_label": c["label"],
                "correlation": c["correlation"],
                "macro_log_return": macro_log_return,
                "contribution": contribution,
            }
        )
    if total_weight == 0:
        return {"predicted_log_return": None, "weights": {}, "details": details}
    predicted = weighted_sum / total_weight
    return {
        "predicted_log_return": predicted,
        "weights": weights,
        "details": details,
        "total_weight": total_weight,
    }
