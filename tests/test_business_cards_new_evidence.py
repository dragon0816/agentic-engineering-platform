"""New evidence updates organisational fields directly; email stays a proposal
(owner 2026-10-20: 「換部門, 或換職位, 就修改那一筆資料」).

- New evidence: a card image never observed for that person before (cards
  carry no evidence date), or an email signature sent after the day of the
  person's last change to the field. Old evidence (a re-scan of a seen
  image, a card without an image, an older or same-day signature) never
  changes or challenges a value the person set: ignored silently.
- New evidence updates title, department, division, business group,
  honorific, phone / ext / mobile / fax and address directly, with history,
  undoable, even over the person's own value. The email, the identity key,
  is never overwritten by a reading: a differing one is a 需確認 proposal.
- The one-time cleanup dismisses open proposals that came from old evidence,
  with history rows, undoable; it also runs on data moved from `cards.db`.

Synthetic data only.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from test_business_cards_migration import ACTOR, CARD_ID, STAMP, WANG, WHO, _legacy

from capabilities.business_cards.contracts import PersonRef
from capabilities.business_cards.space import CONTACTS_ORG
from capabilities.business_cards.store import (
    NEWER_RULE_MARKER,
    NEWER_RULE_REASON,
    CardStore,
    store_dir,
)

CARD = {
    "name": "范仁杰",
    "company": "範例網通",
    "division": "研展處 I",
    "department": "研展一部",
    "title": "經理",
    "email": "rj.fan@example.com",
}
OLD_CARD = "sha256:" + "11" * 32
NEW_CARD = "sha256:" + "22" * 32
TODAY = date.today()


def _store(tmp_path: Path) -> CardStore:
    return CardStore.for_actor(tmp_path, "alice")


def _add(
    store: CardStore,
    values: dict[str, str],
    *,
    source: Any = "card",
    when: date = date(2026, 1, 10),
    ref: str = "",
) -> Any:
    return store.add(
        values, source=source, source_date=when, source_ref=ref, uncertain=(), actor="alice"
    )


def _person_with_own_place(store: CardStore) -> str:
    first = _add(store, CARD, ref=OLD_CARD)
    store.edit(
        PersonRef(person_id=first.person_id),
        {"department": "研展三部", "title": "資深經理"},
        actor="a",
        reason="",
    )
    return str(first.person_id)


def test_a_new_card_updates_the_place_directly_and_a_rescan_never_does(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _person_with_own_place(store)
    # The old card again, filed under any date: nothing changes, nothing is said.
    for when in (date(2020, 1, 1), TODAY, TODAY + timedelta(days=400)):
        rescan = _add(
            store, {**CARD, "department": "研展一部", "title": "經理"}, when=when, ref=OLD_CARD
        )
        assert (rescan.changes, rescan.kept, rescan.proposals) == ((), (), ())
        assert rescan.matched_by == "image"
    # A card without an image has no identity: never new evidence.
    plain = _add(store, {**CARD, "department": "研展五部"}, when=date(2031, 1, 1))
    assert (plain.changes, plain.kept, plain.proposals) == ((), (), ())
    assert store.view(person).department == "研展三部"
    # A new card printed 「研展二部」 and a new title: updated directly, even
    # filed under an old date (a card's date is never compared).
    new = _add(
        store,
        {**CARD, "department": "研展二部", "title": "副理"},
        when=date(2020, 1, 1),
        ref=NEW_CARD,
    )
    assert {(c.field, c.old, c.new) for c in new.changes} == {
        ("department", "研展三部", "研展二部"),
        ("title", "資深經理", "副理"),
    }
    assert new.proposals == () and new.kept == ()
    assert "上次是" in new.summary and "現在是" in new.summary
    view = store.view(person)
    assert (view.department, view.title) == ("研展二部", "副理")
    history = store.history(PersonRef(person_id=person), limit=50)
    rows = [i for i in history.history if i.change_id == new.change_id and i.kind == "field"]
    assert {(i.field, i.reason) for i in rows} == {
        ("department", f"new card {NEW_CARD}"),
        ("title", f"new card {NEW_CARD}"),
    }
    # Undoable: the person's own values are back, and theirs again.
    store.undo(new.change_id, actor="a")
    view = store.view(person)
    assert (view.department, view.title) == ("研展三部", "資深經理")
    rescan = _add(store, {**CARD, "department": "研展一部"}, when=TODAY, ref=OLD_CARD)
    assert rescan.changes == ()


def test_a_new_card_with_another_email_is_a_proposal_not_an_overwrite(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _person_with_own_place(store)
    store.edit(PersonRef(person_id=person), {}, actor="a", reason="", confirm=["email"])
    new = _add(
        store,
        # The same place: another email and another place would be a namesake.
        {**CARD, "email": "rj.fam@example.com", "department": "研展三部", "title": "副理"},
        ref=NEW_CARD,
    )
    assert store.view(person).email == CARD["email"]
    assert [(p.field, p.current, p.proposed) for p in new.proposals] == [
        ("email", CARD["email"], "rj.fam@example.com")
    ]
    assert store.view(person).title == "副理"  # the place still updates
    # Not confirmed by the person: the same holds (never overwritten, 需確認).
    other = _store(tmp_path / "b")
    first = _add(other, CARD, ref=OLD_CARD)
    again = _add(other, {**CARD, "email": "rj.fam@example.com"}, ref=NEW_CARD)
    assert other.view(first.person_id).email == CARD["email"]
    assert "email" in again.needs_confirmation and again.email_differs is not None


def test_a_signature_counts_only_when_sent_after_the_persons_change(tmp_path: Path) -> None:
    store = _store(tmp_path)
    person = _person_with_own_place(store)

    def signature(sent: date, title: str, email: str = CARD["email"]) -> Any:
        return _add(
            store,
            {"name": CARD["name"], "company": CARD["company"], "email": email, "title": title},
            source="email_signature",
            when=sent,
            ref=f"<{sent}-{title}-{email}>",
        )

    for sent in (TODAY - timedelta(days=30), TODAY):  # older, and the same day
        old = signature(sent, "經理")
        assert (old.changes, old.kept, old.proposals) == ((), (), ())
    assert store.view(person).title == "資深經理"
    newer = signature(TODAY + timedelta(days=1), "協理")
    assert [(c.field, c.old, c.new) for c in newer.changes] == [("title", "資深經理", "協理")]
    assert store.view(person).title == "協理"
    # An email the person set: an older signature is ignored, a newer one
    # with another email is a proposal, never an overwrite.
    store.edit(PersonRef(person_id=person), {}, actor="a", reason="", confirm=["email"])
    old_mail = signature(TODAY - timedelta(days=1), "協理", "rj.fan2@example.com")
    assert old_mail.email_differs is None and old_mail.proposals == ()
    new_mail = signature(TODAY + timedelta(days=2), "協理", "rj.fan2@example.com")
    assert [(p.field, p.proposed) for p in new_mail.proposals] == [("email", "rj.fan2@example.com")]
    assert store.view(person).email == CARD["email"]


def _propose_directly(
    store: CardStore, person: str, *, kind: str, ref: str, when: str, value: str
) -> None:
    """An open proposal as the earlier rule (any differing evidence) left it."""
    with store._space.transaction() as tx:
        observed = tx.add_observation(
            person,
            {"department": value},
            source_kind=kind,
            source_date=when,
            source_ref=ref,
            recorded_by=WHO,
        )
        tx.propose(
            "c-old-rule",
            WHO,
            person,
            "department",
            "研展三部",
            value,
            source_kind=kind,
            observation_id=observed,
        )


def test_the_cleanup_dismisses_only_what_the_rule_would_not_propose_and_is_undoable(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    person = _person_with_own_place(store)
    later = (TODAY + timedelta(days=2)).isoformat()
    _propose_directly(store, person, kind="card", ref=OLD_CARD, when="2026-01-10", value="研展處")
    _propose_directly(
        store, person, kind="email_signature", ref="<a>", when="2026-01-01", value="A"
    )
    _propose_directly(
        store, person, kind="email_signature", ref="<b>", when=TODAY.isoformat(), value="B"
    )
    _propose_directly(store, person, kind="card", ref=NEW_CARD, when="2020-01-01", value="新卡")
    _propose_directly(store, person, kind="email_signature", ref="<c>", when=later, value="新信")
    # The cleanup ran when the store was first opened; run it as on a first start.
    with sqlite3.connect(store.path) as con:
        con.execute("DELETE FROM meta WHERE key = ?", (NEWER_RULE_MARKER,))
    reopened = _store(tmp_path)
    open_now = sorted(p.proposed for p in reopened.proposals(None, limit=50)[0])
    assert open_now == ["新信", "新卡"]
    with sqlite3.connect(reopened.path) as con:
        con.row_factory = sqlite3.Row
        marker = json.loads(
            con.execute("SELECT value FROM meta WHERE key = ?", (NEWER_RULE_MARKER,)).fetchone()[0]
        )
        rows = list(
            con.execute(
                "SELECT * FROM history WHERE space = ? AND kind = 'proposal_rule' "
                "ORDER BY history_id",
                (CONTACTS_ORG,),
            )
        )
    assert marker["dismissed"] == 3
    assert sorted(row["new"] for row in rows) == ["A", "B", "研展處"]
    assert {row["reason"] for row in rows} == {NEWER_RULE_REASON}
    assert {row["change_id"] for row in rows} == {marker["change_id"]}
    # Once only: opening again changes nothing.
    assert len(_store(tmp_path).proposals(None, limit=50)[0]) == 2
    # Undoable through the normal undo path.
    reverted, _ = reopened.undo(marker["change_id"], actor="alice via web")
    assert len(reverted) == 3
    assert len(reopened.proposals(None, limit=50)[0]) == 5
    assert len(_store(tmp_path).proposals(None, limit=50)[0]) == 5  # not dismissed again


def test_the_cleanup_covers_data_moved_from_cards_db(tmp_path: Path) -> None:
    """A re-scan of the same card in the old store left a proposal against the
    person's title; the migration on first start brings it over and the
    cleanup dismisses it. The fixture's signature proposal (newer than the
    person's change) stays open."""
    legacy = _legacy(tmp_path)
    with sqlite3.connect(legacy) as con:
        con.execute(
            "INSERT INTO observations (observation_id, person_id, source, source_date, "
            "source_ref, fields_json, uncertain_json, recorded_at, recorded_by) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                9,
                "p-wang",
                "card",
                "2026-10-01",
                CARD_ID,
                json.dumps({**WANG, "title": "經理"}, ensure_ascii=False),
                "[]",
                STAMP,
                WHO,
            ),
        )
        con.execute(
            "INSERT INTO proposals (proposal_id, person_id, field, current, proposed, source, "
            "observation_id, created_at, state) VALUES (?,?,?,?,?,?,?,?,?)",
            (9, "p-wang", "title", "協理", "經理", "card", 9, STAMP, "open"),
        )
    assert (store_dir(tmp_path, ACTOR) / "cards.db").exists()
    store = CardStore.for_actor(tmp_path, ACTOR)
    found, _ = store.proposals(None, limit=10)
    assert [(p.field, p.proposed) for p in found] == [("title", "副總")]
