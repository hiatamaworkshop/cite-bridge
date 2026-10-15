# -*- coding: utf-8 -*-
"""書誌の読み込み（keyline・BibTeX・CSL-JSON のアダプタ）と、文献の格。"""
from pathlib import Path
import re
import sys
from . import config as cfg
from .config import COMMON_EN, KEY_LINE_RE
from .source import is_cjk


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
            "pdfs": _pdf_paths(it.get(cfg.FILES_FIELD)),
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
        }
    return bib


BIB_ADAPTERS = {"keyline": bib_keyline, "csl-json": bib_csljson, "bibtex": bib_bibtex}


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


def grade_of(key, bib):
    """(格, 抽出テキストの Path か None)。"""
    b = bib.get(key)
    if b is None:
        return "書誌に無い", None
    if b["pdfs"]:
        for pdf in b["pdfs"]:
            txt = cfg.TXT_DIR / (Path(pdf).stem + ".txt")
            if txt.exists():
                raw = txt.read_text(encoding="utf-8", errors="replace")
                if raw.startswith("<!-- ocr"):  # 道具の外で OCR したテキスト。誤読があるので近似一致が多くなる
                    return "PDF所持（OCR の抽出）", txt
                bad = garbled(raw, b["entry"])
                if bad:
                    return f"PDF所持（{bad}）", None
                return "PDF所持（抽出あり）", txt
        return "PDF所持（抽出なし）", None
    web = cfg.WEB_DIR / f"{key}.txt"
    if web.exists():
        return "Web 写し（保存あり）", web
    if cfg.WEB_RE and cfg.WEB_RE.search(b["entry"]):
        return "Web 資料（写しなし）", None
    return "未入手", None
