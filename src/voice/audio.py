"""Audio bytes to 16 kHz mono PCM, in memory (docs/phases/VOICE_INPUT.md §2.2).

Nothing is written to disk: the owner keeps the transcript only (2026-11-01).
16-bit PCM WAV is read, down-mixed and resampled with the standard library, so
tests and a host without the optional `voice` extra can use it; everything
else (Telegram's OGG/Opus, the browser's WebM/Opus, MP3, M4A) goes through
PyAV, whose wheels bundle the FFmpeg decoders. The declared type is checked
against the accepted list; the content decides how it is decoded.
"""

from __future__ import annotations

import array
import importlib
import io
import sys
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
    # Precedence (§3.6): bytes that are not audio are `audio_decode_failed`;
    # 16-bit PCM WAV never needs PyAV; only a real compressed container (or an
    # unusual WAV) on a host without PyAV is `audio_unsupported_format` /
    # `stt_unavailable`.
    if _is_wav(data):
        pcm = _plain_wav(data, config.max_seconds)
        if pcm is None:
            av = _import_av()
            if av is None:
                raise SttError("audio_unsupported_format")
            pcm = _with_av(av, data, config.max_seconds)
    elif not _looks_like_audio(data):
        raise SttError("audio_decode_failed")
    else:
        av = _import_av()
        if av is None:
            raise SttError("stt_unavailable")
        pcm = _with_av(av, data, config.max_seconds)
    if pcm.duration_seconds > config.max_seconds:
        raise SttError("audio_too_long")
    if not pcm.samples:
        raise SttError("audio_decode_failed")
    return pcm


def _is_wav(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def _looks_like_audio(data: bytes) -> bool:
    """Whether the bytes start like an accepted compressed container (OGG,
    WebM, MP3, MP4/M4A), so content that is not audio fails to decode even on
    a host without PyAV, and only real audio needs the `voice` extra."""
    return (
        data[:4] in (b"OggS", b"\x1aE\xdf\xa3")
        or data[:3] == b"ID3"
        or data[4:8] == b"ftyp"
        or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    )


def _plain_wav(data: bytes, max_seconds: int) -> Pcm16k | None:
    """16-bit PCM WAV of any rate and channel count, down-mixed and resampled
    with the standard library; None for another sample format (8/24/32-bit,
    float), which needs PyAV."""
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            channels, width, rate = (
                audio.getnchannels(),
                audio.getsampwidth(),
                audio.getframerate(),
            )
            if width != 2:
                return None
            count = audio.getnframes()
            if count > (max_seconds + 1) * rate:
                raise SttError("audio_too_long")
            frames = audio.readframes(count)
    except wave.Error as error:
        if "unknown format" in str(error):
            return None  # not integer PCM, e.g. float samples
        raise SttError("audio_decode_failed") from error
    except (EOFError, ValueError) as error:
        raise SttError("audio_decode_failed") from error
    if not frames or len(frames) != count * 2 * channels or rate <= 0:
        raise SttError("audio_decode_failed")
    if (channels, rate) == (1, _RATE):
        return Pcm16k(frames)
    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
        samples.byteswap()
    mono = (
        samples
        if channels == 1
        else array.array(
            "h",
            (sum(samples[i : i + channels]) // channels for i in range(0, len(samples), channels)),
        )
    )
    out = _resample(mono, rate)
    if sys.byteorder == "big":
        out.byteswap()  # PCM is little-endian
    return Pcm16k(out.tobytes())


def _resample(samples: array.array[int], rate: int) -> array.array[int]:
    """Linear interpolation to 16 kHz; enough for speech recognition."""
    if rate == _RATE or len(samples) < 2:
        return samples
    step = rate / _RATE
    count = int(len(samples) / step)
    last = len(samples) - 1
    out = array.array("h", bytes(2 * count))
    for i in range(count):
        position = i * step
        j = int(position)
        if j >= last:
            out[i] = samples[last]
            continue
        fraction = position - j
        out[i] = int(samples[j] + (samples[j + 1] - samples[j]) * fraction)
    return out


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
