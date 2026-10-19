"""The business-cards capabilities through the Bridge (docs/phases/BUSINESS_CARDS.md).

The org chart renders a real PNG without Graphviz, with its legend; people
who left are left out or drawn grey. Signature harvesting reads only mail in
the person's scope from the named domain, sends only signature blocks to the
(fake) gateway model and stores nothing. The contact-store writes run on a
model's choice without a per-call confirmation, and nothing else does.
Fakes only: no mail, gateway or network.
"""

from __future__ import annotations

import asyncio
import sqlite3
import struct
import subprocess
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from capabilities.business_cards.handlers import (
    CHART_SPEC,
    HARVEST_SPEC,
    WRITE_SPECS,
    bindings,
)
from capabilities.business_cards.signatures import signature_block
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import ExecutionDependencies
from common.execution import RequestContext, TraceIdentifiers
from integrations.outlook_mail import MailMessage, MailScope, MailSummary
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from workflow.dispatch import BridgeExecutor

NOW = datetime.now(UTC)


class FakeMail:
    """A mailbox in memory; records what was opened."""

    def __init__(self, messages: Sequence[MailMessage]) -> None:
        self.messages = {item.message_id: item for item in messages}
        self.opened: list[str] = []
        self.listed: list[tuple[str, datetime]] = []

    def list(self, folder: str, since: datetime, limit: int) -> list[MailSummary]:
        self.listed.append((folder, since))
        return [
            MailSummary(**item.model_dump(exclude={"body", "cc"}))
            for item in self.messages.values()
            if item.folder == folder or item.folder.startswith(folder + "/")
        ]

    def get(self, message_id: str) -> MailMessage:
        self.opened.append(message_id)
        return self.messages[message_id]

    def save_attachment(self, message_id: str, name: str, target: Path) -> Path:
        raise AssertionError("no attachment is ever saved")


class SignatureModel:
    """Reads each block's first line as the name and returns structured JSON."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        text = request.messages[-1].text
        people = []
        for number, block in enumerate(text.split("===== block ")[1:]):
            lines = [line for line in block.split("\n")[1:] if line.strip()]
            people.append(
                {
                    "i": number,
                    "name": lines[0].strip(),
                    "title": lines[1].strip() if len(lines) > 1 else "",
                    "company": "範例科技",
                    "uncertain": ["title"],
                }
            )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output={"people": people},
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def _context(actor: str = "alice") -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t1", request_id="r1", span_id="s1"),
        actor=actor,
        namespace="engineering",
        message="cards",
        channel="local",
        session_id="s-1",
    )


def _bridge(
    tmp_path: Path,
    *,
    mail: FakeMail | None = None,
    scope: MailScope | None = None,
    model: SignatureModel | None = None,
    confirm: bool = True,
    actors: tuple[str, ...] = ("alice", "bob"),
) -> BridgeExecutor:
    installed = InstalledCapabilities()
    specs: list[CapabilitySpec] = []
    for spec, handler, request, response in bindings(
        tmp_path / "workspace",
        reader=lambda: mail if mail is not None else FakeMail(()),
        scope=lambda: scope or MailScope(),
        model=model,
        alias="company",
    ):
        installed.register(
            spec, handler, request, response, ExecutionDependencies(central_required=False)
        )
        specs.append(spec)
    policy = LocalPolicy(
        tuple(
            CapabilityGrant(
                actor=actor,
                asset=spec.identity,
                permissions=spec.policy.required_permissions,
                policy_refs=spec.policy.policy_refs,
                approval_ref="device-owner",
            )
            for actor in actors
            for spec in specs
        ),
        owner_mode=True,
    )
    if confirm:
        for spec in WRITE_SPECS:
            policy.confirm_writes(spec)
    return BridgeExecutor(installed, policy)


def _run(
    bridge: BridgeExecutor, name: str, arguments: dict[str, Any], *, actor: str = "alice"
) -> Any:
    """The `CapabilityResult`, typed loosely so tests can read its JSON data."""
    spec = next(binding for binding in bridge.installed.discover() if binding.identity.name == name)
    return asyncio.run(
        bridge.execute(
            CapabilityInvocation(
                context=_context(actor), origin="model", target=spec.identity, arguments=arguments
            )
        )
    )


def _people(bridge: BridgeExecutor) -> None:
    for card in (
        {
            "name": "王小明",
            "company": "範例科技",
            "business_group": "網通事業群",
            "division": "研發處",
            "department": "射頻部",
            "title": "協理",
            "email": "hm.wang@example.com",
        },
        {"name": "李大華", "company": "範例科技", "division": "研發處", "title": "工程師"},
        {"name": "陳美", "company": "範例科技", "division": "業務處", "title": "業務"},
        {"name": "林離", "company": "範例科技", "division": "業務處", "title": "經理"},
    ):
        assert _run(bridge, "add-card", card).status == "succeeded"


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_writes_run_on_the_models_choice_only_when_confirmed_standing(tmp_path: Path) -> None:
    confirmed = _bridge(tmp_path / "a")
    assert _run(confirmed, "add-card", {"name": "王小明", "company": "範例科技"}).status == (
        "succeeded"
    )
    unconfirmed = _bridge(tmp_path / "b", confirm=False)
    refused = _run(unconfirmed, "add-card", {"name": "王小明", "company": "範例科技"})
    assert refused.failure is not None and refused.failure.code == "approval_required"
    # A read never waits; and only a low-risk local write can be confirmed.
    assert _run(unconfirmed, "find", {"query": "王"}).status == "succeeded"
    with pytest.raises(ValueError):
        LocalPolicy().confirm_writes(CHART_SPEC)
    execute = CapabilitySpec.model_validate(
        {
            **WRITE_SPECS[0].model_dump(),
            "side_effect": "execute",
        }
    )
    with pytest.raises(ValueError):
        LocalPolicy().confirm_writes(execute)


def test_the_org_chart_is_a_png_without_graphviz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_process(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the chart must not start a process (no Graphviz)")

    monkeypatch.setattr(subprocess, "run", no_process)
    monkeypatch.setattr(subprocess, "Popen", no_process)
    monkeypatch.setenv("PATH", "")
    bridge = _bridge(tmp_path)
    _people(bridge)
    assert (
        _run(
            bridge,
            "set-reporting-line",
            {
                "person": {"name": "李大華"},
                "manager": {"name": "王小明"},
                "evidence_kind": "signature",
                "evidence_ref": "<msg-9>",
            },
        ).status
        == "succeeded"
    )
    inferred = _run(
        bridge,
        "set-reporting-line",
        {
            "person": {"name": "陳美"},
            "manager": {"name": "王小明"},
            "evidence_kind": "title_inference",
        },
    )
    assert inferred.data is not None and inferred.data["inferred"] is True
    assert (
        _run(
            bridge,
            "set-status",
            {"person": {"name": "林離"}, "status": "left", "reason": "left in September"},
        ).status
        == "succeeded"
    )
    drawn = _run(bridge, "org-chart", {"company": "範例科技"})
    assert drawn.status == "succeeded", drawn.failure
    data = drawn.data
    assert data is not None
    png = Path(data["png_path"])
    width, height = _png_size(png)
    assert 400 <= width <= 4000 and 150 <= height <= 4000
    assert png.stat().st_size > 2_000
    assert (data["people"], data["left_omitted"], data["left_shown"]) == (3, 1, 0)
    assert (data["lines_evidenced"], data["lines_inferred"]) == (1, 1)
    legend = data["legend_markdown"]
    assert "| 李大華 | 王小明 | 簽名檔（<msg-9>） | 否（實線） |" in legend
    assert "| 陳美 | 王小明 | 依職稱推論 | 是（虛線） |" in legend
    assert "已離職的 1 人沒有畫出" in legend and "林離" not in legend
    assert Path(data["legend_path"]).read_text(encoding="utf-8").strip() == legend
    assert [item["media_type"] for item in data["attach"]] == ["image/png", "text/markdown"]
    # Asked for, people who left are drawn (grey) and counted.
    with_left = _run(bridge, "org-chart", {"company": "範例科技", "include_left": True})
    assert with_left.data is not None
    assert (with_left.data["people"], with_left.data["left_shown"]) == (4, 1)
    assert "已離職的人以灰色顯示" in with_left.data["legend_markdown"]
    grey = _png_size(Path(with_left.data["png_path"]))
    assert grey[1] >= height


def test_a_chart_without_evidenced_lines_says_it_is_no_reporting_chart(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _people(bridge)
    drawn = _run(bridge, "org-chart", {"company": "範例科技"})
    assert drawn.data is not None
    assert "不代表誰向誰報告" in drawn.data["legend_markdown"]
    assert "不代表誰向誰報告" in drawn.data["note"]
    missing = _run(bridge, "org-chart", {"company": "沒有這家"})
    assert missing.failure is not None and missing.failure.code == "company_has_no_contacts"


def _message(
    message_id: str, sender: str, body: str, *, days_ago: int = 1, folder: str = "Inbox"
) -> MailMessage:
    return MailMessage(
        message_id=message_id,
        folder=folder,
        sender=sender,
        subject="weekly sync",
        received=NOW - timedelta(days=days_ago),
        snippet=body[:40],
        body=body,
    )


BODY = (
    "Hi team,\nThe secret plan for project Falcon is attached. password=hunter2\n\n"
    "Best regards,\n{name}\n{title}\nTel: +886-2-2345-6789 #{ext}\n"
    "Mobile: 0912-000-{ext}\n\n-----Original Message-----\nFrom: someone.else@other.com\n"
    "Quoted Person\nDirector\nTel: 03-000-0000\n"
)


def test_signature_harvest_respects_the_scope_and_stores_nothing(tmp_path: Path) -> None:
    mail = FakeMail(
        [
            _message(
                "m1",
                "Wang <hm.wang@example.com>",
                BODY.format(name="王小明", title="協理", ext="312"),
            ),
            _message(
                "m2", "lee@example.com", BODY.format(name="李大華", title="工程師", ext="100")
            ),
            # Same sender, older: only the newest message per person is read.
            _message(
                "m3",
                "Wang <hm.wang@example.com>",
                BODY.format(name="王小明", title="經理", ext="312"),
                days_ago=5,
            ),
            _message("m4", "x@other.com", BODY.format(name="外人", title="經理", ext="1")),
            # Outside the scope: an excluded folder, and older than max_days.
            _message(
                "m5",
                "hr@example.com",
                BODY.format(name="不該讀", title="HR", ext="2"),
                folder="Inbox/HR",
            ),
            _message(
                "m6", "old@example.com", BODY.format(name="太舊", title="舊", ext="3"), days_ago=40
            ),
        ]
    )
    scope = MailScope(folders=("Inbox",), max_days=30, excluded_folders=("Inbox/HR",))
    model = SignatureModel()
    bridge = _bridge(tmp_path, mail=mail, scope=scope, model=model)
    harvested = _run(bridge, "harvest-signatures", {"domain": "example.com", "days": 365})
    assert harvested.status == "succeeded", harvested.failure
    data = harvested.data
    assert data is not None
    names = {item["name"]: item for item in data["candidates"]}
    assert set(names) == {"王小明", "李大華"}
    assert names["王小明"]["email"] == "hm.wang@example.com"
    assert names["王小明"]["message_id"] == "m1"
    assert names["王小明"]["uncertain"] == ["title"]
    assert set(mail.opened) == {"m1", "m2"}
    # days beyond the scope's max_days are capped.
    assert all(NOW - since <= timedelta(days=30, minutes=1) for _, since in mail.listed)
    sent = "\n".join(message.text for request in model.requests for message in request.messages)
    for leaked in ("Falcon", "hunter2", "Quoted Person", "someone.else", "不該讀", "外人"):
        assert leaked not in sent
    assert "Tel: +886-2-2345-6789 #312" in sent
    # Nothing was stored by the harvest.
    found = _run(bridge, "find", {"query": "王小明"})
    assert found.data is not None and found.data["total"] == 0
    stored = _run(
        bridge,
        "add-from-signature",
        {
            "entries": [
                {
                    **{k: v for k, v in names["王小明"].items() if k not in _NOT_ENTRY},
                }
            ]
        },
    )
    assert stored.status == "succeeded", stored.failure
    db = next((tmp_path / "workspace" / "business-cards").glob("*/cards.db"))
    with sqlite3.connect(db) as con:
        dumped = "\n".join(str(row) for row in con.iterdump())
    for leaked in ("Falcon", "hunter2", "Hi team", "Quoted Person"):
        assert leaked not in dumped
    assert "m1" in dumped and "email_signature" in dumped


_NOT_ENTRY = {"existing_person_id", "would_change"}


def test_harvest_needs_a_model_and_a_domain(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path, mail=FakeMail(()))
    refused = _run(bridge, "harvest-signatures", {"domain": "example.com"})
    assert refused.failure is not None and refused.failure.code == "model_not_configured"
    bad = _run(
        _bridge(tmp_path / "x", model=SignatureModel()), "harvest-signatures", {"domain": "x"}
    )
    assert bad.failure is not None and bad.failure.code == "invalid_input"


def test_a_signature_block_is_cut_before_the_quote() -> None:
    block = signature_block(BODY.format(name="王小明", title="協理", ext="312"))
    assert block is not None
    assert block.splitlines()[0] == "王小明"
    assert "Original Message" not in block and "Falcon" not in block
    assert signature_block("just a line\nno signature here") is None


def test_each_actor_sees_only_their_own_contacts(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    assert _run(bridge, "add-card", {"name": "王小明", "company": "範例科技"}).status == "succeeded"
    mine = _run(bridge, "find", {"query": "王小明"}, actor="alice")
    theirs = _run(bridge, "find", {"query": "王小明"}, actor="bob")
    assert mine.data is not None and mine.data["total"] == 1
    assert theirs.data is not None and theirs.data["total"] == 0
    refused = _run(bridge, "org-chart", {"company": "範例科技"}, actor="bob")
    assert refused.failure is not None


def test_add_card_keeps_only_the_hash_of_an_attached_photo(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    photo = tmp_path / "workspace" / "attachments" / "abc" / "att-1" / "card.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"\xff\xd8 synthetic photo bytes")
    outside = tmp_path / "elsewhere.jpg"
    outside.write_bytes(b"other")
    first = _run(
        bridge, "add-card", {"name": "王小明", "company": "範例科技", "image_path": str(photo)}
    )
    second = _run(
        bridge, "add-card", {"name": "陳美", "company": "範例科技", "image_path": str(outside)}
    )
    assert first.status == second.status == "succeeded"
    history = _run(bridge, "history", {"person": {"name": "王小明"}})
    assert history.data is not None
    assert history.data["observations"][0]["source_ref"].startswith("sha256:")
    other = _run(bridge, "history", {"person": {"name": "陳美"}})
    assert other.data is not None and other.data["observations"][0]["source_ref"] == ""


def test_harvest_is_read_only_and_the_writes_are_low_risk() -> None:
    assert HARVEST_SPEC.side_effect == "read"
    for spec in WRITE_SPECS:
        assert spec.side_effect == "write" and spec.policy.risk == "low"
        assert spec.policy.policy_refs == ("personal-contacts-policy",)
