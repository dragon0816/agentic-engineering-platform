"""Same as last time: a member's last identity answers per Workflow (forms v2).

The old dashboard and bot remembered who a release was for (company, chipset,
branch tag) and offered it again. Here the values of a Workflow's
`group: identity` fields are kept after a run passed validation and was
dispatched, per member and per Workflow name (`namespace/name`, so a new
version keeps them), in one local file of the Host workspace. Agent Web offers
them as a prefill and Telegram asks "Same as last time?".

Only plain values are kept (text, numbers, booleans, lists of text); a value
that looks like a credential is never written. Nothing here leaves the
computer.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from common.assets import WorkflowManifest, reject_embedded_secrets
from common.workflow_forms import IDENTITY_GROUP
from host_runtime.workflow_settings import settings_key
from host_runtime.workspace import write_atomically

PRESETS_FILE = "identity-presets.json"
SCHEMA_VERSION = 1
MAX_VALUE_CHARS = 500


def identity_fields(manifest: WorkflowManifest) -> tuple[str, ...]:
    return tuple(
        field.name
        for field in manifest.parameters
        if field.scope == "runtime" and field.group == IDENTITY_GROUP
    )


def _plain(value: Any) -> bool:
    if isinstance(value, bool | int | float):
        return True
    if isinstance(value, str):
        return 0 < len(value) <= MAX_VALUE_CHARS
    if isinstance(value, list):
        return 0 < len(value) <= 50 and all(
            isinstance(item, str) and 0 < len(item) <= MAX_VALUE_CHARS for item in value
        )
    return False


class IdentityPresets:
    def __init__(self, workspace_root: Path) -> None:
        self.path = workspace_root / PRESETS_FILE
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict[str, dict[str, Any]]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
            return {}
        members = data.get("members")
        return members if isinstance(members, dict) else {}

    def last(self, member: str, manifest: WorkflowManifest) -> dict[str, JsonValue]:
        """The member's last identity values that this Workflow still declares."""
        names = identity_fields(manifest)
        with self._lock:
            stored = self._load().get(member, {}).get(settings_key(manifest.metadata.identity))
        if not isinstance(stored, dict):
            return {}
        return {name: stored[name] for name in names if name in stored and _plain(stored[name])}

    def remember(
        self, member: str, manifest: WorkflowManifest, arguments: Mapping[str, Any]
    ) -> None:
        """Keep this run's identity values; a failure to write is not the run's."""
        names = identity_fields(manifest)
        values = {
            name: arguments[name] for name in names if name in arguments and _plain(arguments[name])
        }
        if not values:
            return
        try:
            reject_embedded_secrets(values)
        except ValueError:
            return
        with self._lock:
            members = self._load()
            members.setdefault(member, {})[settings_key(manifest.metadata.identity)] = values
            payload = {"schema_version": SCHEMA_VERSION, "members": members}
            try:
                write_atomically(
                    self.path,
                    json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                )
            except OSError:
                return
