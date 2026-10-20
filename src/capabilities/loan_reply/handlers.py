"""The loan reply capabilities: the source jobs' run, as Workflow steps.

Producer (06): `scan_mail` is the source `loan_scan.run` in dry-run mode
without stamping; `enqueue` writes what it decided. Consumer (06b):
`look_up_all` reads each queued form and C4C (`process.look_up`),
`draft_all` claims each item and saves its draft (`process.draft_reply`) or
its failure notice, `offer_send` hands each saved draft to the host's send
cards when the person asked for them. Nothing here sends: a send happens only
when a person presses Send on one card (`host_runtime.loan_reply_cards`).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from capabilities.loan_reply import process, queue, rules, scan, templates
from capabilities.loan_reply.bridge_api import Bridge, BridgeClientError
from capabilities.loan_reply.contracts import (
    DraftedMail,
    DraftStepInput,
    EnqueueStepInput,
    FollowUp,
    LoanDrafts,
    LoanEnqueued,
    LoanLookUp,
    LoanLookUps,
    LoanReplyResult,
    LoanScan,
    LookUpStepInput,
    OfferStepInput,
    ReplyRequest,
    ScanRequest,
    ScanStepInput,
    SendOffer,
    Verdict,
)
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext

BridgeFactory = Callable[[], Bridge]
Offer = Callable[[Sequence[SendOffer]], Sequence[str]]

#: The folders under the host workspace (`loan-reply/`).
QUEUE_FOLDER = "loan-queue"
SHOTS_FOLDER = "loan-shots"

#: The consumer, offered after a scan that left work in the queue.
CONSUMER = {"namespace": "engineering", "name": "rs-loan-queue-reply", "version": "1.0.0"}

#: Why an item was not queued, as the person reads it (source reason -> 中文).
_SKIP_REASONS = (
    ("rejection notice", "否決通知，不處理"),
    ("sender ", "寄件者不是設定的寄件者"),
    ("category ", "此類別已設定排除"),
    ("borrow number already queued", "已在佇列中或已處理過"),
)
_OUTCOMES = {
    "shipping": "可出貨回信",
    "blocked": "有配送限制回信",
    "customer-not-found": "C4C 查無客戶（內部通知）",
}


def queue_root(workspace: Path) -> Path:
    return workspace / "loan-reply" / QUEUE_FOLDER


def _say(_message: str) -> None:
    """The source jobs log progress lines; a Workflow step reports its result."""


# -- producer ---------------------------------------------------------------


def _scan_refusal(error: scan.JobError) -> str:
    text = str(error)
    if "processFrom" in text:
        return "loan_process_from_invalid"
    if "could not read" in text:
        return "loan_mail_unreadable"
    return "loan_scan_refused"


def scan_mail(request: ScanRequest, bridge: BridgeFactory, root: Path) -> LoanScan:
    params: dict[str, Any] = {
        "_config": request.source_config(),
        "dryRun": True,
        "workflowName": "rs-loan-customer-block-scan",
    }
    if request.process_from_once.strip():
        params["processFrom"] = request.process_from_once.strip()
    try:
        out = scan.run(params, _say, bridge=bridge(), root=root, stamp=False)
    except scan.JobError as error:
        raise CapabilityRefused(_scan_refusal(error)) from None
    except ConnectionError:
        raise CapabilityRefused("loan_outlook_unavailable") from None
    return LoanScan(
        folder=str(out["folder"]),
        max_messages=int(out["maxMessages"]),
        process_from=str(out["processFrom"]),
        process_from_source=str(out["processFromSource"]),
        stamp_needed=out["processFromSource"] == scan.FIRST_RUN_UNSTAMPED,
        scanned=int(out["scanned"]),
        loan_forms=int(out["loanForms"]),
        candidates=tuple(out.get("enqueuedItems") or ()),
        skipped=tuple(out.get("skippedItems") or ()),
        not_loan_forms=int(out["notLoanForms"]),
        before_start=int(out["beforeStart"]),
        undated=int(out["undated"]),
        window_note=out.get("windowNote"),
        by_category=dict(out.get("byCategory") or {}),
        by_notice=dict(out.get("byNotice") or {}),
        queue=dict(out.get("queue") or {}),
        dry_run=request.dry_run,
        skipped_run=bool(out.get("skippedRun")),
        skip_reason=str(out.get("skipReason") or ""),
    )


def _reason(text: str) -> str:
    return next((said for prefix, said in _SKIP_REASONS if text.startswith(prefix)), text)


def _queue_line(counts: Mapping[str, int]) -> str:
    return (
        f"佇列：待處理 {counts.get('pending', 0)}、處理中 {counts.get('claimed', 0)}、"
        f"已完成 {counts.get('done', 0)}、失敗 {counts.get('failed', 0)}"
    )


def enqueue(scanned: LoanScan, root: Path) -> LoanEnqueued:
    when = scanned.process_from.replace("T", " ")[:16]
    lines = [
        f"借用單掃描（{scanned.folder}，{when} 之後收到的信）："
        f"看了 {scanned.scanned} 封，其中借用單 {scanned.loan_forms} 張。"
    ]
    if scanned.skipped_run:
        lines.append("另一個掃描正在進行，這次沒有處理任何信。")
        return LoanEnqueued(
            dry_run=scanned.dry_run,
            queue=scanned.queue,
            preview="\n".join(lines),
            verdict=Verdict(ok=None, summary="另一個掃描正在進行"),
        )
    numbers = [str(item.get("borrowNo") or "") for item in scanned.candidates]
    enqueued: list[str] = []
    already: list[str] = []
    stamped = False
    if scanned.dry_run:
        lines.append(
            f"試跑：會排入佇列 {len(numbers)} 筆" + (f"：{'、'.join(numbers)}" if numbers else "")
        )
        if scanned.stamp_needed:
            lines.append(f"第一次正式執行時會記下起算時間 {when}。")
        counts = scanned.queue
    else:
        if scanned.stamp_needed:
            stamped = scan.write_start_stamp(datetime.fromisoformat(scanned.process_from), root)
        for item in scanned.candidates:
            # `queue.enqueue` checks the borrow number again: a scan that ran
            # meanwhile, or this step run twice, adds nothing.
            if queue.enqueue(item, root) is not None:
                enqueued.append(str(item.get("borrowNo") or ""))
            else:
                already.append(str(item.get("borrowNo") or ""))
        lines.append(
            f"排入佇列 {len(enqueued)} 筆" + (f"：{'、'.join(enqueued)}" if enqueued else "")
        )
        if already:
            lines.append(f"已在佇列中（另一次掃描剛排入）：{'、'.join(already)}")
        if stamped:
            lines.append(f"已記下起算時間 {when}；之後只處理這之後收到的信。")
        counts = queue.counts(root)
    for item in scanned.skipped[:10]:
        lines.append(f"略過 {item.get('borrowNo')}：{_reason(str(item.get('reason') or ''))}")
    if len(scanned.skipped) > 10:
        lines.append(f"…另外略過 {len(scanned.skipped) - 10} 筆")
    if scanned.window_note:
        lines.append(
            f"注意：已達單次上限 {scanned.max_messages} 封，更早的信沒有看到；"
            "需要的話請調高「最多看幾封信」。"
        )
    if scanned.undated:
        lines.append(f"注意：{scanned.undated} 封信沒有收件時間，已略過。")
    lines.append(_queue_line(counts))
    follow_up = None
    if not scanned.dry_run and counts.get("pending", 0) > 0:
        follow_up = FollowUp(
            workflow=CONSUMER,
            label=f"處理佇列中的 {counts['pending']} 筆（建立回信草稿）",
            reason="佇列裡有待處理的借用單",
        )
        lines.append(
            "下一步：執行「借用單回信草稿」(rs-loan-queue-reply) 處理佇列；"
            "這一步不會自動開始，由你決定。"
        )
    summary = (
        f"試跑：會排入 {len(numbers)} 筆"
        if scanned.dry_run
        else f"排入 {len(enqueued)} 筆，待處理 {counts.get('pending', 0)} 筆"
    )
    return LoanEnqueued(
        enqueued=tuple(enqueued),
        already_queued=tuple(already),
        stamped=stamped,
        queue=dict(counts),
        dry_run=scanned.dry_run,
        preview="\n".join(lines),
        verdict=Verdict(ok=None if scanned.dry_run else True, summary=summary),
        follow_up=follow_up,
    )


class ScanMailHandler:
    def __init__(self, bridge: BridgeFactory, workspace: Path) -> None:
        self._bridge = bridge
        self._root = queue_root(workspace)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = ScanStepInput.model_validate(inputs)
        return await asyncio.to_thread(scan_mail, step.request, self._bridge, self._root)


class EnqueueHandler:
    def __init__(self, workspace: Path) -> None:
        self._root = queue_root(workspace)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = EnqueueStepInput.model_validate(inputs)
        return await asyncio.to_thread(enqueue, step.scan, self._root)


# -- consumer ---------------------------------------------------------------


def consumer_config(request: ReplyRequest, root: Path) -> dict[str, Any]:
    """The source's `workflow-06.json` keys for `loan_process`."""
    return {
        **process.DEFAULTS,
        "loanAccount": request.loan_account,
        "c4cHomeUrl": request.c4c_home_url or process.C4C_HOME,
        "settleMs": request.settle_ms,
        "busyTimeoutMs": request.busy_timeout_ms,
        "navTimeoutMs": request.nav_timeout_ms,
        "alertRecipient": "; ".join(request.alert_recipient),
        "closeBrowsersAfter": request.close_browsers_after,
        "templateDir": request.template_dir,
        "shotDir": str(root.parent / SHOTS_FOLDER),
    }


def trusted_link(url: str, origin: str) -> bool:
    """A queued link comes from a mail; it is opened in the signed-in profile
    only when it points at the configured loan portal (AEP addition)."""
    try:
        link, allowed = urlsplit(url), urlsplit(origin.strip())
    except ValueError:
        return False
    return (
        link.scheme == "https"
        and allowed.scheme == "https"
        and bool(link.hostname)
        and (link.hostname or "").lower() == (allowed.hostname or "").lower()
        and link.port == allowed.port
    )


def _pending(root: Path, count: int, *, oldest_first: bool) -> list[queue.QueueItem]:
    items = list(queue.iter_pending(root))
    if oldest_first:
        # As `claim_one` takes them: oldest first.
        items.sort(key=lambda item: item.path.stat().st_mtime)
    return items[:count]


def _looked_up(result: Mapping[str, Any], subject: str | None, body: str) -> LoanLookUp:
    return LoanLookUp(
        borrow_no=str(result.get("borrowNo") or ""),
        entry_id=str(result.get("entryId") or ""),
        loan_url=str(result.get("loanUrl") or ""),
        category=str(result.get("category") or ""),
        outcome=str(result.get("outcome") or ""),
        draft_kind=str(result.get("draftKind") or ""),
        subject=subject,
        body=body,
        customer_raw=str(result.get("customerRaw") or ""),
        customer_id=str(result.get("customerId") or ""),
        customer_name=str(result.get("customerName") or ""),
        customer_email=str(result.get("customerEmail") or ""),
        form_borrow_no=str(result.get("formBorrowNo") or ""),
        blocks=dict(result.get("blocks") or {}),
        screenshot=result.get("screenshot"),
    )


def look_up_all(request: ReplyRequest, bridge: BridgeFactory, root: Path) -> LoanLookUps:
    """Read each queued form (up to `max_items`) without claiming it. A form
    that fails is reported with its error; a browser that cannot start or a
    broken template stops the step with nothing changed (source: the item is
    handed back and nothing is marked failed)."""
    cfg = consumer_config(request, root)
    items = _pending(root, request.max_items, oldest_first=not request.dry_run)
    if not items:
        return LoanLookUps(dry_run=request.dry_run, request=request, queue=queue.counts(root))
    host = bridge()
    if hasattr(host, "headless"):
        # The Workflow setting: a visible window for a first sign-in.
        host.headless = not request.show_browser
    loan_edge = process._Edge(host, str(cfg["loanProfile"]), cfg.get("loanPort"), cfg, _say)
    c4c_edge = process._Edge(
        host,
        str(cfg["c4cProfile"]),
        cfg.get("c4cPort"),
        cfg,
        _say,
        start_url=str(cfg["c4cHomeUrl"]),
    )
    found: list[LoanLookUp] = []
    try:
        for item in items:
            url = str(item.payload.get("loanUrl") or "")
            if not trusted_link(url, request.portal_origin):
                found.append(
                    LoanLookUp(
                        borrow_no=item.borrow_no,
                        entry_id=str(item.payload.get("entryId") or ""),
                        loan_url=url,
                        category=str(item.payload.get("category") or ""),
                        error="the link does not open the configured loan portal; "
                        "it was not opened",
                    )
                )
                continue
            try:
                result, subject, body = process.look_up(item, cfg, loan_edge, c4c_edge, _say)
            except templates.TemplateError:
                raise CapabilityRefused("loan_template_invalid") from None
            except ConnectionError:
                raise CapabilityRefused("loan_browser_unavailable") from None
            except (process.JobError, BridgeClientError) as error:
                found.append(
                    LoanLookUp(
                        borrow_no=item.borrow_no,
                        entry_id=str(item.payload.get("entryId") or ""),
                        loan_url=url,
                        category=str(item.payload.get("category") or ""),
                        error=str(error),
                    )
                )
                # One wedged session must not be inherited by the next form.
                loan_edge.drop_session()
                c4c_edge.drop_session()
                continue
            found.append(_looked_up(result, subject, body))
    finally:
        close_after = bool(cfg.get("closeBrowsersAfter", True))
        loan_edge.close(close_after)
        c4c_edge.close(close_after)
    return LoanLookUps(
        items=tuple(found), dry_run=request.dry_run, request=request, queue=queue.counts(root)
    )


def claim_named(borrow_no: str, root: Path) -> queue.QueueItem | None:
    """Claim this one pending item by renaming it, as `claim_one` claims the
    oldest; None when another run has it or it is no longer pending."""
    queue.ensure_dirs(root)
    name = f"{queue._safe_name(borrow_no)}.json"
    source = queue.state_dir("pending", root) / name
    target = queue.state_dir("claimed", root) / name
    try:
        os.replace(source, target)
    except OSError:
        return None
    payload = queue._read(target)
    if payload is None:
        os.replace(target, queue.state_dir("failed", root) / name)
        return None
    return queue.QueueItem(target.stem, target, payload)


def _drafted(look: LoanLookUp, receipt: Any, cfg: Mapping[str, Any]) -> DraftedMail:
    data = receipt if isinstance(receipt, Mapping) else {}
    to = data.get("to")
    if to is None:
        to = [cfg["alertRecipient"]] if cfg.get("alertRecipient") else []
    return DraftedMail(
        borrow_no=look.borrow_no,
        outcome=look.outcome,
        draft_kind=look.draft_kind,
        entry_id=str(data.get("entryId") or ""),
        to=tuple(str(item) for item in to),
        cc=tuple(str(item) for item in data.get("cc") or ()),
        subject=str(data.get("subject") or look.subject or ""),
        attachments=tuple(str(item) for item in data.get("attachments") or ()),
        body=look.body,
    )


def _record(look: LoanLookUp, receipt: Any) -> dict[str, Any]:
    """What the source kept in `done/<borrow>.json`: the outcome, not the mail."""
    return {
        "borrowNo": look.borrow_no,
        "entryId": look.entry_id,
        "loanUrl": look.loan_url,
        "category": look.category,
        "customerRaw": look.customer_raw,
        "customerId": look.customer_id,
        "customerName": look.customer_name,
        "customerEmail": look.customer_email,
        "formBorrowNo": look.form_borrow_no,
        "blocks": look.blocks,
        "screenshot": look.screenshot,
        "outcome": look.outcome,
        "draftKind": look.draft_kind,
        "draft": receipt,
    }


def draft_all(lookups: LoanLookUps, bridge: BridgeFactory, root: Path) -> LoanDrafts:
    request = lookups.request
    if lookups.dry_run:
        return LoanDrafts(
            previews=lookups.items,
            queue=lookups.queue,
            dry_run=True,
            offer_send=request.offer_send,
        )
    cfg = consumer_config(request, root)
    queue.reclaim_expired(root)
    drafted: list[DraftedMail] = []
    notices: list[DraftedMail] = []
    failed: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    stopped = ""
    host: Bridge | None = None
    for look in lookups.items:
        item = claim_named(look.borrow_no, root)
        if item is None:
            skipped.append({"borrowNo": look.borrow_no, "reason": "已由另一次執行處理"})
            continue
        host = host if host is not None else bridge()
        error = look.error
        if not error:
            try:
                source = {"entryId": look.entry_id, "screenshot": look.screenshot}
                receipt = process.draft_reply(host, source, look.subject, look.body, cfg)
            except ConnectionError:
                # Outlook is not there: says nothing about the form. Back to
                # the queue, and stop rather than fail every form after it.
                queue.requeue(item, root)
                stopped = "loan_outlook_unavailable"
                break
            except (process.JobError, BridgeClientError) as failure:
                error = str(failure)
            else:
                drafted.append(_drafted(look, receipt, cfg))
                queue.finish(item, "done", _record(look, receipt), root)
                continue
        notice = process.draft_failure_notice(host, look.borrow_no, look.loan_url, error, cfg, _say)
        if notice is not None:
            subject, _body, _warnings = rules.failure_notice(
                look.borrow_no, look.loan_url, error, templateDir=cfg.get("templateDir")
            )
            notices.append(
                _drafted(
                    look.model_copy(update={"outcome": "failed", "draft_kind": "failure-notice"}),
                    {**notice, "subject": notice.get("subject") or subject}
                    if isinstance(notice, Mapping)
                    else {"subject": subject},
                    cfg,
                )
            )
        failed.append({"borrowNo": look.borrow_no, "error": error})
        # 'failed', not back to 'pending': a person looks at it once.
        queue.finish(item, "failed", {"error": error}, root)
    return LoanDrafts(
        drafted=tuple(drafted),
        failed=tuple(failed),
        notices=tuple(notices),
        skipped=tuple(skipped),
        stopped=stopped,
        queue=queue.counts(root),
        dry_run=False,
        offer_send=request.offer_send,
    )


def _lines_for(look: LoanLookUp) -> list[str]:
    if look.error:
        return [f"• {look.borrow_no}：無法完成，會建立失敗通知草稿（{look.error[:200]}）"]
    said = _OUTCOMES.get(look.outcome, look.outcome)
    head = f"• {look.borrow_no}（{look.customer_raw or '客戶不明'}）：{said}"
    return [head, *("    " + line for line in look.body.splitlines()[:12])]


def offer_send(drafts: LoanDrafts, offer: Offer | None) -> LoanReplyResult:
    lines: list[str] = []
    cards: Sequence[str] = ()
    if drafts.dry_run:
        lines.append(f"試跑：讀了 {len(drafts.previews)} 筆借用單，沒有建立草稿，佇列沒有變動。")
        for look in drafts.previews:
            lines.extend(_lines_for(look))
    else:
        lines.append(
            f"建立了 {len(drafts.drafted)} 封草稿（都在 Outlook 草稿匣，尚未寄出），"
            f"{len(drafts.failed)} 筆無法完成。"
        )
        for mail in drafts.drafted:
            said = _OUTCOMES.get(mail.outcome, mail.outcome)
            to = "、".join(mail.to) or "（未填收件者）"
            lines.append(f"• {mail.borrow_no}：{said}，收件者 {to}")
        for failure in drafts.failed:
            lines.append(f"• {failure['borrowNo']}：失敗，已建立失敗通知草稿並標記為失敗")
        for skip in drafts.skipped:
            lines.append(f"• {skip['borrowNo']}：{skip['reason']}")
        if drafts.stopped:
            lines.append("Outlook 無法使用，已停止；未處理的借用單已放回佇列。")
        sendable = [
            SendOffer(
                borrow_no=mail.borrow_no,
                entry_id=mail.entry_id,
                to=mail.to,
                cc=mail.cc,
                subject=mail.subject,
                body=mail.body,
                attachments=mail.attachments,
            )
            for mail in drafts.drafted
            if mail.entry_id and mail.to
        ]
        if drafts.offer_send and sendable and offer is not None:
            cards = tuple(offer(sendable))
            lines.append(
                f"已為 {len(cards)} 封草稿各建立一張「寄出」確認卡：每封都要你在 Agent Web "
                "按一次「寄出」才會寄出；不按就留在草稿匣。"
            )
        elif drafts.offer_send and drafts.drafted:
            lines.append("沒有可寄出的草稿（沒有收件者），請在 Outlook 檢查。")
        else:
            lines.append("請到 Outlook 草稿匣檢查後自行寄出。")
    lines.append(_queue_line(drafts.queue))
    if drafts.dry_run:
        verdict = Verdict(ok=None, summary=f"試跑：讀了 {len(drafts.previews)} 筆")
    else:
        verdict = Verdict(
            ok=not drafts.failed and not drafts.stopped,
            summary=f"{len(drafts.drafted)} 封草稿，{len(drafts.failed)} 筆失敗",
        )
    return LoanReplyResult(
        drafted=len(drafts.drafted),
        failed=len(drafts.failed),
        send_cards=tuple(cards),
        action_cards=tuple(cards),
        queue=drafts.queue,
        dry_run=drafts.dry_run,
        preview="\n".join(lines),
        verdict=verdict,
    )


class LookUpHandler:
    def __init__(self, bridge: BridgeFactory, workspace: Path) -> None:
        self._bridge = bridge
        self._root = queue_root(workspace)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = LookUpStepInput.model_validate(inputs)
        return await asyncio.to_thread(look_up_all, step.request, self._bridge, self._root)


class DraftRepliesHandler:
    def __init__(self, bridge: BridgeFactory, workspace: Path) -> None:
        self._bridge = bridge
        self._root = queue_root(workspace)

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = DraftStepInput.model_validate(inputs)
        return await asyncio.to_thread(draft_all, step.lookups, self._bridge, self._root)


class OfferSendHandler:
    """Hands drafts to the host's send cards; the host gives `offer`."""

    def __init__(self, offer: Offer | None) -> None:
        self._offer = offer

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = OfferStepInput.model_validate(inputs)
        return await asyncio.to_thread(offer_send, step.drafts, self._offer)
