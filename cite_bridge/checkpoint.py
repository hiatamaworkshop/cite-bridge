# -*- coding: utf-8 -*-
"""チェックポイントのマニフェスト、道具の版、git の pre-commit、印を外した写し。"""
from pathlib import Path
import datetime
import hashlib
import os
import sys
from . import config as cfg
from .approve import approver_problem
from .check import run_check
from .config import TOOL_NAME, TOOL_VERSION
from .judge import load_ledger, manifest_record, units_from_data
from .manuscript import unmark
from .propose import _manuscript
from .review import review_data
from .util import _git, _sha256


TOOL_ROOT = Path(__file__).resolve().parent.parent  # bridge.py のあるフォルダ（道具のルート）


def cmd_checkpoint(args):
    """check --strict を通った地点を、マニフェスト（JSON）として残す。通らなければ書かない。

    マニフェストは、どの原稿・書誌・抜き書き・抽出テキストから、どの確認の状態で通ったかを、ハッシュと件数で持つ。
    """
    import json
    by = args.by or None
    if cfg.APPROVERS:  # 最終の提出は人が出す（§5.6）
        if not by:
            sys.exit("承認者の一覧があるので --by（提出する人）が要る")
        if approver_problem(by):
            sys.exit(approver_problem(by))
        if cfg.APPROVERS[by] != "human":
            sys.exit(f"--by '{by}' は人（human）でない。最終の提出は人が出す")
    r = run_check()
    if r["errors"] or r["notes"]:
        for e in r["errors"]:
            print("ERROR", e)
        for n in r["notes"]:
            print("NOTE ", n)
        print(f"--- checkpoint を書かなかった（整合の崩れ {len(r['errors'])} 件、確認待ち {len(r['notes'])} 件）")
        sys.exit(1)
    now = datetime.datetime.now(datetime.timezone.utc)
    inputs = {"config": str(cfg.CONFIG_USED), "bibliography": str(cfg.BIB), "manuscript": r["manuscript"], "citations": str(cfg.CIT)}
    files = {k: {"path": v, "sha256": _sha256(v)} for k, v in inputs.items() if v}
    files["excerpts"] = {p.as_posix(): _sha256(p) for p in sorted(cfg.EXC_DIR.glob("*.md"))}
    files["texts"] = {t: _sha256(t) for t in r["texts"]}
    tracked = [v for v in inputs.values() if v] + [cfg.EXC_DIR.as_posix()]
    units = units_from_data(review_data(None, None, include_done=True, checked=r)) if load_ledger() else []  # check と同じ単位
    manifest = {
        "format": "cite-bridge-manifest/1",
        "tool": tool_version(),
        "checkpoint": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": args.label,
        "git": {"head": _git("rev-parse", "HEAD"),
                "uncommitted": (_git("-c", "core.quotepath=off", "status", "--porcelain", "--", *tracked) or "").splitlines()},
        "files": files,
        "excerpts": {"total": r["excerpts"], "match": r["excerpt_states"], "grade": r["grades"]},
        "citations": r["citations"],
        "approvers": r["approvers"],
        "approver_kinds": r["approver_kinds"],
        "coverage": r["coverage"],
        "summary_checks": r["summary_checks"],
        "source_checks": r["source_checks"],
        "decided_by": r["decided_by"],  # 誰が判断したかの内訳。論文の AI の使用の開示に使う（§8、C43）
        "by": by,
        "classifier": manifest_record(units),  # 分類器を使っていなければ None
    }
    cfg.CKPT_DIR.mkdir(parents=True, exist_ok=True)
    out = cfg.CKPT_DIR / (now.strftime("%Y%m%dT%H%M%SZ") + ".json")
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"ok checkpoint: {out.as_posix()}")
    if manifest["git"]["uncommitted"]:
        print("注意: 未コミットの変更がある状態で書いた（git.uncommitted を参照）")


def tool_version():
    """この道具の版。別のリポジトリから使うと、どの版の検査で通ったかが論文側から分からなくなるので、マニフェストに残す。

    version は形式の版、sha256 は道具のソース（bridge.py と cite_bridge/ の下の .py・.html・.js）の指紋、
    commit は道具のフォルダを最後に変えたコミット（git の外では None）。dirty は道具のフォルダに未コミットの変更があること。
    """
    d = str(TOOL_ROOT)
    commit = _git("-C", d, "log", "-1", "--format=%H", "--", ".")
    dirty = None
    if commit is not None:
        dirty = bool(_git("-C", d, "-c", "core.quotepath=off", "status", "--porcelain", "--", "."))
    return {"name": TOOL_NAME, "version": TOOL_VERSION, "sha256": source_digest(), "commit": commit or None, "dirty": dirty}


def source_digest():
    """道具のソースの指紋。ファイルの相対パスと内容の sha256 を、パスの順に並べて、もう一度 sha256 にかける。"""
    files = [TOOL_ROOT / "bridge.py"] + sorted(
        p for p in (TOOL_ROOT / "cite_bridge").rglob("*")
        if p.suffix in (".py", ".html", ".js") and "__pycache__" not in p.parts)
    lines = [f"{p.relative_to(TOOL_ROOT).as_posix()}\t{_sha256(p)}" for p in files]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def cmd_precommit(args):
    """git の pre-commit から呼ぶ。ステージした内容が監視対象のときだけ check を走らせ、整合の崩れ（ERROR）で止める。

    監視するのは、設定が指す原稿・書誌・抜き書き・引用・抽出テキスト・Web の写し・設定ファイルと、道具のフォルダ。
    設定の [hook] watch に足せる。確認待ち（NOTE）では止めない（提出前は check --strict）。
    道具のフォルダをステージしたとき（道具を直したとき）は、tests の試験も走らせる。
    検査するのは作業ツリーの状態で、ステージした内容そのものではない。
    """
    import subprocess
    top = _git("rev-parse", "--show-toplevel")
    if not top:
        sys.exit("git のリポジトリの中で実行する")
    top = Path(top).resolve()
    out = subprocess.run(["git", "-c", "core.quotepath=off", "diff", "--cached", "--name-only", "--diff-filter=ACMRD"],
                         capture_output=True, text=True, encoding="utf-8", cwd=top).stdout
    staged = [(top / ln).resolve() for ln in out.splitlines() if ln.strip()]
    if not staged:
        return

    def under(path, roots):
        return any(path == r or r in path.parents for r in roots)

    tool_dir = TOOL_ROOT
    manuscript = _manuscript() if cfg.CIT.exists() else None
    if manuscript == Path(""):
        manuscript = None
    watch = [cfg.BIB, cfg.EXC_DIR, cfg.CIT, cfg.TXT_DIR, cfg.WEB_DIR, cfg.CONFIG_USED, *cfg.WATCH_EXTRA]
    if manuscript:
        watch.append(manuscript)
    roots = [(Path.cwd() / p).resolve() for p in watch] + [tool_dir]
    if not any(under(p, roots) for p in staged):
        return
    r = run_check()
    for e in r["errors"]:
        print("ERROR", e)
    if r["errors"]:
        print(f"{TOOL_NAME}: 整合の崩れがあるのでコミットを止めた（bridge.py check で確認）")
        sys.exit(1)
    # 道具が使う側と同じリポジトリにあるときだけ、道具の試験を走らせる。道具が別のリポジトリ（submodule）なら、
    # 試験は道具のリポジトリの hook（.githooks/pre-commit）が走らせるので、使う側では整合の検査だけにする
    own = _git("-C", str(tool_dir), "rev-parse", "--show-toplevel")
    same_repo = bool(own) and Path(own).resolve() == top
    if same_repo and any(under(p, [tool_dir]) for p in staged) and (tool_dir / "tests").is_dir():
        # hook の中では GIT_DIR などが環境に入っている。試験の git が呼び出し元のリポジトリを触らないよう外す
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        t = subprocess.run([sys.executable, "-I", "-X", "utf8", "-m", "unittest", "discover", "-s", str(tool_dir / "tests")],
                           capture_output=True, text=True, encoding="utf-8", env=env)
        if t.returncode != 0:
            print("\n".join((t.stdout + t.stderr).splitlines()[-20:]))
            print(f"{TOOL_NAME}: 試験が通らないのでコミットを止めた")
            sys.exit(1)


def cmd_strip(args):
    """原稿から引用の印を外した写しを作る（提出物を作る前段）。原稿そのものは変えない。"""
    text = Path(args.src).read_text(encoding="utf-8")
    n = len(cfg.MARK_RE.findall(text))
    out = unmark(text)
    Path(args.out).write_text(out, encoding="utf-8", newline="")
    print(f"ok {args.out}（印 {n} 個を外した）")
