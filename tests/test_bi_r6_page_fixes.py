"""Two things V1 found on the real page: an AI run's folder, and deciding proposals.

All data is fictional.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_bi_ai_runs import Jobs, _runtime
from test_bi_extract import Scripted
from test_bi_vault import _call, _commit, _ok, _push, _sync, _two_pcs
from test_bi_vault_ui import _browser_missing
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.bi_cards import vault
from capabilities.bi_cards.store import BiStore, PlannedRow, card_id_for
from host_runtime.bi_cards_api import route

AIDC, ROBOTICS = "applications/aidc/sources", "applications/robotics/sources"
PROFILE = {
    "format": "aep.bi.profile/v1",
    "application": "aidc",
    "types": {
        "TestSolution": {"category": "虛構的類別說明", "fields": {"name": {"use": "required"}}}
    },
}
CARD = card_id_for("Technology", "FAKE-TECH")


def _post(ws: Path, path: str, body: Any, ai: Any = None) -> Any:
    return route(ws, "alice", "POST", path, {}, body, None, ai)


def _source(ws: Path, dataset: str, name: str, folder: str) -> str:
    body = {"dataset": dataset, "name": name, "text": f"# {name}\n\n虛構內容。\n", "folder": folder}
    return str(_ok(_post(ws, "/api/bi/sources", body))["source"]["id"])


def _row(values: dict[str, Any], propose: frozenset[str] = frozenset()) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type="Technology",
        canonical_key="FAKE-TECH",
        name="FAKE-TECH",
        values={"name": "FAKE-TECH", **values},
        synthetic=False,
        ref="fake-page.md#3",
        propose=propose,
    )


def _with_proposals(ws: Path, dataset: str) -> None:
    store = BiStore(ws, dataset)
    store.apply([_row({"body": "舊的內容", "summary": "舊的一句"})], filename="a.csv",
                entity_type="Technology", actor="alice")  # fmt: skip
    store.apply([_row({"body": "新的內容", "summary": "新的一句"},
                      frozenset({"body", "summary"}))],
                filename="b.csv", entity_type="Technology", actor="alice")  # fmt: skip


def test_a_folder_in_another_home_is_refused_and_none_means_the_sources_own(tmp_path: Path) -> None:
    _, vault_id, dataset, a, _ = _two_pcs(tmp_path)
    _ok(_post(a, f"/api/bi/vaults/{vault_id}/profiles", {"home": "aidc", "profile": PROFILE}))
    source = _source(a, dataset, "note.md", AIDC)

    def start(**extra: Any) -> tuple[Any, Scripted, Jobs]:
        jobs = Jobs()
        model = Scripted({"candidates": []})
        # `fresh`: the second run is the same request, and this reads the request sent.
        body = {"dataset": dataset, "kind": "trial", "source_id": source, "fresh": True, **extra}
        return _post(a, "/api/bi/runs", body, _runtime(model, jobs)), model, jobs

    # What the page used to send: the profile would silently not apply.
    for folder in ("sources", ROBOTICS):
        (status, body), _, _ = start(folder=folder)
        assert (status, body["code"]) == (400, "run_folder_mismatch"), folder
        assert AIDC in body["message"]

    for extra in ({}, {"folder": AIDC}):
        answer, model, jobs = start(**extra)
        _ok(answer)
        jobs.run_all()
        assert "虛構的類別說明" in model.requests[0].messages[0].text, extra


def test_every_pending_proposal_is_listed_and_a_rejection_keeps_its_reason(tmp_path: Path) -> None:
    drive, vault_id, dataset, a, b = _two_pcs(tmp_path)
    _with_proposals(a, dataset)
    listed = _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    assert [(p["field"], p["current"], p["value"]) for p in listed] == [
        ("body", "舊的內容", "新的內容"),
        ("summary", "舊的一句", "新的一句"),
    ]
    first = listed[0]
    assert first["card_name"] == "FAKE-TECH" and first["card_id"] == CARD
    assert first["source"]["ref"] == "fake-page.md#3" and first["label"]

    path = f"/api/bi/cards/{CARD}/proposals/{first['id']}"
    given = {"dataset": dataset, "base_version": first["version"]}
    _ok(_post(a, path, {**given, "action": "reject", "reason": "這一版寫錯了"}))
    left = _ok(_call(a, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    assert [p["field"] for p in left] == ["summary"]
    assert BiStore(a, dataset).fields(CARD)["body"]["value"] == "舊的內容"

    # The reason travels, and rebuilding does not make a false change.
    units = vault.Vault(a, vault_id).repo.working_units()
    held = [v for k, v in units.items() if k.startswith("proposal:") and v["field"] == "body"]
    assert held[0]["status"] == "rejected" and held[0]["reason"] == "這一版寫錯了"
    _commit(a, vault_id, "Decide a fictional proposal")
    assert _push(a, vault_id)["status"] == "pushed"
    drive.deliver("a", "b", vault_id)
    _sync(b, vault_id)
    assert [
        p["field"] for p in _ok(_call(b, "GET", "/api/bi/proposals", dataset=dataset))["proposals"]
    ] == ["summary"]
    assert not vault.Vault(a, vault_id).repo._pending()["sets"]


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_page_follows_the_source_and_decides_proposals(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    web, server, _, _ = served
    workspace = web.runtime.layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 90) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = run(expression)
            except BrowserError:
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def click(selector: str) -> None:
        run(f"document.querySelector({json.dumps(selector)}).click()")

    def put(element_id: str, value: str) -> None:
        run(f"document.getElementById('{element_id}').value = {json.dumps(value)}")

    try:
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        click("#bi-views [data-bi-view=build]")
        click("#bi-stepper [data-stage=source]")
        click("#bi-b-v-new")
        wait("!document.getElementById('bi-b-v-form').hidden")
        # A new vault starts on the newest shipped schema, whatever dataset is shown.
        assert run("document.getElementById('bi-b-v-schema').value") == "bi.schema/v1.1@5.0.0"
        put("bi-b-v-path", str(shared))
        put("bi-b-v-title", "Fiction")
        put("bi-b-v-purpose", "虛構範例")
        put("bi-b-v-id", "fiction")
        click("#bi-b-v-go")
        dataset = "vault-fiction"
        wait(f"document.getElementById('bi-dataset').value === '{dataset}'")

        # -- the run's folder follows the chosen source ----------------------------------
        one = _source(workspace, dataset, "one.md", AIDC)
        two = _source(workspace, dataset, "two.md", ROBOTICS)
        _with_proposals(workspace, dataset)
        run("biBuildVault()")
        click("#bi-b-v-sync")
        wait("document.getElementById('bi-b-props').hidden === false")
        run("biBuildSources ? biBuildSources() : null")
        wait(f"!!document.querySelector('input[name=bi-b-source][value=\"{one}\"]')")
        wait("document.getElementById('bi-b-folder').options.length > 1")

        def choose(source: str, folder: str) -> Any:
            # The folder follows the choice; the vault's other reads (versions, share, skills)
            # may redraw it a moment later, so this waits for where it settles.
            click(f'input[name=bi-b-source][value="{source}"]')
            follows = f"document.getElementById('bi-b-folder').value === {json.dumps(folder)}"
            try:
                wait(follows, 15)
            except AssertionError:
                pass
            return run("document.getElementById('bi-b-folder').value")

        assert choose(one, AIDC) == AIDC
        assert choose(two, ROBOTICS) == ROBOTICS  # follows reselecting
        assert run("biRunBody('trial').folder") == ROBOTICS

        # -- deciding proposals -------------------------------------------------------------
        wait("document.getElementById('bi-b-props-h').textContent.includes('2 筆')")
        shown = run("document.getElementById('bi-b-props-list').textContent")
        assert "舊的內容" in shown and "新的內容" in shown and "fake-page.md#3" in shown

        # The first row still undecided: a decided row stays on the list with its mark.
        reject = "#bi-b-props-list .bi-actions button:last-child"
        click(reject)
        wait(
            "document.querySelector('#bi-b-props-list li .bi-err')"
            ".textContent.includes('請寫下理由')"
        )
        assert run("document.getElementById('bi-b-props-h').textContent").count("2 筆") == 1
        run("document.querySelector('#bi-b-props-list li input').value = '這一版寫錯了'")
        click(reject)
        wait("document.getElementById('bi-b-props-h').textContent.includes('1 筆')")
        store = BiStore(workspace, dataset)
        assert store.fields(CARD)["body"]["value"] == "舊的內容"

        wait("!!document.querySelector('#bi-b-props-list .bi-state-rejected')")
        accept = "#bi-b-props-list .bi-actions button:nth-last-child(2)"
        run("document.querySelector('#bi-b-props-list li input').value = '新的比較好'")
        click(accept)
        try:
            wait("document.getElementById('bi-b-props-h').textContent.includes('0 筆')", 60)
            wait("!!document.querySelector('#bi-b-props-list .bi-state-accepted')", 60)
        except AssertionError:
            said = run("document.getElementById('bi-b-props-list').textContent")
            raise AssertionError(said) from None
        assert BiStore(workspace, dataset).fields(CARD)["summary"]["value"] == "新的一句"
        assert "commit" in run("document.getElementById('bi-notice').textContent")

        # -- many at once: filter, one reason, a confirmation with the count ------------------
        store = BiStore(workspace, dataset)
        for key in ("FAKE-B1", "FAKE-B2"):
            for values, propose in (
                ({"body": "舊", "confidence": "assumed"}, frozenset()),
                ({"body": "新", "confidence": "verified"}, frozenset({"body", "confidence"})),
            ):
                store.apply(
                    [
                        PlannedRow(
                            row=1,
                            entity_type="Technology",
                            canonical_key=key,
                            name=key,
                            values={"name": key, **values},
                            synthetic=False,
                            ref="bulk-page.md#1",
                            propose=propose,
                        )
                    ],
                    filename="c.csv",
                    entity_type="Technology",
                    actor="alice",
                )
        click("#bi-b-v-sync")
        wait("document.getElementById('bi-b-props-h').textContent.includes('4 筆')")
        # All shown, but `confidence` is left out until the filter names it.
        wait("document.getElementById('bi-b-props-accept').textContent.includes('2 筆')")
        click("#bi-b-props-accept")
        wait("document.getElementById('bi-b-props-confirm').textContent.includes('請寫下理由')")
        put("bi-b-props-reason", "這批看過了")
        click("#bi-b-props-accept")
        wait("document.getElementById('bi-b-props-confirm').textContent.includes('另有 2 筆')")
        assert len(BiStore(workspace, dataset).pending_proposals()) == 4  # nothing yet
        click("#bi-b-props-confirm .go")
        wait("document.getElementById('bi-b-props-h').textContent.includes('2 筆')")
        for key in ("FAKE-B1", "FAKE-B2"):
            card = card_id_for("Technology", key)
            assert BiStore(workspace, dataset).fields(card)["body"]["value"] == "新"
            assert BiStore(workspace, dataset).fields(card)["confidence"]["value"] == "assumed"

        run(
            "(() => { const s = document.getElementById('bi-b-props-field');"
            " s.value = 'confidence'; s.dispatchEvent(new Event('change')); })()"
        )
        wait("document.getElementById('bi-b-props-reject').textContent.includes('2 筆')")
        put("bi-b-props-reason", "沒有依據")
        click("#bi-b-props-reject")
        click("#bi-b-props-confirm .go")
        wait("document.getElementById('bi-b-props-h').textContent.includes('0 筆')")
        # Each answered in the list too, not only by a notice at the top of the page.
        wait("document.querySelectorAll('#bi-b-props-list .bi-state-accepted').length === 3")
        wait("document.querySelectorAll('#bi-b-props-list .bi-state-rejected').length === 3")
    finally:
        browser.close()
