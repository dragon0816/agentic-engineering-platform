"""The BI dataset snapshot `aep-bi-dataset-snapshot/1` (BI dataset sharing slice 1).

Requirements: `docs/proposals/BI_DATASET_SHARING.md` §4.5 and §8.2 item 1,
owner answers of 2026-10-22 (§8.5 Q3), contract `docs/CONTRACTS.md` "BI
dataset sharing": deterministic digest, proposals left out, folders reduced
to file names, actors mapped to platform accounts, a credential fails the
build naming card and field but never the value, strict reading, and an
install that writes nothing when it fails.
"""

from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from aep_bi.cards import catalog, service, snapshot
from aep_bi.cards.snapshot import (
    Publication,
    SnapshotError,
    build_snapshot,
    install_schema,
    install_snapshot,
    read_snapshot,
    schema_state,
    stamp_publication,
)
from aep_bi.cards.store import BiStore, PlannedRow

FOLDER_FILE = "C:\\Users\\leo.chi\\Documents\\secret-project\\customers.csv"


def planned(key: str, **values: Any) -> PlannedRow:
    return PlannedRow(
        row=2, entity_type="Customer", canonical_key=key, name=key, values=values, synthetic=False
    )


def owner_dataset(workspace: Path, name: str = "sales") -> BiStore:
    """Two imports from a folder path, one human edit, and a later import
    that conflicts with the edit and so becomes a pending proposal."""
    store = BiStore(workspace, name)
    store.apply(
        [planned("acme", region="TW", tier="A"), planned("globex", region="JP")],
        filename=FOLDER_FILE,
        entity_type="Customer",
        actor="leo",
    )
    card = store.find("Customer", "acme")
    assert card is not None
    store.set_field(card["id"], "tier", "B", base_version=1, actor="leo", reason="met them")
    result = store.apply(
        [planned("acme", tier="C")],
        filename="D:/exports/customers.csv",
        entity_type="Customer",
        actor="leo",
    )
    assert result.proposals == 1
    return store


def document_of(data: bytes) -> dict[str, Any]:
    loaded = json.loads(gzip.decompress(data))
    assert isinstance(loaded, dict)
    return loaded


def regzip(document: dict[str, Any]) -> bytes:
    return gzip.compress(snapshot.canonical_json(document), mtime=0)


def test_the_same_dataset_gives_the_same_bytes_and_digest(tmp_path: Path) -> None:
    store = owner_dataset(tmp_path / "a")
    first, second = build_snapshot(store), build_snapshot(store)
    assert first == second
    # The same database in another workspace (another user, another folder).
    copy = tmp_path / "b" / "bi" / "sales"
    copy.mkdir(parents=True)
    shutil.copy(store.path, copy / "bi.sqlite")
    elsewhere = build_snapshot(BiStore(tmp_path / "b", "sales"))
    assert elsewhere == first
    read = read_snapshot(first)
    assert read.digest == snapshot.content_digest(document_of(first))
    assert read.dataset == "sales" and read.cards == 2
    assert read.schema_ref == "bi.schema/v1.1@1.1.0" and read.schema_source == "shipped"
    assert read.schema_document["schema_id"] == "bi.schema/v1.1"
    assert read.stats["cards_by_type"] == {"Customer": 2}


def test_the_demo_dataset_round_trips(tmp_path: Path) -> None:
    store = BiStore(tmp_path, "demo")
    service.load_demo(store)
    data = build_snapshot(store)
    assert data == build_snapshot(store)
    read = read_snapshot(data)
    assert read.cards == len(store.card_rows()) == 104


def test_proposals_folders_and_actor_names_are_stripped(tmp_path: Path) -> None:
    store = owner_dataset(tmp_path)
    data = build_snapshot(store, accounts={"leo": "leo.chi"})
    document = document_of(data)
    text = data.decode("latin-1") + json.dumps(document, ensure_ascii=False)
    assert "proposals" not in document
    assert '"C"' not in json.dumps([c["fields"] for c in document["cards"]])
    assert "secret-project" not in json.dumps(document) and "exports" not in json.dumps(document)
    assert "Users" not in text
    acme = next(c for c in document["cards"] if c["canonical_key"] == "acme")
    assert acme["fields"]["region"]["ref"] == "customers.csv#row2"
    assert acme["fields"]["tier"]["ref"] == "agent-web:leo.chi"
    assert {f["by"] for f in acme["fields"].values()} == {"leo.chi"}
    history = acme["history"]
    assert all(entry["by"] == "leo.chi" for entry in history)
    edit = next(entry for entry in history if entry["kind"] == "human")
    assert edit["old_source"]["ref"] == "customers.csv#row2"
    assert edit["reason"] == "met them"
    assert {item["filename"] for item in document["imports"]} == {"customers.csv"}
    assert {item["by"] for item in document["imports"]} == {"leo.chi"}
    # A name the mapping does not know is kept as it is.
    unmapped = document_of(build_snapshot(store))
    assert {item["by"] for item in unmapped["imports"]} == {"leo"}


def test_a_credential_fails_the_build_naming_card_and_field_not_value(tmp_path: Path) -> None:
    store = owner_dataset(tmp_path)
    card = store.find("Customer", "globex")
    assert card is not None
    store.set_field(card["id"], "notes", "password=hunter2", base_version=1, actor="leo")
    with pytest.raises(SnapshotError) as refused:
        build_snapshot(store)
    assert refused.value.code == "secret_found"
    assert refused.value.card == "Customer:globex" and refused.value.field == "notes"
    assert "hunter2" not in str(refused.value) and "hunter2" not in refused.value.message


def test_a_field_named_for_a_secret_fails_too(tmp_path: Path) -> None:
    store = BiStore(tmp_path, "keys")
    store.apply(
        [planned("acme", api_key="x")], filename="a.csv", entity_type="Customer", actor="leo"
    )
    with pytest.raises(SnapshotError) as refused:
        build_snapshot(store)
    assert (refused.value.code, refused.value.field) == ("secret_found", "api_key")


def test_reading_is_strict_and_checks_the_digest(tmp_path: Path) -> None:
    data = build_snapshot(owner_dataset(tmp_path))
    document = document_of(data)

    tampered = json.loads(json.dumps(document))
    tampered["cards"][0]["name"] = "Someone else"
    with pytest.raises(SnapshotError, match="digest") as refused:
        read_snapshot(regzip(tampered))
    assert refused.value.code == "digest_mismatch"

    extra = json.loads(json.dumps(document))
    extra["cards"][0]["unexpected"] = 1
    extra["digest"] = snapshot.content_digest(extra)
    with pytest.raises(SnapshotError) as refused:
        read_snapshot(regzip(extra))
    assert refused.value.code == "snapshot_invalid"

    proposals = json.loads(json.dumps(document))
    proposals["proposals"] = []
    with pytest.raises(SnapshotError, match="snapshot_invalid|格式"):
        read_snapshot(regzip(proposals))

    secret = json.loads(json.dumps(document))
    secret["cards"][0]["fields"]["region"]["value"] = "api_key: abc123"
    secret["digest"] = snapshot.content_digest(secret)
    with pytest.raises(SnapshotError) as refused:
        read_snapshot(regzip(secret))
    assert refused.value.code == "secret_found" and "abc123" not in str(refused.value)

    folder = json.loads(json.dumps(document))
    folder["imports"][0]["filename"] = "C:\\data\\customers.csv"
    folder["digest"] = snapshot.content_digest(folder)
    with pytest.raises(SnapshotError, match="imports"):
        read_snapshot(regzip(folder))

    for broken in (b"not gzip", gzip.compress(b"[1, 2]"), data + data):
        with pytest.raises(SnapshotError) as refused:
            read_snapshot(broken)
        assert refused.value.code == "snapshot_invalid"
    with pytest.raises(SnapshotError) as refused:
        read_snapshot(data, max_bytes=len(data) - 1)
    assert refused.value.code == "artifact_too_large"


def test_a_compression_bomb_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snapshot, "MAX_SNAPSHOT_JSON_BYTES", 1000)
    with pytest.raises(SnapshotError) as refused:
        read_snapshot(gzip.compress(b" " * 5000))
    assert refused.value.code == "artifact_too_large"


def test_a_publication_stamp_keeps_the_content_digest(tmp_path: Path) -> None:
    read = read_snapshot(build_snapshot(owner_dataset(tmp_path)))
    publication = Publication(
        namespace="engineering",
        name="sales-bi",
        version="1.1.0",
        base_version="1.0.0",
        published_by="leo.chi",
        published_at="2026-10-22T09:00:00+00:00",
        note="monthly refresh",
    )
    stamped = read_snapshot(stamp_publication(read, publication))
    assert stamped.digest == read.digest
    assert stamped.publication == publication
    assert stamped.publication.reference == "engineering/sales-bi@1.1.0"


def test_install_writes_a_read_only_copy_that_reads_like_the_original(tmp_path: Path) -> None:
    owner = owner_dataset(tmp_path / "owner")
    read = read_snapshot(build_snapshot(owner))
    target = tmp_path / "colleague" / "bi" / "subscribed" / "engineering__sales-bi" / "1.0.0"
    installed = install_snapshot(read, target)
    assert installed.path == target and installed.dataset == "sales"
    assert installed.version is None and installed.schema_ref == "bi.schema/v1.1@1.1.0"
    assert sorted(p.name for p in target.iterdir()) == ["bi.sqlite", "snapshot.json"]
    summary = json.loads((target / "snapshot.json").read_text(encoding="utf-8"))
    assert summary["digest"] == read.digest and "cards" not in summary
    connection = sqlite3.connect(target / "bi.sqlite")
    try:
        meta = dict(connection.execute("SELECT key, value FROM meta"))
        assert connection.execute("SELECT COUNT(*) FROM proposals").fetchone()[0] == 0
    finally:
        connection.close()
    assert meta["read_only"] == "1" and meta["snapshot_digest"] == read.digest
    copy = BiStore(tmp_path, "unused")
    copy.dir, copy.path = target, target / "bi.sqlite"
    assert [r["canonical_key"] for r in copy.card_rows()] == ["acme", "globex"]
    card = owner.find("Customer", "acme")
    assert card is not None
    assert copy.fields(card["id"])["tier"]["value"] == "B"
    assert [h["field"] for h in copy.history(card["id"])] == [
        h["field"] for h in owner.history(card["id"])
    ]
    # The copy is itself a valid source of the same snapshot content.
    assert read_snapshot(build_snapshot_from(copy, owner)).digest == read.digest


def build_snapshot_from(copy: BiStore, owner: BiStore) -> bytes:
    """Build from the installed copy as if it were the owner's dataset."""
    view = BiStore(owner.workspace, owner.dataset)
    view.dir, view.path = copy.dir, copy.path
    return build_snapshot(view)


def test_install_validation_failing_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = read_snapshot(build_snapshot(owner_dataset(tmp_path / "owner")))
    parent = tmp_path / "colleague" / "subscribed"

    # A snapshot whose document was changed after reading is refused first.
    forged = snapshot.Snapshot(
        **{**read.__dict__, "document": {**read.document, "dataset": "other"}}
    )
    with pytest.raises(SnapshotError) as refused:
        install_snapshot(forged, parent / "1.0.0")
    assert refused.value.code == "digest_mismatch"
    assert not (parent / "1.0.0").exists()

    # A target already holding something is not touched.
    occupied = parent / "2.0.0"
    occupied.mkdir(parents=True)
    (occupied / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(SnapshotError) as refused:
        install_snapshot(read, occupied)
    assert refused.value.code == "install_target_exists"
    assert [p.name for p in occupied.iterdir()] == ["keep.txt"]

    # A failure while writing leaves neither the target nor the staging folder.
    def broken(path: Path, checked: snapshot.Snapshot) -> None:
        path.write_bytes(b"half")
        raise OSError("disk full")

    monkeypatch.setattr(snapshot, "_write_store", broken)
    with pytest.raises(OSError):
        install_snapshot(read, parent / "3.0.0")
    assert sorted(p.name for p in parent.iterdir()) == ["2.0.0"]


def test_an_installed_schema_travels_and_a_conflict_writes_nothing(tmp_path: Path) -> None:
    owner_ws = tmp_path / "owner"
    example = catalog.example()
    catalog.install(owner_ws, example["schema"]["filename"], example["schema"]["json_text"])
    store = BiStore(owner_ws, "spec")
    store.create("example/product-spec@1.0.0")
    store.apply(
        [
            PlannedRow(
                row=2,
                entity_type="Supplier",
                canonical_key="s1",
                name="S1",
                values={"name": "S1"},
                synthetic=False,
            )
        ],
        filename="suppliers.csv",
        entity_type="Supplier",
        actor="leo",
    )
    read = read_snapshot(build_snapshot(store))
    assert read.schema_source == "installed" and read.schema_ref == "example/product-spec@1.0.0"

    colleague = tmp_path / "colleague"
    assert schema_state(read, colleague) == "missing"
    assert install_schema(read, colleague) == "missing"
    assert schema_state(read, colleague) == "present"
    assert install_schema(read, colleague) == "present"
    assert (
        catalog.resolve(colleague, "example/product-spec@1.0.0").schema_id == "example/product-spec"
    )

    other = tmp_path / "other"
    path = catalog.schema_path(other, "example/product-spec", "1.0.0")
    path.parent.mkdir(parents=True)
    changed = {**read.schema_document, "title": "Something else"}
    path.write_text(catalog.canonical(changed), encoding="utf-8")
    before = path.read_bytes()
    assert schema_state(read, other) == "conflict"
    with pytest.raises(SnapshotError) as refused:
        install_schema(read, other)
    assert refused.value.code == "schema_conflict"
    assert path.read_bytes() == before


def test_a_shipped_schema_this_aep_lacks_is_unavailable(tmp_path: Path) -> None:
    read = read_snapshot(build_snapshot(owner_dataset(tmp_path)))
    assert schema_state(read, tmp_path) == "shipped"
    future = snapshot.Snapshot(**{**read.__dict__, "schema_version": "9.0.0"})
    assert schema_state(future, tmp_path) == "unavailable"
    with pytest.raises(SnapshotError) as refused:
        install_schema(future, tmp_path)
    assert refused.value.code == "schema_unavailable"


def test_build_refuses_a_missing_dataset_and_a_too_large_snapshot(tmp_path: Path) -> None:
    with pytest.raises(SnapshotError) as refused:
        build_snapshot(BiStore(tmp_path, "nothing"))
    assert refused.value.code == "dataset_missing"
    with pytest.raises(SnapshotError) as refused:
        build_snapshot(owner_dataset(tmp_path), max_bytes=100)
    assert refused.value.code == "artifact_too_large"
