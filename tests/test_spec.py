# -*- coding: utf-8 -*-
"""SPEC.md が、固める範囲（§11.1）の欄と形式を実装と食い違わずに書いているかの試験。

表（書く欄・記録の欄・英語の別名・値の語彙）は cite_bridge/config.py と突き合わせる。
道具が書く JSON（原本での確認の依頼・判断ファイルの答えの例・マニフェスト）は、一時フォルダの一式で書かせ、鍵が SPEC にあるかを見る。

実行:  python -m pytest -q tests/test_spec.py
"""
import json
import re
import sys
import unittest
from pathlib import Path

import test_bridge as tb

sys.path.insert(0, str(tb.BRIDGE.parent))
from cite_bridge import config as cfg  # noqa: E402

ROOT = tb.BRIDGE.parent
SPEC = (ROOT / "SPEC.md").read_text(encoding="utf-8")


def section(prefix):
    """見出しが prefix で始まる節の本文（次の ## か ### の見出しの手前まで）。"""
    lines = SPEC.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(prefix))
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"#{2,3} ", lines[i])), len(lines))
    return "\n".join(lines[start + 1:end])


def table_rows(text):
    """md の表の行を、欄の並びで返す（見出しと区切りの行は除く）。"""
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in text.splitlines() if ln.startswith("|")]
    return [r for r in rows[2:]]


def json_keys(text):
    return set(re.findall(r'"(\w+)":', text))


FROZEN_SECTIONS = ("### 2.1", "### 3.1")


class SpecTablesTest(unittest.TestCase):
    def written_fields(self):
        return {r[0] for p in FROZEN_SECTIONS for r in table_rows(section(p))}

    def test_record_fields_match(self):
        names = set(re.findall(r"`@([^`]+)`", section("### 2.3") + section("### 3.3")))
        self.assertEqual(names, cfg.RECORD_FIELDS)

    def test_required_excerpt_fields_match(self):
        required = [r[0] for r in table_rows(section("### 2.1")) if r[1] == "要"]
        self.assertEqual(required, cfg.EXC_REQUIRED)

    def test_value_vocabularies_match(self):
        ex = {r[0]: r[2] for r in table_rows(section("### 2.1"))}
        cit = {r[0]: r[2] for r in table_rows(section("### 3.1"))}
        self.assertEqual(set(ex["強さ"].split(" / ")), cfg.STRENGTHS)
        self.assertEqual(set(cit["原文との差"].split(" / ")), cfg.DIFFS)
        self.assertEqual(set(cit["種類"].split(" / ")), cfg.KINDS)

    def test_aliases_in_spec_match_and_cover_frozen_fields(self):
        """§10 の表の対はすべて実装と同じで、固める欄（書く欄・記録の欄・対象）はすべて表にある。"""
        pairs = {}
        for r in table_rows(section("## 10.")):
            for ja, en in ((r[0], r[1]), (r[2], r[3])):
                if ja:
                    pairs[ja] = en
        for ja, en in pairs.items():
            self.assertEqual(cfg.FIELD_ALIASES.get(en), ja, f"§10 の {ja} / {en}")
        frozen = self.written_fields() | cfg.RECORD_FIELDS | {"対象"}
        self.assertEqual(frozen - set(pairs), set())
        values = section("## 10.")
        for vals in cfg.VALUE_ALIASES.values():
            for en in vals:
                self.assertIn(en, values)
        self.assertIn("returned = 差し戻し", values)

    def test_format_names_match(self):
        code = set()
        for p in list((ROOT / "cite_bridge").rglob("*.py")) + list((ROOT / "cite_bridge" / "templates").glob("*")) + [tb.BRIDGE]:
            code |= set(re.findall(r"cite-bridge-[a-z-]+/\d+", p.read_text(encoding="utf-8")))
        self.assertEqual(set(re.findall(r"cite-bridge-[a-z-]+/\d+", SPEC)), code)


class ReadmeBlockTest(unittest.TestCase):
    """README の「AI に使わせるとき」の写すブロックが、道具の今のファイルとコマンドを指す（C30）。"""

    def block(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        part = readme.split("## AI に使わせるとき", 1)[1]
        return part.split("```markdown", 1)[1].split("```\n", 1)[0]

    def test_paths_and_commands_exist(self):
        text = self.block()
        files = set(re.findall(r"tools/cite-bridge/([\w.]+\.md)", text))
        self.assertEqual(files, {"SKILL.md", "SPEC.md"})
        for name in files:
            self.assertTrue((ROOT / name).is_file(), name)
        commands = re.findall(r"python tools/cite-bridge/bridge\.py ([^`]+)`", text)
        self.assertEqual(len(commands), 3)
        import subprocess
        for c in commands:
            r = subprocess.run([sys.executable, "-X", "utf8", str(tb.BRIDGE), *c.split(), "--help"],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, c + r.stderr)
        self.assertEqual([ln[:2] for ln in text.splitlines() if ln.startswith("- ")], ["- "] * 3)  # 三つだけ


class SpecJsonTest(unittest.TestCase):
    """道具が書く JSON の鍵が、SPEC の例にある。"""
    setUp = tb.BridgeTest.setUp
    tearDown = tb.BridgeTest.tearDown
    run_bridge = tb.BridgeTest.run_bridge
    read = tb.BridgeTest.read
    write = tb.BridgeTest.write
    clean_env = staticmethod(tb.BridgeTest.clean_env)

    def test_source_check_request_and_answer_example(self):
        short = "\n## e4\n逐語: grids over lists\n強さ: 観察\n要約: 格子。\n言っていないこと: なし。\n記入: test\n"
        self.write("bridge/excerpts/doe2020.md", tb.EXCERPTS + short)  # 逐語が短いので要ヒューマンチェックになる
        self.run_bridge("derive")
        code, out = self.run_bridge("review", "--source-checks", "--json", "-o", "req.json")
        self.assertEqual(code, 0, out)
        req = json.loads(self.read("req.json"))
        self.assertTrue(req["items"])
        documented = json_keys(section("### 5.1"))
        self.assertEqual(set(req) - documented, set())
        self.assertEqual(set(req["items"][0]) - documented, set())
        decisions = json_keys(section("## 5."))
        answer = req["answer_example"]
        self.assertEqual(set(answer) - decisions, set())
        self.assertEqual(set(answer["source_checks"][0]) - decisions, set())

    def test_manifest(self):
        self.run_bridge("derive")
        self.run_bridge("approve", "c001", "--by", "tester")
        code, out = self.run_bridge("checkpoint")
        self.assertEqual(code, 0, out)
        path = next((self.dir / "bridge/checkpoints").glob("*.json"))
        manifest = json.loads(path.read_text(encoding="utf-8"))
        documented = json_keys(section("## 8."))
        self.assertEqual(set(manifest) - documented, set())
        self.assertEqual(set(manifest["tool"]) - documented, set())
        self.assertEqual(manifest["tool"]["version"], cfg.TOOL_VERSION)
        self.assertIn(f'"version": "{cfg.TOOL_VERSION}"', section("## 8."))


if __name__ == "__main__":
    unittest.main()
