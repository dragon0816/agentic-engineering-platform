"""Offline scripted demo, never STT/extraction accuracy: python -m ...demo --out NEW_DIR."""

from __future__ import annotations

import argparse
import json
import tempfile
import wave
from dataclasses import asdict
from pathlib import Path

from .extraction import ExtractionSkill, FakeExtractor, FakeSTT, prepare
from .submission import Identity, MockSubmission


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fixture", choices=["visit", "visit_missing_customer"], default="visit")
    args = parser.parse_args()
    data = json.loads(
        (Path(__file__).parent / "fixtures" / f"{args.fixture}.json").read_text(encoding="utf-8")
    )
    args.out.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="voice-synthetic-") as folder:
        audio = Path(folder) / "generated-silence.wav"
        with wave.open(str(audio), "wb") as stream:
            stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            stream.writeframes(b"\0\0" * 16000)
        payload = prepare(
            audio,
            data["source_id"],
            FakeSTT(data["transcript"]),
            FakeExtractor(json.dumps(data["extraction"], ensure_ascii=False)),
            ExtractionSkill(),
        )
    identity = Identity(
        "synthetic-lab", "synthetic-reviewer", frozenset({"draft.create", "draft.read.own"})
    )
    mock = MockSubmission()
    first = mock.create(identity, data["source_id"], payload, "synthetic-request-1")
    replay = mock.create(identity, data["source_id"], payload, "synthetic-request-2")
    draft = mock.read(identity, first.draft_id)
    raw = {
        "synthetic": True,
        "evidence": "scripted_fake_not_accuracy",
        "source_id": payload.source_id,
        "transcript": payload.transcript,
        "transcript_sha256": payload.transcript_sha256,
        "audio_sha256": payload.audio_sha256,
        "audio_kind": "generated one-second silence, unrelated to user recordings",
        "stt_provider": "FakeSTT",
        "extraction_provider": "FakeExtractor",
    }
    (args.out / "raw.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.out / "extraction.json").write_text(payload.extraction_json, encoding="utf-8")
    (args.out / "draft.md").write_text(draft.markdown, encoding="utf-8")
    result = {
        "synthetic": True,
        "first": asdict(first),
        "replay": asdict(replay),
        "same_draft": first.draft_id == replay.draft_id,
        "actual_benchmark": "NOT_RUN",
    }
    (args.out / "receipts.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "synthetic": True,
                "status": first.status,
                "same_draft": result["same_draft"],
                "actual_benchmark": "NOT_RUN",
            }
        )
    )


if __name__ == "__main__":
    main()
