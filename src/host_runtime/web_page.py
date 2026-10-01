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

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent</title>
<style>
:root {
  --bg: #ffffff; --panel: #f6f7f9; --line: #e2e5ea; --ink: #1c1f24;
  --dim: #666d78; --accent: #2f6db5; --good: #2e7d4f; --bad: #b3352f;
  --mono: ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #15181c; --panel: #1d2127; --line: #2c323a; --ink: #e6e9ee;
    --dim: #97a0ac; --accent: #74a9e8; --good: #6cc48d; --bad: #e8827c;
  }
}
:root[data-theme="dark"] {
  --bg: #15181c; --panel: #1d2127; --line: #2c323a; --ink: #e6e9ee;
  --dim: #97a0ac; --accent: #74a9e8; --good: #6cc48d; --bad: #e8827c;
}
* { box-sizing: border-box; }
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
section { display: none; padding-top: 18px; max-width: 1100px; }
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
form.ask input {
  flex: 1; font: inherit; padding: 9px 12px; color: var(--ink);
  background: var(--bg); border: 1px solid var(--line); border-radius: 8px;
}
form.ask input:focus { outline: 2px solid var(--accent); outline-offset: -1px; }
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
.settings input, .settings select { width: 100%; font: 13px var(--mono); padding: 9px 10px;
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
@media (max-width: 620px) {
  header { gap: 6px; }
  th, td { padding: 7px 6px; }
}
</style>
</head>
<body>
<header>
  <h1>Agent</h1>
  <span class="who" id="who">reading this machine&hellip;</span>
</header>
<nav>
  <button id="tab-ask" aria-selected="true">Ask</button>
  <button id="tab-installed" aria-selected="false">Installed here</button>
  <button id="tab-platform" aria-selected="false">Shared platform</button>
  <button id="tab-settings" aria-selected="false">Settings</button>
</nav>
<main>
  <section id="panel-ask" data-open>
    <div class="grid" id="readiness">
      <div class="status-card">Reading Agent readiness&hellip;</div>
    </div>
    <h2>What can I ask?</h2>
    <p class="note">These commands come from Skills installed on this computer.
      Choose one to fill the request, then add the required details.</p>
    <div class="quick" id="command-hints"><span class="empty">reading&hellip;</span></div>
    <div class="conversation-bar">
      <select id="conversation" aria-label="Conversation"></select>
      <button class="go" id="new-conversation" type="button">New</button>
    </div>
    <div id="log"></div>
    <form class="ask" id="ask">
      <input id="message" autocomplete="off" spellcheck="false"
             placeholder="a command, such as  weekly.preview 2026_39W">
      <button class="go" id="send" type="submit" disabled>Send</button>
    </form>
    <p class="hint">This is the Agent on this computer &mdash; the same one the
      command line and Telegram reach, with the same permissions and the same
      refusals. Nothing is written unless the command says so. One request runs
      at a time.</p>
  </section>

  <section id="panel-settings">
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
    <h2>Agent profile</h2>
    <p class="note">Choose one exact installed profile. Restart the Agent to apply its
      narrower Skills, Knowledge, capability and model requirements.</p>
    <div class="card"><div id="profiles" class="empty">reading&hellip;</div></div>
    <h2>Skills</h2>
    <p class="note">What can be asked for by name on this machine.</p>
    <div class="card"><div id="skills" class="empty">reading&hellip;</div></div>
    <h2>Workflows</h2>
    <p class="note">What a Skill&rsquo;s command runs.</p>
    <div class="card"><div id="workflows" class="empty">reading&hellip;</div></div>
    <h2>Run an installed Workflow</h2>
    <p class="note">Choose an exact installed version. Arguments must match the shown input
      contract. Execution still passes through Agent admission and Bridge policy.</p>
    <div class="card" style="padding: 12px">
      <label for="workflow-target">Workflow</label>
      <select id="workflow-target" disabled></select>
      <p class="note" id="workflow-contract">No installed Workflow.</p>
      <label for="workflow-arguments">JSON arguments</label>
      <textarea id="workflow-arguments" spellcheck="false">{}</textarea>
      <p><button class="go" id="workflow-run" type="button" disabled>Run Workflow</button></p>
      <pre id="workflow-result" class="note">Nothing has run.</pre>
    </div>
    <h2>Ask installed Knowledge</h2>
    <p class="note">Choose an exact local Knowledge version. Answers must cite the
      immutable Raw evidence retained by that version.</p>
    <div class="card" style="padding: 12px">
      <label for="knowledge-target">Knowledge</label>
      <select id="knowledge-target" disabled></select>
      <p class="note" id="knowledge-domain">No installed Knowledge.</p>
      <label for="knowledge-question">Question</label>
      <textarea id="knowledge-question" spellcheck="true"></textarea>
      <p><button class="go" id="knowledge-ask" type="button" disabled>Ask Knowledge</button></p>
      <pre id="knowledge-result" class="note">Nothing has been asked.</pre>
      <div id="knowledge-citations" class="empty">No citations.</div>
    </div>
    <h2>Bridge Extensions</h2>
    <p class="note">Locally staged extension versions and their last runtime state.
      Activation is a separate device-administrator action and still requires
      technical policy approval.</p>
    <div class="card"><div id="extensions" class="empty">reading&hellip;</div></div>
    <h2>Recent runs</h2>
    <div class="card"><div id="runs" class="empty">reading&hellip;</div></div>
  </section>

  <section id="panel-platform">
    <h2>Published to your team</h2>
    <p class="note" id="platform-note">reading&hellip;</p>
    <p><a id="member-portal" hidden target="_blank" rel="noopener noreferrer">
      Open shared marketplace (Agent Add-ons and Applications)</a></p>
    <p><button class="go" id="platform-sync" type="button" disabled>
      Synchronize selected assets</button></p>
    <p class="note" id="platform-sync-result">
      Synchronization runs only when you press the button.</p>
    <div class="card"><div id="catalog" class="empty">reading&hellip;</div></div>
    <h2>Authorized on this Bridge</h2>
    <p class="note">Selections synchronized to this machine. A selection does not bypass
      capability policy.</p>
    <div class="card"><div id="decisions" class="empty">reading&hellip;</div></div>
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
    throw new Error(failed.error || ("the host answered " + reply.status));
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
  said.className = "said waiting"; said.append(text("working\\u2026"));
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
  const where = [];
  where.push("as " + about.actor);
  where.push("on " + about.bridge_id);
  if (about.namespace) where.push("namespace " + about.namespace);
  el("who").textContent = where.join(" \\u00b7 ");
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

function renderCommandHints(assets) {
  const buttons = [];
  for (const skill of assets.skills) for (const command of skill.commands) {
    const button = document.createElement("button"); button.type = "button";
    button.textContent = command.invocation + "…";
    button.title = command.kind + " " + command.target;
    button.addEventListener("click", () => { field.value = command.invocation; field.focus(); });
    buttons.push(button);
  }
  if (!buttons.length) {
    el("command-hints").replaceChildren(text("No Skill commands are installed yet."));
  } else el("command-hints").replaceChildren(...buttons);
}

async function loadAssets() {
  const assets = await call("/api/assets");
  renderCommandHints(assets);
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
  el("skills").replaceChildren(table(
    ["Alias", "Commands", "Asset", "What it is"], assets.skills,
    (s) => [s.alias, s.commands.map((command) => command.invocation.trim()).join(", ") || "\\u2014",
            s.namespace + "/" + s.name + "@" + s.version, s.description]));
  el("workflows").replaceChildren(table(
    ["Asset", "Steps", "What it does"], assets.workflows,
    (w) => [w.namespace + "/" + w.name + "@" + w.version, w.steps, w.description]));
  el("extensions").replaceChildren(table(
    ["Extension", "State", "Capabilities", "Activation gate"], assets.extensions,
    (x) => [x.namespace + "/" + x.name + "@" + x.version,
            x.state + (x.code ? " (" + x.code + ")" : ""),
            x.capabilities.join(", ") || "\u2014", x.activation_gate]));
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
}

async function loadSettings() {
  const settings = await call("/api/settings"), model = settings.model;
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
  result.textContent = "Workflow is running\\u2026";
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
    result.textContent = identifiers.join(" | ") + "\\n\\n" + launched.answer;
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

function renderPlatform(platform) {
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
  el("catalog").replaceChildren(table(
    ["Type", "Asset", "Owner", "Visibility", "Needs", "Compatibility",
     "Authorized", "Installed", "What it is"],
    platform.catalog,
    (p) => [p.kind, p.namespace + "/" + p.name + "@" + p.version, p.owner,
            p.visibility, p.dependencies.join(", ") || "\\u2014",
            [p.runtime].concat(p.platforms).filter(Boolean).join(", ") || "\\u2014",
            tag(p.authorized, "authorized", "not authorized"),
            tag(p.installed, "installed", "not installed"), p.description || "\\u2014"]));
  el("decisions").replaceChildren(table(
    ["Kind", "Asset", "For", "On this machine"], platform.decisions,
    (d) => [d.kind, d.namespace + "/" + d.name + "@" + d.version, d.actor,
            tag(d.installed, "installed", "not installed")]));
}

async function loadPlatform() {
  renderPlatform(await call("/api/platform"));
}

el("platform-sync").addEventListener("click", async () => {
  const button = el("platform-sync"), result = el("platform-sync-result");
  button.disabled = true;
  result.textContent = "Synchronizing selected assets\\u2026";
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
    result.textContent = "Synchronization did not finish: " + failure.message;
  } finally {
    button.disabled = false;
  }
});

// -- Tabs -----------------------------------------------------------------

const panels = {ask: null, installed: loadAssets, platform: loadPlatform, settings: loadSettings};
const loaded = {};
for (const name of Object.keys(panels)) {
  el("tab-" + name).addEventListener("click", async () => {
    for (const other of Object.keys(panels)) {
      el("tab-" + other).setAttribute("aria-selected", String(other === name));
      el("panel-" + other).toggleAttribute("data-open", other === name);
    }
    if (name === "ask") { field.focus(); return; }
    // Re-read every time it is opened: this is live state, not a snapshot.
    try { await panels[name](); loaded[name] = true; }
    catch (failure) {
      const where = name === "installed" ? "skills" : "catalog";
      el(where).replaceChildren(text("Could not read this: " + failure.message));
    }
  });
}

loadAbout().catch((failure) => { el("who").textContent = "could not read this machine: "
  + failure.message; });
loadReadiness().catch((failure) => { el("readiness").textContent =
  "Could not read Agent readiness: " + failure.message; });
loadAssets().catch((failure) => { el("command-hints").textContent =
  "Could not read installed commands: " + failure.message; });
loadConversations().catch((failure) => { log.textContent =
  "Could not load conversation history: " + failure.message; });
field.focus();
</script>
</body>
</html>
"""
