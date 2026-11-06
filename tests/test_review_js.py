# -*- coding: utf-8 -*-
"""承認の HTML の JavaScript（cite_bridge/templates/review.js）の試験。

画面に依らない部分（保存した入力の統合、古い判断の判定、判断ファイルの組み立て）を node で動かす。
画面（DOM）の部分は、document が無い環境では動かない作りにしてあり、ここでは動かさない。
node が無い環境では、この試験を飛ばす。

実行:  python -m unittest discover -s tests
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "cite_bridge" / "templates"
NODE = shutil.which("node")

HARNESS = r"""
const m = require(process.argv[2]);
const D = {manuscript: 'thesis/main.md', generated: '2026-10-15 10:00:00',
  citations: [
    {id: 'c001', fingerprint: 'fp1', evidence: 'ev1', excerpts: {'a#e1': 'sum1', 'a#e2': 'sum2'}},
    {id: 'c002', fingerprint: 'fp2', evidence: 'ev2', excerpts: {'b#e1': 'sum3'}},
    {id: 'q9', candidate: true, cfp: 'cf9', excerpts: {}},
  ],
  orphans: {'z#e7': 'sum7'}};
const byId = Object.fromEntries(D.citations.map(c => [c.id, c]));
const out = {};

// 保存した入力の統合。後のものが優先し、確認は足される。読めない入力は空になる
out.merge = m.mergeStored([
  JSON.stringify({by: 'old', decisions: {c001: {action: 'approve'}, c002: {action: 'send_back', note: 'x'}}, confirms: ['a#e1']}),
  null,
  JSON.stringify({by: 'new', foldDone: true, decisions: {c001: {action: 'send_back', note: 'y'}}, confirms: ['b#e1']}),
]);
out.mergeBroken = m.mergeStored(['{not json']);

// 判断した後に本文か根拠が変わったものは、戻さない
out.stale = [
  m.isStale({fingerprint: 'fp1', evidence: 'ev1'}, byId.c001),
  m.isStale({fingerprint: 'OLD', evidence: 'ev1'}, byId.c001),
  m.isStale({fingerprint: 'fp1', evidence: 'OLD'}, byId.c001),
  m.isStale({}, byId.c001),                      // 指紋を持たない古い入力は戻す
  m.isStale({cfp: 'cf9'}, byId.q9),
  m.isStale({cfp: 'OLD'}, byId.q9),
];

out.decisionCitation = m.makeDecision(byId.c001, 'approve', 'ok', '指摘');
out.decisionCandidate = m.makeDecision(byId.q9, 'accept', '', '');
out.missing = m.missingReasons({
  c001: {action: 'send_back', note: ''}, c002: {action: 'send_back', note: '理由'},
  q9: {cand: true, action: 'reject', note: ''}, c003: {action: 'approve', note: ''},
});

const s = {by: ' hiatama ', confirms: ['a#e2', 'z#e7', 'unknown#e9'], decisions: {
  c001: m.makeDecision(byId.c001, 'approve', '読んだ', ''),
  c002: m.makeDecision(byId.c002, '', '', 'ここが気になる'),          // 判断を保留にして指摘だけ書く
  q9: m.makeDecision(byId.q9, 'accept', '', ''),
}};
out.output = m.buildOutput(s, D, byId, '2026-10-15T01:00:00.000Z');
out.empty = m.buildOutput({by: 'x', confirms: [], decisions: {}}, D, byId, 't');
out.name = [m.downloadName('thesis_vcp_workingEdition.md'), m.downloadName('a b/c.md')];

// 原本での確認（要ヒューマンチェック）。違うはメモが要る。保存した指紋が今の逐語と違えば戻さない
out.srcMissing = m.missingSourceNotes({
  'a#e1': {result: '違う', note: ''}, 'a#e2': {result: '違う', note: '原本は page two'}, 'a#e3': {result: '一致', note: ''},
});
out.srcStale = [
  m.isStaleSource({fingerprint: 'x'}, 'x'),
  m.isStaleSource({fingerprint: 'x'}, 'y'),
  m.isStaleSource({}, undefined),
];
out.srcMerged = m.mergeStored([
  JSON.stringify({sources: {'a#e1': {result: '一致', fingerprint: 'v1'}}}),
  JSON.stringify({sources: {'a#e1': {result: '違う', note: 'n', fingerprint: 'v1'}}}),
]).sources;
out.srcOutput = m.buildOutput({by: 'hiatama', confirms: [], decisions: {}, sources: {
  'a#e1': {result: '一致', page: 'p.2', note: '', fingerprint: 'vfp1'},
  'a#e2': {result: '', page: '', note: '', fingerprint: 'vfp2'},  // 結果を選んでいないものは書かない
}}, D, byId, '2026-10-15T01:00:00.000Z');
// 要約の確認の印。印を付けた時の要約の指紋を持ち、今の指紋と違う印と、指紋を持たない前の形の印は戻さない
out.confirmFp = [m.summaryFp(D, 'a#e2'), m.summaryFp(D, 'z#e7'), m.summaryFp(D, 'unknown#e9') === undefined];
out.confirmStale = [
  m.isStaleConfirm({id: 'a#e1', fingerprint: 'sum1'}, m.summaryFp(D, 'a#e1')),
  m.isStaleConfirm({id: 'a#e1', fingerprint: 'OLD'}, m.summaryFp(D, 'a#e1')),   // 印の後に要約が変わった
  m.isStaleConfirm('a#e1', m.summaryFp(D, 'a#e1')),                            // 前の形（ID の文字列だけ）
  m.isStaleConfirm({id: 'unknown#e9', fingerprint: 'x'}, m.summaryFp(D, 'unknown#e9')),
];
out.confirmOutput = m.buildOutput({by: 'x', decisions: {}, confirms: [
  {id: 'a#e1', fingerprint: 'sum1'}, {id: 'unknown#e9', fingerprint: 'x'}]}, D, byId, 't').confirms;
out.srcOnly = m.buildOutput({by: 'x', confirms: [], decisions: {}, sources: {'a#e2': {result: '', fingerprint: 'vfp2'}}}, D, byId, 't');
console.log(JSON.stringify(out));
"""


@unittest.skipUnless(NODE, "node が無い")
class ReviewJsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp) / "harness.js"
            h.write_text(HARNESS, encoding="utf-8", newline="\n")
            r = subprocess.run([NODE, str(h), str(TEMPLATES / "review.js")], capture_output=True, text=True,
                               encoding="utf-8")
        assert r.returncode == 0, r.stderr
        cls.out = json.loads(r.stdout)

    def test_merge_stored_later_wins_and_confirms_accumulate(self):
        m = self.out["merge"]
        self.assertEqual(m["by"], "new")
        self.assertTrue(m["foldDone"])
        self.assertEqual(m["decisions"]["c001"], {"action": "send_back", "note": "y"})
        self.assertEqual(m["decisions"]["c002"]["action"], "send_back")
        self.assertEqual(m["confirms"], ["a#e1", "b#e1"])

    def test_merge_stored_unreadable_is_empty(self):
        self.assertEqual(self.out["mergeBroken"], {})

    def test_stale_decisions_are_not_restored(self):
        self.assertEqual(self.out["stale"], [False, True, True, False, False, True])

    def test_decision_carries_the_fingerprints_it_was_made_against(self):
        self.assertEqual(self.out["decisionCitation"], {"action": "approve", "note": "ok", "remark": "指摘",
                                                        "fingerprint": "fp1", "evidence": "ev1"})
        self.assertEqual(self.out["decisionCandidate"], {"cand": True, "action": "accept", "note": "", "cfp": "cf9"})

    def test_send_back_and_reject_need_a_reason(self):
        self.assertEqual(sorted(self.out["missing"]), ["c001", "q9"])

    def test_output_is_a_decisions_file(self):
        o = self.out["output"]
        self.assertEqual(o["format"], "cite-bridge-decisions/1")
        self.assertEqual(o["manuscript"], "thesis/main.md")
        self.assertEqual(o["by"], "hiatama")
        self.assertEqual(o["saved"], "2026-10-15T01:00:00.000Z")
        ids = {d["id"]: d for d in o["decisions"]}
        self.assertEqual(ids["c001"]["action"], "approve")
        self.assertEqual(ids["c001"]["fingerprint"], "fp1")
        # 判断を保留にして指摘だけ書いたものも、指摘として残る
        self.assertEqual(ids["c002"]["action"], "")
        self.assertEqual(ids["c002"]["remark"], "ここが気になる")
        self.assertEqual(o["candidates"], [{"id": "q9", "action": "accept", "note": "", "cfp": "cf9"}])
        # 要約の確認は、抜き書きの要約の指紋を持たせる。引用に使われていない抜き書き（orphans）も扱い、どちらにも無い ID は落とす
        self.assertEqual(o["confirms"], [{"id": "a#e2", "fingerprint": "sum2"}, {"id": "z#e7", "fingerprint": "sum7"}])

    def test_nothing_decided_gives_no_file(self):
        self.assertIsNone(self.out["empty"])

    def test_download_name(self):
        self.assertEqual(self.out["name"], ["decisions_thesis_vcp_workingEdition.json", "decisions_a_b_c.json"])

    def test_source_check_in_output_is_written_with_its_fingerprint(self):  # §5.10 の 7
        o = self.out["srcOutput"]
        self.assertEqual(o["source_checks"], [{"id": "a#e1", "fingerprint": "vfp1", "result": "一致", "page": "p.2", "note": ""}])
        self.assertEqual(o["decisions"], [])

    def test_source_check_only_unchosen_gives_no_file(self):
        self.assertIsNone(self.out["srcOnly"])

    def test_mismatch_result_without_memo_is_refused(self):  # §5.10 の 7（違うでメモの無いものは断る）
        self.assertEqual(self.out["srcMissing"], ["a#e1"])

    def test_source_check_saved_with_other_fingerprint_is_not_restored(self):  # §5.10 の 7
        self.assertEqual(self.out["srcStale"], [False, True, True])

    def test_merge_stored_keeps_sources_later_wins(self):
        self.assertEqual(self.out["srcMerged"]["a#e1"], {"result": "違う", "note": "n", "fingerprint": "v1"})

    def test_summary_fingerprint_comes_from_citations_or_orphans(self):
        self.assertEqual(self.out["confirmFp"], ["sum2", "sum7", True])

    def test_summary_confirm_with_other_or_no_fingerprint_is_not_restored(self):  # C11
        self.assertEqual(self.out["confirmStale"], [False, True, True, True])

    def test_summary_confirm_in_output_has_the_current_fingerprint(self):
        self.assertEqual(self.out["confirmOutput"], [{"id": "a#e1", "fingerprint": "sum1"}])

    def test_page_script_parses(self):
        """ひな形に差し込んだ後の HTML の script が、構文として読めること。"""
        html = (TEMPLATES / "review.html").read_text(encoding="utf-8")
        js = (TEMPLATES / "review.js").read_text(encoding="utf-8")
        page = html.replace("{{SCRIPT}}", js)
        scripts = re.findall(r"<script>\n(.*?)</script>", page, re.S)
        self.assertEqual(len(scripts), 1)
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "page.js"
            f.write_text(scripts[0], encoding="utf-8", newline="\n")
            r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
