"""Closed metadata for out-of-process Bridge Extensions."""

from typing import Literal, Self

from pydantic import Field, model_validator

from capabilities.contracts import CapabilitySpec
from common.assets import AssetMetadata, RegistryContract
from common.base import Symbol, Text


class ExtensionCompatibility(RegistryContract):
    """The only extension runtime supported by the Windows preview."""

    bridge_contract: Literal["1"] = "1"
    platform: Literal["windows"] = "windows"
    python: Literal["3.12"] = "3.12"
    abi: Literal["cp312-win_amd64"] = "cp312-win_amd64"
    protocol: Literal["aep-extension-jsonl/v1"] = "aep-extension-jsonl/v1"


class ExtensionProcess(RegistryContract):
    """A module launched by a dedicated runner, never imported by the Bridge."""

    module: Symbol
    protocol: Literal["aep-extension-jsonl/v1"] = "aep-extension-jsonl/v1"


class ExtensionHealthPolicy(RegistryContract):
    startup_timeout_seconds: int = Field(default=15, ge=1, le=60, strict=True)
    request_timeout_seconds: int = Field(default=30, ge=1, le=300, strict=True)
    max_crashes: int = Field(default=3, ge=1, le=10, strict=True)
    crash_window_seconds: int = Field(default=300, ge=30, le=3600, strict=True)


class ExtensionRollbackPolicy(RegistryContract):
    retain_versions: int = Field(default=2, ge=2, le=5, strict=True)
    automatic_on: tuple[Literal["startup_failure", "health_failure", "crash_limit"], ...] = (
        "startup_failure",
        "health_failure",
        "crash_limit",
    )

    @model_validator(mode="after")
    def unique_triggers(self) -> Self:
        if len(self.automatic_on) != len(set(self.automatic_on)):
            raise ValueError("an extension rollback trigger is declared once")
        return self


class PublisherKeyRef(RegistryContract):
    """Public trust-root identity; signature bytes belong to the package."""

    algorithm: Literal["ed25519"] = "ed25519"
    key_id: Symbol


class BridgeExtensionManifest(RegistryContract):
    metadata: AssetMetadata
    kind: Literal["bridge_extension"] = "bridge_extension"
    description: Text
    compatibility: ExtensionCompatibility
    process: ExtensionProcess
    capabilities: tuple[CapabilitySpec, ...] = Field(min_length=1)
    health: ExtensionHealthPolicy = ExtensionHealthPolicy()
    rollback: ExtensionRollbackPolicy = ExtensionRollbackPolicy()
    publisher_key: PublisherKeyRef

    @model_validator(mode="after")
    def governed_external_process(self) -> Self:
        identities = [item.identity.key for item in self.capabilities]
        if len(identities) != len(set(identities)):
            raise ValueError("an extension declares each capability once")
        if self.process.protocol != self.compatibility.protocol:
            raise ValueError("extension process and compatibility protocols must match")
        policy = self.metadata.technical_policy
        if self.metadata.lifecycle == "published" and (
            policy.status != "approved"
            or not policy.policy_refs
            or not self.metadata.validation_refs
        ):
            raise ValueError("published Bridge Extensions require technical approval evidence")
        return self
