"""What every HTTP model adapter shares, so a second provider is its wire
format and nothing else.

The rules here are the ones that must hold identically whoever is answering:
nothing escapes as an exception, no credential leaves a header, a status is an
answer rather than a failure of the transport, and the platform adds no
dependency. A provider module is then only its own payload shape, its own
reply shape and its own idea of a streaming chunk.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from time import monotonic
from typing import Any, Protocol

from common.assets import REDACTED, SECRET_PATTERN
from common.execution import Failure
from models.catalog import ModelEndpoint
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from models.credentials import CredentialMisconfigured

MAX_ERROR_CHARS = 500
# A status worth trying again on: the request was not wrong, the moment was.
RETRYABLE_STATUS = frozenset({408, 429})


class Reply(Protocol):
    """One answer in progress. A status is an answer, never an exception."""

    status: int

    def chunks(self) -> Iterator[bytes]: ...

    def close(self) -> None: ...


class Transport(Protocol):
    """The whole HTTP surface an adapter needs. Arguments are plain values,
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
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
        self.opener = urllib.request.build_opener(NoRedirect())

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> Reply:
        prepared = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        try:
            raw = self.opener.open(prepared, timeout=timeout_s)
        except urllib.error.HTTPError as answered:
            return _UrllibReply(answered, answered.code)
        return _UrllibReply(raw, int(getattr(raw, "status", 200)))


def redacted(text: str) -> str:
    """Redact, then trim: a credential that straddles the cut would otherwise
    survive as a fragment the pattern no longer recognizes."""
    return SECRET_PATTERN.sub(REDACTED, text)[:MAX_ERROR_CHARS].strip()


def describe(error: BaseException) -> str:
    return redacted(f"{type(error).__name__}: {error}") or type(error).__name__


def transport_failure(error: BaseException, *, prefix: str = "model") -> Failure:
    """Which kind of unreachable, because only one of them suggests trying a
    different endpoint rather than the same one again. `prefix` names the
    wire that failed; every HTTP adapter in the repository uses this one rule."""
    reason = getattr(error, "reason", None)
    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
        return Failure(code=f"{prefix}_timeout", message=describe(error), retryable=True)
    if isinstance(error, OSError):
        return Failure(code=f"{prefix}_unreachable", message=describe(error), retryable=True)
    return Failure(code=f"{prefix}_error", message=describe(error), retryable=True)


def status_failure(status: int, body: bytes, *, prefix: str = "model") -> Failure:
    detail = redacted(body.decode("utf-8", "replace")) or "(no body)"
    return Failure(
        code=f"{prefix}_http_error",
        message=f"{status}: {detail}",
        retryable=status in RETRYABLE_STATUS or status >= 500,
    )


def close_quietly(reply: Reply) -> None:
    try:
        reply.close()
    except Exception:  # noqa: BLE001 - closing is best effort
        pass


def token_count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def lines(chunks: Iterator[bytes]) -> Iterator[bytes]:
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


def checked_base(
    endpoint: ModelEndpoint, credential: Callable[[], str] | None, timeout_s: float
) -> str:
    """The endpoint's API root, with the configuration mistakes that are
    programming errors refused here rather than met at run time."""
    if endpoint.base_url is None:
        raise ValueError("an http endpoint needs a base url")
    if timeout_s <= 0:
        raise ValueError("a timeout is positive")
    if endpoint.credential is not None and credential is None:
        # Otherwise the calls go out anonymously and the endpoint answers 401
        # at run time, long after the configuration mistake was made.
        raise ValueError("this endpoint declares a credential; supply a resolver for it")
    return endpoint.base_url.rstrip("/")


def authorized(credential: Callable[[], str] | None) -> dict[str, str] | Failure:
    """The headers for one call, with the credential resolved now rather than
    captured. Resolving it is its own failure: a token being rewritten is not
    an unreachable endpoint, and the endpoint was never asked."""
    headers = {"Content-Type": "application/json"}
    if credential is None:
        return headers
    try:
        token = credential()
    except Exception as error:  # noqa: BLE001 - a resolver's failure is a status here
        return Failure(
            code="credential_unavailable",
            message=describe(error),
            # A rotating token is rewritten on a schedule, so a read can fail
            # for a moment and succeed immediately afterwards. A secret nothing
            # is mapped to will never appear, however often it is asked for.
            retryable=not isinstance(error, CredentialMisconfigured),
        )
    headers["Authorization"] = f"Bearer {token}"
    return headers


def provider_error(body: object) -> Failure | None:
    """A provider that answered 2xx and put its refusal in the body. Ollama
    does this for a model it does not have, and once a stream's headers are
    sent there is no status left to carry an error, so both wire formats can
    report one this way. Reading past it would turn a refusal into an empty
    success and throw the server's own explanation away."""
    if not isinstance(body, dict):
        return None
    reported = body.get("error")
    if reported is None:
        return None
    if isinstance(reported, dict):
        inner = reported.get("message")
        text = inner if isinstance(inner, str) else json.dumps(reported)
    else:
        text = reported if isinstance(reported, str) else json.dumps(reported)
    return Failure(
        code="provider_error",
        message=redacted(text) or "(empty error)",
        # The provider understood and declined: a missing model or a rejected
        # option does not fix itself on the next identical call.
        retryable=False,
    )


def unsupported(request: ModelRequest) -> Failure | None:
    """Tool calling, in either of the shapes a request can carry it. A
    `ModelTool` names a platform contract, and rendering that as a provider
    schema needs a registry that does not exist yet."""
    # A replayed exchange carries its tool calls on the messages rather than
    # in `tools`; sending it without them is an invalid conversation.
    if request.tools or any(message.tool_calls for message in request.messages):
        return Failure(
            code="tools_not_supported",
            message="a tool's input contract cannot yet be rendered as a provider schema",
            retryable=False,
        )
    return None


def undeclared_streaming(request: ModelRequest) -> Failure | None:
    if request.requirements.streaming:
        return None
    return Failure(
        code="streaming_not_declared",
        message="a streaming call declares streaming in its requirements",
    )


def structured(request: ModelRequest, text: str) -> Any:
    """JSON only when it was asked for and the text really is JSON. Lenient
    salvage belongs to the caller that wants it, so nothing is invented here."""
    if request.output_contract is None or not text.strip():
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


class Elapsed:
    """How long the provider took. Started when a call goes out, so a request
    refused before that reports nothing rather than a misleading zero.
    Monotonic, because a clock adjustment must not produce a negative latency
    in an evaluation. The payload is built before the clock starts, so two
    adapters measure the same span and a large image does not count against
    whichever provider happens to receive it."""

    def __init__(self) -> None:
        self._started = monotonic()

    @property
    def ms(self) -> int:
        return max(0, round((monotonic() - self._started) * 1000))


class Waited:
    """The time a stream spent waiting on its source, and none of the time its
    consumer spent between pulls. A stream is read as the caller iterates, so
    measuring wall clock to the last event would charge a provider for a
    harness that renders slowly, and a model that sends many small deltas
    would rank as the slow one."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._waited = 0.0

    @property
    def ms(self) -> int:
        return max(0, round(self._waited * 1000))

    def __iter__(self) -> Iterator[bytes]:
        while True:
            started = monotonic()
            try:
                chunk = next(self._chunks)
            except StopIteration:
                self._waited += monotonic() - started
                return
            self._waited += monotonic() - started
            yield chunk


def failed_response(
    request: ModelRequest, failure: Failure, *, duration_ms: int | None = None
) -> ModelResponse:
    return ModelResponse(
        trace=request.trace,
        model_alias=request.model_alias,
        failure=failure,
        duration_ms=duration_ms,
    )


def failed_event(
    request: ModelRequest, failure: Failure, *, duration_ms: int | None = None
) -> ModelStreamEvent:
    return ModelStreamEvent(
        trace=request.trace, kind="failed", failure=failure, duration_ms=duration_ms
    )


def answered(
    request: ModelRequest,
    *,
    text: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int | None = None,
) -> ModelResponse:
    return ModelResponse(
        trace=request.trace,
        # The platform's alias. A provider echoes back whatever the client
        # asked for, so its own `model` is no evidence of what served this.
        model_alias=request.model_alias,
        text=text,
        structured_output=structured(request, text),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
    )
