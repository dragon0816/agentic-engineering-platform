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
    # A different email with the same name, company and department is the
    # same person with a doubtful email (live test 2026-10-20, bug 3); with a
    # different department too, it is someone else.
    other = _add(store, {**CARD, "email": "another.wang@example.com", "department": "天線部"})
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
    _, changes, _, _ = store.edit(
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


def test_a_doubtful_field_needs_confirmation_until_the_person_confirms_it(
    tmp_path: Path,
) -> None:
    """Live test 2026-10-20: the second scan did not flag the email, and the
    chart stopped warning about it. A field stays "needs confirmation" while any
    reading flagged it and the person has not confirmed or corrected it."""
    store = _store(tmp_path)
    first = _add(store, CARD, uncertain=("email", "fax"))
    assert first.needs_confirmation == ("fax", "email")
    again = _add(store, CARD, when=date(2026, 2, 1))
    assert again.uncertain == () and again.needs_confirmation == ("fax", "email")
    assert store.view(first.person_id).needs_confirmation == ("fax", "email")
    assert store.uncertain_now([first.person_id]) == {first.person_id: ["fax", "email"]}
    # "email 正確": confirmed, recorded in history, and undoable.
    row, changes, confirmed, change = store.edit(
        PersonRef(person_id=first.person_id),
        {},
        actor="alice via telegram",
        reason="the person said the email is right",
        confirm=("email",),
    )
    assert changes == [] and confirmed == ["email"] and change is not None
    assert row["email"] == CARD["email"]
    assert store.view(first.person_id).needs_confirmation == ("fax",)
    history = store.history(PersonRef(person_id=first.person_id), limit=50).history
    assert ("confirm", "email", "alice via telegram") in {
        (item.kind, item.field, item.actor) for item in history
    }
    # Once the person confirmed it, a later doubtful reading does not reopen it.
    _add(store, CARD, when=date(2026, 3, 1), uncertain=("email",))
    assert store.view(first.person_id).needs_confirmation == ("fax",)
    store.undo(change, actor="alice")
    assert store.view(first.person_id).needs_confirmation == ("fax", "email")
    # A correction clears it too; so does re-stating the stored value.
    store.edit(PersonRef(person_id=first.person_id), {"fax": "02-2345-1111"}, actor="a", reason="")
    store.edit(PersonRef(person_id=first.person_id), {"email": CARD["email"]}, actor="a", reason="")
    assert store.view(first.person_id).needs_confirmation == ()
    assert store.uncertain_now([first.person_id]) == {}


def test_the_needs_confirmation_label_names_fields_in_chinese() -> None:
    from capabilities.business_cards import chart

    assert chart.needs_label(["romanised_name", "email"]) == "需確認：英文名、Email"
    assert chart.needs_label(["phone", "ext", "mobile", "fax"]) == "需確認：電話、分機、手機、傳真"
    assert (
        chart.needs_label(["department", "division", "business_group", "title"])
        == "需確認：部門、處、事業群、職稱"
    )


def test_a_degree_is_kept_out_of_the_title_and_the_division_keeps_its_suffix(
    tmp_path: Path,
) -> None:
    """Live test 2026-10-20: the title absorbed 博士 and 研展處 I lost its "I"."""
    store = _store(tmp_path)
    doctor = _add(
        store,
        {"name": "范博", "company": "範例科技", "division": "研展處 I", "title": "資深經理 博士"},
    )
    view = store.view(doctor.person_id)
    assert (view.title, view.honorific, view.division) == ("資深經理", "博士", "研展處 I")
    other = _add(
        store,
        {
            "name": "Ann Lee",
            "company": "範例科技",
            "division": "研展處 II",
            "title": "Dr. Director",
        },
    )
    assert (store.view(other.person_id).title, store.view(other.person_id).honorific) == (
        "Director",
        "Dr.",
    )
    phd = _add(store, {"name": "Bo Lin", "company": "範例科技", "title": "Engineer, Ph.D."})
    assert (store.view(phd.person_id).title, store.view(phd.person_id).honorific) == (
        "Engineer",
        "Ph.D.",
    )
    postdoc = _add(store, {"name": "林後", "company": "範例科技", "title": "博士後研究員"})
    assert store.view(postdoc.person_id).title == "博士後研究員"
    assert store.view(postdoc.person_id).honorific == ""
    from capabilities.business_cards import chart

    people, _, _ = store.chart_data("範例科技", include_left=False)
    labels = set(chart._tree(people).children)
    assert {"研展處 I", "研展處 II"} <= labels


def test_the_unified_business_number_is_always_its_own_field(tmp_path: Path) -> None:
    """Card B put 統一編號 in notes, card A did not: it is company_tax_id now."""
    store = _store(tmp_path)
    b = _add(store, {**CARD, "notes": "統一編號：12345678；週五休"})
    view = store.view(b.person_id)
    assert (view.company_tax_id, view.notes) == ("12345678", "週五休")
    a = _add(
        store,
        {"name": "陳一", "company": "範例科技", "company_tax_id": "12345678", "notes": ""},
    )
    assert store.view(a.person_id).company_tax_id == "12345678"
    c = _add(store, {"name": "陳二", "company": "範例科技", "notes": "統編 87654321"})
    assert (store.view(c.person_id).company_tax_id, store.view(c.person_id).notes) == (
        "87654321",
        "",
    )


def test_an_older_store_gains_the_new_columns(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with sqlite3.connect(store.path) as con:
        con.execute("ALTER TABLE people DROP COLUMN honorific")
        con.execute("ALTER TABLE people DROP COLUMN company_tax_id")
    reopened = _store(tmp_path)
    added = _add(reopened, {**CARD, "title": "經理 博士", "company_tax_id": "12345678"})
    view = reopened.view(added.person_id)
    assert (view.honorific, view.company_tax_id) == ("博士", "12345678")


IMAGE = "sha256:" + "ab" * 32


def test_the_same_card_image_finds_the_person_it_was_stored_as(tmp_path: Path) -> None:
    """Live test 2026-10-20: re-sending card A created a second person, because
    the reading misread the email and did not flag it. The image's hash was the
    same as before: the same image is the same person."""
    store = _store(tmp_path)
    first = _add(store, CARD, ref=IMAGE)
    misread = _add(
        store, {**CARD, "email": "hm.wamg@example.com"}, when=date(2026, 2, 1), ref=IMAGE
    )
    assert misread.person_id == first.person_id and misread.matched_by == "image"
    view = store.view(first.person_id)
    assert view.email == CARD["email"]  # the stored email is kept
    assert "email" in misread.needs_confirmation and "email" in view.needs_confirmation
    assert misread.email_differs is not None
    assert (misread.email_differs.stored, misread.email_differs.read) == (
        CARD["email"],
        "hm.wamg@example.com",
    )
    assert "Email" in misread.summary and "hm.wamg@example.com" in misread.summary
    history = store.history(PersonRef(person_id=first.person_id), limit=50)
    assert [(p.field, p.proposed) for p in history.proposals] == [("email", "hm.wamg@example.com")]
    people, total = store.list_people(company="範例科技", source="", status="any", limit=50)
    assert total == 1


def test_the_same_name_and_company_with_another_email_updates_the_person(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = _add(store, CARD)
    again = _add(
        store,
        {**CARD, "email": "hm.wang2@example.com", "title": "協理"},
        when=date(2026, 3, 1),
    )
    assert again.person_id == first.person_id and again.matched_by == "name_company"
    view = store.view(first.person_id)
    assert view.email == CARD["email"] and view.title == "協理"
    assert again.needs_confirmation == ("email",)
    assert again.email_differs is not None and again.email_differs.read == "hm.wang2@example.com"
    assert {k.field: k.reason for k in again.kept} == {"email": "email_differs"}
    # A stored email the person set or confirmed is theirs: kept, and the
    # reading is a proposal that needs confirmation (third live test
    # 2026-10-20: without the flag 「email 正確」 found nothing to confirm).
    store.edit(PersonRef(person_id=first.person_id), {}, actor="a", reason="", confirm=("email",))
    third = _add(store, {**CARD, "email": "hm.wang3@example.com"}, when=date(2026, 4, 1))
    assert third.person_id == first.person_id
    assert third.needs_confirmation == ("email",)
    assert [p.proposed for p in third.proposals] == ["hm.wang3@example.com"]
    assert {k.field: k.reason for k in third.kept} == {"email": "user_set"}
    assert store.view(first.person_id).email == CARD["email"]


def test_namesakes_in_another_department_with_another_email_stay_apart(
    tmp_path: Path,
) -> None:
    """The limit of the rule: two people with the same name at the same company
    are told apart only by a different email and a different department (or
    division). Same name, same company, same department, different email is
    taken to be one person whose email needs confirmation."""
    store = _store(tmp_path)
    one = _add(store, CARD)
    two = _add(
        store,
        {**CARD, "email": "hm.wang@lab.example.com", "department": "天線部", "phone": ""},
    )
    assert two.outcome == "created" and two.person_id != one.person_id
    other_division = _add(
        store,
        {"name": "王小明", "company": "範例科技", "division": "業務處", "email": "w3@example.com"},
    )
    assert other_division.outcome == "created"
    assert store.view(one.person_id).needs_confirmation == ()
    from capabilities.business_cards.manifest import PROCEDURE

    assert "email_differs" in PROCEDURE


def test_the_unified_business_number_is_found_wherever_the_reading_put_it() -> None:
    """Live re-test 2026-10-20: card A's 統一編號 was printed but not stored.
    The Host also finds it in the address and in other printed text."""
    from capabilities.business_cards import reading

    moved = reading.tidy({"address": "新竹市科學園區 統一編號：12345678", "company_tax_id": ""})
    assert (moved["company_tax_id"], moved["address"]) == ("12345678", "新竹市科學園區")
    assert reading.tax_id_in("Tel 03-1234567\n統編 87654321\nISO 9001") == "87654321"
    assert reading.tax_id_in("統一編號：１２３４５６７８") == "12345678"  # full-width digits
    assert reading.tax_id_in("Tel 03-12345678") == ""


def test_a_stored_note_with_the_unified_business_number_is_moved_with_history(
    tmp_path: Path,
) -> None:
    """Live re-test 2026-10-20: after company_tax_id was set, the old
    「統一編號：…」 note stayed in notes."""
    store = _store(tmp_path)
    old = _add(store, CARD)
    with sqlite3.connect(store.path) as con:  # a note stored before the field existed
        con.execute(
            "UPDATE people SET notes = ? WHERE person_id = ?",
            ("統一編號：12345678；週五休", old.person_id),
        )
    again = _add(store, {**CARD, "company_tax_id": "12345678"}, when=date(2026, 2, 1))
    view = store.view(old.person_id)
    assert (view.company_tax_id, view.notes) == ("12345678", "週五休")
    assert ("notes", "統一編號：12345678；週五休", "週五休") in {
        (c.field, c.old, c.new) for c in again.changes
    }
    history = store.history(PersonRef(person_id=old.person_id), limit=50).history
    moved = [item for item in history if item.field == "notes"]
    assert moved and "company_tax_id" in moved[0].reason


def test_a_shorter_reading_never_replaces_a_more_complete_value(tmp_path: Path) -> None:
    """Live re-test 2026-10-20: a re-scan replaced "Connectivity & Solutions
    事業群" with "Connectivity & Solutions". An automatic reading that is a
    strict prefix or substring of the stored value leaves it as it is."""
    store = _store(tmp_path)
    group = "Connectivity & Solutions 事業群"
    base = {**CARD, "business_group": group, "division": "研展處 I"}
    first = _add(store, base)
    again = _add(
        store,
        {**CARD, "business_group": "Connectivity & Solutions", "division": "研展處"},
        when=date(2026, 5, 1),
    )
    view = store.view(first.person_id)
    assert (view.business_group, view.division) == (group, "研展處 I")
    assert again.outcome == "unchanged" and again.changes == ()
    assert {k.field: k.reason for k in again.kept} == {
        "business_group": "less_complete",
        "division": "less_complete",
    }
    assert "現在是" not in again.summary
    # A more complete reading still fills it in.
    longer = _add(store, {**base, "department": "射頻部 一課"}, when=date(2026, 6, 1))
    assert [(c.field, c.new) for c in longer.changes] == [("department", "射頻部 一課")]
    # A title is not held back: 總經理 after 副總經理 is a promotion.
    promoted = _add(store, {**base, "title": "副總經理"}, when=date(2026, 7, 1))
    assert promoted.changes
    topped = _add(store, {**base, "title": "總經理"}, when=date(2026, 8, 1))
    assert [(c.field, c.new) for c in topped.changes] == [("title", "總經理")]


def test_a_business_group_the_person_set_is_never_overwritten(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = _add(store, CARD)
    store.edit(
        PersonRef(person_id=first.person_id),
        {"business_group": "C&S 事業群"},
        actor="a",
        reason="",
    )
    later = _add(
        store, {**CARD, "business_group": "Connectivity & Solutions 事業群"}, when=date(2026, 9, 1)
    )
    assert store.view(first.person_id).business_group == "C&S 事業群"
    assert {k.field: k.reason for k in later.kept} == {"business_group": "user_set"}


def _wnc(store: CardStore) -> None:
    _add(
        store,
        {
            "name": "王則閔",
            "company": "啟碁科技股份有限公司",
            "department": "研展三部",
            "title": "資深經理",
            "email": "ze.wang@wnc.com.tw",
        },
    )
    _add(
        store,
        {"name": "Ann Li", "company": "WNC", "title": "Engineer", "email": "ann.li@wnc.com.tw"},
        source="email_signature",
        ref="<m1>",
    )
    _add(store, {"name": "陳範", "company": "範例網通", "email": "chen@gmail.com"})
    _add(store, {"name": "林範", "company": "其他科技", "email": "lin@gmail.com"})


@pytest.mark.parametrize("query", ["WNC", "wnc", "啟碁", "啟碁科技", "啟碁科技股份有限公司"])
def test_a_company_is_found_by_its_name_alias_or_domain(tmp_path: Path, query: str) -> None:
    """Live re-test 2026-10-20: "WNC" found the company once and not the next
    time. A company query resolves against the stored companies: the name
    without legal suffixes, an alias from the website or email domain
    (wnc.com.tw -> WNC) or a romanised short name, or an unambiguous part."""
    store = _store(tmp_path)
    _wnc(store)
    assert store.resolve_company(query) == "啟碁科技股份有限公司"
    people, _, _ = store.chart_data(query, include_left=False)
    assert {p["name"] for p in people} == {"王則閔", "Ann Li"}
    listed, total = store.list_people(company=query, source="", status="any", limit=10)
    assert total == 2
    found, count = store.find(query, status="any", limit=10)
    assert {p.name for p in found} == {"王則閔", "Ann Li"} and count == 2


def test_a_shared_mail_domain_or_an_ambiguous_part_is_no_company(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _wnc(store)
    # gmail.com is no company: 範例網通 and 其他科技 stay apart.
    assert store.resolve_company("gmail") == ""
    assert store.resolve_company("範例網通") == "範例網通"
    # "科技" is part of two companies: not resolved.
    assert store.resolve_company("科技") == ""
    assert store.resolve_company("Unknown Corp") == ""
    # A common word in two English names is no alias.
    _add(store, {"name": "Bo", "company": "Foo Technology Inc.", "email": "bo@footech.com"})
    _add(store, {"name": "Cy", "company": "Bar Technology Ltd", "email": "cy@bartech.com"})
    assert store.resolve_company("Foo Technology") == "Foo Technology Inc."
    assert store.resolve_company("foo") == "Foo Technology Inc."
    assert store.resolve_company("technology") == ""


def test_the_summary_never_reports_a_change_that_did_not_happen(tmp_path: Path) -> None:
    """Live re-test 2026-10-20: 「上次是研展三部資深經理，現在是研展三部資深經理」.
    When the department and title stay, the summary names the field that
    changed; values are named by their Chinese labels."""
    store = _store(tmp_path)
    first = _add(store, {**CARD, "title": "資深經理", "department": "研展三部"})
    moved = _add(
        store,
        {**CARD, "title": "資深經理", "department": "研展三部", "business_group": "寬頻事業群"},
        when=date(2026, 2, 1),
    )
    assert moved.person_id == first.person_id
    assert "現在是研展三部資深經理" not in moved.summary
    assert "事業群：上次是網通事業群，現在是寬頻事業群" in moved.summary
    assert [(c.field, c.label) for c in moved.changes] == [("business_group", "事業群")]


def test_a_result_names_fields_in_chinese_and_states_what_is_stored(tmp_path: Path) -> None:
    """Live re-test 2026-10-20: replies showed `romanised_name`, and asked
    「是否要保持空白？」 about a field that held "Clark Wang"."""
    store = _store(tmp_path)
    first = _add(store, {**CARD, "romanised_name": "Clark Wang"}, uncertain=("romanised_name",))
    assert [(item.field, item.label, item.stored) for item in first.to_confirm] == [
        ("romanised_name", "英文名", "Clark Wang")
    ]
    kept = _add(
        store,
        {**CARD, "romanised_name": "Clark Wong"},
        when=date(2026, 2, 1),
        uncertain=("romanised_name",),
    )
    assert [(k.field, k.label) for k in kept.kept] == [("romanised_name", "英文名")]


def test_a_chart_card_shows_the_desk_phone_first_and_the_honorific_with_the_name(
    tmp_path: Path,
) -> None:
    """Live re-test 2026-10-20: the box showed the mobile instead of the desk
    phone and extension, and left out 博士."""
    from capabilities.business_cards import chart

    store = _store(tmp_path)
    added = _add(
        store,
        {
            "name": "王則閔",
            "company": "範例科技",
            "title": "資深經理 博士",
            "phone": "03-123-4567",
            "ext": "1234",
            "mobile": "0912-000-111",
            "email": "zm.wang@example.com",
        },
        uncertain=("email",),
    )
    people, _, _ = store.chart_data("範例科技", include_left=False)
    needs = store.uncertain_now([added.person_id])
    lines = chart.card_lines(people[0], needs.get(added.person_id, []))
    assert lines == [
        "王則閔 博士",
        "資深經理",
        "03-123-4567 #1234",
        "手機 0912-000-111",
        "需確認：Email",
    ]
    only_mobile = dict(people[0])
    only_mobile.update(phone="", ext="", honorific="")
    assert chart.card_lines(only_mobile, []) == ["王則閔", "資深經理", "手機 0912-000-111"]
    # The legend lists who needs confirmation, fields in Chinese.
    text = chart.legend("範例科技", people, [], include_left=False, left_omitted=0, uncertain=needs)
    assert "需確認" in text and "王則閔 博士：Email" in text
    chart.render(tmp_path / "c.png", "範例科技", people, [], uncertain=needs)
    assert (tmp_path / "c.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_number_that_differs_only_in_formatting_is_not_a_change(tmp_path: Path) -> None:
    """Third live test 2026-10-20: a re-scan read "(03) 666 7799" for the stored
    "(03) 666-7799"; the history logged a change and the reply said 電話、傳真也
    更新了, and each re-scan could flip the format back. Phone, fax and mobile
    compare by digits and extension; +886 is a leading 0."""
    store = _store(tmp_path)
    numbers = {"phone": "(03) 666-7799", "fax": "(03) 666-7799", "mobile": "0912-345-678"}
    first = _add(store, {**CARD, **numbers})
    again = _add(
        store,
        {
            **CARD,
            "phone": "(03) 666 7799",
            "fax": "03.666.7799",
            "mobile": "+886 912 345 678",
        },
        when=date(2026, 3, 1),
    )
    assert again.outcome == "unchanged" and again.changes == ()
    assert again.kept == () and "更新" not in again.summary
    view = store.view(first.person_id)
    assert (view.phone, view.fax, view.mobile) == ("(03) 666-7799", "(03) 666-7799", "0912-345-678")
    history = store.history(PersonRef(person_id=first.person_id), limit=50)
    assert not [item for item in history.history if item.kind == "field"]
    # The extension counts: another extension is another number.
    moved = _add(store, {**CARD, **numbers, "phone": "(03) 666-7799 #12"}, when=date(2026, 4, 1))
    assert [c.field for c in moved.changes] == ["phone"]
    # A real change is still a change.
    other = _add(store, {**CARD, **numbers, "fax": "(03) 666-7700"}, when=date(2026, 5, 1))
    assert [c.field for c in other.changes] == ["fax"]


def test_the_phone_key_ignores_formatting() -> None:
    from capabilities.business_cards.names import phone_key

    assert phone_key("(03) 666-7799") == phone_key("03 666 7799") == phone_key("03.666.7799")
    assert phone_key("+886 3 666 7799") == phone_key("+886 (0)3 666-7799") == "036667799"
    assert phone_key("02-2345-6789 ext. 312") == phone_key("(02) 2345 6789 #312")
    assert phone_key("02-2345-6789 分機 312") == "0223456789#312"
    assert phone_key("02-2345-6789") != phone_key("02-2345-6789 #312")
    assert phone_key("call the desk") == ""


def test_a_reading_that_differs_from_a_confirmed_email_needs_confirmation(
    tmp_path: Path,
) -> None:
    """Third live test 2026-10-20: a re-scan read another email than the one the
    person had confirmed; the reply asked which was right, but there was no
    proposal and no 需確認, so 「X 的 email 正確」 found nothing to confirm."""
    store = _store(tmp_path)
    first = _add(store, CARD, ref=IMAGE)
    store.edit(
        PersonRef(person_id=first.person_id), {}, actor="alice", reason="", confirm=["email"]
    )
    assert store.view(first.person_id).needs_confirmation == ()
    misread = _add(
        store,
        {**CARD, "email": "hm.wamg@example.com"},
        when=date(2026, 2, 1),
        ref=IMAGE,
        uncertain=("email",),
    )
    assert store.view(first.person_id).email == CARD["email"]
    assert "email" in misread.needs_confirmation
    assert [(p.field, p.current, p.proposed, p.observation_id) for p in misread.proposals] == [
        ("email", CARD["email"], "hm.wamg@example.com", misread.observation_id)
    ]
    assert "hm.wamg@example.com" in misread.summary and "請確認" in misread.summary
    assert store.uncertain_now([first.person_id]) == {first.person_id: ["email"]}
    # The same reading again does not open a second proposal.
    _add(store, {**CARD, "email": "hm.wamg@example.com"}, when=date(2026, 2, 2), ref=IMAGE)
    listed, note = store.proposals(None, limit=50)
    assert [(p.name, p.field, p.label) for p in listed] == [("王小明", "email", "Email")]
    assert "王小明" in note and "hm.wamg@example.com" in note and CARD["email"] in note
    # 「王小明 的 email 正確」: the stored one stays, the proposal is rejected,
    # and a confirm row is written.
    row, changes, confirmed, change_id = store.edit(
        PersonRef(name="王小明"), {}, actor="alice via telegram", reason="", confirm=["email"]
    )
    assert confirmed == ["email"] and changes == [] and change_id is not None
    assert row["email"] == CARD["email"]
    assert store.view(first.person_id).needs_confirmation == ()
    assert store.proposals(None, limit=50) == ([], "目前沒有待確認的項目。")
    history = store.history(PersonRef(person_id=first.person_id), limit=50)
    confirms = [item for item in history.history if item.change_id == change_id]
    assert [(i.kind, i.field, i.actor) for i in confirms] == [
        ("confirm", "email", "alice via telegram")
    ]
    with sqlite3.connect(store.path) as con:
        states = [state for (state,) in con.execute("SELECT state FROM proposals")]
    assert states == ["rejected"]
    # Undoing the confirmation opens the proposal again.
    store.undo(change_id, actor="alice")
    assert "email" in store.view(first.person_id).needs_confirmation
    assert len(store.proposals(None, limit=50)[0]) == 1


def test_any_field_read_differently_from_the_persons_own_value_needs_confirmation(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = _add(store, CARD)
    store.edit(PersonRef(person_id=first.person_id), {"title": "資深經理"}, actor="a", reason="")
    later = _add(store, {**CARD, "title": "協理"}, when=date(2026, 3, 1))
    assert {k.field: k.reason for k in later.kept} == {"title": "user_set"}
    assert later.needs_confirmation == ("title",)
    assert [(p.field, p.current, p.proposed) for p in later.proposals] == [
        ("title", "資深經理", "協理")
    ]
    # 「用新的」: the proposal is accepted and becomes the person's value.
    row, changes, confirmed, change_id = store.edit(
        PersonRef(person_id=first.person_id), {}, actor="a", reason="", accept=["title"]
    )
    assert row["title"] == "協理" and [(c.field, c.new) for c in changes] == [("title", "協理")]
    assert store.view(first.person_id).needs_confirmation == ()
    with sqlite3.connect(store.path) as con:
        states = [state for (state,) in con.execute("SELECT state FROM proposals")]
    assert states == ["accepted"]
    history = store.history(PersonRef(person_id=first.person_id), limit=50)
    assert [(i.kind, i.field, i.new) for i in history.history if i.change_id == change_id] == [
        ("field", "title", "協理")
    ]
    # Undo puts the old value back and opens the proposal again.
    store.undo(change_id, actor="a")
    assert store.view(first.person_id).title == "資深經理"
    assert store.view(first.person_id).needs_confirmation == ("title",)
    # Answering with the other value accepts the proposal too.
    store.edit(PersonRef(person_id=first.person_id), {"title": "協理"}, actor="a", reason="")
    with sqlite3.connect(store.path) as con:
        states = [state for (state,) in con.execute("SELECT state FROM proposals")]
    assert states == ["accepted"]
    assert store.view(first.person_id).needs_confirmation == ()
    with pytest.raises(CardStoreError) as refused:
        store.edit(PersonRef(person_id=first.person_id), {}, actor="a", reason="", accept=["fax"])
    assert refused.value.code == "proposal_unknown"
