"""Telegram as an ingress to the resident local Agent.

Adapted from the pinned `telegram-local-agent` channel
(`docs/PHASE_7_MIGRATION.md`): outbound long polling, so the company computer
opens no inbound port; a numeric sender checked before anything is routed; and
a slash command that reaches the deterministic router without a model. What
is deliberately not carried over: the token in a configuration file (it is a
`SecretRef` resolved per call and never held), the rule that an empty
allowlist admits everyone (an empty map admits nobody) and HTML presentation.
Files and photos are accepted (owner 2026-10-08) through the shared
`host_runtime.attachments` store, downloaded only after the sender is checked.

The adapter adds no authority. It maps a sender to exactly one platform actor
and hands the Agent a `LocalAgentRequest`; the Agent admits or refuses by the
same membership rule as every other ingress, and the Gateway routes the same
way. Nothing here imports the Bot API library: the wire is the standard
library behind the same `Transport` the model adapters use, with the same
failure rules.
"""

import asyncio
import json
import re
import time
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, JsonValue, StrictBool, field_validator, model_validator

from agent.gateway import TOOL_PROGRESS, ToolProgressState
from agent.routing import DOT_COMMAND
from channels import telegram_flow
from common.action_cards import CARD_TAP, ActionCard, card_in, telegram_card
from common.assets import (
    REDACTED,
    SECRET_PATTERN,
    AssetIdentity,
    SecretRef,
    WorkflowManifest,
    reject_embedded_secrets,
)
from common.base import Contract, Slug, Symbol, Text
from common.distribution import LocalStateError
from common.execution import Failure, TraceIdentifiers
from common.local_agent import LocalAgentRequest, LocalWorkflowRequest
from common.workflow_run_form import form_offer, offer_in, person_prefill, run_intent
from host_runtime.agent import LocalAgent, LocalAgentOutcome
from host_runtime.attachments import (
    KINDS,
    MAX_FILE_BYTES,
    MAX_FILES_PER_MESSAGE,
    Attachment,
    AttachmentError,
    AttachmentStore,
    for_model,
    safe_name,
)
from host_runtime.chat_authoring import ChatAuthoring, ChatAuthoringError, approval_text
from host_runtime.identity_presets import IdentityPresets
from host_runtime.schedule_policy import target_side_effect
from host_runtime.turn_summary import tool_summary
from host_runtime.workflow_uploads import (
    MAX_UPLOAD_BYTES,
    WorkflowUploadError,
    WorkflowUploadStore,
    accepts,
)
from models.contracts import ModelMessage
from models.credentials import CredentialMisconfigured, CredentialResolver
from models.wire import (
    Transport,
    UrllibTransport,
    close_quietly,
    describe,
    status_failure,
    transport_failure,
)

# The channel this ingress consumes, as the durable cursor names it.
TELEGRAM_CHANNEL = "telegram"
# Telegram refuses a message over 4096 characters; the source split at 4000.
MAX_MESSAGE_CHARS = 4000
# Telegram caps long polling at 50 seconds; the transport waits a little longer.
POLL_MARGIN_SECONDS = 10
# Update ids already handled in this process, so a redelivered batch does not
# run a command twice. Bounded, because the process may live a long time.
SEEN_UPDATES = 1000
# How long `run` waits after a retryable failure before polling again, at most.
MAX_BACKOFF_SECONDS = 60.0
SLASH_COMMAND = re.compile(
    r"^/([a-zA-Z_][a-zA-Z0-9_]*)(?:@[A-Za-z0-9_]+)?(?:\s+([a-zA-Z_][a-zA-Z0-9_]*))?(?:\s+(.*))?$",
    re.DOTALL,
)
#: Longest wait honored after a rate-limited reply.
MAX_RETRY_WAIT_S = 5.0
#: Sent when an answer could not be delivered, so the person is not left
#: with only the "Done" status line (owner 2026-10-15).
UNDELIVERED_REPLY = (
    "The answer could not be delivered here (Telegram refused the message). "
    "Ask again, or open Agent Web."
)
SETTINGS_HINT = "Open Agent Web to set them, then send /run again."
HELP = (
    "Talk to the Agent in words, or send a skill command as /<skill> <command> "
    "[arguments]. /run <number or name> asks a Workflow's fields one by one. /status "
    "shows this Bridge's state. /new starts a fresh conversation and forgets its files. "
    "Send files or photos with a caption to have the Agent work on them."
)
#: Telegram lets a bot download at most 20 MB a file (the Bot API's limit).
TELEGRAM_DOWNLOAD_BYTES = 20 * 1024 * 1024
#: The message text when a file or photo comes without a caption.
DEFAULT_CAPTION = "請看附件。"
SUPPORTED_TYPES = ", ".join(suffix.lstrip(".") for suffix in KINDS)
#: A `file_path` from `getFile`, which goes into the download URL.
_FILE_PATH = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,255}$")
_ATTACHMENT_REPLIES = {
    "attachment_type_not_supported": f"不支援這種檔案。可以傳的類型：{SUPPORTED_TYPES}。",
    "attachment_too_large": f"檔案超過 {MAX_FILE_BYTES // (1024 * 1024)} MB 的上限，沒有收下。",
    "attachment_too_many": f"一則訊息最多 {MAX_FILES_PER_MESSAGE} 個檔案，沒有收下。",
    "attachment_telegram_limit": (
        f"Telegram 只讓 Bot 下載 {TELEGRAM_DOWNLOAD_BYTES // (1024 * 1024)} MB 以內的檔案，"
        "這個檔案太大，請改用 Agent Web 上傳。"
    ),
    "attachment_download_failed": "無法從 Telegram 下載附件，請再傳一次。",
    "attachment_zip_invalid": "這個 zip 檔無法解開。",
    "attachment_zip_too_many_files": "zip 裡的檔案太多（上限 2000 個），沒有收下。",
    "attachment_zip_too_large": "zip 解開後超過 200 MB，沒有收下。",
    "attachment_zip_unsafe_path": "zip 裡有會跑出資料夾的路徑，已拒絕。",
    "attachment_unknown": "找不到這個附件。",
}


def attachment_reply(code: str) -> str:
    """What the person is told about an attachment refusal, by its code."""
    return _ATTACHMENT_REPLIES.get(code, f"附件無法處理（{code}）。")


#: Turns of a Telegram chat kept as context for the next one (memory only).
MAX_CHAT_HISTORY = 12
#: How often a "working on it" message refreshes its elapsed time.
PROGRESS_REFRESH_SECONDS = 5.0
_STEP_MARKS: dict[ToolProgressState, str] = {
    "running": "running…",
    "succeeded": "done",
    "failed": "failed",
}

Disposition = Literal[
    "unmapped_sender", "unsupported_content", "answered", "refused", "routed", "failed"
]


def scrub(text: str) -> str:
    """The shared redaction without the error helper's truncation: a reply is
    shown to a person and split for length separately."""
    return SECRET_PATTERN.sub(REDACTED, text)


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

    @field_validator("api_base")
    @classmethod
    def without_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

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
    update reached it; `failure` is why handling it raised; an unmapped
    sender gets no reply at all, so `reply` is None there."""

    update_id: int = Field(ge=0, strict=True)
    chat_id: int = Field(strict=True)
    sender_id: int | None = Field(default=None, strict=True)
    disposition: Disposition
    reply: Text | None = None
    # Inline keyboard rows of (label, callback data) sent with the reply.
    buttons: tuple[tuple[tuple[Text, Text], ...], ...] = ()
    # Replace this message of the chat (a tapped multi-select) instead of
    # sending a new one.
    edit_message_id: int | None = Field(default=None, strict=True)
    replied: StrictBool = False
    outcome: LocalAgentOutcome | None = None
    failure: Failure | None = None

    @model_validator(mode="after")
    def outcome_matches_disposition(self) -> Self:
        reached = self.disposition in ("refused", "routed")
        if reached != (self.outcome is not None):
            raise ValueError("an update that reached the Agent carries its outcome, and only that")
        if self.outcome is not None and (self.disposition == "refused") != (
            self.outcome.refusal is not None
        ):
            raise ValueError("refused means the Agent refused")
        if (self.disposition == "failed") != (self.failure is not None):
            raise ValueError("failed means handling raised, and says why")
        if (self.disposition == "unmapped_sender") != (self.reply is None):
            raise ValueError("an unmapped sender is the only update that gets no reply")
        if self.replied and self.reply is None:
            raise ValueError("nothing was sent when there was nothing to send")
        return self


class TelegramPollResult(Contract):
    """What one poll did. A `failure` beside no deliveries means the poll
    never happened; a failure beside deliveries means the batch was handled
    but could not be confirmed, so Telegram will offer it again."""

    deliveries: tuple[TelegramDelivery, ...] = ()
    failure: Failure | None = None
    next_offset: int | None = None


class _File:
    """A document or photo Telegram announced; nothing is downloaded yet."""

    def __init__(self, file_id: str, filename: str, size: int | None) -> None:
        self.file_id = file_id
        self.filename = filename
        self.size = size


class _Update:
    def __init__(
        self,
        update_id: int,
        chat_id: int,
        sender_id: int,
        text: str | None,
        callback_id: str | None = None,
        sender_name: str = "",
        files: list[_File] | None = None,
        media_group_id: str | None = None,
        message_id: int | None = None,
    ) -> None:
        self.update_id = update_id
        # The message a tapped button sits on, so a toggle can edit it.
        self.message_id = message_id
        self.chat_id = chat_id
        self.sender_id = sender_id
        self.text = text
        # `@username`, else the first name: shown to the owner, never routed.
        self.sender_name = sender_name
        # A tapped inline button: its data is the text, and the tap is
        # acknowledged so the client stops showing it as pending.
        self.callback_id = callback_id
        # Attached files; an album's items share `media_group_id`.
        self.files = files if files is not None else []
        self.media_group_id = media_group_id

    def joins(self, other: "_Update") -> bool:
        """Whether `other` is another item of this update's album."""
        return (
            self.media_group_id is not None
            and self.media_group_id == other.media_group_id
            and self.chat_id == other.chat_id
            and self.sender_id == other.sender_id
        )

    def absorb(self, other: "_Update") -> None:
        self.files.extend(other.files)
        if not (self.text or "").strip() and other.text:
            self.text = other.text


CREDENTIAL_REPLY = "That message was not forwarded: it looks like it contains a credential."
#: Where a card Telegram may not decide is applied (owner 2026-10-15). No
#: address: Agent Web's page key must never travel in a chat.
CARD_WHERE = "Agent Web on this PC, Tasks > Pending changes"
#: The data of an approval button (G4): `approve:<id>` or `reject:<id>`.
APPROVAL_TAP = re.compile(r"^(approve|reject):(ap-[A-Za-z0-9-]{1,64})$")


def _parse(raw: object) -> _Update | None:
    """A text message or a button tap with a sender, or None for anything
    else Telegram sends (edits, channel posts, service messages, malformed items)."""
    if not isinstance(raw, dict) or type(raw.get("update_id")) is not int:
        return None
    callback = raw.get("callback_query")
    if isinstance(callback, dict):
        sender = callback.get("from")
        message = callback.get("message")
        chat = message.get("chat") if isinstance(message, dict) else None
        data = callback.get("data")
        if (
            isinstance(sender, dict)
            and type(sender.get("id")) is int
            and isinstance(chat, dict)
            and type(chat.get("id")) is int
            and isinstance(data, str)
            and isinstance(callback.get("id"), str)
        ):
            identifier = message.get("message_id") if isinstance(message, dict) else None
            return _Update(
                raw["update_id"],
                chat["id"],
                sender["id"],
                data,
                callback["id"],
                sender_name=_display_name(sender),
                message_id=identifier if type(identifier) is int else None,
            )
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
    if not isinstance(text, str):
        # A file's or photo's words are its caption.
        text = message.get("caption")
    group = message.get("media_group_id")
    return _Update(
        raw["update_id"],
        chat["id"],
        sender["id"],
        text if isinstance(text, str) else None,
        sender_name=_display_name(sender),
        files=_files(message, raw["update_id"]),
        media_group_id=group if isinstance(group, str) else None,
    )


def _size(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _files(message: dict[str, Any], update_id: int) -> list[_File]:
    """The document, or the largest size of the photo, a message carries."""
    document = message.get("document")
    if isinstance(document, dict) and isinstance(document.get("file_id"), str):
        name = document.get("file_name")
        if not isinstance(name, str) or not name.strip():
            mime = document.get("mime_type")
            suffix = next((key for key, (_, media) in KINDS.items() if media == mime), "")
            name = f"file-{update_id}{suffix}"
        return [_File(document["file_id"], name, _size(document.get("file_size")))]
    photo = message.get("photo")
    if isinstance(photo, list):
        sizes = [
            item
            for item in photo
            if isinstance(item, dict) and isinstance(item.get("file_id"), str)
        ]
        if sizes:
            largest = max(
                sizes,
                key=lambda item: (
                    _size(item.get("file_size")) or 0,
                    (_size(item.get("width")) or 0) * (_size(item.get("height")) or 0),
                ),
            )
            unique = largest.get("file_unique_id")
            label = unique if isinstance(unique, str) and unique else str(update_id)
            return [
                _File(largest["file_id"], f"photo-{label}.jpg", _size(largest.get("file_size")))
            ]
    return []


def _files_session(key: tuple[int, int]) -> str:
    """The attachment session of one chat and sender, keyed as its history is."""
    return f"telegram-chat-{key[0]}-sender-{key[1]}"


def _display_name(sender: dict[str, Any]) -> str:
    username = sender.get("username")
    if isinstance(username, str) and username:
        return f"@{username}"[:64]
    first = sender.get("first_name")
    return first[:64] if isinstance(first, str) else ""


#: How many unmapped senders the ingress remembers for the settings page.
MAX_UNMAPPED_SENDERS = 20


class UnmappedSender:
    """Somebody who messaged the bot without being in the sender map."""

    def __init__(self, sender_id: int, name: str, seen: datetime) -> None:
        self.sender_id = sender_id
        self.name = name
        self.seen = seen


def slash_command(text: str) -> tuple[str, str | None, str | None] | None:
    """`(alias, command, rest)` for a slash command, with Telegram's group
    suffix `@botname` dropped; None for anything else."""
    match = SLASH_COMMAND.match(text.strip())
    if match is None:
        return None
    rest = match.group(3)
    return match.group(1), match.group(2), rest.strip() if rest and rest.strip() else None


def command_to_message(text: str) -> str:
    """`/skill command rest` becomes `skill.command rest`, the platform's
    deterministic form, so a slash command reaches the router without a model
    as the source's direct commands did. `/skill` alone is the bare word, and
    anything else is passed through as the person wrote it."""
    parsed = slash_command(text)
    if parsed is None:
        return text.strip()
    alias, command, rest = parsed
    head = f"{alias}.{command}" if command else alias
    return f"{head} {rest}" if rest else head


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


def _retry_after(body: bytes) -> float:
    """Seconds Telegram asked to wait after a 429, at most `MAX_RETRY_WAIT_S`."""
    try:
        seconds = json.loads(body).get("parameters", {}).get("retry_after", 1)
    except (ValueError, AttributeError):
        seconds = 1
    return float(min(max(seconds if isinstance(seconds, int | float) else 1, 0), MAX_RETRY_WAIT_S))


def _no_answer_reply(record: str | None) -> str:
    """What a person reads when the model produced no answer, so a turn is
    never silent (owner 2026-10-15)."""
    used = ""
    if record:
        names = [
            line.lstrip("-• ").split(":", 1)[0]
            for line in record.splitlines()
            if line.startswith("- ")
        ]
        used = " after using " + ", ".join(_tool_label(name) for name in names[:5] if name)
    return (
        f"The Agent gave no answer{used}. Ask again or say it differently; to run a "
        "Workflow, send /run <name>."
    )


def _tool_label(name: str) -> str:
    """`weekly-report__run` -> `/weekly-report run`: how the person would type it."""
    alias, _, command = name.partition("__")
    return f"/{alias} {command}".strip()


def _command_label(text: str) -> str:
    return scrub(" ".join(text.split()[:2]))[:80]


def _handled(outcome: LocalAgentOutcome) -> bool:
    if outcome.capability is not None:
        return outcome.capability.status == "succeeded"
    if outcome.workflow is not None:
        return outcome.workflow.run.status == "succeeded"
    return False


class _Progress:
    """One "working on it" message per request, edited in place while the
    Agent works: how long it has taken and which skills it used. Only tool
    names are shown, never arguments or results. Every Bot API call runs off
    the event loop, one at a time, so edits arrive in order."""

    def __init__(self, ingress: "TelegramIngress", chat_id: int, title: str) -> None:
        self._ingress = ingress
        self._chat_id = chat_id
        self._title = title
        self._started = time.monotonic()
        self._message_id: int | None = None
        self._steps: dict[str, ToolProgressState] = {}
        self._lock = asyncio.Lock()
        self._pending: set[asyncio.Task[None]] = set()
        self._ticker: asyncio.Task[None] | None = None

    def text(self, outcome: bool | None = None) -> str:
        seconds = int(time.monotonic() - self._started)
        if outcome is None:
            head = f"⏳ {self._title}… {seconds} s"
        else:
            head = f"{'✅ Done' if outcome else '⚠️ Stopped'} after {seconds} s"
        lines = [head]
        if self._steps:
            lines.append("Skills used:" if outcome is not None else "Skills:")
            lines.extend(
                f"• {_tool_label(name)} — {_STEP_MARKS[state]}"
                for name, state in self._steps.items()
            )
        elif outcome is not None:
            lines.append("No skills were used.")
        return scrub("\n".join(lines))

    async def open(self) -> None:
        self._message_id = await asyncio.to_thread(
            self._ingress._send_status, self._chat_id, self.text()
        )
        if self._message_id is not None:
            self._ticker = asyncio.create_task(self._tick())

    def tool(self, name: str, state: ToolProgressState) -> None:
        """The Gateway's TOOL_PROGRESS listener; called on the event loop."""
        self._steps[name] = state
        self._schedule()

    async def finish(self, succeeded: bool) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)
        await self._edit(self.text(succeeded))

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(self._ingress.progress_refresh_s)
            self._schedule()

    def _schedule(self) -> None:
        task = asyncio.get_running_loop().create_task(self._edit(self.text()))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _edit(self, text: str) -> None:
        if self._message_id is None:
            return
        async with self._lock:
            await asyncio.to_thread(
                self._ingress._edit_status, self._chat_id, self._message_id, text
            )


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
        attachments: AttachmentStore | None = None,
        uploads: WorkflowUploadStore | None = None,
        presets: IdentityPresets | None = None,
    ) -> None:
        self.config = TelegramIngressConfig.model_validate(config)
        if self.config.bridge_id != agent.membership.device.bridge_id:
            raise ValueError("a Telegram ingress serves the Agent's own device")
        self.agent = agent
        self._resolver = resolver
        self._transport = transport if transport is not None else UrllibTransport()
        self.unmapped: dict[int, UnmappedSender] = {}
        self.progress_refresh_s = PROGRESS_REFRESH_SECONDS
        self._histories: dict[tuple[int, int], list[ModelMessage]] = {}
        # Conversation run and install requests (G4); set by the host once it exists.
        self.approvals: ChatAuthoring | None = None
        # Within a process, a duplicate inside one response is skipped; across
        # a restart, the durable cursor is what stops a batch being replayed.
        self._seen: dict[int, None] = {}
        # Open Workflow question flows, by (chat, sender); they expire.
        self._flows: dict[tuple[int, int], telegram_flow.FlowState] = {}
        # Where attached files are kept; without it files are refused.
        self.attachments = attachments
        # Workflow `upload` fields (forms v2): documents sent while a flow
        # waits on one are stored here; without it such fields are refused.
        self.uploads = uploads
        # The member's identity answers from last time ("same as last time?").
        self.presets = presets
        # Action cards (change proposals): Agent Web decides them; set by it.
        self.cards: Any = None
        # A plain reason for a failed model turn (e.g. the LLM gateway is not
        # running or still starting); set by the host, None says nothing more.
        self.explain_failure: Callable[[Failure], str | None] | None = None

    def offset(self) -> int | None:
        """How far this bot has been consumed, from the Bridge's own durable
        state rather than from memory, so a restart resumes where the last
        confirmed batch ended."""
        return self.agent.state.cursor(TELEGRAM_CHANNEL)

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
            "allowed_updates": ["message", "callback_query"],
        }
        try:
            offset = await asyncio.to_thread(self.offset)
        except LocalStateError as error:
            # Without the cursor this poll would replay a confirmed batch.
            # Worth trying again: the usual reason is another process holding
            # the state file for a moment, not a broken ingress.
            return TelegramPollResult(
                failure=Failure(
                    code="telegram_cursor_unavailable", message=error.code, retryable=True
                )
            )
        if offset is not None:
            payload["offset"] = offset
        try:
            status, body = await asyncio.to_thread(self._call, "getUpdates", payload)
        except CredentialMisconfigured as error:
            return TelegramPollResult(
                failure=Failure(code="telegram_credential_unavailable", message=describe(error))
            )
        except Exception as error:  # noqa: BLE001 - every transport fault is a typed answer
            return TelegramPollResult(failure=transport_failure(error, prefix="telegram"))
        if status == 409:
            return TelegramPollResult(
                failure=Failure(
                    code="telegram_conflict",
                    message="another process is polling this bot; only one may",
                )
            )
        if status != 200:
            return TelegramPollResult(failure=status_failure(status, body, prefix="telegram"))
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
        highest = offset
        updates: list[_Update] = []
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
            # An album arrives as one update per file; the items in this
            # batch become one turn, answered once.
            album = next((item for item in updates if item.joins(update)), None)
            if album is not None:
                album.absorb(update)
                continue
            updates.append(update)
        for update in updates:
            delivery = await self._deliver_guarded(update)
            if update.callback_id is not None:
                await asyncio.to_thread(self._acknowledge, update.callback_id)
            if delivery.reply is not None:
                replied = False
                if delivery.edit_message_id is not None:
                    replied = await asyncio.to_thread(
                        self._edit_reply,
                        update.chat_id,
                        delivery.edit_message_id,
                        delivery.reply,
                        delivery.buttons,
                    )
                if not replied:
                    replied = await asyncio.to_thread(
                        self._reply, update.chat_id, delivery.reply, delivery.buttons
                    )
                if not replied:
                    # Never silent: say that the answer did not arrive.
                    await asyncio.to_thread(self._reply, update.chat_id, UNDELIVERED_REPLY)
                delivery = delivery.model_copy(update={"replied": replied})
            deliveries.append(delivery)
        if highest is None or highest == offset:
            return TelegramPollResult(deliveries=tuple(deliveries), next_offset=offset)
        try:
            await asyncio.to_thread(self.agent.state.advance_cursor, TELEGRAM_CHANNEL, highest)
        except LocalStateError as error:
            # The batch was handled; it just is not confirmed. Telegram will
            # offer it again, and `_seen` keeps this process from repeating it.
            return TelegramPollResult(
                deliveries=tuple(deliveries),
                failure=Failure(
                    code="telegram_cursor_unconfirmed", message=error.code, retryable=True
                ),
                next_offset=offset,
            )
        return TelegramPollResult(deliveries=tuple(deliveries), next_offset=highest)

    def _remember(self, update_id: int) -> None:
        self._seen[update_id] = None
        while len(self._seen) > SEEN_UPDATES:
            del self._seen[next(iter(self._seen))]

    async def _deliver_guarded(self, update: _Update) -> TelegramDelivery:
        """Handling one update never takes the poll loop down with it. What
        raised is recorded on the delivery with its type and a redacted
        message, and the sender is told the request could not be handled."""
        try:
            return await self._deliver(update)
        except Exception as error:  # noqa: BLE001 - recorded, not propagated
            return TelegramDelivery(
                update_id=update.update_id,
                chat_id=update.chat_id,
                sender_id=update.sender_id,
                disposition="failed",
                reply="That request could not be handled on this Bridge.",
                failure=Failure(code="telegram_delivery_failed", message=describe(error)),
            )

    async def _deliver(self, update: _Update) -> TelegramDelivery:
        base = {
            "update_id": update.update_id,
            "chat_id": update.chat_id,
            "sender_id": update.sender_id,
        }
        actor = self.config.actor_for(update.sender_id)
        if actor is None:
            # Refused before the text is even looked at, and not answered: a
            # stranger who found the bot learns nothing and spends nothing.
            # The owner sees the id on the settings page and may allow it.
            self.unmapped[update.sender_id] = UnmappedSender(
                update.sender_id, update.sender_name, datetime.now(UTC)
            )
            while len(self.unmapped) > MAX_UNMAPPED_SENDERS:
                oldest = min(self.unmapped.values(), key=lambda item: item.seen)
                del self.unmapped[oldest.sender_id]
            return TelegramDelivery(**base, disposition="unmapped_sender")
        if update.files:
            waiting = self._flows.get((update.chat_id, update.sender_id))
            if (
                waiting is not None
                and not waiting.expired()
                and (telegram_flow.current_upload(waiting) is not None)
            ):
                return await self._flow_upload(base, waiting, actor, update)
            return await self._attached(base, actor, update)
        if update.text is None or not update.text.strip():
            return TelegramDelivery(
                **base,
                disposition="unsupported_content",
                reply="Only text messages are accepted here.",
            )
        text = update.text.strip()
        key = (update.chat_id, update.sender_id)
        card_tap = CARD_TAP.match(text)
        if card_tap is not None:
            return await self._decide_card(
                base, key, actor, card_tap.group(1), card_tap.group(2), update
            )
        tapped = APPROVAL_TAP.match(text)
        if tapped is not None:
            return await self._decide(base, key, actor, tapped.group(1), tapped.group(2))
        parsed = slash_command(text)
        active = self._flows.get(key)
        if active is not None and active.expired():
            del self._flows[key]
            active = None
        if active is not None and not (
            parsed is not None and parsed[0] in ("run", "start", "help", "status")
        ):
            step = telegram_flow.answer(active, text)
            return await self._flow_step(base, key, active, step, actor, update)
        if parsed is not None and parsed[0] == "run":
            return await self._start_flow(base, key, parsed, actor, update)
        if parsed is not None and parsed[0] in ("start", "help"):
            return TelegramDelivery(**base, disposition="answered", reply=HELP)
        if parsed is not None and parsed[0] == "new":
            self._histories.pop(key, None)
            if self.attachments is not None:
                await asyncio.to_thread(self.attachments.delete_session, _files_session(key))
            return TelegramDelivery(
                **base, disposition="answered", reply="Started a fresh conversation."
            )
        if parsed is not None and parsed[0] == "status":
            # A durable read under the store's lock, so never on the event loop.
            report = await asyncio.to_thread(self._status)
            return TelegramDelivery(**base, disposition="answered", reply=report)
        request = self._request(update, actor, text)
        if request is None:
            return TelegramDelivery(
                **base, disposition="unsupported_content", reply=CREDENTIAL_REPLY
            )
        if parsed is None and not DOT_COMMAND.match(text):
            # "Run X" for an installed Workflow is its question flow, as
            # /run X is, never the model's prose (owner 2026-10-15).
            intent = run_intent(text, self.agent.gateway.engine.workflows.manifests())
            if intent is not None:
                return await self._open_flow(
                    base, key, intent.manifest, actor, update, intent.prefill
                )
        if (
            parsed is None
            and not DOT_COMMAND.match(text)
            and self.agent.gateway.router.model is not None
        ):
            # Free text is a conversation, as in Agent Web: the model answers
            # and may call installed tools under the same policy.
            return await self._converse(base, key, request, text, actor=actor, update=update)
        progress = await self._progress(update.chat_id, f"Running {_command_label(text)}")
        succeeded = False
        try:
            outcome = await self.agent.handle(request)
            succeeded = outcome.refusal is None and _handled(outcome)
        finally:
            await progress.finish(succeeded)
        if outcome.refusal is not None:
            return TelegramDelivery(
                **base,
                disposition="refused",
                reply=f"Refused: {outcome.refusal}.",
                outcome=outcome,
            )
        return TelegramDelivery(
            **base, disposition="routed", reply=scrub(_describe(outcome)), outcome=outcome
        )

    def _request(self, update: _Update, actor: str, text: str) -> LocalAgentRequest | None:
        """The Agent request for `text`, or None when the request contract
        refuses it as credential material; the text is then not forwarded
        and not echoed."""
        # Whose machine this is. A sender who is that member drives it as
        # themselves; anybody else has it done on their behalf, and the
        # Agent decides whether this kind of machine allows that.
        acting, on_behalf_of = self._acting(actor)
        try:
            return LocalAgentRequest(
                ingress="telegram",
                actor=acting,
                on_behalf_of=on_behalf_of,
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
            return None

    async def _attached(
        self, base: dict[str, Any], actor: str, update: _Update
    ) -> TelegramDelivery:
        """A message with files or photos (owner 2026-10-08): checked against
        the limits before anything is downloaded, saved with the shared store,
        and given to the conversation model as Agent Web does. The caller has
        already admitted the sender."""

        def refused(code: str) -> TelegramDelivery:
            return TelegramDelivery(
                **base, disposition="unsupported_content", reply=attachment_reply(code)
            )

        if self.attachments is None:
            return TelegramDelivery(
                **base, disposition="unsupported_content", reply="這個 Bridge 不接受附件。"
            )
        if self.agent.gateway.router.model is None:
            return TelegramDelivery(
                **base,
                disposition="unsupported_content",
                reply="附件需要對話模型，這個 Bridge 目前沒有設定。",
            )
        if len(update.files) > MAX_FILES_PER_MESSAGE:
            return refused("attachment_too_many")
        for file in update.files:
            if Path(safe_name(file.filename)).suffix.lower() not in KINDS:
                return refused("attachment_type_not_supported")
            if file.size is not None and file.size > MAX_FILE_BYTES:
                return refused("attachment_too_large")
            if file.size is not None and file.size > TELEGRAM_DOWNLOAD_BYTES:
                return refused("attachment_telegram_limit")
        text = (update.text or "").strip() or DEFAULT_CAPTION
        request = self._request(update, actor, text)
        if request is None:
            return TelegramDelivery(
                **base, disposition="unsupported_content", reply=CREDENTIAL_REPLY
            )
        key = (update.chat_id, update.sender_id)
        try:
            saved = await asyncio.to_thread(self._save, _files_session(key), update.files)
            note, images = await asyncio.to_thread(for_model, saved)
        except AttachmentError as error:
            return TelegramDelivery(
                **base, disposition="answered", reply=attachment_reply(error.code)
            )
        # Later turns keep the names and paths, never the content.
        listing = "[附件]\n" + "\n".join(
            f"- {item.filename} ({item.kind}): {item.path}" for item in saved
        )
        return await self._converse(
            base, key, request, text, (note, images, listing), actor=actor, update=update
        )

    def _save(self, session_id: str, files: list[_File]) -> list[Attachment]:
        assert self.attachments is not None
        return [
            self.attachments.add(session_id, file.filename, self._download(file.file_id))
            for file in files
        ]

    def _download(self, file_id: str) -> bytes:
        """`getFile`, then the file itself, through the bot's own transport.
        The token is resolved for the URL and dropped; a failure is reported
        by code only, so no URL or error text can carry it anywhere."""
        try:
            status, body = self._call("getFile", {"file_id": file_id})
            result = json.loads(body).get("result") if status == 200 else None
            path = result.get("file_path") if isinstance(result, dict) else None
            if not isinstance(path, str) or not _FILE_PATH.match(path) or ".." in path:
                raise AttachmentError("attachment_download_failed")
            size = _size(result.get("file_size")) if isinstance(result, dict) else None
            if size is not None and size > MAX_FILE_BYTES:
                raise AttachmentError("attachment_too_large")
            token = self._resolver.resolve(self.config.credential)
            url = f"{self.config.api_base}/file/bot{token}/{path}"
            del token
            timeout_s = float(self.config.poll_timeout_seconds + POLL_MARGIN_SECONDS)
            # A file is read with GET where the transport can name the method.
            method = getattr(self._transport, "request", None)
            reply = (
                method("GET", url, None, {}, timeout_s)
                if callable(method)
                else self._transport.send(url, b"", {}, timeout_s)
            )
            del url
            try:
                if reply.status != 200:
                    raise AttachmentError("attachment_download_failed")
                data = bytearray()
                for chunk in reply.chunks():
                    data.extend(chunk)
                    if len(data) > MAX_FILE_BYTES:
                        raise AttachmentError("attachment_too_large")
            finally:
                close_quietly(reply)
            return bytes(data)
        except AttachmentError:
            raise
        except Exception:  # noqa: BLE001 - the error text could name the URL
            raise AttachmentError("attachment_download_failed") from None

    def _approval_buttons(
        self, request: LocalAgentRequest
    ) -> tuple[tuple[tuple[str, str], ...], ...]:
        """One row per pending request the Agent made in this chat (G4, A5).
        With Agent Web's draft cards, an install is answered on its card."""
        if self.approvals is None:
            return ()
        carded: set[str] = set()
        draft_cards = getattr(self.cards, "draft_cards", None)
        if draft_cards is not None and request.session_id:
            carded = draft_cards.carded(request.session_id)
        rows = []
        for item in self.approvals.approvals(request.actor, session_id=request.session_id):
            if item.kind in ("install", "install_skill") and item.candidate_id in carded:
                continue
            label = "安裝" if item.kind == "install" else "執行"
            rows.append(
                (
                    (f"核准{label} {item.workflow}"[:60], f"approve:{item.approval_id}"),
                    ("拒絕", f"reject:{item.approval_id}"),
                )
            )
        return tuple(rows)

    async def _decide(
        self,
        base: dict[str, Any],
        key: tuple[int, int],
        actor: str,
        decision: str,
        approval_id: str,
    ) -> TelegramDelivery:
        """An approval button. Only the owner decides: a sender acting on the
        owner's behalf is refused, and the model never reaches this."""
        acting, on_behalf_of = self._acting(actor)
        if self.approvals is None:
            return TelegramDelivery(
                **base, disposition="answered", reply="Approvals are not available on this Bridge."
            )
        if on_behalf_of is not None:
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply="Only the owner of this Bridge can approve or reject.",
            )
        try:
            decided = await asyncio.to_thread(
                self.approvals.decide, approval_id, acting, decision == "approve"
            )
        except ChatAuthoringError as error:
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply=f"That request was already decided or is unknown ({error.code}).",
            )
        text = approval_text(decided)
        history = self._histories.get(key, [])
        said = ("【核准】" if decision == "approve" else "【拒絕】") + decided.summary
        history = [
            *history,
            ModelMessage(role="user", text=said),
            ModelMessage(role="assistant", text=text),
        ]
        self._histories[key] = history[-MAX_CHAT_HISTORY:]
        return TelegramDelivery(**base, disposition="answered", reply=scrub(text))

    async def _decide_card(
        self,
        base: dict[str, Any],
        key: tuple[int, int],
        actor: str,
        card_id: str,
        action: str,
        update: _Update,
    ) -> TelegramDelivery:
        """A card's button. Only the owner decides, as for approvals; Agent
        Web refuses a kind Telegram may not apply. The card is redrawn in
        place with its outcome."""
        _acting, on_behalf_of = self._acting(actor)
        if self.cards is None:
            return TelegramDelivery(
                **base, disposition="answered", reply="Cards are not available on this Bridge."
            )
        if on_behalf_of is not None:
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply="Only the owner of this Bridge can apply or cancel.",
            )
        decided = await asyncio.to_thread(self.cards.decide_card, card_id, action, "telegram")
        message = str(decided.get("message") or decided.get("code") or "Done.")
        card = decided.get("card")
        if isinstance(card, dict):
            drawn, buttons = telegram_card(ActionCard.model_validate(card), CARD_WHERE)
            history = self._histories.get(key, [])
            history = [
                *history,
                ModelMessage(role="user", text=f"[{action}] {card['title']}"),
                ModelMessage(role="assistant", text=drawn),
            ]
            self._histories[key] = history[-MAX_CHAT_HISTORY:]
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply=scrub(drawn),
                buttons=buttons,
                edit_message_id=update.message_id,
            )
        return TelegramDelivery(**base, disposition="answered", reply=scrub(message))

    async def _converse(
        self,
        base: dict[str, Any],
        key: tuple[int, int],
        request: LocalAgentRequest,
        text: str,
        attached: tuple[str, tuple[str, ...], str] | None = None,
        *,
        actor: str | None = None,
        update: _Update | None = None,
    ) -> TelegramDelivery:
        """`attached` is the files' note and pictures for the model, and the
        short listing the stored history keeps in their place."""
        history = self._histories.get(key, [])
        if attached is None:
            turn = [*history, ModelMessage(role="user", text=text)]
            sent = turn
        else:
            note, images, listing = attached
            turn = [*history, ModelMessage(role="user", text=f"{text}\n\n{listing}")]
            # The files ride on the newest message only, as in Agent Web.
            sent = [*history, ModelMessage(role="user", text=f"{text}\n\n{note}", images=images)]
        progress = await self._progress(base["chat_id"], "Working on it")
        listening = TOOL_PROGRESS.set(progress.tool)
        answered = False
        started = datetime.now(UTC)
        try:
            result = await self.agent.converse(request, tuple(sent))
            answered = result.conversation is not None and result.conversation.status == "answered"
        finally:
            TOOL_PROGRESS.reset(listening)
            await progress.finish(answered)
        if result.refusal is not None:
            return TelegramDelivery(
                **base, disposition="answered", reply=f"Refused: {result.refusal}."
            )
        conversation = result.conversation
        drafted = await self._draft_cards(request, started)
        buttons = self._approval_buttons(request)
        record = tool_summary(conversation)
        if conversation is None or conversation.status != "answered":
            code = (
                conversation.failure.code
                if conversation is not None and conversation.failure is not None
                else "conversation_failed"
            )
            reply = f"That could not be answered ({code})."
            explained = (
                self.explain_failure(conversation.failure)
                if self.explain_failure is not None
                and conversation is not None
                and conversation.failure is not None
                else None
            )
            if explained:
                reply = explained
            if code == "empty_model_answer":
                # Never a silent turn: say what happened (owner 2026-10-15).
                reply = _no_answer_reply(record)
            if code == "tool_loop_limit" and conversation is not None:
                reply = (
                    f"這個回合已用完 {len(conversation.tools)} 次工具呼叫，工作還沒完成；"
                    "回覆「繼續」我會接著做。"
                )
                # Keep what was done so 繼續 can pick it up.
                turn.append(ModelMessage(role="assistant", text=f"{reply}\n\n[工具紀錄]\n{record}"))
                self._histories[key] = turn[-MAX_CHAT_HISTORY:]
            if drafted:
                return self._carded(base, reply, buttons, drafted)
            return TelegramDelivery(**base, disposition="answered", reply=reply, buttons=buttons)
        answer = conversation.text if conversation.text.strip() else _no_answer_reply(record)
        remembered = answer if record is None else f"{answer}\n\n[工具紀錄]\n{record}"
        turn.append(ModelMessage(role="assistant", text=remembered))
        self._histories[key] = turn[-MAX_CHAT_HISTORY:]
        offer = offer_in(conversation.tools)
        if offer is not None and actor is not None and update is not None:
            # The model handed over a Workflow's form: ask its questions here.
            manifest = self._offered_workflow(offer)
            if manifest is not None:
                prefill = offer.get("prefill")
                return await self._open_flow(
                    base, key, manifest, actor, update, prefill if isinstance(prefill, dict) else {}
                )
        card = card_in(conversation.tools)
        if card is not None:
            # A proposal: the card, with Apply/Cancel only for the kinds
            # Telegram may apply (owner 2026-10-15).
            drawn, card_buttons = telegram_card(ActionCard.model_validate(card), CARD_WHERE)
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply=scrub(drawn),
                buttons=(*card_buttons, *buttons),
            )
        if drafted:
            return self._carded(base, answer, buttons, drafted)
        return TelegramDelivery(
            **base, disposition="answered", reply=scrub(answer), buttons=buttons
        )

    def _carded(
        self,
        base: dict[str, Any],
        answer: str,
        buttons: tuple[tuple[tuple[str, str], ...], ...],
        drafted: list[dict[str, Any]],
    ) -> TelegramDelivery:
        """A Workflow or Skill drafted in this turn: the answer, then its
        install card with Install / Not now; a press is the owner's approval,
        as for the approval buttons (owner 2026-10-16)."""
        texts = [answer]
        card_rows: list[tuple[tuple[str, str], ...]] = []
        for shown in drafted:
            drawn, card_buttons = telegram_card(ActionCard.model_validate(shown), CARD_WHERE)
            texts.append(drawn)
            card_rows.extend(card_buttons)
        return TelegramDelivery(
            **base,
            disposition="answered",
            reply=scrub("\n\n".join(texts)),
            buttons=(*card_rows, *buttons),
        )

    async def _draft_cards(
        self, request: LocalAgentRequest, started: datetime
    ) -> list[dict[str, Any]]:
        """The install cards for drafts this turn made, when Agent Web runs
        with this bot (it keeps and decides the cards)."""
        maker = getattr(self.cards, "draft_turn_cards", None)
        if maker is None or not request.session_id:
            return []
        try:
            found = await asyncio.to_thread(maker, request.session_id, started, "telegram")
        except Exception:  # noqa: BLE001 - a card is extra; the answer still goes out
            return []
        return [item for item in found if isinstance(item, dict)]

    def _acting(self, actor: str) -> tuple[str, str | None]:
        """Who runs and on whose behalf, as for every other request."""
        member = self.agent.membership.member()
        acting = member if member is not None and member != actor else actor
        return acting, actor if acting != actor else None

    def _resolve_workflow(self, target: str) -> WorkflowManifest | str:
        installed = self.agent.gateway.engine.workflows.manifests()
        if not target:
            return "Name the Workflow: /run <number or name>."
        found = [
            item
            for item in installed
            if (target.isdigit() and item.run_alias == int(target))
            or target
            in (
                item.metadata.identity.name,
                f"{item.metadata.identity.namespace}/{item.metadata.identity.name}",
            )
        ]
        if len(found) != 1:
            return (
                f"No single installed Workflow is called {target}."
                if not found
                else f"{target} names more than one Workflow; use namespace/name."
            )
        return found[0]

    async def _start_flow(
        self,
        base: dict[str, int],
        key: tuple[int, int],
        parsed: tuple[str, str | None, str | None],
        actor: str,
        update: _Update,
    ) -> TelegramDelivery:
        target = " ".join(part for part in parsed[1:] if part).strip()
        manifest = self._resolve_workflow(target)
        if isinstance(manifest, str):
            return TelegramDelivery(**base, disposition="answered", reply=manifest)
        return await self._open_flow(base, key, manifest, actor, update, {})

    def _offered_workflow(self, offer: Mapping[str, Any]) -> WorkflowManifest | None:
        try:
            identity = AssetIdentity.model_validate(offer.get("workflow"))
        except ValueError:
            return None
        return self.agent.gateway.engine.workflows.get(identity)

    async def _open_flow(
        self,
        base: dict[str, Any],
        key: tuple[int, int],
        manifest: WorkflowManifest,
        actor: str,
        update: _Update,
        prefill: Mapping[str, Any],
    ) -> TelegramDelivery:
        """The Workflow's question flow, with values already given as answers
        (confirmed before the run), or why it cannot run yet."""
        engine = self.agent.gateway.engine
        offer = form_offer(
            manifest, person_prefill(manifest, prefill, ("telegram",)), engine.settings_provider
        )
        if offer["missing_settings"]:
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply=scrub(str(offer["message"])) + "\n" + SETTINGS_HINT,
            )
        effect = await asyncio.to_thread(
            target_side_effect, self.agent, "workflow", manifest.metadata.identity, {}
        )
        preset = (
            await asyncio.to_thread(self.presets.last, actor, manifest)
            if self.presets is not None
            else {}
        )
        state = telegram_flow.start(
            manifest,
            effect,
            engine.choices_provider,
            uploads=self.uploads is not None,
            preset=preset,
            prefill=offer["prefill"],
        )
        if isinstance(state, str):
            return TelegramDelivery(**base, disposition="answered", reply=state)
        return await self._flow_step(base, key, state, telegram_flow.begin(state), actor, update)

    async def _flow_step(
        self,
        base: dict[str, int],
        key: tuple[int, int],
        state: telegram_flow.FlowState,
        step: telegram_flow.FlowStep,
        actor: str,
        update: _Update,
    ) -> TelegramDelivery:
        if step.kind == "ask" and step.prompt is not None:
            self._flows[key] = state
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply=scrub(step.prompt.text),
                buttons=tuple(tuple(row) for row in step.prompt.buttons),
                edit_message_id=update.message_id if step.prompt.edit else None,
            )
        self._flows.pop(key, None)
        if step.kind == "cancelled" or step.arguments is None:
            return TelegramDelivery(**base, disposition="answered", reply="Cancelled.")
        if self.presets is not None:
            await asyncio.to_thread(self.presets.remember, actor, state.manifest, step.arguments)
        acting, on_behalf_of = self._acting(actor)
        progress = await self._progress(update.chat_id, f"Running Workflow {state.workflow.name}")
        succeeded = False
        try:
            outcome = await self._execute_flow(state, step, acting, on_behalf_of, update)
            succeeded = outcome.workflow is not None and outcome.workflow.run.status == "succeeded"
        finally:
            await progress.finish(succeeded)
        if outcome.refusal is not None:
            return TelegramDelivery(
                **base,
                disposition="refused",
                reply=f"Refused: {outcome.refusal}.",
                outcome=outcome,
            )
        if outcome.workflow is None:
            reply = f"{state.workflow.name}: nothing ran."
        else:
            run = outcome.workflow.run
            reply = (
                f"{state.workflow.name} run {run.run_id}: {run.status}, "
                f"{run.completed_steps} step(s)"
                + (f" ({run.failure.code})" if run.failure is not None else "")
            )
        return TelegramDelivery(**base, disposition="routed", reply=scrub(reply), outcome=outcome)

    async def _flow_upload(
        self,
        base: dict[str, Any],
        state: telegram_flow.FlowState,
        actor: str,
        update: _Update,
    ) -> TelegramDelivery:
        """Documents for the upload field a flow waits on (forms v2): checked
        against the field and the limits before anything is downloaded, then
        stored in the Workflow upload store; the run gets their paths."""
        assert self.uploads is not None
        item = telegram_flow.current_upload(state)
        assert item is not None
        key = (update.chat_id, update.sender_id)

        def again(message: str) -> TelegramDelivery:
            reprompt = telegram_flow.prompt(state)
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply=scrub(f"{message}\n\n{reprompt.text}"),
                buttons=tuple(tuple(row) for row in reprompt.buttons),
            )

        if not item.multiple and len(update.files) > 1:
            return again("Send one file here.")
        for file in update.files:
            if not accepts(item, safe_name(file.filename)):
                return again(f"{safe_name(file.filename)} is not a {', '.join(item.accept)} file.")
            if file.size is not None and file.size > TELEGRAM_DOWNLOAD_BYTES:
                return again(attachment_reply("attachment_telegram_limit"))
            if file.size is not None and file.size > MAX_UPLOAD_BYTES:
                return again(attachment_reply("attachment_too_large"))
        if state.upload_set is None:
            state.upload_set = await asyncio.to_thread(self.uploads.new_set)
        step: telegram_flow.FlowStep | None = None
        for file in update.files:
            try:
                data = await asyncio.to_thread(self._download, file.file_id)
                path = await asyncio.to_thread(
                    self.uploads.add, state.upload_set, item, file.filename, data
                )
            except AttachmentError as error:
                return again(attachment_reply(error.code))
            except WorkflowUploadError as error:
                return again(f"That file was not kept ({error.code}).")
            step = telegram_flow.add_upload(state, str(path))
        assert step is not None
        return await self._flow_step(base, key, state, step, actor, update)

    def _edit_reply(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        buttons: tuple[tuple[tuple[str, str], ...], ...] = (),
    ) -> bool:
        """Replace one message's text and keyboard (a multi-select toggle)."""
        if len(text) > MAX_MESSAGE_CHARS:
            return False
        try:
            status, _ = self._call(
                "editMessageText",
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": label, "callback_data": data} for label, data in row]
                            for row in buttons
                        ]
                    },
                },
            )
        except Exception:  # noqa: BLE001 - the caller sends a new message instead
            return False
        return status == 200

    async def _execute_flow(
        self,
        state: telegram_flow.FlowState,
        step: telegram_flow.FlowStep,
        acting: str,
        on_behalf_of: str | None,
        update: _Update,
    ) -> LocalAgentOutcome:
        assert step.arguments is not None
        return await self.agent.execute_workflow(
            LocalWorkflowRequest(
                ingress="telegram",
                actor=acting,
                on_behalf_of=on_behalf_of,
                bridge_id=self.config.bridge_id,
                workflow=state.workflow,
                arguments=step.arguments,
                idempotency_key=f"telegram-{update.update_id}",
                trace=TraceIdentifiers(
                    trace_id=f"telegram-{update.update_id}",
                    request_id=f"telegram-{update.update_id}",
                    span_id="telegram-flow",
                ),
            )
        )

    async def _progress(self, chat_id: int, title: str) -> "_Progress":
        progress = _Progress(self, chat_id, title)
        await progress.open()
        return progress

    def _send_status(self, chat_id: int, text: str) -> int | None:
        """Send one plain message and return its id, or None when it could not
        be sent; progress is a courtesy and never fails the request."""
        try:
            status, body = self._call("sendMessage", {"chat_id": chat_id, "text": text})
            if status != 200:
                return None
            message = json.loads(body).get("result")
            identifier = message.get("message_id") if isinstance(message, dict) else None
            return identifier if type(identifier) is int else None
        except Exception:  # noqa: BLE001 - see above
            return None

    def _edit_status(self, chat_id: int, message_id: int, text: str) -> None:
        try:
            self._call(
                "editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text}
            )
        except Exception:  # noqa: BLE001 - a stale status line is not worth a failure
            pass

    def _status(self) -> str:
        snapshot = self.agent.snapshot(observed_at=datetime.now(UTC))
        lines = [
            f"Bridge {snapshot.device.bridge_id}: {len(snapshot.installed)} installed asset(s), "
            f"{len(snapshot.runs)} run(s)"
        ]
        lines.extend(
            f"{item.workflow.name} run {item.run_id}: {item.status}" for item in snapshot.runs[-3:]
        )
        return scrub("\n".join(lines))

    def _reply(
        self,
        chat_id: int,
        text: str,
        buttons: tuple[tuple[tuple[str, str], ...], ...] = (),
    ) -> bool:
        """Plain text, in pieces Telegram accepts, with any inline keyboard on
        the last piece. A reply that cannot be sent is reported on the
        delivery, never raised over the outcome."""
        try:
            pieces = [piece for piece in chunks(text) if piece.strip()]
            if not pieces:
                return False
            for position, piece in enumerate(pieces):
                payload: dict[str, JsonValue] = {"chat_id": chat_id, "text": piece}
                if buttons and position == len(pieces) - 1:
                    payload["reply_markup"] = {
                        "inline_keyboard": [
                            [{"text": label, "callback_data": data} for label, data in row]
                            for row in buttons
                        ]
                    }
                if not self._send_piece(payload):
                    return False
        except Exception:  # noqa: BLE001 - the delivery records that the reply failed
            return False
        return True

    def _send_piece(self, payload: dict[str, JsonValue]) -> bool:
        """One `sendMessage`, retried once after a rate limit (the progress
        edits just before it can trigger one) and once without its keyboard
        when Telegram refuses the message, so an answer is not lost."""
        status, body = self._call("sendMessage", payload)
        if status == 429:
            time.sleep(_retry_after(body))
            status, body = self._call("sendMessage", payload)
        if status == 400 and "reply_markup" in payload:
            status, _ = self._call(
                "sendMessage",
                {key: value for key, value in payload.items() if key != "reply_markup"},
            )
        return status == 200

    def _acknowledge(self, callback_id: str) -> None:
        try:
            self._call("answerCallbackQuery", {"callback_query_id": callback_id})
        except Exception:  # noqa: BLE001 - an unacknowledged tap only spins longer
            pass

    async def run(self, stop: asyncio.Event, *, interval_s: float = 1.0) -> Failure | None:
        """Poll until asked to stop. A failure that will not fix itself (a
        conflict, a revoked token, a credential the host cannot produce) ends
        the loop and is returned; a retryable one is waited out with a
        doubling delay, so a dead endpoint is not hammered once a second."""
        delay = interval_s
        while not stop.is_set():
            result = await self.poll_once()
            if result.failure is not None and not result.failure.retryable:
                return result.failure
            if result.failure is None:
                delay = interval_s
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
            if result.failure is not None:
                delay = min(delay * 2, MAX_BACKOFF_SECONDS)
        return None
