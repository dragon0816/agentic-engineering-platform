"""The BI overview reader (feature plugin preparation): stdlib-only, read-only
dataset metadata from an explicit `bi/` folder, with truthful statuses.
Synthetic data only (the shipped demo fixture and hand-made files)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from aep_bi.cards import card_model, service
from aep_bi.cards.schema import BI_PREFIX
from aep_bi.cards.store import LEGACY_SCHEMA, BiStore

READER_FILE = (
    Path(__file__).resolve().parents[1]
    / "feature_plugins"
    / "bi_overview"
    / "worker"
    / "aep_plugin_bi_overview"
    / "reader.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bi_overview_reader", READER_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reader = _load()
PARITY = ("name", "cards", "updated", "schema", "dashboard", "subscribed", "read_only")


def tree(root: Path) -> dict[str, str]:
    """Every file under `root` with its digest: proves nothing is written or created."""
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def demo(workspace: Path, name: str = "demo") -> BiStore:
    store = BiStore(workspace, name)
    service.load_demo(store)
    return store


def by_name(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in result["datasets"]}


def make_db(path: Path, *, schema: str | None = LEGACY_SCHEMA, version: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE cards (id TEXT PRIMARY KEY, entity_type TEXT, canonical_key TEXT, "
            "name TEXT, updated TEXT)"
        )
        db.execute("INSERT INTO cards VALUES ('c1', 'Signal', 'k1', 'n', '2026-11-01T00:00:00')")
        if schema is not None:
            db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("INSERT INTO meta VALUES ('schema', ?)", (schema,))
        db.execute(f"PRAGMA user_version = {version}")
    db.close()


# -- parity with the existing listing -----------------------------------------------------------


def test_plain_datasets_match_the_existing_dataset_list(tmp_path: Path) -> None:
    demo(tmp_path, "demo")
    empty = BiStore(tmp_path, "empty-one")
    empty.create("bi.schema/v1.1@1.1.0")
    expected = {item["name"]: item for item in service.dataset_list(tmp_path)}
    before = tree(tmp_path / "bi")
    result = reader.read_overview(tmp_path / "bi")
    assert tree(tmp_path / "bi") == before
    assert result["total"] == 2 and result["truncated"] is False
    found = by_name(result)
    assert set(found) == set(expected)
    for name, item in expected.items():
        assert {key: found[name][key] for key in PARITY} == {key: item[key] for key in PARITY}
        assert found[name]["status"] == "ready" and found[name]["reason"] is None
        assert found[name]["kind"] == "local"
    assert found["demo"]["cards"] > 0 and found["demo"]["dashboard"] is True


def test_constants_follow_the_bi_package() -> None:
    assert reader.PROJECTION_VERSION == card_model.MODEL_VERSION
    assert reader.LEGACY_SCHEMA == LEGACY_SCHEMA
    assert reader.BI_PREFIX == BI_PREFIX


def test_an_absent_or_empty_bi_folder_is_reported_and_never_created(tmp_path: Path) -> None:
    assert reader.read_overview(tmp_path / "bi") == {
        "status": "missing",
        "datasets": [],
        "total": 0,
        "truncated": False,
    }
    assert not (tmp_path / "bi").exists()
    (tmp_path / "bi").mkdir()
    assert reader.read_overview(tmp_path / "bi")["status"] == "ready"


# -- honest statuses ------------------------------------------------------------------------------


def test_corrupt_unsupported_and_legacy_databases_are_named_not_guessed(tmp_path: Path) -> None:
    bi = tmp_path / "bi"
    (bi / "garbage").mkdir(parents=True)
    (bi / "garbage" / "bi.sqlite").write_bytes(b"not a database at all" * 10)
    (bi / "zero").mkdir()
    (bi / "zero" / "bi.sqlite").write_bytes(b"")
    make_db(bi / "legacy" / "bi.sqlite", schema=None)
    make_db(bi / "odd-schema" / "bi.sqlite", schema="no version here")
    no_cards = bi / "no-cards" / "bi.sqlite"
    no_cards.parent.mkdir()
    with sqlite3.connect(no_cards) as db:
        db.execute("CREATE TABLE other (x)")
    db.close()
    (bi / "bad name!").mkdir()
    shutil.copy(bi / "legacy" / "bi.sqlite", bi / "bad name!" / "bi.sqlite")
    before = tree(bi)
    found = by_name(reader.read_overview(bi))
    assert tree(bi) == before
    assert (found["garbage"]["status"], found["garbage"]["reason"]) == ("corrupt", "not_sqlite")
    assert (found["zero"]["status"], found["zero"]["reason"]) == ("corrupt", "not_sqlite")
    assert found["legacy"]["status"] == "ready" and found["legacy"]["schema"] == LEGACY_SCHEMA
    odd = found["odd-schema"]
    assert (odd["status"], odd["reason"], odd["schema"], odd["dashboard"]) == (
        "unsupported",
        "schema_unknown",
        None,
        None,
    )
    assert (found["no-cards"]["status"], found["no-cards"]["reason"]) == (
        "unsupported",
        "tables_unknown",
    )
    assert (found["bad name!"]["status"], found["bad name!"]["reason"]) == (
        "unsupported",
        "name_invalid",
    )
    for item in found.values():
        if item["status"] != "ready":
            assert item["cards"] is None and item["updated"] is None


@pytest.mark.parametrize("sidecar", ["bi.sqlite-journal", "bi.sqlite-wal", "bi.sqlite-shm"])
def test_an_in_flight_write_is_not_read_as_stale_data(tmp_path: Path, sidecar: str) -> None:
    demo(tmp_path)
    (tmp_path / "bi" / "demo" / sidecar).write_bytes(b"pending")
    before = tree(tmp_path / "bi")
    item = by_name(reader.read_overview(tmp_path / "bi"))["demo"]
    assert (item["status"], item["reason"], item["cards"]) == ("busy", "write_in_progress", None)
    assert tree(tmp_path / "bi") == before


def test_a_wal_database_is_refused_without_creating_shared_memory_files(tmp_path: Path) -> None:
    path = tmp_path / "bi" / "walled" / "bi.sqlite"
    make_db(path)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
    db.close()
    for extra in path.parent.glob("bi.sqlite-*"):
        extra.unlink()
    before = tree(tmp_path / "bi")
    item = by_name(reader.read_overview(tmp_path / "bi"))["walled"]
    assert (item["status"], item["reason"]) == ("unsupported", "journal_wal")
    assert tree(tmp_path / "bi") == before


def test_a_locked_database_is_busy_not_empty(tmp_path: Path) -> None:
    demo(tmp_path)
    path = tmp_path / "bi" / "demo" / "bi.sqlite"
    writer = sqlite3.connect(path, isolation_level=None)
    try:
        writer.execute("BEGIN EXCLUSIVE")  # the lock alone, before any journal exists
        journaled = path.with_name("bi.sqlite-journal").exists()
        item = by_name(reader.read_overview(tmp_path / "bi", timeout_seconds=0.2))["demo"]
        expected = "write_in_progress" if journaled else "locked"
        assert (item["status"], item["reason"], item["cards"]) == ("busy", expected, None)
    finally:
        writer.execute("ROLLBACK")
        writer.close()


# -- vault projections and subscriptions ------------------------------------------------


def _vault(bi: Path, vault_id: str, *, version: int, path: str = "C:/elsewhere/vault") -> None:
    registry = bi / "vaults" / "registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    items = json.loads(registry.read_text("utf-8"))["vaults"] if registry.is_file() else []
    items.append({"id": vault_id, "path": path, "author": "synthetic"})
    registry.write_text(json.dumps({"vaults": items}), encoding="utf-8")
    make_db(bi / "vaults" / vault_id / "bi.sqlite", schema="bi.schema/v5@5.0.0", version=version)


def test_vault_projections_are_marked_and_outdated_ones_never_rebuilt(tmp_path: Path) -> None:
    bi = tmp_path / "bi"
    _vault(bi, "v-current", version=card_model.MODEL_VERSION)
    _vault(bi, "v-old", version=card_model.MODEL_VERSION - 1)
    _vault(bi, "v-gone", version=card_model.MODEL_VERSION)
    shutil.rmtree(bi / "vaults" / "v-gone")
    registry = json.loads((bi / "vaults" / "registry.json").read_text("utf-8"))
    registry["vaults"] += [{"id": "../escape", "path": "x"}, {"id": 7}, "not a record"]
    (bi / "vaults" / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    before = tree(bi)
    result = reader.read_overview(bi)
    assert tree(bi) == before
    found = by_name(result)
    current = found["vault-v-current"]
    assert (current["status"], current["kind"], current["projection"]) == ("ready", "vault", True)
    assert current["cards"] == 1 and current["dashboard"] is True
    old = found["vault-v-old"]
    assert (old["status"], old["reason"], old["cards"]) == ("outdated", "projection_version", None)
    gone = found["vault-v-gone"]
    assert (gone["status"], gone["reason"]) == ("missing", "projection_absent")
    assert result["invalid_registrations"] == 3
    assert "C:/elsewhere" not in json.dumps(result)  # registered paths are neither used nor shown


def test_subscribed_copies_are_read_only_and_follow_their_record(tmp_path: Path) -> None:
    bi = tmp_path / "bi"
    root = bi / "subscribed" / "team__shared"
    (root).mkdir(parents=True)
    (root / "subscription.json").write_text(
        json.dumps({"version": "1.2.0", "schema": "bi.schema/v5@5.0.0"}), encoding="utf-8"
    )
    make_db(root / "1.2.0" / "bi.sqlite", schema="bi.schema/v5@5.0.0")
    other = bi / "subscribed" / "team__nover"
    other.mkdir()
    (other / "subscription.json").write_text(json.dumps({"version": "../x"}), encoding="utf-8")
    item = by_name(reader.read_overview(bi))["team/shared"]
    assert (item["kind"], item["subscribed"], item["read_only"]) == ("subscribed", True, True)
    assert (item["status"], item["version"], item["cards"]) == ("ready", "1.2.0", 1)
    nover = by_name(reader.read_overview(bi))["team/nover"]
    assert (nover["status"], nover["reason"]) == ("unsupported", "version_invalid")


@pytest.mark.skipif(sys.platform != "win32", reason="NTFS junctions")
def test_redirected_dataset_folders_are_not_followed(tmp_path: Path) -> None:
    import _winapi

    outside = tmp_path / "outside"
    demo(outside)
    bi = tmp_path / "ws" / "bi"
    bi.mkdir(parents=True)
    _winapi.CreateJunction(str(outside / "bi" / "demo"), str(bi / "linked"))
    item = by_name(reader.read_overview(bi))["linked"]
    assert (item["status"], item["reason"], item["cards"]) == ("unsupported", "redirected", None)


# -- bounds -----------------------------------------------------------------------------


def test_output_is_capped_with_total_and_truncated(tmp_path: Path) -> None:
    bi = tmp_path / "bi"
    make_db(bi / "seed" / "bi.sqlite")
    for index in range(reader.MAX_ROWS + 5):
        target = bi / f"d{index:04d}" / "bi.sqlite"
        target.parent.mkdir()
        shutil.copy(bi / "seed" / "bi.sqlite", target)
    result = reader.read_overview(bi)
    assert result["total"] == reader.MAX_ROWS + 6
    assert result["truncated"] is True
    assert len(result["datasets"]) == reader.MAX_ROWS
    small = reader.read_overview(bi, limit=3)
    assert (len(small["datasets"]), small["truncated"]) == (3, True)
    with pytest.raises(ValueError):
        reader.read_overview(bi, limit=reader.MAX_ROWS + 1)
    with pytest.raises(ValueError):
        reader.read_overview(Path("relative/bi"))


def test_the_reader_is_stdlib_only_and_never_imports_bi_code() -> None:
    import ast

    tree_ = ast.parse(READER_FILE.read_text(encoding="utf-8"))
    roots = {
        (node.module or "").split(".")[0]
        if isinstance(node, ast.ImportFrom)
        else alias.name.split(".")[0]
        for node in ast.walk(tree_)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert roots <= set(sys.stdlib_module_names) | {"__future__"}, roots


def test_an_overall_deadline_bounds_the_read_and_names_unread_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bi = tmp_path / "bi"
    for name in ("a", "b", "c", "d"):
        make_db(bi / name / "bi.sqlite")
    ticks = iter(range(100))
    monkeypatch.setattr(reader, "_clock", lambda: float(next(ticks)))  # +1 s per look
    timeouts: list[float] = []
    real_connect = reader.sqlite3.connect

    def connect(*args: Any, **kwargs: Any) -> Any:
        timeouts.append(kwargs["timeout"])
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(reader.sqlite3, "connect", connect)
    before = tree(bi)
    result = reader.read_overview(bi, timeout_seconds=1.0, deadline_seconds=2.5)
    assert tree(bi) == before
    assert (result["total"], result["truncated"], len(result["datasets"])) == (4, False, 4)
    states = [(i["name"], i["status"], i["reason"], i["cards"]) for i in result["datasets"]]
    assert states == [
        ("a", "ready", None, 1),
        ("b", "ready", None, 1),
        ("c", "busy", "deadline_exceeded", None),
        ("d", "busy", "deadline_exceeded", None),
    ]
    assert timeouts == [1.0, 0.5]  # each row waits at most what the deadline leaves
    with pytest.raises(ValueError):
        reader.read_overview(bi, deadline_seconds=0)


def test_an_empty_subscription_schema_falls_back_to_the_database(tmp_path: Path) -> None:
    root = tmp_path / "bi" / "subscribed" / "team__blank"
    root.mkdir(parents=True)
    (root / "subscription.json").write_text(
        json.dumps({"version": "1.0.0", "schema": ""}), encoding="utf-8"
    )
    make_db(root / "1.0.0" / "bi.sqlite", schema="bi.schema/v5@5.0.0")
    item = by_name(reader.read_overview(tmp_path / "bi"))["team/blank"]
    assert (item["status"], item["schema"], item["dashboard"]) == (
        "ready",
        "bi.schema/v5@5.0.0",
        True,
    )


@pytest.mark.parametrize(
    "message",
    ["attempt to write a readonly database", "database is locked", "database table is locked"],
)
def test_a_read_only_or_lock_race_is_busy_not_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    demo(tmp_path)

    def race(*args: Any, **kwargs: Any) -> Any:
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(reader, "_query", race)
    before = tree(tmp_path / "bi")
    item = by_name(reader.read_overview(tmp_path / "bi"))["demo"]
    assert (item["status"], item["reason"], item["cards"]) == ("busy", "locked", None)
    assert tree(tmp_path / "bi") == before
