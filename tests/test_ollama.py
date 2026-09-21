"""The Ollama adapter: a second wire format behind the same contract, with
the rules that must not differ between providers coming from `models.wire`."""

import json
from typing import Any

import pytest
from test_openai_compatible import Reply, Transport

from common.assets import SecretRef
from common.execution import TraceIdentifiers
from models.catalog import ModelCapabilities, ModelEndpoint
from models.contracts import (
    ModelClient,
    ModelMessage,
    ModelRequest,
    ModelRequirements,
    ModelTool,
)
from models.ollama import Ollama

TRACE = TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1")
ANSWER: dict[str, Any] = {
    "model": "qwen3:8b",
    "created_at": "2026-09-22T00:00:00Z",
    "message": {"role": "assistant", "content": "the answer"},
    "done": True,
    "prompt_eval_count": 11,
    "eval_count": 7,
}


def json_reply(body: dict[str, Any], status: int = 200) -> Reply:
    return Reply(status, [json.dumps(body).encode("utf-8")])


def endpoint(**changes: Any) -> ModelEndpoint:
    return ModelEndpoint.model_validate(
        {
            "alias": "local_small",
            "provider": "ollama",
            "model": "qwen3:8b",
            "base_url": "http://localhost:11434",
            "capabilities": ModelCapabilities(
                max_context_tokens=32_000,
                streaming=True,
                vision=True,
                structured_output=True,
                local=True,
            ),
            **changes,
        }
    )


def request(**changes: Any) -> ModelRequest:
    return ModelRequest.model_validate(
        {
            "trace": TRACE,
            "model_alias": "local_small",
            "messages": (ModelMessage(role="user", text="ask"),),
            "max_output_tokens": 256,
            **changes,
        }
    )


def test_a_generate_call_speaks_ollamas_own_wire() -> None:
    transport = Transport(json_reply(ANSWER))
    client: ModelClient = Ollama(endpoint(), transport=transport, timeout_s=45)
    response = client.generate(request())

    (call,) = transport.calls
    assert call["url"] == "http://localhost:11434/api/chat"
    assert call["timeout_s"] == 45
    assert call["payload"] == {
        "model": "qwen3:8b",
        "messages": [{"role": "user", "content": "ask"}],
        # Ollama streams by default, so a single answer has to say otherwise.
        "stream": False,
        "options": {"num_predict": 256},
    }
    assert "Authorization" not in call["headers"]

    assert response.failure is None and response.text == "the answer"
    # Ollama counts under its own names.
    assert response.input_tokens == 11 and response.output_tokens == 7
    assert response.model_alias == "local_small" and response.trace == TRACE
    assert transport.reply is not None and transport.reply.closed


def test_images_travel_as_bare_base64_and_a_reference_is_refused() -> None:
    transport = Transport(json_reply(ANSWER))
    Ollama(endpoint(), transport=transport).generate(
        request(
            messages=(
                ModelMessage(role="user", text="describe", images=("data:image/png;base64,AAAB",)),
            ),
            requirements=ModelRequirements(vision=True),
        )
    )
    # The data: prefix is Phase 4's encoding, not Ollama's.
    assert transport.calls[0]["payload"]["messages"] == [
        {"role": "user", "content": "describe", "images": ["AAAB"]}
    ]

    fetched = Transport(json_reply(ANSWER))
    refused = Ollama(endpoint(), transport=fetched).generate(
        request(
            messages=(
                ModelMessage(role="user", text="describe", images=("https://pics/one.png",)),
            ),
            requirements=ModelRequirements(vision=True),
        )
    )
    assert refused.failure is not None
    assert refused.failure.code == "image_not_inline" and not refused.failure.retryable
    assert fetched.calls == []  # refused before anything was sent


def test_a_declared_output_contract_asks_ollama_for_json() -> None:
    transport = Transport(json_reply({**ANSWER, "message": {"content": '{"kind": "workflow"}'}}))
    response = Ollama(endpoint(), transport=transport).generate(
        request(
            requirements=ModelRequirements(structured_output=True),
            output_contract="platform.route-proposal.v1",
        )
    )
    payload = transport.calls[0]["payload"]
    assert payload["format"] == "json"
    assert "platform.route-proposal.v1" not in json.dumps(payload)
    assert response.structured_output == {"kind": "workflow"}

    prose = Transport(json_reply({**ANSWER, "message": {"content": "not json at all"}}))
    loose = Ollama(endpoint(), transport=prose).generate(
        request(
            requirements=ModelRequirements(structured_output=True),
            output_contract="platform.route-proposal.v1",
        )
    )
    assert loose.structured_output is None and loose.text == "not json at all"
    assert loose.failure is None


def test_streaming_is_newline_delimited_json_and_always_ends() -> None:
    chunks = [
        b'{"message": {"content": "the "}, "done": false}\n',
        b"\n",
        b'{"message": {"con',
        b'tent": "answer"}, "done": false}\n',
        b'{"message": {"content": ""}, "done": true, "eval_count": 7}\n',
        b'{"message": {"content": "never read"}, "done": false}\n',
    ]
    transport = Transport(Reply(200, chunks))
    events = list(
        Ollama(endpoint(), transport=transport).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in events] == ["text", "text", "done"]
    assert [event.text for event in events[:2]] == ["the ", "answer"]
    assert all(event.trace == TRACE for event in events)
    assert transport.calls[0]["payload"]["stream"] is True
    assert transport.reply is not None and transport.reply.closed

    # A stream that stops without a done flag still ends.
    cut = Transport(Reply(200, [b'{"message": {"content": "x"}, "done": false}\n']))
    ended = list(
        Ollama(endpoint(), transport=cut).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in ended] == ["text", "done"]


def test_a_server_that_is_not_ollama_is_a_typed_status() -> None:
    for chunks in ([b"<html>proxy</html>"], [b'{"done": true}'], [b'"just a string"']):
        response = Ollama(endpoint(), transport=Transport(Reply(200, chunks))).generate(request())
        assert response.failure is not None
        assert response.failure.code == "model_unparseable"

    streamed = list(
        Ollama(endpoint(), transport=Transport(Reply(200, [b"<html>proxy</html>"]))).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in streamed] == ["failed"]
    assert streamed[0].failure is not None
    assert streamed[0].failure.code == "model_unparseable"

    refused = Ollama(endpoint(), transport=Transport(Reply(404, [b"no such model"]))).generate(
        request()
    )
    assert refused.failure is not None
    assert refused.failure.code == "model_http_error" and not refused.failure.retryable

    unreachable = Ollama(
        endpoint(), transport=Transport(error=ConnectionRefusedError("ollama is not running"))
    ).generate(request())
    assert unreachable.failure is not None
    assert unreachable.failure.code == "model_unreachable" and unreachable.failure.retryable


def test_the_rules_that_must_not_differ_between_providers_hold_here() -> None:
    # Tools, in both shapes a request can carry them.
    tooled = Transport(json_reply(ANSWER))
    response = Ollama(endpoint(), transport=tooled).generate(
        request(
            requirements=ModelRequirements(tool_calling=True),
            tools=(ModelTool(name="read_file", description="read", input_contract="fs.read.v1"),),
        )
    )
    assert response.failure is not None and response.failure.code == "tools_not_supported"
    assert tooled.calls == []

    # Streaming that was never declared.
    undeclared = Transport(Reply(200, []))
    events = list(Ollama(endpoint(), transport=undeclared).stream(request()))
    assert [event.kind for event in events] == ["failed"]
    assert events[0].failure is not None
    assert events[0].failure.code == "streaming_not_declared"
    assert undeclared.calls == []

    # A credential, when a proxy in front of Ollama wants one.
    issued: list[str] = []

    def credential() -> str:
        issued.append(f"token-{len(issued)}")
        return issued[-1]

    guarded = endpoint(credential=SecretRef(name="ollama_proxy_token"))
    transport = Transport(json_reply(ANSWER))
    client = Ollama(guarded, credential=credential, transport=transport)
    client.generate(request())
    client.generate(request())
    assert [call["headers"]["Authorization"] for call in transport.calls] == [
        "Bearer token-0",
        "Bearer token-1",
    ]

    with pytest.raises(ValueError, match="supply a resolver"):
        Ollama(guarded)

    def unavailable() -> str:
        raise OSError("the token file is being rewritten")

    never_asked = Transport(json_reply(ANSWER))
    failed = Ollama(guarded, credential=unavailable, transport=never_asked).generate(request())
    assert failed.failure is not None
    assert failed.failure.code == "credential_unavailable" and failed.failure.retryable
    assert never_asked.calls == []

    with pytest.raises(ValueError, match="base url"):
        Ollama(endpoint(base_url=None))
    with pytest.raises(ValueError, match="timeout"):
        Ollama(endpoint(), timeout_s=0)
    assert Ollama(endpoint(base_url="http://localhost:11434/")).url == (
        "http://localhost:11434/api/chat"
    )


def test_a_refusal_in_a_two_hundred_body_is_not_a_success() -> None:
    # Ollama answers 200 and puts the refusal in the body.
    refused = Ollama(
        endpoint(), transport=Transport(json_reply({"error": "model 'qwen9' not found"}))
    ).generate(request())
    assert refused.failure is not None
    assert refused.failure.code == "provider_error" and not refused.failure.retryable
    assert "qwen9" in refused.failure.message

    # Mid-stream the status was sent long ago, so a failure arrives the same
    # way. What already streamed is kept; the stream then fails rather than
    # ending as an empty success.
    chunks = [
        b'{"message": {"content": "partial"}, "done": false}\n',
        b'{"error": "runtime out of memory"}\n',
        b'{"message": {"content": "never read"}, "done": true}\n',
    ]
    events = list(
        Ollama(endpoint(), transport=Transport(Reply(200, chunks))).stream(
            request(requirements=ModelRequirements(streaming=True))
        )
    )
    assert [event.kind for event in events] == ["text", "failed"]
    assert events[0].text == "partial"
    assert events[1].failure is not None
    assert events[1].failure.code == "provider_error"
    assert "out of memory" in events[1].failure.message
