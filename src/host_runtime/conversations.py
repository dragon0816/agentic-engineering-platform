"""Durable, local-only Personal Agent conversation evidence."""

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, StrictBool, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Symbol, Text
from common.execution import TraceIdentifiers
from host_runtime.conversation_backends import ConversationBackendName

MAX_STORED_MESSAGES = 100


FeedbackRating = Literal["up", "down", "neutral"]


class MessageFeedback(Contract):
    """The user's rating of one answer, with an optional reason."""

    rating: FeedbackRating
    note: str | None = Field(default=None, max_length=2000)
    updated_at: datetime


class ConversationMessage(Contract):
    message_id: Symbol
    role: Literal["user", "assistant"]
    text: Text
    created_at: datetime
    status: Literal["submitted", "answered", "needs_input", "failed"]
    trace: TraceIdentifiers | None = None
    # A user message may reply to an earlier exchange (its assistant message).
    reply_to: Symbol | None = None
    # Only an answer carries the user's feedback.
    feedback: MessageFeedback | None = None

    @model_validator(mode="after")
    def user_and_assistant_evidence(self) -> Self:
        if self.role == "user" and (self.status != "submitted" or self.trace is not None):
            raise ValueError("a user message is submitted and carries no result trace")
        if self.role == "assistant" and self.status == "submitted":
            raise ValueError("an assistant message records an outcome")
        if self.role == "user" and self.feedback is not None:
            raise ValueError("feedback rates an answer, not a question")
        if self.role == "assistant" and self.reply_to is not None:
            raise ValueError("only a question replies to an earlier exchange")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ConversationRecord(Contract):
    session_id: Symbol
    actor: Symbol
    title: Text
    backend: ConversationBackendName = "gateway"
    data_classification: Literal["UNCLASSIFIED", "PUBLIC"] = "UNCLASSIFIED"
    classified_by: Symbol | None = None
    created_at: datetime
    updated_at: datetime
    messages: tuple[ConversationMessage, ...] = Field(default=(), max_length=MAX_STORED_MESSAGES)

    @model_validator(mode="after")
    def ordered_history(self) -> Self:
        if (self.data_classification == "PUBLIC") != (self.classified_by is not None):
            raise ValueError("PUBLIC conversation requires an explicit classifier")
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


class ConversationDeleteRequest(Contract):
    session_id: Symbol


class ConversationTurnRequest(Contract):
    session_id: Symbol
    message: Text
    reply_to: Symbol | None = None

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ConversationFeedbackRequest(Contract):
    session_id: Symbol
    message_id: Symbol
    rating: FeedbackRating
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ConversationBackendSelectRequest(Contract):
    session_id: Symbol
    backend: ConversationBackendName
    public_context: StrictBool = False

    @model_validator(mode="after")
    def public_declaration_is_for_external_backend(self) -> Self:
        if self.public_context and self.backend == "gateway":
            raise ValueError("Gateway selection cannot declare a PUBLIC session")
        return self


class ConversationBackendAuthenticationRequest(Contract):
    backend: ConversationBackendName

    @model_validator(mode="after")
    def local_cli_only(self) -> Self:
        if self.backend == "gateway":
            raise ValueError("Gateway credentials are configured through Settings")
        return self
