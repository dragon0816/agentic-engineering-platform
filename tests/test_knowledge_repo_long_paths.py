"""A repository whose paths pass Windows' 260 characters (R6: importing `rs-k` stopped there on a
PC whose workspace path is long, with `LongPathsEnabled` off). All fictional."""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from test_knowledge_repos_api import _call, _ok

from knowledge import wiki_repos
from knowledge.evolution import knowledge_digest, raw_digest
from knowledge.vault import Vault

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="a Windows limit")

LONG = "Fictional instrument now supports over-the-air signaling alongside cellular " * 2
NAME = LONG.strip()[:140] + ".md"
LIMIT = 260


def _source(root: Path) -> Path:
    source = root / "src"
    (source / "wiki" / "sources").mkdir(parents=True)
    (source / "raw" / "PR").mkdir(parents=True)
    (source / "index.md").write_text("# Index\n", encoding="utf-8")
    (source / "log.md").write_text("# Log\n", encoding="utf-8")
    (source / "wiki" / "sources" / NAME).write_text(
        "---\ntitle: long\n---\n\n## Facts\n\nThe K42X option exists.\n", encoding="utf-8"
    )
    (source / "raw" / "PR" / NAME).write_text("the original", encoding="utf-8")
    return source


def test_a_long_path_imports_publishes_and_reads(tmp_path: Path) -> None:
    # As long as the PC's where this was seen: `...\preview-0.1.0\workspace`.
    workspace = tmp_path / ("w" * max(1, 90 - len(str(tmp_path))))
    workspace.mkdir()
    shared = tmp_path / "s"
    shared.mkdir()
    # The subject is a long destination workspace. Keep input-fixture creation
    # within Win32's normal path limit even when pytest's own base is deep.
    # Removing it after import also proves subsequent reads use the copied Raw.
    with TemporaryDirectory(prefix="aep-wiki-src-") as raw_fixture:
        given = {
            "source": str(_source(Path(raw_fixture))),
            "path": str(shared),
            "id": "long-wiki",
            "author": "x",
        }
        done = wiki_repos.import_copy(workspace, given, "x")
    assert done["imported"]["raw"] == 1 and done["imported"]["pages"] >= 1
    folder = workspace / "knowledge-repos" / "long-wiki" / "work" / "files" / "sources"
    assert len(str(folder)) + len(NAME) + 9 > LIMIT  # what this test is about

    _ok(_call(workspace, "POST", "/long-wiki/tag", {"name": "v1", "purpose": "first"}))
    _ok(_call(workspace, "POST", "/long-wiki/publish", {"tag": "v1", "confirm": True}))
    view, _version = wiki_repos.agent_source(workspace, "long-wiki")
    page = next(p for p in view.rglob("*.md") if p.name == NAME and p.parent.name == "sources")
    assert "K42X" in page.read_text(encoding="utf-8")
    assert [p for p in view.rglob("*") if p.is_file() and p.parent.name == "PR"]
    # What the Agent's catalog does with this folder.
    vault = Vault(view)
    assert knowledge_digest(vault) and raw_digest(vault)
    assert any("K42X" in page.read_text(encoding="utf-8") for page in vault.root.rglob("*.md"))

    # A second version swaps the view: the old one, long paths and all, goes.
    _ok(_call(workspace, "POST", "/long-wiki/tag", {"name": "v2", "purpose": "second"}))
    _ok(_call(workspace, "POST", "/long-wiki/publish", {"tag": "v2", "confirm": True}))
    again, _version = wiki_repos.agent_source(workspace, "long-wiki")
    assert [p for p in again.rglob("*.md") if p.name == NAME]
