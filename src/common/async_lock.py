"""Async execution serialization shared by independent native HTTP event loops."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from concurrent.futures import Future
from contextlib import asynccontextmanager
from contextvars import ContextVar


class ExecutionLock:
    """No thread mutex is held across await; nested Workflow steps share a lease.

    A non-reentrant instance protects a receipt even within an existing workflow
    lease. Cancellation of a waiter never cancels another caller's execution.
    """

    def __init__(self, *, reentrant: bool = True) -> None:
        self.reentrant = reentrant
        self._state = threading.Lock()
        self._owner: object | None = None
        self._lease: ContextVar[object | None] = ContextVar("execution_lease", default=None)
        self._waiters: list[Future[None]] = []

    @asynccontextmanager
    async def hold(self) -> AsyncIterator[None]:
        inherited = self._lease.get()
        with self._state:
            nested = self.reentrant and inherited is not None and self._owner is inherited
        if nested:
            yield
            return
        while True:
            with self._state:
                if self._owner is None:
                    lease = object()
                    self._owner = lease
                    break
                waiting: Future[None] = Future()
                self._waiters.append(waiting)
            await asyncio.shield(asyncio.wrap_future(waiting))
        token = self._lease.set(lease)
        try:
            yield
        finally:
            self._lease.reset(token)
            with self._state:
                self._owner = None
                waiters, self._waiters = self._waiters, []
            for waiting in waiters:
                if not waiting.done():
                    waiting.set_result(None)
