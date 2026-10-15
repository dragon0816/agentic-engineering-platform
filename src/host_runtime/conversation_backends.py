"""Restricted adapters for locally signed-in conversation CLIs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field

from agent.backend_contracts import BackendProfile
from agent.data_policy import DataPolicy, OutboundContext
from common.assets import RegistryContract
from host_runtime.acp_client import AcpError, AcpLauncher, prompt_turn
from host_runtime.acp_client import launch as acp_launch
from models.contracts import ModelMessage

ConversationBackendName = Literal["gateway", "claude_code", "codex", "copilot", "copilot_agent"]
ConversationBackendAuthentication = Literal[
    "ready", "required", "pending", "unavailable", "not_applicable"
]
MAX_BACKEND_OUTPUT_CHARS = 16_000
MAX_BACKEND_PROMPT_CHARS = 48_000
BACKEND_TIMEOUT_SECONDS = 90
# The Copilot agent mode reads Knowledge through AEP's tools, several calls per turn.
AGENT_TIMEOUT_SECONDS = 300
AGENT_MCP_FILE = "copilot-agent-mcp.json"
AGENT_SKILLS = ("aep-workflow-creator", "aep-skill-creator", "aep-knowledge")
AGENT_POLICY = (
    "You are GitHub Copilot answering inside AEP, a company engineering agent. You may use "
    "only the `aep-assistant` and `aep` tools. For anything about the company's products, "
    "options, standards, markets or competitors, look it up with aep_knowledge_search and "
    "aep_knowledge_read (try English and Chinese wording) or ask aep_knowledge_ask, and name "
    "the page paths your answer relies on. Say what the knowledge base does not cover instead "
    "of guessing. Run an installed Workflow only with the `aep-assistant` aep_run_workflow, "
    "and never claim one ran when the tool says the person must run it. To build a new "
    "Workflow or Skill for AEP, follow the aep-workflow-creator or aep-skill-creator skill "
    "with the `aep` tools (aep_catalog, aep_workflow_format, aep_capability, "
    "aep_check_workflow, aep_submit_workflow, ...); "
    "when the request is unclear, reply with short questions first. Do not write files or "
    "run commands."
)
AUTH_STATUS_TIMEOUT_SECONDS = 10
# Agent mode (owner 2026-10-15, docs/phases/AGENT_MODE_BACKENDS.md): a turn may
# wait up to ten minutes on each approval card, so the whole run is bounded
# at thirty.
AGENT_MODE_TIMEOUT_SECONDS = 1800
AGENT_RUNS_DIR = "agent-runs"
AGENT_PLUGIN_DIR = "claude-plugin"
AGENT_SKILLS_ROOT = "agent-skills"
CLAUDE_PERMISSION_TOOL = "mcp__aep-agent__permission"
#: Claude Code settings for an agent-mode run: every command and network use
#: asks (even ones Claude Code would let through), AEP's tools are allowed,
#: credential files are denied even inside the folder, no hooks.
CLAUDE_AGENT_SETTINGS = {
    "permissions": {
        "ask": ["Bash", "PowerShell", "WebFetch", "WebSearch"],
        "allow": ["mcp__aep-agent", "mcp__aep-assistant", "mcp__aep"],
        "deny": [
            f"{tool}({pattern})"
            for tool in ("Read", "Edit", "Write")
            for pattern in (
                "**/.env",
                "**/.env.*",
                "**/*.pem",
                "**/*.key",
                "**/*.pfx",
                "**/*.p12",
                "**/*.kdbx",
                "**/id_rsa*",
                "**/id_ed25519*",
                "**/id_ecdsa*",
                "**/.git-credentials",
                "**/.netrc",
                "**/host.json",
            )
        ],
    },
    "disableAllHooks": True,
}
AGENT_MODE_POLICY = (
    "You are {label}, working for a person inside AEP Agent Web (a company engineering "
    "agent). Your working folder is {folder}: read and write files there freely. "
    "{read_roots}Reading anything else, changing files outside the folder and every shell "
    "command are shown to the person as an approval card; wait for it, and when it is "
    "denied do not try another way to do the same thing. Credentials and protected "
    "settings (tokens, SSH keys, passwords, the Windows firewall, environment secrets, "
    "host.json, browser passwords, credential stores) are never touched, even when asked. "
    "Never install, approve or publish AEP assets: build Workflows and Skills with the "
    "aep-workflow-creator / aep-skill-creator skills and submit them as drafts with the "
    "`aep` tools. For company knowledge use the `aep-assistant` tools and cite page paths. "
    "Mail: `aep-agent` outlook_search / outlook_read (read only, the person's scope) and "
    "outlook_draft (the person presses Send for each message). Knowledge pipeline: "
    "`aep-agent` knowledge_* tools; pushing to the vault stays with the person on the "
    "Knowledge page. Answer in the person's language."
)


class ConversationBackendStatus(RegistryContract):
    name: ConversationBackendName
    label: str
    available: bool
    selectable: bool
    authentication: ConversationBackendAuthentication
    action: Literal["none", "authenticate", "configure", "install"]
    detail: str


class ConversationBackendResult(RegistryContract):
    backend: ConversationBackendName
    status: Literal["answered", "unavailable", "failed", "timeout"]
    text: str = ""
    code: str | None = None


@dataclass
class AgentLaunch:
    """What an agent-mode run needs from Agent Web (host_runtime.agent_mode)."""

    folder: Path
    # MCP server name -> (URL, bearer token): `aep-agent` (this run's own
    # token), `aep-assistant` and `aep` (the assistant token).
    servers: dict[str, tuple[str, str]]
    # Copilot's ACP permission requests and tool outcomes.
    on_permission: Callable[[dict[str, object]], bool]
    on_tool_update: Callable[[str, str], None] | None = None
    read_roots: tuple[Path, ...] = ()
    timeout_s: int = AGENT_MODE_TIMEOUT_SECONDS
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class ProcessResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        input: str,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        env: Mapping[str, str],
    ) -> ProcessResult: ...


class AuthenticationProcess(Protocol):
    def poll(self) -> int | None: ...


class AuthenticationLauncher(Protocol):
    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> AuthenticationProcess: ...


class BackendSpec(RegistryContract):
    name: ConversationBackendName
    label: str
    executable: str
    arguments: tuple[str, ...] = Field(min_length=1)
    authentication_arguments: tuple[str, ...] = Field(min_length=1)
    authentication_status_arguments: tuple[str, ...] = ()


SPECS = (
    BackendSpec(
        name="codex",
        label="Codex",
        executable="codex",
        arguments=(
            "exec",
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
            "-",
        ),
        authentication_arguments=("login",),
        authentication_status_arguments=("login", "status"),
    ),
    BackendSpec(
        name="claude_code",
        label="Claude Code",
        executable="claude",
        arguments=(
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--safe-mode",
            "--restricted",
            "--tools",
            "",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--permission-prompts",
            "none",
        ),
        authentication_arguments=("auth", "login"),
        authentication_status_arguments=("auth", "status"),
    ),
    BackendSpec(
        # COPILOT_INTEGRATION CP2: the same signed-in CLI with AEP's assistant tools
        # (MCP over Agent Web) as its only tools; shell and file writes denied.
        name="copilot_agent",
        label="GitHub Copilot (agent, AEP tools)",
        executable="copilot",
        arguments=(
            "--output-format=json",
            "--no-ask-user",
            "--disable-builtin-mcps",
            "--allow-tool=aep",
            "--allow-tool=aep-assistant",
            "--deny-tool=shell",
            "--deny-tool=write",
        ),
        authentication_arguments=("login",),
    ),
    BackendSpec(
        name="copilot",
        label="GitHub Copilot",
        executable="copilot",
        arguments=(
            "--output-format=json",
            "--no-ask-user",
            "--available-tools=",
            "--disable-builtin-mcps",
        ),
        authentication_arguments=("login",),
    ),
)


def _run_process(
    argv: list[str],
    *,
    cwd: Path,
    input: str,
    capture_output: bool,
    text: bool,
    timeout: int,
    check: bool,
    env: Mapping[str, str],
) -> ProcessResult:
    # UTF-8, never the console code page: a Chinese answer from a CLI crashed
    # the cp950 reader thread and left stdout None (2026-10-08 log).
    return subprocess.run(
        argv,
        cwd=cwd,
        input=input,
        capture_output=capture_output,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        timeout=timeout,
        check=check,
        env=env,
    )


def _launch_authentication(
    argv: list[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
) -> AuthenticationProcess:
    """Launch only a fixed login command in a visible local console."""

    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
    return subprocess.Popen(  # noqa: S603 - argv comes only from fixed BackendSpec values
        argv,
        cwd=cwd,
        env=env,
        stdin=None,
        stdout=None,
        stderr=None,
        start_new_session=os.name != "nt",
        creationflags=creationflags,
    )


def _environment() -> dict[str, str]:
    allowed = (
        "PATH",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "CODEX_HOME",
        # A person's own Copilot token, for headless sign-in (COPILOT_INTEGRATION).
        "COPILOT_GITHUB_TOKEN",
        "TEMP",
        "TMP",
        "SystemRoot",
        "ComSpec",
    )
    return {name: os.environ[name] for name in allowed if name in os.environ}


def _text_values(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key in ("result", "text", "content", "message"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                found.append(item.strip())
        for item in value.values():
            if isinstance(item, (dict, list)):
                found.extend(_text_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_text_values(item))
    return found


def _answer(output: str | None) -> str:
    values: list[str] = []
    output = output or ""
    try:
        values.extend(_text_values(json.loads(output)))
    except json.JSONDecodeError:
        for line in output.splitlines():
            try:
                values.extend(_text_values(json.loads(line)))
            except json.JSONDecodeError:
                continue
    if values:
        return values[-1][:MAX_BACKEND_OUTPUT_CHARS]
    stripped = output.strip()
    return stripped[:MAX_BACKEND_OUTPUT_CHARS] if stripped else ""


def _error_code(output: str) -> str:
    objects: list[object] = []
    try:
        objects.append(json.loads(output))
    except json.JSONDecodeError:
        for line in output.splitlines():
            try:
                objects.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def authentication_failure(value: object) -> bool:
        if isinstance(value, dict):
            if value.get("api_error_status") in (401, 403):
                return True
            return any(authentication_failure(item) for item in value.values())
        if isinstance(value, list):
            return any(authentication_failure(item) for item in value)
        return False

    return (
        "backend_authentication_failed"
        if any(authentication_failure(item) for item in objects)
        else "backend_failed"
    )


class LocalConversationBackends:
    """Discover fixed CLI names and run them in a blank, bounded context."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        which: Callable[[str], str | None] = shutil.which,
        runner: ProcessRunner = _run_process,
        status_runner: ProcessRunner | None = None,
        authentication_launcher: AuthenticationLauncher = _launch_authentication,
        acp_launcher: AcpLauncher | None = None,
    ) -> None:
        self.root = workspace_root / ".conversation-backends"
        self.root.mkdir(parents=True, exist_ok=True)
        self._which = which
        self._runner = runner
        self._status_runner = runner if status_runner is None else status_runner
        self._authentication_launcher = authentication_launcher
        self._acp_launcher = acp_launcher if acp_launcher is not None else acp_launch
        self._specs = {item.name: item for item in SPECS}
        self._unavailable: dict[ConversationBackendName, str] = {}
        self._authentication_processes: dict[ConversationBackendName, AuthenticationProcess] = {}
        self._authenticated_this_run: set[ConversationBackendName] = set()
        # (MCP URL, assistant token) of the running Agent Web, for the agent mode;
        # its authoring tools are at the same URL + "/authoring".
        self.agent_mcp: tuple[str, str] | None = None

    def _authentication(
        self, spec: BackendSpec, executable: str
    ) -> ConversationBackendAuthentication:
        process = self._authentication_processes.get(spec.name)
        if process is not None:
            finished = process.poll()
            if finished is None:
                return "pending"
            del self._authentication_processes[spec.name]
            if finished == 0:
                self._authenticated_this_run.add(spec.name)
                self._unavailable.pop(spec.name, None)
                return "ready"
            return "required"
        if spec.name in self._authenticated_this_run:
            return "ready"
        if self._unavailable.get(spec.name) == "backend_authentication_failed":
            return "required"
        if not spec.authentication_status_arguments:
            return "required"
        try:
            completed = self._status_runner(
                [executable, *spec.authentication_status_arguments],
                cwd=self.root,
                input="",
                capture_output=True,
                text=True,
                timeout=AUTH_STATUS_TIMEOUT_SECONDS,
                check=False,
                env=_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            return "required"
        return "ready" if completed.returncode == 0 else "required"

    def statuses(
        self,
        *,
        gateway_available: bool,
        gateway_configured: bool | None = None,
        gateway_issue: str | None = None,
    ) -> tuple[ConversationBackendStatus, ...]:
        configured = gateway_available if gateway_configured is None else gateway_configured
        rows = [
            ConversationBackendStatus(
                name="gateway",
                label="Configured LLM Gateway",
                available=gateway_available,
                selectable=configured,
                authentication=(
                    "ready" if gateway_available else ("required" if configured else "unavailable")
                ),
                action=("none" if gateway_available else "configure"),
                detail=(
                    "Configured and ready"
                    if gateway_available
                    else (
                        gateway_issue or "Configured; its mapped credential is unavailable"
                        if configured
                        else "Configure it in Settings"
                    )
                ),
            )
        ]
        for spec in SPECS:
            failure = self._unavailable.get(spec.name)
            executable = self._which(spec.executable)
            authentication = (
                "unavailable" if executable is None else self._authentication(spec, executable)
            )
            available = executable is not None and authentication == "ready" and failure is None
            rows.append(
                ConversationBackendStatus(
                    name=spec.name,
                    label=spec.label,
                    available=available,
                    selectable=executable is not None,
                    authentication=authentication,
                    action=(
                        "install"
                        if executable is None
                        else ("none" if authentication == "ready" else "authenticate")
                    ),
                    detail=(
                        "Local CLI found and signed in"
                        if available
                        else (
                            f"{spec.executable} authentication is in progress"
                            if authentication == "pending"
                            else (
                                "Sign in to this local CLI"
                                if executable is not None
                                else f"{spec.executable} is not installed or not on PATH"
                            )
                        )
                    ),
                )
            )
        return tuple(rows)

    def authenticate(self, backend: ConversationBackendName) -> dict[str, object]:
        """Start one fixed official CLI login flow after an explicit UI action."""

        spec = self._specs.get(backend)
        if spec is None:
            return {"ok": False, "backend": backend, "code": "backend_authentication_unsupported"}
        executable = self._which(spec.executable)
        if executable is None:
            return {"ok": False, "backend": backend, "code": "backend_not_installed"}
        authentication = self._authentication(spec, executable)
        if authentication == "ready":
            return {"ok": True, "backend": backend, "status": "ready"}
        if authentication == "pending":
            return {"ok": True, "backend": backend, "status": "pending"}
        try:
            process = self._authentication_launcher(
                [executable, *spec.authentication_arguments],
                cwd=self.root,
                env=_environment(),
            )
        except OSError:
            return {"ok": False, "backend": backend, "code": "backend_authentication_failed"}
        self._authentication_processes[backend] = process
        return {"ok": True, "backend": backend, "status": "started"}

    def complete(
        self,
        backend: ConversationBackendName,
        history: tuple[ModelMessage, ...],
        *,
        persona_guidance: str,
        outbound: OutboundContext | None = None,
        max_history_messages: int = 12,
        agent: AgentLaunch | None = None,
    ) -> ConversationBackendResult:
        spec = self._specs.get(backend)
        if spec is None:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_not_local_cli"
            )
        if outbound is not None:
            expected = [("history", message.text) for message in history]
            if persona_guidance:
                expected.append(("persona", persona_guidance))
            actual = [(item.origin, item.text) for item in outbound.materials]
            if actual != expected or any(
                message.images or message.tool_calls for message in history
            ):
                return ConversationBackendResult(
                    backend=backend, status="unavailable", code="context_mismatch"
                )
        decision = DataPolicy(()).decide(
            BackendProfile(backend_id=backend, kind="agent", harness="native"), outbound
        )
        if not decision.allowed:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code=decision.code
            )
        executable = self._which(spec.executable)
        if executable is None:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_not_installed"
            )
        if isinstance(max_history_messages, bool) or not 1 <= max_history_messages <= 40:
            raise ValueError("conversation supports one to forty history messages")
        if agent is not None:
            return self._agent_turn(
                backend, executable, history, persona_guidance, max_history_messages, agent
            )
        prompt = self._prompt(history, persona_guidance, max_history_messages)
        extra: list[str] = []
        timeout = BACKEND_TIMEOUT_SECONDS
        if backend == "copilot_agent":
            if self.agent_mcp is None:
                return ConversationBackendResult(
                    backend=backend, status="unavailable", code="assistant_tools_unavailable"
                )
            url, token = self.agent_mcp
            config = self.root / AGENT_MCP_FILE
            headers = {"Authorization": f"Bearer {token}"}
            # The same server names as the person's own user-level setup
            # (agent_setup.py), so these replace those for this session: the
            # Knowledge and Workflow tools, and the authoring tools, both
            # served by this Agent Web.
            config.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "aep-assistant": {
                                "type": "http",
                                "url": url,
                                "tools": ["*"],
                                "headers": headers,
                            },
                            "aep": {
                                "type": "http",
                                "url": url.rstrip("/") + "/authoring",
                                "tools": ["*"],
                                "headers": headers,
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            self._write_agent_skills()
            extra = ["--additional-mcp-config", f"@{config}", "--add-dir", str(self.root)]
            timeout = AGENT_TIMEOUT_SECONDS
            prompt = self._prompt(
                history, persona_guidance, max_history_messages, policy=AGENT_POLICY
            )
        try:
            completed = self._runner(
                [executable, *spec.arguments, *extra],
                cwd=self.root,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=_environment(),
            )
        except subprocess.TimeoutExpired:
            return ConversationBackendResult(
                backend=backend, status="timeout", code="backend_timeout"
            )
        except OSError:
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="backend_start_failed"
            )
        if completed.returncode != 0:
            code = _error_code(completed.stdout)
            if code == "backend_authentication_failed":
                self._unavailable[backend] = code
            return ConversationBackendResult(backend=backend, status="failed", code=code)
        answer = _answer(completed.stdout)
        if not answer:
            return ConversationBackendResult(
                backend=backend, status="failed", code="backend_empty_response"
            )
        return ConversationBackendResult(backend=backend, status="answered", text=answer)

    # -- agent mode (owner 2026-10-15) ----------------------------------------

    def _agent_turn(
        self,
        backend: ConversationBackendName,
        executable: str,
        history: tuple[ModelMessage, ...],
        persona_guidance: str,
        max_history_messages: int,
        agent: AgentLaunch,
    ) -> ConversationBackendResult:
        """One agent-mode turn: Claude Code with its permission prompts sent
        to AEP's `permission` tool, or Copilot over ACP. Codex has no relay."""
        if backend not in ("claude_code", "copilot"):
            return ConversationBackendResult(
                backend=backend, status="unavailable", code="agent_mode_unsupported"
            )
        label = {"claude_code": "Claude Code", "copilot": "GitHub Copilot"}[backend]
        roots = "; ".join(str(item) for item in agent.read_roots)
        policy = AGENT_MODE_POLICY.format(
            label=label,
            folder=agent.folder,
            read_roots=(f"You may also read these folders freely: {roots}. " if roots else ""),
        )
        prompt = self._prompt(history, persona_guidance, max_history_messages, policy=policy)
        run_dir = self.root / AGENT_RUNS_DIR / agent.run_id
        try:
            if backend == "claude_code":
                return self._claude_agent(executable, prompt, agent, run_dir)
            return self._copilot_agent(executable, prompt, agent)
        finally:
            shutil.rmtree(run_dir, ignore_errors=True)

    def _claude_agent(
        self, executable: str, prompt: str, agent: AgentLaunch, run_dir: Path
    ) -> ConversationBackendResult:
        run_dir.mkdir(parents=True, exist_ok=True)
        servers = {
            name: {"type": "http", "url": url, "headers": {"Authorization": f"Bearer {token}"}}
            for name, (url, token) in agent.servers.items()
        }
        mcp_file = run_dir / "mcp.json"
        mcp_file.write_text(json.dumps({"mcpServers": servers}), encoding="utf-8")
        settings_file = run_dir / "settings.json"
        settings_file.write_text(json.dumps(CLAUDE_AGENT_SETTINGS), encoding="utf-8")
        plugin = self._write_claude_plugin()
        argv = [
            executable,
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            str(mcp_file),
            "--settings",
            str(settings_file),
            "--permission-mode",
            "manual",
            "--permission-prompts",
            "host",
            "--permission-prompt-tool",
            CLAUDE_PERMISSION_TOOL,
            "--plugin-dir",
            str(plugin),
        ]
        environment = _environment()
        # An approval card may wait ten minutes inside one tool call.
        environment["MCP_TOOL_TIMEOUT"] = str((agent.timeout_s + 60) * 1000)
        try:
            completed = self._runner(
                argv,
                cwd=agent.folder,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=agent.timeout_s,
                check=False,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return ConversationBackendResult(
                backend="claude_code", status="timeout", code="backend_timeout"
            )
        except OSError:
            return ConversationBackendResult(
                backend="claude_code", status="unavailable", code="backend_start_failed"
            )
        if completed.returncode != 0:
            code = _error_code(completed.stdout)
            if code == "backend_authentication_failed":
                self._unavailable["claude_code"] = code
            return ConversationBackendResult(backend="claude_code", status="failed", code=code)
        answer = _answer(completed.stdout)
        if not answer:
            return ConversationBackendResult(
                backend="claude_code", status="failed", code="backend_empty_response"
            )
        return ConversationBackendResult(backend="claude_code", status="answered", text=answer)

    def _copilot_agent(
        self, executable: str, prompt: str, agent: AgentLaunch
    ) -> ConversationBackendResult:
        skills = self._write_agent_skills(self.root / AGENT_SKILLS_ROOT)
        argv = [
            executable,
            "--acp",
            "--no-auto-update",
            "--disable-builtin-mcps",
            "--disallow-temp-dir",
            "--no-ask-user",
            "--secret-env-vars=COPILOT_GITHUB_TOKEN",
            *(f"--allow-tool={name}" for name in agent.servers),
            "--add-dir",
            str(skills),
        ]
        servers = [
            {
                "type": "http",
                "name": name,
                "url": url,
                "headers": [{"name": "Authorization", "value": f"Bearer {token}"}],
            }
            for name, (url, token) in agent.servers.items()
        ]
        try:
            process = self._acp_launcher(argv, agent.folder, _environment())
        except OSError:
            return ConversationBackendResult(
                backend="copilot", status="unavailable", code="backend_start_failed"
            )
        try:
            answer = prompt_turn(
                process,
                cwd=agent.folder,
                mcp_servers=servers,
                prompt=prompt,
                deadline_s=agent.timeout_s,
                on_permission=agent.on_permission,
                on_tool_update=agent.on_tool_update,
            )
        except AcpError as error:
            if error.code == "backend_authentication_failed":
                self._unavailable["copilot"] = error.code
            status: Literal["failed", "timeout"] = (
                "timeout" if error.code == "backend_timeout" else "failed"
            )
            return ConversationBackendResult(backend="copilot", status=status, code=error.code)
        finally:
            if process.poll() is None:
                process.kill()
        if not answer:
            return ConversationBackendResult(
                backend="copilot", status="failed", code="backend_empty_response"
            )
        return ConversationBackendResult(
            backend="copilot", status="answered", text=answer[:MAX_BACKEND_OUTPUT_CHARS]
        )

    def _write_claude_plugin(self) -> Path:
        """AEP's skills as a Claude Code plugin loaded with --plugin-dir, so the
        agent has them whatever the person's own configuration holds."""
        from host_runtime.agent_setup import bundle_version, skill_text

        root = self.root / AGENT_PLUGIN_DIR
        manifest = root / ".claude-plugin" / "plugin.json"
        text = json.dumps(
            {
                "name": "aep",
                "version": bundle_version(),
                "description": "AEP's creator and knowledge skills",
            }
        )
        if not manifest.is_file() or manifest.read_text(encoding="utf-8") != text:
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(text, encoding="utf-8")
        for name in AGENT_SKILLS:
            target = root / "skills" / name / "SKILL.md"
            body = skill_text(name)
            if not target.is_file() or target.read_text(encoding="utf-8") != body:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
        return root

    def skill_roots(self) -> tuple[Path, ...]:
        """Where agent mode's read-only skills live (free to read)."""
        return (self.root / AGENT_PLUGIN_DIR, self.root / AGENT_SKILLS_ROOT)

    def _write_agent_skills(self, root: Path | None = None) -> Path:
        """AEP's skills where the Copilot agent reads them (`.github/skills` of
        its working folder, trusted through --add-dir), whatever the person's
        own Copilot configuration holds."""
        from host_runtime.agent_setup import skill_text

        root = self.root if root is None else root
        for name in AGENT_SKILLS:
            target = root / ".github" / "skills" / name / "SKILL.md"
            text = skill_text(name)
            if not target.is_file() or target.read_text(encoding="utf-8") != text:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
        return root

    @staticmethod
    def _prompt(
        history: tuple[ModelMessage, ...],
        persona_guidance: str,
        max_history_messages: int = 12,
        policy: str | None = None,
    ) -> str:
        policy = policy or (
            "You are a restricted conversation backend for a Personal Engineering Agent. "
            "Answer with text only. Do not use tools, read files, execute commands, browse, "
            "modify state, or claim an action occurred. The host Agent separately validates "
            "and executes every supported tool through its Bridge."
        )
        prefix = (
            policy
            + "\n\nPersona controls speaking style only:\n"
            + persona_guidance[:4000]
            + "\n\nConversation:\n"
        )
        suffix = "\nassistant:"
        remaining = MAX_BACKEND_PROMPT_CHARS - len(prefix) - len(suffix)
        selected: list[str] = []
        for message in reversed(history[-max_history_messages:]):
            line = f"{message.role}: {message.text[:4000]}"
            size = len(line) + (1 if selected else 0)
            if size > remaining:
                break
            selected.append(line)
            remaining -= size
        return prefix + "\n".join(reversed(selected)) + suffix
