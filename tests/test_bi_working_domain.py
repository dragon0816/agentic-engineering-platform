"""The BI page's working domain, its backend (`docs/phases/BI_PAGE_SIMPLE.md` §9).

A question may name a home; a bench may cover one and says what it left out; and a run of one
domain must never hide a regression another run found on the same content.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _commit, _ok, _push, _refused, _two_pcs

from capabilities.bi_cards import homes, sessions, vault
from capabilities.bi_cards.store import BiStoreError
from host_runtime import bi_bench

AIDC_Q: dict[str, Any] = {
    "question": "虛構 AIDC 題？",
    "must": ["好"],
    "slug": "aidc",
    "home": "aidc",
}
WIRELESS_Q: dict[str, Any] = {
    "question": "虛構 wireless 題？",
    "must": ["好"],
    "slug": "wl",
    "home": "wireless",
}
WHOLE_Q: dict[str, Any] = {"question": "虛構全庫題？", "must": ["好"], "slug": "whole"}


@pytest.fixture(autouse=True)
def _no_gate() -> Any:
    vault.set_benchmark(None)
    yield
    vault.set_benchmark(None)


def _save(ws: Path, vault_id: str, body: dict[str, Any]) -> Any:
    return _call(ws, "POST", f"/api/bi/vaults/{vault_id}/checks", body)


def _checks(ws: Path, vault_id: str) -> dict[str, Any]:
    return _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/checks"))


def _three(ws: Path, vault_id: str) -> None:
    for question in (AIDC_Q, WIRELESS_Q, WHOLE_Q):
        _ok(_save(ws, vault_id, question))


def _bench(ws: Path, vault_id: str, working_wrong: tuple[str, ...], home: str | None) -> Any:
    def ask(question: str, side: bi_bench.Side) -> dict[str, Any]:
        wrong = side == "working" and any(word in question for word in working_wrong)
        return {"ok": True, "answer": "不知道" if wrong else "好"}

    report = bi_bench.run(ws, vault_id, ask=ask, extract=lambda c: [], actor="alice", home=home)
    assert report["status"] == "finished", report
    return report


# -- a question's home -----------------------------------------------------------------------


def test_a_question_keeps_its_home_and_one_without_stays_as_it_was(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _three(a, vault_id)
    found = {q["slug"]: q for q in _checks(a, vault_id)["questions"]}
    assert found["aidc"]["home"] == "aidc"
    assert found["whole"]["home"] is None
    units = vault.Vault(a, vault_id).repo.working_units()
    # An untagged question's unit is what it always was, so no digest moves.
    assert "home" not in units[found["whole"]["unit"]]
    assert units[found["aidc"]["unit"]]["home"] == "aidc"


def test_a_library_entry_can_be_a_questions_home(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ok(_save(a, vault_id, {"question": "虛構？", "home": "library/products"}))
    assert _checks(a, vault_id)["questions"][0]["home"] == "library/products"


@pytest.mark.parametrize("home", ["../x", "AIDC", "library/skills", "a/b"])
def test_a_home_that_is_no_home_is_refused(tmp_path: Path, home: str) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _refused(_save(a, vault_id, {"question": "虛構？", "home": home}), 400, "question_invalid")


# -- a bench of one domain -------------------------------------------------------------------


def test_a_bench_of_a_home_covers_it_and_the_whole_vaults_and_says_what_it_left(
    tmp_path: Path,
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _three(a, vault_id)
    report = _bench(a, vault_id, (), "aidc")
    assert report["scope"] == "aidc"
    assert sorted(r["question"] for r in report["results"]) == sorted(
        [AIDC_Q["question"], WHOLE_Q["question"]]
    )
    assert report["total"] == 2
    assert [u.rpartition("/")[2] for u in report["not_covered"]] == ["wl"]

    whole = _bench(a, vault_id, (), None)
    assert whole["scope"] == "" and whole["not_covered"] == [] and whole["total"] == 3


def test_a_case_counts_for_the_home_of_its_folder(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    units = vault.Vault(a, vault_id).repo
    expected = {"format": "aep.bi.benchmark.expected/v1", "types": [], "candidates": []}
    for slug, folder in (("mine", "applications/aidc/sources/deep"), ("other", None)):
        units.stage(
            f"check:extract:{slug}", {"note": "虛構", "folder": folder, "expected": expected}
        )
    units.stage(
        "check:extract:theirs",
        {"note": "虛構", "folder": homes.sources_dir("wireless"), "expected": expected},
    )
    report = _bench(a, vault_id, (), "aidc")
    assert sorted(c["slug"] for c in report["cases"]) == ["mine", "other"]
    assert report["not_covered"] == ["check:extract:theirs"]


def test_starting_a_bench_with_nothing_in_that_home_says_so(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _ok(_save(a, vault_id, WIRELESS_Q))
    refused = _call(a, "POST", f"/api/bi/vaults/{vault_id}/bench", {"home": "aidc"})
    _refused(refused, 400, "bench_empty")
    _refused(
        _call(a, "POST", f"/api/bi/vaults/{vault_id}/bench", {"home": "../x"}), 400, "home_invalid"
    )


# -- the gate: never weakened by a smaller run -------------------------------------------------


def _pushable(a: Path, vault_id: str) -> None:
    vault.set_benchmark(partial(bi_bench.gate, a))
    _three(a, vault_id)
    _commit(a, vault_id, "加上測試題")


def test_a_run_of_one_domain_does_not_hide_a_regression_in_another(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _pushable(a, vault_id)
    _bench(a, vault_id, ("wireless",), None)
    # Newer, on the same content, and all green: it did not ask the wireless question.
    newer = _bench(a, vault_id, (), "aidc")
    assert newer["regressions"] == []

    blocked = _push(a, vault_id)
    assert blocked["status"] == "blocked"
    assert len(blocked["blocking"]) == 1
    assert "（wireless）" in blocked["blocking"][0] and "虛構 wireless 題" in blocked["blocking"][0]

    # The person in aidc sees it before pressing push, whatever their last report says.
    standing = _checks(a, vault_id)["standing"]
    assert standing["blocking"] == blocked["blocking"]
    assert _checks(a, vault_id)["latest"]["run_id"] == newer["run_id"]


def test_a_regression_clears_only_when_that_question_passes_again(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _pushable(a, vault_id)
    _bench(a, vault_id, ("wireless",), "wireless")
    _bench(a, vault_id, (), "aidc")
    assert _checks(a, vault_id)["standing"]["blocking"]
    _bench(a, vault_id, (), "wireless")
    assert _checks(a, vault_id)["standing"]["blocking"] == []
    pushed = _push(a, vault_id)
    assert pushed["status"] == "pushed"
    assert any("3/3 題通過" in note for note in pushed["notes"]), pushed["notes"]


def test_a_later_regression_in_the_same_question_blocks_again(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _pushable(a, vault_id)
    _bench(a, vault_id, (), None)
    _bench(a, vault_id, ("AIDC",), "aidc")
    blocked = _push(a, vault_id)
    assert blocked["status"] == "blocked" and "（aidc）" in blocked["blocking"][0]


def test_a_regression_in_a_whole_vault_question_names_no_domain(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _pushable(a, vault_id)
    _bench(a, vault_id, ("全庫",), None)
    blocked = _push(a, vault_id)
    assert blocked["blocking"][0].startswith("測試退步：")


def test_a_push_after_part_of_the_questions_goes_with_a_note_of_how_many_were_not(
    tmp_path: Path,
) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _pushable(a, vault_id)
    _bench(a, vault_id, (), "aidc")
    pushed = _push(a, vault_id)
    assert pushed["status"] == "pushed"
    note = " ".join(pushed["notes"])
    assert "2/2 題通過" in note and "1 題" in note and "沒有測" in note


def test_a_colleagues_content_makes_an_earlier_run_not_count(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _pushable(a, vault_id)
    _bench(a, vault_id, ("wireless",), None)
    assert _checks(a, vault_id)["standing"]["blocking"]
    _ok(_save(a, vault_id, {"question": "別人加的題？", "slug": "colleague", "must": ["好"]}))
    standing = _checks(a, vault_id)["standing"]
    assert standing["blocking"] == []
    assert any("沒有跑過測試" in note for note in standing["notes"])


# -- which homes a change touches --------------------------------------------------------------


def test_the_list_of_changes_says_which_homes_each_touches(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    _three(a, vault_id)
    pending = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/pending"))
    touched = {change["unit"]: change["homes"] for change in pending["uncommitted"]}
    assert touched["check:question:main/aidc"] == ["aidc"]
    assert touched["check:question:main/wl"] == ["wireless"]
    assert touched["check:question:main/whole"] == []


def test_each_kind_of_unit_has_its_homes() -> None:
    units = {
        "source:s1": {"folder": "applications/aidc/sources/deep"},
        "source:s2": {"folder": "sources"},
        "check:extract:c": {"folder": "library/products/sources"},
    }
    cards = {"c1": ["aidc", "wireless"]}
    found = {key: vault.unit_homes(units, key, cards) for key in (
        "source:s1", "source:s2", "check:extract:c", "card:c1", "field:c1:name", "card:none",
        "skill:classify", "skill:aidc/rule", "skill:library/products/rule",
        "tool:wireless/parse", "profile:library/products", "profile:aidc", "meta:dashboard",
    )}  # fmt: skip
    assert found == {
        "source:s1": ["aidc"],
        "source:s2": [],
        "check:extract:c": ["library/products"],
        "card:c1": ["aidc", "wireless"],
        "field:c1:name": ["aidc", "wireless"],
        "card:none": [],
        "skill:classify": [],
        "skill:aidc/rule": ["aidc"],
        "skill:library/products/rule": ["library/products"],
        "tool:wireless/parse": ["wireless"],
        "profile:library/products": ["library/products"],
        "profile:aidc": ["aidc"],
        "meta:dashboard": [],
    }


def test_the_vault_lists_its_homes_with_their_folder_and_domain(tmp_path: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    reply = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/skills"))
    listed = {item["home"]: item for item in reply["homes"]}
    assert listed["library/products"]["folder"] == "library/products/sources"
    assert listed["library/products"]["domain"] is None
    for item in reply["homes"]:
        assert item["folder"] == homes.sources_dir(item["home"])


# -- the AI panel ------------------------------------------------------------------------------


def test_a_turn_in_a_working_domain_says_so_without_counting_against_the_person() -> None:
    said = sessions.scoped("x" * sessions.MAX_MESSAGE, "aidc")
    assert said.startswith(sessions.SCOPE_PREFIX + "aidc")
    assert "applications/aidc/sources" in said
    assert said.endswith("x" * sessions.MAX_MESSAGE)
    assert sessions.check_message(said) == said
    assert sessions.scoped("問題", None) == "問題"
    with pytest.raises(BiStoreError):
        sessions.scoped("x" * (sessions.MAX_MESSAGE + 1), "aidc")
    with pytest.raises(BiStoreError):
        sessions.scoped("問題", "../x")
