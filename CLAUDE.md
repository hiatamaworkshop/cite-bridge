# cite-bridge: 実装する AI へ

## 文書の地図

- [README.md](README.md) — 何をする道具か、使い方
- [SPEC.md](SPEC.md) — データ形式の正本
- [SKILL.md](SKILL.md) — 道具を使う AI の作法
- [docs/roadmap.md](docs/roadmap.md) — 開いている項目 (`### C<n>.`)。依頼で `C<n>` を指されたら、その節の `#### 完了条件` を満たして終える
- [docs/design-0.3.0.md](docs/design-0.3.0.md) — 0.3.0 の設計 (各節の見出しに項目の番号)

## 守ること

1. コミットと push は利用者の指示を待つ。
2. 利用者の原稿のリポジトリ (場所は CLAUDE.local.md) のデータは変えない。実データでの確認は読むだけのコマンドで行う (docs/roadmap.md の「項目」の冒頭)。
3. 周りのコードの書き方に合わせる。日本語の docstring と出力の文、標準ライブラリだけで動くこと (pymupdf は抽出と頁の画像だけで使い、関数の中で import する)。
4. check の ERROR を新しく増やさない。ERROR は git の pre-commit を止める。新しい規則は NOTE (確認待ち。`check --strict` と `checkpoint` が止まる) か INFO にする。
5. 試験は利用者のデータに依らず、一時フォルダに小さな一式を作って動かす (`tests/test_bridge.py` の形)。実行は `python -m pytest -q tests`。
6. 設計書に書いていない形式 (欄の名前、ファイルの形、出力の文の意味) を推測で決めない。決めていないことに当たったら、実装を止めて報告する。
7. 道具の文書 (README・SPEC・SKILL) に利用者の論文に固有の記述を入れない。
