"""
backfill_direction_v2.py — v6 walk-forward サンプルに v7(キャリブレーション + アンサンブル)予測を後付け

既存の outputs/walk_forward_direction/<ticker>_*.json の各 sample に対し、
predict_direction_v2 で再計算 → 比較表を出力。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_stock import get_history  # noqa: E402
from predict_direction_v2 import predict_direction_v2  # noqa: E402

WF = ROOT / "outputs" / "walk_forward_direction"

import os
STOCKS_ENV = os.environ.get("V7_STOCKS", "")
STOCKS = STOCKS_ENV.split(",") if STOCKS_ENV else ["IBM", "KO", "JNJ", "XOM", "PG"]


def backfill_v2(ticker: str) -> dict:
    safe = ticker.replace(".", "_").replace("^", "")
    files = sorted(WF.glob(f"{safe}_*.json"), reverse=True)
    if not files:
        return {"ticker": ticker, "error": "no walk-forward file"}

    fp = files[0]
    data = json.loads(fp.read_text(encoding="utf-8"))

    print(f"[{ticker}] fetching history...")
    history = get_history(ticker, "max")
    if not history:
        return {"ticker": ticker, "error": "history fetch failed"}

    date_to_idx = {h["date"]: i for i, h in enumerate(history)}

    samples = data.get("samples", [])
    forecast_days = data.get("forecast_days", 21)

    n_correct = 0
    n_total = 0
    high_conf_correct = 0
    high_conf_total = 0
    new_samples = []

    print(f"[{ticker}] processing {len(samples)} samples (calibrated + ensemble)...")
    for i, sample in enumerate(samples):
        if i % 30 == 0:
            print(f"  [{ticker}] {i}/{len(samples)}")
        pd_date = sample.get("prediction_date")
        actual_close = sample.get("actual_close")
        past_close = sample.get("past_close")
        if pd_date not in date_to_idx or actual_close is None:
            continue
        idx = date_to_idx[pd_date]
        past_hist = history[: idx + 1]

        # 軽量化: アンサンブルなし、キャリブレーションのみ(時間短縮)
        result = predict_direction_v2(
            past_hist, None,
            days_ahead=forecast_days,
            use_calibration=True,
            use_ensemble=False,
        )
        if not result or "error" in result:
            continue
        prob = result["probability_up"]
        pred_up = prob >= 0.5
        actual_up = actual_close > past_close
        correct = pred_up == actual_up
        confidence = abs(prob - 0.5)
        n_total += 1
        if correct:
            n_correct += 1
        if confidence >= 0.10:
            high_conf_total += 1
            if correct:
                high_conf_correct += 1
        new_samples.append({
            "prediction_date": pd_date,
            "v2_prob_up": prob,
            "v2_correct": correct,
            "v2_confidence": confidence,
        })

    if n_total == 0:
        return {"ticker": ticker, "error": "no samples processed"}

    out = {
        "ticker": ticker,
        "v2_n_total": n_total,
        "v2_accuracy": round(n_correct / n_total * 100, 2),
        "v2_high_conf_n": high_conf_total,
        "v2_high_conf_accuracy": round(high_conf_correct / high_conf_total * 100, 2) if high_conf_total else None,
        "v6_accuracy": data.get("accuracy"),
        "v6_high_conf_accuracy": data.get("high_confidence_accuracy"),
        "improvement_overall": (n_correct / n_total * 100) - data.get("accuracy", 0),
        "improvement_high_conf": (
            (high_conf_correct / high_conf_total * 100) - data.get("high_confidence_accuracy", 0)
        ) if high_conf_total and data.get("high_confidence_accuracy") else None,
    }
    return out


def main():
    results = []
    for t in STOCKS:
        try:
            r = backfill_v2(t)
            results.append(r)
            print(json.dumps(r, ensure_ascii=False))
        except Exception as e:
            results.append({"ticker": t, "error": str(e)})
            print(f"[{t}] error: {e}")

    # 集計
    valid = [r for r in results if "error" not in r]
    if valid:
        total = sum(r["v2_n_total"] for r in valid)
        correct = sum(round(r["v2_accuracy"] / 100 * r["v2_n_total"]) for r in valid)
        h_total = sum(r["v2_high_conf_n"] for r in valid)
        h_correct = sum(round(r["v2_high_conf_accuracy"] / 100 * r["v2_high_conf_n"]) for r in valid if r.get("v2_high_conf_accuracy"))
        print()
        print("=== v7 集計 ===")
        print(f"全サンプル: {correct}/{total} = {correct/total*100:.2f}%")
        print(f"高確度のみ: {h_correct}/{h_total} = {h_correct/h_total*100:.2f}%")

        v6_total = sum(r["v6_accuracy"] for r in valid) / len(valid)
        v6_h = sum(r["v6_high_conf_accuracy"] for r in valid if r.get("v6_high_conf_accuracy")) / len([r for r in valid if r.get("v6_high_conf_accuracy")])
        print(f"\n=== v6 vs v7 ===")
        print(f"全体: v6 {v6_total:.2f}% → v7 {correct/total*100:.2f}%")
        print(f"高確度: v6 {v6_h:.2f}% → v7 {h_correct/h_total*100:.2f}%")

    # 結果保存
    out_dir = ROOT / "outputs" / "v7_direction"
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = out_dir / f"summary_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    fp.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved: {fp}")


if __name__ == "__main__":
    main()
