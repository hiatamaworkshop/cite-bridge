# -*- coding: utf-8 -*-
"""出典ごとの網羅（設計 §8.1・§8.2 の 2）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_coverage.py
"""
import hashlib
import json
import sys
import unittest
from unittest import mock

import test_bridge as tb

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge import manuscript  # noqa: E402
from cite_bridge.manuscript import coverage_items, fingerprint, mark_keys  # noqa: E402

BIB = {
    "doe2020": {"entry": "Doe, J. (2020). A study of things. *Journal of Things*, 1(1), 1–3.", "pdfs": [], "accessed": None},
    "smith2010": {"entry": "Smith, J. (2010). Grids and lists.", "pdfs": [], "accessed": None},
}


def ident(sentence, paren, nth=0, part=None):
    """ID の式（§8.1 の 4）。一件の括弧は part を含めず、出典ごとの件は含める。"""
    s = f"{fingerprint(sentence)}\t{paren}\t{nth}" + ("" if part is None else f"\t{part}")
    return "q" + hashlib.sha1(s.encode("utf-8")).hexdigest()[:7]


class CoverageItemsTest(unittest.TestCase):
    """設定を読まない既定の正規表現で、coverage_items を直接試す。"""

    def items(self, text, bib=None, keys=None):
        return coverage_items(text, bib, keys)

    def test_split_sources_and_repeats(self):
        text = "一文目は二つの出典（Doe, 2020; Smith, 2010）を並べる。二文目は一つだけ（Doe, 2020; §2.2）。三文目は頁だけ（p.49）と同書（同書 p.269）である。四文目は（同一性と内容の分離）。"
        items = self.items(text)
        got = [(c["source"], c["part"], c["kind"]) for c in items]
        self.assertEqual(got, [
            ("Doe, 2020", 0, "cite"), ("Smith, 2010", 1, "cite"),  # 二つの出典は出典ごと
            ("Doe, 2020; §2.2", None, "cite"),                      # §2.2 は出典でない。一つだけなら括弧で一件
            ("p.49", None, "repeat"), ("同書 p.269", None, "repeat"),  # 頁だけ・同書の括弧は repeat の件
        ])                                                          # 「同一性と内容の分離」は数えない
        self.assertEqual([c["nparts"] for c in items], [2, 2, None, None, None])

    def test_ids_of_single_and_per_source_items(self):
        text = "一文目は二つの出典（Doe, 2020; Smith, 2010）を並べる。二文目は一つだけ（Doe, 2020）。"
        first, second, single = self.items(text)
        sent = "一文目は二つの出典（Doe, 2020; Smith, 2010）を並べる。"
        self.assertEqual(first["item"], ident(sent, "（Doe, 2020; Smith, 2010）", 0, 0))
        self.assertEqual(second["item"], ident(sent, "（Doe, 2020; Smith, 2010）", 0, 1))
        self.assertEqual(single["item"], ident("二文目は一つだけ（Doe, 2020）。", "（Doe, 2020）", 0))  # 一件の括弧の ID は今の式

    def test_direct_mark_goes_to_the_first_source_only(self):
        # 印を持たない（書誌を渡さない）ときは、括弧の直後の印を前の出典が使い、後の出典は印が無い
        items = self.items("二つの出典（Doe, 2020; Smith, 2010）〔c001〕を並べる。")
        self.assertEqual([c["marked"] for c in items], [True, False])

    def test_spare_mark_goes_to_the_first_unmarked(self):
        items = self.items("（Doe, 2020）、（Smith, 2010）、〔c001〕を述べる。")
        self.assertEqual([c["marked"] for c in items], [True, False])

    def test_key_match_marks_the_source_it_names(self):
        text = "二つの出典（Doe, 2020; Smith, 2010）〔c001〕を並べる。"
        items = self.items(text, BIB, {"c001": {"smith2010"}})
        self.assertEqual([c["marked"] for c in items], [False, True])  # 印の key が二つ目の出典なら、一つ目は印の無いもの

    def test_one_mark_with_two_sources_covers_both(self):
        text = "二つの文献に基づく主張（Doe, 2020; Smith, 2010）〔c001〕である。"
        items = self.items(text, BIB, {"c001": {"doe2020", "smith2010"}})
        self.assertEqual([c["marked"] for c in items], [True, True])  # 主張の根拠が二つの文献なら、二つの出典を受け持つ

    def test_mark_keys_from_blocks(self):
        blocks = [{"id": "c001", "fields": {"種類": "主張", "抜き書き": "doe2020#e1, smith2010#e2"}},
                  {"id": "c002", "fields": {"種類": "指示", "文献": "smith2010"}},
                  {"id": "c003", "fields": {"種類": "主張", "抜き書き": "e1"}}]
        self.assertEqual(mark_keys(blocks), {"c001": {"doe2020", "smith2010"}, "c002": {"smith2010"}, "c003": set()})

    def test_excluded_record_without_part_still_matches_a_single_paren(self):
        # 設計 §8.1 の 7 より前の記録（part が無い）は part を None とみなす
        text = "一文の（Doe, 2020）。"
        rec = {"fingerprint": fingerprint("一文の（Doe, 2020）。"), "paren": "（Doe, 2020）", "nth": 0}
        with mock.patch.object(manuscript, "load_excluded", return_value=[rec]):
            self.assertEqual([c["excluded"] for c in self.items(text)], [True])

    def test_excluded_record_matches_the_part(self):
        text = "二つの出典（Doe, 2020; Smith, 2010）を並べる。"
        rec = {"fingerprint": fingerprint(text), "paren": "（Doe, 2020; Smith, 2010）", "nth": 0, "part": 1}
        with mock.patch.object(manuscript, "load_excluded", return_value=[rec]):
            self.assertEqual([c["excluded"] for c in self.items(text)], [False, True])


class CoverageCliTest(unittest.TestCase):
    # 試験の一式の作り方と実行の補助だけを tb から借りる（tb.BridgeTest を継ぐと、その試験も重ねて走るため）
    setUp = tb.BridgeTest.setUp
    tearDown = tb.BridgeTest.tearDown
    clean_env = staticmethod(tb.BridgeTest.clean_env)
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write

    def _manuscript(self, extra):
        self.write("manuscript.md", self.read("manuscript.md") + extra)
        self.run_bridge("derive")

    def test_coverage_lists_each_source_and_repeat(self):
        self._manuscript("\n二つの出典（Doe, 2020; Smith, 2010）を並べ、頁だけ（p.49）を続ける。\n")
        code, out = self.run_bridge("coverage")
        self.assertEqual(code, 0, out)
        self.assertIn("manuscript.md:7  Doe, 2020（括弧 （Doe, 2020; Smith, 2010） の出典 1/2）", out)
        self.assertIn("manuscript.md:7  Smith, 2010（括弧 （Doe, 2020; Smith, 2010） の出典 2/2）", out)
        self.assertIn("manuscript.md:7  （p.49）  （", out)
        self.assertIn("--- 出典らしきもの 4（括弧 3）、印のある文 1、印の無い文 3", out)
        self.assertIn("網羅: 原稿の出典らしきもの 4（括弧 3）のうち、印のあるもの 1、印の無いもの 3", self.run_bridge("check")[1])

    def test_manifest_counts_parens(self):
        self._manuscript("\n二つの出典（Doe, 2020; Smith, 2010）を並べる。\n")
        self.run_bridge("approve", "c001", "--by", "tester")  # 未承認が残っていると checkpoint は書かない
        code, out = self.run_bridge("checkpoint", "--label", "test")
        self.assertEqual(code, 0, out)
        cov = json.loads(next((self.dir / "bridge/checkpoints").glob("*.json")).read_text(encoding="utf-8"))["coverage"]
        self.assertEqual((cov["spans"], cov["parens"]), (3, 2))

    def test_excluded_part_is_not_listed(self):
        self._manuscript("\n二つの出典（Doe, 2020; Smith, 2010）を並べる。\n")
        sent = "二つの出典（Doe, 2020; Smith, 2010）を並べる。"
        self.write("bridge/excluded.json", json.dumps([{"item": "x", "paren": "（Doe, 2020; Smith, 2010）", "nth": 0,
                                                        "part": 1, "fingerprint": fingerprint(sent)}]))
        out = self.run_bridge("coverage")[1]
        self.assertIn("Doe, 2020（括弧", out)
        self.assertNotIn("Smith, 2010（括弧", out)
        self.assertIn("引用でないと判断したもの 1", self.run_bridge("check")[1])

    def test_checkable_leaves_out_repeats(self):
        self._manuscript("\n山田（2002）は、音声は状態理解の容易性に関して不利なメディアであると述べた。\n同じ箇所（同書 p.269）。\n")
        code, out = self.run_bridge("propose")
        self.assertEqual(code, 0, out)
        self.assertIn("（同書 p.269）", [w["paren"] for w in json.loads(self.read("bridge/candidates/work.json"))["items"]])
        code, out = self.run_bridge("propose", "--checkable")
        self.assertEqual(code, 0, out)
        self.assertEqual([w["paren"] for w in json.loads(self.read("bridge/candidates/work.json"))["items"]], ["（2002）"])


if __name__ == "__main__":
    unittest.main()
