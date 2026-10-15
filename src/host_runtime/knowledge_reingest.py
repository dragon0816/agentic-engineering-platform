"""Ingest many Raw documents again with a sandbox's current rules (owner 2026-10-13).

After a maintainer changes a skill, the Raw already in the sandbox is ingested
again; nothing is pulled or converted. Each document goes through the same two
pipeline steps a person presses on the page (`ingest-plan`, then `ingest-apply`),
so policy and telemetry are unchanged. A plan the planner flagged (problems or
contradictions) is kept for the person to compare and apply by hand; only the
sandbox is written, and a push still needs the benchmark gate. The run's record
is saved in the sandbox after every document, so a page shows it after a
restart and the person can continue with what is left.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from common.base import Contract

RUNS = ".reingest"
#: Seconds one document took in the K1/C6 live runs (plan, then apply).
SECONDS_PER_DOCUMENT = 60
MAX_DOCUMENTS = 1000
Step = Callable[[str, dict[str, Any]], dict[str, Any]]
ItemStatus = Literal["applied", "needs_review", "failed", "rejected"]


class ReingestItem(Contract):
    raw_ref: str
    status: ItemStatus
    plan_id: str | None = None
    pages: tuple[str, ...] = ()  # the plan's pages, to compare a flagged plan
    contradictions: tuple[str, ...] = ()
    detail: str = ""


class ReingestRun(Contract):
    run_id: str
    sandbox_id: str
    actor: str
    raw_refs: tuple[str, ...]
    status: Literal["running", "stopping", "stopped", "finished"] = "running"
    current: str | None = None
    items: tuple[ReingestItem, ...] = ()
    started: str
    ended: str | None = None

    @property
    def remaining(self) -> tuple[str, ...]:
        done = {item.raw_ref for item in self.items}
        return tuple(ref for ref in self.raw_refs if ref not in done)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _write(folder: Path, run: ReingestRun) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{run.run_id}.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")


def one(step: Step, sandbox_id: str, raw_ref: str) -> ReingestItem:
    """Plan one Raw document and apply the plan unless it needs a person."""
    planned = step("ingest-plan", {"sandbox_id": sandbox_id, "raw_ref": raw_ref})
    if not planned.get("ok"):
        return ReingestItem(raw_ref=raw_ref, status="failed", detail=str(planned.get("code")))
    plan = planned.get("data") or {}
    plan_id = plan.get("plan_id")
    if plan.get("status") != "planned" or not plan_id:
        return ReingestItem(
            raw_ref=raw_ref,
            status="failed",
            detail=str(plan.get("failure_code") or plan.get("status")),
        )
    pages = tuple(str(page.get("path")) for page in plan.get("pages") or ())
    contradictions = tuple(str(line) for line in plan.get("contradictions") or ())
    flagged = [*(plan.get("problems") or ()), *("contradiction" for _ in contradictions)]
    if flagged:
        return ReingestItem(
            raw_ref=raw_ref,
            status="needs_review",
            plan_id=plan_id,
            pages=pages,
            contradictions=contradictions,
            detail=", ".join(dict.fromkeys(flagged)),
        )
    applied = step("ingest-apply", {"sandbox_id": sandbox_id, "plan_id": plan_id})
    data = applied.get("data") or {}
    if not applied.get("ok"):
        return ReingestItem(
            raw_ref=raw_ref,
            status="failed",
            plan_id=plan_id,
            pages=pages,
            detail=str(applied.get("code")),
        )
    if data.get("status") != "applied":
        return ReingestItem(
            raw_ref=raw_ref,
            status="rejected",
            plan_id=plan_id,
            pages=pages,
            detail=", ".join(data.get("problems") or ()),
        )
    return ReingestItem(raw_ref=raw_ref, status="applied", plan_id=plan_id, pages=pages)


def run_reingest(
    step: Step,
    run: ReingestRun,
    folder: Path,
    stop: threading.Event,
    on_change: Callable[[ReingestRun], None] | None = None,
) -> ReingestRun:
    """Go through the run's documents in order until done or stopped. A live
    run is reported through `on_change`, so nobody reads a file being written."""

    def _save(folder: Path, run: ReingestRun) -> None:
        if on_change is not None:
            on_change(run)
        _write(folder, run)

    _save(folder, run)
    for raw_ref in run.remaining:
        if stop.is_set():
            break
        run = run.model_copy(update={"current": raw_ref})
        _save(folder, run)
        try:
            item = one(step, run.sandbox_id, raw_ref)
        except Exception as failure:  # noqa: BLE001 - one document never ends the run
            item = ReingestItem(
                raw_ref=raw_ref, status="failed", detail=f"error:{type(failure).__name__}"
            )
        run = run.model_copy(update={"items": (*run.items, item)})
        _save(folder, run)
    run = run.model_copy(
        update={
            "status": "stopped" if run.remaining else "finished",
            "current": None,
            "ended": _now(),
        }
    )
    _save(folder, run)
    return run


def report(run: ReingestRun) -> dict[str, Any]:
    shown: dict[str, Any] = run.model_dump(mode="json")
    shown["remaining"] = list(run.remaining)
    return shown


def latest(folder: Path) -> dict[str, Any] | None:
    runs = sorted(folder.glob("reingest-*.json")) if folder.is_dir() else []
    if not runs:
        return None
    return report(ReingestRun.model_validate_json(runs[-1].read_text(encoding="utf-8")))
