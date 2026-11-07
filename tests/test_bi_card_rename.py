"""A card's id never changes; a rename keeps it (`docs/phases/BI_CARD_MODEL.md` §3.1).

All data is fictional.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _card, _commit, _ok, _push, _row, _sync, _two_pcs

from capabilities.bi_cards import catalog, quality, vault
from capabilities.bi_cards.store import BiStore, card_id_for

TECH = "Technology"


def _make(ws: Path, dataset: str, key: str, **values: Any) -> str:
    BiStore(ws, dataset).apply(
        [_row(key, **values)], filename="t.csv", entity_type=TECH, actor="alice"
    )
    return str(_card(ws, dataset, key)["id"])


def _rename(
    ws: Path, dataset: str, key: str, name: str, **extra: Any
) -> tuple[int, dict[str, Any]]:
    card = _card(ws, dataset, key)
    answer: tuple[int, dict[str, Any]] = _call(
        ws,
        "POST",
        f"/api/bi/cards/{card['id']}/rename",
        {
            "dataset": dataset,
            "name": name,
            "base_version": card["version"],
            "reason": "the vendor renamed it",
            **extra,
        },
    )
    return answer


def _csv(ws: Path, dataset: str, name: str, extra: str = "") -> dict[str, Any]:
    header = "名稱" + (",說明" if extra else "")
    given = {
        "dataset": dataset,
        "csv_text": f"{header}\n{name}{',' + extra if extra else ''}\n",
        "entity_type": TECH,
    }
    prepared = _ok(_call(ws, "POST", "/api/bi/import/preview", given))
    _ok(_call(ws, "POST", "/api/bi/import/apply", {"preview_id": prepared["preview_id"]}))
    return prepared


def _quality(ws: Path, dataset: str) -> dict[str, Any]:
    store = BiStore(ws, dataset)
    return quality.check(store, catalog.for_store(store))


def _tables(ws: Path, dataset: str) -> dict[str, list[tuple[Any, ...]]]:
    with closing(sqlite3.connect(BiStore(ws, dataset).path)) as db:
        return {
            table: sorted(db.execute(f"SELECT {columns} FROM {table}").fetchall(), key=repr)
            for table, columns in (
                ("cards", "id, entity_type, canonical_key, name, synthetic"),
                ("fields", "card_id, field, value"),
                ("card_names", "card_id, name, kind"),
            )
        }


def test_a_rename_keeps_the_id_and_every_pc_sees_it(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    cid = _make(a, dataset, "FAKE-OLD")
    assert cid == card_id_for(TECH, "FAKE-OLD")
    _push(a, vault_id)

    _ok(_rename(a, dataset, "FAKE-OLD", "FAKE-NEW"))
    card = _card(a, dataset, "FAKE-NEW")
    assert card["id"] == cid
    assert BiStore(a, dataset).find(TECH, "FAKE-OLD") is None
    assert card["fields"]["name"]["value"] == "FAKE-NEW"
    assert "FAKE-OLD" in card["fields"]["aliases"]["value"]
    unit = vault.Vault(a, vault_id).repo.working_units()[f"card:{cid}"]
    assert unit["key"] == "FAKE-NEW" and unit["former_keys"] == ["FAKE-OLD"]

    _commit(a, vault_id, "Rename a fictional card")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _card(b, dataset, "FAKE-NEW")["id"] == cid
    assert _tables(a, dataset) == _tables(b, dataset)
    history = BiStore(b, dataset).history(cid)
    assert any(h["reason"] == "the vendor renamed it" for h in history)


def test_nothing_else_is_staged_and_a_rebuild_reads_back_the_same_units(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _make(a, dataset, "FAKE-OLD")
    _make(a, dataset, "FAKE-OTHER")
    _push(a, vault_id)
    _ok(_rename(a, dataset, "FAKE-OLD", "FAKE-NEW"))
    target = vault.Vault(a, vault_id)
    cid = card_id_for(TECH, "FAKE-OLD")
    staged = set(target.repo._pending()["sets"])
    assert staged == {f"card:{cid}", f"field:{cid}:name", f"field:{cid}:aliases"}

    target.rebuild()
    with closing(sqlite3.connect(target.db_path)) as db:
        read = vault.units_from_db(db, keep_ids=True)
    working = target.repo.working_units()
    for key in read:
        if key.startswith("card:"):
            assert read[key] == working[key], key


def test_the_old_name_lands_on_the_same_card(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    cid = _make(a, dataset, "FAKE-OLD")
    _ok(_rename(a, dataset, "FAKE-OLD", "FAKE-NEW"))
    _commit(a, vault_id, "Rename a fictional card")
    prepared = _csv(a, dataset, "FAKE-OLD")
    assert prepared["summary"]["create"] == 0
    store = BiStore(a, dataset)
    assert store.find(TECH, "FAKE-OLD") is None
    found = store.find(TECH, "FAKE-NEW")
    assert found is not None and found["id"] == cid
    assert len(store.card_rows()) == 1


def test_a_name_in_use_is_refused(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _make(a, dataset, "FAKE-A")
    _make(a, dataset, "FAKE-B")
    _make(a, dataset, "FAKE-C")
    status, body = _rename(a, dataset, "FAKE-A", "FAKE-B")
    assert (status, body["code"]) == (409, "name_taken")
    # A former name stays reserved for its card.
    _ok(_rename(a, dataset, "FAKE-A", "FAKE-A2"))
    status, body = _rename(a, dataset, "FAKE-C", "FAKE-A")
    assert (status, body["code"]) == (409, "name_taken")
    # But that card may take it back.
    _ok(_rename(a, dataset, "FAKE-A2", "FAKE-A"))
    assert _card(a, dataset, "FAKE-A")["id"] == card_id_for(TECH, "FAKE-A")


def test_a_rename_needs_a_reason_a_current_version_and_a_vault(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _make(a, dataset, "FAKE-A")
    status, body = _rename(a, dataset, "FAKE-A", "FAKE-B", reason=" ")
    assert (status, body["code"]) == (400, "reason_required")
    status, body = _rename(a, dataset, "FAKE-A", "FAKE-B", base_version=99)
    assert (status, body["code"]) == (409, "stale_edit")
    # The same name again changes nothing.
    before = _card(a, dataset, "FAKE-A")["version"]
    assert _ok(_rename(a, dataset, "FAKE-A", "FAKE-A"))["version"] == before

    local = BiStore(tmp_path / "ws", "lab")
    local.apply([_row("FAKE-L")], filename="t.csv", entity_type=TECH, actor="x")
    status, body = _rename(tmp_path / "ws", "lab", "FAKE-L", "FAKE-M")
    assert (status, body["code"]) == (400, "rename_vault_only")


def test_a_rename_and_a_new_card_with_that_name_settle_the_same_on_each_pc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A fast CI runner can commit all of this in one second. Keep that case explicit.
    monkeypatch.setattr("knowledge.repo.repository._now", lambda: "2026-11-06T23:59:59+00:00")
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    old = _make(a, dataset, "FAKE-X")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)

    _ok(_rename(a, dataset, "FAKE-X", "FAKE-Y"))
    _commit(a, vault_id, "Rename a fictional card")
    new = _make(b, dataset, "FAKE-Y")  # imports commit at once
    _push(b, vault_id)
    drive.deliver("b", "a", vault_id)

    # Pushing what would make two cards of one name is stopped when it can be seen.
    pushed = _push(a, vault_id)
    assert pushed["status"] == "blocked" and "FAKE-Y" in pushed["blocking"][0]

    # When it could not be seen, both reach the folder: the first created keeps the key.
    target = vault.Vault(a, vault_id)
    units = dict(target.repo.working_units())
    assert units[f"card:{old}"]["key"] == units[f"card:{new}"]["key"] == "FAKE-Y"
    kept = BiStore(a, dataset).find(TECH, "FAKE-Y")
    assert kept is not None and kept["id"] == old
    keys = {r["id"]: r["canonical_key"] for r in BiStore(a, dataset).card_rows()}
    assert keys[new] == f"FAKE-Y#{new}"
    report = _quality(a, dataset)
    conflicts = next(c for c in report["checks"] if c["id"] == "key_conflict")
    assert conflicts["count"] == 1

    # A suffix is only how `cards` shows it: the unit reads back without it.
    with closing(sqlite3.connect(target.db_path)) as db:
        read = vault.units_from_db(db, keep_ids=True)
    assert read[f"card:{new}"]["key"] == "FAKE-Y"

    # A person's rename ends it.
    card = BiStore(a, dataset).card(new)
    assert card is not None
    _ok(
        _call(
            a,
            "POST",
            f"/api/bi/cards/{new}/rename",
            {
                "dataset": dataset,
                "name": "FAKE-Z",
                "base_version": card["version"],
                "reason": "two different things",
            },
        )
    )
    settled = BiStore(a, dataset).find(TECH, "FAKE-Z")
    assert settled is not None and settled["id"] == new
    report = _quality(a, dataset)
    assert next(c for c in report["checks"] if c["id"] == "key_conflict")["count"] == 0


def test_a_type_named_by_two_fields_keeps_its_id_and_its_date(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    given = {
        "dataset": dataset,
        "csv_text": "日期,標題,摘要\n2026-01-02,FAKE-T1,fictional\n",
        "entity_type": "Signal",
    }
    prepared = _ok(_call(a, "POST", "/api/bi/import/preview", given))
    _ok(_call(a, "POST", "/api/bi/import/apply", {"preview_id": prepared["preview_id"]}))
    key = next(r["canonical_key"] for r in BiStore(a, dataset).card_rows())
    cid = card_id_for("Signal", key)
    card = BiStore(a, dataset).card(cid)
    assert card is not None
    _ok(
        _call(
            a,
            "POST",
            f"/api/bi/cards/{cid}/rename",
            {
                "dataset": dataset,
                "name": "FAKE-T2",
                "base_version": card["version"],
                "reason": "typo",
            },
        )
    )
    renamed = BiStore(a, dataset).card(cid)
    assert renamed is not None and renamed["name"] == "FAKE-T2"
    assert renamed["canonical_key"] == key.replace("FAKE-T1", "FAKE-T2")
    # The old row again lands on the renamed card, under its current name.
    again = _ok(_call(a, "POST", "/api/bi/import/preview", given))
    _ok(_call(a, "POST", "/api/bi/import/apply", {"preview_id": again["preview_id"]}))
    assert [r["id"] for r in BiStore(a, dataset).card_rows()] == [cid]
    current = BiStore(a, dataset).card(cid)
    assert current is not None and current["name"] == "FAKE-T2"


def test_a_materialized_clash_of_keys_is_deterministic() -> None:
    units = {
        "card:bbb": {"type": TECH, "key": "SAME", "name": "SAME", "synthetic": False},
        "card:aaa": {"type": TECH, "key": "SAME", "name": "SAME", "synthetic": False},
    }
    info = {"aaa": {"created": "2026-02-02"}, "bbb": {"created": "2026-01-01"}}
    assert vault._card_keys(units, info) == {"bbb": "SAME", "aaa": "SAME#aaa"}
    # With no dates, the lower id.
    assert vault._card_keys(units, {}) == {"aaa": "SAME", "bbb": "SAME#bbb"}


@pytest.mark.parametrize(
    "second_at",
    ["2026-11-07T07:59:59+08:00", "2026-11-06T23:59:59+00:00"],
    ids=["same-second", "same-instant-other-offset"],
)
def test_equal_creation_times_keep_the_first_replayed_card_in_either_unit_order(
    second_at: str,
) -> None:
    """A fast PC can create both cards in one second; id order is not creation order."""
    units = {
        "card:bbb": {"type": TECH, "key": "SAME", "name": "SAME", "synthetic": False},
        "card:aaa": {"type": TECH, "key": "SAME", "name": "SAME", "synthetic": False},
    }
    entries = [
        {
            "at": "2026-11-07T07:59:59+08:00",
            "group": "first",
            "changes": [{"unit": "card:bbb", "applied": True, "after": units["card:bbb"]}],
        },
        {
            "at": second_at,
            "group": "second",
            "changes": [{"unit": "card:aaa", "applied": True, "after": units["card:aaa"]}],
        },
    ]
    _, info = vault._field_history(entries)
    expected = {"bbb": "SAME", "aaa": "SAME#aaa"}
    assert vault._card_keys(units, info) == expected
    assert vault._card_keys(dict(reversed(list(units.items()))), info) == expected
