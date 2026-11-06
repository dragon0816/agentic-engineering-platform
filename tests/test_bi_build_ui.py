"""The 「建立與匯入」 steps of the BI area, in a real (headless) browser.

BI ingest phase 3 (owner 2026-10-27; `docs/phases/BI_INGEST.md` §10): the
real Agent Web server and `/api/bi/*` routes in a temporary workspace. A
source is added, a trial run shows candidates without writing, the steps
after the first stay locked until there is a source, an ingest run is
reviewed (evidence shown, all clean candidates accepted), 「確認匯入」 writes
the cards and the result offers undo. Then a schema draft is published as a
local BI version and the dataset is upgraded through its impact preview.
Screenshots in `.scratch/bi-build/`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.bi_cards.store import BiStore

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-build"
TECH_CSV = (
    "技術,領域,成熟度,新增測試需求\n"
    "EtherCAT,robotics,mature,週期抖動;同步精度\n"
    "TSN,robotics,growth,時間同步(802.1AS)\n"
)


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_build_and_import_steps_in_a_browser(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 60) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = run(expression)
            except BrowserError:
                value = None
            if value:
                return value
            time.sleep(0.1)
        said = run("(document.getElementById('bi-b-trial-result') || {}).textContent")
        raise AssertionError(f"{expression}\ntrial result: {said!r}")

    def click(selector: str) -> None:
        run(f"document.querySelector({json.dumps(selector)}).click()")

    def click_text(scope: str, label: str) -> None:
        run(
            f"[...document.querySelectorAll({json.dumps(scope + ' button')})]"
            f".find(b => b.textContent.includes({json.dumps(label)})).click()"
        )

    def stage_shown(name: str) -> str:
        return f"!document.querySelector('#bi-view-build .kp-stage[data-stage={name}]').hidden"

    def locked(name: str) -> bool:
        return bool(run(f"document.querySelector('#bi-build-steps [data-stage={name}]').disabled"))

    def text_of(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    cards_db = workspace / "bi" / "demo" / "bi.sqlite"
    try:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=1366,
            height=1000,
            deviceScaleFactor=1,
            mobile=False,
        )
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        run("window.confirm = () => true;")
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        click("#bi-views [data-bi-view=build]")
        wait(stage_shown("source"))
        wait("document.getElementById('bi-status-build').hidden")
        # Three steps; step 2's parts show only in step 2. The schema and the skills need no
        # source; trying, reviewing and writing do.
        assert run("document.querySelectorAll('#bi-stepper [data-stage]').length") == 3
        assert run("document.getElementById('bi-substeps').hidden")
        assert all(locked(s) for s in ("method", "review", "commit", "result"))
        assert not locked("schema") and not locked("test")
        assert "資料集「demo」" in text_of("bi-b-target")

        # -- 1 來源 ---------------------------------------------------------------------
        run(
            "(() => { const dt = new DataTransfer();"
            f" dt.items.add(new File([{json.dumps(TECH_CSV)}], 'tech.csv', {{type: 'text/csv'}}));"
            " const f = document.getElementById('bi-b-file'); f.files = dt.files;"
            " f.dispatchEvent(new Event('change')); })()"
        )
        click("#bi-b-upload")
        wait("document.querySelectorAll('#bi-b-sources tbody input:checked').length === 1")
        assert "tech.csv" in text_of("bi-b-sources") and "INTERNAL" in text_of("bi-b-sources")
        assert not locked("method") and locked("commit")
        assert not cards_db.exists()
        shoot("1-source")

        # -- 3 方法與試跑: candidates shown, nothing written -------------------------------
        click("#bi-build-steps [data-stage=method]")
        wait(stage_shown("method"))
        click("#bi-b-trial")
        wait("document.getElementById('bi-b-trial-result').textContent.includes('試跑完成')")
        assert "EtherCAT" in text_of("bi-b-trial-result")
        assert not cards_db.exists()

        # -- 4 逐卡審核 ------------------------------------------------------------------
        click("[data-stage=method] [data-bi-next=review]")
        wait(stage_shown("review"))
        click("#bi-b-start")
        wait("document.querySelectorAll('#bi-b-cands button').length === 2")
        click("#bi-b-cands button")
        wait("document.getElementById('bi-b-cand').textContent.includes('有出處')")
        assert "「mature」" in text_of("bi-b-cand") or "「growth」" in text_of("bi-b-cand")
        click("#bi-b-accept-clean")
        wait("document.getElementById('bi-b-chips').textContent.includes('已接受 2')")
        assert not locked("commit")
        assert not cards_db.exists()
        shoot("4-review")
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("4-review-phone")
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=1366,
            height=1000,
            deviceScaleFactor=1,
            mobile=False,
        )

        # -- 5 確認寫入 → 6 結果 ----------------------------------------------------------
        click("#bi-b-next4")
        wait(stage_shown("commit"))
        assert "新建 2 張" in text_of("bi-b-summary")
        click("#bi-b-commit-go")
        wait(stage_shown("result"))
        wait("document.getElementById('bi-b-done').textContent.includes('已寫入')")
        # BI vault V3: the commit reports the search index it kept current.
        assert "搜尋索引已更新：2 張卡片" in text_of("bi-b-done")
        assert sorted(c["name"] for c in BiStore(workspace).card_rows()) == ["EtherCAT", "TSN"]
        shoot("6-result")

        # -- 3 測試與 Push: a dataset on this PC only has nothing to commit -------------------
        click("[data-stage=result] [data-bi-next=test]")
        wait(stage_shown("test"))
        assert run("document.getElementById('bi-substeps').hidden")
        assert run("document.getElementById('bi-stepper').querySelector('[aria-current]')"
                   ".dataset.stage") == "test"  # fmt: skip
        assert not run("document.getElementById('bi-b-ver-none').hidden")
        assert run("document.getElementById('bi-b-ver').hidden")
        click("#bi-stepper [data-stage=ingest]")  # back to where step 2 was left
        wait(stage_shown("result"))
        assert not run("document.getElementById('bi-substeps').hidden")

        # -- 2 Schema: a draft published as a local BI version, then the upgrade ------------
        click("#bi-build-steps [data-stage=schema]")
        wait(stage_shown("schema"))
        click("#bi-b-draft-new")
        wait("!document.getElementById('bi-b-draft').hidden")
        run(
            "(() => { const box = document.getElementById('bi-b-draft-text');"
            " const doc = JSON.parse(box.value);"
            " doc.types.find(t => t.name === 'Technology').fields.push("
            "{name: 'price_band', label: '價格帶', kind: 'str', class: 'sourced'});"
            " box.value = JSON.stringify(doc); })()"
        )
        run("document.getElementById('bi-b-draft-note').value = '加價格帶';")
        click("#bi-b-draft-save")
        wait("document.getElementById('bi-b-draft-info').textContent.includes('第 2 版')")
        assert "price_band" in text_of("bi-b-draft-info")
        click("#bi-b-draft-publish")
        wait("document.getElementById('bi-notice').textContent.includes('已發布 5.1')")
        wait("document.getElementById('bi-b-versions').textContent.includes('5.1')")
        # Only versions newer than the dataset's 1.1, the published 5.1 last (F6).
        offered = run(
            "[...document.querySelectorAll('#bi-b-versions .bi-actions span')]"
            ".map(s => s.textContent)"
        )
        assert offered == ["2.0", "3.0", "4.0", "5.0", "5.1"], offered
        run(
            "[...document.querySelectorAll('#bi-b-versions .bi-actions')]"
            ".find(r => r.textContent.includes('5.1')).querySelector('button').click()"
        )
        wait("document.getElementById('bi-b-upgrade').textContent.includes('套用升級')")
        shoot("2-upgrade")
        click_text("#bi-b-upgrade", "套用升級")
        wait("document.getElementById('bi-notice').textContent.includes('已升級到 5.1')")
        assert BiStore(workspace).schema_ref() == "bi.schema/v1.1@5.1.0"
    finally:
        browser.close()
