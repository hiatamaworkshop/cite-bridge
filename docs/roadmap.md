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
- [ ] C11 承認の HTML が、要約が変わった後の要約の確認を戻さない
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
- [ ] C14 --citations で写しを指したときの記録の置き場
- [x] C15 引用のブロックの ID の重複を確認待ちにする (2026-11-06、重複は NOTE にして書き込みを断る)
  - 確かめた記録（2026-11-06）:
    - cite_bridge/check.py の run_check: 引用のブロックの loop で、同じ ID の二つ目以降に `notes` を足す（先の行は最初のブロックの行）。ERROR は増やしていない（CLAUDE.md の規則 4）。出力は既存の NOTE と同じ経路なので、行は `NOTE  <パス>:<行> <ID>: …` になり、NOTE の後に空白が二つ入る。
    - cite_bridge/approve.py の `_citation_now`: 同じ ID のブロックが二つ以上なら `(None, "<パス> に <ID> のブロックがちょうど一つ無い（<n> 個）")` を返す。n = 0 の「ブロックが無い」の文言は変えていない。`write_approval` は `<ID>: ` を付け、`write_remark` は `_citation_now` を通るので同じ理由になる。apply は decisions の approve と remark をそれぞれ SKIP に入れ、残りを処理する。`_replace_block_lines` で引用のブロックを書くのは `write_approval` と `write_remark` だけで、どちらも `_citation_now` の後に走る（確かめた）。候補の受け入れは新しい ID のブロックを末尾に足すだけなので、重複を作らず、この変更の対象外（確かめた）。
    - 試験: tests/test_bridge.py の test_duplicate_citation_block_is_a_note_and_writers_refuse（check が NOTE を出し、--strict は exit 1、approve と指摘の apply が理由つきで断り、引用のファイルは変わらない）と test_apply_skips_duplicate_block_and_writes_the_rest（重複した c001 は SKIP、別の ID の c002 は承認を書く、applied.json は written 1・skipped 1）。
    - `python -m pytest -q tests`: 147 passed（前は 145）。
    - 実データ（読むだけ。thesis のフォルダを作業フォルダにして `python <cite-bridge>/bridge.py <cmd>`）: `check` は exit 0、ERROR 0 件、「ID の重複」の NOTE は 0 件（thesis の引用に同じ ID のブロックは無い）。`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` も exit 0。checkpoint・apply・derive・extract・confirm は走らせていない。
    - SPEC.md と README.md は変えていない。NOTE の全部の一覧はどちらにも無い（C13 と同じ）。
    - 閉じた時点の確認（leader）: git diff を確かめ、`python -m pytest -q tests` は 147 passed。レビュアーは接続していなかったので、この項目はレビューを受けていない。
- [ ] C16 指示の引用の欄と承認を SPEC とそろえる
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
- [ ] C18 model の承認と、README の「人の承認が保証する」をそろえる
- [-] C19 レビューで見つけた小さな崩れ (却下 2026-11-05、1 項目 1 依頼にするため C21〜C25 に分けた)
- [ ] C20 短い逐語の照合と、確認者の名前の比べ方
- [ ] C21 判定の台帳の読めない行で止まらない
- [ ] C22 keyline の書誌で、先頭の key の行を読み違えない
- [ ] C23 書誌の key の重複を確認待ちにする
- [ ] C24 apply が件ごとにすべての抜き書きを導き直さない
- [ ] C25 check.py の潰れた行と、SPEC §6.4 の鍵の受け方

## 予定

C13・C15・C11 を決定にした（2026-11-05）。残りの順の案: C21 → C22 → C23 → C24 → C25。C13 と C15 は check の NOTE と書き込みの断りで小さく、C11 は C10 の次に重い穴だが JS で画面の確認が残る。C14・C16・C18・C20 は設計を決めてから。

- [ ] C11

## 項目

各項目の完了条件に共通する確かめ方:
- 全体の試験: 道具のフォルダで `python -m pytest -q tests` がすべて通る (`tests/test_review_js.py` は node が要る)。
- 実データでの確認: 利用者の原稿のリポジトリ (場所は CLAUDE.local.md) で、データを変えずに `check`、`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` (C3 より前は `review -o <一時フォルダの md>`) が最後まで走る。derive・extract・confirm・apply は走らせない。check の ERROR は「導く欄が古い」だけでよい (導く欄が増えるため)。それ以外の ERROR は実装の誤りとして直す。NOTE は増えてよい。

### C11. 承認の HTML が、要約が変わった後の要約の確認を戻さない

承認の HTML は、要約の確認の印を ID だけで localStorage に残し（templates/review.js の collect）、読み戻すときに古さを見ず（restore）、保存のときにその時点の要約の指紋を付ける（buildOutput）。前の HTML で印を付けた抜き書きの要約が後で変わっても、作り直した HTML で印が戻り、人が見ていない要約への確認として apply を通る。判断（isStale）と原本での確認（isStaleSource）には古さの検査があり、要約の確認だけに無い（コードを読んで確認。画面では動かしていない）。

#### 完了条件
- [ ] 要約の確認の印を、印を付けたときの要約の指紋と一緒に残す
- [ ] 読み戻すとき、残した指紋が今の要約の指紋と違う印と、指紋を持たない前の形の印を戻さない
- [ ] tests/test_review_js.py に、指紋の違う印と前の形の印が戻らない試験を足し、全体の試験が通る
- [ ] localStorage の形を変えた点を報告に書く（SPEC の形式には入っていない）

### C14. --citations で写しを指したときの記録の置き場
状態: 提案

`applied.json`・`candidates`・`excluded.json`・`judgments.jsonl` の既定の置き場は、設定を読むときの引用のファイルのフォルダで決まり、`--citations` で替えても追わない。写しで試した apply の記録が元の `applied.json` に入り、同じ判断ファイルを本物に当てると「適用済み」で断られる（2026-10-31 に再現）。

決めること: `--citations` に追わせるのはどの置き場か（台帳は写しと共有したいかもしれない）。設定で置き場を明示したときは追わせないか。決めた形は SPEC §9 に書く。

#### 完了条件
- [ ] 決めた置き場が、`--citations` の引用のファイルのフォルダに従う
- [ ] 写しを指して apply しても、元の `applied.json` が変わらない試験を足し、全体の試験が通る
- [ ] SPEC §9 と README の `--citations` の説明が実装と合う

### C16. 指示の引用の欄と承認を SPEC とそろえる
状態: 提案

SPEC §3.1 は 理由・記入・承認 をすべての引用に要るとするが、check は指示の引用でこれらを見ず、承認の状態も数えない（review も指示を確認待ちに入れない）。理由も記入も無い指示の引用で check が通る（2026-10-31 に再現）。

決めること: 実装を SPEC に合わせる（指示も 理由・記入 を NOTE で求め、承認を求めるか）か、SPEC を実装に合わせる（指示は承認を要らないと書く）か。既存のファイルの状態が変わるなら、SPEC §11 に従い副版を上げ、移行の手順を書く。

#### 完了条件
- [ ] 指示の引用の 理由・記入・承認 の扱いが、SPEC §3.1 と check と review で同じになる
- [ ] 決めた扱いの試験を足し、全体の試験が通る
- [ ] 実データでの確認が通る。NOTE が増えたら件数を報告に書く

### C18. model の承認と、README の「人の承認が保証する」をそろえる
状態: 提案

README は「原典が主張を支えているかは、人の承認が保証する」と書く。実装は、書き手と名前が違えば承認者の一覧の model の承認も「承認済」とし、`check --strict` と `checkpoint` も通す（承認者の種類ごとの数はマニフェストに残る）。設計（用語の「確認者」と §5.8）は、model が承認できることを前提に、書き手と分けることを決めている。README の文とこの前提が食い違う。

決めること: (a) model の承認を数えるのが意図なら、README の文を実装に合わせる。(b) 人の承認だけを数えるなら、model の承認を check で確認待ちにする（承認者の一覧があるときだけ）。(b) は既存の承認の状態が変わるので、副版を上げ、移行の手順を書く。

#### 完了条件
- [ ] README・SPEC・SKILL の承認の説明と、check の承認の数え方が同じことを言う
- [ ] (b) を選んだときは、model の承認が確認待ちになる試験を足す
- [ ] 全体の試験と、実データでの確認が通る

### C20. 短い逐語の照合と、確認者の名前の比べ方
状態: 提案

`逐語: the` のような短い逐語も、抽出テキストのどこかに当たれば「一致」になり、逐語の所在を保証しない。また、書き手と確認者を分ける規則（設計 §5.8）は名前の完全一致で比べるので、`Claude` と `claude` のような書き違いで分離が外れる。どちらも事故の範囲の穴である。

決めること: 短いとみなす長さ（字数か語数、和文と欧文で分けるか）と、そのときの扱い（要ヒューマンチェックの理由に足すか、check の NOTE か INFO か）。名前を比べるときの正規化（大文字と小文字、全角と半角、前後の空白）。

#### 完了条件
- [ ] 決めた長さより短い逐語が、決めた扱いで出る
- [ ] 書き手と確認者の名前を、決めた正規化をしてから比べる
- [ ] それぞれの試験を足し、全体の試験が通る
- [ ] 実データでの確認が通る。印や NOTE が増えたら件数を報告に書く

### C21. 判定の台帳の読めない行で止まらない
状態: 提案

判定の台帳（judgments.jsonl）に JSON として読めない行が一行でもあると、check・checkpoint・classify が止まる（C19 から分けた。2026-10-31 のレビュー）。

#### 完了条件
- [ ] judgments.jsonl に読めない行があっても、check・checkpoint・classify が最後まで走り、その行を飛ばす
- [ ] 飛ばした行があるとき、check が `INFO <パス>: 判定の台帳の読めない行を <n> 行飛ばした（<行番号の並び>）` を出す
- [ ] 読めない行を含む台帳の試験を足し、全体の試験が通る
- [ ] 実データでの確認が通る

### C22. keyline の書誌で、先頭の key の行を読み違えない
状態: 提案

keyline の書誌で `key:` の行がファイルの先頭にあると、最後の行を書誌の行として読む（C19 から分けた。2026-10-31 のレビュー）。

#### 完了条件
- [ ] `key:` の行がファイルの先頭にある keyline の書誌で、各 key の書誌の行が、その `key:` の行の直後の行になる
- [ ] 先頭に `key:` の行がある書誌の試験を足し、全体の試験が通る
- [ ] 実データでの確認が通る（grade と coverage の出力が前と同じ）

### C23. 書誌の key の重複を確認待ちにする
状態: 提案

書誌（keyline・BibTeX・CSL-JSON）に同じ key が二つ以上あると、後のもので黙って上書きする（C19 から分けた。2026-10-31 のレビュー）。

#### 完了条件
- [ ] 書誌に同じ key が二つ以上あると、check が二つ目からごとに `NOTE <パス>:<行> <key>: 書誌の key の重複（先は <行> 行）` を出す。行の無い形式（CSL-JSON）では `<行>` の代わりに何件目かを出す
- [ ] 三つの形式それぞれで重複の試験を足し、全体の試験が通る
- [ ] 実データでの確認が通る。NOTE が増えたら件数を報告に書く

### C24. apply が件ごとにすべての抜き書きを導き直さない
状態: 提案

apply で要約の確認と原本での確認を何件も書くとき、件ごとにすべての抜き書きを導き直す（C19 から分けた。2026-10-31 のレビュー）。

#### 完了条件
- [ ] apply で要約の確認と原本での確認を何件書いても、導き直しは書いた抜き書きのファイルごとに一度だけになる
- [ ] 導き直しの回数を数える試験を足し（C5 の run_check の数え方にならう）、書いた結果が前と同じことも確かめ、全体の試験が通る

### C25. check.py の潰れた行と、SPEC §6.4 の鍵の受け方
状態: 提案

check.py の Web の写しの取得日を読む行は、二行が一行に潰れている。SPEC §6.4 は「鍵は環境変数だけで受け」と書くが、実装は `.env`（bridge.toml の場所と作業フォルダ）も読む（C19 から分けた。2026-10-31 のレビュー）。

#### 完了条件
- [ ] check.py の Web の写しの取得日を読む行を、一行に一つの文の形に直す。check の出力は変わらない
- [ ] SPEC §6.4 の鍵の受け方を、`.env` も読む実装（読む場所と順）に合わせて書く
- [ ] 全体の試験が通る
