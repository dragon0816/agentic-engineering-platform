"""Driving the browser this machine already has.

The owner's procedures are PDFs that tell a person to open a site, sign in,
click through and fetch something. Walking that needs a real browser, and
this uses the one that is already installed rather than bringing another:
every Windows machine has Edge, `--no-index` installs nothing, and the
offline bundle does not grow.

The whole protocol is DevTools over a WebSocket on the loopback address
(`integrations.websocket`). Nothing here is a browser automation framework
and nothing here should become one: it navigates, reads what is on the page,
lists what can be clicked, clicks and types, and takes a picture when the
list is not enough.

Two rules shape all of it, both from the owner's decisions of 2026-09-24:

1. **The element list comes first and a picture is the fallback.** A list is
   cheap, stable, and readable by a model that cannot see. A screenshot is
   for when the list does not explain the screen.
2. **Signing in is a person's job.** The browser runs in a profile of its
   own that somebody logged into once, by hand. No password is asked for,
   stored, typed or seen here, and a profile is the only thing that carries
   a session.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self

from common.base import Contract, Text
from integrations.websocket import Devtools, DevtoolsRefused, WebSocketError

BrowserErrorCode = Literal[
    "browser_missing",
    "browser_would_not_start",
    "no_page",
    "profile_in_use",
    "navigation_failed",
    "page_changed",
    "element_missing",
    "browser_lost",
]

#: Where Windows records the browsers it knows about, in preference order.
APP_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
)
#: Chromium writes the port it chose into the profile it was given.
PORT_FILE = "DevToolsActivePort"
#: A browser releases its profile directory a moment after it exits, so a
#: cleanup straight afterwards fails on Windows. The same shape as the
#: workbook's unstaging retry, and for the same reason.
PROFILE_RELEASE_SECONDS = 10.0
#: What is listed as clickable. Deliberately short: a model choosing from
#: four hundred elements chooses badly.
INTERACTIVE = "a, button, input, select, textarea, [role=button], [role=link]"


class BrowserError(Exception):
    """The code is the message. What is on somebody's screen is their own
    work, and a failure here never repeats it."""

    def __init__(self, code: BrowserErrorCode, detail: str = "") -> None:
        self.code: BrowserErrorCode = code
        # Detail is about the command, never about the page's content.
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


class Element(Contract):
    """One thing on the page a person could use.

    `index` is how it is referred to afterwards, and `signature` is what it
    looked like when it was listed: acting on it checks the signature still
    matches, so a page that changed underneath is refused rather than
    clicked blindly.
    """

    index: int
    tag: Text
    kind: str = ""
    element_id: str = ""
    name: str = ""
    # What the element is called on the page: its own text, or the label a
    # field carries when it is empty. Never what a field currently holds.
    label: str = ""
    # What a field holds right now. Kept apart from `label` on purpose: it
    # changes the moment anybody types, and an identity that changed when
    # something was typed into it would refuse the second half of every
    # sign-in. That is the defect this separation fixes.
    value: str = ""
    href: str = ""
    visible: bool = True

    @property
    def signature(self) -> str:
        """What this element *is*, which is what acting on it later checks.
        Deliberately not what it contains."""
        return f"{self.tag}|{self.kind}|{self.element_id}|{self.name}|{self.label[:40]}"

    def described(self) -> str:
        parts = [f"[{self.index}] {self.tag.lower()}"]
        if self.kind:
            parts.append(f"type={self.kind}")
        if self.element_id:
            parts.append(f"id={self.element_id}")
        if self.label:
            parts.append(repr(self.label[:60]))
        if self.value:
            parts.append(f"holding {self.value[:40]!r}")
        if self.href:
            parts.append(f"-> {self.href[:80]}")
        if not self.visible:
            parts.append("(not visible)")
        return " ".join(parts)


class PageView(Contract):
    """What one look at the page found."""

    url: str = ""
    title: str = ""
    text: str = ""
    elements: tuple[Element, ...] = ()
    screenshot: str = ""

    def described(self, *, limit: int = 4000) -> str:
        """The page as a model or a person reads it: what it says, then what
        can be done to it."""
        lines = [f"{self.title}  <{self.url}>", "", self.text[:limit]]
        if len(self.text) > limit:
            lines.append(f"... ({len(self.text) - limit} more characters)")
        lines.extend(["", f"{len(self.elements)} thing(s) that can be used:"])
        lines.extend("  " + element.described() for element in self.elements)
        if self.screenshot:
            lines.extend(["", f"a picture of it: {self.screenshot}"])
        return "\n".join(lines)


#: Collect what is on the page in one evaluation, because a round trip per
#: element would be a hundred round trips.
_LIST_ELEMENTS = """
(() => {
  const out = [];
  document.querySelectorAll(%s).forEach((e, i) => {
    const box = e.getBoundingClientRect();
    out.push({
      index: i,
      tag: e.tagName,
      kind: e.getAttribute('type') || '',
      element_id: e.id || '',
      name: e.getAttribute('name') || '',
      label: (e.innerText || e.getAttribute('aria-label') ||
              e.getAttribute('placeholder') || e.getAttribute('title') || '')
             .replace(/\\s+/g, ' ').trim().slice(0, 200),
      value: (e.value == null ? '' : String(e.value))
             .replace(/\\s+/g, ' ').trim().slice(0, 200),
      href: e.getAttribute('href') || '',
      visible: box.width > 0 && box.height > 0
    });
  });
  return JSON.stringify(out);
})()
"""


def browser_path() -> str | None:
    """Where Windows says a Chromium browser is, or nothing.

    The registry, and not a search of the disk: it is the same read the Excel
    and Outlook adapters use, it starts nothing, and it answers the question
    a doctor is allowed to ask.
    """
    if sys.platform != "win32":
        return None
    import winreg

    for key_path in APP_PATHS:
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, key_path) as key:
                    value, _kind = winreg.QueryValueEx(key, "")
            except OSError:
                continue
            if value and Path(str(value)).is_file():
                return str(value)
    return None


class Browser:
    """One browser, in one profile, for the length of one run.

    Headless unless somebody is meant to see it, which is the sign-in case.
    The profile is never a temporary one by default: a session that vanished
    with the process would mean signing in again every time, which is exactly
    what the owner's decision avoids.
    """

    def __init__(
        self,
        profile: Path,
        *,
        executable: str | None = None,
        headless: bool = True,
        timeout_s: float = 30.0,
        extra_arguments: tuple[str, ...] = (),
    ) -> None:
        self.profile = Path(profile)
        self.executable = executable if executable is not None else browser_path()
        self.headless = headless
        self.timeout_s = timeout_s
        self.extra_arguments = extra_arguments
        self._process: subprocess.Popen[bytes] | None = None
        self._page: Devtools | None = None
        self._port: int | None = None

    # -- starting and stopping ----------------------------------------

    def _arguments(self) -> list[str]:
        assert self.executable is not None
        arguments = [
            self.executable,
            # Zero, and then read back what it took. Choosing a free port here
            # and passing it looks equivalent and is not: between finding it
            # free and the browser binding it, Windows can still hold it, and
            # the browser then exits at once with nothing to say. Letting it
            # choose is both simpler and the only version that works.
            "--remote-debugging-port=0",
            f"--user-data-dir={self.profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-features=Translate,MediaRouter",
        ]
        if self.headless:
            # The newer headless is a real browser rather than a separate
            # mode, which is what makes a page behave as it would for a
            # person: the old one differed in ways that mattered.
            arguments.extend(["--headless=new", "--disable-gpu"])
        arguments.extend(self.extra_arguments)
        arguments.append("about:blank")
        return arguments

    def start(self) -> None:
        if self.executable is None:
            raise BrowserError("browser_missing")
        if (self.profile / "SingletonLock").exists() and self._running_elsewhere():
            # A profile a person has open cannot also be driven: Chromium
            # holds it, and the second process quietly joins the first.
            raise BrowserError("profile_in_use")
        self.profile.mkdir(parents=True, exist_ok=True)
        # A stale port file from a previous run would be read as this run's.
        (self.profile / PORT_FILE).unlink(missing_ok=True)
        try:
            self._process = subprocess.Popen(
                self._arguments(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as failure:
            raise BrowserError("browser_would_not_start", type(failure).__name__) from None
        self._port = self._published_port()

    def _running_elsewhere(self) -> bool:
        """Whether something is already answering on this profile's port."""
        marker = self.profile / PORT_FILE
        if not marker.is_file():
            return True
        try:
            port = int(marker.read_text(encoding="utf-8").splitlines()[0])
            self._targets(port)
        except (OSError, ValueError, IndexError, BrowserError):
            return False
        return True

    def _published_port(self) -> int:
        """What the browser chose, which it writes into the profile.

        The process this started exiting is **not** a failure, which took
        finding out: `msedge.exe` is a launcher that hands off and exits with
        success within a tenth of a second, while the browser it started runs
        on in a process tree this one does not own. Treating that exit as the
        answer made every start fail and every browser leak, because the
        thing being terminated afterwards had already been dead.

        So the file is what is waited for, and the exit is only a reason to
        stop waiting once the file has not appeared either.
        """
        marker = self.profile / PORT_FILE
        end = time.time() + self.timeout_s
        handed_off_at: float | None = None
        while time.time() < end:
            if marker.is_file():
                first = marker.read_text(encoding="utf-8").splitlines()
                if first and first[0].strip().isdigit():
                    return int(first[0].strip())
            if self._process is not None and self._process.poll() is not None:
                # It may have handed off. Give the browser it started a
                # moment to publish, then conclude it did not start one.
                handed_off_at = handed_off_at or time.time()
                if time.time() - handed_off_at > 5.0:
                    raise BrowserError("browser_would_not_start", "it published no port")
            time.sleep(0.1)
        raise BrowserError("browser_would_not_start", "it never published a port")

    def _targets(self, port: int | None = None) -> list[dict[str, Any]]:
        where = port if port is not None else self._port
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{where}/json/list", timeout=self.timeout_s
            ) as answer:
                found = json.loads(answer.read())
        except (OSError, urllib.error.URLError, ValueError):
            raise BrowserError("browser_lost") from None
        return [item for item in found if isinstance(item, dict)]

    def page(self) -> Devtools:
        """The tab. Extensions publish targets of their own -- this machine's
        Edge lists five background pages -- so the type is checked rather
        than the first one taken."""
        if self._page is not None:
            return self._page
        end = time.time() + self.timeout_s
        while time.time() < end:
            for target in self._targets():
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    try:
                        page = Devtools(
                            str(target["webSocketDebuggerUrl"]), timeout_s=self.timeout_s
                        )
                    except WebSocketError:
                        continue
                    page.call("Page.enable")
                    page.call("Runtime.enable")
                    self._page = page
                    return page
            time.sleep(0.2)
        raise BrowserError("no_page")

    def _ask_it_to_close(self, port: int | None) -> bool:
        """`Browser.close`, which is the browser shutting itself down.

        Worth trying before anything harsher: a session is written to the
        profile on the way out, and a browser killed mid-flush is a profile
        that has forgotten the sign-in somebody did by hand. That is the one
        thing this must not lose.
        """
        if port is None:
            return False
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=5
            ) as answer:
                described = json.loads(answer.read())
            endpoint = described.get("webSocketDebuggerUrl")
            if not endpoint:
                return False
            with Devtools(str(endpoint), timeout_s=10) as browser:
                browser.call("Browser.close")
            return True
        except (OSError, ValueError, WebSocketError, DevtoolsRefused):
            return False

    def _still_answering(self, port: int | None) -> bool:
        if port is None:
            return False
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=2
            ) as answer:
                answer.read()
            return True
        except (OSError, ValueError):
            return False

    def close(self) -> None:
        """Stop the browser this started.

        **`Browser.close` over DevTools is the only thing that reliably does
        it**, which was the defect found on 2026-09-24: the process this
        launched is a launcher that has already exited, so terminating it
        reaches nothing and the browser runs on. A test run left three
        hundred processes alive that way.

        Asking it to close is also the right thing for the profile: a session
        is written on the way out, and a browser killed mid-flush is a
        profile that has forgotten the sign-in somebody did by hand.
        """
        if self._page is not None:
            self._page.close()
            self._page = None
        process, self._process = self._process, None
        port, self._port = self._port, None
        self._ask_it_to_close(port)
        end = time.time() + 10.0
        while time.time() < end and self._still_answering(port):
            time.sleep(0.2)
        if process is not None:
            # Harmless where the launcher is already gone, and the whole
            # answer where it is not: Chrome keeps its parent alive.
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - a wedged browser
                process.kill()
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )

    def discard_profile(self) -> None:
        """Remove a throwaway profile, waiting for the browser to let go.

        Only for a profile this run created. A signed-in one is the thing
        worth keeping, and nothing here removes it.
        """
        end = time.time() + PROFILE_RELEASE_SECONDS
        while time.time() < end:
            try:
                shutil.rmtree(self.profile)
                return
            except FileNotFoundError:
                return
            except OSError:
                time.sleep(0.25)

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # -- looking -------------------------------------------------------

    def _evaluate(self, expression: str) -> Any:
        page = self.page()
        try:
            answer = page.call("Runtime.evaluate", expression=expression, returnByValue=True)
        except (DevtoolsRefused, WebSocketError) as failure:
            raise BrowserError("browser_lost", type(failure).__name__) from None
        result = answer.get("result", {})
        if answer.get("exceptionDetails"):
            raise BrowserError("navigation_failed", "the page could not be read")
        return result.get("value")

    def navigate(self, url: str, *, settle_s: float = 1.0) -> None:
        page = self.page()
        try:
            answer = page.call("Page.navigate", url=url)
        except (DevtoolsRefused, WebSocketError) as failure:
            raise BrowserError("navigation_failed", type(failure).__name__) from None
        if answer.get("errorText"):
            # The browser's own word for why, which is about the address and
            # not about anything on a page.
            raise BrowserError("navigation_failed", str(answer["errorText"]))
        self._await_load(page)
        # What a page does to itself after loading, which no event announces.
        time.sleep(settle_s)

    def _await_load(self, page: Devtools) -> None:
        """Wait for *this* navigation's load, not a previous one's.

        The events a command collected are cleared before navigating, which
        is not tidiness: kept, the last page's `Page.loadEventFired` answers
        for the next one, so the first navigation waits out the whole timeout
        and every one after it does not wait at all. Both were wrong in the
        same line.
        """
        page.events.clear()
        end = time.time() + self.timeout_s
        while time.time() < end:
            if page.drain("Page.loadEventFired"):
                return
            try:
                # Asking anything drains what the browser sent unasked, which
                # is how the event is noticed at all.
                page.call("Runtime.evaluate", expression="1", returnByValue=True)
            except (DevtoolsRefused, WebSocketError):
                return
            if page.drain("Page.loadEventFired"):
                return
            time.sleep(0.05)

    def elements(self, selector: str = INTERACTIVE) -> tuple[Element, ...]:
        raw = self._evaluate(_LIST_ELEMENTS % json.dumps(selector))
        if not isinstance(raw, str):
            return ()
        try:
            listed = json.loads(raw)
        except ValueError:
            return ()
        return tuple(Element.model_validate(item) for item in listed)

    def look(self, *, picture: Path | None = None) -> PageView:
        """The element list first, and a picture only when one is asked for.

        The owner's decision of 2026-09-24: a list is cheap, stable and
        readable by a model that cannot see; a screenshot is the fallback for
        a screen the list does not explain.
        """
        return PageView(
            url=str(self._evaluate("document.location.href") or ""),
            title=str(self._evaluate("document.title") or ""),
            text=str(self._evaluate("document.body ? document.body.innerText : ''") or ""),
            elements=self.elements(),
            screenshot=str(self.screenshot(picture)) if picture is not None else "",
        )

    def screenshot(self, where: Path) -> Path:
        page = self.page()
        try:
            answer = page.call("Page.captureScreenshot", format="png")
        except (DevtoolsRefused, WebSocketError) as failure:
            raise BrowserError("browser_lost", type(failure).__name__) from None
        import base64

        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_bytes(base64.b64decode(str(answer.get("data", ""))))
        return where

    # -- acting --------------------------------------------------------

    def _at(self, index: int, expected: Element | None) -> Element:
        """The element at that position now, refused if it is not the one
        that was listed. A page that changed underneath must not be clicked
        on the strength of what it used to say."""
        found = self.elements()
        if index < 0 or index >= len(found):
            raise BrowserError("element_missing", f"there is no element {index} on this page")
        now = found[index]
        if expected is not None and now.signature != expected.signature:
            raise BrowserError(
                "page_changed",
                f"element {index} is no longer what it was when the page was read",
            )
        return now

    def click(self, index: int, *, expected: Element | None = None) -> None:
        self._at(index, expected)
        self._evaluate(
            f"(() => {{ const e = document.querySelectorAll({json.dumps(INTERACTIVE)})[{index}];"
            " e.click(); return true; })()"
        )

    def fill(self, index: int, value: str, *, expected: Element | None = None) -> None:
        """Type into a field. The value is whatever the caller passed and is
        never logged: a field is where a person's own words go."""
        self._at(index, expected)
        self._evaluate(
            f"(() => {{ const e = document.querySelectorAll({json.dumps(INTERACTIVE)})[{index}];"
            f" e.focus(); e.value = {json.dumps(value)};"
            " e.dispatchEvent(new Event('input', {bubbles: true}));"
            " e.dispatchEvent(new Event('change', {bubbles: true})); return true; })()"
        )
