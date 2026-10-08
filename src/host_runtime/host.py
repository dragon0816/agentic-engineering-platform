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

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from types import TracebackType
from typing import Literal, Self, TypeVar

from pydantic import JsonValue, ValidationError

from agent.backends.gateway import GatewayModelBackend
from agent.contracts import AgentProfile
from agent.data_policy import DataPolicy
from agent.gateway import Gateway, KnowledgeVaultTool
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from agent.task_execution import GatewayTaskExecutor
from capabilities.browser_session.handlers import SPEC as BROWSER_SPEC
from capabilities.browser_session.handlers import (
    BrowserRequest,
    BrowserResult,
    BrowserSessionHandler,
)
from capabilities.chipset_report.apply import ChipsetApplyHandler, ChipsetWorkbookWriter
from capabilities.chipset_report.contracts import (
    ChipsetApplied,
    ChipsetApplyInput,
    ChipsetPreview,
    ChipsetPreviewStepInput,
)
from capabilities.chipset_report.manifest import APPLY_SPEC as CHIPSET_APPLY_SPEC
from capabilities.chipset_report.manifest import PREVIEW_SPEC as CHIPSET_PREVIEW_SPEC
from capabilities.chipset_report.preview import ChipsetPreviewHandler
from capabilities.coding_change.contracts import CodingChangeResult, CodingChangeStepInput
from capabilities.coding_change.handlers import CodingChangeHandler
from capabilities.coding_change.manifest import CHANGE_SPEC as CODING_CHANGE_SPEC
from capabilities.coding_change.manifest import REPOSITORIES_FUNCTION as CODING_REPOSITORIES
from capabilities.coding_change.manifest import coding_skill
from capabilities.coding_change.run_python import RUN_SPEC as CODING_RUN_SPEC
from capabilities.coding_change.run_python import (
    RunPythonHandler,
    RunPythonResult,
    RunPythonStepInput,
)
from capabilities.coding_change.workspaces import workspace_note
from capabilities.company_agent.manifest import personal_proof_fixture_read_spec
from capabilities.desktop_session.handlers import SPEC as DESKTOP_SPEC
from capabilities.desktop_session.handlers import (
    DesktopRequest,
    DesktopResult,
    DesktopSessionHandler,
)
from capabilities.dut_engineering.handlers import (
    DUT_PHYSICAL_VALIDATE_SPEC,
    PhysicalDutValidationHandler,
)
from capabilities.excel_blocks.handlers import READ_SHEET_SPEC as EXCEL_READ_SHEET_SPEC
from capabilities.excel_blocks.handlers import UPSERT_SPEC as EXCEL_UPSERT_SPEC
from capabilities.excel_blocks.handlers import (
    ReadSheetHandler,
    ReadSheetRequest,
    SheetRows,
    UpsertHandler,
    UpsertRequest,
    UpsertResult,
)
from capabilities.files import READ_FILE_SPEC, ReadFileHandler, ReadFileInput, ReadFileOutput
from capabilities.knowledge_query.handlers import (
    KNOWLEDGE_QUERY_SPEC,
    MARKET_MATRIX_SPEC,
    KnowledgeQueryHandler,
    MarketMatrixHandler,
)
from capabilities.mail_draft.handlers import DRAFT_SPEC as MAIL_DRAFT_SPEC
from capabilities.mail_draft.handlers import MailDraftHandler, MailDraftRequest, MailDraftResult
from capabilities.ncc_plan.contracts import (
    NccPlan,
    NccPlanStepInput,
    NccRendered,
    NccRenderStepInput,
)
from capabilities.ncc_plan.handlers import NccPrepareHandler, NccRenderHandler
from capabilities.ncc_plan.manifest import PREPARE_SPEC as NCC_PREPARE_SPEC
from capabilities.ncc_plan.manifest import RENDER_SPEC as NCC_RENDER_SPEC
from capabilities.ncc_plan.manifest import STATIONS_FUNCTION as NCC_STATIONS_FUNCTION
from capabilities.ncc_plan.planning import station_choices
from capabilities.release_package.apply_isolated import IsolatedApplyHandler
from capabilities.release_package.contracts import (
    IsolatedApplyOutput,
    IsolatedApplyStepInput,
    ReleasePreview,
    ReleasePreviewStepInput,
)
from capabilities.release_package.manifest import COMMIT_SPEC as RELEASE_COMMIT_SPEC
from capabilities.release_package.manifest import ISOLATED_APPLY as ISOLATED_APPLY_WORKFLOW
from capabilities.release_package.manifest import ISOLATED_APPLY_SPEC
from capabilities.release_package.manifest import PREPARE_SPEC as RELEASE_PREPARE_SPEC
from capabilities.release_package.manifest import PREVIEW as RELEASE_PREVIEW_WORKFLOW
from capabilities.release_package.manifest import PREVIEW_SPEC as RELEASE_PREVIEW_SPEC
from capabilities.release_package.preview import ReleasePreviewHandler
from capabilities.release_package.release_run import (
    CommitHandler,
    CommitResult,
    CommitStepInput,
    PreparedRelease,
    PrepareHandler,
    PrepareStepInput,
)
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.script_tools import (
    ScriptToolHandler,
    ScriptToolInput,
    ScriptToolOutput,
    load_script_tools,
)
from capabilities.team_tickets.contracts import TeamTicketsPreview
from capabilities.team_tickets.handlers import (
    PREVIEW_SPEC as TEAM_TICKETS_PREVIEW_SPEC,
)
from capabilities.team_tickets.handlers import TeamTicketsPreviewHandler, TeamTicketsPreviewInput
from capabilities.web.handlers import ACT_SPEC as WEB_ACT_SPEC
from capabilities.web.handlers import READ_SPEC as WEB_READ_SPEC
from capabilities.web.handlers import SELECT_SPEC as DATA_SELECT_SPEC
from capabilities.web.handlers import SelectHandler, SelectRequest, SelectResult, WebScriptHandler
from capabilities.weekly_report.contracts import (
    ReportingWindow,
    SheetState,
    WeeklyMailDrafted,
    WeeklyReportApplied,
    WeeklyReportPlan,
)
from capabilities.weekly_report.handlers import (
    APPLY_SPEC,
    MAIL_SPEC,
    PLAN_SPEC,
    PROJECT_SEARCH_SPEC,
    READ_SCRATCH_SHEET_SPEC,
    RESOLVE_WINDOW_SPEC,
    ApplyHandler,
    ApplyInput,
    MailHandler,
    MailInput,
    PlanHandler,
    PlanInput,
    ProjectSearchHandler,
    ProjectSearchInput,
    ProjectSearchOutput,
    ReadScratchSheetHandler,
    ReadScratchSheetInput,
    ResolveWindowHandler,
    ResolveWindowInput,
)
from capabilities.workflow_author.contracts import DraftWorkflowRequest, WorkflowDraft
from capabilities.workflow_author.handlers import DRAFT_SPEC, DraftWorkflowHandler
from channels.telegram import TelegramIngress, TelegramIngressConfig
from common.assets import AssetIdentity, ExecutionDependencies, WorkflowManifest, WorkflowStep
from common.authorization import DeviceAuthorization
from common.base import Contract
from common.distribution import LocalStateError
from common.execution import Failure, TraceIdentifiers
from common.local_agent import BridgeMembership
from dut.adapters import DutAdapter, SubprocessDutAdapter
from dut.contracts import DutPhysicalValidationRequest, DutValidationEvidence
from dut.runtime import PhysicalDutValidationService
from harness.network_block import create_rule_command, outbound_rule_present
from harness.restricted_runner import (
    RestrictedRunner,
    RunnerError,
    RunnerLimits,
    is_venv_launcher,
)
from host_runtime.agent import LocalAgent
from host_runtime.attachments import AttachmentStore
from host_runtime.bridge_tools import bridge_tools
from host_runtime.chat_authoring import ChatAuthoring
from host_runtime.choice_sources import ChoiceFunction, ChoiceSources
from host_runtime.contracts import (
    CompanyHostConfiguration,
    DoctorCheck,
    HostDoctorReport,
    KnowledgeHostBinding,
)

# Re-exported: the layout moved to the contracts module so the platform client
# can take one without importing this module, and callers still find it here.
from host_runtime.contracts import HostLayout as HostLayout
from host_runtime.jev_shadow import SHADOW_LOG_FILE, JevShadowLog, skill_accelerator
from host_runtime.profiles import ProfileError, load_active_profile
from host_runtime.reference_sets import REFERENCE_SETS_FILE, ReferenceItem, ReferenceSetStore
from host_runtime.runtime import inspect_host
from host_runtime.state import SqliteLocalState
from host_runtime.sync import PlatformClient
from host_runtime.task_artifacts import LocalTaskArtifacts
from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore, settings_key
from host_runtime.workspace import documents
from integrations import excel
from integrations.chipset_excel import ChipsetExcelWriter
from integrations.excel_writer import (
    ExcelComWriter,
    WorkbookWriteError,
    WorkbookWriter,
    require_com,
)
from integrations.github_project import GitHubProjectClient
from integrations.jira import JiraClient
from integrations.outlook_draft import DraftError, DraftWriter, OutlookComDraft
from integrations.outlook_draft import require_com as require_outlook
from integrations.web_script import WebScript, WebScriptResult
from knowledge.evolution import (
    KnowledgeAnswerRecord,
    KnowledgeCatalog,
    KnowledgeManifest,
    KnowledgeQueryRequest,
)
from knowledge.market_matrix import MarketMatrixRecord, MarketMatrixRequest
from knowledge.vault import Vault, VaultError
from models.approved import ApprovedModelClient
from models.clients import ModelClients
from models.contracts import ModelClient
from models.credentials import CredentialResolver, EnvironmentCredentials
from models.wire import MethodTransport, Transport
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine
from workflow.host_bridge import BridgeRegistration, LocalResource

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
    "models_invalid",
    "knowledge_invalid",
    "profile_invalid",
    "state_unavailable",
    "dut_skill_missing",
    "dut_driver_missing",
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


def _ncc_stations(
    settings: Mapping[str, JsonValue], arguments: Mapping[str, str]
) -> list[ReferenceItem]:
    """Workflow 14's station menu, read from the catalogue its settings name."""
    catalogue = str(settings.get("catalogue_file") or "").strip()
    if not catalogue:
        raise ValueError("catalogue_file is not set")
    return [ReferenceItem(value=value, label=label) for value, label in station_choices(catalogue)]


#: Read-only `fn:` choice functions by name (see `host_runtime.choice_sources`).
CHOICE_FUNCTIONS: dict[str, ChoiceFunction] = {NCC_STATIONS_FUNCTION: _ncc_stations}


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
        chat_authoring: ChatAuthoring | None = None,
    ) -> None:
        self.config = config
        self.layout = layout
        self.agent = agent
        self.state = state
        self.telegram = telegram
        self.platform = platform
        self.chat_authoring = chat_authoring

    @property
    def actor(self) -> str:
        """Who this host acts as unless the operator names someone else: the
        platform user the device was registered by."""
        return self.config.device.registered_by

    def close(self) -> None:
        # The Agent's own Edge and launched desktop applications end with the host.
        for spec in (BROWSER_SPEC, DESKTOP_SPEC):
            binding = self.agent.gateway.bridge.installed.get(spec.identity)
            closing = getattr(binding.handler, "close", None) if binding is not None else None
            if closing is not None:
                try:
                    closing()
                except Exception:  # noqa: BLE001 - shutting down continues regardless
                    pass
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


def _target_name(step: AssetIdentity | WorkflowStep) -> tuple[str, str, str]:
    return (step.capability if isinstance(step, WorkflowStep) else step).key


def build_integrations(
    config: CompanyHostConfiguration,
    installed: InstalledCapabilities,
    resolver: CredentialResolver | None,
    *,
    layout: HostLayout,
    jira_transport: MethodTransport | None = None,
    writer: Callable[[], WorkbookWriter] | None = None,
    chipset_writer: Callable[[], ChipsetWorkbookWriter] | None = None,
    drafter: Callable[[], DraftWriter] | None = None,
) -> None:
    """The capabilities the migrated workflows need, from what this host was
    given. Jira's token is resolved through the host's credential mapping at
    every call and never held; a name nothing is mapped to is refused now,
    not at the first fetch. The weekly report's steps that need no board are
    installed whenever its settings are, so a preview against the workbook
    alone still runs."""
    # Workflow 13's paths are per-install Workflow settings now; a run without
    # them is stopped by the engine, and the Bridge grant still decides use.
    # Its capabilities exist when this host installed a Workflow that uses
    # them, or still configures them the old way in host.json.
    uses = {
        _target_name(step)
        for workflow in _load_all(layout.workflows, WorkflowManifest)
        for step in workflow.steps
    }
    legacy = config.integrations
    if RELEASE_PREVIEW_SPEC.identity.key in uses or (
        legacy is not None and legacy.release_package is not None
    ):
        installed.register(
            RELEASE_PREVIEW_SPEC,
            ReleasePreviewHandler(),
            ReleasePreviewStepInput,
            ReleasePreview,
            ExecutionDependencies(central_required=False),
        )
    if ISOLATED_APPLY_SPEC.identity.key in uses or (
        legacy is not None and legacy.isolated_release_apply is not None
    ):
        installed.register(
            ISOLATED_APPLY_SPEC,
            IsolatedApplyHandler(),
            IsolatedApplyStepInput,
            IsolatedApplyOutput,
            ExecutionDependencies(central_required=False),
        )
    # Workflow 13's release run up to the commit (owner 2026-10-08): two
    # approved runs, isolated root only until push is approved.
    if RELEASE_PREPARE_SPEC.identity.key in uses:
        installed.register(
            RELEASE_PREPARE_SPEC, PrepareHandler(), PrepareStepInput, PreparedRelease,
            ExecutionDependencies(central_required=False),
        )
    if RELEASE_COMMIT_SPEC.identity.key in uses:
        installed.register(
            RELEASE_COMMIT_SPEC, CommitHandler(), CommitStepInput, CommitResult,
            ExecutionDependencies(central_required=False),
        )
    # Workflow 14: its paths are per-install Workflow settings.
    if NCC_PREPARE_SPEC.identity.key in uses:
        installed.register(
            NCC_PREPARE_SPEC, NccPrepareHandler(), NccPlanStepInput, NccPlan,
            ExecutionDependencies(central_required=False),
        )
    if NCC_RENDER_SPEC.identity.key in uses:
        installed.register(
            NCC_RENDER_SPEC, NccRenderHandler(), NccRenderStepInput, NccRendered,
            ExecutionDependencies(central_required=False),
        )
    # Web and data building blocks for generated Workflows.
    if config.web is not None:
        profile = (
            Path(config.web.profile_dir) if config.web.profile_dir
            else layout.workspace_root / "web-profile"
        )
        for spec, mode in ((WEB_READ_SPEC, "read"), (WEB_ACT_SPEC, "act")):
            installed.register(
                spec, WebScriptHandler(config.web, profile, mode),  # type: ignore[arg-type]
                WebScript, WebScriptResult, ExecutionDependencies(central_required=False),
            )
        # The Agent's own Edge for a task (lab gap L1): kept open between calls,
        # in a profile apart from the Workflow steps' so neither locks the other.
        installed.register(
            BROWSER_SPEC,
            BrowserSessionHandler(
                config.web.allowed_origins, layout.workspace_root / "browser-profile",
                headless=config.web.headless, timeout_s=float(config.web.timeout_seconds),
                workspace_roots=config.coding.workspace_roots if config.coding else (),
            ),
            BrowserRequest, BrowserResult, ExecutionDependencies(central_required=False),
        )
    # Registered desktop applications the Agent may operate (lab gap L2).
    if config.desktop is not None:
        desktop = config.desktop
        if not desktop.workspace_roots and config.coding is not None:
            desktop = desktop.model_copy(
                update={"workspace_roots": config.coding.workspace_roots})
        installed.register(
            DESKTOP_SPEC,
            DesktopSessionHandler(desktop, layout.workspace_root / "desktop-tool"),
            DesktopRequest, DesktopResult, ExecutionDependencies(central_required=False),
        )
    # Data and Excel blocks: installed when a Workflow uses them, or when this
    # host turned on web steps for generated Workflows (`web` in host.json).
    generated = config.web is not None
    if generated or DATA_SELECT_SPEC.identity.key in uses:
        installed.register(
            DATA_SELECT_SPEC, SelectHandler(), SelectRequest, SelectResult,
            ExecutionDependencies(central_required=False),
        )
    if generated or EXCEL_READ_SHEET_SPEC.identity.key in uses:
        installed.register(
            EXCEL_READ_SHEET_SPEC, ReadSheetHandler(), ReadSheetRequest, SheetRows,
            ExecutionDependencies(central_required=False),
        )
    if generated or EXCEL_UPSERT_SPEC.identity.key in uses:
        installed.register(
            EXCEL_UPSERT_SPEC, UpsertHandler(layout.workspace_root / "excel-backups"),
            UpsertRequest, UpsertResult, ExecutionDependencies(central_required=False),
        )
    # The Outlook draft building block: installed when a Workflow uses it.
    if MAIL_DRAFT_SPEC.identity.key in uses:
        installed.register(
            MAIL_DRAFT_SPEC,
            MailDraftHandler(drafter if drafter is not None else OutlookComDraft),
            MailDraftRequest,
            MailDraftResult,
            ExecutionDependencies(central_required=False),
        )
    integrations = config.integrations
    if integrations is None:
        return
    settings = integrations.weekly_report
    if integrations.chipset_report is not None:
        installed.register(
            CHIPSET_PREVIEW_SPEC,
            ChipsetPreviewHandler(
                integrations.chipset_report, state_dir=layout.workspace_root / "state"
            ),
            ChipsetPreviewStepInput,
            ChipsetPreview,
            ExecutionDependencies(central_required=False),
        )
        installed.register(
            CHIPSET_APPLY_SPEC,
            ChipsetApplyHandler(
                integrations.chipset_report,
                chipset_writer if chipset_writer is not None else ChipsetExcelWriter,
                staging_root=layout.workspace_root,
                state_dir=layout.workspace_root / "state",
            ),
            ChipsetApplyInput,
            ChipsetApplied,
            ExecutionDependencies(central_required=False),
        )
    if integrations.github_project is not None:
        if resolver is None:
            mapped = config.credential_environment()
            if integrations.github_project.credential.name not in mapped:
                raise HostError("credential_unmapped")
            resolver = EnvironmentCredentials(mapped)
        client = GitHubProjectClient(
            integrations.github_project, resolver, transport=jira_transport
        )
        if settings is not None:
            installed.register(
                PROJECT_SEARCH_SPEC,
                ProjectSearchHandler(client, settings),
                ProjectSearchInput,
                ProjectSearchOutput,
                ExecutionDependencies(central_required=False),
            )
    if integrations.team_tickets is not None and integrations.jira is not None:
        if resolver is None:
            mapped = config.credential_environment()
            if integrations.jira.credential.name not in mapped:
                raise HostError("credential_unmapped")
            resolver = EnvironmentCredentials(mapped)
        jira_client = JiraClient(integrations.jira, resolver, transport=jira_transport)
        installed.register(
            TEAM_TICKETS_PREVIEW_SPEC,
            TeamTicketsPreviewHandler(jira_client, integrations.team_tickets),
            TeamTicketsPreviewInput,
            TeamTicketsPreview,
            ExecutionDependencies(central_required=False),
        )
    if settings is not None:
        installed.register(
            RESOLVE_WINDOW_SPEC,
            ResolveWindowHandler(settings),
            ResolveWindowInput,
            ReportingWindow,
            ExecutionDependencies(central_required=False),
        )
        installed.register(
            READ_SCRATCH_SHEET_SPEC,
            ReadScratchSheetHandler(settings),
            ReadScratchSheetInput,
            SheetState,
            ExecutionDependencies(central_required=False),
        )
        installed.register(
            PLAN_SPEC,
            PlanHandler(settings),
            PlanInput,
            WeeklyReportPlan,
            ExecutionDependencies(central_required=False),
        )
        # The writer is built per run, so a host without Excel still installs
        # the capability and refuses at the write with `library_missing`
        # rather than failing to assemble at all.
        installed.register(
            APPLY_SPEC,
            ApplyHandler(
                settings,
                writer if writer is not None else ExcelComWriter,
                staging_root=layout.workspace_root,
            ),
            ApplyInput,
            WeeklyReportApplied,
            ExecutionDependencies(central_required=False),
        )
        # The same arrangement for Outlook: built per run, so a host without
        # it installs the capability and refuses at the draft rather than
        # failing to assemble. The chart is written under the workspace,
        # beside everything else this host produces.
        installed.register(
            MAIL_SPEC,
            MailHandler(
                settings,
                drafter if drafter is not None else OutlookComDraft,
                chart_root=layout.workspace_root / "weekly-mail",
            ),
            MailInput,
            WeeklyMailDrafted,
            ExecutionDependencies(central_required=False),
        )


def build_dut(
    config: CompanyHostConfiguration,
    installed: InstalledCapabilities,
    skills: SkillRegistry,
    membership: BridgeMembership,
    *,
    adapter: DutAdapter | None = None,
) -> None:
    """Install the physical DUT boundary only from trusted host configuration."""
    binding = config.dut
    if binding is None:
        return
    installed_skill = next(
        (
            item.metadata.identity
            for item in skills.discover(binding.skill.namespace)
            if item.metadata.identity == binding.skill
        ),
        None,
    )
    if installed_skill is None:
        raise HostError("dut_skill_missing")
    if (
        binding.physical_enabled
        and adapter is None
        and not Path(binding.driver.executable).is_file()
    ):
        raise HostError("dut_driver_missing", Path(binding.driver.executable))
    selected: DutAdapter = adapter if adapter is not None else SubprocessDutAdapter(binding.driver)
    resources = [
        LocalResource(
            resource_id=binding.target.resource_id,
            kind="dut",
            available=binding.device_available,
        )
    ]
    if binding.instrument is not None:
        resources.append(
            LocalResource(
                resource_id=binding.instrument.resource_id,
                kind="instrument",
                available=binding.instrument_available,
            )
        )
    registration = BridgeRegistration(
        bridge_id=config.device.bridge_id,
        owner_id=config.device.registered_by,
        trace=TraceIdentifiers(
            trace_id="dut-host-config",
            request_id="dut-host-config",
            span_id="dut-host-config",
        ),
        capabilities=(DUT_PHYSICAL_VALIDATE_SPEC,),
        local_resources=tuple(resources),
    )
    installed.register(
        DUT_PHYSICAL_VALIDATE_SPEC,
        PhysicalDutValidationHandler(
            PhysicalDutValidationService(
                membership,
                registration,
                installed_skill=installed_skill,
                adapter=selected,
                physical_enabled=binding.physical_enabled,
                installed_target=binding.target,
                installed_instrument=binding.instrument,
            )
        ),
        DutPhysicalValidationRequest,
        DutValidationEvidence,
        ExecutionDependencies(central_required=False),
    )


def build_gateway(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None = None,
    *,
    resolver: CredentialResolver | None = None,
    jira_transport: MethodTransport | None = None,
    writer: Callable[[], WorkbookWriter] | None = None,
    chipset_writer: Callable[[], ChipsetWorkbookWriter] | None = None,
    drafter: Callable[[], DraftWriter] | None = None,
    model_transport: Transport | None = None,
    membership: BridgeMembership | None = None,
    dut_adapter: DutAdapter | None = None,
) -> Gateway:
    """The platform's own wiring, with what this host was given.

    Routing is deterministic only: no model is configured on a company host
    in this slice, so an unrecognized message is `needs_input` rather than a
    guess. Built-in handlers are installed only when their trusted local
    configuration is present; every other capability a manifest names is
    absent, and a step that reaches for one fails closed.

    When the members' decisions are present, only the Workflows and Skills
    they chose are installed: a manifest sitting in the assets directory that
    nobody selected is not something this device may run."""
    allowed = authorization.allows if authorization is not None else None
    try:
        profile = load_active_profile(
            config,
            layout,
            authorization,
            actor=config.device.registered_by,
        )
    except ProfileError as error:
        raise HostError("profile_invalid", layout.active_profile) from error
    profile_skills = None if profile is None else {item.key for item in profile.skills}
    skills = SkillRegistry()
    for manifest in _load_all(layout.skills, SkillManifest):
        if allowed is not None and not allowed("skill", manifest.metadata.identity):
            continue
        if profile_skills is not None and manifest.metadata.identity.key not in profile_skills:
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
    proof_fixture_root = layout.workspace_root / "hermes-fixtures" / "personal-proof"
    installed.register(
        personal_proof_fixture_read_spec(),
        ReadFileHandler(proof_fixture_root),
        ReadFileInput,
        ReadFileOutput,
        ExecutionDependencies(central_required=False),
    )
    try:
        script_tools = load_script_tools(layout.script_tools)
        for tool in script_tools:
            script_manifest = tool.manifest
            if allowed is not None and not allowed("capability", script_manifest.metadata.identity):
                continue
            installed.register(
                script_manifest.capability,
                ScriptToolHandler(tool),
                ScriptToolInput,
                ScriptToolOutput,
                script_manifest.dependencies,
                script_manifest.secrets,
            )
    except (OSError, ValidationError, ValueError) as error:
        raise HostError("asset_invalid", layout.script_tools) from error
    build_integrations(
        config,
        installed,
        resolver,
        layout=layout,
        jira_transport=jira_transport,
        writer=writer,
        chipset_writer=chipset_writer,
        drafter=drafter,
    )
    if config.dut is not None:
        active_membership = (
            membership if membership is not None else load_membership(config, layout)
        )
        build_dut(config, installed, skills, active_membership, adapter=dut_adapter)
    # Registered last, and holding the registry it is in: what a Workflow may
    # be drafted from is whatever this machine ended up with, read per call.
    # A host with no model still installs it, so that "why can I not draft"
    # is answered by a sentence rather than by a missing capability.
    binding = config.models
    drafting_model: ModelClient | None = None
    if binding is not None and binding.routing_alias is not None:
        # The router creates a default environment resolver inside
        # build_router, but Knowledge and Workflow drafting are assembled
        # earlier. They must see the same host-owned credential mapping.
        model_resolver = resolver or EnvironmentCredentials(config.credential_environment())
        chosen = ModelClients(
            binding.catalog,
            resolver=model_resolver,
            transport=model_transport,
            options=binding.options,
        ).for_alias(binding.routing_alias)
        drafting_model = (
            None
            if isinstance(chosen, Failure)
            else ApprovedModelClient(chosen, binding.data_approval)
        )
    installed.register(
        DRAFT_SPEC,
        DraftWorkflowHandler(
            installed,
            model=drafting_model,
            model_alias=(
                binding.routing_alias
                if binding is not None and binding.routing_alias is not None
                else "routing"
            ),
            local_only=binding.require_local_model if binding is not None else False,
            workspace_root=layout.workspace_root,
        ),
        DraftWorkflowRequest,
        WorkflowDraft,
        ExecutionDependencies(central_required=False),
    )
    if config.coding is not None and config.coding.workspace_roots:
        installed.register(
            CODING_RUN_SPEC, RunPythonHandler(config.coding), RunPythonStepInput,
            RunPythonResult, ExecutionDependencies(central_required=False),
        )
    if config.coding is not None:
        installed.register(
            CODING_CHANGE_SPEC,
            CodingChangeHandler(
                config.coding,
                layout.workspace_root / "coding-runs",
                model=drafting_model,
                model_alias=(
                    binding.routing_alias
                    if binding is not None and binding.routing_alias is not None
                    else "routing"
                ),
                local_only=binding.require_local_model if binding is not None else False,
            ),
            CodingChangeStepInput,
            CodingChangeResult,
            ExecutionDependencies(central_required=False),
        )
    selected_knowledge = (
        ()
        if authorization is None
        else tuple(item for item in authorization.selections if item.kind == "knowledge")
    )
    knowledge_catalog: KnowledgeCatalog | None = None
    if config.knowledge or selected_knowledge:
        model_ready = (
            drafting_model is not None and binding is not None and binding.routing_alias is not None
        )
        try:
            catalog = build_knowledge_catalog(config, layout, authorization, profile=profile)
        except HostError as error:
            # A partially configured Knowledge binding did not block Settings
            # or Workflows before a model existed. Keep that setup behavior;
            # the offline matrix becomes available once the asset is valid.
            if model_ready or error.code != "knowledge_invalid":
                raise
            catalog = None
        if catalog is not None:
            installed.register(
                MARKET_MATRIX_SPEC,
                MarketMatrixHandler(catalog),
                MarketMatrixRequest,
                MarketMatrixRecord,
                ExecutionDependencies(central_required=False),
            )
            if model_ready and drafting_model is not None and binding is not None:
                assert binding.routing_alias is not None
                knowledge_catalog = catalog
                installed.register(
                    KNOWLEDGE_QUERY_SPEC,
                    KnowledgeQueryHandler(catalog, drafting_model, alias=binding.routing_alias),
                    KnowledgeQueryRequest,
                    KnowledgeAnswerRecord,
                    ExecutionDependencies(central_required=False),
                )
    # Derive policy only after every configured built-in capability is in the
    # registry. A selected Knowledge query or workflow-author capability must
    # not disappear merely because its handler is assembled from local model
    # configuration later than the filesystem and integration handlers.
    grants = (
        _decided_grants(authorization, installed)
        if authorization is not None
        else _configured_grants(layout)
    )
    if profile is not None:
        permitted = {item.key for item in profile.allowed_capabilities}
        grants = tuple(item for item in grants if item.asset.key in permitted)
    try:
        policy = LocalPolicy(grants)
    except ValueError as error:
        raise HostError("grants_invalid", layout.grants) from error
    bridge = BridgeExecutor(installed, policy, timeout_seconds=config.capability_timeout_seconds)
    router = build_router(
        config, CommandRouter(skills), resolver=resolver, transport=model_transport
    )
    # JEV Skill selection: absent unless configured, sends nothing without the
    # owner's egress approval, and in shadow mode only records its choices.
    accelerator = config.decision_accelerator
    if (
        resolver is None and accelerator.credential is not None
        and accelerator.credential.name not in config.credential_environment()
    ):
        raise HostError("credential_unmapped")
    factory, authorize = skill_accelerator(
        accelerator,
        resolver if resolver is not None else EnvironmentCredentials(
            config.credential_environment()
        ),
    )
    shadow_log = (
        JevShadowLog(layout.workspace_root / SHADOW_LOG_FILE)
        if factory is not None and accelerator.mode == "shadow" else None
    )
    return Gateway(
        router, bridge,
        WorkflowEngine(
            workflows, bridge,
            settings_provider=workflow_settings_provider(config, layout),
            choices_provider=choice_sources(config, layout).values,
        ),
        skill_accelerator=factory,
        skill_authorizer=authorize,
        skill_shadow_observer=None if shadow_log is None else shadow_log.decision,
        conversation_observer=None if shadow_log is None else shadow_log.conversation,
        knowledge_vaults=(
            None if knowledge_catalog is None else _vault_tools(knowledge_catalog)
        ),
        knowledge_capability=KNOWLEDGE_QUERY_SPEC.identity,
        knowledge_procedure=_harness_knowledge_procedure(router.commands.skills),
        accelerator_excluded_aliases=frozenset({coding_skill().alias}),
        workspace_note=workspace_note(
            () if config.coding is None else tuple(config.coding.workspace_roots)),
    )


def _harness_knowledge_procedure(
    skills: SkillRegistry,
) -> Callable[[], dict[str, JsonValue] | None]:
    """The procedure of the one Knowledge Skill the direct Knowledge route uses
    (validated or published, a knowledge harness domain, a command on the
    Knowledge query capability), so the conversation tool route asks the vault
    the same way. None when there is not exactly one."""

    def procedure() -> dict[str, JsonValue] | None:
        found = [
            item for item in skills.manifests()
            if item.procedure
            and item.metadata.lifecycle in {"validated", "published"}
            and item.harness_guidance is not None
            and "knowledge" in item.harness_guidance.domains
            and any(
                command.kind == "capability" and command.target == KNOWLEDGE_QUERY_SPEC.identity
                for command in item.commands
            )
        ]
        return found[0].procedure if len(found) == 1 else None

    return procedure


def _vault_tools(catalog: KnowledgeCatalog) -> Callable[[], list[KnowledgeVaultTool]]:
    """Each queryable vault as the Agent offers it, from the vault's own
    manifest. A vault published before `purpose` existed is described by its
    domain until a new version says more."""

    def tools() -> list[KnowledgeVaultTool]:
        return [
            KnowledgeVaultTool(
                asset=manifest.metadata.identity,
                purpose=manifest.purpose or f"the {manifest.domain} knowledge domain",
                boundaries=manifest.boundaries,
            )
            for manifest in catalog.manifests()
        ]

    return tools


def workflow_settings_provider(
    config: CompanyHostConfiguration, layout: HostLayout
) -> Callable[[WorkflowManifest], dict[str, JsonValue]]:
    """A Workflow's per-install settings, read from the store on every call."""
    settings = WorkflowSettingsStore(layout.workspace_root / SETTINGS_FILE)
    legacy = legacy_workflow_settings(config)

    def provide(manifest: WorkflowManifest) -> dict[str, JsonValue]:
        # Values set on the settings page win over a host.json written before
        # Workflow settings existed, which keeps an existing install working.
        fallback = legacy.get(settings_key(manifest.metadata.identity), {})
        declared = {field.name for field in manifest.parameters if field.scope == "static"}
        return {
            **{name: value for name, value in fallback.items() if name in declared},
            **settings.for_manifest(manifest),
        }

    return provide


def choice_sources(config: CompanyHostConfiguration, layout: HostLayout) -> ChoiceSources:
    """`ref:` sets and the read-only `fn:` choice functions this host offers;
    the engine, Agent Web and Telegram all resolve choices through this."""
    functions = dict(CHOICE_FUNCTIONS)
    coding = config.coding
    if coding is not None:
        # The repositories come from trusted host configuration, not from a
        # Workflow's settings, so this one is bound to the host here.
        functions[CODING_REPOSITORIES] = lambda _settings, _arguments: [
            ReferenceItem(value=item.name, label=f"{item.name} ({item.path})")
            for item in coding.repositories
        ]
    return ChoiceSources(
        ReferenceSetStore(layout.workspace_root / REFERENCE_SETS_FILE),
        workflow_settings_provider(config, layout),
        functions,
    )


def legacy_workflow_settings(config: CompanyHostConfiguration) -> dict[str, dict[str, JsonValue]]:
    """Workflow settings a host.json carried as `integrations` members before
    per-install Workflow settings existed (Workflow 13's checkout and inbox)."""
    integrations = config.integrations
    found: dict[str, dict[str, JsonValue]] = {}
    if integrations is None:
        return found
    if integrations.release_package is not None:
        found[settings_key(RELEASE_PREVIEW_WORKFLOW)] = integrations.release_package.model_dump(
            mode="json"
        )
    if integrations.isolated_release_apply is not None:
        found[settings_key(ISOLATED_APPLY_WORKFLOW)] = (
            integrations.isolated_release_apply.model_dump(mode="json")
        )
    return found


def build_knowledge_catalog(
    config: CompanyHostConfiguration,
    layout: HostLayout,
    authorization: DeviceAuthorization | None = None,
    *,
    profile: AgentProfile | None = None,
) -> KnowledgeCatalog:
    """Load only configured, published local Knowledge versions into a query catalog."""
    manifests = _load_all(layout.knowledge, KnowledgeManifest)
    available = {item.metadata.identity.key: item for item in manifests}
    bindings = {binding.asset.key: binding for binding in config.knowledge}
    if profile is not None:
        permitted = {item.key for item in profile.knowledge}
        bindings = {key: value for key, value in bindings.items() if key in permitted}
    if authorization is not None:
        for selection in authorization.selections:
            if selection.kind != "knowledge":
                continue
            if profile is not None and selection.asset.key not in permitted:
                continue
            manifest = available.get(selection.asset.key)
            expected = (
                layout.knowledge_vaults
                / selection.asset.namespace
                / selection.asset.name
                / selection.asset.version
            ).resolve()
            if manifest is None or Path(manifest.vault_ref).resolve() != expected:
                raise HostError("knowledge_invalid", layout.knowledge)
            existing = bindings.get(selection.asset.key)
            if existing is not None and Path(existing.vault_root).resolve() != expected:
                raise HostError("knowledge_invalid", layout.knowledge)
            bindings[selection.asset.key] = KnowledgeHostBinding(
                asset=selection.asset, vault_root=str(expected)
            )
    catalog = KnowledgeCatalog()
    for key in sorted(bindings):
        binding = bindings[key]
        manifest = available.get(binding.asset.key)
        if manifest is None:
            raise HostError("knowledge_invalid", layout.knowledge)
        try:
            catalog.register(manifest, Vault(Path(binding.vault_root)))
        except (OSError, ValueError, VaultError):
            raise HostError("knowledge_invalid", Path(binding.vault_root)) from None
    return catalog


def build_router(
    config: CompanyHostConfiguration,
    commands: CommandRouter,
    *,
    resolver: CredentialResolver | None = None,
    transport: Transport | None = None,
) -> RequestRouter:
    """The router, with a model behind it when this host was given one.

    A host with no `models` gets exactly what every host got before the field
    existed: deterministic command matching, and `needs_input` for anything
    else. That is not a degraded mode. A machine that guesses which of the
    team's workflows an ambiguous sentence meant, and runs it, is worse than
    one that asks.

    A misconfigured catalog is refused here, while the host is being
    assembled, rather than at the first message somebody types. `doctor` then
    reports it before anybody has waited for an answer that was never coming.
    """
    binding = config.models
    if binding is None or binding.routing_alias is None:
        return RequestRouter(commands, decision_accelerator=config.decision_accelerator)
    if resolver is None:
        mapped = config.credential_environment()
        endpoint = binding.catalog.endpoint(binding.routing_alias)
        if endpoint is not None and endpoint.credential is not None:
            if endpoint.credential.name not in mapped:
                raise HostError("credential_unmapped")
        resolver = EnvironmentCredentials(mapped)
    clients = ModelClients(
        binding.catalog,
        resolver=resolver,
        transport=transport,
        options=binding.options,
    )
    client = clients.for_alias(binding.routing_alias)
    if isinstance(client, Failure):
        # `unknown_alias` cannot happen -- the contract checked it -- so this
        # is a provider this build has no adapter for, which is a
        # configuration mistake and not something to discover at runtime.
        raise HostError("models_invalid")
    return RequestRouter(
        commands,
        ApprovedModelClient(client, binding.data_approval),
        binding.routing_alias,
        # Off unless this host asked for a model running on its own hardware.
        # The contract already refused the pair that cannot both be true.
        local_only=binding.require_local_model,
        decision_accelerator=config.decision_accelerator,
    )


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
        return TelegramIngress(
            ingress_config, agent, resolver,
            attachments=AttachmentStore(layout.workspace_root),
        )
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


def inspect_integrations(config: CompanyHostConfiguration) -> DoctorCheck:
    """Whether the migrated workflows could run here, read from the
    configuration and the installed libraries alone: no site is contacted
    and no workbook is opened."""
    integrations = config.integrations
    if integrations is None or (
        integrations.github_project is None
        and integrations.weekly_report is None
        and integrations.team_tickets is None
    ):
        return DoctorCheck(
            name="integrations",
            status="pending",
            detail="no project board or weekly report is configured; only the file capability runs",
        )
    problems: list[str] = []
    pending: list[str] = []
    if integrations.github_project is not None:
        mapped = config.credential_environment()
        variable = mapped.get(integrations.github_project.credential.name)
        if variable is None:
            problems.append("the board token's secret is not mapped to an environment variable")
        elif not os.environ.get(variable):
            # Reading whether a variable is set is not reading its value, and
            # this is the one thing between a host that looks configured and
            # a run that fails at the first fetch. `setx` on Windows sets it
            # for the next process, not this one, which is how a host passes
            # its own doctor and then cannot fetch anything.
            pending.append(
                f"the board token's environment variable {variable} is not set in this session"
            )
    if integrations.team_tickets is not None:
        if integrations.jira is None:
            problems.append("Workflow 7 needs a Jira connection; none is configured")
        else:
            variable = config.credential_environment().get(integrations.jira.credential.name)
            if variable is None:
                problems.append("the Jira PAT's secret is not mapped to an environment variable")
            elif not os.environ.get(variable):
                pending.append(
                    f"the Jira PAT's environment variable {variable} is not set in this session"
                )
    settings = integrations.weekly_report
    if settings is not None:
        if integrations.github_project is None:
            problems.append("the weekly report needs a project board; none is configured")
        try:
            excel.require_library()
        except excel.WorkbookError:
            problems.append(
                "openpyxl is not installed; the Windows preview bundle carries it, "
                "and a source checkout installs it with the `excel` extra"
            )
        if not Path(settings.workbook_path).is_file():
            problems.append("the weekly workbook is not at the configured path")
    if problems:
        return DoctorCheck(
            name="integrations", status="failed", detail="; ".join((*problems, *pending))
        )
    if pending:
        return DoctorCheck(name="integrations", status="pending", detail="; ".join(pending))
    parts = []
    board = integrations.github_project
    if board is not None:
        parts.append(f"project {board.owner}/{board.project_number}")
    if integrations.team_tickets is not None:
        parts.append(f"Jira project {integrations.team_tickets.project}")
    if settings is not None:
        try:
            require_com()
            writes = "can write it"
        except WorkbookWriteError as missing:
            # A preview needs no Excel; only the write does. Not a failure:
            # a host may be given the dry run alone. Which absence it is
            # decides who fixes it, so the two are never merged.
            writes = (
                "preview only, Excel is not installed"
                if missing.code == "excel_missing"
                else "preview only, the Excel bridge is not installed"
            )
        parts.append(f"weekly report on {Path(settings.workbook_path).name} ({writes})")
        try:
            require_outlook()
            drafts = "can draft the mail"
        except DraftError as missing:
            # Told apart for the same reason as Excel's: whether the machine
            # lacks Outlook or this installation lacks the bridge decides who
            # fixes it. Neither is a failure -- a host may be given the report
            # and not the mail.
            drafts = (
                "no mail, Outlook is not installed"
                if missing.code == "outlook_missing"
                else "no mail, the Outlook bridge is not installed"
            )
        parts.append(drafts)
    return DoctorCheck(name="integrations", status="passed", detail=", ".join(parts))


def inspect_models(config: CompanyHostConfiguration) -> DoctorCheck:
    """What this host can reason with, and whether it can reason at all.

    Nothing is contacted. A model endpoint is not asked whether it is up: a
    doctor that made a chargeable request to answer a question about
    configuration would be a doctor nobody runs.
    """
    binding = config.models
    if binding is None:
        return DoctorCheck(
            name="models",
            status="pending",
            detail=(
                "No model is configured, so this Agent matches commands and runs "
                "Workflows and does not reason about anything else."
            ),
        )
    mapped = config.credential_environment()
    problems: list[str] = []
    for endpoint in binding.catalog.endpoints:
        if endpoint.credential is None:
            continue
        name = endpoint.credential.name
        if name not in mapped:
            problems.append(f"the model endpoint {endpoint.alias} needs the secret {name} mapped")
        elif not os.environ.get(mapped[name]):
            problems.append(
                f"the endpoint {endpoint.alias} has its secret mapped to "
                f"{mapped[name]}, which is not set in this session"
            )
    if problems:
        return DoctorCheck(name="models", status="failed", detail="; ".join(problems))
    aliases = ", ".join(endpoint.alias for endpoint in binding.catalog.endpoints)
    if binding.routing_alias is None:
        return DoctorCheck(
            name="models",
            status="passed",
            detail=(
                f"{aliases}; no routing alias, so an unrecognized message is still "
                "answered with `needs_input` rather than a guess"
            ),
        )
    if (
        binding.data_approval is None
        or "UNCLASSIFIED" not in binding.data_approval.approved_classes
    ):
        return DoctorCheck(
            name="models",
            status="failed",
            detail=("The routed Gateway has no host-administrator approval for UNCLASSIFIED data"),
        )
    here = " (a model on this machine only)" if binding.require_local_model else ""
    return DoctorCheck(
        name="models",
        status="passed",
        detail=f"{aliases}; routing through {binding.routing_alias}{here}",
    )


def _runner_probe(python: Path) -> str | None:
    import tempfile

    try:
        runner = RestrictedRunner(python, RunnerLimits(timeout_seconds=60))
        with tempfile.TemporaryDirectory(prefix="aep-runner-probe-") as folder:
            result = runner.run(["-c", "import pytest, openpyxl; print('ok')"],
                                cwd=Path(folder), run_dir=Path(folder))
    except (RunnerError, OSError) as error:
        return f"the runner interpreter cannot start restricted ({type(error).__name__})"
    if result.exit_code == 0 and result.output.strip().endswith("ok"):
        return None
    code = result.exit_code if result.exit_code is None else hex(result.exit_code & 0xFFFFFFFF)
    return ("the runner interpreter does not start restricted or lacks pytest/openpyxl "
            f"(exit {code})")


def inspect_coding(
    config: CompanyHostConfiguration,
    *,
    rule_present: Callable[[Path], bool] = outbound_rule_present,
) -> DoctorCheck:
    """Coding on the Bridge is ready when the runner interpreter can be
    restricted, has pytest, is cut off by a firewall rule, and every
    configured repository is a git checkout."""
    binding = config.coding
    assert binding is not None
    python = Path(binding.runner_python)
    problems: list[str] = []
    if not python.is_file():
        problems.append("the runner interpreter is missing")
    elif is_venv_launcher(python):
        problems.append("the runner interpreter is a venv launcher; use a standalone Python")
    else:
        # Started the way a coding run starts it (low integrity, one-process
        # Job): a folder the low-integrity token cannot read fails only here,
        # never in a normal-integrity probe (coding_v1 fix-run-001, D4).
        problem = _runner_probe(python)
        if problem is not None:
            problems.append(problem)
        if binding.require_network_block and not rule_present(python):
            problems.append(f"no outbound firewall block names the runner; run elevated: "
                            f"{create_rule_command(python)}")
    problems.extend(
        f"repository {item.name} is not a git checkout"
        for item in binding.repositories if not (Path(item.path) / ".git").exists()
    )
    if problems:
        return DoctorCheck(name="coding", status="failed", detail="; ".join(problems))
    return DoctorCheck(
        name="coding", status="passed",
        detail=f"restricted pytest ready for {', '.join(i.name for i in binding.repositories)}",
    )


def inspect_dut(config: CompanyHostConfiguration) -> DoctorCheck:
    binding = config.dut
    if binding is None:
        return DoctorCheck(
            name="dut",
            status="pending",
            detail=(
                "no physical DUT driver is configured; simulator-only development remains available"
            ),
        )
    if not binding.physical_enabled:
        return DoctorCheck(
            name="dut",
            status="pending",
            detail="the physical DUT driver is configured but explicitly disabled",
        )
    if not Path(binding.driver.executable).is_file():
        return DoctorCheck(
            name="dut",
            status="failed",
            detail="the configured physical DUT driver executable is not present",
        )
    return DoctorCheck(
        name="dut",
        status="passed",
        detail=(
            f"physical validation enabled for {binding.target.vendor} "
            f"{binding.target.model} ({binding.target.device_id})"
        ),
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
    return (
        membership,
        authorization,
        assets,
        state,
        inspect_platform(config),
        inspect_integrations(config),
        inspect_models(config),
        inspect_dut(config),
        *((inspect_coding(config),) if config.coding is not None else ()),
    )


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


def _use_now(
    gateway: Gateway, manifest: WorkflowManifest, grants: tuple[CapabilityGrant, ...]
) -> None:
    """An install the owner approved, usable without a restart."""
    if gateway.engine.workflows.get(manifest.metadata.identity) is None:
        gateway.engine.workflows.register(manifest)
    policy = gateway.bridge.policy
    if isinstance(policy, LocalPolicy):
        for grant in grants:
            policy.add(grant)


def build_runtime(
    config: CompanyHostConfiguration,
    *,
    layout: HostLayout | None = None,
    resolver: CredentialResolver | None = None,
    jira_transport: MethodTransport | None = None,
    writer: Callable[[], WorkbookWriter] | None = None,
    chipset_writer: Callable[[], ChipsetWorkbookWriter] | None = None,
    drafter: Callable[[], DraftWriter] | None = None,
    model_transport: Transport | None = None,
    dut_adapter: DutAdapter | None = None,
) -> HostRuntime:
    """Assemble this company host, or say which file stopped it."""
    checked = CompanyHostConfiguration.model_validate(config)
    place = layout if layout is not None else HostLayout.under(checked.workspace_root)
    membership = load_membership(checked, place)
    gateway = build_gateway(
        checked,
        place,
        load_authorization(checked, place),
        resolver=resolver,
        jira_transport=jira_transport,
        writer=writer,
        chipset_writer=chipset_writer,
        drafter=drafter,
        model_transport=model_transport,
        membership=membership,
        dut_adapter=dut_adapter,
    )
    # Conversational authoring (G4): the Agent drafts, previews and asks to
    # run or install a Workflow; the owner approves outside the model.
    chat_authoring = ChatAuthoring(
        place.workspace_root / "authoring" / "chat",
        bridge=lambda: gateway.bridge,
        namespace=checked.namespace or "engineering",
        workflows_dir=place.workflows,
        grants_file=place.grants,
        skills_dir=place.skills,
        coding_workspace_roots=(
            () if checked.coding is None else tuple(checked.coding.workspace_roots)),
        on_installed=lambda manifest, grants: _use_now(gateway, manifest, grants),
    )
    gateway.host_tools = lambda: (*chat_authoring.tools(), *bridge_tools(gateway.bridge))
    try:
        state = SqliteLocalState(place.state, bridge_id=checked.device.bridge_id)
    except (LocalStateError, OSError, ValueError) as error:
        raise HostError("state_unavailable", place.state) from error
    try:
        agent = LocalAgent(
            membership,
            gateway,
            state,
            workflow_wait_seconds=checked.workflow_wait_seconds,
            task_executor=GatewayTaskExecutor(
                GatewayModelBackend(gateway),
                DataPolicy(
                    ()
                    if checked.models is None or checked.models.data_approval is None
                    else (checked.models.data_approval,)
                ),
                state,
                LocalTaskArtifacts(place.workspace_root),
            ),
        )
        telegram = build_telegram(checked, place, agent, resolver)
        if telegram is not None:
            telegram.approvals = chat_authoring
        platform = build_platform(checked, resolver)
    except BaseException:
        state.close()
        raise
    return HostRuntime(checked, place, agent, state, telegram, platform, chat_authoring)
