# -*- coding: utf-8 -*-
"""分類器による検査（classify）。問いの型の登録、材料の組み立て、判定の台帳、記録との突き合わせ。

分類器は、ブリッジが保存している欄の閉じた語彙を、独立にもう一度付ける。人や AI が記録したラベルと食い違えば、印を立てる。
印を立てるだけで、承認の状態は変えない（人だけが「主張を支持」へ上げる）。確からしさは分岐に使わない。
外へ送るのは `classify --send` のときだけで、既定は送る内容の見積りを出す。
"""
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from . import config as cfg
from .classifier import Ask, ClassifierUnavailable, make_classifier
from .manuscript import unmark

ABSTAIN = "判定できない"

# 既定の型（最小の四つ）。足すときは bridge.toml の [[checks]] に同じ形で書く。同じ type 名は上書きになる。
DEFAULT_CHECKS = [
    {
        "type": "cite.diff", "version": 1, "for": "citation",
        "question": "本文の文は、原典の逐語に対して、次のどれに当たるか。",
        "labels": ["一致", "言い換え", "限定つき一般化", "外挿", ABSTAIN],
        "gloss": {"一致": "逐語と同じ内容", "言い換え": "内容は同じで、言い方が違う",
                  "限定つき一般化": "逐語の条件や範囲を落として、一般化している",
                  "外挿": "逐語に書かれていないことまで述べている", ABSTAIN: "材料から決められない"},
        "materials": {"claim": "citation.sentence", "source": "excerpt.逐語", "before": "excerpt.前", "after": "excerpt.後"},
        "compare": "citation.原文との差",
    },
    {
        "type": "cite.strength", "version": 1, "for": "citation",
        "question": "本文の文は、原典の内容を、どの強さで述べているか。",
        "labels": ["観察", "示唆", "主張", "一般化", "条件付き", ABSTAIN],
        "gloss": {"観察": "観察した事実を述べる", "示唆": "かもしれない、と示す", "主張": "著者の主張として述べる",
                  "一般化": "広い範囲に一般化して述べる", "条件付き": "条件や範囲を限って述べる", ABSTAIN: "材料から決められない"},
        "materials": {"claim": "citation.sentence", "source": "excerpt.逐語", "before": "excerpt.前", "after": "excerpt.後"},
        "compare": "excerpt.強さ",
    },
    {
        "type": "cite.attribution", "version": 1, "for": "excerpt",
        "question": "原典の逐語は、誰の主張か。前後の文から判断する。",
        "labels": ["著者の主張", "他者の紹介", "仮定", ABSTAIN],
        "gloss": {"著者の主張": "この原典の著者自身の主張や結果", "他者の紹介": "他の研究や一般論の紹介",
                  "仮定": "仮定や問題設定", ABSTAIN: "材料から決められない"},
        "materials": {"source": "excerpt.逐語", "before": "excerpt.前", "after": "excerpt.後"},
        "flag_on": ["他者の紹介"],
    },
    {
        "type": "cite.not_said", "version": 1, "for": "excerpt",
        "question": "次の文は、原典の逐語と前後の文に書かれているか。 {about}",
        "labels": ["書かれていない", "書かれている", ABSTAIN],
        "gloss": {"書かれていない": "逐語にも前後の文にも無い", "書かれている": "逐語か前後の文に書かれている",
                  ABSTAIN: "材料から決められない"},
        "materials": {"source": "excerpt.逐語", "before": "excerpt.前", "after": "excerpt.後"},
        "about": "excerpt.言っていないこと",
        "flag_on": ["書かれている"],
    },
]

SLOT_NAMES = {"claim": "本文の文", "source": "原典の逐語", "before": "逐語の前の文", "after": "逐語の後の文"}
# 抜き書きの欄名 -> review_data の根拠（evidence）の鍵
EXCERPT_FIELDS = {"逐語": "verbatim", "前": "before", "含む文": "sentence", "後": "after",
                  "強さ": "strength", "要約": "summary", "言っていないこと": "not_said"}
PATH_RE = re.compile(r"^(citation|excerpt)\.(\S+)$")


def _fp(text):
    return hashlib.sha1(re.sub(r"\s", "", text).encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------- 型の登録

def registry():
    """既定の型に、設定の [[checks]] を足し（同じ type は上書き）、[classifier] types で選ぶ。検証して返す。"""
    by = {c["type"]: dict(c) for c in DEFAULT_CHECKS}
    for c in cfg.CHECKS_USER:
        if "type" not in c:
            sys.exit("設定の [[checks]] に type が無い")
        by[c["type"]] = dict(c)
    names = cfg.CLASSIFIER.get("types")
    if names:
        missing = [n for n in names if n not in by]
        if missing:
            sys.exit(f"[classifier] types に、登録の無い型がある: {missing}")
        by = {n: by[n] for n in names}
    for c in by.values():
        _validate(c)
    return list(by.values())


def _validate(c):
    t = c["type"]
    for k in ("version", "for", "question", "labels", "materials"):
        if k not in c:
            sys.exit(f"型 {t}: 欄 '{k}' が無い")
    if c["for"] not in ("citation", "excerpt"):
        sys.exit(f"型 {t}: for は citation か excerpt")
    if ABSTAIN not in c["labels"] or len(c["labels"]) < 2:
        sys.exit(f"型 {t}: labels に「{ABSTAIN}」と、もう一つ以上の選択肢が要る")
    if not c["materials"]:
        sys.exit(f"型 {t}: materials が空")
    paths = list(c["materials"].values()) + [c[k] for k in ("compare", "about") if c.get(k)]
    for p in paths:
        m = PATH_RE.match(p)
        if not m:
            sys.exit(f"型 {t}: 欄の指し方 '{p}' は citation.<欄> か excerpt.<欄>")
        if c["for"] == "excerpt" and m.group(1) == "citation":
            sys.exit(f"型 {t}: for = excerpt の型は citation の欄を使えない（{p}）")
    if not c.get("compare") and not c.get("flag_on"):
        sys.exit(f"型 {t}: compare か flag_on のどちらかが要る（何と突き合わせるか）")
    for lab in c.get("flag_on", []):
        if lab not in c["labels"]:
            sys.exit(f"型 {t}: flag_on '{lab}' が labels に無い")
    if c.get("on_disagree", "flag") != "flag":
        sys.exit(f"型 {t}: on_disagree は flag だけ（要再確認へ下げる動作は、人の承認との一致率を測ってから）")


def spec_fp(c):
    """型の文面・選択肢・説明の指紋。変えると、以前の判定は古くなる（version を上げ忘れても）。"""
    return _fp(json.dumps([c["question"], c["labels"], sorted(c.get("gloss", {}).items())], ensure_ascii=False))


# ---------------------------------------------------------------- 単位（引用と抜き書き）と材料

def units_from_data(data):
    """review_data の結果から、判定の単位を作る。引用（主張）ごとと、抜き書きごと。"""
    units, seen = [], set()
    for it in data["citations"]:
        if it["kind"] != "主張":
            continue
        ev = [e for e in it["evidence"] if not e.get("missing") and not e.get("new")]
        units.append({"item": f"cite:{it['id']}", "scope": "citation", "id": it["id"], "sentence": unmark(it["sentence"]),
                      "fields": it["fields"], "excerpts": ev})
        for e in ev:
            if e["id"] not in seen:
                seen.add(e["id"])
                units.append({"item": f"exc:{e['id']}", "scope": "excerpt", "id": e["id"], "excerpts": [e]})
    for e in data.get("excerpts_only", []):
        if not e.get("missing") and e["id"] not in seen:
            seen.add(e["id"])
            units.append({"item": f"exc:{e['id']}", "scope": "excerpt", "id": e["id"], "excerpts": [e]})
    return units


def values_at(unit, path):
    """欄の値の並び。citation.<欄> は一つ、excerpt.<欄> は根拠の数だけ。"""
    kind, name = PATH_RE.match(path).groups()
    name = cfg.FIELD_ALIASES.get(name, name)
    if kind == "citation":
        if name in ("sentence", "本文", "含む文"):
            return [unit.get("sentence", "")]
        return [unit.get("fields", {}).get(name, "")]
    key = EXCERPT_FIELDS.get(name)
    if key is None:
        return [""]
    return [e.get(key, "") or "" for e in unit["excerpts"]]


def text_at(unit, path):
    """材料の文面。根拠が複数なら、抜き書きの ID を付けて並べる。"""
    kind = path.split(".")[0]
    vals = values_at(unit, path)
    if kind == "excerpt" and len(unit["excerpts"]) > 1:
        return "\n".join(f"[{e['id']}] {v}" for e, v in zip(unit["excerpts"], vals) if v)
    return "\n".join(v for v in vals if v)


def build(check, unit):
    """(state, about, 材料の指紋)。材料に空の枠しか無ければ None。"""
    parts, mats = [], []
    for slot, path in check["materials"].items():
        text = text_at(unit, path)
        if text:
            parts.append(f"[{SLOT_NAMES.get(slot, slot)}]\n{text}")
            mats.append(f"{slot}\t{text}")
    if not parts or (unit["scope"] == "citation" and not unit["excerpts"]):
        return None
    about = text_at(unit, check["about"]) if check.get("about") else ""
    if check.get("about") and not about:
        return None
    return "\n\n".join(parts), about, _fp("\n".join(mats) + "\nabout\t" + about)


def judge_status(check, label, record):
    """分類器のラベルを、記録（compare の欄の値）と突き合わせた結果。確からしさは使わない。"""
    if label == ABSTAIN:
        return "判定できない"
    if check.get("compare"):
        vals = [v for v in record if v]
        if not vals:
            return "記録なし"
        return "一致" if label in vals else "食い違い"
    return "要確認" if label in check.get("flag_on", []) else "問題なし"


FLAGGED = ("食い違い", "要確認")


# ---------------------------------------------------------------- 台帳

def load_ledger():
    """(item, type) ごとの最新の判定。台帳は追記だけで、同じ組の後のものが新しい。"""
    out = {}
    p = cfg.JUDGMENTS
    if p and p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                e = json.loads(ln)
                out[(e["item"], e["type"])] = e
    return out


def append_ledger(entries):
    cfg.JUDGMENTS.parent.mkdir(parents=True, exist_ok=True)
    with cfg.JUDGMENTS.open("a", encoding="utf-8", newline="\n") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def fresh(entry, check, mat):
    return bool(entry) and entry.get("version") == check["version"] and entry.get("spec") == spec_fp(check) \
        and entry.get("mat") == mat


def attach_checks(data):
    """review_data の引用に、分類器の判定（最新のもの）を足す。台帳が無ければ何もしない。"""
    ledger = load_ledger()
    if not ledger:
        return
    checks = {c["type"]: c for c in registry()}
    by_item = {u["item"]: u for u in units_from_data(data)}
    for it in data["citations"]:
        rows = []
        unit_ids = [f"cite:{it['id']}"] + [f"exc:{e['id']}" for e in it["evidence"] if not e.get("missing")]
        for item in unit_ids:
            u = by_item.get(item)
            for (i, t), e in ledger.items():
                if i != item or t not in checks or u is None:
                    continue
                c = checks[t]
                b = build(c, u)
                is_fresh = bool(b) and fresh(e, c, b[2])
                record = [v for p in [c.get("compare")] if p for v in values_at(u, p)]
                rows.append({"item": item, "type": t, "label": e["label"], "score": e.get("score"),
                             "record": [v for v in record if v], "fresh": is_fresh,
                             "status": judge_status(c, e["label"], record) if is_fresh else "古い"})
        if rows:
            it["classifier"] = rows


def summary():
    """台帳の要約。check とマニフェスト用。台帳が無ければ None。"""
    ledger = load_ledger()
    if not ledger:
        return None
    flagged = sum(1 for e in ledger.values() if e.get("status") in FLAGGED)
    return {"judgments": len(ledger), "flagged": flagged,
            "providers": sorted({f"{e.get('provider')}/{e.get('model')}" for e in ledger.values()}),
            "types": sorted({f"{e['type']}@{e['version']}" for e in ledger.values()})}


# ---------------------------------------------------------------- コマンド

def cmd_classify(args):
    """分類器に問い、判定を台帳へ足す。--send が無ければ、送る内容の見積りだけを出す（何も送らない）。"""
    from .review import review_data
    checks = registry()
    data = review_data(args.cids or None, None, include_done=True)
    units = units_from_data(data)
    ledger = load_ledger()

    if args.list:
        return _list(checks, units, ledger, show_all=args.all)

    max_chars = int(cfg.CLASSIFIER.get("max_chars", 6000))
    requests, too_long, done = {}, 0, 0
    for u in units:
        for c in checks:
            if c["for"] != u["scope"]:
                continue
            b = build(c, u)
            if b is None:
                continue
            state, about, mat = b
            if fresh(ledger.get((u["item"], c["type"])), c, mat):
                done += 1
                continue
            if len(state) + len(about) > max_chars:
                too_long += 1
                continue
            req = requests.setdefault((u["item"], state), {"item": u["item"], "state": state, "asks": [], "unit": u})
            req["asks"].append((c, about, mat))
    reqs = list(requests.values())
    if args.limit:
        reqs = reqs[:args.limit]
    n_asks = sum(len(r["asks"]) for r in reqs)
    chars = sum(len(r["state"]) + sum(len(a[1]) for a in r["asks"]) for r in reqs)
    print(f"判定済み {done} 件。送る予定: 要求 {len(reqs)} 回、問い {n_asks} 件、約 {chars} 字"
          + (f"。材料が長くて渡せないもの {too_long} 件（max_chars {max_chars}）" if too_long else ""))
    if not reqs:
        return
    clf = make_classifier(cfg.CLASSIFIER)
    if clf is None:
        print("[classifier] provider が設定に無いので送れない（README「分類器」）")
        return
    if not args.send:
        print(f"送る相手: {clf.name}（{clf.model}）。原稿の文と原典の逐語・前後の文が外部のサービスへ渡り、課金される。"
              "送るには --send を付ける。")
        return
    print(f"送る相手: {clf.name}（{clf.model}）。原稿の文と原典の逐語・前後の文が外部のサービスへ渡る。")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    written, failed = [], 0
    for r in reqs:
        asks = [Ask(type=c["type"], labels=tuple(c["labels"]), question=c["question"],
                    gloss=tuple(sorted(c.get("gloss", {}).items())), about=about) for c, about, _ in r["asks"]]
        try:
            verdicts = clf.classify(r["state"], asks)
        except ClassifierUnavailable as exc:
            failed += 1
            print(f"SKIP {r['item']}: {exc}")
            if "鍵" in str(exc):
                break
            continue
        for (c, about, mat), v in zip(r["asks"], verdicts):
            if v is None:
                failed += 1
                continue
            record = [x for p in [c.get("compare")] if p for x in values_at(r["unit"], p) if x]
            written.append({"item": r["item"], "type": c["type"], "version": c["version"], "spec": spec_fp(c), "mat": mat,
                            "label": v.label, "score": v.score, "scores": v.scores, "record": record,
                            "status": judge_status(c, v.label, record), "provider": clf.name, "model": clf.model, "at": now})
    if written:
        append_ledger(written)
    flagged = [e for e in written if e["status"] in FLAGGED]
    print(f"--- 判定を {len(written)} 件、台帳に足した（{cfg.JUDGMENTS.as_posix()}）。印: {len(flagged)} 件、答えが無かった問い: {failed} 件")
    for e in flagged:
        print(f"  {e['item']}  {e['type']}  {e['label']}" + (f"（記録 {'・'.join(e['record'])}）" if e["record"] else ""))
    if failed and not written:
        sys.exit(1)


def _list(checks, units, ledger, show_all=False):
    by_type = {c["type"]: c for c in checks}
    unit_by = {u["item"]: u for u in units}
    rows, stale = [], 0
    for (item, t), e in sorted(ledger.items()):
        c, u = by_type.get(t), unit_by.get(item)
        if c is None or u is None:
            continue
        b = build(c, u)
        if not b or not fresh(e, c, b[2]):
            stale += 1
            continue
        record = [v for p in [c.get("compare")] if p for v in values_at(u, p) if v]
        rows.append((item, t, e["label"], e.get("score"), record, judge_status(c, e["label"], record)))
    shown = [r for r in rows if show_all or r[5] in FLAGGED or r[5] == "判定できない"]
    for item, t, label, score, record, status in sorted(shown, key=lambda r: (r[5] not in FLAGGED, r[0], r[1])):
        sc = f"（{score:.2f}）" if isinstance(score, float) else ""
        rec = f"  記録: {'・'.join(record)}" if record else ""
        print(f"{status:<6} {item}  {t}  {label}{sc}{rec}")
    n_flag = sum(1 for r in rows if r[5] in FLAGGED)
    print(f"--- 判定 {len(rows)} 件（古い {stale} 件を除く）のうち、印 {n_flag} 件"
          + ("" if show_all else "（全件は --all）"))


def manifest_record():
    """マニフェストの classifier 欄。分類器を設定せず、台帳も無ければ None。

    型は、設定の [[checks]] で足せる。足したら、ここに型の名前・版・文面の指紋が載る（何に対して判定したかが残る）。
    """
    s = summary()
    if not cfg.CLASSIFIER and s is None:
        return None
    return {
        "provider": cfg.CLASSIFIER.get("provider", ""), "model": cfg.CLASSIFIER.get("model", ""),
        "types": [{"type": c["type"], "version": c["version"], "spec": spec_fp(c)} for c in registry()],
        "judgments": s["judgments"] if s else 0, "flagged": s["flagged"] if s else 0,
        "note": "型は bridge.toml の [[checks]] に足せる（同じ type は上書き）。文面か選択肢を変えると spec が変わり、以前の判定は古くなる。"
                "確からしさは規則に使わない。印を立てるだけで、承認の状態は変えない（README「分類器」）。",
    }
