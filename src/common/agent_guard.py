"""What a coding agent in Agent Web may touch, decided without asking (owner 2026-10-15).

`docs/phases/AGENT_MODE_BACKENDS.md`, "Revised rules": a conversation's agent
works freely inside its working folder, asks (an approval card) for anything
outside it and for every shell command, and is **never** let near credentials
or protected system settings, even when a person presses Allow:

- tokens, SSH keys and passwords, other credential stores, browser-stored
  passwords;
- the Windows firewall and the Windows user environment's secrets;
- AEP's `host.json` and the AEP workspace's secret files (and, for writes,
  the whole AEP workspace outside `agent-sessions`, so installing, approving
  or publishing an asset can never happen by writing a file);
- the coding agents' own configuration (for writes), so an agent cannot grant
  itself more permissions for a later run.

Paths are judged on their resolved, case-folded form; commands by patterns
and by naming a protected place. The command guard is a backstop: every
command already needs a person's press. This module is pure apart from
reading the environment in `GuardPlaces.current`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Literal

from common.assets import SECRET_PATTERN

RequestKind = Literal["read", "write", "command", "network", "other"]
Decision = Literal["free", "card", "refuse"]

#: The refusal every guard answer starts with: one sentence a person can act on.
REFUSAL = ("AEP never changes credentials or protected system settings through the agent "
           "and never reads their secret values into a conversation, even when allowed")

#: File names that hold a credential wherever they are (lower case).
SECRET_NAMES = frozenset({
    ".env", ".netrc", "_netrc", ".git-credentials", ".pgpass", ".npmrc", ".pypirc",
    ".credentials.json", ".claude.json", "login data", "login data for account",
    "logins.json", "key4.db", "key3.db", "signons.sqlite", "web data",
    "assistant-mcp-token", "agent-web.json", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "known_hosts", "authorized_keys",
})
#: Name endings that mark a key or a password store.
SECRET_SUFFIXES = (".pem", ".key", ".pfx", ".p12", ".kdbx", ".keychain", ".jks",
                   ".keystore", ".ppk", ".gpg", ".asc")
#: `.env.local`, `id_rsa.pub`, `id_ed25519-work` …
SECRET_PREFIXES = (".env.", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519")
#: Tool configuration inside a working folder: writing one may change what an
#: agent is allowed next time, so it is asked even inside the folder.
TOOL_CONFIG_PARTS = (".claude", ".codex", ".copilot", ".vscode", ".github/hooks",
                     ".github/copilot", ".git/hooks", ".mcp.json", ".agents")


def _key(path: Path | str) -> str:
    """A comparable form: absolute, normalized, `/`-separated, case-folded."""
    text = os.path.normpath(os.path.abspath(str(path)))
    return os.path.normcase(text).replace("\\", "/").rstrip("/").casefold()


def inside(path: Path | str, root: Path | str) -> bool:
    """`path` is `root` or below it (by name; links are resolved by callers)."""
    child, parent = _key(path), _key(root)
    return child == parent or child.startswith(parent + "/")


def resolved(path: Path | str, base: Path | None = None) -> Path:
    """An absolute path with `~`, `..` and links resolved; relative to `base`."""
    candidate = Path(os.path.expandvars(str(path))).expanduser()
    if not candidate.is_absolute() and base is not None:
        candidate = base / candidate
    try:
        return candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return Path(os.path.abspath(candidate))


@dataclass(frozen=True)
class GuardPlaces:
    """The protected locations of this computer and this Agent."""

    home: Path
    appdata: Path | None = None
    localappdata: Path | None = None
    system_root: Path | None = None
    program_files: tuple[Path, ...] = ()
    host_json: Path | None = None
    workspace_root: Path | None = None
    # The only part of the workspace an agent may write: its working folders.
    sessions_root: Path | None = None

    @classmethod
    def current(cls, *, host_json: Path | None, workspace_root: Path | None,
                environ: Mapping[str, str] | None = None) -> GuardPlaces:
        env = os.environ if environ is None else environ

        def place(name: str) -> Path | None:
            value = env.get(name)
            return Path(value) if value else None

        home = place("USERPROFILE") or place("HOME") or Path.home()
        programs = tuple(path for path in (place("ProgramFiles"), place("ProgramFiles(x86)"),
                                           place("ProgramW6432")) if path is not None)
        return cls(home=home, appdata=place("APPDATA"), localappdata=place("LOCALAPPDATA"),
                   system_root=place("SystemRoot"), program_files=programs,
                   host_json=host_json, workspace_root=workspace_root,
                   sessions_root=(workspace_root / "agent-sessions"
                                  if workspace_root is not None else None))

    def protected(self) -> tuple[tuple[Path, str], ...]:
        """Never read and never written: credentials and secret stores."""
        home = self.home
        found: list[tuple[Path, str]] = [
            (home / ".ssh", "SSH keys"),
            (home / ".aws", "cloud credentials"),
            (home / ".azure", "cloud credentials"),
            (home / ".gnupg", "signing keys"),
            (home / ".kube", "cluster credentials"),
            (home / ".docker" / "config.json", "registry credentials"),
            (home / ".config" / "gh", "GitHub CLI credentials"),
            (home / ".claude.json", "Claude Code configuration and credentials"),
            (home / ".claude" / ".credentials.json", "Claude Code credentials"),
            (home / ".codex" / "auth.json", "Codex credentials"),
            (home / ".copilot" / "config.json", "Copilot credentials"),
            (home / ".git-credentials", "Git credentials"),
            (home / ".netrc", "stored passwords"),
        ]
        if self.appdata is not None:
            found += [
                (self.appdata / "Microsoft" / "Credentials", "Windows credential store"),
                (self.appdata / "Microsoft" / "Protect", "Windows credential store"),
                (self.appdata / "Microsoft" / "Vault", "Windows credential store"),
                (self.appdata / "Microsoft" / "SystemCertificates", "certificate store"),
                (self.appdata / "Mozilla", "browser profile and stored passwords"),
                (self.appdata / "Opera Software", "browser profile and stored passwords"),
                (self.appdata / "GitHub CLI", "GitHub CLI credentials"),
            ]
        if self.localappdata is not None:
            found += [
                (self.localappdata / "Microsoft" / "Credentials", "Windows credential store"),
                (self.localappdata / "Microsoft" / "Vault", "Windows credential store"),
                (self.localappdata / "Google" / "Chrome" / "User Data",
                 "browser profile and stored passwords"),
                (self.localappdata / "Microsoft" / "Edge" / "User Data",
                 "browser profile and stored passwords"),
                (self.localappdata / "BraveSoftware", "browser profile and stored passwords"),
            ]
        if self.system_root is not None:
            found.append((self.system_root / "System32" / "config", "Windows account store"))
        if self.host_json is not None:
            found.append((self.host_json, "AEP host.json"))
        if self.workspace_root is not None:
            found.append((self.workspace_root / "assistant-mcp-token", "AEP workspace secret"))
            found.append((self.workspace_root / "agent-web.json", "AEP workspace secret"))
            found.append((self.workspace_root / "secrets", "AEP workspace secrets"))
            # Each agent run's MCP configuration carries its tokens.
            backends = self.workspace_root / ".conversation-backends"
            found.append((backends / "agent-runs", "AEP workspace secret"))
            found.append((backends / "copilot-agent-mcp.json", "AEP workspace secret"))
        return tuple(found)

    def write_protected(self) -> tuple[tuple[Path, str], ...]:
        """Never written (reading asks as anywhere outside the folder)."""
        found: list[tuple[Path, str]] = [
            (self.home / ".claude", "a coding agent's own configuration"),
            (self.home / ".codex", "a coding agent's own configuration"),
            (self.home / ".copilot", "a coding agent's own configuration"),
            (self.home / ".agents", "a coding agent's own configuration"),
        ]
        if self.system_root is not None:
            found.append((self.system_root, "Windows system files and settings"))
        found += [(path, "installed programs") for path in self.program_files]
        return tuple(found)


def secret_name(path: Path | str) -> bool:
    """A file whose name says it holds a credential."""
    name = PureWindowsPath(str(path)).name.casefold()
    return (name in SECRET_NAMES or name.endswith(SECRET_SUFFIXES)
            or name.startswith(SECRET_PREFIXES))


def path_refusal(path: Path | str, places: GuardPlaces, *, write: bool) -> str | None:
    """Why this path is never touched through the agent, or None."""
    target = resolved(path)
    for root, label in places.protected():
        if inside(target, root):
            return f"{REFUSAL} ({label})."
    if secret_name(target):
        return f"{REFUSAL} (a credential file)."
    if write:
        for root, label in places.write_protected():
            if inside(target, root):
                return f"{REFUSAL} ({label})."
        workspace, sessions = places.workspace_root, places.sessions_root
        if workspace is not None and inside(target, workspace) and not (
                sessions is not None and inside(target, sessions)):
            return (f"{REFUSAL} (the AEP workspace: installing, approving and publishing "
                    "stay with the Capabilities and portal buttons; submit a draft "
                    "through the aep tools instead).")
    return None


def folder_refusal(folder: Path | str, places: GuardPlaces) -> str | None:
    """Why a folder cannot be a working or read folder: it is protected, or
    it contains a protected location (its reads would be free)."""
    target = resolved(folder)
    if target.parent == target:
        return "A drive root cannot be a conversation folder."
    if _key(target) == _key(places.home):
        return "The home folder cannot be a conversation folder; choose a folder inside it."
    problem = path_refusal(target, places, write=False)
    if problem is not None:
        return problem
    for root, label in places.protected():
        if inside(root, target):
            return f"That folder contains {label}; choose a folder that does not."
    return None


def tool_config(path: Path | str, folder: Path) -> bool:
    """A coding agent's configuration file inside the working folder."""
    if not inside(path, folder):
        return False
    relative = _key(path)[len(_key(folder)):].lstrip("/")
    return any(relative == part or relative.startswith(part + "/")
               for part in TOOL_CONFIG_PARTS)


# -- commands -----------------------------------------------------------------

_COMMAND_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), label) for pattern, label in (
        (r"\bnetsh\b[^|;&]*\b(advfirewall|firewall)\b", "the Windows firewall"),
        (r"\b(new|set|remove|disable|enable|copy|rename)-netfirewall", "the Windows firewall"),
        (r"\bsetx\b", "the Windows user environment"),
        (r"\[\s*(system\.)?environment\s*\]\s*::\s*(set|get)environmentvariable",
         "the Windows user environment"),
        (r"hk(cu|ey_current_user)[:\\/]+\\?environment", "the Windows user environment"),
        (r"\breg(\.exe)?\s+(add|delete|import|export|query|save|restore|load|copy)\b",
         "the Windows registry"),
        (r"\b(get-childitem|gci|ls|dir)\s+env:", "the environment's secret values"),
        (r"\$env:\w*(token|key|secret|passw|pwd|credential|auth)",
         "the environment's secret values"),
        (r"%\w*(token|key|secret|passw|pwd|credential|auth)\w*%",
         "the environment's secret values"),
        (r"^\s*(set|env|printenv)\s*$", "the environment's secret values"),
        (r"\bprintenv\b", "the environment's secret values"),
        (r"\bcmdkey\b|\bvaultcmd\b|\bkeymgr\b|get-storedcredential|convertfrom-securestring",
         "the Windows credential store"),
        (r"\bssh-(keygen|add|copy-id)\b", "SSH keys"),
        (r"\bgh\s+auth\b", "GitHub CLI credentials"),
        (r"\bgit\b[^|;&]*\bcredential", "Git credentials"),
        (r"\b(claude|copilot|codex)\b[^|;&]*\b(login|logout|setup-token|auth)\b",
         "a coding agent's sign-in"),
        (r"\bnet\s+(user|localgroup)\b", "Windows accounts"),
        (r"\bsecurity\s+find-(generic|internet)-password\b", "stored passwords"),
        (r"\baep-host\b[^|;&]*\b(install|approve|publish|enroll|connect|grant|secret)",
         "installing, approving or publishing AEP assets"),
        (r"host_runtime\.cli\b[^|;&]*\b(install|approve|publish|enroll|connect|grant)",
         "installing, approving or publishing AEP assets"),
        (r"[\\/]\.(ssh|aws|azure|gnupg|kube)\b", "credential files"),
        (r"\.claude\.json|\.credentials\.json|\.git-credentials|\b_?\.?netrc\b",
         "credential files"),
        (r"\bid_(rsa|dsa|ecdsa|ed25519)\b", "SSH keys"),
        (r"login data|logins\.json|key[34]\.db", "browser-stored passwords"),
        (r"(^|[\s\"'\\/])\.env(\.\w+)?\b(?!\w)", "credential files"),
        (r"\bhost\.json\b", "AEP host.json"),
        (r"assistant-mcp-token|agent-web\.json", "an AEP workspace secret"),
    ))


def command_refusal(command: str, places: GuardPlaces) -> str | None:
    """Why a command is never run through the agent, or None (a card then asks)."""
    text = command.strip()
    if SECRET_PATTERN.search(text):
        return f"{REFUSAL} (the command carries a credential)."
    for pattern, label in _COMMAND_RULES:
        if pattern.search(text):
            return f"{REFUSAL} ({label})."
    folded = text.replace("\\", "/").casefold()
    for root, label in places.protected():
        for form in {_key(root), str(root).replace("\\", "/").casefold()}:
            if form and form in folded:
                return f"{REFUSAL} ({label})."
    return None


def program(command: str) -> str:
    """The program a command starts, as "Allow for this conversation" names it:
    `git`, `python`, `npm` (a path and `.exe` dropped)."""
    first = command.strip().split(None, 1)[0] if command.strip() else ""
    first = first.strip("\"'&")
    name = PureWindowsPath(first).name.casefold()
    for suffix in (".exe", ".cmd", ".bat", ".ps1"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


# -- the decision ----------------------------------------------------------


@dataclass
class Grants:
    """What a person allowed for the rest of one conversation."""

    read_folders: set[str] = field(default_factory=set)
    write_folders: set[str] = field(default_factory=set)
    programs: set[str] = field(default_factory=set)
    tools: set[str] = field(default_factory=set)

    def as_json(self) -> dict[str, list[str]]:
        return {"read_folders": sorted(self.read_folders),
                "write_folders": sorted(self.write_folders),
                "programs": sorted(self.programs), "tools": sorted(self.tools)}

    @classmethod
    def from_json(cls, data: Mapping[str, Iterable[str]] | None) -> Grants:
        data = data or {}
        return cls(*(set(map(str, data.get(name) or ())) for name in
                     ("read_folders", "write_folders", "programs", "tools")))


@dataclass(frozen=True)
class AgentRequest:
    """One thing a coding agent asked to do, in AEP's terms."""

    kind: RequestKind
    tool: str
    paths: tuple[str, ...] = ()
    command: str = ""
    folder: str = ""
    preview: str = ""
    reason: str = ""


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    message: str = ""
    # What "Allow … for this conversation" would remember: a folder, a
    # program or a tool name; empty when the card offers no such button.
    scope: str = ""


def judge(request: AgentRequest, *, folder: Path, read_roots: Iterable[Path],
          grants: Grants, places: GuardPlaces) -> Verdict:
    """free (inside the folder, or allowed for this conversation), card (ask
    the person) or refuse (protected, even if allowed)."""
    paths = tuple(resolved(item, folder) for item in request.paths)
    write = request.kind == "write"
    for path in paths:
        problem = path_refusal(path, places, write=write)
        if problem is not None:
            return Verdict("refuse", problem)
    if request.kind == "command":
        problem = command_refusal(request.command, places)
        if problem is not None:
            return Verdict("refuse", problem)
        name = program(request.command)
        if name and name in grants.programs:
            return Verdict("free", f"{name} is allowed for this conversation")
        return Verdict("card", scope=name)
    if request.kind == "network":
        if request.tool in grants.tools:
            return Verdict("free", f"{request.tool} is allowed for this conversation")
        return Verdict("card", scope=request.tool)
    if request.kind == "other":
        if request.tool in grants.tools:
            return Verdict("free", f"{request.tool} is allowed for this conversation")
        return Verdict("card", scope=request.tool)
    if not paths:
        paths = (folder,)
    readable = [folder, *read_roots, *map(Path, grants.read_folders),
                *map(Path, grants.write_folders)]
    writable = [folder, *map(Path, grants.write_folders)]
    roots = writable if write else readable
    outside = [path for path in paths if not any(inside(path, root) for root in roots)]
    if write:
        configured = [path for path in paths if tool_config(path, folder)
                      and not any(inside(path, Path(root)) for root in grants.write_folders)]
        if configured:
            return Verdict("card", scope="")
    if not outside:
        return Verdict("free", "inside the conversation's folder or an allowed folder")
    first = outside[0]
    scope = str(first if not write and Path(first).is_dir() else Path(first).parent)
    return Verdict("card", scope=scope)
