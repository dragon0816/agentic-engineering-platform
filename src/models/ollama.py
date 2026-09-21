"""`ModelClient` over Ollama's own chat API, for the local half of the
platform's model layer.

This speaks `/api/chat` rather than Ollama's OpenAI-compatible shim
(`docs/PHASE_5_MIGRATION.md` records why): the native API is the stable one,
and the differences are real rather than cosmetic. Images travel as bare
base64 rather than `data:` URIs, the token limit is `options.num_predict`,
structured output is `format: "json"`, and a stream is newline-delimited JSON
objects rather than server-sent events. Everything that is not this wire
format lives in `models.wire`, so the two adapters cannot drift on what a
failure means.

Nothing here assumes the model is on this machine. `local` is a claim an
endpoint makes in the catalog, and a host may run Ollama on another box; this
adapter only needs an address.
"""

import json
import re
from collections.abc import Callable, Iterator
from typing import Any

from common.execution import Failure
from models import wire
from models.catalog import ModelEndpoint
from models.contracts import ModelMessage, ModelRequest, ModelResponse, ModelStreamEvent

CHAT_PATH = "/api/chat"
# Phase 4's describer builds `data:image/png;base64,...`; Ollama wants what
# comes after the comma and nothing else.
_DATA_URI = re.compile(r"^data:[^;,]*;base64,(?P<data>.+)$", re.DOTALL)


def _inline(reference: str) -> str | None:
    match = _DATA_URI.match(reference)
    return match.group("data") if match else None


def _wire_message(message: ModelMessage) -> dict[str, Any] | Failure:
    body: dict[str, Any] = {"role": message.role, "content": message.text}
    if not message.images:
        return body
    images: list[str] = []
    for reference in message.images:
        data = _inline(reference)
        if data is None:
            # Ollama embeds bytes; it does not fetch a URL. Sending the
            # reference verbatim would silently describe nothing.
            return Failure(
                code="image_not_inline",
                message="ollama takes base64 image data, not a reference to fetch",
                retryable=False,
            )
        images.append(data)
    body["images"] = images
    return body


def _content(body: object) -> str | None:
    """The text one reply or streaming object carries, or None when it is not
    shaped like either."""
    if not isinstance(body, dict):
        return None
    message = body.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else ""


class Ollama:
    """`ModelClient` over one Ollama server. `base_url` is the server root,
    such as `http://localhost:11434`; this appends `/api/chat`."""

    def __init__(
        self,
        endpoint: ModelEndpoint,
        *,
        credential: Callable[[], str] | None = None,
        transport: wire.Transport | None = None,
        timeout_s: float = 600.0,
    ) -> None:
        self.endpoint = endpoint
        self.url = wire.checked_base(endpoint, credential, timeout_s) + CHAT_PATH
        # Ollama itself is unauthenticated; a reverse proxy in front of it may
        # not be, so the same resolver rules apply as anywhere else.
        self.credential = credential
        self.transport = transport if transport is not None else wire.UrllibTransport()
        self.timeout_s = timeout_s

    def _payload(self, request: ModelRequest, *, stream: bool) -> dict[str, Any] | Failure:
        messages: list[dict[str, Any]] = []
        for message in request.messages:
            written = _wire_message(message)
            if isinstance(written, Failure):
                return written
            messages.append(written)
        payload: dict[str, Any] = {
            "model": self.endpoint.model,
            "messages": messages,
            # Ollama streams by default, so a single answer must say so.
            "stream": stream,
            "options": {"num_predict": request.max_output_tokens},
        }
        if request.output_contract is not None:
            # The contract names a platform shape Ollama knows nothing about;
            # all it is asked for is JSON. The caller validates.
            payload["format"] = "json"
        return payload

    def _prepare(
        self, request: ModelRequest, *, stream: bool
    ) -> tuple[bytes, dict[str, str]] | Failure:
        for refusal in (
            wire.undeclared_streaming(request) if stream else None,
            wire.unsupported(request),
        ):
            if refusal is not None:
                return refusal
        payload = self._payload(request, stream=stream)
        if isinstance(payload, Failure):
            return payload
        headers = wire.authorized(self.credential)
        if isinstance(headers, Failure):
            return headers
        return json.dumps(payload).encode("utf-8"), headers

    def generate(self, request: ModelRequest) -> ModelResponse:
        prepared = self._prepare(request, stream=False)
        if isinstance(prepared, Failure):
            return wire.failed_response(request, prepared)
        body, headers = prepared
        try:
            reply = self.transport.send(self.url, body, headers, self.timeout_s)
        except Exception as error:  # noqa: BLE001 - a provider failure is a status here
            return wire.failed_response(request, wire.transport_failure(error))
        try:
            status = reply.status
            raw = b"".join(reply.chunks())
        except Exception as error:  # noqa: BLE001 - a read can fail like a send
            return wire.failed_response(request, wire.transport_failure(error))
        finally:
            wire.close_quietly(reply)
        if status // 100 != 2:
            return wire.failed_response(request, wire.status_failure(status, raw))
        return self._answer(request, raw)

    def _answer(self, request: ModelRequest, raw: bytes) -> ModelResponse:
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return wire.failed_response(
                request, Failure(code="model_unparseable", message="the reply is not json")
            )
        reported = wire.provider_error(body)
        if reported is not None:
            return wire.failed_response(request, reported)
        text = _content(body)
        if text is None:
            return wire.failed_response(
                request,
                Failure(code="model_unparseable", message="the reply carries no message"),
            )
        counted = body if isinstance(body, dict) else {}
        return wire.answered(
            request,
            text=text,
            input_tokens=wire.token_count(counted.get("prompt_eval_count")),
            output_tokens=wire.token_count(counted.get("eval_count")),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        prepared = self._prepare(request, stream=True)
        if isinstance(prepared, Failure):
            yield wire.failed_event(request, prepared)
            return
        body, headers = prepared
        try:
            reply = self.transport.send(self.url, body, headers, self.timeout_s)
        except Exception as error:  # noqa: BLE001 - a provider failure is a status here
            yield wire.failed_event(request, wire.transport_failure(error))
            return
        answered = False
        try:
            if reply.status // 100 != 2:
                yield wire.failed_event(
                    request, wire.status_failure(reply.status, b"".join(reply.chunks()))
                )
                return
            for line in wire.lines(reply.chunks()):
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    # A half-written line is not the answer; the next one may be.
                    continue
                if not isinstance(chunk, dict):
                    continue
                answered = True
                reported = wire.provider_error(chunk)
                if reported is not None:
                    # Ollama reports a mid-stream failure in the body, the
                    # status having been sent long before.
                    yield wire.failed_event(request, reported)
                    return
                text = _content(chunk)
                if text:
                    yield ModelStreamEvent(trace=request.trace, kind="text", text=text)
                if chunk.get("done") is True:
                    break
        except Exception as error:  # noqa: BLE001 - a read can fail like a send
            yield wire.failed_event(request, wire.transport_failure(error))
            return
        finally:
            wire.close_quietly(reply)
        if not answered:
            # Nothing that parsed as an object: an error page, or a server
            # that is not Ollama. `generate` would refuse the same body.
            yield wire.failed_event(
                request,
                Failure(code="model_unparseable", message="the reply carries no json objects"),
            )
            return
        yield ModelStreamEvent(trace=request.trace, kind="done")
