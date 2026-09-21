"""One `ModelClient` for every endpoint speaking the OpenAI chat-completions
format: the internal company gateway, a LiteLLM proxy, a public OpenAI-shaped
API. Adapted from the `Gateway` class in the pinned source's `agent/agent.py`
(`docs/PHASE_5_MIGRATION.md`).

Three properties the source could not have, and this must:

- **Nothing escapes.** A timeout, a refused connection, an HTTP status, a body
  that is not an answer and an adapter bug all become a typed `Failure` on the
  response or a `failed` stream event. The source called `SystemExit`; a
  library cannot end its host's process.
- **No credential leaves a header.** The value is resolved per request, because
  the source's token is rewritten on a schedule, and every error body is
  truncated and redacted before it becomes a message.
- **No dependency.** HTTP sits behind an injected `Transport`; the default one
  is the standard library, and no test opens a socket.

The wire's own quirks, learned from the source's compatibility settings, are
behavior here rather than configuration: a streaming chunk carrying no
`choices` is normal and skipped, and unknown fields inside `usage` are ignored.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Literal, Protocol

from common.assets import SECRET_PATTERN
from common.execution import Failure
from models.catalog import ModelEndpoint
from models.contracts import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)

MAX_ERROR_CHARS = 500
# A status worth trying again on: the request was not wrong, the moment was.
RETRYABLE_STATUS = frozenset({408, 429})
CHAT_PATH = "/chat/completions"


class Reply(Protocol):
    """One answer in progress. A status is an answer, never an exception."""

    status: int

    def chunks(self) -> Iterator[bytes]: ...

    def close(self) -> None: ...


class Transport(Protocol):
    """The whole HTTP surface this adapter needs. Arguments are plain values,
    never a contract: an `Authorization` header must not land in something
    serializable that could be logged or published."""

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> Reply: ...


class _UrllibReply:
    def __init__(self, raw: Any, status: int) -> None:
        self._raw = raw
        self.status = status

    def chunks(self) -> Iterator[bytes]:
        yield from self._raw

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:  # noqa: BLE001 - closing is best effort
            pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuses to follow a redirect. urllib copies every header it was given
    to the new location, `Authorization` included, and turns the POST into a
    bodyless GET on the way. A model endpoint that redirects is misconfigured,
    so the 3xx is reported as the status it is rather than chased."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


class UrllibTransport:
    """The standard library, so the platform's install stays `pydantic` alone."""

    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(_NoRedirect())

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> Reply:
        prepared = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        try:
            raw = self.opener.open(prepared, timeout=timeout_s)
        except urllib.error.HTTPError as answered:
            return _UrllibReply(answered, answered.code)
        return _UrllibReply(raw, int(getattr(raw, "status", 200)))


def _redacted(text: str) -> str:
    trimmed = text[:MAX_ERROR_CHARS].strip()
    return SECRET_PATTERN.sub("[redacted]", trimmed)


def _described(error: BaseException) -> str:
    return _redacted(f"{type(error).__name__}: {error}") or type(error).__name__


def _transport_failure(error: BaseException) -> Failure:
    """Which kind of unreachable, because only one of them suggests trying a
    different endpoint rather than the same one again."""
    reason = getattr(error, "reason", None)
    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
        return Failure(code="model_timeout", message=_described(error), retryable=True)
    if isinstance(error, OSError):
        return Failure(code="model_unreachable", message=_described(error), retryable=True)
    return Failure(code="model_error", message=_described(error), retryable=True)


def _status_failure(status: int, body: bytes) -> Failure:
    detail = _redacted(body.decode("utf-8", "replace")) or "(no body)"
    return Failure(
        code="model_http_error",
        message=f"{status}: {detail}",
        retryable=status in RETRYABLE_STATUS or status >= 500,
    )


def _close(reply: Reply) -> None:
    try:
        reply.close()
    except Exception:  # noqa: BLE001 - closing is best effort
        pass


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _wire_message(message: ModelMessage) -> dict[str, Any]:
    wire: dict[str, Any] = {"role": message.role}
    if message.images:
        parts: list[dict[str, Any]] = []
        if message.text:
            parts.append({"type": "text", "text": message.text})
        parts.extend(
            {"type": "image_url", "image_url": {"url": reference}} for reference in message.images
        )
        wire["content"] = parts
    else:
        wire["content"] = message.text
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def _lines(chunks: Iterator[bytes]) -> Iterator[bytes]:
    """Whole lines out of arbitrary byte chunks, so an event split across two
    reads is still one event."""
    buffer = b""
    for chunk in chunks:
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            yield line
    if buffer:
        yield buffer


def _event_data(line: bytes) -> str | None:
    """The payload of one server-sent event line; None for a comment, a blank
    separator or any other field."""
    text = line.strip()
    if not text.startswith(b"data:"):
        return None
    return text[len(b"data:") :].strip().decode("utf-8", "replace")


def _delta(payload: str) -> str | None:
    """The text a streaming chunk adds, or None when it adds none. A chunk
    with no `choices` is the internal gateway's usage-only prelude: normal,
    and the reason the source had to patch a private LiteLLM class."""
    try:
        body = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
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
        transport: Transport | None = None,
        timeout_s: float = 600.0,
        max_tokens_field: Literal["max_tokens", "max_completion_tokens"] = "max_tokens",
    ) -> None:
        if endpoint.base_url is None:
            raise ValueError("an openai-compatible endpoint needs a base url")
        if timeout_s <= 0:
            raise ValueError("a timeout is positive")
        if endpoint.credential is not None and credential is None:
            # Otherwise the calls go out anonymously and the endpoint answers
            # 401 at run time, long after the configuration mistake was made.
            raise ValueError("this endpoint declares a credential; supply a resolver for it")
        self.endpoint = endpoint
        self.url = endpoint.base_url.rstrip("/") + CHAT_PATH
        # Resolved per request, never captured: the internal token rotates.
        self.credential = credential
        self.transport = transport if transport is not None else UrllibTransport()
        self.timeout_s = timeout_s
        # Newer chat models reject `max_tokens` in favour of the longer name.
        self.max_tokens_field = max_tokens_field

    def _authorized(self) -> dict[str, str] | Failure:
        """The headers for one call. Resolving the credential is its own
        failure: a token being rewritten is not an unreachable endpoint."""
        headers = {"Content-Type": "application/json"}
        if self.credential is None:
            return headers
        try:
            token = self.credential()
        except Exception as error:  # noqa: BLE001 - a resolver's failure is a status here
            return Failure(
                code="credential_unavailable",
                message=_described(error),
                # The internal token is rewritten on a schedule, so a read can
                # fail for a moment and succeed immediately afterwards.
                retryable=True,
            )
        headers["Authorization"] = f"Bearer {token}"
        return headers

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

    def _failed(self, request: ModelRequest, failure: Failure) -> ModelResponse:
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, failure=failure)

    def _unsupported(self, request: ModelRequest) -> Failure | None:
        # A replayed exchange carries its tool calls on the messages rather
        # than in `tools`; sending it without them is an invalid conversation.
        if request.tools or any(message.tool_calls for message in request.messages):
            return Failure(
                code="tools_not_supported",
                message="a tool's input contract cannot yet be rendered as a provider schema",
                retryable=False,
            )
        return None

    def generate(self, request: ModelRequest) -> ModelResponse:
        refusal = self._unsupported(request)
        if refusal is not None:
            return self._failed(request, refusal)
        headers = self._authorized()
        if isinstance(headers, Failure):
            return self._failed(request, headers)
        try:
            reply = self.transport.send(
                self.url,
                json.dumps(self._payload(request, stream=False)).encode("utf-8"),
                headers,
                self.timeout_s,
            )
        except Exception as error:  # noqa: BLE001 - a provider failure is a status here
            return self._failed(request, _transport_failure(error))
        try:
            status = reply.status
            raw = b"".join(reply.chunks())
        except Exception as error:  # noqa: BLE001 - a read can fail like a send
            return self._failed(request, _transport_failure(error))
        finally:
            _close(reply)
        if status // 100 != 2:
            return self._failed(request, _status_failure(status, raw))
        return self._answer(request, raw)

    def _answer(self, request: ModelRequest, raw: bytes) -> ModelResponse:
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return self._failed(
                request,
                Failure(code="model_unparseable", message="the reply is not json"),
            )
        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            return self._failed(
                request,
                Failure(code="model_unparseable", message="the reply carries no choices"),
            )
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        text = content if isinstance(content, str) else ""
        usage = body.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        return ModelResponse(
            trace=request.trace,
            # The platform's alias. A provider echoes back whatever the client
            # asked for, so its `model` is no evidence of what served this.
            model_alias=request.model_alias,
            text=text,
            structured_output=_structured(request, text),
            input_tokens=_count(usage.get("prompt_tokens")),
            output_tokens=_count(usage.get("completion_tokens")),
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        def failed(failure: Failure) -> ModelStreamEvent:
            return ModelStreamEvent(trace=request.trace, kind="failed", failure=failure)

        if not request.requirements.streaming:
            yield failed(
                Failure(
                    code="streaming_not_declared",
                    message="a streaming call declares streaming in its requirements",
                )
            )
            return
        refusal = self._unsupported(request)
        if refusal is not None:
            yield failed(refusal)
            return
        headers = self._authorized()
        if isinstance(headers, Failure):
            yield failed(headers)
            return
        try:
            reply = self.transport.send(
                self.url,
                json.dumps(self._payload(request, stream=True)).encode("utf-8"),
                headers,
                self.timeout_s,
            )
        except Exception as error:  # noqa: BLE001 - a provider failure is a status here
            yield failed(_transport_failure(error))
            return
        answered = False
        try:
            if reply.status // 100 != 2:
                yield failed(_status_failure(reply.status, b"".join(reply.chunks())))
                return
            for line in _lines(reply.chunks()):
                payload = _event_data(line)
                if payload is None:
                    continue
                answered = True
                if payload == "[DONE]":
                    break
                text = _delta(payload)
                if text is not None:
                    yield ModelStreamEvent(trace=request.trace, kind="text", text=text)
        except Exception as error:  # noqa: BLE001 - a read can fail like a send
            yield failed(_transport_failure(error))
            return
        finally:
            _close(reply)
        if not answered:
            # An endpoint that ignored `stream: true` answered in one JSON
            # body. Reporting `done` would throw that answer away and call it
            # success; `generate` would have called the same body unparseable.
            yield failed(
                Failure(
                    code="model_unparseable",
                    message="the reply carries no server-sent events",
                )
            )
            return
        yield ModelStreamEvent(trace=request.trace, kind="done")


def _structured(request: ModelRequest, text: str) -> Any:
    """JSON only when it was asked for and the text really is JSON. Lenient
    salvage belongs to the caller that wants it, so nothing is invented here."""
    if request.output_contract is None or not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None
