"""The nightly review compares its last run by local date (a UTC stamp made at
03:00 in Taipei is still the previous day's date in UTC)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from host_runtime.web import _local_day

TAIPEI = timezone(timedelta(hours=8))


def test_a_utc_stamp_from_early_this_morning_is_today_in_local_time() -> None:
    moment = datetime(2026, 10, 21, 4, 10, tzinfo=TAIPEI)
    ran_at_0215_local = "2026-10-20T18:15:00+00:00"
    assert _local_day(ran_at_0215_local, moment) == "2026-10-21"


def test_yesterdays_run_is_still_yesterday() -> None:
    moment = datetime(2026, 10, 21, 3, 0, tzinfo=TAIPEI)
    assert _local_day("2026-10-19T18:30:00+00:00", moment) == "2026-10-20"


def test_missing_naive_and_unreadable_stamps() -> None:
    moment = datetime(2026, 10, 21, 3, 0, tzinfo=TAIPEI)
    assert _local_day(None, moment) == ""
    assert _local_day("", moment) == ""
    assert _local_day("2026-10-21T03:00:00", moment) == "2026-10-21"
    assert _local_day("2026-10-21 garbage", moment) == "2026-10-21"
