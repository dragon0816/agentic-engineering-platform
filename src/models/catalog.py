"""The alias layer: which configured model can serve a declared requirement.

Callers name a stable alias, never a provider or a model id, so changing
either is configuration rather than a code change (Architecture, "Provider
adapters / model gateway"). An endpoint declares the capabilities it actually
has, so a requirement is *checked* against it instead of trusted: the source
tooling aliased models at a proxy that could not reason about capabilities at
all (`docs/PHASE_5_MIGRATION.md`).

Selection is deterministic and calls nothing: no model chooses a model, no
file is read and no socket is opened. A requirement nothing can serve is a
typed `Failure` naming the fields that blocked it, not a provider error at the
first request. A credential appears here only as a `SecretRef`; the value is
resolved by the execution environment and never enters a contract.
"""

from typing import Literal, Self

from pydantic import Field, StrictBool, model_validator

from common.assets import SecretRef
from common.base import Contract, Symbol, Text
from common.execution import Failure
from models.contracts import ModelRequirements

Reasoning = Literal["low", "medium", "high"]
_REASONING_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
# One canonical order for reporting, so the same miss always reads the same.
_FLAGS = ("tool_calling", "structured_output", "streaming", "vision")
_SCHEMES = ("http://", "https://")


class ModelCapabilities(Contract):
    """What one endpoint can do. The mirror of `ModelRequirements`, with two
    deliberate differences: `local` states where the model runs (a request
    asks for `local_only`), and `max_context_tokens` is a ceiling against the
    request's floor."""

    reasoning: Reasoning = "medium"
    tool_calling: StrictBool = False
    structured_output: StrictBool = False
    streaming: StrictBool = False
    vision: StrictBool = False
    local: StrictBool = False
    max_context_tokens: int = Field(default=1, ge=1, strict=True)

    def unmet(self, requirements: ModelRequirements) -> tuple[str, ...]:
        """Every requirement field this endpoint cannot meet, in field order."""
        missing: list[str] = []
        if _REASONING_ORDER[self.reasoning] < _REASONING_ORDER[requirements.reasoning]:
            missing.append("reasoning")
        missing.extend(
            flag for flag in _FLAGS if getattr(requirements, flag) and not getattr(self, flag)
        )
        if requirements.local_only and not self.local:
            missing.append("local_only")
        if self.max_context_tokens < requirements.min_context_tokens:
            missing.append("min_context_tokens")
        return tuple(missing)

    def satisfies(self, requirements: ModelRequirements) -> bool:
        return not self.unmet(requirements)


class ModelEndpoint(Contract):
    """One configured model behind a stable alias. Serializable, and holding
    no secret: `credential` names a requirement the environment resolves."""

    alias: Symbol
    provider: Symbol
    model: Text
    base_url: Text | None = None
    credential: SecretRef | None = None
    capabilities: ModelCapabilities = ModelCapabilities()

    @model_validator(mode="after")
    def addressable(self) -> Self:
        if self.base_url is not None:
            if not self.base_url.startswith(_SCHEMES):
                raise ValueError("a base url is http or https")
            if any(character.isspace() for character in self.base_url):
                raise ValueError("a base url has no whitespace")
        return self


class ModelRoute(Contract):
    """A purpose, such as `default` or `knowledge`, bound to one alias."""

    name: Symbol
    alias: Symbol


class ModelCatalog(Contract):
    """The configured endpoints and the routes that name them. Implements
    `ModelSelector`. Order is meaningful: it breaks ties in selection."""

    endpoints: tuple[ModelEndpoint, ...] = Field(min_length=1)
    routes: tuple[ModelRoute, ...] = ()

    @model_validator(mode="after")
    def names_resolve(self) -> Self:
        aliases = [item.alias for item in self.endpoints]
        if len(set(aliases)) != len(aliases):
            raise ValueError("an alias names one endpoint")
        names = [route.name for route in self.routes]
        if len(set(names)) != len(names):
            raise ValueError("a route name is unique")
        known = set(aliases)
        for route in self.routes:
            if route.alias not in known:
                raise ValueError(f"route {route.name} names an unknown alias")
        return self

    def endpoint(self, alias: str) -> ModelEndpoint | None:
        return next((item for item in self.endpoints if item.alias == alias), None)

    def select(self, requirements: ModelRequirements) -> Symbol | Failure:
        """The first endpoint in catalog order that satisfies the
        requirements, or a `Failure` naming what nothing could meet."""
        blocking: list[str] = []
        for item in self.endpoints:
            unmet = item.capabilities.unmet(requirements)
            if not unmet:
                return item.alias
            blocking.extend(field for field in unmet if field not in blocking)
        return Failure(
            code="no_model_for_requirements",
            message=(f"no endpoint of {len(self.endpoints)} satisfies: {', '.join(blocking)}"),
        )

    def select_route(self, name: str) -> Symbol | Failure:
        route = next((item for item in self.routes if item.name == name), None)
        if route is None:
            return Failure(code="unknown_route", message=f"no route named {name}")
        return route.alias
