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
from typing import Annotated, Any, Literal, Protocol, Self, cast
from urllib.parse import urlsplit

from pydantic import Field, JsonValue, model_validator
from pydantic_core import PydanticCustomError

from common.base import Contract, Symbol, Text
from common.trace import redact
from integrations.dom_names import DOM_NAME_JS

ScriptMode = Literal["read", "act"]
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
MAX_TABLE_ROWS = 2000

PaginationTargetField = Literal[
    "pagination.current", "pagination.total", "pagination.next", "pagination.controls"
]
_PAGINATION_TARGET_FIELDS = frozenset(
    ("pagination.current", "pagination.total", "pagination.next", "pagination.controls")
)


class WebScriptError(Exception):
    def __init__(self, code: str, *, target_field: str | None = None) -> None:
        self.code = code
        self.target_field: PaginationTargetField | None = (
            cast(PaginationTargetField, target_field)
            if target_field in _PAGINATION_TARGET_FIELDS
            else None
        )
        self.action_index: int | None = None
        self.action_kind: str | None = None
        super().__init__(code)


class WebTarget(Contract):
    """What to act on: a label as shown on the page, or a CSS selector."""

    label: Text | None = Field(
        default=None,
        description="The exact accessible name; not nearby text or an inferred caption",
    )
    css: Text | None = Field(
        default=None,
        description=(
            "Use an observed stable CSS locator matching exactly one visible element. "
            "A comma-separated CSS union matches every branch; it is not a fallback list."
        ),
    )
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
    current: WebTarget = Field(description="Current page number control; distinct from total")
    total: WebTarget = Field(
        description="Distinct total-page-count control; never reuse the current-page control"
    )
    max_pages: int = Field(default=200, ge=1, le=200, strict=True)
    key_columns: tuple[Text, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def distinct_page_controls(self) -> Self:
        same_css = (
            self.current.css is not None
            and self.total.css is not None
            and self.current.css.strip() == self.total.css.strip()
        )
        same_label = (
            self.current.label is not None
            and self.total.label is not None
            and self.current.kind == self.total.kind
            and " ".join(self.current.label.split())[:80] == " ".join(self.total.label.split())[:80]
        )
        if same_css or same_label:
            raise PydanticCustomError(
                "pagination_controls_must_differ",
                "pagination current and total must reference distinct controls",
            )
        return self


class WebAction(Contract):
    # `download` clicks a link or button and keeps the file it sends under
    # `save_as`; `read_record` reads a two-column table of field names and
    # values (a detail page's header). Both need a runner that supports them.
    do: Literal[
        "open",
        "fill",
        "click",
        "read_table",
        "read_text",
        "download",
        "read_record",
        "wait_for",
        "inspect_dom",
    ]
    url: Text | None = None
    target: WebTarget | None = None
    row: RowScope | None = None
    value: Text | None = Field(
        default=None,
        description=(
            "For fill, the text to enter (with {placeholders}). For wait_for, a regular expression "
            "matching the whole actual innerText/value, not the accessible name. For an icon-only "
            "visible target, .* accepts empty text and waits for presence; "
            "caption words may time out."
        ),
    )
    table: Text | None = None
    save_as: Symbol | None = None
    header_table: Text | None = None
    pagination: WebPagination | None = None

    scope: Text = Field(
        default="body",
        max_length=500,
        description="inspect_dom only: CSS selector matching exactly one scope element",
    )
    offset: int = Field(
        default=0,
        ge=0,
        le=100_000,
        strict=True,
        description="inspect_dom only: use next_offset for later elements of an unchanged DOM",
    )
    limit: int = Field(
        default=80,
        ge=1,
        le=200,
        strict=True,
        description="inspect_dom only: maximum returned elements",
    )

    @model_validator(mode="after")
    def complete(self) -> Self:
        needs = {
            "inspect_dom": self.save_as is not None,
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
  const caption = __DOM_NAME__;
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
    : [...scope.querySelectorAll(kinds[spec.kind])].filter(
      e => caption(e) === norm(spec.label).slice(0, 80));
  const found = matches.filter(e => e.getClientRects().length
    && getComputedStyle(e).visibility !== 'hidden');
  if (!found.length) return {error: 'web_target_missing'};
  if (found.length > 1) return {error: 'web_target_ambiguous'};
  return {element: found[0]};
}
""".replace("__DOM_NAME__", DOM_NAME_JS)

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


_PAGE_NUMBERS = r"""
(() => {
  const find = %(find)s;
  const current = find(%(current)s);
  if (current.error)
    return JSON.stringify({error: current.error, target_field: 'pagination.current'});
  const total = find(%(total)s);
  if (total.error)
    return JSON.stringify({error: total.error, target_field: 'pagination.total'});
  if (current.element === total.element)
    return JSON.stringify({error: 'pagination_controls_must_differ',
      target_field: 'pagination.controls'});
  const number = element => {
    const text = (element.innerText || element.value || '').trim();
    const match = /^\s*\/?\s*(\d+)\s*$/.exec(text);
    return match ? Number(match[1]) : null;
  };
  const here = number(current.element), count = number(total.element);
  if (!Number.isSafeInteger(here))
    return JSON.stringify({error: 'web_pagination_invalid', target_field: 'pagination.current'});
  if (!Number.isSafeInteger(count))
    return JSON.stringify({error: 'web_pagination_invalid', target_field: 'pagination.total'});
  // Only parsed page counts leave this expression, never raw field values.
  return JSON.stringify({current: here, total: count});
})()
"""


class DOMElement(Contract):
    index: int = Field(ge=0, le=100_000)
    parent: int | None = Field(default=None, ge=0, le=100_000)
    depth: int = Field(ge=0, le=100_000)
    tag: str = Field(max_length=80)
    path: str = Field(max_length=512)
    path_truncated: bool = False
    visible: bool = True
    disabled: bool = False
    text: str = Field(max_length=200)
    attributes: dict[
        Annotated[str, Field(max_length=32)], Annotated[str, Field(max_length=160)]
    ] = Field(default_factory=dict, max_length=16)


class DOMControl(Contract):
    tag: str = Field(max_length=80)
    kind: str = Field(default="", max_length=32)
    label: str = Field(default="", max_length=80)
    path: str = Field(default="", max_length=200)
    disabled: bool = False
    state: dict[
        Literal["expanded", "pressed", "placeholder", "type", "invalid"],
        Annotated[str, Field(max_length=80)] | bool,
    ] = Field(default_factory=dict, max_length=5)


class DOMTableHint(Contract):
    tag: str = Field(max_length=80)
    path: str = Field(default="", max_length=200)


class DOMOverview(Contract):
    controls: tuple[DOMControl, ...] = Field(default=(), max_length=80)
    controls_truncated: bool = False
    text: str = Field(default="", max_length=6000)
    text_truncated: bool = False
    tables: tuple[DOMTableHint, ...] = Field(default=(), max_length=20)
    tables_truncated: bool = False
    visited_nodes: int = Field(default=0, ge=0, le=100_000)
    time_limit_reached: bool = False
    scan_limit_reached: bool = False


class DOMInspection(Contract):
    scope: str = Field(max_length=500)
    offset: int = Field(ge=0, le=100_000)
    next_offset: int | None = Field(default=None, ge=0, le=100_000)
    scan_limit_reached: bool = False
    overview: DOMOverview | None = None
    time_limit_reached: bool = False
    elements: tuple[DOMElement, ...] = Field(max_length=200)


def _bounded_overview(overview: DOMOverview) -> DOMOverview:
    """Keep complete semantic JSON ahead of raw DOM within the tool's preview budget."""
    value = overview.model_dump(mode="json")
    while len(json.dumps(value, ensure_ascii=True)) > 9000:
        text = str(value["text"])
        controls = list(value["controls"])
        tables = list(value["tables"])
        if len(text) > 1000:
            value["text"] = text[: max(1000, len(text) - 512)]
            value["text_truncated"] = True
        elif len(controls) > 1:
            value["controls"] = controls[:-1]
            value["controls_truncated"] = True
        elif len(tables) > 1:
            value["tables"] = tables[:-1]
            value["tables_truncated"] = True
        elif text:
            value["text"] = text[:-512]
            value["text_truncated"] = True
        else:
            break
    return DOMOverview.model_validate(value)


_INSPECT_DOM = r"""
(() => {
  const spec = %(spec)s;
  const deadline = performance.now() + 1000;
  let visited = 0, timedOut = false;
  const budget = () => {
    if (visited >= 100000) return false;
    if (performance.now() >= deadline) { timedOut = true; return false; }
    visited++; return true;
  };
  let roots;
  try { roots = document.querySelectorAll(spec.scope); }
  catch (_) { return JSON.stringify({error: 'web_selector_invalid'}); }
  if (!roots.length) return JSON.stringify({error: 'web_scope_missing'});
  if (roots.length !== 1) return JSON.stringify({error: 'web_scope_ambiguous'});
  const root = roots[0];
  const excludedTags = ['SCRIPT', 'STYLE', 'NOSCRIPT', 'OPTION'];
  const fields = ['INPUT', 'TEXTAREA', 'SELECT'];
  const excluded = e => excludedTags.includes(e.tagName)
    || e.isContentEditable || (e.tagName === 'INPUT' && e.type === 'hidden');
  const privateAncestor = root.closest('script,style,noscript,' +
    '[contenteditable]:not([contenteditable=false])');
  if (excluded(root) || privateAncestor) return JSON.stringify({inspection: {
    scope: spec.scope, offset: spec.offset, next_offset: null,
    scan_limit_reached: false, elements: []}});
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
  const ownText = (element, limit) => {
    if (fields.includes(element.tagName)) return {text: '', truncated: false};
    let text = '', count = 0, truncated = false;
    for (let node = element.firstChild; node && count < 400; node = node.nextSibling) {
      if (!budget()) { truncated = true; break; }
      count++;
      if (node.nodeType !== Node.TEXT_NODE) continue;
      const value = node.textContent || '';
      const room = limit - text.length;
      text += value.slice(0, room);
      if (value.length > room) truncated = true;
      if (text.length >= limit) break;
    }
    return {text: norm(text), truncated};
  };
  const accessibleName = __DOM_NAME__;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, {
    acceptNode: e => excluded(e) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
  });
  const interactive = 'a[href],button,input,select,textarea,[role=button],[role=link],' +
    '[role=option],[role=combobox],[role=menuitem],[role=menuitemcheckbox],' +
    '[role=menuitemradio],[role=treeitem],[role=tab],[role=checkbox],[role=radio]';
  const info = new WeakMap(), out = [], buckets = [[], [], [], [], [], []], tables = [];
  const selector = (element, fallback) => {
    for (const attribute of ['data-automation-id', 'data-testid', 'data-test-id', 'id']) {
      const value = element.getAttribute(attribute);
      if (!value) continue;
      const selected = attribute === 'id' ? '#' + CSS.escape(value)
        : '[' + attribute + '=' + JSON.stringify(value) + ']';
      if (selected.length <= 200) return selected;
    }
    return fallback.length <= 200 ? fallback : '';
  };
  let e = root, index = 0, text = '', textTruncated = false;
  let controlsTruncated = false, tablesTruncated = false;
  while (e && index < 100000 && budget()) {
    const p = info.get(e.parentElement);
    const tag = e.tagName.toLowerCase().slice(0, 80);
    const own = e.id ? '#' + CSS.escape(e.id) : tag + ':nth-child(' +
      (e.parentElement ? Array.prototype.indexOf.call(e.parentElement.children, e) + 1 : 1) + ')';
    const fullPath = e.id || !p ? own : p.path + ' > ' + own;
    const path = fullPath.slice(0, 512);
    const path_truncated = fullPath.length > 512 || !!(p && p.path_truncated);
    const current = {index, parent: p ? p.index : null, depth: p ? p.depth + 1 : 0,
      path, path_truncated};
    info.set(e, current);
    const isVisible = visible(e);
    const ownValue = isVisible ? ownText(e, 3000) : {text: '', truncated: false};
    if (ownValue.text) {
      const value = (text ? '\n' : '') + ownValue.text;
      const room = 3000 - text.length;
      text += value.slice(0, room);
      textTruncated ||= value.length > room || ownValue.truncated;
    }
    const record = value => {
      const attrs = {};
      for (const name of ['id', 'class', 'role', 'aria-label', 'aria-expanded', 'aria-disabled',
                          'name', 'type', 'title', 'data-testid', 'data-test-id',
                          'data-automation-id', 'aria-labelledby', 'aria-describedby', 'for',
                          'aria-invalid']) {
        const attribute = e.getAttribute(name);
        if (attribute !== null) attrs[name] = norm(attribute).slice(0, 160);
      }
      return {...current, tag, visible: isVisible,
        disabled: !!e.disabled || e.getAttribute('aria-disabled') === 'true',
        text: value.slice(0, 200), attributes: attrs};
    };
    if (index >= spec.offset && out.length < spec.limit) out.push(record(ownValue.text));
    if (isVisible && e.matches(interactive)) {
      const role = e.getAttribute('role') || '';
      const navigation = e.closest('nav,[role=navigation],[role=menu],[role=menubar],' +
        '[role=tree],[role=tablist]') ||
        ['menuitem', 'menuitemcheckbox', 'menuitemradio', 'treeitem', 'tab'].includes(role);
      const field = fields.includes(e.tagName) || ['combobox', 'checkbox', 'radio'].includes(role);
      const toolbar = e.closest('[role=toolbar]');
      const link = tag === 'a' || role === 'link';
      const dataCell = e.closest('td,[role=cell],[role=gridcell]');
      const headerCell = e.closest('th,[role=rowheader],[role=columnheader]');
      const checkbox = role === 'checkbox' || (tag === 'input' && e.type === 'checkbox');
      // Data-row fields are record controls, not query fields. Keep TH filters useful,
      // while header select-all checkboxes stay with the table's record controls.
      const recordControl = dataCell || (headerCell && checkbox);
      const priority = navigation ? 0 : recordControl ? 5 : field ? 1 : toolbar ? 2 : link ? 4 : 3;
      if (buckets[priority].length < 80) {
        const label = accessibleName(e, budget);
        const state = {};
        const expanded = e.getAttribute('aria-expanded'), pressed = e.getAttribute('aria-pressed');
        if (['true', 'false'].includes(expanded)) state.expanded = expanded;
        if (['true', 'false', 'mixed'].includes(pressed)) state.pressed = pressed;
        const placeholder = e.getAttribute('placeholder'), type = e.getAttribute('type');
        if (fields.includes(e.tagName) && placeholder !== null)
          state.placeholder = norm(placeholder).slice(0, 80);
        if (type !== null) state.type = norm(type).slice(0, 32);
        if (e.getAttribute('aria-invalid') === 'true' || (e.validity && !e.validity.valid))
          state.invalid = true;
        buckets[priority].push({tag, kind: (role || type || '').slice(0, 32),
          label: norm(label).slice(0, 80), path: selector(e, path_truncated ? '' : path), state,
          disabled: !!e.disabled || e.getAttribute('aria-disabled') === 'true'});
      } else controlsTruncated = true;
    }
    if (isVisible && e.matches('table,[role=table],[role=grid]')) {
      // Only structure hints: table body values use the common 6000-character text budget.
      if (tables.length < 20) tables.push({tag, path: selector(e, path_truncated ? '' : path)});
      else tablesTruncated = true;
    }
    index++;
    e = walker.nextNode();
  }
  const more = index > spec.offset + out.length || !!e;
  const next = spec.offset + out.length;
  const scanLimit = visited >= 100000 && !!e;
  const candidates = buckets.flat(), controls = candidates.slice(0, 80);
  controlsTruncated ||= candidates.length > 80;
  return JSON.stringify({inspection: {scope: spec.scope, offset: spec.offset,
    next_offset: more && out.length && next < 100000 ? next : null,
    scan_limit_reached: scanLimit, time_limit_reached: timedOut, elements: out,
    overview: {text, text_truncated: textTruncated || !!e, controls,
      controls_truncated: controlsTruncated || !!e, tables,
      tables_truncated: tablesTruncated || !!e, visited_nodes: visited,
      time_limit_reached: timedOut, scan_limit_reached: scanLimit}}});
})()
""".replace("__DOM_NAME__", DOM_NAME_JS)

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
            for index, action in enumerate(checked.actions):
                try:
                    self._do(action, values, mode, data)
                except WebScriptError as error:
                    error.action_index = index
                    error.action_kind = action.do
                    raise
                except Exception as error:
                    failure = WebScriptError(str(getattr(error, "code", "web_action_failed")))
                    failure.action_index = index
                    failure.action_kind = action.do
                    raise failure from None
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
        if action.do != "open":
            self._check_origin()
        if action.do == "inspect_dom":
            assert action.save_as is not None
            data[action.save_as] = self.inspect(action.scope, action.offset, action.limit)
            return
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

    def inspect(
        self, scope: str = "body", offset: int = 0, limit: int = 80
    ) -> dict[str, JsonValue]:
        """Fixed read-only DOM observation; no caller-supplied executable code."""
        checked = WebAction(
            do="inspect_dom", scope=scope, offset=offset, limit=limit, save_as="dom"
        )
        if not origin_permitted(self._url(), self.allowed):
            raise WebScriptError("web_origin_not_allowed")
        answer = self._evaluate(
            _INSPECT_DOM
            % {
                "spec": json.dumps(
                    {"scope": checked.scope, "offset": checked.offset, "limit": checked.limit}
                )
            }
        )
        self._check_origin()
        observation, _ = redact(answer["inspection"])
        result = DOMInspection.model_validate(observation)
        if result.overview is not None:
            result = result.model_copy(update={"overview": _bounded_overview(result.overview)})
        return result.model_dump(mode="json")

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

    def _page_numbers(self, paging: WebPagination) -> tuple[int, int]:
        self._check_origin()
        answer = self._evaluate(
            _PAGE_NUMBERS
            % {
                "find": _FIND,
                "current": json.dumps(paging.current.model_dump()),
                "total": json.dumps(paging.total.model_dump()),
            }
        )
        self._check_origin()
        return int(answer["current"]), int(answer["total"])

    def _table_pages(self, action: WebAction, mode: ScriptMode) -> list[Any]:
        answer = self._table_rows(action)
        paging = action.pagination
        if paging is None:
            return list(answer["rows"])
        current, total = self._page_numbers(paging)
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
            try:
                self._perform({"op": "click", "mode": mode, **paging.next.model_dump()})
            except WebScriptError as error:
                error.target_field = "pagination.next"
                raise
            except Exception as error:
                raise WebScriptError(
                    str(getattr(error, "code", "web_action_failed")),
                    target_field="pagination.next",
                ) from None
            deadline = time.monotonic() + self.timeout_s
            candidate: list[Any] | None = None
            stable_since = time.monotonic()
            while True:
                self._check_origin()
                _, observed_total = self._page_numbers(paging)
                if observed_total != total:
                    raise WebScriptError("web_pagination_changed")
                answer = self._table_rows(action)
                if answer["rows"] != candidate:
                    candidate = answer["rows"]
                    stable_since = time.monotonic()
                observed_current, observed_total = self._page_numbers(paging)
                if observed_total != total:
                    raise WebScriptError("web_pagination_changed")
                if (
                    observed_current == current + 1
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
            field = answer.get("target_field")
            raise WebScriptError(
                str(answer["error"]), target_field=field if isinstance(field, str) else None
            )
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
