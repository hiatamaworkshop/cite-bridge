# -*- coding: utf-8 -*-
"""適合試験のファイル（spec/、C58）が、SPEC の例と食い違わないかの試験。

spec/vectors.json は SPEC.md の §4 と §12.2 の例の写しで、spec/publication.example.json は公開物の例である。
別の実装（読む側の道具）は、この二つを通せば SPEC に合うと言える。ここでは、ファイルが SPEC と同じであることと、
例が SPEC の文だけに従った計算（実装の関数を使わない）で計算し直せることを確かめる。

実行:  python -m pytest -q tests/test_vectors.py
"""
import hashlib
import json
import re
import unittest

import test_bridge as tb
import test_spec
from test_publish import jcs, sha1_8, ws

SPEC_DIR = tb.BRIDGE.parent / "spec"


def load(name):
    return json.loads((SPEC_DIR / name).read_text(encoding="utf-8"))


def spec_block(prefix):
    return json.loads(re.search(r"```json\n(.*?)\n```", test_spec.section(prefix), re.S).group(1))


class VectorsTest(unittest.TestCase):
    def setUp(self):
        self.v = load("vectors.json")

    def test_same_as_the_examples_in_the_spec(self):
        """SPEC の例を直したら、spec/vectors.json も直す（直すまでここが落ちる）。"""
        self.assertEqual(self.v["fingerprints"], spec_block("## 4."))
        self.assertEqual(self.v["publication"], spec_block("### 12.2"))
        self.assertEqual(list(self.v), ["about", "fingerprint", "identity", "whitespace", "fingerprints", "publication"])

    def test_names_of_the_definitions(self):
        from cite_bridge import publish
        self.assertEqual({"fingerprint": self.v["fingerprint"], "identity": self.v["identity"]}, publish.SPEC)

    def test_whitespace_is_the_29_characters_of_the_spec(self):
        chars = [chr(int(h, 16)) for h in self.v["whitespace"]]
        self.assertEqual(chars, test_spec.SPEC_WHITESPACE)
        self.assertEqual(len(set(chars)), 29)
        self.assertTrue(all(re.fullmatch(r"[0-9A-F]{4}", h) for h in self.v["whitespace"]))

    def test_every_vector_can_be_recomputed_from_the_file_alone(self):
        """ファイルの空白の一覧だけを使って、すべての例を計算し直せる。"""
        white = {chr(int(h, 16)) for h in self.v["whitespace"]}
        for v in self.v["fingerprints"]:
            self.assertEqual("".join(c for c in test_spec.spec_string(v) if c not in white or c in "\t\n"), v["string"])
            self.assertEqual(hashlib.sha1(v["string"].encode("utf-8")).hexdigest()[:8], v["fingerprint"], v)
        by = {v["kind"]: v for v in self.v["publication"]}
        self.assertEqual("sha256-" + hashlib.sha256(jcs(by["identity"]["object"]).encode("utf-8")).hexdigest(), by["identity"]["id"])
        self.assertEqual(hashlib.sha256("".join(c for c in by["verbatim_sha256"]["verbatim"] if c not in white).encode("utf-8")).hexdigest(),
                         by["verbatim_sha256"]["sha256"])


class PublicationExampleTest(unittest.TestCase):
    def setUp(self):
        self.doc = load("publication.example.json")

    def test_id_follows_the_written_rule(self):
        core = {k: self.doc[k] for k in ("format", "spec", "content", "records")}
        self.assertEqual(self.doc["id"], "sha256-" + hashlib.sha256(jcs(core).encode("utf-8")).hexdigest())
        self.assertEqual(self.doc["format"], "cite-bridge-publication/1")

    def test_fingerprints_follow_spec_section_4(self):
        ex = {e["id"]: e for e in self.doc["content"]["excerpts"]}
        self.assertTrue(ex)
        for e in ex.values():
            self.assertEqual(e["verbatim_fingerprint"], sha1_8(ws(e["verbatim"])))
            self.assertEqual(e["verbatim_sha256"], hashlib.sha256(ws(e["verbatim"]).encode("utf-8")).hexdigest())
            s = "\n".join(ws(e[k]) for k in ("verbatim", "strength", "summary", "not_said"))
            for name, key in (("孫引き", "secondary_source"), ("訳", "translation")):
                s += f"\n{name}\t{ws(e[key])}" if e[key] else ""
            s += f"\n根拠の種類\t{e['evidence_kind']}" if e["evidence_kind"] != "文" else ""
            self.assertEqual(e["summary_fingerprint"], sha1_8(s))
        for c in self.doc["content"]["citations"]:
            self.assertEqual(c["sentence_fingerprint"], sha1_8(ws(c["sentence"])))
            if c["excerpts"]:
                s = "\n".join(f"{i}\t{ws(ex[i]['verbatim'])}" for i in sorted(c["excerpts"]))
                s += f"\n人の読み\t{ws(c['human_reading'])}" if c["human_reading"] else ""
                self.assertEqual(c["evidence_fingerprint"], sha1_8(s))

    def test_records_match_the_content(self):
        """各記録の指紋が、中身の今の指紋と合う。承認の内訳が、並んだ承認と合う（SPEC §12.5）。"""
        c, r = self.doc["content"], self.doc["records"]
        cit = {x["id"]: x for x in c["citations"]}
        ex = {x["id"]: x for x in c["excerpts"]}
        self.assertEqual([len(r[k]) for k in ("approvals", "summary_checks", "source_checks")], [1, 1, 1])  # 三つの種類の記録を一つずつ持つ
        for a in r["approvals"]:
            self.assertEqual((a["sentence_fingerprint"], a["evidence_fingerprint"]),
                             (cit[a["citation"]]["sentence_fingerprint"], cit[a["citation"]]["evidence_fingerprint"]))
        for x in r["summary_checks"]:
            self.assertEqual(x["summary_fingerprint"], ex[x["excerpt"]]["summary_fingerprint"])
        for x in r["source_checks"]:
            self.assertEqual(x["verbatim_fingerprint"], ex[x["excerpt"]]["verbatim_fingerprint"])
        counted = {}
        for a in r["approvals"]:
            key = a["kind"] if a["kind"] != "model" or not a["family"] else f"model:{a['family']}"
            counted[key] = counted.get(key, 0) + 1
        self.assertEqual(counted, r["decided_by"]["approvals"]["counted"])

    def test_keys_are_in_the_spec_and_the_example_is_clean(self):
        documented = set(re.findall(r'"(\w+)":', test_spec.section("### 12.1")))
        d = self.doc
        seen = set(d) | set(d["tool"]) | set(d["spec"]) | set(d["vocabulary"]) | set(d["content"]) | set(d["records"]) | set(d["publication"])
        for name in ("sources", "excerpts", "citations"):
            for item in d["content"][name]:
                seen |= set(item)
        for name in ("approvals", "summary_checks", "source_checks"):
            for item in d["records"][name]:
                seen |= set(item)
        self.assertEqual(seen - documented, set())
        self.assertEqual(d["content"]["sources"][0]["doi"], "10.9999/jt.2020.001")  # DOI は小文字の形（SPEC §12.1）
        # 例は元のファイルを添えず、作った手元の状態を持たない
        self.assertTrue(all(not rec["included"] for rec in d["publication"]["files"].values()))
        self.assertEqual((d["tool"]["commit"], d["tool"]["dirty"]), (None, False))


if __name__ == "__main__":
    unittest.main()
