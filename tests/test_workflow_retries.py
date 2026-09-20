import asyncio
from typing import Any

import pytest
from pydantic import ValidationError
from test_dispatch import Handler, Input, Output, grant, spec
from test_engine import context, engine
from test_workflow_inputs import flow_for, runner_for, step

from capabilities.runtime import InstalledCapabilities, LocalPolicy, TransientCapabilityError
from common.assets import ExecutionDependencies, RetryPolicy
from common.base import Contract
from common.execution import RequestContext, StepAttempt
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine


class Flaky(Handler):
    def __init__(self, failures: int = 1, *, unknown: bool = False) -> None:
        super().__init__()
        self.failures = failures
        self.unknown = unknown
        self.attempts = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.attempts += 1
        if self.attempts <= self.failures:
            if self.unknown:
                raise RuntimeError("private error payload")
            raise TransientCapabilityError("private error payload")
        return await super().__call__(context, inputs)


def retry_step(attempts: int = 3, delay_ms: int = 0) -> dict[str, Any]:
    data = step({"source": "run", "path": ["count"]})
    data["retry"] = {"max_attempts": attempts, "delay_ms": delay_ms}
    return data


@pytest.mark.parametrize(
    "data",
    [
        {"max_attempts": 0},
        {"max_attempts": 4},
        {"max_attempts": True},
        {"max_attempts": "2"},
        {"delay_ms": -1},
        {"delay_ms": 10001},
        {"delay_ms": 0.5},
        {"delay_ms": True},
        {"retry_on": ["permission_denied"]},
    ],
)
def test_invalid_retry_contracts(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RetryPolicy.model_validate(data)


@pytest.mark.parametrize("status,code", [("succeeded", "error"), ("failed", None)])
def test_attempt_contract_requires_matching_outcome(status: str, code: str | None) -> None:
    with pytest.raises(ValidationError):
        StepAttempt.model_validate({"step_index": 0, "attempt": 1, "status": status, "code": code})


def test_defaults_preserve_single_attempt() -> None:
    assert RetryPolicy().max_attempts == 1
    handler = Flaky()
    runner, flow = engine(handler, steps=1)
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"count": 1}))
    assert result.run.status == "failed" and handler.attempts == 1
    assert result.run.failure is not None and result.run.failure.retryable


@pytest.mark.parametrize("failures,expected,attempts", [(1, "succeeded", 2), (10, "failed", 3)])
def test_bounded_transient_retry(failures: int, expected: str, attempts: int) -> None:
    handler = Flaky(failures)
    flow = flow_for([retry_step()])
    assert type(flow).model_validate_json(flow.model_dump_json()) == flow
    runner = runner_for(flow, handler)
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"count": 1}))
    assert result.run.status == expected and handler.attempts == attempts
    assert len(result.step_results) == 1
    assert [item.attempt for item in result.attempts] == list(range(1, attempts + 1))
    assert len(runner.bridge.events) == attempts
    assert "private error payload" not in result.model_dump_json()


def test_unknown_exceptions_do_not_retry() -> None:
    handler = Flaky(unknown=True)
    flow = flow_for([retry_step()])
    result = asyncio.run(
        runner_for(flow, handler).execute(context(), flow.metadata.identity, {"count": 1})
    )
    assert handler.attempts == 1
    assert result.run.failure is not None and result.run.failure.code == "handler_error"
    assert not result.run.failure.retryable


@pytest.mark.parametrize("effect", ["write", "execute", "external_side_effect"])
def test_side_effect_retries_rejected_before_any_step(effect: str) -> None:
    data = spec().model_dump()
    data["side_effect"] = effect
    installed = InstalledCapabilities()
    handler = Flaky()
    installed.register(
        type(spec()).model_validate(data),
        handler,
        Input,
        Output,
        ExecutionDependencies(central_required=False),
    )
    flow = flow_for([spec().identity.model_dump(), retry_step()])
    workflows = InstalledWorkflows()
    workflows.register(flow)
    runner = WorkflowEngine(workflows, BridgeExecutor(installed, LocalPolicy((grant(),))))
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"count": 1}))
    assert result.run.failure is not None and result.run.failure.code == "unsafe_retry"
    assert runner.get(result.run.run_id) is None and handler.attempts == 0


def test_each_attempt_rechecks_policy() -> None:
    class Revoke(Flaky):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            runner.bridge.policy = LocalPolicy()
            return await super().__call__(context, inputs)

    handler = Revoke()
    flow = flow_for([retry_step()])
    runner = runner_for(flow, handler)
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"count": 1}))
    assert handler.attempts == 1
    assert len(result.attempts) == 2
    assert result.run.failure is not None and result.run.failure.code == "permission_denied"


def test_retry_final_output_chains_without_repeating_successful_steps() -> None:
    class FailSecond(Handler):
        def __init__(self) -> None:
            super().__init__()
            self.values: list[int] = []

        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            assert isinstance(inputs, Input)
            self.values.append(inputs.count)
            if len(self.values) == 2:
                raise TransientCapabilityError()
            return await super().__call__(context, inputs)

    handler = FailSecond()
    second = retry_step()
    second["inputs"] = {"count": {"source": "step", "step_index": 0, "path": ["count"]}}
    flow = flow_for(
        [
            spec().identity.model_dump(),
            second,
            step({"source": "step", "step_index": 1, "path": ["count"]}),
        ]
    )
    result = asyncio.run(
        runner_for(flow, handler).execute(context(), flow.metadata.identity, {"count": 1})
    )
    assert result.run.status == "succeeded" and result.run.completed_steps == 3
    assert handler.values == [1, 2, 2, 3]
    assert [r.data for r in result.step_results] == [{"count": 2}, {"count": 3}, {"count": 4}]


def test_timeout_is_not_retryable() -> None:
    class Slow(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            await asyncio.sleep(10)
            return await super().__call__(context, inputs)

    flow = flow_for([retry_step()])
    runner = runner_for(flow, Slow())
    runner.bridge.timeout_seconds = 0.001
    result = asyncio.run(runner.execute(context(), flow.metadata.identity, {"count": 1}))
    assert len(result.attempts) == 1
    assert result.run.failure is not None and result.run.failure.code == "timeout"
    assert not result.run.failure.retryable


def test_backoff_outlives_caller_wait_without_restarting_run() -> None:
    async def scenario() -> None:
        handler = Flaky()
        flow = flow_for([retry_step(delay_ms=40)])
        runner = runner_for(flow, handler)
        timed = await runner.execute(
            context(),
            flow.metadata.identity,
            {"count": 1},
            timeout_seconds=0.001,
            idempotency_key="key",
        )
        assert timed.run.failure is not None and timed.run.failure.code == "workflow_timeout"
        final = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        assert final.run.run_id == timed.run.run_id
        assert final.run.status == "succeeded" and handler.attempts == 2
        assert final.run.failure is None

    asyncio.run(scenario())


def test_invalid_input_and_missing_dependency_never_retry() -> None:
    async def scenario() -> None:
        handler = Flaky()
        flow = flow_for([retry_step()])
        runner = runner_for(flow, handler)
        invalid = await runner.execute(context(), flow.metadata.identity, {"count": "1"})
        assert invalid.run.failure is not None and invalid.run.failure.code == "invalid_input"
        assert len(invalid.attempts) == 1 and handler.attempts == 0
        installed = InstalledCapabilities()
        installed.register(
            spec(),
            handler,
            Input,
            Output,
            ExecutionDependencies(local_capabilities=("missing",), central_required=False),
        )
        runner.bridge.installed = installed
        missing = await runner.execute(context(), flow.metadata.identity, {"count": 1})
        assert missing.run.failure is not None
        assert missing.run.failure.code == "missing_local_capability"
        assert len(missing.attempts) == 1 and handler.attempts == 0

    asyncio.run(scenario())
