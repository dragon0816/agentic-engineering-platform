"""What the first real R6 AI run found: a list that lost items, `domain` blocking
candidates, a stale proposal list and a publish notice with no counts. All data is
fictional; the model is scripted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_run_merge import (
    CARD,
    KEY,
    KIND,
    NOTE,
    QUOTE,
    _accept_and_commit,
    _answer,
    _detail,
    _fact,
    _pending,
    _post,
    _run,
    _seed,
    _value,
)
from test_bi_vault import _call, _ok, _push, _two_pcs
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards import ai_runs, catalog, vault
from capabilities.bi_cards.store import BiStore


def _field(ws: Path, dataset: str, run_id: str, name: str) -> dict[str, Any] | None:
    fields = _detail(ws, dataset, run_id)["candidates"][0]["fields"]
    return next((f for f in fields if f["field"] == name), None)


def _run_in(ws: Path, dataset: str, folder: str, answer: Any) -> str:
    body = {"dataset": dataset, "name": "note.md", "text": NOTE, "folder": folder}
    source = _ok(_post(ws, "/api/bi/sources", body))["source"]["id"]
    jobs = Jobs()
    given = {"dataset": dataset, "kind": "ingest", "source_id": source, "types": [KIND]}
    run = _ok(_post(ws, "/api/bi/runs", given, _runtime(Scripted(answer), jobs)))["run"]
    jobs.run_all()
    return str(run["id"])


# -- 1. a list never shrinks ------------------------------------------------------


@pytest.mark.parametrize("given", [["EMC"], ["emc", "rf"]], ids=["subset", "reordered"])
def test_a_list_the_card_already_holds_writes_nothing(tmp_path: Path, given: list[str]) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, tech_areas=["rf", "emc"])
    before = BiStore(a, dataset).history(CARD)
    run_id = _run(a, dataset, _answer(tech_areas=_fact(given)))
    item = _field(a, dataset, run_id, "tech_areas")
    assert item is not None
    assert item["merge"] == "same"
    assert _detail(a, dataset, run_id)["run"]["merge"]["same"] == 2  # with the name
    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "tech_areas") == ["rf", "emc"]
    assert _pending(a, dataset) == {}
    assert BiStore(a, dataset).history(CARD) == before
    # Its evidence still counts: this source says so too.
    cited = BiStore(a, dataset).evidence(CARD)
    assert [e["excerpt"] for e in cited if e["field"] == "tech_areas"] == [QUOTE]


def test_a_list_with_something_new_is_still_the_union(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, tech_areas=["rf", "emc"])
    run_id = _run(a, dataset, _answer(tech_areas=_fact(["EMC", "high-speed-io"])))
    item = _field(a, dataset, run_id, "tech_areas")
    assert item is not None
    assert item["merge"] == "join"
    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "tech_areas") == ["rf", "emc", "high-speed-io"]


def test_a_subset_of_a_persons_list_proposes_nothing(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset, tech_areas=["rf", "emc"])
    card = BiStore(a, dataset).card(CARD)
    assert card is not None
    BiStore(a, dataset).set_field(
        CARD, "tech_areas", ["rf", "emc"], base_version=int(card["version"]), actor="x", reason="r"
    )
    BiStore(a, dataset).set_field(
        CARD, "supplier", "FAKE-A", base_version=int(card["version"]), actor="x", reason="r"
    )
    run_id = _run(a, dataset, _answer(tech_areas=_fact(["EMC"])))
    _accept_and_commit(a, dataset, run_id)
    assert _value(a, dataset, "tech_areas") == ["rf", "emc"]
    assert _pending(a, dataset) == {}


# -- 2. domain ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("folder", "domain"),
    [
        ("applications/aidc/sources", "AIDC"),
        ("applications/aerospace/sources", "aerospace"),
        ("applications/robotics/sources", "robotics"),
        ("applications/wireless/sources", "wireless"),
        ("applications/no-such-domain/sources", None),
        ("library/products/sources", None),
        (None, None),
    ],
)
def test_the_home_domain_comes_from_the_schema(
    tmp_path: Path, folder: str | None, domain: str | None
) -> None:
    assert ai_runs.home_domain(catalog.resolve(tmp_path, "bi.schema/v1.1"), folder) == domain


def test_a_domain_the_model_invented_is_dropped_and_a_new_card_takes_its_homes(
    tmp_path: Path,
) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    invented = _answer(
        supplier=_fact("FAKE-A"),
        domain={"value": "AI 電源、HVDC", "basis": "inference", "reason": "猜的"},
    )
    run_id = _run_in(a, dataset, "applications/aidc/sources", invented)
    candidate = _detail(a, dataset, run_id)["candidates"][0]
    assert candidate["errors"] == []
    assert candidate["action"] == "create"
    assert "domain_unknown" in [w["code"] for w in candidate["warnings"]]
    item = _field(a, dataset, run_id, "domain")
    assert item is not None
    assert item["basis"] == "inference"
    _accept_and_commit(a, dataset, run_id)
    stored = _value(a, dataset, "domain")
    assert stored == "AIDC" or stored == ["AIDC"]


def test_the_folders_domain_wins_over_one_the_schema_knows(tmp_path: Path) -> None:
    # Acceptance F10 (2026-11-06) reverses R6's rule that a model's known domain stays: the
    # folder a person put the source in decides a new card's domain.
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    given = _answer(domain={"value": "robotics", "basis": "inference", "reason": "原文"})
    run_id = _run_in(a, dataset, "applications/aidc/sources", given)
    item = _field(a, dataset, run_id, "domain")
    assert item is not None
    assert "AIDC" in str(item["value"]) and "robotics" not in str(item["value"])
    # What the model read is kept, as a proposal for a person (BI orchestrator, 2026-11-06).
    assert "robotics" in str(item.get("alternatives"))


def test_a_library_source_gives_no_domain_and_no_error(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    invented = _answer(
        supplier=_fact("FAKE-A"),
        domain={"value": "AI 電源", "basis": "inference", "reason": "猜的"},
    )
    run_id = _run_in(a, dataset, "library/products/sources", invented)
    assert _field(a, dataset, run_id, "domain") is None
    assert _detail(a, dataset, run_id)["candidates"][0]["errors"] == []


def test_a_card_that_exists_does_not_take_the_default(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    _seed(a, dataset)
    run_id = _run_in(a, dataset, "applications/aidc/sources", _answer())
    assert _field(a, dataset, run_id, "domain") is None


def test_another_fields_bad_value_still_blocks(tmp_path: Path) -> None:
    _, _, dataset, a, _ = _two_pcs(tmp_path)
    bad = _answer(tech_areas=_fact("沒有這個領域"))
    run_id = _run_in(a, dataset, "applications/aidc/sources", bad)
    codes = [e["code"] for e in _detail(a, dataset, run_id)["candidates"][0]["errors"]]
    assert "value_invalid" in codes


# -- 3, 4. the page ----------------------------------------------------------------


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_page_lists_proposals_after_a_run_and_counts_missing_summaries(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path)
    ws = layout.workspace_root
    folder = tmp_path / "shared"
    folder.mkdir()
    made = _ok(
        _call(
            ws,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(folder),
                "title": "R6 Fixes",
                "purpose": "虛構測試",
                "schema": "bi.schema/v1.1",
                "author": "alice",
                "default_pack": False,
            },
        )
    )
    vault_id = made["vault"]["id"]
    dataset = vault.dataset_name(vault_id)
    _seed(ws, dataset, confidence="assumed")
    answer = _answer(confidence=_fact("verified", QUOTE))
    run_id = _run(ws, dataset, answer)
    for candidate in _detail(ws, dataset, run_id)["candidates"]:
        path = f"/api/bi/runs/{run_id}/candidates/{candidate['id']}"
        _ok(_post(ws, path, {"dataset": dataset, "review": "accepted"}))
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.run(
                "(() => { const s = document.getElementById('bi-dataset');"
                f" s.value = '{dataset}'; s.dispatchEvent(new Event('change')); }})()"
            )
            page.wait(f"biDataset() === '{dataset}'")
            page.click("#bi-views [data-bi-view=build]")
            page.wait("el('bi-b-props').hidden === true && bi.proposals !== undefined")
            # The page holds no proposal yet; the run's commit from it makes one.
            page.run(f"bi.build.run = {{id: '{run_id}'}}; el('bi-b-commit-go').click()")
            page.wait("(bi.proposals || []).length === 1")
            page.see("bi-b-props-h", "1 筆")
            # Only a protected field: 0 for 「全部」, and the page says why.
            page.see("bi-b-props-accept", "0 筆")
            page.see("bi-b-props-confirm", "confidence")
            _push(ws, vault_id)
            page.run(
                f"biCall('/api/bi/vaults/{vault_id}/tag', {{name: 'v1', purpose: '虛構版本'}})"
                f".then(() => biVerRun('{vault_id}', 'publish', {{tag: 'v1', confirm: true}},"
                " (reply) => biPublishWords('v1', reply)))"
            )
            page.notice("1 張卡片還沒有摘要")
            assert "1" in page.text_of("bi-notice")
    assert _value(ws, dataset, "confidence") == "assumed"
    assert KEY in str(BiStore(ws, dataset).card(CARD)["canonical_key"])  # type: ignore[index]
