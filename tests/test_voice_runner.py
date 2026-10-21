import hashlib
import json
import sys
import wave
from pathlib import Path
from typing import Any

import pytest

from benchmarks.voice_to_knowledge.runner import load_corpus, run_process


def manifest(tmp_path: Path) -> Path:
    audio = tmp_path / "silence.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 16000)
    row = dict(
        id="silence",
        path="silence.wav",
        sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),
        reference="",
        reference_sha256=hashlib.sha256(b"").hexdigest(),
        source_url="https://example.org/synthetic",
        license="CC0-1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        source_revision="fixture-v1",
        reference_version="v1",
        human_reviewed=False,
        speaker_id=None,
        split="plumbing",
        language="en",
        kind="synthetic",
        duration=1,
    )
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps({"schema_version": "voice.corpus.v0", "samples": [row]}))
    return path


def test_valid_plumbing_corpus_and_hash_refusal(tmp_path: Path) -> None:
    path = manifest(tmp_path)
    assert load_corpus(path)[0]["kind"] == "synthetic"
    (tmp_path / "silence.wav").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="audio_hash"):
        load_corpus(path)


@pytest.mark.parametrize(
    "field,value",
    [("license", ""), ("reference_sha256", "bad"), ("path", "../outside.wav"), ("split", "test")],
)
def test_corpus_fail_closed(tmp_path: Path, field: str, value: str) -> None:
    path = manifest(tmp_path)
    data = json.loads(path.read_text())
    data["samples"][0][field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_corpus(path)


def test_timeout_terminates_worker_and_preserves_partial_output() -> None:
    result = run_process(
        [sys.executable, "-u", "-c", 'import time; print("started"); time.sleep(20)'],
        "",
        timeout=0.1,
    )
    assert result["status"] == "timeout"
    assert "started" in result["stdout"]


def test_process_failure_is_not_success() -> None:
    result = run_process([sys.executable, "-c", 'raise RuntimeError("fixture")'], "", timeout=2)
    assert result["status"] == "failed"
    assert result["returncode"] != 0


def test_speaker_disjointness(tmp_path: Path) -> None:
    path = manifest(tmp_path)
    data = json.loads(path.read_text())
    first = data["samples"][0]
    first.update(kind="human", speaker_id="speaker-1", human_reviewed=True, split="dev")
    data["samples"].append({**first, "id": "second", "split": "test"})
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="speaker_split_leakage"):
        load_corpus(path)


def test_runner_artifacts_fake_process_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from benchmarks.voice_to_knowledge import runner

    path = manifest(tmp_path)
    model = tmp_path / "model"
    model.mkdir()
    (model / "model.bin").write_bytes(b"fake: not a model")
    output = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--corpus",
            str(path),
            "--model",
            str(model),
            "--model-id",
            "small",
            "--model-revision",
            "a" * 40,
            "--out",
            str(output),
        ],
    )
    calls = []

    def fake(command: list[str], payload: str, *, timeout: float) -> dict[str, Any]:
        calls.append(json.loads(payload))
        return dict(status="timeout", stdout="", stderr="", returncode=None)

    monkeypatch.setattr(runner, "run_process", fake)
    assert runner.main() == 1
    result = json.loads((output / "manifest.json").read_text())
    assert len(calls) == 3 and result["status"] == "failed"
    assert result["acceptance"] == "pending_thresholds_and_corpus_coverage"
    assert (output / "samples.csv").is_file() and (output / "summary.json").is_file()
