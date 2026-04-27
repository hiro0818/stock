"""
daily_check.py — watchlist の全銘柄について日次データを取得して保存

Usage:
  python tools/daily_check.py

入力: inputs/watchlist.md(各行に1ティッカー、# で始まる行はコメント)
出力: outputs/daily/<YYYYMMDD>/<ticker>_summary.json
                              <ticker>_technical.json
                              <ticker>_competitors.json
       outputs/daily/<YYYYMMDD>/_index.md(全銘柄サマリ表)

Windows Task Scheduler で毎朝自動実行する想定。実行後、Claude Code を起動して
「watchlist の最新を見せて」と言えば、最新 JSON が読み込まれる。
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "inputs" / "watchlist.md"
DAILY = ROOT / "outputs" / "daily"

# ティッカーの妥当性チェック: 大文字英字/数字で始まり、長さ 1〜10、ピリオド・ハイフン許可
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")


def parse_watchlist() -> list[str]:
    if not WATCHLIST.exists():
        return []
    tickers = []
    for line in WATCHLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 行頭が `- ` などのマークダウン記号なら除去
        if line.startswith("- "):
            line = line[2:].strip()
        if line.startswith("* "):
            line = line[2:].strip()
        # スペースで切って最初のトークンを取り、ティッカーパターン合致のみ採用
        # ただし純数字のみ("1", "10" など)は誤検知が多いので除外
        first = line.split()[0] if line.split() else ""
        if TICKER_RE.match(first) and not first.isdigit():
            tickers.append(first)
    return tickers


def run(cmd: list[str]) -> dict:
    """子プロセスを呼んで JSON を取得。Windows のエンコーディング問題に堅牢。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        # バイト列で受け取って明示的に UTF-8 として decode する(コンソール codepage に依存しない)
        result = subprocess.run(
            cmd,
            capture_output=True,  # text=False、バイト列
            timeout=120,
            cwd=str(ROOT),
            env=env,
        )
        stdout = (result.stdout or b"").decode("utf-8", errors="replace")
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")
        if result.returncode != 0:
            return {"error": stderr.strip() or stdout.strip() or f"returncode={result.returncode}"}
        if not stdout.strip():
            return {"error": "empty stdout", "stderr": stderr[:500]}
        return json.loads(stdout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except json.JSONDecodeError as e:
        return {"error": f"json decode error: {e}", "raw": stdout[:500] if 'stdout' in dir() else ""}
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


def fetch_all(ticker: str, out_dir: Path) -> dict:
    """1銘柄について summary + technical + competitors を取得して保存。"""
    summary = run(
        [sys.executable, str(ROOT / "tools" / "fetch_stock.py"), ticker, "--mode", "summary"]
    )
    technical = run(
        [
            sys.executable,
            str(ROOT / "tools" / "fetch_stock.py"),
            ticker,
            "--mode",
            "technical",
        ]
    )
    competitors = run(
        [sys.executable, str(ROOT / "tools" / "find_competitors.py"), ticker, "--limit", "5"]
    )

    (out_dir / f"{ticker.replace('.', '_')}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / f"{ticker.replace('.', '_')}_technical.json").write_text(
        json.dumps(technical, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / f"{ticker.replace('.', '_')}_competitors.json").write_text(
        json.dumps(competitors, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "ticker": ticker,
        "name": summary.get("name") if isinstance(summary, dict) else None,
        "current_price": summary.get("current_price") if isinstance(summary, dict) else None,
        "trailing_pe": summary.get("trailing_pe") if isinstance(summary, dict) else None,
        "rsi14": technical.get("rsi14") if isinstance(technical, dict) else None,
        "trend": technical.get("trend") if isinstance(technical, dict) else None,
        "signals": technical.get("signals", []) if isinstance(technical, dict) else [],
        "competitor_count": competitors.get("competitor_count") if isinstance(competitors, dict) else 0,
        "errors": [
            x.get("error")
            for x in [summary, technical, competitors]
            if isinstance(x, dict) and "error" in x
        ],
    }


def write_index(out_dir: Path, results: list[dict]):
    """全銘柄の一覧表を Markdown で書き出す。"""
    lines = [
        f"# Daily Check Index — {out_dir.name}",
        "",
        f"取得日時: {datetime.now().isoformat()}",
        "",
        "| ティッカー | 名称 | 株価 | PER | RSI14 | トレンド | シグナル | エラー |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        signals = "; ".join(r.get("signals") or []) or "—"
        errors = "; ".join(r.get("errors") or []) or "—"
        lines.append(
            "| {ticker} | {name} | {price} | {pe} | {rsi} | {trend} | {sig} | {err} |".format(
                ticker=r.get("ticker"),
                name=(r.get("name") or "—")[:30],
                price=f"{r['current_price']:.2f}" if r.get("current_price") else "—",
                pe=f"{r['trailing_pe']:.1f}" if r.get("trailing_pe") else "—",
                rsi=f"{r['rsi14']:.1f}" if r.get("rsi14") else "—",
                trend=r.get("trend") or "—",
                sig=signals,
                err=errors[:60],
            )
        )
    (out_dir / "_index.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    tickers = parse_watchlist()
    if not tickers:
        print(
            json.dumps(
                {"error": f"watchlist が空または存在しない: {WATCHLIST}"},
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    today = datetime.now().strftime("%Y%m%d")
    out_dir = DAILY / today
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for t in tickers:
        print(f"[daily_check] fetching {t} ...")
        r = fetch_all(t, out_dir)
        results.append(r)

    write_index(out_dir, results)

    print(
        json.dumps(
            {
                "date": today,
                "out_dir": str(out_dir),
                "tickers": [r["ticker"] for r in results],
                "count": len(results),
                "index": str(out_dir / "_index.md"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
