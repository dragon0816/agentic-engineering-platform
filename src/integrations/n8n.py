"""Offline n8n host seam; no HTTP server, node runtime or production connection.

The host authenticates the caller and chooses a reviewed binding. Payloads supply
only an operation id and arguments; Gateway/Bridge remain the execution authority.
"""

import hashlib
import json

from pydantic import Field, JsonValue

from agent.gateway import Gateway, RunControlResult
from common.assets import AssetIdentity
from common.base import Contract, Symbol
from common.execution import IdempotencyKey, RequestContext, RunId
from workflow.engine import ProgressStream, WorkflowRunSnapshot


class N8nSubmission(Contract):
    operation_id: IdempotencyKey
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class N8nWorkflowBinding(Contract):
    """Trusted host configuration, never parsed from an external submission."""

    binding_id: Symbol
    workflow: AssetIdentity


class N8nAdapter:
    def __init__(self, gateway: Gateway, binding: N8nWorkflowBinding) -> None:
        self.gateway = gateway
        self.binding = N8nWorkflowBinding.model_validate(binding)

    async def submit(
        self,
        context: RequestContext,
        submission: N8nSubmission,
        *,
        workflow_timeout_seconds: float | None = None,
    ) -> WorkflowRunSnapshot:
        checked = N8nSubmission.model_validate(submission)
        # Stable across redelivery and traces. Engine fingerprints intent and
        # scopes the key by actor/namespace. Changing a target under the same
        # binding/operation conflicts instead of silently executing another job.
        identity = json.dumps(
            [self.binding.binding_id, checked.operation_id], separators=(",", ":")
        )
        key = "n8n:" + hashlib.sha256(identity.encode()).hexdigest()
        return await self.gateway.execute_workflow(
            context,
            self.binding.workflow,
            checked.arguments,
            workflow_timeout_seconds=workflow_timeout_seconds,
            workflow_idempotency_key=key,
        )

    def inspect(self, context: RequestContext, run_id: RunId) -> RunControlResult:
        result = self.gateway.inspect(context, run_id)
        if result.plan is not None and result.plan.workflow != self.binding.workflow:
            return RunControlResult(action="inspect", run_id=run_id)
        return result

    def watch(self, context: RequestContext, run_id: RunId) -> ProgressStream | None:
        # Owner checks stay in Gateway/engine; this adapter additionally limits
        # visibility to its bound workflow before allocating a watcher slot.
        if self.inspect(context, run_id).plan is None:
            return None
        return self.gateway.watch(context, run_id)
