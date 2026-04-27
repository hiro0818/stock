"""
fetch_stock.py — yfinance ラッパー

エージェント(researcher など)が Bash 経由で叩いて、銘柄データを JSON で取得する。

Usage:
  python tools/fetch_stock.py <ticker> [--mode summary|full|history|technical]

  ticker:
    - 米国株: AAPL, MSFT, GOOGL, ...
    - 日本株: 7203.T(トヨタ), 9984.T(ソフトバンクG), ...

  --mode:
    summary    ... 主要指標のみ(デフォルト)
    full       ... 主要指標 + 直近4四半期の財務 + 1年株価
    history    ... 1年分の日足株価のみ
    technical  ... 技術指標(MA20/50/200, RSI14, MACD, 出来高分析, 52週レンジ位置)

出力: stdout に JSON

注意: yfinance データは通常 15 分以上の遅延あり。リアルタイム判断には使えない。
"""

import argparse
import json
import sys
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print(
        json.dumps(
            {"error": "yfinance not installed. Run: pip install yfinance"}
        )
    )
    sys.exit(1)


def safe(v):
    """JSON シリアライズ可能に変換。NaN や datetime を string に。"""
    if v is None:
        return None
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        return v
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def get_summary(ticker: str) -> dict:
    """主要指標のサマリ。"""
    t = yf.Ticker(ticker)
    info = t.info or {}
    return {
        "ticker": ticker,
        "fetched_at": datetime.now().isoformat(),
        "source": "yfinance",
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "currency": info.get("currency"),
        "exchange": info.get("exchange"),
        "current_price": safe(
            info.get("currentPrice") or info.get("regularMarketPrice")
        ),
        "market_cap": safe(info.get("marketCap")),
        "trailing_pe": safe(info.get("trailingPE")),
        "forward_pe": safe(info.get("forwardPE")),
        "price_to_book": safe(info.get("priceToBook")),
        "trailing_eps": safe(info.get("trailingEps")),
        "forward_eps": safe(info.get("forwardEps")),
        "dividend_yield": safe(info.get("dividendYield")),
        "payout_ratio": safe(info.get("payoutRatio")),
        "beta": safe(info.get("beta")),
        "return_on_equity": safe(info.get("returnOnEquity")),
        "return_on_assets": safe(info.get("returnOnAssets")),
        "profit_margins": safe(info.get("profitMargins")),
        "operating_margins": safe(info.get("operatingMargins")),
        "revenue_growth": safe(info.get("revenueGrowth")),
        "earnings_growth": safe(info.get("earningsGrowth")),
        "debt_to_equity": safe(info.get("debtToEquity")),
        "current_ratio": safe(info.get("currentRatio")),
        "free_cashflow": safe(info.get("freeCashflow")),
        "fifty_two_week_high": safe(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": safe(info.get("fiftyTwoWeekLow")),
        "fifty_day_average": safe(info.get("fiftyDayAverage")),
        "two_hundred_day_average": safe(info.get("twoHundredDayAverage")),
        "analyst_recommendation": info.get("recommendationKey"),
        "target_mean_price": safe(info.get("targetMeanPrice")),
        "target_high_price": safe(info.get("targetHighPrice")),
        "target_low_price": safe(info.get("targetLowPrice")),
        "long_business_summary": info.get("longBusinessSummary"),
    }


def get_history(ticker: str, period: str = "1y") -> list:
    """日足の株価推移。"""
    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        return []
    out = []
    for idx, row in hist.iterrows():
        out.append(
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": safe(float(row["Open"])),
                "high": safe(float(row["High"])),
                "low": safe(float(row["Low"])),
                "close": safe(float(row["Close"])),
                "volume": int(row["Volume"]) if row["Volume"] else 0,
            }
        )
    return out


def get_financials(ticker: str) -> dict:
    """直近の財務諸表。"""
    t = yf.Ticker(ticker)

    def _df_to_dict(df):
        if df is None or df.empty:
            return {}
        out = {}
        for col in df.columns:
            key = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)
            out[key] = {str(idx): safe(v) for idx, v in df[col].items()}
        return out

    return {
        "income_statement_quarterly": _df_to_dict(t.quarterly_financials),
        "balance_sheet_quarterly": _df_to_dict(t.quarterly_balance_sheet),
        "cashflow_quarterly": _df_to_dict(t.quarterly_cashflow),
    }


def get_technical(ticker: str) -> dict:
    """技術指標(移動平均、RSI、MACD、出来高、52週レンジ位置)。"""
    t = yf.Ticker(ticker)
    hist = t.history(period="1y")
    if hist.empty:
        return {"ticker": ticker, "error": "no historical data"}

    close = hist["Close"]
    volume = hist["Volume"]
    last_close = float(close.iloc[-1])
    last_date = close.index[-1].strftime("%Y-%m-%d")

    # 移動平均
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    ma50 = float(close.tail(50).mean()) if len(close) >= 50 else None
    ma200 = float(close.tail(200).mean()) if len(close) >= 200 else None

    # RSI(14日)
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    rsi14 = float(rsi.iloc[-1]) if not (rsi.iloc[-1] != rsi.iloc[-1]) else None

    # MACD(12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    # 出来高(直近 vs 50日平均)
    vol50_avg = float(volume.tail(50).mean()) if len(volume) >= 50 else None
    last_vol = int(volume.iloc[-1])
    vol_ratio = (last_vol / vol50_avg) if vol50_avg else None

    # 52週レンジ
    week52_high = float(close.max())
    week52_low = float(close.min())
    range_pos = (
        (last_close - week52_low) / (week52_high - week52_low)
        if week52_high > week52_low
        else None
    )

    # トレンド判定(MA配置から)
    trend = "不明"
    if ma20 and ma50 and ma200:
        if last_close > ma20 > ma50 > ma200:
            trend = "上昇トレンド(完全強気配列)"
        elif last_close < ma20 < ma50 < ma200:
            trend = "下降トレンド(完全弱気配列)"
        elif ma50 > ma200:
            trend = "中期上昇優勢"
        elif ma50 < ma200:
            trend = "中期下降優勢"
        else:
            trend = "もみ合い"

    # シグナル簡易判定
    signals = []
    if rsi14 is not None:
        if rsi14 > 70:
            signals.append(f"RSI {rsi14:.1f}: 買われすぎ警戒")
        elif rsi14 < 30:
            signals.append(f"RSI {rsi14:.1f}: 売られすぎ反発候補")
    if ma50 and ma200 and abs(ma50 - ma200) / ma200 < 0.005:
        signals.append("MA50 と MA200 が接近(ゴールデン/デッドクロス近辺)")
    if vol_ratio and vol_ratio > 2.0:
        signals.append(f"出来高 {vol_ratio:.1f} 倍: 平常の倍以上、注目")
    if range_pos is not None and range_pos < 0.1:
        signals.append("52週レンジの下端付近")
    if range_pos is not None and range_pos > 0.9:
        signals.append("52週レンジの上端付近")

    return {
        "ticker": ticker,
        "fetched_at": datetime.now().isoformat(),
        "source": "yfinance",
        "as_of": last_date,
        "last_close": last_close,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "rsi14": rsi14,
        "macd_line": float(macd_line.iloc[-1]),
        "macd_signal": float(signal_line.iloc[-1]),
        "macd_hist": float(macd_hist.iloc[-1]),
        "macd_status": (
            "プラス圏(強気)" if macd_hist.iloc[-1] > 0 else "マイナス圏(弱気)"
        ),
        "volume_last": last_vol,
        "volume_50d_avg": vol50_avg,
        "volume_ratio_vs_50d": vol_ratio,
        "week52_high": week52_high,
        "week52_low": week52_low,
        "range_position": range_pos,
        "range_position_label": (
            "上端付近"
            if range_pos and range_pos > 0.8
            else "下端付近"
            if range_pos and range_pos < 0.2
            else "レンジ中央"
            if range_pos is not None
            else None
        ),
        "trend": trend,
        "signals": signals,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch stock data via yfinance")
    parser.add_argument("ticker", help="Ticker symbol (AAPL, 7203.T, ...)")
    parser.add_argument(
        "--mode",
        choices=["summary", "full", "history", "technical"],
        default="summary",
    )
    parser.add_argument("--period", default="1y", help="History period (1y, 6mo, ...)")
    args = parser.parse_args()

    try:
        if args.mode == "summary":
            data = get_summary(args.ticker)
        elif args.mode == "history":
            data = {
                "ticker": args.ticker,
                "fetched_at": datetime.now().isoformat(),
                "source": "yfinance",
                "history": get_history(args.ticker, args.period),
            }
        elif args.mode == "technical":
            data = get_technical(args.ticker)
        elif args.mode == "full":
            data = get_summary(args.ticker)
            data["history_1y"] = get_history(args.ticker, "1y")
            data["financials"] = get_financials(args.ticker)
            data["technical"] = get_technical(args.ticker)
        else:
            data = {"error": f"unknown mode: {args.mode}"}

        # name が None のときは "ticker not found or invalid" の可能性
        # summary / full モードのみ name チェック(technical / history は会社名を取らない)
        if args.mode in ("summary", "full") and data.get("name") is None:
            data["warning"] = (
                "longName/shortName が取得できませんでした。"
                "ティッカーが間違っている、または yfinance に登録がない可能性があります。"
            )

        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    except Exception as e:
        print(
            json.dumps(
                {"ticker": args.ticker, "error": str(e), "error_type": type(e).__name__},
                ensure_ascii=False,
            )
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
