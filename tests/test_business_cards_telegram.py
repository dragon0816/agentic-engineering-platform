"""Business cards over Telegram (docs/phases/BUSINESS_CARDS.md §7).

A photo message reaches the model as an image, the model stores the card
with `cards__add_card`, and an org chart comes back as a `sendPhoto` after
the text reply, whose text carries the legend. Over the fake Bot API of
`test_telegram_ingress`; no socket is opened. Synthetic people.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from test_telegram_attachments import PNG, FileTransport, message, photo_sizes
from test_telegram_ingress import OWNER, TOKEN, FakeReply, ingress, poll, update

from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.handlers import WRITE_SPECS, bindings
from capabilities.business_cards.manifest import business_cards_skill
from capabilities.business_cards.store import CardStore
from capabilities.runtime import CapabilityGrant, LocalPolicy
from common.assets import ExecutionDependencies
from host_runtime.attachments import AttachmentStore
from host_runtime.business_cards_tools import CHART_TOOL, business_cards_tools
from integrations.outlook_mail import MailScope
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent, ModelToolCall


class PhotoTransport(FileTransport):
    """Also takes `sendPhoto` (multipart), recording each body."""

    def __init__(self, batches: list[list[dict[str, Any]]], files: dict[str, bytes]) -> None:
        super().__init__(batches, files)
        self.photos: list[tuple[bytes, Mapping[str, str]]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        if url.endswith("/sendPhoto"):
            self.photos.append((body, headers))
            return FakeReply(200, {"ok": True, "result": {"message_id": 99}})
        return super().send(url, body, headers, timeout_s)


class CardModel:
    """Stores the card it is shown, then draws the chart when asked."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        asked = next(m.text for m in reversed(request.messages) if m.role == "user")
        tool_results = [m for m in request.messages if m.role == "tool"]
        calls: tuple[ModelToolCall, ...] = ()
        text = ""
        if tool_results and request.messages[-1].role == "tool":
            text = "完成。" if "org chart" not in asked else "這是範例科技的組織圖。"
        elif "org chart" in asked:
            calls = (
                ModelToolCall(call_id="c2", name=CHART_TOOL, arguments={"company": "範例科技"}),
            )
        else:
            assert request.messages[-1].images, "the photo must reach the model as an image"
            listed = re.search(r"\(image[^)]*\): (.+)", asked)
            path = listed.group(1).strip() if listed else ""
            calls = (
                ModelToolCall(
                    call_id="c1",
                    name="cards__add_card",
                    arguments={
                        "name": "周範例",
                        "company": "範例科技",
                        "division": "研發處",
                        "title": "經理",
                        "image_path": path,
                    },
                ),
            )
        return ModelResponse(
            trace=request.trace, model_alias=request.model_alias, text=text, tool_calls=calls
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _with_cards(agent: Any, workspace: Path) -> None:
    """The cards capabilities, the Skill and the tools on this Agent's Bridge,
    in owner mode with the writes confirmed standing, as a Host wires them."""
    bridge = agent.gateway.bridge
    specs = []
    for spec, handler, request, response in bindings(
        workspace,
        reader=lambda: None,  # type: ignore[arg-type, return-value]
        scope=MailScope,
        model=None,
        alias="company",
    ):
        bridge.installed.register(
            spec, handler, request, response, ExecutionDependencies(central_required=False)
        )
        specs.append(spec)
    policy = LocalPolicy(
        tuple(
            CapabilityGrant(
                actor="engineer",
                asset=spec.identity,
                permissions=spec.policy.required_permissions,
                policy_refs=spec.policy.policy_refs,
                approval_ref="device-owner",
            )
            for spec in specs
        ),
        owner_mode=True,
    )
    for spec in WRITE_SPECS:
        policy.confirm_writes(spec)
    bridge.policy = policy
    agent.gateway.router.commands.skills.register(business_cards_skill())
    agent.gateway.host_tools = lambda: business_cards_tools(agent.gateway)


def test_a_photo_is_stored_and_the_chart_comes_back_as_a_photo(tmp_path: Path) -> None:
    transport = PhotoTransport(
        [
            [message(1, OWNER, caption="store this card", photo=photo_sizes("ph1"))],
            [update(2, OWNER, "範例科技 org chart")],
        ],
        {"ph1": PNG},
    )
    item, agent, _ = ingress(tmp_path, transport)
    workspace = tmp_path / "workspace"
    item.attachments = AttachmentStore(workspace)
    model = CardModel()
    agent.gateway.router.model = model
    _with_cards(agent, workspace)

    first = poll(item)
    assert first.deliveries[0].disposition == "answered", first.deliveries[0]
    assert model.requests[0].messages[-1].images[0].startswith("data:image/")
    store = CardStore.for_actor(workspace, "engineer")
    people, total = store.find("周範例", status="any", limit=5)
    assert total == 1 and people[0].division == "研發處"
    observed = store.history(PersonRef(person_id=people[0].person_id), limit=5).observations
    # Only the photo's hash is kept, never the photo.
    assert observed[0].source_ref.startswith("sha256:")
    assert transport.photos == []

    second = poll(item)
    delivery = second.deliveries[0]
    assert delivery.replied and len(delivery.photos) == 1
    assert "這是範例科技的組織圖" in (delivery.reply or "")
    assert "範例科技 組織圖" in (delivery.reply or "")
    assert "不代表誰向誰報告" in (delivery.reply or "")
    ((body, headers),) = transport.photos
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="chat_id"' in body and str(OWNER).encode() in body
    assert b"\x89PNG\r\n\x1a\n" in body
    assert TOKEN.encode() not in body
