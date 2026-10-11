"""Personal ingest sandboxes over a base vault (K1, owner 2026-10-11)."""

import json
from pathlib import Path

import pytest

from knowledge.evolution import decision_digest, knowledge_digest, raw_digest
from knowledge.sandbox import SandboxError, Sandboxes
from knowledge.vault import Vault


def _base(tmp_path: Path) -> Path:
    root = tmp_path / "base"
    for folder in ("drop", "raw/notes", "wiki/concepts", ".ingest-backup/old"):
        (root / folder).mkdir(parents=True)
    (root / "index.md").write_text("# Index\n", encoding="utf-8")
    (root / "log.md").write_text("# Log\n", encoding="utf-8")
    (root / "decisions.md").write_text("# Decisions\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("schema\n", encoding="utf-8")
    (root / "raw/notes/a.md").write_text("---\ntitle: a\n---\nA\n", encoding="utf-8")
    (root / "wiki/concepts/EVM.md").write_text("---\ntitle: EVM\n---\nEVM\n", encoding="utf-8")
    (root / ".ingest-backup/old/x.md").write_text("old", encoding="utf-8")
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_a_sandbox_is_a_full_copy_with_its_base_digests(tmp_path: Path) -> None:
    base = _base(tmp_path)
    boxes = Sandboxes(tmp_path / "workspace")
    info = boxes.create("k-test", base, label="VNA trial", actor="leo.chi")
    assert info.sandbox_id.startswith("sb-vna-trial-")
    _, vault = boxes.open(info.sandbox_id)
    assert (vault.root / "wiki/concepts/EVM.md").read_text(encoding="utf-8").endswith("EVM\n")
    assert (vault.root / "CLAUDE.md").exists() and (vault.root / "drop").is_dir()
    assert not (vault.root / ".ingest-backup").exists()  # backups are not copied
    base_vault = Vault(base)
    assert info.base_raw_sha256 == raw_digest(base_vault)
    assert info.base_content_sha256 == knowledge_digest(base_vault)
    assert info.base_decisions_sha256 == decision_digest(base_vault)
    recorded = json.loads((vault.root / "sandbox.json").read_text(encoding="utf-8"))
    assert recorded["created_by"] == "leo.chi" and recorded["base_name"] == "k-test"


def test_writes_in_a_sandbox_never_reach_the_base(tmp_path: Path) -> None:
    base = _base(tmp_path)
    before = _snapshot(base)
    boxes = Sandboxes(tmp_path / "workspace")
    info = boxes.create("k-test", base, label="t", actor="a")
    _, vault = boxes.open(info.sandbox_id)
    (vault.root / "wiki/concepts/EVM.md").write_text("changed", encoding="utf-8")
    (vault.root / "drop/new.txt").write_text("new", encoding="utf-8")
    assert _snapshot(base) == before


def test_list_open_and_discard(tmp_path: Path) -> None:
    base = _base(tmp_path)
    boxes = Sandboxes(tmp_path / "workspace")
    first = boxes.create("k-test", base, label="one", actor="a")
    second = boxes.create("k-test", base, label="two", actor="a")
    assert {b.sandbox_id for b in boxes.list()} == {first.sandbox_id, second.sandbox_id}
    boxes.discard(first.sandbox_id)
    assert [b.sandbox_id for b in boxes.list()] == [second.sandbox_id]
    # Discarded, never deleted.
    discarded = tmp_path / "workspace" / "knowledge-sandboxes" / ".discarded"
    assert any(p.name == first.sandbox_id for p in discarded.iterdir())
    with pytest.raises(SandboxError, match="unknown_sandbox"):
        boxes.open(first.sandbox_id)


@pytest.mark.parametrize("bad", ["../escape", "sb-x/../../y", "", ".discarded", "C:/x"])
def test_ids_that_leave_the_sandboxes_root_are_refused(tmp_path: Path, bad: str) -> None:
    boxes = Sandboxes(tmp_path / "workspace")
    with pytest.raises(SandboxError):
        boxes.open(bad)


def test_working_state_is_not_copied_and_ids_stay_short(tmp_path: Path) -> None:
    base = _base(tmp_path)
    (base / ".ingest-snapshot/old").mkdir(parents=True)
    (base / ".ingest-snapshot/old/x.md").write_text("x", encoding="utf-8")
    boxes = Sandboxes(tmp_path / "workspace", root=tmp_path / "sb")
    info = boxes.create("k-test", base, label="A very long sandbox label indeed", actor="a")
    assert len(info.sandbox_id) <= 26 and (tmp_path / "sb" / info.sandbox_id).is_dir()
    assert not (tmp_path / "sb" / info.sandbox_id / ".ingest-snapshot").exists()


def test_a_base_that_is_not_a_vault_is_refused(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(SandboxError, match="base_not_a_vault"):
        Sandboxes(tmp_path / "workspace").create("x", tmp_path / "empty", label="t", actor="a")
