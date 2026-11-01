"""Compressed audio and Traditional conversion with the optional `voice` extra
(PyAV, OpenCC); skipped where it is not installed, as in CI. The compressed
variants are encoded here from the committed WAV fixtures, in memory."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from voice import audio
from voice.contracts import VoiceConfig
from voice.service import _opencc
from voice.stt import SttError

av: Any = pytest.importorskip("av")

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"
MANIFEST = {
    entry["name"]: entry
    for entry in json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))["fixtures"]
}


def encode(name: str, container: str, codec: str, rate: int = 48_000) -> bytes:
    """A fixture re-encoded as Telegram (OGG/Opus) or a browser (WebM/Opus) sends it."""
    source = av.open(str(FIXTURES / str(MANIFEST[name]["file"])))
    out_buffer = io.BytesIO()
    with av.open(out_buffer, mode="w", format=container) as out:
        stream = out.add_stream(codec, rate=rate)
        stream.layout = "mono"
        resampler = av.AudioResampler(format=stream.format.name, layout="mono", rate=rate)
        for frame in source.decode(audio=0):
            frame.pts = None
            for converted in resampler.resample(frame):
                for packet in stream.encode(converted):
                    out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)
    source.close()
    return out_buffer.getvalue()


@pytest.mark.parametrize(
    ("container", "codec", "mime"),
    [
        ("ogg", "libopus", "audio/ogg"),
        ("webm", "libopus", "audio/webm;codecs=opus"),
        ("mp3", "mp3", "audio/mpeg"),
    ],
)
def test_compressed_formats_decode_to_16khz_mono(container: str, codec: str, mime: str) -> None:
    data = encode("zh_ask", container, codec)
    pcm = audio.decode(data, mime, VoiceConfig())
    assert pcm.duration_seconds == pytest.approx(
        float(MANIFEST["zh_ask"]["duration_seconds"]), abs=0.15
    )


def test_compressed_audio_over_the_limit_is_refused() -> None:
    data = encode("silence_2s", "ogg", "libopus")
    with pytest.raises(SttError) as raised:
        audio.decode(data, "audio/ogg", VoiceConfig(max_seconds=1))
    assert raised.value.code == "audio_too_long"


def test_text_that_is_not_audio_fails_to_decode() -> None:
    with pytest.raises(SttError) as raised:
        audio.decode((FIXTURES / "not_audio.ogg").read_bytes(), "audio/ogg", VoiceConfig())
    assert raised.value.code == "audio_decode_failed"


def test_opencc_converts_to_taiwan_traditional() -> None:
    pytest.importorskip("opencc")
    convert = _opencc()
    assert convert is not None
    assert convert("帮我查软件选项") == "幫我查軟體選項"
