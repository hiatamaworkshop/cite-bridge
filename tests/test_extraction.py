# -*- coding: utf-8 -*-
"""抽出の頭書きと抽出の診断（設計 §4.6）の試験。一時フォルダに PDF と抽出テキストを作って動かす。

実行:  python -m pytest -q tests/test_extraction.py
"""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_bridge as tb

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge.source import Source  # noqa: E402

try:
    import pymupdf
except ImportError:  # PDF を作れない環境では試験を飛ばす
    pymupdf = None

BIB = """Doe, J. (2020). A study of things. *Journal of Things*, 1(1), 1–3.
key: paper2020
（PDF: `paper2020.pdf`）
"""
SENTENCE = "Participants completed the task in twelve seconds and the results of the study were clear to all of us."
PAGE1 = SENTENCE + " The results of the study and the data in the paper are the basis of the claim."
PAGE2_HIDDEN = "Hidden OCR text: the scan of the page and the words of the study are recognized here."
PAGE3 = "The conclusion of the study is that the grids are faster than the lists of the users."
EXCERPT = f"""# paper2020

## e1
逐語: {SENTENCE}
強さ: 観察
要約: 課題は平均12秒で終わった。
言っていないこと: 雑音の中では測っていない。
記入: test
"""
CITATIONS = "# 引用\n対象: manuscript.md\n"
MANUSCRIPT = "Doe らの研究では、結果が示された（Doe, 2020）。\n"


def make_pdf(path, pages):
    """pages は (種類, 文字) の並び。種類 ocr は頁全体の画像の上に見えない文字（OCR の結果）を置く。"""
    d = pymupdf.open()
    for kind, body in pages:
        pg = d.new_page()
        if kind == "ocr":
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
            pix.clear_with(255)
            pg.insert_image(pg.rect, pixmap=pix)
            pg.insert_text((72, 100), body, render_mode=3)
        else:
            pg.insert_text((72, 72), body)
    d.save(path)
    d.close()


PAGES = [("text", PAGE1), ("ocr", PAGE2_HIDDEN), ("text", PAGE3)]


@unittest.skipIf(pymupdf is None, "pymupdf が無い")
class ExtractionHeaderTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.write("bridge/bridge.toml", tb.CONFIG)
        self.write("bib.md", BIB)
        self.write("bridge/excerpts/paper2020.md", EXCERPT)
        (self.dir / "refs").mkdir()
        self.pdf = self.dir / "refs" / "paper2020.pdf"
        make_pdf(self.pdf, PAGES)
        self.txt = self.dir / "refs" / "_txt" / "paper2020.txt"

    def tearDown(self):
        def writable(func, path, _exc):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(self.dir, onerror=writable)

    @staticmethod
    def clean_env():
        return tb.BridgeTest.clean_env()

    def run_bridge(self, *args):
        r = subprocess.run([sys.executable, "-X", "utf8", str(tb.BRIDGE), *args], cwd=self.dir,
                           capture_output=True, text=True, encoding="utf-8", env=self.clean_env())
        return r.returncode, r.stdout + r.stderr

    def write(self, name, text):
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def read(self, name):
        return (self.dir / name).read_text(encoding="utf-8")

    def write_body(self, body):
        """頭書きの無い抽出テキスト（道具の以前の版が作った形）を置く。"""
        self.write("refs/_txt/paper2020.txt", body)

    @staticmethod
    def header_of(text):
        return text.split("-->", 1)[0]

    # ---- 頭書き（§4.1、§4.2、§4.6 の 1）

    def test_extract_writes_header_with_ocr_pages(self):
        code, out = self.run_bridge("extract", "paper2020")
        self.assertEqual(code, 0, out)
        text = self.txt.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("<!-- extract\n"))
        head = self.header_of(text)
        self.assertIn("\npdf: paper2020.pdf\n", head)
        self.assertIn(f"\nsha256: {hashlib.sha256(self.pdf.read_bytes()).hexdigest()}\n", head)
        self.assertIn("\npages: 3\n", head)
        self.assertIn("\nocr_pages: 2\n", head)
        self.assertIn(f"\nextractor: pymupdf {pymupdf.__version__}\n", head)
        self.assertIn(f"\nextracted: {datetime.date.today().isoformat()}\n", head)
        self.assertTrue(text.split("-->\n", 1)[1].startswith(SENTENCE))  # 頭書きの後に本文

    def test_no_ocr_pages_line_without_ocr(self):
        make_pdf(self.pdf, [("text", PAGE1), ("text", PAGE3)])
        self.assertEqual(self.run_bridge("extract", "paper2020")[0], 0)
        head = self.header_of(self.txt.read_text(encoding="utf-8"))
        self.assertIn("\npages: 2\n", head)
        self.assertNotIn("ocr_pages", head)

    def test_ocr_layer_pages_and_grade(self):
        self.run_bridge("extract", "paper2020")
        code, out = self.run_bridge("grade")
        self.assertEqual(code, 0, out)
        self.assertIn("PDF所持（OCR の文字の層）: 1  paper2020", out)
        self.assertIn("機械で照合できるもの 0 件", out)  # OCR の文字の層は数えない（§4.4）

    def test_ocr_pages_are_read_as_set(self):
        self.run_bridge("extract", "paper2020")
        self.assertEqual(Source(self.txt).ocr_pages(), {2})
        self.write_body("a\fb\f")
        self.assertEqual(Source(self.txt).ocr_pages(), set())  # 頭書きの無いものは空

    # ---- --header-only（§4.3、§4.6 の 2）

    def test_header_only_adds_header_and_keeps_body(self):
        body = f"{PAGE1}\f{PAGE2_HIDDEN}\f{PAGE3}\n"
        self.write_body(body)
        code, out = self.run_bridge("check")
        self.assertIn("頭書きが無い（extract --header-only で足す）", out)
        code, out = self.run_bridge("extract", "paper2020", "--header-only")
        self.assertEqual(code, 0, out)
        text = self.txt.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("<!-- extract\n"))
        self.assertEqual(text.split("-->\n", 1)[1], body)  # 本文は一字も変わらない
        head = self.header_of(text)
        self.assertIn("\nextractor: 不明（頭書きは後から足した）\n", head)
        self.assertIn(f"\nannotated: {datetime.date.today().isoformat()}\n", head)
        self.assertIn("\nocr_pages: 2\n", head)
        code, out = self.run_bridge("extract", "paper2020", "--header-only")  # 二度目は飛ばす
        self.assertEqual(code, 0, out)
        self.assertIn("既に頭書きがある", out)
        self.assertEqual(self.txt.read_text(encoding="utf-8"), text)

    def test_header_only_refuses_force(self):
        self.write_body(PAGE1)
        code, out = self.run_bridge("extract", "paper2020", "--header-only", "--force")
        self.assertNotEqual(code, 0)
        self.assertIn("一緒に使えない", out)
        self.assertEqual(self.txt.read_text(encoding="utf-8"), PAGE1)

    # ---- 照合から外す（§4.4、§4.6 の 3・4）

    def test_header_text_is_not_matched(self):
        self.run_bridge("extract", "paper2020")
        self.write("bridge/excerpts/paper2020.md", EXCERPT.replace(SENTENCE, "extractor: pymupdf"))
        self.assertEqual(self.run_bridge("derive")[0], 0)
        self.assertIn("@照合: 不一致", self.read("bridge/excerpts/paper2020.md"))

    def test_trailing_empty_page_is_not_counted(self):
        self.write_body("first page text\f")
        self.assertEqual(Source(self.txt).pages(), 1)
        self.write_body("first page text\fsecond page text\f\n")
        self.assertEqual(Source(self.txt).pages(), 2)
        self.write_body("first page text\f\fthird page text")
        self.assertEqual(Source(self.txt).pages(), 3)  # 途中の空の頁は数える

    # ---- 抽出の診断（§4.4、§4.5、§4.6 の 5〜7）

    def test_page_count_mismatch_is_note(self):
        self.run_bridge("extract", "paper2020")
        self.write_body(self.txt.read_text(encoding="utf-8").replace("\f", " "))  # 頭書きは残し、頁の区切りを消す
        self.assertEqual(self.run_bridge("derive")[0], 0)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("NOTE  bridge/excerpts/paper2020.md: 抽出の診断: 頁の区切りが PDF と合わない（PDF 3 頁、テキスト 1 頁", out)
        self.assertEqual(self.run_bridge("check", "--strict")[0], 1)

    def test_replaced_pdf_is_note(self):
        self.run_bridge("extract", "paper2020")
        self.assertEqual(self.run_bridge("derive")[0], 0)
        make_pdf(self.pdf, [("text", "A different document with other words of the study and the paper.")])
        self.assertEqual(self.run_bridge("derive")[0], 0)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("NOTE  bridge/excerpts/paper2020.md: 抽出の診断: 抽出の後に PDF が替わった", out)

    def test_unreadable_characters_are_info(self):
        self.write_body(f"{PAGE1} ��\f{PAGE2_HIDDEN}\f{PAGE3}\n")
        self.assertEqual(self.run_bridge("extract", "paper2020", "--header-only")[0], 0)
        self.assertEqual(self.run_bridge("derive")[0], 0)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("INFO  bridge/excerpts/paper2020.md: 抽出の診断: 読めない字 2", out)
        self.assertNotIn("NOTE  bridge/excerpts/paper2020.md: 抽出の診断", out)

    def test_diagnosis_appears_in_propose_worksheet(self):
        self.write_body(f"{PAGE1} ��\f{PAGE2_HIDDEN}\f{PAGE3}\n")
        self.assertEqual(self.run_bridge("extract", "paper2020", "--header-only")[0], 0)
        self.write("bridge/citations.md", CITATIONS)
        self.write("manuscript.md", MANUSCRIPT)
        code, out = self.run_bridge("propose")
        self.assertEqual(code, 0, out)
        work = json.loads(self.read("bridge/candidates/work.json"))
        keys = [k for it in work["items"] for k in it["keys"] if k["key"] == "paper2020"]
        self.assertEqual(len(keys), 1, work)
        self.assertEqual(keys[0]["diagnosis"], ["読めない字 2（置換文字・私用領域・cid）"])
        self.assertIn("- 抽出の診断: 読めない字 2（置換文字・私用領域・cid）", self.read("bridge/candidates/work.md"))


if __name__ == "__main__":
    unittest.main()
