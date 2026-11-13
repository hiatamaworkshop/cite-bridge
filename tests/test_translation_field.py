# -*- coding: utf-8 -*-
"""抜き書きの任意の欄 訳 と 別の所在（SPEC §2.1、0.6.0）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_translation_field.py
"""
import hashlib
import json
import re
import sys
import unittest

import test_bridge as tb

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge.manuscript import summary_fingerprint  # noqa: E402

TRANSLATION = "参加者は平均 12 秒で課題を終えた。"
ALT_LOCATION = "邦訳 p.45、第3章2節"


def with_field(text, eid, name, value):
    """抜き書き eid の欄（記入の前）に、欄 name を足す。"""
    head = f"## {eid}\n"
    start = text.index(head)
    end = text.index("\n## ", start + 1) if "\n## " in text[start + 1:] else len(text)
    block = text[start:end]
    line = "記入: test\n"
    assert block.count(line) == 1
    return text[:start] + block.replace(line, f"{name}: {value}\n{line}") + text[end:]


class TranslationFieldTest(unittest.TestCase):
    setUp = tb.BridgeTest.setUp
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def set_excerpts(self, text):
        self.write("bridge/excerpts/doe2020.md", text)

    def excerpt_text(self):
        return self.read("bridge/excerpts/doe2020.md")

    def derived(self, eid="e1"):
        """抜き書き eid の導く欄（@ 行）のうち、記録の欄でないもの。"""
        text = self.excerpt_text()
        start = text.index(f"## {eid}\n")
        end = text.index("\n## ", start + 1) if "\n## " in text[start + 1:] else len(text)
        return [ln for ln in text[start:end].splitlines() if ln.startswith("@") and "時の指紋" not in ln]

    # ---- 指紋（SPEC §4）

    def test_fingerprint_is_unchanged_without_the_fields(self):
        fields = {"逐語": "a b", "強さ": "観察", "要約": "要約。", "言っていないこと": "なし。"}
        s = "\n".join(re.sub(r"\s", "", fields[n]) for n in ("逐語", "強さ", "要約", "言っていないこと"))
        self.assertEqual(summary_fingerprint(fields), hashlib.sha1(s.encode("utf-8")).hexdigest()[:8])
        self.assertEqual(summary_fingerprint({**fields, "訳": ""}), summary_fingerprint(fields))

    def test_translation_enters_the_fingerprint_and_alternate_location_does_not(self):
        fields = {"逐語": "a", "強さ": "観察", "要約": "要約。", "言っていないこと": "なし。"}
        base = summary_fingerprint(fields)
        with_tr = summary_fingerprint({**fields, "訳": "訳 文。"})
        self.assertNotEqual(with_tr, base)
        self.assertEqual(with_tr, summary_fingerprint({**fields, "訳": "訳文。"}))  # 空白は除く
        self.assertEqual(summary_fingerprint({**fields, "別の所在": ALT_LOCATION}), base)
        # 孫引きと訳の両方があれば、孫引き、訳の順に足す
        s = "a\n観察\n要約。\nなし。\n孫引き\t山田（1996）\n訳\t訳文。"
        self.assertEqual(summary_fingerprint({**fields, "訳": "訳文。", "孫引き": "山田（1996）"}),
                         hashlib.sha1(s.encode("utf-8")).hexdigest()[:8])

    def test_aliases_read_the_same_fields(self):
        from cite_bridge.blocks import parse_blocks
        text = (tb.EXCERPTS.replace("記入: test\n", f"translation: {TRANSLATION}\nalternate_location: {ALT_LOCATION}\n記入: test\n", 1))
        self.set_excerpts(text)
        _, blocks = parse_blocks(self.dir / "bridge/excerpts/doe2020.md")
        f = blocks[0]["fields"]
        self.assertEqual((f["訳"], f["別の所在"]), (TRANSLATION, ALT_LOCATION))

    # ---- 照合と検査

    def test_matching_uses_the_verbatim_only(self):
        """訳と別の所在は照合に使わない。足しても、導く欄（照合・所在・前後の文）は変わらない。"""
        self.assertEqual(self.run_bridge("derive")[0], 0)
        before = self.derived()
        self.assertIn("@照合: 一致", before)
        # 訳は抽出テキストに無い字、別の所在は導く所在と違う頁
        text = with_field(self.excerpt_text(), "e1", "訳", TRANSLATION)
        self.set_excerpts(with_field(text, "e1", "別の所在", ALT_LOCATION))
        self.assertEqual(self.run_bridge("derive")[0], 0)
        self.assertEqual(self.derived(), before)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertNotIn("ERROR", out)

    def test_existing_files_keep_their_states(self):
        """欄の無い一式は、承認と要約の確認の状態が変わらない。別の所在を足しても変わらない。"""
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--by", "tester")[0], 0)
        out = self.run_bridge("check")[1]
        self.assertIn("承認済 1", out)
        self.assertNotIn("確認し直す", out)
        self.set_excerpts(with_field(self.excerpt_text(), "e1", "別の所在", ALT_LOCATION))
        out = self.run_bridge("check")[1]
        self.assertIn("承認済 1", out)
        self.assertNotIn("確認し直す", out)

    def test_adding_or_editing_translation_sends_summary_check_back(self):
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--by", "tester")[0], 0)
        self.set_excerpts(with_field(self.excerpt_text(), "e1", "訳", TRANSLATION))
        out = self.run_bridge("check")[1]
        self.assertIn("要約の確認の後に欄が変わった。確認し直す", out)
        self.assertIn("承認済 1", out)  # 引用の承認は、根拠の指紋（ID と逐語）に依るので変わらない
        # 訳つきで確かめ直すと消え、訳を直すとまた出る
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--by", "tester")[0], 0)
        self.assertNotIn("確認し直す", self.run_bridge("check")[1])
        self.set_excerpts(self.excerpt_text().replace(TRANSLATION, "参加者は必ず 12 秒で課題を終えた。"))
        self.assertIn("確認し直す", self.run_bridge("check")[1])

    # ---- review

    def test_review_shows_both_fields(self):
        text = with_field(self.excerpt_text(), "e1", "訳", TRANSLATION)
        self.set_excerpts(with_field(text, "e1", "別の所在", ALT_LOCATION))
        self.run_bridge("derive")
        ev = json.loads(self.run_bridge("review", "--json", "--all")[1])["citations"][0]["evidence"][0]
        self.assertEqual((ev["translation"], ev["alternate_location"]), (TRANSLATION, ALT_LOCATION))
        md = self.dir / "review.md"
        self.assertEqual(self.run_bridge("review", "-o", str(md))[0], 0)
        shown = md.read_text(encoding="utf-8")
        self.assertIn(f"- 別の所在: {ALT_LOCATION}", shown)
        self.assertIn(f"- 訳（引用者。照合しない）: {TRANSLATION}", shown)
        html = self.dir / "review.html"
        self.assertEqual(self.run_bridge("review", "--html", "-o", str(html))[0], 0)
        page = html.read_text(encoding="utf-8")
        self.assertIn(f"別の所在：{ALT_LOCATION}", page)
        self.assertIn(f'<span class="k">訳（引用者）</span>{TRANSLATION}', page)

    def test_review_is_unchanged_without_the_fields(self):
        self.run_bridge("derive")
        ev = json.loads(self.run_bridge("review", "--json", "--all")[1])["citations"][0]["evidence"][0]
        self.assertEqual((ev["translation"], ev["alternate_location"]), ("", ""))
        md = self.dir / "review.md"
        self.assertEqual(self.run_bridge("review", "-o", str(md))[0], 0)
        shown = md.read_text(encoding="utf-8")
        self.assertNotIn("別の所在", shown)
        self.assertNotIn("訳（引用者", shown)


if __name__ == "__main__":
    unittest.main()
