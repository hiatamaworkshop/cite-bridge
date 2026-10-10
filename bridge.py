# -*- coding: utf-8 -*-
"""引用ブリッジ（抜き書きと引用）の導出と検査。

使い方（リポジトリの根から実行する。書式は SKILL.md、設定は bridge.toml）:
    python bridge.py derive              抜き書きの導く欄（@ で始まる行）を書き直す
    python bridge.py check [--strict]    整合を検査する。崩れがあれば exit 1
    python bridge.py grade [--keys-from <md>]   文献ごとの資料の格と、その内訳を出す
    python bridge.py approve <cID> --by <承認者>  引用の承認を、その時点の本文の指紋つきで記録する
    python bridge.py extract [<key> ...]          原本の PDF から抽出テキストを作る（pymupdf）
    python bridge.py checkpoint [--label …]       check --strict を通った地点をマニフェスト（JSON）で残す
    python bridge.py strip <原稿> <出力>          原稿から引用の印を外した写しを作る（提出物を作る前段）
    python bridge.py snapshot <key> [<URL>]       Web 資料の写しを取得日とハッシュつきで保存する（既定は書誌の URL）

この論文に固有のこと（パス、書誌の書き方）は設定ファイルから受け取り、コードには書かない。

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

# 設定（bridge.toml）から main で埋める
CONFIG = Path("bridge/bridge.toml")
CONFIG_USED = CONFIG
BIB = EXC_DIR = CIT = TXT_DIR = PDF_DIR = WEB_DIR = CKPT_DIR = None
BIB_FORMAT = "keyline"
PDF_RE = WEB_RE = None
APPLIED = None      # 適用した判断ファイルの記録（bridge.applied）
APPROVERS = {}      # 承認者の一覧 {名前: human / model}。空なら名前を問わない（approvers）
# 出典らしき括弧（著者と年など）。印の無い文にあるものを「印の無い出典」として数える（coverage.pattern で替える）
COVER_RE = re.compile(r"[（(][^（）()\n]*?(?<!\d)(?:19|20)\d{2}[a-z]?(?![\d年月日-])[^（）()\n]*[）)]")


def load_config(path):
    import tomllib
    global BIB, EXC_DIR, CIT, TXT_DIR, PDF_DIR, WEB_DIR, BIB_FORMAT, PDF_RE, WEB_RE
    if not path.exists():
        sys.exit(f"設定ファイル {path} が無い（--config で指定する。書き方は SKILL.md）")
    c = tomllib.loads(path.read_text(encoding="utf-8"))
    b, s, r = c.get("bibliography", {}), c.get("sources", {}), c.get("bridge", {})
    BIB = Path(b["path"])
    BIB_FORMAT = b.get("format", "keyline")
    global FILES_FIELD
    FILES_FIELD = b.get("files_field", FILES_FIELD)
    PDF_RE = re.compile(b["pdf_pattern"]) if b.get("pdf_pattern") else None
    WEB_RE = re.compile(b["web_pattern"]) if b.get("web_pattern") else None
    PDF_DIR = Path(s.get("pdf_dir", "references"))
    TXT_DIR = Path(s.get("text_dir", PDF_DIR / "_txt"))
    WEB_DIR = Path(s.get("web_dir", PDF_DIR / "_web"))
    EXC_DIR = Path(r.get("excerpts", "bridge/excerpts"))
    CIT = Path(r.get("citations", "bridge/citations.md"))
    global MARK_RE, QUOTE_RES, NOT_QUOTE_SEP, OUTPUT_LANG, KIND_WORDS, KIND_WORDS_MAP
    m = c.get("manuscript", {})
    if m.get("mark_pattern"):
        MARK_RE = re.compile(m["mark_pattern"])
    if m.get("quote_patterns"):
        QUOTE_RES = [re.compile(x) for x in m["quote_patterns"]]
    NOT_QUOTE_SEP = m.get("not_quote_separator", NOT_QUOTE_SEP)
    global SENT_END_RE, PARAGRAPH, CKPT_DIR
    if m.get("sentence_end"):
        SENT_END_RE = re.compile(m["sentence_end"])
    PARAGRAPH = m.get("paragraph", PARAGRAPH)
    CKPT_DIR = Path(r.get("checkpoints", "bridge/checkpoints"))
    global APPLIED, APPROVERS, COVER_RE
    APPLIED = Path(r.get("applied", CIT.parent / "applied.json"))
    APPROVERS = {str(k): str(v) for k, v in c.get("approvers", {}).items()}
    bad = {k: v for k, v in APPROVERS.items() if v not in ("human", "model")}
    if bad:
        sys.exit(f"approvers の種類は human か model（{bad}）")
    if c.get("coverage", {}).get("pattern"):
        COVER_RE = re.compile(c["coverage"]["pattern"])
    OUTPUT_LANG = c.get("output", {}).get("language", OUTPUT_LANG)
    # 節の種類の語と、抽出が読めるかを見る頻出語は、既定（英語と日本語）に足せる
    extra = c.get("section_kinds", {})
    KIND_WORDS = [(k, ws + [w.lower() for w in extra.get(k, [])]) for k, ws in KIND_WORDS]
    KIND_WORDS_MAP = dict(KIND_WORDS)
    COMMON_EN.update(w.lower() for w in c.get("detect", {}).get("common_words", []))

STRENGTHS = {"観察", "示唆", "主張", "一般化", "条件付き"}
DIFFS = {"一致", "言い換え", "限定つき一般化", "外挿"}
KINDS = {"指示", "主張"}
EXC_REQUIRED = ["逐語", "強さ", "要約", "言っていないこと", "記入"]

# 欄名と値は日本語を正とし、英語の別名も受ける。導く欄を書く言語は設定の output.language で選ぶ
FIELD_ALIASES = {
    "verbatim": "逐語", "strength": "強さ", "summary": "要約", "not_said": "言っていないこと",
    "written_by": "記入", "source_check": "原本での確認", "kind": "種類", "excerpts": "抜き書き",
    "source": "文献", "reason": "理由", "interpretation": "解釈", "diff": "原文との差", "approval": "承認",
    "not_quotes": "引用でない句", "target": "対象",
    "grade": "格", "text": "抽出", "match": "照合", "location": "所在", "section_kind": "節の種類",
    "before": "前", "sentence": "含む文", "after": "後", "also_found_in": "他の文献で一致",
    "approved_fingerprint": "承認時の指紋", "approved_text": "承認時の本文",
    "approval_note": "承認の理由", "approved_evidence": "承認時の根拠",
    "returned_reason": "差し戻しの理由", "returned_fingerprint": "差し戻し時の指紋", "returned_evidence": "差し戻し時の根拠",
    "summary_check": "要約の確認", "summary_check_fingerprint": "要約の確認時の指紋", "remarks": "指摘",
}
# @ 行のうち、導く欄ではなく道具が書く記録（derive は消さず、導き直しの比較にも入れない）
RECORD_FIELDS = {"承認時の指紋", "承認時の本文", "承認時の根拠", "差し戻し時の指紋", "差し戻し時の根拠", "要約の確認時の指紋"}
FIELD_NAMES_EN = {v: k for k, v in FIELD_ALIASES.items()}
VALUE_ALIASES = {
    "強さ": {"observation": "観察", "suggestion": "示唆", "claim": "主張", "generalization": "一般化", "conditional": "条件付き"},
    "原文との差": {"identical": "一致", "paraphrase": "言い換え", "qualified_generalization": "限定つき一般化",
               "extrapolation": "外挿"},
    "種類": {"pointer": "指示", "claim": "主張"},
    "承認": {"none": "未"},
}
RETURNED = "差し戻し"  # 承認の欄の値。英語の原稿では returned とも書ける（_approval_state で読む）
OUTPUT_LANG = "ja"


def out_name(name):
    return FIELD_NAMES_EN.get(name, name) if OUTPUT_LANG == "en" else name


FIELD_RE = re.compile(r"^(@?)([^\s:@][^:]*?):\s?(.*)$")
MARK_RE = re.compile(r"〔(c\d{3,})〕")  # 原稿の中の引用の印。グループ1が ID（設定 manuscript.mark_pattern で替える）
QUOTE_RES = [re.compile(r"「([^「」]{10,})」"), re.compile(r"\"([^\"]{20,})\"")]  # 照合する引用符（manuscript.quote_patterns）
NOT_QUOTE_SEP = "／"
SENT_END_RE = re.compile(r"[。！？]")  # 原稿の文の終わり（manuscript.sentence_end）。英語の原稿は '[。！？]|[.!?](?=\\s)' 等
PARAGRAPH = "line"
KEY_LINE_RE = re.compile(r"^key:\s*(\S+)\s*$")


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


# ---------------------------------------------------------------- 書誌と格

def parse_bib():
    """書誌を {key: {entry, pdfs}} にする。形式ごとの読み方はアダプタに分ける。"""
    if BIB_FORMAT not in BIB_ADAPTERS:
        sys.exit(f"書誌の形式 '{BIB_FORMAT}' には対応していない（{sorted(BIB_ADAPTERS)}）")
    return BIB_ADAPTERS[BIB_FORMAT](BIB.read_text(encoding="utf-8"))


def bib_keyline(text):
    """「key: <key>」行の直前が書誌の行、直後の（ で始まる行が注記、という形。"""
    lines = text.splitlines()
    bib = {}
    for i, ln in enumerate(lines):
        m = KEY_LINE_RE.match(ln.strip())
        if not m:
            continue
        note = lines[i + 1] if i + 1 < len(lines) and lines[i + 1].startswith("（") else ""
        pdfs = PDF_RE.findall(note) if PDF_RE else []
        bib[m.group(1)] = {"entry": lines[i - 1], "pdfs": pdfs}
    return bib


def _entry_text(authors, year, title, container, doi, url):
    """書誌の一行の文字列を組む（照合には使わない。格の判定と表示のため）。"""
    parts = [", ".join(authors) or "?", f"({year or 'n.d.'}).", (title or "?") + "."]
    if container:
        parts.append(f"*{container}*.")
    if doi:
        parts.append(f"https://doi.org/{doi}")
    elif url:
        parts.append(url)
    return " ".join(parts)


def _pdf_paths(value):
    """file 欄から PDF のパスを取る。Zotero/Better BibTeX の「パス」と JabRef の「:パス:PDF」の両方、; 区切りを受ける。"""
    if isinstance(value, list):
        value = ";".join(value)
    return [x.strip() for x in re.findall(r"[^:;{}]+?\.pdf", value or "", re.I)]


def bib_csljson(text):
    """CSL-JSON（Zotero 等の書き出し）。id が key。PDF は設定の files_field（既定 file）の欄から取る。"""
    import json
    data = json.loads(text)
    items = data.get("items", []) if isinstance(data, dict) else data
    bib = {}
    for it in items:
        authors = [a.get("family") or a.get("literal", "") for a in it.get("author", [])]
        year = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        bib[it["id"]] = {
            "entry": _entry_text(authors, year, it.get("title"), it.get("container-title"), it.get("DOI"), it.get("URL")),
            "pdfs": _pdf_paths(it.get(FILES_FIELD)),
        }
    return bib


def _bibtex_fields(body):
    """field = {…} / "…" / 数字 を、波括弧の入れ子を数えて読む。"""
    fields, i, n = {}, 0, len(body)
    while i < n:
        m = re.compile(r"\s*,?\s*([A-Za-z][\w-]*)\s*=\s*").match(body, i)
        if not m:
            break
        name, i = m.group(1).lower(), m.end()
        if i < n and body[i] == "{":
            depth, j = 0, i
            while j < n:
                depth += {"{": 1, "}": -1}.get(body[j], 0)
                if depth == 0:
                    break
                j += 1
            value, i = body[i + 1:j], j + 1
        elif i < n and body[i] == '"':
            j = body.find('"', i + 1)
            value, i = body[i + 1:j], j + 1
        else:
            m2 = re.compile(r"[^,]*").match(body, i)
            value, i = m2.group(0).strip(), m2.end()
        fields[name] = re.sub(r"\s+", " ", value.replace("{", "").replace("}", "")).strip()
    return fields


def bib_bibtex(text):
    """BibTeX。引用キーが key。PDF は設定の files_field（既定 file）の欄から取る。"""
    bib = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        if m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        depth, j = 1, m.end()
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        f = _bibtex_fields(text[m.end():j - 1])
        authors = [a.split(",")[0].strip() for a in re.split(r"\s+and\s+", f.get("author", "")) if a.strip()]
        bib[m.group(2)] = {
            "entry": _entry_text(authors, f.get("year"), f.get("title"), f.get("journal") or f.get("booktitle"),
                                 f.get("doi"), f.get("url")),
            "pdfs": _pdf_paths(f.get(FILES_FIELD.lower(), "")),
        }
    return bib


BIB_ADAPTERS = {"keyline": bib_keyline, "csl-json": bib_csljson, "bibtex": bib_bibtex}
FILES_FIELD = "file"


def garbled(raw, entry):
    s = re.sub(r"\s", "", raw)
    if len(s) < 50:  # 画像だけの PDF 等。要旨だけの短い抽出は通す
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
                raw = txt.read_text(encoding="utf-8", errors="replace")
                if raw.startswith("<!-- ocr"):  # 道具の外で OCR したテキスト。誤読があるので近似一致が多くなる
                    return "PDF所持（OCR の抽出）", txt
                bad = garbled(raw, b["entry"])
                if bad:
                    return f"PDF所持（{bad}）", None
                return "PDF所持（抽出あり）", txt
        return "PDF所持（抽出なし）", None
    web = WEB_DIR / f"{key}.txt"
    if web.exists():
        return "Web 写し（保存あり）", web
    if WEB_RE and WEB_RE.search(b["entry"]):
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
            name = m.group(2).strip()
            name = FIELD_ALIASES.get(name, name)
            value = m.group(3).strip()
            value = VALUE_ALIASES.get(name, {}).get(value, value)
            if m.group(1) and name in RECORD_FIELDS:
                cur.setdefault("records", {})[name] = value
            else:
                (cur["derived"] if m.group(1) else cur["fields"])[name] = value
    return head, blocks


def rewrite_derived(path, head_derived, block_derived):
    """導く欄の @ 行を除いて、各区切りの末尾に新しい @ 行を置く。記録の @ 行（RECORD_FIELDS）は残す。"""
    record_names = RECORD_FIELDS | {FIELD_NAMES_EN.get(n, n) for n in RECORD_FIELDS}
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
        body = [ln for ln in seg if not ln.startswith("@") or ln[1:].split(":")[0].strip() in record_names]
        while body and not body[-1].strip():
            body.pop()
        if si == 0:
            derived = head_derived
        else:
            bid = seg[0][3:].strip()
            derived = block_derived.get(bid, {})
        out.extend(body)
        out.extend(f"@{out_name(k)}: {v}" for k, v in derived.items())
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


def printed_page(entry, pdf_page, total, src=None):
    if src is not None and src.web:
        got = f"Web 写し（取得 {src.web.get('retrieved', '?')}）"
        return f"{got} PDF {pdf_page}頁目" if src.web.get("type") == "pdf" else got
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
                    d["所在"] = printed_page(bib[key]["entry"], src.page_of(a), src.pages(), src) + " / " + sec
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

def mask_comments(text):
    """HTML コメントを同じ長さの空白に置き換える（位置は保ち、改行は残す）。"""
    return re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def manuscript_marks(text):
    """印の (ID, 位置, 印に書かれた key か None)。HTML コメントの中は除く。

    印の正規表現は、名前つきのグループ id（無ければグループ1）と、任意の key を持てる。
    key を持つ形（例 LaTeX の \\cite{doe2020}%c017）では、印の key と引用の根拠の文献が合うかも検査する。
    """
    spans = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?-->", text, re.S)]
    gi = MARK_RE.groupindex
    res = []
    for m in MARK_RE.finditer(text):
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
    if PARAGRAPH == "blank":
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
        elif depth == 0 and SENT_END_RE.match(text, i):
            if i >= off:
                return re.sub(r"\s{2,}", " ", text[start:i + 1]).strip()
            start = i + 1
    return re.sub(r"\s{2,}", " ", text[start:z]).strip()


def unmark(text):
    """印を外す。印の正規表現に名前つきのグループ strip があればその部分だけを外す（LaTeX の cite{key} は残す）。"""
    if "strip" in MARK_RE.groupindex:
        return MARK_RE.sub(lambda m: m.group(0)[:m.start("strip") - m.start()] + m.group(0)[m.end("strip") - m.start():], text)
    return MARK_RE.sub("", text)


def fingerprint(sentence):
    s = unmark(sentence)
    s = re.sub(r"\s", "", s)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def coverage_of(text):
    """原稿の出典らしき括弧（COVER_RE）を、印のある文にあるものと無いものに分ける。text は HTML コメントを伏せたもの。

    印の無い文の出典は、このツールが何も確かめていない引用である。check の「確認待ち 0」が引用全体の確認と読まれないよう数を出す。
    """
    marked, unmarked = 0, []
    for m in COVER_RE.finditer(text):
        sent = sentence_at(text, m.start())
        if MARK_RE.search(sent):
            marked += 1
        else:
            unmarked.append((text.count("\n", 0, m.start()) + 1, m.group(0), heading_at(text, m.start())))
    return marked, unmarked


def evidence_hash(refs, excerpts):
    """引用の根拠（抜き書きの ID と逐語）の指紋。根拠を足したり逐語を直したりすると変わる。"""
    s = "\n".join(f"{r}\t{re.sub(r'\s', '', excerpts.get(r, {}).get('逐語', ''))}" for r in sorted(refs))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def summary_fingerprint(fields):
    """抜き書きの、人が確かめる欄（逐語・要約・言っていないこと・強さ）の指紋。"""
    s = "\n".join(re.sub(r"\s", "", fields.get(n, "")) for n in ("逐語", "強さ", "要約", "言っていないこと"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


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


# ---------------------------------------------------------------- コマンド

def cmd_derive(args):
    bib = parse_bib()
    res = derive_excerpts(bib, {})
    for path, (hd, bd) in res.items():
        rewrite_derived(path, hd, bd)
        print(f"derived: {path.as_posix()}（{len(bd)} 件）")


def run_check():
    """整合の検査。表示も終了もせず、結果を辞書で返す（check と checkpoint が使う）。"""
    bib = parse_bib()
    errors, notes, infos = [], [], []
    approvers, grades, used = {}, {}, set()
    cache = {}
    res = derive_excerpts(bib, cache)
    excerpts = {}
    states = {}
    exc_where, summary_checked = [], {}
    for path, (hd, bd) in res.items():
        head, blocks = parse_blocks(path)
        key = head["title"]
        where = path.as_posix()
        if key not in bib:
            errors.append(f"{where}: key '{key}' が書誌リストに無い")
        if head["derived"] != hd:
            errors.append(f"{where}: 導く欄（文献）が古い。derive を実行する")
        grades[hd.get("格", "")] = grades.get(hd.get("格", ""), 0) + 1
        if hd.get("抽出"):
            used.add(hd["抽出"])
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
            exc_where.append((w, key, f))
            if f.get("要約の確認"):
                if b.get("records", {}).get("要約の確認時の指紋") != summary_fingerprint(f):
                    notes.append(f"{w}: 要約の確認の後に欄が変わった。確認し直す")
                else:
                    summary_checked[f["要約の確認"].split()[0]] = summary_checked.get(f["要約の確認"].split()[0], 0) + 1
            else:
                summary_checked["未確認"] = summary_checked.get("未確認", 0) + 1

    # 欄の中の抜き書きへの参照（key#e3、同じ文献の中なら e3）は実在すること。
    # 言っていないことや解釈が原文の別の箇所に依るなら、その箇所を抜き書きにして ID で指す（§16.2 の 4）
    for w, key, f in exc_where:
        for name in ("要約", "言っていないこと"):
            for shown, cands in refs_in(f.get(name, ""), [key]):
                if not any(c in excerpts for c in cands):
                    errors.append(f"{w}: {name}が指す抜き書き '{shown}' が無い")
    infos.append("抜き書きの要約の確認: " + " / ".join(f"{k} {v}" for k, v in sorted(summary_checked.items())))

    # 引用
    if CIT.exists():
        head, blocks = parse_blocks(CIT)
        target = Path(head["fields"].get("対象", ""))
        text = mask_comments(target.read_text(encoding="utf-8")) if target.is_file() else ""
        if not text:
            errors.append(f"{CIT.as_posix()}: 対象の原稿 '{target}' が読めない")
        marks = manuscript_marks(text)
        ids_in_text, keys_in_text = {}, {}
        for cid, off, mkey in marks:
            ids_in_text.setdefault(cid, []).append(off)
            if mkey:
                keys_in_text[cid] = {k.strip() for k in mkey.split(",")}
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
                if cid in keys_in_text and f.get("文献") not in keys_in_text[cid]:
                    errors.append(f"{w}: 原稿の印の key {sorted(keys_in_text[cid])} と 文献 '{f.get('文献')}' が合わない")
                counts["指示"] += 1
                continue
            refs = [r.strip() for r in f.get("抜き書き", "").split(",") if r.strip()]
            if cid in keys_in_text and not ({r.split("#")[0] for r in refs} & keys_in_text[cid]):
                errors.append(f"{w}: 原稿の印の key {sorted(keys_in_text[cid])} と抜き書きの文献が合わない")
            if not refs:
                errors.append(f"{w}: 主張の引用は 抜き書き が要る")
            for r in refs:
                if r not in excerpts:
                    errors.append(f"{w}: 抜き書き '{r}' が無い")
            ref_keys = list(dict.fromkeys(r.split("#")[0] for r in refs))
            for name in ("理由", "解釈"):
                for shown, cands in refs_in(f.get(name, ""), ref_keys):
                    if not any(c in excerpts for c in cands):
                        errors.append(f"{w}: {name}が指す抜き書き '{shown}' が無い")
            for name in ("理由", "原文との差", "記入"):
                if not f.get(name):
                    errors.append(f"{w}: 欄 '{name}' が空")
            if f.get("原文との差") and f["原文との差"] not in DIFFS:
                errors.append(f"{w}: 原文との差は {sorted(DIFFS)} のどれか")
            # 本文の引用符の中の文字列は、指している抜き書きの逐語に含まれていること
            # 引用符の中でも原文の逐語でない句（コマンドの言い方、UI の文字列の一例等）は、人が「引用でない句」に挙げて外す
            not_quotes = [x.strip() for x in re.sub(r"（[^（）]*）|\([^()]*\)$", "", f.get("引用でない句", "")).split(NOT_QUOTE_SEP)
                          if x.strip()]
            for q in [m.group(1) for rx in QUOTE_RES for m in rx.finditer(sent)]:
                if q in not_quotes:
                    infos.append(f"{w}: 「{q}」は引用でない句として外した")
                    continue
                qcjk = any(is_cjk(c) for c in q)
                pool = [excerpts[r]["逐語"] for r in refs if r in excerpts]
                same = [p for p in pool if any(is_cjk(c) for c in p) == qcjk]
                if same and not any(normalize(q, "alnum")[0] in normalize(p, "alnum")[0] for p in same):
                    errors.append(f"{w}: 本文の引用「{q[:30]}…」が抜き書きの逐語に無い")
            state, extra = approval_state(f, b.get("records", {}), fp, evidence_hash(refs, excerpts))
            counts[state] = counts.get(state, 0) + 1
            if state == "未承認":
                notes.append(f"{w}: 未承認（{heading_at(text, ids_in_text[cid][0])}）")
            elif state == "要再確認":
                notes.append(f"{w}: 承認の後に{extra}が変わった。要再確認")
            elif state == "差し戻し":
                notes.append(f"{w}: 差し戻し。書き手が直すのを待っている（{extra}）")
            elif state == "差し戻し後に直された":
                notes.append(f"{w}: 差し戻しの後に直された。確認を待っている（差し戻しの理由: {extra}）")
            else:
                approvers[extra] = approvers.get(extra, 0) + 1
                if APPROVERS and extra not in APPROVERS:
                    notes.append(f"{w}: 承認者 '{extra}' は承認者の一覧に無い")
            for r in refs:
                st, ok = states.get(r, ("", False))
                if (st.startswith("近似一致") or st.startswith("照合不能")) and not ok:
                    notes.append(f"{w}: 根拠 {r} は {st} で、原本での確認が無い")
            if f.get("原文との差") == "外挿":
                notes.append(f"{w}: 外挿。本文に限定を付けるか、自分の主張として書き直す")
        for cid in ids_in_text:
            if cid not in block_ids:
                errors.append(f"{target}: 〔{cid}〕に対応するブロックが無い")
        cov_marked, cov_unmarked = coverage_of(text)
        coverage = {"spans": cov_marked + len(cov_unmarked), "in_marked_sentences": cov_marked, "unmarked": len(cov_unmarked)}
        if coverage["spans"]:
            infos.append(f"網羅: 原稿の出典らしき括弧 {coverage['spans']} のうち、印のある文にあるもの {cov_marked}、"
                         f"印の無い文にあるもの {len(cov_unmarked)}（印の無いものはこのツールが確かめていない。一覧は coverage）")
        returned = counts.get("差し戻し", 0) + counts.get("差し戻し後に直された", 0)
        infos.append(f"引用: 主張 承認済 {counts['承認済']} / 要再確認 {counts['要再確認']} / 未承認 {counts['未承認']}"
                     + (f" / 差し戻し {returned}" if returned else "") + f"、指示 {counts['指示']}")
    else:
        counts, target, coverage = {}, None, {}

    summary = {}
    for st, _ in states.values():
        summary[st] = summary.get(st, 0) + 1
    return {"errors": errors, "notes": notes, "infos": infos, "excerpt_states": summary, "excerpts": len(states),
            "citations": counts, "approvers": approvers, "coverage": coverage,
            "approver_kinds": {k: sum(v for n, v in approvers.items() if APPROVERS.get(n, "不明") == k)
                               for k in sorted({APPROVERS.get(n, "不明") for n in approvers})}, "summary_checks": summary_checked, "grades": grades, "texts": sorted(used),
            "manuscript": str(target) if target else None}


def cmd_coverage(args):
    """印の無い文にある出典らしき括弧を、行の順に並べる（このツールが確かめていない引用の一覧）。"""
    head, _ = parse_blocks(CIT)
    target = Path(head["fields"].get("対象", ""))
    marked, unmarked = coverage_of(mask_comments(target.read_text(encoding="utf-8")))
    for ln, span, sec in unmarked:
        print(f"{target.as_posix()}:{ln}  {span}  （{sec}）")
    print(f"--- 出典らしき括弧 {marked + len(unmarked)}、印のある文 {marked}、印の無い文 {len(unmarked)}")


def cmd_check(args):
    r = run_check()
    errors, notes, infos, summary = r["errors"], r["notes"], r["infos"], r["excerpt_states"]
    for e in errors:
        print("ERROR", e)
    for n in notes:
        print("NOTE ", n)
    for n in infos:
        print("INFO ", n)
    print(f"--- 抜き書き {r['excerpts']} 件 " + " / ".join(f"{k} {v}" for k, v in sorted(summary.items()))
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
    ok = len(summary.get("PDF所持（抽出あり）", [])) + len(summary.get("Web 写し（保存あり）", []))
    print(f"--- {total} 件のうち、機械で照合できるもの {ok} 件（{round(100 * ok / max(1, total))}%）")


def load_excerpt_fields():
    """{key#eN: 書く欄}。derive をせずに読む（承認と review が使う）。"""
    res = {}
    for path in sorted(EXC_DIR.glob("*.md")):
        head, blocks = parse_blocks(path)
        for b in blocks:
            res[f"{head['title']}#{b['id']}"] = b["fields"]
    return res


def _replace_block_lines(path, bid, drop_re, new_lines):
    """path の ## bid のブロックから drop_re に当たる行を除き、ブロックの末尾に new_lines を置く。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    out, inblock, done = [], False, False
    for ln in lines:
        if ln.startswith("## "):
            if inblock and not done:
                while out and not out[-1].strip():
                    out.pop()
                out.extend(new_lines + [""])
                done = True
            inblock = ln[3:].strip() == bid
        if inblock and re.match(drop_re, ln):
            continue
        out.append(ln)
    if inblock and not done:
        while out and not out[-1].strip():
            out.pop()
        out.extend(new_lines)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


def _citation_now(cid):
    """(本文の文, 本文の指紋, 根拠の指紋, ブロックの欄)。"""
    head, blocks = parse_blocks(CIT)
    target = Path(head["fields"].get("対象", ""))
    text = mask_comments(target.read_text(encoding="utf-8"))
    offs = [off for c, off, _ in manuscript_marks(text) if c == cid]
    if len(offs) != 1:
        sys.exit(f"原稿に〔{cid}〕がちょうど一つ無い（{len(offs)} 箇所）")
    block = next((b for b in blocks if b["id"] == cid), None)
    if block is None:
        sys.exit(f"{CIT.as_posix()} に {cid} のブロックが無い")
    sent = sentence_at(text, offs[0])
    refs = [r.strip() for r in block["fields"].get("抜き書き", "").split(",") if r.strip()]
    return sent, fingerprint(sent), evidence_hash(refs, load_excerpt_fields()), block["fields"]


APPROVAL_LINE_RE = r"^@?(承認|差し戻し|approval|approved_|returned_)"


def approver_problem(by):
    """承認者の一覧があり、by がそこに無ければ理由の文を返す。一覧は事故（打ち間違い、別名）を防ぐもので、悪意は防がない。"""
    if APPROVERS and by not in APPROVERS:
        return f"'{by}' は承認者の一覧（設定の approvers）に無い。一覧: {', '.join(f'{k}（{v}）' for k, v in APPROVERS.items())}"
    return None


def default_approver():
    """コマンドの例に出す名前。一覧の最初の人、一覧が無ければ「人」。"""
    return next((k for k, v in APPROVERS.items() if v == "human"), "人")


def write_approval(cid, by, note=None, send_back=False, seen=None, dry=False):
    """承認か差し戻しを書く。seen=(本文の指紋, 根拠の指紋) を渡すと、今の指紋と合うときだけ書く。

    返り値は (書いたか, 文言)。承認は人の指示があるときだけ行う（AI が自分の書いた引用を承認しない）。
    """
    if approver_problem(by):
        return False, f"{cid}: " + approver_problem(by)
    sent, fp, ev, f = _citation_now(cid)
    if seen and tuple(seen) != (fp, ev):
        return False, f"{cid}: 判断した後に{'本文' if seen[0] != fp else '根拠'}が変わった。書かなかった（review を作り直して見直す）"
    if f.get("種類") != "主張":
        return False, f"{cid}: 主張の引用ではない"
    today = datetime.date.today().isoformat()
    if send_back:
        if not note:
            return False, f"{cid}: 差し戻しには理由が要る"
        new = [f"{out_name('承認')}: {RETURNED} {by} {today}", f"{out_name('差し戻しの理由')}: {note}",
               f"@{out_name('差し戻し時の指紋')}: {fp}", f"@{out_name('差し戻し時の根拠')}: {ev}"]
        msg = f"差し戻しを記録: {cid} {by} {today}"
    else:
        new = [f"{out_name('承認')}: {by} {today}"]
        if note:
            new.append(f"{out_name('承認の理由')}: {note}")
        new += [f"@{out_name('承認時の指紋')}: {fp}", f"@{out_name('承認時の根拠')}: {ev}",
                f"@{out_name('承認時の本文')}: {sent}"]
        msg = f"承認を記録: {cid} {by} {today} 指紋={fp} 根拠={ev}"
    if dry:
        return True, f"{cid}: {'差し戻し' if send_back else '承認'}"
    _replace_block_lines(CIT, cid, APPROVAL_LINE_RE, new)
    return True, msg


def write_confirm(eid, by, note=None, seen=None, dry=False):
    """抜き書きの要約・言っていないこと・強さを確かめた記録を書く。seen（要約の指紋）が今と合うときだけ書く。"""
    if "#" not in eid:
        return False, "抜き書きは key#eN で指す"
    if approver_problem(by):
        return False, f"{eid}: " + approver_problem(by)
    key, bid = eid.split("#", 1)
    for path in sorted(EXC_DIR.glob("*.md")):
        head, blocks = parse_blocks(path)
        if head["title"] != key:
            continue
        b = next((x for x in blocks if x["id"] == bid), None)
        if b is None:
            break
        sfp = summary_fingerprint(b["fields"])
        if seen and seen != sfp:
            return False, f"{eid}: 確かめた後に要約か逐語が変わった。書かなかった"
        if dry:
            return True, f"{eid}: 要約の確認"
        today = datetime.date.today().isoformat()
        new = [f"{out_name('要約の確認')}: {by} {today}" + (f"（{note}）" if note else ""),
               f"@{out_name('要約の確認時の指紋')}: {sfp}"]
        _replace_block_lines(path, bid, r"^@?(要約の確認|summary_check)", new)
        hd, bd = derive_excerpts(parse_bib(), {})[path]  # 導く欄をブロックの末尾へ並べ直す
        rewrite_derived(path, hd, bd)
        return True, f"要約の確認を記録: {eid} {by} {today}"
    return False, f"抜き書き '{eid}' が無い"


def write_remark(cid, by, remark, dry=False):
    """引用の「指摘」の欄に足す。承認の判断とは別の、論文への気づきで、指紋には入らない。同じ文は二度足さない。"""
    head, blocks = parse_blocks(CIT)
    b = next((x for x in blocks if x["id"] == cid), None)
    if b is None:
        return False, f"{cid}: 引用のブロックが無い"
    remark = re.sub(r"\s+", " ", remark).strip()
    have = b["fields"].get("指摘", "")
    if remark in have:
        return True, f"{cid}: 指摘は記録済み"
    if dry:
        return True, f"{cid}: 指摘"
    entry = f"{remark}（{by} {datetime.date.today().isoformat()}）"
    _replace_block_lines(CIT, cid, r"^(指摘|remarks):", [f"{out_name('指摘')}: " + (have + " ｜ " + entry if have else entry)])
    return True, f"指摘を記録: {cid}"


def cmd_approve(args):
    """承認か差し戻しを記録する。承認は人の指示があるときだけ行う（AI が自分の書いた引用を承認しない）。"""
    if args.send_back and not args.note:
        sys.exit("差し戻しには --note で理由を書く")
    ok, msg = write_approval(args.cid, args.by, args.note, args.send_back)
    if not ok:
        sys.exit(msg)
    print(msg)


def cmd_confirm(args):
    """抜き書きの要約・言っていないこと・強さを、人（または書き手と別の者）が原文と照らして確かめたことを記録する。"""
    ok, msg = write_confirm(args.eid, args.by, args.note)
    if not ok:
        sys.exit(msg)
    print(msg)


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


def cmd_apply(args):
    """承認の HTML が書き出した判断ファイルを、指紋を照らしてから書き込む。

    HTML はサーバを持たず、書き込みもしない。判断はファイルとしてここへ渡り、書き込みは approve・confirm と同じ関数を通る。
    HTML を作った後に本文・根拠・要約が変わったものは書かずに報告する（見ていないものへの承認を防ぐ）。
    適用したファイルは記録し（設定の bridge.applied）、同じファイルと、最後に適用したものより前に保存されたファイルは断る
    （保存は判断をすべて含めて書き出すので、古いファイルを後から適用すると判断が巻き戻る）。
    """
    import json
    head, _ = parse_blocks(CIT)
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
    log = json.loads(APPLIED.read_text(encoding="utf-8")) if APPLIED.exists() else {}
    ent = log.setdefault(manuscript, {"last_saved": "", "files": []})
    sha = hashlib.sha256(raw).hexdigest()
    if any(f["sha256"] == sha for f in ent["files"]):
        sys.exit("この判断ファイルは適用済み")
    if ent["last_saved"] and d.get("saved", "") <= ent["last_saved"] and not args.allow_older:
        sys.exit(f"この判断ファイル（保存 {d.get('saved')}）は、最後に適用したもの（保存 {ent['last_saved']}）より古い。"
                 "判断が巻き戻るので断った（意図したときだけ --allow-older）")
    done, skipped = [], []
    for x in d.get("decisions", []):
        if x.get("action"):
            ok, msg = write_approval(x["id"], by, x.get("note") or None, x["action"] == "send_back",
                                     seen=(x["fingerprint"], x["evidence"]), dry=args.dry_run)
            (done if ok else skipped).append(msg)
        if x.get("remark"):
            ok, msg = write_remark(x["id"], by, x["remark"], dry=args.dry_run)
            (done if ok else skipped).append(msg)
    for x in d.get("confirms", []):
        ok, msg = write_confirm(x["id"], by, seen=x["fingerprint"], dry=args.dry_run)
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
        APPLIED.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if skipped:
        sys.exit(1)


def _page_image(key, bib, src, quote, outdir):
    """根拠の逐語がある頁を PNG にする。PDF が無ければ None。"""
    label, a, _ = locate(quote, src)
    if a is None:
        return None
    pdf = None
    for name in bib[key]["pdfs"]:
        if (TXT_DIR / (Path(name).stem + ".txt")) == src.path:
            pdf = PDF_DIR / name
    if pdf is None and (WEB_DIR / f"{key}.pdf").exists():
        pdf = WEB_DIR / f"{key}.pdf"
    if pdf is None or not pdf.exists():
        return None
    import pymupdf
    page = src.page_of(a)
    out = Path(outdir) / f"{key}_p{page}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        pymupdf.open(pdf)[page - 1].get_pixmap(dpi=150).save(out)
    return out


def review_data(cids=None, images=None, include_done=False):
    """人の確認に要る材料を、引用ごとの辞書の並びで返す（review の md と JSON、外の表示が使う）。

    原稿の順に並べる。cids を渡せばそれだけ、渡さなければ確認待ちのもの（include_done なら承認済と指示も）。
    """
    bib = parse_bib()
    cache = {}
    res = derive_excerpts(bib, cache)
    exc = {}
    for path, (hd, bd) in res.items():
        head, blocks = parse_blocks(path)
        for b in blocks:
            exc[f"{head['title']}#{b['id']}"] = (b["fields"], bd.get(b["id"], {}), hd, b.get("records", {}))
    excerpt_fields = {k: v[0] for k, v in exc.items()}
    head, blocks = parse_blocks(CIT)
    target = Path(head["fields"].get("対象", ""))
    text = mask_comments(target.read_text(encoding="utf-8"))
    pos = {cid: off for cid, off, _ in manuscript_marks(text)}
    checked = run_check()
    tool = Path(sys.argv[0]).as_posix()
    who = default_approver()
    items = []
    for b in sorted(blocks, key=lambda b: pos.get(b["id"], 10 ** 9)):
        cid, f = b["id"], b["fields"]
        if cid not in pos or (cids and cid not in cids):
            continue
        refs = [r.strip() for r in f.get("抜き書き", "").split(",") if r.strip()]
        sent = sentence_at(text, pos[cid])
        if f.get("種類") == "主張":
            state, extra = approval_state(f, b.get("records", {}), fingerprint(sent), evidence_hash(refs, excerpt_fields))
        else:
            state, extra = "指示", f.get("文献", "")
        if not cids and not include_done and state in ("承認済", "指示"):
            continue
        tag = f" {cid}:"
        ln_a = text.rfind("\n", 0, pos[cid]) + 1
        ln_z = text.find("\n", pos[cid])
        para = re.sub(r"\s{2,}", " ", text[ln_a:ln_z if ln_z >= 0 else len(text)]).strip()
        item = {"id": cid, "kind": f.get("種類", ""), "state": state, "state_detail": extra,
                "fingerprint": fingerprint(sent), "evidence_fp": evidence_hash(refs, excerpt_fields), "paragraph": para,
                "line": text.count("\n", 0, pos[cid]) + 1, "section": heading_at(text, pos[cid]), "sentence": sent,
                "fields": {n: f[n] for n in ("理由", "解釈", "原文との差", "引用でない句", "記入", "承認", "承認の理由",
                                             "差し戻しの理由", "指摘") if f.get(n)},
                "errors": [e for e in checked["errors"] if tag in e],
                "notes": [n for n in checked["notes"] if tag in n],
                "evidence": [], "commands": {}}
        for r in refs:
            if r not in exc:
                item["evidence"].append({"id": r, "missing": True})
                continue
            ef, d, hd, rec = exc[r]
            st = d.get("照合", "")
            weak = st.startswith(("近似一致", "照合不能")) or "OCR" in hd.get("格", "")
            img = None
            if weak and images and hd.get("抽出"):
                src = cache.get(Path(hd["抽出"]))
                if src:
                    img = _page_image(r.split("#")[0], bib, src, ef.get("逐語", ""), images)
            ok = bool(ef.get("要約の確認")) and rec.get("要約の確認時の指紋") == summary_fingerprint(ef)
            item["evidence"].append({
                "id": r, "verbatim": ef.get("逐語", ""), "location": d.get("所在", ""), "match": st,
                "grade": hd.get("格", ""), "source_check": ef.get("原本での確認", ""), "weak": weak,
                "image": Path(img).as_posix() if img else None,
                "before": d.get("前", ""), "sentence": d.get("含む文", ""), "after": d.get("後", ""),
                "strength": ef.get("強さ", ""), "summary": ef.get("要約", ""), "not_said": ef.get("言っていないこと", ""),
                "written_by": ef.get("記入", ""), "summary_checked": ef["要約の確認"] if ok else None,
                "summary_fp": summary_fingerprint(ef)})
        if item["kind"] == "主張":
            item["commands"] = {
                "approve": f'python {tool} approve {cid} --by {who} --note "…"',
                "send_back": f'python {tool} approve {cid} --by {who} --send-back --note "…"',
                "confirm": [f"python {tool} confirm {e['id']} --by {who}" for e in item["evidence"]
                            if not e.get("missing") and not e.get("summary_checked")]}
        items.append(item)
    return {"manuscript": target.as_posix(), "date": datetime.date.today().isoformat(),
            "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "citations": items}


def review_md(data):
    out = [f"# 引用の確認（{data['date']}、{data['manuscript']}）", "",
           "各件で、本文と根拠の逐語を読み、承認か差し戻しを決める。AI が書いた要約と解釈は、逐語を読んだ後に見る。",
           "前後の文は抽出テキストのままで、誤読を補っていない。", ""]
    for it in data["citations"]:
        st = it["state"] + (f"（{it['state_detail']}）" if it["state_detail"] and it["state"] not in ("承認済", "指示") else "")
        out += [f"## {it['id']}　{st}", "", f"節: {it['section']}（原稿 {it['line']} 行）", "", "本文:", "",
                f"> {it['sentence']}", ""]
        out += [f"- 整合の崩れ: {e}" for e in it["errors"]] + ([""] if it["errors"] else [])
        if it["fields"].get("差し戻しの理由"):
            out += [f"差し戻しの理由: {it['fields']['差し戻しの理由']}", ""]
        for i, e in enumerate(it["evidence"], 1):
            if e.get("missing"):
                out += [f"### 根拠 {i}: {e['id']}（抜き書きが無い）", ""]
                continue
            out += [f"### 根拠 {i}: {e['id']}", "", f"- 所在: {e['location'] or '（導けない）'}", f"- 照合: {e['match']}",
                    f"- 格: {e['grade']}"]
            if e["source_check"]:
                out.append(f"- 原本での確認: {e['source_check']}")
            out += ["", "逐語:", "", f"> {e['verbatim']}", ""]
            if e["weak"]:
                out += ["抽出テキストに誤読がある。前後の文は頁の画像で読む" + (f": {e['image']}" if e["image"] else
                        "（--images で頁の画像を出せる。PDF が無ければ原本を見る）"), ""]
            out += [f"- {n}（抽出テキストのまま）: {e[k]}" for n, k in (("前", "before"), ("含む文", "sentence"), ("後", "after"))
                    if e[k]] + [""]
            who = "確認済: " + e["summary_checked"] if e["summary_checked"] else "AI の候補、記入: " + e["written_by"]
            out += [f"要約と言っていないこと（{who}）:", "", f"- 強さ: {e['strength']}", f"- 要約: {e['summary']}",
                    f"- 言っていないこと: {e['not_said']}", ""]
        out += [f"### 引用の欄（記入: {it['fields'].get('記入', '')}）", ""]
        out += [f"- {n}: {it['fields'][n]}" for n in ("理由", "解釈", "原文との差", "引用でない句", "承認", "承認の理由", "指摘")
                if it["fields"].get(n)] + [""]
        if it["commands"]:
            c = it["commands"]
            out += ["判断:", "", f"- 承認: `{c['approve']}`", f"- 差し戻し: `{c['send_back']}`"]
            out += [f"- 要約を確かめた: `{x}`" for x in c["confirm"]] + [""]
    if not data["citations"]:
        out.append("確認待ちの引用は無い。")
    return "\n".join(out) + "\n"


def review_page(data):
    """承認の HTML（単体で開ける一枚）。表示と判断の入力だけで、書き込まない。判断はファイルに書き出し、apply で書き込む。

    件数が増える前提で、一件を詰めて描く。逐語を AI の候補より先に置く順は md の review と同じである。
    """
    import base64
    import json
    from html import escape as E

    images = {}  # 同じ頁の画像は一度だけ埋め込み、カードからは名前で指す

    def img_ref(path):
        name = Path(path).name
        if name not in images:
            try:
                images[name] = "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")
            except OSError:
                return None
        return name

    def short(t, n=40):  # 長い記入は切り、全文はマウスを載せると出す
        return t if len(t) <= n else t[:n] + "…"

    uses = {}  # 抜き書きごとに、根拠にしている引用
    for it in data["citations"]:
        for e in it["evidence"]:
            uses.setdefault(e["id"], []).append(it["id"])

    cards, meta = [], []
    for it in data["citations"]:
        if it["kind"] != "主張":
            continue
        cid = E(it["id"])
        sev = "ok" if it["state"] == "承認済" else ("miss" if it["errors"] else ("warn" if it["state"] != "未承認" else "info"))
        sent = E(it["sentence"])
        para = E(it["paragraph"]).replace(sent, f"<mark>{sent}</mark>", 1)
        f = it["fields"]
        detail = f'（{E(it["state_detail"])}）' if it["state_detail"] and it["state"] != "承認済" else ""
        h = [f'<article class="card s-{sev}" id="{cid}" data-id="{cid}" data-done="{int(it["state"] == "承認済")}" tabindex="-1">',
             f'<header><b>〔{cid}〕</b><span class="st s-{sev}">{E(it["state"])}{detail}</span>'
             + (f'<span class="tag">{E(f["原文との差"])}</span>' if f.get("原文との差") else "")
             + f'<span class="mut">{E(it["section"])}・{it["line"]} 行</span>'
             f'<button class="fold" type="button" title="畳む・開く">▾</button></header><div class="body">']
        for e in it["errors"]:
            h.append(f'<p class="err">整合の崩れ：{E(e.split(": ", 1)[-1])}</p>')
        if f.get("差し戻しの理由"):
            h.append(f'<p class="back">差し戻しの理由：{E(f["差し戻しの理由"])}</p>')
        h.append(f'<div class="sent">{sent}<details class="inline"><summary>段落</summary><span class="para">{para}</span></details></div>')
        for i, e in enumerate(it["evidence"], 1):
            eid = E(e["id"])
            if e.get("missing"):
                h.append(f'<div class="ev"><p class="evh">根拠 {i} {eid}（抜き書きが無い）</p></div>')
                continue
            others = [c for c in uses.get(e["id"], []) if c != it["id"]]
            h.append(f'<div class="ev"><p class="evh">根拠 {i} <b>{eid}</b> <span class="mut">'
                     f'{E(e["location"] or "所在を導けない")}・{E(e["match"])}・{E(e["grade"])}'
                     + (f'・他に {E("・".join(others))} の根拠' if others else "") + "</span></p>")
            if e["source_check"]:
                h.append(f'<p class="mut sm">原本での確認：{E(e["source_check"])}</p>')
            h.append(f'<blockquote>{E(e["verbatim"])}</blockquote><div class="tools">')
            ref = img_ref(e["image"]) if e.get("image") else None
            if e["weak"]:
                h.append(f'<details><summary>頁の画像（抽出に誤読あり）</summary><img data-img="{E(ref)}" alt="{eid} の頁"></details>'
                         if ref else '<span class="mut sm">抽出に誤読あり。前後は原本で読む</span>')
            ctx = [(n, e[k]) for n, k in (("前", "before"), ("含む文", "sentence"), ("後", "after")) if e[k]]
            if ctx:
                h.append('<details><summary>前後の文（抽出のまま）</summary><dl>'
                         + "".join(f"<dt>{n}</dt><dd>{E(v)}</dd>" for n, v in ctx) + "</dl></details>")
            h.append("</div>")
            done = bool(e["summary_checked"])
            h.append(f'<div class="ai{" done" if done else ""}"><p class="aih"><span class="tag">{E(e["strength"])}</span>'
                     + (f'<span class="mut sm">確認済（{E(e["summary_checked"])}）</span>' if done else
                        f'<span class="mut sm" title="{E(e["written_by"])}">AI の候補（{E(short(e["written_by"]))}）</span>'
                        f'<label class="cf"><input type="checkbox" data-confirm="{eid}"> 原文と照らして確かめた</label>')
                     + f'</p><p><span class="k">要約</span>{E(e["summary"])}</p>'
                     f'<p><span class="k">言っていない</span>{E(e["not_said"])}</p></div></div>')
        rows = [(n, f[n]) for n in ("理由", "解釈", "引用でない句", "承認の理由", "指摘") if f.get(n)]
        h.append('<dl class="cf-rows">' + "".join(f"<dt>{n}</dt><dd>{E(v)}</dd>" for n, v in rows) + "</dl>"
                 + f'<p class="mut sm" title="{E(f.get("記入", ""))}">記入：{E(short(f.get("記入", ""), 60))}</p></div>')
        h.append(f'<div class="decide" data-choice=""><span class="opts">'
                 f'<label><input type="radio" name="d-{cid}" value="" checked>保留</label>'
                 f'<label><input type="radio" name="d-{cid}" value="approve">承認</label>'
                 f'<label><input type="radio" name="d-{cid}" value="send_back">差し戻し</label></span>'
                 f'<textarea data-note="{cid}" rows="1" placeholder="理由（差し戻しでは必須）"></textarea></div>'
                 f'<div class="remark"><textarea data-remark="{cid}" rows="1" '
                 f'placeholder="指摘（論文への気づき。判断とは別に、引用の「指摘」の欄へ残る）"></textarea></div></article>')
        cards.append("".join(h))
        meta.append({"id": it["id"], "fingerprint": it["fingerprint"], "evidence": it["evidence_fp"],
                     "excerpts": {e["id"]: e["summary_fp"] for e in it["evidence"] if not e.get("missing")}})
    pending = sum(1 for it in data["citations"] if it["kind"] == "主張" and it["state"] != "承認済")
    payload = json.dumps({"manuscript": data["manuscript"], "generated": data["generated"], "citations": meta,
                          "images": images}, ensure_ascii=False).replace("</", "<\\/")
    by_html = ('<select id="by">' + "".join(f'<option value="{E(k)}">{E(k)}（{"人" if v == "human" else "モデル"}）</option>'
                                             for k, v in APPROVERS.items()) + "</select>") if APPROVERS else \
        '<input type="text" id="by" value="人">'
    return REVIEW_PAGE.replace("{{BY}}", by_html).replace("{{TITLE}}", E(f"引用の承認：{data['manuscript']}")) \
        .replace("{{HEAD}}", E(f"{data['manuscript']}・{data['generated']} 作成・確認待ち {pending} 件")) \
        .replace("{{CARDS}}", "\n".join(cards) or '<p class="mut">主張の引用が無い。</p>') \
        .replace("{{DATA}}", payload)


REVIEW_PAGE = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{TITLE}}</title>
<style>
:root { --bg:#f6f6f4; --card:#fff; --fg:#1d1d1b; --mut:#6b6b66; --line:#e2e1dc; --q:#2f6fd6; --ok:#2d7a43; --warn:#9a6400;
  --miss:#b03434; --info:#5d5d58; --ai:#fffaf0; --aib:#d8c18c; --mark:#fff2a8; --okbg:#eaf6ee; --warnbg:#fdf1dc; --tag:#efeee9; }
@media (prefers-color-scheme: dark) { :root { --bg:#191918; --card:#232321; --fg:#e8e7e3; --mut:#a3a29c; --line:#3a3936;
  --q:#7aa7f0; --ok:#6cc58a; --warn:#e2b25a; --miss:#ef8080; --info:#b9b8b2; --ai:#2b281f; --aib:#6e5f3a; --mark:#5a4f1c;
  --okbg:#1f3326; --warnbg:#3a2f1a; --tag:#33322f; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:14px/1.6 "Yu Gothic UI","Yu Gothic","Meiryo","Noto Sans JP",sans-serif; }
.bar { position:sticky; top:0; z-index:2; background:var(--card); border-bottom:1px solid var(--line); padding:6px 16px;
  display:flex; flex-wrap:wrap; gap:4px 14px; align-items:center; font-size:13px; }
.bar h1 { font-size:14px; margin:0; } .bar input[type=text], .bar select { width:9em; padding:1px 6px; font:inherit; }
.bar button { font:inherit; padding:2px 10px; border:1px solid var(--line); border-radius:6px; background:var(--bg); color:var(--fg); cursor:pointer; }
.bar button.primary { background:var(--q); color:#fff; border-color:var(--q); }
main { max-width:880px; margin:0 auto; padding:10px 16px 40vh; }
.note { color:var(--mut); font-size:12px; margin:0 0 8px; }
.mut { color:var(--mut); } .sm { font-size:12px; }
.card { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--line); border-radius:6px; margin:0 0 10px; overflow:hidden; }
.card.s-info { border-left-color:var(--info); } .card.s-warn { border-left-color:var(--warn); }
.card.s-miss { border-left-color:var(--miss); } .card.s-ok { border-left-color:var(--ok); }
.card:focus { outline:2px solid var(--q); outline-offset:1px; }
body.pending-only .card[data-done="1"] { display:none; }
.card.folded .body { display:none; } .card.folded .fold { transform:rotate(-90deg); }
header { display:flex; flex-wrap:wrap; gap:2px 10px; align-items:baseline; padding:6px 12px 0; }
header .mut { font-size:12px; } .fold { margin-left:auto; border:0; background:none; color:var(--mut); cursor:pointer; font-size:14px; }
.st { font-size:12px; } .st.s-ok { color:var(--ok); } .st.s-warn { color:var(--warn); } .st.s-miss { color:var(--miss); } .st.s-info { color:var(--info); }
.tag { font-size:11px; background:var(--tag); border-radius:3px; padding:0 6px; }
.body { padding:0 12px 6px; }
p { margin:2px 0; } .sent { margin:4px 0 6px; }
details.inline { display:inline; margin-left:6px; } details.inline > summary { display:inline; }
details summary { cursor:pointer; color:var(--mut); font-size:12px; } details[open].inline .para { display:block; font-size:13px; margin-top:4px; }
.ev { border-top:1px solid var(--line); padding-top:4px; margin-top:4px; }
.evh { font-size:12px; } .evh b { font-weight:600; }
blockquote { margin:3px 0; padding:3px 10px; border-left:3px solid var(--q); background:var(--bg); }
.tools { display:flex; flex-wrap:wrap; gap:0 16px; } .tools details { flex:1 1 100%; } .tools details:not([open]) { flex:0 0 auto; }
details img { max-width:100%; border:1px solid var(--line); margin-top:4px; }
dl { margin:2px 0; } dt { color:var(--mut); font-size:12px; } dd { margin:0 0 2px 1em; overflow-wrap:anywhere; font-size:13px; }
.ai { margin-top:4px; padding:3px 10px; border:1px dashed var(--aib); background:var(--ai); border-radius:4px; font-size:13px; }
.ai.done { border-style:solid; }
.aih { display:flex; flex-wrap:wrap; gap:0 10px; align-items:center; } .cf { margin-left:auto; font-size:12px; }
.k { display:inline-block; min-width:5.5em; color:var(--mut); font-size:12px; }
dl.cf-rows { display:grid; grid-template-columns:auto 1fr; gap:1px 10px; margin-top:6px; border-top:1px solid var(--line); padding-top:4px; }
dl.cf-rows dt { white-space:nowrap; } dl.cf-rows dd { margin:0; }
mark { background:var(--mark); color:inherit; }
.err { color:var(--miss); } .back { color:var(--warn); }
.decide { display:flex; gap:10px; align-items:flex-start; padding:5px 12px; border-top:3px solid var(--line); background:var(--bg); }
.decide[data-choice="approve"] { border-top-color:var(--ok); background:var(--okbg); }
.decide[data-choice="send_back"] { border-top-color:var(--warn); background:var(--warnbg); }
.remark { display:flex; padding:0 12px 5px; background:var(--bg); }
.decide[data-choice="approve"] + .remark { background:var(--okbg); } .decide[data-choice="send_back"] + .remark { background:var(--warnbg); }
.remark textarea { font-size:12px; }
.opts { display:flex; gap:10px; white-space:nowrap; padding-top:2px; } .opts label { cursor:pointer; }
textarea { flex:1; min-width:0; font:inherit; font-size:13px; padding:2px 8px; background:var(--card); color:var(--fg);
  border:1px solid var(--line); border-radius:4px; resize:none; overflow:hidden; }
.keys { font-size:11px; }
@media (max-width:600px) { .decide { flex-wrap:wrap; } textarea { flex-basis:100%; } }
</style></head>
<body class="pending-only">
<div class="bar"><h1>引用の承認</h1><span class="mut">{{HEAD}}</span>
<label class="mut">判断する者 {{BY}}</label>
<label class="mut"><input type="checkbox" id="all"> 承認済も表示</label>
<label class="mut"><input type="checkbox" id="foldDone"> 判断したものを畳む</label>
<span id="count"></span>
<button class="primary" id="save">判断ファイルを保存</button>
<span class="mut keys">j/k 移動・1 保留・2 承認・3 差し戻し・r 理由・m 指摘・f 畳む</span></div>
<main>
<p class="note">本文と根拠の逐語を読んでから判断する。点線の枠は AI の候補である。この HTML は何も書き込まない。
保存した判断ファイルを <code>python .claude/skills/cite-bridge/bridge.py apply &lt;ファイル&gt;</code> に渡すと、
この HTML を作った時点から本文・根拠・要約が変わっていないものだけが書き込まれる。</p>
{{CARDS}}
</main>
<script type="application/json" id="data">{{DATA}}</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const KEY = 'cite-bridge:' + D.manuscript;
const byId = Object.fromEntries(D.citations.map(c => [c.id, c]));
const cards = () => [...document.querySelectorAll('article.card')].filter(a => a.offsetParent !== null);
function load() {
  // 前の版（作った時刻をキーに含めていた）に残っている入力も読む。新しいキーの入力を優先する
  try {
    const merged = {decisions: {}, confirms: []};
    const keys = Object.keys(localStorage).filter(k => k.startsWith(KEY + ':')).sort();
    for (const k of [...keys, KEY]) {
      const s = JSON.parse(localStorage.getItem(k) || '{}');
      if (s.by) merged.by = s.by;
      if (s.foldDone !== undefined) merged.foldDone = s.foldDone;
      Object.assign(merged.decisions, s.decisions || {});
      merged.confirms.push(...(s.confirms || []));
    }
    return merged;
  } catch (e) { return {}; }
}
function store(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }
function grow(t) { t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px'; }
function collect() {
  const s = {decisions: {}, confirms: [], by: document.getElementById('by').value,
             foldDone: document.getElementById('foldDone').checked};
  document.querySelectorAll('article.card').forEach(a => {
    const id = a.dataset.id, r = a.querySelector('input[type=radio]:checked');
    const note = a.querySelector('textarea[data-note]').value.trim();
    const remark = a.querySelector('textarea[data-remark]').value.trim();
    if ((r && r.value) || note || remark) s.decisions[id] = {action: r ? r.value : '', note, remark,
      fingerprint: byId[id].fingerprint, evidence: byId[id].evidence};
    a.querySelector('.decide').dataset.choice = r ? r.value : '';
  });
  document.querySelectorAll('input[data-confirm]:checked').forEach(c => s.confirms.push(c.dataset.confirm));
  s.confirms = [...new Set(s.confirms)];
  return s;
}
function refresh() {
  const s = collect(); store(s);
  const n = Object.values(s.decisions).filter(d => d.action).length;
  document.getElementById('count').textContent = '判断 ' + n + ' 件・要約の確認 ' + s.confirms.length + ' 件';
}
function restore() {
  const s = load();
  if (s.by) document.getElementById('by').value = s.by;
  if (s.foldDone) document.getElementById('foldDone').checked = true;
  for (const [id, d] of Object.entries(s.decisions || {})) {
    const a = document.getElementById(id); if (!a || !byId[id]) continue;
    // 判断した後に本文か根拠が変わった引用は、入力を戻さない（見直してもらう）
    if (d.fingerprint && (d.fingerprint !== byId[id].fingerprint || d.evidence !== byId[id].evidence)) continue;
    const r = a.querySelector('input[type=radio][value="' + (d.action || '') + '"]'); if (r) r.checked = true;
    a.querySelector('textarea[data-note]').value = d.note || '';
    a.querySelector('textarea[data-remark]').value = d.remark || '';
  }
  (s.confirms || []).forEach(e => document.querySelectorAll('input[data-confirm="' + e + '"]').forEach(c => c.checked = true));
}
function foldDecided() {
  const on = document.getElementById('foldDone').checked;
  document.querySelectorAll('article.card').forEach(a => {
    const r = a.querySelector('input[type=radio]:checked');
    if (on && r && r.value) a.classList.add('folded');
  });
}
document.addEventListener('input', e => {
  if (e.target.matches('textarea')) grow(e.target);
  if (e.target.matches('input[data-confirm]'))  // 同じ根拠が他のカードにもあれば、確認の印をそろえる
    document.querySelectorAll('input[data-confirm="' + e.target.dataset.confirm + '"]').forEach(c => c.checked = e.target.checked);
  refresh();
});
document.addEventListener('change', e => { if (e.target.matches('input[type=radio]')) foldDecided(); });
document.addEventListener('click', e => {
  const b = e.target.closest('.fold'); if (b) b.closest('article').classList.toggle('folded');
});
document.addEventListener('toggle', e => {  // 頁の画像は開いたときに入れる（同じ画像を一度だけ持つ）
  const img = e.target.querySelector && e.target.querySelector('img[data-img]');
  if (img && !img.src) img.src = D.images[img.dataset.img];
}, true);
document.getElementById('all').addEventListener('change', e => document.body.classList.toggle('pending-only', !e.target.checked));
document.getElementById('foldDone').addEventListener('change', e => {
  if (!e.target.checked) document.querySelectorAll('article.card.folded').forEach(a => a.classList.remove('folded'));
  foldDecided(); refresh();
});
document.addEventListener('keydown', e => {
  if (e.target.matches('input[type=text], textarea, select') || e.ctrlKey || e.metaKey || e.altKey) {
    if (e.key === 'Escape') e.target.blur();
    return;
  }
  const list = cards(); if (!list.length) return;
  let cur = document.activeElement.closest && document.activeElement.closest('article.card');
  let i = cur ? list.indexOf(cur) : -1;
  const go = j => { const a = list[Math.max(0, Math.min(list.length - 1, j))]; a.focus(); a.scrollIntoView({block: 'start'}); };
  if (e.key === 'j') { go(i + 1); e.preventDefault(); return; }
  if (e.key === 'k') { go(i - 1); e.preventDefault(); return; }
  if (!cur) return;
  const v = {'1': '', '2': 'approve', '3': 'send_back'}[e.key];
  if (v !== undefined) {
    cur.querySelector('input[type=radio][value="' + v + '"]').checked = true; refresh(); foldDecided();
    if (v === 'send_back') cur.querySelector('textarea[data-note]').focus();
    e.preventDefault(); return;
  }
  if (e.key === 'r') { cur.querySelector('textarea[data-note]').focus(); e.preventDefault(); }
  if (e.key === 'm') { cur.querySelector('textarea[data-remark]').focus(); e.preventDefault(); }
  if (e.key === 'f') { cur.classList.toggle('folded'); e.preventDefault(); }
});
document.getElementById('save').addEventListener('click', () => {
  const s = collect(), by = s.by.trim();
  if (!by) { alert('判断する者を書く'); return; }
  const missing = Object.entries(s.decisions).filter(([id, d]) => d.action === 'send_back' && !d.note).map(([id]) => id);
  if (missing.length) { alert('差し戻しには理由が要る: ' + missing.join(', ')); return; }
  const confirms = [];
  for (const e of s.confirms) {
    const c = D.citations.find(c => e in c.excerpts); if (c) confirms.push({id: e, fingerprint: c.excerpts[e]});
  }
  const out = {format: 'cite-bridge-decisions/1', manuscript: D.manuscript, generated: D.generated, by,
    saved: new Date().toISOString(),
    decisions: Object.entries(s.decisions).filter(([id, d]) => d.action || d.remark).map(([id, d]) => ({id, action: d.action,
      note: d.note, remark: d.remark || '',
      fingerprint: byId[id].fingerprint, evidence: byId[id].evidence})),
    confirms};
  if (!out.decisions.length && !out.confirms.length) { alert('判断がまだ無い'); return; }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: 'application/json'}));
  a.download = 'decisions_' + D.manuscript.replace(/[^\w.-]+/g, '_').replace(/\.md$/, '') + '.json';
  document.body.appendChild(a); a.click(); a.remove();
});
restore(); refresh(); foldDecided();
document.querySelectorAll('textarea').forEach(grow);
</script>
</body></html>
"""


def cmd_review(args):
    """人が引用を確かめるための材料を出す。md（既定）は逐語を先に、AI の候補（要約・解釈）を後に置く。

    前後の文は抽出テキストのまま出し、補わない。近似一致・照合不能・OCR の根拠には頁の画像を添える（--images）。
    --json は外の表示（md2docx の review_html 等）へ渡す形で、--all なら承認済と指示の引用も含める。
    表示の側は bridge を読むだけで、承認・差し戻し・確認の書き込みは approve と confirm を通す。
    """
    import json
    if args.html:  # 承認の HTML は承認済も含めて作る（画面で表示を切り替える）。頁の画像は一時フォルダに作って埋め込む
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            data = review_data(args.cids, args.images or tmp, include_done=True)
            doc = review_page(data)
        out = args.out or "review.html"
        Path(out).write_text(doc, encoding="utf-8", newline="\n")
        print(f"ok review: {out}（主張の引用 {sum(1 for c in data['citations'] if c['kind'] == '主張')} 件）")
        return
    data = review_data(args.cids, args.images, include_done=args.all)
    doc = json.dumps(data, ensure_ascii=False, indent=1) + "\n" if args.json else review_md(data)
    if args.out:
        Path(args.out).write_text(doc, encoding="utf-8", newline="\n")
        print(f"ok review: {args.out}（{len(data['citations'])} 件）")
    else:
        print(doc, end="")


def cmd_extract(args):
    """書誌が原本の PDF を指す文献について、抽出テキストを作る。既にあれば --force のときだけ作り直す。"""
    import pymupdf
    bib = parse_bib()
    keys = args.keys or sorted(bib)
    TXT_DIR.mkdir(parents=True, exist_ok=True)
    for k in keys:
        if k not in bib:
            print(f"skip {k}: 書誌に無い")
            continue
        for pdf in bib[k]["pdfs"]:
            src, out = PDF_DIR / pdf, TXT_DIR / (Path(pdf).stem + ".txt")
            if not src.exists():
                print(f"skip {k}: {src} が無い")
                continue
            if out.exists() and not args.force:
                continue
            d = pymupdf.open(src)
            text = "\f".join(pg.get_text() for pg in d)  # 頁の区切りは改ページ文字
            bad = garbled(text, bib[k]["entry"])
            if bad:
                print(f"skip {k}: {pdf}（{bad}。OCR か頁の画像で確かめる）")
                continue
            out.write_text(text, encoding="utf-8", newline="\n")
            print(f"ok   {k}: {out.as_posix()}（{len(d)} 頁）")


class _HTMLText:
    """HTML から本文の文字と見出しを取り出す（標準ライブラリだけで動かす）。"""

    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}
    BLOCK = {"p", "div", "li", "tr", "br", "section", "article", "table", "pre", "blockquote", "dd", "dt"}

    def __init__(self):
        from html.parser import HTMLParser
        outer = self
        self.out, self.skip, self.head = [], 0, None

        class P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                cls = dict(attrs).get("class") or ""
                if tag in outer.SKIP:
                    outer.skip += 1
                elif re.fullmatch(r"h[1-6]", tag):
                    outer.out.append("\n" + "#" * int(tag[1]) + " ")
                    outer.head = tag
                elif not outer.head and (tag == "summary" or (tag == "a" and "zippy" in cls.split())):
                    # 折りたたみの見出し（details の summary、Google のヘルプの a.zippy）。階層は分からないので小見出しとする
                    outer.out.append("\n#### ")
                    outer.head = tag
                elif tag in outer.BLOCK:
                    outer.out.append("\n")

            def handle_endtag(self, tag):
                if tag in outer.SKIP:
                    outer.skip = max(0, outer.skip - 1)
                elif tag == outer.head:
                    outer.out.append("\n")
                    outer.head = None
                elif tag in outer.BLOCK:
                    outer.out.append("\n")

            def handle_data(self, data):
                if not outer.skip:
                    outer.out.append(re.sub(r"\s+", " ", data) if outer.head else data)

        self.parser = P(convert_charrefs=True)

    def text(self, html):
        self.parser.feed(html)
        t = "".join(self.out)
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip() + "\n"


def cmd_snapshot(args):
    """Web 資料の写しを保存する。生の HTML は <key>.html（追跡しない想定）、本文は <key>.txt（取得日と生の HTML のハッシュつき）。"""
    import urllib.request
    bib = parse_bib()
    if args.key not in bib:
        sys.exit(f"key '{args.key}' が書誌に無い")
    out = WEB_DIR / f"{args.key}.txt"
    if args.rebuild:
        # 保存した生の HTML から本文を作り直す（取り直さない）。取得日とハッシュは元のまま、作り直した日を足す
        html = WEB_DIR / f"{args.key}.html"
        if not (html.exists() and out.exists()):
            sys.exit(f"{html.as_posix()} と {out.as_posix()} が要る")
        old = Source(out).web or {}
        raw = html.read_bytes()
        if old.get("sha256") != hashlib.sha256(raw).hexdigest():
            sys.exit("生の HTML のハッシュが写しの頭書きと合わない。取り直す")
        body = _HTMLText().text(raw.decode("utf-8", errors="replace"))
        head = (f"<!-- snapshot\nurl: {old.get('url')}\nretrieved: {old.get('retrieved')}\ntype: html\n"
                f"sha256: {old['sha256']}\nrebuilt: {datetime.date.today().isoformat()}\n-->\n")
        out.write_text(head + body, encoding="utf-8", newline="\n")
        print(f"ok {args.key}: {out.as_posix()} を生の HTML から作り直した（取得 {old.get('retrieved')}）")
        return
    if not args.url:  # 既定は書誌の行の URL
        urls = re.findall(r"https?://[^\s）)]+", bib[args.key]["entry"])
        if not urls:
            sys.exit(f"{args.key} の書誌に URL が無い。URL を引数で渡す")
        args.url = urls[0].rstrip(".")
    req = urllib.request.Request(args.url, headers={"User-Agent": "cite-bridge/0.1 (snapshot for citation checking)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        ctype = r.headers.get_content_type() or ""
        charset = r.headers.get_content_charset() or "utf-8"
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    if ctype == "application/pdf" or raw[:5] == b"%PDF-":
        # URL が PDF を指すとき（書誌に URL しか無い論文）。PDF を保存し、頁を保って本文を抽出する
        import pymupdf
        (WEB_DIR / f"{args.key}.pdf").write_bytes(raw)
        d = pymupdf.open(stream=raw, filetype="pdf")
        body, kind = "\f".join(pg.get_text() for pg in d), "pdf"
    else:
        (WEB_DIR / f"{args.key}.html").write_bytes(raw)
        body, kind = _HTMLText().text(raw.decode(charset, errors="replace")), "html"
    today = datetime.date.today().isoformat()
    head = (f"<!-- snapshot\nurl: {args.url}\nretrieved: {today}\ntype: {kind}\n"
            f"sha256: {hashlib.sha256(raw).hexdigest()}\n-->\n")
    out = WEB_DIR / f"{args.key}.txt"
    out.write_text(head + body, encoding="utf-8", newline="\n")
    print(f"ok {args.key}: {out.as_posix()}（{len(body)} 字、取得 {today}）")


def _sha256(path):
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def _git(*a):
    import subprocess
    try:
        r = subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else None
    except OSError:
        return None


def cmd_checkpoint(args):
    """check --strict を通った地点を、マニフェスト（JSON）として残す。通らなければ書かない。

    マニフェストは、どの原稿・書誌・抜き書き・抽出テキストから、どの確認の状態で通ったかを、ハッシュと件数で持つ。
    """
    import json
    r = run_check()
    if r["errors"] or r["notes"]:
        for e in r["errors"]:
            print("ERROR", e)
        for n in r["notes"]:
            print("NOTE ", n)
        print(f"--- checkpoint を書かなかった（整合の崩れ {len(r['errors'])} 件、確認待ち {len(r['notes'])} 件）")
        sys.exit(1)
    now = datetime.datetime.now(datetime.timezone.utc)
    inputs = {"config": str(CONFIG_USED), "bibliography": str(BIB), "manuscript": r["manuscript"], "citations": str(CIT)}
    files = {k: {"path": v, "sha256": _sha256(v)} for k, v in inputs.items() if v}
    files["excerpts"] = {p.as_posix(): _sha256(p) for p in sorted(EXC_DIR.glob("*.md"))}
    files["texts"] = {t: _sha256(t) for t in r["texts"]}
    tracked = [v for v in inputs.values() if v] + [EXC_DIR.as_posix()]
    manifest = {
        "checkpoint": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": args.label,
        "git": {"head": _git("rev-parse", "HEAD"),
                "uncommitted": (_git("-c", "core.quotepath=off", "status", "--porcelain", "--", *tracked) or "").splitlines()},
        "files": files,
        "excerpts": {"total": r["excerpts"], "match": r["excerpt_states"], "grade": r["grades"]},
        "citations": r["citations"],
        "approvers": r["approvers"],
        "approver_kinds": r["approver_kinds"],
        "coverage": r["coverage"],
        "summary_checks": r["summary_checks"],
        "classifier": None,  # 分類器の段（§10）は未実装
    }
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    out = CKPT_DIR / (now.strftime("%Y%m%dT%H%M%SZ") + ".json")
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"ok checkpoint: {out.as_posix()}")
    if manifest["git"]["uncommitted"]:
        print("注意: 未コミットの変更がある状態で書いた（git.uncommitted を参照）")


def cmd_strip(args):
    """原稿から引用の印を外した写しを作る（提出物を作る前段）。原稿そのものは変えない。"""
    text = Path(args.src).read_text(encoding="utf-8")
    n = len(MARK_RE.findall(text))
    out = unmark(text)
    Path(args.out).write_text(out, encoding="utf-8", newline="")
    print(f"ok {args.out}（印 {n} 個を外した）")


def main():
    global CIT
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG), help="設定ファイル（既定は bridge/bridge.toml）")
    ap.add_argument("--citations", help="引用のファイル（既定は設定の値。原稿が複数あるとき、写しで試すとき）")
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
    a.add_argument("--note", help="判断の中身（承認の理由、差し戻しの理由）")
    a.add_argument("--send-back", action="store_true", help="承認せず、書き手へ差し戻す（--note が要る）")
    a.set_defaults(func=cmd_approve)
    cf = sub.add_parser("confirm")
    cf.add_argument("eid", help="key#eN")
    cf.add_argument("--by", required=True)
    cf.add_argument("--note")
    cf.set_defaults(func=cmd_confirm)
    rv = sub.add_parser("review")
    rv.add_argument("cids", nargs="*", help="引用の ID。省くと確認待ちのものすべて")
    rv.add_argument("--images", help="近似一致・OCR の根拠の頁を画像にして置くフォルダ")
    rv.add_argument("-o", "--out", help="書き出すファイル（省くと標準出力）")
    rv.add_argument("--json", action="store_true", help="外の表示へ渡す JSON で出す")
    rv.add_argument("--all", action="store_true", help="承認済と指示の引用も含める")
    rv.add_argument("--html", action="store_true", help="承認の HTML（単体で開ける一枚）を -o に書く")
    ap_ = sub.add_parser("apply")
    ap_.add_argument("file", nargs="?", help="承認の HTML が保存した判断ファイル（JSON）")
    ap_.add_argument("--latest", action="store_true", help="判断ファイルを渡さず、フォルダの中でこの原稿の最新のものを使う")
    ap_.add_argument("--from", dest="source", help="--latest で探すフォルダ（既定はホームの Downloads）")
    ap_.add_argument("--allow-older", action="store_true", help="最後に適用したものより古い判断ファイルを、意図して適用する")
    ap_.add_argument("--dry-run", action="store_true", help="書かずに、書けるかだけを見る")
    ap_.set_defaults(func=cmd_apply)
    rv.set_defaults(func=cmd_review)
    x = sub.add_parser("extract")
    x.add_argument("keys", nargs="*")
    x.add_argument("--force", action="store_true")
    x.set_defaults(func=cmd_extract)
    w = sub.add_parser("snapshot")
    w.add_argument("key")
    w.add_argument("url", nargs="?", help="既定は書誌の行の URL")
    w.add_argument("--rebuild", action="store_true", help="保存した生の HTML から本文を作り直す（取り直さない）")
    w.set_defaults(func=cmd_snapshot)
    cv = sub.add_parser("coverage")
    cv.set_defaults(func=cmd_coverage)
    cp = sub.add_parser("checkpoint")
    cp.add_argument("--label", default="")
    cp.set_defaults(func=cmd_checkpoint)
    st = sub.add_parser("strip")
    st.add_argument("src")
    st.add_argument("out")
    st.set_defaults(func=cmd_strip)
    args = ap.parse_args()
    global CONFIG_USED
    CONFIG_USED = Path(args.config)
    load_config(CONFIG_USED)
    if args.citations:
        CIT = Path(args.citations)
    args.func(args)


if __name__ == "__main__":
    main()
