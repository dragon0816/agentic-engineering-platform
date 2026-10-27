"""Multi-agent V1: a parent turn delegates one objective to a sub-agent profile.

ADR-MA1–MA5 (`docs/DECISIONS.md` 2026-10-26) and the contract in
`docs/CONTRACTS.md` "Multi-agent delegation (V1)". The parent model calls the
`agent__delegate` Host tool; the Host runs a bounded sub-conversation through
the same `Gateway.converse` loop, guards, approved model client (the session's
model), claim check and Host-check retry, then returns a typed result.

- **Who may be a target:** a profile the active profile lists in
  `may_delegate_to`, or another installed one the person's own message names;
  each validated by the Host (`DelegationCatalog`). No ranker.
- **What the sub-agent may use:** the parent turn's installed Skill tools ∩ the
  target's Skills / capabilities / Knowledge ∩ what the parent actor is
  authorized for ∩ the requested subset. Never a Host tool, never wider (fail
  closed). It acts as the parent actor (ADR-MA4).
- **What it sees:** the objective and the listed session artifacts; not the
  parent's history, persona, memory or session list (ADR-MA5).
- **Bounds:** depth 1, three per parent turn, the profile's turns, tool cap
  and time limit, within the parent turn's own time.
- **Never asks the person (rule 18):** it answers `NEEDS_INPUT: <question>`
  and the parent decides.
- **Writes** still need the person's confirmation: the existing approval
  request lands in the parent session.
- **One side effect per turn (rule 21):** the sub-run shares the parent turn's
  side-effect record.
- **Results** keep the sub-run's Host notes (G1), are capped with a note (G4),
  and their artifacts go to the parent session ledger (rule 20).
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, Self

from pydantic import Field, JsonValue, ValidationError, model_validator

import telemetry.recorder as telemetry
from agent import delegation_scope, turn_progress
from agent.backend_contracts import ConversationLimits
from agent.contracts import AgentProfile
from agent.conversation_harness import NOTE_MARK
from agent.delegation_scope import (
    DELEGATE_TOOL,
    MAX_DELEGATIONS_PER_TURN,
    DelegationTurn,
)
from agent.gateway import (
    MAX_CONVERSATION_MESSAGE_CHARS,
    TOOL_PROGRESS,
    ConversationToolExecution,
    Gateway,
    GatewayConversationResult,
    HostTool,
    HostToolOutcome,
)
from agent.harness_handoff import capped, unverified
from common.assets import AssetIdentity
from common.base import Contract, Symbol, Text
from common.execution import Failure, RequestContext, TraceIdentifiers
from models.contracts import ModelMessage, ModelTool

#: A retry starts only with this much of the time limit left.
MIN_RETRY_SECONDS = 30
#: The sub-agent's answer as the parent sees it (G4: cut with a note).
DELEGATION_OUTPUT_LIMIT_CHARS = 8_000
MAX_FINDINGS = 20
MAX_FINDING_CHARS = 500
MAX_INPUT_ARTIFACTS = 10
#: How much of one text artifact a sub-agent is given, and of all of them.
MAX_ARTIFACT_TEXT_CHARS = 4_000
MAX_ARTIFACTS_TEXT_CHARS = 30_000
_TEXT_SUFFIXES = frozenset({".md", ".txt", ".csv", ".json", ".log", ".tsv", ".yaml", ".yml"})
#: The sub-agent's way to hand a question back instead of asking the person.
NEEDS_INPUT_MARK = "NEEDS_INPUT:"
_BULLET = re.compile(r"^\s*(?:[-*•]|\d{1,2}[.)])\s+(.+)$")
_REFERENCE = re.compile(
    r"^(?P<namespace>[a-z0-9]+(?:-[a-z0-9]+)*)/(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)"
    r"(?:@(?P<version>\S+))?$"
)

DelegationStatus = Literal["succeeded", "needs_input", "awaiting_approval", "failed"]


class DelegationRequest(Contract):
    """What the parent model passes to `agent__delegate`."""

    profile: str = Field(min_length=3, max_length=200)
    objective: Text = Field(max_length=MAX_CONVERSATION_MESSAGE_CHARS)
    input_artifact_ids: tuple[Symbol, ...] = Field(default=(), max_length=MAX_INPUT_ARTIFACTS)
    tools: tuple[Symbol, ...] | None = Field(default=None, max_length=40)


class DelegationArtifact(Contract):
    kind: Literal["run", "file"]
    id: Symbol
    name: Text
    status: str | None = None


class DelegationToolCall(Contract):
    name: Symbol
    status: Literal["succeeded", "failed", "awaiting_approval"]
    replayed: bool = False


class DelegationTokens(Contract):
    input: int | None = Field(default=None, ge=0)
    output: int | None = Field(default=None, ge=0)
    model_calls: int = Field(default=0, ge=0)


class DelegationResult(Contract):
    """The typed result a parent turn gets back (counts and text, no paths)."""

    status: DelegationStatus
    profile: str
    summary: str = ""
    findings: tuple[str, ...] = Field(default=(), max_length=MAX_FINDINGS)
    question: str | None = None
    artifacts: tuple[DelegationArtifact, ...] = ()
    approvals: tuple[str, ...] = ()
    tool_calls: tuple[DelegationToolCall, ...] = ()
    tokens: DelegationTokens = DelegationTokens()
    read_only: bool = True
    validated: bool = False
    host_note: str | None = None
    elapsed_s: float = Field(default=0.0, ge=0)
    failure: Failure | None = None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if (self.status == "failed") != (self.failure is not None):
            raise ValueError("only a failed delegation carries a failure")
        if (self.status == "needs_input") != (self.question is not None):
            raise ValueError("only a needs_input delegation carries a question")
        return self


@dataclass(frozen=True)
class DelegationTarget:
    """A validated profile a parent may delegate to. `listed`: in the active
    profile's `may_delegate_to`; otherwise only when the person names it."""

    profile: AgentProfile
    listed: bool

    @property
    def key(self) -> str:
        identity = self.profile.metadata.identity
        return f"{identity.namespace}/{identity.name}@{identity.version}"


@dataclass(frozen=True)
class DelegationCatalog:
    """The Host's validated targets for this turn, and the listed ones that
    did not validate (refused as unavailable rather than unknown)."""

    targets: tuple[DelegationTarget, ...] = ()
    unavailable: tuple[AssetIdentity, ...] = ()


class SessionLedger(Protocol):
    """What delegation needs of the session ledger (`SessionArtifacts`)."""

    def ledger(self, session_id: str, actor: str) -> Any: ...

    def resolve(self, session_id: str | None, actor: str, artifact_id: object) -> Any: ...

    def record_run(self, session_id: str | None, actor: str, snapshot: Any) -> Any: ...


class DelegationRefused(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class _Plan:
    target: DelegationTarget
    request: DelegationRequest
    tools: tuple[str, ...]
    read_only: bool


INPUT_SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "profile": {
            "type": "string",
            "description": "The sub-agent profile, namespace/name or namespace/name@version, "
            "from the list in this tool's description.",
        },
        "objective": {
            "type": "string",
            "maxLength": MAX_CONVERSATION_MESSAGE_CHARS,
            "description": "One self-contained task for the sub-agent, with every fact it "
            "needs: it sees nothing else of this conversation.",
        },
        "input_artifact_ids": {
            "type": "array",
            "maxItems": MAX_INPUT_ARTIFACTS,
            "items": {"type": "string"},
            "description": "Optional. Ids of files (f<n>) or runs this session produced that "
            "the sub-agent should use.",
        },
        "tools": {
            "type": "array",
            "maxItems": 40,
            "items": {"type": "string"},
            "description": "Optional. Narrow the sub-agent to these of its tools.",
        },
    },
    "required": ["profile", "objective"],
    "additionalProperties": False,
}


def _role(target: DelegationTarget) -> str:
    profile = target.profile
    constraints = "".join(f"\n- {item}" for item in profile.policy_constraints[:10])
    return (
        f'You are the delegated specialist sub-agent "{target.key}": {profile.description} '
        "Another agent gave you one objective; you work for it, not directly for the person, "
        "and you cannot see its conversation. Use only the supplied tools. Never ask the person "
        "anything and never offer choices: if you cannot finish without information only the "
        f"person has, reply with exactly one line starting {NEEDS_INPUT_MARK} followed by that "
        "one question, and nothing else. Otherwise answer with a short summary, then the key "
        'findings as lines starting with "- ", each naming its source when a tool gave one. '
        "Never claim an action or a source that no tool call of yours backs."
        + (f"\nConstraints of this profile:{constraints}" if constraints else "")
    )


def _retry_worthy(answer: GatewayConversationResult) -> bool:
    """Whether a finished sub-run that did not answer should be tried again."""
    # Only a failure the model layer marked retryable (a timeout, a dropped
    # connection, a provider error); a refusal or a missing answer is final.
    if answer.status == "answered" or answer.failure is None:
        return False
    return answer.failure.retryable


def _findings(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for line in text.splitlines():
        match = _BULLET.match(line)
        if match and match.group(1).strip():
            found.append(match.group(1).strip()[:MAX_FINDING_CHARS])
        if len(found) >= MAX_FINDINGS:
            break
    return tuple(found)


CallStatus = Literal["succeeded", "failed", "awaiting_approval"]


def _tool_status(item: ConversationToolExecution) -> CallStatus:
    if item.failure is not None:
        return "failed"
    if item.host is not None:
        if item.host.status == "awaiting_approval":
            return "awaiting_approval"
        return "succeeded" if item.host.status == "succeeded" else "failed"
    if item.capability is not None:
        return "succeeded" if item.capability.status == "succeeded" else "failed"
    ran = item.workflow is not None and item.workflow.run.status == "succeeded"
    return "succeeded" if ran else "failed"


def _not_validated_harness(tools: Sequence[ConversationToolExecution]) -> bool:
    """A domain Harness result in the sub-run that did not pass its checks."""
    return any(
        item.host is not None
        and isinstance(item.host.data, dict)
        and item.host.data.get("harness_verdict") == "not_validated"
        for item in tools
    )


class DelegationService:
    """The `agent__delegate` Host tool and the sub-runs it starts."""

    def __init__(
        self,
        gateway: Gateway,
        *,
        enabled: Callable[[], bool],
        catalog: Callable[[], DelegationCatalog],
        ledger: SessionLedger | None = None,
    ) -> None:
        self.gateway = gateway
        self.enabled = enabled
        self.catalog = catalog
        self.ledger = ledger

    # -- the tool -------------------------------------------------------------

    def tools(self) -> tuple[HostTool, ...]:
        """The tool, only with the flag on, outside a sub-run, and with at least
        one target (CLI backends never reach the Gateway loop that offers it)."""
        if delegation_scope.in_sub_run():
            return ()
        try:
            if not self.enabled():
                return ()
            catalog = self.catalog()
        except Exception:  # noqa: BLE001 - an unreadable setting or profile offers nothing
            return ()
        if not catalog.targets:
            return ()
        return (
            HostTool(
                tool=ModelTool(
                    name=DELEGATE_TOOL,
                    description=self._description(catalog),
                    input_contract="platform.agent-delegate.v1",
                    input_schema=INPUT_SCHEMA,
                ),
                handler=self._handle,
                parallel=self._parallel,
            ),
        )

    @staticmethod
    def _description(catalog: DelegationCatalog) -> str:
        listed = [target for target in catalog.targets if target.listed]
        named = [target for target in catalog.targets if not target.listed]
        lines = [
            "Delegate one bounded, self-contained objective to a specialist sub-agent and get "
            "its typed result (status, summary, findings, artifacts). Use it when a specialist "
            "below fits part of the work; you stay responsible for the answer. The sub-agent "
            "sees only the objective and the artifacts you list, cannot ask the person, and "
            f"uses only its own tools. At most {MAX_DELEGATIONS_PER_TURN} per turn; several "
            "read-only ones in one reply run side by side. When it returns needs_input, ask the "
            "person only that question."
        ]
        if listed:
            lines.append("Specialists you may delegate to:")
            for target in listed:
                hint = target.profile.selector_hint
                lines.append(
                    f"- {target.key}: {target.profile.description}"
                    + (f" Use for: {hint}" if hint else "")
                )
        if named:
            lines.append(
                "Only when the person's own message names one: "
                + ", ".join(target.key for target in named)
            )
        return "\n".join(lines)

    # -- planning (no side effects) ------------------------------------------------

    def _target(self, context: RequestContext, reference: str) -> DelegationTarget:
        match = _REFERENCE.match(reference.strip())
        if match is None:
            raise DelegationRefused(
                "delegation_arguments_invalid", "profile must be namespace/name[@version]"
            )
        namespace, name, version = match["namespace"], match["name"], match["version"]
        catalog = self.catalog()
        found = [
            target
            for target in catalog.targets
            if target.profile.metadata.identity.namespace == namespace
            and target.profile.metadata.identity.name == name
            and (version is None or target.profile.metadata.identity.version == version)
        ]
        if not found:
            if any(
                item.namespace == namespace
                and item.name == name
                and (version is None or item.version == version)
                for item in catalog.unavailable
            ):
                raise DelegationRefused(
                    "delegation_target_unavailable",
                    "That profile is listed but not usable on this machine now",
                )
            raise DelegationRefused(
                "delegation_target_not_allowed", "That profile is not a delegation target here"
            )
        if len(found) > 1:
            raise DelegationRefused(
                "delegation_profile_ambiguous", "Several versions match; name the exact version"
            )
        target = found[0]
        if not target.listed and not _names(context.message, target):
            raise DelegationRefused(
                "delegation_target_not_allowed",
                "This profile is used only when the person names it",
            )
        return target

    def _effective(
        self, context: RequestContext, profile: AgentProfile, requested: tuple[str, ...] | None
    ) -> tuple[tuple[str, ...], bool]:
        """Parent turn's Skill tools ∩ profile ∩ actor grants ∩ requested; and
        whether every one of them is a read."""
        skills = {item.key for item in profile.skills}
        capabilities = {item.key for item in profile.allowed_capabilities}
        vaults = {item.key for item in profile.knowledge}
        installed = self.gateway.bridge.installed
        policy = self.gateway.bridge.policy

        def authorized(target: AssetIdentity) -> tuple[bool, bool]:
            binding = installed.get(target)
            if binding is None or target.key not in capabilities:
                return False, False
            try:
                allowed = bool(policy.authorize(context, binding.spec).allowed)
            except Exception:  # noqa: BLE001 - an unreadable grant is no grant
                allowed = False
            return allowed, binding.spec.side_effect == "read"

        names: list[str] = []
        read_only = True
        for tool in self.gateway.skill_tools(context):
            if tool.skill.key not in skills:
                continue
            if requested is not None and tool.name not in requested:
                continue
            if tool.kind == "capability":
                allowed, reads = authorized(tool.target)
                if not allowed:
                    continue
                if tool.vault is not None and tool.vault.key not in vaults:
                    continue
            else:
                manifest = self.gateway.engine.workflows.get(tool.target)
                if manifest is None or not manifest.steps:
                    continue
                steps = [
                    step if isinstance(step, AssetIdentity) else step.capability
                    for step in manifest.steps
                ]
                if not all(authorized(step)[0] for step in steps):
                    continue
                reads = False  # a Workflow run is a side effect (rule 21)
            names.append(tool.name)
            read_only = read_only and reads
        return tuple(names), read_only

    def _plan(self, context: RequestContext, arguments: dict[str, JsonValue]) -> _Plan:
        try:
            request = DelegationRequest.model_validate(arguments)
        except ValidationError:
            raise DelegationRefused(
                "delegation_arguments_invalid",
                "agent__delegate needs profile and objective (≤ 4,000 characters)",
            ) from None
        target = self._target(context, request.profile)
        tools, read_only = self._effective(context, target.profile, request.tools)
        return _Plan(target=target, request=request, tools=tools, read_only=read_only)

    def _parallel(self, context: RequestContext, arguments: dict[str, JsonValue]) -> bool:
        """Read-only delegations of one reply may run side by side."""
        if delegation_scope.in_sub_run() or not self.enabled():
            return False
        try:
            return self._plan(context, arguments).read_only
        except DelegationRefused:
            return False

    # -- input artifacts -------------------------------------------------------------

    def _artifacts_text(self, context: RequestContext, ids: tuple[str, ...]) -> str:
        """The listed artifacts as text for the sub-agent: names, statuses,
        summaries and short text contents; never a path."""
        if not ids:
            return ""
        if self.ledger is None or not context.session_id:
            raise DelegationRefused(
                "delegation_artifact_unknown", "This conversation has no recorded artifacts"
            )
        ledger = self.ledger.ledger(context.session_id, context.actor)
        runs = {run.run_id: run for run in getattr(ledger, "runs", ())}
        blocks: list[str] = []
        budget = MAX_ARTIFACTS_TEXT_CHARS
        for artifact_id in ids:
            run = runs.get(artifact_id)
            if run is not None:
                blocks.append(
                    f"[{artifact_id}] run of {run.workflow}, status {run.status}: {run.summary}"
                )
                continue
            try:
                found = self.ledger.resolve(context.session_id, context.actor, artifact_id)
            except Exception:  # noqa: BLE001 - unknown, missing or not a file
                raise DelegationRefused(
                    "delegation_artifact_unknown",
                    f"{artifact_id} is not a file or run recorded in this conversation",
                ) from None
            block = f"[{artifact_id}] {found.kind}: {found.filename}"
            path = Path(found.path)
            if path.suffix.lower() in _TEXT_SUFFIXES and budget > 0:
                try:
                    with path.open(encoding="utf-8", errors="replace") as handle:
                        content = handle.read(min(MAX_ARTIFACT_TEXT_CHARS, budget) + 1)
                except OSError:
                    content = ""
                if content:
                    cut = len(content) > min(MAX_ARTIFACT_TEXT_CHARS, budget)
                    content = content[: min(MAX_ARTIFACT_TEXT_CHARS, budget)]
                    budget -= len(content)
                    block += "\n" + content + ("\n…(cut)" if cut else "")
            blocks.append(block)
        return "Input artifacts:\n" + "\n\n".join(blocks)

    # -- the call ------------------------------------------------------------------

    async def _handle(
        self, context: RequestContext, arguments: dict[str, JsonValue]
    ) -> HostToolOutcome:
        turn = delegation_scope.current_turn() or DelegationTurn(
            deadline=math.inf, clock=self.gateway.clock
        )
        reference = str(arguments.get("profile") or "")[:200]
        try:
            if not self.enabled():
                raise DelegationRefused("delegation_disabled", "Delegation is switched off")
            if delegation_scope.in_sub_run():
                raise DelegationRefused(
                    "delegation_depth_exceeded", "A sub-agent cannot delegate further"
                )
            if turn.started >= MAX_DELEGATIONS_PER_TURN:
                raise DelegationRefused(
                    "delegation_limit_reached",
                    f"At most {MAX_DELEGATIONS_PER_TURN} sub-agents per turn",
                )
            plan = self._plan(context, arguments)
            reference = plan.target.key
            inputs = self._artifacts_text(context, plan.request.input_artifact_ids)
            remaining = turn.remaining()
            if remaining <= 1:
                raise DelegationRefused(
                    "delegation_time_exhausted", "The turn has no time left for a sub-agent"
                )
        except DelegationRefused as refusal:
            turn.refused += 1
            return self._refused(reference, refusal.code, refusal.message)
        turn.started += 1
        index = turn.started
        time_limit = min(float(plan.target.profile.time_limit_s), remaining)
        # The parent turn's live progress: how many sub-agents run now (read by
        # `/api/activity`) and one line per sub-agent, which its sub-run
        # reports into as into its own turn.
        turn.running += 1
        parent = turn_progress.current()
        line: Any = None
        started_line = getattr(parent, "delegation_started", None)
        if started_line is not None:
            try:
                line = started_line(
                    plan.target.key, plan.request.objective, read_only=plan.read_only
                )
            except Exception:  # noqa: BLE001 - progress display cannot change the call
                line = None
        turn_progress.report(lambda item: item.delegation_changed(1))
        status = "failed"
        try:
            result = await self._run(context, plan, inputs, index, time_limit, line)
            status = result.status
        finally:
            turn.running -= 1
            if line is not None:
                try:
                    line.finish(status)
                except Exception:  # noqa: BLE001 - see above
                    pass
            turn_progress.report(lambda item: item.delegation_changed(-1))
        return self._outcome(result, plan)

    async def _run(
        self,
        context: RequestContext,
        plan: _Plan,
        inputs: str,
        index: int,
        time_limit: float,
        line: turn_progress.TurnProgress | None = None,
    ) -> DelegationResult:
        profile = plan.target.profile
        message = plan.request.objective + (f"\n\n{inputs}" if inputs else "")
        sub_context = RequestContext(
            trace=TraceIdentifiers(
                trace_id=context.trace.trace_id,
                request_id=f"{context.trace.request_id}.d{index}",
                span_id=f"{context.trace.span_id}.d{index}",
                parent_span_id=context.trace.span_id,
            ),
            actor=context.actor,
            namespace=context.namespace,
            message=message,
            channel=context.channel,
            session_id=context.session_id,
        )
        started = time.monotonic()
        # Only a read-only sub-agent is retried: a retry of anything that may
        # change state could repeat its effect.
        attempts = 1 + (profile.max_retries if plan.read_only else 0)
        answer: GatewayConversationResult | None = None
        with delegation_scope.running_sub_run(plan.target.key) as marker:
            # The sub-run reports into its own line under the parent turn (its
            # limits, tools, checks), never into the parent's counts; the
            # channel's tool lines are the parent's.
            progress_token = turn_progress.TURN_PROGRESS.set(line)
            tools_token = TOOL_PROGRESS.set(None)
            try:
                with telemetry.run(
                    "agent_delegation",
                    attributes={
                        "agent": plan.target.key,
                        "delegation_index": index,
                        "tools_effective": len(plan.tools),
                        "read_only": plan.read_only,
                        "time_limit_s": round(time_limit, 1),
                        "max_attempts": attempts,
                    },
                ):
                    for attempt in range(1, attempts + 1):
                        left = time_limit - (time.monotonic() - started)
                        if attempt > 1 and left < MIN_RETRY_SECONDS:
                            break
                        answer = await self._attempt(sub_context, plan, message, left)
                        if answer is None or not _retry_worthy(answer):
                            break
                    result = self._result(answer, plan, marker, time.monotonic() - started)
                    result = self._record(context, answer, result)
                    telemetry.set_run(
                        status="failed" if result.status == "failed" else "succeeded",
                        delegation_status=result.status,
                        failure_code=None if result.failure is None else result.failure.code,
                        artifacts=len(result.artifacts),
                        validated=result.validated,
                    )
            finally:
                TOOL_PROGRESS.reset(tools_token)
                turn_progress.TURN_PROGRESS.reset(progress_token)
        return result

    async def _attempt(
        self,
        sub_context: RequestContext,
        plan: _Plan,
        message: str,
        left: float,
    ) -> GatewayConversationResult | None:
        """One sub-run within `left` seconds; None when the time limit stops it."""
        parent_cap = self.gateway.limits().tool_calls
        limits = ConversationLimits(
            tool_calls=min(plan.target.profile.max_tool_calls, parent_cap),
            # The loop's own check (at least a minute by contract); the hard
            # stop below holds the exact limit.
            time_limit_seconds=max(60, math.ceil(left)),
        )
        try:
            return await asyncio.wait_for(
                self.gateway.converse(
                    sub_context,
                    (ModelMessage(role="user", text=message),),
                    allowed_tools=frozenset(plan.tools),
                    max_turns=plan.target.profile.max_turns,
                    role_guidance=_role(plan.target),
                    limits=limits,
                ),
                timeout=left,
            )
        except TimeoutError:
            return None

    def _result(
        self,
        answer: GatewayConversationResult | None,
        plan: _Plan,
        marker: delegation_scope.SubRun,
        elapsed: float,
    ) -> DelegationResult:
        tokens = DelegationTokens(
            input=marker.input_tokens if marker.token_reports else None,
            output=marker.output_tokens if marker.token_reports else None,
            model_calls=marker.model_calls,
        )
        common: dict[str, Any] = {
            "profile": plan.target.key,
            "tokens": tokens,
            "read_only": plan.read_only,
            "elapsed_s": round(elapsed, 1),
        }
        if answer is None:
            return DelegationResult(
                status="failed",
                failure=Failure(
                    code="delegation_time_limit",
                    message="The sub-agent was stopped at its time limit",
                ),
                summary="子代理在時間上限內沒有完成，已停止。",
                **common,
            )
        calls = tuple(
            DelegationToolCall(name=item.name, status=_tool_status(item), replayed=item.replayed)
            for item in answer.tools
        )
        common["tool_calls"] = calls
        text = answer.text or ""
        shown, _ = capped(
            text,
            DELEGATION_OUTPUT_LIMIT_CHARS,
            "完整內容沒有保留；需要時請縮小委派的目標再試一次。",
        )
        if answer.status != "answered":
            failure = answer.failure or Failure(
                code="delegation_failed", message="The sub-agent did not answer"
            )
            return DelegationResult(status="failed", summary=shown, failure=failure, **common)
        first, _, rest = text.strip().partition("\n")
        if first.strip().upper().startswith(NEEDS_INPUT_MARK):
            question = first.strip()[len(NEEDS_INPUT_MARK) :].strip() or rest.strip()
            return DelegationResult(
                status="needs_input",
                question=(question or "（子代理需要更多資訊，但沒有說明）")[:MAX_FINDING_CHARS],
                summary=shown,
                validated=False,
                **common,
            )
        notes = unverified(answer.tools)
        marked = NOTE_MARK in text
        validated = not notes and not marked and not _not_validated_harness(answer.tools)
        host_note: str | None = None
        if not validated:
            host_note = "；".join(notes) if notes else None
            if marked:
                host_note = text[text.index(NOTE_MARK) :].strip()[:MAX_FINDING_CHARS]
            host_note = host_note or "子代理的結果未通過 Host 檢查"
        approvals = tuple(
            str(item.host.data["approval_id"])
            for item in answer.tools
            if item.host is not None
            and item.host.status == "awaiting_approval"
            and isinstance(item.host.data, dict)
            and item.host.data.get("approval_id")
        )
        waiting = any(call.status == "awaiting_approval" for call in calls)
        return DelegationResult(
            status="awaiting_approval" if waiting else "succeeded",
            summary=shown,
            findings=_findings(text),
            approvals=approvals,
            validated=validated,
            host_note=host_note,
            **common,
        )

    def _record(
        self,
        context: RequestContext,
        answer: GatewayConversationResult | None,
        result: DelegationResult,
    ) -> DelegationResult:
        """The sub-run's Workflow runs and their files, in the parent session's
        ledger (rule 20), listed on the result by id."""
        if answer is None:
            return result
        found: list[DelegationArtifact] = []
        for item in answer.tools:
            snapshot = item.workflow
            if snapshot is None:
                continue
            run = snapshot.run
            name = run.workflow.name
            recorded = None
            if self.ledger is not None and context.session_id:
                try:
                    recorded = self.ledger.record_run(context.session_id, context.actor, snapshot)
                except Exception:  # noqa: BLE001 - the ledger is a help, never a failure
                    recorded = None
            if any(entry.kind == "run" and entry.id == run.run_id for entry in found):
                continue
            found.append(
                DelegationArtifact(kind="run", id=run.run_id, name=name, status=run.status)
            )
            if recorded is None or self.ledger is None or not context.session_id:
                continue
            ledger = self.ledger.ledger(context.session_id, context.actor)
            files = {entry.artifact_id: entry for entry in getattr(ledger, "artifacts", ())}
            for artifact_id in getattr(recorded, "artifact_ids", ()):
                entry = files.get(artifact_id)
                if entry is not None:
                    found.append(
                        DelegationArtifact(kind="file", id=artifact_id, name=entry.filename)
                    )
        if not found:
            return result
        return result.model_copy(update={"artifacts": tuple(found)})

    # -- what the parent gets ---------------------------------------------------------

    @staticmethod
    def _refused(reference: str, code: str, message: str) -> HostToolOutcome:
        failure = Failure(code=code, message=message)
        result = DelegationResult(
            status="failed", profile=reference or "unknown", failure=failure, validated=False
        )
        return HostToolOutcome(
            status="failed",
            data={
                "delegation": result.model_dump(mode="json"),
                "instruction": "No sub-agent ran. Do the work yourself if your tools allow, or "
                "tell the person why it could not be delegated.",
            },
            failure=failure,
        )

    @staticmethod
    def _outcome(result: DelegationResult, plan: _Plan) -> HostToolOutcome:
        digest = hashlib.sha256(plan.request.objective.encode("utf-8")).hexdigest()[:8]
        data: dict[str, JsonValue] = {
            "delegation": result.model_dump(mode="json"),
            "delegation_verdict": "validated" if result.validated else "not_validated",
            "harness_key": f"{DELEGATE_TOOL}:{result.profile}:{digest}",
            "read_only": result.read_only,
        }
        if result.host_note:
            data["host_note"] = result.host_note
        if result.status == "succeeded":
            data["instruction"] = (
                "Use the sub-agent's result above to answer; claim nothing it did not find."
                if result.validated
                else "This result did not pass the Host's checks: give it to the person as it "
                "is, with the Host's note; never present it as verified."
            )
            return HostToolOutcome(status="succeeded", data=data)
        if result.status == "awaiting_approval":
            data["instruction"] = (
                "Nothing was written yet. Tell the person the sub-agent's change waits for their "
                "approval button; the result appears in this conversation after they approve."
            )
            return HostToolOutcome(status="awaiting_approval", data=data)
        if result.status == "needs_input":
            data["instruction"] = (
                "The sub-agent needs this answered: ask the person only this question, unless "
                "they already said it (then delegate again with it in the objective)."
            )
            return HostToolOutcome(
                status="failed",
                data=data,
                failure=Failure(
                    code="delegation_needs_input", message="The sub-agent needs information"
                ),
            )
        data["instruction"] = (
            "The sub-agent did not finish: say so plainly; never present its work as done."
        )
        return HostToolOutcome(status="failed", data=data, failure=result.failure)


def _names(message: str, target: DelegationTarget) -> bool:
    """Whether the person's own message names this profile (`namespace/name`
    or its `name` as a whole word), case-insensitively."""
    identity = target.profile.metadata.identity
    text = (message or "").lower()
    if f"{identity.namespace}/{identity.name}" in text:
        return True
    return re.search(rf"(?<![a-z0-9-]){re.escape(identity.name)}(?![a-z0-9-])", text) is not None
