import json
import wave
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from benchmarks.voice_to_knowledge.extraction import (
    ExtractionError,
    ExtractionSkill,
    FakeExtractor,
    FakeSTT,
    VisitSubmission,
    prepare,
)
from benchmarks.voice_to_knowledge.submission import Identity, MockSubmission, SubmissionError

FIXTURES = Path(__file__).parents[1] / "benchmarks/voice_to_knowledge/fixtures"


def fixture(name: str = "visit") -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture
def audio(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic-silence.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\0\0" * 16000)
    return path


def prepared(audio: Path, data: dict[str, Any]) -> VisitSubmission:
    return prepare(
        audio,
        data["source_id"],
        FakeSTT(data["transcript"]),
        FakeExtractor(json.dumps(data["extraction"], ensure_ascii=False)),
        ExtractionSkill(),
    )


def test_synthetic_flow_preserves_raw_and_submits_json_and_markdown(audio: Path) -> None:
    data = fixture()
    value = prepared(audio, data)
    assert value.transcript == data["transcript"]
    parsed = json.loads(value.extraction_json)
    assert {c["kind"] for c in parsed["claims"]} == {
        "fact",
        "observation",
        "inference",
        "uncertain",
    }
    assert parsed["synthetic"] is True
    mock = MockSubmission()
    identity = Identity("synthetic", "reviewer", frozenset({"draft.create", "draft.read.own"}))
    receipt = mock.create(identity, "visit-1", value, "r1")
    draft = mock.read(identity, receipt.draft_id)
    assert draft.status == "draft" and draft.mock
    assert isinstance(draft.submission, VisitSubmission)
    assert draft.submission.extraction_json == value.extraction_json
    assert all(f"[{value.source_id}:{c.start}:{c.end}]" in draft.markdown for c in value.claims)
    assert mock.create(identity, "visit-1", value, "r2").draft_id == receipt.draft_id
    with pytest.raises(SubmissionError, match="idempotency_conflict"):
        mock.create(identity, "visit-1", replace(value, audio_sha256="b" * 64), "r3")


def test_missing_customer_remains_null(audio: Path) -> None:
    value = prepared(audio, fixture("visit_missing_customer"))
    assert json.loads(value.extraction_json)["customer"] is None
    assert "unknown customer" not in value.transcript.lower()


@pytest.mark.parametrize("change", ["extra", "kind", "status", "customer", "version", "coercion"])
def test_schema_rejects_invalid_provider_json(audio: Path, change: str) -> None:
    data = fixture()
    output = data["extraction"]
    if change == "extra":
        output["publish"] = True
    elif change == "kind":
        output["claims"][0]["kind"] = "confirmed"
    elif change == "status":
        output["claims"][0]["verification_status"] = "verified"
    elif change == "customer":
        del output["customer"]
    elif change == "version":
        output["schema_version"] = "aep.production.v1"
    else:
        output["claims"][0]["source"]["start"] = "0"
    with pytest.raises(ExtractionError, match="schema_rejected"):
        prepared(audio, data)


@pytest.mark.parametrize("change", ["source_id", "hash", "offset", "quote", "text", "customer"])
def test_invented_or_unsupported_sources_refused(audio: Path, change: str) -> None:
    data = fixture()
    output = data["extraction"]
    if change == "source_id":
        output["source_id"] = "invented-recording"
    elif change == "hash":
        output["transcript_sha256"] = "f" * 64
    elif change == "customer":
        output["customer"]["value"] = "Invented customer"
    else:
        claim = output["claims"][0]
        if change == "offset":
            claim["source"]["end"] = 10000
        elif change == "quote":
            claim["source"]["quote"] = "invented quote"
        else:
            claim["text"] = "unsupported assertion"
    with pytest.raises(ExtractionError, match="source_rejected"):
        prepared(audio, data)


def test_provider_failure_then_explicit_retry(audio: Path) -> None:
    data = fixture()

    class Failing:
        def extract(self, transcript: str, source_id: str, skill: ExtractionSkill) -> str:
            raise RuntimeError("synthetic provider unavailable")

    with pytest.raises(ExtractionError, match="extraction_failed"):
        prepare(audio, data["source_id"], FakeSTT(data["transcript"]), Failing(), ExtractionSkill())
    # Caller retries preparation explicitly, then retains the payload for submission retry.
    assert prepared(audio, data).transcript == data["transcript"]


def test_stt_failure_and_permission_refusal(audio: Path) -> None:
    data = fixture()

    class FailingSTT:
        def transcribe(self, audio: Path, language: str | None) -> Any:
            raise RuntimeError("synthetic STT unavailable")

    with pytest.raises(ExtractionError, match="stt_failed"):
        prepare(audio, data["source_id"], FailingSTT(), FakeExtractor("{}"), ExtractionSkill())
    value = prepared(audio, data)
    with pytest.raises(SubmissionError, match="permission_denied"):
        MockSubmission().create(Identity("synthetic", "reviewer", frozenset()), "k", value, "r")


def test_direct_submission_cannot_bypass_schema_or_claim_mapping(audio: Path) -> None:
    value = prepared(audio, fixture())
    for bad in [replace(value, extraction_json="{}"), replace(value, claims=())]:
        with pytest.raises(SubmissionError, match="invalid_request"):
            bad.validate()


def test_schema_artifact_matches_runtime_contract() -> None:
    from benchmarks.voice_to_knowledge.extraction import Extraction

    path = FIXTURES.parent / "extraction.schema.json"
    assert json.loads(path.read_text(encoding="utf-8")) == Extraction.model_json_schema()


@pytest.mark.parametrize("default_encoding", ["utf-8", "cp1252"])
def test_demo_is_explicitly_synthetic_and_writes_separate_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, default_encoding: str
) -> None:
    import subprocess
    import sys

    original_read_text = Path.read_text

    def legacy_read_text(path: Path, encoding: str | None = None, errors: str | None = None) -> str:
        return original_read_text(path, encoding=encoding or default_encoding, errors=errors)

    # Reproduce the Windows default deterministically, even on UTF-8 Linux.
    monkeypatch.setattr(Path, "read_text", legacy_read_text)
    output = tmp_path / "demo"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "benchmarks.voice_to_knowledge.demo",
            "--out",
            str(output),
            "--fixture",
            "visit_missing_customer",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert json.loads(result.stdout)["actual_benchmark"] == "NOT_RUN"
    raw = json.loads((output / "raw.json").read_text(encoding="utf-8"))
    assert raw["synthetic"] is True
    assert raw["transcript"] == fixture("visit_missing_customer")["transcript"]
    assert json.loads((output / "extraction.json").read_text(encoding="utf-8"))["customer"] is None
    assert json.loads((output / "receipts.json").read_text(encoding="utf-8"))["same_draft"] is True
    assert "Mock draft" in (output / "draft.md").read_text(encoding="utf-8")


def test_audio_mutation_refused_before_extraction(audio: Path) -> None:
    from benchmarks.voice_to_knowledge.provider import Transcript

    class MutatingSTT:
        def transcribe(self, audio: Path, language: str | None) -> Transcript:
            result = FakeSTT("synthetic").transcribe(audio, language)
            audio.write_bytes(b"changed")
            return result

    with pytest.raises(ExtractionError, match="source_changed"):
        prepare(audio, "source", MutatingSTT(), FakeExtractor("{}"), ExtractionSkill())


def test_scripted_extractor_cannot_request_approval(audio: Path) -> None:
    data = fixture()
    data["extraction"]["approve"] = True
    with pytest.raises(ExtractionError, match="schema_rejected"):
        prepared(audio, data)
