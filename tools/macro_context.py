"""
macro_context.py — 銘柄を起点としたマクロ環境の関連付け

ユーザーが入力した銘柄について、関連が深いマクロ指標(米金利、ドル円、原油、
業界 ETF など)を、関連度が高い順に返す。各指標について「どう影響するか」の
解釈コメントを付ける。

⚠️ 投資助言ではありません。
"""

from __future__ import annotations


def relevant_macros_for(ticker: str, summary: dict, themes_in: list[str]) -> list[dict]:
    """
    銘柄ティッカー、yfinance summary、所属テーマを受け取り、
    関連が深いマクロ指標のリストを返す。

    返り値: [{"label": ..., "ticker": ..., "reason": ...}, ...]
    """
    ticker_upper = ticker.upper()
    is_jp = ticker_upper.endswith(".T")
    sector = (summary.get("sector") or "").lower()
    industry = (summary.get("industry") or "").lower()
    pe = summary.get("trailing_pe") or 0
    high_pe = pe and pe > 30

    out: list[dict] = []

    # 共通の市場体温計
    out.append(
        {
            "label": "S&P 500",
            "ticker": "^GSPC",
            "reason": "米株市場全体の温度感。リスク選好の方向を示す。",
        }
    )

    # NASDAQ — テック / 高 PER 銘柄に強く関連
    if "tech" in sector or "communication" in sector or high_pe or any(
        t in themes_in for t in ("AI 関連", "半導体", "クラウド")
    ):
        out.append(
            {
                "label": "NASDAQ",
                "ticker": "^IXIC",
                "reason": "テック寄り指数。同銘柄もテック / グロース性質のため連動性が高い。",
            }
        )

    # 日経 — 日本株は当然
    if is_jp:
        out.append(
            {
                "label": "日経 225",
                "ticker": "^N225",
                "reason": "日本株主要指数。マーケット全体の方向を捉える。",
            }
        )

    # VIX — リスク資産全般に影響
    out.append(
        {
            "label": "VIX(恐怖指数)",
            "ticker": "^VIX",
            "reason": "上昇すると市場全体に売り圧。20 を境に警戒レベル。",
        }
    )

    # 米長期金利 — 高 PER 銘柄、金融、不動産に重要
    if high_pe or "financial" in sector or "real estate" in sector or any(
        t in themes_in for t in ("AI 関連", "半導体", "クラウド", "金融(銀行)")
    ):
        if "financial" in sector or "金融" in str(themes_in):
            reason = "上昇すると銀行の利鞘改善で追い風。下落で逆風。"
        elif "real estate" in sector:
            reason = "金利上昇は不動産銘柄に強い逆風(評価額・借入コスト)。"
        else:
            reason = "高 PER 銘柄に対して、金利上昇は割引率上昇 = 評価減のリスク。"
        out.append(
            {
                "label": "米 10 年金利",
                "ticker": "^TNX",
                "reason": reason,
            }
        )

    # ドル円 — 日本株、輸出関連
    if is_jp or "auto" in industry or "consumer electronics" in industry:
        out.append(
            {
                "label": "ドル円",
                "ticker": "JPY=X",
                "reason": "円安は日本輸出企業の採算改善。輸入物価 / 海外売上比率次第で正負逆転。",
            }
        )

    # 原油 — エネルギー、自動車、航空、素材
    if "energy" in sector or "auto" in industry or "airline" in industry or "material" in sector:
        out.append(
            {
                "label": "原油 WTI",
                "ticker": "CL=F",
                "reason": "エネルギーセクターは直接連動。輸送・自動車は逆相関(コスト面)。",
            }
        )

    # 金 — リスク回避指標
    if "防衛" in str(themes_in) or "高配当" in str(themes_in):
        out.append(
            {
                "label": "金",
                "ticker": "GC=F",
                "reason": "リスク回避局面で買われる。地政学リスクのバロメーター。",
            }
        )

    # ビットコイン — 暗号系
    if any(t in themes_in for t in ("暗号通貨関連",)):
        out.append(
            {
                "label": "ビットコイン",
                "ticker": "BTC-USD",
                "reason": "暗号関連株はBTC価格に強く連動する。",
            }
        )

    # 重複除去(label と ticker のペアでユニーク化)
    seen = set()
    unique = []
    for m in out:
        key = (m["label"], m["ticker"])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    return unique
