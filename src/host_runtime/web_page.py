"""The page `host_runtime.web` serves, as one string.

Kept here rather than as a file beside the package so that an installed
wheel carries it without package data, and so that nothing on the machine
can replace what the browser is served.

Everything is inline: no font, no script and no stylesheet is fetched. A
company machine installs this bundle with `--no-index` behind a proxy that
reaches no content delivery network, and a page that went looking for one
would render wrong exactly where it matters.

The page is generic. It knows about Skills, Workflows, runs and one Agent,
which is the platform's own vocabulary, and it knows nothing about the
weekly report or any other piece of work. A new asset appears in it the day
it is installed.
"""

from __future__ import annotations

from host_runtime.bi_chart_html import BI_CHART_CSS, BI_CHART_JS

# Keep JavaScript escape sequences intact.  A normal Python string turns such
# sequences as ``\n`` into literal line breaks inside JavaScript quoted strings,
# which makes the whole inline script fail to parse and leaves the page inert.
PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent</title>
<style>
:root {
  --bg: #ffffff; --panel: #f6f7f9; --line: #e2e5ea; --ink: #1c1f24;
  --dim: #666d78; --accent: #2f6db5; --good: #2e7d4f; --bad: #b3352f;
  --accent-soft: #eaf2fb; --selected: #dceafb; --warn: #8a5a00;
  --mono: ui-monospace, "Cascadia Mono", Consolas, monospace;
  --avatar-filter: none;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #15181c; --panel: #1d2127; --line: #2c323a; --ink: #e6e9ee;
    --dim: #97a0ac; --accent: #74a9e8; --good: #6cc48d; --bad: #e8827c;
    --accent-soft: #1d3046; --selected: #243e5b; --warn: #e6b75a; --avatar-filter: invert(1);
  }
}
:root[data-theme="dark"] {
  --bg: #15181c; --panel: #1d2127; --line: #2c323a; --ink: #e6e9ee;
  --dim: #97a0ac; --accent: #74a9e8; --good: #6cc48d; --bad: #e8827c;
  --accent-soft: #1d3046; --selected: #243e5b; --warn: #e6b75a; --avatar-filter: invert(1);
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.5 "Segoe UI", system-ui, -apple-system, sans-serif;
}
.app-shell { display: grid; grid-template-columns: 280px minmax(0, 1fr); min-height: 100vh; }
.sidebar {
  position: sticky; top: 0; display: flex; flex-direction: column; height: 100vh;
  min-width: 0; padding: 16px 12px; border-right: 1px solid var(--line);
  background: var(--panel); overflow: hidden;
}
.brand { padding: 2px 8px 14px; border-bottom: 1px solid var(--line); }
.brand h1 { margin: 0; font-size: 18px; font-weight: 700; }
.brand .note { display: block; margin-top: 3px; }
/* The person's pixel-art avatar (owner 2026-10-07): frame 1 at rest, the
   other frames while a turn runs. Wide frames reach right, never push text. */
.avatar-stage { height: 48px; margin-bottom: 6px; overflow: visible; }
.avatar-stage img { height: 48px; width: auto; image-rendering: pixelated;
  filter: var(--avatar-filter); }
.avatar-choices { display: flex; flex-wrap: wrap; gap: 8px; }
.avatar-choice { display: flex; flex-direction: column; align-items: center; gap: 4px;
  min-width: 72px; padding: 6px; background: var(--panel); }
.avatar-choice img { height: 40px; image-rendering: pixelated; filter: var(--avatar-filter); }
.avatar-choice[aria-checked="true"] { outline: 2px solid var(--accent); }
/* Files attached to the next message (owner 2026-10-08). */
.attachment-chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 8px 0; }
.attachment-chip { display: inline-flex; align-items: center; gap: 6px; padding: 2px 8px;
  border: 1px solid var(--line); border-radius: 12px; background: var(--panel);
  font-size: 12px; max-width: 260px; }
.attachment-chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.attachment-chip.bad { border-color: var(--bad); color: var(--bad); }
.attachment-chip button { border: 0; background: none; cursor: pointer; padding: 0 2px; }
.attach-button { font-size: 18px; padding: 0 6px; }
.mic-button[aria-pressed="true"] { color: #b42318; }
.mic-status { font-size: 13px; color: #475467; }
#ask.dropping { outline: 2px dashed var(--accent); }
.asked-files { font-size: 12px; color: var(--dim); margin: 2px 0 0 12px; }
.side-actions { display: grid; gap: 4px; padding: 12px 0; }
.side-actions button {
  min-height: 42px; padding: 9px 10px; color: var(--ink); background: transparent;
  border: 1px solid transparent; border-radius: 8px; text-align: left; font: inherit;
  font-weight: 600; cursor: pointer;
}
.side-actions button:hover, .side-actions button[aria-current="page"] {
  background: var(--selected); border-color: var(--line);
}
.side-actions button::before { display: inline-block; width: 24px; color: var(--accent); }
#new-conversation::before { content: "+"; font-size: 20px; line-height: 0; }
#nav-capabilities::before { content: "\25c7"; }
#nav-settings::before { content: "\2699"; }
#nav-schedules::before { content: "\25f7"; }
#nav-knowledge::before { content: "\25a4"; }
#nav-tasks::before { content: "\2630"; }
#nav-reviews::before { content: "\2611"; }
#nav-memory::before { content: "\25ce"; }
/* The memory page (accumulated memory M4): the person's own memory. Panes are
   divs, not sections (a section is hidden unless it is an open panel). */
.mem-tabs { display: flex; flex-wrap: wrap; gap: 4px; margin: 0 0 12px;
  border-bottom: 1px solid var(--line); }
.mem-tabs button { min-height: 44px; padding: 8px 14px; color: var(--dim);
  background: transparent; border: 0; border-bottom: 3px solid transparent;
  font: inherit; font-weight: 600; cursor: pointer; }
.mem-tabs button[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--accent); }
.mem-count { margin-left: 6px; color: var(--dim); font-size: 12px; font-weight: 400; }
.mem-notice { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px;
  min-height: 22px; margin: 0 0 10px; color: var(--dim); font-size: 13px; }
.mem-notice.good { color: var(--good); }
.mem-notice.bad { color: var(--bad); }
.mem-pane { max-width: 980px; }
/* A pane's loading or error line (B3): visible at once, never empty counts. */
.mem-status { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px;
  min-height: 44px; margin: 0 0 12px; padding: 8px 12px; border: 1px dashed var(--line);
  border-radius: 6px; color: var(--dim); font-size: 14px; }
.mem-status.error { border-style: solid; border-color: var(--bad); color: var(--bad); }
.mem-spinner { flex: none; width: 14px; height: 14px; border: 2px solid var(--line);
  border-top-color: var(--accent); border-radius: 50%; animation: mem-spin 1s linear infinite; }
@keyframes mem-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .mem-spinner { animation: none; } }
.mem-intro { color: var(--dim); font-size: 13px; margin: 0 0 12px; }
.mem-item { margin: 0 0 10px; padding: 10px 14px; border: 1px solid var(--line);
  border-radius: 10px; background: var(--panel); overflow-wrap: anywhere; }
.mem-item-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.mem-item-head strong { font-size: 15px; }
.mem-pairs { display: grid; grid-template-columns: max-content minmax(0, 1fr);
  gap: 4px 12px; margin: 8px 0; font-size: 14px; }
.mem-pairs dt { color: var(--dim); }
.mem-pairs dd { margin: 0; min-width: 0; }
.mem-new { color: var(--accent); font-weight: 600; }
.mem-actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 0; }
.mem-btn { display: inline-flex; align-items: center; justify-content: center;
  min-height: 44px; min-width: 44px; padding: 0 14px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--bg); color: var(--ink); font: inherit;
  font-size: 14px; cursor: pointer; }
.mem-btn:hover { border-color: var(--accent); }
.mem-btn.primary { border-color: var(--accent); background: var(--accent); color: var(--bg);
  font-weight: 600; }
.mem-btn.danger { border-color: var(--bad); color: var(--bad); }
.mem-btn.link { border-color: transparent; background: transparent; color: var(--accent);
  padding: 0 8px; }
.mem-btn.link:hover { text-decoration: underline; }
.mem-btn[disabled] { opacity: .5; cursor: default; }
.mem-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 0 6px;
  margin: 2px 0; color: var(--dim); font-size: 13px; }
.mem-text { margin: 0 0 4px; font-size: 15px; }
.mem-group { margin: 18px 0 8px; font-size: 15px; }
.mem-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }
.mem-chip { display: inline-flex; align-items: center; min-height: 44px; padding: 0 0 0 12px;
  border: 1px solid var(--line); border-radius: 22px; background: var(--bg); font-size: 13px; }
.mem-chip.entity { border-color: var(--accent); }
.mem-chip .mem-btn { border: 0; background: transparent; color: var(--dim); }
.mem-chip .mem-btn:hover { color: var(--bad); }
.mem-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 0 12px; }
.mem-field { min-height: 44px; padding: 8px 10px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--bg); color: var(--ink); font: inherit; font-size: 14px; }
.mem-toolbar input.mem-field { flex: 1 1 220px; min-width: 0; }
select.mem-field { width: auto; flex: 0 1 220px; min-width: 0; max-width: 100%; }
.mem-check { display: inline-flex; align-items: center; gap: 8px; min-height: 44px;
  font-size: 14px; cursor: pointer; }
.mem-check input { width: 20px; height: 20px; margin: 0; }
.mem-editor { margin: 8px 0 0; }
.mem-editor textarea { min-height: 120px; font: 14px/1.5 "Segoe UI", system-ui, sans-serif; }
.mem-inline { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 0; }
.mem-inline input.mem-field { flex: 1 1 200px; min-width: 0; }
.mem-conflict { margin: 8px 0; padding: 8px 12px; border: 1px solid var(--warn);
  border-radius: 8px; }
.mem-conflict p { margin: 4px 0; }
.mem-danger { margin: 8px 0; padding: 10px 12px; border: 1px solid var(--bad); border-radius: 8px; }
.mem-danger p { margin: 4px 0; }
.mem-note-body { margin: 6px 0; line-height: 1.6; }
.mem-note-body > :first-child { margin-top: 0; }
.mem-note-head { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
.tag.mem-orphan { color: var(--warn); border-color: var(--warn); }
.tag.mem-off { color: var(--dim); }
.mem-results { display: grid; gap: 4px; margin: 6px 0 0; }
.mem-results .mem-btn { justify-content: flex-start; text-align: left; }
.mem-list { margin: 6px 0; padding-left: 20px; }
.mem-list li { margin: 4px 0; overflow-wrap: anywhere; }
.mem-sub { margin: 14px 0 0; padding: 12px 14px; border: 1px solid var(--line);
  border-radius: 10px; }
.mem-sub h3 { margin: 0 0 8px; font-size: 15px; }
.mem-records dt { font-weight: 600; color: var(--ink); }
.mem-records dd { color: var(--dim); }
.mem-inline input.mem-field.mem-days { flex: 0 0 7em; width: 7em; }
#mem-refresh { flex: none; white-space: nowrap; }
.mem-used summary { padding: 11px 0; cursor: pointer; color: var(--dim); font-size: 13px; }
/* M5: the health check's findings (a distinct 待確認 type) and 「為什麼」. */
.mem-item.mem-health { border-left: 4px solid var(--warn); }
.tag.mem-health-tag { color: var(--warn); border-color: var(--warn); }
.mem-item.mem-target { outline: 2px solid var(--accent); outline-offset: 2px; }
.why-btn { display: inline-flex; align-items: center; min-height: 32px; margin: 6px 0 0;
  padding: 0 10px; border: 1px solid var(--line); border-radius: 16px; background: var(--bg);
  color: var(--dim); font: inherit; font-size: 12px; cursor: pointer; }
.why-btn:hover, .why-btn[aria-expanded="true"] { color: var(--ink); border-color: var(--accent); }
.why-box { margin: 6px 0 0; padding: 8px 12px; border: 1px solid var(--line);
  border-radius: 8px; font-size: 13px; }
.why-box ul { margin: 4px 0; padding-left: 18px; }
.why-box li { margin: 4px 0; overflow-wrap: anywhere; }
.why-box .why-kind { color: var(--dim); }
.why-box .why-gone { color: var(--bad); }
/* Which model answered (owner 2026-10-22), quietly under the answer. */
.answer-model { margin: 4px 0 0; color: var(--dim); font-size: 12px; overflow-wrap: anywhere; }
.why-box button { border: 0; background: transparent; color: var(--accent); cursor: pointer;
  font: inherit; font-size: 13px; padding: 4px 6px; min-height: 32px; }
.why-box button:hover { text-decoration: underline; }
@media (max-width: 520px) {
  .mem-pairs { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .mem-pairs dd { margin: 0 0 6px; }
}
.rv-card { border: 1px solid var(--line, #ddd); border-radius: 8px; padding: 10px 14px;
  margin: 10px 0; background: var(--panel, #fff); }
.rv-card h3 { margin: 0 0 4px; font-size: 15px; }
.rv-text { white-space: pre-wrap; background: var(--soft, #f4f6fa); border-radius: 6px;
  padding: 8px 10px; margin: 6px 0; }
.rv-tabs { display: flex; gap: 4px; margin: 8px 0; flex-wrap: wrap; }
.rv-tabs button { min-height: 44px; padding: 0 14px; }
/* Suggested Skill cards (SKILL_SUGGESTIONS S2) */
.sg-card { overflow-wrap: anywhere; }
.sg-card .sg-kind { color: var(--accent); font-size: 12px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .04em; }
.sg-why { margin: 6px 0; padding: 8px 10px; border-radius: 6px; background: var(--accent-soft);
  color: var(--ink); }
.sg-evidence { list-style: none; margin: 6px 0; padding: 0; }
.sg-evidence li { margin: 4px 0; }
.sg-evidence button { display: block; width: 100%; min-height: 44px; text-align: left;
  padding: 6px 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--bg);
  color: var(--ink); cursor: pointer; overflow-wrap: anywhere; }
.sg-evidence button:hover, .sg-evidence button:focus-visible { border-color: var(--accent); }
.sg-evidence time { color: var(--dim); margin-right: 8px; font-variant-numeric: tabular-nums; }
.sg-card .kp-actions button, .sg-ignore button { min-height: 44px; min-width: 88px; }
.sg-ignore { margin: 8px 0; padding: 8px 10px; border: 1px solid var(--line); border-radius: 6px; }
.sg-ignore .sg-picks { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }
.sg-ignore .sg-picks button[aria-pressed="true"] { background: var(--accent); color: #fff;
  border-color: var(--accent); }
.sg-ignore input[type=text] { width: 100%; min-height: 44px; margin: 4px 0 8px;
  background: var(--bg); color: var(--ink); border: 1px solid var(--line); border-radius: 6px;
  padding: 6px 10px; }
.sg-gone { color: var(--bad); }
.turn.sg-target { outline: 2px solid var(--accent); outline-offset: 4px; border-radius: 8px; }
#xp-suggest { margin: 10px 0; padding: 8px 12px; border: 1px solid var(--line);
  border-radius: 8px; min-width: 0; }
#xp-suggest legend { font-weight: 600; padding: 0 4px; }
#xp-card .kp-actions button { min-height: 44px; }
#shared-signin input, #shared-signin button, #team-card input, #team-card button {
  min-height: 44px; }
/* An example, not saved values (#233); not used while the platform decides. */
#team-card input::placeholder { color: var(--dim); opacity: 0.6; font-style: italic; }
#team-card input:disabled, #team-card button:disabled {
  color: var(--dim); background: var(--panel); cursor: not-allowed; }
#xp-suggest label { display: flex; align-items: center; gap: 8px; min-height: 44px; }
#xp-sensitivity label { align-items: flex-start; padding: 6px 0; }
#xp-sensitivity input { margin-top: 4px; min-width: 20px; min-height: 20px; }
.rv-tabs [aria-selected="true"] { background: var(--accent, #2b6cb0); color: #fff; }
.kp-banner { border: 1px solid #c9d8f5; background: #eef3fb; border-radius: 8px;
  padding: 8px 12px; margin: 8px 0; }
.task-status { display: inline-block; min-width: 86px; padding: 1px 8px; border-radius: 10px;
  font-size: 12px; text-align: center; background: var(--soft, #eef3fb); }
.task-status.running { background: #e8f0fe; color: #1a56db; }
.task-status.succeeded { background: #e6f4ea; color: #137333; }
.task-status.failed { background: #fce8e6; color: #a50e0e; }
.task-status.needs_input, .task-status.interrupted, .task-status.stopped {
  background: #fef7e0; color: #8a5a00; }
.kp-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.kp-list button { margin: 2px 6px 2px 0; }
.kp-check { display: inline-block; margin: 2px 14px 2px 0; }
/* The steps, the status and the progress stay on top while the page scrolls (owner
   2026-10-14); kpStage scrolls a new step title to just below them. */
.kp-top { position: sticky; top: 0; z-index: 6; background: var(--bg); padding-bottom: 2px; }
.kp-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.kp-advanced summary { cursor: pointer; font-weight: 600; }
.kp-assist { margin-top: 12px; border-top: 1px solid var(--line, #ddd); padding-top: 8px; }
#kp-assist-input { width: 100%; }
.kp-turn { margin: 6px 0; padding: 6px 8px; border-radius: 6px; }
.kp-user { background: var(--soft, #eef3fb); }
.kp-running { border: 1px dashed var(--accent, #2b6cb0); }
.kp-steps { margin: 4px 0 0 18px; padding: 0; }
.kp-steps .kp-now { font-weight: 600; }
.kp-steps .kp-later { opacity: 0.55; }
.kp-tabs { display: flex; gap: 4px; margin: 6px 0; }
.kp-tabs [role="tab"][aria-selected="true"] { background: var(--accent, #2b6cb0); color: #fff; }
.kp-panes { display: flex; height: 70vh; min-height: 360px; gap: 0; }
.kp-pane { position: relative; display: flex; flex-direction: column; min-width: 0;
  border: 1px solid var(--line, #ddd); border-radius: 6px; background: var(--panel, #fff);
  padding-top: 0; max-width: none; }  /* a <section>: drop the page's section padding */
.kp-pane > header { padding: 6px 48px 6px 10px; font-weight: 600; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; border-bottom: 1px solid var(--line, #ddd); }
.kp-pane-body { flex: 1; overflow: auto; position: relative; min-height: 0; }
.kp-split { flex: 0 0 8px; cursor: col-resize; touch-action: none; }
.kp-split:hover { background: var(--accent-soft, #dbe8f7); }
/* Top right, in the pane's header row, clear of the scrollbar arrows (owner 2026-10-14). */
.kp-max { position: absolute; right: 8px; top: 4px; z-index: 3; padding: 2px 8px; opacity: 0.8; }
.kp-pane.kp-maxed { position: fixed; inset: 16px; z-index: 60; flex-basis: auto !important;
  box-shadow: 0 8px 30px rgba(0,0,0,0.25); }
.kp-filebody { display: flex; flex-direction: column; overflow: hidden; }
.kp-md-view { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.kp-block { display: flex; flex-direction: column; flex: 1 1 0; min-height: 0;
  border-bottom: 1px solid var(--line, #ddd); }
.kp-block.kp-collapsed { flex: 0 0 auto; }
.kp-block.kp-collapsed .kp-block-body { display: none; }
.kp-block.kp-collapsed .kp-chev { display: inline-block; transform: rotate(-90deg); }
.kp-block-head { text-align: left; border: 0; border-bottom: 1px solid var(--line, #ddd);
  background: var(--panel, #fff); padding: 6px 10px; font-weight: 600; cursor: pointer; }
.kp-block-body { flex: 1; min-height: 0; overflow: auto; position: relative; }
.kp-diffrows, .kp-code, #kp-rule-text, .kp-gutter { font-family: ui-monospace, Consolas, monospace;
  font-size: 13px; line-height: 20px; }
.kp-drow { display: flex; white-space: pre; min-height: 20px; }
.kp-ln { flex: 0 0 3.2em; text-align: right; padding-right: 6px; color: #888;
  user-select: none; border-right: 1px solid var(--line, #ddd); }
.kp-txt { padding-left: 8px; }
.kp-hunk { color: #888; background: var(--accent-soft, #eef3fb); }
.kp-none { padding: 8px 12px; }
.kp-cur { display: flex; overflow: hidden; }
.kp-gutter { flex: 0 0 6.4em; overflow: hidden; padding: 8px 0 48px; }
.kp-gline { display: flex; height: 20px; white-space: pre; }
.kp-code { padding: 8px; margin: 0; white-space: pre; tab-size: 4; }
.kp-code > div { min-height: 20px; }
.kp-editwrap { position: relative; flex: 1; overflow: hidden; }
.kp-backdrop { position: absolute; inset: 0; overflow: hidden; color: transparent;
  pointer-events: none; padding-bottom: 48px; padding-right: 48px; }
/* The backdrop only shades lines: its text never shows (a green .kp-add line drew a second
   copy under the textarea), and the extra padding lets it and the gutter scroll as far as
   the textarea, whose scrollbars add to its range (owner 2026-10-14: doubled lines). */
.kp-backdrop > div { color: transparent; width: max-content; min-width: 100%; }
#kp-rule-text { position: absolute; inset: 0; width: 100%; height: 100%; box-sizing: border-box;
  border: 0; resize: none; background: transparent; overflow: auto; color: inherit;
  padding: 8px; margin: 0; white-space: pre; tab-size: 4; }
#kp-after-preview { padding: 8px 12px; overflow: auto; flex: 1; }
.kp-ai { display: flex; flex-direction: column; gap: 6px; padding: 8px;
  overflow: hidden; }
/* The buttons sit on the pane's bottom edge, level with the file pane; the
   right padding keeps them clear of the maximize button. */
.kp-ai > .kp-actions { margin: 0; padding-right: 44px; align-items: center; }
.kp-ai #kp-assist-log { flex: 1; overflow: auto; max-height: none; min-height: 0; }
.kp-ai #kp-assist-input { width: 100%; box-sizing: border-box; }
.kp-progress { display: flex; align-items: center; gap: 10px; padding: 6px 10px;
  background: var(--panel, #fff); border: 1px solid var(--line, #ddd); border-radius: 6px; }
.kp-progress progress { flex: 0 0 260px; height: 14px; }
.kp-progress .note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* Knowledge as three guided steps (owner 2026-10-14, ui-ux-pro-max: progress indicator,
   progressive disclosure, one primary action per step, focus moves to the step). */
.kp-stepper ol { list-style: none; display: flex; gap: 8px; padding: 0; margin: 8px 0 14px; }
.kp-stepper li { flex: 1; min-width: 0; }
.kp-stepper button { width: 100%; min-height: 52px; display: flex; align-items: center; gap: 10px;
  text-align: left; padding: 10px 12px; border: 1px solid var(--line, #ddd); border-radius: 10px;
  background: var(--panel, #fff); cursor: pointer; transition: border-color 150ms ease; }
.kp-stepper button small { display: block; color: var(--dim, #666); font-size: 12px; }
.kp-stepper button[aria-current="step"] { border-color: var(--accent, #2b6cb0);
  box-shadow: inset 0 0 0 1px var(--accent, #2b6cb0); }
.kp-stepper button:disabled { opacity: 0.45; cursor: not-allowed; }
.kp-stepper button:focus-visible, .kp-stage-title:focus-visible {
  outline: 3px solid var(--accent-soft, #c9d8f5); outline-offset: 2px; }
.kp-step-n { flex: 0 0 28px; height: 28px; border-radius: 50%; display: grid; place-items: center;
  background: var(--soft, #eef3fb); font-weight: 600; }
.kp-stepper button[aria-current="step"] .kp-step-n { background: var(--accent, #2b6cb0);
  color: #fff; }
/* A step is a <section>, which the page hides unless it is an open panel. */
.kp-stage { display: block; padding-top: 0; max-width: none; }
.kp-stage[hidden] { display: none; }
.kp-stage-title { margin: 6px 0 2px; font-size: 20px; outline: none; }
.kp-nav { display: flex; justify-content: space-between; gap: 8px; margin: 16px 0 4px;
  padding-top: 12px; border-top: 1px solid var(--line, #ddd); }
.kp-nav button { min-height: 44px; padding: 0 16px; }
.kp-sandbox-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px;
  flex-wrap: wrap; padding: 8px 12px; margin-bottom: 8px; border: 1px solid var(--line, #ddd);
  border-radius: 8px; background: var(--soft, #f4f6fa); }
#kp-sandboxes button { min-height: 44px; padding: 6px 14px; margin: 4px 6px 4px 0; }
.kp-grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.kp-form label { display: block; font-size: 13px; margin: 10px 0 4px; }
.kp-form select, .kp-form input { width: 100%; box-sizing: border-box; min-height: 36px; }
.kp-form button { margin-top: 8px; min-height: 44px; }
.kp-repos { margin-top: 12px; }
.kp-repos .kp-list button { min-height: 44px; }
.kp-ver h4 { margin: 14px 0 4px; font-size: 14px; }
.kp-ver input { width: 100%; box-sizing: border-box; min-height: 36px; }
.kp-ver ul { margin: 4px 0; padding-left: 20px; }
.kp-ver li { margin: 6px 0; }
.kp-ver .kp-ver-pair { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px; margin: 4px 0; }
.kp-ver .kp-ver-pair > div { border: 1px solid var(--line, #d0d4da); border-radius: 6px;
  padding: 6px 8px; overflow-wrap: anywhere; }
.kp-ver .kp-ver-pair > div.chosen { outline: 2px solid var(--accent, #2563eb); }
.kp-ver .kp-ver-ask { display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  margin: 6px 0; }
.kp-ver .kp-ver-ask input { flex: 1 1 220px; width: auto; }
.kp-ver .kp-warn { color: var(--warn, #9a5b00); }
#kp-repo-settings input { width: 100%; box-sizing: border-box; min-height: 36px; }
#kp-repo-settings label { display: block; font-size: 13px; margin: 10px 0 4px; }
.kp-coverage { padding: 8px 10px; border-radius: 6px; background: #e6f4ea; color: #137333; }
.kp-coverage.kp-low { background: #fef7e0; color: #8a5a00; }
.kp-q-editor textarea { width: 100%; box-sizing: border-box; font-family: ui-monospace, Consolas,
  monospace; font-size: 13px; }
@media (max-width: 720px) { .kp-stepper ol { flex-direction: column; } }
.laya-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px 14px; }
.laya-grid label { display: flex; flex-direction: column; gap: 2px; }
.settings .laya-check { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.settings .laya-check input { width: auto; margin: 0; flex: none; }
.gateway-state { font-weight: 600; margin: 0 0 8px; }
.gateway-state[data-state="serving"] { color: #137333; }
.gateway-state[data-state="starting"] { color: #8a5a00; }
.gateway-state[data-state="stopped"] { color: #b3261e; }
.gateway-facts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px;
  margin: 0 0 10px; font-size: 13px; }
.gateway-facts dt { color: var(--dim); }
.gateway-facts dd { margin: 0; overflow-wrap: anywhere; }
.gateway-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.gateway-actions button { min-height: 44px; min-width: 88px; }
.kp-ingest { display: flex; gap: 12px; align-items: stretch; height: 70vh; min-height: 380px; }
.kp-ingest-main { flex: 2 1 0; min-width: 0; display: flex; flex-direction: column;
  border: 1px solid var(--line, #ddd); border-radius: 6px; background: var(--panel, #fff); }
.kp-ingest-head { display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  border-bottom: 1px solid var(--line, #ddd); }
.kp-ingest-head strong { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
#kp-plan:empty { display: none; }
#kp-plan { padding: 6px 10px; border-bottom: 1px solid var(--line, #ddd); max-height: 40%;
  overflow: auto; }
.kp-doc { flex: 1; overflow: auto; padding: 8px 14px; max-height: none; }
.kp-ingest-side { flex: 1 1 0; min-width: 220px; display: flex; flex-direction: column; }
.kp-filelist { position: relative; flex: 1; overflow: auto; border: 1px solid var(--line, #ddd);
  border-radius: 6px; background: var(--panel, #fff); outline: none; }
.kp-filelist:focus { box-shadow: 0 0 0 2px var(--accent-soft, #c9d8f5); }
.kp-file { display: flex; align-items: center; gap: 6px; padding: 3px 8px; cursor: pointer;
  white-space: nowrap; }
.kp-file span { overflow: hidden; text-overflow: ellipsis; }
.kp-file:hover { background: var(--soft, #f4f6fa); }
.kp-file.kp-focus { background: var(--accent-soft, #dbe8f7); }
.kp-file.kp-new span { color: #137333; font-weight: 600; }
.kp-add { background: #e6f4ea; color: #137333; }
.kp-del { background: #fce8e6; color: #a50e0e; }
.kp-same { opacity: 0.7; }
.kp-markdown { max-height: 70vh; overflow: auto; }
pre.kp-added { background: var(--ok-bg, #e8f5e9); white-space: pre-wrap; padding: 8px; }
pre.kp-removed { background: var(--bad-bg, #fdecea); white-space: pre-wrap; padding: 8px; }
.schedule-grid { display: grid; gap: 14px; }
.schedule-card { border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px;
  background: var(--panel); }
.schedule-card h3 { margin: 0 0 6px; font-size: 14px; overflow-wrap: anywhere; }
.schedule-meta { color: var(--dim); font-size: 12.5px; margin: 2px 0; overflow-wrap: anywhere; }
.schedule-actions { display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  margin-top: 8px; }
.schedule-actions input, .schedule-actions select { font: inherit; min-height: 32px; }
.schedule-warning { color: var(--bad); font-size: 12.5px; }
.schedule-runs { width: 100%; font-size: 12.5px; margin-top: 8px; }
.schedule-runs td { padding: 4px 6px; vertical-align: top; overflow-wrap: anywhere; }
.schedule-form { display: grid; gap: 8px; max-width: 640px; }
.schedule-form label { font-size: 13px; font-weight: 600; }
.schedule-form input, .schedule-form select, .schedule-form textarea { font: inherit; }
.schedule-days { display: flex; flex-wrap: wrap; gap: 8px; font-size: 13px; }
.session-heading { display: flex; justify-content: space-between; align-items: center;
  margin: 8px 8px 7px; color: var(--dim); font-size: 12px; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase; }
.session-search { width: 100%; min-height: 38px; margin-bottom: 8px; font: inherit; }
.session-snippet { display: block; overflow-wrap: anywhere; color: var(--dim); }
.session-list { flex: 1; overflow-y: auto; min-height: 120px; }
.session-item { display: block; width: 100%; min-height: 58px; padding: 9px 10px;
  color: var(--ink); background: transparent; border: 0; border-radius: 7px;
  text-align: left; cursor: pointer; font: inherit; }
.session-item:hover, .session-item[aria-selected="true"] { background: var(--selected); }
.session-item strong, .session-item small { display: block; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.session-item small { margin-top: 2px; color: var(--dim); font-size: 11px; }
.session-row { position: relative; }
.session-row .session-item { padding-right: 38px; }
.session-delete-button { position: absolute; top: 50%; right: 4px; transform: translateY(-50%);
  min-width: 30px; min-height: 30px; border: 0; border-radius: 6px; background: transparent;
  color: var(--dim); cursor: pointer; opacity: 0; }
.session-row:hover .session-delete-button, .session-delete-button:focus { opacity: 1; }
.session-delete-button:hover { color: var(--bad); background: var(--bg); }
.workspace { min-width: 0; }
.topbar { display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 6px 14px; padding: 10px 18px;
  border-bottom: 1px solid var(--line); background: var(--bg); }
.topbar .who { color: var(--dim); font-size: 13px; margin-left: auto; min-width: 0;
  overflow-wrap: anywhere; }
.visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }
main { padding: 0 20px 40px; }
section { display: none; padding-top: 18px; max-width: 1480px; margin: 0 auto; }
section[data-open] { display: block; }
h2 { font-size: 15px; margin: 22px 0 8px; }
h2:first-child { margin-top: 4px; }
p.note { color: var(--dim); font-size: 13px; margin: 4px 0 12px; }

#log {
  border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
  padding: 12px; min-height: 220px; max-height: 58vh; overflow-y: auto;
}
.turn { margin: 0 0 14px; position: relative; padding: 10px 12px;
  border: 1px solid var(--line); border-radius: 10px; background: var(--bg); }
.turn:last-child { margin-bottom: 0; }
.turn:hover, .turn:focus-within { border-color: var(--accent); }
.turn-reply-ref { font-size: 12px; color: var(--dim); margin: 0 0 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.turn-tools { position: absolute; top: 6px; right: 8px; display: flex; gap: 2px;
  opacity: 0; transition: opacity .12s; background: var(--bg); border-radius: 8px; }
.turn:hover .turn-tools, .turn:focus-within .turn-tools { opacity: 1; }
.turn-tools button { min-width: 32px; min-height: 30px; padding: 2px 6px;
  border: 1px solid var(--line); border-radius: 6px; background: var(--bg);
  color: var(--ink); cursor: pointer; font-size: 13px; }
.turn-tools button[aria-pressed="true"] { background: var(--selected);
  border-color: var(--accent); }
.turn-feedback { margin: 8px 0 0; display: grid; gap: 6px; }
.turn-feedback textarea { width: 100%; min-height: 56px; box-sizing: border-box; }
.turn-feedback-row { display: flex; gap: 8px; align-items: center;
  font-size: 12px; color: var(--dim); }
.turn-feedback-saved { font-size: 12px; color: var(--dim); margin: 6px 0 0; }
.note-saved { font-size: 12px; color: var(--dim); margin: 6px 0 0; }
.note-saved.bad { color: var(--bad); }
#save-selection { position: fixed; z-index: 40; min-height: 36px; padding: 4px 12px;
  border: 1px solid var(--accent); border-radius: 8px; background: var(--bg);
  color: var(--accent); cursor: pointer; font-size: 13px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, .18); }
.turn-menu { position: fixed; z-index: 50; min-width: 170px; padding: 4px;
  border: 1px solid var(--line); border-radius: 8px; background: var(--bg);
  box-shadow: 0 6px 24px rgba(0,0,0,.18); }
.turn-menu button { display: block; width: 100%; text-align: left; padding: 8px 10px;
  border: 0; border-radius: 6px; background: transparent; color: var(--ink); cursor: pointer; }
.turn-menu button:hover, .turn-menu button:focus { background: var(--accent-soft); }
.reply-chip { display: flex; gap: 8px; align-items: center; margin: 0 0 6px; padding: 6px 10px;
  border-radius: 8px; background: var(--accent-soft); font-size: 13px; }
.reply-chip span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asked { font-weight: 600; color: var(--accent); word-break: break-word; }
.said {
  margin: 8px 0 0; line-height: 1.65; overflow-wrap: anywhere;
}
.said.bad { color: var(--bad); }
/* A running turn's live progress (owner 2026-10-19): Harness phases, recent
   tool lines, tool count and time. Names and numbers only. */
.turn-progress { margin: 0; padding: 8px 12px; max-width: 640px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--panel); font-size: 13px; line-height: 1.5;
  overflow-wrap: anywhere; }
.turn-progress .tp-status { margin: 0 0 4px; font-weight: 600; color: var(--ink); }
.turn-progress .tp-steps { display: flex; flex-wrap: wrap; gap: 4px 12px; margin: 0 0 6px;
  padding: 0; list-style: none; }
.turn-progress .tp-steps[hidden], .turn-progress .tp-tools[hidden] { display: none; }
.turn-progress .tp-steps li { margin: 0; color: var(--dim); }
.turn-progress .tp-steps li.done { color: var(--good); }
.turn-progress .tp-steps li.active { color: var(--accent); font-weight: 600; }
.turn-progress .tp-steps li.failed { color: var(--bad); }
.turn-progress .tp-tools { margin: 0 0 6px; padding: 0; list-style: none;
  font-family: var(--mono); font-size: 12px; }
.turn-progress .tp-tools li { margin: 1px 0; display: flex; gap: 6px; min-width: 0; }
.turn-progress .tp-tools .tp-name { flex: 1; min-width: 0; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.turn-progress .tp-tools .tp-mark { flex: none; width: 1.4em; text-align: center; }
.turn-progress .tp-tools .tp-mark.good { color: var(--good); }
.turn-progress .tp-tools .tp-mark.bad { color: var(--bad); }
.turn-progress .tp-tools .tp-mark.wait { color: var(--warn); }
.turn-progress .tp-tools .tp-time { flex: none; color: var(--dim); }
.turn-progress .tp-meter { margin: 0; color: var(--dim); font-variant-numeric: tabular-nums; }
/* Delegated sub-agents (multi-agent V1): one line each under the turn, side by
   side while there is room (parallel read-only ones), stacked on a phone. */
.turn-progress .tp-agents { display: grid; gap: 6px; margin: 0 0 6px; padding: 0;
  list-style: none; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
.turn-progress .tp-agents[hidden] { display: none; }
.turn-progress .tp-agent { min-width: 0; padding: 6px 8px; border: 1px solid var(--line);
  border-left: 3px solid var(--accent); border-radius: 6px; background: var(--bg); }
.turn-progress .tp-agent.done { border-left-color: var(--good); }
.turn-progress .tp-agent.failed { border-left-color: var(--bad); }
.turn-progress .tp-agent.needs_input,
.turn-progress .tp-agent.awaiting_approval { border-left-color: var(--warn); }
.turn-progress .tp-agent-head { display: flex; gap: 6px; align-items: baseline; min-width: 0; }
.turn-progress .tp-agent-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; font-weight: 600; }
.turn-progress .tp-agent-state { flex: none; font-size: 12px; color: var(--accent); }
.turn-progress .tp-agent.done .tp-agent-state { color: var(--good); }
.turn-progress .tp-agent.failed .tp-agent-state { color: var(--bad); }
.turn-progress .tp-agent.needs_input .tp-agent-state,
.turn-progress .tp-agent.awaiting_approval .tp-agent-state { color: var(--warn); }
.turn-progress .tp-agent-goal { margin: 2px 0 0; color: var(--dim); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.turn-progress .tp-agent-meter { margin: 2px 0 0; color: var(--dim); font-size: 12px;
  font-variant-numeric: tabular-nums; }
/* 委派紀錄 under an answer (multi-agent V1): collapsed by default. */
.delegation-record { margin: 8px 0 0; max-width: 720px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--panel); font-size: 13px; }
.delegation-record > summary { min-height: 44px; display: flex; align-items: center;
  padding: 0 12px; cursor: pointer; color: var(--dim); font-weight: 600; }
.delegation-record > summary:focus-visible { outline: 2px solid var(--accent);
  outline-offset: 2px; }
.delegation-record ol { margin: 0; padding: 0 12px 10px; list-style: none; }
.delegation-record li.dr-item { padding: 8px 0; border-top: 1px solid var(--line);
  min-width: 0; overflow-wrap: anywhere; }
.delegation-record .dr-head { display: flex; flex-wrap: wrap; gap: 4px 8px;
  align-items: baseline; }
.delegation-record .dr-profile { font-weight: 600; color: var(--ink); }
.delegation-record .dr-status { font-size: 12px; padding: 0 6px; border-radius: 999px;
  border: 1px solid currentColor; }
.delegation-record .dr-status.succeeded { color: var(--good); }
.delegation-record .dr-status.failed { color: var(--bad); }
.delegation-record .dr-status.needs_input,
.delegation-record .dr-status.awaiting_approval { color: var(--warn); }
.delegation-record .dr-meta { color: var(--dim); font-size: 12px;
  font-variant-numeric: tabular-nums; }
.delegation-record .dr-summary { margin: 4px 0 0; color: var(--ink); }
.delegation-record .dr-note { margin: 4px 0 0; color: var(--warn); }
.delegation-record .dr-artifacts { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 0; }
.delegation-record .dr-run { color: var(--dim); font-family: var(--mono); font-size: 12px; }
.settings .multi-agent-switch { display: flex; align-items: center; gap: 10px; min-height: 44px;
  margin: 0; font-size: 15px; color: var(--ink); }
.settings .multi-agent-switch input { width: 22px; height: 22px; margin: 0; flex: none; }
.multi-agent-docs code { font-family: var(--mono); font-size: 12px; }
.approval-card { margin: 12px 0; padding: 10px 12px; border: 1px solid var(--accent);
  border-radius: 8px; background: var(--accent-soft); }
.approval-card p { margin: 6px 0 8px; white-space: pre-wrap; overflow-wrap: anywhere; }
.approval-card button { margin-right: 8px; }
.approval-note { font-size: 13px; }
/* An action card (owner 2026-10-15): a change proposal now, agent-mode
   permissions next. One renderer, renderActionCard. */
.action-card { margin: 12px 0 0; padding: 12px 14px; max-width: 640px;
  border: 1px solid var(--accent); border-radius: 8px; background: var(--bg); }
.action-card.closed { border-color: var(--line); }
.action-card h3 { margin: 0 0 8px; font-size: 15px; line-height: 1.4; }
.action-card .card-diff { width: 100%; border-collapse: collapse; margin: 6px 0;
  font-size: 13px; table-layout: fixed; }
.action-card .card-diff th, .action-card .card-diff td { padding: 6px 8px;
  border-top: 1px solid var(--line); text-align: left; vertical-align: top;
  overflow-wrap: anywhere; }
.action-card .card-diff th { color: var(--dim); font-weight: 600; }
.action-card .card-diff .before { color: var(--dim); text-decoration: line-through; }
.action-card .card-preview { margin: 6px 0; padding: 8px 10px; max-height: 320px;
  overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; border-radius: 6px;
  background: var(--panel); font: 12.5px/1.55 var(--mono); }
.action-card .card-reason { margin: 6px 0; font-size: 13px; white-space: pre-wrap; }
.action-card .card-effects { margin: 6px 0; padding-left: 20px; font-size: 13px;
  color: var(--warn); }
.action-card .card-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
  margin-top: 10px; }
.action-card .card-actions button { min-height: 44px; min-width: 88px; }
.action-card .card-actions button.danger { color: var(--bad); }
.action-card .card-status { margin: 8px 0 0; font-size: 13px; white-space: pre-wrap;
  overflow-wrap: anywhere; }
.action-card .card-status.good { color: var(--good); }
/* Agent mode (owner 2026-10-15): the folder line under the composer and the
   cards an agent-mode turn shows while it runs. */
.agent-mode-line { display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  margin: 6px 0 0; font-size: 12.5px; color: var(--dim); overflow-wrap: anywhere; }
.agent-mode-line[hidden] { display: none; }
.agent-mode-line button { min-height: 32px; }
.agent-live-cards:empty { display: none; }
.agent-mode-backend { display: flex; gap: 8px; align-items: flex-start; margin: 6px 0; }
.agent-mode-backend .note { margin: 0; }
#agent-mode-form textarea, #agent-mode-form input:not([type=checkbox]),
#agent-folders-dialog textarea, #agent-folders-dialog input { width: 100%;
  box-sizing: border-box; }
.action-card .card-status.bad { color: var(--bad); }
.action-card .card-link { margin-top: 6px; }
.said > :first-child { margin-top: 0; }
.said > :last-child { margin-bottom: 0; }
.said p { margin: 0 0 12px; white-space: pre-wrap; }
.said h1, .said h2, .said h3, .said h4 { margin: 18px 0 8px; line-height: 1.35; }
.said h1 { font-size: 21px; }
.said h2 { font-size: 18px; }
.said h3, .said h4 { font-size: 15px; }
.said ul, .said ol { margin: 6px 0 14px; padding-left: 24px; }
.said li { margin: 3px 0; }
.said blockquote { margin: 10px 0 14px; padding: 8px 12px;
  border-left: 3px solid var(--accent); background: var(--bg); color: var(--dim); }
.said blockquote p { margin: 0; }
.said pre { margin: 10px 0 14px; padding: 12px 14px; overflow-x: auto;
  border: 1px solid var(--line); border-radius: 8px; background: var(--bg);
  font: 12.5px/1.55 var(--mono); white-space: pre; }
.said :not(pre) > code { padding: 1px 4px; border-radius: 4px;
  background: var(--accent-soft); font: .9em var(--mono); }
.said a { color: var(--accent); text-decoration: underline; }
.said .table-scroll { max-width: 100%; margin: 10px 0 16px; overflow-x: auto;
  border: 1px solid var(--line); border-radius: 8px; background: var(--bg); }
.said table { width: max-content; min-width: 100%; font-size: 13px; }
.said th, .said td { min-width: 110px; padding: 9px 11px;
  vertical-align: top; white-space: normal; overflow-wrap: anywhere; }
.said th:first-child, .said td:first-child { min-width: 170px; }
.said th { color: var(--ink); background: var(--accent-soft); }
.said tr:nth-child(even) td { background: var(--panel); }
.waiting { color: var(--dim); font-style: italic; }
form.ask { margin: 12px 0 0; border: 1px solid var(--line); border-radius: 12px;
  overflow: hidden; background: var(--bg); }
form.ask textarea {
  display: block; font: inherit; padding: 12px 14px; color: var(--ink);
  background: transparent; border: 0; border-radius: 0; min-height: 96px;
}
form.ask:focus-within { outline: 2px solid var(--accent); outline-offset: -1px; }
form.ask textarea:focus { outline: 0; }
.composer-footer { display: flex; align-items: center; justify-content: space-between;
  gap: 12px; min-height: 52px; padding: 8px 10px; border-top: 1px solid var(--line);
  background: var(--panel); }
/* The conversation backend sits at the top of the chat pane and the model
   under the message box (owner 2026-10-21). */
.backend-control { display: flex; align-items: center; gap: 9px; min-width: 0;
  flex: 0 1 auto; }
.backend-control[hidden] { display: none; }
.backend-control select, .model-control select { width: auto; min-width: 190px;
  max-width: 330px; min-height: 44px; border: 0; background: transparent; font: inherit;
  font-weight: 600; padding: 7px 28px 7px 8px; }
.backend-state, .model-state { min-width: 0; color: var(--dim); font-size: 12px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.model-control { display: flex; align-items: center; gap: 9px; min-width: 0; flex: 1; }
.model-control select:disabled { opacity: .6; cursor: not-allowed; }
.model-readonly { padding: 7px 8px; font-weight: 600; overflow-wrap: anywhere; }
.link-button { border: 0; background: transparent; color: var(--accent); padding: 5px;
  cursor: pointer; font: inherit; font-size: 12px; }
.send-button { min-width: 78px; }
.command-menu { border: 1px solid var(--line); border-radius: 10px; padding: 6px;
  background: var(--panel); margin: 8px 0; }
.command-menu button { display: grid; grid-template-columns: 180px 1fr; width: 100%;
  text-align: left; gap: 12px; border: 0; background: transparent; color: var(--ink);
  padding: 8px; border-radius: 6px; cursor: pointer; }
.command-menu button:hover, .command-menu button:focus { background: var(--accent-soft); }
.command-menu code { color: var(--accent); }
select, textarea {
  width: 100%; padding: 9px 10px; color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; font: 13px var(--mono);
}
textarea { min-height: 100px; resize: vertical; }
button.go {
  font: inherit; font-weight: 600; padding: 9px 18px; cursor: pointer;
  color: #fff; background: var(--accent); border: none; border-radius: 8px;
}
button.go[disabled] { opacity: .5; cursor: default; }
button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible,
textarea:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
button[aria-busy="true"] { cursor: wait; }
.hint { color: var(--dim); font-size: 12px; margin: 8px 0 0; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.status-card { border: 1px solid var(--line); border-radius: 10px; padding: 12px;
  background: var(--panel); }
.status-card strong { display: block; margin-bottom: 4px; }
.quick { display: flex; flex-wrap: wrap; gap: 7px; margin: 10px 0 14px; }
.quick button { font: 12px var(--mono); color: var(--accent); background: var(--bg);
  border: 1px solid var(--line); border-radius: 999px; padding: 6px 10px; cursor: pointer; }
.settings { padding: 14px; }
.settings label { display: block; font-size: 12px; color: var(--dim); margin: 10px 0 4px; }
.settings input, .settings select, .settings textarea {
  width: 100%; font: 13px var(--mono); padding: 9px 10px;
  color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 8px; }
.settings .two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
dialog { width: min(500px, calc(100vw - 32px)); color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 12px; padding: 0; box-shadow: 0 18px 60px #0005; }
dialog::backdrop { background: #0008; }
.dialog-body { padding: 20px; }
.dialog-body h2 { margin-top: 0; font-size: 18px; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }

table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th, td { border-bottom: 1px solid var(--line); padding: 8px 10px; text-align: left; }
th { color: var(--dim); font-weight: 600; white-space: nowrap; }
td.mono, th.mono { font-family: var(--mono); font-size: 12.5px; }
.shared-cert { border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px;
  margin: 10px 0; }
.shared-cert legend { color: var(--dim); font-weight: 600; padding: 0 4px; }
#shared-cert-fingerprint { display: block; font-family: var(--mono); font-size: 12.5px;
  overflow-wrap: anywhere; }
tr:last-child td { border-bottom: none; }
.card {
  border: 1px solid var(--line); border-radius: 10px; overflow: hidden;
  background: var(--panel); margin: 0 0 16px;
}
.tag {
  display: inline-block; font-size: 11.5px; padding: 1px 7px; border-radius: 999px;
  border: 1px solid var(--line); color: var(--dim); background: var(--bg);
}
.tag.on { color: var(--good); border-color: var(--good); }
.tag.off { color: var(--dim); }
.empty { color: var(--dim); font-style: italic; padding: 10px; }
.boot-error { margin: 12px 16px 0; padding: 12px 14px; color: var(--bad);
  border: 1px solid var(--bad); border-radius: 8px; background: var(--panel); }
.workspace-head { display: flex; align-items: end; justify-content: space-between;
  gap: 16px; margin: 4px 0 14px; }
.workspace-head h2 { margin: 0 0 2px; font-size: 18px; }
.workspace-head p { margin: 0; }
.cap-tabs { display: flex; gap: 4px; flex-wrap: wrap; border-bottom: 1px solid var(--line); }
.cap-tabs button { min-height: 44px; padding: 9px 14px; color: var(--dim);
  background: transparent; border: 0; border-bottom: 3px solid transparent;
  font: inherit; font-weight: 600; cursor: pointer; }
.cap-tabs button[aria-selected="true"] { color: var(--accent); border-bottom-color: var(--accent); }
.cap-count { margin-left: 5px; padding: 1px 6px; border-radius: 999px;
  background: var(--panel); color: var(--dim); font-size: 11px; }
.cap-layout { display: grid; grid-template-columns: minmax(300px, .8fr) minmax(420px, 1.2fr);
  min-height: 460px; border: 1px solid var(--line); border-radius: 10px;
  overflow: hidden; margin-top: 12px; }
.cap-browser { border-right: 1px solid var(--line); background: var(--bg); }
.cap-search { padding: 12px; border-bottom: 1px solid var(--line); }
.cap-search input, .market-tools input, .market-tools select { width: 100%; min-height: 44px;
  padding: 9px 11px; color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; font: inherit; }
.cap-list { max-height: 520px; overflow-y: auto; }
.cap-item { display: block; width: 100%; min-height: 58px; padding: 10px 12px;
  text-align: left; color: var(--ink); background: transparent; border: 0;
  border-bottom: 1px solid var(--line); cursor: pointer; font: inherit; }
.cap-item:hover { background: var(--panel); }
.cap-item[aria-selected="true"] { background: var(--selected); }
.cap-item strong, .cap-item small { display: block; }
.cap-item small { color: var(--dim); margin-top: 2px; }
.cap-detail { padding: 20px; background: var(--panel); overflow-y: auto; max-height: 560px; }
.cap-detail h3 { margin: 0 0 4px; font-size: 18px; }
.identity { color: var(--dim); font: 12px var(--mono); overflow-wrap: anywhere; }
.detail-description { margin: 16px 0; }
.meta-grid { display: grid; grid-template-columns: max-content 1fr; gap: 7px 14px;
  margin: 16px 0; font-size: 13px; }
.meta-grid dt { color: var(--dim); }
.meta-grid dd { margin: 0; overflow-wrap: anywhere; }
.inline-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.inline-actions a { display: inline-flex; align-items: center; min-height: 38px;
  padding: 7px 11px; color: var(--accent); border: 1px solid var(--line);
  border-radius: 8px; background: var(--bg); text-decoration: none; font-weight: 600; }
.action-box { margin-top: 16px; padding: 14px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--bg); }
.action-box label { display: block; margin: 9px 0 4px; font-size: 12px; color: var(--dim); }
.workflow-field { margin: 12px 0; }
.field-group { margin: 16px 0 4px; font-weight: 600; color: var(--dim);
  text-transform: uppercase; font-size: 12px; letter-spacing: .04em; }
.workflow-field input, .workflow-field select { width: 100%; min-height: 44px; padding: 9px 10px;
  color: var(--ink); background: var(--bg); border: 1px solid var(--line);
  border-radius: 8px; font: inherit; }
.workflow-field input[type="checkbox"] { width: 22px; min-height: 22px; }
.workflow-field input[type="file"] { min-height: 44px; padding: 9px 0; border: 0; }
.workflow-field input[hidden] { display: none; }
/* A yes/no field as two choices that say what each does (owner 2026-10-25). */
.boolean-choices { display: grid; gap: 6px; margin: 4px 0; }
.boolean-choice { display: flex; align-items: center; gap: 8px; min-height: 36px;
  padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px; cursor: pointer; }
.workflow-field .boolean-choice input[type="radio"] { width: 18px; min-height: 18px;
  margin: 0; padding: 0; flex: none; }
.workflow-field .field-refresh, .use-last { margin: 6px 0 0; min-height: 36px;
  padding: 6px 12px; color: var(--ink); background: var(--bg); border: 1px solid var(--line);
  border-radius: 8px; font: inherit; cursor: pointer; }
.use-last { display: block; width: 100%; text-align: left; margin: 0 0 8px; }
.upload-list { margin: 6px 0; padding-left: 20px; font-size: 13px; }
.workflow-field .field-error { color: var(--bad); margin: 4px 0; font-size: 12px; }
.workflow-field [aria-invalid="true"] { border-color: var(--bad); }
/* A Workflow's run form inside the chat (owner 2026-10-15). */
.chat-run-form { display: block; margin: 12px 0 0; padding: 12px 14px; max-width: 640px;
  border: 1px solid var(--line); border-radius: 8px; background: var(--bg); }
.chat-run-form > summary { min-height: 44px; display: flex; align-items: center;
  font-weight: 600; cursor: pointer; }
.chat-run-form .optional-fields { margin: 8px 0; }
.chat-run-form .optional-fields > summary { min-height: 44px; display: flex; align-items: center;
  cursor: pointer; color: var(--dim); }
.chat-run-form .chat-run-note { margin: 6px 0; font-size: 13px; color: var(--dim);
  white-space: pre-wrap; }
.chat-run-form .chat-run-missing { margin: 8px 0; padding: 8px 10px; border-radius: 8px;
  border: 1px solid var(--bad); color: var(--ink); }
.chat-run-form .chat-run-actions { display: flex; gap: 8px; align-items: center;
  flex-wrap: wrap; margin-top: 12px; }
.chat-run-form .chat-run-actions button { min-height: 44px; min-width: 88px; }
.chat-run-form .chat-run-result { margin: 8px 0 0; white-space: pre-wrap;
  overflow-wrap: anywhere; font-size: 13px; }
.markdown-panel { max-height: 330px; margin: 8px 0 16px; padding: 16px;
  overflow: auto; white-space: pre-wrap; word-break: break-word; color: var(--ink);
  border: 1px solid var(--line); border-radius: 8px; background: var(--bg);
  font: 12.5px/1.65 var(--mono); }
.market { margin-top: 28px; padding-top: 22px; border-top: 1px solid var(--line); }
.market-tabs { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 10px;
  border-bottom: 1px solid var(--line); }
.market-tabs button { min-height: 42px; padding: 8px 14px; color: var(--dim);
  background: transparent; border: 0; border-bottom: 3px solid transparent;
  font: inherit; font-weight: 600; cursor: pointer; }
.market-tabs button[aria-selected="true"] { color: var(--accent);
  border-bottom-color: var(--accent); }
.market-tools { display: grid; grid-template-columns: minmax(220px, 1fr) 180px 170px auto auto;
  gap: 8px; align-items: center; margin: 12px 0; }
.market-tools a { min-height: 44px; display: inline-flex; align-items: center;
  padding: 8px 12px; border: 1px solid var(--line); border-radius: 8px;
  color: var(--accent); text-decoration: none; font-weight: 600; white-space: nowrap; }
.market-grid { display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px; }
.market-card { border: 1px solid var(--line); border-radius: 9px; background: var(--panel); }
.badges { display: flex; flex-wrap: wrap; gap: 5px; margin: 9px 0; }
.tag.warn { color: var(--warn); border-color: var(--warn); }
.section-status { min-height: 22px; color: var(--dim); font-size: 13px; }
/* Capabilities: one list for installed, drafts and switched-off assets. */
.cap-filters { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip { min-height: 44px; padding: 6px 12px; color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 999px; font: inherit; font-size: 13px;
  cursor: pointer; }
.chip[aria-pressed="true"] { color: var(--accent); border-color: var(--accent);
  background: var(--accent-soft); font-weight: 600; }
.cap-row { display: flex; align-items: center; gap: 6px; padding-right: 8px;
  border-bottom: 1px solid var(--line); }
.cap-row .cap-item { flex: 1; min-width: 0; border-bottom: 0; }
.cap-row .cap-item small { overflow-wrap: anywhere; }
.cap-row[data-state="draft"] { box-shadow: inset 4px 0 0 var(--warn); }
.cap-row[data-state="disabled"] .cap-item strong { color: var(--dim); }
.cap-row[data-fresh] { box-shadow: inset 4px 0 0 var(--good); }
.restart-note { color: var(--warn); }
.cap-item[aria-current="true"] { background: var(--selected); }
.cap-state { display: inline-block; margin-top: 4px; }
.btn { min-height: 44px; padding: 8px 14px; color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; font: inherit; font-weight: 600;
  cursor: pointer; }
.btn[disabled] { opacity: .5; cursor: default; }
.btn.danger { color: var(--bad); border-color: var(--bad); }
.btn.small { min-height: 44px; padding: 6px 12px; font-size: 13px; }
.switch { position: relative; flex: none; width: 52px; min-height: 44px; padding: 0;
  background: transparent; border: 0; cursor: pointer; }
.switch::before { content: ""; position: absolute; left: 4px; top: 50%; width: 44px;
  height: 24px; margin-top: -12px; border-radius: 999px; background: var(--line);
  transition: background .15s; }
.switch::after { content: ""; position: absolute; left: 7px; top: 50%; width: 18px;
  height: 18px; margin-top: -9px; border-radius: 50%; background: var(--bg);
  box-shadow: 0 1px 2px #0004; transition: transform .15s; }
.switch[aria-checked="true"]::before { background: var(--good); }
.switch[aria-checked="true"]::after { transform: translateX(20px); }
.switch[disabled] { opacity: .5; cursor: default; }
.detail-head { display: flex; gap: 14px; align-items: flex-start;
  justify-content: space-between; flex-wrap: wrap; }
.detail-head > div:first-child { min-width: 0; flex: 1 1 220px; }
.detail-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.detail-actions .note { flex-basis: 100%; text-align: right; margin: 0; }
.detail-actions .go, .market-detail .go, .cap-row .btn { min-height: 44px; }
.tag.draft { color: var(--warn); border-color: var(--warn); }
/* Share Platform Library: expandable cards, one open at a time. */
.market-card { position: relative; display: flex; flex-direction: column; min-height: 0;
  padding: 0; border-left-width: 1px; cursor: pointer; }
.market-card:hover { border-color: var(--accent); }
.market-card[data-expanded] { grid-column: 1 / -1; cursor: default;
  border-color: var(--accent); }
.market-card h3 { margin: 0; font-size: inherit; }
.market-head { display: grid; grid-template-columns: 40px minmax(0, 1fr) auto; gap: 10px;
  align-items: center; width: 100%; min-height: 64px; padding: 14px 14px 6px;
  color: var(--ink); background: transparent; border: 0; border-radius: 9px 9px 0 0;
  text-align: left; font: inherit; cursor: pointer; }
.kind-icon { display: inline-flex; width: 40px; height: 40px; align-items: center;
  justify-content: center; border-radius: 10px; font-weight: 700; color: var(--accent);
  background: var(--accent-soft); }
.kind-icon[data-kind="workflow"] { color: var(--good); }
.market-name { display: block; font-size: 15px; font-weight: 600; overflow-wrap: anywhere; }
.market-head .identity { display: block; }
.status-badge { padding: 3px 9px; border-radius: 999px; font-size: 12px; font-weight: 600;
  white-space: nowrap; border: 1px solid var(--line); color: var(--dim); background: var(--bg); }
.status-badge[data-status="installed"] { color: var(--good); border-color: var(--good); }
.status-badge[data-status="selected"] { color: var(--accent); border-color: var(--accent); }
.market-summary { padding: 0 14px 14px 64px; }
.market-summary p { margin: 2px 0 8px; color: var(--dim); font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.market-card[data-expanded] .market-summary p { white-space: normal; }
.market-summary .badges { margin: 0; }
.market-detail { padding: 0 14px 16px 64px; border-top: 1px solid var(--line); }
.market-detail h4 { margin: 14px 0 4px; font-size: 13px; color: var(--dim);
  text-transform: uppercase; letter-spacing: .04em; }
.market-detail .inline-actions { margin-top: 12px; }
.market-outcome { margin-top: 10px; }
/* A card's published content beside its facts and actions (owner 2026-10-15). */
.market-body { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, 320px);
  gap: 8px 24px; align-items: start; }
.market-content, .market-aside { min-width: 0; }
.market-content .note { margin: 4px 0; }
.market-content pre { max-width: 100%; overflow-x: auto; white-space: pre-wrap;
  overflow-wrap: anywhere; padding: 8px 10px; border-radius: 8px; background: var(--bg);
  border: 1px solid var(--line); font-size: 12px; }
.market-content table { display: block; max-width: 100%; overflow-x: auto; }
.market-md { overflow-wrap: anywhere; line-height: 1.5; }
.market-md :is(h1, h2, h3, h4, h5, h6) { margin: 12px 0 4px; font-size: 15px; color: var(--ink);
  text-transform: none; letter-spacing: 0; }
.market-steps { margin: 4px 0; padding-left: 22px; }
.market-steps li { margin: 3px 0; overflow-wrap: anywhere; }
.market-content .mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
/* Side by side only where the open card is wide enough; else facts and actions first. */
.market-detail { container-type: inline-size; }
@container (max-width: 640px) {
  .market-body { grid-template-columns: 1fr; }
  .market-aside { order: -1; }
}
@media (max-width: 760px) {
  .market-summary, .market-detail { padding-left: 14px; }
  .detail-actions { justify-content: flex-start; }
  .detail-actions .note { text-align: left; }
}
@media (prefers-reduced-motion: reduce) {
  .switch::before, .switch::after { transition: none; }
}
.section-status.bad { color: var(--bad); }
@media (max-width: 1000px) {
  .market-tools { grid-template-columns: minmax(220px, 1fr) minmax(150px, .55fr); }
}
@media (max-width: 760px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { position: static; height: auto; max-height: 48vh; border-right: 0;
    border-bottom: 1px solid var(--line); }
  .session-list { max-height: 180px; }
  .topbar { justify-content: flex-start; }
  main { padding: 0 12px 32px; }
  th, td { padding: 7px 6px; }
  .cap-layout { grid-template-columns: 1fr; }
  .cap-browser { border-right: 0; border-bottom: 1px solid var(--line); }
  .cap-list { max-height: 260px; }
  .market-tools { grid-template-columns: 1fr; }
  .workspace-head { align-items: start; flex-direction: column; }
  .composer-footer, .backend-control, .model-control { align-items: stretch;
    flex-direction: column; }
  .backend-control { flex: 1 1 100%; gap: 2px; }
  .backend-control select, .model-control select { width: 100%; max-width: none; }
  .topbar .who { margin-left: 0; }
  .send-button { width: 100%; }
}
.answer-image { margin: 8px 0 4px; }
.answer-image img { max-width: 100%; border: 1px solid #d0d7de; border-radius: 6px;
  cursor: zoom-in; background: #fff; }
.answer-image figcaption { font-size: 12px; color: #6a737d; }

/* Files in the chat (owner 2026-10-20): every file is a chip that opens the
   viewer panel; an HTML file also shows inline in a sandboxed frame. */
.file-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 2px; }
.file-chip { display: inline-flex; align-items: center; gap: 6px; min-height: 44px;
  max-width: 100%; padding: 4px 12px; border: 1px solid var(--line); border-radius: 22px;
  background: var(--panel); color: var(--ink); font: inherit; font-size: 13px;
  cursor: pointer; }
.file-chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-chip:hover { border-color: var(--accent); }
.answer-html { margin: 8px 0 4px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--panel); max-width: 100%; }
.answer-html .frame-wrap { height: 480px; min-height: 200px; resize: vertical;
  overflow: hidden; border-bottom: 1px solid var(--line); }
.answer-html.tall .frame-wrap { height: 80vh; }
.atlas-embed-note { margin: 8px 0 4px; font-size: 13px; color: var(--dim); }
.answer-html iframe, .viewer-preview iframe { display: block; width: 100%; height: 100%;
  border: 0; background: #fff; }
.answer-html .frame-bar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  padding: 4px 8px; font-size: 13px; color: var(--dim); }
.answer-html .frame-bar .name { flex: 1 1 160px; min-width: 0; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.viewer-button { min-height: 44px; min-width: 44px; padding: 0 12px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--bg); color: var(--ink); font: inherit; font-size: 13px;
  cursor: pointer; }
.viewer-button[aria-pressed="true"] { background: var(--accent); border-color: var(--accent);
  color: #fff; }
.file-viewer { position: fixed; top: 0; right: 0; bottom: 0; width: min(720px, 52vw);
  display: flex; flex-direction: column; background: var(--bg); color: var(--ink);
  border-left: 1px solid var(--line); box-shadow: -6px 0 24px rgba(0, 0, 0, 0.18);
  z-index: 60; }
.viewer-head { display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  padding: 8px 10px; border-bottom: 1px solid var(--line); background: var(--panel); }
.viewer-head h2 { flex: 1 1 100%; order: -1; margin: 0; font-size: 15px;
  overflow-wrap: anywhere; padding-right: 52px; }
.viewer-modes { display: inline-flex; gap: 4px; }
.viewer-close { position: absolute; top: 6px; right: 8px; }
.viewer-body { flex: 1 1 auto; min-height: 0; overflow: auto; }
.viewer-preview { height: 100%; }
.viewer-preview.doc { height: auto; padding: 8px 16px; }
.viewer-preview img { max-width: 100%; display: block; margin: 8px auto; background: #fff; }
.viewer-note { margin: 8px 12px; color: var(--dim); font-size: 13px; }
.code-view { display: grid; grid-template-columns: auto minmax(0, 1fr); margin: 0;
  font: 12.5px/1.55 var(--mono); }
.code-view pre { margin: 0; padding: 8px 10px; white-space: pre; overflow: visible; }
.code-view .gutter { color: var(--dim); text-align: right; user-select: none;
  border-right: 1px solid var(--line); background: var(--panel); }
.code-scroll { overflow: auto; }
.csv-table { border-collapse: collapse; font-size: 13px; margin: 8px 12px; }
.csv-table th, .csv-table td { border: 1px solid var(--line); padding: 3px 8px;
  text-align: left; vertical-align: top; }
@media (max-width: 760px) {
  .file-viewer { width: 100vw; left: 0; border-left: 0; }
  .answer-html .frame-wrap { height: 420px; }
}
/* BI cards (Knowledge Strategy v1.3 Case A, 2026-10-21): a sub-tab of Knowledge.
   Panes are divs (a section is hidden unless it is an open panel); 44 px targets,
   colour is never the only cue (every flag carries a text badge). */
.kn-tabs { margin-top: -4px; }
.bi-pane { max-width: 1240px; min-width: 0; }
.bi-pane button.go { min-height: 44px; }
.bi-bar { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 10px 16px; padding: 12px 14px; margin: 0 0 10px; }
.bi-bar-main { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px 14px;
  min-width: 0; flex: 1 1 420px; }
.bi-bar-main > div { min-width: 0; flex: 0 1 200px; }
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
.bi-hint { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; padding: 10px 14px;
  margin: 0 0 12px; border-radius: 10px; background: var(--accent-soft); font-size: 14px; }
.bi-hint .bi-hint-text { flex: 1 1 320px; min-width: 0; }
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
.bi-err:empty { display: none; }
.bi-schema-note { flex: 1 1 100%; margin: 0; overflow-wrap: anywhere; }
.bi-schema-note:empty { display: none; }
.bi-empty-state { flex: 1 1 100%; padding: 8px 12px; border: 1px dashed var(--line);
  border-radius: 8px; overflow-wrap: anywhere; }
.bi-empty-state[hidden] { display: none; }
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
.bi-ai { margin: 12px 0; padding: 10px 12px; border: 1px solid var(--line);
  border-radius: 8px; min-width: 0; }
.bi-ai h4 { margin: 0 0 6px; }
#bi-b-ver h5 { margin: 12px 0 4px; font-size: 13px; }
.bi-substeps ol { margin-top: 0; }
.bi-manage > summary { cursor: pointer; min-height: 44px; display: inline-flex;
  align-items: center; padding: 0 12px; }
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
@media (max-width: 640px) {
  table.bi-stack thead { display: none; }
  table.bi-stack, table.bi-stack tbody, table.bi-stack tr, table.bi-stack td { display: block;
    width: 100%; }
  table.bi-stack tr { padding: 6px 0; border-bottom: 1px solid var(--line); }
  table.bi-stack td { border: 0; padding: 2px 4px; }
  table.bi-stack td[data-label]::before { content: attr(data-label) "\FF1A"; color: var(--dim);
    font-size: 12px; }
  .bi-funnel-row { grid-template-columns: minmax(60px, 96px) minmax(0, 1fr) 2.5em; }
  .bi-bar-main > div { flex: 1 1 140px; }
}
</style>
</head>
<body>
<div class="app-shell">
<aside class="sidebar" aria-label="Agent workspace">
  <div class="brand">
    <div class="avatar-stage" id="avatar-stage" hidden><img id="agent-avatar" alt=""></div>
    <h1 id="agent-name">Agent</h1>
    <span class="note" id="agent-introduction"></span>
  </div>
  <div class="side-actions">
    <button id="new-conversation" type="button">New session</button>
    <button id="nav-capabilities" type="button">Capabilities</button>
    <button id="nav-settings" type="button">Settings</button>
    <button id="nav-schedules" type="button">Schedules</button>
    <button id="nav-knowledge" type="button">Knowledge</button>
    <button id="nav-tasks" type="button">Tasks</button>
    <button id="nav-reviews" type="button">Reviews</button>
    <button id="nav-memory" type="button">記憶</button>
  </div>
  <div class="session-heading"><span>Sessions</span><span id="session-count">0</span></div>
  <input id="session-search" class="session-search" type="search"
         aria-label="Search sessions" placeholder="Search sessions">
  <div id="session-list" class="session-list" role="listbox" aria-label="Sessions"></div>
</aside>
<div class="workspace">
<header class="topbar">
  <div id="chat-backend-bar" class="backend-control">
    <select id="conversation-backend" aria-label="Conversation backend"></select>
    <span id="backend-state" class="backend-state" role="status"></span>
    <button id="backend-settings" class="link-button" type="button" hidden>
      Open Settings</button>
  </div>
  <span class="who" id="who">reading this machine&hellip;</span>
</header>
<div id="boot-error" class="boot-error" role="alert" hidden></div>
<main>
  <section id="panel-ask" data-open>
    <div id="log"></div>
    <div id="command-palette" class="command-menu" role="listbox" hidden></div>
    <div id="turn-menu" class="turn-menu" role="menu" hidden></div>
    <p id="read-only-note" class="note" role="status" hidden>
      這是 Telegram 對話，只能閱讀；要繼續請回到 Telegram。</p>
    <form class="ask" id="ask">
      <div id="reply-chip" class="reply-chip" hidden>
        <span id="reply-chip-text"></span>
        <button type="button" id="reply-chip-clear" class="link-button"
          aria-label="取消回覆">✕</button>
      </div>
      <div id="attachment-chips" class="attachment-chips" aria-live="polite" hidden></div>
      <textarea id="message" rows="3" autocomplete="off" spellcheck="true"
        placeholder="Ask naturally, or type / to choose a command"></textarea>
      <div class="composer-footer">
        <button id="attach" class="link-button attach-button" type="button"
          aria-label="附加檔案"
          title="附加檔案：圖片、PDF、CSV、HTML、TXT、JSON、YAML、MD、ZIP
（單檔 25 MB，最多 10 個）">📎</button>
        <input id="attach-input" type="file" multiple hidden
          accept=".png,.jpg,.jpeg,.gif,.webp,.bmp,.pdf,.csv,.html,.htm,.txt,.json,.yaml,.yml,.md,.zip">
        <button id="mic" class="link-button attach-button mic-button" type="button" hidden
          aria-label="語音輸入" aria-pressed="false"
          title="語音輸入：錄音後轉成文字放進輸入框，確認後再送出">🎤</button>
        <span id="mic-status" class="mic-status" role="status" hidden></span>
        <div class="model-control" id="model-control">
          <label class="visually-hidden" for="conversation-model">LLM model</label>
          <select id="conversation-model" aria-describedby="model-state" hidden></select>
          <span id="model-readonly" class="model-readonly">Reading models&hellip;</span>
          <span id="model-state" class="model-state" role="status"></span>
        </div>
        <button class="go send-button" id="send" type="submit" disabled>Send</button>
      </div>
      <p id="agent-mode-line" class="agent-mode-line" role="status" hidden>
        <span id="agent-mode-state"></span>
        <button id="agent-folders" class="link-button" type="button" hidden>Folders…</button>
      </p>
    </form>
    <p class="hint">This is the Agent on this computer &mdash; the same one the
      command line and Telegram reach, with the same permissions and the same
      refusals. Nothing is written unless the command says so. One request runs
      at a time.</p>
    <dialog id="agent-folders-dialog" aria-labelledby="agent-folders-title">
      <form class="dialog-body" id="agent-folders-form" method="dialog">
        <h2 id="agent-folders-title">This conversation's folders</h2>
        <p class="note">The agent reads and writes its working folder freely. It may also
          read the folders below freely; anything else asks you first.</p>
        <label for="agent-folder">Working folder (empty: the default for this
          conversation)</label>
        <input id="agent-folder" autocomplete="off">
        <label for="agent-read-folders">Read-only folders (one full path per line)</label>
        <textarea id="agent-read-folders" rows="4" autocomplete="off"></textarea>
        <p id="agent-folders-result" class="note" role="status"></p>
        <div class="dialog-actions">
          <button id="agent-folders-cancel" type="button">Cancel</button>
          <button class="go" id="agent-folders-save" type="submit">Save</button>
        </div>
      </form>
    </dialog>
    <dialog id="backend-auth-dialog" aria-labelledby="backend-auth-title">
      <div class="dialog-body">
        <h2 id="backend-auth-title">Connect conversation backend</h2>
        <p id="backend-auth-detail"></p>
        <p id="backend-auth-result" class="note" role="status"></p>
        <div class="dialog-actions">
          <button id="backend-auth-cancel" type="button">Cancel</button>
          <button id="backend-auth-check" type="button">Check again</button>
          <button class="go" id="backend-auth-start" type="button">Authenticate</button>
        </div>
      </div>
    </dialog>
    <dialog id="backend-public-dialog" aria-labelledby="backend-public-title">
      <div class="dialog-body">
        <h2 id="backend-public-title">Start a PUBLIC conversation</h2>
        <p>Only send information you are allowed to share with this external
          backend. Existing conversation history stays here; a new session is
          created if this one already has messages. Commands and local tools
          are unavailable in a PUBLIC conversation.</p>
        <p id="backend-public-result" class="note" role="status"></p>
        <div class="dialog-actions">
          <button id="backend-public-cancel" type="button">Cancel</button>
          <button class="go" id="backend-public-start" type="button">
            Start PUBLIC session</button>
        </div>
      </div>
    </dialog>
  </section>

  <section id="panel-settings">
    <h2>Agent identity and speaking style</h2>
    <p class="note">Name and introduction identify this local Agent. The bounded
      soul.md text guides speaking style on later natural-language turns; it cannot
      change policy, permissions, tools, approvals or factual evidence.</p>
    <div class="card settings">
      <form id="persona-settings">
        <div class="two">
          <div><label for="persona-name">Agent name</label>
            <input id="persona-name" maxlength="80" required></div>
          <div><label for="persona-introduction">Self-introduction</label>
            <input id="persona-introduction" maxlength="500" required></div>
        </div>
        <label for="persona-soul">soul.md</label>
        <textarea id="persona-soul" maxlength="12000"
          placeholder="Describe tone, vocabulary and interaction preferences."></textarea>
        <p><button class="go" id="persona-save" type="submit">Save Agent identity</button></p>
        <pre id="persona-result" class="note">Reading current identity&hellip;</pre>
      </form>
    </div>
    <h2>Avatar</h2>
    <p class="note">Your own picture at the top left; it moves while the Agent works.
      Each person who uses this Agent picks their own.</p>
    <div class="card settings">
      <div id="avatar-choices" class="avatar-choices" role="radiogroup"
           aria-label="Avatar"></div>
      <pre id="avatar-result" class="note"></pre>
    </div>
    <h2 id="gateway-heading">LLM gateway</h2>
    <p class="note">The gateway on this computer connects the Agent (and coding agents) to
      the company models. It listens on 127.0.0.1 only. The company token stays in your
      Windows profile and is never shown here; renewing it needs the company domain
      sign-in (in the office, or over VPN with a Kerberos ticket).</p>
    <div class="card settings" id="gateway-card">
      <p id="gateway-state" class="gateway-state" role="status" aria-live="polite">
        Reading the gateway&hellip;</p>
      <dl id="gateway-facts" class="gateway-facts"></dl>
      <p class="gateway-actions">
        <button class="go" id="gateway-start" type="button">Start</button>
        <button id="gateway-restart" type="button">Restart</button>
        <button id="gateway-refresh" type="button">Refresh token</button>
        <button id="gateway-test" type="button">Test</button></p>
      <label class="laya-check"><input type="checkbox" id="gateway-autostart"> Start the
        gateway when I sign in to Windows</label>
      <pre id="gateway-result" class="note"></pre>
    </div>
    <h2>Natural-language model</h2>
    <p class="note">Connect the Agent to the existing OpenAI-compatible Gateway.
      This page stores only connection metadata and optional secret/environment names.
      It never accepts or stores an access-token value.</p>
    <div class="card settings">
      <p id="model-gateway-link" class="note" hidden></p>
      <form id="model-settings">
        <div class="two">
          <div><label for="model-provider">Provider</label>
            <select id="model-provider"><option value="openai_compatible">
              OpenAI-compatible Gateway</option>
              <option value="ollama">Ollama on this computer</option></select></div>
          <div><label for="model-alias">Alias</label>
            <input id="model-alias" value="company" required></div>
        </div>
        <label for="model-base-url">Gateway URL</label>
        <input id="model-base-url" required>
        <label for="model-choices">Models this Gateway serves</label>
        <div class="two">
          <div><select id="model-choices" aria-describedby="model-choices-state">
            <option value="">Load the list from the saved Gateway&hellip;</option></select></div>
          <div><button id="model-choices-load" type="button">Reload available models</button></div>
        </div>
        <p id="model-choices-state" class="note" role="status"></p>
        <label for="model-name">Model name served by the Gateway</label>
        <input id="model-name" placeholder="Choose above, or type the exact name" required>
        <p class="note" id="model-default-note">This is the default model. In a chat, the
          model menu under the message box can choose another model this Gateway serves for
          that conversation, from the next message and without a restart.</p>
        <label for="model-context-capacity">Declared model context capacity (tokens)</label>
        <input id="model-context-capacity" type="number" min="1" max="10000000" required>
        <p class="note">This value describes the model endpoint for routing. It does not
          increase the context sent by chat; use the conversation limits below for that.</p>
        <div class="two">
          <div><label for="model-secret">SecretRef name (optional)</label>
            <input id="model-secret" placeholder="llm_gateway_token"></div>
          <div><label for="model-environment">Environment variable name (optional)</label>
            <input id="model-environment" placeholder="AEP_LLM_TOKEN"></div>
        </div>
        <p class="note">If the Gateway requires a token, set the token value in the named
          Windows environment variable before restarting the Agent. An administrator
          must separately approve the exact Gateway URL and permitted data classes
          in host.json. Changing the URL, provider or credential clears that approval.</p>
        <p id="model-data-approval" class="note" role="status"></p>
        <p><button class="go" id="model-save" type="submit">Save model settings</button></p>
        <pre id="model-result" class="note">Reading current settings&hellip;</pre>
      </form>
    </div>
    <h2>Conversation context and saved sessions</h2>
    <p class="note">These limits control how much recent chat text is sent on the next
      ordinary conversation turn. They are separate from the model's declared
      context window. Knowledge questions retrieve evidence independently.</p>
    <div class="card settings">
      <form id="context-settings">
        <div class="two">
          <div><label for="context-messages">Recent messages, including the new question</label>
            <input id="context-messages" type="number" min="1" max="40" required></div>
          <div><label for="context-budget">History text budget (UTF-8 bytes)</label>
            <input id="context-budget" type="number" min="4000" max="48000" required></div>
        </div>
        <div class="two">
          <div><label for="context-tool-calls">Tool calls per turn (1–150)</label>
            <input id="context-tool-calls" type="number" min="1" max="150" required></div>
          <div><label for="context-time-limit">Time limit per turn (minutes, 1–120)</label>
            <input id="context-time-limit" type="number" min="1" max="120" required></div>
        </div>
        <p class="note">How much work the Agent may do for one message before it stops and
          asks you to reply 繼續. It also stops early when it calls the same tool with the
          same input three times in a row and it fails, or more than five times with nothing
          new in between. Lower these if a turn runs too long; the work done so far is kept.</p>
        <p class="note">UTF-8 bytes conservatively bound history text. System guidance,
          tool definitions and tool results use additional context. A question that
          exceeds this budget is returned for editing, never silently shortened.</p>
        <p><button class="go" id="context-save" type="submit">Save context limits</button></p>
        <p id="context-result" class="note" role="status"></p>
      </form>
      <hr>
      <p id="memory-state" class="note"></p>
      <label for="session-manage-target">Saved session</label>
      <select id="session-manage-target"></select>
      <p><button id="session-delete" type="button">Delete selected session</button></p>
      <p id="session-manage-result" class="note" role="status"></p>
    </div>
    <h2 id="multi-agent-heading">多 Agent 委派</h2>
    <p class="note multi-agent-docs">開啟後，Agent 可以在一個回合裡把範圍明確的小工作
      交給專家子代理（最多 3 個、不能再往下委派，寫入動作一樣要你確認）。
      預設關閉；儲存後要重新啟動 Agent Web 才生效。
      說明：安裝包的使用手冊 <code>USER_GUIDE.zh-TW.md</code> 第 4.11、4.12 節；
      契約：<code>docs/CONTRACTS.md</code>「Multi-agent delegation (V1)」。</p>
    <div class="card settings" id="multi-agent-card">
      <label class="multi-agent-switch"><input type="checkbox" id="multi-agent-enabled"
        role="switch" aria-describedby="multi-agent-result"> 允許委派給子代理</label>
      <p id="multi-agent-result" class="note" role="status" aria-live="polite">讀取中…</p>
    </div>
    <h2>Telegram bot</h2>
    <p class="note">Let people you list here talk to this Agent through a Telegram bot.
      The access token is stored only in this Windows user's environment variables, never in a
      file, and is never shown again; leave it empty to keep the saved one. Saving applies
      at once.</p>
    <div class="card settings">
      <form id="telegram-settings" autocomplete="off">
        <label><input type="checkbox" id="telegram-enabled"> Answer Telegram messages</label>
        <label for="telegram-token">Bot access token (from @BotFather)</label>
        <input id="telegram-token" type="password" autocomplete="new-password"
               spellcheck="false" placeholder="123456789:AA…">
        <label for="telegram-senders">Allowed senders, one per line: numeric Telegram user
          id, optionally followed by an actor. Don't know yours? Save the token, send the bot
          any message, then press “Check who messaged the bot” and Allow.</label>
        <textarea id="telegram-senders" spellcheck="false"
                  placeholder="123456789 leo.chi"></textarea>
        <p><button class="go" id="telegram-save" type="submit">Save Telegram settings</button>
          <button id="telegram-check" type="button">Check who messaged the bot</button></p>
        <p id="telegram-result" class="note" role="status"></p>
        <div id="telegram-unknown"></div>
      </form>
    </div>
    <h2>Shared platform</h2>
    <p class="note">The company's shared platform: Skills and Workflows your team published,
      and where you publish yours. The Member Portal is the Marketplace in your browser;
      "Open Marketplace" uses this address. Platform sync URL (Bridge API): This PC's
      Bridge connects here to enroll and to download what your team published; everything
      still runs on this PC. Paste the Personal Agent code from the Member Portal
      ("Connect a Personal Agent") once, then press "Enroll this PC". Codes and tokens are
      kept only in this Windows user's environment and never shown again.</p>
    <div class="card settings" id="shared-platform-card">
      <form id="shared-platform-settings" autocomplete="off">
        <div class="laya-grid">
          <label>Member Portal URL <input id="shared-portal-url"></label>
          <label>Platform sync URL (Bridge API) <input id="shared-bridge-url"></label>
          <label>Personal Agent code <input id="shared-code" type="password"
                 autocomplete="off" placeholder="paste once; it is not shown again"></label>
        </div>
        <p class="note" id="shared-this-pc"></p>
        <fieldset class="shared-cert" id="shared-signin">
          <legend>Personal Agent code</legend>
          <p class="note" id="shared-code-state" role="status"></p>
          <p class="note">Instead of copying the code from the Member Portal, sign in here with
            your platform account and password: this PC gets its own code and renews it before
            it expires. The password is used once for this sign-in and is not kept.</p>
          <div class="laya-grid">
            <label>Platform account <input id="shared-signin-account"
                   autocomplete="username"></label>
            <label>Password <input id="shared-signin-password" type="password"
                   autocomplete="current-password"></label>
          </div>
          <p><button id="shared-signin-go" type="button">Sign in to get a code</button></p>
          <p class="note" id="shared-token-note"></p>
        </fieldset>
        <fieldset class="shared-cert" id="shared-cert">
          <legend>Platform certificate</legend>
          <p class="note">A platform on the company network with its own (self-signed)
            certificate: press "Fetch &amp; show fingerprint", compare the SHA-256 with the
            one your administrator gave you, and only if they are the same press "Trust this
            certificate". This PC then accepts that certificate and no other.</p>
          <p class="note" id="shared-cert-pinned"></p>
          <output id="shared-cert-fingerprint" class="mono"></output>
          <p><button id="shared-cert-fetch" type="button">Fetch &amp; show fingerprint</button>
            <button id="shared-cert-trust" type="button" disabled>Trust this certificate</button>
            <button id="shared-cert-download" type="button" disabled>Download .cer</button>
            <button id="shared-cert-forget" type="button">Forget</button></p>
        </fieldset>
        <p><button class="go" id="shared-save" type="submit">Save</button>
          <button id="shared-enroll" type="button">Enroll this PC</button></p>
        <p id="shared-status" class="note" role="status" aria-live="polite"></p>
      </form>
    </div>
    <div class="card settings" id="team-card">
      <form id="team-settings" autocomplete="off">
        <label for="team-declared">Teams I belong to on this PC</label>
        <input id="team-declared" placeholder="for example: engineering, qa"
          aria-describedby="team-unused">
        <p id="team-unused" class="note" hidden>Not used: this PC is connected to the shared
          platform, and the platform decides your teams.</p>
        <p class="note">Lets you revise a Workflow your team owns under its own name
          (1.0.0 → 1.0.1) instead of a copy named after you. When this PC is connected to
          the shared platform, the teams come from the platform and this list is not used.
          It only affects drafts on this PC: publishing is still checked by the platform.</p>
        <p><button class="go" id="team-save" type="submit">Save teams</button></p>
        <p id="team-status" class="note" role="status" aria-live="polite"></p>
      </form>
    </div>
    <h2>Laya decision acceleration</h2>
    <p class="note">Laya answers small routing decisions fast. The Agent reaches it only
      through an SSH tunnel to a port on this computer, so nothing travels unencrypted to
      the other machine. Shadow asks Laya in the background and only records its choice;
      active lets confident choices narrow the Skills the model sees. A mode change applies
      after Agent Web restarts; the tunnel follows at once.</p>
    <div class="card settings">
      <form id="laya-settings" autocomplete="off">
        <div class="laya-grid">
          <label>Remote host <input id="laya-host" placeholder="172.25.228.141"></label>
          <label>SSH port <input id="laya-ssh-port" type="number" min="1" max="65535"></label>
          <label>Account <input id="laya-user" placeholder="openlab"></label>
          <label>Remote port (Laya) <input id="laya-remote-port" type="number" min="1"
                 max="65535"></label>
          <label>Local port <input id="laya-local-port" type="number" min="1024"
                 max="65535"></label>
          <label>Mode <select id="laya-mode">
            <option value="off">Off</option><option value="shadow">Shadow (record only)</option>
            <option value="active">Active</option></select></label>
          <label>Confidence threshold (%) <input id="laya-threshold" type="number" min="0"
                 max="100" step="1"></label>
          <label>Timeout (ms) <input id="laya-timeout" type="number" min="100" max="5000"
                 step="100"></label>
          <label>Owner approval reference <input id="laya-approval"
                 placeholder="needed for shadow or active"></label>
        </div>
        <label class="laya-check"><input type="checkbox" id="laya-auto"> Agent Web opens the
          SSH tunnel and
          reopens it when it drops (the SSH key must be accepted by the remote host)</label>
        <p><button class="go" id="laya-save" type="submit">Save Laya settings</button>
          <button id="laya-check" type="button">Check connection</button></p>
        <p id="laya-status" class="note" role="status"></p>
      </form>
    </div>
    <div class="card settings" id="mcp-card" style="margin-top: 14px">
      <h2>MCP servers</h2>
      <p class="note">Add a Model Context Protocol server to give this Agent more tools: a local
        command (stdio) or a remote URL (Streamable HTTP). Adding a server approves all of its
        tools; the Agent can use them in conversations and coding, and a Workflow can use them
        as steps. Secrets are kept only in this Windows user's environment and never shown.</p>
      <div id="mcp-list" class="empty">reading&hellip;</div>
      <details id="mcp-editor">
        <summary><strong>Add or edit a server</strong></summary>
        <form id="mcp-form">
          <div class="two">
            <div><label for="mcp-name">Name (lowercase, e.g. github)</label>
              <input id="mcp-name" required pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="32"></div>
            <div><label for="mcp-transport">Connection</label>
              <select id="mcp-transport"><option value="stdio">Local command (stdio)</option>
                <option value="http">Remote URL (HTTP)</option></select></div>
          </div>
          <div id="mcp-stdio">
            <label for="mcp-command">Command</label>
            <input id="mcp-command" placeholder="npx">
            <label for="mcp-args">Arguments (one per line)</label>
            <textarea id="mcp-args" rows="3"
              placeholder="-y&#10;@modelcontextprotocol/server-filesystem"></textarea>
            <label for="mcp-cwd">Working folder (optional)</label>
            <input id="mcp-cwd">
            <label for="mcp-env">Environment, not secret (NAME=value per line)</label>
            <textarea id="mcp-env" rows="2"></textarea>
            <label for="mcp-secret-env">Secret environment (NAME=value per line; an empty value
              keeps the stored one)</label>
            <textarea id="mcp-secret-env" rows="2" autocomplete="off"></textarea>
          </div>
          <div id="mcp-http" hidden>
            <label for="mcp-url">URL (starting with https or http)</label>
            <input id="mcp-url" placeholder="mcp.example.com/mcp">
            <label for="mcp-headers">Headers, not secret (Name: value per line)</label>
            <textarea id="mcp-headers" rows="2"></textarea>
            <label for="mcp-token">Bearer token (empty keeps the stored one)</label>
            <input id="mcp-token" type="password" autocomplete="new-password">
          </div>
          <div class="two">
            <div><label for="mcp-timeout">Timeout per call (seconds)</label>
              <input id="mcp-timeout" type="number" min="1" max="900" value="60"></div>
            <div><label><input id="mcp-enabled" type="checkbox" checked> Enabled</label></div>
          </div>
          <p><button class="go" id="mcp-save" type="submit">Save and connect</button></p>
          <p id="mcp-result" class="note" role="status"></p>
        </form>
      </details>
    </div>
    <div class="card settings" id="coding-agents-card" style="margin-top: 14px">
      <h2>Coding agents</h2>
      <p class="note">Claude Code, Codex and GitHub Copilot on this computer get AEP's skills
        (build AEP Workflows and Skills, use AEP Knowledge) and two MCP servers in their own
        user settings: <code>aep</code> (authoring) and <code>aep-assistant</code> (Knowledge
        and Workflows, through this Agent Web). Only AEP's entries are changed; a file is backed
        up before it is edited.</p>
      <div id="coding-agents" class="empty">reading&hellip;</div>
      <p id="coding-agents-result" class="note" role="status"
        style="white-space: pre-wrap; overflow-wrap: anywhere"></p>
    </div>
    <div class="card settings" id="agent-mode-card" style="margin-top: 14px">
      <h2>Agent mode</h2>
      <p class="note">When a conversation uses Claude Code or GitHub Copilot, the agent can
        work in that conversation's own folder with AEP's skills and tools. Inside the folder
        it works freely; reading elsewhere, changing files outside it, every command and
        sending each email ask you with a card in the chat (no answer in 10 minutes means
        Deny). Credentials and protected system settings are never touched, and installing,
        approving or publishing stays with you. Off until you turn a backend on. In Telegram
        these backends stay text-only.</p>
      <form id="agent-mode-form" autocomplete="off">
        <div id="agent-mode-backends" class="empty">reading&hellip;</div>
        <label for="agent-mode-root">Default folder for conversations</label>
        <input id="agent-mode-root">
        <p id="agent-mode-root-note" class="note"></p>
        <h3>Email the agent may read</h3>
        <label for="agent-mail-folders">Folders (one per line, for example Inbox or
          Inbox/Projects)</label>
        <textarea id="agent-mail-folders" rows="2"></textarea>
        <label for="agent-mail-days">Days back, at most</label>
        <input id="agent-mail-days" type="number" min="1" max="365">
        <label for="agent-mail-senders">Never read mail from (an address or @domain per
          line)</label>
        <textarea id="agent-mail-senders" rows="2"></textarea>
        <label for="agent-mail-excluded">Never read these folders (one per line)</label>
        <textarea id="agent-mail-excluded" rows="2"></textarea>
        <p><button class="go" id="agent-mode-save" type="submit">Save agent mode</button></p>
        <p id="agent-mode-result" class="note" role="status"></p>
      </form>
    </div>
    <div class="card settings" style="margin-top: 14px">
      <h2>Agent profile</h2>
      <p class="note">Profiles narrow the Agent's Skills, Knowledge, capabilities and
        model requirements. Restart after activation.</p>
      <div id="profiles" class="empty">reading&hellip;</div>
    </div>
    <h2>Capability management</h2>
    <div class="grid">
      <div class="status-card"><strong>Skills, Workflows and Knowledge</strong>
        Select versions in Shared Marketplace, then return here and synchronize them.</div>
      <div class="status-card"><strong>Bridge Extensions</strong>
        Staging and activation remain protected by device-owner approval and technical policy.</div>
      <div class="status-card"><strong>Applications</strong>
        Applications keep their own process and update lifecycle and are listed
        separately in Marketplace.</div>
    </div>
  </section>

  <section id="panel-installed">
    <div class="workspace-head">
      <div><h2>Installed on this Agent</h2>
        <p class="note">Inspect what this computer can use and run only supported actions.</p></div>
      <div class="inline-actions">
        <button class="go" id="cap-refresh" type="button">Refresh status</button>
      </div>
    </div>
    <div class="card" id="external-card">
      <h3>外部 Agent 提交，等待你核准</h3>
      <p class="note">Claude Code、Codex 或 Copilot 送來的 Skill 與 Workflow。核准前請看完整內容；
        Skill 會在主機重新啟動後生效。</p>
      <div id="external-approvals" class="empty">reading&hellip;</div>
    </div>
    <div class="cap-tabs" role="tablist" aria-label="Installed capability types">
      <button id="cap-tab-skills" role="tab" aria-selected="true" data-kind="skills">
        Skills<span class="cap-count" id="count-skills">0</span></button>
      <button id="cap-tab-workflows" role="tab" aria-selected="false" data-kind="workflows">
        Workflows<span class="cap-count" id="count-workflows">0</span></button>
      <button id="cap-tab-knowledge" role="tab" aria-selected="false" data-kind="knowledge">
        Knowledge<span class="cap-count" id="count-knowledge">0</span></button>
      <button id="cap-tab-extensions" role="tab" aria-selected="false" data-kind="extensions">
        Extensions<span class="cap-count" id="count-extensions">0</span></button>
      <button id="cap-tab-applications" role="tab" aria-selected="false"
              data-kind="applications">
        Apps<span class="cap-count" id="count-applications">0</span></button>
    </div>
    <div id="capability-notice" class="section-status cap-notice" role="status"
         aria-live="polite"></div>
    <div class="cap-layout">
      <div class="cap-browser">
        <div class="cap-search"><label for="capability-search">Search this Agent's
          capabilities</label>
          <input id="capability-search" type="search"
                 placeholder="Name, namespace or description">
          <div id="cap-filters" class="cap-filters" role="group" aria-label="Show">
            <button type="button" class="chip" id="cap-filter-all" data-filter="all"
                    aria-pressed="true">All<span class="cap-count"
                    id="cap-filter-count-all">0</span></button>
            <button type="button" class="chip" id="cap-filter-installed" data-filter="installed"
                    aria-pressed="false">Installed<span class="cap-count"
                    id="cap-filter-count-installed">0</span></button>
            <button type="button" class="chip" id="cap-filter-drafts" data-filter="drafts"
                    aria-pressed="false">Drafts<span class="cap-count"
                    id="cap-filter-count-drafts">0</span></button>
            <button type="button" class="chip" id="cap-filter-disabled" data-filter="disabled"
                    aria-pressed="false">Switched off<span class="cap-count"
                    id="cap-filter-count-disabled">0</span></button>
          </div></div>
        <div id="capability-list" class="cap-list" role="list"
             aria-label="Capabilities on this Agent"></div>
      </div>
      <article id="capability-detail" class="cap-detail" aria-live="polite">
        <div id="capability-detail-content" class="empty">
          Reading installed capabilities&hellip;</div>
        <details id="workflow-settings" class="action-box" hidden>
          <summary><strong>Settings on this computer</strong></summary>
          <p class="note">Where this Workflow finds its reference data on this computer.
            Set once, kept across upgrades, and never asked when the Workflow runs. A
            Workflow with a missing required setting does not start. Credentials are never
            entered here.</p>
          <div id="workflow-settings-list"></div>
        </details>
        <div id="workflow-action" class="action-box" hidden>
          <strong>Run this Workflow</strong>
          <p class="note" id="workflow-contract">No installed Workflow.</p>
          <div id="workflow-fields" hidden></div>
          <div id="workflow-legacy">
            <label for="workflow-arguments">JSON arguments</label>
            <textarea id="workflow-arguments" spellcheck="false">{}</textarea>
          </div>
          <p><button class="go" id="workflow-run" type="button" disabled>Run Workflow</button></p>
          <pre id="workflow-result" class="section-status">Nothing has run.</pre>
        </div>
        <div id="knowledge-action" class="action-box" hidden>
          <strong>Ask this Knowledge source</strong>
          <p class="note" id="knowledge-domain">No installed Knowledge.</p>
          <label for="knowledge-skill">Knowledge Asking Skill</label>
          <select id="knowledge-skill"><option value="">Existing query path</option></select>
          <label for="knowledge-question">Question</label>
          <textarea id="knowledge-question" spellcheck="true"></textarea>
          <p><button class="go" id="knowledge-ask" type="button" disabled>Ask Knowledge</button></p>
          <pre id="knowledge-result" class="section-status">Nothing has been asked.</pre>
          <div id="knowledge-citations" class="empty">No citations.</div>
        </div>
      </article>
    </div>
    <dialog id="asset-confirm" aria-labelledby="asset-confirm-title"
            aria-describedby="asset-confirm-detail">
      <form method="dialog" class="dialog-body">
        <h2 id="asset-confirm-title">Remove?</h2>
        <p id="asset-confirm-detail"></p>
        <div class="dialog-actions">
          <button class="btn" id="asset-confirm-cancel" value="cancel" autofocus>Cancel</button>
          <button class="btn danger" id="asset-confirm-go" value="confirm">Remove</button>
        </div>
      </form>
    </dialog>
    <div hidden aria-hidden="true">
      <select id="workflow-target" disabled></select>
      <select id="knowledge-target" disabled></select>
    </div>
    <div class="market">
      <div class="workspace-head">
        <div><h2>Share Platform Library</h2>
          <p class="note" id="platform-note">reading&hellip;</p></div>
      </div>
      <div class="market-tabs" role="tablist" aria-label="Shared asset types">
        <button id="market-tab-skill" role="tab" aria-selected="true" data-kind="skill">
          Skills<span class="cap-count" id="market-count-skill">0</span></button>
        <button id="market-tab-workflow" role="tab" aria-selected="false" data-kind="workflow">
          Workflows<span class="cap-count" id="market-count-workflow">0</span></button>
        <button id="market-tab-bridge-extension" role="tab" aria-selected="false"
                data-kind="bridge_extension">
          Extensions<span class="cap-count" id="market-count-bridge-extension">0</span></button>
        <button id="market-tab-application" role="tab" aria-selected="false"
                data-kind="application">
          Apps<span class="cap-count" id="market-count-application">0</span></button>
      </div>
      <div class="market-tools">
        <input id="market-search" type="search" aria-label="Search shared platform"
               placeholder="Search shared capabilities">
        <select id="market-category" aria-label="Filter by category">
          <option value="all">All categories</option></select>
        <select id="market-status" aria-label="Filter by status">
          <option value="all">All statuses</option><option value="installed">Installed</option>
          <option value="authorized">Selected</option><option value="available">Available</option>
        </select>
        <a id="member-portal" hidden target="_blank" rel="noopener noreferrer"
           aria-label="Open shared marketplace (Agent Add-ons and Applications)">
          Open Marketplace</a>
        <button class="btn" id="platform-sync" type="button" disabled
                title="Install what you selected elsewhere, such as in the Member Portal">
          Sync again</button>
      </div>
      <div id="platform-sync-result" class="section-status" role="status" aria-live="polite">
        &ldquo;+ Add to this Agent&rdquo; installs at once. &ldquo;Sync again&rdquo; is only for
        selections made in the Member Portal.</div>
      <p class="note">Press a card for its details. &ldquo;+ Add to this Agent&rdquo; selects
        that version for this PC as you on the shared platform and installs it here.</p>
      <div id="catalog" class="market-grid">
        <div class="empty">reading&hellip;</div></div>
      <details style="margin-top: 14px"><summary>Selections authorized on this Bridge</summary>
        <p class="note">A synchronized selection does not bypass capability policy.</p>
        <div class="card"><div id="decisions" class="empty">reading&hellip;</div></div>
      </details>
    </div>
    <div id="publish-card" class="card settings" style="margin-top: 14px">
      <h3>Publish to the shared platform</h3>
      <p class="note">Send an installed Skill or Workflow to the shared platform as you. It
        waits there until an administrator (not you) approves it; only then can others
        choose it. The platform gives it the next version number.</p>
      <div id="publish-off" class="empty" hidden>Publishing is not set up on this PC: set
        the Member Portal URL and your Personal Agent code in Settings &gt; Shared
        platform.</div>
      <div id="publish-form" class="laya-grid" hidden>
        <label>Skill or Workflow<select id="publish-asset"></select></label>
        <label>Change<select id="publish-change">
          <option value="patch">patch: a fix</option>
          <option value="minor" selected>minor: something added</option>
          <option value="major">major: changes how it is used</option></select></label>
        <label>Who can use it<select id="publish-visibility">
          <option value="" selected>As the Skill or Workflow says</option>
          <option value="team">Only my team</option>
          <option value="organization">Everyone in the organization</option></select></label>
        <label>Note for the reviewer<input id="publish-note" maxlength="300"
          placeholder="what changed and why"></label>
        <p id="publish-audience" class="note"></p>
        <div><button class="go" id="publish-go" type="button">Publish for review</button></div>
      </div>
      <div id="publish-status" class="section-status" role="status" aria-live="polite"></div>
      <div id="publish-list"></div>
    </div>
    <details id="recent-runs" class="card settings" style="margin-top: 14px">
      <summary><strong>Recent runs</strong></summary>
      <div id="runs" class="empty">reading&hellip;</div>
    </details>
  </section>

  <section id="panel-knowledge">
    <div class="workspace-head">
      <div><h2>Knowledge</h2>
        <p class="note">Improve one folder of a shared knowledge vault in three steps, inside
          your own sandbox. Nothing reaches the vault until you push.</p></div>
      <button id="kp-refresh" type="button">Refresh</button>
    </div>
    <div class="mem-tabs kn-tabs" id="kn-tabs" role="tablist" aria-label="Knowledge">
      <button type="button" role="tab" data-kn="pipeline" aria-selected="true"
        lang="zh-Hant">知識庫維護</button>
      <button type="button" role="tab" data-kn="bi" aria-selected="false"
        lang="zh-Hant">BI 卡片</button>
    </div>
    <div id="kn-pane-pipeline" role="tabpanel" aria-label="知識庫維護">
    <div id="kp-disabled" class="empty" hidden>The Knowledge pipeline is not configured on
      this machine (host.json <code>knowledge_pipeline</code>).</div>
    <div class="kp-top">
      <nav id="kp-stepper" class="kp-stepper" aria-label="Maintenance steps">
        <ol>
          <li><button type="button" data-stage="pull"><span class="kp-step-n">1</span>
            <span><strong>Pull data</strong><small>pull, add files, convert</small></span>
          </button></li>
          <li><button type="button" data-stage="ingest"><span class="kp-step-n">2</span>
            <span><strong>Ingest data</strong><small>edit skills, ingest</small></span>
          </button></li>
          <li><button type="button" data-stage="test"><span class="kp-step-n">3</span>
            <span><strong>Testing data</strong><small>questions, test, push</small></span>
          </button></li>
        </ol>
      </nav>
      <div id="kp-status" class="section-status" role="status" aria-live="polite"><span
        id="kp-status-text"></span> <span id="kp-status-time" class="note"></span></div>
      <div id="kp-progress" class="kp-progress" hidden>
        <progress id="kp-progress-bar" max="1"></progress>
        <span id="kp-progress-text" class="note"></span></div>
    </div>
    <div id="kp-main">
      <div id="kp-start">
        <h2 class="kp-stage-title" tabindex="-1">Step 1 of 3 &middot; Pull data</h2>
        <p class="note">Continue a sandbox, or start one for the folder you maintain.</p>
        <div class="kp-grid2">
          <div class="card"><h3>Continue a sandbox</h3>
            <div id="kp-sandboxes" class="kp-list">reading&hellip;</div></div>
          <form id="kp-new" class="card kp-form"><h3>Start a new sandbox</h3>
            <label for="kp-base">Project vault</label>
            <select id="kp-base"></select>
            <label for="kp-scope">Folder you maintain</label>
            <select id="kp-scope" required></select>
            <label for="kp-label">Sandbox name</label>
            <input id="kp-label" required maxlength="80" placeholder="e.g. VNA trial">
            <p class="note">The vault is copied into your sandbox and the folder's originals are
              pulled, so you can convert them next.</p>
            <button class="go" type="submit">Create sandbox and pull</button>
          </form>
        </div>
        <div class="card kp-repos" lang="zh-Hant"><h3>知識庫（有版本紀錄）</h3>
          <p class="note">每個改動都寫目的並 commit，push 給大家，發佈後 Agent
            才讀到；歷史裡可以改回任何版本。之後 sandbox 會被知識庫取代。</p>
          <div id="kp-repos" class="kp-list">reading&hellip;</div>
          <div id="kp-askable" aria-live="polite"></div>
          <details class="kp-repo-new"><summary>新增知識庫</summary>
            <form id="kp-repo-form" class="kp-form">
              <label for="kp-repo-mode">方式</label>
              <select id="kp-repo-mode">
                <option value="import">匯入既有 wiki 資料夾的副本</option>
                <option value="create">建立空的知識庫</option>
                <option value="join">加入別人分享的知識庫資料夾</option>
              </select>
              <div id="kp-repo-source-box">
                <label for="kp-repo-source">要匯入的 wiki 資料夾（只會讀，不會改）</label>
                <input id="kp-repo-source" maxlength="400"
                  placeholder="例如 C:\Users\me\Documents\my-wiki">
              </div>
              <label for="kp-repo-path" id="kp-repo-path-l">
                放知識庫的資料夾（例如 OneDrive 上的共用資料夾）</label>
              <input id="kp-repo-path" required maxlength="400">
              <div id="kp-repo-title-box">
                <label for="kp-repo-title">名稱</label>
                <input id="kp-repo-title" maxlength="80" placeholder="例如 RS 產品知識">
              </div>
              <button class="go" type="submit">新增</button>
            </form>
          </details>
        </div>
      </div>
      <div id="kp-box" hidden>
        <div class="kp-sandbox-bar">
          <div><strong id="kp-title"></strong>
            <span class="note">&middot; folder <span id="kp-scope-name"></span></span></div>
          <div class="kp-actions">
            <button id="kp-switch" type="button">Switch sandbox</button>
            <button id="kp-discard" type="button">Discard sandbox</button></div>
        </div>
        <div class="kp-banner" id="kp-review" hidden></div>
        <section class="kp-stage" data-stage="pull" aria-labelledby="kp-stage-pull">
          <h2 class="kp-stage-title" id="kp-stage-pull" tabindex="-1">Step 1 of 3 &middot; Pull
            data</h2>
          <p class="note">Bring this folder's originals into the sandbox, add files from this
            computer if needed, then convert everything to Raw.</p>
          <div class="card" id="kp-repo-settings" lang="zh-Hant" hidden><h3>這台電腦的資料夾</h3>
            <p class="note">只存在這台電腦：「拉資料」從收件資料夾拉原始檔，
              測試題目放在題目資料夾。</p>
            <label for="kp-intake">收件資料夾</label>
            <input id="kp-intake" maxlength="400"
              placeholder="例如 OneDrive 上大家放原始檔的資料夾">
            <label for="kp-questions">題目資料夾</label>
            <input id="kp-questions" maxlength="400">
            <div class="kp-actions"><button id="kp-repo-save" type="button">儲存</button>
              <span class="note" id="kp-repo-saved" role="status"></span></div></div>
          <div class="card"><h3 id="kp-pull-h">From the project vault</h3>
            <p class="note" id="kp-pull-note">Originals not yet ingested are copied into the
              sandbox. Ingested ones are already here as Raw, so they are not pulled again.</p>
            <div id="kp-pull-folders" class="kp-list"></div>
            <div class="kp-actions"><button id="kp-pull" type="button">Pull</button>
              <span class="note" id="kp-pull-result"></span></div></div>
          <div class="card"><h3>From this computer</h3>
            <div class="kp-actions">
              <label for="kp-category">Folder</label>
              <select id="kp-category"></select>
              <input id="kp-files" type="file" multiple aria-label="Files to add">
              <button id="kp-upload" type="button">Add files</button>
            </div>
            <div id="kp-drop"></div></div>
          <div class="card"><h3>Convert</h3>
            <p class="note">Turns every original waiting in the sandbox into a Raw document.
              Pictures are described by the model, so a deck can take minutes; it runs in the
              background and you can keep working.</p>
          <div class="kp-actions">
            <button id="kp-preview" type="button">Preview convert</button>
            <button class="go" id="kp-convert" type="button">Convert</button>
            <button id="kp-convert-stop" type="button" hidden>Stop</button>
          </div>
          <p class="note">Convert asks the model to describe every picture, so a deck can take
            minutes. It runs in the background: you can keep working and come back.</p>
          <div id="kp-convert-progress" class="kp-progress" hidden>
            <progress id="kp-convert-bar" max="1"></progress>
            <span id="kp-convert-text" class="note"></span></div>
          <div id="kp-converted"></div>
          </div>
          <div class="kp-nav"><span></span>
            <button class="go" type="button" data-go="ingest">Next: Ingest data &rarr;</button>
          </div>
        </section>
        <section class="kp-stage" data-stage="ingest" aria-labelledby="kp-stage-ingest" hidden>
          <h2 class="kp-stage-title" id="kp-stage-ingest" tabindex="-1">Step 2 of 3 &middot;
            Ingest data</h2>
          <p class="note">Adjust how this folder's data becomes wiki pages, then ingest the Raw
            documents with those rules.</p>
          <div class="card"><h3>Skills for this folder</h3>
            <p class="note">Edit or add the skills of this folder; the AI session can help.
              The vault-wide CLAUDE.md and more general layers are read only here. Changes stay
              in the sandbox until you push.</p>
            <div id="kp-rules" class="kp-list"></div>
          <div id="kp-rule-editor" hidden>
            <p><strong id="kp-rule-path"></strong>
              <span class="note" id="kp-rule-dirty"></span></p>
            <div class="kp-tabs" role="tablist">
              <button type="button" role="tab" data-tab="preview">Preview</button>
              <button type="button" role="tab" data-tab="md" aria-selected="true">Markdown</button>
            </div>
            <div class="kp-panes" id="kp-panes">
              <section class="kp-pane" id="kp-pane-file">
                <div class="kp-pane-body kp-filebody">
                  <div id="kp-md-view" class="kp-md-view">
                    <div class="kp-block" id="kp-block-prev">
                      <button class="kp-block-head" type="button" data-block="kp-block-prev"
                              aria-expanded="true"><span class="kp-chev">&#x2304;</span>
                        Previous file <span class="note" id="kp-diff-summary"></span></button>
                      <div class="kp-block-body" id="kp-prev-body">
                        <div id="kp-prev" class="kp-diffrows"></div></div>
                    </div>
                    <div class="kp-block" id="kp-block-cur">
                      <button class="kp-block-head" type="button" data-block="kp-block-cur"
                              aria-expanded="true"><span class="kp-chev">&#x2304;</span>
                        Current file <span class="note">editable</span></button>
                      <div class="kp-block-body kp-cur" id="kp-cur-body">
                        <div class="kp-gutter" id="kp-cur-gutter" aria-hidden="true"></div>
                        <div class="kp-editwrap">
                          <div id="kp-after-backdrop" class="kp-code kp-backdrop"
                               aria-hidden="true"></div>
                          <textarea id="kp-rule-text" spellcheck="false" wrap="off"
                                    aria-label="Rule file text"></textarea>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div id="kp-after-preview" class="kp-markdown" hidden></div>
                </div>
                <button class="kp-max" type="button" data-pane="kp-pane-file"
                        title="Maximize" aria-label="Maximize the file">&#x2922;</button>
              </section>
              <div class="kp-split" data-left="kp-pane-file" data-right="kp-pane-ai"
                   role="separator" aria-orientation="vertical" title="Drag to resize"></div>
              <section class="kp-pane" id="kp-pane-ai">
                <header>AI session <span class="note">proposals go to Current file</span></header>
                <div class="kp-pane-body kp-ai">
                  <div id="kp-assist-log"></div>
                  <textarea id="kp-assist-input" rows="4"
                            placeholder="e.g. every market claim must carry a date"
                            aria-label="Message to the Skill assistant"></textarea>
                  <div class="kp-actions">
                    <button class="go" id="kp-assist-send" type="button">Send</button>
                    <button id="kp-assist-reset" type="button">New conversation</button>
                  </div>
                </div>
                <button class="kp-max" type="button" data-pane="kp-pane-ai"
                        title="Maximize" aria-label="Maximize AI session">&#x2922;</button>
              </section>
            </div>
            <div class="kp-actions">
              <button class="go" id="kp-rule-save" type="button">Save</button>
              <button id="kp-rule-revert" type="button">Revert to saved</button>
              <button id="kp-rule-close" type="button">Close</button>
            </div></div>
          </div>
        <div class="card" id="kp-viewer" hidden><h3 id="kp-viewer-title">Preview</h3>
          <div class="kp-actions"><button id="kp-viewer-close" type="button">Close</button></div>
          <div id="kp-viewer-body" class="kp-markdown"></div></div>
          <div class="card"><h3>Ingest</h3>
            <p class="note">Click a document to read it. Tick the ones to ingest; documents a
              convert just made are ticked and shown in green. Keys in the list: &uarr;&darr;
              move, Shift+&uarr;&darr; tick a range, Space ticks one.</p>
          <div class="kp-ingest">
            <section class="kp-ingest-main">
              <div class="kp-ingest-head"><strong id="kp-doc-title">Choose a Raw document on
                the right.</strong>
                <button class="go" id="kp-plan-one" type="button" hidden>Plan ingest</button>
                <button id="kp-doc-back" type="button" hidden>Back to the document</button></div>
              <div id="kp-plan"></div>
              <div id="kp-doc" class="kp-markdown kp-doc"></div>
            </section>
            <section class="kp-ingest-side">
              <div class="kp-actions">
                <label class="kp-check"><input type="checkbox" id="kp-raw-all"
                  aria-label="Tick or untick every listed document"> All</label>
                <select id="kp-raw-folder" aria-label="Raw folder to list"></select>
              </div>
              <div id="kp-raw" class="kp-filelist" tabindex="0" role="listbox"
                   aria-multiselectable="true" aria-label="Raw documents"></div>
              <p class="note" id="kp-raw-count"></p>
            </section>
          </div>
          <div class="kp-actions">
            <button class="go" id="kp-reingest" type="button">Ingest ticked</button>
            <button id="kp-reingest-stop" type="button" hidden>Stop</button></div>
          <div class="note" id="kp-reingest-state"></div>
          <div id="kp-reingest-result"></div>
          </div>
          <div class="kp-nav">
            <button type="button" data-go="pull">&larr; Back: Pull data</button>
            <button class="go" type="button" data-go="test">Next: Testing data &rarr;</button>
          </div>
        </section>
        <section class="kp-stage" data-stage="test" aria-labelledby="kp-stage-test" hidden>
          <h2 class="kp-stage-title" id="kp-stage-test" tabindex="-1">Step 3 of 3 &middot;
            Testing data</h2>
          <p class="note">Make sure the questions cover this folder, test the sandbox against
            the project vault, and push when the result is good.</p>
          <div class="card"><h3>Questions</h3>
            <p id="kp-q-coverage" class="kp-coverage" role="status"></p>
            <div class="kp-actions">
              <button class="go" id="kp-q-new" type="button">New question</button></div>
            <div id="kp-q-list"></div>
            <div id="kp-q-editor" class="kp-q-editor" hidden>
              <label for="kp-q-text"><strong id="kp-q-path"></strong></label>
              <textarea id="kp-q-text" rows="14" spellcheck="false"></textarea>
              <p class="note">The heading is the question. Under <code>必須提到:</code> list the
                terms a good answer must mention, under <code>不可以說:</code> what it must not
                say, one per line starting with <code>- </code>. A question without terms is
                not graded.</p>
              <div class="kp-actions">
                <button class="go" id="kp-q-save" type="button">Save question</button>
                <button id="kp-q-cancel" type="button">Close</button></div>
            </div>
          </div>
          <div class="card"><h3>Test</h3>
            <p class="note">Each ticked question set is asked against this sandbox and against
              the project vault, and graded by its terms.</p>
          <div id="kp-bench-sets" class="kp-list"></div>
          <div class="kp-actions">
            <button class="go" id="kp-bench" type="button">Run test</button>
            <span class="note" id="kp-bench-state"></span></div>
          <div id="kp-bench-result"></div>
          </div>
          <div class="card kp-ver" id="kp-ver" lang="zh-Hant" hidden><h3>版本</h3>
            <p class="note" id="kp-ver-reads"></p>
            <p class="note" id="kp-ver-state"></p>
            <h4>還沒給大家的改動</h4>
            <div id="kp-ver-pending"></div>
            <label for="kp-ver-purpose">
              這次改動的目的（commit 一定要寫，之後在歷史裡看得到）</label>
            <input id="kp-ver-purpose" maxlength="500" placeholder="例如：加入 Tester Y 的規格">
            <div class="kp-actions">
              <button class="go" id="kp-ver-commit" type="button">Commit</button>
              <button id="kp-ver-push" type="button">Push 給大家</button>
              <button id="kp-ver-discard" type="button">捨棄還沒 commit 的改動</button></div>
            <p class="note">Push 前可以先跑上面的「Run test」：跑過的內容如果有
              題目退步，push 會被擋下；沒跑過的照樣送出，但會註明沒有測試。</p>
            <div id="kp-ver-result" role="status" aria-live="polite"></div>
            <div id="kp-ver-conflicts" role="alert"></div>
            <h4>歷史與發佈</h4>
            <div id="kp-ver-history"></div>
          </div>
          <div class="card" id="kp-push-card"><h3>Push to the vault</h3>
            <p class="note">Check conflicts and choose a side for each. Push merges into the
              project vault as it is now, tests the merged result with the ticked sets, and
              writes only when no question regresses and the score is not lower.</p>
          <div class="kp-actions">
            <button id="kp-merge-preview" type="button">Check conflicts</button>
            <button class="go" id="kp-push" type="button">Push</button>
            <button id="kp-refresh-agent" type="button">Refresh the Agent's Knowledge</button>
            <span class="note" id="kp-push-state"></span></div>
          <div id="kp-merge-result"></div>
          <div id="kp-push-result"></div>
          </div>
          <details class="card kp-advanced"><summary>Advanced</summary>
            <h3>Lint</h3>
            <div class="kp-actions"><button id="kp-lint" type="button">Run lint</button></div>
            <div id="kp-lint-result"></div>
          <h3>Legacy Raw</h3>
          <div class="kp-actions"><button id="kp-adopt" type="button">Adopt legacy Raw</button>
            <span class="note" id="kp-adopt-result"></span></div>
          <div id="kp-candidate">
          <h3>Local candidate</h3>
          <p class="note">Merge into a local candidate and publish it as the Agent's version
            without pushing to the project vault.</p>
          <div class="kp-actions">
            <button id="kp-merge" type="button">Merge into a candidate</button>
            <button id="kp-publish" type="button" disabled>Publish candidate</button>
          </div></div>
          <h3>Layered index</h3>
          <p class="note">Bilingual summaries and category indexes for ingest planning on a
            large wiki; queries do not use them.</p>
          <div class="kp-actions">
            <button id="kp-enrich" type="button">Write bilingual summaries</button>
            <button id="kp-index" type="button">Build layered index</button>
          </div><div id="kp-index-result" class="note"></div></details>
          <div class="kp-nav">
            <button type="button" data-go="ingest">&larr; Back: Ingest data</button><span></span>
          </div>
        </section>
      </div>
    </div>
    </div>
    <div id="kn-pane-bi" class="bi-pane" lang="zh-Hant" role="tabpanel" aria-label="BI 卡片"
         hidden>
      <div class="card bi-bar">
        <div class="bi-bar-main">
          <div><label class="bi-label" for="bi-dataset">資料集</label>
            <select id="bi-dataset"><option value="demo">demo</option></select></div>
          <div id="bi-domain-box"><label class="bi-label" for="bi-domain">領域</label>
            <select id="bi-domain">
              <option value="robotics" selected>機器人 Robotics</option>
              <option value="wireless">無線通訊 Wireless</option>
              <option value="aidc">AIDC</option>
            </select></div>
          <div id="bi-sample-box"><label class="bi-check"><input type="checkbox" id="bi-sample">
            含 SAMPLE 示範卡</label></div>
          <div class="bi-counts" id="bi-counts" role="status" aria-live="polite">&hellip;</div>
        </div>
        <div class="bi-actions">
          <button class="bi-btn" id="bi-refresh" type="button">更新</button>
          <button class="bi-btn" id="bi-publish" type="button" aria-expanded="false"
            aria-controls="bi-publish-panel">發佈到 Shared Platform</button>
          <details class="bi-manage" id="bi-manage"><summary>資料集管理</summary>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-new" type="button" aria-expanded="false"
                aria-controls="bi-new-panel">新增資料集</button>
              <button class="bi-btn" id="bi-install" type="button" aria-expanded="false"
                aria-controls="bi-install-panel">安裝 schema</button>
              <button class="bi-btn" id="bi-demo" type="button">載入示範資料</button>
            </div>
          </details>
        </div>
        <p class="bi-meta bi-schema-note" id="bi-schema-note"></p>
        <div class="bi-empty-state" id="bi-empty-state" role="note" hidden>
          <p class="bi-meta">這台電腦還沒有 BI 資料集。載入示範資料來看看，
            或新增一個資料集，再到「建立與匯入」加入資料。</p>
          <div class="bi-actions">
            <button class="go" id="bi-empty-demo" type="button">載入示範資料</button>
            <button class="bi-btn" id="bi-empty-new" type="button">新增資料集</button>
          </div>
        </div>
        <p class="bi-pub-state" id="bi-pub-state" role="status" aria-live="polite"></p>
      </div>
      <div class="bi-ro" id="bi-ro" role="note" hidden>
        <strong id="bi-ro-title"></strong>
        <span class="bi-meta" id="bi-ro-note"></span>
      </div>
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
      <div class="mem-status" id="bi-status-bar" role="status" aria-live="polite" hidden></div>
      <div id="bi-notice" class="mem-notice" role="status" aria-live="polite"></div>
      <aside class="bi-hint" id="bi-hint" aria-label="對話中使用卡片">
        <span class="bi-hint-text"><strong>對話也會用這些卡片回答。</strong>
          在對話中問：「哪些測試方案對應 WiFi 7？」回答會以「[卡片 …]」標出引用的卡片。</span>
        <button class="bi-btn" id="bi-ask" type="button">到對話中問</button>
      </aside>
      <div class="mem-tabs" id="bi-views" role="tablist" aria-label="BI 卡片檢視">
        <button type="button" role="tab" data-bi-view="build"
          aria-selected="true">建立與匯入</button>
        <button type="button" role="tab" data-bi-view="dashboard"
          aria-selected="false">Dashboard</button>
        <button type="button" role="tab" data-bi-view="cards" aria-selected="false">卡片</button>
      </div>
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
          <p class="bi-meta">領域設定已退役：應用領域、技術領域與鏈別改由 schema 的允許值表達，
            別名與鏈別寫進卡片，判讀規則搬進 skills（知識庫）或擷取方法（只在這台電腦的資料集）。
            先預覽，確認後才寫入。</p>
          <div class="bi-actions">
            <button class="bi-btn" id="bi-dom-migrate" type="button">
              預覽：搬進 schema 與卡片</button>
          </div>
          <div id="bi-dom-plan" aria-live="polite"></div>
        </div>
        <div id="bi-dash-params" class="bi-actions" hidden></div>
        <div class="mem-status" id="bi-status-dash" role="status" aria-live="polite" hidden></div>
        <div id="bi-dash-summary" class="bi-summary"></div>
        <div id="bi-dash-sections"></div>
      </div>
      <div id="bi-view-cards" role="tabpanel" aria-label="卡片" hidden>
        <div class="bi-filters">
          <div><label class="bi-label" for="bi-type">類型</label>
            <select id="bi-type"><option value="">全部類型</option></select></div>
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
        <div class="bi-browse">
          <div>
            <div class="mem-status" id="bi-status-cards" role="status" aria-live="polite"
                 hidden></div>
            <p class="bi-meta" id="bi-card-count"></p>
            <ul id="bi-cards" class="bi-cards" aria-label="卡片清單"></ul>
          </div>
          <div class="bi-detail" id="bi-detail">
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
              <span><strong>資料輸入與轉檔</strong><small>知識庫、來源、轉成 Markdown</small></span>
              </button></li>
            <li><button type="button" data-stage="ingest"><span class="kp-step-n">2</span>
              <span><strong>Schema 與 Ingest</strong><small>判讀規則、試跑、審核、寫入</small>
              </span></button></li>
            <li><button type="button" data-stage="test"><span class="kp-step-n">3</span>
              <span><strong>測試與 Push</strong><small>測試、分析圖表、push</small></span>
              </button></li>
          </ol>
        </nav>
        <nav id="bi-substeps" class="kp-stepper bi-substeps" aria-label="步驟 2 的細項" hidden>
          <ol>
            <li><button type="button" data-stage="schema"><span class="kp-step-n">a</span>
              <span><strong>Schema 與判讀規則</strong></span></button></li>
            <li><button type="button" data-stage="method"><span class="kp-step-n">b</span>
              <span><strong>試跑</strong></span></button></li>
            <li><button type="button" data-stage="review"><span class="kp-step-n">c</span>
              <span><strong>逐卡審核</strong></span></button></li>
            <li><button type="button" data-stage="commit"><span class="kp-step-n">d</span>
              <span><strong>確認寫入</strong></span></button></li>
            <li><button type="button" data-stage="result"><span class="kp-step-n">e</span>
              <span><strong>結果</strong></span></button></li>
          </ol>
        </nav>
        </div>
        <div class="mem-status" id="bi-status-build" role="status" aria-live="polite" hidden></div>
        <section class="kp-stage card bi-step" data-stage="source" aria-labelledby="bi-b-source">
          <h3 class="kp-stage-title" id="bi-b-source" tabindex="-1">步驟 1／3・資料輸入與轉檔</h3>
          <div class="bi-ai" id="bi-b-vault" role="region" aria-labelledby="bi-b-vault-h">
            <h4 id="bi-b-vault-h">知識庫</h4>
            <p class="bi-meta">共用知識庫（vault）放在 SharePoint／OneDrive 同步的資料夾。
              你的改動先留在這台電腦，寫下目的 commit、再 push 才會給大家；Agent 只讀發佈的版本。
              一般資料集只在這台電腦。
              「把這個資料集轉成 vault」會把卡片寫成一個 commit，並把來源放進這個知識庫，
              等你 commit、push 後才進共用資料夾；原本的資料集不變。</p>
            <div class="bi-step-grid">
              <div><label class="bi-label" for="bi-b-ds">寫入哪個知識庫</label>
                <select id="bi-b-ds"></select></div>
            </div>
            <p class="bi-meta" id="bi-b-target"></p>
            <div id="bi-b-v-state" role="status" aria-live="polite"></div>
            <div id="bi-b-askable" aria-live="polite"></div>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-v-sync" type="button" hidden>立即同步</button>
              <button class="bi-btn" id="bi-b-v-new" type="button" data-mode="new"
                aria-expanded="false" aria-controls="bi-b-v-form">建立共用知識庫（vault）</button>
              <button class="bi-btn" id="bi-b-v-join" type="button" data-mode="join"
                aria-expanded="false" aria-controls="bi-b-v-form">加入既有的 vault</button>
              <button class="bi-btn" id="bi-b-v-convert" type="button" data-mode="convert"
                aria-expanded="false" aria-controls="bi-b-v-form">把這個資料集轉成 vault</button>
            </div>
            <form id="bi-b-v-form" class="bi-step" hidden novalidate>
              <h4 id="bi-b-v-form-h"></h4>
              <div class="bi-step-grid">
                <div data-for="new"><label class="bi-label" for="bi-b-v-title">知識庫名稱</label>
                  <input id="bi-b-v-title" class="bi-input" maxlength="120"
                    placeholder="例如：市場訊號與產品對應"></div>
                <div data-for="new convert"><label class="bi-label" for="bi-b-v-purpose">
                  目的（Agent 依這段話判斷什麼問題該查它）</label>
                  <input id="bi-b-v-purpose" class="bi-input" maxlength="1000"
                    placeholder="例如：看市場需求與訊號，對應我們的產品與業務策略"></div>
                <div data-for="new"><label class="bi-label" for="bi-b-v-schema">Schema</label>
                  <select id="bi-b-v-schema"></select></div>
                <div data-for="new convert join"><label class="bi-label" for="bi-b-v-path"
                  id="bi-b-v-path-label">資料夾</label>
                  <input id="bi-b-v-path" class="bi-input" maxlength="1000" spellcheck="false"
                    placeholder="C:\Users\你\OneDrive - 公司\…"></div>
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
          <div class="bi-step-grid">
            <div><label class="bi-label" for="bi-b-file">
              來源檔（CSV、TSV、Excel、PDF、Word、PowerPoint、Markdown、文字）</label>
              <input id="bi-b-file" type="file" multiple
                accept=".csv,.tsv,.xlsx,.xlsm,.pdf,.docx,.pptx,.md,.markdown,.txt,text/csv,text/markdown,text/plain"></div>
            <div><label class="bi-label" for="bi-b-class">機密等級</label>
              <select id="bi-b-class">
                <option value="INTERNAL">INTERNAL（預設）</option>
                <option value="UNCLASSIFIED">UNCLASSIFIED</option>
                <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                <option value="RESTRICTED">RESTRICTED</option></select></div>
            <div id="bi-b-src-folder-box" hidden><label class="bi-label" for="bi-b-src-folder">
              放在知識庫的哪個資料夾（決定用哪條判讀規則）</label>
              <select id="bi-b-src-folder"></select></div>
            <div><button class="go" id="bi-b-upload" type="button" disabled>加入來源</button></div>
          </div>
          <p class="bi-meta" id="bi-b-src-shared" hidden>共用知識庫的來源原檔，commit、push
            後會放進共用資料夾。</p>
          <p class="bi-warn" id="bi-b-src-cloud" role="status" hidden></p>
          <p class="bi-meta">AEP 保留一份來源副本（同樣內容只存一次），不會移動或修改你的原始檔，
            並把每份來源轉成 Markdown：之後的擷取都讀這份 Markdown，
            你可以修改它（每次修改是新的版次）。
            掃描的 PDF 沒有文字層，不支援。這一步不會寫入任何卡片。</p>
          <div class="bi-step" id="bi-b-src-withdraw" role="region" aria-label="撤回來源"
            hidden></div>
          <div class="bi-scroll"><table class="bi-table bi-stack" id="bi-b-sources">
            <thead><tr><th>使用</th><th>來源</th><th>格式</th><th>Markdown</th><th>大小</th>
              <th>機密等級</th><th>共用資料夾</th><th>加入時間</th></tr></thead>
              <tbody></tbody></table></div>
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
          <div class="bi-step" id="bi-b-md" role="region" aria-labelledby="bi-b-md-h" hidden>
            <h4 id="bi-b-md-h"></h4>
            <p class="bi-meta" id="bi-b-md-info"></p>
            <div class="bi-step-grid">
              <div><label class="bi-label" for="bi-b-md-rev">看哪一版</label>
                <select id="bi-b-md-rev"></select></div>
            </div>
            <label class="bi-label" for="bi-b-md-text">
              Markdown（修改後存成新的版次；原始檔不會改）</label>
            <textarea id="bi-b-md-text" class="bi-input" rows="16" spellcheck="false"></textarea>
            <div class="bi-step-grid">
              <div><label class="bi-label" for="bi-b-md-note">這一版的說明</label>
                <input id="bi-b-md-note" class="bi-input" maxlength="300"
                  placeholder="例如：修正表格欄位名稱"></div>
              <div><button class="go" id="bi-b-md-save" type="button">存成新版次</button></div>
              <div><button class="bi-btn" id="bi-b-md-close" type="button">關閉</button></div>
            </div>
            <div id="bi-b-md-msg" role="status" aria-live="polite"></div>
          </div>
          <div class="bi-actions"><button class="go" type="button" data-bi-next="schema"
            id="bi-b-next1" disabled>下一步：Schema 與 Ingest</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="schema" aria-labelledby="bi-b-schema"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-schema" tabindex="-1">
            步驟 2／3・Schema 與判讀規則</h3>
          <p class="bi-meta" id="bi-b-schema-now"></p>
          <div id="bi-b-versions"></div>
          <div id="bi-b-upgrade" hidden></div>
          <div class="bi-ai" id="bi-b-sa" role="region" aria-labelledby="bi-b-sa-h">
            <h4 id="bi-b-sa-h">和 AI 一起調整 schema（Session A）</h4>
            <p class="bi-meta" id="bi-b-sa-target"></p>
            <p class="bi-meta" id="bi-b-sa-model"></p>
            <label class="bi-label" for="bi-b-sa-goal">你的目標（用自己的話）</label>
            <input id="bi-b-sa-goal" class="bi-input" maxlength="1000"
              placeholder="例如：追蹤機器人產業的技術、應用與客戶訊號">
            <fieldset class="bi-ai-sources" id="bi-b-sa-sources">
              <legend class="bi-label">附上的樣本來源（最多 5 份，合計上限 12000 字）</legend>
            </fieldset>
            <ol id="bi-b-sa-log" class="bi-log" role="log" aria-live="polite"
              aria-label="schema 對話紀錄"></ol>
            <label class="bi-label" for="bi-b-sa-msg">你想怎麼調整 schema</label>
            <textarea id="bi-b-sa-msg" class="bi-input" rows="3" maxlength="4000"
              placeholder="例如：幫技術卡加一個價格帶欄位"></textarea>
            <div class="bi-actions">
              <button class="go" id="bi-b-sa-send" type="button">送出</button></div>
            <div class="mem-status" id="bi-b-sa-status" role="status" aria-live="polite"
              hidden></div>
          </div>
          <h4>Schema 草稿</h4>
          <p class="bi-meta">草稿每次儲存都是新的版次，可以比較與回復；儲存草稿不會改動任何資料集。
            發布後成為新版本，再用「預覽升級」把資料集移過去。</p>
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
          <div class="bi-ai" id="bi-b-skills" role="region" aria-labelledby="bi-b-skills-h"
            hidden>
            <h4 id="bi-b-skills-h">判讀規則（skills）</h4>
            <p class="bi-meta">放在知識庫裡、跟著 commit 給大家的判讀規則：「分類」說明
              有哪些卡片類型與資料夾，「擷取」是某些資料夾的來源要怎麼讀（領域設定的 notes
              會搬到這裡）。AI 判讀時依來源所在的資料夾選用；固定的證據規則一律先套用，
              不能被改掉。</p>
            <div id="bi-b-sk-list"></div>
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
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-sk-new" type="button">新增擷取規則</button></div>
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
                  只產生這些卡片類型（逗號分隔；留空＝不限）</label>
                  <input id="bi-b-sk-types" class="bi-input" spellcheck="false"></div>
              </div>
              <p class="bi-meta" id="bi-b-sk-folders"></p>
              <label class="bi-label" for="bi-b-sk-body">規則內容</label>
              <textarea id="bi-b-sk-body" class="bi-input" rows="6"></textarea>
              <div class="bi-actions">
                <button class="go" type="submit">存成新版本</button>
                <button class="bi-btn" id="bi-b-sk-cancel" type="button">取消</button></div>
            </form>
            <div class="bi-ai" id="bi-b-ska" role="region" aria-labelledby="bi-b-ska-h" hidden>
              <h4 id="bi-b-ska-h">和 AI 一起修改判讀規則（Session B）</h4>
              <p class="bi-meta" id="bi-b-ska-target"></p>
              <p class="bi-meta" id="bi-b-ska-model"></p>
              <ol id="bi-b-ska-log" class="bi-log" role="log" aria-live="polite"
                aria-label="判讀規則對話紀錄"></ol>
              <label class="bi-label" for="bi-b-ska-msg">你想怎麼調整這條規則</label>
              <textarea id="bi-b-ska-msg" class="bi-input" rows="3" maxlength="4000"
                placeholder="例如：電源相關的規格表，額定功率一律放在 specs 欄位"></textarea>
              <div class="bi-actions">
                <button class="go" id="bi-b-ska-send" type="button">送出</button>
                <button class="bi-btn" id="bi-b-ska-close" type="button">關閉</button></div>
              <div class="mem-status" id="bi-b-ska-status" role="status" aria-live="polite"
                hidden></div>
            </div>
          </div>
          <div class="bi-actions"><button class="bi-btn" type="button" data-bi-next="source">
            上一步</button><button class="go" type="button" data-bi-next="method">
            下一步：試跑</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="method" aria-labelledby="bi-b-method"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-method" tabindex="-1">
            步驟 2／3・試跑</h3>
          <p class="bi-meta">擷取 Skill 決定來源怎麼變成候選卡。內建兩個：「AI 擷取」讀文字與
            Markdown，「表格規則」不用模型、照欄位轉換表格。和 AI 討論或修改內建 Skill 時，
            會另存一份你自己的 Skill；每次修改、套用 AI 建議或回復都是新的版次，
            可以用同一份來源試跑兩個版次再比較。</p>
          <div class="bi-step-grid">
            <div><label class="bi-label" for="bi-b-m-pick">使用的擷取 Skill</label>
              <select id="bi-b-m-pick">
                <option value="builtin:llm">AI 擷取（內建）</option>
                <option value="builtin:rules">表格規則（內建，不用模型）</option>
              </select></div>
            <div id="bi-b-folder-box" hidden><label class="bi-label" for="bi-b-folder">
              來源在知識庫的哪個資料夾（決定 AI 用哪條擷取規則）</label>
              <select id="bi-b-folder"></select></div>
            <div><label class="bi-label" for="bi-b-m-name">另存為新的 Skill（名稱）</label>
              <input id="bi-b-m-name" class="bi-input" maxlength="80"
                placeholder="例如：會議紀錄擷取"></div>
            <div><button class="bi-btn" id="bi-b-m-new" type="button">
              用下方設定另存 Skill</button></div>
          </div>
          <div id="bi-b-m-box" hidden>
            <div id="bi-b-m-info" aria-live="polite"></div>
          </div>
          <div class="bi-ai" id="bi-b-sb" role="region" aria-labelledby="bi-b-sb-h">
            <h4 id="bi-b-sb-h">和 AI 一起調整擷取 Skill（Session B）</h4>
            <p class="bi-meta" id="bi-b-sb-target"></p>
            <p class="bi-meta" id="bi-b-sb-model"></p>
            <ol id="bi-b-sb-log" class="bi-log" role="log" aria-live="polite"
              aria-label="擷取 Skill 對話紀錄"></ol>
            <label class="bi-label" for="bi-b-sb-msg">你想怎麼調整這個 Skill</label>
            <textarea id="bi-b-sb-msg" class="bi-input" rows="3" maxlength="4000"
              placeholder="例如：沒有文件依據的需求標成推測"></textarea>
            <div class="bi-actions">
              <button class="go" id="bi-b-sb-send" type="button">送出</button></div>
            <div class="mem-status" id="bi-b-sb-status" role="status" aria-live="polite"
              hidden></div>
          </div>
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
          <div class="bi-actions"><button class="bi-btn" type="button" data-bi-next="schema">
            上一步</button><button class="go" type="button" data-bi-next="review">
            下一步：逐卡審核</button></div>
        </section>
        <section class="kp-stage card bi-step" data-stage="review" aria-labelledby="bi-b-review"
          hidden>
          <h3 class="kp-stage-title" id="bi-b-review" tabindex="-1">步驟 2／3・逐卡審核</h3>
          <p class="bi-meta">每張候選卡都要你決定接受或拒絕。紅色錯誤要先修正才能接受；
            黃色警告只是提醒。人工設定過的值不會被覆蓋，會成為待審提議。</p>
          <div class="bi-actions">
            <button class="go" id="bi-b-start" type="button">開始正式匯入（產生候選卡）</button>
            <button class="bi-btn" id="bi-b-accept-clean" type="button" disabled>
              接受所有沒有錯誤的候選卡</button></div>
          <div id="bi-b-chips" class="bi-chips" aria-label="候選卡摘要"></div>
          <div class="bi-browse">
            <div><ul id="bi-b-cands" class="bi-cards" aria-label="候選卡清單"></ul></div>
            <div class="bi-detail" id="bi-b-cand" aria-live="polite">
              <p class="bi-empty">選一張候選卡，查看欄位、證據與差異。</p></div>
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
          <h3 class="kp-stage-title" id="bi-b-test" tabindex="-1">步驟 3／3・測試與 Push</h3>
          <p class="bi-meta">先看寫入後的卡片與 Dashboard，再把改動寫下目的 commit、push 給大家。
            也可以用 AI 對話做圖表分析。</p>
          <div class="bi-actions">
            <button class="bi-btn" id="bi-b-to-dash" type="button">看 Dashboard</button>
            <button class="bi-btn" id="bi-b-to-cards" type="button">看卡片</button></div>
          <p class="bi-meta" id="bi-b-ver-none" hidden>這是只在這台電腦的資料集：
            確認寫入後就生效，沒有 commit 與 push。
            要和同事一起維護，請在步驟 1 建立或加入 vault。</p>
          <div id="bi-b-bench" class="bi-step" role="region" aria-labelledby="bi-b-bench-h"
            hidden>
            <h4 id="bi-b-bench-h">題目與擷取測試</h4>
            <p class="bi-meta">測試題用使用者的問法，透過 Agent 分別問「這台電腦的工作版本」與
              「發佈版本」，用「必須提到」與「不可以說」評分；擷取測試用工作版本的判讀規則試跑一段原文，
              檢查找到的卡片與出處。測試跟著知識庫 commit、push。
              push 時，若最近一次測試（測的正是這次要 push 的內容）有題目退步，就不能 push。</p>
            <div class="mem-status" id="bi-b-bench-status" role="status" aria-live="polite"
              hidden></div>
            <h5>測試題</h5>
            <div id="bi-b-bq-list"></div>
            <form id="bi-b-bq-form" class="bi-step" novalidate>
              <div class="bi-step-grid">
                <div><label class="bi-label" for="bi-b-bq-q">題目（使用者會怎麼問）</label>
                  <input id="bi-b-bq-q" class="bi-input" maxlength="1000"
                    placeholder="例如：哪些客戶在評估 TSN？"></div>
                <div><label class="bi-label" for="bi-b-bq-must">必須提到（逗號分隔）</label>
                  <input id="bi-b-bq-must" class="bi-input" maxlength="2000"
                    placeholder="例如：IEEE 802.1"></div>
                <div><label class="bi-label" for="bi-b-bq-not">不可以說（逗號分隔）</label>
                  <input id="bi-b-bq-not" class="bi-input" maxlength="2000"></div>
                <div><label class="bi-label" for="bi-b-bq-set">題組</label>
                  <input id="bi-b-bq-set" class="bi-input" maxlength="60" spellcheck="false"
                    value="main"></div>
              </div>
              <div class="bi-actions"><button class="bi-btn" type="submit">新增測試題</button>
                <button class="bi-btn" id="bi-b-qa-open" type="button">和 AI 一起出題</button></div>
            </form>
            <div class="bi-ai" id="bi-b-qa" role="region" aria-labelledby="bi-b-qa-h" hidden>
              <h5 id="bi-b-qa-h">和 AI 一起出測試題</h5>
              <p class="bi-meta" id="bi-b-qa-target"></p>
              <ol id="bi-b-qa-log" class="bi-log" role="log" aria-live="polite"
                aria-label="出題對話紀錄"></ol>
              <label class="bi-label" for="bi-b-qa-msg">你想測什麼</label>
              <textarea id="bi-b-qa-msg" class="bi-input" rows="3" maxlength="4000"
                placeholder="例如：出五題，涵蓋客戶訊號與產品對應"></textarea>
              <div class="bi-actions">
                <button class="go" id="bi-b-qa-send" type="button">送出</button>
                <button class="bi-btn" id="bi-b-qa-close" type="button">關閉</button></div>
              <div class="mem-status" id="bi-b-qa-status" role="status" aria-live="polite"
                hidden></div>
            </div>
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
            <div class="bi-actions">
              <button class="go" id="bi-b-bench-run" type="button">跑測試</button></div>
            <div id="bi-b-bench-report" aria-live="polite"></div>
          </div>
          <div id="bi-b-an" class="bi-step" role="region" aria-labelledby="bi-b-an-h" hidden>
            <h4 id="bi-b-an-h">分析與圖表</h4>
            <p class="bi-meta">用對話請 AI 寫 SQL 或 Python 腳本，畫出你想看的圖表或表格，
              確認某種關係或現象（例如：哪個標準組織的技術最多）。存起來的分析跟著知識庫
              commit、push，Dashboard 會用最新資料重畫。AI 只能讀資料：SQL 是唯讀的；
              腳本不能連網、不能啟動程式，也不能寫入它的暫存資料夾以外的地方。</p>
            <div id="bi-b-an-list"></div>
            <div class="bi-actions">
              <button class="bi-btn" id="bi-b-an-new" type="button">和 AI 做新分析</button>
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
            <div class="bi-ai" id="bi-b-ana" role="region" aria-labelledby="bi-b-ana-h" hidden>
              <h5 id="bi-b-ana-h">和 AI 做分析</h5>
              <p class="bi-meta" id="bi-b-ana-target"></p>
              <ol id="bi-b-ana-log" class="bi-log" role="log" aria-live="polite"
                aria-label="分析對話紀錄"></ol>
              <label class="bi-label" for="bi-b-ana-msg">你想看什麼</label>
              <textarea id="bi-b-ana-msg" class="bi-input" rows="3" maxlength="4000"
                placeholder="例如：各應用領域各有幾個商機？畫長條圖"></textarea>
              <div class="bi-actions">
                <button class="go" id="bi-b-ana-send" type="button">送出</button>
                <button class="bi-btn" id="bi-b-ana-close" type="button">關閉</button></div>
              <div class="mem-status" id="bi-b-ana-status" role="status" aria-live="polite"
                hidden></div>
            </div>
          </div>
          <div id="bi-b-ver" class="bi-step" role="region" aria-labelledby="bi-b-ver-h" hidden>
            <h4 id="bi-b-ver-h">版本</h4>
            <p class="bi-meta" id="bi-b-ver-reads"></p>
            <h5>還沒給大家的改動</h5>
            <div id="bi-b-ver-pending"></div>
            <div class="bi-step-grid">
              <div><label class="bi-label" for="bi-b-ver-purpose">
                這次改動的目的（commit 一定要寫，之後在歷史裡看得到）</label>
                <input id="bi-b-ver-purpose" class="bi-input" maxlength="500"
                  placeholder="例如：補上 TSN 的標準組織"></div>
            </div>
            <div class="bi-actions">
              <button class="go" id="bi-b-ver-commit" type="button">Commit</button>
              <button class="bi-btn" id="bi-b-ver-push" type="button">Push 給大家</button>
              <button class="bi-btn" id="bi-b-ver-discard" type="button">
                捨棄還沒 commit 的改動</button>
            </div>
            <div id="bi-b-ver-conflicts" role="alert"></div>
            <h5>歷史與發佈</h5>
            <div id="bi-b-ver-history"></div>
          </div>
          <div class="bi-actions"><button class="bi-btn" type="button" data-bi-next="ingest">
            上一步</button></div>
        </section>
      </div>
    </div>
  </section>
  <section id="panel-reviews">
    <div class="workspace-head">
      <div><h2>Reviews</h2>
        <p class="note">Each night the Agent groups failed or down-rated work and proposes an
          improvement. Nothing changes until you decide: <strong>Accept</strong> sends it to
          its normal path (a rule edit or a draft test question opens a review sandbox you
          compare, benchmark and push on the Knowledge page; missing knowledge goes to the
          gap list; a platform problem becomes an issue to follow up),
          <strong>Reject</strong> records why so it is not proposed again for these cases,
          <strong>Snooze</strong> hides it for 7 days. A <strong>Suggested Skill</strong>
          card shows work you keep asking for; open a request to see that conversation,
          or <strong>Ignore</strong> or <strong>Snooze</strong> it.</p>
        <p class="note" id="rv-counts" role="status">reading&hellip;</p></div>
      <button id="rv-refresh" type="button">Refresh</button>
    </div>
    <div class="rv-tabs" role="tablist">
      <button type="button" data-rv="proposed" aria-selected="true">To decide</button>
      <button type="button" data-rv="accepted">Accepted</button>
      <button type="button" data-rv="snoozed">Snoozed</button>
      <button type="button" data-rv="closed">Rejected or done</button>
    </div>
    <div id="rv-list"></div>
    <h3>Knowledge gaps</h3>
    <p class="note">Accepted proposals that say knowledge is missing. Add sources to the named
      drop folder, then mark the gap done.</p>
    <div id="rv-gaps"></div>
      <details class="card" id="xp-card"><summary>
        <strong>Review settings and the latest report</strong>
        <span class="note" id="xp-summary"></span></summary>
        <p class="note">Failed, down-rated and evidence-gap answers are collected as cases;
          a nightly review groups them and proposes improvements. Nothing is changed by the
          review: it only reports.</p>
        <div class="kp-actions">
          <button class="go" id="xp-run" type="button">Review now</button>
          <label>Keep cases <input id="xp-days" type="number" min="1" max="3650"
            style="width:5em"> days</label>
          <label><input id="xp-nightly" type="checkbox"> Review nightly</label>
        </div>
        <fieldset id="xp-suggest">
          <legend>Suggested Skills</legend>
          <label><input id="xp-suggestions" type="checkbox"> Suggest Skills from my repeated
            work</label>
          <p class="note">Each night your own requests are compared; work you repeat becomes
            a card under <strong>To decide</strong>. Only you see your suggestions. A change
            here applies from the next nightly pass, without a restart.</p>
          <p class="note"><strong>Sensitivity</strong>: how often you must repeat a task
            before it is suggested.</p>
          <div id="xp-sensitivity" role="radiogroup" aria-label="Sensitivity"></div>
          <label>Compare at most <input id="xp-max-requests" type="number" min="10" max="1000"
            style="width:6em"> requests a night</label>
        </fieldset>
        <div class="kp-actions">
          <button id="xp-save" type="button">Save settings</button>
        </div>
        <div id="xp-report" class="kp-markdown"></div></details>
  </section>
  <section id="panel-memory" lang="zh-Hant">
    <div class="workspace-head">
      <div><h2>記憶</h2>
        <p class="note">Agent 記得的你的事：待確認的項目、偏好、筆記、各 Skill 的資料與整理進度。
          只有你看得到；這裡的每個變更都記成「你 via web」，大多可以復原。
          Agent 沒有任何工具能讀或改這一頁。</p></div>
      <button id="mem-refresh" class="mem-btn" type="button">更新</button>
    </div>
    <div class="mem-tabs" id="mem-tabs" role="tablist" aria-label="記憶">
      <button type="button" role="tab" data-mem="confirm" aria-selected="true">待確認<span
        class="mem-count"></span></button>
      <button type="button" role="tab" data-mem="preferences" aria-selected="false">偏好<span
        class="mem-count"></span></button>
      <button type="button" role="tab" data-mem="notes" aria-selected="false">筆記<span
        class="mem-count"></span></button>
      <button type="button" role="tab" data-mem="data" aria-selected="false">資料<span
        class="mem-count"></span></button>
      <button type="button" role="tab" data-mem="sync" aria-selected="false">同步進度<span
        class="mem-count"></span></button>
      <button type="button" role="tab" data-mem="records" aria-selected="false">紀錄<span
        class="mem-count"></span></button>
    </div>
    <div id="mem-notice" class="mem-notice" role="status" aria-live="polite"></div>
    <div class="mem-pane" id="mem-pane-confirm" role="tabpanel" aria-label="待確認">
      <p class="mem-intro">自動讀到的值和存著的不一樣時，不會直接覆蓋，而是等你決定。
        平常在對話中就能處理；
        這裡列出所有空間還沒決定的項目。</p>
      <div class="mem-status" id="mem-status-confirm" role="status" aria-live="polite"
           hidden></div>
      <div class="mem-toolbar" id="mem-health-bar">
        <button id="mem-health-run" class="mem-btn" type="button">立即檢查</button>
        <span id="mem-health-last" class="mem-meta"></span>
      </div>
      <div id="mem-health-list"></div>
      <div id="mem-confirm-list"></div>
    </div>
    <div class="mem-pane" id="mem-pane-preferences" role="tabpanel" aria-label="偏好" hidden>
      <p class="mem-intro">你說過、按了「存成偏好」的規則。使用該 Skill 時 Agent 會自動照做。
        修改時會檢查是否和同一個 Skill 的其他偏好矛盾。</p>
      <div class="mem-status" id="mem-status-preferences" role="status" aria-live="polite"
           hidden></div>
      <div id="mem-preferences-list"></div>
    </div>
    <div class="mem-pane" id="mem-pane-notes" role="tabpanel" aria-label="筆記" hidden>
      <p class="mem-intro">對話中存下的筆記。Agent 只在需要時查詢，不會自動帶進每一輪。</p>
      <div class="mem-status" id="mem-status-notes" role="status" aria-live="polite"
           hidden></div>
      <div class="mem-toolbar">
        <input id="mem-note-search" class="mem-field" type="search" placeholder="搜尋筆記"
               aria-label="搜尋筆記">
        <select id="mem-note-tag" class="mem-field" aria-label="依標籤篩選"></select>
        <select id="mem-note-entity" class="mem-field" aria-label="依關聯對象篩選"></select>
      </div>
      <div class="mem-toolbar">
        <label class="mem-check"><input id="mem-note-all" type="checkbox">
          全選（目前列出的）</label>
        <button id="mem-note-export" class="mem-btn" type="button">匯出選取（Markdown）</button>
      </div>
      <div id="mem-notes-list"></div>
    </div>
    <div class="mem-pane" id="mem-pane-data" role="tabpanel" aria-label="資料" hidden>
      <p class="mem-intro">每個記憶空間一列：由哪個 Skill 管理、存了多少、最後何時更新。
        管理的 Skill 已不在這台電腦時標示「無主」，資料保留，由你決定是否刪除（在「紀錄」）。</p>
      <div class="mem-status" id="mem-status-data" role="status" aria-live="polite"
           hidden></div>
      <div id="mem-spaces-list"></div>
      <div id="mem-people" class="mem-sub" hidden>
        <h3>聯絡人</h3>
        <p class="mem-intro">組織圖請在對話中說「&lt;公司&gt; 組織圖」。</p>
        <div class="mem-toolbar">
          <input id="mem-people-search" class="mem-field" type="search"
                 placeholder="搜尋姓名、公司、Email"
                 aria-label="搜尋聯絡人">
          <select id="mem-people-status" class="mem-field" aria-label="在職狀態">
            <option value="any">全部</option><option value="active">在職</option>
            <option value="left">已離職</option></select>
        </div>
        <div id="mem-people-list"></div>
        <div id="mem-person"></div>
      </div>
    </div>
    <div class="mem-pane" id="mem-pane-sync" role="tabpanel" aria-label="同步進度" hidden>
      <p class="mem-intro">每個來源整理到哪裡。「重新整理」讓下次從頭整理（例如簽名檔擷取有誤時）；
        按錯了可以「復原上次重設」。</p>
      <div class="mem-status" id="mem-status-sync" role="status" aria-live="polite"
           hidden></div>
      <div id="mem-sync-list"></div>
    </div>
    <div class="mem-pane" id="mem-pane-records" role="tabpanel" aria-label="紀錄" hidden>
      <p class="mem-intro">紀錄是發生過的事（對話、執行），會依期限清掉；
        記憶是整理出來、之後會再用的東西。</p>
      <div class="mem-status" id="mem-status-records" role="status" aria-live="polite"
           hidden></div>
      <div id="mem-records"></div>
    </div>
  </section>
  <section id="panel-tasks">
    <div class="workspace-head">
      <div><h2>Tasks</h2>
        <p class="note">Workflows and background jobs this Agent ran or is running: converts,
          re-ingests, benchmarks, pushes and experience reviews. Conversations are not listed.
          The newest 50 are kept; running ones refresh by themselves.</p>
        <p class="note" id="task-counts" role="status">reading&hellip;</p></div>
      <button id="task-refresh" type="button">Refresh</button>
    </div>
    <h3 id="pending-cards-heading" hidden>Pending changes</h3>
    <div id="pending-cards"></div>
    <div class="card" id="task-list"></div>
  </section>
  <section id="panel-schedules">
    <div class="workspace-head">
      <div><h2>Scheduled tasks</h2>
        <p class="note">A schedule saves intent only. It runs unattended only after you
          grant it, up to the effect class you choose. Anything that sends mail or
          messages waits for your approval on every run.</p>
        <p class="note" id="schedule-loop" role="status">reading&hellip;</p></div>
      <button class="go" id="schedule-refresh" type="button">Refresh</button>
    </div>
    <h2>Waiting for your approval</h2>
    <div class="card"><div id="schedule-approvals" class="empty">reading&hellip;</div></div>
    <h2>Schedules</h2>
    <div id="schedule-list" class="schedule-grid" aria-live="polite">reading&hellip;</div>
    <div id="schedule-result" class="section-status" role="status" aria-live="polite"></div>
    <h2>History</h2>
    <div class="card"><div id="schedule-history" class="empty">
      Choose History on a schedule.</div></div>
    <h2>New schedule</h2>
    <form id="schedule-form" class="schedule-form">
      <label for="schedule-target">Installed Workflow or Agent Task</label>
      <select id="schedule-target" required></select>
      <p class="hint" id="schedule-target-note"></p>
      <label for="schedule-id">Schedule name</label>
      <input id="schedule-id" required pattern="[a-zA-Z_][a-zA-Z0-9_.\-]*"
             placeholder="weekly-report">
      <label for="schedule-kind">Repeats</label>
      <select id="schedule-kind"><option value="weekly">Weekly</option>
        <option value="daily">Daily</option></select>
      <div id="schedule-days" class="schedule-days" role="group" aria-label="Weekdays"></div>
      <label for="schedule-at">Local time</label>
      <input id="schedule-at" type="time" value="09:00" required>
      <label for="schedule-timezone">Time zone (IANA)</label>
      <input id="schedule-timezone" required>
      <div id="schedule-fields"></div>
      <div id="schedule-json-box" hidden>
        <label for="schedule-json">Runtime inputs (one JSON object)</label>
        <textarea id="schedule-json" spellcheck="false">{}</textarea>
      </div>
      <label><input id="schedule-paused" type="checkbox"> Save paused</label>
      <p><button class="go" id="schedule-save" type="submit">Save schedule</button></p>
      <pre id="schedule-form-result" class="note"></pre>
    </form>
  </section>
</main>
</div>
</div>

<aside class="file-viewer" id="file-viewer" role="dialog" aria-modal="true"
  aria-labelledby="viewer-name" hidden>
  <div class="viewer-head">
    <h2 id="viewer-name"></h2>
    <div class="viewer-modes" id="viewer-modes" role="group" aria-label="檢視方式">
      <button type="button" class="viewer-button" id="viewer-preview-mode"
        aria-pressed="true">Preview</button>
      <button type="button" class="viewer-button" id="viewer-code-mode"
        aria-pressed="false">Code</button>
    </div>
    <button type="button" class="viewer-button" id="viewer-open">在瀏覽器開啟</button>
    <button type="button" class="viewer-button" id="viewer-download">下載</button>
    <button type="button" class="viewer-button" id="viewer-copy" hidden>複製</button>
    <button type="button" class="viewer-button viewer-close" id="viewer-close"
      aria-label="關閉">&#x2715;</button>
  </div>
  <div class="viewer-body" id="viewer-body"></div>
</aside>
<script>
"use strict";
const TOKEN = new URLSearchParams(location.search).get("token") || "";
// Taken out of the address bar at once: a token left in the URL is a token in
// the history, in a screenshot and in anything that syncs tabs.
history.replaceState(null, "", location.pathname);

async function call(path, body) {
  const hasBody = body !== undefined;
  const options = {
    method: hasBody ? "POST" : "GET",
    headers: {"Authorization": "Bearer " + TOKEN},
  };
  if (hasBody) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const reply = await fetch(path, options);
  if (reply.status === 401) {
    // The access key changes on every start; an older tab can no longer act.
    const expired = new Error("This page is from an earlier start of Agent Web. Open the "
      + "newest Agent Web tab (or the address printed when it started) and try again.");
    expired.code = "page_expired"; throw expired;
  }
  if (!reply.ok && reply.status !== 200) {
    const failed = await reply.json().catch(() => ({error: reply.statusText}));
    const problem = new Error(failed.error || failed.code || ("the host answered " + reply.status));
    problem.code = failed.code || "request_failed"; problem.payload = failed; throw problem;
  }
  return reply.json();
}

const el = (id) => document.getElementById(id);
const text = (value) => document.createTextNode(value == null ? "" : String(value));

function table(columns, rows, cell) {
  if (!rows.length) { const p = document.createElement("div");
    p.className = "empty"; p.append(text("nothing here")); return p; }
  const t = document.createElement("table");
  const head = t.insertRow();
  for (const name of columns) {
    const th = document.createElement("th"); th.append(text(name)); head.append(th);
  }
  for (const [index, row] of rows.entries()) {
    const tr = t.insertRow();
    for (const value of cell(row, index)) {
      const td = tr.insertCell();
      if (value instanceof Node) td.append(value); else td.append(text(value));
    }
  }
  return t;
}

function tag(on, yes, no) {
  const span = document.createElement("span");
  span.className = "tag " + (on ? "on" : "off");
  span.append(text(on ? yes : no));
  return span;
}

// Render the useful Markdown subset without accepting model-supplied HTML.
// Every string becomes a text node; only these local element constructors add markup.
function safeMarkdownHref(value) {
  if (!/^(https?:\/\/|mailto:)/i.test(value)) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:", "mailto:"].includes(url.protocol) ? url.href : null;
  } catch (_) { return null; }
}

function appendMarkdownInline(target, source, depth = 0) {
  const value = String(source == null ? "" : source);
  if (depth > 6) { target.append(text(value)); return; }
  let index = 0, plain = "";
  const flush = () => { if (plain) { target.append(text(plain)); plain = ""; } };
  while (index < value.length) {
    if (value[index] === "\\" && index + 1 < value.length
        && /[\\`*\[\]()~]/.test(value[index + 1])) {
      plain += value[index + 1]; index += 2; continue;
    }
    if (value[index] === "`") {
      const marker = /^`+/.exec(value.slice(index))[0];
      const end = value.indexOf(marker, index + marker.length);
      if (end > index + marker.length) {
        flush(); const code = document.createElement("code");
        code.append(text(value.slice(index + marker.length, end)));
        target.append(code); index = end + marker.length; continue;
      }
    }
    if (value[index] === "[") {
      const middle = value.indexOf("](", index + 1);
      const end = middle < 0 ? -1 : value.indexOf(")", middle + 2);
      if (end > middle + 2) {
        const href = safeMarkdownHref(value.slice(middle + 2, end).trim());
        if (href) {
          flush(); const link = document.createElement("a");
          link.href = href; link.target = "_blank"; link.rel = "noopener noreferrer";
          appendMarkdownInline(link, value.slice(index + 1, middle), depth + 1);
          target.append(link); index = end + 1; continue;
        }
      }
    }
    let formatted = false;
    for (const [marker, element] of [["**", "strong"], ["~~", "del"], ["*", "em"]]) {
      if (!value.startsWith(marker, index)) continue;
      const end = value.indexOf(marker, index + marker.length);
      if (end <= index + marker.length) continue;
      flush(); const node = document.createElement(element);
      appendMarkdownInline(node, value.slice(index + marker.length, end), depth + 1);
      target.append(node); index = end + marker.length; formatted = true; break;
    }
    if (formatted) continue;
    plain += value[index]; index += 1;
  }
  flush();
}

function markdownRow(line) {
  let value = line.trim();
  if (value.startsWith("|")) value = value.slice(1);
  if (value.endsWith("|") && !value.endsWith("\\|")) value = value.slice(0, -1);
  const cells = []; let cell = "";
  for (let index = 0; index < value.length; index += 1) {
    if (value[index] === "\\" && value[index + 1] === "|") {
      cell += "|"; index += 1;
    } else if (value[index] === "|") {
      cells.push(cell.trim()); cell = "";
    } else cell += value[index];
  }
  cells.push(cell.trim());
  return cells;
}

function markdownTableStart(lines, index) {
  if (index + 1 >= lines.length || !lines[index].includes("|")) return false;
  const columns = markdownRow(lines[index]).length;
  const divider = markdownRow(lines[index + 1]);
  return columns > 1 && divider.length === columns
    && divider.every(cell => /^:?-{3,}:?$/.test(cell));
}

function markdownBlockStart(lines, index) {
  const line = lines[index];
  return /^ {0,3}(?:#{1,6}\s|`{3,}|~{3,}|>|[-*+]\s|\d+[.)]\s)/.test(line)
    || /^ {0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)
    || markdownTableStart(lines, index);
}

function renderMarkdown(source) {
  const lines = String(source == null ? "" : source).replace(/\r\n?/g, "\n").split("\n");
  const output = document.createDocumentFragment();
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index += 1; continue; }
    const fence = /^ {0,3}(`{3,}|~{3,})/.exec(line);
    if (fence) {
      const contents = []; index += 1;
      while (index < lines.length && !lines[index].trim().startsWith(fence[1])) {
        contents.push(lines[index]); index += 1;
      }
      if (index < lines.length) index += 1;
      const pre = document.createElement("pre"), code = document.createElement("code");
      code.append(text(contents.join("\n"))); pre.append(code); output.append(pre); continue;
    }
    const heading = /^ {0,3}(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      const title = document.createElement("h" + heading[1].length);
      appendMarkdownInline(title, heading[2]); output.append(title); index += 1; continue;
    }
    if (markdownTableStart(lines, index)) {
      const headers = markdownRow(line), wrap = document.createElement("div");
      wrap.className = "table-scroll"; wrap.setAttribute("role", "region");
      wrap.setAttribute("aria-label", "Answer table"); wrap.tabIndex = 0;
      const table = document.createElement("table"), head = document.createElement("thead");
      const headerRow = document.createElement("tr");
      for (const heading of headers) {
        const th = document.createElement("th"); th.scope = "col";
        appendMarkdownInline(th, heading); headerRow.append(th);
      }
      head.append(headerRow); table.append(head);
      const body = document.createElement("tbody"); index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        const row = document.createElement("tr"), cells = markdownRow(lines[index]);
        for (let column = 0; column < headers.length; column += 1) {
          const td = document.createElement("td");
          appendMarkdownInline(td, cells[column] || ""); row.append(td);
        }
        body.append(row); index += 1;
      }
      table.append(body); wrap.append(table); output.append(wrap); continue;
    }
    if (/^ {0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      output.append(document.createElement("hr")); index += 1; continue;
    }
    const listStart = /^( {0,3})([-*+]|\d+[.)])\s+(.+)$/.exec(line);
    if (listStart) {
      const ordered = /^\d/.test(listStart[2]);
      const list = document.createElement(ordered ? "ol" : "ul");
      while (index < lines.length) {
        const item = /^( {0,3})([-*+]|\d+[.)])\s+(.+)$/.exec(lines[index]);
        if (!item || item[1].length !== listStart[1].length
            || /^\d/.test(item[2]) !== ordered) break;
        const li = document.createElement("li");
        appendMarkdownInline(li, item[3]); list.append(li); index += 1;
      }
      output.append(list); continue;
    }
    if (/^ {0,3}>\s?/.test(line)) {
      const quote = document.createElement("blockquote"), paragraph = document.createElement("p");
      const quoted = [];
      while (index < lines.length && /^ {0,3}>\s?/.test(lines[index])) {
        quoted.push(lines[index].replace(/^ {0,3}>\s?/, "")); index += 1;
      }
      appendMarkdownInline(paragraph, quoted.join("\n"));
      quote.append(paragraph); output.append(quote); continue;
    }
    const paragraph = document.createElement("p"), parts = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !markdownBlockStart(lines, index)) {
      parts.push(lines[index]); index += 1;
    }
    appendMarkdownInline(paragraph, parts.join("\n")); output.append(paragraph);
  }
  return output;
}

function renderAnswer(target, answer) {
  target.replaceChildren(renderMarkdown(answer));
}

// -- Ask ------------------------------------------------------------------

const log = el("log"), form = el("ask"), field = el("message"), send = el("send");
let activeConversation = "";
let conversationRows = [];
let backendStatuses = new Map();
let activeBackend = "gateway";
let pendingBackend = "";
let pendingPublicBackend = "";
let activeConversationPublic = false;
let activeConversationMessages = 0;

function turn(asked, replyQuestion, files, session) {
  const block = turnBlock(asked, replyQuestion, files, session);
  log.append(block);
  log.scrollTop = log.scrollHeight;
  return block.querySelector(".said");
}

// -- Files in the chat ----------------------------------------------------
// Owner 2026-10-20: a file on an answer (or one the person attached) is a
// chip that opens the viewer panel with Preview / Code, as in Codex and
// Claude Code. Files come only through the token-checked, path-confined
// /api/conversations/file route; an HTML file is rendered only in a frame
// with sandbox="allow-scripts" (no allow-same-origin), loaded from a
// short-lived /view/file?nonce= address served with a strict CSP, so the
// page token never reaches the frame (docs/DECISIONS.md 2026-10-20).

const CODE_MAX_LINES = 5000;
const CODE_MAX_CHARS = 1000000;
const TEXT_KINDS = new Set(["json", "csv", "tsv", "txt", "log", "py", "ps1", "psm1", "yaml",
  "yml", "toml", "ini", "cfg", "xml", "sql", "sh", "bat", "cmd", "js", "ts", "css"]);

function fileExtension(file) {
  const name = String(file.filename || file.path || "");
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

function fileKind(file) {
  const ext = fileExtension(file);
  if (file.kind === "image" || ["png", "jpg", "jpeg", "gif", "webp", "bmp"].includes(ext)) {
    return "image";
  }
  if (ext === "html" || ext === "htm") return "html";
  if (ext === "md" || ext === "markdown") return "md";
  if (ext === "csv") return "csv";
  if (TEXT_KINDS.has(ext)) return "text";
  return "other";
}

function fileQuery(session, file) {
  return "session_id=" + encodeURIComponent(session)
    + "&path=" + encodeURIComponent(file.path || "");
}

function fetchFile(session, file) {
  return fetch("/api/conversations/file?" + fileQuery(session, file),
    {headers: {"Authorization": "Bearer " + TOKEN}})
    .then(reply => reply.ok ? reply.blob() : Promise.reject(new Error(String(reply.status))));
}

async function htmlViewUrl(session, file) {
  const reply = await fetch("/api/conversations/view-link?" + fileQuery(session, file),
    {headers: {"Authorization": "Bearer " + TOKEN}});
  const data = await reply.json();
  if (!reply.ok || !data.ok) throw new Error(data.code || String(reply.status));
  return data.url;
}

function sandboxFrame(url, title) {
  const frame = document.createElement("iframe");
  // Scripts inside the file only; no allow-same-origin, so the frame has an
  // opaque origin and cannot read this page, its token, cookies or APIs.
  frame.setAttribute("sandbox", "allow-scripts");
  frame.setAttribute("referrerpolicy", "no-referrer");
  frame.title = title || "HTML";
  frame.src = url;
  return frame;
}

function fileIcon(kind) {
  return {image: "\ud83d\uddbc", html: "\ud83c\udf10", md: "\ud83d\udcdd", csv: "\ud83d\udcca",
    text: "\ud83d\udcc4"}[kind] || "\ud83d\udcce";
}

function fileChip(session, file) {
  const chip = document.createElement("button");
  chip.type = "button"; chip.className = "file-chip";
  chip.dataset.path = file.path || "";
  chip.setAttribute("aria-label", "開啟檔案 " + (file.filename || ""));
  const name = document.createElement("span");
  name.append(text(file.filename || ""));
  chip.append(text(fileIcon(fileKind(file))), name);
  chip.addEventListener("click", () => openFileViewer(session, file, chip));
  return chip;
}

function fileChips(session, files) {
  const row = document.createElement("div");
  row.className = "file-chips";
  for (const file of files) row.append(fileChip(session, file));
  return row;
}

// A picture a tool drew for an answer (an org chart, docs/phases/BUSINESS_CARDS.md):
// fetched with the page's token, shown inline, opened in the viewer on a click.
function answerImage(session, file) {
  const figure = document.createElement("figure");
  figure.className = "answer-image";
  const image = document.createElement("img");
  image.alt = file.filename || "";
  const caption = document.createElement("figcaption");
  caption.append(text(file.filename || ""));
  figure.append(image, caption);
  fetchFile(session, file)
    .then(blob => {
      image.src = URL.createObjectURL(blob);
      image.addEventListener("click", () => openFileViewer(session, file, image));
    })
    .catch(() => { caption.replaceChildren(text((file.filename || "") + " (not available)")); });
  return figure;
}

// An HTML file on an answer (the interactive org chart): inline, sandboxed,
// at a reasonable height, resizable, with Expand / Open in panel / browser.
function answerHtml(session, file) {
  const box = document.createElement("figure");
  box.className = "answer-html";
  box.dataset.path = file.path || "";
  const wrap = document.createElement("div");
  wrap.className = "frame-wrap";
  const bar = document.createElement("figcaption");
  bar.className = "frame-bar";
  const name = document.createElement("span");
  name.className = "name"; name.append(text(file.filename || ""));
  const expand = viewerButton("放大", () => {
    const tall = box.classList.toggle("tall");
    expand.textContent = tall ? "縮小" : "放大";
    expand.setAttribute("aria-pressed", String(tall));
  });
  expand.setAttribute("aria-pressed", "false");
  const panel = viewerButton("在面板開啟", () => openFileViewer(session, file, panel));
  const browser = viewerButton("在瀏覽器開啟", () => openInBrowser(session, file));
  bar.append(name, expand, panel, browser);
  box.append(wrap, bar);
  htmlViewUrl(session, file)
    .then(url => wrap.append(sandboxFrame(url, file.filename)))
    .catch(() => { name.replaceChildren(text((file.filename || "") + " (not available)")); });
  return box;
}

// A real Atlas panel or dashboard on an answer (BI E2, E3): the Host built the path; the
// address is this browser's Atlas preference. The contract requires referrerpolicy="origin"
// (Agent Web sends no-referrer, and localhost to 127.0.0.1 is cross-site) and a real origin
// inside the frame. Asked server-side first, since a frame's load event cannot tell whether
// Atlas answered; when it cannot be framed, the answer shows AEP's own chart with a note.
const ATLAS_EMBED_HEIGHT = {min: 160, max: 1200};

function atlasEmbedAddress() {
  // Only a loopback Atlas can be asked for from this PC, and never this page's own origin:
  // scripts with the same origin as their parent would be free of the sandbox.
  try {
    const url = new URL(biAtlasUrl());
    if (!["127.0.0.1", "localhost"].includes(url.hostname)) return null;
    if (url.origin === location.origin) return null;
    return {origin: url.origin, port: url.port || (url.protocol === "https:" ? "443" : "80")};
  } catch (e) { return null; }
}

function answerAtlasEmbed(session, embed, files) {
  const box = document.createElement("div");
  box.className = "answer-atlas";
  const fallBack = () => {
    const note = document.createElement("p");
    note.className = "atlas-embed-note";
    const file = files.find((item) => item.path === embed.fallback);
    note.append(text(file ? "Atlas 沒有執行，這裡顯示 AEP 的圖表；開啟 Atlas 可看到完整版本。"
      : "Atlas 沒有執行；開啟 Atlas 可看到「" + String(embed.title || "") + "」。"));
    box.replaceChildren(note, ...(file ? [answerHtml(session, file)] : []));
  };
  const path = String(embed.path || "");
  const address = atlasEmbedAddress();
  const ours = path.startsWith("/embed/panel?") || path.startsWith("/embed/dashboard/");
  if (!address || !ours) { fallBack(); return box; }
  call("/api/bi/atlas-embed?port=" + encodeURIComponent(address.port))
    .then((reply) => {
      if (!reply.framable) { fallBack(); return; }
      box.replaceChildren(atlasEmbedFrame(embed, address.origin + path, address.origin));
    })
    .catch(fallBack);
  return box;
}

function atlasEmbedFrame(embed, url, origin) {
  const figure = document.createElement("figure");
  figure.className = "answer-html";
  const wrap = document.createElement("div");
  wrap.className = "frame-wrap";
  const frame = document.createElement("iframe");
  frame.setAttribute("sandbox", "allow-scripts allow-same-origin");
  frame.setAttribute("referrerpolicy", "origin");
  frame.dataset.atlasOrigin = origin;
  frame.title = String(embed.title || "Atlas");
  frame.src = url;
  wrap.append(frame);
  const bar = document.createElement("figcaption");
  bar.className = "frame-bar";
  const name = document.createElement("span");
  name.className = "name"; name.append(text(String(embed.title || "") + "（Atlas）"));
  const expand = viewerButton("放大", () => {
    const tall = figure.classList.toggle("tall");
    if (tall) wrap.style.removeProperty("height");
    expand.textContent = tall ? "縮小" : "放大";
    expand.setAttribute("aria-pressed", String(tall));
  });
  expand.setAttribute("aria-pressed", "false");
  bar.append(name, expand);
  figure.append(wrap, bar);
  return figure;
}

window.addEventListener("message", (event) => {
  // The embed's preferred height: only from the frame it came from, at Atlas's origin.
  const data = event.data;
  if (!data || data.type !== "atlas-embed-size" || !Number.isInteger(data.height)) return;
  if (data.height <= 0) return;
  for (const frame of document.querySelectorAll("iframe[data-atlas-origin]")) {
    if (frame.contentWindow !== event.source) continue;
    if (frame.dataset.atlasOrigin !== event.origin) return;
    const figure = frame.closest("figure");
    if (figure && figure.classList.contains("tall")) return;
    const height = Math.min(ATLAS_EMBED_HEIGHT.max, Math.max(ATLAS_EMBED_HEIGHT.min, data.height));
    frame.parentNode.style.height = height + "px";
    return;
  }
});

function viewerButton(label, action) {
  const button = document.createElement("button");
  button.type = "button"; button.className = "viewer-button";
  button.append(text(label));
  button.addEventListener("click", action);
  return button;
}

async function openInBrowser(session, file) {
  // A blank tab first (a tab opened after an await is blocked), cut off from
  // this page, then pointed at the file.
  const tab = window.open("", "_blank");
  if (tab) tab.opener = null;
  try {
    const url = fileKind(file) === "html"
      ? await htmlViewUrl(session, file)
      : URL.createObjectURL(await fetchFile(session, file));
    if (tab) tab.location.replace(url); else window.open(url, "_blank", "noopener");
  } catch (error) {
    if (tab) tab.close();
  }
}

async function downloadFile(session, file) {
  try {
    const blob = await fetchFile(session, file);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = file.filename || "file";
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 30000);
  } catch (error) { /* the chip stays; the panel says when a file is gone */ }
}

const viewer = {session: "", file: null, mode: "preview", text: null, returnTo: null};

function codeView(source) {
  let shown = String(source), notice = "";
  if (shown.length > CODE_MAX_CHARS) shown = shown.slice(0, CODE_MAX_CHARS);
  let lines = shown.replace(/\r\n?/g, "\n").split("\n");
  if (lines.length > CODE_MAX_LINES || shown.length < String(source).length) {
    lines = lines.slice(0, CODE_MAX_LINES);
    notice = "檔案較大，只顯示前 " + lines.length + " 行";
  }
  const out = document.createDocumentFragment();
  if (notice) {
    const note = document.createElement("p");
    note.className = "viewer-note"; note.append(text(notice)); out.append(note);
  }
  const scroll = document.createElement("div");
  scroll.className = "code-scroll";
  const grid = document.createElement("div");
  grid.className = "code-view";
  const gutter = document.createElement("pre");
  gutter.className = "gutter"; gutter.setAttribute("aria-hidden", "true");
  gutter.append(text(lines.map((_, index) => String(index + 1)).join("\n")));
  const code = document.createElement("pre");
  code.className = "code"; code.tabIndex = 0;
  code.setAttribute("aria-label", "檔案內容");
  code.append(text(lines.join("\n")));
  grid.append(gutter, code); scroll.append(grid); out.append(scroll);
  return out;
}

function csvRows(source, limit) {
  const rows = []; let row = [], cell = "", quoted = false;
  for (let index = 0; index < source.length && rows.length < limit; index += 1) {
    const ch = source[index];
    if (quoted) {
      if (ch === '"' && source[index + 1] === '"') { cell += '"'; index += 1; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { row.push(cell); cell = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && source[index + 1] === "\n") index += 1;
      row.push(cell); rows.push(row); row = []; cell = "";
    } else cell += ch;
  }
  if ((cell || row.length) && rows.length < limit) { row.push(cell); rows.push(row); }
  return rows;
}

function csvTable(source) {
  const rows = csvRows(String(source), 501);
  const wrap = document.createElement("div");
  wrap.className = "table-scroll"; wrap.tabIndex = 0;
  wrap.setAttribute("role", "region"); wrap.setAttribute("aria-label", "CSV");
  const table = document.createElement("table");
  table.className = "csv-table";
  rows.forEach((cells, index) => {
    const tr = document.createElement("tr");
    for (const value of cells) {
      const cell = document.createElement(index === 0 ? "th" : "td");
      cell.append(text(value)); tr.append(cell);
    }
    table.append(tr);
  });
  wrap.append(table);
  if (rows.length > 500) {
    const note = document.createElement("p");
    note.className = "viewer-note"; note.append(text("檔案較大，只顯示前 500 列"));
    wrap.append(note);
  }
  return wrap;
}

function viewerModes(kind) {
  if (kind === "html" || kind === "md" || kind === "csv") return ["preview", "code"];
  if (kind === "image") return ["preview"];
  if (kind === "text") return ["code"];
  return [];
}

async function viewerText() {
  if (viewer.text === null) {
    viewer.text = await (await fetchFile(viewer.session, viewer.file)).text();
  }
  return viewer.text;
}

async function showViewer() {
  const body = el("viewer-body");
  const file = viewer.file, kind = fileKind(file), modes = viewerModes(kind);
  el("viewer-modes").hidden = modes.length < 2;
  el("viewer-preview-mode").setAttribute("aria-pressed", String(viewer.mode === "preview"));
  el("viewer-code-mode").setAttribute("aria-pressed", String(viewer.mode === "code"));
  el("viewer-copy").hidden = viewer.mode !== "code";
  body.replaceChildren();
  const pane = document.createElement("div");
  pane.className = "viewer-preview";
  body.append(pane);
  const wanted = file;
  try {
    if (!modes.length) {
      const note = document.createElement("p");
      note.className = "viewer-note";
      note.append(text("這種檔案無法在這裡預覽；請用「下載」或「在瀏覽器開啟」。"));
      pane.append(note);
    } else if (viewer.mode === "code") {
      const source = await viewerText();
      if (viewer.file === wanted) pane.append(codeView(source));
    } else if (kind === "html") {
      const url = await htmlViewUrl(viewer.session, file);
      if (viewer.file === wanted) pane.append(sandboxFrame(url, file.filename));
    } else if (kind === "image") {
      const image = document.createElement("img");
      image.alt = file.filename || "";
      image.src = URL.createObjectURL(await fetchFile(viewer.session, file));
      pane.classList.add("doc"); pane.append(image);
    } else if (kind === "md") {
      const source = await viewerText();
      pane.classList.add("doc"); pane.append(renderMarkdown(source));
    } else if (kind === "csv") {
      pane.classList.add("doc"); pane.append(csvTable(await viewerText()));
    }
  } catch (error) {
    const note = document.createElement("p");
    note.className = "viewer-note";
    note.append(text((file.filename || "") + "：無法讀取（" + error.message + "）"));
    pane.replaceChildren(note);
  }
}

function openFileViewer(session, file, returnTo) {
  viewer.session = session; viewer.file = file; viewer.text = null;
  viewer.returnTo = returnTo || document.activeElement;
  viewer.mode = viewerModes(fileKind(file))[0] || "preview";
  el("viewer-name").textContent = file.filename || "";
  el("file-viewer").hidden = false;
  showViewer();
  el("viewer-close").focus();
}

function closeFileViewer() {
  const panel = el("file-viewer");
  if (panel.hidden) return false;
  panel.hidden = true;
  el("viewer-body").replaceChildren();
  viewer.file = null; viewer.text = null;
  if (viewer.returnTo && document.contains(viewer.returnTo)) viewer.returnTo.focus();
  return true;
}

function setViewerMode(mode) {
  if (!viewer.file || !viewerModes(fileKind(viewer.file)).includes(mode)) return;
  viewer.mode = mode;
  showViewer();
}

el("viewer-close").addEventListener("click", closeFileViewer);
el("viewer-preview-mode").addEventListener("click", () => setViewerMode("preview"));
el("viewer-code-mode").addEventListener("click", () => setViewerMode("code"));
el("viewer-open").addEventListener("click",
  () => { if (viewer.file) openInBrowser(viewer.session, viewer.file); });
el("viewer-download").addEventListener("click",
  () => { if (viewer.file) downloadFile(viewer.session, viewer.file); });
el("viewer-copy").addEventListener("click", async () => {
  const button = el("viewer-copy");
  try {
    await navigator.clipboard.writeText(await viewerText());
    button.textContent = "已複製";
  } catch (error) { button.textContent = "無法複製"; }
  setTimeout(() => { button.textContent = "複製"; }, 1500);
});
el("file-viewer").addEventListener("keydown", (event) => {
  if (event.key === "Escape") { event.stopPropagation(); closeFileViewer(); return; }
  if (event.key !== "Tab") return;
  // Keep focus inside the panel while it is open.
  const items = Array.from(el("file-viewer").querySelectorAll(
    "button:not([hidden]), [tabindex='0'], iframe")).filter(node => node.offsetParent !== null);
  if (!items.length) return;
  const first = items[0], last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) { last.focus(); event.preventDefault(); }
  else if (!event.shiftKey && document.activeElement === last) {
    first.focus(); event.preventDefault();
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeFileViewer();
});

function renderConversation(record) {
  log.replaceChildren();
  closeTurnMenu();
  // Files wait in the conversation they were uploaded to.
  if (attachmentSession && attachmentSession !== activeConversation) clearAttachments();
  if (replyTarget && !(record && record.messages.some(
    item => item.message_id === replyTarget.message_id))) clearReply();
  if (!record) return;
  const questions = new Map();
  for (let index = 0; index + 1 < record.messages.length; index += 2) {
    questions.set(record.messages[index + 1].message_id, record.messages[index].text);
  }
  for (let index = 0; index < record.messages.length; index += 2) {
    const asked = record.messages[index];
    const replied = record.messages[index + 1];
    const said = turn(asked.text, asked.reply_to ? questions.get(asked.reply_to) || "" : null,
      asked.attachments || [], record.session_id);
    said.parentNode.dataset.askedId = asked.message_id;
    if (replied) {
      said.className = "said" + (replied.status === "failed" ? " bad" : "");
      renderAnswer(said, replied.text);
      const answerFiles = replied.attachments || [];
      const embeds = replied.atlas_embeds || [];
      for (const embed of embeds) {
        said.parentNode.append(answerAtlasEmbed(record.session_id, embed, answerFiles));
      }
      const fallbacks = new Set(embeds.map((embed) => embed.fallback));
      for (const file of answerFiles) {
        if (fallbacks.has(file.path)) continue;  // shown by its embed when Atlas is not running
        const kind = fileKind(file);
        if (kind === "image") said.parentNode.append(answerImage(record.session_id, file));
        else if (kind === "html") said.parentNode.append(answerHtml(record.session_id, file));
      }
      if (answerFiles.length) said.parentNode.append(fileChips(record.session_id, answerFiles));
      if (replied.delegations && replied.delegations.length) {
        said.parentNode.append(delegationRecord(record.session_id, replied.delegations));
      }
      if (replied.task_summary_id) {
        said.parentNode.append(summaryNoteButton(replied.task_summary_id));
      }
      // A Telegram conversation is read here: nothing to rate or reply to.
      if (record.source === "telegram") said.parentNode.dataset.messageId = replied.message_id;
      else attachTurnControls(said.parentNode, asked.text, replied);
      const installForm = replied.workflow_form
        && replied.workflow_form.origin === "install";
      if (replied.workflow_form && !installForm) {
        // Only the newest answer's form starts open; older ones fold away.
        chatRunForm(said.parentNode, replied, record.session_id,
          index + 2 >= record.messages.length);
      }
      for (const shown of replied.action_cards || []) {
        said.parentNode.append(shown.card_id.startsWith("dr-")
          ? renderActionCard(shown, (decided) => draftCardDecided(record.session_id,
            replied.message_id, decided))
          : renderActionCard(shown));
      }
      if (installForm) {
        // A Workflow installed from its draft card: its run form under the card.
        chatRunForm(said.parentNode, replied, record.session_id,
          index + 2 >= record.messages.length || openInstallForm === replied.message_id);
      }
      if (replied.action_card) {
        said.parentNode.append(renderActionCard(replied.action_card, async () => {
          if (record.session_id === activeConversation) {
            await loadConversations(record.session_id);
          }
        }));
      }
    }
  }
  renderPendingTurns(record.session_id);
  renderApprovals(record.session_id).catch(() => {});
}

// -- A Workflow's run form in the chat (owner 2026-10-15) -------------------
// "Run X" in the chat answers with the Workflow's own generated form: the
// same renderer as Capabilities > Workflow > Run this Workflow, filled with
// the values the person already gave. Settings are never asked here.

let assetsReady = null;

function installedWorkflow(identity) {
  const all = installedAssets.workflows || [];
  return all.find((item) => item.namespace === identity.namespace
      && item.name === identity.name && item.version === identity.version)
    || all.find((item) => item.namespace === identity.namespace
      && item.name === identity.name);
}

function openWorkflowSettings(workflow) {
  activeCapabilityKind = "workflows"; activeCapabilityFilter = "all";
  activeCapabilityKey = "installed:" + capabilityKey(workflow);
  selectPrimaryTab("installed");
}

function chatRunForm(block, message, session, open) {
  const offer = message.workflow_form;
  const holder = document.createElement("details");
  holder.className = "chat-run-form"; holder.open = !!open;
  holder.dataset.workflow = offer.workflow.namespace + "/" + offer.workflow.name;
  const summary = document.createElement("summary");
  summary.append(text("Run " + offer.title));
  const body = document.createElement("div");
  holder.append(summary, body);
  block.append(holder);
  let drawn = false;
  const draw = () => {
    if (drawn || !holder.open) return;
    drawn = true;
    drawChatRunForm(body, offer, message, session).catch((failure) => {
      body.replaceChildren(text("The form could not be drawn: " + failure.message));
    });
  };
  holder.addEventListener("toggle", draw);
  draw();
}

async function drawChatRunForm(body, offer, message, session) {
  let workflow = installedWorkflow(offer.workflow);
  if (!workflow && assetsReady) {
    await assetsReady.catch(() => {});
    workflow = installedWorkflow(offer.workflow);
  }
  if (!workflow) {
    body.replaceChildren(text(offer.title + " is not installed on this Agent any more."));
    return;
  }
  const identity = {namespace: workflow.namespace, name: workflow.name,
    version: workflow.version};
  if (workflow.description) {
    const about = document.createElement("p"); about.className = "chat-run-note";
    about.append(text(workflow.description)); body.append(about);
  }
  const missing = offer.missing_settings || [];
  const run = document.createElement("button"); run.type = "button";
  run.className = "go"; run.append(text("Run"));
  if (missing.length) {
    const notice = document.createElement("div"); notice.className = "chat-run-missing";
    notice.setAttribute("role", "status");
    notice.append(text("Not set yet: " + missing.map((item) => item.label || item.name)
      .join(", ") + ". These are settings of this Workflow on this computer, set once on "
      + "its settings page, not run values."));
    const open = document.createElement("button"); open.type = "button";
    open.className = "btn small"; open.append(text("Open " + offer.title + " settings"));
    open.addEventListener("click", () => openWorkflowSettings(workflow));
    notice.append(document.createElement("br"), open);
    body.append(notice);
    run.disabled = true;
  }
  const fields = workflow.parameters.editor === "fields" ? workflow.parameters.fields : [];
  const container = document.createElement("div");
  const prefix = "chat-" + message.message_id + "-";
  if (!fields.length) {
    const none = document.createElement("p"); none.className = "chat-run-note";
    none.append(text("This Workflow asks for nothing; press Run to start it."));
    body.append(none);
  }
  const given = offer.prefill || {};
  const named = fields.filter(field => Object.prototype.hasOwnProperty.call(given, field.name));
  if (named.length) {
    // Values read from the chat message (owner 2026-10-25), shown so they can be checked.
    const note = document.createElement("p"); note.className = "chat-run-note chat-run-given";
    note.append(text("已從你的訊息帶入：" + named.map(
      field => field.label + " = " + formatGiven(given[field.name], field)).join("；")));
    body.append(note);
  }
  body.append(container);
  renderParameterForm(container, fields, prefix, {workflow: identity, uploads: true,
    presets: true, values: given, collapseOptional: true});
  const actions = document.createElement("div"); actions.className = "chat-run-actions";
  const result = document.createElement("p"); result.className = "chat-run-result";
  result.setAttribute("aria-live", "polite");
  actions.append(run);
  body.append(actions, result);
  run.addEventListener("click", async () => {
    let values;
    try { values = collectParameterValues(container, fields, prefix); }
    catch (failure) { result.textContent = "Cannot run: " + failure.message; return; }
    run.disabled = true; run.setAttribute("aria-busy", "true");
    const started = Date.now();
    const tick = () => {
      result.textContent = "Running " + offer.title + "\u2026 "
        + Math.round((Date.now() - started) / 1000) + " s";
    };
    tick();
    const timer = setInterval(tick, 1000);
    try {
      const launched = await call("/api/workflows/run", {
        workflow: identity, arguments: values, session_id: session,
        idempotency_key: "chat-" + Date.now() + "-" + Math.random().toString(16).slice(2),
      });
      result.textContent = launched.answer;
      if (session === activeConversation) {
        await loadConversations(session);
        log.scrollTop = log.scrollHeight;
      }
    } catch (failure) {
      result.textContent = "The Workflow did not run: " + failure.message;
    } finally {
      clearInterval(timer); run.removeAttribute("aria-busy");
      run.disabled = missing.length > 0;
    }
  });
}

// -- Action cards (owner 2026-10-15) ----------------------------------------
// One component for "the Agent asks, the person decides": a title, a
// before -> after table or a preview body, the reason, effects and buttons
// whose labels and actions come from the server (Apply/Cancel now; Allow,
// Allow for this conversation, Deny or Send, Keep as draft, Cancel next).
// The server keeps the pending record and decides; the card is redrawn
// from its answer, with the outcome in place.

function openCardLink(link) {
  if (link.view === "installed" && link.asset) {
    activeCapabilityKind = link.capability_kind || "workflows";
    activeCapabilityFilter = "all";
    activeCapabilityKey = "installed:" + link.asset;
  }
  selectPrimaryTab(link.view).then(() => {
    const target = link.anchor ? el(link.anchor) : null;
    if (target) target.scrollIntoView({block: "start"});
  });
}

function renderActionCard(card, onDecided) {
  const box = document.createElement("div");
  box.className = "action-card" + (card.status === "pending" ? "" : " closed");
  box.dataset.cardId = card.card_id; box.dataset.status = card.status;
  box.setAttribute("role", "group"); box.setAttribute("aria-label", card.title);
  const heading = document.createElement("h3"); heading.append(text(card.title));
  box.append(heading);
  if (card.rows && card.rows.length) {
    const diff = document.createElement("table"); diff.className = "card-diff";
    const head = diff.createTHead().insertRow();
    for (const label of ["Setting", "Now", "After"]) {
      const cell = document.createElement("th"); cell.scope = "col";
      cell.append(text(label)); head.append(cell);
    }
    const body = diff.createTBody();
    for (const row of card.rows) {
      const line = body.insertRow();
      const name = document.createElement("th"); name.scope = "row";
      name.append(text(row.label)); line.append(name);
      const before = line.insertCell(); before.className = "before";
      before.append(text(row.before || "(empty)"));
      const after = line.insertCell(); after.append(text(row.after || "(empty)"));
    }
    box.append(diff);
  }
  if (card.preview) {
    const preview = document.createElement("pre"); preview.className = "card-preview";
    preview.append(text(card.preview)); box.append(preview);
  }
  if (card.reason) {
    const reason = document.createElement("p"); reason.className = "card-reason";
    reason.append(text("Why: " + card.reason)); box.append(reason);
  }
  if (card.effects && card.effects.length) {
    const effects = document.createElement("ul"); effects.className = "card-effects";
    for (const effect of card.effects) {
      const item = document.createElement("li"); item.append(text(effect));
      effects.append(item);
    }
    box.append(effects);
  }
  const status = document.createElement("p"); status.className = "card-status";
  status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  const expired = card.status === "pending" && card.expires_at
    && Date.parse(card.expires_at) <= Date.now();
  if (card.status === "pending") {
    const actions = document.createElement("div"); actions.className = "card-actions";
    for (const button of card.buttons || []) {
      const press = document.createElement("button"); press.type = "button";
      press.dataset.action = button.action;
      press.className = button.style === "primary" ? "go"
        : button.style === "danger" ? "danger" : "";
      press.append(text(button.label));
      press.disabled = !!expired;
      press.addEventListener("click", async () => {
        for (const other of actions.querySelectorAll("button")) other.disabled = true;
        press.setAttribute("aria-busy", "true");
        status.className = "card-status"; status.textContent = button.label + "\u2026";
        try {
          const decided = await call("/api/cards/decide",
            {card_id: card.card_id, action: button.action});
          if (decided.card) {
            box.replaceWith(renderActionCard(decided.card, onDecided));
          } else {
            status.className = "card-status bad";
            status.textContent = decided.message || decided.code;
          }
          if (onDecided) await onDecided(decided);
        } catch (failure) {
          status.className = "card-status bad"; status.textContent = failure.message;
          for (const other of actions.querySelectorAll("button")) other.disabled = false;
        } finally { press.removeAttribute("aria-busy"); }
      });
      actions.append(press);
    }
    box.append(actions);
    status.textContent = expired ? "Expired: ask the Agent again."
      : (card.status_label || "") + (card.expires_at
        ? " until " + new Date(card.expires_at).toLocaleTimeString() : "");
  } else {
    status.className = "card-status" + (card.outcome_ok === true ? " good"
      : card.outcome_ok === false ? " bad" : "");
    status.textContent = (card.status_label || card.status)
      + (card.outcome ? ": " + card.outcome : "");
  }
  box.append(status);
  if (card.link) {
    const open = document.createElement("button"); open.type = "button";
    open.className = "link-button card-link"; open.append(text(card.link.label));
    open.addEventListener("click", () => openCardLink(card.link));
    box.append(open);
  }
  return box;
}

async function loadPendingCards() {
  const holder = el("pending-cards");
  const listed = await call("/api/cards");
  holder.replaceChildren();
  el("pending-cards-heading").hidden = !listed.cards.length;
  for (const card of listed.cards) {
    holder.append(renderActionCard(card, () => loadPendingCards().catch(() => {})));
  }
}

// -- Draft install cards (owner 2026-10-16) ----------------------------------
// After a turn that drafted or revised a Workflow or Skill, the answer shows
// its install card: Install (the press is the approval), Run once to try
// (read-only Workflows) and Not now (the draft stays in Capabilities). After
// Install the Workflow's run form opens under the card.

let openInstallForm = null;

async function draftCardDecided(session, messageId, decided) {
  if (!decided || !decided.card) return;
  if (decided.card.status === "installed") {
    openInstallForm = messageId;
    assetsReady = loadAssets();
    await assetsReady.catch(() => {});
  }
  if (decided.card.status !== "pending" && session === activeConversation) {
    await loadConversations(session);
  }
}

// -- Approvals (G4): only the owner's button runs or installs ---------------

async function renderApprovals(session) {
  const listed = await call("/api/approvals?session_id=" + encodeURIComponent(session));
  if (session !== activeConversation) return;
  for (const old of log.querySelectorAll(".approval-card")) old.remove();
  for (const item of listed.approvals) {
    const card = document.createElement("div"); card.className = "approval-card";
    card.dataset.approvalId = item.approval_id;
    const title = document.createElement("strong");
    title.textContent = item.kind === "install" ? "安裝請求" : "執行請求";
    const summary = document.createElement("p"); summary.textContent = item.summary;
    const approve = document.createElement("button"); approve.type = "button";
    approve.className = "approve"; approve.textContent = "核准";
    const reject = document.createElement("button"); reject.type = "button";
    reject.className = "reject"; reject.textContent = "拒絕";
    const note = document.createElement("span"); note.className = "approval-note";
    const decide = async (decision) => {
      approve.disabled = reject.disabled = true;
      note.textContent = decision === "approve" ? "執行中…" : "";
      try {
        const done = await call("/api/approvals/decide",
          {approval_id: item.approval_id, decision: decision});
        if (!done.ok) throw new Error(done.code || "approval failed");
        await loadConversations(session);
      } catch (failure) {
        note.textContent = failure.message; approve.disabled = reject.disabled = false;
      }
    };
    approve.addEventListener("click", () => decide("approve"));
    reject.addEventListener("click", () => decide("reject"));
    card.append(title, summary, approve, reject, note);
    log.append(card);
  }
}

// -- Turn groups ----------------------------------------------------------

const RATINGS = [["up", "\u{1F44D}", "\u6709\u5e6b\u52a9"],
  ["down", "\u{1F44E}", "\u6c92\u5e6b\u52a9"], ["neutral", "\u2796", "\u666e\u901a"]];
let replyTarget = null;

function turnBlock(asked, replyQuestion, files, session) {
  const block = document.createElement("div");
  block.className = "turn"; block.tabIndex = 0;
  block.setAttribute("role", "group");
  block.setAttribute("aria-label", "\u5c0d\u8a71\uff1a" + asked);
  if (replyQuestion !== null && replyQuestion !== undefined) {
    const ref = document.createElement("div");
    ref.className = "turn-reply-ref";
    ref.append(text("\u21a9 \u56de\u8986\uff1a"
      + (replyQuestion || "\u5148\u524d\u7684\u5c0d\u8a71")));
    block.append(ref);
  }
  const line = document.createElement("div");
  line.className = "asked"; line.append(text("> " + asked));
  const said = document.createElement("div");
  said.className = "said waiting"; said.append(text("working\u2026"));
  block.append(line);
  if (files && files.length && session && files.every(file => file.path)) {
    // Stored attachments open in the viewer like an answer's files.
    const chips = fileChips(session, files);
    chips.classList.add("asked-files");
    block.append(chips);
  } else if (files && files.length) {
    const attached = document.createElement("div");
    attached.className = "asked-files";
    attached.append(text("\ud83d\udcce " + files.map(file => file.filename).join("\u3001")));
    block.append(attached);
  }
  block.append(said);
  return block;
}

function ratingLabel(rating) {
  const found = RATINGS.find(item => item[0] === rating);
  return found ? found[1] + " " + found[2] : rating;
}

function feedbackSummary(feedback) {
  const line = document.createElement("div");
  line.className = "turn-feedback-saved";
  line.append(text("\u4f60\u7684\u8a55\u50f9\uff1a" + ratingLabel(feedback.rating)
    + (feedback.note ? " \u2014 " + feedback.note : "")));
  return line;
}

function attachTurnControls(block, question, message) {
  block.dataset.messageId = message.message_id;
  const tools = document.createElement("div");
  tools.className = "turn-tools";
  for (const [rating, icon, label] of RATINGS) {
    const button = document.createElement("button");
    button.type = "button"; button.append(text(icon));
    button.title = label; button.setAttribute("aria-label", "\u8a55\u50f9\uff1a" + label);
    button.setAttribute("aria-pressed",
      String(!!message.feedback && message.feedback.rating === rating));
    button.dataset.rating = rating;
    button.addEventListener("click", () => openFeedback(block, message, rating));
    tools.append(button);
  }
  const reply = document.createElement("button");
  reply.type = "button"; reply.append(text("\u21a9"));
  reply.title = "\u56de\u8986\u9019\u6bb5\u5c0d\u8a71";
  reply.setAttribute("aria-label", reply.title);
  reply.addEventListener("click", () => chooseReply(message.message_id, question));
  tools.append(reply);
  // 「存成筆記」 (accumulated memory M3): the whole answer, in one click.
  const keep = document.createElement("button");
  keep.type = "button"; keep.className = "save-note"; keep.append(text("\ud83d\udcdd"));
  keep.title = "存成筆記"; keep.setAttribute("aria-label", "存成筆記");
  keep.addEventListener("click", () => saveNote(block, message.message_id, ""));
  tools.append(keep);
  block.append(tools);
  // Which model answered (owner 2026-10-22): the session's own choice.
  if (message.model) {
    const used = document.createElement("div"); used.className = "answer-model";
    used.append(text("模型：" + message.model));
    block.append(used);
  }
  // 「為什麼」 (accumulated memory M5): what of the person's memory this answer
  // used, each linked to where it can be edited or deleted on the memory page.
  if ((message.preferences_used || []).length || (message.memory_used || []).length) {
    block.append(whyButton(message.message_id));
  }
  const area = document.createElement("div");
  area.className = "turn-feedback-area";
  if (message.feedback) area.append(feedbackSummary(message.feedback));
  block.append(area);
  block.addEventListener("contextmenu", event => {
    event.preventDefault();
    showTurnMenu(event.clientX, event.clientY, block, question, message);
  });
}

const WHY_KINDS = {preference: "偏好", person: "聯絡人", sync: "整理進度", note: "筆記"};

function whyButton(messageId) {
  const wrap = document.createElement("div"); wrap.className = "why";
  const button = document.createElement("button");
  button.type = "button"; button.className = "why-btn"; button.append(text("為什麼？"));
  button.title = "這則回答用了哪些偏好與記憶";
  button.setAttribute("aria-expanded", "false");
  const box = document.createElement("div"); box.className = "why-box"; box.hidden = true;
  button.addEventListener("click", async () => {
    const open = box.hidden;
    box.hidden = !open; button.setAttribute("aria-expanded", String(open));
    if (!open || box.dataset.loaded) return;
    box.replaceChildren(text("讀取中…"));
    let reply;
    try {
      reply = await call("/api/memory/why?session_id=" + encodeURIComponent(activeConversation)
        + "&message_id=" + encodeURIComponent(messageId));
    } catch (failure) { reply = {ok: false, message: failure.message}; }
    box.replaceChildren();
    if (!reply.ok) { box.append(text(reply.message || reply.code)); return; }
    box.dataset.loaded = "1";
    box.append(text("這則回答用到："));
    const list = document.createElement("ul");
    for (const item of reply.items) {
      const row = document.createElement("li");
      const kind = document.createElement("span"); kind.className = "why-kind";
      kind.append(text((WHY_KINDS[item.kind] || item.kind) + "："));
      row.append(kind, text(item.label + (item.detail ? "（" + item.detail + "）" : "")));
      if (item.gone) {
        const gone = document.createElement("span"); gone.className = "why-gone";
        gone.append(text("（已刪除）")); row.append(gone);
      } else {
        const link = document.createElement("button"); link.type = "button";
        link.append(text(item.kind === "sync" ? "到同步進度" : "到記憶頁修改或刪除"));
        link.addEventListener("click", () => memGoto(item).catch((failure) =>
          memNotice({ok: false, message: failure.message})));
        row.append(link);
      }
      list.append(row);
    }
    box.append(list);
  });
  wrap.append(button, box);
  return wrap;
}

function openFeedback(block, message, rating) {
  const area = block.querySelector(".turn-feedback-area");
  const form = document.createElement("div");
  form.className = "turn-feedback";
  const row = document.createElement("div");
  row.className = "turn-feedback-row";
  row.append(text("\u8a55\u50f9\uff1a" + ratingLabel(rating)
    + "\uff08\u53ef\u88dc\u5145\u539f\u56e0\uff0c\u9078\u586b\uff09"));
  const note = document.createElement("textarea");
  note.maxLength = 2000; note.setAttribute("aria-label", "\u8a55\u50f9\u539f\u56e0");
  note.value = message.feedback && message.feedback.note ? message.feedback.note : "";
  const actions = document.createElement("div");
  actions.className = "turn-feedback-row";
  const save = document.createElement("button");
  save.type = "button"; save.append(text("\u5132\u5b58"));
  const cancel = document.createElement("button");
  cancel.type = "button"; cancel.className = "link-button"; cancel.append(text("\u53d6\u6d88"));
  const status = document.createElement("span");
  status.setAttribute("role", "status");
  actions.append(save, cancel, status);
  form.append(row, note, actions);
  const previous = [...area.childNodes];
  area.replaceChildren(form);
  note.focus();
  cancel.addEventListener("click", () => area.replaceChildren(...previous));
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      const saved = await call("/api/conversations/feedback", {
        session_id: activeConversation, message_id: message.message_id,
        rating: rating, note: note.value,
      });
      message.feedback = saved.feedback;
      area.replaceChildren(feedbackSummary(saved.feedback));
      for (const button of block.querySelectorAll(".turn-tools button[data-rating]")) {
        button.setAttribute("aria-pressed", String(button.dataset.rating === rating));
      }
    } catch (failure) {
      save.disabled = false;
      status.replaceChildren(text("\u7121\u6cd5\u5132\u5b58\uff1a" + failure.message));
    }
  });
}

function chooseReply(messageId, question) {
  replyTarget = {message_id: messageId, question: question};
  el("reply-chip-text").replaceChildren(text("\u21a9 \u56de\u8986\uff1a" + question));
  el("reply-chip").hidden = false;
  closeTurnMenu();
  field.focus();
}

function clearReply() {
  replyTarget = null;
  el("reply-chip").hidden = true;
  el("reply-chip-text").replaceChildren();
}

function closeTurnMenu() {
  const menu = el("turn-menu");
  if (menu) { menu.hidden = true; menu.replaceChildren(); }
}

function showTurnMenu(x, y, block, question, message) {
  const menu = el("turn-menu");
  const items = [
    ["\u56de\u8986\u9019\u6bb5\u5c0d\u8a71", () => chooseReply(message.message_id, question)],
    ["\u8907\u88fd\u56de\u8986", () => { closeTurnMenu();
      if (navigator.clipboard) navigator.clipboard.writeText(message.text); }],
    ["存成筆記", () => { closeTurnMenu(); saveNote(block, message.message_id, ""); }],
    ...RATINGS.map(([rating, icon, label]) => [
      "\u8a55\u50f9\uff1a" + icon + " " + label,
      () => { closeTurnMenu(); openFeedback(block, message, rating); },
    ]),
  ];
  menu.replaceChildren();
  for (const [label, action] of items) {
    const button = document.createElement("button");
    button.type = "button"; button.setAttribute("role", "menuitem");
    button.append(text(label));
    button.addEventListener("click", action);
    menu.append(button);
  }
  menu.style.left = Math.min(x, window.innerWidth - 190) + "px";
  menu.style.top = Math.min(y, window.innerHeight - 220) + "px";
  menu.hidden = false;
  menu.querySelector("button").focus();
}

// -- end Turn groups

// -- Notes (accumulated memory M3): an answer, or a selection of it, in one
// click. The server takes the text from the stored answer; a selection must
// be in it. Only this press saves; 「復原」 undoes it.

// 委派紀錄 (multi-agent V1): under an answer whose turn delegated, a closed
// block with one entry per sub-agent: profile, status, a short summary, its
// files (opened in the file viewer) and runs, and its tokens.
const DELEGATION_LABELS = {succeeded: "完成", needs_input: "需要資訊",
  awaiting_approval: "等待確認", failed: "失敗"};

function delegationTokens(tokens) {
  const calls = (tokens && tokens.model_calls) || 0;
  if (!tokens || (tokens.input == null && tokens.output == null)) {
    return calls + " 次模型呼叫";
  }
  return "tokens " + (tokens.input || 0).toLocaleString() + " / "
    + (tokens.output || 0).toLocaleString() + "（" + calls + " 次呼叫）";
}

function delegationRecord(session, records) {
  const box = document.createElement("details");
  box.className = "delegation-record";
  const head = document.createElement("summary");
  head.append(text("委派紀錄（" + records.length + " 個子代理）"));
  const list = document.createElement("ol");
  for (const record of records) {
    const item = document.createElement("li"); item.className = "dr-item";
    const line = document.createElement("div"); line.className = "dr-head";
    const profile = document.createElement("span"); profile.className = "dr-profile";
    profile.append(text(record.profile || ""));
    const status = document.createElement("span");
    status.className = "dr-status " + record.status;
    status.append(text(DELEGATION_LABELS[record.status] || record.status));
    const meta = document.createElement("span"); meta.className = "dr-meta";
    meta.append(text(Number(record.elapsed_s || 0).toFixed(1) + " s · "
      + delegationTokens(record.tokens)
      + (record.failure_code && record.status === "failed" ? " · " + record.failure_code : "")));
    line.append(profile, status, meta);
    item.append(line);
    const said = record.question ? "需要：" + record.question : record.summary;
    if (said) {
      const summary = document.createElement("p"); summary.className = "dr-summary";
      summary.append(text(said));
      item.append(summary);
    }
    if (record.host_note) {
      const note = document.createElement("p"); note.className = "dr-note";
      note.append(text("Host 註記：" + record.host_note));
      item.append(note);
    }
    const artifacts = record.artifacts || [];
    if (artifacts.length) {
      const row = document.createElement("div"); row.className = "dr-artifacts";
      for (const artifact of artifacts) {
        if (artifact.kind === "file" && artifact.path) {
          row.append(fileChip(session, {filename: artifact.name, path: artifact.path}));
        } else {
          const run = document.createElement("span"); run.className = "dr-run";
          run.append(text(artifact.id + " " + artifact.name
            + (artifact.status ? "（" + artifact.status + "）" : "")));
          row.append(run);
        }
      }
      item.append(row);
    }
    list.append(item);
  }
  box.append(head, list);
  return box;
}

// 「存成筆記」 under a 結果摘要 (task result summaries, owner 2026-10-25): the
// summary's text becomes one note; only this press saves.
function summaryNoteButton(summaryId) {
  const row = document.createElement("div");
  row.className = "summary-note";
  const button = document.createElement("button");
  button.type = "button"; button.className = "link-button summary-note-save";
  button.append(text("結果摘要存成筆記"));
  const said = document.createElement("span");
  said.setAttribute("role", "status");
  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const saved = await call("/api/memory/task-summaries/note", {id: summaryId});
      said.replaceChildren(text(" " + (saved.message || saved.code)));
      if (!saved.ok) button.disabled = false;
    } catch (failure) {
      button.disabled = false; said.replaceChildren(text(" " + failure.message));
    }
  });
  row.append(button, said);
  return row;
}

async function saveNote(block, messageId, selection) {
  const area = block.querySelector(".turn-feedback-area") || block;
  const line = document.createElement("div");
  line.className = "note-saved"; line.setAttribute("role", "status");
  line.append(text(selection ? "存選取內容中…" : "存成筆記中…"));
  area.append(line);
  try {
    const saved = await call("/api/memory/notes/save",
      {session_id: activeConversation, message_id: messageId, selection: selection || ""});
    line.replaceChildren(text(saved.message || saved.code));
    if (!saved.ok) { line.classList.add("bad"); return; }
    if (saved.change_id) {
      const undo = document.createElement("button");
      undo.type = "button"; undo.className = "link-button note-undo"; undo.append(text("復原"));
      undo.addEventListener("click", async () => {
        undo.disabled = true;
        try {
          const undone = await call("/api/memory/undo",
            {kind: "note", change_id: saved.change_id});
          line.replaceChildren(text(undone.ok ? "已復原：這則筆記沒有保留。"
            : (undone.message || undone.code)));
        } catch (failure) {
          undo.disabled = false; line.append(text(" " + failure.message));
        }
      });
      line.append(text(" "), undo);
    }
  } catch (failure) {
    line.classList.add("bad");
    line.replaceChildren(text("無法存成筆記：" + failure.message));
  }
}

const selectionNote = document.createElement("button");
selectionNote.type = "button"; selectionNote.id = "save-selection"; selectionNote.hidden = true;
selectionNote.append(text("存選取內容"));
document.body.append(selectionNote);
let selectionTarget = null;
let selectionTimer = 0;

function selectedAnswer() {
  const chosen = window.getSelection();
  if (!chosen || chosen.isCollapsed || !chosen.rangeCount) return null;
  const range = chosen.getRangeAt(0);
  const node = (item) => item.nodeType === 1 ? item : item.parentElement;
  const start = node(range.startContainer), end = node(range.endContainer);
  const said = start && start.closest(".said");
  if (!said || !end || end.closest(".said") !== said) return null;
  const block = said.closest(".turn");
  if (!block || !block.dataset.messageId) return null;
  const picked = chosen.toString().trim();
  return picked ? {block: block, range: range, text: picked} : null;
}

function placeSelectionNote() {
  const found = selectedAnswer();
  selectionTarget = found;
  if (!found) { selectionNote.hidden = true; return; }
  const box = found.range.getBoundingClientRect();
  selectionNote.style.left = Math.max(8, Math.min(box.left, window.innerWidth - 150)) + "px";
  selectionNote.style.top = Math.max(8, Math.min(box.bottom + 6, window.innerHeight - 48)) + "px";
  selectionNote.hidden = false;
}

document.addEventListener("selectionchange", () => {
  clearTimeout(selectionTimer);
  selectionTimer = setTimeout(placeSelectionNote, 120);
});
// Keep the selection while the button is pressed.
selectionNote.addEventListener("mousedown", (event) => event.preventDefault());
selectionNote.addEventListener("click", () => {
  const found = selectionTarget;
  selectionNote.hidden = true;
  if (!found) return;
  saveNote(found.block, found.block.dataset.messageId, found.text);
  const chosen = window.getSelection();
  if (chosen) chosen.removeAllRanges();
});

// What the server found in stored messages for the words in the search box:
// these join the titles the box filters at once.
let searchHits = [], searchTimer = 0;

async function searchStoredConversations() {
  const query = el("session-search").value.trim();
  clearTimeout(searchTimer);
  if (!query) { searchHits = []; renderSessionList(); return; }
  searchTimer = setTimeout(async () => {
    const found = await call("/api/conversations/search?q=" + encodeURIComponent(query))
      .catch(() => ({results: []}));
    if (el("session-search").value.trim() !== query) return;  // the words changed meanwhile
    searchHits = found.results || [];
    renderSessionList();
  }, 250);
}

function renderSessionList() {
  const query = el("session-search").value.trim().toLowerCase();
  const titled = conversationRows.filter((item) =>
    [item.title, item.backend].filter(Boolean).join(" ").toLowerCase().includes(query));
  const shown = new Set(titled.map((item) => item.session_id));
  const hits = new Map(searchHits.map((item) => [item.session_id, item]));
  const visible = [...titled.map((item) => hits.get(item.session_id) || item),
    ...searchHits.filter((item) => !shown.has(item.session_id))];
  el("session-count").textContent = String(conversationRows.length);
  const buttons = visible.map((item) => {
    const button = document.createElement("button"); button.type = "button";
    button.className = "session-item"; button.setAttribute("role", "option");
    button.setAttribute("aria-selected", String(item.session_id === activeConversation));
    const title = document.createElement("strong"); title.append(text(item.title));
    const detail = document.createElement("small");
    detail.append(text(item.messages + " messages · "
      + (item.source === "telegram" ? "Telegram" : item.backend)
      + (sessionBusy(item.session_id) ? " · 執行中" : "")));
    button.append(title, detail);
    if (item.snippet) {
      const found = document.createElement("small");
      found.className = "session-snippet"; found.append(text(item.snippet));
      button.append(found);
    }
    button.addEventListener("click", async () => {
      selectPrimaryTab("ask");
      // Switch at once, so a message typed during the reload goes here.
      activeConversation = item.session_id; log.replaceChildren();
      renderPendingTurns(item.session_id);
      try { await loadChat(item.session_id); field.focus(); }
      catch (failure) { showBootError(failure); }
    });
    const row = document.createElement("div"); row.className = "session-row";
    const remove = document.createElement("button"); remove.type = "button";
    remove.className = "session-delete-button"; remove.append(text("\u{1F5D1}"));
    remove.title = "刪除此 session";
    remove.setAttribute("aria-label", remove.title + "：" + item.title);
    remove.addEventListener("click", () => deleteSession(item.session_id, item.title));
    row.append(button, remove);
    return row;
  });
  if (buttons.length) el("session-list").replaceChildren(...buttons);
  else {
    const empty = document.createElement("div"); empty.className = "empty";
    empty.append(text("No sessions match this search."));
    el("session-list").replaceChildren(empty);
  }
}

async function deleteSession(sessionId, title) {
  if (!confirm("永久刪除 session「" + title + "」？")) return;
  try {
    const deleted = await call("/api/conversations/delete", {session_id: sessionId});
    if (!deleted.ok) throw new Error(deleted.code || "deletion_failed");
    if (sessionId === activeConversation) activeConversation = "";
    searchHits = searchHits.filter((item) => item.session_id !== sessionId);
    await loadChat(activeConversation || undefined);
  } catch (failure) { showBootError(failure); }
}

async function loadConversations(selectId) {
  let listed = await call("/api/conversations"
    + (selectId ? "?session_id=" + encodeURIComponent(selectId) : ""));
  // Never opens on a Telegram conversation by itself: those are only read.
  const own = listed.conversations.filter((item) => item.source !== "telegram");
  if (!listed.conversations.length || (!selectId && !own.length)) {
    const created = await call("/api/conversations", {});
    selectId = created.conversation.session_id;
    listed = await call("/api/conversations?session_id=" + encodeURIComponent(selectId));
  }
  conversationRows = listed.conversations;
  activeConversation = selectId
    || listed.conversations.find((item) => item.source !== "telegram").session_id;
  if (!listed.selected || listed.selected.session_id !== activeConversation) {
    listed = await call("/api/conversations?session_id="
      + encodeURIComponent(activeConversation));
  }
  renderSessionList();
  renderConversation(listed.selected);
  activeConversationPublic = !!(listed.selected
    && listed.selected.data_classification === "PUBLIC");
  activeConversationMessages = listed.selected ? listed.selected.messages.length : 0;
  const backend = el("conversation-backend");
  const selectedBackend = listed.selected ? listed.selected.backend : "gateway";
  const requested = [...backend.options].find(option => option.value === selectedBackend);
  activeBackend = requested ? selectedBackend : (backend.options[0] || {}).value || "gateway";
  backend.value = activeBackend; renderBackendState();
  const readOnly = !!(listed.selected && listed.selected.source === "telegram");
  el("ask").hidden = readOnly;
  el("read-only-note").hidden = !readOnly;
  backend.disabled = readOnly;
  send.disabled = false;
  loadAgentSession().catch(() => {});
  loadConversationModels().catch(() => {});
}

// The composer's model (owner 2026-10-21): what the configured Gateway
// serves, per conversation, applied from the next message.
let modelChoices = null, modelChoicesFor = "";

async function loadConversationModels() {
  const session = activeConversation;
  if (modelChoicesFor !== session) { modelChoices = null; renderModelControl(); }
  const listed = await call("/api/conversations/models?session_id="
    + encodeURIComponent(session || ""));
  if (session !== activeConversation) return;
  modelChoices = listed; modelChoicesFor = session; renderModelControl();
}

function modelStatusText(data) {
  if (data.unavailable) return data.unavailable + " is not served now · choose another";
  const from = {conversation: "This conversation", default: "Your default"}[data.selected_from]
    || "Settings default";
  return data.source === "gateway" ? from + " · from the next message"
    : "Gateway list unavailable · Settings model";
}

function renderModelControl() {
  const select = el("conversation-model"), fixed = el("model-readonly");
  const state = el("model-state"), data = modelChoices;
  const showFixed = (label, status) => {
    select.hidden = true; fixed.hidden = false;
    fixed.textContent = label; state.textContent = status;
  };
  if (activeBackend !== "gateway") {
    const status = backendStatuses.get(activeBackend);
    showFixed("Model: chosen by " + (status ? status.label : "this backend"), "");
    return;
  }
  if (!data) { showFixed("Reading models…", ""); return; }
  if (!data.ok) { showFixed("No model configured", "Set one in Settings"); return; }
  if (data.models.length < 2 && !data.unavailable) {
    showFixed(data.models[0].label, data.source === "gateway"
      ? "The only model the Gateway serves" : "Gateway list unavailable · Settings model");
    return;
  }
  const options = data.models.map(item => [item.id,
    item.label + (item.id === data.configured ? " · " + item.status : "")]);
  if (data.unavailable) options.unshift([data.unavailable, data.unavailable + " · not served now"]);
  const signature = JSON.stringify(options);
  if (select.dataset.signature !== signature) {
    select.replaceChildren();
    for (const [value, label] of options) {
      const option = document.createElement("option");
      option.value = value; option.textContent = label;
      option.disabled = value === data.unavailable;
      select.append(option);
    }
    select.dataset.signature = signature;
  }
  select.value = data.unavailable || data.selected;
  select.hidden = false; fixed.hidden = true;
  const busy = !!activeConversation && sessionBusy(activeConversation);
  select.disabled = busy;
  state.textContent = busy ? "Locked while the answer runs" : modelStatusText(data);
}

el("conversation-model").addEventListener("change", async () => {
  const select = el("conversation-model"), chosen = select.value;
  if (!activeConversation || !modelChoices || !modelChoices.ok) return;
  const session = activeConversation;
  select.disabled = true; el("model-state").textContent = "Saving…";
  try {
    const saved = await call("/api/conversations/model", {session_id: session, model: chosen});
    if (!saved.ok) throw new Error(saved.code);
    if (session === activeConversation) {
      Object.assign(modelChoices, {selected: chosen, selected_from: "conversation",
        unavailable: null});
    }
  } catch (failure) {
    renderModelControl();
    el("model-state").textContent = "Not changed: " + failure.message;
    return;
  }
  renderModelControl();
});

async function loadBackends() {
  const data = await call("/api/backends"), select = el("conversation-backend");
  backendStatuses = new Map(data.backends.map(item => [item.name, item]));
  select.replaceChildren();
  for (const backend of data.backends) {
    const option = document.createElement("option"); option.value = backend.name;
    const suffix = backend.available ? "" : (backend.selectable ? " · sign in" : " · install");
    option.textContent = backend.label + suffix;
    option.title = backend.detail; select.append(option);
  }
  if ([...select.options].some(option => option.value === activeBackend)) {
    select.value = activeBackend;
  }
  renderBackendState();
}

function renderBackendState() {
  const status = backendStatuses.get(el("conversation-backend").value || activeBackend);
  el("backend-state").textContent = status
    ? (activeConversationPublic ? "PUBLIC session · " : "") + status.detail
    : "Reading backend status…";
  el("backend-settings").hidden = !(status && status.name === "gateway" && !status.available);
}

function showBackendAuthentication(status) {
  pendingBackend = status.name;
  el("backend-auth-title").textContent = "Connect " + status.label;
  el("backend-auth-detail").textContent = status.selectable
    ? "Authentication runs in a separate local window. "
      + "Complete the provider sign-in, then return here."
    : status.detail + ". Install the official CLI, then refresh this page.";
  el("backend-auth-result").textContent = status.detail;
  el("backend-auth-start").hidden = status.action !== "authenticate";
  el("backend-auth-check").hidden = !status.selectable;
  el("backend-auth-dialog").showModal();
}

async function chooseBackend(name) {
  const status = backendStatuses.get(name);
  if (!status) return;
  if (!status.selectable) {
    el("conversation-backend").value = activeBackend; showBackendAuthentication(status); return;
  }
  if (name !== "gateway" && status.authentication !== "ready") {
    el("conversation-backend").value = activeBackend; showBackendAuthentication(status); return;
  }
  if (name !== "gateway" && !activeConversationPublic) {
    pendingPublicBackend = name;
    el("backend-public-result").textContent = "";
    el("conversation-backend").value = activeBackend;
    el("backend-public-dialog").showModal();
    return;
  }
  const selected = await call("/api/conversations/backend", {
    session_id: activeConversation, backend: name,
  });
  if (!selected.ok) throw new Error(selected.code);
  activeBackend = name;
  activeConversationPublic = selected.conversation.data_classification === "PUBLIC";
  el("conversation-backend").value = name; renderBackendState(); renderAgentModeLine();
  renderModelControl();
}

async function loadChat(selectId) {
  await loadBackends();
  await loadConversations(selectId);
}

el("session-search").addEventListener("input", () => {
  renderSessionList();
  searchStoredConversations();
});
el("conversation-backend").addEventListener("change", async () => {
  try { await chooseBackend(el("conversation-backend").value); }
  catch (failure) { el("conversation-backend").value = activeBackend; showBootError(failure); }
});
el("backend-settings").addEventListener("click", () => selectPrimaryTab("settings"));
el("backend-public-cancel").addEventListener("click", () => {
  pendingPublicBackend = ""; el("backend-public-dialog").close();
});
el("backend-public-start").addEventListener("click", async () => {
  const button = el("backend-public-start"); button.disabled = true;
  el("backend-public-result").textContent = "Preparing PUBLIC session…";
  try {
    if (activeConversationMessages) {
      const created = await call("/api/conversations", {});
      await loadChat(created.conversation.session_id);
    }
    const selected = await call("/api/conversations/backend", {
      session_id: activeConversation, backend: pendingPublicBackend, public_context: true,
    });
    if (!selected.ok) throw new Error(selected.code);
    activeBackend = pendingPublicBackend;
    activeConversationPublic = true;
    pendingPublicBackend = "";
    // Show the new backend at once; the backend list reload below is slow,
    // and a stale "Gateway" entry would swallow the user's switch back.
    el("conversation-backend").value = activeBackend; renderBackendState();
    renderModelControl();
    el("backend-public-result").textContent = "";
    el("backend-public-dialog").close();
    await loadChat(activeConversation); field.focus();
  } catch (failure) {
    el("backend-public-result").textContent = "Cannot start: " + failure.message;
  } finally { button.disabled = false; }
});
el("backend-auth-cancel").addEventListener("click", () => {
  pendingBackend = ""; el("backend-auth-dialog").close();
});
el("backend-auth-start").addEventListener("click", async () => {
  const button = el("backend-auth-start"); button.disabled = true;
  try {
    const started = await call("/api/backends/authenticate", {backend: pendingBackend});
    el("backend-auth-result").textContent = started.status === "ready"
      ? "This backend is already authenticated." : "Sign-in opened. Complete it, then check again.";
  } catch (failure) {
    el("backend-auth-result").textContent = "Authentication did not start: " + failure.message;
  } finally { button.disabled = false; }
});
el("backend-auth-check").addEventListener("click", async () => {
  await loadBackends();
  const status = backendStatuses.get(pendingBackend);
  if (status && status.available) {
    await chooseBackend(pendingBackend); pendingBackend = ""; el("backend-auth-dialog").close();
  } else {
    el("backend-auth-result").textContent = status ? status.detail : "Backend status unavailable.";
  }
});
// New session: Send waits until the new session has loaded (#233); a message
// sent meanwhile went into the previous one. Once the server has made it, the
// page is bound to the new session id at once.
let startingSession = false;
el("new-conversation").addEventListener("click", async () => {
  if (startingSession) return;
  startingSession = true; send.disabled = true; send.setAttribute("aria-busy", "true");
  try {
    const created = await call("/api/conversations", {});
    selectPrimaryTab("ask");
    activeConversation = created.conversation.session_id; log.replaceChildren();
    await loadChat(created.conversation.session_id); field.focus();
  } catch (failure) { showBootError(failure); }
  finally {
    startingSession = false; send.removeAttribute("aria-busy");
    send.disabled = uploadingFiles > 0 || !activeConversation;
  }
});

el("reply-chip-clear").addEventListener("click", () => { clearReply(); field.focus(); });
document.addEventListener("click", (event) => {
  const menu = el("turn-menu");
  if (!menu.hidden && !menu.contains(event.target)) closeTurnMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeTurnMenu();
});

// -- Turn queues ------------------------------------------------------------
// Each session sends its turns strictly in order; different sessions run at
// the same time. Queued, running and failed turns stay visible across reloads.

const pendingTurns = new Map();
const sessionChains = new Map();

function pendingFor(sessionId) {
  if (!pendingTurns.has(sessionId)) pendingTurns.set(sessionId, []);
  return pendingTurns.get(sessionId);
}

function sessionBusy(sessionId) {
  return (pendingTurns.get(sessionId) || []).some(entry => entry.state !== "failed");
}

function showPendingState(entry) {
  if (!entry.said) return;
  entry.said.className = "said" + (entry.state === "failed" ? " bad" : " waiting");
  if (entry.state === "working" && entry.progress) {
    if (!entry.said.querySelector(".turn-progress")) {
      entry.said.replaceChildren(turnProgressView());
    }
    showTurnProgress(entry.said.querySelector(".turn-progress"), entry.progress);
    return;
  }
  entry.said.replaceChildren(text(entry.state === "queued" ? "排隊中…"
    : entry.state === "working" ? "working…"
      : "The request did not finish: " + entry.error));
}

// -- Live turn progress (owner 2026-10-19) ------------------------------------
// While a turn runs, its progress is read every second and drawn in place of
// "working…": the Harness phases, the recent tool lines, and the tool count
// and time against their limits. The server sends names and numbers only.

const STEP_MARKS = ["①", "②", "③", "④", "⑤"];
const TOOL_MARKS = {
  running: ["…", ""], succeeded: ["✓", "good"], failed: ["✗", "bad"],
  waiting: ["?", "wait"], allowed: ["✓", "good"], refused: ["✗", "bad"],
};

function clockText(seconds) {
  const whole = Math.max(0, Math.floor(seconds || 0));
  return Math.floor(whole / 60) + ":" + String(whole % 60).padStart(2, "0");
}

function turnProgressView() {
  const box = document.createElement("div"); box.className = "turn-progress";
  const status = document.createElement("p"); status.className = "tp-status";
  status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite");
  const steps = document.createElement("ol"); steps.className = "tp-steps";
  steps.setAttribute("aria-label", "Harness 階段");
  const agents = document.createElement("ul"); agents.className = "tp-agents";
  agents.setAttribute("aria-label", "子代理"); agents.hidden = true;
  const tools = document.createElement("ul"); tools.className = "tp-tools";
  tools.setAttribute("aria-label", "最近的工具");
  const meter = document.createElement("p"); meter.className = "tp-meter";
  box.append(status, steps, agents, tools, meter);
  return box;
}

// Delegated sub-agents (multi-agent V1): one line each, with the profile, a
// short objective, its status, tool count and time. Older pages without the
// lines fall back to the running count.
function showSubAgents(list, progress) {
  const shown = progress.delegations || [];
  list.hidden = !shown.length;
  list.replaceChildren(...shown.map(agent => {
    const item = document.createElement("li");
    item.className = "tp-agent " + agent.status;
    const head = document.createElement("div"); head.className = "tp-agent-head";
    const name = document.createElement("span"); name.className = "tp-agent-name";
    name.textContent = agent.profile; name.title = agent.profile;
    const state = document.createElement("span"); state.className = "tp-agent-state";
    state.textContent = (agent.status === "running" ? "… " : "") + agent.label;
    head.append(name, state);
    const goal = document.createElement("p"); goal.className = "tp-agent-goal";
    goal.textContent = agent.objective || ""; goal.title = agent.objective || "";
    const meter = document.createElement("p"); meter.className = "tp-agent-meter";
    meter.textContent = "工具 " + agent.tool_count + (agent.tool_cap ? "/" + agent.tool_cap : "")
      + " · " + clockText(agent.elapsed_s) + (agent.read_only ? " · 只讀" : "");
    item.append(head, goal, meter);
    return item;
  }));
}

function progressStatus(progress) {
  if (progress.delegations_running) {
    return "子代理執行中（" + progress.delegations_running + " 個）…";
  }
  const harness = progress.harness;
  if (harness && !harness.done) {
    const step = harness.steps.find(item => item.state === "active");
    return harness.label + "：" + (step ? step.label : harness.phase)
      + (harness.retry ? "（第 " + (harness.retry + 1) + " 輪）" : "") + "…";
  }
  const running = (progress.tools || []).filter(tool => tool.status === "running"
    || tool.status === "waiting");
  if (running.length) {
    const last = running[running.length - 1];
    return (last.status === "waiting" ? "等待你確認：" : "執行中：") + last.name;
  }
  // The Harness passed its checks: what is left is writing the answer (#233).
  if (harness && harness.done && harness.phase === "validated") return "整理回答中…";
  return progress.tool_count ? "思考下一步…" : "working…";
}

function showTurnProgress(box, progress) {
  if (!box) return;
  const status = progressStatus(progress);
  const quiet = box.querySelector(".tp-status");
  if (quiet.textContent !== status) quiet.textContent = status;
  const steps = box.querySelector(".tp-steps"), harness = progress.harness;
  steps.hidden = !harness;
  steps.replaceChildren(...(harness ? harness.steps.map((step, index) => {
    const item = document.createElement("li"); item.className = step.state;
    let label = (STEP_MARKS[index] || "") + " " + step.label;
    if (step.state === "active" && harness.retry && step.stage !== "plan") {
      label += "（第 " + (harness.retry + 1) + " 輪）";
    }
    label += step.state === "done" ? " ✓" : step.state === "active" ? "…"
      : step.state === "failed" ? " ✗" : step.state === "stopped" ? " ⏸" : "";
    item.textContent = label;
    return item;
  }) : []));
  showSubAgents(box.querySelector(".tp-agents"), progress);
  const tools = box.querySelector(".tp-tools"), recent = (progress.tools || []).slice(-4);
  tools.hidden = !recent.length;
  tools.replaceChildren(...recent.map(tool => {
    const [mark, tone] = TOOL_MARKS[tool.status] || ["·", ""];
    const item = document.createElement("li");
    const sign = document.createElement("span"); sign.className = "tp-mark " + tone;
    sign.textContent = mark; sign.setAttribute("aria-label", tool.status);
    const name = document.createElement("span"); name.className = "tp-name";
    name.textContent = tool.name; name.title = tool.name;
    const time = document.createElement("span"); time.className = "tp-time";
    time.textContent = (tool.duration_s || 0).toFixed(1) + " s";
    item.append(sign, name, time);
    return item;
  }));
  const parts = [];
  if (progress.tool_cap) parts.push("工具 " + progress.tool_count + "/" + progress.tool_cap);
  else if (progress.tool_count) parts.push("工具 " + progress.tool_count);
  parts.push(clockText(progress.elapsed_s)
    + (progress.time_limit_s ? " / " + clockText(progress.time_limit_s) : ""));
  box.querySelector(".tp-meter").textContent = parts.join(" · ");
}

function watchTurnProgress(session, entry) {
  let stopped = false, timer = null;
  const tick = async () => {
    if (stopped) return;
    try {
      const read = await call("/api/conversations/progress?session_id="
        + encodeURIComponent(session));
      if (!stopped && read.progress && entry.state === "working") {
        entry.progress = read.progress;
        if (session === activeConversation) showPendingState(entry);
      }
    } catch (failure) { /* the next tick tries again */ }
    if (!stopped) timer = setTimeout(tick, 1000);
  };
  timer = setTimeout(tick, 400);
  return {stop() { stopped = true; if (timer) clearTimeout(timer); entry.progress = null; }};
}

function renderPendingTurns(sessionId) {
  for (const entry of pendingTurns.get(sessionId) || []) {
    entry.said = turn(entry.asked, entry.replyQuestion, entry.files);
    showPendingState(entry);
  }
}

// -- Agent mode (owner 2026-10-15) --------------------------------------------
// While an agent-mode turn runs, its approval cards are fetched every 1.5 s
// and drawn under the waiting turn; the run waits on the server until the
// person presses. After the turn the answer keeps them (action_cards).

const AGENT_BACKENDS = ["claude_code", "copilot", "codex"];
let agentSession = null;

function agentModeOn() {
  return !!(agentSession && agentSession.backends && agentSession.backends[activeBackend]);
}

function watchAgentCards(session, entry) {
  let stopped = false, timer = null;
  const tick = async () => {
    if (stopped) return;
    try {
      if (session === activeConversation && agentModeOn() && entry.said) {
        const listed = await call("/api/cards?session_id=" + encodeURIComponent(session));
        let holder = entry.said.parentNode.querySelector(".agent-live-cards");
        if (!holder) {
          holder = document.createElement("div"); holder.className = "agent-live-cards";
          holder.setAttribute("aria-live", "polite");
          entry.said.parentNode.append(holder);
        }
        const shown = new Set([...holder.querySelectorAll(".action-card")]
          .map(node => node.dataset.cardId));
        for (const card of listed.cards) {
          if (!card.card_id.startsWith("pm-") && !card.card_id.startsWith("ml-")) continue;
          if (shown.has(card.card_id)) continue;
          holder.append(renderActionCard(card));
          log.scrollTop = log.scrollHeight;
        }
      }
    } catch (failure) { /* the next tick tries again */ }
    if (!stopped) timer = setTimeout(tick, 1500);
  };
  timer = setTimeout(tick, 300);
  return {stop() { stopped = true; if (timer) clearTimeout(timer); }};
}

function renderAgentModeLine() {
  const line = el("agent-mode-line");
  const relevant = AGENT_BACKENDS.includes(activeBackend) && agentSession;
  line.hidden = !relevant;
  if (!relevant) return;
  const note = (agentSession.notes || {})[activeBackend];
  if (note) {
    el("agent-mode-state").textContent = note; el("agent-folders").hidden = true; return;
  }
  if (!agentModeOn()) {
    el("agent-mode-state").textContent = "Text only: agent mode is off for this backend "
      + "(Settings > Agent mode)."; el("agent-folders").hidden = true; return;
  }
  const extra = (agentSession.read_folders || []).length;
  el("agent-mode-state").textContent = "Agent mode · works in " + agentSession.folder
    + (extra ? " · reads " + extra + " more folder" + (extra > 1 ? "s" : "") : "");
  el("agent-folders").hidden = false;
}

async function loadAgentSession() {
  agentSession = null;
  if (activeConversation) {
    try {
      const view = await call("/api/agent-mode/session?session_id="
        + encodeURIComponent(activeConversation));
      if (view.ok) agentSession = view;
    } catch (failure) { agentSession = null; }
  }
  renderAgentModeLine();
}

el("agent-folders").addEventListener("click", () => {
  if (!agentSession) return;
  el("agent-folder").value = agentSession.folder || "";
  el("agent-read-folders").value = (agentSession.read_folders || []).join("\n");
  el("agent-folders-result").textContent = "";
  el("agent-folders-dialog").showModal();
});
el("agent-folders-cancel").addEventListener("click", () => el("agent-folders-dialog").close());
el("agent-folders-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = el("agent-folders-result"), button = el("agent-folders-save");
  button.disabled = true; result.textContent = "Saving…";
  try {
    const saved = await call("/api/agent-mode/session", {
      session_id: activeConversation, folder: el("agent-folder").value.trim(),
      read_folders: el("agent-read-folders").value.split("\n").map(x => x.trim())
        .filter(Boolean)});
    if (!saved.ok) { result.textContent = saved.message || saved.code; return; }
    agentSession = saved; renderAgentModeLine(); el("agent-folders-dialog").close();
  } catch (failure) {
    result.textContent = "Not saved: " + failure.message;
  } finally { button.disabled = false; }
});

function agentLines(value) { return value.split("\n").map(x => x.trim()).filter(Boolean); }

function renderAgentModeSettings(data) {
  const box = el("agent-mode-backends");
  box.className = ""; box.replaceChildren();
  for (const backend of data.backends) {
    const row = document.createElement("label"); row.className = "agent-mode-backend";
    const check = document.createElement("input"); check.type = "checkbox";
    check.dataset.backend = backend.name; check.checked = backend.enabled;
    check.disabled = !backend.relay;
    const words = document.createElement("span");
    words.append(text(backend.label + (backend.relay ? ": agent mode" : "")));
    if (backend.note) {
      const why = document.createElement("p"); why.className = "note";
      why.append(text(backend.note)); words.append(why);
    }
    row.append(check, words); box.append(row);
  }
  const settings = data.settings, mail = settings.mail;
  el("agent-mode-root").value = settings.default_root;
  el("agent-mode-root").placeholder = data.default_root;
  el("agent-mode-root-note").textContent = "Each conversation gets its own folder inside it. "
    + "It must be under " + [data.default_root, ...data.coding_roots].join(" or ") + ".";
  el("agent-mail-folders").value = mail.folders.join("\n");
  el("agent-mail-days").value = mail.max_days;
  el("agent-mail-senders").value = mail.excluded_senders.join("\n");
  el("agent-mail-excluded").value = mail.excluded_folders.join("\n");
}

async function loadAgentModeSettings() {
  renderAgentModeSettings(await call("/api/agent-mode"));
}

el("agent-mode-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = el("agent-mode-result"), button = el("agent-mode-save");
  const body = {default_root: el("agent-mode-root").value.trim(), mail: {
    folders: agentLines(el("agent-mail-folders").value),
    max_days: Number(el("agent-mail-days").value || 30),
    excluded_senders: agentLines(el("agent-mail-senders").value),
    excluded_folders: agentLines(el("agent-mail-excluded").value)}};
  for (const check of el("agent-mode-backends").querySelectorAll("input[data-backend]")) {
    body[check.dataset.backend] = check.checked;
  }
  button.disabled = true; result.textContent = "Saving…";
  try {
    const saved = await call("/api/agent-mode/settings", body);
    if (!saved.ok) { result.textContent = saved.message || saved.code; return; }
    renderAgentModeSettings(saved); result.textContent = "Saved. New turns use it.";
    loadAgentSession().catch(() => {});
  } catch (failure) {
    result.textContent = "Not saved: " + failure.message;
  } finally { button.disabled = false; }
});

// -- end Turn queues

// -- Attachments (owner 2026-10-08) ----------------------------------------
// Files are uploaded to the open conversation as they are chosen, dropped or
// pasted, shown as chips, and sent with the next message by their ids.

const ATTACHMENT_TYPES = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".csv",
  ".html", ".htm", ".txt", ".json", ".yaml", ".yml", ".md", ".zip"];
const MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024, MAX_ATTACHMENTS = 10;
let attachedFiles = [], uploadingFiles = 0, attachmentSession = "";

function readyFiles() { return attachedFiles.filter(file => file.file_id); }

function clearAttachments() { attachedFiles = []; renderAttachments(); }

function renderAttachments() {
  const box = el("attachment-chips");
  box.replaceChildren();
  box.hidden = attachedFiles.length === 0;
  for (const file of attachedFiles) {
    const chip = document.createElement("span");
    chip.className = "attachment-chip" + (file.error ? " bad" : "");
    const label = document.createElement("span");
    label.textContent = file.error ? file.filename + "：" + file.error
      : file.file_id ? file.filename : file.filename + "（上傳中…）";
    chip.title = label.textContent;
    const remove = document.createElement("button");
    remove.type = "button"; remove.textContent = "✕";
    remove.setAttribute("aria-label", "移除 " + file.filename);
    remove.addEventListener("click", () => {
      attachedFiles = attachedFiles.filter(item => item !== file); renderAttachments();
    });
    chip.append(label, remove);
    box.append(chip);
  }
  send.disabled = uploadingFiles > 0 || !activeConversation;
}

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function addFiles(files) {
  if (!activeConversation) return;
  if (attachmentSession !== activeConversation) { attachedFiles = []; }
  attachmentSession = activeConversation;
  for (const file of files) {
    const entry = {filename: file.name || "pasted.png", file_id: null, error: null};
    const suffix = (entry.filename.match(/\.[^.]+$/) || [""])[0].toLowerCase();
    if (attachedFiles.length >= MAX_ATTACHMENTS) entry.error = "一則訊息最多 10 個檔案";
    else if (!ATTACHMENT_TYPES.includes(suffix)) entry.error = "不支援的檔案類型";
    else if (file.size > MAX_ATTACHMENT_BYTES) entry.error = "超過 25 MB";
    attachedFiles.push(entry);
    renderAttachments();
    if (entry.error) continue;
    uploadingFiles += 1; renderAttachments();
    try {
      const saved = await call("/api/attachments", {
        session_id: attachmentSession, filename: entry.filename, data: await readAsBase64(file),
      });
      if (saved.ok) Object.assign(entry, saved.attachment);
      else entry.error = saved.code || "上傳失敗";
    } catch (failure) {
      entry.error = failure.code || failure.message;
    } finally {
      uploadingFiles -= 1; renderAttachments();
    }
  }
}

el("attach").addEventListener("click", () => el("attach-input").click());
el("attach-input").addEventListener("change", (event) => {
  const chosen = Array.from(event.target.files || []);
  event.target.value = "";
  addFiles(chosen);
});
form.addEventListener("dragover", (event) => {
  if (Array.from(event.dataTransfer.types || []).includes("Files")) {
    event.preventDefault(); form.classList.add("dropping");
  }
});
form.addEventListener("dragleave", () => form.classList.remove("dropping"));
form.addEventListener("drop", (event) => {
  form.classList.remove("dropping");
  const dropped = Array.from(event.dataTransfer.files || []);
  if (dropped.length) { event.preventDefault(); addFiles(dropped); }
});
field.addEventListener("paste", (event) => {
  const pasted = Array.from(event.clipboardData ? event.clipboardData.files : []);
  if (!pasted.length) return;
  event.preventDefault();
  const stamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
  addFiles(pasted.map((file, index) => file.name && file.name !== "image.png" ? file
    : new File([file], "pasted-" + stamp + (index ? "-" + index : "") + ".png",
      {type: file.type || "image/png"})));
});

// -- Voice input (docs/phases/VOICE_INPUT.md) -------------------------------
// The microphone records here; the host turns the recording into text, which
// goes into the message box to read, edit and send. Speaking sends nothing.

let voiceSettings = null, voiceRecorder = null, voiceChunks = [], voiceStarted = 0;
let voiceTimer = null, voiceTranscript = null;

function voiceStatus(text) {
  const status = el("mic-status");
  status.textContent = text; status.hidden = !text;
}

async function loadVoice() {
  try { voiceSettings = await call("/api/voice"); } catch (failure) { voiceSettings = null; }
  el("mic").hidden = !(voiceSettings && voiceSettings.enabled
    && navigator.mediaDevices && window.MediaRecorder);
}

function voiceClock() {
  const seconds = Math.floor((Date.now() - voiceStarted) / 1000);
  const limit = voiceSettings.max_seconds;
  const shown = (n) => Math.floor(n / 60) + ":" + String(n % 60).padStart(2, "0");
  voiceStatus("錄音中 " + shown(seconds) + " / " + shown(limit) + "（再按一次停止）");
  if (seconds >= limit) stopVoice();
}

async function startVoice() {
  if (!activeConversation) return;
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({audio: true}); }
  catch (failure) { voiceStatus("無法使用麥克風：請允許這個網頁使用麥克風。"); return; }
  const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"]
    .find(candidate => MediaRecorder.isTypeSupported(candidate)) || "";
  const recorder = new MediaRecorder(stream, type ? {mimeType: type} : {});
  const session = activeConversation;
  voiceRecorder = recorder; voiceChunks = [];
  recorder.addEventListener("dataavailable", (event) => {
    if (event.data && event.data.size) voiceChunks.push(event.data);
  });
  recorder.addEventListener("stop", () => {
    stream.getTracks().forEach(track => track.stop());
    sendVoice(session, (recorder.mimeType || type || "audio/webm").split(";")[0]);
  });
  voiceStarted = Date.now();
  recorder.start(250);
  el("mic").setAttribute("aria-pressed", "true"); el("mic").textContent = "■";
  voiceClock(); voiceTimer = setInterval(voiceClock, 500);
}

function stopVoice() {
  clearInterval(voiceTimer); voiceTimer = null;
  el("mic").setAttribute("aria-pressed", "false"); el("mic").textContent = "🎤";
  if (voiceRecorder && voiceRecorder.state !== "inactive") voiceRecorder.stop();
}

async function sendVoice(session, mimeType) {
  const blob = new Blob(voiceChunks, {type: mimeType}); voiceChunks = [];
  const duration = Date.now() - voiceStarted;
  voiceStatus("🎤 轉文字中…"); el("mic").disabled = true;
  try {
    const heard = await call("/api/voice/transcribe", {
      session_id: session, mime_type: mimeType, duration_ms: duration,
      data: await readAsBase64(blob),
    });
    if (!heard.ok) {
      voiceStatus(heard.message || "語音轉文字失敗，請再試一次或改用文字。");
      return;
    }
    if (session !== activeConversation) { voiceStatus(""); return; }
    const text = heard.transcript.text;
    field.value = field.value.trim() ? field.value.trimEnd() + " " + text : text;
    field.dispatchEvent(new Event("input"));
    voiceTranscript = {id: heard.transcript.id, session: session};
    voiceStatus("語音轉文字，請確認內容後送出。");
    field.focus();
  } catch (failure) {
    voiceStatus((failure.payload && failure.payload.message) || failure.message);
  } finally { el("mic").disabled = false; }
}

el("mic").addEventListener("click", () => {
  if (voiceRecorder && voiceRecorder.state === "recording") stopVoice(); else startVoice();
});
loadVoice();

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (uploadingFiles > 0 || startingSession) return;
  const files = readyFiles();
  const asked = field.value.trim() || (files.length ? "請看附件。" : "");
  if (!asked || !activeConversation) return;
  field.value = "";
  // A message that came from the microphone names its transcript (§3.2).
  const spoken = voiceTranscript && voiceTranscript.session === activeConversation
    ? voiceTranscript.id : null;
  voiceTranscript = null; voiceStatus("");
  el("command-palette").hidden = true;
  const session = activeConversation, replying = replyTarget;
  clearReply();
  clearAttachments();
  const entry = {
    asked: asked, replyQuestion: replying ? replying.question : null,
    replyTo: replying ? replying.message_id : null, state: "queued", said: null,
    files: files,
  };
  const queue = pendingFor(session);
  if (queue.every(item => item.state === "failed")) entry.state = "working";
  queue.push(entry);
  entry.said = turn(entry.asked, entry.replyQuestion, entry.files);
  showPendingState(entry);
  renderSessionList(); renderModelControl();
  const run = async () => {
    entry.state = "working"; showPendingState(entry); renderSessionList();
    if (session === activeConversation) renderModelControl();
    let answer = null;
    avatarWorking(1);
    const watching = watchAgentCards(session, entry);
    const progressing = watchTurnProgress(session, entry);
    try {
      const completed = await call("/api/conversations/turn", {
        session_id: session, message: asked,
        ...(entry.replyTo ? {reply_to: entry.replyTo} : {}),
        ...(entry.files.length ? {attachments: entry.files.map(file => file.file_id)} : {}),
        ...(spoken ? {voice_transcript: spoken} : {}),
      });
      answer = completed.answer;
      queue.splice(queue.indexOf(entry), 1);
    } catch (failure) {
      entry.state = "failed"; entry.error = failure.message;
      showPendingState(entry);
    } finally { avatarWorking(-1); }
    if (session === activeConversation) renderModelControl();
    watching.stop(); progressing.stop();
    try {
      if (session === activeConversation) await loadConversations(session);
      else { conversationRows = (await call("/api/conversations")).conversations;
        renderSessionList(); }
      if (answer && answer.backend && answer.backend.code === "backend_authentication_failed") {
        await loadBackends();
      }
    } catch (failure) { showBootError(failure); }
    if (session === activeConversation) log.scrollTop = log.scrollHeight;
  };
  const chain = (sessionChains.get(session) || Promise.resolve()).then(run, run);
  sessionChains.set(session, chain);
  field.focus();
});

// -- The person's avatar (owner 2026-10-07) -------------------------------
// Frame 1 shows at rest; while any turn runs, the other frames play in a loop
// and frame 1 returns when the last turn ends.

let avatarCharacters = [], avatarChoice = null, avatarTimer = null;
let avatarFrame = 0, workingTurns = 0;
const AVATAR_FRAME_MS = 180;
const calmMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function chosenAvatar() {
  return avatarCharacters.find(character => character.id === avatarChoice) || null;
}

function showAvatar() {
  const character = chosenAvatar(), stage = el("avatar-stage"), picture = el("agent-avatar");
  if (!character) { stage.hidden = true; return; }
  stage.hidden = false;
  picture.alt = character.name;
  const moving = workingTurns > 0 && character.frames.length > 1;
  picture.src = moving
    ? character.frames[1 + (avatarFrame % (character.frames.length - 1))]
    : character.frames[0];
}

function avatarWorking(change) {
  workingTurns = Math.max(0, workingTurns + change);
  if (workingTurns > 0 && avatarTimer === null && !calmMotion.matches) {
    avatarFrame = 0;
    avatarTimer = setInterval(() => { avatarFrame += 1; showAvatar(); }, AVATAR_FRAME_MS);
  } else if (workingTurns === 0 && avatarTimer !== null) {
    clearInterval(avatarTimer); avatarTimer = null;
  }
  showAvatar();
}

function renderAvatarChoices() {
  const box = el("avatar-choices");
  box.textContent = "";
  for (const character of [{id: null, name: "None", frames: []}, ...avatarCharacters]) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "avatar-choice";
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(character.id === avatarChoice));
    if (character.frames.length) {
      const picture = document.createElement("img");
      picture.src = character.frames[0]; picture.alt = "";
      button.appendChild(picture);
    }
    const label = document.createElement("span");
    label.textContent = character.name;
    button.appendChild(label);
    button.addEventListener("click", () => chooseAvatar(character.id));
    box.appendChild(button);
  }
}

async function chooseAvatar(id) {
  const result = el("avatar-result");
  result.textContent = "Saving avatar…";
  try {
    avatarChoice = (await call("/api/preferences", {avatar: id})).preferences.avatar;
    result.textContent = id ? "Saved for you." : "No avatar.";
  } catch (failure) {
    result.textContent = "The avatar was not saved: " + failure.message;
  }
  showAvatar(); renderAvatarChoices();
}

async function loadAvatars() {
  try {
    avatarCharacters = (await call("/api/avatars")).characters;
    avatarChoice = (await call("/api/preferences")).preferences.avatar;
  } catch (failure) {
    // A missing avatar never stops the page; the name still shows.
    avatarCharacters = []; avatarChoice = null;
  }
  showAvatar(); renderAvatarChoices();
}

// -- The listings ---------------------------------------------------------

async function loadAbout() {
  const about = await call("/api/about");
  el("agent-name").textContent = about.name;
  el("agent-introduction").textContent = about.introduction;
  const where = [];
  where.push("as " + about.actor);
  where.push("on " + about.bridge_id);
  if (about.namespace) where.push("namespace " + about.namespace);
  el("who").textContent = where.join(" \u00b7 ");
  if (!about.namespace) {
    field.placeholder = "no namespace is configured; set it in host.json";
  }
}

let slashCommands = [];
function renderCommandPalette() {
  const palette = el("command-palette"), query = field.value.trim().toLowerCase();
  const visible = slashCommands.filter(item => !query || item.invocation.startsWith(query));
  const buttons = visible.map(item => {
    const button = document.createElement("button"); button.type = "button";
    button.setAttribute("role", "option");
    const command = document.createElement("code"); command.textContent = item.invocation;
    const description = document.createElement("span"); description.textContent = item.description;
    button.append(command, description);
    button.addEventListener("click", () => {
      field.value = item.invocation; palette.hidden = true; field.focus();
    });
    return button;
  });
  palette.replaceChildren(...buttons);
  palette.hidden = !field.value.trim().startsWith("/") || !buttons.length;
}

async function loadSlashCommands() {
  slashCommands = (await call("/api/commands")).commands;
  renderCommandPalette();
}

field.addEventListener("input", renderCommandPalette);
field.addEventListener("keydown", event => {
  if (event.key === "Escape") el("command-palette").hidden = true;
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault(); form.requestSubmit();
  }
});

// Drafts (owner 2026-10-08) live in the Capabilities list beside what is
// installed (owner 2026-10-15): "Draft - not installed" with Install, where the
// owner's press is the approval. Built with text nodes only.
let capabilityDrafts = [];

async function loadDrafts() {
  const listed = await call("/api/drafts");
  capabilityDrafts = listed.drafts.map((item) => {
    const slash = item.asset.indexOf("/"), at = item.asset.lastIndexOf("@");
    return Object.assign({}, item, {namespace: item.asset.slice(0, slash),
      name: item.asset.slice(slash + 1, at), version: item.asset.slice(at + 1)});
  });
  return capabilityDrafts;
}

async function loadExternalApprovals() {
  const box = el("external-approvals");
  const listed = await call("/api/approvals/external");
  if (!listed.approvals.length) {
    box.className = "empty"; box.textContent = "目前沒有外部提交。"; return;
  }
  box.className = ""; box.replaceChildren();
  const labels = {install: "安裝 Workflow", install_skill: "安裝 Skill", run: "執行 Workflow"};
  for (const item of listed.approvals) {
    const card = document.createElement("div"); card.className = "approval-card";
    card.dataset.approvalId = item.approval_id;
    const title = document.createElement("strong");
    title.textContent = (labels[item.kind] || item.kind) + "（" + item.source + "）";
    const summary = document.createElement("p"); summary.textContent = item.summary;
    const details = document.createElement("details");
    const label = document.createElement("summary"); label.textContent = "完整內容";
    const body = document.createElement("pre"); body.textContent = item.detail;
    details.append(label, body);
    const approve = document.createElement("button"); approve.type = "button";
    approve.className = "approve"; approve.textContent = "核准";
    const reject = document.createElement("button"); reject.type = "button";
    reject.className = "reject"; reject.textContent = "拒絕";
    const note = document.createElement("span"); note.className = "approval-note";
    const decide = async (decision) => {
      approve.disabled = reject.disabled = true;
      note.textContent = decision === "approve" ? "處理中…" : "";
      try {
        const done = await call("/api/approvals/decide",
          {approval_id: item.approval_id, decision: decision});
        if (!done.ok) throw new Error(done.code || "approval failed");
        await loadExternalApprovals();
      } catch (failure) {
        note.textContent = failure.message; approve.disabled = reject.disabled = false;
      }
    };
    approve.addEventListener("click", () => decide("approve"));
    reject.addEventListener("click", () => decide("reject"));
    card.append(title, summary, details, approve, reject, note);
    box.append(card);
  }
}

async function loadAssets() {
  loadExternalApprovals().catch(() => {});
  const [assets] = await Promise.all([call("/api/assets"),
    loadDrafts().catch(() => { capabilityDrafts = []; })]);
  return renderAssets(assets);
}

// Draws the Capabilities list from an /api/assets answer, also when an
// action's own response carries it: no second request and no reload.
function renderAssets(assets) {
  el("profiles").replaceChildren(table(
    ["Asset", "State", "Action", "What it is"], assets.profiles,
    (p) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "go";
      button.disabled = p.active; button.textContent = p.active ? "Active" : "Activate";
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          const result = await call("/api/profiles/activate", {profile: {
            namespace: p.namespace, name: p.name, version: p.version}});
          if (!result.ok) throw new Error(result.code);
          alert("Profile selected. Restart the Agent to apply it.");
          await loadAssets();
        } catch (failure) {
          alert("Profile was not activated: " + failure.message); button.disabled = false;
        }
      });
      return [p.namespace + "/" + p.name + "@" + p.version,
              tag(p.active, "active", "installed"), button, p.description];
    }));
  el("runs").replaceChildren(table(
    ["Run", "Workflow", "Status", "Asked by"], assets.runs,
    (r) => [r.run_id, r.workflow, r.status, r.actor]));
  const target = el("workflow-target");
  target.replaceChildren();
  for (const workflow of assets.workflows) {
    const option = document.createElement("option");
    option.value = JSON.stringify({namespace: workflow.namespace, name: workflow.name,
      version: workflow.version});
    option.dataset.inputContract = workflow.input_contract;
    option.textContent = workflow.namespace + "/" + workflow.name + "@" + workflow.version;
    target.append(option);
  }
  target.disabled = assets.workflows.length === 0;
  el("workflow-run").disabled = assets.workflows.length === 0;
  installedAssets = Object.assign({applications: [], disabled: []}, assets);
  showWorkflowContract();
  const knowledgeTarget = el("knowledge-target");
  knowledgeTarget.replaceChildren();
  for (const knowledge of assets.knowledge) {
    const option = document.createElement("option");
    option.value = JSON.stringify({namespace: knowledge.namespace, name: knowledge.name,
      version: knowledge.version});
    option.dataset.domain = knowledge.domain;
    option.textContent = knowledge.namespace + "/" + knowledge.name + "@" + knowledge.version;
    knowledgeTarget.append(option);
  }
  knowledgeTarget.disabled = assets.knowledge.length === 0;
  const knowledgeSkill = el("knowledge-skill");
  knowledgeSkill.replaceChildren(new Option("Existing query path", ""));
  for (const skill of assets.skills) {
    if (!skill.knowledge_harness_selectable) continue;
    const option = document.createElement("option");
    option.value = JSON.stringify({namespace: skill.namespace, name: skill.name,
      version: skill.version});
    option.textContent = skill.namespace + "/" + skill.name + "@" + skill.version;
    knowledgeSkill.append(option);
  }
  el("knowledge-ask").disabled = assets.knowledge.length === 0;
  showKnowledgeDomain();
  renderCapabilityBrowser();
  return assets;
}

let installedAssets = {skills: [], workflows: [], knowledge: [], extensions: [],
  applications: [], disabled: []};
let activeCapabilityKind = "skills";
let activeCapabilityKey = "";
let activeCapabilityFilter = "all";
let freshCapabilityKey = "";
// The kinds a person can install from a draft, switch off and remove here.
const SHELF_KINDS = {skills: "skill", workflows: "workflow"};

function capabilityKey(item) {
  return item.namespace + "/" + item.name + "@" + item.version;
}

function capabilityRowKey(row) {
  return row.state + ":" + capabilityKey(row.item);
}

function capabilityTitle(item, kind) {
  return kind === "skills" && item.alias ? item.alias : item.name;
}

// Drafts first, then what is installed, then what is switched off.
function capabilityRows(kind) {
  const installed = installedAssets[kind].map((item) => ({state: "installed", item: item}));
  const shelf = SHELF_KINDS[kind];
  if (!shelf) return installed;
  const drafts = capabilityDrafts.filter((item) => item.kind === shelf)
    .map((item) => ({state: "draft", item: item}));
  const off = (installedAssets.disabled || []).filter((item) => item.kind === shelf)
    .map((item) => ({state: "disabled", item: item}));
  return drafts.concat(installed, off);
}

function appendMeta(container, rows) {
  const list = document.createElement("dl"); list.className = "meta-grid";
  for (const [label, value] of rows) {
    const term = document.createElement("dt"); term.append(text(label));
    const detail = document.createElement("dd");
    if (value instanceof Node) detail.append(value); else detail.append(text(value || "—"));
    list.append(term, detail);
  }
  container.append(list);
}

function setCapabilityNotice(message, bad) {
  const box = el("capability-notice");
  box.textContent = message || ""; box.classList.toggle("bad", !!bad);
}

// A named confirmation before anything is discarded or removed.
function confirmAsset(title, detail, confirmLabel) {
  const dialog = el("asset-confirm");
  el("asset-confirm-title").textContent = title;
  el("asset-confirm-detail").textContent = detail;
  el("asset-confirm-go").textContent = confirmLabel;
  dialog.returnValue = "";
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"),
      {once: true});
    dialog.showModal();
    el("asset-confirm-cancel").focus();
  });
}

async function capabilityAction(button, busyText, request) {
  for (const other of document.querySelectorAll(
    "#capability-list button, #capability-detail-content button")) other.disabled = true;
  button.setAttribute("aria-busy", "true");
  setCapabilityNotice(busyText, false);
  let done;
  try {
    done = await request();
  } catch (failure) {
    done = {ok: false, message: failure.message};
  }
  setCapabilityNotice(done.message || (done.ok ? "Done." : done.code || "It did not work."),
    !done.ok);
  button.removeAttribute("aria-busy");
  if (done.platform) renderPlatform(done.platform);
  if (done.assets) renderAssets(done.assets);
  else { try { await loadAssets(); } catch (_) { renderCapabilityBrowser(); } }
  return done;
}

function installDraft(draft, button) {
  return capabilityAction(button, "Installing " + draft.asset + "…", async () => {
    const done = await call("/api/drafts/install", {candidate_id: draft.candidate_id});
    if (!done.ok) return {ok: false, message: "Not installed: " + (done.code || "install failed")};
    const installedAs = done.installed_as || draft.asset;
    activeCapabilityKey = "installed:" + installedAs;
    return {ok: true, message: "Installed " + installedAs + ". " + (done.note || "")};
  });
}

async function discardDraft(draft, button) {
  const confirmed = await confirmAsset("Discard the draft " + draft.asset + "?",
    "The draft “" + (draft.title || draft.asset) + "” is deleted. Installed "
      + "versions are not affected.", "Discard draft");
  if (!confirmed) { button.focus(); return null; }
  return capabilityAction(button, "Discarding " + draft.asset + "…", async () => {
    const done = await call("/api/drafts/delete", {candidate_id: draft.candidate_id});
    return done.ok ? {ok: true, message: "Draft " + draft.asset + " discarded."}
      : {ok: false, message: "Not discarded: " + (done.code || "delete failed")};
  });
}

function switchAsset(kind, item, enabled, button) {
  const key = capabilityKey(item);
  return capabilityAction(button, (enabled ? "Switching on " : "Switching off ") + key + "…",
    async () => {
      const done = await call("/api/assets/switch",
        {kind: kind, asset: key, enabled: enabled});
      if (done.ok) activeCapabilityKey = (enabled ? "installed:" : "disabled:") + key;
      return done;
    });
}

async function removeAsset(kind, item, button) {
  const key = capabilityKey(item);
  const name = capabilityTitle(item, kind === "skill" ? "skills" : "workflows");
  const confirmed = await confirmAsset("Remove " + name + " from this Agent?",
    key + " moves to a dated folder under workspace\\removed (it is not deleted) and the "
      + "Agent stops offering it. To put it back, move the file back.",
    "Remove from this Agent");
  if (!confirmed) { button.focus(); return null; }
  return capabilityAction(button, "Removing " + key + "…",
    () => call("/api/assets/remove", {kind: kind, asset: key}));
}

function actionButton(label, className, handler) {
  const button = document.createElement("button"); button.type = "button";
  button.className = className; button.textContent = label;
  button.addEventListener("click", () => handler(button));
  return button;
}

function detailHead(content, title, key, badgeNodes) {
  const head = document.createElement("div"); head.className = "detail-head";
  const left = document.createElement("div");
  const heading = document.createElement("h3"); heading.append(text(title));
  const identity = document.createElement("div"); identity.className = "identity";
  identity.append(text(key));
  const badges = document.createElement("div"); badges.className = "badges";
  badges.append(...badgeNodes);
  left.append(heading, identity, badges);
  const actions = document.createElement("div"); actions.className = "detail-actions";
  head.append(left, actions);
  content.append(head);
  return {actions: actions, badges: badges};
}

function showDraftDetail(content, draft) {
  const state = tag(false, "", "Draft — not installed"); state.classList.add("draft");
  const head = detailHead(content, draft.title || draft.name, draft.asset, [state]);
  head.actions.append(
    actionButton("Install", "go", (button) => installDraft(draft, button)),
    actionButton("Discard draft", "btn danger", (button) => discardDraft(draft, button)));
  const description = document.createElement("p"); description.className = "detail-description";
  description.append(text(draft.description || "No description supplied."));
  const run = draft.last_run;
  content.append(description);
  appendMeta(content, [
    ["Made in", draft.source === "conversation" ? "a conversation" : draft.source],
    [draft.kind === "skill" ? "Commands" : "Steps", draft.steps.join(" → ")],
    ["Parameters", draft.parameters.join(", ") || "None"],
    ["Last run", run ? (run.result || run.status) + " (" + run.at + ")" : "Not run yet"],
    ["Updated", draft.updated_at]]);
  const note = document.createElement("p"); note.className = "note";
  note.append(text("Install is your approval; the Agent never installs a draft on its own. "
    + "A Workflow is usable at once, a Skill after the host restarts. Running it once is "
    + "not installing it."));
  const details = document.createElement("details");
  const label = document.createElement("summary"); label.textContent = "Full content";
  const body = document.createElement("pre"); body.className = "markdown-panel";
  body.textContent = draft.detail;
  details.append(label, body);
  content.append(note, details);
}

function showDisabledDetail(content, item, kind) {
  const state = tag(false, "", "Switched off");
  const head = detailHead(content, capabilityTitle(item, kind), capabilityKey(item), [state]);
  const shelf = SHELF_KINDS[kind];
  head.actions.append(
    actionButton("Switch on", "go", (button) => switchAsset(shelf, item, true, button)));
  appendRemove(head.actions, shelf, item);
  const description = document.createElement("p"); description.className = "detail-description";
  description.append(text(item.description || "No description supplied."));
  content.append(description);
  appendMeta(content, [["State", "Switched off: the Agent does not offer it"],
    ["Kept in", "assets\\" + shelf + "s\\disabled"]]);
}

function appendRemove(actions, shelf, item) {
  const remove = actionButton("Remove from this Agent", "btn danger",
    (button) => removeAsset(shelf, item, button));
  actions.append(remove);
  if (item.shipped) {
    remove.disabled = true;
    const why = document.createElement("p"); why.className = "note";
    why.append(text("Ships with AEP, so export-assets would bring it back; switch it off "
      + "instead."));
    actions.append(why);
  }
}

// Revise an installed Workflow from chat (owner 2026-10-19): a new session with
// the request typed in; the person edits and sends it. Nothing is sent here.
async function reviseInChat(item) {
  const key = capabilityKey(item);
  const created = await call("/api/conversations", {});
  await selectPrimaryTab("ask");
  await loadChat(created.conversation.session_id);
  field.value = "Revise the installed Workflow " + key + ": ";
  field.dispatchEvent(new Event("input"));
  field.focus();
  field.setSelectionRange(field.value.length, field.value.length);
}

function showCapabilityDetail(row, kind) {
  const content = el("capability-detail-content"); content.className = "";
  content.replaceChildren();
  el("workflow-action").hidden = true;
  el("workflow-settings").hidden = true;
  el("knowledge-action").hidden = true;
  if (!row) {
    content.className = "empty";
    content.append(text(kind === "applications"
      ? "Applications run independently and are discovered in the authenticated Shared Marketplace."
      : "Nothing here matches this search and filter."));
    return;
  }
  if (row.state === "draft") { showDraftDetail(content, row.item); return; }
  if (row.state === "disabled") { showDisabledDetail(content, row.item, kind); return; }
  const item = row.item;
  const head = detailHead(content, capabilityTitle(item, kind), capabilityKey(item),
    [tag(true, "installed", "")]);
  const badges = head.badges;
  const shelf = SHELF_KINDS[kind];
  if (kind === "workflows") {
    head.actions.append(actionButton("Revise in chat", "btn revise-in-chat",
      () => reviseInChat(item)));
  }
  if (shelf) {
    head.actions.append(actionButton("Switch off", "btn",
      (button) => switchAsset(shelf, item, false, button)));
    appendRemove(head.actions, shelf, item);
  }
  const description = document.createElement("p"); description.className = "detail-description";
  description.append(text(item.description || "No description supplied."));
  content.append(description);

  if (kind === "skills") {
    appendMeta(content, [["Alias", item.alias], ["Default command", item.default_command],
      ["Commands", item.commands.map((command) => command.invocation.trim()).join(", ")],
      ["Script tools", item.script_tools.length
        ? item.script_tools.map((script) => script.status
          + (script.runtime ? " · " + script.runtime + ": " + script.path : "")).join(", ")
        : "None declared"]]);
    const procedureTitle = document.createElement("h4");
    procedureTitle.append(text("SKILL.md"));
    const procedure = document.createElement("pre");
    procedure.className = "markdown-panel";
    procedure.append(text(item.procedure_markdown));
    content.append(procedureTitle, procedure);
    if (item.commands.length) {
      const actions = document.createElement("div"); actions.className = "inline-actions";
      for (const command of item.commands) {
        const button = document.createElement("button"); button.className = "go";
        button.type = "button"; button.textContent = "Ask " + command.invocation.trim();
        button.addEventListener("click", () => {
          field.value = command.invocation; selectPrimaryTab("ask"); field.focus();
        });
        actions.append(button);
      }
      content.append(actions);
    }
  } else if (kind === "workflows") {
    appendMeta(content, [["Steps", item.steps], ["Input contract", item.input_contract],
      ["Output contract", item.output_contract],
      ["Capabilities", item.capabilities.join(", ")],
      ["Parameter editor", item.parameters.editor === "fields"
        ? "Typed run fields" : "JSON object validated as " + item.parameters.input_contract]]);
    el("workflow-target").value = JSON.stringify({namespace: item.namespace, name: item.name,
      version: item.version});
    showWorkflowContract(); el("workflow-action").hidden = false;
    loadWorkflowSettings(item);
  } else if (kind === "knowledge") {
    appendMeta(content, [["Domain", item.domain], ["Owner", item.owner],
      ["Visibility", item.visibility], ["Location", item.location],
      ["Manifest vault reference", item.vault_ref]]);
    el("knowledge-target").value = JSON.stringify({namespace: item.namespace, name: item.name,
      version: item.version});
    showKnowledgeDomain(); el("knowledge-action").hidden = false;
  } else if (kind === "extensions") {
    badges.append(tag(item.state === "active", item.state, item.state));
    appendMeta(content, [["Runtime state", item.state + (item.code ? " (" + item.code + ")" : "")],
      ["Capabilities", item.capabilities.join(", ")], ["Publisher key", item.publisher_key_id],
      ["Activation gate", item.activation_gate], ["Lifecycle", item.lifecycle],
      ["Documentation", item.documentation]]);
    const gate = document.createElement("p"); gate.className = "note";
    gate.append(text("Activation remains a device-administrator action. "
      + "This page does not bypass approval or technical policy."));
    content.append(gate);
  } else if (kind === "applications") {
    appendMeta(content, [["Owner", item.owner], ["Repository", item.repository],
      ["Release", item.release], ["Documentation", item.documentation]]);
  }
}

function capabilityRow(row) {
  const item = row.item, kind = activeCapabilityKind, shelf = SHELF_KINDS[kind];
  const key = capabilityRowKey(row);
  const wrapper = document.createElement("div"); wrapper.className = "cap-row";
  wrapper.setAttribute("role", "listitem"); wrapper.dataset.state = row.state;
  const button = document.createElement("button"); button.type = "button";
  button.className = "cap-item"; button.dataset.key = key;
  if (key === activeCapabilityKey) button.setAttribute("aria-current", "true");
  if (key === freshCapabilityKey) { wrapper.dataset.fresh = ""; freshCapabilityKey = ""; }
  const title = document.createElement("strong");
  title.append(text(row.state === "draft" ? (item.title || item.name)
    : capabilityTitle(item, kind)));
  const secondary = document.createElement("small"); secondary.append(text(capabilityKey(item)));
  button.append(title, secondary);
  if (row.state === "draft") {
    const state = tag(false, "", "Draft — not installed");
    state.classList.add("draft", "cap-state"); button.append(state);
  } else if (row.state === "disabled") {
    const state = tag(false, "", "Switched off"); state.classList.add("cap-state");
    button.append(state);
  }
  button.addEventListener("click", () => {
    activeCapabilityKey = key; renderCapabilityBrowser();
    const again = document.querySelector('.cap-item[data-key="' + CSS.escape(key) + '"]');
    if (again) again.focus();
  });
  wrapper.append(button);
  if (row.state === "draft") {
    const install = actionButton("Install", "btn small", (pressed) => installDraft(item, pressed));
    install.setAttribute("aria-label", "Install " + item.asset);
    wrapper.append(install);
  } else if (shelf) {
    const on = row.state === "installed";
    const toggle = document.createElement("button"); toggle.type = "button";
    toggle.className = "switch"; toggle.setAttribute("role", "switch");
    toggle.setAttribute("aria-checked", String(on));
    toggle.setAttribute("aria-label", "Offer " + capabilityKey(item) + " to the Agent");
    toggle.title = on ? "On: the Agent may use it. Press to switch it off."
      : "Off: the Agent does not offer it. Press to switch it on.";
    toggle.addEventListener("click", () => switchAsset(shelf, item, !on, toggle));
    wrapper.append(toggle);
  }
  return wrapper;
}

function renderCapabilityBrowser() {
  for (const kind of ["skills", "workflows", "knowledge", "extensions", "applications"]) {
    el("count-" + kind).textContent = String(capabilityRows(kind).length);
    el("cap-tab-" + kind).setAttribute("aria-selected", String(kind === activeCapabilityKind));
  }
  const shelf = SHELF_KINDS[activeCapabilityKind];
  el("cap-filters").hidden = !shelf;
  const filter = shelf ? activeCapabilityFilter : "all";
  const query = el("capability-search").value.trim().toLowerCase();
  const matching = capabilityRows(activeCapabilityKind).filter((row) =>
    [row.item.name, row.item.namespace, row.item.alias, row.item.title, row.item.description,
     row.item.domain, row.item.state].filter(Boolean).join(" ").toLowerCase().includes(query));
  const counts = {all: matching.length, installed: 0, drafts: 0, disabled: 0};
  for (const row of matching) counts[row.state === "draft" ? "drafts" : row.state] += 1;
  for (const name of Object.keys(counts)) {
    el("cap-filter-count-" + name).textContent = String(counts[name]);
    el("cap-filter-" + name).setAttribute("aria-pressed", String(name === filter));
  }
  const rows = matching.filter((row) => filter === "all"
    || (filter === "drafts" ? row.state === "draft" : row.state === filter));
  if (!rows.some((row) => capabilityRowKey(row) === activeCapabilityKey)) {
    activeCapabilityKey = rows.length ? capabilityRowKey(rows[0]) : "";
  }
  if (rows.length) el("capability-list").replaceChildren(...rows.map(capabilityRow));
  else {
    const empty = document.createElement("div"); empty.className = "empty";
    empty.append(text(activeCapabilityKind === "applications"
      ? "Applications are managed in Shared Marketplace."
      : filter === "drafts" ? "No drafts waiting. Drafts made in a conversation or sent by "
        + "an external agent appear here."
      : filter === "disabled" ? "Nothing is switched off."
      : "No matching capabilities."));
    el("capability-list").replaceChildren(empty);
  }
  showCapabilityDetail(rows.find((row) => capabilityRowKey(row) === activeCapabilityKey),
    activeCapabilityKind);
}

for (const button of document.querySelectorAll(".cap-tabs button")) {
  button.addEventListener("click", () => {
    activeCapabilityKind = button.dataset.kind; activeCapabilityKey = "";
    renderCapabilityBrowser();
  });
}
for (const chip of document.querySelectorAll("#cap-filters .chip")) {
  chip.addEventListener("click", () => {
    activeCapabilityFilter = chip.dataset.filter; activeCapabilityKey = "";
    renderCapabilityBrowser();
  });
}
el("capability-search").addEventListener("input", renderCapabilityBrowser);

// -- MCP servers (owner 2026-10-08) ---------------------------------------

const MCP_STATUS = {connected: "已連線", connecting: "連線中…", failed: "連線失敗",
  disabled: "已停用"};

function linesToMap(text, separator) {
  const map = {};
  for (const line of text.split("\n")) {
    const at = line.indexOf(separator);
    if (at <= 0) continue;
    map[line.slice(0, at).trim()] = line.slice(at + separator.length).trim();
  }
  return map;
}

function showMcpTransport() {
  const http = el("mcp-transport").value === "http";
  el("mcp-http").hidden = !http; el("mcp-stdio").hidden = http;
}

function editMcp(server) {
  const c = server.config;
  el("mcp-name").value = c.name; el("mcp-transport").value = c.transport;
  el("mcp-command").value = c.command; el("mcp-args").value = c.args.join("\n");
  el("mcp-cwd").value = c.cwd || "";
  el("mcp-env").value = Object.entries(c.env).map(([k, v]) => k + "=" + v).join("\n");
  el("mcp-secret-env").value = c.secret_env.map((k) => k + "=").join("\n");
  el("mcp-url").value = c.url;
  el("mcp-headers").value = Object.entries(c.headers).map(([k, v]) => k + ": " + v).join("\n");
  el("mcp-token").value = ""; el("mcp-token").placeholder = server.secrets_present.TOKEN
    ? "stored; empty keeps it" : "";
  el("mcp-timeout").value = c.timeout_seconds; el("mcp-enabled").checked = c.enabled;
  showMcpTransport(); el("mcp-editor").open = true;
}

async function mcpAct(action, body) {
  const done = await call("/api/mcp/" + action, body);
  if (!done.ok) throw new Error(done.message || done.code || action + " failed");
  renderMcp(done.servers);
  return done;
}

function renderMcp(servers) {
  const box = el("mcp-list");
  if (!servers.length) {
    box.className = "empty"; box.textContent = "No MCP server yet."; return;
  }
  box.className = ""; box.replaceChildren();
  for (const server of servers) {
    const c = server.config;
    const card = document.createElement("div"); card.className = "approval-card";
    const title = document.createElement("strong");
    title.textContent = c.name + " (" + (c.transport === "http" ? c.url : c.command) + ") — "
      + (MCP_STATUS[server.status] || server.status);
    const detail = document.createElement("p");
    detail.textContent = server.error ? "Error: " + server.error
      : server.tools.length + " tool(s)";
    const tools = document.createElement("details");
    const label = document.createElement("summary"); label.textContent = "Tools";
    const list = document.createElement("ul");
    for (const tool of server.tools) {
      const item = document.createElement("li");
      item.textContent = tool.name + " — " + tool.capability
        + (tool.description ? " — " + tool.description : "");
      list.append(item);
    }
    tools.append(label, list);
    const edit = document.createElement("button"); edit.type = "button"; edit.textContent = "Edit";
    edit.addEventListener("click", () => editMcp(server));
    const again = document.createElement("button"); again.type = "button";
    again.textContent = "Reconnect";
    const remove = document.createElement("button"); remove.type = "button";
    remove.className = "reject"; remove.textContent = "Remove";
    const note = document.createElement("span"); note.className = "approval-note";
    again.addEventListener("click", async () => {
      note.textContent = "connecting…";
      try { await mcpAct("reconnect", {name: c.name}); } catch (f) { note.textContent = f.message; }
    });
    remove.addEventListener("click", async () => {
      if (!confirm("Remove MCP server " + c.name + "? Its tools stop working.")) return;
      try { await mcpAct("delete", {name: c.name}); } catch (f) { note.textContent = f.message; }
    });
    card.append(title, detail, tools, edit, again, remove, note);
    box.append(card);
  }
}

async function loadMcp() {
  const listed = await call("/api/mcp");
  renderMcp(listed.servers);
  if (listed.servers.some((s) => s.status === "connecting")) {
    setTimeout(() => loadMcp().catch(() => {}), 3000);
  }
}

el("mcp-transport").addEventListener("change", showMcpTransport);
el("mcp-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const transport = el("mcp-transport").value;
  const secrets = linesToMap(el("mcp-secret-env").value, "=");
  const config = {
    name: el("mcp-name").value.trim(), transport: transport,
    enabled: el("mcp-enabled").checked,
    timeout_seconds: Number(el("mcp-timeout").value) || 60,
  };
  if (transport === "stdio") {
    Object.assign(config, {command: el("mcp-command").value.trim(),
      args: el("mcp-args").value.split("\n").map((a) => a.trim()).filter(Boolean),
      cwd: el("mcp-cwd").value.trim() || null, env: linesToMap(el("mcp-env").value, "="),
      secret_env: Object.keys(secrets)});
  } else {
    Object.assign(config, {url: el("mcp-url").value.trim(),
      headers: linesToMap(el("mcp-headers").value, ":"),
      bearer_token: !!el("mcp-token").value || !!el("mcp-token").placeholder});
    if (el("mcp-token").value) secrets.TOKEN = el("mcp-token").value;
  }
  const result = el("mcp-result"), button = el("mcp-save");
  button.disabled = true; result.textContent = "Saving…";
  try {
    await mcpAct("save", {config: config, secrets: secrets});
    el("mcp-token").value = ""; el("mcp-secret-env").value = Object.keys(secrets)
      .filter((k) => k !== "TOKEN").map((k) => k + "=").join("\n");
    result.textContent = "Saved. Connecting in the background…";
    setTimeout(() => loadMcp().catch(() => {}), 2000);
  } catch (failure) {
    result.textContent = "Not saved: " + failure.message;
  } finally { button.disabled = false; }
});

function renderBiQuerySwitch(state) {
  const card = document.createElement("div"); card.id = "bi-query-switch";
  card.lang = "zh-Hant";
  const label = document.createElement("label");
  const box = document.createElement("input"); box.type = "checkbox"; box.id = "bi-query-on";
  box.checked = !!(state && state.enabled);
  label.append(box, text(" 讓外部 coding agent 讀取 BI 知識卡片（aep_bi_query）"));
  const note = document.createElement("p"); note.className = "note";
  note.append(text("開啟後，這台電腦上連到 AEP 的 Claude Code、Codex 和 GitHub Copilot 可以讀取"
    + " BI 知識庫已發佈版本的卡片與已存的分析，內容會送到這些 agent 使用的模型服務。"
    + "沒有發佈過的知識庫讀的是已 push 的最新版本，結果會標明。它們不能寫入，也不能自己下 SQL。"
    + "預設關閉；關閉後立刻停止。"));
  const result = document.createElement("p"); result.className = "note"; result.role = "status";
  box.addEventListener("change", async () => {
    box.disabled = true;
    try {
      const saved = await call("/api/coding-agents/bi-query", {enabled: box.checked});
      box.checked = saved.bi_query.enabled;
      result.textContent = saved.bi_query.enabled ? "已開啟。" : "已關閉。";
    } catch (failure) {
      box.checked = !box.checked; result.textContent = failure.message;
    } finally { box.disabled = false; }
  });
  card.append(label, note, result);
  return card;
}

function renderCodingAgents(listed) {
  const box = el("coding-agents");
  box.className = ""; box.replaceChildren();
  box.append(renderBiQuerySwitch(listed.bi_query));
  for (const agent of listed.agents) {
    const card = document.createElement("div"); card.className = "approval-card";
    card.dataset.agent = agent.agent;
    const title = document.createElement("strong");
    title.textContent = agent.label + " — " + (agent.detected ? "found on this computer"
      : "not found on this computer");
    const skills = document.createElement("p");
    skills.textContent = "Skills: " + listed.skills.map((name) => {
      const v = agent.skills[name];
      return name + " " + (v === null ? "not installed" : v === "yours"
        ? "(your own, kept)" : v === listed.version ? "installed" : "out of date");
    }).join(", ");
    const servers = document.createElement("p");
    const registered = (on) => on ? "registered" : "not registered";
    servers.textContent = "MCP: authoring (aep) " + registered(agent.servers.aep)
      + "; Knowledge (aep-assistant) " + registered(agent.servers["aep-assistant"]);
    const where = document.createElement("p"); where.className = "note";
    where.style.overflowWrap = "anywhere";
    where.textContent = agent.problem || (agent.skills_dir + " · " + agent.mcp_file);
    const install = document.createElement("button"); install.type = "button";
    install.className = "go";
    install.textContent = agent.current ? "Reinstall" : agent.installed ? "Update" : "Install";
    install.disabled = !listed.writable;
    const remove = document.createElement("button"); remove.type = "button";
    remove.className = "reject"; remove.textContent = "Remove"; remove.hidden = !agent.installed;
    const act = async (action) => {
      const result = el("coding-agents-result");
      if (action === "remove" && !confirm("Remove AEP's skills and MCP servers from "
        + agent.label + "?")) return;
      install.disabled = remove.disabled = true; result.textContent = "Working…";
      try {
        const done = await call("/api/coding-agents/" + action, {agent: agent.agent});
        renderCodingAgents(done);
        el("coding-agents-result").textContent = (done.lines || []).join("\n")
          + (done.ok ? "\nRestart " + agent.label + " to use the change." : "");
      } catch (failure) {
        result.textContent = "Not changed: " + failure.message;
        install.disabled = remove.disabled = false;
      }
    };
    install.addEventListener("click", () => act("install"));
    remove.addEventListener("click", () => act("remove"));
    card.append(title, skills, servers, where, install, remove);
    box.append(card);
  }
}

async function loadCodingAgents() {
  renderCodingAgents(await call("/api/coding-agents"));
}

async function loadSettings() {
  const settings = await call("/api/settings"), model = settings.model,
    persona = settings.persona;
  el("persona-name").value = persona.name;
  el("persona-introduction").value = persona.introduction;
  el("persona-soul").value = persona.soul;
  showTelegram(settings.telegram);
  loadSharedPlatform().catch(() => {});
  loadTeams().catch(() => {});
  loadLaya().catch(() => {});
  loadCodingAgents().catch(() => {});
  loadAgentModeSettings().catch(() => {});
  loadMultiAgent().catch((failure) => { el("multi-agent-result").textContent = failure.message; });
  loadGateway().catch((failure) => { el("gateway-state").textContent = failure.message; });
  el("persona-result").textContent =
    "Saved locally. Changes apply to the next natural-language turn.";
  el("model-provider").value = model.provider || "openai_compatible";
  el("model-alias").value = model.alias || "company";
  el("model-base-url").value = model.base_url || ["http:", "", "127.0.0.1:4000/v1"].join("/");
  el("model-name").value = model.model || "";
  if (model.configured) loadModelChoices();
  el("model-context-capacity").value = model.declared_context_tokens || 128000;
  el("model-secret").value = model.credential_secret || "";
  el("model-environment").value = model.credential_environment || "";
  el("model-save").disabled = !settings.writable;
  el("model-result").textContent = model.configured
    ? "Configured: " + model.alias + " → " + model.model + " at " + model.base_url
      + (model.credential_secret ? "\nCredential value present: " + model.credential_present : "")
    : (settings.writable
      ? "No routing model is configured." : "Settings are read-only in this launch mode.");
  el("model-data-approval").textContent = model.data_approval
    ? "Administrator approval: " + model.data_approval.approval_ref
      + " · Classes: " + model.data_approval.approved_classes.join(", ")
    : "No administrator data-transfer approval is recorded for this Gateway.";
  el("context-messages").value = settings.context.recent_messages;
  el("context-budget").value = settings.context.history_budget_bytes;
  el("context-tool-calls").value = settings.context.tool_call_limit;
  el("context-time-limit").value = settings.context.turn_time_limit_minutes;
  el("context-result").textContent = "Active now. Model-declared capacity: "
    + (model.declared_context_tokens == null
      ? "not configured" : model.declared_context_tokens + " tokens")
    + ". The history budget is separate from that capacity.";
  el("memory-state").textContent = "Saved locally per session (up to "
    + settings.memory.stored_messages + " messages). Older messages are visible but outside"
    + " the active context. Cross-session memory is off.";
  const listed = await call("/api/conversations"), target = el("session-manage-target");
  target.replaceChildren(...listed.conversations.map(item => {
    const option = document.createElement("option"); option.value = item.session_id;
    option.textContent = item.title + " · " + item.messages + " messages";
    return option;
  }));
  if ([...target.options].some(option => option.value === activeConversation)) {
    target.value = activeConversation;
  }
  el("session-delete").disabled = !listed.conversations.length;
}

// -- Workflow settings ------------------------------------------------------

// Shown with the selected Workflow in Capabilities, only when it declares
// settings; the Settings page no longer repeats them (owner, 2026-10-06).
async function loadWorkflowSettings(item) {
  const panel = el("workflow-settings"), box = el("workflow-settings-list");
  const selected = el("workflow-target").value;
  panel.hidden = true; box.replaceChildren();
  let listed;
  try { listed = await call("/api/settings/workflows"); }
  catch (failure) { listed = {ok: false, code: failure.message}; }
  // Another Workflow may have been chosen while this was being read.
  if (el("workflow-target").value !== selected) return;
  if (!listed.ok) {
    box.replaceChildren(text("Settings are unavailable: " + listed.code));
    panel.hidden = false; return;
  }
  const entry = listed.workflows.find((candidate) =>
    candidate.workflow.namespace === item.namespace && candidate.workflow.name === item.name);
  if (!entry) return;
  box.replaceChildren(workflowSettingsCard(entry, 0));
  panel.open = entry.missing.length > 0;
  panel.hidden = false;
}

function workflowSettingsCard(entry, index) {
  const card = document.createElement("div");
  const missing = document.createElement("p"); missing.className = "note";
  missing.setAttribute("role", "status");
  const showMissing = (names) => missing.replaceChildren(text(names.length
    ? "Missing required settings: " + names.join(", ") + ". The Workflow will not start."
    : "All required settings are set."));
  showMissing(entry.missing);
  // Stored values show in place of declared defaults.
  const fields = entry.fields.map(field => Object.assign({}, field,
    Object.prototype.hasOwnProperty.call(entry.values, field.name)
      ? {default: entry.values[field.name]} : {}));
  const form = document.createElement("div");
  const prefix = "workflow-setting-" + index + "-";
  renderParameterForm(form, fields, prefix);
  const save = document.createElement("button"); save.type = "button";
  save.className = "go"; save.append(text("Save settings"));
  const result = document.createElement("p"); result.className = "note";
  result.setAttribute("role", "status");
  save.addEventListener("click", async () => {
    let values;
    try { values = collectParameterValues(form, fields, prefix); }
    catch (failure) { result.replaceChildren(text(failure.message)); return; }
    save.disabled = true;
    try {
      const saved = await call("/api/settings/workflows",
        {workflow: entry.workflow, values: values});
      if (!saved.ok) throw new Error(saved.message || saved.code);
      showMissing(saved.workflow.missing);
      result.replaceChildren(text("Saved. The next run uses these settings."));
    } catch (failure) {
      result.replaceChildren(text("Not saved: " + failure.message));
    } finally { save.disabled = false; }
  });
  card.append(missing, form, save, result);
  return card;
}

// -- end Workflow settings

// The multi-agent switch (V1): host.json `multi_agent.enabled`, read by the
// Agent when it starts, so the card says when a restart is still needed.
function showMultiAgent(state) {
  const box = el("multi-agent-enabled"), result = el("multi-agent-result");
  box.checked = !!state.enabled;
  box.disabled = !state.writable;
  box.setAttribute("aria-checked", String(!!state.enabled));
  if (!state.supported) {
    result.textContent = "這個 Agent 版本還沒有多 Agent 委派。";
  } else if (!state.writable) {
    result.textContent = "這次啟動的設定是唯讀的。目前"
      + (state.running ? "已開啟" : "已關閉") + "。";
  } else if (state.restart_needed) {
    result.textContent = "已儲存為" + (state.enabled ? "開啟" : "關閉")
      + "；重新啟動 Agent Web 後生效（目前仍" + (state.running ? "開啟" : "關閉")
      + "）。重新啟動前先確認沒有進行中的工作。";
  } else {
    result.textContent = state.running ? "已開啟。" : "已關閉（預設）。";
  }
}

async function loadMultiAgent() {
  showMultiAgent(await call("/api/settings/multi-agent"));
}

el("multi-agent-enabled").addEventListener("change", async () => {
  const box = el("multi-agent-enabled"), result = el("multi-agent-result");
  box.disabled = true; result.textContent = "儲存中…";
  try {
    showMultiAgent(await call("/api/settings/multi-agent", {enabled: box.checked}));
  } catch (failure) {
    result.textContent = "沒有儲存："
      + ((failure.payload && failure.payload.code) || failure.message);
    loadMultiAgent().catch(() => {});
  }
});

el("context-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = el("context-save"), result = el("context-result");
  button.disabled = true; result.textContent = "Saving context limits…";
  try {
    const saved = await call("/api/settings/context", {
      recent_messages: Number(el("context-messages").value),
      history_budget_bytes: Number(el("context-budget").value),
      tool_call_limit: Number(el("context-tool-calls").value),
      turn_time_limit_minutes: Number(el("context-time-limit").value),
    });
    result.textContent = "Saved. The next ordinary chat turn uses "
      + saved.context.recent_messages + " recent messages within "
      + saved.context.history_budget_bytes + " UTF-8 bytes of history text, and may make up to "
      + saved.context.tool_call_limit + " tool calls in "
      + saved.context.turn_time_limit_minutes + " minutes.";
  } catch (failure) {
    result.textContent = "Context limits were not saved: " + failure.message;
  } finally { button.disabled = false; }
});

el("session-delete").addEventListener("click", async () => {
  const target = el("session-manage-target"), selected = target.selectedOptions[0];
  if (!selected || !confirm("Permanently delete saved session “"
      + selected.textContent + "”?")) return;
  const result = el("session-manage-result"), button = el("session-delete");
  button.disabled = true; result.textContent = "Deleting session…";
  try {
    const deleted = await call("/api/conversations/delete", {session_id: selected.value});
    if (!deleted.ok) throw new Error(deleted.code || "deletion_failed");
    if (selected.value === activeConversation) activeConversation = "";
    await loadChat(activeConversation || undefined);
    await loadSettings();
    result.textContent = "Session deleted. Independent contribution drafts retain their evidence.";
  } catch (failure) {
    result.textContent = "Session was not deleted: " + failure.message;
  } finally { button.disabled = false; }
});

function showTelegram(telegram) {
  // Unconfigured: someone filling this in wants the bot on.
  el("telegram-enabled").checked = telegram.enabled || !telegram.configured;
  el("telegram-senders").value = telegram.senders
    .map((item) => item.sender_id + " " + item.actor).join("\n");
  el("telegram-token").value = "";
  const unknown = el("telegram-unknown");
  unknown.replaceChildren();
  for (const sender of telegram.unknown_senders || []) {
    const row = document.createElement("p");
    row.className = "note";
    row.append(text("Not yet allowed: " + sender.sender_id
      + (sender.name ? " (" + sender.name + ")" : "") + " "));
    const allow = document.createElement("button");
    allow.type = "button";
    allow.append(text("Allow"));
    allow.addEventListener("click", () => {
      const box = el("telegram-senders");
      box.value = (box.value.trim() ? box.value.trim() + "\n" : "") + sender.sender_id;
      el("telegram-enabled").checked = true;
      el("telegram-settings").requestSubmit();
    });
    row.append(allow);
    unknown.append(row);
  }
  el("telegram-result").textContent = (telegram.token_present
    ? "Token saved in " + telegram.environment_variable + "."
    : "No token saved yet.")
    + (telegram.enabled && !telegram.senders.length
      ? " The bot is running but allows nobody yet: send it a message, then press"
        + " \u201cCheck who messaged the bot\u201d."
      : "")
    + (telegram.enabled ? (telegram.running
        ? (telegram.problem ? "" : " Bot is answering.")
        : (telegram.failure ? " Bot stopped; save to start it again." : " Bot is starting…"))
      : (telegram.configured
        ? " Saved, but the bot is off: tick"
          + " \u201cAnswer Telegram messages\u201d and save to start it."
        : " Bot is off."))
    + (telegram.running && telegram.problem
      ? " " + (TELEGRAM_WAITING[telegram.problem] || "Not answering yet, retrying: "
        + telegram.problem + ".")
      : "")
    + (telegram.failure ? " Last stop: " + telegram.failure : "");
}

// What a running bot is waiting out (owner 2026-10-30: a second program on the
// same bot made AEP silently stop answering).
const TELEGRAM_WAITING = {
  telegram_conflict: "Not answering: another program is receiving this bot's messages "
    + "(Telegram allows only one; for example another AEP or bot program using the same "
    + "token). Stop it or give it another bot; AEP keeps trying and takes over as soon as "
    + "it stops.",
};

el("telegram-check").addEventListener("click", async () => {
  try {
    showTelegram((await call("/api/settings")).telegram);
  } catch (failure) {
    el("telegram-result").textContent = "Could not check: " + failure.message;
  }
});

const TELEGRAM_PROBLEMS = {
  telegram_token_invalid: "The token does not look like a bot token (123456789:AA…). "
    + "Copy it again from @BotFather.",
  telegram_token_missing: "Paste the bot token from @BotFather first.",
  telegram_senders_missing: "Add at least one allowed sender (a numeric Telegram user id).",
  telegram_sender_invalid: "Each sender line is a numeric Telegram user id, optionally "
    + "followed by an actor name. Message @userinfobot in Telegram to see your id.",
  telegram_actor_invalid: "An actor name may use letters, digits, '.', '_' and '-' only.",
  settings_read_only: "Settings are read-only in this launch mode.",
  page_expired: "This page is from an earlier start of Agent Web. Open the newest Agent Web "
    + "tab and save again.",
};

// -- Shared platform (owner 2026-10-15) ---------------------------------------
// The page names no outside address itself, so the examples are built here.
el("shared-portal-url").placeholder = ["http:", "", "127.0.0.1:28776"].join("/");
el("shared-bridge-url").placeholder = ["http:", "", "127.0.0.1:28775"].join("/");

// A URL the person typed is not replaced by settings that arrive later.
const sharedEdited = new Set();
for (const id of ["shared-portal-url", "shared-bridge-url"]) {
  el(id).addEventListener("input", () => sharedEdited.add(id));
}

function showSharedPlatform(info, saved) {
  if (saved) sharedEdited.clear();
  const keep = (id) => document.activeElement === el(id) || sharedEdited.has(id);
  if (!keep("shared-portal-url")) el("shared-portal-url").value = info.member_portal_url || "";
  if (!keep("shared-bridge-url")) el("shared-bridge-url").value = info.base_url || "";
  el("shared-cert-pinned").textContent = info.certificate_sha256
    ? "Trusted certificate (SHA-256): " + info.certificate_sha256
    : info.ca_file ? "Certificates are checked against " + info.ca_file
      : "No certificate pinned: only certificates Windows already trusts are accepted.";
  el("shared-cert-forget").disabled = !info.certificate_sha256;
  el("shared-this-pc").textContent = "This PC: Bridge " + info.bridge_id + ", registered by "
    + info.registered_by + (info.login_saved ? " · Personal Agent code saved"
      : " · no Personal Agent code yet")
    + (info.assets_only ? " · grants.json decides what this PC may run; synchronizing "
      + "installs files only" : "");
  const parts = [];
  if (info.enrolled) {
    parts.push("Enrolled as " + info.enrolled.bridge_id + " (" + info.enrolled.actor + ")");
    if (info.enrolled.expires_at) {
      parts.push("token valid until " + new Date(info.enrolled.expires_at).toLocaleString());
    }
  } else {
    parts.push("Not enrolled on this shared platform yet");
  }
  if (info.last_catalog) {
    parts.push("last catalog read " + new Date(info.last_catalog.at).toLocaleString()
      + " (" + info.last_catalog.status + ")");
  }
  el("shared-status").textContent = parts.join(" · ");
  showAgentCode(info);
}

// The Personal Agent code and the Bridge token: expiry only (owner 2026-10-19).
function showAgentCode(info) {
  const code = info.agent_code || {state: "none"}, state = el("shared-code-state");
  const when = (iso) => new Date(iso).toLocaleString();
  const account = el("shared-signin-account");
  if (!account.value && info.registered_by) account.value = info.registered_by;
  state.classList.toggle("bad", code.state === "expired");
  el("shared-signin-go").textContent = code.state === "expired"
    ? "Sign in to get a new code" : "Sign in to get a code";
  if (code.state === "none") {
    state.textContent = "No Personal Agent code on this PC yet: sign in below, or paste one.";
  } else if (code.state === "unknown") {
    state.textContent = "A Personal Agent code is saved; its expiry is checked and the code "
      + "renewed automatically.";
  } else if (code.state === "expired") {
    state.textContent = "Your Personal Agent code has expired. Sign in to get a new code.";
  } else {
    state.textContent = "Personal Agent code valid until " + when(code.expires_at)
      + (code.estimated ? " (estimated from when it was pasted)" : "")
      + (code.state === "renew_soon" ? " · it is renewed automatically" : "")
      + (code.renewals ? " · renewed " + code.renewals + "×" : "");
  }
  const token = info.bridge_token || {}, note = el("shared-token-note");
  note.classList.toggle("bad", !!token.remind);
  note.textContent = !token.expires_at ? ""
    : token.expired ? "The Bridge token has expired: press \"Enroll this PC\" again."
      : "Bridge token valid until " + when(token.expires_at)
        + (token.remind ? " · under 14 days left: press \"Enroll this PC\" again." : "");
}

async function signInForCode() {
  const field = el("shared-signin-password"), go = el("shared-signin-go");
  const status = el("shared-status");
  const password = field.value;
  field.value = "";  // the password never stays on the page
  status.classList.remove("bad");
  if (!password) {
    status.classList.add("bad"); status.textContent = "Enter your password."; return;
  }
  go.disabled = true; status.textContent = "Signing in to get a Personal Agent code…";
  try {
    const reply = await call("/api/settings/shared-platform/sign-in", {
      member_portal_url: el("shared-portal-url").value.trim(),
      base_url: el("shared-bridge-url").value.trim(),
      account: el("shared-signin-account").value.trim(), password});
    if (reply.member_portal_url !== undefined) showSharedPlatform(reply, reply.ok !== false);
    if (reply.ok === false) {
      status.classList.add("bad");
      status.textContent = "No code: " + (reply.message || reply.code);
    } else {
      status.textContent = "Personal Agent code saved. " + status.textContent;
    }
  } catch (failure) {
    status.classList.add("bad"); status.textContent = "No code: " + failure.message;
  } finally { go.disabled = false; }
}

el("shared-signin-go").addEventListener("click", signInForCode);
el("shared-signin-password").addEventListener("keydown", (event) => {
  // Enter signs in; it never submits the card's Save with the password typed.
  if (event.key === "Enter") { event.preventDefault(); signInForCode(); }
});

// "Teams I belong to on this PC" (owner 2026-10-19).
const TEAM_SOURCES = {
  platform: "from the shared platform",
  platform_cache: "from the shared platform's last answer (offline)",
  declared: "declared on this PC",
};

function showTeams(info) {
  const field = el("team-declared");
  if (document.activeElement !== field) field.value = (info.declared_teams || []).join(", ");
  // The platform's teams win (#233): the local list is kept but not editable.
  const unused = info.source === "platform" || info.source === "platform_cache";
  field.disabled = unused; el("team-save").disabled = unused;
  el("team-unused").hidden = !unused;
  const teams = (info.teams || []).join(", ") || "none";
  el("team-status").textContent = "Teams used for revisions: " + teams
    + (TEAM_SOURCES[info.source] ? " (" + TEAM_SOURCES[info.source] + ")" : "")
    + (info.checked_at ? " · checked " + new Date(info.checked_at).toLocaleString() : "");
}

async function loadTeams() {
  const info = await call("/api/settings/teams");
  if (info.ok !== false) showTeams(info);
}

el("team-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = el("team-status"), save = el("team-save");
  save.disabled = true; status.classList.remove("bad");
  try {
    const reply = await call("/api/settings/teams",
      {declared_teams: el("team-declared").value});
    if (reply.ok === false) {
      status.classList.add("bad");
      status.textContent = "Not saved: " + (reply.message || reply.code);
    } else {
      showTeams(reply); status.textContent = "Saved. " + status.textContent;
    }
  } catch (failure) {
    status.classList.add("bad"); status.textContent = "Not saved: " + failure.message;
  } finally { save.disabled = el("team-declared").disabled; }
});

async function loadSharedPlatform() {
  const info = await call("/api/settings/shared-platform");
  if (info.ok !== false) showSharedPlatform(info);
}

async function saveSharedPlatform(enroll) {
  const save = el("shared-save"), go = el("shared-enroll"), status = el("shared-status");
  const field = el("shared-code");
  save.disabled = true; go.disabled = true; status.classList.remove("bad");
  status.textContent = enroll ? "Enrolling this PC…" : "Saving…";
  try {
    const reply = await call("/api/settings/shared-platform", {
      member_portal_url: el("shared-portal-url").value.trim(),
      base_url: el("shared-bridge-url").value.trim(),
      code: field.value, enroll});
    field.value = "";  // the code never stays on the page
    if (reply.member_portal_url !== undefined) showSharedPlatform(reply, reply.ok !== false);
    if (reply.ok === false) {
      status.classList.add("bad");
      status.textContent = (reply.saved ? "Settings saved, but not enrolled: " : "Not saved: ")
        + (reply.message || reply.code);
    } else if (enroll) {
      status.textContent = "Enrolled. " + status.textContent
        + (reply.probe ? " · the platform answered: " + reply.probe : "")
        + " · no restart needed.";
      loadCapabilities().catch(() => {});
    } else {
      status.textContent = "Saved. " + status.textContent;
    }
  } catch (failure) {
    status.classList.add("bad"); status.textContent = "Not saved: " + failure.message;
  } finally { save.disabled = false; go.disabled = false; }
}

el("shared-platform-settings").addEventListener("submit", (event) => {
  event.preventDefault(); saveSharedPlatform(false);
});
el("shared-enroll").addEventListener("click", () => saveSharedPlatform(true));

// "Platform certificate" (owner 2026-10-16): fetch shows what the platform
// presents; trusting stores exactly the fingerprint the member compared.
let presentedCertificate = null;

async function fetchSharedCertificate() {
  const out = el("shared-cert-fingerprint"), status = el("shared-status");
  presentedCertificate = null;
  el("shared-cert-trust").disabled = true; el("shared-cert-download").disabled = true;
  status.classList.remove("bad"); out.textContent = "Reading the certificate…";
  try {
    const reply = await call("/api/settings/shared-platform/certificate", {
      member_portal_url: el("shared-portal-url").value.trim(),
      base_url: el("shared-bridge-url").value.trim()});
    if (reply.ok === false) {
      out.textContent = ""; status.classList.add("bad");
      status.textContent = reply.message || reply.code;
      return;
    }
    presentedCertificate = reply;
    out.textContent = "SHA-256 " + reply.fingerprint
      + (reply.matches_pin ? " · already trusted on this PC"
        : reply.trusted_by_system ? " · Windows already trusts it" : " · not trusted yet");
    el("shared-cert-trust").disabled = !!reply.matches_pin;
    el("shared-cert-download").disabled = false;
  } catch (failure) {
    out.textContent = ""; status.classList.add("bad"); status.textContent = failure.message;
  }
}

async function trustSharedCertificate(fingerprint) {
  const status = el("shared-status");
  status.classList.remove("bad");
  try {
    const reply = await call("/api/settings/shared-platform", {
      member_portal_url: el("shared-portal-url").value.trim(),
      base_url: el("shared-bridge-url").value.trim(),
      certificate_sha256: fingerprint, code: "", enroll: false});
    if (reply.member_portal_url !== undefined) showSharedPlatform(reply, reply.ok !== false);
    if (reply.ok === false) {
      status.classList.add("bad");
      status.textContent = "Not saved: " + (reply.message || reply.code);
      return;
    }
    el("shared-cert-trust").disabled = true;
    status.textContent = (fingerprint ? "Certificate trusted. " : "Certificate forgotten. ")
      + status.textContent;
  } catch (failure) {
    status.classList.add("bad"); status.textContent = "Not saved: " + failure.message;
  }
}

el("shared-cert-fetch").addEventListener("click", () => fetchSharedCertificate());
el("shared-cert-trust").addEventListener("click", () => {
  if (presentedCertificate) trustSharedCertificate(presentedCertificate.fingerprint);
});
el("shared-cert-forget").addEventListener("click", () => trustSharedCertificate(""));
el("shared-cert-download").addEventListener("click", () => {
  if (!presentedCertificate) return;
  // The public certificate only, for importing into Windows (see the guide).
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([presentedCertificate.pem],
    {type: "application/x-x509-ca-cert"}));
  link.download = "shared-platform.cer";
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
});

// -- LLM gateway (docs/phases/LLM_GATEWAY.md) --------------------------------
// Running / Starting… / Stopped, token expiry (never the value), last test,
// Start / Restart / Refresh token / Test, autostart. A gateway run outside
// AEP (managed=false) is shown and tested only.
const GATEWAY_STATES = {serving: "Running", starting: "Starting…", stopped: "Stopped"};
const GATEWAY_PROBLEMS = {
  not_managed: "this gateway is run outside AEP; use the tools it was set up with",
  not_ours: "another program serves this port; AEP does not stop it",
  gateway_busy: "the gateway is busy with another action; try again in a moment",
  config: "the gateway configuration has a problem (see below)",
};
let gatewayTimer = null;

function gatewayToken(token) {
  if (!token || !token.present) return "missing — press Refresh token";
  if (!token.expires_at) return "present (expiry unreadable)";
  const day = token.expires_at.slice(0, 16).replace("T", " ");
  return token.expired ? "EXPIRED on " + day + " UTC — press Refresh token"
    : "valid until " + day + " UTC (" + token.days_left + " days left)";
}

function showGateway(info) {
  const state = el("gateway-state");
  state.dataset.state = info.state;
  let line = (GATEWAY_STATES[info.state] || info.state) + " · 127.0.0.1:" + info.port;
  if (!info.managed) line += " · run outside AEP (status and test only)";
  else if (info.state === "serving" && !info.ours) line += " · not started by AEP";
  if (info.state === "starting" && info.started_at) {
    const since = Math.max(0, Math.round((Date.now() - Date.parse(info.started_at)) / 1000));
    line += " · started " + since + " s ago; a first start can take a few minutes";
  }
  state.textContent = line;
  const test = info.last_test && info.last_test.results ? info.last_test : null;
  const rows = [
    ["Token", gatewayToken(info.token)],
    ["Last refresh", info.last_refresh_at ? info.last_refresh_at.replace("T", " ")
      + (info.last_refresh_error ? " (last attempt failed: " + info.last_refresh_error + ")" : "")
      : (info.last_refresh_error ? "failed: " + info.last_refresh_error : "not yet")],
    ["Models answering", test ? test.results.filter((r) => r.model !== "(models)")
      .map((r) => r.model + (r.ok ? " ✓" : " ✗ " + r.code)).join(", ")
      + " (" + test.at.replace("T", " ") + ")" : "not tested yet — press Test"],
    ["Local key", info.key_present ? "present" : "missing"],
    ["Configuration", info.config_ok ? "ok" : info.config_problems.join("; ")],
    ["LiteLLM", (info.litellm_version || "not found") + " (verified " + info.litellm_pinned + ")"],
    ["Folder", info.home],
  ];
  const facts = el("gateway-facts");
  facts.replaceChildren(...rows.flatMap(([term, value]) => {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.append(text(term)); dd.append(text(value)); return [dt, dd];
  }));
  const managed = info.managed !== false;
  el("gateway-start").disabled = !managed || info.state !== "stopped";
  el("gateway-restart").disabled = !managed || !info.ours;
  el("gateway-refresh").disabled = !managed;
  el("gateway-test").disabled = info.state !== "serving";
  const autostart = el("gateway-autostart");
  autostart.disabled = !managed;
  autostart.checked = !!(info.autostart && info.autostart.on);
  const link = el("model-gateway-link");
  link.hidden = !info.model_uses_gateway;
  if (info.model_uses_gateway) {
    const anchor = document.createElement("a");
    anchor.href = "#gateway-heading"; anchor.append(text("127.0.0.1:" + info.port));
    link.replaceChildren(text("Uses the built-in gateway at "), anchor,
      text(" (" + (GATEWAY_STATES[info.state] || info.state).toLowerCase() + ")."));
  }
  clearTimeout(gatewayTimer);
  if (info.state === "starting") {
    gatewayTimer = setTimeout(() => loadGateway().catch(() => {}), 2000);
  }
}

async function loadGateway() {
  showGateway(await call("/api/settings/gateway"));
}

async function gatewayAct(action, extra, busyText) {
  const result = el("gateway-result");
  const buttons = ["gateway-start", "gateway-restart", "gateway-refresh", "gateway-test"];
  buttons.forEach((id) => { el(id).disabled = true; });
  result.textContent = busyText;
  try {
    const done = await call("/api/settings/gateway", {action, ...extra});
    if (done.state) showGateway(done);
    const lines = [];
    if (done.ok === false) lines.push("Not done: " + (GATEWAY_PROBLEMS[done.code] || done.message
      || done.code));
    if (done.refresh) lines.push((done.refresh.ok ? "Token: " : "Token not renewed: ")
      + done.refresh.message + (done.restarted ? " The gateway was restarted." : ""));
    if (done.test) lines.push(...done.test.map((r) => (r.ok ? "✓ " : "✗ ") + r.model
      + ": " + (r.ok ? (r.detail || "ok") : r.code + " " + r.detail)));
    if (done.autostart_result) lines.push("Autostart " + (done.autostart_result.on ? "on" : "off")
      + (done.autostart_result.note ? " — " + done.autostart_result.note : ""));
    if (done.ok !== false && (action === "start" || action === "restart")) {
      lines.push("Starting; this card updates when it answers.");
    }
    result.textContent = lines.join("\n");
  } catch (failure) {
    result.textContent = "Not done: " + failure.message;
    loadGateway().catch(() => {});
  }
}

el("gateway-start").addEventListener("click", () => gatewayAct("start", {}, "Starting…"));
el("gateway-restart").addEventListener("click", () =>
  gatewayAct("restart", {}, "Restarting…"));
el("gateway-refresh").addEventListener("click", () =>
  gatewayAct("refresh", {}, "Renewing the token with your Windows sign-in…"));
el("gateway-test").addEventListener("click", () =>
  gatewayAct("test", {}, "Asking the gateway's default model…"));
el("gateway-autostart").addEventListener("change", () =>
  gatewayAct("autostart", {on: el("gateway-autostart").checked}, "Saving…"));

// -- Laya decision acceleration (owner 2026-10-13) ---------------------------
const LAYA_PROBLEMS = {
  egress_approval_missing: "shadow and active send the latest user message to Laya; "
    + "enter the owner's approval reference first",
  credential_unmapped: "the Laya key is not mapped in host.json credentials",
  laya_settings_invalid: "check the host, account and numbers",
  settings_read_only: "this Agent Web was started without its host file",
};

function showLaya(info) {
  const s = info.settings;
  el("laya-host").value = s.ssh_host; el("laya-ssh-port").value = s.ssh_port;
  el("laya-user").value = s.ssh_user; el("laya-remote-port").value = s.remote_port;
  el("laya-local-port").value = s.local_port; el("laya-mode").value = s.mode;
  el("laya-threshold").value = Math.round(s.confidence_threshold * 100);
  el("laya-timeout").value = s.timeout_ms; el("laya-approval").value = s.approval_ref || "";
  el("laya-auto").checked = s.auto_tunnel;
  const tunnel = info.tunnel || {}, probe = info.probe || {}, last = info.last_decision;
  const parts = [
    probe.reachable ? "Connected: Laya answered in " + probe.ms + " ms"
      : "Not connected through 127.0.0.1:" + s.local_port,
    tunnel.state === "not_managed" ? "tunnel not opened by Agent Web"
      : "tunnel " + tunnel.state + (tunnel.error ? " (" + tunnel.error + ")" : "")
        + (tunnel.restarts ? ", reopened " + tunnel.restarts + " times" : ""),
    last ? "last decision " + (last.at || "").slice(0, 19).replace("T", " ") + " UTC, "
      + last.outcome + (last.latency_ms != null ? ", " + last.latency_ms + " ms" : "") : "",
    info.running_mode !== s.mode ? "running in " + info.running_mode
      + " until Agent Web restarts" : "",
  ].filter(Boolean);
  el("laya-status").textContent = parts.join(" · ");
}

async function loadLaya() {
  const info = await call("/api/settings/laya");
  if (info.ok) showLaya(info);
}

el("laya-check").addEventListener("click", () => {
  el("laya-status").textContent = "Checking…";
  loadLaya().catch((failure) => { el("laya-status").textContent = failure.message; });
});

el("laya-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const number = (id) => Number(el(id).value);
  const body = {
    ssh_host: el("laya-host").value.trim(), ssh_port: number("laya-ssh-port"),
    ssh_user: el("laya-user").value.trim(), remote_port: number("laya-remote-port"),
    local_port: number("laya-local-port"), auto_tunnel: el("laya-auto").checked,
    mode: el("laya-mode").value, confidence_threshold: number("laya-threshold") / 100,
    timeout_ms: number("laya-timeout"),
    approval_ref: el("laya-approval").value.trim() || null,
  };
  const button = el("laya-save"); button.disabled = true;
  el("laya-status").textContent = "Saving…";
  try {
    const saved = await call("/api/settings/laya", body);
    if (saved.ok === false) throw Object.assign(new Error(saved.code), {code: saved.code});
    showLaya(saved);
    if (saved.restart_required) {
      el("laya-status").textContent += " · Saved; restart Agent Web for the new mode.";
    }
  } catch (failure) {
    const code = failure.code || "";
    el("laya-status").textContent = "Not saved: " + (LAYA_PROBLEMS[code] || code
      || failure.message);
  } finally { button.disabled = false; }
});

el("telegram-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = el("telegram-save"), result = el("telegram-result");
  const senders = [];
  for (const line of el("telegram-senders").value.split("\n")) {
    const parts = line.trim().split(/[\s,]+/).filter(Boolean);
    if (!parts.length) continue;
    if (!/^\d+$/.test(parts[0])) {
      result.textContent = "Not saved: “" + parts[0] + "” is not a numeric Telegram "
        + "user id. Message @userinfobot in Telegram to see yours.";
      return;
    }
    senders.push({sender_id: Number(parts[0]), actor: parts[1] || ""});
  }
  const body = {enabled: el("telegram-enabled").checked, senders};
  const token = el("telegram-token").value.trim();
  if (token) body.token = token;
  button.disabled = true; result.textContent = "Saving Telegram settings…";
  try {
    const saved = await call("/api/settings/telegram", body);
    if (saved.ok === false) throw Object.assign(new Error(saved.code), {code: saved.code});
    showTelegram(saved.telegram);   // clears the token field only after a save
  } catch (failure) {
    const code = failure.code || "";
    result.textContent = "Not saved: " + (TELEGRAM_PROBLEMS[code] || code || failure.message);
  } finally { button.disabled = false; }
});

el("persona-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = el("persona-save"), result = el("persona-result");
  button.disabled = true; result.textContent = "Saving Agent identity…";
  try {
    const saved = await call("/api/settings/persona", {
      name: el("persona-name").value.trim(),
      introduction: el("persona-introduction").value.trim(),
      soul: el("persona-soul").value,
    });
    el("agent-name").textContent = saved.persona.name;
    el("agent-introduction").textContent = saved.persona.introduction;
    result.textContent = "Saved locally. Changes apply to the next natural-language turn.";
  } catch (failure) {
    result.textContent = "Agent identity was not saved: " + failure.message;
  } finally { button.disabled = false; }
});

async function loadModelChoices() {
  const select = el("model-choices"), state = el("model-choices-state");
  state.textContent = "Reading the Gateway model list…";
  try {
    const listed = await call("/api/settings/models");
    const first = document.createElement("option"); first.value = "";
    first.append(text(listed.ok ? "Choose a model (" + listed.models.length + ")"
      : "Model list unavailable"));
    select.replaceChildren(first);
    for (const name of listed.models) {
      const option = document.createElement("option");
      option.value = name; option.append(text(name)); select.append(option);
    }
    const current = el("model-name").value;
    if (listed.models.includes(current)) select.value = current;
    state.textContent = listed.ok
      ? "Choosing a model fills the field below; save to apply it."
      : "Could not read the list (" + listed.code + "); type the model name instead.";
  } catch (failure) {
    state.textContent = "Could not read the list: " + failure.message;
  }
}

el("model-choices").addEventListener("change", () => {
  const chosen = el("model-choices").value;
  if (chosen) el("model-name").value = chosen;
});
el("model-choices-load").addEventListener("click", loadModelChoices);

el("model-settings").addEventListener("submit", async (event) => {
  event.preventDefault();
  const secret = el("model-secret").value.trim();
  const environment = el("model-environment").value.trim();
  const button = el("model-save"), result = el("model-result"); button.disabled = true;
  result.textContent = "Validating and saving settings…";
  const body = {
    alias: el("model-alias").value.trim(), provider: el("model-provider").value,
    model: el("model-name").value.trim(), base_url: el("model-base-url").value.trim(),
    max_context_tokens: Number(el("model-context-capacity").value),
  };
  if (secret || environment) {
    body.credential_secret = secret; body.credential_environment = environment;
  }
  try {
    const saved = await call("/api/settings/model", body);
    result.textContent = "Saved. Restart the Agent to use this model configuration. "
      + "If the Gateway route changed, update its approved data classes in host.json."
      + (environment
        ? "\nSet the token value in Windows environment variable " + environment + "."
        : "");
  } catch (failure) {
    result.textContent = "Settings were not saved: " + failure.message;
  } finally { button.disabled = false; }
});

function showWorkflowContract() {
  const chosen = el("workflow-target").selectedOptions[0];
  el("workflow-contract").textContent = chosen
    ? "Input contract: " + chosen.dataset.inputContract : "No installed Workflow.";
  const workflow = chosen && installedAssets.workflows.find((item) =>
    JSON.stringify({namespace: item.namespace, name: item.name, version: item.version})
    === chosen.value);
  const typed = workflow && workflow.parameters.editor === "fields";
  el("workflow-fields").hidden = !typed;
  el("workflow-legacy").hidden = !!typed;
  workflowFields = typed ? workflow.parameters.fields : [];
  renderParameterForm(el("workflow-fields"), workflowFields, "workflow-field-",
    typed ? {workflow: {namespace: workflow.namespace, name: workflow.name,
      version: workflow.version}, uploads: true, presets: true} : null);
}

// -- Parameter forms ------------------------------------------------------
// One renderer for every form generated from a Workflow's parameter
// declaration (run form and schedule form); see common/workflow_forms.py.

let workflowFields = [];
const LIST_KINDS = ["text_list", "emails"];
const PATH_KINDS = ["file", "folder", "upload"];

function comboControl(field, id) {
  // Pick or type (forms v2 `allow_other`): a text box with suggestions.
  const input = document.createElement("input"); input.type = "text";
  const list = document.createElement("datalist"); list.id = id + "-choices";
  input.setAttribute("list", list.id); input.autocomplete = "off";
  for (const choice of field.choices) {
    const option = document.createElement("option"); option.value = choice.value;
    if (choice.label && choice.label !== choice.value) option.label = choice.label;
    list.append(option);
  }
  if (field.default !== null && field.default !== undefined) input.value = String(field.default);
  input.placeholder = field.examples && field.examples.length
    ? "Pick or type, e.g. " + field.examples[0] : "Pick from the list or type a value";
  input.extras = [list];
  if (isDynamicChoice(field) && dynamicContext) {
    const refresh = document.createElement("button"); refresh.type = "button";
    refresh.className = "field-refresh"; refresh.append(text("Refresh list"));
    refresh.dataset.refreshFor = field.name;
    input.extras.push(refresh);
  }
  return input;
}

function uploadControl(field, id) {
  // A real upload (forms v2): files go to the Host now; the run carries paths.
  const input = document.createElement("input"); input.type = "file";
  input.multiple = !!field.multiple;
  if (field.accept && field.accept.length) input.accept = field.accept.join(",");
  input.dataset.paths = "[]"; input.dataset.pending = "0";
  const listed = document.createElement("ul"); listed.className = "upload-list";
  listed.id = id + "-files"; listed.setAttribute("aria-live", "polite");
  input.extras = [listed];
  return input;
}

function booleanLabels(field) {
  // The two choices in plain words (owner 2026-10-25): declared, or the
  // label and 「不要：<label>」; never a bare Yes/No.
  const head = String(field.label || "").replace(/[\s?？]+$/, "") || field.label;
  return [field.true_label || head, field.false_label || "不要：" + head];
}

function booleanControl(field, id) {
  // Two labelled radio options; a hidden checkbox keeps the value, so every
  // reader of `input.checked` (collect, fill, raw answers) is unchanged.
  const input = document.createElement("input"); input.type = "checkbox";
  input.hidden = true; input.tabIndex = -1; input.checked = field.default === true;
  const group = document.createElement("div"); group.className = "boolean-choices";
  group.setAttribute("role", "radiogroup"); group.id = id + "-choices";
  const radios = booleanLabels(field).map((label, index) => {
    const value = index === 0;
    const option = document.createElement("label"); option.className = "boolean-choice";
    const radio = document.createElement("input"); radio.type = "radio";
    radio.name = id + "-choice"; radio.value = value ? "true" : "false";
    radio.id = id + (value ? "-true" : "-false");
    radio.addEventListener("change", () => {
      if (!radio.checked) return;
      input.checked = value;
      input.dispatchEvent(new Event("input"));
      input.dispatchEvent(new Event("change"));
    });
    option.append(radio, text(" " + label)); group.append(option);
    return radio;
  });
  input.syncChoices = () => {
    radios[0].checked = input.checked; radios[1].checked = !input.checked;
  };
  input.syncChoices();
  input.extras = [group];
  return input;
}

function parameterControl(field, id) {
  const kind = field.kind;
  let input;
  if (kind === "boolean") {
    input = booleanControl(field, id);
  } else if (kind === "select" && field.allow_other && !field.multiple) {
    input = comboControl(field, id);
  } else if (kind === "upload" && dynamicContext && dynamicContext.uploads) {
    input = uploadControl(field, id);
  } else if (kind === "select" && isDynamicChoice(field) && dynamicContext) {
    input = document.createElement("select"); input.multiple = !!field.multiple;
    const waiting = document.createElement("option"); waiting.value = "";
    waiting.append(text("Loading choices…")); input.append(waiting);
    input.dataset.source = field.choices_source;
  } else if (kind === "select" && field.choices.length) {
    input = document.createElement("select"); input.multiple = !!field.multiple;
    if (!field.multiple) {
      const empty = document.createElement("option"); empty.value = "";
      empty.append(text("Select " + field.label)); input.append(empty);
    }
    for (const choice of field.choices) {
      const option = document.createElement("option"); option.value = choice.value;
      option.append(text(choice.label));
      const chosen = Array.isArray(field.default) ? field.default.includes(choice.value)
        : field.default === choice.value;
      option.selected = chosen; input.append(option);
    }
  } else if (LIST_KINDS.includes(kind) || (PATH_KINDS.includes(kind) && field.multiple)) {
    input = document.createElement("textarea"); input.rows = 3;
    input.placeholder = kind === "emails" ? "name@example.com (one per line)" : "One per line";
    if (Array.isArray(field.default)) input.value = field.default.join("\n");
  } else {
    input = document.createElement("input");
    input.type = kind === "integer" || kind === "number" ? "number"
      : kind === "date" ? "date" : kind === "boolean" ? "checkbox" : "text";
    if (kind === "integer") input.step = "1";
    if (kind === "number") input.step = "any";
    if (field.minimum !== null && field.minimum !== undefined) input.min = field.minimum;
    if (field.maximum !== null && field.maximum !== undefined) input.max = field.maximum;
    if (field.pattern) input.pattern = field.pattern;
    if (field.min_length) input.minLength = field.min_length;
    if (kind === "boolean") input.checked = field.default === true;
    else if (field.default !== null && field.default !== undefined) {
      input.value = String(field.default);
    }
    if (kind === "select" && field.choices_source) {
      input.placeholder = "Choices from " + field.choices_source;
    } else if (PATH_KINDS.includes(kind)) {
      input.placeholder = kind === "folder" ? "Folder path" : "File path";
    } else if (field.examples && field.examples.length) {
      input.placeholder = "e.g. " + field.examples[0];
    }
  }
  input.id = id; input.dataset.name = field.name; input.dataset.kind = kind;
  input.required = field.required && kind !== "boolean";
  return input;
}

let dynamicContext = null;

function isDynamicChoice(field) {
  // `ref:` published sets and `fn:` Host functions alike (forms v2).
  return field.kind === "select" && !!field.choices_source
    && (field.choices_source.startsWith("ref:") || field.choices_source.startsWith("fn:"));
}

function choiceDependencies(field) {
  const found = [...(field.needs || [])];
  for (const match of (field.choices_source || "").matchAll(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g)) {
    if (!found.includes(match[1])) found.push(match[1]);
  }
  return found;
}

function formatGiven(value, field) {
  if (typeof value === "boolean" && field && field.kind === "boolean") {
    return booleanLabels(field)[value ? 0 : 1];
  }
  if (value === true) return "是";
  if (value === false) return "否";
  return Array.isArray(value) ? value.join(", ") : String(value);
}

function renderParameterForm(container, fields, prefix, context) {
  dynamicContext = context || null;
  container.replaceChildren();
  const rows = {};
  let group = null;
  for (const field of fields) {
    if (field.group && field.group !== group) {
      const heading = document.createElement("p"); heading.className = "field-group";
      heading.append(text(field.group === "identity" ? "Identity" : field.group));
      container.append(heading);
    }
    group = field.group || null;
    const row = document.createElement("div"); row.className = "workflow-field";
    const id = prefix + field.name;
    const label = document.createElement("label");
    label.append(text(field.label + (field.required ? " *" : "")
      + (field.confirm ? " (needs confirmation)" : "")));
    const input = parameterControl(field, id);
    input.setAttribute("aria-describedby", id + "-help " + id + "-error");
    if (field.kind === "boolean") {
      // The label names the radio group; a label for the hidden box would flip it.
      label.id = id + "-label"; label.className = "boolean-legend";
      input.extras[0].setAttribute("aria-labelledby", label.id);
      input.extras[0].setAttribute("aria-describedby", id + "-help " + id + "-error");
    } else label.htmlFor = id;
    const help = document.createElement("p"); help.id = id + "-help";
    help.className = "hint"; help.append(text(field.help || ""));
    const error = document.createElement("p"); error.id = id + "-error";
    error.className = "field-error"; error.setAttribute("aria-live", "polite");
    input.addEventListener("input", () => {
      error.textContent = ""; input.removeAttribute("aria-invalid");
    });
    row.append(label, input, ...(input.extras || []), help, error); container.append(row);
    rows[field.name] = row;
    if (input.type === "file" && dynamicContext) {
      wireUpload(input, field, dynamicContext);
    }
  }
  if (dynamicContext && dynamicContext.collapseOptional) {
    // A form opened from a chat (owner 2026-10-25): optional fields nobody
    // gave a value for keep their defaults, folded away under one heading.
    const given = dynamicContext.values || {};
    const folded = fields.filter(field => !field.required
      && !Object.prototype.hasOwnProperty.call(given, field.name));
    if (folded.length) {
      const more = document.createElement("details"); more.className = "optional-fields";
      const heading = document.createElement("summary");
      heading.append(text("其他選項（使用預設值）"));
      more.append(heading, ...folded.map(field => rows[field.name]));
      container.append(more);
    }
  }
  // Values already given (a chat's "run X ..."), set before dynamic lists
  // load so each list keeps them selected.
  if (dynamicContext && dynamicContext.values) {
    fillParameterValues(container, fields, prefix, dynamicContext.values, false);
  }
  if (dynamicContext) wireDynamicChoices(container, fields, prefix, dynamicContext);
  if (dynamicContext && dynamicContext.presets) {
    offerLastValues(container, fields, prefix, dynamicContext);
  }
  dynamicContext = null;
}

function wireUpload(input, field, context) {
  const listed = input.extras[0];
  const show = () => {
    const paths = JSON.parse(input.dataset.paths || "[]");
    listed.replaceChildren(...paths.map(path => {
      const item = document.createElement("li");
      item.append(text(path.split(/[\\/]/).pop()));
      return item;
    }));
    if (Number(input.dataset.pending) > 0) {
      const busy = document.createElement("li"); busy.append(text("Uploading\u2026"));
      listed.append(busy);
    }
  };
  input.addEventListener("change", async () => {
    const chosen = Array.from(input.files || []);
    if (!field.multiple) input.dataset.paths = "[]";
    for (const file of chosen) {
      input.dataset.pending = String(Number(input.dataset.pending) + 1); show();
      try {
        const saved = await call("/api/workflow-uploads", {
          workflow: context.workflow, field: field.name,
          upload_set: context.uploadSet || "", filename: file.name,
          data: await readAsBase64(file),
        });
        context.uploadSet = saved.upload_set;
        const paths = field.multiple ? JSON.parse(input.dataset.paths || "[]") : [];
        paths.push(saved.path); input.dataset.paths = JSON.stringify(paths);
      } catch (failure) {
        const error = document.getElementById(input.id + "-error");
        if (error) error.textContent = file.name + " was not uploaded: "
          + (failure.code || failure.message);
      } finally {
        input.dataset.pending = String(Number(input.dataset.pending) - 1); show();
      }
    }
    input.value = "";
  });
}

async function offerLastValues(container, fields, prefix, context) {
  // Same as last time (forms v2): this member's last identity answers.
  let found;
  try { found = await call("/api/workflow-identity", {workflow: context.workflow}); }
  catch (failure) { return; }
  const values = found && found.values ? found.values : {};
  const names = fields.filter(field => Object.prototype.hasOwnProperty.call(values, field.name));
  if (!names.length || !container.isConnected) return;
  const button = document.createElement("button"); button.type = "button";
  button.className = "use-last";
  button.append(text("Use last values: " + names.map(field => {
    const value = values[field.name];
    return Array.isArray(value) ? value.join(", ") : String(value);
  }).join(" \u00b7 ")));
  button.addEventListener("click",
    () => fillParameterValues(container, names, prefix, values, true));
  container.prepend(button);
}

function fillParameterValues(container, fields, prefix, values, announce) {
  for (const field of fields) {
    if (!Object.prototype.hasOwnProperty.call(values, field.name)) continue;
    const input = container.querySelector("#" + CSS.escape(prefix + field.name));
    if (!input || input.type === "file") continue;
    const value = values[field.name];
    if (input.type === "checkbox") {
      input.checked = value === true;
      if (input.syncChoices) input.syncChoices();
    } else if (input.tagName === "TEXTAREA") {
      input.value = Array.isArray(value) ? value.join("\n") : String(value);
    } else if (input.tagName === "SELECT" && input.multiple) {
      const wanted = Array.isArray(value) ? value.map(String) : [String(value)];
      for (const item of wanted) {
        if (![...input.options].some(option => option.value === item)) {
          const option = document.createElement("option"); option.value = item;
          option.append(text(item)); input.append(option);
        }
      }
      for (const option of input.options) option.selected = wanted.includes(option.value);
    } else if (input.tagName === "SELECT"
        && ![...input.options].some(option => option.value === String(value))) {
      const option = document.createElement("option"); option.value = String(value);
      option.append(text(String(value))); input.append(option); input.value = String(value);
    } else input.value = String(value);
    if (announce) input.dispatchEvent(new Event("change"));
  }
}

function rawAnswers(container, fields, prefix) {
  const answers = {};
  for (const field of fields) {
    const input = container.querySelector("#" + CSS.escape(prefix + field.name));
    if (!input || input.type === "file") continue;
    answers[field.name] = field.kind === "boolean" ? input.checked : input.value.trim();
  }
  return answers;
}

async function refreshChoices(container, fields, prefix, context, field) {
  const input = container.querySelector("#" + CSS.escape(prefix + field.name));
  if (!input) return;
  const previous = input.value || (field.default == null ? "" : String(field.default));
  const ticked = input.multiple
    ? [...input.selectedOptions].map(option => option.value).filter(Boolean) : null;
  const placeholder = (label) => {
    const option = document.createElement("option"); option.value = "";
    option.append(text(label)); return option;
  };
  if (input.tagName === "INPUT") {
    // Pick or type: the list only suggests, so a missing list never blocks.
    const list = document.getElementById(input.getAttribute("list"));
    let listed = null;
    try {
      listed = await call("/api/workflow-options", {
        workflow: context.workflow, field: field.name,
        answers: rawAnswers(container, fields, prefix),
      });
    } catch (failure) { listed = null; }
    const choices = listed && listed.choices ? listed.choices : [];
    list.replaceChildren(...choices.map(choice => {
      const option = document.createElement("option"); option.value = choice.value;
      if (choice.label && choice.label !== choice.value) option.label = choice.label;
      return option;
    }));
    input.placeholder = listed && listed.waiting_for && listed.waiting_for.length
      ? "Answer " + listed.waiting_for.join(", ") + " first, or type a value"
      : choices.length ? "Pick from " + choices.length + " listed, or type a value"
      : "No list available right now; type a value";
    return;
  }
  let listed;
  try {
    listed = await call("/api/workflow-options", {
      workflow: context.workflow, field: field.name,
      answers: rawAnswers(container, fields, prefix),
    });
  } catch (failure) {
    input.replaceChildren(placeholder("Choices unavailable: " + failure.message)); return;
  }
  if (listed.waiting_for && listed.waiting_for.length) {
    input.replaceChildren(placeholder("Answer " + listed.waiting_for.join(", ") + " first"));
    return;
  }
  if (listed.unavailable) {
    input.replaceChildren(placeholder("The " + listed.set + " list has not been published yet"));
    return;
  }
  const options = listed.choices.map(choice => {
    const option = document.createElement("option"); option.value = choice.value;
    option.append(text(choice.label));
    option.selected = ticked ? ticked.includes(choice.value) : choice.value === previous;
    return option;
  });
  input.replaceChildren(...(input.multiple ? [] : [placeholder("Select " + field.label)]),
    ...options);
}

function wireDynamicChoices(container, fields, prefix, context) {
  const dynamic = fields.filter(isDynamicChoice);
  for (const field of dynamic) {
    refreshChoices(container, fields, prefix, context, field);
    const again = container.querySelector(
      "[data-refresh-for=\"" + CSS.escape(field.name) + "\"]");
    if (again) {
      again.addEventListener("click",
        () => refreshChoices(container, fields, prefix, context, field));
    }
    for (const name of choiceDependencies(field)) {
      const source = container.querySelector("#" + CSS.escape(prefix + name));
      if (source) {
        source.addEventListener("change",
          () => refreshChoices(container, fields, prefix, context, field));
      }
    }
  }
}

function collectParameterValues(container, fields, prefix) {
  const values = {};
  for (const field of fields) {
    const input = container.querySelector("#" + CSS.escape(prefix + field.name));
    if (!input) continue;
    const kind = field.kind;
    const fail = (message) => {
      const error = container.querySelector("#" + CSS.escape(prefix + field.name + "-error"));
      if (error) error.textContent = message;
      input.setAttribute("aria-invalid", "true"); input.focus();
      throw new Error(field.label + ": " + message);
    };
    let value;
    if (kind === "boolean") value = input.checked;
    else if (input.type === "file") {
      if (Number(input.dataset.pending) > 0) fail("Wait for the upload to finish.");
      const paths = JSON.parse(input.dataset.paths || "[]");
      value = !paths.length ? undefined : field.multiple ? paths : paths[0];
    } else if (input.tagName === "SELECT" && input.multiple) {
      value = [...input.selectedOptions].map(option => option.value);
      if (!value.length) value = undefined;
    } else if (input.tagName === "TEXTAREA") {
      value = input.value.split("\n").map(line => line.trim()).filter(Boolean);
      if (!value.length) value = undefined;
    } else {
      const raw = input.value.trim();
      if (raw === "") value = undefined;
      else if (kind === "integer") {
        if (!/^-?\d+$/.test(raw) || !Number.isSafeInteger(Number(raw))) {
          fail("Enter a whole number.");
        }
        value = Number(raw);
      } else if (kind === "number") {
        if (!Number.isFinite(Number(raw))) fail("Enter a number.");
        value = Number(raw);
      } else value = raw;
    }
    if (value === undefined) {
      if (field.required) fail("This field is required.");
      continue;
    }
    if (input.type !== "file" && !input.checkValidity()) {
      fail(input.validationMessage || "This value is not valid.");
    }
    if (field.confirm && value !== field.default && value !== false
        && !confirm("Confirm " + field.label + "?")) {
      fail("Not confirmed.");
    }
    values[field.name] = value;
  }
  return values;
}

// -- end Parameter forms

function workflowArguments() {
  if (el("workflow-fields").hidden) {
    const value = JSON.parse(el("workflow-arguments").value);
    if (!value || Array.isArray(value) || typeof value !== "object") {
      throw new Error("arguments must be one JSON object");
    }
    return value;
  }
  return collectParameterValues(el("workflow-fields"), workflowFields, "workflow-field-");
}

el("workflow-target").addEventListener("change", showWorkflowContract);
el("workflow-run").addEventListener("click", async () => {
  const button = el("workflow-run"), result = el("workflow-result");
  let argumentsValue;
  try {
    argumentsValue = workflowArguments();
  } catch (failure) {
    result.textContent = "Cannot run: " + failure.message;
    return;
  }
  const chosen = el("workflow-target").value;
  if (!chosen) return;
  button.disabled = true;
  result.textContent = "Workflow is running\u2026";
  try {
    const launched = await call("/api/workflows/run", {
      workflow: JSON.parse(chosen),
      arguments: argumentsValue,
      idempotency_key: "web-" + Date.now() + "-" + Math.random().toString(16).slice(2),
    });
    const outcome = launched.outcome, workflow = outcome.workflow;
    const identifiers = ["trace " + outcome.trace.trace_id,
      "request " + outcome.trace.request_id];
    if (workflow) identifiers.push("run " + workflow.run.run_id);
    result.textContent = identifiers.join(" | ") + "\n\n" + launched.answer;
    await loadAssets();
  } catch (failure) {
    result.textContent = "The Workflow did not finish: " + failure.message;
  } finally {
    button.disabled = false;
  }
});

function showKnowledgeDomain() {
  const chosen = el("knowledge-target").selectedOptions[0];
  el("knowledge-domain").textContent = chosen
    ? "Domain: " + chosen.dataset.domain : "No installed Knowledge.";
}

el("knowledge-target").addEventListener("change", showKnowledgeDomain);
el("knowledge-ask").addEventListener("click", async () => {
  const button = el("knowledge-ask"), result = el("knowledge-result");
  const question = el("knowledge-question").value.trim();
  const chosen = el("knowledge-target").value;
  if (!question || !chosen) return;
  button.disabled = true;
  result.textContent = "Knowledge is answering\u2026";
  el("knowledge-citations").replaceChildren(text("Waiting for grounded citations\u2026"));
  try {
    const selectedSkill = el("knowledge-skill").value;
    const answered = await call("/api/knowledge/ask", {
      asset: JSON.parse(chosen), question: question,
      ...(selectedSkill ? {skill: JSON.parse(selectedSkill)} : {}),
    });
    const outcome = answered.outcome;
    const harness = answered.harness;
    const summary = harness ? ("Skill " + harness.plan.skill.namespace + "/"
      + harness.plan.skill.name + "@" + harness.plan.skill.version
      + " | harness " + harness.phase + " | attempts " + (harness.retry_count + 1)
      + " | Raw citations " + (answered.evidence?.raw_citations || 0)
      + " | facet coverage not assessed\n") : "";
    result.textContent = summary + (outcome ? ("trace " + outcome.trace.trace_id
      + " | request " + outcome.trace.request_id + "\n\n") : "") + answered.answer;
    if (!answered.record) {
      el("knowledge-citations").replaceChildren(text("No grounded answer was returned."));
    } else {
      el("knowledge-citations").replaceChildren(table(
        ["#", "Evidence", "Location", "Passage"], answered.record.cited_passages,
        (passage, index) => {
          const citation = passage.citation;
          const location = [citation.raw_ref, citation.wiki_page,
            citation.page ? "page " + citation.page : "",
            citation.slide ? "slide " + citation.slide : "",
            citation.section ? "section " + citation.section : ""]
            .filter(Boolean).join(" \u00b7 ");
          return [index + 1, citation.kind, location || "\u2014", passage.text];
        }));
    }
  } catch (failure) {
    result.textContent = "The Knowledge question did not finish: " + failure.message;
    el("knowledge-citations").replaceChildren(text("No citations."));
  } finally {
    button.disabled = false;
  }
});

let sharedPlatform = {configured: false, catalog: [], decisions: [], note: ""};
let activeMarketKind = "skill";
// One card open at a time; outcomes stay on their card across re-renders.
let expandedMarketKey = "";
let busyMarketKey = "";
const marketOutcome = {};
const KIND_LETTER = {skill: "S", workflow: "W", bridge_extension: "E", application: "A"};
const KIND_TEXT = {skill: "Skill", workflow: "Workflow", bridge_extension: "Extension",
  application: "App"};
const VISIBILITY_TEXT = {private: "Only its owner", team: "Its owner's team",
  organization: "Everyone in the organization", public: "Everyone"};

function marketKey(item) {
  return item.kind + ":" + item.namespace + "/" + item.name + "@" + item.version;
}

function marketStatus(item) {
  return item.installed ? "installed" : item.authorized ? "selected" : "available";
}

function focusMarketHead(key) {
  const head = document.querySelector('.market-head[data-key="' + CSS.escape(key) + '"]');
  if (head) head.focus();
}

function toggleMarket(key) {
  expandedMarketKey = expandedMarketKey === key ? "" : key;
  renderMarketCards(); focusMarketHead(key);
}

// "+ Add to this Agent": select this exact version for this PC as the
// member on the shared platform, then run the verified sync (owner 2026-10-15).
async function marketSelect(item, add) {
  const key = marketKey(item);
  const asset = item.namespace + "/" + item.name + "@" + item.version;
  busyMarketKey = key;
  marketOutcome[key] = {text: add ? "Installing\u2026 (selecting it for this PC and "
    + "synchronizing)" : "Removing the selection\u2026", bad: false};
  renderMarketCards();
  let done;
  try {
    done = await call(add ? "/api/platform/add" : "/api/platform/unselect",
      {kind: item.kind, asset: asset});
  } catch (failure) {
    done = {ok: false, message: failure.message};
  }
  busyMarketKey = "";
  marketOutcome[key] = {text: done.message || done.code || "", bad: !done.ok,
    restart: !!done.restart_required};
  const status = el("platform-sync-result");
  status.textContent = marketOutcome[key].text; status.classList.toggle("bad", !done.ok);
  if (done.assets) {
    if (add && done.installed) {
      // Show the new Skill or Workflow in the list on the left, selected.
      activeCapabilityKind = item.kind === "skill" ? "skills" : "workflows";
      if (activeCapabilityFilter !== "installed") activeCapabilityFilter = "all";
      activeCapabilityKey = "installed:" + asset; freshCapabilityKey = activeCapabilityKey;
    }
    renderAssets(done.assets);
  }
  if (done.sync && done.sync.after) renderPlatform(done.sync.after); else renderMarketCards();
  focusMarketHead(key);
}

function marketActions(item) {
  const actions = document.createElement("div"); actions.className = "inline-actions";
  const busy = busyMarketKey === marketKey(item);
  const button = (label, className, add) => {
    const made = document.createElement("button"); made.type = "button";
    made.className = className; made.textContent = label;
    made.disabled = busy || !!busyMarketKey || !sharedPlatform.configured;
    if (busy) { made.setAttribute("aria-busy", "true"); made.textContent = add
    ? "Installing\u2026" : "Removing\u2026"; }
    made.addEventListener("click", () => marketSelect(item, add));
    actions.append(made);
    return made;
  };
  if (item.kind === "skill" || item.kind === "workflow") {
    if (!item.authorized) button("+ Add to this Agent", "go", true);
    else {
      if (!item.installed) button("Install now", "go", true);
      button("Remove selection", "btn", false);
    }
  } else if (sharedPlatform.member_portal_url) {
    const select = document.createElement("a"); select.href = marketplaceUrl(sharedPlatform);
    select.target = "_blank"; select.rel = "noopener noreferrer";
    select.textContent = item.kind === "bridge_extension"
      ? "Review Extension" : "Open in Marketplace";
    select.addEventListener("click", (event) => openPortal(event, item.kind === "application"
      ? {tab: "applications"} : {tab: "marketplace", asset: item.namespace + "/" + item.name
        + "@" + item.version}));
    actions.append(select);
  }
  return actions;
}

// One-click Member Portal (owner 2026-10-15): Agent Web asks the platform,
// with this PC's Personal Agent login, for a single-use one-minute ticket;
// only that ticket reaches the browser, in the URL fragment. Without a saved
// Personal Agent code the portal opens on its sign-in page.
async function openPortal(event, place = {}) {
  if (event && (event.ctrlKey || event.metaKey || event.shiftKey || event.button === 1)) return;
  if (event) event.preventDefault();
  const status = place.status || el("platform-sync-result");
  // Opened now, inside the click, so a popup blocker lets it through.
  const opened = window.open("about:blank", "_blank");
  if (opened) opened.opener = null;
  let reply;
  try {
    reply = await call("/api/platform/portal-link",
      {tab: place.tab || "", asset: place.asset || ""});
  } catch (failure) { reply = {ok: false, message: failure.message}; }
  if (!reply.ok || !reply.url) {
    if (opened) opened.close();
    status.textContent = "Could not open the Member Portal: " + (reply.message || reply.code
      || "no answer"); status.classList.add("bad");
    return;
  }
  if (opened) opened.location.replace(reply.url);
  else window.open(reply.url, "_blank", "noopener,noreferrer");
  status.classList.toggle("bad", !reply.signed_in);
  status.textContent = reply.signed_in ? "Opened the Member Portal, signed in as you."
    : "Opened the Member Portal sign-in page. " + (reply.message || "");
}

// Library card content (owner 2026-10-15): the published version itself
// (`assets/manifest`), read with this PC's member session and kept per
// version for this page. Every value is set as text; instructions go through
// renderMarkdown, and only http(s) links survive.
const marketContent = new Map();

function contentMarkdown(source) {
  const box = document.createElement("div"); box.className = "market-md";
  box.append(renderMarkdown(source));
  for (const link of box.querySelectorAll("a")) {
    let protocol = "";
    try { protocol = new URL(link.href).protocol; } catch (_) { protocol = ""; }
    if (protocol !== "http:" && protocol !== "https:") link.replaceWith(text(link.textContent));
  }
  return box;
}

function contentRef(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  const target = value.capability || value.identity || value;
  return target.namespace + "/" + target.name
    + (target.version ? "@" + target.version : target.version_range
      ? " " + target.version_range : "");
}

function contentNote(words) {
  const note = document.createElement("p"); note.className = "note"; note.append(text(words));
  return note;
}

function contentSection(title, ...kids) {
  const section = document.createElement("section");
  const heading = document.createElement("h4"); heading.append(text(title));
  section.append(heading, ...kids.filter(Boolean));
  return section;
}

function contentTable(columns, rows) {
  if (!rows.length) return contentNote("None.");
  return table(columns, rows, (row) => row.map((value) =>
    value === null || value === undefined || value === "" ? "—" : String(value)));
}

function shownValue(value) {
  if (value === null || value === undefined) return "";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function workflowContent(m) {
  const policy = (m.metadata && m.metadata.technical_policy) || {};
  const steps = (m.steps || []).map((step) => step.capability ? step : {capability: step});
  const list = document.createElement("ol"); list.className = "market-steps";
  for (const step of steps) {
    const li = document.createElement("li");
    const name = document.createElement("span"); name.className = "mono";
    name.append(text(contentRef(step.capability))); li.append(name);
    const inputs = step.inputs ? Object.keys(step.inputs) : [];
    if (inputs.length) li.append(text(" — inputs: " + inputs.join(", ")));
    list.append(li);
  }
  const parameters = (m.parameters || []).map((p) => [p.label, p.name,
    p.kind + (p.multiple ? " (several)" : ""), p.required ? "Yes" : "No", shownValue(p.default),
    p.choices_source || (p.choices || []).map((c) => c.label || c.value).join(", ")
      || (p.options || []).join(", ")]);
  const checks = (m.checks || []).map((c) => [c.check_id, String(c.kind || "").replace(/_/g, " "),
    Number.isInteger(c.step_index) ? "after step " + (c.step_index + 1) : "", c.pattern || ""]);
  const dependencies = m.dependencies || {};
  const effects = [["Risk", policy.risk || "low"],
    ["Required permissions", (policy.required_permissions || []).join(", ") || "none"],
    ["Approval required", policy.approval_required === false ? "No" : "Yes"],
    ["Side effect", m.occupies_machine
      ? "Occupies the machine: no other such run at the same time" : "None declared"],
    ["Runs", m.execution ? m.execution.mode : "Not declared"],
    ["Local capabilities", (dependencies.local_capabilities || []).join(", ") || "none"],
    ["Secrets it needs (names)", (m.secrets || []).map((x) => x.name).join(", ") || "none"]];
  const effectBox = document.createElement("div"); appendMeta(effectBox, effects);
  return [contentSection("What it does", contentMarkdown(m.description || "No description.")),
    contentSection("Steps", steps.length ? list : contentNote("No steps.")),
    contentSection("Run parameters", contentTable(
      ["Label", "Name", "Kind", "Required", "Default", "Choices / source"], parameters)),
    contentSection("Checks after the run", contentTable(
      ["Check", "Kind", "When", "Pattern"], checks)),
    contentSection("Risk, permissions and side effects", effectBox)];
}

function skillContent(m) {
  const summary = document.createElement("div");
  appendMeta(summary, [["Command", m.alias ? "/" + m.alias : "None"],
    ["Default command", m.default_command || "None"],
    ["Selector hint", m.selector_hint || "None"]]);
  const tools = (m.script_tools || []).map((tool) => [contentRef(tool)]);
  const guidance = m.harness_guidance;
  return [contentSection("Instructions", contentMarkdown(m.instructions || "No instructions.")),
    summary,
    contentSection("Commands", contentTable(["Command", "Runs", "Target"],
      (m.commands || []).map((c) => [c.name, c.kind === "workflow" ? "Workflow" : "Capability",
        contentRef(c.target)]))),
    contentSection("Keyword rules", contentTable(["Pattern", "Command"],
      (m.rules || []).map((r) => [r.pattern, r.command]))),
    contentSection("Script tools", contentTable(["Tool"], tools)),
    guidance ? contentSection("Harness guidance", contentNote("Domains: "
      + (guidance.domains || []).join(", ") + ". On failure: " + (guidance.fallback || "")
      + (guidance.max_retries ? " (up to " + guidance.max_retries + " retries)" : "") + "."))
      : null];
}

function contentFacts(item, reply) {
  if (!reply) {
    const compatibility = [item.runtime].concat(item.platforms || []).filter(Boolean).join(", ");
    return [["Version", item.version], ["Owner", item.owner],
      ["Who can use it", VISIBILITY_TEXT[item.visibility] || item.visibility],
      ["Categories", (item.categories || []).join(", ") || "None"],
      ["Provenance", (item.provenance || []).join("; ") || "Not recorded"],
      ["Depends on", (item.dependencies || []).join(", ") || "Nothing declared"],
      ["Compatibility", compatibility || "Not declared"],
      ["Lifecycle", item.lifecycle]];
  }
  const meta = (reply.package && reply.package.metadata) || {};
  const owner = reply.owner || meta.owner;
  const ownerText = !owner ? item.owner : typeof owner === "string" ? owner
    : owner.type === "user" ? owner.id : owner.id + " (" + owner.type + ")";
  const review = (label, decision) => decision && decision.status
    ? label + " " + decision.status + (decision.reviewer ? " by " + decision.reviewer : "") : "";
  const reviews = [review("Business", meta.business_approval),
    review("technical", meta.technical_policy)].filter(Boolean).join("; ");
  const others = (reply.versions || []).filter((v) => v !== item.version);
  const provenance = (meta.provenance || []).map((p) => typeof p === "string" ? p
    : [p.source, p.author && "by " + p.author, p.revision && "at " + p.revision]
      .filter(Boolean).join(" ")).join("; ");
  const rows = [["Version", item.version],
    ["Other versions", others.length ? others.join(", ") : "None"],
    ["Owner", ownerText || "Not recorded"],
    ["Co-editors", (reply.co_editors || []).join(", ") || "None"],
    ["Who can use it", VISIBILITY_TEXT[reply.visibility] || reply.visibility || "Not recorded"],
    ["Categories", (meta.categories || item.categories || []).join(", ") || "None"],
    ["Provenance", provenance || "Not recorded"],
    ["Reviewed", reviews || "Not recorded"],
    ["Published", reply.published_at ? new Date(reply.published_at).toLocaleString()
      : "Not recorded"],
    ["Depends on", (meta.dependencies || []).map(contentRef).join(", ") || "Nothing declared"]];
  if (reply.deprecation) rows.push(["Deprecated", reply.deprecation.reason
    + (reply.deprecation.replacement ? " (use " + reply.deprecation.replacement + ")" : "")]);
  return rows;
}

function drawMarketContent(content, facts, item, held) {
  facts.replaceChildren();
  appendMeta(facts, contentFacts(item, held && held.state === "ok" ? held.reply : null));
  if (!held || held.state === "loading") {
    content.replaceChildren(contentNote("Reading its content from the shared platform…"));
    content.setAttribute("aria-busy", "true");
    return;
  }
  content.removeAttribute("aria-busy");
  if (held.state === "bad") {
    const problem = contentNote(held.message); problem.classList.add("bad");
    problem.classList.add("section-status"); problem.dataset.problem = "";
    content.replaceChildren(problem);
    return;
  }
  const m = held.reply.manifest, kind = held.reply.package && held.reply.package.kind;
  const parts = m && kind === "workflow" && m.steps ? workflowContent(m)
    : m && kind === "skill" && "instructions" in m ? skillContent(m)
    : [contentSection("About", contentMarkdown((m && m.description) || item.description
      || "No description."))];
  content.replaceChildren(...parts.filter(Boolean));
}

function fillMarketContent(content, facts, item) {
  const key = marketKey(item), held = marketContent.get(key);
  drawMarketContent(content, facts, item, held);
  if (held) return;
  marketContent.set(key, {state: "loading"});
  call("/api/platform/asset-content", {kind: item.kind,
    asset: item.namespace + "/" + item.name + "@" + item.version})
    .then((reply) => reply.ok ? {state: "ok", reply: reply.content}
      : {state: "bad", message: reply.message || reply.code || "The content is unavailable."})
    .catch((failure) => ({state: "bad", message: "The content is unavailable: "
      + failure.message}))
    .then((answer) => {
      // Content is kept per version for this page; a refusal is asked again
      // the next time the card opens.
      if (answer.state === "ok") marketContent.set(key, answer); else marketContent.delete(key);
      const shownContent = document.querySelector(
        '.market-content[data-key="' + CSS.escape(key) + '"]');
      const shownFacts = document.querySelector(
        '.market-facts[data-key="' + CSS.escape(key) + '"]');
      if (shownContent && shownFacts) drawMarketContent(shownContent, shownFacts, item, answer);
    });
}

function marketCard(item, index) {
  const key = marketKey(item), status = marketStatus(item);
  const expanded = key === expandedMarketKey;
  const card = document.createElement("article"); card.className = "market-card";
  card.dataset.status = status;
  if (expanded) card.dataset.expanded = "";
  const headId = "market-head-" + index, detailId = "market-detail-" + index;
  const heading = document.createElement("h3");
  const head = document.createElement("button"); head.type = "button";
  head.className = "market-head"; head.id = headId; head.dataset.key = key;
  head.setAttribute("aria-expanded", String(expanded));
  head.setAttribute("aria-controls", detailId);
  const icon = document.createElement("span"); icon.className = "kind-icon";
  icon.dataset.kind = item.kind; icon.setAttribute("aria-hidden", "true");
  icon.append(text(KIND_LETTER[item.kind] || "?"));
  const names = document.createElement("span");
  const name = document.createElement("span"); name.className = "market-name";
  name.append(text(item.name));
  const identity = document.createElement("span"); identity.className = "identity";
  identity.append(text(item.namespace + " · v" + item.version));
  names.append(name, identity);
  const badge = document.createElement("span"); badge.className = "status-badge";
  badge.dataset.status = status;
  badge.append(text(status === "installed" ? "Installed"
    : status === "selected" ? "Selected" : "Available"));
  head.append(icon, names, badge);
  head.addEventListener("click", () => toggleMarket(key));
  heading.append(head);

  const summary = document.createElement("div"); summary.className = "market-summary";
  const description = document.createElement("p");
  description.append(text(item.description || "No description supplied."));
  const chips = document.createElement("div"); chips.className = "badges";
  chips.append(tag(false, "", KIND_TEXT[item.kind] || item.kind));
  for (const category of item.categories || []) chips.append(tag(false, "", category));
  chips.append(tag(false, "", "v" + item.version));
  summary.append(description, chips);
  card.append(heading, summary);

  const detail = document.createElement("div"); detail.className = "market-detail";
  detail.id = detailId; detail.setAttribute("role", "region");
  detail.setAttribute("aria-labelledby", headId); detail.hidden = !expanded;
  if (expanded) {
    const body = document.createElement("div"); body.className = "market-body";
    const content = document.createElement("div"); content.className = "market-content";
    content.dataset.key = key; content.setAttribute("aria-live", "polite");
    const aside = document.createElement("div"); aside.className = "market-aside";
    const overview = document.createElement("h4"); overview.append(text("Overview"));
    const facts = document.createElement("div"); facts.className = "market-facts";
    facts.dataset.key = key;
    aside.append(overview, facts);
    fillMarketContent(content, facts, item);
    if (sharedPlatform.assets_only && (item.kind === "skill" || item.kind === "workflow")) {
      const only = document.createElement("p"); only.className = "note";
      only.append(text("On this PC adding installs the file only: "
        + "permissions come from this PC's grants.json."));
      aside.append(only);
    }
    body.append(content, aside); detail.append(body);
    aside.append(marketActions(item));
    const outcome = document.createElement("p");
    outcome.className = "section-status market-outcome";
    outcome.setAttribute("role", "status");
    const said = marketOutcome[key];
    if (said) { outcome.append(text(said.text)); outcome.classList.toggle("bad", said.bad); }
    if (said && said.restart) {
      const restart = document.createElement("strong"); restart.className = "restart-note";
      restart.append(text(" Restart needed before the Agent can use it."));
      outcome.append(restart);
    }
    aside.append(outcome);
    detail.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { event.stopPropagation(); toggleMarket(key); }
    });
  }
  card.append(detail);
  // The whole card opens it; controls and links inside keep their own action.
  card.addEventListener("click", (event) => {
    if (expanded || event.target.closest("button, a, select, input")) return;
    toggleMarket(key);
  });
  return card;
}

function renderMarketCards() {
  const query = el("market-search").value.trim().toLowerCase();
  const category = el("market-category").value;
  const status = el("market-status").value;
  const rows = sharedPlatform.catalog.filter((item) => {
    const categories = item.categories || [];
    const matchesQuery = [item.name, item.namespace, item.description, item.owner, item.kind]
      .concat(categories).filter(Boolean).join(" ").toLowerCase().includes(query);
    const matchesKind = item.kind === activeMarketKind;
    const matchesCategory = category === "all" || categories.includes(category);
    const matchesStatus = status === "all"
      || (status === "installed" && item.installed)
      || (status === "authorized" && item.authorized)
      || (status === "available" && !item.authorized && !item.installed);
    return matchesQuery && matchesKind && matchesCategory && matchesStatus;
  });
  const cards = rows.map(marketCard);
  if (cards.length) el("catalog").replaceChildren(...cards);
  else {
    const empty = document.createElement("div"); empty.className = "empty";
    const message = activeMarketKind === "application"
      ? "Applications keep their own release lifecycle and are available in Marketplace."
      : (sharedPlatform.configured
        ? "No shared capabilities match these filters."
        : "Configure a Share Platform connection to discover team capabilities.");
    empty.append(text(message));
    if (activeMarketKind === "application" && sharedPlatform.member_portal_url) {
      const link = document.createElement("a"); link.href = sharedPlatform.member_portal_url;
      link.target = "_blank"; link.rel = "noopener noreferrer";
      link.addEventListener("click", (event) => openPortal(event, {tab: "applications"}));
      link.textContent = " Open Marketplace"; empty.append(link);
    }
    el("catalog").replaceChildren(empty);
  }
}

// The Marketplace opened from here already names this PC's Bridge.
function marketplaceUrl(platform) {
  return platform.member_portal_url
    + (platform.bridge_id ? "/#bridge=" + encodeURIComponent(platform.bridge_id) : "");
}

function renderPlatform(platform) {
  sharedPlatform = platform;
  el("platform-note").textContent = platform.note;
  el("platform-sync").disabled = !platform.configured;
  const portal = el("member-portal");
  if (platform.member_portal_url) {
    portal.href = marketplaceUrl(platform);
    portal.hidden = false;
  } else {
    portal.removeAttribute("href");
    portal.hidden = true;
  }
  for (const kind of ["skill", "workflow", "bridge_extension", "application"]) {
    const domKind = kind.replaceAll("_", "-");
    const count = platform.catalog.filter((item) => item.kind === kind).length;
    el("market-count-" + domKind).textContent = String(count);
    el("market-tab-" + domKind).setAttribute("aria-selected",
      String(activeMarketKind === kind));
  }
  const categorySelect = el("market-category"), previousCategory = categorySelect.value;
  const categories = [...new Set(platform.catalog.flatMap((item) => item.categories || []))]
    .sort();
  categorySelect.replaceChildren();
  const all = document.createElement("option"); all.value = "all";
  all.textContent = "All categories"; categorySelect.append(all);
  for (const value of categories) {
    const option = document.createElement("option"); option.value = value;
    option.textContent = value; categorySelect.append(option);
  }
  categorySelect.value = categories.includes(previousCategory) ? previousCategory : "all";
  renderMarketCards();
  el("decisions").replaceChildren(table(
    ["Kind", "Asset", "For", "On this machine"], platform.decisions,
    (d) => [d.kind, d.namespace + "/" + d.name + "@" + d.version, d.actor,
            tag(d.installed, "installed", "not installed")]));
}

async function loadPlatform() {
  renderPlatform(await call("/api/platform"));
}

el("member-portal").addEventListener("click",
  (event) => openPortal(event, {tab: "marketplace"}));
el("market-search").addEventListener("input", renderMarketCards);
el("market-category").addEventListener("change", renderMarketCards);
el("market-status").addEventListener("change", renderMarketCards);
for (const button of document.querySelectorAll(".market-tabs button")) {
  button.addEventListener("click", () => {
    activeMarketKind = button.dataset.kind;
    for (const other of document.querySelectorAll(".market-tabs button")) {
      other.setAttribute("aria-selected", String(other === button));
    }
    renderMarketCards();
  });
}

async function synchronizePlatform() {
  const button = el("platform-sync"), result = el("platform-sync-result");
  button.disabled = true; button.setAttribute("aria-busy", "true");
  const originalLabel = button.textContent; button.textContent = "Synchronizing…";
  result.textContent = "Synchronizing selected assets\u2026";
  try {
    const synchronized = await call("/api/platform/sync", {});
    renderPlatform(synchronized.after);
    loadAssets().catch(() => {});  // what it installed appears on the left too
    if (synchronized.status === "answered") {
      result.textContent = "Synchronization complete: " + synchronized.installed.length
        + " installed, " + synchronized.selections + " active selections."
        + (synchronized.assets_only ? " Installed files only; permissions come from this "
          + "PC's grants.json." : "");
    } else {
      const failure = synchronized.failure || {code: synchronized.status};
      result.textContent = "Synchronization " + synchronized.status + ": " + failure.code;
    }
  } catch (failure) {
    result.classList.add("bad");
    result.textContent = "Synchronization did not finish: " + failure.message;
  } finally {
    button.disabled = false; button.removeAttribute("aria-busy");
    button.textContent = originalLabel;
  }
}

el("platform-sync").addEventListener("click", synchronizePlatform);

// -- Publish to the shared platform (owner 2026-10-15) ----------------------
async function loadPublishing() {
  const data = await call("/api/publishing");
  el("publish-off").hidden = data.configured; el("publish-form").hidden = !data.configured;
  const select = el("publish-asset"), chosen = select.value;
  select.replaceChildren();
  for (const item of data.assets) {
    const option = document.createElement("option");
    option.value = item.kind + " " + item.asset;
    option.textContent = (item.kind === "skill" ? "Skill " : "Workflow ") + item.asset;
    select.append(option);
  }
  if ([...select.options].some((o) => o.value === chosen)) select.value = chosen;
  const status = el("publish-status");
  status.classList.toggle("bad", !!data.error);
  status.textContent = data.error ? data.error.message
    : data.configured ? "Connected to " + data.portal + " as your Personal Agent." : "";
  el("publish-list").replaceChildren(data.submissions.length ? table(
    ["Asset", "Kind", "Submitted", "Status", "Reviewer note", ""], data.submissions, (s) => [
      s.identity.namespace + "/" + s.identity.name + "@" + s.identity.version, s.kind,
      new Date(s.submitted_at).toLocaleString(), s.status, s.reason || "",
      s.status === "pending" ? kpButton("Withdraw", () => withdrawSubmission(s.submission_id))
        : ""]) : document.createTextNode(""));
}

// Who can use it, in words (owner decision 2026-10-15). The owner is the team
// the Skill or Workflow names when you belong to it, otherwise you.
const PUBLISH_AUDIENCE = {
  "": "Who can use it is what the Skill or Workflow says (its visibility).",
  team: "Only my team: members of the team it names as owner, if you belong to that "
    + "team; otherwise only you. You can change this later in the Member Portal.",
  organization: "Everyone in the organization can choose it once it is approved. "
    + "You can change this later in the Member Portal.",
};
function showPublishAudience() {
  el("publish-audience").textContent = PUBLISH_AUDIENCE[el("publish-visibility").value] || "";
}
el("publish-visibility").addEventListener("change", showPublishAudience);
showPublishAudience();

async function withdrawSubmission(id) {
  const reply = await call("/api/publishing/withdraw", {submission_id: id});
  el("publish-status").textContent = reply.ok ? "Withdrawn." : reply.message || reply.code;
  await loadPublishing();
}

el("publish-go").addEventListener("click", async () => {
  const button = el("publish-go"), status = el("publish-status");
  const [kind, asset] = el("publish-asset").value.split(" ");
  if (!asset) { status.textContent = "Choose a Skill or Workflow first."; return; }
  button.disabled = true; status.classList.remove("bad");
  status.textContent = "Sending " + asset + "…";
  try {
    const reply = await call("/api/publishing/submit", {kind, asset,
      change: el("publish-change").value, note: el("publish-note").value,
      visibility: el("publish-visibility").value});
    if (reply.ok) {
      const id = reply.submission.identity;
      status.textContent = id.namespace + "/" + id.name + "@" + id.version
        + " is waiting for an administrator's review.";
      el("publish-note").value = "";
    } else {
      status.classList.add("bad"); status.textContent = reply.message || reply.code;
    }
    await loadPublishing();
  } catch (failure) {
    status.classList.add("bad"); status.textContent = "Not sent: " + failure.message;
  } finally {
    button.disabled = false;
  }
});

async function loadCapabilities() {
  const refresh = el("cap-refresh"); refresh.disabled = true;
  refresh.setAttribute("aria-busy", "true"); refresh.textContent = "Refreshing…";
  try {
    await Promise.all([loadAssets(), loadPlatform(), loadPublishing()]);
  } finally {
    refresh.disabled = false; refresh.removeAttribute("aria-busy");
    refresh.textContent = "Refresh status";
  }
}

el("cap-refresh").addEventListener("click", () => {
  loadCapabilities().catch(showBootError);
});

// -- Schedules ------------------------------------------------------------
// Every value from the host becomes a text node; these builders add markup.
const SCHEDULE_EFFECTS = ["read", "write", "execute", "external_side_effect"];
const SCHEDULE_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function scheduleNode(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.append(text(value));
  return node;
}

function scheduleButton(label, onClick, go) {
  const button = scheduleNode("button", go ? "go" : "", label);
  button.type = "button";
  button.addEventListener("click", onClick);
  return button;
}

function scheduleTarget(target) {
  return target.namespace + "/" + target.name + "@" + target.version;
}

function scheduleRecurrence(rule) {
  const days = rule.kind === "weekly"
    ? " on " + rule.weekdays.map((day) => SCHEDULE_DAYS[day - 1] || String(day)).join(", ")
    : "";
  return rule.kind + days + " at " + String(rule.at).slice(0, 5) + " (" + rule.timezone + ")";
}

function scheduleRunRows(runs, actions) {
  const rows = scheduleNode("table", "schedule-runs");
  for (const run of runs) {
    const row = scheduleNode("tr");
    row.append(scheduleNode("td", "", run.due_at));
    row.append(scheduleNode("td", "", run.status));
    row.append(scheduleNode("td", "", (run.result_code || "pending")
      + (run.side_effect ? " [" + run.side_effect + "]" : "")));
    const cell = scheduleNode("td");
    if (run.status === "claimed" && actions && actions.resolve) {
      cell.append(actions.resolve(run));
    }
    row.append(cell);
    rows.append(row);
  }
  return rows;
}

function renderScheduleApprovals(container, runs, actions) {
  container.replaceChildren();
  if (!runs.length) {
    container.append(scheduleNode("div", "empty", "Nothing is waiting for approval."));
    return;
  }
  for (const run of runs) {
    const card = scheduleNode("div", "schedule-card");
    card.append(scheduleNode("h3", "", run.schedule_id + " — due " + run.due_at));
    card.append(scheduleNode("p", "schedule-warning",
      "This run can cause an external effect (" + (run.side_effect || "unknown")
      + "). Nothing has been sent."));
    const note = scheduleNode("input");
    note.setAttribute("aria-label", "Approval note");
    note.placeholder = "note (optional)";
    note.maxLength = 500;
    const bar = scheduleNode("div", "schedule-actions");
    bar.append(note,
      scheduleButton("Approve and run", () => actions.approve(run, note.value), true),
      scheduleButton("Deny", () => actions.deny(run, note.value)));
    card.append(bar);
    container.append(card);
  }
}

function renderScheduleList(container, data, actions) {
  container.replaceChildren();
  if (!data.schedules.length) {
    container.append(scheduleNode("div", "empty", "No schedules yet."));
    return;
  }
  for (const item of data.schedules) {
    const card = scheduleNode("div", "schedule-card");
    card.append(scheduleNode("h3", "", item.schedule_id + " — " + item.status));
    card.append(scheduleNode("p", "schedule-meta",
      item.target_kind + " " + scheduleTarget(item.target)
      + " · reaches " + (item.side_effect || "unknown effects")));
    card.append(scheduleNode("p", "schedule-meta",
      scheduleRecurrence(item.recurrence) + " · next " + item.next_due_at));
    const grant = item.grant;
    card.append(scheduleNode("p", "schedule-meta", grant
      ? "Granted up to " + grant.max_side_effect + " by " + grant.approved_by
        + (grant.expires_at ? " until " + grant.expires_at : "")
      : "Not granted: due runs stop as needs input."));
    if (item.blocked_by) {
      card.append(scheduleNode("p", "schedule-warning",
        "Blocked by an unresolved run. Open History to resolve it."));
    }
    const bar = scheduleNode("div", "schedule-actions");
    bar.append(item.status === "active"
      ? scheduleButton("Pause", () => actions.pause(item))
      : scheduleButton("Resume", () => actions.resume(item)));
    const effect = scheduleNode("select");
    effect.setAttribute("aria-label", "Highest effect to allow");
    for (const name of SCHEDULE_EFFECTS) {
      const option = scheduleNode("option", "", name);
      option.value = name;
      if (name === (item.side_effect || "read")) option.selected = true;
      effect.append(option);
    }
    const days = scheduleNode("input");
    days.type = "number"; days.min = "1"; days.max = "3650";
    days.placeholder = "days (optional)";
    days.setAttribute("aria-label", "Grant expires after days");
    bar.append(effect, days,
      scheduleButton("Grant", () => actions.grant(item, effect.value, days.value), true));
    if (grant) bar.append(scheduleButton("Revoke grant", () => actions.revoke(item)));
    bar.append(scheduleButton("History", () => actions.history(item)));
    card.append(bar);
    if (item.side_effect === "external_side_effect") {
      card.append(scheduleNode("p", "schedule-warning",
        "Sending is never automatic: every run waits for your approval."));
    }
    if (item.runs.length) card.append(scheduleRunRows(item.runs.slice(0, 3)));
    container.append(card);
  }
}

function renderScheduleHistory(container, history, actions) {
  container.replaceChildren();
  container.append(scheduleNode("h3", "", "History of " + history.schedule_id));
  if (!history.runs.length) container.append(scheduleNode("div", "empty", "No runs yet."));
  else container.append(scheduleRunRows(history.runs, actions));
  if (history.decisions.length) {
    container.append(scheduleNode("h3", "", "Decisions"));
    for (const decision of history.decisions) {
      container.append(scheduleNode("p", "schedule-meta",
        decision.decided_at + " · " + decision.kind + " " + decision.outcome
        + " by " + decision.decided_by + (decision.note ? ": " + decision.note : "")));
    }
  }
}

function scheduleResolveControl(run, onResolve) {
  const bar = scheduleNode("div", "schedule-actions");
  const outcome = scheduleNode("select");
  outcome.setAttribute("aria-label", "What actually happened");
  for (const [value, label] of [["not_run", "It did not run"],
    ["succeeded", "It succeeded"], ["failed", "It failed"]]) {
    const option = scheduleNode("option", "", label); option.value = value;
    outcome.append(option);
  }
  const note = scheduleNode("input");
  note.placeholder = "what you checked"; note.maxLength = 500;
  note.setAttribute("aria-label", "Resolution note");
  bar.append(outcome, note,
    scheduleButton("Resolve", () => onResolve(run, outcome.value, note.value), true));
  return bar;
}
// -- end Schedules renderers ----------------------------------------------

let scheduleData = {schedules: [], targets: [], awaiting_approval: []};

async function scheduleAction(path, body, success) {
  const result = el("schedule-result");
  try {
    const reply = await call(path, body);
    result.textContent = success(reply);
  } catch (failure) {
    result.textContent = "Not done: " + (failure.code || failure.message);
  }
  await loadSchedules();
}

const scheduleActions = {
  pause: (item) => scheduleAction("/api/schedules/pause", {schedule_id: item.schedule_id},
    () => item.schedule_id + " paused."),
  resume: (item) => scheduleAction("/api/schedules/resume", {schedule_id: item.schedule_id},
    () => item.schedule_id + " resumed."),
  grant: (item, effect, days) => {
    const body = {schedule_id: item.schedule_id, max_side_effect: effect};
    const count = Number(days);
    if (days && Number.isSafeInteger(count) && count > 0) {
      body.expires_at = new Date(Date.now() + count * 86400000).toISOString();
    }
    return scheduleAction("/api/schedules/grant", body,
      () => item.schedule_id + " may now run up to " + effect + ".");
  },
  revoke: (item) => scheduleAction("/api/schedules/revoke", {schedule_id: item.schedule_id},
    () => item.schedule_id + " grant revoked."),
  approve: (run, note) => scheduleAction("/api/schedules/approve",
    {idempotency_key: run.idempotency_key, note: note.trim() || null},
    (reply) => "Approved run finished as " + reply.run.status
      + " (" + (reply.run.result_code || "pending") + ")."),
  deny: (run, note) => scheduleAction("/api/schedules/deny",
    {idempotency_key: run.idempotency_key, note: note.trim() || null},
    () => "Run denied; nothing was sent."),
  history: (item) => showScheduleHistory(item.schedule_id),
  resolve: (run) => scheduleResolveControl(run, async (chosen, outcome, note) => {
    if (!window.confirm("Record that this run " + outcome.replace("_", " ")
        + "? Nothing will be run again.")) return;
    await scheduleAction("/api/schedules/resolve", {idempotency_key: chosen.idempotency_key,
      outcome: outcome, note: note.trim() || null, confirm: true},
      () => "Resolution recorded.");
    await showScheduleHistory(chosen.schedule_id);
  }),
};

async function showScheduleHistory(scheduleId) {
  const history = await call("/api/schedules/history?schedule_id="
    + encodeURIComponent(scheduleId));
  renderScheduleHistory(el("schedule-history"), history, scheduleActions);
}

function renderScheduleTargets() {
  const select = el("schedule-target");
  const previous = select.value;
  select.replaceChildren();
  for (const target of scheduleData.targets) {
    const option = document.createElement("option");
    option.value = JSON.stringify({kind: target.target_kind, target: target.target});
    option.append(text((target.target_kind === "workflow" ? "Workflow " : "Agent Task ")
      + scheduleTarget(target.target)));
    select.append(option);
  }
  if (previous) select.value = previous;
  showScheduleTargetFields();
}

function chosenScheduleTarget() {
  const value = el("schedule-target").value;
  if (!value) return null;
  const chosen = JSON.parse(value);
  return scheduleData.targets.find((item) => item.target_kind === chosen.kind
    && JSON.stringify(item.target) === JSON.stringify(chosen.target)) || null;
}

function showScheduleTargetFields() {
  const target = chosenScheduleTarget();
  const container = el("schedule-fields"); container.replaceChildren();
  el("schedule-target-note").textContent = target
    ? (target.description || "") + " · reaches " + (target.side_effect || "unknown effects")
    : "Nothing installed can be scheduled.";
  el("schedule-json-box").hidden = !target || target.typed;
  if (!target) return;
  renderParameterForm(container, target.fields, "schedule-field-",
    target.target_kind === "workflow" ? {workflow: target.target} : null);
}

function scheduleInputs() {
  const target = chosenScheduleTarget();
  if (target && !target.typed) {
    const value = JSON.parse(el("schedule-json").value || "{}");
    if (!value || Array.isArray(value) || typeof value !== "object") {
      throw new Error("runtime inputs must be one JSON object");
    }
    return value;
  }
  return collectParameterValues(el("schedule-fields"), target ? target.fields : [],
    "schedule-field-");
}

function renderScheduleDays() {
  const box = el("schedule-days"); box.replaceChildren();
  SCHEDULE_DAYS.forEach((name, index) => {
    const label = document.createElement("label");
    const box_ = document.createElement("input"); box_.type = "checkbox";
    box_.value = String(index + 1); box_.checked = index === 0;
    label.append(box_, text(" " + name)); box.append(label);
  });
  box.hidden = el("schedule-kind").value !== "weekly";
}

async function loadSchedules() {
  scheduleData = await call("/api/schedules");
  const loop = scheduleData.resident_loop || {running: false};
  el("schedule-loop").textContent = loop.running
    ? "This Agent checks due schedules every " + loop.interval_seconds + " seconds."
    : "This Agent is not checking schedules by itself. Start it with "
      + "`aep-host web --schedules` (or set schedules.resident_loop), or run "
      + "`aep-host schedules tick` from Windows Task Scheduler. Missed runs are caught up "
      + "once within " + scheduleData.catch_up_hours + " hours.";
  renderScheduleApprovals(el("schedule-approvals"), scheduleData.awaiting_approval,
    scheduleActions);
  renderScheduleList(el("schedule-list"), scheduleData, scheduleActions);
  renderScheduleTargets();
}

el("schedule-refresh").addEventListener("click", () => {
  loadSchedules().catch(showBootError);
});
el("schedule-kind").addEventListener("change", () => {
  el("schedule-days").hidden = el("schedule-kind").value !== "weekly";
});
el("schedule-target").addEventListener("change", showScheduleTargetFields);
el("schedule-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = el("schedule-form-result"), button = el("schedule-save");
  const target = chosenScheduleTarget();
  if (!target) { result.textContent = "Choose an installed target."; return; }
  let inputs;
  try { inputs = scheduleInputs(); }
  catch (failure) { result.textContent = "Cannot save: " + failure.message; return; }
  const kind = el("schedule-kind").value;
  const weekdays = kind === "weekly"
    ? [...el("schedule-days").querySelectorAll("input:checked")].map((box) => Number(box.value))
    : [];
  button.disabled = true;
  try {
    const reply = await call("/api/schedules/create", {
      schedule_id: el("schedule-id").value.trim(),
      target_kind: target.target_kind,
      target: target.target,
      recurrence: {kind: kind, timezone: el("schedule-timezone").value.trim(),
        at: el("schedule-at").value, weekdays: weekdays},
      runtime_inputs: inputs,
      initial_status: el("schedule-paused").checked ? "paused" : "active",
    });
    result.textContent = "Saved " + reply.schedule.definition.schedule_id
      + ". Grant it below before it can run unattended.";
    await loadSchedules();
  } catch (failure) {
    result.textContent = "Not saved: " + (failure.code || failure.message);
  } finally { button.disabled = false; }
});
el("schedule-timezone").value =
  (Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Taipei");
renderScheduleDays();

// -- Workspace navigation -------------------------------------------------

// -- Knowledge pipeline (docs/phases/KNOWLEDGE_K1.md) ----------------------

let kpSandbox = null;

async function pipeline(step, args) {
  const reply = await call("/api/knowledge/pipeline/call", {step, arguments: args || {}});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  return reply.data;
}

function kpStatus(message, bad) {
  const box = el("kp-status"); el("kp-status-text").textContent = message || "";
  box.classList.toggle("bad", !!bad);
}

async function kpRun(label, action) {
  // Every step shows how long it has been running, so a slow one (planning an
  // ingest, a merge, a lint over thousands of pages) never looks like nothing.
  kpStatus(label + "\u2026");
  const started = Date.now(), clock = el("kp-status-time");
  const timer = setInterval(() => {
    const seconds = Math.round((Date.now() - started) / 1000);
    clock.textContent = seconds >= 2 ? "running " + Math.floor(seconds / 60) + ":"
      + String(seconds % 60).padStart(2, "0") : "";
  }, 1000);
  try { await action(); kpStatus(""); }
  catch (failure) { kpStatus(label + " failed: " + (failure.code || failure.message), true); }
  finally { clearInterval(timer); clock.textContent = ""; }
}

function kpKey() {
  // A letter first: the request contracts take the key as a symbol.
  return "p" + Array.from(crypto.getRandomValues(new Uint8Array(12)),
                          (b) => b.toString(16).padStart(2, "0")).join("");
}

async function kpWithProgress(label, key, work) {
  // Long steps (copying the vault, pulling originals) report how far they are;
  // the bar follows them while the request runs (owner 2026-10-13).
  const box = el("kp-progress"), bar = el("kp-progress-bar"), note = el("kp-progress-text");
  box.hidden = false; bar.removeAttribute("value"); note.textContent = label + "\u2026";
  let live = true;
  (async () => {
    while (live) {
      try {
        const reply = await call("/api/knowledge/progress?key=" + key);
        const step = reply.progress;
        if (live && step && step.total) {
          bar.max = step.total; bar.value = step.done;
          note.textContent = label + ": " + step.done + " / " + step.total + " files"
            + (step.current ? " \u2014 " + step.current : "");
        } else if (live && step) {
          bar.removeAttribute("value");
          note.textContent = label + ": " + (step.current || step.phase);
        }
      } catch (failure) { /* the step's own result reports errors */ }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  })();
  try { return await work(); } finally { live = false; box.hidden = true; }
}

function kpButton(label, action) {
  const button = document.createElement("button"); button.type = "button";
  button.append(text(label)); button.addEventListener("click", action); return button;
}

async function xpLoad() { await loadReviews(); }
el("xp-save").addEventListener("click", () => rvRun("Saving", async () => {
  const chosen = document.querySelector('#xp-sensitivity input[name="xp-sens"]:checked');
  const reply = await call("/api/experience/settings", {
    retention_days: Number(el("xp-days").value), nightly: el("xp-nightly").checked,
    suggestions: el("xp-suggestions").checked,
    suggestion_sensitivity: chosen ? chosen.value : "normal",
    suggestion_max_requests: Number(el("xp-max-requests").value)});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  await xpLoad();
}));
el("xp-run").addEventListener("click", () => rvRun("Starting the review", async () => {
  await call("/api/experience/review", {});
  el("rv-counts").textContent = "The review runs in the background (see Tasks); new "
    + "proposals appear here when it is done.";
  setTimeout(() => loadReviews().catch(() => {}), 60000);
}));

// -- Reviews (E3-E5, owner 2026-10-13) --------------------------------------
const RV_KINDS = {rule_edit: "Rule change", knowledge_gap: "Missing knowledge",
  test_question: "Test question", issue: "Platform issue",
  skill_suggestion: "Suggested Skill"};
const SG_REASONS = [["not_useful", "Not useful"], ["one_off", "One-off"],
  ["wrong_grouping", "Wrong grouping"]];
const RV_ACCEPT = {rule_edit: "Accept: open a review sandbox",
  test_question: "Accept: draft it in a review sandbox",
  knowledge_gap: "Accept: add to the gap list",
  issue: "Accept: track as an issue"};
let rvTab = "proposed", rvData = null;

async function rvRun(label, action) {
  el("rv-counts").textContent = label + "\u2026";
  try { await action(); }
  catch (failure) { el("rv-counts").textContent = label + " failed: "
    + (failure.code || failure.message); }
}

async function rvDecide(proposal, action, given) {
  let reason = null, reasonCode = null;
  if (given) { reason = given.reason || null; reasonCode = given.reason_code || null; }
  else if (action === "reject") {
    reason = prompt("Why is this proposal wrong or not worth doing? (recorded, so the same "
      + "cases are not proposed again)");
    if (!reason || !reason.trim()) return;
  }
  await rvRun("Saving your decision", async () => {
    const reply = await call("/api/reviews/decide",
      {proposal_id: proposal.proposal_id, action, reason, reason_code: reasonCode});
    if (!reply.ok) {
      const problem = new Error(reply.code); problem.code = reply.code; throw problem;
    }
    rvShow(reply);
    if (action === "accept" && ["rule_edit", "test_question"].includes(proposal.kind)) {
      setTimeout(() => loadReviews().catch(() => {}), 4000);
    }
  });
}

async function rvOpenSandbox(sandboxId) {
  await selectPrimaryTab("knowledge");
  const listed = await pipeline("sandbox-list");
  const item = listed.sandboxes.find((s) => s.sandbox_id === sandboxId);
  if (item) await kpRun("Opening", () => kpOpen(item));
}

// -- Suggested Skill card (SKILL_SUGGESTIONS S2): no draft yet --------------
async function rvOpenConversation(sessionId, messageId, where) {
  // The person's own conversation, opened at the request (each turn block
  // carries the id of the message it asked).
  const listed = await call("/api/conversations?session_id=" + encodeURIComponent(sessionId));
  if (!listed.selected || listed.selected.session_id !== sessionId) {
    where.textContent = "This conversation was deleted."; where.className = "note sg-gone";
    return;
  }
  selectPrimaryTab("ask");
  activeConversation = sessionId; log.replaceChildren();
  await loadChat(sessionId);
  const target = [...log.querySelectorAll(".turn")]
    .find((block) => block.dataset.askedId === messageId);
  if (target) {
    for (const old of log.querySelectorAll(".turn.sg-target")) old.classList.remove("sg-target");
    target.classList.add("sg-target");
    target.scrollIntoView({block: "center"}); target.focus({preventScroll: true});
  }
}

function sgIgnoreBox(item, actions) {
  const box = document.createElement("div"); box.className = "sg-ignore";
  const ask = document.createElement("p"); ask.className = "note";
  ask.append(text("Why ignore it? Optional. It is recorded, and this work is suggested "
    + "again only if you repeat it often enough afterwards."));
  const picks = document.createElement("div"); picks.className = "sg-picks";
  picks.setAttribute("role", "group"); picks.setAttribute("aria-label", "Reason");
  let code = null;
  for (const [key, label] of SG_REASONS) {
    const pick = kpButton(label, () => {
      code = code === key ? null : key;
      for (const other of picks.children) {
        other.setAttribute("aria-pressed", String(other.dataset.code === code));
      }
    });
    pick.dataset.code = key; pick.setAttribute("aria-pressed", "false");
    picks.append(pick);
  }
  const note = document.createElement("input"); note.type = "text"; note.maxLength = 500;
  note.placeholder = "Anything else (optional)"; note.setAttribute("aria-label", "Comment");
  const confirm = kpButton("Ignore it", () => rvDecide(item, "reject",
    {reason: note.value.trim() || null, reason_code: code}));
  confirm.className = "go"; confirm.dataset.action = "confirm-ignore";
  const cancel = kpButton("Cancel", () => { box.remove(); actions.hidden = false; });
  const row = document.createElement("div"); row.className = "kp-actions";
  row.append(confirm, cancel);
  box.append(ask, picks, note, row);
  return box;
}

function sgCard(item) {
  const card = document.createElement("div"); card.className = "rv-card sg-card";
  card.dataset.proposalId = item.proposal_id; card.dataset.status = item.status;
  const s = item.suggestion || {evidence: [], matched_words: [], tool_shape: []};
  const kind = document.createElement("div"); kind.className = "sg-kind";
  kind.append(text(RV_KINDS.skill_suggestion));
  const head = document.createElement("h3");
  head.append(text(s.task || item.text || "(unnamed)"));
  const meta = document.createElement("p"); meta.className = "note sg-counts";
  meta.append(text(s.requests + " requests \u00b7 " + s.sessions + " conversations \u00b7 "
    + s.days + " days \u00b7 found " + (item.created_at || "").slice(0, 10)
    + (s.seen_more ? " \u00b7 seen " + s.seen_more + " more times since" : "")));
  const why = document.createElement("p"); why.className = "sg-why";
  const parts = [];
  if (s.matched_words.length) parts.push("matched words: " + s.matched_words.join(", "));
  if (s.tool_shape.length) parts.push("same tools: " + s.tool_shape.join(" \u2192 "));
  why.append(text("Why: " + (parts.join("; ") || "the nightly review grouped these requests")
    + (s.note ? " (" + s.note + ")" : "")));
  const listHead = document.createElement("p"); listHead.className = "note";
  listHead.append(text("Your requests (open one to see that conversation):"));
  const list = document.createElement("ul"); list.className = "sg-evidence";
  for (const entry of s.evidence) {
    const row = document.createElement("li");
    if (entry.gone) {
      const when = document.createElement("time"); when.append(text(entry.date));
      const gone = document.createElement("span"); gone.className = "note sg-gone";
      gone.append(text("This conversation was deleted."));
      row.append(when, text(" "), gone); list.append(row); continue;
    }
    const open = document.createElement("button"); open.type = "button";
    const when = document.createElement("time"); when.append(text(entry.date));
    open.append(when, text(entry.excerpt));
    const where = document.createElement("span"); where.className = "note";
    open.addEventListener("click", () => rvOpenConversation(entry.session_id,
      entry.message_id, where).catch(showBootError));
    row.append(open, where); list.append(row);
  }
  const later = document.createElement("p"); later.className = "note";
  later.append(text("No draft yet: making a Skill from a suggestion comes in a later version."));
  card.append(kind, head, meta, why, listHead, list, later);
  const actions = document.createElement("div"); actions.className = "kp-actions";
  if (item.status === "proposed" || item.status === "snoozed") {
    const ignore = kpButton("Ignore", () => {
      actions.hidden = true; card.append(sgIgnoreBox(item, actions));
    });
    ignore.dataset.action = "ignore"; actions.append(ignore);
    if (item.status === "proposed") {
      const snooze = kpButton("Snooze 7 days", () => rvDecide(item, "snooze"));
      snooze.dataset.action = "snooze"; actions.append(snooze);
    }
    if (item.snooze_until) actions.append(text(" snoozed until " + item.snooze_until.slice(0, 10)));
  } else {
    const picked = (SG_REASONS.find(([key]) => key === item.reason_code) || [])[1];
    const said = [picked, item.reason].filter(Boolean);
    const why2 = document.createElement("p"); why2.className = "note";
    why2.append(text("Ignored by " + item.decided_by
      + (said.length ? ": " + said.join(" \u2014 ") : "")));
    card.append(why2);
    const reopen = kpButton("Reopen", () => rvDecide(item, "reopen"));
    reopen.dataset.action = "reopen"; actions.append(reopen);
  }
  card.append(actions);
  return card;
}

function rvCard(item) {
  if (item.kind === "skill_suggestion") return sgCard(item);
  const card = document.createElement("div"); card.className = "rv-card";
  const head = document.createElement("h3");
  head.append(text((RV_KINDS[item.kind] || item.kind)
    + (item.target ? " \u2014 " + item.target : "")));
  const meta = document.createElement("p"); meta.className = "note";
  meta.append(text("Cause: " + (item.cause || "-")
    + " \u00b7 confidence " + (item.confidence || "-")
    + " \u00b7 " + item.case_ids.length + " case(s) \u00b7 " + item.group
    + " \u00b7 " + (item.created_at || "").slice(0, 10)));
  const diagnosis = document.createElement("p"); diagnosis.append(text(item.diagnosis));
  const proposal = document.createElement("div"); proposal.className = "rv-text";
  proposal.append(text(item.text || "(no text)"));
  card.append(head, meta, diagnosis, proposal);
  if (item.confirm) {
    const confirm = document.createElement("p"); confirm.className = "note";
    confirm.append(text("Would confirm it: " + item.confirm)); card.append(confirm);
  }
  const actions = document.createElement("div"); actions.className = "kp-actions";
  if (item.status === "proposed" || item.status === "snoozed") {
    const accept = kpButton(RV_ACCEPT[item.kind] || "Accept", () => rvDecide(item, "accept"));
    accept.className = "go";
    actions.append(accept, kpButton("Reject", () => rvDecide(item, "reject")));
    if (item.status === "proposed") actions.append(kpButton("Snooze 7 days",
      () => rvDecide(item, "snooze")));
    if (item.snooze_until) actions.append(text(" snoozed until " + item.snooze_until.slice(0, 10)));
  } else if (item.status === "accepted") {
    const where = document.createElement("p");
    where.append(text("Accepted by " + item.decided_by + " \u2014 "
      + (item.route_note || item.route)
      + (item.outcome ? " \u00b7 " + item.outcome : "")));
    card.append(where);
    if ((item.route || "").startsWith("sandbox:")) {
      actions.append(kpButton("Open in Knowledge", () => rvOpenSandbox(item.route.slice(8))));
    }
    actions.append(kpButton("Mark done", () => rvDecide(item, "done")),
                   kpButton("Reject", () => rvDecide(item, "reject")));
  } else {
    const why = document.createElement("p"); why.className = "note";
    why.append(text(item.status + " by " + item.decided_by + (item.reason ? ": " + item.reason : "")
      + (item.outcome ? " \u00b7 " + item.outcome : "")));
    card.append(why); actions.append(kpButton("Reopen", () => rvDecide(item, "reopen")));
  }
  card.append(actions);
  return card;
}

function rvShow(data) {
  rvData = data;
  const counts = data.counts || {};
  el("rv-counts").textContent = [["proposed", "to decide"], ["accepted", "accepted"],
    ["pushed", "pushed"], ["snoozed", "snoozed"], ["rejected", "rejected"], ["done", "done"]]
    .filter(([key]) => counts[key]).map(([key, label]) => counts[key] + " " + label)
    .join(" \u00b7 ")
    || "No proposals yet.";
  const wanted = (item) => rvTab === "closed" ? ["rejected", "done"].includes(item.status)
    : item.status === rvTab;
  const shown = data.proposals.filter(wanted);
  el("rv-list").replaceChildren(...(shown.length ? shown.map(rvCard)
    : [Object.assign(document.createElement("p"), {className: "empty",
        textContent: "Nothing here."})]));
  const gaps = data.proposals.filter((p) => p.kind === "knowledge_gap" && p.status === "accepted");
  el("rv-gaps").replaceChildren(table(["Missing knowledge", "Where", ""], gaps, (gap) => [
    gap.text, gap.target, kpButton("Mark done", () => rvDecide(gap, "done"))]));
  el("xp-days").value = data.settings.retention_days;
  el("xp-nightly").checked = data.settings.nightly;
  el("xp-suggestions").checked = data.settings.suggestions;
  el("xp-max-requests").value = data.settings.suggestion_max_requests;
  el("xp-sensitivity").replaceChildren(...(data.sensitivities || []).map((row) => {
    const label = document.createElement("label");
    const radio = document.createElement("input"); radio.type = "radio"; radio.name = "xp-sens";
    radio.value = row.key; radio.checked = row.key === data.settings.suggestion_sensitivity;
    const words = document.createElement("span");
    const name = document.createElement("strong"); name.append(text(row.label + ": "));
    words.append(name, text(row.describe + (row.key === "normal" ? " (default)" : "")));
    label.append(radio, words);
    return label;
  }));
  el("xp-summary").textContent = " \u2014 " + data.open + " open cases"
    + (data.last_review ? "; last review " + data.last_review.slice(0, 16) : "")
    + (data.last_error ? "; last attempt failed: " + data.last_error : "");
  el("xp-report").replaceChildren(data.review ? renderMarkdown(data.review.markdown)
    : text("No review yet."));
}

async function loadReviews() {
  const reply = await call("/api/reviews");
  if (reply.ok) rvShow(reply);
}
for (const tab of document.querySelectorAll(".rv-tabs [data-rv]")) {
  tab.addEventListener("click", () => {
    rvTab = tab.dataset.rv;
    for (const other of document.querySelectorAll(".rv-tabs [data-rv]")) {
      other.setAttribute("aria-selected", String(other === tab));
    }
    if (rvData) rvShow(rvData);
  });
}
el("rv-refresh").addEventListener("click", () => rvRun("Reading", loadReviews));

async function loadKnowledge() {
  const info = await call("/api/knowledge/pipeline");
  el("kp-disabled").hidden = info.enabled; el("kp-main").hidden = !info.enabled;
  el("kp-stepper").hidden = !info.enabled;
  if (!info.enabled) return;
  // Before the steps' own reads: a person without the pipeline's grants still sees this.
  askableLoad().catch((failure) => { el("kp-askable").textContent = failure.message; });
  const base = el("kp-base"); base.replaceChildren();
  for (const vault of info.vaults || info.bases.map((name) => ({name}))) {
    const option = document.createElement("option"); option.value = vault.name;
    option.append(text(vault.name + (vault.project ? " — project vault (the Agent's "
      + vault.asset + ")" : " — test vault"))); base.append(option);
  }
  await kpLoadScopes();
  const listed = await pipeline("sandbox-list");
  const box = el("kp-sandboxes"); box.replaceChildren();
  if (!listed.sandboxes.length) box.append(text("No sandbox yet."));
  for (const item of listed.sandboxes) {
    box.append(kpButton(item.label + " · " + (item.scope || "whole vault") + " ("
      + item.base_name + ")",
      () => kpRun("Opening", () => kpOpen(item))));
  }
  kpRepoPrefix = info.repo_prefix || "repo.";
  const repos = el("kp-repos"); repos.replaceChildren();
  if (!(info.repos || []).length) repos.append(text("還沒有知識庫。"));
  for (const repo of info.repos || []) {
    const item = kpRepoItem(repo);
    repos.append(kpButton(item.label + (repo.reachable ? "" : "（讀不到共用資料夾）"),
      () => kpRun("Opening", () => kpOpen(item))));
  }
  const open = kpSandbox && (kpSandbox.repo
    ? (info.repos || []).some((r) => r.id === kpSandbox.repo)
    : listed.sandboxes.some((s) => s.sandbox_id === kpSandbox.sandbox_id));
  if (!open) kpSandbox = null;
  if (!kpSandbox) kpStage("pull", false);
}

// -- Wiki knowledge repositories (knowledge repositories R4b) -----------------------
// A repository opens like a sandbox under the id `repo.<id>`: every step runs on
// its working folder and what a step writes becomes a change to commit. Its
// 「版本」 area replaces push, refresh and the candidate in step 3.
let kpRepoPrefix = "repo.";

// Whether the general chat can ask each vault, and why not (BI_VAULT_ASKING V2).
function askableRow(entry, reload) {
  const row = document.createElement("div"); row.className = "note";
  row.dataset.askable = entry.id;
  const head = document.createElement("strong");
  head.append(text(entry.title + "：" + (entry.askable ? "可以在對話裡問" : "還不能在對話裡問")));
  row.append(head);
  if (entry.reads && entry.reads.tag) row.append(text("（發佈版本 " + entry.reads.tag + "）"));
  if (entry.reasons.length) {
    const list = document.createElement("ul");
    for (const reason of entry.reasons) {
      const item = document.createElement("li");
      item.append(text(reason.message + (reason.fix ? "：" + reason.fix : "")));
      list.append(item);
    }
    row.append(list);
  }
  const propose = (action) => async () => {
    try {
      const made = await call("/api/knowledge/askable/propose", {repo: entry.id, action});
      row.append(renderActionCard(made.card, reload));
    } catch (failure) { row.append(text(failure.message)); }
  };
  if (entry.reasons.some((reason) => reason.code === "not_bound")) {
    row.append(kpButton("讓 Agent 可以問這個知識庫", propose("bind")));
  } else if (entry.kind === "wiki") {
    row.append(kpButton("解除 Agent 的綁定", propose("unbind")));
  }
  return row;
}

async function askableLoad() {
  const report = await call("/api/knowledge/askable");
  const repos = el("kp-askable"), vaults = el("bi-b-askable");
  repos.replaceChildren(); vaults.replaceChildren();
  for (const note of report.notes || []) {
    const line = document.createElement("p"); line.className = "note";
    line.append(text(note.message)); repos.append(line);
  }
  const again = () => askableLoad().catch(() => {});
  for (const entry of report.repos || []) repos.append(askableRow(entry, again));
  const shown = biVaultOf(biDataset());
  for (const entry of report.vaults || []) {
    if (shown && shown.id === entry.id) vaults.append(askableRow(entry, again));
  }
}

function kpRepoItem(repo) {
  const id = kpRepoPrefix + repo.id;
  return {sandbox_id: id, base_name: id, label: repo.title || repo.id, scope: null,
          repo: repo.id};
}

function kpRepoMode() {
  const mode = el("kp-repo-mode").value;
  el("kp-repo-source-box").hidden = mode !== "import";
  el("kp-repo-title-box").hidden = mode === "join";
  el("kp-repo-path-l").textContent = mode === "join"
    ? "知識庫資料夾（別人分享給你、裡面有 repo.json 的資料夾）"
    : "放知識庫的資料夾（例如 OneDrive 上的共用資料夾）";
}
el("kp-repo-mode").addEventListener("change", kpRepoMode);
kpRepoMode();

async function kpRepoCall(path, body) {
  // The repository routes answer {ok: false, message} in words; show those.
  let reply;
  try { reply = await call("/api/knowledge/repos" + path, body); }
  catch (failure) {
    throw new Error((failure.payload && failure.payload.message) || failure.message);
  }
  if (reply && reply.ok === false) throw new Error(reply.message || reply.code);
  return reply;
}

function kpRepoPath(action) {
  return "/" + encodeURIComponent(kpSandbox.repo) + "/" + action;
}

el("kp-repo-form").addEventListener("submit", (event) => {
  event.preventDefault();
  kpRun("新增知識庫", async () => {
    const mode = el("kp-repo-mode").value, path = el("kp-repo-path").value.trim();
    const body = mode === "join" ? {path}
      : {path, title: el("kp-repo-title").value.trim(),
         ...(mode === "import" ? {source: el("kp-repo-source").value.trim()} : {})};
    if (mode === "create" && !body.title) throw new Error("請填名稱");
    const made = await kpRepoCall(mode === "create" ? "" : "/" + mode, body);
    for (const id of ["kp-repo-source", "kp-repo-path", "kp-repo-title"]) el(id).value = "";
    await loadKnowledge();
    await kpOpen(kpRepoItem({id: made.repo.id, title: made.repo.title}));
  });
});

async function kpRepoSettings() {
  const chosen = (await kpRepoCall(kpRepoPath("settings"))).settings;
  el("kp-intake").value = chosen.intake || ""; el("kp-questions").value = chosen.questions || "";
  el("kp-repo-saved").textContent = "";
}
el("kp-repo-save").addEventListener("click", () => kpRun("儲存資料夾", async () => {
  await kpRepoCall(kpRepoPath("settings"), {intake: el("kp-intake").value.trim(),
                                            questions: el("kp-questions").value.trim()});
  await kpOpen(kpSandbox);
  el("kp-repo-saved").textContent = "已儲存。";
}));

function kpVerValue(value) {
  if (value === null || value === undefined) return "（沒有）";
  let shown;
  if (typeof value !== "object") shown = String(value);
  else if ("heading" in value || "body" in value) {
    shown = [value.heading, value.body].filter(Boolean).join(" ");
  } else if ("text" in value) shown = value.text;
  else if ("file" in value) shown = value.file;
  else if ("revision" in value) shown = "第 " + value.revision + " 版";
  else shown = JSON.stringify(value);
  shown = String(shown).replace(/\s+/g, " ").trim();
  if (!shown) return "（空）";
  return shown.length > 160 ? shown.slice(0, 160) + "\u2026" : shown;
}

function kpVerChanges(changes) {
  const list = bh("ul", "");
  for (const change of changes.slice(0, 50)) {
    list.append(bh("li", "", bh("strong", "", change.label || change.unit), "：",
      kpVerValue(change.before), " \u2192 ", kpVerValue(change.after)));
  }
  if (changes.length > 50) list.append(bh("li", "note", "還有 " + (changes.length - 50) + " 項"));
  return list;
}

function kpVerAsk(where, label, value, go, run) {
  // One inline question (a purpose, a tag name) under the row that asked it.
  where.querySelector(".kp-ver-ask")?.remove();
  const input = document.createElement("input");
  input.maxLength = 500; input.value = value || ""; input.setAttribute("aria-label", label);
  const row = bh("div", "kp-ver-ask", bh("span", "", label), input);
  const ok = kpButton(go, () => kpRun(go, async () => {
    const answer = input.value.trim();
    if (!answer) { input.focus(); return; }
    await run(answer);
  }));
  ok.className = "go";
  row.append(ok, kpButton("取消", () => row.remove()));
  where.append(row); input.focus();
}

function kpVerSay(message, bad) {
  const box = el("kp-ver-result"); box.replaceChildren();
  if (message) box.append(bh("p", bad ? "kp-warn" : "note", message));
}

async function kpVerShow() {
  const [state, pending, history] = await Promise.all([kpRepoCall(kpRepoPath("status")),
    kpRepoCall(kpRepoPath("pending")), kpRepoCall(kpRepoPath("history?limit=30"))]);
  const reads = state.reads || {};
  el("kp-ver-reads").textContent = !state.reachable
    ? "現在讀不到共用資料夾（OneDrive 沒有同步或路徑不對）：可以繼續判讀，但不能 push。"
    : reads.tag ? "Agent 讀的是發佈版本「" + reads.tag
      + "」；之後 push 的內容要再發佈，Agent 才會讀到。"
    : "還沒有發佈過：Agent 讀的是大家已 push 的最新內容（不含你還沒 push 的改動）。";
  el("kp-ver-state").textContent = state.reachable ? "別人 push 了還沒套用的 " + state.behind
    + " 個・你還沒 push 的 commit " + state.ahead + " 個・還沒 commit 的改動 " + state.uncommitted
    + " 個・上次同步 " + (state.last_sync ? biTime(state.last_sync) : "\u2014") : "";
  const box = el("kp-ver-pending"); box.replaceChildren();
  const changes = pending.uncommitted || [], commits = pending.commits || [];
  const files = pending.files || [], uncommitted = changes.length + files.length;
  if (!uncommitted && !commits.length) {
    box.append(bh("p", "note", "沒有：大家看到的就是你的內容。"));
  }
  if (changes.length) {
    box.append(bh("p", "", "還沒 commit 的改動 " + changes.length + " 項："),
      kpVerChanges(changes));
  }
  if (files.length) {
    // Originals pulled or added, Raw, schema and skill files staged with them.
    const list = bh("ul", "");
    for (const path of files.slice(0, 20)) list.append(bh("li", "", path));
    if (files.length > 20) list.append(bh("li", "note", "還有 " + (files.length - 20) + " 個"));
    box.append(bh("p", "", "還沒 commit 的檔案 " + files.length + " 個："), list);
  }
  if (commits.length) {
    const list = bh("ul", "");
    for (const item of commits) {
      list.append(bh("li", "", bh("strong", "", item.purpose), "・" + biTime(item.created)
        + "（已 commit，還沒 push）"));
    }
    box.append(bh("p", "", "已 commit、還沒 push 的 " + commits.length + " 個："), list);
  }
  el("kp-ver-commit").disabled = !uncommitted;
  el("kp-ver-discard").disabled = !uncommitted;
  el("kp-ver-push").disabled = !commits.length || !state.reachable;
  kpVerHistory(history);
}

function kpVerHistory(history) {
  const box = el("kp-ver-history"); box.replaceChildren();
  const tags = history.tags || [], published = history.published;
  const byCommit = {};
  for (const tag of tags) (byCommit[tag.commit] = byCommit[tag.commit] || []).push(tag);
  const live = (tag) => Boolean(published && published.tag === tag.name);
  const list = bh("ul", "");
  (history.commits || []).forEach((commit, index) => {
    const row = bh("li", "");
    const badges = (byCommit[commit.id] || []).map((tag) =>
      biBadge("tag " + tag.name + (live(tag) ? "・發佈中" : ""), live(tag) ? "good" : ""));
    row.append(bh("div", "", bh("strong", "", commit.purpose), " ", ...badges),
      bh("div", "note", biTime(commit.created) + "・" + commit.author + "・" + commit.units
        + " 項" + (commit.kind === "revert" ? "・回復版本" : "") + "・" + commit.id.slice(0, 10)));
    const actions = bh("div", "kp-actions"), detail = bh("div", "");
    const look = kpButton("看改動", () => kpRun("讀取改動", async () => {
      if (detail.childNodes.length) { detail.replaceChildren(); return; }
      const reply = await kpRepoCall(kpRepoPath("diff?commit=" + encodeURIComponent(commit.id)));
      detail.replaceChildren(kpVerChanges(reply.changes || []));
    }));
    look.setAttribute("aria-label", "看「" + commit.purpose + "」的改動");
    actions.append(look);
    if (index > 0) {
      actions.append(kpButton("回到這個版本", () => kpVerAsk(row, "回復的目的",
        "回到「" + commit.purpose + "」的版本", "回復（成為新的 commit）", async (purpose) => {
          await kpRepoCall(kpRepoPath("revert"), {version: commit.id, purpose});
          kpVerSay("已回復成新的 commit；按「Push 給大家」送出。");
          await kpOpen(kpSandbox);
        })));
    }
    actions.append(kpButton("加 tag", () => kpVerAsk(row,
      "tag 名稱（小寫英數字與 . -，例如 2026q4）", "", "建立 tag", async (name) => {
        await kpRepoCall(kpRepoPath("tag"), {name, version: commit.id, purpose: commit.purpose});
        kpVerSay("已建立 tag「" + name + "」；要讓 Agent 讀它，請按「發佈 " + name + "」。");
        await kpVerShow();
      })));
    for (const tag of byCommit[commit.id] || []) {
      if (live(tag)) continue;
      actions.append(kpButton("發佈 " + tag.name, () => kpRun("發佈", async () => {
        if (!confirm("發佈 tag「" + tag.name + "」？發佈後 Agent 只讀這個版本的內容；"
          + "要撤回就再發佈另一個 tag。")) return;
        const reply = await kpRepoCall(kpRepoPath("publish"), {tag: tag.name, confirm: true});
        kpVerSay("已發佈「" + tag.name + "」：Agent 下一個問題就讀這個版本。"
          + (reply && reply.summary_missing ? "提醒：" + reply.summary_missing.total
            + " 張卡片還沒有摘要（不影響發佈）。" : ""));
        await kpVerShow();
      })));
    }
    row.append(actions, detail); list.append(row);
  });
  if (!(history.commits || []).length) list.append(bh("li", "note", "還沒有 commit。"));
  box.append(list);
}

function kpVerConflicts(conflicts) {
  // Push conflicts side by side: nothing was written until each is decided.
  const box = el("kp-ver-conflicts"); box.replaceChildren();
  if (!conflicts.length) return;
  const decided = {};
  box.append(bh("p", "kp-warn", "沒有送出：有 " + conflicts.length + " 個地方別人也改了。"
    + "每一項選一邊，再按「Push 給大家」。"));
  const list = bh("ul", "");
  for (const conflict of conflicts) {
    const label = conflict.label || conflict.unit;
    const mine = bh("div", "", bh("div", "note", "你的（" + conflict.purpose + "）"),
      kpVerValue(conflict.mine));
    const theirs = bh("div", "", bh("div", "note", "別人已 push 的"), kpVerValue(conflict.theirs));
    const choose = (choice) => kpRun("決定衝突", async () => {
      await kpRepoCall(kpRepoPath("resolve"), {unit: conflict.unit, choice});
      decided[conflict.unit] = choice;
      mine.classList.toggle("chosen", choice === "mine");
      theirs.classList.toggle("chosen", choice === "theirs");
      const left = conflicts.filter((c) => !decided[c.unit]).length;
      kpVerSay(left ? "已決定；還有 " + left + " 項。" : "全部決定了，按「Push 給大家」送出。");
    });
    const useMine = kpButton("用我的", () => choose("mine"));
    useMine.setAttribute("aria-label", "用我的：" + label);
    const useTheirs = kpButton("用別人的", () => choose("theirs"));
    useTheirs.setAttribute("aria-label", "用別人的：" + label);
    list.append(bh("li", "", bh("strong", "", label), bh("div", "kp-ver-pair", mine, theirs),
      bh("div", "kp-actions", useMine, useTheirs)));
  }
  box.append(list);
}

el("kp-ver-commit").addEventListener("click", () => kpRun("Commit", async () => {
  const input = el("kp-ver-purpose"), purpose = input.value.trim();
  if (!purpose) { kpVerSay("請先寫這次改動的目的。", true); input.focus(); return; }
  await kpRepoCall(kpRepoPath("commit"), {purpose});
  input.value = ""; kpVerSay("已 commit；按「Push 給大家」才會送出。");
  await kpVerShow();
}));
el("kp-ver-push").addEventListener("click", () => kpRun("Push", async () => {
  const reply = await kpRepoCall(kpRepoPath("push"), {});
  kpVerConflicts(reply.status === "conflicts" ? reply.conflicts || [] : []);
  const notes = (reply.notes || []).join("；");
  if (reply.status === "pushed") {
    kpVerSay("已 push " + (reply.commits || []).length
      + " 個 commit；要讓 Agent 讀到，請加 tag 並發佈。"
      + (notes ? " " + notes : ""));
  } else if (reply.status === "blocked") {
    kpVerSay("沒有送出：" + (reply.blocking || []).join("；") + (notes ? " " + notes : ""), true);
  } else if (reply.status === "nothing") {
    kpVerSay("沒有要 push 的 commit。");
  }
  await kpOpen(kpSandbox);
}));
el("kp-ver-discard").addEventListener("click", () => {
  if (!confirm("捨棄這台電腦上還沒 commit 的改動？工作資料夾會回到最近的版本；"
      + "已 commit 的不受影響。")) {
    return;
  }
  kpRun("捨棄", async () => {
    await kpRepoCall(kpRepoPath("discard"), {});
    kpVerSay("已捨棄還沒 commit 的改動。");
    await kpOpen(kpSandbox);
  });
});

async function kpReviewBanner(item) {
  // A sandbox opened from an accepted review proposal (owner 2026-10-13).
  const box = el("kp-review"); box.replaceChildren(); box.hidden = true;
  const reply = await call("/api/knowledge/review-proposal?sandbox_id="
    + encodeURIComponent(item.sandbox_id));
  const proposal = reply.ok ? reply.proposal : null;
  if (!proposal) return;
  const head = document.createElement("p");
  head.append(text("Opened from review proposal " + proposal.proposal_id + " (" + proposal.cause
    + "): " + proposal.diagnosis));
  const body = document.createElement("div"); body.className = "rv-text";
  body.append(text(proposal.text));
  const open = kpButton(proposal.kind === "test_question"
    ? "Open the draft question " + proposal.path
    : "Open " + proposal.path + " with the proposal added", () => kpRun("Reading", async () => {
      const file = await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id,
                                                path: proposal.path});
      kpRulePath = proposal.path; el("kp-rule-editor").hidden = false;
      el("kp-rule-path").textContent = proposal.path; kpRuleSaved = file.text;
      const marker = "Review proposal (" + proposal.proposal_id + ")";
      el("kp-rule-text").value = proposal.kind === "rule_edit" && !file.text.includes(marker)
        ? file.text.replace(/\s*$/, "") + "\n\n## " + marker + "\n\n" + proposal.text
          + "\n\n> Why: " + proposal.diagnosis + "\n"
        : file.text;
      el("kp-rule-text").dispatchEvent(new Event("input")); kpTab("md");
      el("kp-rule-editor").scrollIntoView({block: "start"});
    }));
  open.className = "go";
  const note = document.createElement("p"); note.className = "note";
  note.append(text(proposal.kind === "test_question"
    ? "Fill in the must-mention terms (an expert's job; the review never invents them), "
      + "save, then benchmark and push."
    : "The proposal is added as an unsaved edit: compare it, edit it (the AI session can "
      + "help), save, then benchmark and push."));
  box.append(head, body, note, open); box.hidden = false;
}

// -- Three guided steps (owner 2026-10-14) ----------------------------------
let kpCurrentStage = "pull", kpRawTotal = 0;
const KP_STAGES = ["pull", "ingest", "test"];

// A stepper (`.kp-stepper`, shared by the Wiki and the BI flow): marks the
// current step and locks the steps `allowed` does not open, with `why` as the
// locked steps' tooltip.
function stepperSet(nav, current, allowed, why) {
  for (const button of nav.querySelectorAll("[data-stage]")) {
    if (button.dataset.stage === current) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
    button.disabled = !allowed[button.dataset.stage];
    button.title = button.disabled ? why : "";
  }
}

function kpStage(name, focus = true) {
  const open = !!kpSandbox;
  const stage = open && KP_STAGES.includes(name) ? name : "pull";
  kpCurrentStage = stage;
  stepperSet(el("kp-stepper"), stage, {pull: true, ingest: open, test: open},
    "Open or create a sandbox first");
  el("kp-start").hidden = open; el("kp-box").hidden = !open;
  for (const section of document.querySelectorAll("#kp-main .kp-stage")) {
    section.hidden = section.dataset.stage !== stage;
  }
  if (open) {
    try { localStorage.setItem("kp-stage-" + kpSandbox.sandbox_id, stage); } catch (e) { /* */ }
  }
  if (focus) {
    const title = open ? document.querySelector('.kp-stage[data-stage="' + stage + '"] '
      + ".kp-stage-title") : document.querySelector("#kp-start .kp-stage-title");
    if (title) {  // screen readers hear the step; the page shows its top below the steps
      title.focus({preventScroll: true});
      const below = document.querySelector(".kp-top").getBoundingClientRect().height + 8;
      const top = title.getBoundingClientRect().top;
      if (top < below) window.scrollTo({top: Math.max(0, top + window.scrollY - below)});
    }
  }
}

function kpStoredStage(sandboxId) {
  try { return localStorage.getItem("kp-stage-" + sandboxId) || "pull"; }
  catch (e) { return "pull"; }
}

for (const button of document.querySelectorAll("#kp-stepper [data-stage]")) {
  button.addEventListener("click", () => kpStage(button.dataset.stage));
}
for (const button of document.querySelectorAll(".kp-nav [data-go]")) {
  button.addEventListener("click", () => kpStage(button.dataset.go));
}
el("kp-switch").addEventListener("click", () => {
  kpSandbox = null; kpStage("pull"); kpRun("Reading", loadKnowledge);
});

// -- Questions and their coverage (step 3) -----------------------------------
let kpQuestionPath = null, kpQuestionSets = null;

function kpQuestionsShow(sets) {
  kpQuestionSets = sets;
  const scope = kpSandbox.scope || "this sandbox";
  const scoped = sets.questions.filter((q) => sets.defaults.includes(q.set));
  const graded = scoped.filter((q) => q.must + q.must_not > 0).length;
  const target = Math.max(5, Math.ceil(kpRawTotal / 10));
  const box = el("kp-q-coverage");
  box.textContent = scope + ": " + scoped.length + " question(s) in its sets, " + graded
    + " graded, for " + kpRawTotal + " Raw document(s). " + (graded < target
      ? "Aim for at least " + target + " graded questions (about one per 10 documents, at "
        + "least 5) so a test can catch a regression."
      : "That is about one graded question per " + Math.max(1, Math.round(kpRawTotal
        / Math.max(graded, 1))) + " documents.");
  box.classList.toggle("kp-low", graded < target);
  const ordered = [...scoped, ...sets.questions.filter((q) => !sets.defaults.includes(q.set))];
  el("kp-q-list").replaceChildren(table(["Set", "Question", "Terms", ""], ordered, (q) => [
    q.set || "(general)", q.text,
    q.must + q.must_not ? q.must + " must, " + q.must_not + " must not" : "not graded",
    kpButton(q.editable ? "Edit" : "View", () => kpRun("Reading", () => kpQuestionOpen(
      q.path, q.editable)))]));
}

async function kpQuestionOpen(path, editable, text = null) {
  const body = text !== null ? text
    : (await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id, path})).text;
  kpQuestionPath = path; el("kp-q-editor").hidden = false;
  el("kp-q-path").textContent = path + (editable ? "" : " (another folder's set: read only)");
  el("kp-q-text").value = body; el("kp-q-text").readOnly = !editable;
  el("kp-q-save").hidden = !editable; el("kp-q-text").focus();
}

el("kp-q-new").addEventListener("click", () => {
  const scope = (kpSandbox.scope || "general").split("/")[0].toLowerCase();
  const set = (kpQuestionSets && kpQuestionSets.defaults[0]) || scope;
  const stamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14);
  kpQuestionOpen("checks/questions/" + set + "/q-" + stamp + ".md", true,
    "---\nname: q-" + stamp + "\nasked_by: \n---\n\n# Write the question here?\n\n"
    + "必須提到:\n  - \n\n不可以說:\n");
});
el("kp-q-save").addEventListener("click", () => kpRun("Saving the question", async () => {
  await pipeline("rule-write", {sandbox_id: kpSandbox.sandbox_id, path: kpQuestionPath,
                                text: el("kp-q-text").value});
  await kpLoadBench();
  kpStatus("Saved " + kpQuestionPath + ".");
}));
el("kp-q-cancel").addEventListener("click", () => { el("kp-q-editor").hidden = true; });

async function kpLoadScopes() {
  // A sandbox maintains one folder of the project vault (owner, 2026-10-13).
  const pick = el("kp-scope"); pick.replaceChildren();
  if (!el("kp-base").value) return;
  const folders = await pipeline("drop-folders", {base: el("kp-base").value});
  const first = document.createElement("option"); first.value = "";
  first.append(text("Folder to maintain\u2026")); pick.append(first);
  for (const folder of folders.folders) {
    const option = document.createElement("option"); option.value = folder.path;
    option.append(text(folder.path)); pick.append(option);
  }
}
el("kp-base").addEventListener("change", () => kpRun("Reading", kpLoadScopes));

async function kpOpen(item) {
  const switched = !kpSandbox || kpSandbox.sandbox_id !== item.sandbox_id;
  if (switched) {
    kpCurrentStage = kpStoredStage(item.sandbox_id); el("kp-q-editor").hidden = true;
    kpNewRaw = new Set(); kpFocus = null; kpAnchor = null;
    el("kp-doc").replaceChildren(); el("kp-plan").replaceChildren();
    el("kp-doc-title").textContent = "Choose a Raw document on the right.";
    el("kp-plan-one").hidden = true; el("kp-doc-back").hidden = true;
  }
  kpSandbox = item; el("kp-box").hidden = false;
  const repo = Boolean(item.repo);
  el("kp-title").textContent = item.label + " \u2014 "
    + (repo ? "知識庫 " + item.repo : item.sandbox_id);
  el("kp-discard").hidden = repo;
  el("kp-switch").textContent = repo ? "換一個" : "Switch sandbox";
  el("kp-repo-settings").hidden = !repo;
  el("kp-ver").hidden = !repo; el("kp-push-card").hidden = repo;
  el("kp-candidate").hidden = repo;
  el("kp-pull-h").textContent = repo ? "從收件資料夾" : "From the project vault";
  el("kp-pull-note").textContent = repo
    ? "還沒判讀過的原始檔會複製進來；已經判讀過的（內容相同）已經是 Raw，不會再拉。"
    : "Originals not yet ingested are copied into the sandbox. Ingested ones are already "
      + "here as Raw, so they are not pulled again.";
  if (repo) await kpRepoSettings();
  kpStatus("Opening the sandbox: its files (1/5)\u2026");
  const contents = await pipeline("sandbox-contents", {sandbox_id: item.sandbox_id});
  el("kp-drop").replaceChildren(table(["Original in drop"], contents.drop, (row) => [row]));
  const raw = el("kp-raw"); raw.replaceChildren();
  const rawRefs = item.scope ? contents.raw.filter((ref) =>
    ref.startsWith("raw/" + item.scope + "/")) : contents.raw;
  el("kp-scope-name").textContent = item.scope
    || (item.repo ? "整個知識庫" : "whole vault (older sandbox)");
  kpRawTotal = rawRefs.length;
  kpStage(kpCurrentStage, switched);
  await kpReviewBanner(item);
  const prefix = item.scope ? "raw/" + item.scope + "/" : "raw/";
  for (const ref of rawRefs) {
    const row = document.createElement("div"); row.className = "kp-file";
    row.dataset.ref = ref; row.setAttribute("role", "option"); row.title = ref;
    const tick = document.createElement("input"); tick.type = "checkbox";
    tick.className = "kp-raw-tick"; tick.value = ref; tick.setAttribute("aria-label", ref);
    tick.tabIndex = -1;
    const name = document.createElement("span");
    name.append(text(ref.startsWith(prefix) ? ref.slice(prefix.length) : ref));
    row.append(tick, name); raw.append(row);
  }
  if (!rawRefs.length) raw.append(text("No Raw documents yet: convert originals in step 1."));
  kpMarkNew();
  if (kpFocus && !rawRefs.includes(kpFocus)) kpFocus = null;
  kpShowFocus();
  const folders = new Set();
  for (const ref of rawRefs) {
    const parts = ref.split("/").slice(0, -1);
    for (let n = 2; n <= parts.length; n++) folders.add(parts.slice(0, n).join("/"));
  }
  const pick = el("kp-raw-folder"); pick.replaceChildren(); kpRawFilter();
  const top = item.scope ? "raw/" + item.scope : "raw";
  for (const folder of [top, ...[...folders].filter((f) => f !== top).sort()]) {
    const option = document.createElement("option"); option.value = folder;
    option.append(text(folder === top ? folder + " (all)" : folder)); pick.append(option);
  }
  kpRawCount();
  await kpReingestShow();
  await kpConvertShow();
  kpStatus("Opening the sandbox: rules (2/5)\u2026"); await kpLoadRules();
  kpStatus("Opening the sandbox: drop folders (3/5)\u2026"); await kpLoadPull();
  kpStatus("Opening the sandbox: question sets (4/5)\u2026"); await kpLoadBench();
  kpStatus("Opening the sandbox: push status (5/5)\u2026");
  if (item.repo) await kpVerShow(); else await kpPushShow();
  kpStatus("");
}

let kpPushTimer = null;
async function kpPushShow() {
  const reply = await call("/api/knowledge/push?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const push = reply.ok ? reply.push : null;
  const box = el("kp-push-result"); box.replaceChildren();
  if (!push) { el("kp-push-state").textContent = "Not pushed yet."; return; }
  const bench = push.benchmark || {};
  el("kp-push-state").textContent = push.push_id + ": " + push.status
    + (push.reason ? " \u2014 " + push.reason : "");
  const lines = [
    "Files: " + push.written.length + (push.proposals.length
      ? "; proposals (outside the scope): " + push.proposals.join(", ") : ""),
    "Benchmark: merged " + (bench.sandbox_score ?? "-") + " / project vault "
      + (bench.project_score ?? "-") + " of " + (bench.total ?? "-")
      + ((bench.regressions || []).length ? "; regressions: " + bench.regressions.join(", ") : ""),
    push.conflicts.length ? "Conflicts to choose: " + push.conflicts.join(", ") : "",
    push.backup ? "Backup: " + push.backup : "",
  ].filter(Boolean);
  const list = document.createElement("ul");
  for (const line of lines) {
    const li = document.createElement("li"); li.append(text(line)); list.append(li);
  }
  box.append(list);
  clearTimeout(kpPushTimer);
  if (["merging", "benchmarking", "writing"].includes(push.status)) {
    kpPushTimer = setTimeout(() => kpPushShow().catch(() => {}), 5000);
  }
}

function kpChecks(box, items, checked) {
  box.replaceChildren();
  for (const [value, label] of items) {
    const row = document.createElement("label"); row.className = "kp-check";
    const tick = document.createElement("input"); tick.type = "checkbox"; tick.value = value;
    tick.checked = checked.includes(value); row.append(tick, text(" " + label)); box.append(row);
  }
}

function kpTicked(box) {
  return [...box.querySelectorAll("input[type=checkbox]:checked")].map((t) => t.value);
}

async function kpLoadPull() {
  let folders;
  try { folders = await pipeline("drop-folders", {base: kpSandbox.base_name}); }
  catch (failure) {
    if (failure.code !== "intake_not_set") throw failure;
    folders = {folders: [], unset: true};
  }
  const pick = el("kp-category"); pick.replaceChildren();
  const categories = kpSandbox.scope ? [[kpSandbox.scope, kpSandbox.scope]]
    : [["", "(no category)"], ...folders.folders.filter((f) => !f.path.includes("/"))
      .map((f) => [f.path, f.path])];
  for (const [value, label] of categories) {
    const option = document.createElement("option"); option.value = value;
    option.append(text(label)); pick.append(option);
  }
  const scope = kpSandbox.scope;
  const inScope = folders.folders.filter((f) => !scope || f.path === scope
    || f.path.startsWith(scope + "/"));
  kpChecks(el("kp-pull-folders"), inScope.map((f) =>
    [f.path, f.path + " (" + f.files + " files)"]), scope ? [scope] : []);
  if (!inScope.length) {
    el("kp-pull-folders").append(text(folders.unset ? "還沒設定收件資料夾（在上面設定）；"
      + "也可以用下面的「Add files」從這台電腦加入。" : kpSandbox.repo ? "收件資料夾是空的。"
      : scope ? "The project vault's drop has no " + scope + " folder yet."
      : "The project vault's drop is empty."));
  }
}

async function kpLoadBench() {
  const sets = await pipeline("question-sets", {sandbox_id: kpSandbox.sandbox_id});
  kpQuestionsShow(sets);
  kpChecks(el("kp-bench-sets"), Object.entries(sets.sets).map(([name, n]) =>
    [name, (name || "(general)") + " \u2014 " + n + " questions"]), sets.defaults);
  if (sets.ungraded.length) {
    el("kp-bench-sets").append(text(" Not graded (no must-mention / must-not-say terms): "
      + sets.ungraded.join(", ")));
  }
  if (kpSandbox.repo && !Object.keys(sets.sets).length) {
    el("kp-bench-sets").append(text("沒有題目：在步驟 1 設定這台電腦的題目資料夾。"));
  }
  await kpBenchShow();
}

let kpBenchTimer = null;
async function kpBenchShow() {
  const reply = await call("/api/knowledge/benchmark?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const report = reply.ok ? reply.report : null;
  const box = el("kp-bench-result"); box.replaceChildren();
  if (!report) { el("kp-bench-state").textContent = "No benchmark run yet."; return; }
  el("kp-bench-state").textContent = report.status + ": " + report.results.length + " of "
    + report.total + " questions; sandbox " + report.sandbox_score + ", project vault "
    + report.project_score + (report.regressions.length ? "; REGRESSIONS: "
    + report.regressions.length : "") + (report.error ? "; error " + report.error : "");
  const rows = [...report.results].sort((a, b) =>
    Number(report.regressions.includes(b.path)) - Number(report.regressions.includes(a.path)));
  const mark = (side) => (side.grade.passed ? "pass" : "fail")
    + (side.grade.missing.length ? " \u2014 missing: " + side.grade.missing.join(", ") : "")
    + (side.grade.forbidden.length ? " \u2014 said: " + side.grade.forbidden.join(", ") : "");
  box.append(table(["Question", "Set", "Project vault", "Sandbox"], rows, (row) => [
    (report.regressions.includes(row.path) ? "\u26a0 regression: " : "") + row.question,
    row.set || "(general)", mark(row.project), mark(row.sandbox)]));
  clearTimeout(kpBenchTimer);
  if (report.status === "running") {
    kpBenchTimer = setTimeout(() => kpBenchShow().catch(() => {}), 5000);
  }
}

function kpViewer(title, content) {
  el("kp-viewer").hidden = false; el("kp-viewer-title").textContent = title;
  el("kp-viewer-body").replaceChildren(content);
  el("kp-viewer").scrollIntoView({behavior: "smooth", block: "start"});
}

async function kpShowFile(path) {
  const file = await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id, path});
  kpViewer(path, renderMarkdown(file.text));
}

function kpLineDiff(before, after) {
  // Lines added or removed, ignoring order: what a reviewer checks first.
  const old = new Set(before.split("\n").map((line) => line.trim()));
  const now = new Set(after.split("\n").map((line) => line.trim()));
  const box = document.createDocumentFragment();
  const added = after.split("\n").filter((line) => line.trim() && !old.has(line.trim()));
  const removed = before.split("\n").filter((line) => line.trim() && !now.has(line.trim()));
  for (const [label, lines, cls] of [["Added", added, "kp-added"],
                                     ["Removed", removed, "kp-removed"]]) {
    const head = document.createElement("p");
    head.append(text(label + " (" + lines.length + " lines)")); box.append(head);
    const pre = document.createElement("pre"); pre.className = cls;
    pre.append(text(lines.join("\n") || "(none)")); box.append(pre);
  }
  return box;
}

async function kpShowPlanPage(planId, path) {
  const page = await pipeline("plan-page", {sandbox_id: kpSandbox.sandbox_id,
                                            plan_id: planId, path});
  const box = document.createDocumentFragment();
  box.append(page.before ? kpLineDiff(page.before, page.after) : text("New page."));
  const full = document.createElement("details");
  const summary = document.createElement("summary");
  summary.append(text("The page after apply")); full.append(summary, renderMarkdown(page.after));
  box.append(full);
  el("kp-doc-title").textContent = path + " \u2014 planned change";
  el("kp-doc-back").hidden = false;
  el("kp-doc").replaceChildren(box); el("kp-doc").scrollTop = 0;
}

let kpRulePath = null;
async function kpLoadRules() {
  const rules = await pipeline("rule-files", {sandbox_id: kpSandbox.sandbox_id});
  const box = el("kp-rules"); box.replaceChildren();
  const roles = {ingest: "how its data becomes wiki pages", answer: "how its questions are "
    + "answered", schema: "the whole vault's schema"};
  const access = {edit: "", inherited: "general layer, read only", shared: "shared, read only"};
  box.append(table(["Rule file", "What it decides", ""], rules.rules, (rule) => [
    rule.path, roles[rule.kind] + (access[rule.access] ? " (" + access[rule.access] + ")" : ""),
    rule.access === "edit"
      ? kpButton("Edit", () => kpRun("Reading", async () => {
          const file = await pipeline("file-read",
                                      {sandbox_id: kpSandbox.sandbox_id, path: rule.path});
          kpRulePath = rule.path; el("kp-rule-editor").hidden = false;
          el("kp-rule-path").textContent = rule.path; el("kp-rule-text").value = file.text;
          kpRuleSaved = file.text; kpTab("md");
        }))
      : kpButton("View", () => kpRun("Reading", () => kpShowFile(rule.path)))]));
  const scope = rules.scope;
  const slug = (scope || "").split("/").pop().toLowerCase().replace(/[^a-z0-9._-]+/g, "-");
  const guide = await pipeline("skill-guide", {});
  const add = kpButton("New skill", () => {
    const suggested = scope && !rules.rules.some((r) => r.kind === "ingest"
      && r.access === "edit") ? "ingest-" + slug : (scope ? "ask-" + slug : "");
    const name = (prompt("Skill folder name: ingest-<name> for processing data, "
      + "ask-<name> for answering" + (scope ? "; it applies to raw/" + scope : ""),
      suggested) || "").trim();
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(name)) return;
    const answering = name.startsWith("ask-");
    const category = scope || name.replace(/^(ingest|ask)-/, "");
    kpRulePath = "skills/" + name + "/SKILL.md"; el("kp-rule-editor").hidden = false;
    el("kp-rule-path").textContent = kpRulePath;
    kpRuleSaved = ""; kpTab("md");
    el("kp-rule-text").value = (answering ? guide.answer_template : guide.ingest_template)
      .replaceAll("ingest-<category>", name).replaceAll("ask-knowledge", name)
      .replaceAll("raw/<Category>", "raw/" + category)
      .replaceAll("raw/Knowledge", "raw/" + category)
      .replaceAll("<Category>", category);
  });
  const help = kpButton("Writing guide", () => kpViewer("Skill writing guide",
                                                        renderMarkdown(guide.guide)));
  box.append(add, help);
}

function kpFileBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error); reader.readAsDataURL(file);
  });
}

async function kpConvert(mode) {
  // A background run, one original at a time (owner 2026-10-13).
  const reply = await call("/api/knowledge/convert/start",
                           {sandbox_id: kpSandbox.sandbox_id, mode});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  await kpConvertShow();
}

let kpConvertTimer = null, kpConvertWatching = null;
async function kpConvertShow() {
  clearTimeout(kpConvertTimer);
  const reply = await call("/api/knowledge/convert?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const run = reply.ok ? reply.run : null;
  const box = el("kp-convert-progress"), bar = el("kp-convert-bar");
  const live = run && ["running", "stopping"].includes(run.status);
  box.hidden = !live; el("kp-convert-stop").hidden = !live;
  el("kp-preview").disabled = !!live; el("kp-convert").disabled = !!live;
  if (!run || run.sandbox_id !== kpSandbox.sandbox_id) {
    el("kp-converted").replaceChildren(); return;
  }
  const total = run.paths.length, done = run.items.length;
  if (live) {
    const step = run.progress || {};
    const pictures = step.phase === "describing" && step.total
      ? "; pictures " + step.done + " / " + step.total : "";
    bar.max = total; bar.value = done + (step.phase === "describing" && step.total
      ? step.done / step.total : 0);
    el("kp-convert-text").textContent = (run.mode === "apply" ? "Converting" : "Previewing")
      + " " + Math.min(done + 1, total) + " / " + total + pictures
      + (run.current ? " \u2014 " + run.current.replace(/^drop\//, "") : "")
      + (run.status === "stopping" ? " (stopping after this one)" : "");
  }
  const head = document.createElement("p");
  head.append(text((run.mode === "apply" ? "Convert" : "Preview") + ": " + run.status + ", "
    + done + " of " + total + " originals" + (run.error ? " \u2014 " + run.error : "")));
  el("kp-converted").replaceChildren(head, table(["Original", "Result", "Raw", "Pictures"],
    run.items, (row) => [row.path, row.status, row.raw_ref || "",
      row.described ? row.described + " described" : String(row.images)]));
  if (live) {
    kpConvertWatching = run.run_id;
    kpConvertTimer = setTimeout(() => kpConvertShow().catch(() => {}), 1500);
  } else if (run.mode === "apply" && kpConvertWatching === run.run_id) {
    kpConvertWatching = null;  // it just ended: the new Raw appears in step 2
    kpNewRaw = new Set(run.items.filter((i) => ["written", "drifted"].includes(i.status)
      && i.raw_ref).map((i) => i.raw_ref));
    await kpOpen(kpSandbox);
  }
}

el("kp-convert-stop").addEventListener("click", () => kpRun("Stopping", async () => {
  await call("/api/knowledge/convert/stop", {sandbox_id: kpSandbox.sandbox_id});
  await kpConvertShow();
}));

async function kpPlan(rawRef) {
  const plan = await pipeline("ingest-plan", {sandbox_id: kpSandbox.sandbox_id, raw_ref: rawRef});
  const box = el("kp-plan"); box.className = ""; box.replaceChildren();
  const head = document.createElement("p");
  head.append(text(rawRef + ": " + plan.status + (plan.summary ? " \u2014 " + plan.summary : "")
    + " (schema: " + plan.schema_source + (plan.skill ? ", rules: " + plan.skill : "") + ")"));
  box.append(head);
  if (plan.problems.length) box.append(text("Problems: " + plan.problems.join(", ")));
  box.append(table(["Page", "Change", "Characters", ""], plan.pages,
    (row) => [row.path, row.change, String(row.chars), plan.plan_id
      ? kpButton("Compare", () => kpRun("Reading",
          () => kpShowPlanPage(plan.plan_id, row.path))) : ""]));
  if (plan.contradictions.length) {
    const list = document.createElement("ul");
    for (const line of plan.contradictions) {
      const li = document.createElement("li"); li.append(text("\u26a0 " + line)); list.append(li);
    }
    box.append(list);
  }
  if (plan.plan_id) {
    box.append(kpButton("Apply to this sandbox", () => kpRun("Applying", async () => {
      const done = await pipeline("ingest-apply",
        {sandbox_id: kpSandbox.sandbox_id, plan_id: plan.plan_id});
      const note = document.createElement("p");
      note.append(text(done.status === "applied" ? "Applied: " + done.written.join(", ")
        : "Not applied: " + done.problems.join(", ")));
      box.append(note);
    })));
  }
}

// -- Re-ingest with the current rules (owner 2026-10-13) ----------------------
// Seconds one document took in the live runs; only for the estimate shown.
const KP_SECONDS_PER_DOC = 60;
const KP_REINGEST_LABELS = {applied: "applied", needs_review: "needs your review",
  failed: "failed", rejected: "not applied"};

function kpRawTicked() {
  return [...document.querySelectorAll("#kp-raw .kp-raw-tick:checked")].map((t) => t.value);
}

function kpRawCount() {
  const rows = kpRows(), ticked = rows.filter((r) => r.querySelector(".kp-raw-tick").checked);
  const all = el("kp-raw-all");
  all.checked = rows.length > 0 && ticked.length === rows.length;
  all.indeterminate = ticked.length > 0 && ticked.length < rows.length;
  const n = kpRawTicked().length;
  el("kp-raw-count").textContent = n ? n + " ticked, about "
    + Math.max(1, Math.round(n * KP_SECONDS_PER_DOC / 60)) + " min" : "";
}

function kpRawTick(refs) {
  const wanted = new Set(refs);
  for (const tick of document.querySelectorAll("#kp-raw .kp-raw-tick")) {
    if (wanted.has(tick.value)) tick.checked = true;
  }
  kpRawCount();
}

let kpReingestTimer = null;
async function kpReingestShow() {
  const reply = await call("/api/knowledge/reingest?sandbox_id="
    + encodeURIComponent(kpSandbox.sandbox_id));
  const run = reply.ok ? reply.run : null;
  const box = el("kp-reingest-result"); box.replaceChildren();
  const live = run && ["running", "stopping"].includes(run.status);
  el("kp-reingest-stop").hidden = !live; el("kp-reingest").disabled = !!live;
  clearTimeout(kpReingestTimer);
  if (!run) { el("kp-reingest-state").textContent = ""; return; }
  const counts = {};
  for (const item of run.items) counts[item.status] = (counts[item.status] || 0) + 1;
  el("kp-reingest-state").textContent = "Re-ingest " + run.run_id + ": " + run.status + ", "
    + run.items.length + " of " + run.raw_refs.length + " done"
    + (run.current ? "; now " + run.current : "")
    + (Object.keys(counts).length ? " (" + Object.entries(counts).map(([k, n]) =>
      (KP_REINGEST_LABELS[k] || k) + " " + n).join(", ") + ")" : "");
  if (!live && run.remaining.length) {
    box.append(kpButton("Continue with the " + run.remaining.length + " left",
      () => kpRun("Starting", () => kpReingestStart(run.remaining))));
  }
  const shown = run.items.filter((item) => item.status !== "applied");
  if (shown.length) {
    box.append(table(["Raw document", "Result", "Detail", ""], shown, (item) => [
      item.raw_ref, KP_REINGEST_LABELS[item.status] || item.status, item.detail,
      item.status === "needs_review" && item.plan_id
        ? kpButton("Review", () => kpReview(item)) : ""]));
  }
  if (live) kpReingestTimer = setTimeout(() => kpReingestShow().catch(() => {}), 5000);
}

async function kpReingestStart(refs) {
  const minutes = Math.max(1, Math.round(refs.length * KP_SECONDS_PER_DOC / 60));
  if (!confirm("Re-ingest " + refs.length + " Raw document(s) with this sandbox's current "
      + "rules? About " + minutes + " min; each one asks the model. Pages are written in "
      + "this sandbox only; plans the planner flags wait for your review.")) return;
  const reply = await call("/api/knowledge/reingest/start",
                           {sandbox_id: kpSandbox.sandbox_id, raw_refs: refs});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  setTimeout(() => kpReingestShow().catch(() => {}), 1000);
}

function kpReview(item) {
  // A flagged plan from a re-ingest run: compare its pages, then apply or leave it.
  const box = el("kp-plan"); box.className = ""; box.replaceChildren();
  const head = document.createElement("p");
  head.append(text(item.raw_ref + ": needs your review — " + item.detail));
  box.append(head);
  box.append(table(["Page", ""], item.pages, (path) => [path,
    kpButton("Compare", () => kpRun("Reading", () => kpShowPlanPage(item.plan_id, path)))]));
  if (item.contradictions.length) {
    const list = document.createElement("ul");
    for (const line of item.contradictions) {
      const li = document.createElement("li"); li.append(text("⚠ " + line)); list.append(li);
    }
    box.append(list);
  }
  box.append(kpButton("Apply to this sandbox", () => kpRun("Applying", async () => {
    const done = await pipeline("ingest-apply",
      {sandbox_id: kpSandbox.sandbox_id, plan_id: item.plan_id});
    const note = document.createElement("p");
    note.append(text(done.status === "applied" ? "Applied: " + done.written.join(", ")
      : "Not applied: " + done.problems.join(", ")));
    box.append(note);
  })));
  box.scrollIntoView({block: "nearest"});
}

// -- The Raw list (owner 2026-10-13): click to read, keys to move and tick ------
let kpFocus = null, kpAnchor = null, kpNewRaw = new Set(), kpDocTimer = null;

function kpRows() {
  return [...document.querySelectorAll("#kp-raw .kp-file")].filter((row) => !row.hidden);
}

function kpRawFilter() {
  const folder = (el("kp-raw-folder").value || "raw") + "/";
  for (const row of document.querySelectorAll("#kp-raw .kp-file")) {
    row.hidden = !row.dataset.ref.startsWith(folder);
  }
  kpRawCount();
}

function kpMarkNew() {
  for (const row of document.querySelectorAll("#kp-raw .kp-file")) {
    const fresh = kpNewRaw.has(row.dataset.ref);
    row.classList.toggle("kp-new", fresh);
    if (fresh) row.querySelector(".kp-raw-tick").checked = true;
  }
  kpRawCount();
}

function kpShowFocus() {
  for (const row of document.querySelectorAll("#kp-raw .kp-file")) {
    const on = row.dataset.ref === kpFocus;
    row.classList.toggle("kp-focus", on); row.setAttribute("aria-selected", String(on));
    if (on) {
      // Scroll the list only, never the page, so the document stays where it is.
      const list = el("kp-raw"), top = row.offsetTop;  // the list is position: relative
      if (top < list.scrollTop) list.scrollTop = top;
      else if (top + row.offsetHeight > list.scrollTop + list.clientHeight) {
        list.scrollTop = top + row.offsetHeight - list.clientHeight;
      }
    }
  }
}

function kpFocusOn(ref, show = true) {
  kpFocus = ref; kpShowFocus();
  if (!show) return;
  clearTimeout(kpDocTimer);  // holding an arrow key reads only where it stops
  kpDocTimer = setTimeout(() => kpDocShow(ref).catch((failure) => {
    el("kp-doc").replaceChildren(text("Not readable: " + (failure.code || failure.message)));
  }), 200);
}

async function kpDocShow(ref) {
  el("kp-doc-title").textContent = ref; el("kp-plan-one").hidden = false;
  el("kp-doc-back").hidden = true; el("kp-doc").replaceChildren(text("Reading\u2026"));
  const file = await pipeline("file-read", {sandbox_id: kpSandbox.sandbox_id, path: ref});
  if (kpFocus !== ref) return;
  el("kp-doc").replaceChildren(renderMarkdown(file.text)); el("kp-doc").scrollTop = 0;
}

function kpTickRange(from, to) {
  const rows = kpRows(), a = rows.findIndex((r) => r.dataset.ref === from);
  const b = rows.findIndex((r) => r.dataset.ref === to);
  if (a < 0 || b < 0) return;
  for (const row of rows.slice(Math.min(a, b), Math.max(a, b) + 1)) {
    row.querySelector(".kp-raw-tick").checked = true;
  }
  kpRawCount();
}

el("kp-raw").addEventListener("click", (event) => {
  const row = event.target.closest(".kp-file");
  if (!row) return;
  const ref = row.dataset.ref;
  if (event.target.classList.contains("kp-raw-tick")) {
    if (event.shiftKey && kpAnchor) kpTickRange(kpAnchor, ref);
    kpAnchor = ref; kpFocusOn(ref, false); kpRawCount(); return;
  }
  if (event.shiftKey && kpAnchor) { kpTickRange(kpAnchor, ref); kpFocusOn(ref); return; }
  kpAnchor = ref; kpFocusOn(ref); el("kp-raw").focus();
});

el("kp-raw").addEventListener("keydown", (event) => {
  const rows = kpRows();
  if (!rows.length) return;
  let at = rows.findIndex((r) => r.dataset.ref === kpFocus);
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    at = at < 0 ? 0 : Math.max(0, Math.min(rows.length - 1,
                                            at + (event.key === "ArrowDown" ? 1 : -1)));
    const ref = rows[at].dataset.ref;
    if (event.shiftKey) {
      if (!kpAnchor) kpAnchor = kpFocus || ref;
      kpTickRange(kpAnchor, ref);
    } else {
      kpAnchor = ref;
    }
    kpFocusOn(ref);
  } else if (event.key === " " && at >= 0) {
    event.preventDefault();
    const tick = rows[at].querySelector(".kp-raw-tick"); tick.checked = !tick.checked;
    kpAnchor = kpFocus; kpRawCount();
  } else if ((event.key === "a" || event.key === "A") && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    for (const row of rows) row.querySelector(".kp-raw-tick").checked = true;
    kpRawCount();
  }
});

el("kp-raw-all").addEventListener("change", () => {
  for (const row of kpRows()) row.querySelector(".kp-raw-tick").checked = el("kp-raw-all").checked;
  kpRawCount();
});
el("kp-raw-folder").addEventListener("change", kpRawFilter);
el("kp-plan-one").addEventListener("click", () => {
  if (kpFocus) kpRun("Planning ingest (this asks the model)", () => kpPlan(kpFocus));
});
el("kp-doc-back").addEventListener("click", () => { if (kpFocus) kpFocusOn(kpFocus); });
el("kp-reingest").addEventListener("click", () => kpRun("Starting the ingest", async () => {
  const refs = kpRawTicked();
  if (!refs.length) { kpStatus("Tick at least one Raw document.", true); return; }
  await kpReingestStart(refs);
}));
el("kp-reingest-stop").addEventListener("click", () => kpRun("Stopping", async () => {
  await call("/api/knowledge/reingest/stop", {sandbox_id: kpSandbox.sandbox_id});
  kpStatus("Stops after the document in progress.");
  await kpReingestShow();
}));

async function kpLint() {
  const report = await pipeline("lint", {sandbox_id: kpSandbox.sandbox_id});
  const box = el("kp-lint-result"); box.replaceChildren();
  box.append(text(report.pages + " pages, " + (report.clean ? "clean" : "findings") + ": "
    + Object.entries(report.counts).filter(([, n]) => n).map(([k, n]) => k + " " + n)
      .join(", ")));
  const list = document.createElement("ul");
  for (const line of report.findings) {
    const li = document.createElement("li"); li.append(text(line)); list.append(li);
  }
  box.append(list);
}

el("kp-refresh").addEventListener("click", () => kpRun("Reading", loadKnowledge));
el("kp-new").addEventListener("submit", (event) => {
  event.preventDefault();
  kpRun("Creating the sandbox (copying the base vault)", async () => {
    if (!el("kp-scope").value) { kpStatus("Choose the folder this sandbox maintains.", true);
      return; }
    const key = kpKey();
    const made = await kpWithProgress("Copying the project vault", key, () =>
      pipeline("sandbox-create", {base: el("kp-base").value, label: el("kp-label").value.trim(),
                                  scope: el("kp-scope").value, progress_key: key}));
    el("kp-label").value = ""; await loadKnowledge(); await kpOpen(made);
    kpStage("pull");
    if (kpTicked(el("kp-pull-folders")).length) el("kp-pull").click();  // pull the folder now
  });
});
el("kp-upload").addEventListener("click", () => kpRun("Adding to drop", async () => {
  for (const file of el("kp-files").files) {
    const folder = el("kp-category").value;
    await pipeline("drop-add", {sandbox_id: kpSandbox.sandbox_id,
      name: (folder ? folder + "/" : "") + file.name,
      data_base64: await kpFileBase64(file)});
  }
  el("kp-files").value = ""; await kpOpen(kpSandbox);
}));
el("kp-preview").addEventListener("click", () => kpRun("Previewing", () => kpConvert("dry_run")));
el("kp-convert").addEventListener("click", () => kpRun("Converting", () => kpConvert("apply")));
el("kp-lint").addEventListener("click", () => kpRun("Linting", kpLint));
el("kp-push").addEventListener("click", () => kpRun("Starting the push", async () => {
  const sets = kpTicked(el("kp-bench-sets"));
  if (!confirm("Push " + kpSandbox.label + " into the project vault? It is written only if the "
      + "benchmark (" + (sets.join(", ") || "no question sets") + ") shows no regression.")) return;
  const reply = await call("/api/knowledge/push/start", {sandbox_id: kpSandbox.sandbox_id, sets,
                                                         resolutions: kpResolutions()});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  setTimeout(() => kpPushShow().catch(() => {}), 1500);
}));
el("kp-refresh-agent").addEventListener("click", () => kpRun("Refreshing", async () => {
  if (!confirm("Stage the project vault " + kpSandbox.base_name + " as the Agent's next "
      + "Knowledge version? It answers from it after a restart.")) return;
  const reply = await call("/api/knowledge/refresh", {base: kpSandbox.base_name});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  el("kp-push-state").textContent = "Staged " + reply.data.version + " at "
    + reply.data.vault_root + ". Restart the Agent to answer from it.";
}));
el("kp-pull").addEventListener("click", () => kpRun("Pulling", async () => {
  const folders = kpTicked(el("kp-pull-folders"));
  if (!folders.length) { kpStatus("Choose at least one folder.", true); return; }
  const key = kpKey();
  const pulled = await kpWithProgress("Pulling originals", key, () =>
    pipeline("pull", {sandbox_id: kpSandbox.sandbox_id, folders, progress_key: key}));
  const parts = [pulled.copied.length + " new original(s) copied to drop (convert them below)"];
  if (pulled.already_in_sandbox.length) {
    parts.push(pulled.already_in_sandbox.length + " already in this sandbox's drop");
  }
  if (pulled.too_large.length) parts.push(pulled.too_large.length + " too large to pull");
  if (pulled.already_ingested.length) {
    parts.push(pulled.already_ingested.length + " already ingested: their Raw ("
      + pulled.already_raw.length + " document(s)) is already in this sandbox, so they are "
      + "not pulled again. To try changed rules on them, re-ingest them in step 2");
  }
  await kpOpen(kpSandbox);
  const box = el("kp-pull-result"); box.replaceChildren(text(parts.join("; ") + ". "));
  if (pulled.already_raw.length) {
    box.append(kpButton("Tick them in step 2", () => {
      kpRawTick(pulled.already_raw);
      el("kp-raw").scrollIntoView({block: "start"});
    }));
  }
}));
el("kp-bench").addEventListener("click", () => kpRun("Starting the benchmark", async () => {
  const sets = kpTicked(el("kp-bench-sets"));
  if (!sets.length) { kpStatus("Choose at least one question set.", true); return; }
  const reply = await call("/api/knowledge/benchmark/start",
                           {sandbox_id: kpSandbox.sandbox_id, sets});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  setTimeout(() => kpBenchShow().catch(() => {}), 1500);
}));
el("kp-viewer-close").addEventListener("click", () => { el("kp-viewer").hidden = true; });
el("kp-rule-close").addEventListener("click", () => {
  el("kp-rule-editor").hidden = true; kpRulePath = null;
});
let kpRuleSaved = "";
function kpDiffLines(before, after) {
  // A line diff in file order (longest common subsequence), so additions and
  // removals show where they happen.
  const lines = (value) => value.replace(/\r\n?/g, "\n").split("\n");
  const a = lines(before), b = lines(after);
  if (a.length * b.length > 4000000) {
    return [...a.map((line) => ["-", line]), ...b.map((line) => ["+", line])];
  }
  const table = Array.from({length: a.length + 1}, () => new Uint16Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1
        : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const out = [];
  let i = 0, j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) { out.push([" ", a[i]]); i++; j++; }
    else if (i < a.length && (j >= b.length || table[i + 1][j] >= table[i][j + 1])) {
      out.push(["-", a[i]]); i++;  // a removal is listed before what replaces it
    } else { out.push(["+", b[j]]); j++; }
  }
  return out;
}
let kpRuleMode = "md", kpRenderTimer = null, kpSyncing = false;
const KP_LINE = 20, KP_CONTEXT = 3;
function kpNumbered(lines) {
  // Old and new line numbers for every diff row.
  let old = 0, now = 0;
  return lines.map(([kind, line]) => {
    if (kind !== "+") old += 1;
    if (kind !== "-") now += 1;
    return {kind, line, old: kind === "+" ? null : old, now: kind === "-" ? null : now};
  });
}
function kpHunks(rows) {
  // Changed rows with three rows of context, merged when they touch.
  const keep = new Set();
  rows.forEach((row, index) => {
    if (row.kind === " ") return;
    for (let k = Math.max(0, index - KP_CONTEXT);
         k <= Math.min(rows.length - 1, index + KP_CONTEXT); k++) keep.add(k);
  });
  const hunks = [];
  let current = null;
  rows.forEach((row, index) => {
    if (!keep.has(index)) { current = null; return; }
    if (current === null) { current = []; hunks.push(current); }
    current.push(row);
  });
  return hunks;
}
function kpRow(cells, kind, now) {
  const row = document.createElement("div");
  row.className = "kp-drow " + (kind === "+" ? "kp-add" : kind === "-" ? "kp-del"
    : kind === "@" ? "kp-hunk" : "kp-same");
  if (now !== null && now !== undefined) row.dataset.now = String(now);
  for (const [cls, value] of cells) {
    const cell = document.createElement("span"); cell.className = cls;
    cell.append(text(value)); row.append(cell);
  }
  return row;
}
function kpRenderPrevious(rows) {
  const box = el("kp-prev"); box.replaceChildren();
  const hunks = kpHunks(rows);
  if (!hunks.length) {
    const none = document.createElement("p"); none.className = "note kp-none";
    none.append(text("No changes from the saved file.")); box.append(none); return;
  }
  for (const hunk of hunks) {
    const olds = hunk.filter((r) => r.old !== null), nows = hunk.filter((r) => r.now !== null);
    const head = "@@ -" + (olds.length ? olds[0].old : 0) + "," + olds.length
      + " +" + (nows.length ? nows[0].now : 0) + "," + nows.length + " @@";
    box.append(kpRow([["kp-ln", ""], ["kp-ln", ""], ["kp-txt", head]], "@", null));
    for (const row of hunk) {
      const oldNo = row.kind === "-" ? "-" + row.old : row.old === null ? "" : String(row.old);
      const nowNo = row.kind === "+" ? "+" + row.now : row.now === null ? "" : String(row.now);
      box.append(kpRow([["kp-ln", oldNo], ["kp-ln", nowNo], ["kp-txt", row.line || "​"]],
                       row.kind, row.now !== null ? row.now : row.old));
    }
  }
}
function kpRenderCurrent(rows) {
  const gutter = el("kp-cur-gutter"), back = el("kp-after-backdrop");
  gutter.replaceChildren(); back.replaceChildren();
  for (const row of rows) {
    if (row.kind === "-") continue;
    const numbers = document.createElement("div");
    numbers.className = "kp-gline" + (row.kind === "+" ? " kp-add" : "");
    const oldCell = document.createElement("span"); oldCell.className = "kp-ln";
    oldCell.append(text(row.old === null ? "" : String(row.old)));
    const nowCell = document.createElement("span"); nowCell.className = "kp-ln";
    nowCell.append(text(row.kind === "+" ? "+" + row.now : String(row.now)));
    numbers.append(oldCell, nowCell); gutter.append(numbers);
    const shade = document.createElement("div");
    shade.className = row.kind === "+" ? "kp-add" : "kp-same";
    shade.append(text(row.line || "​")); back.append(shade);
  }
  kpSyncCurrent();
}
function kpRenderPanes() {
  const current = el("kp-rule-text").value;
  const rows = kpNumbered(kpDiffLines(kpRuleSaved, current));
  const added = rows.filter((r) => r.kind === "+").length;
  const removed = rows.filter((r) => r.kind === "-").length;
  el("kp-diff-summary").textContent = added || removed
    ? "· +" + added + " added, −" + removed + " removed" : "";
  const preview = kpRuleMode === "preview";
  el("kp-md-view").hidden = preview; el("kp-after-preview").hidden = !preview;
  if (preview) {
    el("kp-after-preview").replaceChildren(renderMarkdown(current));
  } else {
    kpRenderPrevious(rows); kpRenderCurrent(rows);
  }
  kpRuleDirty();
}
function kpSyncCurrent() {
  const area = el("kp-rule-text");
  el("kp-after-backdrop").scrollTop = area.scrollTop;
  el("kp-after-backdrop").scrollLeft = area.scrollLeft;
  el("kp-cur-gutter").scrollTop = area.scrollTop;
}
function kpAlign(fromCurrent) {
  // Keep Previous and Current on the same line while either scrolls.
  if (kpSyncing) return;
  kpSyncing = true;
  const area = el("kp-rule-text"), prev = el("kp-prev-body");
  const rows = [...el("kp-prev").querySelectorAll(".kp-drow[data-now]")];
  if (rows.length) {
    if (fromCurrent) {
      const line = Math.floor(area.scrollTop / KP_LINE) + 1;
      const target = rows.find((row) => Number(row.dataset.now) >= line) || rows[rows.length - 1];
      prev.scrollTop = target.offsetTop - el("kp-prev").offsetTop;
    } else {
      const top = prev.scrollTop + el("kp-prev").offsetTop;
      const target = rows.find((row) => row.offsetTop >= top) || rows[rows.length - 1];
      area.scrollTop = (Number(target.dataset.now) - 1) * KP_LINE;
      kpSyncCurrent();
    }
  }
  requestAnimationFrame(() => { kpSyncing = false; });
}
function kpRuleDirty() {
  const changed = el("kp-rule-text").value !== kpRuleSaved;
  el("kp-rule-dirty").textContent = changed ? " — unsaved changes" : "";
}
function kpTab(name) {
  kpRuleMode = name === "preview" ? "preview" : "md";
  for (const button of document.querySelectorAll(".kp-tabs [data-tab]")) {
    button.setAttribute("aria-selected", String(button.dataset.tab === kpRuleMode));
  }
  kpRenderPanes();
}
for (const button of document.querySelectorAll(".kp-tabs [data-tab]")) {
  button.addEventListener("click", () => kpTab(button.dataset.tab));
}
for (const head of document.querySelectorAll(".kp-block-head")) {
  head.addEventListener("click", () => {
    const block = el(head.dataset.block);
    const open = block.classList.toggle("kp-collapsed") === false;
    head.setAttribute("aria-expanded", String(open));
  });
}
el("kp-rule-text").addEventListener("input", () => {
  kpRuleDirty();
  clearTimeout(kpRenderTimer);
  kpRenderTimer = setTimeout(kpRenderPanes, 200);
});
el("kp-rule-text").addEventListener("scroll", () => { kpSyncCurrent(); kpAlign(true); });
el("kp-prev-body").addEventListener("scroll", () => kpAlign(false));
el("kp-rule-revert").addEventListener("click", () => {
  el("kp-rule-text").value = kpRuleSaved; kpTab(kpRuleMode);
});

// Splitters: drag to share the width; the widths are remembered on this browser.
const KP_PANES = ["kp-pane-file", "kp-pane-ai"];
function kpApplyWidths(widths) {
  KP_PANES.forEach((id, index) => { el(id).style.flexBasis = widths[index] + "%"; });
}
let kpWidths = [68, 32];
try {
  const kept = JSON.parse(localStorage.getItem("kp-pane-widths-2") || "null");
  if (Array.isArray(kept) && kept.length === 2) kpWidths = kept;
} catch (_ignored) { /* storage may be unavailable */ }
kpApplyWidths(kpWidths);
for (const split of document.querySelectorAll(".kp-split")) {
  split.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const left = KP_PANES.indexOf(split.dataset.left);
    const right = KP_PANES.indexOf(split.dataset.right);
    const total = el("kp-panes").getBoundingClientRect().width;
    const startX = event.clientX, start = [...kpWidths];
    try { split.setPointerCapture(event.pointerId); } catch (_ignored) { /* best effort */ }
    const move = (moved) => {
      const delta = (moved.clientX - startX) / total * 100;
      const pair = start[left] + start[right];
      const leftWidth = Math.min(pair - 10, Math.max(10, start[left] + delta));
      kpWidths[left] = leftWidth; kpWidths[right] = pair - leftWidth;
      kpApplyWidths(kpWidths);
    };
    const stop = () => {
      split.removeEventListener("pointermove", move);
      split.removeEventListener("pointerup", stop);
      try { localStorage.setItem("kp-pane-widths-2", JSON.stringify(kpWidths)); }
      catch (_ignored) { /* storage may be unavailable */ }
    };
    split.addEventListener("pointermove", move);
    split.addEventListener("pointerup", stop);
  });
}
// Maximize a pane over the page, and restore it.
function kpMaximize(id, on) {
  for (const pane of KP_PANES) el(pane).classList.toggle("kp-maxed", pane === id && on);
  for (const button of document.querySelectorAll(".kp-max")) {
    const maxed = button.dataset.pane === id && on;
    button.innerHTML = maxed ? "&#x2921;" : "&#x2922;";
    button.title = maxed ? "Restore" : "Maximize";
  }
}
for (const button of document.querySelectorAll(".kp-max")) {
  button.addEventListener("click", () => {
    kpMaximize(button.dataset.pane, !el(button.dataset.pane).classList.contains("kp-maxed"));
  });
}
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && document.querySelector(".kp-pane.kp-maxed")) {
    kpMaximize(null, false);
  }
});

const KP_ASSIST_STATES = [["collecting", "Reading the file, guide and a sample"],
  ["asking", "The model is writing"], ["checking", "Checking the proposal"]];
let kpAssistTurns = [];
function kpAssistShow(progress) {
  const log = el("kp-assist-log"); log.replaceChildren();
  for (const turn of kpAssistTurns) {
    const item = document.createElement("div"); item.className = "kp-turn kp-" + turn.role;
    item.append(turn.role === "user" ? text(turn.text) : renderMarkdown(turn.text));
    if (turn.proposal) {
      const note = document.createElement("p"); note.className = "note";
      note.append(text("The proposal is in Current file (added lines green; removed "
        + "ones red under Previous file); press Save to keep it."));
      item.append(note);
    }
    for (const warning of turn.warnings || []) {
      const line = document.createElement("p"); line.className = "bad";
      line.append(text("⚠ " + warning)); item.append(line);
    }
    log.append(item);
  }
  if (progress) {
    const item = document.createElement("div"); item.className = "kp-turn kp-running";
    const title = document.createElement("strong");
    title.append(text("Working… " + progress.elapsed_s + " s")); item.append(title);
    const steps = document.createElement("ol"); steps.className = "kp-steps";
    const reached = progress.history || [];
    for (const [key, label] of KP_ASSIST_STATES) {
      const li = document.createElement("li");
      const done = reached.includes(key) && progress.state !== key;
      li.className = progress.state === key ? "kp-now" : done ? "kp-done" : "kp-later";
      li.append(text((done ? "✓ " : progress.state === key ? "▶ " : "· ") + label));
      steps.append(li);
    }
    item.append(steps); log.append(item);
  }
  log.scrollTop = log.scrollHeight;
}
el("kp-assist-reset").addEventListener("click", () => { kpAssistTurns = []; kpAssistShow(); });
el("kp-assist-send").addEventListener("click", async () => {
  const message = el("kp-assist-input").value.trim();
  if (!message || !kpRulePath) return;
  kpAssistTurns.push({role: "user", text: message});
  el("kp-assist-input").value = "";
  el("kp-assist-send").disabled = true;
  avatarWorking(1);
  try {
    kpAssistShow({state: "collecting", history: ["collecting"], elapsed_s: 0});
    const started = await call("/api/knowledge/skill-assist", {
      sandbox_id: kpSandbox.sandbox_id, path: kpRulePath, current: el("kp-rule-text").value,
      turns: kpAssistTurns.map(({role, text}) => ({role, text}))});
    if (!started.ok) throw Object.assign(new Error(started.code), {code: started.code});
    let status;
    for (;;) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      status = await call("/api/knowledge/skill-assist?job=" + encodeURIComponent(started.job_id));
      if (!status.ok || status.state === "done" || status.state === "failed") break;
      kpAssistShow(status);
    }
    const result = status && status.result;
    if (!result || !result.ok) {
      throw Object.assign(new Error(result ? result.code : "skill_assist_failed"),
                          {code: result ? result.code : "skill_assist_failed"});
    }
    kpAssistTurns.push({role: "assistant", text: result.reply, proposal: result.proposal,
                        warnings: result.warnings});
    kpAssistShow();
    if (result.proposal) { el("kp-rule-text").value = result.proposal; kpTab("md"); }
  } catch (failure) {
    kpAssistTurns.pop(); kpAssistShow();
    kpStatus("The assistant did not answer: " + (failure.code || failure.message), true);
  } finally {
    el("kp-assist-send").disabled = false;
    avatarWorking(-1);
  }
});
el("kp-rule-save").addEventListener("click", () => kpRun("Saving the rule", async () => {
  if (!kpRulePath) return;
  const textNow = el("kp-rule-text").value;
  await pipeline("rule-write", {sandbox_id: kpSandbox.sandbox_id, path: kpRulePath,
                                text: textNow});
  kpRuleSaved = textNow; kpRuleDirty();
  kpRenderPanes();
  kpStatus("Saved " + kpRulePath + "; the next ingest uses it.");
  await kpLoadRules();
}));
let kpCandidate = null;
function kpMergeShow(report) {
  const box = el("kp-merge-result"); box.replaceChildren();
  box.append(text(report.changes.length + " changed pages, " + report.conflicts.length
    + " conflicts" + (report.kept_removed.length ? ", " + report.kept_removed.length
    + " removals kept back" : "") + "."));
  const list = document.createElement("ul");
  for (const change of report.changes) {
    const li = document.createElement("li");
    li.append(text(change.change + ": " + change.path + (change.parts.length
      ? " (" + change.parts.join(", ") + ")" : "") + (change.proposal ? " — proposal" : "")));
    list.append(li);
  }
  for (const conflict of report.conflicts) {
    const li = document.createElement("li");
    const key = conflict.path + "#" + conflict.part;
    const pick = document.createElement("select"); pick.dataset.key = key;
    for (const [value, label] of [["", "choose…"], ["sandbox", "keep sandbox"],
                                  ["published", "keep published"]]) {
      const option = document.createElement("option"); option.value = value;
      option.append(text(label)); pick.append(option);
    }
    const detail = document.createElement("details");
    const summary = document.createElement("summary"); summary.append(text("compare"));
    const sandbox = document.createElement("pre"); sandbox.append(text(conflict.sandbox));
    const published = document.createElement("pre"); published.append(text(conflict.published));
    detail.append(summary, text("Sandbox:"), sandbox, text("Published:"), published);
    li.append(text("conflict: " + key + " "), pick, detail); list.append(li);
  }
  box.append(list);
  if (report.candidate_root) {
    box.append(text("Candidate written: " + report.candidate_root + "; sourced lines lost: "
      + report.lost_sourced_lines + "; lint findings that grew: "
      + (Object.entries(report.lint_worse).map(([k, n]) => k + " +" + n).join(", ") || "none")));
  }
}
function kpResolutions() {
  const chosen = {};
  for (const pick of el("kp-merge-result").querySelectorAll("select[data-key]")) {
    if (pick.value) chosen[pick.dataset.key] = pick.value;
  }
  return chosen;
}
el("kp-merge-preview").addEventListener("click", () => kpRun("Comparing", async () => {
  kpMergeShow(await pipeline("merge", {sandbox_id: kpSandbox.sandbox_id}));
}));
el("kp-merge").addEventListener("click", () => kpRun("Merging", async () => {
  const report = await pipeline("merge", {sandbox_id: kpSandbox.sandbox_id, mode: "apply",
                                          resolutions: kpResolutions()});
  kpCandidate = {base: report.base_name, root: report.candidate_root};
  kpMergeShow(report); el("kp-publish").disabled = false;
}));
el("kp-publish").addEventListener("click", () => kpRun("Publishing", async () => {
  if (!kpCandidate || !confirm("Publish " + kpCandidate.root + " as the new version of "
      + kpCandidate.base + "? The Agent answers from it after a restart.")) return;
  const reply = await call("/api/knowledge/pipeline/publish",
    {base: kpCandidate.base, candidate_root: kpCandidate.root});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  el("kp-publish").disabled = true;
  el("kp-merge-result").append(text(" Published " + (reply.data.version || "")
    + " at " + reply.data.vault_root + ". Restart the Agent to answer from it."));
}));
el("kp-enrich").addEventListener("click", () => kpRun("Writing bilingual summaries", async () => {
  let report;
  do {
    report = await pipeline("index-enrich", {sandbox_id: kpSandbox.sandbox_id, limit: 60});
    el("kp-index-result").textContent = "Enriched " + report.done + " more; "
      + report.remaining + " pages remain.";
  } while (report.remaining > 0 && report.done > 0);
}));
el("kp-index").addEventListener("click", () => kpRun("Building the index", async () => {
  const preview = await pipeline("index-build", {sandbox_id: kpSandbox.sandbox_id});
  const counts = Object.entries(preview.categories).map(([k, n]) => k + " " + n).join(", ");
  if (!confirm("Write " + preview.written.length + " index pages? " + counts)) return;
  await pipeline("index-build", {sandbox_id: kpSandbox.sandbox_id, mode: "apply"});
  el("kp-index-result").textContent = "Index written: " + counts;
}));
el("kp-adopt").addEventListener("click", () => kpRun("Checking legacy Raw", async () => {
  const preview = await pipeline("adopt", {sandbox_id: kpSandbox.sandbox_id, mode: "dry_run"});
  if (!preview.raw_adopted) { el("kp-adopt-result").textContent = "Nothing to adopt."; return; }
  if (!confirm("Adopt " + preview.raw_adopted + " Raw files from earlier tooling? "
    + "Their bytes stay untouched; a ledger records them.")) return;
  const done = await pipeline("adopt", {sandbox_id: kpSandbox.sandbox_id, mode: "apply"});
  el("kp-adopt-result").textContent = "Adopted " + done.raw_adopted + ", drifted "
    + done.raw_drifted + ", unresolved pages " + done.pages_unresolved + ".";
  await kpOpen(kpSandbox);
}));
el("kp-discard").addEventListener("click", () => {
  if (!kpSandbox || !confirm("Discard this sandbox? It is moved aside, not deleted.")) return;
  kpRun("Discarding", async () => {
    await pipeline("sandbox-discard", {sandbox_id: kpSandbox.sandbox_id});
    kpSandbox = null; kpStage("pull"); await loadKnowledge();
  });
});

// -- Tasks (owner 2026-10-13): Workflows and background jobs, newest 50 --------
const TASK_KINDS = {workflow: "Workflow", proposal: "Proposed change",
  convert: "Convert", preview: "Preview convert",
  reingest: "Re-ingest", benchmark: "Benchmark", push: "Push",
  experience_review: "Experience review"};
const TASK_LABELS = {running: "running", succeeded: "done", failed: "failed",
  needs_input: "needs you", stopped: "stopped", interrupted: "interrupted"};
let taskTimer = null;

function taskTime(iso) {
  if (!iso) return "";
  const when = new Date(iso);
  return isNaN(when) ? iso : when.toLocaleString();
}

function taskDuration(task) {
  const start = Date.parse(task.started), end = task.ended ? Date.parse(task.ended) : Date.now();
  if (isNaN(start) || isNaN(end)) return "";
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  return seconds < 60 ? seconds + " s" : Math.floor(seconds / 60) + " min " + (seconds % 60) + " s";
}

async function loadTasks() {
  clearTimeout(taskTimer);
  loadPendingCards().catch(() => {});
  const reply = await call("/api/tasks");
  const counts = reply.counts || {};
  el("task-counts").textContent = reply.tasks.length + " tasks: "
    + Object.entries(TASK_LABELS).filter(([key]) => counts[key])
      .map(([key, label]) => counts[key] + " " + label).join(", ");
  el("task-list").replaceChildren(table(["Status", "Task", "Kind", "Started", "Took", "Result"],
    reply.tasks, (task) => {
      const badge = document.createElement("span");
      badge.className = "task-status " + task.status;
      badge.append(text(TASK_LABELS[task.status] || task.status));
      return [badge, task.title + (task.where && task.kind !== "workflow"
        ? " (" + task.where + ")" : ""), TASK_KINDS[task.kind] || task.kind,
        taskTime(task.started), taskDuration(task), task.summary];
    }));
  if (reply.tasks.some((task) => task.status === "running")
      && el("panel-tasks").hasAttribute("data-open")) {
    taskTimer = setTimeout(() => loadTasks().catch(() => {}), 3000);
  }
}
el("task-refresh").addEventListener("click", () => loadTasks().catch((failure) => {
  el("task-counts").textContent = failure.message;
}));

// -- The memory page (accumulated memory M4) --------------------------------
// The person's own memory, one overview call; every action is a token-checked
// route that acts only for the signed-in actor. Nothing here is a model tool.
const MEM_PANES = ["confirm", "preferences", "notes", "data", "sync", "records"];
let memData = null, memPane = "confirm";
// The sections an action on a preference, a note or a sync state changes.
const MEM_PREFERENCES = ["preferences", "spaces"], MEM_NOTES = ["notes", "spaces"];
const MEM_SYNC = ["sync", "spaces"];
const memSelected = new Set();

function memEl(tagName, className, ...children) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  for (const child of children) {
    if (child == null || child === "") continue;
    node.append(child instanceof Node ? child : text(child));
  }
  return node;
}

function memButton(label, onClick, kind, aria) {
  const button = document.createElement("button");
  button.type = "button"; button.className = "mem-btn" + (kind ? " " + kind : "");
  button.append(text(label));
  if (aria) button.setAttribute("aria-label", aria);
  button.addEventListener("click", (event) => {
    event.preventDefault(); Promise.resolve(onClick()).catch((failure) =>
      memNotice({ok: false, message: failure.message}));
  });
  return button;
}

function memNotice(reply, undo, sections) {
  const box = el("mem-notice"); box.replaceChildren();
  if (!reply) { box.className = "mem-notice"; return; }
  box.className = "mem-notice " + (reply.ok ? "good" : "bad");
  box.append(memEl("span", "", reply.message || reply.code || ""));
  if (reply.ok && undo) {
    box.append(memButton("復原", async () => {
      memNotice(null);
      const back = await undo();
      if (back && back.ok) await loadMemory(sections);
      memNotice(back, null);
    }, "link"));
  }
}

// One action: the sections it changed (`sections`; all when not given) drawn
// again from the server, then the answer in the notice (with 復原 when
// `undoFor` gives one).
async function memAct(path, body, undoFor, sections) {
  memNotice(null);
  let reply;
  try { reply = await call(path, body); }
  catch (failure) { reply = {ok: false, message: failure.message}; }
  const undo = reply.ok && undoFor ? undoFor(reply) : null;
  if (reply.ok) await loadMemory(sections);
  memNotice(reply, undo, sections);
  return reply;
}

const memUndo = (kind) => (reply) => reply.change_id
  ? () => call("/api/memory/undo", {kind, change_id: reply.change_id}) : null;

function memDownload(filename, body, type) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([body], {type}));
  link.download = filename; document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 30000);
}

function memShortRef(ref) {
  return ref.length > 28 ? ref.slice(0, 18) + "…" + ref.slice(-6) : ref;
}

async function memOpenConversation(sessionId, messageId) {
  const listed = await call("/api/conversations?session_id=" + encodeURIComponent(sessionId));
  if (!listed.selected || listed.selected.session_id !== sessionId) {
    memNotice({ok: false, message: "這段對話已經刪除了；偏好與筆記仍保留。"}); return;
  }
  await selectPrimaryTab("ask");
  activeConversation = sessionId; log.replaceChildren();
  await loadChat(sessionId);
  const target = [...log.querySelectorAll(".turn")].find((block) =>
    block.dataset.askedId === messageId || block.dataset.messageId === messageId);
  if (target) {
    for (const old of log.querySelectorAll(".turn.sg-target")) old.classList.remove("sg-target");
    target.classList.add("sg-target");
    target.scrollIntoView({block: "center"}); target.focus({preventScroll: true});
  }
}

// Which pane shows each overview section (B3): a pane says 「載入中…」 while
// its sections load, its count shows 「…」, a failure shows inline with 重試,
// and an action reloads only the sections it changed.
const MEM_SECTION_PANES = {proposals: "confirm", health: "confirm", preferences: "preferences",
  notes: "notes", spaces: "data", sync: "sync", records: "records", deletions: "records"};

function memPanesOf(sections) {
  if (!sections) return MEM_PANES.slice();
  const panes = new Set(sections.map((name) => MEM_SECTION_PANES[name]).filter(Boolean));
  if (sections.includes("spaces")) panes.add("records");  // 紀錄 lists the spaces too
  return [...panes];
}

function memCount(pane, value) {
  const button = document.querySelector('#mem-tabs [data-mem="' + pane + '"]');
  if (button) button.querySelector(".mem-count").textContent = value;
}

function memStatus(pane, state, message, retry) {
  const box = el("mem-status-" + pane); box.replaceChildren();
  box.className = "mem-status" + (state ? " " + state : "");
  box.hidden = !state;
  const panel = el("mem-pane-" + pane);
  if (state === "loading") panel.setAttribute("aria-busy", "true");
  else panel.removeAttribute("aria-busy");
  if (state === "loading") box.append(memEl("span", "mem-spinner"), memEl("span", "", message));
  if (state === "error") {
    box.append(memEl("span", "", message));
    if (retry) box.append(memButton("重試", retry, "link"));
  }
}

// The overview, or only `sections` of it once the page has the rest. Never
// throws: a failure is shown on the panes it concerns.
async function loadMemory(sections) {
  const only = Array.isArray(sections) && sections.length && memData ? sections : null;
  const panes = memPanesOf(only);
  const first = !memData;
  for (const pane of panes) {
    memStatus(pane, "loading", first ? "載入中…" : "更新中…");
    // Until the first answer the counts are unknown (「…」), never empty;
    // afterwards the shown ones stay while a pane updates.
    if (first) memCount(pane, "…");
  }
  if (first) el("mem-health-run").disabled = true;
  let reply;
  try {
    reply = await call("/api/memory/overview"
      + (only ? "?only=" + encodeURIComponent(only.join(",")) : ""));
    if (!reply || !reply.ok) throw new Error((reply && (reply.message || reply.code)) || "");
  } catch (failure) {
    for (const pane of panes) {
      memStatus(pane, "error", "載入失敗" + (failure.message ? "：" + failure.message : "")
        + "。", () => loadMemory(sections));
      if (!memData) memCount(pane, "—");
    }
    return;
  }
  memData = only ? {...memData, ...reply} : reply;
  for (const pane of panes) memStatus(pane, "");
  memRender();
}

function memShow(name) {
  memPane = name;
  for (const button of document.querySelectorAll("#mem-tabs [data-mem]")) {
    button.setAttribute("aria-selected", String(button.dataset.mem === name));
  }
  for (const key of MEM_PANES) el("mem-pane-" + key).hidden = key !== name;
}

function memRender() {
  if (!memData || !memData.ok) return;
  const counts = {
    confirm: memData.proposals.length + memData.health.findings.length,
    preferences: memData.preferences.reduce((sum, group) => sum + group.items.length, 0),
    notes: memData.notes.notes.length, data: memData.spaces.length, sync: memData.sync.length,
    records: null,
  };
  for (const button of document.querySelectorAll("#mem-tabs [data-mem]")) {
    const count = counts[button.dataset.mem];
    const status = el("mem-status-" + button.dataset.mem);
    // A pane still loading (or failed) keeps its 「…」 or 「—」.
    if (status && !status.hidden) continue;
    button.querySelector(".mem-count").textContent = count == null ? "" : String(count);
  }
  memShow(memPane);
  memRenderConfirm(); memRenderPreferences(); memRenderNotes(); memRenderSpaces();
  memRenderSync(); memRenderRecords();
}

// 待確認: the health check's findings (M5), then the spaces' proposals.
function memRenderHealth() {
  const health = memData.health;
  const run = el("mem-health-run");
  run.disabled = !health.settings.enabled;
  const last = health.last_run;
  el("mem-health-last").textContent = !health.settings.enabled
    ? "健康檢查已關閉（在「紀錄」可以打開）。"
    : last ? "上次檢查：" + last.at_local + "（每晚自動檢查；只找問題，不會自己改資料）"
    : "還沒檢查過（每晚自動檢查；只找問題，不會自己改資料）";
  const list = el("mem-health-list"); list.replaceChildren();
  for (const item of health.findings) {
    const card = memEl("article", "mem-item mem-health"); card.dataset.finding = item.finding_id;
    card.append(memEl("div", "mem-item-head", memEl("strong", "", item.title),
      memEl("span", "tag mem-health-tag", "健康檢查：" + item.kind_label)));
    const pairs = memEl("dl", "mem-pairs");
    for (const [label, value] of item.pairs) {
      pairs.append(memEl("dt", "", label), memEl("dd", "", value || "—"));
    }
    pairs.append(memEl("dt", "", "發現"), memEl("dd", "", item.created_at_local));
    const actions = memEl("div", "mem-actions");
    for (const choice of item.actions) {
      actions.append(memButton(choice.label, () => memHealthDecide(item, choice), choice.style));
    }
    for (const link of item.links) {
      actions.append(memButton(link.label, () => memGoto(link.person_id
        ? {kind: "person", id: link.person_id} : {kind: link.tab, id: link.id}), "link"));
    }
    card.append(pairs, actions); list.append(card);
  }
}

function memHealthDecide(item, choice) {
  if (choice.style === "danger" && !confirm(choice.label + "？可以復原。")) return;
  return memAct("/api/memory/health/decide", {finding_id: item.finding_id, action: choice.action},
    // 復原 undoes the fix and reopens the finding, so its card is back at
    // once (#233); the notice reloads the same sections.
    (reply) => reply.undo ? () => call("/api/memory/health/undo", reply.undo) : null,
    ["health", "proposals", "preferences", "spaces"]);
}

// Go to one item on the memory page (a finding's link, an answer's 「為什麼」).
// The target pane shows at once with 「開啟中…」 (#233): never the previous
// tab or person while the page loads.
async function memGoto(item) {
  const panes = {preference: "preferences", preferences: "preferences", note: "notes",
    notes: "notes", sync: "sync", records: "records", data: "data", person: "data"};
  const pane = panes[item.kind] || "confirm";
  const status = el("mem-status-" + pane);
  const opening = () => memStatus(pane, "loading", "開啟中…");
  memShow(pane);
  for (const old of document.querySelectorAll(".mem-item.mem-target")) {
    old.classList.remove("mem-target");
  }
  if (item.kind === "person") el("mem-person").replaceChildren();
  opening();
  try {
    if (!el("panel-memory").hasAttribute("data-open")) await selectPrimaryTab("memory");
    else if (!memData) await loadMemory();
    if (status.classList.contains("error")) return;
    memShow(pane);
    if (item.kind === "person") { opening(); await memOpenPerson(item.id); return; }
    memFind(item, pane);
  } finally {
    if (status.classList.contains("loading")) memStatus(pane, "");
  }
}

function memFind(item, pane) {
  if (pane === "notes") {
    el("mem-note-search").value = ""; el("mem-note-tag").value = "";
    el("mem-note-entity").value = ""; memRenderNotes();
  }
  const selectors = {preferences: "[data-preference]", notes: "[data-note]",
    sync: "[data-sync]", records: "[data-record-space]"};
  const found = [...document.querySelectorAll("#mem-pane-" + pane + " "
    + (selectors[pane] || ".mem-item"))].find((node) => {
    const value = node.dataset.preference || node.dataset.note || node.dataset.recordSpace
      || node.dataset.sync || "";
    return value === item.id || value.endsWith("|" + item.id);
  });
  if (found) {
    found.classList.add("mem-target"); found.scrollIntoView({block: "center"});
  } else if (item.kind === "preference" || item.kind === "note") {
    memNotice({ok: false, message: "這一項已經刪除或停用了。"});
  }
}

function memRenderConfirm() {
  memRenderHealth();
  const list = el("mem-confirm-list"); list.replaceChildren();
  if (!memData.proposals.length) {
    if (!memData.health.findings.length) {
      list.append(memEl("p", "empty", "沒有待確認的項目。"));
    }
    return;
  }
  for (const item of memData.proposals) {
    const card = memEl("article", "mem-item"); card.dataset.proposal = item.proposal_id;
    card.append(memEl("div", "mem-item-head",
      memEl("strong", "", item.entity_label + " · " + item.field_label),
      memEl("span", "tag", item.space_label)));
    const pairs = memEl("dl", "mem-pairs");
    const evidence = [item.source_label, item.evidence_date,
      item.evidence_ref ? memShortRef(item.evidence_ref) : ""].filter(Boolean).join(" · ");
    pairs.append(memEl("dt", "", "存著的"), memEl("dd", "", item.current || "（空白）"),
      memEl("dt", "", "新讀到"), memEl("dd", "mem-new", item.proposed),
      memEl("dt", "", "證據"), memEl("dd", "", evidence || "—"),
      memEl("dt", "", "提出"), memEl("dd", "", item.created_at_local));
    const actions = memEl("div", "mem-actions");
    actions.append(memButton("保留原值", () => memDecide(item, "keep")));
    if (item.actions.includes("accept")) {
      actions.append(memButton("改用新值", () => memDecide(item, "accept"), "primary"));
    }
    if (item.person_id) {
      actions.append(memButton("開啟該聯絡人", () => memOpenPerson(item.person_id), "link"));
    }
    card.append(pairs, actions); list.append(card);
  }
}

function memDecide(item, action) {
  return memAct("/api/memory/proposals/decide",
    {space: item.space, proposal_id: item.proposal_id, action},
    (reply) => reply.undo ? () => call("/api/memory/proposals/undo",
      {space: item.space, change_id: reply.change_id}) : null, ["proposals", "spaces"]);
}

// 偏好
function memRenderPreferences() {
  const box = el("mem-preferences-list"); box.replaceChildren();
  if (!memData.preferences.length) {
    box.append(memEl("p", "empty",
      "還沒有偏好。在對話中說出規則，按卡片上的「存成偏好」才會保存。")); return;
  }
  for (const group of memData.preferences) {
    box.append(memEl("h3", "mem-group", group.label));
    for (const item of group.items) box.append(memPreference(item));
  }
}

function memPreference(item) {
  const card = memEl("article", "mem-item"); card.dataset.preference = item.preference_id;
  card.append(memEl("p", "mem-text", item.text));
  const meta = memEl("div", "mem-meta", item.created_by + " · " + item.created_at_local);
  if (item.updated_at !== item.created_at) {
    meta.append(memEl("span", "", "修改於 " + item.updated_at_local));
  }
  if (item.source_session) {
    meta.append(memButton("來源對話", () => memOpenConversation(item.source_session,
      item.source_message), "link", "開啟存下這條偏好的對話"));
  }
  card.append(meta);
  if (item.used_count) {
    const used = memEl("details", "mem-used",
      memEl("summary", "", "用過 " + item.used_count + " 次"));
    const uses = memEl("div", "mem-results");
    for (const use of item.used) {
      uses.append(memButton(use.at_local + " · " + (use.title || use.session_id),
        () => memOpenConversation(use.session_id, use.message_id), "link"));
    }
    used.append(uses); card.append(used);
  }
  const editor = memEl("div", "mem-editor"); editor.hidden = true;
  const area = document.createElement("textarea");
  area.value = item.text; area.maxLength = 300; area.setAttribute("aria-label", "偏好內容");
  const conflict = memEl("div", "mem-conflict"); conflict.hidden = true;
  const save = async (resolve, replace) => {
    memNotice(null);
    let reply;
    try {
      reply = await call("/api/memory/preferences/edit",
        {id: item.preference_id, text: area.value, resolve: resolve || "", replace: replace || []});
    } catch (failure) { reply = {ok: false, message: failure.message}; }
    if (reply.code === "preference_conflict") {
      conflict.hidden = false;
      conflict.replaceChildren(memEl("p", "", "這條和同一個 Skill 既有的偏好矛盾，要怎麼辦？"));
      for (const other of reply.conflicts) conflict.append(memEl("p", "", "既有：" + other.text));
      conflict.append(memEl("p", "", "修改後：" + area.value));
      const ids = reply.conflicts.map((other) => other.preference_id);
      conflict.append(memEl("div", "mem-actions",
        memButton("取代舊的", () => save("replace", ids), "primary"),
        memButton("兩條都留", () => save("keep_both", [])),
        memButton("取消", () => { conflict.hidden = true; })));
      return;
    }
    if (reply.ok) await loadMemory(MEM_PREFERENCES);
    memNotice(reply, reply.ok ? memUndo("preference")(reply) : null, MEM_PREFERENCES);
  };
  editor.append(area, conflict, memEl("div", "mem-actions",
    memButton("儲存", () => save("", []), "primary"),
    memButton("取消", () => {
      editor.hidden = true; area.value = item.text; conflict.hidden = true;
    })));
  card.append(memEl("div", "mem-actions",
    memButton("修改", () => { editor.hidden = false; area.focus(); }),
    memButton("刪除", () => {
      if (!confirm("刪除這條偏好？之後使用『" + item.scope_label
        + "』時不再套用。可以復原。")) return;
      return memAct("/api/memory/delete", {kind: "preference", id: item.preference_id},
        memUndo("preference"), MEM_PREFERENCES);
    }, "danger")), editor);
  return card;
}

// 筆記
function memNoteVisible(note) {
  const words = el("mem-note-search").value.toLowerCase().split(/\s+/).filter(Boolean);
  const tag = el("mem-note-tag").value, entity = el("mem-note-entity").value;
  if (tag && !note.tags.some((item) => item.toLowerCase() === tag.toLowerCase())) return false;
  if (entity && !note.entities.includes(entity)) return false;
  const haystack = (note.text + " " + note.tags.join(" ")).toLowerCase();
  return words.every((word) => haystack.includes(word));
}

function memFillSelect(select, first, options) {
  const chosen = select.value; select.replaceChildren(new Option(first, ""));
  for (const [value, label] of options) select.append(new Option(label, value));
  select.value = options.some(([value]) => value === chosen) ? chosen : "";
}

function memRenderNotes() {
  const notes = memData.notes;
  memFillSelect(el("mem-note-tag"), "所有標籤", notes.tags.map((tag) => [tag, "#" + tag]));
  memFillSelect(el("mem-note-entity"), "所有關聯對象", Object.entries(notes.entities));
  const list = el("mem-notes-list"); list.replaceChildren();
  const known = new Set(notes.notes.map((note) => note.note_id));
  for (const id of [...memSelected]) if (!known.has(id)) memSelected.delete(id);
  const shown = notes.notes.filter(memNoteVisible);
  el("mem-note-all").checked = shown.length > 0
    && shown.every((note) => memSelected.has(note.note_id));
  if (!notes.notes.length) {
    list.append(memEl("p", "empty",
      "還沒有筆記。在回答旁按 📝「存成筆記」，或選取一段文字存起來。"));
    return;
  }
  if (!shown.length) { list.append(memEl("p", "empty", "沒有符合的筆記。")); return; }
  for (const note of shown) list.append(memNote(note, notes.entities));
}

function memNote(note, labels) {
  const card = memEl("article", "mem-item"); card.dataset.note = note.note_id;
  const pick = document.createElement("input"); pick.type = "checkbox";
  pick.checked = memSelected.has(note.note_id);
  pick.addEventListener("change", () => {
    if (pick.checked) memSelected.add(note.note_id); else memSelected.delete(note.note_id);
  });
  card.append(memEl("div", "mem-note-head",
    memEl("label", "mem-check", pick, note.created_at_local),
    memEl("span", "mem-meta", note.note_id)));
  const edit = (body) => memAct("/api/memory/notes/edit", {id: note.note_id, ...body},
    memUndo("note"), MEM_NOTES);
  const chips = memEl("div", "mem-chips");
  for (const tag of note.tags) {
    chips.append(memEl("span", "mem-chip", "#" + tag, memButton("×",
      () => edit({tags: note.tags.filter((item) => item !== tag)}), "", "移除標籤 " + tag)));
  }
  for (const ref of note.entities) {
    const label = labels[ref] || ref;
    chips.append(memEl("span", "mem-chip entity", label, memButton("×",
      () => edit({entities: note.entities.filter((item) => item !== ref)}), "",
      "取消連結 " + label)));
  }
  if (chips.childNodes.length) card.append(chips);
  const body = memEl("div", "mem-note-body kp-markdown"); body.append(renderMarkdown(note.text));
  card.append(body);
  const meta = memEl("div", "mem-meta", note.created_by);
  if (note.updated_at !== note.created_at) {
    meta.append(memEl("span", "", "修改於 " + note.updated_at_local));
  }
  if (note.source && note.source.conversation) {
    meta.append(memButton("開啟原本的對話", () => memOpenConversation(note.source.conversation,
      note.source.message), "link"));
  }
  card.append(meta);
  const extra = memEl("div", "");
  const editor = () => {
    const area = document.createElement("textarea"); area.value = note.text;
    area.setAttribute("aria-label", "筆記內容（Markdown）");
    extra.replaceChildren(memEl("div", "mem-editor", area, memEl("div", "mem-actions",
      memButton("儲存", () => edit({text: area.value}), "primary"),
      memButton("取消", () => extra.replaceChildren()))));
    area.focus();
  };
  const tagger = () => {
    const input = memEl("input", "mem-field"); input.placeholder = "新標籤";
    input.setAttribute("aria-label", "新標籤");
    const add = () => input.value.trim() && edit({tags: [...note.tags, input.value.trim()]});
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") add(); });
    extra.replaceChildren(memEl("div", "mem-inline", input, memButton("加入", add, "primary"),
      memButton("取消", () => extra.replaceChildren())));
    input.focus();
  };
  const linker = () => {
    const input = memEl("input", "mem-field"); input.type = "search";
    input.placeholder = "搜尋聯絡人"; input.setAttribute("aria-label", "搜尋要連結的聯絡人");
    const results = memEl("div", "mem-results");
    const find = async () => {
      const found = await call("/api/memory/people?q=" + encodeURIComponent(input.value.trim()));
      results.replaceChildren();
      if (!found.ok) { results.append(memEl("p", "empty", found.message || found.code)); return; }
      if (!found.people.length) {
        results.append(memEl("p", "empty", "找不到符合的聯絡人。")); return;
      }
      for (const person of found.people.slice(0, 8)) {
        const ref = "contacts/org:person:" + person.person_id;
        const label = person.name + (person.company ? "（" + person.company + "）" : "");
        results.append(memButton(note.entities.includes(ref) ? label + "（已連結）" : label,
          () => note.entities.includes(ref) ? null : edit({entities: [...note.entities, ref]}),
          "link", "連結 " + label));
      }
    };
    input.addEventListener("keydown", (event) => { if (event.key === "Enter") find(); });
    extra.replaceChildren(memEl("div", "mem-inline", input, memButton("搜尋", find, "primary"),
      memButton("取消", () => extra.replaceChildren())), results);
    input.focus();
  };
  card.append(memEl("div", "mem-actions",
    memButton("修改", editor), memButton("加標籤", tagger), memButton("連結聯絡人", linker),
    memButton("刪除", () => {
      if (!confirm("刪除這則筆記？可以復原。")) return;
      return memAct("/api/memory/delete", {kind: "note", id: note.note_id}, memUndo("note"),
        MEM_NOTES);
    }, "danger")), extra);
  return card;
}

async function memExportNotes() {
  memNotice(null);
  const shown = memData.notes.notes.filter(memNoteVisible).map((note) => note.note_id);
  const chosen = shown.filter((id) => memSelected.has(id));
  const ids = chosen.length ? chosen : shown;
  if (!ids.length) { memNotice({ok: false, message: "沒有可匯出的筆記。"}); return; }
  const reply = await call("/api/memory/notes/export?ids=" + encodeURIComponent(ids.join(",")));
  if (!reply.ok) { memNotice(reply); return; }
  memDownload(reply.filename, reply.markdown, "text/markdown;charset=utf-8");
  memNotice({ok: true, message: "已匯出 " + reply.count + " 則筆記（" + reply.filename + "）。"});
}

// 資料
const MEM_MANAGER_STATES = {on: ["已開啟", "on"], off: ["已關閉（唯讀）", "mem-off"],
  host: ["內建", "on"], missing: ["無主：管理的 Skill 已不在這台電腦", "mem-orphan"],
  outdated: ["Skill 已安裝但版本較舊：請更新 AEP，資料不必刪除", "mem-off"]};

function memRenderSpaces() {
  const list = el("mem-spaces-list"); list.replaceChildren();
  for (const space of memData.spaces) {
    const card = memEl("article", "mem-item"); card.dataset.space = space.space;
    const [stateLabel, stateClass] = MEM_MANAGER_STATES[space.manager_state]
      || [space.manager_state, ""];
    card.append(memEl("div", "mem-item-head", memEl("strong", "", space.label),
      memEl("span", "mem-meta", space.space), memEl("span", "tag " + stateClass, stateLabel)));
    const counts = space.counts.map((item) => item.label + " " + item.count).join("、") || "0";
    const pairs = memEl("dl", "mem-pairs");
    pairs.append(memEl("dt", "", "管理"),
      memEl("dd", "", space.manager_label + "（" + space.manager + "）"),
      memEl("dt", "", "種類"), memEl("dd", "", space.kind_labels.join("、")),
      memEl("dt", "", "敏感度"),
      memEl("dd", "", space.sensitivity_label + "（" + space.sensitivity + "）"),
      memEl("dt", "", "保留"), memEl("dd", "", space.retention_label),
      memEl("dt", "", "筆數"), memEl("dd", "", counts + (space.open_proposals
        ? "；待確認 " + space.open_proposals : "")),
      memEl("dt", "", "最後更新"), memEl("dd", "", space.last_updated_local || "—"));
    card.append(pairs);
    if (space.view === "people") {
      card.append(memEl("div", "mem-actions",
        memButton("開啟聯絡人", () => memOpenPeople(), "primary")));
    }
    list.append(card);
  }
}

async function memOpenPeople() {
  memShow("data"); el("mem-people").hidden = false;
  await memLoadPeople(); el("mem-people").scrollIntoView({block: "start"});
}

async function memLoadPeople() {
  const query = el("mem-people-search").value.trim(), status = el("mem-people-status").value;
  const reply = await call("/api/memory/people?q=" + encodeURIComponent(query)
    + "&status=" + encodeURIComponent(status));
  const list = el("mem-people-list"); list.replaceChildren();
  if (!reply.ok) { list.append(memEl("p", "empty", reply.message || reply.code)); return; }
  if (!reply.people.length) { list.append(memEl("p", "empty", "沒有符合的聯絡人。")); return; }
  const more = reply.total > reply.people.length
    ? "，列出前 " + reply.people.length + " 人" : "";
  list.append(memEl("p", "mem-meta", "共 " + reply.total + " 人" + more));
  for (const person of reply.people) {
    const card = memEl("article", "mem-item"); card.dataset.person = person.person_id;
    card.append(memEl("div", "mem-item-head",
      memEl("strong", "", person.name || person.romanised_name),
      memEl("span", "tag " + (person.status === "active" ? "on" : "mem-off"), person.status_label),
      person.open_proposals
        ? memEl("span", "tag mem-orphan", "待確認 " + person.open_proposals) : ""));
    card.append(memEl("div", "mem-meta", [person.company, person.department, person.title]
      .filter(Boolean).join(" · ")));
    if (person.email) card.append(memEl("div", "mem-meta", person.email));
    card.append(memEl("div", "mem-actions",
      memButton("歷史", () => memOpenPerson(person.person_id), "link", "歷史：" + person.name)));
    list.append(card);
  }
}

async function memOpenPerson(personId) {
  if (memPane !== "data" || el("mem-people").hidden) await memOpenPeople();
  const reply = await call("/api/memory/person?person_id=" + encodeURIComponent(personId));
  const box = el("mem-person"); box.replaceChildren();
  if (!reply.ok) { box.append(memEl("p", "empty", reply.message || reply.code)); return; }
  const person = reply.person;
  const panel = memEl("div", "mem-sub"); panel.id = "mem-person-panel";
  panel.append(memEl("h3", "", (person.name || person.romanised_name) + " 的歷史"),
    memEl("div", "mem-meta", [person.company, person.department, person.title, person.status_label]
      .filter(Boolean).join(" · ")));
  if (reply.proposals.length) {
    panel.append(memEl("p", "", "待確認 " + reply.proposals.length + " 項，在「待確認」處理。"));
  }
  const changes = memEl("ul", "mem-list");
  for (const item of reply.history) {
    const change = item.field_label ? item.field_label + "：" + (item.old_display || "（空白）")
      + " → " + (item.new_display || "（空白）") : "";
    changes.append(memEl("li", "", [item.at_local, item.kind_label, change, item.actor]
      .filter(Boolean).join(" · ")));
  }
  panel.append(memEl("strong", "", "變更"),
    reply.history.length ? changes : memEl("p", "empty", "沒有變更。"));
  const seen = memEl("ul", "mem-list");
  for (const item of reply.observations) {
    seen.append(memEl("li", "", [item.source_label, item.source_date,
      item.source_ref ? memShortRef(item.source_ref) : ""].filter(Boolean).join(" · ")));
  }
  panel.append(memEl("strong", "", "讀到的來源"),
    reply.observations.length ? seen : memEl("p", "empty", "沒有。"));
  box.append(panel); panel.scrollIntoView({block: "start"});
}

// 同步進度
function memRenderSync() {
  const list = el("mem-sync-list"); list.replaceChildren();
  if (!memData.sync.length) {
    list.append(memEl("p", "empty", "還沒有整理進度。第一次整理（例如問組織圖）後會出現在這裡。"));
    return;
  }
  for (const item of memData.sync) {
    const card = memEl("article", "mem-item");
    card.dataset.sync = item.space + "|" + item.source + "|" + item.key;
    card.append(memEl("div", "mem-item-head", memEl("strong", "", item.key),
      memEl("span", "mem-meta", item.source), memEl("span", "tag", item.space_label)));
    const pairs = memEl("dl", "mem-pairs");
    if (item.state) {
      pairs.append(memEl("dt", "", "整理到"), memEl("dd", "", item.state.last_message_date_local),
        memEl("dt", "", "擷取版本"), memEl("dd", "", item.state.extractor_version || "—"),
        memEl("dt", "", "更新"), memEl("dd", "", item.state.updated_by + " · "
          + item.state.updated_at_local));
    } else {
      pairs.append(memEl("dt", "", "狀態"), memEl("dd", "", "已重設，下次從頭整理"));
    }
    if (item.latest) {
      const actions = {advance: "前進", reset: "重設", restore: "復原"};
      pairs.append(memEl("dt", "", "上一次"), memEl("dd", "", (actions[item.latest.action]
        || item.latest.action) + " · " + item.latest.actor + " · " + item.latest.at_local));
    }
    const body = {space: item.space, source: item.source, key: item.key};
    const reset = memButton("重新整理", () => {
      if (!confirm("重新整理「" + item.key + "」（" + item.source + "）？"
        + "下次整理會從頭讀範圍內的來源。"
        + "按錯了可以「復原上次重設」。")) return;
      return memAct("/api/memory/sync/reset", body, null, MEM_SYNC);
    }, "danger");
    reset.disabled = !item.can_reset;
    const restore = memButton("復原上次重設",
      () => memAct("/api/memory/sync/restore", body, null, MEM_SYNC));
    restore.disabled = !item.can_restore;
    card.append(pairs, memEl("div", "mem-actions", reset, restore));
    list.append(card);
  }
}

// 紀錄: the health check's settings (M5), kept in the person's own database.
function memHealthSettings() {
  const settings = memData.health.settings;
  const section = memEl("div", "mem-sub"); section.id = "mem-health-settings";
  const on = document.createElement("input"); on.type = "checkbox"; on.id = "mem-health-on";
  on.checked = settings.enabled;
  const months = document.createElement("input"); months.type = "number"; months.min = "0";
  months.max = "120"; months.value = settings.freshness_months;
  months.className = "mem-field mem-days"; months.id = "mem-health-months";
  months.setAttribute("aria-label", "聯絡人多久沒出現就問是否仍在職（月；0 依規則）");
  const days = document.createElement("input"); days.type = "number"; days.min = "1";
  days.max = "3650"; days.value = settings.unused_days;
  days.className = "mem-field mem-days"; days.id = "mem-health-days";
  days.setAttribute("aria-label", "偏好多久沒用就提醒（天）");
  const rule = (memData.health.rule_periods || []).map((period) =>
    period.endsWith("M") ? period.slice(1, -1) + " 個月" : period.slice(1, -1) + " 天").join("、");
  const pairs = memEl("dl", "mem-pairs mem-records");
  pairs.append(memEl("dt", "", "每晚健康檢查"),
    memEl("dd", "", memEl("label", "mem-check", on,
      "打開（找重複、過期、矛盾、沒在用的偏好、無主的資料）")),
    memEl("dt", "", "聯絡人"), memEl("dd", "", memEl("span", "mem-inline", months,
      "個月沒出現就問是否仍在職（0 = 依空間的規則" + (rule ? "：" + rule : "") + "）")),
    memEl("dt", "", "偏好"), memEl("dd", "", memEl("span", "mem-inline", days,
      "天沒用到就提醒")));
  section.append(memEl("h3", "", "健康檢查"),
    memEl("p", "mem-intro", "健康檢查只找出問題放到「待確認」，不會自己改任何資料；"
      + "矛盾的偏好會用內部模型檢查（同一個 Skill 有兩條以上才問）。"),
    pairs, memEl("div", "mem-actions", memButton("儲存", () => memAct(
      "/api/memory/health/settings", {enabled: on.checked, freshness_months: Number(months.value),
        unused_days: Number(days.value)}, null, ["health"]), "primary")));
  return section;
}

// 任務摘要 (task result summaries, owner 2026-10-25): the recent ones with
// 刪除 and 存成筆記, and how many days they are kept (default 30).
function memTaskSummaries() {
  const section = memEl("div", "mem-sub"); section.id = "mem-task-summaries";
  const list = memEl("div", "", memEl("p", "mem-meta", "載入中…"));
  section.append(memEl("h3", "mem-group", "任務摘要"),
    memEl("p", "mem-intro", "每次執行完的結果摘要（任務、重點、產出、後續），存在這台電腦，"
      + "過了保留天數每晚自動刪除；不會自動存成筆記。"), list);
  const draw = async () => {
    let reply;
    try { reply = await call("/api/memory/task-summaries"); }
    catch (failure) { reply = {ok: false, message: failure.message}; }
    list.replaceChildren();
    if (!reply.ok) { list.append(memEl("p", "mem-meta", reply.message || reply.code)); return; }
    const days = document.createElement("input"); days.type = "number"; days.min = "1";
    days.max = "365"; days.value = reply.settings.retention_days;
    days.className = "mem-field mem-days"; days.id = "mem-summary-days";
    days.setAttribute("aria-label", "任務摘要保留天數");
    list.append(memEl("div", "mem-inline", "保留", days, "天",
      memButton("儲存", async () => {
        memNotice(null);
        const saved = await call("/api/memory/task-summaries/settings",
          {retention_days: Number(days.value)});
        memNotice(saved);
      })));
    if (!reply.summaries.length) { list.append(memEl("p", "empty", "還沒有任務摘要。")); return; }
    for (const item of reply.summaries) {
      const card = memEl("article", "mem-item"); card.dataset.summaryId = item.summary_id;
      const body = memEl("pre", "mem-summary"); body.textContent = item.block;
      card.append(memEl("div", "mem-item-head", memEl("strong", "", item.task),
        memEl("span", "mem-meta", item.at_local)), body,
      memEl("div", "mem-actions",
        memButton("存成筆記", async () => {
          memNotice(null);
          memNotice(await call("/api/memory/task-summaries/note", {id: item.summary_id}));
        }),
        memButton("刪除", async () => {
          memNotice(null);
          const gone = await call("/api/memory/task-summaries/delete", {id: item.summary_id});
          memNotice(gone);
          if (gone.ok) await draw();
        }, "danger")));
      list.append(card);
    }
  };
  draw();
  return section;
}

function memRenderRecords() {
  const box = el("mem-records"); box.replaceChildren();
  const records = memData.records;
  const days = document.createElement("input"); days.type = "number"; days.min = "1";
  days.max = "3650"; days.value = records.experience.retention_days;
  days.className = "mem-field mem-days"; days.id = "mem-experience-days";
  days.setAttribute("aria-label", "經驗回顧案例保留天數");
  const keep = memEl("dl", "mem-pairs mem-records");
  keep.append(memEl("dt", "", "對話"), memEl("dd", "", records.conversations.retention_label
      + "；每段對話保存最近 " + records.conversations.max_messages + " 則訊息。刪除對話在左側清單。"
      + "目前 " + records.conversations.count + " 段" + (records.conversations.count >= 100
        ? "以上" : "") + "。"),
    memEl("dt", "", "執行紀錄"), memEl("dd", "", "保留 " + records.runs.days + " 天，總量超過 "
      + records.runs.max_mb + " MB 時先刪最舊的（固定）。"),
    memEl("dt", "", "經驗回顧案例"), memEl("dd", "", memEl("span", "mem-inline", days, "天",
      memButton("儲存", async () => {
        memNotice(null);
        // The Reviews page's own setting and route (experience review).
        const reply = await call("/api/experience/settings", {retention_days: Number(days.value)});
        const saved = days.value;
        if (reply.ok !== false) await loadMemory(["records"]);
        memNotice(reply.ok === false ? {ok: false, message: "天數要在 1 到 3650 之間。"}
          : {ok: true, message: "已儲存：經驗回顧案例保留 " + saved + " 天。"});
      }))));
  for (const space of memData.spaces) {
    keep.append(memEl("dt", "", "記憶：" + space.label),
      memEl("dd", "", space.retention_label + "（由管理的 Skill 決定，目前不能在這裡改）"));
  }
  box.append(memEl("h3", "mem-group", "保留期限"), keep);
  box.append(memTaskSummaries());
  box.append(memHealthSettings());
  box.append(memEl("h3", "mem-group", "匯出與刪除記憶"),
    memEl("p", "mem-intro", "每個空間可以匯出成 JSON。刪除會永久清掉該空間的所有資料，不能復原，"
      + "只留下一筆刪除紀錄（時間、筆數，沒有內容）。"));
  for (const space of memData.spaces) {
    const card = memEl("article", "mem-item"); card.dataset.recordSpace = space.space;
    const confirmBox = memEl("div", "");
    const total = space.counts.reduce((sum, item) => sum + item.count, 0) + space.observations;
    card.append(memEl("div", "mem-item-head", memEl("strong", "", space.label),
      memEl("span", "mem-meta", space.space + " · " + total + " 筆")),
    memEl("div", "mem-actions",
      memButton("匯出 JSON", async () => {
        memNotice(null);
        const reply = await call("/api/memory/export?space=" + encodeURIComponent(space.space));
        if (!reply.ok) { memNotice(reply); return; }
        memDownload(reply.filename, JSON.stringify(reply.data, null, 2), "application/json");
        memNotice({ok: true, message: "已匯出『" + space.label + "』（" + reply.filename + "）。"});
      }),
      memButton("刪除資料…", () => {
        const input = memEl("input", "mem-field");
        input.setAttribute("aria-label", "輸入空間名稱確認");
        input.placeholder = space.space;
        const go = memButton("確定刪除", () => memAct("/api/memory/space/delete",
          {space: space.space, confirm: input.value.trim()}), "danger");
        go.disabled = true;
        input.addEventListener("input", () => {
          go.disabled = input.value.trim() !== space.space;
        });
        confirmBox.replaceChildren(memEl("div", "mem-danger",
          memEl("p", "", "會永久刪除『" + space.label + "』的所有資料（" + total + " 筆），"
            + "不能復原。"
            + "建議先匯出。"),
          space.space === "contacts/org" ? memEl("p", "",
            "舊版的 cards.db 與它的備份不在記憶資料庫裡，"
            + "不會被刪除。") : "",
          memEl("p", "", "請輸入 " + space.space + " 確認："),
          memEl("div", "mem-inline", input, go,
            memButton("取消", () => confirmBox.replaceChildren()))));
        input.focus();
      }, "danger")), confirmBox);
    box.append(card);
  }
  box.append(memEl("h3", "mem-group", "刪除紀錄"));
  if (!memData.deletions.length) { box.append(memEl("p", "empty", "沒有刪除過。")); return; }
  const done = memEl("ul", "mem-list");
  for (const item of memData.deletions) {
    const total = Object.values(item.counts).reduce((sum, count) => sum + count, 0);
    done.append(memEl("li", "", item.at_local + " · " + item.label + "（" + item.space + "）· "
      + total + " 筆 · " + item.actor));
  }
  box.append(done);
}

for (const button of document.querySelectorAll("#mem-tabs [data-mem]")) {
  button.addEventListener("click", () => { memNotice(null); memShow(button.dataset.mem); });
}
el("mem-refresh").addEventListener("click", () => loadMemory());
el("mem-health-run").addEventListener("click", () => {
  el("mem-health-last").textContent = "檢查中…";
  memAct("/api/memory/health/run", {}, null, ["health"]);
});
for (const id of ["mem-note-search", "mem-note-tag", "mem-note-entity"]) {
  el(id).addEventListener(id === "mem-note-search" ? "input" : "change", () => {
    if (memData) memRenderNotes();
  });
}
el("mem-note-all").addEventListener("change", () => {
  for (const note of memData.notes.notes.filter(memNoteVisible)) {
    if (el("mem-note-all").checked) memSelected.add(note.note_id);
    else memSelected.delete(note.note_id);
  }
  memRenderNotes();
});
el("mem-note-export").addEventListener("click", () => memExportNotes().catch((failure) =>
  memNotice({ok: false, message: failure.message})));
el("mem-people-search").addEventListener("keydown", (event) => {
  if (event.key === "Enter") memLoadPeople().catch(() => {});
});
el("mem-people-search").addEventListener("search", () => memLoadPeople().catch(() => {}));
el("mem-people-status").addEventListener("change", () => memLoadPeople().catch(() => {}));

// -- Knowledge sub-tabs and BI cards (Knowledge Strategy v1.3 Case A) -------
// 「BI 卡片」: a dataset of typed cards. Dashboard, a card browser with
// field-level sources and history, and the CSV import wizard (preview →
// per-card diff → 確認寫入 → 復原). Nothing is written before 確認寫入.
let knPane = "pipeline", knPipelineLoaded = false;

async function loadKnowledgeTab() {
  let stored = "pipeline";
  try { stored = localStorage.getItem("kn-pane") || "pipeline"; } catch (e) { /* */ }
  if (stored === "bi") { knShow("bi"); return; }
  knShow("pipeline", false);
  await loadKnowledge(); knPipelineLoaded = true;
}

function knShow(name, load = true) {
  knPane = name === "bi" ? "bi" : "pipeline";
  for (const button of document.querySelectorAll("#kn-tabs [data-kn]")) {
    button.setAttribute("aria-selected", String(button.dataset.kn === knPane));
  }
  el("kn-pane-pipeline").hidden = knPane !== "pipeline";
  el("kn-pane-bi").hidden = knPane !== "bi";
  el("kp-refresh").hidden = knPane !== "pipeline";
  try { localStorage.setItem("kn-pane", knPane); } catch (e) { /* */ }
  if (!load) return;
  if (knPane === "bi") biLoad();
  else if (!knPipelineLoaded) {
    knPipelineLoaded = true; kpRun("Reading", loadKnowledge);
  }
}

for (const button of document.querySelectorAll("#kn-tabs [data-kn]")) {
  button.addEventListener("click", () => knShow(button.dataset.kn));
}

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
    biRenderBar();
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
  await biShowView(bi.view);
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
}

function biRenderSchema() {
  const isBi = biIsBi(), schema = bi.schema || {};
  el("bi-demo").hidden = !isBi;
  el("bi-hint").hidden = !isBi;
  el("bi-domain-box").hidden = Array.isArray(schema.domains) && !schema.domains.length;
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
  el("bi-empty-state").hidden = !(empty && !bi.datasets.length);
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
  select.value = keep;
  const current = bi.datasets.find((item) => item.name === keep);
  const counts = el("bi-counts"); counts.replaceChildren();
  counts.append(bh("strong", "", String(current ? current.cards : 0)), text("張卡片"));
  counts.append(bh("span", "", current && current.updated ? "· 更新於 " + biTime(current.updated)
    : "· 尚未載入資料"));
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

async function biShowView(name) {
  // A dataset read from the platform cannot be built: it opens on the Dashboard.
  if (name === "build" && biReadOnly()) name = "dashboard";
  bi.view = name;
  for (const button of document.querySelectorAll("#bi-views [data-bi-view]")) {
    button.setAttribute("aria-selected", String(button.dataset.biView === name));
  }
  for (const key of ["dashboard", "cards", "build"]) {
    el("bi-view-" + key).hidden = key !== name;
  }
  if (bi.loaded[name]) return;
  if (name === "dashboard") await biLoadDashboard();
  if (name === "cards") { biFtsStatus(); await biLoadCards(); }
  if (name === "build") { bi.loaded.build = true; await biBuildLoad(); }
}

for (const button of document.querySelectorAll("#bi-views [data-bi-view]")) {
  button.addEventListener("click", () => biShowView(button.dataset.biView));
}
el("bi-refresh").addEventListener("click", () => biLoad());
// A publish draft belongs to the dataset it was made for: switching drops it.
function biLeaveDataset() {
  bi.cardId = null; bi.publish = null;
  biPanel("publish", false); el("bi-pub-result").hidden = true;
  el("bi-pub-state").replaceChildren();
}
el("bi-dataset").addEventListener("change", () => {
  biRemember(el("bi-dataset").value); biLeaveDataset(); biLoad();
});
el("bi-empty-demo").addEventListener("click", () => el("bi-demo").click());
el("bi-empty-new").addEventListener("click", () => biOpenNew());
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
el("bi-ask").addEventListener("click", () => {
  field.value = "哪些測試方案對應 WiFi 7？";
  selectPrimaryTab("ask");
});

// -- Dashboard -----------------------------------------------------------------
function biSectionKey(id) {
  const match = String(id == null ? "" : id).match(/(\d+[a-z]?)/i);
  return match ? match[1].toLowerCase() : String(id);
}

function biCell(value) {
  const box = document.createDocumentFragment();
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      if (index) box.append(text("、"));
      box.append(biCell(item));
    });
    return box;
  }
  if (value && typeof value === "object" && value.card_id) {
    box.append(biButton(value.label || value.card_id, () => biOpenCard(value.card_id), "bi-link"));
    return box;
  }
  if (value == null || value === "") { box.append(text("—")); return box; }
  const source = typeof value === "object" ? JSON.stringify(value) : String(value);
  const pattern = /\[\[card:([^|\]]+)\|([^\]]*)\]\]/g;
  let last = 0, match;
  while ((match = pattern.exec(source))) {
    if (match.index > last) box.append(text(source.slice(last, match.index)));
    const id = match[1], label = match[2] || match[1];
    box.append(biButton(label, () => biOpenCard(id), "bi-link"));
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
  const holder = el("bi-dash-sections"), strip = el("bi-dash-summary");
  if (reply.dashboard === false) {  // a dataset of a non-BI schema
    holder.append(bh("div", "bi-none", bh("h3", "", reply.message || "這個 schema 沒有 Dashboard"),
      bh("p", "", "資料集「" + biDataset() + "」使用「" + biSchemaTitle(reply.schema || "")
        + "」。Dashboard 與對話查詢只支援 BI schema（bi.schema/*）；這個資料集的卡片可以在"
        + "「卡片」瀏覽並提更正單，也可以在「建立與匯入」加入資料。"),
      bh("div", "bi-actions", biButton("看卡片", () => biShowView("cards"), "go"),
        biButton("建立與匯入", () => biShowView("build"), "bi-btn"))));
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
    + "&domain=" + encodeURIComponent(biDomain());
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
  el("bi-card-count").textContent = bi.cards.length + " 張卡片";
  if (!bi.cards.length) {
    list.append(bh("li", "bi-empty", el("bi-q").value.trim() || el("bi-type").value
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

async function biOpenCard(id) {
  bi.cardId = id;
  if (bi.view !== "cards") await biShowView("cards");
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
  if (focus) {
    const title = el("bi-detail-title");
    title.focus({preventScroll: true});
    if (window.matchMedia("(max-width: 900px)").matches) {
      el("bi-detail").scrollIntoView({block: "start"});
    }
  }
  biLoadHistory();
}

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
  if (card.domain != null) body.append(bh("p", "bi-meta", "領域：" + biValue(card.domain)));
  body.append(bh("h4", "", "欄位"));
  const list = bh("div", "bi-fields");
  for (const item of fields) list.append(biFieldRow(card, item));
  if (!fields.length) list.append(bh("p", "bi-empty", "沒有欄位。"));
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
  }
  row.append(foot);
  return row;
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
        + (item.reason ? " · 理由：" + item.reason : ""))));
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
  const keep = {stage: bi.build.stage, sourceId: bi.build.sourceId,
    runId: bi.build.run ? bi.build.run.id : null};
  try { localStorage.setItem(biBuildKey(), JSON.stringify(keep)); } catch (e) { /* */ }
}

function biBuildStored() {
  try { return JSON.parse(localStorage.getItem(biBuildKey()) || "{}") || {}; }
  catch (e) { return {}; }
}

function biBuildAllowed() {
  const run = bi.build.run, has = !!bi.build.sourceId;
  const open = run && run.kind === "ingest" && ["review", "partial"].includes(run.status);
  const accepted = open && run.summary && run.summary.accepted > 0;
  return {source: true, schema: true, method: has, review: has,
    commit: !!accepted && !bi.build.accepting, result: !!(run && run.status === "committed"),
    test: true};
}

function biBuildStepper(stage, allowed) {
  const ingest = BI_INGEST.includes(stage);
  stepperSet(el("bi-stepper"), ingest ? "ingest" : stage,
    {source: true, ingest: true, test: true}, "");
  stepperSet(el("bi-substeps"), stage, allowed, "先完成前面的步驟");
  el("bi-substeps").hidden = !ingest;
}

function biBuildSteps() { biBuildStepper(bi.build.stage, biBuildAllowed()); }

function biBuildStage(name, focus = true) {
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
  if (stage === "schema") biBuildSchema();
  if (stage === "method") biBuildMethodStage();
  if (stage === "review") biBuildRenderRun();
  if (stage === "commit") biBuildSummary();
  if (stage === "result") biBuildResult();
  if (stage === "test" && biVaultOf(biDataset())) {
    // What steps 1 and 2 changed (cards written, skills, schema) waits to be committed here.
    call("/api/bi/vaults/" + biVaultOf(biDataset()).id + "/status").then(biVaultState)
      .catch((failure) => biNotice(false, "讀不到知識庫的狀態：" + failure.message));
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
  button.addEventListener("click", () => biBuildStage(button.dataset.biNext));
}
for (const [id, view] of [["bi-b-to-dash", "dashboard"], ["bi-b-to-cards", "cards"]]) {
  el(id).addEventListener("click",
    () => document.querySelector('#bi-views [data-bi-view="' + view + '"]').click());
}

async function biBuildLoad() {
  const stored = biBuildStored();
  bi.build.sourceId = stored.sourceId || null;
  bi.build.run = null; bi.build.candidates = []; bi.build.candidateId = null;
  const schema = bi.schema || {};
  el("bi-b-target").textContent = "寫入目的地：資料集「" + biDataset() + "」・schema "
    + (schema.ref || schema.schema_id || "—") + "。";
  biBuildVault().catch((failure) => biNotice(false, "知識庫狀態沒有載入：" + failure.message));
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
    if (stored.runId) await biBuildFetchRun(stored.runId);
    biStatus("bi-status-build", "");
  } catch (failure) {
    biStatus("bi-status-build", "error", "載入失敗：" + failure.message + "。", biBuildLoad);
  }
  biBuildStage(stored.stage || "source", false);
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
  // Newest call only: a reload for the dataset shown before must not paint over this one.
  const seq = bi.vaultSeq = (bi.vaultSeq || 0) + 1;
  const reply = await call("/api/bi/vaults");
  if (seq !== bi.vaultSeq) return;
  bi.vaults = reply.vaults || [];
  const pick = el("bi-b-ds"); pick.replaceChildren();
  for (const item of bi.datasets.filter((d) => !d.read_only)) {
    const vault = biVaultOf(item.name);
    const option = bh("option", "", vault ? "共用：" + (vault.title || vault.id) + "（vault）"
      : item.name + (item.schema ? " · " + biSchemaTitle(item.schema) : ""));
    option.value = item.name; pick.append(option);
  }
  if (![...pick.options].some((o) => o.value === biDataset())) {
    const option = bh("option", "", biDataset()); option.value = biDataset(); pick.append(option);
  }
  pick.value = biDataset();
  const vault = biVaultOf(biDataset());
  el("bi-b-v-sync").hidden = !vault;
  el("bi-b-v-convert").hidden = Boolean(vault) || !bi.datasets.some((d) => d.name === biDataset());
  const box = el("bi-b-v-state"); box.replaceChildren();
  el("bi-b-ver-none").hidden = Boolean(vault);
  if (!vault) {
    el("bi-b-ver").hidden = true; el("bi-b-skills").hidden = true;
    el("bi-b-bench").hidden = true; el("bi-b-an").hidden = true;
    box.append(bh("p", "bi-meta", "這是只在這台電腦的資料集。要和同事一起維護，請建立或加入 vault，"
      + "或把它轉成 vault。"));
    return;
  }
  try { await biCall("/api/bi/vaults/" + vault.id + "/sync", {}); }
  catch (failure) { box.append(bh("p", "bi-warn", "沒有同步：" + failure.message + "。")); }
  const state = await call("/api/bi/vaults/" + vault.id + "/status");
  if (seq !== bi.vaultSeq) return;
  biVaultState(state);
  askableLoad().catch((failure) => { el("bi-b-askable").textContent = failure.message; });
}

function biVaultState(state) {
  const box = el("bi-b-v-state"), v = state.vault || {};
  box.replaceChildren();
  const open = (state.conflicts || []).filter((c) => c.open).length;
  box.append(bh("p", "", bh("strong", "", v.title || v.id), "・" + (v.purpose || "（沒有寫目的）")),
    bh("p", "bi-meta", "共用資料夾：" + v.path + "・你的作者名稱：" + v.author));
  if (!state.reachable) {
    box.append(bh("p", "bi-warn", "現在讀不到共用資料夾（OneDrive 沒有同步或路徑不對）："
      + "可以看卡片，但不能寫入。"));
    el("bi-b-ver").hidden = true; el("bi-b-skills").hidden = true;
    el("bi-b-bench").hidden = true; el("bi-b-an").hidden = true;
    return;
  }
  box.append(bh("p", "bi-meta", state.cards + " 張卡片・別人 push 了還沒套用的 " + state.behind
    + " 個・你還沒 push 的 commit " + state.ahead + " 個・還沒 commit 的改動 "
    + state.uncommitted + " 個・上次同步 " + (state.last_sync ? biTime(state.last_sync) : "—")));
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
  biAnalyses(v.id).catch((failure) => biNotice(false, "讀不到分析：" + failure.message));
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

function biBenchReport(report) {
  const box = el("bi-b-bench-report"); box.replaceChildren();
  if (!report) { box.append(bh("p", "bi-meta", "還沒有跑過測試。")); return; }
  const state = {running: "測試中…", finished: "完成", failed: "沒有跑完"}[report.status]
    || report.status;
  const head = "最近一次測試（" + biTime(report.started_at) + "，" + state + "）";
  box.append(bh("h5", "", head));
  if (report.error) box.append(bh("p", "bi-warn", "停在：" + report.error));
  if (report.status !== "running") {
    const parts = ["題目：工作版本 " + report.working_score + "/" + report.total
      + "、發佈版本 " + report.published_score + "/" + report.total];
    if ((report.regressions || []).length) parts.push("退步 " + report.regressions.length + " 題");
    if (report.extract) parts.push("擷取 " + report.extract.score + " 分");
    box.append(bh("p", "", parts.join("；")));
  }
  const regressed = new Set(report.regressions || []);
  const rows = [...(report.results || [])].sort((x, y) =>
    Number(regressed.has(y.unit)) - Number(regressed.has(x.unit)));
  const list = bh("ul", "bi-log");
  for (const row of rows) {
    const answers = bh("details", "", bh("summary", "", "看兩邊的回答"),
      bh("p", "", bh("strong", "", "工作版本："), row.working.answer || "（沒有）"),
      bh("p", "", bh("strong", "", "發佈版本："), row.published.answer || "（沒有）"));
    list.append(bh("li", regressed.has(row.unit) ? "bi-warn" : "",
      bh("strong", "", row.question), bh("br"),
      "工作版本：" + biBenchGrade(row.working) + "・發佈版本：" + biBenchGrade(row.published)
        + (regressed.has(row.unit) ? "・退步" : ""), answers));
  }
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
  const reply = await call("/api/bi/vaults/" + vaultId + "/checks");
  if (seq !== bi.benchSeq || vaultId !== bi.verVault) return;
  el("bi-b-bench").hidden = false;
  const questions = el("bi-b-bq-list"); questions.replaceChildren();
  if (!reply.questions.length) questions.append(bh("p", "bi-meta", "還沒有測試題。"));
  for (const q of reply.questions) {
    const terms = (q.must.length ? "必須提到：" + q.must.join("、") : "")
      + (q.must_not.length ? "　不可以說：" + q.must_not.join("、") : "");
    questions.append(bh("div", "bi-step", bh("strong", "", q.question),
      bh("p", "bi-meta", "題組 " + q.set + (terms ? "・" + terms : "・沒有評分條件")),
      bh("div", "bi-actions", biButton("刪除", () => biBenchSave({delete: q.unit}), "bi-btn",
        "刪除測試題 " + q.question))));
  }
  const cases = el("bi-b-bc-list"); cases.replaceChildren();
  if (!reply.cases.length) cases.append(bh("p", "bi-meta", "還沒有擷取測試。"));
  for (const c of reply.cases) {
    const count = ((c.expected || {}).candidates || []).length;
    cases.append(bh("div", "bi-step", bh("strong", "", c.slug),
      bh("p", "bi-meta", (c.folder || "sources") + "・應找到 " + count + " 張候選卡"),
      bh("div", "bi-actions", biButton("刪除", () => biBenchSave({delete: c.unit}), "bi-btn",
        "刪除擷取測試 " + c.slug))));
  }
  biBenchReport(reply.latest);
  el("bi-b-bench-run").disabled = !(reply.questions.length || reply.cases.length)
    || (reply.latest && reply.latest.status === "running");
  clearTimeout(bi.benchTimer);
  // A run just started may not have written its first report yet: keep reading until it has.
  const unseen = bi.benchWatch && (!reply.latest || reply.latest.run_id !== bi.benchWatch);
  if (unseen || (reply.latest && reply.latest.status === "running")) {
    bi.benchTimer = setTimeout(() => biBench(vaultId).catch(() => {}), unseen ? 300 : 2000);
  } else if (reply.latest && bi.benchWatch === reply.latest.run_id) {
    bi.benchWatch = null;
    biNotice(reply.latest.status === "finished", reply.latest.status === "finished"
      ? "測試跑完了。" : "測試沒有跑完：" + (reply.latest.error || ""));
  }
}

async function biBenchSave(body) {
  await biCall("/api/bi/vaults/" + bi.verVault + "/checks", body);
  biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
  biNotice(true, body.delete ? "已刪除（commit 並 push 後大家才會少這個測試）。"
    : "已加入（commit 並 push 後大家才會有這個測試）。");
  return true;
}

el("bi-b-bq-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await biBenchSave({question: el("bi-b-bq-q").value, must: el("bi-b-bq-must").value,
      must_not: el("bi-b-bq-not").value, set: el("bi-b-bq-set").value});
    el("bi-b-bq-q").value = ""; el("bi-b-bq-must").value = ""; el("bi-b-bq-not").value = "";
  } catch (failure) { biNotice(false, "沒有加入：" + failure.message); }
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
        {dataset: bi.questionsAi.dataset, turn: index, picks});
      bi.questionsAi.session = reply.session;
      biBuildSessionLog("bi-b-qa-log", reply.session, biQuestionsSuggestion);
      await biBench(bi.verVault);
      biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
      biNotice(true, "已加入 " + reply.units.length
        + " 題測試題；commit 並 push 後才會跟著知識庫。");
    }, "go", "把勾選的題目加入測試題")));
  }
  return parts;
}

async function biQuestionsAi() {
  const dataset = "vault-" + bi.verVault;
  const target = el("bi-b-bq-set").value.trim() || "main";
  bi.questionsAi = {dataset, target, session: null};
  el("bi-b-qa").hidden = false;
  el("bi-b-qa-target").textContent = "題組「" + target + "」。Agent 會自己查卡片與分析、"
    + "必要時試問，再提出題目與評分用的詞；你勾選並按「加入測試題」才會加入。";
  const found = await call("/api/bi/sessions?dataset=" + encodeURIComponent(dataset)
    + "&target=" + encodeURIComponent("questions:" + target));
  bi.questionsAi.session = (found.sessions || [])[0] || null;
  biBuildSessionLog("bi-b-qa-log", bi.questionsAi.session, biQuestionsSuggestion);
  el("bi-b-qa-msg").focus();
}

el("bi-b-qa-open").addEventListener("click", () => biQuestionsAi()
  .catch((failure) => biNotice(false, failure.message)));
el("bi-b-qa-close").addEventListener("click", () => {
  el("bi-b-qa").hidden = true; bi.questionsAi = null;
});
el("bi-b-qa-send").addEventListener("click", async () => {
  const chosen = bi.questionsAi; if (!chosen) return;
  const message = el("bi-b-qa-msg").value.trim();
  if (!message) { el("bi-b-qa-msg").focus(); return; }
  const button = el("bi-b-qa-send"); button.disabled = true;
  biStatus("bi-b-qa-status", "loading", "Agent 正在查卡片與分析、試問題目…（可能要幾分鐘）");
  try {
    if (!chosen.session) {
      chosen.session = (await biCall("/api/bi/sessions", {dataset: chosen.dataset,
        kind: "questions", target: chosen.target})).session;
    }
    const reply = await biCall("/api/bi/sessions/" + chosen.session.id + "/turns",
      {dataset: chosen.dataset, message});
    chosen.session = reply.session; el("bi-b-qa-msg").value = "";
    biBuildSessionLog("bi-b-qa-log", reply.session, biQuestionsSuggestion);
    biStatus("bi-b-qa-status", "");
  } catch (failure) {
    biStatus("bi-b-qa-status", "error", "沒有送出：" + failure.message + "。");
  } finally { button.disabled = false; }
});

el("bi-b-bench-run").addEventListener("click", async () => {
  const button = el("bi-b-bench-run"); button.disabled = true;
  try {
    const reply = await biCall("/api/bi/vaults/" + bi.verVault + "/bench", {});
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

async function biSaveDashboard(vaultId, layout) {
  await biCall("/api/bi/vaults/" + vaultId + "/analyses", {dashboard: layout});
  biVaultState(await call("/api/bi/vaults/" + vaultId + "/status"));
  await biAnalyses(vaultId);
  biNotice(true, "已改 Dashboard 的順序（commit 並 push 後大家才會看到）。");
}

async function biAnalyses(vaultId) {
  const reply = await call("/api/bi/vaults/" + vaultId + "/analyses");
  if (vaultId !== bi.verVault) return;
  if (bi.loaded) bi.loaded.dashboard = false;  // its 「分析」 card is drawn again when opened
  el("bi-b-an").hidden = false;
  const box = el("bi-b-an-list"); box.replaceChildren();
  if (!reply.analyses.length) box.append(bh("p", "bi-meta", "還沒有存起來的分析。"));
  // Shown in the Dashboard's order, then hidden and not offered ones.
  const rank = (a) => { const i = reply.order.indexOf(a.slug); return i < 0 ? 1e6 : i; };
  const items = [...reply.analyses].sort((a, b) => rank(a) - rank(b));
  const hidden = new Set(reply.dashboard.hidden || []);
  const move = (slug, step) => {
    const order = [...reply.order], at = order.indexOf(slug);
    if (at < 0 || at + step < 0 || at + step >= order.length) return null;
    [order[at], order[at + step]] = [order[at + step], order[at]];
    return biSaveDashboard(vaultId, {order, hidden: [...hidden]});
  };
  for (const item of items) {
    const state = biAnState(vaultId, item.slug), out = biAnOut("list", item, state);
    const where = !item.offered ? "schema 沒有它需要的類型或欄位，Dashboard 不顯示"
      : hidden.has(item.slug) ? "Dashboard 不顯示" : "Dashboard 第 " + (rank(item) + 1) + " 個";
    const shown = hidden.has(item.slug)
      ? biButton("在 Dashboard 顯示", () => biSaveDashboard(vaultId, {order: reply.order,
        hidden: [...hidden].filter((s) => s !== item.slug)}), "bi-btn",
        "在 Dashboard 顯示分析 " + item.title)
      : biButton("在 Dashboard 隱藏", () => biSaveDashboard(vaultId, {order: reply.order,
        hidden: [...hidden, item.slug]}), "bi-btn", "在 Dashboard 隱藏分析 " + item.title);
    box.append(bh("div", "bi-step", bh("strong", "", item.title),
      bh("p", "bi-meta", (item.question ? item.question + "・" : "")
        + (item.kind === "sql" ? "SQL" : "Python 腳本") + "・" + item.chart.type + "・" + where),
      biParamInputs(item, state.values, () => biRunInto(vaultId, item, state, out)
        .catch((failure) => biNotice(false, failure.message))),
      bh("div", "bi-actions",
        biButton("執行", () => biRunInto(vaultId, item, state, out), "bi-btn",
          "執行分析 " + item.title),
        biButton("和 AI 一起修改", () => biAnalysisAi(item.slug, item.title), "bi-btn",
          "和 AI 一起修改分析 " + item.title),
        reply.order.includes(item.slug) ? biButton("上移", () => move(item.slug, -1), "bi-btn",
          "在 Dashboard 上移分析 " + item.title) : null,
        reply.order.includes(item.slug) ? biButton("下移", () => move(item.slug, 1), "bi-btn",
          "在 Dashboard 下移分析 " + item.title) : null,
        item.offered ? shown : null,
        biButton("刪除", async () => {
          await biCall("/api/bi/vaults/" + vaultId + "/analyses", {delete: item.unit});
          biVaultState(await call("/api/bi/vaults/" + vaultId + "/status"));
          biNotice(true, "已刪除分析（commit 並 push 後大家才會少這個分析）。");
        }, "bi-btn", "刪除分析 " + item.title)), out));
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
        {dataset: bi.analysisAi.dataset, turn: index});
      bi.analysisAi.session = reply.session;
      biBuildSessionLog("bi-b-ana-log", reply.session, biAnalysisSuggestion);
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
      {dataset: bi.analysisAi.dataset, turn: index});
    bi.analysisAi.session = reply.session;
    biBuildSessionLog("bi-b-ana-log", reply.session, biAnalysisSuggestion);
    biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
    biNotice(true, "已套用 Dashboard：" + d.analyses.length + " 個分析與順序；"
      + "commit 並 push 後大家才會看到。");
  }, "go", "把這些分析與 Dashboard 順序存進知識庫")));
  return parts;
}

async function biAnalysisAi(slug, title) {
  const dataset = "vault-" + bi.verVault, target = slug || "new";
  bi.analysisAi = {dataset, target, session: null};
  el("bi-b-ana").hidden = false;
  el("bi-b-ana-target").textContent = slug ? "修改分析「" + title + "」。"
    : "新的分析：說出你想確認的關係或現象。Agent 會自己查資料、寫 SQL 或腳本，再畫給你看。";
  const found = await call("/api/bi/sessions?dataset=" + encodeURIComponent(dataset)
    + "&target=" + encodeURIComponent("analysis:" + target));
  bi.analysisAi.session = (found.sessions || [])[0] || null;
  biBuildSessionLog("bi-b-ana-log", bi.analysisAi.session, biAnalysisSuggestion);
  el("bi-b-ana-msg").focus();
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
el("bi-b-ana-close").addEventListener("click", () => {
  el("bi-b-ana").hidden = true; bi.analysisAi = null;
});
el("bi-b-ana-send").addEventListener("click", async () => {
  const chosen = bi.analysisAi; if (!chosen) return;
  const message = el("bi-b-ana-msg").value.trim();
  if (!message) { el("bi-b-ana-msg").focus(); return; }
  const button = el("bi-b-ana-send"); button.disabled = true;
  biStatus("bi-b-ana-status", "loading", "Agent 正在查資料、畫圖…（可能要一兩分鐘）");
  try {
    if (!chosen.session) {
      chosen.session = (await biCall("/api/bi/sessions", {dataset: chosen.dataset,
        kind: "analysis", target: chosen.target})).session;
    }
    const reply = await biCall("/api/bi/sessions/" + chosen.session.id + "/turns",
      {dataset: chosen.dataset, message});
    chosen.session = reply.session; el("bi-b-ana-msg").value = "";
    biBuildSessionLog("bi-b-ana-log", reply.session, biAnalysisSuggestion);
    biStatus("bi-b-ana-status", "");
  } catch (failure) {
    biStatus("bi-b-ana-status", "error", "沒有送出：" + failure.message + "。");
  } finally { button.disabled = false; }
});

// -- the 「版本」 area (knowledge repositories R5, KNOWLEDGE_REPO.md §10) ----------
function biVerValue(value) {
  if (value === null || value === undefined) return "（沒有）";
  if (typeof value === "object" && !Array.isArray(value) && "value" in value) value = value.value;
  if (value === null || value === undefined || value === "") return "（空）";
  const shown = typeof value === "string" ? value : JSON.stringify(value);
  return shown.length > 200 ? shown.slice(0, 200) + "…" : shown;
}

function biVerChanges(changes) {
  const list = bh("ul", "bi-log");
  for (const change of changes.slice(0, 50)) {
    list.append(bh("li", "", bh("strong", "", change.label || change.unit), "：",
      biVerValue(change.before), " → ", biVerValue(change.after)));
  }
  if (changes.length > 50) {
    list.append(bh("li", "bi-meta", "還有 " + (changes.length - 50) + " 項"));
  }
  return list;
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

async function biVerRun(vaultId, action, body, done) {
  const reply = await biCall("/api/bi/vaults/" + vaultId + "/" + action, body || {});
  if (done) biNotice(true, done);
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
    box.append(bh("p", "", "還沒 commit 的改動 " + changes.length + " 項："),
      biVerChanges(changes));
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
  biSkills(vaultId).catch((failure) => biNotice(false, "讀不到判讀規則：" + failure.message));
  biProfiles(vaultId).catch((failure) => biNotice(false, "讀不到 profile：" + failure.message));
}

function biVerHistory(vaultId, history) {
  const box = el("bi-b-ver-history"); box.replaceChildren();
  const tags = history.tags || [], published = history.published;
  const byCommit = {};
  for (const tag of tags) (byCommit[tag.commit] = byCommit[tag.commit] || []).push(tag);
  const live = (tag) => Boolean(published && published.tag === tag.name);
  const list = bh("ul", "bi-log");
  (history.commits || []).forEach((commit, index) => {
    const row = bh("li", "");
    const badges = (byCommit[commit.id] || []).map((tag) =>
      biBadge("tag " + tag.name + (live(tag) ? "・發佈中" : ""), live(tag) ? "good" : ""));
    row.append(bh("div", "", bh("strong", "", commit.purpose), " ", ...badges),
      bh("div", "bi-meta", biTime(commit.created) + "・" + commit.author + "・" + commit.units
        + " 項" + (commit.kind === "revert" ? "・回復版本" : "") + "・" + commit.id.slice(0, 10)));
    const actions = bh("div", "bi-actions"), detail = bh("div", "");
    actions.append(biButton("看改動", async () => {
      if (detail.childNodes.length) { detail.replaceChildren(); return; }
      const reply = await call("/api/bi/vaults/" + vaultId + "/diff?commit="
        + encodeURIComponent(commit.id));
      detail.replaceChildren(biVerChanges(reply.changes || []));
    }, "bi-btn", "看「" + commit.purpose + "」的改動"));
    if (index > 0) {
      actions.append(biButton("回到這個版本", () => biVerAsk(row, "回復的目的",
        "回到「" + commit.purpose + "」的版本", "回復（成為新的 commit）", (purpose) =>
          biVerRun(vaultId, "revert", {version: commit.id, purpose},
            "已回復成新的 commit；按「Push 給大家」送出。")),
      "bi-btn", "回到「" + commit.purpose + "」的版本"));
    }
    actions.append(biButton("加 tag", () => biVerAsk(row,
      "tag 名稱（小寫英數字與 . -，例如 2026q4）", "", "建立 tag", (name) =>
        biVerRun(vaultId, "tag", {name, version: commit.id, purpose: commit.purpose},
          "已建立 tag「" + name + "」；要讓 Agent 讀它，請按「發佈 " + name + "」。")),
    "bi-btn", "幫「" + commit.purpose + "」加 tag"));
    for (const tag of byCommit[commit.id] || []) {
      if (live(tag)) continue;
      actions.append(biButton("發佈 " + tag.name, async () => {
        if (!confirm("發佈 tag「" + tag.name + "」？發佈後 Agent 只讀這個版本的內容；"
          + "要撤回就再發佈另一個 tag。")) return;
        await biVerRun(vaultId, "publish", {tag: tag.name, confirm: true},
          "已發佈「" + tag.name + "」：Agent 現在讀這個版本。"
          + "資料夾裡的 cards/ 是給人看的唯讀頁，要改值請提更正單。");
      }, "bi-btn", "發佈 tag " + tag.name));
    }
    row.append(actions, detail); list.append(row);
  });
  if (!(history.commits || []).length) list.append(bh("li", "bi-meta", "還沒有 commit。"));
  box.append(list);
}

function biVerConflicts(vaultId, conflicts) {
  // Push conflicts side by side: nothing was written until each is decided.
  const box = el("bi-b-ver-conflicts"); box.replaceChildren();
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
  const box = el("bi-b-sk-list"); box.replaceChildren();
  const list = bh("ul", "bi-log");
  for (const item of reply.skills || []) {
    const where = (item.applies_to || []).length ? item.applies_to.join("、") : "所有來源";
    const badges = [biBadge(item.role === "classify" ? "分類" : "擷取", "dim"),
      biBadge("第 " + item.revision + " 版", "dim")];
    if (item.generated) badges.push(biBadge("依 schema 產生", "dim"));
    if (item.needs_update) badges.push(biBadge("需要更新", "warn"));
    const edit = bh("button", "bi-btn", "修改");
    edit.type = "button";
    edit.addEventListener("click", () => biSkillForm(item));
    const talk = biButton("和 AI 一起修改", () => biSkillAi(item), "bi-btn",
      "和 AI 一起修改判讀規則 " + item.name);
    const row = bh("li", "", bh("strong", "", item.name), " ", ...badges,
      bh("p", "bi-meta", "套用到：" + where + "・schema " + (item.schema || "")
        + (item.needs_update
          ? "（知識庫現在用 " + reply.schema + "；修改並儲存後才會再使用）" : "")),
      bh("div", "bi-actions", edit, talk));
    if (item.problem) row.append(bh("p", "bi-warn", item.problem));
    list.append(row);
  }
  if (!(reply.skills || []).length) box.append(bh("p", "bi-meta", "還沒有判讀規則。"));
  else box.append(list);
  const pick = el("bi-b-folder"), kept = pick.value;
  pick.replaceChildren(...(reply.folders || ["sources"]).map((f) => {
    const option = bh("option", "", f === "sources" ? "（不指定資料夾）" : f);
    option.value = f; return option;
  }));
  if ((reply.folders || []).includes(kept)) pick.value = kept;
  const chosen = (bi.build.sources || []).find((s) => s.id === bi.build.sourceId);
  if (chosen && chosen.folder && (reply.folders || []).includes(chosen.folder)) {
    pick.value = chosen.folder;
  }
  el("bi-b-folder-box").hidden = false;
  biRerunForm(reply.folders || []);
}

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
  el("bi-b-sk-name").value = item ? item.name : "";
  el("bi-b-sk-name").readOnly = Boolean(item);
  el("bi-b-sk-role").value = item ? item.role : "extract";
  el("bi-b-sk-applies").value = item ? (item.applies_to || []).join(", ") : "";
  el("bi-b-sk-types").value = item ? (item.card_types || []).join(", ") : "";
  el("bi-b-sk-body").value = item ? item.body || "" : "";
  el("bi-b-sk-folders").textContent = "可用的資料夾：" + ((bi.skills && bi.skills.folders) || [])
    .filter((f) => f !== "sources").join("、");
  el("bi-b-sk-body").focus();
}

const biList = (text) => text.split(/[,，、\n]/).map((s) => s.trim()).filter(Boolean);

el("bi-b-sk-new").addEventListener("click", () => biSkillForm(null));
el("bi-b-rr-count").addEventListener("click", biRerunCount);

// Session B on a vault skill (knowledge repositories R3): the AI suggests a new
// text; 「套用」 stages the next revision, which is committed and pushed in 「版本」.
async function biSkillAi(item) {
  const dataset = "vault-" + bi.verVault;
  bi.skillAi = {name: item.name, dataset, session: null};
  el("bi-b-ska").hidden = false;
  el("bi-b-ska-target").textContent = "對話的對象：判讀規則「" + item.name + "」第 "
    + item.revision + " 版" + (item.needs_update ? "（需要更新：寫給 " + item.schema
      + "，AI 會一起把它更新到知識庫現在的 schema）" : "") + "。";
  await biBuildAiState("bi-b-ska-model",
    "這條規則、知識庫的卡片類型與資料夾、最近兩次試跑的候選卡", true);
  const found = await call("/api/bi/sessions?dataset=" + encodeURIComponent(dataset)
    + "&target=" + encodeURIComponent("skill:" + item.name));
  bi.skillAi.session = (found.sessions || [])[0] || null;
  biBuildSessionLog("bi-b-ska-log", bi.skillAi.session, biApplySkill);
  el("bi-b-ska-msg").focus();
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
        {dataset: bi.skillAi.dataset, turn: index});
      bi.skillAi.session = reply.session;
      el("bi-b-ska-target").textContent = "對話的對象：判讀規則「" + bi.skillAi.name
        + "」第 " + reply.skill.revision + " 版（剛套用，還沒 commit）。";
      biBuildSessionLog("bi-b-ska-log", reply.session, biApplySkill);
      biVaultState(await call("/api/bi/vaults/" + bi.verVault + "/status"));
      biNotice(true, "判讀規則「" + bi.skillAi.name + "」存成第 " + reply.skill.revision
        + " 版；commit 並 push 後大家才會用到。");
    }, "go", "把這個建議套用為判讀規則的新版本")));
  }
  return parts;
}

el("bi-b-ska-close").addEventListener("click", () => {
  el("bi-b-ska").hidden = true; bi.skillAi = null;
});
el("bi-b-ska-send").addEventListener("click", async () => {
  const chosen = bi.skillAi; if (!chosen) return;
  const message = el("bi-b-ska-msg").value.trim();
  if (!message) { el("bi-b-ska-msg").focus(); return; }
  const button = el("bi-b-ska-send"); button.disabled = true;
  biStatus("bi-b-ska-status", "loading",
    "Agent 正在讀來源、用草稿試跑、看測試結果…（可能要幾分鐘）");
  try {
    if (!bi.build.ai || !bi.build.ai.available) {
      biStatus("bi-b-ska-status", "error", "沒有可用的模型："
        + ((bi.build.ai && bi.build.ai.message) || "") + "。");
      return;
    }
    if (!chosen.session) {
      chosen.session = (await biCall("/api/bi/sessions", {dataset: chosen.dataset,
        kind: "skill", target: chosen.name})).session;
    }
    const reply = await biCall("/api/bi/sessions/" + chosen.session.id + "/turns",
      {dataset: chosen.dataset, message,
        source_ids: bi.build.sourceId && biDataset() === chosen.dataset
          ? [bi.build.sourceId] : []});
    chosen.session = reply.session; el("bi-b-ska-msg").value = "";
    biBuildSessionLog("bi-b-ska-log", reply.session, biApplySkill);
    biStatus("bi-b-ska-status", "");
  } catch (failure) {
    biStatus("bi-b-ska-status", "error", (failure.code === "model_unavailable"
      ? "沒有可用的模型：" : "沒有送出：") + failure.message + "。");
  } finally { button.disabled = false; }
});
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
el("bi-b-ver-discard").addEventListener("click", async () => {
  if (!confirm("捨棄這台電腦上還沒 commit 的改動？已 commit 的不受影響。")) return;
  try { await biVerRun(bi.verVault, "discard", {}, "已捨棄還沒 commit 的改動。"); }
  catch (failure) { biNotice(false, "沒有捨棄：" + failure.message); }
});

el("bi-b-ds").addEventListener("change", () => {
  const select = el("bi-dataset");
  select.value = el("bi-b-ds").value; select.dispatchEvent(new Event("change"));
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
  if ((bi.schema || {}).ref) schema.value = bi.schema.ref;
  el(mode === "new" ? "bi-b-v-title" : "bi-b-v-path").focus();
}

for (const id of ["bi-b-v-new", "bi-b-v-join", "bi-b-v-convert"]) {
  el(id).addEventListener("click", () => biVaultForm(el(id).dataset.mode));
}
el("bi-b-v-cancel").addEventListener("click", () => biVaultForm(el("bi-b-v-form").dataset.mode));
el("bi-b-v-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const mode = el("bi-b-v-form").dataset.mode, err = el("bi-b-v-err"); err.replaceChildren();
  const body = {path: el("bi-b-v-path").value.trim(), author: el("bi-b-v-author").value.trim()};
  if (!body.path) { err.append(bh("p", "bi-err", "請填資料夾路徑。")); return; }
  if (mode === "new") {
    Object.assign(body, {title: el("bi-b-v-title").value.trim(),
      purpose: el("bi-b-v-purpose").value.trim(), schema: el("bi-b-v-schema").value});
    if (!body.title) { err.append(bh("p", "bi-err", "請填知識庫名稱。")); return; }
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
    bi.want = reply.vault.dataset; await biLoad();
  } catch (failure) {
    err.append(bh("p", "bi-err", failure.message + "。"));
  } finally { button.disabled = false; }
});

// -- step 1: sources ---------------------------------------------------------
const BI_SHARED = {local: "只在這台電腦", staged: "commit、push 後才會放上去",
  pushed: "已放上去", cloud_only: "只在雲端"};

async function biSourceFolders() {
  // A vault's source folders, for the folder a new source goes in.
  const vault = biVaultOf(biDataset());
  el("bi-b-src-folder-box").hidden = !vault; el("bi-b-src-shared").hidden = !vault;
  if (!vault) return;
  const reply = await call("/api/bi/vaults/" + vault.id + "/skills");
  const pick = el("bi-b-src-folder"), kept = pick.value;
  pick.replaceChildren(...(reply.folders || ["sources"]).map((f) => {
    const option = bh("option", "", f === "sources" ? "（不指定資料夾）" : f);
    option.value = f; return option;
  }));
  if ((reply.folders || []).includes(kept)) pick.value = kept;
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
  box.replaceChildren(bh("h4", "", "撤回「" + source.name + "」"),
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

async function biBuildSources() {
  // Newest call only: an older list arriving late must not drop the source just added.
  const seq = bi.sourcesSeq = (bi.sourcesSeq || 0) + 1;
  const reply = await call("/api/bi/sources?dataset=" + encodeURIComponent(biDataset()));
  await biSourceFolders().catch(() => {});
  if (seq !== bi.sourcesSeq) return;
  bi.build.sources = reply.sources || [];
  const cloud = bi.build.sources.filter((s) => s.shared === "cloud_only").length;
  const waiting = (reply.waiting || []).length;
  const warn = el("bi-b-src-cloud");
  warn.hidden = !cloud && !waiting;
  warn.textContent = (cloud
    ? cloud + " 個來源只在雲端：請把共用資料夾設為「一律保留在此裝置上」。" : "")
    + (waiting ? waiting + " 個檔案還在等 OneDrive 同步，同步好才看得到。" : "");
  if (!bi.build.sources.some((s) => s.id === bi.build.sourceId)) bi.build.sourceId = null;
  const body = el("bi-b-sources").tBodies[0]; body.replaceChildren();
  for (const source of bi.build.sources) {
    const radio = document.createElement("input");
    radio.type = "radio"; radio.name = "bi-b-source"; radio.value = source.id;
    radio.checked = source.id === bi.build.sourceId;
    radio.setAttribute("aria-label", "使用 " + source.name);
    radio.disabled = !source.format;
    radio.addEventListener("change", () => {
      bi.build.sourceId = source.id; el("bi-b-next1").disabled = false; biBuildSave();
      biBuildSteps();
    });
    const format = {table: "表格（預設表格規則）", document: "文件（預設 AI 擷取）",
      text: "文字（預設 AI 擷取）"};
    const md = source.convert_error
      ? bh("span", "bi-err", "轉檔失敗：" + source.convert_error.message)
      : source.markdown_rev ? "第 " + source.markdown_rev + " 版" : "尚未轉檔";
    body.append(bh("tr", "", bh("td", "", radio), bh("td", "", source.name),
      bh("td", "", format[source.format] || "尚未支援"),
      bh("td", "", md, " ", source.format
        ? biButton("看／改", () => biBuildMarkdown(source.id), "bi-btn", "看或修改 "
          + source.name + " 的 Markdown") : ""),
      bh("td", "", Math.max(1, Math.round(source.size / 1024)) + " KB"),
      bh("td", "", source.classification), bh("td", "", biSharedCell(source)),
      bh("td", "", biTime(source.at))));
  }
  if (!bi.build.sources.length) {
    body.append(bh("tr", "", bh("td", "bi-empty", "還沒有來源。先選檔案，按「加入來源」。")));
  }
  el("bi-b-next1").disabled = !bi.build.sourceId;
  biBuildSteps();
}

// -- step 1: a source's Markdown (BI vaults V2, BI_VAULT.md §5) ----------------
// Every source is read through its current Markdown revision; an edit saves a
// new revision from the one shown (409 markdown_stale when someone saved first).
async function biBuildMarkdown(sourceId, rev) {
  const box = el("bi-b-md"), msg = el("bi-b-md-msg");
  msg.replaceChildren();
  const path = "/api/bi/sources/" + encodeURIComponent(sourceId) + "/markdown"
    + (rev ? "/" + rev : "") + "?dataset=" + encodeURIComponent(biDataset());
  let view;
  try { view = await call(path); }
  catch (failure) { biNotice(false, "Markdown 沒有載入：" + failure.message); return; }
  bi.build.md = view; box.hidden = false;
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
  const old = Boolean(view.current_rev) && r.rev !== view.current_rev;
  el("bi-b-md-save").disabled = old;
  if (old) msg.append(bh("p", "bi-meta", "這是舊版次，只能看；要改請先選目前的版次。"));
}

el("bi-b-md-rev").addEventListener("change", () => {
  if (bi.build.md) biBuildMarkdown(bi.build.md.source.id, el("bi-b-md-rev").value);
});
el("bi-b-md-close").addEventListener("click", () => { el("bi-b-md").hidden = true; });
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

el("bi-b-file").addEventListener("change", () => {
  el("bi-b-upload").disabled = !el("bi-b-file").files.length;
});
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
      samples: el("bi-b-pages-samples").checked}));
  } catch (failure) { biNotice(false, "沒有預覽：" + failure.message); }
});

// A large file goes as the raw request body, read by the browser as it is sent;
// base64 inside JSON cannot carry it (BI_SOURCES_IN_REPOSITORY S6).
const BI_STREAM_FROM = 4 * 1024 * 1024;

async function biUploadFile(file) {
  const query = new URLSearchParams({dataset: biDataset(), name: file.name,
    classification: el("bi-b-class").value});
  if (biVaultOf(biDataset())) query.set("folder", el("bi-b-src-folder").value);
  const reply = await fetch("/api/bi/sources/upload?" + query.toString(),
    {method: "POST", headers: {"Authorization": "Bearer " + TOKEN}, body: file});
  const answer = await reply.json().catch(() => ({}));
  if (!reply.ok || answer.ok === false) {
    throw new Error(answer.message || answer.code || ("主機回應 " + reply.status));
  }
  return answer;
}

el("bi-b-upload").addEventListener("click", async () => {
  const button = el("bi-b-upload"); button.disabled = true;
  biStatus("bi-status-build", "loading", "正在加入來源…");
  try {
    for (const file of el("bi-b-file").files) {
      if (file.size > BI_STREAM_FROM) {
        bi.build.sourceId = (await biUploadFile(file)).source.id;
        continue;
      }
      const binary = /\.(xlsx|xlsm|pdf|docx|pptx)$/i.test(file.name);
      const content = await biReadFile(file, binary);
      const body = {dataset: biDataset(), name: file.name,
        classification: el("bi-b-class").value};
      if (biVaultOf(biDataset())) body.folder = el("bi-b-src-folder").value;
      if (binary) body.content_base64 = content; else body.text = content;
      const reply = await biCall("/api/bi/sources", body);
      bi.build.sourceId = reply.source.id;
    }
    el("bi-b-file").value = "";
    await biBuildSources(); biBuildSave();
    biStatus("bi-status-build", "");
  } catch (failure) {
    biStatus("bi-status-build", "error", "來源沒有加入：" + failure.message + "。");
  } finally { button.disabled = !el("bi-b-file").files.length; }
});

// -- step 2: schema ----------------------------------------------------------
async function biBuildSchema() {
  const schema = bi.schema || {};
  const id = schema.schema_id, ref = schema.ref || "";
  el("bi-b-schema-now").textContent = "這個資料集目前使用 " + (ref || id || "—") + "（"
    + (schema.title || "") + "），" + (schema.types || []).length + " 種卡片。";
  const others = bi.schemas.filter((item) => item.id === id && item.ref !== ref);
  const box = el("bi-b-versions"); box.replaceChildren();
  if (others.length) {
    box.append(bh("p", "bi-meta", "同一個 schema 的其他版本："));
    for (const item of others) {
      box.append(bh("div", "bi-actions", bh("span", "", item.ref),
        biButton("預覽升級", () => biBuildUpgradePreview(item.ref), "bi-btn",
          "預覽把資料集移到 " + item.ref)));
    }
  } else {
    box.append(bh("p", "bi-meta", "沒有同一個 schema 的其他版本。"));
  }
  await biBuildDrafts();
  await biBuildSessA(false);
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
  const parts = [bh("h4", "", "升級 " + preview.from + " → " + preview.to)];
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
      await biCall("/api/bi/datasets/" + encodeURIComponent(biDataset()) + "/schema/apply",
        {to: preview.to, preview_token: preview.preview_token});
      biNotice(true, "資料集已升級到 " + preview.to + "。");
      box.hidden = true; await biLoad();
    }, "go")));
  }
  box.append(...parts);
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
}

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
  biDraftInfo(view);
  if (other) el("bi-b-draft-trial-result").replaceChildren();
  biBuildSessA(other).catch((failure) => biNotice(false, "對話沒有載入：" + failure.message));
}

// -- step 2: Session A, designing the draft by conversation (BI ingest phase 6) --
// The model suggests operations; code applies them to a copy and shows the diff
// and errors. Only 「套用到草稿」 writes a revision; 「用樣本試跑」 tries the draft
// revision on a source without installing it. The conversation is always shown
// (owner, 2026-10-28): without an open draft, the first message makes one from
// the dataset's current version.
async function biBuildSessA(reload) {
  const draft = bi.build.draft;
  el("bi-b-sa-target").textContent = draft
    ? "對話的建議會套用到草稿「" + draft.draft.title + "」（第 " + draft.revision + " 版）。"
    : "還沒有開啟草稿：送出第一句話時，會從目前版本 " + ((bi.schema || {}).ref || "")
      + " 建立一份草稿；資料集在你發布並升級前都不會改變。";
  const box = el("bi-b-sa-sources");
  const kept = new Set([...box.querySelectorAll("input:checked")].map((i) => i.value));
  if (!kept.size && bi.build.sourceId) kept.add(bi.build.sourceId);
  box.replaceChildren(bh("legend", "bi-label", "附上的樣本來源（最多 5 份，合計上限 12000 字）"));
  for (const source of bi.build.sources.filter((s) => s.parse !== "unsupported")) {
    const check = document.createElement("input");
    check.type = "checkbox"; check.value = source.id; check.checked = kept.has(source.id);
    box.append(bh("label", "", check, source.name + "（" + source.classification + "）"));
  }
  if (!bi.build.sources.length) box.append(bh("p", "bi-meta", "還沒有來源；只送草稿與目標。"));
  await biBuildAiState("bi-b-sa-model", "草稿目前的類型與欄位、你的目標", "schema");
  if (!draft) {
    bi.build.sessA = null;
  } else if (reload || !bi.build.sessA || bi.build.sessA.target_ref !== "schema-draft:"
    + draft.draft.id) {
    const found = await call("/api/bi/sessions?dataset=" + encodeURIComponent(biDataset())
      + "&target=" + encodeURIComponent("schema-draft:" + draft.draft.id));
    bi.build.sessA = (found.sessions || [])[0] || null;
    el("bi-b-sa-goal").value = bi.build.sessA ? bi.build.sessA.goal || "" : "";
  }
  biBuildSessionLog("bi-b-sa-log", bi.build.sessA, biBuildApplySchema);
}

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

el("bi-b-sa-send").addEventListener("click", async () => {
  const message = el("bi-b-sa-msg").value.trim();
  if (!message) { el("bi-b-sa-msg").focus(); return; }
  const button = el("bi-b-sa-send"); button.disabled = true;
  biStatus("bi-b-sa-status", "loading", "Agent 正在看來源與卡片、試草稿…（可能要幾分鐘）");
  try {
    // Without a model nothing is made: no draft is created for a message that cannot be sent.
    await biBuildAiState("bi-b-sa-model", "草稿目前的類型與欄位、你的目標", "schema");
    if (!bi.build.ai.available) {
      biStatus("bi-b-sa-status", "error", "沒有可用的模型：" + bi.build.ai.message + "。");
      return;
    }
    if (!bi.build.draft) {
      const made = await biCall("/api/bi/schema-drafts", {base: (bi.schema || {}).ref});
      biBuildShowDraft(made); await biBuildDrafts();
    }
    const draft = bi.build.draft;
    let session = bi.build.sessA;
    if (!session) {
      session = (await biCall("/api/bi/sessions", {dataset: biDataset(), kind: "schema",
        target: draft.draft.id})).session;
    }
    const sources = [...el("bi-b-sa-sources").querySelectorAll("input:checked")]
      .map((i) => i.value).slice(0, 5);
    const reply = await biCall("/api/bi/sessions/" + session.id + "/turns",
      {dataset: biDataset(), message, goal: el("bi-b-sa-goal").value, source_ids: sources});
    bi.build.sessA = reply.session; el("bi-b-sa-msg").value = "";
    biBuildSessionLog("bi-b-sa-log", reply.session, biBuildApplySchema);
    biStatus("bi-b-sa-status", "");
  } catch (failure) {
    biStatus("bi-b-sa-status", "error", (failure.code === "model_unavailable"
      ? "沒有可用的模型：" : "沒有送出：") + failure.message + "。");
  } finally { button.disabled = false; }
});

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
    biNotice(true, "已發布 " + reply.ref + "。要讓資料集使用它，請按「預覽升級」。");
    const schemas = await call("/api/bi/schemas"); bi.schemas = schemas.schemas || [];
    await biBuildSchema();
  } catch (failure) {
    const errors = (failure.payload && failure.payload.errors) || [];
    biNotice(false, "沒有發布：" + failure.message + (errors.length ? "（"
      + errors.map((e) => e.path + "：" + e.message).join("；") + "）" : ""));
  }
});

// -- steps 3-4: runs ---------------------------------------------------------
function biRunBody(kind) {
  const body = {dataset: biDataset(), kind, source_id: bi.build.sourceId,
    entity_type: el("bi-b-entity").value || null};
  const methodId = el("bi-b-m-pick").value;
  if (methodId && !methodId.startsWith("builtin:")) { body.method_id = methodId; return body; }
  // 「AI 擷取」 on a table sends its Markdown to the model (owner 2026-10-28);
  // 「表格規則」 reads the tables without a model.
  const source = bi.build.sources.find((s) => s.id === bi.build.sourceId);
  if (methodId === "builtin:llm" && source && source.format === "table") body.path = "ai";
  if (methodId === "builtin:rules") body.path = "rules";
  if (biDataset().startsWith("vault-") && el("bi-b-folder").value) {
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
    biBadge("錯誤 " + (s.errors || 0), s.errors ? "bad" : "dim"),
    biBadge("警告 " + (s.warnings || 0), s.warnings ? "warn" : "dim"),
    biBadge("已接受 " + (s.accepted || 0), "good")];
}

// An AI run reads its source in the background: follow it until it ends.
async function biBuildFollow(runId) {
  for (;;) {
    const detail = await call("/api/bi/runs/" + runId + "?dataset="
      + encodeURIComponent(biDataset()));
    if (detail.run.status !== "extracting") { biStatus("bi-status-build", ""); return detail; }
    const p = detail.run.progress || {};
    biStatus("bi-status-build", "loading", "AI 判讀中…（第 " + (p.done || 0) + "／"
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
  try {
    await Promise.all([biBuildMethods(), biBuildTrials(), biBuildAiState("bi-b-sb-model",
      "Skill、最近兩次試跑的候選卡")]);
  } catch (failure) { biNotice(false, "擷取 Skill 沒有載入：" + failure.message); }
}

async function biBuildAiState(target, extra, harness) {
  const state = await call("/api/bi/ai?dataset=" + encodeURIComponent(biDataset()));
  bi.build.ai = state;
  const line = el(target); line.replaceChildren(); line.className = "bi-meta";
  if (!state.available) {
    line.className = "bi-warn";
    line.append("目前沒有可用的模型（model_unavailable）：" + state.message + "。");
    return;
  }
  if (harness === "schema") {
    // Session A on the Agent's harness (docs/phases/BI_BUILD_FLOW.md §5).
    line.append("由 Agent（和對話同一套 harness）處理：它會自己讀來源、看卡片、在草稿的副本上試改動"
      + "（看差異、驗證錯誤、對既有卡片的影響，試跑用模型 " + state.model + "，不寫入卡片），"
      + "再提出建議。它不能改草稿、發布或升級；送出的資料：" + extra + "。");
    return;
  }
  if (harness) {
    // BI T2: the skill AI runs on the Agent's harness with tools.
    line.append("由 Agent（和對話同一套 harness）處理：它會自己讀來源、用草稿規則試跑"
      + "（試跑用模型 " + state.model + "，不寫入卡片）、比較試跑、跑擷取測試、查目前的卡片，"
      + "再提出建議。它不能存檔、commit 或 push；送出的資料：" + extra + "。");
    return;
  }
  const source = bi.build.sources.find((s) => s.id === bi.build.sourceId);
  line.append("模型：" + state.model + "。每次送出只呼叫一次模型（格式不對最多重試 3 次），"
    + "模型沒有任何工具，不能改動資料。送出的資料：" + extra
    + (source ? "，以及來源「" + source.name + "」（" + source.classification
      + "）的前段（上限 12000 字）" : "（尚未選來源，不附來源內容）") + "。");
}

async function biBuildMethods(fill) {
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

function biSessBTarget() {
  const line = el("bi-b-sb-target"), value = el("bi-b-m-pick").value;
  if (bi.build.method) {
    line.textContent = "對話的建議會套用到 Skill「" + bi.build.method.document.name + "」（第 "
      + bi.build.method.revision + " 版）。";
  } else if (value === "builtin:rules") {
    line.textContent = "內建「表格規則」自動對應表格欄位，沒有可讓 AI 調整的設定。要調整，"
      + "先在下方貼配方（多表格報告用），送出時會另存成你自己的 Skill；或改選「AI 擷取」。";
  } else {
    line.textContent = "目前是內建「AI 擷取」：送出第一句話時，會用下方的判讀規則"
      + "（空白就是預設規則）另存一份你自己的 Skill 再開始對話；內建 Skill 不會被改動。";
  }
}

function biBuildCloseMethod() {
  bi.build.method = null; el("bi-b-m-box").hidden = true; el("bi-b-m-save").hidden = true;
  bi.build.sessB = null;
  biBuildSessionLog("bi-b-sb-log", null, biBuildApplyMethod);
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
  biBuildSessionLog("bi-b-sb-log", bi.build.sessB, biBuildApplyMethod);
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
    log.append(bh("li", "bi-meta", "還沒有對話。寫下你想要的調整，AI 只會提出建議，"
      + "要你按「套用」才會改動。"));
    return;
  }
  turns.forEach((turn, index) => {
    if (turn.role === "user") {
      log.append(bh("li", "me", bh("strong", "", "你："), turn.text));
      return;
    }
    const item = bh("li", "", bh("p", "bi-meta", biSentLine(turn.sent || {})));
    if (turn.error) item.append(bh("p", "bi-err", turn.error.message));
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

el("bi-b-sb-send").addEventListener("click", async () => {
  const message = el("bi-b-sb-msg").value.trim();
  if (!message) { el("bi-b-sb-msg").focus(); return; }
  const button = el("bi-b-sb-send"); button.disabled = true;
  biStatus("bi-b-sb-status", "loading", "AI 正在看擷取 Skill 與樣本…（一次模型呼叫）");
  try {
    await biBuildAiState("bi-b-sb-model", "Skill、最近兩次試跑的候選卡");
    if (!bi.build.ai.available) {
      biStatus("bi-b-sb-status", "error", "沒有可用的模型：" + bi.build.ai.message + "。");
      return;
    }
    const method = bi.build.method || await biSessBCopy();
    let session = bi.build.sessB;
    if (!session) {
      session = (await biCall("/api/bi/sessions", {dataset: biDataset(), kind: "method",
        target: method.method.id})).session;
    }
    const reply = await biCall("/api/bi/sessions/" + session.id + "/turns",
      {dataset: biDataset(), message,
        source_ids: bi.build.sourceId ? [bi.build.sourceId] : []});
    bi.build.sessB = reply.session; el("bi-b-sb-msg").value = "";
    biBuildSessionLog("bi-b-sb-log", reply.session, biBuildApplyMethod);
    biStatus("bi-b-sb-status", "");
  } catch (failure) {
    biStatus("bi-b-sb-status", "error", (failure.code === "model_unavailable"
      ? "沒有可用的模型：" : "沒有送出：") + failure.message + "。");
  } finally { button.disabled = false; }
});

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
  const button = el("bi-b-start"); button.disabled = true;
  biStatus("bi-status-build", "loading", "正在產生候選卡…");
  try {
    const reply = await biCall("/api/bi/runs", biRunBody("ingest"));
    await biBuildFollow(reply.run.id);
    await biBuildFetchRun(reply.run.id); bi.build.candidateId = null;
    biStatus("bi-status-build", ""); biBuildSave(); biBuildRenderRun();
  } catch (failure) {
    biStatus("bi-status-build", "error", "沒有產生候選卡：" + failure.message + "。");
  } finally { button.disabled = false; }
});

function biBuildRenderRun() {
  const run = bi.build.run, list = el("bi-b-cands");
  list.replaceChildren(); el("bi-b-chips").replaceChildren();
  const open = run && run.kind === "ingest" && ["review", "partial"].includes(run.status);
  el("bi-b-accept-clean").disabled = !open;
  el("bi-b-next4").disabled = !biBuildAllowed().commit;
  biBuildSteps();
  if (!run || run.kind !== "ingest") {
    list.append(bh("li", "bi-empty", "按「開始正式匯入」產生候選卡。"));
    return;
  }
  el("bi-b-chips").append(biBadge("執行 " + run.id + "・" + run.status, "dim"),
    ...biRunChips(run));
  if ((run.failures || []).length) {
    el("bi-b-chips").append(bh("p", "bi-err", "有 " + run.failures.length + " 段沒有判讀成功（"
      + run.failures.map((f) => "第 " + f.line_start + "–" + f.line_end + " 行：" + f.message)
        .join("；") + "）。其他候選卡可以先審核。"), biButton("重試失敗的段落", async () => {
      await biCall("/api/bi/runs/" + run.id + "/retry", {dataset: biDataset()});
      await biBuildFollow(run.id); await biBuildFetchRun(run.id); biBuildRenderRun();
    }, "bi-btn"));
  }
  el("bi-b-chips").append(...biRunNothing(run), ...biRunRelations(run));
  for (const candidate of bi.build.candidates) {
    const decision = BI_DECISION[candidate.review] || [candidate.review, "dim"];
    const button = biButton("", () => biBuildShowCandidate(candidate.id), "bi-card-btn");
    button.replaceChildren(bh("strong", "", candidate.name || candidate.canonical_key
      || "（無名稱）"), bh("span", "bi-meta", " " + biTypeLabel(candidate.entity_type) + "・"
      + (BI_RUN_ACTION[candidate.action] || candidate.action)), " ",
      biBadge(decision[0], decision[1]),
      candidate.errors.length ? biBadge("錯誤 " + candidate.errors.length, "bad") : "",
      candidate.warnings.length ? biBadge("警告 " + candidate.warnings.length, "warn") : "");
    if (candidate.id === bi.build.candidateId) button.setAttribute("aria-current", "true");
    list.append(bh("li", "", button));
  }
  if (bi.build.candidateId) biBuildShowCandidate(bi.build.candidateId);
}

async function biBuildReview(candidateId, body) {
  const run = bi.build.run;
  const reply = await biCall("/api/bi/runs/" + run.id + "/candidates/" + candidateId,
    {dataset: biDataset(), ...body});
  const index = bi.build.candidates.findIndex((c) => c.id === candidateId);
  if (index >= 0) bi.build.candidates[index] = reply.candidate;
  bi.build.run = reply.run; biBuildSave(); biBuildRenderRun();
}

function biEvidence(item) {
  if (!item.evidence.length) return bh("span", "bi-meta", "—");
  return bh("span", "", ...item.evidence.map((e) => {
    const place = Object.entries(e.locator || {}).map(([k, v]) => k + " " + v).join("・");
    const stance = {refutes: "反駁", context_only: "僅背景"}[e.stance];
    return bh("span", "bi-meta", "「" + e.excerpt + "」（" + place + "）"
      + (stance ? "〔" + stance + "〕" : "") + " ");
  }));
}

function biBuildShowCandidate(candidateId) {
  const candidate = bi.build.candidates.find((c) => c.id === candidateId);
  const box = el("bi-b-cand"); box.replaceChildren();
  if (!candidate) return;
  bi.build.candidateId = candidateId;
  const open = bi.build.run && ["review", "partial"].includes(bi.build.run.status);
  const head = bh("h4", "", (candidate.name || candidate.canonical_key || "（無名稱）") + "・"
    + biTypeLabel(candidate.entity_type));
  const match = candidate.match === "existing" ? "對應到既有卡片（版本 "
    + candidate.base_version + "）" : candidate.match === "ambiguous" ? "有名稱相近的既有卡片"
    : "新卡片";
  const parts = [head, bh("p", "bi-meta", match + "・" + (BI_RUN_ACTION[candidate.action]
    || candidate.action))];
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
  if (open && candidate.match === "ambiguous") {
    parts.push(bh("div", "bi-actions", biButton("新建", () => biBuildReview(candidate.id,
      {match: {action: "create"}}), "bi-btn"), ...candidate.match_ids.map((id) =>
      biButton("合併到既有卡片 " + id, () => biBuildReview(candidate.id,
        {match: {action: "update", card_id: id}}), "bi-btn")),
      biButton("略過", () => biBuildReview(candidate.id, {match: {action: "skip"}}), "bi-btn")));
  }
  const table = bh("table", "bi-table bi-stack", bh("thead", "", bh("tr", "",
    bh("th", "", "欄位"), bh("th", "", "新值"), bh("th", "", "依據"), bh("th", "", "出處"),
    bh("th", "", "目前值"), bh("th", "", "修改"))));
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
    const change = {add: "新增", change: "變更", same: "相同", human_kept: "保留人工值，改成提議"};
    rows.append(bh("tr", "", bh("td", "", (field && field.label) || item.field),
      bh("td", "", biValue(item.value)), bh("td", "", biBadge(basis[0], basis[1])),
      bh("td", "", biEvidence(item)), bh("td", "", biValue(item.current) + "（"
        + (change[item.change] || item.change) + "）"), bh("td", "", input, save)));
  }
  table.append(rows);
  parts.push(bh("div", "bi-scroll", table));
  if (open) {
    parts.push(bh("div", "bi-actions",
      biButton("接受", () => biBuildReview(candidate.id, {review: "accepted"}), "go"),
      biButton("拒絕", () => biBuildReview(candidate.id, {review: "rejected"}), "bi-btn"),
      biButton("待決定", () => biBuildReview(candidate.id, {review: "pending"}), "bi-btn")));
  }
  box.append(...parts);
}

el("bi-b-accept-clean").addEventListener("click", async () => {
  const todo = bi.build.candidates.filter((c) => c.review === "pending" && !c.errors.length
    && c.action !== "skip");
  // 「下一步」 waits for all of them: moving on early wrote only the ones accepted so far.
  bi.build.accepting = true;
  try {
    for (const candidate of todo) await biBuildReview(candidate.id, {review: "accepted"});
  } finally {
    bi.build.accepting = false;
    biBuildRenderRun();
  }
  biNotice(true, "已接受 " + todo.length + " 張沒有錯誤的候選卡。");
});

// -- steps 5-6: commit and result --------------------------------------------
function biBuildSummary() {
  const run = bi.build.run, box = el("bi-b-summary"); box.replaceChildren();
  el("bi-b-commit-msg").replaceChildren();
  if (!run) return;
  const s = run.summary || {};
  const accepted = bi.build.candidates.filter((c) => c.review === "accepted");
  const count = (action) => accepted.filter((c) => c.action === action).length;
  box.append(bh("p", "", "目的地：資料集「" + biDataset() + "」・schema " + run.schema_ref),
    bh("ul", "", bh("li", "", "新建 " + count("create") + " 張"),
      bh("li", "", "更新 " + count("update") + " 張"),
      bh("li", "", "拒絕或略過 " + ((s.rejected || 0) + (s.skip || 0)) + " 張"),
      bh("li", "", "還沒決定 " + (s.pending || 0) + " 張（不會寫入）")),
    bh("p", "bi-meta", "按「確認匯入」後，所有已接受的候選卡一次寫入；有任何卡片在審核後被改過，"
      + "就一張都不寫，請重新檢查。寫入後可以整批復原。"));
  el("bi-b-commit-go").disabled = !accepted.some((c) => ["create", "update"].includes(c.action));
}

el("bi-b-commit-go").addEventListener("click", async () => {
  const run = bi.build.run, msg = el("bi-b-commit-msg"); msg.replaceChildren();
  const button = el("bi-b-commit-go"); button.disabled = true;
  try {
    const reply = await biCall("/api/bi/runs/" + run.id + "/commit", {dataset: biDataset()});
    bi.build.run = reply.run; bi.build.result = reply; bi.loaded = {};
    biBuildStage("result"); biRefreshCounts();
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
      bh("li", "", "成為待審提議 " + (applied.proposals || 0)),
      done.skipped != null ? bh("li", "", "略過 " + done.skipped) : "",
      done.pending != null ? bh("li", "", "未決定、沒有寫入 " + done.pending) : ""),
    bh("p", "bi-meta", (done.index && done.index.message) || "BI 卡片寫入後即可查詢。"),
    bh("div", "bi-actions",
      biButton("到卡片查看", () => biShowView("cards"), "go"),
      biButton("看 Dashboard", () => biShowView("dashboard"), "bi-btn"),
      biButton("復原這次匯入", async () => {
        await biCall("/api/bi/import/undo", {dataset: biDataset(),
          import_id: run.commit.import_id});
        biNotice(true, "已復原這次匯入。"); bi.loaded = {}; biRefreshCounts();
      }, "bi-btn"),
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
  document.querySelector("#bi-views [data-bi-view=build]").hidden = readOnly;
  if (readOnly && bi.view === "build") biShowView("dashboard");
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
    actions.append(biButton("取消訂閱", (event) => biUnsubscribe(sub, event.currentTarget),
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

async function biUnsubscribe(sub, button) {
  if (!window.confirm("取消訂閱「" + sub.name + "」？這台電腦上的副本會被移除，"
      + "之後要再到 Shared Platform 選取才能讀。")) return;
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
});

const panels = {ask: null, installed: loadCapabilities,
  settings: loadSettings, schedules: loadSchedules, knowledge: loadKnowledgeTab, tasks: loadTasks,
  reviews: loadReviews, memory: loadMemory};

function showBootError(failure) {
  const banner = el("boot-error"); banner.hidden = false;
  banner.textContent = "Agent Web could not finish loading: " + failure.message;
}

async function selectPrimaryTab(name) {
  for (const other of Object.keys(panels)) {
    el("panel-" + other).toggleAttribute("data-open", other === name);
  }
  el("nav-capabilities").toggleAttribute("aria-current", name === "installed");
  el("nav-settings").toggleAttribute("aria-current", name === "settings");
  el("nav-schedules").toggleAttribute("aria-current", name === "schedules");
  el("nav-knowledge").toggleAttribute("aria-current", name === "knowledge");
  el("nav-tasks").toggleAttribute("aria-current", name === "tasks");
  el("nav-reviews").toggleAttribute("aria-current", name === "reviews");
  el("nav-memory").toggleAttribute("aria-current", name === "memory");
  el("chat-backend-bar").hidden = name !== "ask";
  if (name === "ask") { field.focus(); return; }
  try { await panels[name](); }
  catch (failure) { showBootError(failure); }
}

el("nav-capabilities").addEventListener("click", () => selectPrimaryTab("installed"));
el("nav-settings").addEventListener("click", () => selectPrimaryTab("settings"));
el("nav-schedules").addEventListener("click", () => selectPrimaryTab("schedules"));
el("nav-knowledge").addEventListener("click", () => selectPrimaryTab("knowledge"));
el("nav-tasks").addEventListener("click", () => selectPrimaryTab("tasks"));
el("nav-reviews").addEventListener("click", () => selectPrimaryTab("reviews"));
el("nav-memory").addEventListener("click", () => selectPrimaryTab("memory"));

assetsReady = loadAssets();
Promise.all([loadAbout(), assetsReady, loadChat(), loadSlashCommands(), loadAvatars(), loadMcp()])
  .catch(showBootError);
field.focus();
</script>
</body>
</html>
"""

# The BI chart renderer is shared with the chat's chart files (one source, no drift).
PAGE = PAGE.replace("/* BI_CHART_CSS */", BI_CHART_CSS, 1).replace(
    "/* BI_CHART_JS */", BI_CHART_JS.rstrip(), 1
)
