# ロードマップ

開いている項目は末尾の「項目」に `### C<n>. 題` の節で書く。
- 見出しの直後に、例外の状態だけ `状態: 提案 | 保留(理由) | ブロック(理由)` を字下げせずに 1 行書く。行がなければ決定 (着手してよい)。
- 決定の項目は `#### 完了条件` (チェックボックスの並び) を持つ。依頼の `DONE WHEN` はここから写す。文言を変えるのは約束の変更なので、実装中は変えず、報告で提案する。
- 番号は使い回さない。終わったら節を消し、版の行を `[x] C<n> …` にして、確かめた記録をその下に書く。その項目を待つ `ブロック(C<n> の後)` の行も同じ片付けで外す (状態は進捗で、約束ではない)。
- 却下したら節を消し、`[-] C<n> 題 (却下 YYYY-MM-DD、理由 1 行)` を残す。
- 規則の検査は agent-hub の `npm run docs:check -- <この文書の絶対パス>`。

## 0.3.0: 要ヒューマンチェック、抽出の頭書き、孫引き、出典ごとの網羅

設計は [design-0.3.0.md](design-0.3.0.md)。項目の順は C1 → C2 → C3、C4 → C5、C6、最後に C7。

- [x] propose の `--key` と `--checkable` (設計 §8.2。c75ec03)
- [x] Web 資料の書誌の参照日と写しの取得日を check で比べる (設計 §8.3。c358d27)
- [x] C1 抽出の頭書きと抽出の診断 (設計 §4)
  - 確かめた記録（2026-10-22）:
    - 試験: `python -m pytest -q tests` が 84 件すべて通る（既存の 72 件と、tests/test_extraction.py の 12 件。§4.6 の 1〜7 を含む）。
    - 実データ（利用者の原稿のリポジトリ、読むだけ）: check は ERROR 7 件がすべて「導く欄（文献）が古い」（derive を走らせていないため。頭に抽出の診断の欄が増えた）。NOTE 7 件は「頭書きが無い」。grade は 105 件のうち機械で照合できるもの 45 件（前と同じ）。coverage・classify --list・review -o は最後まで走り、数は前と同じ。
    - OCR の文字の層: references の PDF 56 件を §4.2 の規則で走査し、当たったのは 7 件（設計の 7 件と一致）。
    - 未確認: `extract --header-only` を実データに当てること。原稿のリポジトリでは extract を走らせない決まりで、コピーで試す手は権限の判定で止まった。
    - 設計の変更: §4.4 の 2（頁の区切り）は、頭書きの pages が Source.pages() とも、改ページ文字 `\f` の数 + 1 とも違うときに診断する規則に書き直した（利用者が 2026-10-22 に承認）。最後の頁が空の PDF（work_efficiency）が、Source.pages() だけで比べると extract --force でも直らない NOTE になるため。
- [x] C2 要ヒューマンチェックと原本での確認の記録 (設計 §5.1〜§5.4、§5.6、§5.8)
  - 確かめた記録（2026-10-22）:
    - 試験: `python -m pytest -q tests` が 96 件すべて通る（既存の 84 件と、tests/test_human_check.py の 12 件。§5.10 の 1〜5・8・9、§5.8 の承認と候補の受け入れを含む）。
    - 実データ（読むだけ）: check は ERROR 11 件がすべて「導く欄（文献）が古い」（derive を走らせていないため）。要ヒューマンチェックの印は 4 件（kawahara2013 の近似一致、確認済 0）。NOTE 15 件は、抽出の診断の頭書き 7、kawahara2013 の 0.2.0 の自由文の記録 4（形でない）、根拠の NOTE 4。OCR の文字の層の印はまだ出ない（頭書きを足す移行の後に出る）。grade・coverage・classify --list・review -o は最後まで走り、数は前と同じ。
    - 未確認: confirm・apply・checkpoint を実データに当てること（確認のコマンドは読むだけの範囲で走らせない決まり）。
    - 設計の解釈（報告で確認）: §5.3-1 の 違う の問題の文は、「原本と違うと報告された。逐語を直して確かめ直す」とする（設計どおり。利用者が 2026-10-22 に承認）。INFO の「review --source-checks」は C3 で作ったコマンドを指す。
- [x] C3 review で要ヒューマンチェックを確かめる材料と依頼の JSON (設計 §5.5)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 110 件すべて通り、スキップは無い（前の 96 件、tests/test_source_review.py の 9 件、tests/test_review_js.py の JS の 5 件。node あり）。§5.10 の 6（依頼の JSON の形）と 7（JS の原本での確認）を含む。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 11 件がすべて「導く欄（文献）が古い」。要ヒューマンチェックの印は 4 件（kawahara2013 の近似一致、確認済 0）。`review --source-checks` の md と JSON、`review -o` の md、`review --html` が最後まで走る。md の要ヒューマンチェックの行と `confirm … --source` の命令は 4 件、HTML の入力は 4 件。grade・coverage・classify --list は前と同じ数。
    - 未確認: 承認の HTML を画面で開いて操作すること。JS の画面の部分（クリックと同じ抜き書きの同期）は、構文の確認（node --check）だけで、動かしていない。
    - 設計の解釈（報告で確認）: module.exports に missingSourceNotes と isStaleSource を足した（既存の名前は変えていない）。依頼の JSON の answer_example は、原稿と作った時刻だけ実値、by・saved・id・fingerprint は `<…>` のまま。候補の新しい抜き書きには原本での確認の入力を出さない（抜き書きの ID が無いため）。
- [x] C4 孫引きの欄 (設計 §6)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 123 件すべて通る（前の 110 件、tests/test_secondary_source.py の 13 件。§6.6 の 1〜6 を含む）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件で exit 0、NOTE 33 件、関連研究の INFO は 2 件（harada2006#e2、hua2026_typing_dissolution#e7。どちらも孫引きは無い）。grade・coverage・classify --list（--all を含む）・`review --source-checks -o` の md が最後まで走る。原稿の抜き書きには孫引きが無いので、孫引きの INFO と cite.attribution の一致は実データでは出ない（試験で確かめた）。
    - 未確認: 承認の HTML を画面で開き、「孫引き」の行を見ること（HTML は文字列の試験だけ）。原稿に孫引きを書いて実データで確かめること（原稿のデータは変えない決まり）。check の ERROR が 0 件になった理由（C3 の記録の「導く欄が古い」11 件は今は出ない）は確かめていない。derive は走らせていない。（後に確かめた: 原稿のリポジトリの 0b93ca9 で derive が走り、抽出の頭書きも足されていた。C7 の記録を参照。）
    - 設計の解釈（報告で確認）: 台帳に書く status は、孫引きを使わない今までの式のまま。一覧と review は今の記録から決める。値の中の語は「、」で分け、書誌の key と完全に一致するものだけを拾う（複数なら「元の文献は書誌にある（a、b）」）。cleared_by と compare は同じ型に置けない（_validate で断る）。候補の新しい抜き書きの 孫引き は空。tests/test_source_review.py の根拠の形に secondary を足した（既存の試験の形を review_data に合わせた）。
- [x] C5 check の分類器の数を classify --list とそろえる (設計 §7)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 125 件すべて通る（前の 123 件と、tests/test_classifier.py の新しい 2 件。材料（逐語）を変えた後と、引用が消えた後に、check と classify --list の判定・印・古い件数が一致する。§7.5 を含む。マニフェストの件数も check と一致する）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件。分類器は 判定 8 件のうち印 2 件、古い判定 8 件（classify --list も同じ 8・2・8）。check で run_check は一度だけ走る（呼び出しを数えて確かめた）。grade・coverage は HEAD と同じ出力。`review --source-checks -o` の md が最後まで走る。
    - 未確認: checkpoint で run_check が二度走らないことは、コードを読んだことと試験（checkpoint の試験で件数が一致する）で確かめた。実データの checkpoint は、マニフェストを書くので走らせていない。
    - 設計の解釈（報告で確認）: 単位が無くなった判定に加えて、型が登録から外れた判定（cite.strength の 3 件）も古いに数える。以前は黙って飛ばしていた。試験の import の規則は、check から review への関数の中の import だけを例外にした（§7.3 の形を固定するため）。classify --list --cids で絞ると、絞り外の判定が古いに数えられる。
- [x] C6 出典ごとの網羅 (設計 §8.1、§8.2 の 2)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 138 件すべて通る（前の 125 件、tests/test_coverage.py の 13 件。§8.1 の 9 の 1〜8 と、--checkable で repeat の件が外れる試験、除外の part の試験を含む）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件で exit 0。網羅の INFO は「出典らしきもの 92（括弧 85）のうち、印のあるもの 24、印の無いもの 68」（前は括弧 79 のうち 18・61）。増えた分は、出典ごとに分けた 7 件（DSCR、StepWrite、W3C、Smartbox、緒方・後藤、WISS、Zhu の「（…; …）」）と、頁だけ・同書の括弧 6 件（いずれも直後に印があり、印ありになる）。Smartbox の括弧は、印の key が二つ目の出典なので、一つ目が印の無いものになる。grade・classify --list は前と同じ出力。`review --source-checks -o` の md が最後まで走る。
    - 未確認: propose --checkable を実データに当てること（作業票を原稿のリポジトリに書くため、走らせていない）。checkpoint の manifest の parens は試験で確かめた（実データの manifest は書いていない）。
    - 設計の解釈（報告で確認）: 出典の番号 part は 0 から。表示は k/n（k = part + 1）。一件の括弧の source は括弧の中身。書誌を渡さないときも、括弧の分けと repeat は働く（印の判定だけが今と同じ）。実データでは、一件の括弧の印の有無と除外が HEAD と一致する（分けた括弧を除く）。propose は --checkable 以外では repeat の件も作業票に出す（§8.2 の 2 のとおり）。作業票の見出しは、同じ括弧の出典どうしで括弧が同じ文字列になる（item の ID で区別する。作業票の形は変えていない）。
    - 今の実装のまま採り、記録だけ残した判断（2026-10-23、利用者）:
      - 頁だけ・同書の括弧（repeat）を --checkable なしの propose の作業票にも出す。key の候補は括弧の前の 30 字から取るので外れやすい。作業票は人が見て選ぶ候補なので、外れても害は小さいとみた。外れが目立てば、repeat の件を作業票から外すか、候補の取り方を見直す。
      - 括弧の直後の印が文の外（「。」の後）にある形で、余った印の数え方が以前と変わった（設計の文言に合わせた）。実データに当たる例はない。例が出たら数え方を見直す。
- [x] C7 0.3.0 の文書と版 (設計 §9、§5.7)
  - 確かめた記録（2026-10-23）:
    - 試験: `python -m pytest -q tests` が 138 件すべて通る。この項目で試験は足していない（TOOL_VERSION を固定する試験も、文書の文言を見る試験も無い）。
    - 実データ（読むだけ、出力は一時フォルダ）: check は ERROR 0 件で exit 0。網羅は C6 と同じ（出典らしきもの 92（括弧 85）、印のあるもの 24、印の無いもの 68）。grade・coverage・classify --list は C6 と同じ出力。`review --source-checks -o` の md と `review --source-checks --json -o` の依頼（cite-bridge-source-checks/1、13 件）が最後まで走り、依頼の鍵と answer_example の鍵が SPEC §5.1 の形と一致する。
    - 基準線: 原稿のリポジトリの 0b93ca9（2026-10-23）で、derive と抽出の頭書きの移行（SPEC §11 の 0.3.0 の移行の手順 1〜2）が済んでいた。check の ERROR が「導く欄（文献）が古い」11 件から 0 件になったのは、これによる。
    - 未確認: checkpoint の manifest の新しい鍵（by、source_checks、coverage.parens）を実データで書くこと（原稿のリポジトリに書くため走らせていない）。鍵の並びはコードを読んで SPEC §8 と合わせた。外部の AI に依頼を回して判断ファイルを受け取る流れは、まだ一度も回していない。
    - 設計の解釈・違えた点（報告で確認）: (1) SPEC §8 の例に、設計 §5.6 の by と §5.3 の source_checks を足した。(2) §11 の版の方針は、設計 §9-3 のとおり、1.0 より前は既存のファイルの状態が変わる変更でも副版を上げる、に書き換えた（前の「主版を上げる」の文を替えた）。(3) 依頼の JSON の節は SPEC §5.1 に置いた（設計は節の場所を決めていない）。(4) SKILL の試験の段落の「70件」は古いので外した。(5) README と SKILL に、0.2.0 までの論文固有の記述が残っている（README の「この道具を作った論文では」の二文、thesis のパス、SKILL の 2026-10-16 の例など）。CLAUDE.md の規則 7 に照らして別途判断する。この項目では触れていない。

## 項目

各項目の完了条件に共通する確かめ方:
- 全体の試験: 道具のフォルダで `python -m pytest -q tests` がすべて通る (`tests/test_review_js.py` は node が要る)。
- 実データでの確認: 利用者の原稿のリポジトリ (場所は CLAUDE.local.md) で、データを変えずに `check`、`grade`、`coverage`、`classify --list`、`review --source-checks -o <一時フォルダの md>` (C3 より前は `review -o <一時フォルダの md>`) が最後まで走る。derive・extract・confirm・apply は走らせない。check の ERROR は「導く欄が古い」だけでよい (導く欄が増えるため)。それ以外の ERROR は実装の誤りとして直す。NOTE は増えてよい。
