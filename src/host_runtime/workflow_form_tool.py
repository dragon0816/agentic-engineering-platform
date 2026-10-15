"""The conversation tool that hands a person a Workflow's run form.

A model that decides the person wants to run an installed Workflow calls this
tool instead of collecting the values in prose (owner 2026-10-15). It runs
nothing: it names the Workflow and the run values the person already stated
(only fields a model may set), and the Gateway ends the turn with the offer,
which Agent Web draws as the inline form and Telegram as its question flow.
"""

from __future__ import annotations

from typing import Any

from agent.gateway import HostTool, HostToolOutcome
from common.assets import WorkflowManifest
from common.execution import Failure, RequestContext
from common.workflow_run_form import FORM_TOOL, OFFER_KEY, agent_prefill, form_offer
from models.contracts import ModelTool
from workflow.engine import WorkflowEngine

#: Installed Workflow names listed in the tool's schema; more are still found.
MAX_LISTED = 100


def resolve(manifests: tuple[WorkflowManifest, ...], name: str) -> WorkflowManifest | str:
    """One installed Workflow by `name`, `namespace/name` or run number."""
    target = name.strip()
    if "@" in target:
        target = target.rsplit("@", 1)[0]
    found = [
        item
        for item in manifests
        if (target.isdigit() and item.run_alias == int(target))
        or target
        in (
            item.metadata.identity.name,
            f"{item.metadata.identity.namespace}/{item.metadata.identity.name}",
        )
    ]
    if not found:
        return "workflow_not_installed"
    if len(found) > 1:
        return "workflow_name_ambiguous"
    return found[0]


def workflow_form_tools(engine: WorkflowEngine) -> tuple[HostTool, ...]:
    manifests = engine.workflows.manifests()
    if not manifests:
        return ()
    names = sorted({item.metadata.identity.name for item in manifests})

    async def handler(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        found = resolve(engine.workflows.manifests(), str(args.get("workflow") or ""))
        if isinstance(found, str):
            return HostToolOutcome(
                status="failed",
                failure=Failure(code=found, message="Name one installed Workflow exactly."),
            )
        values = args.get("values")
        prefill = agent_prefill(found, values if isinstance(values, dict) else {})
        offer = form_offer(found, prefill, engine.settings_provider, origin="agent")
        return HostToolOutcome(status="succeeded", data={OFFER_KEY: offer})

    workflow: dict[str, Any] = {"type": "string", "description": "The Workflow's name."}
    if len(names) <= MAX_LISTED:
        workflow["enum"] = names
    return (
        HostTool(
            ModelTool(
                name=FORM_TOOL,
                description=(
                    "Show the person the run form of an installed Workflow when they ask to run it. "
                    "Give `workflow` and, in `values`, only run values the person already stated, by "
                    "parameter name; never guess one. The form asks for the rest and shows which "
                    "settings are missing; settings are never run values. Nothing runs until the "
                    "person presses Run; the turn ends with the form."
                ),
                input_contract="host.workflow-form.v1",
                input_schema={
                    "type": "object",
                    "properties": {
                        "workflow": workflow,
                        "values": {
                            "type": "object",
                            "description": "Run values the person stated, by parameter name.",
                        },
                    },
                    "required": ["workflow"],
                },
            ),
            handler,
        ),
    )
