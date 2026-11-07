# 始め方: 一件の引用を最初から最後まで通す

English: [getting-started.en.md](getting-started.en.md)（正本はこの日本語の版で、英語の版は訳である）

この案内は、一件の引用を、抜き書きから承認と `check --strict` まで通す道筋だけを書く。コマンドの全部は SKILL.md、ファイルの形は SPEC.md にある。
例の一式（`examples/first-citation/`）を使う。原典は架空の短い研究で、PDF の代わりに抽出テキストを同梱している。

コマンドは、使う側のリポジトリ（試すだけなら空のフォルダ）の根で打つ。道具は既定の置き場所 `tools/cite-bridge/` にあるものとする。
出力の例のうち、日付と指紋の入る行は省いた。

## 0. 置く

道具を `tools/cite-bridge/` に置き、例の一式の中身を根に写す。sh なら次のとおり（git のリポジトリでないなら、submodule の代わりに道具のフォルダを写す）。

```sh
git submodule add https://github.com/hiatamaworkshop/cite-bridge.git tools/cite-bridge
cp -r tools/cite-bridge/examples/first-citation/. .
```

写したもの:

| ファイル | 中身 |
|---|---|
| `bridge/bridge.toml` | 設定。書誌・抽出テキスト・抜き書き・引用の場所と、承認者の一覧（`hanako` が人） |
| `bib.md` | 書誌。key は `tanaka2024` |
| `refs/_txt/tanaka2024.txt` | 原典の抽出テキスト。本物の PDF があれば `extract` で作る（下の 2） |
| `manuscript.md` | 原稿。出典の括弧が一つあり、まだ印が無い |
| `bridge/citations.md` | 引用のファイル。見出しと `対象:` だけ |

## 1. 準備の確認（読むだけ）

設定と書誌が読め、原典の抽出テキストがあるかを `grade` で確かめる。何も書き換えない。

```sh
python tools/cite-bridge/bridge.py grade
```

期待する出力（終了コード 0）:

```text
PDF所持（抽出あり）: 1  tanaka2024
--- 1 件のうち、機械で照合できるもの 1 件（100%）
```

`PDF所持（抽出あり）` でなければ、設定の `[bibliography]` と `[sources]` のパスか、書誌の `PDF:` の書き方を見直す。

引用のファイルと原稿が読めるかを `check` で確かめる。ここでも何も書き換えない。

```sh
python tools/cite-bridge/bridge.py check
```

期待する出力（終了コード 0）:

```text
INFO  網羅: 原稿の出典らしきもの 1（括弧 1）のうち、印のあるもの 0、印の無いもの 1（印の無いものはこのツールが確かめていない。一覧は coverage、候補づくりは propose）
INFO  引用: 主張 承認済 0 / 要再確認 0 / 未承認 0、指示 0
--- 抜き書き 0 件  / 整合の崩れ 0 件
```

印の無い出典が一つあると出る。これからこれに引用を付ける。

## 2. 抽出

原本の PDF があるときは、`refs/` に置いて `python tools/cite-bridge/bridge.py extract tanaka2024` で抽出テキストを作る（pymupdf が要る）。
この例では抽出テキストを同梱しているので、この段は飛ばす。

## 3. 抜き書き

原典の一箇所を、抽出テキストから逐語のまま写す。要約と言っていないことは、逐語の範囲の外を書かない。
`bridge/excerpts/tanaka2024.md` を次の中身で作る:

```markdown
# tanaka2024

## e1
逐語: Speaking was faster than typing, but participants corrected more words after speaking.
強さ: 観察
要約: 話す入力は打つ入力より速かったが、話した後に直した語は多かった。
言っていないこと: 直す時間を含めた全体の時間で、話す方が速いとは言っていない。
記入: AI 2026-11-07
```

## 4. 引用と印

原稿の出典の括弧の直後に印〔c001〕を置き、引用のファイルに同じ ID のブロックを書く。
`manuscript.md` を次の中身で作る（印を足しただけ）:

```markdown
# 本文

## 先行研究

話す入力は打つ入力より速いが、話した後に直す語は多かったという報告がある（Tanaka, 2024）〔c001〕。
```

`bridge/citations.md` を次の中身で作る:

```markdown
# 引用
対象: manuscript.md

## c001
種類: 主張
抜き書き: tanaka2024#e1
理由: 音声の入力は速いが、直す手間が残ることを、先行研究の結果として示す
原文との差: 言い換え
記入: AI 2026-11-07
承認: 未
```

## 5. derive と check

`derive` が、抜き書きに所在・照合・前後の文（`@` で始まる行）を書く。手で直さない。

```sh
python tools/cite-bridge/bridge.py derive
```

期待する出力（終了コード 0）:

```text
derived: bridge/excerpts/tanaka2024.md（1 件）
```

`check` が整合を検査する。逐語が原典に一致し、引用が未承認であることが出る。

```sh
python tools/cite-bridge/bridge.py check
```

期待する出力（終了コード 0）:

```text
NOTE  bridge/citations.md:4 c001: 未承認（先行研究）
INFO  引用: 主張 承認済 0 / 要再確認 0 / 未承認 1、指示 0
--- 抜き書き 1 件 一致 1 / 整合の崩れ 0 件
```

`check --strict` は、確認待ち（NOTE）が残っていると止まる。提出前に使う。

```sh
python tools/cite-bridge/bridge.py check --strict
```

期待する出力（終了コード 1）:

```text
--strict: 確認待ちが残っている
```

## 6. 承認

人が、原稿の文と原典の逐語を並べて読み、原典が文を支えているかを判断する。`review` が材料を出す。
ふだんは `review --html -o review.html` の画面で判断し、保存した判断ファイルを `apply` で書き込む。この案内ではコマンドで書く。

```sh
python tools/cite-bridge/bridge.py review c001
```

期待する出力（終了コード 0）:

```text
## c001　未承認
> Speaking was faster than typing, but participants corrected more words after speaking.
- 照合: 一致
```

逐語と要約が合っていれば、要約の確認を記録する。

```sh
python tools/cite-bridge/bridge.py confirm tanaka2024#e1 --by hanako
```

期待する出力（終了コード 0）:

```text
要約の確認を記録: tanaka2024#e1 hanako
```

原典が文を支えていれば、承認を記録する。承認は人が出す（承認者の一覧で human の名前）。

```sh
python tools/cite-bridge/bridge.py approve c001 --by hanako
```

期待する出力（終了コード 0）:

```text
承認を記録: c001 hanako
```

## 7. check --strict

確認待ちが無くなり、通る。

```sh
python tools/cite-bridge/bridge.py check --strict
```

期待する出力（終了コード 0）:

```text
INFO  抜き書きの要約の確認: hanako 1
INFO  引用: 主張 承認済 1 / 要再確認 0 / 未承認 0、指示 0
--- 抜き書き 1 件 一致 1 / 整合の崩れ 0 件
```

この後に原稿の文か逐語を直すと、引用は要再確認に戻り、`check --strict` がまた止まる。承認は、承認したときの文と根拠に対してだけ有効である。

## 次に読むもの

- 原稿に出典がたくさんあるときの候補づくり（`propose`）と、承認の画面（`review --html`）: SKILL.md
- 照合が近似一致や OCR の原典で要る、原本での確認: README の「原本での確認」
- AI に使わせるときに指示ファイルへ写す短いブロック: README の「AI に使わせるとき」
