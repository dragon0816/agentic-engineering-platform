"""Original task documents remain model-visible without inventing another upload."""

from __future__ import annotations

import base64
import io
import json
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from test_agent_web import base, fetch
from test_attachment_authoring import AuthoringGateway
from test_chat_authoring import Echo, Out, spec
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import ready
from test_office import make_docx, make_pdf

from capabilities.runtime import CapabilityExecutionFailed
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.attachments import MAX_FILES_PER_MESSAGE, Attachment
from host_runtime.authoring_task import Requirement
from host_runtime.conversations import ConversationMessage, ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer

REQUIREMENT: dict[str, Any] = {
    "requirement_id": "read",
    "description": "Read original SOP",
    "check_ids": ["read"],
    "assertions": [
        {"path": ["steps", 0, "capability", "name"], "operator": "equals", "expected": "read-it"}
    ],
}
QUESTION: dict[str, Any] = {
    "reason": "business_decision",
    "question": "Which approved business region applies?",
    "input_name": "region",
}


class Wire(AuthoringGateway):
    def __init__(self, *replies: tuple[str, dict[str, Any]] | str) -> None:
        super().__init__()
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        self.requests.append(json.loads(body))
        assert self.replies, "Unexpected extra model request"
        reply = self.replies.pop(0)
        if isinstance(reply, tuple):
            return self._call(*reply)
        return GatewayReply(
            200,
            {
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": reply,
                        },
                    }
                ]
            },
        )


def _content(payload: dict[str, Any]) -> tuple[str, list[str]]:
    message = next(m for m in reversed(payload["messages"]) if m["role"] == "user")
    content = message["content"]
    if isinstance(content, str):
        return content, []
    return (
        "\n".join(p.get("text", "") for p in content),
        [p["image_url"]["url"] for p in content if p["type"] == "image_url"],
    )


@contextmanager
def _web(tmp_path: Path, wire: Wire) -> Iterator[AgentWeb]:
    config, _ = ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, capabilities={"vision": True})],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
            "web": {"allowed_origins": ["https://example.invalid"]},
        },
    )
    with build_runtime(config, model_transport=wire) as runtime:
        yield AgentWeb(runtime)


def _documents() -> list[tuple[str, bytes]]:
    book = Workbook()
    assert book.active is not None
    book.active.append(["Sales Name / Owner", "Sub-Dept."])
    book.active.append(["Example Owner", "SAS"])
    buffer = io.BytesIO()
    book.save(buffer)
    return [
        ("original-sop.pdf", make_pdf(["Open Sales Order"], image=True)),
        ("original-sop.docx", make_docx()),
        ("mapping.xlsx", buffer.getvalue()),
    ]


def _save_user_files(web: AgentWeb, session: str, files: list[Attachment]) -> None:
    record = web.runtime.state.conversation(session, web.runtime.actor)
    assert record is not None
    now = datetime.now(UTC)
    message = ConversationMessage(
        message_id=f"upload-{len(record.messages)}",
        role="user",
        text="Original task references",
        created_at=now,
        status="submitted",
        attachments=tuple({"filename": f.filename, "kind": f.kind, "path": f.path} for f in files),
    )
    web.runtime.state.save_conversation(
        record.model_copy(
            update={
                "updated_at": now,
                "messages": (*record.messages, message),
            }
        )
    )


def test_two_http_turns_keep_original_document_images_and_excel_reference(tmp_path: Path) -> None:
    wire = Wire(
        ("authoring__plan_workflow", {"requirements": [REQUIREMENT]}),
        ("authoring__needs_input", QUESTION),
        "Which approved business region applies?",
        ("authoring__needs_input", QUESTION),
        "Which approved business region applies?",
    )
    with _web(tmp_path, wire) as web:
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            session = fetch(base(server) + "/api/conversations", token=server.token, body={}).json()
            session_id = session["conversation"]["session_id"]
            ids = []
            for name, data in _documents():
                uploaded = fetch(
                    base(server) + "/api/attachments",
                    token=server.token,
                    body={
                        "session_id": session_id,
                        "filename": name,
                        "data": base64.b64encode(data).decode(),
                    },
                ).json()
                assert uploaded["ok"]
                ids.append(uploaded["attachment"]["file_id"])
            first = fetch(
                base(server) + "/api/conversations/turn",
                token=server.token,
                body={
                    "session_id": session_id,
                    "message": "Build this SOP workflow",
                    "attachments": ids,
                },
            ).json()
            assert first["ok"]
            first_text, first_images = _content(wire.requests[0])
            second_start = len(wire.requests)
            second = fetch(
                base(server) + "/api/conversations/turn",
                token=server.token,
                body={
                    "session_id": session_id,
                    "message": "Continue the same authoring task",
                },
            ).json()
            assert second["ok"]
            text, images = _content(wire.requests[second_start])
            assert "Saved task references" in text and "not new user input" in text
            for expected in (
                "Open Sales Order",
                "First paragraph",
                "Sales Name / Owner",
                "Sub-Dept.",
            ):
                assert expected in first_text and expected in text
            assert len(images) == 2 and images == first_images
            messages = web.conversations(session_id)["selected"]["messages"]
            users = [m for m in messages if m["role"] == "user"]
            assert len(users[0]["attachments"]) == 3 and users[-1]["attachments"] == []
            chat = web.runtime.chat_authoring
            assert chat is not None
            observed = chat.tasks.messages(web.runtime.actor, session_id)
            assert len(observed) == 2
            assert observed[-1].text == "Continue the same authoring task"
            assert observed[-1].attachments == ()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def test_automatic_card_repair_receives_original_pdf_images_without_new_input(
    tmp_path: Path,
) -> None:
    wire = Wire(("authoring__needs_input", QUESTION), "Which approved business region applies?")
    with _web(tmp_path, wire) as web:
        session = web.create_conversation()["conversation"]["session_id"]
        files = [web.attachments.add(session, name, data) for name, data in _documents()]
        _save_user_files(web, session, files)
        chat = web.runtime.chat_authoring
        assert chat is not None
        chat.tasks.plan(
            web.runtime.actor, session, "Read SOP", [Requirement.model_validate(REQUIREMENT)]
        )
        chat.tasks.observe(web.runtime.actor, session, "Use the original SOP")

        async def fail(context: RequestContext, inputs: Contract) -> Contract:
            raise CapabilityExecutionFailed("fixture_failure", Out(echoed="failed"))

        web.runtime.agent.gateway.bridge.installed.register(
            spec("read-it", "read"), fail, Echo, Out, ExecutionDependencies(central_required=False)
        )
        item, problems = chat.draft(
            web.runtime.actor,
            session,
            "Read SOP",
            {
                "name": "read-sop",
                "description": "Read SOP",
                "parameters": [],
                "steps": [
                    {
                        "capability": "lab/read-it@1.0.0",
                        "inputs": {"value": {"source": "fixed", "value": "bad"}},
                    }
                ],
                "checks": [{"check_id": "read", "step_index": 0, "kind": "data_nonempty"}],
            },
        )
        assert item is not None and not problems
        (card,) = web.draft_turn_cards(session, datetime(2000, 1, 1, tzinfo=UTC))
        before = chat.tasks.messages(web.runtime.actor, session)

        result = web.decide_card(card["card_id"], "try")

        assert "repair" in result
        text, images = _content(wire.requests[0])
        assert "Host authoring continuation" in text
        assert "Saved task references" in text and "Open Sales Order" in text
        assert "First paragraph" in text and "mapping.xlsx" in text
        assert len(images) == 2
        assert chat.tasks.messages(web.runtime.actor, session) == before
        active = chat.tasks.load(web.runtime.actor, session)
        assert active is not None and active.repair_attempts == 1


def test_references_are_bounded_store_owned_and_missing_files_are_skipped(tmp_path: Path) -> None:
    with _web(tmp_path, Wire()) as web:
        session = web.create_conversation()["conversation"]["session_id"]
        other = web.create_conversation()["conversation"]["session_id"]
        files = [
            web.attachments.add(session, f"ref-{i}.txt", f"row-{i}".encode())
            for i in range(MAX_FILES_PER_MESSAGE + 2)
        ]
        missing = web.attachments.add(session, "missing.txt", b"Missing source")
        Path(missing.path).unlink()
        foreign = web.attachments.add(other, "foreign.txt", b"Foreign secret")
        expired = web.attachments.add(session, "expired.txt", b"Unregistered source")
        Path(expired.path).with_name("attachment.json").unlink()
        _save_user_files(web, session, [missing, foreign, expired, *files])
        chat = web.runtime.chat_authoring
        assert chat is not None
        chat.tasks.plan(
            web.runtime.actor, session, "Read SOP", [Requirement.model_validate(REQUIREMENT)]
        )
        note, images = web._saved_task_references(session)
        assert note.count(" bytes): ") == MAX_FILES_PER_MESSAGE
        assert "missing.txt" not in note and "foreign.txt" not in note and not images
        assert "expired.txt" not in note
        assert web._saved_task_references(other) == ("", ())
        # A forged reference to a real file outside the store is never opened as a source.
        external = tmp_path / "outside.txt"
        external.write_text("External secret")
        _save_user_files(web, session, [missing.model_copy(update={"path": str(external)})])
        note, _ = web._saved_task_references(session)
        assert "External secret" not in note and "outside.txt" not in note
        # Completed tasks do not keep replaying reference pictures on unrelated turns.
        task = chat.tasks.load(web.runtime.actor, session)
        assert task is not None
        chat.tasks.save(
            web.runtime.actor, session, task.model_copy(update={"verified_digest": "done"})
        )
        assert web._saved_task_references(session) == ("", ())


def test_new_uploads_win_and_legacy_turns_do_not_rehydrate(tmp_path: Path) -> None:
    wire = Wire(
        ("authoring__needs_input", QUESTION),
        "Which approved business region applies?",
        "Legacy response",
    )
    with _web(tmp_path, wire) as web:
        session = web.create_conversation()["conversation"]["session_id"]
        old = web.attachments.add(session, "old.txt", b"Old task source")
        _save_user_files(web, session, [old])
        chat = web.runtime.chat_authoring
        assert chat is not None
        chat.tasks.plan(
            web.runtime.actor, session, "Read SOP", [Requirement.model_validate(REQUIREMENT)]
        )
        new = web.attachments.add(session, "new.txt", b"New explicit source")
        web.conversation_turn(
            ConversationTurnRequest(
                session_id=session,
                message="Use this replacement",
                attachments=(new.file_id,),
            )
        )
        text, _ = _content(wire.requests[0])
        assert "New explicit source" in text and "Saved task references" not in text
        assert "Old task source" not in text
        legacy = web.create_conversation()["conversation"]["session_id"]
        _save_user_files(web, legacy, [web.attachments.add(legacy, "legacy.txt", b"Legacy file")])
        start = len(wire.requests)
        web.conversation_turn(ConversationTurnRequest(session_id=legacy, message="Hello"))
        text, images = _content(wire.requests[start])
        assert text == "Hello" and not images
