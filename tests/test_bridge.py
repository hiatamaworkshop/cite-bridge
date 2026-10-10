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

    # ---- 人の確認（§16）

    def test_approval_note_and_evidence(self):
        self.run_bridge("derive")
        self.run_bridge("approve", "c001", "--by", "tester", "--note", "原文のまま")
        cit = self.read("bridge/citations.md")
        self.assertIn("承認の理由: 原文のまま", cit)
        self.assertIn("@承認時の根拠: ", cit)
        self.assertIn("承認済 1", self.run_bridge("check")[1])
        # 根拠を足すと、本文が同じでも要再確認へ戻る
        self.write("bridge/citations.md", cit.replace("抜き書き: doe2020#e1", "抜き書き: doe2020#e1, doe2020#e3"))
        out = self.run_bridge("check")[1]
        self.assertIn("要再確認 1", out)
        self.assertIn("承認の後に根拠が変わった", out)

    def test_send_back(self):
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester", "--send-back")[0], 1)  # 理由が要る
        self.run_bridge("approve", "c001", "--by", "tester", "--send-back", "--note", "限定が落ちている")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("差し戻し。書き手が直すのを待っている（限定が落ちている）", out)
        self.assertEqual(self.run_bridge("check", "--strict")[0], 1)
        self.write("manuscript.md", self.read("manuscript.md").replace("Doe らの実験では", "Doe らの実験（雑音なし）では"))
        self.assertIn("差し戻しの後に直された", self.run_bridge("check")[1])
        self.run_bridge("approve", "c001", "--by", "tester")
        cit = self.read("bridge/citations.md")
        self.assertNotIn("差し戻し", cit)
        self.assertIn("承認済 1", self.run_bridge("check")[1])

    def test_summary_confirm(self):
        self.run_bridge("derive")
        self.assertIn("未確認 3", self.run_bridge("check")[1])
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--by", "tester")[0], 0)
        ex = self.read("bridge/excerpts/doe2020.md")
        self.assertIn("要約の確認: tester", ex)
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)  # 記録の @ 行は導く欄の比較に入らない
        self.assertIn("tester 1", out)
        self.run_bridge("derive")
        self.assertIn("@要約の確認時の指紋", self.read("bridge/excerpts/doe2020.md"))  # derive は記録を消さない
        self.write("bridge/excerpts/doe2020.md", self.read("bridge/excerpts/doe2020.md").replace("平均12秒で", "平均およそ12秒で"))
        self.assertIn("要約の確認の後に欄が変わった", self.run_bridge("check")[1])

    def test_references_in_fields_must_exist(self):
        self.run_bridge("derive")
        self.write("bridge/excerpts/doe2020.md", self.read("bridge/excerpts/doe2020.md")
                   .replace("言っていないこと: 雑音の中では測っていない。", "言っていないこと: 雑音の中では測っていない（e9）。"))
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 1)
        self.assertIn("言っていないことが指す抜き書き 'e9' が無い", out)
        self.write("bridge/excerpts/doe2020.md", self.read("bridge/excerpts/doe2020.md").replace("（e9）", "（e3）"))
        self.write("bridge/citations.md", self.read("bridge/citations.md").replace("理由: 試験", "理由: 試験\n解釈: yamada2002#e1 と比べる"))
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertIn("解釈が指す抜き書き 'yamada2002#e1' が無い", out)

    def test_review(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("review")
        self.assertEqual(code, 0, out)
        self.assertIn("## c001　未承認", out)
        self.assertLess(out.index("逐語:"), out.index("要約と言っていないこと（AI の候補"))  # 逐語を先に見せる
        self.assertIn("（抽出テキストのまま）", out)
        self.assertIn("confirm doe2020#e1 --by 人", out)
        self.run_bridge("approve", "c001", "--by", "tester")
        self.assertIn("確認待ちの引用は無い", self.run_bridge("review")[1])
        self.assertIn("## c001　承認済", self.run_bridge("review", "c001")[1])

    def test_review_json(self):
        import json
        self.run_bridge("derive")
        self.run_bridge("approve", "c001", "--by", "tester")
        self.assertEqual(json.loads(self.run_bridge("review", "--json")[1])["citations"], [])  # 確認待ちだけ
        d = json.loads(self.run_bridge("review", "--json", "--all")[1])
        c = d["citations"][0]
        self.assertEqual((c["id"], c["state"], c["line"]), ("c001", "承認済", 5))
        self.assertEqual(c["evidence"][0]["id"], "doe2020#e1")
        self.assertIn("approve c001", c["commands"]["approve"])

    def _decisions(self, action, note="", confirm=False):
        import json
        c = json.loads(self.run_bridge("review", "--json", "--all")[1])["citations"][0]
        d = {"format": "cite-bridge-decisions/1", "manuscript": "manuscript.md", "by": "tester",
             "decisions": [{"id": "c001", "action": action, "note": note, "fingerprint": c["fingerprint"],
                            "evidence": c["evidence_fp"]}],
             "confirms": [{"id": "doe2020#e1", "fingerprint": c["evidence"][0]["summary_fp"]}] if confirm else []}
        self.write("decisions.json", json.dumps(d, ensure_ascii=False))

    def test_review_html_and_apply(self):
        self.run_bridge("derive")
        code, out = self.run_bridge("review", "--html", "-o", "review.html")
        self.assertEqual(code, 0, out)
        page = self.read("review.html")
        self.assertIn('data-id="c001"', page)
        self.assertIn("cite-bridge-decisions/1", page)
        self.assertLess(page.index("<blockquote>"), page.index('class="ai"'))  # 逐語を AI の候補より先に
        self._decisions("approve", "原文のまま", confirm=True)
        code, out = self.run_bridge("apply", "decisions.json", "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("未承認 1", self.run_bridge("check")[1])  # dry-run は書かない
        code, out = self.run_bridge("apply", "decisions.json")
        self.assertEqual(code, 0, out)
        out = self.run_bridge("check")[1]
        self.assertIn("承認済 1", out)
        self.assertIn("tester 1", out)  # 要約の確認
        self.assertIn("承認の理由: 原文のまま", self.read("bridge/citations.md"))

    def test_apply_refuses_stale_and_records_send_back(self):
        self.run_bridge("derive")
        self._decisions("send_back", "限定が落ちている")
        self.write("manuscript.md", self.read("manuscript.md").replace("Doe らの実験では", "Doe らの研究では"))
        code, out = self.run_bridge("apply", "decisions.json")
        self.assertEqual(code, 1)
        self.assertIn("判断した後に本文が変わった", out)
        self.assertIn("未承認 1", self.run_bridge("check")[1])
        self._decisions("send_back", "限定が落ちている")
        self.assertEqual(self.run_bridge("apply", "decisions.json")[0], 0)
        self.assertIn("差し戻し。書き手が直すのを待っている", self.run_bridge("check")[1])

    def test_coverage_counts_unmarked_citations(self):
        self.write("manuscript.md", self.read("manuscript.md") + "\n印の無い引用がある（Smith, 2010）。製品の頁もある（Acme, Docs page）。\n")
        self.run_bridge("derive")
        out = self.run_bridge("check")[1]
        self.assertIn("出典らしき括弧 2 のうち、印のある文にあるもの 1、印の無い文にあるもの 1", out)  # 既定は年の括弧だけ
        code, out = self.run_bridge("coverage")
        self.assertIn("manuscript.md:7  （Smith, 2010）", out)
        self.write("bridge/bridge.toml", CONFIG + "[coverage]\npattern = '[（(][^（）()]*\\d{4}[^（）()]*[）)]|[（(][A-Z]\\w*, [^（）()]+[）)]'\n")
        self.assertIn("印の無い文にあるもの 2", self.run_bridge("check")[1])

    def test_approvers_registry(self):
        self.write("bridge/bridge.toml", CONFIG + '[approvers]\nalice = "human"\nreviewer-model = "model"\n')
        self.run_bridge("derive")
        code, out = self.run_bridge("approve", "c001", "--by", "人")
        self.assertEqual(code, 1)
        self.assertIn("承認者の一覧", out)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "alice")[0], 0)
        self.assertIn('<option value="alice">alice（人）</option>', (self.run_bridge("review", "--html", "-o", "r.html"), self.read("r.html"))[1])
        self._decisions("approve")
        self.write("decisions.json", self.read("decisions.json").replace('"tester"', '"mallory"'))
        code, out = self.run_bridge("apply", "decisions.json")
        self.assertEqual(code, 1)
        self.assertIn("'mallory' は承認者の一覧", out)

    def test_apply_log_refuses_replay_and_older(self):
        import json
        self.run_bridge("derive")
        self._decisions("approve", "新しい判断")
        d = json.loads(self.read("decisions.json"))
        d["saved"] = "2026-01-02T00:00:00Z"
        (self.dir / "dl").mkdir()
        self.write("dl/decisions_new.json", json.dumps(d, ensure_ascii=False))
        old = dict(d, saved="2026-01-01T00:00:00Z", decisions=[dict(d["decisions"][0], note="古い判断")])
        self.write("dl/decisions_old.json", json.dumps(old, ensure_ascii=False))
        code, out = self.run_bridge("apply", "--latest", "--from", "dl")
        self.assertEqual(code, 0, out)
        self.assertIn("decisions_new.json", out)
        self.assertTrue((self.dir / "bridge/applied.json").exists())
        code, out = self.run_bridge("apply", "dl/decisions_new.json")
        self.assertEqual(code, 1)
        self.assertIn("適用済み", out)
        code, out = self.run_bridge("apply", "dl/decisions_old.json")
        self.assertEqual(code, 1)
        self.assertIn("より古い", out)
        self.assertIn("承認の理由: 新しい判断", self.read("bridge/citations.md"))

    def test_remark_is_kept_apart_from_approval(self):
        import json
        self.run_bridge("derive")
        self._decisions("", "")
        d = json.loads(self.read("decisions.json"))
        d["decisions"][0]["remark"] = "聴覚と音声を混同しないこと"
        self.write("decisions.json", json.dumps(d, ensure_ascii=False))
        code, out = self.run_bridge("apply", "decisions.json")
        self.assertEqual(code, 0, out)
        cit = self.read("bridge/citations.md")
        self.assertIn("指摘: 聴覚と音声を混同しないこと（tester ", cit)
        self.assertIn("承認: 未", cit)  # 指摘だけでは承認しない
        self.assertIn("指摘：聴覚と音声を混同しないこと", self.run_bridge("review", "--html", "-o", "r.html")[1] + self.read("r.html").replace("</dt><dd>", "："))

    def test_snapshot_rebuild_with_folded_headings(self):
        html = ('<html><body><h2>Commands</h2><p>Intro.</p><a class="zippy">Grid selection</a>'
                '<p>Say "Show grid" to start.</p><details><summary>Labels</summary><p>Say "Show labels".</p></details></body></html>')
        import hashlib
        (self.dir / "refs/_web").mkdir(parents=True, exist_ok=True)
        self.write("refs/_web/acme_docs.html", html)
        self.write("refs/_web/acme_docs.txt", "<!-- snapshot\nurl: https://acme.example/docs\nretrieved: 2026-01-01\n"
                   f"sha256: {hashlib.sha256(html.encode('utf-8')).hexdigest()}\n-->\nold body\n")
        code, out = self.run_bridge("snapshot", "acme_docs", "--rebuild")
        self.assertEqual(code, 0, out)
        txt = self.read("refs/_web/acme_docs.txt")
        self.assertIn("retrieved: 2026-01-01", txt)
        self.assertIn("#### Grid selection", txt)
        self.write("bridge/excerpts/acme_docs.md", "# acme_docs\n\n## e1\n逐語: Say \"Show labels\".\n強さ: 観察\n"
                   "要約: ラベルを出す。\n言っていないこと: なし。\n記入: test\n")
        self.run_bridge("derive")
        ex = self.read("bridge/excerpts/acme_docs.md")
        self.assertIn("/ Labels", ex)
        self.assertNotIn("snapshot", ex.split("@含む文")[-1] if "@含む文" in ex else "")
        self.write("refs/_web/acme_docs.html", html + " ")
        self.assertEqual(self.run_bridge("snapshot", "acme_docs", "--rebuild")[0], 1)  # ハッシュが合わない

    def test_custom_mark_pattern(self):
        self.write("bridge/bridge.toml", CONFIG + '[manuscript]\nmark_pattern = \'\\[\\^(c\\d+)\\]\'\n')
        self.write("manuscript.md", MANUSCRIPT.replace("〔c001〕", "[^c001]"))
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("未承認 1", out)


if __name__ == "__main__":
    unittest.main()
