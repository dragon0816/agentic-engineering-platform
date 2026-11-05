"""Two PCs' schema changes merge when they do not overlap (`BI_CARD_MODEL.md` §4.3).

Every test of landing runs in both arrival orders: the result must be byte-identical.
All data is fictional.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _ok, _push, _two_pcs

from capabilities.bi_cards import catalog, schema_merge, schema_versions, vault
from capabilities.bi_cards.schema import shipped
from capabilities.bi_cards.store import BiStore

Mutate = Callable[[dict[str, Any]], None]
BASE = "bi.schema/v1.1@5.0.0"


def _type(document: dict[str, Any], name: str = "Technology") -> dict[str, Any]:
    return next(t for t in document["types"] if t["name"] == name)


def _field(document: dict[str, Any], type_name: str, name: str) -> dict[str, Any]:
    return next(f for f in _type(document, type_name)["fields"] if f["name"] == name)


def _new_field(name: str, label: str = "虛構欄位", **more: Any) -> Mutate:
    def change(document: dict[str, Any]) -> None:
        definition = {"name": name, "kind": "str", "class": "sourced", "label": label, **more}
        _type(document)["fields"].append(definition)

    return change


def _new_type(name: str) -> Mutate:
    def change(document: dict[str, Any]) -> None:
        document["types"].append(
            {
                "name": name,
                "label": f"虛構類型 {name}",
                "domain": "one",
                "fields": [
                    {
                        "name": "name",
                        "kind": "str",
                        "class": "sourced",
                        "label": "名稱",
                        "required": True,
                    }
                ],
            }
        )

    return change


def _new_domain(name: str) -> Mutate:
    def change(document: dict[str, Any]) -> None:
        document["domains"].append(name)

    return change


def _new_enum(field: str, value: str, type_name: str = "Technology") -> Mutate:
    def change(document: dict[str, Any]) -> None:
        _field(document, type_name, field)["enum"].append(value)

    return change


def _new_label(field: str, label: str) -> Mutate:
    def change(document: dict[str, Any]) -> None:
        _field(document, "Technology", field)["label"] = label

    return change


def _change(ws: Path, dataset: str, mutate: Mutate, actor: str = "tester") -> dict[str, Any]:
    """A schema change the way every path makes one: draft, publish, upgrade."""
    current = catalog.for_store(BiStore(ws, dataset))
    made = schema_versions.create_draft(ws, current.ref, "虛構的改動", actor)
    document = copy.deepcopy(made["document"])
    mutate(document)
    saved = schema_versions.save_revision(
        ws,
        made["draft"]["id"],
        document=document,
        json_text=None,
        note="虛構",
        source="edit",
        actor=actor,
    )
    ref = schema_versions.publish(ws, made["draft"]["id"], saved["revision"], actor)["ref"]
    preview = schema_versions.upgrade_preview(ws, dataset, ref)
    schema_versions.upgrade_apply(ws, dataset, ref, preview["preview_token"], actor)
    return {"ref": ref}


def _sync(ws: Path, vault_id: str) -> None:
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))


def _effective_bytes(ws: Path, dataset: str) -> tuple[str, str]:
    reg = catalog.for_store(BiStore(ws, dataset))
    return reg.ref, catalog.canonical(reg.document)


def _both_land(tmp_path: Path, first: Mutate, second: Mutate, *, order: str) -> dict[str, Any]:
    """`a` makes `first`, `b` makes `second`, both from the same state, and they arrive
    in `order`: `ab` and `ba` each see the other's commit before pushing, `race` both push
    with nothing delivered, a real race on OneDrive. Returns the state every PC ends on,
    after checking they all agree."""
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _change(a, dataset, first)
    _change(b, dataset, second)
    _commit(a, vault_id, "虛構：a 的 schema 改動")
    _commit(b, vault_id, "虛構：b 的 schema 改動")
    if order == "race":
        assert _push(a, vault_id)["status"] == "pushed"
        assert _push(b, vault_id)["status"] == "pushed"
    else:
        pcs = [("a", a), ("b", b)] if order == "ab" else [("b", b), ("a", a)]
        assert _push(pcs[0][1], vault_id)["status"] == "pushed"
        drive.deliver(pcs[0][0], pcs[1][0], vault_id)
        assert _push(pcs[1][1], vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)
    late = drive.workspace("c")
    folder = drive.clone("a", "c", vault_id)
    _ok(_call(late, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "carol"}))
    seen = {_effective_bytes(ws, dataset) for ws in (a, b, late)}
    assert len(seen) == 1, "every PC reads byte-identical schema"
    ref, text = seen.pop()
    return {
        "ref": ref,
        "text": text,
        "document": json.loads(text),
        "a": a,
        "b": b,
        "vault_id": vault_id,
        "dataset": dataset,
        "drive": drive,
    }


@pytest.mark.parametrize(
    ("first", "second", "landed"),
    [
        (_new_field("cooling"), _new_field("power"), "fields"),
        (_new_type("Fictional"), _new_type("Imaginary"), "types"),
        (_new_domain("marine"), _new_domain("rail"), "domains"),
        (_new_enum("maturity", "pilot"), _new_enum("maturity", "sunset"), "enum"),
        (_new_label("maturity", "成熟度甲"), _new_label("standard_body", "標準組織乙"), "labels"),
        (_new_field("cooling"), _new_domain("marine"), "field and domain"),
    ],
    ids=["fields", "types", "domains", "enum values", "labels of two fields", "mixed"],
)
def test_non_overlapping_changes_both_land_in_either_order(
    tmp_path: Path, first: Mutate, second: Mutate, landed: str
) -> None:
    results = [
        _both_land(tmp_path / order, first, second, order=order) for order in ("ab", "ba", "race")
    ]
    one = results[0]
    assert {r["ref"] for r in results} == {one["ref"]}, "the same changes, the same version"
    assert {r["text"] for r in results} == {one["text"]}, "byte-identical on any route"
    expected = copy.deepcopy(_base_document())
    first(expected)
    second(expected)
    actual = one["document"]
    assert {t["name"] for t in actual["types"]} == {t["name"] for t in expected["types"]}
    assert set(actual["domains"]) == set(expected["domains"])
    for entity in expected["types"]:
        by_name = {f["name"]: f for f in _type(actual, entity["name"])["fields"]}
        for item in entity["fields"]:
            found = by_name[item["name"]]
            assert found.get("label") == item.get("label")
            assert set(found.get("enum") or []) == set(item.get("enum") or [])


def _base_document() -> dict[str, Any]:
    found = next(r for r in shipped() if r.ref == BASE)
    document: dict[str, Any] = json.loads(json.dumps(found.document))
    return document


def test_the_schema_unit_stays_on_its_version_and_no_new_version_number_is_used(
    tmp_path: Path,
) -> None:
    done = _both_land(tmp_path, _new_field("cooling"), _new_field("power"), order="ab")
    target = vault.Vault(done["a"], done["vault_id"])
    assert target.repo.units()["schema"] == BASE
    assert done["ref"].startswith(f"{BASE}+")
    assert catalog.base_ref(done["ref"]) == BASE
    # A number that was never pushed does not stay installed to collide with a later one.
    assert not catalog.schema_path(done["a"], "bi.schema/v1.1", "5.1.0").exists()


def test_a_third_change_after_a_merge_lands_on_top(tmp_path: Path) -> None:
    done = _both_land(tmp_path, _new_field("cooling"), _new_field("power"), order="ba")
    a, b, vault_id, dataset = done["a"], done["b"], done["vault_id"], done["dataset"]
    _change(a, dataset, _new_field("airflow"))
    _commit(a, vault_id, "虛構：再加一個欄位")
    assert _push(a, vault_id)["status"] == "pushed"
    done["drive"].deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _effective_bytes(a, dataset) == _effective_bytes(b, dataset)
    names = {f["name"] for f in _type(json.loads(_effective_bytes(a, dataset)[1]))["fields"]}
    assert {"cooling", "power", "airflow"} <= names


def test_the_same_addition_on_two_pcs_is_one_change(tmp_path: Path) -> None:
    done = _both_land(tmp_path, _new_field("cooling"), _new_field("cooling"), order="ab")
    fields = [f["name"] for f in _type(done["document"])["fields"]]
    assert fields.count("cooling") == 1


def test_old_commits_read_as_they_did(tmp_path: Path) -> None:
    """A version from before these changes still reads on its own schema."""
    drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    target = vault.Vault(a, vault_id)
    before = target.repo.head()
    _change(a, dataset, _new_field("cooling"))
    _commit(a, vault_id, "虛構：加欄位")
    _push(a, vault_id)
    assert before is not None
    assert schema_merge.effective_ref(a, target.repo.state_at(before)) == BASE
    assert schema_merge.effective_ref(a, target.repo.units()).startswith(f"{BASE}+")


# -- overlap stops for a person ---------------------------------------------------------


def test_the_same_name_with_another_definition_stops_at_push(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _change(a, dataset, _new_field("cooling"))
    _change(b, dataset, _new_field("cooling", kind="int"))
    _commit(a, vault_id, "虛構：文字欄位")
    _commit(b, vault_id, "虛構：數字欄位")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    answer = _push(b, vault_id)
    assert answer["status"] == "conflicts"
    item = answer["conflicts"][0]
    assert item["unit"] == "schema_change:field:Technology.cooling"
    assert "Technology.cooling" in item["label"] and "schema" in item["label"]
    assert item["mine"]["kind"] == "int" and item["theirs"]["kind"] == "str"


def test_a_label_two_people_changed_stops_at_push(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _change(a, dataset, _new_label("maturity", "甲"))
    _change(b, dataset, _new_label("maturity", "乙"))
    _commit(a, vault_id, "虛構")
    _commit(b, vault_id, "虛構")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    assert _push(b, vault_id)["status"] == "conflicts"


def test_the_same_name_in_a_real_race_is_listed_for_a_person_on_every_pc(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _change(a, dataset, _new_field("cooling"))
    _change(b, dataset, _new_field("cooling", kind="int"))
    _commit(a, vault_id, "虛構：文字欄位")
    _commit(b, vault_id, "虛構：數字欄位")
    assert _push(a, vault_id)["status"] == "pushed"
    assert _push(b, vault_id)["status"] == "pushed"  # neither could see the other
    drive.deliver("a", "b", vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)
    assert _effective_bytes(a, dataset) == _effective_bytes(b, dataset)
    listed = [
        _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/status"))["schema_conflicts"]
        for ws in (a, b)
    ]
    assert listed[0] == listed[1] and [c["kind"] for c in listed[0]] == ["race"]
    _ok(
        _call(
            a,
            "POST",
            f"/api/bi/vaults/{vault_id}/schema-conflicts",
            {"unit": listed[0][0]["unit"], "choice": "keep"},
        )
    )
    assert _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/status"))["schema_conflicts"] == []


def _landed(drive: Any, a: Path, b: Path, vault_id: str, dataset: str, *changes: Mutate) -> None:
    """Changes both PCs have. A BI schema's shipped fields cannot be removed or changed at
    all (`catalog.bi_problems`), so what can be is what was added since."""
    for change in changes:
        _change(a, dataset, change)
    _commit(a, vault_id, "虛構：共同的起點")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)


def _remove_field(name: str) -> Mutate:
    def change(document: dict[str, Any]) -> None:
        entity = _type(document)
        entity["fields"] = [f for f in entity["fields"] if f["name"] != name]

    return change


def test_a_kind_change_is_a_version_and_two_of_them_conflict(tmp_path: Path) -> None:
    def to_int(document: dict[str, Any]) -> None:
        _field(document, "Technology", "spec_note")["kind"] = "int"

    _, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _change(a, dataset, _new_field("spec_note"))
    _commit(a, vault_id, "虛構")
    _push(a, vault_id)
    _change(a, dataset, to_int)
    assert vault.Vault(a, vault_id).repo.working_units()["schema"] != BASE
    _commit(a, vault_id, "虛構：改型別")
    assert _push(a, vault_id)["status"] == "pushed"
    done = catalog.for_store(BiStore(a, dataset))
    assert _field(done.document, "Technology", "spec_note")["kind"] == "int"
    # The change it absorbed is gone, so it is not applied twice.
    assert not [k for k in vault.Vault(a, vault_id).repo.units() if k.startswith("schema_change:")]


def test_two_different_versions_with_one_number_never_split(tmp_path: Path) -> None:
    """Two different versions drafted from one state are two refs, so they conflict on the
    `schema` unit for a person, and no number ever has two contents."""

    def to_int(document: dict[str, Any]) -> None:
        _field(document, "Technology", "second_note")["kind"] = "int"

    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _landed(drive, a, b, vault_id, dataset, _new_field("first_note"), _new_field("second_note"))
    _change(a, dataset, _remove_field("first_note"))
    _change(b, dataset, to_int)
    mine = vault.Vault(a, vault_id).repo.working_units()["schema"]
    theirs = vault.Vault(b, vault_id).repo.working_units()["schema"]
    assert mine != theirs and catalog.base_ref(mine) == mine
    _commit(a, vault_id, "虛構")
    _commit(b, vault_id, "虛構")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    answer = _push(b, vault_id)
    assert answer["status"] == "conflicts"
    listed = {c["unit"]: c["label"] for c in answer["conflicts"]}
    assert listed["schema"] == "schema 版本"


def test_a_removal_against_an_addition_stops_the_later_push(tmp_path: Path) -> None:
    """a adds an enum value to a field; b's new version removes that field."""
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    stage = _new_field("stage", kind="enum", enum=["early"])
    _landed(drive, a, b, vault_id, dataset, stage)
    _change(a, dataset, _new_enum("stage", "pilot"))
    _change(b, dataset, _remove_field("stage"))
    _commit(a, vault_id, "虛構：加允許值")
    _commit(b, vault_id, "虛構：移除欄位")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    answer = _push(b, vault_id)
    assert answer["status"] == "blocked"
    assert "Technology.stage" in answer["blocking"][0]


def test_a_removal_of_a_field_someone_uses_is_stopped_before_it_applies(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)

    def used(document: dict[str, Any]) -> None:
        _new_field("cooling", used_by=["aidc"])(document)

    _change(a, dataset, used)
    current = catalog.for_store(BiStore(a, dataset))
    made = schema_versions.create_draft(a, current.ref, "虛構", "tester")
    document = copy.deepcopy(made["document"])
    _remove_field("cooling")(document)
    saved = schema_versions.save_revision(
        a,
        made["draft"]["id"],
        document=document,
        json_text=None,
        note="虛構",
        source="edit",
        actor="tester",
    )
    ref = schema_versions.publish(a, made["draft"]["id"], saved["revision"], "tester")["ref"]
    preview = schema_versions.upgrade_preview(a, dataset, ref)
    assert [b["code"] for b in preview["blocked"]] == ["field_used_by"]
    assert (
        "cooling" in preview["blocked"][0]["message"] and "aidc" in preview["blocked"][0]["message"]
    )


def test_a_clash_that_landed_is_shown_and_a_person_can_drop_it(tmp_path: Path) -> None:
    """A race neither PC could see: a's unit is overlaid on a version without that field."""
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    target = vault.Vault(a, vault_id)
    with target.lock:
        target.repo.stage("schema_change:enum:Technology.no_such_field:pilot", {"value": "pilot"})
    _commit(a, vault_id, "虛構：指向不存在的欄位")
    # On a's own PC the push refuses it; a real race brings it past that: write it as landed.
    with target.lock:
        target.repo._write_commits(  # noqa: SLF001
            [record for _, record in target.repo._local_commits()]  # noqa: SLF001
        )
        for path, _ in target.repo._local_commits():  # noqa: SLF001
            path.unlink()
    drive.deliver("a", "b", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)
    for ws in (a, b):
        found = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/status"))["schema_conflicts"]
        assert [c["unit"] for c in found] == ["schema_change:enum:Technology.no_such_field:pilot"]
        assert found[0]["kind"] == "clash" and "no_such_field" in found[0]["reason"]
    _ok(
        _call(
            b,
            "POST",
            f"/api/bi/vaults/{vault_id}/schema-conflicts",
            {"unit": "schema_change:enum:Technology.no_such_field:pilot", "choice": "drop"},
        )
    )
    _commit(b, vault_id, "虛構：放棄這個改動")
    assert _push(b, vault_id)["status"] == "pushed"
    assert _ok(_call(b, "GET", f"/api/bi/vaults/{vault_id}/status"))["schema_conflicts"] == []


# -- skills ---------------------------------------------------------------------------


def _skill(ws: Path, vault_id: str, name: str, body: str, **more: Any) -> None:
    given = {"name": name, "role": "extract", "body": body, **more}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/skills", given))


def _skills(ws: Path, vault_id: str) -> dict[str, Any]:
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))["skills"]
    return {item["name"]: item for item in listed}


def _with_skills(tmp_path: Path) -> tuple[Path, str, str]:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _change(a, dataset, _new_field("obsolete"))
    _commit(a, vault_id, "虛構：一個之後會移除的欄位")
    _push(a, vault_id)
    folder = ["applications/aidc/sources"]
    _skill(a, vault_id, "aidc/uses-signal", "只讀訊號。", applies_to=folder, card_types=["Signal"])
    _skill(a, vault_id, "wireless/uses-tech", "只讀技術。", card_types=["Technology"])
    _skill(a, vault_id, "robotics/names-cooling", "記得填 cooling。")
    _skill(a, vault_id, "library/skill-review/plain", "一般規則。")
    _commit(a, vault_id, "虛構：幾份 skill")
    _push(a, vault_id)
    return a, vault_id, dataset


def test_an_addition_flags_only_the_skills_it_touches_and_all_still_run(tmp_path: Path) -> None:
    a, vault_id, dataset = _with_skills(tmp_path)
    _change(a, dataset, _new_field("cooling"))
    found = _skills(a, vault_id)
    assert not found["aidc/uses-signal"]["needs_update"], "another type's addition"
    assert not found["library/skill-review/plain"]["needs_update"], "says nothing about it"
    assert found["wireless/uses-tech"]["needs_update"], "its card type changed"
    assert found["robotics/names-cooling"]["needs_update"], "its text names the field"
    for name in ("wireless/uses-tech", "robotics/names-cooling"):
        assert found[name]["update_blocks"] is False, "an addition breaks nothing"
        assert "cooling" in found[name]["update_reason"]
    target = vault.Vault(a, vault_id)
    from knowledge.repo import skills as repo_skills

    assert repo_skills.runnable(target.repo, "wireless/uses-tech").name == "uses-tech"


def test_a_breaking_change_flags_and_stops_what_it_touches_only(tmp_path: Path) -> None:
    a, vault_id, dataset = _with_skills(tmp_path)
    _change(a, dataset, _remove_field("obsolete"))
    found = _skills(a, vault_id)
    assert not found["aidc/uses-signal"]["needs_update"], "another type, and it says so"
    assert found["wireless/uses-tech"]["needs_update"]
    assert found["wireless/uses-tech"]["update_blocks"] is True
    # With no card types a skill reads every type, so a removal cannot be ruled out.
    assert found["library/skill-review/plain"]["needs_update"]
    assert found["library/skill-review/plain"]["update_blocks"] is True


def test_a_skill_saved_again_after_an_addition_is_no_longer_flagged(tmp_path: Path) -> None:
    a, vault_id, dataset = _with_skills(tmp_path)
    _change(a, dataset, _new_field("cooling"))
    _skill(a, vault_id, "wireless/uses-tech", "只讀技術，也讀 cooling。", card_types=["Technology"])
    assert not _skills(a, vault_id)["wireless/uses-tech"]["needs_update"]


def test_a_skill_that_cannot_be_read_is_flagged() -> None:
    assert schema_merge.skill_verdict(None, None, "只讀技術。", (), "extract")["needs_update"]


# -- what a change is, on its own ----------------------------------------------------


def test_only_additions_become_units() -> None:
    old = _base_document()
    new = copy.deepcopy(old)
    new["version"] = "5.1.0"
    _new_field("cooling")(new)
    _new_domain("marine")(new)
    _new_enum("maturity", "pilot")(new)
    units = schema_merge.changes_between(old, new)
    assert units is not None
    assert set(units) == {
        "schema_change:field:Technology.cooling",
        "schema_change:domain:marine",
        "schema_change:enum:Technology.maturity:pilot",
    }
    for mutate in (
        _remove_field("maturity"),
        lambda d: _field(d, "Technology", "maturity").update(kind="str", enum=None),
        lambda d: _field(d, "Technology", "maturity")["enum"].pop(),
        lambda d: _new_field("needed", required=True)(d),
        lambda d: d["domains"].pop(),
    ):
        changed = copy.deepcopy(old)
        changed["version"] = "5.1.0"
        mutate(changed)
        assert schema_merge.changes_between(old, changed) is None


def test_the_overlay_is_the_same_whatever_order_the_units_are_given() -> None:
    old = _base_document()
    new = copy.deepcopy(old)
    new["version"] = "5.1.0"
    _new_type("Fictional")(new)
    _new_field("cooling")(new)
    _new_field("airflow")(new)
    units = schema_merge.changes_between(old, new)
    assert units is not None
    forward = dict(sorted(units.items()))
    backward = dict(sorted(units.items(), reverse=True))
    one = schema_merge.overlay(old, forward)
    other = schema_merge.overlay(old, backward)
    assert catalog.canonical(one[0]) == catalog.canonical(other[0])
    assert one[1] == []


def test_old_units_and_version_text_stay_valid() -> None:
    assert catalog.base_ref(BASE) == BASE
    assert catalog.base_ref(f"{BASE}+abc123def456") == BASE
    assert catalog._version_tuple("5.0.0+abc123def456") == (5, 0, 0)  # noqa: SLF001


def test_the_snapshot_of_a_merged_schema_reads_back(tmp_path: Path) -> None:
    from capabilities.bi_cards import snapshot

    done = _both_land(tmp_path, _new_field("cooling"), _new_field("power"), order="ab")
    a, dataset = done["a"], done["dataset"]
    _call(
        a,
        "POST",
        "/api/bi/cards",
        {"dataset": dataset, "entity_type": "Technology", "name": "虛構技術"},
    )
    store = BiStore(a, dataset)
    assert store.schema_ref().startswith(f"{BASE}+")
    built = snapshot.build_snapshot(store)
    assert snapshot.read_snapshot(built).schema_ref == done["ref"]
