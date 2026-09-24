"""Personal-Agent use case for proving an SOP-derived Workflow.

Drafting still enters through the resident Agent and its normal Gateway route.
Validation installs the draft only in a throwaway WorkflowEngine, then executes
its steps through the same Bridge and policy as the host. Nothing is added to the
host inventory, Registry or distribution plane.
"""

from __future__ import annotations

import hashlib

from agent.gateway import Gateway
from capabilities.workflow_author.contracts import (
    WorkflowAcceptanceOutcome,
    WorkflowAcceptanceRequest,
    WorkflowDraft,
    WorkflowValidationEvidence,
)
from capabilities.workflow_author.handlers import DRAFT_SPEC
from common.assets import BusinessApproval, WorkflowManifest, WorkflowStep
from common.execution import RequestContext
from common.local_agent import LocalAgentRequest
from host_runtime.agent import LocalAgent
from workflow.engine import InstalledWorkflows, WorkflowEngine


def manifest_sha256(manifest: WorkflowManifest) -> str:
    document = manifest.model_dump_json(exclude_none=False)
    return hashlib.sha256(document.encode("utf-8")).hexdigest()


class PersonalWorkflowAuthor:
    """One bounded user request: draft, execute fixtures, validate."""

    def __init__(self, agent: LocalAgent) -> None:
        self.agent = agent

    async def run(
        self, user: LocalAgentRequest, acceptance: WorkflowAcceptanceRequest
    ) -> WorkflowAcceptanceOutcome:
        request = LocalAgentRequest.model_validate(user)
        asked = WorkflowAcceptanceRequest.model_validate(acceptance)
        if request.namespace != asked.draft.namespace:
            return WorkflowAcceptanceOutcome(trace=request.trace, refusal="namespace_mismatch")

        routed = await self.agent.handle(request)
        if routed.refusal is not None:
            return WorkflowAcceptanceOutcome(trace=request.trace, refusal=routed.refusal)
        if (
            routed.decision is None
            or routed.decision.kind != "capability"
            or routed.decision.target != DRAFT_SPEC.identity
            or routed.capability is None
            or routed.capability.status != "succeeded"
        ):
            code = (
                routed.capability.failure.code
                if routed.capability is not None and routed.capability.failure is not None
                else "draft_route_failed"
            )
            return WorkflowAcceptanceOutcome(trace=request.trace, refusal=code)

        draft = WorkflowDraft.model_validate(routed.capability.data)
        if draft.request != asked.draft:
            return WorkflowAcceptanceOutcome(
                trace=request.trace, draft=draft, refusal="draft_request_mismatch"
            )
        if draft.manifest is None:
            return WorkflowAcceptanceOutcome(trace=request.trace, draft=draft)

        evidence = await self._validate(request, draft.manifest, asked)
        return WorkflowAcceptanceOutcome(
            trace=request.trace,
            draft=draft,
            validation=evidence,
        )

    async def _validate(
        self,
        request: LocalAgentRequest,
        manifest: WorkflowManifest,
        acceptance: WorkflowAcceptanceRequest,
    ) -> WorkflowValidationEvidence:
        workflows = InstalledWorkflows()
        workflows.register(manifest)
        # A throwaway engine proves the candidate without installing it on the
        # host. Its Bridge is the real host Bridge, so grants and approvals are
        # exactly the ones normal execution uses.
        engine = WorkflowEngine(workflows, self.agent.gateway.bridge)
        gateway = Gateway(
            self.agent.gateway.router,
            self.agent.gateway.bridge,
            engine,
        )
        context = self._context(request)
        snapshot = await gateway.execute_workflow(
            context,
            manifest.metadata.identity,
            dict(acceptance.fixture.arguments),
        )
        observed = (
            snapshot.step_results[-1].data
            if snapshot.run.status == "succeeded" and snapshot.step_results
            else None
        )
        code: str | None = None
        if snapshot.run.status != "succeeded":
            code = snapshot.run.failure.code if snapshot.run.failure else "workflow_failed"
        elif observed != acceptance.fixture.expected_output:
            code = "output_mismatch"
        dispatched = tuple(
            step.capability if isinstance(step, WorkflowStep) else step for step in manifest.steps
        )
        return WorkflowValidationEvidence(
            trace=request.trace,
            manifest_sha256=manifest_sha256(manifest),
            status="failed" if code else "passed",
            code=code,
            run_id=snapshot.run.run_id,
            completed_steps=snapshot.run.completed_steps,
            dispatched=dispatched,
            expected_output=acceptance.fixture.expected_output,
            observed_output=observed,
        )

    @staticmethod
    def _context(request: LocalAgentRequest) -> RequestContext:
        return RequestContext(
            trace=request.trace,
            actor=request.actor,
            namespace=request.namespace,
            message=request.message,
            channel=request.ingress,
            session_id=request.session_id,
        )


def publish_validated_workflow(
    outcome: WorkflowAcceptanceOutcome, approval: BusinessApproval
) -> WorkflowManifest:
    """Pure human lifecycle transition; registration and authorization stay separate."""

    checked = WorkflowAcceptanceOutcome.model_validate(outcome)
    reviewed = BusinessApproval.model_validate(approval)
    if reviewed.status != "approved":
        raise ValueError("publication requires approved business review")
    if (
        checked.draft is None
        or checked.draft.manifest is None
        or checked.validation is None
        or checked.validation.status != "passed"
    ):
        raise ValueError("publication requires passing validation evidence")
    manifest = checked.draft.manifest
    if checked.validation.manifest_sha256 != manifest_sha256(manifest):
        raise ValueError("validation evidence belongs to another manifest")
    reference = (
        f"workflow-validation:{checked.validation.manifest_sha256}:{checked.validation.run_id}"
    )
    metadata = manifest.metadata.model_copy(
        update={
            "lifecycle": "published",
            "business_approval": reviewed,
            "validation_refs": (*manifest.metadata.validation_refs, reference),
        }
    )
    return manifest.model_copy(update={"metadata": metadata})
