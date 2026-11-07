# -*- coding: utf-8 -*-
"""始め方の案内（docs/getting-started.md）を、書いてあるとおりに通す試験（C31）。

一時フォルダに道具（tools/cite-bridge/）と例の一式（examples/first-citation/）を写し、案内を上から読む。
「`<パス>` を次の中身で作る:」の後の塊はそのファイルに書き、「期待する出力（終了コード N）:」の付いたコマンドは走らせて、
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
GUIDE = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")
STEP_RE = re.compile(
    r"`(?P<path>[^`]+)` を次の中身で作る[^\n]*:\n\n```markdown\n(?P<body>.*?)```"
    r"|```sh\n(?P<cmd>[^\n]*bridge\.py[^\n]*)\n```\n\n期待する出力（終了コード (?P<code>\d)）:\n\n```text\n(?P<expect>.*?)```",
    re.S)


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
        steps = list(STEP_RE.finditer(GUIDE))
        commands = [m for m in steps if m.group("cmd")]
        # bridge.py を打つ sh の塊は、どれも期待する出力を持ち、この試験で走る
        self.assertEqual(len(commands), len(re.findall(r"```sh\n[^`]*bridge\.py", GUIDE)))
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

    def test_example_files_are_listed(self):
        """案内の 0 の表が、例の一式のファイルをすべて挙げる。"""
        files = {p.relative_to(ROOT / "examples" / "first-citation").as_posix()
                 for p in (ROOT / "examples" / "first-citation").rglob("*") if p.is_file()}
        listed = set(re.findall(r"^\| `([^`]+)` \|", GUIDE, re.M))
        self.assertEqual(files, listed)


if __name__ == "__main__":
    unittest.main()
