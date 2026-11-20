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
Voice and audio messages are spoken requests when the host has a
`VoiceService` (docs/phases/VOICE_INPUT.md): transcribed on this PC, shown to
the person, then handled as the same typed text would be; without one they get
the text-only reply as before.

The adapter adds no authority. It maps a sender to exactly one platform actor
and hands the Agent a `LocalAgentRequest`; the Agent admits or refuses by the
same membership rule as every other ingress, and the Gateway routes the same
way. Nothing here imports the Bot API library: the wire is the standard
library behind the same `Transport` the model adapters use, with the same
failure rules.
"""

import asyncio
import hashlib
import json
import logging
import re
import secrets
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, JsonValue, StrictBool, field_validator, model_validator

from agent.gateway import TOOL_PROGRESS, ToolProgressState
from agent.routing import DOT_COMMAND
from agent.turn_progress import TURN_PROGRESS, TurnProgress, compact_lines
from capabilities.business_cards.chart import NOTE as CHART_NOTE
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
from common.execution import Failure, RequestContext, TraceIdentifiers
from common.local_agent import LocalAgentRequest, LocalWorkflowRequest
from common.workflow_run_form import form_offer, offer_in, person_prefill, run_intent
from host_runtime import features
from host_runtime.agent import LocalAgent, LocalAgentOutcome
from host_runtime.answers import run_cards, run_follow_up
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
from host_runtime.business_cards_tools import chart_files, with_legend
from host_runtime.chat_authoring import ChatAuthoring, ChatAuthoringError, approval_text
from host_runtime.delegation_record import records_from as delegation_records
from host_runtime.delegation_record import text_lines as delegation_text
from host_runtime.identity_presets import IdentityPresets
from host_runtime.memory_why import NOTHING as WHY_NOTHING
from host_runtime.memory_why import memory_used_in
from host_runtime.schedule_policy import target_side_effect
from host_runtime.session_artifacts import FinishedRun, FinishedTurn, SessionArtifacts
from host_runtime.telegram_history import StoredTurn, TelegramHistory
from host_runtime.turn_summary import stop_reply, tool_summary
from host_runtime.workflow_uploads import (
    MAX_UPLOAD_BYTES,
    WorkflowUploadError,
    WorkflowUploadStore,
    accepts,
)
from models.contracts import ModelMessage
from models.credentials import CredentialMisconfigured, CredentialResolver
from models.selection import session_model
from models.wire import (
    Transport,
    UrllibTransport,
    close_quietly,
    describe,
    status_failure,
    transport_failure,
)
from voice.contracts import (
    REPLIES,
    ErrorCode,
    TelegramVoice,
    bare_word,
    declared_limit_error,
)
from voice.service import VoiceService
from voice.transcript import TranscriptUse

# The channel this ingress consumes, as the durable cursor names it.
TELEGRAM_CHANNEL = "telegram"
# Telegram refuses a message over 4096 characters, counted in UTF-16 code
# units (an emoji counts as two); pieces are cut at 4000 units, as the source
# cut at 4000 characters.
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
#: Longest wait honored after a rate-limited status edit or final edit.
MAX_RETRY_WAIT_S = 5.0
#: Longest wait honored after a rate-limited answer, and how many times it is
#: tried. A long run's status edits can earn a `retry_after` well over 5 s; an
#: answer is worth waiting for (owner report 2026-10-25).
MAX_REPLY_RETRY_WAIT_S = 60.0
REPLY_ATTEMPTS = 4
#: Pause before the one retry of an answer whose call raised (a timeout or a
#: reset connection on the way to Telegram).
TRANSPORT_RETRY_WAIT_S = 1.0
#: Telegram's answer to an edit that would leave the message as it is: the
#: message already shows the answer, so nothing is resent.
NOT_MODIFIED = "message is not modified"
#: Sent when the answer had no text at all (owner 2026-10-25): never the
#: undelivered notice, which means Telegram refused a real answer.
DONE_NOTICE = "已完成"
DONE_WITHOUT_TEXT = "（沒有文字結果）"
#: Sent when an answer could not be delivered, so the person is not left
#: with only the "Done" status line (owner 2026-10-15).
UNDELIVERED_REPLY = (
    "The answer could not be delivered here (Telegram refused the message). "
    "Ask again, or open Agent Web."
)
#: Sent after a refused answer went out as a Markdown file instead.
FILE_REPLY_NOTICE = "回答太長或格式無法顯示，已改用檔案傳送"
#: How much of Telegram's own refusal description a warning keeps.
MAX_REFUSAL_CHARS = 200
SETTINGS_HINT = "Open Agent Web to set them, then send /run again."
HELP = (
    "Talk to the Agent in words, or send a skill command as /<skill> <command> "
    "[arguments]. /run <number or name> asks a Workflow's fields one by one. /status "
    "shows this Bridge's state. /new starts a fresh conversation and forgets its files. "
    "/why lists the preferences and memory the last answer used. "
    "/model lists the models this chat may use; /model <number or name> chooses one. "
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

#: The interactive org chart arrives as a file (owner 2026-10-20); one line
#: says what to do with it.
HTML_CHART_CAPTION = "互動式組織圖：請下載後用瀏覽器開啟（可搜尋、切換樹狀／分組檢視）。"


#: 「存成筆記」 under a 結果摘要: the button's data, and the words typed.
SUMMARY_NOTE_TAP = re.compile(r"^sumnote:(ts-[0-9a-f]{12})$")
SUMMARY_NOTE_WORDS = frozenset({"存成筆記", "存成筆記。", "把結果摘要存成筆記"})
NO_SUMMARY_REPLY = "這個對話還沒有可以存的結果摘要。"


def _note_row(summary_id: str) -> tuple[tuple[str, str], ...]:
    return (("存成筆記", f"sumnote:{summary_id}"),)


#: Pictures Telegram shows as a photo, by suffix, with their media type.
PHOTO_SUFFIXES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
#: Telegram's caption limit is 1024 characters; a file name stays well under it.
MAX_CAPTION_CHARS = 200
_DOCUMENT_TYPES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _document_type(path: Path) -> str:
    """The media type a document is sent with (Markdown, as the legend, by default)."""
    suffix = path.suffix.lower()
    if suffix in _DOCUMENT_TYPES:
        return _DOCUMENT_TYPES[suffix]
    if suffix in (".gif", ".webp", ".bmp"):
        return f"image/{suffix.lstrip('.')}"
    return "text/markdown" if not suffix else "application/octet-stream"


def attachment_reply(code: str) -> str:
    """What the person is told about an attachment refusal, by its code."""
    return _ATTACHMENT_REPLIES.get(code, f"附件無法處理（{code}）。")


#: Turns of a Telegram chat kept as context for the next one (memory only).
MAX_CHAT_HISTORY = 12
#: How much of a Workflow question the history keeps for that turn.
MAX_FLOW_NOTE_CHARS = 300
#: How often a "working on it" message refreshes its elapsed time when
#: nothing else changed.
PROGRESS_REFRESH_SECONDS = 5.0
#: Shortest gap between two status edits in one chat: Telegram allows about
#: one a second; changes inside the gap are coalesced (owner 2026-10-19).
STATUS_EDIT_INTERVAL_SECONDS = 1.0
#: Longest a 429's `retry_after` may hold back the live status edits.
MAX_STATUS_BACKOFF_S = 60.0
#: Telegram shows a chat action ("typing…" under the bot's name) for about 5 s
#: or until the bot's next message, so it is repeated this often while a
#: request is handled (owner 2026-11-20).
CHAT_ACTION_INTERVAL_SECONDS = 4.0
#: Longest one `sendChatAction` may take: a courtesy, never a hold on a turn.
CHAT_ACTION_TIMEOUT_SECONDS = 5.0
#: Longest stopping the indicator waits for a call already on its way, so no
#: action follows the reply; past it the reply goes out regardless.
CHAT_ACTION_STOP_WAIT_SECONDS = 1.0
_STEP_MARKS: dict[ToolProgressState, str] = {
    "running": "running…",
    "succeeded": "done",
    "failed": "failed",
}

Disposition = Literal[
    "unmapped_sender", "unsupported_content", "answered", "refused", "routed", "failed"
]


#: Refused Bot API calls are logged here at warning; with no handler set up,
#: Python writes them to stderr, which the launcher keeps in
#: `workspace\logs\agent-web-*.err.log`.
_LOG = logging.getLogger(__name__)


def scrub(text: str) -> str:
    """The shared redaction without the error helper's truncation: a reply is
    shown to a person and split for length separately."""
    return SECRET_PATTERN.sub(REDACTED, text)


class TelegramSender(Contract):
    """One Telegram user, mapped to exactly one platform actor."""

    sender_id: int = Field(gt=0, strict=True)
    actor: Symbol


class TelegramCollectionBot(Contract):
    """A further bot of this Host that collects for a feature plugin (owner consent
    2026-11-20: one bot per BI domain). What its mapped senders send goes to the
    feature (`feature`, e.g. `bi-knowledge`) with `target` (e.g. a BI domain), never
    to a model. Its token is a `SecretRef` of its own."""

    name: Symbol
    credential: SecretRef
    feature: Symbol
    target: str = Field(default="", max_length=200)
    senders: tuple[TelegramSender, ...] = ()
    # Off keeps the record and does not poll the bot (Settings → Agents,
    # owner consent 2026-11-20).
    enabled: StrictBool = True

    @model_validator(mode="after")
    def one_actor_per_sender(self) -> Self:
        ids = [item.sender_id for item in self.senders]
        actors = [item.actor for item in self.senders]
        if len(ids) != len(set(ids)) or len(actors) != len(set(actors)):
            raise ValueError("a sender maps to one actor and an actor to one sender")
        return self

    def actor_for(self, sender_id: int) -> str | None:
        for item in self.senders:
            if item.sender_id == sender_id:
                return item.actor
        return None


class TelegramAgentBot(Contract):
    """A further bot of this Host bound to one persistent sub-agent (owner consent
    2026-11-20, `host_runtime.persistent_agents`). What its mapped senders send
    goes to that agent's own conversation (its Skills, tools and model policy),
    through the same Agent, approvals and at-most-once rules as the conversation
    bot; the reply goes back through this bot. Its token is a `SecretRef` of its own."""

    name: Symbol
    credential: SecretRef
    agent: Slug
    senders: tuple[TelegramSender, ...] = ()
    enabled: StrictBool = True

    @model_validator(mode="after")
    def one_actor_per_sender(self) -> Self:
        ids = [item.sender_id for item in self.senders]
        actors = [item.actor for item in self.senders]
        if len(ids) != len(set(ids)) or len(actors) != len(set(actors)):
            raise ValueError("a sender maps to one actor and an actor to one sender")
        return self


class TelegramIngressConfig(Contract):
    """Host configuration for one bot serving one Bridge. The token is a
    `SecretRef`; a token pasted anywhere in this record is refused.
    `collection_bots` are further bots for feature plugins, each polled on its
    own (`channels.telegram_collect`); the conversation bot is unaffected."""

    credential: SecretRef
    bridge_id: Symbol
    namespace: Slug
    senders: tuple[TelegramSender, ...] = ()
    poll_timeout_seconds: int = Field(default=25, ge=0, le=50, strict=True)
    api_base: Text = "https://api.telegram.org"
    collection_bots: tuple[TelegramCollectionBot, ...] = ()
    # Bots bound to persistent sub-agents (owner consent 2026-11-20), each polled
    # on its own (`telegram-agent.<name>`); the conversation bot is unaffected.
    agent_bots: tuple[TelegramAgentBot, ...] = ()

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
        bots = [(bot.name, bot.credential.name) for bot in self.collection_bots]
        bots += [(bot.name, bot.credential.name) for bot in self.agent_bots]
        names = [name for name, _ in bots]
        tokens = [self.credential.name, *(token for _, token in bots)]
        if len(names) != len(set(names)) or len(tokens) != len(set(tokens)):
            raise ValueError("each bot has its own name and its own token")
        agents = [bot.agent for bot in self.agent_bots]
        if len(agents) != len(set(agents)):
            raise ValueError("an agent has at most one bot")
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
    # Pictures sent after the reply (an org chart; docs/phases/BUSINESS_CARDS.md):
    # paths of files a tool produced on this Host, never model text.
    photos: tuple[str, ...] = ()
    # Files sent after the pictures (the chart's full Markdown legend).
    documents: tuple[str, ...] = ()
    # Files this session produced, sent last (owner 2026-10-25): a run's
    # pictures at its end, or what `session__attach_file` attached. A picture
    # goes as a photo, anything else as a document; paths the Host recorded,
    # never model text.
    attached: tuple[str, ...] = ()
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
        quoted: str | None = None,
        voice: TelegramVoice | None = None,
    ) -> None:
        self.update_id = update_id
        # A voice note or audio file; its transcript becomes `text`, and
        # `spoken` marks the text as heard rather than typed.
        self.voice = voice
        self.spoken = False
        # What the message replies to (Telegram's Reply), already trimmed and
        # redacted: the conversation sees it with the person's words.
        self.quoted = quoted
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
#: An agent bot (owner consent 2026-11-20) converses only; commands go to the main bot.
AGENT_BOT_COMMANDS = "這個 bot 只和它的 agent 對話；/run 與指令請用主 Agent 的 bot。"
AGENT_BOT_GONE = "這個 bot 綁定的 agent 已不存在；請在 Agent Web 設定 → Agents 重新綁定。"
AGENT_BOT_NO_MODEL = "這個 agent 需要對話模型，這個 Bridge 目前沒有設定。"
#: The durable cursor of an agent bot is `telegram-agent.<bot name>`.
AGENT_CHANNEL_PREFIX = "telegram-agent."
#: Where a card Telegram may not decide is applied (owner 2026-10-15). No
#: address: Agent Web's page key must never travel in a chat.
CARD_WHERE = "Agent Web on this PC, Tasks > Pending changes"
#: How much of a replied-to message a turn carries (owner 2026-10-25), and
#: what stands for one without words.
MAX_QUOTE_CHARS = 1000
QUOTED_ATTACHMENT = "（附件）"
#: A run summary (a Workflow's `preview`) in a Telegram reply.
MAX_RUN_SUMMARY_CHARS = 3_000
#: A button of an earlier question while a flow waits on another (owner
#: 2026-10-25: a stale Yes answered the new Dry run question).
STALE_TAP_REPLY = "這個按鈕屬於較早的問題，沒有採用。"
#: A Reply or a tap on a question whose flow is gone (a restart, a timeout).
RESTARTED_FLOW = "那個流程已經結束，已用你的值重新開始。"
ENDED_FLOW = "那個流程已經結束。要再執行，請再說一次要執行哪個 Workflow。"
#: The data of an approval button (G4): `approve:<id>` or `reject:<id>`.
APPROVAL_TAP = re.compile(r"^(approve|reject):(ap-[A-Za-z0-9-]{1,64})$")
#: The data of any inline button (`run:yes`, `edit:2`, `approve:ap-1`, ...);
#: a voice transcript never acts as one.
_BUTTON_DATA = re.compile(r"^[a-z][a-z_-]*:[^\s:]+$")
#: While a voice message is transcribed, then what was heard (VOICE_INPUT §2.4).
VOICE_LISTENING = "🎤 轉文字中…"
VOICE_HEARD = "🎤 你說：「{text}」"
VOICE_NOT_HEARD = "🎤 語音沒有轉成文字。"


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
            shown = message.get("text") if isinstance(message, dict) else None
            return _Update(
                raw["update_id"],
                chat["id"],
                sender["id"],
                data,
                callback["id"],
                sender_name=_display_name(sender),
                message_id=identifier if type(identifier) is int else None,
                # The question the button belongs to, for a tap on a stale one.
                quoted=scrub(shown.strip())[:MAX_QUOTE_CHARS]
                if isinstance(shown, str) and shown.strip()
                else None,
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
        quoted=_quoted(message),
        voice=TelegramVoice.from_message(message),
    )


def _quoted(message: dict[str, Any]) -> str | None:
    """The message this one replies to: its text, else its caption, else
    「（附件）」; None when it replies to nothing. Trimmed and redacted, the
    person's own earlier messages and the bot's answers alike."""
    replied = message.get("reply_to_message")
    if not isinstance(replied, dict):
        return None
    for key in ("text", "caption"):
        value = replied.get(key)
        if isinstance(value, str) and value.strip():
            text = scrub(value.strip())
            return text if len(text) <= MAX_QUOTE_CHARS else text[:MAX_QUOTE_CHARS] + "…"
    return QUOTED_ATTACHMENT


def _with_quote(text: str, quoted: str | None) -> str:
    """The person's words with what they replied to, as the model reads them."""
    return text if quoted is None else f"（回覆先前的訊息：「{quoted}」）\n{text}"


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


#: Salt for `chat_hash`: new with each process, so the hash names a chat
#: within one run of Agent Web and can never be turned back into its id.
_CHAT_SALT = secrets.token_bytes(16)


def chat_hash(key: tuple[int, int]) -> str:
    """A short name for a (chat, sender) pair that does not reveal either id."""
    digest = hashlib.sha256(_CHAT_SALT + f"{key[0]}:{key[1]}".encode()).hexdigest()
    return digest[:12]


def _chat_session(chat_id: int) -> str:
    """The session a Telegram chat's turns belong to (its model choice too)."""
    return f"telegram-chat-{chat_id}"


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


def utf16_units(text: str) -> int:
    """The length Telegram measures: UTF-16 code units, two per astral
    character such as most emoji."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _fitting(text: str, limit: int) -> int:
    """How many characters from the start of `text` fit in `limit` UTF-16
    units. A cut between Python characters never splits a surrogate pair."""
    units = 0
    for index, char in enumerate(text):
        units += 2 if ord(char) > 0xFFFF else 1
        if units > limit:
            return index
    return len(text)


def chunks(text: str, limit: int = MAX_MESSAGE_CHARS) -> Iterator[str]:
    """Split at a newline when one is near enough, as the source did, into
    pieces of at most `limit` UTF-16 units (Telegram's measure)."""
    remaining = text
    while utf16_units(remaining) > limit:
        end = max(_fitting(remaining, limit), 1)
        cut = remaining.rfind("\n", 0, end)
        if cut <= 0:
            cut = end
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


def _retry_after(body: bytes, cap: float = MAX_RETRY_WAIT_S) -> float:
    """Seconds Telegram asked to wait after a 429, at most `cap`."""
    try:
        seconds = json.loads(body).get("parameters", {}).get("retry_after", 1)
    except (ValueError, AttributeError):
        seconds = 1
    return float(min(max(seconds if isinstance(seconds, int | float) else 1, 0), cap))


def _refusal(body: bytes) -> str:
    """Telegram's own reason for refusing a call (its `description`),
    redacted and short; never the message that was refused."""
    try:
        description = json.loads(body).get("description")
    except (ValueError, AttributeError):
        description = None
    if not isinstance(description, str) or not description.strip():
        return "no description"
    return scrub(description)[:MAX_REFUSAL_CHARS]


def _log_refused(method: str, status: int, body: bytes, detail: str = "") -> None:
    """One warning per refused Bot API call: the method, the HTTP status,
    Telegram's description and `detail` (sizes and positions only). The text,
    the chat's content and the token never reach the log."""
    _LOG.warning(
        "Telegram %s refused: HTTP %s (%s)%s",
        method,
        status,
        _refusal(body),
        f"; {detail}" if detail else "",
    )


def _done_notice(name: str | None, attachments: bool) -> str:
    """What is sent in place of an answer with no text: 「<workflow> 已完成」
    above its files, or a short completion notice when nothing came back."""
    done = f"{name} {DONE_NOTICE}" if name else DONE_NOTICE
    return done if attachments else f"{done}{DONE_WITHOUT_TEXT}"


def _blank_notice(delivery: "TelegramDelivery") -> str:
    """The completion notice for `delivery` if its text has nothing to show,
    naming the Workflow that ran, when one did."""
    run = delivery.outcome.workflow if delivery.outcome is not None else None
    name = run.run.workflow.name if run is not None else None
    return _done_notice(name, bool(delivery.photos or delivery.documents or delivery.attached))


def _keyboard(buttons: tuple[tuple[tuple[str, str], ...], ...]) -> dict[str, JsonValue]:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row] for row in buttons
        ]
    }


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


def _flow_note(manifest: WorkflowManifest, reply: str | None) -> str:
    """The history's note for a run request answered by a Workflow's own
    questions (or why it cannot run yet) instead of the model."""
    identity = manifest.metadata.identity
    shown = (reply or "").strip()[:MAX_FLOW_NOTE_CHARS]
    return f"（交給 Workflow {identity.namespace}/{identity.name} 的執行問題）\n{shown}".rstrip()


def _unfinished(code: str) -> str:
    """The history's note for a turn that did not complete."""
    return f"（上一輪沒有完成：{code}）"


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


class ChatAction:
    """Telegram's own activity indicator ("typing…" under the bot's name in the
    chat header, `sendChatAction`) while a request is handled (owner
    2026-11-20). `send` makes one call and never raises; it runs off the event
    loop, first after `delay_s` (0: at once) and then every `interval_s` until
    `stop`. `stop` waits briefly for a call already on its way, so no action
    follows the reply, and the loop ends there: nothing is left running.
    Presentation only: it changes no routing, reply or record."""

    def __init__(
        self, send: Callable[[], None], interval_s: float, *, delay_s: float = 0.0
    ) -> None:
        self._send = send
        self._interval_s = interval_s
        self._delay_s = delay_s
        self._stopping = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> "ChatAction":
        self._task = asyncio.create_task(self._run())
        return self

    async def _run(self) -> None:
        if self._delay_s > 0 and await self._stopped_within(self._delay_s):
            return
        while not self._stopping.is_set():
            try:
                await asyncio.to_thread(self._send)
            except Exception as error:  # noqa: BLE001 - a courtesy never fails a turn
                _LOG.debug("Telegram chat action failed: %s", describe(error))
            if await self._stopped_within(self._interval_s):
                return

    async def _stopped_within(self, seconds: float) -> bool:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)
        except TimeoutError:
            return False
        return True

    async def stop(self) -> None:
        self._stopping.set()
        task, self._task = self._task, None
        if task is None:
            return
        done, _ = await asyncio.wait({task}, timeout=CHAT_ACTION_STOP_WAIT_SECONDS)
        if not done:
            task.cancel()


class _Progress:
    """One "working on it" message per request, edited in place while the
    Agent works: how long it has taken and which skills it used, and for a
    conversation the Harness phase and the tool count and time against their
    limits (owner 2026-10-19). Only names and numbers are shown, never
    arguments or results.

    The message is edited whenever the shown state changes (owner 2026-10-19:
    a new Harness phase, a tool starting or finishing, a retry, a stop), not on
    a timer. Edits are coalesced to at most one per `status_edit_interval_s`
    per chat (Telegram allows about one a second): a change inside the window
    is rendered and sent when the window ends, so the newest state is the one
    shown and none is dropped. Text identical to the last edit is not sent; a
    429 pushes the next edit back by Telegram's `retry_after`. Every Bot API
    call runs off the event loop, one at a time, so edits arrive in order. The
    elapsed-time line also refreshes every `progress_refresh_s`."""

    def __init__(
        self,
        ingress: "TelegramIngress",
        chat_id: int,
        title: str,
        turn: TurnProgress | None = None,
    ) -> None:
        self._ingress = ingress
        self._chat_id = chat_id
        self._title = title
        self._started = time.monotonic()
        self._message_id: int | None = None
        self._steps: dict[str, ToolProgressState] = {}
        self._lock = asyncio.Lock()
        self._pending: set[asyncio.Task[None]] = set()
        self._ticker: asyncio.Task[None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: int | None = None
        # A render already queued (next loop pass, or the end of the rate
        # window); every change before it runs is covered by it.
        self._due: asyncio.Handle | None = None
        self._last_text: str | None = None
        self._closed = False
        self.turn = turn
        if turn is not None:
            turn.listener = self.changed

    def text(self, outcome: bool | None = None) -> str:
        seconds = int(time.monotonic() - self._started)
        if outcome is None:
            head = f"⏳ {self._title}… {seconds} s"
        else:
            head = f"{'✅ Done' if outcome else '⚠️ Stopped'} after {seconds} s"
        lines = [head]
        if outcome is None and self.turn is not None:
            lines.extend(compact_lines(self.turn.snapshot()))
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
        self._loop = asyncio.get_running_loop()
        self._loop_thread = threading.get_ident()
        text = self.text()
        self._message_id = await asyncio.to_thread(self._ingress._send_status, self._chat_id, text)
        if self._message_id is not None:
            self._last_text = text
            self._ticker = asyncio.create_task(self._tick())

    def tool(self, name: str, state: ToolProgressState) -> None:
        """The Gateway's TOOL_PROGRESS listener; called on the event loop."""
        self._steps[name] = state
        self._changed()

    def changed(self) -> None:
        """The turn's state changed (`TurnProgress.listener`). Safe from any
        thread: a Harness inside a tool may run in a worker thread."""
        loop = self._loop
        if loop is None or self._closed:
            return
        if threading.get_ident() == self._loop_thread:
            self._changed()
            return
        try:
            loop.call_soon_threadsafe(self._changed)
        except RuntimeError:  # the loop has closed: the turn is over
            pass

    def _changed(self) -> None:
        if self._closed or self._message_id is None or self._due is not None:
            return
        loop = asyncio.get_running_loop()
        wait = self._ingress._status_wait(self._chat_id)
        # Rendered on the next loop pass at the earliest, so the events of one
        # step (a tool's count and its "running" line) become one edit.
        if wait > 0:
            self._due = loop.call_later(wait, self._render)
        else:
            self._due = loop.call_soon(self._render)

    def _render(self) -> None:
        self._due = None
        if self._closed:
            return
        loop = asyncio.get_running_loop()
        wait = self._ingress._status_wait(self._chat_id)
        if wait > 0:  # a 429 or another status edit in this chat moved the window
            self._due = loop.call_later(wait, self._render)
            return
        text = self.text()
        if text == self._last_text:
            return
        self._last_text = text
        self._ingress._status_sent(self._chat_id)
        task = loop.create_task(self._send(text))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _send(self, text: str) -> None:
        retry = await self._edit(text)
        if retry is not None and not self._closed:
            # Rate-limited: wait as told, then show the newest state.
            self._ingress._status_blocked(self._chat_id, retry)
            if self._last_text == text:
                self._last_text = None
            self._changed()

    async def finish(self, succeeded: bool) -> None:
        self._closed = True
        if self.turn is not None:
            self.turn.listener = None
        if self._ticker is not None:
            self._ticker.cancel()
        if self._due is not None:
            self._due.cancel()
            self._due = None
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)
        text = self.text(succeeded)
        if self._message_id is None or text == self._last_text:
            return
        # The final edit keeps the window too; the wait is short and bounded.
        wait = min(self._ingress._status_wait(self._chat_id), MAX_RETRY_WAIT_S)
        if wait > 0:
            await asyncio.sleep(wait)
        self._ingress._status_sent(self._chat_id)
        retry = await self._edit(text)
        if retry is not None:
            await asyncio.sleep(min(retry, MAX_RETRY_WAIT_S))
            self._ingress._status_sent(self._chat_id)
            await self._edit(text)
        self._last_text = text

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(self._ingress.progress_refresh_s)
            self._changed()

    async def _edit(self, text: str) -> float | None:
        """One edit; the seconds Telegram asked to wait after a 429, else None."""
        if self._message_id is None:
            return None
        async with self._lock:
            return await asyncio.to_thread(
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
        voice: VoiceService | None = None,
    ) -> None:
        self.config = TelegramIngressConfig.model_validate(config)
        if self.config.bridge_id != agent.membership.device.bridge_id:
            raise ValueError("a Telegram ingress serves the Agent's own device")
        self.agent = agent
        self._resolver = resolver
        self._transport = transport if transport is not None else UrllibTransport()
        self.unmapped: dict[int, UnmappedSender] = {}
        #: The last `@username` each allowed sender wrote with, in memory only, so
        #: Settings can turn a typed username into that sender's numeric id.
        #: Never used to route or allow a message: usernames change hands.
        self.sender_usernames: dict[int, str] = {}
        #: The retryable failure the running loop is waiting out (a conflict,
        #: an unreachable Bot API); None once a poll succeeds.
        self.problem: Failure | None = None
        self.progress_refresh_s = PROGRESS_REFRESH_SECONDS
        self.status_edit_interval_s = STATUS_EDIT_INTERVAL_SECONDS
        self.chat_action_interval_s = CHAT_ACTION_INTERVAL_SECONDS
        # When each chat may next have its status message edited (monotonic).
        self._status_slots: dict[int, float] = {}
        self._histories: dict[tuple[int, int], list[ModelMessage]] = {}
        # What the chat's last answer used of the person's memory (M5,
        # /why): the actor, preference ids and memory references, no content.
        self._why: dict[tuple[int, int], tuple[str, tuple[str, ...], tuple[str, ...]]] = {}
        # Conversation run and install requests (G4); set by the host once it exists.
        self.approvals: ChatAuthoring | None = None
        # Within a process, a duplicate inside one response is skipped; across
        # a restart, the durable cursor is what stops a batch being replayed.
        self._seen: dict[int, None] = {}
        # Open Workflow question flows, by (chat, sender); they expire.
        self._flows: dict[tuple[int, int], telegram_flow.FlowState] = {}
        # A flow whose question is being sent this update: the sent message's
        # id becomes the flow's `prompt_message_id`.
        self._prompting: dict[tuple[int, int], telegram_flow.FlowState] = {}
        # The id of the last message sent to each chat (sendMessage's reply).
        self._sent_ids: dict[int, int] = {}
        # Updates being handled now, by (chat, sender), with when each began:
        # read by `activity` from another thread, so under a lock.
        self._busy: dict[tuple[int, int], datetime] = {}
        self._activity_lock = threading.Lock()
        # Where attached files are kept; without it files are refused.
        self.attachments = attachments
        # Workflow `upload` fields (forms v2): documents sent while a flow
        # waits on one are stored here; without it such fields are refused.
        self.uploads = uploads
        # The member's identity answers from last time ("same as last time?").
        self.presets = presets
        # Speech to text on this PC; None: voice is off and a voice message
        # gets the text-only reply (docs/phases/VOICE_INPUT.md).
        self.voice = voice
        # Action cards (change proposals): Agent Web decides them; set by it.
        self.cards: Any = None
        # What each session produced (owner 2026-10-25): runs, files and
        # drafts, kept per chat and actor; set by the host, None keeps nothing.
        self.session_artifacts: SessionArtifacts | None = None
        # The owner's conversations, stored for reading in Agent Web; set by
        # the host, None stores nothing. The model never reads them.
        self.history: TelegramHistory | None = None
        # A plain reason for a failed model turn (e.g. the LLM gateway is not
        # running or still starting); set by the host, None says nothing more.
        self.explain_failure: Callable[[Failure], str | None] | None = None
        # The collection bots configured beside this one (owner consent
        # 2026-11-20), each a `telegram_collect.TelegramCollector` polled on its
        # own; set by the host. This bot's own handling never looks at them.
        self.collectors: list[Any] = []
        # The bots bound to persistent sub-agents (owner consent 2026-11-20), each
        # a `TelegramIngress` of its own with `owner_agent` set; set by the host
        # on the conversation bot and polled beside it.
        self.agent_bots: list[TelegramIngress] = []
        # Set on an agent bot: the sub-agent whose conversations this bot feeds
        # and where its definition is read at each turn (`AgentStore`).
        self.owner_agent: str | None = None
        self.agent_store: Any = None
        # The durable cursor's channel: the conversation bot's own, or
        # `telegram-agent.<name>` for an agent bot.
        self.channel = TELEGRAM_CHANNEL

    def _session(self, chat_id: int) -> str:
        """The session a chat's turns belong to; an agent bot's are its own, so the
        same person's chats with two bots never share a session."""
        if self.owner_agent is None:
            return _chat_session(chat_id)
        return f"telegram-agent-{self.owner_agent}-chat-{chat_id}"

    def _files_session(self, key: tuple[int, int]) -> str:
        if self.owner_agent is None:
            return _files_session(key)
        return f"telegram-agent-{self.owner_agent}-chat-{key[0]}-sender-{key[1]}"

    def _agent_options(self, request: LocalAgentRequest) -> dict[str, Any] | None:
        """`LocalAgent.converse` options of an agent bot's turn: its Skills' tools and
        its purpose (`persistent_agents.converse_options`); {} for the conversation
        bot; None when the bound agent no longer exists."""
        if self.owner_agent is None:
            return {}
        from host_runtime.persistent_agents import converse_options

        found = None if self.agent_store is None else self.agent_store.get(self.owner_agent)
        if found is None:
            return None
        context = RequestContext(
            trace=request.trace,
            actor=request.actor,
            namespace=request.namespace,
            message=request.message,
            channel=request.ingress,
            session_id=request.session_id,
        )
        return converse_options(found, self.agent.gateway.skill_tools(context))

    def offset(self) -> int | None:
        """How far this bot has been consumed, from the Bridge's own durable
        state rather than from memory, so a restart resumes where the last
        confirmed batch ended."""
        return self.agent.state.cursor(self.channel)

    def _call(
        self, method: str, payload: Mapping[str, JsonValue], *, timeout_s: float | None = None
    ) -> tuple[int, bytes]:
        """One Bot API call. The token is resolved here, used in the URL and
        dropped; nothing on this object ever holds it."""
        token = self._resolver.resolve(self.config.credential)
        url = f"{self.config.api_base}/bot{token}/{method}"
        if timeout_s is None:
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
            # Another program polls this bot (owner 2026-10-30: a brief second
            # poller stopped AEP for good). Waited out, so AEP takes over as
            # soon as the other one stops; `problem` says so meanwhile.
            return TelegramPollResult(
                failure=Failure(
                    code="telegram_conflict",
                    message="another process is polling this bot; only one may",
                    retryable=True,
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
            self._prompting.pop((update.chat_id, update.sender_id), None)
            # 「正在輸入…」 under the bot's name while the update is handled
            # (owner 2026-11-20); stopped before the reply, so none follows it.
            # Not for an unmapped sender, who is never answered.
            typing = (
                None
                if self.config.actor_for(update.sender_id) is None
                else self._indicator(update.chat_id, "typing").start()
            )
            try:
                delivery = await self._deliver_guarded(update)
            finally:
                if typing is not None:
                    await typing.stop()
            if update.callback_id is not None:
                await asyncio.to_thread(self._acknowledge, update.callback_id)
            if delivery.reply is not None:
                self._sent_ids.pop(update.chat_id, None)
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
                        partial(self._reply, blank=_blank_notice(delivery)),
                        update.chat_id,
                        delivery.reply,
                        delivery.buttons,
                    )
                # A question sent as a new message (not an edit in place) is
                # the only one whose buttons the flow takes from now on.
                asking = self._prompting.pop((update.chat_id, update.sender_id), None)
                sent_id = self._sent_ids.get(update.chat_id)
                if asking is not None and replied and sent_id is not None:
                    asking.prompt_message_id = sent_id
                if not replied:
                    # Never silent: say that the answer did not arrive. Only
                    # Telegram refusing (or never answering) gets here; an
                    # answer with no text was sent as a completion notice.
                    await asyncio.to_thread(self._reply, update.chat_id, UNDELIVERED_REPLY)
                # 「正在傳送檔案…」 while the files go out; the first is
                # sent before any file, so it never lands after the last one.
                uploading = await self._uploading(update.chat_id, delivery)
                try:
                    for photo in delivery.photos:
                        await asyncio.to_thread(self._send_photo, update.chat_id, Path(photo))
                    for document in delivery.documents:
                        await asyncio.to_thread(
                            partial(self._send_photo, document=True),
                            update.chat_id,
                            Path(document),
                        )
                    for produced in delivery.attached:
                        path = Path(produced)
                        await asyncio.to_thread(
                            partial(
                                self._send_photo,
                                document=path.suffix.lower() not in PHOTO_SUFFIXES,
                                caption=path.name,
                            ),
                            update.chat_id,
                            path,
                        )
                finally:
                    if uploading is not None:
                        await uploading.stop()
                delivery = delivery.model_copy(update={"replied": replied})
            deliveries.append(delivery)
        if highest is None or highest == offset:
            return TelegramPollResult(deliveries=tuple(deliveries), next_offset=offset)
        try:
            await asyncio.to_thread(self.agent.state.advance_cursor, self.channel, highest)
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

    def _indicator(self, chat_id: int, action: str, delay_s: float = 0.0) -> ChatAction:
        interval = self.chat_action_interval_s
        return ChatAction(
            partial(self._send_chat_action, chat_id, action), interval, delay_s=delay_s
        )

    async def _uploading(self, chat_id: int, delivery: TelegramDelivery) -> ChatAction | None:
        """The files' indicator: `upload_photo` when every file is a picture,
        else `upload_document`; None when there are no files."""
        paths = [*delivery.photos, *delivery.documents, *delivery.attached]
        if not paths:
            return None
        pictures = not delivery.documents and all(
            Path(path).suffix.lower() in PHOTO_SUFFIXES for path in paths
        )
        action = "upload_photo" if pictures else "upload_document"
        await asyncio.to_thread(self._send_chat_action, chat_id, action)
        return self._indicator(chat_id, action, self.chat_action_interval_s).start()

    def _send_chat_action(self, chat_id: int, action: str) -> None:
        """One `sendChatAction`. A courtesy: whatever goes wrong is logged at
        debug and ignored, never retried and never in the turn's way."""
        try:
            status, body = self._call(
                "sendChatAction",
                {"chat_id": chat_id, "action": action},
                timeout_s=CHAT_ACTION_TIMEOUT_SECONDS,
            )
        except Exception as error:  # noqa: BLE001 - a courtesy never fails a turn
            _LOG.debug("Telegram sendChatAction failed: %s", describe(error))
            return
        if status != 200:
            _LOG.debug("Telegram sendChatAction refused: %s %s", status, _refusal(body))

    def _remember(self, update_id: int) -> None:
        self._seen[update_id] = None
        while len(self._seen) > SEEN_UPDATES:
            del self._seen[next(iter(self._seen))]

    async def _deliver_guarded(self, update: _Update) -> TelegramDelivery:
        """Handling one update never takes the poll loop down with it. What
        raised is recorded on the delivery with its type and a redacted
        message, and the sender is told the request could not be handled."""
        key = (update.chat_id, update.sender_id)
        with self._activity_lock:
            self._busy[key] = datetime.now(UTC)
        try:
            # Everything this update does uses its chat's model (owner
            # 2026-10-22): the chat's own choice, else the person's default,
            # else the Settings model; the data approval decides first.
            with session_model(self._chat_model(update)):
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
        finally:
            with self._activity_lock:
                self._busy.pop(key, None)

    def activity(self) -> list[dict[str, str]]:
        """What a restart would cut off (owner 2026-10-25: a restart lost the
        owner's question flow at 2/9): open question flows and updates being
        handled now. No message content and no chat id, only a hash of the
        chat that changes with each process."""
        now = time.monotonic()
        with self._activity_lock:
            flows = list(self._flows.items())
            busy = list(self._busy.items())
        found: list[dict[str, str]] = []
        for key, state in flows:
            if state.expired(now):
                continue
            identity = state.workflow
            found.append(
                {
                    "kind": "telegram_flow",
                    "started_at": state.started_at.isoformat(timespec="seconds"),
                    "chat": chat_hash(key),
                    "workflow": f"{identity.namespace}/{identity.name}",
                    "stage": "card" if state.confirming or state.choosing else "question",
                }
            )
        for key, began in busy:
            found.append(
                {
                    "kind": "telegram_turn",
                    "started_at": began.isoformat(timespec="seconds"),
                    "chat": chat_hash(key),
                }
            )
        # The agent bots polled beside this one (owner consent 2026-11-20): a
        # restart or a bot reload waits for their turns and flows too (rule 19).
        for bot in self.agent_bots:
            found += [item | {"agent": str(bot.owner_agent)} for item in bot.activity()]
        return found

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
        if update.sender_name.startswith("@"):
            self.sender_usernames[update.sender_id] = update.sender_name[1:]
        if update.voice is not None and self.voice is not None and not update.files:
            heard = await self._hear(base, actor, update)
            if isinstance(heard, TelegramDelivery):
                return heard
            update.text = heard
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
        if update.spoken:
            spoken = self._spoken(base, key, text)
            if isinstance(spoken, TelegramDelivery):
                return spoken
            text = spoken
        noted = SUMMARY_NOTE_TAP.match(text)
        if noted is not None:
            return await self._summary_note(base, actor, noted.group(1), update.chat_id)
        if text in SUMMARY_NOTE_WORDS and key not in self._flows:
            return await self._summary_note(base, actor, None, update.chat_id)
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
        if parsed is None:
            earlier = await self._earlier_question(base, key, active, text, actor, update)
            if earlier is not None:
                return earlier
        if active is not None and not (
            parsed is not None and parsed[0] in ("run", "start", "help", "status", "why", "model")
        ):
            step = telegram_flow.answer(active, text)
            return await self._flow_step(base, key, active, step, actor, update)
        if self.owner_agent is not None and (
            (parsed is not None and parsed[0] == "run") or DOT_COMMAND.match(text)
        ):
            # An agent bot converses with its agent only (owner consent 2026-11-20).
            return TelegramDelivery(**base, disposition="answered", reply=AGENT_BOT_COMMANDS)
        if parsed is not None and parsed[0] == "run":
            return await self._start_flow(base, key, parsed, actor, update)
        if parsed is not None and parsed[0] in ("start", "help"):
            return TelegramDelivery(**base, disposition="answered", reply=HELP)
        if parsed is not None and parsed[0] == "new":
            self._histories.pop(key, None)
            stored = self._stores(actor)
            if self.history is not None and stored:
                self.history.start_new(*key)
            if self.session_artifacts is not None:
                acting, _ = self._acting(actor)
                await asyncio.to_thread(
                    self.session_artifacts.clear, self._session(update.chat_id), acting
                )
            # The owner's stored records list their files, so those stay until
            # the record is deleted in Agent Web, as an Agent Web chat's do.
            if self.attachments is not None and not stored:
                await asyncio.to_thread(self.attachments.delete_session, self._files_session(key))
            return TelegramDelivery(
                **base, disposition="answered", reply="Started a fresh conversation."
            )
        if parsed is not None and parsed[0] == "why":
            # 「為什麼」 (accumulated memory M5): what the chat's last answer used.
            reply = await asyncio.to_thread(self._why_reply, key)
            return TelegramDelivery(**base, disposition="answered", reply=reply)
        if parsed is not None and parsed[0] == "model":
            # The chat's model, as the Agent Web composer menu (owner 2026-10-22).
            parts = text.split(None, 1)
            wanted = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            reply = await asyncio.to_thread(self._model_reply, actor, update.chat_id, wanted)
            return TelegramDelivery(**base, disposition="answered", reply=reply)
        if parsed is not None and parsed[0] == "status":
            # A durable read under the store's lock, so never on the event loop.
            report = await asyncio.to_thread(self._status)
            return TelegramDelivery(**base, disposition="answered", reply=report)
        request = self._request(update, actor, text)
        if request is None:
            return TelegramDelivery(
                **base, disposition="unsupported_content", reply=CREDENTIAL_REPLY
            )
        if self.owner_agent is not None and parsed is None:
            # Free text to an agent bot is always its agent's conversation.
            if self.agent.gateway.router.model is None:
                return TelegramDelivery(**base, disposition="answered", reply=AGENT_BOT_NO_MODEL)
            return await self._converse(base, key, request, text, actor=actor, update=update)
        if parsed is None and not DOT_COMMAND.match(text):
            # "Run X" for an installed Workflow is its question flow, as
            # /run X is, never the model's prose (owner 2026-10-15).
            intent = run_intent(text, self.agent.gateway.engine.workflows.manifests())
            if intent is not None:
                opened = await self._open_flow(
                    base, key, intent.manifest, actor, update, intent.prefill
                )
                self._remember_turn(key, text, _flow_note(intent.manifest, opened.reply))
                return opened
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
        finished = await self._record_run(request.session_id, request.actor, outcome.workflow)
        described = _describe(outcome)
        if finished.summary is not None:
            described = f"{described}\n\n{finished.summary.block()}"
        return TelegramDelivery(
            **base,
            disposition="routed",
            reply=scrub(described),
            outcome=outcome,
            buttons=(_note_row(finished.summary.summary_id),) if finished.summary else (),
            attached=finished.images,
        )

    async def _hear(
        self, base: dict[str, Any], actor: str, update: _Update
    ) -> "TelegramDelivery | str":
        """A voice message's text (its caption first, when it has one), or
        the refusal the person gets. Limits the sender declared are checked
        before any download; the audio is only ever in memory and every
        outcome leaves a transcript record (owner 2026-11-01)."""
        voice, media = self.voice, update.voice
        assert voice is not None and media is not None
        session = self._session(update.chat_id)

        def refused(code: ErrorCode, reply: str | None = None) -> TelegramDelivery:
            # Nothing reached the Agent: answered, as an attachment refusal is.
            return TelegramDelivery(**base, disposition="answered", reply=reply or REPLIES[code])

        async def failed(code: ErrorCode) -> None:
            await asyncio.to_thread(
                partial(
                    voice.fail,
                    code,
                    channel="telegram",
                    actor=actor,
                    session_id=session,
                    mime_type=media.mime_type,
                    size=media.file_size,
                    declared_seconds=media.duration_seconds,
                )
            )

        declared = declared_limit_error(
            media.duration_seconds, media.file_size, media.mime_type, voice.config
        )
        if declared is not None:
            await failed(declared)
            return refused(declared)
        status_id = await asyncio.to_thread(self._send_status, update.chat_id, VOICE_LISTENING)

        async def show(text: str) -> None:
            if status_id is not None:
                await asyncio.to_thread(self._edit_status, update.chat_id, status_id, text)
            else:
                await asyncio.to_thread(self._send_status, update.chat_id, text)

        try:
            data = await asyncio.to_thread(self._download, media.file_id)
        except AttachmentError as error:
            code: ErrorCode = (
                "audio_too_large" if error.code == "attachment_too_large" else "download_failed"
            )
            await failed(code)
            await show(VOICE_NOT_HEARD)
            return refused(
                code, None if code == "audio_too_large" else attachment_reply(error.code)
            )
        record = await voice.transcribe_async(
            data,
            media.mime_type,
            channel="telegram",
            actor=actor,
            session_id=session,
            declared_seconds=media.duration_seconds,
        )
        del data
        if record.error_code == "transcript_credential":
            # Exactly as the typed text would be refused; nothing is echoed.
            await show(VOICE_NOT_HEARD)
            return TelegramDelivery(
                **base, disposition="unsupported_content", reply=CREDENTIAL_REPLY
            )
        if record.status != "ok" or record.text is None:
            await show(VOICE_NOT_HEARD)
            return refused(record.error_code or "stt_failed")
        await show(VOICE_HEARD.format(text=record.text))
        caption = (update.text or "").strip()
        text = f"{caption}\n\n{record.text}" if caption else record.text
        use = TranscriptUse(
            turn=f"telegram-update-{update.update_id}",
            edited=False,
            sent_text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
        await asyncio.to_thread(voice.store.mark_used, actor, session, record.id, use)
        update.spoken = True
        return text

    def _spoken(
        self, base: dict[str, Any], key: tuple[int, int], text: str
    ) -> "TelegramDelivery | str":
        """Heard text is handled as typed text, except that it never presses a
        button and never confirms a card (VOICE_INPUT §2.4, owner decision
        d2): spoken 「好」 at a card is refused and the card stays open, while
        spoken 「取消」 or 「修改」 work as typed. Punctuation the speech engine
        adds around a card word is dropped so the word is recognised."""
        bare = bare_word(text)
        waiting = self._flows.get(key)
        if waiting is not None and waiting.expired():
            waiting = None
        if _BUTTON_DATA.match(text) or (
            waiting is not None and telegram_flow.would_run(waiting, bare)
        ):
            return TelegramDelivery(
                **base, disposition="answered", reply=REPLIES["voice_not_confirmation"]
            )
        if waiting is not None and telegram_flow.is_control_word(bare):
            return bare
        return text

    def _remember_why(self, key: tuple[int, int], actor: str, conversation: Any) -> None:
        """What this answer used of the person's memory, for /why, and when
        each preference was last carried (the health check's unused ones)."""
        preferences = tuple(str(item) for item in conversation.preferences_used)
        self._why[key] = (actor, preferences, memory_used_in(conversation.tools, conversation.text))
        why = getattr(self.cards, "memory_why", None)
        if why is not None and preferences:
            why.remember(actor, preferences)

    def _chat_model(self, update: _Update) -> str | None:
        """The model id this chat's turn asks for; None keeps the Settings
        model. A sender without an actor, or a host without Agent Web's
        model choices, gets the Settings model."""
        actor = self.config.actor_for(update.sender_id)
        models = getattr(self.cards, "conversation_models", None)
        if actor is None or models is None:
            return None
        chosen = models.for_turn(actor, self._session(update.chat_id))
        return chosen if isinstance(chosen, str) else None

    def _model_reply(self, actor: str, chat_id: int, wanted: str | None) -> str:
        """/model: the models this chat may use, or choose one by number or id."""
        models = getattr(self.cards, "conversation_models", None)
        if models is None:
            return "Choosing a model needs Agent Web on this Bridge."
        session = self._session(chat_id)
        listed = models.listed(actor, session)
        if not listed.get("ok"):
            return "No model is configured. Set one in Agent Web Settings."
        ids = [str(item["id"]) for item in listed["models"]]
        if wanted is not None:
            target = (
                ids[int(wanted) - 1]
                if wanted.isdigit() and 1 <= int(wanted) <= len(ids)
                else wanted
            )
            chosen = models.choose(actor, session, target)
            if not chosen.get("ok"):
                return f"Not changed ({chosen.get('code')}). Send /model to see the list."
            return (
                f"This chat now uses {target}, from the next message. "
                "It is also your default for new conversations."
            )
        source = {"conversation": "this chat", "default": "your default"}.get(
            str(listed.get("selected_from")), "Settings default"
        )
        lines = [f"Model for this chat: {listed['selected']} ({source})."]
        if listed.get("unavailable"):
            lines.append(f"{listed['unavailable']} is not served now; choose another.")
        for number, name in enumerate(ids, start=1):
            marks = " · Settings default" if name == listed.get("configured") else ""
            marks += " ✓" if name == listed["selected"] else ""
            lines.append(f"{number}. {name}{marks}")
        if len(ids) > 1:
            lines.append("Send /model <number or name> to choose.")
        return "\n".join(lines)

    def _why_reply(self, key: tuple[int, int]) -> str:
        found = self._why.get(key)
        why = getattr(self.cards, "memory_why", None)
        if found is None or why is None:
            return WHY_NOTHING
        actor, preferences, used = found
        return str(why.text(actor, preferences, used))

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
                session_id=self._session(update.chat_id),
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
            saved = await asyncio.to_thread(self._save, self._files_session(key), update.files)
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
            base,
            key,
            request,
            text,
            (note, images, listing),
            actor=actor,
            update=update,
            files=tuple(
                {"filename": item.filename, "kind": item.kind, "path": item.path} for item in saved
            ),
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
        self._keep_history(key, history)
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
            self._keep_history(key, history)
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
        files: tuple[dict[str, str], ...] = (),
    ) -> TelegramDelivery:
        """`attached` is the files' note and pictures for the model, and the
        short listing the stored history keeps in their place. A message
        sent as a Reply carries what it replied to (owner 2026-10-25: 「再跑一次」
        answered on an earlier message got "what should I re-run?")."""
        # The stored record keeps the person's own words: a quote may be
        # another sender's, which is never stored.
        said = text
        text = _with_quote(text, update.quoted if update is not None else None)
        history = self._histories.get(key, [])
        if attached is None:
            turn = [*history, ModelMessage(role="user", text=text)]
            sent = turn
        else:
            note, images, listing = attached
            turn = [*history, ModelMessage(role="user", text=f"{text}\n\n{listing}")]
            # The files ride on the newest message only, as in Agent Web.
            sent = [*history, ModelMessage(role="user", text=f"{text}\n\n{note}", images=images)]
        # The turn's live progress (owner 2026-10-19): Harness phase, tool
        # count and time, shown in the one status message.
        options = await asyncio.to_thread(self._agent_options, request)
        if options is None:
            return TelegramDelivery(**base, disposition="answered", reply=AGENT_BOT_GONE)
        turn_state = TurnProgress(turn_id=f"telegram-{update.update_id if update else 0}")
        progress = await self._progress(base["chat_id"], "Working on it", turn_state)
        listening = TOOL_PROGRESS.set(progress.tool)
        tracking = TURN_PROGRESS.set(turn_state)
        answered = False
        started = datetime.now(UTC)
        try:
            result = await self.agent.converse(request, tuple(sent), **options)
            answered = result.conversation is not None and result.conversation.status == "answered"
        finally:
            TURN_PROGRESS.reset(tracking)
            TOOL_PROGRESS.reset(listening)
            await progress.finish(answered)
        if result.refusal is not None:
            # Kept, so 「再跑一次」 knows what was asked (owner 2026-10-25).
            note = _unfinished(result.refusal)
            turn.append(ModelMessage(role="assistant", text=note))
            self._keep_history(key, turn, StoredTurn(said, note, "failed", files=files))
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
            stopped = (
                None
                if conversation is None
                else stop_reply(
                    code,
                    len(conversation.tools),
                    self.agent.gateway.limits().time_limit_seconds // 60,
                    recorded=False,
                )
            )
            if stopped is not None:
                # A guard stopped the turn (tool_loop_limit, tool_repeat_limit,
                # turn_time_limit; owner 2026-10-19).
                reply = stopped
                kept = reply
                # Keep what was done so 繼續 can pick it up.
                turn.append(ModelMessage(role="assistant", text=f"{reply}\n\n[工具紀錄]\n{record}"))
            else:
                # Any other failure keeps the request and a short note, so
                # 「再跑一次」 knows what was asked (owner 2026-10-25).
                note = _unfinished(code)
                kept = note
                turn.append(
                    ModelMessage(
                        role="assistant",
                        text=note if record is None else f"{note}\n\n[工具紀錄]\n{record}",
                    )
                )
            self._keep_history(key, turn, StoredTurn(said, kept, "failed", record, files))
            if drafted:
                return self._carded(base, reply, buttons, drafted)
            return TelegramDelivery(**base, disposition="answered", reply=reply, buttons=buttons)
        # A subscribed BI dataset's source line, when the model left it out.
        answer = (
            features.active().finish_answer(conversation.text, conversation)
            if conversation.text.strip()
            else _no_answer_reply(record)
        )
        await asyncio.to_thread(self._remember_why, key, request.actor, conversation)
        # What this turn produced joins the session's ledger; the pictures of
        # a run the model started and the files it attached go out last.
        finished = await self._record_turn(request, text, conversation)
        produced = tuple(finished.files)
        # The 委派紀錄 (multi-agent V1): a summary line per sub-agent that ran.
        delegated = delegation_text(delegation_records(conversation.tools))
        if delegated:
            answer = "\n\n".join([answer, "\n".join(delegated)])
        # The task result summary (owner 2026-10-25) ends the answer, with
        # 「存成筆記」 under it; nothing is saved until it is pressed.
        if finished.summaries:
            answer = "\n\n".join([answer, *(item.block() for item in finished.summaries)])
            buttons = (*buttons, _note_row(finished.summaries[-1].summary_id))
        remembered = answer if record is None else f"{answer}\n\n[工具紀錄]\n{record}"
        if finished.entries:
            remembered = "\n\n".join([remembered, *finished.entries])
        turn.append(ModelMessage(role="assistant", text=remembered))
        visible = "\n\n".join([answer, *finished.entries])
        self._keep_history(key, turn, StoredTurn(said, visible, tool_summary=record, files=files))
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
            shown = ActionCard.model_validate(card)
            drawn, card_buttons = telegram_card(shown, CARD_WHERE)
            if shown.ends_turn:
                return TelegramDelivery(
                    **base,
                    disposition="answered",
                    reply=scrub(drawn),
                    buttons=(*card_buttons, *buttons),
                    attached=produced,
                )
            # A memory proposal (accumulated memory M3) comes under the answer.
            answer = f"{answer}\n\n{drawn}"
            buttons = (*card_buttons, *buttons)
        if drafted:
            return self._carded(base, answer, buttons, drafted).model_copy(
                update={"attached": produced}
            )
        charts = chart_files(conversation)
        return TelegramDelivery(
            **base,
            disposition="answered",
            reply=scrub(with_legend(answer, charts, short=True)),
            buttons=buttons,
            photos=tuple(item["path"] for item in charts if item["kind"] == "image"),
            documents=tuple(item["path"] for item in charts if item["kind"] != "image"),
            attached=produced,
        )

    async def _record_turn(
        self, request: LocalAgentRequest, text: str, conversation: Any
    ) -> FinishedTurn:
        """Keep what a model turn produced (the Workflows it ran, files a tool
        made, a summary of the task) and return the runs' history entries,
        the files to send (each run's pictures, then what
        `session__attach_file` attached) and the summaries."""
        store = self.session_artifacts
        if store is None or not request.session_id:
            return FinishedTurn()
        try:
            return await asyncio.to_thread(
                store.finish_turn, request.session_id, request.actor, text, conversation
            )
        except (OSError, ValueError) as error:
            _LOG.warning("session artifacts not recorded: %s", type(error).__name__)
            return FinishedTurn()

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

    async def _earlier_question(
        self,
        base: dict[str, Any],
        key: tuple[int, int],
        active: telegram_flow.FlowState | None,
        text: str,
        actor: str,
        update: _Update,
    ) -> TelegramDelivery | None:
        """A Reply on, or a button tapped under, a question other than the one
        the flow waits on (owner 2026-10-25). None: handle the update as usual.

        - a tap on an older message while a flow waits: not taken as an answer;
        - a Reply on another question of the same flow: answers that field;
        - a Reply or tap on a question whose flow is gone (a restart, the time
          limit): the Workflow's flow starts again with that value given.
        """
        tapped = update.callback_id is not None
        if (
            tapped
            and active is not None
            and active.prompt_message_id is not None
            and update.message_id != active.prompt_message_id
        ):
            again = telegram_flow.prompt(active)
            self._prompting[key] = active
            return TelegramDelivery(
                **base,
                disposition="answered",
                reply=scrub(f"{STALE_TAP_REPLY}\n\n{again.text}"),
                buttons=tuple(tuple(row) for row in again.buttons),
            )
        question = telegram_flow.quoted_question(update.quoted) if update.quoted else None
        if question is None:
            if tapped and active is None and not text.startswith("/"):
                # A flow's button whose flow is gone: never an answer elsewhere.
                return TelegramDelivery(**base, disposition="answered", reply=ENDED_FLOW)
            return None
        name, label = question
        if active is not None and active.workflow.name == name:
            field = next((item for item in active.fields if item.label == label), None)
            current = telegram_flow.current_field(active)
            if field is None or (current is not None and current.name == field.name):
                return None
            step = telegram_flow.answer_field(active, field.name, text)
            return await self._flow_step(base, key, active, step, actor, update)
        manifest = self._resolve_workflow(name)
        if isinstance(manifest, str):
            # Not an installed Workflow's question (any more): an ordinary turn.
            return None
        self._flows.pop(key, None)
        prefill: dict[str, Any] = {}
        field = next(
            (
                item
                for item in manifest.parameters
                if item.label == label and item.scope == "runtime"
            ),
            None,
        )
        if field is not None:
            value = telegram_flow.convert_reply(field, text)
            if value is not None:
                prefill[field.name] = value
        opened = await self._open_flow(base, key, manifest, actor, update, prefill)
        self._remember_turn(key, text, _flow_note(manifest, opened.reply))
        if opened.reply is None:
            return opened
        return opened.model_copy(update={"reply": f"{RESTARTED_FLOW}\n\n{opened.reply}"})

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
        opened = await self._open_flow(base, key, manifest, actor, update, {})
        self._remember_turn(key, f"/run {target}", _flow_note(manifest, opened.reply))
        return opened

    def _remember_turn(self, key: tuple[int, int], said: str, answer: str) -> None:
        """A turn the model did not answer (a Workflow's questions, its run),
        kept in the chat's history so a later 「再跑一次」 or 「剛剛那個」 knows
        what was meant (owner report 2026-10-25)."""
        history = [
            *self._histories.get(key, []),
            ModelMessage(role="user", text=said),
            ModelMessage(role="assistant", text=answer),
        ]
        self._keep_history(key, history)

    def _stores(self, actor: str | None) -> bool:
        """Whether this sender's turns are stored: the owner's only."""
        return self.history is not None and actor == self.history.actor

    def _keep_history(
        self,
        key: tuple[int, int],
        turn: list[ModelMessage],
        stored: StoredTurn | None = None,
    ) -> None:
        """Every write of a chat's history. The model's window is exactly
        `turn`; the owner's turn, by default `turn`'s last pair, is also stored
        for reading. Storing it never fails a turn."""
        self._histories[key] = turn[-MAX_CHAT_HISTORY:]
        if self.history is None or not self._stores(self.config.actor_for(key[1])):
            return
        try:
            self.history.add_turn(
                key[0], key[1], stored or StoredTurn(turn[-2].text, turn[-1].text)
            )
        except (LocalStateError, ValueError, OSError) as error:
            _LOG.warning("telegram turn not stored: %s", type(error).__name__)

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
            self._prompting[key] = state
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
        # The history keeps the run's result and what it made, by short id
        # (owner 2026-10-25: 「這個workflow 做完之後他都忘記了」).
        finished = await self._record_run(
            self._session(update.chat_id), acting, outcome.workflow, step.arguments
        )
        self._remember_turn(key, f"【執行】{state.workflow.name}", finished.entry or reply)
        texts, buttons = self._run_extras(outcome)
        if finished.summary is not None:
            # The task result summary (owner 2026-10-25), 「存成筆記」 under it.
            texts.append(finished.summary.block())
            buttons = (*buttons, _note_row(finished.summary.summary_id))
        return TelegramDelivery(
            **base,
            disposition="routed",
            reply=scrub("\n\n".join([reply, *texts])),
            buttons=buttons,
            outcome=outcome,
            attached=finished.images,
        )

    async def _record_run(
        self,
        session_id: str | None,
        actor: str,
        snapshot: Any,
        arguments: Mapping[str, Any] | None = None,
    ) -> FinishedRun:
        """Keep a finished run in this session's ledger: its history entry,
        the pictures it made (sent at the end of the run as the org chart is)
        and its task result summary. Nothing when no ledger is set or the run
        did not start."""
        store = self.session_artifacts
        if store is None or snapshot is None:
            return FinishedRun()
        try:
            return await asyncio.to_thread(store.finish_run, session_id, actor, snapshot, arguments)
        except (OSError, ValueError) as error:
            _LOG.warning("session artifacts not recorded: %s", type(error).__name__)
            return FinishedRun()

    async def _summary_note(
        self, base: dict[str, Any], actor: str, summary_id: str | None, chat_id: int
    ) -> TelegramDelivery:
        """「存成筆記」 under a 結果摘要 (a tap, or the words typed): the summary
        becomes a note through Agent Web's one-click note save (accumulated
        memory M3). Only this press saves anything."""
        acting, _ = self._acting(actor)
        store = self.session_artifacts
        if summary_id is None and store is not None:
            latest = await asyncio.to_thread(
                store.summaries.for_session, self._session(chat_id), acting, 1
            )
            summary_id = latest[-1].summary_id if latest else None
        saver = getattr(self.cards, "task_summary_note", None)
        if summary_id is None:
            return TelegramDelivery(**base, disposition="answered", reply=NO_SUMMARY_REPLY)
        if saver is None:
            return TelegramDelivery(
                **base, disposition="answered", reply="存成筆記需要這台電腦的 Agent Web。"
            )
        saved = await asyncio.to_thread(saver, acting, summary_id, "telegram")
        message = str(saved.get("message") or saved.get("code") or "沒有存。")
        return TelegramDelivery(**base, disposition="answered", reply=scrub(message))

    def _run_extras(
        self, outcome: LocalAgentOutcome
    ) -> tuple[list[str], tuple[tuple[tuple[str, str], ...], ...]]:
        """What a run's last step offers the person (loan replies, owner
        2026-10-20): its summary, its action cards (drawn; answered where the
        card says) and a button that opens the next Workflow's questions. A
        button only starts a question flow; nothing runs or sends by itself."""
        texts: list[str] = []
        rows: list[tuple[tuple[str, str], ...]] = []
        workflow = outcome.workflow
        if workflow is not None and workflow.step_results:
            data = workflow.step_results[-1].data
            shown = data.get("preview") if isinstance(data, dict) else None
            if isinstance(shown, str) and shown.strip():
                texts.append(shown.strip()[:MAX_RUN_SUMMARY_CHARS])
        lookup = getattr(self.cards, "card", None)
        for card_id in run_cards(outcome):
            found = lookup(card_id) if lookup is not None else None
            if isinstance(found, dict):
                drawn, card_buttons = telegram_card(ActionCard.model_validate(found), CARD_WHERE)
                texts.append(drawn)
                rows.extend(card_buttons)
        offered = run_follow_up(outcome)
        if offered is not None:
            target = offered["workflow"]
            assert isinstance(target, dict)
            label = str(offered.get("label") or "Next")[:60]
            rows.append(((label, f"/run {target.get('namespace')}/{target.get('name')}"[:64]),))
        return texts, tuple(rows)

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
        """Replace one message's text and keyboard (a multi-select toggle).
        False sends the reply as a new message instead (any refusal but
        Telegram's "message is not modified")."""
        if utf16_units(text) > MAX_MESSAGE_CHARS:
            return False
        try:
            status, body = self._call(
                "editMessageText",
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "reply_markup": _keyboard(buttons),
                },
            )
        except Exception as error:  # noqa: BLE001 - the caller sends a new message instead
            _LOG.warning("Telegram editMessageText failed: %s", describe(error))
            return False
        if status == 400 and NOT_MODIFIED in _refusal(body):
            # A second tap that changes nothing: the message already shows
            # this text and keyboard, so it counts as delivered.
            return True
        if status != 200:
            _log_refused("editMessageText", status, body, f"{utf16_units(text)} UTF-16 units")
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

    async def _progress(
        self, chat_id: int, title: str, turn: TurnProgress | None = None
    ) -> "_Progress":
        progress = _Progress(self, chat_id, title, turn)
        await progress.open()
        return progress

    def _send_status(self, chat_id: int, text: str) -> int | None:
        """Send one plain message and return its id, or None when it could not
        be sent; progress is a courtesy and never fails the request."""
        text = next(chunks(text))
        try:
            status, body = self._call("sendMessage", {"chat_id": chat_id, "text": text})
            if status != 200:
                _log_refused("sendMessage", status, body, "status message")
                return None
            message = json.loads(body).get("result")
            identifier = message.get("message_id") if isinstance(message, dict) else None
            return identifier if type(identifier) is int else None
        except Exception as error:  # noqa: BLE001 - see above
            _LOG.warning("Telegram sendMessage failed: %s; status message", describe(error))
            return None

    def _edit_status(self, chat_id: int, message_id: int, text: str) -> float | None:
        """Edit a status message; after a 429, the seconds Telegram asked to
        wait (its `retry_after`), else None."""
        text = next(chunks(text))
        try:
            status, body = self._call(
                "editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text}
            )
        except Exception as error:  # noqa: BLE001 - a stale status line is not worth a failure
            _LOG.warning("Telegram editMessageText failed: %s; status message", describe(error))
            return None
        if status != 200:
            _log_refused("editMessageText", status, body, "status message")
        return _retry_after(body, MAX_STATUS_BACKOFF_S) if status == 429 else None

    def _status_wait(self, chat_id: int) -> float:
        """Seconds until this chat's status message may be edited again."""
        return max(0.0, self._status_slots.get(chat_id, 0.0) - time.monotonic())

    def _status_sent(self, chat_id: int) -> None:
        self._status_slots[chat_id] = time.monotonic() + self.status_edit_interval_s

    def _status_blocked(self, chat_id: int, seconds: float) -> None:
        until = time.monotonic() + max(seconds, self.status_edit_interval_s)
        self._status_slots[chat_id] = max(self._status_slots.get(chat_id, 0.0), until)

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
        *,
        blank: str = DONE_NOTICE + DONE_WITHOUT_TEXT,
    ) -> bool:
        """Plain text, in pieces Telegram accepts, with any inline keyboard on
        the last piece; a text with nothing to show sends `blank` (a
        completion notice) instead of failing. When Telegram still refuses a
        piece (400), the whole answer goes as a Markdown file with a short
        notice instead. A reply that cannot be sent is reported on the
        delivery, never raised over the outcome."""
        try:
            pieces = [piece for piece in chunks(text) if piece.strip()] or [blank]
            for position, piece in enumerate(pieces):
                payload: dict[str, JsonValue] = {"chat_id": chat_id, "text": piece}
                if buttons and position == len(pieces) - 1:
                    payload["reply_markup"] = _keyboard(buttons)
                status = self._send_piece(payload, f"piece {position + 1} of {len(pieces)}")
                if status == 400:
                    return self._reply_as_file(chat_id, text, buttons)
                if status != 200:
                    return False
        except Exception as error:  # noqa: BLE001 - the delivery records that the reply failed
            _LOG.warning("Telegram reply failed: %s", describe(error))
            return False
        return True

    def _reply_as_file(
        self,
        chat_id: int,
        text: str,
        buttons: tuple[tuple[tuple[str, str], ...], ...] = (),
    ) -> bool:
        """The whole answer as `answer-<time>.md` through `sendDocument`, then
        the notice (with the keyboard). False only when the file did not go;
        the temporary file is removed either way."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        with tempfile.TemporaryDirectory(
            prefix="aep-telegram-", ignore_cleanup_errors=True
        ) as folder:
            path = Path(folder) / f"answer-{stamp}.md"
            path.write_bytes(text.encode("utf-8"))
            sent = self._send_photo(chat_id, path, document=True)
        if not sent:
            return False
        notice: dict[str, JsonValue] = {"chat_id": chat_id, "text": FILE_REPLY_NOTICE}
        if buttons:
            notice["reply_markup"] = _keyboard(buttons)
        self._send_piece(notice, "file notice")
        return True

    def _send_piece(self, payload: dict[str, JsonValue], where: str = "piece 1 of 1") -> int:
        """One `sendMessage`, so an answer is not lost: retried after a rate
        limit for as long as Telegram asks (up to a minute, a few times; the
        progress edits just before it can trigger one), once after a call
        that raised, and once without its keyboard when Telegram refuses the
        message. Returns the last HTTP status, 0 when no call got an answer;
        every refusal is logged with Telegram's reason, the piece's position
        and its UTF-16 length, never its text."""
        text = payload.get("text")
        detail = f"{where}, {utf16_units(text) if isinstance(text, str) else 0} UTF-16 units"
        status, body = self._send_once(payload, detail)
        for _ in range(REPLY_ATTEMPTS - 1):
            if status != 429:
                break
            _log_refused("sendMessage", status, body, detail)
            time.sleep(_retry_after(body, MAX_REPLY_RETRY_WAIT_S))
            status, body = self._send_once(payload, detail)
        if status == 400 and "reply_markup" in payload:
            _log_refused("sendMessage", status, body, f"{detail}, with keyboard")
            status, body = self._send_once(
                {key: value for key, value in payload.items() if key != "reply_markup"}, detail
            )
        if status not in (0, 200):
            _log_refused("sendMessage", status, body, detail)
        if status == 200:
            self._note_sent(payload.get("chat_id"), body)
        return status

    def _note_sent(self, chat_id: object, body: bytes) -> None:
        """Remember the id Telegram gave the message just sent to `chat_id`."""
        try:
            sent = json.loads(body).get("result")
        except (ValueError, AttributeError):
            return
        identifier = sent.get("message_id") if isinstance(sent, dict) else None
        if type(chat_id) is int and type(identifier) is int:
            self._sent_ids[chat_id] = identifier

    def _send_once(self, payload: dict[str, JsonValue], detail: str) -> tuple[int, bytes]:
        """One `sendMessage`; a call that raises is logged and tried once
        more after a short pause (a timeout or a reset connection), and is
        status 0 when that fails too. A retry after a timeout may show the
        piece twice, which beats losing the answer."""
        for attempt in (1, 2):
            try:
                return self._call("sendMessage", payload)
            except Exception as error:  # noqa: BLE001 - the caller reports it on the delivery
                _LOG.warning(
                    "Telegram sendMessage failed (attempt %s): %s; %s",
                    attempt,
                    describe(error),
                    detail,
                )
                if attempt == 1:
                    time.sleep(TRANSPORT_RETRY_WAIT_S)
        return 0, b""

    def _send_photo(
        self, chat_id: int, path: Path, *, document: bool = False, caption: str | None = None
    ) -> bool:
        """One `sendPhoto` (with the chart's short note as its caption) or
        `sendDocument`, the file as multipart form data, through the bot's own
        transport; a file that cannot be sent is not retried. `caption`
        replaces the chart's note (a session file carries its own name)."""
        try:
            data = path.read_bytes()
            boundary = f"aep-{uuid.uuid4().hex}"
            name = re.sub(r"[^A-Za-z0-9._-]", "_", path.name) or "chart.png"
            page = path.suffix.lower() in (".html", ".htm")
            field, method, media = (
                ("document", "sendDocument", _document_type(path))
                if document
                else ("photo", "sendPhoto", PHOTO_SUFFIXES.get(path.suffix.lower(), "image/png"))
            )
            if caption is None:
                caption = HTML_CHART_CAPTION if page else ("" if document else CHART_NOTE)
            caption = caption[:MAX_CAPTION_CHARS]
            parts = [f"--{boundary}", 'Content-Disposition: form-data; name="chat_id"', ""]
            parts.append(str(chat_id))
            if caption:
                parts += [f"--{boundary}", 'Content-Disposition: form-data; name="caption"', ""]
                parts.append(caption)
            parts += [
                f"--{boundary}",
                f'Content-Disposition: form-data; name="{field}"; filename="{name}"',
                f"Content-Type: {media}",
                "",
                "",
            ]
            head = "\r\n".join(parts)
            body = head.encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode()
            token = self._resolver.resolve(self.config.credential)
            reply = self._transport.send(
                f"{self.config.api_base}/bot{token}/{method}",
                body,
                {"Content-Type": f"multipart/form-data; boundary={boundary}"},
                float(self.config.poll_timeout_seconds + POLL_MARGIN_SECONDS),
            )
            try:
                answer = b"".join(reply.chunks())
            finally:
                close_quietly(reply)
            if reply.status != 200:
                _log_refused(method, reply.status, answer, f"{len(data)} bytes")
            return reply.status == 200
        except Exception as error:  # noqa: BLE001 - the text answer already went out
            _LOG.warning("Telegram file upload failed: %s", describe(error))
            return False

    def _acknowledge(self, callback_id: str) -> None:
        try:
            self._call("answerCallbackQuery", {"callback_query_id": callback_id})
        except Exception:  # noqa: BLE001 - an unacknowledged tap only spins longer
            pass

    async def run(self, stop: asyncio.Event, *, interval_s: float = 1.0) -> Failure | None:
        """Poll until asked to stop. A failure that will not fix itself (a
        revoked token, a credential the host cannot produce) ends the loop and
        is returned; a retryable one (another program polling the bot, a
        dead endpoint) is waited out with a doubling delay and kept in
        `problem`, so it is not hammered once a second and is shown."""
        delay = interval_s
        while not stop.is_set():
            result = await self.poll_once()
            if result.failure is not None and not result.failure.retryable:
                self.problem = None
                return result.failure
            self.problem = result.failure
            if result.failure is None:
                delay = interval_s
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
            if result.failure is not None:
                delay = min(delay * 2, MAX_BACKOFF_SECONDS)
        return None
