"""Closed contracts for the company-workstation host."""

from pathlib import Path, PureWindowsPath
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Slug, Symbol, Text
from common.enrollment import BridgeDevice
from workflow.host_bridge import BridgeRegistration

# The name of an environment variable, which is not a credential and cannot
# hold one shaped like a token: no colon, no equals sign, no space.
EnvironmentVariable = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]


class CredentialBinding(Contract):
    """Which environment variable holds the value for a declared `SecretRef`.

    Both halves are names. The secret's own name is what an asset declares;
    the variable is where this host keeps the value, and the value itself is
    never written down here or anywhere else in the configuration.
    """

    secret: Symbol
    environment_variable: EnvironmentVariable


class CompanyHostConfiguration(Contract):
    """Non-secret local identity and workspace settings.

    Enrollment proof, sessions, external-system credential values and
    capability grants deliberately have no fields here.
    """

    schema_version: Literal["1"] = "1"
    device: BridgeDevice
    workspace_root: Text
    # Which namespace this host's work belongs to. There is no default: the
    # platform does not guess whose assets an employee's request addresses,
    # so a host without one must be told per request.
    namespace: Slug | None = None
    # Added after the first preview; a file without either field maps no
    # secrets and names no namespace, which is why the schema version is
    # unchanged: an older file stays valid and means exactly that.
    credentials: tuple[CredentialBinding, ...] = ()

    @model_validator(mode="after")
    def company_profile_without_secrets(self) -> Self:
        if self.device.device_kind != "company_workstation":
            raise ValueError("this preview package supports a company workstation only")
        # A company host is a Windows computer, and its configuration is
        # written there; a Windows path stays valid when the same file is
        # inspected on another platform. An absolute path of the running
        # platform is accepted too, so the wiring can be exercised anywhere.
        # What is refused either way is a relative path.
        if not (
            PureWindowsPath(self.workspace_root).is_absolute()
            or Path(self.workspace_root).is_absolute()
        ):
            raise ValueError("workspace_root must be an absolute path")
        names = [item.secret for item in self.credentials]
        if len(names) != len(set(names)):
            raise ValueError("a secret is mapped to one environment variable")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    def credential_environment(self) -> dict[str, str]:
        return {item.secret: item.environment_variable for item in self.credentials}


class DoctorCheck(Contract):
    """One thing an operator needs to know. `pending` is for what this host
    has not been given yet, which is not the same as something being wrong:
    a freshly installed host is not enrolled, and says so without failing."""

    name: Literal[
        "operating_system",
        "python",
        "device_profile",
        "workspace",
        "membership",
        "authorization",
        "assets",
        "state",
    ]
    status: Literal["passed", "failed", "pending"]
    detail: Text


class HostDoctorReport(Contract):
    """`status` is the device preflight; `runtime` is whether the resident
    Agent could be started with what this host has been given."""

    status: Literal["ready", "not_ready"]
    checks: tuple[DoctorCheck, ...]
    limitations: tuple[Text, ...]
    runtime: Literal["ready", "pending"] = "pending"


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
