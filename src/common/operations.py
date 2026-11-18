"""Metadata-only operation ownership, independent of payloads and execution backends."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

from common.assets import AssetIdentity
from common.base import Contract, Sha256, Symbol
from common.distribution import LocalStateError
from common.execution import RequestContext, TraceIdentifiers

OperationStatus = Literal["running", "unknown", "completed", "failed"]
OperationFinalStatus = Literal["unknown", "completed", "failed"]


class OperationRecord(Contract):
    operation_id: Symbol
    resource_key: Sha256
    actor: Symbol
    capability: AssetIdentity
    trace: TraceIdentifiers
    status: OperationStatus = "running"
    started_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: AwareDatetime | None = None
    code: Symbol | None = None
    reconciled_by: Symbol | None = None

    @property
    def unresolved(self) -> bool:
        return self.status in {"running", "unknown"}

    @model_validator(mode="after")
    def finality_matches_evidence(self) -> Self:
        if self.status == "running" and (self.finished_at is not None or self.code is not None):
            raise ValueError("a running operation has no final observation")
        if self.status in {"completed", "failed"} and self.finished_at is None:
            raise ValueError("a final operation requires a completion observation")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("operation completion predates start")
        if self.status == "completed" and self.code is not None:
            raise ValueError("completed operation has no failure code")
        if self.reconciled_by is not None and self.unresolved:
            raise ValueError("reconciliation ends an unresolved operation")
        return self


class OperationStore(Protocol):
    def claim_operation(self, record: OperationRecord) -> OperationRecord: ...
    def complete_operation(
        self,
        operation_id: str,
        status: OperationFinalStatus,
        code: str | None = None,
    ) -> OperationRecord: ...
    def mark_operation_unknown(self, operation_id: str) -> OperationRecord: ...
    def operation(self, operation_id: str) -> OperationRecord | None: ...


@dataclass
class OperationObservation:
    store: OperationStore
    context: RequestContext
    capability: AssetIdentity
    operation_id: str | None = None

    def warnings(self) -> tuple[str, ...]:
        return () if self.operation_id is None else (f"operation_id={self.operation_id}",)


_CURRENT: ContextVar[OperationObservation | None] = ContextVar(
    "operation_observation", default=None
)


@contextmanager
def observe_operation(observation: OperationObservation) -> Iterator[None]:
    token = _CURRENT.set(observation)
    try:
        yield
    finally:
        _CURRENT.reset(token)


def current_operation() -> OperationObservation | None:
    return _CURRENT.get()


def completed_record(
    record: OperationRecord,
    status: OperationFinalStatus,
    code: str | None = None,
) -> OperationRecord:
    if not record.unresolved:
        raise LocalStateError("operation_already_final")
    return OperationRecord.model_validate(
        record.model_dump()
        | {
            "status": status,
            "code": code,
            "finished_at": datetime.now(UTC),
        }
    )


def unknown_record(record: OperationRecord) -> OperationRecord:
    # Deadline and worker completion race. Never turn an acknowledged terminal
    # observation back into an unknown one or erase a worker's unknown reason.
    if not record.unresolved or record.finished_at is not None:
        return record
    return OperationRecord.model_validate(
        record.model_dump()
        | {
            "status": "unknown",
            "code": "wait_expired",
        }
    )


class MemoryOperationStore:
    """Library/test default. Company hosts bind their existing durable state."""

    def __init__(self) -> None:
        self._records: dict[str, OperationRecord] = {}
        self._lock = threading.RLock()

    def claim_operation(self, record: OperationRecord) -> OperationRecord:
        item = OperationRecord.model_validate(record)
        if item.status != "running":
            raise LocalStateError("operation_invalid_start")
        with self._lock:
            for previous in self._records.values():
                if previous.resource_key == item.resource_key and previous.unresolved:
                    return previous
            if item.operation_id in self._records:
                raise LocalStateError("operation_exists")
            self._records[item.operation_id] = item
        return item

    def complete_operation(
        self,
        operation_id: str,
        status: OperationFinalStatus,
        code: str | None = None,
    ) -> OperationRecord:
        with self._lock:
            item = self._records.get(operation_id)
            if item is None:
                raise LocalStateError("operation_unknown")
            result = completed_record(item, status, code)
            self._records[operation_id] = result
            return result

    def mark_operation_unknown(self, operation_id: str) -> OperationRecord:
        with self._lock:
            item = self._records.get(operation_id)
            if item is None:
                raise LocalStateError("operation_unknown")
            result = unknown_record(item)
            self._records[operation_id] = result
            return result

    def operation(self, operation_id: str) -> OperationRecord | None:
        with self._lock:
            return self._records.get(operation_id)
