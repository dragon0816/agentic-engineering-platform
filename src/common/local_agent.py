"""What the resident local Agent on a Bridge computer accepts, and from whom.

The Bridge computer holds its own copy of who may use it, because company
work must not stop when the shared platform is unreachable. That copy grants
nothing beyond use of the device: capability authorization stays with the
Bridge policy, secrets stay in the execution environment, and publication
still implies no execution.
"""

from typing import Literal, Self

from pydantic import model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Slug, Symbol, Text
from common.enrollment import BridgeBinding, BridgeDevice
from common.execution import TraceIdentifiers

Ingress = Literal["local", "shared_platform", "telegram"]


class BridgeMembership(Contract):
    """The device and the bindings that may use it, as the Bridge holds them.

    Every machine has one member; the contract refuses a second active
    binding, so the local rule cannot drift from the control plane's. On a
    company workstation that member is the employee who registered it. On a
    shared test machine it is a virtual member of its own, which is what
    keeps any real employee's credential off a machine other people can
    read."""

    device: BridgeDevice
    bindings: tuple[BridgeBinding, ...] = ()

    @model_validator(mode="after")
    def bindings_belong_to_this_device(self) -> Self:
        actors = [item.actor for item in self.bindings]
        if len(actors) != len(set(actors)):
            raise ValueError("an actor is bound to a device once")
        if any(item.bridge_id != self.device.bridge_id for item in self.bindings):
            raise ValueError("a binding names the device it belongs to")
        active = [item for item in self.bindings if item.status == "active"]
        if len(active) > 1:
            raise ValueError("a device has one active member")
        if (
            self.device.device_kind == "company_workstation"
            and active
            and active[0].actor != self.device.registered_by
        ):
            raise ValueError("a company workstation's member is its registered owner")
        return self

    def binding_for(self, actor: str) -> BridgeBinding | None:
        for item in self.bindings:
            if item.actor == actor and item.status == "active":
                return item
        return None

    def member(self) -> str | None:
        """Who this machine runs as, or None before anybody is bound. An
        ingress that carries a request for somebody else needs to know whose
        machine it is acting as."""
        active = [item for item in self.bindings if item.status == "active"]
        return active[0].actor if active else None


class LocalAgentRequest(Contract):
    """One request to the resident Agent, from whichever ingress carried it.

    The ingress is recorded as the channel so a trace says where a request
    came from, and it changes nothing about what may run: every ingress is
    admitted by the same membership rule and routed by the same Gateway."""

    ingress: Ingress
    actor: Symbol
    # The member who asked, when that is not the member who runs. It is
    # recorded and never consulted: admission, grants and entitlement all read
    # `actor`, so nothing here can widen what may happen. A field that looked
    # like authorization and was not would be worse than no field at all.
    on_behalf_of: Symbol | None = None
    bridge_id: Symbol
    namespace: Slug
    message: Text
    trace: TraceIdentifiers
    session_id: Symbol | None = None

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        if self.on_behalf_of == self.actor:
            raise ValueError("a request on your own behalf names nobody else")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self
