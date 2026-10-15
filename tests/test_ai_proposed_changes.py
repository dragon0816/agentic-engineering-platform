"""AI proposes, the person applies (owner 2026-10-15).

The model has one tool, `propose_change`; it never reaches a writer. Apply
runs the Settings/Capabilities writer itself. See
docs/phases/AI_PROPOSED_CHANGES.md.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_chat_workflow_forms import _plain
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import host_json, ready

from common.action_cards import (
    CARD_KEY,
    CARD_TAP,
    ActionCard,
    CardButton,
    CardRow,
    telegram_card,
)
from common.change_proposal import PROPOSE_TOOL, looks_like_credential, secret_problem
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb

LAYA = {"ssh_host": "10.0.0.5", "ssh_user": "lab", "mode": "off",
        "approval_ref": "owner-approved-test-laya"}
TELEGRAM_TOKEN = "123456789:AAH" + "x" * 32
SETTING_FIELD = {"name": "inbox_path", "label": "Input inbox", "kind": "folder",
                 "scope": "static"}


class _Model:
    """An OpenAI-compatible Gateway: first a `propose_change` call, then text."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.proposal: dict[str, Any] = {"kind": "laya", "values": {"mode": "shadow"},
                                          "reason": "The person asked for shadow mode."}

    def send(self, url: str, body: bytes, headers: Mapping[str, str],
             timeout_s: float) -> GatewayReply:
        payload = json.loads(body)
        self.calls.append(payload)
        offered = {tool["function"]["name"] for tool in payload.get("tools", [])}
        if PROPOSE_TOOL in offered and not any(
                item["role"] == "tool" for item in payload["messages"]):
            message: dict[str, Any] = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-1", "type": "function", "function": {
                    "name": PROPOSE_TOOL, "arguments": json.dumps(self.proposal)}}]}
        else:
            message = {"role": "assistant", "content": "I could not propose that."}
        return GatewayReply(200, {"choices": [{"index": 0, "message": message}],
                                  "usage": {"prompt_tokens": 1, "completion_tokens": 1}})


def _config(tmp_path: Path) -> tuple[Any, Any]:
    return ready(tmp_path, config_changes={
        "laya": LAYA,
        "credentials": [{"secret": "jev_api_key", "environment_variable": "AEP_JEV_API_KEY"}],
        "models": binding(catalog={
            "endpoints": [endpoint(credential=None, model="fixture-model")],
            "routes": [{"name": "default", "alias": "company"}]}),
    })


@pytest.fixture
def web(tmp_path: Path) -> Iterator[tuple[AgentWeb, Path, _Model]]:
    config, layout = _config(tmp_path)
    path = host_json(tmp_path, config)
    model = _Model()
    with build_runtime(config, layout=layout, model_transport=model) as runtime:
        workflow = _plain("sync-test", [SETTING_FIELD])
        identity = workflow.metadata.identity
        (layout.workflows / f"{identity.namespace}__{identity.name}__{identity.version}.json"
         ).write_text(workflow.model_dump_json(), encoding="utf-8")
        agent_web = AgentWeb(runtime, config_path=path)
        agent_web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        yield agent_web, path, model


def _propose(web: AgentWeb, kind: str, values: dict[str, Any], reason: str = "asked",
             channel: str = "local") -> Any:
    tool = next(item for item in web.runtime.agent.gateway.host_tools()
                if item.tool.name == PROPOSE_TOOL)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor="engineer", namespace="engineering", channel=channel, message="change it",
        session_id="session-1")
    return asyncio.run(tool.handler(context, {"kind": kind, "values": values,
                                              "reason": reason}))


def _card(outcome: Any) -> dict[str, Any]:
    assert outcome.status == "succeeded", outcome
    return dict(outcome.data[CARD_KEY])


def _host(path: Path) -> CompanyHostConfiguration:
    return CompanyHostConfiguration.model_validate_json(path.read_text("utf-8"))


def _proposal_tasks(web: AgentWeb) -> list[Any]:
    return [task for task in web.tasks().records() if task.kind == "proposal"]


# -- the card component -------------------------------------------------------


def test_the_card_is_generic_and_telegram_draws_it() -> None:
    card = ActionCard(
        card_id="pm-0123456789ab", kind="permission", title="Run a command",
        preview="git status", reason="to see the changes",
        buttons=(CardButton(action="allow", label="Allow", style="primary"),
                 CardButton(action="allow_session", label="Allow for this conversation"),
                 CardButton(action="deny", label="Deny", style="danger")),
        message="The agent asks to run a command.")
    text, buttons = telegram_card(card)
    assert "git status" in text and "Why: to see the changes" in text
    assert [label for label, _ in buttons[0]] == ["Allow", "Allow for this conversation",
                                                  "Deny"]
    assert all(CARD_TAP.match(data) and len(data) <= 64 for _, data in buttons[0])
    only_web = card.model_copy(update={"web_only": True})
    text, buttons = telegram_card(only_web, "Agent Web, Tasks")
    assert buttons == () and "Open in Agent Web to apply: Agent Web, Tasks" in text
    closed = card.model_copy(update={"status": "denied", "status_label": "Denied",
                                     "outcome_ok": False, "buttons": ()})
    text, buttons = telegram_card(closed)
    assert buttons == () and "⛔ Denied" in text
    with pytest.raises(ValueError):
        ActionCard(card_id="pm-0123456789ab", kind="x", title="t", message="m",
                   buttons=(CardButton(action="a", label="A"),
                            CardButton(action="a", label="B")))
    row = CardRow(label="Mode", before="off", after="shadow")
    assert "• Mode: off → shadow" in telegram_card(card.model_copy(update={"rows": (row,)}))[0]


@pytest.mark.parametrize("value", [
    TELEGRAM_TOKEN, "login-0123456789abcdef:" + "A" * 40, "sk-" + "a1" * 12,
    "ghp_" + "A1b2" * 6, "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.x",
    "https://user:hunter2@example.com/", "https://x.example/?token=abc",
    "Bearer abc.def", "password=hunter2", "Q2xhdWRlQ29kZTEyMzQ1Njc4OTBhYmNkZWZnaGlqa2xt",
])
def test_credential_shaped_values_are_recognized(value: str) -> None:
    assert looks_like_credential(value)


@pytest.mark.parametrize("value", [
    "shadow", "10.0.0.5", "https://portal.example.com", "C:\\work\\inbox",
    "engineering/sync-test@1.0.0", "AEP_LLM_TOKEN", "llm_gateway_token", "0.9",
])
def test_ordinary_values_are_not_credentials(value: str) -> None:
    assert not looks_like_credential(value)


def test_secret_fields_are_named_never_their_values() -> None:
    assert secret_problem({"token": "x"}) == "token"
    assert secret_problem({"settings": {"api_key": "y"}}) == "settings.api_key"
    assert secret_problem({"senders": [{"actor": TELEGRAM_TOKEN}]}) == "senders[0].actor"
    assert secret_problem({"credential_secret": "llm_gateway_token",
                           "credential_environment": "AEP_LLM_TOKEN"}) is None


# -- the model reaches no writer ---------------------------------------------


def test_the_model_gets_only_propose_change_and_proposing_writes_nothing(web: Any) -> None:
    agent_web, path, _ = web
    names = {item.tool.name for item in agent_web.runtime.agent.gateway.host_tools()}
    assert PROPOSE_TOOL in names
    assert not {name for name in names
                if any(word in name for word in ("update_", "save_", "switch", "remove_asset",
                                                 "add_to_agent", "publish_asset", "enroll"))}
    before = path.read_bytes()
    card = _card(_propose(agent_web, "laya", {"mode": "shadow"}))
    assert path.read_bytes() == before                     # nothing changed yet
    assert card["title"] == "Change Laya decision acceleration"
    assert card["rows"] == [{"label": "Mode", "before": "off", "after": "shadow"}]
    assert [b["label"] for b in card["buttons"]] == ["Apply", "Cancel"]
    assert card["status"] == "pending" and card["web_only"] is False
    assert any("restarts" in effect for effect in card["effects"])
    assert card["link"]["anchor"] == "laya-settings"
    [task] = _proposal_tasks(agent_web)
    assert task.status == "needs_input" and "Mode: off → shadow" in task.summary


def test_a_task_or_schedule_without_a_person_is_refused(web: Any) -> None:
    agent_web, _, _ = web
    tool = next(item for item in agent_web.runtime.agent.gateway.host_tools()
                if item.tool.name == PROPOSE_TOOL)
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor="engineer", namespace="engineering", channel="local", message="x")
    outcome = asyncio.run(tool.handler(context, {"kind": "laya", "values": {"mode": "shadow"}}))
    assert outcome.status == "failed" and outcome.failure.code == "proposal_needs_a_person"


@pytest.mark.parametrize(("kind", "values", "says"), [
    ("laya", {"ssh_port": "abc"}, "not valid"),
    ("laya", {"colour": "blue"}, "has no value 'colour'"),
    ("laya", {"approval_ref": "me"}, "permission or an approval"),
    ("laya", {"mode": "off"}, "Nothing would change"),
    ("grants", {"x": 1}, "Unknown kind"),
    ("capability", {"action": "explode", "asset": "sync-test"}, "action is"),
    ("capability", {"action": "switch_on", "asset": "sync-test"}, "already switched on"),
    ("workflow_settings", {"workflow": "nope", "settings": {"inbox_path": "C:\\in"}},
     "installed Workflow"),
    ("platform_add", {"kind": "workflow", "asset": "engineering/x@1.0.0"}, "not set up"),
    ("publish", {"kind": "workflow", "asset": "engineering/sync-test@9.9.9",
                 "change": "minor"}, "installed"),
    ("telegram", {"enabled": True}, "bot token is not saved"),
])
def test_validation_errors_come_back_as_a_refusal_not_a_card(
        web: Any, kind: str, values: dict[str, Any], says: str) -> None:
    agent_web, path, _ = web
    before = path.read_bytes()
    outcome = _propose(agent_web, kind, values)
    assert outcome.status == "failed" and outcome.failure.code == "proposal_refused"
    assert says in outcome.failure.message
    assert agent_web.proposals.store.records() == []
    assert path.read_bytes() == before
    [task] = _proposal_tasks(agent_web)
    assert task.status == "failed" and task.summary.startswith("Refused:")


@pytest.mark.parametrize(("kind", "values", "where"), [
    ("telegram", {"token": TELEGRAM_TOKEN}, "Settings > Telegram bot"),
    ("shared_platform", {"code": "login-0123456789abcdef:" + "A" * 40}, "Personal Agent code"),
    ("model", {"credential_environment": "sk-" + "a1" * 12}, "environment variable"),
    ("workflow_settings", {"workflow": "sync-test",
                           "settings": {"inbox_path": "https://u:pw@example.com/x"}},
     "Workflow's settings"),
])
def test_secret_looking_values_are_refused_and_never_echoed(
        web: Any, kind: str, values: dict[str, Any], where: str) -> None:
    agent_web, _, _ = web
    outcome = _propose(agent_web, kind, values)
    assert outcome.status == "failed" and "never passed through a chat" in outcome.failure.message
    assert where in outcome.failure.message
    secret = json.dumps(values)
    for piece in ("AAHxxxx", "AAAAAAAA", "a1a1a1a1", "u:pw@"):
        if piece in secret:
            assert piece not in outcome.failure.message
            assert all(piece not in task.summary for task in _proposal_tasks(agent_web))


# -- Apply is the Settings card's writer ---------------------------------------


def test_apply_writes_what_the_settings_card_writes(web: Any, tmp_path: Path) -> None:
    agent_web, path, _ = web
    card = _card(_propose(agent_web, "laya", {"mode": "shadow", "threshold": 85}))
    decided = agent_web.decide_card(card["card_id"], "apply")
    assert decided["ok"] and decided["card"]["status"] == "applied"
    assert decided["card"]["outcome_ok"] is True and "restarts" in decided["card"]["outcome"]
    assert decided["card"]["buttons"] == []
    by_proposal = _host(path)
    assert by_proposal.laya is not None and by_proposal.laya.mode == "shadow"
    assert by_proposal.laya.confidence_threshold == 0.85
    assert by_proposal.decision_accelerator.mode == "shadow"

    # The same values through the Settings card, on a copy of the old host.json.
    other = tmp_path / "other"
    config, layout = _config(other)
    other_path = host_json(other, config)
    with build_runtime(config, layout=layout, model_transport=_Model()) as runtime:
        direct = AgentWeb(runtime, config_path=other_path)
        direct.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        current = direct.laya_settings()["settings"]
        assert direct.update_laya({**current, "mode": "shadow",
                                   "confidence_threshold": 0.85})["ok"]
    assert _host(other_path).laya == by_proposal.laya
    assert _host(other_path).decision_accelerator == by_proposal.decision_accelerator
    # The Laya card shows the saved values at once.
    assert agent_web.laya_settings()["settings"]["mode"] == "shadow"
    [task] = _proposal_tasks(agent_web)
    assert task.status == "succeeded" and task.summary.startswith("Applied")


def test_shared_platform_apply_backs_host_json_up_as_the_card_does(web: Any) -> None:
    agent_web, path, _ = web
    card = _card(_propose(agent_web, "shared_platform",
                          {"member_portal_url": "https://portal.example.com"}))
    assert card["web_only"] is True
    assert any("backed up" in effect for effect in card["effects"])
    decided = agent_web.decide_card(card["card_id"], "apply")
    assert decided["ok"], decided
    assert _host(path).publishing is not None
    assert _host(path).publishing.member_portal_url == "https://portal.example.com"
    assert list(path.parent.glob("host.json.bak-*-before-shared-platform"))


def test_enrolling_needs_the_code_pasted_in_settings_first(web: Any) -> None:
    agent_web, _, _ = web
    outcome = _propose(agent_web, "shared_platform",
                       {"member_portal_url": "https://portal.example.com",
                        "base_url": "https://bridge.example.com", "enroll": True})
    assert outcome.status == "failed"
    assert "Personal Agent code" in outcome.failure.message
    assert "never passed through a chat" in outcome.failure.message


def test_stale_expired_cancelled_and_double_apply_are_refused(web: Any) -> None:
    agent_web, path, _ = web
    stale = _card(_propose(agent_web, "laya", {"mode": "shadow"}))
    current = agent_web.laya_settings()["settings"]
    assert agent_web.update_laya({**current, "timeout_ms": 2000})["ok"]   # changed meanwhile
    written = path.read_bytes()
    refused = agent_web.decide_card(stale["card_id"], "apply")
    assert refused["code"] == "proposal_stale" and refused["card"]["status"] == "stale"
    assert path.read_bytes() == written

    late = _card(_propose(agent_web, "laya", {"mode": "shadow"}))
    clock = agent_web.proposals.store
    clock.clock = lambda: datetime.now(UTC) + timedelta(minutes=31)
    assert agent_web.card(late["card_id"])["status"] == "expired"
    assert agent_web.decide_card(late["card_id"], "apply")["code"] == "proposal_expired"
    clock.clock = lambda: datetime.now(UTC)

    dropped = _card(_propose(agent_web, "laya", {"mode": "shadow"}))
    assert agent_web.decide_card(dropped["card_id"], "cancel")["card"]["status"] == "cancelled"
    assert agent_web.decide_card(dropped["card_id"], "apply")["code"] == "proposal_cancelled"

    twice = _card(_propose(agent_web, "laya", {"mode": "shadow"}))
    assert agent_web.decide_card(twice["card_id"], "apply")["ok"]
    again = agent_web.decide_card(twice["card_id"], "apply")
    assert again["ok"] is False and again["code"] == "proposal_applied"
    assert agent_web.decide_card("cp-000000000000", "apply")["code"] == "card_unknown"
    statuses = sorted(task.status for task in _proposal_tasks(agent_web))
    assert statuses == ["stopped", "stopped", "stopped", "succeeded"]
    assert agent_web.cards()["cards"] == []


def test_workflow_settings_and_capability_switches(web: Any) -> None:
    agent_web, _, _ = web
    settings = _card(_propose(agent_web, "workflow_settings",
                              {"workflow": "sync-test", "settings": {"inbox_path": "C:\\in"}}))
    assert settings["rows"] == [{"label": "Input inbox", "before": "(empty)",
                                 "after": "C:\\in"}]
    assert settings["web_only"] is False and settings["link"]["view"] == "installed"
    assert agent_web.decide_card(settings["card_id"], "apply")["ok"]
    stored = agent_web.workflow_settings()["workflows"]
    assert stored[0]["values"] == {"inbox_path": "C:\\in"}

    off = _card(_propose(agent_web, "capability", {"action": "switch_off",
                                                   "asset": "sync-test"}))
    assert off["web_only"] is False and off["rows"][0]["after"] == "off"
    assert agent_web.decide_card(off["card_id"], "apply")["ok"]
    layout = agent_web.runtime.layout
    assert (layout.workflows / "disabled").is_dir()
    gone = _card(_propose(agent_web, "capability", {"action": "remove", "kind": "workflow",
                                                    "asset": "sync-test"}))
    assert gone["web_only"] is True and gone["rows"][0]["before"] == "off"
    decided = agent_web.decide_card(gone["card_id"], "apply")
    assert decided["ok"] and "Removed from this Agent" in decided["card"]["outcome"]
    assert not list((layout.workflows / "disabled").glob("*sync-test*"))


def test_model_and_telegram_kinds_go_through_their_writers(web: Any, monkeypatch: Any) -> None:
    agent_web, path, _ = web
    card = _card(_propose(agent_web, "model", {"model": "bigger-model"}))
    assert card["rows"] == [{"label": "Model", "before": "fixture-model",
                             "after": "bigger-model"}]
    assert card["web_only"] is True
    assert agent_web.decide_card(card["card_id"], "apply")["ok"]
    written = _host(path)
    assert written.models is not None
    assert written.models.catalog.endpoint("company").model == "bigger-model"

    monkeypatch.setenv("AEP_TELEGRAM_BOT_TOKEN", TELEGRAM_TOKEN)
    swapped: list[Any] = []
    agent_web.update_telegram_settings = lambda form: (  # type: ignore[method-assign]
        swapped.append(form) or {"ok": True})
    card = _card(_propose(agent_web, "telegram", {
        "enabled": True, "senders": [{"sender_id": 4242, "actor": "engineer"}]}))
    assert {row["label"] for row in card["rows"]} == {"Answer Telegram messages",
                                                      "Allowed senders"}
    assert agent_web.decide_card(card["card_id"], "apply")["ok"]
    assert swapped[0].enabled is True and swapped[0].token is None


def test_telegram_applies_only_the_low_risk_kinds(web: Any) -> None:
    agent_web, path, _ = web
    high = _card(_propose(agent_web, "shared_platform",
                          {"member_portal_url": "https://portal.example.com"},
                          channel="telegram"))
    text, buttons = telegram_card(ActionCard.model_validate(high), "Agent Web")
    assert buttons == () and "Open in Agent Web to apply" in text
    before = path.read_bytes()
    refused = agent_web.decide_card(high["card_id"], "apply", "telegram")
    assert refused["code"] == "web_only" and path.read_bytes() == before
    low = _card(_propose(agent_web, "laya", {"mode": "shadow"}, channel="telegram"))
    assert agent_web.decide_card(low["card_id"], "apply", "telegram")["ok"]
    assert _host(path).laya.mode == "shadow"  # type: ignore[union-attr]


# -- Telegram end to end ----------------------------------------------------------


def test_telegram_shows_the_card_and_a_tap_applies_it(web: Any, tmp_path: Path) -> None:
    from test_chat_workflow_forms_telegram import _Scripted
    from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update
    from test_telegram_workflow_flow import _tap

    agent_web, path, _ = web
    transport = FakeTransport([[update(1, OWNER, "turn Laya to shadow")]])
    item, agent, _ = ingress(tmp_path / "bot", transport)
    agent.gateway.host_tools = agent_web.proposals.tools
    item.cards = agent_web
    agent.gateway.router.model = _Scripted(
        {"tools": [(PROPOSE_TOOL, {"kind": "laya", "values": {"mode": "shadow"},
                                   "reason": "asked"})]})
    delivery = poll(item).deliveries[0]
    assert "Change Laya decision acceleration" in (delivery.reply or "")
    assert "• Mode: off → shadow" in (delivery.reply or "")
    [row] = delivery.buttons
    assert [label for label, _ in row] == ["Apply", "Cancel"]
    apply_data = row[0][1]
    transport.batches.append([_tap(2, OWNER, apply_data)])
    applied = poll(item).deliveries[0]
    assert "✅ Applied" in (applied.reply or "") and applied.buttons == ()
    assert _host(path).laya.mode == "shadow"  # type: ignore[union-attr]

    transport.batches.append([update(3, OWNER, "enroll this PC")])
    agent.gateway.router.model = _Scripted(
        {"tools": [(PROPOSE_TOOL, {"kind": "capability", "reason": "asked", "values": {
            "action": "remove", "asset": "sync-test"}})]})
    high = poll(item).deliveries[0]
    assert "Open in Agent Web to apply" in (high.reply or "") and high.buttons == ()
    card_id = agent_web.cards()["cards"][0]["card_id"]
    transport.batches.append([_tap(4, OWNER, f"card:{card_id}:apply")])   # a forged tap
    refused = poll(item).deliveries[0]
    assert "Open in Agent Web to apply" in (refused.reply or "")
    assert agent_web.card(card_id)["status"] == "pending"


# -- Agent Web end to end -----------------------------------------------------------


def test_turn_laya_to_shadow_card_apply_host_json_and_the_laya_card(web: Any) -> None:
    agent_web, path, model = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    replied = agent_web.conversation_turn(ConversationTurnRequest(
        session_id=session, message="turn Laya to shadow"))
    card = replied["answer"][CARD_KEY]
    assert card["status"] == "pending" and replied["answer"]["status"] == "answered"
    assert "nothing changes until you press Apply" in replied["answer"]["answer"]
    assert len(model.calls) == 1                     # the turn ends with the card
    stored = agent_web.conversations(session)["selected"]["messages"][-1]
    assert stored[CARD_KEY]["card_id"] == card["card_id"]
    assert agent_web.cards()["cards"][0]["card_id"] == card["card_id"]

    decided = agent_web.decide_card(card["card_id"], "apply")
    assert decided["ok"] and _host(path).laya.mode == "shadow"  # type: ignore[union-attr]
    assert agent_web.laya_settings()["settings"]["mode"] == "shadow"
    after = agent_web.conversations(session)["selected"]["messages"][-1]
    assert after[CARD_KEY]["status"] == "applied"
    assert f"[card {card['card_id']}] Applied" in after["tool_summary"]


def test_the_page_has_one_card_renderer_and_its_routes() -> None:
    from host_runtime.web_page import PAGE

    for hook in ("function renderActionCard(", "/api/cards/decide", 'id="pending-cards"',
                 "function openCardLink(", "replied.action_card"):
        assert hook in PAGE


# -- the card in a real browser -------------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_card_renders_and_applies_in_a_real_browser(tmp_path: Path) -> None:
    """The chat draws the proposal card (measured), Apply shows the result in
    place, and the link opens Settings at the Laya card."""
    import os
    import threading
    import time

    from host_runtime.web import AgentWebServer
    from integrations.browser import Browser

    config, layout = _config(tmp_path)
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout, model_transport=_Model()) as runtime:
        agent_web = AgentWeb(runtime, config_path=path)
        agent_web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        served = AgentWebServer(agent_web)
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def wait(expression: str, seconds: float = 30) -> object:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                value = browser._evaluate(expression)
                if value:
                    return value
                time.sleep(0.2)
            raise AssertionError(expression)

        def measure(selector: str) -> list[int]:
            return json.loads(str(browser._evaluate(
                "JSON.stringify((() => { const r = document.querySelector("
                + json.dumps(selector) + ").getBoundingClientRect();"
                " return [Math.round(r.width), Math.round(r.height)]; })())")))

        try:
            browser.navigate(served.address)
            wait('!document.getElementById("send").disabled')
            browser._evaluate(
                "(() => { const f = document.getElementById('message'); "
                "f.value = 'turn Laya to shadow'; "
                "document.getElementById('ask').requestSubmit(); })()")
            wait('!!document.querySelector(".action-card[data-status=\\"pending\\"]")')
            width, height = measure(".action-card")
            assert width >= 280 and height >= 150, (width, height)
            apply_width, apply_height = measure('.action-card button[data-action="apply"]')
            assert apply_width >= 44 and apply_height >= 44, (apply_width, apply_height)
            print(f"proposal card {width}x{height}, Apply {apply_width}x{apply_height}")
            assert "off" in str(browser._evaluate(
                'document.querySelector(".action-card .card-diff").innerText'))
            assert not browser._evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth")
            shots = os.environ.get("AEP_UI_SHOTS")
            if shots:
                browser.screenshot(Path(shots) / "proposal-card.png")
            browser._evaluate(
                'document.querySelector(\'.action-card button[data-action="apply"]\').click()')
            wait('!!document.querySelector(".action-card[data-status=\\"applied\\"]")')
            assert "Applied" in str(browser._evaluate(
                'document.querySelector(".action-card .card-status").innerText'))
            assert _host(path).laya.mode == "shadow"  # type: ignore[union-attr]
            browser._evaluate('document.querySelector(".action-card .card-link").click()')
            wait('document.getElementById("panel-settings").hasAttribute("data-open")')
            wait('document.getElementById("laya-mode").value === "shadow"')
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)
