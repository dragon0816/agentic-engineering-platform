"""Accumulated memory M1: an actor's business-cards `cards.db` moves into the
Memory Service as the `contacts/org` space, once, losslessly and safely.

The fixture is a `cards.db` in the schema the store had before M1, with every
table filled (an honorific, a unified business number, an open and a
rejected proposal, a removed reporting line, an undone change, harvest
candidates). Synthetic people only.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from capabilities.business_cards import migration
from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.space import CANDIDATES, CONTACTS_ORG, LINES, PEOPLE
from capabilities.business_cards.store import DB_FILE, CardStore, CardStoreError, store_dir
from memory.service import memory_path

ACTOR = "alice"
WHO = "alice via telegram"

#: The business-cards store's schema before M1, verbatim.
OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
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
CREATE INDEX IF NOT EXISTS people_email ON people(email_key);
CREATE TABLE IF NOT EXISTS field_sources (
    person_id TEXT NOT NULL,
    field TEXT NOT NULL,
    source TEXT NOT NULL,
    source_date TEXT NOT NULL,
    observation_id INTEGER,
    PRIMARY KEY (person_id, field)
);
CREATE TABLE IF NOT EXISTS observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT,
    source TEXT NOT NULL,
    source_date TEXT NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    fields_json TEXT NOT NULL,
    uncertain_json TEXT NOT NULL DEFAULT '[]',
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS observations_ref ON observations(source_ref);
CREATE TABLE IF NOT EXISTS reporting_lines (
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
    removed_reason TEXT
);
CREATE TABLE IF NOT EXISTS history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    change_id TEXT NOT NULL,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    person_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    field TEXT NOT NULL DEFAULT '',
    old TEXT NOT NULL DEFAULT '',
    new TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS history_change ON history(change_id);
CREATE INDEX IF NOT EXISTS history_person ON history(person_id);
CREATE TABLE IF NOT EXISTS undone (
    change_id TEXT PRIMARY KEY,
    undone_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
    proposal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    field TEXT NOT NULL,
    current TEXT NOT NULL,
    proposed TEXT NOT NULL,
    source TEXT NOT NULL,
    observation_id INTEGER,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS candidates (
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

WANG = {
    "name": "王小明",
    "romanised_name": "Hsiao-Ming Wang",
    "company": "範例科技股份有限公司",
    "company_tax_id": "12345678",
    "business_group": "網通事業群",
    "division": "研發處",
    "department": "射頻部",
    "title": "協理",
    "honorific": "博士",
    "phone": "02-2345-6789",
    "email": "hm.wang@example.com",
}
LEE = {"name": "李大華", "company": "範例科技股份有限公司", "title": "工程師"}
CARD_ID = "sha256:" + "ab" * 32
STAMP = "2026-10-19T08:00:00+00:00"


def _row(table: str, **values: Any) -> tuple[str, dict[str, Any]]:
    return table, values


def _fixture_rows() -> list[tuple[str, dict[str, Any]]]:
    """Every table filled, as the store before M1 wrote them."""
    wang_fields = {k: WANG.get(k, "") for k in ("name", "company", "title", "email")}
    return [
        _row(
            "people",
            person_id="p-wang",
            **WANG,
            email_key="hm.wang@example.com",
            notes="週五休",
            created_at=STAMP,
            updated_at=STAMP,
        ),
        _row(
            "people",
            person_id="p-lee",
            **LEE,
            status="left",
            left_at="2026-10-01",
            status_set_by=WHO,
            status_reason="轉職",
            created_at=STAMP,
            updated_at=STAMP,
        ),
        _row(
            "observations",
            observation_id=1,
            person_id="p-wang",
            source="card",
            source_date="2026-01-10",
            source_ref=CARD_ID,
            fields_json=json.dumps({**WANG, "title": "經理"}, ensure_ascii=False),
            uncertain_json='["phone"]',
            recorded_at=STAMP,
            recorded_by=WHO,
        ),
        _row(
            "observations",
            observation_id=2,
            person_id="p-wang",
            source="email_signature",
            source_date="2026-06-01",
            source_ref="<msg-1@example.com>",
            fields_json=json.dumps({**wang_fields, "title": "副總"}, ensure_ascii=False),
            uncertain_json="[]",
            recorded_at=STAMP,
            recorded_by=WHO,
        ),
        _row(
            "observations",
            observation_id=3,
            person_id="p-lee",
            source="card",
            source_date="2026-02-01",
            source_ref="hermes-cards:7",
            fields_json=json.dumps(LEE, ensure_ascii=False),
            uncertain_json="[]",
            recorded_at=STAMP,
            recorded_by=WHO,
        ),
        *[
            _row(
                "field_sources",
                person_id="p-wang",
                field=name,
                source="card",
                source_date="2026-01-10",
                observation_id=1,
            )
            for name in WANG
            if name != "title"
        ],
        _row(
            "field_sources",
            person_id="p-wang",
            field="title",
            source="user",
            source_date="2026-03-01",
            observation_id=None,
        ),
        *[
            _row(
                "field_sources",
                person_id="p-lee",
                field=name,
                source="card",
                source_date="2026-02-01",
                observation_id=3,
            )
            for name in LEE
        ],
        _row(
            "reporting_lines",
            line_id=1,
            person_id="p-lee",
            manager_id="p-wang",
            evidence_kind="title_inference",
            evidence_ref="",
            confidence=0.5,
            inferred=1,
            created_at=STAMP,
            created_by=WHO,
            removed_at=STAMP,
            removed_by=WHO,
            removed_reason="replaced by a new line",
        ),
        _row(
            "reporting_lines",
            line_id=2,
            person_id="p-lee",
            manager_id="p-wang",
            evidence_kind="signature",
            evidence_ref="<msg-9>",
            confidence=0.8,
            inferred=0,
            created_at=STAMP,
            created_by=WHO,
        ),
        _row(
            "history",
            history_id=1,
            change_id="c-create",
            at=STAMP,
            actor=WHO,
            person_id="p-wang",
            kind="create",
            new="王小明",
            source="card",
            extra_json='{"observation_id": 1}',
        ),
        _row(
            "history",
            history_id=2,
            change_id="c-title",
            at="2026-10-19T09:00:00+00:00",
            actor=WHO,
            person_id="p-wang",
            kind="field",
            field="title",
            old="經理",
            new="協理",
            reason="set by the person",
            source="user",
            extra_json=json.dumps(
                {
                    "prev_source": "card",
                    "prev_date": "2026-01-10",
                    "prev_observation": 1,
                    "closed_proposals": [],
                }
            ),
        ),
        _row(
            "history",
            history_id=3,
            change_id="c-sign",
            at=STAMP,
            actor=WHO,
            person_id="p-wang",
            kind="proposal",
            field="title",
            old="協理",
            new="副總",
            source="email_signature",
            reason="the stored value is kept; the new one is a proposal",
        ),
        _row(
            "history",
            history_id=4,
            change_id="c-left",
            at=STAMP,
            actor=WHO,
            person_id="p-lee",
            kind="status",
            field="status",
            old="active",
            new="left",
            reason="轉職",
            source="user",
            extra_json=json.dumps(
                {"prev_left_at": "", "prev_set_by": "", "prev_reason": "", "left_at": "2026-10-01"}
            ),
        ),
        _row(
            "history",
            history_id=5,
            change_id="c-old",
            at=STAMP,
            actor=WHO,
            person_id="p-lee",
            kind="field",
            field="phone",
            old="",
            new="03-1",
            source="card",
        ),
        _row(
            "history",
            history_id=6,
            change_id="c-old-undo",
            at=STAMP,
            actor=WHO,
            person_id="p-lee",
            kind="field",
            field="phone",
            old="03-1",
            new="",
            reason="undo c-old",
            source="user",
        ),
        _row("undone", change_id="c-old", undone_by="c-old-undo"),
        _row(
            "proposals",
            proposal_id=1,
            person_id="p-wang",
            field="title",
            current="協理",
            proposed="副總",
            source="email_signature",
            observation_id=2,
            created_at=STAMP,
            state="open",
        ),
        _row(
            "proposals",
            proposal_id=2,
            person_id="p-wang",
            field="email",
            current="hm.wang@example.com",
            proposed="hm.wamg@example.com",
            source="card",
            observation_id=1,
            created_at=STAMP,
            state="rejected",
        ),
        _row(
            "candidates",
            session_key="telegram:42",
            candidate_id="s1",
            fields_json=json.dumps(
                {"name": "陳美", "company": "範例科技", "email": "mei.chen@example.com"},
                ensure_ascii=False,
            ),
            uncertain_json='["title"]',
            message_id="m-chen",
            message_date="2026-10-18",
            created_at=STAMP,
            expires_at="2099-01-01T00:00:00+00:00",
        ),
    ]


def _legacy(workspace: Path, *, schema: str = OLD_SCHEMA) -> Path:
    path = store_dir(workspace, ACTOR) / DB_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.executescript(schema)
        have = {
            row[0]: {c[1] for c in con.execute(f"PRAGMA table_info({row[0]})")}
            for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for table, values in _fixture_rows():
            if table not in have:
                continue
            values = {k: v for k, v in values.items() if k in have[table]}
            columns = ", ".join(values)
            marks = ", ".join("?" * len(values))
            con.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(values.values()))
    return path


def _dump(path: Path, table: str, order: str) -> list[dict[str, Any]]:
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(f"SELECT * FROM {table} ORDER BY {order}")]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_every_row_moves_into_the_contacts_space_and_the_old_store_is_kept(
    tmp_path: Path,
) -> None:
    legacy = _legacy(tmp_path)
    before = _digest(legacy)
    old = {
        table: _dump(legacy, table, order)
        for table, order in (
            ("people", "person_id"),
            ("observations", "observation_id"),
            ("field_sources", "person_id, field"),
            ("reporting_lines", "line_id"),
            ("history", "history_id"),
            ("undone", "change_id"),
            ("proposals", "proposal_id"),
            ("candidates", "session_key, candidate_id"),
        )
    }
    store = CardStore.for_actor(tmp_path, ACTOR)
    assert store.path == memory_path(tmp_path, ACTOR)
    # The old store is untouched, and a verified copy sits beside it.
    assert _digest(legacy) == before
    (backup,) = legacy.parent.glob("cards.db.bak-*")
    assert _digest(backup) == before
    assert _dump(backup, "people", "person_id") == old["people"]
    assert _dump(backup, "history", "history_id") == old["history"]
    new = store.path
    assert _dump(new, PEOPLE, "person_id") == old["people"]
    assert [
        {k: v for k, v in row.items() if k != "observation_id"}
        for row in _dump(new, LINES, "line_id")
    ] == old["reporting_lines"]
    assert all(row["observation_id"] is None for row in _dump(new, LINES, "line_id"))
    assert _dump(new, CANDIDATES, "session_key, candidate_id") == old["candidates"]
    observations = _dump(new, "observations", "observation_id")
    assert [
        {
            "observation_id": row["observation_id"],
            "person_id": row["entity_id"],
            "source": row["source_kind"],
            "source_date": row["source_date"],
            "source_ref": row["source_ref"],
            "fields_json": row["fields_json"],
            "uncertain_json": row["uncertain_json"],
            "recorded_at": row["recorded_at"],
            "recorded_by": row["recorded_by"],
        }
        for row in observations
    ] == old["observations"]
    assert {row["space"] for row in observations} == {CONTACTS_ORG}
    assert {row["trust"] for row in observations} == {"document"}
    assert {row["contributor"] for row in observations} == {"engineering/business-cards"}
    sources = _dump(new, "field_sources", "entity_id, field")
    assert [
        {
            "person_id": row["entity_id"],
            "field": row["field"],
            "source": row["source_kind"],
            "source_date": row["source_date"],
            "observation_id": row["observation_id"],
        }
        for row in sources
    ] == old["field_sources"]
    title = next(row for row in sources if (row["entity_id"], row["field"]) == ("p-wang", "title"))
    # Provenance in ADR-K11 terms, from the history row that set the value.
    assert (title["origin"], title["set_by"], title["set_at"]) == (
        "human",
        WHO,
        "2026-10-19T09:00:00+00:00",
    )
    assert next(row for row in sources if row["field"] == "honorific")["origin"] == "tool"
    assert [
        {k: v for k, v in row.items() if k not in ("space",)} | {"person_id": row["entity_id"]}
        for row in _dump(new, "history", "history_id")
    ] == [row | {"entity_id": row["person_id"]} for row in old["history"]]
    assert [(row["change_id"], row["undone_by"]) for row in _dump(new, "undone", "change_id")] == [
        (row["change_id"], row["undone_by"]) for row in old["undone"]
    ]
    assert [
        (
            row["proposal_id"],
            row["entity_id"],
            row["field"],
            row["current"],
            row["proposed"],
            row["source_kind"],
            row["observation_id"],
            row["created_at"],
            row["state"],
        )
        for row in _dump(new, "proposals", "proposal_id")
    ] == [tuple(row.values()) for row in old["proposals"]]
    with sqlite3.connect(new) as con:
        marker = json.loads(
            con.execute("SELECT value FROM meta WHERE key = ?", (migration.MARKER,)).fetchone()[0]
        )
    assert marker["backup"] == str(backup) and marker["sha256"] == before
    assert marker["rows"] == {table: len(rows) for table, rows in old.items()}


def test_the_moved_store_behaves_as_before(tmp_path: Path) -> None:
    _legacy(tmp_path)
    store = CardStore.for_actor(tmp_path, ACTOR)
    wang = store.view("p-wang")
    assert (wang.honorific, wang.company_tax_id, wang.title) == ("博士", "12345678", "協理")
    assert wang.manager == "" and wang.open_proposals == 1
    assert wang.needs_confirmation == ("title", "phone")
    lee = store.view("p-lee")
    assert (lee.status, lee.manager, lee.manager_line) == ("left", "王小明", "evidenced")
    found, _ = store.proposals(None, limit=10)
    assert [(p.field, p.current, p.proposed, p.observation_id) for p in found] == [
        ("title", "協理", "副總", 2)
    ]
    # The same card image still finds its person.
    again = store.add(
        {**WANG, "email": ""},
        source="card",
        source_date=date(2026, 10, 1),
        source_ref=CARD_ID,
        uncertain=(),
        actor=WHO,
    )
    assert (again.person_id, again.matched_by) == ("p-wang", "image")
    # A migrated change undoes as before, with its provenance.
    store.undo("c-title", actor=WHO)
    assert store.view("p-wang").title == "經理"
    store.undo("c-left", actor=WHO)
    assert store.view("p-lee").status == "active"
    with pytest.raises(CardStoreError) as done:
        store.undo("c-old", actor=WHO)
    assert done.value.code == "change_already_undone"
    # The kept harvest candidates can still be stored by id.
    results, stored, _, _ = store.store_candidates("telegram:42", ["s1"], actor=WHO)
    assert stored == ["s1"] and results[0].outcome == "created"
    history = store.history(PersonRef(person_id="p-wang"), limit=50)
    assert [o.observation_id for o in history.observations][-2:] == [2, 1]
    # The Hermes import still knows what it imported before.
    assert store.import_hermes(tmp_path / "missing.db", actor=WHO).found is False


def test_the_migration_runs_once(tmp_path: Path) -> None:
    legacy = _legacy(tmp_path)
    first = CardStore.for_actor(tmp_path, ACTOR)
    first.edit(PersonRef(person_id="p-wang"), {"mobile": "0912-000-000"}, actor=WHO, reason="")
    counts = {t: len(_dump(first.path, t, "rowid")) for t in ("observations", "history")}
    second = CardStore.for_actor(tmp_path, ACTOR)
    assert second.view("p-wang").mobile == "0912-000-000"
    assert {t: len(_dump(second.path, t, "rowid")) for t in counts} == counts
    assert len(list(legacy.parent.glob("cards.db.bak-*"))) == 1
    assert len(_dump(second.path, PEOPLE, "person_id")) == 2


def test_a_failure_mid_way_leaves_nothing_behind_and_the_old_store_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = _legacy(tmp_path)
    before = _digest(legacy)

    def broken(*args: Any, **kwargs: Any) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(migration, "_verify", broken)
    with pytest.raises(CardStoreError) as failed:
        CardStore.for_actor(tmp_path, ACTOR)
    assert failed.value.code == "memory_migration_failed"
    assert _digest(legacy) == before
    path = memory_path(tmp_path, ACTOR)
    assert _dump(path, PEOPLE, "person_id") == []
    assert _dump(path, "observations", "observation_id") == []
    assert _dump(path, "history", "history_id") == []
    with sqlite3.connect(path) as con:
        assert (
            con.execute("SELECT 1 FROM meta WHERE key = ?", (migration.MARKER,)).fetchone() is None
        )

    # A copy that does not match is caught too, and nothing is written.
    def mismatched(con: sqlite3.Connection, *args: Any, **kwargs: Any) -> dict[str, int]:
        counts = original_copy(con, *args, **kwargs)
        con.execute(f"UPDATE {PEOPLE} SET honorific = '' WHERE person_id = 'p-wang'")
        return counts

    monkeypatch.undo()
    original_copy = migration._copy
    monkeypatch.setattr(migration, "_copy", mismatched)
    with pytest.raises(CardStoreError) as differs:
        CardStore.for_actor(tmp_path, ACTOR)
    assert differs.value.code == "memory_migration_mismatch"
    assert _dump(path, PEOPLE, "person_id") == []
    monkeypatch.undo()
    # The next start migrates; the one backup made is reused.
    store = CardStore.for_actor(tmp_path, ACTOR)
    assert store.view("p-wang").honorific == "博士"
    assert len(list(legacy.parent.glob("cards.db.bak-*"))) == 1
    assert _digest(legacy) == before


def test_no_migration_without_a_good_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = _legacy(tmp_path)
    before = _digest(legacy)

    def torn(source: Path, target: Path) -> None:
        target.write_bytes(Path(source).read_bytes()[:100])

    monkeypatch.setattr(shutil, "copyfile", torn)
    with pytest.raises(CardStoreError) as failed:
        CardStore.for_actor(tmp_path, ACTOR)
    assert failed.value.code == "memory_backup_failed"
    assert list(legacy.parent.glob("cards.db.bak-*")) == []
    assert _digest(legacy) == before
    assert _dump(memory_path(tmp_path, ACTOR), PEOPLE, "person_id") == []


def test_an_old_store_changed_after_the_migration_is_not_silently_ignored(
    tmp_path: Path,
) -> None:
    legacy = _legacy(tmp_path)
    CardStore.for_actor(tmp_path, ACTOR)
    with sqlite3.connect(legacy) as con:  # the previous version of AEP stored a card
        con.execute("UPDATE people SET title = '總經理' WHERE person_id = 'p-wang'")
    with pytest.raises(CardStoreError) as changed:
        CardStore.for_actor(tmp_path, ACTOR)
    assert changed.value.code == "memory_legacy_changed"


def test_an_older_store_without_later_columns_and_tables_moves_with_defaults(
    tmp_path: Path,
) -> None:
    older = (
        OLD_SCHEMA.replace("    company_tax_id TEXT NOT NULL DEFAULT '',\n", "")
        .replace("    honorific TEXT NOT NULL DEFAULT '',\n", "")
        .split("CREATE TABLE IF NOT EXISTS candidates")[0]
    )
    _legacy(tmp_path, schema=older)
    store = CardStore.for_actor(tmp_path, ACTOR)
    wang = store.view("p-wang")
    assert (wang.honorific, wang.company_tax_id, wang.title) == ("", "", "協理")
    assert _dump(store.path, CANDIDATES, "candidate_id") == []
    assert len(_dump(store.path, "observations", "observation_id")) == 3


def test_a_new_actor_without_an_old_store_needs_no_migration(tmp_path: Path) -> None:
    store = CardStore.for_actor(tmp_path, "bob")
    assert not (store_dir(tmp_path, "bob") / DB_FILE).exists()
    with sqlite3.connect(store.path) as con:
        assert (
            con.execute("SELECT 1 FROM meta WHERE key = ?", (migration.MARKER,)).fetchone() is None
        )
    # Another actor's old store is never read.
    _legacy(tmp_path)
    assert store.find("王小明", status="any", limit=5) == ([], 0)
