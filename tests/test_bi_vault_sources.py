"""A vault's originals in the shared folder (`docs/phases/BI_SOURCES_IN_REPOSITORY.md`).

Two PCs as in `test_bi_vault.py`. All data is fictional.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from test_bi_vault import (
    _call,
    _commit,
    _Drive,
    _edit,
    _import,
    _ok,
    _push,
    _row,
    _status,
    _sync,
    _two_pcs,
)
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards import search_index, vault, vault_sources
from aep_bi.cards.staging import Staging
from aep_bi.cards.store import BiStore, BiStoreError
from knowledge.repo.repository import _file_sha

REPORT = "# AIDC 報告\n\n電源模組 FACT-1。\n"
FOLDER = "library/products/sources"


def _add(ws: Path, dataset: str, name: str = "report.md", text: str = REPORT, **given: Any) -> Any:
    return Staging(ws, dataset).add_source(name, text=text, actor="alice", **given)


def _unit(ws: Path, vault_id: str, sha256: str) -> dict[str, Any]:
    found = vault.Vault(ws, vault_id).repo.working_units()[vault_sources.unit_key(sha256)]
    return dict(found)


def test_adding_a_source_stages_its_file_and_unit_and_a_push_delivers_them(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _add(a, dataset, folder=FOLDER, classification="RESTRICTED")
    folder = drive.parent("a") / vault_id
    unit = _unit(a, vault_id, source["sha256"])
    assert source["id"] == source["sha256"][:12]
    assert unit["folder"] == FOLDER and unit["classification"] == "RESTRICTED"
    assert unit["file"] == f"{FOLDER}/{source['sha256'][:8]}-report.md"
    assert not (folder / unit["file"]).exists()  # nothing shared before the push
    _commit(a, vault_id, "加入報告")
    assert not (folder / unit["file"]).exists()
    _push(a, vault_id)
    assert (folder / unit["file"]).read_bytes() == REPORT.encode()
    (revision,) = unit["markdown"]
    assert revision["rev"] == 1
    assert revision["file"] == f"{FOLDER}/markdown/{source['sha256'][:8]}/rev-1-alice.md"
    assert (folder / revision["file"]).is_file()
    assert vault.Vault(a, vault_id).repo.units()[vault_sources.unit_key(source["sha256"])]


def test_every_classification_can_be_pushed(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    for level in ("UNCLASSIFIED", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"):
        _add(a, dataset, name=f"{level}.md", text=f"# {level}\n", classification=level)
    _commit(a, vault_id, "四種機密等級")
    assert _push(a, vault_id)["status"] == "pushed"


def test_sources_go_in_their_own_commit_when_there_is_anything_else(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))  # commits at once
    source = _add(a, dataset)
    _ok(_edit(a, dataset, "TSN", "standard_body", "IETF", "alice"))
    done = _commit(a, vault_id, "改標準組織")
    assert done["commit"]["purpose"] == "改標準組織"
    local = vault.Vault(a, vault_id).repo.local_commits()
    purposes = [item["purpose"] for item in local]
    assert purposes[-2] == "加入來源：report.md" and purposes[-1] == "改標準組織"
    assert _status(a, vault_id)["uncommitted"] == 0
    repo = vault.Vault(a, vault_id).repo
    assert repo.working_units()[vault_sources.unit_key(source["sha256"])]


def test_only_a_source_keeps_the_persons_purpose(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _add(a, dataset)
    assert _commit(a, vault_id, "加入 AIDC 報告")["commit"]["purpose"] == "加入 AIDC 報告"
    assert len(vault.Vault(a, vault_id).repo.local_commits()) == 1


def test_an_import_commit_does_not_carry_a_staged_source(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _add(a, dataset)
    _import(a, dataset, _row("TSN", standard_body="IEEE"))
    local = vault.Vault(a, vault_id).repo.local_commits()
    assert local[0]["purpose"] == "加入來源：report.md"
    assert len(local) == 2


def test_a_person_edit_of_the_markdown_is_staged_as_a_new_revision(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _add(a, dataset)
    _commit(a, vault_id, "加入")
    _push(a, vault_id)
    Staging(a, dataset).add_markdown(
        source["id"], REPORT + "補充\n", origin="edit", note="修表格", actor="alice", base_rev=1
    )
    unit = _unit(a, vault_id, source["sha256"])
    assert [item["rev"] for item in unit["markdown"]] == [1, 2]
    _commit(a, vault_id, "修 Markdown")
    _push(a, vault_id)
    assert (
        (drive.parent("a") / vault_id / unit["markdown"][1]["file"])
        .read_bytes()
        .endswith("補充\n".encode())
    )


def test_a_dataset_only_on_this_pc_is_untouched(tmp_path: Path) -> None:
    drive, _, _, a, _ = _two_pcs(tmp_path)
    source = _add(a, "demo-local", name="x.md", text="# x\n")
    assert source["id"] != source["sha256"][:12]
    assert not list(drive.parent("a").rglob("*-x.md"))


def test_no_size_is_refused_on_adding_or_at_a_push(tmp_path: Path) -> None:
    # Owner 2026-11-03: no per-file or total limit.
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    first = _add(a, dataset, name="big.md", text="x" * 5000)
    assert first["size"] == 5000
    _commit(a, vault_id, "加入大檔")
    assert _push(a, vault_id)["status"] == "pushed"
    assert not hasattr(vault_sources, "LIMIT_UNIT")


def test_a_source_added_while_the_folder_is_out_of_reach_stays_here_until_shared(
    tmp_path: Path,
) -> None:
    drive, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    folder = drive.parent("a") / vault_id
    away = tmp_path / "away"
    folder.rename(away)
    source = _add(a, dataset)
    away.rename(folder)
    units = vault.Vault(a, vault_id).repo.working_units()
    assert vault_sources.unit_key(source["sha256"]) not in units
    assert Staging(a, dataset).source(source["id"]) is not None
    value = vault_sources.share(a, vault_id, source["id"], FOLDER)
    assert value["folder"] == FOLDER
    assert _unit(a, vault_id, source["sha256"])["folder"] == FOLDER
    # Sharing again changes nothing.
    assert vault_sources.share(a, vault_id, source["id"], "sources")["folder"] == FOLDER


def test_the_folder_list_for_skills_hides_markdown_folders(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _add(a, dataset, folder=FOLDER)
    _commit(a, vault_id, "加入")
    _push(a, vault_id)
    _, listed = _call(a, "GET", f"/api/bi/vaults/{vault_id}/skills")
    assert FOLDER in listed["folders"]
    assert not [f for f in listed["folders"] if "markdown" in f]


def test_a_name_oneDrive_refuses_is_made_safe_in_the_path_and_kept_in_the_unit(
    tmp_path: Path,
) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _add(a, dataset, name='報告 "Q3"?.md')
    unit = _unit(a, vault_id, source["sha256"])
    assert unit["name"] == '報告 "Q3"?.md'
    assert unit["file"].endswith("報告 _Q3__.md")
    _commit(a, vault_id, "加入")
    assert _push(a, vault_id)["status"] == "pushed"


# -- a colleague's PC (S4) --------------------------------------------------------------


def _shared(tmp_path: Path, **given: Any) -> tuple[Any, str, str, Path, Path, dict[str, Any]]:
    """PC a pushed one source; PC b has not received it yet."""
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _add(a, dataset, **given)
    _commit(a, vault_id, "加入報告")
    _push(a, vault_id)
    return drive, vault_id, dataset, a, b, source


def test_a_colleague_reads_a_pushed_source_with_no_second_copy(tmp_path: Path) -> None:
    drive, vault_id, dataset, _, b, source = _shared(
        tmp_path, folder=FOLDER, classification="RESTRICTED"
    )
    drive.deliver("a", "b", vault_id)
    assert not Staging(b, dataset).sources()  # until this PC syncs
    _sync(b, vault_id)
    staging = Staging(b, dataset)
    (seen,) = staging.sources()
    assert seen["id"] == source["id"] and seen["origin"] == "repository"
    assert seen["classification"] == "RESTRICTED" and seen["markdown_rev"] == 1
    assert staging.source_bytes(source["id"]) == REPORT.encode()
    assert staging.markdown_text(source["id"], 1) == REPORT
    assert staging.stored_file(source["id"]).is_relative_to(drive.parent("b"))
    assert not (staging.dir / "sources").exists()  # read through, not copied
    found = search_index.search(BiStore(b, dataset), "FACT-1")
    assert "FACT-1" in json.dumps(found, ensure_ascii=False)
    assert _sync(b, vault_id)  # again: nothing doubles
    assert len(Staging(b, dataset).sources()) == 1


def test_a_commit_delivered_before_its_file_waits_then_the_source_appears(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, source = _shared(tmp_path)
    unit = _unit(a, vault_id, source["sha256"])
    drive.deliver("a", "b", vault_id)
    target = drive.parent("b") / vault_id / unit["file"]
    held = tmp_path / "held"
    target.rename(held)
    report = _sync(b, vault_id)
    assert report["waiting"][0]["files"] == [unit["file"]]
    assert not Staging(b, dataset).sources()
    held.rename(target)
    _sync(b, vault_id)
    assert Staging(b, dataset).sources()[0]["id"] == source["id"]


def test_a_source_that_cannot_be_read_says_so_and_does_not_stop_the_list(tmp_path: Path) -> None:
    drive, vault_id, dataset, _, b, source = _shared(tmp_path)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    staging = Staging(b, dataset)
    path = staging.stored_file(source["id"])
    path.unlink()
    assert staging.sources()[0]["id"] == source["id"]
    with pytest.raises(BiStoreError) as refused:
        staging.source_bytes(source["id"])
    assert refused.value.code == "source_unreadable"


def test_a_colleague_can_edit_the_markdown_and_it_travels_back(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, source = _shared(tmp_path)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    Staging(b, dataset).add_markdown(
        source["id"], REPORT + "乙補充\n", origin="edit", note="補", actor="bob", base_rev=1
    )
    _commit(b, vault_id, "補 Markdown")
    _push(b, vault_id)
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)
    assert Staging(a, dataset).markdown_text(source["id"], 2).endswith("乙補充\n")
    assert [r["rev"] for r in _unit(a, vault_id, source["sha256"])["markdown"]] == [1, 2]


def test_a_colleague_runs_on_it_and_the_evidence_means_the_same_source(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, source = _shared(
        tmp_path, name="t.csv", text="技術,標準組織\nTSN,IEEE\n"
    )
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    run = _ok(_call(b, "POST", "/api/bi/runs", {"dataset": dataset, "kind": "ingest",
                                                "source_id": source["id"],
                                                "entity_type": "Technology"}))["run"]  # fmt: skip
    detail = _ok(_call(b, "GET", f"/api/bi/runs/{run['id']}", dataset=dataset))
    (candidate,) = detail["candidates"]
    proof = candidate["fields"][0]["evidence"][0]
    assert proof["source_id"] == source["id"]
    assert Staging(a, dataset).source(proof["source_id"]) is not None


def test_a_reverted_source_leaves_a_colleagues_list_but_not_the_adders(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, source = _shared(tmp_path)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    repo = vault.Vault(a, vault_id).repo
    repo.stage(vault_sources.unit_key(source["sha256"]), None)
    _commit(a, vault_id, "拿掉來源")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert Staging(b, dataset).sources() == []
    _sync(a, vault_id)
    assert Staging(a, dataset).source(source["id"]) is not None  # still on the adder's PC


def test_syncing_writes_nothing_to_the_shared_folder(tmp_path: Path) -> None:
    drive, vault_id, dataset, _, b, _ = _shared(tmp_path)
    drive.deliver("a", "b", vault_id)
    folder = drive.parent("b") / vault_id
    before = sorted(str(p) for p in folder.rglob("*"))
    _sync(b, vault_id)
    assert Staging(b, dataset).sources()
    assert sorted(str(p) for p in folder.rglob("*")) == before


def test_converting_a_dataset_stages_its_sources_with_the_ids_its_evidence_uses(
    tmp_path: Path,
) -> None:
    drive = _Drive(tmp_path)
    ws = drive.workspace("a")
    source = _add(ws, "plain", name="t.md", text=REPORT)
    assert source["id"] != source["sha256"][:12]
    BiStore(ws, "plain").apply(
        [_row("TSN", standard_body="IEEE")], filename="t.csv", entity_type="Technology", actor="x"
    )
    made = _ok(
        _call(ws, "POST", "/api/bi/vaults/convert",
              {"dataset": "plain", "path": str(drive.parent("a")), "title": "Plain",
               "author": "alice"})
    )  # fmt: skip
    vault_id = made["vault"]["id"]
    assert made["sources"]["copied"] == 1 and made["sources"]["staged"] == 1
    unit = _unit(ws, vault_id, source["sha256"])
    assert unit["id"] == source["id"] and unit["folder"] == "sources"
    folder = drive.parent("a") / vault_id
    assert not (folder / unit["file"]).exists()  # staged; commit and push stay the person's
    _commit(ws, vault_id, "加入來源")
    _push(ws, vault_id)
    assert (folder / unit["file"]).read_bytes() == REPORT.encode()


# -- what the page is told (S7) ---------------------------------------------------------


def _states(ws: Path, dataset: str) -> dict[str, Any]:
    status, reply = _call(ws, "GET", "/api/bi/sources", dataset=dataset)
    assert status == 200, reply
    return dict(reply)


def test_the_list_says_where_each_source_stands(tmp_path: Path, monkeypatch: Any) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    source = _add(a, dataset, folder=FOLDER)
    (seen,) = _states(a, dataset)["sources"]
    assert seen["shared"] == "staged" and seen["folder"] == FOLDER
    _commit(a, vault_id, "加入")
    _push(a, vault_id)
    assert _states(a, dataset)["sources"][0]["shared"] == "pushed"
    monkeypatch.setattr(vault_sources, "cloud_only", lambda _path: True)
    assert _states(a, dataset)["sources"][0]["shared"] == "cloud_only"
    monkeypatch.undo()
    # A commit delivered before its file: the file is named, the source not listed yet.
    unit = _unit(a, vault_id, source["sha256"])
    drive.deliver("a", "b", vault_id)
    target = drive.parent("b") / vault_id / unit["file"]
    held = tmp_path / "held"
    target.rename(held)
    _sync(b, vault_id)
    seen = _states(b, dataset)
    assert seen["sources"] == [] and seen["waiting"] == [unit["file"]]
    held.rename(target)
    _sync(b, vault_id)
    assert _states(b, dataset)["sources"][0]["shared"] == "pushed"


def test_a_source_only_on_this_pc_is_listed_and_shared_through_the_route(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    folder = drive.parent("a") / vault_id
    away = tmp_path / "away"
    folder.rename(away)
    source = _add(a, dataset)
    away.rename(folder)
    assert _states(a, dataset)["sources"][0]["shared"] == "local"
    done = _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/share-source",
                     {"source_id": source["id"], "folder": FOLDER}))  # fmt: skip
    assert done["source"]["folder"] == FOLDER
    assert _states(a, dataset)["sources"][0]["shared"] == "staged"
    status, refused = _call(a, "POST", f"/api/bi/vaults/{vault_id}/share-source",
                            {"source_id": "nope"})  # fmt: skip
    assert status != 200 and refused["code"] == "source_unknown"


def test_a_dataset_only_on_this_pc_lists_no_shared_state(tmp_path: Path) -> None:
    _, _, _, a, _ = _two_pcs(tmp_path)
    _add(a, "demo-local", name="x.md", text="# x\n")
    (seen,) = _states(a, "demo-local")["sources"]
    assert "shared" not in seen


def test_cloud_only_asks_for_attributes_and_reads_nothing(tmp_path: Path) -> None:
    path = tmp_path / "x.bin"
    path.write_bytes(b"x")
    assert vault_sources.cloud_only(path) is False
    assert vault_sources.cloud_only(tmp_path / "gone.bin") is False


# -- large files (S6) --------------------------------------------------------------------


def _send(server: Any, body: Any, length: int, **query: str) -> tuple[int, dict[str, Any]]:
    """The page's raw upload: a file object, sent as it is read."""
    url = f"http://127.0.0.1:{server.server_address[1]}/api/bi/sources/upload?{urlencode(query)}"
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Authorization", f"Bearer {server.token}")
    request.add_header("Content-Length", str(length))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=120) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


def test_a_large_file_is_added_committed_pushed_and_synced_without_being_held_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    size = 9 * 1024 * 1024  # over what base64 under the 8 MiB JSON limit can carry
    original = tmp_path / "large.bin"
    original.write_bytes(os.urandom(1024) * (size // 1024))
    real = Path.read_bytes

    def no_whole_file(path: Path) -> bytes:
        assert path.stat().st_size < size, f"{path.name} read whole into memory"
        return real(path)

    monkeypatch.setattr(Path, "read_bytes", no_whole_file)
    config, layout = _bi_host(tmp_path / "host")
    with _served(config, layout, _Model("none", {})) as server:
        (workspace, target) = (layout.workspace_root, tmp_path / "shared-host")
        target.mkdir()
        made = _ok(_call(workspace, "POST", "/api/bi/vaults",
                         {"path": str(target), "title": "Large", "schema": "bi.schema/v1.1",
                          "author": "alice"}))  # fmt: skip
        vault_id = str(made["vault"]["id"])
        dataset = f"vault-{vault_id}"
        with original.open("rb") as body:
            status, reply = _send(server, body, size, dataset=dataset, name="large.bin",
                                  folder=FOLDER, classification="RESTRICTED")  # fmt: skip
        assert status == 200, reply
        source = reply["source"]
        assert source["size"] == size and source["already"] is False
        with original.open("rb") as body:  # the same bytes are kept once
            assert (
                _send(server, body, size, dataset=dataset, name="again.bin")[1]["source"]["already"]
                is True
            )
    assert not list(Staging(workspace, dataset).dir.glob(".upload-*"))
    _commit(workspace, vault_id, "加入大檔")
    assert _push(workspace, vault_id)["status"] == "pushed"
    unit = _unit(workspace, vault_id, source["sha256"])
    delivered = target / vault_id / unit["file"]
    assert delivered.stat().st_size == size
    assert _file_sha(delivered) == _file_sha(original)
    # A colleague's PC hashes and lists it without holding it either.
    other = tmp_path / "other-ws"
    other.mkdir()
    _ok(_call(other, "POST", "/api/bi/vaults/join",
              {"path": str(target / vault_id), "author": "bob"}))  # fmt: skip
    (seen,) = Staging(other, dataset).sources()
    assert seen["size"] == size and seen["origin"] == "repository"


def test_an_upload_cut_short_or_badly_named_keeps_nothing(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "host")
    with _served(config, layout, _Model("none", {})) as server:
        status, reply = _send(server, b"x" * 10, 10, dataset="plain", name="a/b.md")
        assert status == 400 and reply["code"] == "source_name_invalid"
        status, reply = _send(server, b"x", 1, dataset="plain", name="a.md", classification="NO")
        assert status == 400 and reply["code"] == "classification_invalid"
    staging = Staging(layout.workspace_root, "plain")
    with pytest.raises(BiStoreError) as refused:
        staging.add_source_stream("a.bin", "INTERNAL", io.BytesIO(b"xx"), 10, actor="alice")
    assert refused.value.code == "source_incomplete"
    assert not list(staging.dir.glob(".upload-*")) and staging.sources() == []


def test_a_withdrawn_file_sent_again_as_a_large_upload_is_refused(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _, source = _shared(tmp_path)
    _ok(_withdraw(a, vault_id, source))
    staging = Staging(a, dataset)
    with pytest.raises(BiStoreError) as refused:
        staging.add_source_stream(
            "report.md", "INTERNAL", io.BytesIO(REPORT.encode()), len(REPORT.encode()), actor="a"
        )
    assert refused.value.code == "source_withdrawn"
    assert not list(staging.dir.glob(".upload-*"))


# -- withdrawal (S9) ---------------------------------------------------------------------


def _withdraw(ws: Path, vault_id: str, source: dict[str, Any], **given: Any) -> Any:
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/withdraw-source",
                 {"source_id": source["id"], "confirm": True, **given})  # fmt: skip


def test_withdrawing_removes_the_files_and_each_pcs_copy_and_the_commit_stays(
    tmp_path: Path,
) -> None:
    drive, vault_id, dataset, a, b, source = _shared(tmp_path, folder=FOLDER)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    unit = _unit(a, vault_id, source["sha256"])
    stored = Staging(a, dataset).stored_file(source["id"])
    folder = drive.parent("a") / vault_id
    done = _ok(_withdraw(a, vault_id, source, reason="放錯了"))
    assert done["withdrawn"]["left"] == []
    assert not (folder / unit["file"]).exists()
    assert not (folder / unit["markdown"][0]["file"]).exists()
    assert not stored.exists() and Staging(a, dataset).source(source["id"]) is None
    # The commit stays applied on a rebuild: nothing waits for good.
    repo = vault.Vault(a, vault_id).repo
    assert repo.sync()["waiting"] == []
    assert repo.head() is not None
    # The other PC: the record arrives, OneDrive removes its copy of the files.
    target = drive.parent("b") / vault_id
    drive.deliver("a", "b", vault_id)
    (target / unit["file"]).unlink()
    (target / unit["markdown"][0]["file"]).unlink()
    report = _sync(b, vault_id)
    assert report["waiting"] == [] and Staging(b, dataset).sources() == []
    listed = _states(b, dataset)
    assert listed["sources"] == [] and listed["withdrawn"][0]["file"] == unit["file"]
    assert listed["withdrawn"][0]["reason"] == "放錯了"
    assert search_index.search(BiStore(b, dataset), "FACT-1")["passages"] == []


def test_a_withdrawal_needs_a_person_and_a_pushed_source(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    source = _add(a, dataset)
    status, reply = _withdraw(a, vault_id, source, confirm=False)
    assert status != 200 and reply["code"] == "confirm_required"
    status, reply = _withdraw(a, vault_id, source)
    assert status != 200 and reply["code"] == "source_not_pushed"
    assert Staging(a, dataset).source(source["id"]) is not None


def test_a_withdrawn_file_cannot_come_back(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    # Bob stages the same bytes and commits, unpushed, before Alice withdraws hers.
    bobs = _add(b, dataset)
    _commit(b, vault_id, "乙也加入")
    source = _add(a, dataset)
    assert bobs["sha256"] == source["sha256"]
    _commit(a, vault_id, "加入")
    _push(a, vault_id)
    _ok(_withdraw(a, vault_id, source))
    # Adding the same bytes again is refused and nothing is kept.
    with pytest.raises(BiStoreError) as refused:
        _add(a, dataset)
    assert refused.value.code == "source_withdrawn"
    assert Staging(a, dataset).sources() == []
    # Bob's unpushed commit does not bring it back, here as a conflict on its unit; the
    # engine's own refusal is `test_an_unpushed_commit_cannot_bring_a_withdrawn_file_back`.
    drive.deliver("a", "b", vault_id)
    target = drive.parent("b") / vault_id
    gone = _unit(a, vault_id, source["sha256"])["file"]
    (target / gone).unlink(missing_ok=True)
    status, reply = _call(b, "POST", f"/api/bi/vaults/{vault_id}/push", {})
    assert status != 200 or reply["status"] != "pushed"
    assert not (target / gone).exists()


def test_withdrawing_removes_open_candidates_and_blanks_a_written_runs_excerpts(
    tmp_path: Path,
) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    csv = "技術,標準組織\nTSN,IEEE\nPTP,IETF\n"
    source = _add(a, dataset, name="t.csv", text=csv)
    body = {"dataset": dataset, "kind": "ingest", "source_id": source["id"],
            "entity_type": "Technology"}  # fmt: skip
    written = _ok(_call(a, "POST", "/api/bi/runs", body))["run"]
    detail = _ok(_call(a, "GET", f"/api/bi/runs/{written['id']}", dataset=dataset))
    for candidate in detail["candidates"]:
        _ok(_call(a, "POST", f"/api/bi/runs/{written['id']}/candidates/{candidate['id']}",
                  {"dataset": dataset, "review": "accepted"}))  # fmt: skip
    _ok(_call(a, "POST", f"/api/bi/runs/{written['id']}/commit", {"dataset": dataset}))
    still_open = _ok(_call(a, "POST", "/api/bi/runs", body))["run"]
    _push(a, vault_id)
    _ok(_withdraw(a, vault_id, source))
    staging = Staging(a, dataset)
    assert staging.candidates(still_open["id"]) == []
    assert (staging.run_row(still_open["id"]) or {})["status"] == "failed"
    kept = staging.candidates(written["id"])
    assert kept and (staging.run_row(written["id"]) or {})["status"] == "committed"
    excerpts = [p["excerpt"] for c in kept for f in c["fields"] for p in f["evidence"]]
    assert excerpts and set(excerpts) == {""}
    # What a commit holds stays, as the page says (owner, Q1).
    assert "IEEE" in json.dumps(vault.Vault(a, vault_id).repo.units(), ensure_ascii=False)


def test_a_record_delivered_after_the_deletion_only_waits_until_it_arrives(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b, source = _shared(tmp_path)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    unit = _unit(a, vault_id, source["sha256"])
    _ok(_withdraw(a, vault_id, source))
    target = drive.parent("b") / vault_id
    (target / unit["file"]).unlink()
    # OneDrive delivered the deletion first: the commit waits for now.
    report = _sync(b, vault_id)
    assert report["waiting"][0]["files"] == [unit["file"]]
    drive.deliver("a", "b", vault_id)
    (target / unit["markdown"][0]["file"]).unlink(missing_ok=True)
    assert _sync(b, vault_id)["waiting"] == []
    assert Staging(b, dataset).sources() == []


def test_a_cards_database_ignores_the_source_units(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _add(a, dataset)
    _commit(a, vault_id, "加入")
    _push(a, vault_id)
    target = vault.Vault(a, vault_id)
    target.rebuild()
    assert "source:" not in json.dumps(vault.reading_store(a, dataset).card_rows())
