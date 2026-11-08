# ロードマップ

開いている項目は末尾の「項目」に `### C<n>. 題` の節で書く。
- 見出しの直後に、例外の状態だけ `状態: 提案 | 保留(理由) | ブロック(理由)` を字下げせずに 1 行書く。行がなければ決定 (着手してよい)。
- 決定の項目は `#### 完了条件` (チェックボックスの並び) を持つ。依頼の `DONE WHEN` はここから写す。文言を変えるのは約束の変更なので、実装中は変えず、報告で提案する。
- 決定の項目は `## 予定` に、取りかかる順で `- [ ] C<n>` と並べる。提案と保留は載せない。
- 番号は使い回さない。終わったら節を消し、版の行を `[x] C<n> …` にして、確かめた記録をその下に書く。その項目を待つ `ブロック(C<n> の後)` の行も同じ片付けで外す (状態は進捗で、約束ではない)。
- 却下したら節を消し、`[-] C<n> 題 (却下 YYYY-MM-DD、理由 1 行)` を残す。
- 規則の検査は agent-hub の `npm run docs:check -- <この文書の絶対パス>`。

## 0.3.0: 要ヒューマンチェック、抽出の頭書き、孫引き、出典ごとの網羅

設計は [design-0.3.0.md](design-0.3.0.md)。項目の順は C1 → C2 → C3、C4 → C5、C6、最後に C7。

- [x] propose の `--key` と `--checkable` (設計 §8.2。c75ec03)
- [x] Web 資料の書誌の参照日と写しの取得日を check で比べる (設計 §8.3。c358d27)
- [x] C1 抽出の頭書きと抽出の診断 (2026-10-22、設計 §4)
  - 確かめた記録（2026-10-22）:
    - 試験: `python -m pytest -q tests` が 84 件すべて通る（既存の 72 件と、tests/test_extraction.py の 12 件。§4.6 の 1〜7 を含む）。
    - 実データ（利用者の原稿のリポジトリ、読むだけ）: check は ERROR 7 件がすべて「導く欄（文献）が古い」（derive を走らせていないため。頭に抽出の診断の欄が増えた）。NOTE 7 件は「頭書きが無い」。grade は 105 件のうち機械で照合できるもの 45 件（前と同じ）。coverage・classify --list・review -o は最後まで走り、数は前と同じ。
    - OCR の文字の層: references の PDF 56 件を §4.2 の規則で走査し、当たったのは 7 件（設計の 7 件と一致）。
    - 未確認: `extract --header-only` を実データに当てること。原稿のリポジトリでは extract を走らせない決まりで、コピーで試す手は権限の判定で止まった。
    - 設計の変更: §4.4 の 2（頁の区切り）は、頭書きの pages が Source.pages() とも、改ページ文字 `\f` の数 + 1 とも違うときに診断する規則に書き直した（利用者が 2026-10-22 に承認）。最後の頁が空の PDF（work_efficiency）が、Source.pages() だけで比べると extract --force でも直らない NOTE になるため。
- [x] C2 要ヒューマンチェックと原本での確認の記録 (2026-10-22、設計 §5.1〜§5.4、§5.6、§5.8)
  - 確かめた記録（2026-10-22）:
    - 試験: `python -m pytest -q tests` が 96 件すべて通る（既存の 84 件と、tests/test_human_check.py の 12 件。§5.10 の 1〜5・8・9、§5.8 の承認と候補の受け入れを含む）。
    - 実データ（読むだけ）: check は ERROR 11 件がすべて「導く欄（文献）が古い」（derive を走らせていないため）。要ヒューマンチェックの印は 4 件（kawahara2013 の近似一致、確認済 0）。NOTE 15 件は、抽出の診断の頭書き 7、kawahara2013 の 0.2.0 の自由文の記録 4（形でない）、根拠の NOTE 4。OCR の文字の層の印はまだ出ない（頭書きを足す移行の後に出る）。grade・coverage・classify --list・review -o は最後まで走り、数は前と同じ。
    - 未確認: confirm・apply・checkpoint を実データに当てること（確認のコマンドは読むだけの範囲で走らせない決まり）。
    - 設計の解釈（報告で確認）: §5.3-1 の 違う の問題の文は、「原本と違うと報告された。逐語を直して確かめ直す」とする（設計どおり。利用者が 2026-10-22 に承認）。INFO の「review --source-checks」は C3 で作ったコマンドを指す。
- [x] C3 review で要ヒューマンチェックを確かめる材料と依頼の JSON (2026-10-23、設計 §5.5)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 110 件すべて通り、スキップは無い（前の 96 件、tests/test_source_review.py の 9 件、tests/test_review_js.py の JS の 5 件。node あり）。§5.10 の 6（依頼の JSON の形）と 7（JS の原本での確認）を含む。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 11 件がすべて「導く欄（文献）が古い」。要ヒューマンチェックの印は 4 件（kawahara2013 の近似一致、確認済 0）。`review --source-checks` の md と JSON、`review -o` の md、`review --html` が最後まで走る。md の要ヒューマンチェックの行と `confirm … --source` の命令は 4 件、HTML の入力は 4 件。grade・coverage・classify --list は前と同じ数。
    - 未確認: 承認の HTML を画面で開いて操作すること。JS の画面の部分（クリックと同じ抜き書きの同期）は、構文の確認（node --check）だけで、動かしていない。
    - 設計の解釈（報告で確認）: module.exports に missingSourceNotes と isStaleSource を足した（既存の名前は変えていない）。依頼の JSON の answer_example は、原稿と作った時刻だけ実値、by・saved・id・fingerprint は `<…>` のまま。候補の新しい抜き書きには原本での確認の入力を出さない（抜き書きの ID が無いため）。
- [x] C4 孫引きの欄 (2026-10-23、設計 §6)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 123 件すべて通る（前の 110 件、tests/test_secondary_source.py の 13 件。§6.6 の 1〜6 を含む）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件で exit 0、NOTE 33 件、関連研究の INFO は 2 件（harada2006#e2、hua2026_typing_dissolution#e7。どちらも孫引きは無い）。grade・coverage・classify --list（--all を含む）・`review --source-checks -o` の md が最後まで走る。原稿の抜き書きには孫引きが無いので、孫引きの INFO と cite.attribution の一致は実データでは出ない（試験で確かめた）。
    - 未確認: 承認の HTML を画面で開き、「孫引き」の行を見ること（HTML は文字列の試験だけ）。原稿に孫引きを書いて実データで確かめること（原稿のデータは変えない決まり）。check の ERROR が 0 件になった理由（C3 の記録の「導く欄が古い」11 件は今は出ない）は確かめていない。derive は走らせていない。（後に確かめた: 原稿のリポジトリの 0b93ca9 で derive が走り、抽出の頭書きも足されていた。C7 の記録を参照。）
    - 設計の解釈（報告で確認）: 台帳に書く status は、孫引きを使わない今までの式のまま。一覧と review は今の記録から決める。値の中の語は「、」で分け、書誌の key と完全に一致するものだけを拾う（複数なら「元の文献は書誌にある（a、b）」）。cleared_by と compare は同じ型に置けない（_validate で断る）。候補の新しい抜き書きの 孫引き は空。tests/test_source_review.py の根拠の形に secondary を足した（既存の試験の形を review_data に合わせた）。
- [x] C5 check の分類器の数を classify --list とそろえる (2026-10-23、設計 §7)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 125 件すべて通る（前の 123 件と、tests/test_classifier.py の新しい 2 件。材料（逐語）を変えた後と、引用が消えた後に、check と classify --list の判定・印・古い件数が一致する。§7.5 を含む。マニフェストの件数も check と一致する）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件。分類器は 判定 8 件のうち印 2 件、古い判定 8 件（classify --list も同じ 8・2・8）。check で run_check は一度だけ走る（呼び出しを数えて確かめた）。grade・coverage は HEAD と同じ出力。`review --source-checks -o` の md が最後まで走る。
    - 未確認: checkpoint で run_check が二度走らないことは、コードを読んだことと試験（checkpoint の試験で件数が一致する）で確かめた。実データの checkpoint は、マニフェストを書くので走らせていない。
    - 設計の解釈（報告で確認）: 単位が無くなった判定に加えて、型が登録から外れた判定（cite.strength の 3 件）も古いに数える。以前は黙って飛ばしていた。試験の import の規則は、check から review への関数の中の import だけを例外にした（§7.3 の形を固定するため）。classify --list --cids で絞ると、絞り外の判定が古いに数えられる。
- [x] C6 出典ごとの網羅 (2026-10-23、設計 §8.1、§8.2 の 2)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 138 件すべて通る（前の 125 件、tests/test_coverage.py の 13 件。§8.1 の 9 の 1〜8 と、--checkable で repeat の件が外れる試験、除外の part の試験を含む）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件で exit 0。網羅の INFO は「出典らしきもの 92（括弧 85）のうち、印のあるもの 24、印の無いもの 68」（前は括弧 79 のうち 18・61）。増えた分は、出典ごとに分けた 7 件（DSCR、StepWrite、W3C、Smartbox、緒方・後藤、WISS、Zhu の「（…; …）」）と、頁だけ・同書の括弧 6 件（いずれも直後に印があり、印ありになる）。Smartbox の括弧は、印の key が二つ目の出典なので、一つ目が印の無いものになる。grade・classify --list は前と同じ出力。`review --source-checks -o` の md が最後まで走る。
    - 未確認: propose --checkable を実データに当てること（作業票を原稿のリポジトリに書くため、走らせていない）。checkpoint の manifest の parens は試験で確かめた（実データの manifest は書いていない）。
    - 設計の解釈（報告で確認）: 出典の番号 part は 0 から。表示は k/n（k = part + 1）。一件の括弧の source は括弧の中身。書誌を渡さないときも、括弧の分けと repeat は働く（印の判定だけが今と同じ）。実データでは、一件の括弧の印の有無と除外が HEAD と一致する（分けた括弧を除く）。propose は --checkable 以外では repeat の件も作業票に出す（§8.2 の 2 のとおり）。作業票の見出しは、同じ括弧の出典どうしで括弧が同じ文字列になる（item の ID で区別する。作業票の形は変えていない）。
    - 今の実装のまま採り、記録だけ残した判断（2026-10-23、利用者）:
      - 頁だけ・同書の括弧（repeat）を --checkable なしの propose の作業票にも出す。key の候補は括弧の前の 30 字から取るので外れやすい。作業票は人が見て選ぶ候補なので、外れても害は小さいとみた。外れが目立てば、repeat の件を作業票から外すか、候補の取り方を見直す。
      - 括弧の直後の印が文の外（「。」の後）にある形で、余った印の数え方が以前と変わった（設計の文言に合わせた）。実データに当たる例はない。例が出たら数え方を見直す。
- [x] C7 0.3.0 の文書と版 (2026-10-23、設計 §9、§5.7)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 138 件すべて通る。この項目で試験は足していない（TOOL_VERSION を固定する試験も、文書の文言を見る試験も無い）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件で exit 0。網羅は C6 と同じ（出典らしきもの 92（括弧 85）、印のあるもの 24、印の無いもの 68）。grade・coverage・classify --list は C6 と同じ出力。`review --source-checks -o` の md と `review --source-checks --json -o` の依頼（cite-bridge-source-checks/1、13 件）が最後まで走り、依頼の鍵と answer_example の鍵が SPEC §5.1 の形と一致する。
    - 基準線: 原稿のリポジトリの 0b93ca9（2026-10-23）で、derive と抽出の頭書きの移行（SPEC §11 の 0.3.0 の移行の手順 1〜2）が済んでいた。check の ERROR が「導く欄（文献）が古い」11 件から 0 件になったのは、これによる。
    - 未確認: checkpoint の manifest の新しい鍵（by、source_checks、coverage.parens）を実データで書くこと（原稿のリポジトリに書くため走らせていない）。鍵の並びはコードを読んで SPEC §8 と合わせた。外部の AI に依頼を回して判断ファイルを受け取る流れは、まだ一度も回していない。
    - 設計の解釈・違えた点（報告で確認）: (1) SPEC §8 の例に、設計 §5.6 の by と §5.3 の source_checks を足した。(2) §11 の版の方針は、設計 §9-3 のとおり、1.0 より前は既存のファイルの状態が変わる変更でも副版を上げる、に書き換えた（前の「主版を上げる」の文を替えた）。(3) 依頼の JSON の節は SPEC §5.1 に置いた（設計は節の場所を決めていない）。(4) SKILL の試験の段落の「70件」は古いので外した。(5) README と SKILL に、0.2.0 までの論文固有の記述が残っている（README の「この道具を作った論文では」の二文、thesis のパス、SKILL の 2026-10-16 の例など）。CLAUDE.md の規則 7 に照らして別途判断する。この項目では触れていない。

## 0.3.0 の後: 文書の掃除と抽出の文字コード

項目の順は C8 → C9。

- [x] C8 README・SPEC・SKILL から論文に固有の記述を除く (2026-10-23)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 138 件すべて通る。文書だけの変更で、試験は変えていない。
    - 確認: README・SPEC・SKILL を `thesis`・`構想`・`この道具を作った論文`・`§16`・`§18`・`Grid 3`・`stepwrite`・`2026-10-16` で探して 0 件。残る「論文」は、道具の目的や一般の語としての使い方だけ。
    - 実データ（読むだけ、出力は一時フォルダ）: check の出力は C7 と同じ（ERROR 0 件、exit 0）。文書だけの変更で、道具の動きは変えていない。
    - 消した記述と書き換え（規則や理由は残した）: (1) 設計の経緯を指す行（README・SPEC・SKILL の冒頭付近と、README の文書の節）→ `docs/design-0.3.0.md` を指す。(2) 構想メモの節番号（§16.2 の 6・7、§16.6、§16.7、§18、§6 の 7、§13）→ 番号を外した。規則の文（要約に誤読を補わない、指摘を承認の理由から分ける、書き手と役割を分ける）は残した。(3) README の「この道具を作った論文では、書誌全体の約 4 割」→ 「PDF も Web の写しも無い文献は、照合できない格になる」（件数は消し、限界の文は残した）。(4) README の「実際に見つかった誤り 7 件のうち 2 件」→ 件数を消し、「実際に見つかった誤りの多くを見逃した」にした。(5) SKILL の 2026-10-16 の事例（Grid 3 の頁）→ 事例を消し、図にしか無い内容を照合の範囲に入れる理由だけを残した。(6) 例の論文の実パス（`notes/書誌リスト.md`）→ `bib/bibliography.md`。(7) 例に使っていた論文の文献（StepWrite）→ 架空の key `smith2020` と英文の例に替えた。記入の日付も 2026-01-01 にした。(8) 分類器の台帳の例の時刻（SPEC §6.4）→ 2026-01-01。
    - 未確認: 人が読んで文の流れを確かめていない（置き換えた文が前後と続くかは見ていない）。
    - 設計の解釈（報告で確認）: 0.2.0 までの設計の経緯は、この repo には無い（構想メモは論文のリポジトリにある）。そのため、設計の行は 0.3.0 の設計書だけを指す。
- [x] C9 extract --header-only が UTF-8 でない抽出テキストで止まらない (2026-10-23)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 139 件すべて通る（前の 138 件と、tests/test_extraction.py の新しい 1 件）。新しい試験は、Shift_JIS の抽出テキストと UTF-8 の抽出テキストを並べて `--header-only` を走らせ、飛ばす理由（`skip paper2020: refs/_txt/paper2020.txt は UTF-8 で読めない（頭書きを足さなかった）`）が出て、次の文献に頭書きが足され、Shift_JIS のバイトが変わらないことを確かめる。
    - 実データ（読むだけ）: check の出力は C8 と同じ（ERROR 0 件、exit 0）。extract --header-only は原稿のリポジトリでは走らせていない（決まり）。
    - 未確認: 実データに UTF-8 でない抽出テキストがあるか、あればその扱い。extract を実データで走らせていないため、確かめていない。
    - 設計の解釈（報告で確認）: 飛ばすのは UTF-8 として読めないときだけで、文字コードの推測も変換もしない。check と Source の読み方（置換文字で読む）は変えていない。README と SKILL は、飛ばす場合を並べていないので変えていない。

## 0.3.0 の後: 2026-10-31 のレビューで見つけた穴

道具の全体を読み、一時フォルダの小さな一式で動かして見つけたもの（0971124 の時点）。どれも提案で、決めてから着手する。
先に指紋の照合を素通りできる穴（C10、C11）と、確認待ちを黙って通す穴（C12、C13）を塞ぐ。

- [x] C10 判断ファイルの指紋が空か無いものを断る (2026-11-05、apply で SKIP にする)
  - 確かめた記録（2026-11-05）:
    - cite_bridge/apply.py: 件を書く前に `_gap` で照合に要る欄を見る。空か無い件は書かず、`SKIP <id>: 判断ファイルの <欄> が空か無い。書かなかった` を出して次の件へ進む。欄は decisions が `id`・`fingerprint`・`evidence`（action も remark も無い件は従来どおり何もしない）、candidates（action が accept か reject の件のみ）が `id`・`cfp`、confirms と source_checks が `id`・`fingerprint`。`seen` の falsy 判定には頼らない。件が辞書でない、または id が無いときは SKIP の ID を `?` で出す。
    - 直した前は、decisions の空の `fingerprint` は write_approval の照合で「本文が変わった」の文で断り、空の `cfp` は apply_candidate で「候補が変わった」の文で断っていた（どちらも誤った理由の文）。confirms と source_checks の空の `fingerprint` は `if seen and` の falsy 判定で照合を飛ばして書いていた。鍵の欠けた件は KeyError で apply が止まっていた。直接の `confirm` コマンドは変えていない。
    - 試験: tests/test_bridge.py の test_apply_skips_empty_fingerprints（decisions・candidates・confirms・source_checks の指紋が空。同じファイルの指紋の合う要約の確認は書く）と test_apply_skips_missing_keys_and_goes_on（decisions の evidence、candidates の cfp、confirms の id、source_checks の fingerprint の欠け。KeyError が出ず、候補の却下は書く）。`python -m pytest -q tests`: 141 passed（前は 139）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `check` は exit 0、ERROR 0 件。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` も exit 0。`apply`（`--dry-run` を含む）は、この項目の共通の確かめ方で「derive・extract・confirm・apply は走らせない」と決まっているので走らせていない。
    - SPEC.md は変えていない。§5 の「fingerprint が今と合わなければ書かず、理由を出す」に空と欠けが入るため。
- [x] C11 承認の HTML が、要約が変わった後の要約の確認を戻さない (2026-11-06、印に要約の指紋を持たせ、違う印と前の形の印を戻さない)
  - 確かめた記録（2026-11-06）:
    - cite_bridge/templates/review.js: `summaryFp(D, e)`（引用の根拠の excerpts、無ければ orphans から、この HTML での要約の指紋を引く。どちらにも無ければ undefined）と `isStaleConfirm(v, fp)`（印が無い、オブジェクトでない、今の指紋が無い、指紋が違う、のどれかで古い）を足し、module.exports に加えた（既存の名前は変えていない）。
    - localStorage の形の変更（SPEC の形式には入っていない）: `confirms` は、前は抜き書きの ID の文字列の並び、今は `{id, fingerprint}` の並び。fingerprint は印を付けた HTML での要約の指紋。collect はこの形で残し、restore は `isStaleConfirm` が真の印（指紋の違う印と、前の形の文字列の印）を戻さない。前の形の印は一度だけ外れ、人が付け直す。
    - buildOutput は、前と同じく今の HTML の要約の指紋を判断ファイルに付ける（判断ファイルの形 cite-bridge-decisions/1 は変えていない）。`confirms` の要素は文字列と `{id, …}` のどちらも受ける。どちらにも無い ID は前と同じく落とす。
    - 試験: tests/test_review_js.py に test_summary_fingerprint_comes_from_citations_or_orphans、test_summary_confirm_with_other_or_no_fingerprint_is_not_restored（同じ指紋は戻す、違う指紋・前の形・無い ID は戻さない）、test_summary_confirm_in_output_has_the_current_fingerprint。`python -m pytest -q tests`: 150 passed（前は 147。node あり、スキップ無し）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `check` は exit 0、ERROR 0 件。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` も exit 0。`review --html -o <一時フォルダ>` も走り（主張の引用 23 件、要約の確認の入力 22）、出た HTML の script は `node --check` を通る。thesis の git status は前後とも空。derive・extract・confirm・apply は走らせていない。
    - 未確認: 承認の HTML をブラウザで開き、印を付けて作り直した後の戻り方を画面で見ること（DOM の部分は構文の確認だけ）。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C12 apply が一件の失敗で途中で止まらない (2026-11-05、失敗の件を SKIP にして続ける)
  - 確かめた記録（2026-11-05）:
    - approve.py の `_citation_now` は、印がちょうど一つ無い件とブロックが無い件を `(None, 理由)` で返す（前は `sys.exit`）。`write_approval` と `write_remark` はこれを `(False, "<id>: 理由")` にする。`write_remark` は、印の無い ID の指摘を書かない（前は、ブロックさえあれば印が無くても書いていた）。`write_confirm`・`write_source_check`・`apply_candidate` は、もとから `sys.exit` を使っていない（確かめた）。
    - apply.py: 書き込みの関数が返した失敗は `skipped` に入り、`SKIP` の行になる。confirms と source_checks の失敗の文は、ID で始まらないので `_tag` で `<id>: ` を付けた。decisions と candidates の文は、もとから ID で始まる。書いた件と書かなかった件の数を出し、`applied.json` を記録する（書かなかった件があるときは終了コード 1）。
    - approve と confirm のコマンドは、失敗の文を `sys.exit(文)` で出すので、終了コードは 1 のまま。approve の失敗の文は、ID の頭つき（`c009: 原稿に〔c009〕がちょうど一つ無い（0 箇所）`）になった（前は頭無し）。
    - 試験: tests/test_bridge.py の test_apply_skips_absent_ids_and_goes_on（印の無い c009 とブロックの無い c003 を、有効な件に挟む。applied.json の written 2・skipped 3、再適用は「適用済み」）、test_apply_skips_absent_entries_of_other_kinds（候補の文が変わった件、抜き書きの無い confirm と source_check を挟み、後ろの要約の確認は書く）、test_approve_and_confirm_absent_ids_still_exit_1（approve と confirm が理由を出し、終了コード 1）。`python -m pytest -q tests`: 144 passed（前は 141）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `check` は exit 0、ERROR 0 件。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` も exit 0。`apply` は、共通の確かめ方で「derive・extract・confirm・apply は走らせない」と決まっているので走らせていない。
    - SPEC.md と README.md は変えていない。apply の挙動の文（§5 の「合わなければ読み飛ばして理由を出す」）はそのまま正しい。
    - 閉じた時点の確認（leader）: git diff を確かめ、`python -m pytest -q tests` は 144 passed。レビュアーは接続していなかったので、この項目はレビューを受けていない。後で統制のセッションが差分を読んで確かめた（2026-11-05。apply から呼ぶ書き込みの関数に `sys.exit` が残らないこと、propose の受け入れの `write_approval` は印とブロックを書いた直後に呼ぶので失敗しにくく、前より悪くならないこと、指摘も原稿に印の無い ID では SKIP になること）。
- [x] C13 引用のファイルが無いとき check を確認待ちにする (2026-11-05、無いとき NOTE を出して --strict と checkpoint を止める)
  - 確かめた記録（2026-11-05）:
    - cite_bridge/check.py の run_check: 引用のファイルが無い枝（`cfg.CIT` が存在しない）で、`notes` に `<cfg.CIT のパス>: 引用のファイルが無い（設定の citations か --citations のパスを確かめる）` を足す。ERROR は増やしていない（CLAUDE.md の規則 4）。引用のファイルが有る枝は変えていない。
    - 出力は既存の NOTE と同じ経路（cmd_check の `print("NOTE ", n)`）なので、行は `NOTE  <パス>: …` になり、NOTE の前後に空白が二つ入る（既存の NOTE も同じ）。
    - `check --strict` は既存の NOTE と同じく、確認待ちとして exit 1。`checkpoint` は notes があれば書かず exit 1。普通の `check` は NOTE だけなら exit 0 のまま（既存と同じ）。SPEC・README・SKILL は NOTE の全部の一覧を書いていないので、変えていない。
    - 試験: tests/test_bridge.py の test_missing_citations_file_is_a_note。引用の有る一式（承認済み）では、check --strict が exit 0 で NOTE は出ない。設定を `bridge/citation.md` に打ち間違えると、check は exit 0 で NOTE を出し、check --strict と checkpoint は exit 1、bridge/checkpoints は作られない。`--citations bridge/none.md` も同じ。正しい `--citations` に戻すと check --strict と checkpoint は exit 0。
    - `python -m pytest -q tests`: 145 passed（前は 144）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `check` は exit 0、ERROR 0 件、「引用のファイルが無い」の NOTE は 0 件（thesis の bridge/citations.md は有る）。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` も exit 0。checkpoint・apply・derive・extract・confirm は走らせていない。
    - `--citations` は全体の選択肢なので、サブコマンドの前に置く（`bridge.py --citations X check`）。試験もその形を使う。
    - 閉じた時点の確認（leader）: git diff を確かめ、`python -m pytest -q tests` は 145 passed。レビュアーは接続していなかったので、この項目はレビューを受けていない。
- [x] C14 --citations で写しを指したときの記録の置き場 (2026-11-08、設定で明示していない applied・candidates・excluded・judgments を --citations のフォルダに置く)
  - 決めたこと（2026-11-08、利用者）: 4 つとも、設定で置き場を明示していなければ `--citations` で指した引用のファイルのフォルダに置く。判定の台帳も追わせる（引用の ID で引くので、原稿が複数あって共有すると同じ ID の判定が互いを古くする）。設定で明示した置き場は動かさない（台帳を写しと共有したいときは judgments を明示する）。
  - 確かめた記録（2026-11-08）:
    - cite_bridge/config.py の load_config が citations（--citations の値）を受け、引用のファイルを差し替えてから既定の置き場を決める。cli.py は設定を読んだ後に CIT だけを替えるのをやめ、値を load_config に渡す。
    - SPEC.md と SPEC.en.md: §9 の表の bridge に judgments を足し（設定は前から読んでいたが表に無かった）、省いた置き場の既定と --citations のときの置き場、明示した置き場は動かないことを書いた。README.md と README.en.md の「最小の使い方」に --citations の段を足した（前は README に説明が無かった）。SKILL.md と SKILL.en.md の [bridge] の補足に judgments と --citations のときの置き場を足した。
    - 版は上げていない。§7 の記録は §11.1 で固めない範囲で、欄・形式名・指紋・ファイルの状態は変わらない。
    - 試験: tests/test_bridge.py の test_apply_to_copy_keeps_original_log（写しを指して apply すると記録は trial/applied.json に入り、bridge/applied.json は作られず、同じ判断ファイルを本物に当てても「適用済み」で断られない）と test_record_paths_follow_citations_unless_set（既定、--citations のとき、applied と judgments を明示したときの 4 つの置き場）。直す前のコードでは 2 つとも落ちることを確かめた。`python -m pytest -q tests`: 185 passed（前は 183）。
    - 実データでの確認（読むだけ）: check は exit 1 で、ERROR は許してある「ms_dictate_word_web#e3: 導く欄が古い」だけ、NOTE 35、承認済 23。grade・coverage・classify --list・review --source-checks -o（一時フォルダ）が exit 0。原稿の設定は 4 つを明示しておらず、--citations を使わないので置き場は前と同じ。原稿のリポジトリの git status は空のまま。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C15 引用のブロックの ID の重複を確認待ちにする (2026-11-06、重複は NOTE にして書き込みを断る)
  - 確かめた記録（2026-11-06）:
    - cite_bridge/check.py の run_check: 引用のブロックの loop で、同じ ID の二つ目以降に `notes` を足す（先の行は最初のブロックの行）。ERROR は増やしていない（CLAUDE.md の規則 4）。出力は既存の NOTE と同じ経路なので、行は `NOTE  <パス>:<行> <ID>: …` になり、NOTE の後に空白が二つ入る。
    - cite_bridge/approve.py の `_citation_now`: 同じ ID のブロックが二つ以上なら `(None, "<パス> に <ID> のブロックがちょうど一つ無い（<n> 個）")` を返す。n = 0 の「ブロックが無い」の文言は変えていない。`write_approval` は `<ID>: ` を付け、`write_remark` は `_citation_now` を通るので同じ理由になる。apply は decisions の approve と remark をそれぞれ SKIP に入れ、残りを処理する。`_replace_block_lines` で引用のブロックを書くのは `write_approval` と `write_remark` だけで、どちらも `_citation_now` の後に走る（確かめた）。候補の受け入れは新しい ID のブロックを末尾に足すだけなので、重複を作らず、この変更の対象外（確かめた）。
    - 試験: tests/test_bridge.py の test_duplicate_citation_block_is_a_note_and_writers_refuse（check が NOTE を出し、--strict は exit 1、approve と指摘の apply が理由つきで断り、引用のファイルは変わらない）と test_apply_skips_duplicate_block_and_writes_the_rest（重複した c001 は SKIP、別の ID の c002 は承認を書く、applied.json は written 1・skipped 1）。
    - `python -m pytest -q tests`: 147 passed（前は 145）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `check` は exit 0、ERROR 0 件、「ID の重複」の NOTE は 0 件（thesis の引用に同じ ID のブロックは無い）。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` も exit 0。checkpoint・apply・derive・extract・confirm は走らせていない。
    - SPEC.md と README.md は変えていない。NOTE の全部の一覧はどちらにも無い（C13 と同じ）。
    - 閉じた時点の確認（leader）: git diff を確かめ、`python -m pytest -q tests` は 147 passed。レビュアーは接続していなかったので、この項目はレビューを受けていない。
- [x] C16 指示の引用の欄と承認を SPEC とそろえる (2026-11-07、SPEC を実装に合わせ、指示で要るのは書誌の key だけにした)
  - 確かめた記録（2026-11-07）:
    - SPEC.md §3.1: 表の 理由・記入・承認 を「主張のとき要」にし、表の下に、指示の引用で要るのは `文献` の key（書誌にあるもの）だけで、理由・記入・承認は求めない（書けば review の材料に出るが確認待ちにしない）と書いた。§3.2 の頭に、承認の状態は主張の引用に付くと足した。
    - README の「構成」に主張と指示の二種類の段を、SKILL.md の引用の節に指示で要るものの二行を足した。
    - 実装は変えていない（check.py は指示の引用で 文献 の key と印の key だけを見て、承認の状態を数えない。review は欄があれば材料に出し、確認待ちに入れない）。版は上げない。
    - SPEC §6.2 の下書き（`propose --load`）は、指示にも 理由・記入 を求めたまま。書き手の作業票の形で、引用のブロックの必須ではないので変えていない。
    - 試験: tests/test_bridge.py の test_pointer_needs_only_a_bibliography_key（承認者の一覧あり。種類と文献だけの指示 c002 で `check --strict` が 0 で c002 の行を出さず、集計が「指示 1」、checkpoint も通る。文献を書誌に無い key にすると今の ERROR）。`python -m pytest -q tests`: 158 passed（前は 157）。
    - 実データでの確認は、コードを変えていないので走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C17 試験が pymupdf の有無と版で落ちない (2026-11-05、無い環境ではスキップ、2.0 でも通る)
  - 確かめた記録（2026-11-05）:
    - pymupdf の無い環境の再現: 利用者の環境は触らず、一時フォルダ（scratchpad の nopymupdf）に pymupdf.py と fitz.py を置き、ImportError だけを投げる偽物にした。`PYTHONPATH` の先頭に置いて `python -m pytest -q tests` を走らせた（子プロセスの bridge にも効く）。修正前は、test_snapshot_pdf_url と test_source_checks_images_option_writes_page_image の 2 件が失敗し、他の PDF の試験は飛んでいた（この 2 件が失敗したのは、偽物の ImportError による。実際に無い環境では ModuleNotFoundError になる）。
    - 修正: tests/test_bridge.py に `HAS_PYMUPDF`（pymupdf の import の成否）を置き、test_snapshot_pdf_url に `skipUnless`。tests/test_source_review.py の test_source_checks_images_option_writes_page_image に `tb.HAS_PYMUPDF` の `skipUnless`。tests/test_extraction.py は、もとの `skipIf`（モジュールの pymupdf）のまま。
    - pymupdf の無い環境: `python -m pytest -q tests` は 129 passed、15 skipped（飛んだのは test_extraction の 13 件と、上の 2 件）。
    - 縦横比の確認: 正方形の画像を頁に `insert_image` すると、pymupdf 2.0 では既定で頁の 70.7% を覆い、`keep_proportion=False` で 100%。1.28.2 では既定でも 100%。tests/test_extraction.py の make_pdf と tests/test_source_review.py の make_pdf に `keep_proportion=False` を入れた。2.0 で修正前の 4 件が落ちることは、この比で確かめた（修正前の試験は 2.0 で走らせていない）。
    - pymupdf の版: 1.28.2（この環境の既定、Python 3.12.10）で `python -m pytest -q tests` は 144 passed。2.0 は `pip install --target` で一時フォルダに入れ、`PYTHONPATH` で先頭に置いて走らせた（利用者の環境は変えていない）。2.0 でも 144 passed。
    - README の「動かすのに要るもの」: 試験で確かめた版として 1.28.2 と 2.0 を書いた。2.1 は版の一覧にあるが、試していない。
    - 実データ（読むだけ）: 変えたのは tests と README だけなので、実データへの影響は無い。`check`・`grade`・`coverage`・`classify --list`・`review --source-checks -o <一時フォルダの md>` は、cwd を thesis にして exit 0。`check` の ERROR は 0 件。`apply`・`derive`・`extract`・`confirm` は走らせていない。
    - 閉じた時点の確認（leader）: git diff を確かめ、`python -m pytest -q tests` は 144 passed（pymupdf 1.28.2）。レビュアーは接続していなかったので、この項目はレビューを受けていない。pymupdf 2.1 は試していない。
- [x] C18 model の承認と、README の「人の承認が保証する」をそろえる (2026-11-07、一覧で model の者の引用の承認を確認待ちにし、版を 0.4.0 にした)
  - 確かめた記録（2026-11-07）:
    - cite_bridge/manuscript.py に `model_approval_problem(by)` を足した（承認者の一覧で model なら理由の文、一覧が無いか human なら None）。cite_bridge/check.py の run_check は、承認済の引用で、書き手と同じ model の規則（§5.8）に当たらず、この理由があるとき `NOTE <パス>:<行> <ID>: 承認を数えない（model '<名前>' の承認は記録に残るが、承認済には人（human）の承認が要る）` を出し、状態を未承認として数える（既存の「承認を数えない（書き手と同じモデル …）」と同じ形。続けて「未承認（節）」の NOTE も出る）。承認者の数（approvers）には入らない。ERROR は増やしていない。
    - approve と apply は変えていない（model の承認は今までどおり書け、記録に残る）。原本での確認と要約の確認も変えていない。
    - 道具の版: cite_bridge/config.py の TOOL_VERSION を 0.4.0 に。SPEC の頭の形式の版と §8 のマニフェストの例も 0.4.0 に。
    - SPEC.md §3.2（承認済の条件に、一覧があるときは human の承認であること）、§9 の approvers の行、§11 の 0.4.0 の項と移行の手順。README の「何をする道具か」に一行、SKILL.md の承認者の一覧の段に三行。
    - 試験: tests/test_bridge.py の test_model_approval_is_kept_but_pending（一覧あり。model の承認は書けて記録に残り、check が NOTE を出して未承認 1、approvers は空、`check --strict` と `checkpoint --by alice` が止まり checkpoints を書かない。人が承認すると承認済 1 で --strict が通る）と test_approval_without_approver_list_is_unchanged（一覧が無いと同じ名前の承認は承認済 1 で --strict が通る）。human の承認が変わらないことは、前者の後半と既存の試験で見る。`python -m pytest -q tests`: 160 passed（前は 158）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `check` は exit 0、ERROR 0 件、NOTE 33 件（C21 のときと同じ）、「承認を数えない」は 0 件、集計は「主張 承認済 23 / 要再確認 0 / 未承認 0、指示 5」で変わらない（承認者の一覧は human の一名だけ）。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` も exit 0。thesis の git status は前後とも空。derive・extract・confirm・apply・checkpoint は走らせていない。
    - 残したこと: review は model の承認の引用を今も「承認済」として扱い、既定の確認待ち（`review` と `review --html`）に出さない。完了条件の外なので変えていない。SPEC §11 の移行の手順では、ID か `--all` で指すと書いた。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [-] C19 レビューで見つけた小さな崩れ (却下 2026-11-05、1 項目 1 依頼にするため C21〜C25 に分けた)
- [x] C20 短い逐語の照合と、確認者の名前の比べ方 (2026-11-07、欧文 3 語以下・和文 10 字以下の逐語を要ヒューマンチェックにし、名前を正規化して比べる)
  - 決めたこと（2026-11-07、利用者）: 短い逐語は、和文の字を含めば空白を除いた字数が 10 字以下、含まなければ空白で区切った語数が 3 語以下。扱いは要ヒューマンチェックの理由「逐語が短い」（原本での確認で解ける）。名前は NFKC・大文字と小文字の無視・前後の空白の除去をしてから比べる。
  - 確かめた記録（2026-11-07）:
    - cite_bridge/derive.py に `is_short_verbatim` と上限の定数（SHORT_WORDS 3、SHORT_CHARS 10）を足した。`human_check_reasons` は逐語を受け取り、逐語が抽出テキストに見つかって短いとき「逐語が短い」を足す（見つからないものは前から「照合で見つからない」）。derive と review の新しい抜き書き（候補）の両方から逐語を渡す。和文の字の判定は cite_bridge/source.py の `is_cjk`（かな・漢字・全角の字）。
    - cite_bridge/manuscript.py に `same_name` を足し、`self_check_problem` が書き手と確認者をこれで比べる。原本での確認・要約の確認・承認・候補の受け入れはどれも `self_check_problem` を通るので、四つとも同じ比べ方になる。承認者の一覧の引きは前と同じく完全一致（一覧に無い名前は前から断る）。記録の文字は変えない。
    - SPEC.md §2.1 の条件 3（名前の比べ方）、§2.2（理由「逐語が短い」と長さ）、§11 の 0.4.0 の項と移行の手順 4・5。README と SKILL.md の要ヒューマンチェックの理由と記録が有効な条件。版は C18 で上げた 0.4.0 のまま（まだ push していない）。
    - C18 の直し漏れ: SKILL.md の「保証と持ち主」が「承認者は役割で、人か、書き手と別のモデル」と書いていたので、人の承認が保証し、model の承認は確認待ちになると直した。
    - 試験: tests/test_human_check.py の test_short_verbatim_boundaries（3 語と 4 語、10 字と 11 字、和文の字を含む欧文混じり）、test_short_verbatim_needs_source_check（3 語の逐語は照合が一致でも印が付き、4 語には付かない、check が NOTE を出し `confirm --source` で消える）、test_names_are_compared_after_normalizing（全角・大文字・空白の違い。書き手が Reviewer-Model の抜き書きを reviewer-model が原本で確認しようとすると断る。前のコードでは書けた）。`python -m pytest -q tests`: 163 passed（前は 160）。
    - 実データ（読むだけ。thesis のフォルダ）: `check` は exit 1 で、ERROR は「ms_dictate_word_web#e3: 導く欄が古い」の 1 件だけ（逐語 `bold that` が短く、derive すると印が付くため。台帳の共通の確かめ方で認めた ERROR）。NOTE は 33 から 35 に増えた。増えた 2 件は、その抜き書きの「要ヒューマンチェック（逐語が短い）」と、それを根拠にする c008 の NOTE。集計は「主張 承認済 23 / 要再確認 0 / 未承認 0、指示 5」で変わらない。名前の正規化で新しく出た NOTE は無い（記入は Claude、承認は hiatama で、書き違いは無かった）。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` は exit 0。thesis の git status は前後とも空。derive は走らせていない（利用者が走らせると e3 に印が付き、原本での確認が要る）。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C21 判定の台帳の読めない行で止まらない (2026-11-07、読めない行は飛ばし、check が INFO で行番号を出す)
  - 確かめた記録（2026-11-07）:
    - cite_bridge/judge.py の read_ledger: 読めない行（UTF-8 でない・JSON でない・item・type・label が文字列でない・json.loads が RecursionError になる行）を飛ばす。load_ledger はその辞書を返す。check・checkpoint・classify は最後まで走る。
    - cite_bridge/check.py の run_check: 飛ばした行があると `INFO <パス>: 判定の台帳の読めない行を <n> 行飛ばした（<行番号>）` を出す。NOTE と ERROR は増やしていない。SPEC.md の判定の台帳の節に規則を書いた。
    - 試験: tests/test_bridge.py の test_unreadable_ledger_lines_are_skipped_and_noted（UTF-8 でない行、JSON でない行、item が数の行、100000 個の `[` の行を含む台帳で、derive・check（INFO の行番号 2、4、5、6）・checkpoint（承認して通す）・classify --list が exit 0）。前の読み方では UnicodeDecodeError と RecursionError で止まることを確かめた。
    - `python -m pytest -q tests`: 155 passed（前は 154）。
    - 実データ（読むだけ。thesis のフォルダ）: check と classify --list の出力は前後で cmp 同一（check は NOTE 33・ERROR 0、飛ばした行は無し）。checkpoint は未承認が残るので exit 1 で前と同じ（書いていない）。
    - 閉じた時点の確認（leader）: レビューの指摘は一件（RecursionError の行で止まる）で、直した。
- [x] C22 keyline の書誌で、先頭の key の行を読み違えない (2026-11-06、先頭の key: の entry は空・accessed は None)
  - 確かめた記録（2026-11-06）:
    - cite_bridge/bib.py の bib_keyline: `key:` が 1 行目のとき、書誌の行を `lines[i - 1]`（最後の行）にせず、entry は空文字、accessed は None にする。注記と PDF の読みは前と同じ。
    - 試験: tests/test_bridge.py の test_keyline_key_on_first_line_reads_no_entry（entry は空、accessed は None、注記の PDF は読む）。前のコードでは落ちることを確かめた。
    - `python -m pytest -q tests`: 151 passed（前は 150）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `grade` と `coverage` の出力は、変更の前後で cmp 同一。`check` は exit 0、ERROR 0 件。thesis の最初の key: は 40 行目で、先頭の場合は実データに無い。
    - 閉じた時点の確認（leader）: レビュアーは指摘なし（entry 空を読む他のコードも壊れない）。
- [x] C23 書誌の key の重複を確認待ちにする (2026-11-06、二つ目からごとに NOTE。keyline・BibTeX は行、CSL-JSON は何件目)
  - 確かめた記録（2026-11-06）:
    - cite_bridge/bib.py の bib_occurrences と cite_bridge/check.py の run_check: 書誌の見出しの並びで、同じ key の二つ目からごとに `NOTE <パス>:<行> <key>: 書誌の key の重複（先は <行> 行）` を出す（CSL-JSON は行の代わりに何件目）。ERROR は増やしていない。辞書は前と同じく後のものが残る。
    - 試験: tests/test_bridge.py の test_duplicate_key_is_a_note_keyline（三つ目まで NOTE）、_bibtex、_csl_json。重複の無い版と比べて ERROR が増えないことを確かめ、前のコードでは落ちることを確かめた。
    - `python -m pytest -q tests`: 154 passed（前は 151）。
    - 実データ（読むだけ。thesis のフォルダで `python <cite-bridge>/bridge.py check`）: 前後で同一（NOTE 33・ERROR 0、重複の NOTE 0）。
    - 閉じた時点の確認（leader）: レビュアーは指摘なし。
- [x] C24 apply が件ごとにすべての抜き書きを導き直さない (2026-11-07、apply は書き終えてから、書いた抜き書きのファイルごとに一度だけ導き直す)
  - 確かめた記録（2026-11-07）:
    - cite_bridge/derive.py: `derive_excerpts` の一件分を `derive_excerpt_file` に分け、書いた抜き書きのファイルをまとめて導き直す `rederive_files` を足した。cite_bridge/approve.py・propose.py・apply.py: 要約の確認・原本での確認・候補の受け入れは、件ごとに導き直さず、書いたファイルの集合に入れる。cmd_apply は書き終えてから `rederive_files` を一度だけ呼ぶ。単独の approve・confirm はその場で一ファイル分を導き直す（前と同じ）。dry-run は導き直さない。
    - 試験: tests/test_bridge.py の test_apply_rederives_each_written_file_once（5 件の書き込み・2 ファイルで導き直しは 2 回だけ。書いた後に derive を走らせても導く欄は変わらない）。
    - 比較（同じ apply の場面を HEAD の道具と作業中の道具で走らせた）: 導き直しは 5 回から 2 回。書いた結果と apply の出力は前の道具と同一。
    - 実データ（読むだけ。apply は原稿では走らせていない）: `check`・`grade`・`coverage` は前後で cmp 同一。
    - `python -m pytest -q tests`: 157 passed。
    - 閉じた時点の確認（leader）: レビューの指摘なし。
- [x] C25 check.py の潰れた行と、SPEC §6.4 の鍵の受け方 (2026-11-07、Web の写しの取得日を読む行を一行に一つの文にした。SPEC §6.4 の鍵の受け方を、環境変数→bridge.toml の場所の .env→作業フォルダの .env、git に無視されていない .env は止める、の実装に合わせた)
  - 確かめた記録（2026-11-07）:
    - cite_bridge/check.py の run_check（Web の写しの取得日）: 読む行を `src`・`copy_text`・`wm` の一行ずつに分けた。出力は前後で cmp 同一（thesis の check、exit 0）。振る舞いは変えていない。
    - SPEC §6.4: 鍵の受け方を実装（cite_bridge/classifier.py の jev_key）に合わせた。環境変数 TYPESAFE_API_KEY → JEV_API_KEY、次に bridge.toml と同じフォルダの .env（既定 bridge/）→ 作業フォルダの .env。git のリポジトリの中で無視されていない .env があれば鍵を読まずに止める。鍵を読むのは classify --send のときだけ。
    - 試験: `python -m pytest -q tests`: 156 passed。Web の写しの経路は test_accessed_date_info が通ることで確かめた。
    - 閉じた時点の確認（leader）: レビュアーは指摘なし。
- [x] C26 引用のブロックの ID が重複すると、check の集計が二つ目も数える (2026-11-07、二つ目からの重複ブロックは集計と承認者の数に入れない。欄の ERROR と NOTE は出る)
  - 確かめた記録（2026-11-07）:
    - cite_bridge/check.py の run_check: 同じ ID の二つ目からのブロックは、counts（指示を含む）と approvers に入れない。欄の ERROR と NOTE は前と同じく出る。ERROR は増やしていない。
    - 試験: tests/test_bridge.py の test_duplicate_block_is_left_out_of_the_counts（承認済のブロックを写して二つ目にし、理由の欄を空にする。承認済 1、承認者は {alice: 1} のまま、二つ目の欄の ERROR と重複の NOTE が出る）。修正の前は承認済 2 と数えて落ちることを確かめた。
    - `python -m pytest -q tests`: 156 passed。
    - 実データ（読むだけ。thesis のフォルダで `python <cite-bridge>/bridge.py check`）: 変更の前後で cmp 同一（exit 0、INFO「引用: 主張 承認済 23 / 要再確認 0 / 未承認 0、指示 5」、重複の NOTE 0）。
    - 閉じた時点の確認（leader）: レビュアーは指摘なし。

## 公開に向けて: AI と論文を書く人向けの実験的な道具（0.x）

使い手を絞って 0.x として出す（2026-11-06 に利用者と合意）。汎用性は機能の数ではなく、データの形と作法が中立であることで満たす。毎週使わない機能は作らない。
公開の段階で約束するのは「データの形」と「保証の文」の二つだけで、機能は約束しない。出力の文と欄の名前は、使う人がローカライズや調整をする前提とする（翻訳の仕組みは作らない）。
重要な文書（README・SPEC・作法の文書・始め方の案内）は英語にしてから公開する。

順の案: 保証の約束を決める（C18・C16、続いて C20）→ データの形を固める（C27）→ 他人のデータで壊れる穴（C21〜C26）→ ライセンス（C28）→ ベンダーに縛られない形（C29）→ 写さずに指す（C30）→ 始め方の案内（C31）→ 英語の文書（C32）。

- [x] C27 データの形を正本として固め、版の方針を書き換える (2026-11-07、SPEC §11 に固める範囲と変えるときの手順を書き、SPEC と実装を試験で突き合わせる)
  - 決めたこと（2026-11-07、利用者）: 固める範囲は人と他の道具が読み書きするもの（抜き書きと引用の書く欄・記録の欄、指紋、判断ファイル、原本での確認の依頼、判定の台帳、マニフェスト）。導く欄の文言、作業票・下書き・候補、出力の文は外す。変えるときは副版を上げ、移し方を書き、古い形は次の副版まで読む。
  - 確かめた記録（2026-11-07）:
    - SPEC.md §11 を §11.1 約束する範囲、§11.2 変えるときの手順、§11.3 版の履歴に分けた。§11.1 は決めた範囲と外すもの（上に挙げないほかのファイル、§6.4 の測定の組と §7 の記録も固めない）。§11.2 は副版を上げる・状態が変わるものは移し方を書く・欄の名前と形式名の番号を変えたら前のものを次の副版まで読む。前の「形を変えたら番号を上げ、古い番号は断る」の行は消し、固めない形式は「番号を上げる。前の番号を読み続けるとは約束しない」とした。0.4.0 の項に、この版から §11.1 と §11.2 に従うと足した。冒頭の形式の版の行も §11 を指す形に直した。
    - SPEC.md §10: 固める欄のうち表に無かった `対象` と記録の欄 6 つ（承認時の指紋・本文・根拠、差し戻し時の指紋・根拠、要約の確認時の指紋）の英語の別名を表に足した（実装の FIELD_ALIASES にはもとからある）。導く欄の対応は config.py にあり固めないと書いた。
    - README の「何をする道具か」に、約束はデータの形と保証の文の二つで、コマンドと機能は約束しないと書いた。C18 で足した model の承認の一行が「そのため『検証ツール』とは呼ばない」の前に割り込んでいたので後ろへ移した。
    - 実装は変えていない。今の形式名はすべて `/1` なので、「前の番号も読む」に当たる形式はまだ無い。
    - 試験: tests/test_spec.py を足した。確かめる範囲は、SPEC §2.1 と §3.1 の書く欄の表と §2.3・§3.3 の記録の欄の名前（RECORD_FIELDS と一致）、§2.1 の必須の欄（EXC_REQUIRED と順も一致）、値の語彙（強さ・原文との差・種類）、§10 の別名の対がすべて FIELD_ALIASES と一致し、固める欄（書く欄・記録の欄・対象）がすべて §10 にあること、値の別名、SPEC と実装（cite_bridge と templates と bridge.py）の形式名の集合が一致すること、一時フォルダの一式で道具が書いた原本での確認の依頼（頭と items の鍵）と答えの例（判断ファイルの鍵と source_checks の鍵）の鍵が §5.1・§5 にあること、マニフェストの頭と tool の鍵が §8 にあり version が TOOL_VERSION と §8 の例に合うこと。判定の台帳の欄（§6.4）と判断ファイルの decisions・candidates・confirms の欄は、この試験では見ていない（読み手の規則は既存の試験が見る）。`python -m pytest -q tests`: 170 passed（前は 163）。
    - SKILL.md の試験の説明に test_spec.py の一文を足した。
    - 実データでの確認は、コードを変えていないので走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C28 ライセンスを置く（MIT） (2026-11-06、agent-hub と同じ MIT の LICENSE、README に節)
  - 確かめた記録（2026-11-06）:
    - `LICENSE`: agent-hub の `LICENSE` と `cmp` で同一（21 行、MIT の標準の全文、著作権の行 `Copyright (c) 2026 Hiatama Workshop`）。
    - README: 末尾に「ライセンス」の節（MIT であることと `LICENSE` へのリンク）。
    - 試験: `python -m pytest -q tests` が 150 passed。
    - 閉じた時点の確認（leader）: レビューは指摘なし（no findings）。
- [x] C29 特定のエージェントに縛られない置き場所と作法 (2026-11-07、既定の置き場所を tools/cite-bridge/ にし、hook は前の既定も探す)
  - 決めたこと（2026-11-07、利用者）: 既定の置き場所は `tools/cite-bridge/`（submodule のまま）。hook は新しい既定に無ければ前の既定 `.claude/skills/cite-bridge/` も探す。作法の文書は SKILL.md の名前と頭の name/description を残し、本文から特定のエージェントの前提を外す。
  - 確かめた記録（2026-11-07）:
    - hooks/pre-commit: `CITE_BRIDGE` があればそれ、無ければ `tools/cite-bridge/bridge.py`、そこに無ければ `.claude/skills/cite-bridge/bridge.py` を使う。どれも無ければ、既定の `tools/cite-bridge/bridge.py` の名前で「無いので検査を飛ばした」と出して exit 0（前と同じくコミットは止めない）。改行は LF のまま。
    - SKILL.md: 置き場所の段を `tools/cite-bridge/` に直し、別の場所ではパスを読み替えて `CITE_BRIDGE` を使うこと、この文書は普通の Markdown で、頭の name と description は skill として置くとき（例 `.claude/skills/cite-bridge/`）の入口で置き方の一つであることを書いた。コマンド例 29 行と試験の実行の例を `tools/cite-bridge/` にした。hook の節の既定値の説明を hook の探し方に合わせた。
    - README の文書の表の SKILL.md の行から「Claude Code のスキルとしての入口を兼ねる」を外し、普通の Markdown で、頭は skill として置くときの入口と書いた。tests/test_bridge.py の docstring の実行の例も直した。
    - 残した `.claude/skills/cite-bridge/` は、前の既定として明示した箇所（SKILL.md の 2 か所、hook）だけ。SKILL.md と SPEC.md の例の記入者の名前 `Claude` は欄の値の例で、エージェントの機能の前提ではないので変えていない。
    - 試験: tests/test_bridge.py の test_hook_finds_the_tool（sh があるとき。どこにも無ければ既定の名前で警告して exit 0、前の既定だけなら前の既定、両方あれば tools/cite-bridge、CITE_BRIDGE があればそれ。偽の bridge.py で確かめる）。前の hook では「両方ある」で落ちる。`python -m pytest -q tests`: 171 passed（前は 170）。
    - 原稿のリポジトリは `.claude/skills/cite-bridge` に submodule を置き、pre-commit の hook は入れていない（読むだけで確かめた）。hook を入れても前の既定を探すので、そのまま動く。道具の本体は変えていないので、実データでの確認は走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C30 使う側の指示ファイルには、写さずに指す短いブロックだけを置かせる (2026-11-07、README に「AI に使わせるとき」の節と写すブロックを置いた)
  - 決めたこと（2026-11-07、利用者）: ブロックの文面は README の節に置く。置き先は AGENTS.md・CLAUDE.md・GEMINI.md などを例として並べ、使う人が選ぶ（特定のものを勧めない）。
  - 確かめた記録（2026-11-07）:
    - README の「最小の使い方」の後に「AI に使わせるとき」の節を足した。作法の文書は写さずに指す理由（版が進むと写しがずれる）、置き先の例（AGENTS.md、CLAUDE.md、GEMINI.md など）と選ぶのは使う人であること、パスは既定の置き場所と設定のものなので替えていれば読み替えることを書き、写すブロックを一つ置いた。
    - ブロックは三行だけ: 読む文書（tools/cite-bridge/SKILL.md、形は SPEC.md）、確かめるコマンド（derive と check、提出前は check --strict）、正本（設定 bridge/bridge.toml が指す抜き書きと引用のファイル。`@` の行は手で直さない）。パスは C29 の `tools/cite-bridge/`。
    - 試験: tests/test_spec.py の ReadmeBlockTest.test_paths_and_commands_exist（README のブロックから、指す md が SKILL.md と SPEC.md で道具にあること、三つのコマンド（derive、check、check --strict）が `--help` で exit 0 になること、箇条が三つだけであること）。`python -m pytest -q tests`: 172 passed（前は 171）。
    - 道具の本体は変えていないので、実データでの確認は走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C31 一件の引用を最初から最後まで通す始め方の案内と、準備の確認の手順 (2026-11-07、docs/getting-started.md と examples/first-citation/ を置き、試験が案内のとおりに通す)
  - 決めたこと（2026-11-07、利用者）: 案内は別の一本 `docs/getting-started.md` にし、README の「最小の使い方」から指す。例の一式を `examples/first-citation/` に同梱する（自作の短い文で作る。PDF は使わず、抽出テキストを同梱する）。
  - 確かめた記録（2026-11-07）:
    - examples/first-citation/: 設定（承認者の一覧に human の hanako）、書誌（keyline、key は tanaka2024）、架空の短い英語の研究の抽出テキスト（2 頁）、印の無い出典の括弧が一つある日本語の原稿、見出しと 対象 だけの引用のファイル。.gitattributes に `examples/** text eol=lf` を足し、Windows の clone でも LF のままにした。
    - docs/getting-started.md: 0 置く（submodule と写す sh の例、写したものの表）、1 準備の確認（`grade` と `check`。どちらも読むだけで、期待する出力つき）、2 抽出（PDF があれば extract。例では飛ばす）、3 抜き書き、4 引用と印、5 derive と check と check --strict（終了コード 1）、6 承認（review c001、confirm、approve。ふだんは review --html と apply だと書いた）、7 check --strict（終了コード 0）。コマンドの塊には、どれも期待する出力と終了コードを書いた。
    - README の「最小の使い方」の頭と文書の表、CLAUDE.md の地図から案内を指す。
    - 試験: tests/test_getting_started.py。一時フォルダに道具（tools/cite-bridge/）と例の一式を写し、案内を上から読んで、ファイルの塊を書き、期待する出力つきのコマンド 9 本を走らせて、終了コードと期待する行を確かめる。bridge.py を打つ sh の塊がすべて期待する出力を持つこと、0 の表が例の一式のファイルをすべて挙げることも見る。最初の版の案内は要約の確認の集計を「確認済 1」と書いていて、試験が実際の「hanako 1」との違いを見つけた（直した）。0 の置く段（git submodule と cp）は試験で走らせていない。`python -m pytest -q tests`: 174 passed（前は 172）。
    - 見つけた小さな崩れ（直していない）: 抜き書きが 0 件のとき、check が「INFO  抜き書きの要約の確認: 」と後ろが空の行を出す。
    - 道具の本体は変えていないので、実データでの確認は走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C32 重要な文書を英語にする (2026-11-07、4 本の英語の版を *.en.md に置き、日本語の版と試験で突き合わせる)
  - 決めたこと（2026-11-07、利用者）: 英語にするのは README・SPEC・SKILL・始め方の案内の 4 本。日本語を正本とし、英語の版は訳として同じフォルダの `*.en.md` に置く（今のファイルの名前・試験・リンクは変えない）。両方の頭に正本と相手へのリンクを書く。README に言語の短い節を置く。英語の案内は同じ例の一式（日本語の欄名）を使い、説明だけを英語にする。
  - 確かめた記録（2026-11-07）:
    - README.en.md・SPEC.en.md・SKILL.en.md・docs/getting-started.en.md を足した。英語の版の頭に「Japanese original: …。the Japanese version is authoritative」、日本語の版の頭に「English: …（正本はこの日本語の版で、英語の版は訳である）」を置いた。
    - 訳し方: 欄の名前と値は、正の日本語に英語の別名を括弧で添えた（例 逐語 (verbatim)）。道具が読み書きする JSON・設定の例・期待する出力・抜き書きと引用の例は日本語のまま写し、括弧で英語の意味を添えた。SKILL.en.md は頭の name と description も英語にし、skill として使うときは SKILL.md の代わりに置けると書いた。設計書 docs/design-0.3.0.md は訳していない（日本語だけと書いた）。
    - README（両方の版）に「言語」の節を置いた: 文書の正本は日本語、出力の文はいまは日本語だけで翻訳の仕組みは持たない、替えたい人は cite_bridge/ の中の文を直す（出力の文は §11.1 の約束の外で、場所と文言は変わりうる）、欄の名前と値は英語の別名で書け、導く欄の名前は `[output] language = "en"` で英語になる、英語の原稿は sentence_end を替える。README の文書の表の後に英語の版があることを書いた。
    - README.en.md の「Using it with an AI agent」の写すブロックは、正本の SKILL.md と SPEC.md を指す（日本語のまま AI が読む。英語の版を指したければ替えてよいと書いた）。
    - 英語の案内は、期待する出力を道具が出す日本語のまま載せ、各塊の後に英語の意味を添えた。英語の別名でも書けると冒頭に書いた。
    - CLAUDE.md の地図に、英語の版は訳で、日本語の版を直したら英語の版も直すと書いた。SKILL.md の試験の説明に test_getting_started.py と test_translations.py を足した。
    - 試験: tests/test_translations.py（4 組で、頭が正本と相手へのリンクを持つ、日本語の版の欧字だけのインラインのコードがすべて英語の版にある、コードの中のコマンドの名前とオプションの集まりが同じ、json・text・sh の囲みの塊が同じ、地の文の相対のリンクが実在する）。tests/test_getting_started.py は英語の案内も同じように通し、日本語の案内と同じファイルの中身・コマンド・期待する出力を持つことを見る。tests/test_spec.py の README のブロックの試験は英語の README にも当て、コマンドが日本語のブロックと同じことを見る。オプションを一つ消す、パスのコードを外す、の食い違いを試験が拾うことを確かめた（文書は変えずに、その場の文字列で）。`python -m pytest -q tests`: 181 passed（前は 174）。
    - 訳の文が正しいかは試験で見ていない（見るのはコマンド・オプション・コード・リンク・塊）。
    - 道具の本体は変えていないので、実データでの確認は走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C33 model の承認の理由と根拠を、人が閲覧できるようにする（公開の条件ではない） (2026-11-08、review の JSON の model_approval から md の節と承認の HTML の点線の枠に出す)
  - 決めたこと（2026-11-08、利用者）: 見せる場所は review の md と承認の HTML の両方で、review の JSON の引用に欄を一つ（`model_approval`）足して、そこから出す。見せる中身は、承認した者と日付、承認の理由、承認したときの本文と根拠が今と合うか（根拠は指紋しか残らないので合うかだけ）、本文が変わっていれば `@承認時の本文`。出すのは model の承認（承認者の一覧で model の者の承認と、書き手と同じモデルの承認）だけで、本文が変わって要再確認になったものも含む。新しい記録の欄は足さない。review の JSON は固める範囲の外（§11.1）なので、C27 との順の問題は無い。
  - 確かめた記録（2026-11-08）:
    - cite_bridge/review.py に model_approval_of を足した。`承認` の先頭の者が、書き手と同じモデル（self_check_problem）か一覧で model（model_approval_problem）なら、`{by, date, note, why, text, evidence, approved_text}` を返す。text と evidence は approval_state と同じに記録の指紋で比べ「合う／変わった」（根拠の記録が無い古い承認は evidence が「記録が無い」）、approved_text は本文が変わったときだけ `@承認時の本文`。ほかの承認と未承認・差し戻しは None。状態の決め方（approval_state・uncounted_approval）は変えていない。
    - md: 本文の後に「### model の承認（承認済には数えない。人の承認の材料）」の節（承認・数えない理由・承認の理由・承認したときの本文・承認したときの根拠）。本文が違えば承認したときの本文を引用の形で並べる。この節を出すときは、引用の欄の並びから `承認` と `承認の理由` を外して重ねない。
    - 承認の HTML: 本文の後に、AI が出したものの点線の枠（既存の `.ai`、class に `mappr`）で同じ並びを出す。承認したときの本文は blockquote。この枠を出すときは、カードの下の欄の並びから `承認の理由` を外す。ひな形（review.html・review.js）は変えていない。
    - SPEC.md §3.2 に、数えない承認は人の承認の材料として何を見せるかと、`model_approval` の欄の名前を書いた。SKILL.md の承認者の一覧の段に、そこで model の承認の理由と合うかが見えること、承認の理由は人が読んで判断できるように書くことを足した。英語の版（SPEC.en.md・SKILL.en.md）も同じに直した。
    - 版は上げていない（固める範囲のデータは変わらず、review の JSON に欄を足しただけ）。
    - 試験: tests/test_bridge.py の test_model_approval_record_is_shown（model が理由つきで承認すると、JSON の model_approval が者・理由・数えない理由・合う・合う、md に節と並び、理由は一度だけ、HTML に点線の枠と理由。本文を直すと要再確認で text が変わった、approved_text が前の文、md に「今と違う」と前の文、HTML に「今と違う」。人が承認すると model_approval は None で、md に節が出ない）。`python -m pytest -q tests`: 186 passed（前は 185）。
    - 実データでの確認（読むだけ）: check は exit 1 で、ERROR は許してある「ms_dictate_word_web#e3: 導く欄が古い」だけ、NOTE 35、承認済 23。grade・coverage・classify --list・review --source-checks -o（一時フォルダ）が exit 0。review --json -o と review --html -o（一時フォルダ）が exit 0 で、既定の確認待ち 13 件に model_approval の付く引用は無い（原稿に model の承認は無い）。原稿のリポジトリの git status は空のまま。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C34 model の承認の引用を、review の確認待ちに出す (2026-11-07、review と承認の HTML も check と同じに数え、未承認として既定の確認待ちに出す。0.4.1)
  - 決めたこと（2026-11-07、利用者）: 数えない承認（承認者の一覧で model の者の承認、書き手と同じモデルの承認）の引用は、review の JSON・md・承認の HTML で `state` を「未承認」にし、`state_detail` に「承認を数えない（<check と同じ理由>）」を入れる。新しい状態の値は足さない。review の JSON は固める範囲に入れず、SPEC §3.2 に一文書く。版を 0.4.1 に上げる。
  - 確かめた記録（2026-11-07）:
    - cite_bridge/manuscript.py に uncounted_approval（approval_state が承認済とした承認を数えない理由。書き手と同じモデル §5.8、次に model の承認 §3.2）を足し、check と review が共通に使う。check の NOTE の文と数え方は前と同じ。review は数えない承認の引用を未承認にし、補足に理由を入れるので、needs_review が確認待ちとし、md（「## c001　未承認（承認を数えない（…））」）・JSON・承認の HTML（data-done="0"、状態の横に補足）の既定に出る。
    - 外の表示 md2docx の review_html.py（原稿のリポジトリにある。読むだけで確かめた）は state の値ごとに印の重さを決め、集計を 5 つの状態の並びで出す。「未承認」なので直さずに動き、集計にも入る。
    - SPEC.md と SPEC.en.md: 版を 0.4.1 に（冒頭と §8 の例）。§3.2 に review と承認の HTML も check と同じに数えると書いた。§11.3 に 0.4.1 の項（欄・形式名・指紋・ファイルの状態は変わらず、移行の手順は要らない。外の表示には未承認として渡る）を足し、0.4.0 の移行の手順 2 の回り道に「0.4.1 からは既定の確認待ちに未承認として出る」と書き足した。SKILL.md と SKILL.en.md の承認者の一覧の段に、review と承認の HTML も同じに数えると足した。config.py の TOOL_VERSION を 0.4.1 にした。
    - C31 で見つけた崩れも直した: 抜き書きが 0 件のとき、check は後ろの空いた「抜き書きの要約の確認: 」の行を出さない。
    - 試験: tests/test_bridge.py の test_model_approval_is_pending_in_review（model だけの承認で、review --json の既定に c001 が未承認と理由つきで出る、md の見出しに理由が出る、承認の HTML のカードが data-done="0" で補足が出る、人が承認すると既定から外れ --all で承認済になる）と test_check_has_no_empty_summary_line。`python -m pytest -q tests`: 183 passed（前は 181）。
    - 実データでの確認（読むだけ）: check は exit 1 で、ERROR は許してある「ms_dictate_word_web#e3: 導く欄が古い」だけ、NOTE 35、承認済 23、「承認を数えない」0（原稿に model の承認は無い）。grade・coverage・classify --list・review --source-checks -o（一時フォルダ）が exit 0。review --json -o（一時フォルダ）の既定の確認待ちは 13 件で、数えない承認の引用は無い。原稿のリポジトリの git status は空のまま。
    - 書き手と同じモデルの承認は approve が断るので、review の試験は model の承認だけで見た（書き手と同じモデルの理由は check の既存の試験が見る）。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。
- [x] C35 公開の前に、レビューを受けずに閉じた変更をまとめてレビューする (2026-11-08、/code-review を 2 回かけ、不具合 6 件を直し、--citations の文書を実際に合わせた)
  - 決めたこと（2026-11-08、利用者）: 範囲は 17 項目の差分ではなく、道具の今のコード全体（`cite_bridge/`・`bridge.py`・`hooks/`）。17 項目は互いに触れ合っているので、全体のほうが漏れにくい。やり方はこのセッションの /code-review。指摘の直しもこの項目に含める。
  - 決めたこと（2026-11-08、利用者。レビューの指摘を見て）:
    - 既に決めたことに合わせて直す 5 件: 抜き書きの ID が重なるときは要約の確認と原本での確認を書かずに断る（C15 の引用のブロックと同じ）。`@承認時の本文` は改行を空白にして一行で書く。承認者の一覧の種類は same_name で引く（C20）。承認時の指紋が無い model の承認は、本文を「記録が無い」と見せる。候補の受け入れで承認か要約の確認が書けなかったら、失敗として返す。
    - 今数えている人の承認（本文も根拠も今と合う）がある引用には、model の者の承認を書かずに断る。要再確認・差し戻し・未承認の引用には今のまま書ける。差し戻しは変えない。
    - `--citations` は文書を実際に合わせる。替わるのは引用のファイルと、明示していない 4 つの記録だけ。抜き書き（要約の確認と原本での確認を含む）とチェックポイントは元のものを使い、候補を受け入れたときの印は引用のファイルの `対象` が指す原稿に書く。写しで試すときは原稿も写して `対象` を写しに向ける。コードは変えない。
    - 整理の指摘は、model の承認を数えない理由を決める処理の二重（review の model_approval_of と manuscript の uncounted_approval）だけを一つにする。ほかは直さない（下の一覧に理由）。
  - 確かめた記録（2026-11-08）:
    - レビューは /code-review（high）を 2 回。1 回目は `cite_bridge/`・`bridge.py`・`hooks/` の全体を指したが、直近の C14・C33・C34 が中心になった。2 回目は、コードを変えた C11・C12・C13・C15・C18・C20 のコミットが触れたファイル（approve・apply・check・manuscript・derive・config・review.js）を指した。C29 は hooks/ で 1 回目に入る。C16・C17・C27・C30〜C32 は文書と試験だけ。指摘はどれもコードを読んで確かめた。
    - 指摘の一覧:
      1. 直した: 承認者の一覧で model の者が承認すると、人の承認の行が消えた（approve.py の write_approval）。今数えている人の承認がある引用には断る。
      2. 直した: 抜き書きの ID が重なると、要約の確認と原本での確認が先のブロックに入り、後のブロックの同じ記録の行が黙って消えた（write_confirm・write_source_check）。重なりがあれば断る。
      3. 直した: `paragraph = "blank"` で二行にまたがる文が、改行のまま `@承認時の本文` に書かれ、ブロックが壊れた（sentence_at は二つ以上の空白だけを詰める）。記録は空白を詰めて一行にする。指紋は前と同じ文から計る。
      4. 直した: 承認者の一覧の種類を名前でそのまま引いていたので、手で書いた `claude` は一覧の `Claude`（model）に当たらず承認済に数えた。manuscript.py に approver_kind を足し、same_name で引く。self_check_problem と model_approval_problem が使う。一覧に有るかの検査（approver_problem、check の「一覧に無い」）は前のまま名前でそのまま比べる。
      5. 直した: 承認時の指紋が無い model の承認を、review が本文「今と違う」と出した。「記録が無い（承認時の指紋が無い）」と出す。状態（要再確認）は前と同じ。
      6. 直した: 候補の受け入れで、承認と要約の確認の書き込みの失敗を捨てていた（propose.py の apply_candidate）。ブロックと印を書いた後なので候補は受け入れ済みにし、apply は失敗として数える（終了コード 1）。
      7. 文書を合わせた: `--citations` は、抜き書き（要約の確認と原本での確認）・チェックポイント・候補の印の原稿を替えない。SPEC §9 の「写しで試した記録が元の記録に入らない」は 4 つの記録に限り、替わらないものと、写しで試すときは原稿も写して `対象` を向けることを書いた。README・SKILL と英語の版も同じに。
      8. 直した（整理）: model の承認を数えない理由を、review の model_approval_of と uncounted_approval が別に決めていた。manuscript.py の uncounted_reason に寄せた。
      9. 直さない: review_data が同じ文の指紋を二度計る（結果は同じで、小さな無駄だけ）。
      10. 直さない: hooks/pre-commit の既定のパスが二行にある（test_hook_finds_the_tool が既定の名前を見る）。
      11. 直さない: 同じ引用の ID のブロックが二つあると、mark_keys は後のブロックの key を使う（ID の重複は check の NOTE で `--strict` が止まり、重複を直せば消える）。
      12. 直さない: derive の human_check_reasons の quote の既定が空で、渡さないと「逐語が短い」になる（今の呼び手はどちらも渡す）。
      13. 直さない: write_remark と write_approval が引用のファイルと抜き書きを読み直す（速さだけ）。
    - 差し戻しは model の者でも今のまま書ける（1 は承認だけ）。
    - SPEC §3.2 に 1 と 4 を書き、SKILL の承認者の一覧の段に 1 を足した（英語の版も）。版は上げていない（固める範囲のデータと形式は変わらない）。
    - 試験: tests/test_bridge.py に test_model_approval_does_not_replace_counted_human_approval（1）、test_confirm_refuses_duplicate_excerpt_id（2）、test_approver_kind_ignores_case（4）、test_model_approval_without_fingerprint_says_no_record（5）、test_candidate_accept_reports_failed_record（6。重なった抜き書きで要約の確認を断らせる）を足し、test_latex_cite_with_id_comment に 3 を足した。コードの直しを外すと 6 つとも落ちる。`python -m pytest -q tests`: 191 passed（前は 186）。
    - 実データでの確認（読むだけ）: check は exit 0、ERROR 0、NOTE 36、承認済 22 / 要再確認 1（c008 の本文が承認の後に変わった。直す前のコードでも同じ数）。grade・coverage・classify --list・review --source-checks -o・review --json -o・review --html -o（一時フォルダ）が exit 0。原稿のリポジトリの git status は前後とも空。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。直しの差分はレビューを受けていない。利用者の指示で閉じた。
- [-] C36 公開するリポジトリに残す開発の記録を決める (却下 2026-11-08、台帳の記録はそのまま残すと利用者が決めた。原稿での確認の件数と ID だけで、どのみち git の履歴に残る)
- [x] C38 README を、何のための道具かがわかる短い入口にする (2026-11-08、249 行を 128 行にし、分類器と開発の段を docs/ の 2 本に移し、例を置いた)
  - 背景: README は 249 行で、目的の段（約 34 行）の後に、使い方の手引き、原本での確認の細かい規則、分類器（約 98 行。任意の機能）、実装の構成が積み重なり、版の経緯（「0.2.0 までの…」）、測った結果、試した pymupdf の版などの実装の記録も混じる（2026-11-08、利用者と読んだ）。項目を閉じるたびに該当の段へ書き足してきたため。公開すると最初に読まれる。
  - 決めたこと（2026-11-08、利用者）: 各文書はコンパクトで目的がはっきりしていること。役割は 5 つに分ける。README は何のため・誰向け・短い例・始め方・限界・文書の地図。始め方の案内（docs/getting-started.md）は今のまま。SKILL は使う AI の作法とコマンド（C39）。SPEC はデータの形だけ（C40）。新しく docs/classifier.md（分類器の使い方と文面の測り方）と docs/development.md（実装の構成、試験、設計書と台帳への案内。道具に手を入れる人向け）を置く。README に、原稿の一文と印・抜き書きのブロック・引用のブロック・本文を直すと要再確認に戻ることの短い例を置く（examples/first-citation/ から取る）。新しい 2 本にも英語の版を置く。順は C38 → C39 → C40 → C37。
  - 確かめた記録（2026-11-08）:
    - README は 249 行から 128 行に（英語の版は 131 行）。段は 何をする道具か・例・始め方・AI に使わせるとき・限界・文書・動かすのに要るもの・言語・ライセンス。「何をする道具か」の見出しは SPEC §11 が名前で指すので変えていない。128 行のうち、例と写すブロックのコードの塊が約 35 行。
    - 例: 原稿の一文と印、抜き書きの e1、引用の c001（案内の 3 と 4 の中身の一部）と、承認の後に本文を直したときの check の行「c001: 承認の後に本文が変わった。要再確認」。英語の版は塊を日本語のまま置き、地の文で欄の意味を添えた。
    - 移した先: 分類器の段は docs/classifier.md（設定・既定の型・型を足す・文面を測る・提供元を足す）。「それはまだ実装していない」は「承認の状態を下げる動作は持たない」に、`cite.strength` の測った結果は一文にした。実装の構成と試験の走らせ方（確かめた pymupdf の版を含む）、文書を直すときの決まり、設計書と台帳への案内は docs/development.md。原本での確認の段（委ねる決まりを含む）は SKILL の「要ヒューマンチェック」に同じ文があるので README から外し、限界の段から指す。構成の表、`--citations` の段、`extract --header-only`・`propose --key`・`--checkable` は SKILL にあるので外した。承認者の一覧で model の者の承認を数えない一行も SKILL にあるので外した。
    - 指し先を直した: SKILL の分類器のコマンドの注と委ねる決まりの見出し（README を指していた）、始め方の案内の「次に読むもの」、CLAUDE.md の地図（英語の版も）。
    - 試験: tests/test_getting_started.py の test_readme_example_matches_the_example_set（案内を最後まで通し、README と README.en の例の三つの塊が案内で作るファイルの中身にあること、本文を直すと check --strict が 1 で、例の text の行が出ること）。tests/test_translations.py の組に classifier と development を足した。`python -m pytest -q tests`: 192 passed（前は 191）。
    - 道具の本体は変えていないので、実データでの確認は走らせていない。
    - 完了条件の「100 行前後」は 128 行で、利用者がこのままでよいとした（例と写すブロックのコードの塊が約 35 行）。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。利用者の指示で閉じた。
- [x] C39 SKILL を、使う AI の作法とコマンドだけにする (2026-11-08、315 行を 275 行にし、試験の段と仕組みの説明を外し、SPEC と重なる段は指すだけにした)
  - 背景: SKILL は 315 行。道具に手を入れる人向けの「試験」の段や、README と同じ文の段（原本での確認を委ねる決まり）がある。何を外すかは、読んでからこの項目で利用者に訊く（2026-11-08、利用者）。
  - 決めたこと（2026-11-08、利用者。SKILL を読んで）: 道具の仕組みの説明と設計の理由（照合の段階の定義、頁の数え方、snapshot が拾う見出しと alt、網羅の印の三段の配り方、pdftotext を使わない理由など）は docs/development.md の「仕組みの覚え書き」に短く移し、使う人に効く事実はその規則の一行に残す。「まだ決めていない」は消す。SPEC と同じことを書いた段（承認の状態、model の承認を数えない規則の詳細、下書きの JSON の形、マニフェストの中身）は、SKILL に守ることを一行で書いて SPEC の節を指す。md2docx の行は、利用者の原稿の側の道具なので（CLAUDE.md の 7）、外の表示一般の言い方に替え、cite_bridge/review.py の docstring も同じにする。試験の段の一覧は捨てる（試験の名前と docstring が正で、development.md に走らせ方と文書の試験がある）。
  - 確かめた記録（2026-11-08）:
    - 段の並びを 保証と持ち主・書く欄と導く欄・要ヒューマンチェック・確認と承認・印の無い出典・hook・設定・コマンド・AI が守ること にした（「確認と承認」「印の無い出典」は、コマンドの後に並んでいた箇条を分けた見出し）。英語の版も同じ。
    - 外したもの: 試験の段（一覧は捨てた。走らせ方と文書の試験は docs/development.md にある）、設計書への一行（development.md にある）、「0.2.0 までの自由文の記録は有効でない」（SPEC §11.3 の範囲）、「サーバで判断を受ける形にするかは、まだ決めていない」、承認の HTML のカードの欄の並び、マニフェストの中身の列挙（SPEC §8 を指す）、下書きの JSON の要素の列挙（SPEC §6.2 を指す）、承認の五つの状態の列挙（SPEC §3.2 を指す）、model の承認を数えない規則の詳細（守ることの一行と SPEC §3.2）。
    - docs/development.md と英語の版に「仕組みの覚え書き」を足し、照合の範囲と段階、頁の数え方、pymupdf を使う理由、見出しの検出、頭書きと空行、snapshot が拾う見出しと alt と --rebuild、網羅の印の三段、作業票の句と key の候補の推し方を移した。
    - 使う人に効く事実は規則の一行に残した: 「含む文」を見て要約と言っていないことを書く（書く欄の段）、節が誤ったら抽出テキストの見出しを確かめる、snapshot の保存先、OCR のテキストの置き方、網羅は出典ごとで頁だけ・同書は繰り返し。
    - md2docx の行は「外の表示（差分のレビューなど）は review --json を読んで、本文の印に状態を出せる。依存は表示 → bridge の一方向」に替え、既定の名前 cite_review.html の話は外した。cite_bridge/review.py の docstring も「外の表示（差分のレビュー等）」にした（動きは変えていない）。
    - `python -m pytest -q tests`: 192 passed。道具の動きは変えていないので、実データでの確認は走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。利用者の指示（commit and continue）で閉じた。
- [x] C40 SPEC を、データの形だけにする (2026-11-08、使い方・画面・設計の理由の文を外し、分類器のアダプタの契約と鍵の読み方を docs/classifier.md へ移した)
  - 背景: SPEC は 512 行で、データの形の正本。使い方や設計の理由の文が混じる。何を外すかは、読んでからこの項目で利用者に訊く（2026-11-08、利用者）。固める範囲（§11.1）の欄と形式は変えない。
  - 決めたこと（2026-11-08、利用者。SPEC を読んで）: 使い方・画面・設計の理由の文は外す（SKILL か docs/classifier.md に同じことがあり、無いものは移す）。データの定義（数え方、欄の意味、review の JSON の model_approval の欄）は残す。§6.4 のアダプタの契約と鍵を読む順は docs/classifier.md へ移す。移行の手順（0.4.0・0.3.0）は §11.2 が §11.3 に書くと決めているので SPEC に残す。
  - 確かめた記録（2026-11-08）:
    - SPEC は 512 行から 498 行。もともとデータの形に絞れていたので、減りは小さい。
    - 外した文: 冒頭の設計書への指し先、§2.4.1 の `extract --header-only` が飛ばす場合と `--force` との組（コマンドの振る舞い。道具が理由を出す）、§3.2 の model の承認を md の節と HTML の点線の枠で見せることと、人の承認を model の承認で書き換えないこと（SKILL の確認と承認の段にある）、§4.1 の人の読みを独立の欄とする理由、§9 の「写しで試したこの 4 つの記録が元のものに入らない」と「写しで試すときは原稿も写す」（SKILL の設定の段にある）。
    - §3.2 の model の承認の見せ方は、review の JSON の `model_approval` の欄の定義に書き直した（`{by, date, note, why, text, evidence, approved_text}`、text と evidence は 合う / 変わった / 記録が無い、数える承認と未承認・差し戻しでは null）。
    - §6.4 の「アダプタの契約」と鍵を読む順を docs/classifier.md の「提供元を足す」と「設定」へ移し、§6.4 の末尾と §9 の表の classifier の行から指す。分類器の文書の前の設定の段落は環境変数の順が SPEC と逆（JEV_API_KEY が先）に書いてあったので、SPEC の順（TYPESAFE_API_KEY が先。実装の jev_key と同じ）にそろえた。
    - 欄・指紋・形式の表は変えていない。tests/test_spec.py は通る。英語の版（SPEC.en.md、docs/classifier.en.md）も同じに直した。`python -m pytest -q tests`: 192 passed。
    - 道具の動きは変えていないので、実データでの確認は走らせていない。
    - 閉じた時点の確認: チームを使わず、このセッションで実装した。レビューは受けていない。利用者の指示（commit and continue）で閉じた。
- [x] C37 実験的な 0.x として公開する (2026-11-08、v0.4.2 を付けて公開し、ログインせずに clone して始め方の案内を通した)
  - 背景: GitHub のリポジトリ hiatamaworkshop/cite-bridge は今 PRIVATE（2026-11-08、gh で確かめた）。始め方の案内の「0. 置く」は公開のリポジトリを submodule にするので、公開するまで他人は通せず、試験でも走らせていない（C31）。「公開に向けて」の段で「使い手を絞った 0.x の実験的な道具」と決めたが、README にその一文は無い。タグは一つも無い。
  - 決めたこと（2026-11-08、利用者）: 版は 0.4.1 のままで（0.4.1 からデータの形は変わっていない）、タグは `v0.4.1`。その後、C35 で承認者の一覧の種類の引き方（数え方）を直したので、config.py の「数え方の直しでも上げる」に従い 0.4.2 に上げ、タグは `v0.4.2` にすると決め直した（同じ日、利用者）。可視性は利用者が GitHub の設定で切り替える。このセッションは切り替える前の準備（README の一文、タグ）と、切り替えた後の確かめ（clone と案内）をする。README の一文の文面は、書いたものを利用者が差分で確かめる。GitHub の説明（今は日本語だけ）は決めていないので、この項目では触れない。
  - 確かめた記録（2026-11-08）:
    - README と README.en.md の説明の一行の後に、実験的な 0.x で AI と一緒に論文を書く人に向けていること、約束はデータの形と保証の文の二つだけで（「何をする道具か」の段を指す）、コマンドと出力の文は版ごとに変わりうることを書いた。
    - 版を 0.4.2 に上げた: config.py の TOOL_VERSION、SPEC と SPEC.en の冒頭と §8 の例、§11.3 に 0.4.2 の項（一覧の種類の引き方、人の承認を model の承認で書き換えない、`@承認時の本文` は一行。欄・形式名・指紋とファイルの状態は変わらず、移行の手順は要らない）。`python -m pytest -q tests`: 191 passed。
    - C38〜C40 の後、利用者が README の言い方を直し（「道具」を cite-bridge に、錨をアンカーに等）、別の AI の用語チェックを見て、用語の段（文献・原典・原本・出典・抜き書き・引用・本文）を足した。原典と原本は分けたまま定義し、「原本での確認」の欄の名前は変えていない。「錨」は文書・check の出力の文・試験から外した（逐語を拠り所にする意味はアンカー、人の読みが指すものは根拠の抜き書き）。英語の版も同じに直した。タグ `v0.4.2` はこのコミットに付け直した（非公開のうちに force push）。
    - 利用者が GitHub でリポジトリを public に切り替えた。`gh repo view` の visibility は PUBLIC。
    - 資格情報を使わずに（credential.helper を空、GH_TOKEN を外す）`git clone https://github.com/hiatamaworkshop/cite-bridge.git` ができ、main の先頭 080c0e6 にタグ `v0.4.2` が付いている。raw.githubusercontent.com の README も 200。
    - 新しい一時フォルダを git init し、案内の 0 のとおり公開のリポジトリを `git submodule add` で tools/cite-bridge/ に置き、例の一式を写した。案内の 3・4 のファイルを書き、期待する出力つきのコマンド 9 本（grade、check、derive、check、check --strict（1）、review c001、confirm、approve、check --strict（0））が、日本語と英語の案内のどちらでも期待どおりの終了コードと出力だった。
    - 閉じた時点の確認: チームを使わず、このセッションで行った。レビューは受けていない。

## 予定

C13・C15・C11 を決定にし、終えた（2026-11-06）。C21〜C26 と C28 を決定にした（2026-11-06）。
順の理由: C28 は他に依らず小さい。C22（keyline の読み）を C23（key の重複の行番号）より先にする。C21・C26・C25 はどれも check.py に触れるので続けて一つずつ行う。C24 は apply だけで他に依らない。
どれもデータの形（C27 で固める）と保証の約束（C16・C18・C20）を変えないので、後の決定で手戻りにならない。
C16 と C18 を決定にした（2026-11-06）。保証の文をそろえる項目で、C27（データの形を固める）の前に置く。C16 は文書と試験だけ、C18 は版を 0.4.0 に上げる。C14・C20 は設計を決めてから。公開に向けた順は「公開に向けて」の段にある。
C16 と C18 を終えた（2026-11-07）。C20 を決めて終えた（2026-11-07）。C27 を決めて終えた（2026-11-07）。C29 を決めて終えた（2026-11-07）。C30 を決めて終えた（2026-11-07）。C31 を決めて終えた（2026-11-07）。C32 を決めて終えた（2026-11-07）。公開に向けた順の案は C32 で終わる。C34 を決めて終えた（2026-11-07、0.4.1）。残る C33・C14 はどれも提案のまま。
C14 を決めた（2026-11-08）。再現した不具合で、本物の記録を守るので C33 より先にする。C14 を終えた（2026-11-08）。残る C33 は提案のまま。
C33 を決めて終えた（2026-11-08）。開いている項目は無い。
公開の前の点検として C35〜C37 を提案にした（2026-11-08）。C35 と C37 を決めた。C36 は記録をそのまま残すと決めて却下した。C37 はレビューの直しを含めて公開するので C35 の後。C35 を終えた（2026-11-08）。
公開の前に文書を目的ごとに分けて小さくする C38〜C40 を決めた（2026-11-08）。C37 はその後。C38 を終えた（2026-11-08）。C39 を終えた（2026-11-08）。C40 を終えた（2026-11-08）。C37 を終えて公開した（2026-11-08、v0.4.2）。開いている項目は無い。



## 項目

各項目の完了条件に共通する確かめ方:
- 全体の試験: 道具のフォルダで `python -m pytest -q tests` がすべて通る (`tests/test_review_js.py` は node が要る)。
- 実データでの確認: 利用者の原稿のリポジトリ (場所は CLAUDE.local.md) で、データを変えずに `check`、`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` (C3 より前は `review -o <一時フォルダの md>`) が最後まで走る。derive・extract・confirm・apply は走らせない。check の ERROR は「導く欄が古い」だけでよい (導く欄が増えるため)。それ以外の ERROR は実装の誤りとして直す。NOTE は増えてよい。
