"""The committed voice test audio (docs/phases/VOICE_INPUT.md §4.1) is what
`scripts/voice_fixtures.py` wrote: synthetic speech and generated sounds only,
16 kHz mono 16-bit, each listed in the manifest with its hash."""

from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "voice"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "voice_fixtures", ROOT / "scripts" / "voice_fixtures.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> list[dict[str, object]]:
    data = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    assert data["schema"] == "aep.voice.fixtures/v1"
    fixtures: list[dict[str, object]] = data["fixtures"]
    return fixtures


def test_fixtures_match_the_manifest() -> None:
    assert _script().check() == []


def test_every_file_is_listed_once() -> None:
    names = [str(entry["file"]) for entry in _manifest()]
    assert len(names) == len(set(names))
    on_disk = {path.name for path in FIXTURES.iterdir() if path.name != "manifest.json"}
    assert on_disk == set(names)


def test_audio_fixtures_are_16khz_mono_pcm() -> None:
    for entry in _manifest():
        if entry["kind"] == "invalid":
            continue
        with wave.open(str(FIXTURES / str(entry["file"])), "rb") as audio:
            assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (
                1,
                2,
                16_000,
            )
            assert audio.getnframes() > 0


def test_speech_comes_from_synthetic_voices_with_reference_text() -> None:
    speech = [entry for entry in _manifest() if entry["kind"] == "speech"]
    assert {entry["name"] for entry in speech} >= {
        "zh_ask",
        "zh_workflow",
        "zh_coding",
        "zh_confirm",
    }
    for entry in speech:
        assert entry["text"] and entry["language"] in {"zh", "en"}
        assert str(entry["generator"]).startswith("System.Speech")
