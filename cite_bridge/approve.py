# -*- coding: utf-8 -*-
"""承認・差し戻し・要約の確認・指摘の書き込み（approve・confirm）。"""
from pathlib import Path
import datetime
import re
import sys
from . import config as cfg
from .bib import parse_bib
from .blocks import parse_blocks
from .config import RETURNED, out_name
from .derive import rederive_files
from .manuscript import (
    approval_state,
    model_approval_problem,
    evidence_hash,
    fingerprint,
    manuscript_marks,
    mask_comments,
    self_check_problem,
    sentence_at,
    summary_fingerprint,
    uncounted_approval,
    verbatim_fingerprint,
    writer_of,
)


def load_excerpt_fields():
    """{key#eN: 書く欄}。derive をせずに読む（承認と review が使う）。"""
    res = {}
    for path in sorted(cfg.EXC_DIR.glob("*.md")):
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
    """(今の状態, 失敗の理由)。今の状態は (本文の文, 本文の指紋, 根拠の指紋, ブロックの欄)。失敗のときは今の状態が None で、理由の文が入る。"""
    head, blocks = parse_blocks(cfg.CIT)
    target = Path(head["fields"].get("対象", ""))
    text = mask_comments(target.read_text(encoding="utf-8"))
    offs = [off for c, off, _ in manuscript_marks(text) if c == cid]
    if len(offs) != 1:
        return None, f"原稿に〔{cid}〕がちょうど一つ無い（{len(offs)} 箇所）"
    same = [b for b in blocks if b["id"] == cid]
    if not same:
        return None, f"{cfg.CIT.as_posix()} に {cid} のブロックが無い"
    if len(same) > 1:  # 同じ ID の二つ目以降は、どの書き込みも避ける（どちらに入れるかを道具が決めない）
        return None, f"{cfg.CIT.as_posix()} に {cid} のブロックがちょうど一つ無い（{len(same)} 個）"
    block = same[0]
    sent = sentence_at(text, offs[0])
    refs = [r.strip() for r in block["fields"].get("抜き書き", "").split(",") if r.strip()]
    now = (sent, fingerprint(sent), evidence_hash(refs, load_excerpt_fields(), block["fields"].get("人の読み", "")), block["fields"])
    return now, None


APPROVAL_LINE_RE = r"^@?(承認|差し戻し|approval|approved_|returned_)"


def approver_problem(by):
    """承認者の一覧があり、by がそこに無ければ理由の文を返す。一覧は事故（打ち間違い、別名）を防ぐもので、悪意は防がない。"""
    if cfg.APPROVERS and by not in cfg.APPROVERS:
        return f"'{by}' は承認者の一覧（設定の approvers）に無い。一覧: {', '.join(f'{k}（{v}）' for k, v in cfg.APPROVERS.items())}"
    return None


def default_approver():
    """コマンドの例に出す名前。一覧の最初の人、一覧が無ければ「人」。"""
    return next((k for k, v in cfg.APPROVERS.items() if v == "human"), "人")


def write_approval(cid, by, note=None, send_back=False, seen=None, dry=False):
    """承認か差し戻しを書く。seen=(本文の指紋, 根拠の指紋) を渡すと、今の指紋と合うときだけ書く。

    返り値は (書いたか, 文言)。承認は人の指示があるときだけ行う（AI が自分の書いた引用を承認しない）。
    """
    if approver_problem(by):
        return False, f"{cid}: " + approver_problem(by)
    now, why = _citation_now(cid)
    if now is None:
        return False, f"{cid}: {why}"
    sent, fp, ev, f = now
    if seen and tuple(seen) != (fp, ev):
        return False, f"{cid}: 判断した後に{'本文' if seen[0] != fp else '根拠'}が変わった。書かなかった（review を作り直して見直す）"
    if f.get("種類") != "主張":
        return False, f"{cid}: 主張の引用ではない"
    if self_check_problem(by, writer_of(f.get("記入"))):
        return False, f"{cid}: " + self_check_problem(by, writer_of(f.get("記入")))
    # 同じ者・同じ理由で、指紋も変わらず承認済みなら書き直さない（承認の HTML はブラウザに残った前の判断も判断ファイルに含める）
    rec = next((b.get("records", {}) for b in parse_blocks(cfg.CIT)[1] if b["id"] == cid), {})
    if (not send_back and approval_state(f, rec, fp, ev)[0] == "承認済" and (f.get("承認") or "").split()[:1] == [by]
            and (note or "") == f.get("承認の理由", "")):
        return True, f"{cid}: 承認は記録済み（同じ判断）"
    if not send_back and model_approval_problem(by):  # 今数えている人の承認を、数えない承認で消さない（C35）
        state, head = approval_state(f, rec, fp, ev)
        if state == "承認済" and not uncounted_approval(state, head, f):
            return False, f"{cid}: '{head}' の承認が今と合うので、model '{by}' の承認で書き換えない"
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
        one_line = re.sub(r"\s+", " ", sent)  # 記録は一行（paragraph = blank の文は改行を含む。C35）
        new += [f"@{out_name('承認時の指紋')}: {fp}", f"@{out_name('承認時の根拠')}: {ev}",
                f"@{out_name('承認時の本文')}: {one_line}"]
        msg = f"承認を記録: {cid} {by} {today} 指紋={fp} 根拠={ev}"
    if dry:
        return True, f"{cid}: {'差し戻し' if send_back else '承認'}"
    _replace_block_lines(cfg.CIT, cid, APPROVAL_LINE_RE, new)
    return True, msg


def rederive_later(path, pending=None):
    """書いた抜き書きの導く欄を並べ直す。pending（apply が集める集合）があれば、apply が書き終えてから一度だけ導き直す。無ければ、その場で導き直す（approve・confirm の単独の書き込み）。"""
    if pending is None:
        rederive_files({path})
    else:
        pending.add(path)


def write_confirm(eid, by, note=None, seen=None, dry=False, pending=None):
    """抜き書きの要約・言っていないこと・強さを確かめた記録を書く。seen（要約の指紋）が今と合うときだけ書く。"""
    if "#" not in eid:
        return False, "抜き書きは key#eN で指す"
    if approver_problem(by):
        return False, f"{eid}: " + approver_problem(by)
    key, bid = eid.split("#", 1)
    for path in sorted(cfg.EXC_DIR.glob("*.md")):
        head, blocks = parse_blocks(path)
        if head["title"] != key:
            continue
        same = [x for x in blocks if x["id"] == bid]
        if len(same) > 1:  # 同じ ID の二つ目以降の記録を消さないよう、どの書き込みも避ける（C15 の引用のブロックと同じ、C35）
            return False, f"{eid}: {path.as_posix()} に {bid} のブロックがちょうど一つ無い（{len(same)} 個）"
        b = same[0] if same else None
        if b is None:
            break
        if self_check_problem(by, writer_of(b["fields"].get("記入"))):
            return False, f"{eid}: " + self_check_problem(by, writer_of(b["fields"].get("記入")))
        sfp = summary_fingerprint(b["fields"])
        if seen and seen != sfp:
            return False, f"{eid}: 確かめた後に要約か逐語が変わった。書かなかった"
        if dry:
            return True, f"{eid}: 要約の確認"
        today = datetime.date.today().isoformat()
        new = [f"{out_name('要約の確認')}: {by} {today}" + (f"（{note}）" if note else ""),
               f"@{out_name('要約の確認時の指紋')}: {sfp}"]
        _replace_block_lines(path, bid, r"^@?(要約の確認|summary_check)", new)
        rederive_later(path, pending)  # 導く欄をブロックの末尾へ並べ直す
        return True, f"要約の確認を記録: {eid} {by} {today}"
    return False, f"抜き書き '{eid}' が無い"


def write_source_check(eid, by, result="一致", page=None, note=None, seen=None, dry=False, pending=None):
    """原本での確認を記録する（§5.2、§5.4）。結果は 一致 か 違う（違う はメモが要る）。seen（逐語の指紋）が今と合うときだけ書く。"""
    if "#" not in eid:
        return False, "抜き書きは key#eN で指す"
    if approver_problem(by):
        return False, f"{eid}: " + approver_problem(by)
    if result not in ("一致", "違う"):
        return False, f"{eid}: 結果は 一致 か 違う"
    if result == "違う" and not note:
        return False, f"{eid}: 違う のときはメモに原本の字を書く（--note）"
    key, bid = eid.split("#", 1)
    for path in sorted(cfg.EXC_DIR.glob("*.md")):
        head, blocks = parse_blocks(path)
        if head["title"] != key:
            continue
        same = [x for x in blocks if x["id"] == bid]
        if len(same) > 1:  # 同じ ID の二つ目以降の記録を消さないよう、どの書き込みも避ける（C15 の引用のブロックと同じ、C35）
            return False, f"{eid}: {path.as_posix()} に {bid} のブロックがちょうど一つ無い（{len(same)} 個）"
        b = same[0] if same else None
        if b is None:
            break
        if self_check_problem(by, writer_of(b["fields"].get("記入"))):
            return False, f"{eid}: " + self_check_problem(by, writer_of(b["fields"].get("記入")))
        vfp = verbatim_fingerprint(b["fields"].get("逐語", ""))
        if seen and seen != vfp:
            return False, f"{eid}: 確かめた後に逐語が変わった。書かなかった"
        if dry:
            return True, f"{eid}: 原本での確認"
        today = datetime.date.today().isoformat()
        old = b["fields"].get("原本での確認", "")
        if not note and old:  # 0.2.0 までの古い記録は有効でないので、書き換えず文をメモに残す（§5.2）
            note = f"前の記録: {old}"
        value = f"{by} {today} {result}" + (f" {page}" if page else "") + (f"（{note}）" if note else "")
        new = [f"{out_name('原本での確認')}: {value}", f"@{out_name('原本での確認時の指紋')}: {vfp}"]
        _replace_block_lines(path, bid, r"^@?(原本での確認|source_check|原本での確認時の指紋|source_check_fingerprint):", new)
        rederive_later(path, pending)  # 導く欄をブロックの末尾へ並べ直す
        return True, f"原本での確認を記録: {eid} {by} {today} {result}"
    return False, f"抜き書き '{eid}' が無い"


def write_remark(cid, by, remark, dry=False):
    """引用の「指摘」の欄に足す。承認の判断とは別の、原稿への気づきで、指紋には入らない。同じ文は二度足さない。
    原稿に印が無い ID や、ブロックの無い ID は足さない（apply は SKIP にする）。"""
    now, why = _citation_now(cid)
    if now is None:
        return False, f"{cid}: {why}"
    head, blocks = parse_blocks(cfg.CIT)
    b = next((x for x in blocks if x["id"] == cid), None)
    remark = re.sub(r"\s+", " ", remark).strip()
    have = b["fields"].get("指摘", "")
    if remark in have:
        return True, f"{cid}: 指摘は記録済み"
    if dry:
        return True, f"{cid}: 指摘"
    entry = f"{remark}（{by} {datetime.date.today().isoformat()}）"
    _replace_block_lines(cfg.CIT, cid, r"^(指摘|remarks):", [f"{out_name('指摘')}: " + (have + " ｜ " + entry if have else entry)])
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
    """抜き書きの要約・言っていないこと・強さを、人（または書き手と別の者）が原文と照らして確かめたことを記録する。
    --source は、要ヒューマンチェックの抜き書きを原本（頁の画像・原本の PDF・紙）で確かめた記録（§5.2）。"""
    if args.source:
        ok, msg = write_source_check(args.eid, args.by, args.result, args.page, args.note)
    else:
        ok, msg = write_confirm(args.eid, args.by, args.note)
    if not ok:
        sys.exit(msg)
    print(msg)
