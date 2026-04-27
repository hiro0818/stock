---
name: select-stocks
description: 銘柄選びの判断材料を5体エージェント協調で生成する標準フロー。ユーザーが /select-stocks を叩いた時、または「この銘柄を分析して」「ポートフォリオを組んで」と依頼した時に呼び出す。screener → researcher×3並列 → analyst → devil → portfolio の順に実行し、PDFレポートを生成する。
---

# select-stocks — 5体エージェント協調ワークフロー

ユーザーの投資リクエスト(`inputs/<filename>`)を入力に、銘柄リサーチ + ポートフォリオ提案 PDF を生成する。

## 起動時の引数

- リクエストファイル名(`.md` / `.txt`)。指定なしなら `inputs/` 配下の最新更新ファイルを使用。

## 手順

### Step 0: 準備

1. リクエストファイルの確定:
   - 引数あり → `inputs/<引数>` を確認(無ければエラー終了)
   - 引数なし → `Glob` で `inputs/*.md` および `inputs/*.txt` を取得し、最新更新を選ぶ
2. `run_id` を生成:PowerShell `Get-Date -Format yyyyMMdd-HHmm`
3. `outputs/<run_id>/` を作成
4. 起動メッセージ:`🟢 select-stocks 開始: <ファイル> → outputs/<run_id>/`
5. **冒頭で免責事項を表示**:
   ```
   ⚠️ 注意: 本ツールは投資助言を提供しません。判断材料の整理のみを行い、最終的な投資判断と責任はユーザーにあります。
   ```

### Step 1: screener(投資方針構造化)

`Task` ツールで `screener` サブエージェントを起動。プロンプトに含めるもの:
- リクエストファイルの絶対パス
- `run_id`
- 「`outputs/<run_id>/01_request.md` を作成し、ティッカーを fetch_stock.py で検証すること」

完了後、ユーザーに 1 行で報告:
```
[1/5] 投資方針構造化完了 → outputs/<run_id>/01_request.md をご確認ください
```

### Step 2: researcher × 3(並列リサーチ)

**重要: 同一アシスタントメッセージ内で `Task` ツールを 3 回コールし、並列実行する。**

各プロンプトに含めるもの:
- `run_id`
- 観点(`fundamentals` / `industry` / `macro`)
- 「`tools/fetch_stock.py` で API データを取得し、`knowledge/` 配下も参照、`outputs/<run_id>/02_research_<観点>.md` を作成すること」

3 体とも完了したら 1 行報告:
```
[2/5] リサーチ完了(3並列) → outputs/<run_id>/02_research_*.md をご確認ください
```

### Step 3: analyst(統合判定)

`Task` で `analyst` を起動、プロンプトに `run_id`。

完了後:
```
[3/5] 銘柄判定完了 → outputs/<run_id>/03_analysis.md をご確認ください
```

### Step 4: devil(批判)

`Task` で `devil` を起動、プロンプトに `run_id`。

完了後:
```
[4/5] 批判レビュー完了 → outputs/<run_id>/04_devil.md をご確認ください
```

### Step 5: portfolio(最終統合)

`Task` で `portfolio` を起動、プロンプトに `run_id`。`final_report.md` と `final_report.pdf` を生成。

完了後:
```
[5/5] 最終レポート生成完了
最終ファイル: outputs/<run_id>/final_report.pdf

⚠️ 改めての注意: これは投資助言ではありません。一次資料を確認の上、自己責任で判断してください。
```

## エラー時の挙動

- リクエストファイルが見つからない → 中断、`inputs/` の状態を提示
- ティッカーが yfinance で見つからない → screener が `要確認` フラグを立てて続行
- API レート制限 → researcher が指数バックオフで再試行、それでもダメなら該当銘柄をスキップして続行(他は処理)

## ルール

- 各ステップ完了時に**1行進捗 + ユーザーへのレビュー誘導**を出すこと。
- 中間成果物の内容を要約して垂れ流さない(成果物のパスだけ示す)。
- **免責事項を Step 0 と Step 5 で必ず表示**。
- API 取得時刻は全て記録(再現性のため)。
- 機密情報は基本入らない設計だが、`knowledge/` の中身は外部送信しない(CLAUDE.md ルール)。
