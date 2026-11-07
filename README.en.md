# cite-bridge

Japanese original: [README.md](README.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

cite-bridge gives every citation in a paper an anchor (the verbatim text of the source and its location) and keeps the state of its checks correct while you write.

## What the tool does

Most citation errors make a real source say something it does not say. The tool does not try to detect that automatically.
Instead it does three things, every time.

1. It sets up a place to read a sentence of the manuscript side by side with the verbatim text of the source (`review`).
2. It pins the result a person checked to fingerprints of the sentence and the evidence (`approve`, `apply`).
3. When the sentence or the evidence changes later, it reports the citation as needing recheck (`check`).

What the machine guarantees is that the anchor (the verbatim text) exists in the source, and where it is. Whether the source supports the claim is guaranteed by a person's approval.
For this reason it is not called a "verification tool". It does not leave the judgment of support to a machine; instead, it lays out the same material for the person every time.
An approval by someone listed as model in the approvers list (the `approvers` setting) stays in the record but is not counted as approved; the citation stays pending, waiting for a human approval.

The tool promises two things: the shape of the data (the fields of excerpts and citations, fingerprints, decisions files and so on; SPEC.md §11.1) and the guarantee statement above. It does not promise commands or features. When the shape of the data changes, the version goes up, migration steps are written, and the old shape is read until the next version (SPEC.md §11.2).

## Parts

| What you keep | Contents |
|---|---|
| Excerpts (one md per source) | For each passage of a source: verbatim text, strength, summary, what it does not say. The tool derives the location and the match |
| Citations (one file) | For each place in the manuscript: the excerpts it rests on, the reason, the difference from the original, the approval |
| Settings (bridge.toml) | Paths, how to read the bibliography, the mark format, approvers. The tool holds no other paper-specific information |

Put a mark right after a citation in the manuscript (〔c001〕 by default), and write a block with the same ID in the citations file.
There are two kinds of citation. A claim (it states what the source says) has excerpts, a reason, a difference from the original and an approval, and waits for a person's approval.
A pointer (it only names a work or mentions that it exists) has just a bibliography key and needs no approval. As in ordinary citation practice, it is enough that the referenced work is in the bibliography.

## Minimal use

Run commands at the root of the repository. If you are new, start with `docs/getting-started.md`, which takes one citation all the way through using the example set (English: `docs/getting-started.en.md`).

1. Put the settings in place. A template is in the "設定" (Settings) section of SKILL.md. The bibliography can be keyline, BibTeX or CSL-JSON.
2. Make extracted text from the original PDF with `bridge.py extract` (with a header; for an old extraction without a header, add one with `extract --header-only`). For web sources, use `bridge.py snapshot <key>`.
3. Write excerpts, write citations, and put marks in the manuscript. Sources without a mark can be turned into a worksheet with `bridge.py propose` (narrow it with `--key <key>` to sources whose key candidates include that key, or with `--checkable` to sources whose grade can be checked by machine).
4. Write the derived fields (location, match, surrounding sentences, human check) with `bridge.py derive`, and check consistency with `bridge.py check`.
5. Make the approval page with `bridge.py review --html -o review.html`; a person judges and saves a decisions file.
6. Write the decisions with `bridge.py apply <decisions file>`. For excerpts marked for human check, record the check as described in "Checking against the original" below.
7. Before submission, run `bridge.py check --strict`; to record a milestone, run `bridge.py checkpoint` (with `--by <person>` when there is an approvers list).

To run the check in git's pre-commit, use the bundled `hooks/pre-commit` (the "hook" section of SKILL.md).

## Using it with an AI agent

In the repository where you use the tool, copy only the short block below into the instruction file your agent reads. Point to the usage guide (SKILL.md) rather than copying it,
because a copy drifts each time the tool's version moves on. Choose the file your agent reads: AGENTS.md, CLAUDE.md, GEMINI.md and so on.
The paths are the default location (`tools/cite-bridge/`) and the default settings file (`bridge/bridge.toml`); if you changed them, adjust the paths.
The block points to the Japanese originals, which are authoritative and which agents read as they are. If you prefer, point to `SKILL.en.md` and `SPEC.en.md` instead.

```markdown
## Citations (cite-bridge)

- Read: before writing citations or excerpts, read tools/cite-bridge/SKILL.md and follow it. The file formats are in tools/cite-bridge/SPEC.md.
- Check: after writing, run `python tools/cite-bridge/bridge.py derive` and `python tools/cite-bridge/bridge.py check`, and leave no ERROR.
  Before submission, run `python tools/cite-bridge/bridge.py check --strict`.
- Source of truth: the state of citation checks lives in the excerpt and citation files that the settings bridge/bridge.toml point to. Lines starting with `@` are written by the tool; do not edit them by hand.
```

## Checking against the original (human check)

For some excerpts the machine cannot guarantee that the verbatim text exists: those whose match is approximate or impossible, those from an OCR extraction or an OCR text layer, those with unreadable characters within the verbatim range, and those with a short verbatim text (3 words or fewer in Western text, 10 characters or fewer in Japanese text; a short text can match by chance and does not pin down the location).
The tool marks them "要ヒューマンチェック" (human check needed) and, while there is no record of a check against the original, reports them as pending (NOTE). The check is done by a person, or by an external AI the person delegates to.

| Command | What it does |
|---|---|
| `review --source-checks [--images DIR] [-o output.md]` | Lists the excerpts still waiting for a check against the original (md; page images can be attached) |
| `review --source-checks --json -o request.json` | A request to hand to an external AI (`cite-bridge-source-checks/1`). The answer goes in `source_checks` of a decisions file |
| `confirm <key#eN> --source --by <name> [--result 一致\|違う] [--page "p.49 §4・3"] [--note …]` | Writes the record of a check against the original. When the result is 違う (differs), put the characters of the original in --note |
| `apply <decisions file>` | Writes the `source_checks` of a decisions file (only those whose verbatim fingerprint matches the current one) |

- A record holds the checker, the date, the result (一致 matches, or 違う differs), the page and section, and a note. The checker is a name from the approvers list; a model checker counts only if it is not the writer of the excerpt (names are compared ignoring full-width and half-width forms, letter case, and leading and trailing spaces).
- Editing the verbatim text makes the record invalid, and it must be checked again. The tool does not edit verbatim text.
- Free-text records from 0.2.0 and earlier are not valid. Check again and record again.

Rules for delegating.

1. A person may delegate human-check requests to an external AI. The person decides whether to delegate, and the person lists the delegated AI as model in the approvers list.
2. The delegated AI receives the request from `review --source-checks --json` and writes a decisions file under its own name. The person passes it to `apply`.
3. The writer AI (the model that wrote the excerpt) cannot record a check against the original for its own excerpts.
4. Who checked is kept in the checker of each record and in the manifest's counts per kind of checker. The final submission (`checkpoint --by`) is made by a person.
5. The tool does not call external AIs. It only writes out the request JSON and receives the decisions file.

## Classifier (optional check)

An external classifier (currently Jev) independently assigns again the closed vocabularies of fields the bridge stores (difference from the original, strength and so on), and a flag is raised where it disagrees with the record.
It only raises flags; it does not change approval states. Confidence scores are not used in any rule. Without the setting, nothing changes.

| Command | What it does |
|---|---|
| `classify` | Prints only an estimate of what would be sent (number of requests, number of questions, characters). Sends nothing |
| `classify --send` | Sends the questions that have no judgment, or an outdated one, to the classifier. Judgments are kept in the ledger (`bridge/judgments.jsonl`, append-only) |
| `classify --list [--all]` | Prints the judgments in the ledger, compared with the current records. Sends nothing |

Settings (bridge.toml). Do not write the key there; pass it in the environment variable `JEV_API_KEY` (or `TYPESAFE_API_KEY`, another name for the same key). If the environment variable is absent, the key is read from `.env` in the same folder as `bridge.toml` (a `JEV_API_KEY=...` line). Put `.env` in that folder's `.gitignore` (`bridge/.gitignore`) and do not commit it. The key is not read from a `.env` that git does not ignore.

```toml
[classifier]
provider = "jev"          # provider; omit it to not use a classifier
model = "jev-latest"      # optional
max_chars = 6000          # upper limit of characters of material per request; larger items are not sent
# types = ["cite.diff"]   # restrict the types used (omit for all registered types)
```

What is sent out: sentences of the manuscript, and the verbatim text and surrounding sentences of sources (including excerpts of copyrighted PDFs), go to an external service, which charges for it.
It sends only with `--send`.

### Default types (the minimal three)

| Type | What it looks at | Record it is compared with |
|---|---|---|
| `cite.diff` | Is the part of the manuscript sentence that cites the source identical to, a paraphrase of, a qualified generalization of, or an extrapolation from the verbatim text? | The citation's `原文との差` (difference from the original). Only judgments heavier than the record are flagged (`order`) |
| `cite.attribution` | Is the verbatim text the author's own claim, a report of others, or an assumption? | Flagged if it is a report of others |
| `cite.not_said` | Is the excerpt's "what it does not say" statement correct against the source? (Asking whether a negative statement "is written" inverts the answer.) | Flagged if wrong |

What a classifier reliably catches is conspicuous overstatement (widening the scope, turning something into an assertion, adding a conclusion). Fine misreadings that slightly change a qualification or the subject
were mostly missed in measurements on real data. Fine misreadings are left to human checks. The absence of a flag does not replace checking support.

The type that asks about the strength of the sentence (`cite.strength`) was removed from the defaults. In measurements on real data it answered "strengthened" even for approved citations and could not tell them apart.
Overstatement is caught by 限定つき一般化 (qualified generalization) and 外挿 (extrapolation) in `cite.diff`. To use it, add it with `[[checks]]` as in the example below.

### Adding a type

Viewpoints for the check can be added under `[[checks]]` in `bridge.toml` (the same `type` overrides). Material and fields to compare with are named by SPEC.md's field names
(`citation.<field>`, `excerpt.<field>`). Three rules for adding one:

- Make it a closed choice. Always include 「判定できない」 (cannot judge) in `labels`. Do not let the classifier write sentences.
- Say what it is compared with. To compare with a field of the record, use `compare`; if there is none, put the labels to flag in `flag_on`.
- Changing the wording or the choices makes earlier judgments outdated (the fingerprint of the type's wording changes). When it becomes logically a different type, raise `version`.

```toml
[[checks]]
type = "cite.strength"
version = 3
for = "citation"                     # citation (per citation) or excerpt (per excerpt)
question = "本文の文のうち、{about} を引いている部分は、原典の逐語と比べて、どの強さで述べているか。"
labels = ["同じ強さ", "強めている", "弱めている", "判定できない"]
flag_on = ["強めている"]
about = "citation.出典"              # the field that fills {about} in the question
[checks.gloss]
"強めている" = "推測を断定にする、条件や限定を外す、範囲を広げる"
[checks.materials]
claim = "citation.sentence"
source = "excerpt.逐語"
```

The names, versions and wording fingerprints of registered types are kept in the `classifier` field of the `checkpoint` manifest.
A new type is first used only to raise flags; after measuring its agreement with human approvals, an action that lowers the approval state (`on_disagree`) may be considered. That is not implemented yet.

### Measuring wording (classify --eval)

The wording that works differs by provider. When you change the wording, measure first and then adopt it. Measurements are not written to the ledger.

```
bridge.py classify --eval <eval set.json> --variant <wording variant.toml> [--variant …] [--types type …] [--reps 2] [--split tune|holdout|all] [--verbose] [--send]
```

The types as configured (the variant named 「設定」, "settings") are always measured. To measure only a new type, pass a variant that defines it together with `--types`
(a type absent from the settings is not sent with the settings variant).

- An eval set (`cite-bridge-eval/1`) holds two kinds of items: approved citations (correct when no flag is raised) and mutations that artificially break their sentence
  (dropping a qualification, turning a guess into an assertion, adding a conclusion; correct when the types listed in `flag` raise a flag). A set of correct items alone cannot measure detection, so make broken ones.
- Items are counted separately for tuning (tune) and for confirmation (holdout). Measuring only on the tuning items misses overfitting.
  Other split names (for example `real`, a collection of errors actually found) also appear as rows in the table.
- The output, per variant, type and split: "false flags on approved items", "detection of mutations", "cannot judge", "margin between the top two probabilities (a sign of ambiguity)", "share of identical answers across repetitions".
  Results are kept as JSON in `results/` next to the eval set.
- Items whose sentence and source are in different languages (a Japanese sentence citing an English source, for example) are also counted per language pair (sentence/source, e.g. `ja/en`).
  The tool detects the language from the sentence and the verbatim text (ja if it contains kana or kanji, en if it has only Latin letters). Separate tables appear only when there are two or more pairs.
  The tool does not translate; comparison across languages is left to the provider. To check the effect of language, put in the set an item whose sentence says the same thing in another language (`twin`);
  pairs whose flags differ from the original item are reported. If mutations have a difficulty (`level`), counts are also given per difficulty.
- Mutations you make follow your own view. If you put into the set the actual wording of errors that were found and fixed, specifying `evidence` and `record`,
  you can measure with errors you did not design (a sentence without a citation mark is fine).
- A wording variant is TOML in the same form as `[[checks]]` in `bridge.toml`, and overrides the definition with the same type.

Preparing the material (default): marks and source parentheses are removed from the manuscript sentence, and the question names which source's part to look at (`citation.出典`, first author and year).
Surrounding sentences are cut at 200 characters (leftovers of extraction can join into one long sentence).

### Adding a provider

An adapter has only one method, `classify(state, asks) -> verdicts` (`cite_bridge/classifier.py`).
Write a class that inherits `Classifier` and add one line to `PROVIDERS`.

## Layout of the implementation

The entry point is `bridge.py` (it only takes arguments and passes them to `cite_bridge/cli.py`). The implementation is split by responsibility under `cite_bridge/`.

| Module | Contents |
|---|---|
| config | Reading the settings (bridge.toml), the state the settings decide (other modules read it as `cfg.X`), constants for field names and values |
| source | Normalizing sources, matching, detecting headings and sections, surrounding sentences |
| bib | Bibliography adapters (keyline, BibTeX, CSL-JSON) and source grades |
| blocks | Reading and writing the md of excerpts and citations |
| derive | Making the derived fields (location, match, surrounding sentences) |
| manuscript | Marks, sentences and fingerprints in the manuscript, coverage, computing approval states |
| check | Consistency check (check), coverage list (coverage), grade list (grade) |
| approve / apply | Writing approvals, send-backs, summary checks and remarks, and applying decisions files |
| propose | Making candidates for sources without a mark |
| judge / classifier | The core of the classifier check (type registry, material, ledger, comparison with records, requests and sending) and provider adapters. judge does not import review |
| classify / evaluate | Classifier commands (classify and --list) and wording measurement (classify --eval) |
| review (templates/) | Review material (md, JSON) and the approval HTML. HTML and JavaScript live in templates/ |
| fetch | PDF extraction and copies of web sources |
| checkpoint | Manifest, tool version, pre-commit, removing marks |

## Documents

| Document | Contents |
|---|---|
| SKILL.md | How to use and run the tool: the list of commands and what an AI must follow. Plain Markdown; the name and description at the top are the entry point when placed as an agent skill |
| SPEC.md | The authoritative file formats: fields, fingerprints, approval states, decisions files, manifest, settings, version policy |
| docs/getting-started.md | Getting started. With the example set (`examples/first-citation/`), goes from checking readiness to approving one citation and passing `check --strict` |

This README and the three above have English versions in the same place (`README.en.md`, `SPEC.en.md`, `SKILL.en.md`, `docs/getting-started.en.md`). The Japanese versions are authoritative.
The design is in `docs/design-0.3.0.md` (the design of the mechanisms added in 0.3.0; Japanese only).

## Requirements

- Python 3.11 or later (it uses `tomllib` from the standard library).
- It runs on the standard library alone. Only PDF extraction (`extract`, and `snapshot` of a PDF URL) needs `pymupdf`.
  The tested versions of `pymupdf` are 1.28.2 and 2.0 (all tests passed on both). Without `pymupdf`, only the tests that make PDFs are skipped.
- Tests: `python -m unittest discover -s tests`. They do not depend on the user's data; each builds a small set in a temporary folder.
  The tests of the approval HTML's JavaScript use node (only those tests are skipped without it).

## Language

- The Japanese documents are authoritative; the English versions (`*.en.md`) are translations.
- The tool's output (messages from `check`, `review` and so on, and the text of the approval HTML) is in Japanese only for now. The tool has no translation mechanism.
  If you want another language or different wording, edit the text inside `cite_bridge/` on your side. Output text is outside what the tool promises (SPEC.md §11.1); where the text lives and how it is worded may change between versions.
- Field names and values can also be written with English aliases (`verbatim:`, `strength: observation` and so on; SPEC.md §10). The names of the derived fields the tool writes (lines starting with `@`) become English with `[output] language = "en"` in the settings.
- For an English manuscript, change `sentence_end` in the settings to English sentence endings (the "設定" (Settings) section of SKILL.md).

## Limits

- Only sources with extracted text or a web copy can be matched. A source with neither a PDF nor a web copy gets a grade that cannot be matched.
  PDFs whose extraction is garbled, OCR, and pages drawn by JavaScript end up as approximate or impossible matches, and a person checks them on the page image.
- Sources without a mark (citations with no mark placed) are not checked by this tool. The "網羅" (coverage) line of `check` and `coverage` give their count and list.
- The tool cannot detect an approval made only for form (it does not record whether page images were opened, etc.). It prevents accidents, not malice.
- Detection of headings (sections) is an estimate.

## License

Released under the MIT License. The full text is in [LICENSE](LICENSE) at the root of the repository.
