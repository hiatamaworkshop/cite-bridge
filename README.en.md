# cite-bridge

Japanese original: [README.md](README.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

cite-bridge gives every citation in a paper an anchor (the verbatim text of the source and its location) and keeps the state of its checks correct while you write.

This is an experimental 0.x tool for people who write papers together with an AI. It promises only two things, the shape of the data and the guarantee statement (see "What the tool does" below); commands and output messages may change from version to version.

## What the tool does

Most citation errors make a real source say something it does not say. The tool does not try to detect that automatically.
Instead it does three things, every time.

1. It sets up a place to read a sentence of the manuscript side by side with the verbatim text of the source (`review`).
2. It pins the result a person checked to fingerprints of the sentence and the evidence (`approve`, `apply`).
3. When the sentence or the evidence changes later, it reports the citation as needing recheck (`check`).

What the machine guarantees is that the anchor (the verbatim text) exists in the source, and where it is. Whether the source supports the claim is guaranteed by a person's approval.
For this reason it is not called a "verification tool". It does not leave the judgment of support to a machine; instead, it lays out the same material for the person every time.

The tool promises two things: the shape of the data (the fields of excerpts and citations, fingerprints, decisions files and so on; SPEC.md §11.1) and the guarantee statement above. It does not promise commands or features. When the shape of the data changes, the version goes up, migration steps are written, and the old shape is read until the next version (SPEC.md §11.2).

## Example

Put a mark right after a citation in the manuscript. (The example is in Japanese: "There is a report that speaking is faster than typing, but more words are corrected after speaking (Tanaka, 2024).")

```markdown
話す入力は打つ入力より速いが、話した後に直す語は多かったという報告がある（Tanaka, 2024）〔c001〕。
```

Copy one passage of the source, verbatim, into the excerpt file (one md per source). The tool adds the location and match fields (`derive`).
The fields are 逐語 (verbatim), 強さ (strength), 要約 (summary), 言っていないこと (what it does not say) and 記入 (written by).

```markdown
## e1
逐語: Speaking was faster than typing, but participants corrected more words after speaking.
強さ: 観察
要約: 話す入力は打つ入力より速かったが、話した後に直した語は多かった。
言っていないこと: 直す時間を含めた全体の時間で、話す方が速いとは言っていない。
記入: AI 2026-11-07
```

In the citations file, write a block with the same ID as the mark, and link the excerpts that support the sentence.
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

When a person reads the manuscript sentence side by side with the verbatim text and approves it, the tool records the approval line and the fingerprints of the sentence and the evidence.
If this manuscript sentence or the excerpt is edited after the approval, `check` prints the following (the approval needs recheck because the sentence changed), and the pre-submission check (`check --strict`) stops until it is checked again.

```text
c001: 承認の後に本文が変わった。要再確認
```

The citation above is a claim (it states what the source says). A pointer (it only names a work or mentions that it exists) has just a bibliography key and needs no approval.

## Getting started

If you are new, use [docs/getting-started.en.md](docs/getting-started.en.md) to take one citation all the way through with this example set (`examples/first-citation/`).
The everyday flow is as follows (run commands at the root of the repository).

1. Put the settings `bridge/bridge.toml` in place (a template is in the "設定" (Settings) section of SKILL.md). The bibliography can be keyline, BibTeX or CSL-JSON.
2. Make extracted text from the original PDF (`bridge.py extract`; for web sources, `bridge.py snapshot <key>`).
3. Write excerpts and citations, and put marks in the manuscript. Sources without a mark can be turned into a worksheet with `bridge.py propose`.
4. Write the derived fields with `bridge.py derive`, and check consistency with `bridge.py check`.
5. A person judges on the page made by `bridge.py review --html -o review.html`, and the saved decisions file is written with `bridge.py apply <decisions file>`.
6. Before submission, run `bridge.py check --strict`; to record a milestone, run `bridge.py checkpoint`.

All the commands, git's pre-commit hook, and `--citations` for several manuscripts are in SKILL.md.

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

## Limits

- Only sources with extracted text or a web copy can be matched. A source with neither a PDF nor a web copy gets a grade that cannot be matched.
- For excerpts with an approximate match, OCR extraction, a short verbatim text and so on, the machine cannot guarantee that the verbatim text exists. The tool marks them 「要ヒューマンチェック」 (human check)
  and waits for a record that a person, or an external AI the person delegated to, checked them against the original (the "要ヒューマンチェック" (human check) section of SKILL.md).
- Sources without a mark (citations with no mark placed) are not checked by this tool. The "網羅" (coverage) line of `check` and `coverage` give their count and list.
- The tool cannot detect an approval made only for form (it does not record whether page images were opened, etc.). It prevents accidents, not malice.
- Detection of headings (sections) is an estimate.

## Documents

| Document | Contents |
|---|---|
| [SKILL.md](SKILL.md) | How to use the tool and the rules: the list of commands, the settings, what an AI must follow. The name and description at the top are the entry point when placed as an agent skill |
| [SPEC.md](SPEC.md) | The authoritative shape of the data: fields, fingerprints, approval states, decisions files, manifest, settings, version policy |
| [docs/getting-started.md](docs/getting-started.md) | Getting started. With the example set, goes from checking readiness to approving one citation and passing `check --strict` |
| [docs/classifier.md](docs/classifier.md) | An optional check. An external classifier assigns the record's vocabularies again and flags disagreements. It sends manuscript sentences and source excerpts out, so it is not used unless set up |
| [docs/development.md](docs/development.md) | For people who change the tool: the layout of the implementation, tests, the design document and the ledger of items |

Every document has an English version (`*.en.md`) in the same place.

## Requirements

- Python 3.11 or later (it uses `tomllib` from the standard library).
- It runs on the standard library alone. Only PDF extraction (`extract`, and `snapshot` of a PDF URL) needs `pymupdf`.

## Language

- The Japanese documents are authoritative; the English versions (`*.en.md`) are translations.
- The tool's output (messages from `check`, `review` and so on, and the text of the approval HTML) is in Japanese only for now, and the tool has no translation mechanism.
  If you want to change it, edit the text inside `cite_bridge/` on your side. Output text is outside what the tool promises (SPEC.md §11.1).
- Field names and values can also be written with English aliases (`verbatim:`, `strength: observation` and so on; SPEC.md §10). The names of the derived fields the tool writes (lines starting with `@`) become English with `[output] language = "en"` in the settings.
- For an English manuscript, change `sentence_end` in the settings to English sentence endings (the "設定" (Settings) section of SKILL.md).

## License

Released under the MIT License. The full text is in [LICENSE](LICENSE) at the root of the repository.
