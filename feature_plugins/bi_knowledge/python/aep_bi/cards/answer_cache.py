"""A model's answer, kept per PC, for an identical request.

The same bytes give a different answer each time on gpt-5.5, with no way to fix it
(`docs/phases/BI_EXTRACTION_VARIANCE.md`), so an unchanged chunk reuses the first usable
answer and a re-run repeats. Any change to the prompt, such as a new skill revision or a
card added to the known list, is a different request and asks the model again. A failure
or an answer of the wrong shape is never kept. Answers hold quotes from the sources, so a
withdrawn source clears them (`clear`). Local only, never in the shared folder.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from models.contracts import ModelClient, ModelRequest, ModelResponse

FOLDER = "answer_cache"


def request_key(request: ModelRequest) -> str:
    """What makes two requests the same: everything sent, but not the trace."""
    sent = {
        "alias": request.model_alias,
        "messages": [m.model_dump(mode="json") for m in request.messages],
        "max_output_tokens": request.max_output_tokens,
        "output_contract": request.output_contract,
    }
    text = json.dumps(sent, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clear(dataset_dir: Path) -> None:
    shutil.rmtree(dataset_dir / FOLDER, ignore_errors=True)


class CachingModel:
    """A model that answers an identical request from `dataset_dir`, unless `fresh`.
    `usable` says whether an answer may be kept; it counts hits and tokens for the run."""

    def __init__(
        self, model: ModelClient, dataset_dir: Path, *, fresh: bool = False, usable: Any = None
    ) -> None:
        self.model = model
        self.folder = dataset_dir / FOLDER
        self.fresh = fresh
        self.usable = usable
        self.hits = 0
        self.misses = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        path = self.folder / f"{request_key(request)}.json"
        if not self.fresh:
            try:
                held = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                held = None
            if isinstance(held, dict):
                self.hits += 1
                return ModelResponse(
                    trace=request.trace,
                    model_alias=request.model_alias,
                    text=str(held.get("text") or ""),
                    structured_output=held.get("structured_output"),
                )
        response = self.model.generate(request)
        self.misses += 1
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        if response.failure is None and (self.usable is None or self.usable(response)):
            self._keep(path, response)
        return response

    def _keep(self, path: Path, response: ModelResponse) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        scratch = path.with_name(f".{uuid.uuid4().hex[:8]}.tmp")
        try:
            scratch.write_text(
                json.dumps(
                    {"text": response.text, "structured_output": response.structured_output},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            os.replace(scratch, path)
        except OSError:
            scratch.unlink(missing_ok=True)  # a lost cache entry only costs a call next time

    def __getattr__(self, name: str) -> Any:
        return getattr(self.model, name)
