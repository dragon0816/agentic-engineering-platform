"""The AI session panels of 「建立與匯入」 in a real (headless) browser.

BI ingest phases 5 and 6 (`docs/phases/BI_INGEST.md` §9, §10): the real Agent
Web server, which has no Knowledge model here. Step 3: the Session B panel says
plainly that no model is available and a turn is refused with
`model_unavailable`; a rule-path method is created from the recipe box, tried,
saved as a second revision, tried again, the two trials compared, and the
first revision brought back. Nothing reaches the cards. At phone width the
step has no horizontal scroll. Screenshots in `.scratch/bi-sessions/`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-sessions"
TECH_CSV = "技術,領域,成熟度\nEtherCAT,robotics,mature\nTSN,robotics,growth\nOPC UA,robotics,成熟\n"
RECIPE = {
    "passes": [
        {
            "id": "tech",
            "entity_type": "Technology",
            "mapping": {"columns": {"技術": "name", "領域": "domain", "成熟度": "maturity"}},
        }
    ]
}


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_session_panels_in_a_browser(served: Any, tmp_path: Path) -> None:  # noqa: F811
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
        raise AssertionError(expression)

    def click(selector: str) -> None:
        run(f"document.querySelector({json.dumps(selector)}).click()")

    def click_text(scope: str, label: str) -> None:
        run(
            f"[...document.querySelectorAll({json.dumps(scope + ' button')})]"
            f".find(b => b.textContent.includes({json.dumps(label)})).click()"
        )

    def text_of(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def set_value(element_id: str, value: str) -> None:
        run(f"document.getElementById('{element_id}').value = {json.dumps(value)}")

    def stage_shown(name: str) -> str:
        return f"!document.querySelector('#bi-view-build .kp-stage[data-stage={name}]').hidden"

    def size(width: int, height: int, mobile: bool) -> None:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=mobile,
        )

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    cards_db = workspace / "bi" / "demo" / "bi.sqlite"
    try:
        size(1366, 1000, False)
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        run("window.confirm = () => true;")
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        click("#bi-views [data-bi-view=build]")
        wait(stage_shown("source"))
        run(
            "(() => { const dt = new DataTransfer();"
            f" dt.items.add(new File([{json.dumps(TECH_CSV)}], 'tech.csv', {{type: 'text/csv'}}));"
            " const f = document.getElementById('bi-b-file'); f.files = dt.files;"
            " f.dispatchEvent(new Event('change')); })()"
        )
        click("#bi-b-upload")
        wait("document.querySelectorAll('#bi-b-sources tbody input:checked').length === 1")

        # -- step 3: no model → the panel says so; a rules method with revisions ------------
        click("#bi-stepper [data-stage=method]")
        wait(stage_shown("method"))
        wait("document.getElementById('bi-b-sb-model').textContent.includes('model_unavailable')")
        set_value("bi-b-recipe", json.dumps(RECIPE, ensure_ascii=False))
        set_value("bi-b-m-name", "技術表")
        click("#bi-b-m-new")
        wait("document.getElementById('bi-b-m-info').textContent.includes('第 1 版')")
        assert "規則轉換" in text_of("bi-b-m-info")
        assert run(
            "document.getElementById('bi-b-m-pick').selectedOptions[0].textContent"
        ).startswith("技術表")
        set_value("bi-b-sb-msg", "沒有文件依據的需求標成推測")
        click("#bi-b-sb-send")
        wait("document.getElementById('bi-b-sb-status').textContent.includes('沒有可用的模型')")
        assert run("document.getElementById('bi-b-sb-status').getAttribute('role')") == "status"
        assert "沒有對話" in text_of("bi-b-sb-log")  # nothing was stored

        click("#bi-b-trial")
        wait("document.getElementById('bi-b-trial-result').textContent.includes('試跑完成')")
        assert "@1" in text_of("bi-b-trial-result")
        fixed = json.loads(json.dumps(RECIPE))
        fixed["passes"][0]["mapping"]["enum_aliases"] = {"maturity": {"成熟": "mature"}}
        set_value("bi-b-recipe", json.dumps(fixed, ensure_ascii=False))
        click("#bi-b-m-save")
        wait("document.getElementById('bi-b-m-info').textContent.includes('第 2 版')")
        click("#bi-b-trial")
        wait("document.getElementById('bi-b-trial-result').textContent.includes('@2')")
        wait("!document.getElementById('bi-b-cmp-go').disabled")
        click("#bi-b-cmp-go")
        wait("document.getElementById('bi-b-cmp').textContent.includes('錯誤')")
        compared = text_of("bi-b-cmp")
        assert "@1" in compared and "@2" in compared and "相同" in compared
        shoot("3-compare")

        click_text("#bi-b-m-info", "回復到這一版")
        wait("document.getElementById('bi-b-m-info').textContent.includes('第 3 版')")
        assert "回復到第 1 版" in text_of("bi-b-m-info")
        assert "enum_aliases" not in run("document.getElementById('bi-b-recipe').value")
        assert not cards_db.exists()

        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("3-method-phone")
        size(1366, 1000, False)
    finally:
        browser.close()
