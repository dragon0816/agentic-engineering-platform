"""Execute one explicit Gateway task with Host policy and independent validation."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Protocol

from agent.backend_contracts import GatewayConversationRequest
from agent.backends.gateway import GatewayModelBackend
from agent.data_policy import BackendDataDecision, ContextMaterial, DataPolicy, OutboundContext
from agent.gateway import MAX_CONVERSATION_MESSAGE_CHARS, GatewayConversationResult
from agent.orchestrator import BackendRouter
from agent.run_state import (
    CompletionValidator,
    TaskBackendResult,
    TaskCompletedStep,
    TaskIssue,
    TaskObservation,
    TaskRunState,
    advance_task_run,
    apply_backend_result,
    begin_task_run,
)
from agent.task_contract import TaskContract
from common.base import Contract, Symbol
from common.execution import RequestContext
from models.contracts import ModelMessage


class TaskRunStore(Protocol):
    def create_task_run(self, record: TaskRunState) -> TaskRunState: ...

    def save_task_run(self, record: TaskRunState) -> TaskRunState: ...


class TaskArtifacts(Protocol):
    def write(self, artifact_ref: str, content: bytes) -> None: ...

    def read(self, artifact_ref: str) -> bytes | None: ...


class TaskScopeError(ValueError):
    """A bounded task feature is unsupported; no backend has been called."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class TaskExecutionOutcome(Contract):
    task_id: Symbol
    status: Literal["refused", "validated", "needs_input", "failed"]
    code: Symbol | None = None
    data_decision: BackendDataDecision
    run: TaskRunState | None = None
    conversation: GatewayConversationResult | None = None


class GatewayTaskExecutor:
    """First task-capable orchestrator path; only the approved Gateway is eligible."""

    def __init__(
        self,
        backend: GatewayModelBackend,
        policy: DataPolicy,
        runs: TaskRunStore,
        artifacts: TaskArtifacts,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.backend = backend
        self.policy = policy
        self.runs = runs
        self.artifacts = artifacts
        self.clock = clock if clock is not None else lambda: datetime.now(UTC)
        self.router = BackendRouter((backend,))

    def _allowed_tools(self, task: TaskContract) -> tuple[str, ...]:
        if len(task.objective) > MAX_CONVERSATION_MESSAGE_CHARS:
            raise TaskScopeError("task_objective_too_long")
        if task.resource_refs or task.constraints.workspace_ref is not None:
            raise TaskScopeError("task_resources_not_supported")
        if len(task.expected_outputs) != 1 or task.expected_outputs[0].output_id != "answer":
            raise TaskScopeError("task_output_not_supported")
        installed = self.backend.gateway.bridge.installed
        allowed = {item.key for item in task.allowed_capabilities}
        for identity in task.allowed_capabilities:
            binding = installed.get(identity)
            if binding is None:
                raise TaskScopeError("task_capability_not_installed")
            if binding.spec.side_effect != "read":
                raise TaskScopeError("task_capability_not_read_only")
        names: list[str] = []
        covered: set[tuple[str, str, str]] = set()
        found_skills: set[tuple[str, str, str]] = set()
        selected_skills = {item.key for item in task.skills}
        for skill in self.backend.gateway.router.commands.skills.discover(task.namespace):
            if selected_skills and skill.metadata.identity.key not in selected_skills:
                continue
            found_skills.add(skill.metadata.identity.key)
            for command in skill.commands:
                if command.kind == "capability" and command.target.key in allowed:
                    names.append(f"{skill.alias}__{command.name}")
                    covered.add(command.target.key)
        if found_skills != selected_skills and selected_skills:
            raise TaskScopeError("task_skill_not_installed")
        if covered != allowed:
            raise TaskScopeError("task_capability_has_no_skill_command")
        return tuple(names)

    async def run(self, task: TaskContract) -> TaskExecutionOutcome:
        item = TaskContract.model_validate(task)
        allowed_tools = self._allowed_tools(item)
        context = RequestContext(
            trace=item.trace,
            actor=item.actor,
            namespace=item.namespace,
            message=item.objective,
            channel="local",
        )
        materials = [
            ContextMaterial(material_id="task-objective", origin="user", text=item.objective)
        ]
        for index, name in enumerate(allowed_tools):
            materials.append(
                ContextMaterial(material_id=f"task-tool-{index}", origin="skill", text=name)
            )
        decision = self.policy.decide(
            self.backend.profile, OutboundContext(materials=tuple(materials))
        )
        if not decision.allowed:
            return TaskExecutionOutcome(
                task_id=item.task_id, status="refused", code=decision.code, data_decision=decision
            )
        backend = self.router.select(
            self.backend.profile.backend_id, eligible_ids=(decision.backend_id,)
        )
        pending = begin_task_run(
            item,
            backend.profile.backend_id,
            now=self.clock(),
            effective_classification=decision.effective_classification,
            approval_ref=decision.approval_ref,
        )
        self.runs.create_task_run(pending)
        running = advance_task_run(pending, "running", now=self.clock())
        self.runs.save_task_run(running)
        request = GatewayConversationRequest(
            context=context,
            history=(ModelMessage(role="user", text=item.objective),),
            allowed_tools=allowed_tools,
            max_turns=min(item.constraints.max_backend_turns, 5),
        )
        try:
            response = await backend.execute(request)
        except Exception:
            response = None
        code: str | None = None
        artifact_refs: tuple[str, ...] = ()
        if response is None or response.trace != item.trace:
            code = "backend_context_mismatch" if response is not None else "backend_unavailable"
        elif response.status != "answered":
            code = response.failure.code if response.failure is not None else "backend_unavailable"
        elif any(
            tool.failure is not None
            or tool.workflow is not None
            or (tool.capability is not None and tool.capability.status != "succeeded")
            for tool in response.tools
        ):
            code = "task_tool_failed"
        else:
            try:
                self.artifacts.write(
                    item.expected_outputs[0].artifact_ref, response.text.encode("utf-8")
                )
                artifact_refs = (item.expected_outputs[0].artifact_ref,)
            except (OSError, ValueError):
                code = "artifact_write_failed"
        observations = tuple(
            TaskObservation(
                sequence=index,
                code=(
                    "tool_succeeded"
                    if tool.capability is not None and tool.capability.status == "succeeded"
                    else "tool_failed"
                ),
                evidence_ref=tool.call_id,
            )
            for index, tool in enumerate(() if response is None else response.tools)
        )
        result = TaskBackendResult(
            task_id=item.task_id,
            trace=item.trace,
            backend_id=backend.profile.backend_id,
            status=(
                "completed"
                if code is None
                else "needs_input"
                if response is not None and response.status == "needs_input"
                else "failed"
            ),
            observations=observations,
            completed_steps=tuple(
                TaskCompletedStep(step_id=tool.call_id, evidence_ref=tool.call_id)
                for tool in (() if response is None else response.tools)
                if tool.capability is not None and tool.capability.status == "succeeded"
            ),
            artifact_refs=artifact_refs,
            failure_code=code,
        )
        candidate = apply_backend_result(running, result, now=self.clock())
        self.runs.save_task_run(candidate)
        if candidate.status != "awaiting_validation":
            return TaskExecutionOutcome(
                task_id=item.task_id,
                status=candidate.status,
                code=code,
                data_decision=decision,
                run=candidate,
                conversation=response,
            )
        report = CompletionValidator(self.artifacts).validate(item, candidate)
        final = advance_task_run(
            candidate,
            "validated" if report.status == "passed" else "failed",
            now=self.clock(),
            validation=report,
            errors=(TaskIssue(code="task_validation_failed"),) if report.status == "failed" else (),
        )
        self.runs.save_task_run(final)
        return TaskExecutionOutcome(
            task_id=item.task_id,
            status=final.status,
            code=None if report.status == "passed" else "task_validation_failed",
            data_decision=decision,
            run=final,
            conversation=response,
        )
