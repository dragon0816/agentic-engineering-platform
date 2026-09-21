"""The OpenAI-compatible adapter: one wire format mapped both ways, every
provider failure a typed status, and no credential anywhere but a header."""

import io
import json
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from email.message import Message
from typing import Any

import pytest

from common.assets import SecretRef
from common.execution import TraceIdentifiers
from models.catalog import ModelCapabilities, ModelEndpoint
from models.contracts import (
    ModelClient,
    ModelMessage,
    ModelRequest,
    ModelRequirements,
    ModelTool,
    ModelToolCall,
)
from models.openai_compatible import OpenAICompatible
from models.wire import NoRedirect, UrllibTransport, status_failure

TRACE = TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1")
ANSWER: dict[str, Any] = {
    "id": "chatcmpl-1",
    "model": "gpt-5.6-luna",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "the answer"}}],
    "usage": {"prompt_tokens": 11, "completion_tokens": 7, "latency_checkpoint": {"first": 0.2}},
}


class Reply:
    def __init__(self, status: int, chunks: list[bytes]) -> None:
        self.status = status
        self._chunks = chunks
        self.closed = False

    def chunks(self) -> Iterator[bytes]:
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class Transport:
    def __init__(self, reply: Reply | None = None, error: BaseException | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def send(self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float) -> Reply:
        self.calls.append(
            {
                "url": url,
                "payload": json.loads(body),
                "headers": dict(headers),
                "timeout_s": timeout_s,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.reply is not None
        return self.reply


def json_reply(body: dict[str, Any], status: int = 200) -> Reply:
    return Reply(status, [json.dumps(body).encode("utf-8")])


def endpoint(**changes: Any) -> ModelEndpoint:
    return ModelEndpoint.model_validate(
        {
            "alias": "company",
            "provider": "openai_compatible",
            "model": "gpt-5.5",
            "base_url": "https://gateway.invalid/api",
            "capabilities": ModelCapabilities(
                max_context_tokens=128_000, streaming=True, vision=True, structured_output=True
            ),
            **changes,
        }
    )


def request(**changes: Any) -> ModelRequest:
    return ModelRequest.model_validate(
        {
            "trace": TRACE,
            "model_alias": "company",
            "messages": (ModelMessage(role="user", text="ask"),),
            "max_output_tokens": 256,
            **changes,
        }
    )


def test_a_generate_call_maps_the_wire_both_ways() -> None:
    transport = Transport(json_reply(ANSWER))
    client: ModelClient = OpenAICompatible(
        endpoint(), credential=lambda: "rotating-token", transport=transport, timeout_s=30
    )
    response = client.generate(request())

    (call,) = transport.calls
    assert call["url"] == "https://gateway.invalid/api/chat/completions"
    assert call["timeout_s"] == 30
    assert call["payload"] == {
        "model": "gpt-5.5",
        "messages": [{"role": "user", "content": "ask"}],
        "max_tokens": 256,
    }
    assert call["headers"]["Authorization"] == "Bearer rotating-token"
    assert call["headers"]["Content-Type"] == "application/json"

    assert response.failure is None and response.text == "the answer"
    assert response.input_tokens == 11 and response.output_tokens == 7
    # The platform's alias, never the provider's echo of what it says it ran.
    assert response.model_alias == "company" and response.trace == TRACE
    assert transport.reply is not None and transport.reply.closed


def test_images_and_a_declared_output_contract_reach_the_wire() -> None:
    transport = Transport(
        json_reply({**ANSWER, "choices": [{"message": {"content": '{"kind": "workflow"}'}}]})
    )
    client = OpenAICompatible(endpoint(), transport=transport)
    response = client.generate(
        request(
            messages=(
                ModelMessage(role="system", text="be exact"),
                ModelMessage(role="user", text="describe", images=("data:image/png;base64,AAA",)),
            ),
            requirements=ModelRequirements(vision=True, structured_output=True),
            output_contract="platform.route-proposal.v1",
        )
    )
    payload = transport.calls[0]["payload"]
    assert payload["messages"][0] == {"role": "system", "content": "be exact"}
    assert payload["messages"][1] == {
        "role": "user",
        "content": [
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
        ],
    }
    # A contract name is a platform identifier; the provider is only asked for JSON.
    assert payload["response_format"] == {"type": "json_object"}
    assert "platform.route-proposal.v1" not in json.dumps(payload)
    assert response.structured_output == {"kind": "workflow"}
    assert response.text == '{"kind": "workflow"}'

    # Text that is not JSON leaves structured_output empty; salvage is the
    # caller's business, and the text is never lost.
    prose = Transport(json_reply({**ANSWER, "choices": [{"message": {"content": "```json {}"}}]}))
    loose = OpenAICompatible(endpoint(), transport=prose).generate(
        request(
            requirements=ModelRequirements(structured_output=True),
            output_contract="platform.route-proposal.v1",
        )
    )
    assert loose.structured_output is None and loose.text == "```json {}"
    assert loose.failure is None


def test_usage_and_credentials_are_read_fresh_on_every_call() -> None:
    issued: list[str] = []

    def credential() -> str:
        issued.append(f"token-{len(issued)}")
        return issued[-1]

    transport = Transport(json_reply({**ANSWER, "usage": {}}))
    client = OpenAICompatible(endpoint(), credential=credential, transport=transport)
    first = client.generate(request())
    assert first.input_tokens == 0 and first.output_tokens == 0

    client.generate(request())
    # Resolved per request: the source's token is rewritten on a schedule.
    assert [call["headers"]["Authorization"] for call in transport.calls] == [
        "Bearer token-0",
        "Bearer token-1",
    ]

    anonymous = Transport(json_reply(ANSWER))
    OpenAICompatible(endpoint(), transport=anonymous).generate(request())
    assert "Authorization" not in anonymous.calls[0]["headers"]


def test_streaming_skips_what_is_not_an_answer_and_always_ends() -> None:
    chunks = [
        b": keep-alive\n",
        # chatrs opens with a usage-only chunk carrying no choices at all.
        b'data: {"choices": [], "usage": {"latency_checkpoint": {}}}\n',
        b'data: {"choices": [{"delta": {"role": "assistant"}}]}\n',
        b'data: {"choices": [{"delta": {"content": "the "}}]}\n',
        b"data: not json\n",
        b'data: {"choices": [{"delta": {"content": "answer"}}]}\n',
        b"data: [DONE]\n",
    ]
    transport = Transport(Reply(200, chunks))
    client = OpenAICompatible(endpoint(), transport=transport)
    events = list(client.stream(request(requirements=ModelRequirements(streaming=True))))

    assert [event.kind for event in events] == ["text", "text", "done"]
    assert [event.text for event in events[:2]] == ["the ", "answer"]
    assert all(event.trace == TRACE for event in events)
    assert transport.calls[0]["payload"]["stream"] is True
    assert transport.reply is not None and transport.reply.closed

    # A stream that stops without [DONE], and a line split across two chunks.
    split = Transport(Reply(200, [b'data: {"choices": [{"delta": {"con', b'tent": "x"}}]}']))
    ended = list(
        OpenAICompatible(endpoint(), transport=split).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in ended] == ["text", "done"] and ended[0].text == "x"

    # Streaming that was never declared is refused, as tools are.
    undeclared = Transport(Reply(200, []))
    refused = list(OpenAICompatible(endpoint(), transport=undeclared).stream(request()))
    assert [event.kind for event in refused] == ["failed"]
    assert refused[0].failure is not None
    assert refused[0].failure.code == "streaming_not_declared"
    assert undeclared.calls == []


@pytest.mark.parametrize(
    ("error", "code", "retryable"),
    [
        (TimeoutError("slow"), "model_timeout", True),
        (urllib.error.URLError(TimeoutError("slow")), "model_timeout", True),
        (urllib.error.URLError("connection refused"), "model_unreachable", True),
        (OSError("host is down"), "model_unreachable", True),
        (RuntimeError("adapter bug"), "model_error", True),
    ],
)
def test_a_transport_that_raises_is_a_status(
    error: BaseException, code: str, retryable: bool
) -> None:
    client = OpenAICompatible(endpoint(), transport=Transport(error=error))
    response = client.generate(request())
    assert response.failure is not None
    assert response.failure.code == code and response.failure.retryable is retryable
    assert response.trace == TRACE and response.model_alias == "company"

    streamed = list(client.stream(request(requirements=ModelRequirements(streaming=True))))
    assert [event.kind for event in streamed] == ["failed"]
    assert streamed[0].failure is not None and streamed[0].failure.code == code


@pytest.mark.parametrize(
    ("status", "retryable"), [(400, False), (401, False), (408, True), (429, True), (503, True)]
)
def test_an_http_status_is_an_answer_with_a_redacted_body(status: int, retryable: bool) -> None:
    body = b'{"error": "rejected", "echo": "Authorization: Bearer sk-live-abcdef"}'
    transport = Transport(Reply(status, [body]))
    response = OpenAICompatible(endpoint(), transport=transport).generate(request())

    assert response.failure is not None
    assert response.failure.code == "model_http_error"
    assert response.failure.retryable is retryable
    assert str(status) in response.failure.message
    assert "sk-live-abcdef" not in response.failure.message
    assert "[redacted]" in response.failure.message
    assert transport.reply is not None and transport.reply.closed


def test_a_reply_that_is_not_an_answer_is_unparseable() -> None:
    for chunks in ([b"<html>gateway</html>"], [b'{"choices": []}'], [b'{"ok": true}']):
        response = OpenAICompatible(endpoint(), transport=Transport(Reply(200, chunks))).generate(
            request()
        )
        assert response.failure is not None
        assert response.failure.code == "model_unparseable"
        assert not response.failure.retryable

    streamed = list(
        OpenAICompatible(endpoint(), transport=Transport(Reply(500, [b"down"]))).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert streamed[0].kind == "failed"
    assert streamed[0].failure is not None and streamed[0].failure.code == "model_http_error"


def test_tools_are_refused_until_a_contract_can_be_a_schema() -> None:
    transport = Transport(json_reply(ANSWER))
    response = OpenAICompatible(endpoint(), transport=transport).generate(
        request(
            requirements=ModelRequirements(tool_calling=True),
            tools=(ModelTool(name="read_file", description="read", input_contract="fs.read.v1"),),
        )
    )
    assert response.failure is not None
    assert response.failure.code == "tools_not_supported" and not response.failure.retryable
    assert transport.calls == []  # refused before anything was sent


def test_an_endpoint_without_an_address_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="base url"):
        OpenAICompatible(endpoint(base_url=None))
    with pytest.raises(ValueError, match="timeout"):
        OpenAICompatible(endpoint(), timeout_s=0)
    # A trailing slash on the root does not double the separator.
    client = OpenAICompatible(endpoint(base_url="https://gateway.invalid/api/"))
    assert client.url == "https://gateway.invalid/api/chat/completions"


def test_a_declared_credential_needs_a_resolver_and_can_fail_on_its_own() -> None:
    declaring = endpoint(credential=SecretRef(name="company_gateway_token"))
    with pytest.raises(ValueError, match="supply a resolver"):
        OpenAICompatible(declaring)

    def unavailable() -> str:
        raise OSError("the token file is being rewritten")

    transport = Transport(json_reply(ANSWER))
    client = OpenAICompatible(declaring, credential=unavailable, transport=transport)
    response = client.generate(request())
    assert response.failure is not None
    # Not "unreachable": the endpoint was never asked.
    assert response.failure.code == "credential_unavailable"
    assert response.failure.retryable
    assert transport.calls == []

    streamed = list(client.stream(request(requirements=ModelRequirements(streaming=True))))
    assert [event.kind for event in streamed] == ["failed"]
    assert streamed[0].failure is not None
    assert streamed[0].failure.code == "credential_unavailable"


def test_a_replayed_tool_exchange_is_refused_like_a_tool_request() -> None:
    transport = Transport(json_reply(ANSWER))
    call = ModelToolCall(call_id="c1", name="read_file", arguments={"path": "a.md"})
    response = OpenAICompatible(endpoint(), transport=transport).generate(
        request(
            messages=(
                ModelMessage(role="user", text="read it"),
                ModelMessage(role="assistant", tool_calls=(call,)),
                ModelMessage(role="tool", text="contents", tool_call_id="c1"),
            )
        )
    )
    assert response.failure is not None
    assert response.failure.code == "tools_not_supported"
    assert transport.calls == []


def test_a_stream_that_is_not_a_stream_is_not_a_silent_success() -> None:
    # An endpoint that ignored `stream: true` and answered in one JSON body.
    whole = Transport(Reply(200, [json.dumps(ANSWER).encode("utf-8")]))
    events = list(
        OpenAICompatible(endpoint(), transport=whole).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in events] == ["failed"]
    assert events[0].failure is not None and events[0].failure.code == "model_unparseable"

    # An immediate [DONE] is a real, empty stream and stays a success.
    empty = Transport(Reply(200, [b"data: [DONE]\n"]))
    ended = list(
        OpenAICompatible(endpoint(), transport=empty).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in ended] == ["done"]


def test_the_token_field_is_configurable_for_newer_models() -> None:
    transport = Transport(json_reply(ANSWER))
    OpenAICompatible(
        endpoint(), transport=transport, max_tokens_field="max_completion_tokens"
    ).generate(request())
    payload = transport.calls[0]["payload"]
    assert payload["max_completion_tokens"] == 256 and "max_tokens" not in payload


def test_the_default_transport_speaks_the_standard_library_and_never_redirects() -> None:
    seen: dict[str, Any] = {}

    class Raw:
        status = 200

        def __init__(self) -> None:
            self.closed = False

        def __iter__(self) -> Iterator[bytes]:
            return iter([b'{"ok": true}'])

        def close(self) -> None:
            self.closed = True

    class Opener:
        def __init__(self, error: BaseException | None = None) -> None:
            self.error = error

        def open(self, prepared: Any, timeout: float) -> Raw:
            seen["url"] = prepared.full_url
            seen["method"] = prepared.get_method()
            seen["body"] = prepared.data
            seen["headers"] = prepared.headers
            seen["timeout"] = timeout
            if self.error is not None:
                raise self.error
            return Raw()

    transport = UrllibTransport()
    transport.opener = Opener()  # type: ignore[assignment]
    reply = transport.send(
        "https://gateway.invalid/api/chat/completions",
        b'{"model": "m"}',
        {"Authorization": "Bearer t"},
        12.5,
    )
    assert reply.status == 200 and b"".join(reply.chunks()) == b'{"ok": true}'
    reply.close()
    assert seen["method"] == "POST" and seen["timeout"] == 12.5
    assert seen["body"] == b'{"model": "m"}'
    assert seen["headers"]["Authorization"] == "Bearer t"

    # A status is an answer: the transport reports it instead of raising.
    refusing = UrllibTransport()
    refusing.opener = Opener(  # type: ignore[assignment]
        urllib.error.HTTPError(
            "https://gateway.invalid", 503, "busy", Message(), io.BytesIO(b"overloaded")
        )
    )
    refused = refusing.send("https://gateway.invalid", b"{}", {}, 1.0)
    assert refused.status == 503 and b"".join(refused.chunks()) == b"overloaded"
    refused.close()

    # A redirect is never followed: urllib would copy the Authorization header
    # to the new location and drop the POST body on the way.
    installed = getattr(UrllibTransport().opener, "handlers", [])
    assert NoRedirect in [type(handler) for handler in installed]
    assert (
        NoRedirect().redirect_request(
            urllib.request.Request("https://gateway.invalid"),
            io.BytesIO(b""),
            302,
            "found",
            Message(),
            "https://elsewhere.invalid",
        )
        is None
    )
    moved = UrllibTransport()
    moved.opener = Opener(  # type: ignore[assignment]
        urllib.error.HTTPError(
            "https://gateway.invalid", 302, "found", Message(), io.BytesIO(b"moved")
        )
    )
    relocated = moved.send("https://gateway.invalid", b"{}", {"Authorization": "Bearer t"}, 1.0)
    assert relocated.status == 302
    assert status_failure(relocated.status, b"".join(relocated.chunks())).retryable is False


def test_a_refusal_in_a_two_hundred_body_is_not_a_success() -> None:
    # A proxy that answers 200 and describes the refusal in the body.
    body = {"error": {"message": "quota exceeded", "type": "insufficient_quota"}}
    refused = OpenAICompatible(endpoint(), transport=Transport(json_reply(body))).generate(
        request()
    )
    assert refused.failure is not None
    assert refused.failure.code == "provider_error" and not refused.failure.retryable
    assert "quota exceeded" in refused.failure.message

    chunks = [
        b'data: {"choices": [{"delta": {"content": "partial"}}]}\n',
        b'data: {"error": {"message": "upstream closed"}}\n',
        b"data: [DONE]\n",
    ]
    events = list(
        OpenAICompatible(endpoint(), transport=Transport(Reply(200, chunks))).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in events] == ["text", "failed"]
    assert events[1].failure is not None
    assert events[1].failure.code == "provider_error"
    assert "upstream closed" in events[1].failure.message
