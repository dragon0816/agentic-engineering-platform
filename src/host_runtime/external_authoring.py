"""What Claude Code, Codex or Copilot may do with this Host's assets.

External authoring X1-X3 (`docs/phases/EXTERNAL_AUTHORING.md`, owner
2026-10-08). One facade serves `aep-host assets` and `aep-host mcp`, so both
entries offer the same operations with the same limits:

- the catalog is schemas and names: the platform's capabilities with their
  descriptions and input schemas (shipped code), and installed Workflow and
  Skill names, owners and parameter names. Never their descriptions, steps,
  instructions or selector hints, which a person wrote about company work,
  and never anything a run produced (PUBLIC rule);
- a submission becomes a candidate of this Host's owner, marked
  `external:<agent>`; the agent name is what the caller said it is;
- a Workflow whose steps only read may run now; its result comes back as
  statuses and codes. Every other run, and every install, waits for the
  owner's button in Agent Web.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from common.assets import AssetIdentity
from host_runtime.chat_authoring import (
    ChatAuthoring,
    ChatAuthoringError,
    digest,
    run_codes,
)
from host_runtime.skill_authoring import installed_skills, skill_digest


def _target(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


AGENT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")

WORKFLOW_FORMAT: dict[str, JsonValue] = {
    "name": "kebab-case name; the host adds namespace, owner and version",
    "description": "one sentence",
    "parameters": [
        {
            "name": "snake_case",
            "label": "the question asked for it",
            "kind": "text",
            "scope": "runtime",
            "required": True,
        }
    ],
    "parameters become the form": (
        "Agent Web draws the run form and Telegram asks the questions from the parameters "
        "alone; never write a GUI. Choose the kind and presentation fields so both work."
    ),
    "parameter kinds": {
        "text": "one line of text; pattern and min_length apply",
        "integer": "a whole number; minimum and maximum apply",
        "number": "any number; minimum and maximum apply",
        "date": "YYYY-MM-DD; a date picker on the Web",
        "boolean": "yes or no; a checkbox on the Web, Yes/No buttons on Telegram",
        "select": "one value (or several with multiple: true) from choices, options or "
        "choices_source; buttons on Telegram",
        "text_list": "several lines of text",
        "emails": "several email addresses",
        "file": "a path to an existing file on the Host (typed)",
        "folder": "a path to an existing folder on the Host (typed)",
        "upload": "files the person uploads (Web file picker, Telegram documents); the "
        "run gets their stored absolute paths, a list when multiple",
    },
    "parameter fields": {
        "scope": "runtime (asked every run) or static (a per-install setting on the "
        "Settings page, never asked at run time)",
        "required": "true: the run cannot start without it",
        "default": "the value used when the person gives none; must fit the kind",
        "help": "one short line shown under the field",
        "examples": "up to 5 sample values, shown as a placeholder",
        "choices": "[{value, label}] for select or text_list; options: [values] is the shorthand",
        "choices_source": "a list read when the form opens: fn:<function>?arg={field} or "
        "ref:<published set>; {field} names an earlier field or a static "
        "setting. fn:folder_files?folder={setting}&accept=.json lists the "
        "file names in a folder",
        "allow_other": "select only, not with multiple: the choices are suggestions and "
        "any typed value is accepted (pick or type)",
        "multiple": "select, file or upload: several values (a list)",
        "accept": 'file, folder or upload: allowed extensions, e.g. [".json"]',
        "pattern": "text: a regular expression the whole value must match",
        "min_length": "text: the shortest allowed value",
        "minimum/maximum": "integer or number bounds",
        "order": "0-99999; the question order (depended-on fields first)",
        "group": "identity: who or what the run is for; asked first and offered as "
        '"same as last time"',
        "needs": "names of earlier fields this one depends on",
        "channels": "where it is shown: web, telegram, schedule, agent (default all)",
        "confirm": "true: a privileged choice (e.g. send mail); confirmed before the run and "
        "never filled by a model",
    },
    "parameter examples": [
        {
            "name": "customer",
            "label": "Which customer?",
            "kind": "select",
            "choices": [{"value": "northwind", "label": "Northwind Ltd"}, {"value": "globex"}],
            "allow_other": True,
            "group": "identity",
            "required": True,
        },
        {
            "name": "month_start",
            "label": "First day of the month",
            "kind": "date",
            "required": True,
        },
        {
            "name": "inputs",
            "label": "Input workbooks",
            "kind": "upload",
            "multiple": True,
            "accept": [".xlsx", ".csv"],
        },
    ],
    "steps": [
        {
            "capability": "namespace/name@1.2.3 from the catalog",
            "inputs": {"<input field>": "an input source"},
        }
    ],
    "checks": [
        {"check_id": "snake_case", "step_index": 0, "kind": "files_nonempty", "pattern": "*.xlsx"}
    ],
    "checks note": "what a successful run must produce; the Host checks it after the "
    "steps. A check has exactly check_id, step_index, kind "
    "(files_nonempty, file_exists or data_nonempty) and an optional pattern "
    "(a file-name glob for the file kinds); any other key is refused.",
    "input sources": [
        {"source": "fixed", "value": "any JSON the Workflow fixes"},
        {"source": "run", "path": ["<parameter>"], "note": "[] is all run values"},
        {"source": "step", "step_index": 0, "path": ["<output field>"]},
    ],
    "complete example": {
        "name": "monthly-expense-summary",
        "description": "Summarize the month's uploaded expense CSV files into one workbook.",
        "parameters": [
            {
                "name": "month_start",
                "label": "First day of the month",
                "kind": "date",
                "required": True,
            },
            {
                "name": "inputs",
                "label": "Expense CSV files",
                "kind": "upload",
                "multiple": True,
                "accept": [".csv"],
                "required": True,
            },
        ],
        "steps": [
            {
                "capability": "coding/run-python@1.0.0",
                "inputs": {
                    "request": {
                        "source": "fixed",
                        "value": {
                            "workspace": "<a folder under coding_workspace_roots>",
                            "script": "import json, os ... write output/expenses-<month>.xlsx",
                        },
                    },
                    "arguments": {"source": "run", "path": []},
                },
            }
        ],
        "checks": [
            {"check_id": "workbook", "step_index": 0, "kind": "files_nonempty", "pattern": "*.xlsx"}
        ],
    },
    "rules": [
        "Each step's inputs must fit that capability's input_schema (aep_capability).",
        "Never put a password, token or key in a fixed value.",
        "coding/run-python@1.0.0 runs a complete Python script in an absolute workspace "
        "folder; it reads run values from os.environ['AEP_WORKFLOW_PARAMS'] (a JSON file) "
        "and writes only under the workspace's output folder.",
        "Put run values in output file names so a rerun never overwrites an earlier result.",
    ],
}

SKILL_FORMAT: dict[str, JsonValue] = {
    "name": "kebab-case name; the host adds namespace, owner and version",
    "alias": "identifier people type, e.g. expense_report (letters, digits, _)",
    "instructions": "the guidance the resident Agent follows when this Skill is selected",
    "selector_hint": "optional, at most 240 characters: English and Chinese keywords that "
    "say what this Skill is for and how it differs from others",
    "commands": [
        {
            "name": "identifier",
            "kind": "capability|workflow",
            "target": "namespace/name@1.2.3, installed (see the catalog)",
        }
    ],
    "default_command": "optional, one of the command names",
    "harness_guidance": "optional {domains: [workflow|knowledge|coding], required_evidence, "
    "context_required, fallback: needs_input|stop|retry, max_retries}",
    "procedure": "optional, Knowledge Skills only; must validate as a KnowledgeProcedure",
    "not allowed": ["rules", "script_tools"],
}


CATALOG_GUIDE = (
    "Compact catalog. Read the full Workflow format with aep_workflow_format and the Skill "
    "format with aep_skill_format; read one capability's input schema with aep_capability "
    "before using it in a step. Use only the targets listed here, at the exact version."
)
CATALOG_BUDGET_CHARS = 15_000
PURPOSE_CHARS = 140


def _purpose(description: str) -> str:
    """The first sentence of a description, at most PURPOSE_CHARS long."""
    text = " ".join(description.split())
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return sentence if len(sentence) <= PURPOSE_CHARS else sentence[: PURPOSE_CHARS - 1] + "…"


def _size(value: JsonValue) -> int:
    return len(json.dumps(value, ensure_ascii=False, indent=1))


def _within_budget(catalog: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Drop detail, then entries, until the catalog fits CATALOG_BUDGET_CHARS;
    say what was left out so the agent can ask for it."""
    if _size(catalog) <= CATALOG_BUDGET_CHARS:
        return catalog
    for key in ("capabilities", "workflows", "skills"):
        entries = catalog[key]
        assert isinstance(entries, list)
        for entry in entries:
            if isinstance(entry, dict):
                entry.pop("inputs", None)
                parameters = entry.get("parameters")
                if isinstance(parameters, list):
                    entry["parameters"] = [p["name"] for p in parameters if isinstance(p, dict)]
    omitted: dict[str, JsonValue] = {}
    for key in ("skills", "workflows", "capabilities"):
        entries = catalog[key]
        assert isinstance(entries, list)
        dropped = 0
        # Room for the "omitted" note itself.
        while entries and _size(catalog) > CATALOG_BUDGET_CHARS - 200:
            entries.pop()
            dropped += 1
        if dropped:
            omitted[key] = dropped
    if omitted:
        catalog["omitted"] = omitted
    return catalog


class ExternalAuthoring:
    def __init__(
        self, chat: ChatAuthoring, actor: str, agent: str, *, session_id: str | None = None
    ) -> None:
        if not AGENT_NAME.match(agent):
            raise ChatAuthoringError("agent_name_invalid")
        self.chat = chat
        self.actor = actor
        self.source = f"external:{agent}"
        # The Agent Web conversation this agent answers in (agent mode), so
        # its drafts and install requests show there as an install card
        # (owner 2026-10-16). Run requests stay without it: a run's data is
        # never added to a conversation an external agent reads.
        self.session_id = session_id

    # -- reading -----------------------------------------------------------

    def catalog(self) -> dict[str, JsonValue]:
        """A compact catalog that fits an agent's tool-output limit (live
        2026-10-15: the full one was ~82K characters, over Claude Code's MCP
        limit). Input schemas come one at a time from `capability`, the full
        formats from `workflow_format` and `skill_format`."""
        capabilities: list[JsonValue] = []
        for spec in self.chat.installed.discover():
            binding = self.chat.installed.get(spec.identity)
            fields: list[JsonValue] = []
            if binding is not None:
                try:
                    properties = binding.input_model.model_json_schema().get("properties")
                except Exception:  # noqa: BLE001 - a schema that cannot render is omitted
                    properties = None
                if isinstance(properties, dict):
                    fields = list(properties)
            capabilities.append(
                {
                    "target": _target(spec.identity),
                    "purpose": _purpose(spec.description),
                    "side_effect": spec.side_effect,
                    "inputs": fields,
                }
            )
        workflows: list[JsonValue] = [
            {
                "target": _target(m.metadata.identity),
                "owner": m.metadata.owner.id,
                "parameters": [
                    {"name": p.name, "kind": p.kind, "required": p.required} for p in m.parameters
                ],
            }
            for m in self.chat.installed_workflows()
        ]
        skills: list[JsonValue] = []
        if self.chat.skills_dir is not None:
            skills = [
                {
                    "target": _target(m.metadata.identity),
                    "alias": m.alias,
                    "owner": m.metadata.owner.id,
                    "commands": [c.name for c in m.commands],
                }
                for m in installed_skills(self.chat.skills_dir)
            ]
        catalog: dict[str, JsonValue] = {
            "actor": self.actor,
            "namespace": self.chat.namespace,
            "how_to": CATALOG_GUIDE,
            # Where a coding/run-python step's workspace may be.
            "coding_workspace_roots": list(self.chat.coding_workspace_roots),
            "capabilities": capabilities,
            "workflows": workflows,
            "skills": skills,
        }
        return _within_budget(catalog)

    def capability(self, target: str) -> dict[str, JsonValue]:
        """One capability in full: its description and input schema. `target`
        is namespace/name@version or just the name."""
        wanted = target.strip()
        for spec in self.chat.installed.discover():
            if wanted not in (
                _target(spec.identity),
                spec.name,
                spec.identity.name,
                f"{spec.identity.namespace}/{spec.name}",
            ):
                continue
            binding = self.chat.installed.get(spec.identity)
            schema: JsonValue = None
            if binding is not None:
                try:
                    schema = binding.input_model.model_json_schema()
                except Exception:  # noqa: BLE001 - a schema that cannot render is omitted
                    schema = None
            return {
                "ok": True,
                "target": _target(spec.identity),
                "description": spec.description,
                "side_effect": spec.side_effect,
                "input_schema": schema,
            }
        return {
            "ok": False,
            "code": "capability_unknown",
            "next": "pick a target from aep_catalog's capabilities",
        }

    @staticmethod
    def workflow_format() -> dict[str, JsonValue]:
        return {"ok": True, "workflow_format": WORKFLOW_FORMAT}

    @staticmethod
    def skill_format() -> dict[str, JsonValue]:
        return {"ok": True, "skill_format": SKILL_FORMAT}

    def list(self) -> dict[str, JsonValue]:
        approvals = self.chat.approvals(self.actor, pending_only=False)
        latest: dict[str, JsonValue] = {}
        for item in approvals:
            latest[item.candidate_id] = self.chat.external_view(item)
        return {
            "workflows": [
                {
                    "candidate_id": c.candidate_id,
                    "workflow": _target(c.draft.metadata.identity),
                    "status": c.status,
                    "source": c.source,
                    "digest": digest(c.draft),
                    "last_approval": latest.get(c.candidate_id),
                }
                for c in self.chat.candidates(self.actor)[:50]
            ],
            "skills": [
                {
                    "candidate_id": c.candidate_id,
                    "skill": _target(c.draft.metadata.identity),
                    "status": c.status,
                    "source": c.source,
                    "digest": skill_digest(c.draft),
                    "last_approval": latest.get(c.candidate_id),
                }
                for c in (
                    self.chat.skill_candidates(self.actor)
                    if self.chat.skills_dir is not None
                    else []
                )[:50]
            ],
        }

    def get(self, candidate_id: str) -> dict[str, JsonValue]:
        """A candidate in full: the caller, or another agent, wrote it."""
        if candidate_id.startswith("sk-"):
            skill = self.chat.skill_candidate(candidate_id, self.actor)
            return {
                "candidate_id": candidate_id,
                "status": skill.status,
                "skill": skill.draft.model_dump(mode="json"),
            }
        item = self.chat.candidate(candidate_id, self.actor)
        return {
            "candidate_id": candidate_id,
            "status": item.status,
            "workflow": item.draft.model_dump(mode="json"),
        }

    def status(self, approval_id: str) -> dict[str, JsonValue]:
        return self.chat.external_view(self.chat.approval(approval_id, self.actor))

    # -- Workflows ---------------------------------------------------------

    def check_workflow(self, raw: dict[str, Any]) -> dict[str, JsonValue]:
        manifest, problems = self.chat.check(self.actor, raw)
        if manifest is None:
            return {"ok": False, "problems": list(problems)}
        return {
            "ok": True,
            "workflow": _target(manifest.metadata.identity),
            "read_only": self.chat.read_only(manifest),
        }

    def submit_workflow(
        self, raw: dict[str, Any], title: str, candidate_id: str | None = None
    ) -> dict[str, JsonValue]:
        item, problems = self.chat.draft(
            self.actor, self.session_id, title, raw, candidate_id, source=self.source
        )
        if item is None:
            return {"ok": False, "problems": list(problems)}
        return {
            "ok": True,
            "candidate_id": item.candidate_id,
            "workflow": _target(item.draft.metadata.identity),
            "revision": item.revision,
            "digest": digest(item.draft),
            "read_only": self.chat.read_only(item.draft),
            "next": "run it with test values (aep_run_workflow), then ask to install it",
        }

    def run_workflow(
        self, candidate_id: str, arguments: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        item = self.chat.candidate(candidate_id, self.actor)
        installed = item.status == "installed" and item.installed_digest == digest(item.draft)
        if installed or self.chat.read_only(item.draft):
            # Read-only, or the installed version unchanged: installing was the
            # owner's approval, as in conversations (harness unification U6).
            result = self.chat.execute(
                self.actor,
                item,
                arguments,
                f"external-{'installed' if installed else 'read-only'}:{candidate_id}",
            )
            return {
                "ok": True,
                "ran": True,
                "run": run_codes(result),
                "note": "statuses and codes only; the owner sees the data in Agent Web",
            }
        request = self.chat.request(
            self.actor, None, "run", candidate_id, arguments, source=self.source
        )
        return {
            "ok": True,
            "ran": False,
            "approval_id": request.approval_id,
            "next": "nothing ran; it waits for the owner's approval in Agent Web. "
            "Check it with aep_status.",
        }

    def install_workflow(self, candidate_id: str) -> dict[str, JsonValue]:
        request = self.chat.request(
            self.actor, self.session_id, "install", candidate_id, source=self.source
        )
        return {
            "ok": True,
            "approval_id": request.approval_id,
            "next": "nothing is installed yet; it waits for the owner's approval in "
            "Agent Web. Check it with aep_status.",
        }

    # -- Skills ------------------------------------------------------------

    def check_skill(self, raw: dict[str, Any]) -> dict[str, JsonValue]:
        manifest, problems = self.chat.check_skill(self.actor, raw)
        if manifest is None:
            return {"ok": False, "problems": list(problems)}
        return {"ok": True, "skill": _target(manifest.metadata.identity), "alias": manifest.alias}

    def submit_skill(
        self, raw: dict[str, Any], title: str, candidate_id: str | None = None
    ) -> dict[str, JsonValue]:
        item, problems = self.chat.draft_skill(
            self.actor, title, raw, candidate_id, source=self.source, session_id=self.session_id
        )
        if item is None:
            return {"ok": False, "problems": list(problems)}
        return {
            "ok": True,
            "candidate_id": item.candidate_id,
            "skill": _target(item.draft.metadata.identity),
            "alias": item.draft.alias,
            "revision": item.revision,
            "digest": skill_digest(item.draft),
            "next": "ask to install it (aep_install_skill); the owner approves it",
        }

    def install_skill(self, candidate_id: str) -> dict[str, JsonValue]:
        request = self.chat.request(
            self.actor, self.session_id, "install_skill", candidate_id, source=self.source
        )
        return {
            "ok": True,
            "approval_id": request.approval_id,
            "next": "nothing is installed yet; it waits for the owner's approval in "
            "Agent Web, and the host uses it after a restart.",
        }


def guarded(call: Callable[[], dict[str, JsonValue]]) -> dict[str, JsonValue]:
    """A refusal as a code, never a traceback or a value."""
    try:
        return call()
    except ChatAuthoringError as error:
        return {"ok": False, "code": error.code}


def build(config_path: Path, agent: str) -> ExternalAuthoring:
    """This Host's authoring, as `build_runtime` assembles it, without the
    resident Agent, state or channels."""
    from host_runtime.contracts import CompanyHostConfiguration, HostLayout
    from host_runtime.host import build_gateway, load_authorization, load_membership

    config = CompanyHostConfiguration.model_validate_json(
        config_path.read_text(encoding="utf-8-sig")
    )
    layout = HostLayout.under(config.workspace_root)
    membership = load_membership(config, layout)
    gateway = build_gateway(
        config, layout, load_authorization(config, layout), membership=membership
    )
    chat = ChatAuthoring(
        layout.workspace_root / "authoring" / "chat",
        bridge=lambda: gateway.bridge,
        namespace=config.namespace or "engineering",
        workflows_dir=layout.workflows,
        grants_file=layout.grants,
        skills_dir=layout.skills,
        coding_workspace_roots=(
            () if config.coding is None else tuple(config.coding.workspace_roots)
        ),
    )
    return ExternalAuthoring(chat, config.device.registered_by, agent)


# -- connecting an agent (X4) -------------------------------------------------

CREATORS = ("aep-workflow-creator", "aep-skill-creator", "aep-knowledge")
AGENTS: dict[str, str] = {
    "claude-code": ".claude/skills",
    "codex": ".agents/skills",
    "copilot": ".github/skills",
}


def creator_text(name: str) -> str:
    from importlib.resources import files

    return (files("host_runtime") / "creators" / name / "SKILL.md").read_text(encoding="utf-8")


def server_command(python: str, config_path: Path, agent: str) -> tuple[str, list[str]]:
    return python, [
        "-m",
        "host_runtime.cli",
        "mcp",
        "--config",
        str(config_path.resolve()),
        "--agent",
        agent,
    ]


def assistant_command(python: str, config_path: Path) -> tuple[str, list[str]]:
    """The Knowledge and Workflow tools, through the running Agent Web."""
    return python, [
        "-m",
        "host_runtime.cli",
        "assistant-mcp",
        "--config",
        str(config_path.resolve()),
    ]


def connect(agent: str, project: Path, config_path: Path, python: str) -> list[str]:
    """Write the creator Skills where `agent` reads project skills, and say how
    to register the `aep` MCP server. Claude Code's `.mcp.json` lives in the
    project and is written here; Codex and Copilot keep MCP servers in the
    person's own configuration, which this prints and never edits."""
    if agent not in AGENTS:
        raise ChatAuthoringError("agent_unknown")
    lines: list[str] = []
    for name in CREATORS:
        target = project / AGENTS[agent] / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(creator_text(name), encoding="utf-8")
        lines.append(f"wrote {target}")
    command, arguments = server_command(python, config_path, agent)
    helper, helper_args = assistant_command(python, config_path)
    if agent == "claude-code":
        settings = project / ".mcp.json"
        current: dict[str, Any] = {}
        if settings.is_file():
            loaded = json.loads(settings.read_text(encoding="utf-8-sig"))
            current = loaded if isinstance(loaded, dict) else {}
        servers = current.setdefault("mcpServers", {})
        servers["aep"] = {"type": "stdio", "command": command, "args": arguments}
        servers["aep-assistant"] = {"type": "stdio", "command": helper, "args": helper_args}
        settings.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        lines.append(
            f"wrote {settings} (servers 'aep' and 'aep-assistant'); Claude Code asks "
            "you to trust them once"
        )
    elif agent == "codex":
        lines += [
            "Add this to ~/.codex/config.toml (or run connect --user):",
            "",
            "[mcp_servers.aep]",
            f"command = {json.dumps(command)}",
            f"args = {json.dumps(arguments)}",
            "",
            '[mcp_servers."aep-assistant"]',
            f"command = {json.dumps(helper)}",
            f"args = {json.dumps(helper_args)}",
            "",
        ]
    else:
        block = {
            "mcpServers": {
                "aep": {"type": "local", "command": command, "args": arguments, "tools": ["*"]},
                "aep-assistant": {
                    "type": "local",
                    "command": helper,
                    "args": helper_args,
                    "tools": ["*"],
                },
            }
        }
        lines += [
            "Add this server to ~/.copilot/mcp-config.json:",
            "",
            json.dumps(block, indent=2),
            "",
        ]
    return lines
