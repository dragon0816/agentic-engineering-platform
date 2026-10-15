"""Files and photos sent to the Telegram channel (owner 2026-10-08).

Driven over the same fake Bot API as `test_telegram_ingress`: `getFile`
answers with a file path and the download is a GET the fake serves from
memory. No socket is opened.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from test_telegram_ingress import (
    OWNER,
    STRANGER,
    TOKEN,
    CountingCredentials,
    FakeReply,
    FakeTransport,
    ingress,
    poll,
)

from channels.telegram import DEFAULT_CAPTION, SUPPORTED_TYPES, TelegramIngress
from host_runtime.attachments import MAX_FILE_BYTES, AttachmentStore
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class BytesReply:
    def __init__(self, status: int, data: bytes) -> None:
        self.status = status
        self._data = data

    def chunks(self) -> Any:
        yield self._data

    def close(self) -> None:
        return None


class FileTransport(FakeTransport):
    """Also answers `getFile` and serves downloads by GET from `files`,
    keyed by Telegram file id."""

    def __init__(
        self,
        batches: list[list[dict[str, Any]]],
        files: dict[str, bytes],
        *,
        download_status: int = 200,
    ) -> None:
        super().__init__(batches)
        self.files = files
        self.download_status = download_status
        self.downloads: list[str] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        if url.endswith("/getFile"):
            payload = json.loads(body)
            self.calls.append((url, payload))
            file_id = payload["file_id"]
            return FakeReply(
                200,
                {
                    "ok": True,
                    "result": {
                        "file_id": file_id,
                        "file_path": f"documents/{file_id}.bin",
                        "file_size": len(self.files[file_id]),
                    },
                },
            )
        return super().send(url, body, headers, timeout_s)

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> BytesReply:
        assert method == "GET" and body is None
        self.downloads.append(url)
        file_id = url.rsplit("/", 1)[-1].removesuffix(".bin")
        return BytesReply(self.download_status, self.files[file_id])

    def file_requests(self) -> list[str]:
        return [payload["file_id"] for url, payload in self.calls if url.endswith("/getFile")]


class Seeing:
    """A model that records every request it was given."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, text="I looked at it."
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def message(
    update_id: int,
    sender: int,
    *,
    caption: str | None = None,
    document: dict[str, Any] | None = None,
    photo: list[dict[str, Any]] | None = None,
    group: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "message_id": update_id,
        "chat": {"id": sender, "type": "private"},
        "from": {"id": sender, "is_bot": False, "first_name": "someone"},
    }
    if caption is not None:
        item["caption"] = caption
    if document is not None:
        item["document"] = document
    if photo is not None:
        item["photo"] = photo
    if group is not None:
        item["media_group_id"] = group
    return {"update_id": update_id, "message": item}


def photo_sizes(file_id: str) -> list[dict[str, Any]]:
    # Telegram lists a photo's sizes small to large; the largest is taken.
    return [
        {
            "file_id": f"{file_id}-small",
            "file_unique_id": "s",
            "width": 90,
            "height": 90,
            "file_size": 10,
        },
        {
            "file_id": file_id,
            "file_unique_id": f"u{file_id}",
            "width": 800,
            "height": 800,
            "file_size": len(PNG),
        },
    ]


def attached(
    tmp_path: Path,
    transport: FileTransport,
    resolver: CountingCredentials | None = None,
) -> tuple[TelegramIngress, Seeing, AttachmentStore]:
    item, agent, _ = ingress(tmp_path, transport, resolver=resolver)
    store = AttachmentStore(tmp_path / "workspace")
    item.attachments = store
    model = Seeing()
    agent.gateway.router.model = model
    return item, model, store


def everything_said(item: TelegramIngress, transport: FakeTransport, tmp_path: Path) -> str:
    """Every reply, stored history message and file written under the workspace."""
    stored = [
        message.model_dump_json() for history in item._histories.values() for message in history
    ]
    written = [
        path.read_text("utf-8", "replace")
        for path in (tmp_path / "workspace").rglob("*")
        if path.is_file()
    ]
    return "\n".join([*transport._messages(), *stored, *written])


def test_a_document_reaches_the_model_as_text_and_history_keeps_only_its_path(
    tmp_path: Path,
) -> None:
    files = {"doc1": b"name,price\nWidget,42\n"}
    transport = FileTransport(
        [
            [
                message(
                    1,
                    OWNER,
                    caption="summarise this",
                    document={"file_id": "doc1", "file_name": "prices.csv", "file_size": 21},
                )
            ]
        ],
        files,
    )
    item, model, _ = attached(tmp_path, transport)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered" and delivery.reply == "I looked at it."
    (request,) = model.requests
    newest = request.messages[-1]
    assert newest.role == "user" and newest.text.startswith("summarise this")
    assert "Widget,42" in newest.text and "prices.csv" in newest.text
    assert newest.images == ()
    # The stored question lists the file's name and path, not its content.
    (history,) = item._histories.values()
    remembered = history[0].text
    assert "[附件]" in remembered and "- prices.csv (text): " in remembered
    saved = Path(remembered.split("(text): ", 1)[1].strip())
    assert saved.read_bytes() == files["doc1"]
    assert "Widget,42" not in remembered


def test_a_photo_takes_the_largest_size_and_the_model_sees_it(tmp_path: Path) -> None:
    transport = FileTransport([[message(1, OWNER, photo=photo_sizes("pic1"))]], {"pic1": PNG})
    item, model, _ = attached(tmp_path, transport)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered"
    assert transport.file_requests() == ["pic1"]
    newest = model.requests[0].messages[-1]
    # No caption: the default words stand in for it.
    assert newest.text.startswith(DEFAULT_CAPTION)
    assert newest.images == ("data:image/jpeg;base64," + base64.b64encode(PNG).decode(),)
    assert model.requests[0].requirements.vision is True


def test_an_album_in_one_batch_is_one_turn(tmp_path: Path) -> None:
    files = {"a": PNG, "b": PNG}
    transport = FileTransport(
        [
            [
                message(1, OWNER, photo=photo_sizes("a"), group="album-1"),
                message(2, OWNER, photo=photo_sizes("b"), group="album-1", caption="compare these"),
            ]
        ],
        files,
    )
    item, model, _ = attached(tmp_path, transport)
    result = poll(item)
    assert len(result.deliveries) == 1 and result.next_offset == 3
    assert transport.sent() == ["I looked at it."]
    (request,) = model.requests
    newest = request.messages[-1]
    assert newest.text.startswith("compare these") and len(newest.images) == 2


def test_unsupported_and_oversized_files_are_refused_before_any_download(
    tmp_path: Path,
) -> None:
    transport = FileTransport(
        [
            [
                message(
                    1, OWNER, document={"file_id": "x", "file_name": "tool.exe", "file_size": 2}
                ),
                message(
                    2,
                    OWNER,
                    document={
                        "file_id": "y",
                        "file_name": "big.pdf",
                        "file_size": 21 * 1024 * 1024,
                    },
                ),
                message(
                    3,
                    OWNER,
                    document={
                        "file_id": "z",
                        "file_name": "huge.zip",
                        "file_size": MAX_FILE_BYTES + 1,
                    },
                ),
                *[
                    message(10 + n, OWNER, photo=photo_sizes(f"p{n}"), group="many")
                    for n in range(11)
                ],
            ]
        ],
        {},
    )
    item, model, _ = attached(tmp_path, transport)
    result = poll(item)
    replies = [delivery.reply or "" for delivery in result.deliveries]
    assert [d.disposition for d in result.deliveries] == ["unsupported_content"] * 4
    assert SUPPORTED_TYPES in replies[0] and "png" in replies[0] and "zip" in replies[0]
    assert "20 MB" in replies[1]
    assert "25 MB" in replies[2]
    assert "10" in replies[3]
    assert transport.file_requests() == [] and transport.downloads == []
    assert model.requests == []


def test_a_stranger_s_file_is_never_downloaded(tmp_path: Path) -> None:
    resolver = CountingCredentials({"telegram_bot": TOKEN})
    transport = FileTransport(
        [
            [
                message(
                    1, STRANGER, document={"file_id": "doc1", "file_name": "a.txt", "file_size": 1}
                )
            ]
        ],
        {"doc1": b"x"},
    )
    item, model, _ = attached(tmp_path, transport, resolver)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "unmapped_sender" and delivery.reply is None
    assert transport.file_requests() == [] and transport.downloads == []
    assert resolver.resolved == 1 and model.requests == []
    assert not (tmp_path / "workspace").exists()


def test_the_token_never_reaches_a_reply_the_history_or_a_saved_file(tmp_path: Path) -> None:
    transport = FileTransport(
        [
            [
                message(
                    1,
                    OWNER,
                    caption="read it",
                    document={"file_id": "doc1", "file_name": "notes.md", "file_size": 5},
                )
            ],
        ],
        {"doc1": b"hello"},
    )
    item, model, _ = attached(tmp_path, transport)
    assert poll(item).deliveries[0].disposition == "answered"
    # The download itself used the token, through the bot's transport only.
    assert transport.downloads == [f"https://api.telegram.org/file/bot{TOKEN}/documents/doc1.bin"]
    sent_to_model = "\n".join(m.text for r in model.requests for m in r.messages)
    assert TOKEN not in everything_said(item, transport, tmp_path)
    assert TOKEN not in sent_to_model and "api.telegram.org" not in sent_to_model


def test_a_failed_download_is_a_readable_reply_without_the_token(tmp_path: Path) -> None:
    transport = FileTransport(
        [[message(1, OWNER, document={"file_id": "doc1", "file_name": "a.txt", "file_size": 1})]],
        {"doc1": b"x"},
        download_status=404,
    )
    item, model, _ = attached(tmp_path, transport)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered"
    assert "無法從 Telegram 下載附件" in (delivery.reply or "")
    assert TOKEN not in delivery.model_dump_json()
    assert model.requests == [] and item._histories == {}


def test_new_forgets_the_chat_s_files(tmp_path: Path) -> None:
    transport = FileTransport(
        [
            [message(1, OWNER, document={"file_id": "doc1", "file_name": "a.txt", "file_size": 1})],
            [
                {
                    "update_id": 2,
                    "message": {
                        "message_id": 2,
                        "chat": {"id": OWNER, "type": "private"},
                        "from": {"id": OWNER, "is_bot": False, "first_name": "someone"},
                        "text": "/new",
                    },
                }
            ],
        ],
        {"doc1": b"x"},
    )
    item, _, _ = attached(tmp_path, transport)
    poll(item)
    root = tmp_path / "workspace" / "attachments"
    assert any(root.iterdir())
    assert poll(item).deliveries[0].reply == "Started a fresh conversation."
    assert not any(root.iterdir())
