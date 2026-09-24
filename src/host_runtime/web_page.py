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
button.go {
  font: inherit; font-weight: 600; padding: 9px 18px; cursor: pointer;
  color: #fff; background: var(--accent); border: none; border-radius: 8px;
}
button.go[disabled] { opacity: .5; cursor: default; }
.hint { color: var(--dim); font-size: 12px; margin: 8px 0 0; }

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
</nav>
<main>
  <section id="panel-ask" data-open>
    <div id="log"></div>
    <form class="ask" id="ask">
      <input id="message" autocomplete="off" spellcheck="false"
             placeholder="a command, such as  weekly.preview 2026_39W">
      <button class="go" id="send" type="submit">Send</button>
    </form>
    <p class="hint">This is the Agent on this computer &mdash; the same one the
      command line and Telegram reach, with the same permissions and the same
      refusals. Nothing is written unless the command says so. One request runs
      at a time.</p>
  </section>

  <section id="panel-installed">
    <h2>Skills</h2>
    <p class="note">What can be asked for by name on this machine.</p>
    <div class="card"><div id="skills" class="empty">reading&hellip;</div></div>
    <h2>Workflows</h2>
    <p class="note">What a Skill&rsquo;s command runs.</p>
    <div class="card"><div id="workflows" class="empty">reading&hellip;</div></div>
    <h2>Recent runs</h2>
    <div class="card"><div id="runs" class="empty">reading&hellip;</div></div>
  </section>

  <section id="panel-platform">
    <h2>What the shared platform decided</h2>
    <p class="note" id="platform-note">reading&hellip;</p>
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
  const options = {
    method: body ? "POST" : "GET",
    headers: {"Authorization": "Bearer " + TOKEN},
  };
  if (body) {
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
  for (const row of rows) {
    const tr = t.insertRow();
    for (const value of cell(row)) {
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const asked = field.value.trim();
  if (!asked) return;
  field.value = "";
  field.disabled = send.disabled = true;
  const said = turn(asked);
  try {
    const answer = await call("/api/ask", {message: asked});
    said.className = "said" + (answer.ok ? "" : " bad");
    said.textContent = answer.answer;
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

async function loadAssets() {
  const assets = await call("/api/assets");
  el("skills").replaceChildren(table(
    ["Alias", "Commands", "Asset", "What it is"], assets.skills,
    (s) => [s.alias, s.commands.join(", ") || "\\u2014",
            s.namespace + "/" + s.name + "@" + s.version, s.description]));
  el("workflows").replaceChildren(table(
    ["Asset", "Steps", "What it does"], assets.workflows,
    (w) => [w.namespace + "/" + w.name + "@" + w.version, w.steps, w.description]));
  el("runs").replaceChildren(table(
    ["Run", "Workflow", "Status", "Asked by"], assets.runs,
    (r) => [r.run_id, r.workflow, r.status, r.actor]));
}

async function loadPlatform() {
  const platform = await call("/api/platform");
  el("platform-note").textContent = platform.note;
  el("decisions").replaceChildren(table(
    ["Kind", "Asset", "For", "On this machine"], platform.decisions,
    (d) => [d.kind, d.namespace + "/" + d.name + "@" + d.version, d.actor,
            tag(d.installed, "installed", "not installed")]));
}

// -- Tabs -----------------------------------------------------------------

const panels = {ask: null, installed: loadAssets, platform: loadPlatform};
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
      const where = name === "installed" ? "skills" : "decisions";
      el(where).replaceChildren(text("Could not read this: " + failure.message));
    }
  });
}

loadAbout().catch((failure) => { el("who").textContent = "could not read this machine: "
  + failure.message; });
field.focus();
</script>
</body>
</html>
"""
