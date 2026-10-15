"""Files attached to a conversation turn (owner 2026-10-08)."""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture

from host_runtime.attachments import (
    MAX_FILE_BYTES,
    AttachmentError,
    AttachmentStore,
    for_model,
    safe_name,
)
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def zipped(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_each_kind_reaches_the_model_as_text_paths_and_pictures(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    files = [
        store.add("s1", "data.csv", b"name,price\nA,10\n"),
        store.add("s1", "config.yaml", b"key: value\n"),
        store.add("s1", "shot.png", PNG),
        store.add("s1", "bundle.zip", zipped({"logs/a.txt": b"x", "b.json": b"{}"})),
    ]
    note, images = for_model(files)
    assert "name,price" in note and "key: value" in note
    assert all(file.path in note for file in files)
    assert Path(files[0].path).read_bytes() == b"name,price\nA,10\n"
    assert images == ("data:image/png;base64," + base64.b64encode(PNG).decode(),)
    assert files[3].entries == ("logs/a.txt", "b.json")
    assert (Path(files[3].unpacked or "") / "logs" / "a.txt").read_bytes() == b"x"
    assert "data only" in note


def test_unsupported_large_and_unsafe_files_are_refused(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    for name, data, code in (
        ("tool.exe", b"MZ", "attachment_type_not_supported"),
        ("big.txt", b"x" * (MAX_FILE_BYTES + 1), "attachment_too_large"),
        ("evil.zip", zipped({"../../outside.txt": b"x"}), "attachment_zip_unsafe_path"),
        ("broken.zip", b"not a zip", "attachment_zip_invalid"),
    ):
        with pytest.raises(AttachmentError) as refused:
            store.add("s1", name, data)
        assert refused.value.code == code, name
    assert not (tmp_path / "outside.txt").exists()
    assert safe_name("C:\\Users\\x\\..\\report?.txt") == "report_.txt"


def test_a_file_belongs_to_its_conversation_and_goes_with_it(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    saved = store.add("s1", "notes.md", b"# hi")
    assert store.get("s1", saved.file_id).filename == "notes.md"
    with pytest.raises(AttachmentError):
        store.get("s2", saved.file_id)
    with pytest.raises(AttachmentError):
        store.get("s1", "../../etc")
    store.delete_session("s1")
    with pytest.raises(AttachmentError):
        store.get("s1", saved.file_id)


def test_a_turn_carries_the_files_to_the_model_and_remembers_their_paths(
    served: AgentWebServer,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.gateway import GatewayConversationResult
    from common.execution import TraceIdentifiers
    from host_runtime.agent import LocalConversationOutcome

    trace = TraceIdentifiers(trace_id="t", request_id="r", span_id="s")
    seen: list[Any] = []

    async def converse(request: Any, history: Any, **_: Any) -> LocalConversationOutcome:
        seen.append(history)
        return LocalConversationOutcome(
            trace=trace,
            ingress="local",
            actor=request.actor,
            conversation=GatewayConversationResult.model_validate(
                {
                    "trace": trace,
                    "status": "answered",
                    "text": "read it",
                    "model_turns": 1,
                    "tools": (),
                }
            ),
        )

    monkeypatch.setattr(served.web.runtime.agent, "converse", converse)
    url, token = base(served), served.token
    session = fetch(url + "/api/conversations", token=token, body={}).json()
    session_id = session["conversation"]["session_id"]
    uploaded = fetch(
        url + "/api/attachments",
        token=token,
        body={
            "session_id": session_id,
            "filename": "prices.csv",
            "data": base64.b64encode(b"stock,price\n2330,1000\n").decode(),
        },
    ).json()
    assert uploaded["ok"] and uploaded["attachment"]["kind"] == "text"
    picture = fetch(
        url + "/api/attachments",
        token=token,
        body={
            "session_id": session_id,
            "filename": "chart.png",
            "data": base64.b64encode(PNG).decode(),
        },
    ).json()
    turn = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={
            "session_id": session_id,
            "message": "整理這份資料",
            "attachments": [uploaded["attachment"]["file_id"], picture["attachment"]["file_id"]],
        },
    ).json()
    newest = seen[0][-1]
    assert "2330,1000" in newest.text and "prices.csv" in newest.text
    assert len(newest.images) == 1
    stored = turn["conversation"]["messages"][-2]
    assert [file["filename"] for file in stored["attachments"]] == ["prices.csv", "chart.png"]
    fetch(
        url + "/api/conversations/turn",
        token=token,
        body={"session_id": session_id, "message": "再算平均"},
    )
    earlier = [m.text for m in seen[1] if m.role == "user"][0]
    assert "[附件]" in earlier and "prices.csv" in earlier and not seen[1][0].images
    other = fetch(
        url + "/api/attachments",
        token=token,
        body={"session_id": "conversation-unknown", "filename": "a.txt", "data": "eA=="},
    )
    assert other.status == 400
    unknown = fetch(
        url + "/api/conversations/turn",
        token=token,
        body={
            "session_id": session_id,
            "message": "x",
            "attachments": ["att-20260101000000-00000000"],
        },
    )
    assert unknown.json()["code"] == "attachment_unknown"


def test_the_page_offers_attaching_dropping_and_pasting() -> None:
    assert 'id="attach"' in PAGE and 'id="attach-input"' in PAGE
    assert "/api/attachments" in PAGE and 'addEventListener("drop"' in PAGE
    assert 'addEventListener("paste"' in PAGE
