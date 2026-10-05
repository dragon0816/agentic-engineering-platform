"""Per-install Workflow settings: the values that adapt a Workflow to a person's
computer (rs_workflow_system per-install settings), set once and merged into
every run by the engine.

Settings are keyed by `namespace/name`, so an upgraded version keeps them,
and stored as one JSON file in the Host workspace so every process on this
computer (Agent Web, Telegram, the scheduler) reads the current values on
each run without a restart. Credentials never live here: a Workflow declares
a `SecretRef`, and `host.json` maps it to an environment variable.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from common.assets import AssetIdentity, WorkflowManifest, reject_embedded_secrets
from common.workflow_parameters import static_fields

SETTINGS_FILE = "workflow-settings.json"
SCHEMA_VERSION = 1


class WorkflowSettingsError(ValueError):
    """The settings file is unreadable or a value was refused."""


def settings_key(identity: AssetIdentity) -> str:
    return f"{identity.namespace}/{identity.name}"


class WorkflowSettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise WorkflowSettingsError("workflow settings file is unreadable") from None
        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
            raise WorkflowSettingsError("workflow settings file has an unknown format")
        workflows = data.get("workflows") or {}
        if not isinstance(workflows, dict) or not all(
            isinstance(value, dict) for value in workflows.values()
        ):
            raise WorkflowSettingsError("workflow settings file has an unknown format")
        return workflows

    def values(self, identity: AssetIdentity) -> dict[str, JsonValue]:
        with self._lock:
            return dict(self._load().get(settings_key(identity), {}))

    def for_manifest(self, manifest: WorkflowManifest) -> dict[str, JsonValue]:
        """The stored values for the settings this manifest still declares."""
        declared = {field.name for field in static_fields(manifest)}
        stored = self.values(manifest.metadata.identity)
        return {name: value for name, value in stored.items() if name in declared}

    def save(self, identity: AssetIdentity, values: Mapping[str, JsonValue]) -> None:
        """Replace one Workflow's settings atomically; callers validate first."""
        cleaned = {name: value for name, value in values.items() if value is not None}
        try:
            reject_embedded_secrets(cleaned)
        except ValueError:
            raise WorkflowSettingsError(
                "settings must not contain credentials; declare a SecretRef instead"
            ) from None
        with self._lock:
            workflows = self._load()
            workflows[settings_key(identity)] = cleaned
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {"schema_version": SCHEMA_VERSION, "workflows": workflows},
                    ensure_ascii=False, indent=2, sort_keys=True,
                ),
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
