# -*- coding: utf-8 -*-
"""原典のテキストの正規化、照合（逐語の位置づけ）、見出しと節の検出、前後の文。"""
import re
import unicodedata
from . import config as cfg


# ---------------------------------------------------------------- 正規化

FOLD = {"“": '"', "”": '"', "‘": "'", "’": "'",
        "–": "-", "—": "-", "−": "-", "­": ""}
# 小書きの仮名は抽出で大きい仮名に読み違えられやすい（小林 2002 の「メディア」が「メデイア」になった）
FOLD.update({k: v for k, v in zip("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ", "あいうえおつやゆよわアイウエオツヤユヨワカケ")})


def is_cjk(c):
    return "぀" <= c <= "ヿ" or "㐀" <= c <= "鿿" or "＀" <= c <= "￯"


def normalize(raw, level):
    """raw を正規化し、(文字列, 各文字の raw 上の位置) を返す。

    ws    空白を一つにまとめるだけ（和字に接する空白は和文の組版によるものとして消す）
    nfkc  加えて NFKC、引用符とダッシュの統一、小書きの仮名の統一、小文字化、行末ハイフンの結合
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
        self.web = None
        # 頭書き（Web の写しと OCR の <!-- … -->）は本文ではない。前後の文の切り出しから外す
        self.body_start = self.raw.find("-->") + 3 if self.raw.startswith("<!--") and "-->" in self.raw else 0
        if self.raw.startswith("<!-- snapshot"):  # Web の写しの頭書き
            head = self.raw[:self.raw.find("-->")]
            self.web = dict(re.findall(r"^(\w+): (.*)$", head, re.M))
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
        mh = re.match(r"^(#{1,6}) (\S.*)$", s)
        if mh:  # Web の写しの見出し
            res.append((off, "", mh.group(2), end))
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
            intro = any(w in title.lower() for w in cfg.KIND_WORDS_MAP["序論"])
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
            if any(w in low for w in cfg.KIND_WORDS_MAP[kind]):
                return label, kind
    low = chain[-1][2].lower()
    for kind, words in cfg.KIND_WORDS:
        if kind not in SPECIFIC_KINDS and any(w in low for w in words):
            return label, kind
    return label, "本論"


SENT_END = re.compile(r"(?<=[.!?。．！？])[\"”’)]*\s+|(?<=[。．！？])")


def context(src, a, b, limit=300):
    """一致した箇所の前の文、逐語が文の途中で切れているときはその文全体、後の文。"""
    lo, hi = max(src.body_start, a - 2000), min(len(src.raw), b + 2000)
    win = src.raw[lo:hi]
    ends = [m.end() + lo for m in SENT_END.finditer(win)]
    if src.web:  # Web の写しは、句点の無い題や項目が多い。空行も文の区切りとする
        ends += [m.end() + lo for m in re.finditer(r"\n[ \t]*\n", win)]
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
