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
from pathlib import Path

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
        workspace_root: Path | None = None,
    ) -> None:
        self.installed = installed
        self.model = model
        self.model_alias = model_alias
        self.local_only = local_only
        self.workspace_root = workspace_root.resolve() if workspace_root is not None else None

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        item = DraftWorkflowRequest.model_validate(inputs)
        return await asyncio.to_thread(self._draft, item, context)

    def _draft(self, item: DraftWorkflowRequest, context: RequestContext) -> WorkflowDraft:
        if item.sop_pdf_path is not None:
            sop = self._read_pdf(item.sop_pdf_path)
            if sop is None:
                return WorkflowDraft(
                    refusal="sop_unreadable",
                    preview=(
                        "The SOP PDF could not be read from this host workspace. "
                        "Use a readable PDF below the workspace and install the office extra."
                    ),
                    request=item,
                )
            item = item.model_copy(update={"sop": sop, "sop_pdf_path": None})
        return draft_workflow(
            item,
            self.installed,
            model=self.model,
            model_alias=self.model_alias,
            trace=context.trace,
            local_only=self.local_only,
        )

    def _read_pdf(self, raw_path: str) -> str | None:
        """Read one operator-supplied SOP fixture without letting it escape the host.

        PDF support remains an optional host dependency.  The error deliberately
        becomes the closed `sop_unreadable` result rather than provider/parser
        exception text, which can include local paths or document content.
        """
        if self.workspace_root is None:
            return None
        try:
            path = Path(raw_path).resolve()
            path.relative_to(self.workspace_root)
            if path.suffix.lower() != ".pdf" or not path.is_file():
                return None
            from pypdf import PdfReader

            text = "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages).strip()
            return text if text else None
        except (ImportError, OSError, ValueError):
            return None
