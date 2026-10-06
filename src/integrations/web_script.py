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


class WebAction(Contract):
    # `download` clicks a link or button and keeps the file it sends under
    # `save_as`; `read_record` reads a two-column table of field names and
    # values (a detail page's header). Both need a runner that supports them.
    do: Literal["open", "fill", "click", "read_table", "read_text", "download", "read_record"]
    url: Text | None = None
    target: WebTarget | None = None
    row: RowScope | None = None
    value: Text | None = None
    table: Text | None = None
    save_as: Symbol | None = None

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
        }
        if not needs[self.do]:
            raise ValueError(f"a {self.do} action is missing what it needs")
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
    any: 'a[href], button, input:not([type=hidden]), select, textarea, [role=button]'};
  const found = spec.css ? [...scope.querySelectorAll(spec.css)]
    : [...scope.querySelectorAll(kinds[spec.kind])].filter(e => caption(e) === spec.label);
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
  let heads = [...table.querySelectorAll('thead th')].map(th => norm(th.innerText));
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
  return JSON.stringify({ok: true, rows: out});
})()
"""


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def _fill_in(text: str, values: Mapping[str, JsonValue]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values or values[name] is None:
            raise WebScriptError("web_value_missing")
        return str(values[name])

    return _PLACEHOLDER.sub(replace, text)


class ScriptRunner:
    def __init__(
        self, page: ScriptPage, allowed_origins: tuple[str, ...], *, settle_s: float = 0.3,
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

    def _do(self, action: WebAction, values: Mapping[str, JsonValue], mode: ScriptMode,
            data: dict[str, JsonValue]) -> None:
        if action.do == "open":
            assert action.url is not None
            url = _fill_in(action.url, values)
            if _origin(url) not in self.allowed:
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
            answer = self._evaluate(_READ_TABLE % {"css": json.dumps(action.table),
                                                   "limit": MAX_TABLE_ROWS})
            data[action.save_as] = answer["rows"]
            return
        spec: dict[str, Any] = {
            "op": "click" if action.do == "download" else action.do, "mode": mode,
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
            expression = _ACT % {"find": _FIND, "spec": json.dumps(spec)}

            def click() -> None:
                self._evaluate(expression)

            data[action.save_as] = self.downloader(click, action.save_as)
            return
        answer = self._evaluate(_ACT % {"find": _FIND, "spec": json.dumps(spec)})
        if action.do == "read_text":
            assert action.save_as is not None
            data[action.save_as] = answer.get("text", "")
        if action.do == "click":
            self._settle()
            self._check_origin()

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
        if url and not url.startswith("about:") and _origin(url) not in self.allowed:
            raise WebScriptError("web_origin_not_allowed")
