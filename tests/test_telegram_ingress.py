"""Telegram as an ingress to the resident local Agent, over a fake Bot API.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 2e. Every test drives
`poll_once` against a transport that records what was sent and answers with
canned updates; no socket is opened and no Telegram library is imported.
"""

import asyncio
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from evaluation_runner import GatewayRunner
from pydantic import ValidationError

from channels.telegram import (
    HELP,
    MAX_MESSAGE_CHARS,
    TELEGRAM_CHANNEL,
    TelegramIngress,
    TelegramIngressConfig,
    chunks,
    command_to_message,
    scrub,
)
from common.assets import SECRET_FIELD, SECRET_PATTERN, reject_embedded_secrets
from common.distribution import LocalStateError
from common.enrollment import BridgeBinding, BridgeDevice
from common.local_agent import BridgeMembership
from host_runtime.agent import LocalAgent
from host_runtime.state import SqliteLocalState
from models.credentials import StaticCredentials
from models.wire import redacted

# The shape of a real bot token, with a synthetic body.
TOKEN = "1234567890:AAE" + "x" * 32
OWNER, TESTER, STRANGER = 111, 222, 999


class FakeReply:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def chunks(self) -> Iterator[bytes]:
        yield self._body

    def close(self) -> None:
        return None


class FakeTransport:
    """Answers `getUpdates` from a queue of batches and accepts every
    `sendMessage`, recording each call's URL and payload."""

    def __init__(
        self,
        batches: list[list[dict[str, Any]]] | None = None,
        *,
        status: int = 200,
        error: BaseException | None = None,
        send_status: int = 200,
    ) -> None:
        self.batches = list(batches or [])
        self.status = status
        self.error = error
        self.send_status = send_status
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        self.calls.append((url, json.loads(body)))
        if self.error is not None:
            raise self.error
        if url.endswith("/getUpdates"):
            batch = self.batches.pop(0) if self.batches else []
            return FakeReply(self.status, {"ok": True, "result": batch})
        return FakeReply(self.send_status, {"ok": True, "result": {}})

    def sent(self) -> list[str]:
        return [payload["text"] for url, payload in self.calls if url.endswith("/sendMessage")]

    def polls(self) -> list[dict[str, Any]]:
        return [payload for url, payload in self.calls if url.endswith("/getUpdates")]


class CountingCredentials(StaticCredentials):
    def __init__(self, values: Mapping[str, str]) -> None:
        super().__init__(values)
        self.resolved = 0

    def resolve(self, ref: Any) -> str:
        self.resolved += 1
        return super().resolve(ref)


def update(
    update_id: int, sender: int, text: str | None, chat: int | None = None
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "message_id": update_id,
        "chat": {"id": chat if chat is not None else sender, "type": "private"},
        "from": {"id": sender, "is_bot": False, "first_name": "someone"},
    }
    if text is not None:
        message["text"] = text
    else:
        message["document"] = {"file_id": "f", "file_name": "notes.txt"}
    return {"update_id": update_id, "message": message}


def device(kind: str = "company_workstation") -> BridgeDevice:
    profile = {
        "company_workstation": (
            "bridge-company",
            "dedicated_user",
            "corporate_internal",
            "single_user",
        ),
        "shared_test_workstation": (
            "bridge-shared",
            "shared_user",
            "external_only",
            "cooperative_workspace",
        ),
    }[kind]
    return BridgeDevice.model_validate(
        {
            "bridge_id": profile[0],
            "registered_by": "engineer",
            "device_kind": kind,
            "windows_account_mode": profile[1],
            "resource_scope": profile[2],
            "local_isolation": profile[3],
        }
    )


def membership(kind: str = "company_workstation") -> BridgeMembership:
    dev = device(kind)
    bindings = [BridgeBinding(bridge_id=dev.bridge_id, actor="engineer", role="operator")]
    if kind == "shared_test_workstation":
        bindings.append(BridgeBinding(bridge_id=dev.bridge_id, actor="tester", role="operator"))
    return BridgeMembership(device=dev, bindings=tuple(bindings))


def config(kind: str = "company_workstation", **changes: Any) -> TelegramIngressConfig:
    return TelegramIngressConfig.model_validate(
        {
            "credential": {"name": "telegram_bot"},
            "bridge_id": device(kind).bridge_id,
            "namespace": "engineering",
            "senders": [
                {"sender_id": OWNER, "actor": "engineer"},
                {"sender_id": TESTER, "actor": "tester"},
            ],
            **changes,
        }
    )


def ingress(
    tmp_path: Path,
    transport: FakeTransport,
    kind: str = "company_workstation",
    *,
    resolver: CountingCredentials | None = None,
    **changes: Any,
) -> tuple[TelegramIngress, LocalAgent, GatewayRunner]:
    runner = GatewayRunner()
    members = membership(kind)
    tmp_path.mkdir(exist_ok=True)
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id=members.device.bridge_id)
    agent = LocalAgent(members, runner.gateway(), state)
    resolver = resolver if resolver is not None else CountingCredentials({"telegram_bot": TOKEN})
    return (
        TelegramIngress(config(kind, **changes), agent, resolver, transport=transport),
        agent,
        runner,
    )


def poll(item: TelegramIngress) -> Any:
    return asyncio.run(item.poll_once())


def test_config_refuses_a_pasted_token_duplicates_and_a_plain_origin() -> None:
    with pytest.raises(ValidationError):
        config(api_base=f"https://api.telegram.org/bot{TOKEN}")
    with pytest.raises(ValidationError):
        config(
            senders=[{"sender_id": OWNER, "actor": "engineer"}, {"sender_id": OWNER, "actor": "b"}]
        )
    with pytest.raises(ValidationError):
        config(
            senders=[{"sender_id": 1, "actor": "engineer"}, {"sender_id": 2, "actor": "engineer"}]
        )
    with pytest.raises(ValidationError):
        config(api_base="http://api.telegram.org")
    assert config(api_base="https://proxy.example/").api_base == "https://proxy.example"
    # An empty map admits nobody: the opposite of the source's empty allowlist.
    assert config(senders=[]).actor_for(OWNER) is None
    # The token's shape, and a field named for it, are credential material
    # everywhere in the repository, not only here.
    assert SECRET_PATTERN.search(f"https://api.telegram.org/bot{TOKEN}/getUpdates") is not None
    assert SECRET_FIELD.fullmatch("bot-token") and SECRET_FIELD.fullmatch("BOT_TOKEN")
    with pytest.raises(ValueError):
        reject_embedded_secrets({"note": f"the bot is {TOKEN}"})
    with pytest.raises(ValueError):
        reject_embedded_secrets({"bot_token": "anything at all"})


def test_an_unmapped_sender_is_neither_routed_nor_answered(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, STRANGER, "shipment.run")]])
    resolver = CountingCredentials({"telegram_bot": TOKEN})
    item, agent, runner = ingress(tmp_path, transport, resolver=resolver)
    result = poll(item)
    assert result.failure is None
    delivery = result.deliveries[0]
    assert delivery.disposition == "unmapped_sender"
    assert delivery.outcome is None and delivery.reply is None and not delivery.replied
    assert runner.bridge.events == () and agent.runs() == ()
    # No reply, so a stranger learns nothing and spends nothing: one call
    # and one credential resolution, for the poll itself.
    assert transport.sent() == [] and resolver.resolved == 1
    assert result.next_offset == 2


def test_a_mapped_sender_whose_actor_is_not_bound_is_refused_by_the_agent(tmp_path: Path) -> None:
    # On the company device only the owner is bound; the tester is mapped but not a member.
    transport = FakeTransport([[update(1, TESTER, "shipment.run")]])
    item, agent, runner = ingress(tmp_path, transport)
    result = poll(item)
    delivery = result.deliveries[0]
    assert delivery.disposition == "refused"
    assert delivery.outcome is not None
    assert delivery.outcome.refusal == "company_owner_required"
    assert "company_owner_required" in (delivery.reply or "")
    assert runner.bridge.events == () and agent.runs() == ()
    # And on a shared device, an actor mapped but not bound at all.
    transport = FakeTransport([[update(1, STRANGER, "shipment.run")]])
    item, agent, runner = ingress(
        tmp_path / "shared",
        transport,
        "shared_test_workstation",
        senders=[{"sender_id": STRANGER, "actor": "nobody"}],
    )
    result = poll(item)
    assert result.deliveries[0].outcome is not None
    assert result.deliveries[0].outcome.refusal == "actor_not_bound"
    assert runner.bridge.events == ()


def test_a_bound_sender_reaches_the_real_workflow_and_is_recorded_under_the_actor(
    tmp_path: Path,
) -> None:
    transport = FakeTransport([[update(7, OWNER, "shipment.run")]])
    item, agent, runner = ingress(tmp_path, transport)
    result = poll(item)
    delivery = result.deliveries[0]
    assert delivery.disposition == "routed" and delivery.replied
    outcome = delivery.outcome
    assert outcome is not None and outcome.ingress == "telegram" and outcome.actor == "engineer"
    assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
    assert outcome.trace.trace_id == "telegram-7"
    assert outcome.run is not None and outcome.run.actor == "engineer"
    assert len(runner.bridge.events) == 2
    assert delivery.reply is not None
    assert "release-package" in delivery.reply and "succeeded" in delivery.reply
    assert transport.sent() == [delivery.reply]


def test_a_slash_command_reaches_the_deterministic_router(tmp_path: Path) -> None:
    assert command_to_message("/shipment run") == "shipment.run"
    assert command_to_message("/shipment@release_bot run  now ") == "shipment.run now"
    assert command_to_message("/shipment") == "shipment"
    assert command_to_message("  請發布套件 ") == "請發布套件"
    transport = FakeTransport([[update(1, OWNER, "/shipment run")]])
    item, agent, runner = ingress(tmp_path, transport)
    result = poll(item)
    outcome = result.deliveries[0].outcome
    assert outcome is not None and outcome.decision is not None
    assert outcome.decision.kind == "workflow"
    assert outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
    assert len(runner.bridge.events) == 2


def test_help_and_status_are_answered_locally_in_any_spelling(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [update(1, OWNER, "/help"), update(2, OWNER, "/start@release_bot extra words")],
            [update(3, OWNER, "shipment.run")],
            [update(4, OWNER, "/status@release_bot")],
        ]
    )
    item, agent, runner = ingress(tmp_path, transport)
    first = poll(item)
    assert [d.disposition for d in first.deliveries] == ["answered", "answered"]
    assert all(d.reply == HELP for d in first.deliveries)
    assert runner.bridge.events == ()
    poll(item)
    third = poll(item)
    assert third.deliveries[0].disposition == "answered"
    assert "1 run(s)" in (third.deliveries[0].reply or "")
    assert "succeeded" in (third.deliveries[0].reply or "")
    assert len(agent.runs()) == 1


def test_the_token_is_used_in_the_url_and_held_nowhere(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "/help")]])
    resolver = CountingCredentials({"telegram_bot": TOKEN})
    item, _, _ = ingress(tmp_path, transport, resolver=resolver)
    poll(item)
    # getUpdates and one sendMessage: the token was resolved for each call.
    assert [url.split("/")[-1] for url, _ in transport.calls] == ["getUpdates", "sendMessage"]
    assert all(f"/bot{TOKEN}/" in url for url, _ in transport.calls)
    assert resolver.resolved == 2
    held = json.dumps({k: repr(v) for k, v in vars(item).items()})
    assert TOKEN not in held
    assert TOKEN not in item.config.model_dump_json()


def test_a_transport_error_is_reported_without_the_token_wherever_it_sits(tmp_path: Path) -> None:
    # The URL far enough into the message that the old trim-then-redact
    # would have cut the token in half and lost the match.
    prefix = "connection refused after " + "retrying, " * 60
    error = OSError(f"{prefix}to https://api.telegram.org/bot{TOKEN}/getUpdates")
    transport = FakeTransport(error=error)
    item, agent, _ = ingress(tmp_path, transport)
    agent.state.advance_cursor(TELEGRAM_CHANNEL, 5)
    result = poll(item)
    assert result.failure is not None
    assert result.failure.code == "telegram_unreachable" and result.failure.retryable
    assert TOKEN not in result.failure.message and TOKEN[:20] not in result.failure.message
    assert result.deliveries == () and item.offset() == 5
    assert TOKEN[:20] not in redacted(f"{prefix}{TOKEN}")
    # A credential the host cannot produce is a different, non-retryable answer.
    item, _, _ = ingress(tmp_path / "b", FakeTransport(), resolver=CountingCredentials({}))
    result = poll(item)
    assert result.failure is not None
    assert result.failure.code == "telegram_credential_unavailable" and not result.failure.retryable
    # Rate limiting is the shared wire rule: worth trying again.
    item, _, _ = ingress(tmp_path / "c", FakeTransport(status=429))
    result = poll(item)
    assert result.failure is not None
    assert result.failure.code == "telegram_http_error" and result.failure.retryable


def test_the_loop_stops_on_what_will_not_fix_itself_and_backs_off_otherwise(
    tmp_path: Path,
) -> None:
    item, _, _ = ingress(tmp_path, FakeTransport(status=409))
    result = poll(item)
    assert result.failure is not None and result.failure.code == "telegram_conflict"
    assert not result.failure.retryable
    failure = asyncio.run(item.run(asyncio.Event(), interval_s=0.01))
    assert failure is not None and failure.code == "telegram_conflict"
    # A revoked token and a missing credential end the loop the same way.
    item, _, _ = ingress(tmp_path / "unauthorized", FakeTransport(status=401))
    failure = asyncio.run(item.run(asyncio.Event(), interval_s=0.01))
    assert failure is not None and failure.code == "telegram_http_error"
    item, _, _ = ingress(tmp_path / "nocred", FakeTransport(), resolver=CountingCredentials({}))
    failure = asyncio.run(item.run(asyncio.Event(), interval_s=0.01))
    assert failure is not None and failure.code == "telegram_credential_unavailable"
    # A server error is retryable: the loop keeps going, with a doubling
    # delay, until asked to stop.
    transport = FakeTransport(status=503)
    item, _, _ = ingress(tmp_path / "b", transport)

    async def stop_soon() -> None:
        stop = asyncio.Event()
        asyncio.get_running_loop().call_later(0.12, stop.set)
        assert await item.run(stop, interval_s=0.01) is None

    asyncio.run(stop_soon())
    # 0.01 + 0.02 + 0.04 + 0.08 already exceeds the window: at most five polls,
    # where a fixed one-per-interval loop would have made about twelve.
    assert 2 <= len(transport.polls()) <= 5


def test_the_offset_is_durable_so_a_restart_does_not_replay_a_confirmed_batch(
    tmp_path: Path,
) -> None:
    """The cursor lives in the Bridge's own state, not in the ingress, so a
    new process resumes where the last confirmed batch ended."""
    transport = FakeTransport([[update(41, OWNER, "/help")]])
    item, agent, _ = ingress(tmp_path, transport)
    assert item.offset() is None
    poll(item)
    assert item.offset() == 42
    assert agent.state.cursor(TELEGRAM_CHANNEL) == 42
    # A second ingress over the same Bridge, as a restart would build.
    successor = TelegramIngress(
        config(), agent, CountingCredentials({"telegram_bot": TOKEN}), transport=transport
    )
    assert successor.offset() == 42
    poll(successor)
    assert transport.polls()[-1]["offset"] == 42
    # Cursors are per channel and never rewind.
    assert agent.state.cursor("other") is None
    with pytest.raises(LocalStateError, match="cursor_rewind"):
        agent.state.advance_cursor(TELEGRAM_CHANNEL, 41)
    assert agent.state.cursor(TELEGRAM_CHANNEL) == 42


def test_a_cursor_that_cannot_be_read_or_written_is_a_typed_answer(tmp_path: Path) -> None:
    item, agent, runner = ingress(tmp_path, FakeTransport([[update(1, OWNER, "/help")]]))
    agent.state.close()
    result = poll(item)
    # Without the cursor the poll would replay a confirmed batch, so it does
    # not happen at all: nothing was sent and nothing was routed.
    assert result.failure is not None and result.failure.code == "telegram_cursor_unavailable"
    assert result.deliveries == () and runner.bridge.events == ()


def test_a_redelivered_update_is_handled_once_and_the_batch_is_confirmed(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [update(10, OWNER, "/help"), update(11, OWNER, "/status")],
            [update(11, OWNER, "/status"), update(12, OWNER, "/help")],
        ]
    )
    item, _, _ = ingress(tmp_path, transport)
    first = poll(item)
    assert [d.update_id for d in first.deliveries] == [10, 11]
    assert first.next_offset == 12
    second = poll(item)
    assert [d.update_id for d in second.deliveries] == [12]
    assert second.next_offset == 13
    polls = transport.polls()
    assert "offset" not in polls[0] and polls[1]["offset"] == 12
    assert polls[0]["allowed_updates"] == ["message"]


def test_non_text_and_credential_bearing_messages_are_not_forwarded(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [
                update(1, OWNER, None),
                update(2, OWNER, "   "),
                update(3, OWNER, "shipment.run password: hunter2"),
                {"update_id": 4, "edited_message": {"text": "ignored"}},
            ]
        ]
    )
    item, agent, runner = ingress(tmp_path, transport)
    result = poll(item)
    assert [d.disposition for d in result.deliveries] == ["unsupported_content"] * 3
    assert all(d.outcome is None for d in result.deliveries)
    assert "hunter2" not in " ".join(transport.sent())
    assert runner.bridge.events == () and agent.runs() == ()
    assert result.next_offset == 5


def test_an_update_that_raises_is_recorded_and_the_loop_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport([[update(1, OWNER, "shipment.run"), update(2, OWNER, "/help")]])
    item, agent, _ = ingress(tmp_path, transport)

    async def boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("the gateway fell over")

    monkeypatch.setattr(agent, "handle", boom)
    result = poll(item)
    assert result.failure is None
    failed, answered = result.deliveries
    assert failed.disposition == "failed" and failed.failure is not None
    assert failed.failure.code == "telegram_delivery_failed"
    assert "RuntimeError" in failed.failure.message and failed.replied
    assert answered.disposition == "answered" and answered.reply == HELP
    # The batch is still confirmed: it was handled, one of them badly.
    assert result.next_offset == 3 and item.offset() == 3
    with pytest.raises(ValidationError, match="failed means handling raised"):
        failed.model_copy(update={"failure": None}).model_validate(
            failed.model_copy(update={"failure": None}).model_dump()
        )


def test_replies_are_chunked_scrubbed_and_a_failed_reply_is_recorded_not_raised(
    tmp_path: Path,
) -> None:
    long = "\n".join(f"line {index}" for index in range(1500))
    pieces = list(chunks(long))
    assert len(pieces) > 1
    assert all(len(piece) <= MAX_MESSAGE_CHARS for piece in pieces)
    assert "".join(piece + "\n" for piece in pieces).rstrip("\n").split("\n") == long.split("\n")
    assert list(chunks("")) == [""]
    assert list(chunks("x" * 8001, 4000)) == ["x" * 4000, "x" * 4000, "x"]
    # A reply is redacted but never truncated; truncation is for error text.
    assert (
        scrub("y" * 900 + " Authorization: Bearer abc") == "y" * 900 + " Authorization: [redacted]"
    )
    transport = FakeTransport([[update(1, OWNER, "/help")]], send_status=400)
    item, _, _ = ingress(tmp_path, transport)
    result = poll(item)
    assert result.deliveries[0].disposition == "answered"
    assert result.deliveries[0].replied is False
    assert result.next_offset == 2
