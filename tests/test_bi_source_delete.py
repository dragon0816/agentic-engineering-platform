"""Deleting a source added by mistake (step 1 「刪除」, owner 2026-11-19).

`POST /api/bi/sources/delete`: a source only on this PC goes with its Markdown, its
conversion record and its index passages; a vault source already committed or pushed
has its removal staged for the next commit and push, the history keeping it; a source
a card cites, or an open Ingest run reads, is refused while the others go; a repeat
changes nothing; a subscribed copy refuses. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_vault import _commit, _push, _status, _sync, _two_pcs

from aep_bi.cards import search_index, vault, vault_sources
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore
from aep_bi.host.bi_cards_api import route

TECH_CSV = (
    "技術,領域,成熟度,新增測試需求\n"
    "EtherCAT,robotics,mature,週期抖動\n"
    "TSN,robotics,growth,時間同步\n"
)
NOTE = "# Zebrafish 會議\n\n虛構的 Zebrafish 量測紀錄。\n"
WRONG = "# 放錯的檔案\n\nQuokka 不該在這裡。\n"


def _call(ws: Path, method: str, path: str, body: Any = None, **query: str) -> Any:
    return route(ws, "tester", method, path, query, body)


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _add(ws: Path, dataset: str, name: str, text: str) -> dict[str, Any]:
    body = {"dataset": dataset, "name": name, "text": text}
    return dict(_ok(_call(ws, "POST", "/api/bi/sources", body))["source"])


def _delete(ws: Path, dataset: str, *ids: str) -> dict[str, Any]:
    body = {"dataset": dataset, "ids": list(ids)}
    return _ok(_call(ws, "POST", "/api/bi/sources/delete", body))


def _by_id(reply: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in reply["results"]}


def _listed(ws: Path, dataset: str) -> dict[str, dict[str, Any]]:
    sources = _ok(_call(ws, "GET", "/api/bi/sources", dataset=dataset))["sources"]
    return {item["id"]: item for item in sources}


def _passages(ws: Path, dataset: str, word: str) -> int:
    return len(search_index.search(BiStore(ws, dataset), word)["passages"])


def _files(ws: Path, dataset: str) -> list[str]:
    folder = ws / "bi" / dataset
    return sorted(
        p.relative_to(folder).as_posix()
        for sub in ("sources", "markdown")
        for p in (folder / sub).rglob("*")
        if p.is_file()
    )


def test_a_source_only_on_this_pc_goes_with_its_markdown_and_passages(tmp_path: Path) -> None:
    kept = _add(tmp_path, "demo", "note.md", NOTE)
    wrong = _add(tmp_path, "demo", "wrong.md", WRONG)
    broken = _add(tmp_path, "demo", "broken.pdf", "not really a pdf")
    assert broken["convert_error"] is not None  # its conversion record is kept
    assert _passages(tmp_path, "demo", "Quokka") == 1
    before = _files(tmp_path, "demo")

    done = _delete(tmp_path, "demo", wrong["id"], broken["id"])

    results = _by_id(done)
    assert results[wrong["id"]] == {"id": wrong["id"], "name": "wrong.md", "status": "deleted"}
    assert results[broken["id"]]["status"] == "deleted"
    assert done["counts"] == {"deleted": 2, "staged_removal": 0, "refused": 0, "not_found": 0}
    assert set(_listed(tmp_path, "demo")) == {kept["id"]}
    staging = Staging(tmp_path, "demo")
    assert staging.markdown_revisions(wrong["id"]) == []
    assert _passages(tmp_path, "demo", "Quokka") == 0
    assert _passages(tmp_path, "demo", "Zebrafish") == 1
    gone = set(before) - set(_files(tmp_path, "demo"))
    assert gone == {
        f"sources/{wrong['sha256']}.md",
        f"sources/{broken['sha256']}.pdf",
        f"markdown/{wrong['id']}/rev-1.md",
    }
    assert not (tmp_path / "bi" / "demo" / "markdown" / wrong["id"]).exists()
    with staging._db() as db:
        assert db.execute("SELECT COUNT(*) FROM conversions").fetchone()[0] == 0

    # The same request again changes nothing.
    files = _files(tmp_path, "demo")
    again = _delete(tmp_path, "demo", wrong["id"], broken["id"])
    assert [r["status"] for r in again["results"]] == ["not_found", "not_found"]
    assert _files(tmp_path, "demo") == files
    assert set(_listed(tmp_path, "demo")) == {kept["id"]}

    # The same file can be added again afterwards.
    assert _add(tmp_path, "demo", "wrong.md", WRONG)["already"] is False


def _committed_run(ws: Path, source_id: str) -> str:
    body = {"dataset": "demo", "kind": "ingest", "source_id": source_id}
    run = _ok(_call(ws, "POST", "/api/bi/runs", body))["run"]
    detail = _ok(_call(ws, "GET", f"/api/bi/runs/{run['id']}", dataset="demo"))
    for candidate in detail["candidates"]:
        _ok(
            _call(
                ws,
                "POST",
                f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}",
                {"dataset": "demo", "review": "accepted"},
            )
        )
    _ok(_call(ws, "POST", f"/api/bi/runs/{run['id']}/commit", {"dataset": "demo"}))
    return str(run["id"])


def test_a_source_a_card_cites_is_refused_and_the_others_still_go(tmp_path: Path) -> None:
    cited = _add(tmp_path, "demo", "tech.csv", TECH_CSV)
    _committed_run(tmp_path, cited["id"])
    wrong = _add(tmp_path, "demo", "wrong.md", WRONG)
    with BiStore(tmp_path)._db() as db:
        evidence = db.execute("SELECT * FROM evidence ORDER BY seq").fetchall()
    assert evidence

    done = _delete(tmp_path, "demo", cited["id"], wrong["id"], "nope")

    results = _by_id(done)
    refused = results[cited["id"]]
    assert refused["status"] == "refused" and refused["code"] == "source_cited"
    assert refused["cards"] == ["EtherCAT", "TSN"] and refused["count"] == 2
    assert "「EtherCAT」" in refused["reason"] and "證據" in refused["reason"]
    assert results[wrong["id"]]["status"] == "deleted"
    assert results["nope"]["status"] == "not_found"
    assert set(_listed(tmp_path, "demo")) == {cited["id"]}
    with BiStore(tmp_path)._db() as db:  # the evidence is exactly as it was
        assert [tuple(r) for r in db.execute("SELECT * FROM evidence ORDER BY seq")] == [
            tuple(r) for r in evidence
        ]


def test_a_source_an_open_run_reads_is_refused(tmp_path: Path) -> None:
    source = _add(tmp_path, "demo", "tech.csv", TECH_CSV)
    body = {"dataset": "demo", "kind": "trial", "source_id": source["id"]}
    run = _ok(_call(tmp_path, "POST", "/api/bi/runs", body))["run"]
    assert run["status"] == "review"

    (result,) = _delete(tmp_path, "demo", source["id"])["results"]
    assert (result["status"], result["code"]) == ("refused", "source_in_open_run")
    assert result["runs"] == [run["id"]]

    _ok(_call(tmp_path, "POST", f"/api/bi/runs/{run['id']}/cancel", {"dataset": "demo"}))
    (result,) = _delete(tmp_path, "demo", source["id"])["results"]
    assert result["status"] == "deleted"


def test_a_subscribed_copy_and_a_bad_request_are_refused(tmp_path: Path) -> None:
    status, payload = _call(
        tmp_path, "POST", "/api/bi/sources/delete", {"dataset": "ns/name", "ids": ["x"]}
    )
    assert (status, payload["code"]) == (409, "dataset_read_only")
    status, payload = _call(tmp_path, "POST", "/api/bi/sources/delete", {"dataset": "demo"})
    assert (status, payload["code"]) == (400, "ids_missing")


def _unit_key(source: dict[str, Any]) -> str:
    return vault_sources.unit_key(source["sha256"])


def test_a_vault_source_never_committed_leaves_nothing_to_push(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _add(a, dataset, "wrong.md", WRONG)
    assert _status(a, vault_id)["uncommitted"] == 3  # its unit, file and Markdown

    (result,) = _delete(a, dataset, source["id"])["results"]

    assert result["status"] == "deleted"
    assert _status(a, vault_id)["uncommitted"] == 0
    assert _listed(a, dataset) == {}
    assert _unit_key(source) not in vault.Vault(a, vault_id).repo.working_units()


def test_a_pushed_vault_source_is_removed_at_the_next_commit_and_history_keeps_it(
    tmp_path: Path,
) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _add(a, dataset, "wrong.md", WRONG)
    kept = _add(a, dataset, "note.md", NOTE)
    _commit(a, vault_id, "加入來源")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)  # OneDrive carries the folder to PC b
    _sync(b, vault_id)
    assert source["id"] in _listed(b, dataset)
    pushed_at = vault.Vault(a, vault_id).repo.head()

    (result,) = _delete(a, dataset, source["id"])["results"]

    assert result == {
        "id": source["id"],
        "name": "wrong.md",
        "status": "staged_removal",
        "already": False,
    }
    listed = _listed(a, dataset)
    assert listed[source["id"]]["shared"] == "removing"
    assert listed[kept["id"]]["shared"] == "pushed"
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    (change,) = pending["uncommitted"]
    assert change["unit"] == _unit_key(source) and change["after"] is None
    assert change["label"] == "來源「wrong.md」"

    again = _delete(a, dataset, source["id"])
    assert again["results"][0]["status"] == "staged_removal"
    assert again["results"][0]["already"] is True
    assert _status(a, vault_id)["uncommitted"] == 1

    done = _commit(a, vault_id, "刪除放錯的檔案")
    assert done["commit"]["purpose"] == "刪除放錯的檔案"
    assert set(_listed(a, dataset)) == {kept["id"]}
    assert _passages(a, dataset, "Quokka") == 0
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert set(_listed(b, dataset)) == {kept["id"]}

    # The history keeps it: the version before the removal still has the source.
    repo = vault.Vault(a, vault_id).repo
    assert repo.state_at(str(pushed_at))[_unit_key(source)]["name"] == "wrong.md"
    assert _unit_key(source) not in repo.units()


def test_a_discarded_removal_keeps_the_source(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _add(a, dataset, "wrong.md", WRONG)
    _commit(a, vault_id, "加入來源")
    _delete(a, dataset, source["id"])
    assert _listed(a, dataset)[source["id"]]["shared"] == "removing"

    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/discard", {}))

    assert _listed(a, dataset)[source["id"]]["shared"] == "staged"
    assert Staging(a, dataset).removals() == {}
    nothing = _call(a, "POST", f"/api/bi/vaults/{vault_id}/commit", {"purpose": "x"})
    assert nothing[1].get("code") == "nothing_to_commit"
    assert source["id"] in _listed(a, dataset)


def test_a_removal_committed_with_other_changes_says_so_in_its_own_commit(
    tmp_path: Path,
) -> None:
    from test_bi_vault import _edit, _import, _row

    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    source = _add(a, dataset, "wrong.md", WRONG)
    _commit(a, vault_id, "加入來源")
    _delete(a, dataset, source["id"])
    _ok(_edit(a, dataset, "TSN", "standard_body", "IETF", "alice"))
    _commit(a, vault_id, "改標準組織")
    purposes = [c["purpose"] for c in vault.Vault(a, vault_id).repo.local_commits()]
    assert purposes[-2:] == ["移除來源：wrong.md", "改標準組織"]
