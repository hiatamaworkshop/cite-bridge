# cite-bridge data format specification

Japanese original: [SPEC.md](SPEC.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

This document is the authoritative definition of the formats of the files the tool reads and writes. Where it disagrees with the implementation (bridge.py and cite_bridge/), fix the implementation or this document so that they agree.
How to use and run the tool is in SKILL.md.

- Format version: 0.5.0 (`TOOL_VERSION` in cite_bridge/config.py). It is recorded in the manifest. What is frozen, how changes are made, and migration steps are in §11.
- Character encoding is UTF-8; line endings are LF.
- Japanese field names and values are canonical; English aliases are also accepted (§10). Internally everything is normalized to Japanese.
  In this translation, field names and values are given in Japanese with the English alias in parentheses, e.g. 逐語 (verbatim).

## 1. Files and owners

| File | Owner | Contents |
|---|---|---|
| Settings `bridge/bridge.toml` | The user | Paths, how to read the bibliography, approvers, mark format (§9) |
| Bibliography | The user (keyline / bibtex / csl-json) | Keys and their mapping to original PDFs and URLs |
| Excerpts `<excerpts>/<key>.md` | The writer (fields) and the tool (@ lines) | Verbatim text and summary of each passage of a source (§2) |
| Citations `<citations>` | The writer (fields) and the tool (@ lines) | Each citation in the manuscript (§3) |
| Extracted text `<text_dir>/<name>.txt`, web copies `<web_dir>/<key>.txt` | The tool | What is matched against (§8). Starts with a header (§2.4) |
| Decisions files, source-check requests, worksheets, drafts, candidates | The approval HTML / the writer / the tool | Human decisions and candidate making (§5–§7). Requests are handed to an external AI or a person (§5.1) |
| `applied.json`, `excluded.json` | The tool | Record of applied files; parentheses judged not to be citations (§7) |
| `judgments.jsonl` | The tool | Ledger of classifier judgments (§6.4) |
| `checkpoints/<UTC>.json` | The tool | Manifest (§8) |

Lines starting with `@` are written by the tool. Do not edit them by hand. The tool writes two kinds of lines: derived fields are rebuilt on every check, and record fields (§2.3, §3.3) are kept and never erased.
The 原本での確認 (source_check) field (§2.1) is written only by `confirm --source` or `apply` (it needs a fingerprint, so do not write it by hand).

A bibliography key is an identifying string; once used in an excerpt or a citation, do not change it. The key appears in the excerpt file name and heading, in excerpt IDs (`key#e1`),
in the citation fields `文献` (source) and `抜き書き` (excerpts), and in the evidence fingerprint (§4). Changing it breaks references, and every approval resting on that source returns to needing recheck.
The tool has no procedure for renaming keys. The year or name inside a key is only a label; do not fix it even if it drifts from the bibliography's edition or year.

## 2. Excerpts

One file per source. Under the heading `# <key>`, list blocks `## e1`, `## e2` … (IDs unique within the source).
Directly under the source heading, the tool writes `@格` (grade) and `@抽出` (text).

### 2.1 Written fields

| Field | Required | Value |
|---|---|---|
| 逐語 (verbatim) | Required | The range copied exactly as in the original. One line. Style rules do not apply |
| 強さ (strength) | Required | 観察 / 示唆 / 主張 / 一般化 / 条件付き (observation / suggestion / claim / generalization / conditional) |
| 要約 (summary) | Required | Written from the checked verbatim text. Nothing outside the original's range. Refer to other excerpts by ID (`e6`, `key#e6`) |
| 言っていないこと (not_said) | Required | What the original does not state. If it rests on another passage of the original, make that passage an excerpt too and refer to it by ID |
| 記入 (written_by) | Required | Who wrote it and the date |
| 原本での確認 (source_check) | When human check is needed (§2.2) | Checker, date, result, page and section, note (form below). Written by `confirm --source` or `apply` |
| 要約の確認 (summary_check) | Optional | Record that a person checked the summary, what it does not say, and the strength (who and date). Written by `confirm` |
| 孫引き (secondary_source) | Optional | The original work the verbatim text cites. A bibliography key, or author and year (`山田（1996）`). Separate several with 「、」. English alias secondary_source |

Form of the 原本での確認 (source_check) value:

```
原本での確認: <確認者> <YYYY-MM-DD> <一致 | 違う> [<頁と節>]（<メモ>）
```

(That is: checker, date, result 一致 (matches) or 違う (differs), optional page and section, and a note in full-width parentheses.)

- The result is `一致` (the verbatim text is in the original as written) or `違う` (it differs from the original, or was not found). With `違う`, a note is required and holds the characters of the original.
- A record is valid only when all five of the following hold.
  1. The value fits the form: the first word is the checker, then the date, then the result.
  2. If there is an approvers list, the checker is in it. If there is none, the checker is not 「確認者不明」 (unknown checker).
  3. If the checker's kind is model, the checker is independent of the writer of the excerpt. The writer is the first word of the 記入 (written_by) value, up to a space or a full-width or half-width parenthesis.
     The checker is independent only when all three of the following hold.
     - The checker's name differs from the writer's.
     - The checker has a family (`model:<family>` in the approvers list; §9).
     - The writer is in the approvers list. If the writer is a model, the writer also has a family, and it differs from the checker's family.
     When the writer is unknown, not in the list, or has no family, independence cannot be told, so the checker is not independent. A human writer is independent of any family.
     Names and families are compared after NFKC normalization of full-width and half-width forms, ignoring letter case, and without leading and trailing spaces (`Claude` and `claude` are the same; the recorded characters are not changed).
     The same rule applies to summary checks, approvals (§3.2) and candidate acceptance (§6.3). For an approval, the approver is compared with every writer of the citation and of its evidence excerpts.
     The tool refuses to write a model's record that fails this rule. A record written by hand is not counted, and check reports the reason as a pending NOTE.
     A human checker may be the writer (a human is finally responsible, and a single author is expected).
  4. `@原本での確認時の指紋` (source_check_fingerprint, §2.3) equals the current fingerprint of the verbatim text (§4).
  5. The result is `一致`.
- Free-text records from 0.2.0 and earlier fit neither the form nor the fingerprint and are not valid. The tool does not rewrite old records. Check again and record again.
  When a new record has no note and an old record exists, `前の記録: <古い値>` (previous record: old value) is kept as the note.

### 2.2 Derived fields

照合 (match), 所在 (location), 節の種類 (section_kind), 前 (before), 含む文 (sentence), 後 (after), 他の文献で一致 (also_found_in).

- 照合 (match): 一致 / 正規化で一致 / 正規化で一致（句読点・記号が異なる） / 近似一致（重なり N%） / 照合不能（格）
  (identical / matches after normalization / matches after normalization (punctuation and symbols differ) / approximate (N% overlap) / cannot be matched (grade)).
  Matching is done only within the extracted text bound to the key. A match in another source is shown only as a hint and is not used for matching.
- 所在 (location): page and section (`PDF 5頁目 / §3.3 …`, i.e. PDF page 5). Heading detection is an estimate.
- 節の種類 (section_kind): 序論 / 関連研究 / 方法 / 結果 / 議論 / 限界 / 結論 / 要旨 / 付録 / 参考文献 / 本論
  (introduction / related work / method / results / discussion / limitations / conclusion / abstract / appendix / references / body). Words can be added in the settings.
- 前 (before), 含む文 (sentence), 後 (after): as in the extracted text. Nothing is filled in.
- 要ヒューマンチェック (human_check; a derived field of excerpts, present only when there is a reason): the applicable reasons joined with 「、」. The reasons are: the match is approximate (「照合が近似一致」), not found by matching,
  cannot be matched (grade), OCR extraction, OCR text layer (with 「（PDF n頁目）」 when the page of the verbatim text is an OCR page), unreadable characters within the verbatim range, and short verbatim text.
  Short verbatim text (「逐語が短い」): matching found the verbatim text in the extracted text, and the text is short. A short text can match some place in the extracted text by chance; even if matching succeeds, the location is not guaranteed.
  If the text contains even one Japanese character (kana, kanji or a full-width character), it is short when it has 10 characters or fewer excluding spaces; otherwise, when it has 3 words or fewer separated by spaces.
  The field shows that the machine cannot guarantee the verbatim text exists. It stays regardless of records; whether the check is done is decided by the 原本での確認 (source_check) record (§2.1).
  A misplaced page break (extraction diagnosis 2, §2.4.2) is not a reason.

### 2.3 Record fields

- `@要約の確認時の指紋` (summary_check_fingerprint): the fingerprint of the excerpt (§4) at the time of the summary check. When the fields change, 「確認し直す」 (check again) is reported.
- `@原本での確認時の指紋` (source_check_fingerprint): the fingerprint of the verbatim text (§4) at the time of the check against the original. Editing the verbatim text invalidates the record, and the human check remains (the NOTE says 「確かめた後に逐語が変わった」, the verbatim text changed after the check).
  Written by the tool in `confirm --source` and `apply`. English alias source_check_fingerprint.

### 2.4 Source grades

Decided by the tool from the material the bibliography points to and the state of the extracted text.

PDF所持（抽出あり）/ PDF所持（OCR の抽出）/ PDF所持（OCR の文字の層）/ PDF所持（抽出が化けている 等）/ PDF所持（抽出なし）/
Web 写し（保存あり）/ Web 資料（写しなし）/ 未入手 / 書誌に無い
(PDF held (extracted) / PDF held (OCR extraction) / PDF held (OCR text layer) / PDF held (garbled extraction etc.) / PDF held (not extracted) /
web copy (saved) / web source (no copy) / not obtained / not in bibliography).
Only "抽出あり" (extracted) and "Web 写し" (web copy) can be matched by machine. An OCR extraction is marked by the header `<!-- ocr`, and its matches are often approximate.
An OCR text layer (an extraction containing pages listed in the header's ocr_pages) is not counted as machine-checkable either.

### 2.4.1 Header of extracted text

Extracted text written by extract starts with the following header, then one line break, then the body. The header is not matched against (it is replaced by spaces before normalization).

```
<!-- extract
pdf: <設定の pdf_dir からの PDF のファイル名>
sha256: <PDF のバイト列の sha256（16進）>
pages: <PDF の頁の数>
ocr_pages: <OCR の文字の層と判定した頁。例 1-7、2,5-6。該当が無ければこの行は無い>
extractor: pymupdf <版>
extracted: <YYYY-MM-DD>
-->
```

(pdf: the PDF file name relative to pdf_dir in the settings; sha256: the sha256 (hex) of the PDF bytes; pages: the number of pages of the PDF; ocr_pages: the pages judged to be an OCR text layer, e.g. 1-7 or 2,5-6, omitted when there are none; extractor: pymupdf and its version; extracted: the date.)

- Key and value lines are read with `^(\w+): (.*)$` (the same way as the header of web copies).
- `extract --header-only` adds a header made from the PDF to extracted text that has none (the body is unchanged). That header has `extractor: 不明（頭書きは後から足した）` (unknown; header added later) and, in place of `extracted:`, `annotated: <YYYY-MM-DD>`.
- A page belongs to an OCR text layer when it meets both: (1) invisible characters (render mode 3) make up half or more of its characters; (2) images cover 80% or more of the page area.

### 2.4.2 Extraction diagnoses

Only breakages of extracted text with a known fix are diagnosed. Web copies and `<!-- ocr` text are not diagnosed.

| No. | Condition | Message | Where |
|---|---|---|---|
| 1 | The PDF is in the folder and the extracted text has no header | 頭書きが無い（extract --header-only で足す） (no header; add with extract --header-only) | NOTE of check |
| 2 | The header's pages differs both from the number of pages (not counting trailing empty pages) and from the number of form feeds in the body + 1 | 頁の区切りが PDF と合わない（extract <key> --force で作り直す） (page breaks do not match the PDF; rebuild with extract <key> --force) | NOTE of check |
| 3 | The PDF is in the folder and its sha256 differs from the header's sha256 | 抽出の後に PDF が替わった（extract <key> --force で作り直す） (the PDF changed after extraction; rebuild with extract <key> --force) | NOTE of check |
| 4 | Unreadable characters in the body (replacement characters, private use area, cid) exceed 1 per 1,000 characters excluding spaces | 読めない字 N（置換文字・私用領域・cid） (N unreadable characters) | INFO of check |

- Diagnoses 1 and 3 are given only when the PDF is in the folder.
- Only when there is a diagnosis, `@抽出の診断: <messages joined with 「；」>` is written among the derived fields of the excerpt (English alias extraction_diagnosis). It also appears in grade and in the propose worksheet.
- Characters of diagnosis 4 that fall within the verbatim range become the human-check reason 「逐語の範囲に読めない字」 (unreadable characters within the verbatim range, §2.2).

## 3. Citations

Under the heading `# 引用`, write `対象: <path to the manuscript>` (target), then list blocks `## c001`, `## c002` … (the IDs of the marks in the manuscript).
Put a mark right after the citation in the manuscript (〔c001〕 by default). Each ID has one mark in one place.

### 3.1 Written fields

| Field | Required | Value |
|---|---|---|
| 種類 (kind) | Required | 指示 / 主張 (pointer / claim) |
| 文献 (source) | Required for a pointer | A bibliography key |
| 抜き書き (excerpts) | Required for a claim | `key#e1, key#e2` (comma separated) |
| 理由 (reason) | Required for a claim | What this citation shows |
| 解釈 (interpretation) | Optional | Interpretation added by the writer. States the difference from the original |
| 人の読み (human_reading) | Optional | Follows the rules of §4. A reading, not in the words of the original, that a person puts into the sentence |
| 人の読みの記入 (human_reading_by) | Required when there is a human reading | The person who wrote it and the date |
| 原文との差 (diff) | Required for a claim | 一致 / 言い換え / 限定つき一般化 / 外挿 (identical / paraphrase / qualified_generalization / extrapolation) |
| 引用でない句 (not_quotes) | Optional | Phrases inside quotation marks that are not verbatim from the original. Separated by `／`, with reasons in parentheses |
| 記入 (written_by) | Required for a claim | Who wrote it and the date |
| 承認 (approval) | Required for a claim | 未 (none) / `<approver> <date>` / 差し戻し (returned) |
| 承認の理由 (approval_note) | Optional | The substance of the judgment |
| 差し戻しの理由 (returned_reason) | Required when returned | |
| 指摘 (remarks) | Optional | Remarks on the manuscript itself. Separate from the judgment. Not part of any fingerprint |

An extrapolation stays pending, and is resolved only when the sentence is qualified or rewritten as the writer's own claim.

A pointer citation (one that only names a work or mentions that it exists) needs only the `文献` (source) key, present in the bibliography. In citation practice, it is enough that the referenced work is in the bibliography; the content is not matched.
A reason, written_by and approval are not required. If written, they appear in the review material, but their absence does not make the citation pending. Pointer citations have no approval state; check counts them as 「指示」 (pointer).

### 3.2 Approval states

They apply to claim citations. There are five: 未承認 / 承認済 / 要再確認 / 差し戻し / 差し戻し後に直された (not approved / approved / needs recheck / returned / fixed after return). The tool decides them by comparing the records of §3.3 with the current fingerprints.

- 承認済 (approved): the fingerprint at approval equals the fingerprint of the current sentence, and the evidence fingerprint at approval equals the current evidence fingerprint
  (an old approval without an evidence record looks only at the sentence). When the settings have an approvers list, the approver must also be human in that list (or, when the setting `approval.count_model` is true, a model independent of the writer).
  An approval by someone listed as model is kept in the record; when `approval.count_model` is false (the default) it is counted as not approved, and check reports a pending NOTE 「承認を数えない」 (approval not counted). When it is true, an approval by a model independent of the writer (condition 3 of §2.1) counts as approved. Whether the source supports the claim rests on the judgment of whoever approved it (when false, a person's approval guarantees it).
  Without a list the kind is unknown, so the approver's name does not matter. Checks against the original (§2.1) and summary checks accept a model checker independent of the writer (outside this rule).
  review (md, JSON) and the approval HTML count approvals in the same way as check. A citation whose approval is not counted (an approval by someone listed as model, or by a model not independent of the writer, condition 3 of §2.1) gets the state 未承認 (not approved), with 「承認を数えない（<reason>）」 (approval not counted) as the detail, and is in the default pending list.
  A citation whose approval is not counted has the field `model_approval` in review's JSON (null for a counted approval, not approved and sent back). Its contents are `{by, date, note, why, text, evidence, approved_text}`:
  who approved and when, the approval reason, why it is not counted, whether the text and evidence at approval match the current ones (合う matches / 変わった changed / 記録が無い no record), and `@承認時の本文` (approved_text) only when the text changed. It is also present when the text changed afterwards and the citation became 要再確認 (needs recheck).
  An approved citation has the field `approved_by` in review's JSON, `{by, kind, family}` (kind and family are null when not in the list; null for a citation that is not approved).
  When `approval.count_model` is true, the approver's kind (a person / a model and its family) is shown in check's count of approved citations, and in the state in review's md and the approval HTML.
  When the kind is looked up in the list, differences of full-width and half-width, and of upper and lower case, in the name are ignored.
- 要再確認 (needs recheck): the sentence or the evidence changed after approval.
- 差し戻し (returned): the fingerprint and evidence at the return equal the current ones (the writer has not fixed it yet). If they differ, the state is 「差し戻し後に直された」 (fixed after return), waiting for approval.

### 3.3 Record fields

`@承認時の指紋` (approved_fingerprint), `@承認時の本文` (approved_text), `@承認時の根拠` (approved_evidence), `@差し戻し時の指紋` (returned_fingerprint), `@差し戻し時の根拠` (returned_evidence). The tool writes them at approval and at return.

## 4. Fingerprints and human readings

A fingerprint is the first 8 hex digits of the SHA-1 of a normalized string. Normalization removes all whitespace.

| Fingerprint | Input |
|---|---|
| Sentence fingerprint | The sentence that contains the citation, without marks and HTML comments. It includes the inside of source parentheses, so changing how the parenthesis is written also leads to recheck |
| Evidence fingerprint | The excerpt IDs (including the key) sorted, each as `<ID>\t<verbatim>`, joined by line breaks. If there is a human reading, `\n人の読み\t<human reading>` is appended |
| Summary fingerprint | The excerpt's 逐語, 強さ, 要約 and 言っていないこと (verbatim, strength, summary, not_said) joined by line breaks. Only when there is a 孫引き (secondary_source), `\n孫引き\t<value without spaces>` is appended (otherwise unchanged) |
| Verbatim fingerprint | The verbatim text with all whitespace removed. Compared with the fingerprint at the check against the original (§2.3). The first 8 hex digits of the SHA-1 |

### 4.1 Rules for human readings

Human judgments (approval, return) are the person's authority, but a reading that goes into the sentence needs a supporting excerpt. A reading not in the words of the original is not moved into the sentence without showing its supporting excerpt.

- The writer is a person. When the settings have an approvers list, the writer must be of kind human.
- It points to a supporting excerpt: the reading contains one or more IDs of the excerpts listed in this citation's `抜き書き` (excerpts) (`e6` or `key#e6`).
  A reading that points to a nonexistent ID, or to an ID not among this citation's excerpts, is refused.
- The reading is part of the evidence fingerprint. Editing it after approval returns the citation to needing recheck.

## 5. Decisions file (`cite-bridge-decisions/1`)

JSON saved by the approval HTML. `apply` reads it and writes the decisions.

```json
{"format": "cite-bridge-decisions/1", "manuscript": "<原稿のパス>", "generated": "<HTML を作った時刻>", "by": "<判断した者>",
 "saved": "<保存時刻 ISO>",
 "decisions": [{"id": "c001", "action": "approve | send_back | ''", "note": "理由", "remark": "指摘",
                "fingerprint": "<HTML を作った時の本文の指紋>", "evidence": "<同、根拠の指紋>"}],
 "candidates": [{"id": "<item>", "action": "accept | reject", "note": "理由", "cfp": "<候補の指紋>"}],
 "confirms": [{"id": "key#e1", "fingerprint": "<要約の指紋>"}],
 "source_checks": [{"id": "key#e1", "fingerprint": "<逐語の指紋>", "result": "一致 | 違う", "page": "", "note": ""}]}
```

(manuscript: path to the manuscript; generated: when the HTML was made; by: who decided; saved: ISO time of saving; note: reason; remark: remarks;
fingerprint and evidence: the sentence and evidence fingerprints when the HTML was made; cfp: the candidate fingerprint; in confirms, the summary fingerprint; in source_checks, the verbatim fingerprint.)

- confirms can point to any excerpt, not only the evidence of citations, including excerpts used by no citation (the approval HTML's 「引用に使われていない抜き書き」, excerpts not used by any citation).
- A return and a rejection require a note.
- apply writes only entries whose fingerprints at the time the HTML was made match the current ones (others are skipped with the reason).
- `by` must be in the approvers list. A name not in the list is refused.
- `source_checks` (optional) are records of checks against the original (§2.1). Only those whose fingerprint matches the current verbatim fingerprint are written, under the name in `by`. Others are not written, and the reason is given.
  When the result is `違う`, the note must hold the characters of the original.

### 5.1 Source-check request (`cite-bridge-source-checks/1`)

Written by `review --source-checks --json`. It lists the excerpts that need human check and still wait for a check against the original, whether or not a citation uses them.
An external AI or a person receives it and answers with a decisions file in the form of `answer_example`. The tool does not call external AIs.

```json
{"format": "cite-bridge-source-checks/1", "manuscript": "<原稿のパス>", "generated": "<作った時刻>",
 "instructions": "<道具が持つ定型の文（各件の逐語を原本で確かめ、結果と原本の字を答える）>",
 "answer_example": {"format": "cite-bridge-decisions/1", "manuscript": "<原稿のパス>", "generated": "<作った時刻>", "by": "<名前>",
                    "saved": "<ISO 時刻>", "decisions": [], "candidates": [], "confirms": [],
                    "source_checks": [{"id": "<id>", "fingerprint": "<fingerprint>", "result": "一致", "page": "", "note": ""}]},
 "items": [{"id": "key#e1", "reasons": "<要ヒューマンチェックの理由>", "verbatim": "<逐語>", "location": "<所在>",
            "fingerprint": "<逐語の指紋>", "grade": "<格>", "page_image": "<--images の PNG のパス、無ければ null>",
            "record": "<今の原本での確認の値>", "problem": "<問題の文（§2.1 の五つの条件のどれに欠けるか）>", "written_by": "<記入>"}]}
```

(instructions: fixed text held by the tool (check each item's verbatim text against the original and answer the result and the original's characters); reasons: the human-check reasons; verbatim, location, fingerprint, grade: of the excerpt;
page_image: path of the PNG from --images, or null; record: the current source_check value; problem: which of the five conditions of §2.1 is missing; written_by: the excerpt's 記入.)

- The answer's `by` is a name listed as model in the approvers list. It cannot be the same name as the excerpt's writer (written_by) (condition 3 of §2.1).
- The answer is written by `apply`. Only those whose fingerprint matches the current verbatim fingerprint are written (source_checks of §5).

## 6. Making candidates

Sources without a mark are turned into candidate excerpts and citations. The authoritative candidates live in `<candidates>/`, and are not put into the excerpt and citation files until a person accepts them.

### 6.1 Worksheet (`cite-bridge-work/1`, written by `propose`)

`{format, manuscript, generated, items:[{item, line, section, paren, nth, sentence, fingerprint, clause, keys}]}`.
item is an ID made from "the sentence fingerprint, the parenthesis, and which occurrence of the same parenthesis in the sentence"; it does not change while the sentence does not change.
keys are key candidates, with the match against the bibliography, the grade, the top sentences of the source, and existing excerpts of the same source.

### 6.2 Drafts (`cite-bridge-drafts/1`, written by the writer and checked by `propose --load`)

`{format, items:[{item, kind, key, 理由, 記入, …}]}`.

- Pointer: `kind: 指示`, `key`, `理由`, `記入`.
- Not a citation: `kind: 引用でない`, `理由`, `記入`. On acceptance, the parenthesis is added to `excluded.json` (§7).
- Claim: `kind: 主張`, `key`, `excerpts`, `理由`, `解釈`, `原文との差`, `記入`.
  `excerpts` is a list; an existing excerpt is `{use: "e3"}`, a new one is
  `{sentences: [a, b], from?, to?, 強さ, 要約, 言っていないこと}` (from a to b, up to 6 consecutive sentences of the source).
  The writer does not write the verbatim text; the tool copies it from the sentence range of the source.

The check refuses when: the key is not in the bibliography, the range is not in the source, the sentence fingerprint changed after the worksheet, the source text changed after the worksheet,
the copied verbatim text does not match in the source, or a required field is empty.

### 6.3 Candidates (`cite-bridge-candidates/1`)

`{format, items:{<item>: {item, kind, 理由, 記入, line, section, paren, nth, sentence, fingerprint, key, excerpts, status, loaded, decided}}}`.
status is pending / accepted / rejected. decided is `{by, date, cid}` on acceptance (the ID of the accepted citation) and `{by, date, reason}` on rejection.

Accepting writes the new excerpts and citation, records the approval and the summary check at the same time, and puts a mark in the manuscript sentence.
It is refused if the sentence fingerprint has changed. It is also refused if the one accepting is a model not independent of the candidate's writer (condition 3 of §2.1). A rejection (reject) needs a reason, and the next worksheet marks that item with `rejected_before`.

## 6.4 Classifier check

An external classifier independently assigns the bridge's closed vocabularies, and the result is compared with the records. It only raises flags; it does not change approval states.
Confidence (score) is for display and for the ledger, and is not used in any rule.

### Type definitions (`[[checks]]` in bridge.toml; defaults are `DEFAULT_CHECKS` in judge.py)

| Field | Required | Contents |
|---|---|---|
| type | Required | Name of the type (`cite.diff` etc.). A definition with the same name overrides the default |
| version | Required | Logical version |
| for | Required | `citation` (per citation) or `excerpt` (per excerpt) |
| question | Required | Wording of the question. The text of `about` goes into `{about}` |
| labels | Required | Closed choices. Include 「判定できない」 (cannot judge) |
| gloss | Optional | Short explanation per label (it becomes the wording of the classifier's choices) |
| materials | Required | Slot of material → field reference. `citation.sentence`, `citation.<field>`, `excerpt.<field>` |
| about | Optional | Field of the text being judged (e.g. `excerpt.言っていないこと`) |
| compare | One of the two | Field of the record to compare with. Not passed to the classifier |
| flag_on | One of the two | Labels to flag (when there is no record to compare with) |
| order | Optional | Used with compare. Groups of labels from light to heavy (e.g. `[["一致", "言い換え"], ["限定つき一般化"], ["外挿"]]`). Only judgments heavier than the record are flagged |
| on_disagree | Optional | Only `flag` (the default). An action that lowers the approval state does not exist yet |
| cleared_by | Optional | A field reference (e.g. `excerpt.孫引き`). When this field has a value, even a flag_on label gives the status 一致 (the record says the same thing). Cannot be used with compare |

The field reference `excerpt.<field>` covers the excerpt's 逐語, 前, 含む文, 後, 強さ, 要約, 言っていないこと and 孫引き. Types with `for = excerpt` cannot use `citation.*`.

### Judgment ledger (`bridge/judgments.jsonl`, append-only; a later line for the same item and type is newer)

```json
{"item": "cite:c007 | exc:key#e1", "type": "cite.diff", "version": 1, "spec": "<型の文面の指紋>", "mat": "<材料の指紋>",
 "label": "外挿", "score": 0.91, "scores": {"一致": 0.02, "…": 0.0}, "record": ["言い換え"], "status": "食い違い",
 "lang": "ja/en", "provider": "jev", "model": "jev-latest", "at": "2026-01-01T10:00:00"}
```

(spec: fingerprint of the type's wording; mat: fingerprint of the material.)

- lang is the language pair (`sentence/source` for citations, only the source for excerpts; detected in the same way as for eval sets below). It is not used for branching; it is kept for counting per language later.
  Comparison across languages is left to the provider; the tool does not translate.
- A judgment is fresh when version, spec and mat equal the current ones. When the material or wording changes it becomes outdated, and `classify` judges again.
- Unreadable lines are skipped: lines that are not UTF-8, lines that are not JSON, and JSON lines without item, type or label (strings). `check`, `checkpoint` and `classify` run to the end, and `check` reports the skipped line numbers as INFO (`判定の台帳の読めない行を <n> 行飛ばした（<行番号>）`, skipped n unreadable lines of the ledger (line numbers)). The ledger is not rewritten.
- status is the comparison with the record at the time of judgment: 一致 / 食い違い / 記録より軽い / 判定できない / 記録なし / 要確認 / 問題なし
  (agrees / disagrees / lighter than the record (for a type with order, a judgment lighter than the record) / cannot judge / no record (the compare field is empty) / needs attention (a flag_on label) / no problem).
  For a type with order, labels in the same group agree, and a judgment heavier than the record disagrees.
  Flags are 食い違い and 要確認. Comparison with the current record is given by `classify --list` and `review`.
- What is shown (`classify --list`, `review`, the classifier counts of `check` and `checkpoint`) is decided by comparing judgments with the current records (including cleared_by).
  Judgments outdated by a change of the type's wording or the material are not counted; only their number (K outdated judgments) is shown. The ledger's status stays as at the time of judgment.

### Eval set (`cite-bridge-eval/1`) and results (`cite-bridge-eval-result/1`)

```json
{"format": "cite-bridge-eval/1", "note": "…", "types": ["cite.diff"],
 "items": [{"id": "c001", "split": "tune"},
           {"id": "m01", "base": "c001", "split": "tune", "flag": ["cite.diff"], "level": 1, "mutation": "何をどう壊したか", "claim": "壊した本文の文"},
           {"id": "m01.en", "twin": "m01", "claim": "同じ内容を別の言語で書いた本文"}]}
```

(mutation: what was broken and how; claim: the broken sentence, or for a twin, the same content written in another language.)

- An item with only an id is an approved citation; it is correct that no type in types raises a flag.
- An item with flag is a mutation: a test item where the sentence of the base citation is replaced by claim. It is correct that the types listed in flag raise a flag (types not listed are not counted).
  The other parts of the material (verbatim text, surrounding sentences, record) are those of the base. claim goes neither into the manuscript nor into the citations file.
- evidence (a list of excerpt IDs) and record (record fields, e.g. `{"原文との差": "言い換え"}`) replace the base's material (optional).
  An item without base and with only evidence compares a sentence without a citation (such as the actual wording of an error found earlier) with those excerpts.
  evidence can use excerpts not used by any citation.
- level is the difficulty of the mutation (optional). Results are also counted per difficulty and per language pair. Write what the levels mean in the set's note.
- An item with twin has only a sentence (claim) that says the same as the twin item in another language, and inherits base, split, flag, level and mutation from the twin item.
  If the original is approved, base is the original's id. Flags of pairs that differ only in language are compared, and differing pairs are reported.
- Results are rows of `{variant, rep, item, split, lang, level, twin, type, label, status, record, margin, flagged, expected, ok, mutation}`.
  margin is the difference between the top two confidences, kept as a sign of ambiguity (not used in rules). It is not written to the ledger.
- lang is the language pair of sentence and source (`sentence/source`, e.g. `ja/en`; if the evidence's verbatim texts span several languages, `ja/en+ja`). Text containing kana or kanji is ja,
  text with only Latin letters is en (Western languages other than English are also counted as en). It is not written in the eval set; the tool detects it.
- `citation.出典` is the first author and year of the evidence source (derived from the bibliography). It is used in the question to name which part of the sentence to look at.

The contract of provider adapters, and the order in which the classifier key is read, are in docs/classifier.md.

## 7. Records of applying

- `applied.json`: `{<manuscript>: {last_saved, files:[{file, saved, sha256, by, applied, written, skipped, note?}]}}`.
  apply refuses the same file, and files saved before the last applied one (`--allow-older` applies them on purpose).
- `excluded.json`: `[{item, paren, nth, part, fingerprint, …}]`. Sources a person judged 「引用でない」 (not a citation). Not counted in coverage.
  `part` is the number (from 0) of the source within the parenthesis, for per-source items. For a parenthesis with one source it is null, and a record without `part` is treated as null. Matching uses (sentence fingerprint, parenthesis, nth, part).

## 8. Manifest (`cite-bridge-manifest/1`)

Written by `checkpoint` at a point that has passed `check --strict`. When there is an approvers list, `checkpoint --by <name>` is required, and the name must be human (the final submission is made by a person).

```json
{"format": "cite-bridge-manifest/1",
 "tool": {"name": "cite-bridge", "version": "0.5.0", "sha256": "<道具のソースの指紋>", "commit": "<道具のフォルダの最終コミット | null>", "dirty": false},
 "checkpoint": "<UTC 時刻>", "label": "",
 "git": {"head": "<HEAD>", "uncommitted": ["…"]},
 "files": {"config": {"path", "sha256"}, "bibliography": {…}, "manuscript": {…}, "citations": {…},
           "excerpts": {"<path>": "<sha256>"}, "texts": {"<path>": "<sha256>"}},
 "excerpts": {"total": 0, "match": {}, "grade": {}},
 "citations": {}, "approvers": {}, "approver_kinds": {}, "coverage": {}, "summary_checks": {},
 "source_checks": {}, "by": "<提出者 | null>",
 "classifier": null}
```

(tool.sha256: fingerprint of the tool's source; tool.commit: last commit of the tool's folder, or null; checkpoint: UTC time; by: the submitter, or null.)

`coverage` holds the coverage counts: `spans` (number of sources, excluding those recorded as not citations), `in_marked_sentences` (sources with a mark), `unmarked` (sources without a mark),
`parens` (number of parentheses; a parenthesis split into several sources counts as one), `excluded` (number recorded as not citations).
`source_checks` is the tally of the checks of §5.1: `marked` (excerpts with the human-check mark), `done` (checked), `by_kind` (per kind of checker), `pending` (remaining).
`by` is the name given to `checkpoint --by`, or null.

`tool` records which version of the check was passed. sha256 is the sha256 taken over the relative paths and content sha256s of the tool's source (bridge.py and the .py, .html and .js files under cite_bridge/), listed in path order. Even when the tool is used from another repository, the version is known on the user's side. `classifier` is null when no classifier is configured and there is no ledger. Otherwise it is `{provider, model, types:[{type, version, spec}], judgments, flagged, note}` (§6.4).

## 9. Settings (bridge.toml)

A template is in the "設定" (Settings) section of SKILL.md. The table lists the keys.

| Table | Keys | Contents |
|---|---|---|
| bibliography | path, format, files_field, pdf_pattern, web_pattern | Path of the bibliography, how to read it (keyline / bibtex / csl-json), how to recognize PDFs and web sources |
| sources | pdf_dir, text_dir, web_dir | Where originals, extracted text and web copies are kept |
| bridge | excerpts, citations, checkpoints, applied, candidates, excluded, judgments | Where the data is kept |
| manuscript | mark_pattern, mark_format, quote_patterns, not_quote_separator, sentence_end, paragraph | Rules for marks and sentences in the manuscript |
| output | language | Language of the names of derived fields (ja / en) |
| section_kinds | <kind> = [words] | Adds words for section kinds |
| detect | common_words | Adds frequent words used to see whether an extraction is readable |
| approvers | <name> = human / model / model:<family> | Who can approve, and their kind. For a model, write its family (the provider and so on, e.g. `model:anthropic`), used to see independence from the writer (condition 3 of §2.1). List the writers of excerpts and citations too. If omitted, names are not checked. Only approvals by human approvers count as approved for citations (approval.count_model also counts models; §3.2) |
| approval | count_model | If true, an approval of a citation by a model independent of the writer counts as approved (default false; §3.2) |
| coverage | pattern, repeat_pattern | Regular expression for parentheses that look like sources (default: parentheses containing a year), and for parentheses that are only a page or "ibid." (default below) |
| hook | watch | Paths pre-commit watches besides those the settings point to |
| classifier | provider, model, endpoint, max_chars, types | Classifier provider and limits (§6.4). Do not write the key (docs/classifier.md) |
| checks (array) | type, version, for, question, labels, … | Adding and overriding question types (§6.4) |

When applied, candidates, excluded or judgments in `bridge` is omitted, the tool keeps it as `applied.json`, `candidates/`, `excluded.json` or `judgments.jsonl` in the same folder as the citations file (citations).
When `--citations` replaces the citations file, the omitted locations also move to that citations file's folder.
Locations set explicitly in the settings do not move. To share the classifier ledger with a copy, set judgments explicitly.
`--citations` replaces only the citations file and these four locations. The excerpts (including the records of summary checks and checks against the original) and the checkpoints are the ones at the locations in the settings, and the mark written when a candidate is accepted goes into the manuscript named by `対象` (target) in the citations file.

The default of `repeat_pattern` is `[（(](?:同書[^（）()\n]*|同上|同|ibid\.?[^（）()\n]*|pp?\.\s?\d[^（）()\n]*)[）)]`.
Parentheses that are only a page or "ibid." are not sources; they count as one item, a repetition of the preceding source. A parenthesis that matches both `pattern` and `repeat_pattern` counts on the `pattern` side.
For a parenthesis matching `pattern`, its content is split at 「;」 and 「；」, and each part that, wrapped in full-width parentheses, fully matches `pattern` is a source.
If there are two or more sources, each source is one item (`part` is the same number as in excluded.json of §7).

## 10. English aliases

| Japanese | English | Japanese | English |
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
| 要ヒューマンチェック | human_check | 原本での確認時の指紋 | source_check_fingerprint |
| 孫引き | secondary_source | 抽出の診断 | extraction_diagnosis |
| 対象 | target | 要約の確認時の指紋 | summary_check_fingerprint |
| 承認時の指紋 | approved_fingerprint | 承認時の本文 | approved_text |
| 承認時の根拠 | approved_evidence | 差し戻し時の指紋 | returned_fingerprint |
| 差し戻し時の根拠 | returned_evidence | | |

Value aliases: 強さ (observation / suggestion / claim / generalization / conditional), 種類 (pointer / claim),
原文との差 (identical / paraphrase / qualified_generalization / extrapolation), 承認 (none = 未, returned = 差し戻し).
The table covers all written fields and record fields (frozen by §11.1) and some of the derived fields. The mapping of derived field names is in `FIELD_ALIASES` in cite_bridge/config.py and is not frozen.

## 11. Version policy

### 11.1 What is promised

The tool promises two things: the shape of the data, and the guarantee statement ("What it does" in the README). It does not promise commands or features.
Of the shape of the data, the following, which people and other tools read and write, is frozen.

- The written fields (§2.1) and record fields (§2.3) of excerpts; `対象` (target) of the citations file, and the written fields (§3.1) and record fields (§3.3) of citations. Field names (including English aliases, §10), value vocabularies and meanings.
- How fingerprints are made (§4).
- The shapes of the decisions file (§5), the source-check request (§5.1), the judgment ledger (§6.4) and the manifest (§8).

The following are not frozen. They may change without a version bump.

- Names, values and wording of derived fields (`@` lines that are not record fields). Derived fields are rebuilt on every check.
- Worksheets, drafts and candidates (§6). Likewise other files not listed above (the eval sets and results of §6.4, the records of §7).
- Output text of check and the other commands. Users are expected to localize or adjust it.

### 11.2 How changes are made

Changes to the frozen part follow these steps, before 1.0 as well.

1. Raise the minor version (x in 0.x). Raise it even for a change that only adds fields and lets existing files pass the check.
2. For a change that alters the state of existing files (the meaning of a field, how fingerprints are made, how approvals or checks are counted), write migration steps in the version's entry in §11.3.
3. Old shapes are read until the next minor version. When a field name changes, the previous name is accepted as an alias until the next minor version. When the number of a format name (`/1`) goes up, files with the previous number are also read until the next minor version.
   From the minor version after that, previous names and numbers need not be accepted.

Formats that are not frozen (worksheets, drafts, candidates, eval sets and results) also raise the number of the format name when their shape changes. Continued reading of the previous number is not promised.

### 11.3 Version history

- As of 0.1.0, the human reading is part of the evidence fingerprint. An approval including a human reading needs recheck when the reading is edited.
- 0.2.0 added the classifier check (ledger `judgments.jsonl`, `[[checks]]` and `order` of types, eval sets and results, `classifier` in the manifest).
  As these were added fields, existing excerpts, citations and decisions files pass the check as before, and approval states do not change. When the wording of a default type changes (cite.diff version 4 etc.),
  ledger judgments become outdated by the wording fingerprint, and the next `classify` judges again.
- 0.3.0 added the extraction header and diagnoses (§2.4), human check and checks against the original (§2.1, §2.2, §5.1), secondary sources (§2.1, §4), aligned classifier counts (§6.4),
  per-source coverage (splitting parentheses and repeat, §8, §9), and the request JSON (§5.1). Some fields were added, and the meaning of some fingerprints and records changed.
  The format names of the decisions file, worksheet, drafts, candidates and request all stay at `/1`.
- 0.4.0 stopped counting citation approvals by someone listed as model in the approvers list as approved, and made them pending (§3.2). Fields and format names are unchanged.
  A citation with an approval by a model in the list changes from approved to not approved, and `check --strict` and `checkpoint` stop.
  Without a list, and for human approvals, nothing changes. Checks against the original and summary checks do not change either.
  It also added the human-check reason 「逐語が短い」 (short verbatim text, §2.2), and names of writers and checkers are now compared after normalization (condition 3 of §2.1).
  Excerpts with short verbatim text get the human-check mark after derive, and `check --strict` stops while they have no check against the original.
  Records and approvals by a model checker whose name differs from the writer's only in letter case or full-width and half-width forms are no longer counted.
  From this version, the scope of §11.1 is frozen, and changes follow the steps of §11.2.
- 0.4.1 made review (md, JSON) and the approval HTML count approvals in the same way as check (§3.2). A citation whose approval is not counted changes from approved to not approved (with the reason as the detail) and appears in the default pending list.
  Fields, format names, fingerprints and the state of files do not change, so no migration steps are needed. External viewers that read `state` in review's JSON receive such a citation as not approved instead of approved.
- 0.4.2 looks up the kind in the approvers list ignoring differences of upper and lower case and of full-width and half-width in the name (§3.2). An approval by a name that differs only in spelling from someone listed as model is no longer counted as approved, and `check --strict` and `checkpoint` stop.
  It also refuses to write an approval by someone listed as model for a citation with a human approval that is counted now, and writes `@承認時の本文` (approved_text) on one line. Fields, format names, fingerprints and the state of files do not change, so no migration steps are needed.
- 0.5.0 checks whether a model checker or approver is independent of the writer by family as well as by name (condition 3 of §2.1). The kind in the approvers list can be `model:<family>` (§9).
  For an approval, the approver is compared with the writers of the evidence excerpts as well as the writer of the citation. Records by a model without a family, by a writer not in the list, or by a model of the same family as the writer are not counted, and the tool refuses to write them.
  Nothing changes without a list, or for human checkers and approvers. Fields, format names and fingerprints do not change, but when the list has models, the counting of checks against the original and summary checks changes (the migration steps below).
  It also adds the setting `approval.count_model` (default false). When true, an approval of a citation by a model independent of the writer counts as approved (§3.2). It adds the field `approved_by` to review's JSON. By default the counting of citation approvals does not change.

### Migration steps for 0.5.0

If there is no approvers list, no steps are needed.

1. Write a family for each model in the list (`"claude-opus-5-5" = "model:anthropic"`). Write models from the same provider as the same family.
2. List the writers of excerpts and citations (the first word of 記入, written_by). A person as human, a model as `model:<family>`. Records written with a generic name such as `AI` are listed under that name if you know which model it was; if not, a person redoes the check.
3. Run `check` and look at the records with a NOTE saying independence cannot be told, or the same family. Redo those records with `confirm` (`--source`) or `approve`, by a model of a family different from the writer's or by a person.

### Migration steps for 0.4.0

1. Run `check` and look at citations with the NOTE 「承認を数えない（model … の承認は記録に残るが、承認済には人（human）の承認が要る）」 (approval not counted: the approval by model … stays in the record, but approval needs a human).
   If there are none, step 2 is not needed.
2. For those citations, a person looks at the material with `review <ID>` and approves again with `approve <ID> --by <human name>`. To see them in the approval HTML, use `review --html --all -o <file>`
   (in 0.4.0 these citations are not in review's default pending list, so point to them by ID or with `--all`; from 0.4.1 they appear in the default pending list as not approved).
   The model's approval stays in the record until a human approval overwrites it.
3. Make sure the kinds in the approvers list (human / model) match reality. If a person is listed as model, fix the list.
4. Run `derive`. Excerpts with short verbatim text get the human-check reason 「逐語が短い」 (before derive, check reports 「導く欄が古い」, derived fields outdated, for those excerpts).
   Check the location in the original with `review --source-checks`, and record it with `confirm --source`.
5. If `check` newly reports the NOTE 「書き手と同じモデル」 (same model as the writer), redo that record or approval with someone other than the writer.

### Migration steps for 0.3.0

To check an existing manuscript and extracted text with 0.3.0, do the following in order.

1. Existing extracted text has no header. Add it with `extract --header-only` (the body does not change). Rebuild those whose page breaks do not match (diagnosis 2) with `extract <key> --force`.
2. Run `derive`. The derived fields gain human-check marks and extraction diagnoses.
3. Excerpts from sources with an OCR text layer need human check even when the match is exact, and `check --strict` stops. Check the characters of the original with `review --source-checks` or `review --html`, and record them with `confirm --source`.
   Checks against the original from 0.2.0 and earlier (free text) are not valid, so check again.
4. Excerpts with a secondary source need their summary checked again (the summary fingerprint changes).
5. Coverage counts per source, so the numbers change. Item IDs of parentheses with one source do not change.
