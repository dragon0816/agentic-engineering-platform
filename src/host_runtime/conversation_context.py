"""Host-local conversation history limits, separate from model capability metadata."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from common.assets import RegistryContract
from host_runtime.workspace import write_atomically
from models.contracts import ModelMessage

MAX_MESSAGE_CHARS = 4_000
MAX_RECENT_MESSAGES = 40
MAX_HISTORY_BYTES = 48_000


class ConversationContextSettings(RegistryContract):
    """Bound the transcript carried into ordinary chat, including the new question.

    UTF-8 bytes conservatively bound tokenizer input across configured providers.
    The budget excludes system guidance, tool schemas and tool results, which have
    their own runtime limits. It is not the model's declared context window.
    """

    recent_messages: int = Field(default=12, ge=1, le=MAX_RECENT_MESSAGES, strict=True)
    history_budget_bytes: int = Field(
        default=MAX_HISTORY_BYTES, ge=4_000, le=MAX_HISTORY_BYTES, strict=True
    )


class ConversationContextStore:
    def __init__(self, workspace_root: Path) -> None:
        self.path = workspace_root / "conversation-context.json"

    def load(self) -> ConversationContextSettings:
        if not self.path.is_file():
            return ConversationContextSettings()
        return ConversationContextSettings.model_validate_json(
            self.path.read_text(encoding="utf-8-sig")
        )

    def save(self, request: ConversationContextSettings) -> ConversationContextSettings:
        checked = ConversationContextSettings.model_validate(request)
        write_atomically(self.path, checked.model_dump_json(indent=2).encode("utf-8") + b"\n")
        return checked


def prepare_history(
    history: tuple[ModelMessage, ...], settings: ConversationContextSettings
) -> tuple[ModelMessage, ...]:
    """Keep a contiguous recent tail; never silently cut the current question."""
    if not history:
        return ()
    current = history[-1]
    if (
        len(current.text) > MAX_MESSAGE_CHARS
        or len(current.text.encode("utf-8")) > settings.history_budget_bytes
    ):
        raise ValueError("current_message_too_large")
    selected = [current]
    used = len(current.text.encode("utf-8"))
    for message in reversed(history[-settings.recent_messages : -1]):
        bounded = ModelMessage(role=message.role, text=message.text[:MAX_MESSAGE_CHARS])
        size = len(bounded.text.encode("utf-8"))
        if used + size > settings.history_budget_bytes:
            break
        selected.append(bounded)
        used += size
    selected.reverse()
    return tuple(selected)
