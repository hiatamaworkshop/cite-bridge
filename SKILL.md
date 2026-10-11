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
- 言っていないことや解釈が原文の別の箇所に依るなら、その箇所も抜き書きにして ID（同じ文献なら `e6`、別の文献なら `key#e6`）で指す。
  「同じ頁にある」とだけ書いて指さない形は、未検証の主張が混ざる経路になる。check は指した ID が実在するかを検査する。
- 要約は抽出テキストではなく、確かめた逐語から書く。抽出テキストの誤読を補って要約に入れない（§16.2 の 6）。
- 人が要約・言っていないこと・強さを原文と照らしたら `confirm` で記録する（`要約の確認` と、そのときの指紋）。
  確認の後に欄が変われば check が「確認し直す」と出す。未確認の件数は check の INFO に出る（--strict では止めない）。
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
- 承認の状態は 未承認／承認済／要再確認／差し戻し／差し戻し後に直された の五つ。承認は本文の指紋と根拠の指紋
  （抜き書きの ID と逐語）を残し、どちらが変わっても要再確認へ戻る（根拠の記録が無い古い承認は本文だけを見る）。
  差し戻しは理由を `差し戻しの理由` に残す。書き手が本文か根拠を直すと「差し戻し後に直された」になり、承認を待つ。
- 人の読みも原文と照らす。人の判断（承認、差し戻し）は人の権限だが、本文に入る読みには抜き書きの錨を持たせる
  （§16.2 の 7。原文の語でない読みを本文へ移さない）。
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
# mark_format = "〔{id}〕"                        # 候補を受け入れたときに原稿へ置く印（{id} と {key}）。mark_pattern を替えたら必須
[output]
language = "ja"                                  # 導く欄の名前を書く言語（ja / en）
[section_kinds]                                  # 節の種類を判定する語を足す（既定は英語と日本語）
# 結果 = ["ergebnisse"]
[detect]
# common_words = ["der", "die", "und"]            # 抽出が読めるかを見る頻出語を足す（既定は英語）
[approvers]                                      # 承認できる者と種類（human / model）。省くと名前を問わない
# alice = "human"
[coverage]
# pattern = '…'                                  # 出典らしき括弧（既定は年を含む括弧）。印の無い文にあるものを数える
```
（[bridge] には applied、candidates、excluded も置ける。適用した判断ファイルの記録、候補の作業のフォルダ、引用でないと判断した括弧の記録で、
既定は citations と同じフォルダの applied.json、candidates/、excluded.json）

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
python .claude/skills/cite-bridge/bridge.py review [c001 ...] [--images DIR] [-o 出力.md]  # 確認用の一覧（省くと確認待ちすべて）
python .claude/skills/cite-bridge/bridge.py review --json --all [--images DIR]          # 外の表示へ渡す JSON（承認済と指示も含める）
python .claude/skills/cite-bridge/bridge.py review --html -o preview/cite_review.html     # 承認の HTML（人が見て判断する画面）
python .claude/skills/cite-bridge/bridge.py apply <判断ファイル.json> [--dry-run]          # 承認の HTML が保存した判断を書き込む
python .claude/skills/cite-bridge/bridge.py apply --latest [--from DIR] [--dry-run]       # ダウンロード（既定）の最新の判断ファイルを使う
python .claude/skills/cite-bridge/bridge.py coverage                                     # 印の無い文にある出典らしき括弧の一覧
python .claude/skills/cite-bridge/bridge.py propose [--section 2.2] [--lines 80-120] [--limit 15] [--add-key ITEM=KEY]  # 印の無い出典の作業票
python .claude/skills/cite-bridge/bridge.py sentences <key> [--grep 語 ...] [--range 40-50]   # 原典を作業票と同じ番号の文で引く
python .claude/skills/cite-bridge/bridge.py propose --load bridge/candidates/drafts.json     # 書き手の下書きを検査して候補にする
python .claude/skills/cite-bridge/bridge.py approve c001 --by 人 [--note 理由]
python .claude/skills/cite-bridge/bridge.py approve c001 --by 人 --send-back --note 理由   # 差し戻し
python .claude/skills/cite-bridge/bridge.py confirm kawahara2013#e2 --by 人            # 要約の確認
python .claude/skills/cite-bridge/bridge.py --citations <別の引用ファイル> check   # 原稿が複数あるとき、写しで試すとき
python .claude/skills/cite-bridge/bridge.py extract [<key> ...] [--force]  # 原本の PDF から抽出テキストを作る（pymupdf）
python .claude/skills/cite-bridge/bridge.py snapshot <key> [<URL>]       # Web 資料の写し（既定は書誌の行の URL）
python .claude/skills/cite-bridge/bridge.py snapshot <key> --rebuild     # 保存した生の HTML から本文を作り直す（取り直さない）
python .claude/skills/cite-bridge/bridge.py strip <原稿> <出力>            # 印を外した写しを作る
python .claude/skills/cite-bridge/bridge.py checkpoint [--label 中間提出]   # check --strict を通った地点をマニフェストで残す
```

- snapshot は生の HTML を `<web_dir>/<key>.html`（追跡しない）に、本文を `<key>.txt`（追跡する）に保存する。本文の頭書きに
  URL、取得日、生の HTML の sha256 を置く。所在は「Web 写し（取得日） / 見出し」になる。頁が更新されても、写しは取得した時点の
  ものとして残る。取り直すときは日付が変わり、照合も導き直される。

- review は、本文、根拠の逐語、所在、照合、原本での確認、前後の文、AI の候補（要約・言っていないこと）、引用の欄、判断のコマンドを
  この順に並べる。逐語を先に読ませ、AI の候補で判断が引っ張られないようにする。前後の文は抽出テキストのままで、誤読を補わない。
  近似一致・照合不能・OCR の根拠では「頁の画像で読む」と出し、--images を渡せば PDF の該当頁を PNG にする。
- 人が見て判断する画面は、review --html が作る承認の HTML である（単体で開ける一枚。頁の画像も埋め込む）。
  引用ごとのカードに、本文（段落の全体も開ける）、根拠の逐語、所在、頁の画像、前後の文、AI の候補、引用の欄を並べ、
  保留・承認・差し戻しと理由、要約を確かめた印を入れる。入力はブラウザに一時保存され、最後に判断ファイル（JSON）として保存する。
  HTML はサーバを持たず、何も書き込まない。判断ファイルを apply に渡すと、HTML を作った時点の指紋（本文・根拠・要約）と今の指紋を
  照らし、合うものだけを approve・confirm と同じ関数で書き込む。合わないものは書かずに報告する（見ていないものへの承認を防ぐ）。
  サーバで判断を受ける形にするかは別の問題として残す（構想メモ §16.6）。
- 判断ファイルは保存のたびに判断をすべて含めて書き出すので、古いファイルを後から適用すると判断が巻き戻る。apply は適用したファイルを
  applied.json に記録し、同じファイルと、最後に適用したものより前に保存されたファイルを断る（意図したときだけ --allow-older）。
- 承認者の一覧（approvers）があれば、承認・差し戻し・要約の確認・判断ファイルは一覧の名前でしか書けない。承認の HTML は一覧から選ぶ形になる。
  check は一覧に無い名前の承認を確認待ちとし、マニフェストは承認を種類（human / model）ごとにも数える。一覧が防ぐのは打ち間違いや別名などの
  事故で、悪意は防がない（判断ファイルは誰でも書ける）。
- 承認の HTML には、判断とは別に「指摘」の欄がある。論文への気づきを書く欄で、apply は引用ブロックの「指摘」に足す（承認の指紋には入らない）。
  指摘だけを書いて判断を保留にしてもよい。承認の理由に論文への指摘を書かずに済むようにした（§16.7）。
- check は「網羅」の行に、原稿の出典らしき括弧のうち印の無い文にあるものの数を出す。印の無い引用はこのツールが何も確かめていない。
  「確認待ち 0」や checkpoint は、印のある引用についての状態であって、原稿の引用全体の確認ではない。一覧は coverage で出す。
  パターンは数え方の下限の目安で、括弧を使わない出典は数えない。
- 印の無い出典は、候補として作って人が受け入れる（構想メモ §18）。役割は、道具が拾う・絞る・確かめる・書く、書き手の AI が選ぶ・解釈の欄を書く、
  人が受け入れる。
  1. propose が、印の無い出典の括弧ごとに作業票（`candidates/work.md` と `work.json`）を作る。括弧が受け持つ句（同じ文の前後の出典の括弧の間）、
     書誌の key の候補（括弧と直前の語の名前と年から推す）、同じ文献の既存の抜き書き、原典の文の上位（番号 n つき）を載せる。
  2. 書き手は `candidates/drafts.json`（format `cite-bridge-drafts/1`）に下書きを書く。一件は item、kind（主張・指示・引用でない）、key、
     理由、記入、主張なら excerpts・解釈・原文との差・引用でない句。excerpts の一つは既存の `{"use": "e3"}` か、新しい
     `{"sentences": [n1, n2], "from": "…", "to": "…", "強さ", "要約", "言っていないこと"}`（連続した6文まで。from と to はその中の部分の文字列で省ける）。
     上位の文に無ければ sentences で原典を引く（和文の句と英語の原典では順位付けが効かない）。
  3. propose --load が検査し、通ったものだけを `candidates/candidates.json` に置く。逐語は道具が原典から写す（書き手の文は逐語に入らない）。
     作業票の後に原稿の文か原典のテキストが変わった、key が書誌に無い、範囲が原典で一致しない、のどれかなら断る。
  4. 承認の HTML に候補のカード（左の縁が破線）が原稿の行の順に並ぶ。判断は保留・受け入れる・却下（理由が要る）。
  5. apply が、受け入れた候補を書く。主張なら抜き書き（新しい eN。同じ逐語が既にあれば使う）と引用のブロック（新しい cNNN）を書き、
     原稿の括弧の直後に印を置き、承認と新しい抜き書きの要約の確認を記録する（受け入れは承認を兼ねる）。指示なら引用のブロックと印。
     引用でないなら excluded.json に記録し、網羅の数から外す。候補を作った後に候補か原稿の文が変わっていれば書かない。却下は理由とともに候補に残り、
     次の propose の作業票に出る。
  網羅の数は括弧ごとに見る。括弧の直後に印があれば印のある出典で、同じ文に括弧へ付いていない印が残っていればその数だけ前から印のあるものとみなす。
- md2docx の review_html.py（差分のレビュー）は review --json を読み、本文の〔c003〕に状態の印を付ける。承認の HTML が出力先の隣に
  （既定の名前 cite_review.html で）あれば、印はその引用のカードへのリンクになる。依存は表示 → bridge の一方向で、bridge は表示を知らない。
- review の md 出力は、AI に渡す材料と、HTML を開けない場面のために残す。
- snapshot は h1 から h6 に加えて、折りたたみの見出し（details の summary、Google のヘルプの a.zippy）を小見出しとして拾う。
  見出しの拾い方を直したときは、--rebuild で取得し直さずに写しを作り直せる（取得日とハッシュは元のまま、作り直した日を足す）。
- 写しと OCR の頭書き（`<!-- … -->`）は前後の文から外す。Web の写しでは空行も文の区切りとする。
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
strip、印の形の設定、URL の PDF の写し、LaTeX の \cite と印の key、checkpoint、OCR の印、承認の理由と根拠、差し戻し、
要約の確認、欄の中の参照、review（md と JSON と HTML）、apply（書き込みと指紋の食い違いの拒否）、折りたたみの見出しと作り直し、
網羅の数え方、作業票、候補の検査と受け入れと拒否。31件）。hook は道具の側を直したときに試験も走らせる。

## AI が守ること

- 逐語は抽出テキストか原本から写す。記憶や要約から作らない。
- 判断の欄に書いた者を記入に残す。AI が書いた要約や言っていないことは、人が見るまで候補である。
- 承認（approve）は人の指示があるときだけ行う。AI が自分の書いた引用を承認しない。差し戻しと要約の確認（confirm）も同じ。
  apply は人が承認の HTML で作った判断ファイルを書き込むもので、AI が判断ファイルを作らない。候補の受け入れも同じで、AI は下書きまでを書く。
- 候補の下書きでは、原典と本文がずれていれば、ずれのまま書く（原文との差を外挿にし、解釈と言っていないことに理由を書く）。本文に合わせて読みを寄せない。
- 人に確認を頼むときは review の出力を見せる。手で材料を組むときも、前後の文を補って見せない。OCR の層では頁の画像を見せる。
- 導く欄を手で直さない。おかしければ逐語か抽出テキストを直して derive する。
