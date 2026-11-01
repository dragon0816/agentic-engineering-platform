"""The speech-to-text provider interface (docs/phases/VOICE_INPUT.md §3.5).

Ported from the voice-to-knowledge prototype's `provider.py` (draft PR #240)
and extended: providers take decoded 16 kHz mono PCM instead of WAV files, and
a result names its engine, model and model revision for the transcript record.
Only local engines are implemented (owner, 2026-11-01); `FakeSttProvider`
stands in for them in tests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from voice.contracts import ERROR_CODES, ErrorCode


class SttError(Exception):
    """A transcription failure with one of the codes of §3.6."""

    def __init__(self, code: ErrorCode) -> None:
        if code not in ERROR_CODES:
            raise ValueError("unknown voice error code")
        self.code: ErrorCode = code
        super().__init__(code)


@dataclass(frozen=True)
class Pcm16k:
    """Mono, 16 kHz, signed 16-bit little-endian samples."""

    samples: bytes

    RATE = 16_000

    def __post_init__(self) -> None:
        if len(self.samples) % 2:
            raise ValueError("16-bit PCM has an even number of bytes")

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / 2 / self.RATE

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.samples).hexdigest()


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class SttResult:
    segments: tuple[Segment, ...]
    # Detected language, when the engine reports one.
    language: str | None
    duration_seconds: float
    elapsed_seconds: float
    engine: str
    model: str
    model_revision: str

    @property
    def text(self) -> str:
        return "".join(segment.text for segment in self.segments).strip()


class SttProvider(Protocol):
    def transcribe(
        self, pcm: Pcm16k, *, language: str | None, hints: tuple[str, ...]
    ) -> SttResult: ...


@dataclass(frozen=True)
class FakeCall:
    sha256: str
    language: str | None
    hints: tuple[str, ...]


@dataclass
class FakeSttProvider:
    """Answers by the audio's PCM hash; `default` answers anything else.
    An `SttError` as an answer is raised."""

    answers: Mapping[str, SttResult | SttError] = field(default_factory=dict)
    default: SttResult | SttError | None = None
    calls: list[FakeCall] = field(default_factory=list)

    def transcribe(self, pcm: Pcm16k, *, language: str | None, hints: tuple[str, ...]) -> SttResult:
        self.calls.append(FakeCall(pcm.sha256, language, hints))
        answer = self.answers.get(pcm.sha256, self.default)
        if answer is None:
            raise SttError("stt_failed")
        if isinstance(answer, SttError):
            raise answer
        return answer
