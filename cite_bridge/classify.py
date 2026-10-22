# -*- coding: utf-8 -*-
"""分類器による検査のコマンド（classify）。判定を台帳へ足すのと、台帳の一覧（--list）。測定（--eval）は evaluate.py。"""
import datetime
import sys
from . import config as cfg
from .judge import (FLAGGED, _classifier_or_stop, append_ledger, count_judgments, estimate, judge_status, lang_pair,
                    load_ledger, plan_requests, registry, send_requests, spec_fp, units_from_data, values_at)
from .review import review_data


def cmd_classify(args):
    """分類器に問い、判定を台帳へ足す。--send が無ければ、送る内容の見積りだけを出す（何も送らない）。"""
    if args.eval:
        from .evaluate import cmd_eval
        return cmd_eval(args)
    checks = registry()
    data = review_data(args.cids or None, None, include_done=True)
    units = units_from_data(data)
    ledger = load_ledger()

    if args.list:
        return _list(units, ledger, show_all=args.all)

    max_chars = int(cfg.CLASSIFIER.get("max_chars", 6000))
    reqs, too_long, done = plan_requests(units, checks, ledger, max_chars)
    if args.limit:
        reqs = reqs[:args.limit]
    print(f"判定済み {done} 件。" + estimate(reqs)
          + (f"。材料が長くて渡せないもの {too_long} 件（max_chars {max_chars}）" if too_long else ""))
    if not reqs:
        return
    clf = _classifier_or_stop(args.send)
    if clf is None:
        return
    now = datetime.datetime.now().isoformat(timespec="seconds")
    written, failed = [], 0
    for r, results in send_requests(clf, reqs):
        if results is None:
            failed += 1
            if not written:  # 最初の要求から通らないなら、提供元が使えない。同じ失敗を繰り返さない
                break
            continue
        for (c, about, mat), v in results:
            if v is None:
                failed += 1
                continue
            record = [x for p in [c.get("compare")] if p for x in values_at(r["unit"], p) if x]
            written.append({"item": r["item"], "type": c["type"], "version": c["version"], "spec": spec_fp(c), "mat": mat,
                            "label": v.label, "score": v.score, "scores": v.scores, "record": record,
                            "status": judge_status(c, v.label, record), "lang": lang_pair(r["unit"]),
                            "provider": clf.name, "model": clf.model, "at": now})
    if written:
        append_ledger(written)
    flagged = [e for e in written if e["status"] in FLAGGED]
    print(f"--- 判定を {len(written)} 件、台帳に足した（{cfg.JUDGMENTS.as_posix()}）。印: {len(flagged)} 件、答えが無かった問い: {failed} 件")
    for e in flagged:
        print(f"  {e['item']}  {e['type']}  {e['label']}" + (f"（記録 {'・'.join(e['record'])}）" if e["record"] else ""))
    if failed and not written:
        sys.exit(1)


def _list(units, ledger, show_all=False):
    j = count_judgments(units, ledger=ledger)
    shown = [r for r in j["rows"] if show_all or r[5] in FLAGGED or r[5] == "判定できない"]
    for item, t, label, score, record, status in sorted(shown, key=lambda r: (r[5] not in FLAGGED, r[0], r[1])):
        sc = f"（{score:.2f}）" if isinstance(score, float) else ""
        rec = f"  記録: {'・'.join(record)}" if record else ""
        print(f"{status:<6} {item}  {t}  {label}{sc}{rec}")
    print(f"--- 判定 {len(j['rows'])} 件（古い {j['stale']} 件を除く）のうち、印 {j['flagged']} 件"
          + ("" if show_all else "（全件は --all）"))
