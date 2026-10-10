# -*- coding: utf-8 -*-
"""cite-bridge の試験。論文のデータに依らず、一時フォルダに小さな試験用の一式を作って動かす。

実行:  python -m unittest discover -s .claude/skills/cite-bridge/tests
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BRIDGE = Path(__file__).resolve().parent.parent / "bridge.py"

PAPER = """A Study of Things
Abstract We study things and how people use them in many settings.
\f1 Introduction
Things matter. We build a tool for things.
2 Related Work
2.1 Prior Systems
Smith (2010) reported that users prefer grids over lists. Grids were faster.
3 Results
Participants completed the task in 12 seconds on average. No errors occurred during the study.
\f4 Discussion
Our results suggest that grids may help in noisy settings, although we did not test noise.
5 Conclusion
We presented a tool.
References
Smith, J. (2010). Grids and lists.
"""

JA_PAPER = """1. はじめに
音声は状態理解の容易性に関してはもともと不利なメデイアということになる．
しかしながら，状況は改善する可能性をもつ．
"""

CONFIG = """[bibliography]
path = "bib.md"
format = "keyline"
pdf_pattern = 'PDF: `?([^`]+?\\.pdf)'
web_pattern = 'https?://(?!doi\\.org)'
[sources]
pdf_dir = "refs"
text_dir = "refs/_txt"
web_dir = "refs/_web"
[bridge]
excerpts = "bridge/excerpts"
citations = "bridge/citations.md"
"""

BIB = """Doe, J. (2020). A study of things. *Journal of Things*, 1(1), 1–3.
key: doe2020
（PDF: `doe2020.pdf`）

山田太郎. (2002). 音声の研究. *音声誌*, 1(1), 1–1.
key: yamada2002
（PDF: `yamada2002.pdf`）

Acme. (2026). Acme docs. https://acme.example/docs
key: acme_docs
"""

EXCERPTS = """# doe2020

## e1
逐語: Participants completed the task in 12 seconds on average.
強さ: 観察
要約: 平均12秒で課題を終えた。
言っていないこと: 雑音の中では測っていない。
記入: test

## e2
逐語: Smith (2010) reported that users prefer grids over lists.
強さ: 観察
要約: Smith によれば、利用者は一覧より格子を好む。
言っていないこと: Doe らの観察ではない。
記入: test

## e3
逐語: grids may help in noisy settings
強さ: 示唆
要約: 雑音の中で格子が役立つかもしれない。
言っていないこと: 雑音で試してはいない。
記入: test
"""

MANUSCRIPT = """# 本文

## 2.1 先行研究

Doe らの実験では、参加者は "completed the task in 12 seconds on average" であった（Doe, 2020）〔c001〕。<!-- コメント。ここに。がある -->続く文。
"""

CITATIONS = """# 引用
対象: manuscript.md

## c001
種類: 主張
抜き書き: doe2020#e1
理由: 試験
原文との差: 一致
記入: test
承認: 未
"""


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        files = {
            "bridge/bridge.toml": CONFIG, "bib.md": BIB, "refs/_txt/doe2020.txt": PAPER,
            "refs/_txt/yamada2002.txt": JA_PAPER, "bridge/excerpts/doe2020.md": EXCERPTS,
            "manuscript.md": MANUSCRIPT, "bridge/citations.md": CITATIONS,
        }
        for name, text in files.items():
            p = self.dir / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_bridge(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, "-X", "utf8", str(BRIDGE), *args], cwd=self.dir,
                           capture_output=True, text=True, encoding="utf-8", env=env)
        return r.returncode, r.stdout + r.stderr

    def read(self, name):
        return (self.dir / name).read_text(encoding="utf-8")

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8", newline="\n")

    # ---- 抜き書き

    def test_derive_location_and_kind(self):
        self.assertEqual(self.run_bridge("derive")[0], 0)
        ex = self.read("bridge/excerpts/doe2020.md")
        self.assertIn("@照合: 一致", ex)
        self.assertIn("p.2（PDF 2頁目） / §3 Results", ex)          # 頁範囲 1–3 と PDF の3頁が合うので印刷の頁も出る
        self.assertIn("@節の種類: 結果", ex)
        self.assertIn("@節の種類: 関連研究", ex)                      # e2 は §2.1（親が Related Work）
        self.assertIn("@後: No errors occurred during the study.", ex)
        self.assertIn("@含む文: Our results suggest that grids", ex)  # e3 は文の途中で切れている
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("関連研究の節にある文", out)

    def test_stale_derived_and_missing_verbatim(self):
        self.run_bridge("derive")
        ex = self.read("bridge/excerpts/doe2020.md").replace("12 seconds on average", "10 seconds on average")
        self.write("bridge/excerpts/doe2020.md", ex)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 1)
        self.assertIn("導く欄が古い", out)
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 1)
        self.assertIn("近似一致", self.read("bridge/excerpts/doe2020.md"))

    def test_japanese_small_kana_and_spacing(self):
        self.write("bridge/excerpts/yamada2002.md", "# yamada2002\n\n## e1\n逐語: 音声は状態理解の容易性に関してはもともと不利なメディアということになる．\n"
                   "強さ: 主張\n要約: 音声は状態の理解に不利である。\n言っていないこと: なし。\n記入: test\n")
        self.run_bridge("derive")
        self.assertIn("@照合: 正規化で一致", self.read("bridge/excerpts/yamada2002.md"))

    # ---- 引用

    def test_citation_cycle(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("未承認", out)
        self.assertEqual(self.run_bridge("check", "--strict")[0], 1)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        self.assertIn("承認済 1", self.run_bridge("check")[1])
        # コメントだけを直しても要再確認にならない
        self.write("manuscript.md", self.read("manuscript.md").replace("ここに。がある", "直した"))
        self.assertIn("承認済 1", self.run_bridge("check")[1])
        # 本文を直すと要再確認へ戻る
        self.write("manuscript.md", self.read("manuscript.md").replace("Doe らの実験では", "Doe らの研究では"))
        self.assertIn("要再確認 1", self.run_bridge("check")[1])

    def test_quote_must_be_in_excerpt_unless_declared(self):
        self.run_bridge("derive")
        self.write("manuscript.md", self.read("manuscript.md").replace("completed the task in 12 seconds on average",
                                                                        "finished the task in 12 seconds on average"))
        code, out = self.run_bridge("check")
        self.assertEqual(code, 1)
        self.assertIn("抜き書きの逐語に無い", out)
        self.write("bridge/citations.md", self.read("bridge/citations.md").replace(
            "原文との差: 一致", "原文との差: 言い換え\n引用でない句: finished the task in 12 seconds on average（試験）"))
        self.assertEqual(self.run_bridge("check")[0], 0)

    def test_orphan_and_missing_blocks(self):
        self.run_bridge("derive")
        self.write("manuscript.md", self.read("manuscript.md") + "\n別の文（Doe, 2020）〔c002〕。\n")
        self.write("bridge/citations.md", self.read("bridge/citations.md") + "\n## c003\n種類: 指示\n文献: doe2020\n")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 1)
        self.assertIn("〔c002〕に対応するブロックが無い", out)
        self.assertIn("孤児のブロック", out)

    def test_english_field_names(self):
        en = EXCERPTS.replace("逐語", "verbatim").replace("強さ: 観察", "strength: observation") \
            .replace("強さ: 示唆", "strength: suggestion").replace("要約", "summary") \
            .replace("言っていないこと", "not_said").replace("記入", "written_by")
        self.write("bridge/excerpts/doe2020.md", en)
        self.write("bridge/bridge.toml", CONFIG + '[output]\nlanguage = "en"\n')
        self.run_bridge("derive")
        self.assertIn("@match: 一致", self.read("bridge/excerpts/doe2020.md"))
        self.assertEqual(self.run_bridge("check")[0], 0)

    # ---- 書誌のアダプタ・格・その他

    def test_grade_and_adapters(self):
        out = self.run_bridge("grade")[1]
        self.assertIn("PDF所持（抽出あり）: 2", out)
        self.assertIn("Web 資料（写しなし）: 1", out)
        self.write("bib.bib", "@article{doe2020, author = {Doe, Jane}, title = {A Study}, year = 2020,"
                              " file = {:doe2020.pdf:PDF}}\n@misc{acme_docs, title = {Acme}, url = {https://acme.example/docs}}\n")
        self.write("bridge/bridge.toml", CONFIG.replace('path = "bib.md"\nformat = "keyline"', 'path = "bib.bib"\nformat = "bibtex"'))
        out = self.run_bridge("grade")[1]
        self.assertIn("PDF所持（抽出あり）: 1", out)
        self.assertIn("Web 資料（写しなし）: 1", out)
        self.write("bib.json", '[{"id": "doe2020", "title": "A Study", "file": "doe2020.pdf"}]')
        self.write("bridge/bridge.toml", CONFIG.replace('path = "bib.md"\nformat = "keyline"', 'path = "bib.json"\nformat = "csl-json"'))
        self.assertIn("PDF所持（抽出あり）: 1", self.run_bridge("grade")[1])

    def test_strip(self):
        self.assertEqual(self.run_bridge("strip", "manuscript.md", "out.md")[0], 0)
        self.assertNotIn("〔c001〕", self.read("out.md"))
        self.assertIn("〔c001〕", self.read("manuscript.md"))

    def test_snapshot_pdf_url(self):
        # URL が PDF を指すとき、頁を保って抽出する（file:// で試す。ネットワークは使わない）
        import pymupdf
        doc = pymupdf.open()
        for text in ("First page about acme.", "Second page: the acme docs say hello."):
            doc.new_page().insert_text((72, 72), text)
        pdf = self.dir / "acme.pdf"
        doc.save(pdf)
        code, out = self.run_bridge("snapshot", "acme_docs", pdf.as_uri())
        self.assertEqual(code, 0, out)
        self.assertIn("type: pdf", self.read("refs/_web/acme_docs.txt"))
        self.write("bridge/excerpts/acme_docs.md", "# acme_docs\n\n## e1\n逐語: the acme docs say hello.\n強さ: 観察\n"
                   "要約: 挨拶する。\n言っていないこと: なし。\n記入: test\n")
        self.run_bridge("derive")
        self.assertIn("PDF 2頁目", self.read("bridge/excerpts/acme_docs.md"))

    def test_latex_cite_with_id_comment(self):
        # LaTeX: \cite{key}%c001 の形。段落は折り返し、文の終わりは英語のピリオド
        cfg = CONFIG + ("[manuscript]\n"
                        "mark_pattern = '\\\\cite\\{(?P<key>[^}]+)\\}(?P<strip>%(?P<id>c\\d+))'\n"
                        "quote_patterns = [\"``(.{20,}?)''\"]\n"
                        "sentence_end = '[.!?](?=\\s)'\n"
                        "paragraph = \"blank\"\n")
        self.write("bridge/bridge.toml", cfg)
        tex = ("\\section{Related}\n"
               "Prior work exists. Participants ``completed the task in 12 seconds on average''\n"
               "according to Doe \\cite{doe2020}%c001\n"
               "and this was fast. Another sentence.\n")
        self.write("manuscript.tex", tex)
        self.write("bridge/citations.md", CITATIONS.replace("manuscript.md", "manuscript.tex"))
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.run_bridge("approve", "c001", "--by", "tester")
        self.assertIn("@承認時の本文: Participants ``completed", self.read("bridge/citations.md"))
        # strip は印の ID だけを外し、\cite{key} は残す
        self.run_bridge("strip", "manuscript.tex", "out.tex")
        self.assertIn("\\cite{doe2020}\n", self.read("out.tex"))
        # 印の key と根拠の文献が違えば崩れ
        self.write("manuscript.tex", tex.replace("\\cite{doe2020}", "\\cite{yamada2002}"))
        code, out = self.run_bridge("check")
        self.assertEqual(code, 1)
        self.assertIn("抜き書きの文献が合わない", out)

    def test_checkpoint(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("checkpoint")
        self.assertEqual(code, 1)  # 未承認が残っている
        self.assertFalse((self.dir / "bridge/checkpoints").exists())
        self.run_bridge("approve", "c001", "--by", "tester")
        code, out = self.run_bridge("checkpoint", "--label", "test")
        self.assertEqual(code, 0, out)
        import json
        m = json.loads(next((self.dir / "bridge/checkpoints").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(m["label"], "test")
        self.assertEqual(m["approvers"], {"tester": 1})
        self.assertEqual(m["citations"]["承認済"], 1)
        self.assertTrue(m["files"]["manuscript"]["sha256"])

    def test_ocr_text_is_marked(self):
        self.write("refs/_txt/yamada2002.txt", "<!-- ocr\nengine: test\n-->\n" + JA_PAPER)
        self.assertIn("PDF所持（OCR の抽出）: 1", self.run_bridge("grade")[1])

    def test_custom_mark_pattern(self):
        self.write("bridge/bridge.toml", CONFIG + '[manuscript]\nmark_pattern = \'\\[\\^(c\\d+)\\]\'\n')
        self.write("manuscript.md", MANUSCRIPT.replace("〔c001〕", "[^c001]"))
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("未承認 1", out)


if __name__ == "__main__":
    unittest.main()
