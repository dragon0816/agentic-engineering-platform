"""Closed contracts for the company-workstation technical preview."""

from pathlib import PureWindowsPath
from typing import Literal, Self

from pydantic import model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Text
from common.enrollment import BridgeDevice
from workflow.host_bridge import BridgeRegistration


class CompanyHostConfiguration(Contract):
    """Non-secret local identity and workspace settings.

    Enrollment proof, sessions, external-system credentials and capability grants
    deliberately have no fields here.
    """

    schema_version: Literal["1"] = "1"
    device: BridgeDevice
    workspace_root: Text

    @model_validator(mode="after")
    def company_profile_without_secrets(self) -> Self:
        if self.device.device_kind != "company_workstation":
            raise ValueError("this preview package supports a company workstation only")
        if not PureWindowsPath(self.workspace_root).is_absolute():
            raise ValueError("workspace_root must be an absolute Windows path")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class DoctorCheck(Contract):
    name: Literal["operating_system", "python", "device_profile", "workspace"]
    status: Literal["passed", "failed"]
    detail: Text


class HostDoctorReport(Contract):
    status: Literal["ready", "not_ready"]
    checks: tuple[DoctorCheck, ...]
    limitations: tuple[Text, ...]


class EnrollmentRequest(Contract):
    """Inspectable, credential-free input for a future authenticated host call."""

    schema_version: Literal["1"] = "1"
    device: BridgeDevice
    advertisement: BridgeRegistration

    @model_validator(mode="after")
    def matching_identity_without_secrets(self) -> Self:
        if self.advertisement.bridge_id != self.device.bridge_id:
            raise ValueError("advertisement bridge identity must match the device")
        if self.advertisement.owner_id != self.device.registered_by:
            raise ValueError("advertisement owner must match the registering actor")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self
