# -*- coding: utf-8 -*-
"""英語の版（*.en.md）が、正本の日本語の版と食い違わないかの試験（C32）。

訳の文の正しさは見ない。見るのは、訳で落ちやすく、道具を使う人がそのまま打つもの:
- 頭に、正本が日本語であることと相手へのリンクがある
- 日本語の版の、欧字だけのインラインのコード（パス、欄の指し方、コマンド）が、英語の版にもある
- コマンドの名前（bridge.py の次の語）とオプション（--…）の集まりが同じ
- 囲みの塊のうち、道具が読み書きする JSON と、道具の出力（text）と、打つコマンド（sh）が同じ
- 相対のリンクが、ある文書を指す

実行:  python -m pytest -q tests/test_translations.py
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIRS = [("README.md", "README.en.md"), ("SPEC.md", "SPEC.en.md"), ("SKILL.md", "SKILL.en.md"),
         ("docs/getting-started.md", "docs/getting-started.en.md")]
FENCE_RE = re.compile(r"^```(\w*)\n(.*?)^```$", re.S | re.M)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def head(text):
    """最初の ## の見出しの手前まで。"""
    return text.split("\n## ", 1)[0]


def inline_code(text):
    """囲みの塊の外の、欧字だけのインラインのコード。"""
    return {c for c in re.findall(r"`([^`\n]+)`", FENCE_RE.sub("", text)) if c.isascii()}


def fences(text, *langs):
    return [body for lang, body in FENCE_RE.findall(text) if lang in langs]


def code(text):
    """インラインのコードと囲みの塊の中身。"""
    return "\n".join(re.findall(r"`([^`\n]+)`", FENCE_RE.sub("", text)) + [b for _, b in FENCE_RE.findall(text)])


def prose(text):
    """コードを除いた地の文。"""
    return re.sub(r"`[^`\n]+`", "", FENCE_RE.sub("", text))


def subcommands(text):
    return set(re.findall(r"bridge\.py (?:--citations <[^>]+> )?([a-z][\w-]*)", code(text)))


def options(text):
    return set(re.findall(r"(?<![\w-])--[a-z][\w-]*", text))


class TranslationTest(unittest.TestCase):
    def test_heads_point_to_each_other(self):
        for ja, en in PAIRS:
            with self.subTest(ja):
                ja_name, en_name = Path(ja).name, Path(en).name
                self.assertIn(f"[{en_name}]({en_name})", head(read(ja)))
                self.assertIn("正本はこの日本語の版", head(read(ja)))
                self.assertIn(f"[{ja_name}]({ja_name})", head(read(en)))
                self.assertIn("the Japanese version is authoritative", head(read(en)))

    def test_ascii_inline_code_is_kept(self):
        for ja, en in PAIRS:
            with self.subTest(ja):
                self.assertEqual(inline_code(read(ja)) - inline_code(read(en)), set())

    def test_same_commands_and_options(self):
        for ja, en in PAIRS:
            with self.subTest(ja):
                self.assertEqual(subcommands(read(en)), subcommands(read(ja)))
                self.assertEqual(options(read(en)), options(read(ja)))

    def test_same_json_output_and_shell_blocks(self):
        for ja, en in PAIRS:
            with self.subTest(ja):
                for langs in (("json",), ("text",), ("sh",)):
                    self.assertEqual(fences(read(en), *langs), fences(read(ja), *langs), langs)

    def test_relative_links_resolve(self):
        for name in [n for pair in PAIRS for n in pair]:
            base = (ROOT / name).parent
            for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", prose(read(name))):
                if re.match(r"\w+://", target):
                    continue
                with self.subTest(name=name, target=target):
                    self.assertTrue((base / target).exists())


if __name__ == "__main__":
    unittest.main()
