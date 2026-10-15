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
