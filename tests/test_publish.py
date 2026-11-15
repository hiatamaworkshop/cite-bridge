# -*- coding: utf-8 -*-
"""公開物の書き出し（publish、SPEC §12、0.8.0）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_publish.py
"""
import copy
import hashlib
import json
import sys
import unittest

import test_bridge as tb

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge import publish  # noqa: E402

# SPEC §4 の「空白」の 29 字（test_spec.py と同じ並び）
WS = ([chr(c) for c in range(0x09, 0x0E)] + [chr(c) for c in range(0x1C, 0x20)] + [" ", "\x85", "\xa0", " "]
      + [chr(c) for c in range(0x2000, 0x200B)] + [" ", " ", " ", " ", "　"])

PUBLICATION = '[publication]\npublished_by = "Example Lab"\nlicense = "CC-BY-4.0"\nreference = "https://doi.org/10.9999/example"\n'
APPROVERS = '[approvers]\ntester = "human"\ntest = "model:acme"\n'


def ws(s):
    return "".join(c for c in s if c not in WS)


def sha1_8(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def jcs(v):
    """SPEC §12.2 の文だけに従った直列化（実装の関数を使わない）。鍵は符号位置の順、空白なし、文字列は必要な字だけをエスケープ。"""
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        short = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
        return '"' + "".join(short.get(c) or (f"\\u{ord(c):04x}" if ord(c) < 0x20 else c) for c in v) + '"'
    if isinstance(v, list):
        return "[" + ",".join(jcs(x) for x in v) + "]"
    return "{" + ",".join(jcs(k) + ":" + jcs(v[k]) for k in sorted(v)) + "}"


class PublishTest(unittest.TestCase):
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def setUp(self):
        tb.BridgeTest.setUp(self)
        self.configure()

    def configure(self, extra="", publication=PUBLICATION):
        self.write("bridge/bridge.toml", tb.CONFIG + APPROVERS + publication + extra)

    def checkpoint(self):
        """承認と確認を済ませ、マニフェストを書く。"""
        self.assertEqual(self.run_bridge("derive")[0], 0)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester", "--note", "原文のとおり")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--by", "tester")[0], 0)
        code, out = self.run_bridge("checkpoint", "--by", "tester")
        self.assertEqual(code, 0, out)

    def publish(self, name="pub"):
        code, out = self.run_bridge("publish", "-o", name)
        self.assertEqual(code, 0, out)
        return json.loads(self.read(f"{name}/publication.json")), out

    def working_files(self):
        return {p.relative_to(self.dir).as_posix(): p.read_bytes() for p in self.dir.rglob("*")
                if p.is_file() and "pub" not in p.relative_to(self.dir).parts[0]}

    # ---- 出す条件

    def test_refuses_without_a_manifest(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("publish", "-o", "pub")
        self.assertNotEqual(code, 0)
        self.assertIn("マニフェストが無い", out)
        self.assertFalse((self.dir / "pub").exists())

    def test_refuses_when_files_changed_after_the_manifest(self):
        self.checkpoint()
        self.write("manuscript.md", self.read("manuscript.md") + "\n足した文。\n")
        code, out = self.run_bridge("publish", "-o", "pub")
        self.assertNotEqual(code, 0)
        self.assertIn("manuscript: manuscript.md がマニフェストの後に変わった", out)
        self.assertFalse((self.dir / "pub").exists())

    def test_refuses_a_folder_that_is_not_empty_and_needs_published_by(self):
        self.checkpoint()
        (self.dir / "pub").mkdir()
        self.write("pub/old.txt", "x")
        code, out = self.run_bridge("publish", "-o", "pub")
        self.assertNotEqual(code, 0)
        self.assertIn("空のフォルダでない", out)
        self.assertEqual(self.read("pub/old.txt"), "x")

    def test_working_files_are_not_changed(self):
        self.checkpoint()
        before = self.working_files()
        self.publish()
        self.assertEqual(self.working_files(), before)

    # ---- 形（SPEC §12.1）

    def test_shape_and_what_is_left_out(self):
        self.checkpoint()
        doc, out = self.publish()
        self.assertEqual(list(doc), ["format", "id", "spec", "tool", "vocabulary", "content", "records", "publication"])
        self.assertEqual((doc["format"], doc["spec"]), ("cite-bridge-publication/1", {"fingerprint": "sha1-8", "identity": "sha256-jcs"}))
        c = doc["content"]
        self.assertEqual(list(c), ["manuscript", "sources", "excerpts", "citations"])
        self.assertEqual(list(c["manuscript"]), ["title", "file"])
        self.assertEqual(doc["publication"]["reference"], "https://doi.org/10.9999/example")
        # 引用が根拠にしている抜き書きだけ（e2・e3 はどの引用も根拠にしていない）
        self.assertEqual([e["id"] for e in c["excerpts"]], ["doe2020#e1"])
        self.assertEqual([s["key"] for s in c["sources"]], ["doe2020"])
        e = c["excerpts"][0]
        self.assertEqual(e["verbatim"], "Participants completed the task in 12 seconds on average.")
        self.assertEqual((e["strength"], e["evidence_kind"], e["translation"]), ("観察", "文", ""))
        self.assertEqual(set(e["derived"]), {"match", "location", "section_kind", "human_check", "hits"})  # 前後の文は持たない
        text = self.read("pub/publication.json")
        self.assertNotIn("No errors occurred during the study.", text)  # 抜き書き e1 の「後」の文
        cit = c["citations"][0]
        self.assertEqual((cit["id"], cit["kind"], cit["excerpts"], cit["diff"]), ("c001", "主張", ["doe2020#e1"], "一致"))
        self.assertNotIn("〔c001〕", cit["sentence"])
        self.assertNotIn("コメント", cit["sentence"])
        self.assertEqual(doc["vocabulary"]["strength"]["観察"], "observation")
        self.assertEqual(doc["vocabulary"]["result"], {"一致": "match", "違う": "differs"})
        self.assertIn(doc["id"], out)

    def test_every_key_is_in_the_spec(self):
        """書き出した JSON の鍵が、SPEC §12.1 の形にすべてある（マニフェストから写す欄と、対応表・people・files の中は除く）。"""
        import re
        import test_spec
        documented = set(re.findall(r'"(\w+)":', test_spec.section("### 12.1")))
        self.checkpoint()
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--source", "--by", "tester")[0], 0)
        self.assertEqual(self.run_bridge("checkpoint", "--by", "tester")[0], 0)
        doc, _ = self.publish()
        self.assertEqual(len(doc["records"]["source_checks"]), 1)
        seen = set(doc) | set(doc["tool"]) | set(doc["spec"]) | set(doc["vocabulary"]) | set(doc["content"]) | set(doc["records"])
        seen |= set(doc["publication"]) | set(doc["content"]["manuscript"]) | set(doc["content"]["manuscript"]["file"])
        for name in ("sources", "excerpts", "citations"):
            for item in doc["content"][name]:
                seen |= set(item)
        seen |= set(doc["content"]["sources"][0]["file"] or {}) | set(doc["content"]["excerpts"][0]["derived"])
        for name in ("approvals", "summary_checks", "source_checks"):
            for item in doc["records"][name]:
                seen |= set(item)
        for rec in doc["publication"]["files"].values():
            seen |= set(rec)
        self.assertEqual(seen - documented, set())

    def test_fingerprints_follow_spec_section_4(self):
        """JSON の指紋が、JSON の中の値から SPEC §4 の文だけで計算し直せる（実装の関数を使わない）。"""
        self.checkpoint()
        doc, _ = self.publish()
        e, cit = doc["content"]["excerpts"][0], doc["content"]["citations"][0]
        self.assertEqual(e["verbatim_fingerprint"], sha1_8(ws(e["verbatim"])))
        self.assertEqual(e["verbatim_sha256"], hashlib.sha256(ws(e["verbatim"]).encode("utf-8")).hexdigest())
        self.assertEqual(e["summary_fingerprint"], sha1_8("\n".join(ws(e[k]) for k in ("verbatim", "strength", "summary", "not_said"))))
        self.assertEqual(cit["sentence_fingerprint"], sha1_8(ws(cit["sentence"])))
        self.assertEqual(cit["evidence_fingerprint"], sha1_8(f"{e['id']}\t{ws(e['verbatim'])}"))

    def test_records_hold_counted_judgments_with_their_fingerprints(self):
        self.checkpoint()
        doc, _ = self.publish()
        r, c = doc["records"], doc["content"]
        self.assertEqual(r["approvals"], [{"citation": "c001", "by": "tester", "kind": "human", "family": None,
                                           "date": r["approvals"][0]["date"], "note": "原文のとおり",
                                           "sentence_fingerprint": c["citations"][0]["sentence_fingerprint"],
                                           "evidence_fingerprint": c["citations"][0]["evidence_fingerprint"]}])
        self.assertRegex(r["approvals"][0]["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual([(s["excerpt"], s["by"], s["summary_fingerprint"]) for s in r["summary_checks"]],
                         [("doe2020#e1", "tester", c["excerpts"][0]["summary_fingerprint"])])
        self.assertEqual(r["source_checks"], [])
        manifest = json.loads(next((self.dir / "bridge/checkpoints").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual((r["decided_by"], r["coverage"]), (manifest["decided_by"], manifest["coverage"]))
        self.assertEqual(r["decided_by"]["approvals"]["counted"], {"human": 1})
        self.assertEqual(doc["publication"]["checkpoint"], manifest["checkpoint"])

    def test_source_files_are_attached_and_listed(self):
        self.checkpoint()
        doc, _ = self.publish()
        files = doc["publication"]["files"]
        ckpt = next((self.dir / "bridge/checkpoints").glob("*.json")).name
        self.assertEqual(set(files), {"source/bridge/citations.md", "source/bridge/bridge.toml", "source/bridge/excerpts/doe2020.md",
                                      f"source/bridge/checkpoints/{ckpt}"})
        for name, rec in files.items():
            self.assertTrue(rec["included"], name)
            self.assertEqual(hashlib.sha256((self.dir / "pub" / name).read_bytes()).hexdigest(), rec["sha256"], name)
        self.assertNotIn("publication.json", " ".join(files))

    # ---- 逐語を出す範囲（SPEC §12.3）

    def test_withheld_verbatim(self):
        for target in ("doe2020", "doe2020#e1"):
            with self.subTest(target):
                self.configure(f'withhold_verbatim = ["{target}"]\n')
                if not (self.dir / "bridge/checkpoints").exists():
                    self.checkpoint()
                else:  # 設定を変えたので、マニフェストを書き直す
                    self.assertEqual(self.run_bridge("checkpoint", "--by", "tester")[0], 0)
                name = "pub_" + target.replace("#", "_")
                doc, out = self.publish(name)
                e = doc["content"]["excerpts"][0]
                self.assertIsNone(e["verbatim"])
                verbatim = "Participants completed the task in 12 seconds on average."
                self.assertEqual(e["verbatim_sha256"], hashlib.sha256(ws(verbatim).encode("utf-8")).hexdigest())
                self.assertEqual(e["verbatim_fingerprint"], sha1_8(ws(verbatim)))
                self.assertTrue(e["derived"]["location"])
                self.assertEqual(e["summary"], "平均12秒で課題を終えた。")  # 書き手の文は出す
                self.assertFalse(doc["content"]["sources"][0]["verbatim_published"])
                rec = doc["publication"]["files"]["source/bridge/excerpts/doe2020.md"]
                self.assertFalse(rec["included"])
                self.assertEqual(rec["sha256"], hashlib.sha256((self.dir / "bridge/excerpts/doe2020.md").read_bytes()).hexdigest())
                self.assertFalse((self.dir / name / "source/bridge/excerpts/doe2020.md").exists())
                # 逐語は、公開物のどのファイルにも無い（設定のファイルは添える。抜き書きのファイルは添えない）
                for p in (self.dir / name).rglob("*"):
                    if p.is_file():
                        self.assertNotIn("completed the task in 12 seconds on average.", p.read_text(encoding="utf-8").replace('\\"', '"')
                                         if p.name != "publication.json" else json.dumps([x["verbatim"] for x in doc["content"]["excerpts"]]), p)
                self.assertIn("逐語を外したもの 1 件", out)

    # ---- 名前（SPEC §12.4）

    def test_hidden_names(self):
        self.configure('names = "hide"\n[publication.people]\ntester = { orcid = "0000-0000-0000-0000" }\n')
        self.checkpoint()
        doc, out = self.publish()
        a = doc["records"]["approvals"][0]
        self.assertEqual((a["by"], a["kind"], a["family"]), (None, "human", None))
        self.assertEqual(doc["records"]["summary_checks"][0]["by"], None)
        self.assertEqual(doc["content"]["excerpts"][0]["written_by"], "model:acme")  # 記入「test」は一覧の model:acme
        self.assertEqual(doc["content"]["citations"][0]["written_by"], "model:acme")
        self.assertEqual(doc["publication"]["people"], {})
        self.assertTrue(all(not rec["included"] for rec in doc["publication"]["files"].values()))
        self.assertEqual([p.name for p in (self.dir / "pub").rglob("*") if p.is_file()], ["publication.json"])
        text = self.read("pub/publication.json")
        for name in ("tester", '"test', "test "):
            self.assertNotIn(name, text)
        self.assertIn("添えたファイル 0 件", out)

    def test_shown_names_keep_the_date_after_the_writer(self):
        self.write("bridge/excerpts/doe2020.md", self.read("bridge/excerpts/doe2020.md").replace("記入: test\n", "記入: test 2026-01-02\n", 1))
        self.configure('names = "hide"\nnotes = "hide"\n')
        self.checkpoint()
        doc, _ = self.publish()
        self.assertEqual(doc["content"]["excerpts"][0]["written_by"], "model:acme 2026-01-02")
        self.assertIsNone(doc["records"]["approvals"][0]["note"])  # notes = hide

    # ---- ID（SPEC §12.2）

    def test_id_follows_the_written_rule(self):
        self.checkpoint()
        doc, _ = self.publish()
        core = {k: doc[k] for k in ("format", "spec", "content", "records")}
        self.assertEqual(doc["id"], "sha256-" + hashlib.sha256(jcs(core).encode("utf-8")).hexdigest())
        self.assertEqual(jcs(core), publish.canonical(core))

    def test_id_depends_on_content_and_records_only(self):
        self.checkpoint()
        doc, _ = self.publish("pub1")
        self.assertIsNone(doc["publication"]["replaces"])
        # 公開の情報を変える。設定のファイルが変わるので、マニフェストを書き直す
        self.configure(publication='[publication]\npublished_by = "Another Name"\nreplaces = "' + doc["id"] + '"\n')
        self.assertEqual(self.run_bridge("checkpoint", "--by", "tester")[0], 0)
        doc2, _ = self.publish("pub2")
        self.assertEqual(doc2["id"], doc["id"])
        # 発表した論文の指し方も ID に入らない（論文に ID を書いた後で DOI が決まる）
        self.assertEqual((doc2["publication"]["published_by"], doc2["publication"]["replaces"], doc2["publication"]["license"],
                          doc2["publication"]["reference"]), ("Another Name", doc["id"], None, None))
        self.assertNotEqual(doc2["publication"]["checkpoint"], None)
        # 道具の版と公開の情報は ID に入らず、中身と記録は入る
        d = copy.deepcopy(doc)
        d["tool"]["version"], d["publication"]["published_at"] = "9.9.9", "2099-01-01T00:00:00Z"
        self.assertEqual(publish.publication_id(d), doc["id"])
        d["content"]["citations"][0]["sentence"] += "。"
        self.assertNotEqual(publish.publication_id(d), doc["id"])
        d = copy.deepcopy(doc)
        d["records"]["approvals"][0]["date"] = "2099-01-01"
        self.assertNotEqual(publish.publication_id(d), doc["id"])

    def test_settings_are_validated(self):
        self.checkpoint()
        for extra, word in (('names = "maybe"\n', "names は show か hide"), ('typo = 1\n', "知らない鍵"),
                            ('withhold_verbatim = "doe2020"\n', "withhold_verbatim は")):
            with self.subTest(extra):
                self.configure(extra)
                code, out = self.run_bridge("publish", "-o", "pub")
                self.assertNotEqual(code, 0)
                self.assertIn(word, out)
        self.configure(publication="")
        code, out = self.run_bridge("publish", "-o", "pub")
        self.assertNotEqual(code, 0)
        self.assertIn("published_by", out)


if __name__ == "__main__":
    unittest.main()
