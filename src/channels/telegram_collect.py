"""Collection bots: further Telegram bots of a Host, one per feature target.

Owner consent 2026-11-20 (one bot per BI domain, docs/DECISIONS.md): besides the
conversation bot (`channels.telegram`, unchanged), a Host may configure bots in
`TelegramIngressConfig.collection_bots`. Each is polled on its own with its own
durable cursor (`telegram-collect.<name>`). What a mapped sender sends it — links,
files, words, a Reply — goes straight to the configured feature's
`telegram_item` hook and its answer is sent back; nothing reaches a model, a
Workflow or the command router. An unmapped sender is ignored, as by the
conversation bot. `send` is the proactive message to one of the bot's own mapped
senders (review reminders, results); there is no other chat it can reach. The
token is a `SecretRef` resolved per call and never held.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import partial
from typing import Any

from pydantic import JsonValue

from channels.telegram import (
    _FILE_PATH,
    MAX_BACKOFF_SECONDS,
    POLL_MARGIN_SECONDS,
    SEEN_UPDATES,
    TELEGRAM_DOWNLOAD_BYTES,
    TelegramCollectionBot,
    UnmappedSender,
    _parse,
    _Update,
    chunks,
    scrub,
)
from common.assets import SECRET_PATTERN
from common.execution import Failure
from host_runtime import features
from models.credentials import CredentialMisconfigured, CredentialResolver
from models.wire import (
    Transport,
    UrllibTransport,
    close_quietly,
    describe,
    status_failure,
    transport_failure,
)

_LOG = logging.getLogger(__name__)
_URL = re.compile(r"https?://[^\s<>\"'「」（）]+", re.IGNORECASE)
CHANNEL_PREFIX = "telegram-collect."
#: Said when a collection bot has nowhere to put what it got.
NOT_CONNECTED = "這個 bot 目前沒有接上收集功能。"
UNSUPPORTED = "這個 bot 只收連結、文字或檔案。"
#: A file larger than this is refused before it is downloaded.
MAX_FILE_BYTES = TELEGRAM_DOWNLOAD_BYTES


class DownloadError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def urls_in(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(u.rstrip(".,;:!，。；：！") for u in _URL.findall(text)))


class TelegramCollector:
    """One collection bot. `poll_once` is the unit a test drives; `run` loops it."""

    def __init__(
        self,
        bot: TelegramCollectionBot,
        state: Any,
        resolver: CredentialResolver,
        *,
        api_base: str = "https://api.telegram.org",
        poll_timeout_seconds: int = 25,
        transport: Transport | None = None,
    ) -> None:
        self.bot = TelegramCollectionBot.model_validate(bot)
        self.state = state
        self._resolver = resolver
        self.api_base = api_base.rstrip("/")
        self.poll_timeout_seconds = poll_timeout_seconds
        self._transport = transport if transport is not None else UrllibTransport()
        self.unmapped: dict[int, UnmappedSender] = {}
        self.problem: Failure | None = None
        self._seen: dict[int, None] = {}
        # Where items go: the Host's features and its resident host object.
        self.feature_items: features.FeatureSet | None = None
        self.host: Any = None

    @property
    def name(self) -> str:
        return self.bot.name

    @property
    def channel(self) -> str:
        return CHANNEL_PREFIX + self.bot.name

    def info(self) -> features.TelegramBot:
        return features.TelegramBot(self.bot.name, self.bot.feature, self.bot.target)

    # -- the wire --------------------------------------------------------------------------------

    def _call(self, method: str, payload: Mapping[str, JsonValue]) -> tuple[int, bytes]:
        token = self._resolver.resolve(self.bot.credential)
        url = f"{self.api_base}/bot{token}/{method}"
        del token
        reply = self._transport.send(
            url,
            json.dumps(dict(payload)).encode("utf-8"),
            {"Content-Type": "application/json"},
            float(self.poll_timeout_seconds + POLL_MARGIN_SECONDS),
        )
        try:
            body = b"".join(reply.chunks())
        finally:
            close_quietly(reply)
        return reply.status, body

    def _say(self, chat_id: int, text: str) -> bool:
        """Plain text in pieces Telegram accepts; False when a piece was refused."""
        try:
            for piece in chunks(scrub(text)):
                if not piece.strip():
                    continue
                status, body = self._call("sendMessage", {"chat_id": chat_id, "text": piece})
                if status != 200:
                    _LOG.warning("Telegram collection bot %s: sendMessage %s", self.name, status)
                    return False
        except Exception as error:  # noqa: BLE001 - reported as not sent
            _LOG.warning("Telegram collection bot %s: %s", self.name, describe(error))
            return False
        return True

    def send(self, actor: str, text: str) -> bool:
        """A proactive message to `actor`, only when it is one of this bot's mapped
        senders (its private chat with the bot); False otherwise."""
        sender = next((s.sender_id for s in self.bot.senders if s.actor == actor), None)
        if sender is None or not text.strip():
            return False
        return self._say(sender, text)

    def _download(self, file_id: str) -> bytes:
        """`getFile`, then the file; a failure is a code only (no URL, no token)."""
        try:
            status, body = self._call("getFile", {"file_id": file_id})
            result = json.loads(body).get("result") if status == 200 else None
            path = result.get("file_path") if isinstance(result, dict) else None
            if not isinstance(path, str) or not _FILE_PATH.match(path) or ".." in path:
                raise DownloadError("attachment_download_failed")
            size = result.get("file_size") if isinstance(result, dict) else None
            if isinstance(size, int) and size > MAX_FILE_BYTES:
                raise DownloadError("attachment_too_large")
            token = self._resolver.resolve(self.bot.credential)
            url = f"{self.api_base}/file/bot{token}/{path}"
            del token
            timeout_s = float(self.poll_timeout_seconds + POLL_MARGIN_SECONDS)
            method = getattr(self._transport, "request", None)
            reply = (
                method("GET", url, None, {}, timeout_s)
                if callable(method)
                else self._transport.send(url, b"", {}, timeout_s)
            )
            del url
            try:
                if reply.status != 200:
                    raise DownloadError("attachment_download_failed")
                data = bytearray()
                for chunk in reply.chunks():
                    data.extend(chunk)
                    if len(data) > MAX_FILE_BYTES:
                        raise DownloadError("attachment_too_large")
            finally:
                close_quietly(reply)
            return bytes(data)
        except DownloadError:
            raise
        except Exception:  # noqa: BLE001 - the error text could name the URL
            raise DownloadError("attachment_download_failed") from None

    # -- polling ---------------------------------------------------------------------------------

    async def poll_once(self) -> list[tuple[int, str]]:
        """Handle what arrived; `(update_id, disposition)` per update handled.
        Dispositions: `answered`, `unmapped_sender`, `ignored`, `failed`."""
        payload: dict[str, JsonValue] = {
            "timeout": self.poll_timeout_seconds,
            "allowed_updates": ["message"],
        }
        try:
            offset = await asyncio.to_thread(self.state.cursor, self.channel)
        except Exception as error:  # noqa: BLE001 - retried by `run`
            self.problem = Failure(
                code="telegram_cursor_unavailable", message=describe(error), retryable=True
            )
            return []
        if offset is not None:
            payload["offset"] = offset
        try:
            status, body = await asyncio.to_thread(self._call, "getUpdates", payload)
        except CredentialMisconfigured as error:
            self.problem = Failure(code="telegram_credential_unavailable", message=describe(error))
            return []
        except Exception as error:  # noqa: BLE001 - a typed failure
            self.problem = transport_failure(error, prefix="telegram")
            return []
        if status == 409:
            self.problem = Failure(
                code="telegram_conflict", message="another process polls this bot", retryable=True
            )
            return []
        if status != 200:
            self.problem = status_failure(status, body, prefix="telegram")
            return []
        try:
            items = json.loads(body).get("result")
        except (ValueError, AttributeError):
            items = None
        if not isinstance(items, list):
            self.problem = Failure(
                code="telegram_bad_reply", message="the Bot API reply was not ok", retryable=True
            )
            return []
        self.problem = None
        highest = offset
        updates: list[_Update] = []
        for raw in items:
            if isinstance(raw, dict) and type(raw.get("update_id")) is int:
                highest = max(highest or 0, raw["update_id"] + 1)
            update = _parse(raw)
            if update is None or update.update_id in self._seen:
                continue
            self._seen[update.update_id] = None
            while len(self._seen) > SEEN_UPDATES:
                del self._seen[next(iter(self._seen))]
            album = next((item for item in updates if item.joins(update)), None)
            if album is not None:
                album.absorb(update)
                continue
            updates.append(update)
        handled = []
        for update in updates:
            handled.append((update.update_id, await self._handle(update)))
        if highest is not None and highest != offset:
            try:
                await asyncio.to_thread(self.state.advance_cursor, self.channel, highest)
            except Exception as error:  # noqa: BLE001 - `_seen` keeps this process from repeating
                self.problem = Failure(
                    code="telegram_cursor_unconfirmed", message=describe(error), retryable=True
                )
        return handled

    def _item(self, actor: str, update: _Update) -> features.TelegramItem | None:
        text = (update.text or "").strip()
        urls = urls_in(text)
        kind: features.TelegramItemKind
        if update.files:
            kind = "file"
        elif urls:
            kind = "link"
        elif text and update.quoted is not None:
            kind = "reply"
        elif text:
            kind = "text"
        else:
            return None
        files = tuple(
            features.TelegramFile(f.filename, f.size, partial(self._download, f.file_id))
            for f in update.files
        )
        return features.TelegramItem(
            feature=self.bot.feature,
            bot=self.bot.name,
            target=self.bot.target,
            kind=kind,
            actor=actor,
            text=text,
            received_at=datetime.now(UTC),
            sender_name=update.sender_name,
            urls=urls,
            files=files,
            quoted=update.quoted if kind == "reply" else None,
        )

    async def _handle(self, update: _Update) -> str:
        actor = self.bot.actor_for(update.sender_id)
        if actor is None:
            # Not answered, as by the conversation bot; listed for the owner.
            self.unmapped[update.sender_id] = UnmappedSender(
                update.sender_id, update.sender_name, datetime.now(UTC)
            )
            return "unmapped_sender"
        if update.callback_id is not None:
            return "ignored"
        if SECRET_PATTERN.search(update.text or ""):
            await asyncio.to_thread(
                self._say, update.chat_id, "這則訊息看起來含有密碼或金鑰，沒有收下。"
            )
            return "ignored"
        item = self._item(actor, update)
        if item is None:
            await asyncio.to_thread(self._say, update.chat_id, UNSUPPORTED)
            return "ignored"
        try:
            hooks = self.feature_items
            answer = (
                None
                if hooks is None
                else await asyncio.to_thread(hooks.telegram_item, item, self.host)
            )
        except Exception as error:  # noqa: BLE001 - one message never stops the bot
            _LOG.warning("Telegram collection bot %s: %s", self.name, type(error).__name__)
            await asyncio.to_thread(self._say, update.chat_id, "沒有收下：處理時發生錯誤。")
            return "failed"
        text = NOT_CONNECTED if answer is None else answer.text
        await asyncio.to_thread(self._say, update.chat_id, text)
        return "answered"

    async def run(self, stop: asyncio.Event, *, interval_s: float = 1.0) -> Failure | None:
        """Poll until asked to stop; a failure that will not fix itself ends the loop."""
        delay = interval_s
        while not stop.is_set():
            await self.poll_once()
            failure = self.problem
            if failure is not None and not failure.retryable:
                return failure
            delay = interval_s if failure is None else min(delay * 2, MAX_BACKOFF_SECONDS)
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
        return None


class TelegramBots:
    """The Host's collection bots as one `features.Messenger`."""

    def __init__(self, collectors: list[TelegramCollector]) -> None:
        self.collectors = {c.name: c for c in collectors}

    def bots(self) -> tuple[features.TelegramBot, ...]:
        return tuple(c.info() for c in self.collectors.values())

    def send(self, bot: str, actor: str, text: str) -> bool:
        found = self.collectors.get(bot)
        return found is not None and found.send(actor, text)


def build(config: Any, state: Any, resolver: CredentialResolver) -> list[TelegramCollector]:
    """The collection bots of a `TelegramIngressConfig` that are switched on."""
    return [
        TelegramCollector(
            bot,
            state,
            resolver,
            api_base=config.api_base,
            poll_timeout_seconds=config.poll_timeout_seconds,
        )
        for bot in config.collection_bots
        if bot.enabled
    ]


def attach(
    collectors: list[TelegramCollector], feature_set: features.FeatureSet, host: Any
) -> None:
    """Let `feature_set` take what the collection bots receive, and give the features
    the bots as a `Messenger` (reminders, results)."""
    for collector in collectors:
        collector.feature_items = feature_set
        collector.host = host
    feature_set.telegram_ready(TelegramBots(collectors), host)
