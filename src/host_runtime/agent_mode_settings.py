"""Settings > Agent mode, and each conversation's folders (owner 2026-10-15).

`docs/phases/AGENT_MODE_BACKENDS.md`. Two small JSON files in the workspace:

- `agent-mode.json`: per backend on/off (all off until the person turns one
  on), the default folder new conversations work in, and the email scope;
- `agent-mode-sessions.json`: per conversation its working folder, the extra
  read-only folders a person added, what was allowed "for this
  conversation", and whether mail reading was allowed.

Neither holds a secret.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from pydantic import Field

from common.base import Contract
from host_runtime.workspace import write_atomically
from integrations.outlook_mail import MailScope

SETTINGS_FILE = "agent-mode.json"
SESSIONS_FILE = "agent-mode-sessions.json"
SESSIONS_DIR = "agent-sessions"
#: The backends agent mode exists for, and the ones that can relay prompts.
AGENT_BACKENDS = ("claude_code", "codex", "copilot")
RELAY_BACKENDS = ("claude_code", "copilot")
#: Why a backend stays text-only, shown in Settings and the chat.
TEXT_ONLY_REASON = {
    "codex": ("Codex stays text-only: `codex exec` cannot hand its approval prompts to "
              "Agent Web, and no relay for it has been verified on this computer."),
}


class AgentModeSettings(Contract):
    claude_code: bool = False
    codex: bool = False
    copilot: bool = False
    # Where each conversation's own folder is made; empty: workspace\agent-sessions.
    default_root: str = Field(default="", max_length=400)
    mail: MailScope = MailScope()

    def enabled(self, backend: str) -> bool:
        return backend in RELAY_BACKENDS and bool(getattr(self, backend, False))


class SessionAgentState(Contract):
    folder: str = ""
    read_folders: tuple[str, ...] = Field(default=(), max_length=20)
    grants: dict[str, list[str]] = Field(default_factory=dict)
    mail_read: bool = False


class AgentModeStore:
    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root
        self.settings_path = workspace_root / SETTINGS_FILE
        self.sessions_path = workspace_root / SESSIONS_FILE
        self._lock = threading.RLock()

    @property
    def sessions_root(self) -> Path:
        return self.root / SESSIONS_DIR

    def load(self) -> AgentModeSettings:
        try:
            return AgentModeSettings.model_validate_json(
                self.settings_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return AgentModeSettings()

    def save(self, settings: AgentModeSettings) -> AgentModeSettings:
        checked = AgentModeSettings.model_validate(settings)
        with self._lock:
            write_atomically(self.settings_path,
                             checked.model_dump_json(indent=2).encode("utf-8") + b"\n")
        return checked

    def _sessions(self) -> dict[str, Any]:
        try:
            data = json.loads(self.sessions_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def session(self, session_id: str) -> SessionAgentState:
        with self._lock:
            raw = self._sessions().get(session_id)
        try:
            return SessionAgentState.model_validate(raw or {})
        except ValueError:
            return SessionAgentState()

    def save_session(self, session_id: str, state: SessionAgentState) -> SessionAgentState:
        checked = SessionAgentState.model_validate(state)
        with self._lock:
            data = self._sessions()
            data[session_id] = checked.model_dump(mode="json")
            write_atomically(self.sessions_path,
                             json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
        return checked

    def forget(self, session_id: str) -> None:
        with self._lock:
            data = self._sessions()
            if data.pop(session_id, None) is not None:
                write_atomically(self.sessions_path,
                                 json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
