import time
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from benchmarks.voice_to_knowledge.provider import (
    AudioError,
    FasterWhisperProvider,
    consume,
    validate_audio,
)


def test_generator_is_exhausted_and_late_errors_propagate() -> None:
    seen = []

    def segments():
        for index in range(3):
            seen.append(index)
            yield SimpleNamespace(start=index, end=index + 1, text=str(index))

    assert len(consume(segments())) == 3 and seen == [0, 1, 2]

    def broken():
        yield SimpleNamespace(start=0, end=1, text="partial")
        raise RuntimeError("late failure")

    with pytest.raises(RuntimeError, match="late failure"):
        consume(broken())


def test_provider_times_lazy_inference() -> None:
    class Model:
        def transcribe(self, path, **kwargs):
            def segments():
                time.sleep(0.02)
                yield SimpleNamespace(start=0, end=1, text="synthetic")

            return segments(), SimpleNamespace(language="en")

    result = FasterWhisperProvider(Model()).transcribe(Path("unused"), "en")
    assert result.elapsed_seconds >= 0.02
    assert result.text == "synthetic"


def test_bad_and_oversize_audio(tmp_path: Path) -> None:
    path = tmp_path / "bad.wav"
    path.write_bytes(b"not audio")
    with pytest.raises(AudioError, match="invalid_audio"):
        validate_audio(path)
    with pytest.raises(AudioError, match="audio_too_large"):
        validate_audio(path, max_bytes=2)


def test_duration_and_pcm_validation(tmp_path: Path) -> None:
    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\0\0" * 16000)
    assert validate_audio(path) == 1
    with pytest.raises(AudioError, match="duration_limit"):
        validate_audio(path, max_seconds=0.5)
