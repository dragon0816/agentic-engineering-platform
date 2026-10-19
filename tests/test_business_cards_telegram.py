"""Business cards over Telegram, the main way cards arrive (owner 2026-10-20;
docs/phases/BUSINESS_CARDS.md §7).

A compressed photo, a photo sent as a file and an album all reach the model
as images and are stored in the same turn, one card per photo; a re-scan
brings back the "上次是…現在是…" sentence; the org chart comes back as a
photo with the short "not a reporting chart unless lines have evidence"
note as its caption, the full legend as a document, and a short text reply.
Over the fake Bot API of `test_telegram_ingress`; no socket is opened.
Synthetic people.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from test_telegram_attachments import PNG, FileTransport, message, photo_sizes
from test_telegram_ingress import OWNER, TOKEN, FakeReply, ingress, poll, update

from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.handlers import WRITE_SPECS, bindings
from capabilities.business_cards.manifest import PROCEDURE, business_cards_skill
from capabilities.business_cards.store import CardStore
from capabilities.runtime import CapabilityGrant, LocalPolicy
from channels.telegram import TelegramIngress
from common.assets import ExecutionDependencies
from host_runtime.attachments import AttachmentStore
from host_runtime.business_cards_tools import CHART_TOOL, business_cards_tools
from integrations.outlook_mail import MailScope
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent, ModelToolCall


class PhotoTransport(FileTransport):
    """Also takes `sendPhoto` and `sendDocument` (multipart), recording each."""

    def __init__(self, batches: list[list[dict[str, Any]]], files: dict[str, bytes]) -> None:
        super().__init__(batches, files)
        self.uploads: list[tuple[str, bytes, Mapping[str, str]]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        method = url.rsplit("/", 1)[-1]
        if method in ("sendPhoto", "sendDocument"):
            self.uploads.append((method, body, headers))
            return FakeReply(200, {"ok": True, "result": {"message_id": 99}})
        return super().send(url, body, headers, timeout_s)


#: What the fake model "reads" on each photo, by the order it was sent.
CARDS = [
    {"name": "周範例", "company": "範例科技", "division": "研發處", "title": "經理"},
    {"name": "吳測試", "company": "範例科技", "division": "研發處", "title": "工程師"},
    {"name": "周範例", "company": "範例科技", "division": "研發處", "title": "協理"},
]


class CardModel:
    """Follows the Skill: one `cards__add_card` per attached picture, then a
    short reply that leads with the change; the chart when asked."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []
        self.read = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        user = [m for m in request.messages if m.role == "user"][-1]
        results = [m.text for m in request.messages if m.role == "tool"]
        if request.messages[-1].role == "tool":
            if "org chart" in user.text:
                text = "這是範例科技的組織圖。"
            else:
                lines = []
                for result in results:
                    data = json.loads(result)["host"]["data"]
                    lines.append(data["summary"] or f"已存：{data['name']}")
                text = "\n".join(lines)
            return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=text)
        if "org chart" in user.text:
            calls = [(CHART_TOOL, {"company": "範例科技"})]
        else:
            paths = re.findall(r"\(image[^)]*\): (.+)", user.text)
            assert len(user.images) == len(paths) > 0, "every photo reaches the model"
            calls = []
            for path in paths:
                calls.append(("cards__add_card", {**CARDS[self.read], "image_path": path.strip()}))
                self.read += 1
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            tool_calls=tuple(
                ModelToolCall(call_id=f"c{len(self.requests)}-{i}", name=name, arguments=args)
                for i, (name, args) in enumerate(calls)
            ),
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


def _bot(
    tmp_path: Path, batches: list[list[dict[str, Any]]], files: dict[str, bytes]
) -> tuple[TelegramIngress, PhotoTransport, CardModel, CardStore]:
    transport = PhotoTransport(batches, files)
    item, agent, _ = ingress(tmp_path, transport)
    workspace = tmp_path / "workspace"
    item.attachments = AttachmentStore(workspace)
    model = CardModel()
    agent.gateway.router.model = model
    _with_cards(agent, workspace)
    return item, transport, model, CardStore.for_actor(workspace, "engineer")


def test_a_bare_photo_is_stored_in_the_same_turn_and_a_rescan_leads_with_the_change(
    tmp_path: Path,
) -> None:
    item, transport, model, store = _bot(
        tmp_path,
        [
            # A compressed photo with no caption at all.
            [message(1, OWNER, photo=photo_sizes("ph1"))],
            [message(2, OWNER, caption="名片", photo=photo_sizes("ph2"))],
            [message(3, OWNER, photo=photo_sizes("ph3"))],
        ],
        {"ph1": PNG, "ph2": PNG, "ph3": PNG},
    )
    first = poll(item).deliveries[0]
    assert first.disposition == "answered" and first.replied
    assert model.requests[0].messages[-1].images[0].startswith("data:image/")
    people, total = store.find("周範例", status="any", limit=5)
    assert total == 1
    observed = store.history(PersonRef(person_id=people[0].person_id), limit=5).observations
    assert observed[0].source_ref.startswith("sha256:")
    poll(item)
    third = poll(item).deliveries[0]
    assert third.reply is not None
    assert "上次是研發處經理, 現在是研發處協理" in third.reply
    assert len(third.reply) < 200 and transport.uploads == []
    assert store.find("周範例", status="any", limit=5)[0][0].title == "協理"


def test_a_photo_sent_as_a_file_reaches_the_model_as_an_image(tmp_path: Path) -> None:
    item, _, model, store = _bot(
        tmp_path,
        [
            [
                message(
                    1,
                    OWNER,
                    document={
                        "file_id": "doc1",
                        "file_name": "IMG_0001.JPG",
                        "mime_type": "image/jpeg",
                        "file_size": len(PNG),
                    },
                )
            ],
            # A file without a name: its type comes from the MIME type.
            [message(2, OWNER, document={"file_id": "doc2", "mime_type": "image/png"})],
        ],
        {"doc1": PNG, "doc2": PNG},
    )
    assert poll(item).deliveries[0].replied
    assert poll(item).deliveries[0].replied
    assert all(request.messages[-1].images for request in model.requests[::2])
    assert store.find("範例科技", status="any", limit=5)[1] == 2


def test_an_album_is_one_turn_with_one_card_per_photo(tmp_path: Path) -> None:
    item, transport, model, store = _bot(
        tmp_path,
        [
            [
                message(1, OWNER, caption="這些名片", photo=photo_sizes("a1"), group="album-1"),
                message(2, OWNER, photo=photo_sizes("a2"), group="album-1"),
            ]
        ],
        {"a1": PNG, "a2": PNG},
    )
    result = poll(item)
    assert len(result.deliveries) == 1
    assert len(model.requests[0].messages[-1].images) == 2
    people, total = store.list_people(company="範例科技", source="card", status="any", limit=9)
    assert total == 2 and {p.name for p in people} == {"周範例", "吳測試"}
    reply = result.deliveries[0].reply or ""
    assert "已存：周範例" in reply and "已存：吳測試" in reply
    assert len([m for m in transport.sent() if m.strip()]) == 1


def test_the_org_chart_comes_back_as_a_photo_with_the_short_note(tmp_path: Path) -> None:
    item, transport, _, _ = _bot(
        tmp_path,
        [
            [message(1, OWNER, caption="store this card", photo=photo_sizes("ph1"))],
            [update(2, OWNER, "範例科技 org chart")],
        ],
        {"ph1": PNG},
    )
    poll(item)
    delivery = poll(item).deliveries[0]
    reply = delivery.reply or ""
    assert delivery.replied and len(delivery.photos) == 1 and len(delivery.documents) == 1
    assert "這是範例科技的組織圖" in reply and "範例科技 組織圖" in reply
    assert "不代表誰向誰報告" in reply
    # Short on a phone: the table goes along as the legend file, not in the text.
    assert "| 成員 | 主管 |" not in reply
    (photo_method, photo, headers), (document_method, document, _) = transport.uploads
    assert (photo_method, document_method) == ("sendPhoto", "sendDocument")
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="chat_id"' in photo and str(OWNER).encode() in photo
    assert b"\x89PNG\r\n\x1a\n" in photo
    assert "只有畫出的線才是回報關係".encode() in photo
    assert "組織圖".encode() in document and b'name="document"' in document
    assert TOKEN.encode() not in photo + document


def test_the_skill_says_how_a_telegram_card_is_handled() -> None:
    assert "even when no request comes with it" in PROCEDURE
    assert "one card per photo" in PROCEDURE
    assert "ask about exactly those fields and nothing else" in PROCEDURE
    assert "lead with the change" in PROCEDURE
