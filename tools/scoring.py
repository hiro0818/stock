"""
scoring.py — 銘柄の多角スコアリング

ユーザー入力された銘柄について、5 観点で 0-100 点に正規化し、総合スコアと
判定(強気 / 中立 / 弱気)を返す。すべて日本語コメント・日本語キー。

⚠️ スコアは判断材料の整理用であり、投資助言ではありません。
"""

from __future__ import annotations


def _safe(v):
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN
        return None
    return v


def score_valuation(summary: dict) -> tuple[int, str]:
    """バリュエーション(PER 中心)。低いほど高スコア。"""
    pe = _safe(summary.get("trailing_pe"))
    if pe is None or pe <= 0:
        return 50, "PER 取得不能(赤字 or データなし)、中立扱い"
    if pe < 10:
        return 90, f"PER {pe:.1f}: 歴史的に割安水準"
    if pe < 18:
        return 75, f"PER {pe:.1f}: 適正〜割安"
    if pe < 28:
        return 55, f"PER {pe:.1f}: 適正〜やや割高"
    if pe < 45:
        return 35, f"PER {pe:.1f}: 割高、成長見込みが必要"
    return 20, f"PER {pe:.1f}: 大幅割高、調整リスク"


def score_profitability(summary: dict) -> tuple[int, str]:
    """収益性(ROE + 営業利益率)。"""
    roe = _safe(summary.get("return_on_equity"))
    op = _safe(summary.get("operating_margins"))
    pts = []
    notes = []
    if roe is not None:
        if roe > 0.20:
            pts.append(90)
            notes.append(f"ROE {roe * 100:.1f}%(高水準)")
        elif roe > 0.10:
            pts.append(70)
            notes.append(f"ROE {roe * 100:.1f}%(良好)")
        elif roe > 0.05:
            pts.append(50)
            notes.append(f"ROE {roe * 100:.1f}%(普通)")
        elif roe > 0:
            pts.append(35)
            notes.append(f"ROE {roe * 100:.1f}%(低水準)")
        else:
            pts.append(15)
            notes.append(f"ROE {roe * 100:.1f}%(マイナス)")
    if op is not None:
        if op > 0.25:
            pts.append(85)
            notes.append(f"営業利益率 {op * 100:.1f}%(高い)")
        elif op > 0.15:
            pts.append(70)
            notes.append(f"営業利益率 {op * 100:.1f}%(良好)")
        elif op > 0.05:
            pts.append(50)
            notes.append(f"営業利益率 {op * 100:.1f}%(普通)")
        elif op > 0:
            pts.append(30)
            notes.append(f"営業利益率 {op * 100:.1f}%(薄利)")
        else:
            pts.append(15)
            notes.append(f"営業利益率 {op * 100:.1f}%(赤字)")
    if not pts:
        return 50, "収益性データなし、中立扱い"
    return int(sum(pts) / len(pts)), " / ".join(notes)


def score_growth(summary: dict) -> tuple[int, str]:
    """成長性(売上成長 + EPS成長)。"""
    rg = _safe(summary.get("revenue_growth"))
    eg = _safe(summary.get("earnings_growth"))
    pts = []
    notes = []
    for label, v in (("売上", rg), ("EPS", eg)):
        if v is None:
            continue
        if v > 0.25:
            pts.append(90)
            notes.append(f"{label}成長率 {v * 100:.1f}%(高成長)")
        elif v > 0.10:
            pts.append(70)
            notes.append(f"{label}成長率 {v * 100:.1f}%(良好)")
        elif v > 0.03:
            pts.append(50)
            notes.append(f"{label}成長率 {v * 100:.1f}%(緩やか)")
        elif v > 0:
            pts.append(35)
            notes.append(f"{label}成長率 {v * 100:.1f}%(微増)")
        else:
            pts.append(20)
            notes.append(f"{label}成長率 {v * 100:.1f}%(減収減益)")
    if not pts:
        return 50, "成長性データなし、中立扱い"
    return int(sum(pts) / len(pts)), " / ".join(notes)


def score_financial_health(summary: dict) -> tuple[int, str]:
    """財務健全性(D/E + 流動比率)。"""
    de = _safe(summary.get("debt_to_equity"))
    cr = _safe(summary.get("current_ratio"))
    pts = []
    notes = []
    if de is not None:
        # yfinance の debt_to_equity は通常 % 表示(102.63 なら 1.02 倍)
        de_ratio = de / 100 if de > 5 else de
        if de_ratio < 0.5:
            pts.append(85)
            notes.append(f"D/E {de_ratio:.2f}(低負債)")
        elif de_ratio < 1.0:
            pts.append(65)
            notes.append(f"D/E {de_ratio:.2f}(適正)")
        elif de_ratio < 2.0:
            pts.append(45)
            notes.append(f"D/E {de_ratio:.2f}(やや高負債)")
        else:
            pts.append(25)
            notes.append(f"D/E {de_ratio:.2f}(高負債、利上げ局面で逆風)")
    if cr is not None:
        if cr > 2.0:
            pts.append(80)
            notes.append(f"流動比率 {cr:.2f}(余裕)")
        elif cr > 1.0:
            pts.append(60)
            notes.append(f"流動比率 {cr:.2f}(健全)")
        elif cr > 0.7:
            pts.append(40)
            notes.append(f"流動比率 {cr:.2f}(注意)")
        else:
            pts.append(20)
            notes.append(f"流動比率 {cr:.2f}(短期支払い能力に懸念)")
    if not pts:
        return 50, "財務健全性データなし、中立扱い"
    return int(sum(pts) / len(pts)), " / ".join(notes)


def score_technical(technical: dict) -> tuple[int, str]:
    """テクニカル(MA配置、RSI、MACD、52週レンジ位置)。"""
    pts = []
    notes = []
    trend = technical.get("trend") or ""
    if "完全強気配列" in trend:
        pts.append(85)
        notes.append("MA 完全強気配列")
    elif "中期上昇" in trend:
        pts.append(65)
        notes.append("中期上昇トレンド")
    elif "もみ合い" in trend:
        pts.append(50)
        notes.append("もみ合い")
    elif "中期下降" in trend:
        pts.append(35)
        notes.append("中期下降トレンド")
    elif "完全弱気配列" in trend:
        pts.append(20)
        notes.append("MA 完全弱気配列")

    rsi = _safe(technical.get("rsi14"))
    if rsi is not None:
        if 40 <= rsi <= 60:
            pts.append(60)
            notes.append(f"RSI {rsi:.1f}(中立ゾーン)")
        elif 60 < rsi <= 70:
            pts.append(70)
            notes.append(f"RSI {rsi:.1f}(やや過熱だが上昇余地)")
        elif rsi > 70:
            pts.append(40)
            notes.append(f"RSI {rsi:.1f}(買われすぎ警戒)")
        elif 30 <= rsi < 40:
            pts.append(50)
            notes.append(f"RSI {rsi:.1f}(やや弱気)")
        elif rsi < 30:
            pts.append(70)
            notes.append(f"RSI {rsi:.1f}(売られすぎで反発候補)")

    macd_status = technical.get("macd_status") or ""
    if "強気" in macd_status:
        pts.append(70)
        notes.append("MACD 強気圏")
    elif "弱気" in macd_status:
        pts.append(40)
        notes.append("MACD 弱気圏")

    rp = _safe(technical.get("range_position"))
    if rp is not None:
        if rp > 0.85:
            pts.append(40)
            notes.append("52週レンジ上端付近(過熱の兆し)")
        elif rp < 0.15:
            pts.append(65)
            notes.append("52週レンジ下端付近(底値圏の可能性)")

    if not pts:
        return 50, "テクニカル指標取得不能、中立扱い"
    return int(sum(pts) / len(pts)), " / ".join(notes)


def total_score(summary: dict, technical: dict) -> dict:
    """5 観点のスコアと総合スコア + 判定を返す。"""
    s_val = score_valuation(summary)
    s_pro = score_profitability(summary)
    s_grw = score_growth(summary)
    s_fin = score_financial_health(summary)
    s_tec = score_technical(technical)

    by_axis = {
        "バリュエーション": {"score": s_val[0], "note": s_val[1]},
        "収益性": {"score": s_pro[0], "note": s_pro[1]},
        "成長性": {"score": s_grw[0], "note": s_grw[1]},
        "財務健全性": {"score": s_fin[0], "note": s_fin[1]},
        "テクニカル": {"score": s_tec[0], "note": s_tec[1]},
    }
    avg = int(sum(v["score"] for v in by_axis.values()) / len(by_axis))

    # 判定
    if avg >= 70:
        verdict = "🟢 強気(投資妙味あり)"
        verdict_short = "強気"
    elif avg >= 55:
        verdict = "🟡 やや強気"
        verdict_short = "やや強気"
    elif avg >= 45:
        verdict = "⚪ 中立"
        verdict_short = "中立"
    elif avg >= 30:
        verdict = "🟠 やや弱気"
        verdict_short = "やや弱気"
    else:
        verdict = "🔴 弱気(警戒)"
        verdict_short = "弱気"

    # 強み / 弱み
    sorted_axes = sorted(by_axis.items(), key=lambda kv: kv[1]["score"], reverse=True)
    strengths = [
        f"**{name}**(スコア {d['score']}): {d['note']}"
        for name, d in sorted_axes
        if d["score"] >= 65
    ][:3]
    weaknesses = [
        f"**{name}**(スコア {d['score']}): {d['note']}"
        for name, d in sorted_axes[::-1]
        if d["score"] <= 45
    ][:3]

    return {
        "総合スコア": avg,
        "判定": verdict,
        "判定_簡易": verdict_short,
        "観点別": by_axis,
        "強み": strengths,
        "弱み": weaknesses,
        "免責": "このスコアは情報整理用であり、投資推奨ではありません。",
    }


def find_themes_for_ticker(ticker: str, themes_dict: dict) -> list[str]:
    """指定ティッカーが属するテーマを themes_dict から検索。"""
    ticker_upper = ticker.upper()
    return [
        name
        for name, info in themes_dict.items()
        if ticker_upper in [t.upper() for t in info.get("tickers", [])]
    ]
