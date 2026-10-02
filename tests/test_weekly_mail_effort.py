"""Who worked on what, counted the way the source counted it.

The cases use the shapes the owner's own board carries, read on 2026-09-24:
an instrument field holding one name, several names, or nothing, and titles
that name an instrument the field does not.
"""

from __future__ import annotations

import datetime as dt

import pytest

from capabilities.weekly_report import effort, mail
from capabilities.weekly_report.contracts import ReportingWindow, ReportItem


def item(
    key: str,
    *,
    summary: str = "",
    assignee: str = "",
    company: str = "",
    instrument: str = "",
) -> ReportItem:
    return ReportItem(
        key=key, summary=summary, assignee=assignee, company=company, instrument=instrument
    )


def test_sde_draft_uses_live_counts_and_the_reference_sections() -> None:
    window = ReportingWindow(
        week="2026_40W", since=dt.date(2026, 9, 28), until=dt.date(2026, 10, 4),
        comment_since=dt.date(2026, 9, 28), stamp_date=dt.date(2026, 10, 4),
    )
    items = (
        item("GH-1", assignee="JennyChen", company="FII", instrument="CMP180, WMT"),
        item("GH-2", assignee="JennyChen", company="FII", instrument="CMP180"),
        item("GH-3", assignee="shih-m", company="Google", instrument="CMX500"),
    )
    html = mail.build_html(
        window, items, chart_cid="chart-id", matched=4, project="rs-sde-projects"
    )
    assert mail.subject(window) == "SDE Weekly Report 2026_40W (2026-09-28 - 2026-10-04)"
    assert "本週有留言的 <b>3</b> / 4 張" in html
    assert "GitHub Project rs-sde-projects" in html
    assert "cid:chart-id" in html
    assert "Tickets per team member" in html and "Split per team member" in html
    assert "Instrument totals" in html and "Account totals" in html
    assert "CMP180" in html and "WMT" in html and "FII" in html
    assert "合計 (total)</td>" in html and ">3</td>" in html
    assert "width='808'" in html and html.count("width='96'") == 4
    assert "Instrument and Account come from the configured GitHub Project fields" in html
    assert "2026-09-28～2026-10-04" in html


def test_source_draft_empty_week_explains_why_the_filter_dropped_everything() -> None:
    window = ReportingWindow(
        week="2026_40W", since=dt.date(2026, 9, 28), until=dt.date(2026, 10, 4),
        comment_since=dt.date(2026, 9, 28), stamp_date=dt.date(2026, 10, 4),
    )
    html = mail.build_html(window, (), matched=3)
    assert "本週有留言的 <b>0</b> / 3 張" in html
    assert "沒有任何 ticket" in html and "3 張符合查詢但未計入" in html
    assert "No instrument chart this week" in html
    assert "0%" in html


def test_source_draft_unfiltered_week_does_not_claim_comments_were_required() -> None:
    window = ReportingWindow(
        week="2026_40W", since=dt.date(2026, 9, 28), until=dt.date(2026, 10, 4),
        comment_since=dt.date(2026, 9, 28), stamp_date=dt.date(2026, 10, 4),
    )
    html = mail.build_html(window, (item("GH-1", instrument="CMP180"),),
                           activity_required=False, matched=1)
    assert "本週符合條件的 <b>1</b> / 1 張" in html
    assert "未啟用本週留言篩選" in html
    assert "0 matching ticket(s) excluded by the activity rule" not in html


def test_reference_week_instrument_total_can_exceed_eight_tickets() -> None:
    """The owner's 2026_40W draft showed 11 instrument-tickets from 8 tickets.

    This source-derived shape protects the title and share denominator when
    three tickets each name a second instrument.
    """
    window = ReportingWindow(
        week="2026_40W", since=dt.date(2026, 9, 28), until=dt.date(2026, 10, 4),
        comment_since=dt.date(2026, 9, 28), stamp_date=dt.date(2026, 10, 4),
    )
    instruments = (
        "CMP180, CMW100", "CMP180, CMX500", "CMP180, PVT360A", "CMP180",
        "CMP180", "CMP180", "WMT", "WMT2.0",
    )
    items = tuple(item(f"GH-{index}", instrument=name, assignee="Member")
                  for index, name in enumerate(instruments, 1))
    html = mail.build_html(window, items, chart_cid="effortpie", matched=8)
    assert "11 instrument-tickets from 8 tickets" in html
    assert "Share uses 11 instrument-tickets as its denominator" in html
    assert "55%" in html  # CMP180: 6 / 11, not 6 / 8.
    assert html.index("Tickets per team member") < html.index("Tickets by instrument")
    assert html.index("Tickets by instrument") < html.index("Instrument totals")
    assert html.index("Instrument totals") < html.index("Account totals")
    assert "Account / chipset development" not in html


@pytest.mark.parametrize(
    "summary, expected",
    [
        ("[WNC LCS8][CMP180]WMT for QC WCN785x demo", "CMP180"),
        ("Climax FSVA ATE request", "FSVA"),
        ("[Grand-tek][ZNB3K+ZN-Z154 e-cal] broken", "ZNB3000"),
        ("Providing API description and API Training", "Unassigned"),
    ],
)
def test_a_title_names_its_instrument(summary: str, expected: str) -> None:
    """The vocabulary is matched anywhere in the title, longest name first,
    and a model number butting up against `+` still counts."""
    assert effort.derive_instrument(summary) == expected


def test_the_boards_field_wins_over_the_title() -> None:
    """The field is what the team maintains, and it is right where a title
    cannot say it."""
    assert effort.instrument_field(item("A-1", summary="Nordic BLE testing")) == "Unassigned"
    named = item("A-1", summary="Nordic BLE testing", instrument="CMW100")
    assert effort.instrument_field(named) == "CMW100"


def test_a_name_nobody_listed_is_still_the_answer() -> None:
    """Forcing an unfamiliar name back to `Unassigned` hides a real answer,
    which is the failure this rule exists to prevent. The owner's board holds
    `PVT360A` and `WMT2.0`, neither of which is in the vocabulary."""
    assert effort.instrument_field(item("A-1", instrument="PVT360A")) == "PVT360A"
    assert effort.instruments_for(item("A-1", instrument="WMT2.0")) == ["WMT2.0"]


def test_one_ticket_can_be_about_several_instruments() -> None:
    """Counting `CMP180, CMX500, WMT2.0, WMT` whole would invent an
    instrument of that name with a count of one."""
    several = item("A-1", instrument="CMP180, CMX500, WMT2.0, WMT")
    assert effort.instruments_for(several) == ["CMP180", "CMX500", "WMT2.0", "WMT"]
    assert effort.instruments_for(item("A-2", instrument="FSW, FSW")) == ["FSW"], "counted once"
    assert effort.instruments_for(item("A-3", instrument="ZNB3K")) == ["ZNB3000"], "one spelling"


def test_instrument_totals_sum_to_more_than_the_tickets() -> None:
    """Deliberate, and the mail says so rather than hiding it."""
    items = [
        item("A-1", instrument="CMP180, WMT"),
        item("A-2", instrument="CMP180"),
        item("A-3", instrument="CMW100"),
    ]
    totals = effort.instrument_totals(items)
    assert totals == {"CMP180": 2, "CMW100": 1, "WMT": 1}
    assert sum(totals.values()) == 4, "three tickets, four counts"


def test_unassigned_is_kept_and_sorts_last() -> None:
    """Never silently dropped, and never leading a legend."""
    items = [item("A-1"), item("A-2"), item("A-3", instrument="CMP180")]
    totals = effort.instrument_totals(items)
    assert list(totals) == ["CMP180", "Unassigned"]
    assert totals["Unassigned"] == 2


def test_members_and_accounts_are_counted_by_ticket() -> None:
    """One unit per ticket: there is no hour data in this project to weigh,
    and the mail says that on its face."""
    items = [
        item("A-1", assignee="Ming-Kai Shih", company="WNC"),
        item("A-2", assignee="Ming-Kai Shih", company="Foxconn"),
        item("A-3", assignee="Klaus Peng", company="WNC"),
        item("A-4"),
    ]
    assert effort.member_totals(items) == {
        "Ming-Kai Shih": 2,
        "Klaus Peng": 1,
        "Unassigned": 1,
    }
    assert effort.account_totals(items) == {"WNC": 2, "Foxconn": 1, "Unassigned": 1}


def test_buckets_put_a_multi_instrument_ticket_under_each() -> None:
    items = [
        item("A-1", assignee="Alex Chen", instrument="CMP180, WMT"),
        item("A-2", assignee="Alex Chen", instrument="CMP180"),
    ]
    by_member = effort.buckets(items)
    assert by_member == {"Alex Chen": {"CMP180": ["A-1", "A-2"], "WMT": ["A-1"]}}
    by_account = effort.buckets(items, "account")
    assert by_account == {"Alex Chen": {"Unassigned": ["A-1", "A-2"]}}, "an account is single"


def test_member_rows_are_one_per_ticket_and_grouped() -> None:
    """The table's instrument is the single-cell view: what the field says,
    where the counting splits it."""
    items = [
        item("A-2", assignee="Klaus Peng", company="WNC", instrument="CMP180, WMT"),
        item("A-1", assignee="Alex Chen", company="Foxconn", instrument="CMW100"),
        item("A-3"),
    ]
    rows = effort.member_rows(items)
    assert [row["member"] for row in rows] == ["Alex Chen", "Klaus Peng", "Unassigned"]
    assert rows[1]["instrument"] == "CMP180, WMT", "as written, not split"
    assert rows[1]["account"] == "WNC"


def test_the_same_week_counted_twice_reads_the_same() -> None:
    """A mail somebody compares with last week's has to be stable."""
    items = [item(f"A-{n}", assignee="Somebody", instrument="CMP180") for n in range(5)]
    assert effort.instrument_totals(items) == effort.instrument_totals(list(reversed(items)))
    assert effort.member_totals(items) == effort.member_totals(list(reversed(items)))


def test_the_mail_counts_only_what_somebody_worked_on() -> None:
    """A ticket whose timestamp moved because somebody edited a field is not
    a ticket somebody worked on."""
    import datetime as _dt

    from capabilities.weekly_report.contracts import ReportComment

    since, until = _dt.date(2026, 9, 21), _dt.date(2026, 9, 27)
    worked = ReportItem(
        key="A-1",
        comments=(ReportComment(created="2026-09-23T07:48:31Z", body="[Completed]"),),
    )
    edited = ReportItem(key="A-2")
    older = ReportItem(
        key="A-3",
        comments=(ReportComment(created="2026-09-10T07:48:31Z", body="[Completed]"),),
    )
    activity = effort.active_items([worked, edited, older], since, until)
    assert [item.key for item in activity.counted] == ["A-1"]
    assert activity.excluded == ("A-2", "A-3"), "named, because fifty-nine vanishing is not a count"


def test_a_week_with_nothing_in_it_still_produces_a_record() -> None:
    """There is no chart to draw in a quiet week, so the drafted record
    carries no path to one. `Text` refuses an empty string, so a field that
    may be empty is a plain `str`; this was a real defect, found on
    2026-09-24 only because a browser contract tripped over the same rule.
    """
    from capabilities.weekly_report.contracts import WeeklyMailDrafted

    quiet = WeeklyMailDrafted(
        week="2026_39W",
        subject="GTM weekly report 2026_39W",
        matched=0,
        counted=0,
    )
    assert quiet.chart_path == "" and quiet.preview == ""
    assert quiet.entry_id == "" and quiet.folder == ""


def test_the_activity_filter_can_be_turned_off() -> None:
    """Off, the mail counts everything the week matched, and says so."""
    import datetime as _dt

    since, until = _dt.date(2026, 9, 21), _dt.date(2026, 9, 27)
    items = [ReportItem(key="A-1"), ReportItem(key="A-2")]
    activity = effort.active_items(items, since, until, required=False)
    assert len(activity.counted) == 2
    assert activity.excluded == () and activity.required is False
