# -*- coding: utf-8 -*-
"""spec/vectors.json と spec/publication.example.json を作る（C58）。

使い方: python spec/make_examples.py（SPEC.md の例を直したとき、公開物の形を変えたときに走らせる）
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "tests"))
import test_bridge as tb  # noqa: E402
import test_spec  # noqa: E402
from test_publish import APPROVERS  # noqa: E402

out = root / "spec"
out.mkdir(exist_ok=True)


def block(prefix):
    return json.loads(re.search(r"```json\n(.*?)\n```", test_spec.section(prefix), re.S).group(1))


vectors = {
    "about": "cite-bridge の SPEC.md の例の、機械で読める写し。正本は SPEC.md の §4 と §12.2。",
    "fingerprint": "sha1-8", "identity": "sha256-jcs",
    "whitespace": [f"{ord(c):04X}" for c in test_spec.SPEC_WHITESPACE],
    "fingerprints": block("## 4."),
    "publication": block("### 12.2"),
}
(out / "vectors.json").write_text(json.dumps(vectors, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

# ---- 公開物の例。試験の小さな一式に DOI と承認者の一覧を足し、承認と二つの確認を記録して書き出す
d = Path(tempfile.mkdtemp())
try:
    doe = "Doe, J. (2020). A study of things. *Journal of Things*, 1(1), 1–3."
    conf = tb.CONFIG + APPROVERS + ('[publication]\npublished_by = "Example Lab"\nlicense = "CC-BY-4.0"\n'
                                    'reference = "https://doi.org/10.9999/example.paper"\n')
    files = {"bridge/bridge.toml": conf, "bib.md": tb.BIB.replace(doe, doe + " https://doi.org/10.9999/JT.2020.001"),
             "refs/_txt/doe2020.txt": tb.PAPER, "refs/_txt/yamada2002.txt": tb.JA_PAPER,
             "bridge/excerpts/doe2020.md": tb.EXCERPTS, "manuscript.md": tb.MANUSCRIPT, "bridge/citations.md": tb.CITATIONS}
    for name, text in files.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")

    def run(*args):
        r = subprocess.run([sys.executable, "-X", "utf8", str(tb.BRIDGE), *args], cwd=d, capture_output=True, text=True,
                           encoding="utf-8", env=tb.BridgeTest.clean_env())
        assert r.returncode == 0, (args, r.stdout + r.stderr)

    run("derive")
    run("approve", "c001", "--by", "tester", "--note", "原文のとおり")
    run("confirm", "doe2020#e1", "--by", "tester")
    run("confirm", "doe2020#e1", "--source", "--by", "tester", "--page", "p.2 §3")
    run("checkpoint", "--by", "tester")
    run("publish", "-o", "pub")
    doc = json.loads((d / "pub/publication.json").read_text(encoding="utf-8"))
finally:
    shutil.rmtree(d, ignore_errors=True)

# 例には元のファイルを添えない。道具の指し方は、作った手元の状態（コミット、未コミットの変更）を持たせない
doc["tool"]["commit"], doc["tool"]["dirty"] = None, False
for rec in doc["publication"]["files"].values():
    rec["included"] = False
(out / "publication.example.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("ok", doc["id"], len(vectors["fingerprints"]), len(vectors["publication"]))
