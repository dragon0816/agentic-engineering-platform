"""One turn of an SOP to Workflow discussion (docs/phases/SOP_TO_WORKFLOW.md W6).

The model reads the SOP, the discussion so far and the current draft, and
answers with what to tell the owner, the questions still open, and the whole
Workflow when it can write one. The same checks as `draft_workflow` decide
whether a draft would run here; a draft that fails them goes back to the
model with the problems, a bounded number of times. The model proposes; it
never installs, approves or runs anything.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import Field, ValidationError

from capabilities.runtime import InstalledCapabilities
from capabilities.workflow_author import review
from capabilities.workflow_author.draft import INSTRUCTIONS
from common.assets import WorkflowManifest
from common.base import Contract, Text
from common.execution import TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

OUTPUT_CONTRACT = "workflow-author.conversation.v1"
MAX_SOP_CHARS = 30_000
MAX_TURNS_SHOWN = 20

GUIDE = """
You are discussing one SOP with its owner, turn by turn, to produce one
Workflow. Answer with a single JSON object:
{"reply": what you tell the owner (short, in their language),
 "questions": [what you still need to know],
 "workflow": null while you cannot write it, otherwise exactly
   {"name": "<kebab-case>", "description": "<one or two sentences>",
    "parameters": [<declared fields>],
    "steps": [{"capability": "<namespace>/<name>@<version>",
               "inputs": {"<input name>": <source>}}]}}
The host fills in everything else (owner, visibility, lifecycle, execution,
dependencies, contracts); do not write those.
A parameter is {"name": "<snake_case>", "label": "<question>", "kind":
"text"|"select"|"integer"|"boolean"|"file"|"folder"|"date", "scope":
"runtime"|"static", "required": true|false}.

How values enter a step (every rule is checked):
- Something the SOP fixes (a URL path, a field label, a button text, a sheet
  name, a column list, a recorded web procedure) is a fixed input:
  {"source": "fixed", "value": <JSON>}. Never put a password, token or key in it.
- Something that changes per run (a customer code) is a run parameter: declare
  it in `parameters` (scope "runtime", a kind such as "text" or "select",
  a short `label` phrased as a question) and read it with
  {"source": "run", "path": ["<name>"]}.
- Something that differs per computer (a workbook path, a site address) is a
  setting: declare it in `parameters` with scope "static" (kind "file",
  "folder" or "text") and read it the same way.
- An earlier step's output: {"source": "step", "step_index": N, "path": [...]}.

Web steps replay a recorded procedure with no model at run time:
- web/read@1.0.0 takes {"actions": [...], "values": {...}}; it may open, fill,
  click links or GET search buttons, read_table and read_text. web/act@1.0.0
  takes the same plus "for_each": [items], and is the only way to press a
  button that changes the site; it runs its actions once per item with
  {item} bound.
- Actions: {"do": "open", "url": "{site}/path"}, {"do": "fill", "target":
  {"label": "<field label as the SOP names it>", "kind": "field"}, "value":
  "{customer}"}, {"do": "click", "target": {"label": "<button text>", "kind":
  "button"}}, {"do": "click", "target": {...}, "row": {"table": "<css>",
  "column": "<header>", "equals": "{item}"}}, {"do": "read_table", "table":
  "<css such as #orders or table>", "save_as": "<name>"}.
- {placeholders} are filled from "values"; give "values" the whole run:
  {"source": "run", "path": []}. read_table output is at ["data", "<name>"].
- Use the labels the SOP writes; the preview run will show whether the page
  has them. If the SOP does not say a site address, ask for it.
data/select@1.0.0 keeps table rows whose cells equal `where` and returns the
`take` column as ["values"]. excel/upsert-rows@1.0.0 updates rows by a key
column and appends new keys, never deleting anything.

Ask a question instead of guessing when the SOP leaves out something a run
needs. When the owner answers, return the whole updated Workflow.
"""


class AuthoringTurn(Contract):
    role: Literal["owner", "agent"]
    text: Text


class AuthoringAnswer(Contract):
    reply: Text
    questions: tuple[Text, ...] = ()
    workflow: WorkflowManifest | None = None
    problems: tuple[Text, ...] = ()
    attempts: int = Field(default=1, ge=1)


def _messages(
    sop: str, turns: tuple[AuthoringTurn, ...], current: WorkflowManifest | None,
    installed: InstalledCapabilities, namespace: str, problems: tuple[str, ...],
) -> tuple[ModelMessage, ...]:
    asked = [
        f"Namespace: {namespace}",
        "Capabilities installed on this machine:",
        json.dumps(review.catalogue(installed), ensure_ascii=False, default=str),
        "",
        "The SOP:",
        sop[:MAX_SOP_CHARS],
    ]
    if current is not None:
        asked += ["", "The current draft:", current.model_dump_json()]
    if turns:
        asked += ["", "The discussion so far:"]
        asked += [f"{turn.role}: {turn.text}" for turn in turns[-MAX_TURNS_SHOWN:]]
    if problems:
        asked += ["", "Your last Workflow would not run here. Fix exactly these and return "
                  "the whole JSON answer again:", *(f"- {problem}" for problem in problems)]
    return (
        ModelMessage(role="system", text=INSTRUCTIONS + "\n" + GUIDE),
        ModelMessage(role="user", text="\n".join(asked)),
    )


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return text or "sop-workflow"


def _capability(value: object) -> dict[str, str] | None:
    if isinstance(value, dict):
        return {key: str(value.get(key, "")) for key in ("namespace", "name", "version")}
    match = re.fullmatch(r"([a-z0-9-]+)/([a-z0-9-]+)@([0-9][0-9A-Za-z.+-]*)", str(value or ""))
    if match is None:
        return None
    return {"namespace": match.group(1), "name": match.group(2), "version": match.group(3)}


def assemble(
    raw: dict[str, Any], *, namespace: str, owner: str, installed: InstalledCapabilities
) -> dict[str, Any]:
    """The model's semantic part plus what the host decides. Whatever the
    model wrote about owner, visibility, lifecycle or execution is replaced:
    a draft is private to its author, local and unpublished."""
    identity = (raw.get("metadata") or {}).get("identity") or {}
    name = _slug(raw.get("name") or identity.get("name"))
    steps = []
    used: list[str] = []
    for step in raw.get("steps") or []:
        if not isinstance(step, dict):
            continue
        target = _capability(step.get("capability"))
        assembled: dict[str, Any] = {"capability": target, "inputs": step.get("inputs") or {}}
        if "retry" in step:
            assembled["retry"] = step["retry"]
        steps.append(assembled)
        if target is not None:
            for spec in installed.discover():
                if spec.identity.model_dump() == target and spec.name not in used:
                    used.append(spec.name)
    return {
        "metadata": {
            "identity": {"namespace": namespace, "name": name,
                         "version": str(raw.get("version") or identity.get("version")
                                        or "1.0.0")},
            "owner": {"type": "user", "id": owner},
            "visibility": "private",
            "lifecycle": "draft",
        },
        "kind": "workflow",
        "description": str(raw.get("description") or name),
        "execution": {"mode": "local"},
        "dependencies": {"central_required": False, "local_capabilities": used},
        "parameters": raw.get("parameters") or [],
        "input_contract": f"{namespace}.{name}.input.v1",
        "output_contract": f"{namespace}.{name}.output.v1",
        "steps": steps,
    }


def _salvage(text: str) -> Any:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


def author_turn(
    sop: str,
    turns: tuple[AuthoringTurn, ...],
    current: WorkflowManifest | None,
    installed: InstalledCapabilities,
    *,
    model: ModelClient,
    model_alias: str,
    trace: TraceIdentifiers,
    namespace: str,
    owner: str = "owner",
    local_only: bool = False,
    max_attempts: int = 3,
) -> AuthoringAnswer:
    problems: tuple[str, ...] = ()
    for attempt in range(1, max_attempts + 1):
        response = model.generate(ModelRequest(
            trace=trace, model_alias=model_alias,
            messages=_messages(sop, turns, current, installed, namespace, problems),
            requirements=ModelRequirements(structured_output=True, local_only=local_only),
            output_contract=OUTPUT_CONTRACT, max_output_tokens=8_000,
        ))
        if response.failure is not None:
            return AuthoringAnswer(reply="The model could not answer this turn.",
                                   problems=(response.failure.code,), attempts=attempt)
        answer = response.structured_output
        if not isinstance(answer, dict):
            answer = _salvage(response.text)
        if not isinstance(answer, dict) or not isinstance(answer.get("reply"), str):
            problems = ("the answer was not the JSON object asked for",)
            continue
        asked = answer.get("questions")
        questions = tuple(
            str(item) for item in (asked if isinstance(asked, list) else []) if str(item).strip()
        )
        raw = answer.get("workflow")
        if raw is None:
            return AuthoringAnswer(reply=answer["reply"], questions=questions, attempts=attempt)
        if not isinstance(raw, dict):
            problems = ("`workflow` must be an object or null",)
            continue
        try:
            workflow = WorkflowManifest.model_validate(
                assemble(raw, namespace=namespace, owner=owner, installed=installed))
        except (ValidationError, ValueError) as invalid:
            problems = review.contract_problems(invalid) if isinstance(
                invalid, ValidationError) else (str(invalid),)
            continue
        problems = review.unusable(workflow, installed, namespace=namespace)
        if not problems:
            return AuthoringAnswer(reply=answer["reply"], questions=questions,
                                   workflow=workflow, attempts=attempt)
    return AuthoringAnswer(
        reply="I could not write a Workflow that runs here yet; the problems are listed.",
        problems=problems, attempts=max_attempts,
    )
