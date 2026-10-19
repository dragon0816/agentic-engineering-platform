"""The `cards__*` conversation tools (docs/phases/BUSINESS_CARDS.md §4).

Offered only while some version of the `engineering/business-cards` Skill is
switched on and the capabilities are installed. Each tool carries its own
argument schema (a Skill command to a capability would carry none) and every
call is a `CapabilityInvocation` through the Bridge with `origin: model`,
under the actor's grants. The contact-store writes run without a per-call
confirmation because the Host confirmed them standing
(`LocalPolicy.confirm_writes`); anything else that asks for approval goes to
the owner's approval button as for any model-chosen side effect.

`chart_files` and `with_legend` let Agent Web and Telegram show what
`cards__org_chart` produced: its PNG and its Markdown legend.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agent.gateway import GatewayConversationResult, HostTool, HostToolOutcome
from capabilities.business_cards import handlers as cards
from capabilities.business_cards.contracts import FIELDS
from capabilities.business_cards.manifest import CARDS_SKILL
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityInvocation
from common.execution import Failure, RequestContext
from models.contracts import ModelTool

CHART_TOOL = "cards__org_chart"

_S: dict[str, Any] = {"type": "string"}
_FIELD_PROPS: dict[str, Any] = {name: _S for name in FIELDS}
_FIELD_PROPS["romanised_name"] = {
    "type": "string",
    "description": "the romanised / English form of the name",
}
_FIELD_PROPS["business_group"] = {"type": "string", "description": "事業群 / BG"}
_FIELD_PROPS["division"] = {"type": "string", "description": "處 / BU"}
_FIELD_PROPS["department"] = {"type": "string", "description": "部 / 課 / team"}
_FIELD_PROPS["phone"] = {"type": "string", "description": "desk number"}
_FIELD_PROPS["ext"] = {"type": "string", "description": "desk extension"}
_FIELD_PROPS["mobile"] = {"type": "string", "description": "cellphone"}
_UNCERTAIN = {
    "type": "array",
    "items": {"type": "string", "enum": list(FIELDS)},
    "description": "every field not read with confidence",
}
_PERSON = {
    "type": "object",
    "properties": {
        "person_id": {"type": "string", "description": "from an earlier result"},
        "name": {"type": "string", "description": "local or romanised name"},
        "company": {"type": "string"},
    },
    "description": "person_id, or name (with company when names repeat)",
}
_DATE = {"type": "string", "description": "YYYY-MM-DD"}


def _object(properties: dict[str, Any], required: Sequence[str] = ()) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(required)}


#: (tool name, capability, description, argument schema)
TOOLS: tuple[tuple[str, CapabilitySpec, str, dict[str, Any]], ...] = (
    (
        "cards__add_card",
        cards.ADD_CARD_SPEC,
        "Store one business card read from a photo in the person's contacts. Returns whether "
        "the person existed, the changes, kept values and a summary sentence to lead with.",
        _object(
            {
                **_FIELD_PROPS,
                "uncertain": _UNCERTAIN,
                "image_path": {"type": "string", "description": "the attached photo's path"},
                "card_date": _DATE,
            },
            ("name",),
        ),
    ),
    (
        "cards__add_from_signature",
        cards.ADD_SIGNATURE_SPEC,
        "Store people the person confirmed from email signatures (from "
        "cards__harvest_signatures), with each message_id and message_date as given.",
        _object(
            {
                "entries": {
                    "type": "array",
                    "items": _object(
                        {
                            **_FIELD_PROPS,
                            "message_id": _S,
                            "message_date": _DATE,
                            "uncertain": _UNCERTAIN,
                        },
                        ("message_id", "message_date"),
                    ),
                }
            },
            ("entries",),
        ),
    ),
    (
        "cards__edit_person",
        cards.EDIT_SPEC,
        "Correct a contact's fields as the person says (recorded as the person's own value, "
        "never overwritten by later scans).",
        _object(
            {"person": _PERSON, "fields": _object(_FIELD_PROPS), "reason": _S},
            ("person", "fields"),
        ),
    ),
    (
        "cards__find",
        cards.FIND_SPEC,
        "Find contacts by name (local or romanised), email, company or title.",
        _object(
            {
                "query": _S,
                "status": {"type": "string", "enum": ["active", "left", "any"]},
                "limit": {"type": "integer"},
            },
            ("query",),
        ),
    ),
    (
        "cards__list",
        cards.LIST_SPEC,
        "List contacts by company, by source (card, email_signature, user, import) and status.",
        _object(
            {
                "company": _S,
                "source": {
                    "type": "string",
                    "enum": ["", "card", "email_signature", "user", "import"],
                },
                "status": {"type": "string", "enum": ["active", "left", "any"]},
                "limit": {"type": "integer"},
            }
        ),
    ),
    (
        "cards__history",
        cards.HISTORY_SPEC,
        "One contact's changes (with change ids for cards__undo), sightings and open proposals.",
        _object({"person": _PERSON, "limit": {"type": "integer"}}, ("person",)),
    ),
    (
        "cards__set_status",
        cards.STATUS_SPEC,
        "Only when the person says so: mark a contact as left (or active again), with the "
        "reason, who said it and the date. Recorded and undoable.",
        _object(
            {
                "person": _PERSON,
                "status": {"type": "string", "enum": ["left", "active"]},
                "reason": _S,
                "said_by": _S,
                "effective_date": _DATE,
            },
            ("person", "status"),
        ),
    ),
    (
        "cards__set_reporting_line",
        cards.SET_LINE_SPEC,
        "Record who a contact reports to, with its evidence: signature, email_content, user "
        "(drawn solid) or title_inference (inferred, drawn dashed). Replaces their line.",
        _object(
            {
                "person": _PERSON,
                "manager": _PERSON,
                "evidence_kind": {
                    "type": "string",
                    "enum": ["signature", "email_content", "title_inference", "user"],
                },
                "evidence_ref": {
                    "type": "string",
                    "description": "message id, or what the person said",
                },
                "confidence": {"type": "number"},
                "inferred": {"type": "boolean"},
            },
            ("person", "manager", "evidence_kind"),
        ),
    ),
    (
        "cards__remove_reporting_line",
        cards.REMOVE_LINE_SPEC,
        "Remove a contact's current reporting line, with a reason. Undoable.",
        _object({"person": _PERSON, "reason": _S}, ("person",)),
    ),
    (
        "cards__undo",
        cards.UNDO_SPEC,
        "Undo one recorded change by its change_id (from a result or cards__history).",
        _object({"change_id": _S}, ("change_id",)),
    ),
    (
        CHART_TOOL,
        cards.CHART_SPEC,
        "Draw a company's org chart from the contacts: a PNG the person sees and a Markdown "
        "legend to include in the answer. People who left are left out unless include_left.",
        _object({"company": _S, "include_left": {"type": "boolean"}}, ("company",)),
    ),
    (
        "cards__harvest_signatures",
        cards.HARVEST_SPEC,
        "Read signature blocks from the person's mail from one company domain (e.g. "
        "example.com), within the mail scope set in Settings; returns candidates and stores "
        "nothing.",
        _object(
            {
                "domain": _S,
                "days": {"type": "integer"},
                "limit": {"type": "integer"},
                "folder": _S,
            },
            ("domain",),
        ),
    ),
    (
        "cards__import_hermes",
        cards.IMPORT_SPEC,
        "Import the old Hermes business-cards store (~/.business-cards/cards.db) once; "
        "repeating it adds nothing.",
        _object({}),
    ),
)


def skill_on(gateway: Any) -> bool:
    """Some version of the business-cards Skill is switched on here."""
    try:
        manifests = gateway.router.commands.skills.manifests()
    except AttributeError:
        return False
    return any(
        item.metadata.identity.namespace == CARDS_SKILL.namespace
        and item.metadata.identity.name == CARDS_SKILL.name
        for item in manifests
    )


def _procedure(gateway: Any) -> str:
    found = [
        item
        for item in gateway.router.commands.skills.manifests()
        if item.metadata.identity.namespace == CARDS_SKILL.namespace
        and item.metadata.identity.name == CARDS_SKILL.name
    ]
    return found[-1].instructions if found else ""


def _tool(
    gateway: Any, name: str, spec: CapabilitySpec, description: str, schema: dict[str, Any]
) -> HostTool:
    async def call(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        result = await gateway.bridge.execute(
            CapabilityInvocation(
                context=context, origin="model", target=spec.identity, arguments=arguments
            )
        )
        if result.status == "succeeded":
            return HostToolOutcome(status="succeeded", data=result.data)
        approval = getattr(gateway, "capability_approval", None)
        if (
            result.failure is not None
            and result.failure.code == "approval_required"
            and approval is not None
        ):
            pending = await asyncio.to_thread(approval, context, spec.identity, arguments)
            return HostToolOutcome(status="awaiting_approval", data=pending)
        return HostToolOutcome(
            status="failed",
            data=result.data,
            failure=result.failure or Failure(code=result.status, message=result.status),
        )

    return HostTool(
        ModelTool(
            name=name,
            description=description,
            input_contract=f"host.{name}.v1",
            input_schema=schema,
        ),
        call,
    )


def business_cards_tools(gateway: Any) -> Sequence[HostTool]:
    """The tools, while the Skill is on; the first carries its procedure."""
    if not skill_on(gateway):
        return []
    procedure = _procedure(gateway)
    tools: list[HostTool] = []
    for name, spec, description, schema in TOOLS:
        if gateway.bridge.installed.get(spec.identity) is None:
            continue
        text = description if tools else f"{description} PROCEDURE: {procedure}"
        tools.append(_tool(gateway, name, spec, text, schema))
    return tools


def chart_files(result: GatewayConversationResult | None) -> list[dict[str, str]]:
    """The files `cards__org_chart` produced in this turn, with the legend
    text on the PNG's entry, newest chart last."""
    files: list[dict[str, str]] = []
    if result is None:
        return files
    for item in result.tools:
        host = item.host
        if item.name != CHART_TOOL or host is None or host.status != "succeeded":
            continue
        data = host.data if isinstance(host.data, dict) else {}
        attach = data.get("attach")
        if not isinstance(attach, list):
            continue
        legend = data.get("legend_markdown")
        for entry in attach:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if not isinstance(path, str) or not Path(path).is_file():
                continue
            shown = {
                "filename": str(entry.get("filename") or Path(path).name),
                "kind": "image" if entry.get("media_type") == "image/png" else "text",
                "path": path,
            }
            if shown["kind"] == "image" and isinstance(legend, str):
                shown["legend"] = legend
            files.append(shown)
    return files


def short_legend(legend: str) -> str:
    """The legend without its table: the title and what the picture is
    (for a phone screen; the full legend goes along as a file)."""
    kept = [line for line in legend.splitlines() if not line.startswith("|")]
    return "\n".join(kept).strip()


def with_legend(answer: str, files: Sequence[dict[str, str]], *, short: bool = False) -> str:
    """The answer with each chart's legend, when the model left it out;
    `short` keeps only its title and notes (Telegram)."""
    out = answer
    for entry in files:
        legend = entry.get("legend")
        if not legend:
            continue
        if short:
            legend = short_legend(legend)
        first = legend.splitlines()[0] if legend.splitlines() else legend
        table = "| 成員 | 主管 |" in legend and not short
        if first not in out or (table and "| 成員 | 主管 |" not in out):
            out = f"{out.rstrip()}\n\n{legend}" if out.strip() else legend
    return out
