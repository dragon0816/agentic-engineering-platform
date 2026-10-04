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
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #15181c; --panel: #1d2127; --line: #2c323a; --ink: #e6e9ee;
    --dim: #97a0ac; --accent: #74a9e8; --good: #6cc48d; --bad: #e8827c;
    --accent-soft: #1d3046; --selected: #243e5b; --warn: #e6b75a;
  }
}
:root[data-theme="dark"] {
  --bg: #15181c; --panel: #1d2127; --line: #2c323a; --ink: #e6e9ee;
  --dim: #97a0ac; --accent: #74a9e8; --good: #6cc48d; --bad: #e8827c;
  --accent-soft: #1d3046; --selected: #243e5b; --warn: #e6b75a;
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
.turn { margin: 0 0 14px; }
.turn:last-child { margin-bottom: 0; }
.asked { font-weight: 600; color: var(--accent); word-break: break-word; }
.said {
  margin: 8px 0 0; line-height: 1.65; overflow-wrap: anywhere;
}
.said.bad { color: var(--bad); }
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
    <h1 id="agent-name">Agent</h1>
    <span class="note" id="agent-introduction"></span>
  </div>
  <div class="side-actions">
    <button id="new-conversation" type="button">New session</button>
    <button id="nav-capabilities" type="button">Capabilities</button>
    <button id="nav-settings" type="button">Settings</button>
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
    <form class="ask" id="ask">
      <textarea id="message" rows="3" autocomplete="off" spellcheck="true"
        placeholder="Ask naturally, or type / to choose a command"></textarea>
      <div class="composer-footer">
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
        <label for="model-name">Model name served by the Gateway</label>
        <input id="model-name" placeholder="Ask your Gateway administrator for this name" required>
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
    <details class="card settings" style="margin-top: 14px">
      <summary><strong>Create a Skill or Workflow draft</strong></summary>
      <p class="note">The current conversation is copied as evidence. The draft remains local,
        unpublished and pending both business and technical review.</p>
      <form id="contribution-form">
        <div class="two">
          <div><label for="candidate-kind">Capability type</label>
            <select id="candidate-kind"><option value="skill">Skill</option>
              <option value="workflow">Workflow</option></select></div>
          <div><label for="candidate-name">Proposed name</label>
            <input id="candidate-name" placeholder="team-capability-name" required></div>
        </div>
        <label for="contribution-summary">Purpose</label>
        <input id="contribution-summary" required>
        <label for="contribution-expected">Expected behavior</label>
        <textarea id="contribution-expected" required></textarea>
        <label for="contribution-actual">Current gap</label>
        <textarea id="contribution-actual" required></textarea>
        <label for="contribution-acceptance">Acceptance criteria (one per line)</label>
        <textarea id="contribution-acceptance" required></textarea>
        <p><button class="go" id="contribution-save" type="submit">Save candidate draft</button></p>
        <pre id="contribution-result" class="note">No draft saved yet.</pre>
      </form>
      <h3>Local drafts awaiting review</h3>
      <div id="contribution-drafts" class="empty">reading&hellip;</div>
    </details>
    <div class="card settings" style="margin-top: 14px">
      <h2>Agent profile</h2>
      <p class="note">Profiles narrow the Agent's Skills, Knowledge, capabilities and
        model requirements. Restart after activation.</p>
      <div id="profiles" class="empty">reading&hellip;</div>
    </div>
    <div hidden aria-hidden="true">
      <select id="workflow-target" disabled></select>
      <select id="knowledge-target" disabled></select>
    </div>
    <h2>Recent runs</h2>
    <div class="card"><div id="runs" class="empty">reading&hellip;</div></div>

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

function turn(asked) {
  const block = document.createElement("div");
  block.className = "turn";
  const line = document.createElement("div");
  line.className = "asked"; line.append(text("> " + asked));
  const said = document.createElement("div");
  said.className = "said waiting"; said.append(text("working\u2026"));
  block.append(line, said);
  log.append(block);
  log.scrollTop = log.scrollHeight;
  return said;
}

function renderConversation(record) {
  log.replaceChildren();
  if (!record) return;
  for (let index = 0; index < record.messages.length; index += 2) {
    const asked = record.messages[index];
    const replied = record.messages[index + 1];
    const said = turn(asked.text);
    if (replied) {
      said.className = "said" + (replied.status === "failed" ? " bad" : "");
      renderAnswer(said, replied.text);
    }
  }
}

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
    detail.append(text(item.messages + " messages · " + item.backend));
    button.append(title, detail);
    button.addEventListener("click", async () => {
      selectPrimaryTab("ask");
      try { await loadChat(item.session_id); field.focus(); }
      catch (failure) { showBootError(failure); }
    });
    return button;
  });
  if (buttons.length) el("session-list").replaceChildren(...buttons);
  else {
    const empty = document.createElement("div"); empty.className = "empty";
    empty.append(text("No sessions match this search."));
    el("session-list").replaceChildren(empty);
  }
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const asked = field.value.trim();
  if (!asked) return;
  field.value = "";
  el("command-palette").hidden = true;
  field.disabled = send.disabled = true;
  const said = turn(asked);
  try {
    const completed = await call("/api/conversations/turn", {
      session_id: activeConversation, message: asked,
    });
    const answer = completed.answer;
    said.className = "said" + (answer.ok ? "" : " bad");
    renderAnswer(said, answer.answer);
    await loadConversations(activeConversation);
    if (answer.backend && answer.backend.code === "backend_authentication_failed") {
      await loadBackends();
    }
  } catch (failure) {
    said.className = "said bad";
    said.textContent = "The request did not finish: " + failure.message;
  }
  field.disabled = send.disabled = false;
  field.focus();
  log.scrollTop = log.scrollHeight;
});

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

async function loadAssets() {
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

// -- Governed contribution drafts ---------------------------------------

function renderContributionDrafts(drafts) {
  el("contribution-drafts").replaceChildren(table(
    ["Draft", "Type", "Target / proposal", "Review", "Summary"], drafts,
    (draft) => {
      const subject = draft.target
        ? draft.target.namespace + "/" + draft.target.name + "@" + draft.target.version
        : (draft.proposed_name ? draft.namespace + "/" + draft.proposed_name : draft.namespace);
      return [draft.draft_id, draft.request_kind, draft.asset_kind + " " + subject,
              "business: " + draft.business_approval.status
                + " · technical: " + draft.technical_policy.status,
              draft.summary];
    }));
}

async function loadContributions() {
  const listed = await call("/api/contributions");
  renderContributionDrafts(listed.drafts);
}

el("contribution-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const criteria = el("contribution-acceptance").value.split("\n")
    .map((item) => item.trim()).filter(Boolean);
  const body = {
    session_id: activeConversation,
    request_kind: "new_capability",
    summary: el("contribution-summary").value.trim(),
    expected_behavior: el("contribution-expected").value.trim(),
    actual_behavior: el("contribution-actual").value.trim(),
    acceptance_criteria: criteria,
  };
  body.candidate_kind = el("candidate-kind").value;
  body.proposed_name = el("candidate-name").value.trim();
  const button = el("contribution-save"), result = el("contribution-result");
  button.disabled = true; result.textContent = "Saving a local governed draft…";
  try {
    const saved = await call("/api/contributions", body);
    result.textContent = "Saved " + saved.draft.draft_id
      + ". It remains a local draft awaiting business and technical review.";
    await loadContributions();
  } catch (failure) {
    result.textContent = "Draft was not saved: " + failure.message;
  } finally { button.disabled = false; }
});

async function loadSettings() {
  const settings = await call("/api/settings"), model = settings.model,
    persona = settings.persona;
  el("persona-name").value = persona.name;
  el("persona-introduction").value = persona.introduction;
  el("persona-soul").value = persona.soul;
  el("persona-result").textContent =
    "Saved locally. Changes apply to the next natural-language turn.";
  el("model-provider").value = model.provider || "openai_compatible";
  el("model-alias").value = model.alias || "company";
  el("model-base-url").value = model.base_url || ["http:", "", "127.0.0.1:4000/v1"].join("/");
  el("model-name").value = model.model || "";
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
  const container = el("workflow-fields"); container.replaceChildren();
  if (!typed) return;
  for (const field of workflow.parameters.fields) {
    const row = document.createElement("div"); row.className = "workflow-field";
    const id = "workflow-field-" + field.name;
    const label = document.createElement("label"); label.htmlFor = id;
    label.append(text(field.label + (field.required ? " *" : "")));
    const input = field.kind === "select" ? document.createElement("select")
      : document.createElement("input");
    input.id = id; input.dataset.name = field.name; input.dataset.kind = field.kind;
    if (field.kind === "select") {
      const empty = document.createElement("option"); empty.value = "";
      empty.append(text("Select " + field.label)); input.append(empty);
      for (const value of field.options) {
        const option = document.createElement("option"); option.value = value;
        option.append(text(value)); input.append(option);
      }
    } else {
      input.type = field.kind === "integer" ? "number"
        : field.kind === "date" ? "date"
        : field.kind === "boolean" ? "checkbox" : "text";
    }
    if (field.kind === "integer") {
      input.step = "1";
      if (field.minimum !== null) input.min = field.minimum;
      if (field.maximum !== null) input.max = field.maximum;
    }
    input.required = field.required;
    input.setAttribute("aria-describedby", id + "-help " + id + "-error");
    const help = document.createElement("p"); help.id = id + "-help";
    help.className = "hint"; help.append(text(field.description || ""));
    const error = document.createElement("p"); error.id = id + "-error";
    error.className = "field-error"; error.setAttribute("aria-live", "polite");
    input.addEventListener("input", () => {
      error.textContent = ""; input.removeAttribute("aria-invalid");
    });
    row.append(label, input, help, error); container.append(row);
  }
}

function workflowArguments() {
  if (el("workflow-fields").hidden) {
    const value = JSON.parse(el("workflow-arguments").value);
    if (!value || Array.isArray(value) || typeof value !== "object") {
      throw new Error("arguments must be one JSON object");
    }
    return value;
  }
  const value = {};
  for (const input of el("workflow-fields").querySelectorAll("input, select")) {
    const name = input.dataset.name, kind = input.dataset.kind;
    const raw = kind === "boolean" ? input.checked : input.value.trim();
    const invalid = kind === "integer" && raw !== ""
      && (!/^-?\d+$/.test(raw) || !Number.isSafeInteger(Number(raw)));
    if ((input.required && raw === "") || invalid || !input.checkValidity()) {
      const message = invalid ? "Enter a whole number."
        : input.validationMessage || "This field is required.";
      el(input.id + "-error").textContent = message;
      input.setAttribute("aria-invalid", "true"); input.focus();
      throw new Error(name + ": " + message);
    }
    if (kind !== "boolean" && raw === "") continue;
    value[name] = kind === "integer" ? Number(raw) : raw;
  }
  return value;
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
    await Promise.all([loadAssets(), loadPlatform(), loadContributions()]);
  } finally {
    refresh.disabled = false; refresh.removeAttribute("aria-busy");
    refresh.textContent = "Refresh status";
  }
}

el("cap-refresh").addEventListener("click", () => {
  loadCapabilities().catch(showBootError);
});

// -- Workspace navigation -------------------------------------------------

const panels = {ask: null, installed: loadCapabilities,
  settings: loadSettings};

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
  if (name === "ask") { field.focus(); return; }
  try { await panels[name](); }
  catch (failure) { showBootError(failure); }
}

el("nav-capabilities").addEventListener("click", () => selectPrimaryTab("installed"));
el("nav-settings").addEventListener("click", () => selectPrimaryTab("settings"));

Promise.all([loadAbout(), loadAssets(), loadChat(), loadSlashCommands()])
  .catch(showBootError);
field.focus();
</script>
</body>
</html>
"""
