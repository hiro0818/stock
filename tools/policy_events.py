"""
policy_events.py — 米中日政府の政策・地政学イベントの参照モジュール

3 つのアプローチを組み合わせる:
  1. **既知の定例イベントカレンダー**(FOMC・日銀政策決定会合・全人代など)
  2. **公的資料へのリンク**(FRB / 日銀 / 中国人民銀行)
  3. **Google ニュース検索リンク**(キーワードベース、リアルタイム参照用)

リアルタイムなトランプ発言・FRB 議長声明などのテキスト取得は、
SNS ボットブロック・翻訳 API コストの問題で困難なため、
**「クリックで開いて自分で読む」設計**にしている。

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

from datetime import date
from urllib.parse import quote


# ───────── 米中日の主要政策イベント(年中行事ベース)─────────


def upcoming_recurring_events() -> list[dict]:
    """毎年・毎月決まって発生する主要政策イベントの参照リスト。
    ソース: FRB / 日銀 / 中国共産党スケジュール。具体的な日程はここでは扱わない
    (年により変わるため)、各リンクで直接確認する想定。"""
    return [
        # 米国
        {
            "country": "🇺🇸 米国",
            "event": "FOMC(連邦公開市場委員会)",
            "frequency": "年 8 回(約 6 週間ごと)",
            "impact": "政策金利決定 → 全資産に直接影響、特に高 PER 銘柄・債券・ドル",
            "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        },
        {
            "country": "🇺🇸 米国",
            "event": "雇用統計(NFP)",
            "frequency": "毎月第一金曜",
            "impact": "FRB の利下げ判断材料 → 株式・ドル円に直接影響",
            "url": "https://www.bls.gov/schedule/news_release/empsit.htm",
        },
        {
            "country": "🇺🇸 米国",
            "event": "CPI(消費者物価指数)",
            "frequency": "毎月中旬",
            "impact": "インフレ動向 → 利下げ観測 → 株式・債券に影響",
            "url": "https://www.bls.gov/schedule/news_release/cpi.htm",
        },
        {
            "country": "🇺🇸 米国",
            "event": "大統領発言・関税発表",
            "frequency": "随時",
            "impact": "貿易関係銘柄(自動車・半導体・小売)に短期で大きな影響",
            "url": "https://www.whitehouse.gov/news/",
        },
        # 日本
        {
            "country": "🇯🇵 日本",
            "event": "日銀金融政策決定会合",
            "frequency": "年 8 回",
            "impact": "政策金利・YCC → 円相場 → 輸出企業の採算と日本株全体に影響",
            "url": "https://www.boj.or.jp/mopo/mpmsche_minu/index.htm/",
        },
        {
            "country": "🇯🇵 日本",
            "event": "為替介入",
            "frequency": "随時(円安進行時)",
            "impact": "ドル円急変 → 日本輸出企業(7203/6758)、輸入企業に逆方向の影響",
            "url": "https://www.mof.go.jp/policy/international_policy/reference/feio/index.html",
        },
        {
            "country": "🇯🇵 日本",
            "event": "東証プライム市場 月次パフォーマンス",
            "frequency": "毎月初",
            "impact": "TOPIX/日経 225 のリバランス、機関投資家の月次ロロ",
            "url": "https://www.jpx.co.jp/markets/statistics-equities/index.html",
        },
        # 中国
        {
            "country": "🇨🇳 中国",
            "event": "全国人民代表大会(全人代)",
            "frequency": "年 1 回(3 月)",
            "impact": "成長目標・財政政策・産業育成 → 中国関連銘柄、原材料・コモディティ",
            "url": "https://www.npc.gov.cn/",
        },
        {
            "country": "🇨🇳 中国",
            "event": "中国人民銀行(PBoC)金融政策",
            "frequency": "随時",
            "impact": "預金準備率・LPR → 中国株、人民元、コモディティ需要",
            "url": "http://www.pbc.gov.cn/en/",
        },
        {
            "country": "🇨🇳 中国",
            "event": "中央経済工作会議",
            "frequency": "年 1 回(12 月)",
            "impact": "翌年の経済方針決定 → 中国関連銘柄、商品市況",
            "url": "http://www.gov.cn/",
        },
        {
            "country": "🇨🇳 中国",
            "event": "PMI(製造業景況感)",
            "frequency": "毎月初",
            "impact": "中国景気バロメーター → 鉄鉱石・銅・原油・日本機械株",
            "url": "http://www.stats.gov.cn/",
        },
    ]


# ───────── ニュース検索リンク(リアルタイム参照用)─────────


def policy_news_links_jp() -> list[dict]:
    """米中日政府関連ニュースを各種媒体で検索する URL を返す。
    クリックで Google ニュースなどが開き、最新の話題が見られる。"""
    return [
        # 米国
        {
            "country": "🇺🇸 米国",
            "label": "Trump 発言(Google ニュース、日本語)",
            "url": "https://news.google.com/search?q=" + quote("トランプ 発言 株価") + "&hl=ja",
        },
        {
            "country": "🇺🇸 米国",
            "label": "FRB 利上げ・利下げ(日本語)",
            "url": "https://news.google.com/search?q=" + quote("FRB 利下げ 利上げ パウエル") + "&hl=ja",
        },
        {
            "country": "🇺🇸 米国",
            "label": "Trump tariff(英語、最新発表)",
            "url": "https://news.google.com/search?q=" + quote("Trump tariff announcement") + "&hl=en-US",
        },
        {
            "country": "🇺🇸 米国",
            "label": "Fed FOMC statement(英語)",
            "url": "https://news.google.com/search?q=" + quote("Fed FOMC statement") + "&hl=en-US",
        },
        # 中国
        {
            "country": "🇨🇳 中国",
            "label": "習近平 発言・経済政策(日本語)",
            "url": "https://news.google.com/search?q=" + quote("習近平 中国 経済 政策") + "&hl=ja",
        },
        {
            "country": "🇨🇳 中国",
            "label": "中国 景気刺激策(日本語)",
            "url": "https://news.google.com/search?q=" + quote("中国 景気刺激 LPR PBoC") + "&hl=ja",
        },
        {
            "country": "🇨🇳 中国",
            "label": "China stimulus / Xi Jinping(英語)",
            "url": "https://news.google.com/search?q=" + quote("China stimulus Xi Jinping policy") + "&hl=en-US",
        },
        # 日本
        {
            "country": "🇯🇵 日本",
            "label": "日銀 政策金利・植田総裁",
            "url": "https://news.google.com/search?q=" + quote("日銀 政策金利 植田 為替") + "&hl=ja",
        },
        {
            "country": "🇯🇵 日本",
            "label": "為替介入・財務省",
            "url": "https://news.google.com/search?q=" + quote("為替介入 財務省 ドル円") + "&hl=ja",
        },
        {
            "country": "🇯🇵 日本",
            "label": "日本政府 経済政策・補正予算",
            "url": "https://news.google.com/search?q=" + quote("日本 経済政策 補正予算 政府") + "&hl=ja",
        },
        # 米中関係
        {
            "country": "🌐 米中関係",
            "label": "米中対立・関税戦争(日本語)",
            "url": "https://news.google.com/search?q=" + quote("米中 関税 半導体 規制") + "&hl=ja",
        },
        {
            "country": "🌐 米中関係",
            "label": "US-China trade tensions(英語)",
            "url": "https://news.google.com/search?q=" + quote("US China trade tariff semiconductor") + "&hl=en-US",
        },
        # AI・地政学(横断)
        {
            "country": "📡 AI / テック",
            "label": "AI ニュース日本語(ai-news.dev)",
            "url": "https://ai-news.dev/",
        },
        {
            "country": "📡 AI / テック",
            "label": "AI 半導体規制(日本語)",
            "url": "https://news.google.com/search?q=" + quote("AI 半導体 輸出規制") + "&hl=ja",
        },
    ]


# ───────── 銘柄ごとの政策影響度ヒント ─────────


def policy_relevance_for(ticker: str, summary: dict, themes_in: list[str]) -> list[dict]:
    """銘柄について、特に注視すべき政策分野を返す。"""
    ticker_upper = ticker.upper()
    is_jp = ticker_upper.endswith(".T")
    sector = (summary.get("sector") or "").lower()
    industry = (summary.get("industry") or "").lower()

    out: list[dict] = []

    # 半導体・AI 関連
    if any(t in themes_in for t in ("半導体", "AI 関連")) or "semiconductor" in industry:
        out.append(
            {
                "policy": "🇺🇸 米国の対中半導体輸出規制",
                "impact": "強化されると NVDA / AVGO / 8035.T などの中国売上が打撃。緩和されると株価上昇要因。",
            }
        )
        out.append(
            {
                "policy": "🇨🇳 中国の半導体国産化政策",
                "impact": "中国系メーカーが躍進すると、米半導体大手の中国シェアを失う。SMIC / Huawei 動向を監視。",
            }
        )

    # 金融
    if "financial" in sector or "金融" in str(themes_in):
        out.append(
            {
                "policy": "🇺🇸 FRB 政策金利",
                "impact": "利上げ → 銀行の利鞘改善。利下げ → 逆方向。FOMC 前後は要警戒。",
            }
        )
        if is_jp:
            out.append(
                {
                    "policy": "🇯🇵 日銀利上げ",
                    "impact": "国内金利上昇 → 邦銀の利鞘改善、銀行株上昇要因。",
                }
            )

    # エネルギー
    if "energy" in sector or "oil" in industry:
        out.append(
            {
                "policy": "🌐 OPEC+ 減産協議",
                "impact": "減産合意 → 原油上昇 → エネルギー銘柄追い風。",
            }
        )
        out.append(
            {
                "policy": "🇺🇸 米国の対イラン・対ロシア制裁",
                "impact": "強化で原油供給縮小 → 価格上昇。緩和で逆。",
            }
        )

    # 自動車
    if "auto" in industry:
        out.append(
            {
                "policy": "🇺🇸 米国の関税(自動車・部品)",
                "impact": "対メキシコ / 日本関税で 7203.T / 7267.T に逆風。",
            }
        )
        out.append(
            {
                "policy": "🇨🇳 中国 EV 補助金 / 規制",
                "impact": "BYD など中国 EV 躍進で TSLA / 日系の中国シェア圧迫。",
            }
        )

    # 日本株全般
    if is_jp:
        out.append(
            {
                "policy": "🇯🇵 為替介入(財務省)",
                "impact": "円急騰 → 輸出企業(7203/6758)に逆風。輸入企業には追い風。",
            }
        )
        out.append(
            {
                "policy": "🇯🇵 法人税・賃上げ政策",
                "impact": "賃上げ補助は内需株に追い風。法人税増は全体に逆風。",
            }
        )

    # ヘルスケア(米国制度)
    if "healthcare" in sector:
        out.append(
            {
                "policy": "🇺🇸 薬価規制(IRA 法、メディケア交渉)",
                "impact": "規制強化で大手ファーマの利益率圧縮リスク。LLY / JNJ / PFE が対象。",
            }
        )

    # 暗号通貨関連
    if any(t in themes_in for t in ("暗号通貨関連",)):
        out.append(
            {
                "policy": "🇺🇸 SEC の暗号規制",
                "impact": "ETF 承認 / 規制緩和で COIN / MSTR 上昇。罰金・規制強化で逆。",
            }
        )

    return out
