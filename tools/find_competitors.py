"""
find_competitors.py — 競合企業の自動探索

指定したティッカーの sector / industry を yfinance から取得し、
事前定義された業界マップから同業他社のティッカーを返す。

Usage:
  python tools/find_competitors.py <ticker> [--limit 5]

  ticker: 評価対象のティッカー
  --limit: 何社まで返すか(デフォルト 5)

出力: stdout に JSON
  {
    "ticker": "AAPL",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "competitors": ["MSFT", "GOOGL", "META", "AMZN", "SONY"]
  }

注意: 業界マップは静的辞書ベースで、yfinance の sector/industry をキーに引く。
       完全網羅ではないため、見つからない業種では空配列を返す。
"""

import argparse
import json
import sys
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print(json.dumps({"error": "yfinance not installed"}))
    sys.exit(1)


# 主要業界の代表企業マップ(US + JP)
# yfinance の "industry" 文字列をキーに、同業他社のティッカーリストを返す。
# 必要に応じて追加・編集する。
INDUSTRY_PEERS = {
    # Technology
    "Consumer Electronics": ["AAPL", "SONY", "6758.T", "005930.KS", "GRMN"],
    "Software - Infrastructure": ["MSFT", "ORCL", "CRM", "NOW", "ADBE"],
    "Software - Application": ["CRM", "NOW", "INTU", "ADBE", "WDAY"],
    "Internet Content & Information": ["GOOGL", "META", "BIDU", "BABA", "SNAP"],
    "Internet Retail": ["AMZN", "MELI", "JD", "BABA", "9984.T"],
    "Semiconductors": ["NVDA", "AMD", "INTC", "AVGO", "TXN", "8035.T"],
    "Semiconductor Equipment & Materials": ["ASML", "AMAT", "LRCX", "KLAC", "8035.T"],
    "Information Technology Services": ["ACN", "IBM", "CTSH", "INFY", "WIT"],

    # Auto
    "Auto Manufacturers": ["7203.T", "F", "GM", "TSLA", "STLA", "7267.T", "7201.T"],
    "Auto Parts": ["7267.T", "DENSO", "MGA", "ALV", "6902.T"],

    # Finance
    "Banks - Diversified": ["JPM", "BAC", "C", "WFC", "8306.T", "8316.T"],
    "Banks - Regional": ["USB", "PNC", "TFC", "8316.T", "8411.T"],
    "Insurance - Diversified": ["BRK-B", "AIG", "8766.T", "8725.T"],
    "Asset Management": ["BLK", "BX", "KKR", "APO"],
    "Capital Markets": ["GS", "MS", "SCHW", "IBKR", "8604.T"],

    # Healthcare
    "Drug Manufacturers - General": ["JNJ", "PFE", "MRK", "LLY", "4502.T", "4503.T"],
    "Biotechnology": ["AMGN", "VRTX", "REGN", "GILD", "BIIB"],
    "Medical Devices": ["MDT", "SYK", "ABT", "BSX", "EW"],

    # Consumer
    "Beverages - Non-Alcoholic": ["KO", "PEP", "MNST", "KDP"],
    "Packaged Foods": ["NESN.SW", "MDLZ", "GIS", "K", "2502.T", "2503.T"],
    "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DPZ"],
    "Apparel Retail": ["LULU", "RL", "TJX", "ROST", "9983.T"],
    "Specialty Retail": ["HD", "LOW", "TSCO", "BBY"],
    "Discount Stores": ["WMT", "TGT", "COST", "DG", "BJ"],

    # Communications
    "Entertainment": ["DIS", "NFLX", "WBD", "PARA", "SONY", "6758.T"],
    "Telecom Services": ["T", "VZ", "TMUS", "9433.T", "9432.T"],

    # Energy
    "Oil & Gas Integrated": ["XOM", "CVX", "BP", "SHEL", "TTE", "5020.T"],
    "Oil & Gas E&P": ["EOG", "OXY", "FANG", "PXD", "DVN"],

    # Industrials
    "Industrial Machinery": ["CAT", "DE", "EMR", "ETN", "6301.T", "6326.T"],
    "Aerospace & Defense": ["BA", "LMT", "RTX", "NOC", "GD"],
    "Building Products & Equipment": ["MAS", "FBHS", "AOS", "TT"],

    # Materials
    "Chemicals": ["LIN", "APD", "SHW", "ECL", "4063.T"],
    "Steel": ["NUE", "STLD", "CLF", "X", "5401.T", "5411.T"],

    # Real Estate
    "REIT - Residential": ["EQR", "AVB", "ESS", "MAA", "8951.T"],
    "REIT - Industrial": ["PLD", "DRE", "REXR", "EGP"],
}


def find_peers(ticker: str, limit: int = 5) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}
    sector = info.get("sector")
    industry = info.get("industry")
    name = info.get("longName") or info.get("shortName")

    competitors = []
    if industry and industry in INDUSTRY_PEERS:
        # 自社を除外して上位 N
        peers = [p for p in INDUSTRY_PEERS[industry] if p.upper() != ticker.upper()]
        competitors = peers[:limit]

    return {
        "ticker": ticker,
        "name": name,
        "sector": sector,
        "industry": industry,
        "competitors": competitors,
        "competitor_count": len(competitors),
        "fetched_at": datetime.now().isoformat(),
        "source": "yfinance + static industry map",
        "note": (
            "industry が業界マップに登録されていれば、代表的な同業他社のティッカーを返します。"
            "登録されていなければ空配列です。tools/find_competitors.py の INDUSTRY_PEERS を編集して拡張できます。"
            if competitors
            else (
                f"industry='{industry}' は業界マップ未登録です。"
                "tools/find_competitors.py の INDUSTRY_PEERS に追加するか、"
                "別途手動で同業他社を指定してください。"
            )
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Find industry peers")
    parser.add_argument("ticker", help="Ticker symbol")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    try:
        data = find_peers(args.ticker, args.limit)
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
