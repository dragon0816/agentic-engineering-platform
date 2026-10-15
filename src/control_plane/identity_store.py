"""Small SQLite JSON-record storage for Shared Platform identity state."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from common.base import Contract

TABLES = frozenset(
    {
        "identity_invitations",
        "identity_users",
        "identity_devices",
        "identity_advertisements",
        "identity_bindings",
        "identity_access_tokens",
        "identity_invitation_proofs",
        "identity_member_logins",
        "identity_member_sessions",
        "authorization_selections",
        # Platform overview (owner 2026-10-15): additive tables.
        "identity_user_changes",
        "bridge_activity",
    }
)


class SqliteIdentityStorage:
    """Independent identity tables sharing the Registry's SQLite file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            for table in sorted(TABLES):
                connection.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} "  # noqa: S608 - allowlisted above
                    "(record_key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @staticmethod
    def _table(table: str) -> str:
        if table not in TABLES:
            raise ValueError("unknown identity table")
        return table

    def records(self, table: str) -> tuple[str, ...]:
        checked = self._table(table)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT payload FROM {checked} ORDER BY record_key"  # noqa: S608
            ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def put(self, table: str, key: str, value: Contract) -> None:
        self.put_many(table, ((key, value),))

    def put_many(self, table: str, records: tuple[tuple[str, Contract], ...]) -> None:
        """Atomically replace one or more records in an allowlisted table."""
        checked = self._table(table)
        payloads = tuple((key, value.model_dump_json()) for key, value in records)
        if not payloads:
            return
        with self._connect() as connection:
            connection.executemany(
                f"INSERT INTO {checked}(record_key, payload) VALUES (?, ?) "  # noqa: S608
                "ON CONFLICT(record_key) DO UPDATE SET payload = excluded.payload",
                payloads,
            )
