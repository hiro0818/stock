"""
walk_forward_direction.py — 方向予測の長期バックテスト(50 年〜)

各時点でその時点までのデータで LightGBM 分類器を学習し、21 営業日先の方向を予測。
全期間を月次ローリング。

実行:
  python tools/walk_forward_direction.py <ticker> [--years 50] [--step 21]

長期データが取れる銘柄(50 年以上):
  IBM, KO, JNJ, PG, XOM, JPM, GE, ^GSPC, ^DJI

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from fetch_stock import get_history  # noqa: E402
from predict_direction import build_classification_data  # noqa: E402

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False


def run_walk_forward_direction(
    ticker: str,
    years: int = 50,
    step_days: int = 21,
    forecast_days: int = 21,
    min_train: int = 252 * 3,  # 学習用最低 3 年分
    classifier_params: dict | None = None,
) -> dict:
    """ローリング 2 値分類検証。各時点で学習データを使って学習 → 1 ヶ月先の方向予測。"""
    if not HAS_LGBM:
        return {"error": "lightgbm not installed"}

    if classifier_params is None:
        classifier_params = {
            "n_estimators": 100,
            "learning_rate": 0.05,
            "num_leaves": 15,
            "min_child_samples": 5,
            "verbose": -1,
            "random_state": 42,
        }

    period = "max" if years >= 30 else f"{years}y"
    history = get_history(ticker, period)
    if not history or len(history) < min_train + forecast_days + 30:
        return {"error": f"履歴不足: {len(history) if history else 0} 日"}

    # 必要に応じて期間を切り取る(50 年 = 252×50 = 12600 日)
    target_n = years * 252 + min_train + forecast_days
    if len(history) > target_n:
        history = history[-target_n:]

    n = len(history)
    samples = []
    n_correct = 0
    n_total = 0

    # 高確度 |p-0.5|>=0.1 のみで判定したときの精度も別計測
    high_conf_correct = 0
    high_conf_total = 0

    start_idx = min_train
    end_idx = n - forecast_days

    for i in range(start_idx, end_idx, step_days):
        past_history = history[: i + 1]
        actual_future = history[i + forecast_days]
        if past_history[-1].get("close") is None or actual_future.get("close") is None:
            continue
        c_now = past_history[-1]["close"]
        c_future = actual_future["close"]
        actual_up = c_future > c_now

        # その時点までのデータで学習データ作成
        train = build_classification_data(past_history, None, forecast_days=forecast_days)
        if not train or len(train[0]) < 100:
            continue
        Xs, ys = train

        feature_names = list(Xs[0].keys())
        X_arr = [[x.get(f, 0.0) for f in feature_names] for x in Xs]

        try:
            model = lgb.LGBMClassifier(**classifier_params)
            model.fit(X_arr, ys)

            # 現時点での予測
            from predict_ml import build_features
            cur_feat = build_features(past_history, None, end_idx=len(past_history) - 1)
            if not cur_feat:
                continue
            x_cur = [[cur_feat.get(f, 0.0) for f in feature_names]]
            prob_up = float(model.predict_proba(x_cur)[0][1])
            pred_up = prob_up >= 0.5
            confidence = abs(prob_up - 0.5)

            correct = (pred_up == actual_up)
            samples.append({
                "prediction_date": past_history[-1]["date"],
                "actual_date": actual_future["date"],
                "past_close": c_now,
                "actual_close": c_future,
                "actual_up": actual_up,
                "prob_up": prob_up,
                "pred_up": pred_up,
                "correct": correct,
                "confidence": confidence,
            })
            n_total += 1
            if correct:
                n_correct += 1
            if confidence >= 0.10:
                high_conf_total += 1
                if correct:
                    high_conf_correct += 1
        except Exception as e:
            continue

    if n_total == 0:
        return {"error": "サンプルが生成できなかった"}

    return {
        "ticker": ticker,
        "years_target": years,
        "actual_years": (n - min_train) / 252,
        "step_days": step_days,
        "forecast_days": forecast_days,
        "samples_count": n_total,
        "executed_at": datetime.now().isoformat(),
        "classifier_params": classifier_params,
        "accuracy": round(n_correct / n_total * 100, 2),
        "n_correct": n_correct,
        "n_total": n_total,
        "high_confidence_accuracy": round(high_conf_correct / high_conf_total * 100, 2) if high_conf_total > 0 else None,
        "high_confidence_n": high_conf_total,
        "samples": samples,
    }


def save_result(ticker: str, result: dict) -> Path:
    out_dir = ROOT / "outputs" / "walk_forward_direction"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    fp = out_dir / f"{ticker.replace('.', '_').replace('^', '')}_{today}.json"
    fp.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return fp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--years", type=int, default=50)
    parser.add_argument("--step", type=int, default=21)
    args = parser.parse_args()

    result = run_walk_forward_direction(
        args.ticker, years=args.years, step_days=args.step, forecast_days=21
    )
    if "error" in result:
        print(json.dumps({"ticker": args.ticker, "error": result["error"]}, ensure_ascii=False))
        sys.exit(1)

    fp = save_result(args.ticker, result)
    out = {
        "ticker": result["ticker"],
        "actual_years": round(result["actual_years"], 1),
        "samples_count": result["samples_count"],
        "accuracy": result["accuracy"],
        "high_confidence_accuracy": result["high_confidence_accuracy"],
        "high_confidence_n": result["high_confidence_n"],
        "saved": str(fp),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
