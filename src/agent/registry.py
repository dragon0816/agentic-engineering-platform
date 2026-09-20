"""In-memory control-plane fixture, not an authenticated Registry service."""

from typing import Protocol

from common.assets import AssetIdentity, TaskManifest


class DuplicateAsset(ValueError):
    """A scoped version is already registered; no implicit overwrite."""


class AssetNotFound(LookupError):
    """The requested exact scoped version is absent."""


class TaskRegistry(Protocol):
    def register(self, manifest: TaskManifest) -> None: ...

    def get(self, identity: AssetIdentity) -> TaskManifest: ...

    def discover(
        self,
        *,
        namespace: str | None = None,
        name: str | None = None,
        visibility: str | None = None,
    ) -> tuple[TaskManifest, ...]: ...


class InMemoryTaskRegistry:
    """Stores metadata only. Visibility filters do not enforce authorization."""

    def __init__(self) -> None:
        self._assets: dict[tuple[str, str, str], str] = {}

    def register(self, manifest: TaskManifest) -> None:
        checked = TaskManifest.model_validate(manifest)
        if checked.metadata.lifecycle not in {"validated", "published"}:
            raise ValueError("only validated or published assets may be registered")
        key = checked.metadata.identity.key
        if key in self._assets:
            raise DuplicateAsset(f"asset version already registered: {key}")
        self._assets[key] = checked.model_dump_json()

    def get(self, identity: AssetIdentity) -> TaskManifest:
        checked = AssetIdentity.model_validate(identity)
        try:
            return TaskManifest.model_validate_json(self._assets[checked.key])
        except KeyError:
            raise AssetNotFound(f"asset not found: {checked.key}") from None

    def discover(
        self,
        *,
        namespace: str | None = None,
        name: str | None = None,
        visibility: str | None = None,
    ) -> tuple[TaskManifest, ...]:
        matches = []
        for key in sorted(self._assets):
            task = TaskManifest.model_validate_json(self._assets[key])
            metadata = task.metadata
            if metadata.lifecycle != "published":
                continue
            if namespace is not None and metadata.identity.namespace != namespace:
                continue
            if name is not None and metadata.identity.name != name:
                continue
            if visibility is not None and metadata.visibility != visibility:
                continue
            matches.append(task)
        return tuple(matches)
