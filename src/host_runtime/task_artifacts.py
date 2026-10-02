"""Exclusive local answer artifacts for explicitly submitted Agent tasks."""

from pathlib import Path

from pydantic import TypeAdapter

from common.base import Symbol


class LocalTaskArtifacts:
    """The Host writes and rereads actual bytes; backend claims are insufficient."""

    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root.resolve() / "task-artifacts"

    def _path(self, artifact_ref: str) -> Path:
        name = TypeAdapter(Symbol).validate_python(artifact_ref)
        if self.root.is_symlink():
            raise ValueError("task artifact directory cannot be a symlink")
        return self.root / name

    def write(self, artifact_ref: str, content: bytes) -> None:
        path = self._path(artifact_ref)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("task artifact directory cannot be a symlink")
        with path.open("xb") as output:
            output.write(content)

    def read(self, artifact_ref: str) -> bytes | None:
        path = self._path(artifact_ref)
        if path.is_symlink():
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None
