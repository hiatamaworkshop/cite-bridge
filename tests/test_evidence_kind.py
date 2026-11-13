# -*- coding: utf-8 -*-
"""抜き書きの任意の欄 根拠の種類（SPEC §2.1・§2.2、0.7.0）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_evidence_kind.py
"""
import json
import sys
import unittest

import test_bridge as tb
from test_translation_field import with_field

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge.manuscript import summary_fingerprint  # noqa: E402

FIELDS = {"逐語": "a", "強さ": "観察", "要約": "要約。", "言っていないこと": "なし。"}


class EvidenceKindTest(unittest.TestCase):
    setUp = tb.BridgeTest.setUp
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def set_kind(self, value, eid="e1", name="根拠の種類"):
        self.write("bridge/excerpts/doe2020.md", with_field(self.read("bridge/excerpts/doe2020.md"), eid, name, value))

    def block(self, eid="e1"):
        text = self.read("bridge/excerpts/doe2020.md")
        start = text.index(f"## {eid}\n")
        end = text.index("\n## ", start + 1) if "\n## " in text[start + 1:] else len(text)
        return text[start:end]

    def evidence(self):
        return json.loads(self.run_bridge("review", "--json", "--all")[1])["citations"][0]["evidence"][0]

    # ---- 指紋（SPEC §4）

    def test_omitted_and_text_have_the_same_fingerprint(self):
        base = summary_fingerprint(FIELDS)
        self.assertEqual(summary_fingerprint({**FIELDS, "根拠の種類": ""}), base)
        self.assertEqual(summary_fingerprint({**FIELDS, "根拠の種類": "文"}), base)
        self.assertNotEqual(summary_fingerprint({**FIELDS, "根拠の種類": "表"}), base)
        self.assertNotEqual(summary_fingerprint({**FIELDS, "根拠の種類": "表"}), summary_fingerprint({**FIELDS, "根拠の種類": "図"}))

    def test_aliases_read_the_same_field_and_values(self):
        from cite_bridge.blocks import parse_blocks
        self.set_kind("table", name="evidence_kind")
        _, blocks = parse_blocks(self.dir / "bridge/excerpts/doe2020.md")
        self.assertEqual(blocks[0]["fields"]["根拠の種類"], "表")

    # ---- 要ヒューマンチェック（SPEC §2.2）

    def test_text_excerpts_are_unchanged(self):
        """欄の無い抜き書きと、文と書いた抜き書きは、導く欄も check も今までと変わらない。"""
        self.run_bridge("derive")
        before_block, before_check = self.block(), self.run_bridge("check")[1]
        self.assertNotIn("要ヒューマンチェック", before_block)
        self.assertNotIn("根拠の種類", before_check)
        self.set_kind("文")
        self.assertEqual(self.run_bridge("derive")[0], 0)
        self.assertEqual(self.block().replace("根拠の種類: 文\n", ""), before_block)
        # 欄を一行足したので、後ろの抜き書きの行番号だけが一つずれる
        self.assertEqual(self.run_bridge("check")[1], before_check.replace("doe2020.md:17 ", "doe2020.md:18 "))
        self.assertEqual(self.evidence()["evidence_kind"], "文")

    def test_non_text_needs_a_human_check_even_when_the_match_is_exact(self):
        self.set_kind("表")
        self.assertEqual(self.run_bridge("derive")[0], 0)
        block = self.block()
        self.assertIn("@照合: 一致", block)
        self.assertIn("@要ヒューマンチェック: 文でない根拠（表）", block)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)  # ERROR は増やさない
        self.assertNotIn("ERROR", out)
        self.assertIn("doe2020#e1: 要ヒューマンチェック（文でない根拠（表））", out)
        self.assertIn("根拠 doe2020#e1 は要ヒューマンチェック（文でない根拠（表））で、原本での確認が無い", out)
        self.assertIn("抜き書きの根拠の種類: 文 2 / 表 1", out)
        self.assertNotEqual(self.run_bridge("check", "--strict")[0], 0)  # 原本での確認が無い間は止まる

    def test_source_check_clears_it_and_the_mark_stays(self):
        self.set_kind("グラフ")
        self.run_bridge("derive")
        code, out = self.run_bridge("confirm", "doe2020#e1", "--source", "--by", "tester", "--page", "p.2 図1")
        self.assertEqual(code, 0, out)
        out = self.run_bridge("check")[1]
        self.assertNotIn("doe2020#e1: 要ヒューマンチェック", out)
        self.assertIn("印のある抜き書き 1 件のうち、確認済 1", out)
        self.assertIn("@要ヒューマンチェック: 文でない根拠（グラフ）", self.block())  # 印は記録に依らず残る

    def test_other_reasons_are_kept(self):
        """ほかの理由（逐語が短い）と並ぶ。"""
        short = "\n## e4\n逐語: grids over lists\n強さ: 観察\n要約: 格子。\n言っていないこと: なし。\n根拠の種類: 図\n記入: test\n"
        self.write("bridge/excerpts/doe2020.md", tb.EXCERPTS + short)
        self.run_bridge("derive")
        self.assertIn("@要ヒューマンチェック: 逐語が短い、文でない根拠（図）", self.block("e4"))

    def test_value_outside_the_vocabulary_is_a_note(self):
        self.set_kind("動画")
        self.assertEqual(self.run_bridge("derive")[0], 0)
        self.assertNotIn("要ヒューマンチェック", self.block())  # 文でない根拠としては扱わない
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertNotIn("ERROR", out)
        line = next(ln for ln in out.splitlines() if "根拠の種類 '動画'" in ln)
        self.assertTrue(line.startswith("NOTE"), line)
        self.assertIn("文 / 表 / グラフ / 図", line)
        self.assertNotEqual(self.run_bridge("check", "--strict")[0], 0)

    def test_states_are_unchanged_until_a_kind_is_written(self):
        """欄の無い一式の承認と確認の状態は変わらない。文でない種類を書くと、要約の確認が確認し直すに戻る。"""
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--by", "tester")[0], 0)
        out = self.run_bridge("check")[1]
        self.assertIn("承認済 1", out)
        self.assertNotIn("確認し直す", out)
        self.assertEqual(self.run_bridge("check", "--strict")[0], 0)
        self.set_kind("表")
        self.run_bridge("derive")
        out = self.run_bridge("check")[1]
        self.assertIn("要約の確認の後に欄が変わった。確認し直す", out)
        self.assertIn("承認済 1", out)  # 引用の承認は、根拠の指紋（ID と逐語）に依る

    # ---- review と、原本での確認の依頼（SPEC §5.1）

    def test_review_and_request_show_the_kind(self):
        self.set_kind("表")
        self.run_bridge("derive")
        self.assertEqual(self.evidence()["evidence_kind"], "表")
        md = self.dir / "review.md"
        self.assertEqual(self.run_bridge("review", "-o", str(md))[0], 0)
        self.assertIn("- 根拠の種類: 表（文でない根拠。", md.read_text(encoding="utf-8"))
        html = self.dir / "review.html"
        self.assertEqual(self.run_bridge("review", "--html", "-o", str(html))[0], 0)
        self.assertIn("根拠の種類：表（文でない根拠。", html.read_text(encoding="utf-8"))
        code, out = self.run_bridge("review", "--source-checks", "--json", "-o", "req.json")
        self.assertEqual(code, 0, out)
        items = {it["id"]: it for it in json.loads(self.read("req.json"))["items"]}
        self.assertEqual((items["doe2020#e1"]["evidence_kind"], items["doe2020#e1"]["reasons"]), ("表", "文でない根拠（表）"))
        self.assertEqual(self.run_bridge("review", "--source-checks", "-o", "req.md")[0], 0)
        self.assertIn("- 根拠の種類: 表", self.read("req.md"))

    def test_review_does_not_show_the_kind_for_text(self):
        self.run_bridge("derive")
        md = self.dir / "review.md"
        self.assertEqual(self.run_bridge("review", "-o", str(md))[0], 0)
        self.assertNotIn("根拠の種類", md.read_text(encoding="utf-8"))
        html = self.dir / "review.html"
        self.assertEqual(self.run_bridge("review", "--html", "-o", str(html))[0], 0)
        self.assertNotIn("根拠の種類：", html.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
