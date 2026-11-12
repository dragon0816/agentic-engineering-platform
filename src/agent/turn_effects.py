"""A side effect happens at most once per turn (Harness gap P0-2, multi-agent Phase 0.5).

A Host-check retry (`checked_turn`) runs the tool loop again, and the model may
call the same write again; a delegated sub-run (multi-agent V1) multiplies that.
The Host therefore records, for one conversation turn, every side-effecting
call that succeeded: a capability whose `CapabilitySpec.side_effect` is not
`read`, a Workflow run, or a Host tool that declares a side effect. A repeat of
the same call (the tool and its canonical arguments) within the turn is not
executed again: the model gets the recorded outcome, marked `replayed`.

The record lives in memory for the turn only, keyed by a digest, never the
arguments. It covers the Host check's retry pass and any conversation or
Workflow run nested under the same turn (a delegated sub-run shares its
parent's record). It records only success: a failed call, a refused call and
one waiting for the person's approval run again when asked, so the existing
failure and approval handling applies.
"""

from __future__ import annotations

import hashlib
import json
from _thread import RLock
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from common.async_lock import ExecutionLock

#: What the model is told about a call that was not executed again.
REPLAY_NOTE = "這個動作在本回合已執行過，未重複執行"
REPLAY_INSTRUCTION = (
    "This call already succeeded earlier in this turn with the same arguments; it was not "
    "executed again and the outcome above is the earlier one. Do not call it again."
)


def effect_key(name: str, arguments: Any) -> str:
    """Identity of a call: the tool and its exact arguments, canonical JSON,
    as a digest held in memory only."""
    canonical = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(f"{name}\0{canonical}".encode()).hexdigest()


def workflow_effect_key(actor: str, manifest: dict[str, Any], arguments: Any) -> str:
    """Install/review provenance changes do not repeat an identical procedure."""
    body = dict(manifest)
    identity = body.pop("metadata")["identity"]
    return effect_key(
        "workflow-run",
        {
            "workflow": identity,
            "manifest": body,
            "arguments": arguments or {},
            "actor": actor,
        },
    )


@dataclass
class TurnEffects:
    """One turn's succeeded side effects and its counts (telemetry: counts only)."""

    calls: dict[str, Any] = field(default_factory=dict)
    workflow_runs: dict[str, Any] = field(default_factory=dict)
    capability_calls: dict[str, Any] = field(default_factory=dict)
    operations: dict[str, Any] = field(default_factory=dict)
    capability_locks: dict[str, ExecutionLock] = field(default_factory=dict, repr=False)
    capability_locks_guard: RLock = field(default_factory=RLock, repr=False)
    operations_lock: RLock = field(default_factory=RLock, repr=False)
    native_calls_lock: RLock = field(default_factory=RLock, repr=False)
    recorded: int = 0
    replayed: int = 0

    def replay_call(self, key: str) -> Any | None:
        found = self.calls.get(key)
        if found is not None:
            self.replayed += 1
        return found

    def record_call(self, key: str, outcome: Any, *, counted: bool = True) -> None:
        """`counted` False: the side effect is already counted (a Workflow
        tool's run is recorded by the run itself as well)."""
        if key not in self.calls:
            self.calls[key] = outcome
            self.recorded += int(counted)

    def replay_run(self, key: str) -> Any | None:
        found = self.workflow_runs.get(key)
        if found is not None:
            self.replayed += 1
        return found

    def record_run(self, key: str, snapshot: Any) -> None:
        if key not in self.workflow_runs:
            self.workflow_runs[key] = snapshot
            self.recorded += 1

    def capability_lock(self, key: str) -> ExecutionLock:
        with self.capability_locks_guard:
            return self.capability_locks.setdefault(key, ExecutionLock(reentrant=False))

    def replay_capability(self, key: str) -> Any | None:
        found = self.capability_calls.get(key)
        if found is not None:
            self.replayed += 1
        return found

    def record_capability(self, key: str, result: Any) -> None:
        # Logical tool/run wrappers count the effect. This receipt also protects
        # nested Workflow steps and calls made through a different Bridge wrapper.
        self.capability_calls.setdefault(key, result)

    def replay_operation(self, key: str) -> Any | None:
        result = self.operations.get(key)
        if result is not None:
            self.replayed += 1
        return result

    def record_operation(self, key: str, result: Any) -> None:
        if key not in self.operations:
            self.operations[key] = result
            self.recorded += 1

    def counts(self) -> dict[str, int]:
        return {"side_effects_recorded": self.recorded, "side_effects_replayed": self.replayed}


_CURRENT: ContextVar[TurnEffects | None] = ContextVar("aep_turn_effects", default=None)


def current() -> TurnEffects | None:
    """The record of the turn being run, if any (none outside a turn)."""
    return _CURRENT.get()


@contextmanager
def use_effects(effects: TurnEffects) -> Iterator[None]:
    """Authenticated native-turn adapters carry receipts across HTTP requests."""
    token = _CURRENT.set(effects)
    try:
        yield
    finally:
        _CURRENT.reset(token)


@contextmanager
def turn_scope() -> Iterator[tuple[TurnEffects, bool]]:
    """The turn's record: a new one for an outer turn, the parent's for a run
    nested under it (a delegated sub-run). Yields the record and whether this
    scope opened it."""
    parent = _CURRENT.get()
    if parent is not None:
        yield parent, False
        return
    effects = TurnEffects()
    token = _CURRENT.set(effects)
    try:
        yield effects, True
    finally:
        _CURRENT.reset(token)
