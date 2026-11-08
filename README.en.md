# cite-bridge

Japanese original: [README.md](README.md). This is a translation; the Japanese version is authoritative, and if the two differ, follow it.

cite-bridge anchors each citation in a paper to the verbatim text of its source and its location, records what a person has checked, and tells you when the manuscript sentence or its evidence changes afterwards.

It is still experimental, and is meant for people who write papers with an AI. Commands and output messages may change between versions (what it does promise is under "What it does").

## What it does

Most citation errors are a real source made to say something it does not say. cite-bridge does not try to catch these automatically.
Instead, it does three things every time.

1. It puts the manuscript sentence next to the verbatim text of the source, so a person can read them together (`review`).
2. It records what the person confirmed, tied to fingerprints of the sentence and the evidence (`approve`, `apply`).
3. If the sentence or the evidence changes later, it flags the citation for recheck (`check`).

cite-bridge guarantees only that the anchor (the verbatim text) exists in the source, and where. Whether the source supports the claim is guaranteed by a person's approval.
That is why it is not called a verification tool. It leaves the judgment of support to a person, and gives that person the same material in the same form every time.

cite-bridge promises two things: the shape of the data (the fields of excerpts and citations, fingerprints, decisions files and so on; SPEC.md §11.1) and the guarantee above. It does not promise commands or features. When the shape of the data changes, the version goes up, migration steps are written, and the old shape is still read until the next version (SPEC.md §11.2).

## Terms

| Term | Meaning |
|---|---|
| 文献 (source) | One entry in the bibliography, referred to by its key |
| 原典 (original text) | The content of the source being cited |
| 原本 (original copy) | The PDF or paper of the source itself. When the extracted text cannot settle a match, the page of the original copy is checked (原本での確認, check against the original) |
| 出典 (source reference) | The parenthesis in the manuscript that names a source (such as 「（Tanaka, 2024）」) |
| 抜き書き (excerpt) | One passage of the original text, copied word for word |
| 引用 (citation) | A place in the manuscript, linked to the excerpts that support it. The manuscript carries a mark 〔c001〕 |
| 本文 (sentence) | The manuscript sentence that contains the citation's mark |

## Example

Put a mark right after a citation in the manuscript. (The example is in Japanese: "There is a report that speaking is faster than typing, but more words are corrected after speaking (Tanaka, 2024).")

```markdown
話す入力は打つ入力より速いが、話した後に直す語は多かったという報告がある（Tanaka, 2024）〔c001〕。
```

Copy one passage of the source, word for word, into the excerpt file (one md per source). cite-bridge adds the location and match fields (`derive`).
The fields are 逐語 (verbatim), 強さ (strength), 要約 (summary), 言っていないこと (what it does not say) and 記入 (written by).

```markdown
## e1
逐語: Speaking was faster than typing, but participants corrected more words after speaking.
強さ: 観察
要約: 話す入力は打つ入力より速かったが、話した後に直した語は多かった。
言っていないこと: 直す時間を含めた全体の時間で、話す方が速いとは言っていない。
記入: AI 2026-11-07
```

In the citations file, write a block with the same ID as the mark, and list the excerpts that support the sentence.
The fields are 種類 (kind: 主張, claim), 抜き書き (excerpts), 理由 (reason), 原文との差 (difference from the original: 言い換え, paraphrase), 記入 (written by) and 承認 (approval: 未, not yet).

```markdown
## c001
種類: 主張
抜き書き: tanaka2024#e1
理由: 音声の入力は速いが、直す手間が残ることを、先行研究の結果として示す
原文との差: 言い換え
記入: AI 2026-11-07
承認: 未
```

When a person reads the sentence next to the verbatim text and approves it, cite-bridge records the approval along with fingerprints of the sentence and the evidence.
If the sentence or the excerpt is edited after that, `check` prints the line below (the sentence changed after approval; recheck needed), and the pre-submission check (`check --strict`) fails until it is approved again.

```text
c001: 承認の後に本文が変わった。要再確認
```

The citation above is a claim: it states what the source says. A pointer, which only names a work or mentions that it exists, needs just a bibliography key and no approval.

## Getting started

If you are new, follow [docs/getting-started.en.md](docs/getting-started.en.md) to take one citation from start to finish with this example set (`examples/first-citation/`).
The everyday flow is below (run commands at the root of the repository).

1. Add the settings file `bridge/bridge.toml` (a template is in the "設定" (Settings) section of SKILL.md). The bibliography can be keyline, BibTeX or CSL-JSON.
2. Extract text from the source PDFs (`bridge.py extract`; for web sources, `bridge.py snapshot <key>`).
3. Write excerpts and citations, and put marks in the manuscript. For sources without a mark, `bridge.py propose` makes a worksheet.
4. Fill in the derived fields with `bridge.py derive`, and check consistency with `bridge.py check`.
5. A person makes decisions on the page built by `bridge.py review --html -o review.html`, then the saved decisions file is written with `bridge.py apply <decisions file>`.
6. Before submission, run `bridge.py check --strict`; to record a milestone, run `bridge.py checkpoint`.

All commands, the git pre-commit hook, and `--citations` for several manuscripts are in SKILL.md.

## Using it with an AI agent

In the instruction file your agent reads, in the repository where you use cite-bridge, copy only the short block below. Point to SKILL.md instead of copying it,
because a copy goes out of date with each new version. Use whichever file your agent reads: AGENTS.md, CLAUDE.md, GEMINI.md and so on.
The paths assume the default location (`tools/cite-bridge/`) and settings file (`bridge/bridge.toml`); adjust them if yours differ.
The block points to the Japanese originals, which agents can read as they are. You can point to `SKILL.en.md` and `SPEC.en.md` instead.

```markdown
## Citations (cite-bridge)

- Read: before writing citations or excerpts, read tools/cite-bridge/SKILL.md and follow it. The file formats are in tools/cite-bridge/SPEC.md.
- Check: after writing, run `python tools/cite-bridge/bridge.py derive` and `python tools/cite-bridge/bridge.py check`, and leave no ERROR.
  Before submission, run `python tools/cite-bridge/bridge.py check --strict`.
- Source of truth: the state of citation checks lives in the excerpt and citation files that the settings bridge/bridge.toml point to. Lines starting with `@` are written by cite-bridge; do not edit them by hand.
```

## Limits

- Only sources with extracted text or a web copy can be matched. A source with neither a PDF nor a web copy cannot be matched.
- For some excerpts, such as approximate matches, OCR text and very short verbatim passages, cite-bridge cannot confirm that the verbatim text exists. It marks them 「要ヒューマンチェック」 (human check)
  and waits until a person, or an external AI the person delegates to, records a check against the original (the "要ヒューマンチェック" (human check) section of SKILL.md).
- Sources without a mark (citations with no mark placed) are not checked. The "網羅" (coverage) line of `check` and `coverage` give their count and list.
- cite-bridge cannot tell whether an approval was given carelessly (it does not record whether page images were opened, for example). It prevents mistakes, not misuse.
- Heading (section) detection is a best guess.

## Documents

| Document | Contents |
|---|---|
| [SKILL.md](SKILL.md) | How to use it and the rules to follow: commands, settings, and what an AI must follow. The name and description at the top let it be installed as an agent skill |
| [SPEC.md](SPEC.md) | The reference for the data: fields, fingerprints, approval states, decisions files, manifest, settings, version policy |
| [docs/getting-started.md](docs/getting-started.md) | Getting started. Uses the example set to go from setup to approving one citation and passing `check --strict` |
| [docs/classifier.md](docs/classifier.md) | An optional check. An external classifier labels the records again and flags disagreements. It sends manuscript sentences and source excerpts to an outside service, so it is off unless you set it up |
| [docs/development.md](docs/development.md) | For people who change cite-bridge: code layout, tests, the design document and the list of work items |

Every document has an English version (`*.en.md`) next to it.

## Requirements

- Python 3.11 or later (it uses `tomllib` from the standard library).
- It needs only the standard library, except PDF extraction (`extract`, and `snapshot` of a PDF URL), which needs `pymupdf`.

## Language

- The Japanese documents are the originals; the English versions (`*.en.md`) are translations.
- Output (messages from `check`, `review` and so on, and the text of the approval HTML) is Japanese only for now, and cite-bridge has no translation mechanism.
  To change it, edit the text in `cite_bridge/` in your copy. Output text is not part of what cite-bridge promises (SPEC.md §11.1).
- Field names and values can also be written with English aliases (`verbatim:`, `strength: observation` and so on; SPEC.md §10). The derived fields cite-bridge writes (lines starting with `@`) get English names with `[output] language = "en"` in the settings.
- For an English manuscript, change `sentence_end` in the settings to English sentence endings (the "設定" (Settings) section of SKILL.md).

## License

Released under the MIT License. The full text is in [LICENSE](LICENSE) at the root of the repository.
