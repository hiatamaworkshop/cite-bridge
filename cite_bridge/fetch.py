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


def cmd_extract(args):
    """書誌が原本の PDF を指す文献について、抽出テキストを作る。既にあれば --force のときだけ作り直す。"""
    import pymupdf
    bib = parse_bib()
    keys = args.keys or sorted(bib)
    cfg.TXT_DIR.mkdir(parents=True, exist_ok=True)
    for k in keys:
        if k not in bib:
            print(f"skip {k}: 書誌に無い")
            continue
        for pdf in bib[k]["pdfs"]:
            src, out = cfg.PDF_DIR / pdf, cfg.TXT_DIR / (Path(pdf).stem + ".txt")
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
