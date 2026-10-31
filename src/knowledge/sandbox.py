"""Personal ingest sandboxes over a base vault (K1, owner 2026-10-11).

Several people ingesting into one vault interfere: each rewrite of a shared
page is legal, yet the wiki drifts. So convert, ingest and lint run in a
sandbox: a full copy of a base vault in the person's workspace, recorded with
the base's digests so a later merge (K3) can tell what changed on either side.
A sandbox is discardable; discarding moves it aside and never deletes it.
Nothing here writes to the base vault.

A wiki knowledge repository's working folder (`knowledge.wiki_work`) opens
through the same calls under the id `repo.<repository id>` (R4b), so every
pipeline step runs on it unchanged; it is not listed, recorded or discarded
here, and it has no base vault: its originals are pulled from this PC's
intake folder and its questions read from this PC's question folder.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from knowledge import wiki_repos, wiki_work
from knowledge.evolution import decision_digest, knowledge_digest, raw_digest
from knowledge.merge import ROOT_FILES, TEXT_AREAS
from knowledge.repo.repository import RepoError, Repository
from knowledge.vault import Vault, VaultError

ROOT_NAME = "knowledge-sandboxes"
DISCARDED = ".discarded"
RECORD = "sandbox.json"
#: The id prefix of a wiki repository's working folder (`repo.<id>`).
REPO_PREFIX = "repo."
SCHEMA = "aep.knowledge-sandbox.v1"
# Working state of a base vault that a copy must not inherit.
# `.base` holds the base's wiki and root files as copied, for the three-way merge (K3.3).
BASE = ".base"
# A project vault's drop/ holds every original; a sandbox pulls the folders it
# works on instead (docs/phases/KNOWLEDGE_COLLAB.md section 3).
_SKIPPED = {
    ".ingest-backup",
    ".ingest-snapshot",
    ".plans",
    ".condense-cache",
    ".git",
    RECORD,
    BASE,
    "drop",
}
# Windows refuses longer paths unless long paths are enabled system-wide
# (rs-k has 188-character Raw asset paths; k2 live run, 2026-10-11).
MAX_PATH = 259
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
    # A domain matrix cell (K2 index category) the sandbox works in; changes to
    # pages outside it are merge proposals (K3, owner 2026-10-11).
    domain: str | None = None
    # drop/ folders pulled from the project vault so far.
    pulled: tuple[str, ...] = ()
    # The one folder (e.g. Knowledge or Productions/VNA) this sandbox maintains,
    # chosen at creation: it may pull only below it and edit only its rules
    # (owner, 2026-10-13). None for sandboxes made before scopes existed.
    scope: str | None = None
    # A wiki repository's working folder (R4b): the repository id and this
    # PC's intake and question folders (None while not set).
    repo: str | None = None
    drop_root: str | None = None
    questions_root: str | None = None


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "sandbox"


class Sandboxes:
    """The sandboxes of one workspace, or of a configured shorter folder."""

    def __init__(self, workspace_root: Path, *, root: Path | None = None) -> None:
        self.workspace_root = Path(workspace_root)
        self.root = Path(root) if root is not None else Path(workspace_root) / ROOT_NAME

    def repository(self, sandbox_id: str) -> Repository:
        """The wiki repository behind `repo.<id>`."""
        try:
            return wiki_repos.repository(self.workspace_root, sandbox_id[len(REPO_PREFIX) :])
        except RepoError as failure:
            raise SandboxError(failure.code) from None

    def _repo_info(self, sandbox_id: str, folder: Path) -> SandboxInfo:
        repo = self.repository(sandbox_id)
        chosen = wiki_work.settings(repo)
        return SandboxInfo(
            sandbox_id=sandbox_id,
            base_name=sandbox_id,
            base_root=str(folder),
            base_raw_sha256="",
            base_content_sha256="",
            base_decisions_sha256="",
            label=str(repo.document.get("title") or repo.id),
            created_by=repo.author,
            created_at="",
            pulled=tuple(chosen["pulled"]),
            repo=repo.id,
            drop_root=chosen["intake"],
            questions_root=chosen["questions"],
        )

    def repo_info(self, sandbox_id: str) -> SandboxInfo:
        """A repository's info without building its working folder."""
        repo = self.repository(sandbox_id)
        return self._repo_info(sandbox_id, wiki_work.work_folder(repo))

    def _folder(self, sandbox_id: str) -> Path:
        if not _ID.fullmatch(sandbox_id or ""):
            raise SandboxError("invalid_sandbox_id")
        folder = (self.root / sandbox_id).resolve()
        if folder.parent != self.root.resolve():
            raise SandboxError("invalid_sandbox_id")
        return folder

    def create(
        self,
        base_name: str,
        base_root: Path,
        *,
        label: str,
        actor: str,
        domain: str | None = None,
        scope: str | None = None,
        progress: Callable[[str, int, int, str], None] | None = None,
    ) -> SandboxInfo:
        """Copy the base vault into a new sandbox. `progress(phase, done, total,
        current)` is told how far the copy is, for the page's progress bar."""
        try:
            base = Vault(Path(base_root))
        except VaultError:
            raise SandboxError("base_not_a_vault") from None
        stamp = datetime.now(UTC)
        # Short on purpose: every byte of the id is in every copied path.
        sandbox_id = f"sb-{_slug(label)[:16].strip('-')}-{uuid.uuid4().hex[:6]}"
        folder = self._folder(sandbox_id)
        if progress is not None:
            progress("counting", 0, 0, "counting the project vault's files")
        copied_files = [
            os.path.relpath(os.path.join(d, f), base.root)
            for d, dirs, files in os.walk(base.root)
            if not set(Path(d).relative_to(base.root).parts) & _SKIPPED
            for f in files
            if f not in _SKIPPED
        ]
        longest = max(map(len, copied_files), default=0)
        if os.name == "nt" and len(str(folder)) + 1 + len(BASE) + 1 + longest > MAX_PATH:
            raise SandboxError("path_too_long")
        snapshot_files = sum(
            1
            for area in TEXT_AREAS
            if (base.root / area).is_dir()
            for p in (base.root / area).rglob("*")
            if p.is_file()
        )
        snapshot_files += sum(1 for name in ROOT_FILES if (base.root / name).is_file())
        total = len(copied_files) + snapshot_files
        done = 0

        def copy(source: str, target: str) -> str:
            nonlocal done
            shutil.copy2(source, target)
            done += 1
            if progress is not None and (done % 25 == 0 or done == total):
                progress("copying", done, total, os.path.relpath(source, base.root))
            return target

        if progress is not None:
            progress("copying", 0, total, "")
        self.root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            base.root,
            folder,
            copy_function=copy,
            ignore=lambda _dir, names: [n for n in names if n in _SKIPPED],
        )
        (folder / "drop").mkdir(exist_ok=True)
        for area in TEXT_AREAS:
            if (base.root / area).is_dir():
                shutil.copytree(base.root / area, folder / BASE / area, copy_function=copy)
        for name in ROOT_FILES:
            if (base.root / name).is_file():
                (folder / BASE).mkdir(exist_ok=True)
                copy(str(base.root / name), str(folder / BASE / name))
        if progress is not None:
            progress("checking", total, total, "recording the vault's fingerprint")
        info = SandboxInfo(
            sandbox_id=sandbox_id,
            base_name=base_name,
            base_root=str(base.root.resolve()),
            base_raw_sha256=raw_digest(base),
            base_content_sha256=knowledge_digest(base),
            base_decisions_sha256=decision_digest(base),
            label=label,
            created_by=actor,
            created_at=stamp.isoformat(timespec="seconds"),
            domain=domain,
            scope=scope,
        )
        (folder / RECORD).write_text(info.model_dump_json(indent=1), encoding="utf-8")
        return info

    def record(self, info: SandboxInfo) -> None:
        """Rewrite a sandbox's record, e.g. after a pull."""
        if info.repo is not None:
            repo = self.repository(info.sandbox_id)
            wiki_work.save_settings(repo, {"pulled": list(info.pulled)})
            return
        folder = self._folder(info.sandbox_id)
        if not (folder / RECORD).is_file():
            raise SandboxError("unknown_sandbox")
        (folder / RECORD).write_text(info.model_dump_json(indent=1), encoding="utf-8")

    def list(self) -> tuple[SandboxInfo, ...]:
        if not self.root.is_dir():
            return ()
        found = []
        for folder in sorted(self.root.iterdir()):
            record = folder / RECORD
            if folder.name != DISCARDED and record.is_file():
                found.append(
                    SandboxInfo.model_validate(json.loads(record.read_text(encoding="utf-8")))
                )
        return tuple(found)

    def open(self, sandbox_id: str) -> tuple[SandboxInfo, Vault]:
        if sandbox_id.startswith(REPO_PREFIX):
            try:
                folder = wiki_work.open_work(self.repository(sandbox_id))
            except RepoError as failure:
                raise SandboxError(failure.code) from None
            return self._repo_info(sandbox_id, folder), Vault(folder)
        folder = self._folder(sandbox_id)
        record = folder / RECORD
        if not record.is_file():
            raise SandboxError("unknown_sandbox")
        info = SandboxInfo.model_validate(json.loads(record.read_text(encoding="utf-8")))
        return info, Vault(folder)

    def discard(self, sandbox_id: str) -> None:
        if sandbox_id.startswith(REPO_PREFIX):
            raise SandboxError("repository_not_discarded")  # its 「版本」 area discards changes
        folder = self._folder(sandbox_id)
        if not (folder / RECORD).is_file():
            raise SandboxError("unknown_sandbox")
        target = self.root / DISCARDED
        target.mkdir(exist_ok=True)
        shutil.move(str(folder), str(target / sandbox_id))
