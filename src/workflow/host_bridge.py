"""Execution-plane advertisements; no transport, resource access or execution."""

from typing import Literal, Self

from pydantic import StrictBool, model_validator

from capabilities.contracts import CapabilitySpec
from common.assets import AssetIdentity, Compatibility
from common.base import Contract, Symbol
from common.execution import TraceIdentifiers


class LocalResource(Contract):
    resource_id: Symbol
    kind: Literal["memory", "filesystem", "browser", "dut", "instrument", "other"]
    available: StrictBool


class BridgeRegistration(Contract):
    bridge_id: Symbol
    owner_id: Symbol
    trace: TraceIdentifiers
    compatibility: Compatibility = Compatibility()
    capabilities: tuple[CapabilitySpec, ...] = ()
    installed_tasks: tuple[AssetIdentity, ...] = ()
    local_resources: tuple[LocalResource, ...] = ()

    @model_validator(mode="after")
    def unique_advertisements(self) -> Self:
        groups = (
            [cap.identity.key for cap in self.capabilities],
            [task.key for task in self.installed_tasks],
            [resource.resource_id for resource in self.local_resources],
        )
        if any(len(group) != len(set(group)) for group in groups):
            raise ValueError("advertisement identities must be unique")
        return self
