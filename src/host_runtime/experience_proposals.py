"""Review proposals a person decides on (experience review E3, owner 2026-10-13).

`docs/phases/EXPERIENCE_REVIEW.md` sections 5-6. Every finding with a proposal from a
review becomes one proposal here. A person accepts, rejects (with a reason) or
snoozes it; nothing is changed by the review itself. An accepted proposal is
routed by Agent Web (a review sandbox, the gap list or an issue note) and its
outcome is followed until it is pushed or closed.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from common.base import Contract
from host_runtime.experience import STORE_FILE
from host_runtime.experience_review import REVIEWS_DIR

ProposalStatus = Literal["proposed", "accepted", "rejected", "snoozed", "done"]
Action = Literal["accept", "reject", "snooze", "done", "reopen"]
SNOOZE_DAYS = 7
OUTCOME: dict[Action, ProposalStatus] = {
    "accept": "accepted",
    "reject": "rejected",
    "snooze": "snoozed",
    "done": "done",
    "reopen": "proposed",
}
MAX_REASON = 500


class ProposalError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReviewProposal(Contract):
    proposal_id: str
    review_id: str
    created_at: str
    group: str
    case_ids: tuple[str, ...] = ()
    cause: str | None = None
    diagnosis: str = ""
    kind: Literal["rule_edit", "knowledge_gap", "test_question", "issue"]
    target: str = ""
    text: str = ""
    confidence: str = ""
    confirm: str = ""
    status: ProposalStatus = "proposed"
    reason: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    snooze_until: str | None = None
    # Where an accepted proposal went: "sandbox:<id>", "gap", "issue" or "manual".
    route: str | None = None
    route_note: str = ""


def _now() -> datetime:
    return datetime.now(UTC)


class ProposalStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.path = workspace / STORE_FILE
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS proposals (proposal_id TEXT PRIMARY KEY,"
                " created_at TEXT NOT NULL, record TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path), timeout=10)

    def sync(self) -> int:
        """Add the proposals of every saved review not yet known; returns how many."""
        folder = self.workspace / REVIEWS_DIR
        added = 0
        for path in sorted(folder.glob("review-*.json")) if folder.is_dir() else []:
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for number, finding in enumerate(report.get("findings") or (), 1):
                proposal = finding.get("proposal")
                if finding.get("error") or not isinstance(proposal, dict):
                    continue
                try:
                    record = ReviewProposal(
                        proposal_id=f"{report['review_id']}-{number}",
                        review_id=report["review_id"],
                        created_at=report.get("finished_at") or report.get("started_at") or "",
                        group=str(finding.get("group") or ""),
                        case_ids=tuple(finding.get("case_ids") or ()),
                        cause=finding.get("cause"),
                        diagnosis=str(finding.get("diagnosis") or ""),
                        kind=proposal.get("kind"),
                        target=str(proposal.get("target") or ""),
                        text=str(proposal.get("text") or ""),
                        confidence=str(finding.get("confidence") or ""),
                        confirm=str(finding.get("confirm") or ""),
                    )
                except (KeyError, ValueError):
                    continue
                with self._lock, self._connect() as conn:
                    done = conn.execute(
                        "INSERT OR IGNORE INTO proposals VALUES (?, ?, ?)",
                        (record.proposal_id, record.created_at, record.model_dump_json()),
                    )
                    added += done.rowcount
        return added

    def all(self) -> list[ReviewProposal]:
        """Newest first; a snooze that has run out is shown as proposed again."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT record FROM proposals ORDER BY created_at DESC, proposal_id"
            ).fetchall()
        now = _now().isoformat(timespec="seconds")
        found = []
        for (row,) in rows:
            record = ReviewProposal.model_validate_json(row)
            if record.status == "snoozed" and (record.snooze_until or "") <= now:
                record = record.model_copy(update={"status": "proposed", "snooze_until": None})
            found.append(record)
        return found

    def get(self, proposal_id: str) -> ReviewProposal:
        found = next((p for p in self.all() if p.proposal_id == proposal_id), None)
        if found is None:
            raise ProposalError("unknown_proposal")
        return found

    def save(self, record: ReviewProposal) -> ReviewProposal:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE proposals SET record = ? WHERE proposal_id = ?",
                (record.model_dump_json(), record.proposal_id),
            )
        return record

    def decide(
        self, proposal_id: str, action: Action, actor: str, reason: str | None = None
    ) -> ReviewProposal:
        """A person's decision. Reject needs a reason, so the same cases are not
        proposed again without one on record."""
        record = self.get(proposal_id)
        allowed = {
            "accept": ("proposed", "snoozed"),
            "reject": ("proposed", "snoozed", "accepted"),
            "snooze": ("proposed",),
            "done": ("accepted",),
            "reopen": ("rejected", "done"),
        }
        if record.status not in allowed[action]:
            raise ProposalError("proposal_not_" + "_or_".join(allowed[action]))
        clean = (reason or "").strip()[:MAX_REASON] or None
        if action == "reject" and clean is None:
            raise ProposalError("reason_required")
        now = _now()
        status = OUTCOME[action]
        return self.save(
            record.model_copy(
                update={
                    "status": status,
                    "reason": clean if action != "reopen" else None,
                    "decided_by": actor,
                    "decided_at": now.isoformat(timespec="seconds"),
                    "snooze_until": (now + timedelta(days=SNOOZE_DAYS)).isoformat(
                        timespec="seconds"
                    )
                    if action == "snooze"
                    else None,
                    "route": record.route if action in ("done", "reject") else None,
                }
            )
        )

    def routed(self, proposal_id: str, route: str, note: str = "") -> ReviewProposal:
        return self.save(
            self.get(proposal_id).model_copy(update={"route": route, "route_note": note})
        )
