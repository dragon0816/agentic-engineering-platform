"""A feature plugin in a real (headless) browser, end to end (Feature Plugin Slice 1).

One smoke on a fresh local synthetic Host: Agent Web starts with no plugin,
a package file is chosen and installed from the Plugins panel, its declared
page appears and reads its worker, a real Bridge write with hostile text is
shown as literal text, and disabling then enabling keeps the plugin's data.
No resident, company sign-in or real model is involved.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from plugin_fixture_helpers import capability_identity, package_bytes
from test_chat_authoring import context
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.runtime import CapabilityInvocation
from common.assets import AssetIdentity
from workflow.dispatch import BridgeExecutor

NAMESPACE = "alpha-lab"
PLUGIN = f"{NAMESPACE}.fixture"
#: Counts in the page if any markup from a plugin ever ran.
HOSTILE = '<img src=x onerror="window.__pluginXss=(window.__pluginXss||0)+1"><script>x</script>'
_NAV = f"#plugin-nav button[data-plugin={json.dumps(PLUGIN)}]"
_METRIC = "(document.querySelector('#plugin-page .plugin-metric strong') || {}).textContent"
_ROWS = "document.querySelectorAll('#plugin-page table tr').length"


def _choose_package(page: BiPage, raw: bytes) -> None:
    """Choose the package file in #plugin-file as a person does in the dialog."""
    page.run(
        "(() => { const dt = new DataTransfer();"
        f" dt.items.add(new File([{json.dumps(raw.decode('utf-8'))}], 'fixture.aep-plugin',"
        " {type: 'application/json'}));"
        " const f = document.getElementById('plugin-file'); f.files = dt.files;"
        " f.dispatchEvent(new Event('change')); })()"
    )


def _open_page(page: BiPage) -> None:
    page.wait(f"!!document.querySelector({json.dumps(_NAV)})")
    page.click(_NAV)
    page.wait("!document.getElementById('plugin-page').hidden")
    page.wait("!!document.querySelector('#plugin-page table')")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_plugin_installs_shows_its_page_and_keeps_hostile_text_as_text(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            # No plugin installed yet: only BI Knowledge, shipped with AEP (Plugin
            # API 1.2), is listed, with no plugin pages under the entry.
            assert page.run("document.getElementById('nav-plugins').offsetParent !== null")
            page.click("#nav-plugins")
            page.wait("document.getElementById('panel-plugin').hasAttribute('data-open')")
            page.plugin_row_shows("bi-knowledge.bi", "shipped with AEP")
            rows = "[...document.querySelectorAll('#plugin-list .plugin-row')]"
            assert page.run(f"{rows}.map(r => r.dataset.pluginId)") == ["bi-knowledge.bi"]
            shipped_buttons = f"{rows}[0].querySelectorAll('button')"
            assert page.run(f"[...{shipped_buttons}].map(b => b.textContent)") == ["Disable"]
            assert page.run("document.querySelectorAll('#plugin-nav button').length") == 0

            # Install from a chosen file; no approval step, the plugin is active.
            _choose_package(page, package_bytes(NAMESPACE))
            page.click("#plugin-install")
            page.see("plugin-status", f"Installed {PLUGIN}.")
            page.plugin_row_shows(PLUGIN, "active")
            _open_page(page)
            assert page.run(_METRIC) == "0"
            assert page.run(_ROWS) == 1  # the header row only
            page.see("plugin-page", "<b>Synthetic</b> data only.")

            # A real write through the Bridge, then the page reads it back as text.
            installed = server.web.runtime.agent.gateway.bridge.installed
            target = AssetIdentity.model_validate(capability_identity(NAMESPACE, "write_note"))
            invocation = CapabilityInvocation(
                context=context(), target=target, arguments={"note": HOSTILE}
            )
            written = asyncio.run(BridgeExecutor(installed).execute(invocation))
            assert written.status == "succeeded"
            page.click("#plugin-refresh")
            page.wait(f"{_METRIC} === '1'")
            assert page.run(_ROWS) == 2
            page.see("plugin-page", HOSTILE)
            markup = (
                "document.querySelectorAll('#plugin-page img, #plugin-page script,"
                " #plugin-page b, #plugin-page iframe, #plugin-page a').length"
            )
            assert page.run(markup) == 0
            assert page.run("window.__pluginXss === undefined") is True

            # Disabling removes only its nav entry and page; enabling finds the data kept.
            page.click_plugin_button(PLUGIN, "Disable")
            page.plugin_row_shows(PLUGIN, "disabled")
            page.wait("document.querySelectorAll('#plugin-nav button').length === 0")
            assert page.run("document.getElementById('plugin-page').hidden") is True
            page.click_plugin_button(PLUGIN, "Enable")
            page.plugin_row_shows(PLUGIN, "active")
            _open_page(page)
            page.wait(f"{_METRIC} === '1'")
            page.see("plugin-page", HOSTILE)
            assert page.run("window.__pluginXss === undefined") is True
