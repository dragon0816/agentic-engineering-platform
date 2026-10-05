"""Published reference sets: the choice lists behind `ref:<set>` parameters.

rs_workflow_system let one workflow publish a snapshot (for example Workflow
12's chipsets and package versions) that another workflow's form offered as
choices. Here a set is a named list of `{value, label, tags}` kept in this
install's local SQLite file (owner decision 2026-10-05). `tags` let a choice
source filter by an earlier answer: `ref:packageVersions?chipset={chipset}`
keeps the items whose `chipset` tag equals that answer.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from pydantic import Field

from common.assets import RegistryContract
from common.base import Symbol, Text

REFERENCE_SETS_FILE = "reference-sets.sqlite"
MAX_ITEMS = 5000
_PLACEHOLDER = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")


class ReferenceItem(RegistryContract):
    value: Text
    label: Text | None = None
    tags: dict[Symbol, Text] = Field(default_factory=dict)


class ReferenceSet(RegistryContract):
    name: Symbol
    items: tuple[ReferenceItem, ...] = Field(max_length=MAX_ITEMS)
    published_by: Text
    published_at: datetime


class ReferenceQuery:
    """A parsed `ref:` choice source: the set name and its tag filters."""

    def __init__(self, source: str) -> None:
        if not source.startswith("ref:"):
            raise ValueError("not a ref: choice source")
        name, _, query = source[4:].partition("?")
        self.name = name
        self.filters = dict(parse_qsl(query, keep_blank_values=True))

    def needed(self) -> tuple[str, ...]:
        """Earlier answers the filters wait for."""
        return tuple(
            match.group(1)
            for value in self.filters.values()
            if (match := _PLACEHOLDER.match(value)) is not None
        )

    def select(
        self, items: Iterable[ReferenceItem], answers: Mapping[str, Any]
    ) -> list[ReferenceItem] | None:
        """Matching items, or None while a needed answer is still missing."""
        wanted: dict[str, str] = {}
        for tag, value in self.filters.items():
            match = _PLACEHOLDER.match(value)
            if match is None:
                wanted[tag] = value
                continue
            answer = answers.get(match.group(1))
            if answer in (None, ""):
                return None
            wanted[tag] = str(answer)
        return [
            item for item in items
            if all(item.tags.get(tag) == value for tag, value in wanted.items())
        ]


class ReferenceSetStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS reference_sets ("
            " name TEXT PRIMARY KEY, record TEXT NOT NULL)"
        )
        return connection

    def publish(self, reference_set: ReferenceSet) -> ReferenceSet:
        checked = ReferenceSet.model_validate(reference_set)
        with self._lock:
            connection = self._connect()
            try:
                with connection:
                    connection.execute(
                        "INSERT INTO reference_sets (name, record) VALUES (?, ?)"
                        " ON CONFLICT(name) DO UPDATE SET record = excluded.record",
                        (checked.name, checked.model_dump_json()),
                    )
            finally:
                connection.close()
        return checked

    def get(self, name: str) -> ReferenceSet | None:
        if not self.path.exists():
            return None
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT record FROM reference_sets WHERE name = ?", (name,)
                ).fetchone()
            finally:
                connection.close()
        return None if row is None else ReferenceSet.model_validate_json(row[0])

    def resolve(
        self, source: str, answers: Mapping[str, Any]
    ) -> list[ReferenceItem] | None:
        """The current choices for a `ref:` source, or None if the set was never
        published or a needed earlier answer is missing."""
        query = ReferenceQuery(source)
        found = self.get(query.name)
        if found is None:
            return None
        return query.select(found.items, answers)


def publish_values(
    store: ReferenceSetStore, name: str, values: Iterable[Any], *, published_by: str,
) -> ReferenceSet:
    """Publish plain strings or `{value, label, tags}` mappings as one set."""
    items = [
        ReferenceItem(value=item) if isinstance(item, str) else ReferenceItem.model_validate(item)
        for item in values
    ]
    return store.publish(ReferenceSet(
        name=name, items=tuple(items), published_by=published_by,
        published_at=datetime.now(UTC),
    ))


def as_json(items: list[ReferenceItem]) -> list[dict[str, Any]]:
    return [json.loads(item.model_dump_json()) for item in items]
