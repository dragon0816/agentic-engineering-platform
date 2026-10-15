"""Files a person uploads into a Workflow's `upload` field (forms v2, 2026-10-15).

Agent Web posts each chosen file and a Telegram flow stores each document
reply here, so a Workflow receives the stored absolute paths as the field's
value. Layout: `<workspace>/workflow-uploads/<set>/<field>/<name>`, where a set
is one form fill or one Telegram flow.

Rules, checked before anything is written: at most `MAX_UPLOAD_BYTES` a file
and `MAX_FILES_PER_FIELD` files a field in one set, the extension must be one
the field accepts (when it declares `accept`), and the name is reduced to a
plain file name. The bytes are data for the Workflow's steps; nothing here
reads or interprets them. The engine refuses an `upload` value outside this
store, so only files that came through here can be uploads.
"""

from __future__ import annotations

import re
import secrets
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from common.assets import WorkflowParameter
from host_runtime.attachments import safe_name
from host_runtime.workspace import write_atomically

UPLOADS_FOLDER = "workflow-uploads"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_FILES_PER_FIELD = 20
#: Sets older than this are removed when a new set starts.
KEEP_DAYS = 30
UPLOAD_SET = re.compile(r"^up-[0-9]{14}-[0-9a-f]{8}$")


class WorkflowUploadError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def accepts(field: WorkflowParameter, filename: str) -> bool:
    """Whether the field takes a file of this name (by its extension)."""
    if not field.accept:
        return True
    suffix = Path(filename).suffix.lower()
    wanted = {
        item.strip().lower() if item.strip().startswith(".") else f".{item.strip().lower()}"
        for item in field.accept
    }
    return suffix in wanted


class WorkflowUploadStore:
    def __init__(self, workspace_root: Path) -> None:
        self.root = workspace_root / UPLOADS_FOLDER

    def new_set(self) -> str:
        """A fresh set id; older sets past `KEEP_DAYS` are pruned first."""
        self.prune()
        return f"up-{datetime.now(UTC):%Y%m%d%H%M%S}-{secrets.token_hex(4)}"

    def prune(self, keep_days: int = KEEP_DAYS) -> None:
        if not self.root.is_dir():
            return
        cutoff = time.time() - keep_days * 86400
        for entry in self.root.iterdir():
            try:
                if UPLOAD_SET.match(entry.name) and entry.stat().st_mtime < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                continue

    def add(self, upload_set: str, field: WorkflowParameter, filename: str, data: bytes) -> Path:
        """Store one file for `field` and return its absolute path."""
        if not UPLOAD_SET.match(upload_set):
            raise WorkflowUploadError("upload_set_invalid")
        if field.kind != "upload" or field.scope != "runtime":
            raise WorkflowUploadError("upload_field_invalid")
        name = safe_name(filename)
        if not accepts(field, name):
            raise WorkflowUploadError("upload_type_not_accepted")
        if len(data) > MAX_UPLOAD_BYTES:
            raise WorkflowUploadError("upload_too_large")
        folder = self.root / upload_set / field.name
        existing = [item for item in folder.iterdir() if item.is_file()] if folder.is_dir() else []
        if field.multiple and len(existing) >= MAX_FILES_PER_FIELD:
            raise WorkflowUploadError("upload_too_many")
        if not field.multiple:
            # One file: a new upload replaces the earlier one.
            for item in existing:
                item.unlink(missing_ok=True)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        stem, suffix = Path(name).stem, Path(name).suffix
        counter = 2
        while path.exists():
            path = folder / f"{stem} ({counter}){suffix}"
            counter += 1
        write_atomically(path, data)
        return path.resolve()

    def contains(self, path: str | Path) -> bool:
        candidate = Path(path)
        try:
            return (
                candidate.is_absolute()
                and candidate.is_file()
                and not candidate.is_symlink()
                and candidate.resolve().is_relative_to(self.root.resolve())
            )
        except OSError:
            return False
