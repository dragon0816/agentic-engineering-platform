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
.kp-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.kp-list button { margin: 2px 6px 2px 0; }
.kp-check { display: inline-block; margin: 2px 14px 2px 0; }
.kp-sticky { position: sticky; top: 0; z-index: 5; }
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
  border: 1px solid var(--line, #ddd); border-radius: 6px; background: var(--panel, #fff); }
.kp-pane > header { padding: 6px 10px; font-weight: 600; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; border-bottom: 1px solid var(--line, #ddd); }
.kp-pane-body { flex: 1; overflow: auto; position: relative; min-height: 0; }
.kp-split { flex: 0 0 8px; cursor: col-resize; touch-action: none; }
.kp-split:hover { background: var(--accent-soft, #dbe8f7); }
.kp-max { position: absolute; right: 8px; bottom: 8px; z-index: 3; padding: 2px 8px; opacity: 0.8; }
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
.kp-gutter { flex: 0 0 6.4em; overflow: hidden; padding: 8px 0; }
.kp-gline { display: flex; height: 20px; white-space: pre; }
.kp-code { padding: 8px; margin: 0; white-space: pre; tab-size: 4; }
.kp-code > div { min-height: 20px; }
.kp-editwrap { position: relative; flex: 1; overflow: hidden; }
.kp-backdrop { position: absolute; inset: 0; overflow: hidden; color: transparent;
  pointer-events: none; }
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
.laya-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px 14px; }
.laya-grid label { display: flex; flex-direction: column; gap: 2px; }
.settings .laya-check { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.settings .laya-check input { width: auto; margin: 0; flex: none; }
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
.topbar { display: flex; justify-content: flex-end; padding: 10px 18px;
  border-bottom: 1px solid var(--line); background: var(--bg); }
.topbar .who { color: var(--dim); font-size: 13px; }
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
.approval-card { margin: 12px 0; padding: 10px 12px; border: 1px solid var(--accent);
  border-radius: 8px; background: var(--accent-soft); }
.approval-card p { margin: 6px 0 8px; white-space: pre-wrap; overflow-wrap: anywhere; }
.approval-card button { margin-right: 8px; }
.approval-note { font-size: 13px; }
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
.backend-control { display: flex; align-items: center; gap: 9px; min-width: 0; flex: 1; }
.backend-control select { width: auto; min-width: 190px; max-width: 330px;
  border: 0; background: transparent; font: inherit; font-weight: 600; padding: 7px 28px 7px 8px; }
.backend-state { min-width: 0; color: var(--dim); font-size: 12px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
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
.workflow-field .field-error { color: var(--bad); margin: 4px 0; font-size: 12px; }
.workflow-field [aria-invalid="true"] { border-color: var(--bad); }
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
.market-card { min-height: 180px; padding: 14px; border: 1px solid var(--line);
  border-left: 4px solid var(--accent); border-radius: 9px; background: var(--panel); }
.market-card h3 { margin: 0; font-size: 15px; overflow-wrap: anywhere; }
.market-card p { margin: 8px 0; color: var(--dim); font-size: 13px; }
.market-card .inline-actions { margin-top: 12px; }
.badges { display: flex; flex-wrap: wrap; gap: 5px; margin: 9px 0; }
.tag.warn { color: var(--warn); border-color: var(--warn); }
.section-status { min-height: 22px; color: var(--dim); font-size: 13px; }
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
  .composer-footer, .backend-control { align-items: stretch; flex-direction: column; }
  .backend-control select { width: 100%; max-width: none; }
  .send-button { width: 100%; }
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
  </div>
  <div class="session-heading"><span>Sessions</span><span id="session-count">0</span></div>
  <input id="session-search" class="session-search" type="search"
         aria-label="Search sessions" placeholder="Search sessions">
  <div id="session-list" class="session-list" role="listbox" aria-label="Sessions"></div>
</aside>
<div class="workspace">
<header class="topbar">
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
        <div class="backend-control">
          <select id="conversation-backend" aria-label="Conversation backend"></select>
          <span id="backend-state" class="backend-state" role="status"></span>
          <button id="backend-settings" class="link-button" type="button" hidden>
            Open Settings</button>
        </div>
        <button class="go send-button" id="send" type="submit" disabled>Send</button>
      </div>
    </form>
    <p class="hint">This is the Agent on this computer &mdash; the same one the
      command line and Telegram reach, with the same permissions and the same
      refusals. Nothing is written unless the command says so. One request runs
      at a time.</p>
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
    <h2>Natural-language model</h2>
    <p class="note">Connect the Agent to the existing OpenAI-compatible Gateway.
      This page stores only connection metadata and optional secret/environment names.
      It never accepts or stores an access-token value.</p>
    <div class="card settings">
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
    <div class="cap-layout">
      <div class="cap-browser">
        <div class="cap-search"><label for="capability-search">Search installed capabilities</label>
          <input id="capability-search" type="search"
                 placeholder="Name, namespace or description"></div>
        <div id="capability-list" class="cap-list" role="listbox"
             aria-label="Installed capabilities"></div>
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
    <div class="card" id="drafts-card" style="margin-top: 14px">
      <h3>我的草稿（尚未安裝）</h3>
      <p class="note">在對話中或由外部 Agent 做出、還沒安裝的 Workflow 與 Skill。
        按「安裝」就是你的核准；Workflow 立即可在對話中重用，Skill 在主機重新啟動後生效。
        「執行一次」不等於安裝。</p>
      <div id="drafts" class="empty">reading&hellip;</div>
    </div>
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
          <option value="authorized">Authorized</option><option value="available">Available</option>
        </select>
        <a id="member-portal" hidden target="_blank" rel="noopener noreferrer"
           aria-label="Open shared marketplace (Agent Add-ons and Applications)">
          Open Marketplace</a>
        <button class="go" id="platform-sync" type="button" disabled>Synchronize selected</button>
      </div>
      <div id="platform-sync-result" class="section-status" role="status" aria-live="polite">
        Synchronization runs only when you press the button.</div>
      <div id="catalog" class="market-grid" aria-live="polite">
        <div class="empty">reading&hellip;</div></div>
      <details style="margin-top: 14px"><summary>Selections authorized on this Bridge</summary>
        <p class="note">A synchronized selection does not bypass capability policy.</p>
        <div class="card"><div id="decisions" class="empty">reading&hellip;</div></div>
      </details>
    </div>
    <details id="recent-runs" class="card settings" style="margin-top: 14px">
      <summary><strong>Recent runs</strong></summary>
      <div id="runs" class="empty">reading&hellip;</div>
    </details>
  </section>

  <section id="panel-knowledge">
    <div class="workspace-head">
      <div><h2>Knowledge</h2>
        <p class="note">Convert, ingest and lint run in your own sandbox, a copy of a base
          vault. Nothing here changes the base vault.</p></div>
      <button class="go" id="kp-refresh" type="button">Refresh</button>
    </div>
    <div id="kp-disabled" class="empty" hidden>The Knowledge pipeline is not configured on
      this machine (host.json <code>knowledge_pipeline</code>).</div>
    <div id="kp-status" class="section-status kp-sticky" role="status" aria-live="polite"><span
      id="kp-status-text"></span> <span id="kp-status-time" class="note"></span></div>
    <div id="kp-progress" class="kp-progress kp-sticky" hidden>
      <progress id="kp-progress-bar" max="1"></progress>
      <span id="kp-progress-text" class="note"></span></div>
    <div id="kp-main">
      <details class="card" id="xp-card"><summary><strong>Experience review</strong>
        <span class="note" id="xp-summary"></span></summary>
        <p class="note">Failed, down-rated and evidence-gap answers are collected as cases;
          a nightly review groups them and proposes improvements. Nothing is changed by the
          review: it only reports.</p>
        <div class="kp-actions">
          <button class="go" id="xp-run" type="button">Review now</button>
          <label>Keep cases <input id="xp-days" type="number" min="1" max="3650"
            style="width:5em"> days</label>
          <label><input id="xp-nightly" type="checkbox"> Review nightly</label>
          <button id="xp-save" type="button">Save settings</button>
        </div>
        <div id="xp-report" class="kp-markdown"></div></details>
      <h2>Sandboxes</h2>
      <div class="card">
        <div id="kp-sandboxes" class="kp-list">reading&hellip;</div>
        <form id="kp-new" class="kp-actions">
          <select id="kp-base" aria-label="Project vault"></select>
          <select id="kp-scope" aria-label="Folder this sandbox maintains" required></select>
          <input id="kp-label" required maxlength="80" placeholder="Sandbox name, e.g. VNA trial"
                 aria-label="Sandbox name">
          <button class="go" type="submit">Create sandbox</button>
        </form>
      </div>
      <div id="kp-box" hidden>
        <div class="kp-head"><h2 id="kp-title"></h2>
          <button id="kp-discard" type="button">Discard sandbox</button></div>
        <p class="note kp-flow">Scope and rules &rarr; Drop and convert &rarr; Ingest &rarr;
          Lint &rarr; Benchmark &rarr; Push</p>
        <div class="card"><h3>1. Scope and rules: <span id="kp-scope-name"></span></h3>
          <p class="note">This sandbox maintains one folder, chosen when it was created. Pull
            brings its originals not yet ingested; ingested ones are already here as Raw
            (step 3), so they are not pulled again.</p>
          <div id="kp-pull-folders" class="kp-list"></div>
          <div class="kp-actions"><button class="go" id="kp-pull" type="button">Pull</button>
            <span class="note" id="kp-pull-result"></span></div>
          <p class="note">The rules for this folder: how its data becomes wiki pages
            (ingest) and how its questions are answered (answer). More general layers and
            the vault-wide CLAUDE.md are read only here; their maintainers change them.
            Saved here only; a push brings a change to the project vault.</p>
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
            </div></div></div>
        <div class="card" id="kp-viewer" hidden><h3 id="kp-viewer-title">Preview</h3>
          <div class="kp-actions"><button id="kp-viewer-close" type="button">Close</button></div>
          <div id="kp-viewer-body" class="kp-markdown"></div></div>
        <div class="card"><h3>2. Drop and convert</h3>
          <p class="note">Add originals from this computer if they are not in the project's
            drop. The category folder picks the ingest rules (raw/&lt;category&gt;).</p>
          <div class="kp-actions">
            <select id="kp-category" aria-label="Category folder"></select>
            <input id="kp-files" type="file" multiple aria-label="Originals to add">
            <button id="kp-upload" type="button">Add to drop</button>
          </div>
          <div id="kp-drop"></div>
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
          <div id="kp-converted"></div></div>
        <div class="card"><h3>3. Ingest</h3>
          <p class="note">Plan ingest on a Raw document, Compare each page, then apply.
            After changing the rules, tick Raw documents (or a whole folder) and re-ingest
            them with the current rules; nothing needs to be pulled again.</p>
          <div class="kp-actions">
            <select id="kp-raw-folder" aria-label="Raw folder to tick"></select>
            <button id="kp-raw-tick" type="button">Tick folder</button>
            <button id="kp-raw-clear" type="button">Clear ticks</button>
            <button class="go" id="kp-reingest" type="button">Re-ingest ticked</button>
            <button id="kp-reingest-stop" type="button" hidden>Stop</button>
            <span class="note" id="kp-raw-count"></span></div>
          <div class="note" id="kp-reingest-state"></div>
          <div id="kp-reingest-result"></div>
          <div id="kp-raw" class="kp-list"></div>
          <div id="kp-plan" class="empty">Choose Plan ingest on a Raw document.</div></div>
        <div class="card"><h3>4. Lint</h3>
          <div class="kp-actions"><button id="kp-lint" type="button">Run lint</button></div>
          <div id="kp-lint-result"></div></div>
        <div class="card"><h3>5. Benchmark</h3>
          <p class="note">Each question is asked against this sandbox and against the project
            vault, and graded by its must-mention / must-not-say terms.</p>
          <div id="kp-bench-sets" class="kp-list"></div>
          <div class="kp-actions">
            <button class="go" id="kp-bench" type="button">Run benchmark</button>
            <span class="note" id="kp-bench-state"></span></div>
          <div id="kp-bench-result"></div></div>
        <div class="card"><h3>6. Push to the project vault</h3>
          <p class="note">Check conflicts first and choose a side for each. Push merges into
            the project vault as it is now, runs the question sets ticked under Benchmark on
            the merged result, and writes only when no question regresses and the score is
            not lower.</p>
          <div class="kp-actions">
            <button id="kp-merge-preview" type="button">Check conflicts</button>
            <button class="go" id="kp-push" type="button">Push</button>
            <button id="kp-refresh-agent" type="button">Refresh the Agent's Knowledge</button>
            <span class="note" id="kp-push-state"></span></div>
          <div id="kp-merge-result"></div>
          <div id="kp-push-result"></div></div>
        <details class="card kp-advanced"><summary>Advanced</summary>
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
      </div>
    </div>
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

function turn(asked, replyQuestion, files) {
  const block = turnBlock(asked, replyQuestion, files);
  log.append(block);
  log.scrollTop = log.scrollHeight;
  return block.querySelector(".said");
}

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
      asked.attachments || []);
    if (replied) {
      said.className = "said" + (replied.status === "failed" ? " bad" : "");
      renderAnswer(said, replied.text);
      attachTurnControls(said.parentNode, asked.text, replied);
    }
  }
  renderPendingTurns(record.session_id);
  renderApprovals(record.session_id).catch(() => {});
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

function turnBlock(asked, replyQuestion, files) {
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
  if (files && files.length) {
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
  block.append(tools);
  const area = document.createElement("div");
  area.className = "turn-feedback-area";
  if (message.feedback) area.append(feedbackSummary(message.feedback));
  block.append(area);
  block.addEventListener("contextmenu", event => {
    event.preventDefault();
    showTurnMenu(event.clientX, event.clientY, block, question, message);
  });
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
}

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
  el("conversation-backend").value = name; renderBackendState();
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
el("new-conversation").addEventListener("click", async () => {
  const created = await call("/api/conversations", {});
  selectPrimaryTab("ask");
  await loadChat(created.conversation.session_id); field.focus();
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
  entry.said.replaceChildren(text(entry.state === "queued" ? "排隊中…"
    : entry.state === "working" ? "working…"
      : "The request did not finish: " + entry.error));
}

function renderPendingTurns(sessionId) {
  for (const entry of pendingTurns.get(sessionId) || []) {
    entry.said = turn(entry.asked, entry.replyQuestion, entry.files);
    showPendingState(entry);
  }
}

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
  if (uploadingFiles > 0) return;
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
  renderSessionList();
  const run = async () => {
    entry.state = "working"; showPendingState(entry); renderSessionList();
    let answer = null;
    avatarWorking(1);
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

async function loadDrafts() {
  const box = el("drafts");
  const listed = await call("/api/drafts");
  if (!listed.drafts.length) {
    box.className = "empty"; box.textContent = "沒有尚未安裝的草稿。"; return;
  }
  box.className = ""; box.replaceChildren();
  for (const item of listed.drafts) {
    const card = document.createElement("div"); card.className = "approval-card";
    card.dataset.candidateId = item.candidate_id;
    const title = document.createElement("strong");
    title.textContent = (item.kind === "skill" ? "Skill " : "Workflow ") + item.asset
      + "（" + (item.source === "conversation" ? "對話" : item.source) + "）";
    const summary = document.createElement("p");
    const run = item.last_run;
    summary.textContent = (item.description || item.title)
      + "\n" + (item.kind === "skill" ? "指令：" : "步驟：") + item.steps.join(" → ")
      + (item.parameters.length ? "\n參數：" + item.parameters.join(", ") : "")
      + "\n上次執行：" + (run ? (run.result || run.status) + "（" + run.at + "）" : "尚未執行");
    const details = document.createElement("details");
    const label = document.createElement("summary"); label.textContent = "完整內容";
    const body = document.createElement("pre"); body.textContent = item.detail;
    details.append(label, body);
    const install = document.createElement("button"); install.type = "button";
    install.className = "approve"; install.textContent = "安裝";
    const remove = document.createElement("button"); remove.type = "button";
    remove.className = "reject"; remove.textContent = "刪除草稿";
    const note = document.createElement("span"); note.className = "approval-note";
    const act = async (action) => {
      if (action === "delete" && !confirm("刪除這個草稿？已安裝的版本不受影響。")) return;
      install.disabled = remove.disabled = true;
      note.textContent = action === "install" ? "安裝中…" : "";
      try {
        const done = await call("/api/drafts/" + action, {candidate_id: item.candidate_id});
        if (!done.ok) throw new Error(done.code || action + " failed");
        if (action === "install") alert("已安裝 " + done.installed_as + "。" + (done.note || ""));
        await loadAssets();
      } catch (failure) {
        note.textContent = failure.message; install.disabled = remove.disabled = false;
      }
    };
    install.addEventListener("click", () => act("install"));
    remove.addEventListener("click", () => act("delete"));
    card.append(title, summary, details, install, remove, note);
    box.append(card);
  }
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
  loadDrafts().catch(() => {});
  const assets = await call("/api/assets");
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
  installedAssets = Object.assign({applications: []}, assets);
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
  applications: []};
let activeCapabilityKind = "skills";
let activeCapabilityKey = "";

function capabilityKey(item) {
  return item.namespace + "/" + item.name + "@" + item.version;
}

function capabilityTitle(item, kind) {
  return kind === "skills" && item.alias ? item.alias : item.name;
}

function appendMeta(container, rows) {
  const list = document.createElement("dl"); list.className = "meta-grid";
  for (const [label, value] of rows) {
    const term = document.createElement("dt"); term.append(text(label));
    const detail = document.createElement("dd");
    if (value instanceof Node) detail.append(value); else detail.append(text(value || "\u2014"));
    list.append(term, detail);
  }
  container.append(list);
}

function showCapabilityDetail(item, kind) {
  const content = el("capability-detail-content"); content.className = "";
  content.replaceChildren();
  el("workflow-action").hidden = true;
  el("workflow-settings").hidden = true;
  el("knowledge-action").hidden = true;
  if (!item) {
    content.className = "empty";
    content.append(text(kind === "applications"
      ? "Applications run independently and are discovered in the authenticated Shared Marketplace."
      : "No installed " + kind + " match this search."));
    return;
  }
  const title = document.createElement("h3"); title.append(text(capabilityTitle(item, kind)));
  const identity = document.createElement("div"); identity.className = "identity";
  identity.append(text(capabilityKey(item)));
  const badges = document.createElement("div"); badges.className = "badges";
  badges.append(tag(true, "installed", ""));
  const description = document.createElement("p"); description.className = "detail-description";
  description.append(text(item.description || "No description supplied."));
  content.append(title, identity, badges, description);

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

function renderCapabilityBrowser() {
  for (const kind of ["skills", "workflows", "knowledge", "extensions", "applications"]) {
    el("count-" + kind).textContent = String(installedAssets[kind].length);
    el("cap-tab-" + kind).setAttribute("aria-selected", String(kind === activeCapabilityKind));
  }
  const query = el("capability-search").value.trim().toLowerCase();
  const rows = installedAssets[activeCapabilityKind].filter((item) =>
    [item.name, item.namespace, item.alias, item.description, item.domain, item.state]
      .filter(Boolean).join(" ").toLowerCase().includes(query));
  if (!rows.some((item) => capabilityKey(item) === activeCapabilityKey)) {
    activeCapabilityKey = rows.length ? capabilityKey(rows[0]) : "";
  }
  const buttons = rows.map((item) => {
    const button = document.createElement("button"); button.type = "button";
    button.className = "cap-item"; button.setAttribute("role", "option");
    const selected = capabilityKey(item) === activeCapabilityKey;
    button.setAttribute("aria-selected", String(selected));
    const title = document.createElement("strong");
    title.append(text(capabilityTitle(item, activeCapabilityKind)));
    const secondary = document.createElement("small"); secondary.append(text(capabilityKey(item)));
    button.append(title, secondary);
    button.addEventListener("click", () => {
      activeCapabilityKey = capabilityKey(item); renderCapabilityBrowser();
    });
    return button;
  });
  if (buttons.length) el("capability-list").replaceChildren(...buttons);
  else {
    const empty = document.createElement("div"); empty.className = "empty";
    empty.append(text(activeCapabilityKind === "applications"
      ? "Applications are managed in Shared Marketplace." : "No matching installed capabilities."));
    el("capability-list").replaceChildren(empty);
  }
  showCapabilityDetail(rows.find((item) => capabilityKey(item) === activeCapabilityKey),
    activeCapabilityKind);
}

for (const button of document.querySelectorAll(".cap-tabs button")) {
  button.addEventListener("click", () => {
    activeCapabilityKind = button.dataset.kind; activeCapabilityKey = "";
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

async function loadSettings() {
  const settings = await call("/api/settings"), model = settings.model,
    persona = settings.persona;
  el("persona-name").value = persona.name;
  el("persona-introduction").value = persona.introduction;
  el("persona-soul").value = persona.soul;
  showTelegram(settings.telegram);
  loadLaya().catch(() => {});
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
    });
    result.textContent = "Saved. The next ordinary chat turn uses "
      + saved.context.recent_messages + " recent messages within "
      + saved.context.history_budget_bytes + " UTF-8 bytes of history text.";
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
      version: workflow.version}} : null);
}

// -- Parameter forms ------------------------------------------------------
// One renderer for every form generated from a Workflow's parameter
// declaration (run form and schedule form); see common/workflow_forms.py.

let workflowFields = [];
const LIST_KINDS = ["text_list", "emails"];
const PATH_KINDS = ["file", "folder", "upload"];

function parameterControl(field, id) {
  const kind = field.kind;
  let input;
  if (kind === "select" && isDynamicChoice(field) && dynamicContext) {
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
  return !!field.choices_source && field.choices_source.startsWith("ref:");
}

function choiceDependencies(field) {
  const found = [...(field.needs || [])];
  for (const match of (field.choices_source || "").matchAll(/\{([A-Za-z_][A-Za-z0-9_]*)\}/g)) {
    if (!found.includes(match[1])) found.push(match[1]);
  }
  return found;
}

function renderParameterForm(container, fields, prefix, context) {
  dynamicContext = context || null;
  container.replaceChildren();
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
    const label = document.createElement("label"); label.htmlFor = id;
    label.append(text(field.label + (field.required ? " *" : "")
      + (field.confirm ? " (needs confirmation)" : "")));
    const input = parameterControl(field, id);
    input.setAttribute("aria-describedby", id + "-help " + id + "-error");
    const help = document.createElement("p"); help.id = id + "-help";
    help.className = "hint"; help.append(text(field.help || ""));
    const error = document.createElement("p"); error.id = id + "-error";
    error.className = "field-error"; error.setAttribute("aria-live", "polite");
    input.addEventListener("input", () => {
      error.textContent = ""; input.removeAttribute("aria-invalid");
    });
    row.append(label, input, help, error); container.append(row);
  }
  if (dynamicContext) wireDynamicChoices(container, fields, prefix, dynamicContext);
  dynamicContext = null;
}

function rawAnswers(container, fields, prefix) {
  const answers = {};
  for (const field of fields) {
    const input = container.querySelector("#" + CSS.escape(prefix + field.name));
    if (!input) continue;
    answers[field.name] = field.kind === "boolean" ? input.checked : input.value.trim();
  }
  return answers;
}

async function refreshChoices(container, fields, prefix, context, field) {
  const input = container.querySelector("#" + CSS.escape(prefix + field.name));
  if (!input) return;
  const previous = input.value || (field.default == null ? "" : String(field.default));
  const placeholder = (label) => {
    const option = document.createElement("option"); option.value = "";
    option.append(text(label)); return option;
  };
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
    option.append(text(choice.label)); option.selected = choice.value === previous;
    return option;
  });
  input.replaceChildren(...(input.multiple ? [] : [placeholder("Select " + field.label)]),
    ...options);
}

function wireDynamicChoices(container, fields, prefix, context) {
  const dynamic = fields.filter(isDynamicChoice);
  for (const field of dynamic) {
    refreshChoices(container, fields, prefix, context, field);
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
    else if (input.tagName === "SELECT" && input.multiple) {
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
    if (!input.checkValidity()) fail(input.validationMessage || "This value is not valid.");
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

function marketplaceAction(item) {
  const actions = document.createElement("div"); actions.className = "inline-actions";
  if (item.installed) {
    const installed = document.createElement("button"); installed.type = "button";
    installed.className = "go"; installed.disabled = true; installed.textContent = "Installed";
    actions.append(installed); return actions;
  }
  if (item.authorized) {
    const install = document.createElement("button"); install.type = "button";
    install.className = "go"; install.textContent = "Install selected";
    install.addEventListener("click", synchronizePlatform);
    actions.append(install); return actions;
  }
  if (sharedPlatform.member_portal_url) {
    const select = document.createElement("a"); select.href = sharedPlatform.member_portal_url;
    select.target = "_blank"; select.rel = "noopener noreferrer";
    select.textContent = item.kind === "bridge_extension"
      ? "Review Extension" : "Select in Marketplace";
    actions.append(select);
  }
  return actions;
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
  const cards = rows.map((item) => {
    const card = document.createElement("article"); card.className = "market-card";
    const title = document.createElement("h3");
    title.append(text(item.namespace + "/" + item.name));
    const identity = document.createElement("div"); identity.className = "identity";
    identity.append(text(item.kind + " · version " + item.version));
    const badges = document.createElement("div"); badges.className = "badges";
    badges.append(tag(true, "available", ""));
    if (item.authorized) badges.append(tag(true, "authorized", ""));
    if (item.installed) badges.append(tag(true, "installed", ""));
    if (!item.authorized) {
      const pending = tag(false, "", "select in Marketplace"); pending.classList.add("warn");
      badges.append(pending);
    }
    for (const category of item.categories || []) badges.append(tag(false, "", category));
    const description = document.createElement("p");
    description.append(text(item.description || "No description supplied."));
    const owner = document.createElement("p");
    owner.append(text("Owner: " + item.owner + " · " + item.visibility));
    const compatible = document.createElement("p");
    const compatibility = [item.runtime].concat(item.platforms).filter(Boolean).join(", ");
    compatible.append(text("Compatibility: " + (compatibility || "not declared")));
    card.append(title, identity, badges, description, owner, compatible,
      marketplaceAction(item));
    return card;
  });
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
      link.textContent = " Open Marketplace"; empty.append(link);
    }
    el("catalog").replaceChildren(empty);
  }
}

function renderPlatform(platform) {
  sharedPlatform = platform;
  el("platform-note").textContent = platform.note;
  el("platform-sync").disabled = !platform.configured;
  const portal = el("member-portal");
  if (platform.member_portal_url) {
    portal.href = platform.member_portal_url;
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
    if (synchronized.status === "answered") {
      result.textContent = "Synchronization complete: " + synchronized.installed.length
        + " installed, " + synchronized.selections + " active selections.";
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

async function loadCapabilities() {
  const refresh = el("cap-refresh"); refresh.disabled = true;
  refresh.setAttribute("aria-busy", "true"); refresh.textContent = "Refreshing…";
  try {
    await Promise.all([loadAssets(), loadPlatform()]);
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

async function xpLoad() {
  const info = await call("/api/experience");
  if (!info.ok) return;
  el("xp-days").value = info.settings.retention_days;
  el("xp-nightly").checked = info.settings.nightly;
  el("xp-summary").textContent = " \u2014 " + info.open + " open cases"
    + (info.last_review ? "; last review " + info.last_review.slice(0, 16) : "")
    + (info.last_error ? "; last attempt failed: " + info.last_error : "");
  el("xp-report").replaceChildren(info.review ? renderMarkdown(info.review.markdown)
    : text("No review yet."));
}
el("xp-save").addEventListener("click", () => kpRun("Saving", async () => {
  const reply = await call("/api/experience/settings", {
    retention_days: Number(el("xp-days").value), nightly: el("xp-nightly").checked});
  if (!reply.ok) {
    const problem = new Error(reply.code); problem.code = reply.code; throw problem;
  }
  await xpLoad();
}));
el("xp-run").addEventListener("click", () => kpRun("Starting the review", async () => {
  await call("/api/experience/review", {});
  kpStatus("The review runs in the background; its report appears here when done.");
  setTimeout(() => xpLoad().catch(() => {}), 60000);
}));

async function loadKnowledge() {
  xpLoad().catch(() => {});
  const info = await call("/api/knowledge/pipeline");
  el("kp-disabled").hidden = info.enabled; el("kp-main").hidden = !info.enabled;
  if (!info.enabled) return;
  const base = el("kp-base"); base.replaceChildren();
  for (const name of info.bases) {
    const option = document.createElement("option"); option.value = name;
    option.append(text(name)); base.append(option);
  }
  await kpLoadScopes();
  const listed = await pipeline("sandbox-list");
  const box = el("kp-sandboxes"); box.replaceChildren();
  if (!listed.sandboxes.length) box.append(text("No sandbox yet."));
  for (const item of listed.sandboxes) {
    box.append(kpButton(item.label + " (" + item.base_name + ")",
      () => kpRun("Opening", () => kpOpen(item))));
  }
  if (kpSandbox && !listed.sandboxes.some((s) => s.sandbox_id === kpSandbox.sandbox_id)) {
    kpSandbox = null; el("kp-box").hidden = true;
  }
}

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
  kpSandbox = item; el("kp-box").hidden = false;
  el("kp-title").textContent = item.label + " \u2014 " + item.sandbox_id;
  kpStatus("Opening the sandbox: its files (1/5)\u2026");
  const contents = await pipeline("sandbox-contents", {sandbox_id: item.sandbox_id});
  el("kp-drop").replaceChildren(table(["Original in drop"], contents.drop, (row) => [row]));
  const raw = el("kp-raw"); raw.replaceChildren();
  const rawRefs = item.scope ? contents.raw.filter((ref) =>
    ref.startsWith("raw/" + item.scope + "/")) : contents.raw;
  el("kp-scope-name").textContent = item.scope || "whole vault (older sandbox)";
  raw.append(table(["", "Raw document", "", ""], rawRefs, (row) => {
    const tick = document.createElement("input"); tick.type = "checkbox";
    tick.className = "kp-raw-tick"; tick.value = row; tick.setAttribute("aria-label", row);
    tick.addEventListener("change", kpRawCount);
    return [tick, row,
      kpButton("Preview", () => kpRun("Reading", () => kpShowFile(row))),
      kpButton("Plan ingest", () => kpRun("Planning ingest (this asks the model)",
        () => kpPlan(row)))];
  }));
  const folders = new Set();
  for (const ref of rawRefs) {
    const parts = ref.split("/").slice(0, -1);
    for (let n = 2; n <= parts.length; n++) folders.add(parts.slice(0, n).join("/"));
  }
  const pick = el("kp-raw-folder"); pick.replaceChildren();
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
  kpViewer(path + " \u2014 planned change", box);
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
    kpConvertWatching = null;  // it just ended: the new Raw appears in step 3
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

el("kp-raw-tick").addEventListener("click", () => {
  const folder = el("kp-raw-folder").value + "/";
  kpRawTick([...document.querySelectorAll("#kp-raw .kp-raw-tick")]
    .map((t) => t.value).filter((ref) => ref.startsWith(folder)));
});
el("kp-raw-clear").addEventListener("click", () => {
  for (const tick of document.querySelectorAll("#kp-raw .kp-raw-tick")) tick.checked = false;
  kpRawCount();
});
el("kp-reingest").addEventListener("click", () => kpRun("Starting the re-ingest", async () => {
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
  const parts = [pulled.copied.length + " new original(s) copied to drop (convert them in step 2)"];
  if (pulled.already_in_sandbox.length) {
    parts.push(pulled.already_in_sandbox.length + " already in this sandbox's drop");
  }
  if (pulled.too_large.length) parts.push(pulled.too_large.length + " too large to pull");
  if (pulled.already_ingested.length) {
    parts.push(pulled.already_ingested.length + " already ingested: their Raw ("
      + pulled.already_raw.length + " document(s)) is already in this sandbox, so they are "
      + "not pulled again. To try changed rules on them, re-ingest them in step 3");
  }
  await kpOpen(kpSandbox);
  const box = el("kp-pull-result"); box.replaceChildren(text(parts.join("; ") + ". "));
  if (pulled.already_raw.length) {
    box.append(kpButton("Tick them in step 3", () => {
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
    kpSandbox = null; el("kp-box").hidden = true; await loadKnowledge();
  });
});

const panels = {ask: null, installed: loadCapabilities,
  settings: loadSettings, schedules: loadSchedules, knowledge: loadKnowledge};

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
  if (name === "ask") { field.focus(); return; }
  try { await panels[name](); }
  catch (failure) { showBootError(failure); }
}

el("nav-capabilities").addEventListener("click", () => selectPrimaryTab("installed"));
el("nav-settings").addEventListener("click", () => selectPrimaryTab("settings"));
el("nav-schedules").addEventListener("click", () => selectPrimaryTab("schedules"));
el("nav-knowledge").addEventListener("click", () => selectPrimaryTab("knowledge"));

Promise.all([loadAbout(), loadAssets(), loadChat(), loadSlashCommands(), loadAvatars(), loadMcp()])
  .catch(showBootError);
field.focus();
</script>
</body>
</html>
"""
