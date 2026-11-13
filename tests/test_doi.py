# -*- coding: utf-8 -*-
"""DOI を書誌から拾い、check・grade・公開物で見せる（C57、0.8.1）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_doi.py
"""
import json
import sys
import unittest

import test_bridge as tb
from test_publish import APPROVERS, PUBLICATION

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge.bib import _entry_text, doi_of  # noqa: E402

DOE_LINE = "Doe, J. (2020). A study of things. *Journal of Things*, 1(1), 1–3."


class DoiOfTest(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(doi_of("Doe (2020). Title. https://doi.org/10.1234/AbC.567"), "10.1234/abc.567")  # 小文字にそろえる
        self.assertEqual(doi_of("Doe (2020). Title. doi:10.1234/abc-5(6)."), "10.1234/abc-5")  # 括弧の手前で切る
        self.assertEqual(doi_of("Doe (2020). Title. DOI 10.48550/arXiv.2111.01690。"), "10.48550/arxiv.2111.01690")
        self.assertEqual(doi_of("Doe (2020). Title（https://dx.doi.org/10.1000/xyz）"), "10.1000/xyz")
        self.assertEqual(doi_of("Doe (2020). Title. https://doi.org/10.1234/abc, pp. 1–3."), "10.1234/abc")

    def test_none(self):
        self.assertIsNone(doi_of("Doe, J. (2020). A study. Journal, 10(2), 10.5–11."))  # 巻号と頁は DOI でない
        self.assertIsNone(doi_of("Acme. (2026). Docs. https://acme.example/docs"))
        self.assertIsNone(doi_of(""))
        self.assertIsNone(doi_of(None))

    def test_adapters_put_the_doi_field_into_the_entry(self):
        """BibTeX と CSL-JSON のアダプタは、doi の欄を書誌の文に入れる。そこから同じ関数で拾える。"""
        self.assertEqual(doi_of(_entry_text(["Doe"], 2020, "T", "J", "10.1234/ABC", None)), "10.1234/abc")


class DoiCommandsTest(unittest.TestCase):
    setUp = tb.BridgeTest.setUp
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def add_doi(self, text=" https://doi.org/10.1234/JT.2020.001"):
        self.assertEqual(self.read("bib.md").count(DOE_LINE), 1)
        self.write("bib.md", self.read("bib.md").replace(DOE_LINE, DOE_LINE + text))

    def test_check_reports_sources_without_a_doi_as_info(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        line = next(ln for ln in out.splitlines() if "DOI:" in ln)
        self.assertEqual(line, "INFO  DOI: 抜き書きのある文献 1 件のうち、書誌に DOI があるもの 0、無いもの 1（doe2020）")
        strict_before = self.run_bridge("check", "--strict")[1].count("NOTE")
        self.add_doi()
        self.run_bridge("derive")
        out = self.run_bridge("check")[1]
        self.assertIn("INFO  DOI: 抜き書きのある文献 1 件のうち、書誌に DOI があるもの 1", out)
        self.assertNotIn("無いもの", next(ln for ln in out.splitlines() if "DOI:" in ln))
        self.assertEqual(out.count("NOTE"), strict_before)  # DOI の有無は確認待ちにしない

    def test_doi_in_the_bibliography_does_not_change_the_location(self):
        """書誌の行に DOI を足しても、頁の範囲（行末の 1–3）の読み方と所在が変わらない書き方がある。"""
        self.run_bridge("derive")
        before = self.read("bridge/excerpts/doe2020.md")
        self.add_doi()
        self.run_bridge("derive")
        self.assertEqual(self.read("bridge/excerpts/doe2020.md"), before)

    def test_grade_counts(self):
        out = self.run_bridge("grade")[1]
        self.assertIn("DOI: 書誌に DOI があるもの 0 件、無いもの 3 件", out)
        self.add_doi()
        self.assertIn("DOI: 書誌に DOI があるもの 1 件、無いもの 2 件", self.run_bridge("grade")[1])

    def test_publication_has_the_normalized_doi_and_no_doi_url(self):
        self.write("bridge/bridge.toml", tb.CONFIG + APPROVERS + PUBLICATION)
        self.add_doi()
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--by", "tester")[0], 0)
        code, out = self.run_bridge("checkpoint", "--by", "tester")
        self.assertEqual(code, 0, out)
        code, out = self.run_bridge("publish", "-o", "pub")
        self.assertEqual(code, 0, out)
        src = json.loads(self.read("pub/publication.json"))["content"]["sources"][0]
        self.assertEqual((src["doi"], src["url"]), ("10.1234/jt.2020.001", None))
        self.assertIn("DOI: 文献 1 件のうち、書誌に DOI があるもの 1", out)

    def test_publish_reports_sources_without_a_doi(self):
        self.write("bridge/bridge.toml", tb.CONFIG + APPROVERS + PUBLICATION)
        self.run_bridge("derive")
        self.run_bridge("approve", "c001", "--by", "tester")
        self.run_bridge("confirm", "doe2020#e1", "--by", "tester")
        self.assertEqual(self.run_bridge("checkpoint", "--by", "tester")[0], 0)
        code, out = self.run_bridge("publish", "-o", "pub")
        self.assertEqual(code, 0, out)
        self.assertIn("無いもの 1（doe2020）", out)
        self.assertIsNone(json.loads(self.read("pub/publication.json"))["content"]["sources"][0]["doi"])


if __name__ == "__main__":
    unittest.main()
