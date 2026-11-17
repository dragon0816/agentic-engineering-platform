"""A new card from a reading run takes its source folder's domain, and the model's guess does
not replace it (acceptance F10, 2026-11-06). A source in `applications/marine/sources` of a
domain created on this PC gave a card of domain `wireless`. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok, _two_pcs

from aep_bi.cards.store import BiStore
from aep_bi.host.bi_cards_api import route

KIND = "Signal"
QUOTE = "虛構船廠採用新的衛星模組"
NOTE = f"# 虛構\n\n日期：2026-10-01\n\n{QUOTE}。\n"


def _post(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _signal(**more: Any) -> dict[str, Any]:
    fields = {
        "title": {"value": QUOTE, "basis": "fact", "quote": QUOTE},
        "date": {"value": "2026-10-01", "basis": "fact", "quote": "日期：2026-10-01"},
        "summary": {"value": QUOTE, "basis": "fact", "quote": QUOTE},
        "so_what": {"value": "虛構的影響", "basis": "inference", "reason": "虛構"},
        "source": {"value": "虛構筆記", "basis": "fact", "quote": QUOTE},
        **more,
    }
    return {"entity_type": KIND, "name": QUOTE, "fields": fields}


def _run(ws: Path, dataset: str, folder: str, answer: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    body = {"dataset": dataset, "name": "note.md", "text": NOTE, "folder": folder}
    source = _ok(_post(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    start = {"dataset": dataset, "kind": "ingest", "source_id": source, "types": [KIND]}
    run = _ok(_post(ws, "/api/bi/runs", start, _runtime(Scripted({"candidates": [answer]}), jobs)))
    jobs.run_all()
    run_id = str(run["run"]["id"])
    detail = _ok(_call(ws, "GET", f"/api/bi/runs/{run_id}", dataset=dataset))
    (candidate,) = detail["candidates"]
    return run_id, dict(candidate)


def _candidate(ws: Path, dataset: str, folder: str, answer: dict[str, Any]) -> dict[str, Any]:
    return _run(ws, dataset, folder, answer)[1]


def _domain(candidate: dict[str, Any]) -> list[Any]:
    """Every domain value the candidate carries, whether the type's field is one or a list."""
    found: list[Any] = []
    for item in candidate["fields"]:
        if item["field"] == "domain":
            value = item["value"]
            found.extend(value if isinstance(value, list) else [value])
    return found


def _created(tmp_path: Path) -> tuple[Path, str]:
    _drive, vault_id, dataset, a, _b = _two_pcs(tmp_path)
    body = {"name": "海事", "folder": "marine"}
    _ok(_call(a, "POST", f"/api/bi/vaults/{vault_id}/homes", body))
    return a, dataset


def test_a_card_from_a_created_domain_takes_it(tmp_path: Path) -> None:
    a, dataset = _created(tmp_path)
    candidate = _candidate(a, dataset, "applications/marine/sources", _signal())
    assert _domain(candidate) == ["marine"]


def _proposed(candidate: dict[str, Any]) -> list[Any]:
    (item,) = [f for f in candidate["fields"] if f["field"] == "domain"]
    return [a["value"] for a in item.get("alternatives") or ()]


def test_the_folders_domain_wins_and_the_models_stays_a_proposal(tmp_path: Path) -> None:
    a, dataset = _created(tmp_path)
    guess = {"value": ["wireless"], "basis": "inference", "reason": "猜"}
    candidate = _candidate(a, dataset, "applications/marine/sources", _signal(domain=guess))
    assert _domain(candidate) == ["marine"]
    assert "wireless" in str(_proposed(candidate))


def test_a_written_card_carries_the_models_domain_as_a_proposal(tmp_path: Path) -> None:
    a, dataset = _created(tmp_path)
    guess = {"value": "wireless", "basis": "fact", "quote": QUOTE}
    run_id, candidate = _run(a, dataset, "applications/marine/sources", _signal(domain=guess))
    _ok(_post(a, f"/api/bi/runs/{run_id}/candidates/{candidate['id']}",
              {"dataset": dataset, "review": "accepted"}))  # fmt: skip
    _ok(_post(a, f"/api/bi/runs/{run_id}/commit", {"dataset": dataset}))
    store = BiStore(a, dataset)
    (card,) = [c["id"] for c in store.card_rows() if c["entity_type"] == KIND]
    assert "marine" in str(store.fields(card)["domain"]["value"])
    assert [p["field"] for p in store.proposals(card)] == ["domain"]
    assert "wireless" in str(store.proposals(card)[0]["value"])


def test_an_existing_domain_wins_over_the_models_guess_too(tmp_path: Path) -> None:
    _drive, _vault_id, dataset, a, _b = _two_pcs(tmp_path)
    guess = {"value": ["wireless"], "basis": "inference", "reason": "猜"}
    candidate = _candidate(a, dataset, "applications/aidc/sources", _signal(domain=guess))
    assert _domain(candidate) == ["AIDC"]
