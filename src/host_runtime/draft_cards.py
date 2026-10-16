"""The install card a conversation shows after it drafted a Workflow or Skill.

Owner request 2026-10-16: whenever a Workflow or Skill draft is created or
revised as part of a conversation, whatever backend answered (the Gateway's
own authoring tools, the coding Skill, Claude Code or Copilot in agent mode
through the authoring MCP), that conversation shows a card right after the
turn: what the draft is and does, its steps and the form its parameters
become, the check result, and **Install** (the owner's press is the
approval; the existing install path runs), **Run once to try** (read-only
Workflows only, the existing test-run path) and **Not now** (the draft stays
in Capabilities). The model never presses it; nothing installs by itself.

A card is one `DraftCard` record (`dr-` ids) in `CardStore`; it is drawn with
the shared `ActionCard`. One open card per draft and conversation: a newer
revision closes the earlier card as "Replaced" and shows a new one under the
newer answer. Drafts with no conversation (an external agent outside Agent
Web) get no card; they wait in Capabilities as before.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from common.action_cards import ActionCard, CardButton, CardLink
from common.assets import WorkflowManifest, WorkflowStep
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters
from host_runtime.card_store import CardStore, PendingRecord, new_card_id
from host_runtime.chat_authoring import (
    ChatAuthoring,
    ChatAuthoringError,
    ChatCandidate,
    digest,
    run_codes,
)
from host_runtime.skill_authoring import SkillCandidate, skill_digest

CARDS_FILE = Path("authoring") / "draft-cards.json"
PREFIX = "dr"
KIND = "draft_install"
#: A card that waits this long is still answerable; the draft never expires.
OPEN_DAYS = 30
MAX_PREVIEW_STEPS = 12
MAX_FIELDS = 16

AGENT_LABELS = {
    "conversation": "this conversation",
    "external:claude-code": "Claude Code",
    "external:copilot": "GitHub Copilot",
    "external:codex": "Codex",
}

STATUS_LABELS = {
    "pending": "Waiting for you",
    "installed": "Installed",
    "not_now": "Not now",
    "superseded": "Replaced",
    "stale": "Out of date",
    "failed": "Not installed",
    "expired": "Expired",
}


class DraftCard(PendingRecord):
    """One draft shown in one conversation, as it was when the turn ended."""

    session_id: str
    candidate_id: str
    asset: Literal["workflow", "skill"]
    revision: int
    digest: str
    name: str
    title: str
    channel: str = "local"
    source: str = "conversation"
    read_only: bool = False
    tryable: bool = False
    tried: str = ""
    tried_ok: bool | None = None
    approval_id: str = ""
    # The agent's install request this card answers, when it asked.
    asked_by: str = ""
    outcome: str = ""
    outcome_ok: bool | None = None


def _stamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _key(identity: Any) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


def tryable(manifest: WorkflowManifest) -> bool:
    """A test run needs no values: every required run field has a default."""
    return all(
        not parameter.required or parameter.default is not None
        for parameter in manifest.parameters
        if parameter.scope == "runtime"
    )


def _defaults(manifest: WorkflowManifest) -> dict[str, Any]:
    return {
        parameter.name: parameter.default
        for parameter in manifest.parameters
        if parameter.scope == "runtime" and parameter.default is not None
    }


class DraftCards:
    """Install cards for drafts a conversation made (owner 2026-10-16)."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        chat: Callable[[], ChatAuthoring | None],
        actor: Callable[[], str],
        form_offer: Callable[[WorkflowManifest], dict[str, Any] | None] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._chat = chat
        self._actor = actor
        self.form_offer = form_offer
        self.store: CardStore[DraftCard] = CardStore(
            workspace_root / CARDS_FILE, DraftCard, keep=400, clock=clock
        )

    # -- after a turn ---------------------------------------------------------

    def carded(self, session_id: str) -> set[str]:
        """Drafts this conversation shows a card for: their install requests
        are answered on the card, not with a second approval card."""
        return {
            record.candidate_id
            for record in self.store.records()
            if record.session_id == session_id
        }

    def _touched(
        self, chat: ChatAuthoring, actor: str, session_id: str, since: datetime
    ) -> list[tuple[ChatCandidate | SkillCandidate, str]]:
        """Drafts of this conversation created or revised since the turn
        began, or whose installation the agent asked for in it (with that
        request). Stored times have whole seconds, so a draft or request
        already carded at this revision is not carded again."""
        start = since.astimezone(UTC).replace(microsecond=0)
        records = [r for r in self.store.records() if r.session_id == session_id]
        answered = {r.asked_by for r in records if r.asked_by}
        asked = {
            item.candidate_id: item.approval_id
            for item in chat.approvals(actor, session_id=session_id)
            if item.kind in ("install", "install_skill")
            and (_stamp(item.created_at) or start) >= start
            and item.approval_id not in answered
        }
        shown = {(r.candidate_id, r.revision) for r in records}
        found: list[tuple[ChatCandidate | SkillCandidate, str]] = []
        workflows: list[ChatCandidate | SkillCandidate] = list(chat.candidates(actor))
        skills: list[ChatCandidate | SkillCandidate] = (
            list(chat.skill_candidates(actor)) if chat.skills_dir is not None else []
        )
        for item in workflows + skills:
            if item.session_id != session_id or item.status == "installed":
                continue
            request = asked.get(item.candidate_id, "")
            changed = _stamp(item.updated_at)
            fresh = changed is not None and changed >= start
            if request or (fresh and (item.candidate_id, item.revision) not in shown):
                found.append((item, request))
        return found

    def for_turn(
        self, session_id: str, since: datetime, channel: str = "local", message: str = ""
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """The cards to show under this turn's answer, and the earlier cards
        they replace (redrawn closed where they are)."""
        chat = self._chat()
        if chat is None or not session_id:
            return [], []
        actor = self._actor()
        try:
            touched = self._touched(chat, actor, session_id, since)
        except (OSError, ValueError):
            return [], []
        shown: list[dict[str, Any]] = []
        replaced: list[dict[str, Any]] = []
        now = self.store.now()
        with self.store.lock:
            for item, request in touched:
                for old in self.store.records():
                    if (
                        old.session_id == session_id
                        and old.candidate_id == item.candidate_id
                        and old.status == "pending"
                    ):
                        closed = self.store.put(
                            old.model_copy(
                                update={
                                    "status": "superseded",
                                    "decided_at": now,
                                    "outcome": "A newer revision is shown further down.",
                                }
                            )
                        )
                        replaced.append(self.draw(closed).model_dump(mode="json"))
                record = self._record(chat, item, session_id, channel, now)
                self.store.put(record.model_copy(update={"asked_by": request}))
                shown.append(self.draw(record, message).model_dump(mode="json"))
        return shown, replaced

    def _record(
        self,
        chat: ChatAuthoring,
        item: ChatCandidate | SkillCandidate,
        session_id: str,
        channel: str,
        now: datetime,
    ) -> DraftCard:
        common = {
            "card_id": new_card_id(PREFIX),
            "created_at": now,
            "expires_at": now + timedelta(days=OPEN_DAYS),
            "session_id": session_id,
            "candidate_id": item.candidate_id,
            "revision": item.revision,
            "name": _key(item.draft.metadata.identity),
            "title": item.title[:120],
            "channel": channel,
            "source": item.source,
        }
        if isinstance(item, ChatCandidate):
            read_only = chat.read_only(item.draft)
            return DraftCard(
                **common,
                asset="workflow",
                digest=digest(item.draft),
                read_only=read_only,
                tryable=read_only and tryable(item.draft),
            )
        return DraftCard(**common, asset="skill", digest=skill_digest(item.draft))

    # -- the picture ------------------------------------------------------------

    def _candidate(
        self, chat: ChatAuthoring, record: DraftCard
    ) -> ChatCandidate | SkillCandidate | None:
        try:
            if record.asset == "skill":
                return chat.skill_candidate(record.candidate_id, self._actor())
            return chat.candidate(record.candidate_id, self._actor())
        except (ChatAuthoringError, OSError, ValueError):
            return None

    def _workflow_preview(self, chat: ChatAuthoring, draft: WorkflowManifest) -> list[str]:
        lines = [f"What it does: {draft.description}", "Steps:"]
        for index, step in enumerate(draft.steps[:MAX_PREVIEW_STEPS], start=1):
            if not isinstance(step, WorkflowStep):
                lines.append(f"  {index}. (nested Workflow)")
                continue
            binding = chat.installed.get(step.capability)
            effect = binding.spec.side_effect if binding is not None else "not installed"
            lines.append(f"  {index}. {_key(step.capability)} ({effect})")
        if len(draft.steps) > MAX_PREVIEW_STEPS:
            lines.append(f"  … and {len(draft.steps) - MAX_PREVIEW_STEPS} more")
        runtime = [p for p in draft.parameters if p.scope == "runtime"]
        settings = [p for p in draft.parameters if p.scope == "static"]
        if runtime:
            fields = ", ".join(
                f"{p.label} ({p.kind}{', required' if p.required else ''})"
                for p in runtime[:MAX_FIELDS]
            )
            lines.append(f"Parameters: {', '.join(p.name for p in runtime[:MAX_FIELDS])}")
            lines.append(f"Will become a form with fields: {fields}")
        else:
            lines.append("Parameters: none (it runs without asking anything)")
        if settings:
            lines.append(
                "Settings, set once on this PC: "
                + ", ".join(p.label for p in settings[:MAX_FIELDS])
            )
        return lines

    def draw(self, record: DraftCard, message: str = "") -> ActionCard:
        chat = self._chat()
        item = self._candidate(chat, record) if chat is not None else None
        word = "Workflow" if record.asset == "workflow" else "Skill"
        who = AGENT_LABELS.get(record.source, record.source.removeprefix("external:"))
        lines = [f"{record.name} · revision {record.revision} · drafted by {who}"]
        if chat is not None and isinstance(item, ChatCandidate):
            lines.extend(self._workflow_preview(chat, item.draft))
        elif isinstance(item, SkillCandidate):
            draft = item.draft
            about = draft.selector_hint or draft.instructions.strip().splitlines()[0][:300]
            lines.append(f"What it does: {about}")
            lines.append(f"Alias: /{draft.alias}")
            commands = [f"  {c.name} → {_key(c.target)}" for c in draft.commands]
            lines.extend(["Commands:", *commands] if commands else ["Commands: none"])
        lines.append("Check: passed (what the Host checks before it keeps a draft).")
        if record.tried:
            lines.append(f"Test run: {record.tried}")
        effects: list[str] = []
        if record.asset == "skill":
            effects.append("A new Skill is used after Agent Web restarts.")
        elif not record.read_only:
            effects.append("Its steps change things; each run after installing is yours to start.")
        pending = record.status == "pending"
        buttons: list[CardButton] = []
        if pending:
            buttons.append(CardButton(action="install", label="Install", style="primary"))
            if record.tryable and record.channel != "telegram":
                buttons.append(CardButton(action="try", label="Run once to try"))
            buttons.append(CardButton(action="not_now", label="Not now"))
        label = STATUS_LABELS.get(record.status, record.status)
        if pending and record.tried:
            label = f"Test run {'succeeded' if record.tried_ok else 'did not succeed'}"
        link = None
        if record.status == "installed":
            link = CardLink(
                label="Open in Capabilities",
                view="installed",
                capability_kind="workflows" if record.asset == "workflow" else "skills",
                asset=record.name,
            )
        elif record.status == "not_now":
            link = CardLink(label="Open Capabilities", view="installed")
        return ActionCard(
            card_id=record.card_id,
            kind=KIND,
            title=f"Install the {word} “{record.title}”?"[:160]
            if pending
            else f"{word} “{record.title}”"[:160],
            preview="\n".join(lines)[:20_000],
            effects=tuple(effects),
            buttons=tuple(buttons),
            status=record.status,
            status_label=label,
            outcome=record.outcome[:2_000],
            outcome_ok=record.outcome_ok,
            link=link,
            message=(message or f"A {word} draft is ready: {record.title}")[:600],
        )

    def card(self, card_id: str) -> dict[str, Any] | None:
        record = self.store.get(card_id)
        return None if record is None else self.draw(record).model_dump(mode="json")

    def open_cards(self, session_id: str | None = None) -> list[ActionCard]:
        return [
            self.draw(record)
            for record in self.store.records()
            if record.status == "pending" and session_id in (None, record.session_id)
        ]

    # -- the person's press -----------------------------------------------------

    def decide(self, card_id: str, action: str, *, channel: str = "local") -> dict[str, Any]:
        """Install, try or set aside. Returns `ok`, `code`, `message`, `card`
        and, after a Workflow is installed, its run form (`workflow_form`)."""
        with self.store.lock:
            record = self.store.get(card_id)
            if record is None:
                return {"ok": False, "code": "card_unknown", "message": "That card is unknown."}
            if action not in ("install", "try", "not_now"):
                return self._reply(record, False, "card_action_unknown", "Unknown button.")
            if record.status != "pending":
                return self._reply(
                    record, False, f"draft_{record.status}", "This card was already answered."
                )
            if self.store.expired(record):
                record = self._close(record, "expired", "Ask the Agent again.", None)
                return self._reply(record, False, "draft_expired", record.outcome)
            chat = self._chat()
            item = self._candidate(chat, record) if chat is not None else None
            if chat is None or item is None:
                record = self._close(
                    record, "stale", "The draft is gone (deleted in Capabilities).", False
                )
                return self._reply(record, False, "draft_stale", record.outcome)
            current = digest(item.draft) if isinstance(item, ChatCandidate) else None
            if isinstance(item, SkillCandidate):
                current = skill_digest(item.draft)
            if item.status == "installed" or current != record.digest:
                note = (
                    "Already installed."
                    if item.status == "installed"
                    else "The draft changed after this card; use the newer card."
                )
                record = self._close(record, "stale", note, item.status == "installed")
                return self._reply(record, False, "draft_stale", note)
            if action == "not_now":
                record = self._close(
                    record,
                    "not_now",
                    "Kept as a draft in Capabilities; install it there any time.",
                    None,
                )
                return self._reply(record, True, "not_now", record.outcome)
            if action == "try":
                return self._try(chat, record, item, channel)
            return self._install(chat, record)

    def _close(self, record: DraftCard, status: str, outcome: str, ok: bool | None) -> DraftCard:
        return self.store.put(
            record.model_copy(
                update={
                    "status": status,
                    "decided_at": self.store.now(),
                    "outcome": outcome,
                    "outcome_ok": ok,
                }
            )
        )

    def _reply(
        self, record: DraftCard, ok: bool, code: str, message: str, **extra: Any
    ) -> dict[str, Any]:
        return {
            "ok": ok,
            "code": code,
            "message": message,
            "card": self.draw(record).model_dump(mode="json"),
            "session_id": record.session_id,
            **extra,
        }

    def _try(
        self,
        chat: ChatAuthoring,
        record: DraftCard,
        item: ChatCandidate | SkillCandidate,
        channel: str,
    ) -> dict[str, Any]:
        if not isinstance(item, ChatCandidate) or not record.tryable or channel == "telegram":
            return self._reply(
                record, False, "try_unavailable", "Only a read-only Workflow can be tried here."
            )
        values = _defaults(item.draft)
        try:
            validate_run_parameters(item.draft, values)
        except WorkflowParameterError:
            return self._reply(
                record,
                False,
                "try_needs_values",
                "It needs run values: install it to get its form.",
            )
        try:
            result = chat.execute(self._actor(), item, values, f"card-try:{record.card_id}")
        except (TimeoutError, ChatAuthoringError, OSError) as error:
            result = {"status": "failed", "failure": {"code": getattr(error, "code", "failed")}}
        # Statuses and codes only: the card's outcome joins the conversation
        # history a coding agent reads (PUBLIC rule for external agents).
        codes = run_codes(result)
        steps = codes.get("steps")
        listed = steps if isinstance(steps, list) else []
        done = sum(
            1 for step in listed if isinstance(step, dict) and step.get("status") == "succeeded"
        )
        ok = codes.get("status") == "succeeded"
        summary = f"{codes.get('status')}, {done} of {len(listed)} steps succeeded"
        if codes.get("failure"):
            summary += f" ({codes['failure']})"
        record = self.store.put(record.model_copy(update={"tried": summary, "tried_ok": ok}))
        return self._reply(record, ok, "tried", f"Test run {summary}.")

    def _install(self, chat: ChatAuthoring, record: DraftCard) -> dict[str, Any]:
        """The existing install path: the agent's own pending request when it
        asked (so its status reads approved), else a new one; the press is
        the approval either way."""
        actor = self._actor()
        kind = "install_skill" if record.asset == "skill" else "install"
        asked = [
            item
            for item in chat.approvals(actor)
            if item.candidate_id == record.candidate_id
            and item.kind == kind
            and item.digest == record.digest
        ]
        try:
            if asked:
                decided = chat.decide(asked[-1].approval_id, actor, True)
            else:
                decided = chat.install_now(actor, record.candidate_id)
        except ChatAuthoringError as error:
            record = self._close(record, "failed", f"Not installed ({error.code}).", False)
            return self._reply(record, False, error.code, record.outcome)
        result = decided.result if isinstance(decided.result, dict) else {}
        if decided.status != "approved":
            failure = str(result.get("failure") or decided.status)
            record = self._close(record, "failed", f"Not installed ({failure}).", False)
            return self._reply(record, False, "install_failed", record.outcome)
        if record.asset == "workflow":
            note = (
                f"{result.get('installed_as')} is installed. Run it from the form below, "
                "from Capabilities or by asking in any chat."
            )
        else:
            note = (
                f"{result.get('installed_as')} is installed; it is used after Agent Web restarts."
            )
        record = self.store.put(
            record.model_copy(
                update={
                    "status": "installed",
                    "decided_at": self.store.now(),
                    "outcome": note,
                    "outcome_ok": True,
                    "approval_id": decided.approval_id,
                }
            )
        )
        form = None
        if record.asset == "workflow" and self.form_offer is not None:
            candidate = self._candidate(chat, record)
            if isinstance(candidate, ChatCandidate):
                form = self.form_offer(candidate.draft)
        return self._reply(
            record, True, "installed", note, **({"workflow_form": form} if form else {})
        )
