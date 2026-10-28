"""Per-dataset schemas in the 「BI 卡片」 area, in a real browser.

Unlike `test_bi_cards_ui.py` (a stubbed API), this drives the real Agent Web
server and the real `/api/bi/*` routes in a temporary workspace: 安裝 schema
with inline validation errors, the shipped example 「產品規格」, 新增資料集
with a name and a schema, switching datasets (the type filter, import types,
card detail and chat hint follow the dataset), an import into the non-BI
dataset through 「建立與匯入」 (the rule path) and its Dashboard empty state;
dark mode at 390 px. Screenshots in `.scratch/bi-schemas/`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.bi_cards import catalog
from capabilities.bi_cards.store import BiStore

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-schemas"
EXAMPLE = "example/product-spec@1.0.0"


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_dataset_schemas_end_to_end_in_a_browser(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()
    csvs = {item["entity_type"]: item for item in catalog.example()["csv"]}

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    # 60 s, the same as the Browser's own timeout (issue 248: a late render
    # under full-suite CPU load is not a failure).
    def wait(expression: str, seconds: float = 60) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = run(expression)
            except BrowserError:  # an element not rendered yet
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def content(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def hidden(element_id: str) -> bool:
        return bool(run(f"document.getElementById('{element_id}').hidden"))

    def options(element_id: str) -> list[str]:
        return list(
            json.loads(
                run(
                    f"JSON.stringify([...document.getElementById('{element_id}').options]"
                    ".map(o => o.value))"
                )
            )
        )

    def choose(element_id: str, value: str) -> None:
        run(
            f"{{ const s = document.getElementById('{element_id}'); s.value = {json.dumps(value)};"
            " s.dispatchEvent(new Event('change')); }"
        )

    def attach(element_id: str, name: str, body: str, kind: str) -> None:
        run(
            "(() => { const dt = new DataTransfer();"
            f" dt.items.add(new File([{json.dumps(body)}], {json.dumps(name)},"
            f" {{type: {json.dumps(kind)}}}));"
            f" const f = document.getElementById('{element_id}'); f.files = dt.files;"
            " f.dispatchEvent(new Event('change')); })()"
        )

    def metrics(width: int, height: int) -> None:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=width < 600,
        )

    def scheme(value: str) -> None:
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": value}],
        )

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    def no_side_scroll() -> None:
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    def small_buttons() -> str:
        return str(
            run(
                "[...document.querySelectorAll('#kn-pane-bi button, #kn-pane-bi .bi-files a')]"
                ".filter(b => b.offsetParent && !b.classList.contains('bi-link')"
                " && b.getBoundingClientRect().height < 44)"
                ".map(b => b.textContent.trim()).join('|')"
            )
        )

    def stage(name: str) -> None:
        run(f"document.querySelector('#bi-stepper [data-stage={name}]').click()")
        wait(f"!document.querySelector('#bi-view-build .kp-stage[data-stage={name}]').hidden")

    def import_csv(entity: str, bom: bool = True) -> None:
        # 「建立與匯入」: add the file, pick the card type, review, 確認匯入.
        item = csvs[entity]
        run("document.querySelector('#bi-views [data-bi-view=build]').click()")
        wait("!document.getElementById('bi-view-build').hidden")
        stage("source")
        attach("bi-b-file", item["filename"], ("\ufeff" if bom else "") + item["text"], "text/csv")
        run("document.getElementById('bi-b-upload').click()")
        wait(
            "[...document.querySelectorAll('#bi-b-sources tbody tr')].some(r =>"
            f" r.textContent.includes({json.dumps(item['filename'])})"
            " && r.querySelector('input:checked'))"
        )
        stage("method")
        assert options("bi-b-entity") == ["", "Supplier", "Component", "Product", "SpecItem"]
        choose("bi-b-entity", entity)
        stage("review")
        run("document.getElementById('bi-b-start').click()")
        first = item["text"].splitlines()[1].split(",")[0]  # this run's first card
        wait(f"document.getElementById('bi-b-cands').textContent.includes({json.dumps(first)})")
        run("document.getElementById('bi-notice').textContent = ''")
        run("document.getElementById('bi-b-accept-clean').click()")
        wait("document.getElementById('bi-notice').textContent.includes('張沒有錯誤的候選卡')")
        run("document.getElementById('bi-b-next4').click()")
        run("document.getElementById('bi-b-commit-go').click()")
        wait("document.getElementById('bi-b-done').textContent.includes('已寫入')")

    try:
        metrics(1366, 1000)
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        run("window.confirm = () => true;")
        run("document.getElementById('nav-knowledge').click()")
        run("document.querySelector('#kn-tabs [data-kn=bi]').click()")
        wait("document.getElementById('bi-status-bar').hidden")
        # A fresh workspace: the shipped BI schema, with its Dashboard and chat hint.
        wait("document.getElementById('bi-schema-note').textContent.includes('bi.schema/v1.1')")
        assert not hidden("bi-hint") and not hidden("bi-demo") and not hidden("bi-domain-box")
        assert len(options("bi-type")) == 13  # 全部類型 + 12 BI types

        # -- 安裝 schema: a broken file lists every problem inline ----------------------------
        run("document.getElementById('bi-install').click()")
        assert not hidden("bi-install-panel")
        assert run("document.getElementById('bi-install').getAttribute('aria-expanded')") == "true"
        broken = {
            "schema_id": "team/notes",
            "version": "1",
            "types": [{"name": "Note", "label": "筆記", "fields": [{"name": "Title"}]}],
        }
        attach("bi-schema-file", "notes.json", json.dumps(broken), "application/json")
        run("document.getElementById('bi-install-go').click()")
        wait("document.querySelectorAll('#bi-install-msg .bi-errors li').length >= 4")
        problems = content("bi-install-msg")
        for expected in ("沒有安裝", "version", "title", "types[0]（Note）.fields[0]"):
            assert expected in problems, expected
        assert not (workspace / "bi" / "schemas").exists()
        shoot("install-errors")

        # -- the shipped example installs, with its CSVs to download --------------------------
        run("document.getElementById('bi-example').click()")
        wait(f"document.getElementById('bi-install-msg').textContent.includes('{EXAMPLE}')")
        assert "已安裝" in content("bi-install-msg")
        wait("document.querySelectorAll('#bi-example-files a').length === 4")
        assert (workspace / "bi" / "schemas" / "example" / "product-spec@1.0.0.json").is_file()
        shoot("install-example")

        # -- 新增資料集: name rules, then a dataset bound to the example ---------------------
        run(
            "[...document.querySelectorAll('#bi-install-msg button')]"
            ".find(b => b.textContent.includes('新增資料集')).click()"
        )
        wait("!document.getElementById('bi-new-panel').hidden")
        assert hidden("bi-install-panel")
        wait(f"document.getElementById('bi-new-schema').value === '{EXAMPLE}'")
        run("document.getElementById('bi-new-name').value = 'bad name';")
        run("document.getElementById('bi-new-go').click()")
        wait("document.getElementById('bi-new-err').textContent.includes('1–40')")
        assert not any((workspace / "bi").glob("*/bi.sqlite"))
        shoot("new-dataset")
        run("document.getElementById('bi-new-name').value = 'spec';")
        run("document.getElementById('bi-new-go').click()")
        wait("document.getElementById('bi-dataset').value === 'spec'")
        wait("document.getElementById('bi-notice').textContent.includes('已建立資料集「spec」')")
        assert hidden("bi-new-panel")
        assert BiStore(workspace, "spec").schema_ref() == EXAMPLE
        assert "產品規格" in str(
            run("document.getElementById('bi-dataset').selectedOptions[0].textContent")
        )

        # -- the non-BI dataset: no Dashboard, no chat hint, its own types --------------------
        wait("!!document.querySelector('#bi-dash-sections .bi-none')")
        assert "這個 schema 沒有 Dashboard" in content("bi-dash-sections")
        assert "沒有 Dashboard 與對話查詢" in content("bi-schema-note")
        assert hidden("bi-hint") and hidden("bi-demo") and hidden("bi-domain-box")
        assert options("bi-type") == ["", "Supplier", "Component", "Product", "SpecItem"]
        shoot("dashboard-none")

        # -- import into it: suppliers, then components linking to them -----------------------
        import_csv("Supplier")
        wait("document.getElementById('bi-counts').textContent.startsWith('3')")
        import_csv("Component", bom=False)
        wait("document.getElementById('bi-counts').textContent.startsWith('6')")
        shoot("import-applied-spec")

        # -- card detail follows the example schema --------------------------------------------
        run("document.querySelector('#bi-views [data-bi-view=cards]').click()")
        choose("bi-type", "Component")
        wait("document.querySelectorAll('#bi-cards [data-card]').length === 3")
        run(
            "[...document.querySelectorAll('#bi-cards [data-card]')]"
            ".find(b => b.textContent.includes('48V')).click()"
        )
        detail = "document.getElementById('bi-detail-body').textContent"
        wait(f"{detail}.includes('料號')")
        text = str(run(detail))
        for expected in ("零組件", "PWR-4800", "認證狀態", "approved", "台達電子"):
            assert expected in text, expected
        assert "領域：" not in text
        shoot("card-detail-spec")

        # -- switching: a BI dataset gets its types, Dashboard and hint back -----------------
        run("document.getElementById('bi-new').click()")
        wait("!document.getElementById('bi-new-panel').hidden")
        wait("document.getElementById('bi-new-schema').options.length === 2")
        choose("bi-new-schema", "bi.schema/v1.1@1.1.0")
        run("document.getElementById('bi-new-name').value = 'market';")
        run("document.getElementById('bi-new-go').click()")
        wait("document.getElementById('bi-dataset').value === 'market'")
        wait("document.getElementById('bi-type').options.length === 13")
        assert not hidden("bi-hint") and not hidden("bi-demo")
        run("document.querySelector('#bi-views [data-bi-view=dashboard]').click()")
        wait("document.querySelectorAll('#bi-dash-sections details').length > 0")
        assert not run("!!document.querySelector('#bi-dash-sections .bi-none')")
        choose("bi-dataset", "spec")
        wait("document.getElementById('bi-type').options.length === 5")
        wait("!!document.querySelector('#bi-dash-sections .bi-none')")
        assert hidden("bi-hint")

        # -- dark mode at 390 px ---------------------------------------------------------------
        scheme("dark")
        metrics(390, 844)
        run("window.scrollTo(0, 0)")
        no_side_scroll()
        shoot("dashboard-none-dark-390")
        run("document.getElementById('bi-install').click()")
        attach("bi-schema-file", "notes.json", json.dumps(broken), "application/json")
        run("document.getElementById('bi-install-go').click()")
        wait("document.querySelectorAll('#bi-install-msg .bi-errors li').length >= 4")
        run("document.getElementById('bi-install-panel').scrollIntoView({block: 'start'})")
        no_side_scroll()
        assert small_buttons() == ""
        shoot("install-errors-dark-390")
        run("document.getElementById('bi-new').click()")
        wait("!document.getElementById('bi-new-panel').hidden")
        run("document.getElementById('bi-new-panel').scrollIntoView({block: 'start'})")
        no_side_scroll()
        assert small_buttons() == ""
        shoot("new-dataset-dark-390")
        scheme("light")
    finally:
        browser.close()
        browser.discard_profile()
