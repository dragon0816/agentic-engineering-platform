"""Small structural types shared by application composition helpers."""

from collections.abc import Mapping
from typing import Protocol

from control_plane.distribution import PackageRegistry


class RegistryState(Protocol):
    @property
    def packages(self) -> PackageRegistry: ...

    @property
    def artifacts(self) -> Mapping[str, bytes]: ...
