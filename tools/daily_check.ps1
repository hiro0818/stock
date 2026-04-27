# daily_check.ps1 — Windows Task Scheduler から呼び出す薄いラッパー
#
# 使い方:
#   1. このファイルのパスを Task Scheduler の「プログラム/スクリプト」に指定
#   2. 「引数の追加」は空欄
#   3. 「開始(オプション)」に stock-screening フォルダの絶対パス
#   4. トリガーで「毎日 7:00」など好きな時刻に
#
# 動作:
#   - inputs/watchlist.md を読み、全銘柄を yfinance で取得
#   - outputs/daily/<YYYYMMDD>/ に JSON と _index.md を保存
#   - 実行ログは outputs/daily/run.log に追記

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$logFile = Join-Path $projectRoot "outputs\daily\run.log"
New-Item -ItemType Directory -Path (Split-Path $logFile) -Force | Out-Null

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$timestamp] daily_check 開始" | Out-File -FilePath $logFile -Append -Encoding utf8

try {
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
    & python (Join-Path $projectRoot "tools\daily_check.py") 2>&1 |
        Out-File -FilePath $logFile -Append -Encoding utf8
    "[$timestamp] daily_check 正常終了" | Out-File -FilePath $logFile -Append -Encoding utf8
}
catch {
    "[$timestamp] daily_check エラー: $_" | Out-File -FilePath $logFile -Append -Encoding utf8
    exit 1
}
