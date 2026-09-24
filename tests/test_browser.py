"""Driving the browser this machine already has.

Where there is one, these start it for real, on a page this machine serves to
itself, and drive it through the thing the owner described: open, read, sign
in wrongly, sign in again, find the target. CI has no browser and skips them,
which is said plainly rather than passing quietly -- the Excel adapter has
the same caveat and for the same reason.

The parts that need no browser are tested everywhere: what is refused, how a
page is described, and that acting on a page that changed is refused.
"""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Iterator
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from integrations.browser import Browser, BrowserError, Element, PageView, browser_path

#: The shape the owner described: a site that wants a sign-in, gets it wrong
#: the first time, and has the wanted thing on it only once signed in.
SITE = """<!doctype html><html><head><title>Orders</title></head><body>
<h1>Sign in</h1>
<form>
  <input id="user" name="user" placeholder="user name">
  <input id="pass" name="pass" type="password" placeholder="password">
  <button id="go" type="button" onclick="
    document.getElementById('out').textContent =
      document.getElementById('user').value === 'engineer'
        ? 'WELCOME. order-4471 total 12345'
        : 'Those details were not recognised.'">Sign in</button>
</form>
<div id="out">not signed in</div>
<a id="help" href="/help.html">Help</a>
</body></html>"""

HAVE_BROWSER = browser_path() is not None
needs_browser = pytest.mark.skipif(
    not HAVE_BROWSER, reason="no Chromium browser is installed on this machine"
)


class Site:
    """A page this machine serves to itself, so no test reaches a network."""

    def __init__(self, root: Path) -> None:
        (root / "index.html").write_text(SITE, encoding="utf-8")
        (root / "help.html").write_text("<h1>Help</h1>", encoding="utf-8")
        directory = str(root)

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args: object, **kwargs: object) -> None:
                super().__init__(*args, directory=directory, **kwargs)  # type: ignore[arg-type]

            def log_message(self, *args: object) -> None:
                return None

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}/index.html"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def site(tmp_path: Path) -> Iterator[Site]:
    served = Site(tmp_path)
    try:
        yield served
    finally:
        served.close()


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    started = Browser(tmp_path / "profile", timeout_s=60)
    try:
        started.start()
        yield started
    finally:
        started.close()
        started.discard_profile()


# -- without a browser ----------------------------------------------------


def test_a_machine_with_no_browser_says_so_rather_than_failing_oddly(
    tmp_path: Path,
) -> None:
    absent = Browser(tmp_path / "p", executable=None)
    absent.executable = None
    with pytest.raises(BrowserError) as refused:
        absent.start()
    assert refused.value.code == "browser_missing"


def test_a_port_file_locked_while_chromium_replaces_it_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = tmp_path / "profile"
    profile.mkdir()
    marker = profile / "DevToolsActivePort"
    marker.write_text("43127\n/devtools/browser/session\n", encoding="utf-8")
    original = Path.read_text
    attempts = 0

    def briefly_locked(path: Path, *args: object, **kwargs: object) -> str:
        nonlocal attempts
        if path == marker and attempts == 0:
            attempts += 1
            raise PermissionError("Chromium is replacing the marker")
        return original(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", briefly_locked)
    waiting = Browser(profile, executable="unused", timeout_s=1)

    assert waiting._published_port() == 43127
    assert attempts == 1


def test_an_element_reads_as_something_a_model_can_choose_from() -> None:
    element = Element(
        index=3, tag="BUTTON", kind="button", element_id="go", label="Sign in", visible=True
    )
    shown = element.described()
    assert shown.startswith("[3] button")
    assert "id=go" in shown and "'Sign in'" in shown


def test_an_invisible_element_says_so() -> None:
    """A model told to click something it cannot see is being set up to fail
    silently."""
    hidden = Element(index=0, tag="A", label="Skip", visible=False)
    assert "(not visible)" in hidden.described()


def test_a_page_reads_as_what_it_says_then_what_can_be_done_to_it() -> None:
    view = PageView(
        url="http://127.0.0.1/x",
        title="Orders",
        text="Sign in\nnot signed in",
        elements=(Element(index=0, tag="BUTTON", element_id="go", label="Sign in"),),
    )
    shown = view.described()
    assert "Orders  <http://127.0.0.1/x>" in shown
    assert "not signed in" in shown
    assert "1 thing(s) that can be used:" in shown
    assert "[0] button id=go" in shown


def test_a_long_page_is_cut_and_says_it_was() -> None:
    view = PageView(text="x" * 9000)
    shown = view.described(limit=100)
    assert "... (8900 more characters)" in shown


def test_the_element_signature_is_what_acting_checks() -> None:
    """A page that changed underneath must not be clicked on the strength of
    what it used to say."""
    listed = Element(index=2, tag="BUTTON", element_id="go", label="Sign in")
    same = Element(index=2, tag="BUTTON", element_id="go", label="Sign in")
    moved = Element(index=2, tag="BUTTON", element_id="cancel", label="Cancel")
    assert listed.signature == same.signature
    assert listed.signature != moved.signature


def test_typing_into_a_field_does_not_change_what_it_is() -> None:
    """The defect this separation fixes: with the current contents in the
    identity, the second half of every sign-in was refused, because the field
    was no longer "the same" as the one that had just been typed into."""
    empty = Element(index=0, tag="INPUT", kind="text", element_id="user", label="user name")
    typed = empty.model_copy(update={"value": "engineer"})
    assert empty.signature == typed.signature
    assert "holding 'engineer'" in typed.described()


def test_a_field_that_became_a_different_field_is_a_different_element() -> None:
    empty = Element(index=0, tag="INPUT", kind="text", element_id="user")
    secret = Element(index=0, tag="INPUT", kind="password", element_id="user")
    assert empty.signature != secret.signature


# -- with the browser this machine has ------------------------------------


@needs_browser
def test_it_starts_the_installed_browser_and_finds_the_page(browser: Browser) -> None:
    """Extensions publish targets of their own, so the type is checked rather
    than the first target taken."""
    page = browser.page()
    assert page is not None
    assert browser.page() is page, "the same tab, not a new one each time"


@needs_browser
def test_the_whole_flow_the_owner_described(browser: Browser, site: Site) -> None:
    """Open it, read it, get the sign-in wrong, try again, find the target.

    This is the procedure a PDF describes, walked without anybody clicking.
    """
    browser.navigate(site.url)
    view = browser.look()
    assert view.title == "Orders"
    assert "not signed in" in view.text

    fields = {element.element_id: element for element in view.elements}
    assert {"user", "pass", "go", "help"} <= set(fields)

    # Wrong the first time, which is what happens.
    browser.fill(fields["user"].index, "somebody-else", expected=fields["user"])
    browser.click(fields["go"].index, expected=fields["go"])
    assert "not recognised" in browser.look().text

    # And right the second.
    browser.fill(fields["user"].index, "engineer", expected=fields["user"])
    browser.click(fields["go"].index, expected=fields["go"])
    after = browser.look()
    assert "order-4471" in after.text, "the target was never reached"


@needs_browser
def test_the_element_list_is_what_can_be_used_and_nothing_else(
    browser: Browser, site: Site
) -> None:
    """A model choosing from four hundred elements chooses badly, so headings
    and paragraphs are not offered."""
    browser.navigate(site.url)
    listed = browser.look().elements
    assert [element.tag for element in listed] == ["INPUT", "INPUT", "BUTTON", "A"]
    assert all(element.index == position for position, element in enumerate(listed))
    link = listed[-1]
    assert link.href == "/help.html", "a link says where it goes"
    password = listed[1]
    assert password.kind == "password"


@needs_browser
def test_acting_on_a_page_that_changed_is_refused(browser: Browser, site: Site) -> None:
    """The check that makes a recorded step safe to replay: the thing at
    that position has to still be the thing that was described."""
    browser.navigate(site.url)
    listed = browser.look().elements
    button = listed[2]
    stale = button.model_copy(update={"element_id": "something-else"})
    with pytest.raises(BrowserError) as refused:
        browser.click(button.index, expected=stale)
    assert refused.value.code == "page_changed"


@needs_browser
def test_an_element_that_is_not_there_is_refused(browser: Browser, site: Site) -> None:
    browser.navigate(site.url)
    with pytest.raises(BrowserError) as refused:
        browser.click(99)
    assert refused.value.code == "element_missing"


@needs_browser
def test_a_picture_is_taken_only_when_one_is_asked_for(
    browser: Browser, site: Site, tmp_path: Path
) -> None:
    """The owner's decision: the list first, a picture as the fallback."""
    browser.navigate(site.url)
    assert browser.look().screenshot == "", "no picture unless asked"
    where = tmp_path / "shots" / "page.png"
    view = browser.look(picture=where)
    assert view.screenshot == str(where)
    assert where.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@needs_browser
def test_an_address_that_goes_nowhere_is_a_named_refusal(browser: Browser) -> None:
    with pytest.raises(BrowserError) as refused:
        browser.navigate("http://127.0.0.1:9/nothing-listens-here", settle_s=0)
    assert refused.value.code == "navigation_failed"


@needs_browser
def test_a_signed_in_profile_is_what_carries_the_session(tmp_path: Path, site: Site) -> None:
    """The owner's decision of 2026-09-24: a person signs in once, by hand,
    and the profile carries it. No password is asked for, stored or typed by
    anything here -- what persists is the browser's own session.
    """
    profile = tmp_path / "kept"
    first = Browser(profile, timeout_s=60)
    first.start()
    try:
        first.navigate(site.url)
        # Standing in for a sign-in: something the site remembers.
        first._evaluate("localStorage.setItem('signed-in-as', 'engineer')")
    finally:
        first.close()
    time.sleep(1.0)

    second = Browser(profile, timeout_s=60)
    second.start()
    try:
        second.navigate(site.url)
        assert second._evaluate("localStorage.getItem('signed-in-as')") == "engineer"
    finally:
        second.close()
        second.discard_profile()


@needs_browser
def test_a_throwaway_profile_is_removed_although_the_browser_holds_it(
    tmp_path: Path,
) -> None:
    """Windows keeps the profile locked for a moment after the browser exits,
    which a cleanup straight afterwards trips over."""
    profile = tmp_path / "temporary"
    browser = Browser(profile, timeout_s=60)
    browser.start()
    browser.page()
    browser.close()
    browser.discard_profile()
    assert not profile.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="the registry is Windows' own")
def test_where_the_browser_is_comes_from_the_registry() -> None:
    """The same read the Excel and Outlook adapters use, which starts
    nothing and is what a doctor is allowed to ask."""
    found = browser_path()
    if found is None:
        pytest.skip("no Chromium browser is installed on this machine")
    assert Path(found).is_file()
    assert Path(found).name.lower() in ("msedge.exe", "chrome.exe")


def test_nothing_here_downloads_a_browser() -> None:
    """The whole reason this exists rather than a browser automation
    framework: the offline bundle installs with --no-index and must not grow
    by a browser."""
    source = Path("src/integrations/browser.py").read_text(encoding="utf-8")
    for forbidden in ("pip install", "urlretrieve", "download", ".zip"):
        assert forbidden not in source
    assert "playwright" not in source.lower()
    assert "selenium" not in source.lower()


def test_the_adapter_imports_only_the_standard_library_and_this_package() -> None:
    """The whole point of driving the installed browser is that the offline
    bundle does not grow. A dependency added here would undo that, so what
    this module reaches for is read rather than assumed."""
    import ast

    source = Path("src/integrations/browser.py").read_text(encoding="utf-8")
    reached: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            reached.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            reached.add(node.module.split(".")[0])
    ours = {"common", "integrations"}
    stdlib = set(sys.stdlib_module_names)
    outside = reached - ours - stdlib
    assert outside == set(), f"this adapter reaches outside the standard library: {outside}"
