"""Atomic capability descriptions, never executable callables."""

from typing import Self

from pydantic import model_validator

from common.assets import AssetIdentity, RegistryContract, TechnicalPolicy
from common.base import Symbol, Text
from common.execution import SideEffect


class CapabilitySpec(RegistryContract):
    identity: AssetIdentity
    name: Symbol
    description: Text
    input_contract: Symbol
    output_contract: Symbol
    side_effect: SideEffect
    policy: TechnicalPolicy

    @model_validator(mode="after")
    def side_effect_policy(self) -> Self:
        if self.side_effect != "read" and (
            not self.policy.approval_required or not self.policy.policy_refs
        ):
            raise ValueError("side-effecting capabilities require explicit approval policy refs")
        return self
