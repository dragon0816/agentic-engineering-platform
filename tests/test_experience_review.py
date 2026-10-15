"""Experience cases and the report-only review (EXPERIENCE_REVIEW E1-E2)."""

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

from common.execution import Failure, TraceIdentifiers
from host_runtime.conversations import ConversationMessage, ConversationRecord, MessageFeedback
from host_runtime.experience import (
    ExperienceSettings,
    ExperienceStore,
    from_benchmarks,
    from_conversations,
    from_telemetry,
    group,
    load_settings,
    save_settings,
)
from host_runtime.experience_review import latest_review, run_review
from host_runtime.web_page import PAGE
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
TRACE = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")


def _answer(
    mid: str,
    text: str,
    *,
    status: str = "answered",
    tools: str | None = None,
    rating: str | None = None,
    note: str | None = None,
) -> ConversationMessage:
    return ConversationMessage(
        message_id=mid,
        role="assistant",
        text=text,
        created_at=NOW,
        status=status,
        trace=TRACE,
        tool_summary=tools,
        feedback=MessageFeedback(rating=rating, note=note, updated_at=NOW) if rating else None,
    )


def _record() -> ConversationRecord:
    def ask(mid: str, text: str) -> ConversationMessage:
        return ConversationMessage(
            message_id=mid, role="user", text=text, created_at=NOW, status="submitted"
        )

    return ConversationRecord(
        session_id="s1",
        actor="engineer",
        title="t",
        created_at=NOW,
        updated_at=NOW,
        messages=(
            ask("u1", "Wi-Fi 7 要哪些儀器？"),
            _answer("a1", "FSV3000", rating="down", note="漏了 FSWX"),
            ask("u2", "ZNA67 升級要哪些 option？"),
            _answer(
                "a2",
                "知識庫無法驗證",
                tools="- knowledge__rs-knowledge: failed (knowledge_not_validated) {}",
            ),
            ask("u3", "6G 的市佔？"),
            _answer(
                "a3",
                "證據不足",
                tools="- knowledge__rs-knowledge: failed (knowledge_insufficient_evidence) {}",
            ),
            ask("u4", "天氣？"),
            _answer("a4", "晴天"),  # nothing went wrong: no case
        ),
    )


def test_conversations_become_cases_once(tmp_path: Path) -> None:
    cases = from_conversations([_record()])
    assert [(c.signal, c.domain, c.failure_code) for c in cases] == [
        ("rating", "conversation", None),
        ("harness_gave_up", "knowledge", "knowledge_not_validated"),
        ("evidence_gap", "knowledge", "knowledge_insufficient_evidence"),
    ]
    assert cases[0].subject == "Wi-Fi 7 要哪些儀器？" and cases[0].rating_note == "漏了 FSWX"
    store = ExperienceStore(tmp_path)
    assert store.add(cases) == 3 and store.add(from_conversations([_record()])) == 0


def test_benchmarks_and_telemetry_become_cases(tmp_path: Path) -> None:
    folder = tmp_path / "sb" / "sb-a" / ".benchmarks"
    folder.mkdir(parents=True)
    (folder / "bench-1.json").write_text(
        json.dumps(
            {
                "run_id": "bench-1",
                "started_at": NOW.isoformat(),
                "regressions": ["market/q.md"],
                "results": [
                    {
                        "path": "market/q.md",
                        "question": "Q?",
                        "sandbox": {
                            "answer": "x",
                            "grade": {"passed": False, "missing": ["FSWX"], "forbidden": []},
                        },
                        "project": {"grade": {"passed": True}},
                    },
                    {
                        "path": "market/ok.md",
                        "question": "OK?",
                        "sandbox": {"grade": {"passed": True}},
                        "project": {"grade": {}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (bench,) = from_benchmarks(tmp_path / "sb")
    assert (bench.signal, bench.failure_code, bench.rule) == (
        "regression",
        "missing_terms",
        "checks/questions/market/q.md",
    )
    db = tmp_path / "telemetry.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE runs (run_id TEXT, run_kind TEXT, started_at TEXT, status TEXT,"
        " skill_id TEXT, summary TEXT)"
    )
    conn.execute(
        "INSERT INTO runs VALUES ('r1', 'workflow_run', ?, 'failed', NULL,"
        ' \'{"outcome": "failed"}\')',
        (NOW.isoformat(),),
    )
    conn.execute(
        "INSERT INTO runs VALUES ('r2', 'conversation_turn', ?, 'failed', NULL, '{}')",
        (NOW.isoformat(),),
    )
    conn.commit()
    conn.close()
    (run,) = from_telemetry(db)
    assert (run.domain, run.signal) == ("workflow", "run_failed")
    # With events, the case names the Workflow and the step that failed.
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE events (run_id TEXT, sequence INTEGER, record TEXT)")
    for number, attributes in enumerate(
        [
            {"workflow_id": "engineering/weekly@1.0.2"},
            {"step_index": 2, "tool_id": "excel/read@1.0.0", "failure_code": "handler_error"},
        ]
    ):
        conn.execute(
            "INSERT INTO events VALUES ('r1', ?, ?)",
            (number, json.dumps({"attributes": attributes})),
        )
    conn.commit()
    conn.close()
    (named,) = from_telemetry(db)
    assert named.subject == (
        "Workflow engineering/weekly@1.0.2: step 2 excel/read@1.0.0 failed (handler_error)"
    )
    assert (named.failure_code, named.rule) == ("handler_error", "engineering/weekly")


def test_retention_is_a_setting_with_a_thirty_day_default(tmp_path: Path) -> None:
    assert load_settings(tmp_path) == ExperienceSettings(retention_days=30, nightly=True)
    save_settings(tmp_path, ExperienceSettings(retention_days=7, nightly=False))
    assert load_settings(tmp_path).retention_days == 7
    store = ExperienceStore(tmp_path)
    old = from_conversations([_record()])[0].model_copy(
        update={"case_id": "case-old", "created_at": (NOW - timedelta(days=10)).isoformat()}
    )
    store.add([old, *from_conversations([_record()])])
    assert store.prune(7, now=NOW) == 1 and len(store.cases()) == 3


class _Reviewer:
    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.fail_on and self.fail_on in request.messages[1].text:
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                failure=Failure(code="model_http_error", message="503"),
            )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output={
                "cause": "rule_missing",
                "diagnosis": "Answers omit instruments (case 1).",
                "proposal": {
                    "kind": "rule_edit",
                    "target": "skills/ask-knowledge/SKILL.md",
                    "text": "List every instrument the evidence names, because...",
                },
                "confidence": "medium",
                "confirm": "Two more cases with the same omission.",
            },
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def test_a_review_reports_proposals_per_group_and_changes_nothing(tmp_path: Path) -> None:
    store = ExperienceStore(tmp_path)
    store.add(from_conversations([_record()]))
    assert len(group(store.cases())) == 3
    rules_asked: list[str] = []

    def rules(domain: str) -> str:
        rules_asked.append(domain)
        return "RULES IN FORCE" if domain == "knowledge" else ""

    model = _Reviewer(fail_on="證據不足")
    report = run_review(store, model, "company", rules, workspace=tmp_path, harvested=3)
    assert len(report.findings) == 3 and sorted(rules_asked) == [
        "conversation",
        "knowledge",
        "knowledge",
    ]
    reviewed = [f for f in report.findings if f.error is None]
    failed = [f for f in report.findings if f.error]
    assert len(reviewed) == 2 and len(failed) == 1
    assert reviewed[0].proposal is not None and reviewed[0].cause == "rule_missing"
    # Reviewed groups are closed; the failed one stays open for the next night.
    assert len(store.cases("open")) == 1
    saved = latest_review(tmp_path)
    assert saved is not None and "Cause: **rule_missing**" in saved["markdown"]
    assert any("RULES IN FORCE" in r.messages[1].text for r in model.requests)


def test_the_reviews_tab_shows_the_experience_review() -> None:
    for hook in ('id="xp-run"', 'id="xp-days"', "/api/experience/settings", "/api/experience"):
        assert hook in PAGE
