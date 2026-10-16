"""AEP's skills and MCP servers for the person's own coding agents, user-wide.

Owner 2026-10-15 (`docs/phases/EXTERNAL_AUTHORING.md`, "Default user-level
setup"): Skills and Workflows made with Claude Code, Codex or Copilot must work
on AEP, and AEP's Knowledge must be usable from them, without a per-folder
`assets connect`. So the installer, the updater and Agent Web Settings put,
for every coding agent found on this computer:

- the creator skills (`aep-workflow-creator`, `aep-skill-creator`) and the
  `aep-knowledge` skill where that agent reads the person's own skills;
- two MCP servers in that agent's user configuration: `aep` (authoring,
  `aep-host mcp`, statuses and codes only) and `aep-assistant` (Knowledge and
  installed Workflows, `aep-host assistant-mcp`, a stdio bridge to the running
  Agent Web that reads its address and token at call time, so no token is
  written into the agent's configuration).

Everything AEP writes is recognisable as AEP's: a skill folder carries
`.aep-managed.json` (with the version), a JSON server entry runs
`host_runtime.cli`, and the Codex TOML entries sit between two marker lines.
Updates replace only those; anything else of the person's is left alone, and
a file is copied to `<name>.aep-backup-<time>` before AEP changes it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from host_runtime.workspace import write_atomically

AgentName = Literal["claude-code", "codex", "copilot"]
AGENT_NAMES: tuple[AgentName, ...] = ("claude-code", "codex", "copilot")
LABELS: dict[str, str] = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "copilot": "GitHub Copilot CLI",
}
EXECUTABLES: dict[str, str] = {"claude-code": "claude", "codex": "codex", "copilot": "copilot"}
SKILLS = ("aep-workflow-creator", "aep-skill-creator", "aep-knowledge")
AUTHORING_SERVER = "aep"
ASSISTANT_SERVER = "aep-assistant"
SERVERS = (AUTHORING_SERVER, ASSISTANT_SERVER)
MARKER_FILE = ".aep-managed.json"
TOML_BEGIN = "# >>> AEP managed: aep-host assets connect --user (edits inside are replaced)"
TOML_END = "# <<< AEP managed"
REPLACE_ATTEMPTS = 5


def skill_text(name: str) -> str:
    from importlib.resources import files

    return (files("host_runtime") / "creators" / name / "SKILL.md").read_text(encoding="utf-8")


def bundle_version() -> str:
    """Changes whenever a shipped skill's text changes, so an update rewrites
    exactly the skills that are out of date."""
    digest = hashlib.sha256()
    for name in SKILLS:
        digest.update(name.encode("utf-8") + b"\0" + skill_text(name).encode("utf-8"))
    return digest.hexdigest()[:12]


@dataclass(frozen=True)
class Environment:
    """Where the person's agent configuration lives. Tests pass a temporary
    home; nothing here reads the real one unless it is given."""

    home: Path
    env: Mapping[str, str] = field(default_factory=dict)
    which: Callable[[str], str | None] = shutil.which

    @classmethod
    def current(cls) -> Environment:
        return cls(Path.home(), dict(os.environ))

    def _dir(self, variable: str, default: Path) -> Path:
        value = self.env.get(variable)
        return Path(value) if value else default


@dataclass(frozen=True)
class AgentPlaces:
    agent: AgentName
    config_dir: Path
    skills_dir: Path
    mcp_file: Path
    mcp_format: Literal["claude", "copilot", "codex"]


def places(agent: AgentName, environment: Environment) -> AgentPlaces:
    home = environment.home
    if agent == "claude-code":
        # Claude Code keeps user-scope MCP servers in ~/.claude.json (the file
        # `claude mcp add --scope user` writes) and personal skills in
        # ~/.claude/skills; CLAUDE_CONFIG_DIR moves both.
        configured = environment.env.get("CLAUDE_CONFIG_DIR")
        config_dir = Path(configured) if configured else home / ".claude"
        mcp_file = (config_dir if configured else home) / ".claude.json"
        return AgentPlaces(agent, config_dir, config_dir / "skills", mcp_file, "claude")
    if agent == "codex":
        # Codex reads personal skills from ~/.agents/skills and MCP servers
        # from [mcp_servers.<name>] in $CODEX_HOME/config.toml (~/.codex).
        codex_home = environment._dir("CODEX_HOME", home / ".codex")
        return AgentPlaces(
            agent, codex_home, home / ".agents" / "skills", codex_home / "config.toml", "codex"
        )
    # The Copilot CLI reads personal skills from ~/.copilot/skills and MCP
    # servers from ~/.copilot/mcp-config.json; COPILOT_HOME moves both.
    copilot_home = environment._dir("COPILOT_HOME", home / ".copilot")
    return AgentPlaces(
        agent, copilot_home, copilot_home / "skills", copilot_home / "mcp-config.json", "copilot"
    )


def detected(agent: AgentName, environment: Environment) -> bool:
    """Installed: its command is on PATH, or its configuration folder exists."""
    return (
        environment.which(EXECUTABLES[agent]) is not None
        or places(agent, environment).config_dir.is_dir()
    )


@dataclass(frozen=True)
class Launch:
    """How an agent starts AEP's two servers."""

    python: str
    config: Path

    def server(self, name: str, agent: AgentName) -> tuple[str, list[str]]:
        config = str(self.config.resolve())
        if name == AUTHORING_SERVER:
            return self.python, [
                "-m",
                "host_runtime.cli",
                "mcp",
                "--config",
                config,
                "--agent",
                agent,
            ]
        return self.python, ["-m", "host_runtime.cli", "assistant-mcp", "--config", config]


def _managed_entry(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    args = entry.get("args")
    return isinstance(args, list) and "host_runtime.cli" in [str(a) for a in args]


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


class Changes:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.backups: list[Path] = []
        self.changed = False

    def write(self, path: Path, text: str) -> None:
        """Write `text` to `path`, backing up what was there first."""
        old = path.read_text(encoding="utf-8-sig") if path.is_file() else None
        if old == text:
            return
        if old is not None:
            backup = path.with_name(f"{path.name}.aep-backup-{_stamp()}")
            shutil.copy2(path, backup)
            self.backups.append(backup)
            self.lines.append(f"  backed up {path} to {backup.name}")
        # A running agent, or a virus scanner, may hold the file for a moment.
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                write_atomically(path, text.encode("utf-8"))
                break
            except PermissionError:
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(0.25 * (attempt + 1))
        self.changed = True


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return {}
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} is not a JSON object")
    return loaded


def _json_entry(fmt: str, command: str, args: list[str]) -> dict[str, Any]:
    if fmt == "copilot":
        return {"type": "local", "command": command, "args": args, "tools": ["*"]}
    return {"type": "stdio", "command": command, "args": args, "env": {}}


def _toml_block(launch: Launch, agent: AgentName) -> str:
    lines = [TOML_BEGIN]
    for name in SERVERS:
        command, args = launch.server(name, agent)
        lines += [
            f"[mcp_servers.{json.dumps(name)}]",
            f"command = {json.dumps(command)}",
            f"args = {json.dumps(args)}",
            "",
        ]
    lines[-1] = TOML_END
    return "\n".join(lines) + "\n"


def _without_block(text: str) -> str:
    if TOML_BEGIN not in text:
        return text
    before, _, rest = text.partition(TOML_BEGIN)
    _, _, after = rest.partition(TOML_END)
    return before.rstrip("\n") + ("\n" if before.strip() else "") + after.lstrip("\n")


def _toml_servers(text: str) -> dict[str, Any]:
    try:
        servers = tomllib.loads(text).get("mcp_servers")
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"config.toml does not parse: {error}") from error
    return servers if isinstance(servers, dict) else {}


# -- install, remove, status -------------------------------------------------


def install(agent: AgentName, environment: Environment, launch: Launch) -> Changes:
    """Put AEP's skills and servers in `agent`'s user configuration;
    idempotent, and it never removes the person's own entries."""
    where = places(agent, environment)
    changes = Changes()
    version = bundle_version()
    for name in SKILLS:
        folder = where.skills_dir / name
        marker = folder / MARKER_FILE
        if folder.exists() and not marker.is_file():
            changes.lines.append(f"  kept your own skill {folder} (not AEP's; not replaced)")
            continue
        changes.write(folder / "SKILL.md", skill_text(name))
        changes.write(
            marker, json.dumps({"managed_by": "aep", "skill": name, "version": version}) + "\n"
        )
    changes.lines.append(f"  skills {', '.join(SKILLS)} in {where.skills_dir} (version {version})")
    if where.mcp_format == "codex":
        text = where.mcp_file.read_text(encoding="utf-8-sig") if where.mcp_file.is_file() else ""
        base = _without_block(text)
        clash = [name for name in SERVERS if name in _toml_servers(base)]
        if clash:
            changes.lines.append(
                f"  kept your own MCP server(s) {', '.join(clash)} in "
                f"{where.mcp_file}; AEP's were not added"
            )
        else:
            joined = (
                base.rstrip("\n") + ("\n\n" if base.strip() else "") + _toml_block(launch, agent)
            )
            _toml_servers(joined)  # never write a file the agent cannot read
            changes.write(where.mcp_file, joined)
            changes.lines.append(f"  MCP servers {', '.join(SERVERS)} in {where.mcp_file}")
    else:
        data = _read_json(where.mcp_file)
        servers = data.setdefault("mcpServers", {})
        if not isinstance(servers, dict):
            raise ValueError(f"{where.mcp_file}: mcpServers is not an object")
        added = []
        for name in SERVERS:
            if name in servers and not _managed_entry(servers[name]):
                changes.lines.append(f"  kept your own MCP server '{name}' in {where.mcp_file}")
                continue
            command, args = launch.server(name, agent)
            servers[name] = _json_entry(where.mcp_format, command, args)
            added.append(name)
        changes.write(where.mcp_file, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        if added:
            changes.lines.append(f"  MCP servers {', '.join(added)} in {where.mcp_file}")
    return changes


def remove(agent: AgentName, environment: Environment) -> Changes:
    """Take out only what AEP put in."""
    where = places(agent, environment)
    changes = Changes()
    for name in SKILLS:
        folder = where.skills_dir / name
        if (folder / MARKER_FILE).is_file():
            shutil.rmtree(folder)
            changes.changed = True
            changes.lines.append(f"  removed skill {folder}")
    if where.skills_dir.is_dir():
        for folder in sorted(where.skills_dir.iterdir()):
            if folder.is_dir() and _pack_marker(folder) is not None:
                shutil.rmtree(folder)
                changes.changed = True
                changes.lines.append(f"  removed skill {folder}")
    if where.mcp_format == "codex":
        if where.mcp_file.is_file():
            text = where.mcp_file.read_text(encoding="utf-8-sig")
            if TOML_BEGIN in text:
                changes.write(where.mcp_file, _without_block(text))
                changes.lines.append(
                    f"  removed MCP servers {', '.join(SERVERS)} from {where.mcp_file}"
                )
    elif where.mcp_file.is_file():
        data = _read_json(where.mcp_file)
        servers = data.get("mcpServers")
        if isinstance(servers, dict):
            gone = [name for name in SERVERS if _managed_entry(servers.get(name))]
            for name in gone:
                del servers[name]
            if gone:
                changes.write(where.mcp_file, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                changes.lines.append(
                    f"  removed MCP servers {', '.join(gone)} from {where.mcp_file}"
                )
    return changes


def status(agent: AgentName, environment: Environment) -> dict[str, Any]:
    where = places(agent, environment)
    current = bundle_version()
    skills: dict[str, str | None] = {}
    for name in SKILLS:
        marker = where.skills_dir / name / MARKER_FILE
        if marker.is_file():
            try:
                skills[name] = str(json.loads(marker.read_text(encoding="utf-8"))["version"])
            except (OSError, ValueError, KeyError, TypeError):
                skills[name] = "unknown"
        else:
            skills[name] = "yours" if (where.skills_dir / name).exists() else None
    servers: dict[str, bool] = dict.fromkeys(SERVERS, False)
    problem = None
    try:
        if where.mcp_format == "codex":
            text = (
                where.mcp_file.read_text(encoding="utf-8-sig") if where.mcp_file.is_file() else ""
            )
            if TOML_BEGIN in text:
                found = _toml_servers(text)
                servers = {name: name in found for name in SERVERS}
        else:
            entries = _read_json(where.mcp_file).get("mcpServers")
            if isinstance(entries, dict):
                servers = {name: _managed_entry(entries.get(name)) for name in SERVERS}
    except (OSError, ValueError) as error:
        problem = f"{where.mcp_file} could not be read: {type(error).__name__}"
    installed = [v for v in skills.values() if v not in (None, "yours")]
    return {
        "agent": agent,
        "label": LABELS[agent],
        "detected": detected(agent, environment),
        "skills_dir": str(where.skills_dir),
        "mcp_file": str(where.mcp_file),
        "skills": skills,
        "servers": servers,
        "version": current,
        "installed": bool(installed) or any(servers.values()),
        "current": len(installed) == len(SKILLS)
        and all(v == current for v in installed)
        and all(servers.values()),
        "problem": problem,
    }


def apply(
    action: Literal["install", "remove"],
    targets: tuple[AgentName, ...],
    environment: Environment,
    launch: Launch | None,
    *,
    only_detected: bool = True,
) -> list[str]:
    """Install or remove for several agents and say what changed. With
    `only_detected`, an agent that is not on this computer is skipped."""
    lines: list[str] = []
    for agent in targets:
        if action == "install" and only_detected and not detected(agent, environment):
            lines.append(f"{LABELS[agent]}: not found on this computer; skipped")
            continue
        try:
            if action == "install":
                assert launch is not None
                changes = install(agent, environment, launch)
            else:
                changes = remove(agent, environment)
        except (OSError, ValueError) as error:
            lines.append(f"{LABELS[agent]}: not changed ({error})")
            continue
        verb = (
            ("installed/updated" if action == "install" else "removed")
            if changes.changed
            else ("already up to date" if action == "install" else "nothing of AEP's to remove")
        )
        lines.append(f"{LABELS[agent]}: {verb}")
        lines.extend(changes.lines)
    return lines


# -- Skill-pack copies (owner 2026-10-16, docs/phases/HERMES_SKILL_PACK.md) --
#
# A pack skill (the Hermes skill pack) lives in AEP's own store
# (`workspace/agent-skills/<folder>`, `host_runtime.skill_packs`) and is copied
# into Claude Code's and Copilot's skills folders only while its AEP Skill is
# switched on; switching it off takes the copy out again. Only for an agent
# that already has AEP's own setup (the installer's `connect --user`, or
# Settings > Coding agents), so `-NoAgentSkills` and a removed setup are
# respected. A same-named folder of the person's own is never touched.

PACK_AGENTS: tuple[AgentName, ...] = ("claude-code", "copilot")


def _pack_marker(folder: Path) -> dict[str, Any] | None:
    """The marker of an AEP pack skill folder, or None (not AEP's, or not a
    pack skill)."""
    marker = folder / MARKER_FILE
    if not marker.is_file():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("managed_by") != "aep" or not data.get("pack"):
        return None
    return data


def aep_setup_present(agent: AgentName, environment: Environment) -> bool:
    """AEP's own skills are in this agent's skills folder."""
    skills_dir = places(agent, environment).skills_dir
    return any((skills_dir / name / MARKER_FILE).is_file() for name in SKILLS)


def link_pack_skill(agent: AgentName, environment: Environment, source: Path) -> Changes:
    """Copy one pack skill folder (with its marker) into `agent`'s skills
    folder, replacing only an older AEP copy."""
    changes = Changes()
    wanted = _pack_marker(source)
    if wanted is None:
        raise ValueError(f"{source} is not an AEP pack skill")
    target = places(agent, environment).skills_dir / source.name
    if target.exists():
        present = _pack_marker(target)
        if present is None:
            changes.lines.append(f"  kept your own skill {target} (not AEP's; not replaced)")
            return changes
        if present.get("version") == wanted.get("version"):
            return changes
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    changes.changed = True
    changes.lines.append(f"  {LABELS[agent]}: skill {source.name} in {target.parent}")
    return changes


def unlink_pack_skill(agent: AgentName, environment: Environment, name: str) -> Changes:
    """Take AEP's copy of one pack skill out of `agent`'s skills folder."""
    changes = Changes()
    target = places(agent, environment).skills_dir / name
    if target.is_dir() and _pack_marker(target) is not None:
        shutil.rmtree(target)
        changes.changed = True
        changes.lines.append(f"  {LABELS[agent]}: removed skill {name} from {target.parent}")
    return changes
