"""The business-cards contact store (docs/phases/BUSINESS_CARDS.md §2).

Synthetic people only. Covers what the Hermes `cards.py` could not do: a
source per observation, email-keyed de-duplication across a card and a
signature, romanised names, business group / division / department kept
apart, field-level provenance (a user-set value survives a signature),
departures and undo with history, reporting lines with evidence, per-actor
isolation and the one-time import of a Hermes `cards.db`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.store import CardStore, CardStoreError, store_dir

CARD = {
    "name": "王小明",
    "romanised_name": "Hsiao-Ming Wang",
    "company": "範例科技股份有限公司",
    "business_group": "網通事業群",
    "division": "研發處",
    "department": "射頻部",
    "title": "經理",
    "phone": "02-2345-6789",
    "ext": "312",
    "mobile": "0912-345-678",
    "fax": "02-2345-0000",
    "email": "hm.wang@example.com",
}


def _store(tmp_path: Path, actor: str = "alice") -> CardStore:
    return CardStore.for_actor(tmp_path, actor)


def _add(
    store: CardStore,
    values: dict[str, str],
    *,
    source: Any = "card",
    when: date = date(2026, 1, 10),
    ref: str = "",
    uncertain: tuple[Any, ...] = (),
    actor: str = "alice",
) -> Any:
    return store.add(
        values, source=source, source_date=when, source_ref=ref, uncertain=uncertain, actor=actor
    )


def test_a_card_is_stored_and_a_rescan_leads_with_the_change(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = _add(store, CARD)
    assert first.outcome == "created" and not first.existed
    again = _add(store, CARD, when=date(2026, 3, 1))
    assert again.outcome == "unchanged" and again.existed and again.matched_by == "email"
    moved = _add(store, {**CARD, "title": "協理", "mobile": "0922-000-111"}, when=date(2026, 6, 1))
    assert moved.outcome == "updated" and moved.person_id == first.person_id
    assert {(c.field, c.old, c.new) for c in moved.changes} == {
        ("title", "經理", "協理"),
        ("mobile", "0912-345-678", "0922-000-111"),
    }
    assert moved.summary.startswith("上次是射頻部經理, 現在是射頻部協理")
    assert "手機" in moved.summary
    # Every scan is kept.
    history = store.history(PersonRef(person_id=first.person_id), limit=50)
    assert len(history.observations) == 3
    assert {o.source for o in history.observations} == {"card"}


def test_email_is_the_key_across_a_card_and_a_signature(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _add(store, CARD)
    # The signature spells the company another way and the name in English.
    signed = _add(
        store,
        {
            "name": "Hsiao-Ming Wang",
            "company": "範例科技",
            "email": "HM.Wang@Example.com",
            "title": "協理",
        },
        source="email_signature",
        when=date(2026, 5, 1),
        ref="<msg-1@example.com>",
    )
    assert signed.person_id == card.person_id and signed.matched_by == "email"
    view = store.view(card.person_id)
    # Same company, same person: neither the name nor the company is replaced.
    assert view.name == "王小明" and view.company == "範例科技股份有限公司"
    assert view.title == "協理"
    assert set(view.sources) == {"card", "email_signature"}
    people, total = store.list_people(
        company="範例科技", source="email_signature", status="any", limit=50
    )
    assert total == 1 and people[0].person_id == card.person_id
    # A different email with the same name is someone else.
    other = _add(store, {**CARD, "email": "another.wang@example.com"})
    assert other.outcome == "created"


def test_a_romanised_name_finds_the_local_name(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _add(store, {k: v for k, v in CARD.items() if k != "email"})
    for spelled in ("Wang Hsiao-Ming", "HSIAOMING WANG", "hsiao ming wang"):
        found = _add(
            store,
            {"name": spelled, "company": "範例科技", "title": "經理"},
            source="email_signature",
            when=date(2026, 2, 1),
            ref=f"<{spelled}>",
        )
        assert found.person_id == card.person_id, spelled
        assert found.matched_by == "romanised_name"
    people, _ = store.find("Wang Hsiao Ming", status="any", limit=10)
    assert [p.person_id for p in people] == [card.person_id]
    # Another company with the same name is not this person.
    elsewhere = _add(store, {"name": "王小明", "company": "其他公司"})
    assert elsewhere.outcome == "created"


def test_business_group_division_and_department_are_kept_apart(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _add(store, CARD)
    view = store.view(person.person_id)
    assert (view.business_group, view.division, view.department) == (
        "網通事業群",
        "研發處",
        "射頻部",
    )
    assert (view.phone, view.ext, view.mobile, view.fax) == (
        "02-2345-6789",
        "312",
        "0912-345-678",
        "02-2345-0000",
    )


def test_a_user_set_value_is_not_overwritten_by_a_signature(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _add(store, CARD)
    _, changes, _ = store.edit(
        PersonRef(person_id=person.person_id),
        {"title": "資深經理"},
        actor="alice",
        reason="told me in person",
    )
    assert [c.field for c in changes] == ["title"]
    later = _add(
        store,
        {"email": CARD["email"], "name": "王小明", "title": "副理", "department": "天線部"},
        source="email_signature",
        when=date(2026, 9, 1),
        ref="<sig>",
    )
    assert store.view(person.person_id).title == "資深經理"
    kept = {k.field: k for k in later.kept}
    assert kept["title"].reason == "user_set" and kept["title"].offered == "副理"
    # An automatic value is still updated by newer evidence.
    assert store.view(person.person_id).department == "天線部"
    history = store.history(PersonRef(person_id=person.person_id), limit=50)
    assert [(p.field, p.proposed) for p in history.proposals] == [("title", "副理")]
    # Older evidence never replaces a newer automatic value.
    older = _add(store, {**CARD, "department": "舊部門"}, when=date(2025, 1, 1))
    assert {k.field: k.reason for k in older.kept}["department"] == "older_evidence"
    assert store.view(person.person_id).department == "天線部"


def test_an_uncertain_reading_never_replaces_a_value(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _add(store, CARD)
    blurred = _add(
        store, {**CARD, "phone": "02-2345-6780"}, when=date(2026, 4, 1), uncertain=("phone",)
    )
    assert store.view(person.person_id).phone == "02-2345-6789"
    assert {k.field: k.reason for k in blurred.kept} == {"phone": "uncertain"}


def test_a_departure_is_recorded_and_undone_with_history(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _add(store, CARD)
    row, old, new, change = store.set_status(
        PersonRef(name="Hsiao-Ming Wang"),
        "left",
        actor="alice via telegram",
        reason="moved to another company",
        effective=date(2026, 10, 1),
    )
    assert (old, new) == ("active", "left") and change is not None
    view = store.view(person.person_id)
    assert (view.status, view.left_at, view.status_set_by) == (
        "left",
        "2026-10-01",
        "alice via telegram",
    )
    assert store.list_people(company="範例科技", source="", status="active", limit=10)[1] == 0
    reverted, undo_change = store.undo(change, actor="alice")
    assert [item.kind for item in reverted] == ["status"]
    view = store.view(person.person_id)
    assert (view.status, view.left_at) == ("active", "")
    kinds = [
        (item.kind, item.old, item.new)
        for item in store.history(PersonRef(person_id=person.person_id), limit=50).history
    ]
    assert ("status", "active", "left") in kinds and ("status", "left", "active") in kinds
    with pytest.raises(CardStoreError) as again:
        store.undo(change, actor="alice")
    assert again.value.code == "change_already_undone"
    assert undo_change is not None


def test_undo_refuses_when_a_later_change_touched_the_value(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _add(store, CARD)
    first = _add(store, {**CARD, "title": "協理"}, when=date(2026, 5, 1))
    _add(store, {**CARD, "title": "處長"}, when=date(2026, 6, 1))
    assert first.change_id is not None
    with pytest.raises(CardStoreError) as refused:
        store.undo(first.change_id, actor="alice")
    assert refused.value.code == "undo_conflict"
    assert store.view(person.person_id).title == "處長"


def test_reporting_lines_carry_evidence_and_inferred_lines_are_marked(tmp_path: Path) -> None:
    store = _store(tmp_path)
    boss = _add(store, CARD)
    worker = _add(
        store,
        {"name": "李大華", "company": "範例科技", "division": "研發處", "title": "工程師"},
    )
    seller = _add(store, {"name": "陳美", "company": "範例科技", "title": "業務"})
    _, _, replaced, change = store.set_line(
        PersonRef(name="李大華"),
        PersonRef(person_id=boss.person_id),
        evidence_kind="signature",
        evidence_ref="<msg-7>",
        confidence=0.8,
        inferred=False,
        actor="alice",
    )
    assert not replaced
    store.set_line(
        PersonRef(person_id=seller.person_id),
        PersonRef(person_id=boss.person_id),
        evidence_kind="title_inference",
        evidence_ref="",
        confidence=0.5,
        inferred=True,
        actor="alice",
    )
    assert store.view(worker.person_id).manager_line == "evidenced"
    assert store.view(seller.person_id).manager_line == "inferred"
    with pytest.raises(CardStoreError) as cycle:
        store.set_line(
            PersonRef(person_id=boss.person_id),
            PersonRef(person_id=worker.person_id),
            evidence_kind="user",
            evidence_ref="",
            confidence=1.0,
            inferred=False,
            actor="alice",
        )
    assert cycle.value.code == "line_cycle"
    _, line, removed = store.remove_line(PersonRef(name="李大華"), actor="alice", reason="wrong")
    assert line is not None and store.view(worker.person_id).manager == ""
    assert removed is not None
    store.undo(removed, actor="alice")
    assert store.view(worker.person_id).manager == "王小明"
    assert change is not None


def test_each_actor_has_a_separate_store(tmp_path: Path) -> None:
    alice, bob = _store(tmp_path, "alice"), _store(tmp_path, "bob")
    _add(alice, CARD, actor="alice")
    assert alice.path != bob.path
    assert store_dir(tmp_path, "alice") != store_dir(tmp_path, "bob")
    assert bob.find("王小明", status="any", limit=10) == ([], 0)
    with pytest.raises(CardStoreError):
        bob.set_status(
            PersonRef(name="王小明"),
            "left",
            actor="bob",
            reason="",
            effective=None,
        )


def _hermes_db(path: Path) -> None:
    """A store as the Hermes `cards.py` writes it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE cards (id INTEGER PRIMARY KEY AUTOINCREMENT, captured_at TEXT NOT NULL, "
            "name TEXT NOT NULL, company TEXT NOT NULL, department TEXT, title TEXT, phone TEXT, "
            "mobile TEXT, email TEXT, address TEXT, website TEXT, notes TEXT, uncertain TEXT, "
            "image_path TEXT, raw_text TEXT)"
        )
        rows = [
            ("2025-03-01T10:00:00+08:00", "王小明", "範例科技", "研發部", "經理", "[]"),
            ("2025-09-01T10:00:00+08:00", "王小明", "範例科技", "研發部", "協理", '["phone"]'),
            ("2025-05-01T10:00:00+08:00", "陳美", "範例科技", "業務部", "業務", "[]"),
        ]
        for captured, name, company, department, title, uncertain in rows:
            con.execute(
                "INSERT INTO cards (captured_at, name, company, department, title, uncertain) "
                "VALUES (?,?,?,?,?,?)",
                (captured, name, company, department, title, uncertain),
            )


def test_the_hermes_store_imports_once_keeping_every_row(tmp_path: Path) -> None:
    source = tmp_path / "home" / ".business-cards" / "cards.db"
    _hermes_db(source)
    before = source.read_bytes()
    store = _store(tmp_path / "ws")
    result = store.import_hermes(source, actor="alice")
    assert (result.found, result.rows, result.imported, result.already) == (True, 3, 3, 0)
    assert result.people_created == 2
    again = store.import_hermes(source, actor="alice")
    assert (again.imported, again.already) == (0, 3)
    assert source.read_bytes() == before
    people, _ = store.find("王小明", status="any", limit=5)
    # Oldest first, so the newest scan's title is the current one.
    assert people[0].title == "協理"
    history = store.history(PersonRef(person_id=people[0].person_id), limit=10)
    assert [(o.source, o.source_date, o.source_ref) for o in history.observations] == [
        ("card", "2025-09-01", "hermes-cards:2"),
        ("card", "2025-03-01", "hermes-cards:1"),
    ]
    assert history.observations[0].uncertain == ("phone",)
    assert not store.import_hermes(tmp_path / "missing.db", actor="alice").found


def test_no_email_body_or_image_is_kept(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _add(store, CARD, ref="sha256:" + "a" * 64)
    with sqlite3.connect(store.path) as con:
        observed = con.execute("SELECT fields_json, source_ref FROM observations").fetchall()
    assert json.loads(observed[0][0])["name"] == "王小明"
    assert observed[0][1] == "sha256:" + "a" * 64


def test_the_import_command_is_idempotent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from test_host_wiring import host_json, ready

    from host_runtime.cli import main

    config, _ = ready(tmp_path / "host")
    path = host_json(tmp_path / "host", config)
    source = tmp_path / "old" / "cards.db"
    _hermes_db(source)
    assert main(["cards", "import", "--config", str(path), "--from", str(source)]) == 0
    assert "3 imported (2 new people, 1 updated), 0 already here" in capsys.readouterr().out
    assert main(["cards", "import", "--config", str(path), "--from", str(source)]) == 0
    assert "0 imported (0 new people, 0 updated), 3 already here" in capsys.readouterr().out
    store = CardStore.for_actor(Path(config.workspace_root), config.device.registered_by)
    assert store.find("陳美", status="any", limit=5)[1] == 1
    missing = tmp_path / "none.db"
    assert main(["cards", "import", "--config", str(path), "--from", str(missing)]) == 0
    assert "no Hermes business-cards store" in capsys.readouterr().out
