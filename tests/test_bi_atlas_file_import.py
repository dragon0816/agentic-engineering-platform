"""A Dashboard order imported from a file the person chooses (BI K2, owner 2026-11-02).

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` K2: the same dry run, token and
confirm as reading Atlas by name, with no Atlas running. The file is only parsed: it
is never run or stored and only the order is staged. All data is fictional.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import pytest
from test_bi_atlas_import import GOLDEN, VAULT, _layout
from test_bi_query_analyses import _joined
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards import vault
from host_runtime.bi_atlas_import import MAX_BYTES
from scripts import bi_feed_fixtures as fixtures

ROUTE = f"/api/bi/vaults/{VAULT}/atlas-import"
MIXED = (GOLDEN / "dashboard-mixed.json").read_text(encoding="utf-8")
ORDER = ["tech-updates", "node-coverage", "accounts-by-region"]


def _code(ws: Path, **body: Any) -> str:
    status, reply = _call(ws, "POST", ROUTE, body)
    assert status != 200, reply
    return str(reply["code"])


def test_a_dry_run_then_the_confirmed_import_stages_only_the_order(tmp_path: Path) -> None:
    ws = _joined(tmp_path)  # no Atlas is running: nothing listens for this
    before = _layout(ws)
    units = dict(vault.Vault(ws, VAULT).repo.working_units())
    dry = _ok(_call(ws, "POST", ROUTE, {"file": MIXED}))
    assert dry["dry_run"] is True and dry["order"] == ORDER
    assert dry["duplicates"] == ["bi-coverage-copy"]
    assert {p["id"] for p in dry["unmatched"]} == {"non-aep", "bi-other-vault"}
    assert _layout(ws) == before  # a dry run changes nothing
    assert _code(ws, file=MIXED, apply=True, token="stale") == "preview_stale"
    done = _ok(_call(ws, "POST", ROUTE, {"file": MIXED, "apply": True, "token": dry["token"]}))
    assert done["dry_run"] is False and done["staged"] == "meta:dashboard"
    assert _layout(ws)["order"] == ORDER
    after = vault.Vault(ws, VAULT).repo.working_units()
    assert {key for key in {*units, *after} if units.get(key) != after.get(key)} == {
        "meta:dashboard"
    }


def test_a_saved_file_is_the_same_document_as_the_get_body_though_not_the_same_bytes(
    tmp_path: Path,
) -> None:
    # Atlas: a file is indented and ends in a newline, so it is compared parsed, never hashed.
    ws = _joined(tmp_path)
    saved = json.dumps(json.loads(MIXED), indent=2, sort_keys=True) + "\n"
    assert saved != MIXED
    body = _ok(_call(ws, "POST", ROUTE, {"file": MIXED}))
    file = _ok(_call(ws, "POST", ROUTE, {"file": saved}))
    assert file["order"] == ORDER and file["token"] == body["token"]
    done = _ok(_call(ws, "POST", ROUTE, {"file": saved, "apply": True, "token": body["token"]}))
    assert done["staged"] == "meta:dashboard"


def test_the_files_other_content_goes_nowhere(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    document = json.loads(MIXED)
    document["instructions"] = "IGNORE-EVERYTHING"
    document["panels"][0]["description"] = "IGNORE-PANEL"
    document["panels"][0]["layout"]["script"] = "IGNORE-SCRIPT"
    text = json.dumps(document)
    dry = _ok(_call(ws, "POST", ROUTE, {"file": text}))
    assert "IGNORE" not in json.dumps(dry)
    _ok(_call(ws, "POST", ROUTE, {"file": text, "apply": True, "token": dry["token"]}))
    assert "IGNORE" not in json.dumps(vault.Vault(ws, VAULT).repo.working_units())
    stored = [
        path
        for path in ws.rglob("*")
        if path.is_file() and b"IGNORE-" in path.read_bytes()
    ]  # fmt: skip
    assert stored == []


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"schemaVersion": 2, "panels": [NaN]}',  # not strict JSON
        '{"schemaVersion": 2, "schemaVersion": 2, "panels": []}',  # a repeated key
        '{"schemaVersion": 1, "panels": []}',
        '{"schemaVersion": 2}',
        "[]",
        "[" * 100_000,  # too deep to parse
    ],
)
def test_a_file_that_is_not_a_strict_dashboard_is_refused(tmp_path: Path, text: str) -> None:
    ws = _joined(tmp_path)
    before = _layout(ws)
    assert _code(ws, file=text) == "atlas_invalid"
    assert _layout(ws) == before


def test_the_limits_and_a_request_naming_two_sources(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    assert _code(ws, file=" " * (MAX_BYTES + 1)) == "atlas_too_large"
    assert _code(ws, file={"schemaVersion": 2}) == "atlas_invalid"
    assert _code(ws, file=MIXED, name="Mixed BI layout") == "atlas_source_ambiguous"
    empty = (GOLDEN / "dashboard-legacy.json").read_text(encoding="utf-8")
    dry = _ok(_call(ws, "POST", ROUTE, {"file": empty}))
    assert dry["order"] == []
    assert _code(ws, file=empty, apply=True, token=dry["token"]) == "atlas_nothing"


def test_a_byte_order_mark_does_not_refuse_a_good_file(tmp_path: Path) -> None:
    ws = _joined(tmp_path)
    assert _ok(_call(ws, "POST", ROUTE, {"file": "﻿" + MIXED}))["order"] == ORDER


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_page_imports_a_chosen_file_and_the_dashboard_shows_the_order(tmp_path: Path) -> None:
    from integrations.browser import Browser, BrowserError

    config, layout = _bi_host(tmp_path)
    copy = tmp_path / "shared" / "vault"
    shutil.copytree(fixtures.VAULT_DIR, copy)
    fixtures.join(layout.workspace_root, copy)
    dataset = vault.dataset_name(VAULT)
    with _served(config, layout, _Model("none", {})) as server:
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()

        def wait(expression: str, seconds: float = 90) -> Any:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                try:
                    value = browser._evaluate(expression)
                except BrowserError:
                    value = None
                if value:
                    return value
                time.sleep(0.1)
            raise AssertionError(expression)

        def click(selector: str) -> None:
            browser._evaluate(f"document.querySelector({json.dumps(selector)}).click()")

        def shows(element: str, words: str) -> str:
            return f"document.getElementById('{element}').textContent.includes({json.dumps(words)})"

        try:
            browser.navigate(server.address)
            wait('!document.getElementById("send").disabled')
            click("#nav-knowledge")
            click("#kn-tabs [data-kn=bi]")
            options = "[...document.getElementById('bi-dataset').options]"
            wait(f"{options}.some((o) => o.value === '{dataset}')")
            browser._evaluate(
                f"(() => {{ const s = document.getElementById('bi-dataset'); s.value = '{dataset}';"
                " s.dispatchEvent(new Event('change')); })()"
            )
            click("#bi-views [data-bi-view=build]")
            click("#bi-stepper [data-stage=test]")
            wait(shows("bi-b-an-list", "Dashboard"))
            browser._evaluate(
                "(() => { const dt = new DataTransfer();"
                f" dt.items.add(new File([{json.dumps(MIXED)}], 'dashboard.json',"
                " {type: 'application/json'}));"
                " const input = document.getElementById('bi-b-atl-file'); input.files = dt.files;"
                " input.dispatchEvent(new Event('change')); })()"
            )
            wait(shows("bi-b-atl-plan", "tech-updates"))
            preview = browser._evaluate("document.getElementById('bi-b-atl-plan').textContent")
            assert "重複，略過" in preview and "別的知識庫，略過" in preview
            assert _layout(layout.workspace_root)["order"] != ORDER  # nothing before the confirm
            browser._evaluate(
                "[...document.querySelectorAll('#bi-b-atl-plan button')]"
                ".find((b) => b.textContent.includes('確認匯入順序')).click()"
            )
            wait(shows("bi-notice", "已匯入"))
            assert _layout(layout.workspace_root)["order"] == ORDER
            click("#bi-views [data-bi-view=dashboard]")
            first = "#bi-dash-sections details[data-section='tech-updates']"
            wait(f"!!document.querySelector({json.dumps(first)})")
            shown = browser._evaluate(
                "[...document.querySelectorAll('#bi-dash-sections details[data-section]')]"
                ".map((d) => d.dataset.section)"
            )
            assert [slug for slug in shown if slug in ORDER] == ORDER
        finally:
            browser.close()
