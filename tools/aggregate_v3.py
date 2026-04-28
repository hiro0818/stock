"""
aggregate_v3.py — v3 walk-forward 結果を集計して、Markdown レポート用テーブルを生成する。

実行:
  python tools/aggregate_v3.py

出力:
  outputs/v3_summary_table.md(コンソール + ファイル)
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / "outputs" / "walk_forward"
OUT = ROOT / "outputs" / "v3_summary_table.md"

STOCKS = ["AAPL", "NVDA", "MSFT", "7203_T", "6758_T", "XOM", "CVX", "NEM", "COIN", "MSTR"]
MODELS = ["linear", "mean_reversion", "technical", "monte_carlo", "macro_linked", "lightgbm_ml", "crypto_linked", "ensemble"]


def load_data() -> dict:
    data = {}
    for s in STOCKS:
        files = sorted(WF.glob(f"{s}_*.json"), reverse=True)
        if files:
            try:
                data[s] = json.loads(files[0].read_text(encoding="utf-8"))
            except Exception:
                pass
    return data


def render_markdown(data: dict) -> str:
    lines = []
    lines.append("# v3 walk-forward 集計表")
    lines.append("")
    lines.append("## 1. 銘柄別 ensemble 精度")
    lines.append("")
    lines.append("| 銘柄 | サンプル | 平均絶対誤差 | 方向当たり率 | バイアス |")
    lines.append("|---|---|---|---|---|")
    for s in STOCKS:
        if s not in data:
            continue
        e = data[s].get("stats_by_model", {}).get("ensemble", {})
        lines.append(
            f"| {s} | {e.get('samples', '-')} | {e.get('avg_abs_error_pct', '-')}% | "
            f"{e.get('direction_hit_rate', '-')}% | {e.get('bias_pct', '-'):+.2f}% |"
        )
    lines.append("")

    lines.append("## 2. モデル別 全銘柄横断の平均絶対誤差")
    lines.append("")
    lines.append("| モデル | " + " | ".join(STOCKS) + " | 平均 |")
    lines.append("|---" * (len(STOCKS) + 2) + "|")
    for m in MODELS:
        row = [m]
        avgs = []
        for s in STOCKS:
            if s not in data:
                row.append("-")
                continue
            v = data[s].get("stats_by_model", {}).get(m, {}).get("avg_abs_error_pct")
            if v is not None:
                row.append(f"{v}%")
                avgs.append(v)
            else:
                row.append("-")
        row.append(f"{sum(avgs) / len(avgs):.2f}%" if avgs else "-")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## 3. モデル別 全銘柄横断の方向当たり率")
    lines.append("")
    lines.append("| モデル | " + " | ".join(STOCKS) + " | 平均 |")
    lines.append("|---" * (len(STOCKS) + 2) + "|")
    for m in MODELS:
        row = [m]
        avgs = []
        for s in STOCKS:
            if s not in data:
                row.append("-")
                continue
            v = data[s].get("stats_by_model", {}).get(m, {}).get("direction_hit_rate")
            if v is not None:
                row.append(f"{v}%")
                avgs.append(v)
            else:
                row.append("-")
        row.append(f"{sum(avgs) / len(avgs):.1f}%" if avgs else "-")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return "\n".join(lines)


def main():
    data = load_data()
    md = render_markdown(data)
    OUT.write_text(md, encoding="utf-8")
    print(md)
    print()
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
