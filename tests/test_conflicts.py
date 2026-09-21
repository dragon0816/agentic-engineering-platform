"""Conflicts and decisions: an append-only record injected into planning,
markers found by reading and cleared only with a reason on record, and
manual edits detected by hash and computed into the lint report."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_raw import make_vault

from knowledge.conflicts import (
    DECISIONS_HEADER,
    Decision,
    append_decision,
    clear_conflict,
    clear_conflicts,
    decision_block,
    decisions_text,
    open_conflicts,
    resolve,
)
from knowledge.lint import (
    ManualEdits,
    OpenConflict,
    manual_edits,
    note_written,
    page_hashes,
    record_state,
    scan,
)
from knowledge.planning import NO_DECISIONS
from knowledge.vault import Vault

TODAY = date(2026, 9, 21)


def page(vault: Vault, rel: str, text: str) -> None:
    path = vault.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def test_decisions_are_append_only_and_injected(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    assert decisions_text(vault) == NO_DECISIONS
    with pytest.raises(ValidationError, match="keeps, rejects or explains"):
        Decision(topic="empty")
    first = Decision(
        topic="What a Skill is",
        keep="skill-as-instruction",
        reject="skill == Python function",
        reason="the latter is one implementation's detail",
        pages=("Skills", "OpenHands"),
    )
    assert append_decision(vault, first, today=TODAY) == "decisions.md"
    text = vault.read("decisions.md")
    assert text.startswith(DECISIONS_HEADER)
    assert text.endswith(
        "\n## [2026-09-21] What a Skill is\n- keep: skill-as-instruction\n"
        "- reject: skill == Python function\n- reason: the latter is one implementation's detail\n"
        "- pages: [[Skills]], [[OpenHands]]\n"
    )
    assert decisions_text(vault) == text.strip()
    append_decision(vault, Decision(topic="Second", reason="why"), today=date(2026, 9, 22))
    assert vault.read("decisions.md").count("\n## [20") == 2  # the header's example is not one
    assert vault.read("decisions.md").count(DECISIONS_HEADER.splitlines()[0]) == 1
    assert b"\r" not in (tmp_path / "decisions.md").read_bytes()
    assert (
        decision_block(Decision(topic=" T ", keep=" k "), TODAY) == "## [2026-09-21] T\n- keep: k\n"
    )
    # The header alone still means no decisions.
    (tmp_path / "empty").mkdir()
    empty = make_vault(tmp_path / "empty")
    page(empty, "decisions.md", DECISIONS_HEADER)
    assert decisions_text(empty) == NO_DECISIONS


def test_open_conflicts_are_found_by_reading_and_only_markers_are_cleared(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    page(
        vault,
        "wiki/entities/Foo.md",
        "---\ntitle: Foo\n---\n\n## ⚠️ 待裁決的衝突\n\n"
        "- ⚠️ first claim\ntext ⚠️ mentioned\n  ⚠️ second\n",
    )
    page(vault, "wiki/entities/Bar.md", "---\ntitle: Bar\n---\n* ⚠️ third\n")
    found = open_conflicts(vault)
    assert found == (
        OpenConflict(page="wiki/entities/Bar.md", line=4, text="third"),
        OpenConflict(page="wiki/entities/Foo.md", line=7, text="first claim"),
        OpenConflict(page="wiki/entities/Foo.md", line=9, text="second"),
    )
    assert scan(vault).open_conflicts == found
    # Only marker lines go: the heading and the prose that mention ⚠️ stay.
    assert clear_conflicts(vault, "wiki/entities/Foo.md", (5, 8, 7), stamp="c1") == (7,)
    assert vault.read("wiki/entities/Foo.md") == (
        "---\ntitle: Foo\n---\n\n## ⚠️ 待裁決的衝突\n\ntext ⚠️ mentioned\n  ⚠️ second\n"
    )
    assert (tmp_path / ".ingest-backup" / "c1" / "wiki" / "entities" / "Foo.md").exists()
    # A moved or non-marker line is refused; nothing is written.
    assert clear_conflict(vault, "wiki/entities/Foo.md", 7, stamp="c2") is False
    assert clear_conflict(vault, "wiki/entities/Foo.md", 99, stamp="c2") is False
    assert not (tmp_path / ".ingest-backup" / "c2").exists()


def test_several_markers_on_one_page_cost_one_write_and_one_backup(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    original = "---\ntitle: Foo\n---\n- ⚠️ one\n- ⚠️ two\n\n- ⚠️ three\nkeep\n"
    page(vault, "wiki/entities/Foo.md", original)
    outcome = resolve(
        vault,
        Decision(topic="all three", reason="settled"),
        clear=(
            ("wiki/entities/Foo.md", 4),
            ("./wiki/entities/Foo.md", 5),
            ("wiki/entities/Foo.md", 5),  # a duplicate clears once
            ("wiki/entities/Foo.md", 7),
            ("wiki/entities/Foo.md", 8),  # not a marker
            ("wiki/entities/Foo.md", 42),  # never there
        ),
        today=TODAY,
        stamp="r1",
    )
    assert [c.text for c in outcome.cleared] == ["one", "two", "three"]
    assert outcome.missed == (("wiki/entities/Foo.md", 8), ("wiki/entities/Foo.md", 42))
    # Only a *double* blank collapses, as in the source; a lone blank stays.
    assert vault.read("wiki/entities/Foo.md") == "---\ntitle: Foo\n---\n\nkeep\n"
    backup = tmp_path / ".ingest-backup" / "r1" / "wiki" / "entities" / "Foo.md"
    assert backup.read_text(encoding="utf-8") == original  # the original, not a half-cleared page
    assert "## [2026-09-21] all three" in vault.read("decisions.md")
    assert open_conflicts(vault) == ()
    # The clear list is checked before anything is written.
    with pytest.raises(ValueError, match="page and a line number"):
        resolve(vault, Decision(topic="x", reason="y"), clear=(("", 3),), today=TODAY, stamp="r2")
    assert vault.read("decisions.md").count("\n## [20") == 1


def test_clearing_keeps_a_pages_line_endings(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    path = tmp_path / "wiki" / "entities" / "Win.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"---\r\ntitle: Win\r\n---\r\n- \xe2\x9a\xa0\xef\xb8\x8f gone\r\nkeep\r\n")
    assert clear_conflict(vault, "wiki/entities/Win.md", 4, stamp="w") is True
    assert path.read_bytes() == b"---\r\ntitle: Win\r\n---\r\nkeep\r\n"


def test_manual_edits_are_what_a_person_changed_since_the_record(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    page(vault, "wiki/entities/Foo.md", "v1")
    assert manual_edits(vault) == ManualEdits(first_run=True)
    assert scan(vault).manual_edits == ManualEdits(first_run=True)
    record_state(vault, today=TODAY)
    state = vault.state_read()
    assert "index.md" in state["hashes"] and state["updated"] == "2026-09-21"
    assert page_hashes(vault)["wiki/entities/Foo.md"] == state["hashes"]["wiki/entities/Foo.md"]

    # The tool writes a page and notes it: not a human edit. Then a person edits it: reported.
    page(vault, "wiki/entities/Foo.md", "v2 by the tool")
    note_written(vault, ("wiki/entities/Foo.md",), today=date(2026, 9, 22))
    assert manual_edits(vault) == ManualEdits(since="2026-09-22")
    page(vault, "wiki/entities/Foo.md", "v3 by a person")
    page(vault, "wiki/entities/Bar.md", "new")
    report = manual_edits(vault)
    assert report == ManualEdits(
        since="2026-09-22", edited=("wiki/entities/Foo.md",), added=("wiki/entities/Bar.md",)
    )
    record_state(vault, today=date(2026, 9, 23))
    (tmp_path / "wiki" / "entities" / "Bar.md").unlink()
    page(vault, "index.md", "# Index\nchanged\n")
    report = manual_edits(vault)
    assert report.since == "2026-09-23"
    assert report.edited == ("index.md",) and report.removed == ("wiki/entities/Bar.md",)
    assert scan(vault).manual_edits == report
    # A corrupt or odd state file is a first run, never a failure.
    (tmp_path / ".ingest-state.json").write_text("{not json", encoding="utf-8")
    assert manual_edits(vault).first_run is True and vault.state_read() == {}
    (tmp_path / ".ingest-state.json").write_text(
        '{"hashes": {"": "abc", "x": 5}}', encoding="utf-8"
    )
    assert manual_edits(vault).first_run is True
    assert scan(vault).manual_edits.first_run is True
