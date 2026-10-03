"""Workflow 10 source snapshot parity without a workbook or baseline write."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from capabilities.chipset_report.rules import SourceRow
from capabilities.chipset_report.source_snapshot import (
    build,
    commit_candidate,
    diff,
    load_latest,
    prepare_diff,
    render_report,
    row_key,
)


def row(**changes: object) -> SourceRow:
    values: dict[str, object] = {
        "fiscal_year": "FY2526",
        "sheet": "Project List_Sales update",
        "row_number": 2,
        "brand": "BMW",
        "mfg": "Quanta",
        "project_name": "V28",
        "chipset_models": "QCA6688",
        "end_products": "IVI",
        "purpose": "R&D",
        "units": 6,
        "schedule": "Aug,2026",
        "opp_id": "1085846",
        "priority": "H",
        "status": "On-going",
    }
    values.update(changes)
    return SourceRow(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("placeholder", ["", "N/A", "n/a", "TBD", "TBC", "-", "  "])
def test_key_prefers_real_opp_id_and_uses_triple_for_placeholder(placeholder: str) -> None:
    assert row_key(row(opp_id="553641")) == "opp:553641"
    assert row_key(row(opp_id=placeholder, brand="RVT", mfg="Quanta", project_name="V3TA")) == (
        "row:rvt|quanta|v3ta"
    )


def test_row_move_and_formatting_change_do_not_make_false_diffs() -> None:
    before = build([row(opp_id="1", row_number=2, chipset_models="QCA6688")])
    after = build([row(opp_id="1", row_number=12, chipset_models="  qca6688 ")])
    result = diff(before, after, "t0")
    assert result.changed == []
    assert result.added == []
    assert result.removed == []


def test_critical_and_noncritical_changes_keep_source_order_and_raw_values() -> None:
    before = build([row(chipset_models="QCA6688", priority="H")])
    after = build([row(chipset_models="QCA6698", priority="M")])
    result = diff(before, after, "t0")
    assert [(change.field, change.critical) for change in result.changed] == [
        ("chipset_models", True),
        ("priority", False),
    ]
    assert (result.changed[0].before, result.changed[0].after) == ("QCA6688", "QCA6698")
    assert result.as_dict()["criticalChangeCount"] == 1
    assert "1 CRITICAL" in result.summary()
    report = render_report([("FY2526.xlsx", result)])
    assert report.index("CHIPSET-AFFECTING CHANGES") < report.index("other field changes")


def test_added_removed_and_duplicate_keys_match_source_behavior() -> None:
    before = build([row(opp_id="1"), row(opp_id="2", chipset_models="MTK7925")])
    after = build([row(opp_id="1"), row(opp_id="3", chipset_models="IPQ5424")])
    result = diff(before, after, "t0")
    assert [item["key"] for item in result.added] == ["opp:3"]
    assert [item["key"] for item in result.removed] == ["opp:2"]
    assert result.removed[0]["chipsets"] == "MTK7925"
    duplicate = build([row(opp_id="7", project_name="A"), row(opp_id="7", project_name="B")])
    assert duplicate["opp:7"]["_duplicate"] == 2
    assert duplicate["opp:7"]["project_name"] == "A"


def test_first_preview_is_read_only_and_does_not_consume_its_candidate(tmp_path: Path) -> None:
    state = tmp_path / "state"
    book = "CMP180 project list_ FY2526_RSTW.xlsx"
    first, candidate = prepare_diff(state, book, [row()])
    assert first.is_first_run
    assert not (first.added or first.removed or first.changed)
    assert "baseline pending successful apply" in first.summary()
    assert candidate["opp:1085846"]["_rowNumber"] == 2
    assert not state.exists()
    second, repeated = prepare_diff(state, book, [row(chipset_models="QCA6698")])
    assert second.is_first_run and repeated["opp:1085846"]["chipset_models"] == "QCA6698"
    assert not state.exists()


def test_existing_baseline_is_read_without_advancing_on_preview(tmp_path: Path) -> None:
    state = tmp_path / "state"
    book = "CMP180 project list_ FY2526_RSTW.xlsx"
    snapshots = state / "w1-snapshots" / "CMP180_project_list__FY2526_RSTW"
    snapshots.mkdir(parents=True)
    original = build([row(chipset_models="QCA6688")])
    baseline = snapshots / "20260729_100000.json"
    baseline.write_text(
        json.dumps({"takenAt": "2026-07-29T10:00:00", "rows": original}), encoding="utf-8"
    )
    assert load_latest(state, book) == (original, "2026-07-29T10:00:00")
    first, candidate = prepare_diff(state, book, [row(chipset_models="QCA6698")])
    second, _ = prepare_diff(state, book, [row(chipset_models="QCA6698")])
    assert first.as_dict() == second.as_dict()
    assert first.changed[0].field == "chipset_models"
    assert candidate["opp:1085846"]["chipset_models"] == "QCA6698"
    assert sorted(snapshots.glob("*.json")) == [baseline]
    assert json.loads(baseline.read_text(encoding="utf-8"))["rows"] == original


def test_corrupt_baseline_retains_source_first_run_behavior(tmp_path: Path) -> None:
    state = tmp_path / "state"
    book = "x.xlsx"
    snapshots = state / "w1-snapshots" / "x"
    snapshots.mkdir(parents=True)
    (snapshots / "20260729_120000.json").write_text("{not json", encoding="utf-8")
    assert load_latest(state, book) == (None, None)
    result, _ = prepare_diff(state, book, [row()])
    assert result.is_first_run


def test_candidate_commits_only_after_verified_copyback(tmp_path: Path) -> None:
    state = tmp_path / "state"
    book = "CMP180 project list_ FY2526_RSTW.xlsx"
    now = datetime(2026, 10, 3, 9, tzinfo=UTC)
    _, candidate = prepare_diff(state, book, [row(chipset_models="QCA6688")])
    with pytest.raises(ValueError, match="verified target copyback"):
        commit_candidate(
            state, book, candidate, taken_at=now, verified_copyback=False
        )
    assert not state.exists()
    first = commit_candidate(state, book, candidate, taken_at=now, verified_copyback=True)
    assert first.is_file()
    assert load_latest(state, book) == (candidate, "2026-10-03T09:00:00+00:00")
    changed, next_candidate = prepare_diff(state, book, [row(chipset_models="QCA6698")])
    assert changed.changed[0].field == "chipset_models"
    assert changed.changed[0].before == "QCA6688"
    assert sorted(first.parent.glob("*.json")) == [first]
    with pytest.raises(ValueError, match="verified target copyback"):
        commit_candidate(
            state,
            book,
            next_candidate,
            taken_at=now + timedelta(seconds=1),
            verified_copyback=False,
        )
    repeated, _ = prepare_diff(state, book, [row(chipset_models="QCA6698")])
    assert repeated.as_dict() == changed.as_dict()
    assert sorted(first.parent.glob("*.json")) == [first]


def test_commit_is_atomic_and_retains_recent_baselines(tmp_path: Path) -> None:
    state = tmp_path / "state"
    book = "x.xlsx"
    now = datetime(2026, 10, 3, 9, tzinfo=UTC)
    first = commit_candidate(
        state, book, build([row(chipset_models="A")]),
        taken_at=now, verified_copyback=True, keep=2,
    )
    second = commit_candidate(
        state, book, build([row(chipset_models="B")]),
        taken_at=now + timedelta(microseconds=1), verified_copyback=True, keep=2,
    )
    third = commit_candidate(
        state, book, build([row(chipset_models="C")]),
        taken_at=now + timedelta(seconds=1), verified_copyback=True, keep=2,
    )
    assert first != second != third
    kept = set(third.parent.glob("*.json"))
    assert len(kept) == 2 and third in kept
    assert len(kept & {first, second}) == 1
    assert list(third.parent.glob("*.tmp")) == []
    loaded, _ = load_latest(state, book)
    assert loaded is not None and loaded["opp:1085846"]["chipset_models"] == "C"
