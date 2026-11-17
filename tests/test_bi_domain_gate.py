"""A push is held back by what it touches, and a test counts for its domain's content.

Owner, 2026-11-05: 「這是一個多人合作的平台，但為了不彼此干擾，每一個domain會有專人來處理」.
`docs/phases/BI_PAGE_SIMPLE.md` §14.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _import, _ok, _push, _refused, _row, _sync, _two_pcs

from aep_bi.cards import domain_reach, vault
from aep_bi.cards.store import BiStore
from aep_bi.host import bi_bench

ALL = domain_reach.ALL


@pytest.fixture(autouse=True)
def _no_gate() -> Any:
    vault.set_benchmark(None)
    yield
    vault.set_benchmark(None)


def _question(ws: Path, vault_id: str, slug: str, home: str | None) -> None:
    body = {"question": f"虛構題 {slug}？", "must": ["好"], "slug": slug, "home": home}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/checks", body))


def _bench(ws: Path, vault_id: str, wrong: tuple[str, ...], home: str | None = None) -> Any:
    def ask(question: str, side: bi_bench.Side) -> dict[str, Any]:
        bad = side == "working" and any(word in question for word in wrong)
        return {"ok": True, "answer": "不知道" if bad else "好"}

    report = bi_bench.run(ws, vault_id, ask=ask, extract=lambda c: [], actor="alice", home=home)
    assert report["status"] == "finished", report
    return report


def _ready(a: Path, vault_id: str) -> None:
    """Two domains' questions, pushed, so what comes next is the only change."""
    vault.set_benchmark(partial(bi_bench.gate, a))
    _question(a, vault_id, "aidc-q", "aidc")
    _question(a, vault_id, "wl-q", "wireless")
    _commit(a, vault_id, "題目")
    assert _push(a, vault_id)["status"] == "pushed"


# -- the push check ----------------------------------------------------------------------------


def test_a_regression_elsewhere_is_a_note_and_does_not_stop_this_domains_push(
    tmp_path: Path,
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _bench(a, vault_id, ("wl-q",))
    _question(a, vault_id, "aidc-2", "aidc")
    _commit(a, vault_id, "aidc 的新題目")
    pushed = _push(a, vault_id)
    assert pushed["status"] == "pushed", pushed
    assert any("其他領域，不擋" in n and "（wireless）" in n for n in pushed["notes"]), pushed


def test_a_regression_in_the_domain_touched_still_blocks(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _question(a, vault_id, "aidc-2", "aidc")
    _commit(a, vault_id, "aidc 的新題目")
    _bench(a, vault_id, ("aidc-q",))
    blocked = _push(a, vault_id)
    assert blocked["status"] == "blocked" and "（aidc）" in blocked["blocking"][0]


def test_a_shared_change_is_blocked_by_a_regression_anywhere(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _question(a, vault_id, "whole", None)  # no domain: it reaches them all
    _commit(a, vault_id, "全庫的題目")
    _bench(a, vault_id, ("wl-q",))
    blocked = _push(a, vault_id)
    assert blocked["status"] == "blocked" and "（wireless）" in blocked["blocking"][0]


def test_a_regression_in_a_question_of_no_domain_blocks_any_push(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    vault.set_benchmark(partial(bi_bench.gate, a))
    _question(a, vault_id, "whole", None)
    _commit(a, vault_id, "全庫的題目")
    _push(a, vault_id)
    _question(a, vault_id, "aidc-q", "aidc")
    _commit(a, vault_id, "aidc")
    _bench(a, vault_id, ("whole",))
    assert _push(a, vault_id)["status"] == "blocked"


def test_step_3_says_what_a_push_would_do_for_these_changes(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _bench(a, vault_id, ("wl-q",))
    _question(a, vault_id, "aidc-2", "aidc")
    standing = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/checks"))["standing"]
    assert standing["blocking"] == []
    assert any("其他領域，不擋" in n for n in standing["notes"])


# -- a test counts for its domain's content ----------------------------------------------------


def test_a_colleagues_push_in_another_domain_does_not_void_a_run(tmp_path: Path) -> None:
    drive, vault_id, _dataset, a, b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    # Alice tests aidc: a regression, so her push of it must block.
    _bench(a, vault_id, ("aidc-q",), "aidc")
    _question(a, vault_id, "aidc-2", "aidc")  # her content in aidc changes after it... so:
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/checks",
              {"delete": "check:question:main/aidc-2"}))  # fmt: skip

    # Bob pushes in wireless; it reaches her on sync.
    _question(b, vault_id, "wl-2", "wireless")
    _commit(b, vault_id, "wireless 的新題目")
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)
    _sync(a, vault_id)

    # Her aidc run still counts for aidc, though the vault's digest moved.
    report = bi_bench.reports(a, vault_id)[0]
    units = vault.Vault(a, vault_id).repo.working_units()
    assert report["units_sha256"] != bi_bench.units_digest(units)
    assert report["digests"]["aidc"] == domain_reach.digests(units, ["aidc"])["aidc"]
    assert report["digests"]["wireless"] != domain_reach.digests(units, ["wireless"])["wireless"]
    standing = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/checks"))["standing"]
    assert "沒有跑過測試" not in " ".join(standing["notes"])


def test_a_shared_change_voids_every_domains_run(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    _bench(a, vault_id, ())
    before = bi_bench.reports(a, vault_id)[0]["digests"]
    _question(a, vault_id, "whole", None)
    units = vault.Vault(a, vault_id).repo.working_units()
    now = domain_reach.digests(units, ["aidc", "wireless"])
    assert now["aidc"] != before["aidc"] and now["wireless"] != before["wireless"]


def test_a_report_from_before_this_counts_only_for_the_same_content(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ready(a, vault_id)
    report = _bench(a, vault_id, ("aidc-q",))
    del report["digests"]
    bi_bench._save(a, vault_id, report)
    units = vault.Vault(a, vault_id).repo.working_units()
    assert bi_bench.gate(a, units, units).notes[0].startswith("測試")
    _question(a, vault_id, "new", "wireless")
    units = vault.Vault(a, vault_id).repo.working_units()
    assert "沒有跑過測試" in bi_bench.gate(a, {}, units).notes[0]


# -- 定案 ----------------------------------------------------------------------------------------


def _finalize(ws: Path, vault_id: str, card: str, value: str, reason: str = "會議決定") -> Any:
    body = {"card": card, "field": "standard_body", "value": value, "reason": reason}
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/finalize", body)


def _card(ws: Path, dataset: str) -> Any:
    store = BiStore(ws, dataset)
    row = next(r for r in store.card_rows() if r["canonical_key"] == "TSN")
    return store, row["id"]


def test_finalizing_wins_over_a_racing_edit_and_keeps_what_it_replaced(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"), filename="seed.csv")
    _push(a, vault_id)
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    # A colleague's differing value reaches the shared folder first.
    _import(b, dataset, _row("TSN", standard_body="ITU"), filename="b.csv")
    assert _push(b, vault_id)["status"] == "pushed"
    drive.deliver("b", "a", vault_id)

    store, card = _card(a, dataset)
    reply = _ok(_finalize(a, vault_id, card, "ETSI", "11-05 會議決定"))
    assert reply["field"] == "standard_body"
    _commit(a, vault_id, "定案 TSN 的標準組織")
    pushed = _push(a, vault_id)
    assert pushed["status"] == "pushed", pushed

    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    for ws in (a, b):
        found, card = _card(ws, dataset)
        assert found.fields(card)["standard_body"]["value"] == "ETSI"
    # Nobody's history is erased: the replaced value, who and why are there.
    history = BiStore(b, dataset).history(card)
    assert any("定案：11-05 會議決定" in str(h.get("reason")) for h in history), history
    assert any(str(h.get("old")) in ("ITU", '"ITU"') for h in history), history


def test_finalizing_closes_open_proposals_on_that_field_only(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE", summary="虛構"), filename="seed.csv")
    store, card = _card(a, dataset)
    version = int(store.card(card)["version"])
    store.set_field(card, "standard_body", "IEEE", base_version=version, actor="x", reason="人工")
    _import(a, dataset, _row("TSN", standard_body="ITU", summary="虛構"), filename="b.csv")
    fields = [p["field"] for p in store.proposals(card)]
    reply = _ok(_finalize(a, vault_id, card, "ETSI"))
    assert reply["closed"] == fields.count("standard_body")
    assert [p for p in store.proposals(card) if p["field"] == "standard_body"] == []
    assert store.fields(card)["standard_body"]["value"] == "ETSI"


def test_finalizing_needs_a_reason_and_a_real_field(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    _import(a, dataset, _row("TSN", standard_body="IEEE"), filename="seed.csv")
    store, card = _card(a, dataset)
    _refused(_finalize(a, vault_id, card, "ETSI", "  "), 400, "reason_required")
    _refused(_finalize(a, vault_id, "none", "ETSI"), 404, "card_unknown")
    assert store.fields(card)["standard_body"]["value"] == "IEEE"


def test_a_finalized_push_is_still_blocked_by_a_regression_in_its_domain(tmp_path: Path) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    vault.set_benchmark(partial(bi_bench.gate, a))
    _import(a, dataset, _row("TSN", standard_body="IEEE", domain=["robotics"]), filename="seed.csv")
    _question(a, vault_id, "r-q", "robotics")
    _commit(a, vault_id, "題目")
    assert _push(a, vault_id)["status"] == "pushed"
    _store, card = _card(a, dataset)
    _ok(_finalize(a, vault_id, card, "ETSI"))
    _commit(a, vault_id, "定案")
    _bench(a, vault_id, ("r-q",))
    assert _push(a, vault_id)["status"] == "blocked"


# -- where a unit reaches ----------------------------------------------------------------------


UNITS: dict[str, Any] = {
    "meta:vault_segments": '[{"folder": "aidc"}, {"folder": "wireless"}, {"folder": "robotics"}]',
    "field:c1:domain": {"value": ["AIDC"]},
    "field:c2:domain": {"value": ["AIDC", "wireless"]},
    "field:c3:domain": {"value": "mobile"},
    "card:c1": {"type": "T", "key": "k", "name": "n"},
    "card:c4": {"type": "T", "key": "k", "name": "n"},
    "source:a": {"folder": "applications/aidc/sources"},
    "source:l": {"folder": "library/products/sources"},
    "source:r": {"folder": "sources"},
    "check:question:main/a": {"question": "?", "home": "aidc"},
    "check:question:main/w": {"question": "?"},
    "check:extract:a": {"note": "n", "folder": "applications/wireless/sources"},
    "relation:ab": {"from": "c1", "to": "c2"},
    "relation:ax": {"from": "c1", "to": "c4"},
    "proposal:p": {"card": "c1"},
    "meta:home:auto": "{}",
}


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("card:c1", {"aidc"}),
        ("field:c1:name", {"aidc"}),
        ("evidence:c1:name", {"aidc"}),
        ("state:c1:name", {"aidc"}),
        ("field:c2:name", {"aidc", "wireless"}),
        ("source:a", {"aidc"}),
        ("check:question:main/a", {"aidc"}),
        ("check:extract:a", {"wireless"}),
        ("skill:aidc/rule", {"aidc"}),
        ("tool:wireless/parse", {"wireless"}),
        ("profile:aidc", {"aidc"}),
        ("meta:dashboard:aidc", {"aidc"}),
        ("meta:home:auto", {"auto"}),
        ("relation:ab", {"aidc", "wireless"}),
        ("proposal:p", {"aidc"}),
        ("import:i", set()),
        # Shared, or what cannot be placed, is everyone's.
        ("field:c3:name", ALL),
        ("card:c4", ALL),
        ("relation:ax", ALL),
        ("source:l", ALL),
        ("source:r", ALL),
        ("source:gone", ALL),
        ("check:question:main/w", ALL),
        ("skill:classify", ALL),
        ("skill:library/products/rule", ALL),
        ("profile:library/products", ALL),
        ("schema", ALL),
        ("schema_change:domain:x", ALL),
        ("analysis:x", ALL),
        ("meta:dashboard", ALL),
        ("meta:anything", ALL),
        ("relation_evidence:x", ALL),
        ("decision:x", ALL),
        ("unheard:of", ALL),
    ],
)
def test_where_a_unit_reaches(key: str, expected: Any) -> None:
    reach = domain_reach.Reach(UNITS)
    assert reach.unit(key) == (expected if expected is ALL else frozenset(expected))


def test_moving_a_card_between_domains_reaches_both() -> None:
    after = {**UNITS, "field:c1:domain": {"value": ["wireless"]}}
    assert domain_reach.touched(UNITS, after) == {"aidc", "wireless"}


def test_no_change_reaches_nothing() -> None:
    assert domain_reach.touched(UNITS, dict(UNITS)) == frozenset()
