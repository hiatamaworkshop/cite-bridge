# Getting started: take one citation from start to finish

Japanese original: [getting-started.md](getting-started.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

This guide only covers the path that takes one citation from an excerpt to approval and `check --strict`. All commands are in SKILL.md (English: SKILL.en.md); file formats are in SPEC.md (English: SPEC.en.md).
It uses the example set (`examples/first-citation/`). The source is a short fictional study, and its extracted text is bundled instead of a PDF.

Type the commands at the root of the repository where you use the tool (an empty folder is fine if you are only trying it). The tool is assumed to be at its default location, `tools/cite-bridge/`.
Lines with dates and fingerprints are left out of the example outputs.

About language: the tool's output is in Japanese only for now, so the expected outputs below are shown as the tool prints them, with an English gloss after each.
The example writes field names in Japanese (逐語, 強さ, and so on), which are canonical. English aliases are also accepted (`verbatim:`, `strength: observation`, `kind: claim`, …; SPEC.en.md §10).

## 0. Put things in place

Put the tool at `tools/cite-bridge/`, and copy the contents of the example set to the root. In sh (if this is not a git repository, copy the tool's folder instead of adding a submodule):

```sh
git submodule add https://github.com/hiatamaworkshop/cite-bridge.git tools/cite-bridge
cp -r tools/cite-bridge/examples/first-citation/. .
```

What you copied:

| File | Contents |
|---|---|
| `bridge/bridge.toml` | Settings: where the bibliography, extracted text, excerpts and citations are, and the approvers list (`hanako` is a human) |
| `bib.md` | Bibliography. The key is `tanaka2024` |
| `refs/_txt/tanaka2024.txt` | Extracted text of the source. With a real PDF, make it with `extract` (step 2 below) |
| `manuscript.md` | Manuscript (in Japanese). It has one source parenthesis, without a mark yet |
| `bridge/citations.md` | Citations file. Only the heading and `対象:` (target) |

## 1. Check readiness (read only)

Use `grade` to make sure the settings and the bibliography can be read and the source's extracted text exists. It changes nothing.

```sh
python tools/cite-bridge/bridge.py grade
```

Expected output (exit code 0):

```text
PDF所持（抽出あり）: 1  tanaka2024
--- 1 件のうち、機械で照合できるもの 1 件（100%）
```

(PDF held (extracted): 1, tanaka2024 / of 1 source, 1 can be matched by machine (100%).)

If it is not `PDF所持（抽出あり）` (PDF held, extracted), check the paths in `[bibliography]` and `[sources]` of the settings, or how `PDF:` is written in the bibliography.

Use `check` to make sure the citations file and the manuscript can be read. This also changes nothing.

```sh
python tools/cite-bridge/bridge.py check
```

Expected output (exit code 0):

```text
INFO  網羅: 原稿の出典らしきもの 1（括弧 1）のうち、印のあるもの 0、印の無いもの 1（印の無いものはこのツールが確かめていない。一覧は coverage、候補づくりは propose）
INFO  引用: 主張 承認済 0 / 要再確認 0 / 未承認 0、指示 0
--- 抜き書き 0 件  / 整合の崩れ 0 件
```

(Coverage: of 1 source-like item in the manuscript (1 parenthesis), 0 have a mark and 1 has none. / Citations: claims approved 0, needs recheck 0, not approved 0; pointers 0. / 0 excerpts, 0 consistency errors.)

It reports one source without a mark. You will now attach a citation to it.

## 2. Extract

When you have the original PDF, put it in `refs/` and make the extracted text with `python tools/cite-bridge/bridge.py extract tanaka2024` (needs pymupdf).
This example bundles the extracted text, so skip this step.

## 3. Excerpt

Copy one passage of the source verbatim from the extracted text. In the summary and in what it does not say, write nothing outside the verbatim range.
Create `bridge/excerpts/tanaka2024.md` with the following content:

```markdown
# tanaka2024

## e1
逐語: Speaking was faster than typing, but participants corrected more words after speaking.
強さ: 観察
要約: 話す入力は打つ入力より速かったが、話した後に直した語は多かった。
言っていないこと: 直す時間を含めた全体の時間で、話す方が速いとは言っていない。
記入: AI 2026-11-07
```

(逐語 verbatim; 強さ strength: 観察 observation; 要約 summary: "speech input was faster than typing, but more words were corrected after speaking"; 言っていないこと not_said: "it does not say speaking is faster in total time including corrections"; 記入 written_by.)

## 4. Citation and mark

Put the mark 〔c001〕 right after the source parenthesis in the manuscript, and write a block with the same ID in the citations file.
Create `manuscript.md` with the following content (only the mark is added):

```markdown
# 本文

## 先行研究

話す入力は打つ入力より速いが、話した後に直す語は多かったという報告がある（Tanaka, 2024）〔c001〕。
```

Create `bridge/citations.md` with the following content:

```markdown
# 引用
対象: manuscript.md

## c001
種類: 主張
抜き書き: tanaka2024#e1
理由: 音声の入力は速いが、直す手間が残ることを、先行研究の結果として示す
原文との差: 言い換え
記入: AI 2026-11-07
承認: 未
```

(種類 kind: 主張 claim; 抜き書き excerpts; 理由 reason: "shows, as a prior result, that speech input is fast but correction effort remains"; 原文との差 diff: 言い換え paraphrase; 承認 approval: 未 none.)

## 5. derive and check

`derive` writes the location, match and surrounding sentences (lines starting with `@`) into the excerpt. Do not edit them by hand.

```sh
python tools/cite-bridge/bridge.py derive
```

Expected output (exit code 0):

```text
derived: bridge/excerpts/tanaka2024.md（1 件）
```

`check` checks consistency. It shows that the verbatim text matches the source and that the citation is not approved yet.

```sh
python tools/cite-bridge/bridge.py check
```

Expected output (exit code 0):

```text
NOTE  bridge/citations.md:4 c001: 未承認（先行研究）
INFO  引用: 主張 承認済 0 / 要再確認 0 / 未承認 1、指示 0
--- 抜き書き 1 件 一致 1 / 整合の崩れ 0 件
```

(c001: not approved (section 先行研究, prior work). / Claims: approved 0, needs recheck 0, not approved 1; pointers 0. / 1 excerpt, 1 identical match, 0 consistency errors.)

`check --strict` stops while pending items (NOTE) remain. Use it before submission.

```sh
python tools/cite-bridge/bridge.py check --strict
```

Expected output (exit code 1):

```text
--strict: 確認待ちが残っている
```

(--strict: pending items remain.)

## 6. Approval

A person reads the manuscript sentence and the verbatim text of the source side by side and judges whether the source supports the sentence. `review` lays out the material.
Usually you judge on the page made by `review --html -o review.html` and write the saved decisions file with `apply`. This guide uses commands instead.

```sh
python tools/cite-bridge/bridge.py review c001
```

Expected output (exit code 0):

```text
## c001　未承認
> Speaking was faster than typing, but participants corrected more words after speaking.
- 照合: 一致
```

(c001 not approved / the verbatim text / match: identical.)

If the verbatim text and the summary agree, record the summary check.

```sh
python tools/cite-bridge/bridge.py confirm tanaka2024#e1 --by hanako
```

Expected output (exit code 0):

```text
要約の確認を記録: tanaka2024#e1 hanako
```

(Recorded summary check.)

If the source supports the sentence, record the approval. Approval is given by a person (a name that is human in the approvers list).

```sh
python tools/cite-bridge/bridge.py approve c001 --by hanako
```

Expected output (exit code 0):

```text
承認を記録: c001 hanako
```

(Recorded approval.)

## 7. check --strict

No pending items remain, and it passes.

```sh
python tools/cite-bridge/bridge.py check --strict
```

Expected output (exit code 0):

```text
INFO  抜き書きの要約の確認: hanako 1
INFO  引用: 主張 承認済 1 / 要再確認 0 / 未承認 0、指示 0
--- 抜き書き 1 件 一致 1 / 整合の崩れ 0 件
```

(Summary checks of excerpts: hanako 1. / Claims: approved 1, needs recheck 0, not approved 0; pointers 0. / 1 excerpt, 1 identical match, 0 consistency errors.)

If you later edit the manuscript sentence or the verbatim text, the citation returns to needing recheck and `check --strict` stops again. An approval is valid only for the sentence and the evidence as they were when it was given.

## What to read next

- Making candidates when the manuscript has many sources (`propose`) and the approval page (`review --html`): SKILL.md (SKILL.en.md)
- Checking against the original, needed for approximate matches and OCR sources: "Human check (checking against the original)" in SKILL.en.md
- The short block to put in an agent's instruction file: "Using it with an AI agent" in README.en.md
