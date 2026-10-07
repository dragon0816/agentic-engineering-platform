"""Platform entry point: dispatch contracts behind deterministic-first routing.

The Gateway adds no authority and holds no domain logic. Capability dispatch is
authorized by LocalPolicy inside the Bridge; workflow pre-flights belong to the
engine. Model-selected routes dispatch through exactly the same contract as
deterministic ones, so a trigger's origin never changes what may execute.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import Field, JsonValue, TypeAdapter, model_validator

from agent.backend_contracts import (
    CONVERSATION_MAX_OUTPUT_TOKENS,
    MAX_CONVERSATION_TOOL_CALLS,
    MAX_CONVERSATION_TURNS,
)
from agent.decisions import (
    DecisionProvider,
    DecisionResult,
    DecisionService,
    DecisionShadow,
    DecisionTrace,
)
from agent.routing import RequestRouter, RoutingOutcome
from agent.skills import CommandBinding
from capabilities.runtime import CapabilityInvocation
from common.assets import AssetIdentity
from common.base import Contract, Symbol, Text
from common.execution import (
    CapabilityResult,
    Failure,
    IdempotencyKey,
    RequestContext,
    ResumePlan,
    ResumePolicy,
    RouteDecision,
    RunId,
    TraceIdentifiers,
)
from common.workflow_forms import agent_fields, agent_tool_schema
from common.workflow_parameters import WorkflowParameterError, validate_run_parameters
from models.contracts import (
    ModelMessage,
    ModelRequest,
    ModelRequirements,
    ModelTool,
    ModelToolCall,
)
from workflow.checkpoints import CheckpointStoreError
from workflow.dispatch import BridgeExecutor
from workflow.engine import ProgressStream, WorkflowEngine, WorkflowRunSnapshot
from workflow.journal import SuspensionConfirmation

# A reply cut at the output limit is retried this often within a turn, with
# this notice, before the turn fails with `model_output_truncated`.
MAX_TRUNCATED_RETRIES = 2
TRUNCATED_NOTICE = (
    "Your last reply was cut off at the output limit before it finished, so nothing was "
    "done with it. Reply again more briefly: split a long script into smaller steps or "
    "files, or shorten the text."
)
MAX_CONVERSATION_HISTORY = 12
MAX_CONVERSATION_MESSAGE_CHARS = 4_000
MAX_TOOL_OBSERVATION_CHARS = 16_000

ToolProgressState = Literal["running", "succeeded", "failed"]
#: Set by a channel around one `converse` call to hear which installed tool
#: starts and how it ends (by tool name, no arguments or results), so a person
#: waiting on a slow chat can see what is happening. A context variable rather
#: than a request field: the backend request is a frozen contract, and the
#: callback is presentation, not policy.
TOOL_PROGRESS: ContextVar[Callable[[str, ToolProgressState], None] | None] = ContextVar(
    "aep_tool_progress", default=None
)


#: The only field the model fills on a Knowledge vault tool.
VAULT_QUESTION_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {"question": {
        "type": "string", "description": "The question to answer from this vault",
    }},
    "required": ["question"],
    "additionalProperties": False,
}


class KnowledgeVaultTool(Contract):
    """One installed Knowledge vault as the Agent offers it."""

    asset: AssetIdentity
    purpose: Text
    boundaries: Text | None = None


def _tool_progress(name: str, state: ToolProgressState) -> None:
    listener = TOOL_PROGRESS.get()
    if listener is None:
        return
    try:
        listener(name, state)
    except Exception:  # noqa: BLE001 - progress display cannot change the answer
        pass


def _tool_succeeded(item: "ConversationToolExecution") -> bool:
    if item.failure is not None:
        return False
    if item.host is not None:
        return item.host.status != "failed"
    if item.capability is not None:
        return item.capability.status == "succeeded"
    return item.workflow is not None and item.workflow.run.status == "succeeded"


class RunControlResult(Contract):
    """Host-triggered run control. `run_id` echoes the request; a continuation's
    own id is only in `workflow.run.run_id`.

    `source` says which evidence answered: `memory` is this process's run
    history, `journal` is the durable record that outlives it, and `unknown`
    means the run is unknown to this caller — missing, evicted, never journalled
    or owned by another actor, all indistinguishable on purpose.
    """

    action: Literal["inspect", "resume", "suspend", "retire"]
    run_id: RunId
    source: Literal["memory", "journal", "unknown"] = "unknown"
    plan: ResumePlan | None = None
    workflow: WorkflowRunSnapshot | None = None
    suspended_by: Symbol | None = None

    @model_validator(mode="after")
    def payload_matches_action(self) -> Self:
        if self.action == "inspect" and self.workflow is not None:
            raise ValueError("inspect never executes a run")
        if self.action == "resume" and (self.plan is not None or self.suspended_by is not None):
            raise ValueError("resume reports the continuation, not a plan")
        if self.action == "suspend" and self.workflow is not None:
            raise ValueError("suspend records a confirmation; it never executes a run")
        if self.action == "retire" and (self.workflow is not None or self.source == "memory"):
            raise ValueError("retire removes durable history only")
        if self.suspended_by is not None and self.source != "journal":
            raise ValueError("only the durable record carries a confirmation")
        if self.source == "unknown" and (self.plan is not None or self.workflow is not None):
            raise ValueError("an unknown run has no evidence to report")
        return self


class GatewayResult(Contract):
    routing: RoutingOutcome
    capability: CapabilityResult | None = None
    workflow: WorkflowRunSnapshot | None = None

    @model_validator(mode="after")
    def execution_matches_decision(self) -> Self:
        matches = {
            "capability": self.capability is not None and self.workflow is None,
            "workflow": self.workflow is not None and self.capability is None,
            "needs_input": self.capability is None and self.workflow is None,
        }
        if not matches.get(self.routing.decision.kind, False):
            raise ValueError("execution results must match the routing decision")
        return self


class HostToolOutcome(Contract):
    """What a host-owned conversation tool did (G4 authoring). The host
    performs the action; `awaiting_approval` means nothing ran yet and the
    owner decides with a button the model cannot press."""

    status: Literal["succeeded", "awaiting_approval", "failed"]
    data: JsonValue = None
    failure: Failure | None = None


@dataclass(frozen=True)
class HostTool:
    """A conversation tool the host implements itself, such as drafting a
    Workflow. It never approves, installs or runs a change on its own: any
    step that is not a read goes through an owner approval."""

    tool: ModelTool
    handler: Callable[[RequestContext, dict[str, JsonValue]], Awaitable[HostToolOutcome]]


class ConversationToolExecution(Contract):
    """Evidence for one model-proposed call after installed-target lookup."""

    call_id: Symbol
    name: Symbol
    decision: RouteDecision | None = None
    capability: CapabilityResult | None = None
    workflow: WorkflowRunSnapshot | None = None
    host: HostToolOutcome | None = None
    failure: Failure | None = None

    @model_validator(mode="after")
    def one_outcome(self) -> Self:
        outcomes = (
            self.capability is not None,
            self.workflow is not None,
            self.host is not None,
            self.failure is not None,
        )
        if sum(outcomes) != 1:
            raise ValueError("a tool call has exactly one execution outcome")
        if self.failure is not None and self.decision is not None:
            raise ValueError("a refused tool call selected no execution target")
        if self.decision is None and self.failure is None and self.host is None:
            raise ValueError("an executed tool call records its exact target")
        if self.host is not None and self.decision is not None:
            raise ValueError("a host tool selects no installed target")
        return self


class GatewayConversationResult(Contract):
    """Bounded Agent loop result. The transcript itself grants no authority."""

    trace: TraceIdentifiers
    status: Literal["answered", "needs_input", "failed"]
    text: str
    model_turns: int = Field(ge=0, le=MAX_CONVERSATION_TURNS, strict=True)
    tools: tuple[ConversationToolExecution, ...] = Field(
        default=(), max_length=MAX_CONVERSATION_TOOL_CALLS
    )
    failure: Failure | None = None

    @model_validator(mode="after")
    def terminal_state(self) -> Self:
        if (self.status == "answered") == (self.failure is not None):
            raise ValueError("only an answered conversation omits failure details")
        return self


class SkillCandidateRequest(Contract):
    """The exact initial model payload, available before candidate egress.

    A selector can inspect the conversation and installed tool descriptions, but
    it cannot see a shorter request than the model would receive. In particular,
    persona guidance and earlier turns must not be omitted from authorization.
    """

    context: RequestContext
    initial_request: ModelRequest
    # Each tool's Skill `selector_hint`, when its Skill declares one: what a
    # selector is told the tool is for. Never a wider payload than the tools.
    selector_hints: dict[Symbol, Text] = Field(default_factory=dict)

    @property
    def tools(self) -> tuple[ModelTool, ...]:
        return self.initial_request.tools

    @model_validator(mode="after")
    def unique_tool_names(self) -> Self:
        if self.initial_request.trace != self.context.trace:
            raise ValueError("candidate request must keep the conversation trace")
        if not self.tools:
            raise ValueError("candidate request needs installed tools")
        names = [tool.name for tool in self.tools]
        if len(set(names)) != len(names):
            raise ValueError("installed tool names must be unique")
        if not set(self.selector_hints) <= set(names):
            raise ValueError("selector hints name only installed tools")
        return self


class _InstalledSkillCandidates:
    """Preserve the full installed catalog and its original order by default."""

    provider_id = "rule"

    def decide(self, request: SkillCandidateRequest) -> DecisionResult[tuple[str, ...]]:
        return DecisionResult(
            decision_type="skill_selection",
            value=tuple(tool.name for tool in request.tools),
            confidence=1.0,
            reason_code="all_installed",
            provider_id=self.provider_id,
        )


def _valid_skill_subset(
    request: SkillCandidateRequest, candidate: DecisionResult[tuple[str, ...]]
) -> bool:
    names = candidate.value
    installed = {tool.name for tool in request.tools}
    return bool(names) and len(set(names)) == len(names) and set(names) <= installed


class Gateway:
    def __init__(
        self,
        router: RequestRouter,
        bridge: BridgeExecutor,
        engine: WorkflowEngine,
        *,
        decision_observer: Callable[[DecisionTrace], None] | None = None,
        skill_accelerator: Callable[
            [], DecisionProvider[SkillCandidateRequest, tuple[str, ...]]
        ] | None = None,
        skill_authorizer: Callable[[SkillCandidateRequest], bool] | None = None,
        skill_shadow_observer: Callable[[SkillCandidateRequest, DecisionShadow], None]
        | None = None,
        conversation_observer: Callable[[GatewayConversationResult], None] | None = None,
        knowledge_vaults: Callable[[], Sequence[KnowledgeVaultTool]] | None = None,
        knowledge_capability: AssetIdentity | None = None,
        accelerator_excluded_aliases: frozenset[str] = frozenset(),
        host_tools: Callable[[], Sequence[HostTool]] | None = None,
    ):
        # Host-owned conversation tools (G4 authoring); the host may set it after
        # construction, once the services behind the tools exist.
        self.host_tools = host_tools
        self.router = router
        self.bridge = bridge
        self.engine = engine
        self.skill_decisions = DecisionService[SkillCandidateRequest, tuple[str, ...]](
            baseline=_InstalledSkillCandidates(),
            config=router.decisions.config,
            accelerator_factory=skill_accelerator,
            authorize_accelerator=skill_authorizer,
            # A Skill selector (JEV) may narrow the tools, but never to a set
            # holding an excluded Skill's tools (coding, owner 2026-10-06):
            # such a narrowing falls back to the whole catalogue and the model
            # chooses, so the selector alone never turns a task into coding.
            accept_accelerator=lambda request, candidate: _valid_skill_subset(
                request, candidate
            ) and not any(
                name.split("__", 1)[0] in accelerator_excluded_aliases
                for name in candidate.value
            ),
            observer=decision_observer,
            shadow_observer=skill_shadow_observer,
        )
        # Sees each finished conversation turn (which tools the model called),
        # so a shadow accelerator's choices can be compared with the outcome.
        self._conversation_observer = conversation_observer
        # One conversation tool per Knowledge vault (owner decision 2026-10-06):
        # a Skill command naming `knowledge_capability` is offered once per
        # vault, described by the vault's own purpose and boundaries, with the
        # vault bound by the host and only the question left to the model.
        self._knowledge_vaults = knowledge_vaults
        self._knowledge_capability = knowledge_capability

    def _vault_tools(
        self,
        alias: str,
        instructions: str,
        command: CommandBinding,
        bindings: dict[str, CommandBinding],
        bound: dict[str, dict[str, JsonValue]],
        tools: list[ModelTool],
        hints: dict[str, str],
    ) -> None:
        assert self._knowledge_vaults is not None
        for vault in self._knowledge_vaults():
            asset = vault.asset
            name = f"{alias}__{asset.name}"
            if name in bindings:
                name = f"{name}.{asset.version}"
            if name in bindings:
                continue
            outside = f" It does not cover: {vault.boundaries}" if vault.boundaries else ""
            bindings[name] = command
            bound[name] = {"asset": asset.model_dump(mode="json")}
            hints[name] = vault.purpose[:240]
            tools.append(ModelTool(
                name=name,
                description=(
                    f"Ask the Knowledge vault {asset.namespace}/{asset.name}@{asset.version}. "
                    f"It covers: {vault.purpose}.{outside} {instructions}"
                ),
                input_contract="platform.command-arguments.v1",
                input_schema=VAULT_QUESTION_SCHEMA,
            ))

    async def converse(
        self,
        request: RequestContext,
        history: tuple[ModelMessage, ...],
        *,
        persona_guidance: str | None = None,
        allowed_tools: frozenset[str] | None = None,
        max_turns: int = MAX_CONVERSATION_TURNS,
        max_history_messages: int = MAX_CONVERSATION_HISTORY,
    ) -> GatewayConversationResult:
        result = await self._converse(
            request, history, persona_guidance=persona_guidance, allowed_tools=allowed_tools,
            max_turns=max_turns, max_history_messages=max_history_messages,
        )
        if self._conversation_observer is not None:
            try:
                self._conversation_observer(result)
            except Exception:
                # Telemetry cannot change the answer a person receives.
                pass
        return result

    async def _converse(
        self,
        request: RequestContext,
        history: tuple[ModelMessage, ...],
        *,
        persona_guidance: str | None = None,
        allowed_tools: frozenset[str] | None = None,
        max_turns: int = MAX_CONVERSATION_TURNS,
        max_history_messages: int = MAX_CONVERSATION_HISTORY,
    ) -> GatewayConversationResult:
        """Use installed commands as tools in a bounded loop (`MAX_CONVERSATION_TOOL_CALLS`).

        The model receives aliases for installed commands, never raw capability
        authority. Every accepted call is resolved back to its manifest target
        and dispatched through the same Bridge/Workflow boundaries as any other
        ingress. Unknown calls are observations for one bounded repair attempt;
        they are never executed.
        """
        context = RequestContext.model_validate(request)
        if isinstance(max_turns, bool) or not 1 <= max_turns <= MAX_CONVERSATION_TURNS:
            raise ValueError(
                f"Gateway conversation supports one to {MAX_CONVERSATION_TURNS} turns"
            )
        if isinstance(max_history_messages, bool) or not 1 <= max_history_messages <= 40:
            raise ValueError("Gateway conversation supports one to forty history messages")
        if any(
            message.role not in {"user", "assistant"}
            or message.images
            or message.tool_calls
            or message.tool_call_id is not None
            for message in history
        ):
            return self._conversation_failure(context, "conversation_history_invalid", 0, ())
        if self.router.model is None:
            return self._conversation_failure(context, "model_not_configured", 0, ())
        bindings: dict[str, CommandBinding] = {}
        # Arguments the host fixes for a tool; the model never sees or sets them.
        bound: dict[str, dict[str, JsonValue]] = {}
        tools: list[ModelTool] = []
        hints: dict[str, str] = {}
        for skill in self.router.commands.skills.discover(context.namespace):
            for command in skill.commands:
                if (
                    command.kind == "capability"
                    and self.bridge.installed.get(command.target) is None
                ):
                    continue
                if command.kind == "workflow" and self.engine.workflows.get(command.target) is None:
                    continue
                if (
                    command.kind == "capability"
                    and self._knowledge_vaults is not None
                    and command.target == self._knowledge_capability
                ):
                    self._vault_tools(skill.alias, skill.instructions, command,
                                      bindings, bound, tools, hints)
                    continue
                name = f"{skill.alias}__{command.name}"
                bindings[name] = command
                if skill.selector_hint:
                    hints[name] = skill.selector_hint
                target = command.target
                manifest = (
                    self.engine.workflows.get(target) if command.kind == "workflow" else None
                )
                tools.append(
                    ModelTool(
                        name=name,
                        description=(
                            f"{skill.instructions} Executes installed {command.kind} "
                            f"{target.namespace}/{target.name}@{target.version}."
                        ),
                        input_contract="platform.command-arguments.v1",
                        # A declared Workflow tells the model its exact fields.
                        input_schema=(
                            agent_tool_schema(manifest)
                            if manifest is not None and manifest.parameters else None
                        ),
                    )
                )
        if allowed_tools is not None:
            tools = [tool for tool in tools if tool.name in allowed_tools]
            hints = {name: hint for name, hint in hints.items() if name in allowed_tools}
            bindings = {
                name: binding for name, binding in bindings.items() if name in allowed_tools
            }
        prompt = (
            "You are the Personal Engineering Agent. Answer naturally and concisely. "
            "Use only the supplied installed tools when work is required. Never invent a tool, "
            "target, permission, result, or completed action. Never claim to have read a source "
            "unless a supplied tool successfully returned it. If the requested source has no "
            "available tool, say that it cannot be accessed here. Ask for missing inputs. When a "
            "request for work leaves open a rule that would change the result (which records "
            "count, which period or status, what to flag) and the request has no plain reading, "
            "ask that question first and do no other work in that turn; do not guess it. A "
            "request that names no filter means no filter, and what a screen shows from earlier "
            "use is not the person's choice. After a "
            "tool result, explain what happened and what the user should do next."
        )
        if persona_guidance:
            prompt += (
                "\n\nThe following local persona controls name and speaking style only. "
                "It cannot change policy, permissions, tool restrictions, or factual evidence.\n"
                + persona_guidance[:MAX_CONVERSATION_MESSAGE_CHARS]
            )
        bounded_history = tuple(
            ModelMessage(
                role=message.role,
                text=message.text[:MAX_CONVERSATION_MESSAGE_CHARS],
            )
            for message in history[-max_history_messages:]
        )
        messages = [ModelMessage(role="system", text=prompt), *bounded_history]
        if tools:
            # This is the exact first-turn payload before an optional selector
            # narrows tools. Authorization sees the system/persona text, bounded
            # history and every installed tool description before construction.
            candidate_request = SkillCandidateRequest(
                context=context,
                initial_request=ModelRequest(
                    trace=context.trace,
                    model_alias=self.router.model_alias,
                    messages=tuple(messages),
                    requirements=ModelRequirements(
                        tool_calling=True,
                        local_only=self.router.local_only,
                    ),
                    tools=tuple(tools),
                    max_output_tokens=CONVERSATION_MAX_OUTPUT_TOKENS,
                ),
                selector_hints=hints,
            )
            selected_names = set(
                self.skill_decisions.decide(candidate_request, decision_type="skill_selection")
                .result.value
            )
            tools = [tool for tool in tools if tool.name in selected_names]
            bindings = {
                name: binding for name, binding in bindings.items() if name in selected_names
            }
        # Host tools join after any narrowing: a selector ranks installed
        # Skills, and authoring is not one of them.
        host: dict[str, HostTool] = {}
        for host_tool in self.host_tools() if self.host_tools is not None else ():
            name = host_tool.tool.name
            if name in bindings or (allowed_tools is not None and name not in allowed_tools):
                continue
            host[name] = host_tool
            tools.append(host_tool.tool)
        evidence: list[ConversationToolExecution] = []
        truncated_retries = 0
        for turn in range(1, max_turns + 1):
            model_request = ModelRequest(
                trace=context.trace,
                model_alias=self.router.model_alias,
                messages=tuple(messages),
                requirements=ModelRequirements(
                    tool_calling=bool(tools),
                    local_only=self.router.local_only,
                ),
                tools=tuple(tools),
                max_output_tokens=CONVERSATION_MAX_OUTPUT_TOKENS,
            )
            try:
                response = await asyncio.to_thread(self.router.model.generate, model_request)
            except Exception:
                return self._conversation_failure(
                    context, "model_unavailable", turn, tuple(evidence)
                )
            if (
                response.failure is not None
                and response.failure.code == "model_output_truncated"
                and truncated_retries < MAX_TRUNCATED_RETRIES
                and turn < max_turns
            ):
                # The reply was cut at the output limit (lab fix-005 D04): say so
                # and let the model answer again more briefly within this turn.
                truncated_retries += 1
                messages.append(ModelMessage(role="user", text=TRUNCATED_NOTICE))
                continue
            if response.failure is not None:
                return GatewayConversationResult(
                    trace=context.trace,
                    status="failed",
                    text="The configured model could not answer this turn.",
                    model_turns=turn,
                    tools=tuple(evidence),
                    failure=response.failure,
                )
            if response.trace != context.trace or response.model_alias != self.router.model_alias:
                return self._conversation_failure(
                    context, "model_context_mismatch", turn, tuple(evidence)
                )
            if not response.tool_calls:
                if response.text.strip():
                    return GatewayConversationResult(
                        trace=context.trace,
                        status="answered",
                        text=response.text,
                        model_turns=turn,
                        tools=tuple(evidence),
                    )
                return self._conversation_failure(
                    context, "empty_model_answer", turn, tuple(evidence)
                )
            # A reply may carry several calls; each runs in order and counts
            # against the turn's budget. Every call gets a tool message back,
            # as the provider requires, even one the budget no longer allows.
            messages.append(
                ModelMessage(
                    role="assistant",
                    text=response.text,
                    tool_calls=response.tool_calls,
                )
            )
            for call in response.tool_calls:
                if len(evidence) >= MAX_CONVERSATION_TOOL_CALLS:
                    messages.append(ModelMessage(
                        role="tool", tool_call_id=call.call_id,
                        text=json.dumps({"skipped": "the turn's tool budget is used up"}),
                    ))
                    continue
                binding = bindings.get(call.name)
                if call.name in host:
                    _tool_progress(call.name, "running")
                    item = await self._execute_host_tool(context, call, host[call.name])
                    _tool_progress(call.name, "succeeded" if _tool_succeeded(item) else "failed")
                elif binding is None:
                    item = ConversationToolExecution(
                        call_id=call.call_id,
                        name=call.name,
                        failure=Failure(
                            code="uninstalled_tool",
                            message="The model named a tool that is not installed",
                        ),
                    )
                else:
                    _tool_progress(call.name, "running")
                    item = await self._execute_conversation_tool(
                        context, call, binding, bound.get(call.name)
                    )
                    _tool_progress(call.name, "succeeded" if _tool_succeeded(item) else "failed")
                evidence.append(item)
                observation = json.dumps(item.model_dump(mode="json"), ensure_ascii=False)
                if len(observation) > MAX_TOOL_OBSERVATION_CHARS:
                    observation = json.dumps(
                        {
                            "truncated": True,
                            "preview": observation[:MAX_TOOL_OBSERVATION_CHARS],
                        },
                        ensure_ascii=False,
                    )
                messages.append(
                    ModelMessage(
                        role="tool",
                        tool_call_id=call.call_id,
                        text=observation,
                    )
                )
            if len(evidence) >= MAX_CONVERSATION_TOOL_CALLS:
                break
        return self._conversation_failure(
            context, "tool_loop_limit", min(max_turns, len(evidence)), tuple(evidence)
        )

    @staticmethod
    async def _execute_host_tool(
        context: RequestContext, call: ModelToolCall, item: HostTool
    ) -> ConversationToolExecution:
        try:
            outcome = await item.handler(context, dict(call.arguments))
        except Exception as error:  # noqa: BLE001 - a host fault is an observation
            return ConversationToolExecution(
                call_id=call.call_id, name=call.name,
                failure=Failure(code="host_tool_failed", message=type(error).__name__),
            )
        return ConversationToolExecution(call_id=call.call_id, name=call.name, host=outcome)

    async def _execute_conversation_tool(
        self,
        context: RequestContext,
        call: ModelToolCall,
        binding: CommandBinding,
        bound: dict[str, JsonValue] | None = None,
    ) -> ConversationToolExecution:
        decision = RouteDecision(
            kind=binding.kind,
            target=binding.target,
            reason="Model selected an installed conversation tool",
        )
        if binding.kind == "capability":
            invocation_arguments = dict(call.arguments)
            if bound is not None:
                # Only the question comes from the model; the vault is the
                # host's, so a model cannot point the tool at another vault.
                invocation_arguments = {
                    key: value for key, value in invocation_arguments.items()
                    if key == "question"
                } | bound
            result = await self.bridge.execute(
                CapabilityInvocation(
                    context=context,
                    target=binding.target,
                    arguments=invocation_arguments,
                )
            )
            return ConversationToolExecution(
                call_id=call.call_id,
                name=call.name,
                decision=decision,
                capability=result,
            )
        arguments: dict[str, JsonValue] = dict(call.arguments)
        manifest = self.engine.workflows.get(binding.target)
        if manifest is not None and manifest.parameters:
            # The model may fill only the fields its schema offered; a
            # privileged or internal field stays a person's choice.
            offered = {field.name for field in agent_fields(manifest)}
            refused = sorted(set(arguments) - offered)
            try:
                if refused:
                    raise WorkflowParameterError(
                        f"{', '.join(refused)} cannot be set by the Agent"
                    )
                arguments = validate_run_parameters(manifest, arguments)
            except WorkflowParameterError as error:
                return ConversationToolExecution(
                    call_id=call.call_id,
                    name=call.name,
                    failure=Failure(code="workflow_parameters_invalid", message=str(error)),
                )
        snapshot = await self.execute_workflow(context, binding.target, arguments)
        return ConversationToolExecution(
            call_id=call.call_id,
            name=call.name,
            decision=decision,
            workflow=snapshot,
        )

    @staticmethod
    def _conversation_failure(
        context: RequestContext,
        code: str,
        turns: int,
        tools: tuple[ConversationToolExecution, ...],
    ) -> GatewayConversationResult:
        return GatewayConversationResult(
            trace=context.trace,
            status=(
                "needs_input"
                if code in {"model_not_configured", "no_installed_tools", "tool_loop_limit"}
                else "failed"
            ),
            text=(
                "I need more information or a supported installed tool before I can continue."
                if code in {"model_not_configured", "no_installed_tools", "tool_loop_limit"}
                else "The Personal Agent could not complete this turn."
            ),
            model_turns=turns,
            tools=tools,
            failure=Failure(code=code, message="The bounded conversation loop stopped"),
        )

    async def handle(
        self,
        request: RequestContext,
        *,
        workflow_timeout_seconds: float | None = None,
        workflow_idempotency_key: IdempotencyKey | None = None,
    ) -> GatewayResult:
        context = RequestContext.model_validate(request)
        # Routing is synchronous and the model client owns blocking I/O, so it
        # must never run on the event loop where driving tasks live.
        outcome = await asyncio.to_thread(self.router.route, context)
        decision = outcome.decision
        if decision.kind == "capability" and decision.target is not None:
            if workflow_idempotency_key is not None:
                return GatewayResult(
                    routing=outcome,
                    capability=CapabilityResult(
                        trace=context.trace,
                        status="unavailable",
                        failure=Failure(
                            code="idempotency_not_supported",
                            message="Idempotency keys require a workflow route",
                        ),
                    ),
                )
            result = await self.bridge.execute(
                CapabilityInvocation(
                    context=context, target=decision.target, arguments=outcome.arguments
                )
            )
            return GatewayResult(routing=outcome, capability=result)
        if decision.kind == "workflow" and decision.target is not None:
            snapshot = await self.execute_workflow(
                context,
                decision.target,
                outcome.arguments,
                workflow_timeout_seconds=workflow_timeout_seconds,
                workflow_idempotency_key=workflow_idempotency_key,
            )
            return GatewayResult(routing=outcome, workflow=snapshot)
        # needs_input: nothing executes. A resolved decision without a target is
        # impossible by contract and would fail GatewayResult validation loudly.
        return GatewayResult(routing=outcome)

    async def execute_workflow(
        self,
        request: RequestContext,
        workflow: AssetIdentity,
        arguments: dict[str, JsonValue] | None = None,
        *,
        workflow_timeout_seconds: float | None = None,
        workflow_idempotency_key: IdempotencyKey | None = None,
    ) -> WorkflowRunSnapshot:
        """Exact-target host entry point shared by routed workflows and integrations.

        No routing/model call and no added authority. The engine owns validation,
        execution policy, idempotency and the default caller-wait timeout.
        """
        # The engine's run table belongs to one event loop at a time, and a
        # workflow may change shared resources: serialize runs across threads.
        with self.bridge.exclusive:
            if workflow_timeout_seconds is None:
                return await self.engine.execute(
                    request, workflow, arguments, idempotency_key=workflow_idempotency_key
                )
            return await self.engine.execute(
                request,
                workflow,
                arguments,
                timeout_seconds=workflow_timeout_seconds,
                idempotency_key=workflow_idempotency_key,
            )

    def inspect(self, request: RequestContext, run_id: RunId) -> RunControlResult:
        """Classify a run's steps for its owner; never executes anything.

        The durable record answers whenever it exists, because it alone knows
        whether a run has been suspended or already continued; this process's
        own history answers for everything else. `source` says which.

        Durable reads happen on the calling thread: a host already inside an
        event loop should call this through `asyncio.to_thread`.
        """
        entry = self.engine.inspect_journal(request, run_id)
        if entry is not None:
            return RunControlResult(
                action="inspect",
                run_id=run_id,
                source="journal",
                plan=entry.plan,
                suspended_by=entry.suspended_by,
            )
        plan = self.engine.inspect(request, run_id)
        if plan is None:
            return RunControlResult(action="inspect", run_id=run_id)
        return RunControlResult(action="inspect", run_id=run_id, source="memory", plan=plan)

    def suspend(
        self, request: RequestContext, run_id: RunId, confirmation: SuspensionConfirmation
    ) -> RunControlResult:
        """Record a person's confirmation that the process owning a run is gone.

        Only a journalled run can be suspended, because only durable evidence
        outlives the process whose absence is being confirmed. A run this caller
        cannot see is `unknown`, like everywhere else; a run that is alive here
        or already suspended raises the engine's own closed code rather than a
        second vocabulary invented at this layer.

        Durable writes happen on the calling thread: a host already inside an
        event loop should call this through `asyncio.to_thread`.
        """
        try:
            entry = self.engine.suspend(request, run_id, confirmation)
        except CheckpointStoreError as error:
            if error.code != "missing":
                raise
            entry = None
        if entry is None:
            return RunControlResult(action="suspend", run_id=run_id)
        return RunControlResult(
            action="suspend",
            run_id=run_id,
            source="journal",
            plan=entry.plan,
            suspended_by=entry.suspended_by,
        )

    def retire(self, request: RequestContext, run_id: RunId) -> RunControlResult:
        """Remove a finished run's durable history; the plan reports what went.

        Only durable history is retired — this process's bounded memory evicts
        itself — and only a run that is no longer executing qualifies: succeeded,
        or suspended by a person's confirmation; the store's own closed code says
        why otherwise. A run this caller cannot see
        is `unknown`. Durable writes happen on the calling thread.
        """
        try:
            entry = self.engine.retire(request, run_id)
        except CheckpointStoreError as error:
            if error.code != "missing":
                raise
            entry = None
        if entry is None:
            return RunControlResult(action="retire", run_id=run_id)
        return RunControlResult(
            action="retire",
            run_id=run_id,
            source="journal",
            plan=entry.plan,
            suspended_by=entry.suspended_by,
        )

    async def resume(
        self,
        request: RequestContext,
        run_id: RunId,
        *,
        policy: ResumePolicy | None = None,
        workflow_timeout_seconds: float | None = None,
    ) -> RunControlResult:
        """Continue a finished run through the same engine contract as routed workflows.

        A journalled run is continued through recovery, so its continuation is
        journalled too and the durable "continued once" guard is honoured; every
        other run uses the in-memory path. The policy is a host/caller option and
        is never derived from the request message or a model. Run control is not
        a Skill route, so no model-selected route can trigger it; ownership and
        authorization stay in the engine.
        """
        # Reading the durable record touches the disk under the store's lock, so
        # it never runs on the event loop the in-flight runs share.
        journalled = (
            await asyncio.to_thread(self.engine.inspect_journal, request, run_id) is not None
        )
        timeout = (
            {}
            if workflow_timeout_seconds is None
            else {"timeout_seconds": workflow_timeout_seconds}
        )
        snapshot = (
            await self.engine.recover(request, run_id, policy, **timeout)
            if journalled
            else await self.engine.resume(request, run_id, policy, **timeout)
        )
        if snapshot is None:
            return RunControlResult(action="resume", run_id=run_id)
        return RunControlResult(
            action="resume",
            run_id=run_id,
            source="journal" if journalled else "memory",
            workflow=snapshot,
        )

    def watch(self, request: RequestContext, run_id: RunId) -> ProgressStream | None:
        """Bounded progress stream for the run's owner through the same engine contract.

        None means the run is unknown to this caller. The stream carries
        identities, statuses and codes only, never payloads, and never blocks
        the run; the Gateway adds no authority.
        """
        # Malformed ids fail loudly here like inspect/resume; typos are unknown runs.
        return self.engine.watch(request, TypeAdapter(RunId).validate_python(run_id))
