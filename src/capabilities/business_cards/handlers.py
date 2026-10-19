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

from capabilities.business_cards import chart, reading, signatures
from capabilities.business_cards.contracts import (
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
    HistoryRequest,
    HistoryResult,
    ImportRequest,
    ImportResult,
    LineResult,
    ListRequest,
    PeopleResult,
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
from capabilities.business_cards.store import CardStore, CardStoreError, store_dir
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext
from integrations.outlook_mail import MailError, MailReader, MailScope, read, search
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
CHART_SPEC = _spec(
    "org-chart", "Draw a company's org chart from the contacts (PNG and legend)", "read"
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
    """The store of the request's actor, opened on a worker thread."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def store(self, context: RequestContext) -> CardStore:
        return CardStore.for_actor(self.workspace_root, context.actor)

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
            row, changes, confirmed, change_id = store.edit(
                request.person,
                request.fields.values(),
                actor=who(context),
                reason=request.reason,
                confirm=request.confirm,
                clear=request.clear,
            )
            return EditResult(
                person_id=row["person_id"],
                name=row["name"],
                changes=tuple(changes),
                confirmed=tuple(confirmed),
                needs_confirmation=store.needs_confirmation(row["person_id"]),
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
                undone=request.change_id, reverted=tuple(reverted), change_id=change_id
            )

        return await self.run(work)


class ImportHandler(_Cards):
    """Only the default Hermes place is read: a model cannot point this at a file."""

    def __init__(self, workspace_root: Path, source: Callable[[], Path] = hermes_store) -> None:
        super().__init__(workspace_root)
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
            people, total = self.store(context).find(
                request.query, status=request.status, limit=request.limit
            )
            return PeopleResult(people=tuple(people), total=total)

        return await self.run(work)


class ListHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ListRequest.model_validate(inputs)

        def work() -> Contract:
            people, total = self.store(context).list_people(
                company=request.company,
                source=request.source,
                status=request.status,
                limit=request.limit,
            )
            return PeopleResult(people=tuple(people), total=total)

        return await self.run(work)


class HistoryHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = HistoryRequest.model_validate(inputs)
        return await self.run(
            lambda: self.store(context).history(request.person, limit=request.limit)
        )


class OrgChartHandler(_Cards):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = ChartRequest.model_validate(inputs)

        def work() -> Contract:
            store = self.store(context)
            people, lines, omitted = store.chart_data(
                request.company, include_left=request.include_left
            )
            if not people:
                raise CardStoreError("company_has_no_contacts")
            company = people[0]["company"] or request.company
            folder = store_dir(self.workspace_root, context.actor) / "charts"
            stamp = f"{datetime.now(UTC):%Y%m%d-%H%M%S}"
            safe = "".join(ch if ch.isalnum() else "-" for ch in request.company)[:40] or "company"
            png = folder / f"org-{safe}-{stamp}.png"
            md = folder / f"org-{safe}-{stamp}.md"
            text = chart.legend(
                company,
                people,
                lines,
                include_left=request.include_left,
                left_omitted=omitted,
            )
            try:
                chart.render(
                    png,
                    company,
                    people,
                    lines,
                    uncertain=store.uncertain_now([p["person_id"] for p in people]),
                )
            except ImportError:
                raise CardStoreError("chart_renderer_missing") from None
            folder.mkdir(parents=True, exist_ok=True)
            md.write_text(text + "\n", encoding="utf-8")
            evidenced = sum(1 for line in lines if not line["inferred"])
            return ChartResult(
                company=company,
                people=len(people),
                left_shown=sum(1 for p in people if p["status"] == "left"),
                left_omitted=omitted,
                lines_evidenced=evidenced,
                lines_inferred=len(lines) - evidenced,
                png_path=str(png),
                legend_path=str(md),
                legend_markdown=text,
                note=chart.NOTE if evidenced else chart.NO_LINES_NOTE,
                attach=(
                    ChartFile(path=str(png), media_type="image/png", filename=png.name),
                    ChartFile(path=str(md), media_type="text/markdown", filename=md.name),
                ),
            )

        return await self.run(work)


def skipped_note(skipped: dict[str, int], opened: int) -> str:
    """One line for the person about messages that could not be read."""
    if not skipped:
        return ""
    parts = "、".join(f"{count} 封信無法讀取（{code}）" for code, count in skipped.items())
    return f"讀信失敗：{parts}，已略過；其餘 {opened} 封已處理。"


class HarvestHandler(_Cards):
    """Mail of one company domain, in the person's mail scope, never wider."""

    def __init__(
        self,
        workspace_root: Path,
        reader: Callable[[], MailReader],
        scope: Callable[[], MailScope],
        *,
        model: ModelClient | None,
        alias: str,
        local_only: bool = False,
    ) -> None:
        super().__init__(workspace_root)
        self._reader, self._scope = reader, scope
        self.model, self.alias, self.local_only = model, alias, local_only

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = HarvestRequest.model_validate(inputs)
        model = self.model
        if model is None:
            raise CapabilityRefused("model_not_configured")
        domain = request.domain.lstrip("@").casefold()

        def collect() -> tuple[int, int, list[signatures.Block], dict[str, int], int]:
            reader, scope = self._reader(), self._scope()
            days = min(request.days or scope.max_days, scope.max_days)
            found = search(
                reader,
                scope,
                sender="@" + domain,
                folder=request.folder,
                days=days,
                limit=50,
            )
            newest: dict[str, signatures.Block] = {}
            skipped: dict[str, int] = {}
            matched = opened = 0
            for item in found:
                if not signatures.from_domain(item.sender, domain):
                    continue
                matched += 1
                address = signatures.sender_address(item.sender).casefold()
                if address in newest or len(newest) >= request.limit:
                    continue
                try:
                    message = read(reader, scope, item.message_id)
                except MailError as error:
                    # One unreadable message is skipped and counted, by its code.
                    skipped[error.code] = skipped.get(error.code, 0) + 1
                    continue
                opened += 1
                block = signatures.signature_block(message.body)
                if block is None:
                    continue
                newest[address] = signatures.Block(
                    message_id=item.message_id,
                    sender=signatures.sender_address(item.sender),
                    received=item.received.date().isoformat(),
                    text=block,
                )
            return len(found), matched, list(newest.values()), skipped, opened

        try:
            scanned, matched, blocks, skipped, opened = await asyncio.to_thread(collect)
        except MailError as error:
            raise CapabilityRefused(error.code) from None
        try:
            read_fields = await asyncio.to_thread(
                signatures.read_blocks,
                blocks,
                model,
                self.alias,
                trace=context.trace,
                local_only=self.local_only,
            )
        except RuntimeError:
            raise CapabilityRefused("model_unavailable") from None

        def candidates() -> Contract:
            store = self.store(context)
            out: list[SignatureCandidate] = []
            for block in blocks:
                if block.message_id not in read_fields:
                    continue
                values, unsure = read_fields[block.message_id]
                values = {**values, "email": block.sender}
                # A romanised name is kept only when the block prints it.
                values, unsure, _ = reading.check_romanised(values, unsure, block.text)
                existing, changes = store.preview(values)
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
            ids, expires = store.keep_candidates(
                session_key(context), [item.model_dump(mode="json") for item in out]
            )
            out = [
                item.model_copy(update={"candidate_id": candidate_id})
                for item, candidate_id in zip(out, ids, strict=True)
            ]
            return HarvestResult(
                scanned=scanned,
                from_domain=matched,
                with_signature=len(out),
                candidates=tuple(out),
                note="Nothing was stored. List each candidate with its candidate_id (s1, s2, "
                "...). When the person confirms, call cards__store_candidates with those "
                'candidate_ids, or ["all"]; never harvest again just to store. The '
                "candidates can be stored until expires_at."
                + (" Tell the person skipped_note as written." if skipped else ""),
                expires_at=expires,
                skipped=tuple(
                    SkippedMessages(code=code, count=count) for code, count in skipped.items()
                ),
                skipped_note=skipped_note(skipped, opened),
            )

        return await self.run(candidates)


def bindings(
    workspace_root: Path,
    *,
    reader: Callable[[], MailReader],
    scope: Callable[[], MailScope],
    model: ModelClient | None,
    alias: str,
    local_only: bool = False,
    hermes: Callable[[], Path] = hermes_store,
) -> tuple[tuple[CapabilitySpec, Any, type[Contract], type[Contract]], ...]:
    """Every business-cards capability with its handler and contracts, for a
    host to register."""
    return (
        (ADD_CARD_SPEC, AddCardHandler(workspace_root), AddCardRequest, AddResult),
        (
            ADD_SIGNATURE_SPEC,
            AddFromSignatureHandler(workspace_root),
            AddFromSignatureRequest,
            AddFromSignatureResult,
        ),
        (
            STORE_CANDIDATES_SPEC,
            StoreCandidatesHandler(workspace_root),
            StoreCandidatesRequest,
            StoreCandidatesResult,
        ),
        (EDIT_SPEC, EditPersonHandler(workspace_root), EditPersonRequest, EditResult),
        (STATUS_SPEC, SetStatusHandler(workspace_root), SetStatusRequest, StatusResult),
        (SET_LINE_SPEC, SetLineHandler(workspace_root), SetLineRequest, LineResult),
        (REMOVE_LINE_SPEC, RemoveLineHandler(workspace_root), RemoveLineRequest, LineResult),
        (UNDO_SPEC, UndoHandler(workspace_root), UndoRequest, UndoResult),
        (IMPORT_SPEC, ImportHandler(workspace_root, hermes), ImportRequest, ImportResult),
        (FIND_SPEC, FindHandler(workspace_root), FindRequest, PeopleResult),
        (LIST_SPEC, ListHandler(workspace_root), ListRequest, PeopleResult),
        (HISTORY_SPEC, HistoryHandler(workspace_root), HistoryRequest, HistoryResult),
        (CHART_SPEC, OrgChartHandler(workspace_root), ChartRequest, ChartResult),
        (
            HARVEST_SPEC,
            HarvestHandler(
                workspace_root, reader, scope, model=model, alias=alias, local_only=local_only
            ),
            HarvestRequest,
            HarvestResult,
        ),
    )
