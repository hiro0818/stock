"""
walk_forward.py — 過去 5 年(または任意期間)を使った月次ウォークフォワード検証

各モデルが「過去のある時点で 1 ヶ月先を予測していたら、どれくらい当たっていたか」を
ローリングで全期間計算して集計する。

使い方:
  python tools/walk_forward.py <ticker> [--years 5] [--step 21]

  ticker: AAPL / 7203.T など
  --years: 検証期間(年、デフォルト 5)
  --step: ローリングステップ(営業日、デフォルト 21 = 約1ヶ月)

出力: outputs/walk_forward/<ticker>_<YYYYMMDD>.json
       各時点での予測 vs 実際 + 集計サマリ

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

from backtest import HIT_THRESHOLD_PCT, _technical_from_history  # noqa: E402
from correlation import MACRO_CANDIDATES  # noqa: E402
from fetch_stock import get_history  # noqa: E402
from predict import (  # noqa: E402
    predict_linear,
    predict_macro_linked,
    predict_mean_reversion,
    predict_monte_carlo,
    predict_technical,
)
from predict_ml import predict_crypto_linked, predict_lightgbm  # noqa: E402


# 検証時に使うコアマクロ指標(全候補だと API 呼び出しが多すぎるため、主要 12 個に絞る)
CORE_MACROS = [
    "^GSPC",   # S&P 500
    "^IXIC",   # NASDAQ
    "^N225",   # 日経 225
    "^VIX",    # VIX
    "^TNX",    # 米10年金利
    "JPY=X",   # ドル円
    "CL=F",    # 原油 WTI
    "GC=F",    # 金
    "BTC-USD", # ビットコイン
    "XLK",     # Tech ETF
    "XLE",     # Energy ETF
    "XLF",     # Financials ETF
]


def run_walk_forward(
    ticker: str,
    years: int = 5,
    step_days: int = 21,
    forecast_days: int = 21,
    use_macro: bool = True,
) -> dict:
    """ローリング検証を実行。
    forecast_days = 21 営業日(約 1 ヶ月)先を予測 → 実際値と比較。
    step_days で次の検証時点まで進む。
    use_macro=True で macro_linked モデルも検証(時間がかかる)。"""
    period = f"{years}y"
    history = get_history(ticker, period)
    if not history or len(history) < forecast_days + 90:
        return {"error": f"履歴が不足: {len(history)} 日分しかない"}

    # マクロ指標の履歴を一括取得(キャッシュ的に再利用)
    macro_histories = {}
    if use_macro:
        for m_ticker in CORE_MACROS:
            try:
                m_hist = get_history(m_ticker, period)
                if m_hist:
                    macro_histories[m_ticker] = m_hist
            except Exception:
                pass

    # 各時点でローリング(過去〜現在の history 内で window をずらす)
    samples: list[dict] = []
    n = len(history)
    # 必要: 予測時点で過去 200 日 + 予測先 forecast_days 日が揃う
    start_idx = 200
    end_idx = n - forecast_days

    for i in range(start_idx, end_idx, step_days):
        past_history = history[: i + 1]  # 予測時点までのデータ
        actual_future = history[i + forecast_days]  # 21 営業日後の実際値
        prediction_date = past_history[-1]["date"]
        actual_date = actual_future["date"]
        past_close = past_history[-1]["close"]
        actual_close = actual_future["close"]

        if past_close is None or actual_close is None:
            continue

        # その時点の技術指標を再計算
        past_tech = _technical_from_history(past_history)

        # 各モデルで予測
        preds = {
            "linear": predict_linear(past_history, forecast_days),
            "mean_reversion": predict_mean_reversion(past_history, forecast_days),
            "technical": predict_technical(past_history, past_tech, forecast_days),
        }
        mc = predict_monte_carlo(past_history, forecast_days, n_paths=200)
        preds["monte_carlo"] = mc["median"] if mc else None

        # マクロ連動予測(同時点までのマクロ履歴で計算)
        past_macro = {}
        if use_macro and macro_histories:
            for m_t, m_hist in macro_histories.items():
                # その時点の日付以下にトリミング
                cutoff = past_history[-1]["date"]
                trimmed = [h for h in m_hist if h.get("date") and h["date"] <= cutoff]
                if len(trimmed) >= 90:
                    past_macro[m_t] = trimmed
            macro_pred = predict_macro_linked(past_history, past_macro, forecast_days)
            preds["macro_linked"] = macro_pred["predicted"] if macro_pred else None
        else:
            preds["macro_linked"] = None

        # LightGBM ML 予測(マクロ込みの特徴量で学習・予測)
        if use_macro and past_macro:
            try:
                ml_pred = predict_lightgbm(past_history, past_macro, forecast_days)
                preds["lightgbm_ml"] = ml_pred["predicted"] if ml_pred and "predicted" in ml_pred else None
            except Exception:
                preds["lightgbm_ml"] = None
        else:
            preds["lightgbm_ml"] = None

        # 暗号連動(BTC ベータ)
        btc_past = past_macro.get("BTC-USD") if past_macro else None
        if btc_past:
            try:
                cp = predict_crypto_linked(past_history, btc_past, forecast_days)
                preds["crypto_linked"] = cp["predicted"] if cp else None
            except Exception:
                preds["crypto_linked"] = None
        else:
            preds["crypto_linked"] = None

        # アンサンブル
        valid = [p for p in preds.values() if p is not None]
        if valid:
            valid.sort()
            preds["ensemble"] = valid[len(valid) // 2]

        # 各モデルの誤差
        sample = {
            "prediction_date": prediction_date,
            "actual_date": actual_date,
            "past_close": past_close,
            "actual_close": actual_close,
            "actual_change_pct": (actual_close - past_close) / past_close * 100,
            "models": {},
        }
        for name, pred in preds.items():
            if pred is None:
                sample["models"][name] = {"predicted": None, "error_pct": None, "hit": None}
                continue
            err = (pred - actual_close) / actual_close * 100
            dir_pred = pred > past_close
            dir_actual = actual_close > past_close
            sample["models"][name] = {
                "predicted": pred,
                "error_pct": err,
                "abs_error_pct": abs(err),
                "hit": abs(err) <= HIT_THRESHOLD_PCT,
                "direction_hit": dir_pred == dir_actual,
            }
        samples.append(sample)

    # 集計
    by_model_stats = {}
    model_names = list(samples[0]["models"].keys()) if samples else []
    for name in model_names:
        errs = [s["models"][name].get("abs_error_pct") for s in samples if s["models"][name].get("abs_error_pct") is not None]
        hits = [s["models"][name].get("hit") for s in samples if s["models"][name].get("hit") is not None]
        dir_hits = [s["models"][name].get("direction_hit") for s in samples if s["models"][name].get("direction_hit") is not None]
        signed_errs = [s["models"][name].get("error_pct") for s in samples if s["models"][name].get("error_pct") is not None]
        if not errs:
            continue
        by_model_stats[name] = {
            "samples": len(errs),
            "avg_abs_error_pct": round(sum(errs) / len(errs), 2),
            "median_abs_error_pct": round(sorted(errs)[len(errs) // 2], 2),
            "max_abs_error_pct": round(max(errs), 2),
            "min_abs_error_pct": round(min(errs), 2),
            "hit_count_5pct": sum(1 for h in hits if h),
            "hit_rate_5pct": round(sum(1 for h in hits if h) / len(hits) * 100, 1),
            "direction_hit_rate": round(sum(1 for d in dir_hits if d) / len(dir_hits) * 100, 1),
            "bias_pct": round(sum(signed_errs) / len(signed_errs), 2),  # 符号付き平均(過大予測か過小予測か)
        }

    return {
        "ticker": ticker,
        "years": years,
        "forecast_days": forecast_days,
        "step_days": step_days,
        "samples_count": len(samples),
        "executed_at": datetime.now().isoformat(),
        "stats_by_model": by_model_stats,
        "samples": samples,
    }


def save_walk_forward(ticker: str, result: dict) -> Path:
    out_dir = ROOT / "outputs" / "walk_forward"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    fp = out_dir / f"{ticker.replace('.', '_')}_{today}.json"
    fp.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return fp


def latest_walk_forward(ticker: str) -> dict | None:
    """最新のウォークフォワード結果を読み込む。"""
    out_dir = ROOT / "outputs" / "walk_forward"
    if not out_dir.exists():
        return None
    files = sorted(out_dir.glob(f"{ticker.replace('.', '_')}_*.json"), reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--step", type=int, default=21)
    parser.add_argument("--forecast", type=int, default=21)
    args = parser.parse_args()

    print(f"[walk_forward] {args.ticker} years={args.years} step={args.step} forecast={args.forecast}")
    result = run_walk_forward(
        args.ticker,
        years=args.years,
        step_days=args.step,
        forecast_days=args.forecast,
    )
    if "error" in result:
        print(json.dumps({"error": result["error"]}, ensure_ascii=False))
        sys.exit(1)

    fp = save_walk_forward(args.ticker, result)
    # サマリ表示
    out = {
        "ticker": result["ticker"],
        "samples": result["samples_count"],
        "saved": str(fp),
        "stats_by_model": result["stats_by_model"],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
