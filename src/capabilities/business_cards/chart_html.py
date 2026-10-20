"""The interactive org chart: one self-contained HTML file.

Owner 2026-10-20 (「請幫我全做」): the same chart as the PNG, as a page with a
tree view, a grouped (box) view, a search that opens a person card, and a
toggle for people who left. It is general: nothing in it names a company;
the title comes from the data.

Everything is inline (CSS, script, data): no network, no CDN, so it works
offline, inside Agent Web's sandboxed frame and when opened from disk. The
data travels as JSON in a `<script type="application/json">` block with
`<`, `>`, `&` and the line separators escaped, and the script builds every
element with `textContent`, never `innerHTML`, so a contact field holding
`<script>` is shown as text (no XSS from contact data).

Built from the same rows as the PNG (`chart.render`): the grouping path,
the title order, the reporting lines (solid = evidence, dashed = inferred)
and the fields still to confirm.
"""

from __future__ import annotations

import html
import json
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from capabilities.business_cards import chart
from capabilities.business_cards.contracts import FIELD_LABELS, SOURCE_LABELS, STATUS_LABELS
from capabilities.business_cards.store import local_time


def _evidence(line: sqlite3.Row) -> str:
    text = chart.EVIDENCE_LABELS.get(line["evidence_kind"], line["evidence_kind"])
    return f"{text}（{line['evidence_ref']}）" if line["evidence_ref"] else text


def chart_data(
    company: str,
    people: Sequence[sqlite3.Row],
    lines: Sequence[sqlite3.Row],
    *,
    uncertain: Mapping[str, Sequence[str]],
    sources: Mapping[str, Sequence[tuple[str, str]]],
    show_left: bool,
    generated_at: str = "",
) -> dict[str, Any]:
    """What the page shows, as plain data (the page escapes nothing itself:
    it only ever sets text)."""
    paths = chart._paths(people)
    ids = {person["person_id"] for person in people}
    shown_lines = [line for line in lines if line["person_id"] in ids and line["manager_id"] in ids]
    names = {person["person_id"]: chart.display_name(person) for person in people}
    reports: dict[str, list[str]] = {}
    manager: dict[str, dict[str, Any]] = {}
    for line in shown_lines:
        reports.setdefault(line["manager_id"], []).append(line["person_id"])
        manager[line["person_id"]] = {
            "id": line["manager_id"],
            "name": names[line["manager_id"]],
            "evidence": _evidence(line),
            "inferred": bool(line["inferred"]),
        }
    listed = []
    for person in sorted(people, key=lambda p: (chart.rank_title(p["title"]), p["name"])):
        pid = person["person_id"]
        listed.append(
            {
                "id": pid,
                "name": str(person["name"]),
                "display": names[pid],
                "honorific": str(person["honorific"] or ""),
                "romanised": str(person["romanised_name"] or ""),
                "company": str(person["company"] or ""),
                "business_group": str(person["business_group"] or ""),
                "division": str(person["division"] or ""),
                "department": str(person["department"] or ""),
                "path": paths[pid],
                "title": str(person["title"] or ""),
                "phone": str(person["phone"] or ""),
                "ext": str(person["ext"] or ""),
                "mobile": str(person["mobile"] or ""),
                "fax": str(person["fax"] or ""),
                "email": str(person["email"] or ""),
                "left": person["status"] == "left",
                "status_label": STATUS_LABELS.get(person["status"], person["status"]),
                "left_at": str(person["left_at"] or ""),
                "needs": [FIELD_LABELS.get(name, name) for name in uncertain.get(pid, ())],
                "sources": [
                    {"label": SOURCE_LABELS.get(source, source), "date": local_time(date)}
                    for source, date in sources.get(pid, ())
                ],
                "manager": manager.get(pid),
                "reports": [
                    {
                        "id": member,
                        "name": names[member],
                        "evidence": manager[member]["evidence"],
                        "inferred": manager[member]["inferred"],
                    }
                    for member in reports.get(pid, ())
                ],
            }
        )
    evidenced = any(not line["inferred"] for line in shown_lines)
    return {
        "title": f"{company} 組織圖",
        "company": company,
        "generated_at": generated_at,
        "note": chart.NOTE,
        "no_lines_note": "" if evidenced else chart.NO_LINES_NOTE,
        "has_lines": bool(shown_lines),
        "show_left": show_left,
        "unlabelled": chart.UNLABELLED,
        "people": listed,
    }


def _json_for_html(data: Mapping[str, Any]) -> str:
    """JSON safe inside a `<script>` block: nothing in it can close the
    block or start markup."""
    text = json.dumps(data, ensure_ascii=False)
    for raw, escaped in (
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        (" ", "\\u2028"),
        (" ", "\\u2029"),
    ):
        text = text.replace(raw, escaped)
    return text


def page(data: Mapping[str, Any]) -> str:
    """The whole document."""
    return TEMPLATE.replace("__TITLE__", html.escape(str(data["title"]), quote=True)).replace(
        "__DATA__", _json_for_html(data)
    )


def render(
    path: Path,
    company: str,
    people: Sequence[sqlite3.Row],
    lines: Sequence[sqlite3.Row],
    *,
    uncertain: Mapping[str, Sequence[str]],
    sources: Mapping[str, Sequence[tuple[str, str]]],
    show_left: bool,
    generated_at: str = "",
) -> None:
    """Write the HTML file."""
    data = chart_data(
        company,
        people,
        lines,
        uncertain=uncertain,
        sources=sources,
        show_left=show_left,
        generated_at=generated_at,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page(data), encoding="utf-8")


#: The page. `__TITLE__` is HTML-escaped; `__DATA__` is `_json_for_html`.
#: The script only sets `textContent` and attributes it chose itself.
TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';
  img-src data:">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: light dark;
  --bg: #ffffff; --panel: #f6f7f9; --line: #d5dae1; --ink: #1c1f24; --dim: #5d6570;
  --accent: #2f6db5; --warn: #9a5b00; --warn-line: #c47f00; --left: #8d939b;
  --g1: #e4ecf7; --g2: #e7f1ea; --g3: #f5efe3; --card: #ffffff; --focus: #2f6db5;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15181c; --panel: #1d2127; --line: #39414b; --ink: #e6e9ee; --dim: #a3acb8;
    --accent: #7fb0ea; --warn: #f0c060; --warn-line: #e0a23a; --left: #7d848e;
    --g1: #1c2a3b; --g2: #1c2e24; --g3: #33291a; --card: #20252c; --focus: #7fb0ea;
  }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html, body { margin: 0; background: var(--bg); color: var(--ink); }
body { font: 15px/1.5 "Segoe UI", "Microsoft JhengHei", system-ui, sans-serif;
  overflow-x: hidden; }
header { padding: 12px 16px 4px; }
h1 { margin: 0 0 4px; font-size: 20px; overflow-wrap: anywhere; }
.note { margin: 4px 0; color: var(--dim); font-size: 13px; }
.warning { margin: 6px 0; padding: 8px 10px; border-left: 4px solid var(--warn-line);
  background: var(--panel); font-size: 13px; }
.controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  padding: 8px 16px; position: sticky; top: 0; background: var(--bg);
  border-bottom: 1px solid var(--line); z-index: 2; }
.tabs { display: flex; gap: 4px; }
button, .tab, input[type=search] { font: inherit; color: var(--ink); }
.tab, .person, .result, .close, summary { min-height: 44px; }
.tab { min-width: 44px; padding: 0 14px; border: 1px solid var(--line);
  background: var(--panel); border-radius: 8px; cursor: pointer; }
.tab[aria-selected=true] { background: var(--accent); color: #fff; border-color: var(--accent); }
.search { position: relative; flex: 1 1 220px; min-width: 0; }
input[type=search] { width: 100%; min-height: 44px; padding: 0 10px; border-radius: 8px;
  border: 1px solid var(--line); background: var(--card); }
.toggle { display: inline-flex; align-items: center; gap: 6px; min-height: 44px;
  cursor: pointer; }
.toggle input { width: 22px; height: 22px; }
.results { position: absolute; left: 0; right: 0; top: 48px; margin: 0; padding: 4px;
  list-style: none; background: var(--card); border: 1px solid var(--line);
  border-radius: 8px; max-height: 50vh; overflow-y: auto; z-index: 3;
  box-shadow: 0 4px 16px rgba(0,0,0,.18); }
.result { display: block; width: 100%; text-align: left; padding: 6px 10px;
  border: 0; background: transparent; border-radius: 6px; cursor: pointer; }
.result:hover, .result.active { background: var(--panel); }
.result small { display: block; color: var(--dim); overflow-wrap: anywhere; }
main { padding: 8px 16px 24px; }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
/* Tree view */
.tree ul { list-style: none; margin: 0; padding-left: 18px; border-left: 1px solid var(--line); }
.tree > ul { padding-left: 0; border-left: 0; }
.tree details > summary { display: flex; align-items: center; gap: 6px; cursor: pointer;
  font-weight: 600; overflow-wrap: anywhere; }
.tree .count { color: var(--dim); font-weight: 400; font-size: 13px; }
.tree h2 { font-size: 16px; margin: 16px 0 4px; }
.person { display: flex; flex-direction: column; justify-content: center; text-align: left;
  width: 100%; max-width: 100%; margin: 4px 0; padding: 4px 10px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--card); cursor: pointer; overflow-wrap: anywhere; }
.person small { color: var(--dim); }
.person.unsure { border: 2px solid var(--warn-line); }
.person.unsure .needs { color: var(--warn); }
.person.left { color: var(--left); background: var(--panel); }
.edge { margin-left: 4px; padding-left: 12px; border-left: 2px solid var(--accent); }
.edge.inferred { border-left-style: dashed; }
.edge-label { font-size: 12px; color: var(--dim); }
/* Grouped view */
.grouped { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-start; }
.box { flex: 1 1 260px; min-width: 0; max-width: 100%; padding: 8px; border-radius: 10px;
  border: 1px solid var(--line); }
.box > .box-title { font-weight: 600; margin: 0 0 6px; overflow-wrap: anywhere; }
.box .inner { display: flex; flex-wrap: wrap; gap: 10px; }
.d1 { background: var(--g1); } .d2 { background: var(--g2); } .d3 { background: var(--g3); }
.box .people { flex: 1 1 100%; }
/* Person card */
.card { position: fixed; right: 16px; top: 16px; bottom: 16px;
  width: min(420px, calc(100vw - 32px));
  overflow-y: auto; padding: 14px 16px; background: var(--card); color: var(--ink);
  border: 1px solid var(--line); border-radius: 12px; z-index: 5;
  box-shadow: 0 8px 28px rgba(0,0,0,.28); }
.card h2 { margin: 0 44px 2px 0; font-size: 19px; overflow-wrap: anywhere; }
.card dl { display: grid; grid-template-columns: 7.5em minmax(0, 1fr); gap: 4px 10px;
  margin: 10px 0; }
.card dt { color: var(--dim); }
.card dd { margin: 0; overflow-wrap: anywhere; }
.card .needs { color: var(--warn); font-weight: 600; }
.card ul { margin: 4px 0; padding-left: 18px; }
.close { position: absolute; right: 8px; top: 8px; width: 44px; border: 1px solid var(--line);
  background: var(--panel); border-radius: 8px; cursor: pointer; font-size: 18px; }
.empty { color: var(--dim); }
@media (max-width: 480px) {
  .card { left: 8px; right: 8px; top: 8px; bottom: 8px; width: auto; }
}
</style>
</head>
<body>
<header>
  <h1 id="title"></h1>
  <p class="note" id="note"></p>
  <p class="warning" id="no-lines" hidden></p>
</header>
<div class="controls">
  <div class="tabs" role="tablist" aria-label="檢視方式">
    <button class="tab" role="tab" id="tab-tree" aria-selected="true"
      aria-controls="tree">樹狀</button>
    <button class="tab" role="tab" id="tab-grouped" aria-selected="false"
      aria-controls="grouped" tabindex="-1">分組</button>
  </div>
  <div class="search">
    <input type="search" id="search" placeholder="搜尋姓名、英文名、職稱、部門、Email"
      aria-label="搜尋聯絡人" autocomplete="off" aria-controls="results" aria-expanded="false">
    <ul class="results" id="results" role="listbox" aria-label="搜尋結果" hidden></ul>
  </div>
  <label class="toggle"><input type="checkbox" id="show-left"> 顯示已離職</label>
</div>
<main>
  <section id="tree" class="tree" role="tabpanel" aria-labelledby="tab-tree"></section>
  <section id="grouped" class="grouped" role="tabpanel" aria-labelledby="tab-grouped"
    hidden></section>
</main>
<div class="card" id="card" role="dialog" aria-modal="false" aria-labelledby="card-name" hidden>
  <button class="close" id="card-close" type="button" aria-label="關閉">×</button>
  <div id="card-body"></div>
</div>
<script type="application/json" id="chart-data">__DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("chart-data").textContent);
const byId = new Map(DATA.people.map(p => [p.id, p]));
let showLeft = !!DATA.show_left;
let lastFocus = null;

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "className") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child == null || child === "") continue;
    node.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
}
const visible = () => DATA.people.filter(p => showLeft || !p.left);
function phoneText(p) {
  if (p.phone) return p.phone + (p.ext ? " #" + p.ext : "");
  return p.ext ? "分機 " + p.ext : "";
}
function personButton(p) {
  const second = p.left ? ("已離職 " + p.left_at).trim() : (p.title || p.romanised);
  const button = el("button", {className: "person" + (p.left ? " left" : "")
      + (p.needs.length ? " unsure" : ""), type: "button", "data-person": p.id},
    el("span", null, p.display + (p.needs.length ? "  ！" : "")),
    second ? el("small", null, second) : null,
    phoneText(p) ? el("small", null, phoneText(p)) : null,
    p.mobile ? el("small", null, "手機 " + p.mobile) : null,
    p.needs.length ? el("small", {className: "needs"}, "需確認：" + p.needs.join("、")) : null);
  button.addEventListener("click", () => openCard(p.id));
  return button;
}
// Company -> business group -> division -> department -> people.
function groupTree(people) {
  const root = {label: DATA.company, children: new Map(), people: []};
  for (const p of people) {
    let node = root;
    for (const label of p.path) {
      if (!node.children.has(label)) {
        node.children.set(label, {label, children: new Map(), people: []});
      }
      node = node.children.get(label);
    }
    node.people.push(p);
  }
  return root;
}
function countIn(node) {
  let n = node.people.length;
  for (const child of node.children.values()) n += countIn(child);
  return n;
}
function treeNode(node, open) {
  const details = el("details", open ? {open: ""} : null,
    el("summary", null, node.label,
      el("span", {className: "count"}, "（" + countIn(node) + " 人）")));
  const list = el("ul");
  for (const p of node.people) list.append(el("li", null, personButton(p)));
  for (const child of node.children.values()) list.append(el("li", null, treeNode(child, true)));
  details.append(list);
  return details;
}
function reportingNode(p, shown, seen) {
  const item = el("li", null, personButton(p));
  if (seen.has(p.id)) return item;
  seen.add(p.id);
  const kids = p.reports.filter(r => shown.has(r.id));
  if (kids.length) {
    const list = el("ul");
    for (const r of kids) {
      const edge = el("div", {className: "edge" + (r.inferred ? " inferred" : "")},
        el("div", {className: "edge-label"},
          (r.inferred ? "推論（虛線）：" : "有證據（實線）：") + r.evidence));
      const child = reportingNode(byId.get(r.id), shown, seen);
      edge.append(...child.childNodes);
      list.append(el("li", null, edge));
    }
    item.append(list);
  }
  return item;
}
function renderTree() {
  const target = document.getElementById("tree");
  target.replaceChildren();
  const people = visible();
  const shown = new Set(people.map(p => p.id));
  const roots = people.filter(p => p.reports.some(r => shown.has(r.id))
    && !(p.manager && shown.has(p.manager.id)));
  if (DATA.has_lines && roots.length) {
    target.append(el("h2", null, "回報關係（實線＝有證據，虛線＝推論）"));
    const list = el("ul", {className: "reporting"});
    const seen = new Set();
    for (const p of roots) list.append(reportingNode(p, shown, seen));
    target.append(list);
    target.append(el("h2", null, "分組（只表示分組，不是回報關係）"));
  }
  const list = el("ul");
  list.append(el("li", null, treeNode(groupTree(people), true)));
  target.append(list);
  if (!people.length) target.append(el("p", {className: "empty"}, "沒有可顯示的人。"));
}
function boxNode(node, depth) {
  const box = el("div", {className: "box d" + (((depth - 1) % 3) + 1)},
    el("div", {className: "box-title"}, node.label));
  const inner = el("div", {className: "inner"});
  if (node.people.length) {
    const people = el("div", {className: "people"});
    for (const p of node.people) people.append(personButton(p));
    inner.append(people);
  }
  for (const child of node.children.values()) inner.append(boxNode(child, depth + 1));
  box.append(inner);
  return box;
}
function renderGrouped() {
  const target = document.getElementById("grouped");
  target.replaceChildren();
  const root = groupTree(visible());
  for (const child of root.children.values()) target.append(boxNode(child, 1));
  if (!root.children.size) target.append(el("p", {className: "empty"}, "沒有可顯示的人。"));
}
function row(list, label, value, cls) {
  if (!value) return;
  list.append(el("dt", null, label), el("dd", cls ? {className: cls} : null, value));
}
function openCard(id) {
  const p = byId.get(id);
  if (!p) return;
  lastFocus = document.activeElement;
  const body = document.getElementById("card-body");
  const list = el("dl");
  row(list, "公司", p.company);
  row(list, "事業群", p.business_group);
  row(list, "處", p.division);
  row(list, "部門", p.department);
  row(list, "職稱", p.title);
  row(list, "英文名", p.romanised);
  row(list, "電話", phoneText(p));
  row(list, "手機", p.mobile);
  row(list, "傳真", p.fax);
  row(list, "Email", p.email);
  row(list, "狀態", p.left ? (p.status_label + " " + p.left_at).trim() : p.status_label);
  row(list, "需確認", p.needs.join("、"), "needs");
  const parts = [el("h2", {id: "card-name"}, p.display), list];
  if (p.sources.length) {
    parts.push(el("h3", null, "來源"));
    parts.push(el("ul", null, ...p.sources.map(
      s => el("li", null, s.label + (s.date ? "（" + s.date + "）" : "")))));
  }
  const lines = [];
  if (p.manager) lines.push(el("li", null, "向 " + p.manager.name + " 報告：" + p.manager.evidence
    + (p.manager.inferred ? "（推論）" : "（有證據）")));
  for (const r of p.reports) lines.push(el("li", null, r.name + " 向他報告：" + r.evidence
    + (r.inferred ? "（推論）" : "（有證據）")));
  parts.push(el("h3", null, "回報關係"));
  parts.push(lines.length ? el("ul", null, ...lines)
    : el("p", {className: "empty"}, "沒有記錄（分組不代表回報關係）"));
  body.replaceChildren(...parts);
  const card = document.getElementById("card");
  card.hidden = false;
  document.getElementById("card-close").focus();
}
function closeCard() {
  const card = document.getElementById("card");
  if (card.hidden) return;
  card.hidden = true;
  if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
}
// Search: name, romanised name, title, department (any level) or email.
const search = document.getElementById("search"), results = document.getElementById("results");
let active = -1;
function matches(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return visible().filter(p => [p.name, p.display, p.romanised, p.title, p.business_group,
    p.division, p.department, p.email].some(v => v && v.toLowerCase().includes(q))).slice(0, 30);
}
function showResults() {
  const found = matches(search.value);
  results.replaceChildren();
  active = -1;
  for (const p of found) {
    const where = [p.title, p.department || p.division, p.email].filter(Boolean).join(" · ");
    const button = el("button",
      {className: "result", type: "button", role: "option", "data-person": p.id},
      p.display, el("small", null, where));
    button.addEventListener("click", () => { hideResults(); openCard(p.id); });
    results.append(el("li", null, button));
  }
  if (search.value.trim() && !found.length) {
    results.append(el("li", {className: "empty"}, "找不到符合的人"));
  }
  results.hidden = !search.value.trim();
  search.setAttribute("aria-expanded", String(!results.hidden));
}
function hideResults() { results.hidden = true; search.setAttribute("aria-expanded", "false"); }
function moveActive(step) {
  const options = Array.from(results.querySelectorAll(".result"));
  if (!options.length) return;
  active = (active + step + options.length) % options.length;
  options.forEach((o, i) => o.classList.toggle("active", i === active));
  options[active].scrollIntoView({block: "nearest"});
}
search.addEventListener("input", showResults);
search.addEventListener("keydown", event => {
  if (event.key === "ArrowDown") { event.preventDefault(); moveActive(1); }
  else if (event.key === "ArrowUp") { event.preventDefault(); moveActive(-1); }
  else if (event.key === "Enter") {
    const options = results.querySelectorAll(".result");
    const chosen = options[active >= 0 ? active : 0];
    if (chosen) { event.preventDefault(); hideResults(); openCard(chosen.dataset.person); }
  } else if (event.key === "Escape") hideResults();
});
document.addEventListener("click", event => {
  if (!event.target.closest(".search")) hideResults();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeCard();
});
document.getElementById("card-close").addEventListener("click", closeCard);
// Views.
const tabs = [document.getElementById("tab-tree"), document.getElementById("tab-grouped")];
function select(tab) {
  for (const t of tabs) {
    const on = t === tab;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
  }
}
tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => select(tab));
  tab.addEventListener("keydown", event => {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      const next = tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      select(next); next.focus(); event.preventDefault();
    }
  });
});
const leftToggle = document.getElementById("show-left");
leftToggle.checked = showLeft;
leftToggle.addEventListener("change", () => {
  showLeft = leftToggle.checked; render(); if (!results.hidden) showResults();
});
function render() { renderTree(); renderGrouped(); }
document.getElementById("title").textContent = DATA.title;
document.getElementById("note").textContent = DATA.note
  + (DATA.generated_at ? "（" + DATA.generated_at + " 產生）" : "");
if (DATA.no_lines_note) {
  const warning = document.getElementById("no-lines");
  warning.textContent = DATA.no_lines_note; warning.hidden = false;
}
if (!DATA.people.some(p => p.left)) leftToggle.parentNode.hidden = true;
render();
</script>
</body>
</html>
"""
