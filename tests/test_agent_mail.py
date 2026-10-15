"""Email and the Knowledge pipeline as agent-mode tools (owner 2026-10-15).

docs/phases/AGENT_MODE_BACKENDS.md, "Revised rules": reading mail is read
only, in the person's scope, one card the first time per conversation;
sending is a draft plus a card, every message its own Send press, and
nothing else in AEP can send. Knowledge pipeline writes are carded; push,
merge and publish are not offered.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_agent_mode import _mode, _Tasks

from capabilities.mail_read.handlers import (
    READ_SPEC,
    SEARCH_SPEC,
    MailReadHandler,
    MailReadRequest,
    MailSearchHandler,
    MailSearchRequest,
)
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.agent_mail import AgentMail
from host_runtime.agent_mode import AgentMode, AgentRun
from integrations import outlook_mail, outlook_send
from integrations.outlook_draft import RecordingDraftWriter
from integrations.outlook_mail import MailError, MailMessage, MailScope, MailSummary
from integrations.outlook_send import (
    OutlookComDraftSender,
    RecordingDraftSender,
    SendError,
    draft_fingerprint,
)

NOW = datetime.now(UTC)
SECRET = "password=hunter2-very-secret"


def _message(number: int, *, folder: str = "Inbox", sender: str = "lead@rs.com",
             days: int = 1, subject: str = "", body: str = "",
             attachments: tuple[str, ...] = ()) -> MailMessage:
    return MailMessage(message_id=f"m{number}", folder=folder, sender=sender,
                       to="me@rs.com", subject=subject or f"Status {number}",
                       received=NOW - timedelta(days=days), attachments=attachments,
                       snippet=(body or f"body {number}")[:240], body=body or f"body {number}")


class FakeMailbox:
    def __init__(self, messages: list[MailMessage]) -> None:
        self.messages = {item.message_id: item for item in messages}
        self.saved: list[Path] = []

    def list(self, folder: str, since: datetime, limit: int) -> list[MailSummary]:
        prefix = folder.casefold()
        return [MailSummary(**{key: value for key, value in item.model_dump().items()
                               if key not in ("cc", "body")})
                for item in self.messages.values()
                if item.folder.casefold() == prefix
                or item.folder.casefold().startswith(prefix + "/")][:limit]

    def get(self, message_id: str) -> MailMessage:
        if message_id not in self.messages:
            raise MailError("message_unknown")
        return self.messages[message_id]

    def save_attachment(self, message_id: str, name: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"attachment " + name.encode())
        self.saved.append(target)
        return target


MAILBOX = [
    _message(1, subject="Release plan", body="The plan is attached.",
             attachments=("plan.xlsx", "notes.txt")),
    _message(2, folder="Inbox/Projects", subject="Project X"),
    _message(3, sender="boss@private.com", subject="Private matter"),
    _message(4, folder="Inbox/HR", subject="Salary review"),
    _message(5, days=40, subject="Old release news"),
    _message(6, folder="Sent Items", subject="My own release"),
    _message(7, subject="Token inside", body=f"The login is {SECRET}"),
]
SCOPE = MailScope(folders=("Inbox",), max_days=30, excluded_senders=("@private.com",),
                  excluded_folders=("Inbox/HR",))


def test_search_and_read_keep_to_the_persons_scope() -> None:
    box = FakeMailbox(MAILBOX)
    found = outlook_mail.search(box, SCOPE)
    assert {item.message_id for item in found} == {"m1", "m2", "m7"}
    assert [item.message_id for item in outlook_mail.search(box, SCOPE, query="release")
            ] == ["m1"]
    assert outlook_mail.search(box, SCOPE, folder="Inbox/Projects")[0].message_id == "m2"
    with pytest.raises(MailError):
        outlook_mail.search(box, SCOPE, folder="Inbox/HR")
    with pytest.raises(MailError):
        outlook_mail.search(box, SCOPE, folder="Sent Items")
    # Days cannot widen the scope.
    assert "m5" not in {item.message_id for item in outlook_mail.search(box, SCOPE, days=90)}
    for outside in ("m3", "m4", "m5", "m6"):
        with pytest.raises(MailError) as refused:
            outlook_mail.read(box, SCOPE, outside)
        assert refused.value.code == "message_unknown"
    assert outlook_mail.read(box, SCOPE, "m1").subject == "Release plan"


def test_the_read_only_modules_have_no_verb_that_changes_a_mailbox() -> None:
    source = inspect.getsource(outlook_mail)
    for forbidden in (".Send(", ".Delete(", ".Move(", "UnRead", ".Save(", "MarkAsTask",
                      ".Close("):
        assert forbidden not in source, forbidden


def test_the_capabilities_are_read_only_and_scrub_secrets() -> None:
    assert SEARCH_SPEC.side_effect == "read" and READ_SPEC.side_effect == "read"
    assert SEARCH_SPEC.name == "outlook.search" and READ_SPEC.name == "outlook.read"
    box = FakeMailbox(MAILBOX)
    context = RequestContext(trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
                             actor="engineer", namespace="engineering", channel="local",
                             message="m")
    searched = asyncio.run(MailSearchHandler(lambda: box, lambda: SCOPE)(
        context, MailSearchRequest(query="token")))
    assert [item.message_id for item in searched.messages] == ["m7"]  # type: ignore[attr-defined]
    assert "hunter2" not in searched.model_dump_json()
    read = asyncio.run(MailReadHandler(lambda: box, lambda: SCOPE)(
        context, MailReadRequest(message_id="m7")))
    assert "hunter2" not in read.model_dump_json() and "[redacted]" in read.body  # type: ignore[attr-defined]


# -- agent mode: reading -----------------------------------------------------------


def _mail(tmp_path: Path, timeout_s: float = 20) -> tuple[AgentMode, _Tasks, AgentMail,
                                                         FakeMailbox, RecordingDraftWriter,
                                                         RecordingDraftSender]:
    mode, tasks = _mode(tmp_path, timeout_s=timeout_s)
    mode.save_settings({"claude_code": True, "mail": SCOPE.model_dump(mode="json")})
    box, writer, sender = FakeMailbox(MAILBOX), RecordingDraftWriter(), RecordingDraftSender()
    mail = AgentMail(mode, reader=lambda: box, writer=lambda: writer, sender=lambda: sender)
    mode.mail = mail
    return mode, tasks, mail, box, writer, sender


def _press(cards: Any, action: str, *, times: int = 1) -> threading.Thread:
    """Press `action` on the next `times` cards that appear (`cards()` lists open ones)."""

    def press() -> None:
        done: set[str] = set()
        deadline = time.monotonic() + 20
        while len(done) < times and time.monotonic() < deadline:
            for card in cards():
                if card.card_id not in done:
                    done.add(card.card_id)
                    decide = getattr(cards, "__self__", None)
                    assert decide is not None
                    decide.decide(card.card_id, action)
            time.sleep(0.05)

    thread = threading.Thread(target=press, daemon=True)
    thread.start()
    return thread


def _call(mode: AgentMode, run: AgentRun, name: str, arguments: dict[str, Any]) -> Any:
    reply = mode.mcp(run, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}})
    import json

    return json.loads(reply["result"]["content"][0]["text"])  # type: ignore[index]


def test_the_first_read_asks_once_per_conversation(tmp_path: Path) -> None:
    mode, tasks, mail, box, _, _ = _mail(tmp_path)
    run = mode.begin("s1", "claude_code")
    presser = _press(mode.open_cards, "deny")
    refused = _call(mode, run, "outlook_search", {"query": "release"})
    presser.join()
    assert refused["code"] == "not_allowed"
    presser = _press(mode.open_cards, "allow_session")
    found = _call(mode, run, "outlook_search", {"query": "release"})
    presser.join()
    assert [item["message_id"] for item in found["messages"]] == ["m1"]
    card = mode.card(run.cards[-1])
    assert card is not None and card.title == "Read your email in this conversation"
    assert "Inbox" in card.preview and "@private.com" in card.preview
    assert [button.action for button in card.buttons] == ["allow_session", "deny"]
    # Later reads in this conversation, also in a later turn, ask no more.
    second = mode.begin("s1", "claude_code")
    read = _call(mode, second, "outlook_read", {"message_id": "m1", "save_attachments": True})
    assert read["ok"] and not second.cards
    saved = [Path(path) for path in read["saved_attachments"]]
    assert [path.name for path in saved] == ["plan.xlsx", "notes.txt"]
    assert all(path.parent == second.folder / "mail-attachments" for path in saved)
    secret = _call(mode, second, "outlook_read", {"message_id": "m7"})
    assert "hunter2" not in str(secret)
    assert _call(mode, second, "outlook_read", {"message_id": "m3"})["code"] == "message_unknown"
    # Another conversation asks again.
    other = mode.begin("s2", "claude_code")
    mode.timeout_s = 0.2
    assert _call(mode, other, "outlook_search", {})["code"] == "not_allowed"
    assert any(row["title"] == "Read your email in this conversation"
               for row in tasks.rows.values())


# -- agent mode: sending ---------------------------------------------------------------


def test_sending_needs_a_press_on_each_message(tmp_path: Path) -> None:
    mode, tasks, mail, _, writer, sender = _mail(tmp_path)
    run = mode.begin("s1", "claude_code")
    report = run.folder / "report.txt"
    report.write_text("numbers", encoding="utf-8")
    first = {"to": ["team@rs.com"], "cc": ["lead@rs.com"], "subject": "Weekly numbers",
             "body": "Hello team,\nthe numbers are attached.", "attachments": ["report.txt"]}

    def fingerprint_drafts() -> None:
        # What Outlook holds now for each saved draft: as drafted.
        for number, draft in enumerate(writer.drafts, start=1):
            sender.fingerprints[f"recorded-{number}"] = draft_fingerprint(
                draft.to, draft.cc, draft.subject,
                [Path(path).name for path in draft.attachments])

    def press(action: str) -> threading.Thread:
        def run_press() -> None:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                cards = mail.open_cards("s1")
                if cards:
                    fingerprint_drafts()
                    mail.decide(cards[0].card_id, action)
                    return
                time.sleep(0.05)

        thread = threading.Thread(target=run_press, daemon=True)
        thread.start()
        return thread

    presser = press("send")
    sent = _call(mode, run, "outlook_draft", first)
    presser.join()
    assert sent["ok"] and sent["status"] == "sent"
    assert sender.sent == ["recorded-1"]
    card = mail.card(run.cards[-1])
    assert card is not None and card.card_id.startswith("ml-")
    for shown in ("To: team@rs.com", "Cc: lead@rs.com", "Subject: Weekly numbers",
                  "the numbers are attached.", "Attachments: report.txt"):
        assert shown in card.preview, shown
    assert [b.label for b in card.buttons] == ["Send", "Keep as draft", "Cancel"]
    # The same message again is a new draft and a new card: nothing is remembered.
    presser = press("keep_draft")
    kept = _call(mode, run, "outlook_draft", first)
    presser.join()
    assert kept["status"] == "kept" and sender.sent == ["recorded-1"]
    presser = press("cancel")
    cancelled = _call(mode, run, "outlook_draft", {**first, "attachments": []})
    presser.join()
    assert cancelled["status"] == "cancelled" and sender.discarded == ["recorded-3"]
    # A draft edited in Outlook after the card is not sent.
    def edited() -> None:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            cards = mail.open_cards("s1")
            if cards:
                fingerprint_drafts()
                sender.fingerprints["recorded-4"] = "changed"
                mail.decide(cards[0].card_id, "send")
                return
            time.sleep(0.05)

    thread = threading.Thread(target=edited, daemon=True)
    thread.start()
    changed = _call(mode, run, "outlook_draft", first)
    thread.join()
    assert changed["status"] == "failed" and "changed in Outlook" in changed["message"]
    assert sender.sent == ["recorded-1"]
    # No answer: the draft stays a draft.
    mode.timeout_s = 0.2
    late = _call(mode, run, "outlook_draft", first)
    assert late["status"] == "expired" and sender.sent == ["recorded-1"]
    mail_rows = [row for row in tasks.rows.values() if row["kind"] == "agent_mail"]
    assert [row["status"] for row in mail_rows] == [
        "succeeded", "stopped", "stopped", "failed", "stopped"]
    # The answer keeps every mail card as decided.
    shown = mode.finish(run, "answered")
    assert [card["status"] for card in shown] == ["sent", "kept", "cancelled", "failed",
                                                   "expired"]
    assert all(card["card_id"].startswith("ml-") for card in shown)


def test_a_draft_is_refused_before_outlook_when_it_is_unsafe(tmp_path: Path) -> None:
    mode, _, mail, _, writer, _ = _mail(tmp_path)
    run = mode.begin("s1", "claude_code")
    base = {"to": ["a@rs.com"], "subject": "s", "body": "b"}
    assert _call(mode, run, "outlook_draft", {**base, "to": []})["code"] == \
        "draft_recipient_missing"
    assert _call(mode, run, "outlook_draft", {**base, "body": SECRET})["code"] == \
        "credential_refused"
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x", encoding="utf-8")
    assert _call(mode, run, "outlook_draft", {**base, "attachments": [str(outside)]}
                 )["code"] == "attachment_outside"
    key = run.folder / "deploy.pem"
    key.write_text("x", encoding="utf-8")
    assert _call(mode, run, "outlook_draft", {**base, "attachments": ["deploy.pem"]}
                 )["code"] == "attachment_refused"
    assert writer.drafts == []


def test_mail_cards_are_answered_in_agent_web_only(tmp_path: Path) -> None:
    mode, _, mail, _, _, sender = _mail(tmp_path, timeout_s=1)
    run = mode.begin("s1", "claude_code")
    answers: list[dict[str, Any]] = []

    def telegram() -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            cards = mail.open_cards("s1")
            if cards:
                answers.append(mail.decide(cards[0].card_id, "send", channel="telegram"))
                return
            time.sleep(0.05)

    thread = threading.Thread(target=telegram, daemon=True)
    thread.start()
    result = _call(mode, run, "outlook_draft", {"to": ["a@rs.com"], "subject": "s",
                                                "body": "b"})
    thread.join()
    assert answers[0]["code"] == "web_only" and result["status"] == "expired"
    assert sender.sent == []


def test_no_send_verb_is_reachable_except_a_mail_cards_decision() -> None:
    """`integrations.outlook_send` is used by the mail card's decision only:
    no tool, route, capability or Workflow step reaches it."""
    root = Path(__file__).resolve().parents[1] / "src"
    importing = re.compile(r"^\s*(from\s+\S*outlook_send\s+import|import\s+\S*outlook_send"
                           r"|from\s+integrations\s+import\s+[^\n]*outlook_send)", re.M)
    users = sorted(str(path.relative_to(root)).replace("\\", "/")
                   for path in root.rglob("*.py")
                   if importing.search(path.read_text(encoding="utf-8")))
    assert users == ["host_runtime/agent_mail.py", "host_runtime/web.py"]
    web_source = (root / "host_runtime" / "web.py").read_text(encoding="utf-8")
    assert len(importing.findall(web_source)) == 1  # the factory handed to AgentMail
    mail_source = inspect.getsource(AgentMail)
    assert mail_source.count("self._sender().send(") == 1
    decide = inspect.getsource(AgentMail.decide)
    assert "self._sender().send(" in decide
    from host_runtime.agent_mode import MCP_TOOLS

    assert not any("send" in name for name in MCP_TOOLS)
    # The draft module keeps its own never-send promise.
    from integrations import outlook_draft

    assert ".Send(" not in inspect.getsource(outlook_draft)


def test_the_outlook_sender_sends_only_the_draft_the_card_showed() -> None:
    class Item:
        def __init__(self) -> None:
            self.To, self.CC, self.Subject = "team@rs.com", "", "Weekly numbers"
            self.Attachments = type("A", (), {"Count": 0, "Item": lambda self, i: None})()
            self.sent = self.deleted = 0

        def Send(self) -> None:  # noqa: N802 - Outlook's spelling
            self.sent += 1

        def Delete(self) -> None:  # noqa: N802 - Outlook's spelling
            self.deleted += 1

    item = Item()
    namespace = type("N", (), {"GetItemFromID": lambda self, entry: item})()
    outlook = type("O", (), {"GetNamespace": lambda self, name: namespace})()
    sender = OutlookComDraftSender(dispatch=outlook)
    right = draft_fingerprint(["team@rs.com"], [], "Weekly numbers", [])
    with pytest.raises(SendError) as changed:
        sender.send("E1", draft_fingerprint(["other@rs.com"], [], "Weekly numbers", []))
    assert changed.value.code == "draft_changed" and item.sent == 0
    sender.send("E1", right)
    assert item.sent == 1
    sender.discard("E1")
    assert item.deleted == 1
    assert ".Send()" in inspect.getsource(outlook_send)


# -- the Knowledge pipeline as tools --------------------------------------------------


class FakeKnowledge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.benchmarks: list[tuple[str, list[str]]] = []

    def knowledge_pipeline(self) -> dict[str, Any]:
        return {"enabled": True, "bases": ["product"]}

    def pipeline_call(self, step: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((step, arguments))
        return {"ok": True, "data": {"step": step}}

    def start_benchmark(self, sandbox_id: str, sets: list[str]) -> dict[str, Any]:
        self.benchmarks.append((sandbox_id, sets))
        return {"ok": True, "run_id": "bench-1"}

    def benchmark_status(self, sandbox_id: str) -> dict[str, Any]:
        return {"ok": True, "report": None}


def test_knowledge_reads_are_free_writes_are_carded_and_push_is_not_offered(
        tmp_path: Path) -> None:
    mode, tasks = _mode(tmp_path)
    knowledge = FakeKnowledge()
    mode.knowledge = knowledge
    run = mode.begin("s1", "claude_code")
    assert _call(mode, run, "knowledge_sandboxes", {})["bases"] == ["product"]
    assert _call(mode, run, "knowledge_step", {"step": "lint", "arguments": {
        "sandbox_id": "sb1"}})["ok"]
    assert _call(mode, run, "knowledge_step", {"step": "convert", "arguments": {
        "sandbox_id": "sb1", "mode": "dry_run"}})["ok"]
    assert not run.cards
    for step in ("merge", "sandbox-discard", "adopt", "rule-write", "push", "publish"):
        assert _call(mode, run, "knowledge_step", {"step": step})["code"] == "step_not_offered"
    presser = _press(mode.open_cards, "deny")
    denied = _call(mode, run, "knowledge_step", {"step": "pull", "arguments": {
        "sandbox_id": "sb1", "folders": ["drop/a"]}})
    presser.join()
    assert denied["code"] == "not_allowed"
    assert ("pull", {"sandbox_id": "sb1", "folders": ["drop/a"]}) not in knowledge.calls
    presser = _press(mode.open_cards, "allow_session")
    assert _call(mode, run, "knowledge_step", {"step": "pull", "arguments": {
        "sandbox_id": "sb1", "folders": ["drop/a"]}})["ok"]
    presser.join()
    before = len(run.cards)
    assert _call(mode, run, "knowledge_step", {"step": "pull", "arguments": {
        "sandbox_id": "sb1", "folders": ["drop/b"]}})["ok"]
    assert len(run.cards) == before  # allowed for this conversation
    presser = _press(mode.open_cards, "allow")
    assert _call(mode, run, "knowledge_step", {"step": "convert", "arguments": {
        "sandbox_id": "sb1", "mode": "apply"}})["ok"]
    presser.join()
    presser = _press(mode.open_cards, "allow")
    assert _call(mode, run, "knowledge_run_questions", {"sandbox_id": "sb1",
                                                        "sets": ["core"]})["run_id"] == "bench-1"
    presser.join()
    titles = [mode.record(card).title for card in run.cards]  # type: ignore[union-attr]
    assert titles == ["Knowledge: pull in a sandbox", "Knowledge: pull in a sandbox",
                      "Knowledge: convert in a sandbox",
                      "Knowledge: run questions in a sandbox"]
    assert sum(row["kind"] == "agent_permission" for row in tasks.rows.values()) == 4
