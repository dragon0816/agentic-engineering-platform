"""Telegram voice messages (docs/phases/VOICE_INPUT.md §2.3, §2.4, §3.3;
slice V4): heard text takes the typed path, shown first; a transcript never
presses a button or confirms a card; voice off keeps today's reply."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_telegram_attachments import FileTransport
from test_telegram_ingress import OWNER, STRANGER, TOKEN, CountingCredentials, config, poll, update
from test_telegram_workflow_flow import _install, _tap

from channels.telegram import CREDENTIAL_REPLY, TelegramIngress
from host_runtime.agent import LocalAgent
from voice.contracts import REPLIES, VoiceConfig
from voice.service import VoiceService
from voice.stt import FakeSttProvider, Segment, SttResult
from voice.transcript import TranscriptStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"
SPEECH = (FIXTURES / "zh_ask.wav").read_bytes()
SESSION = f"telegram-chat-{OWNER}"


def heard(text: str) -> SttResult:
    return SttResult(
        segments=(Segment(0.0, 1.0, text),),
        language="zh",
        duration_seconds=1.0,
        elapsed_seconds=0.01,
        engine="fake",
        model="fake",
        model_revision="1",
    )


def voice_message(
    number: int, *, sender: int = OWNER, caption: str | None = None
) -> dict[str, Any]:
    message = update(number, sender, "")["message"]
    message.pop("text")
    message["voice"] = {"file_id": "speech", "duration": 4, "mime_type": "audio/ogg"}
    if caption is not None:
        message["caption"] = caption
    return {"update_id": number, "message": message}


def build(
    tmp_path: Path, transport: FileTransport, text: str | None, *, enabled: bool = True
) -> tuple[TelegramIngress, LocalAgent, Any, FakeSttProvider]:
    from test_telegram_ingress import ingress

    _, agent, runner = ingress(tmp_path, transport)
    fake = FakeSttProvider(default=heard(text) if text is not None else None)
    voice = (
        VoiceService(VoiceConfig(), fake, TranscriptStore(tmp_path / "workspace"))
        if enabled
        else None
    )
    item = TelegramIngress(
        config(),
        agent,
        CountingCredentials({"telegram_bot": TOKEN}),
        transport=transport,
        voice=voice,
    )
    return item, agent, runner, fake


def sent(transport: FileTransport) -> list[str]:
    return [
        str(payload["text"])
        for url, payload in transport.calls
        if url.endswith(("/sendMessage", "/editMessageText")) and "text" in payload
    ]


def records(tmp_path: Path) -> list[Any]:
    return TranscriptStore(tmp_path / "workspace").list("engineer", SESSION)


def test_voice_off_keeps_the_text_only_reply(tmp_path: Path) -> None:
    transport = FileTransport([[voice_message(1)]], {"speech": SPEECH})
    item, *_ = build(tmp_path, transport, "hello", enabled=False)
    delivery = poll(item).deliveries[0]
    assert (delivery.disposition, delivery.reply) == (
        "unsupported_content",
        "Only text messages are accepted here.",
    )
    assert transport.file_requests() == []


def test_voice_off_with_a_caption_handles_the_caption_as_before(tmp_path: Path) -> None:
    on, off = tmp_path / "on", tmp_path / "off"
    typed_transport = FileTransport([[update(1, OWNER, "/status")]], {})
    typed, *_ = build(off, typed_transport, None, enabled=False)
    captioned = FileTransport([[voice_message(1, caption="/status")]], {"speech": SPEECH})
    item, *_ = build(on, captioned, None, enabled=False)
    assert poll(item).deliveries[0].reply == poll(typed).deliveries[0].reply
    assert captioned.file_requests() == []


def test_a_stranger_s_voice_is_never_downloaded(tmp_path: Path) -> None:
    transport = FileTransport([[voice_message(1, sender=STRANGER)]], {"speech": SPEECH})
    item, _, _, fake = build(tmp_path, transport, "hello")
    assert poll(item).deliveries[0].disposition == "unmapped_sender"
    assert transport.file_requests() == [] and fake.calls == []
    assert not (tmp_path / "workspace" / "voice").exists()


def test_heard_text_is_shown_first_and_answered_as_typed_text(tmp_path: Path) -> None:
    transport = FileTransport([[voice_message(1)]], {"speech": SPEECH})
    item, *_ = build(tmp_path / "voice", transport, "/status")
    spoken = poll(item).deliveries[0]
    typed_transport = FileTransport([[update(1, OWNER, "/status")]], {})
    typed, *_ = build(tmp_path / "typed", typed_transport, None, enabled=False)
    assert spoken.reply == poll(typed).deliveries[0].reply
    shown = sent(transport)
    assert shown[0] == "🎤 轉文字中…"
    assert shown[1] == "🎤 你說：「/status」"
    [record] = records(tmp_path / "voice")
    assert record.status == "ok" and record.used_as is not None
    assert record.used_as.turn == "telegram-update-1" and record.used_as.edited is False


def test_a_caption_comes_before_the_transcript(tmp_path: Path) -> None:
    transport = FileTransport([[voice_message(1, caption="關於週報")]], {"speech": SPEECH})
    item, *_ = build(tmp_path, transport, "幫我查")
    seen: list[str] = []
    original = item._request

    def capture(update: Any, actor: str, text: str) -> Any:
        seen.append(text)
        return original(update, actor, text)

    item._request = capture  # type: ignore[method-assign]
    poll(item)
    assert seen == ["關於週報\n\n幫我查"]


def test_a_failed_transcription_says_so_and_reaches_nothing(tmp_path: Path) -> None:
    transport = FileTransport([[voice_message(1)]], {"speech": SPEECH})
    item, agent, runner, _ = build(tmp_path, transport, None)  # the fake fails
    delivery = poll(item).deliveries[0]
    assert delivery.reply == REPLIES["stt_failed"] and delivery.outcome is None
    assert "🎤 語音沒有轉成文字。" in sent(transport)
    assert runner.bridge.events == ()
    assert records(tmp_path)[0].error_code == "stt_failed"


def card(tmp_path: Path, spoken: str) -> tuple[TelegramIngress, FileTransport, Any]:
    transport = FileTransport(
        [[update(1, OWNER, "run release-validation-form package=quick")]], {"speech": SPEECH}
    )
    item, agent, runner, _ = build(tmp_path, transport, spoken)
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    waiting = poll(item).deliveries[0]
    assert waiting.buttons == ((("確認執行", "run:yes"), ("修改", "run:edit")),)
    return item, transport, runner


def test_spoken_yes_with_punctuation_never_runs_the_card(tmp_path: Path) -> None:
    item, transport, runner = card(tmp_path, "好。")
    transport.batches.append([voice_message(2)])
    refused = poll(item).deliveries[0]
    assert refused.reply == REPLIES["voice_not_confirmation"]
    assert item._flows and runner.bridge.events == ()
    transport.batches.append([_tap(3, OWNER, "run:yes", transport)])
    assert poll(item).deliveries[0].outcome is not None  # the button still works


def test_spoken_cancel_with_punctuation_cancels(tmp_path: Path) -> None:
    item, transport, runner = card(tmp_path, "取消！")
    transport.batches.append([voice_message(2)])
    assert poll(item).deliveries[0].reply == "Cancelled."
    assert not item._flows and runner.bridge.events == ()


def test_spoken_edit_opens_editing(tmp_path: Path) -> None:
    item, transport, _ = card(tmp_path, "修改。")
    transport.batches.append([voice_message(2)])
    poll(item)
    state = next(iter(item._flows.values()))
    assert state.choosing and not state.confirming


def test_a_transcript_never_acts_as_button_data(tmp_path: Path) -> None:
    transport = FileTransport([[voice_message(1)]], {"speech": SPEECH})
    item, _, runner, _ = build(tmp_path, transport, "approve:ap-123")
    assert poll(item).deliveries[0].reply == REPLIES["voice_not_confirmation"]
    assert runner.bridge.events == ()


def test_typed_yes_still_confirms_with_voice_on(tmp_path: Path) -> None:
    item, transport, _ = card(tmp_path, "unused")
    transport.batches.append([update(2, OWNER, "好")])
    assert poll(item).deliveries[0].outcome is not None


def test_spoken_credentials_are_refused_like_typed_ones(tmp_path: Path) -> None:
    """Owner 2026-11-01: voice follows the typed rule; nothing is forwarded,
    shown or stored."""
    secret = "123456789:" + "A" * 35
    transport = FileTransport([[voice_message(1)]], {"speech": SPEECH})
    item, _, runner, _ = build(tmp_path / "voice", transport, f"token {secret}")
    spoken = poll(item).deliveries[0]
    typed_transport = FileTransport([[update(1, OWNER, f"token {secret}")]], {})
    typed, *_ = build(tmp_path / "typed", typed_transport, None, enabled=False)
    expected = poll(typed).deliveries[0]
    assert (spoken.disposition, spoken.reply) == (expected.disposition, expected.reply)
    assert spoken.reply == CREDENTIAL_REPLY == REPLIES["transcript_credential"]
    assert runner.bridge.events == ()
    assert all(secret not in text and "你說" not in text for text in sent(transport))
    [record] = records(tmp_path / "voice")
    assert (record.status, record.error_code, record.text) == (
        "failed",
        "transcript_credential",
        None,
    )
    stored = "".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "voice" / "workspace").rglob("*.json")
    )
    assert secret not in stored
