"""Explicit host-installed handlers and policy, distinct from Platform Registry assets."""

from dataclasses import dataclass
from typing import Protocol

from pydantic import Field, JsonValue, TypeAdapter

from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, ExecutionDependencies, SecretRef
from common.base import Contract, Symbol, Text
from common.execution import ExecutionAuthorization, RequestContext


class CapabilityRefused(Exception):
    """A handler refusing what it was asked to do, with a code of its own.

    The dispatcher puts that code on the failure, so a caller learns *why*
    without the handler's message travelling: a message may quote the input
    or the data it reached, and neither may leave the Bridge. Use it for a
    refusal a person can act on; anything else is a `handler_error`.
    """

    def __init__(self, code: str) -> None:
        self.code: str = TypeAdapter(Symbol).validate_python(code)
        super().__init__(self.code)


class TransientCapabilityError(Exception):
    """Trusted handlers may flag a transient failure; exception text is never exposed.

    This is retryable only for installed read capabilities. It does not assert
    idempotency or authorize any additional execution.
    """


class CapabilityInvocation(Contract):
    context: RequestContext
    target: AssetIdentity
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class CapabilityHandler(Protocol):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract: ...


@dataclass(frozen=True)
class InstalledCapability:
    spec: CapabilitySpec
    handler: CapabilityHandler
    input_model: type[Contract]
    output_model: type[Contract]
    dependencies: ExecutionDependencies
    secrets: tuple[SecretRef, ...]


class InstalledCapabilities:
    """Execution-plane installation only; never discovers/imports executable modules."""

    def __init__(self) -> None:
        self._bindings: dict[tuple[str, str, str], InstalledCapability] = {}

    def register(
        self,
        spec: CapabilitySpec,
        handler: CapabilityHandler,
        input_model: type[Contract],
        output_model: type[Contract],
        dependencies: ExecutionDependencies,
        secrets: tuple[SecretRef, ...] = (),
    ) -> None:
        checked = CapabilitySpec.model_validate(spec)
        if checked.identity.key in self._bindings:
            raise ValueError("capability version already installed")
        if not issubclass(input_model, Contract) or not issubclass(output_model, Contract):
            raise ValueError("handlers require closed platform input and output contracts")
        self._bindings[checked.identity.key] = InstalledCapability(
            checked,
            handler,
            input_model,
            output_model,
            ExecutionDependencies.model_validate(dependencies),
            tuple(SecretRef.model_validate(secret) for secret in secrets),
        )

    def get(self, identity: AssetIdentity) -> InstalledCapability | None:
        return self._bindings.get(identity.key)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(binding.spec.name for binding in self._bindings.values())

    def discover(self) -> tuple[CapabilitySpec, ...]:
        return tuple(self._bindings[key].spec for key in sorted(self._bindings))


class CapabilityGrant(Contract):
    """Trusted host configuration, never accepted from model/tool arguments or assets."""

    actor: Symbol
    asset: AssetIdentity
    permissions: tuple[Symbol, ...] = ()
    policy_refs: tuple[Text, ...] = Field(min_length=1)
    approval_ref: Text | None = None


class LocalPolicy:
    """Small default-deny policy for a trusted local host, not an identity/RBAC server."""

    def __init__(self, grants: tuple[CapabilityGrant, ...] = ()) -> None:
        self._grants: dict[tuple[str, tuple[str, str, str]], CapabilityGrant] = {}
        for grant in grants:
            checked = CapabilityGrant.model_validate(grant)
            key = (checked.actor, checked.asset.key)
            if key in self._grants:
                raise ValueError("duplicate actor/asset policy grant")
            self._grants[key] = checked

    def authorize(self, context: RequestContext, spec: CapabilitySpec) -> ExecutionAuthorization:
        grant = self._grants.get((context.actor, spec.identity.key))
        if grant is None:
            return ExecutionAuthorization()
        if not set(spec.policy.required_permissions).issubset(grant.permissions):
            return ExecutionAuthorization()
        if not set(spec.policy.policy_refs).issubset(grant.policy_refs):
            return ExecutionAuthorization()
        if spec.policy.approval_required and grant.approval_ref is None:
            return ExecutionAuthorization()
        return ExecutionAuthorization(
            allowed=True,
            actor=context.actor,
            asset=spec.identity,
            trace=context.trace,
            policy_ref=grant.policy_refs[0],
        )
