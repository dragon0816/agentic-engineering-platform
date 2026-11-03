"""BI vault phase V3 (`docs/phases/BI_VAULT.md` §6.1, owner 2026-10-28).

A rebuildable SQLite FTS5 index (trigram tokenizer) per dataset, in its own
file `search.sqlite`, over card names and current field values and over the
current Markdown revision of every source, chunked with line ranges. It is
kept current on every card write and Markdown save, rebuilt on demand, says
whether it is behind, and a query shorter than three characters scans.
`service.search` (`GET /api/bi/cards?q=`) is not changed.

Every card, note and table here is a fictional fixture; every test uses a
temporary workspace.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards import search_index, service
from capabilities.bi_cards.store import BiStore
from host_runtime.bi_cards_api import route

ACTOR = "tester"
TECH_CSV = (
    "技術,領域,成熟度,新增測試需求\n"
    "EtherCAT,robotics,mature,週期抖動;同步精度\n"
    "TSN,robotics,growth,時間同步(802.1AS)\n"
)
NOTE = """# 展會筆記（虛構範例）

客戶 C 公司提到毫米波雷達模組的量產測試很急。

## 其他

工業乙太網路的時間同步需求也在增加。
"""


def _call(tmp_path: Path, method: str, path: str, body: Any = None, **q: str) -> Any:
    return route(tmp_path, ACTOR, method, path, q, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _search(tmp_path: Path, q: str) -> dict[str, Any]:
    return _ok(_call(tmp_path, "GET", "/api/bi/search", dataset="demo", q=q))


def _source(tmp_path: Path, name: str, text: str) -> str:
    body = {"dataset": "demo", "name": name, "text": text}
    return str(_ok(_call(tmp_path, "POST", "/api/bi/sources", body))["source"]["id"])


def _commit_tech(tmp_path: Path) -> str:
    source = _source(tmp_path, "tech.csv", TECH_CSV)
    body = {"dataset": "demo", "kind": "ingest", "source_id": source}
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", body))["run"]
    detail = _ok(_call(tmp_path, "GET", f"/api/bi/runs/{run['id']}", dataset="demo"))
    for candidate in detail["candidates"]:
        path = f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}"
        _ok(_call(tmp_path, "POST", path, {"dataset": "demo", "review": "accepted"}))
    done = _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": "demo"}))
    return str(done["import_id"])


def _card(tmp_path: Path, key: str) -> dict[str, Any]:
    store = BiStore(tmp_path)
    card = next(c for c in store.card_rows() if c["canonical_key"] == key)
    return _ok(_call(tmp_path, "GET", f"/api/bi/cards/{card['id']}", dataset="demo"))


def _names(result: dict[str, Any]) -> list[str]:
    return [c["name"] for c in result["cards"]]


def test_a_commit_is_searchable_by_name_and_value_with_snippets(tmp_path: Path) -> None:
    _commit_tech(tmp_path)
    found = _search(tmp_path, "同步精度")
    assert found["mode"] == "index" and _names(found) == ["EtherCAT"]
    (hit,) = [h for h in found["cards"][0]["hits"] if h["field"] == "new_test_requirements"]
    start, end = hit["marks"][0]
    assert hit["snippet"][start:end] == "同步精度"
    # Case is ignored and every word must match.
    assert _names(_search(tmp_path, "ethercat")) == ["EtherCAT"]
    assert _names(_search(tmp_path, "TSN 802.1AS")) == ["TSN"]
    assert _search(tmp_path, "TSN 同步精度")["cards"] == []
    state = found["index"]
    assert state["cards"] == 2 and state["behind"] is False and state["tokenizer"] == "trigram"
    # Its own file: nothing is added to the cards' database.
    assert (tmp_path / "bi" / "demo" / "search.sqlite").is_file()
    connection = sqlite3.connect(tmp_path / "bi" / "demo" / "bi.sqlite")
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master")}
    connection.close()
    assert not any("text" in t or "fts" in t for t in tables)


def test_a_short_query_scans(tmp_path: Path) -> None:
    _commit_tech(tmp_path)
    found = _search(tmp_path, "抖動")
    assert found["mode"] == "scan" and _names(found) == ["EtherCAT"]
    assert _search(tmp_path, "")["mode"] == "none"


def test_markdown_passages_are_found_with_their_lines(tmp_path: Path) -> None:
    source = _source(tmp_path, "expo.md", NOTE)
    found = _search(tmp_path, "毫米波雷達")
    (passage,) = found["passages"]
    assert passage["source_id"] == source and passage["source_name"] == "expo.md"
    assert passage["rev"] == 1 and passage["line"] == 3
    assert passage["line_start"] <= 3 <= passage["line_end"]
    start, end = passage["marks"][0]
    assert passage["snippet"][start:end] == "毫米波雷達"
    assert found["index"]["chunks"] >= 1 and found["index"]["sources"] == 1
    # A saved edit is indexed at once; the old text is no longer found.
    edited = NOTE.replace("毫米波雷達", "衛星通訊")
    path = f"/api/bi/sources/{source}/markdown"
    _ok(_call(tmp_path, "POST", path, {"dataset": "demo", "markdown": edited, "base_rev": 1}))
    assert _search(tmp_path, "毫米波雷達")["passages"] == []
    (moved,) = _search(tmp_path, "衛星通訊")["passages"]
    assert moved["rev"] == 2


def test_edits_proposals_and_undo_keep_the_index_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import_id = _commit_tech(tmp_path)
    tsn = _card(tmp_path, "TSN")
    edit = {
        "dataset": "demo",
        "field": "new_test_requirements",
        "value": ["封包排程驗證"],
        "base_version": tsn["card"]["version"],
        "reason": "FAE 確認",
        "card": tsn["card"]["id"],
    }
    note = _ok(_call(tmp_path, "POST", "/api/bi/corrections/preview", edit))
    apply = {"dataset": "demo", "text": note["text"], "base_version": note["base_version"]}
    _ok(_call(tmp_path, "POST", "/api/bi/corrections/apply", apply))
    assert _names(_search(tmp_path, "封包排程")) == ["TSN"]
    assert _search(tmp_path, "802.1AS")["cards"] == []
    # Searching is unchanged in `service.search` (the cards page).
    store = BiStore(tmp_path)
    assert [c["name"] for c, _ in service.search(store, text="封包排程")] == ["TSN"]
    _ok(_call(tmp_path, "POST", "/api/bi/import/undo", {"dataset": "demo", "import_id": import_id}))
    # Undo keeps the person's edit and removes what only the import wrote.
    assert _search(tmp_path, "EtherCAT")["cards"] == []
    assert _names(_search(tmp_path, "封包排程")) == ["TSN"]
    # A write whose index update failed leaves it behind; a rebuild repairs it.
    monkeypatch.setattr(search_index, "sync_quietly", lambda store: None)
    _commit_tech(tmp_path)
    monkeypatch.undo()
    state = _ok(_call(tmp_path, "GET", "/api/bi/index", dataset="demo"))["index"]
    assert state["behind"] is True and state["behind_cards"] >= 1
    rebuilt = _ok(_call(tmp_path, "POST", "/api/bi/index/rebuild", {"dataset": "demo"}))["index"]
    assert rebuilt["behind"] is False and rebuilt["built_at"] and rebuilt["cards"] == 2
    assert _names(_search(tmp_path, "同步精度")) == ["EtherCAT"]


def test_a_schema_change_reindexes_every_card(tmp_path: Path) -> None:
    _commit_tech(tmp_path)
    store = BiStore(tmp_path)
    with sqlite3.connect(search_index.index_path(store)) as connection:
        connection.execute("UPDATE meta SET value = 'other@1.0.0' WHERE key = 'schema'")
    state = search_index.status(store)
    assert state["behind"] is True and state["behind_cards"] == 2
    search_index.sync(store)
    assert search_index.status(store)["behind"] is False


def test_reading_an_empty_dataset_creates_nothing(tmp_path: Path) -> None:
    found = _search(tmp_path, "任何東西")
    assert found["cards"] == [] and found["passages"] == []
    state = _ok(_call(tmp_path, "GET", "/api/bi/index", dataset="demo"))["index"]
    assert state["exists"] is False and state["behind"] is False
    assert not (tmp_path / "bi").exists()
    status, payload = _call(tmp_path, "GET", "/api/bi/search", dataset="nope", q="x")
    assert (status, payload["code"]) == (404, "dataset_unknown")


def test_the_demo_load_is_indexed(tmp_path: Path) -> None:
    loaded = service.load_demo(BiStore(tmp_path))
    state = _ok(_call(tmp_path, "GET", "/api/bi/index", dataset="demo"))["index"]
    assert state["cards"] == loaded["created"] and state["behind"] is False
