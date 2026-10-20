"""Scan Outlook for demo-unit loan approvals and enqueue them (workflow 06).

Producer half of the loan flow. Finds mails carrying a
``<a href="...FastView.aspx...">DR…</a>`` link, and writes one queue item per
**borrow number** for `jobs.loan_process` (workflow 06b) to pick up.

Ported from `c4c/outlook/loan-scan.ps1` in the old repo, with two corrections
that measurement forced:

* The borrow number is not always ``DR`` + digits. Over 124 real mails the old
  ``^DR\\d{6,}$`` matched 66 and **silently dropped 58** -- every ``DRHQ…``,
  ``DRL…`` and ``DRS…`` form. Four categories are live; the old rule saw one.
* Dedupe is by borrow number, not by mail. Those 124 mails carried 118 distinct
  numbers, so keying on the mail would check C4C twice and leave two draft
  replies for one loan.

AEP port (2026-10-20): the mail comes from the host's Outlook adapter and the
queue lives in the host workspace, both passed to `run` (`bridge`, `root`);
the Workflow `engineering/rs-loan-customer-block-scan` splits this run into a
read step (`resolve_start(write=False)` + `_scan(dry_run=True)`) and a write
step (stamp + enqueue). See SOURCE.md for every difference.
"""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from capabilities.loan_reply import queue
from capabilities.loan_reply import rules
from capabilities.loan_reply.bridge_api import Bridge, BridgeClientError

REPO_ROOT = queue.REPO_ROOT

LogFn = Callable[[str], None]

DEFAULT_CONFIG = REPO_ROOT / "config" / "workflow-06.json"
EXAMPLE_CONFIG = REPO_ROOT / "config" / "workflow-06.example.json"

DEFAULTS: dict[str, Any] = {
    "folder": "Inbox",
    "maxMessages": 200,
    #: Off by default: the approval notices come from a workflow mailbox whose
    #: address differs between the HQ and local systems, and rejecting on a
    #: guess would drop real work with no trace.
    "requireSender": False,
    "senderSmtp": "",
    #: Category codes to skip, e.g. ["S"]. Empty = every category, including
    #: ones not yet seen -- a new loan category must not vanish silently.
    "excludeCategories": [],
    #: Only mail received at or after this point is ever processed, e.g.
    #: "2026-08-11 09:00". The mailbox already holds forms somebody answered by
    #: hand before this job existed, and writing to those customers a second
    #: time is worse than being slow. Empty = use the first-run stamp, which
    #: means "from now on".
    #:
    #: Editing this is how you deliberately reach back for older mail -- raise
    #: `sinceHours` to match, or the scan window will still hide it.
    "processFrom": "",
}

def start_stamp_path(root: Path | None = None) -> Path:
    """Where the first-run stamp lives.

    In state, not in the config: the config is a file only the user writes to,
    and a value this job wrote into it would blur who owns which setting.

    Resolved per call rather than captured at import, because the queue root is
    relocatable -- the tests move it, and a module constant would keep pointing
    at the real state directory while everything else used the new one.
    """
    return (root or queue.QUEUE_ROOT) / ".processing-start"

# How this job may be spread across machines (D66).
# Reads the caller's own Outlook and fills the caller's own queue, so a
# scheduled sweep belongs on every subscriber's machine, not on one.

PARAMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "config": {"type": "string", "description": "Path to workflow-06.json."},
        "dryRun": {
            "type": "boolean",
            "default": False,
            "description": "Report what would be enqueued; write nothing.",
        },
        "maxMessages": {"type": ["integer", "null"]},
        "processFrom": {
            "type": ["string", "null"],
            "description": 'Only handle mail received at or after this, e.g. "2026-08-11 09:00". '
                           "Overrides the config and the first-run stamp. The scan window "
                           "(sinceHours) still applies on top.",
        },
    },
}


class JobError(RuntimeError):
    """Anything the caller should see as a failed run."""


def load_config(path: Path | str | None) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    p = queue.resolve_config(path, DEFAULT_CONFIG)
    if p.is_file():
        cfg.update(json.loads(p.read_text(encoding="utf-8-sig")))
    elif path:
        raise FileNotFoundError(f"config not found: {p}")
    elif EXAMPLE_CONFIG.is_file():
        # No live config yet: the example carries usable defaults for a dry run.
        cfg.update(json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8-sig")))
    return {k: v for k, v in cfg.items() if not str(k).startswith("//")}


def _bridge() -> Bridge:
    # The source built its HTTP Bridge client here. In AEP the host passes
    # its Outlook adapter to `run`; there is no default mail source.
    raise JobError("no mail source: the AEP Workflow passes the host's Outlook adapter")


def resolve_start(cfg: Mapping[str, Any], params: Mapping[str, Any], say: LogFn, *,
                  root: Path | None = None, write: bool = True) -> tuple[_dt.datetime, str]:
    """The cut-off, and where it came from.

    Order: an explicit `processFrom` always wins, then the stamp written on the
    very first scan, then now (stamping it). A visible date rather than anything
    inferred from what has already been handled -- "which mail is mine to answer"
    is a decision, and it should be one somebody can read off a config file.
    """
    raw = str(params.get("processFrom") or cfg.get("processFrom") or "").strip()
    if raw:
        try:
            return _dt.datetime.fromisoformat(raw.replace(" ", "T")), "config processFrom"
        except ValueError as exc:
            # Deliberately fatal. Falling back to the stamp would turn "go back
            # and pick up last week" into "from now on" -- the opposite of what
            # was asked, and silent about it.
            raise JobError(
                f"processFrom {raw!r} is not a date/time I can read. "
                f'Use "YYYY-MM-DD HH:MM", e.g. "2026-08-11 09:00".'
            ) from exc

    stamp = start_stamp_path(root)
    if stamp.is_file():
        try:
            return _dt.datetime.fromisoformat(stamp.read_text(encoding="utf-8").strip()), "first-run stamp"
        except (OSError, ValueError):
            say(f"[loan] WARN {stamp.name} is unreadable; stamping a new one")

    now = _dt.datetime.now().replace(microsecond=0)
    if not write:
        # AEP: a read step or a dry run decides the cut-off without keeping it;
        # the write step stamps this same moment (`write_start_stamp`).
        return now, FIRST_RUN_UNSTAMPED
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(now.isoformat(timespec="seconds"), encoding="utf-8")
    except OSError as exc:
        # Without the stamp every run would start "from now", so nothing older
        # than one scan interval would ever be picked up. Say so rather than
        # quietly behaving that way.
        say(f"[loan] WARN could not write {stamp}: {exc}; the cut-off will move each run")
    return now, "first run (stamped now)"


def run(params: Mapping[str, Any] | None = None, log: LogFn | None = None, *,
        bridge: Bridge | None = None, root: Path | None = None,
        stamp: bool = True) -> dict[str, Any]:
    p = dict(params or {})
    say: LogFn = log or (lambda _m: None)
    cfg = p.pop("_config", None) or load_config(p.get("config"))
    dry_run = bool(p.get("dryRun", False))

    folder = str(cfg.get("folder") or "Inbox")
    if p.get("sinceHours") or cfg.get("sinceHours"):
        # Removed rather than renamed: it only ever narrowed what processFrom
        # had already decided, and the two disagreeing was the failure mode.
        say("[loan] NOTE sinceHours is no longer used; processFrom is the only "
            "time bound. maxMessages still caps how much is fetched.")
    limit = int(p.get("maxMessages") or cfg.get("maxMessages") or 200)
    require_sender = bool(cfg.get("requireSender", False))
    expected_sender = str(cfg.get("senderSmtp") or "")
    exclude = list(cfg.get("excludeCategories") or [])
    start_time, start_source = resolve_start(cfg, p, say, root=root, write=stamp)
    say(f"[loan] processing mail received at or after {start_time:%Y-%m-%d %H:%M} ({start_source})")

    bridge = bridge if bridge is not None else _bridge()

    # One scan at a time. `enqueue` checks "already known" and then writes, so
    # two overlapping scans of the same mailbox can both decide a form is new;
    # they write the same filename with the same content, so nothing is
    # corrupted, but the second scan is pure waste -- and once an arriving mail
    # can trigger a scan, a burst of mail means a burst of scans. Separate lock
    # from the consumer's: scanning while a form is being processed is fine.
    try:
        scan_lock = queue.acquire_run_lock(
            "loan_scan", root, owner=str(p.get("workflowName") or ""))
    except queue.RunLockBusy as busy:
        say(f"[loan] {busy}")
        return {
            "folder": folder, "maxMessages": limit, "scanned": 0, "loanForms": 0,
            "enqueued": 0, "skipped": 0, "notLoanForms": 0, "byCategory": {},
            "byNotice": {}, "queue": queue.counts(root), "dryRun": dry_run,
            "processFrom": start_time.isoformat(timespec="seconds"),
            "processFromSource": start_source, "beforeStart": 0, "undated": 0,
            "windowNote": None,
            "skippedRun": True, "skipReason": str(busy),
        }

    try:
        return _scan(bridge, say, folder=folder, limit=limit,
                     start_time=start_time, start_source=start_source,
                     require_sender=require_sender, expected_sender=expected_sender,
                     exclude=exclude, dry_run=dry_run, root=root)
    finally:
        # In a finally, not after the happy path: a scan that raises would
        # otherwise hold the lock until its TTL and block every later scan --
        # for twenty minutes, over a failure that is already being reported.
        scan_lock.release()


def _scan(bridge: Bridge, say: LogFn, *, folder: str, limit: int,
          start_time: _dt.datetime, start_source: str,
          require_sender: bool, expected_sender: str, exclude: list[str],
          dry_run: bool, root: Path | None = None) -> dict[str, Any]:
    """The scan itself, split out so `run` can hold the lock across all of it."""
    # One bound, not two. `sinceHours` used to decide what was fetched while
    # `processFrom` decided what was acted on, which meant a cut-off older than
    # the window silently did nothing -- and the fix for that was a warning
    # about a contradiction that should not have been possible.
    #
    # Fetching from the cut-off costs little: the list comes back newest-first
    # and stops at `maxMessages`, so a wide range cannot starve recent mail and
    # the cap, not the date, is what bounds the work. Measured on the real
    # mailbox: 72h -> 41 messages in 9.1s, a year -> 200 (the cap) in 20.1s,
    # for a job that runs every 30 minutes.
    since = start_time.isoformat(timespec="seconds")
    try:
        listing = bridge.email_list(
            folder=folder, limit=limit, since=since, includeBody=True
        )
    except BridgeClientError as exc:
        raise JobError(f"could not read the {folder!r} folder: {exc}") from exc
    messages = listing.get("messages") or []
    say(f"[loan] {folder}: {len(messages)} message(s) since {start_time:%Y-%m-%d %H:%M}")

    known = queue.known_borrow_numbers(root)
    enqueued: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    by_category: dict[str, int] = {}
    by_notice: dict[str, int] = {}
    not_a_loan = 0

    before_start = 0
    undated = 0

    for message in messages:
        # Checked before parsing: it is cheap, and there is no reason to read
        # the HTML of mail this job is never going to act on.
        received_raw = message.get("receivedTime") or message.get("receivedAt")
        received = None
        if received_raw:
            try:
                received = _dt.datetime.fromisoformat(str(received_raw))
            except ValueError:
                received = None
        if received is None:
            # No usable timestamp, so the cut-off cannot be applied. Skipped,
            # because the harm this cut-off exists to prevent -- writing to a
            # customer somebody already answered -- is worse than a late form,
            # and the count below makes the trade visible instead of silent.
            undated += 1
            continue
        if received < start_time:
            before_start += 1
            continue

        body = message.get("htmlBody") or message.get("body") or ""
        mail = rules.parse_mail(message, body)
        if mail is None:
            not_a_loan += 1
            continue

        by_category[mail.category] = by_category.get(mail.category, 0) + 1
        by_notice[mail.notice or "(none)"] = by_notice.get(mail.notice or "(none)", 0) + 1

        # Rejections are dropped **before** the dedupe, not after. 8 of 118
        # forms carry both notices, and the rejection is often the newer of the
        # two -- deduping first would let it claim the borrow number and lock
        # the approval out as a "duplicate", which is the opposite of the
        # intent. Nothing is enqueued for a rejected form either way: it must
        # not draw a "your instrument is on its way" reply, and its approval
        # view does not open at all.
        if mail.is_rejection:
            skipped.append({**mail.as_dict(), "reason": "rejection notice (否決), not actionable"})
            continue

        if not rules.accepts_sender(mail, expected_sender, require_sender):
            skipped.append({**mail.as_dict(), "reason": f"sender {mail.sender_smtp!r} is not {expected_sender!r}"})
            continue
        if not rules.accepts_category(mail, exclude):
            skipped.append({**mail.as_dict(), "reason": f"category {mail.category!r} is excluded"})
            continue
        if mail.borrow_no in known:
            # The same form approved twice, or already processed in an earlier
            # run. Recorded rather than dropped so a "missing" loan can be
            # traced to a decision instead of a silence.
            skipped.append({**mail.as_dict(), "reason": "borrow number already queued or processed"})
            continue

        known.add(mail.borrow_no)
        if not dry_run:
            queue.enqueue(mail.as_dict(), root)
        enqueued.append(mail.as_dict())

    say(
        f"[loan] {len(enqueued)} enqueued, {len(skipped)} skipped, "
        f"{not_a_loan} not loan forms"
    )
    if by_category:
        say("[loan] categories: " + ", ".join(f"{k}={v}" for k, v in sorted(by_category.items())))
    if by_notice:
        say("[loan] notices: " + ", ".join(f"{k}={v}" for k, v in sorted(by_notice.items())))
    for s in skipped[:10]:
        say(f"[loan]   skipped {s['borrowNo']}: {s['reason']}")
    if len(skipped) > 10:
        say(f"[loan]   … and {len(skipped) - 10} more")

    # With one bound there is no window to contradict the cut-off. What can
    # still hide mail is the cap: the newest `maxMessages` come back, so a
    # cut-off far enough in the past may not reach everything behind it. That is
    # a real risk rather than a self-inflicted one, and it is worth saying.
    window_note = None
    if len(messages) >= limit:
        window_note = (
            f"the fetch returned its maximum of {limit} message(s), so mail older than "
            f"the oldest one seen was not looked at. Raise maxMessages if the cut-off "
            f"({start_time:%Y-%m-%d %H:%M}) is meant to reach further back."
        )
        say(f"[loan] NOTE {window_note}")
    if before_start:
        say(f"[loan] {before_start} message(s) arrived before the cut-off and were left alone")
    if undated:
        say(f"[loan] WARN {undated} message(s) had no readable receivedTime and were skipped")

    return {
        "folder": folder,
        "maxMessages": limit,
        "processFrom": start_time.isoformat(timespec="seconds"),
        "processFromSource": start_source,
        "beforeStart": before_start,
        "undated": undated,
        "windowNote": window_note,
        "scanned": len(messages),
        "loanForms": len(enqueued) + len(skipped),
        "enqueued": len(enqueued),
        "skipped": len(skipped),
        "notLoanForms": not_a_loan,
        "byCategory": by_category,
        "byNotice": by_notice,
        "enqueuedItems": enqueued,
        "skippedItems": skipped,
        "queue": queue.counts(root),
        "dryRun": dry_run,
    }


#: AEP: the cut-off of a first run that has not been stamped yet.
FIRST_RUN_UNSTAMPED = "first run (stamped when enqueued)"


def write_start_stamp(moment: _dt.datetime, root: Path | None = None) -> bool:
    """Keep a first run's cut-off (AEP write step). False when a stamp is
    already there (another scan stamped first) or it cannot be written."""
    stamp = start_stamp_path(root)
    if stamp.is_file():
        return False
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(moment.isoformat(timespec="seconds"), encoding="utf-8")
    except OSError:
        return False
    return True
