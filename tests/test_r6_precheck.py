"""The R6 pre-checks only look (`scripts/r6_precheck.py`). All folders are fictional."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from scripts import r6_precheck as precheck


def _state(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        info = path.stat()
        digest.update(f"{path}{info.st_mtime_ns}{info.st_size}".encode())
    return digest.hexdigest()


def _world(tmp_path: Path) -> dict[str, Path]:
    shared = tmp_path / "BI_Knowledge"
    (shared / "market-bi" / "changes").mkdir(parents=True)
    (shared / "market-bi" / "vault.json").write_text("{}", encoding="utf-8")
    base = tmp_path / "aidc-bi-kb"
    (base / "cards").mkdir(parents=True)
    (base / "cards" / "a.md").write_text("# A", encoding="utf-8")
    (base / "seed.csv").write_text("name\nA\n", encoding="utf-8")
    copy = tmp_path / "rs-k-copy"
    (copy / "wiki").mkdir(parents=True)
    real = tmp_path / "RS_Knowledge"
    real.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    return {"shared": shared, "base": base, "copy": copy, "real": real, "target": target}


def _status(found: list[precheck.Check], name: str) -> str:
    return next(item.status for item in found if item.name == name)


def _run(w: dict[str, Path]) -> list[precheck.Check]:
    return precheck.run(w["shared"], [w["base"]] * 5, w["copy"], w["real"], w["target"])


def test_a_ready_world_passes_and_nothing_is_touched(tmp_path: Path) -> None:
    w = _world(tmp_path)
    before = _state(tmp_path)
    found = _run(w)
    assert _state(tmp_path) == before
    assert not [item for item in found if item.status != "ok"], found


def test_the_script_has_no_way_to_write_or_open_a_file() -> None:
    tree = ast.parse(Path(precheck.__file__).read_text(encoding="utf-8"))
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not imported & {"subprocess", "shutil", "os"}
    assert not called & {"open", "write_text", "write_bytes", "read_text", "read_bytes", "mkdir"}
    assert not called & {"unlink", "rename", "replace", "rmdir", "touch", "chmod", "rmtree"}


@pytest.mark.parametrize(
    ("change", "name", "status"),
    [
        (lambda w: (w["shared"] / "market-bi" / "repo.json").write_text("{}"), "old_vault", "fail"),
        (lambda w: (w["shared"] / "market-bi.v4-old").mkdir(), "rename_target", "fail"),
    ],
)
def test_a_state_that_would_break_the_session_fails(
    tmp_path: Path, change: object, name: str, status: str
) -> None:
    w = _world(tmp_path)
    change(w)  # type: ignore[operator]
    assert _status(_run(w), name) == status


def test_a_missing_shared_folder_or_base_fails(tmp_path: Path) -> None:
    w = _world(tmp_path)
    assert _status(precheck.run(tmp_path / "none", []), "shared_folder") == "fail"
    assert _status(precheck.run(w["shared"], [tmp_path / "gone"]), "base:gone") == "fail"
    assert _status(precheck.run(w["shared"], [w["base"]]), "base_count") == "warn"


def test_a_vault_id_this_pc_already_holds_fails(tmp_path: Path) -> None:
    w = _world(tmp_path)
    workspace = tmp_path / "ws"
    (workspace / "bi" / "vault-market-bi").mkdir(parents=True)
    found = precheck.run(w["shared"], [], workspace=workspace)
    assert _status(found, "vault_id_free") == "fail"
    found = precheck.run(w["shared"], [], workspace=workspace, vault_id="market-intel")
    assert _status(found, "vault_id_free") == "ok"
    assert _status(precheck.run(w["shared"], [], workspace=tmp_path / "no"), "workspace") == "fail"


def test_the_wiki_copy_must_be_a_wiki_and_not_the_real_one(tmp_path: Path) -> None:
    w = _world(tmp_path)
    inner = w["real"] / "copy"
    (inner / "wiki").mkdir(parents=True)
    found = precheck.run(w["shared"], [], inner, w["real"], w["target"])
    assert _status(found, "wiki_copy_is_a_copy") == "fail"
    other = tmp_path / "not-wiki"
    other.mkdir()
    assert _status(precheck.run(w["shared"], [], other), "wiki_copy") == "fail"
    (w["copy"] / "new").mkdir()
    found = precheck.run(w["shared"], [], w["copy"], w["real"], w["copy"] / "new")
    assert _status(found, "wiki_target") == "fail"


def test_the_command_exits_by_failures_and_prints_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    w = _world(tmp_path)
    assert precheck.main(["--shared", str(w["shared"]), "--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert {"name", "status", "detail"} <= set(printed[0])
    assert precheck.main(["--shared", str(tmp_path / "none")]) == 1
