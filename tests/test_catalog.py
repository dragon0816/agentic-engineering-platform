"""Model catalog: an alias declares what its endpoint can actually do,
selection is deterministic and typed, and no contract can carry a secret."""

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


def endpoint(alias: str, **capabilities: object) -> ModelEndpoint:
    return ModelEndpoint(
        alias=alias,
        provider="openai_compatible",
        model="upstream-id",
        capabilities=ModelCapabilities.model_validate(capabilities),
    )


def test_capabilities_are_checked_field_by_field() -> None:
    assert EVERYTHING.satisfies(ModelRequirements())
    assert EVERYTHING.unmet(ModelRequirements(reasoning="high", vision=True)) == ()

    # Reasoning is ordered, not equal: a stronger endpoint still qualifies.
    medium = ModelCapabilities(reasoning="medium")
    assert medium.satisfies(ModelRequirements(reasoning="low"))
    assert medium.satisfies(ModelRequirements(reasoning="medium"))
    assert medium.unmet(ModelRequirements(reasoning="high")) == ("reasoning",)

    # Each flag is an implication: declaring more than asked is fine.
    for flag in ("tool_calling", "structured_output", "streaming", "vision"):
        assert ModelCapabilities().unmet(ModelRequirements.model_validate({flag: True})) == (flag,)
        assert EVERYTHING.satisfies(ModelRequirements.model_validate({flag: True}))

    # local_only is inverted: the request demands locality, the endpoint has it.
    remote = ModelCapabilities(local=False)
    assert remote.satisfies(ModelRequirements(local_only=False))
    assert remote.unmet(ModelRequirements(local_only=True)) == ("local_only",)
    assert ModelCapabilities(local=True).satisfies(ModelRequirements(local_only=True))

    small = ModelCapabilities(max_context_tokens=8_000)
    assert small.satisfies(ModelRequirements(min_context_tokens=8_000))
    assert small.unmet(ModelRequirements(min_context_tokens=8_001)) == ("min_context_tokens",)

    # Every unmet field is named, in one canonical order.
    assert ModelCapabilities(reasoning="low").unmet(
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

    missed = catalog.select(ModelRequirements(reasoning="high", local_only=True))
    assert isinstance(missed, Failure)
    assert missed.code == "no_model_for_requirements" and not missed.retryable
    assert "reasoning" in missed.message and "local_only" in missed.message
    assert "3" in missed.message  # how many endpoints were considered

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

    # An endpoint is addressable or has no address at all.
    for bad in ("ftp://host", "host:4000", "http://ho st"):
        with pytest.raises(ValidationError, match="base url"):
            ModelEndpoint(alias="a", provider="p", model="m", base_url=bad)
    fine = ModelEndpoint(
        alias="a",
        provider="openai_compatible",
        model="gpt-5.5",
        base_url="https://example.invalid/api",
        credential=SecretRef(name="company_gateway_token"),
    )
    assert fine.base_url == "https://example.invalid/api"
    assert fine.capabilities == ModelCapabilities()

    # A secret value cannot be passed where a reference belongs.
    with pytest.raises(ValidationError):
        ModelEndpoint(alias="a", provider="p", model="m", credential="a-real-looking-token")

    catalog = ModelCatalog(endpoints=(fine,), routes=(ModelRoute(name="default", alias="a"),))
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
                        "capabilities": {"local": True, "tool_calling": True},
                    }
                ]
            }
        ).select(ModelRequirements(local_only=True, tool_calling=True))
        == "local"
    )
