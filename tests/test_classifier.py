# -*- coding: utf-8 -*-
"""分類器による検査（classify）の試験。外へは送らず、手元の偽のサーバに Jev の API の形で答えさせる。

実行:  python -m unittest discover -s tests
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import test_bridge as tb

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge import classifier as cl  # noqa: E402

# 問いの文面に含まれる語 -> 偽のサーバが選ぶラベル
SCRIPT = {"どれに当たるか": "外挿", "どの強さ": "観察", "誰の主張": "他者の紹介", "書かれているか": "書かれていない"}


class FakeJev(BaseHTTPRequestHandler):
    log = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        type(self).log.append({"auth": self.headers.get("Authorization"), "body": body})
        answers = {}
        for qid, q in body["questions"].items():
            want = next((v for k, v in SCRIPT.items() if k in q["instructions"]), None)
            probs = {}
            for key, desc in q["criteria"].items():
                probs[key] = 0.9 if want and desc.startswith(want) else 0.05
            answers[qid] = {"probabilities": probs}
        out = json.dumps({"answers": answers, "usage": {"input_tokens": 1}}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):  # 標準エラーへ出さない
        pass


class ClassifierTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeJev)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeJev.log.clear()
        tb.BridgeTest.setUp(self)
        conf = tb.CONFIG + (f'[classifier]\nprovider = "jev"\nmodel = "jev-test"\n'
                            f'endpoint = "http://127.0.0.1:{self.port}/v1/systemone"\n')
        self.write("bridge/bridge.toml", conf)
        self.run_bridge("derive")

    def tearDown(self):
        def writable(func, path, _exc):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(self.dir, onerror=writable)

    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def run_bridge(self, *args, key="test-key"):
        env = self.clean_env()
        env.pop("TYPESAFE_API_KEY", None)
        env.pop("JEV_API_KEY", None)
        if key:
            env["TYPESAFE_API_KEY"] = key
        r = subprocess.run([sys.executable, "-X", "utf8", str(tb.BRIDGE), *args], cwd=self.dir,
                           capture_output=True, text=True, encoding="utf-8", env=env)
        return r.returncode, r.stdout + r.stderr

    def ledger(self):
        p = self.dir / "bridge/judgments.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    # ---- 送る前

    def test_without_send_nothing_leaves(self):
        code, out = self.run_bridge("classify")
        self.assertEqual(code, 0, out)
        self.assertIn("送るには --send を付ける", out)
        self.assertIn("要求 4 回、問い 8 件", out)
        self.assertEqual(FakeJev.log, [])
        self.assertEqual(self.ledger(), [])

    def test_no_key_sends_nothing_and_writes_nothing(self):
        code, out = self.run_bridge("classify", "--send", key="")
        self.assertEqual(code, 1)
        self.assertIn("鍵が無い", out)
        self.assertEqual(FakeJev.log, [])
        self.assertEqual(self.ledger(), [])

    # ---- 送る

    def test_send_writes_ledger_and_flags_disagreements(self):
        code, out = self.run_bridge("classify", "--send")
        self.assertEqual(code, 0, out)
        led = {(e["item"], e["type"]): e for e in self.ledger()}
        self.assertEqual(len(led), 8)
        d = led[("cite:c001", "cite.diff")]
        self.assertEqual((d["label"], d["record"], d["status"]), ("外挿", ["一致"], "食い違い"))
        self.assertEqual(led[("cite:c001", "cite.strength")]["status"], "一致")
        self.assertEqual(led[("exc:doe2020#e1", "cite.attribution")]["status"], "要確認")
        self.assertEqual(led[("exc:doe2020#e1", "cite.not_said")]["status"], "問題なし")
        self.assertEqual(d["provider"], "jev")
        self.assertEqual(d["model"], "jev-test")
        # 要求の形。鍵、選択肢の番号、問いの文面、材料
        first = next(r for r in FakeJev.log if "本文の文" in r["body"]["state"])
        self.assertEqual(first["auth"], "Bearer test-key")
        self.assertEqual(first["body"]["model"], "jev-test")
        self.assertIn("[原典の逐語]", first["body"]["state"])
        qs = list(first["body"]["questions"].values())
        self.assertEqual([q["type"] for q in qs], ["choice", "choice"])
        self.assertTrue(qs[0]["criteria"]["1"].startswith("一致"))
        # 台帳の印が、一覧と check と review に出る
        out = self.run_bridge("classify", "--list")[1]
        self.assertIn("食い違い", out)
        self.assertIn("cite.diff", out)
        self.assertIn("分類器: 判定 8 件のうち印 4 件", self.run_bridge("check")[1])
        rows = json.loads(self.run_bridge("review", "--json", "--all")[1])["citations"][0]["classifier"]
        self.assertEqual({r["type"] for r in rows}, {"cite.diff", "cite.strength", "cite.attribution", "cite.not_said"})
        # 印を立てるだけで、承認の状態は変えない
        self.assertIn("未承認 1", self.run_bridge("check")[1])

    def test_fresh_judgments_are_not_asked_again_and_stale_ones_are(self):
        self.run_bridge("classify", "--send")
        n = len(FakeJev.log)
        code, out = self.run_bridge("classify", "--send")
        self.assertEqual(code, 0)
        self.assertIn("送る予定: 要求 0 回", out)
        self.assertEqual(len(FakeJev.log), n)
        # 本文が変われば、その引用の判定は古くなる
        self.write("manuscript.md", self.read("manuscript.md").replace("参加者は", "被験者は"))
        out = self.run_bridge("classify")[1]
        self.assertIn("要求 1 回", out)

    def test_wording_change_invalidates_judgments(self):
        self.run_bridge("classify", "--send")
        conf = self.read("bridge/bridge.toml") + (
            '[[checks]]\ntype = "cite.diff"\nversion = 1\nfor = "citation"\nquestion = "本文の文は、逐語のどれに当たるか。"\n'
            'labels = ["一致", "外挿", "判定できない"]\ncompare = "citation.原文との差"\n'
            '[checks.materials]\nclaim = "citation.sentence"\nsource = "excerpt.逐語"\n')
        self.write("bridge/bridge.toml", conf)
        out = self.run_bridge("classify")[1]
        self.assertIn("要求 1 回、問い 1 件", out)  # version を上げなくても、文面と選択肢が変われば判定し直す

    # ---- 型の登録

    def test_registry_is_validated(self):
        base = self.read("bridge/bridge.toml")
        bad = base + '[[checks]]\ntype = "x.y"\nversion = 1\nfor = "excerpt"\nquestion = "?"\nlabels = ["a", "判定できない"]\n' \
                     '[checks.materials]\nsource = "excerpt.逐語"\n'
        self.write("bridge/bridge.toml", bad)
        code, out = self.run_bridge("classify")
        self.assertNotEqual(code, 0)
        self.assertIn("compare か flag_on", out)
        bad2 = base + '[[checks]]\ntype = "x.y"\nversion = 1\nfor = "excerpt"\nquestion = "?"\nlabels = ["a", "判定できない"]\n' \
                      'flag_on = ["a"]\non_disagree = "downgrade"\n[checks.materials]\nsource = "excerpt.逐語"\n'
        self.write("bridge/bridge.toml", bad2)
        code, out = self.run_bridge("classify")
        self.assertNotEqual(code, 0)
        self.assertIn("on_disagree は flag だけ", out)

    def test_added_type_runs_and_is_recorded_in_the_manifest(self):
        extra = ('[[checks]]\ntype = "cite.tone"\nversion = 1\nfor = "excerpt"\nquestion = "逐語の語調はどれか。"\n'
                 'labels = ["断定", "留保", "判定できない"]\nflag_on = ["断定"]\n[checks.materials]\nsource = "excerpt.逐語"\n')
        self.write("bridge/bridge.toml", self.read("bridge/bridge.toml") + extra)
        out = self.run_bridge("classify")[1]
        self.assertIn("問い 11 件", out)  # 既定の八件に、抜き書き三件の新しい型が足される
        self.run_bridge("classify", "--send")
        self.assertEqual(self.run_bridge("approve", "c001", "--by", "tester")[0], 0)
        code, out = self.run_bridge("checkpoint")
        self.assertEqual(code, 0, out)
        m = json.loads(next((self.dir / "bridge/checkpoints").glob("*.json")).read_text(encoding="utf-8"))
        c = m["classifier"]
        self.assertEqual((c["provider"], c["model"]), ("jev", "jev-test"))
        self.assertIn("cite.tone", {t["type"] for t in c["types"]})
        self.assertIn("[[checks]]", c["note"])

    def test_manifest_has_no_classifier_when_unused(self):
        self.write("bridge/bridge.toml", tb.CONFIG)
        self.run_bridge("approve", "c001", "--by", "tester")
        self.assertEqual(self.run_bridge("checkpoint")[0], 0)
        m = json.loads(next((self.dir / "bridge/checkpoints").glob("*.json")).read_text(encoding="utf-8"))
        self.assertIsNone(m["classifier"])


class AdapterTest(unittest.TestCase):
    """アダプタの契約。要求の形と応答の読み方。"""

    ASKS = [cl.Ask(type="t.a", labels=("甲", "乙", "判定できない"), question="どれか。 {about}",
                   gloss=(("甲", "こう"),), about="対象の文")]

    def test_payload(self):
        p = cl.jev_payload("m", "state", self.ASKS)
        q = p["questions"]["q1"]
        self.assertEqual(p["state"], "state")
        self.assertEqual(q["type"], "choice")
        self.assertEqual(q["instructions"], "どれか。 対象の文")
        self.assertEqual(q["criteria"], {"1": "甲：こう", "2": "乙", "3": "判定できない"})

    def test_parse_picks_highest_and_ties_keep_order(self):
        v = cl.jev_parse({"answers": {"q1": {"probabilities": {"1": 0.2, "2": 0.5, "3": 0.5}}}}, self.ASKS)[0]
        self.assertEqual(v.label, "乙")
        self.assertEqual(v.score, 0.5)

    def test_parse_unusable_answer_is_none(self):
        self.assertEqual(cl.jev_parse({"answers": {"q1": {"probabilities": {"9": 1.0, "x": 0.1}}}}, self.ASKS), [None])
        with self.assertRaises(cl.ClassifierUnavailable):
            cl.jev_parse({"nope": 1}, self.ASKS)

    def test_unknown_provider_is_refused_and_none_means_unused(self):
        self.assertIsNone(cl.make_classifier({}))
        with self.assertRaises(ValueError):
            cl.make_classifier({"provider": "nope"})

    def test_base_classifier_judges_nothing(self):
        self.assertEqual(cl.Classifier().classify("s", self.ASKS), [None])


if __name__ == "__main__":
    unittest.main()
