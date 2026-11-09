"""Replaying a recorded web procedure on the practice site (SOP_TO_WORKFLOW W2)."""

import json
import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path
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


def test_inspect_dom_exposes_scoped_structure_beyond_first_page_without_secrets(
    browser: Any, site: PracticeSite
) -> None:
    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<section id=\"report\">' + "
        "Array.from({length: 100}, (_, i) => '<button data-automation-id=\"action-' "
        "+ i + '\">Action ' + i + '</button>').join('') + "
        "'<table id=\"grid\"><thead><tr><th>Order</th></tr></thead>' + "
        "'<tbody><tr><td>SO-1</td></tr></tbody></table>' + "
        '\'<input type="password" value="password-secret">'
        '<input name="token" value="token-secret">\' + '
        "'<textarea>textarea-secret</textarea>"
        '<input type="hidden" value="hidden-secret"></section>\';'
    )
    first = WebAction.model_validate(
        {"do": "inspect_dom", "scope": "#report", "limit": 80, "save_as": "dom"}
    )
    first_data = runner(browser, site).run(WebScript(actions=(first,)), "read").data["dom"]
    assert isinstance(first_data, dict) and first_data["next_offset"] == 80
    later = first.model_copy(update={"offset": 80})
    data = runner(browser, site).run(WebScript(actions=(later,)), "read").data["dom"]
    assert isinstance(data, dict) and data["next_offset"] is None
    serialized = json.dumps(data)
    assert "action-99" in serialized and "SO-1" in serialized and '"tag": "th"' in serialized
    assert '"parent"' in serialized and '"path"' in serialized
    for secret in ("password-secret", "token-secret", "textarea-secret", "hidden-secret"):
        assert secret not in serialized
    assert (
        browser.evaluate("document.querySelector('input[type=password]').value")
        == "password-secret"
    )


def test_inspect_dom_refuses_ambiguous_scopes_invalid_css_and_other_origins(browser, site) -> None:  # type: ignore[no-untyped-def]
    browser.navigate(site.url)
    browser.evaluate("document.body.innerHTML = '<div>A</div><div>B</div>'")
    for scope, code in (
        ("div", "web_scope_ambiguous"),
        ("[", "web_selector_invalid"),
        ("#missing", "web_scope_missing"),
    ):
        action = WebAction.model_validate({"do": "inspect_dom", "scope": scope, "save_as": "dom"})
        with pytest.raises(WebScriptError) as stopped:
            runner(browser, site).run(WebScript(actions=(action,)), "read")
        assert stopped.value.code == code
        assert stopped.value.action_index == 0 and stopped.value.action_kind == "inspect_dom"
    with pytest.raises(WebScriptError) as stopped:
        ScriptRunner(browser, ("https://different.example",)).run(
            WebScript(actions=(action,)), "read"
        )
    assert stopped.value.code == "web_origin_not_allowed"


def test_failed_browser_capability_returns_live_page_and_safe_fields(
    browser: Any, site: PracticeSite, tmp_path: Path
) -> None:
    from capabilities.browser_session.handlers import (
        BrowserRequest,
        BrowserResult,
        BrowserSessionHandler,
    )
    from capabilities.runtime import CapabilityExecutionFailed

    class ExistingBrowser:
        def start(self) -> None:
            pass

        def __getattr__(self, name: str) -> Any:
            return getattr(browser, name)

    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<h1>Fresh report</h1>' + "
        '\'<button id="run" data-testid="run-report">Run</button>\' + '
        '\'<input type="password" value="secret-password">\' + '
        '\'<input name="api_key" value="secret-token">\' + '
        "'<textarea>private note</textarea><span>password=inline-secret</span>';"
    )
    run = BrowserSessionHandler(
        (site.url,),
        tmp_path / "profile",
        headless=True,
        timeout_s=0.1,
        workspace_roots=(),
        browser_factory=ExistingBrowser,
    )
    observed = run.run(BrowserRequest())
    assert "Fresh report" in observed.page and "run-report" in observed.page
    with pytest.raises(CapabilityExecutionFailed) as stopped:
        run.run(
            BrowserRequest.model_validate(
                {"actions": [{"do": "click", "target": {"css": "#missing"}}], "look": False}
            )
        )
    result = BrowserResult.model_validate(stopped.value.data)
    assert result.failed_action_index == 0 and result.failed_action_kind == "click"
    assert "Fresh report" in result.page and result.diagnostics is not None
    serialized = json.dumps(result.model_dump(mode="json")) + observed.page
    for secret in ("secret-password", "secret-token", "private note", "inline-secret"):
        assert secret not in serialized


def test_browser_failure_does_not_inspect_a_disallowed_origin(
    browser: Any, site: PracticeSite, tmp_path: Path
) -> None:
    from capabilities.browser_session.handlers import (
        BrowserRequest,
        BrowserResult,
        BrowserSessionHandler,
    )
    from capabilities.runtime import CapabilityExecutionFailed

    class ExistingBrowser:
        def start(self) -> None:
            pass

        def __getattr__(self, name: str) -> Any:
            return getattr(browser, name)

    browser.navigate(site.url)
    browser.evaluate("document.body.innerHTML = '<h1>Forbidden origin secret</h1>'")
    run = BrowserSessionHandler(
        ("https://different.example",),
        tmp_path / "profile",
        headless=True,
        timeout_s=0.1,
        workspace_roots=(),
        browser_factory=ExistingBrowser,
    )
    with pytest.raises(CapabilityExecutionFailed) as stopped:
        run.run(
            BrowserRequest.model_validate({"actions": [{"do": "inspect_dom", "save_as": "dom"}]})
        )
    result = BrowserResult.model_validate(stopped.value.data)
    assert result.diagnostics is None and result.diagnostic_error == "web_origin_not_allowed"
    assert result.page == "" and result.url == ""
    assert "Forbidden origin secret" not in json.dumps(result.model_dump(mode="json"))


def test_read_only_inspection_alias_reads_real_page_and_preserves_failure(
    browser: Any, site: PracticeSite, tmp_path: Path
) -> None:
    import asyncio

    from pydantic import JsonValue

    from agent.gateway import HostToolOutcome
    from capabilities.browser_session.handlers import (
        SPEC,
        BrowserRequest,
        BrowserResult,
        BrowserSessionHandler,
    )
    from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
    from common.assets import ExecutionDependencies
    from common.execution import RequestContext, TraceIdentifiers
    from host_runtime.bridge_tools import bridge_tools
    from workflow.dispatch import BridgeExecutor

    class ExistingBrowser:
        def start(self) -> None:
            pass

        def __getattr__(self, name: str) -> Any:
            return getattr(browser, name)

    browser.navigate(site.url)
    browser.evaluate(
        "window.__clicked = 0; document.body.innerHTML = '<h1>Current report</h1>' + "
        "'<section id=\"report\">' + Array.from({length:100}, (_, i) => "
        "'<button data-automation-id=\"action-' + i + '\">Action ' + i + "
        "'</button>').join('') + '</section>';"
        "document.body.addEventListener('click', () => window.__clicked++);"
    )
    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        BrowserSessionHandler(
            (site.url,),
            tmp_path / "profile",
            headless=True,
            timeout_s=0.1,
            workspace_roots=(),
            browser_factory=ExistingBrowser,
        ),
        BrowserRequest,
        BrowserResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="owner",
        asset=SPEC.identity,
        permissions=SPEC.policy.required_permissions,
        policy_refs=SPEC.policy.policy_refs,
        approval_ref="owner-approved",
    )
    tool = next(
        tool
        for tool in bridge_tools(BridgeExecutor(installed, LocalPolicy((grant,))))
        if tool.tool.name == "browser__inspect"
    )
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="inspect",
    )

    async def observe(arguments: dict[str, JsonValue]) -> HostToolOutcome:
        return await tool.handler(context, arguments)

    result = asyncio.run(observe({"scope": "#report", "offset": 80, "limit": 30}))
    assert result.status == "succeeded" and isinstance(result.data, dict)
    assert "action-99" in json.dumps(result.data["data"])
    assert browser.evaluate("window.__clicked") == 0
    failure = asyncio.run(observe({"scope": "#missing"}))
    assert failure.status == "failed" and failure.failure is not None
    assert failure.failure.code == "web_scope_missing"
    assert isinstance(failure.data, dict) and failure.data["failed_action_kind"] == "inspect_dom"
    assert "Current report" in json.dumps(failure.data["diagnostics"])
    assert browser.evaluate("window.__clicked") == 0


def test_browser_overview_finds_late_visible_controls_without_field_values(
    browser: Any, site: PracticeSite, tmp_path: Path
) -> None:
    from capabilities.browser_session.handlers import BrowserRequest, BrowserSessionHandler

    class ExistingBrowser:
        def start(self) -> None:
            pass

        def __getattr__(self, name: str) -> Any:
            return getattr(browser, name)

    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<div hidden>' + '<div>Hidden header</div>'.repeat(500) + "
        "'</div>' + '<div>Visible report context</div>'.repeat(400) + "
        '\'<button id="sales" data-automation-id="sales-nav"><span>Sales</span></button>\' + '
        "'<label for=\"filter\">Customer filter</label>' + "
        '\'<input id="filter" value="private-field">\' + '
        '\'<input type="password" value="private-password"><textarea>private-note</textarea>\' + '
        "'<div contenteditable=true>private-editor</div><span>password=private-inline</span>' + "
        "'<table id=\"orders\"><thead><tr><th>Order ID</th></tr></thead>' + "
        "'<tbody><tr><td>SO-1</td></tr></tbody></table>' + "
        "'<button>Other</button>'.repeat(100);"
    )
    run = BrowserSessionHandler(
        (site.url,),
        tmp_path / "profile",
        headless=True,
        timeout_s=2,
        workspace_roots=(),
        browser_factory=ExistingBrowser,
    )
    result = run.run(BrowserRequest())
    assert "Sales" in result.page and "sales-nav" in result.page
    inspected = (
        runner(browser, site)
        .run(
            WebScript(actions=(WebAction.model_validate({"do": "inspect_dom", "save_as": "dom"}),)),
            "read",
        )
        .data["dom"]
    )
    assert isinstance(inspected, dict) and isinstance(inspected["overview"], dict)
    overview = inspected["overview"]
    assert isinstance(overview["text"], str) and len(overview["text"]) <= 6000
    assert overview["text_truncated"] is True and overview["controls_truncated"] is True
    assert isinstance(overview["controls"], list) and 0 < len(overview["controls"]) <= 80
    assert "sales-nav" in json.dumps(overview["controls"])
    assert len(json.dumps(overview)) <= 9000
    assert "sales-nav" in json.dumps(inspected)[:16000]
    assert "orders" in json.dumps(overview["tables"])
    serialized = json.dumps(overview) + result.page
    for secret in (
        "private-field",
        "private-password",
        "private-note",
        "private-editor",
        "private-inline",
        "Hidden header",
    ):
        assert secret not in serialized
    assert "sales-nav" not in json.dumps(inspected["elements"])
    assert inspected["next_offset"] == 80


def test_overview_prioritizes_late_navigation_and_bounds_serialized_unicode(
    browser: Any, site: PracticeSite
) -> None:
    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<button>Dashboard tile</button>'.repeat(100) + "
        '\'<nav><button role="menuitem" id="sales">Sales</button></nav>\' + '
        "'<div>' + '中文測試內容'.repeat(2000) + '</div>' + "
        "('<button>' + '中文標籤'.repeat(20) + '</button>').repeat(100);"
    )
    inspected = runner(browser, site).inspect()
    overview = inspected["overview"]
    assert isinstance(overview, dict) and isinstance(overview["controls"], list)
    assert isinstance(overview["controls"][0], dict)
    assert overview["controls"][0]["path"] == "#sales"
    assert len(json.dumps(overview, ensure_ascii=True)) <= 9000
    assert overview["controls_truncated"] is True
    assert "Sales" in json.dumps(inspected, ensure_ascii=True)[:16000]


def test_overview_reports_its_cooperative_time_budget(browser: Any, site: PracticeSite) -> None:
    browser.navigate(site.url)
    browser.evaluate(
        "document.body.innerHTML = '<button>Sales</button>';"
        "window.__savedNow = Object.getOwnPropertyDescriptor(performance, 'now');"
        "window.__nowCalls = 0; Object.defineProperty(performance, 'now', {configurable:true,"
        "value: () => ++window.__nowCalls * 1001}); true;"
    )
    try:
        inspected = runner(browser, site).inspect()
        overview = inspected["overview"]
        assert isinstance(overview, dict) and overview["time_limit_reached"] is True
        assert overview["visited_nodes"] == 0
        assert inspected["time_limit_reached"] is True
    finally:
        browser.evaluate(
            "if (window.__savedNow) Object.defineProperty(performance, 'now', window.__savedNow);"
            "else delete performance.now; true;"
        )


def test_overview_keeps_late_search_fields_and_toolbar_before_table_record_links(
    browser: Any, site: PracticeSite, tmp_path: Path
) -> None:
    from capabilities.browser_session.handlers import BrowserRequest, BrowserSessionHandler

    class ExistingBrowser:
        def start(self) -> None:
            pass

        def __getattr__(self, name: str) -> Any:
            return getattr(browser, name)

    browser.navigate(site.url)
    rows = "".join(
        "<tr>"
        + "".join(f'<td><a href="#record">Record {i}-{j}</a></td>' for j in range(4))
        + "<td><button>Row action</button></td></tr>"
        for i in range(100)
    )
    html = (
        f"<table><tbody>{rows}</tbody></table>"
        '<div role="toolbar"><button id="search" aria-expanded="false" '
        'aria-pressed="true">Advanced Search</button></div>'
        '<label for="date">Order Date</label><input id="date" type="date" '
        'placeholder="Start date" value="2026-01-01">'
        '<a id="plain" href="#help">Unscoped help</a>'
        '<nav><a id="sales-nav" href="#sales">Sales</a></nav>'
    )
    browser.evaluate("document.body.innerHTML = " + json.dumps(html))
    inspected = runner(browser, site).inspect()
    overview = inspected["overview"]
    assert isinstance(overview, dict) and isinstance(overview["controls"], list)
    controls = [control for control in overview["controls"] if isinstance(control, dict)]
    paths = [control["path"] for control in controls]
    assert paths[0] == "#sales-nav" and "#search" in paths and "#date" in paths
    search = next(control for control in controls if control["path"] == "#search")
    date = next(control for control in controls if control["path"] == "#date")
    assert search["state"] == {"expanded": "false", "pressed": "true"}
    assert date["state"] == {"placeholder": "Start date", "type": "date"}
    assert "2026-01-01" not in json.dumps(overview)
    assert len(json.dumps(overview)) <= 9000 and overview["controls_truncated"] is True
    run = BrowserSessionHandler(
        (site.url,),
        tmp_path / "profile",
        headless=True,
        timeout_s=2,
        workspace_roots=(),
        browser_factory=ExistingBrowser,
    )
    page = run.run(BrowserRequest()).page
    assert "Advanced Search" in page and "Order Date" in page and "expanded='false'" in page


def test_standard_accessible_names_are_shared_by_overview_and_target_matching(
    browser: Any, site: PracticeSite
) -> None:
    browser.navigate(site.url)
    html = (
        '<span id="first" hidden>Order</span><span id="second">Date</span>'
        '<input id="aria" name="order_date" aria-labelledby="missing first second" '
        'aria-describedby="help" aria-label="Wrong fallback" value="private-date">'
        '<span id="help">Date guidance</span>'
        '<label for="native">Customer</label><label for="native">Code</label><input id="native">'
        '<label>Owner<input id="wrapped" value="private-owner"></label>'
        '<span id="verb">Run</span><span id="noun">report</span>'
        '<button id="run" aria-labelledby="verb noun">Contradictory visible text</button>'
        '<input id="continue" type="button" value="Continue">'
        '<input id="fallback" aria-labelledby="does-not-exist" aria-label="Safe fallback">'
        '<textarea id="private-note">private-note-value</textarea>'
        '<div id="private-editor" contenteditable=true>private-editor-value</div>'
        '<input id="privacy" aria-labelledby="private-note private-editor" aria-label="Safe name">'
    )
    browser.evaluate(
        "document.body.innerHTML = " + json.dumps(html) + ";"
        "window.__namedClick=false;document.getElementById('run').addEventListener('mouseup',"
        "e=>window.__namedClick=e.isTrusted);"
    )
    inspected = runner(browser, site).inspect()
    overview = inspected["overview"]
    assert isinstance(overview, dict) and isinstance(overview["controls"], list)
    controls = {
        control["path"]: control for control in overview["controls"] if isinstance(control, dict)
    }
    expected = {
        "#aria": "Order Date",
        "#native": "Customer Code",
        "#wrapped": "Owner",
        "#run": "Run report",
        "#continue": "Continue",
        "#fallback": "Safe fallback",
        "#privacy": "Safe name",
    }
    for path, name in expected.items():
        assert controls[path]["label"] == name
    for path in ("#aria", "#native", "#wrapped"):
        action = WebAction(
            do="fill",
            target=WebTarget(label=str(controls[path]["label"]), kind="field"),
            value="chosen",
        )
        runner(browser, site).run(WebScript(actions=(action,)), "act")
    action = WebAction(
        do="click", target=WebTarget(label=str(controls["#run"]["label"]), kind="button")
    )
    runner(browser, site).run(WebScript(actions=(action,)), "act")
    assert browser.evaluate("window.__namedClick") is True
    assert (
        browser.evaluate(
            "['aria','native','wrapped'].every(id=>document.getElementById(id).value==='chosen')"
        )
        is True
    )
    serialized = json.dumps(inspected)
    for secret in ("private-date", "private-owner", "private-note-value", "private-editor-value"):
        assert secret not in serialized
    elements = inspected["elements"]
    assert isinstance(elements, list)
    attribute_sets = []
    for element in elements:
        if isinstance(element, dict):
            attributes = element.get("attributes")
            if isinstance(attributes, dict):
                attribute_sets.append(attributes)
    attrs = next(attributes for attributes in attribute_sets if attributes.get("id") == "aria")
    assert attrs["aria-labelledby"] == "missing first second"
    assert attrs["aria-describedby"] == "help" and attrs["name"] == "order_date"
    assert any(attributes.get("for") == "native" for attributes in attribute_sets)


@pytest.mark.parametrize(
    "current,total",
    [
        ({"css": "#page", "kind": "field"}, {"css": "#page", "kind": "any"}),
        ({"css": "  #page  "}, {"css": "#page"}),
        ({"label": "Page number", "kind": "field"}, {"label": "Page number", "kind": "field"}),
    ],
)
def test_pagination_rejects_reusing_current_control_as_total(
    current: dict[str, str], total: dict[str, str]
) -> None:
    from pydantic import ValidationError

    from integrations.web_script import WebPagination

    with pytest.raises(ValidationError) as invalid:
        WebPagination.model_validate({"next": {"css": "#next"}, "current": current, "total": total})
    assert invalid.value.errors()[0]["type"] == "pagination_controls_must_differ"


def test_pagination_invalid_input_reaches_bridge_before_browser_start(tmp_path: Path) -> None:
    import asyncio

    from capabilities.browser_session.handlers import (
        SPEC,
        BrowserRequest,
        BrowserResult,
        BrowserSessionHandler,
    )
    from capabilities.runtime import (
        CapabilityGrant,
        CapabilityInvocation,
        InstalledCapabilities,
        LocalPolicy,
    )
    from common.assets import ExecutionDependencies
    from common.execution import RequestContext, TraceIdentifiers
    from workflow.dispatch import BridgeExecutor

    starts: list[bool] = []

    def browser_factory() -> Any:
        starts.append(True)
        raise AssertionError("invalid pagination must stop before the browser")

    installed = InstalledCapabilities()
    installed.register(
        SPEC,
        BrowserSessionHandler(
            ("https://example.test",),
            tmp_path / "profile",
            headless=True,
            timeout_s=2,
            workspace_roots=(),
            browser_factory=browser_factory,
        ),
        BrowserRequest,
        BrowserResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="owner",
        asset=SPEC.identity,
        permissions=SPEC.policy.required_permissions,
        policy_refs=SPEC.policy.policy_refs,
        approval_ref="owner-approved",
    )
    context = RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor="owner",
        namespace="engineering",
        channel="local",
        message="read all pages",
    )
    result = asyncio.run(
        BridgeExecutor(installed, LocalPolicy((grant,))).execute(
            CapabilityInvocation(
                context=context,
                target=SPEC.identity,
                arguments={
                    "actions": [
                        {
                            "do": "read_table",
                            "table": "#rows",
                            "save_as": "rows",
                            "pagination": {
                                "next": {"css": "#next"},
                                "current": {"css": "#page", "kind": "field"},
                                "total": {"css": "#page", "kind": "any"},
                            },
                        }
                    ]
                },
            )
        )
    )
    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "invalid_input"
    assert "pagination_controls_must_differ" in result.failure.message
    assert starts == []


def test_distinct_pagination_controls_can_both_display_25_on_last_page(
    browser: Any, site: PracticeSite
) -> None:
    paginated_page(browser, site)
    browser.evaluate("document.getElementById('total').innerText='/ 25'")
    result = ScriptRunner(browser, (site.url,), settle_s=0, timeout_s=2).run(
        WebScript(actions=(paginated_action(25),)), "act"
    )
    rows = result.data["orders"]
    assert isinstance(rows, list) and len(rows) == 25
    assert rows[-1] == {"ID": "SO-25", "Amount": "2500"}
    assert browser.evaluate("document.getElementById('page').value") == "25"
    assert browser.evaluate("document.getElementById('total').innerText") == "/ 25"


def test_invalid_field_state_is_observed_without_turning_fill_into_failure(
    browser: Any, site: PracticeSite
) -> None:
    from capabilities.browser_session.handlers import _described
    from integrations.web_script import DOMInspection

    browser.navigate(site.url)
    html = (
        '<input id="date-invalid" aria-label="Report date" aria-invalid="true" '
        'value="private-invalid-date">'
        '<input id="email-invalid" type="email" aria-label="Contact email" '
        'value="private-invalid-email">'
    )
    browser.evaluate(
        "document.body.innerHTML = " + json.dumps(html) + ";"
        "document.getElementById('date-invalid').addEventListener('input',e=>"
        "e.target.setAttribute('aria-invalid','false'));"
    )
    before = runner(browser, site).inspect()
    overview = before["overview"]
    assert isinstance(overview, dict) and isinstance(overview["controls"], list)
    controls = [control for control in overview["controls"] if isinstance(control, dict)]
    assert all(
        isinstance(control["state"], dict) and control["state"]["invalid"] is True
        for control in controls
    )
    assert "invalid=True" in _described(DOMInspection.model_validate(before))
    elements = before["elements"]
    assert isinstance(elements, list)
    assert any(
        isinstance(element, dict)
        and isinstance(element.get("attributes"), dict)
        and element["attributes"]
        == {"id": "date-invalid", "aria-label": "Report date", "aria-invalid": "true"}
        for element in elements
    )
    result = runner(browser, site).run(
        WebScript(
            actions=(
                WebAction(
                    do="fill",
                    target=WebTarget(label="Report date", kind="field"),
                    value="new-private-date",
                ),
            )
        ),
        "act",
    )
    assert result.data == {}
    after = runner(browser, site).inspect()
    after_overview = after["overview"]
    assert isinstance(after_overview, dict) and isinstance(after_overview["controls"], list)
    date = next(
        control
        for control in after_overview["controls"]
        if isinstance(control, dict) and control["path"] == "#date-invalid"
    )
    assert (
        isinstance(date, dict)
        and isinstance(date["state"], dict)
        and "invalid" not in date["state"]
    )
    for value in ("private-invalid-date", "private-invalid-email", "new-private-date"):
        assert value not in json.dumps(before) + json.dumps(after)


def test_pagination_rejects_distinct_locators_resolving_to_the_same_control(
    browser: Any, site: PracticeSite
) -> None:
    paginated_page(browser, site)
    browser.evaluate(
        "window.__pagingClicks=0;document.getElementById('next').addEventListener('mouseup',()=>window.__pagingClicks++)"
    )
    action = paginated_action().model_dump(mode="json")
    assert isinstance(action["pagination"], dict)
    action["pagination"]["total"] = {"css": "input#page", "kind": "field"}
    parsed = WebAction.model_validate(action)
    with pytest.raises(WebScriptError) as failed:
        runner(browser, site).run(WebScript(actions=(parsed,)), "act")
    assert failed.value.code == "pagination_controls_must_differ"
    assert failed.value.action_kind == "read_table" and failed.value.action_index == 0
    assert browser.evaluate("window.__pagingClicks") == 0
