"""Where a parameter's dynamic choices come from: `ref:` sets or `fn:` functions.

`ref:<set>` reads a published reference set (`reference_sets.py`). `fn:<name>`
calls a read-only host function with the Workflow's own per-install settings,
for a choice list that is a property of this install rather than something a
run published: Workflow 14's stations come from the catalogue file its
settings name. Arguments use the same `{field}` placeholders as `ref:` filters:
`fn:ncc_plan.stations?region={region}`.

A function only reads. It gets the settings and the bound arguments, never a
credential, and an error it raises is treated as "not available", which the
engine reports as a rejected run and a form shows as an empty list.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import parse_qsl

from pydantic import JsonValue

from common.assets import WorkflowManifest
from host_runtime.reference_sets import ReferenceItem, ReferenceQuery, ReferenceSetStore

ChoiceFunction = Callable[[Mapping[str, JsonValue], Mapping[str, str]], list[ReferenceItem]]
SettingsProvider = Callable[[WorkflowManifest], Mapping[str, JsonValue]]
_PLACEHOLDER = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")


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
    def needed(source: str) -> tuple[str, ...]:
        if source.startswith("fn:"):
            return FunctionQuery(source).needed()
        return ReferenceQuery(source).needed()

    def resolve(
        self, manifest: WorkflowManifest, source: str, answers: Mapping[str, Any]
    ) -> list[ReferenceItem] | None:
        """The current choices, or None when the source is unavailable or a
        needed earlier answer is missing."""
        if source.startswith("ref:"):
            return self.references.resolve(source, answers)
        if not source.startswith("fn:"):
            return None
        query = FunctionQuery(source)
        function = self.functions.get(query.name)
        arguments = query.bind(answers)
        if function is None or arguments is None:
            return None
        try:
            settings = self.settings(manifest) if self.settings is not None else {}
            return list(function(settings, arguments))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def values(
        self, manifest: WorkflowManifest, source: str, answers: Mapping[str, Any]
    ) -> list[str] | None:
        found = self.resolve(manifest, source, answers)
        return None if found is None else [item.value for item in found]
