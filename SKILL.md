---
name: cite-bridge
description: 引用ごとに錨（原典の逐語と、道具が導いた所在）を持たせ、その確認の状態を執筆中ずっと正しく保つ。抜き書き（原典の一箇所）と引用（原稿の一箇所）を決まった欄の md で書き、bridge.py が所在・前後の文・節の種類・照合の段階を導いて検査する。原典の抜き書きを足すとき、原稿に引用を足すとき、提出前に引用の確認状態を見るときに使う。
---

# 引用ブリッジ（試作、2026-10-10）

構想と決定の経緯は `notes/構想_AI協調の論文執筆ツールセットと引用ブリッジ_2026-10-10.md`（§6 の 7、§13）。
論文とは別のプロジェクトとして切り出す予定の道具で、それまでこの場所に置く。

## 保証と持ち主

- 錨の実在と所在は、このスクリプトが保証する（抽出テキストとの照合）。
- 主張を原典が支えているかは、承認者が保証する。承認者は役割で、人か、書き手と別のモデル。誰が承認したかを記録する。
- 確認が古くなっていないことは、本文の指紋が保証する。承認の後に文が変われば要再確認へ戻る。

## 書く欄と導く欄

人か AI が書くのは判断の欄だけである。`@` で始まる行はスクリプトが書く。手で直さない。

抜き書き `bridge/excerpts/<key>.md`（文献ごとに一ファイル。見出しは書誌リストの key）

```
# stepwrite2025

## e2
逐語: Users can issue commands such as "modify answer" after navigating to a given question. Upon detecting such edits, StepWrite removes all subsequent question-answer pairs.
強さ: 観察
要約: 特定の質問へ戻って回答を修正すると、それ以降の質問と回答の対がすべて削除される。
言っていないこと: 未来の質問を指名できないとは書いていない。
記入: Claude 2026-10-10
@照合: 正規化で一致
@所在: PDF 5頁目 / §3.3 Modular Prompt Pipeline: Q&A to Final Output
@節の種類: 本論
@前: …
@後: …
```

- 書く欄：逐語、強さ（観察／示唆／主張／一般化／条件付き）、要約、言っていないこと、記入（書いた者と日付）。
  照合が近似一致か照合不能のときは、原本での確認（日付、頁、確認者）を書く。確認者が分からない記録は確認として数えない。
- 要約には原文の範囲の外を書かない。自分の読みは引用の側の解釈に書く。
- 逐語は原文のまま写す。文体の規約（エムダッシュを使わない等）は逐語の欄に当てない。
- 一つの欄は一行に書く。
- 導く欄：照合、所在（頁と節）、節の種類、前、後。文献の見出しの下に格と抽出テキストの場所。

引用 `bridge/citations.md`（原稿ごとに一ファイル。原稿の引用の後に〔c001〕の印を置く）

```
# 引用
対象: thesis_vcp_workingEdition.md

## c001
種類: 主張
抜き書き: kobayashi2002#e1
理由: §2.4 で、状態が伝わりにくいという問題を小林から引き継ぐ根拠として引く
解釈: …
原文との差: 言い換え
記入: Claude 2026-10-10
承認: 未
```

- 種類は 指示（作品の名前や存在を挙げるだけ。`文献: <key>` を書く）か 主張（原典の内容を述べる。抜き書きが要る）。
- 原文との差は 一致／言い換え／限定つき一般化／外挿。外挿は確認待ちとして残り、本文に限定を付けるか自分の主張として書き直すまで解けない。
- 本文の引用符の中の文字列は、指している抜き書きの逐語に含まれていなければならない（言語が違う引用は訳とみなして外す）。
  引用符の中でも原文の逐語でない句（コマンドの型の一つの言い方、UI の文字列の一例等）は、ブロックの「引用でない句」に
  ／区切りで挙げ、括弧で理由を添える。外すかどうかは人の判断で、機械は挙げられた句だけを外す。
- 引用一件の本文は、印を含む文である。鉤括弧の中の。では文を切らない。HTML コメントは文の判定と指紋から除くので、
  コメントだけを直しても要再確認にはならない。コメントの中の印は数えない。
- 印〔c001〕は原稿に残る。提出物を作るときは `strip` で印を外した写しを作り、それを変換に渡す。

## hook

`.githooks/pre-commit` が、bridge・清書・書誌リスト・抽出テキスト・このスキルをステージしたときに check を走らせ、
整合の崩れ（ERROR）があるときだけコミットを止める。確認待ちでは止めない。有効にするのは `git config core.hooksPath .githooks`
（2026-10-10 にこのリポジトリで設定した。clone し直したら設定し直す）。検査するのは作業ツリーで、ステージした内容そのものではない。

## 設定

道具はこの論文のパスや書誌の書き方を知らない。すべて設定ファイル（既定は `bridge/bridge.toml`、`--config` で替える）から受け取る。

```toml
[bibliography]
path = "notes/書誌リスト.md"
format = "keyline"                               # 書誌の読み方（アダプタ）。keyline / bibtex / csl-json
# files_field = "file"                           # bibtex と csl-json で PDF のパスを持つ欄（Zotero・JabRef の file）
pdf_pattern = 'PDF所持: `?references/([^`]+?\.pdf)'  # 注記の中で原本の PDF を指す書き方
web_pattern = '参照 \d{4}|https?://(?!doi\.org|arxiv\.org)'  # Web 資料とみなす書誌の行
[sources]
pdf_dir = "references"
text_dir = "references/_txt"
web_dir = "references/_web"
[bridge]
excerpts = "bridge/excerpts"
citations = "bridge/citations.md"
# 以下は省略できる（省略時は下の値）
[manuscript]
mark_pattern = '〔(c\d{3,})〕'                     # 原稿の中の引用の印。グループ1が ID
quote_patterns = ['「([^「」]{10,})」', '"([^"]{20,})"']  # 抜き書きと照合する引用符
not_quote_separator = "／"                        # 引用でない句の区切り
sentence_end = '[。！？]'                         # 文の終わり。英語の原稿は '[。！？]|[.!?](?=\s)'
paragraph = "line"                               # line は一行が一段落、blank は空行で段落を区切る（行を折り返す原稿）
[output]
language = "ja"                                  # 導く欄の名前を書く言語（ja / en）
[section_kinds]                                  # 節の種類を判定する語を足す（既定は英語と日本語）
# 結果 = ["ergebnisse"]
[detect]
# common_words = ["der", "die", "und"]            # 抽出が読めるかを見る頻出語を足す（既定は英語）
```

- LaTeX では印を \cite の直後のコメントに置く（組版に影響しない）。例 `\cite{doe2020}%c017`。設定は
  `mark_pattern = '\\cite\{(?P<key>[^}]+)\}(?P<strip>%(?P<id>c\d+))'`、`paragraph = "blank"`、英語の sentence_end。
  名前つきのグループ id が ID、key があれば印の key と根拠の文献が合うかも検査し、strip があれば strip と指紋はその部分だけを外す。
- 欄の名前と値は英語でも書ける（verbatim, strength: observation, not_said, written_by, kind: claim, excerpts, diff: paraphrase 等。
  対応は bridge.py の FIELD_ALIASES と VALUE_ALIASES）。内部では日本語の名前にそろえる。出力の文はいまは日本語だけである。

## コマンド

リポジトリの根で実行する。

```
python .claude/skills/cite-bridge/bridge.py derive          # 導く欄を書き直す
python .claude/skills/cite-bridge/bridge.py check           # 整合の崩れがあれば exit 1
python .claude/skills/cite-bridge/bridge.py check --strict  # 確認待ちが残っていても exit 1（提出前）
python .claude/skills/cite-bridge/bridge.py grade --keys-from notes/引用対応表_中途レポート.md
python .claude/skills/cite-bridge/bridge.py approve c001 --by 人
python .claude/skills/cite-bridge/bridge.py --citations <別の引用ファイル> check   # 原稿が複数あるとき、写しで試すとき
python .claude/skills/cite-bridge/bridge.py extract [<key> ...] [--force]  # 原本の PDF から抽出テキストを作る（pymupdf）
python .claude/skills/cite-bridge/bridge.py snapshot <key> [<URL>]       # Web 資料の写し（既定は書誌の行の URL）
python .claude/skills/cite-bridge/bridge.py strip <原稿> <出力>            # 印を外した写しを作る
python .claude/skills/cite-bridge/bridge.py checkpoint [--label 中間提出]   # check --strict を通った地点をマニフェストで残す
```

- snapshot は生の HTML を `<web_dir>/<key>.html`（追跡しない）に、本文を `<key>.txt`（追跡する）に保存する。本文の頭書きに
  URL、取得日、生の HTML の sha256 を置く。所在は「Web 写し（取得日） / 見出し」になる。頁が更新されても、写しは取得した時点の
  ものとして残る。取り直すときは日付が変わり、照合も導き直される。

- 導く欄には「含む文」もある。逐語が文の途中で切れているとき、原文の文全体を示す。逐語の外側にある限定（「…が考えられる」
  「without critical reflection」等）を見落とさないためで、要約と言っていないことはこれを見て書く。
- grade は書誌の key ごとに格を出す。`--keys-from` に対応表を渡すと、表の key 列にあって書誌に無い key（改名の取り残し等）も出す。
- 見出しの検出は推定である（番号が順に進むものだけを見出しとし、目次の行は除く）。節が誤って導かれたら、抽出テキストの見出しの行を確かめる。

- checkpoint は、整合の崩れも確認待ちも無いときだけ `bridge/checkpoints/<UTC 時刻>.json` を書く。中身は git の HEAD と未コミットの入力、
  設定・書誌・原稿・引用・抜き書き・抽出テキストの sha256、抜き書きの照合と格の内訳、引用の状態、承認者ごとの件数。分類器の欄は空（未実装）。
- OCR は道具に入れない（外部の依存を核に持ち込まないため）。OCR で作ったテキストは、頭に `<!-- ocr` で始まる頭書き（エンジン、日付）を置いて
  `<text_dir>/<PDF と同じ名>.txt` に置く。格は「PDF所持（OCR の抽出）」になり、機械で照合できる範囲には数えない。誤読があるので、照合は近似一致が多くなる。
- 照合は key に結ばれた抽出テキスト（書誌が指す PDF と同名の `<text_dir>/<名>.txt`、無ければ `<web_dir>/<key>.txt`）の中だけで行う。
  一致しないときは他の文献での一致を手がかりとして示す。
- 照合の段階は、一致（空白の違いだけ。和字に接する空白は組版によるものとして無視する）、正規化で一致（NFKC、引用符とダッシュ、
  小書きの仮名、行末ハイフン。句読点まで違うときはそう示す）、
  近似一致（字の重なり 50% 以上。候補の所在を示す）、照合不能（抽出が無いか化けている）、不一致。
- 頁は抽出テキストの改ページ（\f）から数える。書誌に頁範囲があり PDF の頁数と合うときは印刷の頁も示す。
- 抽出テキストは pymupdf で作る（pdftotext は和文の PDF の多くで化けた）。

## 試験

`python -m unittest discover -s .claude/skills/cite-bridge/tests`。論文のデータに依らず、一時フォルダに小さな一式を作って動かす
（照合と所在、節の種類、含む文、導く欄の古さ、和文の小書きの仮名、承認と再確認、引用でない句、孤児、英語の欄名、三つの書誌の形式、
strip、印の形の設定、URL の PDF の写し、LaTeX の \cite と印の key、checkpoint、OCR の印。14件）。hook は道具の側を直したときに試験も走らせる。

## AI が守ること

- 逐語は抽出テキストか原本から写す。記憶や要約から作らない。
- 判断の欄に書いた者を記入に残す。AI が書いた要約や言っていないことは、人が見るまで候補である。
- 承認（approve）は人の指示があるときだけ行う。AI が自分の書いた引用を承認しない。
- 導く欄を手で直さない。おかしければ逐語か抽出テキストを直して derive する。
