"""Building the resident Agent a company computer actually runs.

Everything the Agent needs lives under the workspace the host was configured
with, in files an operator can read: who may use this Bridge, what it may
run, and what it has already run. Nothing is discovered: a manifest is
loaded because it is in the assets directory, a capability handler exists
because this package ships it, and a grant applies because the grants file
says so. A missing file is a stated reason, never a guess.

The layering rule holds here as everywhere: this module wires existing
pieces together and adds no authority. The policy decides every dispatch,
the engine decides every workflow, and the Agent decides who may ask.
"""

from pathlib import Path
from types import TracebackType
from typing import Literal, Self, TypeVar

from pydantic import ValidationError

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.files import READ_FILE_SPEC, ReadFileHandler, ReadFileInput, ReadFileOutput
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from channels.telegram import TelegramIngress, TelegramIngressConfig
from common.assets import ExecutionDependencies, WorkflowManifest
from common.authorization import DeviceAuthorization
from common.base import Contract
from common.distribution import LocalStateError
from common.local_agent import BridgeMembership
from host_runtime.agent import LocalAgent
from host_runtime.contracts import CompanyHostConfiguration, DoctorCheck, HostDoctorReport

# Re-exported: the layout moved to the contracts module so the platform client
# can take one without importing this module, and callers still find it here.
from host_runtime.contracts import HostLayout as HostLayout
from host_runtime.runtime import inspect_host
from host_runtime.state import SqliteLocalState
from host_runtime.sync import PlatformClient
from host_runtime.workspace import documents
from models.credentials import CredentialResolver, EnvironmentCredentials
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

HostErrorCode = Literal[
    "membership_missing",
    "membership_invalid",
    "membership_mismatch",
    "grants_invalid",
    "authorization_invalid",
    "authorization_mismatch",
    "authorization_conflict",
    "authorization_ungrantable",
    "asset_invalid",
    "telegram_missing",
    "telegram_invalid",
    "credential_unmapped",
    "state_unavailable",
]

ContractT = TypeVar("ContractT", bound=Contract)


class HostError(Exception):
    """Why this host cannot be assembled. The code is closed and the detail
    names the file at fault; neither ever carries its contents."""

    def __init__(self, code: HostErrorCode, path: Path | None = None) -> None:
        self.code: HostErrorCode = code
        self.path = path
        super().__init__(f"{code}: {path}" if path is not None else code)


def _load_one(path: Path, model: type[ContractT], code: HostErrorCode) -> ContractT:
    try:
        return model.model_validate_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValidationError, ValueError) as error:
        raise HostError(code, path) from error


def _load_all(directory: Path, model: type[ContractT]) -> tuple[ContractT, ...]:
    """Every manifest under a directory, in a stable order. A directory that
    does not exist holds nothing, which is different from holding something
    unreadable: that is refused."""
    if not directory.is_dir():
        return ()
    items: list[ContractT] = []
    for path in sorted(directory.glob("*.json")):
        try:
            items.extend(model.model_validate(item) for item in documents(path))
        except (OSError, ValidationError, ValueError) as error:
            raise HostError("asset_invalid", path) from error
    return tuple(items)


class HostRuntime:
    """One assembled company host: its Agent, its durable state and, when the
    operator configured them, its Telegram ingress and its shared-platform
    client. Closing it closes the state file, which on Windows would
    otherwise stay pinned."""

    def __init__(
        self,
        config: CompanyHostConfiguration,
        layout: HostLayout,
        agent: LocalAgent,
        state: SqliteLocalState,
        telegram: TelegramIngress | None,
        platform: PlatformClient | None = None,
    ) -> None:
        self.config = config
        self.layout = layout
        self.agent = agent
        self.state = state
        self.telegram = telegram
        self.platform = platform

    @property
    def actor(self) -> str:
        """Who this host acts as unless the operator names someone else: the
        platform user the device was registered by."""
        return self.config.device.registered_by

    def close(self) -> None:
        self.state.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def load_membership(config: CompanyHostConfiguration, layout: HostLayout) -> BridgeMembership:
    """This Bridge's own copy of who may use it. It must describe the device
    this host is configured as: a membership record for another device would
    admit the wrong people, so it is refused rather than reconciled."""
    if not layout.membership.is_file():
        raise HostError("membership_missing", layout.membership)
    membership = _load_one(layout.membership, BridgeMembership, "membership_invalid")
    if membership.device != config.device:
        raise HostError("membership_mismatch", layout.membership)
    return membership


def load_authorization(
    config: CompanyHostConfiguration, layout: HostLayout
) -> DeviceAuthorization | None:
    """What the members of this device decided it may run, when the control
    plane has told it. A host without one is configured by hand through
    `grants.json`; having both is two answers to one question, so it is
    refused rather than merged."""
    if not layout.authorization.is_file():
        return None
    if layout.grants.is_file():
        raise HostError("authorization_conflict", layout.authorization)
    decided = _load_one(layout.authorization, DeviceAuthorization, "authorization_invalid")
    if decided.bridge_id != config.device.bridge_id:
        raise HostError("authorization_mismatch", layout.authorization)
    return decided


def _configured_grants(layout: HostLayout) -> tuple[CapabilityGrant, ...]:
    """Grants an operator wrote by hand, for a host with no control plane."""
    if not layout.grants.is_file():
        return ()
    try:
        return tuple(CapabilityGrant.model_validate(item) for item in documents(layout.grants))
    except (OSError, ValidationError, ValueError) as error:
        raise HostError("grants_invalid", layout.grants) from error


def _decided_grants(
    authorization: DeviceAuthorization, installed: InstalledCapabilities
) -> tuple[CapabilityGrant, ...]:
    """A member's tool selections, read against the capability this host
    actually has. The permissions and policy references come from that
    specification and never from the selection, so the shared platform and
    this Bridge reach the same grant without either trusting the other's
    arithmetic. A tool that is not installed here grants nothing."""
    grants: list[CapabilityGrant] = []
    for selection in authorization.tools():
        binding = installed.get(selection.asset)
        if binding is None:
            continue
        if not binding.spec.policy.policy_refs:
            # A grant names the policy it was made under, so a capability
            # that declares none cannot be granted. Saying so beats building
            # a host that quietly refuses every dispatch of it.
            raise HostError("authorization_ungrantable")
        grants.append(
            CapabilityGrant(
                actor=selection.actor,
                asset=binding.spec.identity,
                permissions=binding.spec.policy.required_permissions,
                policy_refs=binding.spec.policy.policy_refs,
                approval_ref=selection.approval_ref,
            )
        )
    return tuple(grants)


def build_gateway(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None = None,
) -> Gateway:
    """The platform's own wiring, with what this host was given.

    Routing is deterministic only: no model is configured on a company host
    in this slice, so an unrecognized message is `needs_input` rather than a
    guess. The one capability handler the package ships is installed and
    rooted at the workspace; every other capability a manifest names is
    absent, and a step that reaches for one fails closed.

    When the members' decisions are present, only the Workflows and Skills
    they chose are installed: a manifest sitting in the assets directory that
    nobody selected is not something this device may run."""
    allowed = authorization.allows if authorization is not None else None
    skills = SkillRegistry()
    for manifest in _load_all(layout.skills, SkillManifest):
        if allowed is not None and not allowed("skill", manifest.metadata.identity):
            continue
        try:
            skills.register(manifest)
        except ValueError as error:
            raise HostError("asset_invalid", layout.skills) from error
    workflows = InstalledWorkflows()
    for workflow in _load_all(layout.workflows, WorkflowManifest):
        if allowed is not None and not allowed("workflow", workflow.metadata.identity):
            continue
        try:
            workflows.register(workflow)
        except ValueError as error:
            raise HostError("asset_invalid", layout.workflows) from error
    installed = InstalledCapabilities()
    installed.register(
        READ_FILE_SPEC,
        ReadFileHandler(layout.workspace_root),
        ReadFileInput,
        ReadFileOutput,
        ExecutionDependencies(central_required=False),
    )
    grants = (
        _decided_grants(authorization, installed)
        if authorization is not None
        else _configured_grants(layout)
    )
    try:
        policy = LocalPolicy(grants)
    except ValueError as error:
        raise HostError("grants_invalid", layout.grants) from error
    bridge = BridgeExecutor(installed, policy)
    return Gateway(RequestRouter(CommandRouter(skills)), bridge, WorkflowEngine(workflows, bridge))


def build_telegram(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    agent: LocalAgent,
    resolver: CredentialResolver | None,
) -> TelegramIngress | None:
    """The Telegram ingress, if this host was given one. The token is never
    in the file: the host maps its name to an environment variable, and an
    unmapped name is refused now rather than at the first poll."""
    if not layout.telegram.is_file():
        return None
    ingress_config = _load_one(layout.telegram, TelegramIngressConfig, "telegram_invalid")
    if resolver is None:
        mapped = config.credential_environment()
        if ingress_config.credential.name not in mapped:
            raise HostError("credential_unmapped", layout.telegram)
        resolver = EnvironmentCredentials(mapped)
    try:
        return TelegramIngress(ingress_config, agent, resolver)
    except ValueError as error:
        raise HostError("telegram_invalid", layout.telegram) from error


def build_platform(
    config: CompanyHostConfiguration, resolver: CredentialResolver | None
) -> PlatformClient | None:
    """The shared-platform client, if this host was given a token. As with
    Telegram, the secret's name must be mapped now: a host that would fail
    at its first sync is refused when it is built."""
    if config.platform is None:
        return None
    if resolver is None:
        mapped = config.credential_environment()
        if config.platform.credential.name not in mapped:
            raise HostError("credential_unmapped")
        resolver = EnvironmentCredentials(mapped)
    return PlatformClient(config.platform, resolver)


def inspect_platform(config: CompanyHostConfiguration) -> DoctorCheck:
    """Whether this host could reach a shared platform, read from its
    configuration alone: no socket is opened by a diagnostic."""
    if config.platform is None:
        return DoctorCheck(
            name="platform",
            status="pending",
            detail="no shared platform is configured; this host works locally",
        )
    if config.platform.credential.name not in config.credential_environment():
        return DoctorCheck(
            name="platform",
            status="failed",
            detail="the platform token's secret is not mapped to an environment variable",
        )
    return DoctorCheck(
        name="platform",
        status="passed",
        detail=f"configured for {config.platform.base_url} as {config.platform.token_id}",
    )


def inspect_runtime(
    config: CompanyHostConfiguration, layout: HostLayout
) -> tuple[DoctorCheck, ...]:
    """What this host has been given, read without assembling anything: a
    membership record for this device, the assets it may run, and a state
    file it can open. `pending` is what has not arrived yet; `failed` is
    what arrived and is unusable."""
    membership: DoctorCheck
    if not layout.membership.is_file():
        membership = DoctorCheck(
            name="membership",
            status="pending",
            detail="this Bridge has no membership record yet, so nobody may use it",
        )
    else:
        try:
            load_membership(config, layout)
        except HostError as error:
            membership = DoctorCheck(
                name="membership",
                status="failed",
                detail=f"membership record refused: {error.code}",
            )
        else:
            membership = DoctorCheck(
                name="membership", status="passed", detail="a membership record names this device"
            )
    decided: DeviceAuthorization | None = None
    authorization: DoctorCheck
    try:
        decided = load_authorization(config, layout)
    except HostError as error:
        authorization = DoctorCheck(
            name="authorization",
            status="failed",
            detail=f"the members' decisions cannot be used: {error.code}",
        )
    else:
        authorization = (
            DoctorCheck(
                name="authorization",
                status="passed",
                detail=(
                    f"{len(decided.selections)} decision(s), issued {decided.issued_at.isoformat()}"
                ),
            )
            if decided is not None
            else DoctorCheck(
                name="authorization",
                status="pending",
                detail="no decisions from the shared platform; grants.json configures this host",
            )
        )
    try:
        skills = _load_all(layout.skills, SkillManifest)
        workflows = _load_all(layout.workflows, WorkflowManifest)
    except HostError as error:
        assets = DoctorCheck(
            name="assets", status="failed", detail=f"an asset manifest is unreadable: {error.code}"
        )
    else:
        # Count what this host would actually install, which is what the
        # members chose when they have chosen.
        if decided is not None:
            skills = tuple(
                item for item in skills if decided.allows("skill", item.metadata.identity)
            )
            workflows = tuple(
                item for item in workflows if decided.allows("workflow", item.metadata.identity)
            )
        detail = f"{len(skills)} skill(s) and {len(workflows)} workflow(s) installed"
        assets = DoctorCheck(
            name="assets", status="passed" if skills or workflows else "pending", detail=detail
        )
    state: DoctorCheck
    if not layout.state.is_file():
        # Reporting must not create it: a diagnostic that writes is not a
        # diagnostic. The Agent creates the file the first time it runs.
        state = DoctorCheck(
            name="state",
            status="pending",
            detail="no local state file yet; the resident Agent creates it when it first runs",
        )
    else:
        try:
            # Read-only, so looking at the file changes nothing about it:
            # no table is created and no schema version is migrated.
            with SqliteLocalState(
                layout.state, bridge_id=config.device.bridge_id, read_only=True
            ) as store:
                counted = f"{len(store.installed())} asset(s), {len(store.runs())} run(s) recorded"
            state = DoctorCheck(name="state", status="passed", detail=counted)
        except (LocalStateError, OSError, ValueError) as error:
            state = DoctorCheck(
                name="state",
                status="failed",
                detail=f"the local state file cannot be read: {type(error).__name__}",
            )
    return (membership, authorization, assets, state, inspect_platform(config))


def host_report(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    *,
    system_name: str | None = None,
    python_version: tuple[int, int] | None = None,
    workspace_exists: bool | None = None,
    workspace_writable: bool | None = None,
) -> HostDoctorReport:
    """The device preflight and the runtime readiness in one report, because
    an operator asks one question: can this computer do anything yet?"""
    device = inspect_host(
        config,
        system_name=system_name,
        python_version=python_version,
        workspace_exists=workspace_exists,
        workspace_writable=workspace_writable,
    )
    runtime_checks = inspect_runtime(config, layout)
    # `status` stays what it has always been, this machine's preflight, so a
    # host that is merely not enrolled yet is not reported as a broken
    # installation. What the host was given is `runtime` and the checks
    # themselves: a membership record that is missing or refused, or a state
    # file that cannot be read, keeps the resident Agent pending.
    named = {item.name: item.status for item in runtime_checks}
    # Ready means the Agent would start: this Bridge knows who may use it and
    # nothing it needs is broken. A state file that does not exist yet is not
    # an obstacle, because the Agent creates it on its first run, and neither
    # is the absence of decisions from a shared platform this host may
    # not have.
    broken = {item.name for item in runtime_checks if item.status == "failed"}
    ready = named.get("membership") == "passed" and not broken
    return HostDoctorReport(
        status=device.status,
        checks=device.checks + runtime_checks,
        limitations=device.limitations,
        runtime="ready" if ready else "pending",
    )


def build_runtime(
    config: CompanyHostConfiguration,
    *,
    layout: HostLayout | None = None,
    resolver: CredentialResolver | None = None,
) -> HostRuntime:
    """Assemble this company host, or say which file stopped it."""
    checked = CompanyHostConfiguration.model_validate(config)
    place = layout if layout is not None else HostLayout.under(checked.workspace_root)
    membership = load_membership(checked, place)
    gateway = build_gateway(checked, place, load_authorization(checked, place))
    try:
        state = SqliteLocalState(place.state, bridge_id=checked.device.bridge_id)
    except (LocalStateError, OSError, ValueError) as error:
        raise HostError("state_unavailable", place.state) from error
    try:
        agent = LocalAgent(membership, gateway, state)
        telegram = build_telegram(checked, place, agent, resolver)
        platform = build_platform(checked, resolver)
    except BaseException:
        state.close()
        raise
    return HostRuntime(checked, place, agent, state, telegram, platform)
