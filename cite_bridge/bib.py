# -*- coding: utf-8 -*-
"""書誌の読み込み（keyline・BibTeX・CSL-JSON のアダプタ）と、文献の格。"""
from pathlib import Path
import re
import sys
from . import config as cfg
from .config import COMMON_EN, KEY_LINE_RE
from .source import Source, is_cjk
from .util import _sha256


# ---------------------------------------------------------------- 書誌と格

def parse_bib():
    """書誌を {key: {entry, pdfs}} にする。形式ごとの読み方はアダプタに分ける。"""
    if cfg.BIB_FORMAT not in BIB_ADAPTERS:
        sys.exit(f"書誌の形式 '{cfg.BIB_FORMAT}' には対応していない（{sorted(BIB_ADAPTERS)}）")
    return BIB_ADAPTERS[cfg.BIB_FORMAT](cfg.BIB.read_text(encoding="utf-8"))


def bib_keyline(text):
    """「key: <key>」行の直前が書誌の行、直後の（ で始まる行が注記、という形。"""
    lines = text.splitlines()
    bib = {}
    for i, ln in enumerate(lines):
        m = KEY_LINE_RE.match(ln.strip())
        if not m:
            continue
        note = lines[i + 1] if i + 1 < len(lines) and lines[i + 1].startswith("（") else ""
        pdfs = cfg.PDF_RE.findall(note) if cfg.PDF_RE else []
        before = lines[i - 1] if i > 0 else ""  # 先頭の key: には直前の行が無い。最後の行を書誌の行として読まない
        am = re.search(r"参照\s*(\d{4}-\d{2}-\d{2})", before)
        bib[m.group(1)] = {"entry": before, "pdfs": pdfs, "accessed": am.group(1) if am else None}
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


def _csl_date(d):
    """CSL-JSON の date-parts を YYYY-MM-DD にする。年・月・日がそろうときだけ。"""
    parts = ((d or {}).get("date-parts") or [[]])[0]
    if len(parts) == 3 and all(parts):
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return None


def _bibtex_date(v):
    m = re.fullmatch(r"\s*(\d{4})-(\d{2})-(\d{2})\s*", v or "")
    return m.group(0).strip() if m else None


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
            "pdfs": _pdf_paths(it.get(cfg.FILES_FIELD)),
            "accessed": _csl_date(it.get("accessed")),
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
            "pdfs": _pdf_paths(f.get(cfg.FILES_FIELD.lower(), "")),
            "accessed": _bibtex_date(f.get("urldate")),
        }
    return bib


BIB_ADAPTERS = {"keyline": bib_keyline, "csl-json": bib_csljson, "bibtex": bib_bibtex}


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


# 読めない字（設計 §4.4 の 4）。置換文字・私用領域・cid
UNREADABLE_RE = re.compile(r"[�-]|\(cid:\d+\)")


def grade_of(key, bib):
    """(格, 抽出テキストの Path か None)。"""
    b = bib.get(key)
    if b is None:
        return "書誌に無い", None
    if b["pdfs"]:
        for pdf in b["pdfs"]:
            txt = cfg.TXT_DIR / (Path(pdf).stem + ".txt")
            if txt.exists():
                src = Source(txt)
                if src.raw.startswith("<!-- ocr"):  # 道具の外で OCR したテキスト。誤読があるので近似一致が多くなる
                    return "PDF所持（OCR の抽出）", txt
                bad = garbled(src.raw[src.body_start:], b["entry"])  # 頭書きは判定の対象にしない
                if bad:
                    return f"PDF所持（{bad}）", None
                if src.ocr_pages():
                    return "PDF所持（OCR の文字の層）", txt
                return "PDF所持（抽出あり）", txt
        return "PDF所持（抽出なし）", None
    web = cfg.WEB_DIR / f"{key}.txt"
    if web.exists():
        return "Web 写し（保存あり）", web
    if cfg.WEB_RE and cfg.WEB_RE.search(b["entry"]):
        return "Web 資料（写しなし）", None
    return "未入手", None


def extraction_diagnosis(key, bib, txt):
    """抽出テキストの崩れの診断（設計 §4.4 の 1〜4）を [(番号, 文)] で返す。直し方の分かるものだけ。

    Web の写しと OCR のテキストには診断しない。PDF が無いときは 1 と 3 を出さない（PDF を持たない機械で注意が出続けないように）。
    """
    src = Source(txt)
    if src.kind == "snapshot" or src.raw.startswith("<!-- ocr"):
        return []
    pdf = next((p for p in bib[key]["pdfs"] if Path(p).stem == txt.stem), None)
    pdf_path = cfg.PDF_DIR / pdf if pdf else None
    have_pdf = pdf_path is not None and pdf_path.exists()
    res = []
    if src.kind is None:
        if have_pdf:
            res.append((1, "頭書きが無い（extract --header-only で足す）"))
    else:
        # 末尾の空の頁は PDF の頁の数には入るが Source.pages() では数えない。どちらの数とも合えば区切りは合っているとみる
        if src.kind == "extract" and "pages" in src.head:
            n = int(src.head["pages"])
            if n not in (src.pages(), src.raw[src.body_start:].count("\f") + 1):
                res.append((2, f"頁の区切りが PDF と合わない（PDF {n} 頁、テキスト {src.pages()} 頁。extract {key} --force で作り直す）"))
        if have_pdf and src.head.get("sha256") != _sha256(pdf_path):
            res.append((3, f"抽出の後に PDF が替わった（extract {key} --force で作り直す）"))
    body = src.raw[src.body_start:]
    chars, bad = len(re.sub(r"\s", "", body)), len(UNREADABLE_RE.findall(body))
    if chars and bad * 1000 > chars:
        res.append((4, f"読めない字 {bad}（置換文字・私用領域・cid）"))
    return res
