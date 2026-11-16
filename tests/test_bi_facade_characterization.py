"""What BI does today, pinned before any BI facade or extraction (BI-first plugin
preparation, 2026-11-14). Synthetic local data only: the built-in fictional demo
cards and a vault in a temporary folder. No model, network or company data.

These tests describe current behaviour; they are not new requirements. In
particular the vault test records that a *read* of an outdated vault database
rebuilds it, so a future read-only facade must not reuse that read path.
"""

from __future__ import annotations

import hashlib
import inspect
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from capabilities.bi_cards import card_model, vault
from capabilities.bi_cards.store import VAULT_PREFIX, BiStore
from host_runtime import plugin_web
from host_runtime.bi_cards_api import route
from host_runtime.web_page import PAGE

DATASET_KEYS = {"name", "cards", "updated", "schema", "dashboard", "subscribed", "read_only"}
#: GET routes the BI pane reads for a dataset, apart from AI and Atlas.
PLAIN_READS = (
    "/api/bi/datasets",
    "/api/bi/cards",
    "/api/bi/schema",
    "/api/bi/dashboard",
    "/api/bi/quality",
)


def _call(ws: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(ws, "tester", method, path, query, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _tree(root: Path) -> dict[str, str]:
    """Every file under `root` by relative path and content digest."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _version(path: Path) -> int:
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as db:
        return int(db.execute("PRAGMA user_version").fetchone()[0])


def _vault(ws: Path, shared: Path) -> tuple[str, str]:
    shared.mkdir(parents=True)
    made = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(shared),
                "title": "Fictional Signals",
                "schema": "bi.schema/v1.1",
                "author": "alice",
                "default_pack": False,
            },
        )
    )
    vault_id = str(made["vault"]["id"])
    return vault_id, vault.dataset_name(vault_id)


# -- dataset metadata ------------------------------------------------------------------


def test_dataset_metadata_is_one_closed_row_per_dataset(tmp_path: Path) -> None:
    ws = tmp_path / "pc"
    assert _ok(_call(ws, "GET", "/api/bi/datasets")) == {"datasets": []}
    loaded = _ok(_call(ws, "POST", "/api/bi/demo/load", {"dataset": "demo"}))
    assert loaded["imported"]["created"] == 104
    vault_id, vault_dataset = _vault(ws, tmp_path / "shared")

    listed = _ok(_call(ws, "GET", "/api/bi/datasets"))["datasets"]
    assert [item["name"] for item in listed] == ["demo", vault_dataset]
    assert vault_dataset == VAULT_PREFIX + vault_id
    for item in listed:
        assert set(item) == DATASET_KEYS, item
        assert item["subscribed"] is False and item["read_only"] is False
        assert item["dashboard"] is True and str(item["schema"]).startswith("bi.")
    demo, made = listed
    assert demo["cards"] == 104 and isinstance(demo["updated"], str)
    assert made["cards"] == 0
    # The count is the card list's length for the same dataset.
    cards = _ok(_call(ws, "GET", "/api/bi/cards", dataset="demo"))["cards"]
    assert len(cards) == demo["cards"]


# -- reads and writes ---------------------------------------------------------------------


def test_plain_dataset_reads_leave_the_bi_folder_unchanged(tmp_path: Path) -> None:
    ws = tmp_path / "pc"
    _ok(_call(ws, "POST", "/api/bi/demo/load", {"dataset": "demo"}))
    before = _tree(ws / "bi")
    for path in PLAIN_READS:
        _ok(_call(ws, "GET", path, dataset="demo"))
    assert _tree(ws / "bi") == before


def test_reading_an_outdated_vault_database_rebuilds_it(tmp_path: Path) -> None:
    """The hazard a facade must avoid: `BiStore(...)` on a vault runs
    `vault.ensure_current`, so listing datasets can write the vault's database."""
    ws = tmp_path / "pc"
    _, dataset = _vault(ws, tmp_path / "shared")
    path = BiStore(ws, dataset).path
    assert _version(path) == card_model.MODEL_VERSION

    # Current version: a read changes nothing.
    current = _tree(ws / "bi")
    _ok(_call(ws, "GET", "/api/bi/datasets"))
    assert _tree(ws / "bi") == current

    # An older database (as an earlier AEP built it): the same read rebuilds it.
    with closing(sqlite3.connect(path)) as db:
        db.execute(f"PRAGMA user_version = {card_model.MODEL_VERSION - 1}")
        db.commit()
    older = _tree(ws / "bi")
    listed = _ok(_call(ws, "GET", "/api/bi/datasets"))["datasets"]
    assert [item["name"] for item in listed] == [dataset]
    assert _version(path) == card_model.MODEL_VERSION
    assert _tree(ws / "bi") != older


# -- the page and the routes stay where people find them ------------------------------------


def test_the_full_bi_entry_stays_in_knowledge() -> None:
    for mount in (
        'id="nav-knowledge"',
        'id="panel-knowledge"',
        'id="kn-tabs"',
        'data-kn="bi"',
        'id="kn-pane-bi"',
        'id="bi-views"',
        'id="bi-dataset"',
    ):
        assert PAGE.count(mount) == 1, mount
    # The Knowledge tab opens BI when this PC has a dataset, from the BI API itself.
    script = PAGE.split("async function loadKnowledgeTab()", 1)[1].split("\n}\n", 1)[0]
    assert 'call("/api/bi/datasets")' in script and 'knShow("bi")' in script
    # Plugin pages are elsewhere: no plugin markup inside the BI pane.
    pane = PAGE.split('id="kn-pane-bi"', 1)[1].split('<section id="panel-', 1)[0]
    assert "plugin-" not in pane


def test_bi_routes_are_served_by_bi_after_the_token_and_not_by_plugins() -> None:
    from host_runtime import web

    for path in ("/api/bi/datasets", "/api/bi/dashboard", "/api/bi/vaults"):
        assert not plugin_web.owns(path), path
    for method in ("do_GET", "do_POST"):
        source = inspect.getsource(getattr(web._Handler, method))
        order = [
            source.index(marker)
            for marker in ("self._authorized()", "plugin_web.handle(", "features.active().handle(")
        ]
        assert order == sorted(order), (method, order)
    # The Atlas analysis feed is read without the page token, before that guard.
    get = inspect.getsource(web._Handler.do_GET)
    assert get.index("features.active().public_get(") < get.index("self._authorized()")
    # Those mount points are BI's own handlers (feature mount points, proposal r3).
    from host_runtime import bi_cards_api, bi_feed_api, features_bi

    bi = inspect.getsource(features_bi.BiFeature)
    assert "bi_cards_api.handle(handler, method, parsed)" in bi
    assert 'bi_feed_api.handle(handler, "GET", path, query, workspace_root)' in bi
    held = vars(features_bi)
    assert held["bi_cards_api"] is bi_cards_api and held["bi_feed_api"] is bi_feed_api
