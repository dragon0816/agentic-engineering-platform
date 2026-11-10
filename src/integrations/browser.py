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
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.client import HTTPException
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Literal, Self

from common.base import Contract, Text
from integrations.dom_names import DOM_NAME_JS
from integrations.network_barrier import NetworkBarrier
from integrations.websocket import Devtools, DevtoolsRefused, SocketTrace, WebSocketError

BrowserErrorCode = Literal[
    "browser_missing",
    "browser_would_not_start",
    "no_page",
    "profile_in_use",
    "navigation_failed",
    "page_changed",
    "element_missing",
    "click_failed",
    "browser_lost",
    "web_network_observer_unavailable",
    "web_network_observation_lost",
    "web_network_no_fresh_request",
    "web_network_request_failed",
    "web_wait_timeout",
    "web_origin_not_allowed",
]

#: Where Windows records the browsers it knows about, in preference order.
APP_PATHS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
)
#: Chromium writes the port it chose into the profile it was given.
PORT_FILE = "DevToolsActivePort"
#: How long `start` waits for a usable tab before it relaunches once.
STARTUP_PAGE_SECONDS = 20.0
# AEP browser/workflow sessions operate desktop sites, including narrow SSO popups.
DESKTOP_VIEWPORT = (1440, 900)
#: Chromium names the profile lock differently by platform and distribution.
#: Edge on Windows uses `lockfile`; Chrome on POSIX uses `SingletonLock`.
PROFILE_LOCK_FILES = ("lockfile", "SingletonLock")
#: A browser releases its profile directory a moment after it exits, so a
#: cleanup straight afterwards fails on Windows. The same shape as the
#: workbook's unstaging retry, and for the same reason.
PROFILE_RELEASE_SECONDS = 10.0
#: What is listed as clickable. Deliberately short: a model choosing from
#: four hundred elements chooses badly.
INTERACTIVE = "a, button, input, select, textarea, [role=button], [role=link]"
#: Opt-in diagnostics for CI (2026-10-20: tabs vanished on the hosted runner
#: and nothing said why). When this names a folder, the browser's own stderr
#: log goes there and every `no_page`/`navigation_failed` writes what the
#: DevTools endpoint reported -- target types and addresses, never page
#: content. Unset, nothing here changes.
DIAG_DIR_ENV = "AEP_BROWSER_DIAG_DIR"
#: How many attach attempts a failure record repeats.
DIAG_ATTACHES_KEPT = 20
#: Which browser to drive, when the registry's first choice is not the one
#: wanted (a CI runner has both Edge and Chrome). Unset, the registry decides
#: exactly as before. Set, it is used as given, so a wrong path fails loudly
#: as `browser_would_not_start` rather than quietly picking another browser.
EXECUTABLE_ENV = "AEP_BROWSER_EXECUTABLE"


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
  const accessibleName = __DOM_NAME__;
  document.querySelectorAll(%s).forEach((e, i) => {
    const box = e.getBoundingClientRect();
    out.push({
      index: i,
      tag: e.tagName,
      kind: e.getAttribute('type') || '',
      element_id: e.id || '',
      name: e.getAttribute('name') || '',
      label: accessibleName(e),
      value: (e.value == null ? '' : String(e.value))
             .replace(/\\s+/g, ' ').trim().slice(0, 200),
      href: e.getAttribute('href') || '',
      visible: box.width > 0 && box.height > 0
    });
  });
  return JSON.stringify(out);
})()
""".replace("__DOM_NAME__", DOM_NAME_JS)


def _named(failure: Exception) -> str:
    """A failure's code or method, for a diagnostic: never its message."""
    if isinstance(failure, WebSocketError):
        return failure.code
    if isinstance(failure, DevtoolsRefused):
        return f"refused {failure.method}"
    return type(failure).__name__


def browser_path() -> str | None:
    """Where Windows says a Chromium browser is, or nothing.

    The registry, and not a search of the disk: it is the same read the Excel
    and Outlook adapters use, it starts nothing, and it answers the question
    a doctor is allowed to ask. `AEP_BROWSER_EXECUTABLE`, when set, answers
    instead.
    """
    chosen = os.environ.get(EXECUTABLE_ENV, "").strip()
    if chosen:
        return chosen
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


class _NetworkObservation:
    """One attached connection's metadata-only evidence; never query correctness."""

    def __init__(self, browser: Browser, page: Devtools, allowed: tuple[str, ...]) -> None:
        self.browser, self.page, self.allowed = browser, page, allowed
        self.tracker = NetworkBarrier(allowed)
        self.frame_id = self.origin = ""
        self.armed = False
        self.last_deadline: float | None = None

    def _connected(self) -> None:
        if (
            self.browser._page is not self.page
            or self.page.network_observer is not self.tracker
            or self.page.network_events_lost
        ):
            self.tracker.mark_lost()
            raise BrowserError("web_network_observation_lost")
        reason = self.tracker.evidence()["failed_reason"]
        if reason:
            code: BrowserErrorCode = (
                "web_network_request_failed"
                if reason in {"http_error", "request_failed"}
                else "web_network_observation_lost"
            )
            raise BrowserError(code)

    @contextmanager
    def within_deadline(self, deadline: float) -> Iterator[None]:
        self._connected()
        self.last_deadline = deadline
        try:
            with self.page.within_deadline(deadline):
                yield
        except (DevtoolsRefused, WebSocketError):
            self.tracker.mark_lost()
            raise BrowserError("web_network_observation_lost") from None

    def _frame(self, check_origin: Callable[[str], None]) -> tuple[str, str]:
        self._connected()
        value = self.page.call("Page.getFrameTree").get("frameTree", {}).get("frame", {})
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            raise BrowserError("web_network_observer_unavailable")
        url = value.get("url")
        if not isinstance(url, str) or not url:
            raise BrowserError("web_network_observer_unavailable")
        check_origin(url)
        from urllib.parse import urlsplit

        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}".lower()
        return value["id"], origin

    def arm(self, check_origin: Callable[[str], None]) -> None:
        self.frame_id, self.origin = self._frame(check_origin)
        # Chromium emits both this Timestamp and Network timestamps as
        # base::TimeTicks::since_origin().InSecondsF(), not Python/wall time.
        metrics = self.page.call("Performance.getMetrics").get("metrics", [])
        stamps = [
            m.get("value") for m in metrics if isinstance(m, dict) and m.get("name") == "Timestamp"
        ]
        if (
            len(stamps) != 1
            or isinstance(stamps[0], bool)
            or not isinstance(stamps[0], (int, float))
            or not math.isfinite(stamps[0])
            or stamps[0] <= 0
        ):
            raise BrowserError("web_network_observer_unavailable")
        self.tracker.arm(self.frame_id, self.origin, float(stamps[0]), time.monotonic())
        self.armed = True
        self._connected()

    def assert_scope(self, check_origin: Callable[[str], None]) -> str:
        frame_id, origin = self._frame(check_origin)
        if origin != self.origin:
            raise BrowserError("web_origin_not_allowed")
        if frame_id != self.frame_id:
            self.tracker.mark_lost()
            raise BrowserError("web_network_observation_lost")
        return origin

    def wait(self, deadline: float, quiet_s: float, check_origin: Callable[[str], None]) -> None:
        while True:
            if time.monotonic() >= deadline:
                code: BrowserErrorCode = (
                    "web_network_no_fresh_request"
                    if not self.tracker.evidence()["fresh_started"]
                    else "web_wait_timeout"
                )
                raise BrowserError(code)
            frame_id, origin = self._frame(check_origin)
            if origin != self.origin:
                raise BrowserError("web_origin_not_allowed")
            if frame_id != self.frame_id:
                self.tracker.mark_lost()
            evidence = self.tracker.evidence()
            if evidence["failed_reason"]:
                reason = evidence["failed_reason"]
                code = (
                    "web_network_request_failed"
                    if reason in {"http_error", "request_failed"}
                    else "web_network_observation_lost"
                )
                raise BrowserError(code)
            if self.tracker.ready(time.monotonic(), quiet_s):
                # The preceding epoch is quiet. Observe intervening activity
                # before another atomic action in the same script/for_each.
                self.tracker = NetworkBarrier(self.allowed)
                self.page.network_observer = self.tracker
                self.armed = False
                return
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


class Browser:
    """One browser, in one profile, for the length of one run.

    Headless unless somebody is meant to see it, which is the sign-in case.
    The profile is never a temporary one by default: a session that vanished
    with the process would mean signing in again every time, which is exactly
    what the owner's decision avoids.
    """

    #: Class defaults so a `Browser.__new__` stand-in in a test still works.
    _viewport: tuple[int, int] | None = None
    _diag_dir: Path | None = None
    _diag_stderr: IO[bytes] | None = None
    _diag_sockets: Path | None = None
    _diag_attaches: tuple[dict[str, Any], ...] = ()

    def __init__(
        self,
        profile: Path,
        *,
        executable: str | None = None,
        headless: bool = True,
        timeout_s: float = 30.0,
        extra_arguments: tuple[str, ...] = (),
        viewport: tuple[int, int] | None = None,
    ) -> None:
        self.profile = Path(profile)
        self.executable = executable if executable is not None else browser_path()
        self.headless = headless
        self.timeout_s = timeout_s
        self.extra_arguments = extra_arguments
        self.viewport = viewport
        self._process: subprocess.Popen[bytes] | None = None
        self._page: Devtools | None = None
        self._port: int | None = None
        configured = os.environ.get(DIAG_DIR_ENV, "").strip()
        self._diag_dir = Path(configured) if configured else None

    @property
    def viewport(self) -> tuple[int, int] | None:
        """Optional declared CSS-pixel dimensions, applied to each attached page."""
        return self._viewport

    @viewport.setter
    def viewport(self, value: tuple[int, int] | None) -> None:
        if value is not None and (
            not isinstance(value, tuple)
            or len(value) != 2
            or any(type(dimension) is not int for dimension in value)
            or not 320 <= value[0] <= 7680
            or not 240 <= value[1] <= 4320
        ):
            raise ValueError("viewport requires integer width 320..7680 and height 240..4320")
        self._viewport = value

    def _apply_viewport(self, page: Devtools) -> None:
        if self.viewport is not None:
            width, height = self.viewport
            page.call(
                "Emulation.setDeviceMetricsOverride",
                width=width,
                height=height,
                deviceScaleFactor=1,
                mobile=False,
                screenWidth=width,
                screenHeight=height,
            )

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
        if self._diag_dir is not None:
            arguments.extend(["--enable-logging=stderr", "--v=0"])
        arguments.extend(self.extra_arguments)
        arguments.append("about:blank")
        return arguments

    def start(self) -> None:
        if self.executable is None:
            raise BrowserError("browser_missing")
        if self._profile_locked():
            if self._running_elsewhere():
                # A profile a person has open cannot also be driven: Chromium
                # holds it, and the second process quietly joins the first.
                raise BrowserError("profile_in_use")
            # Browser.close stops answering before Chromium has finished
            # flushing the profile. Starting during that short interval may
            # appear to work and then close its DevTools socket underneath the
            # first command. Wait on Chromium's own lock, not a fixed sleep.
            if not self._await_profile_release():
                raise BrowserError("profile_in_use")
        self.profile.mkdir(parents=True, exist_ok=True)
        self._launch()
        # A profile reopened right after a close can reach a browser that is
        # still flushing and then goes away (CI 2026-10-20: no_page on the
        # second start). Confirm a usable tab; if the browser reached is gone,
        # launch once more.
        try:
            self.page(within_s=min(self.timeout_s, STARTUP_PAGE_SECONDS))
        except (BrowserError, WebSocketError, DevtoolsRefused):
            self._page = None
            if self._still_answering(self._port):
                return
            self._await_profile_release()
            self._launch()

    def _launch(self) -> None:
        # A stale port file from a previous run would be read as this run's.
        (self.profile / PORT_FILE).unlink(missing_ok=True)
        arguments = self._arguments()
        try:
            self._process = subprocess.Popen(
                arguments,
                stdout=subprocess.DEVNULL,
                stderr=self._diag_stderr_for(arguments),
            )
        except OSError as failure:
            raise BrowserError("browser_would_not_start", type(failure).__name__) from None
        self._port = self._published_port()

    def close_leftover(self) -> bool:
        """Ask a browser still running on this profile to close itself, and
        wait until the profile is free. Only for a profile this host owns
        alone: there, a running browser can only be one an earlier host
        process started and never stopped (it was killed). Never used on a
        profile a person signs in to by hand."""
        marker = self.profile / PORT_FILE
        try:
            port = int(marker.read_text(encoding="utf-8").splitlines()[0])
        except (OSError, ValueError, IndexError):
            return False
        if not self._ask_it_to_close(port):
            return False
        return self._await_profile_release()

    def _profile_locked(self) -> bool:
        return any((self.profile / name).exists() for name in PROFILE_LOCK_FILES)

    def _await_profile_release(self) -> bool:
        end = time.time() + PROFILE_RELEASE_SECONDS
        while time.time() < end:
            if not self._profile_locked():
                return True
            time.sleep(0.1)
        return not self._profile_locked()

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
                try:
                    first = marker.read_text(encoding="utf-8").splitlines()
                except OSError:
                    # Chromium replaces this file while it starts. Windows
                    # may briefly deny a reader during that replacement,
                    # especially when the same profile has just been closed.
                    # The file is the readiness signal, so treat a temporary
                    # lock exactly like a file that is not ready yet.
                    first = []
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

    def page(self, *, within_s: float | None = None) -> Devtools:
        """The tab. Extensions publish targets of their own -- this machine's
        Edge lists five background pages -- so the type is checked rather
        than the first one taken."""
        if self._page is not None:
            return self._page
        end = time.time() + (self.timeout_s if within_s is None else within_s)
        while time.time() < end:
            for target in self._targets():
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    trace = SocketTrace() if self._diag_dir is not None else None
                    began = time.monotonic()
                    try:
                        page = Devtools(
                            str(target["webSocketDebuggerUrl"]),
                            timeout_s=self.timeout_s,
                            trace=trace,
                        )
                    except WebSocketError as failure:
                        self._diag_attach(target, f"connect:{failure.code}", began, trace)
                        continue
                    try:
                        page.call("Page.enable")
                        page.call("Runtime.enable")
                        self._apply_viewport(page)
                    except (DevtoolsRefused, WebSocketError) as failure:
                        # A just-started browser may still be replacing this
                        # tab (CI 2026-10-20): drop it and look again.
                        page.close()
                        self._diag_attach(target, f"enable:{_named(failure)}", began, trace)
                        continue
                    self._diag_attach(target, "attached", began, trace)
                    self._page = page
                    return page
            time.sleep(0.2)
        raise self._failure("no_page")

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
        except (OSError, ValueError, HTTPException, WebSocketError, DevtoolsRefused):
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
        except (OSError, ValueError, HTTPException):
            # A browser that is shutting down can answer with a broken status
            # line (http.client.BadStatusLine is not an OSError; CI 2026-10-19).
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
        self._await_profile_release()
        self._close_diag_stderr()

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

    # -- diagnostics (opt-in, DIAG_DIR_ENV) -----------------------------

    def _diag_name(self, suffix: str) -> Path:
        assert self._diag_dir is not None
        self._diag_dir.mkdir(parents=True, exist_ok=True)
        return self._diag_dir / f"browser-{time.time_ns()}-{os.getpid()}{suffix}"

    def _diag_stderr_for(self, arguments: list[str]) -> IO[bytes] | int:
        """Where the browser's stderr goes: nowhere, unless diagnostics are on."""
        if self._diag_dir is None:
            return subprocess.DEVNULL
        self._close_diag_stderr()
        try:
            handle = self._diag_name(".stderr.log").open("ab")
            header = {"arguments": arguments, "test": os.environ.get("PYTEST_CURRENT_TEST", "")}
            handle.write((json.dumps(header) + "\n").encode("utf-8"))
            handle.flush()
        except OSError:
            return subprocess.DEVNULL
        self._diag_stderr = handle
        return handle

    def _close_diag_stderr(self) -> None:
        handle, self._diag_stderr = self._diag_stderr, None
        if handle is not None:
            handle.close()

    def _diag_socket(self, event: str, trace: SocketTrace | None, **facts: Any) -> None:
        """One socket's story, appended to this browser's socket log: who
        closed it, how, and what was asked of it last. Protocol facts only
        (`SocketTrace`)."""
        if self._diag_dir is None or trace is None:
            return
        record = {
            "event": event,
            "test": os.environ.get("PYTEST_CURRENT_TEST", ""),
            "port": self._port,
            **facts,
            "socket": trace.as_record(),
        }
        try:
            if self._diag_sockets is None:
                self._diag_sockets = self._diag_name("-sockets.jsonl")
            with self._diag_sockets.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except OSError:
            pass  # A diagnostic never replaces what it describes.

    def _diag_attach(
        self,
        target: dict[str, Any],
        outcome: str,
        began: float,
        trace: SocketTrace | None,
    ) -> None:
        """One attempt by `page` to attach to a tab, and how it ended."""
        if self._diag_dir is None:
            return
        attempt = {
            "target_id": str(target.get("id", "")),
            "outcome": outcome,
            "elapsed_s": round(time.monotonic() - began, 3),
        }
        self._diag_attaches = (*self._diag_attaches, attempt)[-DIAG_ATTACHES_KEPT:]
        self._diag_socket("attach", trace, **attempt)

    def _diag_lost(self, event: str, page: Any) -> None:
        """A socket that was in use and failed: its trace says who ended it."""
        self._diag_socket(event, getattr(page, "trace", None))

    def _diag_endpoint(self, path: str) -> Any:
        """One DevTools HTTP endpoint's answer, or why there was none."""
        if self._port is None:
            return {"unavailable": "no port"}
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{self._port}{path}", timeout=2
            ) as answer:
                return json.loads(answer.read())
        except (OSError, ValueError, HTTPException) as failure:
            return {"unavailable": type(failure).__name__}

    def _failure(self, code: BrowserErrorCode, detail: str = "") -> BrowserError:
        """The error to raise, recorded first when diagnostics are on.

        What is recorded is the browser's version and its targets' types and
        addresses -- the same things `/json/list` publishes -- and never
        anything read from a page."""
        if self._diag_dir is not None:
            try:
                listed = self._diag_endpoint("/json/list")
                targets = (
                    [
                        {
                            **({"id": item["id"]} if "id" in item else {}),
                            "type": item.get("type"),
                            "url": item.get("url"),
                        }
                        for item in listed
                        if isinstance(item, dict)
                    ]
                    if isinstance(listed, list)
                    else listed
                )
                record = {
                    "code": code,
                    "detail": detail,
                    "test": os.environ.get("PYTEST_CURRENT_TEST", ""),
                    "executable": self.executable,
                    "profile": str(self.profile),
                    "port": self._port,
                    "version": self._diag_endpoint("/json/version"),
                    "targets": targets,
                    "attach_attempts": list(self._diag_attaches),
                    "socket_log": str(self._diag_sockets) if self._diag_sockets else "",
                }
                self._diag_name(f"-{code}.json").write_text(
                    json.dumps(record, indent=2), encoding="utf-8"
                )
            except OSError:
                pass  # A diagnostic never replaces the failure it describes.
        return BrowserError(code, detail)

    # -- looking -------------------------------------------------------

    def _evaluate(self, expression: str) -> Any:
        page = self.page()
        try:
            answer = page.call("Runtime.evaluate", expression=expression, returnByValue=True)
        except (DevtoolsRefused, WebSocketError) as failure:
            self._diag_lost("evaluate_lost", page)
            raise BrowserError("browser_lost", type(failure).__name__) from None
        result = answer.get("result", {})
        if answer.get("exceptionDetails"):
            raise BrowserError("navigation_failed", "the page could not be read")
        return result.get("value")

    def evaluate(self, expression: str) -> Any:
        """Run one expression on the page and return its JSON value; for
        callers that replay recorded steps (`integrations.web_script`)."""
        return self._evaluate(expression)

    @contextmanager
    def observe_network(
        self, allowed_origins: tuple[str, ...], *, timeout_s: float | None = None
    ) -> Iterator[_NetworkObservation]:
        """Observe before script navigation; never recover a lost observation connection."""
        page = self.page()
        if page.network_observer is not None:
            raise BrowserError("web_network_observer_unavailable")
        observer = _NetworkObservation(self, page, allowed_origins)
        page.network_events_lost = False
        page.network_observer = observer.tracker
        setup_deadline = time.monotonic() + (self.timeout_s if timeout_s is None else timeout_s)
        try:
            with page.within_deadline(setup_deadline):
                page.call("Network.enable")
                page.call("Performance.enable", timeDomain="timeTicks")
            yield observer
        finally:
            # Teardown must not turn an already executed result into a retry.
            cleanup_deadline = observer.last_deadline or setup_deadline
            for method in ("Network.disable", "Performance.disable"):
                if time.monotonic() >= cleanup_deadline:
                    break
                try:
                    with page.within_deadline(cleanup_deadline):
                        page.call(method)
                except (DevtoolsRefused, WebSocketError, OSError):
                    pass
            page.network_observer = None

    def navigate(self, url: str, *, settle_s: float = 1.0) -> None:
        page = self.page()
        try:
            answer = page.call("Page.navigate", url=url)
        except WebSocketError:
            # A freshly started browser can replace its first tab, which drops
            # the socket to the old one (CI 2026-10-19, WinError 10053). Attach
            # to the current tab once and ask again; a second loss is real.
            # If the browser itself is gone -- a profile reopened right after a
            # close can reach one that is still shutting down (CI 2026-10-20)
            # -- launch it once more instead of waiting for a tab that will
            # never come.
            self._diag_lost("navigate_lost", page)
            page.close()
            self._page = None
            if not self._still_answering(self._port):
                self._await_profile_release()
                self._launch()
            page = self.page()
            try:
                answer = page.call("Page.navigate", url=url)
            except (DevtoolsRefused, WebSocketError) as failure:
                self._diag_lost("navigate_lost_again", page)
                raise self._failure("navigation_failed", type(failure).__name__) from None
        except DevtoolsRefused as failure:
            raise self._failure("navigation_failed", type(failure).__name__) from None
        if answer.get("errorText"):
            # The browser's own word for why, which is about the address and
            # not about anything on a page.
            raise self._failure("navigation_failed", str(answer["errorText"]))
        self._await_load(page)
        # What a page does to itself after loading, which no event announces.
        time.sleep(settle_s)

    def reload(
        self,
        *,
        check_origin: Callable[[str], None] | None = None,
        timeout_s: float | None = None,
    ) -> None:
        """Reload this attached tab once and await a genuinely new document.

        The old document can already be complete during a same-document SPA
        navigation. Only a changed main-frame loader followed by its complete
        document proves a reload. Every CDP call shares the absolute budget;
        a lost socket fails without replaying a possibly submitted request.
        """
        page = self._page
        if page is None:
            raise BrowserError("no_page")
        deadline = time.monotonic() + (self.timeout_s if timeout_s is None else timeout_s)
        previous_timeout = page.timeout_s

        def remaining() -> float:
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise BrowserError("navigation_failed", "reload_timeout")
            return budget

        def call(method: str, **params: Any) -> dict[str, Any]:
            page.timeout_s = min(previous_timeout, remaining())
            try:
                answer = page.call(method, **params)
            except (DevtoolsRefused, WebSocketError) as error:
                raise BrowserError("navigation_failed", type(error).__name__) from None
            remaining()
            return answer

        def frame() -> dict[str, Any]:
            answer = call("Page.getFrameTree")
            current = answer.get("frameTree", {}).get("frame", {})
            if (
                not isinstance(current, dict)
                or not current.get("loaderId")
                or not current.get("id")
            ):
                raise BrowserError("navigation_failed", "reload_no_loader")
            url = current.get("url")
            if not isinstance(url, str) or not url:
                raise BrowserError("navigation_failed", "reload_no_url")
            if check_origin is not None:
                check_origin(url)
            remaining()
            return current

        try:
            original = frame()
            call("Page.reload")
            while True:
                current = frame()
                if current["loaderId"] != original["loaderId"]:
                    answer = call(
                        "Runtime.evaluate",
                        expression="({ready:document.readyState,url:document.location.href})",
                        returnByValue=True,
                    )
                    state = answer.get("result", {}).get("value")
                    if isinstance(state, dict) and isinstance(state.get("url"), str):
                        if check_origin is not None:
                            check_origin(state["url"])
                        remaining()
                        if state.get("ready") == "complete":
                            # Readiness and FrameTree are separate CDP snapshots.
                            # A subsequent commit must not inherit the prior
                            # document's complete state.
                            confirmed = frame()
                            if (
                                confirmed["id"] == current["id"]
                                and confirmed["loaderId"] == current["loaderId"]
                            ):
                                return
                time.sleep(min(0.05, remaining()))
        finally:
            page.timeout_s = previous_timeout

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
                self._diag_lost("await_load_lost", page)
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
            self._diag_lost("screenshot_lost", page)
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

    def hover_at(self, x: float, y: float, *, timeout_s: float) -> None:
        """Move the unpressed native pointer within the caller's remaining budget."""
        page = self._page
        if page is None:
            raise BrowserError("no_page")
        if timeout_s <= 0:
            raise BrowserError("click_failed", "hover_timeout")
        previous_timeout = page.timeout_s
        page.timeout_s = min(previous_timeout, timeout_s)
        try:
            page.call(
                "Input.dispatchMouseEvent",
                type="mouseMoved",
                x=x,
                y=y,
                button="none",
                buttons=0,
            )
        except (DevtoolsRefused, WebSocketError) as failure:
            raise BrowserError("click_failed", type(failure).__name__) from None
        finally:
            page.timeout_s = previous_timeout

    def click_at(self, x: float, y: float) -> None:
        """Send real pointer events, including trusted press/release for UI controls."""
        page = self.page()
        try:
            for event in ("mousePressed", "mouseReleased"):
                page.call(
                    "Input.dispatchMouseEvent",
                    type=event,
                    x=x,
                    y=y,
                    button="left",
                    clickCount=1,
                )
        except (DevtoolsRefused, WebSocketError) as failure:
            raise BrowserError("click_failed", type(failure).__name__) from None

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
