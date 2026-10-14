"""Where a parameter's dynamic choices come from: `ref:` sets or `fn:` functions.

`ref:<set>` reads a published reference set (`reference_sets.py`). `fn:<name>`
calls a read-only host function with the Workflow's own per-install settings,
for a choice list that is a property of this install rather than something a
run published: Workflow 14's stations come from the catalogue file its
settings name. Arguments use the same `{field}` placeholders as `ref:` filters:
`fn:ncc_plan.stations?region={region}`.

A function only reads. It gets the settings and the bound arguments, never a
credential, and an error it raises is treated as "not available", which the
engine reports as a rejected run and a form shows as an empty list (forms v2:
a field with `allow_other` then simply takes a typed value).

A placeholder may name one of the Workflow's settings (`scope: static`) as
well as an earlier answer: `fn:folder_files?folder={inbox_path}&accept=.json`
lists the files of the inbox the install's settings name. Settings are bound
from the install, never from what a run or a form sent.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from pydantic import JsonValue

from common.assets import WorkflowManifest
from host_runtime.reference_sets import ReferenceItem, ReferenceQuery, ReferenceSetStore

ChoiceFunction = Callable[[Mapping[str, JsonValue], Mapping[str, str]], list[ReferenceItem]]
SettingsProvider = Callable[[WorkflowManifest], Mapping[str, JsonValue]]
_PLACEHOLDER = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")
#: The built-in folder listing (`fn:folder_files?folder=...&accept=...`).
FOLDER_FILES = "folder_files"
MAX_FOLDER_FILES = 500


def folder_files(
    _settings: Mapping[str, JsonValue], arguments: Mapping[str, str]
) -> list[ReferenceItem]:
    """The regular files directly in one absolute folder, by bare name.

    No subfolders, hidden files or links, so a value never leads out of the
    folder; `accept` is a comma-separated list of extensions. Read-only.
    """
    raw = str(arguments.get("folder") or "").strip()
    folder = Path(raw)
    if not raw or not folder.is_absolute() or not folder.is_dir():
        raise ValueError("folder is not an existing absolute folder")
    accept = {
        item.strip().lower() if item.strip().startswith(".") else f".{item.strip().lower()}"
        for item in str(arguments.get("accept") or "").split(",") if item.strip()
    }
    names: list[str] = []
    for entry in folder.iterdir():
        if (
            entry.name.startswith(".") or entry.is_symlink() or not entry.is_file()
            or (accept and entry.suffix.lower() not in accept)
        ):
            continue
        names.append(entry.name)
    return [ReferenceItem(value=name) for name in sorted(names, key=str.casefold)[
        :MAX_FOLDER_FILES]]


class FunctionQuery:
    """A parsed `fn:` choice source: the function name and its arguments."""

    def __init__(self, source: str) -> None:
        if not source.startswith("fn:"):
            raise ValueError("not a fn: choice source")
        name, _, query = source[3:].partition("?")
        self.name = name
        self.arguments = dict(parse_qsl(query, keep_blank_values=True))

    def needed(self) -> tuple[str, ...]:
        return tuple(
            match.group(1)
            for value in self.arguments.values()
            if (match := _PLACEHOLDER.match(value)) is not None
        )

    def bind(self, answers: Mapping[str, Any]) -> dict[str, str] | None:
        """Arguments with earlier answers filled in, or None while one is missing."""
        bound: dict[str, str] = {}
        for key, value in self.arguments.items():
            match = _PLACEHOLDER.match(value)
            if match is None:
                bound[key] = value
                continue
            answer = answers.get(match.group(1))
            if answer in (None, ""):
                return None
            bound[key] = str(answer)
        return bound


class ChoiceSources:
    def __init__(
        self,
        references: ReferenceSetStore,
        settings: SettingsProvider | None = None,
        functions: Mapping[str, ChoiceFunction] | None = None,
    ) -> None:
        self.references = references
        self.settings = settings
        self.functions = dict(functions or {})

    @staticmethod
    def needed(source: str, manifest: WorkflowManifest | None = None) -> tuple[str, ...]:
        """Answers the source waits for; settings of `manifest` are never waited for."""
        found = (
            FunctionQuery(source).needed() if source.startswith("fn:")
            else ReferenceQuery(source).needed()
        )
        if manifest is None:
            return found
        settings = {field.name for field in manifest.parameters if field.scope == "static"}
        return tuple(name for name in found if name not in settings)

    def resolve(
        self, manifest: WorkflowManifest, source: str, answers: Mapping[str, Any]
    ) -> list[ReferenceItem] | None:
        """The current choices, or None when the source is unavailable or a
        needed earlier answer is missing."""
        if source.startswith("ref:"):
            if any(field.scope == "static" for field in manifest.parameters):
                try:
                    settings = dict(self.settings(manifest)) if self.settings else {}
                except (OSError, ValueError, KeyError, TypeError):
                    settings = {}
                answers = self._with_settings(manifest, answers, settings)
            return self.references.resolve(source, answers)
        if not source.startswith("fn:"):
            return None
        query = FunctionQuery(source)
        function = self.functions.get(query.name)
        if function is None:
            return None
        try:
            settings = dict(self.settings(manifest)) if self.settings is not None else {}
        except (OSError, ValueError, KeyError, TypeError):
            return None
        arguments = query.bind(self._with_settings(manifest, answers, settings))
        if arguments is None:
            return None
        try:
            return list(function(settings, arguments))
        except Exception:  # noqa: BLE001 - a list that cannot be read is "unavailable"
            return None

    @staticmethod
    def _with_settings(
        manifest: WorkflowManifest, answers: Mapping[str, Any], settings: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Answers with this install's settings bound under their own names."""
        merged = dict(answers)
        for field in manifest.parameters:
            if field.scope == "static":
                merged[field.name] = settings.get(field.name)
        return merged

    def values(
        self, manifest: WorkflowManifest, source: str, answers: Mapping[str, Any]
    ) -> list[str] | None:
        found = self.resolve(manifest, source, answers)
        return None if found is None else [item.value for item in found]
