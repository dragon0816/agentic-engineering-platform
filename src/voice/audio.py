"""Audio bytes to 16 kHz mono PCM, in memory (docs/phases/VOICE_INPUT.md §2.2).

Nothing is written to disk: the owner keeps the transcript only (2026-11-01).
WAV that is already 16 kHz mono 16-bit is read with the standard library, so
tests and a host without the optional `voice` extra can use it; everything
else (Telegram's OGG/Opus, the browser's WebM/Opus, MP3, M4A) goes through
PyAV, whose wheels bundle the FFmpeg decoders. The declared type is checked
against the accepted list; the content decides how it is decoded.
"""

from __future__ import annotations

import importlib
import io
import wave
from types import ModuleType
from typing import Any

from voice.contracts import VoiceConfig, accepted_mime
from voice.stt import Pcm16k, SttError

_RATE = Pcm16k.RATE


def _import_av() -> ModuleType | None:
    try:
        return importlib.import_module("av")
    except ImportError:
        return None


def decode(data: bytes, mime_type: str | None, config: VoiceConfig) -> Pcm16k:
    """The audio as PCM, or an `SttError` naming why not (§3.6)."""
    if len(data) > config.max_bytes:
        raise SttError("audio_too_large")
    if mime_type and not accepted_mime(mime_type):
        raise SttError("audio_unsupported_format")
    if not data:
        raise SttError("audio_decode_failed")
    pcm = _plain_wav(data)
    if pcm is None:
        av = _import_av()
        if av is None:
            raise SttError("stt_unavailable")
        pcm = _with_av(av, data, config.max_seconds)
    if pcm.duration_seconds > config.max_seconds:
        raise SttError("audio_too_long")
    if not pcm.samples:
        raise SttError("audio_decode_failed")
    return pcm


def _plain_wav(data: bytes) -> Pcm16k | None:
    """16 kHz mono 16-bit WAV as is; None for any other content."""
    if not (data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
        return None
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            shape = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
            if shape != (1, 2, _RATE):
                return None
            frames = audio.readframes(audio.getnframes())
            expected = audio.getnframes() * 2
    except (wave.Error, EOFError, ValueError) as error:
        raise SttError("audio_decode_failed") from error
    if len(frames) != expected or not frames:
        raise SttError("audio_decode_failed")
    return Pcm16k(frames)


def _with_av(av: Any, data: bytes, max_seconds: int) -> Pcm16k:
    limit = (max_seconds + 1) * _RATE * 2
    chunks: list[bytes] = []
    size = 0
    try:
        with av.open(io.BytesIO(data), mode="r") as container:
            if not container.streams.audio:
                raise SttError("audio_decode_failed")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=_RATE)
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    chunk = bytes(out.planes[0])[: out.samples * 2]
                    chunks.append(chunk)
                    size += len(chunk)
                if size > limit:
                    raise SttError("audio_too_long")
            for out in resampler.resample(None):
                chunks.append(bytes(out.planes[0])[: out.samples * 2])
    except SttError:
        raise
    except Exception as error:  # any FFmpeg or container error
        raise SttError("audio_decode_failed") from error
    return Pcm16k(b"".join(chunks))
