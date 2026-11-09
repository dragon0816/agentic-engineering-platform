"""Replaying a recorded web procedure on the practice site (SOP_TO_WORKFLOW W2)."""

import json
import sys
import urllib.request
from collections.abc import Iterator
from typing import Any

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
    assert isinstance(rows, list)
    table = [row for row in rows if isinstance(row, dict)]
    assert len(table) == len(rows) and [row["訂單號"] for row in table] == [
        "SO-1001",
        "SO-1002",
        "SO-1003",
        "SO-1004",
    ]
    assert table[1]["狀態"] == "延遲" and "customer=C001" in result.url


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


def test_click_delivers_a_trusted_pointer_sequence(browser, site) -> None:  # type: ignore[no-untyped-def]
    """SAP controls listen for pointer release/tap, not HTMLElement.click()."""
    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<button id=\"sap-press\">Select View</button>';"
        "window.__presses = 0; document.getElementById('sap-press').addEventListener("
        "'mouseup', e => { if (e.isTrusted) window.__presses += 1; });"
    )
    script = WebScript(actions=(WebAction(do="click", target=WebTarget(css="#sap-press")),))
    with pytest.raises(WebScriptError) as refused:
        runner(browser, site).run(script, "read")
    assert refused.value.code == "web_click_not_read_only"
    assert browser.evaluate("window.__presses") == 0
    runner(browser, site).run(script, "act")
    assert browser.evaluate("window.__presses") == 1


def test_hidden_copies_do_not_make_a_visible_target_ambiguous(browser, site) -> None:  # type: ignore[no-untyped-def]
    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<button style=\"display:none\">Sales Orders</button>'"
        ' + \'<a href="#" id="visible-orders">Sales Orders</a>\';'
        "window.__chosen = false; document.getElementById('visible-orders').addEventListener("
        "'mouseup', e => { window.__chosen = e.isTrusted; });"
    )
    runner(browser, site).run(
        WebScript(actions=(WebAction(do="click", target=WebTarget(label="Sales Orders")),)), "act"
    )
    assert browser.evaluate("window.__chosen") is True


def test_native_dropdown_options_are_selected_by_their_visible_label(browser, site) -> None:  # type: ignore[no-untyped-def]
    browser.navigate(site.url)
    browser.evaluate(
        'document.body.innerHTML = \'<ul><li role="option" id="between">... Between</li></ul>\';'
        "window.__chosen = false; document.getElementById('between').addEventListener("
        "'mouseup', e => { window.__chosen = e.isTrusted; });"
    )
    runner(browser, site).run(
        WebScript(actions=(WebAction(do="click", target=WebTarget(label="... Between")),)), "act"
    )
    assert browser.evaluate("window.__chosen") is True


def paginated_page(browser: Any, site: PracticeSite, *, stalled: bool = False) -> None:
    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<table id=\"headers\"><thead><tr><th>ID</th><th>Amount</th>'"
        " + '</tr></thead></table><table id=\"rows\"><thead><tr><th></th><th></th></tr></thead>'"
        " + '<tbody><tr><td>SO-1</td><td>100</td></tr></tbody></table>'"
        ' + \'<input id="page" value="1"><span id="total">/ 3</span>\''
        " + '<button id=\"next\">Next Page</button>';"
        "document.getElementById('next').addEventListener('mouseup', e => {"
        f"if (!e.isTrusted || {json.dumps(stalled)}) return;"
        "const n = Number(document.getElementById('page').value) + 1;"
        "document.getElementById('page').value = n;"
        "setTimeout(() => { document.querySelector('#rows tbody').innerHTML = "
        "'<tr><td>SO-' + n + '</td><td>' + n*100 + '</td></tr>'; }, 80); });"
    )


def paginated_action(max_pages: int = 3) -> WebAction:
    return WebAction.model_validate(
        {
            "do": "read_table",
            "table": "#rows",
            "header_table": "#headers",
            "save_as": "orders",
            "pagination": {
                "next": {"css": "#next"},
                "current": {"css": "#page"},
                "total": {"css": "#total"},
                "max_pages": max_pages,
                "key_columns": ["ID"],
            },
        }
    )


def test_split_header_and_all_pages_are_read_after_each_refresh(browser, site) -> None:  # type: ignore[no-untyped-def]
    paginated_page(browser, site)
    result = runner(browser, site).run(WebScript(actions=(paginated_action(),)), "act")
    assert result.data["orders"] == [
        {"ID": "SO-1", "Amount": "100"},
        {"ID": "SO-2", "Amount": "200"},
        {"ID": "SO-3", "Amount": "300"},
    ]


def test_pagination_bounds_and_stalled_pages_never_return_partial_data(browser, site) -> None:  # type: ignore[no-untyped-def]
    paginated_page(browser, site)
    with pytest.raises(WebScriptError) as limited:
        runner(browser, site).run(WebScript(actions=(paginated_action(2),)), "act")
    assert limited.value.code == "web_pagination_limit_exceeded"
    paginated_page(browser, site, stalled=True)
    with pytest.raises(WebScriptError) as stopped:
        ScriptRunner(browser, (site.url,), timeout_s=0.4).run(
            WebScript(actions=(paginated_action(),)), "act"
        )
    assert stopped.value.code == "web_pagination_did_not_advance"


def test_wait_for_observes_visible_completion_and_times_out(browser, site) -> None:  # type: ignore[no-untyped-def]
    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<span id=\"count\">(--)</span>';"
        "setTimeout(() => document.getElementById('count').innerText = '(750)', 150);"
    )
    action = WebAction(do="wait_for", target=WebTarget(css="#count"), value=r"\(\d+\)")
    ScriptRunner(browser, (site.url,), timeout_s=1).run(WebScript(actions=(action,)), "read")
    assert browser.evaluate("document.getElementById('count').innerText") == "(750)"
    with pytest.raises(WebScriptError) as stopped:
        ScriptRunner(browser, (site.url,), timeout_s=0.2).run(
            WebScript(actions=(action.model_copy(update={"value": "finished"}),)), "read"
        )
    assert stopped.value.code == "web_wait_timeout"


def test_pagination_waits_for_frozen_key_cells_to_catch_up(browser, site) -> None:  # type: ignore[no-untyped-def]
    paginated_page(browser, site)
    browser.evaluate(
        "document.getElementById('next').addEventListener('mouseup', () => {"
        "const before = document.querySelector('#rows tbody td').innerText;"
        "setTimeout(() => {"
        "const cell = document.querySelector('#rows tbody td'); const after = cell.innerText;"
        "cell.innerText = before; setTimeout(() => cell.innerText = after, 500); }, 100); });"
    )
    result = ScriptRunner(browser, (site.url,), timeout_s=2).run(
        WebScript(actions=(paginated_action(),)), "act"
    )
    assert result.data["orders"] == [
        {"ID": "SO-1", "Amount": "100"},
        {"ID": "SO-2", "Amount": "200"},
        {"ID": "SO-3", "Amount": "300"},
    ]
