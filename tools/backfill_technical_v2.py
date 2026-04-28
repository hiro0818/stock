"""
backfill_technical_v2.py — 既存の walk_forward 結果に technical_v2 予測を後付けする

walk_forward.py を再実行せず、保存済みサンプルの prediction_date を使って
technical_v2 の予測値だけを追加する。これにより 10 銘柄を数分で更新可能。

実行:
  python tools/backfill_technical_v2.py

更新対象: outputs/walk_forward/<ticker>_<date>.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_stock import get_history  # noqa: E402
from technical_advanced import predict_technical_advanced  # noqa: E402

WF = ROOT / "outputs" / "walk_forward"
HIT_THRESHOLD_PCT = 5.0

STOCKS = ["AAPL", "NVDA", "MSFT", "7203.T", "6758.T", "XOM", "CVX", "NEM", "COIN", "MSTR"]


def backfill_one(ticker: str) -> dict:
    """1 銘柄について technical_v2 を後付け計算してファイルを更新。"""
    safe_ticker = ticker.replace(".", "_")
    files = sorted(WF.glob(f"{safe_ticker}_*.json"), reverse=True)
    if not files:
        return {"ticker": ticker, "error": "no walk-forward file"}

    fp = files[0]
    data = json.loads(fp.read_text(encoding="utf-8"))

    # 全期間の履歴を一度取得
    print(f"[{ticker}] fetching 5y history...")
    history = get_history(ticker, "5y")
    if not history:
        return {"ticker": ticker, "error": "history fetch failed"}

    # date → index のマップ
    date_to_idx = {h["date"]: i for i, h in enumerate(history)}

    samples = data.get("samples", [])
    forecast_days = data.get("forecast_days", 21)
    updated = 0
    abs_errs = []
    dir_hits = []

    for sample in samples:
        pd_date = sample.get("prediction_date")
        actual_close = sample.get("actual_close")
        past_close = sample.get("past_close")
        if pd_date not in date_to_idx or actual_close is None:
            continue
        idx = date_to_idx[pd_date]
        past_hist = history[: idx + 1]
        adv = predict_technical_advanced(past_hist, forecast_days)
        if not adv:
            continue
        pred = adv["predicted"]
        err = (pred - actual_close) / actual_close * 100
        dir_pred = pred > past_close
        dir_actual = actual_close > past_close
        sample["models"]["technical_v2"] = {
            "predicted": pred,
            "error_pct": err,
            "abs_error_pct": abs(err),
            "hit": abs(err) <= HIT_THRESHOLD_PCT,
            "direction_hit": dir_pred == dir_actual,
        }
        updated += 1
        abs_errs.append(abs(err))
        dir_hits.append(dir_pred == dir_actual)

    if not abs_errs:
        return {"ticker": ticker, "error": "no samples updated"}

    # stats_by_model に technical_v2 統計を追加
    signed_errs = [s["models"]["technical_v2"]["error_pct"] for s in samples if "technical_v2" in s["models"]]
    hits_5pct = sum(1 for s in samples if s["models"].get("technical_v2", {}).get("hit"))
    data.setdefault("stats_by_model", {})["technical_v2"] = {
        "samples": len(abs_errs),
        "avg_abs_error_pct": round(sum(abs_errs) / len(abs_errs), 2),
        "median_abs_error_pct": round(sorted(abs_errs)[len(abs_errs) // 2], 2),
        "max_abs_error_pct": round(max(abs_errs), 2),
        "min_abs_error_pct": round(min(abs_errs), 2),
        "hit_count_5pct": hits_5pct,
        "hit_rate_5pct": round(hits_5pct / len(abs_errs) * 100, 1),
        "direction_hit_rate": round(sum(dir_hits) / len(dir_hits) * 100, 1),
        "bias_pct": round(sum(signed_errs) / len(signed_errs), 2) if signed_errs else 0,
    }

    fp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {
        "ticker": ticker,
        "updated_samples": updated,
        "avg_abs_error_pct": data["stats_by_model"]["technical_v2"]["avg_abs_error_pct"],
        "direction_hit_rate": data["stats_by_model"]["technical_v2"]["direction_hit_rate"],
    }


def main():
    results = []
    for t in STOCKS:
        try:
            r = backfill_one(t)
            results.append(r)
            print(json.dumps(r, ensure_ascii=False))
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})
            print(f"[{t}] error: {e}")
    print()
    print("=== 集計 ===")
    avgs = [r.get("avg_abs_error_pct") for r in results if r.get("avg_abs_error_pct") is not None]
    dirs = [r.get("direction_hit_rate") for r in results if r.get("direction_hit_rate") is not None]
    if avgs:
        print(f"technical_v2 平均誤差: {sum(avgs) / len(avgs):.2f}%")
        print(f"technical_v2 方向当たり率: {sum(dirs) / len(dirs):.1f}%")


if __name__ == "__main__":
    main()
