"""Replay a recorded web procedure: fixed targets, no model at run time.

SOP to Workflow (docs/phases/SOP_TO_WORKFLOW.md W2, owner decision
2026-10-06): a Workflow's web step carries the actions recorded when it was
authored, and the run repeats exactly those. A target is found by what a
person sees (a field's label, a button's text) or by a CSS selector, inside
a table row chosen by a column value when needed. A target that is missing or
ambiguous stops the step with a typed failure instead of guessing, because a
changed page is a reason to look again, not to click something else.

Two modes. `read` may open pages, fill fields, follow links and submit GET
forms (searching), and read tables and text: a click on anything that could
change the site (a POST form, a script-only button) is refused at run time,
whatever the step says. `act` may click such buttons, once per item of
`for_each`. Every page must stay on an allowed origin.

What a page says is data, never instructions: nothing here hands page
content to a model, and what is read is returned only as values.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from typing import Any, Literal, Protocol, Self
from urllib.parse import urlsplit

from pydantic import Field, JsonValue, model_validator

from common.base import Contract, Symbol, Text

ScriptMode = Literal["read", "act"]
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
MAX_TABLE_ROWS = 2000


class WebScriptError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WebTarget(Contract):
    """What to act on: a label as shown on the page, or a CSS selector."""

    label: Text | None = None
    css: Text | None = None
    kind: Literal["field", "button", "link", "any"] = "any"

    @model_validator(mode="after")
    def one_way_to_find(self) -> Self:
        if (self.label is None) == (self.css is None):
            raise ValueError("a target names exactly one of label or css")
        return self


class RowScope(Contract):
    """The one table row whose `column` cell equals `equals`."""

    table: Text
    column: Text
    equals: Text


class WebPagination(Contract):
    """Visible page controls; pagination must begin at page one and advance."""

    next: WebTarget
    current: WebTarget
    total: WebTarget
    max_pages: int = Field(default=200, ge=1, le=200, strict=True)
    key_columns: tuple[Text, ...] = Field(default=(), max_length=10)


class WebAction(Contract):
    # `download` clicks a link or button and keeps the file it sends under
    # `save_as`; `read_record` reads a two-column table of field names and
    # values (a detail page's header). Both need a runner that supports them.
    do: Literal[
        "open", "fill", "click", "read_table", "read_text", "download", "read_record", "wait_for"
    ]
    url: Text | None = None
    target: WebTarget | None = None
    row: RowScope | None = None
    value: Text | None = None
    table: Text | None = None
    save_as: Symbol | None = None
    header_table: Text | None = None
    pagination: WebPagination | None = None

    @model_validator(mode="after")
    def complete(self) -> Self:
        needs = {
            "open": self.url is not None,
            "fill": self.target is not None and self.value is not None,
            "click": self.target is not None,
            "read_table": self.table is not None and self.save_as is not None,
            "read_text": self.target is not None and self.save_as is not None,
            "download": self.target is not None and self.save_as is not None,
            "read_record": self.table is not None and self.save_as is not None,
            "wait_for": self.target is not None and self.value is not None,
        }
        if not needs[self.do]:
            raise ValueError(f"a {self.do} action is missing what it needs")
        if self.do != "read_table" and (
            self.header_table is not None or self.pagination is not None
        ):
            raise ValueError("header_table and pagination belong only to read_table")
        if self.do == "wait_for" and self.value is not None:
            try:
                re.compile(self.value)
            except re.error as error:
                raise ValueError("wait_for value must be a valid regular expression") from error
        return self


class WebScript(Contract):
    """The recorded procedure plus the run's values for its `{placeholders}`.
    With `for_each`, the actions run once per item, `{item}` bound to it."""

    actions: tuple[WebAction, ...] = Field(min_length=1, max_length=50)
    values: dict[Symbol, JsonValue] = Field(default_factory=dict)
    for_each: tuple[Text, ...] | None = Field(default=None, max_length=200)


class WebScriptResult(Contract):
    url: Text
    data: dict[Symbol, JsonValue] = Field(default_factory=dict)
    done: tuple[Text, ...] = ()


class ScriptPage(Protocol):
    def navigate(self, url: str) -> None: ...

    def evaluate(self, expression: str) -> Any: ...


_FIND = r"""
(spec) => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const caption = e => {
    const own = e.labels && e.labels.length ? e.labels[0].innerText : '';
    return norm(own || e.getAttribute('aria-label') || e.getAttribute('placeholder') ||
                e.getAttribute('title') || e.innerText || e.value || '');
  };
  let scope = document;
  if (spec.row) {
    const table = document.querySelector(spec.row.table);
    if (!table) return {error: 'web_table_missing'};
    const heads = [...table.querySelectorAll('thead th')].map(th => norm(th.innerText));
    const column = heads.indexOf(spec.row.column);
    if (column < 0) return {error: 'web_column_missing'};
    const rows = [...table.querySelectorAll('tbody tr')].filter(
      tr => tr.children[column] && norm(tr.children[column].innerText) === spec.row.equals);
    if (!rows.length) return {error: 'web_row_missing'};
    if (rows.length > 1) return {error: 'web_row_ambiguous'};
    scope = rows[0];
  }
  const kinds = {
    field: 'input:not([type=hidden]), select, textarea',
    button: 'button, input[type=submit], input[type=button], [role=button]',
    link: 'a[href]',
    any: 'a[href], button, input:not([type=hidden]), select, textarea, '
      + '[role=button], [role=option]'};
  const matches = spec.css ? [...scope.querySelectorAll(spec.css)]
    : [...scope.querySelectorAll(kinds[spec.kind])].filter(e => caption(e) === spec.label);
  const found = matches.filter(e => e.getClientRects().length
    && getComputedStyle(e).visibility !== 'hidden');
  if (!found.length) return {error: 'web_target_missing'};
  if (found.length > 1) return {error: 'web_target_ambiguous'};
  return {element: found[0]};
}
"""

_ACT = r"""
(() => {
  const find = %(find)s;
  const spec = %(spec)s;
  const hit = find(spec);
  if (hit.error) return JSON.stringify(hit);
  const e = hit.element;
  if (spec.op === 'fill') {
    e.focus(); e.value = spec.value;
    e.dispatchEvent(new Event('input', {bubbles: true}));
    e.dispatchEvent(new Event('change', {bubbles: true}));
    return JSON.stringify({ok: true});
  }
  if (spec.op === 'click') {
    if (spec.mode === 'read') {
      const href = e.tagName === 'A' ? (e.getAttribute('href') || '') : '';
      const link = href && !href.toLowerCase().startsWith('javascript:');
      const form = e.form || null;
      const submits = form && (e.type === 'submit' || (e.tagName === 'BUTTON' && !e.type));
      const reading = submits && (form.getAttribute('method') || 'get').toLowerCase() === 'get';
      if (!link && !reading) return JSON.stringify({error: 'web_click_not_read_only'});
    }
    if (spec.pointer) {
      if (e.disabled || e.getAttribute('aria-disabled') === 'true')
        return JSON.stringify({error: 'web_target_disabled'});
      e.scrollIntoView({block: 'center', inline: 'center'});
      const r = e.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2;
      if (!r.width || !r.height || getComputedStyle(e).visibility === 'hidden')
        return JSON.stringify({error: 'web_target_not_visible'});
      const top = document.elementFromPoint(x, y);
      if (!top || (top !== e && !e.contains(top)))
        return JSON.stringify({error: 'web_target_obscured'});
      return JSON.stringify({ok: true, pointer: {x, y}});
    }
    e.click();
    return JSON.stringify({ok: true});
  }
  if (spec.op === 'read_text') {
    return JSON.stringify({ok: true, text: (e.innerText || e.value || '').trim()});
  }
  return JSON.stringify({error: 'web_action_unknown'});
})()
"""

_READ_RECORD = r"""
(() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const table = document.querySelector(%(css)s);
  if (!table) return JSON.stringify({error: 'web_table_missing'});
  const record = {};
  [...table.querySelectorAll('tr')].forEach(tr => {
    const cells = [...tr.children];
    if (cells.length >= 2) record[norm(cells[0].innerText)] = norm(cells[1].innerText);
  });
  return JSON.stringify({ok: true, record: record});
})()
"""

_READ_TABLE = r"""
(() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const table = document.querySelector(%(css)s);
  if (!table) return JSON.stringify({error: 'web_table_missing'});
  const headerSelector = %(header)s;
  const header = headerSelector ? document.querySelector(headerSelector) : table;
  if (!header) return JSON.stringify({error: 'web_table_header_missing'});
  let heads = [...header.querySelectorAll('thead th')].map(th => norm(th.innerText));
  let rows = [...table.querySelectorAll('tbody tr')];
  if (!heads.length && rows.length) {
    heads = [...rows[0].children].map(c => norm(c.innerText)); rows = rows.slice(1);
  }
  const out = rows.slice(0, %(limit)d).map(tr => {
    const cells = [...tr.children].map(c => norm(c.innerText));
    const row = {};
    heads.forEach((h, i) => { if (h) row[h] = cells[i] === undefined ? '' : cells[i]; });
    return row;
  });
  return JSON.stringify({ok: true, rows: out, truncated: rows.length > %(limit)d});
})()
"""


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


#: In `allowed_origins`, any web site (owner 2026-10-08: every page may be
#: used; network access itself is governed by company IT).
ANY_ORIGIN = "*"
WEB_SCHEMES = ("http", "https")


def origin_permitted(url: str, allowed: set[str] | frozenset[str]) -> bool:
    """A web page (http or https) whose origin the host allows. Other schemes
    (file, javascript, data, browser pages) are never web pages to operate."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in WEB_SCHEMES or not parts.netloc:
        return False
    return ANY_ORIGIN in allowed or _origin(url) in allowed


def _fill_in(text: str, values: Mapping[str, JsonValue]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values or values[name] is None:
            raise WebScriptError("web_value_missing")
        return str(values[name])

    return _PLACEHOLDER.sub(replace, text)


class ScriptRunner:
    def __init__(
        self,
        page: ScriptPage,
        allowed_origins: tuple[str, ...],
        *,
        settle_s: float = 0.3,
        timeout_s: float = 30.0,
        downloader: Callable[[Callable[[], None], str], str] | None = None,
    ) -> None:
        self.page = page
        self.allowed = {origin.rstrip("/").lower() for origin in allowed_origins}
        self.settle_s = settle_s
        self.timeout_s = timeout_s
        # Given the click that starts a download and the name to keep it
        # under, returns where the file was kept. None: downloads refused.
        self.downloader = downloader

    def run(self, script: WebScript, mode: ScriptMode) -> WebScriptResult:
        checked = WebScript.model_validate(script)
        data: dict[str, JsonValue] = {}
        done: list[str] = []
        items: tuple[str | None, ...] = (
            checked.for_each if checked.for_each is not None else (None,)
        )
        for item in items:
            values: dict[str, JsonValue] = dict(checked.values)
            if item is not None:
                values["item"] = item
            for action in checked.actions:
                self._do(action, values, mode, data)
            if item is not None:
                done.append(item)
        return WebScriptResult(url=self._url(), data=data, done=tuple(done))

    def _do(
        self,
        action: WebAction,
        values: Mapping[str, JsonValue],
        mode: ScriptMode,
        data: dict[str, JsonValue],
    ) -> None:
        if action.do == "wait_for":
            assert action.target is not None and action.value is not None
            deadline = time.monotonic() + self.timeout_s
            while True:
                self._check_origin()
                try:
                    answer = self._perform(
                        {"op": "read_text", "mode": "read", **action.target.model_dump()}
                    )
                    if re.fullmatch(action.value, str(answer.get("text", ""))):
                        return
                except WebScriptError as error:
                    if error.code != "web_target_missing":
                        raise
                if time.monotonic() >= deadline:
                    raise WebScriptError("web_wait_timeout")
                time.sleep(0.1)
        if action.do == "open":
            assert action.url is not None
            url = _fill_in(action.url, values)
            if not origin_permitted(url, self.allowed):
                raise WebScriptError("web_origin_not_allowed")
            try:
                self.page.navigate(url)
            except Exception as error:  # noqa: BLE001 - the browser's own codes
                raise WebScriptError(getattr(error, "code", "navigation_failed")) from None
            self._check_origin()
            return
        if action.do == "read_record":
            assert action.table is not None and action.save_as is not None
            answer = self._evaluate(_READ_RECORD % {"css": json.dumps(action.table)})
            data[action.save_as] = answer["record"]
            return
        if action.do == "read_table":
            assert action.table is not None and action.save_as is not None
            data[action.save_as] = self._table_pages(action, mode)
            return
        spec: dict[str, Any] = {
            "op": "click" if action.do == "download" else action.do,
            "mode": mode,
            **(action.target.model_dump() if action.target else {}),
        }
        if action.row is not None:
            spec["row"] = {**action.row.model_dump(), "equals": _fill_in(action.row.equals, values)}
        if action.do == "fill":
            assert action.value is not None
            spec["value"] = _fill_in(action.value, values)
        if action.do == "download":
            assert action.save_as is not None
            if self.downloader is None:
                raise WebScriptError("web_download_not_supported")

            def click() -> None:
                self._perform(spec)

            data[action.save_as] = self.downloader(click, action.save_as)
            return
        answer = self._perform(spec)
        if action.do == "read_text":
            assert action.save_as is not None
            data[action.save_as] = answer.get("text", "")
        if action.do == "click":
            self._settle()
            self._check_origin()

    def _table_rows(self, action: WebAction) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_s
        while True:
            self._check_origin()
            try:
                return self._evaluate(
                    _READ_TABLE
                    % {
                        "css": json.dumps(action.table),
                        "header": json.dumps(action.header_table),
                        "limit": MAX_TABLE_ROWS,
                    }
                )
            except WebScriptError as error:
                if (
                    error.code not in {"web_table_missing", "web_table_header_missing"}
                    or time.monotonic() >= deadline
                ):
                    raise
                time.sleep(0.1)

    def _page_number(self, target: WebTarget) -> int:
        result = self._perform({"op": "read_text", "mode": "read", **target.model_dump()})
        match = re.fullmatch(r"\s*/?\s*(\d+)\s*", str(result.get("text", "")))
        if match is None:
            raise WebScriptError("web_pagination_invalid")
        return int(match[1])

    def _table_pages(self, action: WebAction, mode: ScriptMode) -> list[Any]:
        answer = self._table_rows(action)
        paging = action.pagination
        if paging is None:
            return list(answer["rows"])
        current, total = self._page_number(paging.current), self._page_number(paging.total)
        if current != 1 or total < 1:
            raise WebScriptError("web_pagination_not_at_start")
        if total > paging.max_pages:
            raise WebScriptError("web_pagination_limit_exceeded")
        rows = list(answer["rows"])

        def keys(batch: list[Any]) -> set[tuple[str, ...]]:
            if not paging.key_columns:
                return set()
            if any(column not in row for row in batch for column in paging.key_columns):
                raise WebScriptError("web_column_missing")
            result = {tuple(str(row[column]) for column in paging.key_columns) for row in batch}
            if len(result) != len(batch):
                raise WebScriptError("web_pagination_duplicate_keys")
            return result

        seen = keys(rows)
        if answer.get("truncated"):
            raise WebScriptError("web_table_limit_exceeded")
        while current < total:
            previous = answer["rows"]
            self._perform({"op": "click", "mode": mode, **paging.next.model_dump()})
            deadline = time.monotonic() + self.timeout_s
            candidate: list[Any] | None = None
            stable_since = time.monotonic()
            while True:
                self._check_origin()
                if self._page_number(paging.total) != total:
                    raise WebScriptError("web_pagination_changed")
                answer = self._table_rows(action)
                if answer["rows"] != candidate:
                    candidate = answer["rows"]
                    stable_since = time.monotonic()
                if (
                    self._page_number(paging.current) == current + 1
                    and answer["rows"]
                    and answer["rows"] != previous
                    and not (keys(answer["rows"]) & seen)
                    and time.monotonic() - stable_since >= self.settle_s
                ):
                    break
                if time.monotonic() >= deadline:
                    raise WebScriptError("web_pagination_did_not_advance")
                time.sleep(0.1)
            if answer.get("truncated") or len(rows) + len(answer["rows"]) > MAX_TABLE_ROWS:
                raise WebScriptError("web_table_limit_exceeded")
            rows.extend(answer["rows"])
            seen.update(keys(answer["rows"]))
            current += 1
        return rows

    def _perform(self, spec: dict[str, Any]) -> dict[str, Any]:
        pointer = getattr(self.page, "click_at", None)
        native = spec["op"] == "click" and callable(pointer)
        expression = _ACT % {"find": _FIND, "spec": json.dumps({**spec, "pointer": native})}
        deadline = time.monotonic() + self.timeout_s
        while True:
            if native:
                self._check_origin()
            try:
                answer = self._evaluate(expression)
                break
            except WebScriptError as error:
                if (
                    not native
                    or error.code
                    not in {
                        "web_target_missing",
                        "web_target_not_visible",
                        "web_target_disabled",
                        "web_target_obscured",
                    }
                    or time.monotonic() >= deadline
                ):
                    raise
                time.sleep(0.1)
        if native:
            assert callable(pointer)
            point = answer["pointer"]
            pointer(float(point["x"]), float(point["y"]))
        return answer

    def _evaluate(self, expression: str) -> dict[str, Any]:
        raw = self.page.evaluate(expression)
        try:
            answer = json.loads(raw) if isinstance(raw, str) else None
        except ValueError:
            answer = None
        if not isinstance(answer, dict):
            raise WebScriptError("web_page_unreadable")
        if "error" in answer:
            raise WebScriptError(str(answer["error"]))
        return answer

    def _settle(self) -> None:
        """A click may start a navigation; wait until the page has loaded."""
        time.sleep(self.settle_s)
        end = time.monotonic() + self.timeout_s
        while time.monotonic() < end:
            try:
                if self.page.evaluate("document.readyState") == "complete":
                    return
            except Exception:  # noqa: BLE001 - mid-navigation the page cannot answer
                pass
            time.sleep(0.1)
        raise WebScriptError("web_page_did_not_load")

    def _url(self) -> str:
        try:
            return str(self.page.evaluate("document.location.href") or "")
        except Exception:  # noqa: BLE001
            return ""

    def _check_origin(self) -> None:
        url = self._url()
        if url and not url.startswith("about:") and not origin_permitted(url, self.allowed):
            raise WebScriptError("web_origin_not_allowed")
