"""The weekly report's rules, against the source's own cases.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 3a. Every fixture
here is copied from the pinned Host Bridge's `test_weekly_rules.py`, which
was itself written from the live GTM project and `SDE_Weekly_Report.xlsx`.
No network, no workbook.
"""

import datetime as _dt
from typing import Any

import pytest

from capabilities.weekly_report import rules

# ---------------------------------------------------------------------------
# Week naming
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("2026_29W", (2026, 29)),
        ("2025_1W", (2025, 1)),
        ("2025_52W", (2025, 52)),
        # The workbook really does contain a sheet named "2025_14" with no W.
        ("2025_14", (2025, 14)),
        ("  2026_9W  ", (2026, 9)),
    ],
)
def test_real_sheet_names_parse(name: str, expected: tuple[int, int]) -> None:
    assert rules.parse_week_name(name) == expected


@pytest.mark.parametrize(
    "name",
    ["Tasks Summary-12-23", "weekly report temp", "", "2026_W", "26_1W", "2026-29W", "Sheet1"],
)
def test_non_weekly_sheets_are_rejected(name: str) -> None:
    assert rules.parse_week_name(name) is None
    assert rules.is_weekly_sheet(name) is False


def test_week_naming_in_each_style() -> None:
    day = _dt.date(2026, 7, 28)  # a Tuesday in ISO week 31
    assert rules.week_name(day) == "2026_31W"
    assert rules.week_name(day, style="iso") == "2026_31W"
    # %W and iso-1 agree for 2026 because Jan 1 is a Thursday.
    assert rules.week_name(day, style="us") == "2026_30W"
    assert rules.week_name(day, style="iso-1") == "2026_30W"
    assert rules.week_name(day, suffix="") == "2026_31"
    with pytest.raises(ValueError, match="unknown week style"):
        rules.week_number(day, style="fiscal")  # type: ignore[arg-type]


def test_week_range_is_monday_to_sunday_and_stable_across_the_week() -> None:
    start, end = rules.week_range(_dt.date(2026, 7, 28))
    assert (start, end) == (_dt.date(2026, 7, 27), _dt.date(2026, 8, 2))
    assert start.weekday() == 0 and end.weekday() == 6
    ranges = {rules.week_range(_dt.date(2026, 7, 27) + _dt.timedelta(days=i)) for i in range(7)}
    assert len(ranges) == 1


@pytest.mark.parametrize(
    "name,style,expected_start",
    [
        ("2026_31W", "iso", _dt.date(2026, 7, 27)),
        ("2026_30W", "iso-1", _dt.date(2026, 7, 27)),
        ("2026_1W", "iso", _dt.date(2025, 12, 29)),
    ],
)
def test_week_range_for_name(name: str, style: Any, expected_start: _dt.date) -> None:
    assert rules.week_range_for_name(name, style)[0] == expected_start


def test_week_range_for_name_round_trips_and_rejects_junk() -> None:
    for iso_week in (1, 9, 30, 31, 52):
        name = f"2026_{iso_week}W"
        start, _ = rules.week_range_for_name(name, "iso")
        assert rules.week_name(start, "iso") == name
    with pytest.raises(ValueError, match="not a weekly sheet name"):
        rules.week_range_for_name("Tasks Summary-12-23")


#: The real sheet list, trimmed: gaps (no 2025_39W, 2026_7W, 2026_8W,
#: 2026_17W) and the misnamed 2025_14.
REAL_SHEETS = [
    "Tasks Summary-12-23",
    "2025_1W",
    "2025_13W",
    "2025_14",
    "2025_38W",
    "2025_40W",
    "2025_52W",
    "2026_1W",
    "2026_6W",
    "2026_9W",
    "2026_16W",
    "2026_18W",
    "2026_28W",
    "2026_29W",
]


def test_the_newest_weekly_sheet_is_chosen_by_week_not_position() -> None:
    assert rules.latest_weekly_sheet(REAL_SHEETS) == "2026_29W"
    assert rules.latest_weekly_sheet(["Tasks Summary-12-23", "weekly report temp"]) is None
    assert rules.latest_weekly_sheet(["2026_29W", "2026_9W", "2025_52W", "2026_18W"]) == "2026_29W"
    assert rules.latest_weekly_sheet(["2025_52W", "2026_1W"]) == "2026_1W"
    assert rules.latest_weekly_sheet(["2025_13W", "2025_14"]) == "2025_14"
    assert rules.latest_weekly_sheet([]) is None
    # Strictly before the week reported, so a run never seeds from itself.
    assert rules.latest_weekly_sheet(["2026_30W", "2026_31W", "2026_32W"], before=(2026, 32)) == (
        "2026_31W"
    )


# ---------------------------------------------------------------------------
# JQL and columns
# ---------------------------------------------------------------------------


def test_the_updated_clause_has_an_exclusive_upper_bound() -> None:
    clause = rules.jql_updated_clause(_dt.date(2026, 7, 27), _dt.date(2026, 8, 2))
    assert clause == 'updated >= "2026-07-27" AND updated < "2026-08-03"'


def test_compose_jql_keeps_order_by_last() -> None:
    base = (
        'project = GTM AND status in ("In Progress", "Pending") '
        "ORDER BY updated DESC, cf[10019] ASC"
    )
    out = rules.compose_jql(base, 'updated >= "2026-07-27"')
    assert out == (
        'project = GTM AND status in ("In Progress", "Pending") '
        'AND (updated >= "2026-07-27") ORDER BY updated DESC, cf[10019] ASC'
    )
    assert rules.compose_jql("project = GTM", "a = 1") == "project = GTM AND (a = 1)"
    assert rules.compose_jql("project = GTM ORDER BY updated DESC", "a = 1", "b = 2") == (
        "project = GTM AND (a = 1) AND (b = 2) ORDER BY updated DESC"
    )
    assert rules.compose_jql(base) == base
    assert rules.compose_jql(base, "", "   ") == base
    assert rules.compose_jql("project = GTM order by updated desc", "a = 1") == (
        "project = GTM AND (a = 1) order by updated desc"
    )


def test_the_default_jql_is_the_boards_own_order() -> None:
    assert rules.default_jql() == (
        'project = GTM AND status in ("In Progress", "Ready for Launch", "To Do", "Pending") '
        "ORDER BY updated DESC, cf[10019] ASC"
    )


@pytest.mark.parametrize("index,letter", [(1, "A"), (7, "G"), (26, "Z"), (27, "AA"), (28, "AB")])
def test_column_letters(index: int, letter: str) -> None:
    assert rules.column_letter(index) == letter


def test_column_lookup_is_case_insensitive_and_alias_aware() -> None:
    with pytest.raises(ValueError):
        rules.column_letter(0)
    headers = list(rules.WEEKLY_COLUMNS)
    assert rules.column_for_header(headers, "Key") == "A"
    assert rules.column_for_header(headers, "Comments") == "G"
    # 71 of 75 real sheets say "Sales"; three legacy ones say "Salse".
    misspelt = ["Key", "Summary", "Company", "Status", "Assignee", "Salse", "Comments"]
    assert rules.column_for_header(misspelt, "Sales") == "F"
    assert rules.column_for_header(headers, "Salse") == "F"
    with pytest.raises(KeyError):
        rules.column_for_header(["Key"], "Comments")
    assert rules.resolve_sales_header(["Key", "Salse"]) == "Salse"
    assert rules.resolve_sales_header(["Key", "Sales"]) == "Sales"
    assert rules.resolve_sales_header(None) == "Sales"
    assert rules.resolve_sales_header(["Key", "Summary"]) == "Sales"


# ---------------------------------------------------------------------------
# ADF handling
# ---------------------------------------------------------------------------


def adf(*paragraphs: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs
        ],
    }


def test_adf_and_plain_bodies_flatten_alike() -> None:
    assert rules.comment_body_text("ongoing task: fix rx") == "ongoing task: fix rx"
    assert rules.comment_body_text(None) == ""
    assert rules.comment_body_text({}) == ""
    assert rules.comment_body_text(adf("completed:", "did the thing")) == (
        "completed:\ndid the thing"
    )
    bullets = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "[Completed]"}]},
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Ant1 Tx validation ok"}],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "fix rx power"}],
                            }
                        ],
                    },
                ],
            },
        ],
    }
    assert (
        rules.comment_body_text(bullets) == "[Completed]\n- Ant1 Tx validation ok\n- fix rx power"
    )
    marks = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "completed:", "marks": [{"type": "strong"}]},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "tx cal done"},
                ],
            }
        ],
    }
    assert rules.comment_body_text(marks) == "completed:\ntx cal done"
    mention = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "mention", "attrs": {"text": "@Ming-Kai Shih"}},
                    {"type": "text", "text": " see "},
                    {"type": "inlineCard", "attrs": {"url": "https://example.invalid/x"}},
                ],
            }
        ],
    }
    assert rules.comment_body_text(mention) == "@Ming-Kai Shih see https://example.invalid/x"
    # Jira really does sprinkle \xa0 into pasted comments (seen on GTM-757).
    assert rules.comment_body_text("completed task:\r\n\r\nSelect VNA model\r\n\xa0") == (
        "completed task:\n\nSelect VNA model"
    )
    assert rules.comment_body_text("a\n\n\n\n\nb") == "a\n\nb"
    code = {
        "type": "doc",
        "content": [
            {
                "type": "codeBlock",
                "content": [{"type": "text", "text": "iwpriv wlan1 mp_channel 1"}],
            }
        ],
    }
    assert "iwpriv wlan1 mp_channel 1" in rules.comment_body_text(code)


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------


def one(text: Any, synonyms: Any = None) -> list[tuple[str, list[str]]]:
    return [(b.marker, list(b.lines)) for b in rules.extract_marker_blocks(text, synonyms)]


@pytest.mark.parametrize(
    "header,expected",
    [
        ("[Completed]", "Completed"),
        ("Completed", "Completed"),
        ("completed", "Completed"),
        ("COMPLETED", "Completed"),
        ("[In-progress]", "In-progress"),
        ("In-Progress", "In-progress"),
        ("in progress", "In-progress"),
        ("[Todo]", "Todo"),
        ("Todo", "Todo"),
        ("to do", "Todo"),
        ("[In-Completed]", "In-Completed"),
        ("In-Completed", "In-Completed"),
        ("incompleted", "In-Completed"),
        # The vocabulary the team actually writes.
        ("ongoing task:", "In-progress"),
        ("on-going Task:", "In-progress"),
        ("Ongoing Tasks:", "In-progress"),
        ("completed task:", "Completed"),
        ("Complete tasks:", "Completed"),
        ("#Complete:", "Completed"),
        ("[Complete task]", "Completed"),
        ("complete items:", "Completed"),
        ("in-completed tasks:", "In-Completed"),
        ("next step:", "Todo"),
        ("next setp:", "Todo"),  # real typo in the workbook
        ("pending:", "Todo"),
    ],
)
def test_markers_in_every_observed_spelling(header: str, expected: str) -> None:
    assert one(f"{header}\n- did a thing") == [(expected, ["did a thing"])]


def test_verbatim_comments_from_the_project() -> None:
    gtm_727 = (
        "ongoing task:\n\n"
        "discuss with customer to check test time issue and provided c# example code "
        "to reduce test time.\n\n"
        "they will optimize code flow and test process to reduce more test time."
    )
    blocks = rules.extract_marker_blocks(gtm_727)
    assert len(blocks) == 1 and blocks[0].marker == "In-progress"
    assert len(blocks[0].lines) == 2 and blocks[0].lines[0].startswith("discuss with customer")
    gtm_308 = (
        "Complete tasks: Got the request from Climax  \n"
        "Ongoing Tasks: ask test request from Customer\n"
    )
    assert one(gtm_308) == [
        ("Completed", ["Got the request from Climax"]),
        ("In-progress", ["ask test request from Customer"]),
    ]
    inline = "ongoing task: multiATE can do cellular passed, but got the GPS failed."
    assert one(inline) == [
        ("In-progress", ["multiATE can do cellular passed, but got the GPS failed."])
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Complete the rest of test item OBUE, Intermodulation. And the result is ok",
        "completed OBB test item for the customer",
        "next week will complete Wi-Fi X validation",
        "Demonstrated SA515 multi-dut (2 devices) at S1 factory.",
        "WCN informed us that DUT is controlled via UART.",
    ],
)
def test_prose_is_not_a_marker(text: str) -> None:
    assert rules.extract_marker_blocks(text) == []


def test_block_structure() -> None:
    body = (
        "some preamble nobody tagged\ncompleted:\n- the real content\n"
        "more untagged? no, this belongs to completed"
    )
    (block,) = rules.extract_marker_blocks(body)
    assert "some preamble nobody tagged" not in block.lines
    assert rules.extract_marker_blocks("just a status note with no tags") == []
    assert rules.extract_marker_blocks("") == []
    assert rules.extract_marker_blocks(None) == []
    assert one("completed:\n- a\n- b\nongoing:\n- c") == [
        ("Completed", ["a", "b"]),
        ("In-progress", ["c"]),
    ]
    # Older entries pasted below must not be absorbed into this week's block.
    assert one("completed:\n- this week item\n7/17:\n- last week item") == [
        ("Completed", ["this week item"])
    ]
    # Half the team writes the date under the marker: it is the block's own.
    assert one("[complete]\n8/20\n- CMX500 NR SA part make call and measurement is done") == [
        ("Completed", ["CMX500 NR SA part make call and measurement is done"])
    ]
    numbered = (
        "completed task:\n1.fixed n28 HCH power failed issue\n2.instructed WMT ID setting\n"
        "* third\n- fourth"
    )
    assert one(numbered) == [
        (
            "Completed",
            ["fixed n28 HCH power failed issue", "instructed WMT ID setting", "third", "fourth"],
        )
    ]
    assert one("completed:\n- same\n- same\n- other") == [("Completed", ["same", "other"])]
    assert rules.extract_marker_blocks("[Completed]\n\n[Todo]\n- real") == [
        rules.MarkerBlock("Todo", "Todo", ("real",))
    ]
    # GTM-765: "[Completed] :" rendered as a bullet reading "- :".
    assert rules.extract_marker_blocks("[Completed]\n- :") == []
    assert rules.extract_marker_blocks("completed:\n-\n- ---\n- ...") == []
    assert one("completed:\n- :\n- 完成校正") == [("Completed", ["完成校正"])]
    body = "completed:\n" + "\n".join(f"- line {i}" for i in range(50))
    (capped,) = rules.extract_marker_blocks(body, max_lines_per_block=5)
    assert len(capped.lines) == 5
    assert one(adf("ongoing task:", "fix the rx power level")) == [
        ("In-progress", ["fix the rx power level"])
    ]
    only_completed = {"Completed": ("completed",)}
    assert one("ongoing task:\n- x", only_completed) == []
    assert one("completed:\n- x", only_completed) == [("Completed", ["x"])]
    assert rules.MarkerBlock("Completed", "ongoing task", ("a", "b")).as_text() == (
        "[Completed]\n- a\n- b"
    )
    assert rules.MarkerBlock("Todo", "todo", ()).as_text() == "[Todo]"


def test_merging_orders_canonically_and_dedupes_lines() -> None:
    blocks = [
        rules.MarkerBlock("Todo", "next step", ("plan a",)),
        rules.MarkerBlock("Completed", "completed", ("did a",)),
        rules.MarkerBlock("Completed", "complete task", ("did b",)),
    ]
    assert [(b.marker, list(b.lines)) for b in rules.merge_marker_blocks(blocks)] == [
        ("Completed", ["did a", "did b"]),
        ("Todo", ["plan a"]),
    ]
    (merged,) = rules.merge_marker_blocks(
        [
            rules.MarkerBlock("Completed", "completed", ("same",)),
            rules.MarkerBlock("Completed", "complete", ("same", "other")),
        ]
    )
    assert list(merged.lines) == ["same", "other"]
    assert rules.merge_marker_blocks([]) == []


# ---------------------------------------------------------------------------
# Comment windows and formatting
# ---------------------------------------------------------------------------


def comment(created: str, body: Any) -> dict[str, Any]:
    return {"created": created, "body": body, "author": {"displayName": "Ming-Kai Shih"}}


COMMENTS = [
    comment("2026-07-10T14:06:27.878+0800", "completed task:\n- old item"),
    comment("2026-07-28T09:00:00.000+0800", "ongoing task:\n- this week item"),
    comment("2026-08-05T09:00:00.000+0800", "completed:\n- future item"),
]
WEEK = (_dt.date(2026, 7, 27), _dt.date(2026, 8, 2))


def test_jira_timestamps_parse() -> None:
    parsed = rules.parse_jira_datetime("2026-07-28T14:30:55.627+0800")
    assert parsed is not None and parsed.year == 2026 and parsed.hour == 14
    assert rules.parse_jira_datetime("2026-07-28T06:30:55Z") is not None
    assert rules.parse_jira_datetime("not a date") is None
    assert rules.parse_jira_datetime("") is None
    assert rules.parse_jira_datetime(None) is None


def test_the_window_is_inclusive_and_keeps_undated_comments() -> None:
    picked = rules.select_comments_in_window(COMMENTS, *WEEK)
    assert len(picked) == 1 and "this week item" in picked[0]["body"]
    edges = [
        comment("2026-07-27T00:00:01.000+0800", "completed:\n- monday"),
        comment("2026-08-02T23:59:59.000+0800", "completed:\n- sunday"),
    ]
    assert len(rules.select_comments_in_window(edges, *WEEK)) == 2
    assert "old item" in rules.select_comments_in_window(COMMENTS)[0]["body"]
    undated = [{"body": "completed:\n- no timestamp"}]
    assert len(rules.select_comments_in_window(undated, *WEEK)) == 1


def test_blocks_keep_the_day_they_were_written() -> None:
    three_days = [
        comment("2026-07-27T09:00:00.000+0800", "completed:\n- a"),
        comment("2026-07-29T09:00:00.000+0800", "ongoing task:\n- b"),
        comment("2026-07-30T09:00:00.000+0800", "completed:\n- c"),
    ]
    blocks = rules.extract_week_blocks(three_days, *WEEK)
    assert [(b.day, b.marker, list(b.lines)) for b in blocks] == [
        (_dt.date(2026, 7, 30), "Completed", ["c"]),
        (_dt.date(2026, 7, 29), "In-progress", ["b"]),
        (_dt.date(2026, 7, 27), "Completed", ["a"]),
    ]
    same_day = [
        comment("2026-07-29T09:00:00.000+0800", "completed:\n- a"),
        comment("2026-07-29T17:00:00.000+0800", "completed:\n- b"),
    ]
    assert [
        (b.day, b.marker, list(b.lines)) for b in rules.extract_week_blocks(same_day, *WEEK)
    ] == [(_dt.date(2026, 7, 29), "Completed", ["a", "b"])]
    dateless = rules.extract_week_blocks([{"body": "completed:\n- x"}])
    assert dateless and dateless[0].day is None


def test_the_block_matches_the_shape_already_in_the_workbook() -> None:
    assert rules.format_date_header(_dt.date(2026, 7, 9)) == "7/9:"
    assert rules.format_date_header(_dt.date(2026, 7, 23), zero_pad=True) == "07/23:"
    blocks = [
        rules.MarkerBlock(
            "Completed", "completed", ("modify dut firmware", "Ant1 Tx validation ok")
        ),
        rules.MarkerBlock("In-progress", "ongoing", ("HDT cminstrument implementation",)),
    ]
    assert rules.format_comment_block(_dt.date(2026, 7, 28), blocks) == (
        "7/28:\n"
        "[Completed]\n"
        "- modify dut firmware\n"
        "- Ant1 Tx validation ok\n"
        "[In-progress]\n"
        "- HDT cminstrument implementation\n"
    )
    assert rules.format_comment_block(_dt.date(2026, 7, 28), []) == ""
    todo = [rules.MarkerBlock("Todo", "todo", ("x",))]
    assert "* x" in rules.format_comment_block(_dt.date(2026, 7, 28), todo, bullet="* ")
    dated = [
        rules.MarkerBlock("Completed", "completed", ("tx cal done",), _dt.date(2026, 7, 30)),
        rules.MarkerBlock("In-progress", "ongoing", ("fix rx power",), _dt.date(2026, 7, 28)),
    ]
    # 8/1 is the run date here and must appear nowhere.
    assert rules.format_comment_block(_dt.date(2026, 8, 1), dated) == (
        "7/30:\n[Completed]\n- tx cal done\n7/28:\n[In-progress]\n- fix rx power\n"
    )
    assert rules.format_comment_block(_dt.date(2026, 7, 28), todo).startswith("7/28:")
    mixed = [
        rules.MarkerBlock("Completed", "completed", ("dated",), _dt.date(2026, 7, 30)),
        rules.MarkerBlock("Todo", "todo", ("undated",)),
    ]
    out = rules.format_comment_block(_dt.date(2026, 7, 28), mixed)
    assert out.index("7/30:") < out.index("7/28:"), "newest first"


NEW = "7/28:\n[Completed]\n- did a thing\n"
OLD = "7/17:\nBT Tx BR LE are ready\nnext week will implement HTD\n"


def test_a_rerun_in_the_same_week_never_stacks_the_block() -> None:
    assert rules.should_prepend(None, NEW) is True
    assert rules.should_prepend("", NEW) is True
    assert rules.should_prepend(OLD, NEW) is True
    assert rules.should_prepend(NEW + OLD, NEW) is False
    assert rules.should_prepend("7/28:\n[completed]\n-   did a thing\n" + OLD, NEW) is False
    # The user hand-added a newer entry on top after the last run.
    assert rules.should_prepend("7/30:\nhand written note\n" + NEW + OLD, NEW) is False
    other = "7/28:\n[Completed]\n- something else entirely\n"
    assert rules.should_prepend(NEW + OLD, other) is True
    assert rules.should_prepend(OLD, "") is False
    assert rules.should_prepend(OLD, "   \n  ") is False
    assert rules.normalise_for_dedupe("a\n\n\nb") == "a\nb"


# ---------------------------------------------------------------------------
# Row mapping
# ---------------------------------------------------------------------------

ISSUE = {
    "key": "GTM-727",
    "fields": {
        "summary": "[Ghiatek][ZNB]ATE integration with their switching box",
        "status": {"name": "In Progress"},
        "assignee": {"displayName": "Ming-Kai Shih"},
        rules.FIELD_COMPANY: "Ghiatek",
        rules.FIELD_SALES: "Wendy/Teresa",
    },
}


def test_an_issue_maps_to_a_row_and_never_to_the_comments_column() -> None:
    assert rules.issue_to_row(ISSUE) == {
        "Key": "GTM-727",
        "Summary": "[Ghiatek][ZNB]ATE integration with their switching box",
        "Company": "Ghiatek",
        "Status": "In Progress",
        "Assignee": "Ming-Kai Shih",
        "Sales": "Wendy/Teresa",
    }
    assert "Comments" not in rules.issue_to_row(ISSUE)
    assert "Salse" in rules.issue_to_row(ISSUE, sales_header="Salse")
    assert (
        rules.issue_to_row({"key": "GTM-487", "fields": {"summary": "x", "assignee": None}})[
            "Assignee"
        ]
        == rules.UNASSIGNED
    )
    row = rules.issue_to_row({"key": "GTM-1", "fields": {}})
    assert row["Company"] == "" and row["Status"] == "" and row["Summary"] == ""
    assert rules.display(["a", {"name": "b"}, None]) == "a, b"
