"""The local faster-whisper provider (docs/phases/VOICE_INPUT.md §7.1 a2, d3,
d7; slice V3). Runs without faster-whisper: a fake `WhisperModel` stands in.
The real-engine test at the end runs only when `AEP_VOICE_MODEL_DIR` names an
installed, owner-approved model package and faster-whisper is installed."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from voice import whisper
from voice.contracts import VoiceConfig, bare_word
from voice.metrics import cer
from voice.service import _opencc
from voice.stt import Pcm16k, SttError
from voice.whisper import FasterWhisperProvider, build_voice, model_package_sha256

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "voice"


def package(root: Path) -> Path:
    model = root / "whisper-small"
    model.mkdir()
    (model / "model.bin").write_bytes(b"weights")
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "tokenizer.json").write_text("{}", encoding="utf-8")
    return model


def config(model: Path, **changes: Any) -> VoiceConfig:
    values: dict[str, Any] = {
        "enabled": True,
        "model_path": str(model),
        "model_sha256": model_package_sha256(model),
        "hints": ("CMX500", "Wi-Fi 8"),
        **changes,
    }
    return VoiceConfig(**values)


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str


@dataclass
class FakeInfo:
    language: str
    duration: float


class FakeWhisperModel:
    instances: list[FakeWhisperModel] = []

    def __init__(self, path: str, **options: Any) -> None:
        self.path, self.options = path, options
        self.calls: list[dict[str, Any]] = []
        FakeWhisperModel.instances.append(self)

    def transcribe(self, audio: Any, **options: Any) -> tuple[Iterator[FakeSegment], FakeInfo]:
        self.calls.append({"audio": audio, **options})
        segments = iter([FakeSegment(0.0, 1.2, " 幫我查"), FakeSegment(1.2, 2.5, " CMX500")])
        return segments, FakeInfo(language="zh", duration=2.5)


@pytest.fixture(autouse=True)
def fake_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeWhisperModel.instances = []
    monkeypatch.setattr(whisper, "_whisper_model_class", lambda: FakeWhisperModel)
    monkeypatch.setattr(whisper, "_audio_array", lambda pcm: ("float32", len(pcm.samples) // 2))


def pcm(seconds: float = 2.5) -> Pcm16k:
    return Pcm16k(b"\x00\x00" * int(seconds * Pcm16k.RATE))


# -- the model package --------------------------------------------------------


def test_package_hash_covers_names_and_contents(tmp_path: Path) -> None:
    model = package(tmp_path)
    first = model_package_sha256(model)
    assert len(first) == 64 and first == model_package_sha256(model)
    (model / "model.bin").write_bytes(b"other weights")
    assert model_package_sha256(model) != first
    (model / "model.bin").write_bytes(b"weights")
    (model / "model.bin").rename(model / "renamed.bin")
    assert model_package_sha256(model) != first


def test_the_model_loads_on_first_use_from_the_pinned_package(tmp_path: Path) -> None:
    model = package(tmp_path)
    provider = FasterWhisperProvider(config(model))
    assert FakeWhisperModel.instances == []
    result = provider.transcribe(pcm(), language="zh", hints=("CMX500", "Wi-Fi 8"))
    [engine] = FakeWhisperModel.instances
    assert engine.path == str(model)
    assert engine.options["device"] == "cpu"
    assert engine.options["compute_type"] == "int8"
    assert engine.options["local_files_only"] is True
    assert result.text == "幫我查 CMX500"
    assert (result.language, result.duration_seconds) == ("zh", 2.5)
    assert (result.engine, result.model) == ("faster-whisper", "whisper-small")
    assert result.model_revision == model_package_sha256(model)
    provider.transcribe(pcm(), language="zh", hints=())
    assert len(FakeWhisperModel.instances) == 1


def test_decoding_settings_and_the_traditional_prompt(tmp_path: Path) -> None:
    provider = FasterWhisperProvider(config(package(tmp_path)))
    provider.transcribe(pcm(), language="zh", hints=("CMX500", "Wi-Fi 8"))
    [call] = FakeWhisperModel.instances[0].calls
    assert call["language"] == "zh"
    assert call["beam_size"] == 5 and call["temperature"] == 0.0
    assert call["vad_filter"] is True and call["condition_on_previous_text"] is False
    assert "繁體中文" in call["initial_prompt"]
    assert "CMX500" in call["initial_prompt"] and "Wi-Fi 8" in call["initial_prompt"]


def test_unload_drops_the_model(tmp_path: Path) -> None:
    provider = FasterWhisperProvider(config(package(tmp_path)))
    provider.transcribe(pcm(), language="zh", hints=())
    provider.unload()
    provider.transcribe(pcm(), language="zh", hints=())
    assert len(FakeWhisperModel.instances) == 2


@pytest.mark.parametrize("problem", ["missing", "changed", "no_engine"])
def test_an_unusable_model_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    model = package(tmp_path)
    chosen = config(model)
    if problem == "missing":
        chosen = config(model, model_path=str(tmp_path / "nowhere"))
    elif problem == "changed":
        (model / "model.bin").write_bytes(b"tampered")
    else:
        monkeypatch.setattr(whisper, "_whisper_model_class", lambda: None)
    with pytest.raises(SttError) as raised:
        FasterWhisperProvider(chosen).transcribe(pcm(), language="zh", hints=())
    assert raised.value.code == "stt_unavailable"
    assert FakeWhisperModel.instances == []


def test_a_disabled_config_has_no_model(tmp_path: Path) -> None:
    with pytest.raises(SttError) as raised:
        FasterWhisperProvider(VoiceConfig()).transcribe(pcm(), language="zh", hints=())
    assert raised.value.code == "stt_unavailable"


def test_build_voice_only_when_enabled(tmp_path: Path) -> None:
    assert build_voice(None, tmp_path) is None
    assert build_voice(VoiceConfig(), tmp_path) is None
    voice = build_voice(config(package(tmp_path)), tmp_path)
    assert voice is not None and isinstance(voice.provider, FasterWhisperProvider)
    assert voice.store.workspace_root == tmp_path
    voice.close()
    assert FakeWhisperModel.instances == []  # nothing loads before the first message


def test_hash_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    model = package(tmp_path)
    assert whisper.main([str(model)]) == 0
    assert capsys.readouterr().out.strip() == model_package_sha256(model)
    assert whisper.main([str(tmp_path / "nowhere")]) == 2


# -- character error rate ---------------------------------------------------------


def test_cer_normalises_case_width_and_punctuation() -> None:
    assert cer("幫我查 CMX500 的 Wi-Fi 8 選項", "幫我查ＣＭＸ５００的wifi 8選項。") == 0.0
    assert cer("幫我查", "幫你查") == pytest.approx(1 / 3)
    assert cer("", "") == 0.0


# -- the real engine (opt-in) -------------------------------------------------------


MODEL_DIR = os.environ.get("AEP_VOICE_MODEL_DIR", "")
#: V0 (docs/phases/VOICE_INPUT.md §6.2): Whisper small int8 with these hints scored at most 0.105
#: on these fixtures (zh_coding: the synthetic voice reads "UTF-8" as 「UTF 橫線 8」); about twice
#: that leaves room for CPU and library differences. Without hints it was 0.368.
CER_LIMIT = 0.20


@pytest.mark.skipif(not MODEL_DIR, reason="AEP_VOICE_MODEL_DIR names no installed model")
def test_real_engine_on_the_synthetic_speech(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("faster_whisper")
    monkeypatch.undo()  # the real engine, not the fake
    from voice import audio

    model = Path(MODEL_DIR)
    provider = FasterWhisperProvider(
        VoiceConfig(
            enabled=True,
            model_path=str(model),
            model_sha256=model_package_sha256(model),
            hints=("CMX500", "Wi-Fi 8", "Workflow", "parser", "CSV", "UTF-8"),
        )
    )
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    convert = _opencc()
    for entry in manifest["fixtures"]:
        if entry["kind"] != "speech":
            continue
        decoded = audio.decode((FIXTURES / entry["file"]).read_bytes(), "audio/wav", VoiceConfig())
        # The hints reach the engine as they do through VoiceService.
        heard = provider.transcribe(
            decoded, language=entry["language"], hints=provider.config.hints
        ).text
        heard = convert(heard) if convert is not None else heard
        if len(entry["text"]) < 6:
            # A card word must come out as the word itself (「好」, 「取消」).
            assert bare_word(heard) == entry["text"], (entry["name"], heard)
        else:
            assert cer(entry["text"], heard) <= CER_LIMIT, (entry["name"], heard)
