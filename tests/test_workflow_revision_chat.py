"""Revising an installed Workflow in an Agent Web conversation (owner 2026-10-19).

End to end with a fake model: "change the Issue Key rule of <fixture>" leads
to get_workflow (the installed one, with its embedded script), revise_workflow,
draft_workflow on that draft, and an install card that says what changes.
Nothing installs until the person presses Install. Also: Capabilities'
"Revise in chat" in a real browser. A fixture modelled on the weekly report,
never the real one.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import (
    _browser_missing,
    _draft_cards,
    served,  # noqa: F401
)

from common.assets import WorkflowManifest
from host_runtime.conversations import ConversationTurnRequest
from host_runtime.web import AgentWeb
from models.contracts import ModelRequest, ModelResponse, ModelToolCall

RULE = '    return row.get("gtm") or "NO-KEY"\n'
SCRIPT = f"def issue_key(row):\n{RULE}\nprint(issue_key({{}}))\n"
EDITED = SCRIPT.replace(
    RULE, '    # No GTM-xxx: use the tracking issue.\n    return row.get("gtm") or "GH-76"\n'
)
NAME = "fixture-weekly-report"


def _namespace(web: AgentWeb) -> str:
    chat = web.runtime.chat_authoring
    assert chat is not None
    return chat.namespace


def _fixture(web: AgentWeb) -> Path:
    """Installed as the person's own Workflow, as a conversation draft would be."""
    namespace = _namespace(web)
    actor = web.runtime.actor
    manifest = WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {"namespace": namespace, "name": NAME, "version": "1.0.0"},
                "owner": {"type": "user", "id": actor},
                "visibility": "private",
                "lifecycle": "published",
                "business_approval": {
                    "status": "approved",
                    "reviewer": actor,
                    "evidence": "fixture",
                },
                "validation_refs": ["chat-candidate:wf-fixture:abc"],
            },
            "kind": "workflow",
            "description": "Weekly report fixture.",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False, "local_capabilities": ["lab.read-it"]},
            "input_contract": f"{namespace}.{NAME}.input.v1",
            "output_contract": f"{namespace}.{NAME}.output.v1",
            "parameters": [
                {
                    "name": "week_start",
                    "label": "First day of the week",
                    "kind": "date",
                    "scope": "runtime",
                    "required": True,
                }
            ],
            "steps": [
                {
                    "capability": {"namespace": "lab", "name": "read-it", "version": "1.0.0"},
                    "inputs": {"value": {"source": "fixed", "value": SCRIPT}},
                }
            ],
        }
    )
    path = web.runtime.layout.workflows / f"{namespace}__{NAME}__1.0.0.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return path


class _Reviser:
    """A model that does what the tool descriptions ask: read the installed
    Workflow, copy it into a revision draft, edit that draft, then answer."""

    def __init__(self) -> None:
        self.seen: list[str] = []
        self.calls: list[str] = []

    def generate(self, item: ModelRequest) -> ModelResponse:
        results = [m.text for m in item.messages if m.role == "tool"]
        self.seen = results
        step = len(results)
        call: tuple[str, dict[str, Any]]
        if step == 0:
            call = ("authoring__get_workflow", {"workflow": NAME})
        elif step == 1:
            call = ("authoring__revise_workflow", {"workflow": NAME, "title": "Issue Key rule"})
        elif step == 2:
            match = re.search(r'"candidate_id":\s*"(wf-[^"]+)"', results[-1])
            assert match, results[-1]
            call = (
                "authoring__draft_workflow",
                {
                    "title": "Issue Key rule",
                    "candidate_id": match.group(1),
                    "workflow": {
                        "name": NAME,
                        "description": "Weekly report fixture.",
                        "parameters": [
                            {
                                "name": "week_start",
                                "label": "First day of the week",
                                "kind": "date",
                                "scope": "runtime",
                                "required": True,
                            }
                        ],
                        "steps": [
                            {
                                "capability": "lab/read-it@1.0.0",
                                "inputs": {"value": {"source": "fixed", "value": EDITED}},
                            }
                        ],
                    },
                },
            )
        else:
            return ModelResponse(
                trace=item.trace,
                model_alias=item.model_alias,
                text="I revised the Issue Key rule; press Install on the card to use 1.0.1.",
            )
        self.calls.append(call[0])
        return ModelResponse(
            trace=item.trace,
            model_alias=item.model_alias,
            tool_calls=(ModelToolCall(call_id=f"c{step}", name=call[0], arguments=call[1]),),
        )

    def stream(self, item: ModelRequest) -> Any:
        raise NotImplementedError


def test_change_the_issue_key_rule_reads_revises_edits_and_shows_a_card(
    served: Any,  # noqa: F811
) -> None:
    web, _server, recorder, _ = served
    original = _fixture(web)
    before = original.read_bytes()
    model = _Reviser()
    web.runtime.agent.gateway.router.model = model
    session = web.create_conversation()["conversation"]["session_id"]
    replied = web.conversation_turn(
        ConversationTurnRequest(
            session_id=session, message=f"change the Issue Key rule of {NAME}: use GH-76"
        )
    )
    assert model.calls == [
        "authoring__get_workflow",
        "authoring__revise_workflow",
        "authoring__draft_workflow",
    ]
    # The installed Workflow's real script reached the model.
    assert "NO-KEY" in model.seen[0]
    (card,) = _draft_cards(replied["answer"])
    preview = card["preview"]
    namespace = _namespace(web)
    assert f"Revision of {namespace}/{NAME} 1.0.0 → 1.0.1" in preview
    assert "value +2/−1 lines" in preview
    assert [b["action"] for b in card["buttons"]][0] == "install"
    # Nothing installed and nothing ran without the press.
    workflows = web.runtime.layout.workflows
    assert sorted(p.name for p in workflows.glob(f"*{NAME}*")) == [original.name]
    assert recorder.calls == []

    decided = web.decide_card(card["card_id"], "install")
    assert decided["ok"], decided
    new = workflows / f"{namespace}__{NAME}__1.0.1.json"
    installed = json.loads(new.read_text(encoding="utf-8"))
    assert installed["steps"][0]["inputs"]["value"]["value"] == EDITED
    assert original.read_bytes() == before


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_revise_in_chat_opens_a_new_chat_with_the_request_typed_in(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web, server, _recorder, _ = served
    _fixture(web)
    namespace = _namespace(web)
    key = f"{namespace}/{NAME}@1.0.0"
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

    shots = os.environ.get("AEP_UI_SHOTS")
    button = ".detail-actions button.revise-in-chat"
    try:
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        sessions_before = {c["session_id"] for c in web.conversations()["conversations"]}
        browser._evaluate('document.getElementById("nav-capabilities").click()')
        wait('!!document.getElementById("cap-tab-workflows")')
        browser._evaluate('document.getElementById("cap-tab-workflows").click()')
        row = f".cap-item[data-key={json.dumps('installed:' + key)}]"
        wait(f"!!document.querySelector({json.dumps(row)})")
        browser._evaluate(f"document.querySelector({json.dumps(row)}).click()")
        wait(f"!!document.querySelector({json.dumps(button)})")
        size = json.loads(
            str(
                browser._evaluate(
                    "JSON.stringify((() => { const r = document.querySelector("
                    + json.dumps(button)
                    + ").getBoundingClientRect(); return [r.width, r.height]; })())"
                )
            )
        )
        assert size[0] >= 44 and size[1] >= 44, size
        browser._evaluate(
            f"document.querySelector({json.dumps(button)}).scrollIntoView({{block: 'center'}})"
        )
        for theme in ("light", "dark"):
            browser._evaluate(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
            time.sleep(0.3)
            if shots:
                browser.screenshot(Path(shots) / f"revise-in-chat-capabilities-{theme}.png")
        browser._evaluate(f"document.querySelector({json.dumps(button)}).click()")
        expected = f"Revise the installed Workflow {key}: "
        wait(
            'document.getElementById("panel-ask") && '
            f'document.getElementById("message").value === {json.dumps(expected)}'
        )
        assert browser._evaluate('document.activeElement.id === "message"')
        assert not browser._evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        for theme in ("light", "dark"):
            browser._evaluate(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
            time.sleep(0.3)
            if shots:
                browser.screenshot(Path(shots) / f"revise-in-chat-prefilled-{theme}.png")
        # A new conversation, and nothing was sent.
        after = {c["session_id"] for c in web.conversations()["conversations"]}
        (created,) = after - sessions_before
        assert web.conversations(created)["selected"]["messages"] == []
    finally:
        browser.close()
        browser.discard_profile()


def test_the_page_offers_revise_in_chat() -> None:
    from host_runtime.web_page import PAGE

    for hook in ("async function reviseInChat(", '"Revise in chat"', "revise-in-chat"):
        assert hook in PAGE
