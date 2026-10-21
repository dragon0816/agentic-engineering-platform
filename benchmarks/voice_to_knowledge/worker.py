"""One bounded inference process. Its parent enforces the wall clock timeout."""

from __future__ import annotations

import importlib
import json
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .metrics import score
from .provider import FasterWhisperProvider


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def main() -> None:
    request = json.load(sys.stdin)
    psutil = importlib.import_module("psutil")
    process = psutil.Process()
    peak = [process.memory_info().rss]
    stop = threading.Event()

    def sample_memory() -> None:
        while not stop.wait(0.01):
            peak[0] = max(peak[0], process.memory_info().rss)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        start = time.perf_counter()
        library = importlib.import_module("faster_whisper")
        model = library.WhisperModel(
            request["model"],
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            num_workers=1,
            local_files_only=True,
        )
        load_seconds = time.perf_counter() - start
        provider = FasterWhisperProvider(model)
        for pass_number in range(2):
            for index, sample in enumerate(request["samples"]):
                cold = pass_number == 0 and index == 0
                row: dict[str, Any] = {
                    "type": "sample",
                    "id": sample["id"],
                    "repetition": request["repetition"],
                    "thermal": "process_cold" if cold else "warm",
                    "pass": pass_number,
                    "language": sample["language"],
                    "kind": sample["kind"],
                    "split": sample["split"],
                    "reference": sample["reference"],
                    "duration": sample["duration"],
                    "load_seconds": load_seconds if cold else 0,
                    "vram_bytes": None,
                    "vram_reason": "CPU inference",
                    "rss_method": "process lifetime peak sampled every 10ms; may miss brief peaks",
                }
                start = time.perf_counter()
                try:
                    result = provider.transcribe(
                        Path(sample["absolute_path"]),
                        sample["language"] if sample["language"] in {"en", "zh"} else None,
                    )
                    elapsed = time.perf_counter() - start
                    row.update(
                        status="ok",
                        text=result.text,
                        segments=[asdict(s) for s in result.segments],
                        detected_language=result.language,
                        latency_seconds=elapsed,
                        rtf=elapsed / sample["duration"],
                        cold_total_seconds=load_seconds + elapsed if cold else None,
                        metrics=score(sample["reference"], result.text),
                    )
                except Exception as exc:
                    row.update(
                        status="failed",
                        error=type(exc).__name__,
                        latency_seconds=time.perf_counter() - start,
                    )
                peak[0] = max(peak[0], process.memory_info().rss)
                row["peak_rss_bytes"] = peak[0]
                emit(row)
    finally:
        stop.set()
        sampler.join()


if __name__ == "__main__":
    main()
