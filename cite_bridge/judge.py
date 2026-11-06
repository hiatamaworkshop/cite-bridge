# -*- coding: utf-8 -*-
"""分類器による検査の核。問いの型の登録、材料の組み立て、判定の台帳、記録との突き合わせ、要求と送信。

コマンドは classify.py（classify と --list）と evaluate.py（--eval の測定）。ここは review を import しない。

分類器は、ブリッジが保存している欄の閉じた語彙を、独立にもう一度付ける。人や AI が記録したラベルと食い違えば、印を立てる。
印を立てるだけで、承認の状態は変えない（人だけが「主張を支持」へ上げる）。確からしさは分岐に使わない。
外へ送るのは `classify --send` のときだけで、既定は送る内容の見積りを出す。
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from . import config as cfg
from .classifier import Ask, ClassifierUnavailable, make_classifier
from .manuscript import unmark

ABSTAIN = "判定できない"

# 既定の型（最小の三つ）。足すときは bridge.toml の [[checks]] に同じ形で書く。同じ type 名は上書きになる。
# cite.strength（本文の強さ）は既定から外した。実機の測定（2026-10-15）で、承認済みの引用にも「強めている」と答え、区別ができなかった。
# 言い過ぎは cite.diff の 限定つき一般化 と 外挿 で拾う。使うときは [[checks]] で足す（README に例）。
DEFAULT_CHECKS = [
    {
        # 版 4（2026-10-15）。実機の測定で、版 2 より承認済みの誤った印が少なく、検出はほぼ同じだった。
        # 要約・一部だけの引用・別の言語への訳は言い換えに入れ、留保を外して強めることは限定つき一般化に入れる。
        "type": "cite.diff", "version": 4, "for": "citation",
        "question": "本文の文のうち、{about} を引いている部分（前置き、本文の著者自身の判断、他の出典を引いている部分は除く）は、"
                    "原典の逐語に対して、次のどれに当たるか。",
        "labels": ["一致", "言い換え", "限定つき一般化", "外挿", ABSTAIN],
        "gloss": {"一致": "逐語と同じ内容を、ほぼ同じ言い方で述べている",
                  "言い換え": "内容・範囲・確かさは逐語と同じで、言い方が違う（要約する、一部だけを引く、別の言語に訳すことを含む）",
                  "限定つき一般化": "逐語の条件・範囲・留保を落として、逐語より広く、または強く述べている",
                  "外挿": "逐語に書かれていない内容（理由・評価・結論・効果）を、原典が述べたこととして書いている",
                  ABSTAIN: "材料から決められない"},
        "materials": {"claim": "citation.sentence", "source": "excerpt.逐語", "before": "excerpt.前", "after": "excerpt.後"},
        "about": "citation.出典",
        "compare": "citation.原文との差",
        "order": [["一致", "言い換え"], ["限定つき一般化"], ["外挿"]],
    },
    {
        "type": "cite.attribution", "version": 1, "for": "excerpt",
        "question": "原典の逐語は、誰の主張か。前後の文から判断する。",
        "labels": ["著者の主張", "他者の紹介", "仮定", ABSTAIN],
        "gloss": {"著者の主張": "この原典の著者自身の主張や結果", "他者の紹介": "他の研究や一般論の紹介",
                  "仮定": "仮定や問題設定", ABSTAIN: "材料から決められない"},
        "materials": {"source": "excerpt.逐語", "before": "excerpt.前", "after": "excerpt.後"},
        "flag_on": ["他者の紹介"],
        "cleared_by": "excerpt.孫引き",
    },
    {
        "type": "cite.not_said", "version": 2, "for": "excerpt",
        # 「言っていないこと」は否定の文なので、書かれているかを訊くと逆転する（実機の試験 2026-10-15）。文そのものが正しいかを訊く
        "question": "次の文は、原典の逐語と前後の文の内容に照らして、正しいか。 {about}",
        "labels": ["正しい", "誤り", ABSTAIN],
        "gloss": {"正しい": "逐語と前後の文の内容と矛盾しない", "誤り": "逐語か前後の文が、この文に反することを述べている",
                  ABSTAIN: "材料から決められない"},
        "materials": {"source": "excerpt.逐語", "before": "excerpt.前", "after": "excerpt.後"},
        "about": "excerpt.言っていないこと",
        "flag_on": ["誤り"],
    },
]

SLOT_NAMES = {"claim": "本文の文", "source": "原典の逐語", "before": "逐語の前の文", "after": "逐語の後の文",
              "not_said": "原典が言っていないこと"}
# 抜き書きの欄名 -> review_data の根拠（evidence）の鍵
EXCERPT_FIELDS = {"逐語": "verbatim", "前": "before", "含む文": "sentence", "後": "after",
                  "強さ": "strength", "要約": "summary", "言っていないこと": "not_said", "孫引き": "secondary"}
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
    if c.get("cleared_by") and c.get("compare"):
        sys.exit(f"型 {t}: cleared_by と compare は一緒に使えない（記録で消す型と、記録と比べる型は別）")
    paths = list(c["materials"].values()) + [c[k] for k in ("compare", "about", "cleared_by") if c.get(k)]
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
    if c.get("order"):
        if not c.get("compare"):
            sys.exit(f"型 {t}: order は compare と一緒に使う（記録と重さを比べるため）")
        for group in c["order"]:
            for lab in group:
                if lab not in c["labels"] or lab == ABSTAIN:
                    sys.exit(f"型 {t}: order の '{lab}' が labels に無い（「{ABSTAIN}」は入れない）")
    if c.get("on_disagree", "flag") != "flag":
        sys.exit(f"型 {t}: on_disagree は flag だけ（要再確認へ下げる動作は、人の承認との一致率を測ってから）")


def spec_fp(c):
    """型の文面・選択肢・説明の指紋。変えると、以前の判定は古くなる（version を上げ忘れても）。"""
    return _fp(json.dumps([c["question"], c["labels"], sorted(c.get("gloss", {}).items())], ensure_ascii=False))


# ---------------------------------------------------------------- 単位（引用と抜き書き）と材料

CONTEXT_CAP = 200  # 前後の文の上限の字数。抽出の残骸（図の文字、頁の頭書き）が一文に繋がって長くなるのを切る


# 括弧（中に一段の半角括弧を含んでよい。「28(1)」のような巻号）
PAREN_RE = re.compile(r"[（(](?:[^（）()\n]|\([^()\n]*\))*[）)]")
YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")


def clean_claim(sentence):
    """本文の文から、引用の印と出典の括弧を外す。どの出典かは、問いの側で名指す（citation.出典）。

    出典の括弧は、年を含む括弧と、設定の coverage.pattern に当たる括弧。頁だけの括弧（p.49）は残す。
    """
    def drop(m):
        inner = m.group(0)
        flat = re.sub(r"\(([^()]*)\)", r"\1", inner[1:-1])
        return "" if YEAR_RE.search(flat) or cfg.COVER_RE.fullmatch(inner[0] + flat + inner[-1]) else inner
    s = PAREN_RE.sub(drop, unmark(sentence))
    return re.sub(r"[ 　]{2,}", " ", s).strip()


def source_label(keys, bib):
    """根拠の文献の短い名前（筆頭著者と年）。問いの中で、文のどの部分を見るかを名指すのに使う。"""
    out = []
    for k in keys:
        entry = (bib.get(k) or {}).get("entry", "")
        m = re.match(r"\s*(.+?)[.,]?\s*[（(](\d{4}|n\.d\.)[a-z]?[)）]", entry)
        if not m:
            out.append(k)
            continue
        authors, year = m.group(1).strip(), m.group(2)
        many = authors.count(",") >= 2 or "&" in authors or " and " in authors or "、" in authors
        first = authors.split(",")[0].split("、")[0].strip()
        out.append(f"{first}{' ら' if many else ''}（{year}）" if year != "n.d." else first)
    return "・".join(dict.fromkeys(out))


def units_from_data(data, bib=None):
    """review_data の結果から、判定の単位を作る。引用（主張）ごとと、抜き書きごと。"""
    if bib is None:
        from .bib import parse_bib
        bib = parse_bib()
    units, seen = [], set()
    for it in data["citations"]:
        if it["kind"] != "主張":
            continue
        ev = [e for e in it["evidence"] if not e.get("missing") and not e.get("new")]
        keys = list(dict.fromkeys(e["id"].split("#")[0] for e in ev))
        units.append({"item": f"cite:{it['id']}", "scope": "citation", "id": it["id"], "sentence": clean_claim(it["sentence"]),
                      "source": source_label(keys, bib), "fields": it["fields"], "excerpts": ev})
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
        if name == "出典":
            return [unit.get("source", "")]
        return [unit.get("fields", {}).get(name, "")]
    key = EXCERPT_FIELDS.get(name)
    if key is None:
        return [""]
    return [e.get(key, "") or "" for e in unit["excerpts"]]


def _cap(text, keep_end):
    if len(text) <= CONTEXT_CAP:
        return text
    return "…" + text[-CONTEXT_CAP:] if keep_end else text[:CONTEXT_CAP] + "…"


def text_at(unit, path):
    """材料の文面。根拠が複数なら、抜き書きの ID を付けて並べる。前後の文は CONTEXT_CAP で切る（逐語に近い側を残す）。"""
    kind, name = PATH_RE.match(path).groups()
    vals = values_at(unit, path)
    if kind == "excerpt" and name in ("前", "後", "before", "after"):
        vals = [_cap(v, keep_end=name in ("前", "before")) for v in vals]
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


def _rank(order, label):
    return next((i for i, group in enumerate(order) if label in group), None)


def cleared(check, unit):
    """型の cleared_by の欄に値があるか（記録で印が消えるか）。cleared_by の無い型は False。"""
    if not check.get("cleared_by"):
        return False
    return any(v for v in values_at(unit, check["cleared_by"]))


def judge_status(check, label, record, is_cleared=False):
    """分類器のラベルを、記録（compare の欄の値）と突き合わせた結果。確からしさは使わない。
    is_cleared は cleared_by の欄に値があるか（§6.4）。flag_on のラベルでも記録があれば 一致 とする。

    型が order（軽い順のラベルの組）を持てば、記録より重いと判定したときだけ食い違い（印）にし、軽いと判定したときは
    記録より軽い（印にしない）とする。人が記録したずれより小さいと言われても、直す理由にならないため。
    """
    if label == ABSTAIN:
        return "判定できない"
    if check.get("compare"):
        vals = [v for v in record if v]
        if not vals:
            return "記録なし"
        order = check.get("order")
        if order:
            lr = _rank(order, label)
            rr = [r for r in (_rank(order, v) for v in vals) if r is not None]
            if lr is not None and rr:
                top = max(rr)
                return "一致" if lr == top else ("食い違い" if lr > top else "記録より軽い")
        return "一致" if label in vals else "食い違い"
    if label in check.get("flag_on", []):
        return "一致" if is_cleared else "要確認"
    return "問題なし"


FLAGGED = ("食い違い", "要確認")


# ---------------------------------------------------------------- 台帳

def read_ledger():
    """台帳を読み、((item, type) ごとの最新の判定, 読めなかった行の番号の並び)を返す。
    読めない行は飛ばす。読めないのは、UTF-8 でない行、JSON でない行、JSON の対象でも item・type・label（文字列）の無い行
    （読み手がこの三つを直接引く。version・spec・mat の無い行は、古い判定として数えるだけ）。
    台帳は追記だけで、同じ組の後のものが新しい。"""
    out, bad = {}, []
    p = cfg.JUDGMENTS
    if p and p.exists():
        for n, raw in enumerate(p.read_bytes().split(b"\n"), 1):
            raw = raw.rstrip(b"\r")
            if not raw.strip():
                continue
            try:
                e = json.loads(raw.decode("utf-8"))
                if not (isinstance(e, dict) and all(isinstance(e.get(k), str) for k in ("item", "type", "label"))):
                    raise ValueError("item・type・label が文字列で無い")
            except (UnicodeDecodeError, ValueError, RecursionError):  # 深すぎる入れ子は RecursionError（ValueError ではない）
                bad.append(n)
                continue
            out[(e["item"], e["type"])] = e
    return out, bad


def load_ledger():
    """(item, type) ごとの最新の判定。読めない行は飛ばす（read_ledger）。"""
    return read_ledger()[0]


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
                             "status": judge_status(c, e["label"], record, cleared(c, u)) if is_fresh else "古い"})
        if rows:
            it["classifier"] = rows


def count_judgments(units, checks=None, ledger=None):
    """今の判定を数える。classify --list・check・マニフェストは、この一つの数え方を使う。

    数えるのは、台帳の最新の判定のうち、今の型（登録と版と文面）に合い、今の材料（本文・逐語）と突き合わせて新しいもの
    （fresh）。記録との比較は今の記録で行い、cleared_by を含む。古い判定は数えず、件数（stale）だけ返す。
    単位（引用・抜き書き）が無くなった判定と、型が無くなった判定も古いに数える。
    返り値は {"rows": [(item, 型, 判定, score, 記録, 状態)], "stale": K, "flagged": M}。判定の件数は len(rows)。
    """
    if ledger is None:
        ledger = load_ledger()
    if not ledger:
        return {"rows": [], "stale": 0, "flagged": 0}
    checks = registry() if checks is None else checks
    by_type = {c["type"]: c for c in checks}
    unit_by = {u["item"]: u for u in units}
    rows, stale = [], 0
    for (item, t), e in sorted(ledger.items()):
        c, u = by_type.get(t), unit_by.get(item)
        b = build(c, u) if c and u else None
        if not b or not fresh(e, c, b[2]):
            stale += 1
            continue
        record = [v for p in [c.get("compare")] if p for v in values_at(u, p) if v]
        rows.append((item, t, e["label"], e.get("score"), record, judge_status(c, e["label"], record, cleared(c, u))))
    return {"rows": rows, "stale": stale, "flagged": sum(1 for r in rows if r[5] in FLAGGED)}


# ---------------------------------------------------------------- 要求と送信

def plan_requests(units, checks, ledger=None, max_chars=6000):
    """(要求の並び, 材料が長すぎる件数, 判定済みの件数)。同じ単位で材料が同じ問いは、一つの要求にまとめる。"""
    requests, too_long, done = {}, 0, 0
    for u in units:
        for c in checks:
            if c["for"] != u["scope"]:
                continue
            b = build(c, u)
            if b is None:
                continue
            state, about, mat = b
            if ledger is not None and fresh(ledger.get((u["item"], c["type"])), c, mat):
                done += 1
                continue
            if len(state) + len(about) > max_chars:
                too_long += 1
                continue
            req = requests.setdefault((u["item"], state), {"item": u["item"], "state": state, "asks": [], "unit": u})
            req["asks"].append((c, about, mat))
    return list(requests.values()), too_long, done


def estimate(reqs):
    n_asks = sum(len(r["asks"]) for r in reqs)
    chars = sum(len(r["state"]) + sum(len(a[1]) for a in r["asks"]) for r in reqs)
    return f"送る予定: 要求 {len(reqs)} 回、問い {n_asks} 件、約 {chars} 字"


def _classifier_or_stop(send):
    """提供元を作る。設定が無い、または --send が無いときは、理由を出して None。"""
    clf = make_classifier(cfg.CLASSIFIER, env_dirs=[cfg.CONFIG_USED.parent, Path.cwd()])
    if clf is None:
        print("[classifier] provider が設定に無いので送れない（README「分類器」）")
        return None
    warn = endpoint_warning(clf)
    if warn:
        print(warn)
    if not send:
        print(f"送る相手: {clf.name}（{clf.model}）。原稿の文と原典の逐語・前後の文が外部のサービスへ渡り、課金される。"
              "送るには --send を付ける。")
        return None
    print(f"送る相手: {clf.name}（{clf.model}）。原稿の文と原典の逐語・前後の文が外部のサービスへ渡る。")
    return clf


def endpoint_warning(clf):
    """送る宛先が提供元の既定と違うか、https でないときの注意の文。鍵はその宛先へ送られる。問題が無ければ空。"""
    url, default = getattr(clf, "endpoint", ""), getattr(clf, "default_endpoint", "")
    if not url:
        return ""
    notes = []
    if default and url != default:
        notes.append(f"既定（{default}）と違う")
    if not url.startswith("https://") and not url.startswith(("http://127.0.0.1", "http://localhost")):
        notes.append("https でない")
    return f"注意: 送る宛先 {url} は{'、'.join(notes)}。鍵と材料はこの宛先へ送られる。" if notes else ""


def send_requests(clf, reqs):
    """要求ごとに (要求, [(問い, Verdict | None)] | None) を返す。None は要求全体の失敗（理由は出力する）。"""
    for r in reqs:
        asks = [Ask(type=c["type"], labels=tuple(c["labels"]), question=c["question"],
                    gloss=tuple(sorted(c.get("gloss", {}).items())), about=about) for c, about, _ in r["asks"]]
        try:
            verdicts = clf.classify(r["state"], asks)
        except ClassifierUnavailable as exc:
            print(f"SKIP {r['item']}: {exc}")
            yield r, None
            continue
        yield r, list(zip(r["asks"], verdicts))


# ---------------------------------------------------------------- 言語の組

def lang_of(text):
    """文の言語の大まかな判別。仮名か漢字を含めば ja、欧字だけなら en（英語以外の欧文も en に数える）、どちらも無ければ空。

    日本語の本文は英語のコマンド名や製品名を含むことが多いので、字数の多寡ではなく、仮名・漢字の有無で決める。
    """
    if re.search(r"[぀-ヿ一-鿿]", text):
        return "ja"
    return "en" if re.search(r"[A-Za-z]", text) else ""


def lang_pair(unit):
    """本文と原典の言語の組（本文/原典、例 ja/en）。根拠の逐語が複数の言語にまたがれば ja+en のように並べる。
    抜き書きの単位は本文を持たないので、原典の言語だけ（例 en）。"""
    src = "+".join(sorted({lang_of(v) for v in values_at(unit, "excerpt.逐語")} - {""})) or "?"
    if unit.get("scope") == "excerpt":
        return src
    return f"{lang_of(unit.get('sentence', '')) or '?'}/{src}"



def manifest_record(units):
    """マニフェストの classifier 欄。分類器を設定せず、台帳も無ければ None。units は呼ぶ側が review_data から作って渡す。

    型は、設定の [[checks]] で足せる。足したら、ここに型の名前・版・文面の指紋が載る（何に対して判定したかが残る）。
    """
    ledger = load_ledger()
    if not cfg.CLASSIFIER and not ledger:
        return None
    s = count_judgments(units, ledger=ledger)
    return {
        "provider": cfg.CLASSIFIER.get("provider", ""), "model": cfg.CLASSIFIER.get("model", ""),
        "types": [{"type": c["type"], "version": c["version"], "spec": spec_fp(c)} for c in registry()],
        "judgments": len(s["rows"]), "flagged": s["flagged"], "stale": s["stale"],
        "note": "型は bridge.toml の [[checks]] に足せる（同じ type は上書き）。文面か選択肢を変えると spec が変わり、以前の判定は古くなる。"
                "確からしさは規則に使わない。印を立てるだけで、承認の状態は変えない（README「分類器」）。",
    }
