# -*- coding: utf-8 -*-
"""抜き書きと引用の md（## ブロックと欄）の読み書き。"""
from .config import FIELD_ALIASES, FIELD_NAMES_EN, FIELD_RE, RECORD_FIELDS, VALUE_ALIASES, out_name


# ---------------------------------------------------------------- ブロックの読み書き

def parse_blocks(path):
    """# 見出しの部分（head）と、## ID ごとのブロックを読む。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    head = {"title": None, "fields": {}, "derived": {}, "line": 1}
    blocks = []
    cur = head
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            cur = {"id": ln[3:].strip(), "fields": {}, "derived": {}, "line": i + 1}
            blocks.append(cur)
            continue
        if ln.startswith("# "):
            head["title"] = ln[2:].strip()
            continue
        m = FIELD_RE.match(ln)
        if m:
            name = m.group(2).strip()
            name = FIELD_ALIASES.get(name, name)
            value = m.group(3).strip()
            value = VALUE_ALIASES.get(name, {}).get(value, value)
            if m.group(1) and name in RECORD_FIELDS:
                cur.setdefault("records", {})[name] = value
            else:
                (cur["derived"] if m.group(1) else cur["fields"])[name] = value
    return head, blocks


def rewrite_derived(path, head_derived, block_derived):
    """導く欄の @ 行を除いて、各区切りの末尾に新しい @ 行を置く。記録の @ 行（RECORD_FIELDS）は残す。"""
    record_names = RECORD_FIELDS | {FIELD_NAMES_EN.get(n, n) for n in RECORD_FIELDS}
    lines = path.read_text(encoding="utf-8").splitlines()
    segs, cur = [], []
    for ln in lines:
        if ln.startswith("## ") and cur:
            segs.append(cur)
            cur = []
        cur.append(ln)
    segs.append(cur)
    out = []
    for si, seg in enumerate(segs):
        body = [ln for ln in seg if not ln.startswith("@") or ln[1:].split(":")[0].strip() in record_names]
        while body and not body[-1].strip():
            body.pop()
        if si == 0:
            derived = head_derived
        else:
            bid = seg[0][3:].strip()
            derived = block_derived.get(bid, {})
        out.extend(body)
        out.extend(f"@{out_name(k)}: {v}" for k, v in derived.items())
        out.append("")
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")
