"""One `ModelClient` for every endpoint speaking the OpenAI chat-completions
format: the internal company gateway, a LiteLLM proxy, a public OpenAI-shaped
API. Adapted from the `Gateway` class in the pinned source's `agent/agent.py`
(`docs/PHASE_5_MIGRATION.md`); everything not specific to this wire format
lives in `models.wire`.

The wire's own quirks, learned from the source's compatibility settings, are
behavior here rather than configuration: a streaming chunk carrying no
`choices` is normal and skipped, and unknown fields inside `usage` are ignored.
"""

import json
from collections.abc import Callable, Iterator
from typing import Any, Literal

from common.execution import Failure
from models import wire
from models.catalog import ModelEndpoint
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelStreamEvent

CHAT_PATH = "/chat/completions"


def _wire_message(message: ModelMessage) -> dict[str, Any]:
    body: dict[str, Any] = {"role": message.role}
    if message.images:
        parts: list[dict[str, Any]] = []
        if message.text:
            parts.append({"type": "text", "text": message.text})
        parts.extend(
            {"type": "image_url", "image_url": {"url": reference}} for reference in message.images
        )
        body["content"] = parts
    else:
        body["content"] = message.text
    if message.tool_call_id is not None:
        body["tool_call_id"] = message.tool_call_id
    return body


def _event_data(line: bytes) -> str | None:
    """The payload of one server-sent event line; None for a comment, a blank
    separator or any other field."""
    text = line.strip()
    if not text.startswith(b"data:"):
        return None
    return text[len(b"data:") :].strip().decode("utf-8", "replace")


def _parsed(payload: str) -> dict[str, Any] | None:
    try:
        body = json.loads(payload)
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _delta(body: dict[str, Any]) -> str | None:
    """The text a streaming chunk adds, or None when it adds none. A chunk
    with no `choices` is the internal gateway's usage-only prelude: normal,
    and the reason the source had to patch a private LiteLLM class."""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    delta = first.get("delta") if isinstance(first, dict) else None
    content = delta.get("content") if isinstance(delta, dict) else None
    return content if isinstance(content, str) and content else None


class OpenAICompatible:
    """`ModelClient` over one OpenAI-shaped endpoint. `base_url` is the API
    root; this appends `/chat/completions`."""

    def __init__(
        self,
        endpoint: ModelEndpoint,
        *,
        credential: Callable[[], str] | None = None,
        transport: wire.Transport | None = None,
        timeout_s: float = 600.0,
        max_tokens_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens",
    ) -> None:
        self.endpoint = endpoint
        self.url = wire.checked_base(endpoint, credential, timeout_s) + CHAT_PATH
        # Resolved per request, never captured: the internal token rotates.
        self.credential = credential
        self.transport = transport if transport is not None else wire.UrllibTransport()
        self.timeout_s = timeout_s
        # Newer chat models reject `max_tokens` in favour of the longer name.
        self.max_tokens_field = max_tokens_field

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": [_wire_message(message) for message in request.messages],
            self.max_tokens_field: request.max_output_tokens,
        }
        if request.output_contract is not None:
            # The contract names a platform shape the provider knows nothing
            # about; all it is asked for is JSON. The caller validates.
            payload["response_format"] = {"type": "json_object"}
        if stream:
            payload["stream"] = True
        return payload

    def generate(self, request: ModelRequest) -> ModelResponse:
        refusal = wire.unsupported(request)
        if refusal is not None:
            return wire.failed_response(request, refusal)
        headers = wire.authorized(self.credential)
        if isinstance(headers, Failure):
            return wire.failed_response(request, headers)
        elapsed = wire.Elapsed()
        try:
            reply = self.transport.send(
                self.url,
                json.dumps(self._payload(request, stream=False)).encode("utf-8"),
                headers,
                self.timeout_s,
            )
        except Exception as error:  # noqa: BLE001 - a provider failure is a status here
            return wire.failed_response(
                request, wire.transport_failure(error), duration_ms=elapsed.ms
            )
        try:
            status = reply.status
            raw = b"".join(reply.chunks())
        except Exception as error:  # noqa: BLE001 - a read can fail like a send
            return wire.failed_response(
                request, wire.transport_failure(error), duration_ms=elapsed.ms
            )
        finally:
            wire.close_quietly(reply)
        if status // 100 != 2:
            return wire.failed_response(
                request, wire.status_failure(status, raw), duration_ms=elapsed.ms
            )
        return self._answer(request, raw, elapsed.ms)

    def _answer(self, request: ModelRequest, raw: bytes, duration_ms: int) -> ModelResponse:
        def refused(failure: Failure) -> ModelResponse:
            return wire.failed_response(request, failure, duration_ms=duration_ms)

        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return refused(Failure(code="model_unparseable", message="the reply is not json"))
        reported = wire.provider_error(body)
        if reported is not None:
            return refused(reported)
        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return refused(
                Failure(code="model_unparseable", message="the reply carries no choices")
            )
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        usage = body.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        return wire.answered(
            request,
            text=content if isinstance(content, str) else "",
            input_tokens=wire.token_count(usage.get("prompt_tokens")),
            output_tokens=wire.token_count(usage.get("completion_tokens")),
            duration_ms=duration_ms,
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        for refusal in (wire.undeclared_streaming(request), wire.unsupported(request)):
            if refusal is not None:
                yield wire.failed_event(request, refusal)
                return
        headers = wire.authorized(self.credential)
        if isinstance(headers, Failure):
            yield wire.failed_event(request, headers)
            return
        elapsed = wire.Elapsed()
        try:
            reply = self.transport.send(
                self.url,
                json.dumps(self._payload(request, stream=True)).encode("utf-8"),
                headers,
                self.timeout_s,
            )
        except Exception as error:  # noqa: BLE001 - a provider failure is a status here
            yield wire.failed_event(request, wire.transport_failure(error), duration_ms=elapsed.ms)
            return
        answered = False
        try:
            if reply.status // 100 != 2:
                yield wire.failed_event(
                    request,
                    wire.status_failure(reply.status, b"".join(reply.chunks())),
                    duration_ms=elapsed.ms,
                )
                return
            for line in wire.lines(reply.chunks()):
                payload = _event_data(line)
                if payload is None:
                    continue
                answered = True
                if payload == "[DONE]":
                    break
                chunk = _parsed(payload)
                if chunk is None:
                    continue
                reported = wire.provider_error(chunk)
                if reported is not None:
                    # Once the status is sent, a refusal can only arrive in
                    # the body; reading past it would call it a success.
                    yield wire.failed_event(request, reported, duration_ms=elapsed.ms)
                    return
                text = _delta(chunk)
                if text is not None:
                    yield ModelStreamEvent(trace=request.trace, kind="text", text=text)
        except Exception as error:  # noqa: BLE001 - a read can fail like a send
            yield wire.failed_event(request, wire.transport_failure(error), duration_ms=elapsed.ms)
            return
        finally:
            wire.close_quietly(reply)
        if not answered:
            # An endpoint that ignored `stream: true` answered in one JSON
            # body. Reporting `done` would throw that answer away and call it
            # success; `generate` would have called the same body unparseable.
            yield wire.failed_event(
                request,
                Failure(
                    code="model_unparseable", message="the reply carries no server-sent events"
                ),
                duration_ms=elapsed.ms,
            )
            return
        yield ModelStreamEvent(trace=request.trace, kind="done", duration_ms=elapsed.ms)
