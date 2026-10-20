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
from capabilities.business_cards.contracts import FIELD_LABELS, FIELDS
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
    "description": "the romanised / English name ONLY when it is printed on the card; never "
    "derived from the email or the Chinese name; empty when not printed",
}
_FIELD_PROPS["email"] = {
    "type": "string",
    "description": "exactly as printed; never changed to match a name",
}
_FIELD_PROPS["business_group"] = {"type": "string", "description": "事業群 / BG"}
_EXACT = "copied exactly, including suffixes such as I, II or 一處"
_FIELD_PROPS["division"] = {"type": "string", "description": f"處 / BU, {_EXACT} (研展處 I)"}
_FIELD_PROPS["department"] = {"type": "string", "description": f"部 / 課 / team, {_EXACT}"}
_FIELD_PROPS["title"] = {
    "type": "string",
    "description": "the job title only; a degree or honorific (博士, Dr., PhD) goes in honorific",
}
_FIELD_PROPS["honorific"] = {"type": "string", "description": "博士, Dr., PhD, ..."}
_FIELD_PROPS["company_tax_id"] = {
    "type": "string",
    "description": "the company's unified business number 統一編號 / 統編 / Tax ID, 8 digits: "
    "always fill it when printed anywhere on the card (often near the company name or "
    "address); never in notes",
}
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
_COMPANY = {
    "type": "string",
    "description": "as the person says it: name, short name (WNC) or mail domain; the "
    "result names the stored company",
}


#: What a failure code means, for the conversation model to tell the person
#: (live test 2026-10-20: the generic Bridge line made it guess "check
#: Settings"). Settings is named only where the scope there is the cause.
FAILURE_TEXT = {
    "message_unknown": "讀信失敗：這封信無法讀取（不存在、已移動或不在讀信範圍內）",
    "folder_unknown": "這個資料夾不在 Agent Web Settings → Agent mode 設定的讀信範圍內，或找不到",
    "outlook_missing": "這台電腦上沒有可用的 Outlook",
    "library_missing": "這台電腦缺少讀 Outlook 用的 pywin32 元件",
    "mail_failed": "Outlook 讀信時出錯，請稍後再試",
    "model_not_configured": "沒有設定可用的內部模型，無法讀簽名檔",
    "model_unavailable": "內部模型這次沒有回應，請稍後再試",
    "person_unknown": "名片夾裡找不到這個人",
    "person_ambiguous": "名片夾裡有不只一個同名的人，請加上公司或用 person_id",
    "person_unspecified": "沒有指明是哪一位",
    "card_without_name": "這張名片沒有讀到姓名或 Email，沒有存",
    "company_has_no_contacts": "名片夾裡沒有這家公司的人",
    "chart_renderer_missing": "這台電腦缺少畫組織圖用的 Pillow 元件",
    "candidates_expired": "這段對話沒有可存的簽名檔候選人（超過一小時已失效，或還沒整理）；"
    "請重新整理簽名檔",
    "proposal_unknown": "這個欄位沒有待確認的新讀值，沒有可改用的值",
    "change_unknown": "找不到這個變更編號",
    "change_already_undone": "這個變更已經復原過了",
    "undo_conflict": "之後又有變更動到同一筆資料，無法直接復原",
    "line_to_self": "不能把一個人設成自己的主管",
    "line_cycle": "這條回報關係會形成循環，沒有記錄",
    "import_unreadable": "舊的 Hermes 名片資料庫讀不出來",
    # Accumulated memory M1: the contact store moved into the Memory Service.
    "memory_migration_failed": "名片資料搬進記憶庫時失敗，什麼都沒有搬；原本的名片資料沒有變動，"
    "旁邊也留有備份",
    "memory_migration_mismatch": "名片資料搬進記憶庫後核對不一致，已取消；原本的名片資料沒有變動",
    "memory_migration_target_not_empty": "記憶庫裡已經有聯絡人資料，舊的名片資料沒有自動搬入",
    "memory_backup_failed": "搬移前無法備份舊的名片資料，所以沒有搬；原本的名片資料沒有變動",
    "memory_legacy_changed": "舊的名片資料在搬進記憶庫之後又被改過（可能用過舊版 AEP），"
    "為了不漏掉那些變更，請先依說明重新搬移",
    "memory_space_not_declared": "這項功能沒有宣告可以使用聯絡人記憶空間",
    "memory_write_not_declared": "這項功能沒有宣告可以寫入聯絡人記憶空間",
    "memory_read_not_declared": "這項功能沒有宣告可以讀取聯絡人記憶空間",
    "memory_space_unknown": "聯絡人記憶空間還沒有註冊",
    "permission_denied": "這項名片功能沒有授權給你（在 Agent Web 的 Capabilities 選取）",
    "invalid_input": "工具參數不正確",
    "timeout": "這次操作逾時",
    "handler_error": "名片功能內部出錯",
}
GENERIC_FAILURE = "Capability invocation did not complete"


def explain(failure: Failure) -> Failure:
    """The failure with a short, accurate sentence naming its code; a
    specific Bridge message (where the input was wrong) is kept after it."""
    text = FAILURE_TEXT.get(failure.code, "名片功能沒有完成")
    detail = "" if failure.message in ("", GENERIC_FAILURE) else f": {failure.message}"
    return failure.model_copy(update={"message": f"{text}（{failure.code}）{detail}"})


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
                "romanised_name_printed": {
                    "type": "string",
                    "description": "where romanised_name is printed, copied as printed "
                    "(e.g. 'Ryan Fan, under the Chinese name'); required with romanised_name, "
                    "else the Host drops it",
                },
                "other_text": {
                    "type": "string",
                    "description": "any other printed text not placed in a field, one line "
                    "each (e.g. a 統一編號 line); scanned by the Host, not stored",
                },
                "image_path": {"type": "string", "description": "the attached photo's path"},
                "card_date": _DATE,
            },
            ("name",),
        ),
    ),
    (
        "cards__store_candidates",
        cards.STORE_CANDIDATES_SPEC,
        "Store people from this conversation's latest cards__harvest_signatures by their "
        'candidate_id (s1, s2, ...), or ["all"] when the person says to store all (都存進去). '
        "The Host keeps each candidate's message id and date; never harvest again to store.",
        _object(
            {
                "candidate_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": 'candidate ids from the harvest, e.g. ["s1", "s3"], or ["all"]',
                }
            },
            ("candidate_ids",),
        ),
    ),
    (
        "cards__add_from_signature",
        cards.ADD_SIGNATURE_SPEC,
        "Store people read from email signatures with their message_id and message_date. "
        "For people from cards__harvest_signatures use cards__store_candidates instead.",
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
        "never overwritten by later scans), or confirm fields that are right as stored "
        "('email 正確' -> confirm ['email']: keeps the stored value and rejects the open "
        "proposal), or take the value read ('用新的' -> accept ['email']), or empty wrong "
        "fields (clear). Each clears needs_confirmation.",
        _object(
            {
                "person": _PERSON,
                "fields": _object(_FIELD_PROPS),
                "confirm": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(FIELDS)},
                    "description": "fields the person says are right as stored",
                },
                "clear": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(FIELDS)},
                    "description": "fields the person says are wrong and should be empty",
                },
                "accept": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(FIELDS)},
                    "description": "fields whose open proposal the person takes ('用新的'): "
                    "the value read becomes theirs",
                },
                "reason": _S,
            },
            ("person",),
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
                "company": _COMPANY,
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
        "cards__proposals",
        cards.PROPOSALS_SPEC,
        "Open proposals: readings that differ from a contact's confirmed value (or another "
        "email), each with the stored value, the value read and its source; one person's or "
        "everyone's. note is a sentence to tell the person.",
        _object({"person": _PERSON, "limit": {"type": "integer"}}),
    ),
    (
        "cards__set_status",
        cards.STATUS_SPEC,
        "Only when the person says so: mark a contact as left (or active again), with the "
        "reason and the date. Who said it is recorded by the Host. Recorded and undoable.",
        _object(
            {
                "person": _PERSON,
                "status": {"type": "string", "enum": ["left", "active"]},
                "reason": _S,
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
        "Draw a company's org chart from the contacts: a PNG the person sees (format png, the "
        "default), an interactive HTML page with a tree view, a grouped view, search and "
        "person cards (format html, when the person asks for an interactive, HTML, searchable "
        "or tree view), or both; and a Markdown legend to include in the answer. People who "
        "left are left out unless include_left (the HTML page can toggle them).",
        _object(
            {
                "company": _COMPANY,
                "include_left": {"type": "boolean"},
                "format": {
                    "type": "string",
                    "enum": ["png", "html", "both"],
                    "description": "png (default), html (interactive page) or both",
                },
            },
            ("company",),
        ),
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


#: Who did something is the request's actor, never a model argument: these
#: keys are dropped from a call before it reaches the Bridge.
IDENTITY_KEYS = frozenset({"said_by", "set_by", "actor", "recorded_by", "confirmed_by"})


def _tool(
    gateway: Any, name: str, spec: CapabilitySpec, description: str, schema: dict[str, Any]
) -> HostTool:
    async def call(context: RequestContext, arguments: dict[str, Any]) -> HostToolOutcome:
        arguments = {key: value for key, value in arguments.items() if key not in IDENTITY_KEYS}
        result = await gateway.bridge.execute(
            CapabilityInvocation(
                context=context, origin="model", target=spec.identity, arguments=arguments
            )
        )
        if result.status == "succeeded":
            # The fields' Chinese names, so a reply says 英文名, never
            # `romanised_name` (live re-test 2026-10-20).
            data = result.data
            if isinstance(data, dict):
                data = {**data, "field_labels": dict(FIELD_LABELS)}
            return HostToolOutcome(status="succeeded", data=data)
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
            failure=explain(result.failure or Failure(code=result.status, message="")),
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


#: How a chart file is shown: the PNG as a picture, the interactive page in a
#: sandboxed frame (Agent Web) or as a document (Telegram), the legend as text.
_KINDS = {"image/png": "image", "text/html": "html"}


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
                "kind": _KINDS.get(str(entry.get("media_type")), "text"),
                "path": path,
            }
            # The legend rides on the chart's first picture or page.
            if shown["kind"] != "text" and isinstance(legend, str):
                shown["legend"] = legend
                legend = None
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
