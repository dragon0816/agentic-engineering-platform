"""Email tools use the signed-in IT/service identity without AEP approval cards.

Search filters are query defaults, not access policy. Draft and send are distinct
actions. Historical card APIs remain readable; normal tools do not create cards.
Credential-shaped text is redacted and bounded reads expose continuation metadata."""

from __future__ import annotations

import html
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from common.action_cards import ActionCard, CardButton
from common.agent_guard import resolved
from common.assets import SECRET_PATTERN
from host_runtime.agent_mode import AgentMode, AgentRun
from host_runtime.card_store import CardStore, PendingRecord
from integrations.outlook_draft import DraftError, DraftWriter, MailDraft, recipients
from integrations.outlook_mail import (
    MailError,
    MailReader,
    MailScope,
    read,
    safe_file_name,
    search,
)
from integrations.outlook_send import DraftSender, SendError, draft_fingerprint

CARD_PREFIX = "ml"
CARDS_FILE = "agent-mode/mail-cards.json"
ATTACHMENTS_DIR = "mail-attachments"
STATUS_LABELS = {
    "pending": "Waiting for your answer",
    "sent": "Sent",
    "kept": "Kept as a draft in Outlook",
    "cancelled": "Cancelled: the draft was deleted",
    "expired": "No answer in 10 minutes: kept as a draft",
    "failed": "Not sent",
}
SEND_FAILURES = {
    "draft_changed": "The draft was changed in Outlook after this card was shown; nothing "
    "was sent. Review it in Outlook and send it there.",
    "draft_unknown": "The draft is no longer in Outlook; nothing was sent.",
    "send_failed": "Outlook did not send it; the draft is still in Drafts.",
    "library_missing": "Outlook cannot be reached from AEP on this computer.",
    "outlook_missing": "Outlook is not installed on this computer.",
}


class MailCard(PendingRecord):
    session_id: str
    run_id: str = ""
    entry_id: str
    fingerprint: str
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str = ""
    body: str = ""
    attachments: tuple[str, ...] = ()
    task_id: str = ""
    outcome: str = ""
    outcome_ok: bool | None = None
    channel: str = ""


def scope_text(scope: MailScope) -> str:
    lines = [
        f"Folders: {', '.join(scope.folders) or '(none)'}",
        f"Up to {scope.max_days} days back",
    ]
    if scope.excluded_folders:
        lines.append("Never these folders: " + ", ".join(scope.excluded_folders))
    if scope.excluded_senders:
        lines.append("Never mail from: " + ", ".join(scope.excluded_senders))
    lines.append("Read only: nothing is moved, marked, deleted or sent.")
    return "\n".join(lines)


def scrub(text: str) -> str:
    return SECRET_PATTERN.sub("[redacted]", text)


class AgentMail:
    def __init__(
        self,
        mode: AgentMode,
        *,
        reader: Callable[[], MailReader],
        writer: Callable[[], DraftWriter],
        sender: Callable[[], DraftSender],
    ) -> None:
        self.mode = mode
        self._reader = reader
        self._writer = writer
        self._sender = sender
        self.cards = CardStore(
            mode.workspace_root / CARDS_FILE, MailCard, keep=200, clock=mode.cards.clock
        )
        self._events: dict[str, threading.Event] = {}

    def scope(self) -> MailScope:
        return self.mode.store.load().mail

    # -- reading -------------------------------------------------------------

    def _may_read(self, run: AgentRun) -> tuple[bool, str]:
        return self.mode.mail_read_card(run, scope_text(self.scope()))

    def search(self, run: AgentRun, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed, message = self._may_read(run)
        if not allowed:
            return {"ok": False, "code": "not_allowed", "message": message}
        days = arguments.get("days")
        try:
            found = search(
                self._reader(),
                self.scope(),
                query=str(arguments.get("query") or ""),
                sender=str(arguments.get("sender") or ""),
                folder=str(arguments.get("folder") or ""),
                days=int(days) if isinstance(days, int) else None,
                limit=int(arguments.get("limit") or 20),
            )
        except MailError as error:
            return {"ok": False, "code": error.code}
        self.mode.audit(
            {
                "session": run.session_id,
                "run": run.run_id,
                "tool": "outlook.search",
                "decision": "free",
                "found": len(found),
            }
        )
        run.free.append(f"outlook.search ({len(found)})")
        return {
            "ok": True,
            "complete": False,
            "note": "Bounded results; refine folder/date/query before claiming full coverage.",
            "messages": [
                {
                    **item.model_dump(mode="json"),
                    "subject": scrub(item.subject),
                    "snippet": scrub(item.snippet),
                }
                for item in found
            ],
        }

    def read(self, run: AgentRun, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed, message = self._may_read(run)
        if not allowed:
            return {"ok": False, "code": "not_allowed", "message": message}
        message_id = str(arguments.get("message_id") or "")
        reader = self._reader()
        try:
            found = read(
                reader,
                self.scope(),
                message_id,
                body_offset=int(arguments.get("body_offset") or 0),
                body_limit=int(arguments.get("body_limit") or 20000),
            )
        except MailError as error:
            return {"ok": False, "code": error.code}
        saved: list[str] = []
        if arguments.get("save_attachments") and found.attachments:
            target = run.folder / ATTACHMENTS_DIR
            for name in found.attachments:
                path = target / safe_file_name(name)
                stem, suffix, count = path.stem, path.suffix, 1
                while path.exists():
                    count += 1
                    path = target / f"{stem}-{count}{suffix}"
                try:
                    saved.append(str(reader.save_attachment(message_id, name, path)))
                except MailError as error:
                    return {"ok": False, "code": error.code}
        self.mode.audit(
            {
                "session": run.session_id,
                "run": run.run_id,
                "tool": "outlook.read",
                "decision": "free",
                "attachments_saved": len(saved),
            }
        )
        run.free.append("outlook.read")
        data = found.model_dump(mode="json")
        data.update(
            subject=scrub(found.subject), body=scrub(found.body), snippet=scrub(found.snippet)
        )
        return {"ok": True, "message": data, "saved_attachments": saved}

    # -- sending -------------------------------------------------------------

    def draft(self, run: AgentRun, arguments: dict[str, Any]) -> dict[str, Any]:
        """Save a draft; sending is a distinct explicit action."""
        to = recipients([str(item) for item in arguments.get("to") or []])
        cc = recipients([str(item) for item in arguments.get("cc") or []])
        subject = str(arguments.get("subject") or "").strip()
        body = str(arguments.get("body") or "")
        if not to:
            return {"ok": False, "code": "draft_recipient_missing"}
        if not subject or not body.strip():
            return {"ok": False, "code": "draft_content_missing"}
        if SECRET_PATTERN.search(f"{subject}\n{body}"):
            return {
                "ok": False,
                "code": "credential_refused",
                "message": "A mail carrying a credential is never written through the agent.",
            }
        files: list[Path] = []
        for item in arguments.get("attachments") or []:
            path = resolved(str(item), run.folder)
            if not path.is_file():
                return {
                    "ok": False,
                    "code": "attachment_missing",
                    "message": "The attachment is not an existing file.",
                }
            files.append(path)
        markup = "<p>" + html.escape(body).replace("\n", "<br>") + "</p>"
        try:
            receipt = self._writer().save(
                MailDraft(
                    subject=subject,
                    html_body=markup,
                    to=to,
                    cc=cc,
                    attachments=tuple(str(path) for path in files),
                )
            )
        except DraftError as error:
            return {"ok": False, "code": error.code}
        names = tuple(path.name for path in files)
        run.free.append("outlook.draft")
        return {
            "ok": bool(receipt.saved),
            "status": "drafted" if receipt.saved else "draft_failed",
            "entry_id": receipt.entry_id,
            "fingerprint": draft_fingerprint(to, cc, subject, names),
            "sent": False,
        }

    def send(self, run: AgentRun, arguments: dict[str, Any]) -> dict[str, Any]:
        """An explicit send request uses the draft receipt, without a new card."""
        from pydantic import ValidationError

        from capabilities.mail_send.handlers import MailSendRequest

        try:
            request = MailSendRequest.model_validate(arguments)
        except ValidationError:
            return {"ok": False, "code": "invalid_input"}
        try:
            self._sender().send(request.entry_id, request.fingerprint)
        except SendError as error:
            return {"ok": False, "code": error.code, "sent": False}
        run.free.append("outlook.send")
        return {"ok": True, "sent": True, "entry_id": request.entry_id}

    # -- cards ---------------------------------------------------------------

    def _settle(
        self, record: MailCard, status: str, outcome: str, ok: bool | None, channel: str = ""
    ) -> MailCard:
        settled = record.model_copy(
            update={
                "status": status,
                "outcome": outcome[:2_000],
                "outcome_ok": ok,
                "decided_at": self.cards.now(),
                "channel": channel,
            }
        )
        self.cards.put(settled)
        if record.task_id:
            self.mode.tasks().finish(
                record.task_id,
                {"sent": "succeeded", "failed": "failed"}.get(status, "stopped"),
                f"{STATUS_LABELS.get(status, status)}: to " + ", ".join(record.to)[:200],
            )
        self.mode.audit(
            {
                "session": record.session_id,
                "run": record.run_id,
                "card": record.card_id,
                "decision": status,
                "channel": channel,
            }
        )
        event = self._events.get(record.card_id)
        if event is not None:
            event.set()
        return settled

    def _current(self, card_id: str) -> MailCard | None:
        record = self.cards.get(card_id)
        if (
            record is not None
            and record.status == "pending"
            and (self.cards.expired(record) or record.card_id not in self._events)
        ):
            record = self._settle(record, "expired", "Kept as a draft in Outlook.", None)
        return record

    def card(self, card_id: str) -> ActionCard | None:
        with self.cards.lock:
            record = self._current(card_id)
        return None if record is None else draw(record)

    def record(self, card_id: str) -> MailCard | None:
        return self.cards.get(card_id)

    def open_cards(self, session_id: str | None = None) -> list[ActionCard]:
        with self.cards.lock:
            found = [
                self._current(item.card_id)
                for item in self.cards.records()
                if item.status == "pending"
                and (session_id is None or item.session_id == session_id)
            ]
        return [draw(item) for item in found if item is not None and item.status == "pending"]

    def decide(self, card_id: str, action: str, *, channel: str = "local") -> dict[str, Any]:
        """Send, Keep as draft or Cancel: the only way a mail leaves through AEP."""
        if channel == "telegram":
            card = self.card(card_id)
            return {
                "ok": False,
                "code": "web_only",
                "message": "Mail cards are answered in Agent Web only.",
                **({"card": card.model_dump(mode="json")} if card else {}),
            }
        with self.cards.lock:
            record = self._current(card_id)
            if record is None:
                return {
                    "ok": False,
                    "code": "card_unknown",
                    "message": "That card is unknown here.",
                }
            if record.status != "pending":
                return {
                    "ok": False,
                    "code": f"mail_{record.status}",
                    "message": STATUS_LABELS.get(record.status, record.status),
                    "card": draw(record).model_dump(mode="json"),
                }
            if action == "keep_draft":
                record = self._settle(record, "kept", "Kept as a draft in Outlook.", None, channel)
            elif action == "cancel":
                try:
                    self._sender().discard(record.entry_id)
                    record = self._settle(
                        record, "cancelled", "The draft was deleted.", None, channel
                    )
                except SendError as error:
                    record = self._settle(
                        record,
                        "kept",
                        "Cancelled; the draft could not be "
                        f"deleted ({error.code}) and stays in Drafts.",
                        None,
                        channel,
                    )
            elif action == "send":
                try:
                    self._sender().send(record.entry_id, record.fingerprint)
                except SendError as error:
                    record = self._settle(
                        record, "failed", SEND_FAILURES.get(error.code, error.code), False, channel
                    )
                else:
                    record = self._settle(record, "sent", "Sent from your Outlook.", True, channel)
            else:
                return {
                    "ok": False,
                    "code": "card_action_unknown",
                    "message": "The card has Send, Keep as draft and Cancel.",
                }
        return {
            "ok": record.status == "sent" or record.status in ("kept", "cancelled"),
            "code": record.status,
            "message": record.outcome,
            "card": draw(record).model_dump(mode="json"),
        }


def draw(record: MailCard) -> ActionCard:
    lines = [f"To: {', '.join(record.to)}"]
    if record.cc:
        lines.append(f"Cc: {', '.join(record.cc)}")
    lines.append(f"Subject: {record.subject}")
    if record.attachments:
        lines.append("Attachments: " + ", ".join(record.attachments))
    lines += ["", record.body]
    return ActionCard(
        card_id=record.card_id,
        kind="agent_mail",
        title="Send this email?",
        preview=scrub("\n".join(lines))[:20_000],
        effects=(
            "Send delivers this one message from your Outlook. Every message needs its own press.",
        ),
        buttons=(
            CardButton(action="send", label="Send", style="primary"),
            CardButton(action="keep_draft", label="Keep as draft"),
            CardButton(action="cancel", label="Cancel", style="danger"),
        ),
        status=record.status,
        status_label=STATUS_LABELS.get(record.status, record.status),
        outcome=record.outcome,
        outcome_ok=record.outcome_ok,
        expires_at=record.expires_at,
        web_only=True,
        message="The agent drafted an email; it waits for your answer.",
    )
