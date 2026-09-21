"""Credentials and client construction: a secret is resolved where the host
says and nowhere else, and every way of failing to build a client is typed."""

import json
from typing import Any

import pytest
from test_openai_compatible import Reply, Transport

from common.assets import SecretRef
from common.execution import Failure, TraceIdentifiers
from models.catalog import ModelCapabilities, ModelCatalog, ModelEndpoint, ModelRoute
from models.clients import ModelClients
from models.contracts import ModelMessage, ModelRequest, ModelRequirements
from models.credentials import (
    EnvironmentCredentials,
    StaticCredentials,
    credential_for,
)
from models.ollama import Ollama
from models.openai_compatible import OpenAICompatible

TRACE = TraceIdentifiers(trace_id="t-1", request_id="r-1", span_id="s-1")
TOKEN = SecretRef(name="company_gateway_token")


def capabilities(**declared: Any) -> ModelCapabilities:
    return ModelCapabilities.model_validate({"max_context_tokens": 128_000, **declared})


def company(**changes: Any) -> ModelEndpoint:
    return ModelEndpoint.model_validate(
        {
            "alias": "company_reasoning",
            "provider": "openai_compatible",
            "model": "gpt-5.5",
            "base_url": "https://gateway.invalid/api",
            "credential": TOKEN,
            "capabilities": capabilities(reasoning="high", vision=True),
            **changes,
        }
    )


def local(**changes: Any) -> ModelEndpoint:
    return ModelEndpoint.model_validate(
        {
            "alias": "local_small",
            "provider": "ollama",
            "model": "qwen3:8b",
            "base_url": "http://localhost:11434",
            "capabilities": capabilities(reasoning="low", local=True, max_context_tokens=32_000),
            **changes,
        }
    )


def catalog(*endpoints: ModelEndpoint) -> ModelCatalog:
    chosen = endpoints or (local(), company())
    routes = tuple(
        ModelRoute(name="default", alias="company_reasoning")
        for item in chosen
        if item.alias == "company_reasoning"
    )
    return ModelCatalog(endpoints=chosen, routes=routes)


def test_a_secret_is_resolved_where_the_host_says_and_nowhere_else() -> None:
    resolver = EnvironmentCredentials(
        {"company_gateway_token": "CHATRS_TOKEN"}, environ={"CHATRS_TOKEN": "a-live-token"}
    )
    assert resolver.resolve(TOKEN) == "a-live-token"

    # No convention and no default: a secret nobody mapped is not guessed at.
    with pytest.raises(LookupError, match="no environment variable is mapped"):
        resolver.resolve(SecretRef(name="other_token"))
    absent = EnvironmentCredentials({"company_gateway_token": "MISSING"}, environ={})
    with pytest.raises(LookupError, match="no value in MISSING"):
        absent.resolve(TOKEN)
    blank = EnvironmentCredentials(
        {"company_gateway_token": "CHATRS_TOKEN"}, environ={"CHATRS_TOKEN": "   "}
    )
    with pytest.raises(LookupError, match="blank"):
        blank.resolve(TOKEN)

    held = StaticCredentials({"company_gateway_token": "held-token"})
    assert held.resolve(TOKEN) == "held-token"
    with pytest.raises(LookupError, match="no value"):
        held.resolve(SecretRef(name="other_token"))

    # A resolver is not a contract, and neither it nor the endpoint that names
    # the secret can print its value.
    assert "held-token" not in repr(held) and "held-token" not in str(held)
    assert not hasattr(held, "model_dump")
    assert "a-live-token" not in company().model_dump_json()


def test_a_credential_is_resolved_once_per_call_not_captured() -> None:
    issued: list[str] = []

    class Rotating:
        def resolve(self, ref: SecretRef) -> str:
            issued.append(f"token-{len(issued)}")
            return issued[-1]

    resolve = credential_for(company(), Rotating())
    assert resolve is not None
    assert [resolve(), resolve()] == ["token-0", "token-1"]

    # An endpoint that declares nothing needs nothing.
    assert credential_for(local(), None) is None
    with pytest.raises(ValueError, match="supply a resolver"):
        credential_for(company(), None)


def test_the_chain_runs_from_requirements_to_an_answer() -> None:
    answer = {
        "choices": [{"message": {"content": "the answer"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4},
    }
    transport = Transport(Reply(200, [json.dumps(answer).encode("utf-8")]))
    clients = ModelClients(
        catalog(),
        resolver=StaticCredentials({"company_gateway_token": "held-token"}),
        transport=transport,
    )

    chosen = clients.for_requirements(ModelRequirements(reasoning="high", vision=True))
    assert not isinstance(chosen, Failure)
    alias, client = chosen
    assert alias == "company_reasoning" and isinstance(client, OpenAICompatible)

    response = client.generate(
        ModelRequest(
            trace=TRACE,
            model_alias=alias,
            messages=(ModelMessage(role="user", text="ask"),),
            requirements=ModelRequirements(reasoning="high", vision=True),
        )
    )
    assert response.failure is None and response.text == "the answer"
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer held-token"

    # The local endpoint is reached the same way, and gets its own adapter.
    quiet = clients.for_requirements(ModelRequirements(local_only=True, reasoning="low"))
    assert not isinstance(quiet, Failure)
    assert quiet[0] == "local_small" and isinstance(quiet[1], Ollama)

    routed = clients.for_route("default")
    assert not isinstance(routed, Failure) and routed[0] == "company_reasoning"

    # One client per alias, so a host may ask per request.
    assert clients.for_alias("company_reasoning") is client
    assert routed[1] is client


def test_every_way_of_failing_to_build_a_client_is_typed() -> None:
    clients = ModelClients(catalog(), resolver=StaticCredentials({}))

    missing = clients.for_alias("nothing")
    assert isinstance(missing, Failure) and missing.code == "unknown_alias"

    foreign = ModelClients(catalog(local(provider="bedrock")))
    unknown = foreign.for_alias("local_small")
    assert isinstance(unknown, Failure) and unknown.code == "unknown_provider"
    assert "bedrock" in unknown.message

    # A declared credential with no resolver is a configuration mistake, and
    # is reported rather than raised from the middle of a request.
    unresolved = ModelClients(catalog(company())).for_alias("company_reasoning")
    assert isinstance(unresolved, Failure)
    assert unresolved.code == "endpoint_misconfigured" and "resolver" in unresolved.message

    addressless = ModelClients(catalog(local(base_url=None))).for_alias("local_small")
    assert isinstance(addressless, Failure)
    assert addressless.code == "endpoint_misconfigured" and "base url" in addressless.message

    # The catalog's own refusals travel unchanged.
    impossible = clients.for_requirements(ModelRequirements(reasoning="high", local_only=True))
    assert isinstance(impossible, Failure) and impossible.code == "no_model_for_requirements"
    absent = clients.for_route("coding")
    assert isinstance(absent, Failure) and absent.code == "unknown_route"


def test_a_resolver_that_fails_reaches_the_caller_as_a_status() -> None:
    class Unavailable:
        def resolve(self, ref: SecretRef) -> str:
            raise LookupError("the token file is being rewritten")

    transport = Transport(Reply(200, [b"{}"]))
    clients = ModelClients(catalog(company()), resolver=Unavailable(), transport=transport)
    built = clients.for_alias("company_reasoning")
    assert not isinstance(built, Failure)  # construction is fine; resolution is per call

    response = built.generate(
        ModelRequest(
            trace=TRACE,
            model_alias="company_reasoning",
            messages=(ModelMessage(role="user", text="ask"),),
        )
    )
    assert response.failure is not None
    assert response.failure.code == "credential_unavailable" and response.failure.retryable
    assert "rewritten" in response.failure.message
    assert transport.calls == []  # the endpoint was never contacted


def test_a_host_may_register_its_own_provider() -> None:
    built: list[ModelEndpoint] = []

    class Echo:
        def __init__(self, endpoint: ModelEndpoint, **_: Any) -> None:
            built.append(endpoint)

        def generate(self, request: ModelRequest) -> Any: ...

        def stream(self, request: ModelRequest) -> Any: ...

    clients = ModelClients(catalog(local(provider="echo")), providers={"echo": Echo})
    client = clients.for_alias("local_small")
    assert isinstance(client, Echo) and [item.alias for item in built] == ["local_small"]
    # Registering a provider replaces the defaults rather than adding to them.
    replaced = ModelClients(catalog(company()), providers={"echo": Echo})
    assert isinstance(replaced.for_alias("company_reasoning"), Failure)
