"""The BI overview plugin in a real (headless) browser (H1/H4, owner consent 2026-11-15).

One smoke on a fresh local synthetic Host: the built-in fictional demo BI
dataset (104 cards) is loaded through the BI API, the actual overview package
is chosen and installed from the Plugins panel, and its page shows the real
counts, complete coverage and the local origin. Disabling then enabling keeps
the BI data. No resident, company sign-in, real model or company data.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.host.bi_cards_api import route as bi_route

PLUGIN = "bi-overview.overview"
DEMO_CARDS = 104
BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "build_bi_overview_plugin.py"
_NAV = f"#plugin-nav button[data-plugin={json.dumps(PLUGIN)}]"
#: Table columns as declared: name, kind, status, reason, origin, cards, ...
_DEMO_ROW = (
    "(Array.from(document.querySelectorAll('#plugin-page table tr'))"
    ".map(tr => Array.from(tr.querySelectorAll('td')).map(td => td.textContent))"
    ".find(cells => cells[0] === 'demo') || null)"
)


def _package() -> bytes:
    spec = importlib.util.spec_from_file_location("build_bi_overview_plugin", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = module.package_bytes()
    assert isinstance(raw, bytes)
    return raw


def _metric(label: str) -> str:
    """The shown value of the metric block labelled `label` (null until rendered)."""
    return (
        "((Array.from(document.querySelectorAll('#plugin-page .plugin-metric'))"
        f".find(p => p.firstChild && p.firstChild.textContent === {json.dumps(label)})"
        " || {querySelector: () => null}).querySelector('strong') || {}).textContent"
    )


def _choose_package(page: BiPage, raw: bytes) -> None:
    page.run(
        "(() => { const dt = new DataTransfer();"
        f" dt.items.add(new File([{json.dumps(raw.decode('utf-8'))}], 'bi-overview.aep-plugin',"
        " {type: 'application/json'}));"
        " const f = document.getElementById('plugin-file'); f.files = dt.files;"
        " f.dispatchEvent(new Event('change')); })()"
    )


def _open_page(page: BiPage) -> None:
    page.wait(f"!!document.querySelector({json.dumps(_NAV)})")
    page.click(_NAV)
    page.wait("!document.getElementById('plugin-page').hidden")
    page.wait(f"!!{_DEMO_ROW}")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_installed_bi_overview_page_shows_the_real_local_dataset(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = Path(layout.workspace_root)
    status, loaded = bi_route(
        workspace, "tester", "POST", "/api/bi/demo/load", {}, {"dataset": "demo"}
    )
    assert status == 200 and loaded["imported"]["created"] == DEMO_CARDS
    raw = _package()
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.click("#nav-plugins")
            page.wait("document.getElementById('panel-plugin').hasAttribute('data-open')")
            _choose_package(page, raw)
            page.click("#plugin-install")
            page.see("plugin-status", f"Installed {PLUGIN}.")
            page.plugin_row_shows(PLUGIN, "active")
            _open_page(page)

            assert page.wait(f"{_metric('找到的資料集')} === '1'")
            assert page.run(_metric("可讀本機副本卡片數（部分；非已發佈）")) == str(DEMO_CARDS)
            assert page.run(_metric("無法讀取的資料集")) == "0"
            assert page.run(_metric("完整本機副本卡片總數（不完整時為 —）")) == str(DEMO_CARDS)
            assert page.run(_metric("涵蓋範圍")) == "完整"
            assert page.run(_metric("BI 資料夾")) == "ready"
            row = page.run(_DEMO_ROW)
            assert row[:6] == ["demo", "local", "ready", "—", "本機資料庫", str(DEMO_CARDS)]

            # Disabling removes the page; enabling reads the same, untouched BI data.
            page.click_plugin_button(PLUGIN, "Disable")
            page.plugin_row_shows(PLUGIN, "disabled")
            page.wait("document.querySelectorAll('#plugin-nav button').length === 0")
            assert page.run("document.getElementById('plugin-page').hidden") is True
            page.click_plugin_button(PLUGIN, "Enable")
            page.plugin_row_shows(PLUGIN, "active")
            _open_page(page)
            assert page.wait(
                f"{_metric('完整本機副本卡片總數（不完整時為 —）')} === '{DEMO_CARDS}'"
            )
            assert page.run(_DEMO_ROW)[5] == str(DEMO_CARDS)
