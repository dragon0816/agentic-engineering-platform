"""Optional integration uses real Gateway/engine/Bridge with inert handlers only."""

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError
from test_gateway import Handler, Probe, gateway, request, workflow_manifest
from test_routing import FakeModel

from agent.gateway import Gateway
from common.base import Contract
from common.execution import RequestContext
from integrations.n8n import N8nAdapter, N8nSubmission, N8nWorkflowBinding
from workflow.engine import InstalledWorkflows, WorkflowRunSnapshot


def binding(**changes: Any) -> N8nWorkflowBinding:
    return N8nWorkflowBinding.model_validate(
        {
            "binding_id": "release-node",
            "workflow": workflow_manifest().metadata.identity,
            **changes,
        }
    )


def item(operation_id: str = "operation-1", **arguments: Any) -> N8nSubmission:
    return N8nSubmission(operation_id=operation_id, arguments=arguments)


@pytest.mark.parametrize(
    "extra",
    [
        {"actor": "admin"},
        {"workflow": {}},
        {"target": {}},
        {"policy": {}},
        {"resume": "run-1"},
        {"timeout_seconds": 1},
        {"credentials": "placeholder"},
    ],
)
def test_payload_cannot_supply_host_authority_or_execution_options(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        N8nSubmission.model_validate({"operation_id": "one", "arguments": {}, **extra})


@pytest.mark.parametrize("operation_id", ["", "has spaces", "x" * 129, 3, True])
def test_operation_id_is_required_and_bounded(operation_id: Any) -> None:
    with pytest.raises(ValidationError):
        N8nSubmission.model_validate({"operation_id": operation_id})


def test_binding_and_submission_round_trip() -> None:
    bound, payload = binding(), item(args="notes.txt")
    assert N8nWorkflowBinding.model_validate_json(bound.model_dump_json()) == bound
    assert N8nSubmission.model_validate_json(payload.model_dump_json()) == payload
    with pytest.raises(ValidationError):
        N8nWorkflowBinding.model_validate({**bound.model_dump(), "grant": True})


def test_bound_workflow_bypasses_message_routing_and_preserves_arguments() -> None:
    class Echo(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            assert inputs == Probe(args="notes.txt now")
            assert context.message == "unrelated words which must never route"
            return await super().__call__(context, inputs)

    handler, model = Echo(), FakeModel()
    app = gateway(handler, model)
    adapter = N8nAdapter(app, binding())
    result = asyncio.run(
        adapter.submit(
            request("unrelated words which must never route"), item(args="notes.txt now")
        )
    )
    assert result.run.workflow == binding().workflow
    assert result.run.status == "succeeded" and handler.calls == 1
    assert result.step_results[-1].data == {"validated": True}
    assert model.calls == []


def test_n8n_and_routed_workflows_use_same_gateway_entry_point() -> None:
    class ObservedGateway(Gateway):
        entries = 0

        async def execute_workflow(self, *args: Any, **kwargs: Any) -> WorkflowRunSnapshot:
            self.entries += 1
            return await super().execute_workflow(*args, **kwargs)

    async def scenario() -> None:
        handler, model = Handler(), FakeModel()
        original = gateway(handler, model)
        app = ObservedGateway(original.router, original.bridge, original.engine)
        routed = await app.handle(request("release.package"))
        explicit = await app.execute_workflow(request("direct"), binding().workflow, {})
        adapted = await N8nAdapter(app, binding()).submit(request("event"), item())
        assert routed.workflow is not None
        assert [r.run.status for r in (routed.workflow, explicit, adapted)] == ["succeeded"] * 3
        assert [r.step_results[-1].data for r in (routed.workflow, explicit, adapted)] == [
            {"validated": True}
        ] * 3
        assert handler.calls == 3 and model.calls == []
        assert app.entries == 3

    asyncio.run(scenario())


def test_retargeting_binding_conflicts_instead_of_executing_another_workflow() -> None:
    async def scenario() -> None:
        handler = Handler()
        app = gateway(handler)
        await N8nAdapter(app, binding()).submit(request("event"), item())
        changed = binding().workflow.model_copy(update={"version": "2.0.0"})
        result = await N8nAdapter(app, binding(workflow=changed)).submit(request("event"), item())
        assert result.run.failure is not None and result.run.failure.code == "idempotency_conflict"
        assert handler.calls == 1

    asyncio.run(scenario())


def test_changed_trace_reuses_run_but_changed_context_conflicts() -> None:
    async def scenario() -> None:
        handler = Handler()
        adapter = N8nAdapter(gateway(handler), binding())
        original = request("event")
        first = await adapter.submit(original, item())
        retried = original.model_copy(
            update={"trace": original.trace.model_copy(update={"request_id": "retry-request"})}
        )
        second = await adapter.submit(retried, item())
        assert first == second and second.run.trace == original.trace
        conflict = await adapter.submit(request("different event"), item())
        assert (
            conflict.run.failure is not None and conflict.run.failure.code == "idempotency_conflict"
        )
        assert handler.calls == 1

    asyncio.run(scenario())


def test_missing_workflow_fails_without_handler_call() -> None:
    handler = Handler()
    absent = binding().workflow.model_copy(update={"name": "not-installed"})
    result = asyncio.run(
        N8nAdapter(gateway(handler), binding(workflow=absent)).submit(request("event"), item())
    )
    assert result.run.failure is not None and result.run.failure.code == "workflow_not_installed"
    assert handler.calls == 0


def test_dependency_rejection_can_be_redelivered_after_availability_is_restored() -> None:
    async def scenario() -> None:
        handler = Handler()
        app = gateway(handler)
        data = workflow_manifest().model_dump()
        data["dependencies"] = {
            "central_required": True,
            "central_services": [{"name": "catalog", "required": True}],
        }
        app.engine.workflows = InstalledWorkflows()
        app.engine.workflows.register(type(workflow_manifest()).model_validate(data))
        adapter = N8nAdapter(app, binding())
        unavailable = await adapter.submit(request("event"), item())
        assert unavailable.run.failure is not None
        assert unavailable.run.failure.code == "needs_connectivity" and handler.calls == 0
        app.bridge.services = frozenset({"catalog"})
        available = await adapter.submit(request("event"), item())
        assert available.run.status == "succeeded" and handler.calls == 1

    asyncio.run(scenario())


def test_failed_delivery_never_automatically_retries_or_resumes() -> None:
    class Failing(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            self.calls += 1
            raise RuntimeError("private payload")

    async def scenario() -> None:
        handler = Failing()
        adapter = N8nAdapter(gateway(handler), binding())
        first = await adapter.submit(request("event"), item())
        second = await adapter.submit(request("event"), item())
        assert first.run.status == "failed" and first == second and handler.calls == 1
        assert "private payload" not in first.model_dump_json()

    asyncio.run(scenario())


def test_offline_example_loads_and_runs() -> None:
    from pathlib import Path

    payload = N8nSubmission.model_validate_json(
        (Path(__file__).parents[1] / "integrations/n8n/submission.json").read_text(encoding="utf-8")
    )
    result = asyncio.run(
        N8nAdapter(gateway(Handler()), binding()).submit(request("event"), payload)
    )
    assert result.run.status == "succeeded"


@pytest.mark.parametrize(
    "granted,args,code",
    [
        (False, {}, "permission_denied"),
        (True, {"unexpected": 1}, "invalid_input"),
    ],
)
def test_adapter_adds_no_authority_or_input_coercion(
    granted: bool, args: dict[str, Any], code: str
) -> None:
    handler = Handler()
    result = asyncio.run(
        N8nAdapter(gateway(handler, granted=granted), binding()).submit(
            request("event"), item(**args)
        )
    )
    assert result.run.failure is not None and result.run.failure.code == code
    assert handler.calls == 0


def test_duplicate_delivery_joins_same_run_and_changed_input_conflicts() -> None:
    async def scenario() -> None:
        handler = Handler()
        adapter = N8nAdapter(gateway(handler), binding())
        first = await adapter.submit(request("event"), item(args="original"))
        again = await adapter.submit(request("event"), item(args="original"))
        conflict = await adapter.submit(request("event"), item(args="changed"))
        assert first == again and handler.calls == 1
        assert conflict.run.failure is not None
        assert conflict.run.failure.code == "idempotency_conflict"
        new = await adapter.submit(request("event"), item("operation-2", args="changed"))
        assert new.run.run_id != first.run.run_id and handler.calls == 2

    asyncio.run(scenario())


def test_distinct_bindings_do_not_collide() -> None:
    async def scenario() -> None:
        handler = Handler()
        app = gateway(handler)
        first = await N8nAdapter(app, binding()).submit(request("event"), item())
        second = await N8nAdapter(app, binding(binding_id="other-node")).submit(
            request("event"), item()
        )
        assert first.run.run_id != second.run.run_id and handler.calls == 2

    asyncio.run(scenario())


def test_timeout_redelivery_and_progress_use_original_run() -> None:
    async def scenario() -> None:
        entered, release = asyncio.Event(), asyncio.Event()

        class Waiting(Handler):
            async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
                entered.set()
                await release.wait()
                return await super().__call__(context, inputs)

        handler = Waiting()
        adapter = N8nAdapter(gateway(handler), binding())
        task = asyncio.create_task(
            adapter.submit(request("event"), item(), workflow_timeout_seconds=0.01)
        )
        await entered.wait()
        initial = await task
        assert initial.run.failure is not None and initial.run.failure.code == "workflow_timeout"
        plan = adapter.inspect(request("inspect"), initial.run.run_id)
        assert plan.plan is not None and plan.plan.status == "running"
        stream = adapter.watch(request("watch"), initial.run.run_id)
        assert stream is not None
        duplicates = [
            asyncio.create_task(adapter.submit(request("event"), item())) for _ in range(3)
        ]
        release.set()
        finals = await asyncio.gather(*duplicates)
        events = [event async for event in stream]
        assert all(
            r.run.run_id == initial.run.run_id and r.run.status == "succeeded" for r in finals
        )
        assert handler.calls == 1
        assert events[-1].event == "finished" and events[-1].status == "succeeded"
        assert "validated" not in "".join(event.model_dump_json() for event in events)

    asyncio.run(scenario())


def test_inspect_and_watch_do_not_disclose_other_owner_or_binding() -> None:
    async def scenario() -> None:
        app = gateway(Handler())
        adapter = N8nAdapter(app, binding())
        result = await adapter.submit(request("event"), item())
        other = request("status").model_copy(update={"actor": "other"})
        assert adapter.inspect(other, result.run.run_id).plan is None
        assert adapter.watch(other, result.run.run_id) is None
        target = binding().workflow.model_copy(update={"name": "other-workflow"})
        other_binding = N8nAdapter(app, binding(workflow=target))
        assert other_binding.inspect(request("status"), result.run.run_id).plan is None
        assert other_binding.watch(request("status"), result.run.run_id) is None
        with pytest.raises(ValidationError):
            adapter.watch(request("status"), "bad\nid")

    asyncio.run(scenario())
