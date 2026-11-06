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

    # A new aidc question the run did not see: aidc's content changed, so its run no longer
    # counts there, while wireless's still does.
    _question(a, vault_id, "aidc-2", "aidc")
    assert _states(_share(a, vault_id)) == {"aidc": "untested", "wireless": "regressed"}


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
