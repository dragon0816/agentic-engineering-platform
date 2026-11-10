"""Bounded, existing-value Workflow edits; no filesystem paths or JSON pointers."""

import os
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, JsonValue, StrictInt, StrictStr, field_validator, model_validator

from common.base import Contract, Sha256

_held = threading.local()


@contextmanager
def candidate_lock(path: Path) -> Iterator[None]:
    """Process/thread admission; the OS releases it when the process exits."""
    key = str(path.resolve())
    held: set[str] = getattr(_held, "paths", set())
    if key in held:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if not stream.tell():
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _held.paths = held | {key}
        try:
            yield
        finally:
            _held.paths = held
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


PathPart = StrictStr | StrictInt
PatchPath = Annotated[tuple[PathPart, ...], Field(min_length=1, max_length=20)]


class PatchOperation(Contract):
    op: Literal["replace", "copy_reference"]
    path: PatchPath
    value: JsonValue = None
    attachment_id: str | None = Field(
        default=None,
        description="Host-issued att-... attachment ID shown as attachment_id in attached-file "
        "metadata; never use a filename or filesystem path.",
    )
    source_path: PatchPath | None = None

    @model_validator(mode="after")
    def operation_fields(self) -> "PatchOperation":
        if self.op == "replace":
            if (
                "value" not in self.model_fields_set
                or self.attachment_id is not None
                or self.source_path is not None
            ):
                raise ValueError("replace requires only value")
        elif "value" in self.model_fields_set or not self.attachment_id or self.source_path is None:
            raise ValueError("copy_reference requires attachment_id and source_path only")
        return self

    @field_validator("path", "source_path")
    @classmethod
    def safe_path(cls, path: tuple[str | int, ...] | None) -> tuple[str | int, ...] | None:
        if path is not None:
            for part in path:
                if isinstance(part, int):
                    if part < 0:
                        raise ValueError("negative index")
                elif (
                    not part
                    or len(part) > 128
                    or part in {".", ".."}
                    or any(char in part for char in ("/", "\\", "\x00"))
                ):
                    raise ValueError("invalid path segment")
        return path


class WorkflowPatchRequest(Contract):
    candidate_id: str = Field(min_length=1, max_length=100)
    base_digest: Sha256
    operations: tuple[PatchOperation, ...] = Field(min_length=1, max_length=20)


def existing(root: JsonValue, path: tuple[str | int, ...]) -> JsonValue:
    value = root
    for part in path:
        if isinstance(value, dict) and isinstance(part, str):
            value = value[part]
        elif isinstance(value, list) and isinstance(part, int):
            value = value[part]
        else:
            raise ValueError("path does not match existing JSON")
    return value


def replace(root: JsonValue, path: tuple[str | int, ...], value: JsonValue) -> None:
    existing(root, path)
    parent = existing(root, path[:-1])
    last = path[-1]
    if isinstance(parent, dict) and isinstance(last, str):
        parent[last] = value
    elif isinstance(parent, list) and isinstance(last, int):
        parent[last] = value
    else:
        raise ValueError("path does not match existing JSON")
