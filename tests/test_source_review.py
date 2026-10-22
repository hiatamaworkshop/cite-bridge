# -*- coding: utf-8 -*-
"""要ヒューマンチェックを確かめる材料（review・承認の HTML・依頼の JSON、設計 §5.5 と §5.10 の 6）の試験。

一時フォルダに小さな一式を作って動かす。HTML の画面の部分は node で動かす試験（test_review_js.py）が見る。
実行:  python -m pytest -q tests/test_source_review.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_bridge as tb

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge.manuscript import verbatim_fingerprint  # noqa: E402
from cite_bridge.review import INSTRUCTIONS  # noqa: E402

BIB = tb.BIB + ("\nLee, K. (2019). Noise study. *Journal*, 3(1), 1–2.\nkey: noisy2020\n（PDF: `noisy2020.pdf`）\n"
                "\nKim, S. (2021). Scanned study. *Journal*, 2(1), 1–2.\nkey: ocr2020\n（PDF: `ocr2020.pdf`）\n")
OCR_TEXT = ("<!-- extract\npdf: ocr2020.pdf\nsha256: 0000\npages: 2\nocr_pages: 2\nextractor: pymupdf 1.28.2\n"
            "extracted: 2026-10-22\n-->\n"
            "The first page has ordinary words of the study and the data.\fPage two verbatim OCR sentence here for the test.\n")
OCR_SENTENCE = "Page two verbatim OCR sentence here for the test."
NOISY_TEXT = "The grids are � faster in noisy rooms. Other words of the study here.\n"
NOISY_SENTENCE = "The grids are � faster in noisy rooms."


def excerpt(key, eid, verbatim, writer="test"):
    return f"# {key}\n\n## {eid}\n逐語: {verbatim}\n強さ: 観察\n要約: 要約。\n言っていないこと: なし。\n記入: {writer}\n"


class SourceReviewTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.write("bridge/bridge.toml", tb.CONFIG)
        self.write("bib.md", BIB)
        self.write("refs/_txt/doe2020.txt", tb.PAPER)
        self.write("refs/_txt/ocr2020.txt", OCR_TEXT)
        self.write("refs/_txt/noisy2020.txt", NOISY_TEXT)
        self.write("bridge/excerpts/ocr2020.md", excerpt("ocr2020", "e1", OCR_SENTENCE))
        self.write("bridge/excerpts/noisy2020.md", excerpt("noisy2020", "e1", NOISY_SENTENCE))
        self.write("bridge/excerpts/doe2020.md", tb.EXCERPTS)
        self.write("manuscript.md", "# 本文\n\n第二頁では、Page two verbatim OCR sentence here for the test.〔c001〕\n")
        self.write("bridge/citations.md", "# 引用\n対象: manuscript.md\n\n## c001\n種類: 主張\n抜き書き: ocr2020#e1\n"
                   "理由: 試験\n原文との差: 一致\n記入: test\n承認: 未\n")

    def tearDown(self):
        def writable(func, path, _exc):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(self.dir, onerror=writable)

    def run_bridge(self, *args):
        r = subprocess.run([sys.executable, "-X", "utf8", str(tb.BRIDGE), *args], cwd=self.dir,
                           capture_output=True, text=True, encoding="utf-8", env=tb.BridgeTest.clean_env())
        return r.returncode, r.stdout + r.stderr

    def write(self, name, text):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def read(self, name):
        return (self.dir / name).read_text(encoding="utf-8")

    def source_checks_json(self):
        code, out = self.run_bridge("review", "--source-checks", "--json")
        self.assertEqual(code, 0, out)
        return json.loads(out)

    # ---- §5.10 の 6（依頼の JSON の形）

    def test_source_checks_json_shape(self):
        self.run_bridge("derive")
        d = self.source_checks_json()
        self.assertEqual(d["format"], "cite-bridge-source-checks/1")
        self.assertEqual(d["manuscript"], "manuscript.md")
        self.assertEqual(d["instructions"], INSTRUCTIONS)
        self.assertTrue(d["instructions"].startswith("各件の逐語が、原本（頁の画像、無ければ原本の PDF か紙）に、そのとおりあるかを確かめる。"))
        ex = d["answer_example"]
        self.assertEqual(ex["format"], "cite-bridge-decisions/1")
        self.assertEqual(ex["source_checks"], [{"id": "<id>", "fingerprint": "<fingerprint>", "result": "一致",
                                                "page": "", "note": ""}])
        self.assertEqual((ex["decisions"], ex["candidates"], ex["confirms"]), ([], [], []))
        ids = {it["id"]: it for it in d["items"]}
        self.assertEqual(set(ids), {"ocr2020#e1", "noisy2020#e1"})  # 印のある抜き書きだけ。doe2020 は印が無い
        it = ids["ocr2020#e1"]
        self.assertEqual(set(it), {"id", "reasons", "verbatim", "location", "fingerprint", "grade", "page_image",
                                   "record", "problem", "written_by"})
        self.assertEqual(it["reasons"], "OCR の文字の層（PDF 2頁目）")
        self.assertEqual(it["fingerprint"], verbatim_fingerprint(OCR_SENTENCE))
        self.assertEqual(it["problem"], "原本での確認が無い")
        self.assertEqual(it["record"], "")
        self.assertIsNone(it["page_image"])  # --images を渡していないので画像は無い
        self.assertEqual(it["written_by"], "test")
        self.assertIn("逐語の範囲に読めない字", ids["noisy2020#e1"]["reasons"])

    def test_source_checks_md_has_confirm_command(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("review", "--source-checks")
        self.assertEqual(code, 0, out)
        self.assertIn("## ocr2020#e1", out)
        self.assertIn("- 理由: OCR の文字の層（PDF 2頁目）", out)
        self.assertIn("confirm ocr2020#e1 --source --by <名前> --page", out)

    def test_source_checks_images_option_writes_page_image(self):
        self.run_bridge("derive")
        pdf_name = "ocr2020.pdf"
        make_pdf(self.dir / "refs" / pdf_name)
        imgs = self.dir / "imgs"
        code, out = self.run_bridge("review", "--source-checks", "--json", "--images", str(imgs))
        self.assertEqual(code, 0, out)
        it = {x["id"]: x for x in json.loads(out)["items"]}["ocr2020#e1"]
        self.assertIsNotNone(it["page_image"])
        self.assertTrue(Path(it["page_image"]).exists())

    def test_source_checks_empty_when_confirmed(self):
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "tester")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "noisy2020#e1", "--source", "--by", "tester")[0], 0)
        self.assertEqual(self.source_checks_json()["items"], [])

    # ---- §5.5 の 2〜4（確認待ち・excerpts_only・md）

    def test_unconfirmed_source_keeps_approved_citation_in_review(self):
        self.run_bridge("derive")
        self.run_bridge("confirm", "ocr2020#e1", "--by", "tester")  # 要約は確かめたが、原本での確認は無い
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        code, out = self.run_bridge("review")
        self.assertIn("## c001", out)  # 承認済でも、要ヒューマンチェックの原本での確認が無ければ確認待ち
        self.assertIn("- 要ヒューマンチェック: OCR の文字の層（PDF 2頁目）（確認済: なし / 未: 原本での確認が無い）", out)
        self.assertIn("原本で確かめた: `python", out)
        self.assertIn("confirm ocr2020#e1 --source --by 人 --page", out)
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "tester")[0], 0)
        self.assertNotIn("## c001", self.run_bridge("review")[1])  # 確認が済めば外れる

    def test_unconfirmed_source_puts_excerpt_in_excerpts_only(self):
        self.run_bridge("derive")
        self.run_bridge("confirm", "noisy2020#e1", "--by", "tester")  # 要約は確かめた。原本での確認は無い
        code, out = self.run_bridge("review", "--json")
        self.assertEqual(code, 0, out)
        only = {e["id"]: e for e in json.loads(out)["excerpts_only"]}
        self.assertIn("noisy2020#e1", only)
        e = only["noisy2020#e1"]
        self.assertEqual(e["needs_check"], "逐語の範囲に読めない字")
        self.assertFalse(e["check_ok"])
        self.assertEqual(e["check_problem"], "原本での確認が無い")
        self.assertEqual(e["verbatim_fp"], verbatim_fingerprint(NOISY_SENTENCE))
        self.assertIn("check_record", e)
        self.run_bridge("confirm", "noisy2020#e1", "--source", "--by", "tester")
        only = {e["id"] for e in json.loads(self.run_bridge("review", "--json")[1])["excerpts_only"]}
        self.assertNotIn("noisy2020#e1", only)

    # ---- §5.5 の 7（承認の HTML の材料）

    def test_html_carries_source_check_inputs_and_vfp(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("review", "--html", "-o", "review.html")
        self.assertEqual(code, 0, out)
        html = self.read("review.html")
        self.assertIn('data-scheck="ocr2020#e1"', html)
        self.assertIn('data-scheck="noisy2020#e1"', html)
        self.assertIn("要ヒューマンチェック：OCR の文字の層（PDF 2頁目）", html)
        self.assertIn("要ヒューマンチェック 2 件", html)
        self.assertIn("要ヒューマンチェックは、機械の照合では原本の字を保証できない抜き書きである", html)
        m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
        payload = json.loads(m.group(1).replace("<\\/", "</"))
        self.assertEqual(payload["vfp"], {"ocr2020#e1": verbatim_fingerprint(OCR_SENTENCE),
                                          "noisy2020#e1": verbatim_fingerprint(NOISY_SENTENCE)})

    def test_html_hides_inputs_for_confirmed_source(self):
        self.run_bridge("derive")
        self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "tester")
        self.run_bridge("review", "--html", "-o", "review.html")
        html = self.read("review.html")
        self.assertNotIn('data-scheck="ocr2020#e1"', html)  # 有効な確認が済んだものは入力を出さない
        self.assertIn('data-scheck="noisy2020#e1"', html)

    def test_source_checks_not_for_new_candidate_excerpts(self):
        """候補の新しい抜き書きには、抜き書きの ID が無いので原本での確認の入力を出さない（設計 §5.5 の 7 の補足）。"""
        from cite_bridge.review import review_page
        self.run_bridge("derive")
        data = {"manuscript": "m", "generated": "g", "citations": [], "candidates": [{
            "id": "q1", "candidate": True, "kind": "主張", "key": "doe2020", "entry": "", "cfp": "x", "state": "候補",
            "line": 1, "section": "", "sentence": "", "paren": "", "paragraph": "", "fields": {},
            "evidence": [{"id": "doe2020（新 1）", "new": True, "verbatim": "x", "grade": "PDF所持（OCR の抽出）",
                          "source_check": "", "secondary": "", "needs_check": "OCR の抽出", "check_ok": False, "check_problem": "原本での確認が無い",
                          "check_record": "", "verbatim_fp": "abcd1234", "strength": "観察", "summary": "", "not_said": "",
                          "summary_checked": None, "summary_fp": "", "location": "", "match": "一致", "before": "",
                          "sentence": "", "after": "", "image": None, "weak": False, "written_by": ""}]}],
            "excerpts_only": []}
        html = review_page(data)
        self.assertNotIn('data-scheck="doe2020（新 1）"', html)


def make_pdf(path):
    import pymupdf
    d = pymupdf.open()
    d.new_page().insert_text((72, 72), "The first page has ordinary words of the study and the data.")
    pg = d.new_page()  # 二頁目が OCR の文字の層（逐語の頁）
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
    pix.clear_with(255)
    pg.insert_image(pg.rect, pixmap=pix)
    pg.insert_text((72, 100), OCR_SENTENCE, render_mode=3)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(path)
    d.close()


if __name__ == "__main__":
    unittest.main()
