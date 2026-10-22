# -*- coding: utf-8 -*-
"""原稿の印・文・指紋、網羅、承認の状態の計算。"""
import hashlib
import re
from . import config as cfg
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
        cid = m.group("id") if "id" in gi else m.group(1)
        key = m.group("key") if "key" in gi else None
        res.append((cid, m.start(), key))
    return res


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


def coverage_of(text):
    """原稿の出典らしき括弧（COVER_RE）を、印のある文にあるものと無いものに分ける。text は HTML コメントを伏せたもの。

    印の無い文の出典は、このツールが何も確かめていない引用である。check の「確認待ち 0」が引用全体の確認と読まれないよう数を出す。
    """
    marked, unmarked = 0, []
    for c in coverage_items(text):
        if c["marked"]:
            marked += 1
        elif not c["excluded"]:
            unmarked.append((c["line"], c["paren"], c["section"]))
    return marked, unmarked


def load_excluded():
    import json
    return json.loads(cfg.EXCLUDED.read_text(encoding="utf-8")) if cfg.EXCLUDED and cfg.EXCLUDED.exists() else []


def coverage_items(text):
    """原稿の出典らしき括弧を、文と指紋つきで並べる。item は文の指紋・括弧・文の中で何番目の同じ括弧か、から作る ID で、
    文が変わらない限り変わらない（候補の作業票と、引用でないの記録が使う）。"""
    excluded = {(x["fingerprint"], x["paren"], x.get("nth", 0)) for x in load_excluded()}
    seen = {}
    out = []
    for m in cfg.COVER_RE.finditer(text):
        sent = sentence_at(text, m.start())
        fp = fingerprint(sent)
        nth = seen.get((fp, m.group(0)), 0)
        seen[(fp, m.group(0))] = nth + 1
        item = "q" + hashlib.sha1(f"{fp}\t{m.group(0)}\t{nth}".encode("utf-8")).hexdigest()[:7]
        k = m.end()
        while k < len(text) and text[k] in " \t":
            k += 1
        out.append({"item": item, "off": m.start(), "end": m.end(), "paren": m.group(0), "nth": nth, "sentence": sent,
                    "fingerprint": fp, "direct": bool(cfg.MARK_RE.match(text, k)), "excluded": (fp, m.group(0), nth) in excluded,
                    "line": text.count("\n", 0, m.start()) + 1, "section": heading_at(text, m.start())})
    # 括弧の直後に印があれば印のある出典。無くても、同じ文に括弧へ付いていない印が残っていれば、その数だけ前から印のあるものとみなす
    # （印を文末に置いた引用）。一文に出典が三つあり印が二つなら、残る一つは印の無い出典である
    by_sent = {}
    for c in out:
        by_sent.setdefault((c["fingerprint"], c["sentence"]), []).append(c)
    for (fp, sent), cs in by_sent.items():
        spare = len(cfg.MARK_RE.findall(sent)) - sum(c["direct"] for c in cs)
        for c in cs:
            c["marked"] = c["direct"] or spare > 0
            if not c["direct"] and spare > 0:
                spare -= 1
    return out


def evidence_hash(refs, excerpts, reading=""):
    """引用の根拠（抜き書きの ID と逐語、あれば人の読み）の指紋。根拠を足す、逐語を直す、読みを直すと変わる。"""
    s = "\n".join(f"{r}\t{re.sub(r'\s', '', excerpts.get(r, {}).get('逐語', ''))}" for r in sorted(refs))
    if reading:
        s += "\n人の読み\t" + re.sub(r"\s", "", reading)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def summary_fingerprint(fields):
    """抜き書きの、人が確かめる欄（逐語・要約・言っていないこと・強さ）の指紋。"""
    s = "\n".join(re.sub(r"\s", "", fields.get(n, "")) for n in ("逐語", "強さ", "要約", "言っていないこと"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def verbatim_fingerprint(verbatim):
    """逐語の指紋（§5.2）。逐語から空白をすべて除いた文字列の SHA-1 の先頭8桁。"""
    return hashlib.sha1(re.sub(r"\s", "", verbatim).encode("utf-8")).hexdigest()[:8]


def writer_of(value):
    """「記入」の値の先頭の語（空白と全角・半角の括弧の手前まで）。書き手の名前。"""
    m = re.match(r"[^\s（(]+", (value or "").strip())
    return m.group(0) if m else ""


def self_check_problem(by, writer):
    """書き手と同じ者が、モデル（承認者の一覧で model）として確かめる・承認する・受け入れることを断る理由（§5.8）。無ければ None。"""
    if writer and by == writer and cfg.APPROVERS.get(by) == "model":
        return f"書き手と同じモデル '{by}' の確認は数えない"
    return None


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
    problem = self_check_problem(checker, writer)
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
