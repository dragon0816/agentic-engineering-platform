"""Subscribed BI datasets: read-only copies of datasets shared through the
Shared Platform (BI dataset sharing slice 1, owner 2026-10-22;
`docs/proposals/BI_DATASET_SHARING.md` §4, §8.5, §8.6).

A subscription is the platform's selection of one exact `bi_dataset` version
for this computer's Bridge; the verified sync installs it here:

    <workspace>/bi/subscribed/<namespace>__<name>/
        subscription.json        what is installed and what the platform said
        <version>/bi.sqlite      the installed snapshot, opened read only
        <version>/snapshot.json  the snapshot's manifest

Only the installed version is kept (§8.6: no pinning or rollback in this
slice). A newer version the person may use is never installed by itself: it
is recorded as `latest` and shown as `update_available` until the person
presses 「更新」. When the platform answers and the dataset is no longer among
what this member may use, the copy is kept, readable, and marked
`stopped_no_access` (owner Q2: keep it, stop updating it). When the platform
does not answer, nothing changes except the `offline` status: unreachable is
never treated as revoked.

Installing verifies everything before the first write and is all or nothing:
the artifact's digest, the snapshot itself (`snapshot.read_snapshot`), its
identity, and its schema. A schema not on this PC is installed from the
snapshot; the same id@version with different content is `schema_conflict`
and nothing is written.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aep_bi.cards import catalog, schema_versions
from aep_bi.cards import snapshot as snapshots
from aep_bi.cards.snapshot import Snapshot
from aep_bi.cards.store import (
    DB_FILE,
    SUBSCRIBED_RE,
    SUBSCRIPTION_FILE,
    BiStore,
    subscribed_datasets,
    subscribed_root,
    subscription_record,
)

KIND = "bi_dataset"
STATUSES = ("current", "update_available", "stopped_no_access", "offline")
STATUS_TEXT = {
    "current": "已是最新版本",
    "update_available": "有新版本",
    "stopped_no_access": "已停止更新（無權限）",
    "offline": "無法連線平台",
}


class SubscriptionError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else -1 for part in str(version).split("."))


def dataset_name(namespace: str, name: str) -> str:
    return f"{namespace}/{name}"


def split(dataset: str) -> tuple[str, str]:
    match = SUBSCRIBED_RE.match(str(dataset or ""))
    if match is None:
        raise SubscriptionError("dataset_invalid", "訂閱的資料集名稱是 <namespace>/<name>")
    namespace, name = match.groups()
    return namespace, name


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    schema_versions.replace(temporary, path)


def write_record(workspace: Path, dataset: str, record: dict[str, Any]) -> None:
    _write_json(subscribed_root(workspace, dataset) / SUBSCRIPTION_FILE, record)


# -- installing a snapshot ------------------------------------------------


@dataclass
class PreparedInstall:
    """Everything an install will write, checked and not yet written.
    `commit` writes it; `rollback` takes back what `commit` wrote."""

    workspace: Path
    dataset: str
    version: str
    sha256: str
    snapshot: Snapshot
    record: dict[str, Any]
    #: The snapshot's schema is not on this PC and is installed with it.
    install_schema: bool
    already: bool = False
    _written: list[Path] = field(default_factory=list)
    _previous_record: dict[str, Any] | None = None
    _committed: bool = False

    def commit(self) -> None:
        if self.already:
            return
        root = subscribed_root(self.workspace, self.dataset)
        target = root / self.version
        staging = root / f".{self.version}.{uuid.uuid4().hex[:8]}.tmp"
        self._previous_record = subscription_record(self.workspace, self.dataset)
        try:
            if self.install_schema:
                path = catalog.schema_path(
                    self.workspace, self.snapshot.schema_id, self.snapshot.schema_version
                )
                existed = path.exists()
                snapshots.install_schema(self.snapshot, self.workspace)
                if not existed:
                    self._written.append(path)
            root.mkdir(parents=True, exist_ok=True)
            snapshots.install_snapshot(self.snapshot, staging)
            if target.exists():
                shutil.rmtree(target)
            schema_versions.replace(staging, target)
            self._written.append(target)
            write_record(self.workspace, self.dataset, self.record)
            self._committed = True
        except BaseException as failure:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            self.rollback()
            if isinstance(failure, snapshots.SnapshotError):
                raise SubscriptionError(failure.code, failure.message) from None
            raise
        # Only the installed version is kept (§8.6: no pinning or rollback).
        for other in root.iterdir():
            if other.is_dir() and other.name != self.version and not other.name.startswith("."):
                shutil.rmtree(other, ignore_errors=True)

    def rollback(self) -> None:
        for path in reversed(self._written):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink()
        self._written.clear()
        if self._committed or self._previous_record is not None:
            record = subscribed_root(self.workspace, self.dataset) / SUBSCRIPTION_FILE
            if self._previous_record is not None:
                write_record(self.workspace, self.dataset, self._previous_record)
            elif record.exists():
                record.unlink()
        self._committed = False


def _schema_check(workspace: Path, snapshot: Snapshot) -> bool:
    """Whether the snapshot's schema must be installed with it. Raises
    `schema_conflict` (same id@version here, other content) and
    `schema_unavailable` (a shipped schema this AEP does not have)."""
    state = snapshots.schema_state(snapshot, workspace)
    ref = snapshot.schema_ref
    if state == "conflict":
        raise SubscriptionError(
            "schema_conflict",
            f"這台電腦已有 schema {ref}，但內容不同。同一個 schema 版本有兩種內容，"
            "請發佈者換 schema 版本號",
        )
    if state == "unavailable":
        raise SubscriptionError(
            "schema_unavailable",
            f"這份資料集使用的 schema {ref} 不在這個版本的 AEP 裡，請先更新 AEP",
        )
    return state == "missing"


def prepare(
    workspace: Path,
    namespace: str,
    name: str,
    version: str,
    raw: bytes,
    sha256: str,
) -> PreparedInstall:
    """Check one `bi_dataset` artifact for install; nothing is written."""
    dataset = dataset_name(namespace, name)
    split(dataset)
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise SubscriptionError("artifact_hash_mismatch", "快照內容與它的 digest 不符")
    try:
        snapshot = snapshots.read_snapshot(raw)
    except snapshots.SnapshotError as error:
        raise SubscriptionError(error.code, f"快照無法讀取或不正確（{error.code}）") from None
    publication = snapshot.publication
    if publication is None or (publication.namespace, publication.name, publication.version) != (
        namespace,
        name,
        version,
    ):
        raise SubscriptionError("snapshot_invalid", "快照的名稱或版本與平台上的不同")
    install_schema = _schema_check(workspace, snapshot)
    current = subscription_record(workspace, dataset)
    already = False
    if current is not None and current.get("version") == version:
        if current.get("sha256") != sha256:
            raise SubscriptionError("asset_conflict", f"{dataset}@{version} 已經安裝，而且內容不同")
        already = (subscribed_root(workspace, dataset) / version / DB_FILE).is_file()
    record: dict[str, Any] = dict(current or {})
    record.update(
        {
            "dataset": dataset,
            "namespace": namespace,
            "name": name,
            "version": version,
            "sha256": sha256,
            "digest": snapshot.digest,
            "published_by": publication.published_by or "",
            "published_at": publication.published_at or "",
            "note": publication.note or "",
            "schema": snapshot.schema_ref,
            "installed_at": record.get("installed_at") if already else _now(),
        }
    )
    latest = record.get("latest")
    if not isinstance(latest, dict) or version_key(str(latest.get("version"))) <= version_key(
        version
    ):
        record["latest"] = None
    return PreparedInstall(
        workspace=workspace,
        dataset=dataset,
        version=version,
        sha256=sha256,
        snapshot=snapshot,
        record=record,
        install_schema=install_schema,
        already=already,
    )


def install(
    workspace: Path, namespace: str, name: str, version: str, raw: bytes, sha256: str
) -> dict[str, Any]:
    """Check and install one snapshot; idempotent for the same version and digest."""
    prepared = prepare(workspace, namespace, name, version, raw, sha256)
    prepared.commit()
    return {
        "ok": True,
        "dataset": prepared.dataset,
        "version": version,
        "already": prepared.already,
    }


# -- what the platform says ------------------------------------------------


@dataclass(frozen=True)
class Offer:
    """One `bi_dataset` version this member may use, from the catalog."""

    namespace: str
    name: str
    version: str
    description: str = ""
    owner: str = ""

    @property
    def dataset(self) -> str:
        return dataset_name(self.namespace, self.name)


def observe(workspace: Path, offers: Iterable[Offer] | None) -> None:
    """Record what the platform's catalog said about every subscription.

    `offers` None: the platform did not answer; only `reachable` changes.
    Otherwise a subscription whose name is not offered is stopped (Q2: kept,
    readable, no longer updated); one with a newer offered version records
    it as `latest` (the badge); nothing is installed here."""
    at = _now()
    newest: dict[str, Offer] = {}
    for offer in () if offers is None else offers:
        held = newest.get(offer.dataset)
        if held is None or version_key(offer.version) > version_key(held.version):
            newest[offer.dataset] = offer
    for dataset in subscribed_datasets(workspace):
        record = subscription_record(workspace, dataset)
        if record is None:
            continue
        before = dict(record)
        if offers is None:
            record["reachable"] = False
        else:
            record["reachable"] = True
            record["checked_at"] = at
            found = newest.get(dataset)
            if found is None:
                if not record.get("stopped"):
                    record["stopped"] = True
                    record["stopped_at"] = at
            else:
                record["stopped"] = False
                record.pop("stopped_at", None)
                record["latest"] = (
                    {"version": found.version, "description": found.description}
                    if version_key(found.version) > version_key(str(record.get("version")))
                    else None
                )
        if record != before:
            write_record(workspace, dataset, record)


def status_of(record: dict[str, Any]) -> str:
    if record.get("stopped"):
        return "stopped_no_access"
    if record.get("reachable") is False:
        return "offline"
    if isinstance(record.get("latest"), dict):
        return "update_available"
    return "current"


def entry(workspace: Path, dataset: str) -> dict[str, Any] | None:
    """One subscription as the API and the chat show it."""
    record = subscription_record(workspace, dataset)
    if record is None or not isinstance(record.get("version"), str):
        return None
    store = BiStore(workspace, dataset)
    status = status_of(record)
    latest = record.get("latest") if isinstance(record.get("latest"), dict) else None
    return {
        "name": dataset,
        "subscribed": True,
        "read_only": True,
        "version": record["version"],
        "published_by": record.get("published_by") or "",
        "published_at": record.get("published_at") or "",
        "note": record.get("note") or "",
        "schema": record.get("schema") or store.schema_ref(),
        "status": status,
        "status_text": STATUS_TEXT[status],
        "latest": latest.get("version") if latest else None,
        "latest_note": (latest.get("description") or "") if latest else "",
        "stopped_at": record.get("stopped_at"),
        "checked_at": record.get("checked_at"),
        "cards": len(store.card_rows()) if store.exists else 0,
        "updated": store.last_updated() if store.exists else None,
    }


def listing(workspace: Path) -> list[dict[str, Any]]:
    return [item for d in subscribed_datasets(workspace) if (item := entry(workspace, d))]


def source(workspace: Path, dataset: str) -> dict[str, Any] | None:
    """What the chat cites for a subscribed dataset; None for a local one."""
    found = entry(workspace, dataset) if SUBSCRIBED_RE.match(dataset) else None
    if found is None:
        return None
    return {
        "dataset": dataset,
        "version": found["version"],
        "published_by": found["published_by"],
        "published_at": found["published_at"],
        "status": found["status"],
        "stopped": found["status"] == "stopped_no_access",
        "latest": found["latest"],
    }


def remove(workspace: Path, dataset: str) -> bool:
    """Take the local copy off this computer; False when there was none."""
    split(dataset)
    root = subscribed_root(workspace, dataset)
    if not root.exists():
        return False
    shutil.rmtree(root)
    return True
