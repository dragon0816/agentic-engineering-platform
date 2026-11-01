"""Decoding and the transcription service (docs/phases/VOICE_INPUT.md §2.2,
§3.6, §7.1 c; slice V2). Runs without the optional `voice` extra: WAV audio is
read with the standard library, and the engine is `FakeSttProvider`."""

from __future__ import annotations

import asyncio
import io
import json
import threading
import wave
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from host_runtime.contracts import CompanyHostConfiguration
from voice import audio
from voice.contracts import VoiceConfig
from voice.service import VoiceService
from voice.stt import FakeSttProvider, Pcm16k, Segment, SttError, SttProvider, SttResult
from voice.transcript import TranscriptRecord, TranscriptStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"
MANIFEST = {
    entry["name"]: entry
    for entry in json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["fixtures"]
}
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def fixture(name: str) -> bytes:
    return (FIXTURES / str(MANIFEST[name]["file"])).read_bytes()


def answer(text: str, language: str | None = "zh") -> SttResult:
    return SttResult(
        segments=(Segment(0.0, 1.0, text),),
        language=language,
        duration_seconds=1.0,
        elapsed_seconds=0.01,
        engine="fake",
        model="fake-model",
        model_revision="fake-1",
    )


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


def service(
    tmp_path: Path,
    provider: SttProvider | None = None,
    *,
    config: VoiceConfig | None = None,
    clock: Clock | None = None,
    **options: object,
) -> VoiceService:
    chosen = provider or FakeSttProvider(default=answer("幫我查 CMX500"))
    return VoiceService(
        config or VoiceConfig(hints=("CMX500",)),
        chosen,
        TranscriptStore(tmp_path, clock=clock or Clock()),
        **options,  # type: ignore[arg-type]
    )


def files_under(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


# -- decoding -------------------------------------------------------------------


def test_wav_decodes_without_the_voice_extra() -> None:
    pcm = audio.decode(fixture("zh_ask"), "audio/wav", VoiceConfig())
    assert isinstance(pcm, Pcm16k)
    assert pcm.duration_seconds == pytest.approx(MANIFEST["zh_ask"]["duration_seconds"], abs=0.01)


def test_wav_content_is_read_whatever_type_was_declared() -> None:
    """A test server may send WAV bytes as a Telegram voice note."""
    pcm = audio.decode(fixture("tone_1khz_1s"), "audio/ogg", VoiceConfig())
    assert pcm.duration_seconds == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("name", "mime", "code"),
    [
        ("zh_ask", "video/mp4", "audio_unsupported_format"),
        ("empty", "audio/wav", "audio_decode_failed"),
        ("truncated", "audio/wav", "audio_decode_failed"),
    ],
)
def test_decode_failures(name: str, mime: str, code: str) -> None:
    with pytest.raises(SttError) as raised:
        audio.decode(fixture(name), mime, VoiceConfig())
    assert raised.value.code == code


def test_decode_refuses_too_many_bytes_and_seconds() -> None:
    with pytest.raises(SttError) as raised:
        audio.decode(fixture("zh_ask"), "audio/wav", VoiceConfig(max_bytes=1000))
    assert raised.value.code == "audio_too_large"
    with pytest.raises(SttError) as raised:
        audio.decode(fixture("silence_2s"), "audio/wav", VoiceConfig(max_seconds=1))
    assert raised.value.code == "audio_too_long"


def test_compressed_audio_without_the_voice_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio, "_import_av", lambda: None)
    with pytest.raises(SttError) as raised:
        audio.decode(b"OggS" + bytes(60), "audio/ogg", VoiceConfig())
    assert raised.value.code == "stt_unavailable"


def _wav(rate: int, channels: int, width: int, seconds: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(bytes(int(rate * seconds) * channels * width))
    return buffer.getvalue()


def test_any_16_bit_wav_decodes_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(audio, "_import_av", lambda: None)
    pcm = audio.decode(_wav(44_100, 2, 2, 1.5), "audio/wav", VoiceConfig())
    assert pcm.duration_seconds == pytest.approx(1.5, abs=0.01)
    pcm = audio.decode(_wav(8_000, 1, 2, 2.0), "audio/x-wav", VoiceConfig())
    assert pcm.duration_seconds == pytest.approx(2.0, abs=0.01)


def test_decode_precedence_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not audio -> decode failed; an unusual WAV -> unsupported format; a
    real compressed container -> the decoder is unavailable (§3.6)."""
    monkeypatch.setattr(audio, "_import_av", lambda: None)
    cases = [
        (fixture("not_audio"), "audio/wav", "audio_decode_failed"),
        (fixture("truncated"), "audio/wav", "audio_decode_failed"),
        (_wav(16_000, 1, 1, 1.0), "audio/wav", "audio_unsupported_format"),
        (b"OggS" + bytes(60), "audio/ogg", "stt_unavailable"),
    ]
    for data, mime, code in cases:
        with pytest.raises(SttError) as raised:
            audio.decode(data, mime, VoiceConfig())
        assert raised.value.code == code, (mime, code)


def test_content_that_is_not_audio_fails_to_decode_without_the_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audio, "_import_av", lambda: None)
    with pytest.raises(SttError) as raised:
        audio.decode(fixture("not_audio"), "audio/ogg", VoiceConfig())
    assert raised.value.code == "audio_decode_failed"


# -- the service ----------------------------------------------------------------


def test_transcribes_saves_and_passes_language_and_hints(tmp_path: Path) -> None:
    fake = FakeSttProvider(default=answer(" 幫我查 CMX500 "))
    record = service(tmp_path, fake).transcribe(
        fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1"
    )
    assert record.status == "ok" and record.text == "幫我查 CMX500"
    assert record.audio.bytes == len(fixture("zh_ask"))
    assert record.audio.mime_type == "audio/wav"
    assert record.audio.duration_seconds == pytest.approx(
        MANIFEST["zh_ask"]["duration_seconds"], abs=0.01
    )
    assert record.stt is not None and record.stt.model == "fake-model"
    assert [(call.language, call.hints) for call in fake.calls] == [("zh", ("CMX500",))]
    assert service(tmp_path).store.get("owner", "c-1", record.id) == record
    view = record.view()
    assert (view.id, view.text, view.engine) == (record.id, "幫我查 CMX500", "fake")


def test_traditional_conversion_is_recorded(tmp_path: Path) -> None:
    fake = FakeSttProvider(default=answer("帮我查选单"))
    record = service(
        tmp_path, fake, to_traditional=lambda text: text.replace("帮", "幫").replace("选", "選")
    ).transcribe(fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1")
    assert (record.text_raw, record.text) == ("帮我查选单", "幫我查選单")
    assert record.post_processing == ("opencc:s2twp", "strip")


@pytest.mark.parametrize("heard", ["", "  ", "。", "..."])
def test_nothing_heard_is_an_empty_transcript(tmp_path: Path, heard: str) -> None:
    record = service(tmp_path, FakeSttProvider(default=answer(heard))).transcribe(
        fixture("silence_2s"), "audio/wav", channel="telegram", actor="owner", session_id="tg-1"
    )
    assert (record.status, record.error_code, record.text) == ("empty", "transcript_empty", None)


def test_engine_errors_become_failed_records(tmp_path: Path) -> None:
    class Broken:
        def transcribe(
            self, pcm: Pcm16k, *, language: str | None, hints: tuple[str, ...]
        ) -> SttResult:
            raise RuntimeError("engine exploded")

    record = service(tmp_path, Broken()).transcribe(
        fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1"
    )
    assert (record.status, record.error_code) == ("failed", "stt_failed")
    record = service(tmp_path, FakeSttProvider(default=SttError("stt_unavailable"))).transcribe(
        fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1"
    )
    assert record.error_code == "stt_unavailable"


def test_declared_limits_fail_before_decoding(tmp_path: Path) -> None:
    fake = FakeSttProvider(default=answer("x"))
    record = service(tmp_path, fake).transcribe(
        fixture("zh_ask"),
        "audio/ogg",
        channel="telegram",
        actor="owner",
        session_id="tg-1",
        declared_seconds=400,
    )
    assert record.error_code == "audio_too_long" and fake.calls == []


def test_a_model_that_cannot_load_is_unavailable(tmp_path: Path) -> None:
    missing = FakeSttProvider(default=SttError("stt_unavailable"))
    record = VoiceService(
        VoiceConfig(), missing, TranscriptStore(tmp_path, clock=Clock())
    ).transcribe(fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1")
    assert record.error_code == "stt_unavailable"


def test_timeout(tmp_path: Path) -> None:
    release = threading.Event()

    class Slow:
        def transcribe(
            self, pcm: Pcm16k, *, language: str | None, hints: tuple[str, ...]
        ) -> SttResult:
            release.wait(10)
            return answer("late")

    voice = service(tmp_path, Slow(), config=VoiceConfig(timeout_seconds=1))
    try:
        record = voice.transcribe(
            fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1"
        )
        assert record.error_code == "stt_timeout"
    finally:
        release.set()
        voice.close()


def test_one_at_a_time_and_a_full_queue_is_busy(tmp_path: Path) -> None:
    started, release = threading.Event(), threading.Event()

    class Held:
        def transcribe(
            self, pcm: Pcm16k, *, language: str | None, hints: tuple[str, ...]
        ) -> SttResult:
            started.set()
            release.wait(10)
            return answer("first")

    voice = service(tmp_path, Held(), config=VoiceConfig(queue=0))
    results: list[TranscriptRecord] = []
    first = threading.Thread(
        target=lambda: results.append(
            voice.transcribe(
                fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1"
            )
        )
    )
    first.start()
    try:
        assert started.wait(10)
        busy = voice.transcribe(
            fixture("zh_ask"), "audio/wav", channel="web", actor="owner", session_id="c-1"
        )
        assert busy.error_code == "stt_busy"
    finally:
        release.set()
        first.join(10)
        voice.close()
    assert results[0].status == "ok"


def test_the_model_is_unloaded_when_idle(tmp_path: Path) -> None:
    class Unloadable(FakeSttProvider):
        unloads = 0

        def unload(self) -> None:
            self.unloads += 1

    provider = Unloadable(default=answer("hi"))
    clock = Clock()
    voice = VoiceService(
        VoiceConfig(idle_unload_seconds=60), provider, TranscriptStore(tmp_path, clock=clock)
    )
    assert voice.unload_if_idle() is False  # nothing loaded yet
    voice.transcribe(fixture("zh_ask"), "audio/wav", channel="web", actor="o", session_id="c")
    clock.now += timedelta(seconds=30)
    assert voice.unload_if_idle() is False
    clock.now += timedelta(seconds=31)
    assert voice.unload_if_idle() is True
    assert provider.unloads == 1
    assert voice.unload_if_idle() is False  # already unloaded
    voice.transcribe(fixture("zh_ask"), "audio/wav", channel="web", actor="o", session_id="c")
    assert len(provider.calls) == 2


def test_no_audio_is_ever_written(tmp_path: Path) -> None:
    """Owner 2026-11-01: keep the transcript only, after success and failure."""
    voice = service(tmp_path)
    voice.transcribe(fixture("zh_ask"), "audio/wav", channel="web", actor="o", session_id="c")
    voice.transcribe(fixture("truncated"), "audio/wav", channel="web", actor="o", session_id="c")
    voice.transcribe(fixture("zh_ask"), "video/mp4", channel="web", actor="o", session_id="c")
    written = files_under(tmp_path)
    assert len(written) == 3
    assert all(name.startswith("voice/transcripts/") and name.endswith(".json") for name in written)


def test_leftover_temporary_audio_is_swept_on_start(tmp_path: Path) -> None:
    leftover = tmp_path / "voice" / "tmp" / "crash.ogg"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"audio")
    service(tmp_path)
    assert not leftover.exists()


def test_async_transcription(tmp_path: Path) -> None:
    voice = service(tmp_path)
    record = asyncio.run(
        voice.transcribe_async(
            fixture("zh_ask"), "audio/wav", channel="telegram", actor="o", session_id="tg"
        )
    )
    assert record.status == "ok"


# -- host.json ------------------------------------------------------------------


def _host(**extra: object) -> dict[str, object]:
    return {
        "device": {
            "bridge_id": "bridge-1",
            "registered_by": "engineer",
            "device_kind": "company_workstation",
            "windows_account_mode": "dedicated_user",
            "resource_scope": "corporate_internal",
            "local_isolation": "single_user",
        },
        "workspace_root": "C:/aep/workspace",
        **extra,
    }


def test_host_json_without_voice_is_unchanged() -> None:
    config = CompanyHostConfiguration.model_validate(_host())
    assert config.voice is None
    assert "voice" not in config.model_dump(exclude_defaults=True)


def test_host_json_voice_section() -> None:
    config = CompanyHostConfiguration.model_validate(
        _host(
            voice={
                "enabled": True,
                "model_path": "C:/aep/models/whisper-small",
                "model_sha256": "b" * 64,
            }
        )
    )
    assert config.voice is not None and config.voice.enabled
