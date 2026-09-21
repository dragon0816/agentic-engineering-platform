"""Where a `SecretRef` becomes a value, and nowhere else.

AGENTS rule 17: shared assets declare symbolic secret requirements, and
resolution belongs to the execution environment. A `ModelEndpoint` therefore
names its credential and never holds it; a host supplies a `CredentialResolver`
and the adapters ask it once per request, so a token that is rewritten on a
schedule is never captured at construction.

Nothing here is a `Contract`. A contract is serializable, validated and
loggable, which is everything a secret value must not be. Nothing here reads
an environment variable on its own either: `EnvironmentCredentials` is given
the variable names by the host, because a convention that guesses is a
convention that reads the wrong thing in silence.
"""

import os
from collections.abc import Callable, Mapping
from typing import Protocol

from common.assets import SecretRef
from models.catalog import ModelEndpoint


class CredentialResolver(Protocol):
    """The execution environment's answer to one declared secret. Raising is
    how a resolver reports failure; every adapter turns that into a typed
    `credential_unavailable` rather than letting it escape."""

    def resolve(self, ref: SecretRef) -> str: ...


class _Mapped:
    """Shared refusals, so a blank value is never mistaken for a credential."""

    def _checked(self, name: str, value: str | None, source: str) -> str:
        if value is None:
            raise LookupError(f"no {source} for the secret named {name}")
        if not value.strip():
            raise LookupError(f"the {source} for the secret named {name} is blank")
        return value


class EnvironmentCredentials(_Mapped):
    """Development-grade resolution from environment variables, with the
    mapping stated by the host: `{"company_gateway_token": "CHATRS_TOKEN"}`.
    A production deployment should use a real store instead; this exists so a
    developer does not have to write the same ten lines."""

    def __init__(self, names: Mapping[str, str], environ: Mapping[str, str] | None = None) -> None:
        self._names = dict(names)
        # Injected for tests; a host has no reason to pass anything else.
        self._environ = environ if environ is not None else os.environ

    def resolve(self, ref: SecretRef) -> str:
        variable = self._names.get(ref.name)
        if variable is None:
            raise LookupError(f"no environment variable is mapped to the secret named {ref.name}")
        return self._checked(ref.name, self._environ.get(variable), f"value in {variable}")


class StaticCredentials(_Mapped):
    """For a host that already holds its secrets, and for tests. The values
    live only in this object; it is deliberately not serializable."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    def resolve(self, ref: SecretRef) -> str:
        return self._checked(ref.name, self._values.get(ref.name), "value")


def credential_for(
    endpoint: ModelEndpoint, resolver: CredentialResolver | None
) -> Callable[[], str] | None:
    """The callable an adapter takes. It resolves on every call rather than
    once, so a rotated token is picked up without rebuilding the client."""
    declared = endpoint.credential
    if declared is None:
        return None
    if resolver is None:
        raise ValueError("this endpoint declares a credential; supply a resolver for it")
    return lambda: resolver.resolve(declared)
