"""
pdca_loop.py — 重み学習による PDCA 連続実行(N サイクル)

walk-forward で取得済みの予測サンプル(全銘柄)を使い回して、
**Act フェーズの重み更新を N サイクル繰り返す**ループ。

各サイクル:
  Plan: 現在の重み W で重み付きアンサンブル予測を構成
  Do:   全サンプル × 全銘柄でアンサンブル予測を計算
  Check: アンサンブルの平均絶対誤差・方向当たり率を測定
  Act:  各モデルの平均絶対誤差から、重みを微更新(学習率 lr)
        weight_new = (1 - lr) * weight_old + lr * inverse_error_ratio

ログは outputs/pdca_loop_<YYYYMMDD-HHMM>.json に保存。

⚠️ 投資助言ではありません。
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF_DIR = ROOT / "outputs" / "walk_forward"
LOG_DIR = ROOT / "outputs"

DEFAULT_TICKERS = [
    "AAPL", "NVDA", "MSFT", "7203_T", "6758_T",
    "XOM", "CVX", "NEM", "COIN", "MSTR",
]
MODELS = ["linear", "mean_reversion", "technical", "monte_carlo", "macro_linked"]


def load_all_samples(tickers: list[str]) -> dict[str, list[dict]]:
    """銘柄ごとに最新の walk_forward 結果から samples を読み出す。"""
    out = {}
    for t in tickers:
        files = sorted(WF_DIR.glob(f"{t}_*.json"), reverse=True)
        if not files:
            continue
        try:
            data = json.loads(files[0].read_text(encoding="utf-8"))
            out[t] = data.get("samples", [])
        except Exception:
            continue
    return out


def compute_weighted_ensemble(samples: dict[str, list[dict]], weights: dict[str, float]) -> dict:
    """全銘柄全サンプルで、現在の重みによる重み付きアンサンブル予測を計算し、誤差統計を返す。"""
    abs_errors = []
    dir_hits = []
    by_ticker_stats = {}

    for ticker, ticker_samples in samples.items():
        t_errs = []
        t_dirs = []
        for s in ticker_samples:
            past_close = s["past_close"]
            actual = s["actual_close"]
            if past_close is None or actual is None or actual == 0:
                continue
            # 各モデルの予測値を加重平均
            num = 0.0
            denom = 0.0
            for m in MODELS:
                w = weights.get(m, 0)
                if w <= 0:
                    continue
                pred = s["models"].get(m, {}).get("predicted")
                if pred is None:
                    continue
                num += pred * w
                denom += w
            if denom == 0:
                continue
            ens_pred = num / denom
            err = (ens_pred - actual) / actual * 100
            t_errs.append(abs(err))
            dir_hit = (ens_pred > past_close) == (actual > past_close)
            t_dirs.append(dir_hit)
            abs_errors.append(abs(err))
            dir_hits.append(dir_hit)

        by_ticker_stats[ticker] = {
            "samples": len(t_errs),
            "avg_abs_error_pct": round(sum(t_errs) / len(t_errs), 3) if t_errs else None,
            "direction_hit_rate": round(sum(1 for d in t_dirs if d) / len(t_dirs) * 100, 1) if t_dirs else None,
        }

    return {
        "samples_total": len(abs_errors),
        "avg_abs_error_pct": round(sum(abs_errors) / len(abs_errors), 3) if abs_errors else None,
        "direction_hit_rate": round(sum(1 for d in dir_hits if d) / len(dir_hits) * 100, 1) if dir_hits else None,
        "by_ticker": by_ticker_stats,
    }


def compute_per_model_errors(samples: dict[str, list[dict]]) -> dict[str, float]:
    """各モデル単独の平均絶対誤差を返す(全銘柄全サンプル)。"""
    out = {}
    for m in MODELS:
        errs = []
        for ticker_samples in samples.values():
            for s in ticker_samples:
                ed = s["models"].get(m, {})
                e = ed.get("abs_error_pct")
                if e is not None:
                    errs.append(e)
        out[m] = sum(errs) / len(errs) if errs else None
    return out


def update_weights(
    current: dict[str, float],
    per_model_errors: dict[str, float],
    learning_rate: float = 0.15,
) -> dict[str, float]:
    """誤差逆数比例ルールで重みを更新する。
    新しい重み目標: 1 / (誤差^2) を正規化。これと現在の重みを学習率で混ぜる。"""
    inverse_scores = {}
    for m, err in per_model_errors.items():
        if err is None or err <= 0:
            inverse_scores[m] = 0
        else:
            inverse_scores[m] = 1.0 / (err ** 2)
    total = sum(inverse_scores.values())
    if total <= 0:
        return current
    target = {m: inverse_scores[m] / total for m in inverse_scores}
    # 学習率でブレンド
    updated = {}
    for m in MODELS:
        old = current.get(m, 0)
        new = (1 - learning_rate) * old + learning_rate * target.get(m, 0)
        updated[m] = round(new, 4)
    # 正規化(合計 1)
    s = sum(updated.values())
    if s > 0:
        updated = {k: round(v / s, 4) for k, v in updated.items()}
    return updated


def run_pdca_loop(
    tickers: list[str] | None = None,
    cycles: int = 20,
    learning_rate: float = 0.15,
    initial_weights: dict[str, float] | None = None,
) -> dict:
    tickers = tickers or DEFAULT_TICKERS
    samples = load_all_samples(tickers)
    if not samples:
        return {"error": "walk_forward 結果が見つかりません。先に walk_forward.py を実行してください。"}

    # 初期重み(均等 or 指定)
    if initial_weights is None:
        weights = {m: round(1 / len(MODELS), 4) for m in MODELS}
    else:
        s = sum(initial_weights.values())
        weights = {k: v / s for k, v in initial_weights.items()}

    # 各モデルの単独誤差(これは固定、サンプルは変わらない)
    per_model_errors = compute_per_model_errors(samples)

    log = {
        "started_at": datetime.now().isoformat(),
        "cycles": cycles,
        "learning_rate": learning_rate,
        "tickers": list(samples.keys()),
        "samples_per_ticker": {t: len(s) for t, s in samples.items()},
        "per_model_avg_error": per_model_errors,
        "history": [],
    }

    for cycle in range(1, cycles + 1):
        # Plan + Do + Check
        stats = compute_weighted_ensemble(samples, weights)

        cycle_log = {
            "cycle": cycle,
            "weights": dict(weights),
            "ensemble_avg_abs_error_pct": stats["avg_abs_error_pct"],
            "ensemble_direction_hit_rate": stats["direction_hit_rate"],
        }
        log["history"].append(cycle_log)

        # Act: 重み更新(最終サイクル以外)
        if cycle < cycles:
            weights = update_weights(weights, per_model_errors, learning_rate)

    log["final_weights"] = dict(weights)
    log["finished_at"] = datetime.now().isoformat()
    return log


def save_log(log: dict) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    fp = LOG_DIR / f"pdca_loop_{ts}.json"
    fp.write_text(json.dumps(log, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return fp


def latest_log() -> dict | None:
    files = sorted(LOG_DIR.glob("pdca_loop_*.json"), reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception:
        return None


if __name__ == "__main__":
    import sys

    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    log = run_pdca_loop(cycles=cycles)
    if "error" in log:
        print(json.dumps(log, ensure_ascii=False))
        sys.exit(1)
    fp = save_log(log)
    print(f"Saved: {fp}")
    print(f"Cycles: {len(log['history'])}")
    print()
    print("=== Cycle Log ===")
    print(f'{"cycle":<6} {"err%":<10} {"dir%":<8} weights')
    for h in log["history"]:
        w_short = " ".join(f"{k[:3]}={v:.3f}" for k, v in h["weights"].items())
        print(f"{h['cycle']:<6} {h['ensemble_avg_abs_error_pct']:<10.2f} {h['ensemble_direction_hit_rate']:<8.1f} {w_short}")
    print()
    print("Final weights:", log["final_weights"])
