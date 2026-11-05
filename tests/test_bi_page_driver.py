"""A failed wait in the browser driver explains itself (`bi_page_driver.BiPage.diagnosis`).

`test_bi_build_flow_ui` has twice timed out with no clue why; the next one reports what
the page was doing. The wait and its assertion are unchanged. All data is fictional.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_vault_asking_e2e import _bi_host, _Model, _served

from integrations.browser import Browser


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_failed_wait_reports_the_pages_requests_and_errors(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path)
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.run(
                "(() => { setTimeout(() => { throw new Error('fictional page error'); }, 0);"
                " fetch('/no/such/route?x=1').catch(() => {});"
                " fetch('/api/about', {signal: AbortSignal.abort()}).catch(() => {}); })()"
            )
            page.wait("window.__aepWatch.errors.length && window.__aepWatch.failed.length > 1", 20)
            with pytest.raises(AssertionError) as failed:
                page.wait("false", seconds=0.2)
    message = str(failed.value)
    assert message.startswith("false\n")  # the assertion still names what it waited for
    assert "ready': 'complete'" in message and "'send': False" in message
    assert "fictional page error" in message
    assert "/no/such/route" in message and "x=1" not in message
    assert "requests still open:" in message and "visible stage:" in message


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_page_that_never_opens_leaves_no_browser_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[bool] = []
    real_close = Browser.close

    def counted(self: Browser) -> None:
        closed.append(True)
        real_close(self)

    def never(self: BiPage, expression: str, seconds: float = 240) -> None:
        raise AssertionError(expression)

    monkeypatch.setattr(Browser, "close", counted)
    monkeypatch.setattr(BiPage, "wait", never)
    config, layout = _bi_host(tmp_path)
    with _served(config, layout, _Model("none", {})) as server:
        with pytest.raises(AssertionError):
            with BiPage(tmp_path / "browser", server.address):
                pass
    assert closed
