"""One unit name, one level, per company (acceptance walk 2026-11-06).

The same printed 光學事業處 was read as the 事業群 on one card and as the 處
on a colleague's card, and the org chart nested it twice (光學事業處 >
光學事業處 > 研發部). A name the company uses at two levels is placed at one:
by its name (…事業群 is a business group, …處 a division), otherwise where
most of the company's people have it. Every card for the company re-places
the people already stored, recorded in history and undone with the card.
Also: the chart's file name carries the local (Asia/Taipei) time the page
shows. Synthetic people only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_business_cards_capabilities import _bridge, _run

from capabilities.business_cards import chart, handlers

COMPANY = "晨曦光電股份有限公司"


def _units(bridge: Any) -> dict[str, tuple[str, str, str]]:
    listed = _run(bridge, "list", {"company": COMPANY}).data
    assert listed is not None
    return {
        p["name"]: (p["business_group"], p["division"], p["department"]) for p in listed["people"]
    }


def _card(bridge: Any, **fields: str) -> Any:
    result = _run(bridge, "add-card", {"company": COMPANY, **fields})
    assert result.status == "succeeded", result.failure
    return result.data


def test_a_division_read_as_the_business_group_moves_to_the_division(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _card(bridge, name="林雅婷", business_group="光學事業處", department="研發部")
    _card(bridge, name="陳志遠", division="光學事業處", department="研發部")
    assert _units(bridge) == {
        "林雅婷": ("", "光學事業處", "研發部"),
        "陳志遠": ("", "光學事業處", "研發部"),
    }


def test_an_updated_card_with_both_levels_keeps_the_name_once(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _card(
        bridge,
        name="林雅婷",
        business_group="光學事業處",
        department="研發部",
        email="yt.lin@dawn.example",
    )
    _card(bridge, name="陳志遠", division="光學事業處", department="研發部")
    updated = _card(
        bridge,
        name="林雅婷",
        business_group="光學事業處",
        division="光學事業處",
        department="研發部",
        title="協理",
        email="yt.lin@dawn.example",
    )
    assert updated["outcome"] == "updated"
    assert _units(bridge)["林雅婷"] == ("", "光學事業處", "研發部")


def test_a_business_group_stays_one_and_a_misread_division_moves_up(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _card(bridge, name="王小明", business_group="網通事業群", division="研發處")
    _card(bridge, name="李大華", division="網通事業群", department="射頻部")
    assert _units(bridge)["李大華"] == ("網通事業群", "", "射頻部")


def test_a_name_without_a_level_word_goes_where_most_people_have_it(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _card(bridge, name="甲", business_group="Optics BU")
    _card(bridge, name="乙", business_group="Optics BU")
    _card(bridge, name="丙", division="Optics BU", department="Lens")
    assert _units(bridge)["丙"] == ("Optics BU", "", "Lens")


def test_a_taken_level_is_not_overwritten(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _card(bridge, name="林雅婷", business_group="光學事業處", division="研展處 I")
    _card(bridge, name="陳志遠", division="光學事業處")
    # 林雅婷's division holds another name: her 光學事業處 cannot move there.
    assert _units(bridge)["林雅婷"] == ("光學事業處", "研展處 I", "")


def test_a_stored_colleague_is_re_placed_and_undo_puts_it_back(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _card(bridge, name="林雅婷", business_group="光學事業處", department="研發部")
    # Alone, the name is at one level: nothing to place.
    assert _units(bridge)["林雅婷"] == ("光學事業處", "", "研發部")
    second = _card(bridge, name="陳志遠", division="光學事業處", department="研發部")
    assert _units(bridge)["林雅婷"] == ("", "光學事業處", "研發部")
    history = _run(bridge, "history", {"person": {"name": "林雅婷"}}).data
    assert history is not None
    moved = [item for item in history["history"] if item["change_id"] == second["change_id"]]
    assert {item["field"] for item in moved} == {"business_group", "division"}
    undone = _run(bridge, "undo", {"change_id": second["change_id"]})
    assert undone.status == "succeeded", undone.failure
    after = _units(bridge)
    assert "陳志遠" not in after
    assert after["林雅婷"] == ("光學事業處", "", "研發部")


def test_a_value_the_person_set_is_not_moved(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    _card(bridge, name="林雅婷", division="光學事業處")
    edited = _run(
        bridge,
        "edit-person",
        {"person": {"name": "林雅婷"}, "fields": {"business_group": "光學事業處"}, "reason": "t"},
    )
    assert edited.status == "succeeded", edited.failure
    _card(bridge, name="陳志遠", division="光學事業處")
    assert _units(bridge)["林雅婷"][0] == "光學事業處"


def test_the_chart_never_nests_a_unit_in_itself() -> None:
    people = [
        {
            "person_id": "a",
            "business_group": "光學事業處",
            "division": "光學事業處",
            "department": "研發部",
        },
        {"person_id": "b", "business_group": "", "division": "光學事業處", "department": "設計部"},
    ]
    paths = chart._paths(people)  # type: ignore[arg-type]
    assert paths == {"a": ["光學事業處", "研發部"], "b": ["光學事業處", "設計部"]}


def test_the_chart_file_name_uses_the_local_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Fixed(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> _Fixed:
            moment = cls(2026, 11, 5, 20, 16, 19, tzinfo=UTC)
            return moment if tz is None else moment.astimezone(tz)

    bridge = _bridge(tmp_path)
    _card(bridge, name="林雅婷", division="光學事業處")
    monkeypatch.setattr(handlers, "datetime", _Fixed)
    drawn = _run(bridge, "org-chart", {"company": COMPANY, "format": "html"})
    assert drawn.status == "succeeded", drawn.failure
    assert Path(drawn.data["html_path"]).name.endswith("-20261106-041619.html")
