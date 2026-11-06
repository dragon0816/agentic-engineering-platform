"""Ingest over several sources: ticked in step 1, named in step 2b, one run each.

Acceptance F11: Ingest read only the one source chosen, and ten files meant ten rounds. Each
source keeps its own run, so its own folder and review; one that fails does not stop the
rest, and 停止 starts no more. A real browser on fictional data with a scripted model.
Screenshots in `batch-ingest/` with `AEP_UI_SHOTS`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_extract import Scripted
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards.ai_runs import AiRuntime
from common.execution import Failure
from host_runtime import bi_cards_api

NOTES = [(f"會議{n}.md", f"# 會議 {n}\n\n客戶 FAKE-{n} 表示正在評估 TSN。\n") for n in (1, 2, 3)]
BROKEN = ("壞掉.md", "# 壞掉\n\n這份會讓模型失敗。\n")


def _answer(text: str) -> Any:
    if "失敗" in text:
        return Failure(code="model_http_error", message="虛構的失敗", retryable=True)
    name = next(f"FAKE-{n}" for n in (1, 2, 3) if f"FAKE-{n}" in text)
    quote = f"客戶 {name} 表示正在評估 TSN"
    return {
        "candidates": [
            {
                "entity_type": "Signal",
                "name": f"{name} 評估 TSN",
                "fields": {"summary": {"value": quote, "basis": "fact", "quote": quote}},
            }
        ]
    }


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch) -> Scripted:
    model = Scripted(_answer)
    monkeypatch.setattr(
        bi_cards_api,
        "web_ai_runtime",
        lambda _web: AiRuntime(
            model=lambda: (model, "test-model"),
            background=lambda _title, work: work(),
            approved=lambda: ("UNCLASSIFIED", "INTERNAL"),
        ),
    )
    return model


def _open(page: BiPage, dataset: str) -> None:
    page.click("#bi-views [data-bi-view=build]")
    page.run(
        f"window.__opened = false; bi.want = {json.dumps(dataset)};"
        " biLoad().then(() => { window.__opened = true; }); 0"
    )
    page.wait("window.__opened")


def _runs(workspace: Path, dataset: str) -> list[dict[str, Any]]:
    found = _ok(_call(workspace, "GET", "/api/bi/runs", dataset=dataset))["runs"]
    return [run for run in found if run["kind"] == "ingest"]


def _ticked(page: BiPage) -> int:
    return int(page.run("document.querySelectorAll('#bi-b-sources tbody input:checked').length"))


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_ticked_sources_run_one_after_another_and_a_failure_does_not_stop_the_rest(
    tmp_path: Path, scripted: Scripted
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    _ok(_call(workspace, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "batch-ingest" if shots else None
        ) as page:
            _open(page, "lab")

            # -- several files in one go are all ticked ---------------------------------------
            page.attach_many([(n, t, "text/markdown") for n, t in [*NOTES[:2], BROKEN, NOTES[2]]])
            page.click("#bi-b-upload")
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 4")
            page.wait("document.querySelectorAll('#bi-b-sources tbody input:checked').length === 4")
            page.see("bi-b-src-count", "已選 4 份")

            # -- the header box: none, then all of what is shown --------------------------------
            page.click("#bi-b-src-all")
            assert _ticked(page) == 0 and "已選 0 份" in page.text_of("bi-b-src-count")
            page.click("#bi-b-src-all")
            assert _ticked(page) == 4
            # A search narrows what the header box ticks.
            page.set_value("bi-b-src-q", "會議3")
            page.run("document.getElementById('bi-b-src-q').dispatchEvent(new Event('input'))")
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 1")
            page.click("#bi-b-src-all")
            assert "已選 3 份" in page.text_of("bi-b-src-count")
            page.click("#bi-b-src-all")
            page.set_value("bi-b-src-q", "")
            page.run("document.getElementById('bi-b-src-q').dispatchEvent(new Event('input'))")
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 4")
            page.shoot("ticked")

            # -- step 2b says what will run, before anything is pressed --------------------------
            page.click("#bi-stepper [data-stage=ingest]")
            page.stage("method")
            page.see("bi-b-batch", "這次 Ingest：4 份來源")
            for name, _ in [*NOTES, BROKEN]:
                assert name in page.text_of("bi-b-batch")
            assert _runs(workspace, "lab") == []
            assert page.run("document.getElementById('bi-b-m-pick').options.length") >= 2
            page.shoot("named")

            # -- one run each; the broken one is said, and the others are there ----------------
            page.click("#bi-b-start")
            page.wait(
                "!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden"
            )
            runs = _runs(workspace, "lab")
            assert len(runs) == 4
            assert len({tuple(run["source_ids"]) for run in runs}) == 4  # each its own source
            failed = [run for run in runs if run["status"] == "failed"]
            assert len(failed) == 1
            page.see("bi-status-build", "壞掉.md")
            page.see("bi-status-build", "3 次執行")
            page.wait("document.querySelectorAll('#bi-b-run-pick option').length === 3")
            page.shoot("review")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_stop_cancels_the_run_under_way_and_starts_no_more(
    tmp_path: Path, scripted: Scripted
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    _ok(_call(workspace, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "lab")
            page.attach_many([(n, t, "text/markdown") for n, t in NOTES])
            page.click("#bi-b-upload")
            page.wait("document.querySelectorAll('#bi-b-sources tbody input:checked').length === 3")
            page.click("#bi-stepper [data-stage=ingest]")
            page.stage("method")
            # The second run's start waits, and 停止 is pressed meanwhile.
            page.run(
                "(() => { const real = window.fetch; let calls = 0;"
                " window.__gate = new Promise((go) => { window.__go = go; });"
                " window.fetch = async (u, o) => {"
                " if (String(u).endsWith('/api/bi/runs') && o && o.method === 'POST'"
                " && ++calls === 2) await window.__gate;"
                " return real(u, o); }; })(); 0"
            )
            page.click("#bi-b-start")
            page.wait("!document.getElementById('bi-b-batch-stop').hidden")
            page.wait(page.shows("bi-status-build", "第 2／3 份"))
            page.click("#bi-b-batch-stop")
            page.run("window.__go(); 0")
            page.wait("document.getElementById('bi-b-batch-stop').hidden")
            runs = _runs(workspace, "lab")
            assert len(runs) == 2, "no third run after 停止"
            assert sorted(run["status"] for run in runs) == ["cancelled", "review"]
            page.see("bi-notice", "已停止")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_one_source_still_runs_as_before(tmp_path: Path, scripted: Scripted) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    _ok(_call(workspace, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "lab")
            page.upload(*NOTES[0], "text/markdown")
            page.click("#bi-stepper [data-stage=ingest]")
            page.stage("method")
            assert page.text_of("bi-b-batch") == "這次 Ingest：會議1.md"
            assert page.run("document.getElementById('bi-b-batch-stop').hidden")
            page.click("#bi-b-start")
            page.wait(
                "!document.querySelector('#bi-view-build .kp-stage[data-stage=review]').hidden"
            )
            assert len(_runs(workspace, "lab")) == 1
