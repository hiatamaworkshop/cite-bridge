# -*- coding: utf-8 -*-
"""引用ブリッジ（抜き書きと引用）の導出と検査。

使い方（リポジトリの根から実行する。書式は SKILL.md）:
    python bridge.py derive              抜き書きの導く欄（@ で始まる行）を書き直す
    python bridge.py check [--strict]    整合を検査する。崩れがあれば exit 1
    python bridge.py grade [--keys-from <md>]   文献ごとの資料の格と、その内訳を出す
    python bridge.py approve <cID> --by <承認者>  引用の承認を、その時点の本文の指紋つきで記録する

役割の分担:
  - 人か AI が書くのは判断の欄（逐語、強さ、要約、言っていないこと、解釈、理由 等）だけ。
  - 所在・前後の文・節の種類・照合の段階・格は、このスクリプトが導く。手で書かない。
  - 照合は key に結ばれた抽出テキストの中だけで行う。他の文献での一致は手がかりとして示すに留める。
"""
import argparse
import datetime
import hashlib
import re
import sys
import unicodedata
from pathlib import Path

BIB = Path("notes/書誌リスト.md")
EXC_DIR = Path("bridge/excerpts")
CIT = Path("bridge/citations.md")
TXT_DIR = Path("references/_txt")

STRENGTHS = {"観察", "示唆", "主張", "一般化", "条件付き"}
DIFFS = {"一致", "言い換え", "限定つき一般化", "外挿"}
KINDS = {"指示", "主張"}
EXC_REQUIRED = ["逐語", "強さ", "要約", "言っていないこと", "記入"]

FIELD_RE = re.compile(r"^(@?)([^\s:@][^:]*?):\s?(.*)$")
MARK_RE = re.compile(r"〔(c\d{3,})〕")
KEY_LINE_RE = re.compile(r"^key:\s*(\S+)\s*$")


# ---------------------------------------------------------------- 正規化

FOLD = {"“": '"', "”": '"', "‘": "'", "’": "'",
        "–": "-", "—": "-", "−": "-", "­": ""}


def is_cjk(c):
    return "぀" <= c <= "ヿ" or "㐀" <= c <= "鿿" or "＀" <= c <= "￯"


def normalize(raw, level):
    """raw を正規化し、(文字列, 各文字の raw 上の位置) を返す。

    ws    空白を一つにまとめるだけ（和字に接する空白は和文の組版によるものとして消す）
    nfkc  加えて NFKC、引用符とダッシュの統一、小文字化、行末ハイフンの結合
    alnum 文字と数字だけを残す（句読点と空白の違いを無視する）
    """
    out, pos = [], []
    pending = False
    i, n = 0, len(raw)
    while i < n:
        ch = raw[i]
        if level != "ws" and ch == "-" and i > 0 and raw[i - 1].isalpha():
            j = i + 1
            while j < n and raw[j] in " \t":
                j += 1
            if j < n and raw[j] in "\r\n\f":
                k = j
                while k < n and raw[k] in " \t\r\n\f":
                    k += 1
                if k < n and raw[k].islower():
                    i = k
                    continue
        if level == "ws":
            s = ch
        else:
            s = "".join(FOLD.get(c, c) for c in unicodedata.normalize("NFKC", ch)).lower()
        for c in s:
            if c.isspace():
                pending = True
                continue
            if level == "alnum" and not c.isalnum():
                continue
            if pending and out and level != "alnum" and not (is_cjk(out[-1]) or is_cjk(c)):
                out.append(" ")
                pos.append(i)
            pending = False
            out.append(c)
            pos.append(i)
        i += 1
    return "".join(out), pos


class Source:
    """一つの抽出テキスト。正規化の結果と見出しを持つ。"""

    def __init__(self, path):
        self.path = path
        self.raw = path.read_text(encoding="utf-8", errors="replace")
        self._norm = {}
        self.headings = find_headings(self.raw)

    def norm(self, level):
        if level not in self._norm:
            self._norm[level] = normalize(self.raw, level)
        return self._norm[level]

    def page_of(self, off):
        return self.raw.count("\f", 0, off) + 1

    def pages(self):
        return self.raw.count("\f") + 1


# ---------------------------------------------------------------- 照合

LEVELS = [("ws", "一致"), ("nfkc", "正規化で一致"), ("alnum", "正規化で一致（句読点・記号が異なる）")]


def locate(quote, src):
    """(段階, raw の開始位置, raw の終了位置) を返す。見つからなければ位置は None。"""
    for level, label in LEVELS:
        q, _ = normalize(quote, level)
        t, tp = src.norm(level)
        k = t.find(q) if q else -1
        if k >= 0:
            return label, tp[k], tp[k + len(q) - 1] + 1
    q, _ = normalize(quote, "alnum")
    t, tp = src.norm("alnum")
    g = 6 if any(is_cjk(c) for c in q) else 10
    grams = {q[i:i + g] for i in range(max(0, len(q) - g + 1))}
    if not grams:
        return "不一致", None, None
    hits = []
    for gr in grams:
        s = t.find(gr)
        while s >= 0:
            hits.append((s, gr))
            s = t.find(gr, s + 1)
    hits.sort()
    width = int(len(q) * 1.5) + g
    best, span, left, cnt = 0, None, 0, {}
    for right in range(len(hits)):
        cnt[hits[right][1]] = cnt.get(hits[right][1], 0) + 1
        while hits[right][0] - hits[left][0] > width:
            gl = hits[left][1]
            cnt[gl] -= 1
            if cnt[gl] == 0:
                del cnt[gl]
            left += 1
        if len(cnt) > best:
            best, span = len(cnt), (hits[left][0], hits[right][0] + g)
    share = best / len(grams)
    if share >= 0.5:
        return f"近似一致（重なり {round(share * 100)}%）", tp[span[0]], tp[span[1] - 1] + 1
    return "不一致", None, None


# ---------------------------------------------------------------- 見出しと節の種類

HEAD_RE = re.compile(r"^((?:\d{1,2}|[A-Z])(?:[.・]\d{1,2}){0,3})[.・]?(\s*)(\S.{0,80})$")
NUM_ONLY_RE = re.compile(r"^((?:\d{1,2}|[A-Z])(?:[.・]\d{1,2}){0,3})[.・]?$")
TOC_RE = re.compile(r"(\.\s?){4,}\s*\d*$")  # 目次の点線と頁番号
UNNUMBERED = {"abstract": "要旨", "references": "参考文献", "bibliography": "参考文献",
              "acknowledgments": "謝辞", "acknowledgements": "謝辞", "参考文献": "参考文献",
              "文献": "参考文献", "謝辞": "謝辞", "あらまし": "要旨", "要旨": "要旨", "概要": "要旨"}
KIND_WORDS = [
    ("限界", ["limitation", "future work", "限界", "今後の課題", "今後の展望"]),
    ("関連研究", ["related work", "background", "prior work", "関連研究", "先行研究", "従来研究"]),
    ("参考文献", ["references", "bibliography", "参考文献"]),
    ("付録", ["appendix", "付録"]),
    ("序論", ["introduction", "はじめに", "序論", "まえがき"]),
    ("方法", ["method", "study design", "procedure", "participants", "実験方法", "評価方法"]),
    ("結果", ["result", "findings", "結果"]),
    ("議論", ["discussion", "考察"]),
    ("結論", ["conclusion", "concluding", "おわりに", "むすび", "結論", "まとめ"]),
    ("要旨", ["abstract", "要旨", "あらまし", "概要"]),
]
KIND_WORDS_MAP = dict(KIND_WORDS)


def find_headings(raw):
    """(位置, 番号, 題, 行末の位置) の並び。番号が順に進むものだけを見出しとみなす。"""
    lines = []
    off = 0
    for ln in raw.split("\n"):
        lines.append((off, ln))
        off += len(ln) + 1
    res = []
    top = None
    letters_ok = False
    for idx, (off, ln) in enumerate(lines):
        end = off + len(ln)
        s = unicodedata.normalize("NFKC", ln.replace("\f", "")).strip()
        if s.lower().startswith("abstract "):
            res.append((off, "", "Abstract", off + 8))
            continue
        if not s or len(s) > 90 or TOC_RE.search(s):
            continue
        low = s.lower().rstrip(":")
        if low in UNNUMBERED:
            res.append((off, "", s, end))
            if UNNUMBERED[low] == "参考文献":
                letters_ok = True
            continue
        m = HEAD_RE.match(s)
        num = title = None
        if m and (m.group(2) or is_cjk(m.group(3)[0])):
            num, title = m.group(1), m.group(3)
        elif NUM_ONLY_RE.match(s) and idx + 1 < len(lines):
            nxt = unicodedata.normalize("NFKC", lines[idx + 1][1]).strip()
            if 0 < len(nxt) <= 80:
                num, title = NUM_ONLY_RE.match(s).group(1), nxt
                end = lines[idx + 1][0] + len(lines[idx + 1][1])
        if not num or not (title[0].isupper() or is_cjk(title[0])):
            continue
        parts = re.split(r"[.・]", num)
        if parts[0].isdigit():
            t = int(parts[0])
            intro = any(w in title.lower() for w in KIND_WORDS_MAP["序論"])
            if len(parts) == 1:
                # 番号が順に進むか、序論で 1 へ戻る（目次の後の本文）ときだけ見出しとする
                if (top is None and t <= 2) or (top is not None and (t == top + 1 or (t == 1 and intro))):
                    top = t
                    res.append((off, num, title, end))
            elif top is not None and t == top:
                res.append((off, num, title, end))
            elif top is not None and t == top + 1:
                # 親の見出しを拾えなかった小節。親が進んだとみなす
                top = t
                res.append((off, num, title, end))
        elif letters_ok:
            res.append((off, num, title, end))
    return res


SPECIFIC_KINDS = ("限界", "関連研究", "参考文献", "付録")


def section_at(src, off):
    """off を含む節の (見出しの文字列, 節の種類)。

    限界・関連研究・参考文献・付録は、どの階層の題からでも判定する。
    それ以外（序論・方法・結果・議論・結論・要旨）は、最上位の章の題だけで判定する。
    """
    before = [h for h in src.headings if h[0] <= off]
    if not before:
        return "見出しなし", "不明"
    cur = before[-1]
    label = (f"§{cur[1].replace('・', '.')} " if cur[1] else "") + cur[2]
    chain = [cur]
    if cur[1]:
        parts = re.split(r"[.・]", cur[1])
        for n in range(len(parts) - 1, 0, -1):
            prefix = parts[:n]
            anc = [h for h in before if re.split(r"[.・]", h[1]) == prefix]
            if anc:
                chain.append(anc[-1])
    for _, _, title, _ in chain:
        low = title.lower()
        for kind in SPECIFIC_KINDS:
            if any(w in low for w in KIND_WORDS_MAP[kind]):
                return label, kind
    low = chain[-1][2].lower()
    for kind, words in KIND_WORDS:
        if kind not in SPECIFIC_KINDS and any(w in low for w in words):
            return label, kind
    return label, "本論"


SENT_END = re.compile(r"(?<=[.!?。．！？])[\"”’)]*\s+|(?<=[。．！？])")


def context(src, a, b, limit=300):
    """一致した箇所の前の文、逐語が文の途中で切れているときはその文全体、後の文。"""
    lo, hi = max(0, a - 2000), min(len(src.raw), b + 2000)
    win = src.raw[lo:hi]
    ends = [m.end() + lo for m in SENT_END.finditer(win)]
    ends += [h[3] for h in src.headings if lo <= h[3] < hi]  # 見出しの行末も文の区切り
    ends.sort()
    starts_before = [e for e in ends if e <= a]
    s0 = starts_before[-1] if starts_before else lo
    s_prev = starts_before[-2] if len(starts_before) >= 2 else lo
    after = [e for e in ends if e >= b]
    e1 = after[0] if after else hi
    e2 = after[1] if len(after) >= 2 else hi

    def clean(x, limit=limit):
        x = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", x)
        x = re.sub(r"\s+", " ", x).strip()
        return x if len(x) <= limit else x[:limit] + "…"

    whole = None
    rest = src.raw[s0:a] + src.raw[b:e1]
    if re.sub(r"[\s.。．,，、:;\"”’)）]", "", rest):
        whole = clean(src.raw[s0:e1], limit=600)
    return clean(src.raw[s_prev:s0]), whole, clean(src.raw[e1:e2])


# ---------------------------------------------------------------- 書誌と格

def parse_bib():
    lines = BIB.read_text(encoding="utf-8").splitlines()
    bib = {}
    for i, ln in enumerate(lines):
        m = KEY_LINE_RE.match(ln.strip())
        if not m:
            continue
        note = lines[i + 1] if i + 1 < len(lines) and lines[i + 1].startswith("（") else ""
        pdfs = re.findall(r"PDF所持: `?references/([^`]+?\.pdf)", note)
        bib[m.group(1)] = {"entry": lines[i - 1], "note": note, "pdfs": pdfs}
    return bib


def garbled(raw, entry):
    s = re.sub(r"\s", "", raw)
    if len(s) < 200:
        return "抽出が空か短い"
    # 和文の文献は和字の割合で、それ以外は英語の頻出語の割合で読めるかを見る
    if any(is_cjk(c) for c in re.sub(r"（[^（）]*）", "", entry)):  # （参照 …）等の注記は除く
        cjk = sum(1 for c in s if is_cjk(c)) / len(s)
        return "抽出が化けている" if cjk < 0.2 else None
    words = re.findall(r"[A-Za-z]{2,}", raw)
    common = sum(1 for w in words if w.lower() in COMMON_EN) / max(1, len(words))
    return "抽出が化けている" if common < 0.08 else None


COMMON_EN = set("the and of to in for with that this are is was were be on as by from or which can not have has their its".split())


def grade_of(key, bib):
    """(格, 抽出テキストの Path か None)。"""
    b = bib.get(key)
    if b is None:
        return "書誌に無い", None
    if b["pdfs"]:
        for pdf in b["pdfs"]:
            txt = TXT_DIR / (Path(pdf).stem + ".txt")
            if txt.exists():
                bad = garbled(txt.read_text(encoding="utf-8", errors="replace"), b["entry"])
                if bad:
                    return f"PDF所持（{bad}）", None
                return "PDF所持（抽出あり）", txt
        return "PDF所持（抽出なし）", None
    if re.search(r"参照 \d{4}", b["entry"]) or re.search(r"https?://(?!doi\.org|arxiv\.org)", b["entry"]):
        return "Web 資料（写しなし）", None
    return "未入手", None


# ---------------------------------------------------------------- ブロックの読み書き

def parse_blocks(path):
    """# 見出しの部分（head）と、## ID ごとのブロックを読む。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    head = {"title": None, "fields": {}, "derived": {}, "line": 1}
    blocks = []
    cur = head
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            cur = {"id": ln[3:].strip(), "fields": {}, "derived": {}, "line": i + 1}
            blocks.append(cur)
            continue
        if ln.startswith("# "):
            head["title"] = ln[2:].strip()
            continue
        m = FIELD_RE.match(ln)
        if m:
            (cur["derived"] if m.group(1) else cur["fields"])[m.group(2).strip()] = m.group(3).strip()
    return head, blocks


def rewrite_derived(path, head_derived, block_derived):
    """@ 行を除いて、各区切りの末尾に新しい @ 行を置く。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    segs, cur = [], []
    for ln in lines:
        if ln.startswith("## ") and cur:
            segs.append(cur)
            cur = []
        cur.append(ln)
    segs.append(cur)
    out = []
    for si, seg in enumerate(segs):
        body = [ln for ln in seg if not ln.startswith("@")]
        while body and not body[-1].strip():
            body.pop()
        if si == 0:
            derived = head_derived
        else:
            bid = seg[0][3:].strip()
            derived = block_derived.get(bid, {})
        out.extend(body)
        out.extend(f"@{k}: {v}" for k, v in derived.items())
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


def printed_page(entry, pdf_page, total):
    m = re.search(r"(\d+)\s*[–-]\s*(\d+)\.?\s*$", entry.split("http")[0].strip().rstrip("."))
    if m:
        a, z = int(m.group(1)), int(m.group(2))
        if z - a + 1 == total:
            return f"p.{a + pdf_page - 1}（PDF {pdf_page}頁目）"
    return f"PDF {pdf_page}頁目"


def derive_excerpts(bib, sources_cache):
    """抜き書きファイルごとに (head_derived, {id: derived}) を作る。"""
    result = {}
    for path in sorted(EXC_DIR.glob("*.md")):
        head, blocks = parse_blocks(path)
        key = head["title"]
        grade, txt = grade_of(key, bib)
        hd = {"格": grade}
        if txt:
            hd["抽出"] = txt.as_posix()
        bd = {}
        src = None
        if txt:
            if txt not in sources_cache:
                sources_cache[txt] = Source(txt)
            src = sources_cache[txt]
        for b in blocks:
            d = {}
            quote = b["fields"].get("逐語", "")
            if not src:
                d["照合"] = "照合不能（" + grade + "）"
            elif not quote:
                d["照合"] = "逐語が空"
            else:
                label, a, z = locate(quote, src)
                d["照合"] = label
                if a is not None:
                    sec, kind = section_at(src, a)
                    d["所在"] = printed_page(bib[key]["entry"], src.page_of(a), src.pages()) + " / " + sec
                    d["節の種類"] = kind
                    prev, whole, nxt = context(src, a, z)
                    d["前"] = prev
                    if whole:
                        d["含む文"] = whole
                    d["後"] = nxt
                else:
                    others = other_matches(quote, txt, sources_cache)
                    if others:
                        d["他の文献で一致"] = ", ".join(others)
            bd[b["id"]] = d
        result[path] = (hd, bd)
    return result


def other_matches(quote, own, cache):
    q, _ = normalize(quote, "alnum")
    hits = []
    for p in sorted(TXT_DIR.glob("*.txt")):
        if p == own:
            continue
        if p not in cache:
            cache[p] = Source(p)
        if q and q in cache[p].norm("alnum")[0]:
            hits.append(p.name)
    return hits


# ---------------------------------------------------------------- 引用（原稿側）

def manuscript_marks(text):
    """〔cNNN〕の (ID, 位置)。HTML コメントの中は除く。"""
    spans = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?-->", text, re.S)]
    res = []
    for m in MARK_RE.finditer(text):
        if any(a <= m.start() < z for a, z in spans):
            continue
        res.append((m.group(1), m.start()))
    return res


def sentence_at(text, off):
    a = max(text.rfind("。", 0, off), text.rfind("\n", 0, off)) + 1
    e_candidates = [x for x in (text.find("。", off), text.find("\n", off)) if x >= 0]
    z = min(e_candidates) + 1 if e_candidates else len(text)
    return text[a:z].strip()


def fingerprint(sentence):
    s = MARK_RE.sub("", sentence)
    s = re.sub(r"\s", "", s)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def heading_at(text, off):
    hs = [m for m in re.finditer(r"^#{1,4} .*$", text[:off], re.M)]
    return hs[-1].group(0).lstrip("# ").strip() if hs else ""


# ---------------------------------------------------------------- コマンド

def cmd_derive(args):
    bib = parse_bib()
    res = derive_excerpts(bib, {})
    for path, (hd, bd) in res.items():
        rewrite_derived(path, hd, bd)
        print(f"derived: {path.as_posix()}（{len(bd)} 件）")


def cmd_check(args):
    bib = parse_bib()
    errors, notes, infos = [], [], []
    cache = {}
    res = derive_excerpts(bib, cache)
    excerpts = {}
    states = {}
    for path, (hd, bd) in res.items():
        head, blocks = parse_blocks(path)
        key = head["title"]
        where = path.as_posix()
        if key not in bib:
            errors.append(f"{where}: key '{key}' が書誌リストに無い")
        if head["derived"] != hd:
            errors.append(f"{where}: 導く欄（文献）が古い。derive を実行する")
        seen = set()
        for b in blocks:
            bid = f"{key}#{b['id']}"
            w = f"{where}:{b['line']} {bid}"
            if b["id"] in seen:
                errors.append(f"{w}: ID の重複")
            seen.add(b["id"])
            f = b["fields"]
            for name in EXC_REQUIRED:
                if not f.get(name):
                    errors.append(f"{w}: 欄 '{name}' が空")
            if f.get("強さ") and f["強さ"] not in STRENGTHS:
                errors.append(f"{w}: 強さ '{f['強さ']}' は {sorted(STRENGTHS)} のどれか")
            if b["derived"] != bd.get(b["id"], {}):
                errors.append(f"{w}: 導く欄が古い。derive を実行する")
            d = bd.get(b["id"], {})
            st = d.get("照合", "")
            confirmed = bool(f.get("原本での確認")) and "確認者不明" not in f.get("原本での確認", "")
            if st == "不一致" and not confirmed:
                errors.append(f"{w}: 逐語が抽出テキストに無い" + (f"（他の文献で一致: {d['他の文献で一致']}）" if d.get("他の文献で一致") else ""))
            if (st.startswith("近似一致") or st.startswith("照合不能")) and not confirmed:
                notes.append(f"{w}: {st}。原本での確認が要る")
            if d.get("節の種類") in ("関連研究", "参考文献"):
                infos.append(f"{w}: 原典の{d['節の種類']}の節にある文。原典の著者の主張でない可能性")
            excerpts[bid] = f
            states[bid] = (st, confirmed)

    # 引用
    if CIT.exists():
        head, blocks = parse_blocks(CIT)
        target = Path(head["fields"].get("対象", ""))
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        if not text:
            errors.append(f"{CIT.as_posix()}: 対象の原稿 '{target}' が読めない")
        marks = manuscript_marks(text)
        ids_in_text = {}
        for cid, off in marks:
            ids_in_text.setdefault(cid, []).append(off)
        block_ids = set()
        counts = {"承認済": 0, "要再確認": 0, "未承認": 0, "指示": 0}
        for b in blocks:
            cid = b["id"]
            w = f"{CIT.as_posix()}:{b['line']} {cid}"
            block_ids.add(cid)
            f = b["fields"]
            if cid not in ids_in_text:
                errors.append(f"{w}: 原稿に〔{cid}〕が無い（孤児のブロック）")
                continue
            if len(ids_in_text[cid]) > 1:
                errors.append(f"{w}: 原稿に〔{cid}〕が{len(ids_in_text[cid])}箇所ある")
            kind = f.get("種類", "")
            if kind not in KINDS:
                errors.append(f"{w}: 種類は 指示 か 主張")
                continue
            sent = sentence_at(text, ids_in_text[cid][0])
            fp = fingerprint(sent)
            if kind == "指示":
                if f.get("文献") not in bib:
                    errors.append(f"{w}: 指示の引用は 文献 に書誌の key を書く")
                counts["指示"] += 1
                continue
            refs = [r.strip() for r in f.get("抜き書き", "").split(",") if r.strip()]
            if not refs:
                errors.append(f"{w}: 主張の引用は 抜き書き が要る")
            for r in refs:
                if r not in excerpts:
                    errors.append(f"{w}: 抜き書き '{r}' が無い")
            for name in ("理由", "原文との差", "記入"):
                if not f.get(name):
                    errors.append(f"{w}: 欄 '{name}' が空")
            if f.get("原文との差") and f["原文との差"] not in DIFFS:
                errors.append(f"{w}: 原文との差は {sorted(DIFFS)} のどれか")
            # 本文の引用符の中の文字列は、指している抜き書きの逐語に含まれていること
            for q in re.findall(r"「([^「」]{10,})」|\"([^\"]{20,})\"", sent):
                q = q[0] or q[1]
                qcjk = any(is_cjk(c) for c in q)
                pool = [excerpts[r]["逐語"] for r in refs if r in excerpts]
                same = [p for p in pool if any(is_cjk(c) for c in p) == qcjk]
                if same and not any(normalize(q, "alnum")[0] in normalize(p, "alnum")[0] for p in same):
                    errors.append(f"{w}: 本文の引用「{q[:30]}…」が抜き書きの逐語に無い")
            appr = f.get("承認", "未")
            if appr == "未" or not appr:
                counts["未承認"] += 1
                notes.append(f"{w}: 未承認（{heading_at(text, ids_in_text[cid][0])}）")
            elif b["derived"].get("承認時の指紋") != fp:
                counts["要再確認"] += 1
                notes.append(f"{w}: 承認の後に本文が変わった。要再確認")
            else:
                counts["承認済"] += 1
            for r in refs:
                st, ok = states.get(r, ("", False))
                if (st.startswith("近似一致") or st.startswith("照合不能")) and not ok:
                    notes.append(f"{w}: 根拠 {r} は {st} で、原本での確認が無い")
            if f.get("原文との差") == "外挿":
                notes.append(f"{w}: 外挿。本文に限定を付けるか、自分の主張として書き直す")
        for cid in ids_in_text:
            if cid not in block_ids:
                errors.append(f"{target}: 〔{cid}〕に対応するブロックが無い")
        infos.append(f"引用: 主張 承認済 {counts['承認済']} / 要再確認 {counts['要再確認']} / 未承認 {counts['未承認']}、指示 {counts['指示']}")

    summary = {}
    for st, _ in states.values():
        summary[st] = summary.get(st, 0) + 1
    for e in errors:
        print("ERROR", e)
    for n in notes:
        print("NOTE ", n)
    for n in infos:
        print("INFO ", n)
    print(f"--- 抜き書き {len(states)} 件 " + " / ".join(f"{k} {v}" for k, v in sorted(summary.items()))
          + f" / 整合の崩れ {len(errors)} 件")
    if errors:
        sys.exit(1)
    if args.strict and notes:
        print("--strict: 確認待ちが残っている")
        sys.exit(1)


def cmd_grade(args):
    bib = parse_bib()
    keys = sorted(bib)
    if args.keys_from:
        text = Path(args.keys_from).read_text(encoding="utf-8")
        keys = [k for k in keys if re.search(r"(?<![\w])" + re.escape(k) + r"(?![\w])", text)]
        # 見出しに key を持つ表の列は、書誌に無い key も拾う（改名の取り残し等）
        col = None
        for ln in text.splitlines():
            if not ln.startswith("|"):
                continue
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if "key" in cells:
                col = cells.index("key")
            elif all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                continue
            elif col is not None and col < len(cells) and re.fullmatch(r"\w+", cells[col]):
                if cells[col] not in keys:
                    keys.append(cells[col])
    summary = {}
    for k in keys:
        g, _ = grade_of(k, bib)
        summary.setdefault(g, []).append(k)
    for g, ks in sorted(summary.items(), key=lambda x: -len(x[1])):
        print(f"{g}: {len(ks)}  {', '.join(ks)}")
    total = len(keys)
    ok = len(summary.get("PDF所持（抽出あり）", []))
    print(f"--- {total} 件のうち、機械で照合できるもの {ok} 件（{round(100 * ok / max(1, total))}%）")


def cmd_approve(args):
    head, blocks = parse_blocks(CIT)
    target = Path(head["fields"].get("対象", ""))
    text = target.read_text(encoding="utf-8")
    offs = [off for cid, off in manuscript_marks(text) if cid == args.cid]
    if len(offs) != 1:
        sys.exit(f"原稿に〔{args.cid}〕がちょうど一つ無い（{len(offs)} 箇所）")
    sent = sentence_at(text, offs[0])
    today = datetime.date.today().isoformat()
    lines = CIT.read_text(encoding="utf-8").splitlines()
    out, inblock, done = [], False, False
    for ln in lines:
        if ln.startswith("## "):
            if inblock and not done:
                out.extend(_approval_lines(args.by, today, sent))
                done = True
            inblock = ln[3:].strip() == args.cid
        if inblock and (ln.startswith("承認:") or ln.startswith("@承認時の")):
            continue
        if inblock and not ln.strip() and not done:
            out.extend(_approval_lines(args.by, today, sent))
            done = True
        out.append(ln)
    if inblock and not done:
        out.extend(_approval_lines(args.by, today, sent))
    CIT.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"承認を記録: {args.cid} {args.by} {today} 指紋={fingerprint(sent)}")


def _approval_lines(by, today, sent):
    return [f"承認: {by} {today}", f"@承認時の指紋: {fingerprint(sent)}", f"@承認時の本文: {sent}"]


def main():
    global CIT
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--citations", default=str(CIT), help="引用のファイル（原稿ごとに一つ）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("derive").set_defaults(func=cmd_derive)
    c = sub.add_parser("check")
    c.add_argument("--strict", action="store_true")
    c.set_defaults(func=cmd_check)
    g = sub.add_parser("grade")
    g.add_argument("--keys-from")
    g.set_defaults(func=cmd_grade)
    a = sub.add_parser("approve")
    a.add_argument("cid")
    a.add_argument("--by", required=True)
    a.set_defaults(func=cmd_approve)
    args = ap.parse_args()
    CIT = Path(args.citations)
    args.func(args)


if __name__ == "__main__":
    main()
