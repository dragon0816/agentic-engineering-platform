"""Correction notes: the one way a person changes a value (design §5.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from test_bi_vault import _push, _row, _sync, _two_pcs

from aep_bi.cards import correction, service, vault, vault_skills
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, BiStoreError, PlannedRow
from aep_bi.host.bi_cards_api import route


def _call(ws: Path, path: str, body: Any, actor: str = "tester") -> Any:
    return route(ws, actor, "POST", path, {}, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _store(ws: Path, dataset: str = "demo") -> BiStore:
    store = BiStore(ws, dataset)
    store.create("bi.schema/v1.1")
    return store


def _import(store: BiStore, **values: Any) -> dict[str, Any]:
    store.apply(
        [PlannedRow(2, "Technology", "TSN", "TSN", values, False)],
        filename="tech.csv",
        entity_type="Technology",
        actor="x via web",
    )
    card = store.find("Technology", "TSN")
    assert card is not None
    return dict(card)


def _preview(
    ws: Path, store: BiStore, card: dict[str, Any], field: str, value: Any, **more: Any
) -> Any:
    body = {
        "dataset": store.dataset,
        "card": card["id"],
        "field": field,
        "value": value,
        "base_version": card["version"],
        "reason": "FAE 確認",
        **more,
    }
    return _call(ws, "/api/bi/corrections/preview", body)


def _apply(ws: Path, store: BiStore, note: dict[str, Any], actor: str = "tester") -> Any:
    body = {"dataset": store.dataset, "text": note["text"], "base_version": note["base_version"]}
    return _call(ws, "/api/bi/corrections/apply", body, actor=actor)


@pytest.mark.parametrize(
    "value",
    [
        "IEEE 802.1",
        'has "quotes" and: a colon',
        "[not a list]",
        "{not a map}",
        "two\nlines",
        "line separator\x85next",
        "# not a comment",
        ["a, b", "c]"],
        "",
        [],
    ],
)
def test_a_note_reads_back_what_it_said(value: Any) -> None:
    card = {"id": "c1", "entity_type": "Technology", "name": "TSN"}
    text = correction.render(
        card, "body", value, "第一行\n第二行: x", "愛麗絲", "2026-11-04T00:00:00Z"
    )
    note = correction.read(text)
    assert (note.card_id, note.field, note.value) == ("c1", "body", value)
    assert note.reason == "第一行\n第二行: x" and note.author == "愛麗絲"


def test_a_note_written_by_hand_is_read_the_same_way() -> None:
    note = correction.read("---\ncard: c1\nfield: body\nvalue: 手寫\nreason: 看規格\n---\n本文\n")
    assert (note.card_id, note.field, note.value, note.reason) == ("c1", "body", "手寫", "看規格")


@pytest.mark.parametrize(
    "text",
    [
        "一般的筆記，沒有 frontmatter",
        "---\ntitle: 一般筆記\n---\n本文\n",
        "---\ncard: c1\nfield: body\n---\n沒有 value\n",
        "---\ncard: c1\nvalue: x\n---\n沒有 field\n",
        None,
    ],
)
def test_text_without_the_frontmatter_is_not_a_note(text: Any) -> None:
    with pytest.raises(BiStoreError) as refused:
        correction.read(text)
    assert refused.value.code == "note_invalid"


def test_the_preview_writes_nothing_and_lists_the_difference(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _import(store, standard_body="IEEE")
    before = store.path.read_bytes()
    note = _ok(_preview(tmp_path, store, card, "standard_body", "IETF"))
    assert (note["current"], note["value"], note["unchanged"]) == ("IEEE", "IETF", False)
    assert note["folder"] == correction.NO_HOME_FOLDER
    assert store.path.read_bytes() == before
    assert Staging(tmp_path, "demo").sources() == []


def test_a_confirmed_note_is_a_source_and_the_values_evidence(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _import(store, standard_body="IEEE")
    note = _ok(_preview(tmp_path, store, card, "standard_body", "IETF"))
    done = _ok(_apply(tmp_path, store, note))
    assert done["version"] == card["version"] + 1

    field = store.fields(card["id"])["standard_body"]
    assert (field["value"], field["kind"]) == ("IETF", "human")
    (kept,) = Staging(tmp_path, "demo").sources()
    assert kept["id"] == done["source"] and kept["name"].startswith("correction-")
    (proof,) = store.evidence(card["id"])
    assert proof["source_id"] == kept["id"] and proof["basis"] == "human"
    assert proof["locator"]["key"] == "value" and proof["excerpt"] == 'value: "IETF"'
    assert store.history(card["id"])[-1]["reason"] == "FAE 確認"


def test_a_note_can_be_undone(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _import(store, standard_body="IEEE")
    note = _ok(_preview(tmp_path, store, card, "standard_body", "IETF"))
    done = _ok(_apply(tmp_path, store, note))
    _ok(_call(tmp_path, "/api/bi/import/undo", {"dataset": "demo", "import_id": done["import_id"]}))
    assert store.fields(card["id"])["standard_body"]["value"] == "IEEE"


def test_a_person_can_still_mark_a_card_verified_with_a_note(tmp_path: Path) -> None:
    """`service.trusted` needs `verified` of kind `human`; an import cannot give it."""
    store = _store(tmp_path)
    card = _import(store, confidence="verified")
    assert not service.trusted(store.card(card["id"]), store.fields(card["id"]))
    store.set_field(card["id"], "confidence", "low", base_version=card["version"], actor="x")
    now = store.card(card["id"])
    assert now is not None
    note = _ok(_preview(tmp_path, store, dict(now), "confidence", "verified"))
    _ok(_apply(tmp_path, store, note))
    assert service.trusted(store.card(card["id"]), store.fields(card["id"]))


@pytest.mark.parametrize(
    ("field", "value", "more", "code"),
    [
        ("no_such_field", "x", {}, "field_unknown"),
        ("standard_body", "x", {"reason": " "}, "reason_required"),
        ("standard_body", "x", {"base_version": None}, "base_version_missing"),
        ("standard_body", ["a"], {}, "value_invalid"),
    ],
)
def test_a_note_that_cannot_be_taken_is_refused_400(
    tmp_path: Path, field: str, value: Any, more: dict[str, Any], code: str
) -> None:
    store = _store(tmp_path)
    card = _import(store, standard_body="IEEE")
    status, answer = _preview(tmp_path, store, card, field, value, **more)
    assert (status, answer["code"]) == (400, code)


def test_a_note_on_no_card_is_404(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _import(store, standard_body="IEEE")
    note = _ok(_preview(tmp_path, store, card, "standard_body", "IETF"))
    text = note["text"].replace(card["id"], "nosuchcard")
    status, answer = _call(
        tmp_path,
        "/api/bi/corrections/apply",
        {"dataset": "demo", "text": text, "base_version": note["base_version"]},
    )
    assert (status, answer["code"]) == (404, "card_unknown")


def test_a_card_that_moved_after_the_preview_refuses_the_note(tmp_path: Path) -> None:
    store = _store(tmp_path)
    card = _import(store, standard_body="IEEE")
    note = _ok(_preview(tmp_path, store, card, "standard_body", "IETF"))
    store.set_field(
        card["id"], "standard_body", "ISO", base_version=card["version"], actor="other via web"
    )
    status, answer = _apply(tmp_path, store, note)
    assert (status, answer["code"]) == (409, "stale_edit")
    assert answer["current"] == "ISO" and answer["by"] == "other via web"
    assert store.fields(card["id"])["standard_body"]["value"] == "ISO"
    assert Staging(tmp_path, "demo").sources() == []


def test_a_note_says_a_value_or_a_state_not_both() -> None:
    both = "---\ncard: c1\nfield: body\nvalue: x\nstate: confirmed_none\nreason: r\n---\n"
    with pytest.raises(BiStoreError) as refused:
        correction.read(both)
    assert refused.value.code == "note_invalid"
    bad = "---\ncard: c1\nfield: body\nstate: maybe\nreason: r\n---\n"
    with pytest.raises(BiStoreError) as refused:
        correction.read(bad)
    assert refused.value.code == "state_invalid"


# -- in a vault ----------------------------------------------------------------------------


def _vault_card(ws: Path, dataset: str) -> dict[str, Any]:
    card = BiStore(ws, dataset).find("Technology", "TSN")
    assert card is not None
    return dict(card)


def _note(ws: Path, dataset: str, field: str, value: Any, actor: str) -> dict[str, Any]:
    card = _vault_card(ws, dataset)
    body = {
        "dataset": dataset,
        "card": card["id"],
        "field": field,
        "value": value,
        "base_version": card["version"],
        "reason": f"{actor} 的更正",
    }
    note = _ok(_call(ws, "/api/bi/corrections/preview", body, actor=actor))
    return _ok(_apply(ws, BiStore(ws, dataset), note, actor=actor))


def _shared(tmp_path: Path) -> tuple[Any, str, str, Path, Path]:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE")],
        filename="t.csv",
        entity_type="Technology",
        actor="x via web",
    )
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    return drive, vault_id, dataset, a, b


def test_a_note_in_a_vault_commits_at_once_with_its_purpose(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _shared(tmp_path)
    _note(a, dataset, "standard_body", "IEEE 802.1", "alice")
    repo = vault.Vault(a, vault_id).repo
    assert vault.status(a, vault_id)["uncommitted"] == 0
    purposes = [item["purpose"] for item in repo.local_commits()]
    assert purposes[-2].startswith("加入來源：correction-")
    assert purposes[-1].startswith("更正 Technology「TSN」的 standard_body：alice")


def test_two_notes_on_the_same_field_are_a_conflict(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _shared(tmp_path)
    _note(a, dataset, "standard_body", "IEEE 802.1", "alice")
    assert _push(a, vault_id)["status"] == "pushed"
    _note(b, dataset, "standard_body", "IETF", "bob")
    drive.deliver("a", "b", vault_id)
    result = _push(b, vault_id)
    assert result["status"] == "conflicts"
    field = next(c for c in result["conflicts"] if c["unit"].startswith("field:"))
    assert (field["mine"]["value"], field["theirs"]["value"]) == ("IETF", "IEEE 802.1")


def test_notes_on_different_fields_merge(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _shared(tmp_path)
    _note(a, dataset, "standard_body", "IEEE 802.1", "alice")
    assert _push(a, vault_id)["status"] == "pushed"
    _note(b, dataset, "body", "時間敏感網路", "bob")
    drive.deliver("a", "b", vault_id)
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    store = BiStore(a, dataset)
    fields = store.fields(_vault_card(a, dataset)["id"])
    assert (fields["standard_body"]["value"], fields["body"]["value"]) == (
        "IEEE 802.1",
        "時間敏感網路",
    )
    assert fields["body"]["kind"] == "human"
    # The note reaches the other PC as evidence.
    proof = store.evidence(_vault_card(a, dataset)["id"])
    assert {p["basis"] for p in proof if p["field"] == "body"} == {"human"}


def _state_note(ws: Path, dataset: str, field: str, state: str, actor: str) -> dict[str, Any]:
    card = _vault_card(ws, dataset)
    body = {
        "dataset": dataset,
        "card": card["id"],
        "field": field,
        "state": state,
        "base_version": card["version"],
        "reason": "查過規格書，沒有這項",
    }
    note = _ok(_call(ws, "/api/bi/corrections/preview", body, actor=actor))
    assert note["state"] == state and note["unchanged"] is False
    return _ok(_apply(ws, BiStore(ws, dataset), note, actor=actor))


def test_only_a_note_says_confirmed_none_and_it_travels_with_its_evidence(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _shared(tmp_path)
    version = _vault_card(a, dataset)["version"]
    done = _state_note(a, dataset, "body", "confirmed_none", "alice")
    assert done["version"] == version + 1
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    store = BiStore(b, dataset)
    card = _vault_card(b, dataset)
    stated = store.field_states(card["id"])["body"]
    assert (stated["state"], stated["reason"]) == ("confirmed_none", "查過規格書，沒有這項")
    assert "body" not in store.fields(card["id"])
    proof = [e for e in store.evidence(card["id"]) if e["field"] == "body"]
    assert proof[0]["basis"] == "human" and proof[0]["excerpt"] == 'state: "confirmed_none"'


def test_the_same_state_again_is_no_change_and_a_value_clears_it(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _shared(tmp_path)
    _state_note(a, dataset, "body", "not_applicable", "alice")
    card = _vault_card(a, dataset)
    body = {
        "dataset": dataset,
        "card": card["id"],
        "field": "body",
        "state": "not_applicable",
        "base_version": card["version"],
        "reason": "再說一次",
    }
    note = _ok(_call(a, "/api/bi/corrections/preview", body))
    assert note["unchanged"] is True
    assert _ok(_apply(a, BiStore(a, dataset), note))["unchanged"] is True
    _note(a, dataset, "body", "其實有", "alice")
    assert "body" not in BiStore(a, dataset).field_states(card["id"])


def test_a_state_on_a_field_with_a_value_replaces_the_value(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _shared(tmp_path)
    _state_note(a, dataset, "standard_body", "pending_confirmation", "alice")
    store = BiStore(a, dataset)
    card = _vault_card(a, dataset)
    assert "standard_body" not in store.fields(card["id"])
    assert store.field_states(card["id"])["standard_body"]["state"] == "pending_confirmation"


def test_a_note_lands_in_its_home_or_the_shared_corrections_folder(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _shared(tmp_path)
    _note(a, dataset, "standard_body", "IEEE 802.1", "alice")
    units = vault.Vault(a, vault_id).repo.working_units()
    (kept,) = [v for k, v in units.items() if k.startswith("source:")]
    assert kept["folder"] == correction.NO_HOME_FOLDER
    assert kept["file"].startswith("library/corrections/sources/")


class _Homed:
    def __init__(self, home: str | None) -> None:
        self.home = home

    def first_home(self, card_id: str) -> str | None:
        return self.home


@pytest.mark.parametrize(
    ("home", "folder"),
    [
        ("aidc", "applications/aidc/sources"),
        ("library/products", "library/products/sources"),
        (None, "library/corrections/sources"),
    ],
)
def test_the_notes_folder_is_a_valid_one_of_its_home(home: str | None, folder: str) -> None:
    found = correction.note_folder(cast(BiStore, _Homed(home)), "c1")
    assert found == folder and vault_skills.checked_folder(found) == folder
