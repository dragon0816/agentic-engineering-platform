"""Worker-owned completion of explicitly tracked synchronous task handlers."""

import asyncio
import hashlib
import logging
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from capabilities.runtime import CapabilityRefused, CapabilityTaskFailed
from common.distribution import LocalStateError
from common.operations import OperationFinalStatus, OperationRecord, current_operation

T = TypeVar("T")
LOG = logging.getLogger(__name__)


def workspace_resource_key(path: Path) -> str:
    # No path, arguments, stdout or credential is written to the claim table.
    canonical = os.path.normcase(str(path.resolve()))
    return hashlib.sha256(("workspace:" + canonical).encode("utf-8")).hexdigest()


async def run_tracked_thread(resource: Path, work: Callable[[], T]) -> T:
    observation = current_operation()
    if observation is None:
        # Low-level library callers have no Bridge/store context. Company-host
        # invocations always go through BridgeExecutor's observation scope.
        return await asyncio.to_thread(work)
    item = OperationRecord(
        operation_id="operation-" + uuid.uuid4().hex,
        resource_key=workspace_resource_key(resource),
        actor=observation.context.actor,
        capability=observation.capability,
        trace=observation.context.trace,
    )
    observation.operation_id = item.operation_id
    try:
        claimed = observation.store.claim_operation(item)
    except LocalStateError:
        # Even an ambiguous claim acknowledgment forbids starting the worker.
        raise CapabilityRefused("operation_state_unavailable") from None
    observation.operation_id = claimed.operation_id
    if claimed.operation_id != item.operation_id:
        raise CapabilityRefused("operation_in_progress")

    def finish(status: OperationFinalStatus, code: str | None = None) -> None:
        try:
            observation.store.complete_operation(item.operation_id, status, code)
        except LocalStateError:
            # A failed acknowledgment never authorizes replay. The durable row
            # may remain unresolved or already be final after an ambiguous commit.
            raise CapabilityRefused("operation_state_unavailable") from None

    def execute() -> T:
        try:
            result = work()
        except CapabilityTaskFailed as stopped:
            finish("unknown" if stopped.outcome_unknown else "failed", stopped.code)
            raise
        except CapabilityRefused as refused:
            finish("failed", refused.code)
            raise
        except BaseException:
            finish("failed", "handler_error")
            raise
        else:
            finish("completed")
            return result

    try:
        return await asyncio.to_thread(execute)
    except asyncio.CancelledError:
        # Cancelling this await cannot terminate its thread. The real worker
        # alone acknowledges completion; there is no lease/TTL-based release.
        try:
            observation.store.mark_operation_unknown(item.operation_id)
        except LocalStateError:
            LOG.warning("operation wait expired and its state acknowledgment was unavailable")
        raise
