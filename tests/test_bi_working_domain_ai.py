"""A session opened in a working domain tells the model so (`docs/phases/BI_PAGE_SIMPLE.md` §9.6).

Through the route, on the kinds that use no gateway here: what reaches the session is the person's
words after one line naming the home, and an invalid home is refused before anything is stored.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_vault import _call, _ok, _refused, _two_pcs

from capabilities.bi_cards import questions_session, sessions
from capabilities.bi_cards.staging import Staging
from host_runtime import bi_cards_api


class _Bench:
    """A questions turn with its asker in place of the Agent harness."""

    def __init__(self) -> None:
        self.turns: list[Any] = []

    def questions_asker_for(self, _dataset: str, _actor: str) -> Any:
        def ask(_context: str, turns: list[Any], _check: Any) -> Any:
            self.turns = turns
            answer = {"reply": "虛構", "reasons": [], "questions": [
                {"question": "虛構題？", "must": ["虛構"], "must_not": [], "slug": "q-new"}
            ]}  # fmt: skip
            return sessions.Asked(answer=answer, attempts=1), "fake", []

        return ask


def test_a_questions_session_names_the_domain_and_its_questions_take_it(
    tmp_path: Path, monkeypatch: Any
) -> None:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    monkeypatch.setattr(questions_session, "check_proposal", lambda *args, **kwargs: [])
    made = _ok(
        _call(a, "POST", "/api/bi/sessions", {"dataset": dataset, "kind": "questions",
                                              "target": "main"})
    )  # fmt: skip
    session_id = made["session"]["id"]
    bench = _Bench()
    turned = bi_cards_api._session_write(
        a,
        "alice",
        session_id,
        "turns",
        {"dataset": dataset, "message": "出一題", "scope": "aidc"},
        None,
        bench,
        "alice",
    )
    assert turned[0] == 200
    said = bench.turns[-1]["text"]
    assert said.startswith("工作領域：aidc") and "applications/aidc/sources" in said
    assert said.endswith("出一題")

    stored = sessions.load(Staging(a, dataset), session_id)
    index = next(i for i, t in enumerate(stored["turns"]) if t["role"] != "user")
    applied = bi_cards_api._session_write(
        a,
        "alice",
        session_id,
        "apply",
        {"dataset": dataset, "turn": index, "picks": [0], "home": "aidc"},
        None,
        bench,
        "alice",
    )
    assert applied[0] == 200
    checks = _ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/checks"))
    assert [q["home"] for q in checks["questions"]] == ["aidc"]


def test_a_scope_that_is_no_home_stores_nothing(tmp_path: Path) -> None:
    _drive, _vault_id, dataset, a, _b = _two_pcs(tmp_path)
    made = _ok(
        _call(a, "POST", "/api/bi/sessions", {"dataset": dataset, "kind": "questions",
                                              "target": "main"})
    )  # fmt: skip
    refused = _call(
        a,
        "POST",
        f"/api/bi/sessions/{made['session']['id']}/turns",
        {"dataset": dataset, "message": "出一題", "scope": "../x"},
    )
    _refused(refused, 400, "home_invalid")
    assert sessions.load(Staging(a, dataset), made["session"]["id"])["turns"] == []
