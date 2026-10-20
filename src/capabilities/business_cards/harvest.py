"""Incremental signature harvest (docs/phases/ACCUMULATED_MEMORY.md §4, M2).

Each pass reads one company domain's mail in the person's mail scope, but
only what the sync state of `(contacts/org, "mail:<folder>", <domain>)` says
is new: messages newer than `last_message_date`, minus a small overlap
window, without the ids already processed near that boundary. Nothing here
stores anything or reaches the model: `scan` decides which messages to open
and cuts their signature blocks; the handler reads the blocks, keeps the
candidates and moves the state forward (`target`) only after a successful
pass.

- First pass (no state): the full configured scope.
- The configured scope always caps the window: it can only shrink.
- A message already observed in the space (an observation with that
  `source_ref`) is skipped and counted, unless the extractor changed: then
  it is read again and proposed only when the new reading changes something.
- An extractor change (`signatures.EXTRACTOR_VERSION`) or a manual
  「重新整理」 reads the full scope again.
- A message that could not be read, or that a pass left for later (the
  people limit), holds the state back to just before it, so nothing is
  silently lost.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Literal
from zoneinfo import ZoneInfo

from capabilities.business_cards import signatures
from common.memory import SyncState
from integrations.outlook_mail import (
    MAX_RESULTS,
    MailError,
    MailReader,
    MailScope,
    read,
    search,
)

#: How far before the last processed message each incremental pass re-reads:
#: a message that reaches the folder late (a rule, an offline sync) but is
#: dated earlier is still read; the ids processed last time are skipped.
OVERLAP = timedelta(days=1)
LOCAL_ZONE = ZoneInfo("Asia/Taipei")
#: Folder names as the person sees them in a reply.
_FOLDER_LABELS = {"inbox": "收件匣", "sent items": "寄件備份", "sent": "寄件備份"}

Mode = Literal["first", "incremental", "reset", "extractor"]


def source_name(folder: str, scope: MailScope) -> str:
    """The sync source of a harvest: `mail:Inbox`, or every scope folder
    (`mail:Inbox+Sent Items`) when no folder is named. Another set of folders
    is another source, read in full the first time."""
    folders = [folder] if folder else list(scope.folders)
    return "mail:" + "+".join(item.strip() for item in folders)


def folder_label(folder: str, scope: MailScope) -> str:
    folders = [folder] if folder else list(scope.folders)
    return "、".join(_FOLDER_LABELS.get(item.strip().casefold(), item.strip()) for item in folders)


def local_day(value: str | datetime) -> str:
    """`10/19`: a moment as the person's calendar day."""
    moment = datetime.fromisoformat(value) if isinstance(value, str) else value
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    local = moment.astimezone(LOCAL_ZONE)
    return f"{local.month}/{local.day}"


@dataclass(frozen=True)
class Window:
    """Which part of the scope one pass reads."""

    mode: Mode
    since: datetime
    days: int
    full_days: int
    #: The incremental window would start before the scope allows.
    capped: bool = False
    last: str = ""
    seen_ids: frozenset[str] = frozenset()
    #: Why the state is reset before it moves on (manual, extractor change).
    reset_reason: str = ""


def plan(
    state: SyncState | None,
    *,
    full: bool,
    now: datetime,
    full_days: int,
    extractor_version: str,
) -> Window:
    """The window of one pass: the full scope the first time, after a manual
    「重新整理」 (`full`) or an extractor change; otherwise from the last
    processed message minus `OVERLAP`, never before the scope's start."""
    start = now - timedelta(days=full_days)
    if full:
        return Window("reset", start, full_days, full_days, reset_reason="manual full re-harvest")
    if state is None:
        return Window("first", start, full_days, full_days)
    if state.extractor_version != extractor_version:
        reason = (
            f"extractor version changed from {state.extractor_version or '-'} "
            f"to {extractor_version}"
        )
        return Window("extractor", start, full_days, full_days, reset_reason=reason)
    last = datetime.fromisoformat(state.last_message_date)
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    since = last - OVERLAP
    capped = since < start
    since = max(since, start)
    days = max(1, min(full_days, ceil((now - since).total_seconds() / 86400)))
    return Window(
        "incremental",
        since,
        days,
        full_days,
        capped=capped,
        last=state.last_message_date,
        seen_ids=frozenset(state.last_message_ids),
    )


@dataclass
class DomainPass:
    """What one pass over one domain found, before the model reads blocks."""

    domain: str
    window: Window
    scanned: int = 0
    from_domain: int = 0
    blocks: list[signatures.Block] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)
    opened: int = 0
    without: int = 0
    same_sender: int = 0
    #: Already observed in the space, or processed by the previous pass.
    already: int = 0
    #: Left for a later pass: more people than the request's limit.
    over_limit: int = 0
    #: The search reached its cap: older messages in the window were not seen.
    truncated: bool = False
    #: Observed messages read again after an extractor change.
    reread: set[str] = field(default_factory=set)
    processed: list[tuple[str, datetime]] = field(default_factory=list)
    unprocessed: list[datetime] = field(default_factory=list)
    # Filled once the model has read the blocks.
    with_signature: int = 0
    unreadable_signature: int = 0


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def scan(
    reader: MailReader,
    scope: MailScope,
    domain: str,
    *,
    folder: str,
    window: Window,
    now: datetime,
    limit: int,
    observed: Callable[[Sequence[str]], set[str]],
) -> DomainPass:
    """Open the messages of `domain` in the window, newest first; at most
    one per sender (its newest), at most `limit` people. Raises `MailError`
    when the mailbox cannot be listed; one unreadable message is skipped and
    counted, and holds the state back."""
    found = search(
        reader,
        scope,
        sender="@" + domain,
        folder=folder,
        days=window.days,
        limit=MAX_RESULTS,
        now=now,
    )
    in_window = [item for item in found if _aware(item.received) >= window.since]
    done = DomainPass(domain, window)
    done.truncated = len(found) >= MAX_RESULTS and len(in_window) == len(found)
    done.scanned = len(in_window)
    mine = [item for item in in_window if signatures.from_domain(item.sender, domain)]
    done.from_domain = len(mine)
    seen_in_space = observed([item.message_id for item in mine])
    newest: dict[str, signatures.Block] = {}
    for item in mine:
        received = _aware(item.received)
        if item.message_id in window.seen_ids:
            done.already += 1
            done.processed.append((item.message_id, received))
            continue
        if item.message_id in seen_in_space and window.mode != "extractor":
            done.already += 1
            done.processed.append((item.message_id, received))
            continue
        address = signatures.sender_address(item.sender).casefold()
        if address in newest:
            done.same_sender += 1
            done.processed.append((item.message_id, received))
            continue
        if len(newest) >= limit:
            done.over_limit += 1
            done.unprocessed.append(received)
            continue
        try:
            message = read(reader, scope, item.message_id, now=now)
        except MailError as error:
            done.skipped[error.code] = done.skipped.get(error.code, 0) + 1
            done.unprocessed.append(received)
            continue
        done.opened += 1
        done.processed.append((item.message_id, received))
        block = signatures.signature_block(message.body)
        if block is None:
            done.without += 1
            continue
        if item.message_id in seen_in_space:
            done.reread.add(item.message_id)
        newest[address] = signatures.Block(
            message_id=item.message_id,
            sender=signatures.sender_address(item.sender),
            received=item.received.date().isoformat(),
            text=block,
        )
    done.blocks = list(newest.values())
    return done


def target(done: DomainPass, state: SyncState | None, now: datetime) -> datetime | None:
    """Where the state moves after a successful pass, or None to leave it.

    Everything up to the returned moment was processed: the newest processed
    message, or the scan time when the window held none; with messages left
    for later, just before the oldest of them (so the next pass reads them
    again). Never before the stored date (the caller keeps that one)."""
    fresh = [
        message_id for message_id, _ in done.processed if message_id not in done.window.seen_ids
    ]
    if done.window.mode == "incremental" and not fresh and not done.unprocessed:
        # Only messages the previous pass already processed: nothing moves.
        return None
    if done.unprocessed:
        moment = min(done.unprocessed) - timedelta(microseconds=1)
    elif done.processed:
        moment = max(received for _, received in done.processed)
    else:
        moment = now
    if state is not None and done.window.mode == "incremental":
        stored = datetime.fromisoformat(state.last_message_date)
        moment = max(moment, _aware(stored))
    return moment


def window_text(done: DomainPass, scope: MailScope, folder: str) -> str:
    """How the reply names the window: 「從 10/19 之後的新信」, 「首次整理（收件匣
    180 天內）」, 「重新整理（…）」, or the extractor-change sentence."""
    window = done.window
    where = f"{folder_label(folder, scope)} {window.full_days} 天內"
    if window.mode == "first":
        return f"首次整理（{where}）"
    if window.mode == "reset":
        return f"重新整理（{where}）"
    if window.mode == "extractor":
        return f"簽名檔擷取規則已更新，這次重新整理全部範圍內的信（{where}）"
    text = f"從 {local_day(window.last)} 之後的新信"
    if window.capped:
        text += f"（讀信設定只到 {window.full_days} 天內）"
    return text
