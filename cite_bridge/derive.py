# -*- coding: utf-8 -*-
"""抜き書きの導く欄（所在・照合・前後の文）を作る。"""
import re
from . import config as cfg
from .bib import grade_of, parse_bib
from .blocks import parse_blocks, rewrite_derived
from .source import Source, context, locate, normalize, section_at


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
    for path in sorted(cfg.EXC_DIR.glob("*.md")):
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
    for p in sorted(cfg.TXT_DIR.glob("*.txt")):
        if p == own:
            continue
        if p not in cache:
            cache[p] = Source(p)
        if q and q in cache[p].norm("alnum")[0]:
            hits.append(p.name)
    return hits


# ---------------------------------------------------------------- コマンド

def cmd_derive(args):
    bib = parse_bib()
    res = derive_excerpts(bib, {})
    for path, (hd, bd) in res.items():
        rewrite_derived(path, hd, bd)
        print(f"derived: {path.as_posix()}（{len(bd)} 件）")
