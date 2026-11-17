"""A status reads the commit files once while they stay the same, and never misses a change.

On market-intel, a status read and checked 46 commit files twice, seconds each, and the page asks
for one with every load. What a sync or a rebuild uses still reads the files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_bi_vault import _call, _commit, _ok, _push, _sync, _two_pcs

from aep_bi.cards import vault
from knowledge.repo import repository


def _counted(monkeypatch: Any) -> list[int]:
    reads: list[int] = []
    original = repository.Repository.scan

    def counting(self: repository.Repository) -> repository.Scan:
        reads.append(1)
        return original(self)

    monkeypatch.setattr(repository.Repository, "scan", counting)
    return reads


def _status(ws: Path, vault_id: str) -> dict[str, Any]:
    return vault.Vault(ws, vault_id).repo.status()


def _question(ws: Path, vault_id: str, text: str) -> None:
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/checks", {"question": text}))


def test_a_second_status_reads_no_commit_file(tmp_path: Path, monkeypatch: Any) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    repository._SCANS.clear()
    reads = _counted(monkeypatch)
    first = _status(a, vault_id)
    assert len(reads) == 1
    second = _status(a, vault_id)
    assert len(reads) == 1 and second == first
    vault.Vault(a, vault_id).repo.history()
    assert len(reads) == 1


def test_a_commit_that_arrives_is_seen_at_once(tmp_path: Path) -> None:
    drive, vault_id, _dataset, a, b = _two_pcs(tmp_path)
    assert _status(b, vault_id)["behind"] == 0
    _question(a, vault_id, "虛構？")
    _commit(a, vault_id, "加題目")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    assert _status(b, vault_id)["behind"] == 1
    _sync(b, vault_id)
    status = _status(b, vault_id)
    assert status["behind"] == 0
    assert vault.Vault(b, vault_id).repo.history()[0]["purpose"] == "加題目"


def test_a_commit_file_changed_in_place_is_read_again(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    target = vault.Vault(a, vault_id)
    assert _status(a, vault_id)["bad"] == []
    path = next((target.folder / "commits").rglob("*.json"))
    document = json.loads(path.read_text("utf-8"))
    document["seq_was_tampered"] = True
    path.write_text(json.dumps(document), "utf-8")
    assert _status(a, vault_id)["bad"] != []


def test_a_file_that_cannot_be_read_yet_is_not_kept(tmp_path: Path, monkeypatch: Any) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    target = vault.Vault(a, vault_id)
    (target.folder / "commits" / "alice" / "99.json").write_text("{half", "utf-8")
    reads = _counted(monkeypatch)
    _status(a, vault_id)
    _status(a, vault_id)
    assert len(reads) == 2


def test_what_hands_on_values_still_reads_the_files(tmp_path: Path, monkeypatch: Any) -> None:
    # A caller may change what `state_at` and `log` give it, and a kept scan must not be that.
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    repo = vault.Vault(a, vault_id).repo
    head = repo.head()
    assert head is not None
    _status(a, vault_id)
    reads = _counted(monkeypatch)
    repo.state_at(head)
    repo.log()
    assert len(reads) == 2
