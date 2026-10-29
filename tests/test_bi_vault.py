"""BI vaults phase V4 (owner 2026-10-28; `docs/phases/BI_VAULT.md` §3, §4).

Every PC is its own temporary workspace with its own copy of the vault folder;
`_Drive.deliver` plays OneDrive, copying change files between the copies, so a
test decides exactly which files each PC has seen when it writes. The cards of
two PCs with the same files must be identical, table by table. All data is
fictional.
"""

from __future__ import annotations

import copy
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards import catalog, vault
from capabilities.bi_cards.store import BiStore, PlannedRow, datasets
from host_runtime.bi_cards_api import route

EXAMPLE = "example/product-spec@1.0.0"


class _Drive:
    """Per-PC copies of one shared vault folder and a manual OneDrive."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.copies: dict[str, Path] = {}

    def workspace(self, pc: str) -> Path:
        path = self.root / pc / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def parent(self, pc: str) -> Path:
        path = self.root / pc / "OneDrive - Fictional Co"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def clone(self, source_pc: str, pc: str, vault_id: str) -> Path:
        """A new PC receives the whole folder."""
        target = self.parent(pc) / vault_id
        shutil.copytree(self.parent(source_pc) / vault_id, target)
        return target

    def deliver(self, source_pc: str, pc: str, vault_id: str, only: str | None = None) -> None:
        """Copy the change files (and schemas) `pc` has not got yet; `only`
        delivers just one `<author>/<seq>.json`."""
        source = self.parent(source_pc) / vault_id
        target = self.parent(pc) / vault_id
        for folder in ("changes", "schemas"):
            for path in sorted((source / folder).rglob("*.json")):
                relative = path.relative_to(source)
                if only is not None and relative.as_posix() != f"changes/{only}":
                    continue
                if not (target / relative).exists():
                    (target / relative).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target / relative)


def _call(
    ws: Path, method: str, path: str, body: Any = None, actor: str = "tester", **q: str
) -> Any:
    return route(ws, actor, method, path, q, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _refused(answer: Any, status: int, code: str) -> dict[str, Any]:
    assert (answer[0], answer[1].get("code")) == (status, code), answer
    return dict(answer[1])


def _tables(ws: Path, dataset: str) -> dict[str, list[tuple[Any, ...]]]:
    """Every card table of a PC, to compare PCs exactly."""
    path = BiStore(ws, dataset).path
    with sqlite3.connect(path) as db:
        return {
            table: sorted(tuple(r) for r in db.execute(f"SELECT * FROM {table}"))
            for table in (
                "cards",
                "fields",
                "history",
                "proposals",
                "evidence",
                "imports",
                "meta",
                "vault_pkeys",
                "vault_conflicts",
            )
        }


def _row(key: str, **values: Any) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type="Technology",
        canonical_key=key,
        name=key,
        values={"name": key, **values},
        synthetic=False,
    )


def _two_pcs(tmp_path: Path) -> tuple[_Drive, str, str, Path, Path]:
    """PC a creates a vault (author alice); PC b joins it (author bob)."""
    drive = _Drive(tmp_path)
    a, b = drive.workspace("a"), drive.workspace("b")
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(drive.parent("a")),
                "title": "Market Signals",
                "purpose": "虛構測試：市場訊號與產品對應",
                "schema": "bi.schema/v1.1",
                "author": "alice",
            },
        )
    )
    vault_id = made["vault"]["id"]
    folder = drive.clone("a", "b", vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "bob"}))
    return drive, vault_id, vault.dataset_name(vault_id), a, b


def _sync(ws: Path, vault_id: str) -> dict[str, Any]:
    return dict(_ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))["sync"])


def _status(ws: Path, vault_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/status"))


def _card(ws: Path, dataset: str, key: str) -> dict[str, Any]:
    store = BiStore(ws, dataset)
    found = store.find("Technology", key)
    assert found is not None
    return {"id": found["id"], "version": found["version"], "fields": store.fields(found["id"])}


def _edit(ws: Path, dataset: str, key: str, field: str, value: Any, actor: str) -> Any:
    card = _card(ws, dataset, key)
    return _call(
        ws,
        "POST",
        f"/api/bi/cards/{card['id']}/field",
        {"dataset": dataset, "field": field, "value": value, "base_version": card["version"]},
        actor=actor,
    )


def _changes(drive: _Drive, pc: str, vault_id: str) -> list[str]:
    root = drive.parent(pc) / vault_id / "changes"
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*.json"))


def test_create_lays_out_the_folder_and_join_checks_it(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    folder = drive.parent("a") / vault_id
    document = json.loads((folder / "vault.json").read_text(encoding="utf-8"))
    assert document["format"] == "bi.vault/v1" and document["id"] == vault_id
    assert document["schema"] == "bi.schema/v1.1@2.0.0"  # the newest shipped version
    assert len(document["folders"]["applications"]) == 11
    assert (folder / "VAULT.md").read_text(encoding="utf-8").startswith("# Market Signals")
    for name in ("applications/robotics-amr/sources", "library/competitors/sources"):
        assert (folder / name).is_dir()
    assert (folder / "schemas").is_dir() and (folder / "skills").is_dir()
    assert _changes(drive, "a", vault_id) == ["alice/1.json"]
    # No database is ever in the shared folder.
    assert not [p for p in folder.rglob("*") if p.suffix in (".sqlite", ".db")]
    assert dataset in datasets(a) and dataset in datasets(b)
    assert BiStore(b, dataset).schema_ref() == "bi.schema/v1.1@2.0.0"
    listed = _ok(_call(b, "GET", "/api/bi/vaults"))["vaults"]
    assert [(v["id"], v["author"], v["title"]) for v in listed] == [
        (vault_id, "bob", "Market Signals")
    ]
    # Joining checks the folder and keeps authors apart.
    _refused(_call(b, "POST", "/api/bi/vaults/join", {"path": str(tmp_path)}), 400, "vault_invalid")
    c = drive.workspace("c")
    other = drive.clone("a", "c", vault_id)
    body = {"path": str(other), "author": "alice"}
    _refused(_call(c, "POST", "/api/bi/vaults/join", body), 409, "author_taken")
    _ok(_call(c, "POST", "/api/bi/vaults/join", {**body, "resume": True}))
    _refused(
        _call(
            a,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(drive.parent("a")),
                "title": "x",
                "id": vault_id,
                "schema": "bi.schema/v1.1",
            },
        ),
        409,
        "vault_exists",
    )
    # A plain dataset may not take a vault's name.
    _refused(
        _call(a, "POST", "/api/bi/datasets", {"name": "vault-x", "schema": "bi.schema/v1.1"}),
        400,
        "dataset_invalid",
    )


def test_a_write_is_one_change_file_and_every_pc_builds_the_same_cards(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE"), _row("EtherCAT")],
        filename="tech.csv",
        entity_type="Technology",
        actor="alice via web",
    )
    assert _changes(drive, "a", vault_id) == ["alice/1.json", "alice/2.json"]
    written = json.loads(
        (drive.parent("a") / vault_id / "changes/alice/2.json").read_text(encoding="utf-8")
    )
    assert (written["author"], written["seq"], written["clock"]) == ("alice", 2, 2)
    assert written["action"] == "import"
    field = next(o for o in written["ops"] if o["op"] == "field" and o["field"] == "standard_body")
    assert field["base"] is None and field["value"] == "IEEE"
    assert field["source"]["ref"] == "tech.csv#row1"
    drive.deliver("a", "b", vault_id)
    report = _sync(b, vault_id)
    assert (report["applied"], report["rebuilt"]) == (1, False)
    assert _tables(a, dataset) == _tables(b, dataset)
    status = _status(b, vault_id)
    assert (status["files"], status["applied"], status["behind"]) == (2, 2, 0)
    # A person's edit on b reaches a; a sync with nothing new changes nothing.
    _ok(_edit(b, dataset, "TSN", "standard_body", "IEEE 802.1", "bob"))
    drive.deliver("b", "a", vault_id)
    assert _sync(a, vault_id)["applied"] == 1
    assert _card(a, dataset, "TSN")["fields"]["standard_body"]["kind"] == "human"
    assert _tables(a, dataset) == _tables(b, dataset)
    assert _sync(a, vault_id)["applied"] == 0


def test_concurrent_edits_of_one_field_become_one_value_and_one_proposal(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE")], filename="t.csv", entity_type="Technology", actor="a"
    )
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    # Both edit before OneDrive brings the other's file.
    _ok(_edit(a, dataset, "TSN", "standard_body", "IEEE 802.1", "alice"))
    _ok(_edit(b, dataset, "TSN", "standard_body", "IETF", "bob"))
    drive.deliver("a", "b", vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)
    assert _tables(a, dataset) == _tables(b, dataset)
    for ws in (a, b):
        card = _card(ws, dataset, "TSN")
        # Same clock: alice sorts first and wins; bob's value waits for a person.
        assert card["fields"]["standard_body"]["value"] == "IEEE 802.1"
        proposals = BiStore(ws, dataset).proposals(card["id"])
        assert [(p["field"], p["value"]) for p in proposals] == [("standard_body", "IETF")]
        conflicts = _status(ws, vault_id)["conflicts"]
        assert [(c["kind"], c["field"], c["open"]) for c in conflicts] == [
            ("field", "standard_body", True)
        ]
        assert conflicts[0]["detail"]["author"] == "bob"
    # A person accepts bob's value on b: a new change file, closed for everyone.
    card = _card(b, dataset, "TSN")
    proposal = BiStore(b, dataset).proposals(card["id"])[0]
    _ok(
        _call(
            b,
            "POST",
            f"/api/bi/cards/{card['id']}/proposals/{proposal['id']}",
            {"dataset": dataset, "action": "accept", "base_version": card["version"]},
            actor="bob",
        )
    )
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    assert _card(a, dataset, "TSN")["fields"]["standard_body"]["value"] == "IETF"
    assert BiStore(a, dataset).proposals(card["id"]) == []
    assert _status(a, vault_id)["conflicts"][0]["open"] is False
    assert _tables(a, dataset) == _tables(b, dataset)


def test_concurrent_edits_of_different_fields_are_both_applied(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE")], filename="t.csv", entity_type="Technology", actor="a"
    )
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    version = _card(a, dataset, "TSN")["version"]
    _ok(_edit(a, dataset, "TSN", "standard_body", "IEEE 802.1", "alice"))
    _ok(_edit(b, dataset, "TSN", "body", "虛構備註", "bob"))
    drive.deliver("a", "b", vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)
    assert _tables(a, dataset) == _tables(b, dataset)
    card = _card(a, dataset, "TSN")
    assert card["fields"]["standard_body"]["value"] == "IEEE 802.1"
    assert card["fields"]["body"]["value"] == "虛構備註"
    assert card["version"] == version + 2
    assert _status(a, vault_id)["conflicts"] == []


def test_a_late_file_with_an_earlier_key_rebuilds_and_every_pc_converges(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    c = drive.workspace("c")
    folder = drive.clone("a", "c", vault_id)
    _ok(_call(c, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "carol"}))
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE")], filename="a.csv", entity_type="Technology", actor="a"
    )
    BiStore(b, dataset).apply(
        [_row("TSN", standard_body="IETF"), _row("PTP")],
        filename="b.csv",
        entity_type="Technology",
        actor="b",
    )
    # c gets bob's file first, then alice's: (2, alice) sorts before (2, bob).
    drive.deliver("b", "c", vault_id)
    first = _sync(c, vault_id)
    assert (first["applied"], first["rebuilt"]) == (1, False)
    drive.deliver("a", "c", vault_id)
    second = _sync(c, vault_id)
    assert second["rebuilt"] is True
    for pc in ("a", "b"):
        for other in ("a", "b"):
            if pc != other:
                drive.deliver(pc, other, vault_id)
    _sync(a, vault_id)
    _sync(b, vault_id)
    assert _tables(a, dataset) == _tables(b, dataset) == _tables(c, dataset)
    # Same type and key created twice: one card, flagged for a person.
    assert len(BiStore(c, dataset).card_rows()) == 2
    merges = _status(c, vault_id)["merges"]
    assert [(m["detail"]["type"], m["detail"]["key"]) for m in merges] == [("Technology", "TSN")]
    card = _card(c, dataset, "TSN")
    assert card["fields"]["standard_body"]["value"] == "IEEE"
    assert [p["value"] for p in BiStore(c, dataset).proposals(card["id"])] == ["IETF"]


def test_a_run_id_is_applied_once(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    csv = "技術,標準組織\nTSN,IEEE\nPTP,IEEE\n"
    source = _ok(
        _call(a, "POST", "/api/bi/sources", {"dataset": dataset, "name": "t.csv", "text": csv})
    )["source"]
    run = _ok(
        _call(
            a,
            "POST",
            "/api/bi/runs",
            {
                "dataset": dataset,
                "kind": "ingest",
                "source_id": source["id"],
                "entity_type": "Technology",
            },
        )
    )["run"]
    detail = _ok(_call(a, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))
    for candidate in detail["candidates"]:
        _ok(
            _call(
                a,
                "POST",
                f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
                {"dataset": dataset, "review": "accepted"},
            )
        )
    committed = _ok(_call(a, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))
    assert committed["applied"]["created"] == 2
    again = _ok(_call(a, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": dataset}))
    assert again.get("already") is True
    root = drive.parent("a") / vault_id / "changes" / "alice"
    written = json.loads((root / "2.json").read_text(encoding="utf-8"))
    assert written["action"] == "commit_run" and written["run_id"] == run["id"]
    assert any(o["op"] == "evidence" for o in written["ops"])
    # The same run arrives a second time (a copied file): applied once.
    duplicate = {**copy.deepcopy(written), "seq": 3, "clock": written["clock"] + 1}
    (root / "3.json").write_text(json.dumps(duplicate), encoding="utf-8")
    report = _sync(a, vault_id)
    assert report["outcomes"] == {"duplicate_run": 1}
    assert len(BiStore(a, dataset).card_rows()) == 2
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert _tables(a, dataset) == _tables(b, dataset)
    skipped = _status(b, vault_id)["skipped"]
    assert [(s["file"], s["outcome"]) for s in skipped] == [("alice/3", "duplicate_run")]
    card = _card(b, dataset, "TSN")
    assert BiStore(b, dataset).evidence(card["id"])[0]["excerpt"]


def test_a_half_written_file_waits_and_a_malformed_one_is_reported(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE")], filename="t.csv", entity_type="Technology", actor="a"
    )
    source = drive.parent("a") / vault_id / "changes" / "alice" / "2.json"
    target = drive.parent("b") / vault_id / "changes" / "alice" / "2.json"
    content = source.read_bytes()
    target.write_bytes(content[: len(content) // 2])  # OneDrive still downloading
    bad_dir = drive.parent("b") / vault_id / "changes" / "mallory"
    bad_dir.mkdir()
    (bad_dir / "1.json").write_text(json.dumps({"format": "bi.vault.change/v1"}), encoding="utf-8")
    (bad_dir / "notes.json").write_text("{}", encoding="utf-8")
    report = _sync(b, vault_id)
    assert report["applied"] == 0
    assert [i["file"] for i in report["incomplete"]] == ["alice/2.json"]
    assert sorted(i["file"] for i in report["bad"]) == ["mallory/1.json", "mallory/notes.json"]
    assert BiStore(b, dataset).find("Technology", "TSN") is None
    status = _status(b, vault_id)
    assert len(status["bad"]) == 2 and len(status["incomplete"]) == 1
    # The download finishes: picked up on the next sync; the bad files stay reported.
    target.write_bytes(content)
    report = _sync(b, vault_id)
    assert report["applied"] == 1 and len(report["bad"]) == 2
    assert _tables(a, dataset) == _tables(b, dataset)


def test_undo_and_a_schema_upgrade_travel_as_change_files(tmp_path: Path) -> None:
    drive = _Drive(tmp_path)
    a, b = drive.workspace("a"), drive.workspace("b")
    example = catalog.example()
    _ok(_call(a, "POST", "/api/bi/schemas/install", example["schema"]))
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(drive.parent("a")),
                "title": "Specs",
                "schema": EXAMPLE,
                "author": "alice",
            },
        )
    )
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    assert (drive.parent("a") / vault_id / "schemas" / "example__product-spec@1.0.0.json").is_file()
    store = BiStore(a, dataset)
    store.apply(
        [
            PlannedRow(
                row=1,
                entity_type="Supplier",
                canonical_key="虛構電子",
                name="虛構電子",
                values={"name": "虛構電子", "country": "TW"},
                synthetic=True,
            )
        ],
        filename="s.csv",
        entity_type="Supplier",
        actor="alice via web",
    )
    second = store.apply(
        [
            PlannedRow(
                row=1,
                entity_type="Supplier",
                canonical_key="範例零件",
                name="範例零件",
                values={"name": "範例零件", "country": "JP"},
                synthetic=True,
            )
        ],
        filename="s2.csv",
        entity_type="Supplier",
        actor="alice via web",
    )
    _ok(
        _call(a, "POST", "/api/bi/import/undo", {"dataset": dataset, "import_id": second.import_id})
    )
    assert store.find("Supplier", "範例零件") is None
    # A new schema version with a declared rename, then the dataset upgrade.
    draft = _ok(_call(a, "POST", "/api/bi/schema-drafts", {"base": EXAMPLE, "title": "v2"}))
    document = copy.deepcopy(draft["document"])
    supplier = next(t for t in document["types"] if t["name"] == "Supplier")
    supplier["fields"] = [f for f in supplier["fields"] if f["name"] != "country"]
    supplier["fields"].append(
        {"name": "region", "label": "地區", "kind": "str", "class": "sourced"}
    )
    document["migrations"] = {"renames": {"Supplier.country": "region"}}
    draft_id = draft["draft"]["id"]
    _ok(_call(a, "POST", f"/api/bi/schema-drafts/{draft_id}/revisions", {"document": document}))
    target = _ok(_call(a, "POST", f"/api/bi/schema-drafts/{draft_id}/publish", {}))["ref"]
    preview = _ok(_call(a, "POST", f"/api/bi/datasets/{dataset}/schema/preview", {"to": target}))
    body = {"to": target, "preview_token": preview["preview_token"]}
    _ok(_call(a, "POST", f"/api/bi/datasets/{dataset}/schema/apply", body))
    actions = [
        json.loads(p.read_text(encoding="utf-8"))["action"]
        for p in sorted((drive.parent("a") / vault_id / "changes" / "alice").glob("*.json"))
    ]
    assert actions == ["create", "import", "import", "undo_import", "upgrade_schema"]
    # A PC without either schema joins: it installs them from the folder.
    folder = drive.clone("a", "b", vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "bob"}))
    assert BiStore(b, dataset).schema_ref() == target
    assert catalog.for_store(BiStore(b, dataset)).ref == target
    card = _card_of(b, dataset, "Supplier", "虛構電子")
    assert card["fields"]["region"]["value"] == "TW" and "country" not in card["fields"]
    assert BiStore(b, dataset).find("Supplier", "範例零件") is None
    assert _tables(a, dataset) == _tables(b, dataset)


def _card_of(ws: Path, dataset: str, entity_type: str, key: str) -> dict[str, Any]:
    store = BiStore(ws, dataset)
    found = store.find(entity_type, key)
    assert found is not None
    return {"id": found["id"], "fields": store.fields(found["id"])}


def test_a_dataset_converts_to_a_vault_with_its_history(tmp_path: Path) -> None:
    drive = _Drive(tmp_path)
    a, b = drive.workspace("a"), drive.workspace("b")
    _ok(_call(a, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    store = BiStore(a, "lab")
    store.apply(
        [_row("TSN", standard_body="IEEE")], filename="t.csv", entity_type="Technology", actor="x"
    )
    card = _card(a, "lab", "TSN")
    store.set_field(
        card["id"], "standard_body", "IEEE 802.1", base_version=card["version"], actor="p"
    )
    store.apply(
        [_row("TSN", standard_body="IETF")], filename="u.csv", entity_type="Technology", actor="x"
    )
    lab_bytes = store.path.read_bytes()
    made = _ok(
        _call(
            a,
            "POST",
            "/api/bi/vaults/convert",
            {
                "dataset": "lab",
                "path": str(drive.parent("a")),
                "author": "alice",
                "purpose": "虛構",
            },
        )
    )
    assert store.path.read_bytes() == lab_bytes  # the dataset itself is left as it was
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    assert _changes(drive, "a", vault_id) == ["alice/1.json"]
    converted = BiStore(a, dataset)
    assert converted.schema_ref() == store.schema_ref()
    original = store.find("Technology", "TSN")
    copied = converted.find("Technology", "TSN")
    assert original is not None and copied is not None
    assert dict(copied) == dict(original)
    assert converted.fields(copied["id"]) == store.fields(original["id"])
    assert converted.history(copied["id"]) == store.history(original["id"])
    assert [p["value"] for p in converted.proposals(copied["id"])] == ["IETF"]
    folder = drive.clone("a", "b", vault_id)
    _ok(_call(b, "POST", "/api/bi/vaults/join", {"path": str(folder), "author": "bob"}))
    assert _tables(a, dataset) == _tables(b, dataset)
    # The proposal kept from the dataset is decided in the vault like any other.
    proposal = BiStore(b, dataset).proposals(copied["id"])[0]
    _ok(
        _call(
            b,
            "POST",
            f"/api/bi/cards/{copied['id']}/proposals/{proposal['id']}",
            {"dataset": dataset, "action": "reject"},
        )
    )
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    assert converted.proposals(copied["id"]) == []
    assert _tables(a, dataset) == _tables(b, dataset)


def test_a_plain_dataset_is_written_as_before(tmp_path: Path) -> None:
    _ok(_call(tmp_path, "POST", "/api/bi/demo/load", {"dataset": "demo"}))
    assert not (tmp_path / "bi" / "vaults").exists()
    assert BiStore(tmp_path, "demo").vault_id is None
    assert datasets(tmp_path) == ["demo"]
    with sqlite3.connect(BiStore(tmp_path, "demo").path) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert not any(t.startswith("vault_") for t in tables)


def test_an_unreachable_folder_refuses_writes(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    shutil.rmtree(drive.parent("b") / vault_id)
    with pytest.raises(Exception) as caught:
        BiStore(b, dataset).apply(
            [_row("TSN")], filename="t.csv", entity_type="Technology", actor="b"
        )
    assert getattr(caught.value, "code", "") == "vault_unreachable"
    _refused(_call(b, "POST", f"/api/bi/vaults/{vault_id}/sync", {}), 409, "vault_unreachable")
    assert _status(b, vault_id)["reachable"] is False
    _refused(_call(b, "GET", "/api/bi/vaults/nope/status"), 404, "vault_unknown")
