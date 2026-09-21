"""Checkpoint store contract, shared transition rules and a memory reference model.

Not connected to WorkflowEngine. The rules here decide whether a write is
legal; each backend decides how to commit it atomically. No authentication,
payload resolution, policy enforcement or automatic recovery is provided.
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
_ERROR_CODE: TypeAdapter[StoreErrorCode] = TypeAdapter(StoreErrorCode)
_RUN_ID: TypeAdapter[str] = TypeAdapter(RunId)
_KEY: TypeAdapter[str] = TypeAdapter(IdempotencyKey)
# Execution intent: what a keyed resubmission or a continuation must match exactly.
INTENT_FIELDS = ("manifest", "runtime_contract", "intent_sha256", "arguments")
_MUTABLE_FIELDS = {"status", "steps", "revision"}
_STEP_TRANSITIONS = {
    ("never_started", "started"),
    ("started", "started"),
    ("started", "completed"),
}


class CheckpointStoreError(Exception):
    """Sanitized outcome; commit_unknown requires inspection before proceeding."""

    def __init__(self, code: StoreErrorCode) -> None:
        self.code: StoreErrorCode = _ERROR_CODE.validate_python(code)
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


def checked_copy(checkpoint: RunCheckpoint) -> RunCheckpoint:
    """Validated private copy: manifests carry mutable input maps."""
    return RunCheckpoint.model_validate(checkpoint).model_copy(deep=True)


def validate_owner(owner: CheckpointOwner) -> CheckpointOwner:
    return CheckpointOwner.model_validate(owner)


def validate_run_id(run_id: RunId) -> str:
    return _RUN_ID.validate_python(run_id)


def validate_key(key: IdempotencyKey) -> str:
    return _KEY.validate_python(key)


def same_intent(left: RunCheckpoint, right: RunCheckpoint) -> bool:
    return all(getattr(left, field) == getattr(right, field) for field in INTENT_FIELDS)


def check_revision(item: RunCheckpoint, expected: int) -> None:
    if type(expected) is not int or expected < 0 or expected != item.revision:
        raise CheckpointStoreError("conflict")


def check_create(item: RunCheckpoint) -> None:
    """A new run starts at revision 0 with no evidence and no relationships."""
    if (
        item.revision != 0
        or item.resumed_from is not None
        or item.continued_by is not None
        or item.status != "running"
        or any(s.state != "never_started" for s in item.steps)
    ):
        raise CheckpointStoreError("invalid_transition")


def check_replace(old: RunCheckpoint, item: RunCheckpoint, expected_revision: int) -> None:
    """Compare-and-swap on the expected revision, one legal step transition at most."""
    check_revision(old, expected_revision)
    if old.status != "running":
        raise CheckpointStoreError("invalid_transition")
    if old.model_dump(exclude=_MUTABLE_FIELDS) != item.model_dump(exclude=_MUTABLE_FIELDS):
        raise CheckpointStoreError("invalid_transition")
    transitions = 0
    for before, after in zip(old.steps, item.steps, strict=True):
        if before == after:
            continue
        transitions += 1
        if (before.state, after.state) not in _STEP_TRANSITIONS:
            raise CheckpointStoreError("invalid_transition")
    if transitions > 1:
        raise CheckpointStoreError("invalid_transition")


def check_continue(
    parent: RunCheckpoint, child: RunCheckpoint, expected_parent_revision: int
) -> None:
    """The child keeps the completed prefix and the first unresolved step's evidence."""
    if parent.continued_by is not None:
        raise CheckpointStoreError("already_continued")
    check_revision(parent, expected_parent_revision)
    if (
        parent.status != "suspended"
        or child.status != "running"
        or child.revision != 0
        or child.continued_by is not None
        or not same_intent(parent, child)
    ):
        raise CheckpointStoreError("invalid_transition")
    unresolved = False
    for before, after in zip(parent.steps, child.steps, strict=True):
        if before.state == "completed" or not unresolved:
            # A started (uncertain) step stays started until the child itself
            # re-acknowledges it; a completed step is immutable evidence.
            unresolved = unresolved or before.state != "completed"
            if before != after:
                raise CheckpointStoreError("invalid_transition")
        elif after.state != "never_started":
            raise CheckpointStoreError("invalid_transition")


def linked_parent(parent: RunCheckpoint, child: RunCheckpoint) -> RunCheckpoint:
    return parent.model_copy(update={"continued_by": child.run_id, "revision": parent.revision + 1})


_StoreKey = tuple[str, str, str]


def _key(owner: CheckpointOwner, run_id: str) -> _StoreKey:
    return (owner.actor, owner.namespace, run_id)


class MemoryCheckpointStore:
    """Bounded reference model, synchronous calls on one owning thread only.

    Records are scoped by owner, so run identifiers are private to an owner: one
    owner can neither observe nor block another's. Every write commits with one
    assignment. There is no TTL/eviction or deletion API. A new instance starts
    empty; this is not a durable backend.
    """

    def __init__(self, *, capacity: int = 50) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        self._capacity = capacity
        self._runs: dict[_StoreKey, RunCheckpoint] = {}

    def _lookup(self, owner: CheckpointOwner, run_id: str) -> RunCheckpoint | None:
        return self._runs.get(_key(owner, run_id))

    def get(self, owner: CheckpointOwner, run_id: RunId) -> RunCheckpoint | None:
        item = self._lookup(validate_owner(owner), validate_run_id(run_id))
        return item.model_copy(deep=True) if item is not None else None

    def find_key(self, owner: CheckpointOwner, key: IdempotencyKey) -> RunCheckpoint | None:
        item = self._find_key(validate_owner(owner), validate_key(key))
        return item.model_copy(deep=True) if item is not None else None

    def _find_key(self, owner: CheckpointOwner, key: str) -> RunCheckpoint | None:
        return next(
            (r for r in self._runs.values() if r.owner == owner and r.idempotency_key == key),
            None,
        )

    def _room(self, item: RunCheckpoint) -> None:
        if _key(item.owner, item.run_id) in self._runs:
            raise CheckpointStoreError("conflict")
        if len(self._runs) >= self._capacity:
            raise CheckpointStoreError("capacity")

    def create(self, checkpoint: RunCheckpoint) -> RunCheckpoint:
        item = checked_copy(checkpoint)
        check_create(item)
        if item.idempotency_key is not None:
            existing = self._find_key(item.owner, item.idempotency_key)
            if existing is not None:
                if not same_intent(existing, item):
                    raise CheckpointStoreError("key_conflict")
                return existing.model_copy(deep=True)
        self._room(item)
        self._runs[_key(item.owner, item.run_id)] = item
        return item.model_copy(deep=True)

    def replace(self, checkpoint: RunCheckpoint, *, expected_revision: int) -> RunCheckpoint:
        item = checked_copy(checkpoint)
        old = self._lookup(item.owner, item.run_id)
        if old is None:
            raise CheckpointStoreError("missing")
        check_replace(old, item, expected_revision)
        updated = item.model_copy(update={"revision": old.revision + 1})
        self._runs[_key(item.owner, item.run_id)] = updated
        return updated.model_copy(deep=True)

    def continue_run(self, child: RunCheckpoint, *, expected_parent_revision: int) -> RunCheckpoint:
        item = checked_copy(child)
        if item.resumed_from is None:
            raise CheckpointStoreError("invalid_transition")
        parent = self._lookup(item.owner, item.resumed_from)
        if parent is None:
            raise CheckpointStoreError("missing")
        check_continue(parent, item, expected_parent_revision)
        self._room(item)
        self._runs[_key(parent.owner, parent.run_id)] = linked_parent(parent, item)
        self._runs[_key(item.owner, item.run_id)] = item
        return item.model_copy(deep=True)
