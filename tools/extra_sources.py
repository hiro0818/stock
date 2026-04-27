"""
extra_sources.py — yfinance 以外の追加データソース

採用したもの:
  - yfinance ニュース      ── Yahoo Finance 経由、認証不要
  - Google Trends(pytrends)── キーワード検索ボリューム、認証不要
  - X 検索リンク           ── 自動取得は不可(ボット対策)、新タブで開くリンクのみ提供
  - StockTwits リンク      ── 同上

不採用:
  - X 公式 API(2023 以降、無料枠ほぼ廃止)
  - StockTwits API(Cloudflare ボット保護で 403)
  - Reddit API(client_id/secret 登録必須、面倒)
  - Twitter スクレイピング系(規約違反 + 不安定)
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None


# ───────── yfinance ニュース ─────────


def get_yfinance_news(ticker: str, limit: int = 10) -> list[dict]:
    """yfinance 内蔵のニュースを取得。10 件程度返る。"""
    if yf is None:
        return []
    try:
        t = yf.Ticker(ticker)
        news = t.news or []
    except Exception:
        return []

    out = []
    for n in news[:limit]:
        # yfinance v1.x で構造が変わっており、n["content"] にネストされる場合がある
        content = n.get("content") if isinstance(n, dict) else None
        c = content if isinstance(content, dict) else (n if isinstance(n, dict) else {})
        publisher = c.get("provider", {}).get("displayName") if isinstance(c.get("provider"), dict) else c.get("publisher")
        pub_date = c.get("pubDate") or c.get("providerPublishTime")
        # providerPublishTime は UNIX 秒の場合あり
        if isinstance(pub_date, (int, float)):
            pub_date = datetime.fromtimestamp(pub_date).isoformat()
        canonical_url = c.get("canonicalUrl", {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else (c.get("link") or "")
        out.append(
            {
                "title": c.get("title") or "(タイトル取得失敗)",
                "publisher": publisher or "(出典不明)",
                "published": pub_date,
                "url": canonical_url,
                "summary": (c.get("summary") or "")[:300],
            }
        )
    return out


# ───────── Google Trends ─────────


def get_google_trends(keywords: list[str], timeframe: str = "today 3-m") -> dict:
    """指定キーワードの Google Trends データを取得。最大 5 キーワードまで。

    timeframe:
      "today 1-m"  ── 過去 1 ヶ月
      "today 3-m"  ── 過去 3 ヶ月(デフォルト)
      "today 12-m" ── 過去 1 年
      "today 5-y"  ── 過去 5 年
    """
    if TrendReq is None:
        return {"error": "pytrends がインストールされていません: pip install pytrends"}

    keywords = keywords[:5]
    try:
        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(10, 25))
        pytrends.build_payload(keywords, timeframe=timeframe, geo="")
        df = pytrends.interest_over_time()
        if df is None or df.empty:
            return {"error": "Google Trends からデータが返りませんでした", "keywords": keywords}

        # DataFrame を辞書化
        df = df.drop(columns=["isPartial"], errors="ignore")
        result = {
            "keywords": keywords,
            "timeframe": timeframe,
            "fetched_at": datetime.now().isoformat(),
            "series": {kw: df[kw].astype(int).tolist() for kw in df.columns},
            "dates": [d.strftime("%Y-%m-%d") for d in df.index],
            "latest": {kw: int(df[kw].iloc[-1]) for kw in df.columns},
        }
        # トレンド傾向(直近 7 日 vs それ以前の差)
        if len(df) >= 14:
            trend_signal = {}
            for kw in df.columns:
                recent = df[kw].iloc[-7:].mean()
                before = df[kw].iloc[-14:-7].mean()
                pct = (recent - before) / before * 100 if before > 0 else 0
                trend_signal[kw] = {
                    "recent_7d_avg": round(float(recent), 1),
                    "previous_7d_avg": round(float(before), 1),
                    "change_pct": round(float(pct), 1),
                    "label": (
                        "上昇(注目度↑)" if pct > 15
                        else "下降(注目度↓)" if pct < -15
                        else "横ばい"
                    ),
                }
            result["trend_signal"] = trend_signal
        return result
    except Exception as e:
        return {"error": f"Google Trends 取得失敗: {e}", "keywords": keywords}


# ───────── X(旧 Twitter)/ StockTwits 検索リンク ─────────


def x_search_url(ticker: str) -> str:
    """X(旧 Twitter)の銘柄キャッシュタグ検索 URL。新タブで開けば最新ツイートが見られる。"""
    return f"https://x.com/search?q={quote('$' + ticker.upper())}&f=live"


def stocktwits_url(ticker: str) -> str:
    """StockTwits の銘柄ページ URL。"""
    return f"https://stocktwits.com/symbol/{ticker.upper()}"


def yahoo_finance_url(ticker: str) -> str:
    """Yahoo Finance の銘柄ページ URL。"""
    return f"https://finance.yahoo.com/quote/{ticker}/"


def all_external_links(ticker: str, name: str | None = None) -> list[dict]:
    """銘柄に関する外部リンクをまとめて返す。"""
    nm = name or ticker
    return [
        {
            "label": "📰 X 検索(キャッシュタグ)",
            "url": x_search_url(ticker),
            "description": "$AAPL のような形でリアルタイムツイートを検索。新タブで開く。",
        },
        {
            "label": "💬 StockTwits",
            "url": stocktwits_url(ticker),
            "description": "株専門 SNS。bullish/bearish 投稿を閲覧。",
        },
        {
            "label": "📊 Yahoo Finance",
            "url": yahoo_finance_url(ticker),
            "description": "公式の銘柄ページ。チャート、決算、ニュース。",
        },
        {
            "label": "🔍 Google ニュース",
            "url": f"https://news.google.com/search?q={quote(nm + ' stock')}&hl=ja",
            "description": f"{nm} の最新ニュースを Google ニュースで検索。",
        },
        {
            "label": "📈 TradingView",
            "url": f"https://www.tradingview.com/symbols/{ticker.upper()}/",
            "description": "高機能チャート。テクニカル分析の定番。",
        },
    ]
