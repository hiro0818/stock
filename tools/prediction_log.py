"""
prediction_log.py — 予測ログの永続化と検証(疑似 PDCA の Do / Check)

予測したら JSON として保存、後で実際の株価と照合できるようにする。

保存先: outputs/predictions/<ticker>/<YYYYMMDD>.json

  {
    "ticker": "AAPL",
    "predicted_at": "2026-04-28",
    "current_price_at_prediction": 266.4,
    "target_date": "2026-05-28",       # 30 営業日後の目安
    "models": { ... predict.predict_all の出力 ... },
    "verified": false,                  # 1 ヶ月後に検証して true に更新
    "actual_price_on_target": null,     # 検証時に埋める
    "errors": null                      # 検証時に埋める
  }
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "outputs" / "predictions"


def _ensure_dir(ticker: str) -> Path:
    d = LOG_DIR / ticker.replace("/", "_")
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_prediction(
    ticker: str,
    current_price: float,
    prediction_result: dict,
    days_ahead: int = 30,
) -> Path:
    """予測結果を保存する。同じ日に複数回予測した場合は上書きする。"""
    today = datetime.now().date()
    target_date = today + timedelta(days=int(days_ahead * 1.4))  # 営業日 30 日 ≒ 暦 42 日

    record = {
        "ticker": ticker,
        "predicted_at": today.isoformat(),
        "current_price_at_prediction": current_price,
        "target_date": target_date.isoformat(),
        "days_ahead": days_ahead,
        "models": prediction_result.get("models", {}),
        "ensemble": prediction_result.get("ensemble"),
        "ensemble_band": prediction_result.get("ensemble_band"),
        "ensemble_change_pct": prediction_result.get("ensemble_change_pct"),
        "verified": False,
        "actual_price_on_target": None,
        "errors_pct": None,
        "verified_at": None,
    }

    d = _ensure_dir(ticker)
    fp = d / f"{today.isoformat()}.json"
    fp.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return fp


def list_pending_predictions(ticker: str | None = None) -> list[dict]:
    """target_date を過ぎている、まだ verified=False のレコードを返す。
    ticker 指定で絞り込み可能。"""
    if not LOG_DIR.exists():
        return []
    pending = []
    today = datetime.now().date()
    target_dirs = [LOG_DIR / ticker] if ticker else [d for d in LOG_DIR.iterdir() if d.is_dir()]
    for d in target_dirs:
        if not d.exists():
            continue
        for fp in d.glob("*.json"):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("verified"):
                continue
            target = rec.get("target_date")
            if not target:
                continue
            try:
                td = datetime.fromisoformat(target).date()
            except Exception:
                continue
            if td <= today:
                rec["_filepath"] = str(fp)
                pending.append(rec)
    return pending


def list_verified_predictions(ticker: str | None = None) -> list[dict]:
    """検証済みのレコードを返す。"""
    if not LOG_DIR.exists():
        return []
    out = []
    target_dirs = [LOG_DIR / ticker] if ticker else [d for d in LOG_DIR.iterdir() if d.is_dir()]
    for d in target_dirs:
        if not d.exists():
            continue
        for fp in d.glob("*.json"):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("verified"):
                rec["_filepath"] = str(fp)
                out.append(rec)
    return out


def list_all_predictions(ticker: str | None = None) -> list[dict]:
    """検証可否問わず全予測を返す。"""
    if not LOG_DIR.exists():
        return []
    out = []
    target_dirs = [LOG_DIR / ticker] if ticker else [d for d in LOG_DIR.iterdir() if d.is_dir()]
    for d in target_dirs:
        if not d.exists():
            continue
        for fp in d.glob("*.json"):
            try:
                rec = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            rec["_filepath"] = str(fp)
            out.append(rec)
    return sorted(out, key=lambda r: r.get("predicted_at", ""), reverse=True)


def verify_prediction(record: dict, actual_price: float) -> dict:
    """1 ヶ月経過したレコードを実際の株価で検証し、誤差を計算 + 上書き保存する。"""
    record["verified"] = True
    record["actual_price_on_target"] = actual_price
    record["verified_at"] = datetime.now().isoformat()

    errors = {}
    for model_name, model_data in (record.get("models") or {}).items():
        pred = model_data.get("predicted") if isinstance(model_data, dict) else None
        if pred is None or actual_price is None:
            errors[model_name] = None
            continue
        err_pct = (pred - actual_price) / actual_price * 100
        errors[model_name] = {
            "predicted": pred,
            "actual": actual_price,
            "error_pct": round(err_pct, 2),
            "abs_error_pct": round(abs(err_pct), 2),
            "hit_5pct": abs(err_pct) <= 5.0,
        }

    if record.get("ensemble"):
        e_err = (record["ensemble"] - actual_price) / actual_price * 100
        errors["ensemble"] = {
            "predicted": record["ensemble"],
            "actual": actual_price,
            "error_pct": round(e_err, 2),
            "abs_error_pct": round(abs(e_err), 2),
            "hit_5pct": abs(e_err) <= 5.0,
        }

    record["errors_pct"] = errors

    fp = record.get("_filepath")
    if fp:
        Path(fp).write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return record


def aggregate_accuracy() -> dict:
    """全検証済みレコードを集計して、モデル別の平均誤差・ヒット率を返す(PDCA の Act 用)。"""
    verified = list_verified_predictions()
    by_model: dict[str, list[dict]] = {}
    for rec in verified:
        for model_name, err_data in (rec.get("errors_pct") or {}).items():
            if not isinstance(err_data, dict):
                continue
            by_model.setdefault(model_name, []).append(err_data)

    summary = {}
    for model_name, errs in by_model.items():
        if not errs:
            continue
        abs_errs = [e["abs_error_pct"] for e in errs if e.get("abs_error_pct") is not None]
        hits = sum(1 for e in errs if e.get("hit_5pct"))
        summary[model_name] = {
            "samples": len(errs),
            "avg_abs_error_pct": round(sum(abs_errs) / len(abs_errs), 2) if abs_errs else None,
            "hit_count_5pct": hits,
            "hit_rate_5pct": round(hits / len(errs) * 100, 1) if errs else 0,
        }
    return {
        "total_verified": len(verified),
        "by_model": summary,
        "aggregated_at": datetime.now().isoformat(),
    }
