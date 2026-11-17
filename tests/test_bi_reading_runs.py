"""Empty reading fields filled from a card's own text (`docs/phases/BI_SUMMARY_FILL.md`): through
the usual run review, fill only, each value's quote word for word. All data is fictional."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs, _runtime
from test_bi_card_page_import import _apply, _preview
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _two_pcs
from test_bi_vault_sources import FOLDER

from aep_bi.cards import reading_runs
from aep_bi.cards.store import BiStore
from aep_bi.host.bi_cards_api import route
from common.execution import Failure

DESCRIBED = """---
type: technology
name: FAKE-TSN
standard_body: IEEE
confidence: assumed
---

## 說明
虛構的時間敏感網路技術,用於虛構工廠的即時控制。

```dataview
TABLE x FROM "BI/Y"
```

## 匯入備註
這段不是在講它。
"""
UNCONFIRMED = """---
type: technology
name: FAKE-PLP
---

## 說明
虛構廠商 A 的合作展示。
## 證據與來源
證據等級 C:僅公開展示,不構成供貨關係。
## 尚待確認
- 供貨關係
"""
EMPTY = """---
type: technology
name: FAKE-EMPTY
---

## 說明
(待補。)

```dataview
TABLE x FROM "BI/Y"
```
"""
SAMPLE = """---
type: technology
name: SAMPLE-FAKE
---

## 說明
虛構的範例文字,應該不會被送出去。
"""
ANSWER = {
    "summary": {
        "value": "虛構的時間敏感網路技術。",
        "quote": "虛構的時間敏感網路技術",
        "reason": "r",
    },
    "usage": {"value": "虛構工廠的即時控制。", "quote": "用於虛構工廠的即時控制", "reason": "r"},
    "scope": {"value": "不該寫入", "quote": "虛構的時間敏感網路技術", "reason": "r"},
}
NOTHING = {"summary": {"value": None, "quote": None, "reason": "沒說"}}


def _pages(*texts: str) -> list[dict[str, str]]:
    return [{"path": f"BI/Technology/p{i}.md", "text": t} for i, t in enumerate(texts)]


def _vault(tmp_path: Path, *texts: str) -> tuple[Path, str, str]:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    plan = _preview(a, dataset, _pages(*texts), folder=FOLDER)
    _apply(a, plan["preview_id"])
    return a, vault_id, dataset


def _start(ws: Path, dataset: str, model: Any, **given: Any) -> tuple[Any, Jobs]:
    jobs = Jobs()
    body = {"dataset": dataset, "kind": "ingest", "reading": True, **given}
    return route(ws, "alice", "POST", "/api/bi/runs", {}, body, None, _runtime(model, jobs)), jobs


def _ran(ws: Path, dataset: str, answer: Any, **given: Any) -> tuple[dict[str, Any], Scripted]:
    model = Scripted(answer)
    started, jobs = _start(ws, dataset, model, **given)
    run_id = _ok(started)["run"]["id"]
    jobs.run_all()
    found = _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))
    return dict(found), model


def _id(store: BiStore, name: str) -> str:
    found = store.find("Technology", name)
    assert found is not None
    return str(found["id"])


def _card(ws: Path, dataset: str, name: str) -> Any:
    store = BiStore(ws, dataset)
    return store.fields(_id(store, name))


def test_a_page_import_leaves_the_reading_empty_and_the_run_fills_it(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, DESCRIBED)
    before = _card(ws, dataset, "FAKE-TSN")
    assert "summary" not in before and "usage" not in before

    found, model = _ran(ws, dataset, lambda _text: ANSWER)
    run = found["run"]
    assert run["method_ref"] == "llm:reading" and run["status"] == "review"
    (candidate,) = found["candidates"]
    assert candidate["match"] == "existing" and candidate["action"] == "update"
    assert {f["field"]: f["merge"] for f in candidate["fields"]} == {
        "summary": "fill",
        "usage": "fill",
    }
    assert all(f["basis"] == "inference" for f in candidate["fields"])

    # Nothing is written before the person's review.
    assert "summary" not in _card(ws, dataset, "FAKE-TSN")
    _ok(_call(ws, "POST", f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
              {"dataset": dataset, "review": "accepted"}))  # fmt: skip
    _ok(_call(ws, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))
    after = _card(ws, dataset, "FAKE-TSN")
    assert after["summary"]["value"] == "虛構的時間敏感網路技術。"
    assert after["usage"]["value"] == "虛構工廠的即時控制。"
    for name in ("standard_body", "confidence"):
        assert after[name]["value"] == before[name]["value"]

    store = BiStore(ws, dataset)
    evidence = [e for e in store.evidence(_id(store, "FAKE-TSN"))
                if e["field"] == "summary"]  # fmt: skip
    assert evidence[0]["excerpt"] == "虛構的時間敏感網路技術"
    assert evidence[0]["source_name"] == "p0.md" and evidence[0]["basis"] == "inference"
    assert model.requests  # one call for the card


def test_what_the_model_reads_keeps_headings_and_evidence_notes(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, UNCONFIRMED)
    _found, model = _ran(ws, dataset, lambda _text: NOTHING)
    sent = model.requests[0].messages[1].text
    assert "## 尚待確認" in sent and "不構成供貨關係" in sent and "- 供貨關係" in sent


def test_only_the_cards_own_text_is_sent(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, DESCRIBED)
    _found, model = _ran(ws, dataset, lambda _text: NOTHING)
    system, user = (m.text for m in model.requests[0].messages)
    assert "虛構工廠的即時控制" in user
    assert "TABLE x" not in user and "這段不是在講它" not in user and "standard_body" not in user
    assert '"usage"' in system and '"scope"' not in system


def test_a_quote_not_in_the_text_loses_its_value(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, DESCRIBED)
    wrong = {
        "summary": {"value": "虛構的技術。", "quote": "原文沒有這句話", "reason": "r"},
        "usage": {
            "value": "虛構工廠的即時控制。",
            "quote": "用於虛構工廠的即時控制",
            "reason": "r",
        },
    }
    found, _model = _ran(ws, dataset, lambda _text: wrong)
    (candidate,) = found["candidates"]
    assert [f["field"] for f in candidate["fields"]] == ["usage"]
    assert [w["code"] for w in candidate["warnings"]] == ["evidence_not_found"]


def test_samples_cards_with_no_text_and_skipped_cards_are_not_sent(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, DESCRIBED, EMPTY, SAMPLE, UNCONFIRMED)
    found, model = _ran(ws, dataset, lambda _text: NOTHING, skip=["FAKE-PLP"])
    assert len(model.requests) == 1
    assert "FAKE-TSN" in model.requests[0].messages[1].text
    assert found["candidates"] == []
    said = [w["message"] for w in found["run"]["warnings"] if w["code"] == "reading_left_empty"]
    assert "sample" in said[0] and "skipped" in said[0] and "no text" in said[0]


def test_a_card_whose_text_says_nothing_new_stays_empty(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, EMPTY)
    started, _jobs = _start(ws, dataset, Scripted(lambda _text: ANSWER))
    status, body = started
    assert (status, body["code"]) == (400, "reading_nothing")


def test_a_value_filled_meanwhile_is_never_changed(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, DESCRIBED)
    model = Scripted(lambda _text: ANSWER)
    started, jobs = _start(ws, dataset, model)
    run_id = _ok(started)["run"]["id"]
    jobs.run_all()
    store = BiStore(ws, dataset)
    card = _id(store, "FAKE-TSN")
    fresh = _preview(
        ws,
        dataset,
        _pages(DESCRIBED.replace("confidence: assumed", "summary: 人寫的")),
        folder=FOLDER,
    )
    _apply(ws, fresh["preview_id"])
    assert store.fields(card)["summary"]["value"] == "人寫的"
    _ok(_call(ws, "POST", f"/api/bi/runs/{run_id}/recheck", {"dataset": dataset}))
    found = _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))
    (candidate,) = found["candidates"]
    merged = {f["field"]: f["merge"] for f in candidate["fields"]}
    assert merged == {"summary": "proposal", "usage": "fill"}
    _ok(_call(ws, "POST", f"/api/bi/runs/{run_id}/candidates/{candidate['id']}",
              {"dataset": dataset, "review": "accepted"}))  # fmt: skip
    _ok(_call(ws, "POST", f"/api/bi/runs/{run_id}/commit", {"dataset": dataset}))
    assert store.fields(card)["summary"]["value"] == "人寫的"


def test_a_failed_card_is_retried_and_a_trial_writes_nothing(tmp_path: Path) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, DESCRIBED)
    model = Scripted(Failure(code="model_http_error", message="x", retryable=True))
    started, jobs = _start(ws, dataset, model, kind="trial")
    run_id = _ok(started)["run"]["id"]
    jobs.run_all()
    found = _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))
    assert found["run"]["status"] == "failed" and found["run"]["failures"][0]["chunk"] == 0

    again = Scripted(lambda _text: ANSWER)
    jobs = Jobs()
    retried = route(ws, "alice", "POST", f"/api/bi/runs/{run_id}/retry", {},
                    {"dataset": dataset}, None, _runtime(again, jobs))  # fmt: skip
    _ok(retried)
    jobs.run_all()
    found = _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))
    assert found["run"]["status"] == "review" and len(found["candidates"]) == 1
    status, body = _call(ws, "POST", f"/api/bi/runs/{run_id}/commit", {"dataset": dataset})
    assert status != 200 and body["code"] == "run_trial"


def test_adding_a_field_is_one_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws, _vault_id, dataset = _vault(tmp_path, DESCRIBED)
    monkeypatch.setattr(reading_runs, "FIELDS", ("summary", "usage", "scope"))
    with_scope = {**ANSWER, "scope": {"value": "虛構工廠。", "quote": "虛構工廠", "reason": "r"}}
    found, model = _ran(ws, dataset, lambda _text: with_scope)
    (candidate,) = found["candidates"]
    assert {f["field"] for f in candidate["fields"]} == {"summary", "usage", "scope"}
    assert '"scope"' in model.requests[0].messages[0].text
