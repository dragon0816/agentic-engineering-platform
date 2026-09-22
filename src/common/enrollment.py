"""Provider-neutral account invitation and Bridge device identity contracts.

These records contain no password, invitation proof, session, credential,
capability grant or secret value. Authentication belongs to the shared-platform
host; capability authorization remains at the Bridge execution boundary.
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from common.base import Contract, Symbol


class Invitation(Contract):
    invitation_id: Symbol
    actor: Symbol
    issued_by: Symbol
    status: Literal["pending", "accepted", "revoked"] = "pending"
    accepted_by: Symbol | None = None

    @model_validator(mode="after")
    def acceptance(self) -> Self:
        if (self.status == "accepted") != (self.accepted_by is not None):
            raise ValueError("accepted invitations name the actor that accepted them")
        if self.accepted_by is not None and self.accepted_by != self.actor:
            raise ValueError("an invitation may be accepted only by its named actor")
        return self


class PlatformUser(Contract):
    actor: Symbol
    invitation_id: Symbol
    status: Literal["active", "disabled"] = "active"


class BridgeDevice(Contract):
    bridge_id: Symbol
    registered_by: Symbol
    device_kind: Literal["company_workstation", "shared_test_workstation"]
    windows_account_mode: Literal["dedicated_user", "shared_user"]
    resource_scope: Literal["corporate_internal", "external_only"]
    local_isolation: Literal["single_user", "cooperative_workspace"]
    interactive_slots: int = Field(default=1, ge=1, strict=True)
    status: Literal["active", "disabled"] = "active"

    @model_validator(mode="after")
    def deployment_profile(self) -> Self:
        if self.interactive_slots != 1:
            raise ValueError("Phase 7 workstations serialize interactive execution")
        actual = (
            self.windows_account_mode,
            self.resource_scope,
            self.local_isolation,
        )
        expected = {
            "company_workstation": (
                "dedicated_user",
                "corporate_internal",
                "single_user",
            ),
            "shared_test_workstation": (
                "shared_user",
                "external_only",
                "cooperative_workspace",
            ),
        }[self.device_kind]
        if actual != expected:
            raise ValueError("device security and resource profile must match its kind")
        return self


class BridgeBinding(Contract):
    """May use one Bridge; grants no capability, asset, secret or side effect."""

    bridge_id: Symbol
    actor: Symbol
    role: Literal["device_admin", "operator"]
    status: Literal["active", "revoked"] = "active"


class BridgeExecutionSubject(Contract):
    """Authenticated actor and selected device carried into a new execution."""

    actor: Symbol
    bridge_id: Symbol
