"""The selected source across a change of dataset, in a real browser.

`test_bi_build_flow_ui` failed about 2 runs in 17 with `bi.build.sourceId` empty at Ingest and
the page back on step 1. The dataset select changes before `biBuildLoad` runs, one request
later, and until then the page shows the old dataset's table and still holds its selection.
What is read in that gap then disappears when the load starts, and the load's end returned
to the step it read at its start. These hold that request open, so the order is not luck.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards.staging import Staging

SCHEMA = "/api/bi/schema?"
SOURCES = "/api/bi/sources?"


def _dataset(workspace: Path, name: str) -> None:
    _ok(_call(workspace, "POST", "/api/bi/datasets", {"name": name, "schema": "bi.schema/v1.1"}))


def _hold(page: BiPage, part: str) -> None:
    """Requests naming `part` wait until `_free`."""
    page.run(
        "(() => { const real = window.__realFetch = window.fetch; let free;"
        " const gate = new Promise((go) => { free = go; }); window.__free = free;"
        " window.fetch = async (u, o) => {"
        f" if (String(u).includes({json.dumps(part)})) await gate; return real(u, o); }}; }})()"
    )


def _free(page: BiPage) -> None:
    page.run("window.__free(); window.fetch = window.__realFetch")


def _open(page: BiPage, dataset: str) -> None:
    page.click("#bi-views [data-bi-view=build]")
    page.run(
        f"window.__opened = false; bi.want = {json.dumps(dataset)};"
        " biLoad().then(() => { window.__opened = true; }); 0"
    )
    page.wait("window.__opened")
    page.see("bi-b-target", dataset)
    page.wait("document.getElementById('bi-status-build').hidden")


def _switch(page: BiPage, dataset: str) -> None:
    page.run(
        "(() => { const s = document.getElementById('bi-dataset');"
        f" s.value = {json.dumps(dataset)}; s.dispatchEvent(new Event('change')); }})()"
    )


def _pick(page: BiPage, name: str) -> str:
    page.wait(page.shows("bi-b-sources", name))
    page.click("#bi-b-sources tbody input")
    return str(page.wait("bi.build.sourceId"))


def _visible_stage(page: BiPage) -> str:
    return str(
        page.run(
            "[...document.querySelectorAll('#bi-view-build .kp-stage')]"
            ".filter(s => !s.hidden).map(s => s.dataset.stage).join(',')"
        )
    )


def _stored(page: BiPage, dataset: str) -> dict[str, object]:
    saved = page.run(f"localStorage.getItem('bi-build-' + {json.dumps(dataset)}) || '{{}}'")
    return dict(json.loads(str(saved)))


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_what_was_selected_before_converting_stays_selected_in_the_vault(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    _dataset(workspace, "lab")
    Staging(workspace, "lab").add_source("meeting.md", text="# 會議\n", actor="alice")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "lab")
            source = _pick(page, "meeting.md")

            _hold(page, SCHEMA)
            page.click("#bi-b-v-convert")
            page.set_value("bi-b-v-path", str(shared))
            page.set_value("bi-b-v-purpose", "虛構")
            page.set_value("bi-b-v-author", "alice")
            page.click("#bi-b-v-go")
            page.wait("document.getElementById('bi-dataset').value.startsWith('vault-')")
            _free(page)
            page.wait(page.shows("bi-b-target", "vault-"))
            page.wait("document.getElementById('bi-status-build').hidden")

            # Nobody pressed anything: the same id came along, and step 2b and 2c are open.
            assert page.run("bi.build.sourceId") == source
            assert page.run("document.querySelector('#bi-b-sources tbody input').checked")
            assert not page.run(
                "document.querySelector('#bi-build-steps [data-stage=method]').disabled"
            )
            page.stage("method")
            assert _visible_stage(page) == "method"


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_nothing_of_the_old_dataset_can_be_read_or_saved_once_the_select_has_changed(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    for name in ("one", "two"):
        _dataset(workspace, name)
    Staging(workspace, "one").add_source("first.md", text="# 一\n", actor="alice")
    Staging(workspace, "two").add_source("second.md", text="# 二\n", actor="alice")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "one")
            first = _pick(page, "first.md")

            _hold(page, SCHEMA)
            _switch(page, "two")
            # What `test_bi_build_flow_ui` read as its own in this gap: the old table and selection.
            assert page.run("bi.build.sourceId") is None
            assert "first.md" not in page.text_of("bi-b-sources")
            page.click("#bi-build-steps [data-stage=schema]")
            assert _stored(page, "two").get("sourceId") is None
            _free(page)
            page.wait(page.shows("bi-b-sources", "second.md"))
            assert page.run("bi.build.sourceId") is None

            # Going back finds its own selection.
            _switch(page, "one")
            page.wait(page.shows("bi-b-sources", "first.md"))
            page.wait("document.getElementById('bi-status-build').hidden")
            assert page.run("bi.build.sourceId") == first


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_step_opened_while_the_page_loads_is_not_taken_away(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    for name in ("one", "two"):
        _dataset(workspace, name)
    Staging(workspace, "two").add_source("second.md", text="# 二\n", actor="alice")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "one")
            _hold(page, SOURCES)
            _switch(page, "two")
            page.see("bi-b-target", "two")  # the load has begun and waits for its sources
            page.stage("schema")
            _free(page)
            page.wait(page.shows("bi-b-sources", "second.md"))
            page.wait("document.getElementById('bi-status-build').hidden")
            assert _visible_stage(page) == "schema"


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_table_tried_while_the_skills_load_still_goes_by_its_rules(tmp_path: Path) -> None:
    """`test_bi_build_ui` failed 1 run in 12: the list's first entry is AI, until it is filled."""
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    _dataset(workspace, "lab")
    Staging(workspace, "lab").add_source(
        "tech.csv", text="技術,領域\nTSN,robotics\n", actor="alice"
    )
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "lab")
            _pick(page, "tech.csv")
            _hold(page, "/api/bi/methods?")
            page.stage("method")
            assert page.run("document.getElementById('bi-b-m-pick').value") == "builtin:rules"
            page.click("#bi-b-trial")
            page.see("bi-b-trial-result", "試跑")
            _free(page)
            assert "試跑完成" in page.text_of("bi-b-trial-result")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_load_overtaken_by_a_dataset_change_does_not_write_over_the_new_ones_step(
    tmp_path: Path,
) -> None:
    """`test_bi_review_table_ui` came back to step 1 after a reload, now and then. Opening the
    tab during the page's first load starts a load for the dataset shown then, and its end
    saved step 1 under whichever dataset the select had moved to."""
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    for name in ("one", "two"):
        _dataset(workspace, name)
    Staging(workspace, "two").add_source("second.md", text="# 二\n", actor="alice")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "one")
            page.run(
                "localStorage.setItem('bi-build-two', JSON.stringify({stage: 'schema'}));"
                " (() => { const real = window.fetch; window.__gates = {};"
                f" for (const part of {json.dumps([SOURCES, SCHEMA])}) {{"
                " let go; const gate = new Promise((r) => { go = r; });"
                " window.__gates[part] = {gate, go}; }"
                " window.fetch = async (u, o) => {"
                " for (const [part, held] of Object.entries(window.__gates)) {"
                " if (String(u).includes(part)) await held.gate; }"
                " return real(u, o); }; })(); 0"
            )
            # A load for this dataset, waiting for its sources.
            page.run("bi.loaded = {}; biShowView('build'); 0")
            page.wait("document.getElementById('bi-status-build').hidden === false")
            # The select moves on, and that load has not started yet.
            _switch(page, "two")
            page.wait("bi.build.dataset === 'two'")
            page.run(f"window.__gates[{json.dumps(SOURCES)}].go(); 0")
            page.wait("document.getElementById('bi-status-build').hidden")
            assert _stored(page, "two").get("stage") == "schema"
            page.run(f"window.__gates[{json.dumps(SCHEMA)}].go(); 0")
            page.wait(page.shows("bi-b-sources", "second.md"))
            page.wait("document.getElementById('bi-status-build').hidden")
            assert _visible_stage(page) == "schema"
