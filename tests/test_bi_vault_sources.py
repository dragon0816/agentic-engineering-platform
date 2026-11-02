"""A vault's originals in the shared folder (`docs/phases/BI_SOURCES_IN_REPOSITORY.md`).

Two PCs as in `test_bi_vault.py`. All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _edit, _import, _ok, _push, _row, _status, _two_pcs

from capabilities.bi_cards import vault, vault_sources
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStoreError

REPORT = "# AIDC 報告\n\n電源模組 FACT-1。\n"
FOLDER = "sources/library/products"


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


def test_the_limit_refuses_on_adding_and_blocks_a_push_with_no_number_invented(
    tmp_path: Path,
) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    # Without a number set by the owner nothing is refused for its size.
    big = "x" * 5000
    first = _add(a, dataset, name="big.md", text=big)
    assert first["size"] == 5000
    assert vault_sources.limit_of(vault.Vault(a, vault_id).repo.working_units()) is None
    repo = vault.Vault(a, vault_id).repo
    repo.stage(vault_sources.LIMIT_UNIT, "1000")
    with pytest.raises(BiStoreError) as refused:
        _add(a, dataset, name="big2.md", text="y" * 5000)
    assert refused.value.code == "source_too_large"
    assert not [s for s in Staging(a, dataset).sources() if s["name"] == "big2.md"]
    # One already staged, or staged by a PC without the limit, is blocked at the push.
    _commit(a, vault_id, "加入大檔")
    answer = _push(a, vault_id)
    assert answer["status"] == "blocked" and "big.md" in json.dumps(answer, ensure_ascii=False)


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


def test_a_cards_database_ignores_the_source_units(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _add(a, dataset)
    _commit(a, vault_id, "加入")
    _push(a, vault_id)
    target = vault.Vault(a, vault_id)
    target.rebuild()
    assert "source:" not in json.dumps(vault.reading_store(a, dataset).card_rows())
