"""A profile's field proposal into the schema (`BI_CARD_MODEL.md` §4.3). Fictional data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _ok, _push, _refused, _two_pcs

from aep_bi.cards import catalog, vault
from aep_bi.cards.store import BiStore

V5 = "bi.schema/v1.1@5.0.0"
FIELD = {"kind": "str", "class": "sourced", "label": "冷卻方式"}


def _proposal(field: str = "cooling", definition: Any = None) -> dict[str, Any]:
    return {
        "type": "Technology",
        "field": field,
        "definition": FIELD if definition is None else definition,
        "reason": "液冷是這個應用的重點",
    }


def _propose(ws: Path, vault_id: str, *proposals: dict[str, Any], home: str = "aidc") -> None:
    document = {"types": {"Technology": {"fields": {}}}, "proposals": list(proposals)}
    body = {"home": home, "profile": document}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/profiles", body))


def _decide(ws: Path, vault_id: str, **more: Any) -> Any:
    body = {
        "home": "aidc",
        "type": "Technology",
        "field": "cooling",
        "decision": "merge",
        "confirm": True,
        **more,
    }
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/profile-proposals", body)


def _profile(ws: Path, vault_id: str, home: str = "aidc") -> dict[str, Any]:
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/profiles"))["profiles"]
    return next(p for p in listed if p["home"] == home)


def _reg(ws: Path, dataset: str) -> Any:
    return catalog.for_store(BiStore(ws, dataset))


def test_a_new_name_merges_on_the_reviewers_confirmation(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _propose(a, vault_id, _proposal())
    done = _ok(_decide(a, vault_id))
    assert done["schema"] != V5 and done["schema"].startswith("bi.schema/v1.1@5.")
    reg = _reg(a, dataset)
    assert reg.ref == done["schema"]
    item = reg.types["Technology"].get("cooling")
    assert item is not None and item.kind == "str"
    raw = next(
        f
        for t in reg.document["types"]
        if t["name"] == "Technology"
        for f in t["fields"]
        if f["name"] == "cooling"
    )
    assert raw["used_by"] == ["aidc"]
    written = _profile(a, vault_id)
    assert written["revision"] == 2 and written["schema"] == reg.ref
    assert written["proposals"][0]["status"] == "merged"
    assert written["types"]["Technology"]["fields"]["cooling"] == {"use": "optional"}
    # It goes out as any schema change: the other PC gets the file and the version.
    _commit(a, vault_id, "合併欄位")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _ok(_call(b, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))
    assert _reg(b, dataset).ref == reg.ref


def test_the_same_name_with_another_definition_stops_for_a_person(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    other = {"kind": "enum", "class": "sourced", "label": "x", "enum": ["a"]}
    _propose(a, vault_id, _proposal("standard_body", other))
    answer = _decide(a, vault_id, field="standard_body")
    refused = _refused(answer, 409, "schema_conflict")
    assert "kind" in refused["differs"]
    assert _reg(a, dataset).ref == V5
    written = _profile(a, vault_id)
    assert written["revision"] == 1 and written["proposals"][0]["status"] == "proposed"


def test_the_same_name_and_definition_only_records_the_home(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _propose(a, vault_id, _proposal())
    _ok(_decide(a, vault_id))
    first = _reg(a, dataset).ref
    _propose(a, vault_id, _proposal(), home="wireless")
    done = _ok(_decide(a, vault_id, home="wireless"))
    reg = _reg(a, dataset)
    assert done["schema"] == reg.ref and reg.ref != first
    raw = next(
        f
        for t in reg.document["types"]
        if t["name"] == "Technology"
        for f in t["fields"]
        if f["name"] == "cooling"
    )
    assert raw["used_by"] == ["aidc", "wireless"]
    assert raw["kind"] == "str"
    # Asked again with nothing new: no new version.
    _propose(a, vault_id, _proposal(), home="wireless")
    assert _ok(_decide(a, vault_id, home="wireless"))["schema"] == reg.ref


def test_a_rejected_proposal_changes_no_schema(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _propose(a, vault_id, _proposal())
    assert _ok(_decide(a, vault_id, decision="reject"))["schema"] == V5
    assert _reg(a, dataset).types["Technology"].get("cooling") is None
    written = _profile(a, vault_id)
    assert written["proposals"][0]["status"] == "rejected"
    assert "cooling" not in written["types"]["Technology"]["fields"]
    # Decided once; it is not asked again.
    _refused(_decide(a, vault_id), 404, "proposal_unknown")


def test_a_merge_needs_a_persons_confirm_and_a_real_proposal(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _propose(a, vault_id, _proposal())
    _refused(_decide(a, vault_id, confirm=False), 400, "confirm_required")
    _refused(_decide(a, vault_id, decision="maybe"), 400, "decision_invalid")
    _refused(_decide(a, vault_id, field="other"), 404, "proposal_unknown")
    _refused(_decide(a, vault_id, home="wireless"), 404, "proposal_unknown")
    assert _reg(a, dataset).ref == V5


def test_an_invalid_definition_changes_nothing(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _propose(a, vault_id, _proposal(definition={"kind": "no-such-kind"}))
    status, payload = _decide(a, vault_id)
    assert status >= 400 and not payload.get("ok")
    assert _reg(a, dataset).ref == V5
    assert _profile(a, vault_id)["proposals"][0]["status"] == "proposed"


def test_a_written_skill_is_named_when_the_merge_leaves_it_behind(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    rule = {"name": "power-extract", "role": "extract", "body": "記得填 cooling。", "home": "aidc"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/skills", rule))
    other = {"name": "other-extract", "role": "extract", "body": "虛構規則。", "home": "wireless"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/skills", other))
    _propose(a, vault_id, _proposal())
    done = _ok(_decide(a, vault_id))
    # Only the skill the new field touches: an addition elsewhere flags nothing (§4.3).
    assert done["skills_need_update"] == ["aidc/power-extract"]
    target = vault.Vault(a, vault_id)
    assert "skill:aidc/power-extract" in target.repo.working_units()
