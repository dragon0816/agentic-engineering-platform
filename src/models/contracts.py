"""Logical model requirements and adapter protocols, without provider wire objects."""

from collections.abc import Iterator
from typing import Literal, Protocol, Self

from pydantic import Field, JsonValue, StrictBool, model_validator

from common.base import Contract, Symbol, Text
from common.execution import Failure, TraceIdentifiers

# Declared weakest to strongest; `models.catalog` compares by this order, so
# the two layers cannot drift apart.
Reasoning = Literal["low", "medium", "high"]


class ModelRequirements(Contract):
    reasoning: Reasoning = "medium"
    tool_calling: StrictBool = False
    structured_output: StrictBool = False
    streaming: StrictBool = False
    vision: StrictBool = False
    local_only: StrictBool = False
    min_context_tokens: int = Field(default=1, ge=1, strict=True)


class ModelToolCall(Contract):
    call_id: Symbol
    name: Symbol
    arguments: dict[str, JsonValue]


class ModelMessage(Contract):
    role: Literal["system", "user", "assistant", "tool"]
    text: str = ""
    images: tuple[Text, ...] = ()
    tool_call_id: Symbol | None = None
    tool_calls: tuple[ModelToolCall, ...] = ()

    @model_validator(mode="after")
    def tool_result_identity(self) -> Self:
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("only tool-result messages require tool_call_id")
        if self.tool_calls and self.role != "assistant":
            raise ValueError("only assistant messages may contain tool calls")
        if not self.text.strip() and not self.images and not self.tool_calls:
            raise ValueError("message requires text, image references or tool calls")
        return self


class ModelTool(Contract):
    name: Symbol
    description: Text
    input_contract: Symbol


class ModelRequest(Contract):
    trace: TraceIdentifiers
    model_alias: Symbol
    messages: tuple[ModelMessage, ...] = Field(min_length=1)
    requirements: ModelRequirements = ModelRequirements()
    tools: tuple[ModelTool, ...] = ()
    output_contract: Symbol | None = None
    max_output_tokens: int = Field(default=1024, ge=1, strict=True)

    @model_validator(mode="after")
    def declared_requirements(self) -> Self:
        if self.tools and not self.requirements.tool_calling:
            raise ValueError("tools require tool_calling")
        if self.output_contract and not self.requirements.structured_output:
            raise ValueError("output contract requires structured_output")
        if any(message.images for message in self.messages) and not self.requirements.vision:
            raise ValueError("image input requires vision")
        return self


class ModelResponse(Contract):
    trace: TraceIdentifiers
    model_alias: Symbol
    text: str = ""
    tool_calls: tuple[ModelToolCall, ...] = ()
    structured_output: JsonValue = None
    failure: Failure | None = None
    input_tokens: int = Field(default=0, ge=0, strict=True)
    output_tokens: int = Field(default=0, ge=0, strict=True)
    # How long the provider took, so evaluation can compare aliases on latency
    # as well as on quality and usage. None when nothing was measured, which
    # is not the same as a call that took no time: a refusal made before any
    # request must not be averaged in as an instant answer.
    duration_ms: int | None = Field(default=None, ge=0, strict=True)


class ModelStreamEvent(Contract):
    trace: TraceIdentifiers
    kind: Literal["text", "tool_call", "done", "failed"]
    text: str | None = None
    tool_call: ModelToolCall | None = None
    failure: Failure | None = None
    # Set on a terminal event, counting only time spent waiting on the
    # provider, so a stream is comparable to a single call. None when nothing
    # was measured.
    duration_ms: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def event_payload(self) -> Self:
        present = (self.text is not None, self.tool_call is not None, self.failure is not None)
        expected = {
            "text": (True, False, False),
            "tool_call": (False, True, False),
            "done": (False, False, False),
            "failed": (False, False, True),
        }
        if present != expected[self.kind]:
            raise ValueError("stream payload must match event kind")
        return self


class ModelClient(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse: ...

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]: ...


class ModelSelector(Protocol):
    def select(self, requirements: ModelRequirements) -> Symbol | Failure: ...
