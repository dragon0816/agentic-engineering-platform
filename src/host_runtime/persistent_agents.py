"""Persistent named agents of one Host (owner consent 2026-11-20, docs/DECISIONS.md
"Sidebar sections and agents bound to Telegram bots").

Besides the main agent (the Host's own, fixed), the owner may keep sub-agents that
own their conversations. A sub-agent carries the parts of an `AgentProfile` that V1
allows (`agent.contracts.AgentProfile`): a name, its purpose (the profile's
`description`), the installed Skills it may use (`skills`) and `model_policy`
(`"session"` only: the conversation's own model through the approved client). Its
turns run on the same `LocalAgent` with the same admission, approvals and
at-most-once rules; only the offered tools are narrowed to its Skills' tools and
its purpose joins the prompt as guidance (`converse_options`). It grants nothing:
a Skill the Host has not installed or the actor may not use offers no tool.

Kept in `<workspace>/agents.json` = `{"agents": [...]}`; each write is atomic and
keeps fields this module does not know (on the file and on each agent).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, ValidationError, model_validator

from common.assets import AssetIdentity, reject_embedded_secrets
from common.base import Contract, Slug, Text
from host_runtime.workspace import write_atomically

AGENTS_FILE = "agents.json"
#: The Host's own agent: always listed, never stored, never deleted.
MAIN_AGENT = "main"
MAX_AGENTS = 20
MAX_DELEGATION_ENTRIES = 20
#: An installed Skill as `namespace/name@version`.
SkillKey = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[A-Za-z0-9_.+-]+$", max_length=200
    ),
]


class AgentStoreError(Exception):
    """A stable code."""


def skill_key(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}@{identity.version}"


class PersistentAgent(Contract):
    id: Slug = Field(max_length=40)
    name: Text = Field(max_length=60)
    purpose: str = Field(default="", max_length=500)
    skills: tuple[SkillKey, ...] = Field(default=(), max_length=40)
    model_policy: Literal["session"] = "session"
    # The installed AgentProfile this agent was created from, when it was
    # (`namespace/name@version`): its delegation records (multi-agent V1) are
    # listed with this agent's conversations. Grants nothing.
    profile: SkillKey | None = None

    @model_validator(mode="after")
    def checked(self) -> Self:
        if self.id == MAIN_AGENT:
            raise ValueError("the main agent is the Host's own")
        if len(self.skills) != len(set(self.skills)):
            raise ValueError("skills name each Skill once")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    def guidance(self) -> str:
        """The agent's role, joined to the conversation prompt."""
        purpose = self.purpose.strip()
        return (
            f'You are "{self.name}", a sub-agent of this Personal Agent.'
            + (f" Your purpose: {purpose}" if purpose else "")
            + " Use only the tools supplied to you."
        )

    def tool_names(self, skill_tools: Iterable[Any]) -> frozenset[str]:
        """The installed Skill tools (`agent.gateway.SkillTool`) of this agent's Skills."""
        wanted = set(self.skills)
        return frozenset(tool.name for tool in skill_tools if skill_key(tool.skill) in wanted)


def converse_options(agent: PersistentAgent, skill_tools: Iterable[Any]) -> dict[str, Any]:
    """`LocalAgent.converse` keyword arguments for a turn of `agent`."""
    return {"allowed_tools": agent.tool_names(skill_tools), "persona_guidance": agent.guidance()}


def delegation_entries(records: Iterable[Any], profile: str) -> list[dict[str, Any]]:
    """The 委派紀錄 (`ConversationMessage.delegations`) of `profile` (any version) in
    `records`, newest first, as read-only entries naming the conversation they are in."""
    wanted = profile.partition("@")[0]
    found: list[dict[str, Any]] = []
    for record in records:
        for message in record.messages:
            for item in message.delegations:
                if str(item.get("profile", "")).partition("@")[0] != wanted:
                    continue
                found.append(
                    {
                        "kind": "delegation",
                        "session_id": record.session_id,
                        "message_id": message.message_id,
                        "title": record.title,
                        "profile": str(item.get("profile", "")),
                        "status": str(item.get("status", "")),
                        "summary": str(item.get("summary", "")),
                        "updated_at": message.created_at.isoformat(),
                    }
                )
    found.sort(key=lambda entry: entry["updated_at"], reverse=True)
    return found[:MAX_DELEGATION_ENTRIES]


def installed_profiles(agents_directory: Path) -> list[dict[str, Any]]:
    """The installed AgentProfiles a sub-agent can be created from: key, name,
    description and Skills (an unreadable or unpublished file is left out)."""
    from agent.contracts import AgentProfile

    found: list[dict[str, Any]] = []
    try:
        paths = sorted(agents_directory.glob("*__*__*.json"))
    except OSError:
        return []
    for path in paths:
        try:
            profile = AgentProfile.model_validate_json(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if profile.metadata.lifecycle != "published":
            continue
        identity = profile.metadata.identity
        found.append(
            {
                "key": skill_key(identity),
                "name": identity.name,
                "description": profile.description,
                "skills": [skill_key(item) for item in profile.skills],
                "model_policy": profile.model_policy,
            }
        )
    return found


def installed_skills(skills_directory: Path) -> tuple[str, ...]:
    """The installed Skills' keys, as their file names say (`namespace__name__version.json`)."""
    found: list[str] = []
    try:
        paths = sorted(skills_directory.glob("*__*__*.json"))
    except OSError:
        return ()
    for path in paths:
        namespace, _, rest = path.stem.partition("__")
        name, _, version = rest.partition("__")
        try:
            found.append(skill_key(AssetIdentity(namespace=namespace, name=name, version=version)))
        except ValidationError:
            continue
    return tuple(found)


class AgentStore:
    """`agents.json`: read fresh on every call, so a change applies at the next turn."""

    def __init__(self, workspace_root: Path) -> None:
        self.path = workspace_root / AGENTS_FILE

    def _raw(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return {"agents": []}
        except (OSError, ValueError):
            raise AgentStoreError("agents_file_unreadable") from None
        if not isinstance(data, dict) or not isinstance(data.get("agents", []), list):
            raise AgentStoreError("agents_file_unreadable")
        data.setdefault("agents", [])
        return data

    def agents(self) -> tuple[PersistentAgent, ...]:
        """Every valid agent; an entry that no longer validates is left out, not fatal."""
        try:
            raw = self._raw()
        except AgentStoreError:
            return ()
        found: list[PersistentAgent] = []
        known = set(PersistentAgent.model_fields)
        for entry in raw["agents"]:
            if not isinstance(entry, dict):
                continue
            try:
                found.append(
                    PersistentAgent.model_validate({k: v for k, v in entry.items() if k in known})
                )
            except ValidationError:
                continue
        return tuple(found)

    def get(self, agent_id: str) -> PersistentAgent | None:
        return next((item for item in self.agents() if item.id == agent_id), None)

    def save(self, agent: PersistentAgent) -> PersistentAgent:
        item = PersistentAgent.model_validate(agent)
        raw = self._raw()
        entries: list[Any] = raw["agents"]
        values = item.model_dump(mode="json")
        for index, entry in enumerate(entries):
            if isinstance(entry, dict) and entry.get("id") == item.id:
                entries[index] = {**entry, **values}
                break
        else:
            if len(entries) >= MAX_AGENTS:
                raise AgentStoreError("agents_too_many")
            entries.append(values)
        self._write(raw)
        return item

    def delete(self, agent_id: str) -> bool:
        raw = self._raw()
        entries: list[Any] = raw["agents"]
        kept = [e for e in entries if not (isinstance(e, dict) and e.get("id") == agent_id)]
        if len(kept) == len(entries):
            return False
        raw["agents"] = kept
        self._write(raw)
        return True

    def _write(self, raw: dict[str, Any]) -> None:
        reject_embedded_secrets(raw)
        write_atomically(
            self.path, json.dumps(raw, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        )
