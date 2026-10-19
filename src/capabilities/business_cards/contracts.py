"""Typed inputs and outputs of the business-cards capabilities.

Field names follow the card JSON of the Hermes `business-cards` Skill, with
the gaps closed: `romanised_name`, `ext`, `fax`, and `business_group`
(事業群) / `division` (處) / `department` kept apart.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from common.base import Contract

FieldName = Literal[
    "name",
    "romanised_name",
    "company",
    "company_tax_id",
    "business_group",
    "division",
    "department",
    "title",
    "honorific",
    "phone",
    "ext",
    "mobile",
    "fax",
    "email",
    "address",
    "website",
    "notes",
]
#: Every person field, in the order a card is read and shown.
FIELDS: tuple[FieldName, ...] = (
    "name",
    "romanised_name",
    "company",
    "company_tax_id",
    "business_group",
    "division",
    "department",
    "title",
    "honorific",
    "phone",
    "ext",
    "mobile",
    "fax",
    "email",
    "address",
    "website",
    "notes",
)
#: How a field is named to the person (the org chart, replies).
FIELD_LABELS: dict[str, str] = {
    "name": "姓名",
    "romanised_name": "英文名",
    "company": "公司",
    "company_tax_id": "統一編號",
    "business_group": "事業群",
    "division": "處",
    "department": "部門",
    "title": "職稱",
    "honorific": "學位/尊稱",
    "phone": "電話",
    "ext": "分機",
    "mobile": "手機",
    "fax": "傳真",
    "email": "Email",
    "address": "地址",
    "website": "網站",
    "notes": "備註",
}
Source = Literal["card", "email_signature", "user", "import"]
Status = Literal["active", "left"]
EvidenceKind = Literal["signature", "email_content", "title_inference", "user"]

_SHORT = 200
_LONG = 600


class CardFields(Contract):
    """What one card or signature says. Empty means "not on it"."""

    name: str = Field(default="", max_length=120)
    romanised_name: str = Field(default="", max_length=120)
    company: str = Field(default="", max_length=_SHORT)
    # The company's unified business number (統一編號), always here, never
    # in notes (DECISIONS 2026-10-20).
    company_tax_id: str = Field(default="", max_length=40)
    business_group: str = Field(default="", max_length=_SHORT)
    division: str = Field(default="", max_length=_SHORT)
    department: str = Field(default="", max_length=_SHORT)
    title: str = Field(default="", max_length=_SHORT)
    # An academic or honorific title (博士, Dr., PhD), never part of `title`.
    honorific: str = Field(default="", max_length=60)
    phone: str = Field(default="", max_length=60)
    ext: str = Field(default="", max_length=30)
    mobile: str = Field(default="", max_length=60)
    fax: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=_LONG)
    website: str = Field(default="", max_length=_SHORT)
    notes: str = Field(default="", max_length=_LONG)

    def values(self) -> dict[str, str]:
        return {name: str(getattr(self, name)).strip() for name in FIELDS}


class AddCardRequest(CardFields):
    """A card the model read from a photo."""

    uncertain: tuple[FieldName, ...] = Field(default=(), max_length=len(FIELDS))
    # Where the romanised name is printed, copied as printed ("Ryan Fan, under
    # the Chinese name"). Without it the Host drops romanised_name.
    romanised_name_printed: str = Field(default="", max_length=200)
    # The attached photo's path, as the conversation listed it. Only its hash
    # is kept, and only for a file inside this Host's attachment store.
    image_path: str = Field(default="", max_length=1000)
    # The day the card was received; today when not given.
    card_date: date | None = None


class SignatureEntry(CardFields):
    """One person read from an email signature."""

    message_id: str = Field(min_length=1, max_length=400)
    message_date: date
    uncertain: tuple[FieldName, ...] = Field(default=(), max_length=len(FIELDS))


class AddFromSignatureRequest(Contract):
    entries: tuple[SignatureEntry, ...] = Field(min_length=1, max_length=50)


class FieldChange(Contract):
    field: FieldName
    old: str
    new: str


class KeptField(Contract):
    """A value that was offered and not taken, and why."""

    field: FieldName
    current: str
    offered: str
    reason: Literal["user_set", "older_evidence", "uncertain"]


class DroppedField(Contract):
    """A value the Host did not store, and why."""

    field: FieldName
    value: str
    # not_on_card: a romanised name the reading could not show printed.
    reason: Literal["not_on_card"]


class AddResult(Contract):
    person_id: str
    name: str
    company: str
    outcome: Literal["created", "updated", "unchanged"]
    existed: bool
    matched_by: Literal["email", "name_company", "romanised_name"] | None = None
    changes: tuple[FieldChange, ...] = ()
    kept: tuple[KeptField, ...] = ()
    uncertain: tuple[FieldName, ...] = ()
    # Fields any reading flagged that the person has not confirmed or
    # corrected yet: still to ask about, even when this scan was sure.
    needs_confirmation: tuple[FieldName, ...] = ()
    dropped: tuple[DroppedField, ...] = ()
    status: Status = "active"
    # "上次是研發部經理, 現在是協理": the sentence to lead with.
    summary: str = ""
    observation_id: int
    change_id: str | None = None


class AddFromSignatureResult(Contract):
    results: tuple[AddResult, ...]


class PersonRef(Contract):
    """Who is meant: the id from an earlier result, or the name (local or
    romanised), with the company when two people share a name."""

    person_id: str = Field(default="", max_length=40)
    name: str = Field(default="", max_length=120)
    company: str = Field(default="", max_length=_SHORT)


class EditPersonRequest(Contract):
    person: PersonRef
    fields: CardFields = CardFields()
    # Fields the person says are right as stored ("email 正確").
    confirm: tuple[FieldName, ...] = Field(default=(), max_length=len(FIELDS))
    reason: str = Field(default="", max_length=_SHORT)


class EditResult(Contract):
    person_id: str
    name: str
    changes: tuple[FieldChange, ...] = ()
    confirmed: tuple[FieldName, ...] = ()
    needs_confirmation: tuple[FieldName, ...] = ()
    change_id: str | None = None


class FindRequest(Contract):
    query: str = Field(min_length=1, max_length=200)
    status: Literal["active", "left", "any"] = "any"
    limit: int = Field(default=20, ge=1, le=100)


class ListRequest(Contract):
    company: str = Field(default="", max_length=_SHORT)
    source: Source | Literal[""] = ""
    status: Literal["active", "left", "any"] = "active"
    limit: int = Field(default=50, ge=1, le=200)


class PersonView(CardFields):
    person_id: str
    status: Status
    left_at: str = ""
    status_reason: str = ""
    status_set_by: str = ""
    sources: tuple[Source, ...] = ()
    manager: str = ""
    manager_line: Literal["evidenced", "inferred", ""] = ""
    open_proposals: int = 0
    needs_confirmation: tuple[FieldName, ...] = ()
    updated_at: str = ""


class PeopleResult(Contract):
    people: tuple[PersonView, ...]
    total: int


class HistoryRequest(Contract):
    person: PersonRef
    limit: int = Field(default=30, ge=1, le=200)


class HistoryItem(Contract):
    change_id: str
    at: str
    actor: str
    kind: str
    field: str = ""
    old: str = ""
    new: str = ""
    reason: str = ""
    source: str = ""


class ObservationView(Contract):
    observation_id: int
    source: Source
    source_date: str
    source_ref: str = ""
    uncertain: tuple[str, ...] = ()


class ProposalView(Contract):
    field: str
    current: str
    proposed: str
    source: str


class HistoryResult(Contract):
    person: PersonView
    history: tuple[HistoryItem, ...]
    observations: tuple[ObservationView, ...]
    proposals: tuple[ProposalView, ...] = ()


class SetStatusRequest(Contract):
    person: PersonRef
    status: Status
    reason: str = Field(default="", max_length=_SHORT)
    # Who said so is never an argument: the Host records the request's actor
    # and channel (live test 2026-10-20 stored the model's "使用者").
    effective_date: date | None = None


class StatusResult(Contract):
    person_id: str
    name: str
    old_status: Status
    new_status: Status
    left_at: str = ""
    change_id: str | None = None


class SetLineRequest(Contract):
    person: PersonRef
    manager: PersonRef
    evidence_kind: EvidenceKind
    evidence_ref: str = Field(default="", max_length=400)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    # Default: true only for a title inference.
    inferred: bool | None = None


class RemoveLineRequest(Contract):
    person: PersonRef
    reason: str = Field(default="", max_length=_SHORT)


class LineResult(Contract):
    person_id: str
    name: str
    manager_id: str = ""
    manager: str = ""
    evidence_kind: str = ""
    inferred: bool = False
    replaced: bool = False
    removed: bool = False
    change_id: str | None = None


class UndoRequest(Contract):
    change_id: str = Field(min_length=1, max_length=60)


class UndoResult(Contract):
    undone: str
    reverted: tuple[HistoryItem, ...]
    change_id: str | None = None


class ImportRequest(Contract):
    """The Hermes store at its default place; nothing to choose."""


class ImportResult(Contract):
    found: bool
    rows: int = 0
    imported: int = 0
    already: int = 0
    people_created: int = 0
    people_updated: int = 0
    source: str = ""


class ChartRequest(Contract):
    company: str = Field(min_length=1, max_length=_SHORT)
    include_left: bool = False


class ChartFile(Contract):
    path: str
    media_type: str
    filename: str


class ChartResult(Contract):
    company: str
    people: int
    left_shown: int = 0
    left_omitted: int = 0
    lines_evidenced: int = 0
    lines_inferred: int = 0
    png_path: str
    legend_path: str
    legend_markdown: str
    note: str
    attach: tuple[ChartFile, ...]


class HarvestRequest(Contract):
    domain: str = Field(min_length=3, max_length=120, pattern=r"^@?[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
    days: int | None = Field(default=None, ge=1, le=365)
    limit: int = Field(default=20, ge=1, le=40)
    folder: str = Field(default="", max_length=200)


class SignatureCandidate(CardFields):
    message_id: str
    message_date: date
    uncertain: tuple[FieldName, ...] = ()
    existing_person_id: str = ""
    would_change: tuple[FieldName, ...] = ()


class SkippedMessages(Contract):
    """Messages that could not be read, by the mail reader's code."""

    code: str
    count: int


class HarvestResult(Contract):
    scanned: int
    from_domain: int
    with_signature: int
    candidates: tuple[SignatureCandidate, ...]
    note: str = ""
    # A message that could not be read is skipped, never the whole harvest.
    skipped: tuple[SkippedMessages, ...] = ()
    # For the person, e.g. "讀信失敗：1 封信無法讀取（message_unknown），已略過；其餘 3 封已處理。"
    skipped_note: str = ""
