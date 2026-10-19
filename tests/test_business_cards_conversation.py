"""Business cards in a real Host, through Agent Web's Gateway chat (docs/phases/BUSINESS_CARDS.md).

A fake model plays the conversation end to end: "parse this card and store
it" with a photo attached, then "the EXN org chart", then "X has left", then
"undo that". The tools exist only while the Skill is switched on; the
writes run without an approval card; the chart's PNG is kept on the answer
and served to the page; the legend is in the answer text. Synthetic people,
fake model, no network.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_ai_proposed_changes import LAYA
from test_business_cards_capabilities import _context
from test_host_models import binding, endpoint
from test_host_wiring import host_json, ready

from capabilities.business_cards.handlers import ADD_CARD_SPEC, WRITE_SPECS
from capabilities.business_cards.manifest import CARDS_SKILL, business_cards_skill
from capabilities.runtime import LocalPolicy
from host_runtime.business_cards_tools import CHART_TOOL, TOOLS, _tool, business_cards_tools
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent, ModelToolCall

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d4944415478da63646060f80f0002040101b5d1c5a70000000049454e44ae426082"
)
CARD = {
    "name": "周範例",
    "romanised_name": "Fan-Li Chou",
    "romanised_name_printed": "Fan-Li Chou (printed under the Chinese name)",
    "company": "EXN 範例網通",
    "business_group": "網通事業群",
    "division": "研發處",
    "department": "射頻部",
    "title": "經理",
    "mobile": "0912-000-001",
    "email": "fanli.chou@exn.example",
    "uncertain": ["email"],
}


class Conversation:
    """One scripted reply per model call; records what it was shown."""

    def __init__(self) -> None:
        self.script: list[dict[str, Any]] = []
        self.requests: list[ModelRequest] = []

    def then(self, *replies: dict[str, Any]) -> None:
        self.script.extend(replies)

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        reply = self.script.pop(0)
        if callable(reply.get("tools")):
            reply = {**reply, "tools": reply["tools"](request)}
        calls = tuple(
            ModelToolCall(call_id=f"c{len(self.requests)}-{index}", name=name, arguments=args)
            for index, (name, args) in enumerate(reply.get("tools", []))
        )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            text=reply.get("text", ""),
            tool_calls=calls,
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError

    def tool_results(self) -> list[str]:
        return [m.text for m in self.requests[-1].messages if m.role == "tool"]


@pytest.fixture
def web(tmp_path: Path) -> Iterator[tuple[AgentWeb, Conversation]]:
    # A colleague's install: owner mode, the product default.
    config, layout = ready(
        tmp_path,
        config_changes={
            "laya": LAYA,
            "local_owner_grants": True,
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model="fixture-model")],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            ),
        },
    )
    layout.skills.mkdir(parents=True, exist_ok=True)
    skill = business_cards_skill()
    (layout.skills / "engineering__business-cards__1.0.0.json").write_text(
        skill.model_dump_json(), encoding="utf-8"
    )
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        agent_web = AgentWeb(runtime, config_path=path)
        agent_web.start_laya_tunnel = lambda settings=None: None  # type: ignore[method-assign]
        model = Conversation()
        runtime.agent.gateway.router.model = model
        yield agent_web, model


def _tools(web: AgentWeb) -> list[str]:
    host_tools = web.runtime.agent.gateway.host_tools
    assert host_tools is not None
    return [item.tool.name for item in host_tools()]


def test_the_tools_follow_the_skills_switch_and_writes_are_confirmed(
    web: tuple[AgentWeb, Conversation],
) -> None:
    agent_web, _ = web
    gateway = agent_web.runtime.agent.gateway
    assert gateway.bridge.installed.get(ADD_CARD_SPEC.identity) is not None
    names = _tools(agent_web)
    assert "cards__add_card" in names and CHART_TOOL in names
    assert "cards__set_status" in names and "cards__undo" in names
    first = next(t for t in business_cards_tools(gateway) if t.tool.name == "cards__add_card")
    assert "uncertain" in first.tool.description and first.tool.input_schema is not None
    policy = gateway.bridge.policy
    assert isinstance(policy, LocalPolicy)
    assert {spec.identity.key for spec in WRITE_SPECS} <= policy.confirmed_writes
    # Switched off: the tools are gone.
    gateway.router.commands.skills.remove(CARDS_SKILL)
    assert not any(name.startswith("cards__") for name in _tools(agent_web))


def _turn(agent_web: AgentWeb, session: str, message: str, files: list[str] | None = None) -> Any:
    return agent_web.conversation_turn(
        ConversationTurnRequest(session_id=session, message=message, attachments=files or [])
    )


def test_store_a_card_draw_the_chart_record_a_departure_and_undo_it(
    web: tuple[AgentWeb, Conversation],
) -> None:
    agent_web, model = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    uploaded = agent_web.add_attachment(session, "card.png", PNG)
    assert uploaded["ok"], uploaded
    file_id = uploaded["attachment"]["file_id"]
    photo_path = agent_web.attachments.get(session, file_id).path

    # 1. "Parse this card and store it."
    model.then(
        {"tools": [("cards__add_card", {**CARD, "image_path": photo_path})]},
        {"text": "已存：周範例，EXN 範例網通 研發處 射頻部 經理。Email 我不太確定，請確認。"},
    )
    replied = _turn(agent_web, session, "parse this card and store it", [file_id])
    assert replied["ok"], replied
    seen = model.requests[0].messages[-1]
    assert seen.images and seen.images[0].startswith("data:image/png;base64,")
    stored = json.loads(model.tool_results()[-1])
    assert "approval" not in json.dumps(stored)
    assert stored["host"]["status"] == "succeeded", stored
    assert stored["host"]["data"]["outcome"] == "created"
    assert stored["host"]["data"]["uncertain"] == ["email"]

    # A second card under the same manager, with a line the person stated.
    model.then(
        {
            "tools": [
                (
                    "cards__add_card",
                    {
                        "name": "吳測試",
                        "company": "EXN 範例網通",
                        "division": "研發處",
                        "department": "射頻部",
                        "title": "工程師",
                    },
                ),
                (
                    "cards__set_reporting_line",
                    {
                        "person": {"name": "吳測試"},
                        "manager": {"name": "Fan-Li Chou"},
                        "evidence_kind": "user",
                        "evidence_ref": "the person said so",
                    },
                ),
            ]
        },
        {"text": "已存吳測試，並記下他向周範例報告。"},
    )
    assert _turn(agent_web, session, "also this one; he reports to Chou")["ok"]

    # 2. "EXN org chart": the PNG is on the answer, the legend in its text.
    model.then(
        {"tools": [(CHART_TOOL, {"company": "EXN"})]},
        {"text": "這是 EXN 的組織圖。"},
    )
    charted = _turn(agent_web, session, "EXN org chart")
    assert charted["ok"], charted
    answer = charted["answer"]["answer"]
    assert "這是 EXN 的組織圖" in answer
    assert "| 吳測試 | 周範例 | 使用者告知（the person said so） | 否（實線） |" in answer
    files = charted["conversation"]["messages"][-1]["attachments"]
    image = next(item for item in files if item["kind"] == "image")
    served = agent_web.conversation_file(session, image["path"])
    assert served is not None and served[1] == "image/png"
    assert served[0][:8] == b"\x89PNG\r\n\x1a\n"
    # Only a file listed on this conversation's answers is served.
    assert agent_web.conversation_file(session, photo_path) is None
    assert agent_web.conversation_file("nope", image["path"]) is None

    # 3. "周範例 has left."
    model.then(
        {
            "tools": [
                (
                    "cards__set_status",
                    {
                        "person": {"name": "周範例"},
                        "status": "left",
                        "reason": "the person said he left",
                        "said_by": agent_web.runtime.actor,
                    },
                )
            ]
        },
        {"text": "已記錄周範例離職，可以復原。"},
    )
    assert _turn(agent_web, session, "周範例 has left")["ok"]
    status = json.loads(model.tool_results()[-1])
    change = re.search(r'"change_id":\s*"(c-[^"]+)"', json.dumps(status))
    assert change is not None
    model.then(
        {"tools": [(CHART_TOOL, {"company": "EXN"})]},
        {"text": "更新後的組織圖。"},
    )
    after = _turn(agent_web, session, "EXN org chart again")
    assert "已離職的 1 人沒有畫出" in after["answer"]["answer"]

    # 4. "Undo that."
    model.then(
        {"tools": [("cards__undo", {"change_id": change.group(1)})]},
        {"text": "已復原：周範例回到在職。"},
    )
    assert _turn(agent_web, session, "undo that")["ok"]
    model.then({"tools": [("cards__find", {"query": "周範例"})]}, {"text": "周範例在職。"})
    assert _turn(agent_web, session, "is Chou still there?")["ok"]
    found = json.loads(model.tool_results()[-1])
    assert '"status": "active"' in json.dumps(found)
    # Nothing waited for an approval button.
    assert agent_web.approvals(session)["approvals"] == []


def test_the_page_shows_an_answers_picture_through_the_token_guarded_route() -> None:
    from host_runtime.web_page import PAGE

    assert "function answerImage(session, file)" in PAGE
    assert '"/api/conversations/file?" + query' in PAGE
    assert 'if (file.kind === "image") said.parentNode.append(answerImage(' in PAGE


class _FailingBridge:
    """A Bridge whose every call fails with one code and the generic message."""

    def __init__(self, code: str, message: str = "Capability invocation did not complete") -> None:
        self.code, self.message = code, message
        self.installed = type("I", (), {"get": lambda self, identity: object()})()
        self.calls: list[Any] = []

    async def execute(self, invocation: Any) -> Any:
        from common.execution import CapabilityResult, Failure

        self.calls.append(invocation)
        return CapabilityResult(
            trace=invocation.context.trace,
            status="failed",
            failure=Failure(code=self.code, message=self.message),
            handler_invoked=True,
        )


def _failed(code: str, message: str = "Capability invocation did not complete") -> Any:
    gateway = type("G", (), {})()
    gateway.bridge = _FailingBridge(code, message)
    name, spec, description, schema = next(t for t in TOOLS if t[0] == "cards__harvest_signatures")
    tool = _tool(gateway, name, spec, description, schema)

    async def call() -> Any:
        return await tool.handler(_context(), {"domain": "example.com"})

    return asyncio.run(call())


def test_a_failed_tool_says_what_failed_not_a_generic_line() -> None:
    """Live test 2026-10-20: the model got only "Capability invocation did not
    complete" and told the person to check Settings. The failure now carries
    the code and a short, accurate sentence; Settings only when it is the cause."""
    unread = _failed("message_unknown")
    assert unread.status == "failed" and unread.failure is not None
    assert unread.failure.code == "message_unknown"
    assert "Capability invocation did not complete" not in unread.failure.message
    assert "message_unknown" in unread.failure.message
    assert "Settings" not in unread.failure.message
    scope = _failed("folder_unknown").failure
    assert "Settings" in scope.message and "folder_unknown" in scope.message
    nobody = _failed("person_unknown").failure
    assert "person_unknown" in nobody.message and "Settings" not in nobody.message
    # A specific message from the Bridge (where the input was wrong) is kept.
    kept = _failed("invalid_input", "Invalid input at domain: string_pattern_mismatch").failure
    assert kept.message.endswith("Invalid input at domain: string_pattern_mismatch")
    # An unknown code still names itself.
    other = _failed("something_new").failure
    assert "something_new" in other.message
    assert "Capability invocation did not complete" not in other.message
    from capabilities.business_cards.manifest import PROCEDURE

    assert "IF A TOOL FAILS" in PROCEDURE


def test_the_host_tool_drops_who_said_it_from_the_models_arguments() -> None:
    from host_runtime.business_cards_tools import TOOLS

    status = next(schema for name, _, _, schema in TOOLS if name == "cards__set_status")
    assert "said_by" not in status["properties"]
    bridge = _FailingBridge("person_unknown")
    gateway = type("G", (), {"bridge": bridge})()
    name, spec, description, schema = next(t for t in TOOLS if t[0] == "cards__set_status")
    tool = _tool(gateway, name, spec, description, schema)

    async def call() -> Any:
        return await tool.handler(
            _context(), {"person": {"name": "X"}, "status": "left", "said_by": "使用者"}
        )

    asyncio.run(call())
    assert bridge.calls[0].arguments == {"person": {"name": "X"}, "status": "left"}


def test_the_person_can_confirm_a_field_in_chat() -> None:
    from capabilities.business_cards.manifest import PROCEDURE

    edit = next(schema for name, _, _, schema in TOOLS if name == "cards__edit_person")
    assert edit["properties"]["confirm"]["items"]["enum"][0] == "name"
    assert edit["required"] == ["person"]
    assert "needs_confirmation" in PROCEDURE and "email 正確" in PROCEDURE


def test_a_romanised_name_not_printed_on_the_card_is_dropped(
    web: tuple[AgentWeb, Conversation],
) -> None:
    """Live test 2026-10-20: card A had no English name, yet the model stored
    "Yanji Fan" and bent the email to match it. The Host keeps a romanised
    name only when the model says where it is printed, and marks an email
    that looks made to match a dropped name as needing confirmation."""
    agent_web, model = web
    session = agent_web.create_conversation()["conversation"]["session_id"]
    invented = {
        "name": "范例",
        "romanised_name": "Yanji Fan",
        "company": "WNC 範例",
        "email": "Yanji.fan@wnc.example",
        "uncertain": ["romanised_name"],
    }
    model.then(
        {"tools": [("cards__add_card", invented)]},
        {"text": "已存：范例。"},
    )
    assert _turn(agent_web, session, "store this card")["ok"]
    stored = json.loads(model.tool_results()[-1])["host"]["data"]
    assert stored["dropped"] == [
        {"field": "romanised_name", "value": "Yanji Fan", "reason": "not_on_card"}
    ]
    assert "email" in stored["uncertain"] and "email" in stored["needs_confirmation"]
    model.then({"tools": [("cards__find", {"query": "范例"})]}, {"text": "找到了。"})
    assert _turn(agent_web, session, "find 范例")["ok"]
    person = json.loads(model.tool_results()[-1])["host"]["data"]["people"][0]
    assert person["romanised_name"] == ""
    # An evidence line that is the email is no evidence.
    model.then(
        {
            "tools": [
                (
                    "cards__add_card",
                    {
                        **invented,
                        "name": "范二",
                        "email": "yanji.fan2@wnc.example",
                        "romanised_name_printed": "yanji.fan2@wnc.example",
                    },
                )
            ]
        },
        {"text": "已存。"},
    )
    assert _turn(agent_web, session, "and this one")["ok"]
    second = json.loads(model.tool_results()[-1])["host"]["data"]
    assert [item["field"] for item in second["dropped"]] == ["romanised_name"]
    # Printed on the card: kept.
    model.then(
        {
            "tools": [
                (
                    "cards__add_card",
                    {
                        "name": "范瑞",
                        "romanised_name": "Ryan Fan",
                        "romanised_name_printed": "Ryan R.J. Fan, under the Chinese name",
                        "company": "WNC 範例",
                        "email": "ryan.rj.fan@wnc.example",
                    },
                )
            ]
        },
        {"text": "已存。"},
    )
    assert _turn(agent_web, session, "a third card")["ok"]
    kept = json.loads(model.tool_results()[-1])["host"]["data"]
    assert kept["dropped"] == [] and kept["uncertain"] == []


def test_the_tools_and_skill_say_a_romanised_name_must_be_printed() -> None:
    from capabilities.business_cards.manifest import PROCEDURE

    add = next(schema for name, _, _, schema in TOOLS if name == "cards__add_card")
    assert "printed" in add["properties"]["romanised_name"]["description"]
    assert "romanised_name_printed" in add["properties"]
    assert "never derive it from the email" in PROCEDURE
    assert "never change the email to match a name" in PROCEDURE
