"""Closed contracts for the company-workstation host."""

import re
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

from agent.data_policy import BackendDataApproval
from agent.decisions import DecisionAcceleratorConfig
from capabilities.chipset_report.contracts import ChipsetReportSettings
from capabilities.coding_change.contracts import CodingHostBinding
from capabilities.desktop_session.handlers import DesktopHostBinding
from capabilities.knowledge_pipeline.contracts import KnowledgePipelineHostBinding
from capabilities.release_package.contracts import IsolatedApplySettings, ReleasePreviewSettings
from capabilities.team_tickets.contracts import TeamTicketsSettings
from capabilities.web.handlers import WebHostBinding
from capabilities.weekly_report.contracts import WeeklyReportSettings
from common.assets import AssetIdentity, SecretRef, reject_embedded_secrets
from common.base import Contract, Slug, Symbol, Text
from common.enrollment import BridgeDevice
from common.execution import Failure, IdempotencyKey
from dut.adapters import PhysicalDriverConfiguration
from dut.contracts import DutTarget, InstrumentTarget
from integrations.github_project import GitHubProjectConnection
from integrations.jira import JiraConnection
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


def _pinned(value: str | None) -> str | None:
    """A certificate pin as `AB:CD:...`; None when not set."""
    if value is None or not value.strip():
        return None
    from common.certificates import normalize_fingerprint

    return normalize_fingerprint(value)


def _one_trust(certificate_sha256: str | None, ca_file: str | None) -> None:
    if certificate_sha256 and ca_file:
        raise ValueError("trust the platform by a pinned fingerprint or by a CA file, not both")


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
    # A platform with a self-signed certificate (owner 2026-10-16): the
    # exact certificate's SHA-256 fingerprint, which the administrator hands
    # out, or a PEM CA file to verify the chain and name against. Neither
    # turns verification off; without both the system's trust store decides.
    certificate_sha256: str | None = None
    ca_file: Text | None = None

    @field_validator("base_url", "member_portal_url")
    @classmethod
    def without_trailing_slash(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value is not None else None

    @field_validator("certificate_sha256")
    @classmethod
    def a_sha256_pin(cls, value: str | None) -> str | None:
        return _pinned(value)

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
        _one_trust(self.certificate_sha256, self.ca_file)
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class PlatformPublishBinding(Contract):
    """Where this host's owner publishes Skills and Workflows, and as whom
    (owner 2026-10-15, `docs/phases/MEMBER_PUBLISH.md`).

    Publishing is the member's act, so it uses the member's own `Personal
    Agent` login, issued in the Member Portal, never the Bridge token; a host
    may publish without being enrolled as a Bridge. The login's value is a
    `SecretRef` mapped to an environment variable, never in a file.
    """

    member_portal_url: Text
    credential: SecretRef
    timeout_seconds: int = Field(default=30, ge=1, le=300, strict=True)
    # The same trust as `PlatformBinding` (owner 2026-10-16); both ports of a
    # platform present one certificate.
    certificate_sha256: str | None = None
    ca_file: Text | None = None

    @field_validator("member_portal_url")
    @classmethod
    def without_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("certificate_sha256")
    @classmethod
    def a_sha256_pin(cls, value: str | None) -> str | None:
        return _pinned(value)

    @model_validator(mode="after")
    def https_beyond_loopback(self) -> Self:
        parts = urlsplit(self.member_portal_url)
        if (
            parts.scheme not in ("https", "http")
            or not parts.hostname
            or parts.path
            or parts.query
            or parts.fragment
        ):
            raise ValueError("member_portal_url is an origin of the shared platform")
        if parts.username is not None or parts.password is not None:
            raise ValueError("member_portal_url carries no credential")
        if parts.scheme == "http" and not _loopback(self.member_portal_url):
            raise ValueError("a member portal beyond loopback is reached over https")
        _one_trust(self.certificate_sha256, self.ca_file)
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
    categories: tuple[Symbol, ...] = ()
    dependencies: tuple[Text, ...] = ()
    # Where it came from and who wrote it, e.g. "member-portal (author leo)".
    provenance: tuple[Text, ...] = ()
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
    # The Bridge this host is enrolled as, so "Open Marketplace" can name it.
    bridge_id: str = ""
    # `grants.json` exists: a sync installs files only and permissions stay
    # with that file (owner decision (a), 2026-10-15).
    assets_only: StrictBool = False
    connection: PlatformReachability | None = None
    note: Text
    catalog: tuple[PlatformCatalogProjection, ...] = ()
    decisions: tuple[PlatformDecisionProjection, ...] = ()


class ExtensionLifecycleProjection(Contract):
    """One locally staged Bridge Extension as visible to its operator.

    This is evidence about local package/runtime state.  It is deliberately
    not an activation request and carries no permission or approval.
    """

    namespace: Slug
    name: Symbol
    version: Text
    description: str = ""
    state: Literal["staged", "active", "refused", "unhealthy", "rolled_back", "disabled"]
    publisher_key_id: Symbol
    capabilities: tuple[Text, ...] = ()
    approval_required: StrictBool
    activation_gate: Text
    code: Symbol | None = None


class PlatformSyncRequest(Contract):
    """An explicit user action. It intentionally accepts no instruction."""


class WorkflowOptionsRequest(Contract):
    """Current choices for one field with a dynamic choice source."""

    workflow: AssetIdentity
    field: Symbol
    answers: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class WorkflowIdentityRequest(Contract):
    """The calling member's last identity values for one Workflow (forms v2)."""

    workflow: AssetIdentity


class WorkflowSettingsUpdateRequest(Contract):
    """One Workflow's per-install settings from the settings page."""

    workflow: AssetIdentity
    values: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ModelSettingsUpdateRequest(Contract):
    """One local model endpoint selected by the device operator.

    The request deliberately has no credential-value field.  A protected
    gateway may name a symbolic secret and the environment variable that will
    hold it after restart.
    """

    alias: Symbol
    provider: Literal["openai_compatible", "ollama"]
    model: Text
    base_url: Text
    credential_secret: Symbol | None = None
    credential_environment: EnvironmentVariable | None = None
    reasoning: Literal["none", "low", "medium", "high"] = "medium"
    tool_calling: StrictBool = True
    structured_output: StrictBool = True
    streaming: StrictBool = False
    vision: StrictBool = False
    local: StrictBool = False
    max_context_tokens: int = Field(default=128_000, ge=1, le=10_000_000, strict=True)
    require_local_model: StrictBool = False

    @model_validator(mode="after")
    def credential_names_are_a_pair(self) -> Self:
        if (self.credential_secret is None) != (self.credential_environment is None):
            raise ValueError(
                "credential_secret and credential_environment are both set or both absent"
            )
        if self.provider == "ollama" and self.credential_secret is not None:
            raise ValueError("an Ollama endpoint does not accept a credential binding")
        return self


class PlatformSyncResult(Contract):
    """What the existing all-or-nothing sync did and what the UI observed."""

    status: PlatformReachability
    failure: Failure | None = None
    installed: tuple[AssetIdentity, ...] = ()
    selections: int | None = Field(default=None, ge=0, strict=True)
    # Files only; permissions stay with this PC's grants.json (owner 2026-10-15).
    assets_only: StrictBool = False
    before: PlatformProjection
    after: PlatformProjection

    @model_validator(mode="after")
    def typed_failure(self) -> Self:
        if (self.status == "answered") != (self.failure is None):
            raise ValueError("only an answered synchronization omits failure details")
        return self


class AgentProfileActivationRequest(Contract):
    """Exact installed profile chosen locally; actor and authority are host state."""

    profile: AssetIdentity


class WorkflowLaunchRequest(Contract):
    """One exact installed Workflow plus its contract-shaped JSON arguments."""

    workflow: AssetIdentity
    arguments: dict[Symbol, JsonValue] = Field(default_factory=dict)
    idempotency_key: IdempotencyKey
    # A run started from a conversation's inline form: the run and its
    # result are added to that conversation (owner 2026-10-15).
    session_id: Symbol | None = None

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
    skill: AssetIdentity | None = None

    @model_validator(mode="after")
    def no_credential_material(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class HostIntegrations(Contract):
    """The external systems this host reaches and the workflows' settings,
    none of it secret: the GitHub board, the company Jira site, and the
    separate weekly-report and team-ticket settings. Tokens are `SecretRef`s.

    A host installed before the report's source moved will refuse a
    configuration naming `github_project`, because the field did not exist
    yet. That refusal reads as a typo and is not one: it is an old
    installation, and the answer is to install the current bundle.
    """

    github_project: GitHubProjectConnection | None = None
    jira: JiraConnection | None = None
    team_tickets: TeamTicketsSettings | None = None
    weekly_report: WeeklyReportSettings | None = None
    chipset_report: ChipsetReportSettings | None = None
    release_package: ReleasePreviewSettings | None = None
    isolated_release_apply: IsolatedApplySettings | None = None


class GatewayHostApproval(BackendDataApproval):
    """Tie a generic data grant to one exact host-configured Gateway URL."""

    endpoint_alias: Symbol
    endpoint_base_url: Text


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

    A configured endpoint is not data-transfer approval. A host administrator
    separately approves an exact routed Gateway URL and explicit data classes.
    Changing the routed endpoint invalidates the approval rather than silently
    inheriting trust from a URL that happens to be on localhost.
    """

    catalog: ModelCatalog
    routing_alias: Symbol | None = None
    require_local_model: StrictBool = False
    # Per-alias wire details an adapter takes but the catalog does not
    # describe, such as a model that rejects the newer `max_completion_tokens`
    # name. Host wiring, which is why it is here and not in the catalog.
    options: dict[Symbol, dict[str, str]] = {}
    data_approval: GatewayHostApproval | None = None

    @model_validator(mode="after")
    def the_routing_alias_is_one_of_the_endpoints(self) -> Self:
        if self.routing_alias is not None and self.catalog.endpoint(self.routing_alias) is None:
            raise ValueError("routing_alias names an endpoint this catalog does not have")
        unknown = sorted(alias for alias in self.options if self.catalog.endpoint(alias) is None)
        if unknown:
            raise ValueError(f"options name no endpoint: {', '.join(unknown)}")
        approval = self.data_approval
        if approval is not None:
            endpoint = (
                None if self.routing_alias is None else self.catalog.endpoint(self.routing_alias)
            )
            if (
                approval.backend_id != "gateway"
                or endpoint is None
                or approval.endpoint_alias != endpoint.alias
                or approval.endpoint_base_url != endpoint.base_url
            ):
                raise ValueError("Gateway data approval must name the exact routed endpoint")
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
    # The owner sets this for each Vault. Existing bindings remain private.
    privacy: Literal["private", "public"] = "private"

    @field_validator("vault_root")
    @classmethod
    def absolute_vault_root(cls, value: str) -> str:
        if not (PureWindowsPath(value).is_absolute() or Path(value).is_absolute()):
            raise ValueError("vault_root must be an absolute path")
        return value


class ScheduleHostSettings(Contract):
    """How this host runs its local schedules. Off unless the owner opts in.

    `resident_loop` starts a schedule loop inside the long-running Agent Web
    process; nothing starts it when a host is merely built. `aep-host
    schedules tick` runs one poll either way, for Windows Task Scheduler or
    recovery. A missed occurrence older than `catch_up_hours` is skipped
    rather than run; only the latest missed occurrence is ever caught up.
    """

    resident_loop: StrictBool = False
    poll_seconds: int = Field(default=30, ge=5, le=3600, strict=True)
    catch_up_hours: int = Field(default=24, ge=1, le=336, strict=True)


_SSH_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
_SSH_USER = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]{0,31}")


class LayaSettings(Contract):
    """Laya decision acceleration as the Settings page edits it (owner 2026-10-13).

    The Agent reaches Laya only through an SSH tunnel to a loopback port, so the
    decision endpoint stays `http://127.0.0.1:<local_port>`: a plaintext LAN
    address is never accepted. Host and user are checked so they can only be
    an address and an account name on the ssh command line, never an option.
    """

    ssh_host: str = Field(default="", max_length=253)
    ssh_port: int = Field(default=22, ge=1, le=65535, strict=True)
    ssh_user: str = Field(default="", max_length=32)
    remote_port: int = Field(default=8000, ge=1, le=65535, strict=True)
    local_port: int = Field(default=18000, ge=1024, le=65535, strict=True)
    # Agent Web opens the tunnel itself while it runs and reopens it when it drops.
    auto_tunnel: StrictBool = False
    mode: Literal["off", "shadow", "active"] = "off"
    confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    timeout_ms: int = Field(default=1500, ge=100, le=5000, strict=True)
    # The owner's approval to send the latest user message to Laya.
    approval_ref: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def ssh_names_only(self) -> Self:
        if self.ssh_host and not _SSH_HOST.fullmatch(self.ssh_host):
            raise ValueError("ssh_host must be a host name or address")
        if self.ssh_user and not _SSH_USER.fullmatch(self.ssh_user):
            raise ValueError("ssh_user must be an account name")
        if self.auto_tunnel and not (self.ssh_host and self.ssh_user):
            raise ValueError("an automatic tunnel needs ssh_host and ssh_user")
        if self.approval_ref is not None and not self.approval_ref.strip():
            raise ValueError("approval_ref must not be blank")
        return self


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
    # Member publish to the shared platform (owner 2026-10-15); independent of
    # `platform`, which is this host's Bridge enrollment.
    publishing: PlatformPublishBinding | None = None
    # The external systems the migrated workflows reach, when configured.
    integrations: HostIntegrations | None = None
    # The models this host may use. Absent means none, and the Agent then
    # matches commands and runs Workflows without reasoning about anything,
    # which is what every host did before this field existed.
    models: ModelBinding | None = None
    # Optional bounded-decision acceleration. NONE is an exact baseline path;
    # a configured provider alone grants no data egress or execution authority.
    decision_accelerator: DecisionAcceleratorConfig = DecisionAcceleratorConfig()
    # The Settings page's Laya card (owner 2026-10-13): the SSH tunnel to the
    # Laya host and the mode it sets; `decision_accelerator` is derived from it.
    laya: LayaSettings | None = None
    # Published Knowledge is installed only through exact local bindings.
    # Querying it needs the same explicitly configured model used by the
    # Personal Agent, so an empty binding cannot quietly become retrieval-only
    # output that violates the grounded-answer contract.
    knowledge: tuple[KnowledgeHostBinding, ...] = ()
    # Optional physical DUT boundary. The driver is fixed by trusted local
    # configuration and remains disabled until the operator explicitly opts in.
    dut: DutHostBinding | None = None
    # Coding on the Bridge (docs/phases/CODING_ON_BRIDGE.md): which
    # repositories may be changed and the restricted runner interpreter.
    coding: CodingHostBinding | None = None
    # Sandboxed Knowledge convert/ingest/lint (docs/phases/KNOWLEDGE_K1.md):
    # the base vaults people may copy into a personal sandbox.
    knowledge_pipeline: KnowledgePipelineHostBinding | None = None
    # Owner mode (owner 2026-10-11): on a host without the shared platform's
    # member decisions, the device owner holds every installed capability, a
    # person's own request needs no recorded approval, and a side effect the
    # conversation model chose itself waits for the person. False keeps the
    # strict grants.json rules (an explicit, approved grant per capability).
    local_owner_grants: StrictBool = True
    # Web steps of generated Workflows (docs/phases/SOP_TO_WORKFLOW.md W2):
    # the origins they may open and the browser profile they use.
    web: WebHostBinding | None = None
    # Registered Windows applications the Agent may operate (lab gap L2).
    desktop: DesktopHostBinding | None = None
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
    # Local scheduled tasks; the resident loop stays off unless enabled here
    # or by `aep-host web --schedules`.
    schedules: ScheduleHostSettings = ScheduleHostSettings()

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
    # What the platform says this device's member selected, kept for display
    # only while `grants.json` decides what runs (assets-only sync, owner
    # 2026-10-15). The host never reads it as an authorization.
    platform_selections: Path
    skills: Path
    workflows: Path
    knowledge: Path
    knowledge_vaults: Path
    agents: Path
    extensions: Path
    script_tools: Path
    extension_lifecycle: Path
    active_profile: Path
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
            platform_selections=root / "platform-selections.json",
            skills=root / "assets" / "skills",
            workflows=root / "assets" / "workflows",
            knowledge=root / "assets" / "knowledge",
            knowledge_vaults=root / "assets" / "knowledge-vaults",
            agents=root / "assets" / "agents",
            extensions=root / "assets" / "extensions",
            script_tools=root / "assets" / "script-tools",
            extension_lifecycle=root / "extension-lifecycle.json",
            active_profile=root / "active-agent-profile.json",
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
        "coding",
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
