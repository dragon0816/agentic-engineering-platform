"""Exact backend selection; eligibility is supplied by policy, never inferred."""

from collections.abc import Collection, Iterable
from typing import Generic, TypeVar

from agent.backend_contracts import ExecutionBackend

RequestT = TypeVar("RequestT")
ResultT = TypeVar("ResultT")


class BackendSelectionError(ValueError):
    def __init__(self, code: str, backend_id: str) -> None:
        self.code = code
        self.backend_id = backend_id
        super().__init__(f"{code}: {backend_id}")


class BackendRouter(Generic[RequestT, ResultT]):
    """Select one exact registered backend; never silently fall back."""

    def __init__(self, backends: Iterable[ExecutionBackend[RequestT, ResultT]]) -> None:
        self._backends: dict[str, ExecutionBackend[RequestT, ResultT]] = {}
        for backend in backends:
            backend_id = backend.profile.backend_id
            if backend_id in self._backends:
                raise ValueError(f"duplicate backend: {backend_id}")
            self._backends[backend_id] = backend

    def select(
        self, backend_id: str, *, eligible_ids: Collection[str]
    ) -> ExecutionBackend[RequestT, ResultT]:
        backend = self._backends.get(backend_id)
        if backend is None:
            raise BackendSelectionError("not_registered", backend_id)
        if backend_id not in eligible_ids:
            raise BackendSelectionError("not_eligible", backend_id)
        health = backend.health()
        if health.backend_id != backend_id:
            raise BackendSelectionError("health_mismatch", backend_id)
        if health.state == "unavailable":
            raise BackendSelectionError("unavailable", backend_id)
        return backend
