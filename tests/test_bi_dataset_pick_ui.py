"""Which dataset the 「BI 卡片」 area opens on (live test 2026-10-24).

It always opened on `demo`, even when `demo` did not exist, showing 0 cards
and an empty Dashboard. Now: the last dataset chosen in this browser while it
still exists, else the first own dataset, else the first subscribed one, else
`demo` with an empty state offering 載入示範資料 / 新增資料集. The real Agent Web
page and server behind the stub proxy of `test_bi_cards_ui.py`.
"""

from __future__ import annotations

import time
import urllib.parse
from pathlib import Path
from typing import Any

import pytest
from test_bi_cards_ui import _browser_missing, _proxy
from test_bi_share_ui import ROBOTICS, ShareStub
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture


class PickStub(ShareStub):
    """`/api/bi/datasets` lists exactly `own` (local names) and the stub's
    subscriptions."""

    def __init__(self) -> None:
        super().__init__()
        self.own: list[str] = []

    def handle(self, method: str, path: str, body: Any) -> tuple[int, dict[str, Any]]:
        route = urllib.parse.urlsplit(path).path
        if route == "/api/bi/datasets":
            self.calls.append((method, route, {}))
            own = [
                {"name": name, "cards": 2, "updated": None, "read_only": False} for name in self.own
            ]
            return 200, {"datasets": [*own, *self.subs.values()]}
        return super().handle(method, path, body)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_bi_area_opens_on_a_dataset_that_exists(served: Any, tmp_path: Path) -> None:  # noqa: F811
    import threading

    from integrations.browser import Browser, BrowserError

    _web, server, _recorder, _ = served
    real = urllib.parse.urlsplit(server.address)
    stub = PickStub()
    proxy = _proxy(stub, f"{real.scheme}://{real.netloc}")
    threading.Thread(target=proxy.serve_forever, daemon=True).start()
    address = f"http://127.0.0.1:{proxy.server_address[1]}/?{real.query}"
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 20) -> Any:
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

    def open_bi() -> str:
        stub.calls.clear()
        browser.navigate(address)
        wait('!document.getElementById("send").disabled')
        run("document.getElementById('nav-knowledge').click()")
        run("document.querySelector('#kn-tabs [data-kn=bi]').click()")
        wait("document.getElementById('bi-status-bar').hidden")
        wait("document.getElementById('bi-dataset').options.length > 0")
        return str(run("document.getElementById('bi-dataset').value"))

    def asked() -> set[str]:
        return {
            str(body.get("dataset"))
            for _method, route, body in stub.calls
            if route in ("/api/bi/dashboard", "/api/bi/schema") and isinstance(body, dict)
        }

    try:
        # Only a subscription: it opens on it, not on a `demo` that is not there.
        stub.subs.pop("sales/old-bi")
        stub.own = []
        assert open_bi() == ROBOTICS
        wait("!document.getElementById('bi-ro').hidden")  # read only
        assert asked() == {ROBOTICS}
        assert run("document.getElementById('bi-empty-state').hidden")

        # Own datasets come first; a choice is remembered in this browser.
        stub.own = ["demo", "spec"]
        assert open_bi() == ROBOTICS  # remembered from the last visit
        run(
            "{ const s = document.getElementById('bi-dataset'); s.value = 'spec';"
            " s.dispatchEvent(new Event('change')); }"
        )
        wait("document.getElementById('bi-status-bar').hidden")
        assert open_bi() == "spec"
        # A remembered dataset that is gone: the first own one.
        stub.own = ["demo"]
        assert open_bi() == "demo"
        assert "spec" not in str(
            run("[...document.getElementById('bi-dataset').options].map(o => o.value).join()")
        )

        # Nothing at all (acceptance F2): 新增知識庫 and 加入 in the guide, a small demo link,
        # and no select, tabs or steps for a dataset that does not exist.
        stub.own = []
        stub.subs.clear()
        assert open_bi() == "demo"
        wait("!document.getElementById('bi-empty-state').hidden")
        state = str(run("document.getElementById('bi-empty-state').textContent"))
        assert "還沒有知識庫" in state and "載入示範資料" in state
        assert "新增資料集" not in state
        shown = "(id) => document.getElementById(id).offsetParent !== null"
        for gone in ("bi-dataset", "bi-views", "bi-view-build", "bi-counts", "bi-b-v-state"):
            assert not run(f"({shown})('{gone}')"), gone
        for kept in ("bi-empty-new", "bi-empty-join", "bi-empty-demo", "bi-b-v-menu"):
            assert run(f"({shown})('{kept}')"), kept
        assert "go" in str(run("document.getElementById('bi-empty-new').className"))
        # The guide's 新增知識庫 opens the same form as the one in 管理.
        run("document.getElementById('bi-empty-new').click()")
        wait("!document.getElementById('bi-b-v-form').hidden")
        assert run("document.getElementById('bi-b-v-form').dataset.mode") == "new"
        run("document.getElementById('bi-b-v-cancel').click()")
        # 新增資料集 is in 管理 (owner 2026-11-19, B1).
        run("document.querySelector('#bi-b-v-menu > summary').click()")
        wait("document.getElementById('bi-b-v-menu').open")
        for item in ("bi-b-v-new", "bi-b-v-join", "bi-new", "bi-install"):
            assert run(f"({shown})('{item}')"), item
        run("document.getElementById('bi-new').click()")
        wait("!document.getElementById('bi-new-panel').hidden")
        assert not run("document.getElementById('bi-b-v-menu').open")
    finally:
        browser.close()
        proxy.shutdown()
