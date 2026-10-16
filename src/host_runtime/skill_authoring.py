"""Skills drafted outside the Host, checked against what it has installed.

External authoring X1 (`docs/phases/EXTERNAL_AUTHORING.md`, owner 2026-10-08):
Claude Code, Codex or Copilot submit a Skill through `aep-host assets` or
`aep-host mcp`; it becomes a candidate here, and only the owner's approval
installs it. The host decides owner, version and lifecycle, as it does for a
Workflow drafted in a conversation.

A Skill's instructions reach the model's prompt, so what an author may set is
narrower than what an installer may: no keyword `rules` (regular expressions
are trusted installation configuration), no `script_tools`, commands only to
installed capabilities and Workflows, and a `procedure` only for the Knowledge
domain, where it must validate as a `KnowledgeProcedure`.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from agent.skills import SkillManifest
from capabilities.runtime import InstalledCapabilities
from common.assets import SECRET_PATTERN, AssetIdentity, WorkflowManifest
from common.base import Contract, Symbol, Text
from host_runtime.workspace import documents
from knowledge.procedure import KnowledgeProcedure

MAX_INSTRUCTIONS_CHARS = 20_000
REFUSED_FIELDS = ("rules", "script_tools")
_TARGET = re.compile(r"^([a-z0-9][a-z0-9-]*)/([a-z0-9][a-z0-9-]*)@(\d+\.\d+\.\d+)$")


class SkillCandidate(Contract):
    candidate_id: Symbol
    actor: Symbol
    # The conversation that drafted it (agent mode in Agent Web), for its
    # install card; None for an external agent outside Agent Web.
    session_id: Text | None = None
    source: Text = "conversation"
    title: Text
    created_at: Text
    updated_at: Text
    revision: int = Field(default=1, ge=1, strict=True)
    draft: SkillManifest
    status: Text = "draft"
    installed_as: Text | None = None
    installed_digest: Text | None = None


def skill_digest(manifest: SkillManifest) -> str:
    return hashlib.sha256(manifest.model_dump_json().encode("utf-8")).hexdigest()


def _target(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return text[:64] or "skill"


def _identity(text: object) -> dict[str, str] | None:
    if isinstance(text, dict):
        return {k: str(text.get(k, "")) for k in ("namespace", "name", "version")}
    match = _TARGET.match(str(text or "").strip())
    if match is None:
        return None
    return {"namespace": match[1], "name": match[2], "version": match[3]}


def assemble_skill(raw: dict[str, Any], *, namespace: str, owner: str) -> dict[str, Any]:
    """The author's part plus what the host decides; owner, visibility,
    lifecycle and approvals written by the author are replaced."""
    name = _slug(raw.get("name") or raw.get("alias"))
    commands = []
    for command in raw.get("commands") or []:
        if not isinstance(command, dict):
            continue
        commands.append(
            {
                "name": command.get("name"),
                "kind": command.get("kind") or "capability",
                "target": _identity(command.get("target")),
            }
        )
    assembled: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": namespace, "name": name, "version": "1.0.0"},
            "owner": {"type": "user", "id": owner},
            "visibility": "private",
            "lifecycle": "draft",
            "categories": raw.get("categories") or [],
        },
        "alias": raw.get("alias") or name.replace("-", "_"),
        "instructions": raw.get("instructions"),
        "commands": commands,
        "default_command": raw.get("default_command"),
        "harness_guidance": raw.get("harness_guidance"),
        "procedure": raw.get("procedure") or {},
    }
    if raw.get("selector_hint"):
        assembled["selector_hint"] = raw["selector_hint"]
    return assembled


def installed_skills(skills_dir: Path) -> list[SkillManifest]:
    """The Skills installed on this Host (not those set aside in disabled/)."""
    found: list[SkillManifest] = []
    if not skills_dir.is_dir():
        return found
    for path in sorted(skills_dir.glob("*.json")):
        try:
            found.extend(SkillManifest.model_validate(item) for item in documents(path))
        except (OSError, ValueError):
            continue
    return found


def check_skill(
    raw: dict[str, Any],
    manifest_data: dict[str, Any],
    *,
    actor: str,
    installed: InstalledCapabilities,
    workflows: list[WorkflowManifest],
    skills: list[SkillManifest],
) -> tuple[SkillManifest | None, list[str]]:
    """Validate an assembled Skill against this Host; the problems are what
    the author must fix."""
    problems = [
        f"{field}: an authored Skill may not set {field}; the installer configures it"
        for field in REFUSED_FIELDS
        if raw.get(field)
    ]
    instructions = raw.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        problems.append("instructions: required, the guidance the model follows")
    elif len(instructions) > MAX_INSTRUCTIONS_CHARS:
        problems.append(f"instructions: at most {MAX_INSTRUCTIONS_CHARS} characters")
    elif SECRET_PATTERN.search(instructions):
        problems.append("instructions: looks like it holds a password, token or key; remove it")
    for index, command in enumerate(manifest_data["commands"]):
        if command["target"] is None:
            problems.append(f"commands.{index}.target: write it as namespace/name@1.2.3")
    if problems:
        return None, problems
    try:
        manifest = SkillManifest.model_validate(manifest_data)
    except ValidationError as error:
        return None, [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()[:8]
        ]
    have_workflows = {_target(m.metadata.identity) for m in workflows}
    for index, command in enumerate(manifest.commands):
        if command.kind == "capability" and installed.get(command.target) is None:
            problems.append(
                f"commands.{index}: capability {_target(command.target)} is not installed"
            )
        if command.kind == "workflow" and _target(command.target) not in have_workflows:
            problems.append(
                f"commands.{index}: Workflow {_target(command.target)} is not installed"
            )
    if manifest.procedure:
        guidance = manifest.harness_guidance
        if guidance is None or "knowledge" not in guidance.domains:
            problems.append(
                "procedure: only a Knowledge Skill (harness_guidance.domains "
                'includes "knowledge") may carry a procedure'
            )
        else:
            try:
                KnowledgeProcedure.model_validate(manifest.procedure)
            except ValidationError as error:
                problems.extend(
                    f"procedure.{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in error.errors()[:6]
                )
    identity = manifest.metadata.identity
    for other in skills:
        theirs = other.metadata.identity
        if theirs.namespace != identity.namespace:
            continue
        owner = (other.metadata.owner.type, other.metadata.owner.id)
        if theirs.name == identity.name and owner != ("user", actor):
            problems.append(
                f"name: '{identity.name}' already belongs to {owner[1]}; choose "
                "another name, or ask its owner to let you co-edit it"
            )
            break
        if theirs.name != identity.name and other.alias == manifest.alias:
            problems.append(
                f"alias: '{manifest.alias}' is already used by "
                f"{theirs.namespace}/{theirs.name}; choose another alias"
            )
            break
    return (None, problems) if problems else (manifest, [])
