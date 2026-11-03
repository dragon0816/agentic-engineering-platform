"""A stored Telegram conversation in Agent Web: listed, read, searched, deleted
and never continued (docs/phases/TELEGRAM_HISTORY.md). No Telegram and no model."""

from __future__ import annotations

import base64
import threading
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import fetch
from test_host_wiring import ready

from common.assets import AssetIdentity
from host_runtime.attachments import AttachmentStore
from host_runtime.conversations import (
    ConversationBackendSelectRequest,
    ConversationDeleteRequest,
    ConversationFeedbackRequest,
    ConversationModelSelectRequest,
    ConversationRecord,
    ConversationTurnRequest,
)
from host_runtime.host import HostRuntime, build_runtime
from host_runtime.telegram_history import StoredTurn
from host_runtime.web import AgentWeb, AgentWebServer

CHAT = 7654321987654
FILES_SESSION = f"telegram-chat-{CHAT}-sender-{CHAT}"


@dataclass
class Served:
    runtime: HostRuntime
    web: AgentWeb
    server: AgentWebServer

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}{path}"

    def get(self, path: str) -> Any:
        return fetch(self.url(path), token=self.server.token)

    def post(self, path: str, body: Any) -> Any:
        return fetch(self.url(path), token=self.server.token, body=body)

    def add_turn(self, said: str = "a question", **changes: Any) -> ConversationRecord:
        store = self.runtime.telegram_history
        assert store is not None
        store.add_turn(CHAT, CHAT, StoredTurn(said, "an answer", **changes))
        latest = self.runtime.state.conversations(self.runtime.actor, source="telegram")[0]
        return latest


@pytest.fixture
def served(tmp_path: Path) -> Iterator[Served]:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield Served(runtime, web, server)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def test_the_list_marks_the_source_and_the_record_opens(served: Served) -> None:
    chat = served.web.create_conversation()["conversation"]["session_id"]
    record = served.add_turn("問題一")
    listed = served.get("/api/conversations").json()
    assert {row["session_id"]: row["source"] for row in listed["conversations"]} == {
        chat: "agent_web",
        record.session_id: "telegram",
    }
    opened = served.get(f"/api/conversations?session_id={record.session_id}").json()
    assert opened["selected"]["source"] == "telegram"
    assert [m["text"] for m in opened["selected"]["messages"]] == ["問題一", "an answer"]
    assert str(CHAT) not in served.get("/api/conversations").body.decode()


def test_daily_telegram_records_do_not_push_chats_off_the_list(served: Served) -> None:
    chat = served.web.create_conversation()["conversation"]["session_id"]
    store = served.runtime.telegram_history
    assert store is not None
    for number in range(60):
        store.start_new(CHAT, CHAT)
        store.add_turn(CHAT, CHAT, StoredTurn(f"question {number}", "an answer"))
    rows = served.web.conversations()["conversations"]
    assert chat in [row["session_id"] for row in rows]
    assert sum(row["source"] == "telegram" for row in rows) == 50


def test_every_changing_route_refuses_a_telegram_conversation(served: Served) -> None:
    record = served.add_turn()
    session = record.session_id
    answer = record.messages[1].message_id
    web = served.web
    results = [
        web.conversation_turn(ConversationTurnRequest(session_id=session, message="continue")),
        web.select_conversation_model(
            ConversationModelSelectRequest(session_id=session, model="any")
        ),
        web.select_conversation_backend(
            ConversationBackendSelectRequest(session_id=session, backend="gateway")
        ),
        web.conversation_feedback(
            ConversationFeedbackRequest(session_id=session, message_id=answer, rating="up")
        ),
        web.add_attachment(session, "a.txt", b"x"),
        web.update_agent_session({"session_id": session, "folder": "x"}),
    ]
    for result in results:
        assert result == {"ok": False, "code": "conversation_read_only"}
    # Nothing changed, and no rating is waiting to go to the platform.
    assert served.runtime.state.conversation(session, served.runtime.actor) == record
    assert served.runtime.state.feedback_backlog() == 0


def test_the_turn_route_answers_with_a_refusal_not_a_missing_conversation(served: Served) -> None:
    session = served.add_turn().session_id
    reply = served.post("/api/conversations/turn", {"session_id": session, "message": "go on"})
    assert reply.status == 409 and reply.json()["code"] == "conversation_read_only"


def test_a_contribution_draft_is_refused(served: Served) -> None:
    from host_runtime.contributions import ContributionDraftCreateRequest

    record = served.add_turn()
    request = ContributionDraftCreateRequest(
        session_id=record.session_id,
        request_kind="problem",
        summary="a problem",
        expected_behavior="this",
        actual_behavior="that",
        acceptance_criteria=("fixed",),
    )
    assert served.web.create_contribution_draft(request) == {
        "ok": False,
        "code": "conversation_read_only",
    }


def test_voice_is_refused_for_a_telegram_conversation(
    served: Served, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = served.add_turn().session_id
    monkeypatch.setattr(served.web, "voice", object())
    status, body = served.web.transcribe_voice(
        {
            "session_id": session,
            "mime_type": "audio/webm",
            "data": base64.b64encode(b"x").decode(),
        }
    )
    assert (status, body["code"]) == (409, "conversation_read_only")


def test_a_form_run_is_not_written_into_a_telegram_conversation(served: Served) -> None:
    record = served.add_turn()
    identity = AssetIdentity(namespace="engineering", name="a-workflow", version="1.0.0")
    assert (
        served.web._record_form_run(record.session_id, None, identity, {}, "the result", True)
        is None
    )
    assert served.runtime.state.conversation(record.session_id, served.runtime.actor) == record


def test_an_agent_web_conversation_is_still_writable(served: Served) -> None:
    session = served.web.create_conversation()["conversation"]["session_id"]
    assert served.web.add_attachment(session, "a.txt", b"x")["ok"] is True


def test_deleting_removes_the_record_and_the_files_it_lists_and_no_others(served: Served) -> None:
    store = AttachmentStore(served.runtime.layout.workspace_root)
    kept = store.add(FILES_SESSION, "kept.txt", b"kept")
    gone = store.add(FILES_SESSION, "gone.txt", b"gone")
    history = served.runtime.telegram_history
    assert history is not None

    def listing(path: str, name: str) -> dict[str, str]:
        return {"filename": name, "kind": "text", "path": path}

    earlier = served.add_turn("kept", files=[listing(kept.path, "kept.txt")])
    history.start_new(CHAT, CHAT)
    latest = served.add_turn("gone", files=[listing(gone.path, "gone.txt")])
    assert latest.session_id != earlier.session_id

    assert served.web.delete_conversation(
        ConversationDeleteRequest(session_id=latest.session_id)
    ) == {"ok": True, "code": None}
    actor = served.runtime.actor
    assert served.runtime.state.conversation(latest.session_id, actor) is None
    assert not Path(gone.path).exists() and not Path(gone.path).parent.exists()
    assert Path(kept.path).is_file()
    assert served.runtime.state.conversation(earlier.session_id, actor) is not None


def test_deleting_never_reaches_a_path_outside_the_attachments(
    served: Served, tmp_path: Path
) -> None:
    outside = tmp_path / "outside" / "one" / "two"
    outside.mkdir(parents=True)
    keep = outside / "keep.txt"
    keep.write_text("keep", encoding="utf-8")
    workspace_file = served.runtime.layout.workspace_root / "plan.txt"
    workspace_file.write_text("keep", encoding="utf-8")
    store = AttachmentStore(served.runtime.layout.workspace_root)
    store.delete_files([str(keep), str(workspace_file), "", str(store.root)])
    assert keep.is_file() and workspace_file.is_file()


def test_a_listed_file_opens_while_the_record_exists(served: Served) -> None:
    store = AttachmentStore(served.runtime.layout.workspace_root)
    saved = store.add(FILES_SESSION, "a.txt", b"x")
    record = served.add_turn(files=[{"filename": "a.txt", "kind": "text", "path": saved.path}])
    found = served.web._conversation_file_path(record.session_id, saved.path)
    assert found == Path(saved.path).resolve()


def search(served: Served, query: str) -> Any:
    return served.get("/api/conversations/search?q=" + urllib.parse.quote(query))


def test_search_finds_both_sources_with_a_snippet(served: Served) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    from host_runtime.conversations import ConversationMessage

    web_chat = served.runtime.state.create_conversation(
        ConversationRecord(
            session_id="conversation-a",
            actor=served.runtime.actor,
            title="Chat",
            created_at=now,
            updated_at=now,
            messages=(
                ConversationMessage(
                    message_id="m1",
                    role="user",
                    text="在 Agent Web 問 CMX500 的頻段",
                    created_at=now,
                    status="submitted",
                ),
            ),
        )
    )
    tg = served.add_turn("x" * 100 + " 在 Telegram 問 cmx500 " + "y" * 100)
    reply = search(served, "CMX500")
    assert reply.status == 200
    results = {row["session_id"]: row for row in reply.json()["results"]}
    assert set(results) == {web_chat.session_id, tg.session_id}
    assert results[tg.session_id]["source"] == "telegram"
    assert results[web_chat.session_id]["source"] == "agent_web"
    snippet = results[tg.session_id]["snippet"]
    assert "cmx500" in snippet and len(snippet) < 120
    assert search(served, "頻段").json()["results"][0]["session_id"] == web_chat.session_id


def test_search_of_a_title_only_hit_and_of_nothing(served: Served) -> None:
    served.web.create_conversation()
    assert search(served, "New conversation").json()["results"][0]["snippet"] == ""
    assert search(served, "   ").json() == {"ok": True, "results": []}
    assert search(served, "no such words").json() == {"ok": True, "results": []}


def test_search_refuses_an_overlong_query(served: Served) -> None:
    reply = search(served, "x" * 201)
    assert reply.json() == {"ok": False, "code": "search_query_too_long"}


def test_search_shows_no_raw_chat_id(served: Served) -> None:
    served.add_turn("words to find")
    assert str(CHAT) not in search(served, "words").body.decode()
