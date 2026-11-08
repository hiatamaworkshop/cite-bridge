---
name: cite-bridge
description: Gives every citation an anchor (the verbatim text of the source and the location the tool derives) and keeps the state of its checks correct throughout writing. Excerpts (a passage of a source) and citations (a place in the manuscript) are written as md with fixed fields, and bridge.py derives and checks the location, surrounding sentences, section kind and match level. Use it when adding an excerpt of a source, when adding a citation to the manuscript, and when reviewing the check state of citations before submission.
---

# Citation bridge

Japanese original: [SKILL.md](SKILL.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

This document gives the rules and commands for the people and AIs who use the tool. What the tool does is in `README.md`; the authoritative shape of the data (fields, fingerprints, decisions files, manifest, etc.) is in `SPEC.md`.
In the repository where you use the tool, put the tool in `tools/cite-bridge/` (as a submodule). The command examples below assume this location. If you put it elsewhere, adjust the paths and tell the hook where it is with the environment variable `CITE_BRIDGE` (the "hook" section).
This document is plain Markdown that any agent or person can read. The name and description at the top are the entry point when it is placed as an agent skill (e.g. `.claude/skills/cite-bridge/`), which is one way of placing it.
To use this English version as a skill, put it in place of SKILL.md.

## Guarantees and owners

- The existence and location of the anchor are guaranteed by this script (matching against the extracted text).
- Whether the source supports the claim rests on the judgment of whoever approved it. Who approved is recorded (a person, or a model of which family). By default only a person's approval counts; an approval by someone listed as model in the approvers list stays in the record but
  is not counted as approved and stays pending. With the setting `count_model = true`, an approval by a model independent of the writer also counts (the "approvers list" paragraph below). Checks against the original and summary checks can be delegated to a model of a different family from the writer (checks by a model of the same family are not counted).
- That a check has not gone stale is guaranteed by the sentence fingerprint. If the sentence changes after approval, the citation returns to needing recheck.

## Written fields and derived fields

People and AIs write only the judgment fields. Lines starting with `@` are written by the script. Do not edit them by hand.

Excerpts `bridge/excerpts/<key>.md` (one file per source; the heading is the bibliography key)

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

(The same block with English aliases: `verbatim:`, `strength: observation`, `summary:`, `not_said:`, `written_by:`. With `[output] language = "en"`, the derived fields are written as `@match:`, `@location:` and so on.)

- Written fields: 逐語 (verbatim), 強さ (strength: 観察／示唆／主張／一般化／条件付き, observation／suggestion／claim／generalization／conditional), 要約 (summary), 言っていないこと (not_said), 記入 (written_by: who wrote it and the date).
  For an excerpt with the human-check mark (`@要ヒューマンチェック`), record the check against the original with `confirm --source` (do not write the field by hand; see "Human check" below).
  A record whose checker is unknown does not count as a check.
- Do not write anything outside the original's range in the summary. Put your own reading in the interpretation on the citation side.
- If what it does not say, or an interpretation, rests on another passage of the original, make that passage an excerpt too and refer to it by ID (`e6` in the same source, `key#e6` in another source).
  Writing only "it is on the same page" without pointing to it is a route by which unverified claims slip in. check verifies that the referenced IDs exist.
- Write the summary from the checked verbatim text, not from the extracted text. Do not fill in misreadings of the extracted text in the summary.
- When the verbatim text is cut in the middle of a sentence, the derived field 「含む文」 (sentence) shows the whole sentence of the original. So as not to overlook qualifications outside the verbatim text
  (「…が考えられる」, "without critical reflection", etc.), write the summary and what it does not say looking at it.
- When a person has compared the summary, what it does not say, and the strength with the original, record it with `confirm` (`要約の確認`, summary_check, and the fingerprint at that time).
  If the fields change after the check, check reports 「確認し直す」 (check again). The number of unchecked items appears in check's INFO (--strict does not stop on it).
- Copy the verbatim text exactly as in the original. Style rules (such as not using em dashes) do not apply to the verbatim field.
- Write each field on one line.
- Derived fields: 照合 (match), 所在 (location: page and section), 節の種類 (section kind), 前 (before), 後 (after), 含む文 (sentence). Under the source heading, the grade and the location of the extracted text.
  If a section is derived wrongly, check the heading lines in the extracted text (heading detection is an estimate).

Citations `bridge/citations.md` (one file per manuscript; put a mark 〔c001〕 after each citation in the manuscript)

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

- The kind is 指示 (pointer: it only names a work or mentions that it exists; write `文献: <key>`) or 主張 (claim: it states what the source says; it needs excerpts).
  A pointer needs only the `文献` (source) key, present in the bibliography; a reason, written_by and approval are not required (if written they appear in review, but their absence does not make it pending).
  The rules below on approval, human readings and the difference from the original are about claim citations (SPEC.md §3.1).
- The approval states, and which fingerprints return a citation to needing recheck when they change, are in SPEC.md §3.2. A return keeps its reason in `差し戻しの理由` (returned_reason); when the writer fixes the sentence or the evidence, it waits for approval.
- A human reading (when a person puts a reading not in the words of the original into the sentence) is written in fields separate from the writer's interpretation: `人の読み` (human_reading) and `人の読みの記入` (human_reading_by: the person and the date).
  An AI cannot write it (an entry by someone not human in the approvers list is refused). Write in the reading the ID of one of this citation's excerpts (`e6`, `key#e6`) to show the supporting excerpt.
  The reading is part of the evidence fingerprint, so editing it after approval returns the citation to needing recheck (SPEC.md §4.1). Human judgments (approval, return) are separate.
- The difference from the original is 一致／言い換え／限定つき一般化／外挿 (identical／paraphrase／qualified generalization／extrapolation). An extrapolation stays pending, and is resolved only when the sentence is qualified or rewritten as the writer's own claim.
- A string inside quotation marks in the manuscript must be contained in the verbatim text of the excerpts it points to (quotations in another language are treated as translations and excluded).
  Phrases inside quotation marks that are not verbatim from the original (one way of phrasing a command, an example UI string, etc.) are listed in the block's 「引用でない句」 (not_quotes)
  separated by ／, with reasons in parentheses. Excluding them is a person's judgment; the machine excludes only the listed phrases.
- The text of one citation is the sentence containing the mark. A 。 inside 「」 brackets does not end a sentence. HTML comments are excluded from sentence detection and the fingerprint, so
  editing only a comment does not lead to recheck. Marks inside comments are not counted.
- Marks 〔c001〕 stay in the manuscript. To make a submission, make a copy without marks with `strip` and pass it to the conversion.

## Human check (checking against the original)

For some excerpts the machine cannot guarantee that the verbatim text exists: those whose match is approximate or impossible, those from an OCR extraction or an OCR text layer, those with unreadable characters within the verbatim range, and those with a short verbatim text (3 words or fewer in Western text, 10 characters or fewer in Japanese text).
The tool gives them `@要ヒューマンチェック` (the reasons joined with 「、」), and while there is no record of a check against the original, check reports a NOTE.
The reasons are 「照合が近似一致」「照合で見つからない」「照合不能（格）」「OCR の抽出」「OCR の文字の層」「逐語の範囲に読めない字」「逐語が短い」 (approximate match, not found by matching, cannot be matched (grade), OCR extraction, OCR text layer, unreadable characters within the verbatim range, short verbatim text).
The mark stays regardless of records; whether the check is done is decided by the `原本での確認` (source_check) record. A misplaced page break (extraction diagnosis 2) is not a reason for human check.

- The material to check is `review --source-checks` (md; attach page images with `--images DIR`). To hand it to an external AI, use `review --source-checks --json -o request.json` (format `cite-bridge-source-checks/1`).
- Record it with `confirm <key#eN> --source --by <name> [--result 一致|違う] [--page "p.49 §4・3"] [--note …]`. When the result is 違う (differs), put the characters of the original in --note.
  When an external AI has answered, write the `source_checks` of its decisions file with `apply` (only those whose verbatim fingerprint matches the current one are written).
- A record is valid when the checker is in the approvers list, a model checker is independent of the writer of the excerpt (the names differ, the list has its family, and the writer is in the list with a different family; condition 3 of SPEC.md §2.1), the verbatim fingerprint matches the current one, and the result is 一致 (matches).
- Editing the verbatim text invalidates the record. The writer edits it; the tool does not. Verbatim text reported as differing is also fixed by the writer and checked again.

Rules for delegating.

1. A person may delegate human-check requests to an external AI. The person decides whether to delegate, and the person lists the delegated AI as `model:<family>` in the approvers list.
2. The delegated AI receives the request JSON and writes a decisions file under its own name. The person passes it to `apply`.
3. An AI of the same family as the writer AI (the model that wrote the excerpt) cannot record a check against the original for that excerpt. An AI whose family is unknown cannot either.
4. Who checked is kept in the checker of each record and in the manifest's counts per kind of checker. The final submission (`checkpoint --by <person>`) is made by a person.
5. The tool does not call external AIs. It only writes out the request JSON and receives the decisions file.

## Checks and approval

- The pending list includes, besides not approved, needing recheck and returned citations, approved citations whose evidence summary has not been checked (the summary-check field exists only on the citation cards).
- review lays out, in this order: the sentence, the verbatim text of the evidence, location, match, check against the original, surrounding sentences, the AI's candidates (summary, what it does not say), the citation's fields, and the commands for the judgment.
  The verbatim text is read first so that the AI's candidates do not pull the judgment. Surrounding sentences are as in the extracted text, without filling in misreadings.
  For approximate, impossible or OCR evidence it says 「頁の画像で読む」 (read on the page image), and with --images the relevant PDF page is rendered as PNG.
  review's md output is kept as material to hand to an AI, and for situations where the HTML cannot be opened.
- The page where a person looks and decides is the approval HTML made by review --html (a single file that opens on its own, with page images embedded).
  On each citation's card a person enters hold, approve or return with a reason, and a mark that the summary was checked. Input is kept temporarily in the browser and finally saved as a decisions file (JSON).
  The HTML writes nothing. When the decisions file is passed to apply, it compares the fingerprints at the time the HTML was made (sentence, evidence, summary) with the current ones,
  and writes only those that match, with the same functions as approve and confirm. Those that do not match are reported and not written (this prevents approving what was not seen).
- A decisions file is written out with all decisions each time it is saved, so applying an old file later rolls decisions back. apply records the applied files
  in applied.json and refuses the same file and files saved before the last applied one (only on purpose, with --allow-older).
- With an approvers list (approvers), approvals, returns, summary checks and decisions files can be written only under names in the list. The approval HTML lets you choose from the list.
  check makes approvals by names not in the list pending, and the manifest also counts approvals per kind (human / model). The list prevents accidents such as typos and aliases,
  not malice (anyone can write a decisions file).
- By default, an approval of a citation by someone listed as model stays in the record but is not counted as approved, and appears in the pending list of review and the approval HTML as not approved (the full counting rules are in SPEC.md §3.2).
  The model's approval reason and whether the text and evidence at approval match the current ones are shown there too, as material for the person's approval. Write the approval reason so that a person can read it and judge.
  An approval by someone listed as model cannot be written for a citation whose human approval matches the current text and evidence (it is refused).
- With the setting `[approval] count_model = true`, an approval by a model independent of the writer (condition 3 of SPEC.md §2.1; compared with every writer of the citation and of its evidence excerpts) counts as approved.
  An approval by a model that is not independent is still not counted. The approver's kind (a person / a model and its family) is shown in check's count of approved citations, and in the state in review and the approval HTML.
- At the end of the approval HTML is a list of 「引用に使われていない抜き書き」 (excerpts not used by any citation; no citation uses them as evidence, and their summary has not been checked).
  They do not appear on citation cards, so this is where you compare the summary, what it does not say, and the strength with the original and mark them. Once a citation uses one, it is looked at again in that citation's approval.
- Besides the judgment, the approval HTML has a 「指摘」 (remarks) field. It is for notes on the manuscript; apply adds it to the citation block's 「指摘」 (it is not part of the approval fingerprint).
  You may write only a remark and leave the judgment on hold. Write remarks on the manuscript in this field, not in the approval reason.
- An external viewer (a diff review, for example) can read review --json and show the state on the marks in the text. The dependency is one way, viewer → bridge; the bridge does not know the viewer.

## Sources without a mark

- In the 「網羅」 (coverage) line, check gives the number of source-like items in the manuscript (with the number of parentheses) that have no mark. This tool checks nothing about citations without a mark.
  「確認待ち 0」 (0 pending) and checkpoint are about the state of marked citations, not a check of all citations in the manuscript. List them with coverage.
  The pattern is a lower-bound guide to counting; sources not in parentheses are not counted. Coverage is counted per source (the inside of a parenthesis is split at 「;」 and 「；」), and parentheses that are only a page or ibid. count as one repetition of the preceding source.
- Sources without a mark become candidates, and a person accepts them. The roles: the tool picks up, narrows, checks and writes; the writer AI chooses and writes the interpretation fields;
  a person accepts.
  1. propose makes a worksheet (`candidates/work.md` and `work.json`) per parenthesis of sources without a mark. It shows the clause the parenthesis covers, key candidates from the bibliography,
     existing excerpts of the same source, and the top sentences of the source (with numbers n).
  2. The writer writes drafts in `candidates/drafts.json` (format `cite-bridge-drafts/1`; the shape is in SPEC.md §6.2). An excerpt either points to an existing one
     or points to a range of the source by the worksheet's sentence numbers. If the passage is not among the top sentences, look up the source with sentences (ranking does not work between Japanese clauses and an English source).
  3. propose --load checks them and puts only those that pass in `candidates/candidates.json`. The tool copies the verbatim text from the source (the writer's text does not go into the verbatim text).
  4. Candidate cards (with a dashed left border) appear in the approval HTML in the order of the manuscript lines. Judgments are hold, accept, or reject (a reason is required).
  5. apply writes accepted candidates. For a claim, it writes the excerpt and the citation block, puts a mark right after the parenthesis in the manuscript, and records the approval and the summary check of the new excerpt
     (acceptance counts as approval). For a pointer, the citation block and the mark. For not a citation, it records it in excluded.json and removes it from the coverage count.
     If the candidate or the manuscript sentence changed after the candidate was made, nothing is written. A rejection stays in the candidates with its reason, and appears in the next propose worksheet.
- Narrowing propose: `--key <key>` (repeatable) puts in the worksheet only sources whose key candidates (the top 3 and --add-key) include that key.
  `--checkable` keeps only sources whose first key candidate has a machine-checkable grade (PDF extracted, web copy saved). Repeat items drop out with `--checkable`. Narrowing happens before cutting with --limit.

## hook

Put the consistency check in git's pre-commit. The check itself is `bridge.py precommit`, and what it watches is decided by the settings (bridge.toml).
Only when what is staged touches the manuscript, bibliography, excerpts, citations, extracted text, web copies, settings file or the tool's folder does it run
check, and it stops the commit only when there is a consistency error (ERROR). It does not stop on pending items (NOTE) (before submission, use `check --strict`).
When the tool is in the same repository as the user's files, staging the tool's folder (editing the tool) also runs the tests.
When the tool is in another repository (a submodule), its tests are run by the tool repository's `.githooks/pre-commit` (run `git config core.hooksPath .githooks` in each clone).
What is checked is the working tree, not the staged content itself.

- Installing: put the bundled `hooks/pre-commit` (a few lines of sh) at `.githooks/pre-commit` in the repository you use it in,
  and enable it with `git config core.hooksPath .githooks` (set it again after a fresh clone).
  The hook runs in sh, so stop line-ending conversion with `.githooks/* text eol=lf` in `.gitattributes`.
- Change the tool's location with the environment variable `CITE_BRIDGE` (the path of bridge.py). The default is `tools/cite-bridge/bridge.py`; if it is not there, the previous default `.claude/skills/cite-bridge/bridge.py` is tried.
  If neither exists, it warns and skips the check (the commit is not stopped).
- To watch paths other than those in the settings, use `[hook] watch = ["…"]`.

## Settings

The tool does not know the paths of your paper or how your bibliography is written. It takes all of this from the settings file (`bridge/bridge.toml` by default; change it with `--config`).

```toml
[bibliography]
path = "bib/bibliography.md"
format = "keyline"                               # how to read the bibliography (adapter): keyline / bibtex / csl-json
# files_field = "file"                           # for bibtex and csl-json, the field holding the PDF path (Zotero's and JabRef's file)
pdf_pattern = 'PDF所持: `?references/([^`]+?\.pdf)'  # how a note in the bibliography points to the original PDF
web_pattern = '参照 \d{4}|https?://(?!doi\.org|arxiv\.org)'  # bibliography lines treated as web sources
[sources]
pdf_dir = "references"
text_dir = "references/_txt"
web_dir = "references/_web"
[bridge]
excerpts = "bridge/excerpts"
citations = "bridge/citations.md"
# everything below is optional (the values shown are the defaults)
[manuscript]
mark_pattern = '〔(c\d{3,})〕'                     # the citation mark in the manuscript; group 1 is the ID
quote_patterns = ['「([^「」]{10,})」', '"([^"]{20,})"']  # quotation marks matched against excerpts
not_quote_separator = "／"                        # separator of phrases that are not quotations
sentence_end = '[。！？]'                         # end of a sentence; for an English manuscript, '[。！？]|[.!?](?=\s)'
paragraph = "line"                               # line: one line is one paragraph; blank: blank lines separate paragraphs (manuscripts with wrapped lines)
# mark_format = "〔{id}〕"                        # the mark put into the manuscript when a candidate is accepted ({id} and {key}); required if you change mark_pattern
[output]
language = "ja"                                  # language of the names of derived fields (ja / en)
[section_kinds]                                  # add words that decide the section kind (defaults are English and Japanese)
# 結果 = ["ergebnisse"]
[detect]
# common_words = ["der", "die", "und"]            # add frequent words used to see whether an extraction is readable (default: English)
[approvers]                                      # who can approve and their kind (human / model:<family>); if omitted, names are not checked
# alice = "human"
# claude-opus-5-5 = "model:anthropic"            # for a model, write its family (provider). List the writers of excerpts and citations too
[approval]
# count_model = false                            # if true, approvals of citations by a model independent of the writer also count as approved
[coverage]
# pattern = '…'                                  # parentheses that look like sources (default: parentheses containing a year); counted in sentences without a mark
# repeat_pattern = '…'                           # parentheses that are only a page or ibid. (defaults include 「（同書…）」「（同）」「（p.49）」); not sources, counted as one repetition of the preceding source
[hook]
# watch = ["extra/dir"]                          # paths pre-commit watches besides those the settings point to
```
([bridge] can also hold applied, candidates, excluded and judgments: the record of applied decisions files, the folder for candidate work, the record of parentheses judged not to be citations, and the classifier ledger;
by default applied.json, candidates/, excluded.json and judgments.jsonl in the same folder as citations. When --citations replaces the citations file, those not set explicitly are kept in its folder.
The excerpts and the checkpoints do not change, and the mark written when a candidate is accepted goes into the manuscript named by 対象 (target) in the citations file. To try on a copy, copy the manuscript too and point 対象 at it.)

- In LaTeX, put the mark in a comment right after \cite (it does not affect typesetting), e.g. `\cite{doe2020}%c017`. The settings are
  `mark_pattern = '\\cite\{(?P<key>[^}]+)\}(?P<strip>%(?P<id>c\d+))'`, `paragraph = "blank"`, and the English sentence_end.
  The named group id is the ID; if key is present, the tool also checks that the mark's key matches the evidence source; if strip is present, strip and the fingerprint remove only that part.
- Field names and values can also be written in English (verbatim, strength: observation, not_said, written_by, kind: claim, excerpts, diff: paraphrase, etc.;
  the mapping is FIELD_ALIASES and VALUE_ALIASES in cite_bridge/config.py). Internally they are normalized to the Japanese names. Output text is in Japanese only for now.

## Commands

Run them at the root of the repository.

```
python tools/cite-bridge/bridge.py derive          # rewrite the derived fields
python tools/cite-bridge/bridge.py check           # exit 1 if there is a consistency error
python tools/cite-bridge/bridge.py check --strict  # exit 1 also when pending items remain (before submission)
python tools/cite-bridge/bridge.py grade --keys-from <md containing keys>
python tools/cite-bridge/bridge.py review [c001 ...] [--images DIR] [-o output.md]  # list for checking (all pending items if omitted)
python tools/cite-bridge/bridge.py review --json --all [--images DIR]          # JSON for an external viewer (including approved citations and pointers)
python tools/cite-bridge/bridge.py review --html -o preview/cite_review.html     # approval HTML (the page where a person looks and decides)
python tools/cite-bridge/bridge.py apply <decisions.json> [--dry-run]          # write the decisions saved by the approval HTML
python tools/cite-bridge/bridge.py apply --latest [--from DIR] [--dry-run]       # use the latest decisions file in Downloads (default)
python tools/cite-bridge/bridge.py coverage                                     # list of source-like parentheses in sentences without a mark
python tools/cite-bridge/bridge.py propose [--section 2.2] [--lines 80-120] [--limit 15] [--add-key ITEM=KEY]  # worksheet of sources without a mark
python tools/cite-bridge/bridge.py propose [--key smith2020 ...] [--checkable]  # only sources whose key candidates include the key / only sources whose first candidate has a machine-checkable grade (repeats drop out with --checkable)
python tools/cite-bridge/bridge.py sentences <key> [--grep word ...] [--range 40-50]   # look up the source by the sentence numbers used in the worksheet
python tools/cite-bridge/bridge.py propose --load bridge/candidates/drafts.json     # check the writer's drafts and turn them into candidates
python tools/cite-bridge/bridge.py approve c001 --by person [--note reason]
python tools/cite-bridge/bridge.py approve c001 --by person --send-back --note reason   # return
python tools/cite-bridge/bridge.py confirm smith2020#e2 --by person            # summary check
python tools/cite-bridge/bridge.py confirm smith2020#e2 --source --by person [--result 違う] [--page "p.49 §4・3"] --note "…"  # check against the original (human check)
python tools/cite-bridge/bridge.py review --source-checks [--json] [--images DIR] [-o output]  # excerpts still waiting for a check against the original (--json is a request to an external AI)
python tools/cite-bridge/bridge.py --citations <another citations file> check   # when there are several manuscripts, or to try on a copy
python tools/cite-bridge/bridge.py extract [<key> ...] [--force]  # make extracted text from the original PDF (pymupdf; with a header)
python tools/cite-bridge/bridge.py extract [<key> ...] --header-only  # add a header to old extracted text without one (the body is unchanged)
python tools/cite-bridge/bridge.py snapshot <key> [<URL>]       # copy of a web source (default: the URL in the bibliography line)
python tools/cite-bridge/bridge.py snapshot <key> --rebuild     # rebuild the body from the saved raw HTML (without fetching again)
python tools/cite-bridge/bridge.py strip <manuscript> <output>            # make a copy without marks
python tools/cite-bridge/bridge.py checkpoint [--label interim] [--by person]   # record, as a manifest, a point that passed check --strict (with the tool's version); with an approvers list, --by (human) is required
python tools/cite-bridge/bridge.py precommit                       # called from git's pre-commit (hook section)
python tools/cite-bridge/bridge.py classify [--send] [--list [--all]] [--cids c001 ...] [--limit N]   # classifier check (docs/classifier.md; nothing is sent without --send)
python tools/cite-bridge/bridge.py classify --eval <set.json> --variant <variant.toml> [--types type …] [--reps 2] [--send]   # wording measurement (not written to the ledger)
```

- snapshot saves the raw HTML to `<web_dir>/<key>.html` (not tracked) and the body to `<key>.txt` (tracked). The location becomes 「Web 写し（取得日） / 見出し」 (web copy (date of retrieval) / heading).
  The copy stays as it was when retrieved. When it is retrieved again, the date changes and the match is derived again.
- OCR is not built into the tool. Put text made by OCR at `<text_dir>/<same name as the PDF>.txt` with a header starting with `<!-- ocr` (engine, date) at the top.
  Its grade becomes 「PDF所持（OCR の抽出）」 (PDF held, OCR extraction), and it is not counted as machine-checkable. Because of misreadings, matches are often approximate.
- grade gives the grade per bibliography key. Given a mapping table with `--keys-from`, it also shows keys in the table's key column that are not in the bibliography (leftovers of renaming, etc.).
- checkpoint writes `bridge/checkpoints/<UTC time>.json` only when there are neither consistency errors nor pending items (its contents are in SPEC.md §8).

## What an AI must follow

- Copy verbatim text from the extracted text or the original. Do not make it from memory or a summary.
- Leave who wrote a judgment field in its written_by. Summaries and what-it-does-not-say written by an AI are candidates until a person has looked at them.
- Approve (approve) only when a person tells you to, or when a person has delegated approval (with `count_model = true`, to an AI listed as `model:<family>` in the approvers list and independent of the writer).
  An AI does not approve citations written by itself or by an AI of the same family. The same goes for returns and summary checks (confirm).
  apply writes decisions files. Decisions files are made by a person using the approval HTML, or by an AI a person delegated to that is independent of the writer. The same goes for accepting candidates: the writer AI writes only drafts.
- In candidate drafts, if the source and the sentence diverge, write them as they diverge (set the difference from the original to extrapolation, and give the reason in the interpretation and in what it does not say). Do not bend the reading toward the sentence.
- When asking a person to check, show review's output. Even when you assemble material by hand, do not fill in surrounding sentences. For OCR layers, show the page image.
- Do not edit derived fields by hand. If something is wrong, fix the verbatim text or the extracted text and run derive.
- The writer AI does not record checks against the original, summary checks or approvals for the excerpts and citations it wrote (the tool also refuses model checkers not independent of the writer).
- Do not write the source_check field by hand (go through `confirm --source` or `apply`; it needs a fingerprint).
- It is a person who decides whether to delegate to an external AI and who lists that AI in the approvers list.
