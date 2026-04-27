---
description: 銘柄選びの判断材料を5体エージェント協調で生成する(投資助言ではありません)
argument-hint: "[リクエストファイル名(省略時はinputs/最新)]"
---

# /select-stocks — 銘柄リサーチ + ポートフォリオ提案

引数: `$ARGUMENTS`

`select-stocks` スキルを起動して、ユーザーの投資リクエストから銘柄リサーチと最終ポートフォリオ提案(Markdown + PDF)を生成してください。

- `$ARGUMENTS` が指定されていれば、それをリクエストファイル名として `inputs/$ARGUMENTS` を入力に使う。
- `$ARGUMENTS` が空なら、`inputs/` 配下の最新更新ファイル(`.md` / `.txt`)を自動選択する。

スキルの定義通り、screener → researcher×3並列 → analyst → devil → portfolio の順に実行し、各ステップ完了時に進捗1行とレビュー誘導を出力すること。

**Step 0 と最終出力で必ず免責事項(投資助言ではない旨)を表示すること。**
