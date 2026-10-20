"""Files in the chat: the viewer panel and in-chat HTML (owner 2026-10-20).

Every file on an answer, and a file the person attached, is a chip that opens
the viewer panel (Preview / Code, like Codex and Claude Code). Files come only
through the token-checked, path-confined `/api/conversations/file`; an HTML
file renders only in a frame with `sandbox="allow-scripts"` (no
`allow-same-origin`), loaded from a short-lived `/view/file?nonce=` address
served with a strict CSP, so the page token never reaches the frame
(docs/DECISIONS.md 2026-10-20). The real Agent Web server; a real headless
browser when one is installed; screenshots in `.scratch/file-viewer/`.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_business_cards_capabilities import _bridge, _people, _run
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from host_runtime.conversations import ConversationMessage, ConversationRecord
from host_runtime.web import FILE_VIEW_CSP, AgentWeb
from host_runtime.web_page import PAGE

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "file-viewer"
SESSION = "fv-1"
MARKDOWN = "# 圖例標題\n\n<script>alert(1)</script>\n\n| 成員 | 主管 |\n|---|---|\n| 李 | 王 |\n"
TEXT = "<b>bold</b> & <img src=x onerror=alert(1)>\nsecond line\n"


def _seed(web: AgentWeb, tmp_path: Path) -> dict[str, Path]:
    """A conversation whose answer carries a real interactive org chart, a
    Markdown legend, a JSON file and a text file, and whose question carries
    an attached CSV; plus one listed file outside the workspace."""
    root = web.runtime.layout.workspace_root
    charts = root / "business-cards" / "me" / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    bridge = _bridge(tmp_path / "cards")
    _people(bridge)
    _run(
        bridge,
        "set-reporting-line",
        {
            "person": {"name": "李大華"},
            "manager": {"name": "王小明"},
            "evidence_kind": "user",
            "evidence_ref": "said so",
        },
    )
    drawn = _run(bridge, "org-chart", {"company": "範例科技", "format": "html"}).data
    assert drawn is not None
    files = {
        "html": charts / "org-範例科技.html",
        "md": charts / "org-範例科技.md",
        "json": charts / "data.json",
        "txt": charts / "notes.txt",
        "csv": root / "attachments" / SESSION / "table.csv",
        "outside": tmp_path / "outside.html",
    }
    shutil.copy(drawn["html_path"], files["html"])
    files["md"].write_text(MARKDOWN, encoding="utf-8")
    files["json"].write_text(
        json.dumps({"rows": list(range(30)), "tag": "<x>"}, indent=2), encoding="utf-8"
    )
    files["txt"].write_text(TEXT, encoding="utf-8")
    files["csv"].parent.mkdir(parents=True, exist_ok=True)
    files["csv"].write_text('name,title\n王小明,"協理, RF"\n', encoding="utf-8")
    files["outside"].write_text("<p>outside</p>", encoding="utf-8")
    now = datetime.now(UTC)

    def listed(*keys: str) -> tuple[dict[str, str], ...]:
        kinds = {"html": "html", "csv": "text"}
        return tuple(
            {"filename": files[key].name, "kind": kinds.get(key, "text"), "path": str(files[key])}
            for key in keys
        )

    web.runtime.state.create_conversation(
        ConversationRecord(
            session_id=SESSION,
            actor=web.runtime.actor,
            title="files",
            created_at=now,
            updated_at=now + timedelta(seconds=1),
            messages=(
                ConversationMessage(
                    message_id="fv-u",
                    role="user",
                    text="用 HTML 互動式呈現範例科技的組織圖",
                    created_at=now,
                    status="submitted",
                    attachments=listed("csv"),
                ),
                ConversationMessage(
                    message_id="fv-a",
                    role="assistant",
                    text="這是範例科技的互動式組織圖。",
                    created_at=now + timedelta(seconds=1),
                    status="answered",
                    attachments=listed("html", "md", "json", "txt", "outside"),
                ),
            ),
        )
    )
    return files


def _request(server: Any, path: str, *, token: bool = True) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_address[1]}{path}",
        headers={"Authorization": f"Bearer {server.token}"} if token else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as reply:
            return reply.status, dict(reply.headers), reply.read()
    except urllib.error.HTTPError as refused:
        return refused.code, dict(refused.headers), refused.read()


def _css(path: Path) -> str:
    """A path as a CSS string: CSS reads no JSON unicode escapes, so keep the text."""
    return json.dumps(str(path), ensure_ascii=False)


def _query(path: Path) -> str:
    from urllib.parse import urlencode

    return urlencode({"session_id": SESSION, "path": str(path)})


def test_an_html_file_is_served_sandboxed_by_a_short_lived_link_never_the_token(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    web, server, _recorder, _ = served
    files = _seed(web, tmp_path)
    # The link is asked for with the page token ...
    status, _, body = _request(server, "/api/conversations/view-link?" + _query(files["html"]))
    assert status == 200, body
    link = json.loads(body)
    assert link["ok"] and link["url"].startswith("/view/file?nonce=")
    assert server.token not in link["url"]
    refused, _, _ = _request(
        server, "/api/conversations/view-link?" + _query(files["html"]), token=False
    )
    assert refused == 401
    # ... and the file is let in by the nonce alone, sandboxed, with no network.
    status, headers, page = _request(server, link["url"], token=False)
    assert status == 200 and page.startswith(b"<!DOCTYPE html>")
    assert headers["Content-Security-Policy"] == FILE_VIEW_CSP
    for directive in (
        "default-src 'none'",
        "script-src 'unsafe-inline'",
        "style-src 'unsafe-inline'",
        "img-src data:",
        "sandbox allow-scripts",
        "frame-ancestors 'self'",
    ):
        assert directive in FILE_VIEW_CSP
    assert "allow-same-origin" not in FILE_VIEW_CSP
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert server.token.encode() not in page
    # A made-up or expired nonce shows nothing.
    assert _request(server, "/view/file?nonce=made-up", token=False)[0] == 404
    nonce = link["url"].split("nonce=", 1)[1]
    with web._file_views_lock:
        session, path, _ = web._file_views[nonce]
        web._file_views[nonce] = (session, path, time.monotonic() - 1)
    assert _request(server, link["url"], token=False)[0] == 404


def test_the_file_routes_refuse_anything_outside_the_listed_workspace_files(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    web, server, _recorder, _ = served
    files = _seed(web, tmp_path)
    # Only HTML gets a sandboxed view; a listed file outside the workspace,
    # an unlisted file and another conversation get nothing.
    for path in (files["md"], files["outside"], web.runtime.layout.workspace_root / "x.html"):
        assert _request(server, "/api/conversations/view-link?" + _query(path))[0] == 404
    assert web.conversation_view_link("other", str(files["html"]))["ok"] is False
    assert web.conversation_file(SESSION, str(files["outside"])) is None
    assert web.conversation_file(SESSION, str(tmp_path / "cards" / "workspace")) is None
    # Text, HTML included, comes back as plain text for the Code view; the
    # person's own attachment is listed too.
    status, headers, _ = _request(server, "/api/conversations/file?" + _query(files["html"]))
    assert status == 200 and headers["Content-Type"] == "text/plain; charset=utf-8"
    assert headers["X-Frame-Options"] == "DENY"
    status, headers, body = _request(server, "/api/conversations/file?" + _query(files["csv"]))
    assert status == 200 and "王小明" in body.decode("utf-8")
    assert _request(server, "/api/conversations/file?" + _query(files["md"]), token=False)[0] == (
        401
    )


def test_the_page_frames_html_with_scripts_only_and_never_same_origin() -> None:
    assert 'frame.setAttribute("sandbox", "allow-scripts")' in PAGE
    # Named only in comments that say it is left out.
    mentions = [line for line in PAGE.splitlines() if "allow-same-origin" in line]
    assert mentions and all(line.strip().startswith("//") for line in mentions), mentions
    assert 'frame.setAttribute("referrerpolicy", "no-referrer")' in PAGE
    assert '"/api/conversations/view-link?"' in PAGE
    # The viewer never builds its own path: only the listed file's path.
    assert PAGE.count('fetch("/api/conversations/file?"') == 1


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_files_open_in_the_viewer_and_the_chart_renders_in_the_answer(
    served: Any,  # noqa: F811
    tmp_path: Path,
) -> None:
    from integrations.browser import Browser

    web, server, _recorder, _ = served
    files = _seed(web, tmp_path)
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 30) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = run(expression)
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(expression)

    def size(selector: str) -> list[int]:
        found: list[int] = json.loads(
            str(
                run(
                    "JSON.stringify((() => { const r = document.querySelector("
                    + json.dumps(selector)
                    + ").getBoundingClientRect(); return [Math.round(r.width),"
                    " Math.round(r.height)]; })())"
                )
            )
        )
        return found

    def no_side_scroll() -> None:
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )

    def chip(path: Path) -> str:
        return f".said ~ .file-chips .file-chip[data-path={_css(path)}]"

    def in_frame(expression: str) -> Any:
        """Evaluate inside the sandboxed chart frame (the parent page cannot:
        the frame's origin is opaque). The browser may run the frame in its
        own process, a target of its own; otherwise it is in the tab's tree."""
        from integrations.websocket import Devtools

        for target in browser._targets():
            if target.get("type") == "iframe" and "/view/file" in str(target.get("url")):
                with Devtools(str(target["webSocketDebuggerUrl"]), timeout_s=30) as frame:
                    answer = frame.call(
                        "Runtime.evaluate", expression=expression, returnByValue=True
                    )
                return answer.get("result", {}).get("value")
        tree = browser.page().call("Page.getFrameTree")
        children = tree["frameTree"].get("childFrames", [])
        if not children:
            return None
        world = browser.page().call("Page.createIsolatedWorld", frameId=children[0]["frame"]["id"])
        answer = browser.page().call(
            "Runtime.evaluate",
            expression=expression,
            contextId=world["executionContextId"],
            returnByValue=True,
        )
        return answer.get("result", {}).get("value")

    try:
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        # Let the page's own first load finish, then open the conversation.
        time.sleep(1.5)
        run(f"loadConversations({json.dumps(SESSION)})")
        wait(f"activeConversation === {json.dumps(SESSION)}")
        wait("!!document.querySelector('.answer-html iframe')")
        time.sleep(1.0)
        wait("!!document.querySelector('.answer-html iframe')")
        frame = ".answer-html iframe"
        # Sandboxed: scripts only, no same origin, no token in its address.
        assert run(f"document.querySelector('{frame}').getAttribute('sandbox')") == (
            "allow-scripts"
        )
        assert run(f"document.querySelector('{frame}').contentDocument") is None
        source = str(run(f"document.querySelector('{frame}').getAttribute('src')"))
        assert source.startswith("/view/file?nonce=") and server.token not in source
        # The chart rendered inside the answer, at a reasonable height.
        deadline = time.monotonic() + 20
        while not in_frame("document.querySelectorAll('.person').length > 0"):
            assert time.monotonic() < deadline, "the chart did not render in its frame"
            time.sleep(0.3)
        assert in_frame("document.getElementById('title').textContent") == "範例科技 組織圖"
        assert in_frame("document.referrer") == ""
        assert in_frame("location.href").find(server.token) == -1
        assert (
            in_frame(
                "(() => { try { return String(parent.TOKEN); } catch (e) { return 'blocked'; } })()"
            )
            == "blocked"
        )
        height = size(".answer-html .frame-wrap")[1]
        assert 300 <= height <= 700, height
        for selector in (".answer-html .viewer-button", chip(files["html"])):
            assert size(selector)[1] >= 44, selector
        run("document.querySelector('.answer-html').scrollIntoView({block: 'start'})")
        browser.screenshot(shots / "chart-in-answer-light.png")
        # The person's attached CSV is a chip too.
        attached = f".asked-files .file-chip[data-path={_css(files['csv'])}]"
        assert run(f"!!document.querySelector({json.dumps(attached)})")
        # HTML chip: Preview in the sandboxed frame, then Code shows the source.
        run(f"document.querySelector({json.dumps(chip(files['html']))}).click()")
        wait("!document.getElementById('file-viewer').hidden")
        wait("!!document.querySelector('#viewer-body iframe')")
        assert run("document.querySelector('#viewer-body iframe').getAttribute('sandbox')") == (
            "allow-scripts"
        )
        assert run("document.getElementById('viewer-name').textContent") == files["html"].name
        assert run("document.activeElement.id") == "viewer-close"
        for selector in ("#viewer-close", "#viewer-preview-mode", "#viewer-code-mode"):
            assert min(size(selector)) >= 44, selector
        browser.screenshot(shots / "viewer-html-preview.png")
        run("document.getElementById('viewer-code-mode').click()")
        wait("!!document.querySelector('#viewer-body pre.code')")
        code = str(run("document.querySelector('#viewer-body pre.code').textContent"))
        assert code.startswith("<!DOCTYPE html>") and "chart-data" in code
        assert run("document.querySelector('#viewer-body iframe')") is None
        assert not run("document.getElementById('viewer-copy').hidden")
        browser.screenshot(shots / "viewer-html-code.png")
        # Esc closes it and focus returns to the chip.
        run(
            "document.getElementById('viewer-code-mode').dispatchEvent("
            "new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))"
        )
        assert run("document.getElementById('file-viewer').hidden") is True
        # Markdown: rendered (the <script> line is text), Code shows it raw.
        run(f"document.querySelector({json.dumps(chip(files['md']))}).click()")
        wait("!!document.querySelector('#viewer-body h1')")
        assert run("document.querySelector('#viewer-body h1').textContent") == "圖例標題"
        assert run("document.querySelectorAll('#viewer-body script').length") == 0
        assert run("document.querySelectorAll('#viewer-body table').length") == 1
        body = str(run("document.getElementById('viewer-body').innerText"))
        assert "<script>alert(1)</script>" in body
        browser.screenshot(shots / "viewer-md-preview.png")
        # Keyboard: the toggle is a button reached and pressed by keys.
        run("document.getElementById('viewer-code-mode').focus()")
        run("document.getElementById('viewer-code-mode').click()")
        wait("!!document.querySelector('#viewer-body pre.code')")
        raw = str(run("document.querySelector('#viewer-body pre.code').textContent"))
        assert raw == MARKDOWN.rstrip("\n") + "\n" or raw == MARKDOWN, raw
        assert run("document.querySelectorAll('#viewer-body h1').length") == 0
        run("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
        assert run("document.getElementById('file-viewer').hidden") is True
        # JSON: the Code view only, with line numbers.
        run(f"document.querySelector({json.dumps(chip(files['json']))}).click()")
        wait("!!document.querySelector('#viewer-body pre.code')")
        assert run("document.getElementById('viewer-modes').hidden") is True
        gutter = str(run("document.querySelector('#viewer-body pre.gutter').textContent"))
        assert gutter.splitlines()[:3] == ["1", "2", "3"]
        assert '"tag": "<x>"' in str(
            run("document.querySelector('#viewer-body pre.code').textContent")
        )
        browser.screenshot(shots / "viewer-json-code.png")
        run("document.getElementById('viewer-close').click()")
        # Text holding HTML is shown as text.
        run(f"document.querySelector({json.dumps(chip(files['txt']))}).click()")
        wait("!!document.querySelector('#viewer-body pre.code')")
        assert run("document.querySelectorAll('#viewer-body b, #viewer-body img').length") == 0
        shown = str(run("document.querySelector('#viewer-body pre.code').textContent"))
        assert shown in (TEXT, TEXT.rstrip("\n") + "\n"), shown
        assert "<b>bold</b> & <img src=x onerror=alert(1)>" in shown
        run("document.getElementById('viewer-close').click()")
        # Dark mode: the panel and the answer frame follow it.
        light = run("getComputedStyle(document.getElementById('file-viewer')).backgroundColor")
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        run(f"document.querySelector({json.dumps(chip(files['md']))}).click()")
        wait("!!document.querySelector('#viewer-body h1')")
        dark = run("getComputedStyle(document.getElementById('file-viewer')).backgroundColor")
        assert light != dark, (light, dark)
        browser.screenshot(shots / "viewer-md-dark.png")
        run("document.getElementById('viewer-close').click()")
        run("document.querySelector('.answer-html').scrollIntoView({block: 'start'})")
        browser.screenshot(shots / "chart-in-answer-dark.png")
        # 390 px: a full-screen sheet, no horizontal page scroll.
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        time.sleep(0.5)
        no_side_scroll()
        run("document.querySelector('.answer-html').scrollIntoView({block: 'start'})")
        browser.screenshot(shots / "chart-in-answer-narrow.png")
        run(f"document.querySelector({json.dumps(chip(files['html']))}).click()")
        wait("!!document.querySelector('#viewer-body iframe')")
        assert size("#file-viewer")[0] == 390
        no_side_scroll()
        browser.screenshot(shots / "viewer-html-narrow.png")
        run("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
        assert run("document.getElementById('file-viewer').hidden") is True
    finally:
        browser.close()
        browser.discard_profile()
