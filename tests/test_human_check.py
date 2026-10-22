# -*- coding: utf-8 -*-
"""要ヒューマンチェックと原本での確認の記録（設計 §5.10）の試験。一時フォルダに小さな一式を作って動かす。

実行:  python -m pytest -q tests/test_human_check.py
"""
import datetime
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
from cite_bridge.manuscript import verbatim_fingerprint  # noqa: E402
from cite_bridge.propose import candidate_fp  # noqa: E402

TODAY = datetime.date.today().isoformat()
APPROVERS = '[approvers]\nhiatama = "human"\nreviewer-model = "model"\n'
BIB = tb.BIB + ("\nLee, K. (2019). Noise study. *Journal*, 3(1), 1–2.\nkey: noisy2020\n（PDF: `noisy2020.pdf`）\n"
                "\nKim, S. (2021). Scanned study. *Journal*, 2(1), 1–2.\nkey: ocr2020\n（PDF: `ocr2020.pdf`）\n")
OCR_TEXT = ("<!-- extract\npdf: ocr2020.pdf\nsha256: 0000\npages: 2\nocr_pages: 2\nextractor: pymupdf 1.28.2\n"
            "extracted: 2026-10-22\n-->\n"
            "The first page has ordinary words of the study and the data.\fPage two verbatim OCR sentence here for the test.\n")
OCR_SENTENCE = "Page two verbatim OCR sentence here for the test."
NOISY_TEXT = "The grids are � faster in noisy rooms. Other words of the study here.\n"
NOISY_SENTENCE = "The grids are � faster in noisy rooms."
MANUSCRIPT = "# 本文\n\n第二頁では、Page two verbatim OCR sentence here for the test.\n"
CITATIONS_HEAD = "# 引用\n対象: manuscript.md\n"


def excerpt(key, eid, verbatim, writer="test", extra=""):
    """抜き書きのファイル（1 件）。extra は確認の記録などの行。"""
    return (f"# {key}\n\n## {eid}\n逐語: {verbatim}\n強さ: 観察\n要約: 要約。\n言っていないこと: なし。\n"
            f"記入: {writer}\n{extra}")


class HumanCheckTest(unittest.TestCase):
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
        self.write("bridge/citations.md", CITATIONS_HEAD)
        self.write("manuscript.md", MANUSCRIPT)

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

    def set_approvers(self):
        self.write("bridge/bridge.toml", tb.CONFIG + APPROVERS)

    def ocr_record(self, value, verbatim=OCR_SENTENCE, writer="test"):
        """ocr2020#e1 に、原本での確認の記録（値と指紋）を書く。"""
        fp = verbatim_fingerprint(verbatim)
        self.write("bridge/excerpts/ocr2020.md",
                   excerpt("ocr2020", "e1", verbatim, writer, f"原本での確認: {value}\n@原本での確認時の指紋: {fp}\n"))

    # ---- §5.1・§5.3（印と NOTE）

    def test_derive_marks_and_check_notes(self):  # §5.10 の 1
        self.assertEqual(self.run_bridge("derive")[0], 0)
        self.assertIn("@要ヒューマンチェック: OCR の文字の層（PDF 2頁目）", self.read("bridge/excerpts/ocr2020.md"))
        self.assertIn("@要ヒューマンチェック: 逐語の範囲に読めない字", self.read("bridge/excerpts/noisy2020.md"))
        self.assertNotIn("要ヒューマンチェック", self.read("bridge/excerpts/doe2020.md"))  # 印の無い抜き書きには付かない
        code, out = self.run_bridge("check")
        self.assertEqual(code, 0, out)
        self.assertIn("ocr2020#e1: 要ヒューマンチェック（OCR の文字の層（PDF 2頁目））。原本での確認が無い", out)
        self.assertIn("要ヒューマンチェック: 印のある抜き書き 2 件のうち、確認済 0（人 0、モデル 0）、残り 2", out)
        self.assertEqual(self.run_bridge("check", "--strict")[0], 1)

    def test_derive_marks_exact_match_in_ocr_layer(self):  # §5.10 の 1（完全一致でも印が付く）
        self.run_bridge("derive")
        self.assertIn("@照合: 一致", self.read("bridge/excerpts/ocr2020.md"))
        self.assertIn("@要ヒューマンチェック: OCR の文字の層（PDF 2頁目）", self.read("bridge/excerpts/ocr2020.md"))

    def test_readable_characters_reason(self):  # §5.10 の 9
        self.run_bridge("derive")
        self.assertIn("@要ヒューマンチェック: 逐語の範囲に読めない字", self.read("bridge/excerpts/noisy2020.md"))

    # ---- §5.4・§5.2（記録と有効な確認）

    def test_confirm_source_clears_note_and_changed_verbatim_returns(self):  # §5.10 の 2
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "tester")[0], 0)
        self.assertIn(f"原本での確認: tester {TODAY} 一致", self.read("bridge/excerpts/ocr2020.md"))
        self.assertIn("@要ヒューマンチェック: OCR の文字の層", self.read("bridge/excerpts/ocr2020.md"))  # 印は残る（§5.1）
        code, out = self.run_bridge("check")
        self.assertNotIn("ocr2020#e1: 要ヒューマンチェック", out)
        self.assertIn("確認済 1（人 0、モデル 0）", out)
        self.write("bridge/excerpts/ocr2020.md", self.read("bridge/excerpts/ocr2020.md").replace("Page two verbatim", "page two verbatim"))
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertIn("ocr2020#e1: 要ヒューマンチェック（OCR の文字の層（PDF 2頁目））。確かめた後に逐語が変わった", out)

    def test_source_check_form_and_approver_rules(self):  # §5.10 の 3
        self.set_approvers()
        self.ocr_record("2026-10-10 p.49 ユーザ（古い記録）")  # 0.2.0 までの自由文
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertIn("原本での確認の記録が今の形でない", out)
        # 承認者の一覧に無い名前は書けない
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "someone")[0], 1)
        # 違う は、メモ（原本の字）が無ければ書けない
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "hiatama", "--result", "違う")[0], 1)
        # 一覧の人が確かめて一致と記録すると、古い記録は「前の記録」としてメモに残り、確認が有効になる
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "hiatama", "--page", "p.2")[0], 0)
        self.assertIn("前の記録: 2026-10-10 p.49 ユーザ", self.read("bridge/excerpts/ocr2020.md"))
        code, out = self.run_bridge("check")
        self.assertNotIn("ocr2020#e1: 要ヒューマンチェック", out)
        # 違う と記録されたものは有効でない
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "hiatama", "--result", "違う",
                                         "--note", "原本は page two")[0], 0)
        code, out = self.run_bridge("check")
        self.assertIn("ocr2020#e1: 要ヒューマンチェック（OCR の文字の層（PDF 2頁目））。原本と違うと報告された。逐語を直して確かめ直す（confirm --source か review --html で記録する）", out)

    def test_unknown_checker_is_note(self):  # §5.10 の 3（確認者が一覧に無い）
        self.set_approvers()
        self.ocr_record(f"someone {TODAY} 一致")
        self.run_bridge("derive")
        self.assertIn("確認者 'someone' が承認者の一覧に無い", self.run_bridge("check")[1])

    # ---- §5.8（書き手と確認者を分ける）

    def test_model_writer_cannot_record_own_text(self):  # §5.10 の 4
        self.set_approvers()
        self.write("bridge/excerpts/ocr2020.md", excerpt("ocr2020", "e1", OCR_SENTENCE, writer="reviewer-model"))
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "reviewer-model")[0], 1)
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--by", "reviewer-model")[0], 1)  # 要約の確認も断る
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "hiatama")[0], 0)  # 人は書ける

    def test_model_record_on_own_text_is_not_counted(self):  # §5.10 の 4（記録が手で書かれていた場合）
        self.set_approvers()
        self.ocr_record(f"reviewer-model {TODAY} 一致", writer="reviewer-model")
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertIn("書き手と同じモデル 'reviewer-model' の確認は数えない", out)
        self.assertNotIn("確認済 1", out)

    def test_model_approval_of_own_citation_is_not_counted(self):  # §5.8 の 3
        self.set_approvers()
        self.write("manuscript.md", MANUSCRIPT.replace("for the test.", "for the test.〔c001〕"))
        self.write("bridge/citations.md", CITATIONS_HEAD + "\n## c001\n種類: 主張\n抜き書き: ocr2020#e1\n理由: 試験\n"
                   "原文との差: 一致\n記入: reviewer-model\n承認: 未\n")
        self.write("bridge/excerpts/ocr2020.md", excerpt("ocr2020", "e1", OCR_SENTENCE, writer="hiatama"))
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "reviewer-model")[0], 1)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "hiatama")[0], 0)
        self.assertIn("承認済 1", self.run_bridge("check")[1])
        # 手で書かれた model の承認は、書き手と同じなら数えない
        self.write("bridge/citations.md", self.read("bridge/citations.md").replace("承認: hiatama", "承認: reviewer-model"))
        code, out = self.run_bridge("check")
        self.assertIn("承認を数えない（書き手と同じモデル 'reviewer-model' の確認は数えない）", out)

    def test_candidate_acceptance_refused_for_model_writer(self):  # §5.8 の 3（候補の受け入れ）
        self.set_approvers()
        cand = {"status": "pending", "kind": "主張", "key": "doe2020", "excerpts": [], "記入": "reviewer-model",
                "理由": "試験"}
        self.write("bridge/candidates/candidates.json", json.dumps(
            {"format": "cite-bridge-candidates/1", "items": {"qtest001": cand}}, ensure_ascii=False))
        decisions = {"format": "cite-bridge-decisions/1", "manuscript": "manuscript.md", "generated": "x",
                     "by": "reviewer-model", "saved": "2026-10-22T10:00:00", "decisions": [], "confirms": [],
                     "candidates": [{"id": "qtest001", "action": "accept", "note": "", "cfp": candidate_fp(cand)}]}
        self.write("decisions.json", json.dumps(decisions, ensure_ascii=False))
        code, out = self.run_bridge("apply", "decisions.json")
        self.assertEqual(code, 1, out)
        self.assertIn("SKIP qtest001: 書き手と同じモデル 'reviewer-model' の確認は数えない", out)

    # ---- §5.4 の 2（判断ファイル）

    def test_apply_writes_source_checks_and_skips_changed_verbatim(self):  # §5.10 の 5
        self.run_bridge("derive")
        decisions = {"format": "cite-bridge-decisions/1", "manuscript": "manuscript.md", "generated": "x",
                     "by": "tester", "saved": "2026-10-22T10:00:00", "decisions": [], "candidates": [], "confirms": [],
                     "source_checks": [
                         {"id": "ocr2020#e1", "fingerprint": verbatim_fingerprint(OCR_SENTENCE), "result": "一致",
                          "page": "p.2", "note": ""},
                         {"id": "noisy2020#e1", "fingerprint": "00000000", "result": "一致", "page": "", "note": ""}]}
        self.write("decisions.json", json.dumps(decisions, ensure_ascii=False))
        code, out = self.run_bridge("apply", "decisions.json")
        self.assertEqual(code, 1, out)  # 指紋が合わないものは書かず、理由を出す
        self.assertIn("SKIP noisy2020#e1: 確かめた後に逐語が変わった", out)
        self.assertIn(f"原本での確認: tester {TODAY} 一致 p.2", self.read("bridge/excerpts/ocr2020.md"))
        self.assertNotIn("原本での確認", self.read("bridge/excerpts/noisy2020.md"))
        self.assertNotIn("ocr2020#e1: 要ヒューマンチェック", self.run_bridge("check")[1])

    # ---- §5.6（マニフェスト）

    def test_checkpoint_by_requires_human_when_approvers_exist(self):  # §5.10 の 8
        self.set_approvers()
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("checkpoint")[0], 1)  # --by が無い
        self.assertIn("--by", self.run_bridge("checkpoint")[1])
        self.assertEqual(self.run_bridge("checkpoint", "--by", "reviewer-model")[0], 1)  # model は提出できない
        self.assertIn("human", self.run_bridge("checkpoint", "--by", "reviewer-model")[1])
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "hiatama")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "noisy2020#e1", "--source", "--by", "hiatama")[0], 0)
        self.run_bridge("derive")
        code, out = self.run_bridge("checkpoint", "--by", "hiatama")
        self.assertEqual(code, 0, out)
        manifest = json.loads(next((self.dir / "bridge/checkpoints").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(manifest["by"], "hiatama")
        self.assertEqual(manifest["source_checks"]["done"], 2)
        self.assertEqual(manifest["source_checks"]["by_kind"], {"human": 2, "model": 0})


if __name__ == "__main__":
    unittest.main()
