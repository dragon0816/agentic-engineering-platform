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


def _message(
    number: int,
    *,
    folder: str = "Inbox",
    sender: str = "lead@rs.com",
    days: int = 1,
    subject: str = "",
    body: str = "",
    attachments: tuple[str, ...] = (),
) -> MailMessage:
    return MailMessage(
        message_id=f"m{number}",
        folder=folder,
        sender=sender,
        to="me@rs.com",
        subject=subject or f"Status {number}",
        received=NOW - timedelta(days=days),
        attachments=attachments,
        snippet=(body or f"body {number}")[:240],
        body=body or f"body {number}",
    )


class FakeMailbox:
    def __init__(self, messages: list[MailMessage]) -> None:
        self.messages = {item.message_id: item for item in messages}
        self.saved: list[Path] = []

    def list(self, folder: str, since: datetime, limit: int) -> list[MailSummary]:
        prefix = folder.casefold()
        return [
            MailSummary(
                **{
                    key: value
                    for key, value in item.model_dump().items()
                    if key in MailSummary.model_fields
                }
            )
            for item in self.messages.values()
            if item.folder.casefold() == prefix or item.folder.casefold().startswith(prefix + "/")
        ][:limit]

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
    _message(
        1,
        subject="Release plan",
        body="The plan is attached.",
        attachments=("plan.xlsx", "notes.txt"),
    ),
    _message(2, folder="Inbox/Projects", subject="Project X"),
    _message(3, sender="boss@private.com", subject="Private matter"),
    _message(4, folder="Inbox/HR", subject="Salary review"),
    _message(5, days=40, subject="Old release news"),
    _message(6, folder="Sent Items", subject="My own release"),
    _message(7, subject="Token inside", body=f"The login is {SECRET}"),
]
SCOPE = MailScope(
    folders=("Inbox",),
    max_days=30,
    excluded_senders=("@private.com",),
    excluded_folders=("Inbox/HR",),
)


def test_query_parameters_filter_results_without_legacy_mail_admission() -> None:
    box = FakeMailbox(MAILBOX)
    assert {item.message_id for item in outlook_mail.search(box, SCOPE)} == {
        "m1",
        "m2",
        "m3",
        "m4",
        "m7",
    }
    assert [item.message_id for item in outlook_mail.search(box, SCOPE, query="release")] == ["m1"]
    assert outlook_mail.search(box, SCOPE, folder="Inbox/HR")[0].message_id == "m4"
    assert outlook_mail.search(box, SCOPE, folder="Sent Items")[0].message_id == "m6"
    assert "m5" in {item.message_id for item in outlook_mail.search(box, SCOPE, days=90)}
    for number in range(1, 8):
        assert outlook_mail.read(box, SCOPE, f"m{number}").message_id == f"m{number}"
    with pytest.raises(MailError, match="message_unknown"):
        outlook_mail.read(box, SCOPE, "missing")


def test_the_read_only_modules_have_no_verb_that_changes_a_mailbox() -> None:
    source = inspect.getsource(outlook_mail)
    for forbidden in (".Send(", ".Delete(", ".Move(", "UnRead", ".Save(", "MarkAsTask", ".Close("):
        assert forbidden not in source, forbidden


def test_the_capabilities_are_read_only_and_scrub_secrets() -> None:
    assert SEARCH_SPEC.side_effect == "read" and READ_SPEC.side_effect == "read"
    assert SEARCH_SPEC.name == "outlook.search" and READ_SPEC.name == "outlook.read"
    box = FakeMailbox(MAILBOX)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="engineer",
        namespace="engineering",
        channel="local",
        message="m",
    )
    searched = asyncio.run(
        MailSearchHandler(lambda: box, lambda: SCOPE)(context, MailSearchRequest(query="token"))
    )
    assert [item.message_id for item in searched.messages] == ["m7"]  # type: ignore[attr-defined]
    assert "hunter2" not in searched.model_dump_json()
    read = asyncio.run(
        MailReadHandler(lambda: box, lambda: SCOPE)(context, MailReadRequest(message_id="m7"))
    )
    assert "hunter2" not in read.model_dump_json() and "[redacted]" in read.body  # type: ignore[attr-defined]


# -- agent mode: reading -----------------------------------------------------------


def _mail(
    tmp_path: Path, timeout_s: float = 20
) -> tuple[AgentMode, _Tasks, AgentMail, FakeMailbox, RecordingDraftWriter, RecordingDraftSender]:
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
    reply = mode.mcp(
        run,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    import json

    return json.loads(reply["result"]["content"][0]["text"])  # type: ignore[index]


def test_mail_reads_need_no_card_and_keep_attachments_and_redaction(tmp_path: Path) -> None:
    mode, tasks, mail, box, _, _ = _mail(tmp_path)
    run = mode.begin("s1", "claude_code")
    found = _call(mode, run, "outlook_search", {"query": "release"})
    assert found["ok"] and found["complete"] is False
    assert [item["message_id"] for item in found["messages"]] == ["m1"]
    read = _call(mode, run, "outlook_read", {"message_id": "m1", "save_attachments": True})
    assert read["ok"]
    saved = [Path(path) for path in read["saved_attachments"]]
    assert [path.name for path in saved] == ["plan.xlsx", "notes.txt"]
    assert all(path.parent == run.folder / "mail-attachments" and path.is_file() for path in saved)
    assert "hunter2" not in str(_call(mode, run, "outlook_read", {"message_id": "m7"}))
    assert _call(mode, run, "outlook_read", {"message_id": "m3"})["ok"]
    other = mode.begin("s2", "claude_code")
    assert _call(mode, other, "outlook_search", {})["ok"]
    assert not run.cards and not other.cards and not mail.open_cards()
    assert not any(row["kind"] == "agent_permission" for row in tasks.rows.values())


# -- agent mode: sending ---------------------------------------------------------------


def test_draft_and_explicit_send_are_distinct_and_success_is_not_repeated(tmp_path: Path) -> None:
    mode, tasks, mail, _, writer, sender = _mail(tmp_path)
    run = mode.begin("s1", "claude_code")
    report = run.folder / "report.txt"
    report.write_text("numbers", encoding="utf-8")
    first = {
        "to": ["team@rs.com"],
        "cc": ["lead@rs.com"],
        "subject": "Weekly numbers",
        "body": "Hello team,\nthe numbers are attached.",
        "attachments": ["report.txt"],
    }
    drafted = _call(mode, run, "outlook_draft", first)
    assert drafted["ok"] and drafted["status"] == "drafted" and drafted["sent"] is False
    assert sender.sent == [] and len(writer.drafts) == 1
    assert writer.drafts[0].attachments == (str(report),)
    assert "the numbers are attached." in writer.drafts[0].html_body
    assert _call(mode, run, "outlook_draft", first)["replayed"] is True
    assert len(writer.drafts) == 1
    sender.fingerprints[drafted["entry_id"]] = drafted["fingerprint"]
    arguments = {key: drafted[key] for key in ("entry_id", "fingerprint")}
    assert _call(mode, run, "outlook_send", arguments)["sent"] is True
    assert _call(mode, run, "outlook_send", arguments)["replayed"] is True
    assert sender.sent == [drafted["entry_id"]]
    changed = _call(mode, run, "outlook_draft", {**first, "subject": "Changed"})
    sender.fingerprints[changed["entry_id"]] = "changed"
    refused = _call(
        mode, run, "outlook_send", {key: changed[key] for key in ("entry_id", "fingerprint")}
    )
    assert refused["ok"] is False and refused["code"] == "draft_changed"
    assert sender.sent == [drafted["entry_id"]]
    assert not run.cards and not mail.open_cards()
    assert not any(row["kind"] in {"agent_mail", "agent_permission"} for row in tasks.rows.values())


def test_draft_contract_and_credentials_remain_checked_without_folder_acl(tmp_path: Path) -> None:
    mode, _, mail, _, writer, _ = _mail(tmp_path)
    run = mode.begin("s1", "claude_code")
    base = {"to": ["a@rs.com"], "subject": "s", "body": "b"}
    assert (
        _call(mode, run, "outlook_draft", {**base, "to": []})["code"] == "draft_recipient_missing"
    )
    assert (
        _call(mode, run, "outlook_draft", {**base, "body": SECRET})["code"] == "credential_refused"
    )
    assert writer.drafts == []
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("fixture", encoding="utf-8")
    assert _call(mode, run, "outlook_draft", {**base, "attachments": [str(outside)]})["ok"]
    key = run.folder / "deploy.pem"
    key.write_text("fixture, not a key", encoding="utf-8")
    assert _call(mode, run, "outlook_draft", {**base, "attachments": ["deploy.pem"]})["ok"]
    assert (
        _call(mode, run, "outlook_draft", {**base, "attachments": ["missing"]})["code"]
        == "attachment_missing"
    )
    assert len(writer.drafts) == 2


def test_historical_mail_cards_remain_readable_without_replaying_them(tmp_path: Path) -> None:
    from host_runtime.agent_mail import MailCard

    mode, _, mail, _, _, sender = _mail(tmp_path)
    now = mail.cards.now()
    record = MailCard(
        card_id="ml-123456789abc",
        session_id="old",
        entry_id="old-draft",
        fingerprint="a" * 64,
        created_at=now,
        expires_at=now + timedelta(minutes=1),
    )
    mail.cards.put(record)
    assert mail.decide(record.card_id, "send", channel="telegram")["code"] == "web_only"
    assert mail.record(record.card_id) is not None
    assert sender.sent == []
    run = mode.begin("new", "claude_code")
    assert (
        _call(mode, run, "outlook_draft", {"to": ["a@rs.com"], "subject": "s", "body": "b"})[
            "status"
        ]
        == "drafted"
    )
    assert sender.sent == [] and not run.cards


def test_send_is_an_explicit_tool_and_drafting_and_reading_never_send() -> None:
    from capabilities.mail_send.handlers import SPEC as SEND_SPEC
    from host_runtime.agent_mode import MCP_TOOLS
    from integrations import outlook_draft

    assert SEND_SPEC.side_effect == "external_side_effect"
    assert "outlook_send" in MCP_TOOLS
    assert ".Send(" not in inspect.getsource(outlook_draft)
    assert ".Send(" not in inspect.getsource(outlook_mail)
    assert "self._sender().send(" not in inspect.getsource(AgentMail.draft)
    assert "self._sender().send(" in inspect.getsource(AgentMail.send)


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


def test_knowledge_steps_execute_without_cards_and_keep_publication_separate(
    tmp_path: Path,
) -> None:
    mode, tasks = _mode(tmp_path)
    knowledge = FakeKnowledge()
    mode.knowledge = knowledge
    run = mode.begin("s1", "claude_code")
    assert _call(mode, run, "knowledge_sandboxes", {})["bases"] == ["product"]
    for step, arguments in (
        ("lint", {"sandbox_id": "sb1"}),
        ("convert", {"sandbox_id": "sb1", "mode": "dry_run"}),
        ("pull", {"sandbox_id": "sb1", "folders": ["drop/a"]}),
        ("convert", {"sandbox_id": "sb1", "mode": "apply"}),
    ):
        values = {"step": step, "arguments": arguments}
        assert _call(mode, run, "knowledge_step", values)["ok"]
        if step == "pull":
            assert _call(mode, run, "knowledge_step", values)["replayed"] is True
            assert knowledge.calls.count((step, arguments)) == 1
    for step in ("merge", "sandbox-discard", "adopt", "rule-write", "push", "publish"):
        assert _call(mode, run, "knowledge_step", {"step": step})["code"] == "step_not_offered"
    assert (
        _call(mode, run, "knowledge_run_questions", {"sandbox_id": "sb1", "sets": ["core"]})[
            "run_id"
        ]
        == "bench-1"
    )
    assert not run.cards
    assert not any(row["kind"] == "agent_permission" for row in tasks.rows.values())


def test_knowledge_read_steps_are_fresh_and_not_success_receipts(tmp_path: Path) -> None:
    mode, _ = _mode(tmp_path)
    knowledge = FakeKnowledge()
    mode.knowledge = knowledge
    run = mode.begin("fresh", "claude_code")
    values = {"step": "lint", "arguments": {"sandbox_id": "sb1"}}
    assert _call(mode, run, "knowledge_step", values)["ok"]
    assert _call(mode, run, "knowledge_step", values)["ok"]
    assert knowledge.calls.count(("lint", {"sandbox_id": "sb1"})) == 2
