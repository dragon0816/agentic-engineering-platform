import asyncio
from typing import Any

import pytest
from test_dispatch import Handler
from test_engine import context, engine
from test_gateway import Handler as GatewayHandler
from test_gateway import gateway, request

from capabilities.runtime import InstalledCapabilities, LocalPolicy, TransientCapabilityError
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from workflow.engine import MAX_RUNS_KEPT


def test_duplicate_submission_returns_original_run_and_trace() -> None:
    async def scenario() -> None:
        handler = Handler()
        runner, flow = engine(handler, steps=1)
        first = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="request-one"
        )
        changed = context().model_dump()
        changed["trace"]["request_id"] = "new-request"
        second = await runner.execute(
            RequestContext.model_validate(changed),
            flow.metadata.identity,
            {"count": 1},
            idempotency_key="request-one",
        )
        assert first == second and len(handler.calls) == 1
        assert second.run.trace == context().trace

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "changes",
    [
        {"arguments": {"count": 2}},
        {"message": "different"},
        {"channel": "other"},
        {"session_id": "other"},
    ],
)
def test_key_conflict_never_reexecutes(changes: dict[str, Any]) -> None:
    async def scenario() -> None:
        handler = Handler()
        runner, flow = engine(handler, steps=1)
        await runner.execute(context(), flow.metadata.identity, {"count": 1}, idempotency_key="key")
        ctx = context().model_dump()
        ctx.update({k: v for k, v in changes.items() if k != "arguments"})
        result = await runner.execute(
            RequestContext.model_validate(ctx),
            flow.metadata.identity,
            changes.get("arguments", {"count": 1}),
            idempotency_key="key",
        )
        assert result.run.failure is not None and result.run.failure.code == "idempotency_conflict"
        assert len(handler.calls) == 1 and runner.get(result.run.run_id) is None

    asyncio.run(scenario())


def test_concurrent_submission_and_timeout_do_not_duplicate_work() -> None:
    async def scenario() -> None:
        release = asyncio.Event()
        entered = asyncio.Event()

        class Waiting(Handler):
            async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
                entered.set()
                await release.wait()
                return await super().__call__(context, inputs)

        handler = Waiting()
        runner, flow = engine(handler, steps=1)
        first = asyncio.create_task(
            runner.execute(
                context(),
                flow.metadata.identity,
                {"count": 1},
                idempotency_key="key",
                timeout_seconds=0.01,
            )
        )
        await entered.wait()
        timed_out = await first
        assert timed_out.run.failure is not None
        assert timed_out.run.failure.code == "workflow_timeout"
        duplicates = [
            asyncio.create_task(
                runner.execute(
                    context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
                )
            )
            for _ in range(3)
        ]
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(*duplicates)
        assert len(handler.calls) == 1
        assert all(
            r.run.run_id == timed_out.run.run_id and r.run.status == "succeeded" for r in results
        )

    asyncio.run(scenario())


def test_replay_rechecks_authorization() -> None:
    async def scenario() -> None:
        handler = Handler()
        runner, flow = engine(handler, steps=1)
        await runner.execute(context(), flow.metadata.identity, {"count": 1}, idempotency_key="key")
        runner.bridge.policy = LocalPolicy()
        denied = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        assert denied.run.failure is not None and denied.run.failure.code == "permission_denied"
        assert denied.step_results == () and len(handler.calls) == 1

    asyncio.run(scenario())


def test_key_survives_history_eviction() -> None:
    async def scenario() -> None:
        handler = Handler()
        runner, flow = engine(handler, steps=1)
        first = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        for _ in range(MAX_RUNS_KEPT):
            await runner.execute(context(), flow.metadata.identity, {"count": 1})
        assert runner.get(first.run.run_id) is None
        replay = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        assert replay == first and len(handler.calls) == MAX_RUNS_KEPT + 1

    asyncio.run(scenario())


def test_gateway_passes_key_to_workflow_engine() -> None:
    async def scenario() -> None:
        handler = GatewayHandler()
        app = gateway(handler)
        first = await app.handle(request("release.package"), workflow_idempotency_key="key")
        second = await app.handle(request("release.package"), workflow_idempotency_key="key")
        assert first.workflow == second.workflow and handler.calls == 1

    asyncio.run(scenario())


def test_gateway_does_not_ignore_workflow_key_on_capability_route() -> None:
    handler = GatewayHandler()
    result = asyncio.run(
        gateway(handler).handle(request("release.check"), workflow_idempotency_key="key")
    )
    assert result.capability is not None and result.capability.failure is not None
    assert result.capability.failure.code == "idempotency_not_supported"
    assert handler.calls == 0


def test_capacity_fails_closed_without_evicting_old_keys() -> None:
    from workflow.engine import MAX_IDEMPOTENCY_KEYS

    async def scenario() -> None:
        handler = Handler()
        runner, flow = engine(handler, steps=1)
        first = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key-0"
        )
        for n in range(1, MAX_IDEMPOTENCY_KEYS):
            await runner.execute(
                context(), flow.metadata.identity, {"count": 1}, idempotency_key=f"key-{n}"
            )
        full = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="overflow"
        )
        assert full.run.failure is not None and full.run.failure.code == "idempotency_capacity"
        assert runner.get(full.run.run_id) is None
        again = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key-0"
        )
        assert first == again and len(handler.calls) == MAX_IDEMPOTENCY_KEYS

    asyncio.run(scenario())


@pytest.mark.parametrize("effect", ["write", "execute", "external_side_effect"])
@pytest.mark.parametrize("fail", [False, True])
def test_keyed_side_effect_is_not_reexecuted(effect: str, fail: bool) -> None:
    from test_dispatch import Input, Output, spec

    class Uncertain(Handler):
        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            if not fail:
                return await super().__call__(context, inputs)
            self.calls.append(context)
            raise TransientCapabilityError("may already have completed the effect")

    async def scenario() -> None:
        handler = Uncertain()
        runner, flow = engine(handler, steps=1)
        installed = InstalledCapabilities()
        data = spec().model_dump()
        data["side_effect"] = effect
        installed.register(
            type(spec()).model_validate(data),
            handler,
            Input,
            Output,
            ExecutionDependencies(central_required=False),
        )
        runner.bridge.installed = installed
        first = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        second = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        assert first.run.status == ("failed" if fail else "succeeded")
        assert first == second and len(handler.calls) == 1
        if first.run.failure is not None:
            assert not first.run.failure.retryable

    asyncio.run(scenario())


def test_cancelled_run_keeps_key_without_reexecution() -> None:
    async def scenario() -> None:
        class Waiting(Handler):
            async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
                self.calls.append(context)
                await asyncio.Event().wait()
                return inputs

        handler = Waiting()
        runner, flow = engine(handler, steps=1)
        initial = await runner.execute(
            context(),
            flow.metadata.identity,
            {"count": 1},
            idempotency_key="key",
            timeout_seconds=0.01,
        )
        runner._tasks[initial.run.run_id].cancel()
        final = await runner.wait(initial.run.run_id)
        assert final is not None and final.run.failure is not None
        assert final.run.failure.code == "workflow_aborted"
        replay = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        assert replay == final and len(handler.calls) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("scope", ["actor", "namespace"])
def test_keys_are_scoped_to_actor_and_namespace(scope: str) -> None:
    from test_dispatch import grant

    async def scenario() -> None:
        handler = Handler()
        runner, flow = engine(handler, steps=1)
        runner.bridge.policy = LocalPolicy((grant(), grant(actor="other")))
        first = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        changed = context().model_dump()
        changed[scope] = "other"
        second = await runner.execute(
            RequestContext.model_validate(changed),
            flow.metadata.identity,
            {"count": 1},
            idempotency_key="key",
        )
        assert first.run.run_id != second.run.run_id and len(handler.calls) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("key", ["", "white space", "x" * 129, True, 1])
def test_invalid_keys_rejected_before_execution(key: Any) -> None:
    from pydantic import ValidationError

    handler = Handler()
    runner, flow = engine(handler, steps=1)
    with pytest.raises(ValidationError):
        asyncio.run(
            runner.execute(context(), flow.metadata.identity, {"count": 1}, idempotency_key=key)
        )
    assert handler.calls == []


def test_preflight_does_not_consume_key() -> None:
    async def scenario() -> None:
        handler = Handler()
        runner, flow = engine(handler, steps=1)
        missing = flow.metadata.identity.model_copy(update={"name": "missing"})
        rejected = await runner.execute(context(), missing, {"count": 1}, idempotency_key="key")
        assert rejected.run.status == "unavailable"
        result = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, idempotency_key="key"
        )
        assert result.run.status == "succeeded" and len(handler.calls) == 1

    asyncio.run(scenario())
