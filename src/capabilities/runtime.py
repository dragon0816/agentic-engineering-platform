"""Explicit host-installed handlers and policy, distinct from Platform Registry assets."""

from dataclasses import dataclass
from typing import Literal, Protocol

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

    `where` may name the place in the request that was refused, such as
    "action 7 (wait_dialog)". It must be built from the request's own
    structure (positions and fixed kinds), never from values or data.
    """

    def __init__(self, code: str, where: str | None = None) -> None:
        self.code: str = TypeAdapter(Symbol).validate_python(code)
        self.where = where
        super().__init__(self.code)


class TransientCapabilityError(Exception):
    """Trusted handlers may flag a transient failure; exception text is never exposed.

    This is retryable only for installed read capabilities. It does not assert
    idempotency or authorize any additional execution.
    """


class CapabilityExecutionFailed(Exception):
    """An invoked operation failed, with typed local diagnostic output.

    Unlike a refusal this reports execution, not policy or input rejection.
    The Bridge validates `data` against the installed output contract before
    retaining it. Exception text never travels. `where` is fixed request
    structure only (positions and action kinds), just as for CapabilityRefused.
    This does not authorize retries, even for a read capability.
    """

    def __init__(self, code: str, data: Contract, *, where: str | None = None) -> None:
        self.code: str = TypeAdapter(Symbol).validate_python(code)
        self.data = data
        self.where = where
        super().__init__(self.code)


class CapabilityInvocation(Contract):
    context: RequestContext
    target: AssetIdentity
    arguments: dict[str, JsonValue] = Field(default_factory=dict)
    # Who asked (owner 2026-10-11): a person (a button, the CLI, a Workflow they
    # installed or started) or the conversation model choosing a tool itself.
    origin: Literal["person", "model"] = "person"


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
    timeout_seconds: float | None = None


class InstalledCapabilities:
    """Execution-plane installation only; never discovers/imports executable modules."""

    def __init__(self) -> None:
        self._bindings: dict[tuple[str, str, str], InstalledCapability] = {}
        self._offered: dict[tuple[str, str, str], CapabilitySpec] = {}

    def offer(self, spec: CapabilitySpec) -> None:
        """Advertise a known integration requiring setup, without a handler."""
        checked = CapabilitySpec.model_validate(spec)
        self._offered[checked.identity.key] = checked

    def offered(self) -> tuple[CapabilitySpec, ...]:
        return tuple(
            self._offered[key] for key in sorted(self._offered) if key not in self._bindings
        )

    def unregister(self, identity: AssetIdentity) -> None:
        """Remove a disconnected binding; never pretend its cached schema is live."""
        self._bindings.pop(identity.key, None)

    def register(
        self,
        spec: CapabilitySpec,
        handler: CapabilityHandler,
        input_model: type[Contract],
        output_model: type[Contract],
        dependencies: ExecutionDependencies,
        secrets: tuple[SecretRef, ...] = (),
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        checked = CapabilitySpec.model_validate(spec)
        if timeout_seconds is not None and not 0 < timeout_seconds <= 3600:
            raise ValueError("capability timeout must be finite and positive, at most one hour")
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
            timeout_seconds,
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
    """Compatibility facade for execution under the environment's identity.

    Owner2026-11-12: IT, the OS and the source service decide tool usability.
    Legacy grants and owner_mode are accepted for configuration compatibility;
    neither controls tool execution. The Bridge still checks the real target,
    dependencies, input/output contracts and handler outcome. This facade does
    not assert that IT reviewed or approved a particular operation.
    """

    def __init__(
        self,
        grants: tuple[CapabilityGrant, ...] = (),
        *,
        owner_mode: bool = False,
    ) -> None:
        self.owner_mode = owner_mode
        # Historical metadata remains readable while callers migrate; it is
        # never an admission list and no synthetic approval record is made.
        self.confirmed_writes: set[tuple[str, str, str]] = set()

    def add(self, grant: CapabilityGrant) -> None:
        """Accept an obsolete caller's grant without granting or recording anything."""

    def confirm_writes(self, spec: CapabilitySpec) -> None:
        """Retain legacy descriptive metadata; no execution depends on it."""
        self.confirmed_writes.add(spec.identity.key)

    def confirmation_needed(self, spec: CapabilitySpec, origin: str) -> bool:
        """AEP adds no per-tool or per-call approval boundary."""
        return False

    def authorize(self, context: RequestContext, spec: CapabilitySpec) -> ExecutionAuthorization:
        """Carry the authenticated call identity, not an application permission grant."""
        return ExecutionAuthorization(
            allowed=True,
            actor=context.actor,
            asset=spec.identity,
            trace=context.trace,
            policy_ref="execution-environment",
        )
