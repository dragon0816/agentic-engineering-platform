"""Agent Web's schedule routes over a real loopback socket."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import ready

from common.scheduling import ScheduleDefinition
from host_runtime.conversation_backends import LocalConversationBackends
from host_runtime.host import build_runtime
from host_runtime.schedules import SqliteScheduleStore
from host_runtime.web import AgentWeb, AgentWebServer
from integrations.browser import Browser, browser_path

TARGET = {"namespace": "engineering", "name": "read-local-file", "version": "1.0.0"}


class Served:
    def __init__(self, server: AgentWebServer, workspace: Path) -> None:
        self.server = server
        self.workspace = workspace

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def call(
        self,
        path: str,
        body: Any = None,
        *,
        token: str | None = "",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        request = urllib.request.Request(
            self.base + path, method="POST" if body is not None else "GET"
        )
        chosen = self.server.token if token == "" else token
        if chosen is not None:
            request.add_header("Authorization", f"Bearer {chosen}")
        for name, value in (headers or {}).items():
            request.add_header(name, value)
        if body is not None:
            request.add_header("Content-Type", "application/json")
            request.data = json.dumps(body).encode("utf-8")
        try:
            with urllib.request.urlopen(request, timeout=20) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as refused:
            return refused.code, json.loads(refused.read() or b"{}")

    def store(self) -> SqliteScheduleStore:
        return SqliteScheduleStore(self.workspace / "schedules.sqlite", bridge_id="bridge-company")


@pytest.fixture
def served(tmp_path: Path) -> Iterator[Served]:
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        backends = LocalConversationBackends(layout.workspace_root, which=lambda _name: None)
        server = AgentWebServer(AgentWeb(runtime, conversation_backends=backends))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield Served(server, layout.workspace_root)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def create_body(schedule_id: str = "daily-read", **changes: Any) -> dict[str, Any]:
    return {
        "schedule_id": schedule_id,
        "target_kind": "workflow",
        "target": TARGET,
        "recurrence": {"kind": "daily", "timezone": "Asia/Taipei", "at": "09:00"},
        "runtime_inputs": {"args": "notes.txt"},
        **changes,
    }


def test_schedule_routes_refuse_without_token_foreign_host_or_foreign_origin(
    served: Served,
) -> None:
    assert served.call("/api/schedules", token=None)[0] == 401
    assert served.call("/api/schedules", token="not-the-token")[0] == 401
    assert served.call("/api/schedules", headers={"Host": "attacker.example"})[0] == 403
    assert served.call("/api/schedules", headers={"Origin": "https://evil.example"})[0] == 403
    assert served.call("/api/schedules/create", create_body(), token=None)[0] == 401
    status, _ = served.call(
        "/api/schedules/create", create_body(), headers={"Origin": "null"}
    )
    assert status == 403
    status, _ = served.call(
        "/api/schedules/grant",
        {"schedule_id": "daily-read", "max_side_effect": "read"},
        headers={"Host": "evil.example:80"},
    )
    assert status == 403
    assert not (served.workspace / "schedules.sqlite").exists()
    assert served.call("/api/schedules/unknown", {})[0] == 404


def test_create_grant_pause_resume_and_history_over_the_socket(served: Served) -> None:
    status, overview = served.call("/api/schedules")
    assert status == 200 and overview["schedules"] == []
    assert overview["resident_loop"] == {"running": False}
    (target,) = overview["targets"]
    assert target["target"] == TARGET and target["side_effect"] == "read"
    # The browser cannot name an owner, approver or policy.
    assert served.call("/api/schedules/create", {**create_body(), "owner": "other"})[0] == 400
    assert served.call(
        "/api/schedules/create", create_body(target={**TARGET, "name": "missing"})
    ) == (409, {"ok": False, "code": "workflow_not_installed"})
    status, created = served.call(
        "/api/schedules/create", create_body(), headers={"Origin": served.base}
    )
    assert status == 201 and created["schedule"]["definition"]["owner"] == "engineer"
    assert served.call("/api/schedules/create", create_body())[1]["code"] == "exists"
    status, granted = served.call(
        "/api/schedules/grant",
        {"schedule_id": "daily-read", "max_side_effect": "read", "approved_by": "other"},
    )
    assert status == 400
    status, granted = served.call(
        "/api/schedules/grant", {"schedule_id": "daily-read", "max_side_effect": "read"}
    )
    assert status == 200
    assert granted["grant"]["grant"]["approved_by"] == "engineer"
    assert granted["grant"]["grant"]["policy_ref"] == "owner-schedule-grant"
    assert served.call("/api/schedules/pause", {"schedule_id": "daily-read"})[1]["schedule"][
        "status"
    ] == "paused"
    assert served.call("/api/schedules/resume", {"schedule_id": "daily-read"})[1]["schedule"][
        "status"
    ] == "active"
    status, overview = served.call("/api/schedules")
    (schedule,) = overview["schedules"]
    assert schedule["grant"]["max_side_effect"] == "read" and schedule["side_effect"] == "read"
    assert served.call("/api/schedules/history?schedule_id=daily-read")[1]["runs"] == []
    assert served.call("/api/schedules/history?schedule_id=nope")[0] == 404
    assert served.call("/api/schedules/revoke", {"schedule_id": "daily-read"})[0] == 200
    assert served.call("/api/schedules/revoke", {"schedule_id": "daily-read"})[1] == {
        "ok": False,
        "code": "no_grant",
    }


@pytest.mark.skipif(browser_path() is None, reason="no Chromium browser is installed")
def test_schedules_panel_loads_and_creates_in_a_real_browser(
    served: Served, tmp_path: Path
) -> None:
    browser = Browser(tmp_path / "schedule-browser", timeout_s=60)
    browser.start()
    try:
        browser.navigate(served.base + f"/?token={served.server.token}")
        controls = {item.element_id: item for item in browser.look().elements}
        browser.click(controls["nav-schedules"].index, expected=controls["nav-schedules"])
        opened = browser.look()
        assert "Scheduled tasks" in opened.text
        assert "Waiting for your approval" in opened.text
        assert browser._evaluate('document.getElementById("boot-error").hidden') is True
        # The panel fills its target list asynchronously after the click.
        for _ in range(100):
            options = browser._evaluate(
                'document.getElementById("schedule-target").options.length'
            )
            if options:
                break
            threading.Event().wait(0.05)
        assert options == 1
        browser._evaluate(
            'document.getElementById("schedule-id").value = "browser-read";'
            'document.getElementById("schedule-kind").value = "daily";'
            'document.getElementById("schedule-json").value = '
            '\'{"args": "notes.txt"}\';'
            'document.getElementById("schedule-save").click(); true'
        )
        for _ in range(100):
            result = browser._evaluate(
                'document.getElementById("schedule-form-result").textContent'
            )
            if result:
                break
            threading.Event().wait(0.05)
        assert "Saved browser-read" in result
    finally:
        browser.close()
        browser.discard_profile()
    status, overview = served.call("/api/schedules")
    assert [item["schedule_id"] for item in overview["schedules"]] == ["browser-read"]


def _open_claims(served: Served, count: int) -> list[str]:
    assert served.call("/api/schedules/create", create_body())[0] == 201
    keys: list[str] = []
    with served.store() as store:
        for offset in range(count):
            due = datetime(2026, 10, 1, 1, tzinfo=UTC) + timedelta(days=offset)
            definition = ScheduleDefinition.model_validate(
                {**create_body(f"stuck-{offset}"), "owner": "engineer"}
            )
            store.create(definition, now=due - timedelta(minutes=5))
            (claim,) = store.claim_due(now=due, owner="engineer")
            keys.append(claim.idempotency_key)
    return keys


def test_resolve_needs_confirmation_and_records_the_decision(served: Served) -> None:
    (key,) = _open_claims(served, 1)
    status, overview = served.call("/api/schedules")
    stuck = next(item for item in overview["schedules"] if item["schedule_id"] == "stuck-0")
    assert stuck["blocked_by"] == key
    assert served.call(
        "/api/schedules/resolve", {"idempotency_key": key, "outcome": "failed"}
    ) == (400, {"ok": False, "code": "confirmation_required"})
    status, resolved = served.call(
        "/api/schedules/resolve",
        {"idempotency_key": key, "outcome": "failed", "note": "Saw the error", "confirm": True},
    )
    assert status == 200
    assert resolved["run"]["result_code"] == "operator_resolved_failed"
    history = served.call("/api/schedules/history?schedule_id=stuck-0")[1]
    assert history["decisions"][0]["decided_by"] == "engineer"
    assert history["decisions"][0]["note"] == "Saw the error"
    assert served.call(
        "/api/schedules/resolve", {"idempotency_key": key, "outcome": "failed", "confirm": True}
    ) == (409, {"ok": False, "code": "not_claimed"})


def test_approve_rechecks_every_grant_and_deny_settles_without_running(served: Served) -> None:
    first, second = _open_claims(served, 2)
    with served.store() as store:
        for key in (first, second):
            store.await_approval(key, owner="engineer", side_effect="external_side_effect")
    overview = served.call("/api/schedules")[1]
    assert {run["idempotency_key"] for run in overview["awaiting_approval"]} == {first, second}
    status, denied = served.call("/api/schedules/deny", {"idempotency_key": first})
    assert status == 200 and denied["run"]["result_code"] == "run_approval_denied"
    # Approval is not a grant: without the schedule's own grant nothing runs.
    status, approved = served.call(
        "/api/schedules/approve", {"idempotency_key": second, "note": "ok"}
    )
    assert status == 200
    assert approved["run"]["status"] == "needs_input"
    assert approved["run"]["result_code"] == "schedule_grant_missing"
    assert served.call("/api/schedules/approve", {"idempotency_key": second})[1] == {
        "ok": False,
        "code": "not_awaiting_approval",
    }
