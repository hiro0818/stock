# 銘柄選びアシスタント(stock-screening)

> **重要**: このツールは投資助言ではありません。判断材料を整理した結果は、最終的な投資判断と責任はユーザー自身にあります。

日本株・米国株の銘柄選定の判断材料を、Claude Code の 5 体のサブエージェント(screener → researcher×3並列 → analyst → devil → portfolio)で構造化するアシスタントです。yfinance API 経由で最新の財務指標を取得し、ハルシネーションを抑えた数値ベースのレポートを PDF 出力します。

---

## セットアップ

### 1. Claude Code

[Claude Code 公式](https://claude.com/claude-code) からインストール。

### 2. Python と必要パッケージ

```powershell
pip install yfinance streamlit plotly pandas pytrends
```

| パッケージ | 用途 |
|---|---|
| yfinance | 株価・財務データの取得 |
| streamlit + plotly + pandas | Web ダッシュボード |
| pytrends | Google Trends(検索ボリューム) |

### 3. (任意)PDF 出力したいなら

```powershell
winget install --id JohnMacFarlane.Pandoc
winget install --id tschoonj.GTKForWindows
pip install weasyprint
```

PowerShell を再起動してから `pandoc --version` で確認。

### 4. Claude Code を起動

```powershell
cd "<このフォルダ>"
claude
```

### 5. (推奨)Web ダッシュボード

ブラウザで使える GUI。**事前にデータを取得しないオンデマンド設計**で、ユーザーが入力した銘柄を起点に多角的に分析します。

```powershell
pip install streamlit plotly
streamlit run app.py
```

自動でブラウザが立ち上がり `http://localhost:8501` を開きます。閉じるときは PowerShell で Ctrl+C。

#### ダッシュボードでできること

ティッカーを入れて「分析開始」を押すと、その銘柄について以下を**一度に**生成:

| タブ | 内容 |
|---|---|
| 🎯 トップ画面 | 5 観点(バリュエーション / 収益性 / 成長性 / 財務健全性 / テクニカル)を 0-100 でスコア化、強気・中立・弱気を自動判定。強み/弱みを箇条書きで提示 |
| 💰 ファンダメンタル | 主要指標 12 項目 + 観点別の解釈コメント |
| 📈 テクニカル | ローソク足 + MA20/50/200 + RSI(14)+ MACD(Plotly でズーム可)、シグナル自動検出 |
| 🏢 競合比較 | 同業他社を yfinance の業界情報から自動列挙 + 横並び比較表 |
| 🌐 関連テーマ | 銘柄が属するメタトレンド(AI / 半導体 / EV / クラウド など)と同テーマ銘柄の比較 |
| 🌍 マクロ環境 | 銘柄に関係が深い指標(米金利 / VIX / ドル円 / 関連 ETF)を自動選別 |
| **📊 1ヶ月予測** | **5 モデル(線形回帰 / 平均回帰 / アナリスト / テクニカル / モンテカルロ)+ 中央値アンサンブル。30 営業日前のデータでバックテスト → ヒット率と平均絶対誤差を即時表示。予測ログを保存して PDCA を回せる** |
| **📰 ニュース・声** | **Yahoo Finance ニュース 10 件 + Google Trends(検索ボリューム推移)+ X / StockTwits / TradingView へのリンク** |
| **🔄 PDCA(予測精度)** | **過去の予測ログを集計し、モデル別の平均誤差・ヒット率を表示。検証待ちの予測を「今の終値で照合」するボタン付き** |
| 🔍 生データ | yfinance の生レスポンス + スコア計算の中身(裏取り用) |

すべてキャッシュ TTL = 1 時間で、データ遅延を 1 時間以内に保ちます。

### 6. Claude Code から使う(2 通り)

#### 5a. 単一銘柄の即時評価
```
/quick-eval AAPL
```
ファンダ + 技術指標 + 競合比較が即座にチャットに出ます。`outputs/quick-eval/<ticker>_<YYYYMMDD-HHMM>.md` にも保存。

#### 5b. フルリサーチ + ポートフォリオ提案
```
/select-stocks sample_request.md
```
5 体エージェントが順に走り、`outputs/<YYYYMMDD-HHMM>/final_report.pdf` を生成。

---

## 使い方

### 用途別の使い分け

| やりたいこと | 使うインタフェース |
|---|---|
| **GUI でグラフ見ながら触りたい** | **`streamlit run app.py`(Web ダッシュボード)** |
| 「この株どう?」と聞く感覚で即評価 | Claude Code で `/quick-eval AAPL` |
| 翌日もう一回最新を見たい | 同じコマンド `/quick-eval AAPL` を翌日叩く / ダッシュボードを再表示 |
| 複数銘柄を毎日自動で追跡したい | `inputs/watchlist.md` に登録 → daily_check.py(後述) |
| 投資方針から推奨ポートフォリオを設計 | Claude Code で `/select-stocks` |

---

### A. 自分の投資方針を `inputs/` に置く

`inputs/sample_request.md` をコピーして、自分の方針を書き込みます。形式は自由ですが、以下を含めると精度が上がります:

- 投資目的・期間・リスク許容度
- 検討したい銘柄(ティッカー or 企業名)
- 除外条件
- 知りたいこと(バリュエーション、競合、撤退条件など)

### B. 実行

```
/select-stocks                       # inputs/ の最新ファイルを自動選択
/select-stocks 自分のリクエスト.md   # ファイルを指定
```

### C. 出力を確認

`outputs/<YYYYMMDD-HHMM>/`:

| ファイル | 内容 |
|---|---|
| `01_request.md` | 投資方針の構造化、対象ティッカー確定 |
| `02_research_fundamentals.md` | 各銘柄の財務指標(yfinance + knowledge/) |
| `02_research_industry.md` | 業界動向・競合分析 |
| `02_research_macro.md` | 金利・為替・政策の影響 |
| `03_analysis.md` | analyst の統合判定(買い/様子見/避ける) |
| `04_devil.md` | devil の全否定批判 |
| `final_report.md` | 最終ポートフォリオ提案(Markdown) |
| `final_report.pdf` | 最終レポート(PDF) |

---

## `knowledge/` の使い方

自分が読んだ証券会社レポート、決算短信メモ、IR 資料の要約を Markdown で投入します。researcher が API データと併せて参照するため、これがあるほど質が上がります。

例:
```
knowledge/
├── aapl_2024Q4_earnings.md
├── 7203_2024_annual_summary.md
├── tech_sector_outlook_2026.md
└── jp_macro_2026Q1.md
```

機密度に応じて `.gitignore` で除外済み。

---

## ティッカーの書き方

| 市場 | 例 |
|---|---|
| 米国株 | `AAPL`, `MSFT`, `GOOGL`, `NVDA` |
| 日本株 | `7203.T`(トヨタ), `9984.T`(ソフトバンクG), `6758.T`(ソニーG) |

日本株は **証券コード + `.T`** の形式で yfinance に渡します。

---

## 構成

```
.
├── CLAUDE.md                       プロジェクトルール
├── README.md                       このファイル
├── app.py                          Streamlit Web ダッシュボード(streamlit run app.py)
├── .gitignore                      機密分離
├── .claude/
│   ├── agents/                     5 体のサブエージェント
│   │   ├── screener.md             投資方針構造化
│   │   ├── researcher.md           リサーチ(3観点で並列)
│   │   ├── analyst.md              統合判定
│   │   ├── devil.md                全否定批判
│   │   └── portfolio.md            最終ポートフォリオ + PDF
│   ├── skills/
│   │   ├── select-stocks/SKILL.md  フルリサーチ + ポートフォリオ提案
│   │   └── quick-eval/SKILL.md     単一銘柄の即時評価
│   └── commands/
│       ├── select-stocks.md        /select-stocks コマンド
│       └── quick-eval.md           /quick-eval コマンド
├── tools/
│   ├── fetch_stock.py              yfinance ラッパー(summary/full/history/technical)
│   ├── find_competitors.py         同業他社の自動列挙(yfinance industry ベース)
│   ├── themes.py                   テーマ別銘柄バスケット + マクロ指数の定義
│   ├── scoring.py                  5 観点の多角スコアリング
│   ├── macro_context.py            銘柄から関連マクロ指標を自動選別
│   ├── predict.py                  1ヶ月先株価予測(5 モデル + アンサンブル)
│   ├── backtest.py                 過去 30 日でモデル精度評価(疑似 PDCA Check)
│   ├── prediction_log.py           予測の永続化と検証(PDCA Do/Check/Act)
│   ├── extra_sources.py            yfinance ニュース + Google Trends + 外部リンク
│   ├── daily_check.py              watchlist 全銘柄の日次取得
│   └── daily_check.ps1             Task Scheduler 用ラッパー
├── inputs/
│   ├── .gitkeep
│   └── sample_request.md           動作確認用サンプル
├── knowledge/
│   └── .gitkeep
└── outputs/
    └── .gitkeep
```

---

## Watchlist + 日次自動チェック

### `inputs/watchlist.md` に追跡銘柄を登録

```markdown
- AAPL
- MSFT
- 7203.T
- 6758.T
```

### 手動で 1 回実行(動作確認)

```powershell
python tools/daily_check.py
```

`outputs/daily/<YYYYMMDD>/` に各銘柄の `*_summary.json` `*_technical.json` `*_competitors.json` が並び、
`_index.md` に全銘柄の一行サマリ表が出ます。

### Windows Task Scheduler で毎朝自動化

`tools/daily_check.ps1` を Task Scheduler に登録すると、毎朝勝手にデータが取れて、Claude Code を
起動した時には最新が手元にある状態になります。

**設定手順**:

1. Windows キー → `タスク スケジューラ` を起動
2. 右ペインの「**基本タスクの作成**」をクリック
3. 名前: `stock-daily-check`、説明: 任意
4. トリガー: 毎日 → 開始時刻(例: 7:00)
5. 操作: **プログラムの開始** を選択
6. 「プログラム/スクリプト」に `powershell.exe`
7. 「引数の追加」に:
   ```
   -NoProfile -ExecutionPolicy Bypass -File "C:\Users\hiroy\OneDrive\デスクトップ\stock-screening\tools\daily_check.ps1"
   ```
8. 「開始(オプション)」に:
   ```
   C:\Users\hiroy\OneDrive\デスクトップ\stock-screening
   ```
9. 「完了」で保存

実行ログは `outputs/daily/run.log` に追記されます。

### Claude Code から最新データを呼び出す

スケジューラで取得したデータは、自然言語で頼めます:

```
今朝の watchlist の最新を見せて
昨日と今日で AAPL が動いたか教えて
RSI が 70 を超えてる銘柄ある?
```

Claude が `outputs/daily/<YYYYMMDD>/_index.md` を読んでサマリを返します。

---

## ツール単体で使う

エージェント経由でなく、Python だけで個別に値を取りたい時:

```powershell
# 主要指標のサマリ
python tools/fetch_stock.py AAPL --mode summary

# 主要指標 + 1年株価 + 直近4Q財務 + 技術指標
python tools/fetch_stock.py 7203.T --mode full

# 技術指標のみ(MA20/50/200, RSI, MACD, 出来高分析)
python tools/fetch_stock.py AAPL --mode technical

# 1年分の日足株価のみ
python tools/fetch_stock.py NVDA --mode history --period 1y

# 同業他社の自動列挙
python tools/find_competitors.py AAPL --limit 5

# Watchlist を一括取得
python tools/daily_check.py
```

JSON が標準出力に流れます。

---

## カスタマイズ・拡張

### J-Quants(日本株の上場企業情報 API)を追加したい

1. https://jpx-jquants.com/ で無料登録
2. `tools/fetch_jquants.py` を作って、決算短信や四半期データを取得
3. `researcher` に「fundamentals 観点では fetch_stock.py と fetch_jquants.py の両方を使う」と追記

### Web 検索を許可したい

CLAUDE.md と各エージェントの `tools` 行に `WebSearch` を足せば使えるようになります。**ただしハルシネーション・誤情報リスクが上がる**ので、CLAUDE.md の方針(API データを一次情報源)を維持することを推奨。

---

## 制約と注意

- **yfinance は通常 15 分以上のデータ遅延**があります。リアルタイムの売買判断には使えません。
- **海外取引所のデータが不安定**になることがあります(Yahoo Finance のスクレイピング系ライブラリのため)。
- **LLM のハルシネーションは消えません**。各レポートで引用された数値は必ず一次資料(決算短信、IR ページ)で裏取りしてください。
- **投資判断は自己責任**。本ツールが出す「推奨度」は判断材料の整理であり、売買指示ではありません。

---

## トラブルシューティング

### `Unknown command: /select-stocks`

→ Claude Code を**このフォルダで起動していない**のが原因。`cd` してから `claude` 起動。

### `yfinance not installed`

→ `pip install yfinance` を実行、PowerShell を再起動。

### ティッカーで `name: null` が返る

→ ティッカーが間違っている、または yfinance に登録がない。日本株は `.T` 付きを確認。

### researcher が「該当資料なし」ばかり

→ `knowledge/` が空。自分の決算メモや業界レポートを `.md` で入れてから再実行。
