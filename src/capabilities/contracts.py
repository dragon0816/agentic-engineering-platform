"""Atomic capability descriptions, never executable callables."""

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

    # Legacy policy metadata remains readable. Side effects are execution facts;
    # they do not require an application approval policy to be describable.
