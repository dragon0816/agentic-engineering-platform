"""Platform entry point: dispatch contracts behind deterministic-first routing.

The Gateway adds no authority and holds no domain logic. Capability dispatch is
authorized by LocalPolicy inside the Bridge; workflow pre-flights belong to the
engine. Model-selected routes dispatch through exactly the same contract as
deterministic ones, so a trigger's origin never changes what may execute.
"""

import asyncio
import json
from typing import Literal, Self

from pydantic import Field, JsonValue, TypeAdapter, model_validator

from agent.routing import RequestRouter, RoutingOutcome
from agent.skills import CommandBinding
from capabilities.runtime import CapabilityInvocation
from common.assets import AssetIdentity
from common.base import Contract, Symbol
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

MAX_CONVERSATION_HISTORY = 12
MAX_CONVERSATION_MESSAGE_CHARS = 4_000
MAX_TOOL_OBSERVATION_CHARS = 16_000


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


class ConversationToolExecution(Contract):
    """Evidence for one model-proposed call after installed-target lookup."""

    call_id: Symbol
    name: Symbol
    decision: RouteDecision | None = None
    capability: CapabilityResult | None = None
    workflow: WorkflowRunSnapshot | None = None
    failure: Failure | None = None

    @model_validator(mode="after")
    def one_outcome(self) -> Self:
        outcomes = (
            self.capability is not None,
            self.workflow is not None,
            self.failure is not None,
        )
        if sum(outcomes) != 1:
            raise ValueError("a tool call has exactly one execution outcome")
        if self.failure is not None and self.decision is not None:
            raise ValueError("a refused tool call selected no execution target")
        if self.decision is None and self.failure is None:
            raise ValueError("an executed tool call records its exact target")
        return self


class GatewayConversationResult(Contract):
    """Bounded Agent loop result. The transcript itself grants no authority."""

    trace: TraceIdentifiers
    status: Literal["answered", "needs_input", "failed"]
    text: str
    model_turns: int = Field(ge=0, le=5, strict=True)
    tools: tuple[ConversationToolExecution, ...] = Field(default=(), max_length=4)
    failure: Failure | None = None

    @model_validator(mode="after")
    def terminal_state(self) -> Self:
        if (self.status == "answered") == (self.failure is not None):
            raise ValueError("only an answered conversation omits failure details")
        return self


class Gateway:
    def __init__(self, router: RequestRouter, bridge: BridgeExecutor, engine: WorkflowEngine):
        self.router = router
        self.bridge = bridge
        self.engine = engine

    async def converse(
        self,
        request: RequestContext,
        history: tuple[ModelMessage, ...],
    ) -> GatewayConversationResult:
        """Use installed commands as tools in a five-turn/four-call maximum loop.

        The model receives aliases for installed commands, never raw capability
        authority. Every accepted call is resolved back to its manifest target
        and dispatched through the same Bridge/Workflow boundaries as any other
        ingress. Unknown calls are observations for one bounded repair attempt;
        they are never executed.
        """
        context = RequestContext.model_validate(request)
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
        tools: list[ModelTool] = []
        for skill in self.router.commands.skills.discover(context.namespace):
            for command in skill.commands:
                name = f"{skill.alias}__{command.name}"
                bindings[name] = command
                target = command.target
                tools.append(
                    ModelTool(
                        name=name,
                        description=(
                            f"{skill.instructions} Executes installed {command.kind} "
                            f"{target.namespace}/{target.name}@{target.version}."
                        ),
                        input_contract="platform.command-arguments.v1",
                    )
                )
        if not tools:
            return self._conversation_failure(context, "no_installed_tools", 0, ())

        prompt = (
            "You are the Personal Engineering Agent. Answer naturally and concisely. "
            "Use only the supplied installed tools when work is required. Never invent a tool, "
            "target, permission, result, or completed action. Ask for missing inputs. After a "
            "tool result, explain what happened and what the user should do next."
        )
        bounded_history = tuple(
            ModelMessage(
                role=message.role,
                text=message.text[:MAX_CONVERSATION_MESSAGE_CHARS],
            )
            for message in history[-MAX_CONVERSATION_HISTORY:]
        )
        messages = [ModelMessage(role="system", text=prompt), *bounded_history]
        evidence: list[ConversationToolExecution] = []
        for turn in range(1, 6):
            model_request = ModelRequest(
                trace=context.trace,
                model_alias=self.router.model_alias,
                messages=tuple(messages),
                requirements=ModelRequirements(
                    tool_calling=True,
                    local_only=self.router.local_only,
                ),
                tools=tuple(tools),
                max_output_tokens=1024,
            )
            try:
                response = await asyncio.to_thread(self.router.model.generate, model_request)
            except Exception:
                return self._conversation_failure(
                    context, "model_unavailable", turn, tuple(evidence)
                )
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
            if len(response.tool_calls) != 1:
                return self._conversation_failure(
                    context, "multiple_tool_calls_not_supported", turn, tuple(evidence)
                )
            call = response.tool_calls[0]
            binding = bindings.get(call.name)
            if binding is None:
                item = ConversationToolExecution(
                    call_id=call.call_id,
                    name=call.name,
                    failure=Failure(
                        code="uninstalled_tool",
                        message="The model named a tool that is not installed",
                    ),
                )
            else:
                item = await self._execute_conversation_tool(context, call, binding)
            evidence.append(item)
            messages.append(
                ModelMessage(
                    role="assistant",
                    text=response.text,
                    tool_calls=response.tool_calls,
                )
            )
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
            if len(evidence) >= 4:
                break
        return self._conversation_failure(
            context, "tool_loop_limit", min(5, len(evidence)), tuple(evidence)
        )

    async def _execute_conversation_tool(
        self,
        context: RequestContext,
        call: ModelToolCall,
        binding: CommandBinding,
    ) -> ConversationToolExecution:
        decision = RouteDecision(
            kind=binding.kind,
            target=binding.target,
            reason="Model selected an installed conversation tool",
        )
        if binding.kind == "capability":
            result = await self.bridge.execute(
                CapabilityInvocation(
                    context=context,
                    target=binding.target,
                    arguments=call.arguments,
                )
            )
            return ConversationToolExecution(
                call_id=call.call_id,
                name=call.name,
                decision=decision,
                capability=result,
            )
        snapshot = await self.execute_workflow(context, binding.target, call.arguments)
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
