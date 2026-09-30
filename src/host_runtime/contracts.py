"""Closed contracts for the company-workstation host."""

from pathlib import Path, PureWindowsPath
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    Field,
    JsonValue,
    StrictBool,
    StringConstraints,
    field_validator,
    model_validator,
)

from capabilities.weekly_report.contracts import WeeklyReportSettings
from common.assets import AssetIdentity, SecretRef, reject_embedded_secrets
from common.base import Contract, Slug, Symbol, Text
from common.enrollment import BridgeDevice
from common.execution import Failure, IdempotencyKey
from dut.adapters import PhysicalDriverConfiguration
from dut.contracts import DutTarget, InstrumentTarget
from integrations.github_project import GitHubProjectConnection
from models.catalog import ModelCatalog
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
    # Interactive member sign-in and selection use a different credential and
    # may be served on a different port.  This optional origin is navigation
    # metadata only; the Bridge client never sends its token there.
    member_portal_url: Text | None = None
    token_id: Symbol
    credential: SecretRef
    timeout_seconds: int = Field(default=30, ge=1, le=300, strict=True)

    @field_validator("base_url", "member_portal_url")
    @classmethod
    def without_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value is not None else None

    @model_validator(mode="after")
    def https_beyond_loopback(self) -> Self:
        for field, url in (
            ("base_url", self.base_url),
            ("member_portal_url", self.member_portal_url),
        ):
            if url is None:
                continue
            parts = urlsplit(url)
            if (
                parts.scheme not in ("https", "http")
                or not parts.hostname
                or parts.path
                or parts.query
                or parts.fragment
            ):
                raise ValueError(f"{field} is an origin of the shared platform")
            if parts.username is not None or parts.password is not None:
                # A credential in a URL is a credential in a file.
                raise ValueError(f"{field} carries no credential")
            if parts.scheme == "http" and not _loopback(url):
                if field == "member_portal_url":
                    raise ValueError("a member portal beyond loopback is reached over https")
                raise ValueError("a platform beyond loopback is reached over https")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


PlatformReachability = Literal["answered", "unreachable", "withdrawn", "rejected", "refused"]


class PlatformCatalogProjection(Contract):
    """One published package as shown by the local Personal Agent Web.

    These are display facts only. In particular, none of the three booleans
    is an execution permission.
    """

    kind: Symbol
    namespace: Slug
    name: Symbol
    version: Text
    description: str = ""
    owner: Text
    visibility: Symbol
    lifecycle: Symbol
    dependencies: tuple[Text, ...] = ()
    runtime: str = ""
    platforms: tuple[Symbol, ...] = ()
    published: StrictBool
    authorized: StrictBool
    installed: StrictBool


class PlatformDecisionProjection(Contract):
    """One active device selection synchronized to the local Bridge."""

    kind: Symbol
    namespace: Slug
    name: Symbol
    version: Text
    actor: Symbol
    installed: StrictBool


class PlatformProjection(Contract):
    """Shared catalog state and the separate facts held on this Bridge."""

    configured: StrictBool
    member_portal_url: str = ""
    connection: PlatformReachability | None = None
    note: Text
    catalog: tuple[PlatformCatalogProjection, ...] = ()
    decisions: tuple[PlatformDecisionProjection, ...] = ()


class PlatformSyncRequest(Contract):
    """An explicit user action. It intentionally accepts no instruction."""


class PlatformSyncResult(Contract):
    """What the existing all-or-nothing sync did and what the UI observed."""

    status: PlatformReachability
    failure: Failure | None = None
    installed: tuple[AssetIdentity, ...] = ()
    selections: int | None = Field(default=None, ge=0, strict=True)
    before: PlatformProjection
    after: PlatformProjection

    @model_validator(mode="after")
    def typed_failure(self) -> Self:
        if (self.status == "answered") != (self.failure is None):
            raise ValueError("only an answered synchronization omits failure details")
        return self


class WorkflowLaunchRequest(Contract):
    """One exact installed Workflow plus its contract-shaped JSON arguments."""

    workflow: AssetIdentity
    arguments: dict[Symbol, JsonValue] = Field(default_factory=dict)
    idempotency_key: IdempotencyKey

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class KnowledgeAskRequest(Contract):
    """One question against one exact installed Knowledge version.

    Actor, Bridge, model and local Vault location are trusted host state and
    therefore deliberately absent from this browser-facing request.
    """

    asset: AssetIdentity
    question: Text

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class HostIntegrations(Contract):
    """The external systems this host reaches and the workflows' settings,
    none of it secret: the project board whose token is a `SecretRef`, and
    the weekly report's workbook and rules.

    A host installed before the report's source moved will refuse a
    configuration naming `github_project`, because the field did not exist
    yet. That refusal reads as a typo and is not one: it is an old
    installation, and the answer is to install the current bundle.
    """

    github_project: GitHubProjectConnection | None = None
    weekly_report: WeeklyReportSettings | None = None


class ModelBinding(Contract):
    """The models this host may use, and how it is allowed to use them.

    The catalog is the platform's own `ModelCatalog`: endpoints declaring what
    they can do, and routes naming them. Nothing here holds a secret; an
    endpoint names its credential and this host's `credentials` say which
    environment variable holds the value, exactly as the board token does.

    `routing_alias` is the endpoint the Agent asks when a request matches no
    installed command. A host that configures a catalog but no routing alias
    has models for capabilities to use and still answers `needs_input` to an
    unrecognized message, which is a reasonable thing to want.

    `require_local_model` narrows routing to an endpoint that runs on this
    machine. An endpoint's `local` flag is about where the model *runs*: an
    Ollama loading a model into this computer's own memory is local, and a
    gateway is not, however close it is. Most machines cannot run a useful
    model and will leave this off; the setting exists so that a workstation
    with the memory to do it can say so, and so that a machine which must
    keep working with nothing reachable can insist on it.

    It is not a data boundary and does not pretend to be one. This platform
    cannot tell a company's own gateway from anybody else's -- both are a URL
    somebody wrote here -- so writing that URL, and mapping a credential to
    go with it, is the decision. Asking for it twice would add a line to
    every host and no information to any of them.
    """

    catalog: ModelCatalog
    routing_alias: Symbol | None = None
    require_local_model: StrictBool = False
    # Per-alias wire details an adapter takes but the catalog does not
    # describe, such as a model that rejects the newer `max_completion_tokens`
    # name. Host wiring, which is why it is here and not in the catalog.
    options: dict[Symbol, dict[str, str]] = {}

    @model_validator(mode="after")
    def the_routing_alias_is_one_of_the_endpoints(self) -> Self:
        if self.routing_alias is not None and self.catalog.endpoint(self.routing_alias) is None:
            raise ValueError("routing_alias names an endpoint this catalog does not have")
        unknown = sorted(alias for alias in self.options if self.catalog.endpoint(alias) is None)
        if unknown:
            raise ValueError(f"options name no endpoint: {', '.join(unknown)}")
        if self.require_local_model and self.routing_alias is not None:
            endpoint = self.catalog.endpoint(self.routing_alias)
            if endpoint is not None and not endpoint.capabilities.local:
                # Refused here rather than at the first message, where it
                # would read as "the model would not answer" instead of "this
                # host was told two things it cannot both do".
                raise ValueError(
                    "require_local_model is set and the routing endpoint does not "
                    "run on this machine"
                )
        return self


class DutHostBinding(Contract):
    """Trusted, credential-free wiring for one company-host DUT driver."""

    skill: AssetIdentity
    target: DutTarget
    instrument: InstrumentTarget | None = None
    driver: PhysicalDriverConfiguration
    physical_enabled: StrictBool = False
    device_available: StrictBool = True
    instrument_available: StrictBool = True

    @model_validator(mode="after")
    def instrument_availability(self) -> Self:
        if self.instrument is None and not self.instrument_available:
            raise ValueError("instrument availability requires an instrument")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class KnowledgeHostBinding(Contract):
    """One exact published Knowledge asset and its local immutable evidence.

    Discovery metadata remains in the manifest under `assets/knowledge`; this
    binding says which local Vault this Bridge may query.  It is deliberately
    an exact identity, never a floating "latest" reference.
    """

    asset: AssetIdentity
    vault_root: Text

    @field_validator("vault_root")
    @classmethod
    def absolute_vault_root(cls, value: str) -> str:
        if not (PureWindowsPath(value).is_absolute() or Path(value).is_absolute()):
            raise ValueError("vault_root must be an absolute path")
        return value


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
    # The models this host may use. Absent means none, and the Agent then
    # matches commands and runs Workflows without reasoning about anything,
    # which is what every host did before this field existed.
    models: ModelBinding | None = None
    # Published Knowledge is installed only through exact local bindings.
    # Querying it needs the same explicitly configured model used by the
    # Personal Agent, so an empty binding cannot quietly become retrieval-only
    # output that violates the grounded-answer contract.
    knowledge: tuple[KnowledgeHostBinding, ...] = ()
    # Optional physical DUT boundary. The driver is fixed by trusted local
    # configuration and remains disabled until the operator explicitly opts in.
    dut: DutHostBinding | None = None
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
        keys = [item.asset.key for item in self.knowledge]
        if len(keys) != len(set(keys)):
            raise ValueError("Knowledge bindings must name unique exact versions")
        if self.knowledge and (self.models is None or self.models.routing_alias is None):
            raise ValueError("installed Knowledge query requires a configured routing model")
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
    knowledge: Path
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
            knowledge=root / "assets" / "knowledge",
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
        "models",
        "knowledge",
        "dut",
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
