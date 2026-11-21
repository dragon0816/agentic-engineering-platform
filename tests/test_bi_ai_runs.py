"""BI ingest runs on the AI path (phase 4; `docs/phases/BI_INGEST.md` §7, §11).

A text source goes to the model in a background job; the run moves from
`extracting` to `review`, or to `partial` with retryable chunks. The owner
proposal's acceptance case runs end to end with a scripted model: evidence by
line from the meeting note, an inferred field marked, a value that does not
fit the schema blocking acceptance until edited, no Opportunity without a
stated need, and nothing written to the cards before 「確認匯入」. Without a
model the AI path is refused and the rule path still works.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from test_bi_extract import MEETING_ANSWER, NOTE, Scripted

from aep_bi.cards.ai_runs import AiRuntime
from aep_bi.cards.store import BiStore
from aep_bi.host.bi_cards_api import route
from common.execution import Failure

ACTOR = "tester"


class Jobs:
    """Background work held until `run_all`, as a thread would run it later."""

    def __init__(self) -> None:
        self.pending: list[tuple[str, Callable[[], None]]] = []

    def __call__(self, title: str, work: Callable[[], None]) -> None:
        self.pending.append((title, work))

    def run_all(self) -> None:
        while self.pending:
            self.pending.pop(0)[1]()


def _runtime(model: Any, jobs: Jobs) -> AiRuntime:
    pair = None if model is None else (model, "test-model")
    return AiRuntime(model=lambda: pair, background=jobs)


def _call(
    tmp_path: Path, method: str, path: str, body: Any = None, ai: Any = None, **q: str
) -> Any:
    return route(tmp_path, ACTOR, method, path, q, body, None, ai)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _note(tmp_path: Path) -> str:
    body = {"dataset": "demo", "name": "meeting.md", "text": NOTE}
    return str(_ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]["id"])


def _start(tmp_path: Path, ai: AiRuntime, source: str, kind: str = "ingest") -> dict[str, Any]:
    body = {"dataset": "demo", "kind": kind, "source_id": source}
    return dict(_ok(_call(tmp_path, "POST", "/api/bi/runs", body, ai))["run"])


def _detail(tmp_path: Path, run_id: str) -> dict[str, Any]:
    return _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run_id}", dataset="demo"))


def _review(tmp_path: Path, run_id: str, cid: str, **body: Any) -> Any:
    path = f"/api/bi/runs/{run_id}/candidates/{cid}"
    return _call(tmp_path, "POST", path, {"dataset": "demo", **body})


def test_the_meeting_note_runs_end_to_end(tmp_path: Path) -> None:
    jobs = Jobs()
    ai = _runtime(Scripted(MEETING_ANSWER), jobs)
    run = _start(tmp_path, ai, _note(tmp_path))
    assert run["status"] == "extracting" and run["model"] == "test-model"
    assert run["method_ref"] == "llm:default"
    jobs.run_all()
    detail = _detail(tmp_path, run["id"])
    assert detail["run"]["status"] == "review"
    assert detail["run"]["progress"]["done"] == detail["run"]["progress"]["chunks"] >= 1
    assert detail["run"]["types"] == ["Signal", "Technology", "Application"]
    by_type = {c["entity_type"]: c for c in detail["candidates"]}
    # Opportunity is not in the default types; the shipped types are the MVP's three.
    assert set(by_type) == {"Signal", "Technology", "Application"}
    signal = {f["field"]: f for f in by_type["Signal"]["fields"]}
    assert signal["summary"]["evidence"][0]["locator"] == {"line_start": 4, "line_end": 4}
    assert signal["so_what"]["basis"] == "inference"
    application = by_type["Application"]
    assert [e["field"] for e in application["errors"]] == ["lifecycle"]
    assert "value_errors" not in application
    status, payload = _review(tmp_path, run["id"], application["id"], review="accepted")
    assert (status, payload["code"]) == (400, "candidate_invalid")
    fixed = _ok(
        _review(
            tmp_path,
            run["id"],
            application["id"],
            fields={"lifecycle": "Production"},
            review="accepted",
        )
    )["candidate"]
    assert fixed["errors"] == [] and fixed["review"] == "accepted"
    for candidate in detail["candidates"]:
        if candidate["entity_type"] != "Application":
            _ok(_review(tmp_path, run["id"], candidate["id"], review="accepted"))
    assert not BiStore(tmp_path).exists
    done = _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": "demo"}))
    assert done["applied"]["created"] == 3
    signal_card = next(c for c in BiStore(tmp_path).card_rows() if c["entity_type"] == "Signal")
    card = _ok(_call(tmp_path, "GET", f"/api/bi/cards/{signal_card['id']}", dataset="demo"))
    summary = next(e for e in card["evidence"] if e["field"] == "summary")
    assert summary["source_name"] == "meeting.md" and summary["locator"]["line_start"] == 4
    assert summary["basis"] == "fact"


def test_opportunities_need_a_stated_need(tmp_path: Path) -> None:
    jobs = Jobs()
    ai = _runtime(Scripted(MEETING_ANSWER), jobs)
    body = {
        "dataset": "demo",
        "kind": "trial",
        "source_id": _note(tmp_path),
        "types": ["Signal", "Technology", "Application", "Opportunity"],
        "instructions": "沒有文件依據的需求標成推測。",
    }
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", body, ai))["run"]
    assert run["method_ref"] == "llm:inline"
    jobs.run_all()
    (opportunity,) = [
        c for c in _detail(tmp_path, run["id"])["candidates"] if c["entity_type"] == "Opportunity"
    ]
    assert opportunity["review"] == "rejected"
    assert "opportunity_unsupported" in [w["code"] for w in opportunity["warnings"]]
    status, payload = _call(tmp_path, "POST", "/api/bi/runs", {**body, "types": ["Nope"]}, ai)
    assert (status, payload["code"]) == (400, "types_invalid")


def test_a_failed_chunk_makes_a_partial_run_that_can_be_retried(tmp_path: Path) -> None:
    jobs = Jobs()
    long_note = NOTE + "\n## 附錄\n\n" + "產線背景說明。" * 1000 + "\n"
    body = {"dataset": "demo", "name": "long.md", "text": long_note}
    source = _ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]["id"]
    failing = Scripted(MEETING_ANSWER, Failure(code="model_http_error", message="503"))
    run = _start(tmp_path, _runtime(failing, jobs), source)
    jobs.run_all()
    detail = _detail(tmp_path, run["id"])
    assert detail["run"]["progress"]["chunks"] == 2
    assert detail["run"]["status"] == "partial" and len(detail["candidates"]) == 3
    assert [f["code"] for f in detail["run"]["failures"]] == ["model_unavailable"]
    # The candidates found so far can be reviewed while the failed chunk waits.
    signal = next(c for c in detail["candidates"] if c["entity_type"] == "Signal")
    _ok(_review(tmp_path, run["id"], signal["id"], review="accepted"))
    again = Scripted({"candidates": []})
    path = f"/api/bi/runs/{run['id']}/retry"
    _ok(_call(tmp_path, "POST", path, {"dataset": "demo"}, _runtime(again, jobs)))
    jobs.run_all()
    after = _detail(tmp_path, run["id"])
    assert len(again.requests) == 1  # only the failed chunk
    assert after["run"]["status"] == "review" and after["run"]["failures"] == []
    assert len(after["candidates"]) == 3
    kept = next(c for c in after["candidates"] if c["entity_type"] == "Signal")
    assert kept["review"] == "accepted"


def test_every_chunk_failing_fails_the_run_and_retry_recovers(tmp_path: Path) -> None:
    jobs = Jobs()
    ai = _runtime(Scripted(*[Failure(code="model_http_error", message="503")] * 5), jobs)
    run = _start(tmp_path, ai, _note(tmp_path))
    jobs.run_all()
    detail = _detail(tmp_path, run["id"])
    assert detail["run"]["status"] == "failed" and detail["run"]["failures"]
    commit = f"/api/bi/runs/{run['id']}/commit"
    status, payload = _call(tmp_path, "POST", commit, {"dataset": "demo"})
    assert (status, payload["code"]) == (409, "run_closed")
    _ok(
        _call(
            tmp_path,
            "POST",
            f"/api/bi/runs/{run['id']}/retry",
            {"dataset": "demo"},
            _runtime(Scripted(MEETING_ANSWER), jobs),
        )
    )
    jobs.run_all()
    after = _detail(tmp_path, run["id"])
    assert after["run"]["status"] == "review" and len(after["candidates"]) == 3


def test_without_a_model_the_ai_path_is_refused(tmp_path: Path) -> None:
    jobs = Jobs()
    status, payload = _call(
        tmp_path,
        "POST",
        "/api/bi/runs",
        {"dataset": "demo", "kind": "ingest", "source_id": _note(tmp_path)},
        _runtime(None, jobs),
    )
    assert (status, payload["code"]) == (400, "model_unavailable")
    assert jobs.pending == []
    csv = {"dataset": "demo", "name": "t.csv", "text": "技術,成熟度\nTSN,growth\n"}
    source = _ok(_call(tmp_path, "POST", "/api/bi/sources", csv))["source"]["id"]
    run = _start(tmp_path, _runtime(None, jobs), source)
    assert run["status"] == "review" and run["model"] is None


def test_a_cancelled_extraction_stays_cancelled(tmp_path: Path) -> None:
    jobs = Jobs()
    run = _start(tmp_path, _runtime(Scripted(MEETING_ANSWER), jobs), _note(tmp_path))
    _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/cancel", {"dataset": "demo"}))
    jobs.run_all()
    assert _detail(tmp_path, run["id"])["run"]["status"] == "cancelled"


def test_a_source_of_every_data_class_goes_to_the_model(tmp_path: Path) -> None:
    """BI never refuses a source for its data class (owner 2026-11-17): the class
    stays recorded on the source, and the source is sent to the model."""
    for level in ("INTERNAL", "CONFIDENTIAL", "RESTRICTED"):
        jobs = Jobs()
        model = Scripted(MEETING_ANSWER)
        ai = _runtime(model, jobs)
        body = {
            "dataset": "demo",
            "name": f"{level.lower()}.md",
            "text": NOTE + f"\n標記 MARK-{level}。\n",
            "classification": level,
        }
        added = _ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]
        assert added["classification"] == level
        run = _start(tmp_path, ai, str(added["id"]), kind="trial")
        jobs.run_all()
        assert _detail(tmp_path, run["id"])["run"]["status"] == "review"
        assert any(f"MARK-{level}" in str(request) for request in model.requests)


def test_a_retry_is_sent_whatever_the_source_s_data_class(tmp_path: Path) -> None:
    """A retry is never refused for the source's class: no approval is consulted."""
    jobs = Jobs()
    model = Scripted(Failure(code="model_unavailable", message="down"), MEETING_ANSWER)
    ai = AiRuntime(model=lambda: (model, "test-model"), background=jobs)
    run = _start(tmp_path, ai, _note(tmp_path))  # INTERNAL by default
    jobs.run_all()
    assert _detail(tmp_path, run["id"])["run"]["status"] == "failed"
    asked = len(model.requests)

    path = f"/api/bi/runs/{run['id']}/retry"
    _ok(_call(tmp_path, "POST", path, {"dataset": "demo"}, ai))
    jobs.run_all()
    assert len(model.requests) > asked
    assert _detail(tmp_path, run["id"])["run"]["status"] == "review"


def test_a_truncated_answer_says_which_chunk_and_can_be_tried_again(tmp_path: Path) -> None:
    """Measured 2026-11-04: real report chunks needed up to 16,705 output tokens.
    The limit has room for that, and a chunk that still does not fit is not lost silently."""
    jobs = Jobs()
    truncated = Failure(code="model_output_truncated", message="cut", retryable=False)
    model = Scripted(truncated, MEETING_ANSWER)
    ai = _runtime(model, jobs)
    run = _start(tmp_path, ai, _note(tmp_path))
    jobs.run_all()
    assert model.requests[0].max_output_tokens == 32000
    detail = _detail(tmp_path, run["id"])
    assert detail["run"]["status"] == "failed" and detail["candidates"] == []
    (failure,) = detail["run"]["failures"]
    assert failure["code"] == "model_output_truncated" and failure["retryable"] is True
    assert failure["chunk"] == 0 and failure["line_start"] == 1 and failure["line_end"] >= 1
    assert "這一段沒有讀到" in failure["message"] and "可以重試" in failure["message"]

    path = f"/api/bi/runs/{run['id']}/retry"
    _ok(_call(tmp_path, "POST", path, {"dataset": "demo"}, ai))
    jobs.run_all()
    again = _detail(tmp_path, run["id"])
    assert again["run"]["status"] == "review" and again["run"]["failures"] == []
    assert again["candidates"]


def test_a_warning_names_its_field_never_blocks_and_is_confirmed_or_edited(
    tmp_path: Path,
) -> None:
    """Owner 2026-11-20: 「警告」 must not block acceptance and must say what to fix. A field's
    warning names the field; 確認 moves it to `confirmed` with who confirmed it, and a person's
    value for the field does the same; nothing is silently dropped."""
    jobs = Jobs()
    run = _start(tmp_path, _runtime(Scripted(MEETING_ANSWER), jobs), _note(tmp_path))
    jobs.run_all()
    signal = next(
        c for c in _detail(tmp_path, run["id"])["candidates"] if c["entity_type"] == "Signal"
    )
    (inferred,) = [w for w in signal["warnings"] if w["code"] == "inference"]
    assert inferred["field"] == "so_what" and inferred["message"].endswith(
        inferred["message"].split("是推論：", 1)[1]
    )
    # A warning does not stop 接受.
    accepted = _ok(_review(tmp_path, run["id"], signal["id"], review="accepted"))["candidate"]
    assert accepted["review"] == "accepted" and accepted["warnings"]
    confirm = {"code": "inference", "field": "so_what", "message": inferred["message"]}
    done = _ok(_review(tmp_path, run["id"], signal["id"], confirm_warning=confirm))["candidate"]
    assert not [w for w in done["warnings"] if w["code"] == "inference"]
    (kept,) = done["confirmed"]
    assert (kept["field"], kept["by"]) == ("so_what", "tester via web") and kept["at"]
    status, payload = _review(tmp_path, run["id"], signal["id"], confirm_warning=confirm)
    assert (status, payload["code"]) == (404, "warning_unknown")
