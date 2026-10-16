"""The install card after a conversation drafts a Workflow or Skill (owner 2026-10-16).

"Earlier, after coding produced a Workflow, a small card popped up in the
conversation letting the person choose whether to apply (install) it
directly. Bring it back, so nobody has to go to Capabilities to install it."

Whichever backend drafted it (the Gateway's authoring tools, Claude Code or
Copilot in agent mode through the authoring MCP), the conversation shows one
card after the turn: Install (the press is the approval), Run once to try
(read-only Workflows), Not now (the draft stays in Capabilities). Drafts from
an external agent outside Agent Web keep waiting in Capabilities only.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from test_ai_proposed_changes import _config
from test_chat_authoring import Echo, Out, Recorder, spec, workflow
from test_chat_workflow_forms_telegram import _Scripted
from test_external_authoring import skill
from test_host_wiring import host_json

from common.action_cards import ActionCard, telegram_card
from common.assets import AssetIdentity, ExecutionDependencies
from host_runtime.contracts import WorkflowLaunchRequest
from host_runtime.conversation_backends import LocalConversationBackends
from host_runtime.conversations import (
    ConversationBackendSelectRequest,
    ConversationTurnRequest,
)
from host_runtime.external_authoring import ExternalAuthoring
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE

DRAFT = "authoring__draft_workflow"
INSTALL = "authoring__install_workflow"


def _lab(web: AgentWeb) -> Recorder:
    """lab/read-it (read) and lab/write-it (write) on this Agent's Bridge."""
    recorder = Recorder()
    installed = web.runtime.agent.gateway.bridge.installed
    for name, effect in (("read-it", "read"), ("write-it", "write")):
        installed.register(
            spec(name, effect), recorder, Echo, Out, ExecutionDependencies(central_required=False)
        )
    return recorder


def _with_default(capability: str) -> dict[str, Any]:
    body = workflow(capability)
    body["parameters"][0]["default"] = "2026-09"
    return body


class _Completed:
    def __init__(self, returncode: int, stdout: str) -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


class _AuthoringClaude:
    """A Claude Code in agent mode that calls AEP's authoring MCP (`aep`)
    over the real HTTP endpoint with the headers its run configuration gives."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.replies: list[dict[str, Any]] = []

    def __call__(
        self,
        argv: list[str],
        *,
        cwd: Path,
        input: str,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        env: Mapping[str, str],
    ) -> _Completed:
        if argv[1:3] == ["auth", "status"]:
            return _Completed(0, "")
        if "--mcp-config" not in argv:
            return _Completed(0, json.dumps({"type": "result", "result": "plain answer"}))
        config = json.loads(Path(argv[argv.index("--mcp-config") + 1]).read_text("utf-8"))
        server = config["mcpServers"]["aep"]
        for number, (name, arguments) in enumerate(self.calls):
            body = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": number,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
            ).encode()
            request = urllib.request.Request(
                server["url"],
                data=body,
                headers={**server["headers"], "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=60) as reply:
                self.replies.append(json.loads(reply.read())["result"]["structuredContent"])
        self.calls = []
        return _Completed(0, json.dumps({"type": "result", "result": "Submitted the draft."}))


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[AgentWeb, AgentWebServer, Recorder, _AuthoringClaude]]:
    config, layout = _config(tmp_path)
    path = host_json(tmp_path, config)
    claude = _AuthoringClaude()
    with build_runtime(config, layout=layout) as runtime:
        backends = LocalConversationBackends(
            layout.workspace_root, which=lambda name: f"C:/fake/{name}.exe", runner=claude
        )
        web = AgentWeb(runtime, config_path=path, conversation_backends=backends)
        web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        recorder = _lab(web)
        server = AgentWebServer(web)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield web, server, recorder, claude
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _gateway_turn(web: AgentWeb, session: str, message: str, *replies: dict[str, Any]) -> Any:
    web.runtime.agent.gateway.router.model = _Scripted(*replies)
    return web.conversation_turn(ConversationTurnRequest(session_id=session, message=message))


def _draft_cards(answer: dict[str, Any]) -> list[dict[str, Any]]:
    return [card for card in answer.get("action_cards", []) if card["card_id"].startswith("dr-")]


def _stored(web: AgentWeb, session: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = web.conversations(session)["selected"]["messages"]
    return messages


# -- the Gateway's own authoring tools (and the coding Skill, which uses them) -------


def test_a_gateway_draft_shows_the_card_and_install_makes_it_usable_here(served: Any) -> None:
    web, _server, recorder, _ = served
    session = web.create_conversation()["conversation"]["session_id"]
    replied = _gateway_turn(
        web,
        session,
        "make me a Workflow that echoes a month",
        {"tools": [(DRAFT, {"title": "Echo the month", "workflow": workflow("read-it")})]},
        {"text": "Drafted it."},
    )
    (card,) = _draft_cards(replied["answer"])
    assert card["kind"] == "draft_install" and card["status"] == "pending"
    assert card["title"] == "Install the Workflow “Echo the month”?"
    preview = card["preview"]
    assert "engineering/echo-month@1.0.0 · revision 1 · drafted by this conversation" in preview
    assert "What it does: Echo the month." in preview
    assert "1. lab/read-it@1.0.0 (read)" in preview
    assert "Will become a form with fields: Which month? (text, required)" in preview
    assert "Check: passed" in preview
    # Required month without a default: nothing to try with, so no Try button.
    assert [b["action"] for b in card["buttons"]] == ["install", "not_now"]
    assert recorder.calls == [] and not list(web.runtime.layout.workflows.glob("*echo*"))
    stored = _stored(web, session)[-1]
    assert stored["action_cards"][0]["card_id"] == card["card_id"]
    assert f"[card {card['card_id']}]" in stored["tool_summary"]

    decided = web.decide_card(card["card_id"], "install")
    assert decided["ok"] and decided["card"]["status"] == "installed"
    assert decided["card"]["outcome_ok"] is True and decided["card"]["buttons"] == []
    assert decided["card"]["link"]["asset"] == "engineering/echo-month@1.0.0"
    assert (web.runtime.layout.workflows / "engineering__echo-month__1.0.0.json").is_file()
    after = _stored(web, session)[-1]
    assert after["action_cards"][0]["status"] == "installed"
    form = after["workflow_form"]
    assert form["origin"] == "install" and form["workflow"]["name"] == "echo-month"
    # Usable at once in the same chat: "run echo-month" is its form, and the
    # form's Run (/api/workflows/run with this session) runs it.
    asked = web.conversation_turn(
        ConversationTurnRequest(session_id=session, message="run echo-month")
    )
    assert asked["answer"]["workflow_form"]["workflow"]["name"] == "echo-month"
    ran = web.launch_workflow(
        WorkflowLaunchRequest(
            workflow=AssetIdentity(namespace="engineering", name="echo-month", version="1.0.0"),
            arguments={"month": "2026-10"},
            idempotency_key="card-run-1",
            session_id=session,
        )
    )
    assert recorder.calls == ["2026-10"], ran
    again = web.decide_card(card["card_id"], "install")
    assert not again["ok"] and again["code"] == "draft_installed"


def test_a_revision_replaces_the_card_and_one_turn_shows_one_card(served: Any) -> None:
    web, _server, _recorder, _ = served
    session = web.create_conversation()["conversation"]["session_id"]
    first = _gateway_turn(
        web,
        session,
        "draft it",
        {"tools": [(DRAFT, {"title": "Echo", "workflow": workflow("read-it")})]},
        {"text": "Drafted."},
    )
    (old,) = _draft_cards(first["answer"])
    candidate = web.runtime.chat_authoring.candidates(web.runtime.actor)[0].candidate_id
    revised = dict(workflow("read-it"), description="Echo the month, revised.")
    second = _gateway_turn(
        web,
        session,
        "change the description, twice",
        {"tools": [(DRAFT, {"title": "Echo", "workflow": revised, "candidate_id": candidate})]},
        {
            "tools": [
                (
                    DRAFT,
                    {
                        "title": "Echo",
                        "workflow": dict(revised, description="Echo the month, final."),
                        "candidate_id": candidate,
                    },
                )
            ]
        },
        {"text": "Revised."},
    )
    (new,) = _draft_cards(second["answer"])  # two revisions in one turn: one card
    assert "revision 3" in new["preview"] and "Echo the month, final." in new["preview"]
    messages = _stored(web, session)
    shown = [
        card
        for message in messages
        for card in message.get("action_cards", [])
        if card["card_id"].startswith("dr-")
    ]
    assert [(c["card_id"], c["status"]) for c in shown] == [
        (old["card_id"], "superseded"),
        (new["card_id"], "pending"),
    ]
    assert web.decide_card(old["card_id"], "install")["code"] == "draft_superseded"
    # A turn that drafts nothing adds no card.
    quiet = _gateway_turn(web, session, "thanks", {"text": "You're welcome."})
    assert _draft_cards(quiet["answer"]) == []


def test_not_now_keeps_the_draft_in_capabilities(served: Any) -> None:
    web, _server, _recorder, _ = served
    session = web.create_conversation()["conversation"]["session_id"]
    replied = _gateway_turn(
        web,
        session,
        "draft it",
        {"tools": [(DRAFT, {"title": "Echo", "workflow": workflow("write-it")})]},
        {"text": "Drafted."},
    )
    (card,) = _draft_cards(replied["answer"])
    assert "Its steps change things" in card["effects"][0]
    assert [b["action"] for b in card["buttons"]] == ["install", "not_now"]
    decided = web.decide_card(card["card_id"], "not_now")
    assert decided["ok"] and decided["card"]["status"] == "not_now"
    assert "Kept as a draft in Capabilities" in decided["card"]["outcome"]
    (draft,) = web.drafts()["drafts"]
    assert draft["asset"] == "engineering/echo-month@1.0.0"
    assert not list(web.runtime.layout.workflows.glob("*echo*"))
    assert _stored(web, session)[-1]["action_cards"][0]["status"] == "not_now"
    # Capabilities still installs it later.
    assert web.draft_action("install", draft["candidate_id"])["ok"]


def test_the_models_install_request_is_answered_on_the_card(served: Any) -> None:
    web, _server, _recorder, _ = served
    session = web.create_conversation()["conversation"]["session_id"]
    _gateway_turn(
        web,
        session,
        "draft it",
        {"tools": [(DRAFT, {"title": "Echo", "workflow": workflow("write-it")})]},
        {"text": "Drafted."},
    )
    candidate = web.runtime.chat_authoring.candidates(web.runtime.actor)[0].candidate_id
    asked = _gateway_turn(
        web,
        session,
        "install it",
        {"tools": [(INSTALL, {"candidate_id": candidate})]},
        {"text": "It waits for your approval."},
    )
    (card,) = _draft_cards(asked["answer"])  # the earlier card moved down, not doubled
    statuses = [
        card["status"]
        for message in _stored(web, session)
        for card in message.get("action_cards", [])
    ]
    assert statuses == ["superseded", "pending"]
    # No second, old-style approval card for the same install.
    assert web.approvals(session)["approvals"] == []
    (pending,) = web.runtime.chat_authoring.approvals(web.runtime.actor)
    assert web.decide_card(card["card_id"], "install")["ok"]
    assert web.runtime.chat_authoring.approval(pending.approval_id, web.runtime.actor).status == (
        "approved"
    )


def test_run_once_to_try_only_for_read_only_and_keeps_the_card_open(served: Any) -> None:
    web, _server, recorder, _ = served
    session = web.create_conversation()["conversation"]["session_id"]
    replied = _gateway_turn(
        web,
        session,
        "draft it",
        {"tools": [(DRAFT, {"title": "Echo", "workflow": _with_default("read-it")})]},
        {"text": "Drafted."},
    )
    (card,) = _draft_cards(replied["answer"])
    assert [b["action"] for b in card["buttons"]] == ["install", "try", "not_now"]
    tried = web.decide_card(card["card_id"], "try")
    assert tried["ok"] and tried["card"]["status"] == "pending"
    assert tried["card"]["status_label"] == "Test run succeeded"
    assert "Test run: succeeded, 1 of 1 steps succeeded" in tried["card"]["preview"]
    assert recorder.calls == ["2026-09"]
    # Nothing was installed by trying; Install still works.
    assert not list(web.runtime.layout.workflows.glob("*echo*"))
    assert web.decide_card(card["card_id"], "install")["ok"]


def test_a_draft_changed_after_its_card_is_not_installed_from_it(served: Any) -> None:
    web, _server, _recorder, _ = served
    session = web.create_conversation()["conversation"]["session_id"]
    replied = _gateway_turn(
        web,
        session,
        "draft it",
        {"tools": [(DRAFT, {"title": "Echo", "workflow": workflow("read-it")})]},
        {"text": "Drafted."},
    )
    (card,) = _draft_cards(replied["answer"])
    chat = web.runtime.chat_authoring
    candidate = chat.candidates(web.runtime.actor)[0]
    # Revised outside this conversation (e.g. an external agent): stale card.
    chat.draft(
        web.runtime.actor,
        None,
        "Echo",
        dict(workflow("read-it"), description="Something else."),
        candidate.candidate_id,
    )
    refused = web.decide_card(card["card_id"], "install")
    assert not refused["ok"] and refused["code"] == "draft_stale"
    assert not list(web.runtime.layout.workflows.glob("*echo*"))


# -- agent mode: Claude Code through the authoring MCP ---------------------------------


def _claude_session(web: AgentWeb) -> str:
    session = web.create_conversation()["conversation"]["session_id"]
    chosen = web.select_conversation_backend(
        ConversationBackendSelectRequest(
            session_id=session, backend="claude_code", public_context=True
        )
    )
    assert chosen["ok"], chosen
    web.agent_mode.save_settings({"claude_code": True})
    return str(session)


def test_agent_mode_drafts_show_the_card_in_their_conversation(served: Any) -> None:
    web, _server, _recorder, claude = served
    session = _claude_session(web)
    claude.calls = [
        ("aep_submit_workflow", {"workflow": workflow("read-it"), "title": "Echo the month"}),
        ("aep_submit_skill", {"skill": skill(), "title": "Echo helper"}),
    ]
    done = web.conversation_turn(ConversationTurnRequest(session_id=session, message="build it"))
    assert done["ok"], done
    assert all(reply["ok"] for reply in claude.replies), claude.replies
    cards = _draft_cards(done["answer"])
    assert {card["title"] for card in cards} == {
        "Install the Workflow “Echo the month”?",
        "Install the Skill “Echo helper”?",
    }
    workflow_card = next(c for c in cards if "Workflow" in c["title"])
    skill_card = next(c for c in cards if "Skill" in c["title"])
    assert "drafted by Claude Code" in workflow_card["preview"]
    assert (
        "Alias: /echo" in skill_card["preview"]
        and "read → lab/read-it@1.0.0" in (skill_card["preview"])
    )
    chat = web.runtime.chat_authoring
    (candidate,) = chat.candidates(web.runtime.actor)
    assert candidate.session_id == session and candidate.source == "external:claude-code"
    # The next turn tells the agent the card is there.
    assert "Install the Workflow" in done["conversation"]["messages"][-1]["tool_summary"]

    installed = web.decide_card(skill_card["card_id"], "install")
    assert installed["ok"] and "after Agent Web restarts" in installed["card"]["outcome"]
    assert (web.runtime.layout.skills / "engineering__echo-helper__1.0.0.json").is_file()
    assert web.decide_card(workflow_card["card_id"], "install")["ok"]
    assert (web.runtime.layout.workflows / "engineering__echo-month__1.0.0.json").is_file()


def test_agent_mode_install_request_waits_on_the_card_and_status_follows(served: Any) -> None:
    web, _server, _recorder, claude = served
    session = _claude_session(web)
    claude.calls = [("aep_submit_workflow", {"workflow": workflow("write-it"), "title": "Echo"})]
    web.conversation_turn(ConversationTurnRequest(session_id=session, message="build it"))
    candidate = str(claude.replies[-1]["candidate_id"])
    claude.calls = [("aep_install_workflow", {"candidate_id": candidate})]
    asked = web.conversation_turn(ConversationTurnRequest(session_id=session, message="install"))
    approval_id = str(claude.replies[-1]["approval_id"])
    (card,) = _draft_cards(asked["answer"])
    assert web.approvals(session)["approvals"] == []
    # Still listed for review in Capabilities, as every external request is.
    assert [a["approval_id"] for a in web.external_approvals()["approvals"]] == [approval_id]
    assert web.decide_card(card["card_id"], "install")["ok"]
    status = web.runtime.chat_authoring.external_view(
        web.runtime.chat_authoring.approval(approval_id, web.runtime.actor)
    )
    assert status["status"] == "approved" and status["installed_as"] == (
        "engineering/echo-month@1.0.0"
    )


def test_the_authoring_endpoint_attributes_only_a_running_turns_token(served: Any) -> None:
    web, server, _recorder, _ = served
    port = server.server_address[1]

    def submit(token: str) -> dict[str, Any]:
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "aep_submit_workflow",
                    "arguments": {"workflow": workflow("read-it"), "title": "Echo"},
                },
            }
        ).encode()
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/mcp/authoring",
            data=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as reply:
            result: dict[str, Any] = json.loads(reply.read())["result"]["structuredContent"]
        return result

    chat = web.runtime.chat_authoring
    plain = submit(web.assistant_token)
    assert chat.candidate(str(plain["candidate_id"]), web.runtime.actor).session_id is None
    web._authoring_turns["turn-token"] = ("conversation-x", "copilot")
    turned = submit("turn-token")
    item = chat.candidate(str(turned["candidate_id"]), web.runtime.actor)
    assert item.session_id == "conversation-x" and item.source == "external:copilot"
    web._authoring_turns.clear()
    with pytest.raises(urllib.error.HTTPError) as refused:
        submit("turn-token")
    assert refused.value.code == 401


# -- an external agent outside Agent Web: unchanged ---------------------------------------


def test_an_external_agent_outside_agent_web_still_waits_in_capabilities(served: Any) -> None:
    web, _server, _recorder, _ = served
    session = web.create_conversation()["conversation"]["session_id"]
    outside = ExternalAuthoring(web.runtime.chat_authoring, web.runtime.actor, "claude-code")
    submitted = outside.submit_workflow(workflow("write-it"), "Echo")
    asked = outside.install_workflow(str(submitted["candidate_id"]))
    quiet = _gateway_turn(web, session, "hello", {"text": "Hi."})
    assert _draft_cards(quiet["answer"]) == []
    assert [a["approval_id"] for a in web.external_approvals()["approvals"]] == [
        asked["approval_id"]
    ]
    assert [d["candidate_id"] for d in web.drafts()["drafts"]] == [submitted["candidate_id"]]
    assert web.draft_cards.store.records() == []


# -- Telegram -------------------------------------------------------------------------------


def test_telegram_shows_the_card_with_install_and_not_now(served: Any, tmp_path: Path) -> None:
    from test_telegram_ingress import OWNER, FakeTransport, ingress, poll, update
    from test_telegram_workflow_flow import _tap

    web, _server, _recorder, _ = served
    transport = FakeTransport([[update(1, OWNER, "make an echo Workflow")]])
    item, agent, _ = ingress(tmp_path / "bot", transport)
    chat = web.runtime.chat_authoring
    agent.gateway.host_tools = chat.tools
    item.approvals = chat
    item.cards = web
    agent.gateway.router.model = _Scripted(
        {"tools": [(DRAFT, {"title": "Echo", "workflow": _with_default("read-it")})]},
        {"text": "Drafted."},
    )
    delivery = poll(item).deliveries[0]
    reply = delivery.reply or ""
    assert "Drafted." in reply and "Install the Workflow “Echo”?" in reply
    assert "Will become a form with fields" in reply
    [row] = delivery.buttons
    # Telegram: Install / Not now only, as its approval rules already allow.
    assert [label for label, _ in row] == ["Install", "Not now"]
    transport.batches.append([_tap(2, OWNER, row[0][1])])
    installed = poll(item).deliveries[0]
    assert "Installed" in (installed.reply or "") and installed.buttons == ()
    assert (web.runtime.layout.workflows / "engineering__echo-month__1.0.0.json").is_file()


def test_the_telegram_card_text_names_where_to_go_when_closed() -> None:
    card = ActionCard(
        card_id="dr-0123456789ab",
        kind="draft_install",
        title="Workflow “Echo”",
        status="not_now",
        status_label="Not now",
        outcome="Kept as a draft in Capabilities; install it there any time.",
        message="x",
    )
    text, buttons = telegram_card(card)
    assert "Kept as a draft in Capabilities" in text and buttons == ()


def test_the_page_draws_draft_cards_with_their_run_form() -> None:
    for hook in ('startsWith("dr-")', "function draftCardDecided(", 'origin === "install"'):
        assert hook in PAGE


# -- the card in a real browser -----------------------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_card_renders_installs_and_opens_the_run_form_in_a_real_browser(
    served: Any, tmp_path: Path
) -> None:
    import os

    from integrations.browser import Browser

    web, server, _recorder, _ = served
    web.runtime.agent.gateway.router.model = _Scripted(
        {"tools": [(DRAFT, {"title": "Echo the month", "workflow": workflow("read-it")})]},
        {"text": "Drafted the Workflow."},
    )
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
        size: list[int] = json.loads(
            str(
                browser._evaluate(
                    "JSON.stringify((() => { const r = document.querySelector("
                    + json.dumps(selector)
                    + ").getBoundingClientRect();"
                    " return [Math.round(r.width), Math.round(r.height)]; })())"
                )
            )
        )
        return size

    card = '.action-card[data-card-id^="dr-"]'
    try:
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        browser._evaluate(
            "(() => { const f = document.getElementById('message'); "
            "f.value = 'make a Workflow that echoes a month'; "
            "document.getElementById('ask').requestSubmit(); })()"
        )
        wait(f"!!document.querySelector({json.dumps(card + '[data-status=pending]')})")
        width, height = measure(card)
        assert width >= 280 and height >= 150, (width, height)
        install_w, install_h = measure(card + ' button[data-action="install"]')
        later_w, later_h = measure(card + ' button[data-action="not_now"]')
        assert install_w >= 44 and install_h >= 44, (install_w, install_h)
        assert later_w >= 44 and later_h >= 44, (later_w, later_h)
        print(f"draft card {width}x{height}, Install {install_w}x{install_h}")
        preview = str(browser._evaluate(f"document.querySelector({json.dumps(card)}).innerText"))
        assert "Will become a form with fields: Which month?" in preview
        assert not browser._evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shots = os.environ.get("AEP_UI_SHOTS")
        if shots:
            browser.screenshot(Path(shots) / "draft-card.png")
        browser._evaluate(
            f"document.querySelector({json.dumps(card + ' button[data-action=install]')}).click()"
        )
        wait(f"!!document.querySelector({json.dumps(card + '[data-status=installed]')})")
        wait('!!document.querySelector(".chat-run-form[open] .chat-run-actions button.go")')
        run_w, run_h = measure(".chat-run-form[open] .chat-run-actions button.go")
        assert run_w >= 44 and run_h >= 44, (run_w, run_h)
        assert (web.runtime.layout.workflows / "engineering__echo-month__1.0.0.json").is_file()
        if shots:
            browser.screenshot(Path(shots) / "draft-card-installed.png")
    finally:
        browser.close()
        browser.discard_profile()
