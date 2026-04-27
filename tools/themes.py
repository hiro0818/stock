"""
themes.py — テーマ別銘柄バスケット + マーケット指数の定義

ダッシュボードの「テーマ別」「メタトレンド」タブから参照される。
編集することでテーマを増減できる(コード追加不要、辞書だけ書き換え)。
"""

from __future__ import annotations

# ───────── テーマ別銘柄バスケット ─────────
THEMES: dict[str, dict] = {
    "半導体": {
        "description": "半導体製造・設計・装置メーカー。AI ブームの中核。米長期金利と中国市況に敏感。",
        "tickers": ["NVDA", "AMD", "INTC", "AVGO", "ASML", "TSM", "AMAT", "LRCX", "MU", "8035.T", "6857.T", "6920.T"],
        "leaders": ["NVDA", "AVGO", "ASML"],
    },
    "AI 関連": {
        "description": "生成 AI のインフラ・モデル・アプリ層。開発投資と業績の連動が議論の的。",
        "tickers": ["NVDA", "MSFT", "GOOGL", "META", "AVGO", "PLTR", "ORCL", "AMD", "CRM", "NOW"],
        "leaders": ["NVDA", "MSFT", "GOOGL"],
    },
    "クラウド": {
        "description": "ハイパースケーラ + SaaS 主要プレイヤー。AI 計算需要の波及で再評価。",
        "tickers": ["MSFT", "AMZN", "GOOGL", "ORCL", "CRM", "NOW", "SNOW", "DDOG", "NET"],
        "leaders": ["MSFT", "AMZN", "GOOGL"],
    },
    "EV・自動車": {
        "description": "完成車・EV ピュア・サプライヤー。中国メーカー躍進と関税が論点。",
        "tickers": ["TSLA", "7203.T", "7267.T", "F", "GM", "STLA", "RIVN", "LCID", "7201.T", "BYDDY"],
        "leaders": ["TSLA", "7203.T"],
    },
    "防衛": {
        "description": "地政学リスク高まりで再評価。米欧の予算動向に連動。",
        "tickers": ["LMT", "RTX", "NOC", "GD", "BA", "LDOS", "HII", "7011.T"],
        "leaders": ["LMT", "RTX"],
    },
    "ヘルスケア": {
        "description": "ファーマ大手 + バイオ + 医療機器。GLP-1 と米選挙年が論点。",
        "tickers": ["JNJ", "LLY", "PFE", "MRK", "UNH", "ABBV", "AMGN", "TMO", "4502.T", "4503.T"],
        "leaders": ["LLY", "JNJ", "UNH"],
    },
    "金融(銀行)": {
        "description": "金利環境と景気サイクルに敏感。日米とも利上げ・利下げで再評価される。",
        "tickers": ["JPM", "BAC", "GS", "MS", "C", "WFC", "8306.T", "8316.T", "8411.T"],
        "leaders": ["JPM", "8306.T"],
    },
    "高配当・ディフェンシブ": {
        "description": "景気後退耐性 + インカム狙い。金利低下局面で評価される。",
        "tickers": ["KO", "PEP", "PG", "JNJ", "VZ", "T", "MO", "PM", "XOM", "CVX"],
        "leaders": ["KO", "PG", "JNJ"],
    },
    "日本主力大型": {
        "description": "TOPIX Core30 級の日本大型株。円安耐性と海外売上比率がポイント。",
        "tickers": ["7203.T", "6758.T", "9984.T", "8306.T", "6098.T", "9432.T", "8035.T", "4063.T", "6501.T", "6902.T"],
        "leaders": ["7203.T", "6758.T", "8035.T"],
    },
    "暗号通貨関連": {
        "description": "BTC 価格・規制動向に連動。ボラティリティ高、ポジションサイズ注意。",
        "tickers": ["COIN", "MSTR", "MARA", "RIOT", "HOOD"],
        "leaders": ["COIN", "MSTR"],
    },
}


# ───────── マクロ・メタトレンド指数 ─────────
INDICES: dict[str, dict] = {
    "S&P 500": {"ticker": "^GSPC", "category": "米株指数", "comment": "米国大型株 500 銘柄。市場全体の体温計。"},
    "NASDAQ": {"ticker": "^IXIC", "category": "米株指数", "comment": "テック寄り、AI 期待を反映しやすい。"},
    "Dow 30": {"ticker": "^DJI", "category": "米株指数", "comment": "古参 30 銘柄、伝統セクター比率高め。"},
    "日経 225": {"ticker": "^N225", "category": "日本株指数", "comment": "日本主力 225 銘柄。為替と海外景気に連動。"},
    "TOPIX": {"ticker": "^TOPX", "category": "日本株指数", "comment": "東証プライム全体。バリュー寄り。"},
    "VIX(恐怖指数)": {"ticker": "^VIX", "category": "ボラティリティ", "comment": "20 を超えると緊張、30 超えで警戒。"},
    "米 10 年金利": {"ticker": "^TNX", "category": "金利", "comment": "高 PER 銘柄に逆風(分母の割引率)。"},
    "ドル円": {"ticker": "JPY=X", "category": "為替", "comment": "円安 = 日本輸出企業の採算改善。"},
    "ユーロドル": {"ticker": "EURUSD=X", "category": "為替", "comment": "欧州景気 + 米利下げ観測。"},
    "原油 WTI": {"ticker": "CL=F", "category": "コモディティ", "comment": "エネルギー / インフレ / 中東情勢の指標。"},
    "金": {"ticker": "GC=F", "category": "コモディティ", "comment": "リスク回避 + 実質金利低下時に上昇。"},
    "ビットコイン": {"ticker": "BTC-USD", "category": "暗号通貨", "comment": "リスク資産 + ハイテクに連動傾向。"},
}


# ───────── セクター ETF(米国)─────────
SECTOR_ETFS: dict[str, dict] = {
    "Tech (XLK)": {"ticker": "XLK", "comment": "情報技術セクター。AI / 半導体寄与"},
    "Communications (XLC)": {"ticker": "XLC", "comment": "通信・メディア。GOOGL/META 比率高"},
    "Cons. Discr. (XLY)": {"ticker": "XLY", "comment": "一般消費。AMZN/TSLA 寄与"},
    "Cons. Staples (XLP)": {"ticker": "XLP", "comment": "生活必需品。ディフェンシブ"},
    "Financials (XLF)": {"ticker": "XLF", "comment": "金融。金利との連動"},
    "Healthcare (XLV)": {"ticker": "XLV", "comment": "ヘルスケア。GLP-1 で攪拌"},
    "Industrials (XLI)": {"ticker": "XLI", "comment": "資本財。景気循環"},
    "Energy (XLE)": {"ticker": "XLE", "comment": "エネルギー。原油連動"},
    "Materials (XLB)": {"ticker": "XLB", "comment": "素材。中国景気で攪拌"},
    "Utilities (XLU)": {"ticker": "XLU", "comment": "公益。金利低下で評価"},
    "Real Estate (XLRE)": {"ticker": "XLRE", "comment": "不動産。金利逆風"},
}
