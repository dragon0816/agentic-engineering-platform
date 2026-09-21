"""From a declared requirement to something that can answer it.

This is the last link in the chain the architecture describes: a caller states
`ModelRequirements`, the catalog picks the alias whose endpoint satisfies them,
and this builds the adapter for that endpoint's provider. A caller never names
a provider, a model id or a URL, so changing any of them stays configuration.

A host may register its own provider without changing core runtime code, which
is the contribution rule applied to the model layer.
"""

from collections.abc import Callable, Mapping
from typing import Protocol

from common.base import Symbol
from common.execution import Failure
from models import wire
from models.catalog import ModelCatalog, ModelEndpoint
from models.contracts import ModelClient, ModelRequirements
from models.credentials import CredentialResolver, credential_for
from models.ollama import Ollama
from models.openai_compatible import OpenAICompatible


class ClientBuilder(Protocol):
    """What a provider registration is: something that turns one endpoint into
    a client. Both built-in adapters are their own builders."""

    def __call__(
        self,
        endpoint: ModelEndpoint,
        *,
        credential: Callable[[], str] | None,
        transport: wire.Transport | None,
        timeout_s: float,
    ) -> ModelClient: ...


DEFAULT_PROVIDERS: Mapping[str, ClientBuilder] = {
    "openai_compatible": OpenAICompatible,
    "ollama": Ollama,
}


class ModelClients:
    """Builds and keeps one client per alias. Every way of failing is a typed
    `Failure`, so a misconfigured catalog reads like an unavailable model
    rather than an exception from the middle of a request."""

    def __init__(
        self,
        catalog: ModelCatalog,
        *,
        resolver: CredentialResolver | None = None,
        transport: wire.Transport | None = None,
        timeout_s: float = 600.0,
        providers: Mapping[str, ClientBuilder] | None = None,
    ) -> None:
        self.catalog = catalog
        self.resolver = resolver
        self.transport = transport
        self.timeout_s = timeout_s
        self.providers = dict(DEFAULT_PROVIDERS if providers is None else providers)
        self._built: dict[str, ModelClient] = {}

    def for_alias(self, alias: str) -> ModelClient | Failure:
        known = self._built.get(alias)
        if known is not None:
            return known
        endpoint = self.catalog.endpoint(alias)
        if endpoint is None:
            return Failure(code="unknown_alias", message=f"no endpoint is named {alias}")
        builder = self.providers.get(endpoint.provider)
        if builder is None:
            return Failure(
                code="unknown_provider",
                message=f"no builder is registered for the provider {endpoint.provider}",
            )
        try:
            client = builder(
                endpoint,
                credential=credential_for(endpoint, self.resolver),
                transport=self.transport,
                timeout_s=self.timeout_s,
            )
        except ValueError as error:
            # The construction-time refusals: no base url, a non-positive
            # timeout, a declared credential with nothing to resolve it.
            return Failure(code="endpoint_misconfigured", message=f"{alias}: {error}")
        self._built[alias] = client
        return client

    def for_route(self, name: str) -> tuple[Symbol, ModelClient] | Failure:
        alias = self.catalog.select_route(name)
        if isinstance(alias, Failure):
            return alias
        return self._paired(alias)

    def for_requirements(
        self, requirements: ModelRequirements
    ) -> tuple[Symbol, ModelClient] | Failure:
        """The whole chain: what the caller needs, the alias that satisfies it,
        and the client that speaks to it."""
        alias = self.catalog.select(requirements)
        if isinstance(alias, Failure):
            return alias
        return self._paired(alias)

    def _paired(self, alias: Symbol) -> tuple[Symbol, ModelClient] | Failure:
        client = self.for_alias(alias)
        return client if isinstance(client, Failure) else (alias, client)
