# -*- coding: utf-8 -*-
"""原本の PDF の抽出（extract）と Web 資料の写し（snapshot）。"""
from pathlib import Path
import datetime
import hashlib
import re
import sys
from . import config as cfg
from .bib import garbled, parse_bib
from .source import Source
from .util import _sha256


def cmd_extract(args):
    """書誌が原本の PDF を指す文献について、抽出テキストを作る（頭書きつき）。既にあれば --force のときだけ作り直す。
    --header-only は、頭書きの無い抽出テキストに頭書きを足す（本文は変えない）。"""
    import pymupdf
    if args.header_only and args.force:
        sys.exit("--header-only と --force は一緒に使えない")
    bib = parse_bib()
    keys = args.keys or sorted(bib)
    cfg.TXT_DIR.mkdir(parents=True, exist_ok=True)
    for k in keys:
        if k not in bib:
            print(f"skip {k}: 書誌に無い")
            continue
        for pdf in bib[k]["pdfs"]:
            src, out = cfg.PDF_DIR / pdf, cfg.TXT_DIR / (Path(pdf).stem + ".txt")
            if args.header_only:
                _add_header(k, pdf, src, out)
                continue
            if not src.exists():
                print(f"skip {k}: {src} が無い")
                continue
            if out.exists() and not args.force:
                continue
            d = pymupdf.open(src)
            body = "\f".join(pg.get_text() for pg in d)  # 頁の区切りは改ページ文字
            bad = garbled(body, bib[k]["entry"])
            if bad:
                print(f"skip {k}: {pdf}（{bad}。OCR か頁の画像で確かめる）")
                continue
            head = _header(pdf, src, d, f"pymupdf {pymupdf.__version__}", f"extracted: {datetime.date.today().isoformat()}")
            out.write_text(head + body, encoding="utf-8", newline="\n")
            print(f"ok   {k}: {out.as_posix()}（{len(d)} 頁）")


def _add_header(key, pdf, src, out):
    """頭書きの無い抽出テキストに、PDF から作った頭書きを足す。本文の字は一字も変えない（バイトのまま残す）。"""
    import pymupdf
    if not out.exists():
        return
    raw = out.read_bytes().decode("utf-8")
    if raw.startswith("<!--"):
        print(f"skip {key}: {out.as_posix()} は既に頭書きがある")
        return
    if not src.exists():
        print(f"skip {key}: {src} が無い")
        return
    d = pymupdf.open(src)
    head = _header(pdf, src, d, "不明（頭書きは後から足した）", f"annotated: {datetime.date.today().isoformat()}")
    out.write_bytes((head + raw).encode("utf-8"))
    print(f"ok   {key}: {out.as_posix()} に頭書きを足した（本文は変えていない）")


def _header(pdf, src, doc, extractor, stamp):
    """抽出の頭書き（設計 §4.1）。頭書きの後に改行を一つ置く。"""
    lines = ["<!-- extract", f"pdf: {pdf}", f"sha256: {_sha256(src)}", f"pages: {len(doc)}"]
    ocr = _ocr_text_layer_pages(doc)
    if ocr:
        lines.append(f"ocr_pages: {_page_ranges(ocr)}")
    lines += [f"extractor: {extractor}", stamp, "-->"]
    return "\n".join(lines) + "\n"


def _ocr_text_layer_pages(doc):
    """OCR の文字の層の頁の集合（設計 §4.2）。見えない文字（描画の型 3）が半分以上で、頁の8割以上を画像が覆う頁。"""
    import pymupdf
    pages = set()
    for pg in doc:
        n = hidden = 0
        for span in pg.get_texttrace():
            n += len(span["chars"])
            if span["type"] == 3:
                hidden += len(span["chars"])
        if not n or hidden * 2 < n:
            continue
        area = abs(pg.rect)
        if any(abs(pymupdf.Rect(im["bbox"]) & pg.rect) / area >= 0.8 for im in pg.get_image_info()):
            pages.add(pg.number + 1)
    return pages


def _page_ranges(pages):
    """頁の集合を「1-7,2,5-6」の形にする（昇順。連続は a-b、単独は a、区切りは「,」）。"""
    runs = []
    for p in sorted(pages):
        if runs and p == runs[-1][1] + 1:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    return ",".join(str(a) if a == z else f"{a}-{z}" for a, z in runs)


class _HTMLText:
    """HTML から本文の文字と見出しを取り出す（標準ライブラリだけで動かす）。"""

    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}
    BLOCK = {"p", "div", "li", "tr", "br", "section", "article", "table", "pre", "blockquote", "dd", "dt", "figure", "figcaption"}

    def __init__(self):
        from html.parser import HTMLParser
        outer = self
        self.out, self.skip, self.head = [], 0, None
        self.text_in_block, self.figure = False, None  # 図の代替テキストは、同じ段落に文字が無い画像だけに出す

        def flush():
            if outer.figure:
                outer.out.append("\n[図: " + outer.figure + "]\n")
            outer.figure, outer.text_in_block = None, False

        class P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                cls = dict(attrs).get("class") or ""
                if tag in outer.SKIP:
                    outer.skip += 1
                elif re.fullmatch(r"h[1-6]", tag):
                    flush()
                    outer.out.append("\n" + "#" * int(tag[1]) + " ")
                    outer.head = tag
                elif not outer.head and (tag == "summary" or (tag == "a" and "zippy" in cls.split())):
                    # 折りたたみの見出し（details の summary、Google のヘルプの a.zippy）。階層は分からないので小見出しとする
                    flush()
                    outer.out.append("\n#### ")
                    outer.head = tag
                elif tag == "img" and not outer.skip and not outer.head and (dict(attrs).get("alt") or "").strip():
                    # 図の代替テキスト。図にしか無い内容（画面の部品の名前等）を、逐語と照合の範囲に入れる（2026-10-16、
                    # Grid 3 の頁で undo と clear が図にだけあり、写しの全文に無いと誤って判断した）。
                    # 文の途中のアイコンやロゴ（"and then" の矢印、"Word Logo"）は図ではないので、同じ段落に文字があれば出さない
                    if not outer.text_in_block:
                        outer.figure = re.sub(r"\s+", " ", dict(attrs)["alt"]).strip()
                elif tag in outer.BLOCK:
                    flush()
                    outer.out.append("\n")

            def handle_endtag(self, tag):
                if tag in outer.SKIP:
                    outer.skip = max(0, outer.skip - 1)
                elif tag == outer.head:
                    outer.out.append("\n")
                    outer.head = None
                elif tag in outer.BLOCK:
                    flush()
                    outer.out.append("\n")

            def handle_data(self, data):
                if not outer.skip:
                    if data.strip():
                        outer.figure, outer.text_in_block = None, True  # 文字と同じ段落にある画像は図にしない
                    outer.out.append(re.sub(r"\s+", " ", data) if outer.head else data)

        self.parser = P(convert_charrefs=True)

    def text(self, html):
        self.parser.feed(html)
        if self.figure:
            self.out.append("\n[図: " + self.figure + "]\n")
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
    out = cfg.WEB_DIR / f"{args.key}.txt"
    if args.rebuild:
        # 保存した生の HTML から本文を作り直す（取り直さない）。取得日とハッシュは元のまま、作り直した日を足す
        html = cfg.WEB_DIR / f"{args.key}.html"
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
    cfg.WEB_DIR.mkdir(parents=True, exist_ok=True)
    if ctype == "application/pdf" or raw[:5] == b"%PDF-":
        # URL が PDF を指すとき（書誌に URL しか無い論文）。PDF を保存し、頁を保って本文を抽出する
        import pymupdf
        (cfg.WEB_DIR / f"{args.key}.pdf").write_bytes(raw)
        d = pymupdf.open(stream=raw, filetype="pdf")
        body, kind = "\f".join(pg.get_text() for pg in d), "pdf"
    else:
        (cfg.WEB_DIR / f"{args.key}.html").write_bytes(raw)
        body, kind = _HTMLText().text(raw.decode(charset, errors="replace")), "html"
    today = datetime.date.today().isoformat()
    head = (f"<!-- snapshot\nurl: {args.url}\nretrieved: {today}\ntype: {kind}\n"
            f"sha256: {hashlib.sha256(raw).hexdigest()}\n-->\n")
    out = cfg.WEB_DIR / f"{args.key}.txt"
    out.write_text(head + body, encoding="utf-8", newline="\n")
    print(f"ok {args.key}: {out.as_posix()}（{len(body)} 字、取得 {today}）")
