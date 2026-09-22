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

    A company workstation has one owner; the contract refuses a second active
    binding or an active binding that is not the registering owner, so the
    local rule cannot drift from the control plane's."""

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
        if self.device.device_kind == "company_workstation":
            if len(active) > 1:
                raise ValueError("a company workstation has one active member")
            if active and active[0].actor != self.device.registered_by:
                raise ValueError("a company workstation's member is its registered owner")
        return self

    def binding_for(self, actor: str) -> BridgeBinding | None:
        for item in self.bindings:
            if item.actor == actor and item.status == "active":
                return item
        return None


class LocalAgentRequest(Contract):
    """One request to the resident Agent, from whichever ingress carried it.

    The ingress is recorded as the channel so a trace says where a request
    came from, and it changes nothing about what may run: every ingress is
    admitted by the same membership rule and routed by the same Gateway."""

    ingress: Ingress
    actor: Symbol
    bridge_id: Symbol
    namespace: Slug
    message: Text
    trace: TraceIdentifiers
    session_id: Symbol | None = None

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self
