"""Model catalog: an alias declares what its endpoint can actually do,
selection is deterministic and typed, and no contract can carry a secret."""

from typing import Any

import pytest
from pydantic import ValidationError

from common.assets import SecretRef
from common.execution import Failure
from models.catalog import ModelCapabilities, ModelCatalog, ModelEndpoint, ModelRoute
from models.contracts import ModelRequirements, ModelSelector

EVERYTHING = ModelCapabilities(
    reasoning="high",
    tool_calling=True,
    structured_output=True,
    streaming=True,
    vision=True,
    local=True,
    max_context_tokens=200_000,
)
NOTHING = ModelCapabilities(max_context_tokens=1)


def capabilities(**declared: Any) -> ModelCapabilities:
    return ModelCapabilities.model_validate({"max_context_tokens": 128_000, **declared})


def endpoint(alias: str, **declared: Any) -> ModelEndpoint:
    return ModelEndpoint(
        alias=alias,
        provider="openai_compatible",
        model="upstream-id",
        capabilities=capabilities(**declared),
    )


def test_selection_considers_every_requirement_field() -> None:
    """A field added to ModelRequirements needs a rule in `unmet`. This pins
    the mirror so a new or renamed field fails here rather than being
    silently ignored by selection, or raising from inside `select`."""
    assert set(ModelRequirements.model_fields) == {
        "reasoning",
        "tool_calling",
        "structured_output",
        "streaming",
        "vision",
        "local_only",
        "min_context_tokens",
    }
    assert EVERYTHING.unmet(ModelRequirements()) == ()
    assert set(NOTHING.unmet(ModelRequirements(**{f: True for f in ("vision", "local_only")}))) <= (
        set(ModelRequirements.model_fields)
    )


def test_capabilities_are_checked_field_by_field() -> None:
    assert EVERYTHING.satisfies(ModelRequirements())
    assert EVERYTHING.unmet(ModelRequirements(reasoning="high", vision=True)) == ()

    # Reasoning is ordered, not equal: a stronger endpoint still qualifies.
    medium = capabilities(reasoning="medium")
    assert medium.satisfies(ModelRequirements(reasoning="low"))
    assert medium.satisfies(ModelRequirements(reasoning="medium"))
    assert medium.unmet(ModelRequirements(reasoning="high")) == ("reasoning",)

    # Each flag is an implication: declaring more than asked is fine.
    for flag in ("tool_calling", "structured_output", "streaming", "vision"):
        assert capabilities().unmet(ModelRequirements.model_validate({flag: True})) == (flag,)
        assert EVERYTHING.satisfies(ModelRequirements.model_validate({flag: True}))

    # local_only is inverted: the request demands locality, the endpoint has it.
    remote = capabilities(local=False)
    assert remote.satisfies(ModelRequirements(local_only=False))
    assert remote.unmet(ModelRequirements(local_only=True)) == ("local_only",)
    assert capabilities(local=True).satisfies(ModelRequirements(local_only=True))

    # The ceiling is a ceiling, and it is required rather than guessed.
    small = capabilities(max_context_tokens=8_000)
    assert small.satisfies(ModelRequirements(min_context_tokens=8_000))
    assert small.unmet(ModelRequirements(min_context_tokens=8_001)) == ("min_context_tokens",)
    with pytest.raises(ValidationError):
        ModelCapabilities.model_validate({"reasoning": "high"})

    # Every unmet field is named, in one canonical order.
    assert capabilities(reasoning="low", max_context_tokens=8).unmet(
        ModelRequirements(
            reasoning="high", tool_calling=True, vision=True, local_only=True, min_context_tokens=9
        )
    ) == ("reasoning", "tool_calling", "vision", "local_only", "min_context_tokens")


def test_selection_is_deterministic_and_every_miss_is_typed() -> None:
    catalog = ModelCatalog(
        endpoints=(
            endpoint("local_small", reasoning="low", local=True, max_context_tokens=8_000),
            endpoint("company_reasoning", reasoning="high", tool_calling=True, vision=True),
            endpoint("company_spare", reasoning="high", tool_calling=True, vision=True),
        ),
        routes=(ModelRoute(name="default", alias="company_reasoning"),),
    )
    selector: ModelSelector = catalog  # the protocol is satisfied

    assert selector.select(ModelRequirements(reasoning="low")) == "local_small"
    # Ties break by catalog order, so the same question always picks the same alias.
    assert catalog.select(ModelRequirements(reasoning="high")) == "company_reasoning"
    assert catalog.select(ModelRequirements(reasoning="high")) == "company_reasoning"
    assert catalog.select(ModelRequirements(local_only=True, reasoning="low")) == "local_small"
    assert catalog.select(ModelRequirements(vision=True)) == "company_reasoning"
    # The context ceiling participates: the small local endpoint cannot hold it.
    assert (
        catalog.select(ModelRequirements(reasoning="low", min_context_tokens=100_000))
        == "company_reasoning"
    )

    missed = catalog.select(ModelRequirements(reasoning="high", local_only=True))
    assert isinstance(missed, Failure)
    assert missed.code == "no_model_for_requirements" and not missed.retryable
    assert "3" in missed.message  # how many endpoints were considered
    # The message describes one real candidate, not a union of every miss.
    assert "closest is local_small, lacking: reasoning" in missed.message
    assert "local_only" not in missed.message

    # The closest endpoint is the one lacking least, not merely the first.
    harder = catalog.select(ModelRequirements(reasoning="high", vision=True, local_only=True))
    assert isinstance(harder, Failure)
    assert "closest is company_reasoning, lacking: local_only" in harder.message

    assert catalog.select_route("default") == "company_reasoning"
    unknown = catalog.select_route("coding")
    assert isinstance(unknown, Failure) and unknown.code == "unknown_route"
    assert "coding" in unknown.message

    assert catalog.endpoint("local_small") is catalog.endpoints[0]
    assert catalog.endpoint("nothing") is None


def test_a_catalog_is_validated_where_it_is_built() -> None:
    one = endpoint("only", reasoning="high")
    with pytest.raises(ValidationError, match="alias names one endpoint"):
        ModelCatalog(endpoints=(one, endpoint("only")))
    with pytest.raises(ValidationError, match="route name is unique"):
        ModelCatalog(
            endpoints=(one,),
            routes=(
                ModelRoute(name="default", alias="only"),
                ModelRoute(name="default", alias="only"),
            ),
        )
    with pytest.raises(ValidationError, match="unknown alias"):
        ModelCatalog(endpoints=(one,), routes=(ModelRoute(name="default", alias="gone"),))
    with pytest.raises(ValidationError):
        ModelCatalog(endpoints=())

    catalog = ModelCatalog(endpoints=(one,), routes=(ModelRoute(name="default", alias="only"),))
    assert ModelCatalog.model_validate_json(catalog.model_dump_json()) == catalog
    # A host may keep the catalog in its own file format; plain data loads.
    assert (
        ModelCatalog.model_validate(
            {
                "endpoints": [
                    {
                        "alias": "local",
                        "provider": "ollama",
                        "model": "qwen3:8b",
                        "capabilities": {
                            "local": True,
                            "tool_calling": True,
                            "max_context_tokens": 32_000,
                        },
                    }
                ]
            }
        ).select(ModelRequirements(local_only=True, tool_calling=True))
        == "local"
    )


def test_an_endpoint_is_addressable_and_carries_no_credential() -> None:
    def built(**changes: Any) -> ModelEndpoint:
        return ModelEndpoint.model_validate(
            {
                "alias": "a",
                "provider": "openai_compatible",
                "model": "gpt-5.5",
                "capabilities": capabilities(),
                **changes,
            }
        )

    assert built(base_url="https://example.invalid/api").base_url == "https://example.invalid/api"
    # Schemes are case-insensitive; a host is required.
    assert built(base_url="HTTPS://Example.invalid/api").base_url == "HTTPS://Example.invalid/api"
    assert built().base_url is None
    for bad in ("ftp://host", "host:4000", "//host", ""):
        with pytest.raises(ValidationError):
            built(base_url=bad)
    for hostless in ("http://", "https:///api"):
        with pytest.raises(ValidationError, match="names a host"):
            built(base_url=hostless)
    with pytest.raises(ValidationError, match="whitespace"):
        built(base_url="http://ho st")

    # A credential is a reference, and cannot be smuggled in beside one.
    assert built(credential=SecretRef(name="company_gateway_token")).credential == SecretRef(
        name="company_gateway_token"
    )
    with pytest.raises(ValidationError):
        built(credential="a-real-looking-token")
    with pytest.raises(ValidationError, match="userinfo"):
        built(base_url="https://user:s3cret@host/api")
    with pytest.raises(ValidationError, match="SecretRef"):
        built(base_url="https://host/api?api_key=abcd1234")
