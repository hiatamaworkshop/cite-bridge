# -*- coding: utf-8 -*-
"""始め方の案内（docs/getting-started.md と英語の版 getting-started.en.md）を、書いてあるとおりに通す試験（C31、C32）。

一時フォルダに道具（tools/cite-bridge/）と例の一式（examples/first-citation/）を写し、案内を上から読む。
「`<パス>` を次の中身で作る:」（英語の版は「Create `<パス>` with the following content:」）の後の塊はそのファイルに書き、
「期待する出力（終了コード N）:」（Expected output (exit code N):）の付いたコマンドは走らせて、
終了コードと、期待する出力の各行が出力にあることを確かめる。

実行:  python -m pytest -q tests/test_getting_started.py
"""
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_bridge as tb

ROOT = tb.BRIDGE.parent


def step_re(make_file, expected):
    return re.compile(
        r"`(?P<path>[^`]+)` " + make_file + r"[^\n]*:\n\n```markdown\n(?P<body>.*?)```"
        r"|```sh\n(?P<cmd>[^\n]*bridge\.py[^\n]*)\n```\n\n" + expected + r":\n\n```text\n(?P<expect>.*?)```",
        re.S)


GUIDES = {
    "ja": ("getting-started.md", step_re("を次の中身で作る", r"期待する出力（終了コード (?P<code>\d)）")),
    "en": ("getting-started.en.md", step_re("with the following content", r"Expected output \(exit code (?P<code>\d)\)")),
}


def guide_text(lang):
    return (ROOT / "docs" / GUIDES[lang][0]).read_text(encoding="utf-8")


class GettingStartedTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        tool = self.dir / "tools" / "cite-bridge"
        tool.mkdir(parents=True)
        shutil.copy(tb.BRIDGE, tool / "bridge.py")
        shutil.copytree(ROOT / "cite_bridge", tool / "cite_bridge", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "examples" / "first-citation", self.dir, dirs_exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_every_command_runs_as_written(self):
        self.run_guide("ja")

    def test_english_guide_runs_as_written(self):
        self.run_guide("en")

    def run_guide(self, lang):
        guide = guide_text(lang)
        steps = list(GUIDES[lang][1].finditer(guide))
        commands = [m for m in steps if m.group("cmd")]
        # bridge.py を打つ sh の塊は、どれも期待する出力を持ち、この試験で走る
        self.assertEqual(len(commands), len(re.findall(r"```sh\n[^`]*bridge\.py", guide)))
        self.assertGreaterEqual(len(commands), 8)
        for m in steps:
            if m.group("path"):
                p = self.dir / m.group("path")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(m.group("body"), encoding="utf-8", newline="\n")
                continue
            args = shlex.split(m.group("cmd"))
            self.assertEqual(args[0], "python")
            r = subprocess.run([sys.executable, "-X", "utf8", *args[1:]], cwd=self.dir, capture_output=True, text=True,
                               encoding="utf-8", env=tb.BridgeTest.clean_env())
            out = r.stdout + r.stderr
            self.assertEqual(r.returncode, int(m.group("code")), f"{m.group('cmd')}\n{out}")
            for line in m.group("expect").splitlines():
                if line.strip():
                    self.assertIn(line, out, f"{m.group('cmd')} の出力に無い")

    def test_readme_example_matches_the_example_set(self):
        """README の「例」（日本語と英語）の塊は、案内で作るファイルの中身と同じで、承認の後に本文を直すと、書いてある check の行が出る（C38）。"""
        made = {m.group("path"): m.group("body") for m in GUIDES["ja"][1].finditer(guide_text("ja")) if m.group("path")}
        self.run_guide("ja")  # 承認と check --strict まで通す
        sentence = "話す入力は打つ入力より速いが"
        self.assertIn(sentence, (self.dir / "manuscript.md").read_text(encoding="utf-8"))
        (self.dir / "manuscript.md").write_text(made["manuscript.md"].replace(sentence, "話す入力は打つ入力より速く"),
                                                encoding="utf-8", newline="\n")
        r = subprocess.run([sys.executable, "-X", "utf8", "tools/cite-bridge/bridge.py", "check", "--strict"], cwd=self.dir,
                           capture_output=True, text=True, encoding="utf-8", env=tb.BridgeTest.clean_env())
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for name, head, after in (("README.md", "## 例\n", "\n## 始め方\n"), ("README.en.md", "## Example\n", "\n## Getting started\n")):
            part = (ROOT / name).read_text(encoding="utf-8").split(head, 1)[1].split(after, 1)[0]  # 塊の中の ## e1 では切らない
            manuscript, excerpt, citation = re.findall(r"```markdown\n(.*?)```", part, re.S)
            self.assertIn(manuscript, made["manuscript.md"], name)
            self.assertIn(excerpt, made["bridge/excerpts/tanaka2024.md"], name)
            self.assertIn(citation, made["bridge/citations.md"], name)
            for line in "".join(re.findall(r"```text\n(.*?)```", part, re.S)).splitlines():
                self.assertIn(line, r.stdout + r.stderr, name)

    def test_example_files_are_listed(self):
        """案内（日本語と英語）の 0 の表が、例の一式のファイルをすべて挙げる。"""
        files = {p.relative_to(ROOT / "examples" / "first-citation").as_posix()
                 for p in (ROOT / "examples" / "first-citation").rglob("*") if p.is_file()}
        for lang in GUIDES:
            listed = set(re.findall(r"^\| `([^`]+)` \|", guide_text(lang), re.M))
            self.assertEqual(files, listed, lang)

    def test_english_guide_has_the_same_steps(self):
        """英語の案内は、日本語の案内と同じファイルの中身、同じコマンド、同じ期待する出力を持つ。"""
        def steps(lang):
            return [(m.group("path"), m.group("body"), m.group("cmd"), m.group("code"), m.group("expect"))
                    for m in GUIDES[lang][1].finditer(guide_text(lang))]
        self.assertEqual(steps("en"), steps("ja"))


if __name__ == "__main__":
    unittest.main()
