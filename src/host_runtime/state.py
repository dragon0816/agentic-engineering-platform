"""Durable local inventory and run state on one SQLite file.

The Bridge computer owns the authoritative record of what is installed on it
and what has run there; the control plane only projects it. This is that
record: one file, one writer, every write one committed transaction, following
the checkpoint store in `workflow.checkpoints_sqlite`. It holds installed-asset
rows, compact run summaries, conversations and inert contribution drafts; no
artifact bytes, external payload or credential is stored. Every failure surfaces
as a `LocalStateError` with a code and nothing else; no path, record or SQLite
message is echoed.
"""

import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self
from urllib.request import pathname2url

from pydantic import TypeAdapter, ValidationError

from agent.run_state import TaskRunState, task_run_follows
from common.assets import AssetIdentity
from common.base import Symbol
from common.distribution import (
    BridgeStateSnapshot,
    InstallationPlan,
    InstalledAsset,
    LocalRunSummary,
    LocalStateError,
    verify_installation,
)
from common.enrollment import BridgeDevice
from common.sync import FeedbackRecord
from host_runtime.contributions import ContributionDraft
from host_runtime.conversations import MAX_STORED_MESSAGES, ConversationRecord, MessageFeedback
from host_runtime.feedback_sync import feedback_record

# Version 5 adds portable task-run evidence; version 6 the feedback outbox
# (owner 2026-10-08). Tables are additive and every open creates them, so
# older files migrate rather than being refused.
SCHEMA_VERSION = "6"
_MIGRATABLE = frozenset({"1", "2", "3", "4", "5"})
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS local_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS installed ("
    " namespace TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL,"
    " record TEXT NOT NULL, PRIMARY KEY (namespace, name, version))",
    "CREATE TABLE IF NOT EXISTS runs ("
    " run_id TEXT PRIMARY KEY, actor TEXT NOT NULL, updated_at TEXT NOT NULL,"
    " record TEXT NOT NULL)",
    # How far an ingress has consumed its channel. One row per channel, so a
    # restart resumes where the last confirmed batch ended.
    "CREATE TABLE IF NOT EXISTS channel_cursor ("
    " channel TEXT PRIMARY KEY, position INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS conversations ("
    " session_id TEXT PRIMARY KEY, actor TEXT NOT NULL, updated_at TEXT NOT NULL,"
    " record TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS contribution_drafts ("
    " draft_id TEXT PRIMARY KEY, actor TEXT NOT NULL, created_at TEXT NOT NULL,"
    " record TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS task_runs ("
    " task_id TEXT PRIMARY KEY, actor TEXT NOT NULL, updated_at TEXT NOT NULL,"
    " record TEXT NOT NULL)",
    # Ratings waiting for the Shared Platform; one row per rated answer.
    "CREATE TABLE IF NOT EXISTS feedback_outbox ("
    " feedback_id TEXT PRIMARY KEY, rated_at TEXT NOT NULL, attempts INTEGER NOT NULL,"
    " last_error TEXT, record TEXT NOT NULL)",
)
# Commit outcomes SQLite reports as definitely not committed; anything else is ambiguous.
_NOT_COMMITTED = frozenset({"SQLITE_BUSY", "SQLITE_LOCKED"})


class SqliteLocalState:
    """One process, one owning thread, one file, one device. The file records
    which Bridge it belongs to on first open and refuses another, so a state
    file cannot quietly become some other device's inventory. Reads and
    writes share one lock, so a reader never sees the inside of a
    transaction that may yet roll back."""

    def __init__(self, path: Path, *, bridge_id: Symbol, read_only: bool = False) -> None:
        self.bridge_id = TypeAdapter(Symbol).validate_python(bridge_id)
        self._path = Path(path)
        self.read_only = read_only
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        try:
            self._conn = self._connect()
            if read_only:
                self._verify()
            else:
                with self._write() as conn:
                    for statement in _SCHEMA:
                        conn.execute(statement)
                    self._version(conn)
                    self._claim(conn, "bridge_id", self.bridge_id)
        except BaseException as error:
            # Never leak a half-built handle; on Windows it would pin the file.
            self.close()
            # A corrupt or unreadable file is this class's own closed answer,
            # not a SQLite exception escaping into a caller that promised not
            # to echo one.
            if isinstance(error, sqlite3.Error):
                raise LocalStateError("unavailable") from None
            raise

    def _connect(self) -> sqlite3.Connection:
        """A read-only open never creates the file and never writes to it, so
        a report can look without changing what it is looking at."""
        if not self.read_only:
            conn = sqlite3.connect(
                self._path, isolation_level=None, timeout=0, check_same_thread=False
            )
            conn.execute("PRAGMA synchronous=FULL")
            return conn
        if not self._path.is_file():
            raise LocalStateError("unavailable")
        uri = f"file:{pathname2url(str(self._path.resolve()))}?mode=ro"
        return sqlite3.connect(
            uri, uri=True, isolation_level=None, timeout=0, check_same_thread=False
        )

    def _verify(self) -> None:
        """What a read-only open can still insist on: this file belongs to
        this device and its schema is one this code understands."""
        with self._read() as conn:
            marks = dict(conn.execute("SELECT key, value FROM local_meta").fetchall())
        if marks.get("bridge_id") != self.bridge_id:
            raise LocalStateError("unavailable")
        if marks.get("schema_version") not in {SCHEMA_VERSION, *_MIGRATABLE}:
            raise LocalStateError("unavailable")

    @staticmethod
    def _claim(conn: sqlite3.Connection, key: str, value: str) -> None:
        """Write a mark on a fresh file, or insist the existing one matches."""
        row = conn.execute("SELECT value FROM local_meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO local_meta (key, value) VALUES (?, ?)", (key, value))
        elif row[0] != value:
            raise LocalStateError("unavailable")

    @staticmethod
    def _version(conn: sqlite3.Connection) -> None:
        """Mark a fresh file, move a migratable one forward, refuse the rest.
        Every schema change so far has been an added table that every open
        creates, so migrating is only moving the mark."""
        row = conn.execute("SELECT value FROM local_meta WHERE key = 'schema_version'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO local_meta (key, value) VALUES ('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
        elif row[0] in _MIGRATABLE:
            conn.execute(
                "UPDATE local_meta SET value = ? WHERE key = 'schema_version'", (SCHEMA_VERSION,)
            )
        elif row[0] != SCHEMA_VERSION:
            raise LocalStateError("unavailable")

    def close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise LocalStateError("unavailable")
        return self._conn

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """One atomic write. `unavailable` means known not committed;
        `commit_unknown` means the acknowledgment was lost and the caller must
        read back rather than retry blindly. Whatever happens inside, the
        transaction never stays open on the connection."""
        with self._lock:
            if self.read_only:
                raise LocalStateError("unavailable")
            conn = self._connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
            except sqlite3.Error:
                raise LocalStateError("unavailable") from None
            try:
                yield conn
            except BaseException as error:
                self._rollback()
                if isinstance(error, LocalStateError):
                    raise
                if isinstance(error, sqlite3.Error):
                    raise LocalStateError("unavailable") from None
                raise
            try:
                conn.execute("COMMIT")
            except sqlite3.Error as error:
                self._rollback()
                if getattr(error, "sqlite_errorname", "") in _NOT_COMMITTED:
                    raise LocalStateError("unavailable") from None
                # The commit may or may not have reached the file; never guess.
                raise LocalStateError("commit_unknown") from None

    def _rollback(self) -> None:
        try:
            if self._conn is not None and self._conn.in_transaction:
                self._conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        """A read under the same lock as the writes, so it never observes an
        open transaction, and with the same closed vocabulary on failure."""
        with self._lock:
            conn = self._connection()
            try:
                yield conn
            except (sqlite3.Error, ValidationError):
                # A locked file or an undecodable record is unusable evidence;
                # fail closed rather than guess or echo it.
                raise LocalStateError("unavailable") from None

    def installed(self) -> tuple[InstalledAsset, ...]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT record FROM installed ORDER BY namespace, name, version"
            ).fetchall()
            return tuple(InstalledAsset.model_validate_json(row[0]) for row in rows)

    def install(
        self, plan: InstallationPlan, artifacts: Mapping[str, bytes]
    ) -> tuple[InstalledAsset, ...]:
        """Verify the whole plan, then write it in one transaction. The rule
        is `verify_installation`, shared with the in-memory reference."""
        with self._write() as conn:
            present = {
                (row[0], row[1], row[2])
                for row in conn.execute("SELECT namespace, name, version FROM installed")
            }
            added = verify_installation(
                plan, artifacts, bridge_id=self.bridge_id, installed=present
            )
            for item in added:
                conn.execute(
                    "INSERT INTO installed (namespace, name, version, record) VALUES (?, ?, ?, ?)",
                    (*item.identity.key, item.model_dump_json()),
                )
        return added

    def forget(self, identity: AssetIdentity) -> bool:
        """Drop one installed-asset row after its file was taken off this
        computer (Agent Web "Remove from this Agent", owner 2026-10-15), so
        the inventory no longer reports it and a later sync may install it
        again. False when no row named it."""
        with self._write() as conn:
            removed = conn.execute(
                "DELETE FROM installed WHERE namespace = ? AND name = ? AND version = ?",
                identity.key,
            ).rowcount
        return bool(removed)

    def record_run(self, summary: LocalRunSummary) -> LocalRunSummary:
        """A run belongs to the actor who started it for as long as the record
        exists, and a record never moves backwards in time."""
        item = LocalRunSummary.model_validate(summary)
        with self._write() as conn:
            row = conn.execute(
                "SELECT record FROM runs WHERE run_id = ?", (item.run_id,)
            ).fetchone()
            if row is not None:
                stored = LocalRunSummary.model_validate_json(row[0])
                if (stored.actor, stored.on_behalf_of) != (item.actor, item.on_behalf_of):
                    # Who ran it and who asked are both fixed for the life of
                    # the record: a later update may change how it ended and
                    # nothing about whose work it was.
                    raise LocalStateError("run_owner_fixed")
                if item.updated_at < stored.updated_at:
                    raise LocalStateError("run_update_stale")
            # Stored in UTC so the column's text order is chronological
            # whatever offset the caller's clock carried.
            conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, actor, updated_at, record)"
                " VALUES (?, ?, ?, ?)",
                (
                    item.run_id,
                    item.actor,
                    item.updated_at.astimezone(UTC).isoformat(),
                    item.model_dump_json(),
                ),
            )
        return item

    def runs(self) -> tuple[LocalRunSummary, ...]:
        with self._read() as conn:
            rows = conn.execute("SELECT record FROM runs ORDER BY updated_at, run_id").fetchall()
            return tuple(LocalRunSummary.model_validate_json(row[0]) for row in rows)

    def create_task_run(self, record: TaskRunState) -> TaskRunState:
        """Persist only portable progress; the task objective stays with its caller."""
        item = TaskRunState.model_validate(record)
        if (
            item.status != "pending"
            or item.revision != 0
            or item.observations
            or (
                item.completed_steps
                or item.unresolved_requirements
                or item.errors
                or item.artifact_refs
                or item.validation is not None
            )
        ):
            raise LocalStateError("task_update_stale")
        with self._write() as conn:
            if conn.execute(
                "SELECT 1 FROM task_runs WHERE task_id = ?", (item.task_id,)
            ).fetchone():
                raise LocalStateError("task_exists")
            conn.execute(
                "INSERT INTO task_runs (task_id, actor, updated_at, record) VALUES (?, ?, ?, ?)",
                (
                    item.task_id,
                    item.actor,
                    item.updated_at.astimezone(UTC).isoformat(),
                    item.model_dump_json(),
                ),
            )
        return item

    def save_task_run(self, record: TaskRunState) -> TaskRunState:
        item = TaskRunState.model_validate(record)
        with self._write() as conn:
            row = conn.execute(
                "SELECT record FROM task_runs WHERE task_id = ?", (item.task_id,)
            ).fetchone()
            if row is None:
                raise LocalStateError("task_unknown")
            stored = TaskRunState.model_validate_json(row[0])
            if (
                item.actor != stored.actor
                or item.trace != stored.trace
                or item.task_sha256 != stored.task_sha256
                or item.backend_id != stored.backend_id
                or item.created_at != stored.created_at
            ):
                raise LocalStateError("task_owner_fixed")
            if not task_run_follows(stored, item):
                raise LocalStateError("task_update_stale")
            conn.execute(
                "UPDATE task_runs SET updated_at = ?, record = ? WHERE task_id = ?",
                (
                    item.updated_at.astimezone(UTC).isoformat(),
                    item.model_dump_json(),
                    item.task_id,
                ),
            )
        return item

    def task_run(self, task_id: Symbol, actor: Symbol) -> TaskRunState | None:
        with self._read() as conn:
            row = conn.execute(
                "SELECT record FROM task_runs WHERE task_id = ? AND actor = ?",
                (task_id, actor),
            ).fetchone()
            return None if row is None else TaskRunState.model_validate_json(row[0])

    def task_runs(self, actor: Symbol, *, limit: int = 50) -> tuple[TaskRunState, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("task-run limit is between 1 and 100")
        with self._read() as conn:
            rows = conn.execute(
                "SELECT record FROM task_runs WHERE actor = ?"
                " ORDER BY updated_at DESC, task_id LIMIT ?",
                (actor, limit),
            ).fetchall()
            return tuple(TaskRunState.model_validate_json(row[0]) for row in rows)

    def create_conversation(self, record: ConversationRecord) -> ConversationRecord:
        item = ConversationRecord.model_validate(record)
        with self._write() as conn:
            if conn.execute(
                "SELECT 1 FROM conversations WHERE session_id = ?", (item.session_id,)
            ).fetchone():
                raise LocalStateError("conversation_exists")
            conn.execute(
                "INSERT INTO conversations (session_id, actor, updated_at, record)"
                " VALUES (?, ?, ?, ?)",
                (
                    item.session_id,
                    item.actor,
                    item.updated_at.astimezone(UTC).isoformat(),
                    item.model_dump_json(),
                ),
            )
        return item

    def save_conversation(self, record: ConversationRecord) -> ConversationRecord:
        item = ConversationRecord.model_validate(record)
        with self._write() as conn:
            row = conn.execute(
                "SELECT record FROM conversations WHERE session_id = ?", (item.session_id,)
            ).fetchone()
            if row is None:
                raise LocalStateError("conversation_unknown")
            stored = ConversationRecord.model_validate_json(row[0])
            if stored.actor != item.actor:
                raise LocalStateError("conversation_owner_fixed")
            old = stored.messages
            new = item.messages
            appended = len(new) >= len(old) and new[: len(old)] == old
            rolled = (
                len(old) == MAX_STORED_MESSAGES
                and len(new) == MAX_STORED_MESSAGES
                and new[: MAX_STORED_MESSAGES - 2] == old[2:]
            )
            if item.updated_at < stored.updated_at or not (appended or rolled):
                raise LocalStateError("conversation_update_stale")
            conn.execute(
                "UPDATE conversations SET updated_at = ?, record = ? WHERE session_id = ?",
                (
                    item.updated_at.astimezone(UTC).isoformat(),
                    item.model_dump_json(),
                    item.session_id,
                ),
            )
        return item

    def set_message_feedback(
        self,
        session_id: Symbol,
        actor: Symbol,
        message_id: Symbol,
        feedback: MessageFeedback,
        *,
        queue: bool = False,
    ) -> ConversationRecord:
        """Annotate one answer with the user's feedback.

        The transcript stays append-only: only that assistant message's
        `feedback` changes, and the conversation's update time is kept.
        """
        with self._write() as conn:
            row = conn.execute(
                "SELECT record FROM conversations WHERE session_id = ? AND actor = ?",
                (session_id, actor),
            ).fetchone()
            if row is None:
                raise LocalStateError("conversation_unknown")
            stored = ConversationRecord.model_validate_json(row[0])
            target = next((item for item in stored.messages if item.message_id == message_id), None)
            if target is None or target.role != "assistant":
                raise LocalStateError("conversation_message_unknown")
            updated = stored.model_copy(
                update={
                    "messages": tuple(
                        item.model_copy(update={"feedback": feedback})
                        if item.message_id == message_id
                        else item
                        for item in stored.messages
                    )
                }
            )
            checked = ConversationRecord.model_validate(updated.model_dump())
            conn.execute(
                "UPDATE conversations SET record = ? WHERE session_id = ?",
                (checked.model_dump_json(), session_id),
            )
            if queue:
                # In the same transaction: a rating is never kept without
                # its upload, or queued without being kept.
                item = feedback_record(self.bridge_id, checked, message_id)
                conn.execute(
                    "INSERT INTO feedback_outbox (feedback_id, rated_at, attempts, last_error,"
                    " record) VALUES (?, ?, 0, NULL, ?) ON CONFLICT(feedback_id) DO UPDATE SET"
                    " rated_at = excluded.rated_at, attempts = 0, last_error = NULL,"
                    " record = excluded.record",
                    (item.feedback_id, item.rated_at.isoformat(), item.model_dump_json()),
                )
        return checked

    def set_message_card(
        self,
        session_id: Symbol,
        actor: Symbol,
        card: dict[str, Any],
        note: str,
        *,
        workflow_form: dict[str, Any] | None = None,
    ) -> ConversationRecord | None:
        """Redraw an answer's action card after a decision (owner 2026-10-15).

        The transcript stays append-only: only the answer that shows this
        card changes, its `action_card` (or that entry of its `action_cards`)
        and a line added to its tool record so later turns tell the model the
        outcome. `workflow_form` (a Workflow installed from its draft card,
        owner 2026-10-16) is set on that answer when it has none. None when
        no answer here shows the card."""
        card_id = card.get("card_id")
        with self._write() as conn:
            row = conn.execute(
                "SELECT record FROM conversations WHERE session_id = ? AND actor = ?",
                (session_id, actor),
            ).fetchone()
            if row is None:
                return None
            stored = ConversationRecord.model_validate_json(row[0])
            target = next(
                (
                    item
                    for item in stored.messages
                    if item.role == "assistant"
                    and (
                        (
                            isinstance(item.action_card, dict)
                            and item.action_card.get("card_id") == card_id
                        )
                        or any(shown.get("card_id") == card_id for shown in item.action_cards)
                    )
                ),
                None,
            )
            if target is None:
                return None
            summary = ((target.tool_summary + "\n") if target.tool_summary else "") + note
            change: dict[str, Any] = {"tool_summary": summary}
            if (
                isinstance(target.action_card, dict)
                and target.action_card.get("card_id") == card_id
            ):
                change["action_card"] = card
            else:
                change["action_cards"] = tuple(
                    card if shown.get("card_id") == card_id else shown
                    for shown in target.action_cards
                )
            if workflow_form is not None and target.workflow_form is None:
                change["workflow_form"] = workflow_form
            updated = stored.model_copy(
                update={
                    "messages": tuple(
                        item.model_copy(update=change)
                        if item.message_id == target.message_id
                        else item
                        for item in stored.messages
                    )
                }
            )
            checked = ConversationRecord.model_validate(updated.model_dump())
            conn.execute(
                "UPDATE conversations SET record = ? WHERE session_id = ?",
                (checked.model_dump_json(), session_id),
            )
        return checked

    def queued_feedback(self, limit: int) -> list[FeedbackRecord]:
        with self._read() as conn:
            rows = conn.execute(
                "SELECT record FROM feedback_outbox ORDER BY rated_at LIMIT ?", (limit,)
            ).fetchall()
        return [FeedbackRecord.model_validate_json(row[0]) for row in rows]

    def feedback_attempted(self, feedback_ids: list[str], code: str) -> None:
        with self._write() as conn:
            for ident in feedback_ids:
                conn.execute(
                    "UPDATE feedback_outbox SET attempts = attempts + 1, last_error = ?"
                    " WHERE feedback_id = ?",
                    (code[:200], ident),
                )

    def feedback_delivered(self, sent: list[FeedbackRecord], accepted: tuple[str, ...]) -> None:
        """Forget what the platform acknowledged, unless it was rated again
        while on its way."""
        done = set(accepted)
        with self._write() as conn:
            for item in sent:
                if item.feedback_id in done:
                    conn.execute(
                        "DELETE FROM feedback_outbox WHERE feedback_id = ? AND rated_at = ?",
                        (item.feedback_id, item.rated_at.isoformat()),
                    )

    def feedback_backlog(self) -> int:
        with self._read() as conn:
            row = conn.execute("SELECT COUNT(*) FROM feedback_outbox").fetchone()
        return int(row[0])

    def conversation(self, session_id: Symbol, actor: Symbol) -> ConversationRecord | None:
        with self._read() as conn:
            row = conn.execute(
                "SELECT record FROM conversations WHERE session_id = ? AND actor = ?",
                (session_id, actor),
            ).fetchone()
            return None if row is None else ConversationRecord.model_validate_json(row[0])

    def delete_conversation(self, session_id: Symbol, actor: Symbol) -> bool:
        """Delete only this actor's transcript; independent draft evidence is retained."""
        with self._write() as conn:
            deleted = conn.execute(
                "DELETE FROM conversations WHERE session_id = ? AND actor = ?",
                (session_id, actor),
            )
        return deleted.rowcount == 1

    def conversations(self, actor: Symbol, *, limit: int = 50) -> tuple[ConversationRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("conversation limit is between 1 and 100")
        with self._read() as conn:
            rows = conn.execute(
                "SELECT record FROM conversations WHERE actor = ?"
                " ORDER BY updated_at DESC, session_id LIMIT ?",
                (actor, limit),
            ).fetchall()
            return tuple(ConversationRecord.model_validate_json(row[0]) for row in rows)

    def create_contribution_draft(self, draft: ContributionDraft) -> ContributionDraft:
        item = ContributionDraft.model_validate(draft)
        with self._write() as conn:
            if conn.execute(
                "SELECT 1 FROM contribution_drafts WHERE draft_id = ?", (item.draft_id,)
            ).fetchone():
                raise LocalStateError("contribution_exists")
            conn.execute(
                "INSERT INTO contribution_drafts (draft_id, actor, created_at, record)"
                " VALUES (?, ?, ?, ?)",
                (
                    item.draft_id,
                    item.actor,
                    item.created_at.astimezone(UTC).isoformat(),
                    item.model_dump_json(),
                ),
            )
        return item

    def contribution_drafts(
        self, actor: Symbol, *, limit: int = 50
    ) -> tuple[ContributionDraft, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValueError("contribution draft limit is between 1 and 100")
        with self._read() as conn:
            rows = conn.execute(
                "SELECT record FROM contribution_drafts WHERE actor = ?"
                " ORDER BY created_at DESC, draft_id LIMIT ?",
                (actor, limit),
            ).fetchall()
            return tuple(ContributionDraft.model_validate_json(row[0]) for row in rows)

    def cursor(self, channel: Symbol) -> int | None:
        """How far this ingress has consumed its channel, or None if it never
        has. Durable, so a restart resumes instead of replaying."""
        key = TypeAdapter(Symbol).validate_python(channel)
        with self._read() as conn:
            row = conn.execute(
                "SELECT position FROM channel_cursor WHERE channel = ?", (key,)
            ).fetchone()
            return int(row[0]) if row is not None else None

    def advance_cursor(self, channel: Symbol, position: int) -> int:
        """Move a channel's cursor forward. Backwards is refused: a cursor
        that can rewind replays messages that were already acted on."""
        key = TypeAdapter(Symbol).validate_python(channel)
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            raise ValueError("a cursor position is a non-negative integer")
        with self._write() as conn:
            row = conn.execute(
                "SELECT position FROM channel_cursor WHERE channel = ?", (key,)
            ).fetchone()
            if row is not None and position < int(row[0]):
                raise LocalStateError("cursor_rewind")
            conn.execute(
                "INSERT OR REPLACE INTO channel_cursor (channel, position) VALUES (?, ?)",
                (key, position),
            )
        return position

    def snapshot(self, device: BridgeDevice, *, observed_at: datetime) -> BridgeStateSnapshot:
        """The authoritative state the control plane may project. The
        snapshot's own contract refuses a run newer than the observation."""
        return BridgeStateSnapshot(
            device=device,
            observed_at=observed_at,
            installed=self.installed(),
            runs=self.runs(),
        )
