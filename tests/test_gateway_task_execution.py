"""An explicit task uses the approved Gateway and Host-owned validation."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from test_gateway import Handler, Probe, Report, capability_spec, gateway
from test_local_agent import company
from test_routing import FakeModel

from agent.backends.gateway import GatewayModelBackend
from agent.data_policy import BackendDataApproval, DataPolicy
from agent.task_contract import CompletionCheck, ExpectedOutput, TaskContract
from agent.task_execution import GatewayTaskExecutor, TaskScopeError
from capabilities.runtime import InstalledCapabilities
from common.assets import AssetIdentity, ExecutionDependencies
from common.execution import TraceIdentifiers
from host_runtime.agent import LocalAgent
from host_runtime.cli import _parser, _prompt_task
from host_runtime.state import SqliteLocalState
from host_runtime.task_artifacts import LocalTaskArtifacts
from models.contracts import ModelRequest, ModelResponse, ModelToolCall

NOW = datetime(2026, 10, 2, tzinfo=UTC)


class AnswerModel(FakeModel):
    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, text="The answer is recorded."
        )


def task(*, allowed: tuple[AssetIdentity, ...] = ()) -> TaskContract:
    return TaskContract(
        task_id="task-gateway-1",
        trace=TraceIdentifiers(
            trace_id="trace-task", request_id="request-task", span_id="span-task"
        ),
        actor="engineer",
        namespace="engineering",
        objective="Answer the question",
        allowed_capabilities=allowed,
        expected_outputs=(ExpectedOutput(output_id="answer", artifact_ref="answer-task-1"),),
        checks=(CompletionCheck(check_id="answer-present", output_id="answer", kind="nonempty"),),
    )


def approved() -> DataPolicy:
    return DataPolicy(
        (
            BackendDataApproval(
                backend_id="gateway",
                approved_classes=("UNCLASSIFIED",),
                approval_ref="host-gateway-approval",
                internal_gateway=True,
            ),
        )
    )


def executor(
    tmp_path: Path,
    model: FakeModel,
    policy: DataPolicy,
    *,
    artifacts: LocalTaskArtifacts | None = None,
) -> tuple[GatewayTaskExecutor, SqliteLocalState]:
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge-company")
    runtime = gateway(Handler(), model)
    service = GatewayTaskExecutor(
        GatewayModelBackend(runtime),
        policy,
        state,
        artifacts if artifacts is not None else LocalTaskArtifacts(tmp_path),
        clock=lambda: NOW,
    )
    return service, state


def test_gateway_task_persists_validated_answer_without_objective_or_answer_in_state(
    tmp_path: Path,
) -> None:
    model = AnswerModel()
    service, state = executor(tmp_path, model, approved())
    with state:
        outcome = asyncio.run(service.run(task()))
        assert outcome.status == "validated"
        assert outcome.run is not None and outcome.run.validation is not None
        assert outcome.run.validation.status == "passed"
        assert outcome.run.backend_history[0].approval_ref == "host-gateway-approval"
        assert outcome.run.effective_classification == "UNCLASSIFIED"
        assert model.calls[0].tools == ()
        assert not model.calls[0].requirements.tool_calling
        assert (tmp_path / "task-artifacts" / "answer-task-1").read_text() == (
            "The answer is recorded."
        )
    with SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge-company") as reopened:
        persisted = reopened.task_run("task-gateway-1", "engineer")
        assert persisted == outcome.run
    raw = (tmp_path / "state.sqlite").read_bytes()
    assert b"Answer the question" not in raw
    assert b"The answer is recorded." not in raw


def test_gateway_policy_denial_precedes_model_and_state_creation(tmp_path: Path) -> None:
    model = AnswerModel()
    service, state = executor(tmp_path, model, DataPolicy(()))
    with state:
        outcome = asyncio.run(service.run(task()))
        assert outcome.status == "refused" and outcome.code == "gateway_not_approved"
        assert outcome.run is None
        assert state.task_runs("engineer") == ()
    assert model.calls == []
    assert not (tmp_path / "task-artifacts").exists()


def test_missing_answer_artifact_cannot_validate_a_backend_claim(tmp_path: Path) -> None:
    class VanishingArtifacts(LocalTaskArtifacts):
        def write(self, artifact_ref: str, content: bytes) -> None:
            pass

    model = AnswerModel()
    service, state = executor(tmp_path, model, approved(), artifacts=VanishingArtifacts(tmp_path))
    with state:
        outcome = asyncio.run(service.run(task()))
        assert outcome.status == "failed" and outcome.code == "task_validation_failed"
        assert outcome.run is not None and outcome.run.validation is not None
        assert outcome.run.validation.checks[0].code == "artifact_missing"
        assert [issue.code for issue in outcome.run.errors] == ["task_validation_failed"]


def test_task_scope_refuses_unknown_or_write_capability_before_model(tmp_path: Path) -> None:
    model = AnswerModel()
    service, state = executor(tmp_path, model, approved())
    unknown = AssetIdentity(namespace="engineering", name="missing", version="1.0.0")
    with state:
        with pytest.raises(TaskScopeError, match="task_capability_not_installed"):
            asyncio.run(service.run(task(allowed=(unknown,))))
        write = capability_spec().model_copy(
            update={
                "identity": AssetIdentity(
                    namespace="engineering", name="write-report", version="1.0.0"
                ),
                "side_effect": "write",
            }
        )
        installed: InstalledCapabilities = service.backend.gateway.bridge.installed
        installed.register(
            write, Handler(), Probe, Report, ExecutionDependencies(central_required=False)
        )
        with pytest.raises(TaskScopeError, match="task_capability_not_read_only"):
            asyncio.run(service.run(task(allowed=(write.identity,))))
        assert state.task_runs("engineer") == ()
    assert model.calls == []


def test_read_capability_scope_hides_workflow_tools(tmp_path: Path) -> None:
    class ScopedModel(AnswerModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            assert [tool.name for tool in request.tools] == ["release__check"]
            return super().generate(request)

    model = ScopedModel()
    service, state = executor(tmp_path, model, approved())
    with state:
        outcome = asyncio.run(service.run(task(allowed=(capability_spec().identity,))))
        assert outcome.status == "validated"
    assert len(model.calls) == 1


def test_successful_read_tool_records_bounded_step_evidence(tmp_path: Path) -> None:
    class ToolModel(AnswerModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            assert [tool.name for tool in request.tools] == ["release__check"]
            if not self.calls:
                self.calls.append(request)
                return ModelResponse(
                    trace=request.trace,
                    model_alias=request.model_alias,
                    tool_calls=(
                        ModelToolCall(call_id="read-check", name="release__check", arguments={}),
                    ),
                )
            assert request.messages[-1].role == "tool"
            return super().generate(request)

    model = ToolModel()
    service, state = executor(tmp_path, model, approved())
    with state:
        outcome = asyncio.run(service.run(task(allowed=(capability_spec().identity,))))
        assert outcome.status == "validated"
        assert outcome.run is not None
        assert [(step.step_id, step.evidence_ref) for step in outcome.run.completed_steps] == [
            ("read-check", "read-check")
        ]
        assert [event.code for event in outcome.run.observations] == ["tool_succeeded"]
        assert outcome.run.errors == ()
    assert len(model.calls) == 2


def test_hidden_workflow_tool_cannot_execute_or_complete_task(tmp_path: Path) -> None:
    class HiddenToolModel(AnswerModel):
        def generate(self, request: ModelRequest) -> ModelResponse:
            assert [tool.name for tool in request.tools] == ["release__check"]
            if not self.calls:
                self.calls.append(request)
                return ModelResponse(
                    trace=request.trace,
                    model_alias=request.model_alias,
                    tool_calls=(
                        ModelToolCall(
                            call_id="hidden-workflow", name="release__package", arguments={}
                        ),
                    ),
                )
            return super().generate(request)

    model = HiddenToolModel()
    service, state = executor(tmp_path, model, approved())
    with state:
        outcome = asyncio.run(service.run(task(allowed=(capability_spec().identity,))))
        assert outcome.status == "failed" and outcome.code == "task_tool_failed"
        assert outcome.run is not None
        assert [issue.code for issue in outcome.run.errors] == ["task_tool_failed"]
        assert outcome.run.completed_steps == ()
    assert not (tmp_path / "task-artifacts").exists()


def test_local_agent_admission_precedes_task_policy_and_backend(tmp_path: Path) -> None:
    model = AnswerModel()
    service, state = executor(tmp_path, model, approved())
    resident = LocalAgent(company(), service.backend.gateway, state, task_executor=service)
    with state:
        denied = asyncio.run(resident.run_task(task(), bridge_id="wrong-bridge"))
        assert denied.refusal is not None and denied.execution is None
        assert state.task_runs("engineer") == ()
        assert model.calls == []
        admitted = asyncio.run(resident.run_task(task(), bridge_id="bridge-company"))
        assert admitted.refusal is None
        assert admitted.execution is not None and admitted.execution.status == "validated"


def test_prompt_cli_builds_a_text_only_task_with_host_identity() -> None:
    args = _parser().parse_args(
        ["run-task", "--config", "host.json", "--prompt", "What can you do?"]
    )
    assert args.prompt == "What can you do?" and args.task is None
    runtime = MagicMock()
    runtime.actor = "engineer"
    runtime.config.namespace = "engineering"
    generated = _prompt_task(runtime, args.prompt, None)
    assert generated is not None
    assert generated.actor == "engineer" and generated.namespace == "engineering"
    assert generated.objective == "What can you do?"
    assert generated.allowed_capabilities == ()
    assert generated.expected_outputs[0].output_id == "answer"
