"""Typed inputs and outputs of the business-cards capabilities.

Field names follow the card JSON of the Hermes `business-cards` Skill, with
the gaps closed: `romanised_name`, `ext`, `fax`, and `business_group`
(事業群) / `division` (處) / `department` kept apart.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

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
#: How a source, an evidence kind and a status are named to the person
#: (third live test 2026-10-20: replies showed `email_signature`, `left`).
SOURCE_LABELS: dict[str, str] = {
    "card": "名片",
    "email_signature": "郵件簽名檔",
    "user": "使用者",
    "import": "匯入",
    "signature": "簽名檔",
    "email_content": "郵件內容",
    "title_inference": "依職稱推論",
}
STATUS_LABELS: dict[str, str] = {"active": "在職", "left": "已離職"}
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
    # Any other printed text not placed in a field, one line each (a
    # 統一編號 line, a slogan). The Host only scans it for the unified
    # business number; it is not stored.
    other_text: str = Field(default="", max_length=1000)
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


class _Labelled(Contract):
    """An item naming a field, with the field's Chinese label for the reply
    (英文名, never `romanised_name`)."""

    field: FieldName
    label: str = ""

    @model_validator(mode="before")
    @classmethod
    def _label(cls, data: object) -> object:
        if isinstance(data, dict) and not data.get("label"):
            return {**data, "label": FIELD_LABELS.get(str(data.get("field", "")), "")}
        return data


class FieldChange(_Labelled):
    old: str
    new: str


class ToConfirm(_Labelled):
    """A field to ask the person about, with what is stored now: a question
    names the stored value (「英文名目前是 Clark Wang，對嗎？」)."""

    stored: str


class KeptField(_Labelled):
    """A value that was offered and not taken, and why."""

    current: str
    offered: str
    # email_differs: a reading matched by image or name + company brought
    # another email; the stored one is kept and the new one is a proposal.
    # less_complete: the reading is a strict prefix or substring of the
    # stored value ("研展處" for "研展處 I"), so the stored one stays.
    reason: Literal["user_set", "older_evidence", "uncertain", "email_differs", "less_complete"]


class DroppedField(_Labelled):
    """A value the Host did not store, and why."""

    value: str
    # not_on_card: a romanised name the reading could not show printed.
    reason: Literal["not_on_card"]


class ProposalView(_Labelled):
    """An automatic reading that differs from the person's own (set or
    confirmed) value, or another email for a matched person: still open
    until the person keeps the stored value or takes the read one. The field
    needs confirmation while it is open."""

    current: str  # the value stored now
    proposed: str  # the value read
    source: str
    source_label: str = ""
    proposal_id: int = 0
    observation_id: int | None = None
    person_id: str = ""
    name: str = ""
    company: str = ""
    created_at: str = ""


class EmailDiffers(Contract):
    """The reading's email is not the stored one (the person matched by the
    card image or by name and company)."""

    stored: str
    read: str


class AddResult(Contract):
    person_id: str
    name: str
    company: str
    outcome: Literal["created", "updated", "unchanged"]
    existed: bool
    matched_by: Literal["image", "email", "name_company", "romanised_name"] | None = None
    changes: tuple[FieldChange, ...] = ()
    kept: tuple[KeptField, ...] = ()
    uncertain: tuple[FieldName, ...] = ()
    # Fields any reading flagged that the person has not confirmed or
    # corrected yet: still to ask about, even when this scan was sure.
    needs_confirmation: tuple[FieldName, ...] = ()
    # The fields to ask about (uncertain this time or still to confirm),
    # each with its label and the value stored now.
    to_confirm: tuple[ToConfirm, ...] = ()
    dropped: tuple[DroppedField, ...] = ()
    # Set when this reading's email differs from the stored one: say so.
    email_differs: EmailDiffers | None = None
    # The person's open proposals (this reading's and earlier ones): each
    # field here needs confirmation; ask which value is right.
    proposals: tuple[ProposalView, ...] = ()
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
    # Fields the person says are wrong and should be empty (kept empty: a
    # later scan does not refill them).
    clear: tuple[FieldName, ...] = Field(default=(), max_length=len(FIELDS))
    # Fields whose open proposal the person takes ("用新的"): the value read
    # becomes their own.
    accept: tuple[FieldName, ...] = Field(default=(), max_length=len(FIELDS))
    reason: str = Field(default="", max_length=_SHORT)


class EditResult(Contract):
    person_id: str
    name: str
    changes: tuple[FieldChange, ...] = ()
    confirmed: tuple[FieldName, ...] = ()
    # Asked to confirm, but already the person's own value with nothing open.
    already_confirmed: tuple[FieldName, ...] = ()
    # Proposals closed: the read value taken (accepted) or the stored one kept
    # (rejected).
    accepted: tuple[FieldName, ...] = ()
    rejected: tuple[FieldName, ...] = ()
    proposals: tuple[ProposalView, ...] = ()
    needs_confirmation: tuple[FieldName, ...] = ()
    to_confirm: tuple[ToConfirm, ...] = ()
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
    # The stored company the query named ("WNC" -> 啟碁科技股份有限公司), if any.
    company: str = ""


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


class HistoryResult(Contract):
    person: PersonView
    history: tuple[HistoryItem, ...]
    observations: tuple[ObservationView, ...]
    proposals: tuple[ProposalView, ...] = ()


class ProposalsRequest(Contract):
    """Open proposals: one person's, or everyone's when no person is named."""

    person: PersonRef | None = None
    limit: int = Field(default=50, ge=1, le=200)


class ProposalsResult(Contract):
    proposals: tuple[ProposalView, ...]
    total: int
    # One sentence for the reply, e.g.
    # 「目前有 1 項待確認：王小明 的 Email（名片夾：…；這次讀到：…）。」
    note: str


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
    # A short id for this conversation ("s1"), to store it with
    # `store-candidates`; the Host keeps the message id and date.
    candidate_id: str = ""
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
    # When this conversation's candidates can no longer be stored by id.
    expires_at: str = ""


class StoreCandidatesRequest(Contract):
    """Candidates of this conversation's latest harvest, by id ("s1"), or
    ["all"]. The Host stores them with source `email_signature`, each with its
    message id and date; the model copies neither."""

    candidate_ids: tuple[str, ...] = Field(min_length=1, max_length=50)


class StoreCandidatesResult(Contract):
    results: tuple[AddResult, ...] = ()
    stored: tuple[str, ...] = ()
    already_stored: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
