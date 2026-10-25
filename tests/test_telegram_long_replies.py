"""Long and emoji-heavy answers over Telegram (owner report 2026-10-25: the
SDE weekly report came back as "Telegram refused the message").

Telegram measures its 4096 limit in UTF-16 code units, so an emoji counts as
two. Pieces are cut by that measure. Over the fake Bot API of
`test_telegram_ingress`; no socket is opened.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from test_telegram_ingress import OWNER, FakeReply, FakeTransport, ingress

from channels.telegram import MAX_MESSAGE_CHARS, chunks, utf16_units

TELEGRAM_LIMIT = 4096
TOO_LONG = "Bad Request: message is too long"


def emoji_answer(length: int = 4000) -> str:
    """`length` code points, most of them astral (two UTF-16 units each)."""
    line = "😀🚀📈 進度 ✅ 🎯🔥\n"
    return (line * (length // len(line) + 1))[:length]


class RefusingTransport(FakeTransport):
    """Refuses every `sendMessage` whose text satisfies `refuse` with a 400
    and Telegram's description; takes `sendDocument` (multipart) with
    `document_status`, recording each upload."""

    def __init__(
        self,
        batches: list[list[dict[str, Any]]] | None = None,
        *,
        refuse: Any = None,
        document_status: int = 200,
        description: str = TOO_LONG,
    ) -> None:
        super().__init__(batches)
        self.refuse = refuse or (lambda text: False)
        self.document_status = document_status
        self.description = description
        self.uploads: list[tuple[str, bytes]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        method = url.rsplit("/", 1)[-1]
        if method in ("sendDocument", "sendPhoto"):
            self.uploads.append((url, body))
            if self.document_status != 200:
                return FakeReply(
                    self.document_status,
                    {"ok": False, "error_code": 400, "description": "Bad Request: file empty"},
                )
            return FakeReply(200, {"ok": True, "result": {"message_id": 77}})
        if method == "sendMessage" and self.refuse(json.loads(body)["text"]):
            self.calls.append((url, json.loads(body)))
            return FakeReply(400, {"ok": False, "error_code": 400, "description": self.description})
        return super().send(url, body, headers, timeout_s)


def test_an_emoji_heavy_answer_is_cut_by_utf16_units_without_breaking_a_pair() -> None:
    answer = emoji_answer()
    assert len(answer) == 4000
    assert utf16_units(answer) > TELEGRAM_LIMIT  # one piece by code points was refused
    pieces = list(chunks(answer))
    assert len(pieces) > 1
    assert all(utf16_units(piece) <= MAX_MESSAGE_CHARS <= TELEGRAM_LIMIT for piece in pieces)
    for piece in pieces:
        piece.encode("utf-16-le")  # a lone surrogate would raise here
    assert "\n".join(pieces).replace("\n", "") == answer.replace("\n", "")
    # The cut still prefers a newline: every piece but the last ends a line.
    assert all(answer.find(piece + "\n") >= 0 for piece in pieces[:-1])
    # A run of emoji with no newline is cut between characters, never inside one.
    solid = "😀" * 2500
    hard = list(chunks(solid))
    assert [utf16_units(piece) for piece in hard] == [4000, 1000]
    assert "".join(hard) == solid
    # An odd limit cannot hold half an emoji: the cut falls before it.
    assert list(chunks("a😀😀", 4)) == ["a😀", "😀"]
    # Plain text is cut exactly as before.
    assert list(chunks("x" * 8001, 4000)) == ["x" * 4000, "x" * 4000, "x"]


def test_each_piece_sent_is_within_telegrams_limit(tmp_path: Path) -> None:
    transport = RefusingTransport(refuse=lambda text: utf16_units(text) > TELEGRAM_LIMIT)
    item, _, _ = ingress(tmp_path, transport)
    answer = emoji_answer()

    assert item._reply(OWNER, answer) is True

    sent = transport.sent()
    assert len(sent) > 1
    assert all(utf16_units(text) <= TELEGRAM_LIMIT for text in sent)
    assert transport.uploads == []


def test_status_messages_and_edits_stay_within_the_limit(tmp_path: Path) -> None:
    transport = RefusingTransport(refuse=lambda text: utf16_units(text) > TELEGRAM_LIMIT)
    item, _, _ = ingress(tmp_path, transport)
    long_status = emoji_answer(5000)

    assert item._send_status(OWNER, long_status) is not None
    item._edit_status(OWNER, 1, long_status)
    edits = [payload for url, payload in transport.calls if url.endswith("/editMessageText")]
    assert utf16_units(edits[-1]["text"]) <= MAX_MESSAGE_CHARS
    # A multi-select edit too long by Telegram's measure is not attempted;
    # the caller then sends a new message.
    assert item._edit_reply(OWNER, 1, emoji_answer(3000)) is False
    assert len([url for url, _ in transport.calls if url.endswith("/editMessageText")]) == 1
