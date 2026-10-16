"""Review proposals a person decides on (experience review E3, owner 2026-10-13).

`docs/phases/EXPERIENCE_REVIEW.md` sections 5-6. Every finding with a proposal from a
review becomes one proposal here. A person accepts, rejects (with a reason) or
snoozes it; nothing is changed by the review itself. An accepted proposal is
routed by Agent Web (a review sandbox, the gap list or an issue note) and its
outcome is followed until it is pushed or closed.

Suggested Skills (`docs/phases/SKILL_SUGGESTIONS.md` S2): a group the nightly
pass qualifies becomes one `skill_suggestion` proposal for the person whose
requests formed it (`actor`). Each person sees and decides only their own;
rows saved before S2 have no actor and belong to the device owner. A later
pass that adds requests updates the open card instead of making another.
S2 has no draft: a suggestion can be ignored (a reason is optional), snoozed
or reopened, never accepted.
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
from host_runtime.skill_suggestions import SuggestionEvidence, SuggestionItem, SuggestionPass

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
SUGGESTION = "skill_suggestion"
# Quick-pick reasons for ignoring a suggestion; a free text may go with one.
IGNORE_REASONS = {
    "not_useful": "not useful",
    "one_off": "one-off",
    "wrong_grouping": "wrong grouping",
}


class ProposalError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SuggestionCard(Contract):
    """What a Suggested Skill card shows: the group, why, counts and the
    evidence as session and message ids with dates. Excerpts are not kept:
    Agent Web cuts them from the person's conversations when it lists the
    card, so a deleted conversation drops out (S1 decision: no second copy
    of conversation text)."""

    group_id: str
    task: str = ""
    requests: int
    sessions: int
    days: int
    matched_words: tuple[str, ...] = ()
    tool_shape: tuple[str, ...] = ()
    evidence: tuple[SuggestionEvidence, ...] = ()
    sensitivity: str = "normal"
    # Requests that joined after the card was made ("seen N more times").
    seen_more: int = 0
    updated_at: str = ""
    note: str = ""


class ReviewProposal(Contract):
    proposal_id: str
    review_id: str
    created_at: str
    group: str
    case_ids: tuple[str, ...] = ()
    cause: str | None = None
    diagnosis: str = ""
    kind: Literal["rule_edit", "knowledge_gap", "test_question", "issue", "skill_suggestion"]
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
    # Whose proposal this is (S2). None: saved before S2, the device owner's.
    actor: str | None = None
    reason_code: str | None = None
    suggestion: SuggestionCard | None = None


def _now() -> datetime:
    return datetime.now(UTC)


class ProposalStore:
    """`owner` is the device owner: the person a row without an actor (made
    before S2, or by the failure review) belongs to. Without an owner such
    rows are visible to anybody, as before S2."""

    def __init__(self, workspace: Path, owner: str | None = None) -> None:
        self.workspace = workspace
        self.owner = owner
        self.path = workspace / STORE_FILE
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS proposals (proposal_id TEXT PRIMARY KEY,"
                " created_at TEXT NOT NULL, record TEXT NOT NULL)"
            )
            # S2 migration: an additive, nullable actor column. Old rows keep
            # NULL (the device owner's) and their records are untouched.
            columns = {row[1] for row in conn.execute("PRAGMA table_info(proposals)")}
            if "actor" not in columns:
                conn.execute("ALTER TABLE proposals ADD COLUMN actor TEXT")

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
                if record.kind == SUGGESTION:
                    continue  # suggestion cards are made by `suggest` only
                added += self._insert(record)
        return added

    def _insert(self, record: ReviewProposal) -> int:
        with self._lock, self._connect() as conn:
            done = conn.execute(
                "INSERT OR IGNORE INTO proposals (proposal_id, created_at, record, actor)"
                " VALUES (?, ?, ?, ?)",
                (record.proposal_id, record.created_at, record.model_dump_json(), record.actor),
            )
            return int(done.rowcount)

    def visible(self, record: ReviewProposal, actor: str | None) -> bool:
        """Whether `actor` may see and decide this proposal. None: no filter
        (the store's own maintenance)."""
        if actor is None:
            return True
        owner = record.actor or self.owner
        return owner is None or owner == actor

    def all(self, actor: str | None = None) -> list[ReviewProposal]:
        """Newest first; a snooze that has run out is shown as proposed again.
        With an actor, only what that person may see."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT record FROM proposals ORDER BY created_at DESC, proposal_id"
            ).fetchall()
        now = _now().isoformat(timespec="seconds")
        found = []
        for (row,) in rows:
            record = ReviewProposal.model_validate_json(row)
            if not self.visible(record, actor):
                continue
            if record.status == "snoozed" and (record.snooze_until or "") <= now:
                record = record.model_copy(update={"status": "proposed", "snooze_until": None})
            found.append(record)
        return found

    def get(self, proposal_id: str, actor: str | None = None) -> ReviewProposal:
        """Another person's proposal is answered exactly like a missing one."""
        found = next((p for p in self.all(actor) if p.proposal_id == proposal_id), None)
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
        self,
        proposal_id: str,
        action: Action,
        actor: str,
        reason: str | None = None,
        reason_code: str | None = None,
    ) -> ReviewProposal:
        """A person's decision. Reject needs a reason, so the same cases are not
        proposed again without one on record; ignoring a Skill suggestion does
        not (a quick-pick reason and a free text are both optional). Only the
        person's own proposal can be decided."""
        record = self.get(proposal_id, actor)
        suggestion = record.kind == SUGGESTION
        if suggestion and action in ("accept", "done"):
            raise ProposalError("suggestion_has_no_draft_yet")
        if reason_code is not None and (
            not suggestion or action != "reject" or reason_code not in IGNORE_REASONS
        ):
            raise ProposalError("unknown_reason_code")
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
        if action == "reject" and clean is None and not suggestion:
            raise ProposalError("reason_required")
        now = _now()
        status = OUTCOME[action]
        return self.save(
            record.model_copy(
                update={
                    "status": status,
                    "reason": clean if action != "reopen" else None,
                    "reason_code": reason_code if action == "reject" else None,
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

    # -- Suggested Skills (S2) ----------------------------------------------------

    def suggestion_cards(self, actor: str, group_id: str) -> list[ReviewProposal]:
        """The actor's cards for one group, newest first."""
        return [
            p
            for p in self.all(actor)
            if p.kind == SUGGESTION
            and p.actor == actor
            and p.suggestion is not None
            and p.suggestion.group_id == group_id
        ]

    def suggest(
        self, actor: str, item: SuggestionItem, *, review_id: str, sensitivity: str, at: str
    ) -> tuple[str | None, str]:
        """Make or update the card for one item of a nightly pass; returns the
        card id and what happened. Never two open cards for one group: new
        evidence joining an open card updates it ("seen N more times")."""
        cards = self.suggestion_cards(actor, item.group_id)
        open_card = next((c for c in cards if c.status in ("proposed", "snoozed")), None)
        if item.status == "updated" or (item.status == "qualified" and open_card is not None):
            if open_card is None or open_card.suggestion is None:
                return None, "no open card to update"
            before = open_card.suggestion
            added = max(0, item.requests - before.requests)
            if added == 0:
                return open_card.proposal_id, "card unchanged"
            self.save(
                open_card.model_copy(
                    update={
                        "suggestion": self._card(item, sensitivity, at).model_copy(
                            update={"seen_more": before.seen_more + added, "note": before.note}
                        )
                    }
                )
            )
            return open_card.proposal_id, f"card updated: seen {added} more times"
        if item.status != "qualified":
            return None, ""
        number = len(cards) + 1
        proposal_id = f"suggest-{item.group_id}" + (f"-{number}" if number > 1 else "")
        record = ReviewProposal(
            proposal_id=proposal_id,
            review_id=review_id,
            created_at=at,
            group=item.group_id,
            diagnosis=item.reason,
            kind=SUGGESTION,
            target=item.task,
            text=item.task,
            actor=actor,
            suggestion=self._card(item, sensitivity, at).model_copy(update={"note": item.reason}),
        )
        if not self._insert(record):
            return proposal_id, "card already exists"
        return proposal_id, "card created" + (" again after it was ignored" if number > 1 else "")

    @staticmethod
    def _card(item: SuggestionItem, sensitivity: str, at: str) -> SuggestionCard:
        return SuggestionCard(
            group_id=item.group_id,
            task=item.task,
            requests=item.requests,
            sessions=item.sessions,
            days=item.days,
            matched_words=item.matched_words,
            tool_shape=item.tool_shape,
            evidence=tuple(e.model_copy(update={"excerpt": ""}) for e in item.evidence),
            sensitivity=sensitivity,
            updated_at=at,
        )

    def routed(self, proposal_id: str, route: str, note: str = "") -> ReviewProposal:
        return self.save(
            self.get(proposal_id).model_copy(update={"route": route, "route_note": note})
        )


def make_cards(store: ProposalStore, found: SuggestionPass) -> SuggestionPass:
    """The pass's qualified groups become cards and grown ones update theirs;
    the returned pass names each item's card for the nightly report. A dry
    run or a pass that is off makes nothing."""
    counts = found.counts
    if counts.dry_run or not counts.enabled:
        return found
    at = _now().isoformat(timespec="seconds")
    items = []
    created = updated = 0
    for item in found.suggestions:
        if item.status not in ("qualified", "updated"):
            items.append(item)
            continue
        card, note = store.suggest(
            counts.actor, item, review_id=counts.pass_id, sensitivity=counts.sensitivity, at=at
        )
        created += note.startswith("card created")
        updated += note.startswith("card updated")
        items.append(item.model_copy(update={"card": card, "card_note": note}))
    return SuggestionPass(
        counts=counts.model_copy(update={"cards_created": created, "cards_updated": updated}),
        suggestions=tuple(items),
    )
