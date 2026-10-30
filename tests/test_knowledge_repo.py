"""Knowledge repositories R1: the common version layer (docs/phases/KNOWLEDGE_REPO.md).

Two PCs are two workspaces sharing one repository folder; a minimal test type
stands in for wiki and BI.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from knowledge.repo import CheckReport, RepoError, Repository, create, join, register_type


class NoteType:
    """Units are short texts; a value `BLOCK` fails the push check."""

    name = "test-notes"

    def unit_problem(self, key: str, value: Any) -> str | None:
        return None if isinstance(value, str) and len(value) < 200 else "value must be a short text"

    def check(self, before: Mapping[str, Any], after: Mapping[str, Any]) -> CheckReport:
        blocking = [f"{k} is blocked" for k, v in after.items() if v == "BLOCK"]
        added = len(set(after) - set(before))
        return CheckReport(blocking=blocking, notes=[f"{added} units added"])


register_type(NoteType())


@pytest.fixture
def pcs(tmp_path: Path) -> tuple[Repository, Repository]:
    shared = tmp_path / "shared"
    shared.mkdir()
    a = create(
        tmp_path / "pc-a",
        shared,
        repo_id="notes",
        title="Notes",
        purpose="test",
        kind="test-notes",
        author="alice",
    )
    b = join(tmp_path / "pc-b", shared / "notes", author="bob")
    return a, b


def change(repo: Repository, purpose: str, **units: str | None) -> dict[str, Any]:
    for key, value in units.items():
        repo.stage(key, value)
    return repo.commit(purpose)


def test_create_lays_out_the_folder(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    names = {p.name for p in a.folder.iterdir()}
    assert {
        "repo.json",
        "REPO.md",
        "schemas",
        "skills",
        "sources",
        "commits",
        "tags",
        "publish",
    } <= names
    assert json.loads((a.folder / "repo.json").read_text(encoding="utf-8"))["type"] == "test-notes"


def test_commit_needs_a_purpose(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    a.stage("x", "1")
    with pytest.raises(RepoError) as failure:
        a.commit("   ")
    assert failure.value.code == "purpose_missing"
    with pytest.raises(RepoError) as failure:
        a.commit("x" * 501)
    assert failure.value.code == "purpose_too_long"


def test_commit_is_local_until_pushed(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    change(a, "first notes", x="1", y="2")
    assert a.status()["ahead"] == 1
    assert list((a.folder / "commits").iterdir()) == []
    result = a.push()
    assert result["status"] == "pushed"
    assert result["notes"] == ["2 units added"]
    b.sync()
    assert b.units() == {"x": "1", "y": "2"}
    assert b.history()[0]["purpose"] == "first notes"
    assert a.status()["ahead"] == 0


def test_different_units_merge(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    change(a, "base", x="1", y="1")
    a.push()
    b.sync()
    change(a, "a edits x", x="2")
    change(b, "b edits y", y="2")
    assert a.push()["status"] == "pushed"
    assert b.push()["status"] == "pushed"  # rebased onto a's commit
    a.sync()
    assert a.units() == b.units() == {"x": "2", "y": "2"}
    assert a.head() == b.head()


def test_same_unit_is_a_conflict_until_resolved(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    change(a, "base", x="1")
    a.push()
    b.sync()
    change(a, "a edits x", x="from a")
    change(b, "b edits x", x="from b")
    a.push()
    files_before = sorted(p.name for p in (a.folder / "commits").rglob("*.json"))
    result = b.push()
    assert result["status"] == "conflicts"
    assert result["conflicts"] == [
        {"unit": "x", "mine": "from b", "theirs": "from a", "purpose": "b edits x"}
    ]
    assert sorted(p.name for p in (a.folder / "commits").rglob("*.json")) == files_before
    b.resolve("x", "mine")
    assert b.push()["status"] == "pushed"
    a.sync()
    assert a.units() == b.units() == {"x": "from b"}


def test_choosing_theirs_drops_the_change(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    change(a, "base", x="1")
    a.push()
    b.sync()
    change(a, "a edits x", x="from a")
    change(b, "b edits x", x="from b")
    a.push()
    b.push()
    b.resolve("x", "theirs")
    assert b.push()["status"] == "pushed"
    assert not (a.folder / "commits" / "bob").exists()  # nothing left to write
    assert b.units() == {"x": "from a"}


def test_blocking_check_writes_nothing(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    change(a, "bad", x="BLOCK")
    result = a.push()
    assert result == {"status": "blocked", "blocking": ["x is blocked"], "notes": ["1 units added"]}
    assert list((a.folder / "commits").iterdir()) == []
    assert a.status()["ahead"] == 1


def test_revert_to_a_tag_and_back(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    change(a, "v1", x="1", y="1")
    a.push()
    a.tag("v1", "first release")
    change(a, "v2", x="2", z="new")
    a.push()
    before_revert = a.units()
    a.revert("v1", "the v2 numbers were wrong")
    assert a.push()["status"] == "pushed"
    assert a.units() == {"x": "1", "y": "1"}
    reverted = a.history()[0]
    assert reverted["kind"] == "revert" and reverted["restores"] == a.resolve_version("v1")
    a.revert(a.history()[1]["id"], "undo the revert")
    a.push()
    assert a.units() == before_revert
    b.sync()
    assert b.units() == before_revert
    assert len(b.history()) == 4  # history is never rewritten


def test_revert_needs_a_clean_working_copy(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    change(a, "v1", x="1")
    a.push()
    a.tag("v1", "release")
    a.stage("x", "2")
    with pytest.raises(RepoError) as failure:
        a.revert("v1", "back")
    assert failure.value.code == "work_not_clean"


def test_published_version_is_what_readers_get(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    change(a, "v1", x="1")
    a.push()
    assert a.published_units() == {"x": "1"}  # never published: the head
    a.tag("v1", "release")
    a.publish("v1")
    change(a, "work in progress", x="2")
    a.push()
    b.sync()
    assert b.units() == {"x": "2"}
    assert b.published_units() == {"x": "1"}
    assert b.status()["published"]["tag"] == "v1"
    b.tag("v2", "next release")
    b.publish("v2")
    assert a.published_units() == {"x": "2"}
    a.publish("v1")  # withdraw v2 by publishing v1 again
    assert b.published_units() == {"x": "1"}


def test_tags_never_move(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    change(a, "v1", x="1")
    a.push()
    a.tag("v1", "release")
    with pytest.raises(RepoError) as failure:
        a.tag("v1", "again")
    assert failure.value.code == "tag_exists"
    with pytest.raises(RepoError) as failure:
        a.tag("Bad Name", "x")
    assert failure.value.code == "tag_invalid"
    with pytest.raises(RepoError) as failure:
        a.publish("nope")
    assert failure.value.code == "tag_unknown"


def test_files_wait_for_sync_and_are_checked(
    pcs: tuple[Repository, Repository], tmp_path: Path
) -> None:
    a, b = pcs
    source = tmp_path / "report.md"
    source.write_text("# report\n", encoding="utf-8")
    a.stage_file("sources/market/3f9a1c2b-report.md", source)
    a.stage("doc", "report")
    a.commit("add the report")
    a.push()
    stored = a.folder / "sources/market/3f9a1c2b-report.md"
    assert stored.read_text(encoding="utf-8") == "# report\n"

    # OneDrive has delivered the commit but not the file yet.
    hidden = tmp_path / "hidden.md"
    shutil.move(stored, hidden)
    result = b.sync()
    assert result["waiting"] == [
        {"commit": "alice/1", "files": ["sources/market/3f9a1c2b-report.md"]}
    ]
    assert b.units() == {}
    shutil.move(hidden, stored)
    b.sync()
    assert b.units() == {"doc": "report"}

    # A file changed after it was written is reported and its commit dropped.
    stored.write_text("edited\n", encoding="utf-8")
    result = b.sync()
    assert result["rebuilt"] and result["changed"][0]["commit"] == "alice/1"
    assert b.units() == {}


def test_file_paths_are_checked(pcs: tuple[Repository, Repository], tmp_path: Path) -> None:
    a, _ = pcs
    source = tmp_path / "x.md"
    source.write_text("x", encoding="utf-8")
    for bad in ("../x.md", "wiki/x.md", "sources/.hidden/x.md", "sources\\x.md"):
        with pytest.raises(RepoError) as failure:
            a.stage_file(bad, source)
        assert failure.value.code == "path_invalid"


def test_written_file_cannot_change(pcs: tuple[Repository, Repository], tmp_path: Path) -> None:
    a, _ = pcs
    first = tmp_path / "a.md"
    first.write_text("one", encoding="utf-8")
    a.stage_file("sources/a.md", first)
    a.commit("add a")
    a.push()
    first.write_text("two", encoding="utf-8")
    with pytest.raises(RepoError) as failure:
        a.stage_file("sources/a.md", first)
    assert failure.value.code == "path_taken"


def test_race_is_caught_on_replay_the_same_on_every_pc(
    pcs: tuple[Repository, Repository], tmp_path: Path
) -> None:
    a, b = pcs
    change(a, "base", x="1")
    a.push()
    b.sync()
    change(a, "a edits x", x="from a")
    a.push()
    # OneDrive has not delivered a's commit to b when b pushes.
    delayed = a.folder / "commits" / "alice" / "2.json"
    parked = tmp_path / "parked.json"
    shutil.move(delayed, parked)
    change(b, "b edits x", x="from b")
    assert b.push()["status"] == "pushed"
    shutil.move(parked, delayed)
    a.sync()
    b.sync()
    assert a.units() == b.units()
    assert len(a.conflicts()) == len(b.conflicts()) == 1
    # A later commit on the unit supersedes the open conflict.
    change(a, "settle x", x="agreed")
    a.push()
    b.sync()
    assert b.conflicts() == [] and b.units() == {"x": "agreed"}


def test_tampered_commit_is_reported(pcs: tuple[Repository, Repository]) -> None:
    a, b = pcs
    change(a, "v1", x="1")
    a.push()
    path = a.folder / "commits" / "alice" / "1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ops"][0]["value"] = "forged"
    path.write_text(json.dumps(data), encoding="utf-8")
    result = b.sync()
    assert result["bad"] == [
        {"file": "commits/alice/1.json", "reason": "id does not match the content"}
    ]
    assert b.units() == {}


def test_diff_and_history(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    change(a, "v1", x="1", y="1")
    change(a, "v2", x="2", y=None)
    a.push()
    first, second = reversed(a.history())
    assert [first["purpose"], second["purpose"]] == ["v1", "v2"]
    assert a.diff(second["id"]) == [
        {"unit": "x", "before": "1", "after": "2"},
        {"unit": "y", "before": "1", "after": None},
    ]


def test_unit_values_are_checked_by_the_type(pcs: tuple[Repository, Repository]) -> None:
    a, _ = pcs
    with pytest.raises(RepoError) as failure:
        a.stage("x", 42)
    assert failure.value.code == "unit_invalid"


def test_one_person_on_a_local_folder(tmp_path: Path) -> None:
    parent = tmp_path / "disk"
    parent.mkdir()
    repo = create(
        tmp_path / "pc",
        parent,
        repo_id="solo",
        title="Solo",
        purpose="",
        kind="test-notes",
        author="leo.chi",
    )
    change(repo, "notes", x="1")
    assert repo.push()["status"] == "pushed"
    repo.tag("v1", "release")
    repo.publish("v1")
    assert repo.published_units() == {"x": "1"}
    # Moving the folder into a shared library keeps its history.
    moved = tmp_path / "onedrive"
    moved.mkdir()
    shutil.move(parent / "solo", moved / "solo")
    other = join(tmp_path / "pc-2", moved / "solo", author="bob")
    other.sync()
    assert other.history()[0]["purpose"] == "notes" and other.published_units() == {"x": "1"}
