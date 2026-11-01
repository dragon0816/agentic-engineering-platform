"""Voice input contracts (docs/phases/VOICE_INPUT.md §3, slice V1): the STT
provider interface, the fake provider, the host `voice` section, the Agent Web
request, the Telegram limits checked before a download and the transcript
record with its per-person store and retention."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from voice.contracts import (
    ACCEPTED_MIME_TYPES,
    ERROR_CODES,
    REPLIES,
    TelegramVoice,
    TranscriptView,
    VoiceConfig,
    VoiceTranscribeFailure,
    VoiceTranscribeRequest,
    VoiceTranscribeSuccess,
    accepted_mime,
    declared_limit_error,
)
from voice.stt import FakeSttProvider, Pcm16k, Segment, SttError, SttProvider, SttResult
from voice.transcript import (
    SCHEMA,
    TranscriptAudio,
    TranscriptRecord,
    TranscriptStore,
    TranscriptStt,
    TranscriptUse,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
SHA = "a" * 64


def pcm(seconds: float, value: int = 0) -> Pcm16k:
    sample = value.to_bytes(2, "little", signed=True)
    return Pcm16k(sample * int(seconds * Pcm16k.RATE))


def result(text: str = "幫我查 CMX500 的選項") -> SttResult:
    return SttResult(
        segments=(Segment(0.0, 1.5, " " + text),),
        language="zh",
        duration_seconds=1.5,
        elapsed_seconds=0.2,
        engine="fake",
        model="fake",
        model_revision="fake-1",
    )


# -- STT provider interface ---------------------------------------------------


def test_pcm_duration_and_hash() -> None:
    audio = pcm(2.0)
    assert audio.duration_seconds == pytest.approx(2.0)
    assert audio.sha256 == hashlib.sha256(audio.samples).hexdigest()


def test_pcm_rejects_odd_byte_count() -> None:
    with pytest.raises(ValueError):
        Pcm16k(b"\x00\x00\x00")


def test_result_text_joins_segments_and_trims() -> None:
    two = SttResult(
        segments=(Segment(0.0, 1.0, " 幫我查"), Segment(1.0, 2.0, " CMX500 ")),
        language="zh",
        duration_seconds=2.0,
        elapsed_seconds=0.1,
        engine="fake",
        model="fake",
        model_revision="1",
    )
    assert two.text == "幫我查 CMX500"


def test_stt_error_accepts_only_known_codes() -> None:
    assert SttError("stt_timeout").code == "stt_timeout"
    with pytest.raises(ValueError):
        SttError("something_else")  # type: ignore[arg-type]


def test_fake_provider_by_hash_default_and_error() -> None:
    hello, silence = pcm(1.0, 100), pcm(1.0)
    fake = FakeSttProvider(
        {hello.sha256: result("你好"), silence.sha256: SttError("transcript_empty")},
        default=result("其他"),
    )
    provider: SttProvider = fake
    assert provider.transcribe(hello, language="zh", hints=()).text == "你好"
    assert provider.transcribe(pcm(2.0, 5), language=None, hints=("CMX500",)).text == "其他"
    with pytest.raises(SttError) as raised:
        provider.transcribe(silence, language="zh", hints=())
    assert raised.value.code == "transcript_empty"
    assert [call.language for call in fake.calls] == ["zh", None, "zh"]
    assert fake.calls[1].hints == ("CMX500",)


def test_fake_provider_without_default_fails_unknown_audio() -> None:
    with pytest.raises(SttError) as raised:
        FakeSttProvider({}).transcribe(pcm(1.0), language=None, hints=())
    assert raised.value.code == "stt_failed"


# -- error codes and replies ----------------------------------------------------


def test_every_error_code_has_a_traditional_chinese_reply() -> None:
    assert set(REPLIES) == set(ERROR_CODES)
    assert all(REPLIES[code] for code in ERROR_CODES)
    assert "audio_too_long" in ERROR_CODES and "voice_not_confirmation" in ERROR_CODES


# -- host configuration -------------------------------------------------------


def test_voice_is_off_by_default() -> None:
    config = VoiceConfig()
    assert config.enabled is False
    assert (config.max_seconds, config.max_bytes) == (180, 10 * 1024 * 1024)
    assert config.model == "whisper-small" and config.compute == "int8"


def test_enabled_voice_needs_a_pinned_model() -> None:
    with pytest.raises(ValidationError):
        VoiceConfig(enabled=True)
    with pytest.raises(ValidationError):
        VoiceConfig(enabled=True, model_path="C:/aep/models/whisper-small")
    config = VoiceConfig(enabled=True, model_path="C:/aep/models/whisper-small", model_sha256=SHA)
    assert config.enabled


def test_byte_limit_stays_within_the_bot_api_download_limit() -> None:
    with pytest.raises(ValidationError):
        VoiceConfig(max_bytes=21 * 1024 * 1024)


def test_config_refuses_embedded_secrets() -> None:
    with pytest.raises(ValidationError):
        VoiceConfig(hints=("123456789:" + "A" * 35,))


# -- accepted formats and the limits checked before a download ----------------


@pytest.mark.parametrize(
    "mime",
    ["audio/ogg", "audio/ogg; codecs=opus", "audio/webm;codecs=opus", "AUDIO/MPEG", "audio/x-wav"],
)
def test_accepted_mime(mime: str) -> None:
    assert accepted_mime(mime)


@pytest.mark.parametrize("mime", ["video/mp4", "audio/flac", "", "text/plain"])
def test_refused_mime(mime: str) -> None:
    assert not accepted_mime(mime)


def test_accepted_list_matches_the_design() -> None:
    assert set(ACCEPTED_MIME_TYPES) == {
        "audio/ogg",
        "audio/webm",
        "audio/mpeg",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/wav",
        "audio/x-wav",
    }


def test_declared_limits() -> None:
    config = VoiceConfig()
    assert declared_limit_error(30, 200_000, "audio/ogg", config) is None
    assert declared_limit_error(181, 200_000, "audio/ogg", config) == "audio_too_long"
    assert declared_limit_error(30, 10 * 1024 * 1024 + 1, "audio/ogg", config) == (
        "audio_too_large"
    )
    assert declared_limit_error(30, 200_000, "video/mp4", config) == "audio_unsupported_format"
    # Telegram may leave the size or the type out; the download cap and the
    # decoder check them again.
    assert declared_limit_error(30, None, None, config) is None


# -- Telegram media -----------------------------------------------------------


def test_telegram_voice_from_a_message() -> None:
    voice = TelegramVoice.from_message(
        {
            "voice": {
                "file_id": "AwAC1",
                "file_unique_id": "u1",
                "duration": 7,
                "mime_type": "audio/ogg",
                "file_size": 48213,
            }
        }
    )
    assert voice is not None
    assert (voice.kind, voice.file_id, voice.duration_seconds) == ("voice", "AwAC1", 7)
    audio = TelegramVoice.from_message(
        {"audio": {"file_id": "CQAC2", "duration": 30, "mime_type": "audio/mpeg"}}
    )
    assert audio is not None and audio.kind == "audio" and audio.file_size is None


@pytest.mark.parametrize(
    "message",
    [
        {"text": "hi"},
        {"video_note": {"file_id": "x", "duration": 3}},
        {"voice": {"duration": 3}},
        {"voice": "not a mapping"},
    ],
)
def test_telegram_message_without_usable_voice(message: dict[str, object]) -> None:
    assert TelegramVoice.from_message(message) is None


# -- Agent Web request and response ---------------------------------------------


def test_transcribe_request() -> None:
    request = VoiceTranscribeRequest(
        session_id="c-1", mime_type="audio/webm;codecs=opus", duration_ms=8400, data="AAAA"
    )
    assert request.duration_ms == 8400
    with pytest.raises(ValidationError):
        VoiceTranscribeRequest(session_id="c-1", mime_type="audio/webm", data="")
    with pytest.raises(ValidationError):
        VoiceTranscribeRequest(session_id="c 1", mime_type="audio/webm", data="AAAA")
    with pytest.raises(ValidationError):
        VoiceTranscribeRequest(session_id="c-1", mime_type="audio/webm", data="AAAA", extra="x")  # type: ignore[call-arg]


def test_transcribe_responses() -> None:
    view = TranscriptView(
        id="vt-20261101120000-0a1b2c3d",
        text="幫我查",
        language="zh",
        duration_seconds=8.4,
        engine="faster-whisper",
        model="whisper-small",
        elapsed_seconds=2.1,
    )
    assert VoiceTranscribeSuccess(transcript=view).model_dump(mode="json")["ok"] is True
    failure = VoiceTranscribeFailure.for_code("audio_too_long")
    assert failure.model_dump(mode="json") == {
        "ok": False,
        "code": "audio_too_long",
        "message": REPLIES["audio_too_long"],
    }


# -- transcript record ------------------------------------------------------------


def record(
    store: TranscriptStore,
    *,
    actor: str = "owner",
    session: str = "c-1",
    at: datetime = NOW,
    text: str | None = "幫我查 CMX500",
) -> TranscriptRecord:
    return TranscriptRecord(
        id=store.new_id(),
        channel="web",
        actor=actor,
        session_id=session,
        created_at=at,
        audio=TranscriptAudio(
            sha256=SHA, mime_type="audio/webm", bytes=48213, duration_seconds=7.9
        ),
        stt=TranscriptStt(
            provider="faster-whisper",
            model="whisper-small",
            model_revision=SHA,
            compute="cpu-int8",
            language_requested="zh",
            language_detected="zh",
            settings={"beam_size": 5},
            elapsed_seconds=2.1,
        ),
        text_raw=text,
        text=text,
        post_processing=("opencc:s2twp",) if text else (),
        segments=(Segment(0.0, 3.2, text),) if text else (),
        status="ok" if text else "empty",
        error_code=None if text else "transcript_empty",
    )


def test_record_round_trip_uses_the_schema_name(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path, clock=lambda: NOW)
    item = record(store)
    dumped = item.dump()
    assert dumped["schema"] == SCHEMA == "aep.voice.transcript/v1"
    assert "retained" not in dumped["audio"] and "path" not in dumped["audio"]
    assert TranscriptRecord.model_validate(dumped) == item


def test_record_status_rules(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path)
    with pytest.raises(ValidationError):  # ok without text
        TranscriptRecord.model_validate({**record(store).dump(), "text": None})
    failed = TranscriptRecord.failed(
        id=store.new_id(),
        channel="telegram",
        actor="owner",
        session_id="tg-1",
        created_at=NOW,
        code="audio_too_long",
        audio=TranscriptAudio(mime_type="audio/ogg", bytes=None, duration_seconds=400),
    )
    assert (failed.status, failed.error_code, failed.text) == ("failed", "audio_too_long", None)
    with pytest.raises(ValidationError):
        TranscriptRecord.model_validate({**failed.dump(), "error_code": None})


def test_record_never_holds_a_bot_file_url(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path)
    url = "https://api.telegram.org/file/bot123456:ABC/voice/file_1.oga"
    with pytest.raises(ValidationError):
        TranscriptRecord.model_validate({**record(store).dump(), "text": url, "text_raw": url})


def test_store_saves_per_session_and_person(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path, clock=lambda: NOW)
    mine = store.save(record(store))
    other = store.save(record(store, actor="colleague"))
    folder = tmp_path / "voice" / "transcripts" / hashlib.sha256(b"c-1").hexdigest()[:24]
    assert (folder / f"{mine.id}.json").is_file()
    assert json.loads((folder / f"{mine.id}.json").read_text(encoding="utf-8"))["id"] == mine.id
    assert store.get("owner", "c-1", mine.id) == mine
    assert store.get("owner", "c-1", other.id) is None  # another person's record
    assert store.get("owner", "c-2", mine.id) is None  # another session
    assert store.get("owner", "c-1", "../../etc") is None
    assert [item.id for item in store.list("owner", "c-1")] == [mine.id]


def test_store_marks_how_a_transcript_was_used(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path, clock=lambda: NOW)
    saved = store.save(record(store))
    use = TranscriptUse(turn="turn-1", edited=True, sent_text_sha256=SHA)
    updated = store.mark_used("owner", "c-1", saved.id, use)
    assert updated is not None and updated.used_as == use
    assert store.get("owner", "c-1", saved.id) == updated
    assert store.mark_used("colleague", "c-1", saved.id, use) is None


def test_store_purges_after_the_retention(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path, clock=lambda: NOW)
    old = store.save(record(store, at=NOW - timedelta(days=31)))
    recent = store.save(record(store, at=NOW - timedelta(days=29)))
    assert store.purge(retention_days=30) == 1
    assert store.get("owner", "c-1", old.id) is None
    assert store.get("owner", "c-1", recent.id) == recent


def test_new_ids_are_unique(tmp_path: Path) -> None:
    store = TranscriptStore(tmp_path, clock=lambda: NOW)
    ids = {store.new_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(TranscriptStore.ID.fullmatch(item) for item in ids)
