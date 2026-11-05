# -*- coding: utf-8 -*-
"""承認の HTML が保存した判断ファイルの書き込み（apply）。"""
from pathlib import Path
import datetime
import hashlib
import sys
from . import config as cfg
from .approve import approver_problem, write_approval, write_confirm, write_remark, write_source_check
from .blocks import parse_blocks
from .propose import apply_candidate


def _latest_decisions(folder, manuscript):
    """folder の判断ファイルのうち、この原稿の、保存が最も新しいもの。"""
    import json
    best = None
    for f in Path(folder).glob("decisions_*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("format") == "cite-bridge-decisions/1" and d.get("manuscript") == manuscript:
            if best is None or d.get("saved", "") > best[1]:
                best = (f, d.get("saved", ""))
    return best[0] if best else None


def _gap(x, *keys):
    """判断ファイルの件 x で、照合に要る欄（keys）が空か無いときは、その欄の名前を並べた文を返す。揃っていれば None。

    指紋が空だと照合を飛ばす書き込みがあるので、書き込みの前にここで断る。件が辞書でないときは全部が無いものとして扱う。
    """
    if not isinstance(x, dict):
        x = {}
    gone = [k for k in keys if not str(x.get(k) or "").strip()]
    return "・".join(gone) if gone else None


def _id_of(x):
    """SKIP の行の頭に出す件の ID。無ければ「?」。"""
    return (x.get("id") if isinstance(x, dict) else None) or "?"


def cmd_apply(args):
    """承認の HTML が書き出した判断ファイルを、指紋を照らしてから書き込む。

    HTML はサーバを持たず、書き込みもしない。判断はファイルとしてここへ渡り、書き込みは approve・confirm と同じ関数を通る。
    HTML を作った後に本文・根拠・要約が変わったものは書かずに報告する（見ていないものへの承認を防ぐ）。
    適用したファイルは記録し（設定の bridge.applied）、同じファイルと、最後に適用したものより前に保存されたファイルは断る
    （保存は判断をすべて含めて書き出すので、古いファイルを後から適用すると判断が巻き戻る）。
    """
    import json
    head, _ = parse_blocks(cfg.CIT)
    manuscript = Path(head["fields"].get("対象", "")).as_posix()
    if args.latest:
        folder = Path(args.source) if args.source else Path.home() / "Downloads"
        args.file = _latest_decisions(folder, manuscript)
        if not args.file:
            sys.exit(f"{folder} に {manuscript} の判断ファイルが無い")
        print(f"最新の判断ファイル: {args.file}")
    elif not args.file:
        sys.exit("判断ファイルを渡すか、--latest を付ける")
    raw = Path(args.file).read_bytes()
    d = json.loads(raw.decode("utf-8"))
    if d.get("format") != "cite-bridge-decisions/1":
        sys.exit("判断ファイルの形式が違う（format: cite-bridge-decisions/1 を期待）")
    by = (d.get("by") or "").strip()
    if not by:
        sys.exit("判断ファイルに判断した者（by）が無い")
    if approver_problem(by):
        sys.exit(approver_problem(by))
    if manuscript != d.get("manuscript"):
        sys.exit(f"判断ファイルの原稿 {d.get('manuscript')} が、引用のファイルの対象と違う")
    log = json.loads(cfg.APPLIED.read_text(encoding="utf-8")) if cfg.APPLIED.exists() else {}
    ent = log.setdefault(manuscript, {"last_saved": "", "files": []})
    sha = hashlib.sha256(raw).hexdigest()
    if any(f["sha256"] == sha for f in ent["files"]):
        sys.exit("この判断ファイルは適用済み")
    if ent["last_saved"] and d.get("saved", "") <= ent["last_saved"] and not args.allow_older:
        sys.exit(f"この判断ファイル（保存 {d.get('saved')}）は、最後に適用したもの（保存 {ent['last_saved']}）より古い。"
                 "判断が巻き戻るので断った（意図したときだけ --allow-older）")
    done, skipped = [], []
    for x in d.get("decisions", []):
        if not (isinstance(x, dict) and (x.get("action") or x.get("remark"))):
            continue
        gone = _gap(x, "id", "fingerprint", "evidence")
        if gone:
            skipped.append(f"{_id_of(x)}: 判断ファイルの {gone} が空か無い。書かなかった")
            continue
        if x.get("action"):
            ok, msg = write_approval(x["id"], by, x.get("note") or None, x["action"] == "send_back",
                                     seen=(x["fingerprint"], x["evidence"]), dry=args.dry_run)
            (done if ok else skipped).append(msg)
        if x.get("remark"):
            ok, msg = write_remark(x["id"], by, x["remark"], dry=args.dry_run)
            (done if ok else skipped).append(msg)
    for x in d.get("candidates", []):
        if isinstance(x, dict) and x.get("action") in ("accept", "reject"):
            gone = _gap(x, "id", "cfp")
            if gone:
                skipped.append(f"{_id_of(x)}: 判断ファイルの {gone} が空か無い。書かなかった")
                continue
            ok, msg = apply_candidate(x["id"], x["action"], by, x.get("note") or None, x["cfp"], dry=args.dry_run)
            (done if ok else skipped).append(msg)
    for x in d.get("confirms", []):
        gone = _gap(x, "id", "fingerprint")
        if gone:
            skipped.append(f"{_id_of(x)}: 判断ファイルの {gone} が空か無い。書かなかった")
            continue
        ok, msg = write_confirm(x["id"], by, seen=x["fingerprint"], dry=args.dry_run)
        (done if ok else skipped).append(msg)
    for x in d.get("source_checks", []):  # 原本での確認（§5.4 の 2）。指紋が今の逐語と合うものだけ書く
        gone = _gap(x, "id", "fingerprint")
        if gone:
            skipped.append(f"{_id_of(x)}: 判断ファイルの {gone} が空か無い。書かなかった")
            continue
        ok, msg = write_source_check(x["id"], by, x.get("result", "一致"), x.get("page") or None, x.get("note") or None,
                                     seen=x["fingerprint"], dry=args.dry_run)
        (done if ok else skipped).append(msg)
    for m in done:
        print(("（試し）" if args.dry_run else "") + m)
    for m in skipped:
        print("SKIP", m)
    print(f"--- 書いた {len(done)} 件、書かなかった {len(skipped)} 件" + ("（--dry-run なので何も書いていない）" if args.dry_run else ""))
    if not args.dry_run:
        ent["files"].append({"file": Path(args.file).name, "saved": d.get("saved", ""), "sha256": sha, "by": by,
                             "applied": datetime.datetime.now().isoformat(timespec="seconds"),
                             "written": len(done), "skipped": len(skipped)})
        ent["last_saved"] = max(ent["last_saved"], d.get("saved", ""))
        cfg.APPLIED.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if skipped:
        sys.exit(1)
