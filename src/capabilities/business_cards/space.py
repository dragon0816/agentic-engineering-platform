"""The `contacts/org` memory space: people, companies and reporting lines
(docs/phases/ACCUMULATED_MEMORY.md §3.8; first instance, M1).

The business-cards Skill manages it: it declares the space in its manifest,
ships the merge rules below as data and keeps the space's own tables (the
current view of each person, reporting lines, harvest candidates). The
generic facilities (observations, provenance, history, undo, proposals,
external ids) are the Memory Service's (`memory.service`).
"""

from __future__ import annotations

from typing import Final

from common.memory import (
    AutoMergeRule,
    FieldMergeRule,
    MemorySpaceDeclaration,
    MergeRules,
    RelationRule,
)
from memory.registry import MemoryRegistry
from memory.service import table_prefix

CONTACTS_ORG = "contacts/org"
SCHEMA_REF = "contacts.org.person.v1"
#: v2 (owner 2026-10-20): only new evidence touches the person's value.
RULES_ID = "contacts.org.merge.v2"
REPORTING_LINE = "reporting_line"

#: The owner's defaults (2026-10-20, §3.8.3 and §10.6–10.7):
#: - the company's official name: a business card (a document) wins; C4C,
#:   filled in by people, is a lower-trust system record and a mismatch
#:   becomes a proposal;
#: - title, department, division and business group: the newest evidence;
#: - external ids (C4C account / contact) only match, never name anything;
#: - a reporting line is solid only on the person's word or explicit
#:   evidence; anything else is drawn dashed;
#: - a value the person set is touched only by new evidence (owner
#:   2026-10-20): an email signature sent after the day of the person's
#:   change to that field; a business card, which carries no evidence date,
#:   only when its image was never observed for that person before (a
#:   re-scan of a seen card, or a card without an image, an imported Hermes
#:   card included, never is). Old evidence is ignored silently. New evidence
#:   updates the organisational fields directly ("換部門, 或換職位, 就修改那一
#:   筆資料"; history, undoable; an uncertain reading only proposes); the
#:   email, the identity key, and the other fields stay a proposal;
#: - another source joins a person by itself only on an identical email or
#:   an already-mapped external id; otherwise ask.
#: New evidence proposes against the person's value; old is ignored.
NEWER: Final = "propose_if_newer"
#: New evidence replaces the person's value; old is ignored.
TAKE: Final = "take_if_newer"
#: Where a person sits and how to reach them: new evidence updates them.
ORG_UPDATE_FIELDS = (
    "title",
    "department",
    "division",
    "business_group",
    "honorific",
    "phone",
    "ext",
    "mobile",
    "fax",
    "address",
)

MERGE_RULES = MergeRules(
    rules_id=RULES_ID,
    trust={
        "user": "user_stated",
        "card": "document",
        "email_signature": "document",
        "import": "document",
        "signature": "document",
        "email_content": "document",
        "c4c": "system_record",
        "title_inference": "inferred",
        "agent": "inferred",
    },
    default=FieldMergeRule(policy="newest_evidence", user_conflict=NEWER),
    fields={
        "company": FieldMergeRule(
            policy="precedence", lower_conflict="propose", user_conflict=NEWER
        ),
        **{
            name: FieldMergeRule(policy="newest_evidence", user_conflict=TAKE)
            for name in ORG_UPDATE_FIELDS
        },
        "email": FieldMergeRule(policy="newest_evidence", user_conflict=NEWER),
    },
    external_ids=("c4c_account", "c4c_contact"),
    relations=(
        RelationRule(
            relation=REPORTING_LINE, solid_evidence=("user", "signature", "email_content")
        ),
    ),
    auto_merge=AutoMergeRule(identities=("email",), mapped_external_ids=True),
    # A card's date is when it was scanned, not when it was true.
    undated=("card", "import"),
)

DECLARATION = MemorySpaceDeclaration(
    space=CONTACTS_ORG,
    role="manager",
    # sync_state (M2): how far each mail folder was read for a domain.
    kinds=("entities", "sync_state"),
    sensitivity="CONFIDENTIAL",
    retention="until_deleted",
    schema_ref=SCHEMA_REF,
    merge_rules=RULES_ID,
)

_PREFIX = table_prefix(CONTACTS_ORG)
PEOPLE = _PREFIX + "people"
LINES = _PREFIX + "reporting_lines"
CANDIDATES = _PREFIX + "candidates"

#: The space's own tables, as the business-cards store had them (`cards.db`);
#: a reporting line also names the observation that claimed it.
SPACE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {PEOPLE} (
    person_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    romanised_name TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    company_tax_id TEXT NOT NULL DEFAULT '',
    business_group TEXT NOT NULL DEFAULT '',
    division TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    honorific TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    ext TEXT NOT NULL DEFAULT '',
    mobile TEXT NOT NULL DEFAULT '',
    fax TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    email_key TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    left_at TEXT NOT NULL DEFAULT '',
    status_set_by TEXT NOT NULL DEFAULT '',
    status_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS {PEOPLE}_email ON {PEOPLE}(email_key);
CREATE TABLE IF NOT EXISTS {LINES} (
    line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    manager_id TEXT NOT NULL,
    evidence_kind TEXT NOT NULL,
    evidence_ref TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL,
    inferred INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    removed_at TEXT,
    removed_by TEXT,
    removed_reason TEXT,
    observation_id INTEGER
);
CREATE TABLE IF NOT EXISTS {CANDIDATES} (
    session_key TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    uncertain_json TEXT NOT NULL DEFAULT '[]',
    message_id TEXT NOT NULL,
    message_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    stored_person_id TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (session_key, candidate_id)
);
"""


def default_registry() -> MemoryRegistry:
    """The declarations of the shipped business-cards Skill and its rules,
    with the Host's personal spaces: what a store opened outside a Host
    (the CLI, tests) uses."""
    from capabilities.business_cards.manifest import business_cards_skill
    from memory import personal

    return MemoryRegistry.from_manifests(
        [business_cards_skill()],
        rules=[MERGE_RULES, *personal.RULES],
        first=personal.HOST_DECLARED,
    )
