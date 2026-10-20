"""The business-cards capabilities: one actor's contact store, its org chart,
and people read from email signatures (docs/phases/BUSINESS_CARDS.md).

Every handler opens the store of the request's actor, so two members never
see each other's contacts. The writes are local, recorded in history and
undoable; nothing here sends mail or reaches the network except the internal
gateway model call that reads signature blocks.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from capabilities.business_cards import chart, chart_html, harvest, reading, signatures
from capabilities.business_cards.contracts import (
    STATUS_LABELS,
    UNDO_HINT,
    AddCardRequest,
    AddFromSignatureRequest,
    AddFromSignatureResult,
    AddResult,
    ChartFile,
    ChartRequest,
    ChartResult,
    EditPersonRequest,
    EditResult,
    FindRequest,
    HarvestRequest,
    HarvestResult,
    HarvestWindow,
    HistoryRequest,
    HistoryResult,
    ImportRequest,
    ImportResult,
    LineResult,
    ListRequest,
    PeopleResult,
    PersonRef,
    ProposalsRequest,
    ProposalsResult,
    RemoveLineRequest,
    SetLineRequest,
    SetStatusRequest,
    SignatureCandidate,
    SkippedMessages,
    StatusResult,
    StoreCandidatesRequest,
    StoreCandidatesResult,
    UndoRequest,
    UndoResult,
)
from capabilities.business_cards.store import (
    CardStore,
    CardStoreError,
    EditOutcome,
    local_time,
    store_dir,
    undo_note,
)
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from common.memory import SyncState
from integrations.outlook_mail import MAX_RESULTS, MailError, MailReader, MailScope
from memory.registry import MemoryRegistry
from models.contracts import ModelClient

NAMESPACE = "business-cards"
VERSION = "1.0.0"
POLICY_REF = "personal-contacts-policy"
#: The Hermes store, imported once on request.
HERMES_HOME_VARIABLE = "BUSINESS_CARDS_HOME"


def _spec(name: str, description: str, side_effect: Literal["read", "write"]) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": NAMESPACE, "name": name, "version": VERSION},
            "name": f"{NAMESPACE}.{name}",
            "description": description,
            "input_contract": f"{NAMESPACE}.{name}.input.v1",
            "output_contract": f"{NAMESPACE}.{name}.output.v1",
            "side_effect": side_effect,
            "policy": {
                "risk": "low",
                "approval_required": side_effect != "read",
                "required_permissions": [f"{NAMESPACE}.{name}"],
                "policy_refs": [POLICY_REF],
            },
        }
    )


ADD_CARD_SPEC = _spec(
    "add-card", "Store a business card read from a photo in the person's own contacts", "write"
)
ADD_SIGNATURE_SPEC = _spec(
    "add-from-signature",
    "Store people read from email signatures in the person's contacts",
    "write",
)
STORE_CANDIDATES_SPEC = _spec(
    "store-candidates",
    "Store people from this conversation's latest signature harvest by candidate id",
    "write",
)
EDIT_SPEC = _spec("edit-person", "Correct a contact's fields as the person says", "write")
STATUS_SPEC = _spec(
    "set-status", "Mark a contact as left or active, recorded and undoable", "write"
)
SET_LINE_SPEC = _spec(
    "set-reporting-line", "Record who a contact reports to, with evidence", "write"
)
REMOVE_LINE_SPEC = _spec("remove-reporting-line", "Remove a contact's reporting line", "write")
UNDO_SPEC = _spec("undo", "Undo one recorded change to the contacts", "write")
IMPORT_SPEC = _spec(
    "import-hermes", "Import the Hermes business-cards store once, keeping every scan", "write"
)
FIND_SPEC = _spec("find", "Find contacts by name, email, company or title; read only", "read")
LIST_SPEC = _spec("list", "List contacts by company, source and status; read only", "read")
HISTORY_SPEC = _spec("history", "One contact's changes and sightings; read only", "read")
PROPOSALS_SPEC = _spec(
    "proposals",
    "Readings that differ from a contact's confirmed value, still to decide; read only",
    "read",
)
CHART_SPEC = _spec(
    "org-chart",
    "Draw a company's org chart from the contacts (PNG and/or interactive HTML, and legend)",
    "read",
)
HARVEST_SPEC = _spec(
    "harvest-signatures",
    "Read signatures from mail of one company domain within the mail scope set in Settings; "
    "proposes people, stores nothing",
    "read",
)

#: The writes the Host runs without a per-call confirmation (the person's own
#: contact store: local, recorded, undoable; docs/phases/BUSINESS_CARDS.md §3).
WRITE_SPECS = (
    ADD_CARD_SPEC,
    ADD_SIGNATURE_SPEC,
    STORE_CANDIDATES_SPEC,
    EDIT_SPEC,
    STATUS_SPEC,
    SET_LINE_SPEC,
    REMOVE_LINE_SPEC,
    UNDO_SPEC,
    IMPORT_SPEC,
)


def hermes_store() -> Path:
    home = os.environ.get(HERMES_HOME_VARIABLE)
    return (Path(home) if home else Path.home() / ".business-cards") / "cards.db"


def session_key(context: RequestContext) -> str:
    """Which conversation a harvest's candidates belong to."""
    return f"{context.channel}:{context.session_id or '-'}"


def who(context: RequestContext) -> str:
    """Who made a change, as the Host knows it: the request's actor and its
    channel (`alice via telegram`). Never a model argument."""
    return f"{context.actor} via {context.channel}"


class _Cards:
    """The store of the request's actor, opened on a worker thread: the
    `contacts/org` memory space, as the Host's memory registry allows."""

    def __init__(self, workspace_root: Path, memory: MemoryRegistry | None = None) -> None:
        self.workspace_root = workspace_root
        self.memory = memory

    def store(self, context: RequestContext) -> CardStore:
        return CardStore.for_actor(self.workspace_root, context.actor, self.memory)

    async def run(self, work: Callable[[], Contract]) -> Contract:
        try:
            return await asyncio.to_thread(work)
        except CardStoreError as error:
            raise CapabilityRefused(error.code) from None

    def image_ref(self, image_path: str) -> str:
        """`sha256:<hex>` of an attached photo in this Host's attachment store;
        nothing for any other path. The image itself is never kept."""
        if not image_path.strip():
            return ""
        try:
            path = Path(image_path).resolve()
            root = (self.workspace_root / "attachments").resolve()
            if not path.is_relative_to(root) or not path.is_file():
                return ""
            return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError):
            return ""


class AddCardHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = AddCardRequest.model_validate(inputs)
        read = request.values()
        if not read["company_tax_id"]:
            # Printed but not placed in its field (live re-test 2026-10-20).
            read["company_tax_id"] = reading.tax_id_in(request.other_text)
        values, uncertain, dropped = reading.check_romanised(
            read, request.uncertain, request.romanised_name_printed
        )

        def work() -> Contract:
            result = self.store(context).add(
                values,
                source="card",
                source_date=request.card_date or date.today(),
                source_ref=self.image_ref(request.image_path),
                uncertain=uncertain,
                actor=who(context),
            )
            return result.model_copy(update={"dropped": dropped})

        return await self.run(work)


class AddFromSignatureHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = AddFromSignatureRequest.model_validate(inputs)

        def work() -> Contract:
            store = self.store(context)
            results: list[AddResult] = []
            for entry in sorted(request.entries, key=lambda item: item.message_date):
                results.append(
                    store.add(
                        entry.values(),
                        source="email_signature",
                        source_date=entry.message_date,
                        source_ref=entry.message_id,
                        uncertain=entry.uncertain,
                        actor=who(context),
                    )
                )
            return AddFromSignatureResult(results=tuple(results))

        return await self.run(work)


class StoreCandidatesHandler(_Cards):
    """This conversation's harvested candidates, stored by id: the model never
    copies a message id or a date (live test 2026-10-20)."""

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = StoreCandidatesRequest.model_validate(inputs)

        def work() -> Contract:
            results, stored, already, unknown = self.store(context).store_candidates(
                session_key(context), request.candidate_ids, actor=who(context)
            )
            return StoreCandidatesResult(
                results=tuple(results),
                stored=tuple(stored),
                already_stored=tuple(already),
                unknown=tuple(unknown),
            )

        return await self.run(work)


class EditPersonHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = EditPersonRequest.model_validate(inputs)

        def work() -> Contract:
            store = self.store(context)
            outcome = EditOutcome()
            row, changes, confirmed, change_id = store.edit(
                request.person,
                request.fields.values(),
                actor=who(context),
                reason=request.reason,
                confirm=request.confirm,
                clear=request.clear,
                accept=request.accept,
                outcome=outcome,
            )
            remaining, _ = store.proposals(PersonRef(person_id=row["person_id"]), limit=50)
            return EditResult(
                person_id=row["person_id"],
                name=row["name"],
                changes=tuple(changes),
                confirmed=tuple(confirmed),
                already_confirmed=tuple(outcome.already_confirmed),
                accepted=tuple(outcome.accepted),
                rejected=tuple(outcome.rejected),
                proposals=tuple(remaining),
                needs_confirmation=store.needs_confirmation(row["person_id"]),
                to_confirm=store.to_confirm(row["person_id"]),
                change_id=change_id,
            )

        return await self.run(work)


class SetStatusHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SetStatusRequest.model_validate(inputs)

        def work() -> Contract:
            row, old, new, change_id = self.store(context).set_status(
                request.person,
                request.status,
                actor=who(context),
                reason=request.reason,
                effective=request.effective_date,
            )
            return StatusResult(
                person_id=row["person_id"],
                name=row["name"],
                old_status=old,
                new_status=new,
                left_at=row["left_at"],
                change_id=change_id,
                old_status_label=STATUS_LABELS[old],
                new_status_label=STATUS_LABELS[new],
                undo_hint=UNDO_HINT if change_id else "",
            )

        return await self.run(work)


class SetLineHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = SetLineRequest.model_validate(inputs)
        inferred = (
            request.inferred
            if request.inferred is not None
            else request.evidence_kind == "title_inference"
        )
        confidence = (
            request.confidence
            if request.confidence is not None
            else (0.5 if inferred else 1.0 if request.evidence_kind == "user" else 0.8)
        )

        def work() -> Contract:
            row, boss, replaced, change_id = self.store(context).set_line(
                request.person,
                request.manager,
                evidence_kind=request.evidence_kind,
                evidence_ref=request.evidence_ref,
                confidence=confidence,
                inferred=inferred,
                actor=who(context),
            )
            return LineResult(
                person_id=row["person_id"],
                name=row["name"],
                manager_id=boss["person_id"],
                manager=boss["name"],
                evidence_kind=request.evidence_kind,
                inferred=inferred,
                replaced=replaced,
                change_id=change_id,
            )

        return await self.run(work)


class RemoveLineHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = RemoveLineRequest.model_validate(inputs)

        def work() -> Contract:
            row, line, change_id = self.store(context).remove_line(
                request.person, actor=who(context), reason=request.reason
            )
            return LineResult(
                person_id=row["person_id"],
                name=row["name"],
                manager_id="" if line is None else line["manager_id"],
                manager="" if line is None else line["manager_name"],
                evidence_kind="" if line is None else line["evidence_kind"],
                inferred=False if line is None else bool(line["inferred"]),
                removed=line is not None,
                change_id=change_id,
            )

        return await self.run(work)


class UndoHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = UndoRequest.model_validate(inputs)

        def work() -> Contract:
            reverted, change_id = self.store(context).undo(request.change_id, actor=who(context))
            return UndoResult(
                undone=request.change_id,
                reverted=tuple(reverted),
                change_id=change_id,
                note=undo_note(reverted),
            )

        return await self.run(work)


class ImportHandler(_Cards):
    """Only the default Hermes place is read: a model cannot point this at a file."""

    def __init__(
        self,
        workspace_root: Path,
        source: Callable[[], Path] = hermes_store,
        memory: MemoryRegistry | None = None,
    ) -> None:
        super().__init__(workspace_root, memory)
        self.source = source

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        ImportRequest.model_validate(inputs)
        return await self.run(
            lambda: self.store(context).import_hermes(self.source(), actor=who(context))
        )


class FindHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = FindRequest.model_validate(inputs)

        def work() -> Contract:
            store = self.store(context)
            people, total = store.find(request.query, status=request.status, limit=request.limit)
            return PeopleResult(
                people=tuple(people), total=total, company=store.resolve_company(request.query)
            )

        return await self.run(work)


class ListHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ListRequest.model_validate(inputs)

        def work() -> Contract:
            store = self.store(context)
            people, total = store.list_people(
                company=request.company,
                source=request.source,
                status=request.status,
                limit=request.limit,
            )
            company = store.resolve_company(request.company) if request.company else ""
            return PeopleResult(people=tuple(people), total=total, company=company)

        return await self.run(work)


class HistoryHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = HistoryRequest.model_validate(inputs)
        return await self.run(
            lambda: self.store(context).history(request.person, limit=request.limit)
        )


class ProposalsHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ProposalsRequest.model_validate(inputs)

        def work() -> Contract:
            found, note = self.store(context).proposals(request.person, limit=request.limit)
            return ProposalsResult(proposals=tuple(found), total=len(found), note=note)

        return await self.run(work)


def scan_note(
    scanned: int,
    with_signature: int,
    without_signature: int,
    *,
    same_sender: int = 0,
    unreadable_signature: int = 0,
    skipped: int = 0,
    already_seen: int = 0,
    over_limit: int = 0,
    truncated: bool = False,
    window: str = "",
    synced_to: str = "",
) -> str:
    """One sentence for the person on what a harvest found in the mail,
    led by the window it read (「從 10/19 之後的新信：…」)."""
    parts = [f"掃描 {scanned} 封", f"{with_signature} 封有簽名檔"]
    parts.append(f"{without_signature} 封沒有簽名檔")
    if unreadable_signature:
        parts.append(f"{unreadable_signature} 封的簽名檔讀不出聯絡人")
    if same_sender:
        parts.append(f"{same_sender} 封是同一寄件人較舊的信，未讀")
    if already_seen:
        parts.append(f"{already_seen} 封先前已整理過，略過")
    if skipped:
        parts.append(f"{skipped} 封無法讀取")
    if over_limit:
        parts.append(f"{over_limit} 封超過這次的人數上限，留待下次")
    if truncated:
        parts.append(f"範圍內的信超過 {MAX_RESULTS} 封，只處理了最新的 {MAX_RESULTS} 封")
    if (skipped or over_limit) and synced_to:
        parts.append(f"整理進度只更新到 {harvest.local_day(synced_to)}，沒有處理的信下次會再讀")
    text = "，".join(parts) + "。"
    return f"{window}：{text}" if window else text


def skipped_note(skipped: dict[str, int], opened: int) -> str:
    """One line for the person about messages that could not be read."""
    if not skipped:
        return ""
    parts = "、".join(f"{count} 封信無法讀取（{code}）" for code, count in skipped.items())
    return f"讀信失敗：{parts}，已略過；其餘 {opened} 封已處理。"


#: Why the harvest before an org chart was skipped, for the person; the chart
#: is drawn from what is stored all the same.
HARVEST_SKIPPED = {
    "outlook_missing": "這台電腦上沒有可用的 Outlook",
    "library_missing": "這台電腦缺少讀 Outlook 用的 pywin32 元件",
    "mail_failed": "Outlook 讀信時出錯（可能沒有開啟）",
    "folder_unknown": "讀信範圍裡的資料夾找不到",
    "model_not_configured": "沒有設定可用的內部模型，無法讀簽名檔",
    "model_unavailable": "內部模型這次沒有回應",
}
NO_DOMAIN_NOTE = (
    "名片夾裡這家公司的人沒有公司 email 或網站，不知道要讀哪個網域的信，"
    "這次沒有先整理新信；組織圖依已存的資料畫。"
)


def harvest_skipped_note(code: str) -> str:
    reason = HARVEST_SKIPPED.get(code, "讀信沒有完成")
    return f"這次沒有先整理新信：{reason}（{code}）；組織圖依已存的資料畫。"


class HarvestFailed(Exception):
    """A harvest that could not run (no mail, no model), by code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_HARVEST_NOTE = (
    "Nothing was stored. Tell the person scan_note as written. List each candidate with "
    "its candidate_id (s1, s2, ...). When the person confirms, call cards__store_candidates "
    'with those candidate_ids, or ["all"]; never harvest again just to store. The '
    "candidates can be stored until expires_at."
)
_NOTHING_NEW = (
    "Nothing was stored and no new people were found. Tell the person scan_note as written."
)
_CHART_NOTE = (
    " These people are NOT on the chart yet: ask whether to store them; after "
    "cards__store_candidates, call cards__org_chart again with harvest_first false to "
    "redraw it with them."
)


class _Harvesting(_Cards):
    """Reads one company's mail in the person's scope, never wider, and
    only what the sync state says is new (accumulated memory M2)."""

    def __init__(
        self,
        workspace_root: Path,
        reader: Callable[[], MailReader],
        scope: Callable[[], MailScope],
        *,
        model: ModelClient | None,
        alias: str,
        local_only: bool = False,
        memory: MemoryRegistry | None = None,
    ) -> None:
        super().__init__(workspace_root, memory)
        self._reader, self._scope = reader, scope
        self.model, self.alias, self.local_only = model, alias, local_only

    def harvest(
        self,
        context: RequestContext,
        store: CardStore,
        domains: tuple[str, ...],
        *,
        folder: str = "",
        days: int | None = None,
        limit: int = 20,
        full: bool = False,
        for_chart: bool = False,
    ) -> HarvestResult:
        """One incremental pass per domain, the blocks read by the model in
        one go, the candidates kept for this conversation, then each domain's
        sync state moved forward. Runs on a worker thread. `HarvestFailed`
        when the mail or the model is unavailable: then no state moves."""
        model = self.model
        if model is None:
            raise HarvestFailed("model_not_configured")
        now = datetime.now(UTC)
        passes: list[tuple[harvest.DomainPass, SyncState | None]] = []
        try:
            reader, scope = self._reader(), self._scope()
            full_days = min(days or scope.max_days, scope.max_days)
            source = harvest.source_name(folder, scope)
            for domain in domains:
                state = store.sync_state(source, domain)
                window = harvest.plan(
                    state,
                    full=full,
                    now=now,
                    full_days=full_days,
                    extractor_version=signatures.EXTRACTOR_VERSION,
                )
                done = harvest.scan(
                    reader,
                    scope,
                    domain,
                    folder=folder,
                    window=window,
                    now=now,
                    limit=limit,
                    observed=store.observed,
                )
                passes.append((done, state))
        except MailError as error:
            raise HarvestFailed(error.code) from None
        blocks = [block for done, _ in passes for block in done.blocks]
        try:
            read_fields = signatures.read_blocks(
                blocks, model, self.alias, trace=context.trace, local_only=self.local_only
            )
        except RuntimeError:
            raise HarvestFailed("model_unavailable") from None

        out: list[SignatureCandidate] = []
        for done, _ in passes:
            for block in done.blocks:
                if block.message_id not in read_fields:
                    done.unreadable_signature += 1
                    continue
                values, unsure = read_fields[block.message_id]
                values = {**values, "email": block.sender}
                # A romanised name is kept only when the block prints it.
                values, unsure, _ = reading.check_romanised(values, unsure, block.text)
                existing, changes = store.preview(values)
                if block.message_id in done.reread and existing and not changes:
                    # Read again after an extractor change, and nothing new.
                    done.already += 1
                    continue
                done.with_signature += 1
                out.append(
                    SignatureCandidate(
                        **values,
                        message_id=block.message_id,
                        message_date=date.fromisoformat(block.received),
                        uncertain=unsure,
                        existing_person_id=existing,
                        would_change=changes,
                    )
                )
        expires = ""
        if out:
            # A pass with nobody new keeps the conversation's earlier
            # candidates storable.
            ids, expires = store.keep_candidates(
                session_key(context), [item.model_dump(mode="json") for item in out]
            )
            out = [
                item.model_copy(update={"candidate_id": candidate_id})
                for item, candidate_id in zip(out, ids, strict=True)
            ]

        windows: list[HarvestWindow] = []
        notes: list[str] = []
        skipped: dict[str, int] = {}
        for done, state in passes:
            moment = harvest.target(done, state, now)
            synced = "" if state is None else state.last_message_date
            if moment is not None:
                synced = store.finish_sync(
                    source,
                    done.domain,
                    last_message_date=moment,
                    message_ids=[message_id for message_id, _ in done.processed],
                    extractor_version=signatures.EXTRACTOR_VERSION,
                    actor=who(context),
                    reset_reason=done.window.reset_reason,
                ).last_message_date
            for code, count in done.skipped.items():
                skipped[code] = skipped.get(code, 0) + count
            note = scan_note(
                done.scanned,
                done.with_signature,
                done.without,
                same_sender=done.same_sender,
                unreadable_signature=done.unreadable_signature,
                skipped=sum(done.skipped.values()),
                already_seen=done.already,
                over_limit=done.over_limit,
                truncated=done.truncated,
                window=harvest.window_text(done, scope, folder),
                synced_to=synced,
            )
            notes.append(note if len(passes) == 1 else f"{done.domain} {note}")
            windows.append(
                HarvestWindow(
                    domain=done.domain,
                    source=source,
                    mode=done.window.mode,
                    since=done.window.since.isoformat(timespec="seconds"),
                    synced_to=synced,
                    note=note,
                )
            )
        found = [done for done, _ in passes]
        note = (_HARVEST_NOTE + (_CHART_NOTE if for_chart else "")) if out else _NOTHING_NEW
        if skipped:
            note += " Tell the person skipped_note as written."
        return HarvestResult(
            scanned=sum(done.scanned for done in found),
            from_domain=sum(done.from_domain for done in found),
            with_signature=len(out),
            without_signature=sum(done.without for done in found),
            same_sender=sum(done.same_sender for done in found),
            unreadable_signature=sum(done.unreadable_signature for done in found),
            already_seen=sum(done.already for done in found),
            over_limit=sum(done.over_limit for done in found),
            truncated=any(done.truncated for done in found),
            scan_note="".join(notes),
            candidates=tuple(out),
            note=note,
            expires_at=expires,
            skipped=tuple(
                SkippedMessages(code=code, count=count) for code, count in skipped.items()
            ),
            skipped_note=skipped_note(skipped, sum(done.opened for done in found)),
            domains=tuple(windows),
        )


class OrgChartHandler(_Harvesting):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ChartRequest.model_validate(inputs)

        def work() -> Contract:
            store = self.store(context)
            harvested: HarvestResult | None = None
            harvest_note = ""
            if request.harvest_first:
                # Owner decision 2026-10-20 (accumulated memory §10.1): the
                # company's new mail first; new people are candidates only.
                _, domains = store.company_domains(request.company)
                if not domains:
                    harvest_note = NO_DOMAIN_NOTE
                else:
                    try:
                        harvested = self.harvest(context, store, domains, for_chart=True)
                    except HarvestFailed as failed:
                        harvest_note = harvest_skipped_note(failed.code)
            return self.chart(context, store, request, harvested, harvest_note)

        return await self.run(work)

    def chart(
        self,
        context: RequestContext,
        store: CardStore,
        request: ChartRequest,
        harvested: HarvestResult | None,
        harvest_note: str,
    ) -> ChartResult:
        # Everyone, also who left: the HTML page toggles them; the PNG and
        # the legend show them only when asked.
        everyone, all_lines, _ = store.chart_data(request.company, include_left=True)
        people = [p for p in everyone if request.include_left or p["status"] != "left"]
        omitted = len(everyone) - len(people)
        shown_ids = {p["person_id"] for p in people}
        lines = [
            line
            for line in all_lines
            if line["person_id"] in shown_ids and line["manager_id"] in shown_ids
        ]
        if not people:
            if harvested is not None and harvested.candidates:
                # Nobody stored yet, but the mail named people: the chart
                # waits for the person to store them.
                return ChartResult(
                    company=request.company,
                    people=0,
                    format=request.format,
                    legend_path="",
                    legend_markdown="",
                    note=NO_CHART_YET,
                    attach=(),
                    harvest=harvested,
                )
            raise CardStoreError("company_has_no_contacts")
        company = store.resolve_company(request.company) or people[0]["company"] or request.company
        folder = store_dir(self.workspace_root, context.actor) / "charts"
        now = datetime.now(UTC)
        stamp = f"{now:%Y%m%d-%H%M%S}"
        safe = "".join(ch if ch.isalnum() else "-" for ch in request.company)[:40] or "company"
        png = folder / f"org-{safe}-{stamp}.png"
        page = folder / f"org-{safe}-{stamp}.html"
        md = folder / f"org-{safe}-{stamp}.md"
        needs = store.uncertain_now([p["person_id"] for p in everyone])
        text = chart.legend(
            company,
            people,
            lines,
            include_left=request.include_left,
            left_omitted=omitted,
            uncertain=needs,
        )
        files: list[ChartFile] = []
        if request.format in ("png", "both"):
            try:
                chart.render(png, company, people, lines, uncertain=needs)
            except ImportError:
                raise CardStoreError("chart_renderer_missing") from None
            files.append(ChartFile(path=str(png), media_type="image/png", filename=png.name))
        if request.format in ("html", "both"):
            chart_html.render(
                page,
                company,
                everyone,
                all_lines,
                uncertain=needs,
                sources=store.sources_seen([p["person_id"] for p in everyone]),
                show_left=request.include_left,
                generated_at=local_time(now.isoformat()),
            )
            files.append(ChartFile(path=str(page), media_type="text/html", filename=page.name))
        folder.mkdir(parents=True, exist_ok=True)
        md.write_text(text + "\n", encoding="utf-8")
        files.append(ChartFile(path=str(md), media_type="text/markdown", filename=md.name))
        evidenced = sum(1 for line in lines if not line["inferred"])
        return ChartResult(
            company=company,
            people=len(people),
            left_shown=sum(1 for p in people if p["status"] == "left"),
            left_omitted=omitted,
            lines_evidenced=evidenced,
            lines_inferred=len(lines) - evidenced,
            format=request.format,
            png_path=str(png) if request.format != "html" else "",
            html_path=str(page) if request.format != "png" else "",
            legend_path=str(md),
            legend_markdown=text,
            note=chart.NOTE if evidenced else chart.NO_LINES_NOTE,
            attach=tuple(files),
            harvest=harvested,
            harvest_note=harvest_note,
        )


NO_CHART_YET = (
    "No contact of this company is stored yet, so no chart was drawn. Tell the person "
    "the harvest's scan_note and list its candidates; once they are stored, call "
    "cards__org_chart again with harvest_first false."
)


class HarvestHandler(_Harvesting):
    """Mail of one company domain (or a stored company's domains), in the
    person's mail scope, never wider; only what is new since the last pass
    unless `full` (「重新整理」)."""

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = HarvestRequest.model_validate(inputs)
        if self.model is None:
            raise CapabilityRefused("model_not_configured")

        def work() -> Contract:
            store = self.store(context)
            if request.domain:
                domains: tuple[str, ...] = (request.domain.lstrip("@").casefold(),)
            else:
                _, domains = store.company_domains(request.company)
                if not domains:
                    raise CardStoreError("company_has_no_domain")
            try:
                return self.harvest(
                    context,
                    store,
                    domains,
                    folder=request.folder,
                    days=request.days,
                    limit=request.limit,
                    full=request.full,
                )
            except HarvestFailed as failed:
                raise CardStoreError(failed.code) from None

        return await self.run(work)


def bindings(
    workspace_root: Path,
    *,
    reader: Callable[[], MailReader],
    scope: Callable[[], MailScope],
    model: ModelClient | None,
    alias: str,
    local_only: bool = False,
    hermes: Callable[[], Path] = hermes_store,
    memory: MemoryRegistry | None = None,
) -> tuple[tuple[CapabilitySpec, Any, type[Contract], type[Contract]], ...]:
    """Every business-cards capability with its handler and contracts, for a
    host to register. `memory` is the Host's memory registry (the shipped
    business-cards declaration when None)."""
    root, m = workspace_root, memory
    return (
        (ADD_CARD_SPEC, AddCardHandler(root, m), AddCardRequest, AddResult),
        (
            ADD_SIGNATURE_SPEC,
            AddFromSignatureHandler(root, m),
            AddFromSignatureRequest,
            AddFromSignatureResult,
        ),
        (
            STORE_CANDIDATES_SPEC,
            StoreCandidatesHandler(root, m),
            StoreCandidatesRequest,
            StoreCandidatesResult,
        ),
        (EDIT_SPEC, EditPersonHandler(root, m), EditPersonRequest, EditResult),
        (STATUS_SPEC, SetStatusHandler(root, m), SetStatusRequest, StatusResult),
        (SET_LINE_SPEC, SetLineHandler(root, m), SetLineRequest, LineResult),
        (REMOVE_LINE_SPEC, RemoveLineHandler(root, m), RemoveLineRequest, LineResult),
        (UNDO_SPEC, UndoHandler(root, m), UndoRequest, UndoResult),
        (IMPORT_SPEC, ImportHandler(root, hermes, m), ImportRequest, ImportResult),
        (FIND_SPEC, FindHandler(root, m), FindRequest, PeopleResult),
        (LIST_SPEC, ListHandler(root, m), ListRequest, PeopleResult),
        (HISTORY_SPEC, HistoryHandler(root, m), HistoryRequest, HistoryResult),
        (PROPOSALS_SPEC, ProposalsHandler(root, m), ProposalsRequest, ProposalsResult),
        (
            CHART_SPEC,
            OrgChartHandler(
                root, reader, scope, model=model, alias=alias, local_only=local_only, memory=m
            ),
            ChartRequest,
            ChartResult,
        ),
        (
            HARVEST_SPEC,
            HarvestHandler(
                root, reader, scope, model=model, alias=alias, local_only=local_only, memory=m
            ),
            HarvestRequest,
            HarvestResult,
        ),
    )
