# -*- coding: utf-8 -*-
"""抜き書きの導く欄（所在・照合・前後の文）を作る。"""
import re
from . import config as cfg
from .bib import UNREADABLE_RE, extraction_diagnosis, grade_of, parse_bib
from .blocks import parse_blocks, rewrite_derived
from .source import Source, context, is_cjk, locate, normalize, section_at


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
    return {path: derive_excerpt_file(path, bib, sources_cache) for path in sorted(cfg.EXC_DIR.glob("*.md"))}


def rederive_files(paths):
    """書いた抜き書きのファイルごとに、導く欄を導き直して書く。各ファイルは一度だけ導く（apply は書き終えてから、ここへまとめて渡す）。"""
    bib, cache = parse_bib(), {}
    for path in sorted(paths):
        hd, bd = derive_excerpt_file(path, bib, cache)
        rewrite_derived(path, hd, bd)


def derive_excerpt_file(path, bib, sources_cache):
    """一つの抜き書きファイルの (head_derived, {id: derived})。derive_excerpts の一件分。"""
    head, blocks = parse_blocks(path)
    key = head["title"]
    grade, txt = grade_of(key, bib)
    hd = {"格": grade}
    if txt:
        hd["抽出"] = txt.as_posix()
        diag = extraction_diagnosis(key, bib, txt)
        if diag:
            hd["抽出の診断"] = "；".join(text for _, text in diag)
    bd = {}
    src = None
    if txt:
        if txt not in sources_cache:
            sources_cache[txt] = Source(txt)
        src = sources_cache[txt]
    for b in blocks:
        if cfg.is_absence(b["fields"]):
            bd[b["id"]] = derive_absence(b["fields"], grade, src, bib[key]["entry"] if key in bib else "")
            continue
        d = {}
        quote = b["fields"].get("逐語", "")
        a = z = None
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
        reasons = human_check_reasons(grade, src, d["照合"], a, z, quote) if not src or quote else []
        # 文でない根拠（表・グラフ・図）は、照合が一致しても、逐語の字だけでは根拠の中身を確かめられない（SPEC §2.2）
        kind = cfg.evidence_kind(b["fields"])
        if kind != cfg.TEXT_KIND and kind in cfg.EVIDENCE_KINDS:
            reasons.append(f"文でない根拠（{kind}）")
        if reasons:
            d["要ヒューマンチェック"] = "、".join(reasons)
        bd[b["id"]] = d
    return hd, bd


HITS_SHOWN = 3  # 不在の抜き書きの @当たり に、語ごとに出す所在の数
CHECKABLE_GRADES = ("PDF所持（抽出あり）", "Web 写し（保存あり）")  # 機械で照合できる格（SPEC §2.4）


def term_hits(term, src):
    """探した語が抽出テキストの本文にある位置（raw 上の開始位置の並び）。

    逐語の照合の一番ゆるい正規化（NFKC、小文字、文字と数字だけ）で、部分一致で探す。広く当てる側に倒す（SPEC §2.2）。
    文字と数字を含まない語は探せないので、空の並びを返す（check が確認待ちで出す）。
    """
    q, _ = normalize(term, "alnum")
    t, tp = src.norm("alnum")
    out, k = [], t.find(q) if q else -1
    while k >= 0:
        out.append(tp[k])
        k = t.find(q, k + len(q))
    return out


def derive_absence(fields, grade, src, entry):
    """不在の抜き書き（逐語の代わりに探した語を持つ）の導く欄（SPEC §2.2）。所在・節の種類・前後の文は持たない。"""
    if not src:
        return {"照合": f"照合不能（{grade}）", "要ヒューマンチェック": f"照合不能（{grade}）"}
    d, counts, shown, reasons = {}, [], [], []
    for term in cfg.searched_terms(fields):
        hits = term_hits(term, src)
        if not hits:
            continue
        counts.append(f"{term} {len(hits)}")
        places = [printed_page(entry, src.page_of(a), src.pages(), src) + " / " + section_at(src, a)[0] for a in hits[:HITS_SHOWN]]
        more = f"（ほか {len(hits) - HITS_SHOWN}）" if len(hits) > HITS_SHOWN else ""
        shown.append(f"{term}：" + "、".join(places) + more)
    if counts:
        d["照合"] = "当たりあり（" + "、".join(counts) + "）"
        d["当たり"] = "；".join(shown)
        reasons.append("探した語に当たりがある")
    else:
        d["照合"] = "当たりなし"
    # 文献の全体が対象なので、OCR の文字の層は頁を付けない。OCR の頁が一つでもあれば、当たりが無くても機械では保証できない
    if grade == "PDF所持（OCR の抽出）":
        reasons.append("OCR の抽出")
    elif grade == "PDF所持（OCR の文字の層）":
        reasons.append("OCR の文字の層")
    elif grade not in CHECKABLE_GRADES:  # 抽出はあるが、機械で照合できる格でない（抽出が化けている等）。当たりが無くても不在を保証しない
        reasons.append(f"照合不能（{grade}）")
    if reasons:
        d["要ヒューマンチェック"] = "、".join(reasons)
    return d


SHORT_WORDS, SHORT_CHARS = 3, 10  # 短い逐語の上限（欧文の語数、和文の字数。C20）


def is_short_verbatim(quote):
    """短い逐語か。短い逐語は抽出テキストのどこかに偶然当たりやすく、照合が一致しても所在を保証しない。

    和文の字を一つでも含めば空白を除いた字数が 10 字以下、含まなければ空白で区切った語数が 3 語以下を短いとする。
    """
    if any(is_cjk(c) for c in quote):
        return len(re.sub(r"\s", "", quote)) <= SHORT_CHARS
    return len(quote.split()) <= SHORT_WORDS


def human_check_reasons(grade, src, label, a, z, quote=""):
    """要ヒューマンチェックの理由（設計 §5.1）。当たるものをすべて挙げる。a, z は逐語の位置（見つからなければ None）。"""
    if src is None:
        return [f"照合不能（{grade}）"]
    reasons = []
    if label.startswith("近似一致"):
        reasons.append("照合が近似一致")
    if label == "不一致":
        reasons.append("照合で見つからない")
    if grade == "PDF所持（OCR の抽出）":
        reasons.append("OCR の抽出")
    if grade == "PDF所持（OCR の文字の層）":
        if a is None:
            reasons.append("OCR の文字の層")
        elif src.page_of(a) in src.ocr_pages():
            reasons.append(f"OCR の文字の層（PDF {src.page_of(a)}頁目）")
    if a is not None and UNREADABLE_RE.search(src.raw[a:z]):
        reasons.append("逐語の範囲に読めない字")
    if a is not None and is_short_verbatim(quote):
        reasons.append("逐語が短い")
    return reasons


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
