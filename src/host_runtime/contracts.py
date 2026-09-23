"""Closed contracts for the company-workstation host."""

from pathlib import Path, PureWindowsPath
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, field_validator, model_validator

from capabilities.weekly_report.contracts import WeeklyReportSettings
from common.assets import SecretRef, reject_embedded_secrets
from common.base import Contract, Slug, Symbol, Text
from common.enrollment import BridgeDevice
from integrations.jira import JiraConnection
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


def _loopback(base_url: str) -> bool:
    host = urlsplit(base_url).hostname
    return host in ("127.0.0.1", "::1", "localhost")


class PlatformBinding(Contract):
    """How this host reaches the shared platform and as which token.

    The token's secret is a `SecretRef` like the Telegram bot token: the host
    maps its name to an environment variable, and the value is never in a
    file. A plain-HTTP platform is accepted on loopback only, so the wire can
    be exercised without a certificate and a token never crosses a network in
    the clear.
    """

    base_url: Text
    token_id: Symbol
    credential: SecretRef
    timeout_seconds: int = Field(default=30, ge=1, le=300, strict=True)

    @field_validator("base_url")
    @classmethod
    def without_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def https_beyond_loopback(self) -> Self:
        parts = urlsplit(self.base_url)
        if (
            parts.scheme not in ("https", "http")
            or not parts.hostname
            or parts.path
            or parts.query
            or parts.fragment
        ):
            raise ValueError("base_url is the origin of the shared platform")
        if parts.username is not None or parts.password is not None:
            # A credential in a URL is a credential in a file.
            raise ValueError("base_url carries no credential; the token is a SecretRef")
        if parts.scheme == "http" and not _loopback(self.base_url):
            raise ValueError("a platform beyond loopback is reached over https")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class HostIntegrations(Contract):
    """The external systems this host reaches and the workflows' settings,
    none of it secret: a Jira site whose token is a `SecretRef`, and the
    weekly report's workbook and rules."""

    jira: JiraConnection | None = None
    weekly_report: WeeklyReportSettings | None = None


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
    # The shared platform, when this host has been given a token for one. A
    # host without it works locally, which every earlier command still does.
    platform: PlatformBinding | None = None
    # The external systems the migrated workflows reach, when configured.
    integrations: HostIntegrations | None = None
    # How long one capability step may run. The platform's default of thirty
    # seconds is right for a file read and wrong for a Jira search over a
    # week's tickets with their comment threads and a throttle waited out;
    # the source's job ran under no such cap. A step that outlives this
    # fails as `timeout`, and the thread it was running on finishes on its
    # own, so the cap is a report, not a stop.
    capability_timeout_seconds: int = Field(default=600, ge=1, le=3600, strict=True)
    # How long a caller waits for a workflow before the Agent reports it
    # still running; no shorter than a step's cap, or the caller would be
    # told `workflow_timeout` while the step was still allowed to finish.
    workflow_wait_seconds: int = Field(default=900, ge=1, le=7200, strict=True)

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
        if self.workflow_wait_seconds < self.capability_timeout_seconds:
            raise ValueError("a caller waits at least as long as one step may run")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    def credential_environment(self) -> dict[str, str]:
        return {item.secret: item.environment_variable for item in self.credentials}


class HostLayout(Contract):
    """Where a company host keeps what it needs, all under one workspace, so
    an operator and the installer agree without a second configuration file."""

    workspace_root: Path
    membership: Path
    grants: Path
    authorization: Path
    skills: Path
    workflows: Path
    telegram: Path
    state: Path

    @classmethod
    def under(cls, workspace_root: Path | str) -> Self:
        root = Path(workspace_root)
        return cls(
            workspace_root=root,
            membership=root / "membership.json",
            grants=root / "grants.json",
            authorization=root / "authorization.json",
            skills=root / "assets" / "skills",
            workflows=root / "assets" / "workflows",
            telegram=root / "telegram.json",
            state=root / "state.sqlite",
        )


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
        "platform",
        "integrations",
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
