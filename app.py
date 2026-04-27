"""
app.py — 銘柄選びアシスタント Streamlit ダッシュボード

設計方針:
  - 事前にデータを取得しない(ユーザー入力起点)
  - 入力されたら、その銘柄を中心に多角的に分析(総合スコア / テクニカル / ファンダ /
    競合 / テーマ / マクロ環境)
  - すべて日本語表記
  - キャッシュ TTL = 1 時間(yfinance データ遅延 1 時間以内に維持)

⚠️ 投資助言ではありません。判断材料の整理用です。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_stock import get_history, get_summary, get_technical  # noqa: E402
from find_competitors import find_peers  # noqa: E402
from macro_context import relevant_macros_for  # noqa: E402
from scoring import find_themes_for_ticker, total_score  # noqa: E402
from themes import THEMES  # noqa: E402

# ───────── ページ設定 ─────────
st.set_page_config(
    page_title="銘柄選びアシスタント",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_TTL = 3600  # 1 時間


# ───────── キャッシュ付き取得関数 ─────────
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _summary(t: str) -> dict:
    return get_summary(t)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _technical(t: str) -> dict:
    return get_technical(t)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _history(t: str, period: str) -> list:
    return get_history(t, period)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _peers(t: str, limit: int = 5) -> dict:
    return find_peers(t, limit)


# ───────── ヘルパー ─────────
def fmt_num(v, digits: int = 2) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "—"
    if isinstance(v, (int, float)):
        if abs(v) >= 1e12:
            return f"{v / 1e12:.{digits}f} 兆"
        if abs(v) >= 1e8:
            return f"{v / 1e8:.{digits}f} 億"
        if abs(v) >= 1e4:
            return f"{v / 1e4:.{digits}f} 万"
        return f"{v:,.{digits}f}"
    return str(v)


def fmt_pct(v, mult_100: bool = False) -> str:
    if v is None:
        return "—"
    if mult_100:
        return f"{v:.2f}%"
    return f"{v * 100:.2f}%"


# ───────── サイドバー ─────────
st.sidebar.title("📈 銘柄選び")
st.sidebar.caption("yfinance ベース・自分用ツール")

st.sidebar.markdown("##### 銘柄ティッカーを入力")
ticker_input = st.sidebar.text_input(
    "例:AAPL / NVDA / 7203.T / 6758.T",
    value="",
    placeholder="ティッカーを入れてね",
    key="ticker_input",
)
period = st.sidebar.selectbox(
    "チャート期間",
    options=["3mo", "6mo", "1y", "2y", "5y"],
    index=2,
    format_func=lambda x: {
        "3mo": "3 か月",
        "6mo": "6 か月",
        "1y": "1 年",
        "2y": "2 年",
        "5y": "5 年",
    }[x],
)

run = st.sidebar.button("🔍 分析開始", type="primary", use_container_width=True)

# クイック入力ボタン
st.sidebar.markdown("##### よく見る銘柄")
quick_cols = st.sidebar.columns(3)
for i, (label, t) in enumerate(
    [("AAPL", "AAPL"), ("NVDA", "NVDA"), ("MSFT", "MSFT"),
     ("7203", "7203.T"), ("6758", "6758.T"), ("9984", "9984.T")]
):
    if quick_cols[i % 3].button(label, key=f"quick_{t}", use_container_width=True):
        st.session_state["ticker_input"] = t
        st.session_state["_run"] = True
        st.rerun()

# 履歴
if "history_tickers" not in st.session_state:
    st.session_state["history_tickers"] = []

if st.session_state["history_tickers"]:
    st.sidebar.markdown("##### 過去に調べた銘柄")
    for prev in st.session_state["history_tickers"][-10:][::-1]:
        if st.sidebar.button(f"↺ {prev}", key=f"hist_{prev}", use_container_width=True):
            st.session_state["ticker_input"] = prev
            st.session_state["_run"] = True
            st.rerun()

st.sidebar.divider()
st.sidebar.markdown(
    "##### ⚠️ 免責\n"
    "このツールは投資助言ではありません。判断材料の整理のみを行い、"
    "最終的な投資判断と責任はユーザー自身にあります。\n\n"
    "yfinance データは取得時点で最大 1 時間遅延の可能性があります。"
)

# クイックボタンからのトリガを拾う
if st.session_state.get("_run"):
    run = True
    st.session_state["_run"] = False

ticker = (st.session_state.get("ticker_input") or ticker_input).strip().upper()


# ───────── ホーム画面(銘柄未入力)─────────
if not ticker or not run:
    st.title("📈 銘柄選びアシスタント")
    st.caption("yfinance ベース・自分用ツール  ·  ⚠️ 投資助言ではありません")

    st.markdown(
        """
        ### 使い方
        左サイドバーに **ティッカー** を入力して **「分析開始」** を押してください。
        その銘柄を起点に、以下を **多角的にレポート** します:

        | 観点 | 内容 |
        |---|---|
        | 🎯 総合評価 | 5 観点(バリュエーション / 収益性 / 成長性 / 財務 / テクニカル)を 0-100 でスコア化 → 強気・中立・弱気の判定 |
        | 💰 ファンダメンタル | 主要な財務指標と、その水準の解釈コメント |
        | 📈 テクニカル | ローソク足 + MA20/50/200 + RSI(14)+ MACD + 出来高、シグナル自動検出 |
        | 🏢 競合比較 | 同業他社を自動列挙して横並び比較 |
        | 🌐 関連テーマ | この銘柄が属するメタトレンド(AI / 半導体 / EV など)と、その他の銘柄 |
        | 🌍 マクロ環境 | この銘柄に関係する指標(米金利 / VIX / ドル円 / 業界 ETF)を厳選表示 |

        ### ティッカーの書き方
        - **米国株**: `AAPL`, `MSFT`, `NVDA`, `GOOGL`, `META`
        - **日本株**: `7203.T`(トヨタ), `6758.T`(ソニー G), `9984.T`(SBG)、証券コード末尾に `.T`

        ### よく見る銘柄
        サイドバーのクイックボタンから 1 クリックで分析できます。
        """
    )
    st.stop()


# ───────── データ取得(指定銘柄)─────────
if ticker not in st.session_state["history_tickers"]:
    st.session_state["history_tickers"].append(ticker)

with st.spinner(f"{ticker} のデータを取得中..."):
    try:
        summary = _summary(ticker)
        technical = _technical(ticker)
    except Exception as e:
        st.error(f"yfinance からの取得に失敗しました: {e}")
        st.stop()

if summary.get("name") is None:
    st.error(
        f"ティッカー `{ticker}` が見つかりません。日本株は `XXXX.T` 形式で入力してください(例: 7203.T)。"
    )
    st.stop()

# ───────── ヒーロー(銘柄ヘッダー)─────────
st.title(f"📈 {summary.get('name')}  ·  `{ticker}`")
col_meta1, col_meta2, col_meta3 = st.columns([2, 2, 3])
col_meta1.markdown(f"**セクター**: {summary.get('sector') or '—'}")
col_meta2.markdown(f"**業界**: {summary.get('industry') or '—'}")
col_meta3.caption(f"取得日時: {summary.get('fetched_at', '')[:19]}  ·  yfinance(遅延あり)")

# 総合スコア
score = total_score(summary, technical)

st.divider()
hero_col1, hero_col2 = st.columns([1, 2])
with hero_col1:
    # 大きな判定バッジ
    st.metric("総合判定", score["判定"], help="5 観点の平均スコアから自動判定")
    st.metric("総合スコア", f"{score['総合スコア']} / 100")

with hero_col2:
    # 観点別スコアを横棒で
    axes = score["観点別"]
    df_axes = pd.DataFrame(
        [{"観点": k, "スコア": v["score"]} for k, v in axes.items()]
    )
    bar = go.Figure(
        go.Bar(
            x=df_axes["スコア"],
            y=df_axes["観点"],
            orientation="h",
            marker_color=df_axes["スコア"].apply(
                lambda s: "#26a69a" if s >= 65 else ("#ffb74d" if s >= 45 else "#ef5350")
            ),
            text=df_axes["スコア"],
            textposition="outside",
        )
    )
    bar.update_layout(
        height=240,
        margin=dict(l=10, r=30, t=10, b=10),
        xaxis=dict(range=[0, 100], title=""),
        yaxis=dict(title=""),
        template="plotly_white",
    )
    st.plotly_chart(bar, use_container_width=True)

# 強み / 弱み
strength_col, weakness_col = st.columns(2)
with strength_col:
    st.markdown("##### ✅ 強みの論点")
    if score["強み"]:
        for s in score["強み"]:
            st.markdown(f"- {s}")
    else:
        st.caption("際立った強みは検出されませんでした。")
with weakness_col:
    st.markdown("##### ⚠️ 警戒の論点")
    if score["弱み"]:
        for w in score["弱み"]:
            st.markdown(f"- {w}")
    else:
        st.caption("際立った弱みは検出されませんでした。")

st.caption(score["免責"])
st.divider()


# ───────── タブ構成 ─────────
tab_fund, tab_tech, tab_peer, tab_theme, tab_macro, tab_raw = st.tabs(
    [
        "💰 ファンダメンタル",
        "📈 テクニカル",
        "🏢 競合比較",
        "🌐 関連テーマ",
        "🌍 マクロ環境",
        "🔍 生データ",
    ]
)


# ───── ファンダメンタル ─────
with tab_fund:
    st.markdown("##### 主要指標")
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    f_col1.metric("株価", fmt_num(summary.get("current_price"), 2))
    f_col2.metric("時価総額", fmt_num(summary.get("market_cap"), 2))
    f_col3.metric("Trailing PER", fmt_num(summary.get("trailing_pe"), 1))
    f_col4.metric("Forward PER", fmt_num(summary.get("forward_pe"), 1))

    f_col5, f_col6, f_col7, f_col8 = st.columns(4)
    f_col5.metric("PBR", fmt_num(summary.get("price_to_book"), 2))
    f_col6.metric("ROE", fmt_pct(summary.get("return_on_equity")))
    f_col7.metric("営業利益率", fmt_pct(summary.get("operating_margins")))
    f_col8.metric(
        "配当利回り",
        fmt_pct(summary.get("dividend_yield"), mult_100=True) if summary.get("dividend_yield") else "—",
    )

    f_col9, f_col10, f_col11, f_col12 = st.columns(4)
    f_col9.metric("売上成長率", fmt_pct(summary.get("revenue_growth")))
    f_col10.metric("EPS成長率", fmt_pct(summary.get("earnings_growth")))
    f_col11.metric("D/E 比率", fmt_num(summary.get("debt_to_equity"), 1))
    f_col12.metric("流動比率", fmt_num(summary.get("current_ratio"), 2))

    st.divider()

    # 観点別の解釈コメント
    st.markdown("##### 観点別の解釈")
    for axis, info in score["観点別"].items():
        if axis == "テクニカル":
            continue  # ファンダ画面ではスキップ(別タブ)
        score_val = info["score"]
        color = "#26a69a" if score_val >= 65 else ("#ffb74d" if score_val >= 45 else "#ef5350")
        st.markdown(
            f"<div style='border-left:4px solid {color}; padding:8px 12px; margin:4px 0; background:#fafafa;'>"
            f"<b>{axis}</b>(スコア {score_val}/100): {info['note']}"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    if summary.get("long_business_summary"):
        with st.expander("📄 事業概要(yfinance、英語)"):
            st.write(summary["long_business_summary"])


# ───── テクニカル ─────
with tab_tech:
    with st.spinner("株価履歴を取得中..."):
        history = _history(ticker, period)
    if not history:
        st.warning("株価履歴が取得できませんでした")
    else:
        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"])
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma50"] = df["close"].rolling(50).mean()
        df["ma200"] = df["close"].rolling(200).mean()

        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))

        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["signal"]

        # チャート(3 段)
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.55, 0.2, 0.25],
            subplot_titles=("ローソク足 + 移動平均", "RSI(14)", "MACD"),
        )
        fig.add_trace(
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="ローソク",
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
            ),
            row=1,
            col=1,
        )
        for col, color, name in [
            ("ma20", "#ffa726", "MA 20"),
            ("ma50", "#42a5f5", "MA 50"),
            ("ma200", "#ab47bc", "MA 200"),
        ]:
            fig.add_trace(
                go.Scatter(x=df["date"], y=df[col], mode="lines", name=name, line=dict(color=color, width=1.5)),
                row=1,
                col=1,
            )
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["rsi"], mode="lines", name="RSI", line=dict(color="#7e57c2")),
            row=2,
            col=1,
        )
        fig.add_hline(y=70, line=dict(color="red", dash="dash"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="green", dash="dash"), row=2, col=1)
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["macd"], mode="lines", name="MACD", line=dict(color="#26a69a")),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["signal"], mode="lines", name="シグナル", line=dict(color="#ef5350")),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["macd_hist"],
                name="ヒストグラム",
                marker_color=df["macd_hist"].apply(lambda v: "#26a69a" if v > 0 else "#ef5350"),
                opacity=0.5,
            ),
            row=3,
            col=1,
        )
        fig.update_layout(
            height=750,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=40, b=10),
            template="plotly_white",
        )
        fig.update_yaxes(title_text="価格", row=1, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
        fig.update_yaxes(title_text="MACD", row=3, col=1)
        st.plotly_chart(fig, use_container_width=True)

        # 解釈コメント
        st.markdown("##### テクニカルの解釈")
        tech_score = score["観点別"]["テクニカル"]
        color = "#26a69a" if tech_score["score"] >= 65 else ("#ffb74d" if tech_score["score"] >= 45 else "#ef5350")
        st.markdown(
            f"<div style='border-left:4px solid {color}; padding:8px 12px; margin:4px 0; background:#fafafa;'>"
            f"<b>テクニカル スコア {tech_score['score']}/100</b>: {tech_score['note']}"
            f"</div>",
            unsafe_allow_html=True,
        )

        # シグナル
        if technical.get("signals"):
            for sig in technical["signals"]:
                st.warning(f"📢 {sig}")

        # 主要数値
        st.markdown("##### 直近の値")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("終値", fmt_num(technical.get("last_close"), 2))
        c2.metric("RSI(14)", fmt_num(technical.get("rsi14"), 1))
        c3.metric("52週レンジ位置", technical.get("range_position_label") or "—")
        c4.metric("MACD", technical.get("macd_status") or "—")


# ───── 競合比較 ─────
with tab_peer:
    with st.spinner("同業他社を取得中..."):
        peers_data = _peers(ticker, 5)
    competitors = peers_data.get("competitors", [])
    if not competitors:
        st.info(
            f"業界 `{peers_data.get('industry')}` は内蔵マップ未登録のため、競合自動列挙はスキップしました。"
            f" `tools/find_competitors.py` の `INDUSTRY_PEERS` に追加できます。"
        )
    else:
        st.markdown(f"**業界**:{peers_data.get('industry')}  ·  **同業他社**:{len(competitors)} 社")
        rows = []
        with st.spinner(f"{len(competitors) + 1} 銘柄の指標を取得中..."):
            for t in [ticker] + competitors:
                try:
                    s = _summary(t)
                    rows.append(
                        {
                            "ティッカー": t,
                            "名称": (s.get("name") or "—")[:35],
                            "株価": s.get("current_price"),
                            "時価総額": s.get("market_cap"),
                            "PER": s.get("trailing_pe"),
                            "ROE(%)": (s.get("return_on_equity") or 0) * 100 if s.get("return_on_equity") else None,
                            "営業利益率(%)": (s.get("operating_margins") or 0) * 100 if s.get("operating_margins") else None,
                            "売上成長率(%)": (s.get("revenue_growth") or 0) * 100 if s.get("revenue_growth") else None,
                            "配当利回り(%)": s.get("dividend_yield"),
                        }
                    )
                except Exception as e:
                    rows.append({"ティッカー": t, "名称": f"取得失敗: {e}"})

        df_peers = pd.DataFrame(rows)
        # 自社行をハイライトするためインデックス取得
        st.dataframe(
            df_peers,
            use_container_width=True,
            hide_index=True,
            column_config={
                "株価": st.column_config.NumberColumn(format="%.2f"),
                "時価総額": st.column_config.NumberColumn(format="%.2e"),
                "PER": st.column_config.NumberColumn(format="%.1f"),
                "ROE(%)": st.column_config.NumberColumn(format="%.1f"),
                "営業利益率(%)": st.column_config.NumberColumn(format="%.1f"),
                "売上成長率(%)": st.column_config.NumberColumn(format="%.1f"),
                "配当利回り(%)": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        st.caption(f"先頭行が分析対象銘柄(`{ticker}`)、続く行が自動列挙された同業他社です。")


# ───── 関連テーマ ─────
with tab_theme:
    themes_in = find_themes_for_ticker(ticker, THEMES)
    if not themes_in:
        st.info(f"`{ticker}` は内蔵テーマバスケットに含まれていません。`tools/themes.py` の `THEMES` に追加できます。")
    else:
        st.markdown(f"**`{ticker}` が属するテーマ**:{', '.join(themes_in)}")
        st.divider()

        for theme_name in themes_in:
            theme_info = THEMES[theme_name]
            st.markdown(f"### 🏷️ {theme_name}")
            st.caption(theme_info["description"])

            # 同テーマ銘柄の主要指標を取得して比較表に
            with st.spinner(f"{theme_name} の銘柄を取得中..."):
                theme_rows = []
                for t in theme_info["tickers"][:8]:  # 最大 8 銘柄まで(速度配慮)
                    try:
                        s = _summary(t)
                        theme_rows.append(
                            {
                                "ティッカー": t,
                                "名称": (s.get("name") or "—")[:30],
                                "株価": s.get("current_price"),
                                "時価総額": s.get("market_cap"),
                                "PER": s.get("trailing_pe"),
                                "売上成長率(%)": (s.get("revenue_growth") or 0) * 100
                                if s.get("revenue_growth")
                                else None,
                                "リーダー": "★" if t in theme_info.get("leaders", []) else "",
                            }
                        )
                    except Exception:
                        pass
            if theme_rows:
                df_th = pd.DataFrame(theme_rows)
                st.dataframe(
                    df_th,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "株価": st.column_config.NumberColumn(format="%.2f"),
                        "時価総額": st.column_config.NumberColumn(format="%.2e"),
                        "PER": st.column_config.NumberColumn(format="%.1f"),
                        "売上成長率(%)": st.column_config.NumberColumn(format="%.1f"),
                    },
                )
            st.divider()


# ───── マクロ環境 ─────
with tab_macro:
    st.markdown("##### この銘柄に関係が深いマクロ指標")
    st.caption("銘柄のセクター・所属テーマ・PER 水準から、影響度の高いものを自動選別します。")

    themes_in = find_themes_for_ticker(ticker, THEMES)
    macros = relevant_macros_for(ticker, summary, themes_in)

    rows = []
    with st.spinner("関連マクロ指標を取得中..."):
        for m in macros:
            try:
                s = _summary(m["ticker"])
                t = _technical(m["ticker"])
                rows.append(
                    {
                        "指標": m["label"],
                        "現在値": s.get("current_price") or t.get("last_close"),
                        "トレンド": t.get("trend") or "—",
                        "RSI(14)": t.get("rsi14"),
                        "なぜ関係するか": m["reason"],
                    }
                )
            except Exception:
                rows.append({"指標": m["label"], "現在値": "取得失敗", "なぜ関係するか": m["reason"]})

    if rows:
        df_macro = pd.DataFrame(rows)
        st.dataframe(
            df_macro,
            use_container_width=True,
            hide_index=True,
            column_config={
                "現在値": st.column_config.NumberColumn(format="%.2f"),
                "RSI(14)": st.column_config.NumberColumn(format="%.1f"),
            },
        )
    st.info(
        f"💡 上記は `{ticker}` に強く関連するものを厳選しています。すべてのマクロ指標を見るには、"
        "`tools/themes.py` の `INDICES` を直接参照してください。"
    )


# ───── 生データ ─────
with tab_raw:
    st.markdown("##### yfinance の生レスポンス(デバッグ・裏取り用)")
    with st.expander("📦 サマリ"):
        st.json(summary)
    with st.expander("📈 テクニカル"):
        st.json(technical)
    with st.expander("🎯 スコア計算"):
        st.json(score)
