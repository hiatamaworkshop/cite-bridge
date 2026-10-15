# -*- coding: utf-8 -*-
"""分類器の差し込み口。エンジン（Jev など）を替えられるよう、呼び出しを一つの形にし、提供元ごとにアダプタを書く。

アダプタの契約は一つだけである。

    classify(state, asks) -> list[Verdict | None]

state は問いが共通に見る材料の文面。asks は同じ state に対する互いに独立な問い（閉じた選択肢）で、結果は同じ順に並ぶ。
答えられなかった問いは None。分類器は文を作らず、ラベルを一つ返す。

確からしさ（score）は表示と台帳のためにあり、ツール側の規則は分岐に使わない（提供元を替えたとき、規則が変わらないため）。
判定できないときは、分類器が「判定できない」のラベルを選ぶ。
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Ask:
    """問い一つ。type は問いの名前、labels は閉じた選択肢、gloss はラベルごとの短い説明、about は判定の対象になる文。"""
    type: str
    labels: tuple
    question: str = ""
    gloss: tuple = ()
    about: str = ""


@dataclass(frozen=True)
class Verdict:
    label: str
    score: "float | None" = None
    scores: dict = field(default_factory=dict, compare=False)


class ClassifierUnavailable(Exception):
    """提供元が使える答えを返さなかった（鍵が無い、通信できない、応答が読めない）。一度の呼び出し全体の失敗として扱う。"""


class Classifier:
    """基底。エンジンを持たず、何も判定しない。"""
    name = ""
    model = ""

    def classify(self, state, asks):
        return [None for _ in asks]


# ---------------------------------------------------------------- Jev（TypeSafe）

JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_KEY_VARS = ("TYPESAFE_API_KEY", "JEV_API_KEY")  # 鍵は環境変数だけで受ける。設定ファイルには書かない


def jev_key():
    for name in JEV_KEY_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _http_post(url, payload, key, timeout_s):
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


def _question_id(i):
    return f"q{i + 1}"


def _criteria(ask):
    """選択肢の鍵は 1 から n の番号にし、ラベルと説明を文面に入れる（鍵が重ならず、提供元が文面を読む）。"""
    gloss = dict(ask.gloss)
    return {str(j + 1): (f"{label}：{gloss[label]}" if gloss.get(label) else label) for j, label in enumerate(ask.labels)}


def jev_payload(model, state, asks):
    """要求の本体。呼び出しと分けてあるのは、試験が読めるようにするため。"""
    return {
        "state": state,
        "model": model,
        "questions": {
            _question_id(i): {
                "type": "choice",
                "instructions": ask.question.replace("{about}", ask.about) if "{about}" in ask.question else ask.question,
                "criteria": _criteria(ask),
            }
            for i, ask in enumerate(asks)
        },
    }


def jev_parse(body, asks):
    """応答を Verdict の並びにする。確率の鍵が選択肢の番号でないものは捨て、一つも残らない問いは None にする。"""
    if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
        raise ClassifierUnavailable("応答が読めない（answers が無い）")
    out = []
    for i, ask in enumerate(asks):
        ans = body["answers"].get(_question_id(i))
        probs = ans.get("probabilities") if isinstance(ans, dict) else None
        scored = {}
        if isinstance(probs, dict):
            for key, p in probs.items():
                try:
                    j, v = int(str(key)) - 1, float(p)
                except (TypeError, ValueError):
                    continue
                if 0 <= j < len(ask.labels):
                    scored[ask.labels[j]] = v
        if not scored:
            out.append(None)
            continue
        # 同点は選択肢の並びの先を取る（同じ問いを二度出しても結果が変わらない）
        label = max(ask.labels, key=lambda l: (scored.get(l, -1.0), -ask.labels.index(l)))
        out.append(Verdict(label=label, score=scored[label], scores=scored))
    return out


class JevClassifier(Classifier):
    name = "jev"

    def __init__(self, model="", endpoint="", *, key="", timeout_s=30.0, post=None):
        self.model = model or JEV_MODEL
        self.endpoint = endpoint or JEV_ENDPOINT
        self._key = key or jev_key()
        self._timeout = timeout_s
        self._post = post or _http_post

    def classify(self, state, asks):
        if not asks:
            return []
        if not self._key:
            raise ClassifierUnavailable("鍵が無い（環境変数 " + " か ".join(JEV_KEY_VARS) + "）")
        try:
            body = self._post(self.endpoint, jev_payload(self.model, state, asks), self._key, self._timeout)
        except Exception as exc:
            raise ClassifierUnavailable(f"{type(exc).__name__}: {exc}") from exc
        return jev_parse(body, asks)


# ---------------------------------------------------------------- 提供元の選択

#: 設定の provider の名前 -> アダプタ。提供元を足すときは、Classifier を継いだクラスを書いて、ここに一行足す。
PROVIDERS = {"jev": JevClassifier}


def make_classifier(conf):
    """設定（[classifier]）から提供元を作る。provider が無ければ None（分類器を使わない）。知らない名前は例外。"""
    name = (conf or {}).get("provider", "")
    if not name:
        return None
    if name not in PROVIDERS:
        raise ValueError(f"分類器の提供元 '{name}' は無い（{sorted(PROVIDERS)}）")
    return PROVIDERS[name](model=conf.get("model", ""), endpoint=conf.get("endpoint", ""))
