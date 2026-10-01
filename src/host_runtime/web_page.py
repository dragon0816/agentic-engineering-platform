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
header {
  display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap;
  padding: 14px 16px; border-bottom: 1px solid var(--line); background: var(--panel);
}
header h1 { margin: 0; font-size: 16px; font-weight: 650; }
header .who { color: var(--dim); font-size: 13px; }
nav { display: flex; gap: 4px; padding: 10px 16px 0; flex-wrap: wrap; }
nav button {
  font: inherit; font-size: 14px; padding: 7px 14px; cursor: pointer; color: var(--dim);
  background: none; border: 1px solid transparent; border-radius: 8px 8px 0 0;
}
nav button:hover { color: var(--ink); }
nav button[aria-selected="true"] {
  color: var(--ink); background: var(--bg);
  border-color: var(--line); border-bottom-color: var(--bg); font-weight: 600;
}
main { padding: 0 16px 40px; border-top: 1px solid var(--line); margin-top: -1px; }
section { display: none; padding-top: 18px; max-width: 1240px; }
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
  margin: 6px 0 0; white-space: pre-wrap; word-break: break-word;
  font-family: var(--mono); font-size: 13px;
}
.said.bad { color: var(--bad); }
.waiting { color: var(--dim); font-style: italic; }
form.ask { display: flex; gap: 8px; margin: 12px 0 0; }
form.ask textarea {
  flex: 1; font: inherit; padding: 9px 12px; color: var(--ink);
  background: var(--bg); border: 1px solid var(--line); border-radius: 8px;
  min-height: 76px;
}
form.ask textarea:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
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
.conversation-bar { display: flex; gap: 8px; align-items: center; margin: 0 0 10px; }
.conversation-bar select { flex: 1; }

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
.cap-layout { display: grid; grid-template-columns: minmax(260px, .85fr) minmax(360px, 1.4fr);
  min-height: 360px; border: 1px solid var(--line); border-radius: 10px;
  overflow: hidden; margin-top: 12px; }
.cap-browser { border-right: 1px solid var(--line); background: var(--bg); }
.cap-search { padding: 12px; border-bottom: 1px solid var(--line); }
.cap-search input, .market-tools input, .market-tools select { width: 100%; min-height: 44px;
  padding: 9px 11px; color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; font: inherit; }
.cap-list { max-height: 430px; overflow-y: auto; }
.cap-item { display: block; width: 100%; min-height: 58px; padding: 10px 12px;
  text-align: left; color: var(--ink); background: transparent; border: 0;
  border-bottom: 1px solid var(--line); cursor: pointer; font: inherit; }
.cap-item:hover { background: var(--panel); }
.cap-item[aria-selected="true"] { background: var(--selected); }
.cap-item strong, .cap-item small { display: block; }
.cap-item small { color: var(--dim); margin-top: 2px; }
.cap-detail { padding: 20px; background: var(--panel); }
.cap-detail h3 { margin: 0 0 4px; font-size: 18px; }
.identity { color: var(--dim); font: 12px var(--mono); overflow-wrap: anywhere; }
.detail-description { margin: 16px 0; }
.meta-grid { display: grid; grid-template-columns: max-content 1fr; gap: 7px 14px;
  margin: 16px 0; font-size: 13px; }
.meta-grid dt { color: var(--dim); }
.meta-grid dd { margin: 0; overflow-wrap: anywhere; }
.inline-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.action-box { margin-top: 16px; padding: 14px; border: 1px solid var(--line);
  border-radius: 8px; background: var(--bg); }
.action-box label { display: block; margin: 9px 0 4px; font-size: 12px; color: var(--dim); }
.market { margin-top: 28px; padding-top: 22px; border-top: 1px solid var(--line); }
.market-tools { display: grid; grid-template-columns: minmax(220px, 1fr) 170px 170px auto auto;
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
.badges { display: flex; flex-wrap: wrap; gap: 5px; margin: 9px 0; }
.tag.warn { color: var(--warn); border-color: var(--warn); }
.section-status { min-height: 22px; color: var(--dim); font-size: 13px; }
.section-status.bad { color: var(--bad); }
@media (max-width: 1000px) {
  .market-tools { grid-template-columns: minmax(220px, 1fr) minmax(150px, .55fr); }
}
@media (max-width: 760px) {
  header { gap: 6px; }
  th, td { padding: 7px 6px; }
  .cap-layout { grid-template-columns: 1fr; }
  .cap-browser { border-right: 0; border-bottom: 1px solid var(--line); }
  .cap-list { max-height: 260px; }
  .market-tools { grid-template-columns: 1fr; }
  .workspace-head { align-items: start; flex-direction: column; }
}
</style>
</head>
<body>
<header>
  <div><h1 id="agent-name">Agent</h1><span class="note" id="agent-introduction"></span></div>
  <span class="who" id="who">reading this machine&hellip;</span>
</header>
<div id="boot-error" class="boot-error" role="alert" hidden></div>
<nav>
  <button id="tab-ask" aria-selected="true">Ask</button>
  <button id="tab-feedback" aria-selected="false">Improve</button>
  <button id="tab-installed" aria-selected="false">Capabilities</button>
  <button id="tab-settings" aria-selected="false">Settings</button>
</nav>
<main>
  <section id="panel-ask" data-open>
    <div class="grid" id="readiness">
      <div class="status-card">Reading Agent readiness&hellip;</div>
    </div>
    <div class="conversation-bar">
      <select id="conversation" aria-label="Conversation"></select>
      <button class="go" id="new-conversation" type="button">New</button>
    </div>
    <div id="log"></div>
    <div id="command-palette" class="command-menu" role="listbox" hidden></div>
    <form class="ask" id="ask">
      <textarea id="message" rows="3" autocomplete="off" spellcheck="true"
        placeholder="Ask naturally, or type / to choose a command"></textarea>
      <button class="go" id="send" type="submit" disabled>Send</button>
    </form>
    <p class="hint">This is the Agent on this computer &mdash; the same one the
      command line and Telegram reach, with the same permissions and the same
      refusals. Nothing is written unless the command says so. One request runs
      at a time.</p>
  </section>

  <section id="panel-feedback">
    <h2>Turn this conversation into a reviewable draft</h2>
    <p class="note">Capture a problem with one exact installed version, or propose a new
      Skill or Workflow. The Agent copies recent conversation evidence into a local draft.
      It does not publish, install, execute or open an external issue.</p>
    <div class="card settings">
      <form id="contribution-form">
        <label for="contribution-kind">Draft type</label>
        <select id="contribution-kind">
          <option value="improvement">Improve an installed capability</option>
          <option value="new_capability">Propose a new Skill or Workflow</option>
        </select>
        <div id="improvement-fields">
          <label for="contribution-target">Exact installed version</label>
          <select id="contribution-target"></select>
        </div>
        <div id="candidate-fields" hidden>
          <div class="two">
            <div><label for="candidate-kind">Capability type</label>
              <select id="candidate-kind"><option value="skill">Skill</option>
                <option value="workflow">Workflow</option></select></div>
            <div><label for="candidate-name">Proposed name</label>
              <input id="candidate-name" placeholder="team-capability-name"></div>
          </div>
        </div>
        <label for="contribution-summary">Problem or opportunity</label>
        <input id="contribution-summary" required>
        <label for="contribution-expected">Expected behavior</label>
        <textarea id="contribution-expected" required></textarea>
        <label for="contribution-actual">Current behavior or gap</label>
        <textarea id="contribution-actual" required></textarea>
        <label for="contribution-acceptance">Acceptance criteria (one per line)</label>
        <textarea id="contribution-acceptance" required></textarea>
        <p><button class="go" id="contribution-save" type="submit">Save draft</button></p>
        <pre id="contribution-result" class="note">No draft saved yet.</pre>
      </form>
    </div>
    <h2>Local drafts awaiting review</h2>
    <p class="note">Business approval and technical policy remain separate and pending.
      A later governed contribution path may validate and publish a new version.</p>
    <div class="card"><div id="contribution-drafts" class="empty">reading&hellip;</div></div>
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
        <div class="two">
          <div><label for="model-secret">SecretRef name (optional)</label>
            <input id="model-secret" placeholder="llm_gateway_token"></div>
          <div><label for="model-environment">Environment variable name (optional)</label>
            <input id="model-environment" placeholder="AEP_LLM_TOKEN"></div>
        </div>
        <p class="note">If the Gateway requires a token, set the token value in the named
          Windows environment variable before restarting the Agent.</p>
        <p><button class="go" id="model-save" type="submit">Save model settings</button></p>
        <pre id="model-result" class="note">Reading current settings&hellip;</pre>
      </form>
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
          <label for="workflow-arguments">JSON arguments</label>
          <textarea id="workflow-arguments" spellcheck="false">{}</textarea>
          <p><button class="go" id="workflow-run" type="button" disabled>Run Workflow</button></p>
          <pre id="workflow-result" class="section-status">Nothing has run.</pre>
        </div>
        <div id="knowledge-action" class="action-box" hidden>
          <strong>Ask this Knowledge source</strong>
          <p class="note" id="knowledge-domain">No installed Knowledge.</p>
          <label for="knowledge-question">Question</label>
          <textarea id="knowledge-question" spellcheck="true"></textarea>
          <p><button class="go" id="knowledge-ask" type="button" disabled>Ask Knowledge</button></p>
          <pre id="knowledge-result" class="section-status">Nothing has been asked.</pre>
          <div id="knowledge-citations" class="empty">No citations.</div>
        </div>
      </article>
    </div>
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
        <div><h2>Shared Platform</h2><p class="note" id="platform-note">reading&hellip;</p></div>
      </div>
      <div class="market-tools">
        <input id="market-search" type="search" aria-label="Search shared platform"
               placeholder="Search shared capabilities">
        <select id="market-kind" aria-label="Filter by type">
          <option value="all">All types</option></select>
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
    throw new Error(failed.error || failed.code || ("the host answered " + reply.status));
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

// -- Ask ------------------------------------------------------------------

const log = el("log"), form = el("ask"), field = el("message"), send = el("send");
let activeConversation = "";

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
      said.textContent = replied.text;
    }
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
  const selector = el("conversation"); selector.replaceChildren();
  for (const item of listed.conversations) {
    const option = document.createElement("option"); option.value = item.session_id;
    option.textContent = item.title; selector.append(option);
  }
  activeConversation = selectId || listed.conversations[0].session_id;
  selector.value = activeConversation;
  if (!listed.selected || listed.selected.session_id !== activeConversation) {
    listed = await call("/api/conversations?session_id="
      + encodeURIComponent(activeConversation));
  }
  renderConversation(listed.selected);
  send.disabled = false;
}

el("conversation").addEventListener("change", async () => {
  await loadConversations(el("conversation").value);
});
el("new-conversation").addEventListener("click", async () => {
  const created = await call("/api/conversations", {});
  await loadConversations(created.conversation.session_id); field.focus();
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
    said.textContent = answer.answer;
    await loadConversations(activeConversation);
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

async function loadReadiness() {
  const ready = await call("/api/readiness");
  const cards = [];
  const natural = document.createElement("div"); natural.className = "status-card";
  const naturalTitle = document.createElement("strong");
  naturalTitle.append(text(ready.natural_language.status === "ready"
    ? "Natural language ready" : "Natural language needs setup"));
  natural.append(naturalTitle, text(ready.natural_language.action)); cards.push(natural);
  const installed = document.createElement("div"); installed.className = "status-card";
  const installedTitle = document.createElement("strong");
  installedTitle.append(text("Installed here"));
  installed.append(installedTitle, text(ready.installed.skills + " Skills · "
    + ready.installed.workflows + " Workflows · " + ready.installed.knowledge + " Knowledge"));
  cards.push(installed);
  const shared = document.createElement("div"); shared.className = "status-card";
  const sharedTitle = document.createElement("strong"); sharedTitle.append(text(
    ready.shared_platform.configured
      ? "Shared platform connected" : "Shared platform not configured"));
  shared.append(sharedTitle, text(ready.shared_platform.action)); cards.push(shared);
  el("readiness").replaceChildren(...cards);
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
  el("knowledge-ask").disabled = assets.knowledge.length === 0;
  showKnowledgeDomain();
  installedAssets = Object.assign({applications: []}, assets);
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
      ["Commands", item.commands.map((command) => command.invocation.trim()).join(", ")]]);
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
      ["Capabilities", item.capabilities.join(", ")]]);
    el("workflow-target").value = JSON.stringify({namespace: item.namespace, name: item.name,
      version: item.version});
    showWorkflowContract(); el("workflow-action").hidden = false;
  } else if (kind === "knowledge") {
    appendMeta(content, [["Domain", item.domain], ["Owner", item.owner],
      ["Visibility", item.visibility]]);
    el("knowledge-target").value = JSON.stringify({namespace: item.namespace, name: item.name,
      version: item.version});
    showKnowledgeDomain(); el("knowledge-action").hidden = false;
  } else if (kind === "extensions") {
    badges.append(tag(item.state === "active", item.state, item.state));
    appendMeta(content, [["Runtime state", item.state + (item.code ? " (" + item.code + ")" : "")],
      ["Capabilities", item.capabilities.join(", ")], ["Publisher key", item.publisher_key_id],
      ["Activation gate", item.activation_gate]]);
    const gate = document.createElement("p"); gate.className = "note";
    gate.append(text("Activation remains a device-administrator action. "
      + "This page does not bypass approval or technical policy."));
    content.append(gate);
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

function showContributionFields() {
  const candidate = el("contribution-kind").value === "new_capability";
  el("improvement-fields").hidden = candidate;
  el("candidate-fields").hidden = !candidate;
  el("contribution-save").disabled = !candidate && !el("contribution-target").value;
}

el("contribution-kind").addEventListener("change", showContributionFields);

function renderContributionDrafts(drafts) {
  el("contribution-drafts").replaceChildren(table(
    ["Draft", "Type", "Target / proposal", "Review", "Summary"], drafts,
    (draft) => {
      const subject = draft.target
        ? draft.target.namespace + "/" + draft.target.name + "@" + draft.target.version
        : draft.namespace + "/" + draft.proposed_name;
      return [draft.draft_id, draft.request_kind, draft.asset_kind + " " + subject,
              "business: " + draft.business_approval.status
                + " · technical: " + draft.technical_policy.status,
              draft.summary];
    }));
}

async function loadContributions() {
  const assets = await call("/api/assets");
  const target = el("contribution-target"); target.replaceChildren();
  for (const kind of ["skills", "workflows", "knowledge"]) {
    for (const asset of assets[kind]) {
      const option = document.createElement("option");
      option.value = JSON.stringify({namespace: asset.namespace, name: asset.name,
        version: asset.version});
      option.textContent = kind.slice(0, -1) + " · " + asset.namespace + "/" + asset.name
        + "@" + asset.version;
      target.append(option);
    }
  }
  target.disabled = target.options.length === 0;
  const listed = await call("/api/contributions");
  renderContributionDrafts(listed.drafts);
  showContributionFields();
}

el("contribution-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const kind = el("contribution-kind").value;
  const criteria = el("contribution-acceptance").value.split("\n")
    .map((item) => item.trim()).filter(Boolean);
  const body = {
    session_id: activeConversation,
    request_kind: kind,
    summary: el("contribution-summary").value.trim(),
    expected_behavior: el("contribution-expected").value.trim(),
    actual_behavior: el("contribution-actual").value.trim(),
    acceptance_criteria: criteria,
  };
  if (kind === "improvement") {
    if (!el("contribution-target").value) return;
    body.target = JSON.parse(el("contribution-target").value);
  } else {
    body.candidate_kind = el("candidate-kind").value;
    body.proposed_name = el("candidate-name").value.trim();
  }
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
  el("model-secret").value = model.credential_secret || "";
  el("model-environment").value = model.credential_environment || "";
  el("model-save").disabled = !settings.writable;
  el("model-result").textContent = model.configured
    ? "Configured: " + model.alias + " → " + model.model + " at " + model.base_url
      + (model.credential_secret ? "\nCredential value present: " + model.credential_present : "")
    : (settings.writable
      ? "No routing model is configured." : "Settings are read-only in this launch mode.");
}

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
  };
  if (secret || environment) {
    body.credential_secret = secret; body.credential_environment = environment;
  }
  try {
    const saved = await call("/api/settings/model", body);
    result.textContent = "Saved. Restart the Agent to use this model configuration."
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
}

el("workflow-target").addEventListener("change", showWorkflowContract);
el("workflow-run").addEventListener("click", async () => {
  const button = el("workflow-run"), result = el("workflow-result");
  let argumentsValue;
  try {
    argumentsValue = JSON.parse(el("workflow-arguments").value);
    if (!argumentsValue || Array.isArray(argumentsValue) || typeof argumentsValue !== "object") {
      throw new Error("arguments must be one JSON object");
    }
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
    const answered = await call("/api/knowledge/ask", {
      asset: JSON.parse(chosen), question: question,
    });
    const outcome = answered.outcome;
    result.textContent = "trace " + outcome.trace.trace_id + " | request "
      + outcome.trace.request_id + "\n\n" + answered.answer;
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

function renderMarketCards() {
  const query = el("market-search").value.trim().toLowerCase();
  const kind = el("market-kind").value;
  const status = el("market-status").value;
  const rows = sharedPlatform.catalog.filter((item) => {
    const matchesQuery = [item.name, item.namespace, item.description, item.owner, item.kind]
      .filter(Boolean).join(" ").toLowerCase().includes(query);
    const matchesKind = kind === "all" || item.kind === kind;
    const matchesStatus = status === "all"
      || (status === "installed" && item.installed)
      || (status === "authorized" && item.authorized)
      || (status === "available" && !item.authorized && !item.installed);
    return matchesQuery && matchesKind && matchesStatus;
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
    const description = document.createElement("p");
    description.append(text(item.description || "No description supplied."));
    const owner = document.createElement("p");
    owner.append(text("Owner: " + item.owner + " · " + item.visibility));
    const compatible = document.createElement("p");
    const compatibility = [item.runtime].concat(item.platforms).filter(Boolean).join(", ");
    compatible.append(text("Compatibility: " + (compatibility || "not declared")));
    card.append(title, identity, badges, description, owner, compatible);
    return card;
  });
  if (cards.length) el("catalog").replaceChildren(...cards);
  else {
    const empty = document.createElement("div"); empty.className = "empty";
    empty.append(text(sharedPlatform.configured
      ? "No shared capabilities match these filters. Applications are listed in Marketplace."
      : "Configure a Shared Platform connection to discover team capabilities."));
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
  const kinds = [...new Set(platform.catalog.map((item) => item.kind))].sort();
  const kindSelect = el("market-kind"), previousKind = kindSelect.value;
  kindSelect.replaceChildren();
  const all = document.createElement("option"); all.value = "all"; all.textContent = "All types";
  kindSelect.append(all);
  for (const value of kinds) {
    const option = document.createElement("option"); option.value = value;
    option.textContent = value.charAt(0).toUpperCase() + value.slice(1); kindSelect.append(option);
  }
  kindSelect.value = kinds.includes(previousKind) ? previousKind : "all";
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
el("market-kind").addEventListener("change", renderMarketCards);
el("market-status").addEventListener("change", renderMarketCards);

el("platform-sync").addEventListener("click", async () => {
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
});

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

// -- Tabs -----------------------------------------------------------------

const panels = {ask: null, feedback: loadContributions, installed: loadCapabilities,
  settings: loadSettings};

function showBootError(failure) {
  const banner = el("boot-error"); banner.hidden = false;
  banner.textContent = "Agent Web could not finish loading: " + failure.message;
}

async function selectPrimaryTab(name) {
  for (const other of Object.keys(panels)) {
    el("tab-" + other).setAttribute("aria-selected", String(other === name));
    el("panel-" + other).toggleAttribute("data-open", other === name);
  }
  if (name === "ask") { field.focus(); return; }
  try { await panels[name](); }
  catch (failure) { showBootError(failure); }
}

for (const name of Object.keys(panels)) {
  el("tab-" + name).addEventListener("click", () => selectPrimaryTab(name));
}

Promise.all([loadAbout(), loadReadiness(), loadAssets(), loadConversations(), loadSlashCommands()])
  .catch(showBootError);
field.focus();
</script>
</body>
</html>
"""
