"""
pdca_param_search.py — LightGBM 分類器のパラメータを 50 サイクル探索

仮説駆動 PDCA:
  - サイクル 1: ベースライン(default パラメータ)で精度測定
  - サイクル 2-50: パラメータをランダムサンプリング → 改善があれば採用

評価指標: 1 銘柄(代表 AAPL)5 年 walk-forward での方向当たり率(精度)

⚠️ 投資助言ではありません。
"""

import json
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from walk_forward_direction import run_walk_forward_direction  # noqa: E402

# パラメータ候補(ランダム探索の範囲)
PARAM_RANGES = {
    "n_estimators": [50, 100, 150, 200, 300, 500],
    "learning_rate": [0.01, 0.03, 0.05, 0.07, 0.1],
    "num_leaves": [7, 11, 15, 21, 31, 47, 63],
    "min_child_samples": [3, 5, 10, 15, 20, 30],
    "max_depth": [-1, 3, 5, 7, 10],
}


def random_params(rng: random.Random) -> dict:
    return {
        "n_estimators": rng.choice(PARAM_RANGES["n_estimators"]),
        "learning_rate": rng.choice(PARAM_RANGES["learning_rate"]),
        "num_leaves": rng.choice(PARAM_RANGES["num_leaves"]),
        "min_child_samples": rng.choice(PARAM_RANGES["min_child_samples"]),
        "max_depth": rng.choice(PARAM_RANGES["max_depth"]),
        "verbose": -1,
        "random_state": 42,
    }


def main():
    cycles = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    ticker = sys.argv[2] if len(sys.argv) > 2 else "AAPL"
    years = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    print(f"PDCA Parameter Search: {cycles} cycles on {ticker} ({years}y)")
    print(f"Target: 方向当たり率を最大化")

    rng = random.Random(42)
    history_log = []

    # サイクル 1: ベースライン
    base_params = {
        "n_estimators": 100,
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_child_samples": 5,
        "max_depth": -1,
        "verbose": -1,
        "random_state": 42,
    }
    print(f"\n[Cycle 1: ベースライン]")
    result = run_walk_forward_direction(
        ticker, years=years, step_days=21, forecast_days=21, classifier_params=base_params
    )
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return
    best_acc = result["accuracy"]
    best_params = base_params
    print(f"  acc={best_acc:.2f}% (n={result['samples_count']})")
    history_log.append({
        "cycle": 1,
        "params": base_params,
        "accuracy": best_acc,
        "high_conf_acc": result.get("high_confidence_accuracy"),
        "samples": result["samples_count"],
        "best_so_far": True,
    })

    # サイクル 2-N: ランダム探索
    for c in range(2, cycles + 1):
        params = random_params(rng)
        result = run_walk_forward_direction(
            ticker, years=years, step_days=21, forecast_days=21, classifier_params=params
        )
        if "error" in result:
            print(f"[Cycle {c}] ERROR: {result['error']}")
            continue
        acc = result["accuracy"]
        improved = acc > best_acc
        if improved:
            best_acc = acc
            best_params = params
        marker = "*** NEW BEST" if improved else ""
        print(f"[Cycle {c}] acc={acc:.2f}% {marker} params={params}")
        history_log.append({
            "cycle": c,
            "params": params,
            "accuracy": acc,
            "high_conf_acc": result.get("high_confidence_accuracy"),
            "samples": result["samples_count"],
            "best_so_far": improved,
        })

    # 結果保存
    out_dir = ROOT / "outputs" / "pdca_param_search"
    out_dir.mkdir(parents=True, exist_ok=True)
    fp = out_dir / f"{ticker}_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    fp.write_text(json.dumps({
        "ticker": ticker,
        "years": years,
        "cycles": cycles,
        "best_accuracy": best_acc,
        "best_params": best_params,
        "history": history_log,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n=== 結果 ===")
    print(f"Best accuracy: {best_acc:.2f}%")
    print(f"Best params: {best_params}")
    print(f"Saved: {fp}")


if __name__ == "__main__":
    main()
