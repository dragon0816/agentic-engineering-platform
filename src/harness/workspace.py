"""Workspace confinement and revision evidence for the coding Harness."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath, PureWindowsPath


class WorkspaceRefused(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class BoundedWorkspace:
    def __init__(self, root: str, allowed_paths: tuple[str, ...]) -> None:
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise WorkspaceRefused("workspace_not_directory")
        self._allowed = frozenset(allowed_paths)

    def resolve(self, relative: str) -> Path:
        normalized = PurePosixPath(relative.replace("\\", "/"))
        # Contract validation catches traversal; runtime independently enforces containment.
        if (
            normalized.is_absolute()
            or PureWindowsPath(relative).is_absolute()
            or ".." in normalized.parts
            or relative not in self._allowed
        ):
            raise WorkspaceRefused("path_not_allowed")
        candidate = self.root.joinpath(*normalized.parts).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as error:
            raise WorkspaceRefused("workspace_escape") from error
        return candidate

    def read(self, relative: str) -> bytes | None:
        path = self.resolve(relative)
        if not path.exists():
            return None
        if not path.is_file():
            raise WorkspaceRefused("path_not_file")
        return path.read_bytes()

    def write(self, relative: str, content: str) -> None:
        path = self.resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    def revision(self) -> str:
        digest = hashlib.sha256()
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(self.root).as_posix()
            except ValueError as error:
                raise WorkspaceRefused("workspace_escape") from error
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(resolved.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()
