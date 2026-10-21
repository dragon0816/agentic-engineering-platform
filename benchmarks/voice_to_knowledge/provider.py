"""Local provider seam; decoding accepts bounded mono PCM WAV only."""

from __future__ import annotations

import math
import time
import wave
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

PARAMETERS = {
    "beam_size": 5,
    "temperature": 0.0,
    "vad_filter": False,
    "condition_on_previous_text": False,
    "initial_prompt": None,
}


class AudioError(ValueError):
    pass


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Transcript:
    segments: tuple[Segment, ...]
    language: str
    elapsed_seconds: float

    @property
    def text(self) -> str:
        return "".join(segment.text for segment in self.segments)


class Provider(Protocol):
    def transcribe(self, audio: Path, language: str | None) -> Transcript: ...


def consume(segments: Iterable[Any]) -> tuple[Segment, ...]:
    output = []
    for item in segments:
        start, end = float(item.start), float(item.end)
        if not math.isfinite(start + end) or not 0 <= start <= end:
            raise AudioError("invalid_segments")
        output.append(Segment(start, end, str(item.text)))
    return tuple(output)


class FasterWhisperProvider:
    def __init__(self, model: Any) -> None:
        self.model = model

    def transcribe(self, audio: Path, language: str | None) -> Transcript:
        start = time.perf_counter()
        segments, info = self.model.transcribe(str(audio), language=language, **PARAMETERS)
        complete = consume(segments)  # Actual inference is lazy, including failures.
        return Transcript(complete, str(info.language), time.perf_counter() - start)


def validate_audio(path: Path, *, max_bytes: int = 32_000_000, max_seconds: float = 300) -> float:
    if not path.is_file():
        raise AudioError("invalid_audio")
    if path.stat().st_size > max_bytes:
        raise AudioError("audio_too_large")
    try:
        with wave.open(str(path), "rb") as audio:
            if (
                audio.getnchannels(),
                audio.getsampwidth(),
                audio.getframerate(),
                audio.getcomptype(),
            ) != (1, 2, 16000, "NONE"):
                raise AudioError("expected_mono_pcm16_16khz")
            duration = audio.getnframes() / 16000
            if not 0 < duration <= max_seconds:
                raise AudioError("duration_limit")
            if len(audio.readframes(audio.getnframes())) != audio.getnframes() * 2:
                raise AudioError("truncated_audio")
    except (wave.Error, EOFError) as exc:
        raise AudioError("invalid_audio") from exc
    return duration
