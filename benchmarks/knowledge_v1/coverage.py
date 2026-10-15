"""Pick the fewest questions that cover the bank (owner 2026-10-09).

The owner cares about coverage, not the number of questions. A greedy set
cover picks, each time, the question that covers the most still-uncovered
features, preferring questions earlier runs already asked (comparable) and
then file order. Two tiers:

- core: every market x product cell, every type in every market and in every
  product, every type x difficulty, every foundation category, and every
  outcome seen in earlier runs (status, gap and route);
- intents: core plus every distinct question template (the same question with
  only the market and product names swapped is one template) and every
  foundation topic group.

    .venv\\Scripts\\python.exe benchmarks\\knowledge_v1\\coverage.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import questions as Q  # noqa: E402


def template(question: dict[str, Any]) -> str:
    text = question["text"]
    for key in ("market", "product"):
        if question.get(key):
            text = text.replace(question[key], "{" + key + "}")
    return text


def past_outcomes() -> dict[str, tuple[str, str, str]]:
    """The latest recorded outcome of each question asked before."""
    found: dict[str, tuple[str, str, str]] = {}
    for run in sorted((HERE / "runs").glob("sample-*")):
        for result in run.glob("Q*/result.json"):
            data = json.loads(result.read_text(encoding="utf-8"))
            found[data["id"]] = (
                str(data.get("status")),
                str(data.get("gap") or "-"),
                str(data.get("route") or "-"),
            )
    return found


def features(
    question: dict[str, Any], history: dict[str, tuple[str, str, str]], tier: str
) -> set[str]:
    out: set[str] = set()
    if "market" in question:
        market, product, kind = question["market"], question["product"], question["type"]
        out |= {
            f"cell:{market}|{product}",
            f"type-market:{kind}|{market}",
            f"type-product:{kind}|{product}",
            f"type-difficulty:{kind}|{question['difficulty']}",
        }
        if tier == "intents":
            out.add("template:" + template(question))
    else:
        out.add("foundation:" + question.get("technical", "?"))
        if tier == "intents":
            out.add("topic:" + question.get("topic", "?"))
    if question["id"] in history:
        status, gap, route = history[question["id"]]
        out.add(f"outcome:{status}|{gap}|{route}")
    return out


def cover(questions: list[dict[str, Any]], tier: str) -> list[dict[str, Any]]:
    history = past_outcomes()
    pool = {q["id"]: features(q, history, tier) for q in questions}
    wanted = set().union(*pool.values())
    chosen: list[dict[str, Any]] = []
    by_id = {q["id"]: q for q in questions}
    while wanted:
        best = max(
            pool, key=lambda ident: (len(pool[ident] & wanted), ident in history, -int(ident[1:]))
        )
        gained = pool.pop(best) & wanted
        if not gained:
            break
        wanted -= gained
        chosen.append({**by_id[best], "covers": sorted(gained), "past": history.get(best)})
    return sorted(chosen, key=lambda q: q["id"])


def main() -> int:
    questions = Q.load()
    report = {}
    for tier in ("core", "intents"):
        picked = cover(questions, tier)
        report[tier] = picked
        kinds = Counter(q.get("type", "foundation") for q in picked)
        print(f"{tier}: {len(picked)} questions {dict(kinds)}")
    (HERE / "questions" / "coverage.json").write_text(
        json.dumps({tier: [q["id"] for q in picked] for tier, picked in report.items()}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    write_review(report, questions)
    return 0


def write_review(report: dict[str, list[dict[str, Any]]], questions: list[dict[str, Any]]) -> None:
    history = past_outcomes()
    templates = {template(q) for q in questions if "market" in q}
    core = report["core"]
    lines = [
        "# knowledge_v1 涵蓋率選題（審閱用）",
        "",
        "由 `benchmarks/knowledge_v1/coverage.py` 產生（2026-10-09）。"
        "目標是用最少題目涵蓋題庫的各個面向，"
        "而不是追求題數。選法：每次挑「能補上最多尚未涵蓋面向」的題目；同分時優先選以前跑過的題目"
        "（方便前後比較），再依題號。",
        "",
        "## 兩個層級",
        "",
        f"- **核心層（core）：{len(core)} 題**。涵蓋：20 個市場×產品格、"
        "每個題型在每個市場與每個產品都出現、"
        "每個題型×難度組合、6 個基礎知識類別，以及過去三次樣本出現過的每一種結果"
        "（PASS / INSUFFICIENT / FAIL 與缺口類型、直接或工具路徑）。",
        f"- **意圖層（intents）：{len(report['intents'])} 題**。在核心層之上再涵蓋全部 "
        f"{len(templates)} 種題目模板（同一題只換市場/產品名稱算一種）與 100 個基礎主題。",
        "",
        "建議先用**核心層**請 Claude Code 產生參考答案並比較；"
        "若核心層結果穩定，再決定是否擴到意圖層。",
        "",
        f"過去跑過的題目共 {len(history)} 題；核心層中有 "
        f"{sum(1 for q in core if q['id'] in history)} 題跑過，可直接前後比較。",
        "",
        "## 核心層題目",
        "",
        "| 題號 | 市場 / 產品（或基礎類別） | 題型 / 難度 | 過去結果 | 題目 | 涵蓋原因 |",
        "|---|---|---|---|---|---|",
    ]
    for q in core:
        where = (
            f"{q['market']} / {q['product']}"
            if "market" in q
            else f"基礎：{q.get('technical')}（{q.get('topic')}）"
        )
        kind = f"{q.get('type', '-')} / {q.get('difficulty', '-')}"
        past = "／".join(q["past"]) if q["past"] else "未跑過"
        reason = "；".join(item.split(":", 1)[0] for item in q["covers"])
        lines.append(
            f"| {q['id']} | {where} | {kind} | {past} | {q['text']} | "
            f"{len(q['covers'])} 項（{reason}） |"
        )
    out = HERE / "questions" / "coverage-review.zh-TW.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    raise SystemExit(main())
