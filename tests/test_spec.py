# -*- coding: utf-8 -*-
"""SPEC.md が、固める範囲（§11.1）の欄と形式を実装と食い違わずに書いているかの試験。

表（書く欄・記録の欄・英語の別名・値の語彙）は cite_bridge/config.py と突き合わせる。
道具が書く JSON（原本での確認の依頼・判断ファイルの答えの例・マニフェスト）は、一時フォルダの一式で書かせ、鍵が SPEC にあるかを見る。

実行:  python -m pytest -q tests/test_spec.py
"""
import hashlib
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
        self.assertEqual(tuple(ex["根拠の種類"].split(" / ")), cfg.EVIDENCE_KINDS)
        self.assertEqual(set(cfg.VALUE_ALIASES["根拠の種類"].values()), set(cfg.EVIDENCE_KINDS))
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


# §4 の「空白」の 29 字。SPEC の文と同じ並び
SPEC_WHITESPACE = ([chr(c) for c in range(0x09, 0x0E)] + [chr(c) for c in range(0x1C, 0x20)]
                   + [" ", "\x85", "\xa0", " "] + [chr(c) for c in range(0x2000, 0x200B)]
                   + [" ", " ", " ", " ", "　"])


def spec_string(v):
    """§4 の文だけに従って、指紋にかける前の文字列を作る（実装の関数を使わない）。"""
    def ws(s):
        return "".join(c for c in s if c not in SPEC_WHITESPACE)
    if v["kind"] == "verbatim":
        return ws(v["verbatim"])
    if v["kind"] == "sentence":
        return ws(v["sentence"])
    if v["kind"] == "evidence":
        s = "\n".join(f"{i}\t{ws(v['excerpts'][i])}" for i in sorted(v["excerpts"]))
        return s + ("\n人の読み\t" + ws(v["human_reading"]) if v["human_reading"] else "")
    # 不在の抜き書き（searched_terms のある例）は、逐語の代わりに探した語を使う
    s = "\n".join(ws(v.get("searched_terms") or v[n] if n == "verbatim" else v[n]) for n in ("verbatim", "strength", "summary", "not_said"))
    s += "\n孫引き\t" + ws(v["secondary_source"]) if v["secondary_source"] else ""
    s += "\n訳\t" + ws(v["translation"]) if v.get("translation") else ""
    return s + ("\n根拠の種類\t" + ws(v["evidence_kind"]) if v.get("evidence_kind", "文") != "文" else "")


class SpecFingerprintTest(unittest.TestCase):
    """§4 の指紋の定義と例が、実装と食い違わない（C45）。別の実装は §4 だけを読んで同じ指紋を出す。"""

    def setUp(self):
        self.vectors = json.loads(re.search(r"```json\n(.*?)\n```", section("## 4."), re.S).group(1))

    def test_whitespace_is_the_29_characters(self):
        self.assertEqual(len(SPEC_WHITESPACE), 29)
        self.assertEqual({chr(c) for c in range(sys.maxunicode + 1) if re.match(r"\s", chr(c))}, set(SPEC_WHITESPACE))
        for a, z in re.findall(r"U\+([0-9A-F]{4})(?:〜U\+([0-9A-F]{4}))?", section("## 4.").split("U+FEFF")[0]):
            for c in range(int(a, 16), int(z or a, 16) + 1):
                self.assertIn(chr(c), SPEC_WHITESPACE)

    def test_examples_follow_the_written_rules(self):
        self.assertEqual({v["kind"] for v in self.vectors}, {"verbatim", "sentence", "evidence", "summary"})
        for v in self.vectors:
            self.assertEqual(spec_string(v), v["string"], v)
            self.assertEqual(hashlib.sha1(v["string"].encode("utf-8")).hexdigest()[:8], v["fingerprint"], v)

    def test_examples_match_the_implementation(self):
        from cite_bridge.manuscript import evidence_hash, fingerprint, summary_fingerprint, verbatim_fingerprint
        for v in self.vectors:
            if v["kind"] == "verbatim":
                got = verbatim_fingerprint(v["verbatim"])
            elif v["kind"] == "sentence":
                got = fingerprint(v["sentence"])
            elif v["kind"] == "evidence":
                got = evidence_hash(list(v["excerpts"]), {i: {"逐語": t} for i, t in v["excerpts"].items()}, v["human_reading"])
            else:
                got = summary_fingerprint({"逐語": v["verbatim"], "探した語": v.get("searched_terms", ""), "強さ": v["strength"], "要約": v["summary"],
                                           "言っていないこと": v["not_said"], "孫引き": v["secondary_source"],
                                           "訳": v.get("translation", ""), "根拠の種類": v.get("evidence_kind", "")})
            self.assertEqual(got, v["fingerprint"], v)
        absent = [v for v in self.vectors if v.get("searched_terms")]
        self.assertEqual([(v["kind"], v["verbatim"]) for v in absent], [("summary", "")])  # 不在の抜き書きの例が一つある
        summaries = [v for v in self.vectors if v["kind"] == "summary" and not v.get("searched_terms")]
        # 訳だけの例と、孫引きと訳の両方の例がある（足す順を例で決める）
        both = {(bool(v["secondary_source"]), bool(v.get("translation"))) for v in summaries}
        self.assertEqual(both, {(False, False), (False, True), (True, False), (True, True)})
        # 根拠の種類は、文の例（欄の無い例と同じ指紋）と、文でない例がある
        plain = next(v for v in summaries if not v["secondary_source"] and not v.get("translation") and "evidence_kind" not in v)
        kinds = {v["evidence_kind"]: v["fingerprint"] for v in summaries if "evidence_kind" in v}
        self.assertEqual(kinds["文"], plain["fingerprint"])
        self.assertNotEqual(kinds["表"], plain["fingerprint"])

    def test_missing_excerpt_counts_as_empty_verbatim(self):
        from cite_bridge.manuscript import evidence_hash
        self.assertEqual(evidence_hash(["k#e1"], {}), hashlib.sha1("k#e1\t".encode("utf-8")).hexdigest()[:8])

    def test_value_alias_is_read_as_the_japanese_value(self):
        import tempfile
        from cite_bridge.blocks import parse_blocks
        from cite_bridge.manuscript import summary_fingerprint
        v = next(x for x in self.vectors if x["kind"] == "summary" and not x["secondary_source"] and x["verbatim"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "doe2020.md"
            p.write_text(f"# doe2020\n\n## e1\nverbatim: {v['verbatim']}\nstrength: observation\n"
                         f"summary: {v['summary']}\nnot_said: {v['not_said']}\n", encoding="utf-8")
            _, blocks = parse_blocks(p)
        self.assertEqual(summary_fingerprint(blocks[0]["fields"]), v["fingerprint"])


class SpecPublicationTest(unittest.TestCase):
    """§12 の公開物の ID と verbatim_sha256 の定義と例が、実装と食い違わない（C54）。別の実装は §12 と §4 だけを読んで同じ値を出す。"""

    def setUp(self):
        self.vectors = {v["kind"]: v for v in json.loads(re.search(r"```json\n(.*?)\n```", section("### 12.2"), re.S).group(1))}

    def test_identity_example_follows_the_written_rule_and_the_implementation(self):
        from test_publish import jcs  # §12.2 の文だけに従った直列化（実装の関数を使わない）
        from cite_bridge import publish
        v = self.vectors["identity"]
        self.assertEqual(set(v["object"]), {"format", "spec", "content", "records"})
        self.assertEqual(jcs(v["object"]), v["string"])
        self.assertEqual("sha256-" + hashlib.sha256(v["string"].encode("utf-8")).hexdigest(), v["id"])
        self.assertEqual(publish.canonical(v["object"]), v["string"])
        self.assertEqual(publish.publication_id({**v["object"], "tool": {"version": "x"}, "publication": {"published_by": "y"}}), v["id"])
        # 例は、エスケープの要る字、ASCII でない字、null、整数、鍵の整列を含む
        for part in ('\\"', "信頼", "null", ":1", '{"content":'):
            self.assertIn(part, v["string"])
        self.assertEqual(v["object"]["format"], "cite-bridge-publication/1")
        self.assertEqual(v["object"]["spec"], publish.SPEC)

    def test_verbatim_sha256_example(self):
        from cite_bridge import publish
        v = self.vectors["verbatim_sha256"]
        self.assertEqual("".join(c for c in v["verbatim"] if c not in SPEC_WHITESPACE), v["string"])
        self.assertEqual(hashlib.sha256(v["string"].encode("utf-8")).hexdigest(), v["sha256"])
        self.assertEqual(publish.verbatim_sha256(v["verbatim"]), v["sha256"])

    def test_settings_keys_match(self):
        from cite_bridge import publish
        row = next(r for r in table_rows(section("## 9.")) if r[0] == "publication")
        self.assertEqual({k.strip() for k in row[1].split(",")}, publish.SETTINGS)


class ReadmeBlockTest(unittest.TestCase):
    """README の「AI に使わせるとき」の写すブロックが、道具の今のファイルとコマンドを指す（C30）。英語の版も同じ（C32）。"""
    READMES = {"README.md": "## AI に使わせるとき", "README.en.md": "## Using it with an AI agent"}

    def block(self, name):
        readme = (ROOT / name).read_text(encoding="utf-8")
        part = readme.split(self.READMES[name], 1)[1]
        return part.split("```markdown", 1)[1].split("```\n", 1)[0]

    def commands(self, text):
        return re.findall(r"python tools/cite-bridge/bridge\.py ([^`]+)`", text)

    def test_paths_and_commands_exist(self):
        import subprocess
        for name in self.READMES:
            with self.subTest(name):
                text = self.block(name)
                files = set(re.findall(r"tools/cite-bridge/([\w.]+\.md)", text))
                self.assertEqual(files, {"SKILL.md", "SPEC.md"})
                for f in files:
                    self.assertTrue((ROOT / f).is_file(), f)
                commands = self.commands(text)
                self.assertEqual(len(commands), 3)
                for c in commands:
                    r = subprocess.run([sys.executable, "-X", "utf8", str(tb.BRIDGE), *c.split(), "--help"],
                                       capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(r.returncode, 0, c + r.stderr)
                self.assertEqual([ln[:2] for ln in text.splitlines() if ln.startswith("- ")], ["- "] * 3)  # 三つだけ
        self.assertEqual(self.commands(self.block("README.en.md")), self.commands(self.block("README.md")))


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
