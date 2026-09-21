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
    NO_DECISIONS,
    Decision,
    append_decision,
    clear_conflict,
    decision_block,
    decisions_text,
    open_conflicts,
    resolve,
)
from knowledge.lint import ManualEdits, OpenConflict, manual_edits, page_hashes, record_state, scan
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


def test_open_conflicts_are_found_by_reading_and_cleared_with_a_reason(
    tmp_path: Path,
) -> None:
    vault = make_vault(tmp_path)
    page(
        vault,
        "wiki/entities/Foo.md",
        "---\ntitle: Foo\n---\n\n- ⚠️ first claim\ntext\n  ⚠️ second\n",
    )
    page(vault, "wiki/entities/Bar.md", "---\ntitle: Bar\n---\n* ⚠️ third\n")
    found = open_conflicts(vault)
    assert found == (
        OpenConflict(page="wiki/entities/Bar.md", line=4, text="third"),
        OpenConflict(page="wiki/entities/Foo.md", line=5, text="first claim"),
        OpenConflict(page="wiki/entities/Foo.md", line=7, text="second"),
    )
    assert scan(vault).open_conflicts == found
    # Clearing removes exactly the marker line, collapses the blank it leaves, backs up.
    assert clear_conflict(vault, "wiki/entities/Foo.md", 5, stamp="c1") is True
    assert vault.read("wiki/entities/Foo.md") == "---\ntitle: Foo\n---\n\ntext\n  ⚠️ second\n"
    assert (tmp_path / ".ingest-backup" / "c1" / "wiki" / "entities" / "Foo.md").exists()
    # A moved or non-marker line is refused; nothing else is ever removed.
    assert clear_conflict(vault, "wiki/entities/Foo.md", 5, stamp="c2") is False
    assert clear_conflict(vault, "wiki/entities/Foo.md", 99, stamp="c2") is False
    assert not (tmp_path / ".ingest-backup" / "c2").exists()

    outcome = resolve(
        vault,
        Decision(topic="second vs third", keep="second", reject="third", reason="newer source"),
        clear=(
            ("wiki/entities/Foo.md", 6),
            ("wiki/entities/Bar.md", 4),
            ("wiki/entities/Bar.md", 9),
        ),
        today=TODAY,
        stamp="r1",
    )
    assert [c.text for c in outcome.cleared] == ["third", "second"]
    assert outcome.missed == (("wiki/entities/Bar.md", 9),)
    assert "## [2026-09-21] second vs third" in vault.read("decisions.md")
    assert open_conflicts(vault) == ()
    assert vault.read("wiki/entities/Bar.md") == "---\ntitle: Bar\n---\n"


def test_manual_edits_exclude_what_the_tool_wrote(tmp_path: Path) -> None:
    vault = make_vault(tmp_path)
    page(vault, "wiki/entities/Foo.md", "v1")
    assert manual_edits(vault) == ManualEdits(first_run=True)
    assert scan(vault).manual_edits == ManualEdits(first_run=True)
    record_state(vault, written=("wiki/entities/Foo.md",), today=TODAY)
    state = vault.state_read()
    assert state["tool_written"] == ["wiki/entities/Foo.md"] and "index.md" in state["hashes"]
    assert page_hashes(vault)["wiki/entities/Foo.md"] == state["hashes"]["wiki/entities/Foo.md"]

    page(vault, "wiki/entities/Foo.md", "v2")
    page(vault, "wiki/entities/Bar.md", "new")
    report = manual_edits(vault)
    # Foo changed but was tool-written last run, so it is not a human edit.
    assert report == ManualEdits(
        since="2026-09-21", added=("wiki/entities/Bar.md",), tool_written=1
    )
    record_state(vault, today=date(2026, 9, 22))
    page(vault, "wiki/entities/Foo.md", "v3")
    (tmp_path / "wiki" / "entities" / "Bar.md").unlink()
    page(vault, "index.md", "# Index\nchanged\n")
    report = manual_edits(vault)
    assert report.since == "2026-09-22"
    assert report.edited == ("wiki/entities/Foo.md", "index.md")
    assert report.removed == ("wiki/entities/Bar.md",) and report.added == ()
    assert scan(vault).manual_edits == report
    # A corrupt state file is a first run, not a failure; the state lives in its own file.
    (tmp_path / ".ingest-state.json").write_text("{not json", encoding="utf-8")
    assert manual_edits(vault).first_run is True
    assert vault.state_read() == {}
