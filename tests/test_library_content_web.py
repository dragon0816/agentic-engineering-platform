"""Agent Web: one-click Member Portal and Library card content (owner
2026-10-15, `docs/phases/PLATFORM_OVERVIEW.md` "One-click sign-in from Agent
Web" and "Library card content in Agent Web").

"Open Marketplace" opens the portal already signed in as this PC's member:
Agent Web, server side, trades the Personal Agent's session for a single-use
ticket and returns `<portal>/#ticket=...`; without a saved Personal Agent code
it returns the plain sign-in page with a note. A Library card shows the
version's published content (`assets/manifest`), fetched as the member and
rendered safely. Everything runs against a real in-process shared platform.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from test_capability_shelf import REFERENCE, _published
from test_host_wiring import ready
from test_member_publish import _signed_in, workflow_manifest
from test_shared_platform_app import request
from test_shared_platform_settings import _agent_login, _card, _host, _web

from control_plane.app import SharedPlatformApplication
from host_runtime.contracts import CompanyHostConfiguration
from host_runtime.host import build_runtime
from host_runtime.shared_platform import LOGIN_VARIABLE, TOKEN_VARIABLE
from host_runtime.web import AgentWeb
from host_runtime.web_page import PAGE
from integrations.browser import browser_path

SKILL_TEXT = (
    "## How it works\n\nRun **the weekly check** with `run`.\n\n"
    "<script>window.__pwned=1</script>\n\n<img src=x onerror=window.__pwned=2>\n\n"
    "[docs](https://example.invalid/docs) [bad](javascript:window.__pwned=3) "
    "[mail](mailto:someone@example.invalid)"
)


@pytest.fixture
def app(tmp_path: Path) -> Iterator[SharedPlatformApplication]:
    platform = SharedPlatformApplication.empty(
        administrators=("platform-admin",), registry_path=tmp_path / "registry.sqlite"
    )
    with platform:
        yield platform


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (TOKEN_VARIABLE, LOGIN_VARIABLE, "AEP_LOCAL_PLATFORM_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    from host_runtime import platform_publish

    monkeypatch.setattr(platform_publish, "_saved_user_variable", lambda name: None)


def _skill(name: str, instructions: str) -> dict[str, Any]:
    return {
        "metadata": {
            "identity": {"namespace": "lab", "name": name, "version": "0.1.0"},
            "owner": {"type": "user", "id": "anyone"},
            "visibility": "organization",
        },
        "alias": name.replace("-", ""),
        "instructions": instructions,
        "commands": [
            {
                "name": "run",
                "kind": "workflow",
                "target": {"namespace": "lab", "name": "weekly-check", "version": "1.0.0"},
            }
        ],
        "rules": [{"pattern": "weekly (numbers|check)", "command": "run"}],
        "default_command": "run",
        "selector_hint": "Weekly numbers of the lab",
    }


def _publish(
    app: SharedPlatformApplication,
    author: str,
    kind: str,
    manifest: dict[str, Any],
    visibility: str = "organization",
) -> None:
    portal = app.member_base_url + "/v1/member/"
    status, submitted = request(
        portal + "assets/submit",
        authorization=author,
        body={"kind": kind, "change": "minor", "visibility": visibility, "manifest": manifest},
    )
    assert status == 200, submitted
    root = getattr(app, "_test_root", None)
    if root is None:
        root = _signed_in(app, "root", "platform_admin")
        app._test_root = root  # type: ignore[attr-defined]
    status, approved = request(
        portal + "admin/submissions/approve",
        authorization=root,
        body={"submission_id": submitted["submission"]["submission_id"], "evidence": "read it"},
    )
    assert status == 200, approved


def _connected(
    app: SharedPlatformApplication, tmp_path: Path, runtime: Any, path: Path, engineer: str
) -> AgentWeb:
    web = _web(runtime, path, {})
    assert web.update_shared_platform(_card(app, _agent_login(app, engineer)))["ok"]
    return web


# -- One-click Member Portal --------------------------------------------------


def test_open_marketplace_gets_a_single_use_ticket_in_the_fragment(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    _published(app)
    path, layout = _host(tmp_path)
    engineer = _signed_in(app, "engineer", "member")
    login = _agent_login(app, engineer)
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, {})
        assert web.update_shared_platform(_card(app, login))["ok"]
        link = web.portal_link("marketplace", REFERENCE)
        assert link["ok"] is True and link["signed_in"] is True, link
        url = link["url"]
        parts = urlsplit(url)
        assert url.startswith(app.member_base_url + "/#ticket=")
        assert parts.query == "" and "?" not in url
        place = parse_qs(parts.fragment)
        assert place["tab"] == ["marketplace"] and place["asset"] == [REFERENCE]
        assert place["bridge"] == [runtime.config.device.bridge_id]
        ticket = place["ticket"][0]
        # The Personal Agent's own login never goes into the address.
        assert login not in url and login.partition(":")[2] not in url
        # The ticket signs a browser in as this PC's member, once.
        status, signed = request(
            app.member_base_url + "/v1/member/sign-in/ticket",
            authorization=f"Ticket {ticket}",
            method="POST",
        )
        assert status == 200, signed
        status, me = request(
            app.member_base_url + "/v1/member/me",
            authorization=f"Bearer {signed['session']}",
            body={},
        )
        assert me["actor"] == "engineer"
        assert (
            request(
                app.member_base_url + "/v1/member/sign-in/ticket",
                authorization=f"Ticket {ticket}",
                method="POST",
            )[0]
            == 409
        )
        # A fresh ticket each time; nothing recorded in the task list.
        again = web.portal_link()
        assert again["signed_in"] is True and again["url"] != url
        assert "tab=" not in again["url"] and "asset=" not in again["url"]
        assert ticket.partition(":")[2] not in json.dumps(web.task_list())
        assert web.portal_link("Market!")["code"] == "tab_invalid"
        assert web.portal_link("marketplace", "not a reference")["code"] == "bad_reference"


def test_open_marketplace_without_a_code_opens_the_sign_in_page_with_a_note(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    config, _ = ready(tmp_path / "bare")
    with build_runtime(config) as runtime:
        missing = AgentWeb(runtime).portal_link("marketplace")
        assert missing["ok"] is False and missing["code"] == "portal_not_configured"
        assert "Settings > Shared platform" in missing["message"]

    path, layout = _host(tmp_path)
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _web(runtime, path, {})
        assert web.update_shared_platform(_card(app, enroll=False))["ok"]
        plain = web.portal_link("marketplace")
        assert plain["ok"] is True and plain["signed_in"] is False, plain
        assert "ticket" not in plain["url"]
        assert plain["url"].startswith(app.member_base_url + "/#")
        assert "Settings > Shared platform" in plain["message"]
        assert "Personal Agent code" in plain["message"]
        no_code = web.asset_content("workflow", REFERENCE)
        assert no_code["code"] == "login_missing" and "Personal Agent code" in no_code["message"]

        # With a code of a member who was then disabled: the sign-in page.
        engineer = _signed_in(app, "engineer", "member")
        assert web.update_shared_platform(_card(app, _agent_login(app, engineer), enroll=False))[
            "ok"
        ]
        assert web.portal_link()["signed_in"] is True
        app.state.enrollment.disable_user("platform-admin", "engineer")
        web._member_publisher = (None, None)  # a new session, as after a restart
        refused = web.portal_link()
        assert refused["signed_in"] is False and "ticket" not in refused["url"]
        assert "disabled" in refused["message"] and "Settings" in refused["message"]

        # The portal stops answering.
        assert web.update_shared_platform(
            {**_card(app, enroll=False), "member_portal_url": "http://127.0.0.1:9"}
        )["ok"]
        gone = web.portal_link()
        assert gone["signed_in"] is False and gone["url"].startswith("http://127.0.0.1:9/")
        assert "did not answer" in gone["message"]


# -- Library card content -----------------------------------------------------


def test_card_content_is_read_as_the_member_only_when_shared(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    _published(app)
    anna = _signed_in(app, "anna", "member")
    _publish(app, anna, "workflow", workflow_manifest("private-check"), visibility="private")
    _publish(app, anna, "skill", _skill("weekly-guide", SKILL_TEXT))
    path, layout = _host(tmp_path)
    engineer = _signed_in(app, "engineer", "member")
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _connected(app, tmp_path, runtime, path, engineer)
        shown = web.asset_content("workflow", REFERENCE)
        assert shown["ok"] is True, shown
        content = shown["content"]
        assert content["package"]["kind"] == "workflow"
        assert content["manifest"]["steps"] and content["manifest"]["description"]
        assert content["owner"] == {"type": "user", "id": "leo"}
        assert content["versions"] == ["1.0.0"] and content["visibility"] == "organization"
        skill = web.asset_content("skill", "lab/weekly-guide@1.0.0")
        assert skill["ok"] is True and skill["content"]["manifest"]["instructions"] == SKILL_TEXT

        hidden = web.asset_content("workflow", "lab/private-check@1.0.0")
        assert hidden["ok"] is False and hidden["code"] == "content_not_shared"
        assert "not shared" in hidden["message"]
        assert web.asset_content("workflow", "lab/nothing@9.9.9")["code"] == ("content_not_shared")
        assert web.asset_content("workflow", "nope")["code"] == "bad_reference"
        assert web.asset_content("knowledge", REFERENCE)["code"] == "bad_reference"

        # The portal stops answering.
        assert web.update_shared_platform(
            {**_card(app, enroll=False), "member_portal_url": "http://127.0.0.1:9"}
        )["ok"]
        gone = web.asset_content("workflow", REFERENCE)
        assert gone["code"] == "platform_unreachable" and "did not answer" in gone["message"]

    config, _ = ready(tmp_path / "bare")
    with build_runtime(config) as runtime:
        bare = AgentWeb(runtime).asset_content("workflow", REFERENCE)
        assert bare["code"] == "platform_not_configured"
        assert "Settings > Shared platform" in bare["message"]


def _post(served: Any, path: str, body: object, token: str | None) -> tuple[int, dict]:
    host, port = served.server_address[0], served.server_address[1]
    sent = urllib.request.Request(
        f"http://{host}:{port}{path}", method="POST", data=json.dumps(body).encode("utf-8")
    )
    sent.add_header("Content-Type", "application/json")
    if token is not None:
        sent.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(sent, timeout=30) as answer:
            return answer.status, json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


def test_the_routes_need_the_page_token_and_validate_their_body(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    from host_runtime.web import AgentWebServer

    _published(app)
    path, layout = _host(tmp_path)
    engineer = _signed_in(app, "engineer", "member")
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _connected(app, tmp_path, runtime, path, engineer)
        served = AgentWebServer(web)
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        try:
            for route, body in (
                ("/api/platform/portal-link", {"tab": "marketplace"}),
                ("/api/platform/asset-content", {"kind": "workflow", "asset": REFERENCE}),
            ):
                assert _post(served, route, body, None)[0] == 401
                assert _post(served, route, body, "wrong")[0] == 401
                status, reply = _post(served, route, body, served.token)
                assert status == 200 and reply["ok"] is True, reply
            status, reply = _post(served, "/api/platform/portal-link", {"tab": 3}, served.token)
            assert status == 400 and reply["code"] == "portal_request_invalid"
            status, reply = _post(
                served, "/api/platform/asset-content", {"kind": "workflow"}, served.token
            )
            assert status == 400 and reply["code"] == "asset_request_invalid"
        finally:
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)


def test_the_page_has_the_portal_and_content_hooks() -> None:
    for hook in (
        "/api/platform/portal-link",
        "/api/platform/asset-content",
        "async function openPortal(",
        'window.open("about:blank", "_blank")',
        "opened.opener = null",
        "function contentMarkdown(",
        "function workflowContent(",
        "function skillContent(",
        "function fillMarketContent(",
        "Run parameters",
        "Keyword rules",
        "Selector hint",
        "Script tools",
        "Checks after the run",
        "Risk, permissions and side effects",
        "Other versions",
        "Reviewed",
        "market-content",
        "market-aside",
        "const marketContent = new Map()",
    ):
        assert hook in PAGE, hook
    # The shared renderer escapes: every value is a text node, links only
    # through safeMarkdownHref; card content keeps http(s) links only.
    start = PAGE.index("function renderMarkdown(")
    renderer = PAGE[start : PAGE.index("function renderAnswer(")]
    assert "innerHTML" not in renderer
    assert 'protocol !== "http:" && protocol !== "https:"' in PAGE


@pytest.mark.skipif(browser_path() is None, reason="no Chromium browser is installed")
def test_a_library_card_shows_its_content_safely_in_a_real_browser(
    app: SharedPlatformApplication,
    tmp_path: Path,
) -> None:
    from host_runtime.web import AgentWebServer
    from integrations.browser import Browser

    _published(app)
    anna = _signed_in(app, "anna", "member")
    _publish(app, anna, "skill", _skill("weekly-guide", SKILL_TEXT))
    _publish(app, anna, "skill", _skill("weekly-helper", "Short and plain."))
    path, layout = _host(tmp_path)
    engineer = _signed_in(app, "engineer", "member")
    with build_runtime(
        CompanyHostConfiguration.model_validate_json(path.read_text("utf-8")), layout=layout
    ) as runtime:
        web = _connected(app, tmp_path, runtime, path, engineer)
        served = AgentWebServer(web)
        thread = threading.Thread(target=served.serve_forever, daemon=True)
        thread.start()
        browser = Browser(
            tmp_path / "browser", timeout_s=60, extra_arguments=("--window-size=1400,1000",)
        )
        browser.start()

        def js(code: str) -> Any:
            return browser._evaluate(code)

        def wait(expression: str, timeout: float = 30) -> object:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                value = js(expression)
                if value:
                    return value
                time.sleep(0.2)
            raise AssertionError(expression)

        def box(selector: str) -> dict[str, float]:
            return dict(
                json.loads(
                    str(
                        js(
                            "JSON.stringify((r => ({x: r.x, y: r.y, w: r.width, h: r.height}))("
                            f"document.querySelector({json.dumps(selector)}).getBoundingClientRect()))"
                        )
                    )
                )
            )

        def open_card(name: str) -> None:
            js(
                '[...document.querySelectorAll("#catalog .market-head")].find((b) => '
                f"b.textContent.includes({json.dumps(name)})).click(); 0"
            )

        try:
            browser.navigate(served.address)
            js('document.getElementById("nav-capabilities").click()')
            wait('document.querySelectorAll("#catalog .market-head").length === 2')
            heights = json.loads(
                str(
                    js(
                        'JSON.stringify([...document.querySelectorAll("#catalog .market-card")]'
                        ".map((c) => Math.round(c.getBoundingClientRect().height)))"
                    )
                )
            )
            assert max(heights) - min(heights) <= 1, heights  # uniform closed cards

            open_card("weekly-guide")
            wait(
                '(document.querySelector(".market-content") || {}).textContent'
                ' && document.querySelector(".market-content").textContent'
                '.includes("Keyword rules")'
            )
            content = str(js('document.querySelector(".market-content").textContent'))
            for words in (
                "How it works",
                "the weekly check",
                "Commands",
                "lab/weekly-check@1.0.0",
                "weekly (numbers|check)",
                "Weekly numbers of the lab",
                "/weeklyguide",
                "Script tools",
            ):
                assert words in content, words
            # A <script> in the instructions is shown as text and never runs.
            assert "<script>window.__pwned=1</script>" in content
            assert js("window.__pwned === undefined") is True
            assert (
                js(
                    'document.querySelectorAll(".market-content script, '
                    '.market-content img").length'
                )
                == 0
            )
            links = json.loads(
                str(
                    js(
                        "JSON.stringify([...document.querySelectorAll("
                        '".market-content a")].map((a) => a.href))'
                    )
                )
            )
            assert links == ["https://example.invalid/docs"], links
            assert js('document.querySelector(".market-md strong").textContent') == (
                "the weekly check"
            )
            facts = str(js('document.querySelector(".market-facts").textContent'))
            for words in (
                "Owner",
                "anna",
                "Other versions",
                "Who can use it",
                "Everyone in the organization",
                "Reviewed",
                "approved by root",
                "Published",
                "Depends on",
            ):
                assert words in facts, words
            assert "+ Add to this Agent" in str(
                js('document.querySelector(".market-aside").textContent')
            )
            # Measured: the open card spans the row, content and facts side by side.
            card, grid = box(".market-card[data-expanded]"), box("#catalog")
            assert abs(card["w"] - grid["w"]) <= 2, (card, grid)
            body, aside = box(".market-content"), box(".market-aside")
            assert body["w"] >= 300 and aside["w"] >= 200, (body, aside)
            assert aside["x"] > body["x"] + body["w"] - 1, (body, aside)
            assert (
                js("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
                is True
            )
            # A narrow Library: facts and actions first, content below, nothing wider.
            js('document.getElementById("catalog").style.width = "420px"; 0')
            body, aside = box(".market-content"), box(".market-aside")
            assert aside["y"] + aside["h"] <= body["y"] + 1, (body, aside)
            assert body["w"] <= 420 and aside["w"] <= 420, (body, aside)
            js('document.getElementById("catalog").style.width = ""; 0')

            # Kept per version for the page: reopening shows it at once.
            open_card("weekly-guide")
            wait('!document.querySelector(".market-card[data-expanded]")')
            open_card("weekly-guide")
            assert "Keyword rules" in str(
                js('document.querySelector(".market-content").textContent')
            )

            # A Workflow card: steps, parameters, risk and permissions.
            js('document.getElementById("market-tab-workflow").click()')
            open_card("weekly-check")
            wait(
                '(document.querySelector(".market-content") || {textContent: ""})'
                '.textContent.includes("Risk, permissions and side effects")'
            )
            content = str(js('document.querySelector(".market-content").textContent'))
            for words in (
                "What it does",
                "Check the weekly numbers.",
                "Steps",
                "Run parameters",
                "Checks after the run",
                "medium",
                "read_file",
            ):
                assert words in content, words

            # "Open Marketplace" asks for a ticket and opens it in the new tab.
            js(
                "window.__opened = []; window.open = () => ({opener: 1, close() {}, "
                "location: {replace: (u) => window.__opened.push(u)}}); 0"
            )
            js('document.getElementById("member-portal").click(); 0')
            wait("window.__opened.length === 1")
            opened = str(js("window.__opened[0]"))
            assert opened.startswith(app.member_base_url + "/#ticket=") and "?" not in opened
            assert "tab=marketplace" in opened
            assert "signed in as you" in str(
                js('document.getElementById("platform-sync-result").textContent')
            )
        finally:
            browser.close()
            browser.discard_profile()
            served.shutdown()
            served.server_close()
            thread.join(timeout=5)
