# -*- coding: utf-8 -*-
"""不在の抜き書き（逐語の代わりに探した語を持つ。SPEC §2.1、0.10.0、C50）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_absence.py
"""
import hashlib
import json
import re
import sys
import unittest

import test_bridge as tb
import test_publish as tp

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge.manuscript import evidence_hash, summary_fingerprint  # noqa: E402

SUMMARY = "応答の遅延には触れていない。"
NO_HIT = "latency、遅延、レイテンシ"
HIT = "noise、雑音"  # 試験の原典の 3 頁目（§4 Discussion）に noise が一度ある


def absence(eid, terms, writer="test"):
    return f"\n## {eid}\n探した語: {terms}\n要約: {SUMMARY}\n記入: {writer}\n"


def sha1_8(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


class AbsenceTest(unittest.TestCase):
    setUp = tb.BridgeTest.setUp
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def add(self, terms, eid="e4"):
        self.write("bridge/excerpts/doe2020.md", tb.EXCERPTS + absence(eid, terms))

    def block(self, eid="e4", name="bridge/excerpts/doe2020.md"):
        text = self.read(name)
        start = text.index(f"## {eid}\n")
        end = text.index("\n## ", start + 1) if "\n## " in text[start + 1:] else len(text)
        return text[start:end]

    def cite_absence(self):
        """c001 の根拠に、不在の抜き書き e4 を足す。"""
        self.write("bridge/citations.md", self.read("bridge/citations.md").replace("抜き書き: doe2020#e1", "抜き書き: doe2020#e1, doe2020#e4"))

    # ---- 指紋（SPEC §4）

    def test_fingerprints_use_searched_terms_in_place_of_verbatim(self):
        f = {"探した語": "latency、 遅延", "要約": "要約。", "記入": "test"}
        self.assertEqual(summary_fingerprint(f), sha1_8("latency、遅延\n\n要約。\n"))
        self.assertEqual(evidence_hash(["k#e1"], {"k#e1": f}), sha1_8("k#e1\tlatency、遅延"))
        # 逐語のある抜き書きは変わらない。両方があれば逐語を使う
        g = {"逐語": "a b", "強さ": "観察", "要約": "要約。", "言っていないこと": "なし。"}
        self.assertEqual(summary_fingerprint(g), sha1_8("ab\n観察\n要約。\nなし。"))
        self.assertEqual(summary_fingerprint({**g, "探した語": "x"}), summary_fingerprint(g))
        self.assertEqual(evidence_hash(["k#e1"], {"k#e1": {**g, "探した語": "x"}}), sha1_8("k#e1\tab"))

    # ---- 導く欄と check

    def test_no_hits_is_machine_checked(self):
        self.add(NO_HIT)
        self.assertEqual(self.run_bridge("derive")[0], 0)
        b = self.block()
        self.assertIn("@照合: 当たりなし\n", b + "\n")
        for name in ("@当たり", "@要ヒューマンチェック", "@所在", "@節の種類", "@前", "@後"):
            self.assertNotIn(name, b)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertNotIn("ERROR", out)  # 逐語・強さ・言っていないことが無くても、必須の欄の ERROR は出ない
        self.assertNotIn("doe2020#e4: 要ヒューマンチェック", out)
        self.assertIn("INFO  不在の抜き書き: 1 件（当たりなし 1）", out)

    def test_plain_set_is_unchanged(self):
        """不在の抜き書きの無い一式では、不在の行を出さない。"""
        self.run_bridge("derive")
        out = self.run_bridge("check")[1]
        self.assertNotIn("不在の抜き書き", out)
        self.assertNotIn("当たり", self.read("bridge/excerpts/doe2020.md"))

    def test_hits_need_a_human_check_and_a_source_check_clears_it(self):
        self.add(HIT)
        self.run_bridge("derive")
        b = self.block()
        self.assertIn("@照合: 当たりあり（noise 1）", b)
        self.assertIn("@当たり: noise：p.3（PDF 3頁目） / §4 Discussion", b)
        self.assertIn("@要ヒューマンチェック: 探した語に当たりがある", b)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)  # ERROR は増やさない
        self.assertIn("doe2020#e4: 要ヒューマンチェック（探した語に当たりがある）。原本での確認が無い", out)
        self.assertIn("INFO  不在の抜き書き: 1 件（当たりあり 1）", out)
        self.assertNotEqual(self.run_bridge("check", "--strict")[0], 0)
        # 原本で確かめた記録で消える。指紋は探した語から作る
        code, out = self.run_bridge("confirm", "doe2020#e4", "--source", "--by", "tester", "--note", "別の意味の noise")
        self.assertEqual(code, 0, out)
        self.assertIn(f"@原本での確認時の指紋: {sha1_8(re.sub(r'\\s', '', HIT))}", self.block())
        self.assertNotIn("doe2020#e4: 要ヒューマンチェック", self.run_bridge("check")[1])
        # 探した語を直すと、記録は有効でなくなる
        text = self.read("bridge/excerpts/doe2020.md")
        self.write("bridge/excerpts/doe2020.md", text.replace(f"探した語: {HIT}", "探した語: noise"))
        self.run_bridge("derive")
        self.assertIn("doe2020#e4: 要ヒューマンチェック（探した語に当たりがある）。確かめた後に探した語が変わった", self.run_bridge("check")[1])

    def test_many_hits_show_the_first_three(self):
        self.add("grids、latency")  # 2 頁目に 2 回、3 頁目に本文で 1 回と参考文献の題で 1 回。latency は無い
        self.run_bridge("derive")
        b = self.block()
        self.assertIn("@照合: 当たりあり（grids 4）", b)
        self.assertIn("@当たり: grids：p.2（PDF 2頁目） / §2.1 Prior Systems、p.2（PDF 2頁目） / §2.1 Prior Systems、"
                      "p.3（PDF 3頁目） / §4 Discussion（ほか 1）\n", b)

    def test_without_extraction_or_with_ocr_it_cannot_be_machine_checked(self):
        (self.dir / "refs/_txt/yamada2002.txt").unlink()
        self.write("bridge/excerpts/yamada2002.md", "# yamada2002\n" + absence("e1", "雑音"))
        self.write("refs/_txt/doe2020.txt", "<!-- ocr\nengine: test\ndate: 2026-01-01\n-->\n" + tb.PAPER)
        self.add(NO_HIT)
        self.run_bridge("derive")
        y = self.block("e1", "bridge/excerpts/yamada2002.md")
        self.assertRegex(y, r"@照合: 照合不能（.+）")
        self.assertRegex(y, r"@要ヒューマンチェック: 照合不能（.+）")
        b = self.block()
        self.assertIn("@照合: 当たりなし", b)  # OCR の抽出は、当たりが無くても不在を保証しない
        self.assertIn("@要ヒューマンチェック: OCR の抽出", b)
        code, out = self.run_bridge("check")
        self.assertNotIn("yamada2002#e1: 欄", out)
        self.assertIn("yamada2002#e1: 要ヒューマンチェック（照合不能", out)
        self.assertIn("doe2020#e4: 要ヒューマンチェック（OCR の抽出）", out)

    def test_notes_for_both_fields_and_unsearchable_terms(self):
        text = tb.EXCERPTS.replace("強さ: 観察\n要約: 平均12秒", "探した語: latency\n強さ: 観察\n要約: 平均12秒")
        self.write("bridge/excerpts/doe2020.md", text + absence("e4", "latency、——"))
        self.run_bridge("derive")
        self.assertIn("@照合: 一致", self.block("e1"))  # 逐語の抜き書きとして扱う
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("doe2020#e1: 逐語と探した語の両方がある", out)
        self.assertIn("doe2020#e4: 探した語 '——' は文字と数字を含まず、探せない", out)

    def test_required_fields_of_an_absence_excerpt(self):
        self.write("bridge/excerpts/doe2020.md", tb.EXCERPTS + "\n## e4\n探した語: latency\n記入: test\n")
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertNotEqual(code, 0)
        self.assertIn("doe2020#e4: 欄 '要約' が空", out)
        self.assertNotIn("doe2020#e4: 欄 '逐語' が空", out)
        self.assertNotIn("doe2020#e4: 欄 '強さ' が空", out)

    # ---- 承認と確認

    def test_citation_resting_on_absence_is_approved_and_goes_back_when_terms_change(self):
        self.add(NO_HIT)
        self.cite_absence()
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "doe2020#e4", "--by", "tester")[0], 0)
        out = self.run_bridge("check")[1]
        self.assertIn("承認済 1", out)
        self.assertNotIn("確認し直す", out)
        text = self.read("bridge/excerpts/doe2020.md")
        self.write("bridge/excerpts/doe2020.md", text.replace(f"探した語: {NO_HIT}", "探した語: latency"))
        self.run_bridge("derive")
        out = self.run_bridge("check")[1]
        self.assertIn("要再確認 1", out)
        self.assertIn("doe2020#e4: 要約の確認の後に欄が変わった。確認し直す", out)

    # ---- review と依頼

    def test_review_and_request_show_terms_and_hits(self):
        self.add(HIT)
        self.cite_absence()
        self.run_bridge("derive")
        ev = json.loads(self.run_bridge("review", "--json", "--all")[1])["citations"][0]["evidence"]
        self.assertEqual((ev[0]["searched_terms"], ev[0]["hits"]), ("", ""))
        self.assertEqual((ev[1]["searched_terms"], ev[1]["verbatim"]), (HIT, ""))
        self.assertIn("noise：p.3（PDF 3頁目） / §4 Discussion", ev[1]["hits"])
        md = self.dir / "review.md"
        self.assertEqual(self.run_bridge("review", "-o", str(md))[0], 0)
        shown = md.read_text(encoding="utf-8")
        self.assertIn(f"> {HIT}", shown)
        self.assertIn("- 当たり: noise：p.3（PDF 3頁目） / §4 Discussion", shown)
        self.assertIn("- 所在: （不在の抜き書き。所在は無い）", shown)
        html = self.dir / "review.html"
        self.assertEqual(self.run_bridge("review", "--html", "-o", str(html))[0], 0)
        page = html.read_text(encoding="utf-8")
        self.assertIn(f"<blockquote>{HIT}</blockquote>", page)
        self.assertIn("触れていない", page)
        # 依頼
        d = json.loads(self.run_bridge("review", "--source-checks", "--json")[1])
        it = {x["id"]: x for x in d["items"]}["doe2020#e4"]
        self.assertEqual((it["searched_terms"], it["verbatim"], it["reasons"]), (HIT, "", "探した語に当たりがある"))
        self.assertIn("noise：", it["hits"])
        self.assertEqual(it["fingerprint"], sha1_8(re.sub(r"\s", "", HIT)))
        self.assertIn("探した語（searched_terms）がある件は", d["instructions"])
        out = self.run_bridge("review", "--source-checks")[1]
        self.assertIn(f"> {HIT}", out)
        # 判断ファイルの答えを apply が書く（指紋は探した語の指紋）
        answer = {**d["answer_example"], "by": "tester", "saved": "2026-11-15T00:00:00",
                  "source_checks": [{"id": "doe2020#e4", "fingerprint": it["fingerprint"], "result": "一致", "page": "", "note": "別の意味"}]}
        self.write("answer.json", json.dumps(answer, ensure_ascii=False))
        code, out = self.run_bridge("apply", "answer.json")
        self.assertEqual(code, 0, out)
        self.assertIn("原本での確認を記録: doe2020#e4", out)
        self.assertNotIn("doe2020#e4: 要ヒューマンチェック", self.run_bridge("check")[1])

    # ---- spread と分類器

    def test_spread_counts_absence_apart(self):
        self.add(NO_HIT)
        code, out = self.run_bridge("spread")
        self.assertEqual(code, 0, out)
        self.assertIn("doe2020  抜き書き 4（引用に使う 1）", out)
        self.assertIn("  不在の抜き書き 1", out)
        self.assertNotIn("  所在なし", out)
        self.assertIn("所在なし 0、不在の抜き書き 1", out)

    def test_classifier_units_skip_absence(self):
        from cite_bridge.judge import units_from_data
        e = {"id": "k#e1", "verbatim": "a", "searched_terms": ""}
        a = {"id": "k#e2", "verbatim": "", "searched_terms": "x"}
        data = {"citations": [{"kind": "主張", "id": "c001", "sentence": "文。", "fields": {}, "evidence": [e]},
                              {"kind": "主張", "id": "c002", "sentence": "文。", "fields": {}, "evidence": [e, a]}],
                "excerpts_only": [dict(a, id="k#e3")]}
        self.assertEqual([u["item"] for u in units_from_data(data, bib={})], ["cite:c001", "exc:k#e1"])


class AbsencePublishTest(unittest.TestCase):
    setUp = tp.PublishTest.setUp
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)
    configure = tp.PublishTest.configure
    publish = tp.PublishTest.publish

    def prepare(self):
        self.write("bridge/excerpts/doe2020.md", tb.EXCERPTS + absence("e4", NO_HIT, writer="tester"))
        self.write("bridge/citations.md", self.read("bridge/citations.md").replace("抜き書き: doe2020#e1", "抜き書き: doe2020#e1, doe2020#e4"))
        self.assertEqual(self.run_bridge("derive")[0], 0)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        for eid in ("doe2020#e1", "doe2020#e4"):
            self.assertEqual(self.run_bridge("confirm", eid, "--by", "tester")[0], 0)
        code, out = self.run_bridge("checkpoint", "--by", "tester")
        self.assertEqual(code, 0, out)

    def test_publication_carries_searched_terms(self):
        self.prepare()
        doc, out = self.publish()
        e1, e4 = doc["content"]["excerpts"]
        self.assertEqual((e1["searched_terms"], e1["derived"]["hits"]), ("", ""))
        self.assertEqual((e4["id"], e4["searched_terms"], e4["verbatim"], e4["verbatim_sha256"]), ("doe2020#e4", NO_HIT, None, None))
        self.assertEqual(e4["verbatim_fingerprint"], tp.sha1_8(tp.ws(NO_HIT)))
        self.assertEqual(e4["summary_fingerprint"], tp.sha1_8("\n".join(tp.ws(x) for x in (NO_HIT, "", SUMMARY, ""))))
        self.assertEqual(e4["derived"], {"match": "当たりなし", "location": "", "section_kind": "", "human_check": "", "hits": ""})
        cit = doc["content"]["citations"][0]
        self.assertEqual(cit["evidence_fingerprint"],
                         tp.sha1_8(f"doe2020#e1\t{tp.ws(e1['verbatim'])}\ndoe2020#e4\t{tp.ws(NO_HIT)}"))
        self.assertIn("逐語を外したもの 0 件", out)  # 不在の抜き書きは、逐語を外したものに数えない

    def test_withheld_source_still_publishes_searched_terms(self):
        self.configure(publication=tp.PUBLICATION + 'withhold_verbatim = ["doe2020"]\n')
        self.prepare()
        doc, out = self.publish()
        e1, e4 = doc["content"]["excerpts"]
        self.assertIsNone(e1["verbatim"])
        self.assertEqual(e4["searched_terms"], NO_HIT)  # 探した語は書き手の文なので出す
        self.assertIn("逐語を外したもの 1 件", out)


if __name__ == "__main__":
    unittest.main()
