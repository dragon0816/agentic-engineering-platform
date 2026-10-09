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
    "parameters": [{"name": "snake_case", "label": "the question asked for it",
                    "kind": "text|date|integer|boolean|folder|file",
                    "scope": "runtime", "required": True}],
    "steps": [{"capability": "namespace/name@1.2.3 from the catalog",
               "inputs": {"<input field>": "an input source"}}],
    "checks": [{"check_id": "snake_case", "step_index": 0,
                "kind": "files_nonempty|file_exists|data_nonempty", "pattern": "*.xlsx",
                "note": "what a successful run must produce; the Host checks it"}],
    "input sources": [
        {"source": "fixed", "value": "any JSON the Workflow fixes"},
        {"source": "run", "path": ["<parameter>"], "note": "[] is all run values"},
        {"source": "step", "step_index": 0, "path": ["<output field>"]},
    ],
    "rules": [
        "Each step's inputs must fit that capability's input_schema in the catalog.",
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
    "commands": [{"name": "identifier", "kind": "capability|workflow",
                  "target": "namespace/name@1.2.3, installed (see the catalog)"}],
    "default_command": "optional, one of the command names",
    "harness_guidance": "optional {domains: [workflow|knowledge|coding], required_evidence, "
                        "context_required, fallback: needs_input|stop|retry, max_retries}",
    "procedure": "optional, Knowledge Skills only; must validate as a KnowledgeProcedure",
    "not allowed": ["rules", "script_tools"],
}


class ExternalAuthoring:
    def __init__(self, chat: ChatAuthoring, actor: str, agent: str) -> None:
        if not AGENT_NAME.match(agent):
            raise ChatAuthoringError("agent_name_invalid")
        self.chat = chat
        self.actor = actor
        self.source = f"external:{agent}"

    # -- reading -----------------------------------------------------------

    def catalog(self) -> dict[str, JsonValue]:
        capabilities: list[JsonValue] = []
        for spec in self.chat.installed.discover():
            binding = self.chat.installed.get(spec.identity)
            schema: JsonValue = None
            if binding is not None:
                try:
                    schema = binding.input_model.model_json_schema()
                except Exception:  # noqa: BLE001 - a schema that cannot render is omitted
                    schema = None
            capabilities.append({
                "target": _target(spec.identity), "name": spec.name,
                "description": spec.description, "side_effect": spec.side_effect,
                "input_schema": schema})
        workflows: list[JsonValue] = [
            {"target": _target(m.metadata.identity), "owner": m.metadata.owner.id,
             "parameters": [{"name": p.name, "kind": p.kind, "required": p.required}
                            for p in m.parameters]}
            for m in self.chat.installed_workflows()
        ]
        skills: list[JsonValue] = []
        if self.chat.skills_dir is not None:
            skills = [
                {"target": _target(m.metadata.identity), "alias": m.alias,
                 "owner": m.metadata.owner.id, "commands": [c.name for c in m.commands]}
                for m in installed_skills(self.chat.skills_dir)
            ]
        return {"actor": self.actor, "namespace": self.chat.namespace,
                "workflow_format": WORKFLOW_FORMAT, "skill_format": SKILL_FORMAT,
                # Where a coding/run-python step's workspace may be.
                "coding_workspace_roots": list(self.chat.coding_workspace_roots),
                "capabilities": capabilities, "workflows": workflows, "skills": skills}

    def list(self) -> dict[str, JsonValue]:
        approvals = self.chat.approvals(self.actor, pending_only=False)
        latest: dict[str, JsonValue] = {}
        for item in approvals:
            latest[item.candidate_id] = self.chat.external_view(item)
        return {
            "workflows": [
                {"candidate_id": c.candidate_id, "workflow": _target(c.draft.metadata.identity),
                 "status": c.status, "source": c.source, "digest": digest(c.draft),
                 "last_approval": latest.get(c.candidate_id)}
                for c in self.chat.candidates(self.actor)[:50]],
            "skills": [
                {"candidate_id": c.candidate_id, "skill": _target(c.draft.metadata.identity),
                 "status": c.status, "source": c.source, "digest": skill_digest(c.draft),
                 "last_approval": latest.get(c.candidate_id)}
                for c in (self.chat.skill_candidates(self.actor)
                          if self.chat.skills_dir is not None else [])[:50]],
        }

    def get(self, candidate_id: str) -> dict[str, JsonValue]:
        """A candidate in full: the caller, or another agent, wrote it."""
        if candidate_id.startswith("sk-"):
            skill = self.chat.skill_candidate(candidate_id, self.actor)
            return {"candidate_id": candidate_id, "status": skill.status,
                    "skill": skill.draft.model_dump(mode="json")}
        item = self.chat.candidate(candidate_id, self.actor)
        return {"candidate_id": candidate_id, "status": item.status,
                "workflow": item.draft.model_dump(mode="json")}

    def status(self, approval_id: str) -> dict[str, JsonValue]:
        return self.chat.external_view(self.chat.approval(approval_id, self.actor))

    # -- Workflows ---------------------------------------------------------

    def check_workflow(self, raw: dict[str, Any]) -> dict[str, JsonValue]:
        manifest, problems = self.chat.check(self.actor, raw)
        if manifest is None:
            return {"ok": False, "problems": list(problems)}
        return {"ok": True, "workflow": _target(manifest.metadata.identity),
                "read_only": self.chat.read_only(manifest)}

    def submit_workflow(
        self, raw: dict[str, Any], title: str, candidate_id: str | None = None
    ) -> dict[str, JsonValue]:
        item, problems = self.chat.draft(self.actor, None, title, raw, candidate_id,
                                         source=self.source)
        if item is None:
            return {"ok": False, "problems": list(problems)}
        return {"ok": True, "candidate_id": item.candidate_id,
                "workflow": _target(item.draft.metadata.identity), "revision": item.revision,
                "digest": digest(item.draft), "read_only": self.chat.read_only(item.draft),
                "next": "run it with test values (aep_run_workflow), then ask to install it"}

    def run_workflow(
        self, candidate_id: str, arguments: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        item = self.chat.candidate(candidate_id, self.actor)
        installed = item.status == "installed" and item.installed_digest == digest(item.draft)
        if installed or self.chat.read_only(item.draft):
            # Read-only, or the installed version unchanged: installing was the
            # owner's approval, as in conversations (harness unification U6).
            result = self.chat.execute(
                self.actor, item, arguments,
                f"external-{'installed' if installed else 'read-only'}:{candidate_id}")
            return {"ok": True, "ran": True, "run": run_codes(result),
                    "note": "statuses and codes only; the owner sees the data in Agent Web"}
        request = self.chat.request(self.actor, None, "run", candidate_id, arguments,
                                    source=self.source)
        return {"ok": True, "ran": False, "approval_id": request.approval_id,
                "next": "nothing ran; it waits for the owner's approval in Agent Web. "
                        "Check it with aep_status."}

    def install_workflow(self, candidate_id: str) -> dict[str, JsonValue]:
        request = self.chat.request(self.actor, None, "install", candidate_id,
                                    source=self.source)
        return {"ok": True, "approval_id": request.approval_id,
                "next": "nothing is installed yet; it waits for the owner's approval in "
                        "Agent Web. Check it with aep_status."}

    # -- Skills ------------------------------------------------------------

    def check_skill(self, raw: dict[str, Any]) -> dict[str, JsonValue]:
        manifest, problems = self.chat.check_skill(self.actor, raw)
        if manifest is None:
            return {"ok": False, "problems": list(problems)}
        return {"ok": True, "skill": _target(manifest.metadata.identity), "alias": manifest.alias}

    def submit_skill(
        self, raw: dict[str, Any], title: str, candidate_id: str | None = None
    ) -> dict[str, JsonValue]:
        item, problems = self.chat.draft_skill(self.actor, title, raw, candidate_id,
                                               source=self.source)
        if item is None:
            return {"ok": False, "problems": list(problems)}
        return {"ok": True, "candidate_id": item.candidate_id,
                "skill": _target(item.draft.metadata.identity), "alias": item.draft.alias,
                "revision": item.revision, "digest": skill_digest(item.draft),
                "next": "ask to install it (aep_install_skill); the owner approves it"}

    def install_skill(self, candidate_id: str) -> dict[str, JsonValue]:
        request = self.chat.request(self.actor, None, "install_skill", candidate_id,
                                    source=self.source)
        return {"ok": True, "approval_id": request.approval_id,
                "next": "nothing is installed yet; it waits for the owner's approval in "
                        "Agent Web, and the host uses it after a restart."}


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
        config_path.read_text(encoding="utf-8-sig"))
    layout = HostLayout.under(config.workspace_root)
    membership = load_membership(config, layout)
    gateway = build_gateway(config, layout, load_authorization(config, layout),
                            membership=membership)
    chat = ChatAuthoring(
        layout.workspace_root / "authoring" / "chat",
        bridge=lambda: gateway.bridge,
        namespace=config.namespace or "engineering",
        workflows_dir=layout.workflows,
        grants_file=layout.grants,
        skills_dir=layout.skills,
        coding_workspace_roots=(
            () if config.coding is None else tuple(config.coding.workspace_roots)),
    )
    return ExternalAuthoring(chat, config.device.registered_by, agent)


# -- connecting an agent (X4) -------------------------------------------------

CREATORS = ("aep-workflow-creator", "aep-skill-creator")
AGENTS: dict[str, str] = {
    "claude-code": ".claude/skills",
    "codex": ".agents/skills",
    "copilot": ".github/skills",
}


def creator_text(name: str) -> str:
    from importlib.resources import files

    return (files("host_runtime") / "creators" / name / "SKILL.md").read_text(encoding="utf-8")


def server_command(python: str, config_path: Path, agent: str) -> tuple[str, list[str]]:
    return python, ["-m", "host_runtime.cli", "mcp", "--config", str(config_path.resolve()),
                    "--agent", agent]


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
    if agent == "claude-code":
        settings = project / ".mcp.json"
        current: dict[str, Any] = {}
        if settings.is_file():
            loaded = json.loads(settings.read_text(encoding="utf-8-sig"))
            current = loaded if isinstance(loaded, dict) else {}
        servers = current.setdefault("mcpServers", {})
        servers["aep"] = {"type": "stdio", "command": command, "args": arguments}
        settings.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        lines.append(f"wrote {settings} (server 'aep'); Claude Code asks you to trust it once")
    elif agent == "codex":
        lines += ["Add this to ~/.codex/config.toml:", "", "[mcp_servers.aep]",
                  f"command = {json.dumps(command)}",
                  f"args = {json.dumps(arguments)}", ""]
    else:
        block = {"mcpServers": {"aep": {"type": "local", "command": command,
                                        "args": arguments, "tools": ["*"]}}}
        lines += ["Add this server to ~/.copilot/mcp-config.json:", "",
                  json.dumps(block, indent=2), ""]
    return lines
