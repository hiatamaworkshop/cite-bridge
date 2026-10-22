# -*- coding: utf-8 -*-
"""印の無い出典の候補づくり（propose・sentences・候補の検査と受け入れ）。"""
from pathlib import Path
import datetime
import hashlib
import re
import sys
from . import config as cfg
from .approve import load_excerpt_fields, write_approval, write_confirm
from .bib import extraction_diagnosis, grade_of, parse_bib
from .blocks import parse_blocks, rewrite_derived
from .config import DIFFS, STRENGTHS, out_name
from .derive import derive_excerpts, printed_page
from .manuscript import (
    coverage_items,
    load_excluded,
    mask_comments,
    sentence_bounds,
    summary_fingerprint,
    unmark,
)
from .source import SENT_END, Source, locate, normalize, section_at
from .util import _sha256


# ---------------------------------------------------------------- 候補（作業票・下書き・受け入れ）
#
# 道具は拾う・絞る・確かめる・書く。書き手の AI は選ぶ・解釈の欄を書く。人は受け入れる（構想メモ §18）。
# 候補の逐語は、道具が原典から写した範囲だけである。書き手は文の番号と、その中の部分の文字列で範囲を指す。

def source_sentences(src):
    """原典の本文を文に分け、(開始, 終了) の並びを返す。番号は作業票と下書きで共有するので、同じテキストなら同じになる。"""
    lo = src.body_start
    ends = {m.end() for m in SENT_END.finditer(src.raw, lo)}
    ends |= {m.end() for m in re.compile(r"\n[ \t]*\n").finditer(src.raw, lo)}  # 段落の区切り（頁の区切りでは切らない。文は頁をまたぐ）
    ends |= {h[3] for h in src.headings if h[3] >= lo}
    ends |= {h[0] for h in src.headings if h[0] > lo}  # 見出しの行の前でも切る
    ends.add(len(src.raw))
    out, a = [], lo
    for e in sorted(x for x in ends if x > lo):
        if ABBREV_END.search(src.raw[a:e]) and "\n\n" not in src.raw[a:e][-3:] and e < len(src.raw):
            continue  # et al. や e.g. の後では切らない（次の区切りまで伸ばす）
        if len(normalize(src.raw[a:e], "alnum")[0]) >= 4:
            out.append((a, e))
        a = e
    return out


ABBREV_END = re.compile(r"(?<![A-Za-z])(?:al|e\.g|i\.e|cf|vs|etc|Fig|Figs|Eq|Sec|pp|p|No|Vol|Dr|Mr|Ms|St)\.\s*$")


def sentence_text(src, a, b):
    x = re.sub(r"(\w)-\s*\n\s*([a-z])", r"\1\2", src.raw[a:b])
    return normalize(x.replace("\f", " "), "ws")[0].strip()


def _feats(s):
    from collections import Counter
    t = normalize(s, "nfkc")[0]
    a = re.sub(r"[\W_]+", "", t)
    f = Counter(a[i:i + 2] for i in range(len(a) - 1))
    f.update(w for w in re.findall(r"[a-z]{3,}", t))
    return f


def rank_texts(query, texts):
    """query に近い順の添字。文字の二字組と英単語の重なりを、出現の少ないものを重く数える（構想メモ §18.1 の試し）。"""
    import math
    qf = _feats(query)
    fs = [_feats(t) for t in texts]
    df = {}
    for f in fs:
        for g in f:
            df[g] = df.get(g, 0) + 1
    n = len(texts)
    scores = []
    for i, f in enumerate(fs):
        num = sum(min(qf[g], f[g]) * math.log((n + 1) / (df[g] + 0.5)) for g in qf if g in f)
        scores.append((num / (math.sqrt(sum(f.values())) or 1), i))
    return [i for s, i in sorted(scores, key=lambda x: -x[0])]


def resolve_keys(window, bib, limit=3):
    """出典の括弧（と直前の語）から、書誌の key の候補を点数の順に返す。年が合うこと、著者の部分に名前があることを重く見る。"""
    years = set(re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", window))
    latin = {w.lower() for w in re.findall(r"[A-Z][A-Za-z\x27-]{2,}", window)} - {"proceedings", "the", "and"}
    kanji = set(re.findall(r"[㐀-鿿]{2,4}", window))
    res = []
    for key, b in bib.items():
        entry = b["entry"]
        m = re.search(r"[（(]\s*(?:(?:19|20)\d{2}|n\.d\.)", entry)
        authors = entry[:m.start()] if m else entry[:80]
        al, el = authors.lower(), entry.lower()
        score, why = 0, []
        for w in latin:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", al):
                score += 3
                why.append(w)
            elif re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", el):
                score += 1
        for w in kanji:
            if w in authors:
                score += 3
                why.append(w)
        ey = set(re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", entry))
        if years and years & ey:
            score += 2
        elif years and ey:
            score -= 2
        if score >= 3 and why:
            res.append({"key": key, "score": score, "entry": entry})
    res.sort(key=lambda x: (-x["score"], x["key"]))
    return res[:limit]


def _clause(text, c, items):
    """括弧が受け持つ句。同じ文の前の出典の括弧から、次の出典の括弧まで（日本語は「小林（2002）は…」と後ろに述べる形が多い）。"""
    a, z = sentence_bounds(text, c["off"])
    same = [x for x in items if a <= x["off"] < z]
    prev = [x for x in same if x["off"] < c["off"]]
    nxt = [x for x in same if x["off"] > c["off"]]
    lo = prev[-1]["end"] if prev else a
    hi = nxt[0]["off"] if nxt else z
    return re.sub(r"\s+", " ", cfg.MARK_RE.sub("", text[lo:hi])).strip()


def _sources_for(key, bib, cache):
    grade, txt = grade_of(key, bib)
    if not txt:
        return grade, None
    if txt not in cache:
        cache[txt] = Source(txt)
    return grade, cache[txt]


def load_candidates():
    import json
    p = cfg.CAND_DIR / "candidates.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"format": "cite-bridge-candidates/1", "items": {}}


def save_candidates(c):
    import json
    cfg.CAND_DIR.mkdir(parents=True, exist_ok=True)
    (cfg.CAND_DIR / "candidates.json").write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def candidate_fp(c):
    """候補の指紋。人が見た候補と、受け入れるときの候補が同じかを確かめる。"""
    import json
    body = {k: v for k, v in c.items() if k not in ("status", "loaded", "decided")}
    return hashlib.sha1(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:8]


def _manuscript():
    head, _ = parse_blocks(cfg.CIT)
    return Path(head["fields"].get("対象", ""))


CHECKABLE_GRADES = ("PDF所持（抽出あり）", "Web 写し（保存あり）")


def cmd_propose(args):
    """印の無い出典ごとに作業票を作る（--load なら、書き手の下書きを検査して候補として置く）。"""
    if args.load:
        return _load_drafts(args)
    import json
    bib = parse_bib()
    target = _manuscript()
    text = mask_comments(target.read_text(encoding="utf-8"))
    items = coverage_items(text)
    cands = load_candidates()["items"]
    extra = {}
    for s in args.add_key or []:
        q, _, k = s.partition("=")
        if k not in bib:
            sys.exit(f"--add-key {s}: key '{k}' が書誌に無い")
        extra.setdefault(q, []).append(k)
    exc = load_excerpt_fields()
    lo, hi = (int(x) for x in args.lines.split("-")) if args.lines else (0, 10 ** 9)
    picked = [c for c in items if not c["marked"] and not c["excluded"] and lo <= c["line"] <= hi
              and (not args.section or args.section in c["section"])
              and cands.get(c["item"], {}).get("status") not in ("accepted",)
              and (not args.items or c["item"] in args.items)]
    resolved = []
    for c in picked:  # key の候補は絞り込みに使うので、--limit で切る前に出す
        window = text[max(0, c["off"] - 30):c["end"]]
        keys = resolve_keys(window, bib)
        for k in extra.get(c["item"], []):
            if k not in [x["key"] for x in keys]:
                keys.insert(0, {"key": k, "score": None, "entry": bib[k]["entry"]})
        if args.key and not set(args.key) & {x["key"] for x in keys}:
            continue
        if args.checkable and not (keys and grade_of(keys[0]["key"], bib)[0] in CHECKABLE_GRADES):
            continue
        resolved.append((c, keys))
    cache, work = {}, []
    for c, keys in resolved[:args.limit]:
        clause = _clause(text, c, items)
        query = cfg.COVER_RE.sub(" ", clause)  # 出典の括弧の名前と年で、原典の中の別の引用が上位に来ないように外す
        w = {"item": c["item"], "line": c["line"], "section": c["section"], "paren": c["paren"], "nth": c["nth"],
             "sentence": unmark(c["sentence"]), "fingerprint": c["fingerprint"], "clause": clause, "keys": []}
        prior = cands.get(c["item"])
        if prior and prior.get("status") == "rejected":
            w["rejected_before"] = prior.get("decided", {})
        for k in keys:
            grade, src = _sources_for(k["key"], bib, cache)
            diagnosis = [text for _, text in extraction_diagnosis(k["key"], bib, src.path)] if src else []
            kk = {"key": k["key"], "score": k["score"], "entry": k["entry"], "grade": grade, "diagnosis": diagnosis,
                  "text": None, "existing": [], "passages": []}
            own = {eid: f for eid, f in exc.items() if eid.split("#")[0] == k["key"]}
            if own:
                ids = list(own)
                for i in rank_texts(query, [own[e].get("逐語", "") + " " + own[e].get("要約", "") for e in ids])[:args.top]:
                    kk["existing"].append({"id": ids[i], "verbatim": own[ids[i]].get("逐語", ""), "summary": own[ids[i]].get("要約", "")})
            if src:
                kk["text"] = src.path.as_posix()
                kk["text_sha"] = _sha256(src.path)
                spans = source_sentences(src)
                texts = [sentence_text(src, a, b) for a, b in spans]
                kinds = [section_at(src, a) for a, b in spans]
                order = [i for i in rank_texts(query, texts) if kinds[i][1] != "参考文献"]
                for i in order[:args.top]:
                    a, b = spans[i]
                    kk["passages"].append({"n": i, "location": printed_page(bib[k["key"]]["entry"], src.page_of(a), src.pages(), src)
                                           + " / " + kinds[i][0], "section_kind": kinds[i][1], "text": texts[i][:600],
                                           "before": texts[i - 1][-200:] if i else "", "after": texts[i + 1][:200] if i + 1 < len(texts) else ""})
            w["keys"].append(kk)
        work.append(w)
    cfg.CAND_DIR.mkdir(parents=True, exist_ok=True)
    out = {"format": "cite-bridge-work/1", "manuscript": target.as_posix(),
           "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "items": work}
    (cfg.CAND_DIR / "work.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (cfg.CAND_DIR / "work.md").write_text(work_md(out), encoding="utf-8", newline="\n")
    rest = sum(1 for c in items if not c["marked"] and not c["excluded"])
    print(f"ok propose: {(cfg.CAND_DIR / 'work.md').as_posix()} と work.json（{len(work)} 件。印の無い出典は全部で {rest}）")
    print(f"下書きは {(cfg.CAND_DIR / 'drafts.json').as_posix()} に書き、propose --load で候補にする（書き方は SKILL.md）")


def cmd_sentences(args):
    """原典を作業票と同じ番号の文に分けて出す。--grep で絞る（書き手が原典の言葉で引くため。和文の句と英語の原典では順位付けが効かない）。"""
    bib = parse_bib()
    if args.key not in bib:
        sys.exit(f"key '{args.key}' が書誌に無い")
    grade, src = _sources_for(args.key, bib, {})
    if not src:
        sys.exit(f"{args.key} は原典のテキストが無い（{grade}）")
    spans = source_sentences(src)
    lo, hi = (int(x) for x in args.range.split("-")) if args.range else (0, len(spans) - 1)
    pats = [normalize(g, "nfkc")[0] for g in args.grep or []]
    shown = 0
    for i in range(max(0, lo), min(hi, len(spans) - 1) + 1):
        t = sentence_text(src, *spans[i])
        if pats and not all(p in normalize(t, "nfkc")[0] for p in pats):
            continue
        a = spans[i][0]
        loc = printed_page(bib[args.key]["entry"], src.page_of(a), src.pages(), src) + " / " + section_at(src, a)[0]
        print(f"n={i} [{loc}] {t}")
        shown += 1
    print(f"--- {shown} 文（{args.key} は全部で {len(spans)} 文、{src.path.as_posix()}）")


def work_md(w):
    out = [f"# 作業票（{w['generated']}、{w['manuscript']}）", "",
           "下書きは drafts.json に書く。逐語は文の番号（n）で指し、文字列は道具が原典から写す。",
           "上位の文に無ければ `sentences <key> --grep <語>` で原典を同じ番号のまま引く。", ""]
    for it in w["items"]:
        out += [f"## {it['item']}　{it['paren']}（{it['line']} 行、{it['section']}）", "", f"文: {it['sentence']}", "",
                f"受け持つ句: {it['clause']}", ""]
        if it.get("rejected_before"):
            out += [f"前の候補は却下された: {it['rejected_before']}", ""]
        if not it["keys"]:
            out += ["key の候補なし（書誌に無いか、括弧から名前を拾えない。--add-key で足せる）", ""]
        for k in it["keys"]:
            out += [f"### {k['key']}（点 {k['score']}、{k['grade']}）", "", f"- {k['entry']}"]
            if k["diagnosis"]:
                out.append(f"- 抽出の診断: {'；'.join(k['diagnosis'])}")
            for e in k["existing"]:
                out.append(f"- 既存 {e['id']}: {e['verbatim'][:160]}")
            for p in k["passages"]:
                out.append(f"- n={p['n']} [{p['location']}・{p['section_kind']}] {p['text'][:300]}")
            if not k["text"]:
                out.append("- 原典のテキストなし（指示にするか、入手する）")
            out.append("")
    return "\n".join(out) + "\n"


def _load_drafts(args):
    """書き手の下書き（drafts.json）を検査し、候補（candidates.json）に置く。検査に通らないものは置かずに理由を出す。"""
    import json
    bib = parse_bib()
    work = json.loads((cfg.CAND_DIR / "work.json").read_text(encoding="utf-8"))
    witems = {w["item"]: w for w in work["items"]}
    drafts = json.loads(Path(args.load).read_text(encoding="utf-8"))
    if drafts.get("format") != "cite-bridge-drafts/1":
        sys.exit("下書きの形式が違う（format: cite-bridge-drafts/1 を期待）")
    text = mask_comments(_manuscript().read_text(encoding="utf-8"))
    now = {c["item"]: c for c in coverage_items(text)}
    store = load_candidates()
    exc = load_excerpt_fields()
    cache, ok, bad = {}, [], []
    for d in drafts.get("items", []):
        it = d.get("item")
        problems = []
        w, cur = witems.get(it), now.get(it)
        if not w:
            problems.append("作業票に無い item")
        if not cur:
            problems.append("原稿のその文が作業票を作った後に変わった（propose をやり直す）")
        elif cur["marked"]:
            problems.append("その括弧には既に印がある")
        kind = d.get("kind")
        if kind not in ("主張", "指示", "引用でない"):
            problems.append("kind は 主張・指示・引用でない のどれか")
        cand = {"item": it, "kind": kind, "理由": d.get("理由", ""), "記入": d.get("記入", "")}
        if w:
            cand.update({k: w[k] for k in ("line", "section", "paren", "nth", "sentence", "fingerprint")})
        if not cand["理由"]:
            problems.append("理由が空")
        if kind in ("主張", "指示"):
            key = d.get("key")
            cand["key"] = key
            if key not in bib:
                problems.append(f"key '{key}' が書誌に無い")
            if not cand["記入"]:
                problems.append("記入が空")
        if kind == "主張" and not problems:
            for n in ("解釈", "原文との差", "引用でない句"):
                if d.get(n):
                    cand[n] = d[n]
            if cand.get("原文との差") not in DIFFS:
                problems.append(f"原文との差は {sorted(DIFFS)} のどれか")
            wk = next((k for k in w["keys"] if k["key"] == key), None) if w else None
            refs = []
            for x in d.get("excerpts", []):
                if x.get("use"):
                    eid = x["use"] if "#" in x["use"] else f"{key}#{x['use']}"
                    if eid not in exc:
                        problems.append(f"既存の抜き書き {eid} が無い")
                    refs.append({"use": eid})
                    continue
                if not wk or not wk.get("text"):
                    problems.append(f"{key} は作業票に原典のテキストが無い（新しい抜き書きは作れない。--add-key で作業票に足す）")
                    continue
                grade, src = _sources_for(key, bib, cache)
                if not src or _sha256(src.path) != wk.get("text_sha"):
                    problems.append(f"{key} の原典のテキストが作業票を作った後に変わった")
                    continue
                spans = source_sentences(src)
                ns = x.get("sentences") or []
                if not ns or any(not isinstance(n, int) or n < 0 or n >= len(spans) for n in ns) or max(ns) - min(ns) > 5:
                    problems.append(f"sentences {ns} が原典の文の番号として正しくない（連続した6文まで）")
                    continue
                joined = " ".join(sentence_text(src, *spans[n]) for n in range(min(ns), max(ns) + 1))
                joined = normalize(joined, "ws")[0]
                s = joined.find(x["from"]) if x.get("from") else 0
                if s < 0:
                    problems.append(f"from '{x['from'][:20]}' が文 {ns} の中に無い")
                    continue
                e = joined.find(x["to"], s) + len(x["to"]) if x.get("to") else len(joined)
                if x.get("to") and e < len(x["to"]):
                    problems.append(f"to '{x['to'][:20]}' が文 {ns} の中に無い（from より後で）")
                    continue
                verb = joined[s:e].strip()
                label, a, _ = locate(verb, src)
                if a is None or label.startswith("近似"):
                    problems.append(f"写した逐語が原典で一致しない（{label}）")
                    continue
                for n in ("強さ", "要約", "言っていないこと"):
                    if not x.get(n):
                        problems.append(f"新しい抜き書きの {n} が空")
                if x.get("強さ") and x["強さ"] not in STRENGTHS:
                    problems.append(f"強さは {sorted(STRENGTHS)} のどれか")
                refs.append({"new": True, "逐語": verb, "強さ": x.get("強さ", ""), "要約": x.get("要約", ""),
                             "言っていないこと": x.get("言っていないこと", ""), "sentences": [min(ns), max(ns)]})
            if not refs:
                problems.append("主張の候補に抜き書きが無い")
            cand["excerpts"] = refs
        if problems:
            bad.append(f"{it}: " + "／".join(problems))
            continue
        cand["status"] = "pending"
        cand["loaded"] = datetime.datetime.now().isoformat(timespec="seconds")
        store["items"][it] = cand
        ok.append(it)
    if ok:
        save_candidates(store)
    for m in bad:
        print("SKIP", m)
    print(f"--- 候補にした {len(ok)} 件、断った {len(bad)} 件。人は review --html で受け入れるか却下する")
    if bad:
        sys.exit(1)


def _next_cid():
    _, blocks = parse_blocks(cfg.CIT)
    nums = [int(b["id"][1:]) for b in blocks if re.fullmatch(r"c\d+", b["id"])]
    return f"c{(max(nums) + 1 if nums else 1):03d}"


def _append_block(path, lines):
    body = path.read_text(encoding="utf-8").rstrip("\n") + "\n\n" if path.exists() else ""
    path.write_text(body + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def apply_candidate(item, action, by, note, cfp, dry=False):
    """候補を受け入れる（抜き書き・引用のブロックを書き、原稿に印を置き、承認と要約の確認を記録する）か、却下を記録する。"""
    import json
    store = load_candidates()
    c = store["items"].get(item)
    if not c or c.get("status") != "pending":
        return False, f"{item}: 判断を待つ候補が無い"
    if candidate_fp(c) != cfp:
        return False, f"{item}: 判断した後に候補が変わった。書かなかった（review を作り直して見直す）"
    target = _manuscript()
    raw = target.read_bytes().decode("utf-8")  # 改行を変えずに書き戻すため、改行の変換をせずに読む
    cur = next((x for x in coverage_items(mask_comments(raw)) if x["item"] == item), None)
    if not cur:
        return False, f"{item}: 原稿のその文が変わった。書かなかった"
    if cur["marked"]:
        return False, f"{item}: その括弧には既に印がある"
    today = datetime.date.today().isoformat()
    if action == "reject":
        if not note:
            return False, f"{item}: 却下には理由が要る"
        if not dry:
            c["status"] = "rejected"
            c["decided"] = {"by": by, "date": today, "reason": note}
            save_candidates(store)
        return True, f"候補を却下: {item}（{note}）"
    if c["kind"] == "引用でない":
        if not dry:
            ex = load_excluded()
            ex.append({"item": item, "paren": cur["paren"], "nth": cur["nth"], "fingerprint": cur["fingerprint"],
                       "line": cur["line"], "reason": c["理由"], "by": by, "date": today})
            cfg.EXCLUDED.write_text(json.dumps(ex, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            c["status"] = "accepted"
            c["decided"] = {"by": by, "date": today, "excluded": True}
            save_candidates(store)
        return True, f"引用でないと記録: {cur['paren']}（{cur['line']} 行）"
    if not cfg.MARK_FORMAT:
        return False, f"{item}: 印の形（manuscript.mark_format）が設定に無いので、原稿に印を置けない"
    cid = _next_cid()
    if dry:
        return True, f"{item}: 受け入れ（{cid} になる）"
    refs, new_eids = [], []
    if c["kind"] == "主張":
        path = cfg.EXC_DIR / f"{c['key']}.md"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {c['key']}\n", encoding="utf-8", newline="\n")
        for x in c["excerpts"]:
            if x.get("use"):
                refs.append(x["use"])
                continue
            _, blocks = parse_blocks(path)
            # 同じ逐語の抜き書きが既にあれば使う（同じ回の別の候補が先に作ったもの等）。要約はその抜き書きのものが残る
            same = next((b for b in blocks if re.sub(r"\s", "", b["fields"].get("逐語", "")) == re.sub(r"\s", "", x["逐語"])), None)
            if same:
                refs.append(f"{c['key']}#{same['id']}")
                if summary_fingerprint(same["fields"]) == summary_fingerprint(x):  # 人が見た要約と同じときだけ確認を記録する
                    new_eids.append(f"{c['key']}#{same['id']}")
                continue
            nums = [int(b["id"][1:]) for b in blocks if re.fullmatch(r"e\d+", b["id"])]
            eid = f"e{(max(nums) + 1 if nums else 1)}"
            _append_block(path, [f"## {eid}", f"{out_name('逐語')}: {x['逐語']}", f"{out_name('強さ')}: {x['強さ']}",
                                 f"{out_name('要約')}: {x['要約']}", f"{out_name('言っていないこと')}: {x['言っていないこと']}",
                                 f"{out_name('記入')}: {c['記入']}（候補 {item} から）"])
            refs.append(f"{c['key']}#{eid}")
            new_eids.append(f"{c['key']}#{eid}")
        lines = [f"## {cid}", f"{out_name('種類')}: 主張", f"{out_name('抜き書き')}: {', '.join(refs)}", f"{out_name('理由')}: {c['理由']}"]
        lines += [f"{out_name(n)}: {c[n]}" for n in ("解釈", "原文との差", "引用でない句") if c.get(n)]
    else:
        lines = [f"## {cid}", f"{out_name('種類')}: 指示", f"{out_name('文献')}: {c['key']}", f"{out_name('理由')}: {c['理由']}"]
    lines.append(f"{out_name('記入')}: {c['記入']}（候補 {item} から）")
    _append_block(cfg.CIT, lines)
    raw = raw[:cur["end"]] + cfg.MARK_FORMAT.format(id=cid, key=c["key"]) + raw[cur["end"]:]
    target.write_text(raw, encoding="utf-8", newline="")
    if new_eids:
        for path, (hd, bd) in derive_excerpts(parse_bib(), {}).items():
            if path == cfg.EXC_DIR / f"{c['key']}.md":
                rewrite_derived(path, hd, bd)
    msgs = [f"候補を受け入れた: {item} → {cid}（{cur['line']} 行）"]
    if c["kind"] == "主張":  # 受け入れは承認を兼ねる（§18.5 の A）。新しい抜き書きの要約の確認も同時に記録する
        _, m = write_approval(cid, by, note or None)
        msgs.append(m)
        for e in new_eids:
            msgs.append(write_confirm(e, by)[1])
    c["status"] = "accepted"
    c["decided"] = {"by": by, "date": today, "cid": cid}
    save_candidates(store)
    return True, "／".join(msgs)
