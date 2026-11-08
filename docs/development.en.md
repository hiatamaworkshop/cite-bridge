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

## Design and items

- The design is in [docs/design-0.3.0.md](design-0.3.0.md) (the design of the mechanisms added in 0.3.0; Japanese only).
- Open items, and records of closed items, are in [docs/roadmap.md](roadmap.md) (Japanese only).
