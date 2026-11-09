# -*- coding: utf-8 -*-
"""整合の検査（check）、網羅の一覧（coverage）、文献の格の一覧（grade）。"""
from pathlib import Path
import re
import sys
from . import config as cfg
from .bib import bib_occurrences, extraction_diagnosis, grade_of, parse_bib
from .blocks import parse_blocks
from .config import DIFFS, EXC_REQUIRED, KINDS, STRENGTHS
from .derive import derive_excerpts
from .judge import count_judgments, load_ledger, read_ledger, units_from_data
from .manuscript import (
    approval_state,
    approver_key,
    independence_code,
    uncounted_code,
    approver_label,
    coverage_of,
    evidence_hash,
    fingerprint,
    heading_at,
    load_excluded,
    mark_keys,
    manuscript_marks,
    mask_comments,
    refs_in,
    independence_problem,
    sentence_at,
    source_check_state,
    source_checker_unlisted,
    summary_fingerprint,
    uncounted_approval,
    writer_of,
)
from .propose import load_candidates
from .source import is_cjk, normalize


def run_check():
    """整合の検査。表示も終了もせず、結果を辞書で返す（check と checkpoint が使う）。"""
    bib = parse_bib()
    errors, notes, infos = [], [], []
    _, bad_ledger = read_ledger()  # 読めない行は台帳から飛ばす（judge.read_ledger）。飛ばしたことは INFO で出す
    if bad_ledger:
        nums = "、".join(map(str, bad_ledger))
        infos.append(f"{cfg.JUDGMENTS.as_posix()}: 判定の台帳の読めない行を {len(bad_ledger)} 行飛ばした（{nums}）")
    first = {}  # 書誌の key の最初の出現（重複の NOTE の「先は」に使う）
    for k, num, is_line in bib_occurrences():
        if k not in first:
            first[k] = (num, is_line)
            continue
        fnum, fline = first[k]
        loc = str(num) if is_line else f"{num} 件目"
        ref = f"{fnum} 行" if fline else f"{fnum} 件目"
        notes.append(f"{cfg.BIB.as_posix()}:{loc} {k}: 書誌の key の重複（先は {ref}）")
    marked, done, by_kind = 0, 0, {"human": 0, "model": 0}  # 要ヒューマンチェックの印と確認（§5.3 の 4・5）
    approvers, grades, used = {}, {}, set()
    # 誰が判断したかの内訳（マニフェストの decided_by。§8、C43）。数えたものは判断した者の種類ごと、数えなかったものは理由ごと
    decided = {k: {"counted": {}, "uncounted": {}} for k in ("approvals", "source_checks", "summary_checks")}

    def tally(kind, part, key):
        decided[kind][part][key] = decided[kind][part].get(key, 0) + 1
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
        if hd.get("格") == "Web 写し（保存あり）" and key in bib:
            src = hd.get("抽出")
            copy_text = Path(src).read_text(encoding="utf-8", errors="replace") if src else ""
            wm = re.search(r"^retrieved: (\S+)", copy_text[:2000], re.M)
            got, acc = (wm.group(1) if wm else None), bib[key].get("accessed")
            if got and not acc:
                infos.append(f"{key}: 書誌に参照日が無い（写しの取得日 {got}）")
            elif got and acc != got:
                infos.append(f"{key}: 書誌の参照日 {acc} と写しの取得日 {got} が違う。書誌の参照日を写しの取得日にそろえる")
        if hd.get("抽出") and key in bib:
            for n, text in extraction_diagnosis(key, bib, Path(hd["抽出"])):
                (infos if n == 4 else notes).append(f"{where}: 抽出の診断: {text}")  # 4 は情報、1〜3 は確認待ち
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
            checker, problem = source_check_state(f, b.get("records", {}), f.get("逐語", ""), writer_of(f.get("記入")))
            confirmed = not problem  # 有効な原本での確認（§5.2 の条件1〜5）
            if f.get("原本での確認") and checker:
                if confirmed:
                    tally("source_checks", "counted", approver_key(checker))
                elif source_checker_unlisted(checker):  # 一覧に無い確認者（C44）
                    tally("source_checks", "uncounted", "unlisted")
                elif independence_code(checker, [writer_of(f.get("記入"))]):
                    tally("source_checks", "uncounted", independence_code(checker, [writer_of(f.get("記入"))]))
            reason = d.get("要ヒューマンチェック", "")
            if st == "不一致" and not confirmed:
                errors.append(f"{w}: 逐語が抽出テキストに無い" + (f"（他の文献で一致: {d['他の文献で一致']}）" if d.get("他の文献で一致") else ""))
            if reason:  # 要ヒューマンチェック（§5.3 の 1 と 4）
                marked += 1
                if confirmed:
                    done += 1
                    kind = cfg.APPROVERS.get(checker)
                    if kind in by_kind:
                        by_kind[kind] += 1
                else:
                    notes.append(f"{w}: 要ヒューマンチェック（{reason}）。{problem}（confirm --source か review --html で記録する）")
            # 孫引きの記録があれば、原典の主張でないと記録済み（§6.3）
            if d.get("節の種類") in ("関連研究", "参考文献") and not f.get("孫引き"):
                infos.append(f"{w}: 原典の{d['節の種類']}の節にある文。原典の著者の主張でない可能性")
            excerpts[bid] = f
            states[bid] = (st, confirmed, reason)
            exc_where.append((w, key, f))
            if f.get("要約の確認"):
                name = f["要約の確認"].split()[0]
                if b.get("records", {}).get("要約の確認時の指紋") != summary_fingerprint(f):
                    notes.append(f"{w}: 要約の確認の後に欄が変わった。確認し直す")
                elif independence_problem(name, [writer_of(f.get("記入"))]):  # §2.1 の条件 3。書き手と独立でない model の確認は数えない（C41）
                    notes.append(f"{w}: 要約の確認を数えない（{independence_problem(name, [writer_of(f.get('記入'))])}）")
                    summary_checked["未確認"] = summary_checked.get("未確認", 0) + 1
                    tally("summary_checks", "uncounted", independence_code(name, [writer_of(f.get("記入"))]))
                else:
                    summary_checked[name] = summary_checked.get(name, 0) + 1
                    tally("summary_checks", "counted", approver_key(name))
            else:
                summary_checked["未確認"] = summary_checked.get("未確認", 0) + 1

    # 欄の中の抜き書きへの参照（key#e3、同じ文献の中なら e3）は実在すること。
    # 言っていないことや解釈が原文の別の箇所に依るなら、その箇所を抜き書きにして ID で指す（§16.2 の 4）
    for w, key, f in exc_where:
        for name in ("要約", "言っていないこと"):
            for shown, cands in refs_in(f.get(name, ""), [key]):
                if not any(c in excerpts for c in cands):
                    errors.append(f"{w}: {name}が指す抜き書き '{shown}' が無い")
    if summary_checked:  # 抜き書きが無ければ、後ろの空いた行を出さない
        infos.append("抜き書きの要約の確認: " + " / ".join(f"{k} {v}" for k, v in sorted(summary_checked.items())))
    infos.append(f"要ヒューマンチェック: 印のある抜き書き {marked} 件のうち、確認済 {done}"
                 f"（人 {by_kind['human']}、モデル {by_kind['model']}）、残り {marked - done}（一覧は review --source-checks）")

    # 引用
    if cfg.CIT.exists():
        head, blocks = parse_blocks(cfg.CIT)
        target = Path(head["fields"].get("対象", ""))
        text = mask_comments(target.read_text(encoding="utf-8")) if target.is_file() else ""
        if not text:
            errors.append(f"{cfg.CIT.as_posix()}: 対象の原稿 '{target}' が読めない")
        marks = manuscript_marks(text)
        ids_in_text, keys_in_text = {}, {}
        for cid, off, mkey in marks:
            ids_in_text.setdefault(cid, []).append(off)
            if mkey:
                keys_in_text[cid] = {k.strip() for k in mkey.split(",")}
        block_ids = set()
        counts = {"承認済": 0, "要再確認": 0, "未承認": 0, "指示": 0}
        first_line = {}  # 同じ ID の最初のブロックの行（重複を見つけたとき、先の行を書く）
        for b in blocks:
            cid = b["id"]
            w = f"{cfg.CIT.as_posix()}:{b['line']} {cid}"
            block_ids.add(cid)
            f = b["fields"]
            again = cid in first_line  # 二つ目からのブロック。検査は続けるが、集計と承認者の数には入れない（ID ごとに一度）
            if again:  # 確認待ち。書き込みは両方のブロックを避ける（approve.py の _citation_now）
                notes.append(f"{w}: 引用のブロックの ID の重複（先は {first_line[cid]} 行）")
            else:
                first_line[cid] = b["line"]
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
                if not again:
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
                    continue
                sec = excerpts[r].get("孫引き", "")
                if sec:  # 原典が他の文献の主張を紹介している逐語を、主張として引いている（§6.3）
                    keyed = [t.strip() for t in sec.split("、") if t.strip() in bib]
                    tail = f"。元の文献は書誌にある（{'、'.join(keyed)}）。直接引けるか確かめる" if keyed else ""
                    infos.append(f"{w}: 根拠 {r} は孫引き（{sec}）。本文で元の文献に帰属させているか確かめる{tail}")
            ref_keys = list(dict.fromkeys(r.split("#")[0] for r in refs))
            for name in ("理由", "解釈"):
                for shown, cands in refs_in(f.get(name, ""), ref_keys):
                    if not any(c in excerpts for c in cands):
                        errors.append(f"{w}: {name}が指す抜き書き '{shown}' が無い")
            for name in ("理由", "原文との差", "記入"):
                if not f.get(name):
                    errors.append(f"{w}: 欄 '{name}' が空")
            # 人の読み：原文の語でない読みを、人が本文へ入れるときの欄。AI は書けず、この引用の抜き書きを根拠として ID で指す（§16.2 の 7）
            if f.get("人の読み"):
                by = f.get("人の読みの記入", "").split()
                if not by:
                    errors.append(f"{w}: 人の読みには 人の読みの記入（書いた人と日付）が要る")
                elif cfg.APPROVERS and cfg.APPROVERS.get(by[0]) != "human":
                    errors.append(f"{w}: 人の読みの記入者 '{by[0]}' は人（approvers の human）でない")
                anchors = refs_in(f["人の読み"], ref_keys)
                if not anchors:
                    errors.append(f"{w}: 人の読みが抜き書きの ID（e6 や key#e6）を指していない。根拠の抜き書きを ID で示す")
                for shown, cands in anchors:
                    if not any(c in excerpts for c in cands):
                        errors.append(f"{w}: 人の読みが指す抜き書き '{shown}' が無い")
                    elif not any(c in refs for c in cands):
                        errors.append(f"{w}: 人の読みが指す抜き書き '{shown}' がこの引用の抜き書きに無い（根拠に足す）")
            elif f.get("人の読みの記入"):
                errors.append(f"{w}: 人の読みの記入だけがある（人の読みを書く）")
            if f.get("原文との差") and f["原文との差"] not in DIFFS:
                errors.append(f"{w}: 原文との差は {sorted(DIFFS)} のどれか")
            # 本文の引用符の中の文字列は、指している抜き書きの逐語に含まれていること
            # 引用符の中でも原文の逐語でない句（コマンドの言い方、UI の文字列の一例等）は、人が「引用でない句」に挙げて外す
            not_quotes = [x.strip() for x in re.sub(r"（[^（）]*）|\([^()]*\)$", "", f.get("引用でない句", "")).split(cfg.NOT_QUOTE_SEP)
                          if x.strip()]
            for q in [m.group(1) for rx in cfg.QUOTE_RES for m in rx.finditer(sent)]:
                if q in not_quotes:
                    infos.append(f"{w}: 「{q}」は引用でない句として外した")
                    continue
                qcjk = any(is_cjk(c) for c in q)
                pool = [excerpts[r]["逐語"] for r in refs if r in excerpts]
                same = [p for p in pool if any(is_cjk(c) for c in p) == qcjk]
                if same and not any(normalize(q, "alnum")[0] in normalize(p, "alnum")[0] for p in same):
                    errors.append(f"{w}: 本文の引用「{q[:30]}…」が抜き書きの逐語に無い")
            state, extra = approval_state(f, b.get("records", {}), fp, evidence_hash(refs, excerpts, f.get("人の読み", "")))
            uncounted = uncounted_approval(state, extra, f, excerpts)  # §2.1 の条件 3 と §3.2。書き手と独立でない model と model の承認は確認待ち（C18、C41）
            if uncounted:
                notes.append(f"{w}: 承認を数えない（{uncounted}）")
                state = "未承認"
                if not again:
                    tally("approvals", "uncounted", uncounted_code(extra, f, excerpts))
            if not again:
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
                if not again:
                    approvers[extra] = approvers.get(extra, 0) + 1
                    tally("approvals", "counted", approver_key(extra))
                if cfg.APPROVERS and extra not in cfg.APPROVERS:
                    notes.append(f"{w}: 承認者 '{extra}' は承認者の一覧に無い")
            for r in refs:
                _, ok, reason = states.get(r, ("", False, ""))
                if reason and not ok:
                    notes.append(f"{w}: 根拠 {r} は要ヒューマンチェック（{reason}）で、原本での確認が無い")
            if f.get("原文との差") == "外挿":
                notes.append(f"{w}: 外挿。本文に限定を付けるか、自分の主張として書き直す")
        for cid in ids_in_text:
            if cid not in block_ids:
                errors.append(f"{target}: 〔{cid}〕に対応するブロックが無い")
        cov_marked, cov_unmarked, parens = coverage_of(text, bib, mark_keys(blocks))
        coverage = {"spans": cov_marked + len(cov_unmarked), "in_marked_sentences": cov_marked, "unmarked": len(cov_unmarked), "parens": parens}
        n_ex = len(load_excluded())
        coverage["excluded"] = n_ex
        if coverage["spans"]:
            infos.append(f"網羅: 原稿の出典らしきもの {coverage['spans'] + n_ex}（括弧 {parens}）のうち、印のあるもの {cov_marked}、"
                         f"印の無いもの {len(cov_unmarked)}" + (f"、引用でないと判断したもの {n_ex}" if n_ex else "")
                         + "（印の無いものはこのツールが確かめていない。一覧は coverage、候補づくりは propose）")
        pend = sum(1 for c in load_candidates()["items"].values() if c.get("status") == "pending")
        if pend:
            infos.append(f"候補: 人の判断を待つもの {pend} 件（review --html）")
        returned = counts.get("差し戻し", 0) + counts.get("差し戻し後に直された", 0)
        by_label = {}  # model の承認も数えるときは、承認済を承認者の種類ごとに分けて出す（C42）
        for n, v in approvers.items():
            by_label[approver_label(n)] = by_label.get(approver_label(n), 0) + v
        kinds = ("（" + "、".join(f"{k} {v}" for k, v in sorted(by_label.items(), key=lambda kv: (kv[0] != "人", kv[0]))) + "）"
                 if cfg.COUNT_MODEL and by_label and None not in by_label else "")
        infos.append(f"引用: 主張 承認済 {counts['承認済']}{kinds} / 要再確認 {counts['要再確認']} / 未承認 {counts['未承認']}"
                     + (f" / 差し戻し {returned}" if returned else "") + f"、指示 {counts['指示']}")
    else:  # 引用のファイルが無いと、引用の検査は走らない。確認待ちにして、check --strict と checkpoint を止める（黙って通さない）
        counts, target, coverage = {}, None, {}
        notes.append(f"{cfg.CIT.as_posix()}: 引用のファイルが無い（設定の citations か --citations のパスを確かめる）")

    summary = {}
    for st, _, _ in states.values():
        summary[st] = summary.get(st, 0) + 1
    return {"errors": errors, "notes": notes, "infos": infos, "excerpt_states": summary, "excerpts": len(states),
            "source_checks": {"marked": marked, "done": done, "by_kind": by_kind, "pending": marked - done},
            "citations": counts, "approvers": approvers, "coverage": coverage, "decided_by": decided,
            "approver_kinds": {k: sum(v for n, v in approvers.items() if cfg.APPROVERS.get(n, "不明") == k)
                               for k in sorted({cfg.APPROVERS.get(n, "不明") for n in approvers})}, "summary_checks": summary_checked, "grades": grades, "texts": sorted(used),
            "manuscript": str(target) if target else None}


def cmd_coverage(args):
    """印の無い文にある出典らしき括弧を、行の順に並べる（このツールが確かめていない引用の一覧）。"""
    head, blocks = parse_blocks(cfg.CIT)
    target = Path(head["fields"].get("対象", ""))
    marked, unmarked, parens = coverage_of(mask_comments(target.read_text(encoding="utf-8")), parse_bib(), mark_keys(blocks))
    for c in unmarked:
        span = c["paren"] if c["part"] is None else f"{c['source']}（括弧 {c['paren']} の出典 {c['part'] + 1}/{c['nparts']}）"
        print(f"{target.as_posix()}:{c['line']}  {span}  （{c['section']}）")
    print(f"--- 出典らしきもの {marked + len(unmarked)}（括弧 {parens}）、印のある文 {marked}、印の無い文 {len(unmarked)}")


def cmd_check(args):
    from .review import review_data  # review が check を import するので、循環を避けてここで import する（設計 §7.3）
    r = run_check()
    errors, notes, infos, summary = r["errors"], r["notes"], r["infos"], r["excerpt_states"]
    for e in errors:
        print("ERROR", e)
    for n in notes:
        print("NOTE ", n)
    for n in infos:
        print("INFO ", n)
    if load_ledger():  # 台帳が空なら何も出さない。数えるのは classify --list と同じ（judge.count_judgments）
        data = review_data(None, None, include_done=True, checked=r)  # classify --list と同じ単位。run_check は走らせ直さない
        js = count_judgments(units_from_data(data))
        print("INFO ", f"分類器: 判定 {len(js['rows'])} 件のうち印 {js['flagged']} 件（今の記録との比較。一覧は classify --list）。"
                       f"古い判定 {js['stale']} 件は数えていない")
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
    summary, diag = {}, []
    for k in keys:
        g, txt = grade_of(k, bib)
        summary.setdefault(g, []).append(k)
        if txt:
            diag += [f"{k}: {text}" for _, text in extraction_diagnosis(k, bib, txt)]
    for g, ks in sorted(summary.items(), key=lambda x: -len(x[1])):
        print(f"{g}: {len(ks)}  {', '.join(ks)}")
    for line in diag:
        print(line)
    total = len(keys)
    ok = len(summary.get("PDF所持（抽出あり）", [])) + len(summary.get("Web 写し（保存あり）", []))
    print(f"--- {total} 件のうち、機械で照合できるもの {ok} 件（{round(100 * ok / max(1, total))}%）")
