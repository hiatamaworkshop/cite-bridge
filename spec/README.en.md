# Conformance files

Japanese original: [README.md](README.md). This English version is a translation; the Japanese version is authoritative, and where the two differ, follow it.

These files let an implementation other than cite-bridge (a tool that reads published packages, for example) check that it conforms to [SPEC.md](../SPEC.md).
Both are JSON and language-neutral. SPEC.md is authoritative; what is here is a machine-readable copy of the same content, and an end-to-end example.

| File | Contents |
|---|---|
| `vectors.json` | Examples of inputs and values from SPEC.md §4 (fingerprints) and §12.2 (package ID, `verbatim_sha256`). The list of the 29 whitespace characters |
| `publication.example.json` | One example of a published package (`cite-bridge-publication/1`), written by `publish` from a small set of files |
| `make_examples.py` | Rebuilds the two files above (`python spec/make_examples.py`). Run it when an example in SPEC.md changes and when the form of a published package changes |

## What another implementation checks

`vectors.json`:

- `whitespace` gives the code points (hexadecimal) of the 29 "whitespace" characters of SPEC §4. The whitespace class of a language's regular expressions may not match these 29 characters. Use this list.
- For each example in `fingerprints`: build `string` from the input by the rules of SPEC §4, and the first 8 digits of the SHA-1 of its UTF-8 bytes match `fingerprint`.
  `kind` is one of `verbatim` (verbatim fingerprint), `sentence` (sentence fingerprint), `evidence` (evidence fingerprint) and `summary` (summary fingerprint).
  A `summary` example with `searched_terms` is an absence excerpt; it uses the searched terms in place of the verbatim text (SPEC §4).
- For the `identity` example in `publication`: `object` serialized by the rules of SPEC §12.2 matches `string`, and its SHA-256 prefixed with `sha256-` matches `id`.
- For the `verbatim_sha256` example in `publication`: `verbatim` with whitespace removed matches `string`, and its SHA-256 matches `sha256`.

`publication.example.json`:

- The ID recomputed from `format`, `spec`, `content` and `records` matches `id` (SPEC §12.2).
- The fingerprints (verbatim, summary, sentence, evidence) and `verbatim_sha256` recomputed from the values in `content` match the values written (SPEC §4, §12.3).
- The fingerprint in each record of `records` matches the current fingerprint in `content`. The breakdown of approvals (`counted` under `approvals` in `decided_by`) matches the listed approvals (SPEC §12.5).

This example does not attach the source files (`source/`). Every `included` in `publication.files` is false, and only the fingerprints remain.

The cite-bridge tests (`tests/test_vectors.py`) check that these two files are the same as the examples in SPEC.md, and that the items above pass with calculations that follow the text of SPEC alone.
