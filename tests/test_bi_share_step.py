"""What the 分享 step shows before it runs: the commits since the published version, with
author and domain, and each domain's test state. Fictional data only.

`docs/phases/BI_PAGE_SIMPLE.md` S6; the push check itself is `test_bi_domain_gate.py`.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import pytest
from test_bi_domain_gate import _bench, _question, _ready
from test_bi_vault import _call, _commit, _ok, _push, _two_pcs

from capabilities.bi_cards import domain_reach, vault
from host_runtime import bi_bench


@pytest.fixture(autouse=True)
def _no_gate() -> Any:
    vault.set_benchmark(None)
    yield
    vault.set_benchmark(None)


def _share(ws: Path, vault_id: str) -> Any:
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/share"))


def _states(plan: Any) -> dict[str, str]:
    return {item["home"]: item["state"] for item in plan["domains"]}


def test_it_lists_the_commits_since_the_published_version_with_author_and_domain(
    tmp_path: Path,
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    vault.set_benchmark(partial(bi_bench.gate, a))
    _question(a, vault_id, "aidc-q", "aidc")
    _commit(a, vault_id, "aidc 的題目")
    assert _push(a, vault_id)["status"] == "pushed"
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/tag", {"name": "2026-11-01", "purpose": "x"}))
    published = {"tag": "2026-11-01", "confirm": True}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/publish", published))

    _question(a, vault_id, "wl-q", "wireless")
    _commit(a, vault_id, "wireless 的題目")
    assert _push(a, vault_id)["status"] == "pushed"
    _question(a, vault_id, "whole", None)
    _commit(a, vault_id, "全庫的題目")  # only on this PC
    _question(a, vault_id, "aidc-2", "aidc")  # not committed

    plan = _share(a, vault_id)
    assert plan["published"]["tag"] == "2026-11-01"
    assert plan["tags"] == ["2026-11-01"]
    shown = [(c["purpose"], c["pushed"], c["homes"]) for c in plan["commits"]]
    # Newest first; the published one is not listed again.
    assert shown == [("全庫的題目", False, ["*"]), ("wireless 的題目", True, ["wireless"])]
    author = vault.Vault(a, vault_id).repo.author
    assert {c["author"] for c in plan["commits"]} == {author}
    assert plan["uncommitted"] == 1 and plan["uncommitted_homes"] == ["aidc"]
    assert plan["older"] == 0


def test_a_vault_never_published_lists_every_commit(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    before = len(vault.Vault(a, vault_id).repo.history(500))
    _question(a, vault_id, "aidc-q", "aidc")
    _commit(a, vault_id, "aidc 的題目")
    plan = _share(a, vault_id)
    assert plan["published"] is None
    assert len(plan["commits"]) == before + 1
    assert plan["commits"][0]["purpose"] == "aidc 的題目"
    assert plan["commits"][0]["homes"] == ["aidc"]


def test_each_domains_test_state_is_passed_regressed_or_untested(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    plan = _share(a, vault_id)
    assert plan["domains"] == [] and plan["running"] is False
    _ready(a, vault_id)
    assert _states(_share(a, vault_id)) == {"aidc": "untested", "wireless": "untested"}
    assert any("沒有跑過測試" in n for n in _share(a, vault_id)["standing"]["notes"])

    _bench(a, vault_id, ("wl-q",))
    plan = _share(a, vault_id)
    assert _states(plan) == {"aidc": "passed", "wireless": "regressed"}
    wireless = next(item for item in plan["domains"] if item["home"] == "wireless")
    assert wireless["regressed"] == ["虛構題 wl-q？"]
    assert (wireless["questions"], wireless["tested"], wireless["passed"]) == (1, 1, 0)
    # Nothing waits that touches wireless, so its regression is a note, not a block.
    assert plan["standing"]["blocking"] == []

    # A new aidc question the run did not see: aidc's content changed, so its run is an old
    # result there (acceptance F24), while wireless's still counts.
    _question(a, vault_id, "aidc-2", "aidc")
    assert _states(_share(a, vault_id)) == {"aidc": "stale", "wireless": "regressed"}


def test_a_regression_in_the_domain_a_share_touches_shows_as_blocking(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _question(a, vault_id, "aidc-2", "aidc")
    _commit(a, vault_id, "aidc 的新題目")
    _bench(a, vault_id, ("aidc-q",))
    plan = _share(a, vault_id)
    assert _states(plan)["aidc"] == "regressed"
    assert plan["standing"]["blocking"] and "（aidc）" in plan["standing"]["blocking"][0]
    # The push check is the same one: it still blocks.
    assert _push(a, vault_id)["status"] == "blocked"


def test_touched_looks_only_at_the_keys_given() -> None:
    before = {"meta:vault_segments": '[{"folder": "aidc"}, {"folder": "wireless"}]'}
    after = {**before, "source:a": {"folder": "applications/aidc/sources"}, "schema": "x"}
    assert domain_reach.touched(before, after) == domain_reach.ALL
    assert domain_reach.touched(before, after, ["source:a"]) == {"aidc"}


# -- acceptance F24: a result from before a publish or a change is an old result ---------------


def _publish(ws: Path, vault_id: str, name: str, version: str | None = None) -> None:
    """Tag `version` (the head by default) and publish it."""
    body = {"name": name, "purpose": "x", "version": version}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/tag", body))
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/publish", {"tag": name, "confirm": True}))


def _latest(ws: Path, vault_id: str) -> Any:
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/checks"))["latest"]


def test_a_run_says_which_published_version_it_compared_and_goes_old_on_a_publish(
    tmp_path: Path,
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _publish(a, vault_id, "2026-11-05")
    # Pushed, not yet published: the run compares it with 2026-11-05.
    _question(a, vault_id, "aidc-2", "aidc")
    _commit(a, vault_id, "aidc 的新題目")
    assert _push(a, vault_id)["status"] == "pushed"
    _bench(a, vault_id, ())
    report = bi_bench.reports(a, vault_id)[0]
    assert report["published"]["tag"] == "2026-11-05"
    latest = _latest(a, vault_id)
    assert latest["stale"]["stale"] is False
    assert latest["stale"]["compared"]["tag"] == "2026-11-05"
    assert _states(_share(a, vault_id)) == {"aidc": "passed", "wireless": "passed"}

    # Publishing the same commit again changes nothing the run compared.
    first = vault.Vault(a, vault_id).repo.tag_record("2026-11-05")
    assert first is not None
    _publish(a, vault_id, "2026-11-05-2", first["commit"])
    assert _latest(a, vault_id)["stale"]["stale"] is False
    # Publishing what was pushed since does: the run compared an older version.
    _publish(a, vault_id, "2026-11-06")
    stale = _latest(a, vault_id)["stale"]
    assert stale == {
        **stale,
        "stale": True,
        "published_changed": True,
        "content_changed": False,
    }
    assert stale["published_now"]["tag"] == "2026-11-06"
    assert _states(_share(a, vault_id)) == {"aidc": "stale", "wireless": "stale"}


def test_a_report_from_before_runs_recorded_the_version_goes_by_time(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    report = _bench(a, vault_id, ())
    del report["published"]
    report["started_at"] = "2026-11-06T04:14:00+08:00"
    bi_bench._save(a, vault_id, report)
    assert _latest(a, vault_id)["stale"]["stale"] is False  # never published
    _publish(a, vault_id, "2026-11-06.2")
    stale = _latest(a, vault_id)["stale"]
    assert stale["published_changed"] is True and stale["compared"] is None


def test_content_changed_since_the_run_is_an_old_result(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _bench(a, vault_id, ())
    _question(a, vault_id, "aidc-2", "aidc")
    stale = _latest(a, vault_id)["stale"]
    assert stale["content_changed"] is True and stale["published_changed"] is False
    # By domain: only aidc changed.
    assert _states(_share(a, vault_id)) == {"aidc": "stale", "wireless": "passed"}


def test_the_shares_one_replay_matches_the_repository_and_the_push_check(tmp_path: Path) -> None:
    # The route replays the commits once instead of loading the working copy three times
    # (ten seconds on market-intel); it must arrive at the same states and answers.
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _publish(a, vault_id, "2026-11-05")
    _question(a, vault_id, "wl-2", "wireless")
    _commit(a, vault_id, "pushed after the publish")
    assert _push(a, vault_id)["status"] == "pushed"
    _bench(a, vault_id, ("wl-q",))
    _question(a, vault_id, "aidc-2", "aidc")
    _commit(a, vault_id, "only on this PC")
    _question(a, vault_id, "aidc-3", "aidc")  # not committed
    _ok(
        _call(
            a, "POST", f"/api/bi/vaults/{vault_id}/checks", {"delete": "check:question:main/wl-q"}
        )
    )

    repo = vault.Vault(a, vault_id).repo
    state = vault.share_state(a, vault_id)
    assert state.head == repo.units()
    assert state.working == repo.working_units()
    published = repo.published()
    checked = bi_bench.share_check(a, state.head, state.working, state.changed, published)
    assert checked["domains"] == bi_bench.domain_states(a, repo.working_units(), published)
    assert checked["standing"] == bi_bench.standing(a, vault_id)
    assert state.plan["uncommitted"] == 2
    assert [c["purpose"] for c in state.plan["commits"]] == [
        "only on this PC",
        "pushed after the publish",
    ]
