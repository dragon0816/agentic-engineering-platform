"""What a restart of Agent Web would cut off (owner, 2026-10-25).

The restart helper checked `GET /api/tasks`, saw nothing running and
restarted while the owner was at question 2/9 of a Telegram question flow,
which lives only in memory. `GET /api/activity` adds that conversational work
(Telegram flows and turns, chat turns in progress) and `launcher.
restart_blockers` is the check a restart helper runs first. No message
content and no chat id appear in it.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from test_agent_web import base, fetch, served  # noqa: F401 - the fixture
from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update
from test_telegram_workflow_flow import _install, _tap

from agent.turn_progress import TurnProgress
from host_runtime import launcher
from host_runtime.web import AgentWebServer

#: Too long to appear by chance in the 12 hex digits of a chat's salted digest, which a
#: short id such as OWNER does about one run in 400.
LONG_OWNER = 1_234_567_890_123

FIELDS = [
    {"name": "package", "label": "Mode", "kind": "text", "required": True},
    {"name": "week", "label": "Report week", "kind": "text", "required": True},
]


def test_an_open_flow_is_listed_until_it_is_finished_or_cancelled(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, LONG_OWNER, "/run 7")]])
    senders = [{"sender_id": LONG_OWNER, "actor": "engineer"}]
    item, agent, _ = ingress(tmp_path, transport, senders=senders)
    _install(agent, FIELDS)
    assert item.activity() == []
    poll(item)
    (flow,) = item.activity()
    assert flow["kind"] == "telegram_flow" and flow["stage"] == "question"
    assert flow["workflow"] == "engineering/release-validation-form"
    assert str(LONG_OWNER) not in json.dumps(flow) and len(flow["chat"]) == 12
    assert flow["started_at"].endswith("+00:00")
    # Cancelled: gone.
    transport.batches.append([update(2, LONG_OWNER, "/cancel")])
    poll(item)
    assert item.activity() == []
    # Finished: listed on its card, gone once it ran.
    transport.batches += [[update(3, LONG_OWNER, "/run 7")], [update(4, LONG_OWNER, "quick")]]
    poll(item)
    poll(item)
    transport.batches.append([update(5, LONG_OWNER, "2026_43W")])
    poll(item)
    assert [entry["stage"] for entry in item.activity()] == ["card"]
    transport.batches.append([_tap(6, LONG_OWNER, "run:yes", transport)])
    poll(item)
    assert item.activity() == []
    # Expired: gone too.
    transport.batches.append([update(7, LONG_OWNER, "/run 7")])
    poll(item)
    for state in item._flows.values():
        state.started -= 3600
    assert item.activity() == []


def test_a_turn_in_progress_is_listed_while_it_runs(tmp_path: Path) -> None:
    transport = FakeTransport([])
    item, _agent, _ = ingress(tmp_path, transport)
    seen: list[list[dict[str, str]]] = []

    async def deliver(update: object) -> object:
        seen.append(item.activity())
        raise RuntimeError("stop here")

    item._deliver = deliver  # type: ignore[method-assign,assignment]
    transport.batches.append([update(1, OWNER, "hello")])
    poll(item)
    assert [entry["kind"] for entry in seen[0]] == ["telegram_turn"]
    assert item.activity() == []  # over, even though it failed


def test_agent_web_reports_activity_and_the_restart_check_refuses(
    served: AgentWebServer,  # noqa: F811 - the fixture
    tmp_path: Path,
) -> None:
    web = served.web
    idle = fetch(base(served) + "/api/activity", token=served.token)
    assert idle.status == 200 and idle.json() == {"ok": True, "busy": False, "items": []}
    assert launcher.restart_blockers(served.address) == []
    # An open Telegram flow and a chat turn in progress.
    transport = FakeTransport([[update(1, OWNER, "/run 7")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent, FIELDS)
    poll(item)
    web.telegram_loop = SimpleNamespace(running=True, ingress=item)  # type: ignore[assignment]
    turn = web.turn_progress.begin(TurnProgress(turn_id="t1", session_id="s1", owner="me"))
    busy = fetch(base(served) + "/api/activity", token=served.token).json()
    assert busy["busy"] is True
    assert sorted(entry["kind"] for entry in busy["items"]) == ["chat_turn", "telegram_flow"]
    blockers = launcher.restart_blockers(served.address)
    assert len(blockers) == 2 and any(line.startswith("telegram_flow:") for line in blockers)
    web.turn_progress.end(turn)
    item._flows.clear()
    assert launcher.restart_blockers(served.address) == []
    web.telegram_loop = None
    # Without its token, or with no Agent Web there, it is never "idle".
    assert fetch(base(served) + "/api/activity").status == 401
    assert launcher.restart_blockers("http://127.0.0.1:9/?token=x") != []
