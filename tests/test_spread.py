# -*- coding: utf-8 -*-
"""一つの原本から引いた箇所の広がり（spread、C51）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_spread.py
"""
import unittest

import test_bridge as tb

WEB_TEXT = "<!-- snapshot\nurl: https://acme.example/docs\nretrieved: 2026-01-01\ntype: html\n-->\nSay \"Show labels\".\n"


def excerpt(key, *verbatims):
    blocks = "".join(f"\n## e{i}\n逐語: {v}\n強さ: 観察\n要約: 要約。\n言っていないこと: なし。\n記入: test\n"
                     for i, v in enumerate(verbatims, 1))
    return f"# {key}\n{blocks}"


class SpreadTest(unittest.TestCase):
    setUp = tb.BridgeTest.setUp
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def write(self, name, text):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def spread(self):
        code, out = self.run_bridge("spread")
        self.assertEqual(code, 0, out)
        return out

    def test_counts_pages_and_sections_of_one_source(self):
        """抜き書き三つ（2頁目に二つ、3頁目に一つ）。引用が根拠にしているのは e1 だけ。"""
        out = self.spread()
        self.assertIn("doe2020  抜き書き 3（引用に使う 1）", out)
        self.assertIn("  頁: 全 3 頁のうち 2 頁  p.2（PDF 2頁目） 2 / p.3（PDF 3頁目） 1", out)
        self.assertIn("  節: §3 Results 1 / §2.1 Prior Systems 1 / §4 Discussion 1", out)
        self.assertNotIn("所在なし ", out.split("---")[0])
        self.assertIn("--- 文献 1、抜き書き 3（引用に使う 1）、所在なし 0", out)

    def test_does_not_write_files(self):
        """derive の前でも後でも、抜き書きのファイルを書き換えない（導く欄は読むたびに導く）。"""
        before = self.read("bridge/excerpts/doe2020.md")
        first = self.spread()
        self.assertEqual(self.read("bridge/excerpts/doe2020.md"), before)
        self.run_bridge("derive")
        derived = self.read("bridge/excerpts/doe2020.md")
        self.assertEqual(self.spread(), first)
        self.assertEqual(self.read("bridge/excerpts/doe2020.md"), derived)

    def test_web_snapshot_has_sections_only(self):
        self.write("refs/_web/acme_docs.txt", WEB_TEXT)
        self.write("bridge/excerpts/acme_docs.md", excerpt("acme_docs", 'Say "Show labels".'))
        out = self.spread()
        block = out.split("acme_docs  ")[1].split("\n\n")[0]
        self.assertTrue(block.startswith("抜き書き 1（引用に使う 0）"), out)
        self.assertIn("  頁: 頁が無い（Web 写し）", block)
        self.assertIn("  節: 見出しなし 1", block)
        self.assertIn("--- 文献 2、抜き書き 4（引用に使う 1）、所在なし 0", out)

    def test_unlocated_excerpts_are_counted_with_reason(self):
        """抽出の無い文献と、逐語が見つからない抜き書きは、所在なしとして数と理由を出す。"""
        (self.dir / "refs/_txt/yamada2002.txt").unlink()
        self.write("bridge/excerpts/yamada2002.md", excerpt("yamada2002", "音声は不利なメデイアである．"))
        self.write("bridge/excerpts/doe2020.md",
                   tb.EXCERPTS + "\n## e4\n逐語: This sentence is nowhere in the paper at all.\n強さ: 観察\n要約: 要約。\n"
                                 "言っていないこと: なし。\n記入: test\n")
        out = self.spread()
        doe = out.split("doe2020  ")[1].split("\n\n")[0]
        self.assertTrue(doe.startswith("抜き書き 4（引用に使う 1）"), out)
        self.assertIn("  頁: 全 3 頁のうち 2 頁", doe)  # 所在のあるものは、そのまま数える
        self.assertIn("  所在なし 1: e4 不一致", doe)
        yamada = out.split("yamada2002  ")[1].split("\n\n")[0]
        self.assertNotIn("  頁:", yamada)
        self.assertNotIn("  節:", yamada)
        self.assertIn("  所在なし 1: e1 照合不能（", yamada)
        self.assertIn("--- 文献 2、抜き書き 5（引用に使う 1）、所在なし 2", out)


if __name__ == "__main__":
    unittest.main()
