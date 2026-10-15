# -*- coding: utf-8 -*-
"""コマンドラインの入口。"""
from pathlib import Path
import argparse
import sys
from . import config as cfg
from .apply import cmd_apply
from .approve import cmd_approve, cmd_confirm
from .check import cmd_check, cmd_coverage, cmd_grade
from .checkpoint import cmd_checkpoint, cmd_precommit, cmd_strip
from .config import CONFIG, load_config
from .derive import cmd_derive
from .judge import cmd_classify
from .fetch import cmd_extract, cmd_snapshot
from .propose import cmd_propose, cmd_sentences
from .review import cmd_review


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG), help="設定ファイル（既定は bridge/bridge.toml）")
    ap.add_argument("--citations", help="引用のファイル（既定は設定の値。原稿が複数あるとき、写しで試すとき）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("derive").set_defaults(func=cmd_derive)
    c = sub.add_parser("check")
    c.add_argument("--strict", action="store_true")
    c.set_defaults(func=cmd_check)
    g = sub.add_parser("grade")
    g.add_argument("--keys-from")
    g.set_defaults(func=cmd_grade)
    a = sub.add_parser("approve")
    a.add_argument("cid")
    a.add_argument("--by", required=True)
    a.add_argument("--note", help="判断の中身（承認の理由、差し戻しの理由）")
    a.add_argument("--send-back", action="store_true", help="承認せず、書き手へ差し戻す（--note が要る）")
    a.set_defaults(func=cmd_approve)
    cf = sub.add_parser("confirm")
    cf.add_argument("eid", help="key#eN")
    cf.add_argument("--by", required=True)
    cf.add_argument("--note")
    cf.set_defaults(func=cmd_confirm)
    rv = sub.add_parser("review")
    rv.add_argument("cids", nargs="*", help="引用の ID。省くと確認待ちのものすべて")
    rv.add_argument("--images", help="近似一致・OCR の根拠の頁を画像にして置くフォルダ")
    rv.add_argument("-o", "--out", help="書き出すファイル（省くと標準出力）")
    rv.add_argument("--json", action="store_true", help="外の表示へ渡す JSON で出す")
    rv.add_argument("--all", action="store_true", help="承認済と指示の引用も含める")
    rv.add_argument("--html", action="store_true", help="承認の HTML（単体で開ける一枚）を -o に書く")
    ap_ = sub.add_parser("apply")
    ap_.add_argument("file", nargs="?", help="承認の HTML が保存した判断ファイル（JSON）")
    ap_.add_argument("--latest", action="store_true", help="判断ファイルを渡さず、フォルダの中でこの原稿の最新のものを使う")
    ap_.add_argument("--from", dest="source", help="--latest で探すフォルダ（既定はホームの Downloads）")
    ap_.add_argument("--allow-older", action="store_true", help="最後に適用したものより古い判断ファイルを、意図して適用する")
    ap_.add_argument("--dry-run", action="store_true", help="書かずに、書けるかだけを見る")
    ap_.set_defaults(func=cmd_apply)
    rv.set_defaults(func=cmd_review)
    x = sub.add_parser("extract")
    x.add_argument("keys", nargs="*")
    x.add_argument("--force", action="store_true")
    x.set_defaults(func=cmd_extract)
    w = sub.add_parser("snapshot")
    w.add_argument("key")
    w.add_argument("url", nargs="?", help="既定は書誌の行の URL")
    w.add_argument("--rebuild", action="store_true", help="保存した生の HTML から本文を作り直す（取り直さない）")
    w.set_defaults(func=cmd_snapshot)
    cv = sub.add_parser("coverage")
    cv.set_defaults(func=cmd_coverage)
    pr = sub.add_parser("propose")
    pr.add_argument("items", nargs="*", help="作業票を作る item（省くと、絞り込みに当たる印の無い出典）")
    pr.add_argument("--section", help="見出しにこの文字列を含む節だけ")
    pr.add_argument("--lines", help="原稿の行の範囲（例 80-120）")
    pr.add_argument("--limit", type=int, default=15, help="作業票の件数の上限（既定 15。一回の承認が30分ほどに収まる数）")
    pr.add_argument("--top", type=int, default=6, help="key ごとに載せる原典の文と既存の抜き書きの数")
    pr.add_argument("--add-key", action="append", metavar="ITEM=KEY", help="key の候補に足す（推定が外れたとき）")
    pr.add_argument("--load", metavar="DRAFTS", help="書き手の下書き（JSON）を検査して候補にする")
    pr.set_defaults(func=cmd_propose)
    se = sub.add_parser("sentences")
    se.add_argument("key")
    se.add_argument("--grep", action="append", help="この語を含む文だけ（複数なら全部を含む文）")
    se.add_argument("--range", help="文の番号の範囲（例 40-50）")
    se.set_defaults(func=cmd_sentences)
    cp = sub.add_parser("checkpoint")
    cp.add_argument("--label", default="")
    cp.set_defaults(func=cmd_checkpoint)
    cl = sub.add_parser("classify")
    cl.add_argument("--send", action="store_true", help="外部の分類器へ送る（既定は、送る内容の見積りだけ）")
    cl.add_argument("--list", action="store_true", help="台帳の判定を、現在の記録と突き合わせて出す（何も送らない）")
    cl.add_argument("--all", action="store_true", help="--list で、印の無いものも出す")
    cl.add_argument("--cids", nargs="*", help="この引用だけ")
    cl.add_argument("--limit", type=int, default=0, help="送る要求の回数の上限（既定は無制限）")
    cl.set_defaults(func=cmd_classify)
    pc = sub.add_parser("precommit")
    pc.set_defaults(func=cmd_precommit)
    st = sub.add_parser("strip")
    st.add_argument("src")
    st.add_argument("out")
    st.set_defaults(func=cmd_strip)
    args = ap.parse_args()
    cfg.CONFIG_USED = Path(args.config)
    load_config(cfg.CONFIG_USED)
    if args.citations:
        cfg.CIT = Path(args.citations)
    args.func(args)


if __name__ == "__main__":
    main()
