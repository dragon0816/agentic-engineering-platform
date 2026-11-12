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
import time
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self, TypeVar

from pydantic import JsonValue, ValidationError

from agent.backends.gateway import GatewayModelBackend
from agent.contracts import AgentProfile
from agent.data_policy import DataPolicy
from agent.delegation import DelegationCatalog, DelegationService, DelegationTarget
from agent.gateway import Gateway, KnowledgeVaultTool
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from agent.task_execution import GatewayTaskExecutor
from capabilities.bi_cards import vault as bi_vault
from capabilities.bi_cards.capability import bindings as bi_cards_bindings
from capabilities.browser_session.handlers import SPEC as BROWSER_SPEC
from capabilities.browser_session.handlers import (
    BrowserRequest,
    BrowserResult,
    BrowserSessionHandler,
)
from capabilities.business_cards.handlers import WRITE_SPECS as CARDS_WRITE_SPECS
from capabilities.business_cards.handlers import bindings as business_cards_bindings
from capabilities.business_cards.manifest import CARDS_SKILL
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
from capabilities.data_merge.handlers import SPEC as DATA_MERGE_SPEC
from capabilities.data_merge.handlers import MergeHandler as DataMergeHandler
from capabilities.data_merge.handlers import MergeRequest as DataMergeRequest
from capabilities.data_merge.handlers import MergeResult as DataMergeResult
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
from capabilities.knowledge_pipeline.contracts import (
    AdoptRequest,
    ConvertRequest,
    DropAdded,
    DropAddRequest,
    DropFoldersRequest,
    FileRequest,
    IndexBuildRequest,
    IndexEnrichRequest,
    IngestApplyRequest,
    IngestPlanRequest,
    LintRequest,
    MergeRequest,
    PlanPageRequest,
    PullRequest,
    RuleWriteRequest,
    SandboxCreateRequest,
    SandboxDiscarded,
    SandboxList,
    SandboxListRequest,
    SandboxRecord,
    SandboxRef,
    SkillGuideRequest,
)
from capabilities.knowledge_pipeline.handlers import (
    ADOPT_SPEC,
    CONVERT_SPEC,
    DROP_ADD_SPEC,
    DROP_FOLDERS_SPEC,
    FILE_READ_SPEC,
    INDEX_BUILD_SPEC,
    INDEX_ENRICH_SPEC,
    INGEST_APPLY_SPEC,
    INGEST_PLAN_SPEC,
    LINT_SPEC,
    MERGE_SPEC,
    PLAN_PAGE_SPEC,
    PULL_SPEC,
    QUESTION_SETS_SPEC,
    RULE_FILES_SPEC,
    RULE_WRITE_SPEC,
    SANDBOX_CONTENTS_SPEC,
    SANDBOX_CREATE_SPEC,
    SANDBOX_DISCARD_SPEC,
    SANDBOX_LIST_SPEC,
    SKILL_GUIDE_SPEC,
    AdoptHandler,
    ConvertHandler,
    DropAddHandler,
    DropFoldersHandler,
    FileReadHandler,
    IndexBuildHandler,
    IndexEnrichHandler,
    IngestApplyHandler,
    IngestPlanHandler,
    LintHandler,
    MergeHandler,
    PlanPageHandler,
    PullHandler,
    QuestionSetsHandler,
    RuleFilesHandler,
    RuleWriteHandler,
    SandboxContentsHandler,
    SandboxCreateHandler,
    SandboxDiscardHandler,
    SandboxListHandler,
    SkillGuideHandler,
)
from capabilities.knowledge_query.handlers import (
    KNOWLEDGE_QUERY_SPEC,
    MARKET_MATRIX_SPEC,
    KnowledgeQueryHandler,
    MarketMatrixHandler,
)
from capabilities.loan_reply import handlers as loan_handlers
from capabilities.loan_reply import manifest as loan_manifest
from capabilities.loan_reply.bridge_api import Bridge as LoanBridgeApi
from capabilities.loan_reply.contracts import (
    DraftStepInput as LoanDraftStepInput,
)
from capabilities.loan_reply.contracts import (
    EnqueueStepInput as LoanEnqueueStepInput,
)
from capabilities.loan_reply.contracts import (
    LoanDrafts,
    LoanEnqueued,
    LoanLookUps,
    LoanReplyResult,
    LoanScan,
)
from capabilities.loan_reply.contracts import (
    LookUpStepInput as LoanLookUpStepInput,
)
from capabilities.loan_reply.contracts import (
    OfferStepInput as LoanOfferStepInput,
)
from capabilities.loan_reply.contracts import (
    ScanStepInput as LoanScanStepInput,
)
from capabilities.mail_draft.handlers import DRAFT_SPEC as MAIL_DRAFT_SPEC
from capabilities.mail_draft.handlers import MailDraftHandler, MailDraftRequest, MailDraftResult
from capabilities.mail_read.handlers import READ_SPEC as MAIL_READ_SPEC
from capabilities.mail_read.handlers import SEARCH_SPEC as MAIL_SEARCH_SPEC
from capabilities.mail_read.handlers import (
    MailReadHandler,
    MailReadRequest,
    MailReadResult,
    MailSearchHandler,
    MailSearchRequest,
    MailSearchResult,
)
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
from capabilities.release_package import choices as release_choices
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
from capabilities.release_package.manifest import PUSH_SPEC as RELEASE_PUSH_SPEC
from capabilities.release_package.preview import ReleasePreviewHandler
from capabilities.release_package.release_run import (
    CommitHandler,
    CommitResult,
    CommitStepInput,
    PreparedRelease,
    PrepareHandler,
    PrepareStepInput,
    PushHandler,
    PushResult,
    PushStepInput,
)
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.script_tools import (
    ScriptToolHandler,
    ScriptToolInput,
    ScriptToolOutput,
    load_script_tools,
)
from capabilities.system_command.handlers import register as register_system_command
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
from common.assets import AssetIdentity, ExecutionDependencies, WorkflowManifest
from common.authorization import DeviceAuthorization
from common.base import Contract
from common.distribution import LocalStateError
from common.execution import Failure, TraceIdentifiers
from common.local_agent import BridgeMembership
from common.workflow_run_form import agent_prefill, form_offer
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
from host_runtime import bi_bench, wiki_bench
from host_runtime.agent import LocalAgent
from host_runtime.attachments import AttachmentStore
from host_runtime.bi_cards_tools import bi_cards_tools
from host_runtime.bridge_tools import bridge_tools
from host_runtime.business_cards_tools import business_cards_tools
from host_runtime.chat_authoring import ChatAuthoring
from host_runtime.choice_sources import FOLDER_FILES, ChoiceFunction, ChoiceSources, folder_files
from host_runtime.contracts import (
    CompanyHostConfiguration,
    DoctorCheck,
    HostDoctorReport,
    KnowledgeHostBinding,
)

# Re-exported: the layout moved to the contracts module so the platform client
# can take one without importing this module, and callers still find it here.
from host_runtime.contracts import HostLayout as HostLayout
from host_runtime.gateway_link import explain_model_failure
from host_runtime.identity_presets import IdentityPresets
from host_runtime.jev_shadow import SHADOW_LOG_FILE, JevShadowLog, skill_accelerator
from host_runtime.mcp_servers import McpHub
from host_runtime.profiles import (
    ProfileError,
    delegation_target,
    installed_profiles,
    load_active_profile,
)
from host_runtime.reference_sets import REFERENCE_SETS_FILE, ReferenceItem, ReferenceSetStore
from host_runtime.runtime import inspect_host
from host_runtime.session_artifacts import SessionArtifacts
from host_runtime.state import LocalStateBusy, SqliteLocalState
from host_runtime.sync import PlatformClient
from host_runtime.task_artifacts import LocalTaskArtifacts
from host_runtime.team_membership import TeamMembershipStore
from host_runtime.telegram_history import TelegramHistory
from host_runtime.telegram_settings import windows_user_environment
from host_runtime.tool_access import ToolAccess
from host_runtime.workflow_form_tool import workflow_form_tools
from host_runtime.workflow_settings import SETTINGS_FILE, WorkflowSettingsStore, settings_key
from host_runtime.workflow_uploads import UPLOADS_FOLDER, WorkflowUploadStore
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
from knowledge import wiki_repos
from knowledge.describe import ImageDescriber
from knowledge.evolution import (
    KnowledgeAnswerRecord,
    KnowledgeCatalog,
    KnowledgeManifest,
    KnowledgeQueryRequest,
)
from knowledge.layered_index import EnrichReport, IndexReport
from knowledge.market_matrix import MarketMatrixRecord, MarketMatrixRequest
from knowledge.office import office_extractors
from knowledge.pipeline import (
    AdoptSummary,
    ConvertResult,
    DropFolders,
    IngestApplyResult,
    IngestPlanResult,
    KnowledgePipeline,
    LintSummary,
    MergeReport,
    PlanPage,
    PullResult,
    QuestionSets,
    RuleFiles,
    SandboxContents,
    SandboxFile,
    SkillGuide,
)
from knowledge.repo import wiki
from knowledge.sandbox import Sandboxes
from knowledge.vault import Vault, VaultError
from models.approved import ApprovedModelClient
from models.clients import ModelClients
from models.contracts import ModelClient
from models.credentials import CredentialResolver, EnvironmentCredentials
from models.selection import SelectableModelClient
from models.wire import MethodTransport, Transport
from voice.service import VoiceService
from voice.whisper import build_voice
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
    "state_busy",
    "state_unavailable",
    "dut_skill_missing",
    "dut_driver_missing",
]

ContractT = TypeVar("ContractT", bound=Contract)


#: How long a start waits for a busy `state.sqlite`. Holders keep it for moments, so this is
#: generous; the starting page's patience (`launcher.START_WAIT_SECONDS`) leaves room for it.
STATE_BUSY_WAIT_SECONDS = 30.0
STATE_BUSY_POLL_SECONDS = 0.25


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


def _release_chipsets(
    settings: Mapping[str, JsonValue], arguments: Mapping[str, str]
) -> list[ReferenceItem]:
    """The release form's chipset list (forms v2); fails soft, never blocks."""
    return [
        ReferenceItem(value=value, label=label)
        for value, label in release_choices.chipset_choices(settings, arguments)
    ]


def _release_versions(
    settings: Mapping[str, JsonValue], arguments: Mapping[str, str]
) -> list[ReferenceItem]:
    """Published versions of one package, for the release form (forms v2)."""
    return [
        ReferenceItem(value=value, label=label)
        for value, label in release_choices.version_choices(settings, arguments)
    ]


#: Read-only `fn:` choice functions by name (see `host_runtime.choice_sources`).
CHOICE_FUNCTIONS: dict[str, ChoiceFunction] = {
    NCC_STATIONS_FUNCTION: _ncc_stations,
    FOLDER_FILES: folder_files,
    release_choices.CHIPSETS_FUNCTION: _release_chipsets,
    release_choices.VERSIONS_FUNCTION: _release_versions,
}


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
        # MCP servers the owner added in Agent Web (owner 2026-10-08); they
        # connect when a long-running command starts them.
        self.mcp: McpHub | None = None
        # What each conversation produced (owner 2026-10-25); set by build_runtime.
        self.session_artifacts: SessionArtifacts | None = None
        # The owner's Telegram conversations, kept for Agent Web; set by build_runtime.
        self.telegram_history: TelegramHistory | None = None
        # Speech to text for Telegram and Agent Web; None: voice is off.
        self.voice: VoiceService | None = None
        # Which teams this PC's person belongs to (owner 2026-10-19); set by
        # `build_runtime`. Decides only where a local revision is named.
        self.team_membership: TeamMembershipStore | None = None

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
        if self.mcp is not None:
            self.mcp.close()
        if self.voice is not None:
            self.voice.close()
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
    """Read legacy member metadata, including unchanged Knowledge selections.

    Tool grants no longer govern execution and may coexist with this file.
    Device identity is still checked; Knowledge selection is not widened here.
    """
    if not layout.authorization.is_file():
        return None
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


OWNER_GRANT_REF = "device-owner"


def _owner_grants(
    membership: BridgeMembership | None,
    installed: InstalledCapabilities,
    layout: HostLayout,
) -> tuple[CapabilityGrant, ...]:
    """Every installed capability for the device owner (owner 2026-10-11): on a
    local host what this computer may do, its owner may do. A grant written in
    grants.json for the same capability is kept as written."""
    if membership is None:
        return ()
    owner = next((b.actor for b in membership.bindings if b.status == "active"), None)
    if owner is None:
        return ()
    written = {(g.actor, g.asset.key) for g in _configured_grants(layout)}
    return tuple(
        CapabilityGrant(
            actor=owner,
            asset=spec.identity,
            permissions=spec.policy.required_permissions,
            policy_refs=spec.policy.policy_refs or (OWNER_GRANT_REF,),
            approval_ref=OWNER_GRANT_REF,
        )
        for spec in installed.discover()
        if (owner, spec.identity.key) not in written
    )


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


def _loan_bridge_factory(
    layout: HostLayout, drafter: Callable[[], DraftWriter] | None
) -> Callable[[], LoanBridgeApi]:
    """One `LoanBridge` per host, made on first use: this computer's Outlook
    and its own Edge profiles for the loan portal and C4C."""
    made: list[LoanBridgeApi] = []

    def factory() -> LoanBridgeApi:
        if not made:
            from capabilities.loan_reply.bridge import LoanBridge
            from integrations.outlook_mail import OutlookComMailbox

            made.append(
                LoanBridge(
                    layout.workspace_root,
                    mailbox=OutlookComMailbox,
                    drafts=drafter if drafter is not None else OutlookComDraft,
                    replies=OutlookComDraft,
                )
            )
        return made[0]

    return factory


def _register_loan_reply(
    installed: InstalledCapabilities,
    layout: HostLayout,
    loan_bridge: Callable[[], LoanBridgeApi] | None,
    drafter: Callable[[], DraftWriter] | None,
) -> None:
    """Register the shipped loan tools without an asset-reference prerequisite. The send itself
    (`loan_manifest.SEND_SPEC`) is never registered: only a person's press on
    a send card sends (`host_runtime.loan_reply_cards`)."""
    from host_runtime.loan_reply_cards import LoanReplyCards

    bridge = loan_bridge if loan_bridge is not None else _loan_bridge_factory(layout, drafter)
    workspace = layout.workspace_root
    cards = LoanReplyCards(workspace)
    for spec, handler, step_input, output in (
        (
            loan_manifest.SCAN_SPEC,
            loan_handlers.ScanMailHandler(bridge, workspace),
            LoanScanStepInput,
            LoanScan,
        ),
        (
            loan_manifest.ENQUEUE_SPEC,
            loan_handlers.EnqueueHandler(workspace),
            LoanEnqueueStepInput,
            LoanEnqueued,
        ),
        (
            loan_manifest.LOOK_UP_SPEC,
            loan_handlers.LookUpHandler(bridge, workspace),
            LoanLookUpStepInput,
            LoanLookUps,
        ),
        (
            loan_manifest.DRAFT_SPEC,
            loan_handlers.DraftRepliesHandler(bridge, workspace),
            LoanDraftStepInput,
            LoanDrafts,
        ),
        (
            loan_manifest.OFFER_SPEC,
            loan_handlers.OfferSendHandler(cards.offer),
            LoanOfferStepInput,
            LoanReplyResult,
        ),
    ):
        installed.register(
            spec, handler, step_input, output, ExecutionDependencies(central_required=False)
        )


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
    loan_bridge: Callable[[], LoanBridgeApi] | None = None,
) -> None:
    """The capabilities the migrated workflows need, from what this host was
    given. Jira's token is resolved through the host's credential mapping at
    every call and never held; a name nothing is mapped to is refused now,
    not at the first fetch. The weekly report's steps that need no board are
    installed whenever its settings are, so a preview against the workbook
    alone still runs."""
    # Register portable blocks before any asset references them. Task settings
    # remain real inputs, validated by the handler at invocation time.
    installed.register(
        RELEASE_PREVIEW_SPEC,
        ReleasePreviewHandler(),
        ReleasePreviewStepInput,
        ReleasePreview,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        ISOLATED_APPLY_SPEC,
        IsolatedApplyHandler(),
        IsolatedApplyStepInput,
        IsolatedApplyOutput,
        ExecutionDependencies(central_required=False),
    )
    # Release prepare/commit/push are discoverable before a Workflow is authored.
    # Their real request inputs and preflight checks remain unchanged.
    # Uploaded release files are read only from this host's upload store.
    uploads = layout.workspace_root / UPLOADS_FOLDER
    for spec, handler, step_input, output in (
        (
            RELEASE_PREPARE_SPEC,
            PrepareHandler(upload_root=uploads),
            PrepareStepInput,
            PreparedRelease,
        ),
        (RELEASE_COMMIT_SPEC, CommitHandler(), CommitStepInput, CommitResult),
        (RELEASE_PUSH_SPEC, PushHandler(), PushStepInput, PushResult),
    ):
        installed.register(
            spec, handler, step_input, output, ExecutionDependencies(central_required=False)
        )
    # Workflow 14: its paths are per-install Workflow settings.
    installed.register(
        NCC_PREPARE_SPEC,
        NccPrepareHandler(),
        NccPlanStepInput,
        NccPlan,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        NCC_RENDER_SPEC,
        NccRenderHandler(),
        NccRenderStepInput,
        NccRendered,
        ExecutionDependencies(central_required=False),
    )
    # Web and data building blocks for generated Workflows.
    if config.web is not None:
        profile = (
            Path(config.web.profile_dir)
            if config.web.profile_dir
            else layout.workspace_root / "web-profile"
        )
        for spec, mode in ((WEB_READ_SPEC, "read"), (WEB_ACT_SPEC, "act")):
            installed.register(
                spec,
                WebScriptHandler(config.web, profile, mode),  # type: ignore[arg-type]
                WebScript,
                WebScriptResult,
                ExecutionDependencies(central_required=False),
            )
        # The Agent's own Edge for a task (lab gap L1): kept open between calls,
        # in a profile apart from the Workflow steps' so neither locks the other.
        installed.register(
            BROWSER_SPEC,
            BrowserSessionHandler(
                config.web.allowed_origins,
                layout.workspace_root / "browser-profile",
                headless=config.web.headless,
                timeout_s=float(config.web.timeout_seconds),
                workspace_roots=config.coding.workspace_roots if config.coding else (),
            ),
            BrowserRequest,
            BrowserResult,
            ExecutionDependencies(central_required=False),
        )
    # Registered desktop applications the Agent may operate (lab gap L2).
    if config.desktop is not None:
        desktop = config.desktop
        if not desktop.workspace_roots and config.coding is not None:
            desktop = desktop.model_copy(update={"workspace_roots": config.coding.workspace_roots})
        installed.register(
            DESKTOP_SPEC,
            DesktopSessionHandler(desktop, layout.workspace_root / "desktop-tool"),
            DesktopRequest,
            DesktopResult,
            ExecutionDependencies(central_required=False),
        )
    # Data/Excel discovery does not depend on another tool's configuration.
    installed.register(
        DATA_MERGE_SPEC,
        DataMergeHandler(),
        DataMergeRequest,
        DataMergeResult,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        DATA_SELECT_SPEC,
        SelectHandler(),
        SelectRequest,
        SelectResult,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        EXCEL_READ_SHEET_SPEC,
        ReadSheetHandler(),
        ReadSheetRequest,
        SheetRows,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        EXCEL_UPSERT_SPEC,
        UpsertHandler(layout.workspace_root / "excel-backups"),
        UpsertRequest,
        UpsertResult,
        ExecutionDependencies(central_required=False),
    )
    _register_loan_reply(installed, layout, loan_bridge, drafter)
    # Outlook handlers are factories: registration neither opens COM nor reads mail.
    installed.register(
        MAIL_DRAFT_SPEC,
        MailDraftHandler(drafter if drafter is not None else OutlookComDraft),
        MailDraftRequest,
        MailDraftResult,
        ExecutionDependencies(central_required=False),
    )
    # Legacy mail settings are loaded only when a read/search is invoked.
    from host_runtime.agent_mode_settings import AgentModeStore
    from integrations.outlook_mail import OutlookComMailbox

    store = AgentModeStore(layout.workspace_root)
    installed.register(
        MAIL_SEARCH_SPEC,
        MailSearchHandler(OutlookComMailbox, lambda: store.load().mail),
        MailSearchRequest,
        MailSearchResult,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        MAIL_READ_SPEC,
        MailReadHandler(OutlookComMailbox, lambda: store.load().mail),
        MailReadRequest,
        MailReadResult,
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
    loan_bridge: Callable[[], LoanBridgeApi] | None = None,
) -> Gateway:
    """The platform's own wiring, with what this host was given.

    Routing is deterministic only: no model is configured on a company host
    in this slice, so an unrecognized message is `needs_input` rather than a
    guess. Built-in handlers are installed only when their trusted local
    configuration is present; every other capability a manifest names is
    absent, and a step that reaches for one fails closed.

    Local tools/assets are usable without member tool selections. Knowledge
    source/model eligibility is assembled separately and remains unchanged."""
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
        if profile_skills is not None and manifest.metadata.identity.key not in profile_skills:
            continue
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
    register_system_command(installed)
    for spec in (
        BROWSER_SPEC,
        DESKTOP_SPEC,
        WEB_READ_SPEC,
        WEB_ACT_SPEC,
        CHIPSET_PREVIEW_SPEC,
        CHIPSET_APPLY_SPEC,
        PROJECT_SEARCH_SPEC,
        TEAM_TICKETS_PREVIEW_SPEC,
        RESOLVE_WINDOW_SPEC,
        READ_SCRATCH_SHEET_SPEC,
        PLAN_SPEC,
        APPLY_SPEC,
        MAIL_SPEC,
    ):
        installed.offer(spec)
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
        loan_bridge=loan_bridge,
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
    session_selectable: SelectableModelClient | None = None
    chat_selectable: SelectableModelClient | None = None
    if binding is not None and binding.routing_alias is not None:
        # The router creates a default environment resolver inside
        # build_router, but Knowledge and Workflow drafting are assembled
        # earlier. They must see the same host-owned credential mapping.
        model_resolver = resolver or EnvironmentCredentials(config.credential_environment())
        drafting_clients = ModelClients(
            binding.catalog,
            resolver=model_resolver,
            transport=model_transport,
            timeout_s=float(binding.batch_timeout_seconds),
            options=binding.options,
        )
        chosen = drafting_clients.for_alias(binding.routing_alias)
        drafting_endpoint = binding.catalog.endpoint(binding.routing_alias)
        if not isinstance(chosen, Failure) and drafting_endpoint is not None:
            # One switch for the router and every drafting client (owner
            # 2026-10-22): a Knowledge answer, a Workflow draft or a card
            # read made during a session turn uses that session's model;
            # the data approval still decides each request first.
            # The conversation has its own clients with the shorter per-call
            # timeout (`call_timeout_seconds`); drafting keeps
            # `batch_timeout_seconds`. Both follow the session's model and
            # the models the page approves (set on the router's switch).
            chat_clients = ModelClients(
                binding.catalog,
                resolver=model_resolver,
                transport=model_transport,
                timeout_s=float(binding.call_timeout_seconds),
                options=binding.options,
            )
            chat_base = chat_clients.for_alias(binding.routing_alias)
            if not isinstance(chat_base, Failure):
                chat_selectable = SelectableModelClient(
                    drafting_endpoint, chat_base, chat_clients.build
                )
            follow = chat_selectable
            session_selectable = SelectableModelClient(
                drafting_endpoint,
                chosen,
                drafting_clients.build,
                **({"approved": lambda: follow.approved()} if follow is not None else {}),
            )
            drafting_model = ApprovedModelClient(session_selectable, binding.data_approval)
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
    # Procedure Skills do not decide whether these built-in tools exist.
    _register_business_cards(
        installed,
        layout,
        model=drafting_model,
        alias=(
            binding.routing_alias
            if binding is not None and binding.routing_alias is not None
            else "routing"
        ),
        local_only=binding.require_local_model if binding is not None else False,
    )
    approval = None if binding is None else binding.data_approval
    for spec, handler, request, response in bi_cards_bindings(
        layout.workspace_root,
        approved=() if approval is None else approval.approved_classes,
    ):
        installed.register(
            spec, handler, request, response, ExecutionDependencies(central_required=False)
        )
    if config.coding is not None and config.coding.workspace_roots:
        installed.register(
            CODING_RUN_SPEC,
            RunPythonHandler(config.coding),
            RunPythonStepInput,
            RunPythonResult,
            ExecutionDependencies(central_required=False),
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
    if config.knowledge_pipeline is not None:
        _register_knowledge_pipeline(installed, config, layout, drafting_model)
    # Legacy grant files and profile tool lists are not execution admission.
    # Actor/device identity and model/data eligibility remain their own contracts.
    policy = LocalPolicy(owner_mode=authorization is None and config.local_owner_grants)
    for spec in CARDS_WRITE_SPECS:
        if installed.get(spec.identity) is not None:
            policy.confirm_writes(spec)
    bridge = BridgeExecutor(installed, policy, timeout_seconds=config.capability_timeout_seconds)
    router = build_router(
        config,
        CommandRouter(skills),
        resolver=resolver,
        transport=model_transport,
        selectable=chat_selectable,
    )
    # JEV Skill selection: absent unless configured, sends nothing without the
    # owner's egress approval, and in shadow mode only records its choices.
    accelerator = config.decision_accelerator
    if (
        resolver is None
        and accelerator.credential is not None
        and accelerator.credential.name not in config.credential_environment()
    ):
        raise HostError("credential_unmapped")
    factory, authorize = skill_accelerator(
        accelerator,
        resolver
        if resolver is not None
        else EnvironmentCredentials(config.credential_environment()),
    )
    shadow_log = (
        JevShadowLog(layout.workspace_root / SHADOW_LOG_FILE)
        if factory is not None and accelerator.mode == "shadow"
        else None
    )
    return Gateway(
        router,
        bridge,
        WorkflowEngine(
            workflows,
            bridge,
            settings_provider=workflow_settings_provider(config, layout),
            choices_provider=choice_sources(config, layout).values,
            upload_root=layout.workspace_root / UPLOADS_FOLDER,
        ),
        skill_accelerator=factory,
        skill_authorizer=authorize,
        skill_shadow_observer=None if shadow_log is None else shadow_log.decision,
        conversation_observer=None if shadow_log is None else shadow_log.conversation,
        knowledge_vaults=(None if knowledge_catalog is None else _vault_tools(knowledge_catalog)),
        knowledge_capability=KNOWLEDGE_QUERY_SPEC.identity,
        knowledge_procedure=_harness_knowledge_procedure(router.commands.skills),
        accelerator_excluded_aliases=frozenset({coding_skill().alias}),
        workspace_note=workspace_note(
            () if config.coding is None else tuple(config.coding.workspace_roots)
        ),
        workspace_roots=() if config.coding is None else tuple(config.coding.workspace_roots),
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
            item
            for item in skills.manifests()
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


def _chat_form_offer(
    gateway: Gateway, identity: AssetIdentity, values: dict[str, JsonValue]
) -> dict[str, Any] | None:
    manifest = gateway.engine.workflows.get(identity)
    if manifest is None:
        return None
    return form_offer(
        manifest, agent_prefill(manifest, values), gateway.engine.settings_provider, origin="agent"
    )


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
            if existing is not None and (
                existing.vault_root is None or Path(existing.vault_root).resolve() != expected
            ):
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
        if binding.repo is not None:
            # A wiki knowledge repository: its published version, rebuilt and
            # picked up at the next question (knowledge repositories R4a).
            catalog.register_live(
                manifest, partial(wiki_repos.agent_source, layout.workspace_root, binding.repo)
            )
            continue
        assert binding.vault_root is not None
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
    selectable: SelectableModelClient | None = None,
) -> RequestRouter:
    """The router, with a model behind it when this host was given one.

    `selectable` is the host's one session-model switch, already built for
    the drafting clients from the same catalog, alias, credential mapping
    and transport; the router shares it so every client honours the same
    choice and the same approved list.

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
    if selectable is None:
        clients = ModelClients(
            binding.catalog,
            resolver=resolver,
            transport=transport,
            timeout_s=float(binding.call_timeout_seconds),
            options=binding.options,
        )
        client = clients.for_alias(binding.routing_alias)
        if isinstance(client, Failure):
            # `unknown_alias` cannot happen -- the contract checked it -- so
            # this is a provider this build has no adapter for, which is a
            # configuration mistake and not something to discover at runtime.
            raise HostError("models_invalid")
        endpoint = binding.catalog.endpoint(binding.routing_alias)
        assert endpoint is not None  # the contract checked the routing alias
        # A conversation may choose another model this Gateway serves (owner
        # 2026-10-21, `models.selection`); the data approval still decides first.
        selectable = SelectableModelClient(endpoint, client, clients.build)
    return RequestRouter(
        commands,
        ApprovedModelClient(selectable, binding.data_approval),
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
    *,
    voice: VoiceService | None = None,
    approvals: ChatAuthoring | None = None,
    session_artifacts: SessionArtifacts | None = None,
    history: TelegramHistory | None = None,
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
        ingress = TelegramIngress(
            ingress_config,
            agent,
            resolver,
            attachments=AttachmentStore(layout.workspace_root),
            uploads=WorkflowUploadStore(layout.workspace_root),
            presets=IdentityPresets(layout.workspace_root),
            voice=voice,
        )
    except ValueError as error:
        raise HostError("telegram_invalid", layout.telegram) from error
    # A failed turn says when the LLM gateway is down, starting or rejecting
    # the token (docs/phases/LLM_GATEWAY.md), as Agent Web does.
    ingress.explain_failure = lambda failure: explain_model_failure(config, failure)
    ingress.approvals = approvals
    ingress.session_artifacts = session_artifacts
    ingress.history = history
    return ingress


def build_platform(
    config: CompanyHostConfiguration, resolver: CredentialResolver | None
) -> PlatformClient | None:
    """The shared-platform client, if this host was given a token. As with
    Telegram, the secret's name must be mapped now: a host that would fail
    at its first sync is refused when it is built."""
    if config.platform is None:
        return None
    if resolver is None:
        from host_runtime.platform_publish import UserEnvironment

        mapped = config.credential_environment()
        if config.platform.credential.name not in mapped:
            raise HostError("credential_unmapped")
        # The token is saved for this Windows user when the PC enrolls, which
        # a process started earlier does not see in its own environment.
        resolver = EnvironmentCredentials(mapped, UserEnvironment())
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
            result = runner.run(
                ["-c", "import pytest, openpyxl; print('ok')"],
                cwd=Path(folder),
                run_dir=Path(folder),
            )
    except (RunnerError, OSError) as error:
        return f"the runner interpreter cannot start restricted ({type(error).__name__})"
    if result.exit_code == 0 and result.output.strip().endswith("ok"):
        return None
    code = result.exit_code if result.exit_code is None else hex(result.exit_code & 0xFFFFFFFF)
    return (
        f"the runner interpreter does not start restricted or lacks pytest/openpyxl (exit {code})"
    )


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
            problems.append(
                f"no outbound firewall block names the runner; run elevated: "
                f"{create_rule_command(python)}"
            )
    problems.extend(
        f"repository {item.name} is not a git checkout"
        for item in binding.repositories
        if not (Path(item.path) / ".git").exists()
    )
    if problems:
        return DoctorCheck(name="coding", status="failed", detail="; ".join(problems))
    return DoctorCheck(
        name="coding",
        status="passed",
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
                status="passed",
                detail="tools use the execution environment; no AEP tool grants are required",
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
        # Report physically installed assets, not obsolete member tool selections.
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


def delegation_catalog(config: CompanyHostConfiguration, layout: HostLayout) -> DelegationCatalog:
    """The profiles a parent turn may delegate to now (multi-agent V1): the
    active profile's `may_delegate_to` that validate (listed), and every other
    installed profile that validates (used only when the person names it).
    Nothing with the flag off."""
    if not config.multi_agent.enabled:
        return DelegationCatalog()
    authorization = load_authorization(config, layout)
    try:
        active = load_active_profile(
            config, layout, authorization, actor=config.device.registered_by
        )
    except ProfileError:
        active = None
    listed = active.may_delegate_to if active is not None else ()
    targets: list[DelegationTarget] = []
    unavailable: list[AssetIdentity] = []
    for identity in listed:
        try:
            profile = delegation_target(config, layout, authorization, identity)
        except ProfileError:
            unavailable.append(identity)
            continue
        targets.append(DelegationTarget(profile=profile, listed=True))
    skipped = {item.key for item in listed}
    if active is not None:
        skipped.add(active.metadata.identity.key)
    for identity in installed_profiles(layout):
        if identity.key in skipped:
            continue
        try:
            profile = delegation_target(config, layout, authorization, identity)
        except ProfileError:
            continue
        targets.append(DelegationTarget(profile=profile, listed=False))
    return DelegationCatalog(targets=tuple(targets), unavailable=tuple(unavailable))


def _switched_off_skills(layout: HostLayout) -> list[str]:
    """`namespace/name` of each Skill on the Capabilities shelf (switched off)."""
    from host_runtime.asset_shelf import disabled_assets

    return [
        f"{item['namespace']}/{item['name']}"
        for item in disabled_assets(layout)
        if item["kind"] == "skill"
    ]


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


def model_condenser(gateway: Any) -> Callable[[str], list[str]]:
    """One bounded structured call that condenses a run's text preview into
    at most five key results (task result summaries, owner 2026-10-25), on
    the gateway's approved model client and whichever model the running
    turn selected. Without a configured model it calls nothing."""
    from common.execution import TraceIdentifiers
    from host_runtime.task_summaries import (
        CONDENSE_MAX_OUTPUT_TOKENS,
        CONDENSE_PROMPT,
        parse_condensed,
    )
    from models.contracts import ModelMessage, ModelRequest

    def condense(text: str) -> list[str]:
        model = gateway.router.model
        if model is None or not text.strip():
            return []
        reply = model.generate(
            ModelRequest(
                trace=TraceIdentifiers(
                    trace_id="task-summary", request_id="task-summary", span_id="condense"
                ),
                model_alias=gateway.router.model_alias,
                messages=(
                    ModelMessage(role="system", text=CONDENSE_PROMPT),
                    ModelMessage(role="user", text=text),
                ),
                max_output_tokens=CONDENSE_MAX_OUTPUT_TOKENS,
            )
        )
        return parse_condensed(reply.text or "")

    return condense


def _open_state(path: Path, bridge_id: str) -> SqliteLocalState:
    """The state file for a host that is starting. A second writer is refused rather than
    waited for, and that stays the rule while a host runs (`state.py`'s `timeout=0`). A
    start is different: two starts can meet on the file, and exiting over a moment's lock
    is worse than waiting it out. A file that is broken, or another device's, fails at once."""
    deadline = time.monotonic() + STATE_BUSY_WAIT_SECONDS
    while True:
        try:
            return SqliteLocalState(path, bridge_id=bridge_id)
        except LocalStateBusy as error:
            if time.monotonic() >= deadline:
                raise HostError("state_busy", path) from error
            time.sleep(STATE_BUSY_POLL_SECONDS)
        except (LocalStateError, OSError, ValueError) as error:
            raise HostError("state_unavailable", path) from error


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
    loan_bridge: Callable[[], LoanBridgeApi] | None = None,
) -> HostRuntime:
    """Assemble this company host, or say which file stopped it."""
    checked = CompanyHostConfiguration.model_validate(config)
    place = layout if layout is not None else HostLayout.under(checked.workspace_root)
    # A wiki repository's push is checked against its recorded test runs (R4a).
    wiki.set_benchmark(partial(wiki_bench.gate, place.workspace_root))
    # So is a BI vault's push (BI T1).
    bi_vault.set_benchmark(partial(bi_bench.gate, place.workspace_root))
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
        loan_bridge=loan_bridge,
    )
    # Conversational authoring (G4): the Agent drafts, previews and asks to
    # run or install a Workflow; the owner approves outside the model.
    chat_authoring = ChatAuthoring(
        place.workspace_root / "authoring" / "chat",
        attachments=AttachmentStore(place.workspace_root),
        bridge=lambda: gateway.bridge,
        namespace=checked.namespace or "engineering",
        workflows_dir=place.workflows,
        grants_file=place.grants,
        skills_dir=place.skills,
        coding_workspace_roots=(
            () if checked.coding is None else tuple(checked.coding.workspace_roots)
        ),
        on_installed=lambda manifest, grants: _use_now(gateway, manifest, grants),
    )
    mcp = McpHub(
        place.workspace_root,
        gateway.bridge.installed,
        lambda: gateway.bridge.policy,
        checked.device.registered_by,
        store_secret=windows_user_environment,
    )
    chat_authoring.mcp = mcp
    gateway.capability_approval = chat_authoring.capability_approval_tool_data
    # What each session produced, so the agent can show it again (owner
    # 2026-10-25): listed in every turn and attachable by its short id.
    session_artifacts = SessionArtifacts(place.workspace_root)
    gateway.authoring_completion_problem = chat_authoring.completion_problem
    gateway.session_context = lambda context: "\n\n".join(
        part
        for part in (chat_authoring.task_context(context), session_artifacts.guidance(context))
        if part
    )
    # Task result summaries: field labels from the installed Workflow, and one
    # bounded call on the approved model client when a run's outputs give
    # too few facts (none when no model is configured).
    session_artifacts.manifest_for = gateway.engine.workflows.get
    session_artifacts.condenser = model_condenser(gateway)
    # Multi-agent V1 (flag `multi_agent.enabled`, off by default): the parent
    # turn's `agent__delegate` tool; nothing is offered with the flag off.
    delegation = DelegationService(
        gateway,
        enabled=lambda: checked.multi_agent.enabled,
        catalog=lambda: delegation_catalog(checked, place),
        ledger=session_artifacts,
    )
    gateway.host_tools = lambda: (
        *ToolAccess(gateway.bridge, mcp=mcp).tools(),
        *chat_authoring.tools(),
        *bridge_tools(gateway.bridge),
        *business_cards_tools(gateway),
        *bi_cards_tools(gateway),
        *mcp.tools(gateway.bridge),
        *workflow_form_tools(gateway.engine),
        *session_artifacts.tools(),
        *delegation.tools(),
    )
    # Skills installed but switched off, by name, so the model never offers to
    # install one (live test 2026-10-20).
    gateway.switched_off_skills = lambda: _switched_off_skills(place)
    # An installed Workflow run from the chat with incomplete values becomes
    # its form (owner 2026-10-15), as on the Gateway's own Workflow tools.
    chat_authoring.form_offer = lambda identity, values: _chat_form_offer(gateway, identity, values)
    state = _open_state(place.state, checked.device.bridge_id)
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
        # Voice input (docs/phases/VOICE_INPUT.md): one service for Telegram
        # and Agent Web, built only when host.json enables it.
        voice = build_voice(checked.voice, place.workspace_root)
        telegram_history = TelegramHistory(state, checked.device.registered_by)
        telegram = build_telegram(
            checked,
            place,
            agent,
            resolver,
            voice=voice,
            approvals=chat_authoring,
            session_artifacts=session_artifacts,
            history=telegram_history,
        )
        platform = build_platform(checked, resolver)
    except BaseException:
        state.close()
        raise
    runtime = HostRuntime(checked, place, agent, state, telegram, platform, chat_authoring)
    runtime.voice = voice
    runtime.mcp = mcp
    runtime.session_artifacts = session_artifacts
    runtime.telegram_history = telegram_history
    # The Knowledge tool route runs the shared Knowledge Harness (unification U5).
    from host_runtime.knowledge_harness import KnowledgeHarness

    gateway.knowledge_harness = KnowledgeHarness(runtime, checked.namespace).for_tool
    # The per-turn tool cap and time budget are Agent Web settings (owner
    # 2026-10-19), read at each turn so a change applies without a restart.
    from host_runtime.conversation_context import ConversationContextStore

    gateway.conversation_limits = ConversationContextStore(place.workspace_root).limits
    # Team membership for revising a team-owned Workflow in place (owner
    # 2026-10-19): the Shared Platform's answer for this PC's member (cached
    # for offline use), else the teams declared in Agent Web Settings.
    runtime.team_membership = TeamMembershipStore(
        place.workspace_root,
        client=lambda: _membership_client(runtime),
        account=lambda: runtime.actor,
    )
    chat_authoring.teams = runtime.team_membership.membership
    return runtime


def _membership_client(runtime: HostRuntime) -> Any:
    """The Member Portal client for the current `publishing` binding, kept
    while the binding is the same object (Settings replaces it on save)."""
    from host_runtime.platform_publish import publisher_for

    binding = runtime.config.publishing
    held = getattr(runtime, "_membership_publisher", None)
    if held is None or held[0] is not binding:
        held = (binding, publisher_for(binding, runtime.config.credential_environment()))
        runtime._membership_publisher = held  # type: ignore[attr-defined]
    return held[1]


def _has_business_cards_skill(layout: HostLayout) -> bool:
    return _has_skill(layout, CARDS_SKILL)


def _has_skill(layout: HostLayout, identity: AssetIdentity) -> bool:
    """Some version of the Skill is installed here, switched on or off."""
    pattern = f"{identity.namespace}__{identity.name}__*.json"
    return any(layout.skills.glob(pattern)) or any((layout.skills / "disabled").glob(pattern))


def _register_business_cards(
    installed: InstalledCapabilities,
    layout: HostLayout,
    *,
    model: ModelClient | None,
    alias: str,
    local_only: bool,
) -> None:
    """The contact store's capabilities; mail is read in the scope set in
    Agent Web Settings > Agent mode, read at each call. The store lives in
    the actor's Memory Service (`<workspace>/memory/<actor-key>/memory.sqlite`);
    an older `business-cards/<actor-key>/cards.db` moves there on first use."""
    from host_runtime.agent_mode_settings import AgentModeStore
    from host_runtime.memory_spaces import registry as memory_registry
    from integrations.outlook_mail import OutlookComMailbox

    store = AgentModeStore(layout.workspace_root)
    for spec, handler, request, response in business_cards_bindings(
        layout.workspace_root,
        reader=OutlookComMailbox,
        scope=lambda: store.load().mail,
        model=model,
        alias=alias,
        local_only=local_only,
        # The contact store is the `contacts/org` memory space (accumulated
        # memory M1): the Host's registry says who may read and write it.
        memory=memory_registry(layout),
    ):
        installed.register(
            spec, handler, request, response, ExecutionDependencies(central_required=False)
        )


def _register_knowledge_pipeline(
    installed: InstalledCapabilities,
    config: CompanyHostConfiguration,
    layout: HostLayout,
    model: ModelClient | None,
) -> None:
    """Sandboxed convert/ingest/lint (docs/phases/KNOWLEDGE_K1.md). Ingest
    planning and image description use the routing model when there is one;
    images are described only when its endpoint declares vision."""
    assert config.knowledge_pipeline is not None
    binding = config.models
    alias = binding.routing_alias if binding is not None else None
    endpoints = binding.catalog.endpoints if binding is not None else ()
    endpoint = next((e for e in endpoints if e.alias == alias), None)
    describer = (
        ImageDescriber(model, alias=alias)
        if model is not None
        and alias is not None
        and endpoint is not None
        and endpoint.capabilities.vision
        else None
    )
    pipeline = KnowledgePipeline(
        Sandboxes(
            layout.workspace_root,
            root=(
                Path(config.knowledge_pipeline.sandbox_root)
                if config.knowledge_pipeline.sandbox_root
                else None
            ),
        ),
        {item.name: Path(item.root) for item in config.knowledge_pipeline.vaults},
        extractors=office_extractors(),
        model=model,
        alias=alias,
        describer=describer,
        drop_roots={
            item.name: Path(item.drop_root)
            for item in config.knowledge_pipeline.vaults
            if item.drop_root
        },
        questions_roots={
            item.name: Path(item.questions_root)
            for item in config.knowledge_pipeline.vaults
            if item.questions_root
        },
        maintainers={
            item.name: tuple(item.maintainers) for item in config.knowledge_pipeline.vaults
        },
    )
    local = ExecutionDependencies(central_required=False)
    for spec, handler, request, response in (
        (SANDBOX_CREATE_SPEC, SandboxCreateHandler(pipeline), SandboxCreateRequest, SandboxRecord),
        (SANDBOX_LIST_SPEC, SandboxListHandler(pipeline), SandboxListRequest, SandboxList),
        (CONVERT_SPEC, ConvertHandler(pipeline), ConvertRequest, ConvertResult),
        (INGEST_PLAN_SPEC, IngestPlanHandler(pipeline), IngestPlanRequest, IngestPlanResult),
        (INGEST_APPLY_SPEC, IngestApplyHandler(pipeline), IngestApplyRequest, IngestApplyResult),
        (LINT_SPEC, LintHandler(pipeline), LintRequest, LintSummary),
        (ADOPT_SPEC, AdoptHandler(pipeline), AdoptRequest, AdoptSummary),
        (INDEX_ENRICH_SPEC, IndexEnrichHandler(pipeline), IndexEnrichRequest, EnrichReport),
        (INDEX_BUILD_SPEC, IndexBuildHandler(pipeline), IndexBuildRequest, IndexReport),
        (MERGE_SPEC, MergeHandler(pipeline), MergeRequest, MergeReport),
        (DROP_FOLDERS_SPEC, DropFoldersHandler(pipeline), DropFoldersRequest, DropFolders),
        (PULL_SPEC, PullHandler(pipeline), PullRequest, PullResult),
        (QUESTION_SETS_SPEC, QuestionSetsHandler(pipeline), SandboxRef, QuestionSets),
        (RULE_FILES_SPEC, RuleFilesHandler(pipeline), SandboxRef, RuleFiles),
        (FILE_READ_SPEC, FileReadHandler(pipeline), FileRequest, SandboxFile),
        (RULE_WRITE_SPEC, RuleWriteHandler(pipeline), RuleWriteRequest, SandboxFile),
        (PLAN_PAGE_SPEC, PlanPageHandler(pipeline), PlanPageRequest, PlanPage),
        (SKILL_GUIDE_SPEC, SkillGuideHandler(pipeline), SkillGuideRequest, SkillGuide),
        (DROP_ADD_SPEC, DropAddHandler(pipeline), DropAddRequest, DropAdded),
        (SANDBOX_CONTENTS_SPEC, SandboxContentsHandler(pipeline), SandboxRef, SandboxContents),
        (SANDBOX_DISCARD_SPEC, SandboxDiscardHandler(pipeline), SandboxRef, SandboxDiscarded),
    ):
        installed.register(spec, handler, request, response, local)
