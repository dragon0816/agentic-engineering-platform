"""Replaying a recorded web procedure on the practice site (SOP_TO_WORKFLOW W2)."""

import json
import sys
import urllib.request
from collections.abc import Iterator

import pytest

from evaluation.sop_practice import PracticeSite
from integrations.web_script import (
    ScriptRunner,
    WebAction,
    WebScript,
    WebScriptError,
    WebTarget,
)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="drives the installed Edge")


@pytest.fixture(scope="module")
def site() -> Iterator[PracticeSite]:
    served = PracticeSite()
    served.start()
    yield served
    served.close()


@pytest.fixture(scope="module")
def browser(tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    from integrations.browser import Browser, browser_path

    if browser_path() is None:
        pytest.skip("no Chromium browser installed")
    with Browser(tmp_path_factory.mktemp("profile"), timeout_s=30) as running:
        yield running


SEARCH = (
    WebAction(do="open", url="{site}/"),
    WebAction(do="fill", target=WebTarget(label="客戶代碼", kind="field"), value="{customer}"),
    WebAction(do="click", target=WebTarget(label="查詢", kind="button")),
    WebAction(do="read_table", table="#orders", save_as="orders"),
)


def runner(browser: object, site: PracticeSite) -> ScriptRunner:
    return ScriptRunner(browser, (site.url,))  # type: ignore[arg-type]


def test_a_search_is_replayed_and_the_table_comes_back_as_rows(browser, site) -> None:  # type: ignore[no-untyped-def]
    result = runner(browser, site).run(
        WebScript(actions=SEARCH, values={"site": site.url, "customer": "C001"}), "read"
    )
    rows = result.data["orders"]
    assert isinstance(rows, list) and [row["訂單號"] for row in rows] == [
        "SO-1001",
        "SO-1002",
        "SO-1003",
        "SO-1004",
    ]
    assert rows[1]["狀態"] == "延遲" and "customer=C001" in result.url


def test_read_mode_refuses_a_click_that_would_change_the_site(browser, site) -> None:  # type: ignore[no-untyped-def]
    notify = (
        *SEARCH[:3],
        WebAction(
            do="click",
            target=WebTarget(label="標記已通知", kind="button"),
            row={"table": "#orders", "column": "訂單號", "equals": "SO-1002"},
        ),
    )
    with pytest.raises(WebScriptError) as refused:
        runner(browser, site).run(
            WebScript(actions=notify, values={"site": site.url, "customer": "C001"}), "read"
        )
    assert refused.value.code == "web_click_not_read_only"
    assert site.notified == set()


def test_act_mode_clicks_once_per_item_in_the_matching_row(browser, site) -> None:  # type: ignore[no-untyped-def]
    actions = (
        WebAction(do="open", url="{site}/orders?customer=C001"),
        WebAction(
            do="click",
            target=WebTarget(label="標記已通知", kind="button"),
            row={"table": "#orders", "column": "訂單號", "equals": "{item}"},
        ),
    )
    result = runner(browser, site).run(
        WebScript(actions=actions, values={"site": site.url}, for_each=("SO-1002", "SO-1004")),
        "act",
    )
    assert result.done == ("SO-1002", "SO-1004")
    with urllib.request.urlopen(site.url + "/state.json") as reply:
        assert json.loads(reply.read())["notified"] == ["SO-1002", "SO-1004"]
    site.notified.clear()


def test_a_changed_page_stops_with_a_named_failure(browser, site) -> None:  # type: ignore[no-untyped-def]
    for target, code in (
        (WebTarget(label="客戶編號", kind="field"), "web_target_missing"),
        (WebTarget(css="input, button"), "web_target_ambiguous"),
    ):
        with pytest.raises(WebScriptError) as stopped:
            runner(browser, site).run(
                WebScript(
                    actions=(
                        WebAction(do="open", url=f"{site.url}/"),
                        WebAction(do="fill", target=target, value="x"),
                    )
                ),
                "read",
            )
        assert stopped.value.code == code


def test_only_allowed_origins_are_opened(browser, site) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(WebScriptError) as refused:
        runner(browser, site).run(
            WebScript(actions=(WebAction(do="open", url="https://example.com/"),)), "read"
        )
    assert refused.value.code == "web_origin_not_allowed"
    with pytest.raises(WebScriptError) as missing:
        runner(browser, site).run(WebScript(actions=SEARCH, values={"site": site.url}), "read")
    assert missing.value.code == "web_value_missing"


def test_an_action_must_carry_what_it_needs() -> None:
    with pytest.raises(ValueError):
        WebAction(do="fill", target=WebTarget(label="x"))
    with pytest.raises(ValueError):
        WebTarget(label="x", css="#x")


def test_any_origin_allows_every_web_page_but_no_other_scheme() -> None:
    """Owner 2026-10-08: every web page may be used; network access is company IT's.
    Only http(s) pages are web pages: local files and scripts never are."""
    from capabilities.web.handlers import WebHostBinding
    from integrations.web_script import origin_permitted

    anything = {"*"}
    for url in (
        "https://tw.stock.yahoo.com/quote/2330",
        "http://intranet.example:8080/a",
        "https://www.rohde-schwarz.com/",
    ):
        assert origin_permitted(url, anything), url
    for url in (
        "file:///C:/Users/x/secret.txt",
        "javascript:alert(1)",
        "data:text/html,hi",
        "chrome://settings",
        "edge://settings",
        "about:blank",
        "https://",
    ):
        assert not origin_permitted(url, anything), url
    listed = {"https://tw.stock.yahoo.com"}
    assert origin_permitted("https://tw.stock.yahoo.com/x", listed)
    assert not origin_permitted("https://evil.example/", listed)
    assert WebHostBinding().allowed_origins == ("*",)
