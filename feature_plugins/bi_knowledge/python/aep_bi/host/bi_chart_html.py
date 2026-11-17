"""The BI chart renderer, shared by the Dashboard tab and the chat's chart files.

`docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md` §2 and C2. `BI_CHART_JS`
draws an analysis result (`{columns, rows, truncated?}`) for a chart spec
(`{type: table|bar|line|scatter, x?, y?, series?}`, feed §5) as plain DOM/SVG:
text reaches the page through `textContent` and attributes only, never HTML.
`web_page.PAGE` embeds it where the Dashboard tab draws analyses, and `page`
embeds the same source in a self-contained HTML file the chat shows in its
sandboxed file viewer (`FILE_VIEW_CSP`): the data rides in a JSON block, and
nothing is fetched.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from typing import Any

BI_CHART_JS = r"""// Elements with text children only (never HTML).
function biEl(tag, cls, ...children) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  for (const child of children) {
    if (child == null || child === "") continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// The SVG namespace as the HTML parser gives it (the page holds no addresses).
const SVG_NS = (() => {
  const holder = document.createElement("template"); holder.innerHTML = "<svg></svg>";
  return holder.content.firstChild.namespaceURI;
})();

function biSvg(tag, attrs, label) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  if (label !== undefined) node.textContent = label;
  return node;
}

function biTableOf(table) {
  const head = biEl("tr", "", ...table.columns.map((c) => biEl("th", "", String(c))));
  const rows = table.rows.slice(0, 200).map((r) => biEl("tr", "", ...r.map((v) =>
    biEl("td", "", v === null || v === undefined ? "" : String(v)))));
  const box = biEl("div", "bi-scroll", biEl("table", "bi-table", biEl("thead", "", head),
    biEl("tbody", "", ...rows)));
  if (table.rows.length > 200 || table.truncated) {
    box.append(biEl("p", "bi-meta", "只顯示前 200 列（共 " + table.rows.length + " 列"
      + (table.truncated ? "以上" : "") + "）。"));
  }
  return box;
}

function biChart(table, chart) {
  // A table, or a plain SVG bar / line / scatter chart drawn from two columns.
  chart = chart || {type: "table"};
  const xi = table.columns.indexOf(chart.x), yi = table.columns.indexOf(chart.y);
  if (chart.type === "table" || xi < 0 || yi < 0) return biTableOf(table);
  const points = table.rows.map((r) => ({x: r[xi], y: Number(r[yi])}))
    .filter((p) => Number.isFinite(p.y)).slice(0, chart.type === "bar" ? 40 : 1000);
  const wrap = biEl("figure", "");
  if (!points.length) { wrap.append(biEl("p", "bi-meta", "結果沒有可以畫的數字。")); return wrap; }
  const max = Math.max(...points.map((p) => p.y), 0) || 1;
  const min = Math.min(...points.map((p) => p.y), 0);
  const label = chart.y + "（依 " + chart.x + "）";
  if (chart.type === "bar") {
    const rowH = 26, left = 180, width = 720, height = points.length * rowH + 30;
    const svg = biSvg("svg", {class: "bi-chart", viewBox: "0 0 " + width + " " + height,
      role: "img", "aria-label": label});
    points.forEach((p, i) => {
      const base = Math.min(min, 0);
      const w = Math.max(1, (p.y - base) / (max - base) * (width - left - 60));
      const y = 10 + i * rowH;
      svg.append(biSvg("text", {x: left - 8, y: y + 15, "text-anchor": "end"},
        String(p.x).slice(0, 24)));
      svg.append(biSvg("rect", {class: "bar", x: left, y: y + 3, width: w, height: rowH - 8}));
      svg.append(biSvg("text", {x: left + w + 6, y: y + 15}, String(p.y)));
    });
    wrap.append(svg);
  } else {
    const width = 720, height = 320, pad = 44;
    const numeric = points.every((p) => Number.isFinite(Number(p.x)));
    const xs = numeric ? points.map((p) => Number(p.x)) : points.map((_, i) => i);
    const x0 = Math.min(...xs), x1 = Math.max(...xs) === x0 ? x0 + 1 : Math.max(...xs);
    const sx = (v) => pad + (v - x0) / (x1 - x0) * (width - 2 * pad);
    const sy = (v) => height - pad - (v - min) / ((max - min) || 1) * (height - 2 * pad);
    const svg = biSvg("svg", {class: "bi-chart", viewBox: "0 0 " + width + " " + height,
      role: "img", "aria-label": label});
    svg.append(biSvg("line", {class: "axis", x1: pad, y1: height - pad, x2: width - pad,
      y2: height - pad}), biSvg("line", {class: "axis", x1: pad, y1: pad, x2: pad,
      y2: height - pad}));
    svg.append(biSvg("text", {x: pad - 6, y: pad, "text-anchor": "end"}, String(max)),
      biSvg("text", {x: pad - 6, y: height - pad, "text-anchor": "end"}, String(min)),
      biSvg("text", {x: pad, y: height - 14}, String(points[0].x).slice(0, 20)),
      biSvg("text", {x: width - pad, y: height - 14, "text-anchor": "end"},
        String(points[points.length - 1].x).slice(0, 20)));
    if (chart.type === "line") {
      svg.append(biSvg("polyline", {class: "line", points: points.map((p, i) =>
        sx(xs[i]) + "," + sy(p.y)).join(" ")}));
    }
    points.forEach((p, i) => svg.append(biSvg("circle", {class: "dot", cx: sx(xs[i]),
      cy: sy(p.y), r: chart.type === "line" ? 3 : 4}, undefined)));
    wrap.append(svg);
  }
  const more = biEl("details", "", biEl("summary", "", "看資料表"), biTableOf(table));
  wrap.append(biEl("figcaption", "bi-meta", label), more);
  return wrap;
}
"""

BI_CHART_CSS = r"""
.bi-chart { width: 100%; max-width: 760px; height: auto; display: block; margin: 8px 0; }
.bi-chart text { fill: var(--dim, #666); font-size: 12px; }
.bi-chart .bar, .bi-chart .dot { fill: var(--accent, #2f6db5); }
.bi-chart .line { fill: none; stroke: var(--accent, #2f6db5); stroke-width: 2; }
.bi-chart .axis { stroke: var(--dim, #666); stroke-width: 1; }"""

#: The card fields a card table shows, after name and type.
CARD_FIELDS = 8


def _shown(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        value = value["value"]
    if isinstance(value, list):
        return "、".join(str(v) for v in value)
    if value is None or isinstance(value, str | int | float):
        return value
    return json.dumps(value, ensure_ascii=False)


def cards_table(cards: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Cards as a table: name, type, then the fields they carry (first seen first)."""
    fields: list[str] = []
    for card in cards:
        for name in card.get("fields") or {}:
            if name not in fields and name != "name":
                fields.append(name)
    fields = fields[:CARD_FIELDS]
    rows = [
        [card.get("name"), card.get("entity_type"),
         *(_shown((card.get("fields") or {}).get(f)) for f in fields)]
        for card in cards
    ]  # fmt: skip
    return {"columns": ["name", "type", *fields], "rows": rows}


def _json_for_html(value: Any) -> str:
    """JSON safe inside a <script> element: no `</script>`, no line separators."""
    text = json.dumps(value, ensure_ascii=False, default=str)
    for raw, escaped in (
        ("&", "\\u0026"),
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        text = text.replace(raw, escaped)
    return text


def page(title: str, sections: Sequence[Mapping[str, Any]], about: str = "") -> str:
    """A self-contained HTML page: each section (`title`, `chart`, `columns`,
    `rows`, `truncated`, `note`) drawn by `BI_CHART_JS`; `about` is one line
    under the title (vault, version, parameters). The caller resolves each
    chart (`analyses.chart_for`); none is a table."""
    data = {
        "title": title,
        "about": about,
        "sections": [
            {
                "title": str(s.get("title") or ""),
                "note": str(s.get("note") or ""),
                "chart": s.get("chart") or {"type": "table"},
                "table": {
                    "columns": list(s.get("columns") or []),
                    "rows": list(s.get("rows") or []),
                    "truncated": bool(s.get("truncated")),
                },
            }  # fmt: skip
            for s in sections
        ],
    }
    return (
        TEMPLATE.replace("__TITLE__", html.escape(title))
        .replace("__CSS__", BI_CHART_CSS)
        .replace("__JS__", BI_CHART_JS)
        .replace("__DATA__", _json_for_html(data))
    )


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none';
  script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
body { font: 14px/1.5 system-ui, "Segoe UI", "Microsoft JhengHei", sans-serif; margin: 12px;
  color: #222; background: #fff; --dim: #666; --accent: #2f6db5; --line: #ddd; }
h1 { font-size: 16px; margin: 0 0 4px; }
h2 { font-size: 14px; margin: 16px 0 4px; }
.bi-meta { color: var(--dim); font-size: 12.5px; }
.bi-scroll { overflow-x: auto; max-width: 100%; }
.bi-table { border-collapse: collapse; }
.bi-table td, .bi-table th { vertical-align: top; text-align: left; padding: 3px 8px;
  border-bottom: 1px solid var(--line); }
.bi-table td { overflow-wrap: anywhere; min-width: 72px; }
__CSS__
</style>
</head>
<body>
<main id="bi-chat-chart"></main>
<script type="application/json" id="bi-chart-data">__DATA__</script>
<script>
__JS__
const BI_DATA = JSON.parse(document.getElementById("bi-chart-data").textContent);
const holder = document.getElementById("bi-chat-chart");
holder.append(biEl("h1", "", BI_DATA.title));
if (BI_DATA.about) holder.append(biEl("p", "bi-meta", BI_DATA.about));
for (const section of BI_DATA.sections) {
  const box = biEl("section", "bi-section");
  if (BI_DATA.sections.length > 1 || section.title !== BI_DATA.title) {
    box.append(biEl("h2", "", section.title));
  }
  if (section.note) box.append(biEl("p", "bi-meta", section.note));
  box.append(biChart(section.table, section.chart));
  holder.append(box);
}
</script>
</body>
</html>
"""
