# Development guide

Japanese original: [development.md](development.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

This document is for people who change the tool. How to use the tool and its rules are in [SKILL.md](../SKILL.md); the shape of the data is in [SPEC.md](../SPEC.md).

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

## Tests

- In the tool's folder, run `python -m pytest -q tests` (without pytest, `python -m unittest discover -s tests`).
  They do not depend on the user's data; each builds a small set in a temporary folder.
- The tests of the approval HTML's JavaScript use node (only those tests are skipped without it).
  The tests that make PDFs are skipped without `pymupdf`. The tested versions of `pymupdf` are 1.28.2 and 2.0.
- There are also tests of the documents: that SPEC's fields and formats match the implementation (`tests/test_spec.py`), that the getting-started guide works as written (`tests/test_getting_started.py`),
  and that the English versions match the Japanese ones in commands, options, code and links (`tests/test_translations.py`).

## When you edit the documents

- The Japanese version is authoritative. When you edit it, make the same change to the English version (`*.en.md`) in the same place. `tests/test_translations.py` does not check whether the translated sentences are right.
- When you change the shape of the data (the scope of SPEC.md §11.1), follow the steps in SPEC.md §11.2 and raise `TOOL_VERSION` in `cite_bridge/config.py`.

## Notes on how it works

Not rules for users, but things that help before reading the code. The code is authoritative.

- Matching is done only within the extracted text bound to the key (`<text_dir>/<name>.txt` with the same name as the PDF the bibliography points to, or else `<web_dir>/<key>.txt`). When nothing matches, matches in other sources are shown as hints.
- Match levels: identical (only whitespace differs; spaces next to Japanese characters are treated as typesetting and ignored), matches after normalization (NFKC, quotation marks and dashes, small kana, end-of-line hyphens; it says so when punctuation also differs),
  approximate (50% or more character overlap; the candidate location is shown), cannot be matched (no extraction, or a garbled one), no match.
- Pages are counted from page breaks (`\f`) in the extracted text. When the bibliography has a page range that fits the PDF's page count, the printed page is also shown.
- Extracted text is made with pymupdf (pdftotext garbled many Japanese PDFs).
- Only headings whose numbers advance in order are taken as headings, and table-of-contents lines are excluded (it is an estimate).
- The headers of copies and OCR (`<!-- … -->`) are excluded from surrounding sentences. In web copies, blank lines also separate sentences.
- Besides h1 to h6, snapshot picks up collapsible headings (summary of details, Google help's a.zippy) as subheadings.
  Alternative text of images (alt) is kept as `[図: …]` lines (so that content found only in figures, such as names of screen parts, falls within the verbatim text and matching).
  Images in a paragraph that also has text (arrow icons in the middle of a sentence, logos at the head of an item) are not figures and are not output (they would cut the sentence and break verbatim matching).
  When `--rebuild` rebuilds the copy, the date of retrieval and the hash stay and the date of rebuilding is added. The body's header holds the URL, the date of retrieval and the sha256 of the raw HTML.
- Coverage marks are bound to sources in three passes. First, when the bibliography and the citation's keys are available, a mark is bound to the source in the same sentence whose key candidates include the citation's key (if the evidence spans two sources, one mark covers two sources).
  Next, among the remaining sources, a mark is given to those whose directly following mark is not used yet (for several split sources, only one, from the front). Finally, unused marks are distributed from the front to the remaining sources without a mark.
- The clause a worksheet parenthesis covers is the span between the source parentheses before and after it in the same sentence. Key candidates are guessed from the names and years in and just before the parenthesis.

## Design and items

- The design is in [docs/design-0.3.0.md](design-0.3.0.md) (the design of the mechanisms added in 0.3.0; Japanese only).
- Open items, and records of closed items, are in [docs/roadmap.md](roadmap.md) (Japanese only).
