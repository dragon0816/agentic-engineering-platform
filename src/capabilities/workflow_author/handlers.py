"""The capability that drafts a Workflow, and its spec.

A **read**: it reaches a model and returns a document, and installs nothing,
publishes nothing and runs nothing. So a member may be given drafting without
being given any power to change this machine -- though it is still granted
deliberately, like everything else here, because reaching a paid gateway is
worth giving on purpose even when it writes nothing.

Installing what comes out is a separate, deliberate act by a person, which is
the architecture's own lifecycle and not a caution added here.
"""

from __future__ import annotations

import asyncio

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities
from capabilities.workflow_author.contracts import DraftWorkflowRequest, WorkflowDraft
from capabilities.workflow_author.draft import draft_workflow
from common.base import Contract
from common.execution import RequestContext
from models.contracts import ModelClient

DRAFT_SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "workflow-author", "name": "draft", "version": "1.0.0"},
        "name": "workflow_author.draft",
        "description": "Draft a Workflow this machine could run from a written procedure",
        "input_contract": "workflow-author.draft.input.v1",
        "output_contract": "workflow-author.draft.output.v1",
        # A draft changes nothing. What it produces is text until a person
        # installs it, and installing is not this capability.
        "side_effect": "read",
        "policy": {
            "required_permissions": ["workflow-author.draft"],
            "policy_refs": ["workflow-author-policy"],
        },
    }
)


class DraftWorkflowHandler:
    """Drafting over whichever model the host configured.

    It holds the machine's own capability registry -- the same object it is
    registered into -- and reads it per call, so a Workflow drafted after
    something new is installed can use it without this being rebuilt.
    """

    def __init__(
        self,
        installed: InstalledCapabilities,
        *,
        model: ModelClient | None = None,
        model_alias: str = "routing",
        local_only: bool = False,
    ) -> None:
        self.installed = installed
        self.model = model
        self.model_alias = model_alias
        self.local_only = local_only

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = DraftWorkflowRequest.model_validate(inputs)
        return await asyncio.to_thread(self._draft, item, context)

    def _draft(self, item: DraftWorkflowRequest, context: RequestContext) -> WorkflowDraft:
        return draft_workflow(
            item,
            self.installed,
            model=self.model,
            model_alias=self.model_alias,
            trace=context.trace,
            local_only=self.local_only,
        )
