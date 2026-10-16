# -*- coding: utf-8 -*-
"""人が確かめるための材料（md・JSON・承認の HTML）。"""
from pathlib import Path
import datetime
import re
import sys
from . import config as cfg
from .approve import default_approver
from .bib import parse_bib
from .blocks import parse_blocks
from .check import run_check
from .derive import derive_excerpts, printed_page
from .manuscript import (
    approval_state,
    coverage_items,
    evidence_hash,
    fingerprint,
    heading_at,
    manuscript_marks,
    mask_comments,
    sentence_at,
    summary_fingerprint,
    unmark,
)
from .judge import attach_checks
from .propose import _sources_for, candidate_fp, load_candidates
from .source import context, locate, section_at

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def template(name):
    """承認の HTML のひな形（templates/review.html と review.js）を読む。"""
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _page_image(key, bib, src, quote, outdir):
    """根拠の逐語がある頁を PNG にする。PDF が無ければ None。"""
    label, a, _ = locate(quote, src)
    if a is None:
        return None
    pdf = None
    for name in bib[key]["pdfs"]:
        if (cfg.TXT_DIR / (Path(name).stem + ".txt")) == src.path:
            pdf = cfg.PDF_DIR / name
    if pdf is None and (cfg.WEB_DIR / f"{key}.pdf").exists():
        pdf = cfg.WEB_DIR / f"{key}.pdf"
    if pdf is None or not pdf.exists():
        return None
    import pymupdf
    page = src.page_of(a)
    out = Path(outdir) / f"{key}_p{page}.png"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        pymupdf.open(pdf)[page - 1].get_pixmap(dpi=150).save(out)
    return out


def review_data(cids=None, images=None, include_done=False, all_orphans=False):
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
    head, blocks = parse_blocks(cfg.CIT)
    target = Path(head["fields"].get("対象", ""))
    text = mask_comments(target.read_text(encoding="utf-8"))
    pos = {cid: off for cid, off, _ in manuscript_marks(text)}
    checked = run_check()
    tool = Path(sys.argv[0]).as_posix()
    who = default_approver()
    items = []

    def ev_of(r):
        if r not in exc:
            return {"id": r, "missing": True}
        ef, d, hd, rec = exc[r]
        st = d.get("照合", "")
        weak = st.startswith(("近似一致", "照合不能")) or "OCR" in hd.get("格", "")
        img = None
        if weak and images and hd.get("抽出"):
            src = cache.get(Path(hd["抽出"]))
            if src:
                img = _page_image(r.split("#")[0], bib, src, ef.get("逐語", ""), images)
        ok = bool(ef.get("要約の確認")) and rec.get("要約の確認時の指紋") == summary_fingerprint(ef)
        return {"id": r, "verbatim": ef.get("逐語", ""), "location": d.get("所在", ""), "match": st,
                "grade": hd.get("格", ""), "source_check": ef.get("原本での確認", ""), "weak": weak,
                "image": Path(img).as_posix() if img else None,
                "before": d.get("前", ""), "sentence": d.get("含む文", ""), "after": d.get("後", ""),
                "strength": ef.get("強さ", ""), "summary": ef.get("要約", ""), "not_said": ef.get("言っていないこと", ""),
                "written_by": ef.get("記入", ""), "summary_checked": ef["要約の確認"] if ok else None,
                "summary_fp": summary_fingerprint(ef)}

    def new_ev(key, x, n):
        """候補の新しい抜き書き。所在と前後の文は、既存の抜き書きと同じく道具が導く。"""
        grade, src = _sources_for(key, bib, cache)
        e = {"id": f"{key}（新 {n}）", "new": True, "verbatim": x["逐語"], "grade": grade, "source_check": "",
             "strength": x["強さ"], "summary": x["要約"], "not_said": x["言っていないこと"], "summary_checked": None,
             "location": "", "match": "照合不能", "before": "", "sentence": "", "after": "", "weak": False, "image": None}
        if src:
            label, a, z = locate(x["逐語"], src)
            e["match"] = label
            if a is not None:
                sec, _ = section_at(src, a)
                e["location"] = printed_page(bib[key]["entry"], src.page_of(a), src.pages(), src) + " / " + sec
                e["before"], whole, e["after"] = context(src, a, z)
                e["sentence"] = whole or ""
            e["weak"] = label.startswith("近似") or "OCR" in grade
            if e["weak"] and images:
                img = _page_image(key, bib, src, x["逐語"], images)
                e["image"] = Path(img).as_posix() if img else None
        return e
    def summaries_done(refs):
        return all(e.get("missing") or e.get("summary_checked") for e in (ev_of(r) for r in refs))

    for b in sorted(blocks, key=lambda b: pos.get(b["id"], 10 ** 9)):
        cid, f = b["id"], b["fields"]
        if cid not in pos or (cids and cid not in cids):
            continue
        refs = [r.strip() for r in f.get("抜き書き", "").split(",") if r.strip()]
        sent = sentence_at(text, pos[cid])
        if f.get("種類") == "主張":
            state, extra = approval_state(f, b.get("records", {}), fingerprint(sent),
                                          evidence_hash(refs, excerpt_fields, f.get("人の読み", "")))
        else:
            state, extra = "指示", f.get("文献", "")
        if not cids and not include_done and state in ("承認済", "指示") and summaries_done(refs):
            continue  # 承認済でも、根拠の要約が未確認なら確認待ちとして出す（要約の確認の欄はこのカードにしか無いため）
        tag = f" {cid}:"
        ln_a = text.rfind("\n", 0, pos[cid]) + 1
        ln_z = text.find("\n", pos[cid])
        para = re.sub(r"\s{2,}", " ", text[ln_a:ln_z if ln_z >= 0 else len(text)]).strip()
        item = {"id": cid, "kind": f.get("種類", ""), "state": state, "state_detail": extra,
                "fingerprint": fingerprint(sent), "evidence_fp": evidence_hash(refs, excerpt_fields, f.get("人の読み", "")), "paragraph": para,
                "line": text.count("\n", 0, pos[cid]) + 1, "section": heading_at(text, pos[cid]), "sentence": sent,
                "fields": {n: f[n] for n in ("理由", "解釈", "人の読み", "人の読みの記入", "原文との差", "引用でない句", "記入", "承認", "承認の理由",
                                             "差し戻しの理由", "指摘") if f.get(n)},
                "errors": [e for e in checked["errors"] if tag in e],
                "notes": [n for n in checked["notes"] if tag in n],
                "evidence": [], "commands": {}}
        for r in refs:
            item["evidence"].append(ev_of(r))
        if item["kind"] == "主張":
            item["commands"] = {
                "approve": f'python {tool} approve {cid} --by {who} --note "…"',
                "send_back": f'python {tool} approve {cid} --by {who} --send-back --note "…"',
                "confirm": [f"python {tool} confirm {e['id']} --by {who}" for e in item["evidence"]
                            if not e.get("missing") and not e.get("summary_checked")]}
        items.append(item)
    cands = []
    if not cids:
        cov = {c["item"]: c for c in coverage_items(text)}
        for iid, c in load_candidates()["items"].items():
            if c.get("status") != "pending":
                continue
            cur = cov.get(iid)
            line = cur["line"] if cur else c.get("line", 0)
            ln_a = text.rfind("\n", 0, cur["off"]) + 1 if cur else 0
            ln_z = text.find("\n", cur["off"]) if cur else 0
            para = re.sub(r"\s{2,}", " ", text[ln_a:ln_z if ln_z >= 0 else len(text)]).strip() if cur else ""
            ev, n = [], 0
            for x in c.get("excerpts", []):
                if x.get("use"):
                    ev.append(ev_of(x["use"]))
                else:
                    n += 1
                    ev.append(new_ev(c["key"], x, n))
            cands.append({"id": iid, "candidate": True, "kind": c["kind"], "key": c.get("key"),
                          "entry": bib.get(c.get("key"), {}).get("entry", ""), "cfp": candidate_fp(c),
                          "state": "候補" if cur and not cur["marked"] else "原稿が変わった",
                          "line": line, "section": cur["section"] if cur else c.get("section", ""),
                          "sentence": unmark(cur["sentence"]) if cur else c.get("sentence", ""), "paren": c.get("paren", ""),
                          "paragraph": para, "evidence": ev,
                          "fields": {k: c[k] for k in ("理由", "解釈", "原文との差", "引用でない句", "記入") if c.get(k)}})
    # どの引用も根拠にしていない抜き書きで、要約をまだ確かめていないもの。引用のカードに出ないので、別の一覧にして確認できるようにする
    only = []
    if not cids:
        used = {r.strip() for b in blocks for r in b["fields"].get("抜き書き", "").split(",") if r.strip()}
        for c in cands:
            used.update(e["id"] for e in c["evidence"])
        # all_orphans は、要約を確かめたものも含める（classify --eval が、引用の無い抜き書きを evidence に使うため）
        only = [e for e in (ev_of(r) for r in sorted(exc) if r not in used) if all_orphans or not e.get("summary_checked")]
    res = {"manuscript": target.as_posix(), "date": datetime.date.today().isoformat(),
           "generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "citations": items, "candidates": cands,
           "excerpts_only": only}
    attach_checks(res)  # 分類器の判定（台帳にあれば）。確認の材料に添えるだけで、承認の状態は変えない
    return res


def classifier_line(c):
    """分類器の判定一件を、確認の画面と md に出す一行にする。"""
    rec = f"（記録: {'・'.join(c['record'])}）" if c["record"] else ""
    sc = f"・確からしさ {c['score']:.2f}" if isinstance(c.get("score"), float) else ""
    return f"{c['label']}{rec}　{c['status']}{sc}" + ("" if c["fresh"] else "（本文か材料が変わった。判定し直す）")


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
        out += [f"- {n}: {it['fields'][n]}" for n in ("理由", "解釈", "人の読み", "人の読みの記入", "原文との差", "引用でない句", "承認", "承認の理由", "指摘")
                if it["fields"].get(n)] + [""]
        if it.get("classifier"):
            out += ["分類器の判定（印を立てるだけで、判断は人）:", ""]
            out += [f"- {c['item']} {c['type']}: {classifier_line(c)}" for c in it["classifier"]] + [""]
        if it["commands"]:
            c = it["commands"]
            out += ["判断:", "", f"- 承認: `{c['approve']}`", f"- 差し戻し: `{c['send_back']}`"]
            out += [f"- 要約を確かめた: `{x}`" for x in c["confirm"]] + [""]
    if not data["citations"]:
        out.append("確認待ちの引用は無い。")
    if data.get("candidates"):
        out += ["", f"候補 {len(data['candidates'])} 件（受け入れと却下は review --html で行う）:", ""]
        out += [f"- {c['id']} {c['kind']} {c.get('key') or ''} {c['paren']}（{c['line']} 行）" for c in data["candidates"]]
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

    def ev_html(i, e, owner, label="根拠"):
        eid = E(e["id"])
        if e.get("missing"):
            return f'<div class="ev"><p class="evh">{label} {i} {eid}（抜き書きが無い）</p></div>'
        h = []
        others = [c for c in uses.get(e["id"], []) if c != owner]
        h.append(f'<div class="ev"><p class="evh">{label} {i} <b>{eid}</b> <span class="mut">'
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
        if e.get("new"):  # 候補の新しい抜き書き。受け入れると要約の確認も記録されるので、確認の印は置かない
            who = '<span class="mut sm">AI の候補（受け入れると要約の確認も記録する）</span>'
        elif done:
            who = f'<span class="mut sm">確認済（{E(e["summary_checked"])}）</span>'
        else:
            who = (f'<span class="mut sm" title="{E(e["written_by"])}">AI の候補（{E(short(e["written_by"]))}）</span>'
                   f'<label class="cf"><input type="checkbox" data-confirm="{eid}"> 原文と照らして確かめた</label>')
        h.append(f'<div class="ai{" done" if done else ""}"><p class="aih"><span class="tag">{E(e["strength"])}</span>{who}'
                 f'</p><p><span class="k">要約</span>{E(e["summary"])}</p>'
                 f'<p><span class="k">言っていない</span>{E(e["not_said"])}</p></div></div>')
        return "".join(h)

    def cand_card(it):
        iid = E(it["id"])
        f = it["fields"]
        sent = E(it["sentence"])
        if it["paren"]:
            sent = sent.replace(E(it["paren"]), f'<mark>{E(it["paren"])}</mark>', 1)
        stale = it["state"] != "候補"
        h = [f'<article class="card cand s-{"miss" if stale else "info"}" id="{iid}" data-id="{iid}" data-cand="1" data-done="0" tabindex="-1">',
             f'<header><b>候補 {iid}</b><span class="st s-{"miss" if stale else "info"}">{E(it["state"])}・{E(it["kind"])}</span>'
             + (f'<span class="tag">{E(f["原文との差"])}</span>' if f.get("原文との差") else "")
             + f'<span class="mut">{E(it["section"])}・{it["line"]} 行</span>'
             f'<button class="fold" type="button" title="畳む・開く">▾</button></header><div class="body">']
        if stale:
            h.append('<p class="err">候補を作った後に原稿の文が変わったか、印が置かれた。受け入れても書かれない（propose をやり直す）</p>')
        h.append(f'<div class="sent">{sent}' + (f'<details class="inline"><summary>段落</summary><span class="para">{E(it["paragraph"])}</span></details>'
                                               if it["paragraph"] else "") + "</div>")
        if it.get("key"):
            h.append(f'<p class="mut sm">文献 <b>{E(it["key"])}</b>：{E(it["entry"])}</p>')
        for i, e in enumerate(it["evidence"], 1):
            h.append(ev_html(i, e, it["id"]))
        rows = [(n, f[n]) for n in ("理由", "解釈", "引用でない句") if f.get(n)]
        h.append('<dl class="cf-rows">' + "".join(f"<dt>{n}</dt><dd>{E(v)}</dd>" for n, v in rows) + "</dl>"
                 + f'<p class="mut sm" title="{E(f.get("記入", ""))}">記入：{E(short(f.get("記入", ""), 60))}</p></div>')
        what = {"主張": "受け入れると、抜き書きと引用を書き、原稿に印を置き、承認と要約の確認を記録する",
                "指示": "受け入れると、指示の引用を書き、原稿に印を置く",
                "引用でない": "受け入れると、この括弧を引用でないと記録し、網羅の数から外す"}.get(it["kind"], "")
        h.append(f'<div class="decide" data-choice=""><span class="opts">'
                 f'<label><input type="radio" name="d-{iid}" value="" checked>保留</label>'
                 f'<label><input type="radio" name="d-{iid}" value="accept">受け入れる</label>'
                 f'<label><input type="radio" name="d-{iid}" value="reject">却下</label></span>'
                 f'<textarea data-note="{iid}" rows="1" placeholder="理由（却下では必須。受け入れでは承認の理由になる）"></textarea></div>'
                 f'<p class="mut sm what">{E(what)}</p></article>')
        return "".join(h)

    def summaries_done(it):  # 承認済でも、要約の確認が残る根拠があれば「確認待ちだけ」の表示に残す
        return all(e.get("missing") or e.get("summary_checked") for e in it["evidence"])

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
        h = [f'<article class="card s-{sev}" id="{cid}" data-id="{cid}" data-done="{int(it["state"] == "承認済" and summaries_done(it))}" tabindex="-1">',
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
            h.append(ev_html(i, e, it["id"]))
        rows = [(n, f[n]) for n in ("理由", "解釈", "人の読み", "人の読みの記入", "引用でない句", "承認の理由", "指摘") if f.get(n)]
        rows += [("分類器 " + c["type"], f'{c["item"].split(":", 1)[-1]}　{classifier_line(c)}') for c in it.get("classifier", [])]
        h.append('<dl class="cf-rows">' + "".join(f"<dt>{n}</dt><dd>{E(v)}</dd>" for n, v in rows) + "</dl>"
                 + f'<p class="mut sm" title="{E(f.get("記入", ""))}">記入：{E(short(f.get("記入", ""), 60))}</p></div>')
        h.append(f'<div class="decide" data-choice=""><span class="opts">'
                 f'<label><input type="radio" name="d-{cid}" value="" checked>保留</label>'
                 f'<label><input type="radio" name="d-{cid}" value="approve">承認</label>'
                 f'<label><input type="radio" name="d-{cid}" value="send_back">差し戻し</label></span>'
                 f'<textarea data-note="{cid}" rows="1" placeholder="理由（差し戻しでは必須）"></textarea></div>'
                 f'<div class="remark"><textarea data-remark="{cid}" rows="1" '
                 f'placeholder="指摘（原稿への気づき。判断とは別に、引用の「指摘」の欄へ残る）"></textarea></div></article>')
        cards.append((it["line"], "".join(h)))
        meta.append({"id": it["id"], "fingerprint": it["fingerprint"], "evidence": it["evidence_fp"],
                     "excerpts": {e["id"]: e["summary_fp"] for e in it["evidence"] if not e.get("missing")}})
    for it in data.get("candidates", []):  # 候補も原稿の行の順に、引用のカードの間に並べる
        cards.append((it["line"], cand_card(it)))
        meta.append({"id": it["id"], "candidate": True, "cfp": it["cfp"],
                     "excerpts": {e["id"]: e["summary_fp"] for e in it["evidence"] if not e.get("missing") and not e.get("new")}})
    cards = [c for _, c in sorted(cards, key=lambda x: x[0])]
    # どの引用にも使われていない抜き書き。引用のカードには出ないので、要約の確認だけをここで行う（判断のカードではない）
    only = [e for e in data.get("excerpts_only", []) if not e.get("missing")]
    if only:
        cards.append(f'<section class="orphans"><h2>引用に使われていない抜き書き（{len(only)} 件）</h2>'
                     '<p class="note">原稿のどの引用も根拠にしていない。要約・言っていないこと・強さを原文と照らして確かめたものに印を付ける。'
                     '引用に使うときは、その引用の承認で改めて見る。</p>'
                     + "".join(f'<div class="orphan">{ev_html(i, e, "", "抜き書き")}</div>' for i, e in enumerate(only, 1))
                     + "</section>")
    pending = sum(1 for it in data["citations"] if it["kind"] == "主張" and it["state"] != "承認済")
    n_cand = len(data.get("candidates", []))
    payload = json.dumps({"manuscript": data["manuscript"], "generated": data["generated"], "citations": meta,
                          "orphans": {e["id"]: e["summary_fp"] for e in only}, "images": images},
                         ensure_ascii=False).replace("</", "<\\/")
    by_html = ('<select id="by">' + "".join(f'<option value="{E(k)}">{E(k)}（{"人" if v == "human" else "モデル"}）</option>'
                                             for k, v in cfg.APPROVERS.items()) + "</select>") if cfg.APPROVERS else \
        '<input type="text" id="by" value="人">'
    values = {
        "BY": by_html,
        "TITLE": E(f"引用の承認：{data['manuscript']}"),
        "HEAD": E(f"{data['manuscript']}・{data['generated']} 作成・確認待ち {pending} 件"
                  + (f"・候補 {n_cand} 件" if n_cand else "")
                  + (f"・引用に使われていない抜き書き {len(only)} 件" if only else "")),
        "CARDS": "\n".join(cards) or '<p class="mut">主張の引用も候補も無い。</p>',
        "DATA": payload,
        "SCRIPT": template("review.js"),
    }
    # 一度の置換で差し込む（差し込んだ本文の中の {{…}} は、もう一度置換しない）
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), template("review.html"))


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
