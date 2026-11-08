# Classifier (optional check)

Japanese original: [classifier.md](classifier.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

An external classifier (currently Jev) independently assigns again the closed vocabularies of the record (difference from the original, strength and so on), and a flag is raised where it disagrees with the record.
It only raises flags; it does not change approval states. Confidence scores are not used in any rule. Without the setting, nothing changes.
The shape of the judgment ledger and of types is in §6.4 of [SPEC.md](../SPEC.md).

## Commands

| Command | What it does |
|---|---|
| `classify` | Prints only an estimate of what would be sent (number of requests, number of questions, characters). Sends nothing |
| `classify --send` | Sends the questions that have no judgment, or an outdated one, to the classifier. Judgments are kept in the ledger (`bridge/judgments.jsonl`, append-only) |
| `classify --list [--all]` | Prints the judgments in the ledger, compared with the current records. Sends nothing |

## Settings

The key is not written in the settings file (bridge.toml). The key is read only when sending, by looking at the following in order and using the first value found (`jev_key` in `cite_bridge/classifier.py`).

1. The environment variables `TYPESAFE_API_KEY`, then `JEV_API_KEY` (another name for the same key). An empty value (only whitespace) counts as absent.
2. `.env` (`KEY=VALUE` lines; comments and blank lines are ignored, and quotes at both ends are removed). It is looked for in the folder of bridge.toml (when changed with `--config`, the folder of that settings file; `bridge/` by default), then in the working folder. In each folder, the value is looked for as `TYPESAFE_API_KEY`, then `JEV_API_KEY`.
   If that `.env` exists inside a git repository and git does not ignore it, the tool stops without reading the key (`ClassifierUnavailable`; the request becomes SKIP and no judgment is written). Outside a repository, or without git, it reads the key without stopping.

If no key is found anywhere, `ClassifierUnavailable`. Put `.env` in that folder's `.gitignore` (`bridge/.gitignore`) and do not commit it.

```toml
[classifier]
provider = "jev"          # provider; omit it to not use a classifier
model = "jev-latest"      # optional
max_chars = 6000          # upper limit of characters of material per request; larger items are not sent
# types = ["cite.diff"]   # restrict the types used (omit for all registered types)
```

What is sent out: sentences of the manuscript, and the verbatim text and surrounding sentences of sources (including excerpts of copyrighted PDFs), go to an external service, which charges for it.
It sends only with `--send`.

## Default types (the minimal three)

| Type | What it looks at | Record it is compared with |
|---|---|---|
| `cite.diff` | Is the part of the manuscript sentence that cites the source identical to, a paraphrase of, a qualified generalization of, or an extrapolation from the verbatim text? | The citation's `原文との差` (difference from the original). Only judgments heavier than the record are flagged (`order`) |
| `cite.attribution` | Is the verbatim text the author's own claim, a report of others, or an assumption? | Flagged if it is a report of others |
| `cite.not_said` | Is the excerpt's "what it does not say" statement correct against the source? (Asking whether a negative statement "is written" inverts the answer.) | Flagged if wrong |

What a classifier reliably catches is conspicuous overstatement (widening the scope, turning something into an assertion, adding a conclusion). Fine misreadings that slightly change a qualification or the subject
were mostly missed in measurements on real data. Fine misreadings are left to human checks. The absence of a flag does not replace checking support.

The type that asks about the strength of the sentence (`cite.strength`) could not tell approved citations apart, so it was removed from the defaults. Overstatement is caught by 限定つき一般化 (qualified generalization) and 外挿 (extrapolation) in `cite.diff`.
To use it, add it with `[[checks]]` as in the example below.

## Adding a type

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
The classifier only raises flags and has no action that lowers the approval state. Use a new type after measuring its agreement with human approvals.

## Measuring wording (classify --eval)

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

## Adding a provider

Write a class that inherits `Classifier` and add one line to `PROVIDERS` (`cite_bridge/classifier.py`). The adapter's contract is a single method, `classify(state, asks) -> list[Verdict | None]`.
state is the wording of the shared material; asks are mutually independent questions about the same state. A Verdict has label (one of labels), score (Optional) and scores (all labels).
A question that could not be answered is None; a failure of the whole call is `ClassifierUnavailable` (no judgment is written). Data is sent out only with `classify --send`.
