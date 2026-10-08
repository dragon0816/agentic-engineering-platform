"""Start harness telemetry for a long-running host command (owner 2026-10-08).

The store is `<workspace>/telemetry.sqlite`. `strategy_id` is a short hash of
what decides how the harness behaves, so strategy changes compare: the code
build, the model alias, the decision accelerator, the loop limits, the
installed Skill versions, and an optional label the owner sets
(`<workspace>/telemetry.json`, `{"strategy_label": "coding-skill-1.8-trial"}`).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import telemetry.recorder as telemetry
from agent.backend_contracts import (
    CONVERSATION_MAX_OUTPUT_TOKENS,
    MAX_CONVERSATION_TOOL_CALLS,
    MAX_CONVERSATION_TURNS,
)
from telemetry.store import TelemetryStore

SETTINGS_FILE = "telemetry.json"
STORE_FILE = "telemetry.sqlite"


def _build() -> str:
    """The code in use: the git commit (with a dirty mark) or the package version."""
    source = Path(__file__).resolve().parents[2]
    try:
        head = subprocess.run(["git", "-C", str(source), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(source), "status", "--porcelain",
                                "--untracked-files=no"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        if head:
            return head + ("+dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        from importlib.metadata import version

        return "pkg-" + version("agentic-engineering-platform")
    except Exception:  # noqa: BLE001 - an unknown build is still a build
        return "unknown"


def settings(workspace_root: Path) -> dict[str, Any]:
    try:
        loaded = json.loads((workspace_root / SETTINGS_FILE).read_text(encoding="utf-8-sig"))
        return loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        return {}


def strategy(runtime: Any) -> dict[str, Any]:
    config = runtime.config
    skills = sorted(
        f"{m.metadata.identity.namespace}/{m.metadata.identity.name}@{m.metadata.identity.version}"
        for m in runtime.agent.gateway.router.commands.skills.manifests())
    accelerator = config.decision_accelerator
    return {
        "build": _build(),
        "model_alias": None if config.models is None else config.models.routing_alias,
        "accelerator": f"{accelerator.provider}:{getattr(accelerator, 'mode', '')}",
        "limits": f"turns={MAX_CONVERSATION_TURNS},tools={MAX_CONVERSATION_TOOL_CALLS},"
                  f"out={CONVERSATION_MAX_OUTPUT_TOKENS}",
        "skills_digest": hashlib.sha256("\n".join(skills).encode()).hexdigest()[:12],
        "strategy_label": str(settings(runtime.layout.workspace_root).get("strategy_label")
                              or "") or None,
    }


def start(runtime: Any) -> telemetry.Recorder | None:
    """Record this process's runs; never stops the host from starting."""
    if settings(runtime.layout.workspace_root).get("enabled") is False:
        return None
    try:
        store = TelemetryStore(runtime.layout.workspace_root / STORE_FILE)
        return telemetry.configure(store, strategy(runtime))
    except Exception:  # noqa: BLE001 - telemetry is optional
        return None
