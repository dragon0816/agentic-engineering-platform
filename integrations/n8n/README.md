# Optional n8n adapter — offline host seam

This slice provides a Python integration boundary and offline tests. It does not
install an n8n node, expose an HTTP endpoint, import a live workflow, send a message
or connect to a production instance. The platform does not depend on n8n.

## Host wiring

The host installs reviewed capabilities/workflows and policy grants as usual,
authenticates callers, chooses a binding and supplies RequestContext independently
of the incoming JSON. Never parse an actor, binding, grant or resume policy from
the submitted payload. One binding identifies one intended n8n workflow/node
operation and selects an exact platform workflow version.

```python
from agent.gateway import Gateway
from common.execution import RequestContext
from integrations.n8n import N8nAdapter, N8nSubmission, N8nWorkflowBinding


def bind_release(gateway: Gateway) -> N8nAdapter:
    binding = N8nWorkflowBinding.model_validate(
        {
            "binding_id": "release-validation-node",
            "workflow": {
                "namespace": "engineering",
                "name": "release-validation",
                "version": "1.0.0",
            },
        }
    )
    return N8nAdapter(gateway, binding)


async def on_authenticated_submission(
    adapter: N8nAdapter, context: RequestContext, body: str
) -> str:
    submission = N8nSubmission.model_validate_json(body)
    result = await adapter.submit(context, submission)
    return result.model_dump_json()
```

The referenced release workflow/capability in tests is inert. Real host installation
and authentication, an eventual network transport and n8n-node configuration are
separate future work; this example does not supply them. Use
`submission.json` with `tests/test_n8n.py::test_offline_example_loads_and_runs`.

## Delivery and results

- Reuse `operation_id` for retries/redelivery of the same logical operation. Use
  a new id only for new work. It is a bounded ASCII identifier, not a credential.
  Do not assume a transport's delivery identifier remains stable on retries.
- Binding id + operation id derive a stable engine key; actor/namespace scope and
  intent-conflict checks remain in the engine. Preserve non-trace RequestContext
  on redelivery; a fresh trace is allowed, but the returned run keeps its original
  trace. Changed parameters, context or workflow conflict instead of executing.
- The adapter returns the shared WorkflowRunSnapshot unchanged. Success means
  `run.status == "succeeded"`. The pinned source graph used `ok` plus
  `data.status == "success"`; that old HTTP wrapper is not the new contract.
- `workflow_timeout` bounds the caller's wait, not the running job. Inspect/watch
  the original run (or resubmit the same operation id) rather than creating a new
  operation. No adapter retry or automatic resume occurs.
- `adapter.inspect(context, run_id)` returns Gateway's RunControlResult.
  `adapter.watch(context, run_id)` returns its bounded ProgressStream or None.
  Both require the run's owner and this binding's workflow. Use `aclose()` when
  leaving a stream early; honor `lagged` and `rejected/watch_capacity` events.
  Streams contain metadata only; run snapshots contain validated result data.
- Engine idempotency is in memory, capped at 50 retained keys; `idempotency_capacity`
  refuses new keyed work. Replacing the engine loses keys. This is not durable
  exactly-once execution, and changing ids/restarting must not be an automatic
  response to timeouts or capacity. Persistence remains outside this slice.

## Offline verification

```sh
python -m pytest -q tests/test_n8n.py tests/test_source_n8n.py
```

Tests exercise the actual Gateway, engine and Bridge with inert handlers, covering
explicit dispatch, policy denial, duplicate/concurrent delivery, timeouts, status
and progress ownership. `tests/fixtures/source_n8n_release.json` is a declarative
source projection for characterization, not an importable n8n workflow.
