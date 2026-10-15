"""The server side of an action card: one pending record per card (owner 2026-10-15).

A card's buttons decide nothing by themselves: the record here does. It has
an id, a status, when it was made and when it expires. A handler (change
proposals now, agent-mode permissions next) subclasses `PendingRecord` with
what it needs and keeps its records in one `CardStore` file under the
workspace. The store is small and synchronous: one JSON file written whole,
the newest `keep` records kept, a lock a handler holds while it checks and
decides a record so that two presses never both act.

See `common/action_cards.py` for the card a record is drawn as.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import Field

from common.action_cards import CARD_ID
from common.base import Contract, Symbol

REPLACE_ATTEMPTS = 6


class PendingRecord(Contract):
    """What every card's record has; a handler adds its own fields."""

    card_id: str = Field(pattern=rf"^{CARD_ID}$")
    status: Symbol = "pending"
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None = None


Record = TypeVar("Record", bound=PendingRecord)


def new_card_id(prefix: str) -> str:
    """`<prefix>-` and twelve random hex digits; `prefix` is two letters."""
    if len(prefix) != 2 or not prefix.isalpha() or not prefix.islower():
        raise ValueError("a card id prefix is two lower-case letters")
    return f"{prefix}-{secrets.token_hex(6)}"


class CardStore(Generic[Record]):
    """Pending records of one kind, persisted so a restart keeps them."""

    def __init__(
        self,
        path: Path,
        model: type[Record],
        *,
        keep: int = 200,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self.model = model
        self.keep = keep
        self.clock = clock if clock is not None else (lambda: datetime.now(UTC))
        # Held by a handler around check-and-decide; re-entrant for `put`.
        self.lock = threading.RLock()
        self._records: dict[str, Record] = {}
        if path.is_file():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                for item in stored if isinstance(stored, list) else []:
                    record = model.model_validate(item)
                    self._records[record.card_id] = record
            except (OSError, ValueError):
                self._records = {}

    def now(self) -> datetime:
        return self.clock()

    def get(self, card_id: str) -> Record | None:
        with self.lock:
            return self._records.get(card_id)

    def records(self) -> list[Record]:
        with self.lock:
            return list(self._records.values())

    def put(self, record: Record) -> Record:
        with self.lock:
            self._records[record.card_id] = record
            self._save()
        return record

    def expired(self, record: Record) -> bool:
        """A pending record past its expiry; the handler records the change."""
        return record.status == "pending" and self.now() >= record.expires_at

    def _save(self) -> None:
        newest = sorted(self._records.values(), key=lambda item: item.created_at, reverse=True)[
            : self.keep
        ]
        self._records = {item.card_id: item for item in newest}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        text = json.dumps(
            [item.model_dump(mode="json") for item in newest], ensure_ascii=False, indent=1
        )
        # A scanner may hold the file for a moment on Windows; the record
        # stays in memory if it still cannot be written.
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                temporary.write_text(text, encoding="utf-8")
                temporary.replace(self.path)
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
