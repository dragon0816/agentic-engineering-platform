"""Long and emoji-heavy answers over Telegram (owner report 2026-10-25: the
SDE weekly report came back as "Telegram refused the message").

Telegram measures its 4096 limit in UTF-16 code units, so an emoji counts as
two. Pieces are cut by that measure; a piece Telegram still refuses sends the
whole answer as a Markdown file with a short notice, and every refusal is
logged with Telegram's reason but never the text or the token. Over the fake
Bot API of `test_telegram_ingress`; no socket is opened.
"""

from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_telegram_ingress import (
    OWNER,
    TOKEN,
    FakeReply,
    FakeTransport,
    ingress,
    poll,
    update,
)

import channels.telegram as telegram_module
from channels.telegram import (
    FILE_REPLY_NOTICE,
    HELP,
    MAX_MESSAGE_CHARS,
    UNDELIVERED_REPLY,
    TelegramDelivery,
    chunks,
    utf16_units,
)

TELEGRAM_LIMIT = 4096
TOO_LONG = "Bad Request: message is too long"
#: A sentence that must never appear in the log.
SECRET_LINE = "季度營收 12,345 萬 😀"


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


def test_a_refused_piece_sends_the_whole_answer_as_a_file_with_a_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scratch = tmp_path / "temp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    answer = "第一段\n" + SECRET_LINE + "\n" + "x" * 5000
    # Telegram refuses the second piece only (as if it could not show it).
    transport = RefusingTransport(refuse=lambda text: text.startswith("x"))
    item, _, _ = ingress(tmp_path, transport)
    buttons = ((("Next", "/run next"),),)

    assert item._reply(OWNER, answer, buttons) is True

    assert len(transport.uploads) == 1
    url, body = transport.uploads[0]
    assert url.endswith("/sendDocument")
    assert b'name="document"; filename="answer-' in body and b'.md"' in body
    assert b"Content-Type: text/markdown" in body
    assert answer.encode("utf-8") in body  # the whole answer, not just the refused piece
    notices = [
        payload for url, payload in transport.calls if payload.get("text") == FILE_REPLY_NOTICE
    ]
    assert len(notices) == 1
    assert notices[0]["reply_markup"]["inline_keyboard"][0][0]["text"] == "Next"
    assert UNDELIVERED_REPLY not in transport.sent()
    # The temporary file and its folder are gone.
    assert list(scratch.iterdir()) == []


def test_the_document_failing_too_ends_in_the_undelivered_reply(tmp_path: Path) -> None:
    transport = RefusingTransport(
        [[update(1, OWNER, "/help")]],
        refuse=lambda text: text == HELP,
        document_status=400,
    )
    item, _, _ = ingress(tmp_path, transport)

    result = poll(item)

    assert len(transport.uploads) == 1
    assert result.deliveries[0].replied is False
    assert transport.sent()[-1] == UNDELIVERED_REPLY
    assert FILE_REPLY_NOTICE not in transport.sent()


def test_a_refused_answer_delivered_as_a_file_counts_as_replied(tmp_path: Path) -> None:
    transport = RefusingTransport([[update(1, OWNER, "/help")]], refuse=lambda text: text == HELP)
    item, _, _ = ingress(tmp_path, transport)

    result = poll(item)

    assert result.deliveries[0].replied is True
    assert HELP.encode("utf-8") in transport.uploads[0][1]
    assert transport.sent()[-1] == FILE_REPLY_NOTICE
    assert UNDELIVERED_REPLY not in transport.sent()


def test_a_refusal_is_logged_with_status_and_reason_but_no_text_or_token(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    answer = SECRET_LINE + "\n" + "y" * 100
    transport = RefusingTransport(
        refuse=lambda text: True,
        document_status=400,
        # Telegram's reason carrying the token must still come out redacted.
        description=f"{TOO_LONG} for bot{TOKEN}",
    )
    item, _, _ = ingress(tmp_path, transport)

    with caplog.at_level(logging.WARNING, logger="channels.telegram"):
        assert item._reply(OWNER, answer) is False
        item._edit_reply(OWNER, 5, answer)
        item._send_photo(OWNER, write_file(tmp_path, "chart.png"))

    log = "\n".join(record.getMessage() for record in caplog.records)
    assert "Telegram sendMessage refused: HTTP 400" in log
    assert TOO_LONG in log
    assert f"piece 1 of 1, {utf16_units(answer)} UTF-16 units" in log
    assert "Telegram editMessageText refused: HTTP 400" not in log  # the fake accepts edits
    assert "Telegram sendPhoto refused: HTTP 400 (Bad Request: file empty)" in log
    # The answer was then tried as a file, refused too, and logged by size.
    assert "Telegram sendDocument refused: HTTP 400 (Bad Request: file empty)" in log
    assert all(record.levelno == logging.WARNING for record in caplog.records)
    assert_clean(log)


def test_a_transport_fault_is_logged_without_the_url_or_token(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    transport = FakeTransport(error=OSError(f"proxy reset https://api.telegram.org/bot{TOKEN}/x"))
    item, _, _ = ingress(tmp_path, transport)

    with caplog.at_level(logging.WARNING, logger="channels.telegram"):
        assert item._reply(OWNER, SECRET_LINE) is False
        assert item._send_status(OWNER, SECRET_LINE) is None
        assert item._edit_status(OWNER, 3, SECRET_LINE) is None

    log = "\n".join(record.getMessage() for record in caplog.records)
    assert "OSError" in log and "status message" in log
    assert_clean(log)


def write_file(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_bytes(b"\x89PNG fake")
    return path


def assert_clean(log: str) -> None:
    """No answer text and no part of the token in a log."""
    assert SECRET_LINE not in log and "季度營收" not in log and "y" * 20 not in log
    assert TOKEN not in log and TOKEN.split(":")[1] not in log


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


class LimitedTransport(FakeTransport):
    """Answers the first `limited` `sendMessage` calls with a 429 asking to
    wait `retry_after` seconds, or raises on the first `faults` calls, then
    accepts."""

    def __init__(
        self,
        batches: list[list[dict[str, Any]]],
        limited: int = 0,
        retry_after: int = 1,
        *,
        faults: int = 0,
    ) -> None:
        super().__init__(batches)
        self.limited = limited
        self.retry_after = retry_after
        self.faults = faults
        self.uploads: list[bytes] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        if url.endswith(("/sendDocument", "/sendPhoto")):
            self.uploads.append(body)
            return FakeReply(200, {"ok": True, "result": {"message_id": 5}})
        if url.endswith("/sendMessage") and self.faults > 0:
            self.faults -= 1
            raise TimeoutError("the read operation timed out")
        if url.endswith("/sendMessage") and self.limited > 0:
            self.limited -= 1
            self.calls.append((url, json.loads(body)))
            return FakeReply(
                429,
                {
                    "ok": False,
                    "error_code": 429,
                    "description": f"Too Many Requests: retry after {self.retry_after}",
                    "parameters": {"retry_after": self.retry_after},
                },
            )
        return super().send(url, body, headers, timeout_s)


def test_a_short_answer_waits_out_a_long_rate_limit_instead_of_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A long run's status edits can earn a `retry_after` above 5 s; the answer
    used to retry once after at most 5 s and end in UNDELIVERED_REPLY."""
    waits: list[float] = []
    monkeypatch.setattr("channels.telegram.time.sleep", waits.append)
    transport = LimitedTransport([[update(1, OWNER, "/help")]], limited=2, retry_after=12)
    item, _, _ = ingress(tmp_path, transport)

    with caplog.at_level(logging.WARNING, logger="channels.telegram"):
        result = poll(item)

    assert result.deliveries[0].replied is True
    assert waits == [12, 12]
    assert transport.sent()[-1] == HELP
    assert UNDELIVERED_REPLY not in transport.sent()
    assert transport.uploads == []  # a rate limit is not a reason to send a file
    assert "sendMessage refused: HTTP 429 (Too Many Requests: retry after 12)" in caplog.text


def test_a_rate_limit_that_does_not_end_gives_up_after_a_few_capped_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waits: list[float] = []
    monkeypatch.setattr("channels.telegram.time.sleep", waits.append)
    transport = LimitedTransport([], limited=100, retry_after=600)
    item, _, _ = ingress(tmp_path, transport)

    assert item._reply(OWNER, "短回答") is False

    assert waits == [60.0, 60.0, 60.0]  # capped, and only a few attempts
    assert transport.uploads == []


def test_a_reply_whose_call_timed_out_is_tried_once_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    waits: list[float] = []
    monkeypatch.setattr("channels.telegram.time.sleep", waits.append)
    transport = LimitedTransport([[update(1, OWNER, "/help")]], faults=1)
    item, _, _ = ingress(tmp_path, transport)

    with caplog.at_level(logging.WARNING, logger="channels.telegram"):
        result = poll(item)

    assert result.deliveries[0].replied is True
    assert transport.sent() == [HELP]
    assert waits == [1.0]
    assert "sendMessage failed (attempt 1): TimeoutError" in caplog.text
    # Two faults in a row are a failed answer, and that is said once.
    transport = LimitedTransport([[update(2, OWNER, "/help")]], faults=2)
    item, _, _ = ingress(tmp_path / "again", transport)
    result = poll(item)
    assert result.deliveries[0].replied is False
    assert transport.sent() == [UNDELIVERED_REPLY]


def blank_delivery(photos: tuple[str, ...] = (), workflow: str | None = None) -> TelegramDelivery:
    """A delivery whose text is blank, as the leading hypothesis of the owner
    report had it. The contract refuses one anywhere (see the test after
    these; the poll result validates its deliveries again), so it is built
    without validation to show what `_reply` does as a second line."""
    outcome: Any = (
        None
        if workflow is None
        else SimpleNamespace(
            workflow=SimpleNamespace(run=SimpleNamespace(workflow=SimpleNamespace(name=workflow)))
        )
    )
    return TelegramDelivery.model_construct(
        update_id=1,
        chat_id=OWNER,
        sender_id=OWNER,
        disposition="routed",
        reply="  \n ",
        buttons=(),
        edit_message_id=None,
        photos=photos,
        documents=(),
        replied=False,
        outcome=outcome,
        failure=None,
    )


def test_an_answer_with_no_text_but_files_says_the_workflow_finished(
    tmp_path: Path,
) -> None:
    chart = write_file(tmp_path, "chart.png")
    delivery = blank_delivery((str(chart),), "sde-weekly-report")
    transport = LimitedTransport([])
    item, _, _ = ingress(tmp_path, transport)

    notice = telegram_module._blank_notice(delivery)
    assert item._reply(OWNER, delivery.reply or "", blank=notice) is True
    assert item._send_photo(OWNER, chart) is True

    assert transport.sent() == ["sde-weekly-report 已完成"]
    assert len(transport.uploads) == 1
    assert UNDELIVERED_REPLY not in transport.sent()
    # Files without a Workflow name: just 「已完成」.
    assert telegram_module._blank_notice(blank_delivery((str(chart),))) == "已完成"


def test_an_answer_with_nothing_at_all_sends_a_short_completion_notice(
    tmp_path: Path,
) -> None:
    transport = LimitedTransport([])
    item, _, _ = ingress(tmp_path, transport)

    assert item._reply(OWNER, "  \n ") is True
    assert item._reply(OWNER, " ", blank=telegram_module._blank_notice(blank_delivery())) is True
    named = telegram_module._blank_notice(blank_delivery(workflow="sde-weekly-report"))

    assert transport.sent() == ["已完成（沒有文字結果）"] * 2
    assert named == "sde-weekly-report 已完成（沒有文字結果）"
    assert transport.uploads == []


def test_a_blank_reply_never_reaches_telegram_as_an_undelivered_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The delivery contract refuses a blank reply (`Text`: at least one
    non-space character), so a turn whose text came out empty is a handling
    failure with its own message, never UNDELIVERED_REPLY: that one means
    Telegram itself refused a non-empty answer (owner report 2026-10-25)."""
    monkeypatch.setattr(telegram_module, "_describe", lambda outcome: "  ")
    transport = RefusingTransport([[update(7, OWNER, "shipment.run")]])
    item, _, _ = ingress(tmp_path, transport)

    result = poll(item)

    delivery = result.deliveries[0]
    assert delivery.disposition == "failed"
    assert delivery.failure is not None and "string_pattern_mismatch" in delivery.failure.message
    assert transport.sent() == ["That request could not be handled on this Bridge."]
    assert UNDELIVERED_REPLY not in transport.sent()


class EditRefusingTransport(FakeTransport):
    def __init__(self, description: str) -> None:
        super().__init__()
        self.description = description

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        if url.endswith("/editMessageText"):
            self.calls.append((url, json.loads(body)))
            return FakeReply(400, {"ok": False, "error_code": 400, "description": self.description})
        return super().send(url, body, headers, timeout_s)


def test_an_edit_that_changes_nothing_counts_as_delivered_and_others_fall_back(
    tmp_path: Path,
) -> None:
    unchanged = EditRefusingTransport(
        "Bad Request: message is not modified: specified new message content and reply "
        "markup are exactly the same as a current content and reply markup of the message"
    )
    item, _, _ = ingress(tmp_path, unchanged)
    assert item._edit_reply(OWNER, 4, "same text") is True
    assert unchanged.sent() == []
    # Any other refusal makes the poll loop send the answer as a new message.
    gone = EditRefusingTransport("Bad Request: message to edit not found")
    item, _, _ = ingress(tmp_path / "gone", gone)
    assert item._edit_reply(OWNER, 4, "new text") is False
