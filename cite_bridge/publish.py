# -*- coding: utf-8 -*-
"""公開物の書き出し（publish）。チェックポイントの地点から、公開用の JSON と添える元のファイルを書く（SPEC §12）。

作業中のファイルは変えない。書くのは -o のフォルダだけである。
"""
from pathlib import Path
import datetime
import hashlib
import json
import re
import shutil
import sys
from . import config as cfg
from .bib import doi_of, grade_of, parse_bib
from .blocks import parse_blocks
from .check import run_check
from .checkpoint import tool_version
from .derive import derive_excerpts
from .manuscript import (
    SOURCE_CHECK_RE,
    approval_state,
    approver_family,
    approver_key,
    approver_kind,
    evidence_hash,
    fingerprint,
    heading_at,
    independence_problem,
    manuscript_marks,
    mask_comments,
    parse_source_check,
    sentence_at,
    source_check_state,
    summary_fingerprint,
    uncounted_approval,
    unmark,
    verbatim_fingerprint,
    writer_of,
)
from .source import Source
from .util import _sha256

FORMAT = "cite-bridge-publication/1"
SPEC = {"fingerprint": "sha1-8", "identity": "sha256-jcs"}  # 指紋（SPEC §4）と ID（§12.2）の定義の名前。定義を変えたら名前を変える
RESULT_WORDS = {"一致": "match", "違う": "differs"}  # 原本での確認の結果。作業中のファイルの読み方は変えず、対応表にだけ持つ
SETTINGS = {"reference", "published_by", "license", "withhold_verbatim", "names", "notes", "replaces", "people"}


def canonical(obj):
    """ID にかける前の直列化（RFC 8785 のうち、この形で効く範囲）。鍵を整列し、空白を入れず、UTF-8 のまま書く。数は整数だけ。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def publication_id(doc):
    """公開物の ID（SPEC §12.2）。format・spec・content・records だけから作る。"""
    core = {k: doc[k] for k in ("format", "spec", "content", "records")}
    return "sha256-" + hashlib.sha256(canonical(core).encode("utf-8")).hexdigest()


def verbatim_sha256(verbatim):
    """逐語から空白（SPEC §4）を除いた文字列の SHA-256 の全桁（SPEC §12.3）。"""
    return hashlib.sha256(re.sub(r"\s", "", verbatim).encode("utf-8")).hexdigest()


def settings():
    """設定の [publication] を読み、検査して返す。"""
    s = dict(cfg.PUBLICATION)
    unknown = sorted(set(s) - SETTINGS)
    if unknown:
        sys.exit(f"[publication] に知らない鍵がある: {unknown}（{sorted(SETTINGS)}）")
    for k in ("names", "notes"):
        s.setdefault(k, "show")
        if s[k] not in ("show", "hide"):
            sys.exit(f"[publication] {k} は show か hide（{s[k]!r}）")
    s.setdefault("withhold_verbatim", [])
    if not isinstance(s["withhold_verbatim"], list) or not all(isinstance(x, str) for x in s["withhold_verbatim"]):
        sys.exit("[publication] withhold_verbatim は、文献の key か抜き書きの ID（key#e1）の並び")
    s.setdefault("people", {})
    if not s.get("published_by"):
        sys.exit("[publication] published_by（公開する者）が要る")
    return s


def find_manifest(path):
    """(マニフェストの Path, 中身)。path を省くと、チェックポイントの置き場の最新のもの。"""
    if path:
        p = Path(path)
    else:
        found = sorted(cfg.CKPT_DIR.glob("*.json")) if cfg.CKPT_DIR.is_dir() else []
        if not found:
            sys.exit(f"マニフェストが無い（{cfg.CKPT_DIR.as_posix()}）。checkpoint で書いてから publish する")
        p = found[-1]
    if not p.is_file():
        sys.exit(f"マニフェスト {p.as_posix()} が無い")
    m = json.loads(p.read_text(encoding="utf-8"))
    if m.get("format") != "cite-bridge-manifest/1":
        sys.exit(f"{p.as_posix()} はマニフェスト（cite-bridge-manifest/1）でない")
    return p, m


def manifest_mismatches(m, texts):
    """マニフェストの files と、今のファイルの指紋の食い違い（文の並び）。空なら合っている。"""
    def sha(path):
        return _sha256(path) if Path(path).is_file() else None
    out = []
    files = m.get("files", {})
    now = {"config": str(cfg.CONFIG_USED), "bibliography": str(cfg.BIB), "citations": str(cfg.CIT)}
    for k in ("config", "bibliography", "manuscript", "citations"):
        rec = files.get(k)
        if not rec:
            continue
        if k in now and Path(rec["path"]) != Path(now[k]):
            out.append(f"{k}: マニフェストは {rec['path']}、今の設定は {now[k]}")
        elif sha(rec["path"]) != rec["sha256"]:
            out.append(f"{k}: {rec['path']} がマニフェストの後に変わった" if sha(rec["path"]) else f"{k}: {rec['path']} が無い")
    for name, cur in (("excerpts", {p.as_posix(): _sha256(p) for p in sorted(cfg.EXC_DIR.glob("*.md"))}),
                      ("texts", {t: _sha256(t) for t in texts})):
        old = files.get(name, {})
        for p in sorted(set(old) | set(cur)):
            if p not in cur:
                out.append(f"{name}: {p} が無い")
            elif p not in old:
                out.append(f"{name}: {p} はマニフェストに無い")
            elif old[p] != cur[p]:
                out.append(f"{name}: {p} がマニフェストの後に変わった")
    return out


def _masked(value, hide):
    """記入の値。名前を出さないときは、先頭の名前（書き手）を種類に置き換え、残りの字はそのまま出す。"""
    if not hide or not value:
        return value or ""
    name = writer_of(value)
    return approver_key(name) + value.strip()[len(name):] if name else value


def _who(by, hide):
    """記録の by・kind・family。名前を出さないときは by を null にする。一覧に無い者の kind は unlisted。"""
    return {"by": None if hide else by, "kind": approver_kind(by) or "unlisted", "family": approver_family(by)}


def _date(value):
    m = re.search(r"\d{4}-\d{2}-\d{2}", value or "")
    return m.group(0) if m else None


def _source_entry(key, bib, grade, txt, withheld):
    entry = (bib.get(key) or {}).get("entry", "")
    urls = [u.rstrip(".,;") for u in re.findall(r"https?://[^\s（）()<>\[\]]+", entry)]
    url = next((u for u in urls if not re.match(r"https?://(?:dx\.)?doi\.org/", u)), None)  # DOI の URL は doi の欄に持つ
    src = Source(txt) if txt else None
    head = src.head if src else {}
    file = None
    if src and src.kind in ("extract", "snapshot") and head.get("sha256"):
        file = {"sha256": head["sha256"], "pages": int(head["pages"]) if head.get("pages", "").isdigit() else None,
                "ocr_pages": head.get("ocr_pages") or None}
    return {"key": key, "entry": entry, "doi": doi_of(entry), "url": url, "accessed": (bib.get(key) or {}).get("accessed"),
            "retrieved": head.get("retrieved") if src and src.kind == "snapshot" else None,
            "grade": grade, "file": file, "verbatim_published": not withheld}


def build(manifest, conf, published_at):
    """公開用の JSON（辞書）を作る。書き込まない。"""
    hide = conf["names"] == "hide"
    notes = conf["notes"] == "show"
    withhold = set(conf["withhold_verbatim"])
    bib = parse_bib()
    exc = {}       # key#e1 -> (書く欄, 導く欄, 記録の欄, 文献の導く欄)
    for path, (hd, bd) in derive_excerpts(bib, {}).items():
        head, blocks = parse_blocks(path)
        for b in blocks:
            exc[f"{head['title']}#{b['id']}"] = (b["fields"], bd.get(b["id"], {}), b.get("records", {}), hd)
    fields = {k: v[0] for k, v in exc.items()}

    head, blocks = parse_blocks(cfg.CIT)
    target = Path(head["fields"].get("対象", ""))
    text = mask_comments(target.read_text(encoding="utf-8"))
    pos = {cid: off for cid, off, _ in manuscript_marks(text)}
    citations, approvals, used, pointer_keys = [], [], [], []
    seen = set()
    for b in sorted(blocks, key=lambda b: pos.get(b["id"], 10 ** 9)):
        cid, f = b["id"], b["fields"]
        if cid not in pos or cid in seen:
            continue
        seen.add(cid)
        sent = sentence_at(text, pos[cid])
        fp = fingerprint(sent)
        refs = [r.strip() for r in f.get("抜き書き", "").split(",") if r.strip()] if f.get("種類") == "主張" else []
        ev = evidence_hash(refs, fields, f.get("人の読み", "")) if refs else ""
        citations.append({
            "id": cid, "kind": f.get("種類", ""), "sentence": unmark(sent).strip(), "sentence_fingerprint": fp,
            "excerpts": refs, "source": f.get("文献", ""), "reason": f.get("理由", ""), "interpretation": f.get("解釈", ""),
            "human_reading": f.get("人の読み", ""), "human_reading_by": _masked(f.get("人の読みの記入", ""), hide),
            "diff": f.get("原文との差", ""), "not_quotes": f.get("引用でない句", ""),
            "written_by": _masked(f.get("記入", ""), hide), "evidence_fingerprint": ev,
            "section": heading_at(text, pos[cid])})
        if f.get("種類") != "主張":
            if f.get("文献"):
                pointer_keys.append(f["文献"])
            continue
        used += [r for r in refs if r in exc and r not in used]
        state, by = approval_state(f, b.get("records", {}), fp, ev)
        if state == "承認済" and not uncounted_approval(state, by, f, fields):  # 数えた承認だけを並べる
            approvals.append({"citation": cid, **_who(by, hide), "date": _date(f.get("承認", "")),
                              "note": (f.get("承認の理由") or None) if notes else None,
                              "sentence_fingerprint": fp, "evidence_fingerprint": ev})

    excerpts, summary_checks, source_checks = [], [], []
    for eid in used:
        f, d, rec, _ = exc[eid]
        key = eid.split("#")[0]
        out = key not in withhold and eid not in withhold
        absent = cfg.is_absence(f)  # 不在の抜き書き。逐語は無く、指紋は探した語から作る（SPEC §4、§12.1）
        verbatim = cfg.checked_text(f)
        excerpts.append({
            "id": eid, "verbatim": verbatim if out and not absent else None, "verbatim_fingerprint": verbatim_fingerprint(verbatim),
            "verbatim_sha256": None if absent else verbatim_sha256(verbatim),
            "searched_terms": f["探した語"] if absent else "", "strength": f.get("強さ", ""), "summary": f.get("要約", ""),
            "not_said": f.get("言っていないこと", ""), "secondary_source": f.get("孫引き", ""), "translation": f.get("訳", ""),
            "alternate_location": f.get("別の所在", ""), "evidence_kind": cfg.evidence_kind(f),
            "written_by": _masked(f.get("記入", ""), hide), "summary_fingerprint": summary_fingerprint(f),
            "derived": {"match": d.get("照合", ""), "location": d.get("所在", ""), "section_kind": d.get("節の種類", ""),
                        "human_check": d.get("要ヒューマンチェック", ""), "hits": d.get("当たり", "")}})
        writer = writer_of(f.get("記入"))
        if f.get("要約の確認"):
            name = f["要約の確認"].split()[0]
            if rec.get("要約の確認時の指紋") == summary_fingerprint(f) and not independence_problem(name, [writer]):
                summary_checks.append({"excerpt": eid, **_who(name, hide), "date": _date(f["要約の確認"]),
                                       "summary_fingerprint": summary_fingerprint(f)})
        checker, problem = source_check_state(f, rec, verbatim, writer)
        if f.get("原本での確認") and checker and not problem:
            _, result, page, note = parse_source_check(f["原本での確認"])
            source_checks.append({"excerpt": eid, **_who(checker, hide), "date": SOURCE_CHECK_RE.match(f["原本での確認"]).group(2),
                                  "result": result, "page": page, "note": (note or None) if notes else None,
                                  "verbatim_fingerprint": verbatim_fingerprint(verbatim)})

    sources = []
    hds = {k.split("#")[0]: v[3] for k, v in exc.items()}
    for key in dict.fromkeys([e.split("#")[0] for e in used] + pointer_keys):
        grade, txt = grade_of(key, bib)
        withheld = any(e == key or e.startswith(key + "#") for e in withhold)
        sources.append(_source_entry(key, bib, hds.get(key, {}).get("格", grade), txt, withheld))

    mfile = manifest.get("files", {}).get("manuscript") or {}
    title = re.search(r"^# (.+)$", text, re.M)
    doc = {
        "format": FORMAT, "id": None, "spec": dict(SPEC), "tool": tool_version(),
        "vocabulary": {"strength": {v: k for k, v in cfg.VALUE_ALIASES["強さ"].items()},
                       "diff": {v: k for k, v in cfg.VALUE_ALIASES["原文との差"].items()},
                       "kind": {v: k for k, v in cfg.VALUE_ALIASES["種類"].items()},
                       "evidence_kind": {v: k for k, v in cfg.VALUE_ALIASES["根拠の種類"].items()},
                       "result": dict(RESULT_WORDS)},
        "content": {"manuscript": {"title": title.group(1).strip() if title else None,
                                   "file": {"path": mfile.get("path"), "sha256": mfile.get("sha256")}},
                    "sources": sources, "excerpts": excerpts, "citations": citations},
        "records": {"approvals": approvals, "summary_checks": summary_checks, "source_checks": source_checks,
                    "decided_by": manifest.get("decided_by", {}), "coverage": manifest.get("coverage", {}),
                    "classifier": manifest.get("classifier")},
        # 発表した論文の指し方は ID に入れない（論文に ID を書いてから DOI が決まるので、中身に入れると順序が循環する）
        "publication": {"published_by": conf["published_by"], "published_at": published_at, "license": conf.get("license") or None,
                        "reference": conf.get("reference") or None,
                        "checkpoint": manifest.get("checkpoint"), "replaces": conf.get("replaces") or None,
                        "people": {} if hide else {str(k): {"orcid": (v or {}).get("orcid")} for k, v in conf["people"].items()},
                        "files": {}},
    }
    doc["id"] = publication_id(doc)
    return doc


def _source_path(path):
    """元のファイルを公開物の source/ の下に置くときのパス。作業フォルダの外や絶対パスは、名前だけにする。"""
    p = Path(path)
    parts = [x for x in p.parts if x not in ("..", ".", p.anchor)]
    return "source/" + ("/".join(parts) if not p.is_absolute() and ".." not in p.parts else p.name)


def cmd_publish(args):
    """チェックポイントの地点から、公開物を書き出す（SPEC §12）。マニフェストと今のファイルが合うときだけ書く。"""
    conf = settings()
    out = Path(args.out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        sys.exit(f"{out.as_posix()} は空のフォルダでない（公開物は書き換えない。新しいフォルダへ書き出す）")
    mpath, manifest = find_manifest(args.checkpoint)
    r = run_check()
    bad = manifest_mismatches(manifest, r["texts"])
    if bad:
        for b in bad:
            print("違い ", b)
        sys.exit(f"--- 公開物を書かなかった（マニフェスト {mpath.as_posix()} と今のファイルが合わない {len(bad)} 件。checkpoint を書き直す）")
    if r["errors"] or r["notes"]:  # マニフェストの後に道具を替えたなど、ファイルは同じでも今の検査を通らない場合
        sys.exit(f"--- 公開物を書かなかった（今の検査で整合の崩れ {len(r['errors'])} 件、確認待ち {len(r['notes'])} 件。check で確かめる）")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build(manifest, conf, now)

    # 添える元のファイル（引用・抜き書き・設定・マニフェスト）。逐語を外した文献の抜き書きは添えない。名前を出さないときは一つも添えない
    hide = conf["names"] == "hide"
    withheld = {e.split("#")[0] for e in conf["withhold_verbatim"]}
    files = manifest.get("files", {})
    listed = [(files[k]["path"], True) for k in ("citations", "config") if files.get(k)]
    for p in files.get("excerpts", {}):
        key = parse_blocks(Path(p))[0]["title"]
        listed.append((p, key not in withheld))
    listed.append((mpath.as_posix(), True))
    copies = []
    for path, include in listed:
        include = include and not hide
        name = _source_path(path)
        doc["publication"]["files"][name] = {"sha256": _sha256(path), "included": include}
        if include:
            copies.append((Path(path), out / name))
    out.mkdir(parents=True, exist_ok=True)
    for src, dst in copies:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    (out / "publication.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    c = doc["content"]
    kept = sum(1 for e in c["excerpts"] if e["verbatim"] is None and not e["searched_terms"])  # 不在の抜き書きは逐語を持たない
    print(f"ok publish: {(out / 'publication.json').as_posix()}")
    print(f"  ID: {doc['id']}")
    print(f"  引用 {len(c['citations'])} 件、抜き書き {len(c['excerpts'])} 件（逐語を外したもの {kept} 件）、文献 {len(c['sources'])} 件、"
          f"添えたファイル {len(copies)} 件")
    no_doi = [s["key"] for s in c["sources"] if not s["doi"]]
    print(f"  DOI: 文献 {len(c['sources'])} 件のうち、書誌に DOI があるもの {len(c['sources']) - len(no_doi)}"
          + (f"、無いもの {len(no_doi)}（{', '.join(no_doi)}）。DOI のある文献は、書誌に書いてから書き出し直す" if no_doi else ""))
    print("  ID を論文の本文か補足資料に書くと、読み手が受け取った公開物を確かめられる")
