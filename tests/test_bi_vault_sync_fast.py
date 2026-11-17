"""A BI vault sync with nothing new does no rebuild and reads no commit, and a
colleague's change still arrives. All data is fictional."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import (
    _call,
    _card,
    _commit,
    _Drive,
    _edit,
    _ok,
    _push,
    _row,
    _sync,
    _two_pcs,
)

from aep_bi.cards import analyses, card_model, feed, vault, vault_sources
from aep_bi.cards.store import BiStore, BiStoreError
from aep_bi.host import bi_feed_api
from knowledge.repo.repository import Repository
from scripts.bi_feed_fixtures import LATE_ANALYSIS


class _Counted:
    """Counts calls of what a quiet sync must not do."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.rebuilds = 0
        self.scans = 0
        self.staging = 0
        real_rebuild, real_scan = vault.Vault.rebuild, Repository.scan
        real_staging = vault_sources.sync_staging

        def rebuild(this: Any) -> None:
            self.rebuilds += 1
            real_rebuild(this)

        def scan(this: Any) -> Any:
            self.scans += 1
            return real_scan(this)

        def staging(*args: Any) -> Any:
            self.staging += 1
            return real_staging(*args)

        monkeypatch.setattr(vault.Vault, "rebuild", rebuild)
        monkeypatch.setattr(Repository, "scan", scan)
        monkeypatch.setattr(vault_sources, "sync_staging", staging)


def _shared(tmp_path: Path) -> tuple[_Drive, str, str, Path, Path]:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    BiStore(a, dataset).apply(
        [_row("TSN", standard_body="IEEE")],
        filename="t.csv",
        entity_type="Technology",
        actor="x via web",
    )
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    return drive, vault_id, dataset, a, b


def _quiet(ws: Path, vault_id: str) -> None:
    """Bring this PC to rest: what it had to catch up on is done."""
    vault.sync(ws, vault_id)
    vault.sync(ws, vault_id)


def test_nothing_new_is_no_rebuild_no_commit_read_and_no_feed_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, vault_id, _, a, _ = _shared(tmp_path)
    _quiet(a, vault_id)
    counted = _Counted(monkeypatch)
    refreshed: list[str] = []
    monkeypatch.setattr(bi_feed_api, "refresh", lambda _w, v: refreshed.append(v))
    answer = _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/sync", {}))
    assert answer["sync"]["applied"] == 0 and answer["sync"]["moved"] is False
    assert (counted.rebuilds, counted.scans, counted.staging) == (0, 0, 0)
    assert refreshed == []


def test_a_colleagues_commit_arrives_and_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive, vault_id, dataset, a, b = _shared(tmp_path)
    _quiet(b, vault_id)
    _ok(_edit(a, dataset, "TSN", "standard_body", "IETF", "alice"))
    _commit(a, vault_id, "a 的修改")
    _push(a, vault_id)
    assert _card(b, dataset, "TSN")["fields"]["standard_body"]["value"] == "IEEE"
    drive.deliver("a", "b", vault_id)
    counted = _Counted(monkeypatch)
    report = vault.sync(b, vault_id)
    assert report["applied"] == 1 and report["moved"] is True and counted.rebuilds == 1
    assert counted.staging == 1
    assert _card(b, dataset, "TSN")["fields"]["standard_body"]["value"] == "IETF"
    again = vault.sync(b, vault_id)
    assert again["applied"] == 0 and again["moved"] is False and counted.rebuilds == 1


def test_a_colleagues_publish_moves_the_feed_with_no_new_commit(tmp_path: Path) -> None:
    drive, vault_id, _, a, b = _shared(tmp_path)
    _quiet(b, vault_id)
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "v1", "purpose": "一"}))
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": "v1", "confirm": True}))
    drive.deliver("a", "b", vault_id)
    report = vault.sync(b, vault_id)
    assert report["moved"] is True
    assert vault.Vault(b, vault_id).reads()["tag"] == "v1"
    assert vault.sync(b, vault_id)["moved"] is False


def test_what_a_rebuild_reads_changing_here_still_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, vault_id, dataset, a, _ = _shared(tmp_path)
    _quiet(a, vault_id)
    target = vault.Vault(a, vault_id)
    counted = _Counted(monkeypatch)
    # Staged without a rebuild, as a change made outside a card write is.
    with target.lock:
        target.repo.stage("meta:note", "x")
    assert vault.sync(a, vault_id)["moved"] is True
    assert counted.rebuilds == 1
    # A local commit of it.
    _commit(a, vault_id, "備註")
    vault.sync(a, vault_id)
    assert counted.rebuilds >= 2
    settled = counted.rebuilds
    assert vault.sync(a, vault_id)["moved"] is False and counted.rebuilds == settled
    # A database gone, or built by an older model.
    target.db_path.unlink()
    vault.sync(a, vault_id)
    assert counted.rebuilds == settled + 1
    assert BiStore(a, dataset).find("Technology", "TSN") is not None
    monkeypatch.setattr(card_model, "MODEL_VERSION", card_model.MODEL_VERSION + 1)
    vault.sync(a, vault_id)
    assert counted.rebuilds > settled + 1


def test_a_commit_that_vanished_or_changed_is_still_seen(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _shared(tmp_path)
    _quiet(b, vault_id)
    commits = drive.parent("b") / vault_id / "commits"
    newest = max(commits.rglob("*.json"), key=lambda p: (p.parent.name, int(p.stem)))
    assert newest.is_file()
    kept = newest.read_bytes()
    newest.unlink()
    assert vault.sync(b, vault_id)["rebuilt"] is True
    assert BiStore(b, dataset).find("Technology", "TSN") is None
    newest.write_bytes(kept)
    assert vault.sync(b, vault_id)["applied"] >= 1
    assert _card(b, dataset, "TSN")["fields"]["standard_body"]["value"] == "IEEE"


def test_a_file_a_commit_names_going_missing_is_still_seen(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _shared(tmp_path)
    body = {"dataset": dataset, "name": "fict.md", "text": "虛構來源"}
    _ok(_call(a, "POST", "/api/bi/sources", body))
    _commit(a, vault_id, "來源")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _quiet(b, vault_id)
    assert vault.sync(b, vault_id)["waiting"] == []
    folder = drive.parent("b") / vault_id
    named = [p for p in folder.rglob("*fict*") if p.is_file()]
    assert named
    named[0].unlink()
    report = vault.sync(b, vault_id)
    assert report["waiting"] or report["changed"]


class _Watched(threading.Event):
    """Counts who is waiting, so a test can know the joiners have joined."""

    waiting = 0

    def wait(self, timeout: float | None = None) -> bool:
        type(self).waiting += 1
        return super().wait(timeout)


def test_concurrent_syncs_share_one_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, vault_id, _, a, _ = _shared(tmp_path)
    release, started = threading.Event(), threading.Event()
    runs: list[int] = []

    def slow(_this: Any) -> dict[str, Any]:
        runs.append(1)
        started.set()
        assert release.wait(30)
        return {"applied": 0, "moved": False}

    made = vault._Flight
    monkeypatch.setattr(vault.Vault, "sync", slow)
    monkeypatch.setattr(vault, "_Flight", lambda: made(done=_Watched()))
    _Watched.waiting = 0
    answers: list[dict[str, Any]] = []

    def call() -> None:
        answers.append(vault.sync(a, vault_id))

    first = threading.Thread(target=call)
    first.start()
    assert started.wait(30)
    joining = [threading.Thread(target=call) for _ in range(3)]
    for thread in joining:
        thread.start()
    deadline = time.monotonic() + 30
    while _Watched.waiting < 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert _Watched.waiting == 3
    release.set()
    for thread in [first, *joining]:
        thread.join(30)
    assert len(runs) == 1 and answers == [{"applied": 0, "moved": False}] * 4
    assert not vault._FLIGHTS


def test_a_joiner_gets_the_leaders_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, vault_id, _, a, _ = _shared(tmp_path)

    def broken(_this: Any) -> dict[str, Any]:
        raise BiStoreError("vault_unreachable", "拿不到")

    monkeypatch.setattr(vault.Vault, "sync", broken)
    with pytest.raises(BiStoreError):
        vault.sync(a, vault_id)
    assert not vault._FLIGHTS  # the next call starts over


def test_listing_the_defaults_replays_the_version_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, vault_id, _, a, _ = _shared(tmp_path)
    analyses.save(a, vault_id, LATE_ANALYSIS)
    _commit(a, vault_id, "分析")
    _push(a, vault_id)
    calls = []
    real = Repository.state_at

    def counted(this: Any, target: str) -> Any:
        calls.append(target)
        return real(this, target)

    monkeypatch.setattr(Repository, "state_at", counted)
    monkeypatch.setattr(feed, "enqueue", lambda *_a, **_k: None)
    feed._UNITS.clear()
    assert feed.enqueue_defaults(a, vault_id) > 0
    assert len(calls) == 1


def test_a_new_version_is_not_served_from_the_kept_units(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _shared(tmp_path)
    feed._UNITS.clear()
    before = feed.listing(a, vault_id)["version"]["commit"]
    _ok(_edit(a, dataset, "TSN", "standard_body", "IETF", "alice"))
    _commit(a, vault_id, "改")
    _push(a, vault_id)
    assert feed.listing(a, vault_id)["version"]["commit"] != before
