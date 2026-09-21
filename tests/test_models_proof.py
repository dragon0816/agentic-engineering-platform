"""The worked example, and the latency every answer now carries."""

import json
from typing import Any

import pytest
from test_openai_compatible import Reply, Transport

from common.assets import SECRET_PATTERN
from common.execution import Failure, TraceIdentifiers
from models import wire
from models.catalog import ModelCapabilities, ModelCatalog, ModelEndpoint
from models.contracts import ModelMessage, ModelRequest, ModelRequirements
from models.credentials import StaticCredentials
from models.ollama import Ollama
from models.openai_compatible import OpenAICompatible
from models.proof import SAMPLE_CATALOG, ask, clients_from

TRACE = TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1")


def openai_reply() -> Reply:
    body = {
        "choices": [{"message": {"content": "the answer"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
    }
    return Reply(200, [json.dumps(body).encode("utf-8")])


def test_the_sample_catalog_is_valid_and_carries_no_secret() -> None:
    catalog = ModelCatalog.model_validate(SAMPLE_CATALOG)
    assert [item.alias for item in catalog.endpoints] == ["local_small", "company_reasoning"]
    # A credential is named, never held, so the whole catalog is safe to commit.
    company = catalog.endpoint("company_reasoning")
    assert company is not None and company.credential is not None
    assert company.credential.name == "company_gateway_token"
    # The guard the platform applies to every registry asset finds nothing,
    # so the whole catalog is safe to commit.
    assert SECRET_PATTERN.search(json.dumps(SAMPLE_CATALOG)) is None


def test_the_worked_example_runs_end_to_end_without_a_socket() -> None:
    transport = Transport(openai_reply())
    clients = clients_from(
        SAMPLE_CATALOG,
        resolver=StaticCredentials({"company_gateway_token": "held-token"}),
        transport=transport,
    )

    # What the work needs decides where it goes; no caller names a provider.
    answered = ask(
        clients,
        requirements=ModelRequirements(reasoning="high", vision=True),
        prompt="summarise the release notes",
        trace=TRACE,
    )
    assert not isinstance(answered, Failure)
    assert answered.text == "the answer" and answered.model_alias == "company_reasoning"
    assert answered.input_tokens == 3 and answered.output_tokens == 4
    assert transport.calls[0]["url"].startswith("https://gateway.example.invalid/api")
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer held-token"

    # A cheaper requirement reaches the local endpoint, through the same call.
    local_transport = Transport(
        Reply(200, [b'{"message": {"content": "local answer"}, "done": true}'])
    )
    local_clients = clients_from(SAMPLE_CATALOG, transport=local_transport)
    quiet = ask(
        local_clients,
        requirements=ModelRequirements(reasoning="low", local_only=True),
        prompt="tidy this sentence",
        trace=TRACE,
    )
    assert not isinstance(quiet, Failure)
    assert quiet.model_alias == "local_small" and quiet.text == "local answer"
    assert local_transport.calls[0]["url"] == "http://localhost:11434/api/chat"

    # A requirement nothing satisfies is a routing failure, not an exception.
    impossible = ask(
        local_clients,
        requirements=ModelRequirements(reasoning="high", local_only=True),
        prompt="anything",
        trace=TRACE,
    )
    assert isinstance(impossible, Failure) and impossible.code == "no_model_for_requirements"


def test_the_example_needs_a_resolver_only_where_a_secret_is_declared() -> None:
    # The local endpoint declares none, so no resolver is needed to reach it.
    clients = clients_from(SAMPLE_CATALOG)
    assert not isinstance(clients.for_alias("local_small"), Failure)
    # The company one does, and says so rather than calling out anonymously.
    unresolved = clients.for_alias("company_reasoning")
    assert isinstance(unresolved, Failure) and unresolved.code == "endpoint_misconfigured"


@pytest.mark.parametrize("provider", ["openai_compatible", "ollama"])
def test_every_answer_reports_how_long_the_provider_took(
    provider: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ticks = iter([10.0, 10.25, 30.0, 30.5])
    monkeypatch.setattr(wire, "monotonic", lambda: next(ticks))

    endpoint = ModelEndpoint.model_validate(
        {
            "alias": "alias",
            "provider": provider,
            "model": "m",
            "base_url": "http://host.invalid",
            "capabilities": ModelCapabilities(max_context_tokens=1_000, streaming=True),
        }
    )
    reply = (
        openai_reply()
        if provider == "openai_compatible"
        else Reply(200, [b'{"message": {"content": "the answer"}, "done": true}'])
    )
    build: Any = OpenAICompatible if provider == "openai_compatible" else Ollama
    request = ModelRequest(
        trace=TRACE, model_alias="alias", messages=(ModelMessage(role="user", text="ask"),)
    )

    answered = build(endpoint, transport=Transport(reply)).generate(request)
    assert answered.failure is None and answered.duration_ms == 250

    # A failed call is timed too, so a slow refusal is visible.
    refused = build(endpoint, transport=Transport(Reply(503, [b"busy"]))).generate(request)
    assert refused.failure is not None and refused.duration_ms == 500


def test_a_stream_reports_its_duration_on_the_event_that_ends_it() -> None:
    endpoint = ModelEndpoint.model_validate(
        {
            "alias": "alias",
            "provider": "openai_compatible",
            "model": "m",
            "base_url": "http://host.invalid",
            "capabilities": ModelCapabilities(max_context_tokens=1_000, streaming=True),
        }
    )
    chunks = [b'data: {"choices": [{"delta": {"content": "hi"}}]}\n', b"data: [DONE]\n"]
    events = list(
        OpenAICompatible(endpoint, transport=Transport(Reply(200, chunks))).stream(
            ModelRequest(
                trace=TRACE,
                model_alias="alias",
                messages=(ModelMessage(role="user", text="ask"),),
                requirements=ModelRequirements(streaming=True),
            )
        )
    )
    assert [event.kind for event in events] == ["text", "done"]
    # Only the terminal event carries it; the deltas are not each timed.
    assert events[0].duration_ms == 0 and events[1].duration_ms >= 0

    # A request refused before any call reports nothing rather than a
    # misleading number.
    undeclared = list(
        OpenAICompatible(endpoint, transport=Transport(Reply(200, []))).stream(
            ModelRequest(
                trace=TRACE,
                model_alias="alias",
                messages=(ModelMessage(role="user", text="ask"),),
            )
        )
    )
    assert undeclared[0].kind == "failed" and undeclared[0].duration_ms == 0
