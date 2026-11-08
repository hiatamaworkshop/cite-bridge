---
name: cite-bridge
description: 引用ごとにアンカー（原典の逐語と、道具が導いた所在）を持たせ、その確認の状態を執筆中ずっと正しく保つ。抜き書き（原典の一箇所）と引用（原稿の一箇所）を決まった欄の md で書き、bridge.py が所在・前後の文・節の種類・照合の段階を導いて検査する。原典の抜き書きを足すとき、原稿に引用を足すとき、提出前に引用の確認状態を見るときに使う。
---

# 引用ブリッジ

English: [SKILL.en.md](SKILL.en.md)（正本はこの日本語の版で、英語の版は訳である）

この文書は、道具を使う人と AI の作法とコマンドである。何をする道具かは `README.md`、データの形（欄、指紋、判断ファイル、マニフェスト等）の正本は `SPEC.md`。
使う側のリポジトリでは、道具を `tools/cite-bridge/` に置く（submodule）。以下のコマンド例はこの置き場所を前提にしている。別の場所に置いたときはパスを読み替え、hook には環境変数 `CITE_BRIDGE` で場所を教える（「hook」の節）。
この文書は普通の Markdown で、どのエージェントも人も読める。頭の name と description は、エージェントの skill として置くとき（例: `.claude/skills/cite-bridge/`）の入口で、それは置き方の一つである。

## 保証と持ち主

- アンカーの実在と所在は、このスクリプトが保証する（抽出テキストとの照合）。
- 主張を原典が支えているかは、承認した者の判断による。誰が承認したか（人か、どの系統のモデルか）を記録する。既定では人の承認だけを数え、承認者の一覧で model の者の承認は記録に残るが、
  承認済に数えず確認待ちになる。設定の `count_model = true` では、書き手と独立なモデルの承認も数える（後の「承認者の一覧」の段）。原本での確認と要約の確認は、書き手と系統の違うモデルにも委ねられる（同じ系統のモデルの確認は数えない）。
- 確認が古くなっていないことは、本文の指紋が保証する。承認の後に文が変われば要再確認へ戻る。

## 書く欄と導く欄

人か AI が書くのは判断の欄だけである。`@` で始まる行はスクリプトが書く。手で直さない。

抜き書き `bridge/excerpts/<key>.md`（文献ごとに一ファイル。見出しは書誌リストの key）

```
# smith2020

## e2
逐語: Users can revise an earlier answer by navigating back to a given question. Upon detecting such a revision, the system removes all subsequent question-answer pairs.
強さ: 観察
要約: 特定の質問へ戻って回答を修正すると、それ以降の質問と回答の対がすべて削除される。
言っていないこと: 未来の質問を指名できないとは書いていない。
記入: Claude 2026-01-01
@照合: 正規化で一致
@所在: PDF 5頁目 / §3.3 Dialogue Flow
@節の種類: 本論
@前: …
@後: …
```

- 書く欄：逐語、強さ（観察／示唆／主張／一般化／条件付き）、要約、言っていないこと、記入（書いた者と日付）。
  要ヒューマンチェックの印（`@要ヒューマンチェック`）が付いた抜き書きは、原本での確認を `confirm --source` で記録する（欄を手で書かない。下の「要ヒューマンチェック」）。
  確認者が分からない記録は確認として数えない。
- 要約には原文の範囲の外を書かない。自分の読みは引用の側の解釈に書く。
- 言っていないことや解釈が原文の別の箇所に依るなら、その箇所も抜き書きにして ID（同じ文献なら `e6`、別の文献なら `key#e6`）で指す。
  「同じ頁にある」とだけ書いて指さない形は、未検証の主張が混ざる経路になる。check は指した ID が実在するかを検査する。
- 要約は抽出テキストではなく、確かめた逐語から書く。抽出テキストの誤読を補って要約に入れない。
- 逐語が文の途中で切れているとき、導く欄の「含む文」が原文の文全体を示す。逐語の外側にある限定（「…が考えられる」「without critical reflection」等）を
  見落とさないよう、要約と言っていないことはこれを見て書く。
- 人が要約・言っていないこと・強さを原文と照らしたら `confirm` で記録する（`要約の確認` と、そのときの指紋）。
  確認の後に欄が変われば check が「確認し直す」と出す。未確認の件数は check の INFO に出る（--strict では止めない）。
- 逐語は原文のまま写す。文体の規約（エムダッシュを使わない等）は逐語の欄に当てない。
- 一つの欄は一行に書く。
- 導く欄：照合、所在（頁と節）、節の種類、前、後、含む文。文献の見出しの下に格と抽出テキストの場所。
  節が誤って導かれたら、抽出テキストの見出しの行を確かめる（見出しの検出は推定である）。

引用 `bridge/citations.md`（原稿ごとに一ファイル。原稿の引用の後に〔c001〕の印を置く）

```
# 引用
対象: manuscript.md

## c001
種類: 主張
抜き書き: smith2020#e2
理由: §2.4 で、戻って直すと以降の質問と回答が削除される仕様を、先行システムの制約として引く
解釈: …
原文との差: 言い換え
記入: Claude 2026-01-01
承認: 未
```

- 種類は 指示（作品の名前や存在を挙げるだけ。`文献: <key>` を書く）か 主張（原典の内容を述べる。抜き書きが要る）。
  指示で要るのは書誌にある `文献` の key だけで、理由・記入・承認は求めない（書けば review に出るが、無くても確認待ちにならない）。
  以下の承認・人の読み・原文との差は、主張の引用についての規則である（SPEC.md §3.1）。
- 承認の状態と、どの指紋が変わると要再確認に戻るかは SPEC.md §3.2。差し戻しは理由を `差し戻しの理由` に残し、書き手が本文か根拠を直すと承認を待つ。
- 人の読み（原文の語でない読みを、人が本文へ入れるとき）は、書き手の解釈とは別の欄 `人の読み`、`人の読みの記入`（書いた人と日付）に書く。
  AI は書けない（設定の承認者の一覧で human でない者の記入は断る）。読みの中に、この引用の抜き書きの ID（`e6`、`key#e6`）を書いて、根拠の抜き書きを示す。
  読みは根拠の指紋に入るので、承認の後に直すと要再確認に戻る（SPEC.md §4.1）。人の判断（承認、差し戻し）は別である。
- 原文との差は 一致／言い換え／限定つき一般化／外挿。外挿は確認待ちとして残り、本文に限定を付けるか自分の主張として書き直すまで解けない。
- 本文の引用符の中の文字列は、指している抜き書きの逐語に含まれていなければならない（言語が違う引用は訳とみなして外す）。
  引用符の中でも原文の逐語でない句（コマンドの型の一つの言い方、UI の文字列の一例等）は、ブロックの「引用でない句」に
  ／区切りで挙げ、括弧で理由を添える。外すかどうかは人の判断で、機械は挙げられた句だけを外す。
- 引用一件の本文は、印を含む文である。鉤括弧の中の。では文を切らない。HTML コメントは文の判定と指紋から除くので、
  コメントだけを直しても要再確認にはならない。コメントの中の印は数えない。
- 印〔c001〕は原稿に残る。提出物を作るときは `strip` で印を外した写しを作り、それを変換に渡す。

## 要ヒューマンチェック（原本での確認）

照合が近似一致か照合不能の抜き書き、OCR の抽出や OCR の文字の層の抜き書き、逐語の範囲に読めない字がある抜き書き、短い逐語（欧文 3 語以下・和文 10 字以下）の抜き書きは、機械では逐語の実在を保証できない。
道具はそれに `@要ヒューマンチェック`（理由を「、」で結んだもの）を付け、原本で確かめた記録が無ければ check が NOTE を出す。
理由は「照合が近似一致」「照合で見つからない」「照合不能（格）」「OCR の抽出」「OCR の文字の層」「逐語の範囲に読めない字」「逐語が短い」のどれか。
この印は確認の記録に依らず残る。済んだかは `原本での確認` の記録で決まる。頁の区切りのずれ（抽出の診断 2）は要ヒューマンチェックの理由にしない。

- 確かめる材料は `review --source-checks`（md。`--images DIR` で頁の画像を添える）。外の AI に渡すなら `review --source-checks --json -o 依頼.json`（format `cite-bridge-source-checks/1`）。
- 記録は `confirm <key#eN> --source --by <名前> [--result 一致|違う] [--page "p.49 §4・3"] [--note …]`。違うのときは --note に原本の字を書く。
  外の AI が答えたら、その判断ファイルの `source_checks` を `apply` で書く（逐語の指紋が今と合うものだけ書く）。
- 記録が有効であるのは、確認者が承認者の一覧にあり、model なら抜き書きの書き手と独立で（名前が違い、一覧に系統があり、書き手が一覧にあって系統が違う。SPEC.md §2.1 の条件 3）、逐語の指紋が今と合い、結果が一致のとき。
- 逐語を直すと記録は有効でなくなる。直すのは書き手で、道具は直さない。違うと報告された逐語も、書き手が直して確かめ直す。

委ねる場合の決まり。

1. 要ヒューマンチェックの依頼は、人が外部の AI に委ねてよい。委ねるかを決めるのは人で、委ねる AI を承認者の一覧に `model:<系統>` として載せるのも人である。
2. 委ねた AI は、依頼の JSON を受け取り、その名前で判断ファイルを書く。人がそれを `apply` に渡す。
3. 書き手の AI（抜き書きを記入したモデル）と同じ系統の AI は、その抜き書きの原本での確認を記録できない。系統の分からない AI も記録できない。
4. 誰が確かめたかは、記録の確認者と、マニフェストの確認者の種類ごとの数に残る。最終の提出（`checkpoint --by <人>`）は人が出す。
5. 道具は外部の AI を呼ばない。依頼の JSON を書き出し、判断ファイルを受け取るだけである。

## 確認と承認

- 確認待ちには、未承認・要再確認・差し戻しの引用に加えて、承認済でも根拠の要約が未確認の引用も入る（要約の確認の欄は引用のカードにしか無いため）。
- review は、本文、根拠の逐語、所在、照合、原本での確認、前後の文、AI の候補（要約・言っていないこと）、引用の欄、判断のコマンドを
  この順に並べる。逐語を先に読ませ、AI の候補で判断が引っ張られないようにする。前後の文は抽出テキストのままで、誤読を補わない。
  近似一致・照合不能・OCR の根拠では「頁の画像で読む」と出し、--images を渡せば PDF の該当頁を PNG にする。
  review の md 出力は、AI に渡す材料と、HTML を開けない場面のために残す。
- 人が見て判断する画面は、review --html が作る承認の HTML である（単体で開ける一枚。頁の画像も埋め込む）。
  引用ごとのカードで、保留・承認・差し戻しと理由、要約を確かめた印を入れる。入力はブラウザに一時保存され、最後に判断ファイル（JSON）として保存する。
  HTML は何も書き込まない。判断ファイルを apply に渡すと、HTML を作った時点の指紋（本文・根拠・要約）と今の指紋を照らし、
  合うものだけを approve・confirm と同じ関数で書き込む。合わないものは書かずに報告する（見ていないものへの承認を防ぐ）。
- 判断ファイルは保存のたびに判断をすべて含めて書き出すので、古いファイルを後から適用すると判断が巻き戻る。apply は適用したファイルを
  applied.json に記録し、同じファイルと、最後に適用したものより前に保存されたファイルを断る（意図したときだけ --allow-older）。
- 承認者の一覧（approvers）があれば、承認・差し戻し・要約の確認・判断ファイルは一覧の名前でしか書けない。承認の HTML は一覧から選ぶ形になる。
  check は一覧に無い名前の承認を確認待ちとし、マニフェストは承認を種類（human / model）ごとにも数える。一覧が防ぐのは打ち間違いや別名などの
  事故で、悪意は防がない（判断ファイルは誰でも書ける）。
- 既定では、一覧で model の者の引用の承認は、記録に残るが承認済に数えず、review と承認の HTML の確認待ちに未承認として出る（数え方の全部は SPEC.md §3.2）。
  そこには model の承認の理由と、承認したときの本文と根拠が今と合うかも出るので、人の承認の材料にする。承認の理由は、人が読んで判断できるように書く。
  人の承認が今と合う引用には、model の者の承認は書けない（断る）。
- 設定の `[approval] count_model = true` では、書き手と独立なモデル（SPEC.md §2.1 の条件 3。引用と根拠の抜き書きのすべての書き手と比べる）の承認を承認済に数える。
  独立でないモデルの承認は、今と同じに数えない。check の承認済の数と、review と承認の HTML の状態に、承認者の種類（人 / model と系統）が出る。
- 承認の HTML の末尾に「引用に使われていない抜き書き」の一覧が出る（どの引用も根拠にしておらず、要約を確かめていないもの）。
  引用のカードに出ないので、要約・言っていないこと・強さを原文と照らして印を付けるのはここである。引用に使い始めたら、その引用の承認で改めて見る。
- 承認の HTML には、判断とは別に「指摘」の欄がある。原稿への気づきを書く欄で、apply は引用ブロックの「指摘」に足す（承認の指紋には入らない）。
  指摘だけを書いて判断を保留にしてもよい。原稿への指摘はこの欄に書き、承認の理由には混ぜない。
- 外の表示（差分のレビューなど）は review --json を読んで、本文の印に状態を出せる。依存は表示 → bridge の一方向で、bridge は表示を知らない。

## 印の無い出典

- check は「網羅」の行に、原稿の出典らしきもの（括弧の数を併記）のうち、印の無いものの数を出す。印の無い引用はこのツールが何も確かめていない。
  「確認待ち 0」や checkpoint は、印のある引用についての状態であって、原稿の引用全体の確認ではない。一覧は coverage で出す。
  パターンは数え方の下限の目安で、括弧を使わない出典は数えない。網羅は出典ごとに数え（括弧の中を「;」「；」で分ける）、頁だけ・同書の括弧は前の出典の繰り返しとして一件に数える。
- 印の無い出典は、候補として作って人が受け入れる。役割は、道具が拾う・絞る・確かめる・書く、書き手の AI が選ぶ・解釈の欄を書く、
  人が受け入れる。
  1. propose が、印の無い出典の括弧ごとに作業票（`candidates/work.md` と `work.json`）を作る。括弧が受け持つ句、書誌の key の候補、
     同じ文献の既存の抜き書き、原典の文の上位（番号 n つき）を載せる。
  2. 書き手は `candidates/drafts.json`（format `cite-bridge-drafts/1`。形は SPEC.md §6.2）に下書きを書く。抜き書きは既存のものを指すか、
     作業票の文の番号で原典の範囲を指す。上位の文に無ければ sentences で原典を引く（和文の句と英語の原典では順位付けが効かない）。
  3. propose --load が検査し、通ったものだけを `candidates/candidates.json` に置く。逐語は道具が原典から写す（書き手の文は逐語に入らない）。
  4. 承認の HTML に候補のカード（左の縁が破線）が原稿の行の順に並ぶ。判断は保留・受け入れる・却下（理由が要る）。
  5. apply が、受け入れた候補を書く。主張なら抜き書きと引用のブロックを書き、原稿の括弧の直後に印を置き、承認と新しい抜き書きの要約の確認を記録する
     （受け入れは承認を兼ねる）。指示なら引用のブロックと印。引用でないなら excluded.json に記録し、網羅の数から外す。
     候補を作った後に候補か原稿の文が変わっていれば書かない。却下は理由とともに候補に残り、次の propose の作業票に出る。
- propose の絞り込み。`--key <key>`（何度でも）は、key の候補（上位3件と --add-key）にその key がある出典だけを作業票にする。
  `--checkable` は、key の第一候補が機械で照合できる格（PDF の抽出あり・Web 写しあり）の出典だけにする。repeat の件は `--checkable` で外れる。絞り込みは --limit で切る前に行う。

## hook

整合の検査を git の pre-commit に置く。検査の本体は `bridge.py precommit` で、何を監視するかは設定（bridge.toml）が決める。
ステージしたものが、原稿・書誌・抜き書き・引用・抽出テキスト・Web の写し・設定ファイル・道具のフォルダのどれかに当たるときだけ
check を走らせ、整合の崩れ（ERROR）があるときだけコミットを止める。確認待ち（NOTE）では止めない（提出前は `check --strict`）。
道具が使う側と同じリポジトリにあるときは、道具のフォルダをステージしたとき（道具を直したとき）に tests の試験も走らせる。
道具が別のリポジトリ（submodule）のときは、試験は道具のリポジトリの `.githooks/pre-commit` が走らせる（clone ごとに `git config core.hooksPath .githooks`）。
検査するのは作業ツリーで、ステージした内容そのものではない。

- 入れ方。道具に同梱の `hooks/pre-commit`（sh の数行）を、使うリポジトリの `.githooks/pre-commit` に置き、
  `git config core.hooksPath .githooks` で有効にする（clone し直したら設定し直す）。
  hook は sh で動くので、`.gitattributes` で `.githooks/* text eol=lf` にして改行変換を止める。
- 道具の場所は環境変数 `CITE_BRIDGE`（bridge.py のパス）で替える。既定は `tools/cite-bridge/bridge.py` で、そこに無ければ前の既定の `.claude/skills/cite-bridge/bridge.py` を見る。
  無ければ警告して検査を飛ばす（コミットは止めない）。
- 設定以外のパスも監視したいときは `[hook] watch = ["…"]`。

## 設定

道具は、使う論文のパスや書誌の書き方を知らない。すべて設定ファイル（既定は `bridge/bridge.toml`、`--config` で替える）から受け取る。

```toml
[bibliography]
path = "bib/bibliography.md"
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
[approvers]                                      # 承認できる者と種類（human / model:<系統>）。省くと名前を問わない
# alice = "human"
# claude-opus-5-5 = "model:anthropic"            # モデルには系統（提供元）を書く。抜き書きと引用の書き手も載せる
[approval]
# count_model = false                            # true なら、書き手と独立なモデルの引用の承認も承認済に数える
[coverage]
# pattern = '…'                                  # 出典らしき括弧（既定は年を含む括弧）。印の無い文にあるものを数える
# repeat_pattern = '…'                           # 頁だけ・同書の括弧（既定は「（同書…）」「（同）」「（p.49）」等）。出典でなく、前の出典の繰り返しとして一件に数える
[hook]
# watch = ["extra/dir"]                          # pre-commit が監視する、設定が指す以外のパス
```
（[bridge] には applied、candidates、excluded、judgments も置ける。適用した判断ファイルの記録、候補の作業のフォルダ、引用でないと判断した括弧の記録、分類器の判定の台帳で、
既定は citations と同じフォルダの applied.json、candidates/、excluded.json、judgments.jsonl。--citations で引用のファイルを替えると、明示していないものはそのフォルダに置く。
抜き書きとチェックポイントは替わらず、候補を受け入れたときの印は引用のファイルの 対象 が指す原稿に書く。写しで試すときは原稿も写して 対象 を向ける）

- LaTeX では印を \cite の直後のコメントに置く（組版に影響しない）。例 `\cite{doe2020}%c017`。設定は
  `mark_pattern = '\\cite\{(?P<key>[^}]+)\}(?P<strip>%(?P<id>c\d+))'`、`paragraph = "blank"`、英語の sentence_end。
  名前つきのグループ id が ID、key があれば印の key と根拠の文献が合うかも検査し、strip があれば strip と指紋はその部分だけを外す。
- 欄の名前と値は英語でも書ける（verbatim, strength: observation, not_said, written_by, kind: claim, excerpts, diff: paraphrase 等。
  対応は cite_bridge/config.py の FIELD_ALIASES と VALUE_ALIASES）。内部では日本語の名前にそろえる。出力の文はいまは日本語だけである。

## コマンド

リポジトリの根で実行する。

```
python tools/cite-bridge/bridge.py derive          # 導く欄を書き直す
python tools/cite-bridge/bridge.py check           # 整合の崩れがあれば exit 1
python tools/cite-bridge/bridge.py check --strict  # 確認待ちが残っていても exit 1（提出前）
python tools/cite-bridge/bridge.py grade --keys-from <key を含む md>
python tools/cite-bridge/bridge.py review [c001 ...] [--images DIR] [-o 出力.md]  # 確認用の一覧（省くと確認待ちすべて）
python tools/cite-bridge/bridge.py review --json --all [--images DIR]          # 外の表示へ渡す JSON（承認済と指示も含める）
python tools/cite-bridge/bridge.py review --html -o preview/cite_review.html     # 承認の HTML（人が見て判断する画面）
python tools/cite-bridge/bridge.py apply <判断ファイル.json> [--dry-run]          # 承認の HTML が保存した判断を書き込む
python tools/cite-bridge/bridge.py apply --latest [--from DIR] [--dry-run]       # ダウンロード（既定）の最新の判断ファイルを使う
python tools/cite-bridge/bridge.py coverage                                     # 印の無い文にある出典らしき括弧の一覧
python tools/cite-bridge/bridge.py propose [--section 2.2] [--lines 80-120] [--limit 15] [--add-key ITEM=KEY]  # 印の無い出典の作業票
python tools/cite-bridge/bridge.py propose [--key smith2020 ...] [--checkable]  # key の候補に当たる出典だけ／機械で照合できる格の第一候補の出典だけ（repeat は --checkable で外れる）
python tools/cite-bridge/bridge.py sentences <key> [--grep 語 ...] [--range 40-50]   # 原典を作業票と同じ番号の文で引く
python tools/cite-bridge/bridge.py propose --load bridge/candidates/drafts.json     # 書き手の下書きを検査して候補にする
python tools/cite-bridge/bridge.py approve c001 --by 人 [--note 理由]
python tools/cite-bridge/bridge.py approve c001 --by 人 --send-back --note 理由   # 差し戻し
python tools/cite-bridge/bridge.py confirm smith2020#e2 --by 人            # 要約の確認
python tools/cite-bridge/bridge.py confirm smith2020#e2 --source --by 人 [--result 違う] [--page "p.49 §4・3"] --note "…"  # 原本での確認（要ヒューマンチェック）
python tools/cite-bridge/bridge.py review --source-checks [--json] [--images DIR] [-o 出力]  # 原本での確認が残る抜き書きの一覧（--json は外の AI への依頼）
python tools/cite-bridge/bridge.py --citations <別の引用ファイル> check   # 原稿が複数あるとき、写しで試すとき
python tools/cite-bridge/bridge.py extract [<key> ...] [--force]  # 原本の PDF から抽出テキストを作る（pymupdf。頭書きつき）
python tools/cite-bridge/bridge.py extract [<key> ...] --header-only  # 頭書きの無い古い抽出テキストに頭書きを足す（本文は変えない）
python tools/cite-bridge/bridge.py snapshot <key> [<URL>]       # Web 資料の写し（既定は書誌の行の URL）
python tools/cite-bridge/bridge.py snapshot <key> --rebuild     # 保存した生の HTML から本文を作り直す（取り直さない）
python tools/cite-bridge/bridge.py strip <原稿> <出力>            # 印を外した写しを作る
python tools/cite-bridge/bridge.py checkpoint [--label 中間提出] [--by 人]   # check --strict を通った地点をマニフェストで残す（道具の版つき）。承認者の一覧があるときは --by（human）が要る
python tools/cite-bridge/bridge.py precommit                       # git の pre-commit から呼ぶ（hook 節）
python tools/cite-bridge/bridge.py classify [--send] [--list [--all]] [--cids c001 ...] [--limit N]   # 分類器による検査（docs/classifier.md。--send が無ければ送らない）
python tools/cite-bridge/bridge.py classify --eval <組.json> --variant <案.toml> [--types 型 …] [--reps 2] [--send]   # 文面の測定（台帳に書かない）
```

- snapshot は生の HTML を `<web_dir>/<key>.html`（追跡しない）に、本文を `<key>.txt`（追跡する）に保存する。所在は「Web 写し（取得日） / 見出し」になる。
  写しは取得した時点のものとして残る。取り直すと日付が変わり、照合も導き直される。
- OCR は道具に入れない。OCR で作ったテキストは、頭に `<!-- ocr` で始まる頭書き（エンジン、日付）を置いて `<text_dir>/<PDF と同じ名>.txt` に置く。
  格は「PDF所持（OCR の抽出）」になり、機械で照合できる範囲には数えない。誤読があるので、照合は近似一致が多くなる。
- grade は書誌の key ごとに格を出す。`--keys-from` に対応表を渡すと、表の key 列にあって書誌に無い key（改名の取り残し等）も出す。
- checkpoint は、整合の崩れも確認待ちも無いときだけ `bridge/checkpoints/<UTC 時刻>.json` を書く（中身は SPEC.md §8）。

## AI が守ること

- 逐語は抽出テキストか原本から写す。記憶や要約から作らない。
- 判断の欄に書いた者を記入に残す。AI が書いた要約や言っていないことは、人が見るまで候補である。
- 承認（approve）は、人の指示があるときか、人が承認を委ねたとき（`count_model = true` で、承認者の一覧に `model:<系統>` として載った書き手と独立な AI）だけ行う。
  AI は、自分か同じ系統の AI が書いた引用を承認しない。差し戻しと要約の確認（confirm）も同じ。
  apply は判断ファイルを書き込む。判断ファイルを作るのは、承認の HTML を使う人か、人が委ねた書き手と独立な AI である。候補の受け入れも同じで、書き手の AI は下書きまでを書く。
- 候補の下書きでは、原典と本文がずれていれば、ずれのまま書く（原文との差を外挿にし、解釈と言っていないことに理由を書く）。本文に合わせて読みを寄せない。
- 人に確認を頼むときは review の出力を見せる。手で材料を組むときも、前後の文を補って見せない。OCR の層では頁の画像を見せる。
- 導く欄を手で直さない。おかしければ逐語か抽出テキストを直して derive する。
- 書き手の AI は、自分の書いた抜き書きと引用について、原本での確認・要約の確認・承認を記録しない（道具も、書き手と独立でない model の確認者について断る）。
- 原本での確認の欄を手で書かない（`confirm --source` か `apply` を通す。指紋が要る）。
- 外部の AI に委ねるかを決め、その AI を承認者の一覧に載せるのは人である。
