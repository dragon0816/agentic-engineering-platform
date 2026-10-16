"""The runtime patch for chatrs streaming chunks with empty `choices`.

Ported from the owner's working gateway (`rs_llm_gateway/gateway.py`).

LiteLLM's Anthropic streaming adapter (POST /v1/messages, every Claude Code
request) indexes `chunk.choices[0]` unguarded in
`llms/anthropic/experimental_pass_through/adapters/streaming_iterator.py`.
chatrs (Open WebUI) emits at least one chunk with `choices: []` (a usage /
timing prelude with its non-standard `usage.latency_checkpoint`), so the
adapter raises IndexError mid-stream and the client gets a 500 and no text.
The patch drops those chunks at `_CombinedChunkSplitter`, the single point
both the sync and async iteration paths draw from. Known cost: token counts
LiteLLM reports for /v1/messages may under-report (no billing is attached).

It patches a private class, so it fails loudly when the internals moved
instead of silently doing nothing.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

STREAMING_MODULE = "litellm.llms.anthropic.experimental_pass_through.adapters.streaming_iterator"
SPLITTER = "_CombinedChunkSplitter"
_MARKER = "_aep_empty_choices_patch"


class GatewayPatchError(RuntimeError):
    """LiteLLM's internals no longer match what the patch was written for."""


def has_choices(chunk: object) -> bool:
    return bool(getattr(chunk, "choices", None))


def apply(module: ModuleType | None = None) -> type[Any]:
    """Patch the splitter in `module` (LiteLLM's by default); returns the class.

    Applying twice is a no-op, so a re-import cannot wrap the wrapper.
    """
    if module is None:
        try:
            module = importlib.import_module(STREAMING_MODULE)
        except ImportError as error:
            raise GatewayPatchError(
                f"LiteLLM's streaming adapter is gone ({STREAMING_MODULE}): the streaming "
                "patch no longer applies. Re-check whether the upstream IndexError is fixed "
                "before changing the pinned LiteLLM version."
            ) from error
    splitter = getattr(module, SPLITTER, None)
    if not isinstance(splitter, type):
        raise GatewayPatchError(
            f"LiteLLM's {SPLITTER} is gone: the streaming patch no longer applies. "
            "Re-check whether the upstream IndexError is fixed; if it is, drop the patch."
        )
    original_next = getattr(splitter, "__next__", None)
    original_anext = getattr(splitter, "__anext__", None)
    if not callable(original_next) or not callable(original_anext):
        raise GatewayPatchError(
            f"LiteLLM's {SPLITTER} no longer iterates with __next__/__anext__: "
            "the streaming patch no longer applies."
        )
    if getattr(splitter, _MARKER, False):
        return splitter

    def patched_next(self: object) -> object:
        while True:
            chunk = original_next(self)  # propagates StopIteration
            if has_choices(chunk):
                return chunk

    async def patched_anext(self: object) -> object:
        while True:
            chunk = await original_anext(self)  # propagates StopAsyncIteration
            if has_choices(chunk):
                return chunk

    splitter.__next__ = patched_next  # type: ignore[attr-defined]
    splitter.__anext__ = patched_anext  # type: ignore[attr-defined]
    setattr(splitter, _MARKER, True)
    return splitter
