# -*- coding: utf-8 -*-
"""原稿の印・文・指紋、網羅、承認の状態の計算。"""
import hashlib
import re
import unicodedata
from . import config as cfg
from .bib import resolve_keys
from .config import RETURNED


# ---------------------------------------------------------------- 引用（原稿側）

def mask_comments(text):
    """HTML コメントを同じ長さの空白に置き換える（位置は保ち、改行は残す）。"""
    return re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def manuscript_marks(text):
    """印の (ID, 位置, 印に書かれた key か None)。HTML コメントの中は除く。

    印の正規表現は、名前つきのグループ id（無ければグループ1）と、任意の key を持てる。
    key を持つ形（例 LaTeX の \\cite{doe2020}%c017）では、印の key と引用の根拠の文献が合うかも検査する。
    """
    spans = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?-->", text, re.S)]
    gi = cfg.MARK_RE.groupindex
    res = []
    for m in cfg.MARK_RE.finditer(text):
        if any(a <= m.start() < z for a, z in spans):
            continue
        key = m.group("key") if "key" in gi else None
        res.append((mark_id(m), m.start(), key))
    return res


def mark_id(m):
    """印の正規表現のマッチから ID を取る（名前つきのグループ id、無ければグループ1）。"""
    return m.group("id") if "id" in cfg.MARK_RE.groupindex else m.group(1)


def sentence_at(text, off):
    """off を含む文。引用符（「」と “”）の中の文の終わりでは切らない（引用が二文にまたがる場合）。

    段落の区切りは設定 manuscript.paragraph で選ぶ。line は一行が一段落（行を折り返さない md）、
    blank は空行で段落を区切る（行を折り返す md や LaTeX）。文の終わりは manuscript.sentence_end の正規表現。
    """
    a, z = sentence_bounds(text, off)
    return re.sub(r"\s{2,}", " ", text[a:z]).strip()


def sentence_bounds(text, off):
    """off を含む文の (開始, 終了)。sentence_at の本体。"""
    if cfg.PARAGRAPH == "blank":
        b = [m.end() for m in re.finditer(r"\n[ \t]*\n", text[:off])]
        a = b[-1] if b else 0
        m = re.compile(r"\n[ \t]*\n").search(text, off)
        z = m.start() if m else len(text)
    else:
        a = text.rfind("\n", 0, off) + 1
        z = text.find("\n", off)
        z = len(text) if z < 0 else z
    start, depth = a, 0
    for i in range(a, z):
        c = text[i]
        if c in "「“":
            depth += 1
        elif c in "」”":
            depth = max(0, depth - 1)
        elif depth == 0 and cfg.SENT_END_RE.match(text, i):
            if i >= off:
                return start, i + 1
            start = i + 1
    return start, z


def unmark(text):
    """印を外す。印の正規表現に名前つきのグループ strip があればその部分だけを外す（LaTeX の cite{key} は残す）。"""
    if "strip" in cfg.MARK_RE.groupindex:
        return cfg.MARK_RE.sub(lambda m: m.group(0)[:m.start("strip") - m.start()] + m.group(0)[m.end("strip") - m.start():], text)
    return cfg.MARK_RE.sub("", text)


def fingerprint(sentence):
    s = unmark(sentence)
    s = re.sub(r"\s", "", s)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def coverage_of(text, bib=None, mark_keys=None):
    """原稿の出典らしき括弧を、印のある文にあるものと無いものに分ける。text は HTML コメントを伏せたもの。

    返り値は (印のある出典の数, 印の無い出典の件の並び, 括弧の数)。引用でないと記録したものは並びに入れない。
    印の無い文の出典は、このツールが何も確かめていない引用である。check の「確認待ち 0」が引用全体の確認と読まれないよう数を出す。
    """
    items = coverage_items(text, bib, mark_keys)
    marked, unmarked = 0, []
    for c in items:
        if c["marked"]:
            marked += 1
        elif not c["excluded"]:
            unmarked.append(c)
    return marked, unmarked, len({c["off"] for c in items})


def load_excluded():
    import json
    return json.loads(cfg.EXCLUDED.read_text(encoding="utf-8")) if cfg.EXCLUDED and cfg.EXCLUDED.exists() else []


def mark_keys(blocks):
    """印の ID から、その引用のブロックの key の集合 {ID: {key}} を作る（§8.1 の 5）。指示は 文献、主張は 抜き書き の key。"""
    out = {}
    for b in blocks:
        f = b["fields"]
        if f.get("種類") == "指示":
            keys = {f.get("文献", "").strip()}
        else:
            keys = {r.strip().split("#")[0] for r in f.get("抜き書き", "").split(",") if "#" in r}
        out[b["id"]] = {k for k in keys if k}
    return out


def _paren_matches(text):
    """出典らしき括弧（COVER_RE）と、頁だけ・同書の括弧（REPEAT_RE）を、位置の順に (一致, 種類) で返す。
    REPEAT_RE に当たっても、COVER_RE に当たる括弧と重なれば数えない（COVER_RE の側で数える）。"""
    covers = list(cfg.COVER_RE.finditer(text))
    spans = [(m.start(), m.end()) for m in covers]
    reps = [m for m in cfg.REPEAT_RE.finditer(text) if not any(a <= m.start() < z for a, z in spans)]
    found = [(m, "cite") for m in covers] + [(m, "repeat") for m in reps]
    return sorted(found, key=lambda x: x[0].start())


def _sources_in(inner):
    """括弧の中身を ; と ； で分け、前後の空白を除いて、全角の括弧で包んだものが COVER_RE に全体一致するものを出典とする（§8.1 の 1）。"""
    return [p for p in (x.strip() for x in re.split(r"[;；]", inner)) if cfg.COVER_RE.fullmatch(f"（{p}）")]


def coverage_items(text, bib=None, mark_keys=None):
    """原稿の出典らしき括弧を、文と指紋つきで並べる（§8.1）。
    出典が二つ以上の括弧は出典ごとに一件（part が出典の番号）、それ以外は括弧ごとに一件（part は None）。
    repeat（頁だけ・同書）の括弧も一件。item は文の指紋・括弧・文の中で何番目の同じ括弧か（と part）から作る ID で、
    文が変わらない限り変わらない（候補の作業票と、引用でないの記録が使う）。
    bib と mark_keys（mark_keys の結果）を渡すと、印を key で結ぶ（§8.1 の 5）。渡さなければ key を使わない。"""
    excluded = {(x["fingerprint"], x["paren"], x.get("nth", 0), x.get("part")) for x in load_excluded()}
    seen = {}
    out = []
    for m, kind in _paren_matches(text):
        paren = m.group(0)
        sent = sentence_at(text, m.start())
        fp = fingerprint(sent)
        nth = seen.get((fp, paren), 0)
        seen[(fp, paren)] = nth + 1
        srcs = _sources_in(paren[1:-1]) if kind == "cite" else []
        split = len(srcs) >= 2
        k = m.end()
        while k < len(text) and text[k] in " \t":
            k += 1
        dm = cfg.MARK_RE.match(text, k)
        for part, source in (enumerate(srcs) if split else [(None, paren[1:-1])]):
            ident = f"{fp}\t{paren}\t{nth}" + ("" if part is None else f"\t{part}")
            out.append({"item": "q" + hashlib.sha1(ident.encode("utf-8")).hexdigest()[:7], "off": m.start(), "end": m.end(),
                        "paren": paren, "nth": nth, "sentence": sent, "fingerprint": fp, "kind": kind,
                        "source": source, "part": part, "nparts": len(srcs) if split else None,
                        "window": source if split else text[max(0, m.start() - 30):m.end()],
                        "direct": bool(dm), "dmark": mark_id(dm) if dm else None,
                        "excluded": (fp, paren, nth, part) in excluded, "marked": False,
                        "line": text.count("\n", 0, m.start()) + 1, "section": heading_at(text, m.start())})
    by_sent = {}
    for c in out:
        by_sent.setdefault((c["fingerprint"], c["sentence"]), []).append(c)
    for cs in by_sent.values():
        _mark_sentence(cs, [cid for cid, _, _ in manuscript_marks(cs[0]["sentence"])], bib, mark_keys)
    return out


def _mark_sentence(cs, marks, bib, mark_keys):
    """一文の出典 cs に印を付ける（§8.1 の 5）。marks は文の中の印の ID を位置の順に並べたもの。
    3（key で結ぶ）は bib と mark_keys を渡したときだけ行う。4 は括弧の直後の印、残りは使われていない印を前から配る。"""
    used = set()
    if bib is not None and mark_keys is not None and marks:
        cands = [{r["key"]: r["score"] for r in resolve_keys(c["window"], bib)} if c["kind"] == "cite" else {} for c in cs]
        edges = sorted((-cands[i][key], i, j, key) for i in range(len(cs)) for j in range(len(marks))
                       for key in mark_keys.get(marks[j], ()) if key in cands[i])
        pairs = set()
        for _, i, j, key in edges:
            if cs[i]["marked"] or (marks[j], key) in pairs:
                continue
            cs[i]["marked"] = True
            pairs.add((marks[j], key))
            used.add(marks[j])
    taken = set()  # 同じ括弧の出典は、前のものから一つだけが括弧の直後の印を使える
    for c in cs:
        if c["marked"] or c["dmark"] is None or c["dmark"] in used or c["off"] in taken:
            continue
        c["marked"] = True
        used.add(c["dmark"])
        taken.add(c["off"])
    spare = [cid for cid in marks if cid not in used]
    for c in cs:
        if not c["marked"] and spare:
            c["marked"] = True
            spare.pop(0)


def evidence_hash(refs, excerpts, reading=""):
    """引用の根拠（抜き書きの ID と逐語、あれば人の読み）の指紋。根拠を足す、逐語を直す、読みを直すと変わる。"""
    s = "\n".join(f"{r}\t{re.sub(r'\s', '', excerpts.get(r, {}).get('逐語', ''))}" for r in sorted(refs))
    if reading:
        s += "\n人の読み\t" + re.sub(r"\s", "", reading)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def summary_fingerprint(fields):
    """抜き書きの、人が確かめる欄（逐語・要約・言っていないこと・強さ）の指紋。孫引きがあるときだけ、それも含める（§6.2）。"""
    s = "\n".join(re.sub(r"\s", "", fields.get(n, "")) for n in ("逐語", "強さ", "要約", "言っていないこと"))
    if fields.get("孫引き"):
        s += "\n孫引き\t" + re.sub(r"\s", "", fields["孫引き"])
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def verbatim_fingerprint(verbatim):
    """逐語の指紋（§5.2）。逐語から空白をすべて除いた文字列の SHA-1 の先頭8桁。"""
    return hashlib.sha1(re.sub(r"\s", "", verbatim).encode("utf-8")).hexdigest()[:8]


def writer_of(value):
    """「記入」の値の先頭の語（空白と全角・半角の括弧の手前まで）。書き手の名前。"""
    m = re.match(r"[^\s（(]+", (value or "").strip())
    return m.group(0) if m else ""


def same_name(a, b):
    """二つの名前が同じ者か。NFKC（全角と半角）、大文字と小文字、前後の空白の違いを無視して比べる（C20）。記録の文字は変えない。"""
    def norm(s):
        return unicodedata.normalize("NFKC", s or "").strip().casefold()
    return norm(a) == norm(b)


def approver_kind(by):
    """承認者の一覧での by の種類（human / model）。名前は same_name で引く（C20、C35）。一覧に無ければ None。"""
    if by in cfg.APPROVERS:
        return cfg.APPROVERS[by]
    return next((v for k, v in cfg.APPROVERS.items() if same_name(k, by)), None)


def approver_family(by):
    """承認者の一覧での by の系統（`model:<系統>` の系統）。名前は same_name で引く。書いていなければ None。"""
    if by in cfg.APPROVER_FAMILIES:
        return cfg.APPROVER_FAMILIES[by]
    return next((v for k, v in cfg.APPROVER_FAMILIES.items() if same_name(k, by)), None)


def independence_problem(by, writers):
    """model の by が、書き手（writers は名前の並び）と独立でない理由。独立なら、または by が model でなければ None（§2.1 の条件 3、C41）。

    確かめる・承認する・候補を受け入れるのすべてで、この一つの規則を使う。名前は same_name で比べる。
    独立なのは、どの書き手とも名前が違い、一覧で引いた書き手の系統とも違うときだけ。
    書き手が一覧に無い、または by か model の書き手に系統が無いときは、独立か分からないので独立としない。
    human の書き手とは常に独立とする。human の by は問わない（人は最終の責任者で、一人で書く場合を想定する）。
    """
    if approver_kind(by) != "model":
        return None
    names = list(dict.fromkeys(w for w in writers if w))
    if not names:
        return f"書き手が分からないので、model '{by}' が書き手と独立か分からない"
    if any(same_name(by, w) for w in names):
        return f"書き手と同じモデル '{by}' の確認は数えない"
    fam = approver_family(by)
    if not fam:
        return f"model '{by}' の系統が承認者の一覧に無いので、書き手と独立か分からない（model:<系統> と書く）"
    for w in names:
        kind = approver_kind(w)
        if kind is None:
            return f"書き手 '{w}' が承認者の一覧に無いので、model '{by}' と独立か分からない"
        if kind == "model":
            wfam = approver_family(w)
            if not wfam:
                return f"書き手 '{w}' の系統が承認者の一覧に無いので、model '{by}' と独立か分からない"
            if same_name(wfam, fam):
                return f"書き手 '{w}' と同じ系統（{fam}）の model '{by}' の確認は数えない"
    return None


def citation_writers(f, excerpts):
    """引用の承認で独立を見る書き手。引用の「記入」と、根拠の抜き書き（excerpts は {key#eN: 欄}）の「記入」の先頭の語（C41）。"""
    refs = [r.strip() for r in f.get("抜き書き", "").split(",") if r.strip()]
    return [writer_of(f.get("記入"))] + [writer_of(excerpts[r].get("記入")) for r in refs if r in excerpts]


def model_approval_problem(by):
    """承認者の一覧で model の者の、引用の承認を承認済に数えない理由（§3.2）。主張を原典が支えているかは人の承認が保証する。

    承認は記録として残す。一覧が無いときは種類が分からないので、今の扱いのまま（None）。原本での確認と要約の確認には使わない。
    """
    if approver_kind(by) == "model":
        return f"model '{by}' の承認は記録に残るが、承認済には人（human）の承認が要る"
    return None


def uncounted_reason(approver, f, excerpts):
    """approver の引用の承認を数えない理由。数えるなら None。状態を問わない（review の model の承認の記録も使う）。

    f は引用の欄、excerpts は {key#eN: 抜き書きの欄}（根拠の書き手を引く）。
    """
    return independence_problem(approver, citation_writers(f, excerpts)) or model_approval_problem(approver)


def uncounted_approval(state, approver, f, excerpts):
    """approval_state が承認済とした引用の承認を、承認済に数えない理由。数えるなら None。

    書き手と独立でない model の承認（§2.1 の条件 3、C41）と、承認者の一覧で model の者の承認（§3.2）を数えない。
    check と review（md・JSON・承認の HTML）が同じに数えるために共通に使う（C34）。
    """
    if state != "承認済":
        return None
    return uncounted_reason(approver, f, excerpts)


SOURCE_CHECK_RE = re.compile(r"^(\S+) (\d{4}-\d{2}-\d{2}) (一致|違う)(.*)$")


def parse_source_check(value):
    """原本での確認の値（§5.2 の形）を (確認者, 結果, 頁と節, メモ) にする。形に当たらなければ None。"""
    m = SOURCE_CHECK_RE.match(value or "")
    if not m:
        return None
    rest = m.group(4)
    memo = re.search(r"（([^（）]*)）$", rest)
    page = rest[:memo.start()] if memo else rest
    return m.group(1), m.group(3), page.strip(), memo.group(1) if memo else ""


def source_check_state(f, rec, verbatim, writer):
    """原本での確認が有効か（§5.2 の条件1〜5）。(確認者, 問題の文) を返す。問題の文が空なら有効。"""
    value = f.get("原本での確認", "")
    if not value:
        return None, "原本での確認が無い"
    parsed = parse_source_check(value)
    if parsed is None:
        return None, "原本での確認の記録が今の形でない"
    checker, result = parsed[0], parsed[1]
    if (cfg.APPROVERS and checker not in cfg.APPROVERS) or (not cfg.APPROVERS and checker == "確認者不明"):
        return checker, f"確認者 '{checker}' が承認者の一覧に無い"
    problem = independence_problem(checker, [writer])
    if problem:
        return checker, problem
    if rec.get("原本での確認時の指紋") != verbatim_fingerprint(verbatim):
        return checker, "確かめた後に逐語が変わった（または指紋が無い）"
    if result == "違う":
        return checker, "原本と違うと報告された。逐語を直して確かめ直す"
    return checker, ""


REF_RE = re.compile(r"(?<![\w#])(?:([\w.-]+)#)?(e\d+)(?![\w])")


def refs_in(value, keys):
    """欄の文字列の中の抜き書きへの参照を (書かれた形, 候補の ID の並び) で返す。
    key の無い e3 は、keys（同じ文献、または引用の根拠の文献）のどれかの e3 を指すとみなす。"""
    out = []
    for m in REF_RE.finditer(value):
        if m.group(1):
            out.append((m.group(0), [f"{m.group(1)}#{m.group(2)}"]))
        elif keys:
            out.append((m.group(0), [f"{k}#{m.group(2)}" for k in keys]))
    return out


def approval_state(f, rec, fp, ev):
    """(状態, 補足)。状態は 未承認 / 承認済 / 要再確認 / 差し戻し / 差し戻し後に直された。"""
    appr = f.get("承認", "未") or "未"
    head = appr.split()[0]
    if head in (RETURNED, "returned"):
        reason = f.get("差し戻しの理由", "")
        if rec.get("差し戻し時の指紋") == fp and rec.get("差し戻し時の根拠", ev) == ev:
            return "差し戻し", reason
        return "差し戻し後に直された", reason
    if head == "未":
        return "未承認", ""
    changed = []
    if rec.get("承認時の指紋") != fp:
        changed.append("本文")
    if rec.get("承認時の根拠") and rec["承認時の根拠"] != ev:  # 根拠の記録が無い古い承認は本文だけを見る
        changed.append("根拠")
    if changed:
        return "要再確認", "・".join(changed)
    return "承認済", head


def heading_at(text, off):
    hs = [m for m in re.finditer(r"^#{1,4} .*$", text[:off], re.M)]
    return hs[-1].group(0).lstrip("# ").strip() if hs else ""
