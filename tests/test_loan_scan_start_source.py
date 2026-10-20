# Vendored oracle: rs_workflow_system@896046e8 host-bridge/tests/test_loan_scan_start.py; only tests/loan_oracle.py REPLACEMENTS differ.
"""Workflow 06's start-time cut-off.

Ported from the predecessor project's `c4c/outlook/loan-scan.ps1`, whose comment
states the reason plainly:

    the inbox already holds mails a human dealt with by hand before the
    automation existed; re-answering those customers would be bad

So the rule is a visible cut-off, not anything inferred from what has already
been handled: an explicit `processFrom` wins, otherwise a stamp written on the
very first scan, which means "from now on".

`loan_scan` had no tests before this. Outlook is faked; nothing here reads a
mailbox or writes a queue.
"""

from __future__ import annotations

import datetime as _dt
import json

import pytest

from capabilities.loan_reply import scan as loan_scan
from capabilities.loan_reply.scan import JobError


def mail(received: str | None, subject: str = "not a loan form") -> dict:
    m = {"entryId": received or "none", "subject": subject, "body": "", "htmlBody": ""}
    if received is not None:
        m["receivedTime"] = received
    return m


class FakeBridge:
    def __init__(self, messages):
        self.messages = messages
        self.listed: list[dict] = []

    def email_list(self, **kw):
        self.listed.append(kw)
        return {"messages": self.messages}


@pytest.fixture
def stamp(tmp_path, monkeypatch):
    """Move the queue root, so the first-run stamp lands in tmp.

    Not by patching a module constant: the job resolves the path per call, so
    relocating the root is the whole mechanism and this exercises it.
    """
    from capabilities.loan_reply import queue as q

    monkeypatch.setattr(q, "QUEUE_ROOT", tmp_path)
    return tmp_path / ".processing-start"


def scan(messages, cfg=None, params=None, monkeypatch=None):
    bridge = FakeBridge(messages)
    monkeypatch.setattr(loan_scan, "_bridge", lambda: bridge)
    full = {**loan_scan.DEFAULTS, **(cfg or {})}
    out = loan_scan.run({"_config": full, "dryRun": True, **(params or {})}, log=lambda _m: None)
    return out, bridge


class TestWhereTheCutOffComesFrom:
    def test_an_explicit_processFrom_wins(self, stamp, monkeypatch):
        stamp.write_text("2020-01-01T00:00:00", encoding="utf-8")
        out, _ = scan([], cfg={"processFrom": "2026-08-11 09:00"}, monkeypatch=monkeypatch)
        assert out["processFrom"] == "2026-08-11T09:00:00"
        assert out["processFromSource"] == "config processFrom"

    def test_a_param_beats_the_config(self, stamp, monkeypatch):
        out, _ = scan([], cfg={"processFrom": "2026-08-11 09:00"},
                      params={"processFrom": "2026-08-12 07:30"}, monkeypatch=monkeypatch)
        assert out["processFrom"] == "2026-08-12T07:30:00"

    def test_the_first_run_stamps_now_and_keeps_it(self, stamp, monkeypatch):
        assert not stamp.exists()
        first, _ = scan([], monkeypatch=monkeypatch)
        assert first["processFromSource"] == "first run (stamped now)"
        assert stamp.is_file(), "the stamp has to survive the run"

        second, _ = scan([], monkeypatch=monkeypatch)
        assert second["processFromSource"] == "first-run stamp"
        assert second["processFrom"] == first["processFrom"], "the cut-off must not drift"

    def test_an_unreadable_stamp_is_replaced_not_fatal(self, stamp, monkeypatch):
        stamp.write_text("not a date", encoding="utf-8")
        out, _ = scan([], monkeypatch=monkeypatch)
        assert out["processFromSource"] == "first run (stamped now)"

    def test_an_unparseable_processFrom_is_fatal(self, stamp, monkeypatch):
        """Falling back would turn "go back to last week" into "from now on"
        -- the opposite of what was asked, and silent about it."""
        with pytest.raises(JobError, match="processFrom"):
            scan([], cfg={"processFrom": "11/08/2026 9am"}, monkeypatch=monkeypatch)
        assert not stamp.exists(), "a bad value must not quietly stamp one either"


class TestWhatGetsLookedAt:
    CUTOFF = "2026-08-11 09:00"

    def test_mail_before_the_cut_off_is_left_alone(self, stamp, monkeypatch):
        out, _ = scan(
            [mail("2026-08-11T08:59:59"), mail("2026-08-10T23:00:00")],
            cfg={"processFrom": self.CUTOFF}, monkeypatch=monkeypatch,
        )
        assert out["beforeStart"] == 2
        assert out["notLoanForms"] == 0, "it should not even have been parsed"

    def test_mail_exactly_on_the_cut_off_is_ours(self, stamp, monkeypatch):
        out, _ = scan([mail("2026-08-11T09:00:00")],
                      cfg={"processFrom": self.CUTOFF}, monkeypatch=monkeypatch)
        assert out["beforeStart"] == 0
        assert out["notLoanForms"] == 1, "parsed, and found not to be a loan form"

    def test_mail_with_no_readable_timestamp_is_skipped_and_counted(self, stamp, monkeypatch):
        """The cut-off cannot be applied, and writing to a customer somebody
        already answered is worse than a late form. Counted, not silent."""
        out, _ = scan([mail(None), mail("nonsense")],
                      cfg={"processFrom": self.CUTOFF}, monkeypatch=monkeypatch)
        assert out["undated"] == 2
        assert out["notLoanForms"] == 0


class TestThereIsOnlyOneBound:
    """The cut-off is what gets fetched, too.

    There used to be a second knob, sinceHours, bounding the fetch. It could
    only narrow what processFrom had already decided, so a cut-off older than
    that window silently did nothing -- and the first fix for that was a warning
    about a contradiction that should not have been constructible.
    """

    def test_the_fetch_starts_at_the_cut_off(self, stamp, monkeypatch):
        old = (_dt.datetime.now() - _dt.timedelta(days=30)).replace(second=0, microsecond=0)
        _, bridge = scan([], cfg={"processFrom": old.strftime("%Y-%m-%d %H:%M")},
                         monkeypatch=monkeypatch)
        assert _dt.datetime.fromisoformat(bridge.listed[0]["since"]) == old

    def test_a_leftover_sinceHours_is_ignored_out_loud(self, stamp, monkeypatch):
        """Someone's existing workflow-06.json still has it."""
        said: list[str] = []
        bridge = FakeBridge([])
        monkeypatch.setattr(loan_scan, "_bridge", lambda: bridge)
        old = (_dt.datetime.now() - _dt.timedelta(days=30)).replace(second=0, microsecond=0)
        loan_scan.run(
            {"_config": {**loan_scan.DEFAULTS, "processFrom": old.strftime("%Y-%m-%d %H:%M"),
                         "sinceHours": 1},
             "dryRun": True},
            log=said.append,
        )
        assert any("sinceHours is no longer used" in m for m in said), said
        assert _dt.datetime.fromisoformat(bridge.listed[0]["since"]) == old,             "and it must not narrow the fetch"

    def test_hitting_the_cap_is_reported(self, stamp, monkeypatch):
        """The cap can still hide older mail -- that risk is real, unlike the
        one the old note warned about."""
        msgs = [mail(f"2026-08-11T09:0{i % 10}:00") for i in range(5)]
        out, _ = scan(msgs, cfg={"processFrom": "2026-08-11 09:00", "maxMessages": 5},
                      monkeypatch=monkeypatch)
        assert out["windowNote"] and "maxMessages" in out["windowNote"]

    def test_not_hitting_the_cap_is_quiet(self, stamp, monkeypatch):
        out, _ = scan([mail("2026-08-11T09:30:00")],
                      cfg={"processFrom": "2026-08-11 09:00", "maxMessages": 5},
                      monkeypatch=monkeypatch)
        assert out["windowNote"] is None


class TestTheSummaryAlwaysCarriesIt:
    def test_the_keys_are_present_on_a_normal_run(self, stamp, monkeypatch):
        out, _ = scan([], monkeypatch=monkeypatch)
        for key in ("processFrom", "processFromSource", "beforeStart", "undated", "windowNote"):
            assert key in out, key

    def test_and_when_another_scan_holds_the_lock(self, stamp, monkeypatch, tmp_path):
        """A caller reading the summary should not have to know which path
        produced it."""
        from capabilities.loan_reply import queue as q

        def busy(*_a, **_kw):
            raise q.RunLockBusy("loan_scan", {"pid": 4242, "startedAt": "2026-08-18T10:00:00"})

        monkeypatch.setattr(q, "acquire_run_lock", busy)
        out, _ = scan([], monkeypatch=monkeypatch)
        assert out["skippedRun"] is True
        for key in ("processFrom", "processFromSource", "beforeStart", "undated", "windowNote"):
            assert key in out, key
