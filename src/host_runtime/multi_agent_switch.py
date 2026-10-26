"""The Agent Web Settings switch for multi-agent delegation (V1).

It reads and writes `host.json` `multi_agent.enabled` (`MultiAgentSettings`,
`docs/CONTRACTS.md` "Multi-agent delegation (V1)"), the flag the core reads
when the Agent starts: a change applies after an Agent Web restart, so the
card reports what is saved, what the running Agent uses and whether a restart
is needed. It never changes the running configuration.

A Host whose configuration contract has no `multi_agent` field yet reports
`supported: false` and refuses to save, instead of writing a field the Host
would reject on its next start.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.workspace import write_atomically

FIELD = "multi_agent"


def supported() -> bool:
    return FIELD in CompanyHostConfiguration.model_fields


def _enabled(config: object) -> bool:
    settings = getattr(config, FIELD, None)
    return getattr(settings, "enabled", False) is True


def _saved(config_path: Path) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate_json(config_path.read_text(encoding="utf-8-sig"))


def state(config_path: Path | None, running: object) -> dict[str, Any]:
    """The card: saved value, the running Agent's value, restart needed."""
    now = _enabled(running)
    saved = now
    if config_path is not None:
        try:
            saved = _enabled(_saved(config_path))
        except (OSError, ValueError):
            saved = now
    return {
        "ok": True,
        "supported": supported(),
        "writable": config_path is not None and supported(),
        "enabled": saved,
        "running": now,
        "restart_needed": saved != now,
    }


def save(
    config_path: Path | None, running: object, enabled: object, lock: AbstractContextManager[Any]
) -> dict[str, Any]:
    """Write `multi_agent.enabled` to host.json; the rest of the file stays."""
    if not isinstance(enabled, bool):
        return {"ok": False, "code": "multi_agent_settings_invalid"}
    if not supported():
        return {"ok": False, "code": "multi_agent_unsupported"}
    if config_path is None:
        return {"ok": False, "code": "settings_read_only"}
    with lock:
        current = _saved(config_path)
        candidate = current.model_dump(mode="json")
        candidate[FIELD] = {**(candidate.get(FIELD) or {}), "enabled": enabled}
        updated = CompanyHostConfiguration.model_validate(candidate)
        write_atomically(config_path, updated.model_dump_json(indent=2).encode("utf-8") + b"\n")
    return state(config_path, running)
