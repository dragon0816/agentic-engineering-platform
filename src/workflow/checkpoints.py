"""Checkpoint store contract and single-writer memory reference model.

Not connected to WorkflowEngine. No disk durability, authentication, payload
resolution, policy enforcement or automatic recovery is provided here.
"""

from typing import Literal, Protocol

from pydantic import TypeAdapter

from common.checkpoints import CheckpointOwner, RunCheckpoint
from common.execution import IdempotencyKey, RunId

StoreErrorCode = Literal[
    "conflict",
    "missing",
    "capacity",
    "invalid_transition",
    "key_conflict",
    "already_continued",
    "unavailable",
    "commit_unknown",
]


class CheckpointStoreError(Exception):
    """Sanitized outcome; commit_unknown requires inspection before proceeding."""

    def __init__(self, code: StoreErrorCode) -> None:
        self.code: StoreErrorCode = TypeAdapter(StoreErrorCode).validate_python(code)
        super().__init__(self.code)


class CheckpointStore(Protocol):
    """Trusted single-writer seam. Durable implementations acknowledge only after
    atomic commit. Reads are owner-scoped; writes require a trusted coordinator.
    See docs/WORKFLOW_CHECKPOINTS.md for compatibility and retention obligations.
    """

    def get(self, owner: CheckpointOwner, run_id: RunId) -> RunCheckpoint | None: ...

    def find_key(self, owner: CheckpointOwner, key: IdempotencyKey) -> RunCheckpoint | None: ...

    def create(self, checkpoint: RunCheckpoint) -> RunCheckpoint: ...

    def replace(self, checkpoint: RunCheckpoint, *, expected_revision: int) -> RunCheckpoint: ...

    def continue_run(
        self, child: RunCheckpoint, *, expected_parent_revision: int
    ) -> RunCheckpoint: ...


def _checked(checkpoint: RunCheckpoint) -> RunCheckpoint:
    return RunCheckpoint.model_validate(checkpoint).model_copy(deep=True)


class MemoryCheckpointStore:
    """Bounded reference model, synchronous calls on one owning thread only.

    One aggregate assignment commits all relationships. There is no TTL/eviction
    or deletion API. A new instance starts empty; this is not a durable backend.
    """

    def __init__(self, *, capacity: int = 50) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._runs: dict[str, RunCheckpoint] = {}

    def get(self, owner: CheckpointOwner, run_id: RunId) -> RunCheckpoint | None:
        owner = CheckpointOwner.model_validate(owner)
        run_id = TypeAdapter(RunId).validate_python(run_id)
        item = self._runs.get(run_id)
        return _checked(item) if item is not None and item.owner == owner else None

    def find_key(self, owner: CheckpointOwner, key: IdempotencyKey) -> RunCheckpoint | None:
        owner = CheckpointOwner.model_validate(owner)
        key = TypeAdapter(IdempotencyKey).validate_python(key)
        return next(
            (
                _checked(r)
                for r in self._runs.values()
                if r.owner == owner and r.idempotency_key == key
            ),
            None,
        )

    def _room(self, item: RunCheckpoint) -> None:
        if item.run_id in self._runs:
            raise CheckpointStoreError("conflict")
        if len(self._runs) >= self._capacity:
            raise CheckpointStoreError("capacity")

    def create(self, checkpoint: RunCheckpoint) -> RunCheckpoint:
        item = _checked(checkpoint)
        if (
            item.revision != 0
            or item.resumed_from is not None
            or item.continued_by is not None
            or item.status != "running"
            or any(s.state != "never_started" for s in item.steps)
        ):
            raise CheckpointStoreError("invalid_transition")
        if item.idempotency_key is not None:
            existing = self.find_key(item.owner, item.idempotency_key)
            if existing is not None:
                if existing.intent_sha256 != item.intent_sha256:
                    raise CheckpointStoreError("key_conflict")
                return existing
        self._room(item)
        self._runs = {**self._runs, item.run_id: item}
        return _checked(item)

    def replace(self, checkpoint: RunCheckpoint, *, expected_revision: int) -> RunCheckpoint:
        item = _checked(checkpoint)
        old = self.get(item.owner, item.run_id)
        if old is None:
            raise CheckpointStoreError("missing")
        self._revision(old, expected_revision)
        if item.revision != expected_revision:
            raise CheckpointStoreError("conflict")
        mutable = {"status", "steps", "revision"}
        if old.model_dump(exclude=mutable) != item.model_dump(exclude=mutable):
            raise CheckpointStoreError("invalid_transition")
        if old.status != "running" or old.continued_by is not None:
            raise CheckpointStoreError("invalid_transition")
        transitions = 0
        for before, after in zip(old.steps, item.steps, strict=True):
            if before == after:
                continue
            transitions += 1
            if (before.state, after.state) not in {
                ("never_started", "started"),
                ("started", "started"),
                ("started", "completed"),
            }:
                raise CheckpointStoreError("invalid_transition")
        if transitions > 1:
            raise CheckpointStoreError("invalid_transition")
        updated = RunCheckpoint.model_validate({**item.model_dump(), "revision": old.revision + 1})
        self._runs = {**self._runs, updated.run_id: updated}
        return _checked(updated)

    @staticmethod
    def _revision(item: RunCheckpoint, expected: int) -> None:
        if type(expected) is not int or expected < 0 or expected != item.revision:
            raise CheckpointStoreError("conflict")

    def continue_run(self, child: RunCheckpoint, *, expected_parent_revision: int) -> RunCheckpoint:
        item = _checked(child)
        if item.resumed_from is None:
            raise CheckpointStoreError("invalid_transition")
        parent = self.get(item.owner, item.resumed_from)
        if parent is None:
            raise CheckpointStoreError("missing")
        if parent.continued_by is not None:
            raise CheckpointStoreError("already_continued")
        self._revision(parent, expected_parent_revision)
        if (
            parent.status != "suspended"
            or item.status != "running"
            or item.revision != 0
            or item.continued_by is not None
            or any(
                getattr(parent, f) != getattr(item, f)
                for f in ("manifest", "runtime_contract", "intent_sha256", "arguments")
            )
        ):
            raise CheckpointStoreError("invalid_transition")
        for before, after in zip(parent.steps, item.steps, strict=True):
            if before.state == "completed":
                if before != after:
                    raise CheckpointStoreError("invalid_transition")
            elif after.state != "never_started":
                raise CheckpointStoreError("invalid_transition")
        self._room(item)
        linked = RunCheckpoint.model_validate(
            {
                **parent.model_dump(),
                "continued_by": item.run_id,
                "revision": parent.revision + 1,
            }
        )
        self._runs = {**self._runs, parent.run_id: linked, item.run_id: item}
        return _checked(item)
