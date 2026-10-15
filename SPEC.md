# cite-bridge データ形式の仕様

この文書は、道具が読み書きするファイルの形式の正本である。実装（bridge.py と cite_bridge/）と食い違ったときは、この文書に合わせて実装か文書を直す。
使い方と運用の作法は SKILL.md、設計の経緯は、この道具を作った論文のリポジトリ（thesis）の構想メモ（`notes/構想_AI協調の論文執筆ツールセットと引用ブリッジ_2026-10-10.md`）にある。

- 形式の版: 0.1.0（cite_bridge/config.py の `TOOL_VERSION`）。欄の追加・削除・意味の変更をしたら版を上げ、マニフェストに記録する。
- 文字コードは UTF-8、改行は LF。
- 欄名と値は日本語を正とし、英語の別名も受ける（§10）。内部では日本語にそろえる。

## 1. ファイルと持ち主

| ファイル | 持ち主 | 内容 |
|---|---|---|
| 設定 `bridge/bridge.toml` | 使う側 | パス、書誌の読み方、承認者、印の形（§9） |
| 書誌 | 使う側（keyline / bibtex / csl-json） | key と、原本の PDF・URL への対応 |
| 抜き書き `<excerpts>/<key>.md` | 書き手（欄）と道具（@ 行） | 原典の一箇所ごとの逐語・要約（§2） |
| 引用 `<citations>` | 書き手（欄）と道具（@ 行） | 原稿の一箇所ごとの引用（§3） |
| 抽出テキスト `<text_dir>/<名>.txt`、Web の写し `<web_dir>/<key>.txt` | 道具 | 照合の対象（§8） |
| 判断ファイル、作業票、下書き、候補 | 承認の HTML / 書き手 / 道具 | 人の判断と候補づくり（§5〜§7） |
| `applied.json`、`excluded.json` | 道具 | 適用の記録、引用でないとした括弧（§7） |
| `judgments.jsonl` | 道具 | 分類器の判定の台帳（§6.4） |
| `checkpoints/<UTC>.json` | 道具 | マニフェスト（§8） |

行頭が `@` の行は道具が書く。手で直さない。道具が書く行は二種類ある。導く欄は検査のたびに作り直され、記録の欄（§2.3、§3.3）は消されずに残る。

## 2. 抜き書き

一文献一ファイル。`# <key>` の見出しの下に、`## e1`、`## e2` …（文献の中で一意な ID）のブロックを並べる。
文献の見出しの直下に、道具が `@格` と `@抽出` を書く。

### 2.1 書く欄

| 欄 | 必須 | 値 |
|---|---|---|
| 逐語 | 要 | 原文のまま写した範囲。一行。文体の規約を当てない |
| 強さ | 要 | 観察 / 示唆 / 主張 / 一般化 / 条件付き |
| 要約 | 要 | 確かめた逐語から書く。原文の範囲の外を書かない。他の抜き書きを指すときは ID（`e6`、`key#e6`）で書く |
| 言っていないこと | 要 | 原文が述べていないこと。原文の別の箇所に依るなら、その箇所も抜き書きにして ID で指す |
| 記入 | 要 | 書いた者と日付 |
| 原本での確認 | 近似一致・照合不能のとき | 確認者、日付、頁 |
| 要約の確認 | 任意 | 人が要約・言っていないこと・強さを確かめた記録（者と日付）。`confirm` が書く |

### 2.2 導く欄

照合、所在、節の種類、前、含む文、後、他の文献で一致。

- 照合: 一致 / 正規化で一致 / 正規化で一致（句読点・記号が異なる） / 近似一致（重なり N%） / 照合不能（格）。
  照合は、key に結ばれた抽出テキストの中だけで行う。他の文献での一致は手がかりとして出すだけで、照合には使わない。
- 所在: 頁と節（`PDF 5頁目 / §3.3 …`）。見出しの検出は推定である。
- 節の種類: 序論 / 関連研究 / 方法 / 結果 / 議論 / 限界 / 結論 / 要旨 / 付録 / 参考文献 / 本論（設定で語を足せる）。
- 前・含む文・後: 抽出テキストのまま。補わない。

### 2.3 記録の欄

- `@要約の確認時の指紋`: 要約の確認のときの、抜き書きの指紋（§4）。欄が変わると「確認し直す」と出る。

### 2.4 文献の格

書誌が指す資料と抽出テキストの状態で、道具が決める。

PDF所持（抽出あり）/ PDF所持（OCR の抽出）/ PDF所持（抽出が化けている 等）/ PDF所持（抽出なし）/
Web 写し（保存あり）/ Web 資料（写しなし）/ 未入手 / 書誌に無い。
機械で照合できるのは「抽出あり」と「Web 写し」だけである。OCR の抽出は頭書き `<!-- ocr` で示し、照合は近似一致が多くなる。

## 3. 引用

`# 引用` の見出しの下に `対象: <原稿のパス>` を書き、`## c001`、`## c002` …（原稿の印の ID）のブロックを並べる。
原稿の引用の直後に印を置く（既定は〔c001〕）。印は一つの ID につき一箇所。

### 3.1 書く欄

| 欄 | 必須 | 値 |
|---|---|---|
| 種類 | 要 | 指示 / 主張 |
| 文献 | 指示のとき要 | 書誌の key |
| 抜き書き | 主張のとき要 | `key#e1, key#e2`（カンマ区切り） |
| 理由 | 要 | この引用で何を示すか |
| 解釈 | 任意 | 書き手が足した解釈。原文との差を述べる |
| 人の読み | 任意 | §4 の規則に従う。人が本文へ入れる、原文の語でない読み |
| 人の読みの記入 | 人の読みがあるとき要 | 書いた人と日付 |
| 原文との差 | 主張のとき要 | 一致 / 言い換え / 限定つき一般化 / 外挿 |
| 引用でない句 | 任意 | 引用符の中でも原文の逐語でない句。`／` 区切り、括弧で理由を添える |
| 記入 | 要 | 書いた者と日付 |
| 承認 | 要 | 未 / `<承認者> <日付>` / 差し戻し |
| 承認の理由 | 任意 | 判断の中身 |
| 差し戻しの理由 | 差し戻しのとき要 | |
| 指摘 | 任意 | 原稿そのものへの指摘。判断とは別。指紋に入らない |

外挿は確認待ちとして残り、本文に限定を付けるか自分の主張として書き直すまで解けない。

### 3.2 承認の状態

未承認 / 承認済 / 要再確認 / 差し戻し / 差し戻し後に直された の五つ。道具が §3.3 の記録と現在の指紋を比べて決める。

- 承認済: 承認時の指紋が、現在の本文の指紋と一致し、承認時の根拠の指紋が現在の根拠の指紋と一致する
  （根拠の記録が無い古い承認は本文だけを見る）。
- 要再確認: 承認の後に本文か根拠が変わった。
- 差し戻し: 差し戻し時の指紋と根拠が現在と一致する（書き手がまだ直していない）。一致しなければ「差し戻し後に直された」で、承認を待つ。

### 3.3 記録の欄

`@承認時の指紋`、`@承認時の本文`、`@承認時の根拠`、`@差し戻し時の指紋`、`@差し戻し時の根拠`。承認と差し戻しのときに道具が書く。

## 4. 指紋と、人の読み

指紋は、正規化した文字列の SHA-1 の先頭 8 桁（16 進）である。正規化は、空白をすべて除くことである。

| 指紋 | 対象 |
|---|---|
| 本文の指紋 | 引用を含む文。印と HTML コメントを除く |
| 根拠の指紋 | 抜き書きの ID を整列し、各 `<ID>\t<逐語>` を改行で結んだもの。人の読みがあれば、末尾に `\n人の読み\t<人の読み>` を足す |
| 要約の指紋 | 抜き書きの 逐語・強さ・要約・言っていないこと を改行で結んだもの |

### 4.1 人の読みの規則

人の判断（承認、差し戻し）は人の権限だが、本文に入る読みには抜き書きの錨が要る。原文の語でない読みを、錨なしに本文へ移さない。
人の読みを独立の欄とするのは、書き手の解釈（AI が書く）と、人が自分の責任で足す読みを、記入者と承認の対象で分けるためである。

- 記入者は人である。設定に承認者の一覧があるとき、記入者は種類 human でなければならない。
- 錨が要る。読みの中に、この引用の `抜き書き` に挙げた抜き書きの ID（`e6` または `key#e6`）が一つ以上ある。
  実在しない ID、この引用の抜き書きに無い ID を指す読みは断る。
- 読みは根拠の指紋に入る。承認の後に読みを直すと要再確認に戻る。

## 5. 判断ファイル（`cite-bridge-decisions/1`）

承認の HTML が保存する JSON。`apply` がこれを読んで書き込む。

```json
{"format": "cite-bridge-decisions/1", "manuscript": "<原稿のパス>", "generated": "<HTML を作った時刻>", "by": "<判断した者>",
 "saved": "<保存時刻 ISO>",
 "decisions": [{"id": "c001", "action": "approve | send_back | ''", "note": "理由", "remark": "指摘",
                "fingerprint": "<HTML を作った時の本文の指紋>", "evidence": "<同、根拠の指紋>"}],
 "candidates": [{"id": "<item>", "action": "accept | reject", "note": "理由", "cfp": "<候補の指紋>"}],
 "confirms": [{"id": "key#e1", "fingerprint": "<要約の指紋>"}]}
```

- confirms は、引用の根拠の抜き書きに限らず、どの引用にも使われていない抜き書きも指せる（承認の HTML の「引用に使われていない抜き書き」）。
- 差し戻しと却下は note が要る。
- apply は、HTML を作った時点の指紋が現在と合うものだけを書く（合わなければ読み飛ばして理由を出す）。
- `by` は承認者の一覧に載っていなければならない。一覧に無い名前は断る。

## 6. 候補づくり

印の無い出典を、抜き書きと引用の候補にする。候補の正本は `<candidates>/` に置き、人が受け入れるまで抜き書きと引用のファイルには入れない。

### 6.1 作業票（`cite-bridge-work/1`、`propose` が書く）

`{format, manuscript, generated, items:[{item, line, section, paren, nth, sentence, fingerprint, clause, keys}]}`。
item は「文の指紋・括弧・文の中で何番目の同じ括弧か」から作る ID で、文が変わらない限り変わらない。
keys は key の候補で、書誌との突き合わせ、格、原典の文の上位、同じ文献の既存の抜き書きを持つ。

### 6.2 下書き（`cite-bridge-drafts/1`、書き手が書き `propose --load` が検査する）

`{format, items:[{item, kind, key, 理由, 記入, …}]}`。

- 指示: `kind: 指示`、`key`、`理由`、`記入`。
- 引用でない: `kind: 引用でない`、`理由`、`記入`。受け入れると、その括弧を `excluded.json` に足す（§7）。
- 主張: `kind: 主張`、`key`、`excerpts`、`理由`、`解釈`、`原文との差`、`記入`。
  `excerpts` は要素の並びで、既存の抜き書きは `{use: "e3"}`、新しい抜き書きは
  `{sentences: [a, b], from?, to?, 強さ, 要約, 言っていないこと}`（a から b は原典の連続した 6 文まで）。
  逐語は書き手が書かず、道具が原典の文の範囲から写す。

検査で断る場合: key が書誌に無い、範囲が原典に無い、文の指紋が作業票の後に変わった、原典のテキストが作業票の後に変わった、
写した逐語が原典で一致しない、必須の欄が空。

### 6.3 候補（`cite-bridge-candidates/1`）

`{format, items:{<item>: {item, kind, 理由, 記入, line, section, paren, nth, sentence, fingerprint, key, excerpts, status, loaded, decided}}}`。
status は pending / accepted / rejected。decided は、受け入れたときは `{by, date, cid}`（受け入れた引用の ID）、却下のときは `{by, date, reason}`。

受け入れる（accept）と、新しい抜き書きと引用を書き、承認と要約の確認を同時に記録し、原稿の文に印を置く。
文の指紋が変わっていれば断る。却下（reject）は理由が要り、次の作業票ではその item に `rejected_before` が付く。

## 6.4 分類器による検査

ブリッジの閉じた語彙を、外部の分類器に独立に付けさせ、記録と突き合わせる。印を立てるだけで、承認の状態は変えない。
確からしさ（score）は表示と台帳のためにあり、規則に使わない。

### 型の定義（bridge.toml の `[[checks]]`、既定は judge.py の `DEFAULT_CHECKS`）

| 欄 | 必須 | 内容 |
|---|---|---|
| type | 要 | 型の名前（`cite.diff` 等）。同じ名前の定義は、既定を上書きする |
| version | 要 | 論理的な版 |
| for | 要 | `citation`（引用ごと）か `excerpt`（抜き書きごと） |
| question | 要 | 問いの文面。`{about}` に `about` の文が入る |
| labels | 要 | 閉じた選択肢。「判定できない」を含む |
| gloss | 任意 | ラベルごとの短い説明（分類器の選択肢の文面になる） |
| materials | 要 | 材料の枠 → 欄の指し方。`citation.sentence`、`citation.<欄>`、`excerpt.<欄>` |
| about | 任意 | 判定の対象になる文の欄（例: `excerpt.言っていないこと`） |
| compare | どちらか | 突き合わせる記録の欄。分類器には渡さない |
| flag_on | どちらか | 印にするラベル（記録と比べるものが無いとき） |
| order | 任意 | compare と使う。軽い順のラベルの組（例 `[["一致", "言い換え"], ["限定つき一般化"], ["外挿"]]`）。記録より重い判定だけを印にする |
| on_disagree | 任意 | `flag` のみ（既定）。承認の状態を下げる動作は、まだ無い |

欄の指し方の `excerpt.<欄>` は、抜き書きの 逐語・前・含む文・後・強さ・要約・言っていないこと。`for = excerpt` の型は `citation.*` を使えない。

### 判定の台帳（`bridge/judgments.jsonl`、追記だけ。同じ item と type の後の行が新しい）

```json
{"item": "cite:c007 | exc:key#e1", "type": "cite.diff", "version": 1, "spec": "<型の文面の指紋>", "mat": "<材料の指紋>",
 "label": "外挿", "score": 0.91, "scores": {"一致": 0.02, "…": 0.0}, "record": ["言い換え"], "status": "食い違い",
 "lang": "ja/en", "provider": "jev", "model": "jev-latest", "at": "2026-10-15T10:00:00"}
```

- lang は言語の組（引用は `本文/原典`、抜き書きは原典だけ。下の測定の組と同じ判別）。分岐には使わず、後で言語ごとに数えるために残す。
  言語をまたぐ比較は提供元に任せ、道具は訳さない。
- 判定が新しい（fresh）のは、version・spec・mat が現在と一致するとき。材料か文面が変わると古くなり、`classify` が判定し直す。
- status は、判定時の記録との比較。一致 / 食い違い / 記録より軽い（order を持つ型で、記録より軽い判定） / 判定できない /
  記録なし（compare の欄が空） / 要確認（flag_on に当たる） / 問題なし。order を持つ型では、同じ組のラベルは一致、記録より重い判定が食い違い。
  印は 食い違い と 要確認。現在の記録との比較は `classify --list` と `review` が出す。

### 測定の組（`cite-bridge-eval/1`）と結果（`cite-bridge-eval-result/1`）

```json
{"format": "cite-bridge-eval/1", "note": "…", "types": ["cite.diff"],
 "items": [{"id": "c001", "split": "tune"},
           {"id": "m01", "base": "c001", "split": "tune", "flag": ["cite.diff"], "level": 1, "mutation": "何をどう壊したか", "claim": "壊した本文の文"},
           {"id": "m01.en", "twin": "m01", "claim": "同じ内容を別の言語で書いた本文"}]}
```

- id だけの件は承認済みの引用で、types のどの型でも印が立たないのが正しい。
- flag を持つ件は改変で、base の引用の本文を claim に置き換えた試験の件である。flag に挙げた型で印が立つのが正しい（挙げない型は数えない）。
  材料のほかの部分（逐語、前後の文、記録）は base のものを使う。claim は原稿にも引用のファイルにも入らない。
- evidence（抜き書きの ID の並び）と record（記録の欄、例 `{"原文との差": "言い換え"}`）は、base の材料を差し替える（任意）。
  base が無く evidence だけを持つ件は、引用の無い文（実際に見つかった誤りの当時の文など）を、その抜き書きと突き合わせる。
  evidence には、どの引用にも使われていない抜き書きも使える。
- level は改変の難しさ（任意）。結果を難しさと言語の組ごとにも数える。段の意味は組の note に書く。
- twin を持つ件は、twin の件と同じ内容を別の言語で書いた本文（claim）だけを持ち、base・split・flag・level・mutation を twin の件から引き継ぐ。
  元が承認済みなら base は元の id。同じ内容で言語だけが違う組の印の立ち方を比べ、違った組を出す。
- 結果は、行ごとに `{variant, rep, item, split, lang, level, twin, type, label, status, record, margin, flagged, expected, ok, mutation}`。
  margin は確からしさの一位と二位の差で、曖昧さの目安として残す（規則には使わない）。台帳には書かない。
- lang は本文と原典の言語の組（`本文/原典`、例 `ja/en`。根拠の逐語が複数の言語にまたがれば `ja/en+ja`）。仮名か漢字を含む文は ja、
  欧字だけの文は en（英語以外の欧文も en に数える）。測定の組には書かず、道具が判別する。
- `citation.出典` は、根拠の文献の筆頭著者と年（書誌から導く）。問いの中で、文のどの部分を見るかを名指すのに使う。

### アダプタの契約（`cite_bridge/classifier.py`）

`classify(state, asks) -> list[Verdict | None]`。state は共通の材料の文面、asks は同じ state に対する互いに独立な問い。
Verdict は label（labels のどれか）、score（Optional）、scores（全ラベル）。答えられなかった問いは None、呼び出し全体の失敗は
`ClassifierUnavailable`（判定を何も書かない）。鍵は環境変数だけで受け、設定ファイルには書かない。外へ送るのは `classify --send` のときだけ。

## 7. 適用の記録

- `applied.json`: `{<原稿>: {last_saved, files:[{file, saved, sha256, by, applied, written, skipped, note?}]}}`。
  同じファイルと、最後に適用したものより前に保存されたファイルを、apply は断る（`--allow-older` で意図して適用できる）。
- `excluded.json`: `[{item, paren, nth, fingerprint, …}]`。人が「引用でない」とした括弧。網羅の数に入れない。

## 8. マニフェスト（`cite-bridge-manifest/1`）

`check --strict` を通った地点で `checkpoint` が書く。

```json
{"format": "cite-bridge-manifest/1",
 "tool": {"name": "cite-bridge", "version": "0.1.0", "sha256": "<道具のソースの指紋>", "commit": "<道具のフォルダの最終コミット | null>", "dirty": false},
 "checkpoint": "<UTC 時刻>", "label": "",
 "git": {"head": "<HEAD>", "uncommitted": ["…"]},
 "files": {"config": {"path", "sha256"}, "bibliography": {…}, "manuscript": {…}, "citations": {…},
           "excerpts": {"<path>": "<sha256>"}, "texts": {"<path>": "<sha256>"}},
 "excerpts": {"total": 0, "match": {}, "grade": {}},
 "citations": {}, "approvers": {}, "approver_kinds": {}, "coverage": {}, "summary_checks": {},
 "classifier": null}
```

`tool` は、どの版の検査で通ったかを残す。sha256 は、道具のソース（bridge.py と cite_bridge/ の下の .py・.html・.js）の相対パスと内容の sha256 を、パスの順に並べてもう一度 sha256 にかけたもの。別のリポジトリから道具を使っても、使う側から版が分かる。`classifier` は、分類器を設定せず台帳も無ければ null。あれば `{provider, model, types:[{type, version, spec}], judgments, flagged, note}`（§6.4）。

## 9. 設定（bridge.toml）

SKILL.md の「設定」の節にひな形がある。表は鍵の一覧である。

| 表 | 鍵 | 内容 |
|---|---|---|
| bibliography | path, format, files_field, pdf_pattern, web_pattern | 書誌のパス、読み方（keyline / bibtex / csl-json）、PDF と Web の見分け方 |
| sources | pdf_dir, text_dir, web_dir | 原本、抽出テキスト、Web の写しの置き場 |
| bridge | excerpts, citations, checkpoints, applied, candidates, excluded | データの置き場 |
| manuscript | mark_pattern, mark_format, quote_patterns, not_quote_separator, sentence_end, paragraph | 原稿の印と文の規則 |
| output | language | 導く欄の名前を書く言語（ja / en） |
| section_kinds | <種類> = [語] | 節の種類の語を足す |
| detect | common_words | 抽出が読めるかを見る頻出語を足す |
| approvers | <名前> = human / model | 承認できる者と種類。省くと名前を問わない |
| coverage | pattern | 出典らしき括弧の正規表現 |
| hook | watch | pre-commit が監視する、設定が指す以外のパス |
| classifier | provider, model, endpoint, max_chars, types | 分類器の提供元と上限（§6.4）。鍵は環境変数 |
| checks（配列） | type, version, for, question, labels, … | 問いの型の追加と上書き（§6.4） |

## 10. 英語の別名

| 日本語 | 英語 | 日本語 | 英語 |
|---|---|---|---|
| 逐語 | verbatim | 人の読み | human_reading |
| 強さ | strength | 人の読みの記入 | human_reading_by |
| 要約 | summary | 原文との差 | diff |
| 言っていないこと | not_said | 引用でない句 | not_quotes |
| 記入 | written_by | 承認 | approval |
| 原本での確認 | source_check | 承認の理由 | approval_note |
| 種類 | kind | 差し戻しの理由 | returned_reason |
| 抜き書き | excerpts | 要約の確認 | summary_check |
| 文献 | source | 指摘 | remarks |
| 理由 | reason | 解釈 | interpretation |

値の別名: 強さ（observation / suggestion / claim / generalization / conditional）、種類（pointer / claim）、
原文との差（identical / paraphrase / qualified_generalization / extrapolation）、承認（none = 未、returned = 差し戻し）。
導く欄と記録の欄の名前の対応は cite_bridge/config.py の `FIELD_ALIASES` にある。

## 11. 版の方針

- 欄を足す（既存のファイルが検査を通る）: 副版を上げる。
- 欄の意味・指紋の作り方・判断ファイルの形を変える（既存のファイルの状態が変わる）: 主版を上げ、移行の手順を書く。
  例: 0.1.0 の時点で、人の読みを根拠の指紋に含める。人の読みを含む承認は、読みを直すと要再確認になる。
- 判断ファイル・作業票・下書き・候補・マニフェストは、形式の名前の末尾（`/1`）が版である。形を変えたら番号を上げ、古い番号は断る。
