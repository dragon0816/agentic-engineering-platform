"""The working folder of a wiki repository (knowledge repositories R4a).

The ingest pipeline writes into a folder built from the working copy;
`capture` stages pages, new Raw files, new originals, skills and the schema
back as units, committed and pushed like any change. Two PCs as in
`tests/test_knowledge_repos_api.py`. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path

from test_knowledge_repos_api import PAGE, _call, _deliver, _ok, _push, _two_pcs

from knowledge import wiki_repos, wiki_work
from knowledge.repo import skills, wiki
from knowledge.vault import Vault


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def test_the_working_folder_is_a_wiki_built_from_the_working_copy(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    repo = wiki_repos.repository(a, repo_id)
    folder = wiki_work.open_work(repo)
    Vault(folder)
    assert (folder / "drop").is_dir()
    assert (folder / PAGE).read_text(encoding="utf-8") == wiki.pages(repo.units())[PAGE]
    assert (folder / "raw" / "Products" / "tester-x.md").is_file()
    assert wiki_work.open_work(repo) == folder  # unchanged units: not rebuilt
    assert wiki_work.capture(repo)["pages"] == []


def test_captured_changes_are_committed_and_reach_the_other_pc(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    repo = wiki_repos.repository(a, repo_id)
    folder = wiki_work.open_work(repo)
    text = (folder / PAGE).read_text(encoding="utf-8")
    _write(folder / PAGE, text.replace("Nothing yet.", "Shipping in Q3."))
    _write(folder / "wiki" / "entities" / "tester-y.md", "# Tester Y\n\nNew page.\n")
    _write(folder / "raw" / "Products" / "tester-y.md", "# Y sheet\n")
    (folder / "drop" / "Products").mkdir(parents=True)
    (folder / "drop" / "Products" / "tester-y.pdf").write_bytes(b"%PDF y")
    _write(folder / ".ingest-state.json", "{}")  # pipeline bookkeeping stays local
    summary = wiki_work.capture(repo)
    assert summary["pages"] == [PAGE, "wiki/entities/tester-y.md"]
    assert summary["raw"] == ["raw/Products/tester-y.md"]
    assert [o.split("/")[-1][9:] for o in summary["originals"]] == ["tester-y.pdf"]
    labels = {c["label"] for c in _ok(_call(a, "GET", f"/{repo_id}/pending"))["uncommitted"]}
    assert f"{PAGE} 的「Notes」" in labels and "raw/Products/tester-y.md" in labels
    _ok(_call(a, "POST", f"/{repo_id}/commit", {"purpose": "加入 Tester Y"}))
    _push(a, repo_id)
    _deliver(drive_a / repo_id, drive_b / repo_id)
    view = wiki_repos.reading_folder(b, repo_id)
    assert "Shipping in Q3." in (view / PAGE).read_text(encoding="utf-8")
    assert (view / "raw" / "Products" / "tester-y.md").read_text(encoding="utf-8") == "# Y sheet\n"
    assert not (view / ".ingest-state.json").exists()


def test_raw_is_never_rewritten(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    repo = wiki_repos.repository(a, repo_id)
    folder = wiki_work.open_work(repo)
    _write(folder / "raw" / "Products" / "tester-x.md", "# Rewritten\n")
    summary = wiki_work.capture(repo)
    assert summary["raw_changed"] == ["raw/Products/tester-x.md"] and summary["raw"] == []
    assert _ok(_call(a, "GET", f"/{repo_id}/status"))["uncommitted"] == 0


def test_rules_become_skill_revisions_and_a_schema_version(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    repo = wiki_repos.repository(a, repo_id)
    folder = wiki_work.open_work(repo)
    skill_file = folder / "skills" / "ingest-products" / "SKILL.md"
    _write(skill_file, "---\nname: ingest-products\n---\nRead product sheets and options.\n")
    summary = wiki_work.capture(repo)
    assert summary["skills"] == ["ingest-products"] and summary["schema"] is None
    (item,) = skills.current_skills(repo)
    assert item["revision"] == 2 and not item["needs_update"]
    # A schema edit is a new version; the skill written for the old one waits.
    _write(folder / "CLAUDE.md", "# Schema\n\nEntities, sources and options.\n")
    assert wiki_work.capture(repo)["schema"] == "wiki.schema@1.0.1"
    (item,) = skills.current_skills(repo)
    assert item["needs_update"]
    # The rebuilt folder serves the new schema from the staged file.
    wiki_work.work_folder(repo).joinpath("../state.json").resolve().unlink()
    rebuilt = wiki_work.open_work(repo)
    assert "options" in (rebuilt / "CLAUDE.md").read_text(encoding="utf-8")


def test_the_folder_follows_a_discard(tmp_path: Path) -> None:
    drive_a, drive_b, repo_id, a, b = _two_pcs(tmp_path)
    repo = wiki_repos.repository(a, repo_id)
    folder = wiki_work.open_work(repo)
    _write(folder / PAGE, (folder / PAGE).read_text(encoding="utf-8") + "\nDraft.\n")
    wiki_work.capture(repo)
    _ok(_call(a, "POST", f"/{repo_id}/discard", {}))
    assert "Draft." not in (wiki_work.open_work(repo) / PAGE).read_text(encoding="utf-8")
