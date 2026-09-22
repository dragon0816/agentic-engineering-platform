"""Telegram as an ingress to the resident local Agent.

Adapted from the pinned `telegram-local-agent` channel
(`docs/PHASE_7_MIGRATION.md`): outbound long polling, so the company computer
opens no inbound port; a numeric sender checked before anything is routed; and
a slash command that reaches the deterministic router without a model. What
is deliberately not carried over: the token in a configuration file (it is a
`SecretRef` resolved per call and never held), the rule that an empty
allowlist admits everyone (an empty map admits nobody), HTML presentation, and
attachment handling.

The adapter adds no authority. It maps a sender to exactly one platform actor
and hands the Agent a `LocalAgentRequest`; the Agent admits or refuses by the
same membership rule as every other ingress, and the Gateway routes the same
way. Nothing here imports the Bot API library: the wire is the standard
library behind the same `Transport` the model adapters use.
"""

import asyncio
import json
import re
from collections.abc import Iterator, Mapping
from typing import Literal, Self

from pydantic import Field, JsonValue, StrictBool, model_validator

from common.assets import SecretRef, reject_embedded_secrets
from common.base import Contract, Slug, Symbol, Text
from common.execution import Failure, TraceIdentifiers
from common.local_agent import LocalAgentRequest
from host_runtime.agent import LocalAgent, LocalAgentOutcome
from models.credentials import CredentialMisconfigured, CredentialResolver
from models.wire import Transport, UrllibTransport, close_quietly, describe, redacted

# Telegram refuses a message over 4096 characters; the source split at 4000.
MAX_MESSAGE_CHARS = 4000
# Telegram caps long polling at 50 seconds; the transport waits a little longer.
POLL_MARGIN_SECONDS = 10
# Update ids already handled in this process, so a redelivered batch does not
# run a command twice. Bounded, because the process may live a long time.
SEEN_UPDATES = 1000
SLASH_COMMAND = re.compile(
    r"^/([a-zA-Z_][a-zA-Z0-9_]*)(?:@[A-Za-z0-9_]+)?(?:\s+([a-zA-Z_][a-zA-Z0-9_]*))?(?:\s+(.*))?$",
    re.DOTALL,
)
HELP = (
    "Send a skill command as /<skill> <command> [arguments], or describe the task in "
    "words. /status shows this Bridge's state. Attachments are not accepted."
)

Disposition = Literal["unmapped_sender", "unsupported_content", "answered", "refused", "routed"]


class TelegramSender(Contract):
    """One Telegram user, mapped to exactly one platform actor."""

    sender_id: int = Field(gt=0, strict=True)
    actor: Symbol


class TelegramIngressConfig(Contract):
    """Host configuration for one bot serving one Bridge. The token is a
    `SecretRef`; a token pasted anywhere in this record is refused."""

    credential: SecretRef
    bridge_id: Symbol
    namespace: Slug
    senders: tuple[TelegramSender, ...] = ()
    poll_timeout_seconds: int = Field(default=25, ge=0, le=50, strict=True)
    api_base: Text = "https://api.telegram.org"

    @model_validator(mode="after")
    def one_actor_per_sender_and_no_secret(self) -> Self:
        ids = [item.sender_id for item in self.senders]
        actors = [item.actor for item in self.senders]
        if len(ids) != len(set(ids)) or len(actors) != len(set(actors)):
            raise ValueError("a sender maps to one actor and an actor to one sender")
        if not self.api_base.startswith("https://") or "/bot" in self.api_base:
            raise ValueError("api_base is the https origin of the Bot API, without a token")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    def actor_for(self, sender_id: int) -> str | None:
        """None for a sender not in the map, including every sender when the
        map is empty: the opposite of the source, which admitted everyone."""
        for item in self.senders:
            if item.sender_id == sender_id:
                return item.actor
        return None


class TelegramDelivery(Contract):
    """What became of one update. `outcome` is the Agent's answer when the
    update reached it; the other dispositions never did."""

    update_id: int = Field(ge=0, strict=True)
    chat_id: int = Field(strict=True)
    sender_id: int | None = Field(default=None, strict=True)
    disposition: Disposition
    reply: Text
    replied: StrictBool = True
    outcome: LocalAgentOutcome | None = None

    @model_validator(mode="after")
    def outcome_matches_disposition(self) -> Self:
        reached = self.disposition in ("refused", "routed")
        if reached != (self.outcome is not None):
            raise ValueError("an update that reached the Agent carries its outcome, and only that")
        if self.outcome is not None and (self.disposition == "refused") != (
            self.outcome.refusal is not None
        ):
            raise ValueError("refused means the Agent refused")
        return self


class TelegramPollResult(Contract):
    deliveries: tuple[TelegramDelivery, ...] = ()
    failure: Failure | None = None
    next_offset: int | None = None


class _Update:
    def __init__(self, update_id: int, chat_id: int, sender_id: int, text: str | None) -> None:
        self.update_id = update_id
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.text = text


def _parse(raw: object) -> _Update | None:
    """A text message with a sender, or None for anything else Telegram
    sends (edits, channel posts, service messages, malformed items)."""
    if not isinstance(raw, dict) or type(raw.get("update_id")) is not int:
        return None
    message = raw.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    sender = message.get("from")
    if not isinstance(chat, dict) or type(chat.get("id")) is not int:
        return None
    if not isinstance(sender, dict) or type(sender.get("id")) is not int:
        return None
    text = message.get("text")
    return _Update(
        raw["update_id"], chat["id"], sender["id"], text if isinstance(text, str) else None
    )


def command_to_message(text: str) -> str:
    """`/skill command rest` becomes `skill.command rest`, the platform's
    deterministic form, so a slash command reaches the router without a model
    as the source's direct commands did. `/skill` alone is the bare word, and
    anything else is passed through as the person wrote it."""
    match = SLASH_COMMAND.match(text.strip())
    if match is None:
        return text.strip()
    alias, command, rest = match.group(1), match.group(2), match.group(3)
    head = f"{alias}.{command}" if command else alias
    return f"{head} {rest.strip()}" if rest and rest.strip() else head


def chunks(text: str, limit: int = MAX_MESSAGE_CHARS) -> Iterator[str]:
    """Split at a newline when one is near enough, as the source did."""
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        yield remaining[:cut]
        remaining = remaining[cut:].lstrip("\n")
    if remaining or not text:
        yield remaining


def _transport_failure(error: BaseException) -> Failure:
    reason = getattr(error, "reason", None)
    if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
        return Failure(code="telegram_timeout", message=describe(error), retryable=True)
    if isinstance(error, OSError):
        return Failure(code="telegram_unreachable", message=describe(error), retryable=True)
    return Failure(code="telegram_error", message=describe(error), retryable=True)


def _describe(outcome: LocalAgentOutcome) -> str:
    """A reply that names identities, statuses and codes and never a payload."""
    decision = outcome.decision
    if decision is None:
        return "Nothing was decided."
    target = decision.target
    if decision.kind == "needs_input" or target is None:
        return f"No safe route was selected: {decision.reason}"
    if outcome.capability is not None:
        return f"{target.name}: {outcome.capability.status}"
    if outcome.workflow is not None:
        run = outcome.workflow.run
        text = f"{target.name} run {run.run_id}: {run.status}, {run.completed_steps} step(s)"
        if run.failure is not None:
            text += f" ({run.failure.code})"
        if outcome.unrecorded is not None:
            text += f"; the run record could not be written ({outcome.unrecorded})"
        return text
    return f"{target.name}: {decision.kind}"


class TelegramIngress:
    """One bot, one Bridge, one resident Agent. `poll_once` is the unit a
    host schedules and a test drives; `run` loops it until asked to stop."""

    def __init__(
        self,
        config: TelegramIngressConfig,
        agent: LocalAgent,
        resolver: CredentialResolver,
        *,
        transport: Transport | None = None,
    ) -> None:
        self.config = TelegramIngressConfig.model_validate(config)
        if self.config.bridge_id != agent.membership.device.bridge_id:
            raise ValueError("a Telegram ingress serves the Agent's own device")
        self.agent = agent
        self._resolver = resolver
        self._transport = transport if transport is not None else UrllibTransport()
        self.offset: int | None = None
        self._seen: dict[int, None] = {}

    def _call(self, method: str, payload: Mapping[str, JsonValue]) -> tuple[int, bytes]:
        """One Bot API call. The token is resolved here, used in the URL and
        dropped; nothing on this object ever holds it."""
        token = self._resolver.resolve(self.config.credential)
        url = f"{self.config.api_base}/bot{token}/{method}"
        timeout_s = float(self.config.poll_timeout_seconds + POLL_MARGIN_SECONDS)
        reply = self._transport.send(
            url,
            json.dumps(dict(payload)).encode("utf-8"),
            {"Content-Type": "application/json"},
            timeout_s,
        )
        try:
            body = b"".join(reply.chunks())
        finally:
            close_quietly(reply)
        return reply.status, body

    async def poll_once(self) -> TelegramPollResult:
        """Fetch what arrived since the last poll, hand each text message to
        the Agent, reply, and confirm the batch. A failure is a typed answer
        with the token already redacted; the offset then stays where it was."""
        payload: dict[str, JsonValue] = {
            "timeout": self.config.poll_timeout_seconds,
            "allowed_updates": ["message"],
        }
        if self.offset is not None:
            payload["offset"] = self.offset
        try:
            status, body = await asyncio.to_thread(self._call, "getUpdates", payload)
        except CredentialMisconfigured as error:
            return TelegramPollResult(
                failure=Failure(code="telegram_credential_unavailable", message=describe(error))
            )
        except Exception as error:  # noqa: BLE001 - every transport fault is a typed answer
            return TelegramPollResult(failure=_transport_failure(error))
        if status == 409:
            return TelegramPollResult(
                failure=Failure(
                    code="telegram_conflict",
                    message="another process is polling this bot; only one may",
                )
            )
        if status != 200:
            detail = redacted(body.decode("utf-8", "replace")) or "(no body)"
            return TelegramPollResult(
                failure=Failure(
                    code="telegram_http_error",
                    message=f"{status}: {detail}",
                    retryable=status >= 500,
                )
            )
        try:
            data = json.loads(body)
        except ValueError:
            data = None
        if not isinstance(data, dict) or data.get("ok") is not True:
            return TelegramPollResult(
                failure=Failure(code="telegram_bad_reply", message="the Bot API reply was not ok")
            )
        items = data.get("result")
        if not isinstance(items, list):
            return TelegramPollResult(
                failure=Failure(
                    code="telegram_bad_reply", message="the Bot API reply had no result"
                )
            )
        deliveries: list[TelegramDelivery] = []
        highest = self.offset
        for raw in items:
            # Every update is confirmed, including the kinds this adapter does
            # not handle; otherwise Telegram would redeliver them forever.
            if isinstance(raw, dict) and type(raw.get("update_id")) is int:
                highest = max(highest or 0, raw["update_id"] + 1)
            update = _parse(raw)
            if update is None:
                continue
            if update.update_id in self._seen:
                continue
            self._remember(update.update_id)
            delivery = await self._deliver(update)
            replied = await asyncio.to_thread(self._reply, update.chat_id, delivery.reply)
            deliveries.append(delivery.model_copy(update={"replied": replied}))
        self.offset = highest
        return TelegramPollResult(deliveries=tuple(deliveries), next_offset=self.offset)

    def _remember(self, update_id: int) -> None:
        self._seen[update_id] = None
        while len(self._seen) > SEEN_UPDATES:
            del self._seen[next(iter(self._seen))]

    async def _deliver(self, update: _Update) -> TelegramDelivery:
        base = {
            "update_id": update.update_id,
            "chat_id": update.chat_id,
            "sender_id": update.sender_id,
        }
        actor = self.config.actor_for(update.sender_id)
        if actor is None:
            # Refused before the text is even looked at, and without naming
            # who would have been allowed.
            return TelegramDelivery(
                **base,
                disposition="unmapped_sender",
                reply="This sender is not mapped to a platform actor on this Bridge.",
            )
        if update.text is None or not update.text.strip():
            return TelegramDelivery(
                **base,
                disposition="unsupported_content",
                reply="Only text messages are accepted here.",
            )
        text = update.text.strip()
        if text in ("/start", "/help"):
            return TelegramDelivery(**base, disposition="answered", reply=HELP)
        if text == "/status":
            return TelegramDelivery(**base, disposition="answered", reply=self._status())
        try:
            request = LocalAgentRequest(
                ingress="telegram",
                actor=actor,
                bridge_id=self.config.bridge_id,
                namespace=self.config.namespace,
                message=command_to_message(text),
                trace=TraceIdentifiers(
                    trace_id=f"telegram-{update.update_id}",
                    request_id=f"telegram-{update.update_id}",
                    span_id="telegram",
                ),
                session_id=f"telegram-chat-{update.chat_id}",
            )
        except ValueError:
            # The request contract refuses credential material; the text is
            # not forwarded and not echoed.
            return TelegramDelivery(
                **base,
                disposition="unsupported_content",
                reply="That message was not forwarded: it looks like it contains a credential.",
            )
        outcome = await self.agent.handle(request)
        if outcome.refusal is not None:
            return TelegramDelivery(
                **base,
                disposition="refused",
                reply=f"Refused: {outcome.refusal}.",
                outcome=outcome,
            )
        return TelegramDelivery(
            **base, disposition="routed", reply=redacted(_describe(outcome)), outcome=outcome
        )

    def _status(self) -> str:
        from datetime import UTC, datetime

        snapshot = self.agent.snapshot(observed_at=datetime.now(UTC))
        lines = [
            f"Bridge {snapshot.device.bridge_id}: {len(snapshot.installed)} installed asset(s), "
            f"{len(snapshot.runs)} run(s)"
        ]
        lines.extend(
            f"{item.workflow.name} run {item.run_id}: {item.status}" for item in snapshot.runs[-3:]
        )
        return redacted("\n".join(lines))

    def _reply(self, chat_id: int, text: str) -> bool:
        """Plain text, in pieces Telegram accepts. A reply that cannot be
        sent is reported on the delivery, never raised over the outcome."""
        try:
            for piece in chunks(text):
                status, _ = self._call("sendMessage", {"chat_id": chat_id, "text": piece})
                if status != 200:
                    return False
        except Exception:  # noqa: BLE001 - the delivery records that the reply failed
            return False
        return True

    async def run(self, stop: asyncio.Event, *, interval_s: float = 1.0) -> Failure | None:
        """Poll until asked to stop. A conflict ends the loop, because two
        pollers on one bot steal each other's updates and neither can tell."""
        while not stop.is_set():
            result = await self.poll_once()
            if result.failure is not None and result.failure.code == "telegram_conflict":
                return result.failure
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_s)
            except TimeoutError:
                continue
        return None
