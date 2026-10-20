"""File-backed work queue for the loan flow (workflows 06 / 06b).

The producer (06) scans Outlook every few minutes and enqueues; the consumer
(06b) claims one item at a time, drives two browser flows and drafts a reply.
Keeping them apart means a form that hangs in the portal cannot stall the
scanner, and a failure can be retried for one borrow number instead of the batch.

**Claiming is an atomic rename**, not a lock file. ``os.replace`` either moves
the item or raises, so two consumers racing for the same item cannot both win
and there is no lock to leak if the Bridge dies mid-run. The old implementation
carried a lock plus a TTL to recover from exactly that; a rename needs neither.

**The identity is the borrow number, not the mail.** The same form can be
approved twice and generate two notices -- measured 2026-08-02: 124 mails
carried 118 distinct borrow numbers. Keying on the mail would check C4C twice
and leave the user two draft replies for one loan.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator, Mapping
from typing import Any

#: The queue's folder. The AEP host passes its workspace folder on every call;
#: this default is only for a caller that names none (AEP port).
REPO_ROOT = Path.home() / ".aep-loan-reply"

QUEUE_ROOT = REPO_ROOT / "state" / "loan-queue"

#: pending -> claimed -> done | failed. Every state is a directory so the queue
#: can be inspected, drained or replayed with a file manager.
STATES = ("pending", "claimed", "done", "failed")

#: A claim older than this is assumed abandoned (the Bridge was restarted
#: mid-item) and may be taken again. Generous: the consumer drives two browser
#: flows and a screenshot, which is slow but not this slow.
CLAIM_TTL_SEC = 1800.0

_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def resolve_config(path: Path | str | None, default: Path) -> Path:
    """Where a config path points, tried repo-root first and then the CWD.

    Both are needed. Under uvicorn the Bridge runs from `host-bridge/`, so a
    repo-relative ``config/workflow-06.json`` only resolves against the repo
    root; but CLAUDE.md documents the CLI form as
    ``--config ..\\config\\workflow-06.json`` from inside ``host-bridge``, which
    only resolves against the CWD.

    Shared by both halves of the flow: 06 and 06b read one config file, and a
    path that resolved differently between them would be its own bug.
    """
    p = Path(path).expanduser() if path else default
    if p.is_absolute():
        return p
    for candidate in (REPO_ROOT / p, Path.cwd() / p):
        if candidate.is_file():
            return candidate
    return REPO_ROOT / p


def _safe_name(borrow_no: str) -> str:
    """A borrow number as a filename. Refuses to produce an empty one."""
    name = _SAFE.sub("_", (borrow_no or "").strip())
    return name or "unknown"


def state_dir(state: str, root: Path | None = None) -> Path:
    if state not in STATES:
        raise ValueError(f"unknown queue state {state!r}")
    return (root or QUEUE_ROOT) / state


def ensure_dirs(root: Path | None = None) -> None:
    for s in STATES:
        state_dir(s, root).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class QueueItem:
    borrow_no: str
    path: Path
    payload: dict[str, Any]

    @property
    def state(self) -> str:
        return self.path.parent.name


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def known_borrow_numbers(root: Path | None = None) -> set[str]:
    """Every borrow number the queue has seen, in any state.

    This is the dedupe set. It deliberately includes ``done`` and ``failed``:
    a form that has already been replied to must not be replied to again just
    because a second approval notice arrived, and one that failed should be
    looked at rather than silently retried forever.
    """
    ensure_dirs(root)
    seen: set[str] = set()
    for s in STATES:
        for f in state_dir(s, root).glob("*.json"):
            seen.add(f.stem)
    return seen


def enqueue(payload: Mapping[str, Any], root: Path | None = None) -> Path | None:
    """Write one item to ``pending``. Returns ``None`` if it is already known."""
    borrow_no = str(payload.get("borrowNo") or "")
    name = _safe_name(borrow_no)
    ensure_dirs(root)
    if name in known_borrow_numbers(root):
        return None
    dest = state_dir("pending", root) / f"{name}.json"
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({**payload, "enqueuedAt": time.strftime("%Y-%m-%dT%H:%M:%S")},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Rename last so a reader never sees a half-written item.
    os.replace(tmp, dest)
    return dest


def iter_pending(root: Path | None = None) -> Iterator[QueueItem]:
    ensure_dirs(root)
    for f in sorted(state_dir("pending", root).glob("*.json")):
        payload = _read(f)
        if payload is not None:
            yield QueueItem(f.stem, f, payload)


def reclaim_expired(root: Path | None = None, ttl: float | None = None) -> list[str]:
    """Move claims older than the TTL back to ``pending``.

    Without this an item claimed by a Bridge that was then restarted would sit
    in ``claimed`` forever -- invisible to the consumer and, because
    ``known_borrow_numbers`` counts it, never re-enqueued either.
    """
    ensure_dirs(root)
    cutoff = time.time() - (CLAIM_TTL_SEC if ttl is None else ttl)
    moved: list[str] = []
    for f in list(state_dir("claimed", root).glob("*.json")):
        try:
            if f.stat().st_mtime > cutoff:
                continue
            os.replace(f, state_dir("pending", root) / f.name)
            moved.append(f.stem)
        except OSError:
            continue
    return moved


def claim_one(root: Path | None = None) -> QueueItem | None:
    """Take the oldest pending item, or ``None``.

    The rename is the claim: if another consumer got there first, ``os.replace``
    raises and we simply try the next item.
    """
    reclaim_expired(root)
    for f in sorted(state_dir("pending", root).glob("*.json"), key=lambda p: p.stat().st_mtime):
        dest = state_dir("claimed", root) / f.name
        try:
            os.replace(f, dest)
        except OSError:
            continue  # someone else won the race
        payload = _read(dest)
        if payload is None:
            os.replace(dest, state_dir("failed", root) / f.name)
            continue
        return QueueItem(dest.stem, dest, payload)
    return None


def finish(item: QueueItem, state: str, result: Mapping[str, Any] | None = None,
           root: Path | None = None) -> Path:
    """Move a claimed item to ``done`` or ``failed``, recording the outcome."""
    if state not in ("done", "failed"):
        raise ValueError(f"finish() takes 'done' or 'failed', not {state!r}")
    ensure_dirs(root)
    payload = {
        **item.payload,
        "finishedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "outcome": state,
        "result": dict(result or {}),
    }
    dest = state_dir(state, root) / item.path.name
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, dest)
    item.path.unlink(missing_ok=True)
    return dest


def requeue(item: QueueItem, root: Path | None = None) -> Path:
    """Put a claimed item back in ``pending``, untouched.

    For when the run was stopped by something that has nothing to do with this
    form -- the Bridge going away, the machine being shut down. Marking it
    ``failed`` would be a lie about the form and would need a human to clear it;
    leaving it ``claimed`` hides it until the TTL lapses.
    """
    ensure_dirs(root)
    dest = state_dir("pending", root) / item.path.name
    os.replace(item.path, dest)
    return dest


# ---------------------------------------------------------------------------
# Run-level lock
# ---------------------------------------------------------------------------
# Claiming an *item* needs no lock -- `os.replace` decides the winner (see the
# module docstring). A whole *run* has nothing to rename, and needs a different
# guarantee: only one consumer driving the browsers at a time. Two runs would
# each open their own Edge session on the same profile, which is untested and
# doubles what the portal sees from this machine.
#
# One mechanism, not two. An in-process threading.Lock looked necessary for the
# common case -- two job runs inside the one long-lived Bridge, sharing its pid
# so a liveness check cannot separate them. It is not: `_lock_is_stale` skips
# the pid check for our own pid and falls through to the TTL, so a fresh lock
# held by a sibling thread already reads as busy. Mutation testing is what
# showed this: removing the in-process lock changed no test.
#
# Dropping it also removes the worse failure mode. A threading.Lock that is
# never released stays held for the life of the Bridge process -- permanently
# blocking that job with no way back short of a restart. The file lock expires.

RUN_LOCK_TTL_SEC = 1200.0


class RunLockBusy(RuntimeError):
    """Another run of the same job is already in progress."""

    def __init__(self, name: str, holder: Mapping[str, Any] | None):
        self.name = name
        self.holder = dict(holder or {})
        started = self.holder.get("startedAt") or "unknown time"
        pid = self.holder.get("pid", "?")
        super().__init__(
            f"another {name} run is already in progress "
            f"(pid {pid}, started {started}). Nothing was processed."
        )


@dataclass
class RunLock:
    name: str
    path: Path
    token: str

    def release(self) -> None:
        """Give the lock up. Safe to call twice, and never deletes someone else's.

        The token check matters: if this run overran the TTL and another stole
        the lock, deleting the file here would leave that run unprotected while
        it still believes it holds the lock.
        """
        try:
            if self.path.is_file():
                current = _read(self.path) or {}
                if current.get("token") == self.token:
                    self.path.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self) -> "RunLock":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.release()


def _lock_path(name: str, root: Path | None = None) -> Path:
    return (root or QUEUE_ROOT) / f"{_SAFE.sub('_', name)}.lock"


def _lock_is_stale(payload: Mapping[str, Any] | None, path: Path, ttl: float) -> bool:
    """Whether an existing lock may be taken over.

    Stale if the holder's process is gone (a crashed CLI run, detected in
    seconds) or the lock is older than the TTL (a hung run, capped). The pid
    check cannot help when the holder was another job inside this same Bridge
    process -- that is what the in-process lock is for.
    """
    if not payload:
        return True
    pid = payload.get("pid")
    if isinstance(pid, int) and pid != os.getpid():
        try:
            from capabilities.loan_reply.processes import pid_exists

            if not pid_exists(pid):
                return True
        except Exception:  # noqa: BLE001 - psutil missing or refusing; fall back to time
            pass
    try:
        return (time.time() - path.stat().st_mtime) > ttl
    except OSError:
        return True


def acquire_run_lock(name: str = "loan_process", root: Path | None = None,
                     ttl: float | None = None, owner: str = "") -> RunLock:
    """Take the run lock for ``name`` or raise :class:`RunLockBusy`."""
    ensure_dirs(root)
    ttl = RUN_LOCK_TTL_SEC if ttl is None else ttl
    path = _lock_path(name, root)

    token = f"{os.getpid()}-{time.time_ns()}"
    payload = {
        "token": token,
        "pid": os.getpid(),
        "owner": owner,
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    for attempt in (1, 2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            existing = _read(path)
            if attempt == 1 and _lock_is_stale(existing, path, ttl):
                path.unlink(missing_ok=True)
                continue
            raise RunLockBusy(name, existing) from None
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return RunLock(name, path, token)

    raise RunLockBusy(name, _read(path))


def counts(root: Path | None = None) -> dict[str, int]:
    ensure_dirs(root)
    return {s: len(list(state_dir(s, root).glob("*.json"))) for s in STATES}
