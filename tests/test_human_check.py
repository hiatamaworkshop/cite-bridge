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

    def test_short_verbatim_boundaries(self):  # C20。欧文 3 語以下、和文 10 字以下（空白を除く）
        from cite_bridge.derive import is_short_verbatim
        self.assertTrue(is_short_verbatim("the"))
        self.assertTrue(is_short_verbatim("grids over lists"))
        self.assertFalse(is_short_verbatim("prefer grids over lists"))
        self.assertTrue(is_short_verbatim("しかしながら状況は改"))  # 10 字
        self.assertFalse(is_short_verbatim("しかしながら状況は改善"))  # 11 字
        self.assertTrue(is_short_verbatim("音声 は 不利 な Web"))  # 和文の字を含めば字数で数える（9 字）

    def test_short_verbatim_needs_source_check(self):  # C20。照合が一致しても、短い逐語は所在を保証しない
        self.write("bridge/excerpts/doe2020.md", excerpt("doe2020", "e1", "grids over lists")
                   + "\n" + excerpt("doe2020", "e2", "prefer grids over lists").split("\n", 2)[2])
        self.run_bridge("derive")
        ex = self.read("bridge/excerpts/doe2020.md")
        e1, e2 = ex.split("## e2")
        self.assertIn("@照合: 一致", e1)
        self.assertIn("@要ヒューマンチェック: 逐語が短い", e1)
        self.assertNotIn("要ヒューマンチェック", e2)
        code, out = self.run_bridge("check")
        self.assertIn("doe2020#e1: 要ヒューマンチェック（逐語が短い）。原本での確認が無い", out)
        self.assertEqual(self.run_bridge("confirm", "doe2020#e1", "--source", "--by", "tester")[0], 0)
        self.assertNotIn("doe2020#e1: 要ヒューマンチェック", self.run_bridge("check")[1])

    def test_names_are_compared_after_normalizing(self):  # C20。NFKC・大小文字・前後の空白
        from cite_bridge.manuscript import same_name
        self.assertTrue(same_name("Claude", "claude"))
        self.assertTrue(same_name(" ｒｅｖｉｅｗｅｒ-Model ", "reviewer-model"))
        self.assertFalse(same_name("reviewer-model", "reviewer-model2"))
        # 書き手を大文字で書いた抜き書きでも、同じモデルの原本での確認は断る
        self.set_approvers()
        self.write("bridge/excerpts/ocr2020.md", excerpt("ocr2020", "e1", OCR_SENTENCE, writer="Reviewer-Model"))
        self.run_bridge("derive")
        code, out = self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "reviewer-model")
        self.assertEqual(code, 1, out)
        self.assertIn("書き手と同じモデル 'reviewer-model' の確認は数えない", out)

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

    # ---- C41（書き手と確認者・承認者の独立を系統で見る）

    FAMILIES = ('[approvers]\nhiatama = "human"\nwriter-a = "model:anthropic"\nalias-a = "model:Anthropic"\n'
                'nofam = "model"\nother-o = "model:openai"\n')

    def set_families(self, writer):
        self.write("bridge/bridge.toml", tb.CONFIG + self.FAMILIES)
        self.write("bridge/excerpts/ocr2020.md", excerpt("ocr2020", "e1", OCR_SENTENCE, writer=writer))
        self.run_bridge("derive")

    def test_same_family_alias_is_not_independent(self):
        self.set_families("writer-a")
        for args in (("--source",), ()):  # 原本での確認と要約の確認
            code, out = self.run_bridge("confirm", "ocr2020#e1", *args, "--by", "alias-a")
            self.assertEqual(code, 1, out)
            self.assertIn("書き手 'writer-a' と同じ系統（Anthropic）の model 'alias-a' の確認は数えない", out)
        # 手で書かれた記録も数えない
        self.ocr_record(f"alias-a {TODAY} 一致", writer="writer-a")
        self.run_bridge("derive")
        code, out = self.run_bridge("check")
        self.assertIn("同じ系統（Anthropic）の model 'alias-a' の確認は数えない", out)
        self.assertNotIn("確認済 1", out)

    def test_model_without_family_is_not_independent(self):
        self.set_families("hiatama")
        code, out = self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "nofam")
        self.assertEqual(code, 1, out)
        self.assertIn("model 'nofam' の系統が承認者の一覧に無いので、書き手と独立か分からない", out)

    def test_writer_not_in_list_is_not_independent(self):
        self.set_families("stranger")
        code, out = self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "other-o")
        self.assertEqual(code, 1, out)
        self.assertIn("書き手 'stranger' が承認者の一覧に無いので、model 'other-o' と独立か分からない", out)
        self.write("bridge/bridge.toml", tb.CONFIG + self.FAMILIES.replace('nofam = "model"', 'stranger = "model"'))
        code, out = self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "other-o")
        self.assertIn("書き手 'stranger' の系統が承認者の一覧に無いので", out)

    def test_other_family_and_human_are_independent(self):
        self.set_families("writer-a")
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "other-o")[0], 0)
        code, out = self.run_bridge("check")
        self.assertIn("確認済 1（人 0、モデル 1）", out)
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "hiatama")[0], 0)  # 人は書き手を問わない
        self.assertIn("確認済 1（人 1、モデル 0）", self.run_bridge("check")[1])
        self.set_families("hiatama")  # 書き手が人なら、系統のある model は独立
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "alias-a")[0], 0)

    def test_citation_approval_looks_at_evidence_writers(self):
        self.set_families("writer-a")  # 根拠の抜き書きの書き手が writer-a
        self.write("manuscript.md", MANUSCRIPT.replace("for the test.", "for the test.〔c001〕"))
        self.write("bridge/citations.md", CITATIONS_HEAD + "\n## c001\n種類: 主張\n抜き書き: ocr2020#e1\n理由: 試験\n"
                   "原文との差: 一致\n記入: hiatama\n承認: 未\n")
        code, out = self.run_bridge("approve", "c001", "--by", "alias-a")
        self.assertEqual(code, 1, out)
        self.assertIn("書き手 'writer-a' と同じ系統（Anthropic）の model 'alias-a' の確認は数えない", out)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "hiatama")[0], 0)
        self.write("bridge/citations.md", self.read("bridge/citations.md").replace("承認: hiatama", "承認: alias-a"))
        code, out = self.run_bridge("check")
        self.assertIn("承認を数えない（書き手 'writer-a' と同じ系統（Anthropic）の model 'alias-a' の確認は数えない）", out)

    # ---- C42（model の承認を数えるかを設定で選ぶ）

    def set_count_model(self, value):
        """書き手が人（引用）と writer-a（根拠の抜き書き）の c001 を置き、approval.count_model を value にする。"""
        self.set_families("writer-a")
        self.write("bridge/bridge.toml", tb.CONFIG + self.FAMILIES + f"[approval]\ncount_model = {value}\n")
        self.write("manuscript.md", MANUSCRIPT.replace("for the test.", "for the test.〔c001〕"))
        self.write("bridge/citations.md", CITATIONS_HEAD + "\n## c001\n種類: 主張\n抜き書き: ocr2020#e1\n理由: 試験\n"
                   "原文との差: 一致\n記入: hiatama\n承認: 未\n")

    def test_count_model_false_keeps_model_approval_pending(self):
        self.set_count_model("false")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "other-o")[0], 0)
        code, out = self.run_bridge("check")
        self.assertIn("承認を数えない（model 'other-o' の承認は記録に残るが、承認済には人（human）の承認が要る）", out)
        self.assertIn("引用: 主張 承認済 0 /", out)

    def test_count_model_true_counts_independent_model(self):
        self.set_count_model("true")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "other-o")[0], 0)
        code, out = self.run_bridge("check")
        self.assertNotIn("承認を数えない", out)
        self.assertIn("引用: 主張 承認済 1（model openai 1） /", out)
        c = json.loads(self.run_bridge("review", "--json", "--all")[1])["citations"][0]
        self.assertEqual((c["state"], c["approved_by"], c["model_approval"]),
                         ("承認済", {"by": "other-o", "kind": "model", "family": "openai"}, None))
        self.assertIn("## c001　承認済（other-o・model openai）", self.run_bridge("review", "--all")[1])

    def test_count_model_true_still_refuses_same_family(self):
        self.set_count_model("true")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "alias-a")[0], 1)  # 根拠の書き手 writer-a と同じ系統
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "hiatama")[0], 0)
        self.write("bridge/citations.md", self.read("bridge/citations.md").replace("承認: hiatama", "承認: alias-a"))
        code, out = self.run_bridge("check")
        self.assertIn("承認を数えない（書き手 'writer-a' と同じ系統（Anthropic）の model 'alias-a' の確認は数えない）", out)
        self.assertIn("引用: 主張 承認済 0 /", out)

    def test_count_model_true_does_not_replace_human_approval(self):
        self.set_count_model("true")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "hiatama")[0], 0)
        code, out = self.run_bridge("approve", "c001", "--by", "other-o")
        self.assertEqual(code, 1, out)
        self.assertIn("'hiatama' の承認が今と合うので、model 'other-o' の承認で書き換えない", out)
        self.assertIn("引用: 主張 承認済 1（人 1） /", self.run_bridge("check")[1])

    # ---- C43（マニフェストの decided_by）

    def decided_by(self):
        """一時フォルダの一式で run_check を走らせ、decided_by を返す（数えない記録があると checkpoint は書かれないため）。"""
        code = ("import json, sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]);"
                "from cite_bridge import config as cfg; cfg.load_config(Path('bridge/bridge.toml'));"
                "from cite_bridge.check import run_check; print(json.dumps(run_check()['decided_by']))")
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, str(tb.BRIDGE.parent)], cwd=self.dir,
                           capture_output=True, text=True, encoding="utf-8", env=tb.BridgeTest.clean_env())
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_decided_by_counts_who_judged(self):
        from cite_bridge.manuscript import summary_fingerprint
        self.set_count_model("true")  # c001 の書き手は hiatama、根拠 ocr2020#e1 の書き手は writer-a
        self.write("manuscript.md", self.read("manuscript.md") + "\n二つ目の文である。〔c002〕\n")
        self.write("bridge/citations.md", self.read("bridge/citations.md")
                   + "\n## c002\n種類: 主張\n抜き書き: ocr2020#e1\n理由: 試験\n原文との差: 一致\n記入: hiatama\n承認: 未\n")
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "other-o")[0], 0)
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--by", "hiatama")[0], 0)
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "other-o")[0], 0)
        self.assertEqual(self.run_bridge("approve", "c002", "--by", "hiatama")[0], 0)
        cit = self.read("bridge/citations.md")
        i = cit.index("## c002")
        self.write("bridge/citations.md", cit[:i] + cit[i:].replace("承認: hiatama", "承認: alias-a"))  # 同じ系統の手書きの承認
        # 一覧に無い書き手（test）の抜き書きへの、手書きの要約の確認
        noisy = self.read("bridge/excerpts/noisy2020.md")
        fields = {"逐語": NOISY_SENTENCE, "強さ": "観察", "要約": "要約。", "言っていないこと": "なし。"}
        self.write("bridge/excerpts/noisy2020.md", noisy.rstrip("\n")
                   + f"\n要約の確認: alias-a {TODAY}\n@要約の確認時の指紋: {summary_fingerprint(fields)}\n")
        self.run_bridge("derive")
        self.assertEqual(self.decided_by(), {
            "approvals": {"counted": {"model:openai": 1}, "uncounted": {"same_family": 1}},
            "source_checks": {"counted": {"model:openai": 1}, "uncounted": {}},
            "summary_checks": {"counted": {"human": 1}, "uncounted": {"unknown_writer": 1}}})
        self.write("bridge/bridge.toml", tb.CONFIG + self.FAMILIES + "[approval]\ncount_model = false\n")
        self.assertEqual(self.decided_by()["approvals"],
                         {"counted": {}, "uncounted": {"model_not_counted": 1, "same_family": 1}})

    def test_checkpoint_writes_decided_by(self):
        self.write("bridge/bridge.toml", tb.CONFIG + APPROVERS)
        self.write("bridge/excerpts/ocr2020.md", excerpt("ocr2020", "e1", OCR_SENTENCE, writer="hiatama"))
        self.write("bridge/excerpts/noisy2020.md", "# noisy2020\n")
        self.run_bridge("derive")
        self.assertEqual(self.run_bridge("confirm", "ocr2020#e1", "--source", "--by", "hiatama")[0], 0)
        code, out = self.run_bridge("checkpoint", "--by", "hiatama")
        self.assertEqual(code, 0, out)
        manifest = json.loads(next((self.dir / "bridge/checkpoints").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(manifest["decided_by"]["source_checks"], {"counted": {"human": 1}, "uncounted": {}})
        self.assertEqual(self.run_bridge("checkpoint", "--by", "reviewer-model")[0], 1)  # 提出は今と同じに人だけ

    def test_count_model_must_be_boolean(self):
        self.write("bridge/bridge.toml", tb.CONFIG + '[approval]\ncount_model = "yes"\n')
        code, out = self.run_bridge("check")
        self.assertNotEqual(code, 0)
        self.assertIn("approval.count_model は true か false", out)

    def test_approver_kind_must_be_known_form(self):
        for bad in ('robot', 'model:', 'human:x'):
            self.write("bridge/bridge.toml", tb.CONFIG + f'[approvers]\nx = "{bad}"\n')
            code, out = self.run_bridge("check")
            self.assertNotEqual(code, 0, bad)
            self.assertIn("approvers の種類は human、model、model:<系統>", out)

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
