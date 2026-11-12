"""Scheduled execution uses real identity/claims, not application grant records."""

import asyncio
from pathlib import Path

from test_local_agent import agent, company
from test_schedule_worker import DUE, definition

from common.assets import AssetIdentity
from host_runtime.schedule_worker import ScheduleWorker
from host_runtime.schedules import SqliteScheduleStore


def test_due_workflow_runs_without_schedule_grants_and_never_reclaims_it(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    try:
        with SqliteScheduleStore(
            tmp_path / "schedules.sqlite", bridge_id="bridge-company"
        ) as store:
            store.create(definition(), now=DUE)
            assert store.active_grant("scheduled-release", owner="engineer") is None
            results = asyncio.run(ScheduleWorker(store, resident).poll_once(now=DUE))
            assert len(results) == 1 and results[0].status == "succeeded"
            assert runner.bridge.events
            assert asyncio.run(ScheduleWorker(store, resident).poll_once(now=DUE)) == ()
            assert store.pending_claims() == ()
    finally:
        resident.state.close()


def test_uninstalled_target_remains_a_real_failure_without_an_approval_card(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    try:
        with SqliteScheduleStore(
            tmp_path / "schedules.sqlite", bridge_id="bridge-company"
        ) as store:
            target = AssetIdentity(namespace="engineering", name="missing", version="1.0.0")
            store.create(definition(target=target), now=DUE)
            result = asyncio.run(ScheduleWorker(store, resident).poll_once(now=DUE))[0]
            assert result.status == "unavailable" and result.result_code == "workflow_not_installed"
            assert not runner.bridge.events
    finally:
        resident.state.close()


def test_external_effect_needs_no_per_run_card_and_still_executes_only_once(tmp_path: Path) -> None:
    from test_schedule_grants import SEND
    from test_schedule_grants import definition as define

    resident, runner = agent(company(), tmp_path)
    try:
        with SqliteScheduleStore(tmp_path / "send.sqlite", bridge_id="bridge-company") as store:
            store.create(define(SEND), now=DUE)
            result = asyncio.run(ScheduleWorker(store, resident).poll_once(now=DUE))[0]
            assert result.status == "succeeded" and result.side_effect == "external_side_effect"
            assert runner.bridge.events and store.pending_claims() == ()
            assert asyncio.run(ScheduleWorker(store, resident).poll_once(now=DUE)) == ()
    finally:
        resident.state.close()
