# Vendored oracle: rs_workflow_system@896046e8 host-bridge/tests/test_loan_queue.py; only tests/loan_oracle.py REPLACEMENTS differ.
"""The loan work queue and the scanner that fills it (workflows 06 / 06b)."""

from __future__ import annotations

import json
import os

import pytest

from capabilities.loan_reply import queue as q
from capabilities.loan_reply import scan as loan_scan

PORTAL = "https://rstw-portal.rsint.net/FastView.aspx"


def item(borrow_no: str, **extra) -> dict:
    return {"borrowNo": borrow_no, "loanUrl": f"{PORTAL}?accessId={borrow_no}", **extra}


class TestQueueBasics:
    def test_enqueue_then_claim_then_finish(self, tmp_path):
        assert q.enqueue(item("DR1"), root=tmp_path) is not None
        assert q.counts(tmp_path) == {"pending": 1, "claimed": 0, "done": 0, "failed": 0}

        claimed = q.claim_one(tmp_path)
        assert claimed is not None and claimed.borrow_no == "DR1"
        assert q.counts(tmp_path)["claimed"] == 1

        q.finish(claimed, "done", {"customerId": "130895"}, root=tmp_path)
        assert q.counts(tmp_path) == {"pending": 0, "claimed": 0, "done": 1, "failed": 0}
        saved = json.loads((tmp_path / "done" / "DR1.json").read_text(encoding="utf-8"))
        assert saved["result"]["customerId"] == "130895"
        assert saved["outcome"] == "done"

    def test_claiming_an_empty_queue_returns_none(self, tmp_path):
        assert q.claim_one(tmp_path) is None

    def test_a_second_claim_cannot_take_the_same_item(self, tmp_path):
        """The rename *is* the claim, so two consumers cannot both win."""
        q.enqueue(item("DR1"), root=tmp_path)
        first = q.claim_one(tmp_path)
        second = q.claim_one(tmp_path)
        assert first is not None and second is None

    def test_claims_come_out_oldest_first(self, tmp_path):
        import os
        import time

        for n in ("DR1", "DR2", "DR3"):
            q.enqueue(item(n), root=tmp_path)
            time.sleep(0.01)
        # make the order unambiguous regardless of filesystem timestamp
        # resolution
        base = (tmp_path / "pending" / "DR1.json").stat().st_mtime
        for i, n in enumerate(("DR1", "DR2", "DR3")):
            os.utime(tmp_path / "pending" / f"{n}.json", (base + i, base + i))
        assert [q.claim_one(tmp_path).borrow_no for _ in range(3)] == ["DR1", "DR2", "DR3"]

    def test_finish_only_accepts_done_or_failed(self, tmp_path):
        q.enqueue(item("DR1"), root=tmp_path)
        claimed = q.claim_one(tmp_path)
        with pytest.raises(ValueError):
            q.finish(claimed, "pending", root=tmp_path)


class TestDedupe:
    """Identity is the borrow number, not the mail: 8 of 118 forms arrive
    twice, once approved and once rejected."""

    def test_the_same_borrow_number_is_not_queued_twice(self, tmp_path):
        assert q.enqueue(item("DR1"), root=tmp_path) is not None
        assert q.enqueue(item("DR1"), root=tmp_path) is None
        assert q.counts(tmp_path)["pending"] == 1

    @pytest.mark.parametrize("state", ["claimed", "done", "failed"])
    def test_a_finished_form_is_not_queued_again(self, tmp_path, state):
        """Otherwise a second approval notice would re-run the whole flow and
        leave the user a duplicate draft reply."""
        q.enqueue(item("DR1"), root=tmp_path)
        claimed = q.claim_one(tmp_path)
        if state != "claimed":
            q.finish(claimed, state, root=tmp_path)
        assert q.enqueue(item("DR1"), root=tmp_path) is None

    def test_known_numbers_span_every_state(self, tmp_path):
        q.enqueue(item("DR1"), root=tmp_path)
        q.finish(q.claim_one(tmp_path), "done", root=tmp_path)
        q.enqueue(item("DR2"), root=tmp_path)
        assert q.known_borrow_numbers(tmp_path) == {"DR1", "DR2"}


class TestAbandonedClaims:
    def test_an_expired_claim_returns_to_pending(self, tmp_path):
        """A Bridge restarted mid-item would otherwise strand the form: the
        consumer cannot see it and the dedupe stops it being re-enqueued."""
        q.enqueue(item("DR1"), root=tmp_path)
        q.claim_one(tmp_path)
        assert q.reclaim_expired(tmp_path, ttl=-1) == ["DR1"]
        assert q.counts(tmp_path)["pending"] == 1

    def test_a_fresh_claim_is_left_alone(self, tmp_path):
        q.enqueue(item("DR1"), root=tmp_path)
        q.claim_one(tmp_path)
        assert q.reclaim_expired(tmp_path, ttl=3600) == []
        assert q.counts(tmp_path)["claimed"] == 1

    def test_the_ttl_is_longer_than_a_real_run(self):
        """The consumer drives two browser flows and a screenshot."""
        assert q.CLAIM_TTL_SEC >= 600


class TestFilenameSafety:
    @pytest.mark.parametrize("borrow", ["../escape", "DR/1", "DR 1", "", "DR:1"])
    def test_a_borrow_number_cannot_escape_the_queue(self, tmp_path, borrow):
        q.enqueue(item(borrow), root=tmp_path)
        written = list(tmp_path.rglob("*.json"))
        assert written
        for f in written:
            assert f.parent.parent == tmp_path, f"{borrow!r} escaped to {f}"

    def test_a_corrupt_item_is_failed_rather_than_crashing(self, tmp_path):
        q.ensure_dirs(tmp_path)
        (tmp_path / "pending" / "DR1.json").write_text("{not json", encoding="utf-8")
        assert q.claim_one(tmp_path) is None
        assert q.counts(tmp_path)["failed"] == 1


class TestRunLock:
    """Only one consumer at a time.

    Claiming an *item* needs no lock -- os.replace decides the winner. A whole
    *run* has nothing to rename and needs a different guarantee: two runs would
    each open their own Edge session on the same profile.
    """

    def test_a_second_run_is_refused_while_the_first_holds_it(self, tmp_path):
        first = q.acquire_run_lock("loan_process", tmp_path)
        try:
            with pytest.raises(q.RunLockBusy):
                q.acquire_run_lock("loan_process", tmp_path)
        finally:
            first.release()

    def test_releasing_lets_the_next_run_in(self, tmp_path):
        q.acquire_run_lock("loan_process", tmp_path).release()
        q.acquire_run_lock("loan_process", tmp_path).release()

    def test_two_runs_inside_one_bridge_process_are_caught(self, tmp_path):
        """The common case: n8n calls the same Bridge twice.

        Both runs are threads in one process and so record the same pid, which
        makes a liveness check useless -- it answers "alive" for both. The lock
        still holds because staleness falls through to the TTL, and the holder's
        file is fresh.
        """
        first = q.acquire_run_lock("loan_process", tmp_path)
        try:
            holder = json.loads((tmp_path / "loan_process.lock").read_text(encoding="utf-8"))
            assert holder["pid"] == os.getpid()      # same process, deliberately
            with pytest.raises(q.RunLockBusy):
                q.acquire_run_lock("loan_process", tmp_path)
        finally:
            first.release()

    def test_different_jobs_do_not_block_each_other(self, tmp_path):
        """Scanning while a form is being processed is fine and should not wait."""
        scan = q.acquire_run_lock("loan_scan", tmp_path)
        process = q.acquire_run_lock("loan_process", tmp_path)
        scan.release()
        process.release()

    def test_a_lock_left_by_a_dead_process_is_taken_over(self, tmp_path):
        """A CLI run killed mid-flight must not block the schedule for 20 minutes."""
        q.ensure_dirs(tmp_path)
        # pid 1 does not belong to a python process on Windows; psutil reports
        # whether it exists at all, which is what the staleness check asks.
        (tmp_path / "loan_process.lock").write_text(
            json.dumps({"token": "old", "pid": 999999999, "startedAt": "2026-01-01T00:00:00"}),
            encoding="utf-8")
        taken = q.acquire_run_lock("loan_process", tmp_path)
        taken.release()

    def test_an_expired_lock_is_taken_over(self, tmp_path):
        q.ensure_dirs(tmp_path)
        path = tmp_path / "loan_process.lock"
        path.write_text(json.dumps({"token": "old", "pid": os.getpid()}), encoding="utf-8")
        # ttl=0 makes any existing lock expired, whatever its mtime.
        taken = q.acquire_run_lock("loan_process", tmp_path, ttl=0)
        taken.release()

    def test_a_live_lock_from_another_process_is_respected(self, tmp_path):
        """The TTL must not be the only thing standing between two runs."""
        q.ensure_dirs(tmp_path)
        (tmp_path / "loan_process.lock").write_text(
            json.dumps({"token": "other", "pid": os.getpid()}), encoding="utf-8")
        # Fresh mtime + a live pid: nothing here says the holder is gone.
        with pytest.raises(q.RunLockBusy):
            q.acquire_run_lock("loan_process", tmp_path)

    def test_release_does_not_delete_a_lock_someone_else_took(self, tmp_path):
        """An overrunning run must not unlock the run that replaced it."""
        mine = q.acquire_run_lock("loan_process", tmp_path)
        path = tmp_path / "loan_process.lock"
        path.write_text(json.dumps({"token": "someone-else", "pid": os.getpid()}),
                        encoding="utf-8")
        mine.release()
        assert path.is_file()
        assert json.loads(path.read_text(encoding="utf-8"))["token"] == "someone-else"

    def test_the_busy_error_says_who_holds_it(self, tmp_path):
        first = q.acquire_run_lock("loan_process", tmp_path, owner="06b")
        try:
            with pytest.raises(q.RunLockBusy) as exc:
                q.acquire_run_lock("loan_process", tmp_path)
            assert str(os.getpid()) in str(exc.value)
            assert "already in progress" in str(exc.value)
        finally:
            first.release()


class TestScannerGates:
    """`run()` with the Bridge stubbed: what reaches the queue, and why not."""

    def _run(self, monkeypatch, tmp_path, messages, cfg=None):
        monkeypatch.setattr(q, "QUEUE_ROOT", tmp_path)

        class FakeBridge:
            def email_list(self, **kw):
                return {"messages": messages}

        monkeypatch.setattr(loan_scan, "_bridge", lambda: FakeBridge())
        # These fixtures are dated 2026-08-01 and these tests are about the
        # gates, not the cut-off. Without an explicit processFrom the first run
        # stamps "now" and every fixture falls before it -- so state the
        # precondition here rather than leave the gates untested behind it.
        full = {"processFrom": "2026-01-01 00:00", **(cfg or {})}
        return loan_scan.run({"_config": full, "dryRun": False}, log=lambda _m: None)

    # Realistic borrow numbers: the pattern requires six or more digits, so
    # "DR1" would be rejected by the parser before any gate is reached.
    A, B = "DR26270135", "DR26270136"

    def _mail(self, borrow, notice="簽核通知", entry="e1"):
        href = f"{PORTAL}?action=flow&amp;accessId={borrow}"
        return {
            "entryId": entry,
            "subject": f"{notice}--(展示機出借申請單 - 一般 {borrow} )",
            "senderEmail": "workflow@rohde-schwarz.com",
            "receivedTime": "2026-08-01T09:00:00",
            "htmlBody": f'<a href="{href}">{borrow}</a>',
        }

    def test_approvals_are_enqueued(self, monkeypatch, tmp_path):
        out = self._run(monkeypatch, tmp_path, [self._mail(self.A), self._mail(self.B, entry="e2")])
        assert out["enqueued"] == 2
        assert q.counts(tmp_path)["pending"] == 2

    def test_rejections_are_never_enqueued(self, monkeypatch, tmp_path):
        out = self._run(monkeypatch, tmp_path, [self._mail(self.A, notice="否決")])
        assert out["enqueued"] == 0
        assert out["skippedItems"][0]["reason"].startswith("rejection notice")

    def test_a_rejection_does_not_lock_out_the_approval(self, monkeypatch, tmp_path):
        """The decisive ordering test.

        8 of 118 forms carry both notices and the rejection is often the newer.
        If rejections were dropped *after* the dedupe, the rejection would claim
        the borrow number and the approval would be discarded as a duplicate --
        exactly backwards.
        """
        out = self._run(
            monkeypatch,
            tmp_path,
            [self._mail(self.A, notice="否決", entry="e1"),
             self._mail(self.A, notice="簽核通知", entry="e2")],
        )
        assert out["enqueued"] == 1
        assert [i["notice"] for i in out["enqueuedItems"]] == ["簽核通知"]

    def test_non_loan_mail_is_counted_separately_from_skips(self, monkeypatch, tmp_path):
        junk = {"entryId": "x", "subject": "Lunch", "htmlBody": "<p>hi</p>",
                "receivedTime": "2026-08-01T09:00:00"}
        out = self._run(monkeypatch, tmp_path, [junk, self._mail(self.A)])
        assert out["notLoanForms"] == 1
        assert out["skipped"] == 0

    def test_a_duplicate_borrow_number_is_reported_not_dropped(self, monkeypatch, tmp_path):
        out = self._run(
            monkeypatch, tmp_path,
            [self._mail(self.A, entry="e1"), self._mail(self.A, entry="e2")],
        )
        assert out["enqueued"] == 1 and out["skipped"] == 1
        assert "already queued" in out["skippedItems"][0]["reason"]

    def test_excluded_categories_are_skipped(self, monkeypatch, tmp_path):
        out = self._run(monkeypatch, tmp_path, [self._mail("DRS26270011")],
                        cfg={"excludeCategories": ["S"]})
        assert out["enqueued"] == 0
        assert "excluded" in out["skippedItems"][0]["reason"]

    def test_a_dry_run_writes_nothing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(q, "QUEUE_ROOT", tmp_path)
        messages = [self._mail(self.A)]  # bind outside: `self` inside FakeBridge is the fake

        class FakeBridge:
            def email_list(self, **kw):
                return {"messages": messages}

        monkeypatch.setattr(loan_scan, "_bridge", lambda: FakeBridge())
        out = loan_scan.run(
            {"_config": {"processFrom": "2026-01-01 00:00"}, "dryRun": True}, log=lambda _m: None
        )
        assert out["enqueued"] == 1
        assert q.counts(tmp_path)["pending"] == 0
