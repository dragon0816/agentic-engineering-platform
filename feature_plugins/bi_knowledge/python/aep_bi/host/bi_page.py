"""The BI Knowledge page: its CSS, Knowledge pane and script.

Moved unchanged from `web_page.py` (feature mount points, proposal r3);
`aep_bi.feature` puts them back in `web_page.PAGE`'s feature slots.
"""

from __future__ import annotations

from aep_bi.host.bi_chart_html import BI_CHART_CSS, BI_CHART_JS

BI_CSS = r"""
.bi-pane { max-width: 1240px; min-width: 0; }
.bi-pane button.go { min-height: 44px; }
.bi-pane label.bi-label { display: block; font-size: 12px; color: var(--dim); margin: 0 0 4px; }
.bi-pane select, .bi-input { min-height: 44px; max-width: 100%; padding: 8px 10px;
  color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 8px;
  font: 14px "Segoe UI", system-ui, sans-serif; }
.bi-input { width: 100%; }
.bi-pane input[type="file"] { max-width: 100%; min-height: 44px; font: inherit; }
.bi-counts { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; min-height: 44px;
  color: var(--dim); font-size: 14px; }
.bi-counts strong { color: var(--ink); font-size: 20px; }
.bi-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.bi-btn { min-height: 44px; padding: 8px 14px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--bg); color: var(--ink); font: inherit; cursor: pointer;
  transition: border-color 150ms ease; }
.bi-btn:hover { border-color: var(--accent); }
.bi-btn:disabled, .bi-pane button.go:disabled { opacity: .5; cursor: not-allowed; }
.bi-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
  border: 1px solid var(--line); border-radius: 999px; font-size: 13px; background: var(--bg); }
.bi-chip b { font-size: 15px; font-variant-numeric: tabular-nums; }
.bi-chip.good { color: var(--good); border-color: var(--good); }
.bi-chip.warn { color: var(--warn); border-color: var(--warn); }
.bi-chip.bad { color: var(--bad); border-color: var(--bad); }
.bi-chip.accent { color: var(--accent); border-color: var(--accent); }
.bi-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 10px; }
.bi-badge { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px;
  font-weight: 600; border: 1px solid currentColor; white-space: nowrap; background: var(--bg); }
.bi-badge.type, .bi-badge.accent { color: var(--accent); }
.bi-badge.warn { color: var(--warn); }
.bi-badge.bad { color: var(--bad); }
.bi-badge.good { color: var(--good); }
.bi-badge.dim { color: var(--dim); }
.bi-meta { color: var(--dim); font-size: 12.5px; }
.bi-empty { color: var(--dim); padding: 18px 12px; text-align: center; }
.bi-scroll { overflow-x: auto; max-width: 100%; }
.bi-table td, .bi-table th { vertical-align: top; }
.bi-table td { overflow-wrap: anywhere; min-width: 72px; }
.bi-table tr.bi-flag-red td:first-child { box-shadow: inset 4px 0 0 var(--bad); }
.bi-table tr.bi-flag-warn td:first-child { box-shadow: inset 4px 0 0 var(--warn); }
.bi-table tr.bi-flag-red { background: color-mix(in srgb, var(--bad) 7%, transparent); }
.bi-table tr.bi-flag-warn { background: color-mix(in srgb, var(--warn) 8%, transparent); }
.bi-flag-badges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.bi-link { border: 0; background: transparent; color: var(--accent); text-decoration: underline;
  text-underline-offset: 2px; font: inherit; cursor: pointer; padding: 6px 2px; min-height: 32px;
  text-align: left; }
.bi-link:hover { color: var(--ink); }
.bi-summary { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }
.bi-stat { flex: 1 1 150px; min-width: 0; padding: 10px 14px; border: 1px solid var(--line);
  border-left: 4px solid var(--line); border-radius: 8px; background: var(--panel); }
.bi-stat b { display: block; font-size: 24px; line-height: 1.2;
  font-variant-numeric: tabular-nums; }
.bi-stat.red { border-left-color: var(--bad); } .bi-stat.red b { color: var(--bad); }
.bi-stat.warn { border-left-color: var(--warn); } .bi-stat.warn b { color: var(--warn); }
.bi-stat.dim { border-left-color: var(--dim); }
.bi-sec { overflow: visible; margin: 0 0 10px; }
.bi-sec > summary { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 10px;
  min-height: 48px; padding: 10px 14px; cursor: pointer; font-weight: 600; list-style: none; }
.bi-sec > summary::-webkit-details-marker { display: none; }
.bi-sec > summary::before { content: "\25B8"; color: var(--dim); transition: transform 150ms ease; }
.bi-sec[open] > summary::before { transform: rotate(90deg); }
.bi-sec > summary:focus-visible { outline: 3px solid var(--accent); outline-offset: -3px; }
.bi-sec-title { flex: 1 1 200px; min-width: 0; }
.bi-sec-body { padding: 0 14px 14px; min-width: 0; }
.bi-sec-note { color: var(--dim); font-size: 13px; margin: 0 0 8px; }
.bi-matrix { width: auto; min-width: 100%; }
.bi-matrix th, .bi-matrix td { text-align: center; padding: 6px 10px;
  font-variant-numeric: tabular-nums; }
.bi-matrix th:first-child, .bi-matrix td:first-child { text-align: left; position: sticky; left: 0;
  background: var(--panel); white-space: nowrap; }
.bi-matrix td.bi-zero { color: var(--dim); opacity: .45; }
.bi-matrix td.bi-hot { font-weight: 700; background: var(--accent-soft); }
.bi-funnel { display: grid; gap: 8px; }
.bi-funnel-row { display: grid; grid-template-columns: minmax(70px, 160px) minmax(0, 1fr) 3em;
  gap: 10px; align-items: center; }
.bi-funnel-label { overflow-wrap: anywhere; }
.bi-funnel-track { height: 26px; border: 1px solid var(--line); border-radius: 6px;
  background: var(--bg); overflow: hidden; }
.bi-funnel-bar { height: 100%; min-width: 3px; background: var(--accent); }
.bi-funnel-items { margin: -4px 0 4px; overflow-wrap: anywhere; }
.bi-funnel-n { font-weight: 700; font-variant-numeric: tabular-nums; text-align: right; }
.bi-filters { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: flex-end;
  margin: 0 0 10px; }
.bi-filters > div { min-width: 0; flex: 1 1 200px; }
.bi-filters > div:first-child { flex: 0 1 220px; }
.bi-browse { display: grid; grid-template-columns: minmax(0, 360px) minmax(0, 1fr); gap: 14px;
  align-items: start; }
.bi-cards { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; max-height: 72vh;
  overflow: auto; }
.bi-card-row { width: 100%; min-height: 56px; display: grid; gap: 3px; padding: 8px 12px;
  text-align: left; border: 1px solid var(--line); border-radius: 8px; background: var(--panel);
  color: var(--ink); font: inherit; cursor: pointer; transition: border-color 150ms ease; }
.bi-card-row:hover { border-color: var(--accent); }
.bi-card-row[aria-current="true"] { border-color: var(--accent);
  box-shadow: inset 3px 0 0 var(--accent); }
.bi-card-top { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.bi-card-name { font-weight: 600; overflow-wrap: anywhere; }
.bi-detail { min-width: 0; padding: 14px; border: 1px solid var(--line); border-radius: 10px;
  background: var(--panel); }
.bi-detail h3 { margin: 0 0 6px; font-size: 18px; outline: none; overflow-wrap: anywhere; }
.bi-detail h4 { margin: 16px 0 6px; font-size: 14px; }
.bi-fields { display: grid; gap: 8px; }
.bi-field { padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--bg); overflow-wrap: anywhere; min-width: 0; }
.bi-field-head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.bi-field-head strong { margin-right: auto; }
.bi-field-value { font-size: 15px; margin: 2px 0; white-space: pre-wrap; }
.bi-field-foot { display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: 4px 10px; }
.bi-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }
.bi-list li { padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--bg); overflow-wrap: anywhere; }
.bi-missing { color: var(--bad); font-weight: 600; }
.bi-edit { display: grid; gap: 6px; margin-top: 8px; padding-top: 8px;
  border-top: 1px dashed var(--line); }
.bi-edit textarea { min-height: 64px; font: 14px "Segoe UI", system-ui, sans-serif; }
.bi-stale { margin: 6px 0; padding: 8px 12px; border: 1px solid var(--warn); border-radius: 8px;
  background: color-mix(in srgb, var(--warn) 10%, transparent); }
.bi-err { color: var(--bad); font-size: 13px; }
/* A folder path has nowhere to break; it wraps instead of widening the page on a phone. */
#bi-notice, #bi-b-v-state, .bi-err { overflow-wrap: anywhere; }
.bi-err:empty, #bi-b-apply-status:empty { display: none; }
.bi-schema-note { flex: 1 1 100%; margin: 0; overflow-wrap: anywhere; }
.bi-schema-note:empty { display: none; }
.bi-empty-state { flex: 1 1 100%; padding: 8px 12px; border: 1px dashed var(--line);
  border-radius: 8px; overflow-wrap: anywhere; }
.bi-empty-state[hidden] { display: none; }
.bi-empty-state .bi-link { min-height: 0; padding: 0; margin-left: 4px; }
#kn-pane-bi.bi-none :is(.bi-top-pick, #bi-b-v-menu, #bi-b-v-state, .bi-views-row, #bi-back,
  #bi-view-build, #bi-view-dashboard, #bi-view-cards) { display: none; }
.bi-empty-state p { margin: 0 0 6px; }
.bi-errors { margin: 6px 0 0; padding-left: 18px; color: var(--bad); font-size: 13px; }
.bi-errors li { overflow-wrap: anywhere; margin: 2px 0; }
.bi-errors code { color: var(--ink); }
.bi-ok { color: var(--good); font-size: 13px; margin: 6px 0 0; }
.bi-files { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 6px; }
.bi-files a { display: inline-flex; align-items: center; min-height: 44px; color: var(--accent); }
.bi-none { padding: 24px 16px; text-align: center; border: 1px dashed var(--line);
  border-radius: 10px; }
.bi-none h3 { margin: 0 0 6px; font-size: 17px; }
.bi-none p { color: var(--dim); margin: 0 0 12px; }
.bi-none .bi-actions { justify-content: center; }
.bi-kept, .bi-kept td { background: color-mix(in srgb, var(--warn) 15%, transparent); }
.bi-row { margin: 0 0 6px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--bg); }
.bi-row-head { display: flex; align-items: center; gap: 2px; }
.bi-row-check { display: flex; align-items: center; justify-content: center; flex: none;
  min-width: 44px; min-height: 44px; cursor: pointer; }
.bi-row-check input { width: 20px; height: 20px; margin: 0; }
.bi-row-toggle { flex: 1; min-width: 0; min-height: 44px; display: flex; flex-wrap: wrap;
  align-items: center; gap: 4px 10px; padding: 6px 10px 6px 0; border: 0; background: transparent;
  color: var(--ink); font: inherit; text-align: left; cursor: pointer; }
.bi-row-toggle::after { content: "\25BE"; margin-left: auto; color: var(--dim); }
.bi-row-toggle[aria-expanded="true"]::after { content: "\25B4"; }
.bi-row-body { padding: 0 12px 12px; min-width: 0; }
.bi-arrow { color: var(--dim); padding: 0 4px; }
.bi-warnings { margin: 6px 0 0; padding-left: 18px; color: var(--warn); }
.bi-step { padding: 12px 14px; overflow: visible; }
.bi-step h3 { margin: 0 0 8px; font-size: 16px; }
.bi-step-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px 14px; align-items: end; }
.bi-warn { color: var(--warn); font-size: 13px; }
.bi-ai-sources { border: 0; margin: 8px 0; padding: 0; min-width: 0; display: flex;
  flex-wrap: wrap; gap: 4px 14px; }
.bi-ai-sources label { display: inline-flex; gap: 6px; align-items: center;
  overflow-wrap: anywhere; }
.bi-ai-panel { position: fixed; top: 0; right: 0; bottom: 0; z-index: 30;
  width: min(440px, 40vw); display: flex; flex-direction: column; gap: 6px; padding: 12px;
  background: var(--panel); border-left: 1px solid var(--line); box-shadow: -4px 0 16px #0002; }
.bi-ai-panel[hidden] { display: none; }
.bi-ai-panel p { margin: 0; }
#bi-card-peek { z-index: 31; }
#bi-card-peek .bi-split-pane { border: 0; padding: 0; overflow: visible; }
.bi-run { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin: 14px 0; }
#bi-b-bench-run { min-height: 52px; min-width: 200px; font-size: 18px; }
#bi-b-bench[hidden] ~ .bi-run { display: none; }
#bi-b-bench[hidden] ~ .bi-test-results #bi-b-bench-report { display: none; }
.bi-test-results { display: grid; gap: 12px; margin-bottom: 14px;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); align-items: start; }
#bi-b-test-dash { max-height: 76vh; overflow: auto; }
#bi-b-bq-split { height: auto; }
/* Sized by its rows: without the editor beside it (全部領域) nothing else gives it a height. */
#bi-b-bq-list { flex: 0 1 auto; max-height: 56vh; overflow: auto; }
#bi-b-bq-list tbody tr { cursor: pointer; }
#bi-b-bq-list tbody tr[aria-selected="true"] { box-shadow: inset 3px 0 0 var(--accent); }
#bi-b-bq-form textarea { width: 100%; }
.bi-ai-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.bi-ai-head h4 { margin: 0; }
.bi-ai-body { flex: 1; min-height: 0; overflow: auto; display: flex; flex-direction: column;
  gap: 6px; }
#bi-ai-log { margin: 0; }
#kn-pane-bi.bi-ai-open { margin-right: calc(min(440px, 40vw) + 12px); }
tr.bi-ai-from > td { background: var(--accent-soft, #2563eb22); }
@media (max-width: 760px) {
  .bi-ai-panel { top: auto; left: 0; width: auto; height: 66vh; border-left: 0;
    border-top: 1px solid var(--line); box-shadow: 0 -4px 16px #0002; }
  #kn-pane-bi.bi-ai-open { margin-right: 0; margin-bottom: 68vh; }
}
#bi-b-ver h5 { margin: 12px 0 4px; font-size: 13px; }
.bi-substeps ol { margin-top: 0; }
.bi-manage > summary { cursor: pointer; min-height: 44px; display: inline-flex;
  align-items: center; padding: 0 12px; }
.bi-manage > summary::before { content: "\25B8\A0"; color: var(--dim); }
.bi-manage[open] > summary::before { content: "\25BE\A0"; }
.bi-adv { margin-top: 12px; }
#bi-b-chips { align-items: center; }
.bi-row-menu > summary { cursor: pointer; color: var(--accent); white-space: nowrap;
  min-height: 32px; list-style: none; }
.bi-row-menu > summary::before { content: "\25B8\A0"; }
.bi-row-menu[open] > summary::before { content: "\25BE\A0"; }
.bi-detail-row td { padding: 0 4px; border: 0; }
.bi-detail-row pre { margin: 4px 0; }
.bi-menu > .bi-btn { display: block; margin: 4px 0; }
.bi-views-row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px;
  justify-content: space-between; }
/* BI_CHART_CSS */
.bi-code { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; margin: 6px 0;
  padding: 8px; border: 1px solid var(--line, #ddd); border-radius: 6px; }
.bi-substeps button { min-height: 44px; }
.bi-ver-pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px; margin: 6px 0; }
.bi-ver-pair > div { padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px;
  min-width: 0; overflow-wrap: anywhere; }
.bi-ver-pair > div.chosen { border-color: var(--accent);
  box-shadow: inset 0 0 0 1px var(--accent); }
.bi-ver-ask { display: flex; flex-wrap: wrap; gap: 8px; align-items: flex-end; margin-top: 6px; }
.bi-ver-ask .bi-input { flex: 1 1 200px; min-width: 0; }
.bi-confirm { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 6px;
  padding: 8px 10px; border: 1px solid var(--warn); border-radius: 8px; }
.bi-confirm > span { flex: 1 1 240px; min-width: 0; overflow-wrap: anywhere; }
.bi-share-progress { margin: 8px 0; padding-left: 20px; display: grid; gap: 4px; }
.bi-share-progress > li[data-state=done] { color: var(--good); }
.bi-share-progress > li[data-state=failed] { color: var(--bad); }
.bi-share-progress > li[data-state=waiting] { color: var(--dim); }
.bi-log { list-style: none; margin: 8px 0; padding: 0; display: grid; gap: 8px; }
.bi-log > li { padding: 8px 10px; border-radius: 8px; background: var(--panel);
  border: 1px solid var(--line); overflow-wrap: anywhere; min-width: 0; }
.bi-log > li.me { border-style: dashed; }
.bi-pre { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 16em; overflow-y: auto;
  margin: 4px 0; font-size: 12.5px; }
.bi-apply { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; margin-top: 10px; }
.bi-result { padding: 12px 14px; border-color: var(--good); overflow: visible; }
.bi-result.pending { border-color: var(--warn); }
.bi-pub-state { flex: 1 1 100%; margin: 0; display: flex; flex-wrap: wrap; gap: 6px;
  align-items: center; }
.bi-pub-state:empty { display: none; }
.bi-ro { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; margin: 0 0 10px;
  padding: 10px 14px; border: 1px solid var(--accent); border-left-width: 4px; border-radius: 8px;
  background: var(--accent-soft); color: var(--ink); overflow-wrap: anywhere; }
.bi-ro.stopped { border-color: var(--warn); background: color-mix(in srgb, var(--warn) 10%,
  transparent); }
.bi-pub-readers { border: 0; margin: 0; padding: 0; min-width: 0; }
.bi-pub-team { margin: 0 0 4px; font-weight: 600; }
.bi-check { display: flex; align-items: center; gap: 8px; min-height: 44px; cursor: pointer; }
.bi-check input { width: 20px; height: 20px; margin: 0; flex: none; }
.bi-pub-confirm { color: var(--warn); }
.bi-pub-what { margin: 10px 0; }
.bi-pub-what ul { margin: 4px 0 0; padding-left: 18px; }
.bi-pub-first { margin: 10px 0 10px; padding: 8px 12px; border: 1px solid var(--warn);
  border-radius: 8px; color: var(--ink); }
.bi-subs > summary { min-height: 44px; padding: 8px 14px; cursor: pointer; list-style: none; }
.bi-subs-list li { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.bi-sub-main { flex: 1 1 240px; min-width: 0; display: grid; gap: 2px; }
.bi-sub-name { font-weight: 600; overflow-wrap: anywhere; }
.bi-subs-list .bi-actions { flex: 0 1 auto; }
.bi-subs-more { margin: 10px 0 6px; }
@media (max-width: 900px) {
  .bi-browse { grid-template-columns: minmax(0, 1fr); }
  .bi-cards { max-height: none; }
}
/* A list and what it opens, side by side at one height, each scrolling on its own. */
/* What the whole page is about, first, and in sight while it scrolls. */
/* No box of its own: a sticky row sticks only inside its parent, and this must span the page. */
.bi-top { display: contents; }
#bi-b-v-state:not(:empty) { margin-bottom: 8px; }
#bi-b-v-state .bi-link { min-height: 0; padding: 0; }
#bi-b-ver { scroll-margin-top: calc(var(--bi-top-h, 0px) + var(--bi-steps-h, 0px) + 8px);
  /* Its tables fill in after a jump to it: they must not pull the page along. */
  overflow-anchor: none; }
/* The step bar sticks just under the top row instead of sliding half under it (acceptance
   F4); the row's height is measured into --bi-top-h. */
#bi-build-steps { position: sticky; top: var(--bi-top-h, 0px); z-index: 4; background: var(--bg); }
#bi-view-build .kp-stage-title {
  scroll-margin-top: calc(var(--bi-top-h, 0px) + var(--bi-steps-h, 0px) + 8px); }
#bi-b-v-path-suggest:empty { display: none; }
.bi-top-row { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap;
  align-items: flex-end; gap: 8px 10px; padding: 6px 0; background: var(--bg); }
.bi-top-pick { flex: 0 1 300px; min-width: 0; }
.bi-top-pick select { width: 100%; }
.bi-top-row > .bi-menu { margin-bottom: 8px; }
.bi-counts[hidden] { display: none; }
.bi-scope { display: grid; grid-template-columns: minmax(140px, 220px) auto; gap: 0 10px;
  align-items: end; margin-left: 6px; padding-left: 14px; border-left: 1px solid var(--line); }
.bi-scope[hidden] { display: none; }
.bi-scope .bi-label { grid-column: 1 / -1; }
.bi-scope select { width: 100%; }
.bi-scope .bi-scope-form { grid-column: 1 / -1; }
@media (max-width: 760px) {
  .bi-top-row { position: static; flex-direction: column; align-items: stretch; }
  .bi-top-pick { flex: 0 0 auto; }
  .bi-scope { grid-template-columns: minmax(0, 1fr) auto; margin-left: 0; padding-left: 0;
    border-left: 0; }
}
#bi-b-bq-split:has(> #bi-b-bq-pane[hidden]) { grid-template-columns: minmax(0, 1fr); }
.bi-scope-form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.bi-scope-form[hidden] { display: none; }
.bi-scope-form .bi-input { width: 210px; }
.bi-src-row { display: flex; flex-wrap: wrap; gap: 10px 14px; align-items: flex-end; }
.bi-src-row > div { flex: 1 1 200px; min-width: 0; }
.bi-src-row > div:has(.bi-file) { flex: 2 1 260px; }
.bi-src-row > div:last-child { flex: 0 0 auto; }
.bi-src-row > [hidden] { display: none; }
.bi-src-row > :last-child .go { min-width: 110px; }
.bi-src-row select { width: 100%; }
.bi-pane .bi-label { display: block; font-size: 12px; color: var(--dim); margin: 0 0 4px; }
.bi-md-bar { display: flex; flex-wrap: wrap; gap: 8px 10px; align-items: flex-end; }
.bi-md-bar > div:first-child { flex: 1 1 160px; min-width: 0; }
.bi-md-bar > div:first-child select { width: 100%; }
.bi-file-input { position: absolute; width: 1px; height: 1px; min-height: 0; opacity: 0;
  overflow: hidden; }
.bi-file { display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 10px 0 4px;
  background: var(--bg); border: 1px solid var(--line); border-radius: 8px; cursor: pointer;
  font: 14px "Segoe UI", system-ui, sans-serif; transition: border-color 150ms ease; }
.bi-file:hover { border-color: var(--accent); }
.bi-file-input:focus-visible + .bi-file { outline: 3px solid var(--accent); outline-offset: 2px; }
.bi-file-pick { flex: none; padding: 5px 12px; border-radius: 6px; background: var(--accent-soft);
  color: var(--ink); font-weight: 600; }
.bi-file-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--dim); }
.bi-md-view { margin-top: 10px; max-height: none; overflow-wrap: anywhere; line-height: 1.55; }
.bi-md-view > :first-child { margin-top: 0; }
.bi-md-view h1 { font-size: 18px; } .bi-md-view h2 { font-size: 16px; }
.bi-md-view h3, .bi-md-view h4, .bi-md-view h5, .bi-md-view h6 { font-size: 14px; }
.bi-md-view pre { padding: 10px; overflow-x: auto; background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; }
.bi-md-view .table-scroll { max-width: 100%; margin: 8px 0 14px; overflow-x: auto;
  border: 1px solid var(--line); border-radius: 8px; }
.bi-md-view table { width: 100%; border-collapse: collapse; font-size: 13px; }
.bi-md-view th, .bi-md-view td { padding: 6px 9px; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--line); overflow-wrap: normal; word-break: normal; }
.bi-md-view th { background: var(--accent-soft); white-space: nowrap; }
.bi-md-view tbody tr:last-child td { border-bottom: 0; }
.bi-md-view .bi-md-front th { width: 1%; }
.bi-md-view .bi-md-front td { overflow-wrap: anywhere; }
@media (max-width: 760px) {
  .bi-src-row { grid-template-columns: minmax(0, 1fr); }
  .bi-src-row > :last-child .go { width: 100%; }
}
.bi-src-split { display: grid; gap: 14px;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); }
.bi-src-split .bi-scroller { max-height: 50vh; overflow: auto; }
.bi-split-pane { min-width: 0; padding: 12px; border: 1px solid var(--line);
  border-radius: 10px; background: var(--panel); }
#bi-b-src-split { margin-top: 10px; }
.bi-split { margin-bottom: 14px; }
.bi-ver-changes { max-height: 50vh; overflow: auto; }
#bi-b-cands tbody tr { cursor: pointer; }
#bi-b-cands tbody tr[aria-selected="true"] { box-shadow: inset 3px 0 0 var(--accent); }
#bi-b-cands .bi-cand-value { display: -webkit-box; -webkit-box-orient: vertical;
  -webkit-line-clamp: 2; overflow: hidden; }
#bi-b-cands .bi-link { min-height: 0; padding: 0; border: 0; background: none; color: inherit;
  font: inherit; font-weight: 600; text-align: left; cursor: pointer; }
#bi-b-cands td { padding-top: 6px; padding-bottom: 6px; }
#bi-b-cands thead th { position: sticky; top: 0; z-index: 1; background: var(--panel); }
#bi-b-cands tbody tr { scroll-margin-top: 40px; }
.bi-state { display: inline-flex; align-items: center; gap: 4px; font-size: 13px;
  font-weight: 600; white-space: nowrap; }
.bi-state-icon { font-size: 16px; font-weight: 700; line-height: 1; }
.bi-state-accepted .bi-state-icon { color: var(--accent); }
.bi-state-rejected { color: var(--dim); }
.bi-state-rejected .bi-state-icon { color: var(--bad); }
#bi-b-cand-last:not(:empty)::before { content: "・"; }
.bi-prop-sides { width: 100%; table-layout: fixed; }
.bi-prop-sides td { white-space: pre-wrap; overflow-wrap: anywhere; }
.bi-prop-sides td > div { max-height: 220px; overflow: auto; }
.bi-prop-loss { font-weight: 600; }
#bi-b-cand h4 { margin-top: 0; }
#bi-b-cand .bi-cand-edit { display: flex; gap: 6px; margin-top: 6px; }
#bi-b-cand .bi-cand-edit .bi-input { flex: 1 1 auto; min-width: 0; }
#bi-b-cand-src { position: relative; max-height: 40vh; overflow: auto; margin: 0; padding: 10px;
  border: 1px solid var(--line); border-radius: 8px; white-space: pre-wrap;
  overflow-wrap: anywhere; font: inherit; }
#bi-b-cand-src mark { background: color-mix(in srgb, var(--warn) 35%, transparent);
  color: inherit; }
#bi-detail-abstract { margin-top: 8px; }
#bi-b-sources tbody tr { cursor: pointer; }
#bi-b-sources td { overflow-wrap: anywhere; word-break: normal; }
#bi-b-sources td:nth-child(5) { white-space: nowrap; }
#bi-b-sources .bi-btn { min-height: 30px; padding: 2px 8px; white-space: nowrap; }
#bi-b-sources tbody tr[aria-selected="true"] { box-shadow: inset 3px 0 0 var(--accent); }
@media (max-width: 900px) {
  .bi-src-split { grid-template-columns: minmax(0, 1fr); }
}
@media (min-width: 901px) {
  .bi-split { height: max(420px, 76vh); align-items: stretch;
    grid-template-rows: minmax(0, 1fr); }
  .bi-split-list { display: flex; flex-direction: column; min-height: 0; min-width: 0; }
  .bi-split-list > .bi-scroller { flex: 1 1 0; min-height: 0; max-height: none; overflow: auto;
    align-content: start; }
  .bi-split-pane { min-height: 0; overflow-y: auto; }
  #bi-b-review-split { grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr); }
}"""


BI_PANE_HTML = r"""
    <div id="kn-pane-bi" class="bi-pane" lang="zh-Hant" role="tabpanel" aria-label="BI 卡片"
         hidden>
        <aside id="bi-ai" class="bi-ai-panel" aria-labelledby="bi-ai-title" hidden>
          <div class="bi-ai-head">
            <h4 id="bi-ai-title"></h4>
            <button class="bi-btn" id="bi-ai-close" type="button">關閉</button></div>
          <div class="bi-ai-body" id="bi-ai-body">
          <p class="bi-meta" id="bi-ai-target"></p>
          <p class="bi-meta" id="bi-ai-sent"></p>
          <div id="bi-ai-new" class="bi-step-grid" hidden>
            <div><label class="bi-label" for="bi-ai-new-name">規則名稱（小寫英數字與 -）</label>
              <input id="bi-ai-new-name" class="bi-input" maxlength="60" spellcheck="false"></div>
            <div><label class="bi-label" for="bi-ai-new-folder">套用到</label>
              <select id="bi-ai-new-folder"></select></div>
          </div>
          <div id="bi-ai-schema" hidden>
            <label class="bi-label" for="bi-ai-goal">目標</label>
            <input id="bi-ai-goal" class="bi-input" maxlength="1000"
              placeholder="例如：追蹤機器人產業的技術、應用與客戶訊號">
            <details id="bi-ai-sources-box"><summary class="bi-label">附上的樣本來源</summary>
              <div class="bi-ai-sources" id="bi-ai-sources"></div></details>
          </div>
          <ol id="bi-ai-log" class="bi-log" role="log" aria-live="polite"
            aria-label="AI 對話紀錄"></ol>
          </div>
          <div class="mem-status" id="bi-ai-status" role="status" aria-live="polite" hidden></div>
          <label class="bi-label" for="bi-ai-msg" id="bi-ai-label"></label>
          <textarea id="bi-ai-msg" class="bi-input" rows="2" maxlength="4000"></textarea>
          <div class="bi-actions">
            <button class="go" id="bi-ai-send" type="button">送出</button></div>
        </aside>
      <div id="bi-b-vault" class="bi-top" role="region" aria-label="知識庫與工作領域">
        <div class="bi-top-row" id="bi-top-row">
          <div class="bi-top-pick"><label class="bi-label" for="bi-dataset">知識庫</label>
            <select id="bi-dataset"><option value="demo">demo</option></select></div>
          <button class="bi-btn" id="bi-b-v-new" type="button" data-mode="new"
            aria-expanded="false" aria-controls="bi-b-v-form">新增知識庫</button>
          <button class="bi-btn" id="bi-b-v-join" type="button" data-mode="join"
            aria-expanded="false" aria-controls="bi-b-v-form">加入</button>
          <details class="bi-manage bi-menu" id="bi-b-v-menu"><summary>管理</summary>
            <button class="bi-btn" id="bi-b-v-sync" type="button" hidden>立即同步</button>
          </details>
        <div class="bi-scope" id="bi-b-src-folder-box" hidden>
          <label class="bi-label" for="bi-b-src-folder">工作領域</label>
          <select id="bi-b-src-folder"></select>
          <button class="bi-btn" id="bi-b-home-new" type="button">新增領域</button>
          <form id="bi-b-home-form" class="bi-scope-form" hidden novalidate>
            <input id="bi-b-home-name" class="bi-input" maxlength="40" autocomplete="off"
              aria-label="領域名稱" placeholder="領域名稱，例如 Automotive">
            <input id="bi-b-home-folder" class="bi-input" maxlength="40" autocomplete="off"
              spellcheck="false" aria-label="資料夾名稱"
              placeholder="資料夾（中文名稱才要填）">
            <button class="go" id="bi-b-home-go" type="submit">建立</button>
            <button class="bi-btn" id="bi-b-home-cancel" type="button">取消</button>
          </form>
        </div>
        </div>
        <p class="bi-err" id="bi-b-home-err" role="alert" hidden></p>
        <p class="bi-warn" id="bi-b-scope-empty" role="status" hidden></p>
        <div id="bi-b-v-state" role="status" aria-live="polite"></div>
            <form id="bi-b-v-form" class="bi-step" hidden novalidate>
              <h4 id="bi-b-v-form-h"></h4>
              <div class="bi-step-grid">
                <div data-for="new"><label class="bi-label" for="bi-b-v-title">知識庫名稱</label>
                  <input id="bi-b-v-title" class="bi-input" maxlength="120"
                    placeholder="例如：市場訊號與產品對應"></div>
                <div data-for="new"><label class="bi-label" for="bi-b-v-id">
                  知識庫 id（資料夾名稱，之後不能改；中文名稱才要填）</label>
                  <input id="bi-b-v-id" class="bi-input" maxlength="40" spellcheck="false"
                    placeholder="例如：market-intel"></div>
                <div data-for="new convert"><label class="bi-label" for="bi-b-v-purpose">
                  目的（Agent 依這段話判斷什麼問題該查它）</label>
                  <input id="bi-b-v-purpose" class="bi-input" maxlength="1000"
                    placeholder="例如：看市場需求與訊號，對應我們的產品與業務策略"></div>
                <div data-for="new convert join"><label class="bi-label" for="bi-b-v-path"
                  id="bi-b-v-path-label">資料夾</label>
                  <input id="bi-b-v-path" class="bi-input" maxlength="1000" spellcheck="false"
                    placeholder="C:\Users\你\OneDrive - 公司\…">
                  <p class="bi-meta" id="bi-b-v-path-check" role="status" aria-live="polite"></p>
                  <div class="bi-actions" id="bi-b-v-path-suggest"></div></div>
                <details class="bi-adv" data-for="new"><summary>進階：Schema 版本</summary>
                  <label class="bi-label" for="bi-b-v-schema">Schema（預設最新版）</label>
                  <select id="bi-b-v-schema"></select></details>
                <div data-for="new convert join"><label class="bi-label" for="bi-b-v-author">
                  你的作者名稱（變更檔放在這個名稱的資料夾；留空用登入名稱）</label>
                  <input id="bi-b-v-author" class="bi-input" maxlength="40"></div>
                <div data-for="join"><label><input id="bi-b-v-resume" type="checkbox">
                  接續（我本人換電腦，沿用同一個作者名稱）</label></div>
              </div>
              <div class="bi-actions">
                <button class="go" id="bi-b-v-go" type="submit">建立</button>
                <button class="bi-btn" id="bi-b-v-cancel" type="button">取消</button></div>
              <div id="bi-b-v-err" role="alert"></div>
            </form>
      </div>
        <div class="bi-empty-state" id="bi-empty-state" role="note" hidden>
          <p class="bi-meta">還沒有知識庫：新增一個，或加入同事的。
            <button class="bi-link" id="bi-empty-demo" type="button">載入示範資料</button></p>
        </div>
      <div class="bi-ro" id="bi-ro" role="note" hidden>
        <strong id="bi-ro-title"></strong>
        <span class="bi-meta" id="bi-ro-note"></span>
      </div>
      <div class="mem-status" id="bi-status-bar" role="status" aria-live="polite" hidden></div>
      <div id="bi-notice" class="mem-notice" role="status" aria-live="polite"></div>
      <div class="bi-views-row">
      <aside id="bi-card-peek" class="bi-ai-panel" aria-label="卡片" hidden>
        <div class="bi-ai-head">
          <h4>卡片</h4>
          <button class="bi-btn" id="bi-card-peek-close" type="button">關閉</button></div>
        <div class="bi-ai-body" id="bi-card-peek-body"></div>
      </aside>
      <div class="mem-tabs" id="bi-views" role="tablist" aria-label="BI 卡片檢視">
        <button type="button" role="tab" data-bi-view="build"
          aria-selected="true">建立與匯入</button>
        <button type="button" role="tab" data-bi-view="dashboard"
          aria-selected="false">Dashboard</button>
        <button type="button" role="tab" data-bi-view="cards" aria-selected="false">卡片</button>
      </div>
          <div class="bi-counts" id="bi-counts" role="status" aria-live="polite">&hellip;</div>
      </div>
      <div class="bi-actions" id="bi-back" hidden>
        <button class="bi-btn" id="bi-back-go" type="button"></button></div>
      <div id="bi-view-dashboard" role="tabpanel" aria-label="Dashboard" hidden>
        <div class="bi-actions bi-atlas">
          <button class="bi-btn" id="bi-atlas-open" type="button">
            在 Atlas 開啟個人 Dashboard</button>
          <details id="bi-atlas-set"><summary>Atlas 位址</summary>
            <label class="bi-label" for="bi-atlas-url">Atlas 的網址（只存在這個瀏覽器）</label>
            <input id="bi-atlas-url" class="bi-input" type="text" maxlength="300"
              placeholder="127.0.0.1:8127">
            <button class="bi-btn" id="bi-atlas-save" type="button">儲存</button>
          </details>
          <span class="bi-meta" id="bi-atlas-state" role="status" aria-live="polite"></span>
        </div>
        <div class="card" id="bi-dom" hidden>
          <p><strong>這個資料集還有舊的領域設定</strong></p>
          <p class="bi-meta">領域設定已退役，先預覽再搬進 schema 與卡片。</p>
          <div class="bi-actions">
            <button class="bi-btn" id="bi-dom-migrate" type="button">
              預覽：搬進 schema 與卡片</button>
          </div>
          <div id="bi-dom-plan" aria-live="polite"></div>
        </div>
        <div class="bi-filters">
          <div id="bi-domain-box"><label class="bi-label" for="bi-domain">領域</label>
            <select id="bi-domain">
              <option value="robotics" selected>機器人 Robotics</option>
              <option value="wireless">無線通訊 Wireless</option>
              <option value="aidc">AIDC</option>
            </select></div>
          <div id="bi-sample-box"><label class="bi-check"><input type="checkbox" id="bi-sample">
            含 SAMPLE 示範卡</label></div>
        </div>
        <div id="bi-dash-block">
        <div id="bi-dash-params" class="bi-actions" hidden></div>
        <div class="mem-status" id="bi-status-dash" role="status" aria-live="polite" hidden></div>
        <div id="bi-dash-summary" class="bi-summary"></div>
        <div id="bi-dash-not-shown" class="bi-warn" hidden></div>
        <div id="bi-dash-sections"></div>
        </div>
      </div>
      <div id="bi-view-cards" role="tabpanel" aria-label="卡片" hidden>
        <div class="bi-filters">
          <div><label class="bi-label" for="bi-type">類型</label>
            <select id="bi-type"><option value="">全部類型</option></select></div>
          <div id="bi-card-domain-box"><label class="bi-label" for="bi-card-domain">領域</label>
            <select id="bi-card-domain"><option value="">全部領域</option></select></div>
          <div><label class="bi-label" for="bi-q">搜尋</label>
            <input id="bi-q" class="bi-input" type="search" autocomplete="off"
              placeholder="名稱或代碼"></div>
        </div>
        <details class="card bi-fts" id="bi-fts">
          <summary><strong>全文搜尋（卡片與原文）</strong>
            <span class="bi-meta" id="bi-fts-index"></span></summary>
          <form class="bi-step-grid" id="bi-fts-form" role="search">
            <div><label class="bi-label" for="bi-fts-q">
              找卡片的值與來源原文（Markdown）裡的字</label>
              <input id="bi-fts-q" class="bi-input" type="search" maxlength="200"
                autocomplete="off" placeholder="例如：800G 光模組"></div>
            <div><button class="go" id="bi-fts-go" type="submit">搜尋</button></div>
            <div><button class="bi-btn" id="bi-fts-rebuild" type="button">重建索引</button></div>
          </form>
          <div id="bi-fts-out" aria-live="polite"></div>
        </details>
        <div class="bi-browse bi-split" id="bi-card-split">
          <div class="bi-split-list" id="bi-card-list">
            <div class="mem-status" id="bi-status-cards" role="status" aria-live="polite"
                 hidden></div>
            <p class="bi-meta" id="bi-card-count"></p>
            <ul id="bi-cards" class="bi-cards bi-scroller" aria-label="卡片清單"></ul>
          </div>
          <div class="bi-detail bi-split-pane" id="bi-detail">
            <div class="mem-status" id="bi-status-detail" role="status" aria-live="polite"
                 hidden></div>
            <div id="bi-detail-body"><p class="bi-empty">選一張卡片，查看欄位、來源、關聯與歷史。
              </p></div>
          </div>
        </div>
      </div>
      <div id="bi-view-build" role="tabpanel" aria-label="建立與匯入">
        <div id="bi-build-steps">
        <nav id="bi-stepper" class="kp-stepper" aria-label="建立與匯入步驟">
          <ol>
            <li><button type="button" data-stage="source"><span class="kp-step-n">1</span>
              <span><strong>輸入與轉檔</strong></span></button></li>
            <li><button type="button" data-stage="ingest"><span class="kp-step-n">2</span>
              <span><strong>Schema 與 Ingest</strong></span></button></li>
            <li><button type="button" data-stage="test"><span class="kp-step-n">3</span>
              <span><strong>測試</strong></span></button></li>
          </ol>
        </nav>
        <nav id="bi-substeps" class="kp-stepper bi-substeps" aria-label="步驟 2 的細項" hidden>
          <ol>
            <li><button type="button" data-stage="schema"><span class="kp-step-n">a</span>
              <span><strong>類別與規則</strong></span></button></li>
            <li><button type="button" data-stage="method"><span class="kp-step-n">b</span>
              <span><strong>Ingest</strong></span></button></li>
            <li><button type="button" data-stage="review"><span class="kp-step-n">c</span>
              <span><strong>審核</strong></span></button></li>
            <li hidden><button type="button" data-stage="commit"></button></li>
            <li hidden><button type="button" data-stage="result"></button></li>
          </ol>
        </nav>
        </div>
        <div class="mem-status" id="bi-status-build" role="status" aria-live="polite" hidden></div>
        <section class="kp-stage card bi-step" data-stage="source" aria-labelledby="bi-b-source">
          <h3 class="kp-stage-title" id="bi-b-source" tabindex="-1">步驟 1／3・輸入與轉檔</h3>
          <div class="bi-actions" id="bi-b-ro-links" hidden>
            <button class="bi-btn" id="bi-b-ro-cards" type="button">看卡片</button>
            <button class="bi-btn" id="bi-b-ro-dash" type="button">看 Dashboard</button>
          </div>
          <div class="bi-src-row" id="bi-b-src-input">
            <div><label class="bi-label" for="bi-b-class">機密等級</label>
              <select id="bi-b-class">
                <option value="INTERNAL">INTERNAL（預設）</option>
                <option value="UNCLASSIFIED">UNCLASSIFIED</option>
                <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                <option value="RESTRICTED">RESTRICTED</option></select></div>
            <div><span class="bi-label" id="bi-b-file-h">來源檔</span>
              <input id="bi-b-file" class="bi-file-input" type="file" multiple
                aria-labelledby="bi-b-file-h"
                accept=".csv,.tsv,.xlsx,.xlsm,.pdf,.docx,.pptx,.md,.markdown,.txt,text/csv,text/markdown,text/plain">
              <label class="bi-file" for="bi-b-file"><span class="bi-file-pick">選檔</span>
                <span id="bi-b-file-name" class="bi-file-name">還沒有選檔</span></label></div>
            <div><button class="go" id="bi-b-upload" type="button" disabled>轉檔</button>
              <div class="mem-status bi-upload-status" id="bi-b-upload-status" role="status"
                aria-live="polite" hidden></div></div>
          </div>
          <p class="bi-warn" id="bi-b-scope-need" hidden>
            先在上面選工作領域，才能加入檔案或 Ingest。</p>
          <p class="bi-warn" id="bi-b-src-cloud" role="status" hidden></p>
          <div class="bi-step" id="bi-b-src-withdraw" role="region" aria-label="撤回來源"
            hidden></div>
          <div class="bi-split bi-src-split" id="bi-b-src-split">
            <div class="bi-split-list">
              <div class="bi-filters">
                <div><label class="bi-label" for="bi-b-src-q">搜尋來源</label>
                  <input id="bi-b-src-q" class="bi-input" type="search" autocomplete="off"
                    placeholder="檔名"></div>
                <div class="bi-meta" id="bi-b-src-count" role="status"></div>
              </div>
              <div class="bi-scroll bi-scroller"><table class="bi-table bi-stack" id="bi-b-sources">
                <thead><tr><th><label class="bi-meta"><input type="checkbox"
                  id="bi-b-src-all" aria-label="全選顯示的來源"> 使用</label></th><th>來源</th>
                  <th>格式</th><th>Markdown</th>
                  <th>機密等級</th><th>共用資料夾</th></tr></thead>
                <tbody></tbody></table></div>
            </div>
            <div class="bi-split-pane" id="bi-b-src-pane" aria-live="polite">
              <p class="bi-empty" id="bi-b-md-empty">選一份來源，看轉檔結果。</p>
              <div class="mem-status" id="bi-b-md-status" role="status" hidden></div>
          <div id="bi-b-md" role="region" aria-labelledby="bi-b-md-h" hidden>
            <h4 id="bi-b-md-h"></h4>
            <p class="bi-meta" id="bi-b-md-info"></p>
            <div class="bi-md-bar">
              <div><label class="bi-label" for="bi-b-md-rev">看哪一版</label>
                <select id="bi-b-md-rev"></select></div>
              <div><label class="bi-label" for="bi-b-md-mode">顯示</label>
                <select id="bi-b-md-mode">
                  <option value="view">預覽</option>
                  <option value="edit">編輯</option></select></div>
              <div><button class="bi-btn" id="bi-b-md-close" type="button">關閉</button></div>
            </div>
            <div id="bi-b-md-view" class="kp-markdown bi-md-view" tabindex="0"
              role="region" aria-label="Markdown 預覽"></div>
            <div id="bi-b-md-edit" hidden>
              <label class="bi-label" for="bi-b-md-text">
                Markdown（修改後存成新的版次；原始檔不會改）</label>
              <textarea id="bi-b-md-text" class="bi-input" rows="16" spellcheck="false"></textarea>
              <div class="bi-step-grid">
                <div><label class="bi-label" for="bi-b-md-note">這一版的說明</label>
                  <input id="bi-b-md-note" class="bi-input" maxlength="300"
                    placeholder="例如：修正表格欄位名稱"></div>
                <div><button class="go" id="bi-b-md-save" type="button">存成新版次</button></div>
              </div>
            </div>
            <div id="bi-b-md-msg" role="status" aria-live="polite"></div>
          </div>
            </div>
          </div>
          <details class="bi-manage bi-adv" id="bi-b-adv-source">
            <summary>進階：知識庫與匯入</summary>
            <p class="bi-meta" id="bi-b-target"></p>
            <div id="bi-b-v-info"></div>
              <button class="bi-btn" id="bi-b-v-convert" type="button" data-mode="convert"
                aria-expanded="false" aria-controls="bi-b-v-form">把這個資料集轉成 vault</button>
            <div id="bi-b-askable" aria-live="polite"></div>
          <details class="bi-manage" id="bi-b-pages">
            <summary>匯入卡片頁（Obsidian）</summary>
            <p class="bi-meta">選一個資料夾：讀每頁開頭的欄位，對應到 schema，就像匯入
              CSV；不用模型，也不會猜。先預覽，看不懂的欄位和值都會列出來，確認後每頁都
              保留成來源，當作卡片的證據。</p>
            <input id="bi-b-pages-dir" type="file" webkitdirectory multiple
              aria-label="選擇卡片頁資料夾">
            <label><input id="bi-b-pages-samples" type="checkbox"> 全部標成範例資料</label>
            <div id="bi-b-pages-plan" role="region" aria-live="polite"
              aria-label="卡片頁匯入預覽"></div>
          </details>
          </details>
          <div class="bi-actions"><button class="go" type="button" data-bi-next="schema"
            id="bi-b-next1" disabled>下一步：Schema 與 Ingest</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="schema" aria-labelledby="bi-b-schema"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-schema" tabindex="-1">步驟 2／3・類別與規則</h3>
          <p class="bi-meta" id="bi-b-schema-now"></p>
          <div class="bi-step-grid" id="bi-b-sg-bar">
            <div><label class="bi-label" for="bi-b-sg-scope">看哪些來源</label>
              <select id="bi-b-sg-scope">
                <option value="new">這個領域還沒 ingest 的來源</option>
                <option value="picked">步驟 1 選的來源</option></select></div>
            <div><button class="go" id="bi-b-sg-run" type="button">建議 schema</button></div>
            <div><button class="bi-btn" id="bi-b-sa-open" type="button">
              和 AI 調整 schema</button></div>
          </div>
          <div class="mem-status" id="bi-b-sg-status" role="status" aria-live="polite"
            hidden></div>
          <div id="bi-b-sg-box" hidden>
            <p class="bi-meta" id="bi-b-sg-sum"></p>
            <div class="bi-scroll"><table class="bi-table bi-stack" id="bi-b-sg-table"
              aria-label="schema 建議">
              <thead><tr><th>建議</th><th>為什麼</th><th>原文</th><th>動作</th></tr></thead>
              <tbody></tbody></table></div></div>
          <div id="bi-b-draft-main" role="region" aria-labelledby="bi-b-draft-h" hidden>
            <h4 id="bi-b-draft-h">Schema 草稿</h4>
            <div class="bi-step-grid">
              <div><label class="bi-label" for="bi-b-draft-pick">草稿</label>
                <select id="bi-b-draft-pick"></select></div>
              <div><button class="go" id="bi-b-draft-use" type="button">
                套用到資料集</button></div>
            </div>
            <div class="bi-scroll"><table class="bi-table bi-stack" id="bi-b-draft-table"
              aria-label="草稿的改動">
              <thead><tr><th>類型</th><th>欄位</th><th>改動</th><th>說明</th></tr></thead>
              <tbody></tbody></table></div>
            <p class="bi-meta" id="bi-b-draft-sum"></p>
          </div>
          <div id="bi-b-upgrade" hidden></div>
          <div class="bi-ai" id="bi-b-skills" role="region" aria-labelledby="bi-b-skills-h"
            hidden>
            <h4 id="bi-b-skills-h">判讀規則（skills）</h4>
            <div id="bi-b-sk-list"></div>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-sk-new" type="button">和 AI 新增規則</button></div>
            <div id="bi-b-tools">
              <h5>資料處理程式</h5>
              <div id="bi-b-tl-list"></div>
            </div>
          <details class="bi-manage bi-adv" id="bi-b-adv-skills">
            <summary>進階：規則與程式</summary>
            <div class="bi-step" id="bi-b-profile">
              <h5>應用的 profile</h5>
              <p class="bi-meta">每個應用用到哪些卡片類型和欄位。AI 判讀這個應用的來源時，
                只問這裡列的；沒有列的值仍會留下，並在審核時標出來。
                存成新版本後，commit 並 push 大家才會用到。</p>
              <label class="bi-label" for="bi-b-pf-home">應用或資料庫項目</label>
              <select id="bi-b-pf-home"></select>
              <div id="bi-b-pf-view"></div>
              <div id="bi-b-pf-proposals"></div>
              <label class="bi-label" for="bi-b-pf-json">Profile 內容（JSON）</label>
              <textarea id="bi-b-pf-json" class="bi-input" rows="10" spellcheck="false"></textarea>
              <p class="bi-meta">格式：{"types": {"類型": {"category": "這個類型在這裡的意思",
                "fields": {"欄位": {"use": "required 或 optional", "note": "說明"}}}},
                "proposals": [{"type": "類型", "field": "新欄位", "definition": {"kind": "str",
                "class": "sourced", "label": "名稱"}, "reason": "為什麼需要"}]}。
                schema 沒有的欄位只能放在 proposals。</p>
              <div class="bi-actions">
                <button class="bi-btn" id="bi-b-pf-save" type="button">存成新版本</button></div>
            </div>
            <div class="bi-step" id="bi-b-tool-new">
              <p class="bi-meta">把原始來源轉成 CSV 或 Markdown，產出會成為新的來源，
                再走一樣的預覽和審核，不會直接寫卡片。每個新版本第一次在這台電腦執行前，
                要由人看過程式碼並核准。執行時擋網路、子程序和輸出資料夾以外的寫入；
                這是防止失誤，不是防範蓄意攻擊的邊界。</p>
              <label class="bi-label" for="bi-b-tl-name">新增版本：應用/名稱</label>
              <input id="bi-b-tl-name" class="bi-input" spellcheck="false"
                placeholder="aidc/normalize-report 或 library/products/normalize">
              <label class="bi-label" for="bi-b-tl-code">
                Python 程式（讀 INPUT，寫到 OUTPUT）</label>
              <textarea id="bi-b-tl-code" class="bi-input" rows="6" spellcheck="false"></textarea>
              <div class="bi-actions">
                <button class="bi-btn" id="bi-b-tl-save" type="button">存成新版本</button></div>
            </div>
            <div class="bi-step" id="bi-b-rerun">
              <h5>改完規則後重跑</h5>
              <p class="bi-meta">用現在的規則重讀來源，只列出和卡片不同的值；你確認的才會寫入。
                模型這次沒讀到的值不會被清掉。</p>
              <label class="bi-label" for="bi-b-rr-app">應用資料夾</label>
              <select id="bi-b-rr-app"></select>
              <div id="bi-b-rr-sources"></div>
              <div class="bi-actions">
                <button class="bi-btn" id="bi-b-rr-count" type="button">看要重跑幾份</button></div>
              <div id="bi-b-rr-out"></div>
            </div>
            <form id="bi-b-sk-form" class="bi-step" hidden>
              <div class="bi-step-grid">
                <div><label class="bi-label" for="bi-b-sk-name">名稱（小寫英數字與 -）</label>
                  <input id="bi-b-sk-name" class="bi-input" maxlength="60" spellcheck="false"
                    placeholder="例如：aidc-extract"></div>
                <div><label class="bi-label" for="bi-b-sk-role">種類</label>
                  <select id="bi-b-sk-role"><option value="extract">擷取</option>
                    <option value="classify">分類</option></select></div>
                <div><label class="bi-label" for="bi-b-sk-applies">
                  套用到的資料夾（逗號分隔；留空＝所有來源）</label>
                  <input id="bi-b-sk-applies" class="bi-input" spellcheck="false"
                    placeholder="applications/aidc/sources"></div>
                <div><label class="bi-label" for="bi-b-sk-types">
                  只產生這些卡片類型（逗號分隔；留空＝用領域 profile 的類型，
                  沒有 profile 就用預設類型）</label>
                  <input id="bi-b-sk-types" class="bi-input" spellcheck="false"></div>
              </div>
              <p class="bi-meta" id="bi-b-sk-runtypes" role="status"></p>
              <p class="bi-meta" id="bi-b-sk-folders"></p>
              <label class="bi-label" for="bi-b-sk-body">規則內容</label>
              <textarea id="bi-b-sk-body" class="bi-input" rows="6"></textarea>
              <div class="bi-actions">
                <button class="go" type="submit">存成新版本</button>
                <button class="bi-btn" id="bi-b-sk-cancel" type="button">取消</button></div>
            </form>
          </details>
          </div>
          <details class="bi-manage bi-adv" id="bi-b-adv-schema">
            <summary>進階：Schema</summary>
          <div id="bi-b-versions"></div>
          <h4>Schema 草稿</h4>
          <div class="bi-actions"><button class="bi-btn" id="bi-b-draft-new" type="button">
            從目前版本建立草稿</button></div>
          <ul id="bi-b-drafts" class="bi-cards" aria-label="schema 草稿"></ul>
          <div id="bi-b-draft" hidden>
            <label class="bi-label" for="bi-b-draft-text">草稿內容（JSON）</label>
            <textarea id="bi-b-draft-text" class="bi-input" rows="14" spellcheck="false"></textarea>
            <div class="bi-step-grid">
              <div><label class="bi-label" for="bi-b-draft-note">這一版的說明</label>
                <input id="bi-b-draft-note" class="bi-input" maxlength="200"></div>
              <div><button class="go" id="bi-b-draft-save" type="button">儲存為新版次</button></div>
              <div><button class="bi-btn" id="bi-b-draft-publish" type="button">
                發布為新版本</button></div>
              <div><button class="bi-btn" id="bi-b-draft-trial" type="button">
                用樣本試跑</button></div>
            </div>
            <div id="bi-b-draft-trial-result" aria-live="polite"></div>
            <div id="bi-b-draft-info" role="status" aria-live="polite"></div>
          </div>
          </details>
          <div class="bi-actions"><button class="bi-btn" type="button" data-bi-next="source">
            上一步</button><button class="go" type="button" data-bi-next="method">
            下一步：Ingest</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="method" aria-labelledby="bi-b-method"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-method" tabindex="-1">步驟 2／3・Ingest</h3>
          <div class="bi-step-grid">
            <div><label class="bi-label" for="bi-b-m-pick">使用的擷取 Skill</label>
              <select id="bi-b-m-pick">
                <option value="builtin:llm">AI 擷取（內建）</option>
                <option value="builtin:rules">表格規則（內建，不用模型）</option>
              </select></div>
            <div><button class="go" id="bi-b-start" type="button">Ingest</button>
              <button class="bi-btn" id="bi-b-batch-stop" type="button" hidden>停止</button></div>
          </div>
          <div class="bi-meta" id="bi-b-batch" role="status"></div>
          <details class="bi-manage bi-adv" id="bi-b-adv-method">
            <summary>進階：擷取設定與試跑</summary>
          <div class="bi-step-grid">
            <div id="bi-b-folder-box" hidden><label class="bi-label" for="bi-b-folder">
              來源在知識庫的哪個資料夾（決定 AI 用哪條擷取規則）</label>
              <select id="bi-b-folder"></select></div>
            <div><label><input id="bi-b-fresh" type="checkbox">
              不沿用上次的回答（同樣的來源和規則，重新問模型一次）</label></div>
            <div><label><input id="bi-b-fit" type="checkbox">
              同時檢查內容和綱要合不合（知識庫才有；輸出約多四到五成，也會多出要人回答的問題）</label></div>
            <div><label class="bi-label" for="bi-b-m-name">另存為新的 Skill（名稱）</label>
              <input id="bi-b-m-name" class="bi-input" maxlength="80"
                placeholder="例如：會議紀錄擷取"></div>
            <div><button class="bi-btn" id="bi-b-m-new" type="button">
              用下方設定另存 Skill</button></div>
          </div>
          <div id="bi-b-m-box" hidden>
            <div id="bi-b-m-info" aria-live="polite"></div>
          </div>
          <div class="bi-actions"><button class="bi-btn" id="bi-b-sb-open" type="button">
            和 AI 調整擷取 Skill</button></div>
          <div class="bi-step-grid">
            <div><label class="bi-label" for="bi-b-entity">卡片類型（單一表格）</label>
              <select id="bi-b-entity"><option value="">自動判斷</option></select></div>
          </div>
          <label class="bi-label" for="bi-b-recipe">
            配方 JSON（多表格報告用；單一表格可留空）</label>
          <textarea id="bi-b-recipe" class="bi-input" rows="6" spellcheck="false"
            placeholder='{"schema_version": "aep.bi.recipe/v1", "passes": [...]}'></textarea>
          <label class="bi-label" for="bi-b-instr">
            判讀規則（文字或 Markdown 來源由 AI 判讀；留空使用預設規則）</label>
          <textarea id="bi-b-instr" class="bi-input" rows="5"
            placeholder="例如：沒有文件依據的需求標成推測；依應用而不是產品拆卡"></textarea>
          <p class="bi-meta">試跑只產生候選卡給你看，不會寫入卡片；試跑結果也不能直接寫入。
            AI 判讀時，原文只當資料，模型不能執行任何動作；出處由程式在原文中找到。</p>
          <div class="bi-actions">
            <button class="go" id="bi-b-trial" type="button">試跑</button>
            <button class="bi-btn" id="bi-b-m-save" type="button" hidden>
              把上面的設定存成這個 Skill 的新版次</button></div>
          <div id="bi-b-trial-result" role="status" aria-live="polite"></div>
          <h4>比較兩次試跑</h4>
          <p class="bi-meta">選同一份來源的兩次試跑（例如同一個 Skill 的兩個版次），看候選卡的增減、
            每個欄位的值與依據、警告與推論數的差異。比較不會寫入任何東西。</p>
          <div class="bi-step-grid">
            <div><label class="bi-label" for="bi-b-cmp-left">較早的試跑</label>
              <select id="bi-b-cmp-left"></select></div>
            <div><label class="bi-label" for="bi-b-cmp-right">較新的試跑</label>
              <select id="bi-b-cmp-right"></select></div>
            <div><button class="bi-btn" id="bi-b-cmp-go" type="button">比較</button></div>
          </div>
          <div id="bi-b-cmp" aria-live="polite"></div>
          </details>
          <div class="bi-actions"><button class="bi-btn" type="button" data-bi-next="schema">
            上一步</button><button class="bi-btn" type="button" data-bi-next="review">
            審核</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="review" aria-labelledby="bi-b-review"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-review" tabindex="-1">步驟 2／3・審核</h3>
          <div class="bi-actions">
            <label class="bi-meta">待審核的執行 <select id="bi-b-run-pick"></select></label>
            <button class="bi-btn" id="bi-b-props-jump" type="button" hidden></button></div>
          <div id="bi-b-chips" class="bi-chips" aria-label="候選卡摘要"></div>
          <div id="bi-b-same"></div>
          <div class="bi-split bi-src-split" id="bi-b-review-split">
            <div class="bi-split-list">
              <div class="bi-actions">
                <label class="bi-meta">卡片類型 <select id="bi-b-cand-type"></select></label>
                <label class="bi-meta">狀態 <select id="bi-b-cand-state">
                  <option value="">全部</option><option value="pending">待決定</option>
                  <option value="accepted">已接受</option><option value="rejected">已拒絕</option>
                </select></label>
                <span class="bi-meta"><span id="bi-b-cand-count" role="status"></span><span
                  id="bi-b-cand-last" role="status"></span></span>
              </div>
              <div class="bi-actions">
                <button class="bi-btn" id="bi-b-apply-all" type="button" disabled>
                  全部套用（0 張）</button>
                <button class="bi-btn" id="bi-b-apply-import" type="button" disabled>
                  全部接受並匯入（0 張）</button>
                <span class="bi-meta" id="bi-b-apply-note"></span></div>
              <p class="bi-meta" id="bi-b-apply-status" role="status" aria-live="polite"></p>
              <div class="bi-scroll bi-scroller"><table class="bi-table bi-stack" id="bi-b-cands"
                aria-label="候選卡清單"><thead><tr><th>卡片</th><th>欄位</th><th>提議值</th>
                <th>狀態</th></tr></thead><tbody></tbody></table></div>
            </div>
            <div class="bi-split-pane" id="bi-b-cand" aria-live="polite">
              <p class="bi-empty">選一列，看原文與引用。</p></div>
          </div>
            <div id="bi-b-props" hidden>
              <h4 id="bi-b-props-h">待審提案</h4>
              <div class="bi-actions" id="bi-b-props-bulk">
                <label class="bi-meta">欄位 <select id="bi-b-props-field"></select></label>
                <label class="bi-meta">來源 <select id="bi-b-props-origin"></select></label>
                <input id="bi-b-props-reason" class="bi-input" maxlength="500"
                  placeholder="一次決定多筆的理由（必填）" aria-label="一次決定多筆的理由">
                <button class="bi-btn" id="bi-b-props-accept" type="button">接受顯示的全部</button>
                <button class="bi-btn" id="bi-b-props-reject" type="button">否決顯示的全部</button>
              </div>
              <div id="bi-b-props-confirm" role="alert"></div>
              <ul id="bi-b-props-list" class="bi-fit"></ul>
            </div>
          <div class="bi-actions"><button class="bi-btn" type="button" data-bi-next="method">
            上一步</button><button class="go" type="button" data-bi-next="commit"
            id="bi-b-next4" disabled>下一步：確認寫入</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="commit" aria-labelledby="bi-b-commit"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-commit" tabindex="-1">步驟 2／3・確認寫入</h3>
          <div id="bi-b-summary"></div>
          <div class="bi-actions">
            <button class="bi-btn" type="button" data-bi-next="review">上一步</button>
            <button class="go" id="bi-b-commit-go" type="button">確認匯入</button></div>
          <div id="bi-b-commit-msg" role="alert"></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="result" aria-labelledby="bi-b-result"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-result" tabindex="-1">步驟 2／3・結果</h3>
          <div id="bi-b-done"></div>
          <div class="bi-actions"><button class="go" type="button" data-bi-next="test">
            下一步：測試與 Push</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="test" aria-labelledby="bi-b-test"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-test" tabindex="-1">步驟 3／3・測試</h3>
          <p class="bi-meta" id="bi-b-overview" hidden>
            全部領域只能看：選工作領域才能新增題目或分析。</p>
          <p class="bi-meta" id="bi-b-ver-none" hidden>只在這台電腦：確認寫入後就生效。</p>
          <details id="bi-b-bench" class="card bi-sec" hidden>
            <summary><span class="bi-sec-title"><strong>Benchmark</strong></span>
              <span class="bi-meta" id="bi-b-bench-state"></span></summary>
            <div class="bi-sec-body">
            <div class="mem-status" id="bi-b-bench-status" role="status" aria-live="polite"
              hidden></div>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-bq-add" type="button">新增題目</button>
              <button class="bi-btn" id="bi-b-qa-open" type="button">和 AI 一起出題</button></div>
            <div class="bi-split bi-src-split" id="bi-b-bq-split">
              <div class="bi-split-list"><div id="bi-b-bq-list" class="bi-scroller"></div></div>
              <div class="bi-split-pane" id="bi-b-bq-pane">
                <h5 id="bi-b-bq-title">新增題目</h5>
                <form id="bi-b-bq-form" novalidate>
                  <label class="bi-label" for="bi-b-bq-q">題目（使用者會怎麼問）</label>
                  <textarea id="bi-b-bq-q" class="bi-input" rows="2" maxlength="1000"
                    placeholder="例如：哪些客戶在評估 TSN？"></textarea>
                  <label class="bi-label" for="bi-b-bq-must">必須提到（逗號分隔）</label>
                  <input id="bi-b-bq-must" class="bi-input" maxlength="2000"
                    placeholder="例如：IEEE 802.1">
                  <label class="bi-label" for="bi-b-bq-not">不可以說（逗號分隔）</label>
                  <input id="bi-b-bq-not" class="bi-input" maxlength="2000">
                  <label class="bi-label" for="bi-b-bq-set">題組</label>
                  <input id="bi-b-bq-set" class="bi-input" maxlength="60" spellcheck="false"
                    list="bi-b-bq-sets" value="main">
                  <datalist id="bi-b-bq-sets"></datalist>
                  <label class="bi-label" for="bi-b-bq-home">領域</label>
                  <select id="bi-b-bq-home"></select>
                  <div class="bi-actions">
                    <button class="go" type="submit" id="bi-b-bq-save">儲存</button>
                    <button class="bi-btn" id="bi-b-bq-del" type="button" hidden>刪除</button>
                  </div>
                </form>
              </div>
            </div>
          <details class="bi-manage bi-adv" id="bi-b-adv-bench">
            <summary>進階：擷取測試</summary>
            <h5>擷取測試</h5>
            <div id="bi-b-bc-list"></div>
            <details id="bi-b-bc-box"><summary>新增擷取測試</summary>
              <form id="bi-b-bc-form" class="bi-step" novalidate>
                <div class="bi-step-grid">
                  <div><label class="bi-label" for="bi-b-bc-slug">代號（小寫英數字與 -）</label>
                    <input id="bi-b-bc-slug" class="bi-input" maxlength="60" spellcheck="false"
                      placeholder="例如：tsn-visit"></div>
                  <div><label class="bi-label" for="bi-b-bc-folder">
                    來源資料夾（決定用哪條擷取規則；留空＝sources）</label>
                    <input id="bi-b-bc-folder" class="bi-input" maxlength="200" spellcheck="false"
                      placeholder="applications/aidc/sources"></div>
                </div>
                <label class="bi-label" for="bi-b-bc-note">原文</label>
                <textarea id="bi-b-bc-note" class="bi-input" rows="5" maxlength="20000"></textarea>
                <label class="bi-label" for="bi-b-bc-expected">
                  應找到什麼（aep.bi.benchmark.expected/v1 JSON）</label>
                <textarea id="bi-b-bc-expected" class="bi-input" rows="8" spellcheck="false"
                  placeholder='{"format": "aep.bi.benchmark.expected/v1", "candidates": [...]}'
                  ></textarea>
                <div class="bi-actions"><button class="bi-btn" type="submit">新增擷取測試</button>
                </div>
              </form>
            </details>
          </details>
            </div>
          </details>
          <details id="bi-b-an" class="card bi-sec" hidden>
            <summary><span class="bi-sec-title"><strong>Dashboard</strong></span>
              <span class="bi-meta" id="bi-b-an-state"></span></summary>
            <div class="bi-sec-body">
            <div id="bi-b-an-list"></div>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-an-new" type="button">和 AI 做新分析</button>
            </div>
          <details class="bi-manage bi-adv" id="bi-b-adv-an">
            <summary>進階：分析包與匯入</summary>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-an-pack" type="button">匯入預設分析包</button>
              <label class="bi-btn" for="bi-b-an-file">匯入分析包檔案</label>
              <input type="file" id="bi-b-an-file" accept=".json,application/json" hidden>
              <button class="bi-btn" id="bi-b-an-export" type="button">匯出分析包</button></div>
            <details class="bi-manage" id="bi-b-atl">
              <summary>從 Atlas 匯入 Dashboard 順序</summary>
              <p class="bi-meta">讀這台電腦上 Atlas 存的 Dashboard，
                只匯入這個知識庫的分析由上到下的順序；不在順序裡的分析會在
                Dashboard 隱藏，不會刪除。Atlas 的位置、大小與參數不會匯入，
                也不會改動 Atlas。</p>
              <label class="bi-label" for="bi-b-atl-port">Atlas 的 port</label>
              <input id="bi-b-atl-port" class="bi-input" inputmode="numeric" maxlength="5"
                value="8127">
              <div class="bi-actions">
                <button class="bi-btn" id="bi-b-atl-load" type="button">
                  讀取 Atlas 的 Dashboard</button></div>
              <label class="bi-label" for="bi-b-atl-name">Atlas Dashboard</label>
              <select id="bi-b-atl-name" class="bi-input"></select>
              <div class="bi-actions">
                <button class="bi-btn" id="bi-b-atl-preview" type="button">預覽匯入</button></div>
              <p class="bi-meta">Atlas 沒有在執行時，可以選一個 Dashboard 檔案（JSON），
                一樣先預覽再確認；只讀順序，檔案本身不會存下來。</p>
              <div class="bi-actions">
                <button class="bi-btn" id="bi-b-atl-pick" type="button">選擇 Dashboard 檔案</button>
                <input type="file" id="bi-b-atl-file" accept=".json,application/json" hidden></div>
              <div id="bi-b-atl-plan" role="region" aria-live="polite" aria-label="匯入預覽"></div>
            </details>
          </details>
            </div>
          </details>
          <div id="bi-b-run" class="bi-run">
            <button class="go" id="bi-b-bench-run" type="button">跑測試</button>
            <span class="bi-meta" id="bi-b-run-why"></span></div>
          <div id="bi-b-test-results" class="bi-test-results">
            <div id="bi-b-bench-report" aria-live="polite"></div>
            <div class="bi-split-pane" id="bi-b-test-dash"><h5>Dashboard</h5></div>
          </div>
          <div class="bi-actions">
            <button class="bi-btn" id="bi-b-to-cards" type="button">看卡片</button></div>
          <div id="bi-b-ver" class="bi-step" role="region" aria-labelledby="bi-b-ver-h" hidden>
            <h4 id="bi-b-ver-h">分享</h4>
            <p class="bi-meta" id="bi-b-ver-reads"></p>
            <div id="bi-b-ver-pending"></div>
            <div id="bi-b-share-list"></div>
            <div id="bi-b-share-tests"></div>
            <div class="bi-step-grid">
              <div><label class="bi-label" for="bi-b-ver-purpose">
                這次改動的目的（有還沒 commit 的改動時要寫，之後在歷史裡看得到）</label>
                <input id="bi-b-ver-purpose" class="bi-input" maxlength="500"
                  placeholder="例如：補上 TSN 的標準組織"></div>
              <div><label class="bi-label" for="bi-b-share-tag">版本名稱（tag）</label>
                <input id="bi-b-share-tag" class="bi-input" maxlength="60" spellcheck="false"></div>
            </div>
            <div class="bi-actions" id="bi-b-share-act">
              <button class="go" id="bi-b-share-go" type="button">分享</button>
              <span class="bi-meta" id="bi-b-share-why"></span></div>
            <ol id="bi-b-share-progress" class="bi-share-progress" aria-live="polite" hidden></ol>
            <div id="bi-b-ver-conflicts" role="alert"></div>
            <h5>歷史與發佈</h5>
            <div id="bi-b-ver-history"></div>
          <details class="bi-manage bi-adv" id="bi-b-adv-ver">
            <summary>進階：分開 commit、push 與捨棄</summary>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-ver-commit" type="button">只 commit</button>
              <button class="bi-btn" id="bi-b-ver-push" type="button">只 push</button>
              <button class="bi-btn" id="bi-b-ver-discard" type="button">
                捨棄還沒 commit 的改動</button></div>
          </details>
          </div>
          <div class="bi-actions"><button class="bi-btn" type="button" data-bi-next="ingest">
            上一步</button></div>
        </section>
      </div>
      <details class="card bi-sec" id="bi-advanced">
      <summary><span class="bi-sec-title">進階：資料集與發佈</span></summary>
      <div class="bi-sec-body">
        <div class="bi-step-grid">
        </div>
        <p class="bi-meta bi-schema-note" id="bi-schema-note"></p>
        <div class="bi-actions">
          <button class="bi-btn" id="bi-publish" type="button" aria-expanded="false"
            aria-controls="bi-publish-panel">發佈到 Shared Platform</button>
              <button class="bi-btn" id="bi-new" type="button" aria-expanded="false"
                aria-controls="bi-new-panel">新增資料集</button>
              <button class="bi-btn" id="bi-install" type="button" aria-expanded="false"
                aria-controls="bi-install-panel">安裝 schema</button>
              <button class="bi-btn" id="bi-demo" type="button">載入示範資料</button>
        </div>
        <p class="bi-pub-state" id="bi-pub-state" role="status" aria-live="polite"></p>
      <form class="card bi-step" id="bi-publish-panel" aria-labelledby="bi-pub-heading" hidden
            novalidate>
        <h3 id="bi-pub-heading">發佈到 Shared Platform</h3>
        <p class="bi-meta" id="bi-pub-dataset"></p>
        <div class="bi-step-grid">
          <div id="bi-pub-name-box"><label class="bi-label" for="bi-pub-name">
              平台名稱（第一次發佈時決定，之後不變）</label>
            <input id="bi-pub-name" class="bi-input" type="text" autocomplete="off"
              spellcheck="false" maxlength="81" placeholder="namespace/name"
              aria-describedby="bi-pub-err"></div>
          <div><label class="bi-label" for="bi-pub-note">版本說明（必填）</label>
            <input id="bi-pub-note" class="bi-input" type="text" autocomplete="off"
              maxlength="200" placeholder="例如 加入 10 月的客戶產品"
              aria-describedby="bi-pub-err" required></div>
          <fieldset class="bi-pub-readers">
            <legend class="bi-label">讀者</legend>
            <p class="bi-pub-team" id="bi-pub-team">我的團隊（預設）</p>
            <label class="bi-check"><input id="bi-pub-org" type="checkbox">
              開放給全公司</label>
            <label class="bi-check bi-pub-confirm" id="bi-pub-confirm-box" hidden>
              <input id="bi-pub-org-confirm" type="checkbox">
              我確認：這是 INTERNAL 資料，會開放給平台上所有成員</label>
          </fieldset>
        </div>
        <div class="bi-pub-what" id="bi-pub-what" aria-label="將分享的內容"></div>
        <p class="bi-pub-first" id="bi-pub-first" hidden><strong>第一次發佈需要管理員審核</strong
          >：管理員確認名稱、擁有團隊與讀者後，同事才看得到；之後的版本會直接發佈。</p>
        <p class="bi-err" id="bi-pub-err" role="alert"></p>
        <div class="bi-actions">
          <button class="go" id="bi-pub-go" type="submit">發佈</button>
          <button class="bi-btn" id="bi-pub-cancel" type="button">取消</button>
        </div>
      </form>
      <div class="card bi-result" id="bi-pub-result" role="status" aria-live="polite" hidden></div>
      <details class="card bi-sec bi-subs" id="bi-subs">
        <summary><span class="bi-sec-title">已訂閱的資料集</span>
          <span class="bi-badge dim" id="bi-subs-count">…</span></summary>
        <div class="bi-sec-body">
          <div class="mem-status" id="bi-status-subs" role="status" aria-live="polite"
               hidden></div>
          <ul class="bi-list bi-subs-list" id="bi-subs-list" aria-label="已訂閱的資料集"></ul>
          <div class="bi-actions bi-subs-more">
            <button class="bi-btn" id="bi-subs-browse" type="button">瀏覽平台上的資料集</button>
          </div>
          <div class="mem-status" id="bi-status-avail" role="status" aria-live="polite"
               hidden></div>
          <ul class="bi-list bi-subs-list" id="bi-subs-avail" aria-label="可以訂閱的資料集"
              hidden></ul>
          <p class="bi-meta" id="bi-subs-how">要讀同事分享的資料集：按「瀏覽平台上的資料集」
            訂閱，或到 Shared Platform 選取資料集後在 Settings 同步。</p>
        </div>
      </details>
      <form class="card bi-step" id="bi-new-panel" aria-label="新增資料集" hidden novalidate>
        <h3>新增資料集</h3>
        <div class="bi-step-grid">
          <div><label class="bi-label" for="bi-new-name">
              名稱（英文字母、數字、- 或 _，最多 40 字）</label>
            <input id="bi-new-name" class="bi-input" type="text" autocomplete="off"
              maxlength="40" spellcheck="false" placeholder="例如 product-spec"
              aria-describedby="bi-new-err"></div>
          <div><label class="bi-label" for="bi-new-schema">Schema</label>
            <select id="bi-new-schema"><option value="">載入中…</option></select></div>
        </div>
        <p class="bi-meta">建立後只能升級到同一個 schema 的新版本，不能換成別的 schema。
          Dashboard 與對話查詢只支援 BI schema（bi.schema/*）；
          其他 schema 的資料集可以匯入、瀏覽卡片，並用更正單改值。</p>
        <p class="bi-err" id="bi-new-err" role="alert"></p>
        <div class="bi-actions">
          <button class="go" id="bi-new-go" type="submit">建立</button>
          <button class="bi-btn" id="bi-new-cancel" type="button">取消</button>
        </div>
      </form>
      <form class="card bi-step" id="bi-install-panel" aria-label="安裝 schema" hidden novalidate>
        <h3>安裝 schema</h3>
        <div class="bi-step-grid">
          <div><label class="bi-label" for="bi-schema-file">Schema 檔（.json）</label>
            <input id="bi-schema-file" type="file" accept=".json,application/json"
              aria-describedby="bi-install-msg"></div>
          <div><button class="go" id="bi-install-go" type="submit"
              disabled>驗證並安裝</button></div>
        </div>
        <p class="bi-meta">同一個 id@version 安裝後不能修改；要改內容，請把 version
          改成新版本再安裝。</p>
        <div id="bi-install-msg" role="status" aria-live="polite"></div>
        <div class="bi-actions">
          <button class="bi-btn" id="bi-example" type="button">安裝範例 schema（產品規格）</button>
          <button class="bi-btn" id="bi-install-cancel" type="button">關閉</button>
        </div>
        <div id="bi-example-files" class="bi-meta" hidden></div>
      </form>
      </div>
      </details>
    </div>"""


BI_JS = r"""
const BI_GAP_SECTIONS = ["6", "10", "19", "18"];
const BI_CLASS = {sourced: ["事實", "accent"], judgement: ["判斷", "warn"],
  derived: ["衍生", "dim"], human: ["人工", "good"]};
const BI_REVIEW = {
  // The sample data (all assumed) arrives as draft: 範例資料／待驗證.
  draft: ["範例資料／待驗證", "warn"], synthetic: ["草稿／虛構", "warn"],
  fictional: ["草稿／虛構", "warn"], assumed: ["範例資料／待驗證", "warn"],
  sample: ["範例資料／待驗證", "warn"], unverified: ["範例資料／待驗證", "warn"],
  candidate: ["候選", "warn"], pending: ["待審", "warn"],
  reviewed: ["已審閱", "good"], verified: ["已驗證", "good"], published: ["已發佈", "good"],
};
const BI_ACTION = {create: ["新增", "good"], update: ["更新", "accent"],
  unchanged: ["不變", "dim"], skip: ["略過", "warn"]};
const BI_MAPPING = {mapped: ["已對應", "good"], alias: ["別名對應", "accent"],
  unknown: ["未知欄位", "warn"], ignored: ["不匯入", "dim"]};
const BI_CHANGE = {add: ["新增", "good"], change: ["變更", "accent"], same: ["不變", "dim"],
  human_kept: ["人工值保留，改成提議", "warn"], state: ["記下沒有值的原因", "accent"]};

// Each dataset follows the schema it was created with (owner 2026-10-21): the
// type filter, import types, card detail and editors read `bi.schema`, loaded
// for the selected dataset. Dashboard and the chat hint are BI-only.
const bi = {schema: null, schemas: [], datasets: [], view: "build", loaded: {}, cards: [],
  cardId: null, detail: null, preview: null, csv: null, importId: null, searchTimer: 0,
  want: null, picked: false, subs: [], subsState: null, publish: null};
const BI_NAME = /^[A-Za-z0-9_-]{1,40}$/;

const bh = (tag, cls, ...children) => memEl(tag, cls, ...children);

function biDataset() { return el("bi-dataset").value || "demo"; }
function biDomain() { return el("bi-domain").value || "robotics"; }

async function biCall(path, body) {
  let reply;
  try { reply = await call(path, body); }
  catch (failure) {
    const payload = failure.payload || {};
    const problem = new Error(payload.message || failure.message || "連線失敗");
    problem.code = payload.code || failure.code; problem.payload = payload; throw problem;
  }
  if (!reply || reply.ok === false) {
    const problem = new Error((reply && (reply.message || reply.code)) || "主機沒有回應");
    problem.code = reply && reply.code; problem.payload = reply || {}; throw problem;
  }
  return reply;
}

function biButton(label, onClick, cls, aria) {
  const button = document.createElement("button");
  button.type = "button"; button.className = cls || "bi-btn"; button.append(text(label));
  if (aria) button.setAttribute("aria-label", aria);
  button.addEventListener("click", (event) => {
    event.preventDefault();
    Promise.resolve(onClick(event)).catch((failure) => biNotice(false, failure.message));
  });
  return button;
}

function biBadge(label, cls) { return bh("span", "bi-badge " + (cls || ""), label); }

// A word on what was just done is old by the next press. Capture runs before the press's
// own handler, so what that says stays. A failure stays until something replaces it.
for (const type of ["click", "change"]) {
  el("kn-pane-bi").addEventListener(type, (event) => {
    if (type === "click" && !event.target.closest("button, a, summary, [role=tab]")) return;
    if (el("bi-notice").classList.contains("good")) biNotice(true, "");
  }, true);
}

function biNotice(ok, message) {
  const box = el("bi-notice"); box.replaceChildren();
  box.className = "mem-notice" + (message ? (ok ? " good" : " bad") : "");
  if (message) box.append(bh("span", "", message));
}

function biStatus(id, state, message, retry) {
  const box = el(id); box.replaceChildren();
  box.className = "mem-status" + (state ? " " + state : ""); box.hidden = !state;
  const owner = box.parentElement;
  if (state === "loading") owner.setAttribute("aria-busy", "true");
  else owner.removeAttribute("aria-busy");
  if (state === "loading") box.append(bh("span", "mem-spinner"), bh("span", "", message));
  if (state === "error") {
    box.append(bh("span", "", message));
    if (retry) box.append(biButton("重試", retry, "bi-btn"));
  }
}

function biTime(iso) {
  if (!iso) return "—";
  const when = new Date(iso);
  if (isNaN(when.getTime())) return String(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return when.getFullYear() + "/" + pad(when.getMonth() + 1) + "/" + pad(when.getDate()) + " "
    + pad(when.getHours()) + ":" + pad(when.getMinutes());
}

function biValue(value) {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map(biValue).join("、") : "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") {
    if (value.label || value.card_id) return value.label || value.card_id;
    return JSON.stringify(value);
  }
  return String(value);
}

function biTypeLabel(name) {
  const found = bi.schema && bi.schema.types.find((type) => type.name === name);
  return found ? found.label || found.name : name || "—";
}

function biSchemaField(typeName, fieldName) {
  const found = bi.schema && bi.schema.types.find((type) => type.name === typeName);
  return found ? found.fields.find((item) => item.name === fieldName) || null : null;
}

function biReview(status, synthetic) {
  if (synthetic && !["draft", "assumed", "sample"].includes(String(status || "").toLowerCase())) {
    return biBadge("範例資料／待驗證", "warn");
  }
  const known = BI_REVIEW[String(status || "").toLowerCase()];
  return known ? biBadge(known[0], known[1]) : biBadge(status || "未標示", "dim");
}

function biSource(source) {
  if (!source) return "來源不明";
  const kind = source.kind;
  const head = kind === "import" ? "匯入 " + (source.ref || "")
    : kind === "human" ? "人工" + (source.by ? " · " + source.by : "")
    : kind === "demo" || kind === "fixture" ? "示範資料" + (source.ref ? " " + source.ref : "")
    : kind === "agent" ? "Agent 提出" + (source.ref ? " " + source.ref : "")
    : kind === "migration" ? "移轉" : (kind || "來源") + (source.ref ? " " + source.ref : "");
  return head.trim() + (source.at ? " · " + biTime(source.at) : "");
}

// -- loading -----------------------------------------------------------------
async function biLoad() {
  biStatus("bi-status-bar", "loading", "載入中…");
  el("bi-counts").textContent = "…";
  try {
    const [datasets, schemas, vaults] = await Promise.all([biCall("/api/bi/datasets"),
      biCall("/api/bi/schemas").catch(() => ({schemas: bi.schemas})),
      biCall("/api/bi/vaults").catch(() => ({vaults: bi.vaults || []}))]);
    bi.datasets = datasets.datasets || []; bi.schemas = schemas.schemas || [];
    bi.vaults = vaults.vaults || [];
    biRenderBar(); biBuildFollowDataset();
    bi.schema = await biCall("/api/bi/schema?dataset=" + encodeURIComponent(biDataset()));
  } catch (failure) {
    el("bi-counts").textContent = "—";
    biStatus("bi-status-bar", "error", "載入失敗：" + failure.message + "。", biLoad);
    return;
  }
  biStatus("bi-status-bar", "");
  biRenderSchema(); biRenderTypes(); biRenderReadOnly();
  biLoadSubs(); biLoadPublishState();
  bi.loaded = {};
  // The working domain first: every tab reads under it.
  await biSourceFolders().catch(() => {});
  await biShowView(bi.view);
  // The build tab asks for the vault's status itself, after what its step needs. Here it is
  // only the line under the row, and must not take the notice from what this tab is doing.
  if (bi.view !== "build") biBuildVault().catch(() => {});
}

// A dataset whose schema is not bi.schema/* has no Dashboard and no chat query.
function biIsBi() { return !bi.schema || bi.schema.bi !== false; }

function biSchemaTitle(ref) {
  const found = bi.schemas.find((item) => item.ref === ref
    || item.id + "@" + item.version === ref);
  return found ? found.title : ref;
}

// The schema's own domains (2.0.0 adds mobile and aerospace, BI vault V9/V12).
const BI_DOMAIN_LABELS = {robotics: "機器人 Robotics", wireless: "無線通訊 Wireless",
  aidc: "AIDC", mobile: "行動 Mobile", aerospace: "航太 Aerospace"};

function biDomainOptions(domains) {
  if (!domains.length) return;
  const select = el("bi-domain"), current = select.value.toLowerCase();
  select.replaceChildren(...domains.map((d) => {
    const option = document.createElement("option");
    // Lower case, as before: the host compares domains without case.
    option.value = d.toLowerCase(); option.textContent = BI_DOMAIN_LABELS[d.toLowerCase()] || d;
    return option;
  }));
  const values = domains.map((d) => d.toLowerCase());
  select.value = values.includes(current) ? current
    : (values.includes("robotics") ? "robotics" : values[0]);
  // The card list starts on every domain: a filter nobody chose hides cards silently.
  const cards = el("bi-card-domain"), kept = cards.value;
  cards.replaceChildren(bh("option", "", "全部領域"), ...[...select.options].map((option) => {
    const copy = bh("option", "", option.textContent); copy.value = option.value; return copy;
  }));
  cards.firstChild.value = "";
  cards.value = values.includes(kept) ? kept : "";
}

function biRenderSchema() {
  const isBi = biIsBi(), schema = bi.schema || {};
  el("bi-demo").hidden = !isBi;
  el("bi-card-domain-box").hidden = Array.isArray(schema.domains) && !schema.domains.length;
  biDashDomainBox();
  biDomainOptions(schema.domains || []);
  const note = el("bi-schema-note"); note.replaceChildren();
  if (!schema.ref) return;
  note.append(text("Schema："), bh("strong", "", schema.title || schema.ref),
    text("（" + schema.ref + "）"));
  if (!isBi) note.append(text(" · 沒有 Dashboard 與對話查詢；卡片、匯入與更正單照常可用"));
}

// Which dataset the page opens on (live test 2026-10-24: always `demo`, even
// when it did not exist): the one asked for (just created or opened), the one
// already shown, the last one chosen in this browser, then the first own
// dataset, the first subscribed one, else `demo` with an empty state.
const BI_LAST = "bi-dataset-last";

function biPick(select) {
  const names = bi.datasets.map((item) => item.name);
  const has = (name) => Boolean(name) && names.includes(name);
  if (has(bi.want)) return bi.want;
  if (bi.picked && !bi.want && has(select.value)) return select.value;
  let remembered = null;
  try { remembered = localStorage.getItem(BI_LAST); } catch (e) { /* no storage */ }
  if (has(remembered)) return remembered;
  const own = bi.datasets.find((item) => !item.read_only);
  if (own) return own.name;
  const subscribed = bi.datasets.find((item) => item.read_only);
  return subscribed ? subscribed.name : "demo";
}

function biRemember(name) {
  try { localStorage.setItem(BI_LAST, name); } catch (e) { /* no storage */ }
}

function biRenderBar() {
  const select = el("bi-dataset"), keep = biPick(select);
  bi.want = null; bi.picked = true;
  select.replaceChildren();
  const names = bi.datasets.map((item) => item.name);
  const empty = !names.includes(keep);
  if (empty) names.unshift(keep); else biRemember(keep);
  // Nothing on this PC yet (acceptance F2): the row's 新增知識庫 and 加入, and no steps
  // for a dataset that does not exist. 新增資料集 stays under 進階.
  const none = empty && !bi.datasets.length;
  el("bi-empty-state").hidden = !none;
  el("kn-pane-bi").classList.toggle("bi-none", none);
  // Two groups: the datasets this PC keeps, then read-only subscribed copies.
  const mine = document.createElement("optgroup"); mine.label = "我的資料集";
  const subscribed = document.createElement("optgroup"); subscribed.label = "已訂閱";
  for (const name of names) {
    const option = document.createElement("option"); option.value = name;
    const info = bi.datasets.find((item) => item.name === name);
    if (info && info.read_only) {
      const sub = biSubOf(name);
      option.textContent = biSubLabel(info, sub) + " · 唯讀";
      subscribed.append(option);
    } else {
      const vault = biVaultOf(name);
      option.textContent = vault ? "共用：" + (vault.title || vault.id) + "（vault）"
        : info && info.schema ? name + " · " + biSchemaTitle(info.schema) : name;
      mine.append(option);
    }
  }
  select.append(mine);
  if (subscribed.children.length) select.append(subscribed);
  // Someone with no vault yet starts here: creating one or joining a colleague's, as many
  // do one as the other (acceptance F21).
  el("bi-b-v-new").className = (bi.vaults || []).length ? "bi-btn" : "go";
  el("bi-b-v-join").className = el("bi-b-v-new").className;
  select.value = keep;
  biRenderCounts();
}

function biRenderCounts() {
  const current = bi.datasets.find((item) => item.name === biDataset());
  const counts = el("bi-counts"); counts.replaceChildren();
  // A vault's status line, under the row, already says how many.
  counts.hidden = Boolean(biVaultOf(biDataset()));
  counts.append(bh("strong", "", String(current ? current.cards : 0)), text("張卡片"));
  const sources = (bi.build.sourcesFor === biDataset() && bi.build.sources || []).length;
  counts.append(bh("span", "", current && current.updated ? "· 更新於 " + biTime(current.updated)
    : sources ? "· " + sources + " 份來源，還沒有卡片" : "· 還沒有資料"));
  // The same words on a vault's line: the bar is hidden there.
  const line = el("bi-b-v-count");
  if (line) {
    const cards = current ? current.cards : 0;
    line.textContent = cards + " 張卡片" + (!cards && sources ? "（" + sources + " 份來源）" : "");
  }
}

function biRenderTypes() {
  for (const id of ["bi-type"]) {
    const select = el(id), keep = select.value;
    select.replaceChildren();
    const first = document.createElement("option"); first.value = "";
    first.textContent = id === "bi-type" ? "全部類型" : "自動判斷"; select.append(first);
    for (const type of (bi.schema && bi.schema.types) || []) {
      const option = document.createElement("option"); option.value = type.name;
      option.textContent = type.label && type.label !== type.name
        ? type.label + "（" + type.name + "）" : type.name;
      select.append(option);
    }
    select.value = keep;
  }
}

function biScroller() {
  // What scrolls this page: the app's main column, or the window.
  for (let at = el("kn-pane-bi").parentElement; at; at = at.parentElement) {
    const overflow = getComputedStyle(at).overflowY;
    if ((overflow === "auto" || overflow === "scroll") && at.scrollHeight > at.clientHeight) {
      return at;
    }
  }
  return document.scrollingElement;
}

function biDashHome() {
  // One Dashboard: in its tab, or in step 3 beside the results. Moved, so its ids stay.
  const inStep = bi.view === "build" && bi.build && bi.build.stage === "test";
  const home = el(inStep ? "bi-b-test-dash" : "bi-view-dashboard");
  if (el("bi-dash-block").parentElement !== home) home.append(el("bi-dash-block"));
  if (inStep && !bi.loaded.dashboard) bi.dashLoad = biLoadDashboard();
}

async function biShowView(name) {
  const scroller = biScroller();
  bi.viewScroll = bi.viewScroll || {};
  if (bi.view !== name) bi.viewScroll[bi.view] = scroller.scrollTop;
  const back = bi.viewScroll[name] || 0;
  if (name === "cards") biCardPeekClose();
  bi.view = name;
  for (const button of document.querySelectorAll("#bi-views [data-bi-view]")) {
    button.setAttribute("aria-selected", String(button.dataset.biView === name));
  }
  for (const key of ["dashboard", "cards", "build"]) {
    el("bi-view-" + key).hidden = key !== name;
  }
  biDashHome();
  if (!bi.loaded[name]) {
    if (name === "dashboard") await biLoadDashboard();
    if (name === "cards") { biFtsStatus(); await biLoadCards(); }
    if (name === "build") { bi.loaded.build = true; await biBuildLoad(); }
  }
  // Back where the person was; a view opened for the first time starts at its top.
  biScroller().scrollTop = back;
}

const BI_STAGE_WORDS = {source: "步驟 1・輸入與轉檔", schema: "步驟 2・類別與規則",
  method: "步驟 2・Ingest", review: "步驟 2・審核", commit: "步驟 2・確認", result: "步驟 2・結果",
  test: "步驟 3・測試"};
const BI_VIEW_WORDS = {dashboard: "Dashboard", cards: "卡片"};

async function biJump(view) {
  // Going to another tab from a button: a way back to the same place stays on screen.
  const from = {view: bi.view, stage: bi.build.stage};
  await biShowView(view);
  bi.back = from;
  el("bi-back-go").textContent = "← 回到「" + (from.view === "build"
    ? BI_STAGE_WORDS[from.stage] || "建立與匯入" : BI_VIEW_WORDS[from.view]) + "」";
  el("bi-back").hidden = false;
}

function biBackHide() { bi.back = null; el("bi-back").hidden = true; }

el("bi-back-go").addEventListener("click", async () => {
  const to = bi.back; biBackHide();
  if (to) await biShowView(to.view);
});

for (const button of document.querySelectorAll("#bi-views [data-bi-view]")) {
  button.addEventListener("click", () => { biBackHide(); biShowView(button.dataset.biView); });
}
// A publish draft belongs to the dataset it was made for: switching drops it.
function biLeaveDataset() {
  biAiClose(); biCardPeekClose(); biBackHide();
  bi.cardId = null; bi.publish = null;
  biPanel("publish", false); el("bi-pub-result").hidden = true;
  el("bi-pub-state").replaceChildren();
}
el("bi-dataset").addEventListener("change", () => {
  biRemember(el("bi-dataset").value); biLeaveDataset(); biBuildFollowDataset(); biLoad();
});
el("bi-empty-demo").addEventListener("click", () => el("bi-demo").click());
const biStuck = new ResizeObserver(() => {
  // Not on a phone, where the row does not stick.
  const row = el("bi-top-row"), sticks = getComputedStyle(row).position === "sticky";
  el("kn-pane-bi").style.setProperty("--bi-top-h", (sticks ? row.offsetHeight : 0) + "px");
  el("kn-pane-bi").style.setProperty("--bi-steps-h", el("bi-build-steps").offsetHeight + "px");
});
biStuck.observe(el("bi-top-row")); biStuck.observe(el("bi-build-steps"));
el("bi-card-domain").addEventListener("change", () => {
  bi.cardId = null; biLoadCards();
});
el("bi-domain").addEventListener("change", () => {
  bi.loaded = {}; bi.cardId = null; biShowView(bi.view);
});
el("bi-sample").addEventListener("change", () => {
  bi.loaded = {}; biShowView(bi.view);
});
el("bi-demo").addEventListener("click", async () => {
  const button = el("bi-demo"); button.disabled = true; button.setAttribute("aria-busy", "true");
  biNotice(true, "");
  biStatus("bi-status-bar", "loading", "正在載入示範資料…");
  try {
    const reply = await biCall("/api/bi/demo/load", {dataset: biDataset()});
    const done = reply.imported || {};
    biNotice(true, "示範資料已載入：新增 " + (done.created || 0) + "、更新 " + (done.updated || 0)
      + "、不變 " + (done.unchanged || 0) + "。");
    await biLoad();
  } catch (failure) {
    biStatus("bi-status-bar", "error", "示範資料沒有載入：" + failure.message + "。",
      () => el("bi-demo").click());
  } finally { button.disabled = false; button.removeAttribute("aria-busy"); }
});

// -- Dashboard -----------------------------------------------------------------
function biSectionKey(id) {
  const match = String(id == null ? "" : id).match(/(\d+[a-z]?)/i);
  return match ? match[1].toLowerCase() : String(id);
}

function biCell(value, open = biOpenCard, named = null) {
  const box = document.createDocumentFragment();
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      if (index) box.append(text("、"));
      box.append(biCell(item, open, named));
    });
    return box;
  }
  if (value && typeof value === "object" && value.card_id) {
    box.append(biButton(value.label || value.card_id, () => open(value.card_id), "bi-link"));
    return box;
  }
  if (value == null || value === "") { box.append(text("—")); return box; }
  const source = typeof value === "object" ? JSON.stringify(value) : String(value);
  const whole = named && named(source);
  if (whole) { box.append(biButton(source, () => open(whole), "bi-link")); return box; }
  const pattern = /\[\[card:([^|\]]+)\|([^\]]*)\]\]/g;
  let last = 0, match;
  while ((match = pattern.exec(source))) {
    if (match.index > last) box.append(text(source.slice(last, match.index)));
    const id = match[1], label = match[2] || match[1];
    box.append(biButton(label, () => open(id), "bi-link"));
    last = pattern.lastIndex;
  }
  if (last < source.length) box.append(text(source.slice(last)));
  return box;
}

async function biLoadDashboard() {
  // Newest request only, as in biLoadCards: a late older reply must not
  // repaint the Dashboard for a dataset or domain that is no longer shown.
  const seq = bi.dashSeq = (bi.dashSeq || 0) + 1;
  biStatus("bi-status-dash", "loading", "載入中…");
  el("bi-dash-summary").replaceChildren(); el("bi-dash-sections").replaceChildren();
  let reply;
  const extra = Object.entries(bi.dashParams || {}).map(([name, value]) =>
    "&param." + encodeURIComponent(name) + "=" + encodeURIComponent(String(value))).join("");
  try {
    reply = await biCall("/api/bi/dashboard?dataset=" + encodeURIComponent(biDataset())
      + "&domain=" + encodeURIComponent(biDomain())
      + (biScope() ? "&home=" + encodeURIComponent(biScope()) : "")
      + (el("bi-sample").checked ? "&include_sample=1" : "") + extra);
  } catch (failure) {
    if (seq !== bi.dashSeq) return;
    biStatus("bi-status-dash", "error", "Dashboard 載入失敗：" + failure.message + "。",
      biLoadDashboard);
    return;
  }
  if (seq !== bi.dashSeq) return;
  biStatus("bi-status-dash", ""); bi.loaded.dashboard = true;
  biRenderDashboard(reply);
  // An old domain configuration still to move (BI D4).
  el("bi-dom").hidden = !reply.domains_left; el("bi-dom-plan").replaceChildren();
}

// -- the old domain configuration: preview and move it (BI D3, D4) ---------------
async function biMigrateDomains() {
  const vault = biVaultOf(biDataset());
  const url = vault ? "/api/bi/vaults/" + vault.id + "/migrate-domains" : "/api/bi/migrate-domains";
  const body = vault ? {} : {dataset: biDataset()};
  const plan = await biCall(url, body);
  const box = el("bi-dom-plan"); box.replaceChildren();
  const list = bh("ul", "");
  if (plan.schema) {
    list.append(bh("li", "", "schema 從 " + plan.schema.from + " 升到 " + plan.schema.to));
  }
  if (plan.schema_adds) {
    const adds = Object.entries(plan.schema_adds.enum_aliases || {}).map(([f, t]) =>
      f + "：" + Object.entries(t).map(([a, v]) => a + " → " + v).join("、"));
    list.append(bh("li", "", "建立新的本地 schema 版本：" + [...adds,
      ...(plan.schema_adds.name_pattern ? ["節點名稱規則 " + plan.schema_adds.name_pattern] : [])]
      .join("；")));
  }
  for (const item of plan.aliases) {
    list.append(bh("li", "", item.type + "「" + item.card + "」加上別名：" + item.add.join("、")));
  }
  for (const item of plan.chains) {
    list.append(bh("li", "", "節點「" + item.node + "」的鏈別：" + item.chain.join("、")));
  }
  if (plan.notes.length) {
    list.append(bh("li", "", plan.notes.map((n) => n.label).join("、") + " 的判讀規則搬進"
      + (plan.notes_to === "skills" ? "各自的 extract skill"
        : "擷取方法「領域判讀規則（從領域設定搬來）」")));
  }
  list.append(bh("li", "", "移除領域設定（區段與技術領域改由 schema 的允許值提供）"));
  const notes = [];
  if (plan.missing.length) {
    notes.push("找不到卡片、不會建立的別名：" + plan.missing.map((m) => m.alias + " → "
      + m.name).join("、"));
  }
  if (plan.missing_nodes.length) {
    notes.push("節點清單上還沒有卡片的節點（不會建立）：" + plan.missing_nodes.join("、"));
  }
  if (plan.dropped_chains.length) {
    notes.push("schema 不允許的鏈：" + plan.dropped_chains.join("、"));
  }
  if (plan.unknown_areas.length) {
    notes.push("schema 不允許的技術領域：" + plan.unknown_areas.join("、"));
  }
  if (plan.enum_aliases_dropped.length) {
    notes.push("指向 schema 不允許的值、不會搬的別名：" + plan.enum_aliases_dropped.map((e) =>
      e.field + " " + e.alias + " → " + e.value).join("、"));
  }
  const committed = plan.writes === "commit";
  box.append(bh("p", "", committed ? "會寫成一個 commit「" + plan.purpose + "」："
    : "會直接寫進這台電腦的資料集："), list, ...notes.map((n) => bh("p", "bi-warn", n)),
    bh("div", "bi-actions", biButton(committed ? "確認搬移（寫入一個 commit）" : "確認搬移（寫入）",
      async () => {
        await biCall(url, {...body, apply: true, token: plan.token});
        box.replaceChildren();
        biNotice(true, "已把領域設定搬進 schema 與卡片"
          + (committed ? "（push 後大家才會看到）。" : "。"));
        bi.loaded = {}; biShowView(bi.view);
      }, "go", "確認把領域設定搬進 schema 與卡片"),
    biButton("取消（不寫入）", () => box.replaceChildren(), "bi-btn")));
}

function biRenderDashboard(reply) {
  const sections = (reply.sections || []).slice();
  const notShown = reply.not_shown || [], absent = el("bi-dash-not-shown");
  absent.hidden = !notShown.length;
  absent.replaceChildren(...notShown.map((a) => bh("div", "", "「" + a.title
    + "」沒有顯示：schema 沒有它需要的 " + a.missing.join("、")
    + "。到「建立與匯入」的「分析與圖表」修改它的 requires。")));
  const holder = el("bi-dash-sections"), strip = el("bi-dash-summary");
  if (reply.dashboard === false) {  // a dataset of a non-BI schema
    holder.append(bh("div", "bi-none", bh("h3", "", reply.message || "這個 schema 沒有 Dashboard"),
      bh("p", "", "資料集「" + biDataset() + "」使用「" + biSchemaTitle(reply.schema || "")
        + "」。Dashboard 與對話查詢只支援 BI schema（bi.schema/*）；這個資料集的卡片可以在"
        + "「卡片」瀏覽並提更正單，也可以在「建立與匯入」加入資料。"),
      bh("div", "bi-actions", biButton("看卡片", () => biJump("cards"), "go"),
        biButton("建立與匯入", () => biJump("build"), "bi-btn"))));
    return;
  }
  if (!sections.length && reply.home) {
    holder.append(bh("p", "bi-empty", "這個領域的 Dashboard 還是空的："
      + "按「和 AI 做新分析」，或從「Dashboard」區塊把現有的分析加進來。"));
    return;
  }
  if (!sections.length) {
    holder.append(bh("p", "bi-empty",
      "這個領域還沒有卡片。先「載入示範資料」或到「建立與匯入」加入資料。"));
    return;
  }
  const rank = (section) => {
    const at = BI_GAP_SECTIONS.indexOf(biSectionKey(section.id));
    return at < 0 ? BI_GAP_SECTIONS.length : at;
  };
  // A vault's analyses come in its own order (BI P3); the coded ones put gaps first.
  if (!reply.ordered) sections.sort((a, b) => rank(a) - rank(b));
  biDashParams(reply.params || {});
  let red = 0, warn = 0, stale = 0;
  for (const section of sections) {
    for (const flag of section.flags || []) {
      if (flag.level === "red") red += 1; else warn += 1;
      if (/過期|推測|待驗證|stale|assumed/i.test(flag.text || "")) stale += 1;
    }
    if (biSectionKey(section.id) === "8") stale += (section.rows || []).length;
  }
  const given = reply.summary || {};
  const stat = (cls, count, label) => bh("div", "bi-stat " + cls, bh("b", "", String(count)),
    bh("span", "", label));
  strip.append(stat("red", given.red ?? red, "紅色缺口"), stat("warn", given.warn ?? warn, "警告"),
    stat("dim", given.stale ?? stale, "過期或推測內容"));
  strip.setAttribute("aria-label", "Dashboard 摘要");
  for (const section of sections) holder.append(biSection(section));
}

function biDashParams(specs) {
  // Parameters some analysis declares beyond 領域 and 範例卡, shown at the top.
  const box = el("bi-dash-params"); box.replaceChildren();
  bi.dashParams = bi.dashParams || {};
  const row = biParamInputs({title: "Dashboard", inputs: specs}, bi.dashParams,
    () => biLoadDashboard());
  box.hidden = !row;
  if (row) box.append(...row.childNodes);
}

function biSection(section) {
  const box = document.createElement("details");
  box.className = "card bi-sec";
  box.dataset.section = section.analysis ? section.id : biSectionKey(section.id);
  const flags = section.flags || [];
  if (BI_GAP_SECTIONS.includes(box.dataset.section) || (section.analysis && flags.length)) {
    box.open = true;
  }
  const summary = bh("summary", "", bh("span", "bi-sec-title", section.title || section.id));
  const reds = flags.filter((flag) => flag.level === "red").length;
  if (reds) summary.append(biBadge("缺口 " + reds, "bad"));
  if (flags.length - reds) summary.append(biBadge("警告 " + (flags.length - reds), "warn"));
  summary.append(bh("span", "bi-meta", (section.rows || []).length + " 列"));
  const body = bh("div", "bi-sec-body");
  if (section.note) body.append(bh("p", "bi-sec-note", section.note));
  const rows = section.rows || [];
  const chart = section.chart || {type: "table"};
  if (!rows.length) body.append(bh("p", "bi-empty", "沒有資料。"));
  else if (chart.type !== "table") {
    const plain = rows.map((row) => row.map((cell) =>
      cell && typeof cell === "object" ? cell.label : cell));
    body.append(biChart({columns: section.columns || [], rows: plain}, chart));
  } else if (section.kind === "matrix") body.append(biMatrix(section));
  else if (section.kind === "funnel") body.append(biFunnel(section));
  else body.append(biTable(section));
  box.append(summary, body);
  return box;
}

function biTable(section) {
  const columns = section.columns || [];
  const table = bh("table", "bi-table bi-stack"), head = bh("tr", "");
  for (const name of columns) head.append(bh("th", "", name));
  table.append(bh("thead", "", head));
  const body = bh("tbody", "");
  (section.rows || []).forEach((row, index) => {
    const tr = bh("tr", ""), flags = (section.flags || []).filter((flag) => flag.row === index);
    if (flags.length) {
      tr.className = flags.some((flag) => flag.level === "red") ? "bi-flag-red" : "bi-flag-warn";
    }
    row.forEach((value, at) => {
      const td = bh("td", "", biCell(value));
      if (columns[at]) td.dataset.label = columns[at];
      if (at === 0 && flags.length) {
        td.append(bh("div", "bi-flag-badges", ...flags.map((flag) =>
          biBadge(flag.text, flag.level === "red" ? "bad" : "warn"))));
      }
      tr.append(td);
    });
    body.append(tr);
  });
  table.append(body);
  return bh("div", "bi-scroll", table);
}

function biMatrix(section) {
  const columns = section.columns || [];
  const table = bh("table", "bi-table bi-matrix"), head = bh("tr", "");
  for (const name of columns) head.append(bh("th", "", name));
  table.append(bh("thead", "", head));
  const body = bh("tbody", "");
  let top = 0;
  for (const row of section.rows || []) {
    for (const value of row.slice(1)) if (typeof value === "number") top = Math.max(top, value);
  }
  for (const row of section.rows || []) {
    const tr = bh("tr", "");
    row.forEach((value, at) => {
      const td = bh(at ? "td" : "th", "", biCell(value));
      if (at && (value === 0 || value === "0")) td.className = "bi-zero";
      else if (at && typeof value === "number" && top && value === top) td.className = "bi-hot";
      if (at && columns[at]) td.title = row[0] + " × " + columns[at];
      tr.append(td);
    });
    body.append(tr);
  }
  table.append(body);
  const scroll = bh("div", "bi-scroll", table);
  scroll.tabIndex = 0; scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", section.title || "矩陣");
  return scroll;
}

function biFunnel(section) {
  const rows = section.rows || [];
  const top = Math.max(1, ...rows.map((row) => Number(row[1]) || 0));
  const box = bh("div", "bi-funnel");
  for (const row of rows) {
    const count = Number(row[1]) || 0;
    const bar = bh("div", "bi-funnel-bar"); bar.style.width = (count / top * 100) + "%";
    const track = bh("div", "bi-funnel-track", bar);
    track.setAttribute("role", "img");
    track.setAttribute("aria-label", biValue(row[0]) + "：" + count);
    box.append(bh("div", "bi-funnel-row", bh("span", "bi-funnel-label", biCell(row[0])), track,
      bh("span", "bi-funnel-n", String(count))));
    if (row.length > 2 && row[2] != null && !(Array.isArray(row[2]) && !row[2].length)) {
      box.append(bh("div", "bi-funnel-items bi-meta", biCell(row[2])));
    }
  }
  return box;
}

// -- card browser ------------------------------------------------------------
async function biLoadCards() {
  // Only the newest request may paint: an older reply that arrives late must
  // not overwrite the list for the filter the person has chosen since.
  const seq = bi.cardsSeq = (bi.cardsSeq || 0) + 1;
  biStatus("bi-status-cards", "loading", "載入中…");
  const query = "?dataset=" + encodeURIComponent(biDataset()) + "&type="
    + encodeURIComponent(el("bi-type").value) + "&q=" + encodeURIComponent(el("bi-q").value.trim())
    + "&domain=" + encodeURIComponent(el("bi-card-domain").value);
  let reply;
  try { reply = await biCall("/api/bi/cards" + query); }
  catch (failure) {
    if (seq !== bi.cardsSeq) return;
    biStatus("bi-status-cards", "error", "卡片載入失敗：" + failure.message + "。", biLoadCards);
    return;
  }
  if (seq !== bi.cardsSeq) return;
  biStatus("bi-status-cards", ""); bi.loaded.cards = true;
  bi.cards = reply.cards || [];
  biRenderCards();
}

function biRenderCards() {
  const list = el("bi-cards"); list.replaceChildren();
  // Of how many, so a filter can never hide cards without saying so.
  const total = (biCurrent() || {}).cards;
  el("bi-card-count").textContent = bi.cards.length + " 張卡片"
    + (Number.isInteger(total) && total !== bi.cards.length ? "（共 " + total + " 張）" : "");
  if (!bi.cards.length) {
    const picked = el("bi-card-domain");
    list.append(bh("li", "bi-empty", picked.value && total
      ? picked.selectedOptions[0].textContent + " 領域沒有這類卡片。"
      : el("bi-q").value.trim() || el("bi-type").value
      ? "沒有符合的卡片。"
      : "這個資料集還沒有卡片。先「載入示範資料」或到「建立與匯入」加入資料。"));
    return;
  }
  for (const card of bi.cards) {
    const row = document.createElement("button");
    row.type = "button"; row.className = "bi-card-row"; row.dataset.card = card.id;
    row.setAttribute("aria-current", String(card.id === bi.cardId));
    row.append(bh("span", "bi-card-top", biBadge(biTypeLabel(card.entity_type), "type"),
      biReview(card.review_status, card.synthetic)),
    bh("span", "bi-card-name", card.name || card.canonical_key),
    bh("span", "bi-meta", (card.canonical_key || "") + " · " + (card.fields || 0) + " 個欄位 · "
      + biTime(card.updated)));
    row.addEventListener("click", () => biOpenCard(card.id));
    list.append(bh("li", "", row));
  }
}

// Personal dashboards live in Atlas (docs/phases/BI_VAULT.md §6.3). Its address
// is a per-browser preference; a no-cors request only tells whether something
// answers there, so a stopped Atlas is named instead of opening a dead tab.
// The default is the loopback Atlas on the page's own scheme; the page names
// no outside address (test_the_page_fetches_nothing_from_anywhere).
const BI_ATLAS_KEY = "bi-atlas-url";
const BI_ATLAS_DEFAULT = location.protocol + "//127.0.0.1:8127";

function biAtlasUrl() {
  let saved = "";
  try { saved = localStorage.getItem(BI_ATLAS_KEY) || ""; } catch (e) { /* */ }
  return saved || BI_ATLAS_DEFAULT;
}

el("bi-dom-migrate").addEventListener("click", () => biMigrateDomains()
  .catch((failure) => biNotice(false, "沒有預覽：" + failure.message)));
el("bi-atlas-set").addEventListener("toggle", () => { el("bi-atlas-url").value = biAtlasUrl(); });
el("bi-atlas-save").addEventListener("click", () => {
  let value = el("bi-atlas-url").value.trim();
  if (value && !/^[a-z]+:/i.test(value)) value = location.protocol + "//" + value;
  if (value && !/^https?:\/\/[^\s]+$/i.test(value)) {
    el("bi-atlas-state").textContent = "網址要用 http 或 https。"; return;
  }
  try {
    if (value) localStorage.setItem(BI_ATLAS_KEY, value);
    else localStorage.removeItem(BI_ATLAS_KEY);
  } catch (e) { /* */ }
  el("bi-atlas-state").textContent = "已儲存：" + biAtlasUrl();
});
el("bi-atlas-open").addEventListener("click", async () => {
  const url = biAtlasUrl(), state = el("bi-atlas-state");
  state.textContent = "正在確認 Atlas 是否在執行…";
  const stop = new AbortController(), timer = setTimeout(() => stop.abort(), 3000);
  try {
    await fetch(url, {mode: "no-cors", cache: "no-store", signal: stop.signal});
    state.textContent = "";
    window.open(url, "_blank", "noopener");
  } catch (e) {
    state.textContent = "Atlas 沒有回應（" + url + "）。請先啟動 Atlas"
      + "（python -m server --port 8127），或在「Atlas 位址」改成正確的網址。";
  } finally { clearTimeout(timer); }
});

// -- full-text search over cards and source Markdown (BI vaults V3) -----------
function biMarked(textValue, marks) {
  const out = []; let at = 0;
  for (const [start, end] of (marks || []).slice().sort((a, b) => a[0] - b[0])) {
    if (start < at) continue;
    out.push(textValue.slice(at, start), bh("mark", "", textValue.slice(start, end)));
    at = end;
  }
  out.push(textValue.slice(at));
  return bh("span", "", ...out);
}

function biIndexLine(index) {
  if (!index || !index.exists) return "・還沒有索引（第一次搜尋時建立）";
  return "・索引：" + index.cards + " 張卡片、" + index.chunks + " 段原文"
    + (index.updated_at ? "・更新於 " + biTime(index.updated_at) : "")
    + (index.behind ? "・落後，搜尋時會先更新" : "");
}

async function biFtsStatus() {
  const info = bi.datasets.find((item) => item.name === biDataset());
  el("bi-fts-rebuild").hidden = Boolean(info && info.read_only);
  try {
    const reply = await call("/api/bi/index?dataset=" + encodeURIComponent(biDataset()));
    el("bi-fts-index").textContent = biIndexLine(reply.index);
  } catch (failure) { el("bi-fts-index").textContent = "・索引狀態讀不到：" + failure.message; }
}

el("bi-fts-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const q = el("bi-fts-q").value.trim(), out = el("bi-fts-out"); out.replaceChildren();
  if (!q) { el("bi-fts-q").focus(); return; }
  out.append(bh("p", "bi-meta", "搜尋中…"));
  let reply;
  try {
    reply = await call("/api/bi/search?dataset=" + encodeURIComponent(biDataset()) + "&q="
      + encodeURIComponent(q) + "&limit=20");
  } catch (failure) {
    out.replaceChildren(bh("p", "bi-err", "沒有搜尋：" + failure.message + "。"));
    return;
  }
  out.replaceChildren();
  el("bi-fts-index").textContent = biIndexLine(reply.index);
  if (reply.mode === "scan") out.append(bh("p", "bi-meta", "有少於 3 個字的詞，改用逐筆比對。"));
  out.append(bh("h4", "", "卡片（" + reply.cards.length + "）"));
  out.append(reply.cards.length ? bh("ul", "", ...reply.cards.map((c) => bh("li", "",
    biButton(biTypeLabel(c.entity_type) + "・" + c.name, () => biOpenCard(c.id), "bi-link"),
    ...c.hits.slice(0, 3).map((h) => bh("div", "bi-meta", h.field + "：",
      biMarked(h.snippet, h.marks))))))
    : bh("p", "bi-meta", "沒有卡片符合。"));
  out.append(bh("h4", "", "來源原文（" + reply.passages.length + "）"));
  out.append(reply.passages.length ? bh("ul", "", ...reply.passages.map((s) => bh("li", "",
    bh("strong", "", s.source_name), " 第 " + s.rev + " 版・第 " + s.line_start + "–"
      + s.line_end + " 行", bh("div", "bi-meta", biMarked(s.snippet, s.marks)))))
    : bh("p", "bi-meta", "原文沒有符合的段落。"));
});
el("bi-fts-rebuild").addEventListener("click", async () => {
  const button = el("bi-fts-rebuild"); button.disabled = true;
  try {
    const reply = await biCall("/api/bi/index/rebuild", {dataset: biDataset()});
    el("bi-fts-index").textContent = biIndexLine(reply.index);
    const missed = reply.index.not_converted || [];
    biNotice(true, "索引已重建" + (missed.length ? "；" + missed.length
      + " 份來源轉不出 Markdown，沒有收進索引" : "") + "。");
  } catch (failure) { biNotice(false, "索引沒有重建：" + failure.message); }
  finally { button.disabled = false; }
});

el("bi-type").addEventListener("change", () => biLoadCards());
el("bi-q").addEventListener("input", () => {
  clearTimeout(bi.searchTimer); bi.searchTimer = setTimeout(() => biLoadCards(), 250);
});
el("bi-q").addEventListener("keydown", (event) => {
  if (event.key === "Enter") { clearTimeout(bi.searchTimer); biLoadCards(); }
});

function biSideRoom() {
  el("kn-pane-bi").classList.toggle("bi-ai-open",
    !el("bi-ai").hidden || !el("bi-card-peek").hidden);
}

function biCardPeekClose() {
  if (el("bi-card-peek").hidden) return;
  el("bi-card-peek").hidden = true;
  el("bi-detail").parentElement === el("bi-card-peek-body")
    && el("bi-card-split").append(el("bi-detail"));
  biSideRoom();
}

el("bi-card-peek-close").addEventListener("click", biCardPeekClose);
el("bi-card-peek").addEventListener("keydown", (event) => {
  if (event.key === "Escape") biCardPeekClose();
});

async function biOpenCard(id) {
  bi.cardId = id;
  if (bi.view !== "cards") {
    el("bi-card-peek-body").append(el("bi-detail"));
    el("bi-card-peek").hidden = false;
    biSideRoom();
  }
  for (const row of document.querySelectorAll("#bi-cards [data-card]")) {
    row.setAttribute("aria-current", String(row.dataset.card === id));
  }
  await biLoadDetail(true);
}

async function biLoadDetail(focus) {
  const id = bi.cardId;
  if (!id) return;
  biStatus("bi-status-detail", "loading", "開啟中…");
  el("bi-detail-body").replaceChildren();
  let reply;
  try {
    reply = await biCall("/api/bi/cards/" + encodeURIComponent(id) + "?dataset="
      + encodeURIComponent(biDataset()));
  } catch (failure) {
    biStatus("bi-status-detail", "error", "卡片開不了：" + failure.message + "。",
      () => biLoadDetail(focus));
    return;
  }
  if (bi.cardId !== id) return;
  biStatus("bi-status-detail", ""); bi.detail = reply;
  biRenderDetail();
  el("bi-detail").scrollTop = 0;  // a card opens at its top
  if (focus) {
    const title = el("bi-detail-title");
    title.focus({preventScroll: true});
    if (window.matchMedia("(max-width: 900px)").matches) {
      el("bi-detail").scrollIntoView({block: "start"});
    }
  }
  biLoadHistory();
}

const BI_ABSTRACT = [["summary", "摘要"], ["usage", "用途"], ["scope", "範圍"]];

function biRenderDetail() {
  const {card, fields = [], links = [], proposals = []} = bi.detail;
  const body = el("bi-detail-body"); body.replaceChildren();
  const title = bh("h3", "", card.name || card.canonical_key);
  title.id = "bi-detail-title"; title.tabIndex = -1;
  const head = bh("div", "bi-card-top", biBadge(biTypeLabel(card.entity_type), "type"),
    biReview(card.review_status, card.synthetic),
    bh("span", "bi-meta", card.canonical_key + " · 版本 " + card.version
      + " · 更新於 " + biTime(card.updated)));
  body.append(title, head);
  // What the card is about comes first, each with its source, history and 更正單.
  const about = bh("div", "bi-fields"); about.id = "bi-detail-abstract";
  for (const [name, label] of BI_ABSTRACT) {
    const item = fields.find((f) => f.field === name);
    if (item) about.append(biFieldRow(card, {...item, label}));
  }
  if (biIsBi() && !fields.some((f) => f.field === "summary")) {
    about.prepend(bh("p", "bi-meta", "沒有摘要"));
  }
  if (about.childNodes.length) body.append(about);
  if (card.domain != null) body.append(bh("p", "bi-meta", "領域：" + biValue(card.domain)));
  body.append(bh("h4", "", "欄位"));
  const list = bh("div", "bi-fields");
  const others = fields.filter((f) => !BI_ABSTRACT.some(([name]) => name === f.field));
  for (const item of others) list.append(biFieldRow(card, item));
  if (!others.length) list.append(bh("p", "bi-empty", "沒有其他欄位。"));
  body.append(list);
  biRenderStates(body, card, bi.detail.field_states || {});
  biRenderReviews(body, card);
  body.append(bh("h4", "", "關聯"));
  if (!links.length) body.append(bh("p", "bi-meta", "沒有關聯。"));
  else {
    const ul = bh("ul", "bi-list");
    for (const link of links) {
      const label = (biSchemaField(card.entity_type, link.field) || {}).label || link.field;
      const li = bh("li", "", bh("span", "bi-meta", label + "："));
      if (link.missing || !link.target_id) {
        li.append(bh("span", "", link.target_key || "—"), text(" "),
          bh("span", "bi-missing", "⚠ 找不到目標卡片"));
        li.dataset.missing = "true";
      } else {
        li.append(biButton(link.target_key || link.target_id, () => biOpenCard(link.target_id),
          "bi-link"));
      }
      ul.append(li);
    }
    body.append(ul);
  }
  body.append(bh("h4", "", "待審提議（" + proposals.length + "）"));
  if (!proposals.length) body.append(bh("p", "bi-meta", "沒有待審提議。"));
  else {
    body.append(bh("p", "bi-meta",
      "匯入或 Agent 給的值與人工值不同時，不會覆蓋，會列在這裡等你決定。"));
    const ul = bh("ul", "bi-list");
    for (const item of proposals) {
      const label = (fields.find((f) => f.field === item.field) || {}).label || item.field;
      ul.append(bh("li", "", bh("strong", "", label), text("：" + biValue(item.value) + " "),
        bh("span", "bi-meta", "（" + biSource(item.source) + "）")));
    }
    body.append(ul);
  }
  body.append(bh("h4", "", "欄位歷史"));
  const history = bh("div", ""); history.id = "bi-history-box";
  const status = bh("div", "mem-status"); status.id = "bi-status-history"; status.hidden = true;
  status.setAttribute("role", "status");
  const historyList = bh("div", ""); historyList.id = "bi-history";
  history.append(status, historyList); body.append(history);
}

const BI_STATE_WORDS = {not_applicable: "不適用", pending_confirmation: "待確認",
  confirmed_none: "確認沒有", unknown: "未知"};
const BI_STANCE = [["supports", "支持：這段出處支持這個敘述"],
  ["refutes", "反駁：這段出處和這個敘述相反"], ["context_only", "僅背景：只是背景，不能當依據"]];
const BI_DIRECT = [["direct", "直接支持：出處明確寫出這件事"],
  ["indirect", "間接支持：要經過推論才得到"], ["insufficient", "不足以支持：不能當作依據"],
  ["unknown", "未知：資訊不足，無法判斷"]];
const BI_SAME = [["independent", "獨立來源：不是轉述別的來源"],
  ["same_source", "同源：轉述或轉載同一個來源"], ["unknown", "未知：看不出來"]];
const BI_REVIEW_VERDICT = [["accepted", "採信"], ["pending", "待確認"], ["rejected", "不採信"]];
const biWord = (list, code) => ((list.find(([c]) => c === code) || [, code])[1] || "")
  .split("：")[0];

function biRenderStates(body, card, states) {
  const names = Object.keys(states);
  if (!names.length) return;
  body.append(bh("h4", "", "沒有值的欄位"));
  const ul = bh("ul", "bi-list"); ul.dataset.fieldStates = "true";
  for (const name of names) {
    const label = (biSchemaField(card.entity_type, name) || {}).label || name;
    const state = states[name];
    ul.append(bh("li", "", bh("strong", "", label), text("："
      + (BI_STATE_WORDS[state.state] || state.state) + " "),
      bh("span", "bi-meta", state.raw ? "（寫的是「" + state.raw + "」）" : "")));
  }
  body.append(ul);
}

function biPlace(item) {
  const place = Object.entries(item.locator || {}).map(([k, v]) => k + " " + v).join("・");
  return (item.source_name || "沒有來源檔") + (place ? "（" + place + "）" : "");
}

// One reference to review: what it says, where, what the model judged and any earlier
// review. Changes go through a note (preview, then confirm), never a field edit.
function biReviewRow(card, target, statement, item) {
  const row = bh("div", "bi-field"); row.dataset.review = item.reference_id || "relation";
  const now = (item.assessment || {}).current || {};
  const reason = ((item.assessment || {}).system || {}).reason;
  row.append(bh("div", "bi-field-head", bh("strong", "", statement),
    biBadge(biWord(BI_STANCE, item.stance || "supports"),
      item.stance === "refutes" ? "warn" : "dim"),
    now.verdict ? biBadge(biWord(BI_REVIEW_VERDICT, now.verdict), "accent") : text("")));
  if (item.reference_id) {
    row.append(bh("div", "bi-field-value", "「" + (item.excerpt || "") + "」"),
      bh("p", "bi-meta", "出處：" + biPlace(item)));
  } else row.append(bh("p", "bi-meta", "這條關係沒有出處，覆核會留下你的理由。"));
  row.append(bh("p", "bi-meta", "AI 判定：" + (item.basis ? biBasisWord(item.basis) + "，" : "")
    + biWord(BI_STANCE, ((item.assessment || {}).history || [])[0]?.before?.stance
      || item.stance || "supports") + (reason ? "；理由：" + reason : "")));
  for (const past of (item.assessment || {}).history || []) {
    row.append(bh("p", "bi-meta", biTime(past.at) + " " + (past.author || past.by) + "："
      + biWord(BI_REVIEW_VERDICT, past.before.verdict) + " → "
      + biWord(BI_REVIEW_VERDICT, past.after.verdict)
      + "，" + biWord(BI_DIRECT, past.before.directness) + " → "
      + biWord(BI_DIRECT, past.after.directness) + "；" + past.reason));
  }
  if (!biReadOnly()) {
    row.append(bh("div", "bi-field-foot", biButton("覆核",
      () => biReviewForm(card, target, item, row), "bi-btn", "覆核「" + statement + "」")));
  }
  return row;
}

function biBasisWord(basis) { return (BI_BASIS[basis] || [basis])[0]; }

function biRenderReviews(body, card) {
  if (!biVaultOf(biDataset())) return;
  const {fields = [], evidence = [], relations = [], rejected_relations: gone = []} = bi.detail;
  body.append(bh("h4", "", "證據覆核"));
  const box = bh("div", "bi-fields"); box.id = "bi-reviews";
  const seen = new Set();
  for (const item of evidence) {
    const key = item.field + "/" + item.reference_id;
    if (seen.has(key)) continue;
    seen.add(key);
    const field = fields.find((f) => f.field === item.field);
    box.append(biReviewRow(card, {target: "card", field: item.field,
      reference_id: item.reference_id}, ((field || {}).label || item.field) + "："
      + biValue(field ? field.value : null), item));
  }
  for (const relation of [...relations, ...gone]) {
    const arrow = relation.direction === "out" ? " → " : " ← ";
    const statement = relation.type + arrow + relation.other_name + "（"
      + relation.status + "）";
    const target = {target: "relation", relation: relation.relation_id};
    const given = relation.references || [];
    for (const item of given) {
      box.append(biReviewRow(card, {...target, reference_id: item.reference_id},
        statement, {...item, assessment: item.assessment
          || {system: relation.note ? {reason: relation.note} : undefined}}));
    }
    if (!given.length) {
      box.append(biReviewRow(card, target, statement, {stance: "supports",
        assessment: {system: relation.note ? {reason: relation.note} : undefined}}));
    }
  }
  if (!box.children.length) box.append(bh("p", "bi-meta", "沒有可以覆核的出處。"));
  body.append(box);
}

function biReviewForm(card, target, item, row) {
  const old = row.querySelector(".bi-edit");
  if (old) { old.remove(); return; }
  const now = (item.assessment || {}).current || {};
  const form = bh("form", "bi-edit"); form.noValidate = true;
  const id = "bi-rev-" + (item.reference_id || target.relation) + "-";
  const label = (words, node) => { const tag = bh("label", "bi-label", words);
    tag.htmlFor = node.id; return tag; };
  const choose = (name, list, value) => {
    const node = document.createElement("select"); node.id = id + name; node.name = name;
    for (const [code, words] of list) {
      const option = document.createElement("option"); option.value = code;
      option.textContent = words; node.append(option);
    }
    node.value = value; return node;
  };
  const typed = (name, value) => {
    const node = document.createElement("input"); node.className = "bi-input";
    node.id = id + name; node.name = name; node.value = value || ""; return node;
  };
  const verdict = choose("verdict", BI_REVIEW_VERDICT, now.verdict || "pending");
  const stance = choose("stance", BI_STANCE, item.stance || "supports");
  const direct = choose("directness", BI_DIRECT, now.directness || "unknown");
  const same = choose("same_source", BI_SAME, now.same_source || "unknown");
  const scope = typed("scope", now.scope), date = typed("date", now.date);
  date.placeholder = "例如 2026-03-01；留空就不改";
  const reason = document.createElement("textarea"); reason.id = id + "reason";
  reason.name = "reason"; reason.required = true;
  reason.placeholder = "為什麼這樣判斷？";
  const error = bh("div", "bi-err"); error.setAttribute("role", "alert");
  const review = bh("div", "bi-note-review");
  const save = bh("button", "go", "預覽覆核"); save.type = "submit";
  form.append(label("覆核結果", verdict), verdict, label("立場", stance), stance,
    label("證據直接性", direct), direct, label("適用範圍", scope), scope,
    label("日期", date), date, label("同源資訊", same), same,
    label("理由（必填）", reason), reason, review, error,
    bh("div", "bi-actions", save, biButton("取消", () => form.remove())));
  const words = (state) => biWord(BI_REVIEW_VERDICT, state.verdict) + "、"
    + biWord(BI_STANCE, state.stance) + "、" + biWord(BI_DIRECT, state.directness) + "、"
    + biWord(BI_SAME, state.same_source) + (state.scope ? "、範圍 " + state.scope : "")
    + (state.date ? "、日期 " + state.date : "");
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); error.textContent = ""; review.replaceChildren();
    if (!reason.value.trim()) { error.textContent = "請寫下理由。"; reason.focus(); return; }
    save.disabled = true;
    try {
      const note = await biCall("/api/bi/evidence-reviews/preview", {dataset: biDataset(),
        ...target, card: card.id, base_version: card.version, verdict: verdict.value,
        stance: stance.value, directness: direct.value, same_source: same.value,
        scope: scope.value.trim(), date: date.value.trim(), reason: reason.value.trim()});
      const go = biButton("確認覆核", async () => {
        go.disabled = true;
        try {
          const done = await biCall("/api/bi/evidence-reviews/apply", {dataset: biDataset(),
            text: note.text, base_version: note.base_version});
          biNotice(true, done.unchanged ? "沒有變更：覆核結果和原本一樣。" : "已寫入覆核。");
          await biLoadDetail(false);
        } catch (failure) {
          error.textContent = "沒有寫入：" + failure.message; go.disabled = false;
        }
      }, "go");
      go.dataset.reviewConfirm = "true";
      review.append(bh("p", "", note.unchanged ? "覆核結果和原本一樣，確認後不會有變更。"
        : "原本：" + words(note.before) + "。改成：" + words(note.after)
          + "。覆核單會存成來源（" + note.folder + "）。"), go);
    } catch (failure) { error.textContent = "沒有寫入：" + failure.message; }
    finally { save.disabled = false; }
  });
  row.append(form); verdict.focus();
}

function biFieldRow(card, item) {
  const row = bh("div", "bi-field"); row.dataset.field = item.field;
  const head = bh("div", "bi-field-head", bh("strong", "", item.label || item.field));
  const cls = BI_CLASS[item.class];
  if (cls) head.append(biBadge(cls[0], cls[1]));
  if (item.source && item.source.kind === "human" && item.class !== "human") {
    head.append(biBadge("人工", "good"));
  }
  row.append(head, bh("div", "bi-field-value", biValue(item.value)));
  const foot = bh("div", "bi-field-foot", bh("span", "bi-meta", biSource(item.source)
    + (item.history ? " · 歷史 " + item.history + " 筆" : "")));
  if (!biReadOnly()) {  // a subscribed copy is read-only: no note form at all
    foot.append(biButton("提更正單", () => biEditField(card, item, row), "bi-btn",
      "提「" + (item.label || item.field) + "」的更正單"));
    if (biVaultOf(biDataset())) {
      foot.append(biButton("定案", () => biFinalField(card, item, row), "bi-btn",
        "定案「" + (item.label || item.field) + "」"));
    }
  }
  row.append(foot);
  return row;
}

function biFinalField(card, item, row) {
  // After a meeting: this value wins, and the old one, who and why stay in history.
  const old = row.querySelector(".bi-final");
  if (old) { old.remove(); return; }
  const spec = biSchemaField(card.entity_type, item.field) || {};
  const form = bh("form", "bi-edit bi-final"); form.noValidate = true;
  const value = document.createElement("input"); value.className = "bi-input";
  value.setAttribute("aria-label", "定案的值");
  value.value = Array.isArray(item.value) ? item.value.join("、")
    : item.value == null ? "" : String(item.value);
  const reason = document.createElement("input"); reason.className = "bi-input";
  reason.setAttribute("aria-label", "定案的理由");
  reason.placeholder = "理由（必填），例如哪一次會議決定的";
  const error = bh("div", "bi-err"); error.setAttribute("role", "alert");
  const go = bh("button", "go", "確認定案"); go.type = "submit";
  form.append(bh("label", "bi-label", "定案的值" + (spec.list ? "（多個值用「、」分隔）" : "")),
    value, bh("label", "bi-label", "理由"), reason, error, bh("div", "bi-actions", go));
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); error.replaceChildren(); go.disabled = true;
    try {
      const vault = biVaultOf(biDataset());
      const reply = await biCall("/api/bi/vaults/" + vault.id + "/finalize",
        {card: card.id, field: item.field, value: value.value, reason: reason.value});
      biNotice(true, "已定案「" + (item.label || item.field) + "」"
        + (reply.closed ? "，關閉 " + reply.closed + " 筆待審提議" : "")
        + "。commit 並 push 後大家才會看到。");
      await biOpenCard(card.id);
    } catch (failure) {
      error.append(bh("p", "bi-err", "沒有定案：" + failure.message + "。")); go.disabled = false;
    }
  });
  row.append(form);
}

function biEditField(card, item, row) {
  const old = row.querySelector(".bi-edit");
  if (old) { old.remove(); return; }
  const spec = biSchemaField(card.entity_type, item.field) || {};
  const form = bh("form", "bi-edit"); form.noValidate = true;
  const valueId = "bi-edit-" + item.field, reasonId = "bi-reason-" + item.field;
  const authorId = "bi-author-" + item.field;
  let input;
  if (spec.enum && spec.enum.length && !spec.list) {
    input = document.createElement("select");
    for (const choice of spec.enum) {
      const option = document.createElement("option"); option.value = choice;
      option.textContent = choice; input.append(option);
    }
    input.value = item.value == null ? "" : String(item.value);
  } else {
    input = document.createElement("input"); input.className = "bi-input";
    input.value = Array.isArray(item.value) ? item.value.join("、")
      : item.value == null ? "" : String(item.value);
  }
  input.id = valueId;
  const stateId = "bi-state-" + item.field;
  const state = document.createElement("select"); state.id = stateId;
  for (const [code, words] of [["", "寫新值"], ["not_applicable", "不適用"],
    ["pending_confirmation", "待確認"], ["confirmed_none", "確認沒有"]]) {
    const option = document.createElement("option"); option.value = code;
    option.textContent = words; state.append(option);
  }
  const reason = document.createElement("textarea"); reason.id = reasonId; reason.required = true;
  reason.placeholder = "為什麼改？例如：依據哪個訊號、客戶產品或商機";
  const author = document.createElement("input"); author.className = "bi-input";
  author.id = authorId;
  author.placeholder = "留空就用你的帳號";
  const error = bh("div", "bi-err"); error.setAttribute("role", "alert");
  const label = (text_, target) => { const node = bh("label", "bi-label", text_);
    node.htmlFor = target; return node; };
  const review = bh("div", "bi-note-review");
  const save = bh("button", "go", "預覽更正"); save.type = "submit";
  form.append(label("要更正成", stateId), state,
    label("新值" + (spec.list ? "（多個值用「、」或逗號分隔）" : ""), valueId), input,
    label("理由（必填）", reasonId), reason, label("作者", authorId), author, review, error,
    bh("div", "bi-actions", save, biButton("取消", () => form.remove())));
  const failed = (failure) => {
    if (failure.code === "stale_edit") {
      const payload = failure.payload || {};
      const stale = bh("div", "bi-stale",
        bh("p", "", "這張卡片已經被 " + (payload.by || "別人") + " 在 " + biTime(payload.at)
          + " 改過，目前的值是「" + biValue(payload.current) + "」。你的更正單還沒有寫入。"),
        biButton("重新載入卡片", () => biLoadDetail(true), "go"));
      stale.dataset.stale = "true";
      error.replaceChildren(stale);
    } else {
      error.textContent = "沒有寫入：" + failure.message;
    }
  };
  const confirmNote = async (note, button) => {
    error.textContent = ""; button.disabled = true; button.setAttribute("aria-busy", "true");
    try {
      const reply = await biCall("/api/bi/corrections/apply",
        {dataset: biDataset(), text: note.text, base_version: note.base_version});
      // The value it already had: no new version, nothing in the history.
      biNotice(true, reply.unchanged
        ? "沒有變更：「" + (item.label || item.field) + "」本來就是這個值（版本 "
          + reply.version + "）。"
        : "已寫入更正單「" + (item.label || item.field) + "」（版本 " + reply.version + "）。");
      await biLoadDetail(false);
      biLoadCards();
    } catch (failure) { failed(failure); }
    finally { button.disabled = false; button.removeAttribute("aria-busy"); }
  };
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); error.textContent = ""; review.replaceChildren();
    if (!reason.value.trim()) { error.textContent = "請寫下理由。"; reason.focus(); return; }
    let value = input.value.trim();
    if (spec.list) {
      value = value ? value.split(/[、,，;；]/).map((v) => v.trim()).filter(Boolean) : [];
    }
    else if ((spec.type === "int" || spec.type === "float") && value !== ""
      && !isNaN(Number(value))) value = Number(value);
    save.disabled = true; save.setAttribute("aria-busy", "true");
    try {
      const note = await biCall("/api/bi/corrections/preview",
        {dataset: biDataset(), card: card.id, field: item.field,
         ...(state.value ? {state: state.value} : {value}),
         base_version: card.version, reason: reason.value.trim(), author: author.value.trim()});
      const go = biButton("確認寫入", () => confirmNote(note, go), "go");
      go.dataset.noteConfirm = "true";
      review.append(bh("p", "", note.unchanged
        ? "「" + (note.label || note.field) + "」本來就是這個值，確認後不會有變更。"
        : "「" + (note.label || note.field) + "」：「" + biValue(note.current) + "」→「"
          + (note.state_label || biValue(note.value)) + "」。更正單會存成來源（"
          + note.folder + "），確認後寫入。"), go);
    } catch (failure) { failed(failure); }
    finally { save.disabled = false; save.removeAttribute("aria-busy"); }
  });
  row.append(form); input.focus();
}

async function biLoadHistory() {
  const id = bi.cardId;
  if (!el("bi-status-history")) return;
  biStatus("bi-status-history", "loading", "載入中…");
  let reply;
  try {
    reply = await biCall("/api/bi/cards/" + encodeURIComponent(id) + "/history?dataset="
      + encodeURIComponent(biDataset()));
  } catch (failure) {
    if (el("bi-status-history")) {
      biStatus("bi-status-history", "error", "歷史載入失敗：" + failure.message + "。",
        biLoadHistory);
    }
    return;
  }
  if (bi.cardId !== id || !el("bi-history")) return;
  biStatus("bi-status-history", "");
  const box = el("bi-history"); box.replaceChildren();
  const items = reply.history || [];
  if (!items.length) { box.append(bh("p", "bi-meta", "還沒有變更紀錄。")); return; }
  const labels = Object.fromEntries((bi.detail.fields || []).map((f) => [f.field, f.label]));
  const ul = bh("ul", "bi-list");
  for (const item of items) {
    ul.append(bh("li", "", bh("strong", "", labels[item.field] || item.field), text("："),
      bh("span", "", biValue(item.old)), bh("span", "bi-arrow", "→"),
      bh("span", "", biValue(item.new)), bh("div", "bi-meta", biTime(item.at) + " · "
        + (item.by || "—") + " · " + biSource(item.source ? {...item.source, at: null} : null)
        + (item.reason ? " · 理由：" + item.reason : "")),
      ...(item.old_evidence || []).map((e) => bh("div", "bi-meta bi-old-evidence", "舊值的出處："
        + (e.source_name || "") + (e.excerpt ? "「" + e.excerpt + "」" : "")))));
  }
  box.append(ul);
}

// The bar's card counts after a write (a commit or its undo).
async function biRefreshCounts() {
  try {
    const reply = await biCall("/api/bi/datasets");
    bi.datasets = reply.datasets || []; biRenderBar();
  } catch (failure) { biNotice(false, "卡片數沒有更新：" + failure.message); }
}

// -- sharing through the Shared Platform (BI dataset sharing slice 1) ----------
// An own dataset can be published as an immutable version; a subscribed copy
// is read-only (no import, edit or demo load) and says whose version it is.
const BI_SUB_STATUS = {
  update_available: ["有新版本", "accent"], current: ["已是最新", "good"],
  stopped_no_access: ["已停止更新（無權限）", "warn"], offline: ["無法連線", "dim"]};
const BI_PUB_ERRORS = {
  version_superseded: "平台上已有比你這份更新的版本，請先更新後再發佈。",
  artifact_too_large: "資料集太大，超過平台的上限。",
  publisher_not_authorized: "你沒有發佈這個名稱的權限；請名稱的負責人把你加為共同維護者。",
  platform_unreachable: "Shared Platform 沒有回應，請稍後再試（資料沒有送出）。",
  publishing_not_configured: "這台電腦還沒設定 Shared Platform：到 Settings → Shared platform"
    + " 設定 Member Portal 與 Personal Agent code。",
  dataset_read_only: "這是訂閱的資料集，不能發佈。",
  organization_unconfirmed: "開放給全公司需要先勾選確認。",
  note_required: "請寫版本說明。"};

function biCurrent() { return bi.datasets.find((item) => item.name === biDataset()) || null; }
function biReadOnly() { const info = biCurrent(); return !!(info && info.read_only); }
function biSubOf(name) {
  return bi.subs.find((item) => item.dataset === name || item.name === name) || null;
}
function biSubField(info, sub, key) {
  const from = [sub, info && info.subscription, info && info.source, info];
  for (const item of from) if (item && item[key] != null && item[key] !== "") return item[key];
  return null;
}
function biSubLabel(info, sub) {
  const name = (sub && sub.name) || biSubField(info, sub, "identity") || (info && info.name);
  const version = biSubField(info, sub, "version");
  return name + (version ? " v" + version : "");
}

// -- 建立與匯入 (BI ingest phases 1-3, owner 2026-10-27) ---------------------
// Six steps sharing the Wiki's stepper: sources, schema (versions, drafts,
// upgrade), method and trial run, review of every candidate with its evidence,
// the person's 「確認匯入」, and the result. Trial runs and review write only the
// dataset's staging store; only the commit writes cards.
const BI_STAGES = ["source", "schema", "method", "review", "commit", "result", "test"];
// Step 2 of three (Schema 與 Ingest) holds these parts, shown in `#bi-substeps`.
const BI_INGEST = ["schema", "method", "review", "commit", "result"];
const BI_BASIS = {fact: ["有出處", "good"], inference: ["推論", "warn"],
  unknown: ["無出處", "dim"], human: ["人工", "dim"]};
const BI_RUN_ACTION = {create: "新建", update: "更新", unchanged: "不變", skip: "略過"};
const BI_DECISION = {pending: ["待決定", "dim"], accepted: ["已接受", "good"],
  rejected: ["已拒絕", "warn"]};
bi.build = {stage: "source", sources: [], sourceId: null, run: null, candidates: [],
  candidateId: null, drafts: [], draft: null, upgrade: null};

function biBuildKey() { return "bi-build-" + biDataset(); }

function biBuildSave() {
  const keep = {stage: bi.build.stage, sourceId: bi.build.sourceId, chosen: bi.build.chosen,
    runId: bi.build.run ? bi.build.run.id : bi.build.runLoading || null,
    candidateId: bi.build.candidateId};
  try { localStorage.setItem(biBuildKey(), JSON.stringify(keep)); } catch (e) { /* */ }
}

function biBuildStored() {
  try { return JSON.parse(localStorage.getItem(biBuildKey()) || "{}") || {}; }
  catch (e) { return {}; }
}

function biBuildAllowed() {
  if (biReadOnly()) {
    return {source: true, schema: false, method: false, review: false, commit: false,
      result: false, test: false};
  }
  // Ingest belongs to a working domain; an old source in no home has none to choose.
  const chosen = (bi.build.sources || []).find((s) => s.id === bi.build.sourceId);
  const run = bi.build.run, has = !!bi.build.sourceId
    && !(biOverview() && chosen && biFolderHome(chosen.folder));
  const open = run && run.kind === "ingest" && ["review", "partial"].includes(run.status);
  const accepted = open && run.summary && run.summary.accepted > 0;
  // A run may wait for review with no source chosen, one started through the API; and
  // proposals are decided in the same step.
  return {source: true, schema: true, method: has,
    review: has || !!run || (bi.build.waiting || []).length > 0
      || (bi.proposals || []).length > 0 || (bi.proposalsDecided || []).length > 0,
    commit: !!accepted && !bi.build.accepting && !bi.build.saving,
    result: !!(run && run.status === "committed"),
    test: true};
}

function biBuildStepper(stage, allowed) {
  const ingest = BI_INGEST.includes(stage);
  stepperSet(el("bi-stepper"), ingest ? "ingest" : stage,
    {source: true, ingest: allowed.schema, test: allowed.test}, "這是唯讀的副本");
  stepperSet(el("bi-substeps"), stage, allowed, "先完成前面的步驟");
  el("bi-substeps").hidden = !ingest;
}

function biBuildSteps() { biBuildStepper(bi.build.stage, biBuildAllowed()); }

async function biToVersion() {
  // 版本 sits in step 3, under the tests: open it there, clear of the sticky row and steps.
  if (bi.view !== "build") await biJump("build");
  biBuildStage("test", false);
  // What loads after this moves it: the Dashboard, tests and analyses above it, the share
  // step inside it, the sticky row and steps over it. Each arrives in its own time (a slow
  // computer: after any fixed wait), so it is placed again whenever one of them changes
  // size, until the person scrolls, clicks or types somewhere else.
  bi.keepVersion = true;
  biKeepVersion();
  if (!el("bi-b-ver").hidden) el("bi-b-ver-purpose").focus({preventScroll: true});
}

function biKeepVersion() {
  if (!bi.keepVersion) return;
  const box = el("bi-b-ver");
  if (bi.view !== "build" || bi.build.stage !== "test") { bi.keepVersion = false; return; }
  if (box.hidden) return;
  // Clear of the top row while it sticks (not on a phone): its own height, as it is now.
  const row = el("bi-top-row");
  box.style.setProperty("--bi-top-h",
    getComputedStyle(row).position === "sticky" ? row.offsetHeight + "px" : "0px");
  box.scrollIntoView({block: "start"});
}

const biVersionMoved = new ResizeObserver(() => biKeepVersion());
for (const moves of [el("bi-top-row"), el("bi-build-steps"),
  document.querySelector('#bi-view-build .kp-stage[data-stage="test"]')]) {
  biVersionMoved.observe(moves);
}
for (const type of ["wheel", "touchstart", "pointerdown", "keydown"]) {
  window.addEventListener(type, (event) => {
    // Typing the commit's purpose is being where it was opened.
    if (type === "keydown" && event.target && event.target.id === "bi-b-ver-purpose") return;
    bi.keepVersion = false;
  }, {capture: true, passive: true});
}

function biBuildStage(name, focus = true) {
  bi.build.moves = (bi.build.moves || 0) + 1;
  const allowed = biBuildAllowed();
  // Step 2 opens where it was left, or at its first part.
  if (name === "ingest") name = allowed[bi.build.ingestAt] ? bi.build.ingestAt : "schema";
  const stage = BI_STAGES.includes(name) && allowed[name] ? name : "source";
  bi.build.stage = stage;
  if (BI_INGEST.includes(stage)) bi.build.ingestAt = stage;
  biBuildStepper(stage, allowed);
  for (const section of document.querySelectorAll("#bi-view-build .kp-stage")) {
    section.hidden = section.dataset.stage !== stage;
  }
  biBuildSave();
  biDashHome();
  if (stage === "schema") biBuildSchema();
  if (stage === "method") biBuildMethodStage();
  if (stage === "review") biBuildReviewStage();
  if (stage === "commit") biBuildSummary();
  if (stage === "result") biBuildResult();
  if (stage === "test" && biVaultOf(biDataset())) {
    // What steps 1 and 2 changed (cards written, skills, schema) waits to be committed here.
    // After the Dashboard: on market-intel the ten reads this starts took it from 4 s to 13 s,
    // and the tables they refresh are already drawn.
    const vaultId = biVaultOf(biDataset()).id;
    Promise.resolve(bi.dashLoad).finally(() => call("/api/bi/vaults/" + vaultId + "/status")
      .then((state) => { if (vaultId === (biVaultOf(biDataset()) || {}).id) biVaultState(state); })
      .catch((failure) => biNotice(false, "讀不到知識庫的狀態：" + failure.message)));
  }
  if (focus) {
    const title = document.querySelector('#bi-view-build .kp-stage[data-stage="' + stage
      + '"] .kp-stage-title');
    if (title) title.focus({preventScroll: false});
  }
}

for (const button of document.querySelectorAll("#bi-build-steps [data-stage]")) {
  button.addEventListener("click", () => biBuildStage(button.dataset.stage));
}
for (const button of document.querySelectorAll("#bi-view-build [data-bi-next]")) {
  if (button.id === "bi-b-next4") continue;  // waits for the decisions being saved
  button.addEventListener("click", () => biBuildStage(button.dataset.biNext));
}
el("bi-b-next4").addEventListener("click", async () => {
  // A quick hand presses as soon as 「全部套用」 is pressed: the press is kept, and goes on
  // when the last decision is saved.
  if (bi.build.accepting || bi.build.saving) {
    const button = el("bi-b-next4");
    button.textContent = "儲存完就前往確認寫入…";
    while (bi.build.accepting || bi.build.saving) {
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
    button.textContent = "下一步：確認寫入"; biNext4();
    // Stopped, or nothing accepted after all: the notice says why, and the step stays.
    if (!biBuildAllowed().commit) return;
  }
  biBuildStage("commit");
});
for (const [id, view] of [["bi-b-to-cards", "cards"],
  ["bi-b-ro-dash", "dashboard"], ["bi-b-ro-cards", "cards"]]) {
  el(id).addEventListener("click", () => biJump(view));
}

function biBuildReadOnly() {
  const readOnly = biReadOnly();
  el("bi-b-src-input").hidden = readOnly; el("bi-b-adv-source").hidden = readOnly;
  el("bi-b-ro-links").hidden = !readOnly;
  el("bi-b-src-split").hidden = readOnly;  // a copy has no sources here
  el("bi-b-next1").parentNode.hidden = readOnly;
  return readOnly;
}

function biBuildFollowDataset() {
  // The select changes a request before `biBuildLoad` runs. From that moment nothing of the
  // old dataset may be read or saved as this one's: the old table and selection looked
  // chosen, and the load then emptied them with the page already moving on.
  if (bi.build.dataset === biDataset()) return;
  bi.build.dataset = biDataset();
  const stored = biBuildStored();
  bi.build.sourceId = stored.sourceId || null; bi.build.runLoading = stored.runId || null;
  bi.build.chosen = stored.chosen || (stored.sourceId ? [stored.sourceId] : []);
  bi.build.sources = []; bi.build.run = null; bi.build.candidates = [];
  bi.build.candidateId = stored.candidateId || null; bi.build.waiting = []; bi.build.md = null;
  bi.build.cards = null; bi.build.peek = null;
  el("bi-b-sources").tBodies[0].replaceChildren();
  el("bi-b-md").hidden = true; el("bi-b-md-empty").hidden = false;
  // Another dataset's working domain means nothing here, not even for a moment.
  el("bi-b-src-folder").replaceChildren(); bi.build.homes = []; bi.build.scopeSet = null;
  el("bi-b-src-folder-box").hidden = !biVaultOf(biDataset()) || biReadOnly();
  biBuildSteps();
}

async function biBuildLoad() {
  biBuildFollowDataset();
  if (biBuildReadOnly()) {
    // A subscribed copy is only read: here it is the way to another dataset.
    el("bi-b-v-state").replaceChildren(); delete el("bi-b-v-state").dataset.vault;
    el("bi-b-target").textContent = "";
    biStatus("bi-status-build", "");
    el("bi-b-sources").tBodies[0].replaceChildren();
    bi.build.sourceId = null; el("bi-b-next1").disabled = true;
    biBuildStage("source", false);
    return;
  }
  const stored = biBuildStored();
  const load = bi.build.load = (bi.build.load || 0) + 1, dataset = biDataset();
  // The step comes back at once where it needs no source; its data follows.
  if (["schema", "test"].includes(stored.stage) && bi.build.stage !== stored.stage) {
    biBuildStage(stored.stage, false);
  }
  const moves = bi.build.moves;
  const schema = bi.schema || {};
  el("bi-b-target").textContent = "寫入目的地：資料集「" + biDataset() + "」・schema "
    + (schema.ref || schema.schema_id || "—") + "。";
  // After the sources: on market-intel the dozen reads this starts took them from 5 s to 12 s,
  // and they serve the steps not showing yet.
  let vaultAsked = false;
  const askVault = () => {
    if (vaultAsked || load !== bi.build.load) return;
    vaultAsked = true;
    // Asked late, the person may be on another tab by now, whose notice this must not replace.
    biBuildVault().catch((failure) => {
      if (bi.view === "build") biNotice(false, "知識庫狀態沒有載入：" + failure.message);
    });
  };
  const select = el("bi-b-entity"), keep = select.value;
  select.replaceChildren(bh("option", "", "自動判斷"));
  select.firstChild.value = "";
  for (const type of (schema.types || [])) {
    const option = bh("option", "", (type.label || type.name) + "（" + type.name + "）");
    option.value = type.name; select.append(option);
  }
  select.value = keep;
  biStatus("bi-status-build", "loading", "載入中…");
  try {
    await biBuildSources();
    askVault();
    if (stored.runId) await biBuildFetchRun(stored.runId);
    bi.build.runLoading = null;
    await biBuildRuns();
    biStatus("bi-status-build", "");
  } catch (failure) {
    askVault();
    biStatus("bi-status-build", "error", "載入失敗：" + failure.message + "。", biBuildLoad);
  }
  // A newer load ends this. So does a dataset chosen since, whose load has not started yet:
  // the step below would be saved as that dataset's.
  if (load !== bi.build.load || dataset !== biDataset()) return;
  // A step the person opened meanwhile stays open.
  if (moves === bi.build.moves) biBuildStage(stored.stage || "source", false);
  else if (bi.build.stage === "review") biBuildRenderRun();
  else biBuildSteps();
}

// -- step 1: the knowledge base (BI vaults V4, docs/phases/BI_VAULT.md §3, §7.1) --
// A vault is the dataset `vault-<id>`, kept in a synced shared folder; every
// write becomes one change file of this author. Opening the step syncs it, so
// what others wrote is shown; status names conflicts and unreadable files.
const BI_VAULT_PARENT = "放在哪個資料夾底下（SharePoint／OneDrive 同步的資料夾）";
const BI_VAULT_MODES = {
  new: ["建立共用知識庫（vault）", "建立", BI_VAULT_PARENT],
  join: ["加入既有的 vault", "加入", "vault 資料夾（裡面有 vault.json）"],
  convert: ["把這個資料集轉成 vault", "轉換", BI_VAULT_PARENT],
};

function biVaultOf(name) {
  return (bi.vaults || []).find((v) => v.dataset === name) || null;
}

async function biBuildVault() {
  if (bi.ai && bi.ai.dataset !== biDataset()) biAiClose();
  // Newest call only: a reload for the dataset shown before must not paint over this one.
  const seq = bi.vaultSeq = (bi.vaultSeq || 0) + 1;
  const reply = await call("/api/bi/vaults");
  if (seq !== bi.vaultSeq) return;
  bi.vaults = reply.vaults || [];
  const vault = biVaultOf(biDataset());
  el("bi-b-v-sync").hidden = !vault;
  el("bi-b-v-convert").hidden = Boolean(vault) || !bi.datasets.some((d) => d.name === biDataset());
  // The same vault's line stays until its new state replaces it: emptied in between, its
  // links to 版本 would vanish under a press made just then. Another's goes at once.
  const box = el("bi-b-v-state");
  if (!vault || box.dataset.vault !== vault.id) { box.replaceChildren(); delete box.dataset.vault; }
  el("bi-b-ver-none").hidden = Boolean(vault);
  if (!vault) {
    el("bi-b-v-info").replaceChildren();
    el("bi-b-ver").hidden = true; el("bi-b-skills").hidden = true;
    el("bi-b-bench").hidden = true; el("bi-b-an").hidden = true;
    box.append(bh("p", "bi-meta", "只在這台電腦。"));
    return;
  }
  // Show the local copy now; a sync that brought something updates the page after it.
  const state = await call("/api/bi/vaults/" + vault.id + "/status");
  if (seq !== bi.vaultSeq) return;
  biVaultState(state);
  askableLoad().catch((failure) => { el("bi-b-askable").textContent = failure.message; });
  const synced = biCall("/api/bi/vaults/" + vault.id + "/sync", {}).then(async (reply) => {
    if (seq !== bi.vaultSeq || !(reply.sync || {}).moved) return;
    const newer = await call("/api/bi/vaults/" + vault.id + "/status");
    // Redrawing resets what the person has open, so only for what came from outside:
    // what they did here is already drawn by the action that did it.
    const came = reply.sync.applied || reply.sync.rebuilt
      || JSON.stringify(newer.reads) !== JSON.stringify(state.reads);
    if (seq !== bi.vaultSeq || !came) return;
    biVaultState(newer);
    bi.loaded = {}; biRefreshCounts();
  }).catch((failure) => {
    if (seq === bi.vaultSeq) box.append(bh("p", "bi-warn", "沒有同步：" + failure.message + "。"));
  });
  // Says the panel has stopped changing by itself.
  Promise.allSettled([synced, bi.analysesLoad]).then(() => {
    if (seq === bi.vaultSeq) box.dataset.settled = String(seq);
  });
}

async function biProposals() {
  // Every pending proposal of the working copy, so a person can settle them in one place.
  const dataset = biDataset();
  // Newest call only: each decision refreshes the list, and a list read before the next
  // decision, arriving after it, would show that one as pending again beside its mark.
  const seq = bi.proposalsSeq = (bi.proposalsSeq || 0) + 1;
  const reply = await call("/api/bi/proposals?dataset=" + encodeURIComponent(dataset));
  if (dataset !== biDataset() || seq !== bi.proposalsSeq) return;
  // What was decided here is not pending, whenever the list was read.
  const decided = bi.proposalsFor === dataset
    ? new Set((bi.proposalsDecided || []).map((done) => done.item.id)) : new Set();
  bi.proposals = (reply.proposals || []).filter((item) => !decided.has(item.id));
  biBuildSteps();
  // What was decided here stays on the list, with its mark, until the page is left.
  if (bi.proposalsFor !== dataset) { bi.proposalsFor = dataset; bi.proposalsDecided = []; }
  el("bi-b-props").hidden = !bi.proposals.length && !bi.proposalsDecided.length;
  el("bi-b-props-h").textContent = "待審提案（" + bi.proposals.length + " 筆）";
  el("bi-b-props-bulk").hidden = !bi.proposals.length;
  el("bi-b-props-jump").hidden = !bi.proposals.length;
  el("bi-b-props-jump").textContent = "待審提案 " + bi.proposals.length + " 筆";
  el("bi-b-props-confirm").replaceChildren();
  const fill = (id, values, label) => {
    const pick = el(id), kept = pick.value;
    pick.replaceChildren(bh("option", "", "全部"));
    pick.options[0].value = "";
    for (const value of [...new Set(values)].sort()) {
      const option = bh("option", "", label(value)); option.value = value; pick.append(option);
    }
    pick.value = [...pick.options].some((o) => o.value === kept) ? kept : "";
  };
  const labels = Object.fromEntries(bi.proposals.map((p) => [p.field, p.label]));
  fill("bi-b-props-field", bi.proposals.map((p) => p.field), (f) => labels[f] || f);
  fill("bi-b-props-origin", bi.proposals.map((p) => p.origin), (o) => o);
  biProposalsShown();
}

function biProposalsShown() {
  // Which proposals the filters show, and which of them 「全部」 would decide: a protected
  // field (`confidence`, `evidence_grade`) only when the filter names it.
  const field = el("bi-b-props-field").value, origin = el("bi-b-props-origin").value;
  const shown = (bi.proposals || []).filter((p) => (!field || p.field === field)
    && (!origin || p.origin === origin));
  const chosen = shown.filter((p) => p.field === field || !p.protected);
  el("bi-b-props-confirm").replaceChildren();
  el("bi-b-props-accept").textContent = "接受顯示的全部（" + chosen.length + " 筆）";
  el("bi-b-props-reject").textContent = "否決顯示的全部（" + chosen.length + " 筆）";
  el("bi-b-props-accept").disabled = el("bi-b-props-reject").disabled = !chosen.length;
  if (shown.length && !chosen.length) {
    el("bi-b-props-confirm").append(bh("p", "bi-meta", "這 " + shown.length
      + " 筆都是 confidence 或 evidence_grade：一次決定前要先在「欄位」選定其中一個，"
      + "也可以逐筆決定。"));
  }
  // A reason being written survives the redraw: a refresh after another decision (or a
  // sync) lands while the person types the next one, and their words must not go with it.
  const typed = {};
  for (const input of el("bi-b-props-list").querySelectorAll("li[data-proposal] > .bi-actions"
    + " > input")) {
    const id = input.closest("li").dataset.proposal;
    if (input.value) typed[id] = {value: input.value, focused: input === document.activeElement};
  }
  const rows = shown.map((item) => biProposalRow(item, biDataset(), typed[item.id]));
  for (const done of bi.proposalsDecided || []) {
    rows.splice(Math.min(done.at, rows.length), 0, biProposalDone(done));
  }
  el("bi-b-props-list").replaceChildren(...rows);
  for (const row of rows) {
    const kept = typed[row.dataset.proposal], input = row.querySelector(".bi-actions > input");
    if (kept && kept.focused && input) input.focus({preventScroll: true});
  }
  return {field, origin, shown, chosen};
}

function biProposalsAll(action) {
  // One reason, and a second click on what will happen and how many.
  const {field, origin, shown, chosen} = biProposalsShown();
  const box = el("bi-b-props-confirm"), reason = el("bi-b-props-reason");
  if (!reason.value.trim()) {
    box.append(bh("p", "bi-err", "請寫下理由。")); reason.focus(); return;
  }
  const left = shown.length - chosen.length;
  const losing = chosen.filter((item) => biProposalLoss(item)).length;
  const bare = chosen.filter((item) => !(item.evidence || []).length).length;
  const yes = biButton("確定" + (action === "accept" ? "接受 " : "否決 ") + chosen.length + " 筆",
    async () => {
      yes.disabled = true;
      try {
        const done = await biCall("/api/bi/proposals/decide", {dataset: biDataset(), action,
          reason: reason.value.trim(), field: field || null, origin: origin || null,
          count: chosen.length});
        reason.value = "";
        if (!done.superseded) {
          const review = action === "accept" ? "accepted" : "rejected";
          bi.proposalsDecided.push(...chosen.map((item) => ({item, review,
            at: (bi.proposalsDecided || []).length})));
        }
        biNotice(true, "已決定 " + done.decided + " 筆提案；要 commit 才會寫進知識庫。");
        await biBuildVault();
      } catch (failure) {
        box.replaceChildren(bh("p", "bi-err", failure.message + "。"));
        await biProposals();
      }
    }, "go");
  box.append(bh("p", "bi-warn", "將" + (action === "accept" ? "接受 " : "否決 ") + chosen.length
    + " 筆提案" + (left ? "；另有 " + left + " 筆 confidence 或 evidence_grade 不包含在內，"
      + "要先篩選到那個欄位" : "") + "。"
    + (action === "accept" && losing ? "其中 " + losing + " 筆會用短很多的文字取代目前的長文。"
      : "")
    + (action === "accept" && bare ? "其中 " + bare + " 筆沒有出處，接受後那些欄位就沒有出處。"
      : "")),
  yes,
  biButton("取消", () => box.replaceChildren(), "bi-btn"));
}

el("bi-b-props-jump").addEventListener("click",
  () => el("bi-b-props").scrollIntoView({block: "start"}));
el("bi-b-props-field").addEventListener("change", biProposalsShown);
el("bi-b-props-origin").addEventListener("change", biProposalsShown);
el("bi-b-props-accept").addEventListener("click", () => biProposalsAll("accept"));
el("bi-b-props-reject").addEventListener("click", () => biProposalsAll("reject"));

function biProposalLoss(item) {
  // A long value about to give way to a much shorter one: how a sourced text gets lost.
  const old = typeof item.current === "string" ? item.current.length : 0;
  const now = typeof item.value === "string" ? item.value.length : 0;
  return old >= 100 && now < old / 2 ? {old, now} : null;
}

function biProposalSides(item) {
  const side = (value) => bh("td", "", bh("div", "", value === null ? "（空）" : biValue(value)));
  return bh("table", "bi-table bi-prop-sides", bh("thead", "", bh("tr", "",
    bh("th", "", "目前的值"), bh("th", "", "提議的值"))), bh("tbody", "", bh("tr", "",
    side(item.current), side(item.value))));
}

function biProposalDone(done) {
  const item = done.item;
  const box = bh("li", "", bh("strong", "", item.card_name),
    bh("span", "bi-meta", " " + biTypeLabel(item.entity_type) + "・" + item.label + " "),
    biDecisionMark(done.review),
    bh("div", "bi-meta", done.review === "accepted" ? "現在的值：" + biValue(item.value)
      : "值沒有改動：" + biValue(item.current)),
    done.review === "accepted" ? bh("div", "bi-meta", "要 commit 才會寫進知識庫。") : "");
  box.dataset.proposal = item.id;
  return box;
}

function biProposalRow(item, dataset, typed) {
  const reason = bh("input", "bi-input");
  if (typed) reason.value = typed.value;
  reason.placeholder = item.needs_reason ? "理由（這是判斷欄位，必填）" : "理由（否決時必填）";
  reason.setAttribute("aria-label", "理由：" + item.card_name + " 的 " + item.label);
  const error = bh("div", "bi-err");
  const loss = biProposalLoss(item);
  const decide = async (action) => {
    error.textContent = "";
    if (!reason.value.trim() && (action === "reject" || item.needs_reason)) {
      error.textContent = "請寫下理由。"; reason.focus(); return;
    }
    // An answer at once, in the row pressed: the page's notice can be far above it.
    actions.replaceChildren(bh("span", "bi-meta", "儲存中…"));
    try {
      await biCall("/api/bi/cards/" + encodeURIComponent(item.card_id) + "/proposals/" + item.id,
        {dataset, action, base_version: item.version, reason: reason.value.trim()});
    } catch (failure) {
      error.textContent = failure.message + "。"; actions.replaceChildren(...buttons); return;
    }
    const list = el("bi-b-props-list");
    const at = [...list.children].indexOf(box);
    const done = {item, at: Math.max(at, 0),
      review: action === "accept" ? "accepted" : "rejected"};
    (bi.proposalsDecided = bi.proposalsDecided || []).push(done);
    box.replaceWith(biProposalDone(done));
    biNotice(true, (action === "accept" ? "已接受" : "已否決") + "「" + item.card_name + "」的"
      + item.label + "；要 commit 才會寫進知識庫。");
    await biBuildVault();
  };
  const accept = () => {
    if (!loss) return decide("accept");
    // A second press that names the loss.
    actions.replaceChildren(bh("span", "bi-warn", "用 " + loss.now + " 字取代目前的 " + loss.old
      + " 字？"), biButton("確定取代", () => decide("accept"), "go"),
    biButton("取消", () => actions.replaceChildren(...buttons), "bi-btn"));
  };
  const buttons = [reason, biButton("接受", accept, "bi-btn"),
    biButton("否決", () => decide("reject"), "bi-btn")];
  const actions = bh("div", "bi-actions", ...buttons);
  const said = (label, rows) => (rows || []).map((e) => bh("div", "bi-meta",
    label + (e.source_name || "") + (e.excerpt ? "「" + (e.excerpt.length > 120
      ? e.excerpt.slice(0, 120) + "…" : e.excerpt) + "」" : "")));
  const cited = (item.current_evidence || []).length;
  const facts = [...said("提議的依據：", item.evidence),
    ...said("目前的值依據：", item.current_evidence)];
  const box = bh("li", "", bh("strong", "", item.card_name),
    bh("span", "bi-meta", " " + biTypeLabel(item.entity_type) + "・" + item.label),
    biProposalSides(item),
    loss ? bh("p", "bi-warn bi-prop-loss", "接受會用 " + loss.now + " 字取代目前的 " + loss.old
      + " 字。") : "",
    (item.evidence || []).length ? bh("p", "bi-meta",
      "接受後這個欄位算人工的值，提議的出處成為它的出處。"
      + (cited ? "目前值的出處移到卡片的歷史，和舊值放在一起。" : ""))
      : bh("p", "bi-warn bi-prop-bare", "這筆提議沒有出處：接受後這個欄位就沒有出處。"
        + (cited ? "目前值的出處移到卡片的歷史，和舊值放在一起。" : "")),
    bh("div", "bi-meta", "提議來源：" + (item.source.ref || item.source.kind)),
    ...facts, actions, error);
  box.dataset.proposal = item.id;
  return box;
}

function biVaultState(state) {
  const box = el("bi-b-v-state"), v = state.vault || {};
  box.replaceChildren(); box.dataset.vault = v.id || "";
  bi.verSchemaConflicts = state.schema_conflicts || [];
  if (v.id) biVerConflictList(v.id);
  // Whatever moved the vault (a sync, an import, a commit) may have moved its proposals.
  biProposals().catch((failure) => { el("bi-b-props-list").textContent = failure.message; });
  const open = (state.conflicts || []).filter((c) => c.open).length;
  el("bi-b-v-info").replaceChildren(
    bh("p", "", bh("strong", "", v.title || v.id), "・" + (v.purpose || "（沒有寫目的）")),
    bh("p", "bi-meta", "共用資料夾：" + v.path + "・你的作者名稱：" + v.author));
  if (!state.reachable) {
    box.append(bh("p", "bi-warn", "現在讀不到共用資料夾（OneDrive 沒有同步或路徑不對）："
      + "可以看卡片，但不能寫入。"));
    el("bi-b-ver").hidden = true; el("bi-b-skills").hidden = true;
    el("bi-b-bench").hidden = true; el("bi-b-an").hidden = true;
    return;
  }
  const count = bh("span", ""); count.id = "bi-b-v-count";
  // Something to commit or push opens 版本 from any tab, not only after a run (acceptance F12).
  const toVersion = (words, n) => n
    ? biButton(words + n + " 個", biToVersion, "bi-link",
      words + n + " 個：到「版本」commit 或 push")
    : words + n + " 個";
  box.append(bh("p", "bi-meta", count, "・別人 push 了還沒套用的 " + state.behind + " 個・",
    toVersion("你還沒 push 的 commit ", state.ahead), "・",
    toVersion("還沒 commit 的改動 ", state.uncommitted),
    "・上次同步 " + (state.last_sync ? biTime(state.last_sync) : "—")));
  const shown = bi.datasets.find((item) => item.name === biDataset());
  if (shown) shown.cards = state.cards;
  biRenderCounts();
  if ((state.waiting || []).length) {
    box.append(bh("p", "bi-warn", state.waiting.length + " 個 commit 在等 OneDrive 把檔案同步完"
      + "（同步完會自動套用）。"));
  }
  if (open) {
    box.append(bh("p", "bi-warn", "衝突 " + open + " 筆待決定：兩個人同時改了同一個欄位，"
      + "後到的變成卡片上的待審提議，請到卡片上決定。"));
  }
  if ((state.bad || []).length) {
    box.append(bh("p", "bi-warn", "有 " + state.bad.length + " 個檔案讀不懂，已略過："
      + state.bad.map((b) => b.file || b).slice(0, 5).join("、")));
  }
  const reads = state.reads || {};
  el("bi-b-ver-reads").textContent = reads.tag
    ? "Agent 讀的是發佈版本「" + reads.tag + "」；之後 push 的內容要再發佈，Agent 才會讀到。"
    : "還沒有發佈過：Agent 讀的是大家已 push 的最新內容（不含你還沒 push 的改動）。";
  el("bi-b-ver").hidden = false; el("bi-b-skills").hidden = false;
  bi.verVault = v.id;
  bi.analysesLoad = biAnalyses(v.id)
    .catch((failure) => biNotice(false, "讀不到分析：" + failure.message));
  biBench(v.id).catch((failure) => biNotice(false, "讀不到測試：" + failure.message));
  biVersions(v.id).catch((failure) => biNotice(false, "讀不到版本資訊：" + failure.message));
}

// -- 題目與擷取測試 (BI T1, docs/phases/BI_TEST_AND_TOOLS.md §3) ------------------------
function biBenchGrade(side) {
  const g = side.grade || {};
  if (!side.ok) return "沒有回答";
  if (g.passed) return "通過";
  const why = [];
  if ((g.missing || []).length) why.push("沒提到 " + g.missing.join("、"));
  if ((g.forbidden || []).length) why.push("說了 " + g.forbidden.join("、"));
  return "沒通過（" + why.join("；") + "）";
}

function biBenchCompared(report) {
  // Which two versions the run compared; a report from before this did not record it.
  if (!("published" in report)) return "比較：工作版本與當時的發佈版本（這次測試沒有記下是哪一版）";
  return report.published
    ? "比較：工作版本與發佈版本「" + report.published.tag + "」"
    : "比較：工作版本與大家已 push 的內容（當時還沒有發佈過）";
}

function biBenchReport(report, standing) {
  const box = el("bi-b-bench-report"); box.replaceChildren();
  // In every working domain: the push carries the whole vault, so it blocks everyone.
  for (const line of (standing || {}).blocking || []) {
    box.append(bh("p", "bi-warn", "Push 會被擋：" + line));
  }
  // A colleague's failure shows whether or not this domain has run anything yet.
  const notes = (standing || {}).notes || [], elsewhere = (line) => line.startsWith("其他領域");
  for (const line of notes.filter(elsewhere)) box.append(bh("p", "bi-meta", line));
  if (!report) {
    box.append(bh("p", "bi-meta", biScope() ? "這個領域還沒有跑過測試。" : "還沒有跑過測試。"));
    return;
  }
  const state = {running: "測試中…", finished: "完成", failed: "沒有跑完"}[report.status]
    || report.status;
  const head = "最近一次測試（" + biTime(report.started_at) + "，" + state + "）";
  const stale = report.stale || {};
  box.append(bh("h5", "", head, ...(stale.stale ? [" ", biBadge("舊結果", "warn")] : [])));
  box.append(bh("p", "bi-meta", biBenchCompared(report)));
  if (stale.stale) {
    // Acceptance F24: an old comparison must not read as how the versions stand today.
    const why = [];
    if (stale.published_changed) {
      why.push(stale.published_now ? "之後發佈了「" + stale.published_now.tag + "」"
        : "之後發佈的版本變了");
    }
    if (stale.content_changed) why.push("之後內容改了");
    box.append(bh("p", "bi-warn", "這是舊結果：" + why.join("，") + "，下面的比較不是現在的狀態。"),
      bh("div", "bi-actions", biButton("重新跑測試", () => el("bi-b-bench-run").click(),
        "bi-btn", "重新跑測試")));
  }
  box.append(bh("p", "bi-meta", (report.scope ? "涵蓋 " + report.scope + " "
    : "涵蓋全部 ") + (report.total || 0) + " 題"));
  for (const line of notes.filter((n) => !elsewhere(n))) box.append(bh("p", "bi-meta", line));
  if (report.error) box.append(bh("p", "bi-warn", "停在：" + report.error));
  if (report.status !== "running") {
    const parts = ["題目：工作版本 " + report.working_score + "/" + report.total
      + "、發佈版本 " + report.published_score + "/" + report.total];
    if ((report.regressions || []).length) parts.push("退步 " + report.regressions.length + " 題");
    if (report.extract) parts.push("擷取 " + report.extract.score + " 分");
    box.append(bh("p", "", parts.join("；")));
    const classes = Object.entries(report.error_classes || {});
    if (classes.length) {
      const words = {retrieval: "檢索", relation: "關係", extraction: "萃取", evidence: "採信",
        generation: "生成", unknown: "分不出"};
      box.append(bh("p", "bi-meta", "工作版本答錯的詞："
        + classes.map(([name, count]) => (words[name] || name) + " " + count).join("、")));
    }
  }
  const regressed = new Set(report.regressions || []);
  const rows = [...(report.results || [])].sort((x, y) =>
    Number(regressed.has(y.unit)) - Number(regressed.has(x.unit)));
  if (rows.length) {
    const table = biListTable(["題目", "工作版本", "發佈版本", "回答"]);
    for (const row of rows) {
      const answers = bh("details", "", bh("summary", "", "看兩邊"),
        bh("p", "", bh("strong", "", "工作版本："), row.working.answer || "（沒有）"),
        bh("p", "", bh("strong", "", "發佈版本："), row.published.answer || "（沒有）"));
      const line = biRow(table, [row.question,
        biBenchGrade(row.working) + (regressed.has(row.unit) ? "・退步" : ""),
        biBenchGrade(row.published), answers]);
      if (regressed.has(row.unit)) line.className = "bi-warn";
    }
    box.append(table.box);
  }
  const list = bh("ul", "bi-log");
  for (const item of report.cases || []) {
    const result = item.result;
    const line = result ? "擷取「" + item.slug + "」：" + result.score + " 分（找到 "
      + result.counts.found + "／" + result.counts.expected + "）"
      : "擷取「" + item.slug + "」：沒有跑完（" + item.error + "）";
    const failures = result ? result.failures.map((f) => f.message) : [];
    list.append(bh("li", failures.length || !result ? "bi-warn" : "", line,
      biListBlock("沒過的檢查", failures.slice(0, 10))));
  }
  if ((report.ungraded || []).length) {
    list.append(bh("li", "bi-meta", report.ungraded.length + " 題沒有「必須提到」或「不可以說」，"
      + "沒有評分。"));
  }
  box.append(list);
}

async function biBench(vaultId) {
  // The newest read wins: an older reply arriving late must not cancel the polling of a run.
  const seq = bi.benchSeq = (bi.benchSeq || 0) + 1;
  const asked = biScope(), writes = bi.benchWrites || 0;
  const reply = await call("/api/bi/vaults/" + vaultId + "/checks"
    + (asked ? "?home=" + encodeURIComponent(asked) : ""));
  if (seq !== bi.benchSeq || vaultId !== bi.verVault) return;
  // Read before a save landed, it would take the saved question away, and clear the editor if
  // that is the one open: what the person saved next would then become a new question.
  if (writes !== (bi.benchWrites || 0)) { await biBench(vaultId); return; }
  reply.home = asked;
  bi.benchReply = {vaultId, reply};
  biBenchDraw(reply);
  clearTimeout(bi.benchTimer);
  // By the newest run of any domain: only one runs at a time on this PC. A run just started may
  // not have written its first report yet: keep reading until it has.
  const newest = reply.newest;
  const unseen = bi.benchWatch && (!newest || newest.run_id !== bi.benchWatch);
  if (unseen || (newest && newest.status === "running")) {
    bi.benchTimer = setTimeout(() => biBench(vaultId).catch(() => {}), unseen ? 300 : 2000);
  } else if (newest && bi.benchWatch === newest.run_id) {
    bi.benchWatch = null;
    biNotice(newest.status === "finished", newest.status === "finished"
      ? "測試跑完了。" : "測試沒有跑完：" + (newest.error || ""));
    // What the share step says of each domain's tests changed with this run.
    if (vaultId === bi.verVault) {
      biShareLoad(vaultId)
        .catch((failure) => biNotice(false, "讀不到分享的內容：" + failure.message));
    }
  }
}

function biBenchDraw(reply) {
  el("bi-b-bench").hidden = false;
  const questions = el("bi-b-bq-list"); questions.replaceChildren();
  // A domain has its own; what no domain has yet shows apart and is not this domain's.
  const scope = biScope();
  const shown = reply.questions.filter((q) => !scope || q.home === scope);
  const waiting = scope ? reply.questions.filter((q) => !q.home) : [];
  const shownCases = reply.cases.filter((c) => !scope || biFolderHome(c.folder) === scope);
  const table = (items) => {
    const list = biListTable(["題目", "必須提到", "不可以說", "題組", "領域"]);
    for (const q of items) {
      const row = biRow(list, [q.question, q.must.join("、") || "—",
        q.must_not.join("、") || "—", q.set, q.home || "全庫"]);
      row.dataset.unit = q.unit;
      // The overview only reads.
      if (biOverview()) continue;
      row.tabIndex = 0;
      row.setAttribute("aria-selected", String(!!bi.bqSel && bi.bqSel.unit === q.unit));
      row.addEventListener("click", () => biBqPick(q));
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter") { event.preventDefault(); biBqPick(q); }
      });
    }
    return list.box;
  };
  questions.append(shown.length ? table(shown) : bh("p", "bi-meta", scope
    ? "這個領域還沒有測試題：按「新增題目」或「和 AI 一起出題」。" : "還沒有測試題。"));
  if (waiting.length) {
    const apart = bh("details", "bi-manage", bh("summary", "",
      "還沒指定領域的題目 " + waiting.length + " 題（全庫）：不是這個領域的，選一列指定領域。"),
    table(waiting));
    apart.id = "bi-b-bq-waiting";
    apart.open = Boolean(bi.bqSel && waiting.some((q) => q.unit === bi.bqSel.unit));
    questions.append(apart);
  }
  // The question being edited may be gone (deleted here, or by a colleague's commit).
  if (bi.bqSel && ![...shown, ...waiting].some((q) => q.unit === bi.bqSel.unit)) biBqPick(null);
  el("bi-b-bq-sets").replaceChildren(...[...new Set(reply.questions.map((q) => q.set))]
    .map((name) => { const o = document.createElement("option"); o.value = name; return o; }));
  el("bi-b-bench-state").textContent = shown.length + " 題"
    + (shownCases.length ? "・擷取測試 " + shownCases.length + " 個" : "");
  el("bi-b-run-why").textContent = !shown.length && !shownCases.length
    ? "還沒有測試題：展開 Benchmark 新增。"
    : "這次跑" + (scope ? " " + scope + " 的 " : "全部 ") + shown.length + " 題";
  const cases = el("bi-b-bc-list"); cases.replaceChildren();
  if (!shownCases.length) cases.append(bh("p", "bi-meta", "還沒有擷取測試。"));
  for (const c of shownCases) {
    const count = ((c.expected || {}).candidates || []).length;
    cases.append(bh("div", "bi-step", bh("strong", "", c.slug),
      bh("p", "bi-meta", (c.folder || "sources") + "・應找到 " + count + " 張候選卡"),
      bh("div", "bi-actions", biButton("刪除", () => biBenchSave({delete: c.unit}), "bi-btn",
        "刪除擷取測試 " + c.slug))));
  }
  // A reply for the domain left says nothing of this one; the read under way will.
  if (reply.home === scope) biBenchReport(reply.latest, reply.standing);
  else el("bi-b-bench-report").replaceChildren();
  el("bi-b-bench-run").disabled = !(shown.length || shownCases.length)
    || Boolean(reply.newest && reply.newest.status === "running");
}

function biBqPick(q) {
  // The row chosen goes into the editor beside the table; none means a new question.
  // Homes may arrive after the row's listener was attached. Check the current view.
  if (q && biOverview()) return;
  bi.bqSel = q;
  for (const row of el("bi-b-bq-list").querySelectorAll("tbody tr")) {
    row.setAttribute("aria-selected", String(!!q && row.dataset.unit === q.unit));
  }
  el("bi-b-bq-title").textContent = q ? "修改題目" : "新增題目";
  el("bi-b-bq-q").value = q ? q.question : "";
  el("bi-b-bq-must").value = q ? q.must.join(", ") : "";
  el("bi-b-bq-not").value = q ? q.must_not.join(", ") : "";
  if (q) el("bi-b-bq-set").value = q.set;
  el("bi-b-bq-del").hidden = !q;
  biBqHomes();
}

function biBqHomes() {
  // 全庫 and the vault's homes. A home no longer listed stays an option on its own question,
  // or saving a question would quietly take its home away.
  const q = bi.bqSel, own = q ? q.home || "" : biScope() || "";
  const homes = (bi.build.homes || []).map((item) => item.home);
  if (own && !homes.includes(own)) homes.push(own);
  el("bi-b-bq-home").replaceChildren(...["", ...homes].map((home) => {
    const option = bh("option", "", home || "全庫"); option.value = home; return option;
  }));
  el("bi-b-bq-home").value = own;
}

async function biBenchSave(body) {
  const reply = await biCall("/api/bi/vaults/" + bi.verVault + "/checks", body);
  bi.benchWrites = (bi.benchWrites || 0) + 1;
  biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
  biNotice(true, body.delete ? "已刪除（commit 並 push 後大家才會少這個測試）。"
    : body.slug ? "已存（commit 並 push 後大家才會用到）。"
      : "已加入（commit 並 push 後大家才會有這個測試）。");
  return reply;
}

el("bi-b-bq-add").addEventListener("click", () => {
  biBqPick(null); el("bi-b-bq-q").focus();
});
el("bi-b-bq-del").addEventListener("click", async () => {
  const q = bi.bqSel; if (!q) return;
  try { await biBenchSave({delete: q.unit}); biBqPick(null); }
  catch (failure) { biNotice(false, "沒有刪除：" + failure.message); }
});
el("bi-b-bq-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const q = bi.bqSel;
  const set = el("bi-b-bq-set").value.trim() || "main";
  const body = {question: el("bi-b-bq-q").value, must: el("bi-b-bq-must").value,
    must_not: el("bi-b-bq-not").value, set, home: el("bi-b-bq-home").value || null};
  try {
    if (q) {
      // A question is its set and slug: the same pair overwrites, another set is a move.
      const saved = await biBenchSave({...body, slug: q.slug});
      if (set !== q.set) await biBenchSave({delete: q.unit});
      // Given to another domain, it has left this list and the editor starts afresh.
      biBqPick(!biInScope(body.home) ? null : {...q, ...{question: body.question, set,
        unit: saved.unit, home: body.home,
        must: biList(body.must), must_not: biList(body.must_not)}});
    } else {
      await biBenchSave(body);
      biBqPick(null);
    }
  } catch (failure) { biNotice(false, "沒有存：" + failure.message); }
});
el("bi-b-bc-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  let expected;
  try { expected = JSON.parse(el("bi-b-bc-expected").value || "null"); }
  catch (e) { biNotice(false, "「應找到什麼」不是正確的 JSON。"); return; }
  try {
    await biBenchSave({kind: "case", slug: el("bi-b-bc-slug").value,
      folder: el("bi-b-bc-folder").value, note: el("bi-b-bc-note").value, expected});
    for (const id of ["bi-b-bc-slug", "bi-b-bc-note", "bi-b-bc-expected"]) el(id).value = "";
  } catch (failure) { biNotice(false, "沒有加入：" + failure.message); }
});
// -- 和 AI 一起出測試題 (docs/phases/BI_BUILD_FLOW.md §7) ------------------------------
function biQuestionsSuggestion(session, turn, index) {
  const s = turn.suggestion;
  const parts = [bh("p", "", bh("strong", "", "AI："), s.reply), biListBlock("理由", s.reasons)];
  if (!s.questions.length) return parts;
  const ticks = s.questions.map((q) => {
    const tick = document.createElement("input");
    tick.type = "checkbox"; tick.disabled = !!turn.applied;
    tick.checked = turn.applied ? turn.applied.units.includes(q.unit) : true;
    tick.setAttribute("aria-label", "加入：" + q.question);
    return tick;
  });
  parts.push(bh("ul", "bi-qa-list", ...s.questions.map((q, i) => bh("li", "",
    bh("label", "", ticks[i], " " + q.question),
    bh("p", "bi-meta", "必須提到：" + (q.must.join("、") || "（沒有）")
      + "・不可以說：" + (q.must_not.join("、") || "（沒有）"))))));
  if (turn.applied) {
    parts.push(bh("p", "bi-meta", "已加入 " + turn.applied.units.length
      + " 題（commit 並 push 後才會跟著知識庫）。"));
  } else {
    parts.push(bh("div", "bi-actions", biButton("加入測試題", async () => {
      const picks = ticks.flatMap((tick, i) => tick.checked ? [i] : []);
      const reply = await biCall("/api/bi/sessions/" + session.id + "/apply",
        {dataset: bi.ai.dataset, turn: index, picks, home: bi.ai.scope});
      biAiShow(reply.session);
      await biBench(bi.verVault);
      biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
      biNotice(true, "已加入 " + reply.units.length
        + " 題測試題；commit 並 push 後才會跟著知識庫。");
    }, "go", "把勾選的題目加入測試題")));
  }
  return parts;
}

// -- the one AI panel: every session kind opens here, beside what it concerns --------
// A kind says what it is about, what goes to the model, and how to get ready to send.
// The conversation is the same for all, and nothing changes until the person confirms.
function biAiShow(session) {
  if (!bi.ai) return;
  bi.ai.session = session;
  biBuildSessionLog("bi-ai-log", session, bi.ai.render);
  const body = el("bi-ai-body"); body.scrollTop = body.scrollHeight;
}

function biAiTarget(text) { el("bi-ai-target").textContent = text; }

function biAiClose() {
  const spec = bi.ai; if (!spec) return;
  bi.ai = null;
  el("bi-ai").hidden = true;
  biSideRoom();
  document.querySelectorAll("tr.bi-ai-from").forEach((r) => r.classList.remove("bi-ai-from"));
  if (spec.from && spec.from.isConnected) spec.from.focus();
}

async function biAiOpen(spec) {
  biAiClose();
  spec.from = spec.from || document.activeElement;
  const row = spec.from && spec.from.closest ? spec.from.closest("tr") : null;
  if (row) row.classList.add("bi-ai-from");
  bi.ai = spec;
  spec.scope = biScope();
  el("bi-ai").dataset.kind = spec.kind;
  el("bi-ai").hidden = false;
  biSideRoom();
  el("bi-ai-title").textContent = spec.title;
  el("bi-ai-label").textContent = spec.label;
  el("bi-ai-msg").placeholder = spec.placeholder; el("bi-ai-msg").value = "";
  el("bi-ai-new").hidden = spec.mode !== "new";
  el("bi-ai-schema").hidden = spec.kind !== "schema";
  biStatus("bi-ai-status", "");
  biAiTarget((spec.scope ? "工作領域 " + spec.scope + "・" : "") + spec.about);
  biBuildSessionLog("bi-ai-log", null, spec.render);
  // After the page has made room: what it came from stays in view beside the panel.
  const shown = row || spec.shows || spec.from;
  if (shown && shown.closest && shown.closest("details.bi-sec")) {
    shown.closest("details.bi-sec").open = true;
  }
  // On a phone the panel takes the lower part, so what it came from goes to the top.
  const phone = matchMedia("(max-width: 760px)").matches;
  if (shown && shown.isConnected) {
    shown.scrollIntoView({block: phone ? "start" : row ? "nearest" : "center"});
  }
  await biBuildAiState("bi-ai-sent", spec.sends, spec.agent);
  if (bi.ai === spec && spec.ref) {
    const found = await call("/api/bi/sessions?dataset=" + encodeURIComponent(spec.dataset)
      + "&target=" + encodeURIComponent(spec.ref));
    if (bi.ai === spec) biAiShow((found.sessions || [])[0] || null);
  }
  if (bi.ai === spec) el("bi-ai-msg").focus();
  return spec;
}

function biAiNoModel() {
  // Without a model nothing is made: no draft or copy for a message that cannot be sent.
  return Object.assign(new Error(bi.build.ai.message), {code: "model_unavailable"});
}

el("bi-ai-close").addEventListener("click", biAiClose);
el("bi-ai").addEventListener("keydown", (event) => {
  if (event.key === "Escape") biAiClose();
});
el("bi-ai-send").addEventListener("click", async () => {
  const spec = bi.ai; if (!spec) return;
  const message = el("bi-ai-msg").value.trim();
  if (!message) { el("bi-ai-msg").focus(); return; }
  const button = el("bi-ai-send"); button.disabled = true;
  biStatus("bi-ai-status", "loading", spec.busy);
  try {
    if (spec.agent !== undefined && spec.checkModel !== false) {
      await biBuildAiState("bi-ai-sent", spec.sends, spec.agent);
      if (!bi.build.ai.available) throw biAiNoModel();
    }
    if (spec.prepare) await spec.prepare(message, spec);
    if (!spec.session) {
      spec.session = (await biCall("/api/bi/sessions", {dataset: spec.dataset, kind: spec.kind,
        target: spec.sessionTarget()})).session;
    }
    const reply = await biCall("/api/bi/sessions/" + spec.session.id + "/turns",
      {dataset: spec.dataset, message, scope: spec.scope,
        ...(spec.turn ? spec.turn() : {})});
    spec.session = reply.session;
    if (spec.saved) spec.saved(reply.session);
    if (bi.ai === spec) {
      el("bi-ai-msg").value = ""; biAiShow(reply.session); biStatus("bi-ai-status", "");
    }
  } catch (failure) {
    if (bi.ai === spec) {
      biStatus("bi-ai-status", "error", (failure.code === "model_unavailable"
        ? "沒有可用的模型：" : "沒有送出：") + failure.message + "。");
    }
  } finally { button.disabled = false; }
});

async function biQuestionsAi() {
  const target = el("bi-b-bq-set").value.trim() || "main";
  await biAiOpen({kind: "questions", dataset: "vault-" + bi.verVault, ref: "questions:" + target,
    title: "和 AI 出測試題", about: "題組「" + target + "」。勾選並按「加入測試題」才會加入。",
    sends: "卡片與分析", agent: true, checkModel: false,
    label: "你想測什麼", placeholder: "例如：出五題，涵蓋客戶訊號與產品對應",
    busy: "正在查卡片、試問題目…（可能要幾分鐘）", render: biQuestionsSuggestion,
    shows: el("bi-b-bq-list"),
    sessionTarget: () => target});
}

el("bi-b-qa-open").addEventListener("click", () => biQuestionsAi()
  .catch((failure) => biNotice(false, failure.message)));

el("bi-b-bench-run").addEventListener("click", async () => {
  const button = el("bi-b-bench-run"); button.disabled = true;
  try {
    const reply = await biCall("/api/bi/vaults/" + bi.verVault + "/bench", {home: biScope()});
    bi.benchWatch = reply.run_id;
    biNotice(true, "測試開始了：每題會問 Agent 兩次，需要幾分鐘。");
    await biBench(bi.verVault);
  } catch (failure) {
    button.disabled = false;
    biNotice(false, "沒有開始：" + failure.message);
  }
});

// -- 分析與圖表 (BI T3, docs/phases/BI_TEST_AND_TOOLS.md §5) -----------------------------
/* BI_CHART_JS */

function biParamInputs(item, values, onChange) {
  // The analysis's parameters as controls (design §4.1); a change reruns it.
  const inputs = item.inputs || {}, names = Object.keys(inputs);
  if (!names.length) return null;
  const row = bh("div", "bi-actions bi-params");
  for (const name of names) {
    const spec = inputs[name], label = spec.label || name;
    let control;
    if (spec.type === "enum") {
      control = document.createElement("select");
      for (const value of spec.values || []) {
        const option = document.createElement("option");
        option.value = value; option.textContent = value; control.append(option);
      }
      const own = name === "domain" && (spec.values || []).find((value) =>
        value.toLowerCase() === String(biScopeDomain() || "").toLowerCase());
      if (own && values[name] === undefined) values[name] = own;
      control.value = values[name] ?? spec.default ?? "";
    } else if (spec.type === "bool") {
      control = document.createElement("input"); control.type = "checkbox";
      control.checked = values[name] ?? Boolean(spec.default);
    } else {
      control = document.createElement("input");
      control.type = spec.type === "date" ? "date" : "text";
      control.value = values[name] ?? (spec.default === "today" ? "" : (spec.default || ""));
    }
    control.dataset.param = name;
    control.setAttribute("aria-label", item.title + "：" + label);
    control.addEventListener("change", () => {
      values[name] = spec.type === "bool" ? control.checked : control.value;
      if (values[name] === "") delete values[name];
      onChange();
    });
    row.append(bh("label", "bi-meta", label + " ", control));
  }
  return row;
}

function biAnState(vaultId, slug) {
  // Chosen values and the last result per analysis, kept across re-renders.
  bi.anState = bi.anState || {};
  const key = vaultId + "/" + slug;
  bi.anState[key] = bi.anState[key] || {values: {}, table: null};
  return bi.anState[key];
}

function biAnOut(where, item, state) {
  const out = bh("div", "");
  out.dataset.anOut = where + ":" + item.slug;
  if (state.table && where === "list") out.append(biChart(state.table, item.chart));
  return out;
}

async function biRunInto(vaultId, item, state, out) {
  const ran = await biCall("/api/bi/vaults/" + vaultId + "/analyses",
    {run: item.slug, params: state.values});
  state.table = ran.table;
  // The list may have been drawn again meanwhile: draw into the one shown now.
  const shown = out.isConnected ? out
    : document.querySelector('[data-an-out="' + CSS.escape(out.dataset.anOut) + '"]') || out;
  shown.replaceChildren(biChart(ran.table, item.chart));
}

const biDashboardSaves = new Map();
function biSaveDashboard(vaultId, change, scope) {
  const key = JSON.stringify([vaultId, scope]);
  const here = () => vaultId === bi.verVault && scope === biScope();
  // Queue intentions, not the old rendered order: a second button can be pressed
  // before the first response body or its refresh has finished.
  const previous = biDashboardSaves.get(key) || Promise.resolve();
  const pending = previous.catch(() => {}).then(async () => {
    const current = await call("/api/bi/vaults/" + vaultId + "/analyses"
      + (scope ? "?home=" + encodeURIComponent(scope) : ""));
    const layout = change({order: [...(scope ? current.dashboard.order : current.order)],
      hidden: [...(current.dashboard.hidden || [])], visible: [...current.order]});
    if (!layout) return;
    await biCall("/api/bi/vaults/" + vaultId + "/analyses", {dashboard: layout, home: scope});
    if (!here()) return;
    const status = await call("/api/bi/vaults/" + vaultId + "/status");
    if (!here()) return;
    biVaultState(status);
    await biAnalyses(vaultId);
    if (here()) biNotice(true, "已改 Dashboard 的順序（commit 並 push 後大家才會看到）。");
  });
  biDashboardSaves.set(key, pending);
  const clean = () => { if (biDashboardSaves.get(key) === pending) biDashboardSaves.delete(key); };
  // A failed save remains a failure for its caller, without poisoning the next intent.
  pending.then(clean, clean);
  return pending;
}

async function biAnalyses(vaultId) {
  // The newest read wins: a reply for the domain left must not draw over this one's.
  const seq = bi.anSeq = (bi.anSeq || 0) + 1, scope = biScope();
  const reply = await call("/api/bi/vaults/" + vaultId + "/analyses"
    + (scope ? "?home=" + encodeURIComponent(scope) : ""));
  if (vaultId !== bi.verVault || seq !== bi.anSeq) return;
  // What the Dashboard shows may have changed: drawn again when opened, or now in step 3.
  const seen = JSON.stringify([reply.home, reply.order, reply.dashboard,
    reply.analyses.map((a) => [a.slug, a.digest])]);
  if (seen !== bi.anSeen) {
    bi.anSeen = seen;
    if (bi.loaded) bi.loaded.dashboard = false;
    biDashHome();
  }
  el("bi-b-an").hidden = false;
  const box = el("bi-b-an-list"); box.replaceChildren();
  if (!reply.analyses.length) box.append(bh("p", "bi-meta", "還沒有存起來的分析。"));
  // Shown in the Dashboard's order, then hidden and not offered ones.
  const rank = (a) => { const i = reply.order.indexOf(a.slug); return i < 0 ? 1e6 : i; };
  const items = [...reply.analyses].sort((a, b) => rank(a) - rank(b));
  const hidden = new Set(reply.dashboard.hidden || []);
  const move = (slug, step) => biSaveDashboard(vaultId, (current) => {
    const order = [...current.order], at = current.visible.indexOf(slug);
    if (at < 0 || at + step < 0 || at + step >= current.visible.length) return null;
    const from = order.indexOf(slug), to = order.indexOf(current.visible[at + step]);
    [order[from], order[to]] = [order[to], order[from]];
    return {order, hidden: current.hidden};
  }, scope);
  // A domain's Dashboard is what it chose; the vault's is every analysis not hidden.
  const onIt = (a) => a.offered && !hidden.has(a.slug) && (!scope || reply.order.includes(a.slug));
  el("bi-b-an-state").textContent = scope
    ? items.filter(onIt).length + " 個分析"
    : reply.analyses.length + " 個分析・Dashboard 顯示 " + items.filter(onIt).length + " 個";
  const heads = ["分析", "類型", "Dashboard", "動作"];
  const onBoard = biListTable(heads), offBoard = biListTable(heads);
  let off = 0;
  for (const item of items) {
    const state = biAnState(vaultId, item.slug), out = biAnOut("list", item, state);
    const where = !item.offered
      ? "schema 沒有它需要的 " + (item.missing || []).join("、") + "，Dashboard 不顯示"
      : !onIt(item) ? "Dashboard 不顯示" : "Dashboard 第 " + (rank(item) + 1) + " 個";
    const shown = scope && !onIt(item)
      ? biButton("加到這個領域", () => biSaveDashboard(vaultId,
        (current) => ({order: [...current.order.filter((s) => s !== item.slug), item.slug],
          hidden: current.hidden.filter((s) => s !== item.slug)}), scope),
      "bi-btn", "把分析 " + item.title + " 加到這個領域的 Dashboard")
      : hidden.has(item.slug)
      ? biButton("在 Dashboard 顯示", () => biSaveDashboard(vaultId,
        (current) => ({order: current.order,
          hidden: current.hidden.filter((s) => s !== item.slug)}), scope), "bi-btn",
        "在 Dashboard 顯示分析 " + item.title)
      : biButton("在 Dashboard 隱藏", () => biSaveDashboard(vaultId,
        (current) => ({order: current.order,
          hidden: [...new Set([...current.hidden, item.slug])]}), scope),
        "bi-btn", "在 Dashboard 隱藏分析 " + item.title);
    const shownOn = onIt(item);
    if (!shownOn) off += 1;
    const table = shownOn ? onBoard : offBoard;
    const title = [bh("strong", "", item.title)];
    // It would show the same numbers in any domain, and must not pass for this one's.
    if (scope && !item.filters_domain) title.push(" ", biBadge("全庫資料", "dim"));
    if (item.question) title.push(bh("div", "bi-meta", item.question));
    const row = biRow(table, [title, (item.kind === "sql" ? "SQL" : "Python") + "・"
      + item.chart.type, where, ""]);
    // Its parameters and result open under the row when it is run.
    const under = biRowDetail(table);
    under.row.hidden = !state.table;
    under.cell.append(...[biParamInputs(item, state.values, () => biRunInto(vaultId, item, state,
      out).catch((failure) => biNotice(false, failure.message))), out].filter(Boolean));
    row.lastChild.append(
      biRowActions([
        biButton("執行", () => {
          under.row.hidden = false;
          return biRunInto(vaultId, item, state, out);
        }, "bi-btn", "執行分析 " + item.title),
        reply.order.includes(item.slug) ? biButton("上移", () => move(item.slug, -1), "bi-btn",
          "在 Dashboard 上移分析 " + item.title) : null],
        biButton("和 AI 一起修改", (event) =>
          biAnalysisAi(item.slug, item.title, event.currentTarget),
          "bi-btn", "和 AI 一起修改分析 " + item.title),
        reply.order.includes(item.slug) ? biButton("下移", () => move(item.slug, 1), "bi-btn",
          "在 Dashboard 下移分析 " + item.title) : null,
        item.offered ? shown : null,
        biButton("刪除", async () => {
          await biCall("/api/bi/vaults/" + vaultId + "/analyses", {delete: item.unit});
          biVaultState(await call("/api/bi/vaults/" + vaultId + "/status"));
          biNotice(true, "已刪除分析（commit 並 push 後大家才會少這個分析）。");
        }, "bi-btn", "刪除分析 " + item.title)));
  }
  if (off < items.length) box.append(onBoard.box);
  else if (scope) {
    box.append(bh("p", "bi-meta",
      "這個領域的 Dashboard 還是空的：按「和 AI 做新分析」，或從下面加入。"));
  }
  if (off) {
    box.append(bh("details", "bi-manage", bh("summary", "", (scope
      ? "還沒放進這個領域的分析（" : "不在 Dashboard 的分析（") + off + "）"),
      offBoard.box));
  }
}

const BI_ANALYSIS_FIELDS = {title: "標題", question: "問題", kind: "類型", code: "SQL 或腳本",
  chart: "圖表", params: "參數", requires: "需要的卡片類型與欄位"};

function biChangedValue(value) {
  if (value === null || value === undefined) return "（無）";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function biAnalysisChanges(edit) {
  // What an edit changes (BI P2): each field before and after.
  return bh("div", "bi-analysis-changes", ...edit.changes.map((change) => bh("div", "",
    bh("p", "bi-meta", BI_ANALYSIS_FIELDS[change.field] || change.field),
    bh("div", "bi-ver-pair",
      bh("div", "", bh("p", "bi-meta", "修改前"),
        bh("pre", "bi-code", biChangedValue(change.before))),
      bh("div", "", bh("p", "bi-meta", "修改後"),
        bh("pre", "bi-code", biChangedValue(change.after)))))));
}

function biAnalysisSuggestion(session, turn, index) {
  const s = turn.suggestion;
  const parts = [bh("p", "", bh("strong", "", "AI："), s.reply)];
  if (s.dashboard) return parts.concat(biDashboardSuggestion(session, turn, index));
  if (!s.analysis) return parts;
  const edit = s.edit || null;
  parts.push(bh("p", "", bh("strong", "", s.analysis.title),
    edit ? "（修改現有分析 " + s.analysis.slug + "）" : ""));
  if (edit) parts.push(biAnalysisChanges(edit));
  parts.push(bh("details", "", bh("summary", "", s.analysis.kind === "sql" ? "看 SQL" : "看腳本"),
    bh("pre", "bi-code", s.analysis.code)));
  if (edit && edit.preview) {
    parts.push(bh("div", "bi-ver-pair",
      bh("div", "", bh("p", "bi-meta", "修改前的結果"), biChart(edit.preview, edit.before.chart)),
      bh("div", "", bh("p", "bi-meta", "修改後的結果"),
        s.preview ? biChart(s.preview, s.analysis.chart) : "")));
  } else if (s.preview) {
    parts.push(biChart(s.preview, s.analysis.chart));
  }
  if (turn.applied) {
    parts.push(bh("p", "bi-meta", (edit ? "已套用修改" : "已存成分析")
      + "（commit 並 push 後大家才會看到）。"));
  } else if (edit && !edit.changes.length) {
    parts.push(bh("p", "bi-meta", "這個提案和現有的分析一樣，沒有要改的。"));
  } else {
    parts.push(bh("div", "bi-actions", biButton(edit ? "套用修改" : "存成分析", async () => {
      const reply = await biCall("/api/bi/sessions/" + session.id + "/apply",
        {dataset: bi.ai.dataset, turn: index, home: bi.ai.scope});
      biAiShow(reply.session);
      biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
      biNotice(true, (edit ? "已套用修改「" : "已存成分析「") + s.analysis.title
        + "」；commit 並 push 後大家才會看到。");
    }, "go", edit ? "把這個修改存進知識庫" : "把這個分析存進知識庫")));
  }
  return parts;
}

function biDashboardSuggestion(session, turn, index) {
  // A dashboard the analysis AI proposed (BI K1): the order, each analysis, new or changed
  // (BI P3), with its preview, and one 「套用 Dashboard」 that stages them and the order together.
  const d = turn.suggestion.dashboard, previews = turn.suggestion.previews || {};
  const edits = d.edits || {};
  const fresh = new Map(d.analyses.map((a) => [a.slug, a]));
  const parts = [bh("p", "", bh("strong", "", "Dashboard（由上到下）")),
    bh("ol", "bi-dash-order", ...d.order.map((slug) => bh("li", "",
      fresh.has(slug) ? fresh.get(slug).title + (edits[slug] ? "（修改）" : "（新）")
        : slug + "（知識庫已有）")))];
  for (const a of d.analyses) {
    parts.push(bh("p", "", bh("strong", "", a.title), edits[a.slug] ? "（修改）" : ""));
    if (edits[a.slug]) parts.push(biAnalysisChanges(edits[a.slug]));
    parts.push(
      bh("details", "", bh("summary", "", a.kind === "sql" ? "看 SQL" : "看腳本"),
        bh("pre", "bi-code", a.code)));
    if (previews[a.slug]) parts.push(biChart(previews[a.slug], a.chart));
  }
  parts.push(bh("p", "bi-meta", "不在順序裡的分析會在 Dashboard 隱藏，不會刪除。"));
  if (turn.applied) {
    parts.push(bh("p", "bi-meta", "已套用 Dashboard（commit 並 push 後大家才會看到）。"));
    return parts;
  }
  parts.push(bh("div", "bi-actions", biButton("套用 Dashboard", async () => {
    const reply = await biCall("/api/bi/sessions/" + session.id + "/apply",
      {dataset: bi.ai.dataset, turn: index, home: bi.ai.scope});
    biAiShow(reply.session);
    biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
    biNotice(true, "已套用 Dashboard：" + d.analyses.length + " 個分析與順序；"
      + "commit 並 push 後大家才會看到。");
  }, "go", "把這些分析與 Dashboard 順序存進知識庫")));
  return parts;
}

async function biAnalysisAi(slug, title, from) {
  const target = slug || "new";
  await biAiOpen({kind: "analysis", dataset: "vault-" + bi.verVault, from,
    ref: "analysis:" + target,
    title: slug ? "和 AI 修改分析" : "和 AI 做新分析",
    about: slug ? "分析「" + title + "」。按「存成分析」才會存。"
      : "說出你想確認的關係或現象。按「存成分析」才會存。",
    sends: "資料表與欄位的說明、查詢結果", agent: true, checkModel: false,
    label: "你想看什麼", placeholder: "例如：各應用領域各有幾個商機？畫長條圖",
    busy: "正在查資料、畫圖…（可能要一兩分鐘）", render: biAnalysisSuggestion,
    shows: el("bi-b-an-new"),
    sessionTarget: () => target});
}

async function biImportPack(pack) {
  // A pack's analyses the schema satisfies are staged; the rest are listed (design §4.2).
  const vaultId = bi.verVault;
  const reply = await biCall("/api/bi/vaults/" + vaultId + "/packs", {import: pack});
  biVaultState(await call("/api/bi/vaults/" + vaultId + "/status"));
  const skipped = (reply.skipped || []).map((s) => s.title + "（缺 " + s.missing.join("、") + "）");
  biNotice(true, "已加入 " + reply.staged.length + " 個分析（commit 並 push 後大家才會看到）"
    + (skipped.length ? "；schema 不支援、沒有加入：" + skipped.join("、") : "") + "。");
}

el("bi-b-an-pack").addEventListener("click", () => biImportPack("bi-market-default")
  .catch((failure) => biNotice(false, failure.message)));
el("bi-b-an-file").addEventListener("change", async () => {
  const file = el("bi-b-an-file").files[0]; el("bi-b-an-file").value = "";
  if (!file) return;
  try { await biImportPack(JSON.parse(await file.text())); }
  catch (failure) { biNotice(false, "沒有匯入分析包：" + failure.message); }
});
el("bi-b-an-export").addEventListener("click", async () => {
  try {
    const reply = await biCall("/api/bi/vaults/" + bi.verVault + "/packs", {export: {}});
    const blob = new Blob([JSON.stringify(reply.pack, null, 2)], {type: "application/json"});
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob); link.download = reply.pack.id + ".json";
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    biNotice(true, "已匯出 " + reply.pack.analyses.length + " 個分析（" + link.download + "）。");
  } catch (failure) { biNotice(false, "沒有匯出：" + failure.message); }
});
// -- 從 Atlas 匯入 Dashboard 順序 (BI K2, docs/phases/BI_CHAT_CHARTS_AND_DASHBOARD_SOURCES.md) --
const BI_ATLAS_STATUS = {kept: "匯入", duplicate: "重複，略過", unknown_analysis:
  "知識庫沒有這個分析，略過", other_vault: "別的知識庫，略過", not_aep: "不是 AEP 的分析，略過",
  not_a_panel: "略過"};

function biAtlasAsked() {
  return {name: el("bi-b-atl-name").value, port: el("bi-b-atl-port").value.trim()};
}

function biAtlasPlan(asked, plan) {
  // The dry run: the new order, what becomes hidden, and what became of every panel.
  const box = el("bi-b-atl-plan");
  const parts = [bh("p", "", bh("strong", "", "「" + plan.dashboard + "」的順序（由上到下）")),
    bh("ol", "bi-dash-order", ...plan.order.map((slug) => bh("li", "", slug)))];
  if (plan.hidden.length) {
    parts.push(bh("p", "bi-meta", "會在 Dashboard 隱藏（不刪除）：" + plan.hidden.join("、")));
  }
  parts.push(bh("details", "", bh("summary", "", "Atlas 的 panel（" + plan.panels.length + "）"),
    bh("ul", "", ...plan.panels.map((p) => bh("li", "", p.id + (p.slug ? "（" + p.slug + "）" : "")
      + "：" + (BI_ATLAS_STATUS[p.status] || p.status))))));
  if (!plan.order.length) {
    parts.push(bh("p", "bi-meta", "這個 Atlas Dashboard 沒有這個知識庫的分析，沒有可匯入的順序。"));
  } else {
    parts.push(bh("div", "bi-actions", biButton("確認匯入順序", async () => {
      await biCall("/api/bi/vaults/" + bi.verVault + "/atlas-import",
        Object.assign({}, asked, {apply: true, token: plan.token}));
      box.replaceChildren();
      biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
      await biAnalyses(bi.verVault);
      biNotice(true, "已匯入 Atlas「" + plan.dashboard + "」的順序"
        + "（commit 並 push 後大家才會看到）。");
    }, "go", "把這個順序存進知識庫")));
  }
  box.replaceChildren(...parts);
}

el("bi-b-atl-load").addEventListener("click", async () => {
  try {
    const port = el("bi-b-atl-port").value.trim();
    const reply = await biCall("/api/bi/vaults/" + bi.verVault + "/atlas-dashboards?port="
      + encodeURIComponent(port));
    el("bi-b-atl-name").replaceChildren(...reply.names.map((name) => {
      const option = document.createElement("option");
      option.value = name; option.textContent = name; return option;
    }));
    el("bi-b-atl-plan").replaceChildren();
    biNotice(true, reply.names.length ? "Atlas 有 " + reply.names.length + " 個 Dashboard。"
      : "Atlas 還沒有存任何 Dashboard。");
  } catch (failure) { biNotice(false, "沒有讀到 Atlas：" + failure.message); }
});
el("bi-b-atl-preview").addEventListener("click", async () => {
  try {
    const asked = biAtlasAsked();
    biAtlasPlan(asked, await biCall("/api/bi/vaults/" + bi.verVault + "/atlas-import", asked));
  } catch (failure) { biNotice(false, "沒有預覽：" + failure.message); }
});
el("bi-b-atl-pick").addEventListener("click", () => el("bi-b-atl-file").click());
el("bi-b-atl-file").addEventListener("change", async (event) => {
  const chosen = event.target.files[0]; event.target.value = "";
  if (!chosen) return;
  try {
    if (chosen.size > 2000000) throw new Error("檔案太大（上限 2 MB）");
    const asked = {file: await chosen.text()};
    biAtlasPlan(asked, await biCall("/api/bi/vaults/" + bi.verVault + "/atlas-import", asked));
  } catch (failure) { biNotice(false, "沒有預覽：" + failure.message); }
});
el("bi-b-an-new").addEventListener("click", () => biAnalysisAi(null, null)
  .catch((failure) => biNotice(false, failure.message)));
// -- the 「版本」 area (knowledge repositories R5, KNOWLEDGE_REPO.md §10) ----------
function biVerValue(value) {
  if (value === null || value === undefined) return "（沒有）";
  if (typeof value === "object" && !Array.isArray(value) && "value" in value) value = value.value;
  if (value === null || value === undefined || value === "") return "（空）";
  const shown = typeof value === "string" ? value : JSON.stringify(value);
  return shown.length > 200 ? shown.slice(0, 200) + "…" : shown;
}

const BI_UNIT_KIND = {card: "卡片", field: "欄位", evidence: "出處", state: "欄位狀態",
  source: "來源", skill: "判讀規則", check: "測試題", analysis: "分析", proposal: "待審提議",
  import: "匯入紀錄", decision: "衝突決定", meta: "設定", schema: "schema", profile: "profile",
  tool: "資料處理程式", relation: "關聯", relation_evidence: "關聯出處"};

function biVerWords(value) {
  // A value in words, or nothing where it has none: an object is never shown as JSON.
  if (value === null || value === undefined || value === "") return "（空）";
  if (Array.isArray(value)) {
    return value.every((item) => typeof item !== "object") ? value.join("、") : null;
  }
  if (typeof value === "object") return null;
  const shown = String(value);
  return shown.length > 80 ? shown.slice(0, 80) + "…" : shown;
}

function biVerChange(change) {
  const {before, after} = change;
  const inner = (value) => (value && typeof value === "object" && !Array.isArray(value)
    && "value" in value ? value.value : value);
  const old = biVerWords(inner(before)), now = biVerWords(inner(after));
  const said = (word, value) => (value && value !== "（空）" ? word + "：" + value : word);
  if (before === null || before === undefined) return said("新增", now);
  if (after === null || after === undefined) return said("移除", old);
  if (Array.isArray(before) && Array.isArray(after) && change.unit.startsWith("evidence:")) {
    return before.length + " → " + after.length + " 筆";
  }
  return old === null || now === null || old === now ? "修改" : old + " → " + now;
}

function biHomeLabel(home) {
  const item = (bi.build.homes || []).find((found) => found.home === home);
  return item ? item.label : home;
}

function biVerChanges(changes) {
  const table = biListTable(["名稱", "種類", "領域", "改動"]);
  for (const change of changes) {
    const unit = String(change.unit), kind = unit.split(":", 1)[0];
    const homes = (change.homes || []).map(biHomeLabel).join("、");
    biRow(table, [change.label || unit, BI_UNIT_KIND[kind] || kind, homes || "其他",
      biVerChange(change)]);
  }
  table.box.classList.add("bi-scroller", "bi-ver-changes");
  return table.box;
}

// A list as a table, its row's rarer actions in a menu (the owner: 善用 table, menu).
function biListTable(heads) {
  const body = bh("tbody", "");
  const table = bh("table", "bi-table bi-stack",
    bh("thead", "", bh("tr", "", ...heads.map((head) => bh("th", "", head)))), body);
  return {box: bh("div", "bi-scroll", table), body, heads};
}

function biRow(table, cells) {
  const row = bh("tr", "", ...cells.map((cell, index) => {
    const td = bh("td", "", ...(Array.isArray(cell) ? cell : [cell]));
    td.dataset.label = table.heads[index];
    return td;
  }));
  table.body.append(row);
  return row;
}

function biRowDetail(table) {
  // What a row opens: a full-width row under it, empty until then.
  const cell = bh("td", ""); cell.colSpan = table.heads.length;
  const row = bh("tr", "bi-detail-row", cell);
  table.body.append(row);
  return {row, cell};
}

function biRowActions(shown, ...more) {
  // A row's one or two common actions in sight, the rest in a menu, so a first-timer
  // finds them (acceptance F15).
  const rest = more.filter(Boolean);
  const box = bh("div", "bi-actions", ...shown.filter(Boolean));
  if (rest.length === 1) box.append(rest[0]);
  else if (rest.length) {
    box.append(bh("details", "bi-row-menu", bh("summary", "", "更多"),
      bh("div", "bi-actions", ...rest)));
  }
  return box;
}

function biRowMenu(...items) {
  // Only rarer actions, in 更多; a lone one stays a button.
  return biRowActions([], ...items);
}

function biVerAsk(where, label, value, go, run) {
  // One inline question (a purpose, a tag name) under the row that asked it.
  where.querySelector(".bi-ver-ask")?.remove();
  const input = document.createElement("input");
  input.className = "bi-input"; input.maxLength = 500; input.value = value || "";
  input.setAttribute("aria-label", label);
  const row = bh("div", "bi-ver-ask", bh("span", "bi-label", label), input);
  row.append(biButton(go, async () => {
    const answer = input.value.trim();
    if (!answer) { input.focus(); return; }
    await run(answer);
  }, "go"), biButton("取消", () => row.remove()));
  where.append(row); input.focus();
}

function biConfirm(where, question, go, run) {
  // The page's own confirm, in place of the browser's: the question and two buttons, under
  // what asked it. Only the button runs it.
  where.querySelector(":scope > .bi-confirm")?.remove();
  const box = bh("div", "bi-confirm", bh("span", "", question));
  box.setAttribute("role", "group"); box.setAttribute("aria-label", question);
  const yes = biButton(go, () => { box.remove(); return run(); }, "go");
  box.append(yes, biButton("取消", () => box.remove()));
  where.append(box); yes.focus();
  return box;
}

function biPublishWords(name, reply) {
  const missing = reply.summary_missing;
  const counts = missing ? Object.entries(missing.by_type)
    .map(([type, count]) => biTypeLabel(type) + " " + count).join("、") : "";
  return "已發佈「" + name + "」：Agent 現在讀這個版本。"
    + "資料夾裡的 cards/ 是給人看的唯讀頁，要改值請提更正單。"
    + (missing ? "提醒：" + missing.total + " 張卡片還沒有摘要（" + counts + "），不影響發佈。"
      : "");
}

async function biVerRun(vaultId, action, body, done) {
  const reply = await biCall("/api/bi/vaults/" + vaultId + "/" + action, body || {});
  if (done) biNotice(true, typeof done === "function" ? done(reply) : done);
  bi.loaded = {}; biRefreshCounts();
  biVaultState(await call("/api/bi/vaults/" + vaultId + "/status"));
  return reply;
}

async function biVersions(vaultId) {
  const seq = bi.verSeq = (bi.verSeq || 0) + 1;
  const [pending, history] = await Promise.all([
    call("/api/bi/vaults/" + vaultId + "/pending"),
    call("/api/bi/vaults/" + vaultId + "/history?limit=30")]);
  if (seq !== bi.verSeq) return;
  bi.verVault = vaultId;
  const box = el("bi-b-ver-pending"); box.replaceChildren();
  const changes = pending.uncommitted || [], commits = pending.commits || [];
  if (!changes.length && !commits.length) {
    box.append(bh("p", "bi-meta", "沒有：大家看到的就是你的內容。"));
  }
  if (changes.length) {
    const counts = new Map();
    for (const change of changes) {
      for (const home of (change.homes || []).length ? change.homes : ["其他"]) {
        counts.set(home, (counts.get(home) || 0) + 1);
      }
    }
    box.append(bh("p", "", "還沒 commit 的改動 " + changes.length + " 項："),
      bh("p", "bi-meta",
        [...counts].map(([home, count]) => biHomeLabel(home) + " " + count + " 項").join("・")));
    // Commit carries all of it, whichever domain is chosen.
    const scope = biScope();
    if (scope && changes.some((c) => (c.homes || []).length && !c.homes.includes(scope))) {
      box.append(bh("p", "bi-warn", "這次 commit 也會帶上其他領域的改動。"));
    }
    box.append(biVerChanges(changes));
  }
  if (commits.length) {
    const list = bh("ul", "bi-log");
    for (const item of commits) {
      list.append(bh("li", "me", bh("strong", "", item.purpose), "・" + biTime(item.created)
        + "・" + (item.ops || []).length + " 項（已 commit，還沒 push）"));
    }
    box.append(bh("p", "", "已 commit、還沒 push 的 " + commits.length + " 個："), list);
  }
  el("bi-b-ver-commit").disabled = !changes.length;
  el("bi-b-ver-discard").disabled = !changes.length;
  el("bi-b-ver-push").disabled = !commits.length;
  biVerHistory(vaultId, history);
  biShareLoad(vaultId).catch((failure) => biNotice(false, "讀不到分享的內容：" + failure.message));
  biSkills(vaultId).catch((failure) => biNotice(false, "讀不到判讀規則：" + failure.message));
  biProfiles(vaultId).catch((failure) => biNotice(false, "讀不到 profile：" + failure.message));
  biTools(vaultId).catch((failure) => biNotice(false, "讀不到資料處理程式：" + failure.message));
}

function biVerHistory(vaultId, history) {
  const box = el("bi-b-ver-history"); box.replaceChildren();
  const tags = history.tags || [], published = history.published;
  const byCommit = {};
  for (const tag of tags) (byCommit[tag.commit] = byCommit[tag.commit] || []).push(tag);
  const live = (tag) => Boolean(published && published.tag === tag.name);
  const list = biListTable(["版本", "時間", "作者", "項數", "動作"]);
  (history.commits || []).forEach((commit, index) => {
    const badges = (byCommit[commit.id] || []).map((tag) =>
      biBadge("tag " + tag.name + (live(tag) ? "・發佈中" : ""), live(tag) ? "good" : ""));
    const actions = [], publishes = [];
    const shown = biRow(list, [[bh("strong", "", commit.purpose), " ", ...badges,
      commit.kind === "revert" ? bh("span", "bi-meta", "・回復版本") : ""],
    biTime(commit.created), commit.author, String(commit.units), ""]);
    const under = biRowDetail(list), row = under.cell, detail = bh("div", "");
    row.append(detail);
    const look = biButton("看改動", async () => {
      if (detail.childNodes.length) { detail.replaceChildren(); return; }
      const reply = await call("/api/bi/vaults/" + vaultId + "/diff?commit="
        + encodeURIComponent(commit.id));
      detail.replaceChildren(biVerChanges(reply.changes || []));
    }, "bi-btn", "看「" + commit.purpose + "」的改動");
    if (index > 0) {
      actions.push(biButton("回到這個版本", () => biVerAsk(row, "回復的目的",
        "回到「" + commit.purpose + "」的版本", "回復（成為新的 commit）", (purpose) =>
          biVerRun(vaultId, "revert", {version: commit.id, purpose},
            "已回復成新的 commit；按「Push 給大家」送出。")),
      "bi-btn", "回到「" + commit.purpose + "」的版本"));
    }
    actions.push(biButton("加 tag", () => biVerAsk(row,
      "tag 名稱（小寫英數字與 . -，例如 2026q4）", "", "建立 tag", (name) =>
        biVerRun(vaultId, "tag", {name, version: commit.id, purpose: commit.purpose},
          "已建立 tag「" + name + "」；要讓 Agent 讀它，請按「發佈 " + name + "」。")),
    "bi-btn", "幫「" + commit.purpose + "」加 tag"));
    for (const tag of byCommit[commit.id] || []) {
      if (live(tag)) continue;
      publishes.push(biButton("發佈 " + tag.name, () => biConfirm(row,
        "發佈 tag「" + tag.name + "」？發佈後 Agent 只讀這個版本的內容；要撤回就再發佈另一個 tag。",
        "確定發佈", () => biVerRun(vaultId, "publish", {tag: tag.name, confirm: true},
          (reply) => biPublishWords(tag.name, reply))), "bi-btn", "發佈 tag " + tag.name));
    }
    shown.lastChild.append(biRowActions([look, publishes[0]], ...publishes.slice(1),
      ...actions));
  });
  box.append((history.commits || []).length ? list.box : bh("p", "bi-meta", "還沒有 commit。"));
}

// -- 分享: commit, push, tag and publish as one step (BI_PAGE_SIMPLE.md S6) ---------------
const BI_SHARE_STEPS = [["commit", "Commit"], ["push", "Push 給大家"], ["tag", "建立 tag"],
  ["publish", "發佈"]];
const BI_TEST_STATE = {passed: ["通過", "good"], regressed: ["退步", "warn"],
  untested: ["沒有測試", "dim"], stale: ["舊結果", "warn"]};

function biShareTagName(taken) {
  // Today's local date; a suffix when that tag is taken (a tag never moves).
  const now = new Date(), two = (n) => String(n).padStart(2, "0");
  const day = now.getFullYear() + "-" + two(now.getMonth() + 1) + "-" + two(now.getDate());
  let name = day;
  for (let n = 2; taken.includes(name); n += 1) name = day + "-" + n;
  return name;
}

function biShareHomes(homes) {
  if (!homes.length) return "—";
  return homes.includes("*") ? "全部領域" : homes.map(biHomeLabel).join("、");
}

async function biShareLoad(vaultId) {
  const seq = bi.shareSeq = (bi.shareSeq || 0) + 1;
  const plan = await call("/api/bi/vaults/" + vaultId + "/share");
  if (seq !== bi.shareSeq || vaultId !== bi.verVault) return;
  bi.share = plan; bi.shareVault = vaultId;
  biShareDraw(plan);
}

function biShareDraw(plan) {
  // Drawn again when the domains' names arrive (`biSourceFolders`): before, a home shows its key.
  const list = el("bi-b-share-list"); list.replaceChildren();
  const commits = plan.commits || [];
  list.append(bh("p", "", plan.published
    ? "上次發佈「" + plan.published.tag + "」之後的內容："
    : "還沒有發佈過，這次會分享的內容："));
  if (commits.length || plan.uncommitted) {
    const table = biListTable(["內容", "作者", "領域", "狀態"]);
    if (plan.uncommitted) {
      biRow(table, [bh("strong", "", "還沒 commit 的改動 " + plan.uncommitted + " 項"),
        "你", biShareHomes(plan.uncommitted_homes || []), "分享時會先 commit"]);
    }
    for (const commit of commits) {
      biRow(table, [[bh("strong", "", commit.purpose), bh("div", "bi-meta",
        biTime(commit.created) + "・" + commit.units + " 項")], commit.author,
      biShareHomes(commit.homes || []), commit.pushed ? "已 push" : "還沒 push"]);
    }
    list.append(table.box);
    if (plan.older) list.append(bh("p", "bi-meta", "更早的還有 " + plan.older + " 個 commit。"));
  } else {
    list.append(bh("p", "bi-meta", "沒有新的內容：大家與 Agent 讀到的就是現在的內容。"));
  }
  const tests = el("bi-b-share-tests"); tests.replaceChildren();
  const standing = plan.standing || {};
  if (plan.running) {
    tests.append(bh("p", "bi-meta", "測試還在跑；跑完再看各領域的結果。"));
  } else if ((plan.domains || []).length) {
    const table = biListTable(["領域", "測試"]);
    for (const item of plan.domains) {
      const [word, cls] = BI_TEST_STATE[item.state] || [item.state, ""];
      const said = [biBadge(word, cls)];
      if (item.tested) said.push(" " + item.passed + "/" + item.tested + " 題通過");
      if (item.questions > item.tested) {
        said.push(bh("span", "bi-meta", "・" + (item.questions - item.tested) + " 題沒有測"));
      }
      for (const question of item.regressed || []) {
        said.push(bh("div", "bi-warn", "「" + question + "」發佈版本答得對，這次的內容答錯"));
      }
      biRow(table, [item.home ? biHomeLabel(item.home) : "不分領域", said]);
    }
    tests.append(table.box);
    if (plan.domains.some((item) => item.state === "stale")) {
      tests.append(bh("p", "bi-meta",
        "舊結果：之後發佈了新版本或內容改了，這些結果不是現在的狀態。"),
        bh("div", "bi-actions", biButton("重新跑測試", () => el("bi-b-bench-run").click(),
          "bi-btn", "重新跑測試")));
    }
  }
  for (const line of standing.blocking || []) tests.append(bh("p", "bi-warn", line));
  for (const line of standing.notes || []) tests.append(bh("p", "bi-meta", line));
  const tag = el("bi-b-share-tag");
  if (!tag.dataset.edited || (plan.tags || []).includes(tag.value.trim())) {
    tag.value = biShareTagName(plan.tags || []); delete tag.dataset.edited;
  }
  const why = !commits.length && !plan.uncommitted ? "沒有新的內容要分享。"
    : (standing.blocking || []).length
      ? "這次的內容在它改到的領域測試退步，push 會被擋下；請先修正或再跑一次測試。" : "";
  el("bi-b-share-why").textContent = why;
  el("bi-b-share-go").disabled = Boolean(why) || Boolean(bi.shareBusy);
  biKeepVersion();
}

function biShareProgress(skipCommit) {
  const box = el("bi-b-share-progress"); box.replaceChildren(); box.hidden = false;
  const items = {};
  for (const [step, label] of BI_SHARE_STEPS) {
    const item = bh("li", "", label + "：", bh("span", "", ""));
    item.dataset.step = step;
    items[step] = item; box.append(item);
  }
  const mark = (step, state, words) => {
    items[step].dataset.state = state;
    items[step].lastChild.textContent = words;
  };
  for (const [step] of BI_SHARE_STEPS) mark(step, "waiting", "等待");
  if (skipCommit) mark("commit", "skipped", "不需要（沒有還沒 commit 的改動）");
  return mark;
}

async function biShare(vaultId, purpose, name) {
  // In order, stopping at the first that fails; each says done, failed or not done.
  const plan = bi.share || {};
  const mark = biShareProgress(!plan.uncommitted);
  const done = [], label = Object.fromEntries(BI_SHARE_STEPS);
  let step = "commit";
  bi.shareBusy = true; el("bi-b-share-go").disabled = true;
  try {
    if (plan.uncommitted) {
      mark(step, "running", "進行中…");
      await biCall("/api/bi/vaults/" + vaultId + "/commit", {purpose});
      mark(step, "done", "完成"); done.push(step);
    }
    step = "push"; mark(step, "running", "進行中…");
    const pushed = await biCall("/api/bi/vaults/" + vaultId + "/push", {});
    biVerConflicts(vaultId, pushed.status === "conflicts" ? pushed.conflicts || [] : []);
    if (pushed.status === "blocked") throw new Error((pushed.blocking || []).join("；"));
    if (pushed.status === "conflicts") {
      throw new Error("有 " + (pushed.conflicts || []).length + " 個地方別人也改了，"
        + "請在下面每一項選一邊，再按一次「分享」");
    }
    const notes = (pushed.notes || []).join("；");
    mark(step, "done", (pushed.status === "nothing" ? "完成（已經 push 過）" : "完成")
      + (notes ? "・" + notes : "")); done.push(step);
    step = "tag"; mark(step, "running", "進行中…");
    const newest = (plan.commits || [])[0];
    await biCall("/api/bi/vaults/" + vaultId + "/tag",
      {name, purpose: purpose || (newest ? newest.purpose : "分享 " + name)});
    mark(step, "done", "完成「" + name + "」"); done.push(step);
    step = "publish"; mark(step, "running", "進行中…");
    const reply = await biCall("/api/bi/vaults/" + vaultId + "/publish",
      {tag: name, confirm: true});
    mark(step, "done", "完成"); done.push(step);
    el("bi-b-ver-purpose").value = ""; delete el("bi-b-share-tag").dataset.edited;
    biNotice(true, biPublishWords(name, reply));
  } catch (failure) {
    mark(step, "failed", "停下：" + failure.message);
    const left = BI_SHARE_STEPS.map(([key]) => key)
      .filter((key) => key !== step && !done.includes(key)
        && !(key === "commit" && !plan.uncommitted));
    for (const key of left) mark(key, "waiting", "沒有做");
    biNotice(false, "分享停在「" + label[step] + "」：" + failure.message + "。已完成："
      + (done.map((key) => label[key]).join("、") || "沒有") + "；沒有做："
      + [step, ...left].map((key) => label[key]).join("、") + "。");
  } finally {
    bi.shareBusy = false;
    bi.loaded = {}; biRefreshCounts();
    biVaultState(await call("/api/bi/vaults/" + vaultId + "/status"));
  }
}

el("bi-b-share-tag").addEventListener("input", (event) => {
  event.currentTarget.dataset.edited = "1";
});
el("bi-b-share-go").addEventListener("click", () => {
  const vaultId = bi.verVault, plan = bi.share || {};
  const input = el("bi-b-ver-purpose"), purpose = input.value.trim();
  const tag = el("bi-b-share-tag"), name = tag.value.trim();
  if (plan.uncommitted && !purpose) {
    biNotice(false, "請先寫這次改動的目的（commit 一定要寫）。"); input.focus(); return;
  }
  if (!/^[a-z0-9]+(?:[.-][a-z0-9]+)*$/.test(name) || name.length > 60) {
    biNotice(false, "版本名稱只能用小寫英數字與 . -（最多 60 個字），例如 2026-11-06。");
    tag.focus(); return;
  }
  if ((plan.tags || []).includes(name)) {
    biNotice(false, "版本名稱「" + name + "」已經用過；tag 不能移動，請換一個。");
    tag.focus(); return;
  }
  const steps = (plan.uncommitted ? "commit " + plan.uncommitted + " 項改動、" : "")
    + "push、建立 tag「" + name + "」並發佈";
  biConfirm(el("bi-b-share-act"), "要分享嗎？會依序 " + steps + "；發佈後 Agent 讀這個版本。",
    "確定分享", () => biShare(vaultId, purpose, name));
});

function biVerConflicts(vaultId, conflicts) {
  bi.verPushConflicts = conflicts;
  biVerConflictList(vaultId);
}

function biVerSchemaConflicts(vaultId, list) {
  // Schema changes that landed with nobody to stop them (`BI_CARD_MODEL.md` §4.3).
  if (!list.length) return null;
  const rows = bh("ul", "bi-log");
  const decide = async (conflict, choice, done) => {
    try {
      const reply = await biCall("/api/bi/vaults/" + vaultId + "/schema-conflicts",
        {unit: conflict.unit, choice});
      biNotice(true, done + "commit 並 push 後大家才會用到。");
      biVaultState(reply.status);
    } catch (failure) { biNotice(false, "沒有決定：" + failure.message); }
  };
  for (const conflict of list) {
    const label = conflict.label || conflict.unit;
    const row = bh("li", "", bh("strong", "", label), bh("p", "bi-meta", conflict.reason || ""),
      biVerValue(conflict.value));
    const actions = bh("div", "bi-actions");
    if (conflict.kind === "clash") {
      actions.append(biButton("放棄這個改動", () => decide(conflict, "drop", "已放棄這個改動；"),
        "bi-btn", "放棄這個改動：" + label));
    } else {
      row.append(bh("div", "bi-meta", "現在的"), biVerValue(conflict.current));
      actions.append(
        biButton("留下現在的", () => decide(conflict, "keep", "已留下現在的；"),
          "bi-btn", "留下現在的：" + label),
        biButton("改用另一個", () => decide(conflict, "take", "已改用另一個；"),
          "bi-btn", "改用另一個：" + label));
    }
    row.append(actions); rows.append(row);
  }
  return [bh("p", "bi-warn", "schema 的改動有 " + list.length + " 個要決定：已經送出的改動"
    + "互相衝突，決定之前，這些改動不會生效。"), rows];
}

function biVerConflictList(vaultId) {
  // Push conflicts side by side: nothing was written until each is decided.
  const box = el("bi-b-ver-conflicts"); box.replaceChildren();
  const landed = biVerSchemaConflicts(vaultId, bi.verSchemaConflicts || []);
  if (landed) box.append(...landed);
  const conflicts = bi.verPushConflicts || [];
  if (!conflicts.length) return;
  const decided = {};
  box.append(bh("p", "bi-warn", "沒有送出：有 " + conflicts.length + " 個地方別人也改了。"
    + "每一項選一邊（或自己填），再按「Push 給大家」。"));
  const list = bh("ul", "bi-log");
  for (const conflict of conflicts) {
    const label = conflict.label || conflict.unit;
    const mine = bh("div", "", bh("div", "bi-meta", "你的（" + conflict.purpose + "）"),
      biVerValue(conflict.mine));
    const theirs = bh("div", "", bh("div", "bi-meta", "別人已 push 的"),
      biVerValue(conflict.theirs));
    const choose = async (choice, value) => {
      await biCall("/api/bi/vaults/" + vaultId + "/resolve", {unit: conflict.unit, choice, value});
      decided[conflict.unit] = choice;
      mine.classList.toggle("chosen", choice === "mine");
      theirs.classList.toggle("chosen", choice === "theirs");
      const left = conflicts.filter((c) => !decided[c.unit]).length;
      biNotice(true, left ? "已決定；還有 " + left + " 項。"
        : "全部決定了，按「Push 給大家」送出。");
    };
    const row = bh("li", "", bh("strong", "", label), bh("div", "bi-ver-pair", mine, theirs));
    const actions = bh("div", "bi-actions",
      biButton("用我的", () => choose("mine"), "bi-btn", "用我的：" + label),
      biButton("用別人的", () => choose("theirs"), "bi-btn", "用別人的：" + label));
    const own = conflict.mine;
    if (own && typeof own === "object" && "value" in own
      && (own.value === null || typeof own.value !== "object")) {
      // A field: keep my source and history, change only the value.
      actions.append(biButton("自己填", () => biVerAsk(row, "新的值", "", "用這個值",
        (typed) => choose("value", {...own, value: typed})), "bi-btn", "自己填：" + label));
    }
    row.append(actions); list.append(row);
  }
  box.append(list);
}

// -- skills in the vault (knowledge repositories R3, KNOWLEDGE_REPO.md §8) -------
async function biSkills(vaultId) {
  const reply = await call("/api/bi/vaults/" + vaultId + "/skills");
  bi.skills = reply;
  biSkillsDraw(reply);
}

function biFolderName(folder) {
  // A folder by the name people know it by; one outside the homes as it is.
  const home = biFolderHome(folder);
  const item = (bi.build.homes || []).find((found) => found.home === home);
  if (item) return item.label;
  // Not a home of this vault: its own name, without the folders around it.
  const parts = String(folder).split("/").filter((part) => part
    && !["sources", "applications", "library"].includes(part));
  return parts.length ? parts.join(" / ") : "所有來源";
}

function biSkillsDraw(reply) {
  biScopeEmpty();
  const box = el("bi-b-sk-list"); box.replaceChildren();
  const list = biListTable(["規則", "種類", "版本", "套用到", "狀態", "動作"]);
  const scope = biScope();
  // What applies to every source (the classify skill) is every domain's.
  const skills = (reply.skills || []).filter((item) => !scope || !(item.applies_to || []).length
    || item.applies_to.some((folder) => biFolderHome(folder) === scope));
  for (const item of skills) {
    const where = (item.applies_to || []).length
      ? item.applies_to.flatMap((folder, at) => {
        const name = bh("span", "", biFolderName(folder)); name.title = folder;
        return at ? ["、", name] : [name];
      }) : "所有來源";
    const state = [];
    if (item.generated) state.push(biBadge("依 schema 產生", "dim"));
    if (item.needs_update && item.update_blocks === false) {
      state.push(biBadge("可以看一下", "dim"), bh("p", "bi-meta", item.update_reason || ""));
    } else if (item.needs_update) {
      state.push(biBadge("需要更新", "warn"), bh("p", "bi-meta", (item.update_reason
        ? item.update_reason + "；" : "知識庫現在用 " + reply.schema + "；")
        + "修改並儲存後才會再使用"));
    }
    if (item.problem) state.push(bh("p", "bi-warn", item.problem));
    if (item.run_types) {
      // What a run with it really produces (acceptance F17), whatever card_types says.
      state.push(bh("p", "bi-meta", "產生：" + item.run_types.types.join("、")
        + ({skill: "", profile: "（依領域 profile）", default: "（預設類型）"}[item.run_types.from]
          || "")));
    }
    const edit = bh("button", "bi-btn", "修改");
    edit.type = "button";
    edit.addEventListener("click", () => {
      el("bi-b-adv-skills").open = true; biSkillForm(item);
    });
    const talk = biButton("和 AI 一起修改", (event) => biSkillAi(item, event.currentTarget),
      "bi-btn",
      "和 AI 一起修改判讀規則 " + item.name);
    biRow(list, [bh("strong", "", item.name), item.role === "classify" ? "分類" : "擷取",
      "第 " + item.revision + " 版", where, state, biRowActions([edit, talk])]);
  }
  box.append(skills.length ? list.box : bh("p", "bi-meta", "還沒有判讀規則。"));
  if (skills.length < (reply.skills || []).length) {
    box.append(bh("p", "bi-meta", "其他領域還有 " + ((reply.skills || []).length - skills.length)
      + " 條，選「全部領域」可以看。"));
  }
  const pick = el("bi-b-folder"), kept = pick.value;
  pick.replaceChildren(...(reply.folders || ["sources"]).map((f) => {
    const option = bh("option", "", f === "sources" ? "（不指定資料夾）" : f);
    option.value = f; return option;
  }));
  if ((reply.folders || []).includes(kept)) pick.value = kept;
  biFollowSourceFolder();
  el("bi-b-folder-box").hidden = false;
  biRerunForm(reply.folders || []);
}

function biFollowSourceFolder() {
  // The run's folder decides whose skill and profile apply: it starts as the source's own.
  const pick = el("bi-b-folder");
  const chosen = (bi.build.sources || []).find((s) => s.id === bi.build.sourceId);
  if (!chosen || !chosen.folder || !pick.options.length) return;
  if (![...pick.options].some((o) => o.value === chosen.folder)) {
    const option = bh("option", "", chosen.folder);
    option.value = chosen.folder; pick.append(option);
  }
  pick.value = chosen.folder;
}

// -- a home's data-processing tools (BI_CARD_MODEL.md P2-a) -------------------------
async function biTools(vaultId) {
  const reply = await call("/api/bi/vaults/" + vaultId + "/tools");
  bi.toolsReply = {vaultId, reply};
  biToolsDraw(vaultId, reply);
}

function biToolsDraw(vaultId, reply) {
  const box = el("bi-b-tl-list"); box.replaceChildren();
  const runOn = async (item) => {
    if (!bi.build.sourceId) { biNotice(false, "請先在上面選一份來源。"); return; }
    try {
      const done = await biVerRun(vaultId, "tool-run",
        {name: item.name, source_id: bi.build.sourceId});
      bi.build.sourceId = done.sources[0].id;
      await biBuildSources();
      biBuildSave();
      biNotice(true, "產出新來源並已選取：" + done.sources.map((s) => s.name).join("、")
        + "；接著走一樣的試跑、預覽和審核。");
    } catch (failure) { biNotice(false, "工具處理未完成：" + failure.message); }
  };
  const list = biListTable(["程式", "狀態", "動作"]);
  const row = (item, draft) => {
    const title = item.name + (draft ? "（AI 提出的草稿）" : "（第 " + item.revision + " 版）");
    const code = bh("pre", "bi-meta", item.code || item.problem || "");
    const actions = [];
    if (!draft && item.code && !item.problem) {
      actions.push(biButton("對選取的來源執行", () => runOn(item), "bi-btn", "執行：" + item.name));
    }
    if (draft) {
      actions.push(biButton("填入下面，存成新版本", () => {
        el("bi-b-adv-skills").open = true;
        el("bi-b-tl-name").value = item.name; el("bi-b-tl-code").value = item.code;
      }, "bi-btn", "填入：" + item.name));
    }
    biRow(list, [bh("strong", "", title),
      item.problem ? biBadge("程式無法讀取", "warn") : biBadge("不需核准", "good"),
      biRowActions(actions)]);
    // Code stays inspectable; historical review metadata does not admit execution.
    const shown = bh("details", "", bh("summary", "", "程式碼"), code);
    shown.open = Boolean(item.code && !item.approved);
    if (shown.open) {
      shown.append(bh("p", "bi-meta", "直接執行工具；若環境不支援，會顯示實際錯誤。"
        + "輸出維持新來源的預覽與審核流程，不會自動變更知識卡。"));
    }
    biRowDetail(list).cell.append(shown);
  };
  const scope = biScope();
  const tools = (reply.tools || []).filter((tool) => !scope
    || String(tool.name).slice(0, String(tool.name).lastIndexOf("/")) === scope);
  for (const tool of tools) row(tool, false);
  for (const draft of reply.drafts || []) row(draft, true);
  box.append(tools.length + (reply.drafts || []).length ? list.box
    : bh("p", "bi-meta", "還沒有資料處理程式。"));
}

el("bi-b-tl-save").addEventListener("click", async () => {
  const parts = el("bi-b-tl-name").value.trim().split("/");
  const name = parts.pop(), home = parts.join("/");
  try {
    const reply = await biVerRun(bi.verVault, "tools",
      {home, name, suffix: ".py", text: el("bi-b-tl-code").value});
    biNotice(true, "「" + reply.tool.name + "」存成第 " + reply.tool.revision
      + " 版；commit 並 push 後大家才會用到。");
    el("bi-b-tl-code").value = "";
  } catch (failure) { biNotice(false, "沒有儲存：" + failure.message); }
});

// -- a home's profile and its field proposals (BI_CARD_MODEL.md §4.2, §4.3) --------
async function biProfiles(vaultId) {
  bi.profiles = await call("/api/bi/vaults/" + vaultId + "/profiles");
  const pick = el("bi-b-pf-home"), kept = pick.value, homes = bi.profiles.homes || [];
  pick.replaceChildren(...homes.map((item) => {
    const option = bh("option", "", item.label === item.home ? item.home
      : item.label + "（" + item.home + "）");
    option.value = item.home; return option;
  }));
  if (homes.some((item) => item.home === kept)) pick.value = kept;
  if (homes.some((item) => item.home === biScope())) pick.value = biScope();
  biProfileShow();
}

function biProfileShow() {
  const home = el("bi-b-pf-home").value;
  const current = ((bi.profiles || {}).profiles || []).find((p) => p.home === home);
  const view = el("bi-b-pf-view"); view.replaceChildren();
  if (!current) {
    view.append(bh("p", "bi-meta", "這裡還沒有 profile：AI 會用整份 schema 判讀。"));
  } else {
    view.append(bh("p", "bi-meta", "第 " + current.revision + " 版・schema " + current.schema));
    const list = bh("ul", "bi-log");
    for (const [type, used] of Object.entries(current.types || {})) {
      const row = bh("li", "", bh("strong", "", biTypeLabel(type) + "（" + type + "）"));
      if (used.category) row.append(bh("p", "bi-meta", used.category));
      const names = Object.entries(used.fields || {});
      row.append(names.length ? bh("ul", "", ...names.map(([name, field]) => bh("li", "",
        name, " ",
        field.use === "required" ? biBadge("必填", "warn") : biBadge("選填", "dim"),
        field.note ? bh("span", "bi-meta", " " + field.note) : "")))
        : bh("p", "bi-meta", "沒有列欄位。"));
      if ((used.not_applicable || []).length) {
        row.append(bh("p", "bi-meta", "不適用：" + used.not_applicable.map((item) => item.field
          + (item.reason ? "（" + item.reason + "）" : "")).join("、")));
      }
      list.append(row);
    }
    view.append(list);
  }
  biProfileProposals(home, current);
  // A refresh keeps what the person is typing; only another version replaces it.
  const shown = home + "#" + (current ? current.revision : 0);
  if (bi.profileShown !== shown) {
    bi.profileShown = shown;
    el("bi-b-pf-json").value = JSON.stringify(current
      ? {types: current.types || {}, proposals: current.proposals || []}
      : {types: {}, proposals: []}, null, 2);
  }
}

function biProfileProposals(home, current) {
  const box = el("bi-b-pf-proposals"); box.replaceChildren();
  const waiting = ((current || {}).proposals || []).filter((p) => p.status === "proposed");
  if (!waiting.length) return;
  const decide = async (item, decision) => {
    try {
      const reply = await biVerRun(bi.verVault, "profile-proposals",
        {home, type: item.type, field: item.field, decision, confirm: true});
      const behind = reply.skills_need_update || [];
      biNotice(true, (decision === "merge"
        ? "已合併「" + item.field + "」，schema 是 " + reply.schema
        : "已不採用「" + item.field + "」") + "；commit 並 push 後大家才會用到。"
        + (behind.length ? "這些判讀規則要更新後才會再使用：" + behind.join("、") : ""));
    } catch (failure) { biNotice(false, "沒有完成：" + failure.message); }
  };
  box.append(bh("h5", "", "等待決定的新欄位"), bh("ul", "bi-log", ...waiting.map((item) => {
    const name = item.type + "." + item.field;
    return bh("li", "", bh("strong", "", name),
      bh("p", "bi-meta", (item.reason ? item.reason + "・" : "") + JSON.stringify(item.definition)),
      bh("div", "bi-actions",
        biButton("合併進 schema", () => decide(item, "merge"), "bi-btn", "合併進 schema：" + name),
        biButton("不採用", () => decide(item, "reject"), "bi-btn", "不採用：" + name)));
  })));
}

el("bi-b-pf-home").addEventListener("change", biProfileShow);
el("bi-b-pf-save").addEventListener("click", async () => {
  const home = el("bi-b-pf-home").value;
  let document_;
  try { document_ = JSON.parse(el("bi-b-pf-json").value); }
  catch (failure) { biNotice(false, "沒有儲存：內容不是有效的 JSON。"); return; }
  try {
    const reply = await biVerRun(bi.verVault, "profiles", {home, profile: document_});
    biNotice(true, "「" + home + "」的 profile 存成第 " + reply.profile.revision
      + " 版；commit 並 push 後大家才會用到。");
  } catch (failure) { biNotice(false, "沒有儲存：" + failure.message); }
});

function biRerunApplication(folder) {
  const parts = folder.split("/");
  if (parts[0] === "applications" && parts[2] === "sources") return parts[1];
  if (parts[0] === "library" && parts[2] === "sources") return "library/" + parts[1];
  if (parts[0] === "sources" && parts[1] === "applications" && parts[2]) return parts[2];
  return "";
}

function biRerunForm(folders) {
  const pick = el("bi-b-rr-app"), kept = pick.value;
  const names = [...new Set(folders.map(biRerunApplication).filter(Boolean))];
  pick.replaceChildren(...["", ...names].map((name) => {
    const option = bh("option", "", name || "（選下面的來源）"); option.value = name;
    return option;
  }));
  if (names.includes(kept)) pick.value = kept;
  const box = el("bi-b-rr-sources"); box.replaceChildren();
  for (const source of bi.build.sources || []) {
    const tick = document.createElement("input"); tick.type = "checkbox"; tick.value = source.id;
    box.append(bh("label", "bi-meta", tick, " " + source.name), document.createElement("br"));
  }
}

function biRerunScope() {
  const application = el("bi-b-rr-app").value;
  const scope = {dataset: biDataset()};
  if (application) return {...scope, application, all: true};
  const ticked = [...el("bi-b-rr-sources").querySelectorAll("input:checked")];
  return {...scope, sources: ticked.map((t) => t.value)};
}

async function biRerunCount() {
  const out = el("bi-b-rr-out"); out.replaceChildren();
  const scope = biRerunScope();
  try {
    const reply = await biCall("/api/bi/reruns/preview", scope);
    const go = biButton("開始重跑", () => biRerunStart(scope), "go");
    go.id = "bi-b-rr-start";
    out.append(bh("p", "", "共 " + reply.count + " 份來源，每份都會呼叫模型："
      + reply.sources.map((s) => s.name).join("、")), go);
  } catch (failure) { out.append(bh("p", "bi-err", failure.message)); }
}

async function biRerunStart(scope) {
  const out = el("bi-b-rr-out"); out.replaceChildren(bh("p", "bi-meta", "重跑中…"));
  try {
    const reply = await biCall("/api/bi/reruns/preview", {...scope, start: true});
    await biRerunPoll(reply.rerun.id);
  } catch (failure) { out.replaceChildren(bh("p", "bi-err", failure.message)); }
}

async function biRerunPoll(id) {
  const out = el("bi-b-rr-out");
  const reply = await call("/api/bi/reruns/" + id + "?dataset=" + encodeURIComponent(biDataset()));
  const rerun = reply.rerun;
  if (rerun.status === "running") {
    out.replaceChildren(bh("p", "bi-meta", "重跑中："
      + rerun.runs.filter((r) => r.status !== "extracting").length + " / " + rerun.runs.length));
    setTimeout(() => biRerunPoll(id).catch((failure) =>
      out.replaceChildren(bh("p", "bi-err", failure.message))), 2000);
    return;
  }
  biRerunList(rerun);
}

function biRerunList(rerun) {
  const out = el("bi-b-rr-out"); out.replaceChildren();
  for (const run of rerun.runs) {
    if (run.failures || run.error || run.status === "failed") {
      out.append(bh("p", "bi-warn", run.source + "：沒有全部讀完，這裡只比對讀到的部分。"));
    }
  }
  if (!rerun.items.length) {
    out.append(bh("p", "", "沒有和卡片不同的值，不需要寫入。")); return;
  }
  const list = bh("ul", "bi-log");
  const ticks = [];
  for (const item of rerun.items) {
    const tick = document.createElement("input"); tick.type = "checkbox"; tick.value = item.id;
    tick.disabled = Boolean(item.problem);
    ticks.push(tick);
    const proof = (item.evidence || []).map((e) => e.excerpt).filter(Boolean).join("；");
    const skills = (item.skills || []).map((s) => s.name + " 第 " + s.revision + " 版").join("、");
    const row = bh("li", "", bh("label", "", tick, " ", bh("strong", "", item.name), "・"
      + (item.label || item.field) + "：「" + biValue(item.current) + "」→「"
      + biValue(item.new) + "」"));
    if (item.person_set) row.append(" ", biBadge("目前的值是人工設定", "warn"));
    if (item.new_card) row.append(" ", biBadge("新卡片", "dim"));
    row.append(bh("p", "bi-meta", item.source + (skills ? "・" + skills : "")
      + (proof ? "・「" + proof + "」" : "")));
    if (item.problem) row.append(bh("p", "bi-warn", item.problem));
    list.append(row);
  }
  const done = biButton("確認勾選的差異", async () => {
    const items = ticks.filter((t) => t.checked).map((t) => t.value);
    try {
      const reply = await biCall("/api/bi/reruns/" + rerun.id + "/confirm",
        {dataset: biDataset(), items});
      out.replaceChildren(bh("p", "", "已寫入 " + reply.commit.values + " 個值，其他沒有變動。"));
      biLoadCards();
    } catch (failure) {
      out.append(bh("p", "bi-err", failure.code === "cards_changed"
        ? "有卡片在比對後被修改，沒有寫入任何值；請重跑。" : failure.message));
    }
  }, "go");
  done.id = "bi-b-rr-confirm";
  out.append(list, bh("div", "bi-actions", done));
}

function biSkillForm(item) {
  const form = el("bi-b-sk-form");
  form.hidden = false;
  el("bi-b-sk-name").value = item.name;
  el("bi-b-sk-name").readOnly = true;
  el("bi-b-sk-role").value = item.role;
  el("bi-b-sk-applies").value = (item.applies_to || []).join(", ");
  el("bi-b-sk-types").value = (item.card_types || []).join(", ");
  el("bi-b-sk-body").value = item.body || "";
  el("bi-b-sk-folders").textContent = "可用的資料夾：" + ((bi.skills && bi.skills.folders) || [])
    .filter((f) => f !== "sources").join("、");
  biSkillTypesNote();
  el("bi-b-sk-body").focus();
}

const biList = (text) => text.split(/[,，、\n]/).map((s) => s.trim()).filter(Boolean);

function biRunTypes(role, applies, typed) {
  // The card types a run with this rule produces, as ai_runs.run_types decides them
  // (acceptance F17): the rule's, narrowed by the domain's profile, else the profile's,
  // else the defaults.
  if (role !== "extract") return null;
  const s = bi.skills || {}, home = applies.length ? biFolderHome(applies[0]) : "";
  const used = (s.profile_types || {})[home] || [];
  if (used.length) {
    const narrowed = typed.filter((t) => used.includes(t));
    return narrowed.length ? [narrowed, "這條規則"] : [used, "領域 profile"];
  }
  return typed.length ? [typed, "這條規則"] : [s.default_types || [], "預設"];
}

function biSkillTypesNote() {
  const found = biRunTypes(el("bi-b-sk-role").value, biList(el("bi-b-sk-applies").value),
    biList(el("bi-b-sk-types").value));
  el("bi-b-sk-runtypes").textContent = found
    ? "用這條規則擷取會產生：" + found[0].join("、") + "（來自" + found[1] + "）"
    : "分類規則不限定卡片類型。";
}
for (const id of ["bi-b-sk-role", "bi-b-sk-applies", "bi-b-sk-types"]) {
  el(id).addEventListener("input", biSkillTypesNote);
}

el("bi-b-sk-new").addEventListener("click", () => biSkillNew()
  .catch((failure) => biNotice(false, failure.message)));
el("bi-b-rr-count").addEventListener("click", biRerunCount);

// An AI session on a vault skill (knowledge repositories R3): the AI suggests a new
// text; 「套用」 stages the next revision, which is committed and pushed in 「版本」.
function biSkillSpec(dataset) {
  return {kind: "skill", dataset, title: "和 AI 修改規則",
    sends: "這條規則、卡片類型與資料夾、最近兩次試跑的候選卡", agent: true,
    label: "你想怎麼調整這條規則",
    placeholder: "例如：電源相關的規格表，額定功率一律放在 specs 欄位",
    busy: "正在讀來源、用草稿試跑、看測試結果…（每次最多試跑 3 次、約 6 分鐘，"
      + "時間到會先給目前最好的草稿）", render: biApplySkill,
    turn: () => ({source_ids: bi.build.sourceId && biDataset() === dataset
      ? [bi.build.sourceId] : []})};
}

async function biSkillAi(item, from) {
  const name = item.name;
  await biAiOpen({...biSkillSpec("vault-" + bi.verVault), name, from, ref: "skill:" + name,
    about: "規則「" + name + "」第 " + item.revision + " 版"
      + (item.needs_update && item.update_blocks !== false
        ? "（需要更新：寫給 " + item.schema + "，AI 會一起更新）" : "") + "。",
    sessionTarget: () => name});
}

async function biSkillNew() {
  // The new rule is the session's until the person applies a draft (acceptance F16: the
  // first message was saved as revision 1 that nobody approved); applying saves revision 1.
  // The working domain's folder, never another: under 全部領域 the person picks one (F9).
  const pick = el("bi-ai-new-folder"), none = bh("option", "", "（選一個資料夾）");
  none.value = "";
  pick.replaceChildren(none, ...((bi.skills && bi.skills.folders) || [])
    .filter((f) => f !== "sources")
    .map((folder) => { const o = bh("option", "", folder); o.value = folder; return o; }));
  const own = el("bi-b-src-folder").value;
  pick.value = biScope() && [...pick.options].some((option) => option.value === own) ? own : "";
  el("bi-ai-new-name").value = "";
  const spec = {...biSkillSpec("vault-" + bi.verVault), mode: "new", title: "和 AI 新增規則",
    shows: el("bi-b-sk-list"),
    about: "AI 會依你的描述寫出草稿並試跑；按「套用為新版本」才會存成第 1 版（還沒 commit）。",
    label: "這條規則要做什麼", placeholder: "例如：虛構電源廠是 Account",
    sessionTarget: () => spec.name,
    prepare: async (message) => {
      if (spec.name) return;
      const name = el("bi-ai-new-name").value.trim();
      if (!name) { el("bi-ai-new-name").focus(); throw new Error("請寫規則名稱"); }
      if (!pick.value) { pick.focus(); throw new Error("請選這條規則套用到哪個資料夾"); }
      spec.session = (await biCall("/api/bi/sessions", {dataset: spec.dataset, kind: "skill",
        target: name, new: {role: "extract", applies_to: [pick.value]}})).session;
      spec.name = name; spec.mode = null; el("bi-ai-new").hidden = true;
      spec.ref = "skill:" + name;
      biAiTarget("新規則「" + name + "」：套用 AI 的草稿後才會存成第 1 版（還沒 commit）。");
    }};
  await biAiOpen(spec);
}

function biApplySkill(session, turn, index) {
  const s = turn.suggestion;
  const parts = [bh("p", "", bh("strong", "", "AI："), s.reply),
    biListBlock("理由", s.reasons), biListBlock("限制", s.limits),
    biListBlock("需要工程開發（判讀規則做不到，沒有套用）", s.needs_engineering, "bi-warn"),
    bh("strong", "", "套用後的變化"), biMethodDiff(s.result.diff)];
  if (turn.applied) {
    parts.push(bh("p", "bi-meta", "已套用為第 " + turn.applied.revision
      + " 版（commit 並 push 後大家才會用到）。"));
  } else if (s.result.diff.length) {
    parts.push(bh("div", "bi-actions", biButton("套用為新版本", async () => {
      const reply = await biCall("/api/bi/sessions/" + session.id + "/apply",
        {dataset: bi.ai.dataset, turn: index});
      const name = bi.ai.name;
      biAiTarget("規則「" + name + "」第 " + reply.skill.revision + " 版（剛套用，還沒 commit）。");
      biAiShow(reply.session);
      biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
      biNotice(true, "判讀規則「" + name + "」存成第 " + reply.skill.revision
        + " 版；commit 並 push 後大家才會用到。");
    }, "go", "把這個建議套用為判讀規則的新版本")));
  }
  return parts;
}

el("bi-b-sk-cancel").addEventListener("click", () => { el("bi-b-sk-form").hidden = true; });
el("bi-b-sk-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {name: el("bi-b-sk-name").value.trim(), role: el("bi-b-sk-role").value,
    applies_to: biList(el("bi-b-sk-applies").value), card_types: biList(el("bi-b-sk-types").value),
    body: el("bi-b-sk-body").value};
  try {
    const reply = await biVerRun(bi.verVault, "skills", body);
    el("bi-b-sk-form").hidden = true;
    biNotice(true, "判讀規則「" + body.name + "」存成第 " + reply.skill.revision
      + " 版；commit 並 push 後大家才會用到。");
  } catch (failure) { biNotice(false, "沒有儲存：" + failure.message); }
});

el("bi-b-ver-commit").addEventListener("click", async () => {
  const input = el("bi-b-ver-purpose"), purpose = input.value.trim();
  if (!purpose) { biNotice(false, "請先寫這次改動的目的。"); input.focus(); return; }
  try {
    await biVerRun(bi.verVault, "commit", {purpose}, "已 commit；按「Push 給大家」才會送出。");
    input.value = "";
  } catch (failure) { biNotice(false, "沒有 commit：" + failure.message); }
});
el("bi-b-ver-push").addEventListener("click", async () => {
  const vaultId = bi.verVault, button = el("bi-b-ver-push");
  button.disabled = true;
  try {
    const reply = await biVerRun(vaultId, "push", {});
    biVerConflicts(vaultId, reply.status === "conflicts" ? reply.conflicts || [] : []);
    if (reply.status === "pushed") {
      const notes = (reply.notes || []).join("；");
      biNotice(true, "已 push " + (reply.commits || []).length + " 個 commit；要讓 Agent 讀到，"
        + "請加 tag 並發佈。" + (notes ? " " + notes : ""));
    } else if (reply.status === "blocked") {
      biNotice(false, "沒有送出：" + (reply.blocking || []).join("；"));
    } else if (reply.status === "nothing") {
      biNotice(true, "沒有要 push 的 commit。");
    }
  } catch (failure) {
    biNotice(false, "沒有 push：" + failure.message);
    button.disabled = false;
  }
});
el("bi-b-ver-discard").addEventListener("click", () => {
  biConfirm(el("bi-b-adv-ver"), "捨棄這台電腦上還沒 commit 的改動？已 commit 的不受影響。",
    "確定捨棄", async () => {
      try { await biVerRun(bi.verVault, "discard", {}, "已捨棄還沒 commit 的改動。"); }
      catch (failure) { biNotice(false, "沒有捨棄：" + failure.message); }
    });
});

el("bi-b-v-sync").addEventListener("click", async () => {
  const vault = biVaultOf(biDataset()); if (!vault) return;
  try {
    const report = (await biCall("/api/bi/vaults/" + vault.id + "/sync", {})).sync || {};
    biVaultState(await call("/api/bi/vaults/" + vault.id + "/status"));
    biNotice(true, "已同步" + (report.rebuilt ? "（依所有變更檔重建）" : "") + "。");
    bi.loaded = {}; biRefreshCounts();
  } catch (failure) { biNotice(false, "沒有同步：" + failure.message); }
});

function biVaultForm(mode) {
  el("bi-b-v-menu").open = false;
  const form = el("bi-b-v-form"), same = !form.hidden && form.dataset.mode === mode;
  for (const id of ["bi-b-v-new", "bi-b-v-join", "bi-b-v-convert"]) {
    el(id).setAttribute("aria-expanded", String(!same && el(id).dataset.mode === mode));
  }
  if (same) { form.hidden = true; return; }
  const [title, go, pathLabel] = BI_VAULT_MODES[mode];
  form.dataset.mode = mode; form.hidden = false;
  el("bi-b-v-form-h").textContent = title; el("bi-b-v-go").textContent = go;
  el("bi-b-v-path-label").textContent = pathLabel; el("bi-b-v-err").replaceChildren();
  for (const box of form.querySelectorAll("[data-for]")) {
    box.hidden = !box.dataset.for.split(" ").includes(mode);
  }
  const schema = el("bi-b-v-schema"); schema.replaceChildren();
  for (const item of bi.schemas || []) {
    const option = bh("option", "", (item.title || item.id) + "（" + item.ref + "）");
    option.value = item.ref; schema.append(option);
  }
  // A new vault starts on the newest shipped version, not the dataset shown or the oldest.
  const newest = (bi.schemas || []).filter((s) => s.source === "shipped").pop();
  if (newest) schema.value = newest.ref;
  biVaultPathCheck();
  el(mode === "new" ? "bi-b-v-title" : "bi-b-v-path").focus();
}

async function biVaultPathCheck() {
  // The folder as typed, checked here, with this PC's OneDrive to pick (acceptance F3).
  const mode = el("bi-b-v-form").dataset.mode, typed = el("bi-b-v-path").value.trim();
  const seq = bi.pathSeq = (bi.pathSeq || 0) + 1;
  const reply = await call("/api/bi/vaults/folder-check?mode=" + encodeURIComponent(mode)
    + "&path=" + encodeURIComponent(typed)).catch(() => null);
  if (!reply || seq !== bi.pathSeq) return;
  const line = el("bi-b-v-path-check"), suggest = el("bi-b-v-path-suggest");
  line.className = reply.ok ? "bi-meta" : "bi-warn";
  line.textContent = !typed ? "" : reply.ok
    ? (mode === "join" ? "可以用：這是一個 BI 知識庫。"
      : "可以用：知識庫會建成這個資料夾裡的一個新資料夾。")
      + (reply.shared || !reply.suggest.length ? "" : "這裡不在 OneDrive 裡，同事收不到。")
    : reply.problem + "。";
  suggest.replaceChildren(...(mode === "join" || reply.shared ? [] : reply.suggest)
    .map((folder) => biButton("用 OneDrive：" + folder, () => {
      el("bi-b-v-path").value = folder; biVaultPathCheck();
    }, "bi-link")));
}

for (const id of ["bi-b-v-new", "bi-b-v-join", "bi-b-v-convert"]) {
  el(id).addEventListener("click", () => biVaultForm(el(id).dataset.mode));
}
el("bi-b-v-cancel").addEventListener("click", () => biVaultForm(el("bi-b-v-form").dataset.mode));
el("bi-b-v-path").addEventListener("input", () => {
  clearTimeout(bi.pathTimer); bi.pathTimer = setTimeout(biVaultPathCheck, 300);
});
el("bi-b-v-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const mode = el("bi-b-v-form").dataset.mode, err = el("bi-b-v-err"); err.replaceChildren();
  const body = {path: el("bi-b-v-path").value.trim(), author: el("bi-b-v-author").value.trim()};
  if (!body.path) { err.append(bh("p", "bi-err", "請填資料夾路徑。")); return; }
  if (mode === "new") {
    Object.assign(body, {title: el("bi-b-v-title").value.trim(),
      purpose: el("bi-b-v-purpose").value.trim(), schema: el("bi-b-v-schema").value});
    if (!body.title) { err.append(bh("p", "bi-err", "請填知識庫名稱。")); return; }
    const id = el("bi-b-v-id").value.trim();
    if (id) body.id = id;
    // A name with no letters would become an id like vault-199bbd (acceptance F4).
    const slug = body.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    if (!id && !slug) {
      err.append(bh("p", "bi-err", "名稱是中文：請填知識庫 id（英數字與 -，例如 market-intel）。"));
      el("bi-b-v-id").focus(); return;
    }
  }
  if (mode === "convert") {
    Object.assign(body, {dataset: biDataset(), purpose: el("bi-b-v-purpose").value.trim()});
  }
  if (mode === "join") body.resume = el("bi-b-v-resume").checked;
  const button = el("bi-b-v-go"); button.disabled = true;
  try {
    const path = {new: "/api/bi/vaults", join: "/api/bi/vaults/join",
      convert: "/api/bi/vaults/convert"}[mode];
    const reply = await biCall(path, body);
    el("bi-b-v-form").hidden = true;
    biNotice(true, {new: "已建立", join: "已加入", convert: "已轉成"}[mode] + "共用知識庫「"
      + (reply.vault.title || reply.vault.id) + "」：" + reply.vault.path
      + (mode === "convert" ? "（原本的資料集沒有改動；帶過 " + reply.sources.copied + " 份來源"
        + (reply.sources.skipped ? "，" + reply.sources.skipped + " 份的檔案不見了、沒有帶過"
          : "")
        + (reply.sources.error ? "，來源沒有帶過，請重新加入" : "") + "）" : ""));
    if (mode === "convert" && bi.build.sourceId) {
      // The sources came along under the same ids, so what was chosen stays chosen.
      try {
        localStorage.setItem("bi-build-" + reply.vault.dataset,
          JSON.stringify({stage: "source", sourceId: bi.build.sourceId, runId: null}));
      } catch (e) { /* no storage */ }
    }
    if (mode !== "convert") bi.vaultArrived = reply.vault.dataset;
    bi.want = reply.vault.dataset; await biLoad();
  } catch (failure) {
    err.append(bh("p", "bi-err", failure.message + "。"));
  } finally { button.disabled = false; }
});

// -- step 1: sources ---------------------------------------------------------
const BI_SHARED = {local: "只在這台電腦", staged: "commit、push 後才會放上去",
  pushed: "已放上去", cloud_only: "只在雲端"};

// -- the working domain (BI_PAGE_SIMPLE.md §9): one home, per person and per PC ------
function biFolderHome(folder) {
  // `homes.home_of`: the home a source folder lies in, also from before the homes.
  const found = new RegExp("^(?:applications/([^/]+)/|library/(?!skills/)([^/]+)/"
    + "|sources/applications/([^/]+)(?:/|$)|sources/library/([^/]+)(?:/|$))")
    .exec(String(folder || ""));
  if (!found) return null;
  return found[1] || found[3] || "library/" + (found[2] || found[4]);
}

function biScope() {
  // The home chosen; null for 全部領域 and where there is no choice to make.
  return el("bi-b-src-folder-box").hidden ? null : biFolderHome(el("bi-b-src-folder").value);
}

function biInScope(home) {
  // What has no home belongs to the whole vault, so every working domain has it.
  const scope = biScope();
  return !scope || !home || home === scope;
}

function biSourceInScope(source) {
  // A source still only on this PC has no home yet; sharing it gives it this one.
  const scope = biScope();
  return !scope || source.shared === "local" && !source.folder
    || biFolderHome(source.folder) === scope;
}

function biScopeKey() { return "bi-scope-" + biDataset(); }

function biAddReady() {
  // A file added to no home gets no skill and no profile; a vault with no homes has no choice.
  return !biVaultOf(biDataset()) || !(bi.build.homes || []).length || Boolean(biScope());
}

function biScopeDomain() {
  const item = (bi.build.homes || []).find((home) => home.home === biScope());
  return item ? item.domain : null;
}

function biDashDomainBox() {
  // A working domain with a card domain decides the Dashboard's, so there is nothing to choose.
  const schema = bi.schema || {};
  el("bi-domain-box").hidden = Boolean(biScopeDomain())
    || (Array.isArray(schema.domains) && !schema.domains.length);
}

function biScopeFollowed() {
  // The tabs follow once per choice. The Dashboard's domain is the working domain's; the card
  // tab's filter starts on it and stays the person's to change, until the next choice.
  const chosen = el("bi-b-src-folder").value;
  if (bi.build.scopeSet === chosen) return;
  bi.build.scopeSet = chosen;
  const wanted = String(biScopeDomain() || "").toLowerCase();
  const option = [...el("bi-domain").options].find((o) => o.value.toLowerCase() === wanted);
  if (wanted && option && el("bi-domain").value !== option.value) {
    el("bi-domain").value = option.value;
    if (bi.loaded) bi.loaded.dashboard = false;
  }
  const filter = el("bi-card-domain");
  const own = [...filter.options].find((o) => o.value && o.value.toLowerCase() === wanted);
  const next = own ? own.value : "";
  if (filter.value !== next) {
    filter.value = next;
    if (bi.loaded) bi.loaded.cards = false;
  }
  biDashDomainBox();
}

async function biSourceFolders() {
  const vault = biVaultOf(biDataset()), box = el("bi-b-src-folder-box");
  box.hidden = !vault || biReadOnly();
  if (box.hidden) return;
  const listed = biDataset(), reply = await call("/api/bi/vaults/" + vault.id + "/skills");
  if (listed !== biDataset()) return;
  bi.build.homes = reply.homes || [];
  if (bi.share && bi.shareVault === vault.id && vault.id === bi.verVault) {
    biShareDraw(bi.share);
  }
  const pick = el("bi-b-src-folder"), current = pick.value;
  const all = bh("option", "", "全部領域"); all.value = "sources";
  const option = (item) => {
    const o = bh("option", "", item.label); o.value = item.folder; return o;
  };
  // The library entries are the vault's shared reference areas, not a domain (F22).
  const shared = bi.build.homes.filter((item) => item.home.startsWith("library/"));
  const library = document.createElement("optgroup"); library.label = "共用參考資料（不是領域）";
  library.append(...shared.map(option));
  pick.replaceChildren(all, ...bi.build.homes.filter((item) => !shared.includes(item)).map(option),
    ...(shared.length ? [library] : []));
  // A list read again keeps the choice; only a dataset just opened goes back to what was kept.
  let stored = current;
  try { stored = current || localStorage.getItem(biScopeKey()) || ""; } catch (e) { /* */ }
  pick.value = bi.build.homes.some((item) => item.folder === stored) ? stored : "sources";
  biScopeFollowed(); biFileChosen(); biBqHomes(); biOverviewApply();
  // Just joined or created (acceptance F22): one domain is chosen, several are asked for.
  if (bi.vaultArrived !== listed) return;
  bi.vaultArrived = null;
  const arrivedNotice = el("bi-notice").classList.contains("good")
    ? el("bi-notice").textContent : "";
  const arrivalHint = (message) =>
    biNotice(true, [arrivedNotice, message].filter(Boolean).join(" "));
  const domains = bi.build.homes.filter((item) => !item.home.startsWith("library/"));
  if (domains.length === 1) {
    // This is automatic initialization, not the next press that dismisses a success notice.
    pick.value = domains[0].folder; biScopeChanged();
  } else if (domains.length) {
    pick.focus();
    try { pick.showPicker(); } catch (e) { /* a picker opens only on a person's click */ }
    arrivalHint("選一個工作領域：新增、Ingest 和測試都在那個領域裡做。");
  } else {
    el("bi-b-home-new").focus();
    arrivalHint("這個知識庫還沒有領域：按「新增領域」建一個。");
  }
}

function biOverview() {
  // 全部領域 reads everything and adds nothing. A vault with no homes has no other view.
  return !biScope() && Boolean((bi.build.homes || []).length);
}

function biOverviewApply() {
  const overview = biOverview();
  for (const id of ["bi-b-bq-add", "bi-b-qa-open", "bi-b-an-new", "bi-b-bq-pane"]) {
    el(id).hidden = overview;
  }
  el("bi-b-overview").hidden = !overview;
}

function biScopeEmpty() {
  // Where it matters, in sight: an empty domain's run reads with the defaults only.
  const scope = biScope(), skills = (bi.skills || {}).skills, box = el("bi-b-scope-empty");
  const has = !skills || (skills).some((item) => item.role === "extract"
    && (item.applies_to || []).some((folder) => biFolderHome(folder) === scope));
  box.hidden = !scope || has;
  box.textContent = box.hidden ? "" : "這個領域還沒有判讀規則，AI 擷取只會找 "
    + (((bi.skills || {}).profile_types || {})[scope]
      || (bi.skills || {}).default_types || []).join("、")
    + "。可以用「和 AI 新增規則」，或參考 library/skill-review 的範例。";
}

function biHomeForm(open) {
  el("bi-b-home-form").hidden = !open; el("bi-b-home-new").hidden = open;
  el("bi-b-home-err").hidden = true;
  el("bi-b-home-name").value = ""; el("bi-b-home-folder").value = "";
  if (open) el("bi-b-home-name").focus();
}

el("bi-b-home-new").addEventListener("click", () => biHomeForm(true));
el("bi-b-home-cancel").addEventListener("click", () => biHomeForm(false));
el("bi-b-home-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const vault = biVaultOf(biDataset()), err = el("bi-b-home-err");
  if (!vault) return;
  const go = el("bi-b-home-go"); go.disabled = true; err.hidden = true;
  biStatus("bi-status-build", "loading", "正在建立領域…（要重建這台電腦的資料，可能要十幾秒）");
  try {
    const reply = await biCall("/api/bi/vaults/" + vault.id + "/homes",
      {name: el("bi-b-home-name").value, folder: el("bi-b-home-folder").value});
    go.disabled = false; biStatus("bi-status-build", "");
    const item = reply.homes.find((home) => home.home === reply.home);
    biHomeForm(false);
    el("bi-b-src-folder").value = "";
    bi.build.homes = reply.homes;
    try { localStorage.setItem(biScopeKey(), item.folder); } catch (e) { /* */ }
    await biSourceFolders();
    biScopeChanged();
    biVaultState(await call("/api/bi/vaults/" + vault.id + "/status"));
    biNotice(true, "已建立領域「" + item.label + "」，現在是你的工作領域。還沒 commit："
      + "commit 並 push 後，同事才看得到，共用資料夾也才會有 applications/" + item.home
      + "/（sources、skills、tools、profile）。");
  } catch (failure) {
    biStatus("bi-status-build", "");
    err.textContent = "沒有建立：" + failure.message + "。"; err.hidden = false;
  } finally { go.disabled = false; }
});

function biScopeChanged() {
  try { localStorage.setItem(biScopeKey(), el("bi-b-src-folder").value); } catch (e) { /* */ }
  biAiClose(); biBqPick(null); biOverviewApply();
  // Another domain's panels: nothing of the one left stays in sight while they load.
  if (bi.loaded) bi.loaded.dashboard = false;
  bi.anSeen = null;
  el("bi-b-an-list").replaceChildren(bh("p", "bi-meta", "載入中…"));
  el("bi-b-an-state").textContent = "";
  const picked = (bi.build.sources || []).find((s) => s.id === bi.build.sourceId);
  if (picked && !biSourceInScope(picked)) {
    bi.build.sourceId = null; el("bi-b-next1").disabled = true;
    el("bi-b-md").hidden = true; el("bi-b-md-empty").hidden = false;
    biBuildSave();
  }
  biScopeFollowed(); biFileChosen(); biRenderSources(); biBuildRunPick();
  biBuildStage(bi.build.stage, false);
  biDashHome();
  // The tab showing follows too; biDashHome has already moved and asked for a Dashboard in step 3.
  if (bi.view !== "build") {
    if (bi.loaded) bi.loaded[bi.view] = false;
    biShowView(bi.view);
  }
  // What is already here redraws at once; the reads below take seconds on a real vault, and
  // whichever reply comes last, it is drawn for the domain chosen by then.
  if (bi.skills) biSkillsDraw(bi.skills);
  biScopeEmpty();
  if (bi.toolsReply && bi.toolsReply.vaultId === bi.verVault) {
    biToolsDraw(bi.toolsReply.vaultId, bi.toolsReply.reply);
  }
  if (bi.benchReply && bi.benchReply.vaultId === bi.verVault) biBenchDraw(bi.benchReply.reply);
  if (!bi.verVault) return;
  biBench(bi.verVault).catch((failure) => biNotice(false, "讀不到測試：" + failure.message));
  biVersions(bi.verVault).catch((failure) => biNotice(false, failure.message));
  biAnalyses(bi.verVault).catch((failure) => biNotice(false, failure.message));
}

function biSharedCell(source) {
  const vault = biVaultOf(biDataset());
  if (!vault) return "—";
  const words = bh("span", source.shared === "cloud_only" ? "bi-warn" : "",
    (BI_SHARED[source.shared] || "") + (source.folder ? "（" + source.folder + "）" : ""));
  if (source.shared === "pushed" || source.shared === "cloud_only") {
    return bh("span", "", words, " ", biButton("撤回", () => biWithdrawForm(source),
      "bi-btn", "撤回 " + source.name));
  }
  if (source.shared !== "local") return words;
  return bh("span", "", words, " ", biButton("放進共用資料夾", async () => {
    if (!biAddReady()) { biNotice(false, "先在上面選工作領域。"); return; }
    await biCall("/api/bi/vaults/" + vault.id + "/share-source",
      {source_id: source.id, folder: el("bi-b-src-folder").value});
    await biBuildSources();
  }, "bi-btn", "把 " + source.name + " 放進共用資料夾"));
}

function biWithdrawForm(source) {
  // What it does not remove is said before the person confirms (BI_SOURCES_IN_REPOSITORY §5).
  const vault = biVaultOf(biDataset()), box = el("bi-b-src-withdraw");
  const reason = document.createElement("input");
  reason.className = "bi-input"; reason.maxLength = 300; reason.id = "bi-b-src-withdraw-reason";
  reason.setAttribute("aria-label", "撤回的原因");
  box.hidden = false;
  // Anyone may withdraw any source (no access control); someone else's says so (F23).
  const by = source.added_by || "", me = (vault && vault.author) || "";
  const mine = !by || by === me || by.split(" ")[0] === me;
  box.replaceChildren(bh("h4", "", "撤回「" + source.name + "」"),
    bh("p", mine ? "" : "bi-warn", (mine ? "" : "這是 " + by + " 放進共用資料夾的來源，不是你的；"
      + "最好先跟對方說一聲。") + "撤回是對所有人：每位同事的電腦同步後都看不到這份來源。"),
    bh("p", "", "共用資料夾的檔案和它的 Markdown 會移除，各台電腦下次同步時移除 AEP 裡的副本；"
      + "這份來源還沒寫入的候選資料會移除，已寫入的擷取紀錄留下但清空摘錄。"),
    bh("p", "bi-warn", "OneDrive／SharePoint 可能還保留版本紀錄和資源回收筒裡的檔案，"
      + "保留多久由公司的設定決定，AEP 無法移除；需要完全清除時請找管理這個資料夾的人。"),
    bh("ul", "", bh("li", "", "還沒同步的電腦上的副本，要等那台電腦同步才會移除。"),
      bh("li", "", "已下載、備份、寄出，或已送給模型的內容，AEP 無法收回。"),
      bh("li", "", "卡片、欄位值和引用的摘錄留在版本紀錄裡，檔名和雜湊也是。"
        + "要移除 AEP 能觸及的一切，請不帶這個檔案重建知識庫。")),
    bh("label", "bi-label", "原因（會留在紀錄裡）"), reason,
    bh("div", "bi-actions", biButton("確認撤回", async () => {
      await biCall("/api/bi/vaults/" + vault.id + "/withdraw-source",
        {source_id: source.id, reason: reason.value, confirm: true});
      box.hidden = true; box.replaceChildren();
      await biBuildSources();
      biNotice(true, "已撤回「" + source.name + "」。");
    }, "go", "確認撤回 " + source.name),
    biButton("取消", () => { box.hidden = true; box.replaceChildren(); }, "bi-btn", "取消撤回")));
}

function biBuildSources() {
  // Settles when the newest list is drawn, whichever call that was: a caller that goes on to
  // read `bi.build.sources` (the upload opening what it added) reads that list, not one a
  // later call (the build tab still loading, a sync) made stale before it was drawn.
  const drawn = biBuildSourcesOnce();
  bi.sourcesDrawn = drawn;
  return drawn;
}

async function biBuildSourcesOnce() {
  // Newest call only: an older list arriving late must not drop the source just added.
  const seq = bi.sourcesSeq = (bi.sourcesSeq || 0) + 1, listed = biDataset();
  const reply = await call("/api/bi/sources?dataset=" + encodeURIComponent(listed));
  // Read once with the page (`biLoad`); here only if that failed or this dataset is new to it.
  if (!(bi.build.homes || []).length) await biSourceFolders().catch(() => {});
  if (listed !== biDataset()) return;
  if (seq !== bi.sourcesSeq) { await bi.sourcesDrawn.catch(() => {}); return; }
  bi.build.sources = reply.sources || []; bi.build.sourcesFor = listed;
  biRenderCounts();
  const cloud = bi.build.sources.filter((s) => s.shared === "cloud_only").length;
  const waiting = (reply.waiting || []).length;
  const warn = el("bi-b-src-cloud");
  warn.hidden = !cloud && !waiting;
  warn.textContent = (cloud
    ? cloud + " 個來源只在雲端：請把共用資料夾設為「一律保留在此裝置上」。" : "")
    + (waiting ? waiting + " 個檔案還在等 OneDrive 同步，同步好才看得到。" : "");
  const chosen = bi.build.sources.find((s) => s.id === bi.build.sourceId);
  if (!chosen || !biSourceInScope(chosen)) bi.build.sourceId = null;
  biFollowSourceFolder();
  biRenderSources();
  el("bi-b-next1").disabled = !bi.build.sourceId;
  biBuildSteps();
}

function biRenderSources() {
  // The working domain and the words typed.
  const words = el("bi-b-src-q").value.trim().toLowerCase();
  const shown = bi.build.sources.filter((source) => biSourceInScope(source)
    && (!words || source.name.toLowerCase().includes(words)));
  bi.build.shownCount = shown.length;
  const body = el("bi-b-sources").tBodies[0]; body.replaceChildren();
  bi.build.shownSources = shown.filter((source) => source.format).map((source) => source.id);
  for (const source of shown) {
    const radio = document.createElement("input");
    radio.type = "checkbox"; radio.name = "bi-b-source"; radio.value = source.id;
    radio.checked = biChosen().includes(source.id);
    radio.setAttribute("aria-label", "使用 " + source.name);
    radio.disabled = !source.format;
    radio.addEventListener("change", () => {
      // A row of the dataset just left would be dropped as soon as the new list arrives, and
      // the steps after this one would quietly stay shut.
      if (bi.build.sourcesFor !== biDataset()) { radio.checked = false; return; }
      biChoose([source.id], radio.checked);
      if (radio.checked) biPickSource(source);
    });
    const format = {table: "表格（預設表格規則）", document: "文件（預設 AI 擷取）",
      text: "文字（預設 AI 擷取）"};
    const md = source.convert_error
      ? bh("span", "bi-err", "轉檔失敗：" + source.convert_error.message)
      : source.markdown_rev ? "第 " + source.markdown_rev + " 版" : "尚未轉檔";
    const name = bh("td", "", source.name);
    name.title = Math.max(1, Math.round(source.size / 1024)) + " KB・加入於 " + biTime(source.at);
    const row = bh("tr", "", bh("td", "", radio), name,
      bh("td", "", format[source.format] || "尚未支援"),
      bh("td", "", md, " ", source.format
        ? biButton("看／改", () => biPickSource(source), "bi-btn", "看或修改 "
          + source.name + " 的 Markdown") : ""),
      bh("td", "", source.classification), bh("td", "", biSharedCell(source)));
    row.dataset.source = source.id;
    row.setAttribute("aria-selected", String(source.id === bi.build.sourceId));
    // A press anywhere on the row opens it; its own controls do their own thing.
    if (source.format) {
      row.addEventListener("click", (event) => {
        if (!event.target.closest("button, input, a")) biPickSource(source);
      });
    }
    body.append(row);
  }
  if (!shown.length) {
    body.append(bh("tr", "", bh("td", "bi-empty", bi.build.sources.length
      ? "這個領域或搜尋沒有來源。" : "還沒有來源。先選檔案，按「轉檔」。")));
  }
  biChosenShown();
}

function biChosen() {
  // What Ingest runs: the ticked sources still listed, in the working domain.
  const listed = new Set(bi.build.sources.filter((source) => source.format
    && biSourceInScope(source)).map((source) => source.id));
  return (bi.build.chosen || []).filter((id) => listed.has(id));
}

function biChoose(ids, on) {
  const kept = (bi.build.chosen || []).filter((id) => !ids.includes(id));
  bi.build.chosen = on ? [...kept, ...ids] : kept;
  const chosen = biChosen();
  if (!on && ids.includes(bi.build.sourceId)) bi.build.sourceId = chosen.at(-1) || null;
  if (on && !bi.build.sourceId) bi.build.sourceId = ids.at(-1);
  biBuildSave(); biBuildSteps(); biChosenShown();
}

function biChosenShown() {
  // The count beside the search, the header box, and step 2b's line all say the same.
  const chosen = biChosen(), shown = bi.build.shownSources || [];
  for (const box of el("bi-b-sources").querySelectorAll("tbody input[type=checkbox]")) {
    box.checked = chosen.includes(box.value);
  }
  const all = el("bi-b-src-all"), ticked = shown.filter((id) => chosen.includes(id)).length;
  all.checked = Boolean(shown.length) && ticked === shown.length;
  all.indeterminate = ticked > 0 && ticked < shown.length;
  all.disabled = !shown.length;
  const count = el("bi-b-src-count");
  count.textContent = bi.build.sources.length ? "顯示 " + (bi.build.shownCount || 0) + "／"
    + bi.build.sources.length + " 份・已選 " + chosen.length + " 份" : "";
  const names = chosen.map((id) => (bi.build.sources.find((s) => s.id === id) || {}).name);
  const line = el("bi-b-batch");
  line.replaceChildren(!chosen.length ? "還沒有選來源：到步驟 1 勾選「使用」。"
    : chosen.length === 1 ? "這次 Ingest：" + names[0]
      : bh("details", "", bh("summary", "", "這次 Ingest：" + chosen.length + " 份來源，"
        + "一份一次，依序執行"), bh("ul", "", ...names.map((name) => bh("li", "", name)))));
  if (!bi.build.batchRunning) el("bi-b-start").disabled = !chosen.length;
}

el("bi-b-src-all").addEventListener("change", () => {
  biChoose(bi.build.shownSources || [], el("bi-b-src-all").checked);
});

el("bi-b-src-q").addEventListener("input", () => biRenderSources());
el("bi-b-src-folder").addEventListener("change", biScopeChanged);

// -- step 1: a source's Markdown (BI vaults V2, BI_VAULT.md §5) ----------------
// Every source is read through its current Markdown revision; an edit saves a
// new revision from the one shown (409 markdown_stale when someone saved first).
function biShowMarkdownPane() {
  // Side by side the whole pair fits; stacked on a phone, go to the pane.
  const stacked = window.matchMedia("(max-width: 900px)").matches;
  (stacked ? el("bi-b-src-pane") : el("bi-b-src-split")).scrollIntoView(
    {block: stacked ? "start" : "nearest"});
}

function biMdFront(markdown) {
  // YAML-looking lines at the very top; what they say is only shown, never interpreted.
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  if (lines[0].trim() !== "---") return {rows: [], body: markdown};
  const end = lines.findIndex((line, index) => index > 0 && line.trim() === "---");
  if (end < 0) return {rows: [], body: markdown};
  const rows = [];
  for (const line of lines.slice(1, end)) {
    const pair = /^([^\s:][^:]*):\s*(.*)$/.exec(line);
    if (pair) rows.push([pair[1].trim(), pair[2].trim()]);
    else if (line.trim() && rows.length) {
      rows[rows.length - 1][1] = (rows[rows.length - 1][1] + " " + line.trim()).trim();
    }
  }
  return {rows, body: lines.slice(end + 1).join("\n")};
}

function biMdRender() {
  // Through renderMarkdown, as a chat answer: elements and text only, so a source's own
  // HTML shows as words, nothing runs, and there are no images to fetch from anywhere.
  const front = biMdFront(el("bi-b-md-text").value), box = el("bi-b-md-view");
  box.replaceChildren(renderMarkdown(front.body));
  for (const wrap of box.querySelectorAll(".table-scroll")) {
    wrap.setAttribute("aria-label", "表格");
  }
  if (front.rows.length) {
    const body = document.createElement("tbody");
    for (const [name, value] of front.rows) {
      const head = bh("th", "", name); head.scope = "row";
      body.append(bh("tr", "", head, bh("td", "", value)));
    }
    const table = bh("table", "bi-md-front"); table.append(body);
    const wrap = bh("div", "table-scroll", table);
    wrap.setAttribute("aria-label", "文件資訊");
    box.prepend(wrap);
  }
  if (!box.childNodes.length) box.append(bh("p", "bi-empty", "這一版沒有內容。"));
}

function biMdMode(mode) {
  el("bi-b-md-mode").value = mode;
  el("bi-b-md-edit").hidden = mode !== "edit"; el("bi-b-md-view").hidden = mode === "edit";
  if (mode !== "edit") biMdRender();
}

function biPickSource(source) {
  bi.build.sourceId = source.id; biBuildSave();
  el("bi-b-next1").disabled = biOverview() && Boolean(biFolderHome(source.folder));
  biFollowSourceFolder();
  biBuildSteps();
  for (const row of el("bi-b-sources").tBodies[0].rows) {
    row.setAttribute("aria-selected", String(row.dataset.source === source.id));
  }
  // Opening one with none ticked makes it the one Ingest reads, as a single choice did.
  if (!biChosen().length) biChoose([source.id], true);
  biBuildMarkdown(source.id);
}

async function biBuildMarkdown(sourceId, rev) {
  const box = el("bi-b-md"), msg = el("bi-b-md-msg");
  // Opens where the person is looking, and says there how it went.
  const seq = bi.mdSeq = (bi.mdSeq || 0) + 1;
  msg.replaceChildren();
  box.hidden = true; el("bi-b-md-empty").hidden = true;
  biStatus("bi-b-md-status", "loading", "載入 Markdown…");
  biShowMarkdownPane();
  const path = "/api/bi/sources/" + encodeURIComponent(sourceId) + "/markdown"
    + (rev ? "/" + rev : "") + "?dataset=" + encodeURIComponent(biDataset());
  let view;
  try { view = await call(path); }
  catch (failure) {
    if (seq !== bi.mdSeq) return;
    biStatus("bi-b-md-status", "error", "Markdown 沒有載入：" + failure.message + "。",
      () => biBuildMarkdown(sourceId, rev));
    return;
  }
  if (seq !== bi.mdSeq) return;
  biStatus("bi-b-md-status", "");
  bi.build.md = view; box.hidden = false;
  el("bi-b-src-pane").scrollTop = 0;
  el("bi-b-md-h").textContent = "「" + view.source.name + "」的 Markdown";
  const r = view.revision || {};
  el("bi-b-md-info").textContent = view.current_rev
    ? "第 " + r.rev + " 版（目前是第 " + view.current_rev + " 版）・"
      + (r.origin === "edit" ? "人工修改" : "轉檔") + (r.note ? "：" + r.note : "") + "・"
      + (r.lines || 0) + " 行・" + (r.by || "") + "・" + biTime(r.at)
    : "還沒有 Markdown（轉檔失敗）：可以自己貼上內容，存成第 1 版。";
  const pick = el("bi-b-md-rev"); pick.replaceChildren();
  for (const item of view.revisions || []) {
    const option = bh("option", "", "第 " + item.rev + " 版・" + (item.origin === "edit"
      ? "修改" : "轉檔") + (item.note ? "・" + item.note : ""));
    option.value = String(item.rev); pick.append(option);
  }
  pick.value = String(r.rev || "");
  el("bi-b-md-text").value = view.markdown || "";
  el("bi-b-md-note").value = "";
  // Opens on the preview; choosing another revision stays where the person is, and with
  // nothing to preview there is only pasting a first revision.
  biMdMode(!view.markdown ? "edit" : rev ? el("bi-b-md-mode").value : "view");
  const old = Boolean(view.current_rev) && r.rev !== view.current_rev;
  el("bi-b-md-save").disabled = old;
  if (old) msg.append(bh("p", "bi-meta", "這是舊版次，只能看；要改請先選目前的版次。"));
}

el("bi-b-md-rev").addEventListener("change", () => {
  if (bi.build.md) biBuildMarkdown(bi.build.md.source.id, el("bi-b-md-rev").value);
});
el("bi-b-md-mode").addEventListener("change", () => biMdMode(el("bi-b-md-mode").value));
el("bi-b-md-close").addEventListener("click", () => {
  el("bi-b-md").hidden = true; el("bi-b-md-empty").hidden = false;
});
el("bi-b-md-save").addEventListener("click", async () => {
  const view = bi.build.md, msg = el("bi-b-md-msg"); if (!view) return;
  msg.replaceChildren();
  const button = el("bi-b-md-save"); button.disabled = true;
  try {
    const reply = await biCall("/api/bi/sources/" + encodeURIComponent(view.source.id)
      + "/markdown", {dataset: biDataset(), markdown: el("bi-b-md-text").value,
      base_rev: view.current_rev || 0, note: el("bi-b-md-note").value.trim()});
    biNotice(true, reply.already ? "內容和目前的版次一樣，沒有存新版次。"
      : "已存成第 " + reply.current_rev + " 版；之後的試跑與匯入都讀這一版。");
    await biBuildSources(); await biBuildMarkdown(view.source.id);
  } catch (failure) {
    const stale = failure.code === "markdown_stale";
    msg.append(bh("p", "bi-err", stale
      ? "有人先存了新的版次（第 " + ((failure.payload || {}).current_rev || "?")
        + " 版）；你的修改沒有存。請重新載入後再改。" : "沒有存：" + failure.message + "。"));
    if (stale) {
      msg.append(biButton("重新載入目前的版次", () => biBuildMarkdown(view.source.id), "go"));
    }
    button.disabled = false;
  }
});

function biReadFile(file, binary) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("讀不到檔案 " + file.name));
    reader.onload = () => resolve(binary ? String(reader.result).split(",", 2)[1] || ""
      : String(reader.result));
    if (binary) reader.readAsDataURL(file); else reader.readAsText(file, "utf-8");
  });
}

function biFileChosen() {
  const files = el("bi-b-file").files, name = el("bi-b-file-name");
  el("bi-b-upload").disabled = !files.length || !biAddReady();
  el("bi-b-scope-need").hidden = biAddReady();
  name.textContent = !files.length ? "還沒有選檔"
    : files.length === 1 ? files[0].name : files.length + " 個檔案";
  name.title = [...files].map((file) => file.name).join("\n");
}
el("bi-b-file").addEventListener("change", biFileChosen);
// -- Obsidian card pages (BI_CARD_PAGE_IMPORT): preview, then apply ---------------
const BI_PAGES_MAX = 7 * 1024 * 1024;

function biPagesPlan(plan) {
  const box = el("bi-b-pages-plan"), s = plan.summary;
  const lines = [bh("p", "", bh("strong", "", "新增 " + s.create + "、更新 " + s.update
    + "、不變 " + s.unchanged + "、略過 " + s.skip),
    "（" + s.pages + " 頁，" + s.samples + " 張標成範例資料）"),
    bh("p", "bi-meta", "和既有卡片合併：補空值 " + s.merge.fill + "、清單合併 " + s.merge.join
      + "、不同的值轉成待審提議 " + s.merge.proposal + "（不會覆寫）、人工設定的值保留 "
      + s.merge.human_kept + "。")];
  if (plan.mark_conflicts.length) {
    lines.push(bh("p", "bi-warn", plan.mark_conflicts.length
      + " 張卡和這次的資料一邊是範例、一邊不是："
      + "卡片維持原本的標記，值轉成待審提議，不會自動變成範例或事實。"));
  }
  const unknown = plan.types.flatMap((t) => t.columns
    .filter((c) => c.status === "unknown" || c.status === "ignored")
    .map((c) => t.entity_type + "." + c.source));
  if (unknown.length) {
    lines.push(bh("p", "bi-warn", "schema 沒有的欄位（不會寫入）：" + unknown.join("、")));
  }
  const warned = plan.types.flatMap((t) => t.rows.flatMap((r) => r.warnings.map((w) =>
    t.entity_type + " " + r.canonical_key + "：" + w.message)));
  if (warned.length) {
    lines.push(bh("details", "", bh("summary", "", "值的問題（" + warned.length + "）"),
      bh("ul", "", ...warned.map((w) => bh("li", "", w)))));
  }
  if (plan.problems.length) {
    lines.push(bh("details", "", bh("summary", "", "看不懂的地方（" + plan.problems.length + "）"),
      bh("ul", "", ...plan.problems.map((p) => bh("li", "", p.path
        + (p.line ? " 第 " + p.line + " 行" : "") + "：" + p.message)))));
  }
  if (plan.skipped.length) {
    lines.push(bh("details", "", bh("summary", "", "略過的檔案（" + plan.skipped.length + "）"),
      bh("ul", "", ...plan.skipped.map((p) => bh("li", "", p.path + "：" + p.reason)))));
  }
  lines.push(bh("div", "bi-actions", biButton("確認匯入", async () => {
    const done = await biCall("/api/bi/import/pages/apply", {preview_id: plan.preview_id,
      folder: biVaultOf(biDataset()) ? el("bi-b-src-folder").value : undefined});
    box.replaceChildren();
    await biBuildSources();
    bi.loaded = {}; bi.loaded.build = true; await biRefreshCounts();
    biNotice(true, "已匯入卡片頁：新增 " + (done.applied ? done.applied.created : 0) + " 張、更新 "
      + (done.applied ? done.applied.updated : 0) + " 張。");
  }, "go", "確認匯入這些卡片頁")));
  box.replaceChildren(...lines);
}

el("bi-b-pages-dir").addEventListener("change", async (event) => {
  const chosen = [...event.target.files].filter((f) => /\.(md|csv)$/i.test(f.name)
    && !/(^|\/)\./.test(f.webkitRelativePath || f.name));
  event.target.value = "";
  try {
    const size = chosen.reduce((sum, f) => sum + f.size, 0);
    if (size > BI_PAGES_MAX) {
      throw new Error("這些檔案有 " + Math.round(size / 1048576) + " MB，請選小一點的資料夾");
    }
    const pages = await Promise.all(chosen.map(async (f) =>
      ({path: f.webkitRelativePath || f.name, text: await f.text()})));
    biPagesPlan(await biCall("/api/bi/import/pages/preview", {dataset: biDataset(), pages,
      samples: el("bi-b-pages-samples").checked,
      folder: biVaultOf(biDataset()) ? el("bi-b-src-folder").value : undefined}));
  } catch (failure) { biNotice(false, "沒有預覽：" + failure.message); }
});

// A large file goes as the raw request body, read by the browser as it is sent;
// base64 inside JSON cannot carry it (BI_SOURCES_IN_REPOSITORY S6).
const BI_STREAM_FROM = 4 * 1024 * 1024;

// A POST whose request body reports how much of it was sent (AGENTS.md rule 23):
// fetch cannot say that, XMLHttpRequest can.
function biSend(url, body, contentType, onSent) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.setRequestHeader("Authorization", "Bearer " + TOKEN);
    if (contentType) request.setRequestHeader("Content-Type", contentType);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onSent(event.loaded, event.total);
    };
    request.upload.onload = () => onSent(null, null);
    request.onerror = () => reject(new Error("連線失敗"));
    request.onload = () => {
      let answer = {};
      try { answer = JSON.parse(request.responseText || "{}"); } catch (_) { answer = {}; }
      if (request.status === 401) {
        reject(new Error("這個頁面是 Agent Web 較早的啟動；請開最新的 Agent Web 分頁再試"));
      } else if (request.status >= 400 || answer.ok === false) {
        const problem = new Error(answer.message || answer.error || answer.code
          || ("主機回應 " + request.status));
        problem.code = answer.code; reject(problem);
      } else resolve(answer);
    };
    request.send(body);
  });
}

async function biUploadFile(file, onSent) {
  const query = new URLSearchParams({dataset: biDataset(), name: file.name,
    classification: el("bi-b-class").value});
  if (biVaultOf(biDataset())) query.set("folder", el("bi-b-src-folder").value);
  return biSend("/api/bi/sources/upload?" + query.toString(), file, "", onSent);
}

function biMegabytes(bytes) {
  return bytes < 100 * 1024 ? (bytes / 1024).toFixed(1) + " KB"
    : (bytes / 1048576).toFixed(1) + " MB";
}

// Beside 轉檔: that it started, which file of how many, bytes sent, seconds passed,
// and in the end what came of every file (AGENTS.md rule 23).
function biUploadProgress(state, message) {
  const box = el("bi-b-upload-status"), button = el("bi-b-upload");
  box.replaceChildren(); box.hidden = !state;
  box.className = "mem-status bi-upload-status" + (state ? " " + state : "");
  if (state === "loading") {
    button.setAttribute("aria-busy", "true");
    box.append(bh("span", "mem-spinner"), bh("span", "", message));
  } else {
    button.removeAttribute("aria-busy");
    if (state) box.append(bh("span", "", message));
  }
}

el("bi-b-upload").addEventListener("click", async () => {
  const button = el("bi-b-upload"); button.disabled = true;
  const files = Array.from(el("bi-b-file").files);
  const started = Date.now();
  const now = {index: 0, name: "", step: "開始"};
  const show = () => {
    const seconds = Math.floor((Date.now() - started) / 1000);
    biUploadProgress("loading", "正在轉檔 " + now.index + "/" + files.length + "："
      + now.name + "・" + now.step + "・" + seconds + " 秒");
  };
  const ticker = setInterval(show, 1000);
  const sent = (loaded, total) => {
    now.step = loaded === null ? "已上傳，主機轉檔中"
      : "已上傳 " + biMegabytes(loaded) + "/" + biMegabytes(total)
        + (total ? "（" + Math.floor(loaded * 100 / total) + "%）" : "");
    show();
  };
  const added = [], failed = [];
  try {
    for (const [index, file] of files.entries()) {
      Object.assign(now, {index: index + 1, name: file.name, step: "讀取檔案"}); show();
      let reply;
      try {
        if (file.size > BI_STREAM_FROM) {
          reply = await biUploadFile(file, sent);
        } else {
          // Markdown and text go as their bytes too: the host decides their encoding
          // (UTF-8, UTF-16 or Big5) and says so when it cannot read one.
          const binary = /\.(xlsx|xlsm|pdf|docx|pptx|md|markdown|txt)$/i.test(file.name);
          const content = await biReadFile(file, binary);
          const body = {dataset: biDataset(), name: file.name,
            classification: el("bi-b-class").value};
          if (biVaultOf(biDataset())) body.folder = el("bi-b-src-folder").value;
          if (binary) body.content_base64 = content; else body.text = content;
          now.step = "上傳中"; show();
          reply = await biSend("/api/bi/sources", JSON.stringify(body), "application/json",
            sent);
        }
      } catch (failure) {
        failed.push(file.name + "：" + failure.message
          + (failure.code ? "（" + failure.code + "）" : ""));
        continue;
      }
      bi.build.sourceId = reply.source.id; added.push(reply.source.id);
      const problem = reply.source.convert_error;
      if (problem) {
        failed.push(file.name + "：" + (problem.message || problem.code)
          + (problem.code ? "（" + problem.code + "）" : ""));
      }
    }
    clearInterval(ticker);
    el("bi-b-file").value = ""; biFileChosen();
    const done = files.length - failed.length;
    const result = "已轉檔 " + done + " 份" + (failed.length
      ? "；" + failed.length + " 份沒有轉檔：" + failed.join("；")
        + "。可另存為 UTF-8、含文字層的檔案後再加入，或在右邊直接編輯 Markdown。" : "");
    biUploadProgress(failed.length ? "error" : "good", result);
    // What was just added is what is ticked: the next Ingest reads those files.
    bi.build.chosen = added;
    await biBuildSources(); biBuildSave();
    biStatus("bi-status-build", "");
    const last = bi.build.sources.find((source) => source.id === bi.build.sourceId);
    if (last && last.format) biPickSource(last);
  } catch (failure) {
    biUploadProgress("error", "來源沒有加入：" + failure.message + "。");
  } finally { clearInterval(ticker); biFileChosen(); }
});

// -- step 2: schema ----------------------------------------------------------
function biSchemaLabel(schema) {
  // Readable, never the digest (acceptance F6): 「5.0 加 1 項新增」.
  return (schema || {}).label || (schema || {}).version || "—";
}

async function biBuildSchema() {
  const schema = bi.schema || {};
  const now = el("bi-b-schema-now"); now.replaceChildren();
  now.append("目前的 schema：" + biSchemaLabel(schema) + "・" + (schema.types || []).length
    + " 種卡片");
  if ((schema.additions || []).length) {
    now.append(bh("details", "bi-manage", bh("summary", "", "新增了哪些"),
      bh("ul", "", ...schema.additions.map((a) => bh("li", "", a)))));
  }
  // Only newer versions that keep this vault's additions (acceptance F6).
  const newer = schema.upgrades || [];
  const box = el("bi-b-versions"); box.replaceChildren();
  if (newer.length) {
    box.append(bh("p", "bi-meta", "可以升級到的版本："));
    for (const item of newer) {
      box.append(bh("div", "bi-actions", bh("span", "", item.label),
        biButton("預覽升級", () => biBuildUpgradePreview(item.ref), "bi-btn",
          "預覽把資料集移到 " + item.label)));
    }
  } else {
    box.append(bh("p", "bi-meta", "沒有比目前更新的版本。"));
  }
  await biBuildDrafts();
  await biBuildSessA(false);
  await biSuggestLoad();
}

function biImpactList(title, items, render) {
  if (!items.length) return null;
  return bh("div", "", bh("strong", "", title), bh("ul", "", ...items.map((x) => bh("li", "",
    render(x)))));
}

async function biBuildUpgradePreview(to) {
  const box = el("bi-b-upgrade"); box.hidden = false; box.replaceChildren();
  const preview = await biCall("/api/bi/datasets/" + encodeURIComponent(biDataset())
    + "/schema/preview", {to});
  bi.build.upgrade = preview;
  const parts = [bh("h4", "", preview.additive
    ? "加入 " + preview.diff.length + " 項新增到 " + biSchemaLabel(bi.schema) + "（版本不變）"
    : "升級 " + biSchemaLabel(bi.schema) + " → " + biRefLabel(preview.to))];
  for (const type of preview.types) {
    const lines = [
      biImpactList("改名後移動的值", type.renamed, (r) => r.from + " → " + r.to + "（"
        + r.cards + " 張）"),
      biImpactList("放寬成清單或小數，既有值保留", type.widened || [], (w) => w.field + "："
        + w.from + " → " + w.to + "（" + w.cards + " 張）"),
      biImpactList("保留但隱藏（新版本沒有這個欄位）", type.hidden, (h) => h.field + "（"
        + h.cards + " 張）"),
      biImpactList("值已不在允許值裡，保留待審", type.retired, (r) => r.name + "・"
        + r.field + "＝" + r.value),
      biImpactList("新的必填欄位，這些卡片缺少", type.required_missing, (m) => m.field + "（"
        + m.cards + " 張）")].filter(Boolean);
    if (lines.length) parts.push(bh("div", "card", bh("strong", "", type.type), ...lines));
  }
  if (preview.blocked.length) {
    parts.push(bh("p", "bi-err", "不能升級：" + preview.blocked.map((b) => b.message)
      .join("；") + "。請另建資料集。"));
  } else {
    if (parts.length === 1) parts.push(bh("p", "bi-meta", "既有卡片都不受影響。"));
    parts.push(bh("div", "bi-actions", biButton("套用升級", async () => {
      const done = await biCall("/api/bi/datasets/" + encodeURIComponent(biDataset())
        + "/schema/apply", {to: preview.to, preview_token: preview.preview_token});
      biNotice(true, biUpgradeWords(preview.from, done.schema));
      box.hidden = true; await biLoad();
    }, "go")));
  }
  box.append(...parts);
}

function biRefLabel(ref) {
  // `bi.schema/v1.1@5.1.0` -> 5.1, as the server labels a version.
  const version = String(ref || "").split("@")[1] || String(ref || "");
  const base = version.split("+")[0], parts = base.split(".");
  return parts.length === 3 && parts[2] === "0" ? parts[0] + "." + parts[1] : base;
}

function biUpgradeWords(from, after) {
  // What really happened: additions on the same version, or a new one (acceptance F6).
  const same = String(from).split("+")[0] === String(after.ref).split("+")[0];
  return same
    ? "已加入 schema：" + after.label
      + "（相容的新增，不是新版本；commit 並 push 後大家才會用到）。"
    : "資料集已升級到 " + after.label + "。";
}

async function biBuildDrafts() {
  const reply = await call("/api/bi/schema-drafts");
  const id = (bi.schema || {}).schema_id;
  bi.build.drafts = (reply.drafts || []).filter((d) => d.schema_id === id);
  const list = el("bi-b-drafts"); list.replaceChildren();
  for (const draft of bi.build.drafts) {
    list.append(bh("li", "", biButton(draft.title + "・第 " + draft.revisions + " 版"
      + (draft.valid ? "" : "（有錯誤）"), () => biBuildOpenDraft(draft.id), "bi-btn")));
  }
  biDraftMain();
}

const BI_DRAFT_CHANGE = {type_added: "新增類型", type_removed: "移除類型", field_added: "新增欄位",
  field_removed: "移除欄位", renamed: "改名", widened: "放寬型別", kind: "改型別",
  class: "改類別", required: "必填", enum_added: "新增允許值", enum_removed: "移除允許值",
  link_to: "改連結", label: "顯示名稱", aliases: "別名", naming: "命名欄位"};

function biDraftMain() {
  // Acceptance F8: the draft as a table of what changes; the AI edits it, JSON is 進階.
  const view = bi.build.draft, box = el("bi-b-draft-main");
  const pick = el("bi-b-draft-pick"); pick.replaceChildren();
  for (const draft of bi.build.drafts || []) {
    const option = new Option(draft.title + "・第 " + draft.revisions + " 版", draft.id);
    option.selected = Boolean(view && view.draft.id === draft.id);
    pick.append(option);
  }
  box.hidden = !view;
  const body = el("bi-b-draft-table").tBodies[0]; body.replaceChildren();
  if (!view) return;
  for (const c of view.diff) {
    const row = bh("tr", c.breaking ? "bi-flag-red" : "", bh("td", "", biTypeLabel(c.type)),
      bh("td", "", c.field || "—"), bh("td", "", (c.breaking ? "⚠ " : "")
        + (BI_DRAFT_CHANGE[c.change] || c.change)), bh("td", "", c.detail));
    body.append(row);
  }
  if (!view.diff.length) {
    body.append(bh("tr", "", bh("td", "bi-empty", "這份草稿和目前的 schema 一樣。")));
  }
  el("bi-b-draft-sum").textContent = view.errors.length
    ? "有 " + view.errors.length + " 個問題，不能套用；請和 AI 調整，或在進階看 JSON。"
    : view.additive ? "都是新增：套用後版本不變，加在目前的 schema 上。"
      : "有新增以外的改動：套用後是新的版本。";
  el("bi-b-draft-use").disabled = Boolean(view.errors.length || !view.diff.length);
}

el("bi-b-draft-pick").addEventListener("change", () => biBuildOpenDraft(
  el("bi-b-draft-pick").value).catch((failure) => biNotice(false, failure.message)));
el("bi-b-draft-use").addEventListener("click", async () => {
  // Publish the open revision, then the same preview and confirm as 預覽升級.
  const view = bi.build.draft; if (!view) return;
  try {
    const reply = await biCall("/api/bi/schema-drafts/" + view.draft.id + "/publish",
      {rev: view.revision});
    await biBuildUpgradePreview(reply.ref);
    el("bi-b-upgrade").scrollIntoView({block: "nearest"});
  } catch (failure) {
    const errors = (failure.payload && failure.payload.errors) || [];
    biNotice(false, "沒有套用：" + failure.message + (errors.length ? "（"
      + errors.map((e) => e.path + "：" + e.message).join("；") + "）" : ""));
  }
});

// -- step 2a: 建議 schema (BI_PAGE_SIMPLE.md S2, acceptance F5) --------------------
// The fit question alone, on a press: the model reads the sources, no card is written.
// Each row is quoted from a source; 「不用改」 is an answer.
const BI_SG_KIND = {extend_schema: ["新增欄位", "accent"], dictionary_change: ["用語", "dim"],
  propose_type: ["新增類型", "warn"], needs_clarification: ["待釐清", "dim"]};

function biSuggestSources() {
  if (el("bi-b-sg-scope").value === "picked") {
    return bi.build.sourceId ? [bi.build.sourceId] : [];
  }
  return (bi.build.sources || []).filter((s) => biSourceInScope(s) && s.markdown_rev)
    .map((s) => s.id);
}

async function biSuggestLoad() {
  // A read that answers after a press must not put back what the press replaced.
  const seq = bi.sgSeq = (bi.sgSeq || 0) + 1;
  const reply = await call("/api/bi/schema-suggest?dataset=" + encodeURIComponent(biDataset()));
  if (seq !== bi.sgSeq) return;
  biSuggestShow(reply.suggestion);
  if (reply.suggestion && reply.suggestion.status === "running") biSuggestFollow();
}

async function biSuggestFollow() {
  const listed = biDataset(), seq = bi.sgSeq = (bi.sgSeq || 0) + 1;
  for (;;) {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    if (seq !== bi.sgSeq || listed !== biDataset()) return;
    const reply = await call("/api/bi/schema-suggest?dataset=" + encodeURIComponent(listed));
    biSuggestShow(reply.suggestion);
    if (!reply.suggestion || reply.suggestion.status !== "running") return;
  }
}

function biSuggestShow(state) {
  bi.build.suggest = state;
  const box = el("bi-b-sg-box"), body = el("bi-b-sg-table").tBodies[0];
  el("bi-b-sg-run").disabled = Boolean(state && state.status === "running");
  if (!state) { box.hidden = true; biStatus("bi-b-sg-status", ""); return; }
  if (state.status === "running") {
    biStatus("bi-b-sg-status", "loading", "AI 正在看 " + state.sources.length + " 份來源…（第 "
      + state.done + "／" + state.sources.length + " 份；只問 schema，不會寫卡片）");
  } else if (state.status === "failed") {
    biStatus("bi-b-sg-status", "error", "建議沒有完成：" + state.failures.map((f) => f.message)
      .join("；"));
  } else {
    biStatus("bi-b-sg-status", "");
  }
  box.hidden = state.status === "running";
  const tokens = state.answers.input_tokens + state.answers.output_tokens;
  el("bi-b-sg-sum").textContent = "看了 " + state.sources.length + " 份來源（"
    + state.sources.map((s) => s.name).join("、") + "）"
    + (state.seconds !== null ? "，" + state.seconds + " 秒" : "")
    + (tokens ? "，約 " + tokens + " tokens" : "")
    + (state.answers.reused ? "，" + state.answers.reused + " 段沿用上次的回答" : "")
    + "。放得進目前 schema 的內容 " + state.fits + " 項"
    + (state.unquoted ? "；" + state.unquoted + " 項找不到原文，沒有列出" : "")
    + (state.left_out ? "；還有 " + state.left_out + " 份沒看（一次最多 10 份）" : "")
    + (state.failures.length ? "；" + state.failures.length + " 段沒有讀到" : "") + "。";
  body.replaceChildren();
  for (const row of state.items) body.append(biSuggestRow(state, row));
  if (!state.items.length && state.status === "done") {
    const cell = bh("td", "", bh("strong", "", "不用改"),
      "：這些來源的內容都放得進目前的 schema。");
    cell.colSpan = 4;
    body.append(bh("tr", "", cell));
  }
}

function biSuggestRow(state, row) {
  const kind = BI_SG_KIND[row.kind] || [row.kind, "dim"];
  const why = bh("td", "", row.reason);
  if (row.questions.length) why.append(biListBlock("要回答", row.questions));
  const quote = bh("td", "", bh("q", "", row.quote), bh("div", "bi-meta", row.source
    + (row.places > 1 ? "・提到 " + row.places + " 次" : "")));
  const act = bh("td", "");
  if (row.status === "applied") {
    act.append(biBadge("✓ 已加入", "good"), " " + (row.schema || ""));
  } else if (row.status === "rejected") {
    act.append(biBadge("✕ 不要", "dim"));
  } else {
    // One way first: add it when a press can, else talk it through; the rest in a menu.
    const direct = row.applies && biDataset().startsWith("vault-");
    const add = direct ? biButton("加入 schema", () => biSuggestApply(state, row), "go",
      "把「" + row.what + "」加入 schema") : null;
    const ask = biButton("和 AI 討論", () => biSuggestAsk(row), direct ? "bi-btn" : "go",
      "和 AI 討論「" + row.what + "」");
    const no = biButton("不要", () => biSuggestReject(state, row), "bi-btn",
      "不要「" + row.what + "」");
    act.append(add || ask, biRowMenu(add ? ask : null, no));
  }
  const tr = bh("tr", "", bh("td", "", biBadge(kind[0], kind[1]), " ", row.what), why, quote,
    act);
  tr.dataset.row = row.id;
  return tr;
}

async function biSuggestApply(state, row) {
  const reply = await biCall("/api/bi/schema-suggest/apply",
    {dataset: biDataset(), id: state.id, row: row.id});
  biNotice(true, "已加入「" + row.what + "」：目前的 schema 是 " + reply.schema.label
    + "（相容的新增，不是新版本；commit 並 push 後大家才會用到）。");
  bi.schema = await biCall("/api/bi/schema?dataset=" + encodeURIComponent(biDataset()));
  await biBuildSchema();
  biSuggestShow(reply.suggestion);
}

async function biSuggestReject(state, row) {
  const reply = await biCall("/api/bi/schema-suggest/reject",
    {dataset: biDataset(), id: state.id, row: row.id, reason: "不需要"});
  biSuggestShow(reply.suggestion);
}

async function biSuggestAsk(row) {
  // The one AI panel, with the suggestion and its quote already written.
  await biSchemaAi();
  const box = el("bi-ai-sources");
  for (const input of box.querySelectorAll("input")) {
    if (input.value === row.source_id) input.checked = true;
  }
  el("bi-ai-msg").value = "建議：" + row.what + "\n理由：" + row.reason + "\n原文（"
    + row.source + "）：「" + row.quote + "」"
    + (row.questions.length ? "\n要回答：" + row.questions.join("；") : "")
    + "\n請幫我決定要不要改 schema，要的話怎麼改。";
}

el("bi-b-sg-run").addEventListener("click", async () => {
  const ids = biSuggestSources();
  if (!ids.length) {
    biStatus("bi-b-sg-status", "error", el("bi-b-sg-scope").value === "picked"
      ? "先在步驟 1 選一份來源。" : "這個領域還沒有轉好的來源。"); return;
  }
  bi.sgSeq = (bi.sgSeq || 0) + 1;
  try {
    const reply = await biCall("/api/bi/schema-suggest", {dataset: biDataset(), source_ids: ids,
      only_new: el("bi-b-sg-scope").value === "new"});
    biSuggestShow(reply.suggestion); biSuggestFollow();
  } catch (failure) { biStatus("bi-b-sg-status", "error", failure.message); }
});

function biDraftInfo(view) {
  const info = el("bi-b-draft-info"); info.replaceChildren();
  info.append(bh("p", "bi-meta", "第 " + view.revision + " 版・version "
    + ((view.document || {}).version || "?")));
  if (view.errors.length) {
    info.append(bh("p", "bi-err", "有 " + view.errors.length + " 個問題，不能發布："),
      bh("ul", "", ...view.errors.map((e) => bh("li", "", e.path + "：" + e.message))));
  }
  if (view.diff.length) {
    info.append(bh("strong", "", "和基礎版本的差異"), bh("ul", "", ...view.diff.map((c) =>
      bh("li", c.breaking ? "bi-err" : "", (c.breaking ? "⚠ " : "") + c.type
        + (c.field ? "." + c.field : "") + "：" + c.detail))));
  }
  const revisions = view.draft.revisions.slice().reverse();
  info.append(bh("strong", "", "版次"), bh("ul", "", ...revisions.map((r) => bh("li", "",
    "第 " + r.rev + " 版・" + (r.note || r.source) + "・" + biTime(r.at) + " ",
    r.rev === view.revision ? "" : biButton("回復到這一版", async () => {
      biBuildShowDraft(await biCall("/api/bi/schema-drafts/" + view.draft.id + "/revert",
        {rev: r.rev}));
    }, "bi-btn", "回復到第 " + r.rev + " 版")))));
}

function biBuildShowDraft(view) {
  const other = !bi.build.draft || bi.build.draft.draft.id !== view.draft.id;
  bi.build.draft = view;
  el("bi-b-draft").hidden = false;
  el("bi-b-draft-text").value = JSON.stringify(view.document, null, 1);
  el("bi-b-draft-note").value = "";
  biDraftInfo(view); biDraftMain();
  if (other) el("bi-b-draft-trial-result").replaceChildren();
  biBuildSessA(other).catch((failure) => biNotice(false, "對話沒有載入：" + failure.message));
}

// -- step 2: Session A, designing the draft by conversation (BI ingest phase 6) --
// The model suggests operations; code applies them to a copy and shows the diff
// and errors. Only 「套用到草稿」 writes a revision; 「用樣本試跑」 tries the draft
// revision on a source without installing it. The conversation is always shown
// (owner, 2026-10-28): without an open draft, the first message makes one from
// the dataset's current version.
function biSchemaAbout() {
  const draft = bi.build.draft;
  return draft ? "草稿「" + draft.draft.title + "」第 " + draft.revision + " 版。"
    + "發布並升級前，資料集不會變。"
    : "還沒有開啟草稿：第一句話會從目前的 schema（" + biSchemaLabel(bi.schema)
      + "）建一份。套用前，資料集不會變。";
}

function biSchemaSources() {
  const box = el("bi-ai-sources");
  const kept = new Set([...box.querySelectorAll("input:checked")].map((i) => i.value));
  if (!kept.size && bi.build.sourceId) kept.add(bi.build.sourceId);
  box.replaceChildren();
  const usable = bi.build.sources.filter((s) => s.parse !== "unsupported");
  for (const source of usable) {
    const check = document.createElement("input");
    check.type = "checkbox"; check.value = source.id; check.checked = kept.has(source.id);
    box.append(bh("label", "", check, source.name + "（" + source.classification + "）"));
  }
  if (!usable.length) box.append(bh("p", "bi-meta", "還沒有來源；只送草稿與目標。"));
  el("bi-ai-sources-box").querySelector("summary").textContent = "附上的樣本來源（最多 5 份，已選 "
    + [...box.querySelectorAll("input:checked")].length + " 份）";
}

async function biBuildSessA(reload) {
  const draft = bi.build.draft;
  if (!draft) {
    bi.build.sessA = null;
  } else if (reload || !bi.build.sessA || bi.build.sessA.target_ref !== "schema-draft:"
    + draft.draft.id) {
    const found = await call("/api/bi/sessions?dataset=" + encodeURIComponent(biDataset())
      + "&target=" + encodeURIComponent("schema-draft:" + draft.draft.id));
    bi.build.sessA = (found.sessions || [])[0] || null;
    if (bi.ai && bi.ai.kind === "schema") {
      el("bi-ai-goal").value = bi.build.sessA ? bi.build.sessA.goal || "" : "";
    }
  }
  if (bi.ai && bi.ai.kind === "schema") {
    biAiTarget(biSchemaAbout()); biSchemaSources(); biAiShow(bi.build.sessA);
  }
}

async function biSchemaAi() {
  await biAiOpen({kind: "schema", dataset: biDataset(), title: "和 AI 調整 schema",
    about: biSchemaAbout(), sends: "草稿的類型與欄位、你的目標、勾選的來源", agent: "schema",
    label: "你想怎麼調整", placeholder: "例如：幫技術卡加一個價格帶欄位",
    busy: "正在看來源與卡片、試草稿…（可能要幾分鐘）", render: biBuildApplySchema,
    sessionTarget: () => bi.build.draft.draft.id,
    prepare: async (_message, spec) => {
      if (!bi.build.draft) {
        biBuildShowDraft(await biCall("/api/bi/schema-drafts", {base: (bi.schema || {}).ref}));
        await biBuildDrafts();
      }
      spec.session = bi.build.sessA;
    },
    turn: () => ({goal: el("bi-ai-goal").value, source_ids: [...el("bi-ai-sources")
      .querySelectorAll("input:checked")].map((i) => i.value).slice(0, 5)}),
    saved: (session) => { bi.build.sessA = session; }});
  el("bi-ai-goal").value = bi.build.sessA ? bi.build.sessA.goal || "" : "";
  await biBuildSessA(false);
}

el("bi-b-sa-open").addEventListener("click", () => biSchemaAi()
  .catch((failure) => biNotice(false, failure.message)));

const BI_VERDICT = {reuse: ["照用目前的 schema", "good"], extend: ["擴充這份 schema", "accent"],
  new: ["需要新的 schema（另建資料集）", "warn"], answer: ["回答問題，沒有建議", "dim"]};

function biBuildApplySchema(session, turn, index) {
  const s = turn.suggestion, r = s.result, verdict = BI_VERDICT[s.verdict] || [s.verdict, "dim"];
  const parts = [bh("p", "", bh("strong", "", "AI："), biBadge(verdict[0], verdict[1]), " ",
    s.reply), biListBlock("理由", s.reasons), biListBlock("假設", s.assumptions),
    biListBlock("缺少的資訊", s.missing_information)];
  if (r.diff.length) {
    parts.push(bh("strong", "", "套用後和第 " + r.base_rev + " 版的差異"), bh("ul", "",
      ...r.diff.map((c) => bh("li", c.breaking ? "bi-err" : "", (c.breaking ? "⚠ " : "")
        + c.type + (c.field ? "." + c.field : "") + "：" + c.detail))));
  } else {
    parts.push(bh("p", "bi-meta", "這個建議不改動草稿。"));
  }
  const problems = [...r.problems, ...r.errors.map((e) => e.path + "：" + e.message)];
  if (problems.length) parts.push(biListBlock("不能套用的原因", problems, "bi-err"));
  if ((s.examples || []).length) {
    parts.push(biListBlock("範例卡片", s.examples.map((e) => biTypeLabel(e.entity_type) + "・"
      + e.name + (Object.keys(e.fields).length ? "（" + Object.entries(e.fields).map(([k, v]) =>
        k + "＝" + biValue(v)).join("；") + "）" : ""))));
  }
  if (turn.applied) {
    parts.push(bh("p", "bi-meta", "已套用為草稿第 " + turn.applied.rev + " 版。"));
  } else if (r.valid && r.diff.length) {
    parts.push(bh("div", "bi-actions", biButton("套用到草稿", async () => {
      const reply = await biCall("/api/bi/sessions/" + session.id + "/apply",
        {dataset: biDataset(), turn: index});
      bi.build.sessA = reply.session;
      biBuildShowDraft(reply); await biBuildDrafts();
      biNotice(true, "已存成草稿第 " + reply.revision + " 版；可以「用樣本試跑」看看。");
    }, "go", "把這個建議套用為草稿的新版次")));
  }
  return parts;
}

el("bi-b-draft-trial").addEventListener("click", async () => {
  const draft = bi.build.draft, box = el("bi-b-draft-trial-result");
  box.replaceChildren();
  if (!draft) return;
  if (!bi.build.sourceId) {
    box.append(bh("p", "bi-err", "先在步驟 1 選一份來源。")); return;
  }
  try {
    const reply = await biCall("/api/bi/runs", {dataset: biDataset(), kind: "trial",
      source_id: bi.build.sourceId, entity_type: el("bi-b-entity").value || null,
      draft_id: draft.draft.id, draft_rev: draft.revision});
    const detail = await biBuildFollow(reply.run.id);
    box.append(bh("p", "bi-meta", "用草稿第 " + draft.revision + " 版試跑完成（沒有安裝 schema，"
      + "也沒有寫入；" + detail.run.schema_ref + "）："),
      bh("div", "bi-chips", ...biRunChips(detail.run)),
      bh("ul", "", ...detail.candidates.slice(0, 30).map((c) => bh("li", "",
        (c.name || c.canonical_key || "（無名稱）") + "・" + c.entity_type + "："
        + c.fields.map((f) => f.field + "＝" + biValue(f.value)).join("；")
        + (c.errors.length ? "・錯誤：" + c.errors.map((e) => e.message).join("；") : "")))));
  } catch (failure) {
    const errors = (failure.payload && failure.payload.errors) || [];
    box.append(bh("p", "bi-err", "試跑失敗：" + failure.message + (errors.length ? "（"
      + errors.map((e) => e.path + "：" + e.message).join("；") + "）" : "") + "。"));
  }
});

async function biBuildOpenDraft(id) {
  biBuildShowDraft(await call("/api/bi/schema-drafts/" + id));
}

el("bi-b-draft-new").addEventListener("click", async () => {
  try {
    const view = await biCall("/api/bi/schema-drafts", {base: (bi.schema || {}).ref});
    biBuildShowDraft(view); await biBuildDrafts();
  } catch (failure) { biNotice(false, "沒有建立草稿：" + failure.message); }
});
el("bi-b-draft-save").addEventListener("click", async () => {
  const draft = bi.build.draft; if (!draft) return;
  try {
    const view = await biCall("/api/bi/schema-drafts/" + draft.draft.id + "/revisions",
      {json_text: el("bi-b-draft-text").value, note: el("bi-b-draft-note").value});
    biBuildShowDraft(view); await biBuildDrafts();
  } catch (failure) { biNotice(false, "沒有儲存：" + failure.message); }
});
el("bi-b-draft-publish").addEventListener("click", async () => {
  const draft = bi.build.draft; if (!draft) return;
  try {
    const reply = await biCall("/api/bi/schema-drafts/" + draft.draft.id + "/publish",
      {rev: draft.revision});
    biNotice(true, "已發布 " + biRefLabel(reply.ref) + "。要讓資料集使用它，請按「預覽升級」。");
    const schemas = await call("/api/bi/schemas"); bi.schemas = schemas.schemas || [];
    // What it may upgrade to is the dataset's schema state, read again.
    bi.schema = await biCall("/api/bi/schema?dataset=" + encodeURIComponent(biDataset()));
    await biBuildSchema();
  } catch (failure) {
    const errors = (failure.payload && failure.payload.errors) || [];
    biNotice(false, "沒有發布：" + failure.message + (errors.length ? "（"
      + errors.map((e) => e.path + "：" + e.message).join("；") + "）" : ""));
  }
});

// -- steps 3-4: runs ---------------------------------------------------------
function biRunBody(kind, sourceId = bi.build.sourceId, batch = false) {
  const body = {dataset: biDataset(), kind, source_id: sourceId,
    entity_type: el("bi-b-entity").value || null};
  const methodId = el("bi-b-m-pick").value;
  if (methodId && !methodId.startsWith("builtin:")) { body.method_id = methodId; return body; }
  // 「AI 擷取」 on a table sends its Markdown to the model (owner 2026-10-28);
  // 「表格規則」 reads the tables without a model.
  const source = bi.build.sources.find((s) => s.id === sourceId);
  if (methodId === "builtin:llm" && source && source.format === "table") body.path = "ai";
  if (methodId === "builtin:rules") body.path = "rules";
  if (el("bi-b-fresh").checked) body.fresh = true;
  if (el("bi-b-fit").checked && biDataset().startsWith("vault-")) body.check_fit = true;
  // 「不指定」 sends nothing: the server then uses the source's own folder. Several sources
  // each keep their own, so a batch never sends one.
  if (!batch && biDataset().startsWith("vault-") && el("bi-b-folder").value
    && el("bi-b-folder").value !== "sources") {
    body.folder = el("bi-b-folder").value;
  }
  const instructions = el("bi-b-instr").value.trim();
  if (instructions) body.instructions = instructions;
  const recipe = el("bi-b-recipe").value.trim();
  if (recipe) {
    try { body.recipe = JSON.parse(recipe); }
    catch (e) { throw new Error("配方不是有效的 JSON"); }
  }
  return body;
}

function biRunNothing(run) {
  // Why the AI made no candidate, in its words: an empty run must not look like a broken one.
  const said = (run.warnings || []).filter((w) => w.code === "model_found_nothing");
  const notes = said.map((w) => bh("p", "bi-warn", "AI 沒有建立候選卡，它的說明：" + w.message));
  if ("profile" in run && !run.profile) {
    notes.push(bh("p", "bi-meta", "這個資料夾沒有 profile，AI 用整份 schema 判讀。"));
  }
  return notes;
}

const BI_FIT_ACTION = {update_card: "更新卡片", create_card: "新增卡片",
  dictionary_change: "字典調整", extend_schema: "擴充欄位", propose_type: "新卡型提案",
  needs_clarification: "待釐清"};

function biRunFit(run) {
  // What the schema cannot hold yet: nothing registers until a person decides, and an
  // approved field goes to the application's profile for its own merge.
  const items = (run.items || []).filter((item) => item.status !== "through_candidate");
  if (!items.length) return [];
  const decide = async (item, status, reason) => {
    await biCall("/api/bi/runs/" + run.id + "/items/" + item.id,
      {dataset: biDataset(), status, reason: reason.value.trim()});
    await biBuildFetchRun(run.id); biBuildRenderRun();
  };
  return [bh("h4", "", "不適合現有 schema 的內容（逐項決定）"),
    bh("ul", "bi-fit", ...items.map((item) => {
      const reason = bh("input", "");
      reason.placeholder = "理由（退回或待釐清必填）";
      const open = item.status === "proposed" || item.status === "needs_clarification";
      return bh("li", "", item.actions.map((a) => BI_FIT_ACTION[a] || a).join(" + ") + "："
        + item.summary,
        bh("div", "bi-meta", item.reason + (item.excerpt ? "（「" + item.excerpt + "」）" : "")),
        ...(item.questions || []).map((q) => bh("div", "bi-warn", "待確認：" + q)),
        open
          ? bh("span", "", reason, " ",
            item.actions.includes("needs_clarification") ? ""
              : biButton("核准", () => decide(item, "approved", reason), "bi-btn"), " ",
            biButton("退回", () => decide(item, "rejected", reason), "bi-btn"), " ",
            biButton("待釐清", () => decide(item, "needs_clarification", reason), "bi-btn"))
          : biBadge(item.status === "approved" ? "已核准" : "已退回",
            item.status === "approved" ? "good" : "dim"));
    }))];
}

function biRunRelations(run) {
  // Relations the AI inferred: each decided by a person, on its quote. Confirming needs both
  // cards to exist, so it works once the run's cards are written.
  const items = run.relations || [];
  if (!items.length) return [];
  const decide = async (item, status) => {
    await biCall("/api/bi/runs/" + run.id + "/relations/" + item.id,
      {dataset: biDataset(), status});
    await biBuildFetchRun(run.id); biBuildRenderRun();
  };
  return [bh("h4", "", "AI 推論的關係（逐筆決定，要提交後才會寫入知識庫）"),
    bh("ul", "bi-relations", ...items.map((item) => bh("li", "",
      item.from + " → " + item.type + " → " + item.to + "：「" + item.excerpt + "」",
      item.reason ? bh("span", "bi-meta", "（" + item.reason + "）") : "", " ",
      item.decision
        ? biBadge(item.decision === "confirmed" ? "已確認" : "已否決",
          item.decision === "confirmed" ? "good" : "dim")
        : bh("span", "", biButton("確認", () => decide(item, "confirmed"), "bi-btn"), " ",
          biButton("否決", () => decide(item, "rejected"), "bi-btn")))))];
}

function biRunChips(run) {
  const s = run.summary || {};
  return [biBadge("候選 " + (s.candidates || 0), "dim"), biBadge("新建 " + (s.create || 0), "good"),
    biBadge("更新 " + (s.update || 0), "dim"), biBadge("略過 " + (s.skip || 0), "dim"),
    ...(s.citations ? [biBadge("新增出處 " + s.citations, "accent")] : []),
    biBadge("錯誤 " + (s.errors || 0), s.errors ? "bad" : "dim"),
    biBadge("警告 " + (s.warnings || 0), s.warnings ? "warn" : "dim"),
    biBadge("已接受 " + (s.accepted || 0), "good"), ...biRunMerge(run)];
}

function biRunMerge(run) {
  // What writing this run would do to the cards there already.
  const m = run.merge;
  if (!m) return [];
  const a = run.answers || {};
  return [...(a.reused ? [biBadge(a.reused + " 段沿用上次的回答（提示詞完全相同）", "dim")] : []),
    biBadge("既有卡片：填入 " + m.fill, "good"), biBadge("合併清單 " + m.join, "good"),
    biBadge("變成提案 " + m.proposal, m.proposal ? "warn" : "dim"),
    ...(m.take ? [biBadge("你選了新值 " + m.take, "warn")] : [])];
}

// An AI run reads its source in the background: follow it until it ends.
async function biBuildFollow(runId, where = "") {
  for (;;) {
    const detail = await call("/api/bi/runs/" + runId + "?dataset="
      + encodeURIComponent(biDataset()));
    if (detail.run.status !== "extracting") { biStatus("bi-status-build", ""); return detail; }
    const p = detail.run.progress || {};
    biStatus("bi-status-build", "loading", where + "AI 判讀中…（第 " + (p.done || 0) + "／"
      + (p.chunks || "?") + " 段）");
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

el("bi-b-trial").addEventListener("click", async () => {
  const box = el("bi-b-trial-result"); box.replaceChildren();
  try {
    const reply = await biCall("/api/bi/runs", biRunBody("trial"));
    const detail = await biBuildFollow(reply.run.id);
    box.append(bh("p", "bi-meta", "試跑完成（沒有寫入）："), bh("div", "bi-chips",
      ...biRunChips(detail.run)), bh("ul", "", ...detail.candidates.slice(0, 50).map((c) =>
      bh("li", "", biTypeLabel(c.entity_type) + "・" + (c.name || c.canonical_key || "（無名稱）")
        + "・" + (BI_RUN_ACTION[c.action] || c.action)
        + (c.errors.length ? "・錯誤 " + c.errors.length : "")
        + (c.warnings.length ? "・警告 " + c.warnings.length : "")))),
      ...biRunNothing(detail.run));
    if (detail.run.method_ref) {
      box.prepend(bh("p", "bi-meta", "擷取 Skill：" + detail.run.method_ref));
    }
  } catch (failure) {
    box.append(bh("p", "bi-err", "試跑失敗：" + failure.message + "。"));
  }
  try {
    await biBuildTrials();
    if (bi.build.method) await biBuildOpenMethod(bi.build.method.method.id);
  } catch (failure) { biNotice(false, "試跑紀錄沒有更新：" + failure.message); }
});

// -- step 3: methods, Session B and comparison (BI ingest phase 5) -------------
// A method is a versioned file in the dataset; Session B suggests changes (one
// model call per turn, no tools) and only 「套用為新版次」 writes a revision.
async function biBuildMethodStage() {
  biChosenShown();
  // Right from the start: until the list is filled its first entry, AI, would send a table
  // to the model on a press.
  if (!bi.build.skill && !bi.build.method) el("bi-b-m-pick").value = biBuiltinFor();
  try {
    await Promise.all([biBuildMethods(), biBuildTrials()]);
  } catch (failure) { biNotice(false, "擷取 Skill 沒有載入：" + failure.message); }
}

async function biBuildAiState(target, extra, agent) {
  const state = await call("/api/bi/ai?dataset=" + encodeURIComponent(biDataset()));
  bi.build.ai = state;
  const line = el(target); line.replaceChildren(); line.className = "bi-meta";
  if (!state.available) {
    line.className = "bi-warn";
    line.append("目前沒有可用的模型（model_unavailable）：" + state.message + "。");
    return;
  }
  line.append("模型 " + state.model + (agent ? "" : "（每次送出呼叫一次，沒有工具）")
    + "・會送出：" + extra + "。AI 不能存檔、commit 或 push；你確認才會改動。");
}

async function biBuildMethods(fill) {
  // At once, not after the reply: a trial pressed meanwhile must not send a table to the
  // model because the select still shows its first option.
  if (!bi.build.method && !bi.build.skill) el("bi-b-m-pick").value = biBuiltinFor();
  const reply = await call("/api/bi/methods?dataset=" + encodeURIComponent(biDataset()));
  // Keep what the person picked; otherwise the built-in that fits the source.
  const pick = el("bi-b-m-pick"), keep = bi.build.method ? bi.build.method.method.id
    : bi.build.skill || "";
  pick.replaceChildren();
  for (const [value, label] of BI_BUILTIN_SKILLS) {
    const option = bh("option", "", label); option.value = value; pick.append(option);
  }
  for (const item of reply.methods || []) {
    const option = bh("option", "", item.name + "・第 " + item.revisions + " 版・"
      + (item.mode === "rules" ? "規則" : "AI") + (item.status.schema_changed
        ? "・schema 已更新，請重新試跑" : ""));
    option.value = item.id; pick.append(option);
  }
  const saved = (reply.methods || []).some((m) => m.id === keep);
  pick.value = saved || keep.startsWith("builtin:") ? keep : biBuiltinFor();
  if (!pick.value.startsWith("builtin:")) await biBuildOpenMethod(pick.value, fill);
  else biBuildCloseMethod();
}

// The built-in Skills are the shipped defaults, not files: picking one runs
// with the boxes below (empty = the default rules or the automatic mapping).
const BI_BUILTIN_SKILLS = [["builtin:llm", "AI 擷取（內建）"],
  ["builtin:rules", "表格規則（內建，不用模型）"]];

function biBuiltinFor() {
  const source = bi.build.sources.find((s) => s.id === bi.build.sourceId);
  return source && source.parse === "table" ? "builtin:rules" : "builtin:llm";
}

function biSessBAbout() {
  if (bi.build.method) {
    return "Skill「" + bi.build.method.document.name + "」第 " + bi.build.method.revision + " 版。";
  }
  return el("bi-b-m-pick").value === "builtin:rules"
    ? "內建「表格規則」沒有設定可調：先貼配方，或改選「AI 擷取」。"
    : "內建「AI 擷取」：第一句話會另存成你的 Skill，內建的不變。";
}

function biSessBTarget() {
  if (bi.ai && bi.ai.kind === "method") biAiTarget(biSessBAbout());
}

async function biMethodAi() {
  const source = bi.build.sources.find((s) => s.id === bi.build.sourceId);
  await biAiOpen({kind: "method", dataset: biDataset(), title: "和 AI 調整擷取 Skill",
    about: biSessBAbout(),
    sends: "Skill、最近兩次試跑的候選卡" + (source ? "、來源「" + source.name + "」（"
      + source.classification + "）的前段（上限 12000 字）" : ""),
    agent: false, label: "你想怎麼調整", placeholder: "例如：沒有文件依據的需求標成推測",
    busy: "正在看 Skill 與樣本…（一次模型呼叫）", render: biBuildApplyMethod,
    sessionTarget: () => bi.build.method.method.id,
    prepare: async (_message, spec) => {
      if (!bi.build.method) await biSessBCopy();
      spec.session = bi.build.sessB;
    },
    turn: () => ({source_ids: bi.build.sourceId ? [bi.build.sourceId] : []}),
    saved: (session) => { bi.build.sessB = session; }});
  biAiShow(bi.build.sessB);
}

el("bi-b-sb-open").addEventListener("click", () => biMethodAi()
  .catch((failure) => biNotice(false, failure.message)));

function biBuildCloseMethod() {
  bi.build.method = null; el("bi-b-m-box").hidden = true; el("bi-b-m-save").hidden = true;
  bi.build.sessB = null;
  if (bi.ai && bi.ai.kind === "method") biAiShow(null);
  biSessBTarget();
}

el("bi-b-m-pick").addEventListener("change", async () => {
  const id = el("bi-b-m-pick").value;
  bi.build.skill = id;
  if (id.startsWith("builtin:")) { biBuildCloseMethod(); return; }
  try { await biBuildOpenMethod(id, true); }
  catch (failure) { biNotice(false, "擷取 Skill 沒有載入：" + failure.message); }
});

// The settings boxes below as a method body (rules when there is a recipe).
function biMethodBody(name) {
  const method = {name, mode: "llm"};
  const recipe = el("bi-b-recipe").value.trim(), instr = el("bi-b-instr").value.trim();
  if (recipe) {
    try { method.mode = "rules"; method.recipe = JSON.parse(recipe); }
    catch (e) { throw new Error("配方不是有效的 JSON"); }
  }
  if (instr && !recipe) method.instructions = instr;
  if (bi.build.method && bi.build.method.document.name === name) {
    method.checks = bi.build.method.document.checks;
    if (!recipe) method.types = bi.build.method.document.types;
  }
  return method;
}

el("bi-b-m-save").addEventListener("click", async () => {
  const view = bi.build.method; if (!view) return;
  try {
    const saved = await biCall("/api/bi/methods/" + view.method.id + "/revisions",
      {dataset: biDataset(), method: biMethodBody(view.document.name), note: "手動修改"});
    await biBuildMethods(true);
    biNotice(true, "已存成第 " + saved.revision + " 版。");
  } catch (failure) { biNotice(false, "沒有存成新版次：" + failure.message); }
});

el("bi-b-m-new").addEventListener("click", async () => {
  const name = el("bi-b-m-name").value.trim();
  if (!name) { biNotice(false, "請先寫新 Skill 的名稱。"); el("bi-b-m-name").focus(); return; }
  let method;
  try { method = biMethodBody(name); }
  catch (failure) { biNotice(false, failure.message + "。"); return; }
  try {
    const view = await biCall("/api/bi/methods", {dataset: biDataset(), method});
    el("bi-b-m-name").value = "";
    bi.build.method = view; bi.build.skill = view.method.id; await biBuildMethods();
    biNotice(true, "已另存 Skill「" + view.document.name + "」第 1 版。");
  } catch (failure) { biNotice(false, "沒有另存 Skill：" + failure.message); }
});

function biMethodText(value) {
  if (value == null || value === "") return "（無）";
  return typeof value === "string" ? value : JSON.stringify(value, null, 1);
}

const BI_METHOD_KEY = {instructions: "判讀規則", types: "卡片類型", recipe: "配方",
  mode: "方式", checks: "必要欄位檢查", name: "名稱", schema_ref: "schema",
  body: "規則內容", applies_to: "套用到的資料夾", card_types: "卡片類型"};

function biMethodDiff(diff) {
  if (!diff.length) return bh("p", "bi-meta", "內容沒有變化。");
  return bh("ul", "", ...diff.map((d) => bh("li", "", bh("strong", "",
    (BI_METHOD_KEY[d.key] || d.key) + "："), bh("div", "bi-meta", "原本："),
    bh("pre", "bi-pre", biMethodText(d.before)), bh("div", "bi-meta", "之後："),
    bh("pre", "bi-pre", biMethodText(d.after)))));
}

async function biBuildOpenMethod(id, fill) {
  // Newest request only: a reload started before a save must not paint the
  // older revision over the new one (seen under load in the full suite).
  const seq = bi.build.methodSeq = (bi.build.methodSeq || 0) + 1;
  const view = await call("/api/bi/methods/" + id + "?dataset="
    + encodeURIComponent(biDataset()));
  if (seq !== bi.build.methodSeq) return;
  bi.build.method = view;
  el("bi-b-m-box").hidden = false; el("bi-b-m-save").hidden = false;
  const doc = view.document, info = el("bi-b-m-info"); info.replaceChildren();
  if (fill) {
    // The boxes below show the chosen revision, so editing them is editing it.
    el("bi-b-recipe").value = doc.mode === "rules" ? JSON.stringify(doc.recipe, null, 1) : "";
    el("bi-b-instr").value = doc.mode === "llm" ? doc.instructions : "";
  }
  info.append(bh("p", "", bh("strong", "", doc.name), "・第 " + view.revision + " 版・"
    + (doc.mode === "rules" ? "規則轉換（配方）" : "AI 判讀") + "・schema " + doc.schema_ref));
  if (view.status.schema_changed) {
    info.append(bh("p", "bi-warn", view.status.message + "：資料集現在使用 "
      + view.status.schema_ref + "；用這個 Skill 試跑一次（到可審核）後才能正式匯入。"));
  } else if (view.status.rechecked && view.status.revision_schema_ref !== view.status.schema_ref) {
    info.append(bh("p", "bi-meta", "已在 " + view.status.schema_ref + " 下試跑確認（執行 "
      + view.status.rechecked.run_id + "）。"));
  }
  info.append(bh("p", "bi-meta", "卡片類型：" + doc.types.map(biTypeLabel).join("、")
    + (doc.checks.length ? "・必要欄位檢查 " + doc.checks.length + " 條" : "")));
  info.append(bh("details", "", bh("summary", "", doc.mode === "rules" ? "配方內容"
    : "判讀規則"), bh("pre", "bi-pre", biMethodText(doc.mode === "rules" ? doc.recipe
    : doc.instructions))));
  if (view.revision > 1) {
    info.append(bh("details", "", bh("summary", "", "和第 " + (view.revision - 1)
      + " 版的差異"), biMethodDiff(view.diff)));
  }
  const revisions = view.method.revisions.slice().reverse();
  const source = {base: "建立", edit: "修改", ai: "AI 建議", revert: "回復"};
  info.append(bh("strong", "", "版次"), bh("ul", "", ...revisions.map((r) => bh("li", "",
    "第 " + r.rev + " 版・" + (r.note || source[r.source] || r.source) + "・" + biTime(r.at)
      + " ", r.rev === view.revision ? biBadge("目前", "good")
      : biButton("回復到這一版", async () => {
        await biCall("/api/bi/methods/" + id + "/revert", {dataset: biDataset(), rev: r.rev});
        await biBuildMethods(true);
        biNotice(true, "已回復：第 " + r.rev + " 版的內容成為新的版次。");
      }, "bi-btn", "回復到第 " + r.rev + " 版")))));
  const found = await call("/api/bi/sessions?dataset=" + encodeURIComponent(biDataset())
    + "&target=" + encodeURIComponent("method:" + id));
  if (seq !== bi.build.methodSeq) return;
  bi.build.sessB = (found.sessions || [])[0] || null;
  if (bi.ai && bi.ai.kind === "method") biAiShow(bi.build.sessB);
  biSessBTarget();
}

const BI_TOOL_NAME = {bi_skill__sources: "列出來源", bi_skill__read_source: "讀來源",
  bi_skill__try: "草稿試跑", bi_skill__compare: "比較試跑", bi_skill__test_cases: "擷取測試",
  bi_skill__benchmark: "看對答案的影響",
  bi__query: "查卡片", bi_skill__suggest: "提出建議", bi_analysis__sql: "SQL",
  bi_analysis__python: "Python 腳本", bi_analysis__propose: "提出分析",
  bi_analysis__read: "讀取分析", bi_analysis__propose_dashboard: "提出 Dashboard",
  bi_schema__sources: "列出來源", bi_schema__read_source: "讀來源", bi_schema__cards: "看卡片",
  bi_schema__try: "試草稿", bi_schema__suggest: "提出建議",
  bi_questions__analyses: "看分析", bi_questions__try: "試問", bi_questions__propose: "提出題目"};

function biSentLine(sent) {
  const parts = (sent.sources || []).map((s) => "來源「" + s.name + "」（" + s.classification
    + "，送出 " + s.chars + "／" + s.of + " 字" + (s.truncated ? "，已截斷" : "") + "）");
  if ((sent.runs || []).length) parts.push("試跑 " + sent.runs.join("、") + " 的候選卡");
  if (sent.method_rev) parts.push("Skill 第 " + sent.method_rev + " 版");
  if (sent.skill_revision) parts.push("判讀規則第 " + sent.skill_revision + " 版");
  if (sent.draft_rev) parts.push("草稿第 " + sent.draft_rev + " 版");
  if (sent.goal) parts.push("目標");
  let used = "";
  if (sent.harness) {
    const counts = {};
    for (const t of sent.tools || []) counts[t.name] = (counts[t.name] || 0) + 1;
    used = "・Agent 用了：" + (Object.entries(counts).map(([n, c]) => (BI_TOOL_NAME[n] || n)
      + (c > 1 ? " ×" + c : "")).join("、") || "沒有用工具");
  }
  if (sent.analysis) parts.push("資料表與欄位的說明");
  return "模型 " + (sent.model || "?") + "・送出：" + (parts.join("、") || "只有對話")
    + (sent.harness ? "" : "（來源上限 " + (sent.cap || 12000) + " 字）") + used;
}

function biListBlock(title, items, cls) {
  if (!items || !items.length) return "";
  return bh("div", cls || "", bh("strong", "", title), bh("ul", "", ...items.map((x) =>
    bh("li", "", x))));
}

function biBuildSessionLog(target, session, renderSuggestion) {
  const log = el(target); log.replaceChildren();
  const turns = session ? session.turns : [];
  if (!turns.length) {
    log.append(bh("li", "bi-meta", "還沒有對話。"));
    return;
  }
  turns.forEach((turn, index) => {
    if (turn.role === "user") {
      // The working domain's line went to the model; the person did not write it.
      log.append(bh("li", "me", bh("strong", "", "你："),
        String(turn.text).replace(/^工作領域：[^\n]*\n\n/, "")));
      return;
    }
    const item = bh("li", "", bh("p", "bi-meta", biSentLine(turn.sent || {})));
    if (turn.error) item.append(bh("p", "bi-err", turn.error.message));
    const asked = index > 0 ? turns[index - 1] : null;
    if (turn.error && target === "bi-ai-log" && index === turns.length - 1 && asked) {
      // The last turn failed: send the same request again (acceptance F16/F20).
      item.append(bh("div", "bi-actions", biButton("重試", () => {
        el("bi-ai-msg").value = String(asked.text).replace(/^工作領域：[^\n]*\n\n/, "");
        el("bi-ai-send").click();
      }, "bi-btn", "再送一次同樣的要求")));
    }
    if (turn.suggestion) item.append(...renderSuggestion(session, turn, index));
    log.append(item);
  });
}

function biBuildApplyMethod(session, turn, index) {
  const s = turn.suggestion;
  const parts = [bh("p", "", bh("strong", "", "AI："), s.reply),
    biListBlock("理由", s.reasons), biListBlock("限制", s.limits),
    biListBlock("需要工程開發（Skill 做不到，沒有套用）", s.needs_engineering, "bi-warn"),
    bh("strong", "", "套用後的變化"), biMethodDiff(s.result.diff)];
  if (turn.applied) {
    parts.push(bh("p", "bi-meta", "已套用為第 " + turn.applied.rev + " 版。"));
  } else if (s.result.diff.length) {
    parts.push(bh("div", "bi-actions", biButton("套用為新版次", async () => {
      const reply = await biCall("/api/bi/sessions/" + session.id + "/apply",
        {dataset: biDataset(), turn: index});
      await biBuildMethods(true);
      biNotice(true, "已套用為第 " + reply.revision + " 版；用同一份來源試跑後可以比較。");
    }, "go", "把這個建議套用為 Skill 的新版次")));
  }
  return parts;
}

// A built-in Skill is never changed: the first message saves a copy from the
// boxes below and the conversation is about that copy.
async function biSessBCopy() {
  const value = el("bi-b-m-pick").value;
  if (value === "builtin:rules" && !el("bi-b-recipe").value.trim()) {
    throw new Error("內建「表格規則」沒有可調整的設定；先在下方貼配方，或改選「AI 擷取」");
  }
  const label = value === "builtin:rules" ? "表格規則" : "AI 擷取";
  const view = await biCall("/api/bi/methods", {dataset: biDataset(),
    method: biMethodBody(label + "（我的版本 " + new Date().toISOString().slice(0, 16)
      .replace("T", " ") + "）")});
  bi.build.method = view; bi.build.skill = view.method.id;
  await biBuildMethods(true);
  biNotice(true, "已把內建「" + label + "」另存為你的 Skill「" + view.document.name
    + "」，對話的建議會套用到它。");
  return bi.build.method;
}

async function biBuildTrials() {
  const reply = await call("/api/bi/runs?dataset=" + encodeURIComponent(biDataset()));
  const trials = (reply.runs || []).filter((r) => r.kind === "trial"
    && r.source_ids.includes(bi.build.sourceId) && ["review", "partial"].includes(r.status));
  for (const [id, pick] of [["bi-b-cmp-left", 1], ["bi-b-cmp-right", 0]]) {
    const select = el(id); select.replaceChildren();
    for (const run of trials) {
      const option = bh("option", "", biTime(run.at) + "・" + (run.method_ref || "內建 Skill")
        + "・" + run.id);
      option.value = run.id; select.append(option);
    }
    if (trials[pick]) select.value = trials[pick].id;
  }
  el("bi-b-cmp-go").disabled = trials.length < 2;
}

function biCompareField(f) {
  const side = (x) => x ? biValue(x.value) + "（" + ((BI_BASIS[x.basis] || [x.basis])[0])
    + "）" : "（無）";
  const what = {added: "新增", removed: "移除", value: "值改變", basis: "依據改變"};
  return bh("li", "", bh("strong", "", f.field), "：" + side(f.before) + " → "
    + side(f.after) + "・" + (what[f.change] || f.change));
}

el("bi-b-cmp-go").addEventListener("click", async () => {
  const box = el("bi-b-cmp"); box.replaceChildren();
  try {
    const c = await call("/api/bi/runs/compare?dataset=" + encodeURIComponent(biDataset())
      + "&left=" + el("bi-b-cmp-left").value + "&right=" + el("bi-b-cmp-right").value);
    const row = (label, key) => bh("tr", "", bh("td", "", label),
      bh("td", "", String(c.counts.left[key])), bh("td", "", String(c.counts.right[key])));
    const table = bh("table", "bi-table", bh("thead", "", bh("tr", "", bh("th", "", "數量"),
      bh("th", "", "較早 " + c.left.id), bh("th", "", "較新 " + c.right.id))),
      bh("tbody", "", row("候選卡", "candidates"), row("推論欄位", "inferences"),
        row("警告", "warnings"), row("錯誤", "errors")));
    const name = (x) => biTypeLabel(x.entity_type) + "・" + (x.name || x.canonical_key);
    box.append(bh("p", "bi-meta", (c.left.method_ref || "內建 Skill") + " → "
      + (c.right.method_ref || "內建 Skill") + "・相同 " + c.same + " 張"),
      bh("div", "bi-scroll", table),
      biListBlock("只在較新的試跑", c.added.map(name)),
      biListBlock("只在較早的試跑", c.removed.map(name)));
    for (const item of c.changed) {
      box.append(bh("div", "card", bh("strong", "", biTypeLabel(item.entity_type) + "・"
        + item.name), bh("ul", "", ...item.fields.map(biCompareField)),
        item.warnings_added.length ? bh("p", "bi-warn", "新增警告：" + item.warnings_added
          .join("、")) : "",
        item.warnings_removed.length ? bh("p", "bi-meta", "少了警告：" + item.warnings_removed
          .join("、")) : ""));
    }
    if (!c.changed.length && !c.added.length && !c.removed.length) {
      box.append(bh("p", "bi-meta", "兩次試跑的候選卡完全相同。"));
    }
  } catch (failure) {
    box.append(bh("p", "bi-err", "沒有比較：" + (failure.message || failure) + "。"));
  }
});

async function biBuildFetchRun(runId) {
  try {
    const detail = await call("/api/bi/runs/" + runId + "?dataset="
      + encodeURIComponent(biDataset()));
    bi.build.run = detail.run; bi.build.candidates = detail.candidates;
  } catch (failure) { bi.build.run = null; bi.build.candidates = []; }
}

el("bi-b-start").addEventListener("click", async () => {
  // One run per ticked source, one after another: each keeps its own source and folder, and
  // one that fails does not stop the rest. 停止 cancels the run under way and starts no more.
  const chosen = biChosen(), batch = chosen.length > 1;
  if (!chosen.length) return;
  const button = el("bi-b-start"), stop = el("bi-b-batch-stop");
  const name = (id) => (bi.build.sources.find((s) => s.id === id) || {}).name || id;
  button.disabled = true; stop.hidden = !batch; stop.disabled = false;
  bi.build.batchRunning = true; bi.build.batchStop = false; bi.build.batchRun = null;
  const done = [], failed = [];
  try {
    for (const [index, sourceId] of chosen.entries()) {
      if (bi.build.batchStop) break;
      const where = batch ? "第 " + (index + 1) + "／" + chosen.length + " 份「" + name(sourceId)
        + "」：" : "";
      biStatus("bi-status-build", "loading", where + "正在產生候選卡…");
      try {
        const reply = await biCall("/api/bi/runs", biRunBody("ingest", sourceId, batch));
        bi.build.batchRun = reply.run.id;
        if (bi.build.batchStop) {
          await biCall("/api/bi/runs/" + reply.run.id + "/cancel", {dataset: biDataset()});
          break;
        }
        const detail = await biBuildFollow(reply.run.id, where);
        // Finished: 停止 from now on must not cancel it, its candidates wait for review.
        bi.build.batchRun = null;
        if (["failed", "cancelled"].includes(detail.run.status)) {
          if (detail.run.status === "failed") {
            failed.push(name(sourceId) + "：" + (detail.run.error || "判讀失敗"));
          }
        } else done.push(reply.run.id);
      } catch (failure) { failed.push(name(sourceId) + "：" + failure.message); }
    }
  } finally {
    bi.build.batchRunning = false; stop.hidden = true; button.disabled = false;
    biChosenShown();
  }
  const stopped = bi.build.batchStop ? "已停止；" : "";
  if (failed.length) {
    biStatus("bi-status-build", "error", stopped + "產生了 " + done.length + " 次執行，"
      + failed.length + " 份沒有成功（" + failed.join("；") + "）。");
  } else biStatus("bi-status-build", "");
  if (!done.length) return;
  if (batch) {
    biNotice(true, stopped + "產生了 " + done.length
      + " 次執行，在「待審核的執行」一次選一個審核。");
  }
  await biBuildFetchRun(done[0]); bi.build.candidateId = null;
  biBuildSave(); biBuildStage("review");
});

el("bi-b-batch-stop").addEventListener("click", async () => {
  bi.build.batchStop = true; el("bi-b-batch-stop").disabled = true;
  if (bi.build.batchRun) {
    await biCall("/api/bi/runs/" + bi.build.batchRun + "/cancel", {dataset: biDataset()})
      .catch(() => {});
  }
});

function biNext4() {
  // Shut only when there is nothing accepted; while decisions are saved it says so and waits.
  const run = bi.build.run, busy = bi.build.accepting || bi.build.saving;
  const accepted = biRunOpen(run) && run.summary && run.summary.accepted > 0;
  const button = el("bi-b-next4");
  button.disabled = !(biBuildAllowed().commit || busy && (accepted || bi.build.accepting));
  if (!button.textContent.startsWith("儲存完")) {
    const why = bi.build.acceptProgress ? "接受中 " + bi.build.acceptProgress : "儲存中…";
    button.textContent = busy ? "下一步：確認寫入（" + why + "）" : "下一步：確認寫入";
  }
}

function biRunReading(run) { return run.method_ref === "llm:reading"; }

function biCandAction(candidate) {
  // Nothing it says changes; a source that repeats a value adds its citation, and only that.
  if (candidate.action === "unchanged" && (candidate.citations || []).length) return "新增出處";
  return BI_RUN_ACTION[candidate.action] || candidate.action;
}

function biRunReviewable(run) {
  // A page's trial is read in its own step; a reading run's has nowhere else to be read.
  return !!run && (run.kind === "ingest" || biRunReading(run));
}

function biRunOpen(run) {
  return !!run && run.kind === "ingest" && ["review", "partial"].includes(run.status);
}

async function biBuildRuns() {
  const dataset = biDataset();
  const reply = await call("/api/bi/runs?dataset=" + encodeURIComponent(dataset));
  if (dataset !== biDataset()) return;
  bi.build.waiting = (reply.runs || []).filter((run) => biRunReviewable(run)
    && ["review", "partial"].includes(run.status));
  biBuildRunPick(); biBuildSteps();
}

function biRunLabel(run) {
  const source = (bi.build.sources || []).find((s) => s.id === (run.source_ids || [])[0]);
  const what = biRunReading(run) ? "補摘要" : source ? source.name : "匯入";
  const s = run.summary || {};
  return biTime(run.at) + "・" + what + (run.kind === "trial" ? "（試跑）" : "")
    + "・待決定 " + (s.pending || 0) + "／" + (s.candidates || 0);
}

function biRunInScope(run) {
  // By its source's folder. Filling summaries spans the vault, whatever it starts from.
  const source = (bi.build.sources || []).find((s) => s.id === (run.source_ids || [])[0]);
  return biRunReading(run) || !source || biSourceInScope(source);
}

function biBuildRunPick() {
  const select = el("bi-b-run-pick"), run = bi.build.run;
  const runs = [...(bi.build.waiting || [])];
  if (biRunReviewable(run)) {
    const at = runs.findIndex((item) => item.id === run.id);
    if (at >= 0) runs[at] = run; else runs.unshift(run);
  }
  const option = (item) => {
    const made = bh("option", "", biRunLabel(item)); made.value = item.id; return made;
  };
  const own = runs.filter(biRunInScope), others = runs.filter((item) => !biRunInScope(item));
  select.replaceChildren(...own.map(option));
  if (others.length) {
    // Never opened by themselves, always one choice away.
    if (!biRunReviewable(run)) {
      const none = bh("option", "", own.length ? "選一個待審核的執行"
        : "這個領域沒有待審核的執行（其他領域 " + others.length + " 個）");
      none.value = ""; select.prepend(none);
    }
    const group = document.createElement("optgroup");
    group.label = "其他領域"; group.append(...others.map(option));
    select.append(group);
  }
  if (!runs.length) select.append(bh("option", "", "沒有待審核的執行"));
  select.disabled = !runs.length || !!bi.build.accepting;
  if (biRunReviewable(run)) select.value = run.id;
}

async function biBuildOpenRun(runId) {
  // The last one chosen: an earlier run answering late must not take its place.
  const seq = bi.build.openSeq = (bi.build.openSeq || 0) + 1;
  const detail = await call("/api/bi/runs/" + runId + "?dataset="
    + encodeURIComponent(biDataset()));
  if (seq !== bi.build.openSeq) return;
  bi.build.run = detail.run; bi.build.candidates = detail.candidates;
  bi.build.candidateId = null; bi.build.texts = new Map();
  el("bi-b-cand-last").replaceChildren();
  el("bi-b-cand-type").value = ""; el("bi-b-cand-state").value = "";
  biBuildSave(); biBuildRenderRun();
}

async function biBuildReviewStage() {
  biBuildRenderRun();
  biBuildRowInView();
  const dataset = biDataset();
  biBuildCardIndex(dataset);
  await biBuildRuns().catch((failure) => biNotice(false, "讀不到執行清單：" + failure.message));
  if (dataset !== biDataset() || biRunReviewable(bi.build.run)) return;
  const first = bi.build.waiting.find(biRunInScope);
  if (first) await biBuildOpenRun(first.id);
}

async function biBuildCardIndex(dataset) {
  // Which values name a card: read once per visit, and links appear when it has come.
  try {
    const reply = await call("/api/bi/cards?dataset=" + encodeURIComponent(dataset));
    if (dataset !== biDataset()) return;
    const cards = new Map();
    for (const card of reply.cards || []) {
      for (const name of new Set([card.canonical_key, card.name])) {
        if (!cards.has(name)) cards.set(name, []);
        cards.get(name).push(card);
      }
    }
    bi.build.cards = cards;
    if (bi.build.candidateId && !bi.build.peek
      && bi.build.stage === "review") biBuildShowCandidate(bi.build.candidateId);
  } catch (failure) { biNotice(false, "卡片連結沒有載入：" + failure.message); }
}

function biBuildNamedCard(value, typeName, fieldName, selfIds) {
  const found = (bi.build.cards && bi.build.cards.get(value)) || [];
  const field = fieldName ? biSchemaField(typeName, fieldName) : null;
  const wanted = field && field.link_to;
  const card = found.find((c) => !selfIds.includes(c.id)
    && (!wanted || c.entity_type === wanted)) || found.find((c) => !selfIds.includes(c.id));
  return card ? card.id : null;
}

function biBuildRowInView() {
  const row = el("bi-b-cands").querySelector('tr[data-candidate="' + bi.build.candidateId + '"]');
  if (row) row.scrollIntoView({block: "nearest"});
}

el("bi-b-run-pick").addEventListener("change", () => {
  if (!el("bi-b-run-pick").value) return;
  biBuildOpenRun(el("bi-b-run-pick").value)
    .catch((failure) => biNotice(false, failure.message));
});

function biCandShown() {
  const type = el("bi-b-cand-type").value, state = el("bi-b-cand-state").value;
  return bi.build.candidates.filter((c) => (!type || c.entity_type === type)
    && (!state || c.review === state));
}

function biBuildCandTypes() {
  const select = el("bi-b-cand-type"), keep = select.value, counts = new Map();
  for (const c of bi.build.candidates) {
    counts.set(c.entity_type, (counts.get(c.entity_type) || 0) + 1);
  }
  const all = bh("option", "", "全部"); all.value = "";
  select.replaceChildren(all, ...[...counts].map(([type, count]) => {
    const option = bh("option", "", biTypeLabel(type) + "（" + count + "）");
    option.value = type; return option;
  }));
  select.value = counts.has(keep) ? keep : "";
}

function biCandLabel(candidate, item) {
  const field = biSchemaField(candidate.entity_type, item.field);
  return (field && field.label) || item.field;
}

function biDecisionMark(review) {
  const decision = BI_DECISION[review] || [review, "dim"];
  if (review !== "accepted" && review !== "rejected") return biBadge(decision[0], decision[1]);
  const icon = bh("span", "bi-state-icon", review === "accepted" ? "✓" : "✕");
  icon.setAttribute("aria-hidden", "true");
  return bh("span", "bi-state bi-state-" + review, icon, decision[0]);
}

function biBuildCandRows() {
  const body = el("bi-b-cands").tBodies[0], shown = biCandShown();
  const focused = body.contains(document.activeElement);
  const pending = bi.build.candidates.filter((c) => c.review === "pending").length;
  el("bi-b-cand-count").textContent = "顯示 " + shown.length + "／" + bi.build.candidates.length
    + "・待決定 " + pending;
  body.replaceChildren(...shown.map((candidate) => {
    const name = candidate.name || candidate.canonical_key || "（無名稱）";
    const open = biButton(name, () => biBuildPickCandidate(candidate.id), "bi-link");
    const fields = candidate.fields, first = fields.find((f) => f.change !== "same") || fields[0];
    const labels = fields.slice(0, 2).map((item) => biCandLabel(candidate, item)).join("、")
      + (fields.length > 2 ? " 等 " + fields.length + " 欄" : "");
    const cells = [
      ["卡片", [open, bh("div", "bi-meta", biTypeLabel(candidate.entity_type) + "・"
        + biCandAction(candidate))]],
      ["欄位", [labels]],
      ["提議值", [bh("div", "bi-cand-value", first ? biValue(first.value) : "—")]],
      ["狀態", [biDecisionMark(candidate.review), " ",
        candidate.errors.length ? biBadge("錯誤 " + candidate.errors.length, "bad") : "",
        candidate.warnings.length ? biBadge("警告 " + candidate.warnings.length, "warn") : ""]]];
    const row = bh("tr", "", ...cells.map(([label, parts]) => {
      const cell = bh("td", "", ...parts); cell.dataset.label = label; return cell;
    }));
    row.dataset.candidate = candidate.id;
    row.setAttribute("aria-selected", String(candidate.id === bi.build.candidateId));
    row.addEventListener("click", (event) => {
      if (!event.target.closest("button")) biBuildPickCandidate(candidate.id);
    });
    return row;
  }));
  if (!shown.length) {
    const none = bh("td", "bi-empty", bi.build.candidates.length ? "這個篩選沒有候選卡。"
      : "這次執行沒有候選卡。");
    none.colSpan = 4; body.append(bh("tr", "", none));
  }
  // The rows are drawn anew: a keyboard stays on the row it was on.
  const here = focused && body.querySelector('tr[aria-selected="true"] button');
  if (here) here.focus({preventScroll: true});
  biApplyAllLabel();
}

// -- 「全部套用」 and 「全部接受並匯入」 --------------------------------------------------
// Owner 2026-11-18. 「全部套用」 accepts every undecided candidate the filters show: the same
// check one 接受 makes, on the host, a few at a time so the count beside the button is what
// was saved. Each goes back with 待決定, so there is no confirmation. 「全部接受並匯入」 does
// the same and then 確認匯入 once, after the last batch; that write is undone with
// 「復原這次匯入」, so it asks nothing either.
const BI_APPLY_CHUNK = 20;

function biApplyAllTodo() {
  return biCandShown().filter((c) => c.review === "pending" && c.action !== "skip");
}

function biApplyAllLabel() {
  if (bi.build.applying) return;
  const open = biRunOpen(bi.build.run), todo = open ? biApplyAllTodo() : [];
  for (const [id, label] of [["bi-b-apply-all", "全部套用"],
    ["bi-b-apply-import", "全部接受並匯入"]]) {
    el(id).textContent = label + "（" + todo.length + " 張）";
    el(id).disabled = !todo.length || !!bi.build.accepting;
  }
  const filtered = el("bi-b-cand-type").value || el("bi-b-cand-state").value;
  el("bi-b-apply-note").textContent = !open ? "" : (filtered
    ? "只套用目前篩選顯示的" : "套用所有待決定的")
    + "（＝接受，可改回待決定）；匯入寫入所有已接受的";
}

function biApplyAllName(candidate) {
  return candidate.name || candidate.canonical_key || "（無名稱）";
}

async function biApplyAll(andImport) {
  const run = bi.build.run, todo = biApplyAllTodo();
  if (!biRunOpen(run) || !todo.length || bi.build.applying) return;
  const button = el(andImport ? "bi-b-apply-import" : "bi-b-apply-all");
  const status = el("bi-b-apply-status"), others = ["bi-b-apply-all", "bi-b-apply-import"];
  const total = todo.length, left = [];
  let started = Date.now(), done = 0, applied = 0, before = 0, current = "", stopped = null;
  let importing = false;
  const show = () => {
    const seconds = Math.floor((Date.now() - started) / 1000) + " 秒";
    status.textContent = importing ? "匯入中・" + seconds
      : "套用中 " + done + "/" + total + "：" + current + "・" + seconds;
  };
  // 「下一步」 and the other button wait for it.
  bi.build.applying = true; bi.build.accepting = true; bi.build.acceptProgress = "0／" + total;
  for (const id of others) el(id).disabled = true;
  button.setAttribute("aria-busy", "true");
  status.classList.remove("bi-err"); status.replaceChildren();
  biBuildRunPick(); biBuildSteps(); biNext4();
  const tick = setInterval(show, 1000);
  let wrote = null, unwritten = null;
  try {
    for (let at = 0; at < total; at += BI_APPLY_CHUNK) {
      const chunk = todo.slice(at, at + BI_APPLY_CHUNK);
      current = biApplyAllName(chunk[0]) + (chunk.length > 1 ? " 等 " + chunk.length + " 張" : "");
      show();
      const reply = await biCall("/api/bi/runs/" + run.id + "/accept",
        {dataset: biDataset(), ids: chunk.map((c) => c.id)});
      if (!bi.build.run || bi.build.run.id !== run.id) return;  // another run was opened
      for (const fresh of reply.candidates) {
        const index = bi.build.candidates.findIndex((c) => c.id === fresh.id);
        if (index >= 0) bi.build.candidates[index] = fresh;
      }
      bi.build.run = reply.run;
      for (const result of reply.results) {
        if (result.status === "applied") applied += 1;
        else if (result.code === "already_accepted") before += 1;
        else left.push(result);
      }
      done += chunk.length; bi.build.acceptProgress = done + "／" + total;
      biNext4(); biBuildCandRows(); show();
    }
    if (andImport) {
      // Once, after every batch: what was refused stays out, and the rest is written.
      importing = true; started = Date.now(); bi.build.acceptProgress = null; biNext4(); show();
      try { wrote = await biBuildCommit(run); } catch (failure) { unwritten = failure; }
    }
  } catch (failure) {
    stopped = failure;
  } finally {
    clearInterval(tick);
    bi.build.applying = false; bi.build.accepting = false; bi.build.acceptProgress = null;
    button.removeAttribute("aria-busy");
  }
  const named = left.slice(0, 10).map((r) => (r.name || r.id) + "：" + r.reason).join("；")
    + (left.length > 10 ? "；…等 " + left.length + " 張" : "");
  const notAccepted = left.length ? left.length + " 張未" + (andImport ? "接受、沒有匯入" : "套用")
    + "：" + named : "";
  const earlier = before ? "（另有 " + before + " 張先前已接受）" : "";
  let message;
  if (stopped) {
    message = "套用到第 " + (done + 1) + " 張時停下：" + stopped.message
      + "。其餘沒有送出，可以再按一次（已接受的不會重複）" + (andImport ? "；沒有匯入" : "")
      + "。已套用 " + applied + " 張" + earlier + (notAccepted ? "；" + notAccepted : "") + "。";
  } else if (wrote) {
    const a = wrote.applied || {};
    message = "已接受 " + applied + " 張並匯入" + earlier + "（新建 " + (a.created || 0)
      + "、更新 " + (a.updated || 0) + "）；可用『復原這次匯入』撤回。"
      + (notAccepted ? notAccepted + "。" : "");
  } else if (unwritten) {
    message = "已接受 " + applied + " 張" + earlier + "，但沒有匯入：" + unwritten.message
      + "。已接受的還在，可以按「下一步：確認寫入」再試。"
      + (notAccepted ? notAccepted + "。" : "");
  } else {
    message = "已套用 " + applied + " 張" + earlier
      + (notAccepted ? "；" + notAccepted : "") + "。";
  }
  status.replaceChildren(message);
  status.classList.toggle("bi-err", !!stopped || !!unwritten || left.length > 0);
  if (wrote) {
    const committed = bi.build.run;
    status.append(" ", biButton("看匯入結果", () => biBuildStage("result"), "bi-link"), " ",
      biButton("復原這次匯入", async (event) => {
        event.target.disabled = true;  // one undo per import
        try { await biBuildUndoImport(committed); }
        catch (failure) { event.target.disabled = false; throw failure; }
        status.replaceChildren("已復原這次匯入。");
      }, "bi-btn"));
  }
  biBuildSave(); biBuildRenderRun();
}

el("bi-b-apply-all").addEventListener("click", () => biApplyAll(false)
  .catch((failure) => biNotice(false, failure.message)));
el("bi-b-apply-import").addEventListener("click", () => biApplyAll(true)
  .catch((failure) => biNotice(false, failure.message)));

el("bi-b-run-pick").addEventListener("change", () => {
  el("bi-b-apply-status").textContent = "";
});

function biBuildPickCandidate(candidateId) {
  biBuildShowCandidate(candidateId);
  biBuildSave();
  // Side by side the whole pair fits; stacked on a phone, go to the pane.
  const stacked = window.matchMedia("(max-width: 900px)").matches;
  (stacked ? el("bi-b-cand") : el("bi-b-review-split")).scrollIntoView(
    {block: stacked ? "start" : "nearest"});
}

for (const id of ["bi-b-cand-type", "bi-b-cand-state"]) {
  el(id).addEventListener("change", () => biBuildCandRows());
}

function biBuildRenderRun(detail = true) {
  const run = bi.build.run, body = el("bi-b-cands").tBodies[0];
  body.replaceChildren(); el("bi-b-chips").replaceChildren();
  biNext4();
  biBuildSteps(); biBuildRunPick();
  // With no run the table is not drawn: empty, it pushed 待審提案 out of sight below it.
  el("bi-b-review-split").hidden = !biRunReviewable(run);
  if (!biRunReviewable(run)) {
    el("bi-b-cand-count").textContent = ""; el("bi-b-cand-type").replaceChildren();
    el("bi-b-same").replaceChildren();
    el("bi-b-cand").replaceChildren(bh("p", "bi-empty", "選一列，看原文與引用。"));
    el("bi-b-chips").append(bh("p", "bi-empty", "到上一步按「Ingest」產生候選卡。"));
    biApplyAllLabel();
    return;
  }
  // What decides the next press on the line; the rest of the run's counts folded.
  const chips = [biBadge("執行 " + run.id + "・" + run.status, "dim"), ...biRunChips(run)];
  const main = chips.filter((chip) => /^(候選|錯誤|警告|已接受|新增出處)/.test(chip.textContent));
  const more = chips.filter((chip) => !main.includes(chip));
  const left = (run.warnings || []).filter((w) => w.code === "reading_left_empty")
    .map((w) => bh("p", "bi-meta", w.message));
  el("bi-b-chips").append(...main, run.kind === "trial" ? biBadge("試跑，不能寫入", "warn") : "",
    bh("details", "bi-manage", bh("summary", "", "明細"), ...more, ...left));
  if ((run.failures || []).length) {
    el("bi-b-chips").append(bh("p", "bi-err", "有 " + run.failures.length + " 段沒有判讀成功（"
      + run.failures.map((f) => (f.line_start ? "第 " + f.line_start + "–" + f.line_end + " 行："
        : "") + f.message).join("；") + "）。其他候選卡可以先審核。"),
    biButton("重試失敗的段落", async () => {
      await biCall("/api/bi/runs/" + run.id + "/retry", {dataset: biDataset()});
      await biBuildFollow(run.id); await biBuildFetchRun(run.id); biBuildRenderRun();
    }, "bi-btn"));
  }
  el("bi-b-chips").append(...biRunNothing(run), ...biRunRelations(run), ...biRunFit(run));
  biBuildSameNames(); biBuildCandTypes(); biBuildCandRows();
  if (!detail) return;
  if (bi.build.candidateId) biBuildShowCandidate(bi.build.candidateId);
  else el("bi-b-cand").replaceChildren(bh("p", "bi-empty", "選一列，看原文與引用。"));
}

function biSameNameOpen(candidate) {
  const confirmed = candidate.same_name_confirmed || [];
  return (candidate.same_name || []).filter((card) => !confirmed.includes(card.id));
}

function biBuildSameNames() {
  // New cards named like a card of another type: never merged, and never accepted in bulk.
  const box = el("bi-b-same"); box.replaceChildren();
  const open = bi.build.candidates.filter((c) => c.review === "pending"
    && biSameNameOpen(c).length);
  if (!open.length) return;
  const list = bh("ul", "bi-list");
  for (const candidate of open) {
    const cards = biSameNameOpen(candidate).map((card) => biTypeLabel(card.type)
      + "「" + card.name + "」").join("、");
    list.append(bh("li", "", bh("strong", "", candidate.name || candidate.canonical_key),
      bh("span", "bi-meta", " 新的 " + biTypeLabel(candidate.entity_type) + "；已經有 " + cards),
      bh("div", "bi-actions",
        biButton("是不同的對象，接受", () => biBuildReview(candidate.id,
          candidate.errors.length ? {confirm_same_name: true}
            : {confirm_same_name: true, review: "accepted"}), "bi-btn"),
        biButton("同一個對象，不新建", () => biBuildReview(candidate.id,
          {review: "rejected"}), "bi-btn"))));
  }
  box.append(bh("h4", "", "和既有卡片同名（" + open.length + "）"),
    bh("p", "bi-meta", "AI 想新建的卡片，名字和另一種類型的卡片相同。"
      + "不會自動合併；「全部套用」不會接受它們，會列在未套用裡。"),
    list);
}

async function biBuildReview(candidateId, body, quiet = false) {
  const run = bi.build.run;
  // One at a time: each rewrites the run's candidates, and a quick hand presses faster than
  // an answer comes back. Moving on to the write waits for them.
  bi.build.saving = (bi.build.saving || 0) + 1;
  biNext4();
  const work = (bi.build.queue || Promise.resolve()).then(() => biCall("/api/bi/runs/" + run.id
    + "/candidates/" + candidateId, {dataset: biDataset(), ...body}));
  bi.build.queue = work.catch(() => {});
  let reply;
  try { reply = await work; } finally { bi.build.saving -= 1; }
  if (!bi.build.run || bi.build.run.id !== run.id) return;  // another run was opened meanwhile
  const index = bi.build.candidates.findIndex((c) => c.id === candidateId);
  if (index >= 0) bi.build.candidates[index] = reply.candidate;
  bi.build.run = reply.run;
  if (!quiet) { biBuildSave(); biBuildRenderRun(); }
}

async function biBuildDecide(candidateId, review) {
  // Shown before the answer comes: the row's mark, a word on what was done, and on to the next
  // row still undecided, as 180 of them are worked through one after another.
  const list = biCandShown(), at = list.findIndex((c) => c.id === candidateId);
  const next = [...list.slice(at + 1), ...list.slice(0, Math.max(at, 0))]
    .find((c) => c.review === "pending");
  const candidate = bi.build.candidates.find((c) => c.id === candidateId);
  const before = candidate.review;
  const name = candidate.name || candidate.canonical_key || "";
  const show = (id) => {
    bi.build.candidateId = id;
    biBuildCandRows(); biBuildShowCandidate(id); biBuildRowInView();
    biBuildSave();
    el("bi-b-cand").scrollTop = 0;
    const row = el("bi-b-cands").querySelector('tr[data-candidate="' + id + '"]');
    if (row) row.querySelector("button").focus({preventScroll: true});
    // Stacked on a phone the row just opened is above: its pane is what comes next.
    if (window.matchMedia("(max-width: 900px)").matches) el("bi-b-cand").scrollIntoView();
  };
  candidate.review = review;
  el("bi-b-cand-last").replaceChildren(biDecisionMark(review), " " + name);
  show(next ? next.id : candidateId);
  if (!next) biNotice(true, "這個篩選裡的候選卡都決定了。");
  try {
    await biBuildReview(candidateId, {review}, true);
    biBuildSave(); biBuildRenderRun(false);
  } catch (failure) {
    // Not saved, so it must not look decided: back to that row, with why.
    const kept = bi.build.candidates.find((c) => c.id === candidateId);
    if (kept) kept.review = before;
    el("bi-b-cand-last").replaceChildren();
    show(candidateId);
    biNext4();
    biNotice(false, "「" + name + "」沒有存到，還是" + BI_DECISION[before][0] + "："
      + failure.message + "。");
  }
}

function biSourceName(sourceId, fallback) {
  const source = (bi.build.sources || []).find((s) => s.id === sourceId);
  return source ? source.name : fallback || "來源";
}

function biEvidence(item) {
  if (!item.evidence.length) return bh("span", "bi-meta", "—");
  return bh("span", "", ...item.evidence.map((e) => {
    const {line_start: first, line_end: last, default: _, ...others} = e.locator || {};
    const place = [...(first ? ["第 " + first + (last && last !== first ? "–" + last : "") + " 行"]
      : []), ...Object.entries(others).map(([k, v]) => k + " " + v)].join("・");
    const stance = {refutes: "反駁", context_only: "僅背景"}[e.stance];
    return bh("span", "bi-meta", "「" + e.excerpt + "」（",
      e.source_id ? biButton(biSourceName(e.source_id, e.source_name),
        () => biBuildCandSource(item, e), "bi-link bi-source-link") : "",
      (place ? "・" + place : "") + "）" + (stance ? "〔" + stance + "〕" : "") + " ");
  }));
}

function biBuildShowCandidate(candidateId) {
  const candidate = bi.build.candidates.find((c) => c.id === candidateId);
  const box = el("bi-b-cand"); box.replaceChildren();
  if (!candidate) return;
  bi.build.candidateId = candidateId; bi.build.peek = null;
  for (const row of el("bi-b-cands").tBodies[0].rows) {
    row.setAttribute("aria-selected", String(row.dataset.candidate === candidateId));
  }
  const open = biRunOpen(bi.build.run);
  const head = bh("h4", "", (candidate.name || candidate.canonical_key || "（無名稱）") + "・"
    + biTypeLabel(candidate.entity_type));
  const match = candidate.match === "existing" ? "對應到既有卡片（版本 "
    + candidate.base_version + "）" : candidate.match === "ambiguous" ? "有名稱相近的既有卡片"
    : "新卡片";
  const parts = [head];
  if (candidate.review !== "pending") parts.push(bh("p", "", biDecisionMark(candidate.review)));
  if (open) {
    parts.push(bh("div", "bi-actions",
      biButton("接受", () => biBuildDecide(candidate.id, "accepted"), "go"),
      biButton("拒絕", () => biBuildDecide(candidate.id, "rejected"), "bi-btn"),
      biButton("待決定", () => biBuildReview(candidate.id, {review: "pending"}), "bi-btn")));
  }
  const selfIds = candidate.match_ids || [];
  const current = candidate.match === "existing" && selfIds.length
    ? biButton("目前的卡片", () => biBuildPeek(selfIds[0]), "bi-link") : null;
  if (current) current.id = "bi-b-cand-current";
  parts.push(bh("p", "bi-meta", match + "・" + biCandAction(candidate),
    current ? "・" : "", current || ""));
  if (candidate.action === "unchanged" && (candidate.citations || []).length) {
    parts.push(bh("p", "bi-meta", "內容不變。接受後只把這份來源加進這些欄位的出處："
      + candidate.citations.map((name) => (biSchemaField(candidate.entity_type, name) || {}).label
        || name).join("、") + "。"));
  }
  if (candidate.errors.length) {
    parts.push(bh("ul", "bi-err", ...candidate.errors.map((e) => bh("li", "", e.message))));
  }
  if (candidate.warnings.length) {
    parts.push(bh("ul", "bi-warn", ...candidate.warnings.map((w) => bh("li", "", w.message))));
  }
  const profile = bi.build.run && bi.build.run.profile;
  const view = profile && (profile.types || {})[candidate.entity_type];
  if (view && view.category) parts.push(bh("p", "bi-meta", "這個應用的說明：" + view.category));
  if (candidate.outside_profile_type) {
    parts.push(bh("p", "bi-warn", "這個類型不在這個應用的 profile 裡。"));
  } else if ((candidate.outside_profile || []).length) {
    parts.push(bh("p", "bi-warn", "這些欄位不在這個應用的 profile 裡："
      + candidate.outside_profile.join("、")));
  }
  if (open && candidate.errors.some((e) => e.code === "pair_repeated")) {
    const keep = candidate.match === "existing"
      ? {action: "update", card_id: candidate.match_ids[0]} : {action: "create"};
    parts.push(bh("div", "bi-actions", biButton("留這一張", () => biBuildReview(candidate.id,
      {match: keep}), "bi-btn"), biButton("略過", () => biBuildReview(candidate.id,
      {match: {action: "skip"}}), "bi-btn")));
  }
  if (open && candidate.match === "ambiguous") {
    parts.push(bh("div", "bi-actions", biButton("新建", () => biBuildReview(candidate.id,
      {match: {action: "create"}}), "bi-btn"), ...candidate.match_ids.map((id) =>
      biButton("合併到既有卡片 " + id, () => biBuildReview(candidate.id,
        {match: {action: "update", card_id: id}}), "bi-btn")),
      biButton("略過", () => biBuildReview(candidate.id, {match: {action: "skip"}}), "bi-btn")));
  }
  const table = bh("table", "bi-table bi-stack", bh("thead", "", bh("tr", "",
    bh("th", "", "欄位"), bh("th", "", "新值與引用"), bh("th", "", "目前值"))));
  const rows = bh("tbody", "");
  for (const item of candidate.fields) {
    const basis = BI_BASIS[item.basis] || [item.basis, "dim"];
    const field = biSchemaField(candidate.entity_type, item.field);
    const input = document.createElement("input");
    input.className = "bi-input"; input.value = Array.isArray(item.value)
      ? item.value.join("；") : String(item.value ?? "");
    input.setAttribute("aria-label", "修改 " + ((field && field.label) || item.field));
    input.disabled = !open;
    const save = biButton("存", () => biBuildReview(candidate.id,
      {fields: {[item.field]: field && field.list ? input.value.split(/[;；]/)
        .map((v) => v.trim()).filter(Boolean) : input.value}}), "bi-btn",
      "儲存 " + item.field);
    save.disabled = !open;
    const merged = {fill: "填入", join: "合併清單", same: "相同", take: "你選了新值",
      capped: "AI 不能寫 verified：存 " + (item.capped || "（空）") + "，另成提案",
      key_kept: "卡片保留原本的名字",
      proposal: "值不同，變成提案，不會覆蓋", human_kept: "保留人工值，改成提案",
      bookkeeping: "記錄用欄位"}[item.merge];
    const take = open && !item.protected && (item.merge === "proposal" || item.merge === "take"
      || item.merge === "human_kept")
      ? biButton(item.take_new ? "改回提案" : "改用新值", () => biBuildReview(candidate.id,
        {take_new: {[item.field]: !item.take_new}}), "bi-btn", "這個欄位改用新值 " + item.field)
      : "";
    const others = (item.alternatives || []).map((o) => bh("div", "bi-warn",
      "另一段寫的是：" + biValue(o.value) + "（會變成提案）"));
    const change = {add: "新增", change: "變更", same: "相同", human_kept: "保留人工值，改成提議"};
    const line = bh("tr", "", bh("td", "", (field && field.label) || item.field),
      bh("td", "", bh("div", "", biBuildValue(item.value, candidate.entity_type, item.field,
        selfIds), " ", biBadge(basis[0], basis[1])),
        biEvidence(item), ...others, bh("div", "bi-cand-edit", input, save)),
      bh("td", "", biValue(item.current) + "（"
        + (merged || change[item.change] || item.change) + "）", " ", take));
    // A press on a field's row shows that field's quote in the source below.
    line.addEventListener("click", (event) => {
      if (!event.target.closest("button, input")) biBuildCandSource(item);
    });
    rows.append(line);
  }
  table.append(rows);
  parts.push(bh("div", "bi-scroll", table));
  const place = document.createElement("div"); place.id = "bi-b-cand-source";
  parts.push(place);
  box.append(...parts);
  biBuildCandSource(candidate.fields.find((f) => f.evidence.length) || null);
}

function biBuildValue(value, typeName, fieldName, selfIds) {
  // A value naming another card links to it, beside the table; the rest as they are.
  const links = biCell(value, biBuildPeek, (word) => biBuildNamedCard(word, typeName, fieldName,
    selfIds));
  for (const button of links.querySelectorAll(".bi-link")) button.classList.add("bi-card-link");
  return links;
}

async function biBuildPeek(cardId) {
  // A card opened from the one under review: it takes the pane, the table and its row stay
  // exactly as they are, and the way back is the first thing in it.
  const candidateId = bi.build.candidateId, box = el("bi-b-cand"), top = box.scrollTop;
  const candidate = bi.build.candidates.find((c) => c.id === candidateId);
  const seq = bi.build.peek = (bi.build.peekSeq = (bi.build.peekSeq || 0) + 1);
  const back = biButton("← 回到候選卡「" + ((candidate && candidate.name) || "") + "」", () => {
    biBuildShowCandidate(candidateId); box.scrollTop = top;
  }, "bi-btn");
  back.id = "bi-b-peek-back";
  const peek = bh("div", "", back, bh("p", "bi-meta", "載入卡片中…"));
  peek.id = "bi-b-peek";
  box.replaceChildren(peek); box.scrollTop = 0;
  back.focus({preventScroll: true});
  let reply;
  try {
    reply = await biCall("/api/bi/cards/" + encodeURIComponent(cardId) + "?dataset="
      + encodeURIComponent(biDataset()));
  } catch (failure) {
    if (seq === bi.build.peek) {
      peek.replaceChildren(back, bh("p", "bi-err", "卡片開不了：" + failure.message + "。"));
    }
    return;
  }
  if (seq !== bi.build.peek) return;
  const table = biListTable(["欄位", "值"]);
  for (const item of reply.fields) {
    biRow(table, [item.label, biBuildValue(item.value, reply.card.entity_type, item.field,
      [cardId])]);
  }
  const seen = new Map();
  for (const e of reply.evidence || []) if (!seen.has(e.source_id)) seen.set(e.source_id, e);
  const place = document.createElement("div"); place.id = "bi-b-cand-source";
  peek.replaceChildren(back, bh("h4", "", reply.card.name + "・"
    + biTypeLabel(reply.card.entity_type)), table.box,
  ...(seen.size ? [bh("p", "bi-meta", "來源：", ...[...seen.values()].flatMap((e, index) => [
    index ? "、" : "", biButton(biSourceName(e.source_id, e.source_name),
      () => biBuildCandSource({evidence: [e]}, e), "bi-link bi-source-link")]))] : []), place);
}

function biQuoteAt(text, quote) {
  // Line ends and indents may differ between the source and a quote taken from its lines.
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return null;
  const pattern = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
  return new RegExp(pattern).exec(text);
}

async function biBuildCandSource(item, chosen = null) {
  const box = el("bi-b-cand-source"); if (!box) return;
  const seq = bi.build.sourceSeq = (bi.build.sourceSeq || 0) + 1;
  const evidence = chosen || (item && item.evidence.find((e) => e.source_id));
  if (!evidence) {
    box.replaceChildren(bh("p", "bi-meta", "這個欄位沒有來源原文。"));
    return;
  }
  const texts = bi.build.texts = bi.build.texts || new Map();
  let view = texts.get(evidence.source_id);
  if (!view) {
    box.replaceChildren(bh("p", "bi-meta", "載入原文中…"));
    try {
      view = await call("/api/bi/sources/" + encodeURIComponent(evidence.source_id)
        + "/markdown?dataset=" + encodeURIComponent(biDataset()));
      texts.set(evidence.source_id, view);
    } catch (failure) {
      if (seq === bi.build.sourceSeq) {
        box.replaceChildren(bh("p", "bi-err", "讀不到原文：" + failure.message + "。"),
          biButton("重試", () => biBuildCandSource(item), "bi-btn"));
      }
      return;
    }
    if (seq !== bi.build.sourceSeq) return;
  }
  const text = view.markdown || "", found = biQuoteAt(text, evidence.excerpt || "");
  const pre = document.createElement("pre"); pre.id = "bi-b-cand-src"; pre.tabIndex = 0;
  if (found) {
    pre.append(text.slice(0, found.index), bh("mark", "", found[0]),
      text.slice(found.index + found[0].length));
  } else pre.textContent = text;
  box.replaceChildren(bh("h4", "", "原文：" + view.source.name),
    ...(found ? [] : [bh("p", "bi-warn", "原文裡找不到這段引用，請對照上面的引用。")]), pre);
  const mark = pre.querySelector("mark");
  if (mark) pre.scrollTop = Math.max(0, mark.offsetTop - 40);
  if (chosen) box.scrollIntoView({block: "nearest"});
}

// -- steps 5-6: commit and result --------------------------------------------
function biBuildSummary() {
  const run = bi.build.run, box = el("bi-b-summary"); box.replaceChildren();
  el("bi-b-commit-msg").replaceChildren();
  if (!run) return;
  const s = run.summary || {};
  const accepted = bi.build.candidates.filter((c) => c.review === "accepted");
  const count = (action) => accepted.filter((c) => c.action === action).length;
  const citing = accepted.filter((c) => c.action === "unchanged"
    && (c.citations || []).length).length;
  box.append(bh("p", "", "目的地：資料集「" + biDataset() + "」・schema " + run.schema_ref),
    bh("ul", "", bh("li", "", "新建 " + count("create") + " 張"),
      bh("li", "", "更新 " + count("update") + " 張"),
      ...(citing ? [bh("li", "", "新增出處 " + citing + " 張（內容不變）")] : []),
      bh("li", "", "拒絕或略過 " + ((s.rejected || 0) + (s.skip || 0)) + " 張"),
      bh("li", "", "還沒決定 " + (s.pending || 0) + " 張（不會寫入）")),
    bh("p", "bi-meta", "按「確認匯入」後，所有已接受的候選卡一次寫入；有任何卡片在審核後被改過，"
      + "就一張都不寫，請重新檢查。寫入後可以整批復原。"));
  el("bi-b-commit-go").disabled = !accepted.some((c) => ["create", "update"].includes(c.action)
    || (c.citations || []).length);
}

async function biBuildCommit(run) {
  // 「確認匯入」 and 「全部接受並匯入」 write the same way. Pressed again, or retried after a
  // lost reply, the host answers with the write it already made (`already`).
  const reply = await biCall("/api/bi/runs/" + run.id + "/commit", {dataset: biDataset()});
  bi.build.run = reply.run; bi.build.result = reply; bi.loaded = {};
  biRefreshCounts();
  // The commit may have made proposals, and moved the vault's state.
  biBuildVault().catch((failure) => biNotice(false, "知識庫狀態沒有載入：" + failure.message));
  return reply;
}

async function biBuildUndoImport(run) {
  await biCall("/api/bi/import/undo", {dataset: biDataset(), import_id: run.commit.import_id});
  biNotice(true, "已復原這次匯入。"); bi.loaded = {}; biRefreshCounts();
}

el("bi-b-commit-go").addEventListener("click", async () => {
  const run = bi.build.run, msg = el("bi-b-commit-msg"); msg.replaceChildren();
  const button = el("bi-b-commit-go"); button.disabled = true;
  try {
    await biBuildCommit(run);
    biBuildStage("result");
  } catch (failure) {
    const cards = (failure.payload && failure.payload.cards) || [];
    msg.append(bh("p", "bi-err", "沒有寫入：" + failure.message
      + (cards.length ? "（" + cards.map((c) => c.name).join("、") + "）" : "")));
    if (failure.code === "cards_changed") {
      msg.append(biButton("重新檢查並回到審核", async () => {
        const again = await biCall("/api/bi/runs/" + run.id + "/recheck",
          {dataset: biDataset()});
        bi.build.run = again.run; bi.build.candidates = again.candidates;
        biBuildStage("review");
      }, "go"));
    }
  } finally { button.disabled = false; }
});

function biBuildResult() {
  const run = bi.build.run, box = el("bi-b-done"); box.replaceChildren();
  if (!run || !run.commit) return;
  const done = bi.build.result || {applied: run.commit, index: {message: ""}};
  const applied = done.applied || run.commit;
  box.append(bh("p", "", "執行 " + run.id + " 已寫入（匯入編號 " + run.commit.import_id + "）。"),
    bh("ul", "", bh("li", "", "新建 " + (applied.created || 0)),
      bh("li", "", "更新 " + (applied.updated || 0)),
      bh("li", "", "不變 " + (applied.unchanged || 0)),
      ...(applied.citations ? [bh("li", "", "新增出處 " + applied.citations)] : []),
      bh("li", "", "成為待審提議 " + (applied.proposals || 0)),
      done.skipped != null ? bh("li", "", "略過 " + done.skipped) : "",
      done.pending != null ? bh("li", "", "未決定、沒有寫入 " + done.pending) : ""),
    bh("p", "bi-meta", (done.index && done.index.message) || "BI 卡片寫入後即可查詢。"),
    bh("div", "bi-actions",
      biButton("到卡片查看", () => biJump("cards"), "go"),
      biButton("看 Dashboard", () => biJump("dashboard"), "bi-btn"),
      biButton("復原這次匯入", () => biBuildUndoImport(run), "bi-btn"),
      biButton("再匯入另一份來源", () => {
        bi.build.run = null; bi.build.candidates = []; biBuildStage("source");
      }, "bi-btn")));
}

function biRenderReadOnly() {
  const info = biCurrent(), readOnly = biReadOnly();
  el("bi-demo").hidden = readOnly || !biIsBi();
  // A shared knowledge base (vault) is shared by commit, push and publish in
  // step 3; the platform copy is for a dataset on this PC only.
  el("bi-publish").hidden = readOnly || biDataset().startsWith("vault-");
  // Step 1 stays reachable: it holds the select, the only way to another dataset.
  if (readOnly && bi.view === "build") bi.view = "dashboard";
  const banner = el("bi-ro"); banner.hidden = !readOnly;
  banner.classList.remove("stopped");
  if (!readOnly) return;
  const sub = biSubOf(info.name);
  const by = biSubField(info, sub, "published_by") || "發佈者";
  const version = biSubField(info, sub, "version") || "?";
  el("bi-ro-title").textContent = "唯讀：" + by + " 發佈的 v" + version;
  const status = biSubField(info, sub, "status");
  const when = biSubField(info, sub, "published_at");
  let note = ((sub && sub.name) || biSubField(info, sub, "identity") || info.name)
    + (when ? " · 發佈於 " + biTime(when) : "") + " · 不能匯入或提更正單";
  if (status === "stopped_no_access") {
    banner.classList.add("stopped");
    note = "已停止更新（無權限）：你仍可讀這一版，但不會再收到新版本。 · " + note;
  } else if (status === "offline") {
    note = "無法連線平台，目前顯示 v" + version + " · " + note;
  }
  el("bi-ro-note").textContent = note;
}

// -- 已訂閱的資料集 ---------------------------------------------------------------
async function biLoadSubs() {
  biStatus("bi-status-subs", "loading", "正在讀取訂閱…");
  try {
    const reply = await biCall("/api/bi/subscriptions");
    bi.subs = reply.subscriptions || []; bi.subsState = reply;
  } catch (failure) {
    el("bi-subs-count").textContent = "—";
    biStatus("bi-status-subs", "error", "訂閱清單沒有載入：" + failure.message + "。", biLoadSubs);
    return;
  }
  biStatus("bi-status-subs", "");
  biRenderSubs(); biRenderBar(); biRenderReadOnly();
}

function biRenderSubs() {
  const list = el("bi-subs-list"); list.replaceChildren();
  el("bi-subs-count").textContent = String(bi.subs.length);
  if (!bi.subs.length) list.append(bh("li", "bi-empty", "還沒有訂閱任何資料集。"));
  for (const sub of bi.subs) {
    const key = sub.dataset || sub.name;
    const status = BI_SUB_STATUS[sub.status] || [sub.status || "未知", "dim"];
    const li = bh("li", ""); li.dataset.sub = sub.name || key;
    const main = bh("div", "bi-sub-main",
      bh("span", "bi-sub-name", sub.name || key),
      bh("span", "bi-meta", (sub.published_by || "—") + " 發佈 · v" + (sub.version || "?")
        + (sub.published_at ? " · " + biTime(sub.published_at) : "")));
    const badges = bh("div", "bi-card-top", biBadge(status[0], status[1]));
    if (sub.status === "update_available" && sub.latest) {
      badges.append(bh("span", "bi-meta", "最新 v" + sub.latest
        + (sub.latest_note ? "：" + sub.latest_note : "")));
    }
    main.append(badges);
    const actions = bh("div", "bi-actions");
    actions.append(biButton("開啟", () => biOpenSub(key), "bi-btn",
      "開啟「" + (sub.name || key) + "」（唯讀）"));
    if (sub.status === "update_available") {
      actions.append(biButton("更新", (event) => biUpdateSub(sub, event.currentTarget), "go",
        "更新「" + (sub.name || key) + "」到最新版"));
    }
    actions.append(biButton("取消訂閱", (event) => biUnsubscribeAsk(sub, event.currentTarget),
      "bi-btn", "取消訂閱「" + (sub.name || key) + "」"));
    li.append(main, actions); list.append(li);
  }
}

// 瀏覽平台上的資料集: asks the platform (refresh=1) what this member may read.
async function biBrowseAvailable() {
  const list = el("bi-subs-avail"), button = el("bi-subs-browse");
  button.disabled = true; button.setAttribute("aria-busy", "true");
  biStatus("bi-status-avail", "loading", "正在詢問 Shared Platform…");
  let reply;
  try { reply = await biCall("/api/bi/subscriptions?refresh=1"); }
  catch (failure) {
    biStatus("bi-status-avail", "error", "沒有讀到平台上的資料集：" + failure.message + "。",
      biBrowseAvailable);
    return;
  } finally { button.disabled = false; button.removeAttribute("aria-busy"); }
  biStatus("bi-status-avail", "");
  bi.subs = reply.subscriptions || bi.subs; biRenderSubs(); biRenderBar(); biRenderReadOnly();
  list.replaceChildren(); list.hidden = false;
  if (reply.configured === false) {
    list.append(bh("li", "bi-empty", "這台電腦還沒設定 Shared Platform（Settings → Shared "
      + "platform）。"));
    return;
  }
  if (reply.connection === "unreachable") {
    list.append(bh("li", "bi-empty", "無法連線 Shared Platform；已訂閱的資料集照常可讀。"));
    return;
  }
  const found = reply.available || [];
  if (!found.length) list.append(bh("li", "bi-empty", "目前沒有其他你可以訂閱的資料集。"));
  for (const item of found) {
    const li = bh("li", ""); li.dataset.avail = item.name;
    li.append(bh("div", "bi-sub-main", bh("span", "bi-sub-name", item.name),
      bh("span", "bi-meta", "v" + item.version + (item.description ? " · " + item.description : "")
        + (item.owner ? " · " + String(item.owner).replace(/^\w+:/, "") : ""))));
    li.append(bh("div", "bi-actions", biButton("訂閱",
      (event) => biSubscribe(item, event.currentTarget), "go", "訂閱「" + item.name + "」")));
    list.append(li);
  }
}
el("bi-subs-browse").addEventListener("click", () => biBrowseAvailable());

async function biSubscribe(item, button) {
  button.disabled = true; button.setAttribute("aria-busy", "true");
  try {
    const reply = await biCall("/api/bi/subscriptions/subscribe", {dataset: item.name});
    const now = reply.subscription || {};
    biNotice(true, "已訂閱「" + item.name + "」v" + (now.version || item.version)
      + "，可在資料集選單的「已訂閱」開啟（唯讀）。");
    const row = button.closest("li"); if (row) row.remove();
    await biLoad();
  } catch (failure) {
    biNotice(false, "沒有訂閱：" + failure.message);
  } finally { button.disabled = false; button.removeAttribute("aria-busy"); }
}

async function biOpenSub(key) {
  bi.want = key; biLeaveDataset(); await biLoad();
  el("bi-dataset").focus();
}

async function biUpdateSub(sub, button) {
  button.disabled = true; button.setAttribute("aria-busy", "true");
  biNotice(true, "");
  try {
    const reply = await biCall("/api/bi/subscriptions/update", {dataset: sub.name});
    const now = reply.subscription || {};
    biNotice(true, reply.already ? "「" + sub.name + "」已是最新版本。"
      : "已更新「" + sub.name + "」到 v" + (now.version || sub.latest || "") + "。");
    await biLoad();
  } catch (failure) {
    biNotice(false, "沒有更新：" + failure.message);
  } finally { button.disabled = false; button.removeAttribute("aria-busy"); }
}

function biUnsubscribeAsk(sub, button) {
  biConfirm(button.closest("li") || button.parentElement, "取消訂閱「" + sub.name
    + "」？這台電腦上的副本會被移除，之後要再到 Shared Platform 選取才能讀。", "確定取消訂閱",
  () => biUnsubscribe(sub, button));
}

async function biUnsubscribe(sub, button) {
  button.disabled = true; button.setAttribute("aria-busy", "true");
  try {
    await biCall("/api/bi/subscriptions/unsubscribe", {dataset: sub.name});
    biNotice(true, "已取消訂閱「" + sub.name + "」。");
    if (biSubOf(biDataset()) === sub) { bi.want = "demo"; biLeaveDataset(); }
    await biLoad();
  } catch (failure) {
    biNotice(false, "沒有取消訂閱：" + failure.message);
  } finally { button.disabled = false; button.removeAttribute("aria-busy"); }
}

// -- 發佈到 Shared Platform ------------------------------------------------------
async function biLoadPublishState() {
  const dataset = biDataset();
  if (biReadOnly()) { el("bi-pub-state").replaceChildren(); bi.publish = null; return; }
  try {
    const reply = await biCall("/api/bi/publish/status?dataset=" + encodeURIComponent(dataset));
    if (dataset !== biDataset()) return;
    bi.publish = reply;
  } catch (failure) {
    bi.publish = null; el("bi-pub-state").replaceChildren(); return;
  }
  biRenderPublishState();
}

function biRenderPublishState() {
  const box = el("bi-pub-state"); box.replaceChildren();
  const last = bi.publish && bi.publish.last;
  if (!last) return;
  if (last.status === "pending_review") {
    box.append(biBadge("待審核", "warn"), bh("span", "bi-meta", (last.name || "")
      + " v" + last.version + " 送出於 " + biTime(last.at) + "，等待管理員審核"));
  } else {
    box.append(biBadge("已發佈 v" + last.version + "（" + biTime(last.at) + "）", "good"),
      bh("span", "bi-meta", (last.name || "") + " · 讀者："
        + (last.readers === "organization" ? "全公司" : "我的團隊")));
  }
}

function biRenderPublishWhat() {
  const info = biCurrent() || {}, state = bi.publish || {};
  const box = el("bi-pub-what"); box.replaceChildren();
  const cards = state.cards != null ? state.cards : info.cards || 0;
  const ul = bh("ul", "",
    bh("li", "", "卡片 " + cards + " 張，含每個欄位的來源"),
    bh("li", "", "修改歷史（誰、何時、為什麼改）"),
    bh("li", "", "不含待審提議"
      + (state.proposals ? "（" + state.proposals + " 筆不會分享）" : "")),
    bh("li", "", "匯入檔只留檔名，不含你電腦上的資料夾路徑"));
  box.append(bh("strong", "", "將分享："), ul);
  const last = state.last;
  el("bi-pub-first").hidden = !(!last || last.status === "pending_review");
  // The platform name is chosen once, at the first publish.
  el("bi-pub-name-box").hidden = !!(last && last.name);
  if (!el("bi-pub-name").value && state.name) el("bi-pub-name").value = state.name;
  el("bi-pub-dataset").textContent = "資料集「" + biDataset() + "」"
    + (last && last.name ? " → " + last.name + "（上次 v" + last.version + "）"
      : " → 第一次發佈，平台會指定名稱與版本號");
}

function biPubOrg() {
  const org = el("bi-pub-org").checked;
  el("bi-pub-confirm-box").hidden = !org;
  if (!org) el("bi-pub-org-confirm").checked = false;
  el("bi-pub-team").textContent = org ? "全公司（平台上所有成員）" : "我的團隊（預設）";
}

async function biOpenPublish() {
  biPanel("publish", true);
  el("bi-pub-result").hidden = true;
  el("bi-pub-err").textContent = "";
  el("bi-pub-org").checked = false; biPubOrg();
  el("bi-pub-name").value = "";
  biRenderPublishWhat();
  el("bi-pub-note").focus();
  await biLoadPublishState();
  biRenderPublishWhat();
}

el("bi-publish").addEventListener("click", () => {
  if (el("bi-publish-panel").hidden) biOpenPublish(); else biPanel("publish", false);
});
el("bi-pub-cancel").addEventListener("click", () => {
  biPanel("publish", false); el("bi-publish").focus();
});
el("bi-pub-org").addEventListener("change", biPubOrg);

function biPublishProblem(failure) {
  const payload = failure.payload || {};
  if (payload.code === "secret_found") {
    // The host names the card and field; the value itself is never shown.
    const where = [payload.card, payload.field].filter(Boolean).join(" 的 ");
    return "沒有發佈：" + (where ? "「" + where + "」" : "有一個欄位")
      + "看起來含有密碼或 token，請先修改那個欄位再發佈。";
  }
  return "沒有發佈：" + (BI_PUB_ERRORS[payload.code] || failure.message);
}

el("bi-publish-panel").addEventListener("submit", async (event) => {
  event.preventDefault();
  const problem = el("bi-pub-err"); problem.textContent = "";
  const note = el("bi-pub-note").value.trim();
  if (!note) {
    problem.textContent = BI_PUB_ERRORS.note_required;
    el("bi-pub-note").setAttribute("aria-invalid", "true"); el("bi-pub-note").focus(); return;
  }
  el("bi-pub-note").removeAttribute("aria-invalid");
  const org = el("bi-pub-org").checked, confirmed = el("bi-pub-org-confirm").checked;
  if (org && !confirmed) {
    problem.textContent = BI_PUB_ERRORS.organization_unconfirmed;
    el("bi-pub-org-confirm").focus(); return;
  }
  const payload = {dataset: biDataset(), note, readers: org ? "organization" : "team",
    confirm_organization: org && confirmed};
  const platformName = el("bi-pub-name-box").hidden ? "" : el("bi-pub-name").value.trim();
  if (platformName) {
    if (!/^[a-z0-9]+(-[a-z0-9]+)*\/[a-z0-9]+(-[a-z0-9]+)*$/.test(platformName)) {
      problem.textContent = "平台名稱是 namespace/name，只能用小寫英文字母、數字與 -。";
      el("bi-pub-name").focus(); return;
    }
    payload.name = platformName;
  }
  const button = el("bi-pub-go"); button.disabled = true; button.setAttribute("aria-busy", "true");
  button.textContent = "發佈中…";
  try {
    const reply = await biCall("/api/bi/publish", payload);
    biPanel("publish", false); el("bi-pub-note").value = "";
    biRenderPublishResult(reply);
    await biLoadPublishState();
  } catch (failure) {
    problem.textContent = biPublishProblem(failure);
  } finally {
    button.disabled = false; button.removeAttribute("aria-busy"); button.textContent = "發佈";
  }
});

function biRenderPublishResult(reply) {
  const box = el("bi-pub-result"); box.replaceChildren(); box.hidden = false;
  const pending = reply.status === "pending_review";
  box.classList.toggle("pending", pending);
  const ref = (reply.name || "") + "@" + (reply.version || "");
  if (pending) {
    box.append(bh("h3", "", "已送出，待審核"),
      bh("p", "", "第一次發佈需要管理員審核：" + ref + " 核准後，讀者才看得到。"));
  } else {
    box.append(bh("h3", "", "已發佈 " + ref),
      bh("p", "", "訂閱的同事會看到「有新版本」，按「更新」後就讀得到這一版。"));
  }
  box.append(biButton("關閉", () => { box.hidden = true; el("bi-publish").focus(); }, "bi-btn"));
  box.tabIndex = -1; box.focus();
}

// -- 新增資料集 and 安裝 schema ---------------------------------------------------
// A dataset is created with a name and a schema, which it keeps. A schema file
// is validated by the host; every problem is listed with the place it is at.
function biPanel(which, open) {
  const panel = el("bi-" + which + "-panel"), button = el("bi-" + which);
  panel.hidden = !open; button.setAttribute("aria-expanded", String(open));
  if (open) {
    el("bi-advanced").open = true;
    for (const other of ["new", "install", "publish"]) {
      if (other === which) continue;
      el("bi-" + other + "-panel").hidden = true;
      el("bi-" + other).setAttribute("aria-expanded", "false");
    }
  }
}

async function biRefreshSchemas() {
  const reply = await biCall("/api/bi/schemas");
  bi.schemas = reply.schemas || [];
}

function biRenderSchemaChoices(chosen) {
  const select = el("bi-new-schema"), keep = chosen || select.value;
  select.replaceChildren();
  for (const item of bi.schemas) {
    const option = document.createElement("option");
    option.value = item.ref || item.id + "@" + item.version;
    const kinds = (item.types || []).map((type) => type.label || type.name);
    option.textContent = item.title + "（" + option.value + "）"
      + (item.source === "installed" ? " · 已安裝" : " · 內建 BI")
      + (kinds.length ? " · " + kinds.length + " 種類型" : "");
    select.append(option);
  }
  if (keep && bi.schemas.some((item) => (item.ref || item.id + "@" + item.version) === keep)) {
    select.value = keep;
  }
}

async function biOpenNew(chosen) {
  biPanel("new", true);
  el("bi-new-err").textContent = "";
  const select = el("bi-new-schema"); select.disabled = true;
  try { await biRefreshSchemas(); }
  catch (failure) { el("bi-new-err").textContent = "Schema 清單沒有載入：" + failure.message; }
  finally { select.disabled = false; }
  biRenderSchemaChoices(chosen);
  el("bi-new-name").focus();
}

el("bi-new").addEventListener("click", () => {
  if (el("bi-new-panel").hidden) biOpenNew(); else biPanel("new", false);
});
el("bi-new-cancel").addEventListener("click", () => {
  biPanel("new", false); el("bi-new").focus();
});
el("bi-new-panel").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = el("bi-new-name").value.trim(), schema = el("bi-new-schema").value;
  const problem = el("bi-new-err"); problem.textContent = "";
  if (!BI_NAME.test(name)) {
    problem.textContent = "名稱只能用英文字母、數字、- 與 _，1–40 個字。";
    el("bi-new-name").setAttribute("aria-invalid", "true"); el("bi-new-name").focus(); return;
  }
  el("bi-new-name").removeAttribute("aria-invalid");
  if (!schema) { problem.textContent = "請選一個 schema。"; return; }
  const button = el("bi-new-go"); button.disabled = true; button.setAttribute("aria-busy", "true");
  try {
    const reply = await biCall("/api/bi/datasets", {name, schema});
    biPanel("new", false); el("bi-new-name").value = "";
    bi.want = reply.dataset.name; biLeaveDataset();
    biNotice(true, "已建立資料集「" + reply.dataset.name + "」（schema "
      + reply.dataset.schema + "）。");
    await biLoad();
  } catch (failure) {
    problem.textContent = "沒有建立：" + failure.message;
    el("bi-new-name").focus();
  } finally { button.disabled = false; button.removeAttribute("aria-busy"); }
});

el("bi-install").addEventListener("click", () => {
  biPanel("install", el("bi-install-panel").hidden);
  if (!el("bi-install-panel").hidden) el("bi-schema-file").focus();
});
el("bi-install-cancel").addEventListener("click", () => {
  biPanel("install", false); el("bi-install").focus();
});
el("bi-schema-file").addEventListener("change", () => {
  el("bi-install-go").disabled = !el("bi-schema-file").files.length;
  el("bi-install-msg").replaceChildren();
});

function biInstallResult(reply, failure) {
  const box = el("bi-install-msg"); box.replaceChildren();
  if (failure) {
    box.append(bh("p", "bi-err", "沒有安裝：" + failure.message));
    const errors = (failure.payload && failure.payload.errors) || [];
    if (errors.length) {
      const list = bh("ul", "bi-errors"); list.setAttribute("aria-label", "schema 的問題");
      for (const item of errors) {
        list.append(bh("li", "", bh("code", "", item.path || "$"), text("：" + item.message)));
      }
      box.append(list);
    }
    return;
  }
  const ref = reply.id + "@" + reply.version;
  box.append(bh("p", "bi-ok", (reply.already ? "已經安裝過（內容相同）：" : "已安裝：") + ref),
    bh("div", "bi-actions", biButton("用這個 schema 新增資料集", () => biOpenNew(ref), "go")));
}

async function biInstall(filename, jsonText) {
  const button = el("bi-install-go"); button.setAttribute("aria-busy", "true");
  el("bi-install-msg").replaceChildren(bh("p", "bi-meta", "驗證中…"));
  try {
    const reply = await biCall("/api/bi/schemas/install", {filename, json_text: jsonText});
    try { await biRefreshSchemas(); } catch (e) { /* the list refreshes on the next load */ }
    biInstallResult(reply, null);
    biRenderBar();
  } catch (failure) {
    biInstallResult(null, failure);
  } finally { button.removeAttribute("aria-busy"); }
}

el("bi-install-panel").addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = el("bi-schema-file").files[0];
  if (!file) return;
  let content;
  try {
    content = new TextDecoder("utf-8", {fatal: true}).decode(await file.arrayBuffer());
  } catch (e) {
    biInstallResult(null, new Error("這個檔案不是 UTF-8 編碼的 JSON。"));
    return;
  }
  await biInstall(file.name, content.replace(/^﻿/, ""));
});

el("bi-example").addEventListener("click", async () => {
  const button = el("bi-example"); button.disabled = true;
  try {
    const example = await biCall("/api/bi/schemas/example");
    await biInstall(example.schema.filename, example.schema.json_text);
    const files = el("bi-example-files"); files.replaceChildren(); files.hidden = false;
    files.append(text("範例 CSV（依序匯入，連結才找得到對象）："));
    const row = bh("div", "bi-files");
    for (const item of example.csv || []) {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob(["﻿" + item.text], {type: "text/csv"}));
      link.download = item.filename; link.textContent = item.filename;
      row.append(link);
    }
    files.append(row);
  } catch (failure) {
    biInstallResult(null, failure);
  } finally { button.disabled = false; }
});"""


# Each block opens on its own line above; the page has none there.
BI_CSS, BI_PANE_HTML, BI_JS = BI_CSS[1:], BI_PANE_HTML[1:], BI_JS[1:]
BI_CSS = BI_CSS.replace("/* BI_CHART_CSS */", BI_CHART_CSS, 1)
BI_JS = BI_JS.replace("/* BI_CHART_JS */", BI_CHART_JS.rstrip(), 1)
