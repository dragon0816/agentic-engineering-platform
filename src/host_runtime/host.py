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

import json
from collections.abc import Iterator
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
from common.base import Contract
from common.distribution import LocalStateError
from common.local_agent import BridgeMembership
from host_runtime.agent import LocalAgent
from host_runtime.contracts import CompanyHostConfiguration, DoctorCheck, HostDoctorReport
from host_runtime.runtime import inspect_host
from host_runtime.state import SqliteLocalState
from models.credentials import CredentialResolver, EnvironmentCredentials
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

HostErrorCode = Literal[
    "membership_missing",
    "membership_invalid",
    "membership_mismatch",
    "grants_invalid",
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


class HostLayout(Contract):
    """Where a company host keeps what it needs, all under one workspace, so
    an operator and the installer agree without a second configuration file."""

    workspace_root: Path
    membership: Path
    grants: Path
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
            skills=root / "assets" / "skills",
            workflows=root / "assets" / "workflows",
            telegram=root / "telegram.json",
            state=root / "state.sqlite",
        )


def _documents(path: Path) -> Iterator[object]:
    """Every JSON document in a file, which may hold one or a list of them."""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    yield from payload if isinstance(payload, list) else [payload]


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
            items.extend(model.model_validate(item) for item in _documents(path))
        except (OSError, ValidationError, ValueError) as error:
            raise HostError("asset_invalid", path) from error
    return tuple(items)


class HostRuntime:
    """One assembled company host: its Agent, its durable state and, when the
    operator configured one, its Telegram ingress. Closing it closes the
    state file, which on Windows would otherwise stay pinned."""

    def __init__(
        self,
        config: CompanyHostConfiguration,
        layout: HostLayout,
        agent: LocalAgent,
        state: SqliteLocalState,
        telegram: TelegramIngress | None,
    ) -> None:
        self.config = config
        self.layout = layout
        self.agent = agent
        self.state = state
        self.telegram = telegram

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


def build_gateway(config: CompanyHostConfiguration, layout: HostLayout) -> Gateway:
    """The platform's own wiring, with what this host was given.

    Routing is deterministic only: no model is configured on a company host
    in this slice, so an unrecognized message is `needs_input` rather than a
    guess. The one capability handler the package ships is installed and
    rooted at the workspace; every other capability a manifest names is
    absent, and a step that reaches for one fails closed."""
    skills = SkillRegistry()
    for manifest in _load_all(layout.skills, SkillManifest):
        try:
            skills.register(manifest)
        except ValueError as error:
            raise HostError("asset_invalid", layout.skills) from error
    workflows = InstalledWorkflows()
    for workflow in _load_all(layout.workflows, WorkflowManifest):
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
    grants: tuple[CapabilityGrant, ...] = ()
    if layout.grants.is_file():
        try:
            grants = tuple(
                CapabilityGrant.model_validate(item) for item in _documents(layout.grants)
            )
        except (OSError, ValidationError, ValueError) as error:
            raise HostError("grants_invalid", layout.grants) from error
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
    try:
        skills = _load_all(layout.skills, SkillManifest)
        workflows = _load_all(layout.workflows, WorkflowManifest)
    except HostError as error:
        assets = DoctorCheck(
            name="assets", status="failed", detail=f"an asset manifest is unreadable: {error.code}"
        )
    else:
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
            with SqliteLocalState(layout.state, bridge_id=config.device.bridge_id) as store:
                counted = f"{len(store.installed())} asset(s), {len(store.runs())} run(s) recorded"
            state = DoctorCheck(name="state", status="passed", detail=counted)
        except (LocalStateError, OSError, ValueError) as error:
            state = DoctorCheck(
                name="state",
                status="failed",
                detail=f"the local state file cannot be opened: {type(error).__name__}",
            )
    return (membership, assets, state)


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
    checks = device.checks + inspect_runtime(config, layout)
    failed = any(item.status == "failed" for item in checks)
    # A host is ready to run when it knows who may use it and nothing is
    # broken. A state file that does not exist yet is not an obstacle: the
    # Agent creates it.
    runtime_pending = failed or any(
        item.status != "passed" for item in checks if item.name == "membership"
    )
    return HostDoctorReport(
        status="not_ready" if failed else device.status,
        checks=checks,
        limitations=device.limitations,
        runtime="pending" if runtime_pending else "ready",
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
    gateway = build_gateway(checked, place)
    try:
        state = SqliteLocalState(place.state, bridge_id=checked.device.bridge_id)
    except (LocalStateError, OSError) as error:
        raise HostError("state_unavailable", place.state) from error
    try:
        agent = LocalAgent(membership, gateway, state)
        telegram = build_telegram(checked, place, agent, resolver)
    except BaseException:
        state.close()
        raise
    return HostRuntime(checked, place, agent, state, telegram)
