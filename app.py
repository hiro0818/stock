"""
app.py — Streamlit Web ダッシュボード(銘柄選びアシスタント UI)

起動:
  streamlit run app.py

起動後、ブラウザが自動で開いて http://localhost:8501 に接続される。
左サイドバーでティッカーを入力 → タブで「概要」「チャート」「競合比較」「Watchlist」「日次ログ」を切り替え。

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# tools/ を import path に追加
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_stock import get_summary, get_history, get_technical  # noqa: E402
from find_competitors import find_peers  # noqa: E402

st.set_page_config(
    page_title="銘柄選びアシスタント",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────── サイドバー ─────────
st.sidebar.title("📈 銘柄選び")
st.sidebar.caption("yfinance ベース・自分用ツール")

ticker_input = st.sidebar.text_input(
    "ティッカー",
    value="AAPL",
    help="米国株: AAPL / MSFT / NVDA … 日本株: 7203.T / 6758.T / 9984.T …",
)
ticker = ticker_input.strip().upper()

period = st.sidebar.selectbox(
    "チャート期間",
    options=["3mo", "6mo", "1y", "2y", "5y", "max"],
    index=2,
)

run_button = st.sidebar.button("📊 分析する", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.markdown(
    "##### ⚠️ 免責\n"
    "本ツールは投資助言ではありません。判断材料の整理のみを行い、"
    "最終的な投資判断と責任はユーザー自身にあります。"
    "yfinance のデータには通常 15 分以上の遅延があります。"
)


# ───────── ヘルパー ─────────
@st.cache_data(ttl=300)
def cached_summary(t: str) -> dict:
    return get_summary(t)


@st.cache_data(ttl=300)
def cached_technical(t: str) -> dict:
    return get_technical(t)


@st.cache_data(ttl=600)
def cached_history(t: str, period: str) -> list:
    return get_history(t, period)


@st.cache_data(ttl=600)
def cached_peers(t: str, limit: int = 5) -> dict:
    return find_peers(t, limit)


def fmt_num(v, digits: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        if abs(v) >= 1_000_000_000_000:
            return f"{v / 1e12:.{digits}f}T"
        if abs(v) >= 1_000_000_000:
            return f"{v / 1e9:.{digits}f}B"
        if abs(v) >= 1_000_000:
            return f"{v / 1e6:.{digits}f}M"
        return f"{v:,.{digits}f}"
    return str(v)


def fmt_pct(v) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.2f}%" if abs(v) < 5 else f"{v:.2f}%"


# ───────── メイン ─────────
if not ticker:
    st.info("左サイドバーでティッカーを入力して「分析する」を押してください。")
    st.stop()

st.title(f"📈 {ticker}")

# データ取得
with st.spinner(f"{ticker} のデータを yfinance から取得中..."):
    try:
        summary = cached_summary(ticker)
        technical = cached_technical(ticker)
    except Exception as e:
        st.error(f"データ取得に失敗: {e}")
        st.stop()

if summary.get("name") is None:
    st.warning(
        "ティッカーが見つかりません。yfinance に登録がない可能性があります。"
        "日本株は `XXXX.T` 形式で入力してください(例: 7203.T)。"
    )
    st.stop()

st.subheader(f"{summary.get('name')}  ·  {summary.get('sector')} / {summary.get('industry')}")
st.caption(f"取得日時: {summary.get('fetched_at')}  ·  yfinance(15 分以上の遅延あり)")

# ── タブ ──
tab_overview, tab_chart, tab_competitors, tab_watchlist, tab_daily = st.tabs(
    ["概要", "チャート", "競合比較", "Watchlist", "日次ログ"]
)

# ───── 概要タブ ─────
with tab_overview:
    col1, col2, col3, col4 = st.columns(4)

    price = summary.get("current_price")
    week_high = summary.get("fifty_two_week_high")
    week_low = summary.get("fifty_two_week_low")
    range_pos = technical.get("range_position")

    col1.metric(
        "株価",
        fmt_num(price),
        delta=f"{technical.get('range_position_label', '')}"
        if technical.get("range_position_label")
        else None,
    )
    col2.metric("時価総額", fmt_num(summary.get("market_cap")))
    col3.metric("Trailing PER", fmt_num(summary.get("trailing_pe"), 1))
    col4.metric("Forward PER", fmt_num(summary.get("forward_pe"), 1))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("ROE", fmt_pct(summary.get("return_on_equity")))
    col6.metric("営業利益率", fmt_pct(summary.get("operating_margins")))
    col7.metric("売上成長率", fmt_pct(summary.get("revenue_growth")))
    col8.metric("配当利回り", fmt_pct((summary.get("dividend_yield") or 0) / 100) if summary.get("dividend_yield") else "—")

    st.divider()

    # シグナル(警告ボックス)
    if technical.get("signals"):
        st.warning("**シグナル**: " + "  /  ".join(technical["signals"]))
    else:
        st.info("**シグナル**: 特記事項なし")

    # トレンド
    st.markdown(f"**トレンド判定**:{technical.get('trend')}  ·  **MACD**: {technical.get('macd_status')}")

    with st.expander("🔍 全指標(yfinance 生データ)"):
        st.json(summary)
    with st.expander("🔍 技術指標(算出値)"):
        st.json(technical)

    st.divider()
    if summary.get("long_business_summary"):
        st.markdown("##### 事業概要(yfinance)")
        st.write(summary["long_business_summary"])


# ───── チャートタブ ─────
with tab_chart:
    with st.spinner("株価履歴を取得中..."):
        history = cached_history(ticker, period)

    if not history:
        st.warning("株価履歴データがありません")
    else:
        df = pd.DataFrame(history)
        df["date"] = pd.to_datetime(df["date"])
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma50"] = df["close"].rolling(50).mean()
        df["ma200"] = df["close"].rolling(200).mean()

        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0.0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # 3 段構成のチャート
        fig = make_subplots(
            rows=3,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.55, 0.2, 0.25],
            subplot_titles=("株価 + 移動平均", "RSI(14)", "MACD"),
        )

        # ローソク足
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
        # 移動平均
        for col, color, name in [
            ("ma20", "#ffa726", "MA20"),
            ("ma50", "#42a5f5", "MA50"),
            ("ma200", "#ab47bc", "MA200"),
        ]:
            fig.add_trace(
                go.Scatter(
                    x=df["date"],
                    y=df[col],
                    mode="lines",
                    name=name,
                    line=dict(color=color, width=1.5),
                ),
                row=1,
                col=1,
            )

        # RSI
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["rsi"], mode="lines", name="RSI", line=dict(color="#7e57c2")),
            row=2,
            col=1,
        )
        fig.add_hline(y=70, line=dict(color="red", dash="dash"), row=2, col=1)
        fig.add_hline(y=30, line=dict(color="green", dash="dash"), row=2, col=1)

        # MACD
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["macd"], mode="lines", name="MACD", line=dict(color="#26a69a")),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["macd_signal"], mode="lines", name="Signal", line=dict(color="#ef5350")),
            row=3,
            col=1,
        )
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["macd_hist"],
                name="Hist",
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

        # 出来高(独立)
        st.subheader("出来高")
        vol_fig = go.Figure()
        vol_fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["volume"],
                marker_color="#90a4ae",
                name="出来高",
            )
        )
        vol_fig.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), template="plotly_white")
        st.plotly_chart(vol_fig, use_container_width=True)


# ───── 競合比較タブ ─────
with tab_competitors:
    with st.spinner("競合銘柄を取得中..."):
        peers_data = cached_peers(ticker, 5)

    competitors = peers_data.get("competitors", [])
    if not competitors:
        st.info(f"industry='{peers_data.get('industry')}' は業界マップ未登録です。`tools/find_competitors.py` の INDUSTRY_PEERS に追加してください。")
    else:
        st.write(f"**業界**: {peers_data.get('industry')}  ·  **同業他社**: {len(competitors)} 社")

        rows = []
        with st.spinner(f"{len(competitors) + 1} 銘柄の指標を取得中..."):
            for t in [ticker] + competitors:
                try:
                    s = cached_summary(t)
                    rows.append(
                        {
                            "ティッカー": t,
                            "名称": (s.get("name") or "—")[:35],
                            "株価": s.get("current_price"),
                            "時価総額": s.get("market_cap"),
                            "PER": s.get("trailing_pe"),
                            "ROE": s.get("return_on_equity"),
                            "営業利益率": s.get("operating_margins"),
                            "売上成長率": s.get("revenue_growth"),
                            "配当利回り(%)": s.get("dividend_yield"),
                        }
                    )
                except Exception as e:
                    rows.append({"ティッカー": t, "名称": f"取得失敗: {e}"})

        df_peers = pd.DataFrame(rows)
        st.dataframe(
            df_peers,
            use_container_width=True,
            hide_index=True,
            column_config={
                "株価": st.column_config.NumberColumn(format="%.2f"),
                "時価総額": st.column_config.NumberColumn(format="%.2e"),
                "PER": st.column_config.NumberColumn(format="%.1f"),
                "ROE": st.column_config.NumberColumn(format="%.2f"),
                "営業利益率": st.column_config.NumberColumn(format="%.2f"),
                "売上成長率": st.column_config.NumberColumn(format="%.2f"),
            },
        )


# ───── Watchlist タブ ─────
with tab_watchlist:
    watchlist_path = ROOT / "inputs" / "watchlist.md"
    st.write(f"📋 `{watchlist_path.relative_to(ROOT)}`")

    if not watchlist_path.exists():
        st.warning("watchlist.md が存在しません。")
    else:
        content = watchlist_path.read_text(encoding="utf-8")
        new_content = st.text_area(
            "Watchlist の編集",
            value=content,
            height=300,
            help="1行1ティッカー。`#` で始まる行はコメント。",
        )
        col_a, col_b = st.columns([1, 4])
        if col_a.button("💾 保存"):
            watchlist_path.write_text(new_content, encoding="utf-8")
            st.success("保存しました。次回の daily_check から反映されます。")

        st.divider()
        st.caption("daily_check.py を実行すると、ここに登録された全銘柄を一括取得できます。")
        if st.button("▶️ 今すぐ daily_check を実行"):
            import subprocess

            with st.spinner("daily_check 実行中..."):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / "daily_check.py")],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=300,
                )
                if result.returncode == 0:
                    st.success("実行完了")
                    st.code(result.stdout)
                else:
                    st.error(result.stderr or result.stdout)


# ───── 日次ログタブ ─────
with tab_daily:
    daily_dir = ROOT / "outputs" / "daily"
    if not daily_dir.exists():
        st.info("まだ日次ログがありません。Watchlist タブから daily_check を実行するか、コマンドで `python tools/daily_check.py` を回してください。")
    else:
        date_dirs = sorted([d for d in daily_dir.iterdir() if d.is_dir()], reverse=True)
        if not date_dirs:
            st.info("日次ログのディレクトリがありません。")
        else:
            selected = st.selectbox("日付を選択", [d.name for d in date_dirs])
            sel_dir = daily_dir / selected
            index_file = sel_dir / "_index.md"
            if index_file.exists():
                st.markdown(index_file.read_text(encoding="utf-8"))
            else:
                st.warning("_index.md が見つかりません。")

            st.divider()
            st.caption("各銘柄の生 JSON")
            json_files = sorted(sel_dir.glob("*.json"))
            for jf in json_files:
                with st.expander(jf.name):
                    try:
                        data = json.loads(jf.read_text(encoding="utf-8"))
                        st.json(data)
                    except Exception as e:
                        st.error(f"読み込みエラー: {e}")
