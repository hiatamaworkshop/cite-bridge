# -*- coding: utf-8 -*-
"""孫引き（設計 §6.6）の試験。一時フォルダに小さな一式を作って動かす。分類器は手元の偽のサーバ（test_classifier の FakeJev）。

実行:  python -m pytest -q tests/test_secondary_source.py
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import test_bridge as tb
from test_classifier import FakeJev

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge import judge  # noqa: E402
from cite_bridge.manuscript import summary_fingerprint  # noqa: E402


def with_secondary(text, eid, value):
    """抜き書き eid の欄（記入の前）に 孫引き を足す。"""
    head = f"## {eid}\n"
    start = text.index(head)
    end = text.index("\n## ", start + 1) if "\n## " in text[start + 1:] else len(text)
    block = text[start:end]
    line = "記入: test\n"
    assert block.count(line) == 1
    return text[:start] + block.replace(line, f"孫引き: {value}\n{line}") + text[end:]


class SecondarySourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeJev)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeJev.log.clear()
        tb.BridgeTest.setUp(self)
        conf = tb.CONFIG + (f'[classifier]\nprovider = "jev"\nmodel = "jev-test"\n'
                            f'endpoint = "http://127.0.0.1:{self.port}/v1/systemone"\n')
        self.write("bridge/bridge.toml", conf)
        self.run_bridge("derive")

    def tearDown(self):
        def writable(func, path, _exc):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(self.dir, onerror=writable)

    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def run_bridge(self, *args, key="test-key"):
        env = self.clean_env()
        env.pop("TYPESAFE_API_KEY", None)
        env.pop("JEV_API_KEY", None)
        if key:
            env["TYPESAFE_API_KEY"] = key
        r = subprocess.run([sys.executable, "-X", "utf8", str(tb.BRIDGE), *args], cwd=self.dir,
                           capture_output=True, text=True, encoding="utf-8", env=env)
        return r.returncode, r.stdout + r.stderr

    def set_excerpts(self, text):
        self.write("bridge/excerpts/doe2020.md", text)

    def excerpt_text(self):
        return self.read("bridge/excerpts/doe2020.md")

    # ---- 指紋（§6.2）

    def test_fingerprint_is_unchanged_without_secondary_source(self):
        fields = {"逐語": "a b", "強さ": "観察", "要約": "要約。", "言っていないこと": "なし。"}
        s = "\n".join(re.sub(r"\s", "", fields[n]) for n in ("逐語", "強さ", "要約", "言っていないこと"))
        self.assertEqual(summary_fingerprint(fields), hashlib.sha1(s.encode("utf-8")).hexdigest()[:8])
        self.assertEqual(summary_fingerprint({**fields, "孫引き": ""}), summary_fingerprint(fields))

    def test_fingerprint_changes_with_secondary_source_and_ignores_spaces(self):
        fields = {"逐語": "a", "強さ": "観察", "要約": "要約。", "言っていないこと": "なし。"}
        base = summary_fingerprint(fields)
        with_sec = summary_fingerprint({**fields, "孫引き": "西本（1996）"})
        self.assertNotEqual(with_sec, base)
        self.assertEqual(with_sec, summary_fingerprint({**fields, "孫引き": "西本 （1996）"}))

    def test_secondary_source_alias_reads_the_same_field(self):
        from cite_bridge.config import FIELD_ALIASES
        self.assertEqual(FIELD_ALIASES["secondary_source"], "孫引き")

    def test_adding_secondary_source_sends_summary_check_back(self):
        self.assertEqual(self.run_bridge("confirm", "doe2020#e2", "--by", "test")[0], 0)
        self.assertNotIn("確認し直す", self.run_bridge("check")[1])
        self.set_excerpts(with_secondary(self.excerpt_text(), "e2", "Smith（2010）"))
        self.assertIn("確認し直す", self.run_bridge("check")[1])

    # ---- check（§6.3）

    def test_related_work_info_is_cleared_by_secondary_source(self):
        related = lambda out: [ln for ln in out.splitlines() if "原典の関連研究の節" in ln]
        self.assertTrue(any("doe2020#e2:" in ln for ln in related(self.run_bridge("check")[1])))
        self.set_excerpts(with_secondary(self.excerpt_text(), "e2", "Smith（2010）"))
        self.assertEqual([ln for ln in related(self.run_bridge("check")[1]) if "doe2020#e2:" in ln], [])

    def test_claim_on_secondary_evidence_gets_info_and_key_hint(self):
        self.set_excerpts(with_secondary(self.excerpt_text(), "e1", "yamada2002、Smith（2010）"))
        code, out = self.run_bridge("check")
        line = next(ln for ln in out.splitlines() if "根拠 doe2020#e1 は孫引き" in ln)
        self.assertIn("c001", line)
        self.assertIn("根拠 doe2020#e1 は孫引き（yamada2002、Smith（2010））。本文で元の文献に帰属させているか確かめる", line)
        self.assertTrue(line.endswith("元の文献は書誌にある（yamada2002）。直接引けるか確かめる"), line)
        self.assertNotIn("ERROR", out)

    def test_secondary_source_without_bib_key_has_no_hint(self):
        self.set_excerpts(with_secondary(self.excerpt_text(), "e1", "西本（1996）"))
        line = next(ln for ln in self.run_bridge("check")[1].splitlines() if "根拠 doe2020#e1 は孫引き" in ln)
        self.assertTrue(line.endswith("本文で元の文献に帰属させているか確かめる"), line)

    # ---- 分類器（§6.4）

    def test_cleared_by_is_the_default_for_attribution(self):
        c = next(c for c in judge.DEFAULT_CHECKS if c["type"] == "cite.attribution")
        self.assertEqual(c["cleared_by"], "excerpt.孫引き")
        self.assertEqual(judge.EXCERPT_FIELDS["孫引き"], "secondary")

    def test_judge_status_cleared_only_on_flag_on_labels(self):
        c = next(c for c in judge.DEFAULT_CHECKS if c["type"] == "cite.attribution")
        self.assertEqual(judge.judge_status(c, "他者の紹介", [], False), "要確認")
        self.assertEqual(judge.judge_status(c, "他者の紹介", [], True), "一致")
        self.assertEqual(judge.judge_status(c, "著者の主張", [], True), "問題なし")
        self.assertEqual(judge.judge_status(c, judge.ABSTAIN, [], True), "判定できない")

    def test_cleared_reads_the_secondary_field_of_each_excerpt(self):
        c = next(c for c in judge.DEFAULT_CHECKS if c["type"] == "cite.attribution")
        unit = {"scope": "excerpt", "excerpts": [{"verbatim": "x", "secondary": ""}]}
        self.assertFalse(judge.cleared(c, unit))
        unit["excerpts"].append({"verbatim": "y", "secondary": "西本（1996）"})
        self.assertTrue(judge.cleared(c, unit))
        self.assertFalse(judge.cleared({"type": "t"}, unit))

    def test_validate_rejects_cleared_by_with_compare_and_bad_paths(self):
        base = {"type": "t", "version": 1, "for": "excerpt", "question": "q", "labels": ["a", "b", judge.ABSTAIN],
                "materials": {"source": "excerpt.逐語"}, "flag_on": ["a"]}
        judge._validate(dict(base, cleared_by="excerpt.孫引き"))  # 通る
        with self.assertRaises(SystemExit):
            judge._validate(dict(base, cleared_by="excerpt.孫引き", compare="excerpt.強さ"))
        with self.assertRaises(SystemExit):
            judge._validate(dict(base, cleared_by="citation.出典"))
        with self.assertRaises(SystemExit):
            judge._validate(dict(base, cleared_by="孫引き"))

    def test_classify_list_and_review_show_the_cleared_status(self):
        self.assertEqual(self.run_bridge("classify", "--send")[0], 0)
        listed = lambda: [ln for ln in self.run_bridge("classify", "--list", "--all")[1].splitlines()
                          if "exc:doe2020#e1" in ln and "cite.attribution" in ln]
        self.assertTrue(listed() and listed()[0].startswith("要確認"), listed())
        led = [json.loads(x) for x in self.read("bridge/judgments.jsonl").splitlines()]
        disk = next(e for e in led if e["item"] == "exc:doe2020#e1" and e["type"] == "cite.attribution")
        self.assertEqual(disk["status"], "要確認")  # 台帳の状態は判定の時点のまま

        self.set_excerpts(with_secondary(self.excerpt_text(), "e1", "yamada2002"))
        self.assertTrue(listed()[0].startswith("一致"), listed())
        led = [json.loads(x) for x in self.read("bridge/judgments.jsonl").splitlines()]
        disk = next(e for e in led if e["item"] == "exc:doe2020#e1" and e["type"] == "cite.attribution")
        self.assertEqual(disk["status"], "要確認")

        rv = json.loads(self.run_bridge("review", "--json", "--all")[1])
        ev = next(e for e in rv["citations"][0]["evidence"] if e["id"] == "doe2020#e1")
        self.assertEqual(ev["secondary"], "yamada2002")

    # ---- review（§6.5）

    def test_review_md_and_html_show_secondary_source(self):
        self.set_excerpts(with_secondary(self.excerpt_text(), "e1", "yamada2002"))
        md = self.dir / "review.md"
        code, out = self.run_bridge("review", "-o", str(md))
        self.assertEqual(code, 0, out)
        self.assertIn("- 孫引き: yamada2002", md.read_text(encoding="utf-8"))
        html = self.dir / "review.html"
        code, out = self.run_bridge("review", "--html", "-o", str(html))
        self.assertEqual(code, 0, out)
        self.assertIn("孫引き：yamada2002", html.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
