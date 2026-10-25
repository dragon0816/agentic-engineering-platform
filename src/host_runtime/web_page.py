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
          <div class="card"><h3>From the project vault</h3>
            <p class="note">Originals not yet ingested are copied into the sandbox. Ingested
              ones are already here as Raw, so they are not pulled again.</p>
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
          <div class="card"><h3>Push to the vault</h3>
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
          <h3>Local candidate</h3>
          <p class="note">Merge into a local candidate and publish it as the Agent's version
            without pushing to the project vault.</p>
          <div class="kp-actions">
            <button id="kp-merge" type="button">Merge into a candidate</button>
            <button id="kp-publish" type="button" disabled>Publish candidate</button>
          </div>
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
          <div class="bi-counts" id="bi-counts" role="status" aria-live="polite">&hellip;</div>
        </div>
        <div class="bi-actions">
          <button class="go" id="bi-demo" type="button">載入示範資料</button>
          <button class="bi-btn" id="bi-new" type="button" aria-expanded="false"
            aria-controls="bi-new-panel">新增資料集</button>
          <button class="bi-btn" id="bi-install" type="button" aria-expanded="false"
            aria-controls="bi-install-panel">安裝 schema</button>
          <button class="bi-btn" id="bi-refresh" type="button">更新</button>
          <button class="bi-btn" id="bi-publish" type="button" aria-expanded="false"
            aria-controls="bi-publish-panel">發佈到 Shared Platform</button>
        </div>
        <p class="bi-meta bi-schema-note" id="bi-schema-note"></p>
        <div class="bi-empty-state" id="bi-empty-state" role="note" hidden>
          <p class="bi-meta">這台電腦還沒有 BI 資料集。載入示範資料來看看，
            或新增一個資料集再匯入 CSV。</p>
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
        <p class="bi-meta">建立後不能更換 schema。Dashboard 與對話查詢只支援 BI schema
          （bi.schema/*）；其他 schema 的資料集可以匯入、瀏覽與編輯卡片。</p>
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
        <button type="button" role="tab" data-bi-view="dashboard"
          aria-selected="true">Dashboard</button>
        <button type="button" role="tab" data-bi-view="cards" aria-selected="false">卡片</button>
        <button type="button" role="tab" data-bi-view="import"
          aria-selected="false">匯入 CSV</button>
      </div>
      <div id="bi-view-dashboard" role="tabpanel" aria-label="Dashboard">
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
      <div id="bi-view-import" role="tabpanel" aria-label="匯入 CSV" hidden>
        <div class="card bi-step">
          <h3>1. 選擇 CSV 檔</h3>
          <div class="bi-step-grid">
            <div><label class="bi-label" for="bi-file">CSV 檔（UTF-8，含 BOM 亦可）</label>
              <input id="bi-file" type="file" accept=".csv,text/csv"></div>
            <div><label class="bi-label" for="bi-entity">卡片類型</label>
              <select id="bi-entity"><option value="">自動判斷</option></select></div>
            <div><button class="go" id="bi-preview-go" type="button" disabled>預覽</button></div>
          </div>
          <p class="bi-meta">預覽只比對，不寫入任何資料；按「確認寫入」才會寫入，
            寫入後也可以復原。</p>
        </div>
        <div class="mem-status" id="bi-status-import" role="status" aria-live="polite" hidden></div>
        <div id="bi-preview" hidden>
          <div class="card bi-step">
            <h3>2. 欄位對應</h3>
            <div id="bi-summary-chips" class="bi-chips" aria-label="預覽摘要"></div>
            <div class="bi-scroll"><table class="bi-table bi-stack" id="bi-mapping">
              <thead><tr><th>CSV 欄位</th><th>對應到</th><th>狀態</th><th>說明</th></tr></thead>
              <tbody></tbody></table></div>
          </div>
          <div class="card bi-step">
            <h3>3. 逐卡差異</h3>
            <p class="bi-meta">展開每一列，看原始值 → 正規化後的值，以及目前值 → 新值。
              人工設定過的值不會被覆蓋，會改成待審提議。</p>
            <div class="bi-actions" style="margin: 0 0 8px">
              <button class="bi-btn" id="bi-select-all" type="button">全選</button>
              <button class="bi-btn" id="bi-select-none" type="button">全不選</button>
            </div>
            <div id="bi-rows"></div>
            <div class="bi-apply">
              <button class="go" id="bi-apply" type="button">確認寫入</button>
              <span class="bi-meta" id="bi-apply-note"></span>
            </div>
          </div>
        </div>
        <div id="bi-result" class="card bi-result" role="status" aria-live="polite" hidden></div>
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
      for (const file of answerFiles) {
        const kind = fileKind(file);
        if (kind === "image") said.parentNode.append(answerImage(record.session_id, file));
        else if (kind === "html") said.parentNode.append(answerHtml(record.session_id, file));
      }
      if (answerFiles.length) said.parentNode.append(fileChips(record.session_id, answerFiles));
      if (replied.task_summary_id) {
        said.parentNode.append(summaryNoteButton(replied.task_summary_id));
      }
      attachTurnControls(said.parentNode, asked.text, replied);
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

function renderSessionList() {
  const query = el("session-search").value.trim().toLowerCase();
  const visible = conversationRows.filter((item) =>
    [item.title, item.backend].filter(Boolean).join(" ").toLowerCase().includes(query));
  el("session-count").textContent = String(conversationRows.length);
  const buttons = visible.map((item) => {
    const button = document.createElement("button"); button.type = "button";
    button.className = "session-item"; button.setAttribute("role", "option");
    button.setAttribute("aria-selected", String(item.session_id === activeConversation));
    const title = document.createElement("strong"); title.append(text(item.title));
    const detail = document.createElement("small");
    detail.append(text(item.messages + " messages · " + item.backend
      + (sessionBusy(item.session_id) ? " · 執行中" : "")));
    button.append(title, detail);
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
    await loadChat(activeConversation || undefined);
  } catch (failure) { showBootError(failure); }
}

async function loadConversations(selectId) {
  let listed = await call("/api/conversations"
    + (selectId ? "?session_id=" + encodeURIComponent(selectId) : ""));
  if (!listed.conversations.length) {
    const created = await call("/api/conversations", {});
    selectId = created.conversation.session_id;
    listed = await call("/api/conversations?session_id=" + encodeURIComponent(selectId));
  }
  conversationRows = listed.conversations;
  activeConversation = selectId || listed.conversations[0].session_id;
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

el("session-search").addEventListener("input", renderSessionList);
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
  const tools = document.createElement("ul"); tools.className = "tp-tools";
  tools.setAttribute("aria-label", "最近的工具");
  const meter = document.createElement("p"); meter.className = "tp-meter";
  box.append(status, steps, tools, meter);
  return box;
}

function progressStatus(progress) {
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

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (uploadingFiles > 0 || startingSession) return;
  const files = readyFiles();
  const asked = field.value.trim() || (files.length ? "請看附件。" : "");
  if (!asked || !activeConversation) return;
  field.value = "";
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

function renderCodingAgents(listed) {
  const box = el("coding-agents");
  box.className = ""; box.replaceChildren();
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
    + (telegram.enabled ? (telegram.running ? " Bot is answering." : " Bot is starting…")
      : (telegram.configured
        ? " Saved, but the bot is off: tick"
          + " \u201cAnswer Telegram messages\u201d and save to start it."
        : " Bot is off."))
    + (telegram.failure ? " Last stop: " + telegram.failure : "");
}

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
  if (kpSandbox && !listed.sandboxes.some((s) => s.sandbox_id === kpSandbox.sandbox_id)) {
    kpSandbox = null;
  }
  if (!kpSandbox) kpStage("pull", false);
}

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

function kpStage(name, focus = true) {
  const open = !!kpSandbox;
  const stage = open && KP_STAGES.includes(name) ? name : "pull";
  kpCurrentStage = stage;
  for (const button of document.querySelectorAll(".kp-stepper [data-stage]")) {
    if (button.dataset.stage === stage) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
    button.disabled = !open && button.dataset.stage !== "pull";
    button.title = button.disabled ? "Open or create a sandbox first" : "";
  }
  el("kp-start").hidden = open; el("kp-box").hidden = !open;
  for (const section of document.querySelectorAll(".kp-stage")) {
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

for (const button of document.querySelectorAll(".kp-stepper [data-stage]")) {
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
  el("kp-title").textContent = item.label + " \u2014 " + item.sandbox_id;
  kpStatus("Opening the sandbox: its files (1/5)\u2026");
  const contents = await pipeline("sandbox-contents", {sandbox_id: item.sandbox_id});
  el("kp-drop").replaceChildren(table(["Original in drop"], contents.drop, (row) => [row]));
  const raw = el("kp-raw"); raw.replaceChildren();
  const rawRefs = item.scope ? contents.raw.filter((ref) =>
    ref.startsWith("raw/" + item.scope + "/")) : contents.raw;
  el("kp-scope-name").textContent = item.scope || "whole vault (older sandbox)";
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
  kpStatus("Opening the sandbox: push status (5/5)\u2026"); await kpPushShow();
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
  const folders = await pipeline("drop-folders", {base: kpSandbox.base_name});
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
    el("kp-pull-folders").append(text(scope ? "The project vault's drop has no " + scope
      + " folder yet." : "The project vault's drop is empty."));
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
  human_kept: ["人工值保留，改成提議", "warn"]};

// Each dataset follows the schema it was created with (owner 2026-10-21): the
// type filter, import types, card detail and editors read `bi.schema`, loaded
// for the selected dataset. Dashboard and the chat hint are BI-only.
const bi = {schema: null, schemas: [], datasets: [], view: "dashboard", loaded: {}, cards: [],
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
    const [datasets, schemas] = await Promise.all([biCall("/api/bi/datasets"),
      biCall("/api/bi/schemas").catch(() => ({schemas: bi.schemas}))]);
    bi.datasets = datasets.datasets || []; bi.schemas = schemas.schemas || [];
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

function biRenderSchema() {
  const isBi = biIsBi(), schema = bi.schema || {};
  el("bi-demo").hidden = !isBi;
  el("bi-hint").hidden = !isBi;
  el("bi-domain-box").hidden = Array.isArray(schema.domains) && !schema.domains.length;
  const note = el("bi-schema-note"); note.replaceChildren();
  if (!schema.ref) return;
  note.append(text("Schema："), bh("strong", "", schema.title || schema.ref),
    text("（" + schema.ref + "）"));
  if (!isBi) note.append(text(" · 沒有 Dashboard 與對話查詢；卡片、匯入與編輯照常可用"));
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
      option.textContent = info && info.schema ? name + " · " + biSchemaTitle(info.schema) : name;
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
  for (const id of ["bi-type", "bi-entity"]) {
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
  bi.view = name;
  for (const button of document.querySelectorAll("#bi-views [data-bi-view]")) {
    button.setAttribute("aria-selected", String(button.dataset.biView === name));
  }
  for (const key of ["dashboard", "cards", "import"]) {
    el("bi-view-" + key).hidden = key !== name;
  }
  if (bi.loaded[name]) return;
  if (name === "dashboard") await biLoadDashboard();
  if (name === "cards") await biLoadCards();
}

for (const button of document.querySelectorAll("#bi-views [data-bi-view]")) {
  button.addEventListener("click", () => biShowView(button.dataset.biView));
}
el("bi-refresh").addEventListener("click", () => biLoad());
// A preview belongs to the dataset it was made for: switching drops it.
function biLeaveDataset() {
  bi.cardId = null; bi.preview = null; bi.publish = null;
  biPanel("publish", false); el("bi-pub-result").hidden = true;
  el("bi-pub-state").replaceChildren();
  el("bi-preview").hidden = true; el("bi-result").hidden = true;
  biStatus("bi-status-import", "");
}
el("bi-dataset").addEventListener("change", () => {
  biRemember(el("bi-dataset").value); biLeaveDataset(); biLoad();
});
el("bi-empty-demo").addEventListener("click", () => el("bi-demo").click());
el("bi-empty-new").addEventListener("click", () => biOpenNew());
el("bi-domain").addEventListener("change", () => {
  bi.loaded = {}; bi.cardId = null; biShowView(bi.view);
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
  biStatus("bi-status-dash", "loading", "載入中…");
  el("bi-dash-summary").replaceChildren(); el("bi-dash-sections").replaceChildren();
  let reply;
  try {
    reply = await biCall("/api/bi/dashboard?dataset=" + encodeURIComponent(biDataset())
      + "&domain=" + encodeURIComponent(biDomain()));
  } catch (failure) {
    biStatus("bi-status-dash", "error", "Dashboard 載入失敗：" + failure.message + "。",
      biLoadDashboard);
    return;
  }
  biStatus("bi-status-dash", ""); bi.loaded.dashboard = true;
  biRenderDashboard(reply);
}

function biRenderDashboard(reply) {
  const sections = (reply.sections || []).slice();
  const holder = el("bi-dash-sections"), strip = el("bi-dash-summary");
  if (reply.dashboard === false) {  // a dataset of a non-BI schema
    holder.append(bh("div", "bi-none", bh("h3", "", reply.message || "這個 schema 沒有 Dashboard"),
      bh("p", "", "資料集「" + biDataset() + "」使用「" + biSchemaTitle(reply.schema || "")
        + "」。Dashboard 與對話查詢只支援 BI schema（bi.schema/*）；這個資料集的卡片可以在"
        + "「卡片」瀏覽與編輯，也可以「匯入 CSV」。"),
      bh("div", "bi-actions", biButton("看卡片", () => biShowView("cards"), "go"),
        biButton("匯入 CSV", () => biShowView("import"), "bi-btn"))));
    return;
  }
  if (!sections.length) {
    holder.append(bh("p", "bi-empty", "這個領域還沒有卡片。先「載入示範資料」或「匯入 CSV」。"));
    return;
  }
  const rank = (section) => {
    const at = BI_GAP_SECTIONS.indexOf(biSectionKey(section.id));
    return at < 0 ? BI_GAP_SECTIONS.length : at;
  };
  sections.sort((a, b) => rank(a) - rank(b));  // stable: gaps first, the rest as sent
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

function biSection(section) {
  const box = document.createElement("details");
  box.className = "card bi-sec"; box.dataset.section = biSectionKey(section.id);
  const flags = section.flags || [];
  if (BI_GAP_SECTIONS.includes(box.dataset.section)) box.open = true;
  const summary = bh("summary", "", bh("span", "bi-sec-title", section.title || section.id));
  const reds = flags.filter((flag) => flag.level === "red").length;
  if (reds) summary.append(biBadge("缺口 " + reds, "bad"));
  if (flags.length - reds) summary.append(biBadge("警告 " + (flags.length - reds), "warn"));
  summary.append(bh("span", "bi-meta", (section.rows || []).length + " 列"));
  const body = bh("div", "bi-sec-body");
  if (section.note) body.append(bh("p", "bi-sec-note", section.note));
  const rows = section.rows || [];
  if (!rows.length) body.append(bh("p", "bi-empty", "沒有資料。"));
  else if (section.kind === "matrix") body.append(biMatrix(section));
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
  biStatus("bi-status-cards", "loading", "載入中…");
  const query = "?dataset=" + encodeURIComponent(biDataset()) + "&type="
    + encodeURIComponent(el("bi-type").value) + "&q=" + encodeURIComponent(el("bi-q").value.trim())
    + "&domain=" + encodeURIComponent(biDomain());
  let reply;
  try { reply = await biCall("/api/bi/cards" + query); }
  catch (failure) {
    biStatus("bi-status-cards", "error", "卡片載入失敗：" + failure.message + "。", biLoadCards);
    return;
  }
  biStatus("bi-status-cards", ""); bi.loaded.cards = true;
  bi.cards = reply.cards || [];
  biRenderCards();
}

function biRenderCards() {
  const list = el("bi-cards"); list.replaceChildren();
  el("bi-card-count").textContent = bi.cards.length + " 張卡片";
  if (!bi.cards.length) {
    list.append(bh("li", "bi-empty", el("bi-q").value.trim() || el("bi-type").value
      ? "沒有符合的卡片。" : "這個資料集還沒有卡片。先「載入示範資料」或「匯入 CSV」。"));
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
  if (!biReadOnly()) {  // a subscribed copy is read-only: no editor at all
    foot.append(biButton("編輯", () => biEditField(card, item, row), "bi-btn",
      "編輯「" + (item.label || item.field) + "」"));
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
  const reason = document.createElement("textarea"); reason.id = reasonId; reason.required = true;
  reason.placeholder = "為什麼改？例如：依據哪個訊號、客戶產品或商機";
  const error = bh("div", "bi-err"); error.setAttribute("role", "alert");
  const label = (text_, target) => { const node = bh("label", "bi-label", text_);
    node.htmlFor = target; return node; };
  const save = bh("button", "go", "儲存"); save.type = "submit";
  form.append(label("新值" + (spec.list ? "（多個值用「、」或逗號分隔）" : ""), valueId), input,
    label("理由（必填）", reasonId), reason, error,
    bh("div", "bi-actions", save, biButton("取消", () => form.remove())));
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); error.textContent = "";
    if (!reason.value.trim()) { error.textContent = "請寫下理由。"; reason.focus(); return; }
    let value = input.value.trim();
    if (spec.list) {
      value = value ? value.split(/[、,，;；]/).map((v) => v.trim()).filter(Boolean) : [];
    }
    else if (spec.type === "int" && value !== "" && !isNaN(Number(value))) value = Number(value);
    save.disabled = true; save.setAttribute("aria-busy", "true");
    try {
      const reply = await biCall("/api/bi/cards/" + encodeURIComponent(card.id) + "/field",
        {dataset: biDataset(), field: item.field, value, base_version: card.version,
         reason: reason.value.trim()});
      // The value it already had: no new version, nothing in the history.
      biNotice(true, reply.unchanged
        ? "沒有變更：「" + (item.label || item.field) + "」本來就是這個值（版本 "
          + reply.version + "）。"
        : "已儲存「" + (item.label || item.field) + "」（版本 " + reply.version + "）。");
      await biLoadDetail(false);
      biLoadCards();
    } catch (failure) {
      if (failure.code === "stale_edit") {
        const payload = failure.payload || {};
        const stale = bh("div", "bi-stale",
          bh("p", "", "這張卡片已經被 " + (payload.by || "別人") + " 在 " + biTime(payload.at)
            + " 改過，目前的值是「" + biValue(payload.current) + "」。你的修改還沒有儲存。"),
          biButton("重新載入卡片", () => biLoadDetail(true), "go"));
        stale.dataset.stale = "true";
        error.replaceChildren(stale);
      } else {
        error.textContent = "沒有儲存：" + failure.message;
      }
    } finally { save.disabled = false; save.removeAttribute("aria-busy"); }
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

// -- import wizard (Case A) ---------------------------------------------------
async function biReadCsv(file) {
  const bytes = await file.arrayBuffer();
  let decoded;
  try { decoded = new TextDecoder("utf-8", {fatal: true}).decode(bytes); }
  catch (e) {
    throw new Error("這個檔案不是 UTF-8 編碼。請在 Excel 用「另存新檔 → CSV UTF-8」後再試。");
  }
  return decoded.replace(/^﻿/, "");
}

el("bi-file").addEventListener("change", () => {
  el("bi-preview-go").disabled = !el("bi-file").files.length;
  el("bi-preview").hidden = true; el("bi-result").hidden = true; bi.preview = null;
});
el("bi-preview-go").addEventListener("click", () => biPreview());

async function biPreview() {
  const file = el("bi-file").files[0];
  if (!file) return;
  el("bi-result").hidden = true; el("bi-preview").hidden = true;
  biStatus("bi-status-import", "loading", "正在預覽 " + file.name + "…（不會寫入）");
  try {
    const csv = await biReadCsv(file);
    bi.preview = await biCall("/api/bi/import/preview", {dataset: biDataset(),
      entity_type: el("bi-entity").value || null, filename: file.name, csv_text: csv,
      mapping: null});
  } catch (failure) {
    biStatus("bi-status-import", "error", "預覽失敗：" + failure.message, biPreview);
    return;
  }
  biStatus("bi-status-import", "");
  biRenderPreview();
}

function biRenderPreview() {
  const preview = bi.preview, summary = preview.summary || {};
  const chips = el("bi-summary-chips"); chips.replaceChildren();
  const chip = (cls, label, count) => bh("span", "bi-chip " + cls, label,
    bh("b", "", String(count || 0)));
  chips.append(bh("span", "bi-chip accent", "類型", bh("b", "", biTypeLabel(preview.entity_type))),
    chip("good", "新增", summary.create), chip("accent", "更新", summary.update),
    chip("", "不變", summary.unchanged), chip("warn", "略過", summary.skip),
    chip(summary.warnings ? "bad" : "", "警告", summary.warnings));
  const body = el("bi-mapping").querySelector("tbody"); body.replaceChildren();
  for (const column of preview.columns || []) {
    const status = BI_MAPPING[column.status] || [column.status, "dim"];
    const tr = bh("tr", "");
    tr.dataset.status = column.status;
    const cells = [
      ["CSV 欄位", bh("strong", "", column.source)],
      ["對應到", column.field ? column.field : bh("span", "bi-meta", "—")],
      ["狀態", biBadge(status[0], status[1])],
      ["說明", column.note || ""]];
    for (const [label, value] of cells) {
      const td = bh("td", "", value); td.dataset.label = label; tr.append(td);
    }
    body.append(tr);
  }
  const rows = el("bi-rows"); rows.replaceChildren();
  for (const row of preview.rows || []) rows.append(biDiffRow(row));
  el("bi-preview").hidden = false;
  el("bi-apply").disabled = false;
  biApplyNote();
  el("bi-preview").querySelector("h3").scrollIntoView({block: "nearest"});
}

function biDiffRow(row) {
  const box = bh("div", "bi-row"); box.dataset.row = row.row;
  const selectable = row.action === "create" || row.action === "update";
  const check = document.createElement("input"); check.type = "checkbox";
  check.checked = selectable; check.disabled = !selectable; check.dataset.row = row.row;
  check.setAttribute("aria-label", "寫入第 " + row.row + " 列");
  check.addEventListener("change", biApplyNote);
  const action = BI_ACTION[row.action] || [row.action, "dim"];
  const toggle = bh("button", "bi-row-toggle", bh("span", "bi-meta", "第 " + row.row + " 列"),
    bh("strong", "", row.canonical_key || "（無代碼）"), biBadge(action[0], action[1]));
  toggle.type = "button"; toggle.setAttribute("aria-expanded", "false");
  const kept = (row.fields || []).filter((f) => f.change === "human_kept").length;
  if (kept) toggle.append(biBadge("人工值保留 " + kept, "warn"));
  if ((row.warnings || []).length) toggle.append(biBadge("警告 " + row.warnings.length, "bad"));
  const detail = bh("div", "bi-row-body"); detail.hidden = true;
  detail.id = "bi-row-body-" + row.row; toggle.setAttribute("aria-controls", detail.id);
  toggle.addEventListener("click", () => {
    const open = toggle.getAttribute("aria-expanded") !== "true";
    toggle.setAttribute("aria-expanded", String(open)); detail.hidden = !open;
  });
  const checkLabel = bh("label", "bi-row-check", check);
  box.append(bh("div", "bi-row-head", checkLabel, toggle));
  if ((row.fields || []).length) {
    const table = bh("table", "bi-table bi-stack");
    table.append(bh("thead", "", bh("tr", "", bh("th", "", "欄位"), bh("th", "", "原始值 → 正規化"),
      bh("th", "", "目前 → 新值"), bh("th", "", "變更"))));
    const body = bh("tbody", "");
    for (const item of row.fields) {
      const change = BI_CHANGE[item.change] || [item.change, "dim"];
      const tr = bh("tr", item.change === "human_kept" ? "bi-kept" : "");
      tr.dataset.change = item.change;
      const cells = [
        ["欄位", bh("strong", "", item.field)],
        ["原始值 → 正規化", bh("span", "", bh("span", "", biValue(item.raw)),
          bh("span", "bi-arrow", "→"), bh("span", "", biValue(item.normalized)))],
        ["目前 → 新值", bh("span", "", bh("span", "", biValue(item.current)),
          bh("span", "bi-arrow", "→"), bh("span", "", item.change === "human_kept"
            ? biValue(item.current) + "（提議：" + biValue(item.normalized) + "）"
            : biValue(item.normalized)))],
        ["變更", biBadge(change[0], change[1])]];
      for (const [label, value] of cells) {
        const td = bh("td", "", value); td.dataset.label = label; tr.append(td);
      }
      body.append(tr);
    }
    table.append(body); detail.append(bh("div", "bi-scroll", table));
  }
  if ((row.warnings || []).length) {
    detail.append(bh("ul", "bi-warnings", ...row.warnings.map((warning) =>
      bh("li", "", "⚠ " + (warning.message || warning.code)))));
  }
  box.append(detail);
  return box;
}

function biSelectedRows() {
  const all = [...document.querySelectorAll("#bi-rows input[type=checkbox]:not(:disabled)")];
  const picked = all.filter((box) => box.checked).map((box) => Number(box.dataset.row));
  return {all: all.length, picked};
}

function biApplyNote() {
  const {all, picked} = biSelectedRows();
  el("bi-apply").textContent = "確認寫入（" + picked.length + " 列）";
  el("bi-apply").disabled = !picked.length;
  el("bi-apply-note").textContent = picked.length === all ? "寫入所有新增與更新的列。"
    : "只寫入勾選的 " + picked.length + " 列（共 " + all + " 列可寫入）。";
}

for (const [id, value] of [["bi-select-all", true], ["bi-select-none", false]]) {
  el(id).addEventListener("click", () => {
    for (const box of document.querySelectorAll("#bi-rows input[type=checkbox]:not(:disabled)")) {
      box.checked = value;
    }
    biApplyNote();
  });
}

el("bi-apply").addEventListener("click", async () => {
  if (!bi.preview) return;
  const {all, picked} = biSelectedRows();
  const button = el("bi-apply"); button.disabled = true; button.setAttribute("aria-busy", "true");
  biStatus("bi-status-import", "loading", "寫入中…");
  let reply;
  try {
    reply = await biCall("/api/bi/import/apply", {preview_id: bi.preview.preview_id,
      rows: picked.length === all ? null : picked});
  } catch (failure) {
    button.disabled = false; button.removeAttribute("aria-busy");
    biStatus("bi-status-import", "error", "沒有寫入：" + failure.message,
      () => el("bi-apply").click());
    return;
  }
  button.removeAttribute("aria-busy");
  biStatus("bi-status-import", "");
  bi.importId = reply.import_id; bi.importDataset = biDataset(); bi.preview = null;
  el("bi-preview").hidden = true;
  biRenderResult(reply.applied || {});
  bi.loaded = {};
  biRefreshCounts();
});

function biRenderResult(applied) {
  const box = el("bi-result"); box.replaceChildren(); box.hidden = false;
  box.style.borderColor = "";
  const chip = (cls, label, count) => bh("span", "bi-chip " + cls, label,
    bh("b", "", String(count || 0)));
  box.append(bh("h3", "", "已寫入"), bh("div", "bi-chips", chip("good", "新增", applied.created),
    chip("accent", "更新", applied.updated), chip("", "不變", applied.unchanged),
    chip(applied.proposals ? "warn" : "", "提議", applied.proposals)));
  if (applied.proposals) {
    box.append(bh("p", "bi-meta", applied.proposals
      + " 個欄位原本是人工設定的值，保留不變；匯入的值改成待審提議，可在卡片中查看。"));
  }
  box.append(bh("div", "bi-actions",
    biButton("到卡片查看", () => { bi.loaded = {}; return biShowView("cards"); }, "go"),
    biButton("復原這次匯入", biUndo, "bi-btn")));
}

async function biUndo() {
  if (!bi.importId) return;
  if (!confirm("復原這次匯入？新增的卡片會移除，更新的欄位回到匯入前的值。")) return;
  biStatus("bi-status-import", "loading", "復原中…");
  try { await biCall("/api/bi/import/undo", {import_id: bi.importId, dataset: bi.importDataset}); }
  catch (failure) {
    biStatus("bi-status-import", "error", "沒有復原：" + failure.message, biUndo);
    return;
  }
  biStatus("bi-status-import", "");
  bi.importId = null;
  const box = el("bi-result"); box.replaceChildren(bh("h3", "", "已復原這次匯入。"),
    bh("p", "bi-meta", "資料已回到匯入前的狀態。"));
  bi.loaded = {};
  biRefreshCounts();
}

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

function biRenderReadOnly() {
  const info = biCurrent(), readOnly = biReadOnly();
  el("bi-demo").hidden = readOnly || !biIsBi();
  el("bi-publish").hidden = readOnly;
  const importTab = document.querySelector("#bi-views [data-bi-view=import]");
  importTab.hidden = readOnly;
  if (readOnly && bi.view === "import") biShowView("dashboard");
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
    + (when ? " · 發佈於 " + biTime(when) : "") + " · 不能匯入或編輯";
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
