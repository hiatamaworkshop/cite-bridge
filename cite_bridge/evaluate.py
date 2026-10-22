# -*- coding: utf-8 -*-
"""文面の測定（classify --eval）。型の文面を比べるための測定で、台帳には書かない。

測定の組（cite-bridge-eval/1）は二種類の件を持つ。
承認済みの引用（id だけ）: 人が確かめた組なので、どの型でも印が立たないのが正しい。
改変した組（base と claim）: 承認済みの引用の本文を、人工的に壊したもの（限定を外す、推測を断定にする、結論を足す）。
  flag に挙げた型で印が立つのが正しい。原稿にも引用のファイルにも入らない、試験だけの文である。
調整に使った組だけで測ると当てはめすぎを見逃すので、split（tune / holdout）で分けて数える。
本文と原典の言語が違う組（日本語の本文が英語の原典を引く）は、言語の組ごとにも数える。言語の差を吸収する手当ては、その結果を見て決める。
"""
import datetime
import json
import sys
from pathlib import Path
from . import config as cfg
from .bib import parse_bib
from .judge import (FLAGGED, _classifier_or_stop, _validate, clean_claim, estimate, judge_status, lang_pair,
                    plan_requests, registry, send_requests, source_label, spec_fp, units_from_data, values_at)
from .review import review_data


def _variant(path):
    """(名前, 型の辞書)。path が無ければ、設定どおりの型（既定と bridge.toml の [[checks]]）。"""
    import tomllib
    by = {c["type"]: dict(c) for c in registry()}
    if path:
        for c in tomllib.loads(Path(path).read_text(encoding="utf-8")).get("checks", []):
            by[c["type"]] = dict(c)
        for c in by.values():
            _validate(c)
    return (Path(path).stem if path else "設定"), by


def expected_flag(item, t):
    """True は印が立つのが正しい、False は立たないのが正しい、None は数えない。flag を持つ件が改変。"""
    if "flag" in item:
        return True if t in item["flag"] else None
    return False


def resolve_twin(item, by_id):
    """twin を持つ件は、元の件と同じ内容を別の言語で書いた本文（claim）を持つ。base・split・flag・level・mutation は元の件から引き継ぐ。"""
    if "twin" not in item:
        return item
    src = by_id.get(item["twin"])
    if src is None:
        sys.exit(f"測定の組: {item['id']} の twin '{item['twin']}' が無い")
    out = {k: v for k, v in src.items() if k not in ("id", "claim")}
    if "evidence" not in src:
        out.setdefault("base", src["id"])
    out.update(item)
    return out


def _eval_unit(it, by, pool, bib):
    """測定の件の単位。base の引用の材料を使い、evidence（抜き書きの ID の並び）と record（記録の欄）があれば差し替える。
    base が無く evidence だけを持つ件は、引用の無い文（実際に見つかった誤りの文など）を、その抜き書きと突き合わせる。理由を返せば SKIP。"""
    if it.get("base") or "evidence" not in it:
        u = by.get(it.get("base", it["id"]))
        if u is None:
            return f"引用 {it.get('base', it['id'])} が無い（主張の引用でない、または原稿に無い）"
    else:
        u = {"scope": "citation", "id": it["id"], "sentence": "", "fields": {}, "excerpts": []}
    v = dict(u, item=f"eval:{it['id']}")
    if "evidence" in it:
        missing = [e for e in it["evidence"] if e not in pool]
        if missing:
            return f"抜き書き {', '.join(missing)} が無い"
        v["excerpts"] = [pool[e] for e in it["evidence"]]
        v["source"] = source_label(list(dict.fromkeys(e.split("#")[0] for e in it["evidence"])), bib)
    if "record" in it:
        v["fields"] = {**v.get("fields", {}), **it["record"]}
    if it.get("claim"):
        v["sentence"] = clean_claim(it["claim"])
    return v


def cmd_eval(args):
    es = json.loads(Path(args.eval).read_text(encoding="utf-8"))
    if es.get("format") != "cite-bridge-eval/1":
        sys.exit("測定の組の形式が違う（format: cite-bridge-eval/1 を期待）")
    types = args.types or es.get("types") or []
    variants = [_variant(None)] + [_variant(p) for p in (args.variant or [])]
    data = review_data(None, None, include_done=True, all_orphans=True)
    bib = parse_bib()
    units = units_from_data(data, bib)
    by = {u["id"]: u for u in units if u["scope"] == "citation"}
    pool = {u["id"]: u["excerpts"][0] for u in units if u["scope"] == "excerpt"}
    eunits = []
    by_id = {it["id"]: it for it in es["items"]}
    for it in (resolve_twin(i, by_id) for i in es["items"]):
        if args.split != "all" and it.get("split") != args.split:
            continue
        v = _eval_unit(it, by, pool, bib)
        if isinstance(v, str):
            print(f"SKIP {it['id']}: {v}")
            continue
        eunits.append((it, v))
    max_chars = int(cfg.CLASSIFIER.get("max_chars", 6000))
    plans = []
    for name, by_type in variants:
        checks = [by_type[t] for t in types if t in by_type]
        reqs, too_long, _ = plan_requests([v for _, v in eunits], checks, None, max_chars)
        plans.append((name, by_type, checks, reqs))
    total = [r for *_, reqs in plans for r in reqs] * args.reps
    langs = {}
    for _, v in eunits:
        langs[lang_pair(v)] = langs.get(lang_pair(v), 0) + 1
    twins = sum(1 for i, _ in eunits if i.get("twin"))
    print(f"測定: 組 {len(eunits)} 件（承認済み {sum(1 for i, _ in eunits if 'flag' not in i)}、改変 "
          f"{sum(1 for i, _ in eunits if 'flag' in i)}。言語（本文/原典） "
          f"{'、'.join(f'{k} {n}' for k, n in sorted(langs.items()))}"
          + (f"。うち別の言語で書いた本文 {twins}" if twins else "") + f"）、型 {', '.join(types)}、"
          f"案 {', '.join(n for n, *_ in plans)}、各 {args.reps} 回。" + estimate(total))
    clf = _classifier_or_stop(args.send)
    if clf is None:
        return
    items_by_unit = {v["item"]: it for it, v in eunits}
    rows = []
    for name, by_type, checks, reqs in plans:
        for rep in range(args.reps):
            for r, results in send_requests(clf, reqs):
                if results is None:
                    continue
                it = items_by_unit[r["item"]]
                head = {"variant": name, "rep": rep, "item": it["id"], "split": it.get("split", ""),
                        "lang": lang_pair(r["unit"]), "level": it.get("level", ""), "twin": it.get("twin", "")}
                for (c, about, mat), v in results:
                    exp = expected_flag(it, c["type"])
                    if v is None:
                        rows.append({**head, "type": c["type"], "label": None, "expected": exp,
                                     "ok": False if exp is not None else None})
                        continue
                    record = [x for p in [c.get("compare")] if p for x in values_at(r["unit"], p) if x]
                    status = judge_status(c, v.label, record)
                    top = sorted(v.scores.values(), reverse=True) + [0.0, 0.0]
                    flagged = status in FLAGGED
                    rows.append({**head, "type": c["type"], "label": v.label, "status": status, "record": record,
                                 "margin": round(top[0] - top[1], 3), "flagged": flagged, "expected": exp,
                                 "ok": (flagged == exp) if exp is not None else None, "mutation": it.get("mutation", "")})
    _eval_report(rows, plans, args.verbose)
    out_dir = Path(args.eval).parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"{Path(args.eval).stem}_{stamp}.json"
    out.write_text(json.dumps({
        "format": "cite-bridge-eval-result/1", "set": Path(args.eval).as_posix(), "provider": clf.name, "model": clf.model,
        "reps": args.reps, "types": types,
        "variants": {n: [{"type": c["type"], "version": c["version"], "spec": spec_fp(c)} for c in checks]
                     for n, _, checks, _ in plans},
        "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"--- 結果: {out.as_posix()}（台帳には書いていない）")


def _eval_report(rows, plans, verbose=False):
    splits = ["tune", "holdout"] + sorted({r["split"] for r in rows} - {"tune", "holdout"})
    _eval_table(rows, plans, "分け", lambda r: r["split"], splits)
    langs = sorted({r.get("lang", "") for r in rows})
    if len(langs) > 1:
        print("言語の組（本文/原典）ごと")
        _eval_table(rows, plans, "分けと言語", lambda r: f"{r['split']} {r.get('lang', '')}",
                    [f"{s} {l}" for s in splits for l in langs])
    levels = sorted({str(r["level"]) for r in rows if r.get("level") not in ("", None)})
    if levels:
        print("改変の難しさ（1 目立つ ～ 3 繊細）と言語ごと。調整用と確認用を合わせる")
        _eval_table(rows, plans, "難しさと言語",
                    lambda r: f"{r['level']} {r.get('lang', '')}" if r.get("level") not in ("", None) else None,
                    [f"{lv} {l}" for lv in levels for l in langs])
    if any(r.get("twin") for r in rows):
        _twin_report(rows, plans)
    if verbose:
        for r in rows:
            if r.get("ok") is False:
                exp = "印が立つべき" if r["expected"] else "印が立たないべき"
                print(f"  外れ {r['variant']} {r['type']} {r['item']}（{r.get('lang', '')}、{exp}）: {r.get('label')}"
                      + (f"／記録 {'・'.join(r.get('record') or [])}" if r.get("record") else "")
                      + (f"／{r['mutation']}" if r.get("mutation") else ""))


def _twin_report(rows, plans):
    """同じ内容を別の言語で書いた本文（twin）と元の件で、印の立ち方が同じかを数える。違った組は全部出す。"""
    by = {(r["variant"], r["type"], r["item"], r["rep"]): r for r in rows}
    print("同じ内容の言語違い（元の件 と 別の言語で書いた本文）")
    print(f"{'案':<14}{'型':<16}{'件':<8}{'両方に印':<8}{'元だけ印':<8}{'訳だけ印':<8}{'両方なし'}")
    diffs = []
    for name, *_ in plans:
        for t in sorted({r["type"] for r in rows if r["variant"] == name}):
            pairs = [(by[k], r) for r in rows if r["variant"] == name and r["type"] == t and r.get("twin")
                     for k in [(name, t, r["twin"], r["rep"])] if k in by]
            for kind, want in (("承認済み", False), ("改変", True)):
                sel = [(a, b) for a, b in pairs if a["expected"] is want]
                if not sel:
                    continue
                n = [sum(1 for a, b in sel if (bool(a.get("flagged")), bool(b.get("flagged"))) == k)
                     for k in ((True, True), (True, False), (False, True), (False, False))]
                print(f"{name:<14}{t:<16}{kind:<10}{n[0]:<12}{n[1]:<12}{n[2]:<12}{n[3]}")
                diffs += [(name, t, a, b) for a, b in sel if bool(a.get("flagged")) != bool(b.get("flagged"))]
    for name, t, a, b in diffs:
        print(f"  違い {name} {t} {a['item']}（{a['lang']}）{a.get('label')} ／ {b['item']}（{b['lang']}）{b.get('label')}"
              + (f"／記録 {'・'.join(a.get('record') or [])}" if a.get("record") else ""))


def _eval_table(rows, plans, head, key, groups):
    """案と型ごとに、key(row) が groups のそれぞれに当たる行を数えて一行ずつ出す。"""
    def frac(sel):
        return f"{sum(1 for r in sel if r.get('flagged'))}/{len(sel)}" if sel else "-"

    print(f"{'案':<14}{'型':<16}{head:<14}{'承認済みの誤った印':<12}{'改変の検出':<10}{'判定できない':<8}{'確率の差':<8}{'反復の一致'}")
    for name, *_ in plans:
        for t in sorted({r["type"] for r in rows if r["variant"] == name}):
            for g in groups:
                sel = [r for r in rows if r["variant"] == name and r["type"] == t and key(r) == g]
                if not sel:
                    continue
                real = [r for r in sel if r["expected"] is False]
                mut = [r for r in sel if r["expected"] is True]
                abst = sum(1 for r in sel if r.get("status") == "判定できない")
                margins = [r["margin"] for r in sel if r.get("margin") is not None]
                samples = {}
                for r in sel:
                    samples.setdefault(r["item"], []).append(r.get("label"))
                same = sum(1 for s in samples.values() if len(set(s)) == 1)
                agree = f"{same}/{len(samples)}" if max(map(len, samples.values())) > 1 else "-"  # 一回だけなら比べられない
                print(f"{name:<14}{t:<16}{g:<16}{frac(real):<20}{frac(mut):<14}{abst:<12}"
                      f"{(sum(margins) / len(margins)) if margins else 0:<12.2f}{agree}")
