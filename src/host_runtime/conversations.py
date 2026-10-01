"""Durable, local-only Personal Agent conversation evidence."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Symbol, Text
from common.execution import TraceIdentifiers


class ConversationMessage(Contract):
    message_id: Symbol
    role: Literal["user", "assistant"]
    text: Text
    created_at: datetime
    status: Literal["submitted", "answered", "needs_input", "failed"]
    trace: TraceIdentifiers | None = None

    @model_validator(mode="after")
    def user_and_assistant_evidence(self) -> Self:
        if self.role == "user" and (self.status != "submitted" or self.trace is not None):
            raise ValueError("a user message is submitted and carries no result trace")
        if self.role == "assistant" and self.status == "submitted":
            raise ValueError("an assistant message records an outcome")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ConversationRecord(Contract):
    session_id: Symbol
    actor: Symbol
    title: Text
    created_at: datetime
    updated_at: datetime
    messages: tuple[ConversationMessage, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def ordered_history(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("a conversation cannot be updated before it was created")
        moments = [item.created_at for item in self.messages]
        if moments != sorted(moments):
            raise ValueError("conversation messages are chronological")
        if self.messages and self.updated_at < self.messages[-1].created_at:
            raise ValueError("conversation update covers its latest message")
        return self


class ConversationCreateRequest(Contract):
    """An explicit empty request; identity and title come from the host."""


class ConversationTurnRequest(Contract):
    session_id: Symbol
    message: Text

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self
