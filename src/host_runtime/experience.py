"""Experience cases: what went wrong, harvested from the Host's own records (E1).

`docs/phases/EXPERIENCE_REVIEW.md`. A case is one answer or run that failed,
gave up, lacked evidence or was rated down. Cases are harvested from records
the Host already keeps:

- conversation answers (status, rating and reason, tool summary);
- sandbox question-set benchmarks;
- failed coding and Workflow runs in telemetry.

Every case has a stable id, so harvesting again adds nothing twice. Cases are
grouped by domain, failure and governing rule; the review (E2) diagnoses a
group, never a lone case. Cases older than the retention setting (default 30
days, owner 2026-10-12) are removed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from common.assets import SECRET_PATTERN
from common.base import Contract

STORE_FILE = "experience.sqlite"
SETTINGS_FILE = "experience-settings.json"
EXCERPT = 1500
FAILED_TOOL = re.compile(r"(\w[\w.-]*): failed \((\w+)\)")
EVIDENCE_GAP = {"knowledge_insufficient_evidence", "knowledge_not_grounded"}

Signal = Literal[
    "rating", "harness_gave_up", "evidence_gap", "question_set_failure", "regression", "run_failed"
]


class ExperienceSettings(Contract):
    retention_days: int = Field(default=30, ge=1, le=3650)
    nightly: bool = True
    # Suggested Skills from repeated work (docs/phases/SKILL_SUGGESTIONS.md, S1):
    # off means no harvest and no model call; the cap bounds the request
    # excerpts one nightly grouping pass sends to the model.
    suggestions: bool = True
    suggestion_max_requests: int = Field(default=120, ge=10, le=1000)
    # S2: which row of the design's section 5 table (repeated requests) the
    # nightly pass uses; read on every pass, so a change needs no restart.
    suggestion_sensitivity: Literal["low", "normal", "high"] = "normal"


class ExperienceCase(Contract):
    case_id: str
    created_at: str
    domain: str  # knowledge, conversation, coding, workflow
    signal: Signal
    subject: str  # the question or task, an excerpt
    answer: str = ""  # an excerpt of what was answered or produced
    failure_code: str | None = None
    rating_note: str | None = None
    rule: str | None = None  # the governing Skill or rule file, when known
    source: str  # where it was harvested from, e.g. conversation:<session>/<message>
    status: Literal["open", "reviewed"] = "open"
    review_id: str | None = None

    @property
    def group_key(self) -> str:
        return f"{self.domain}|{self.failure_code or self.signal}|{self.rule or '-'}"


def _clip(text: str | None) -> str:
    return SECRET_PATTERN.sub("[redacted]", (text or "").strip())[:EXCERPT]


def _id(*parts: str) -> str:
    return "case-" + hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:20]


def load_settings(workspace: Path) -> ExperienceSettings:
    path = workspace / SETTINGS_FILE
    try:
        return ExperienceSettings.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ExperienceSettings()


def save_settings(workspace: Path, settings: ExperienceSettings) -> ExperienceSettings:
    checked = ExperienceSettings.model_validate(settings)
    (workspace / SETTINGS_FILE).write_text(checked.model_dump_json(indent=1), encoding="utf-8")
    return checked


class ExperienceStore:
    def __init__(self, workspace: Path) -> None:
        self.path = workspace / STORE_FILE
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cases (case_id TEXT PRIMARY KEY,"
                " created_at TEXT NOT NULL, status TEXT NOT NULL, record TEXT NOT NULL)"
            )
            conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    def add(self, cases: Iterable[ExperienceCase]) -> int:
        """Store new cases; a case already known keeps its status. Returns how
        many were new."""
        added = 0
        with self._lock, self._connect() as conn:
            for case in cases:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO cases (case_id, created_at, status, record)"
                    " VALUES (?, ?, ?, ?)",
                    (case.case_id, case.created_at, case.status, case.model_dump_json()),
                )
                added += cursor.rowcount
        return added

    def cases(self, status: str | None = None) -> list[ExperienceCase]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT record FROM cases"
                + (" WHERE status = ?" if status else "")
                + " ORDER BY created_at",
                (status,) if status else (),
            ).fetchall()
        return [ExperienceCase.model_validate_json(row[0]) for row in rows]

    def mark_reviewed(self, case_ids: Iterable[str], review_id: str) -> None:
        with self._lock, self._connect() as conn:
            for case_id in case_ids:
                row = conn.execute(
                    "SELECT record FROM cases WHERE case_id = ?", (case_id,)
                ).fetchone()
                if row is None:
                    continue
                case = ExperienceCase.model_validate_json(row[0]).model_copy(
                    update={"status": "reviewed", "review_id": review_id}
                )
                conn.execute(
                    "UPDATE cases SET status = ?, record = ? WHERE case_id = ?",
                    ("reviewed", case.model_dump_json(), case_id),
                )

    def prune(self, retention_days: int, now: datetime | None = None) -> int:
        cutoff = ((now or datetime.now(UTC)) - timedelta(days=retention_days)).isoformat()
        with self._lock, self._connect() as conn:
            return conn.execute("DELETE FROM cases WHERE created_at < ?", (cutoff,)).rowcount

    def meta(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row[0])

    def set_meta(self, key: str, value: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key)"
                " DO UPDATE SET value = excluded.value",
                (key, value),
            )


# -- harvesters ----------------------------------------------------------------


def from_conversations(records: Iterable[Any]) -> list[ExperienceCase]:
    """Answers that were rated down, failed, needed input, or whose tools failed."""
    found = []
    for record in records:
        question = ""
        for message in record.messages:
            if message.role == "user":
                question = message.text
                continue
            failures = FAILED_TOOL.findall(message.tool_summary or "")
            code = failures[0][1] if failures else None
            knowledge = (
                any(tool.startswith("knowledge") for tool, _ in failures)
                or bool(code and code.startswith("knowledge_"))
                or "knowledge__" in (message.tool_summary or "")
            )
            signal: Signal | None = None
            if message.feedback is not None and message.feedback.rating == "down":
                signal = "rating"
            elif code in EVIDENCE_GAP:
                signal = "evidence_gap"
            elif code or message.status in ("failed", "needs_input"):
                signal = "harness_gave_up"
            if signal is None:
                continue
            found.append(
                ExperienceCase(
                    case_id=_id("conversation", record.session_id, message.message_id, signal),
                    created_at=message.created_at.astimezone(UTC).isoformat(),
                    domain="knowledge" if knowledge else "conversation",
                    signal=signal,
                    subject=_clip(question),
                    answer=_clip(message.text),
                    failure_code=code,
                    rating_note=_clip(message.feedback.note) if message.feedback else None,
                    source=f"conversation:{record.session_id}/{message.message_id}",
                )
            )
    return found


def from_benchmarks(sandbox_root: Path) -> list[ExperienceCase]:
    """Question-set failures and regressions in sandbox benchmarks."""
    found = []
    for path in sorted(sandbox_root.glob("*/.benchmarks/bench-*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sandbox = path.parent.parent.name
        regressions = set(report.get("regressions") or ())
        for result in report.get("results") or ():
            side = result.get("sandbox") or {}
            grade = side.get("grade") or {}
            if grade.get("passed", True):
                continue
            signal: Signal = (
                "regression" if result.get("path") in regressions else "question_set_failure"
            )
            missing = ", ".join(grade.get("missing") or ())
            said = ", ".join(grade.get("forbidden") or ())
            found.append(
                ExperienceCase(
                    case_id=_id(
                        "benchmark", sandbox, report.get("run_id", ""), str(result.get("path"))
                    ),
                    created_at=str(report.get("started_at") or datetime.now(UTC).isoformat()),
                    domain="knowledge",
                    signal=signal,
                    subject=_clip(result.get("question")),
                    answer=_clip(side.get("answer")),
                    failure_code="missing_terms" if missing else "forbidden_terms",
                    rating_note=_clip(f"missing: {missing}; said: {said}"),
                    rule=f"checks/questions/{result.get('path')}",
                    source=f"benchmark:{sandbox}/{report.get('run_id')}",
                )
            )
    return found


def _run_detail(conn: sqlite3.Connection, run_id: str) -> dict[str, str]:
    """The Workflow, and the first step that failed with its tool and code,
    from a run's telemetry events."""
    detail: dict[str, str] = {}
    try:
        rows = conn.execute(
            "SELECT record FROM events WHERE run_id = ? ORDER BY sequence", (run_id,)
        ).fetchall()
    except sqlite3.Error:
        return detail
    for (record,) in rows:
        try:
            attributes = json.loads(record).get("attributes") or {}
        except ValueError:
            continue
        for key in ("workflow_id", "task_id", "skill_id"):
            if attributes.get(key) and key not in detail:
                detail[key] = str(attributes[key])
        if attributes.get("failure_code") and "failure_code" not in detail:
            detail["failure_code"] = str(attributes["failure_code"])
            detail["tool_id"] = str(attributes.get("tool_id") or "")
            if attributes.get("step_index") is not None:
                detail["step_index"] = str(attributes["step_index"])
    return detail


def from_telemetry(path: Path) -> list[ExperienceCase]:
    """Coding and Workflow runs that failed, named by their Workflow and the
    step that failed, so a group is one Workflow failing one way."""
    if not path.is_file():
        return []
    conn = sqlite3.connect(str(path), timeout=10)
    found = []
    try:
        try:
            rows = conn.execute(
                "SELECT run_id, run_kind, started_at, skill_id, summary FROM runs"
                " WHERE run_kind IN ('coding_change', 'workflow_run') AND status = 'failed'"
            ).fetchall()
        except sqlite3.Error:
            rows = []
        for run_id, kind, started, skill, summary in rows:
            try:
                data = json.loads(summary or "{}")
            except ValueError:
                data = {}
            detail = _run_detail(conn, str(run_id))
            code = detail.get("failure_code") or str(data.get("outcome") or "failed")
            name = detail.get("workflow_id") or detail.get("task_id") or skill or kind
            step = (f"step {detail['step_index']} " if "step_index" in detail else "") + detail.get(
                "tool_id", ""
            )
            subject = f"{'Workflow' if kind == 'workflow_run' else 'Coding task'} {name}" + (
                f": {step.strip()} failed ({code})" if step.strip() else f" failed ({code})"
            )
            found.append(
                ExperienceCase(
                    case_id=_id("telemetry", str(run_id)),
                    created_at=str(started or ""),
                    domain="coding" if kind == "coding_change" else "workflow",
                    signal="run_failed",
                    subject=_clip(subject),
                    failure_code=code[:80],
                    # Versions of one Workflow fail for one reason: group without the version.
                    rule=name.split("@")[0] if name != kind else None,
                    source=f"telemetry:{run_id}",
                )
            )
    finally:
        conn.close()
    return found


def group(cases: Iterable[ExperienceCase]) -> dict[str, list[ExperienceCase]]:
    groups: dict[str, list[ExperienceCase]] = {}
    for case in cases:
        groups.setdefault(case.group_key, []).append(case)
    return dict(sorted(groups.items(), key=lambda item: -len(item[1])))
