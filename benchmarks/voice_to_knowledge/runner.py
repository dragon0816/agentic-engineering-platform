"""Offline CPU runner: python -m benchmarks.voice_to_knowledge.runner --help."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .metrics import POLICY, summarize
from .provider import PARAMETERS, validate_audio


def sha256(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def load_corpus(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "voice.corpus.v0":
        raise ValueError("corpus_version")
    samples = document.get("samples")
    if not isinstance(samples, list) or not 0 < len(samples) <= 1000:
        raise ValueError("corpus_size")
    ids: set[str] = set()
    speakers: dict[str, str] = {}
    for sample in samples:
        for field in (
            "id",
            "path",
            "sha256",
            "reference_sha256",
            "source_url",
            "license",
            "license_url",
            "source_revision",
            "reference_version",
            "split",
            "language",
            "kind",
        ):
            if not isinstance(sample.get(field), str) or not sample[field].strip():
                raise ValueError(f"missing_{field}")
        if sample["id"] in ids:
            raise ValueError("duplicate_id")
        ids.add(sample["id"])
        if sample["language"] not in {"zh", "en", "mixed", "none"}:
            raise ValueError("language")
        if sample["kind"] not in {"human", "non_speech", "synthetic"}:
            raise ValueError("kind")
        if sample["split"] not in {"pilot", "dev", "test", "plumbing"}:
            raise ValueError("split")
        if sample["kind"] == "synthetic" and sample["split"] != "plumbing":
            raise ValueError("synthetic_accuracy_forbidden")
        if not isinstance(sample.get("human_reviewed"), bool):
            raise ValueError("review_state_missing")
        if sample["split"] in {"dev", "test"} and sample["kind"] == "human":
            speaker = sample.get("speaker_id")
            if not isinstance(speaker, str) or not speaker.strip() or not sample["human_reviewed"]:
                raise ValueError("holdout_requires_review_and_speaker")
            if speaker in speakers and speakers[speaker] != sample["split"]:
                raise ValueError("speaker_split_leakage")
            speakers[speaker] = sample["split"]
        reference = sample.get("reference")
        if not isinstance(reference, str) or len(reference) > 100_000:
            raise ValueError("invalid_reference")
        if hashlib.sha256(reference.encode()).hexdigest() != sample["reference_sha256"]:
            raise ValueError("reference_hash")
        if sample["kind"] == "non_speech" and reference:
            raise ValueError("non_speech_reference")
        audio = (path.parent / sample["path"]).resolve()
        if path.parent.resolve() not in audio.parents:
            raise ValueError("audio_outside_corpus")
        if audio.stat().st_size > 32_000_000:
            raise ValueError("audio_too_large")
        if sha256(audio) != sample["sha256"]:
            raise ValueError("audio_hash")
        duration = validate_audio(audio)
        declared = sample.get("duration")
        if not isinstance(declared, (float, int)) or not math.isfinite(declared):
            raise ValueError("duration_missing")
        if abs(duration - declared) > 1 / 16000:
            raise ValueError("duration_mismatch")
        sample["absolute_path"] = str(audio)
    return samples


def run_process(command: list[str], payload: str, *, timeout: float) -> dict[str, Any]:
    env = {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }
    # subprocess.run kills and waits for this single worker on timeout.
    try:
        result = subprocess.run(
            command,
            input=payload,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
            check=False,
        )
        return {
            "status": "ok" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired as exc:

        def decode(value: str | bytes | None) -> str:
            return (
                value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
            )

        return {
            "status": "timeout",
            "returncode": None,
            "stdout": decode(exc.stdout),
            "stderr": decode(exc.stderr),
        }


def hardware() -> dict[str, Any]:
    def read(path: str) -> str | None:
        file = Path(path)
        return file.read_text().strip() if file.is_file() else None

    def version(package: str) -> str | None:
        try:
            return importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            return None

    return {
        "platform": platform.platform(),
        "python": sys.version,
        "visible_cpus": os.cpu_count(),
        "cpuinfo": read("/proc/cpuinfo"),
        "memory_max": read("/sys/fs/cgroup/memory.max"),
        "cpu_max": read("/sys/fs/cgroup/cpu.max"),
        "load_average": list(os.getloadavg()) if hasattr(os, "getloadavg") else None,
        "gpu": None,
        "gpu_reason": "CPU-only runner; GPU measurement not implemented",
        "packages": {
            p: version(p) for p in ("faster-whisper", "ctranslate2", "av", "numpy", "psutil")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--model", type=Path, required=True, help="pre-downloaded local CT2 directory"
    )
    parser.add_argument("--model-id", choices=["small", "medium"], required=True)
    parser.add_argument("--model-revision", required=True, help="immutable upstream commit SHA")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    parser.add_argument("--timeout", type=float, default=1800, help="seconds per repetition")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be positive and finite")
    if len(args.model_revision) != 40 or any(
        c not in "0123456789abcdef" for c in args.model_revision
    ):
        parser.error("model revision must be a 40-character commit hash")
    samples = load_corpus(args.corpus)
    model = args.model.resolve()
    if not model.is_dir() or not (model / "model.bin").is_file():
        parser.error("local model.bin required; no model download is attempted")
    args.out.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "schema_version": "voice.run.v0",
        "started_at": datetime.now(UTC).isoformat(),
        "evidence": "real_local_inference",
        "model_id": args.model_id,
        "model_revision": args.model_revision,
        "model_sha256": {
            str(p.relative_to(model)): sha256(p) for p in sorted(model.rglob("*")) if p.is_file()
        },
        "corpus_sha256": sha256(args.corpus),
        "corpus": json.loads(args.corpus.read_text()),
        "hardware": hardware(),
        "parameters": PARAMETERS,
        "compute_type": "int8",
        "device": "cpu",
        "threads": 4,
        "workers": 1,
        "concurrency": 1,
        "repetitions": 3,
        "score_policy": POLICY,
        "timeout_seconds_per_repetition": args.timeout,
        "counts": dict(Counter(f"{s['language']}/{s['kind']}/{s['split']}" for s in samples)),
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True)),
        "command": sys.argv,
        "status": "running",
    }
    manifest_path = args.out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    rows = []
    outcomes = []
    for repetition in range(1, 4):
        # Warm passes contain the same inputs and model; fresh process for each repetition.
        payload = json.dumps({"model": str(model), "samples": samples, "repetition": repetition})
        outcome = run_process(
            [sys.executable, "-m", "benchmarks.voice_to_knowledge.worker"],
            payload,
            timeout=args.timeout,
        )
        outcomes.append({k: v for k, v in outcome.items() if k != "stdout"})
        (args.out / f"worker-{repetition}.jsonl").write_text(outcome["stdout"])
        for line in outcome["stdout"].splitlines():
            try:
                row = json.loads(line)
                if isinstance(row, dict) and row.get("type") == "sample":
                    rows.append(row)
            except json.JSONDecodeError:
                continue
    (args.out / "samples.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    with (args.out / "samples.csv").open("w", newline="") as stream:
        columns = [
            "id",
            "repetition",
            "thermal",
            "status",
            "latency_seconds",
            "rtf",
            "load_seconds",
            "cold_total_seconds",
            "peak_rss_bytes",
            "vram_bytes",
            "text",
            "metrics",
            "error",
        ]
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "metrics": json.dumps(row.get("metrics"), ensure_ascii=False)})
    (args.out / "summary.json").write_text(
        json.dumps(summarize(rows), ensure_ascii=False, indent=2)
    )
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    manifest["process_outcomes"] = outcomes
    manifest["status"] = (
        "completed"
        if all(o["status"] == "ok" for o in outcomes)
        and len(rows) == len(samples) * 2 * 3
        and all(r["status"] == "ok" for r in rows)
        else "failed"
    )
    manifest["acceptance"] = "pending_thresholds_and_corpus_coverage"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
