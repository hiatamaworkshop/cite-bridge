# 適合試験のファイル

English: [README.en.md](README.en.md)（正本はこの日本語の版で、英語の版は訳である）

cite-bridge でない実装（公開物を読む側の道具など）が、[SPEC.md](../SPEC.md) に合うかを確かめるためのファイルである。
どちらも JSON で、言語に依らない。正本は SPEC.md で、ここにあるのは同じ中身の機械で読める写しと、通しの例である。

| ファイル | 中身 |
|---|---|
| `vectors.json` | SPEC.md の §4（指紋）と §12.2（公開物の ID、`verbatim_sha256`）の、入力と値の例。空白の 29 字の一覧 |
| `publication.example.json` | 公開物（`cite-bridge-publication/1`）の例を一つ。小さな一式から `publish` で書き出したもの |
| `make_examples.py` | 上の二つを作り直す（`python spec/make_examples.py`）。SPEC.md の例を直したときと、公開物の形を変えたときに走らせる |

## 別の実装が確かめること

`vectors.json`:

- `whitespace` は、SPEC §4 の「空白」の 29 字の符号位置（16 進）である。言語の正規表現の空白は、この 29 字と一致しないことがある。この一覧を使う。
- `fingerprints` の各例について、SPEC §4 の規則で入力から `string` を作り、その UTF-8 の SHA-1 の先頭 8 桁が `fingerprint` と合うこと。
  `kind` は `verbatim`（逐語の指紋）、`sentence`（本文の指紋）、`evidence`（根拠の指紋）、`summary`（要約の指紋）のどれかである。
  `searched_terms` のある `summary` の例は不在の抜き書きで、逐語の代わりに探した語を使う（SPEC §4）。
- `publication` の `identity` の例について、`object` を SPEC §12.2 の規則で直列化した文字列が `string` と合い、その SHA-256 に `sha256-` を付けたものが `id` と合うこと。
- `publication` の `verbatim_sha256` の例について、`verbatim` から空白を除いた文字列が `string` と合い、その SHA-256 が `sha256` と合うこと。

`publication.example.json`:

- `format`・`spec`・`content`・`records` から計算し直した ID が、`id` と合うこと（SPEC §12.2）。
- `content` の値から計算し直した指紋（逐語、要約、本文、根拠）と `verbatim_sha256` が、書いてある値と合うこと（SPEC §4、§12.3）。
- `records` の各記録の指紋が、`content` の今の指紋と合うこと。承認の内訳（`decided_by` の `approvals` の `counted`）が、並んだ承認と合うこと（SPEC §12.5）。

この例は、元のファイル（`source/`）を添えていない。`publication.files` の `included` はすべて false で、指紋だけが残っている。

cite-bridge の試験（`tests/test_vectors.py`）は、この二つのファイルが SPEC.md の例と同じであることと、上の項目が SPEC の文だけに従った計算で通ることを確かめている。
