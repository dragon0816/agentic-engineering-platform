"""Personal ingest sandboxes over a base vault (K1, owner 2026-10-11).

Several people ingesting into one vault interfere: each rewrite of a shared
page is legal, yet the wiki drifts. So convert, ingest and lint run in a
sandbox: a full copy of a base vault in the person's workspace, recorded with
the base's digests so a later merge (K3) can tell what changed on either side.
A sandbox is discardable; discarding moves it aside and never deletes it.
Nothing here writes to the base vault.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from knowledge.evolution import decision_digest, knowledge_digest, raw_digest
from knowledge.vault import Vault, VaultError

ROOT_NAME = "knowledge-sandboxes"
DISCARDED = ".discarded"
RECORD = "sandbox.json"
SCHEMA = "aep.knowledge-sandbox.v1"
# Working state of a base vault that a copy must not inherit.
_SKIPPED = {".ingest-backup", ".plans", ".condense-cache", RECORD}
_ID = re.compile(r"^sb-[a-z0-9-]{1,80}$")


class SandboxError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SandboxInfo(BaseModel):
    schema_version: str = SCHEMA
    sandbox_id: str
    base_name: str
    base_root: str
    base_raw_sha256: str
    base_content_sha256: str
    base_decisions_sha256: str
    label: str
    created_by: str
    created_at: str


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "sandbox"


class Sandboxes:
    """The sandboxes of one workspace."""

    def __init__(self, workspace_root: Path) -> None:
        self.root = Path(workspace_root) / ROOT_NAME

    def _folder(self, sandbox_id: str) -> Path:
        if not _ID.fullmatch(sandbox_id or ""):
            raise SandboxError("invalid_sandbox_id")
        folder = (self.root / sandbox_id).resolve()
        if folder.parent != self.root.resolve():
            raise SandboxError("invalid_sandbox_id")
        return folder

    def create(self, base_name: str, base_root: Path, *, label: str, actor: str) -> SandboxInfo:
        try:
            base = Vault(Path(base_root))
        except VaultError:
            raise SandboxError("base_not_a_vault") from None
        stamp = datetime.now(UTC)
        sandbox_id = f"sb-{_slug(label)}-{stamp.strftime('%Y%m%dt%H%M%S')}-{uuid.uuid4().hex[:4]}"
        folder = self._folder(sandbox_id)
        self.root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(base.root, folder,
                        ignore=lambda _dir, names: [n for n in names if n in _SKIPPED])
        (folder / "drop").mkdir(exist_ok=True)
        info = SandboxInfo(
            sandbox_id=sandbox_id, base_name=base_name, base_root=str(base.root.resolve()),
            base_raw_sha256=raw_digest(base), base_content_sha256=knowledge_digest(base),
            base_decisions_sha256=decision_digest(base), label=label, created_by=actor,
            created_at=stamp.isoformat(timespec="seconds"))
        (folder / RECORD).write_text(info.model_dump_json(indent=1), encoding="utf-8")
        return info

    def list(self) -> tuple[SandboxInfo, ...]:
        if not self.root.is_dir():
            return ()
        found = []
        for folder in sorted(self.root.iterdir()):
            record = folder / RECORD
            if folder.name != DISCARDED and record.is_file():
                found.append(SandboxInfo.model_validate(json.loads(record.read_text(encoding="utf-8"))))
        return tuple(found)

    def open(self, sandbox_id: str) -> tuple[SandboxInfo, Vault]:
        folder = self._folder(sandbox_id)
        record = folder / RECORD
        if not record.is_file():
            raise SandboxError("unknown_sandbox")
        info = SandboxInfo.model_validate(json.loads(record.read_text(encoding="utf-8")))
        return info, Vault(folder)

    def discard(self, sandbox_id: str) -> None:
        folder = self._folder(sandbox_id)
        if not (folder / RECORD).is_file():
            raise SandboxError("unknown_sandbox")
        target = self.root / DISCARDED
        target.mkdir(exist_ok=True)
        shutil.move(str(folder), str(target / sandbox_id))
