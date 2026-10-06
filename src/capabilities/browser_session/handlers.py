"""`browser/operate@1.0.0`: operate the host's Edge for a task (lab gap L1).

Owner direction 2026-10-06: the Agent uses Edge, as people do for the company
systems, and signing in is clicking through the company's automatic sign-in
(a link or a "continue" button), so no password is asked for or typed here.

One call replays a short list of `integrations.web_script` actions (open,
fill, click, read_table, read_text, read_record, download), optionally once
per item of `for_each`, and returns what they read plus a look at the page
it ends on: its text and the things on it that can be used, so the model can
choose the next actions. The browser stays open between calls (one profile
of its own), so a conversation can work through a site step by step, and a
drafted Workflow can carry the same actions as a step.

Bounds: every page stays on the host's `web.allowed_origins`; downloads land
only in `output/downloads/` of a task workspace under an allowed root; page
content is data returned to the caller, never instructions.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import Field, JsonValue

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityRefused
from common.base import Contract, Symbol, Text
from common.execution import RequestContext
from integrations.web_script import ScriptRunner, WebAction, WebScript, WebScriptError

SPEC = CapabilitySpec.model_validate({
    "identity": {"namespace": "browser", "name": "operate", "version": "1.0.0"},
    "name": "browser.operate",
    "description": "Operate the host's Edge on allowed sites: open, fill, click, read, download",
    "input_contract": "browser.operate.input.v1",
    "output_contract": "browser.operate.output.v1",
    "side_effect": "external_side_effect",
    "policy": {
        "risk": "medium",
        "approval_required": True,
        "required_permissions": ["browser.operate"],
        "policy_refs": ["web-origin-policy"],
    },
})
MAX_PAGE_CHARS = 6_000
MAX_ELEMENTS = 80
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class BrowserRequest(Contract):
    actions: tuple[WebAction, ...] = Field(default=(), max_length=50)
    values: dict[Symbol, JsonValue] = Field(default_factory=dict)
    for_each: tuple[Text, ...] | None = Field(default=None, max_length=200)
    # Absolute task workspace; needed only for `download`.
    workspace: Text | None = None
    look: bool = True


class BrowserResult(Contract):
    url: str = ""
    data: dict[Symbol, JsonValue] = Field(default_factory=dict)
    items: dict[Text, JsonValue] = Field(default_factory=dict)
    downloads: tuple[Text, ...] = ()
    page: str = ""


class BrowserSessionHandler:
    """Holds one browser for the host's lifetime and serializes its use."""

    def __init__(
        self,
        allowed_origins: tuple[str, ...],
        profile: Path,
        *,
        headless: bool,
        timeout_s: float,
        workspace_roots: tuple[str, ...],
        browser_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.allowed_origins = allowed_origins
        self.workspace_roots = tuple(Path(root).resolve() for root in workspace_roots)
        self.timeout_s = timeout_s
        self._factory = browser_factory or (lambda: _edge(profile, headless, timeout_s))
        self._browser: Any = None
        self._lock = threading.Lock()

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        request = BrowserRequest.model_validate(inputs)
        return await asyncio.to_thread(self.run, request)

    def close(self) -> None:
        with self._lock:
            if self._browser is not None:
                try:
                    self._browser.close()
                finally:
                    self._browser = None

    def _page(self) -> Any:
        if self._browser is not None:
            try:
                self._browser.evaluate("1")
                return self._browser
            except Exception:  # noqa: BLE001 - a lost browser is started again
                self._browser = None
        browser = self._factory()
        browser.start()
        self._browser = browser
        return browser

    def _downloads(self, raw: str | None) -> Path:
        if raw is None:
            raise CapabilityRefused("browser_workspace_missing")
        path = Path(raw.strip())
        if not path.is_absolute():
            raise CapabilityRefused("browser_workspace_not_absolute")
        resolved = path.resolve()
        if not any(resolved == root or root in resolved.parents for root in self.workspace_roots):
            raise CapabilityRefused("browser_workspace_not_allowed")
        if not resolved.is_dir():
            raise CapabilityRefused("browser_workspace_missing")
        folder = resolved / "output" / "downloads"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def run(self, request: BrowserRequest) -> BrowserResult:
        with self._lock:
            try:
                browser = self._page()
            except Exception as error:  # noqa: BLE001 - the browser's own typed codes
                code = str(getattr(error, "code", "browser_would_not_start"))
                raise CapabilityRefused(code) from None
            saved: list[str] = []
            folder: Path | None = None

            def download(click: Callable[[], None], name: str) -> str:
                nonlocal folder
                if folder is None:
                    folder = self._downloads(request.workspace)
                kept = _download(browser, folder, click, name, self.timeout_s)
                saved.append(kept)
                return kept

            runner = ScriptRunner(browser, self.allowed_origins, timeout_s=self.timeout_s,
                                  downloader=download)
            data: dict[str, JsonValue] = {}
            items: dict[str, JsonValue] = {}
            try:
                if request.actions:
                    if request.for_each is None:
                        result = runner.run(WebScript(actions=request.actions,
                                                      values=request.values), "act")
                        data = dict(result.data)
                    else:
                        for item in request.for_each:
                            values = {**request.values, "item": item}
                            result = runner.run(WebScript(actions=request.actions,
                                                          values=values), "act")
                            items[item] = dict(result.data)
            except WebScriptError as error:
                # A code only; the model looks again with an empty action list.
                raise CapabilityRefused(error.code) from None
            except Exception as error:  # noqa: BLE001 - the browser's own typed codes
                raise CapabilityRefused(str(getattr(error, "code", "browser_failed"))) from None
            url = ""
            try:
                url = str(browser.evaluate("document.location.href") or "")
            except Exception:  # noqa: BLE001
                pass
            return BrowserResult(url=url, data=data, items=items, downloads=tuple(saved),
                                 page=_described(browser) if request.look else "")


def _edge(profile: Path, headless: bool, timeout_s: float) -> Any:
    from integrations.browser import Browser

    return Browser(profile, headless=headless, timeout_s=timeout_s)


def _described(browser: Any) -> str:
    try:
        view = browser.look()
    except Exception:  # noqa: BLE001 - a look is a courtesy, never the result
        return ""
    view = view.model_copy(update={"elements": view.elements[:MAX_ELEMENTS]})
    text: str = view.described(limit=MAX_PAGE_CHARS)
    return text


def _download(browser: Any, folder: Path, click: Callable[[], None], name: str,
              timeout_s: float) -> str:
    """Let the page's own link or button send the file, then keep it as `name`."""
    page = browser.page()
    for method in ("Browser.setDownloadBehavior", "Page.setDownloadBehavior"):
        try:
            page.call(method, behavior="allow", downloadPath=str(folder))
            break
        except Exception:  # noqa: BLE001 - the older name on older browsers
            continue
    before = {item.name for item in folder.iterdir()}
    click()
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        fresh = [item for item in folder.iterdir() if item.name not in before
                 and not item.name.endswith((".crdownload", ".tmp"))]
        if fresh:
            got = fresh[0]
            size = -1
            while size != got.stat().st_size:
                size = got.stat().st_size
                time.sleep(0.3)
            target = folder / (_SAFE_NAME.sub("_", name).strip("._") or "download")
            if target != got:
                got.replace(target)
            return str(target)
        time.sleep(0.2)
    raise WebScriptError("web_download_timed_out")
