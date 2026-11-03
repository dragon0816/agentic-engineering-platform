"""A home's profile (`docs/phases/BI_CARD_MODEL.md` §4.2). All data is fictional."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _commit, _ok, _push, _refused, _two_pcs

from capabilities.bi_cards import card_model, catalog, extract, profile, vault
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStoreError
from host_runtime.bi_cards_api import route

SCHEMA = "bi.schema/v1.1@5.0.0"
AIDC = "applications/aidc/sources"
NOTE = "虛構電力公司宣布液冷方案，與虛構 ODM 合作。"
PROFILE: dict[str, Any] = {
    "types": {
        "Technology": {
            "category": "這個應用裡的技術指液冷與電源",
            "fields": {"domain": {"use": "required", "note": "一律填 AIDC"}},
        }
    }
}


def _reg() -> Any:
    return catalog.resolve(Path("."), SCHEMA)


def _save(ws: Path, vault_id: str, home: str = "aidc", document: Any = None) -> dict[str, Any]:
    body = {"home": home, "profile": PROFILE if document is None else document}
    return _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/profiles", body))


def _ai_run(ws: Path, dataset: str, folder: str, model: Scripted, **more: Any) -> Any:
    jobs = Jobs()
    ai = _runtime(model, jobs)
    body = {"dataset": dataset, "name": "note.md", "text": NOTE}
    source = _ok(route(ws, "alice", "POST", "/api/bi/sources", {}, body))["source"]["id"]
    start = {"dataset": dataset, "kind": "ingest", "source_id": source, "folder": folder, **more}
    answer = route(ws, "alice", "POST", "/api/bi/runs", {}, start, None, ai)
    jobs.run_all()
    return answer


@pytest.mark.parametrize(
    "document",
    [
        "not an object",
        {"types": []},
        {"types": {"NoSuchType": {"fields": {}}}},
        {"types": {"Technology": {"fields": {"no_such_field": {"use": "optional"}}}}},
        {"types": {"Technology": {"fields": {"domain": {"use": "sometimes"}}}}},
        {"types": {"Technology": {"fields": {"domain": {"use": "optional", "kind": "text"}}}}},
        {"types": {"Technology": {"fields": {"domain": {"use": "optional", "enum": ["a"]}}}}},
        {"types": {"Technology": {"fields": {}, "kind": "text"}}},
        {"types": {}, "extra": 1},
        {"types": {}, "application": "wireless"},
        {"types": {}, "format": "other/v1"},
        {"types": {}, "proposals": [{"type": "NoSuchType", "field": "x", "definition": {}}]},
        {"types": {}, "proposals": [{"type": "Technology", "field": "x"}]},
    ],
)
def test_a_bad_profile_is_refused(document: Any) -> None:
    with pytest.raises(BiStoreError) as failure:
        profile.checked(document, "aidc", _reg())
    assert failure.value.code == "profile_invalid"


def test_a_definition_is_allowed_only_inside_a_proposal() -> None:
    proposal = {
        "type": "Technology",
        "field": "cooling",
        "definition": {"kind": "text", "enum": ["liquid"]},
        "reason": "液冷",
    }
    good = profile.checked({"types": {}, "proposals": [proposal]}, "aidc", _reg())
    assert good["proposals"] == [{**proposal, "status": "proposed"}]
    assert good["format"] == "aep.bi.profile/v1"
    assert good["application"] == "aidc" and good["schema"] == SCHEMA


def test_a_profile_is_a_file_written_once_with_a_unit(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    first = _save(a, vault_id)["profile"]
    second = _save(a, vault_id, document={**PROFILE, "types": {}})["profile"]
    entry = _save(a, vault_id, home="library/products")["profile"]
    assert first["path"] == "applications/aidc/profile/rev-1-alice.json"
    assert second["path"] == "applications/aidc/profile/rev-2-alice.json"
    assert entry["path"] == "library/products/profile/rev-1-alice.json"
    target = vault.Vault(a, vault_id)
    units = target.repo.working_units()
    assert set(units["profile:aidc"]) == {"revision", "author", "path", "sha256", "schema"}
    assert units["profile:aidc"]["revision"] == 2 and units["profile:aidc"]["schema"] == SCHEMA
    assert units["profile:library/products"]["revision"] == 1
    _commit(a, vault_id, "profiles")
    _push(a, vault_id)
    folder = drive.parent("a") / vault_id
    written = json.loads((folder / first["path"]).read_text(encoding="utf-8"))
    assert written["revision"] == 1 and written["application"] == "aidc"
    assert written["types"]["Technology"]["fields"]["domain"]["use"] == "required"
    listed = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/profiles"))["profiles"]
    assert [(p["home"], p["revision"]) for p in listed] == [("aidc", 2), ("library/products", 1)]


def test_a_refused_profile_answers_400(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    bad = {"types": {"Technology": {"fields": {"domain": {"use": "optional", "kind": "x"}}}}}
    body = {"home": "aidc", "profile": bad}
    _refused(_call(a, "POST", f"/api/bi/vaults/{vault_id}/profiles", body), 400, "profile_invalid")
    assert "profile:aidc" not in vault.Vault(a, vault_id).repo.working_units()


def test_the_prompt_shows_only_what_the_profile_uses() -> None:
    reg = _reg()
    text = extract.describe_types(reg, ["Technology"], PROFILE)
    whole = extract.describe_types(reg, ["Technology"])
    assert "What this type means here: 這個應用裡的技術指液冷與電源" in text
    assert "required here; 一律填 AIDC" in text
    entity = reg.types["Technology"]
    unused = [
        f.name
        for f in entity.fields
        if f.klass != "derived"
        and not f.required
        and f.name not in {*entity.naming, *profile.ALWAYS_FIELDS, "domain"}
    ]
    assert unused
    for name in unused:
        assert f"    {name}:" not in text and f"    {name}:" in whole
    for name in (*entity.naming, *profile.ALWAYS_FIELDS):
        assert f"    {name}:" in text
    assert "means here" not in whole and "required here" not in whole


def test_a_run_with_a_profile_asks_only_for_it_and_marks_the_rest(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _save(a, vault_id)
    entity = _reg().types["Technology"]
    name = entity.naming_field
    outside = next(
        f.name
        for f in entity.fields
        if f.klass != "derived"
        and f.kind == "str"
        and not f.required
        and f.name not in {*entity.naming, *profile.ALWAYS_FIELDS, "domain"}
    )
    model = Scripted(
        {
            "candidates": [
                {
                    "entity_type": "Technology",
                    "name": "虛構液冷",
                    "fields": {
                        name: {"value": "虛構液冷", "basis": "fact", "quote": "液冷方案"},
                        outside: {"value": "虛構", "basis": "fact", "quote": "虛構電力公司"},
                    },
                },
                {
                    "entity_type": "Signal",
                    "name": "虛構訊號",
                    "fields": {"title": {"value": "虛構訊號", "basis": "fact", "quote": "虛構"}},
                },
            ]
        }
    )
    run = _ok(_ai_run(a, dataset, AIDC, model))["run"]
    system = model.requests[0].messages[0].text
    assert "這個應用裡的技術指液冷與電源" in system
    assert "- Technology (" in system and "- Signal (" not in system
    detail = _ok(_call(a, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))
    assert detail["run"]["home"] == "aidc" and detail["run"]["profile"]["revision"] == 1
    assert detail["run"]["types"] == ["Technology"]
    found = {c["entity_type"]: c for c in detail["candidates"]}
    technology, signal = found["Technology"], found["Signal"]
    # Outside the profile but in the schema: kept and marked, not dropped.
    assert technology["outside_profile"] == [outside]
    assert technology["outside_profile_type"] is False
    assert [f["outside_profile"] for f in technology["fields"] if f["field"] == outside] == [True]
    assert not any(f.get("outside_profile") for f in technology["fields"] if f["field"] == name)
    assert signal["outside_profile_type"] is True
    # Required by the profile is a warning; only the schema's `required` refuses.
    codes = [w["code"] for w in technology["warnings"]]
    assert codes.count("profile_required_missing") == 1
    assert "domain" in next(
        w["message"] for w in technology["warnings"] if w["code"] == "profile_required_missing"
    )
    assert not [e for e in technology["errors"] if e.get("field") == "domain"]


def test_a_retry_reads_the_profile_the_run_kept(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _save(a, vault_id)
    run = _ok(_ai_run(a, dataset, AIDC, Scripted({"candidates": []})))["run"]
    layout = Staging(a, dataset).layout(run["id"]) or {}
    assert layout["skills"]["profile"]["types"] == PROFILE["types"]
    assert layout["skills"]["home"] == "aidc"


def test_a_run_with_no_profile_reads_the_whole_schema_and_says_so(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _save(a, vault_id)  # another home's profile does not apply
    model = Scripted({"candidates": []})
    run = _ok(_ai_run(a, dataset, "applications/wireless/sources", model))["run"]
    assert "這個應用裡的技術" not in model.requests[0].messages[0].text
    detail = _ok(_call(a, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))["run"]
    assert detail["profile"] is None and detail["home"] == "wireless"
    assert detail["types"] == list(extract.DEFAULT_TYPES)


def test_an_unreadable_profile_refuses_the_run(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    saved = _save(a, vault_id)["profile"]
    target = vault.Vault(a, vault_id)
    (target.repo.work / "files" / saved["path"]).unlink()
    answer = _ai_run(a, dataset, AIDC, Scripted({"candidates": []}))
    _refused(answer, 400, "profile_missing")


# -- rebuilt from units ---------------------------------------------------------------


def _source(sha: str, folder: str) -> dict[str, Any]:
    return {
        "id": sha,
        "name": f"{sha}.md",
        "folder": folder,
        "file": f"{folder}/{sha}.md",
        "bytes": 1,
        "markdown": [],
    }


def _evidence(source: str) -> list[dict[str, Any]]:
    return [
        {
            "run_id": "r1",
            "source_id": source,
            "source_name": "x",
            "locator": {"line_start": 1},
            "excerpt": "x",
            "basis": "fact",
            "at": "2026-11-04T00:00:00+00:00",
        }
    ]


def _card(key: str) -> dict[str, Any]:
    return {"type": "Technology", "key": key, "name": key, "synthetic": False}


def _field(value: Any) -> dict[str, Any]:
    return {"value": value, "source": None, "history": None}


def _rebuilt(tmp_path: Path, profiles: dict[str, Any]) -> sqlite3.Connection:
    name = _reg().types["Technology"].naming_field
    units: dict[str, Any] = {
        "schema": SCHEMA,
        "source:a": _source("aaa", AIDC),
        "source:o": _source("old", "sources/applications/uav"),
        "source:w": _source("www", "applications/wireless/sources"),
        "source:l": _source("lib", "library/products/sources"),
        "source:n": _source("non", "sources"),
    }
    for card, sources in {
        "one": ["aaa"],
        "two": ["aaa", "www"],
        "valued": ["aaa"],
        "entry": ["lib"],
        "old": ["old"],
        "unhomed": ["non"],
        "bare": [],
    }.items():
        units[f"card:{card}"] = _card(card)
        units[f"field:{card}:{name}"] = _field(card)
        if sources:
            units[f"evidence:{card}:{name}"] = [e for s in sources for e in _evidence(s)]
    units["field:valued:usage"] = _field("x")
    units[f"field:valued:{_unused()}"] = _field("x")
    db = sqlite3.connect(tmp_path / "bi.sqlite", isolation_level=None)
    vault.materialize(db, units, [], [], _reg(), profiles)
    return db


def _unused() -> str:
    entity = _reg().types["Technology"]
    name: str = next(
        f.name
        for f in entity.fields
        if f.klass != "derived"
        and not f.required
        and f.name not in {*entity.naming, *profile.ALWAYS_FIELDS, "domain"}
    )
    return name


def _homes(db: sqlite3.Connection) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for card, home in db.execute("SELECT card_id, application FROM card_app_folders ORDER BY 1, 2"):
        found.setdefault(card, []).append(home)
    return found


def _states(db: sqlite3.Connection, card: str) -> set[str]:
    return {
        r[0]
        for r in db.execute(
            "SELECT field FROM field_states WHERE card_id = ? AND origin = 'profile' AND state = ?",
            (card, card_model.NOT_APPLICABLE),
        )
    }


def test_a_card_belongs_to_the_homes_of_its_evidence(tmp_path: Path) -> None:
    db = _rebuilt(tmp_path, {})
    assert _homes(db) == {
        "one": ["aidc"],
        "two": ["aidc", "wireless"],
        "valued": ["aidc"],
        "entry": ["library/products"],
        "old": ["uav"],
    }


def test_with_no_profile_nothing_is_computed(tmp_path: Path) -> None:
    db = _rebuilt(tmp_path, {})
    assert db.execute("SELECT COUNT(*) FROM field_states").fetchone()[0] == 0


def test_a_field_no_home_uses_is_not_applicable(tmp_path: Path) -> None:
    unused = _unused()
    db = _rebuilt(tmp_path, {"aidc": PROFILE})
    states = _states(db, "one")
    assert unused in states
    assert "domain" not in states  # the profile uses it
    entity = _reg().types["Technology"]
    for name in (*entity.naming, *profile.ALWAYS_FIELDS):
        assert name not in states
    assert not any(f.klass == "derived" and f.name in states for f in entity.fields)
    assert not any(f.required and f.name in states for f in entity.fields)
    # A value stands; a state would say the opposite of it.
    assert unused not in _states(db, "valued")
    # A home with no profile: not every home has one, so nothing is computed.
    assert _states(db, "two") == set()
    # A card in no home reads `unknown`.
    assert _states(db, "unhomed") == set() and _states(db, "bare") == set()


def test_a_type_the_profile_leaves_out_is_not_used_there(tmp_path: Path) -> None:
    db = _rebuilt(tmp_path, {"aidc": {"types": {"Signal": {"fields": {}}}}})
    states = _states(db, "one")
    assert "domain" in states and _unused() in states
    assert _reg().types["Technology"].naming_field not in states


def test_a_field_one_of_two_homes_uses_is_not_computed(tmp_path: Path) -> None:
    both = {"types": {"Technology": {"fields": {_unused(): {"use": "optional"}}}}}
    db = _rebuilt(tmp_path, {"aidc": PROFILE, "wireless": both})
    states = _states(db, "two")
    assert "domain" not in states and _unused() not in states
    assert states  # another field neither uses


def test_a_computed_state_is_never_a_unit(tmp_path: Path) -> None:
    db = _rebuilt(tmp_path, {"aidc": PROFILE})
    db.row_factory = sqlite3.Row
    assert _states(db, "one")
    assert not [k for k in vault.units_from_db(db) if k.startswith(card_model.STATE_PREFIX)]


def test_publish_reports_what_a_profile_requires_and_never_blocks(tmp_path: Path) -> None:
    db = _rebuilt(tmp_path, {"aidc": PROFILE})
    assert profile.missing_required(db, {"aidc": PROFILE}) == [
        {"home": "aidc", "type": "Technology", "field": "domain", "cards": 3}
    ]
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path / "pcs")
    _save(a, vault_id)
    _commit(a, vault_id, "profile")
    _push(a, vault_id)
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "first"}))
    done = _ok(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True})
    )
    assert done["profile_required_missing"] == []
    assert done["published"]["tag"] == "v1"
