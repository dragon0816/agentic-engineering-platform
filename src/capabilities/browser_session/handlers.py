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

Bounds: every page is an http(s) page the host's `web.allowed_origins` allows
("*", the default, is any site); downloads land
only in `output/downloads/` of a task workspace under an allowed root; page
content is data returned to the caller, never instructions.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from pydantic import Field, JsonValue

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityExecutionFailed, CapabilityRefused
from common.base import Contract, Symbol, Text
from common.execution import RequestContext
from common.trace import redact
from integrations.web_script import (
    DOMInspection,
    DOMOverview,
    PaginationTargetField,
    ScriptRunner,
    WebAction,
    WebScript,
    WebScriptError,
    origin_permitted,
)

SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "browser", "name": "operate", "version": "1.0.0"},
        "name": "browser.operate",
        "description": "Operate the host's Edge on web sites: open, fill, click, read, download",
        "input_contract": "browser.operate.input.v1",
        "output_contract": "browser.operate.output.v1",
        "side_effect": "external_side_effect",
        "policy": {
            "risk": "medium",
            "approval_required": True,
            "required_permissions": ["browser.operate"],
            "policy_refs": ["web-origin-policy"],
        },
    }
)
MAX_PAGE_CHARS = 6_000
MAX_ELEMENTS = 80
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

# Host-owned, request-local narrowing for an approved repair preflight. Ordinary
# requests and their model input contract are unchanged; threads copy this scope.
_ORIGIN_SCOPE: ContextVar[tuple[str, ...] | None] = ContextVar(
    "authoring_browser_origin_scope", default=None
)


@contextmanager
def browser_origin_scope(origins: tuple[str, ...]) -> Iterator[None]:
    token = _ORIGIN_SCOPE.set(origins)
    try:
        yield
    finally:
        _ORIGIN_SCOPE.reset(token)


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
    page: str = Field(default="", max_length=MAX_PAGE_CHARS)
    failed_action_index: int | None = Field(default=None, ge=0, le=49)
    failed_action_kind: str | None = None
    failed_target_field: PaginationTargetField | None = None
    diagnostics: DOMInspection | None = None
    overview: DOMOverview | None = None
    diagnostic_error: str | None = None


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
        try:
            browser.start()
        except Exception as error:
            # This profile is the Agent's alone, so a browser holding it was
            # left by an earlier host process that was stopped hard: ask it
            # to close (keeping the profile intact) and start once more.
            leftover = getattr(browser, "close_leftover", None)
            in_use = getattr(error, "code", None) == "profile_in_use"
            if not in_use or leftover is None or not leftover():
                raise
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
        if resolved.exists() and not resolved.is_dir():
            raise CapabilityRefused("browser_workspace_not_a_folder")
        resolved.mkdir(parents=True, exist_ok=True)
        folder = resolved / "output" / "downloads"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def run(self, request: BrowserRequest) -> BrowserResult:
        with self._lock:
            allowed = self.allowed_origins
            scoped = _ORIGIN_SCOPE.get()
            if scoped is not None:
                if not scoped or not all(
                    origin_permitted(origin, set(allowed)) for origin in scoped
                ):
                    raise CapabilityRefused("web_origin_not_allowed")
                allowed = scoped
            folder = (
                self._downloads(request.workspace)
                if any(action.do == "download" for action in request.actions)
                else None
            )
            try:
                browser = self._page()
            except Exception as error:  # noqa: BLE001 - the browser's own typed codes
                code = str(getattr(error, "code", "browser_would_not_start"))
                raise CapabilityRefused(code) from None
            saved: list[str] = []

            def download(click: Callable[[], None], name: str) -> str:
                nonlocal folder
                if folder is None:
                    folder = self._downloads(request.workspace)
                kept = _download(browser, folder, click, name, self.timeout_s)
                saved.append(kept)
                return kept

            runner = ScriptRunner(browser, allowed, timeout_s=self.timeout_s, downloader=download)
            data: dict[str, JsonValue] = {}
            items: dict[str, JsonValue] = {}
            try:
                if request.actions:
                    if request.for_each is None:
                        result = runner.run(
                            WebScript(actions=request.actions, values=request.values), "act"
                        )
                        data = dict(result.data)
                    else:
                        for item in request.for_each:
                            values = {**request.values, "item": item}
                            result = runner.run(
                                WebScript(actions=request.actions, values=values), "act"
                            )
                            items[item] = dict(result.data)
            except WebScriptError as error:
                observation, diagnostic_error = _diagnostics(runner)
                failure = BrowserResult(
                    url=_safe_url(runner),
                    data=data,
                    items=items,
                    downloads=tuple(saved),
                    page=_described(observation),
                    overview=observation.overview if observation is not None else None,
                    diagnostics=observation,
                    diagnostic_error=diagnostic_error,
                    failed_action_index=error.action_index,
                    failed_action_kind=error.action_kind,
                    failed_target_field=error.target_field,
                )
                where = (
                    f"actions[{error.action_index}] ({error.action_kind})"
                    if error.action_index is not None
                    else None
                )
                if error.target_field is not None:
                    where = f"{where} {error.target_field}" if where else error.target_field
                raise CapabilityExecutionFailed(error.code, failure, where=where) from None
            except Exception as error:  # noqa: BLE001 - the browser's own typed codes
                raise CapabilityRefused(str(getattr(error, "code", "browser_failed"))) from None
            observation, _ = _diagnostics(runner) if request.look else (None, None)
            return BrowserResult(
                url=_safe_url(runner),
                data=data,
                items=items,
                downloads=tuple(saved),
                page=_described(observation),
                overview=observation.overview if observation is not None else None,
            )


def _edge(profile: Path, headless: bool, timeout_s: float) -> Any:
    from integrations.browser import DESKTOP_VIEWPORT, Browser

    return Browser(profile, headless=headless, timeout_s=timeout_s, viewport=DESKTOP_VIEWPORT)


def _safe_url(runner: ScriptRunner) -> str:
    """Keep navigation state while redacting recognizable credential material."""
    from urllib.parse import quote, unquote_plus, urlsplit, urlunsplit

    try:
        raw = str(runner.page.evaluate("document.location.href") or "")
        allowed = {origin.rstrip("/").lower() for origin in runner.allowed}
        if not origin_permitted(raw, allowed):
            return ""
        parts = urlsplit(raw)
        host = parts.hostname or ""
        if ":" in host:
            host = f"[{host}]"
        if parts.port is not None:
            host += f":{parts.port}"

        def component(raw_component: str) -> str:
            chunks: list[str] = []
            for chunk in raw_component.split("&"):
                key, separator, value = chunk.partition("=")
                decoded_key, decoded_value = unquote_plus(key), unquote_plus(value)
                secret_label = (
                    "access_token"
                    if re.fullmatch(
                        r"token|secret|client_secret|id_token|session_token|authorization|csrf|sessionid",
                        decoded_key,
                        re.IGNORECASE,
                    )
                    else decoded_key
                )
                cleaned, count = redact(decoded_value, secret_label)
                if not count:
                    cleaned_chunk, count = redact(unquote_plus(chunk))
                    chunks.append(quote(str(cleaned_chunk), safe="=/?:[]") if count else chunk)
                else:
                    chunks.append(key + separator + quote(str(cleaned), safe="[]"))
            return "&".join(chunks)

        path, _ = redact(parts.path)
        return urlunsplit(
            (parts.scheme, host, str(path), component(parts.query), component(parts.fragment))
        )
    except Exception:  # noqa: BLE001 - a lost page is never evidence
        return ""


def _diagnostics(runner: ScriptRunner) -> tuple[DOMInspection | None, str | None]:
    try:
        observation, _ = redact(runner.inspect(limit=MAX_ELEMENTS))
        return DOMInspection.model_validate(observation), None
    except WebScriptError as error:
        return None, error.code
    except Exception:  # noqa: BLE001 - original failure must survive a lost page
        return None, "web_diagnostics_unavailable"


def _described(observation: DOMInspection | None) -> str:
    if observation is None:
        return ""
    if observation.overview is not None:
        view = observation.overview
        lines = ["Visible controls (field values omitted):"]
        for control in view.controls:
            state = " ".join(f"{key}={value!r}" for key, value in control.state.items())
            lines.append(
                f"{control.tag} {control.kind} {control.path} "
                f"disabled={control.disabled} {state} {control.label}"
            )
        if view.controls_truncated:
            lines.append("More controls exist; narrow inspection scope for details.")
        for table in view.tables:
            lines.append(f"Table: {table.tag} {table.path}")
        lines.append("Visible text:\n" + view.text)
        if view.time_limit_reached or view.scan_limit_reached:
            lines.append("Observation scan budget reached; narrow inspection scope.")
        return "\n".join(lines)[:MAX_PAGE_CHARS]
    lines = [f"DOM scope={observation.scope}; next_offset={observation.next_offset}"]
    for element in observation.elements:
        attrs = " ".join(f"{key}={value!r}" for key, value in element.attributes.items())
        lines.append(
            f"[{element.index}] parent={element.parent} {element.tag} "
            f"visible={element.visible} disabled={element.disabled} {attrs} {element.text}"
        )
    return "\n".join(lines)[:MAX_PAGE_CHARS]


def _download(
    browser: Any, folder: Path, click: Callable[[], None], name: str, timeout_s: float
) -> str:
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
        fresh = [
            item
            for item in folder.iterdir()
            if item.name not in before and not item.name.endswith((".crdownload", ".tmp"))
        ]
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
