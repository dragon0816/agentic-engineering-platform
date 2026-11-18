"""Wiki repositories on this PC (knowledge repositories R4a, `docs/phases/KNOWLEDGE_REPO.md`).

Two PCs are two workspaces; each has its own copy of the shared folder and
`_deliver` plays OneDrive, as in `tests/test_bi_vault.py`. Pages are edited with
`wiki.stage_page` (the ingest path is wired separately). All data is fictional.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from aep_wiki.host.knowledge_repos_api import route
from knowledge import wiki_repos
from knowledge.repo import wiki
from knowledge.vault import Vault

PAGE = "wiki/entities/tester-x.md"
TEXT = """---
title: Tester X
---
# Tester X

Intro.

## Options

- K1 base [[tester-x-sheet]]

## Notes

Nothing yet.
"""
SOURCE = """---
title: Tester X sheet
---
# Tester X sheet

Raw: raw/Products/tester-x.md
"""


def _call(ws: Path, method: str, path: str, body: Any = None, **q: str) -> tuple[int, Any]:
    return route(ws, "tester", method, "/api/knowledge/repos" + path, q, body)


def _ok(answer: tuple[int, Any]) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _refused(answer: tuple[int, Any], status: int, code: str) -> dict[str, Any]:
    assert (answer[0], answer[1].get("code")) == (status, code), answer
    return dict(answer[1])


def _write(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _wiki_folder(root: Path) -> Path:
    """A fictional wiki vault as people keep it today."""
    folder = root / "tester-wiki"
    (folder / "wiki" / "entities").mkdir(parents=True)
    (folder / "wiki" / "sources").mkdir(parents=True)
    (folder / "raw" / "Products").mkdir(parents=True)
    (folder / "drop" / "Products").mkdir(parents=True)
    (folder / "skills" / "ingest-products").mkdir(parents=True)
    _write(folder / "index.md", "# Index\n\n- [[tester-x]]\n")
    _write(folder / "log.md", "# Log\n\n## [2026-10-01] ingest | sheet\n")
    _write(folder / "CLAUDE.md", "# Schema\n\nEntities and sources.\n")
    _write(folder / PAGE, TEXT)
    _write(folder / "wiki" / "sources" / "tester-x-sheet.md", SOURCE)
    _write(folder / "raw" / "Products" / "tester-x.md", "# Sheet\n\nK1.\n")
    (folder / "drop" / "Products" / "tester-x.pdf").write_bytes(b"%PDF fictional")
    _write(
        folder / "skills" / "ingest-products" / "SKILL.md",
        "---\nname: ingest-products\n---\nRead product sheets.\n",
    )
    return folder


def _digest(folder: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        digest.update(path.relative_to(folder).as_posix().encode() + path.read_bytes())
    return digest.hexdigest()


def _two_pcs(tmp_path: Path) -> tuple[Path, Path, str, Path, Path]:
    """PC a imports a copy of a wiki folder; PC b joins the shared folder."""
    a, b = tmp_path / "a" / "ws", tmp_path / "b" / "ws"
    drive_a, drive_b = tmp_path / "a" / "drive", tmp_path / "b" / "drive"
    for folder in (a, b, drive_a, drive_b):
        folder.mkdir(parents=True)
    source = _wiki_folder(tmp_path)
    made = _ok(
        _call(a, "POST", "/import", {"source": str(source), "path": str(drive_a),
                                     "title": "Tester wiki", "author": "alice"})
    )  # fmt: skip
    repo_id = made["repo"]["id"]
    shutil.copytree(drive_a / repo_id, drive_b / repo_id)
    _ok(_call(b, "POST", "/join", {"path": str(drive_b / repo_id), "author": "bob"}))
    return drive_a, drive_b, repo_id, a, b


def _deliver(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_file() and relative.name != "REPO.md" and not (target / relative).exists():
            (target / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target / relative)


def _edit(ws: Path, repo_id: str, old: str, new: str, purpose: str | None = None) -> None:
    repo = wiki_repos.repository(ws, repo_id)
    text = wiki.pages(repo.working_units())[PAGE]
    assert old in text
    wiki.stage_page(repo, PAGE, text.replace(old, new))
    if purpose:
        _ok(_call(ws, "POST", f"/{repo_id}/commit", {"purpose": purpose}))


def _push(ws: Path, repo_id: str) -> dict[str, Any]:
    pushed = _ok(_call(ws, "POST", f"/{repo_id}/push", {}))
    assert pushed["status"] == "pushed", pushed
    return pushed


def _read(ws: Path, repo_id: str) -> str:
    return (wiki_repos.reading_folder(ws, repo_id) / PAGE).read_text(encoding="utf-8")


def test_an_imported_copy_is_served_as_a_wiki_the_agent_can_read(tmp_path: Path) -> None:
    source = _wiki_folder(tmp_path / "src")
    before = _digest(source)
    ws, drive = tmp_path / "ws", tmp_path / "drive"
    ws.mkdir()
    drive.mkdir()
    made = _ok(_call(ws, "POST", "/import", {"source": str(source), "path": str(drive)}))
    assert made["imported"]["pages"] == 4 and made["imported"]["raw"] == 1
    assert made["push"] == "pushed"
    assert _digest(source) == before  # the folder given is only read
    view = wiki_repos.reading_folder(ws, made["repo"]["id"])
    for name in (PAGE, "index.md", "log.md", "raw/Products/tester-x.md", "CLAUDE.md"):
        assert (view / name).read_bytes() == (source / name).read_bytes(), name
    assert (view / "skills" / "ingest-products" / "SKILL.md").read_bytes() == (
        source / "skills" / "ingest-products" / "SKILL.md"
    ).read_bytes()
    Vault(view)  # the query engine accepts it
    listed = _ok(_call(ws, "GET", ""))["repos"]
    assert [r["title"] for r in listed] == ["tester-wiki"]
    # A new repository inside the folder being imported is refused.
    _refused(
        _call(ws, "POST", "/import", {"source": str(source), "path": str(source / "wiki")}),
        400,
        "path_invalid",
    )


def test_a_new_repository_starts_with_a_schema_index_and_log(tmp_path: Path) -> None:
    ws, drive = tmp_path / "ws", tmp_path / "drive"
    ws.mkdir()
    drive.mkdir()
    made = _ok(_call(ws, "POST", "", {"path": str(drive), "title": "Fresh wiki"}))
    repo_id = made["repo"]["id"]
    status = _ok(_call(ws, "GET", f"/{repo_id}/status"))
    assert status["schema"] == wiki.SCHEMA_REF and status["reads"]["tag"] is None
    view = wiki_repos.reading_folder(ws, repo_id)
    assert (view / "index.md").read_text(encoding="utf-8").startswith("# Fresh wiki")
    assert "Wiki schema" in (view / "CLAUDE.md").read_text(encoding="utf-8")
    Vault(view)
    assert "Fresh wiki" in (drive / repo_id / "REPO.md").read_text(encoding="utf-8")


def test_the_agent_reads_the_published_tag_while_the_head_moves_on(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    assert "K1 base" in _read(a, repo_id)  # never published: the pushed head
    _edit(a, repo_id, "[[tester-x-sheet]]\n", "[[tester-x-sheet]]\n- K2 option\n", "加 K2")
    assert "K2 option" not in _read(a, repo_id)  # committed here, not pushed
    _push(a, repo_id)
    assert "K2 option" in _read(a, repo_id)
    _ok(_call(a, "POST", f"/{repo_id}/tag", {"name": "v1", "purpose": "第一版"}))
    _refused(_call(a, "POST", f"/{repo_id}/publish", {"tag": "v1"}), 400, "confirm_required")
    _ok(_call(a, "POST", f"/{repo_id}/publish", {"tag": "v1", "confirm": True}))
    _edit(a, repo_id, "Nothing yet.", "Shipping in Q3.", "出貨時程")
    _push(a, repo_id)
    assert "Shipping in Q3." not in _read(a, repo_id)  # the published v1
    status = _ok(_call(a, "GET", f"/{repo_id}/status"))
    assert status["reads"]["tag"] == "v1"
    # PC b reads the same published version once the files arrive.
    _deliver(drive_a / repo_id, drive_b / repo_id)
    text = _read(b, repo_id)
    assert "K2 option" in text and "Shipping in Q3." not in text


def test_two_maintainers_merge_sections_and_see_a_conflict_in_words(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    _edit(a, repo_id, "[[tester-x-sheet]]\n", "[[tester-x-sheet]]\n- K2 option\n", "a 加選項")
    _edit(b, repo_id, "Intro.", "Intro, revised.", "b 改開頭")
    _push(a, repo_id)
    _deliver(drive_a / repo_id, drive_b / repo_id)
    _push(b, repo_id)
    _deliver(drive_b / repo_id, drive_a / repo_id)
    _ok(_call(a, "POST", f"/{repo_id}/sync", {}))
    for ws in (a, b):
        text = wiki.pages(wiki_repos.repository(ws, repo_id).units())[PAGE]
        assert "K2 option" in text and "Intro, revised." in text
    # The same section on both PCs: the second push names it.
    _edit(a, repo_id, "Nothing yet.", "From a.", "a 的備註")
    _edit(b, repo_id, "Nothing yet.", "From b.", "b 的備註")
    _push(a, repo_id)
    _deliver(drive_a / repo_id, drive_b / repo_id)
    pushed = _ok(_call(b, "POST", f"/{repo_id}/push", {}))
    assert pushed["status"] == "conflicts"
    assert [c["label"] for c in pushed["conflicts"]] == [f"{PAGE} 的「Notes」"]
    pending = _ok(_call(b, "GET", f"/{repo_id}/pending"))
    assert pending["commits"]  # nothing was written to the shared folder
    history = _ok(_call(a, "GET", f"/{repo_id}/history"))
    diff = _ok(_call(a, "GET", f"/{repo_id}/diff", commit=history["commits"][0]["id"]))
    assert [c["label"] for c in diff["changes"]] == [f"{PAGE} 的「Notes」"]


def test_a_push_that_loses_a_sourced_line_is_blocked(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    _edit(a, repo_id, "- K1 base [[tester-x-sheet]]", "- K1 base", "拿掉來源")
    pushed = _ok(_call(a, "POST", f"/{repo_id}/push", {}))
    assert pushed["status"] == "blocked" and "K1 base [[tester-x-sheet]]" in pushed["blocking"][0]
    assert "[[tester-x-sheet]]" in _read(a, repo_id)


def test_refusals(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    _refused(_call(ws, "GET", "/nope/status"), 404, "repo_unknown")
    _refused(_call(ws, "POST", "", {"path": "relative", "title": "x"}), 400, "path_missing")
    _refused(_call(ws, "POST", "/import", {"source": str(tmp_path), "path": str(ws)}), 400,
             "source_not_wiki")  # fmt: skip
    _refused(_call(ws, "GET", "/a/b/c"), 404, "route_unknown")
    _refused(_call(ws, "POST", "", ["not", "an", "object"]), 400, "body_invalid")
