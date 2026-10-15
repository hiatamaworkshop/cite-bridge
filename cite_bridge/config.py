# -*- coding: utf-8 -*-
"""設定（bridge.toml）の読み込みと、設定で決まる状態、欄名・値の定数。他のモジュールは `cfg.X` で読む。"""
from pathlib import Path
import re
import sys


TOOL_NAME = "cite-bridge"
TOOL_VERSION = "0.1.0"  # 形式（欄・判断ファイル・マニフェスト）を変えたら上げる。マニフェストに記録する

# 設定（bridge.toml）から main で埋める
CONFIG = Path("bridge/bridge.toml")
CONFIG_USED = CONFIG
BIB = EXC_DIR = CIT = TXT_DIR = PDF_DIR = WEB_DIR = CKPT_DIR = None
BIB_FORMAT = "keyline"
PDF_RE = WEB_RE = None
APPLIED = None      # 適用した判断ファイルの記録（bridge.applied）
CAND_DIR = None     # 候補の作業票・下書き・候補（bridge.candidates）
EXCLUDED = None     # 「引用でない」と判断した括弧の記録（bridge.excluded）。coverage が数えない
MARK_FORMAT = "〔{id}〕"
WATCH_EXTRA = []    # pre-commit が監視する、設定が指す以外のパス（hook.watch）
APPROVERS = {}      # 承認者の一覧 {名前: human / model}。空なら名前を問わない（approvers）
# 出典らしき括弧（著者と年など）。印の無い文にあるものを「印の無い出典」として数える（coverage.pattern で替える）
COVER_RE = re.compile(r"[（(][^（）()\n]*?(?<!\d)(?:19|20)\d{2}[a-z]?(?![\d年月日-])[^（）()\n]*[）)]")


def load_config(path):
    import tomllib
    global BIB, EXC_DIR, CIT, TXT_DIR, PDF_DIR, WEB_DIR, BIB_FORMAT, PDF_RE, WEB_RE
    if not path.exists():
        sys.exit(f"設定ファイル {path} が無い（--config で指定する。書き方は SKILL.md）")
    c = tomllib.loads(path.read_text(encoding="utf-8"))
    b, s, r = c.get("bibliography", {}), c.get("sources", {}), c.get("bridge", {})
    BIB = Path(b["path"])
    BIB_FORMAT = b.get("format", "keyline")
    global FILES_FIELD
    FILES_FIELD = b.get("files_field", FILES_FIELD)
    PDF_RE = re.compile(b["pdf_pattern"]) if b.get("pdf_pattern") else None
    WEB_RE = re.compile(b["web_pattern"]) if b.get("web_pattern") else None
    PDF_DIR = Path(s.get("pdf_dir", "references"))
    TXT_DIR = Path(s.get("text_dir", PDF_DIR / "_txt"))
    WEB_DIR = Path(s.get("web_dir", PDF_DIR / "_web"))
    EXC_DIR = Path(r.get("excerpts", "bridge/excerpts"))
    CIT = Path(r.get("citations", "bridge/citations.md"))
    global MARK_RE, QUOTE_RES, NOT_QUOTE_SEP, OUTPUT_LANG, KIND_WORDS, KIND_WORDS_MAP
    m = c.get("manuscript", {})
    if m.get("mark_pattern"):
        MARK_RE = re.compile(m["mark_pattern"])
    if m.get("quote_patterns"):
        QUOTE_RES = [re.compile(x) for x in m["quote_patterns"]]
    NOT_QUOTE_SEP = m.get("not_quote_separator", NOT_QUOTE_SEP)
    global SENT_END_RE, PARAGRAPH, CKPT_DIR
    if m.get("sentence_end"):
        SENT_END_RE = re.compile(m["sentence_end"])
    PARAGRAPH = m.get("paragraph", PARAGRAPH)
    CKPT_DIR = Path(r.get("checkpoints", "bridge/checkpoints"))
    global APPLIED, APPROVERS, COVER_RE, CAND_DIR, EXCLUDED, MARK_FORMAT
    APPLIED = Path(r.get("applied", CIT.parent / "applied.json"))
    CAND_DIR = Path(r.get("candidates", CIT.parent / "candidates"))
    EXCLUDED = Path(r.get("excluded", CIT.parent / "excluded.json"))
    # 候補を受け入れたときに原稿へ置く印の形。印の正規表現を替えたときは、こちらも設定しないと印を書けない
    MARK_FORMAT = m.get("mark_format", None if m.get("mark_pattern") else "〔{id}〕")
    APPROVERS = {str(k): str(v) for k, v in c.get("approvers", {}).items()}
    bad = {k: v for k, v in APPROVERS.items() if v not in ("human", "model")}
    if bad:
        sys.exit(f"approvers の種類は human か model（{bad}）")
    if c.get("coverage", {}).get("pattern"):
        COVER_RE = re.compile(c["coverage"]["pattern"])
    OUTPUT_LANG = c.get("output", {}).get("language", OUTPUT_LANG)
    global WATCH_EXTRA
    WATCH_EXTRA = [Path(x) for x in c.get("hook", {}).get("watch", [])]
    # 節の種類の語と、抽出が読めるかを見る頻出語は、既定（英語と日本語）に足せる
    extra = c.get("section_kinds", {})
    KIND_WORDS = [(k, ws + [w.lower() for w in extra.get(k, [])]) for k, ws in KIND_WORDS]
    KIND_WORDS_MAP = dict(KIND_WORDS)
    COMMON_EN.update(w.lower() for w in c.get("detect", {}).get("common_words", []))

STRENGTHS = {"観察", "示唆", "主張", "一般化", "条件付き"}
DIFFS = {"一致", "言い換え", "限定つき一般化", "外挿"}
KINDS = {"指示", "主張"}
EXC_REQUIRED = ["逐語", "強さ", "要約", "言っていないこと", "記入"]

# 欄名と値は日本語を正とし、英語の別名も受ける。導く欄を書く言語は設定の output.language で選ぶ
FIELD_ALIASES = {
    "verbatim": "逐語", "strength": "強さ", "summary": "要約", "not_said": "言っていないこと",
    "written_by": "記入", "source_check": "原本での確認", "kind": "種類", "excerpts": "抜き書き",
    "source": "文献", "reason": "理由", "interpretation": "解釈", "diff": "原文との差", "approval": "承認",
    "human_reading": "人の読み", "human_reading_by": "人の読みの記入",
    "not_quotes": "引用でない句", "target": "対象",
    "grade": "格", "text": "抽出", "match": "照合", "location": "所在", "section_kind": "節の種類",
    "before": "前", "sentence": "含む文", "after": "後", "also_found_in": "他の文献で一致",
    "approved_fingerprint": "承認時の指紋", "approved_text": "承認時の本文",
    "approval_note": "承認の理由", "approved_evidence": "承認時の根拠",
    "returned_reason": "差し戻しの理由", "returned_fingerprint": "差し戻し時の指紋", "returned_evidence": "差し戻し時の根拠",
    "summary_check": "要約の確認", "summary_check_fingerprint": "要約の確認時の指紋", "remarks": "指摘",
}
# @ 行のうち、導く欄ではなく道具が書く記録（derive は消さず、導き直しの比較にも入れない）
RECORD_FIELDS = {"承認時の指紋", "承認時の本文", "承認時の根拠", "差し戻し時の指紋", "差し戻し時の根拠", "要約の確認時の指紋"}
FIELD_NAMES_EN = {v: k for k, v in FIELD_ALIASES.items()}
VALUE_ALIASES = {
    "強さ": {"observation": "観察", "suggestion": "示唆", "claim": "主張", "generalization": "一般化", "conditional": "条件付き"},
    "原文との差": {"identical": "一致", "paraphrase": "言い換え", "qualified_generalization": "限定つき一般化",
               "extrapolation": "外挿"},
    "種類": {"pointer": "指示", "claim": "主張"},
    "承認": {"none": "未"},
}
RETURNED = "差し戻し"  # 承認の欄の値。英語の原稿では returned とも書ける（_approval_state で読む）
OUTPUT_LANG = "ja"


def out_name(name):
    return FIELD_NAMES_EN.get(name, name) if OUTPUT_LANG == "en" else name


FIELD_RE = re.compile(r"^(@?)([^\s:@][^:]*?):\s?(.*)$")
MARK_RE = re.compile(r"〔(c\d{3,})〕")  # 原稿の中の引用の印。グループ1が ID（設定 manuscript.mark_pattern で替える）
QUOTE_RES = [re.compile(r"「([^「」]{10,})」"), re.compile(r"\"([^\"]{20,})\"")]  # 照合する引用符（manuscript.quote_patterns）
NOT_QUOTE_SEP = "／"
SENT_END_RE = re.compile(r"[。！？]")  # 原稿の文の終わり（manuscript.sentence_end）。英語の原稿は '[。！？]|[.!?](?=\\s)' 等
PARAGRAPH = "line"
KEY_LINE_RE = re.compile(r"^key:\s*(\S+)\s*$")
KIND_WORDS = [
    ("限界", ["limitation", "future work", "限界", "今後の課題", "今後の展望"]),
    ("関連研究", ["related work", "background", "prior work", "関連研究", "先行研究", "従来研究"]),
    ("参考文献", ["references", "bibliography", "参考文献"]),
    ("付録", ["appendix", "付録"]),
    ("序論", ["introduction", "はじめに", "序論", "まえがき"]),
    ("方法", ["method", "study design", "procedure", "participants", "実験方法", "評価方法"]),
    ("結果", ["result", "findings", "結果"]),
    ("議論", ["discussion", "考察"]),
    ("結論", ["conclusion", "concluding", "おわりに", "むすび", "結論", "まとめ"]),
    ("要旨", ["abstract", "要旨", "あらまし", "概要"]),
]
KIND_WORDS_MAP = dict(KIND_WORDS)
FILES_FIELD = "file"


COMMON_EN = set("the and of to in for with that this are is was were be on as by from or which can not have has their its".split())
