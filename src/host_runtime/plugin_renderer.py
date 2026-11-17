"""The core's renderer for Feature Plugin pages and the plugin manager panel
(Slice 1, `docs/phases/FEATURE_PLUGIN_SLICE1_PLAN_20261113.md` §3).

A plugin contributes data, never markup: its titles, texts, labels, failure
messages and route answers reach the page only as text nodes made by this
core-authored script. Nothing here creates a link, image, frame or script, or
sets an attribute from plugin text. The page token is used only by
`pluginRequest` for Agent Web's own routes and is never handed to a plugin.

`web_page.PAGE` embeds `PLUGIN_NAV_HTML` in the sidebar, `PLUGIN_PANEL_HTML`
among the panels and `PLUGIN_RENDERER_CSS`/`PLUGIN_RENDERER_JS` in its style
and script; the script uses the page's `el`, `text`, `TOKEN` and, when it
exists, `selectPrimaryTab`.
"""

from __future__ import annotations

from common.plugins import MAX_PACKAGE_BYTES, MAX_TABLE_ROWS

#: The sidebar entry and the list of active plugin pages under it.
PLUGIN_NAV_HTML = (
    '<button id="nav-plugins" type="button">Plugins</button>\n'
    '<div id="plugin-nav" class="plugin-nav" role="group" aria-label="Plugin pages"></div>'
)

#: The panel: one plugin page at a time, then install and the installed list.
PLUGIN_PANEL_HTML = """<section id="panel-plugin">
    <div class="workspace-head">
      <div><h2>Plugins</h2>
        <p class="note">Feature plugins installed on this machine. A plugin's pages show
          its own data as text. Disabling or uninstalling keeps its data.</p></div>
      <button id="plugin-refresh" type="button">Refresh</button>
    </div>
    <div id="plugin-page" class="plugin-page" hidden></div>
    <form id="plugin-install-form" class="plugin-install">
      <label for="plugin-file">Plugin package (.aep-plugin)</label>
      <input id="plugin-file" type="file" accept=".aep-plugin,.json,application/json">
      <button id="plugin-install" type="submit">Install</button>
    </form>
    <p id="plugin-status" class="note" role="status"></p>
    <div id="plugin-list" class="plugin-list"></div>
  </section>"""

PLUGIN_RENDERER_CSS = r"""
#nav-plugins::before { content: "\25a6"; }
.plugin-nav { display: grid; gap: 2px; padding-left: 24px; }
.plugin-nav:empty { display: none; }
.side-actions .plugin-nav button { min-height: 32px; padding: 4px 10px; font-size: 0.9em;
  font-weight: 500; }
.plugin-page { margin-bottom: 16px; }
.plugin-page .plugin-block { margin: 8px 0; }
.plugin-page .plugin-text { white-space: pre-wrap; }
.plugin-page .plugin-metric strong { font-size: 1.4em; margin-left: 8px; }
.plugin-page table { border-collapse: collapse; }
.plugin-page th, .plugin-page td { border: 1px solid var(--line, #ddd); padding: 2px 8px;
  text-align: left; white-space: pre-wrap; }
.plugin-install { display: flex; gap: 8px; align-items: center; margin: 8px 0; }
.plugin-list .plugin-row { border-top: 1px solid var(--line, #ddd); padding: 8px 0; }
.plugin-list .plugin-failure { color: var(--danger, #b00020); }
.plugin-error { color: var(--danger, #b00020); }
"""

PLUGIN_RENDERER_JS = r"""// -- Feature plugins (Slice 1) ---
// Plugin text is data: every string below reaches the page as a text node.
const PLUGIN_MAX_PACKAGE_BYTES = __MAX_PACKAGE_BYTES__;
const PLUGIN_MAX_TABLE_ROWS = __MAX_TABLE_ROWS__;
let pluginSnapshot = {plugins: []}, pluginCurrent = null;

async function pluginRequest(path, options = {}) {
  // Agent Web's own routes only; the page token never goes to a plugin.
  const headers = Object.assign({}, options.headers || {},
    {"Authorization": "Bearer " + TOKEN});
  const reply = await fetch(path, Object.assign({}, options, {headers}));
  let data = {};
  try { data = await reply.json(); } catch (e) { data = {}; }
  if (!data || typeof data !== "object") data = {};
  return Object.assign({}, data, {ok: reply.ok && data.ok !== false, http: reply.status});
}

function pluginFailureText(reply) {
  const code = String(reply.code || ("http_" + reply.http));
  return reply.message ? code + ": " + String(reply.message) : code;
}

function pluginCell(value) {
  if (value == null) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function pluginElement(tag, className, ...children) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  for (const child of children) node.append(typeof child === "string" ? text(child) : child);
  return node;
}

function pluginButton(label, action) {
  const button = document.createElement("button");
  button.type = "button";
  button.append(text(label));
  button.addEventListener("click", action);
  return button;
}

function pluginActive(snapshot) {
  return ((snapshot && snapshot.plugins) || []).filter(item => item.state === "active");
}

function renderPluginNav(box, snapshot, open) {
  const buttons = [];
  for (const plugin of pluginActive(snapshot)) {
    for (const page of plugin.pages || []) {
      const button = pluginButton(String(plugin.title) + " · " + String(page.title),
        () => open(plugin, page));
      button.dataset.plugin = String(plugin.plugin_id);
      button.dataset.page = String(page.page_id);
      buttons.push(button);
    }
  }
  box.replaceChildren(...buttons);
}

function renderPluginList(box, snapshot, act) {
  const plugins = (snapshot && snapshot.plugins) || [];
  // Shipped with AEP (Plugin API 1.2): switched off or on, never uninstalled.
  const shipped = ((snapshot && snapshot.bundled) || []).map((p) => ({...p, shipped: true}));
  const all = [...plugins, ...shipped];
  if (!all.length) {
    box.replaceChildren(pluginElement("p", "empty", "No plugins are installed."));
    return;
  }
  box.replaceChildren(...all.map((plugin) => {
    const identity = plugin.identity || {};
    const row = pluginElement("div", "plugin-row",
      pluginElement("strong", "", String(plugin.title)),
      " ", pluginElement("code", "", String(plugin.plugin_id) + "@" + String(identity.version)),
      " ", pluginElement("span", "plugin-state", String(plugin.state)));
    row.dataset.pluginId = String(plugin.plugin_id);
    if (plugin.shipped) row.append(" ", pluginElement("span", "plugin-note", "shipped with AEP"));
    if (plugin.failure) {
      row.append(pluginElement("p", "plugin-failure", pluginFailureText(plugin.failure)));
    }
    if (plugin.restart_required) {
      row.append(pluginElement("p", "plugin-restart",
        "Restart AEP to apply this change (it loads into AEP when AEP starts)."));
    }
    const controls = pluginElement("div", "plugin-controls");
    if (plugin.state === "active") {
      controls.append(pluginButton("Disable", () => act("disable", plugin)));
    } else {
      controls.append(pluginButton("Enable", () => act("enable", plugin)));
    }
    if (!plugin.shipped) controls.append(pluginButton("Uninstall", () => act("uninstall", plugin)));
    row.append(controls);
    return row;
  }));
}

async function pluginRead(plugin, routeId) {
  const version = (plugin.identity || {}).version;
  return pluginRequest("/api/plugins/" + encodeURIComponent(plugin.plugin_id) + "/"
    + encodeURIComponent(routeId) + "?version=" + encodeURIComponent(version));
}

function pluginTable(block, rows) {
  const table = document.createElement("table");
  const head = document.createElement("tr");
  for (const column of block.columns || []) {
    head.append(pluginElement("th", "", String(column.label)));
  }
  table.append(head);
  const list = Array.isArray(rows) ? rows : [];
  for (const row of list.slice(0, PLUGIN_MAX_TABLE_ROWS)) {
    const line = document.createElement("tr");
    for (const column of block.columns || []) {
      const value = row && typeof row === "object" ? row[column.key] : null;
      line.append(pluginElement("td", "", pluginCell(value)));
    }
    table.append(line);
  }
  const box = pluginElement("div", "plugin-block plugin-table");
  if (block.title) box.append(pluginElement("h4", "", String(block.title)));
  box.append(table);
  if (list.length > PLUGIN_MAX_TABLE_ROWS) {
    box.append(pluginElement("p", "note", "Showing the first " + PLUGIN_MAX_TABLE_ROWS
      + " of " + list.length + " rows."));
  }
  return box;
}

async function renderPluginPage(box, plugin, page, read = routeId => pluginRead(plugin, routeId)) {
  // One read per route, shared by every block that shows it.
  const answers = {};
  for (const block of page.blocks || []) {
    if (block.kind !== "text" && !(block.route_id in answers)) {
      answers[block.route_id] = null;
    }
  }
  for (const routeId of Object.keys(answers)) {
    try { answers[routeId] = await read(routeId); }
    catch (failure) { answers[routeId] = {ok: false, code: "plugin_unavailable"}; }
  }
  const blocks = [pluginElement("h3", "", String(page.title))];
  for (const block of page.blocks || []) {
    if (block.kind === "text") {
      blocks.push(pluginElement("p", "plugin-block plugin-text", String(block.text)));
      continue;
    }
    const answer = answers[block.route_id] || {ok: false, code: "plugin_unavailable"};
    if (!answer.ok) {
      blocks.push(pluginElement("p", "plugin-block plugin-error", pluginFailureText(answer)));
      continue;
    }
    const data = answer.data && typeof answer.data === "object" ? answer.data : {};
    if (block.kind === "metric") {
      blocks.push(pluginElement("p", "plugin-block plugin-metric", String(block.label),
        pluginElement("strong", "", pluginCell(data[block.field]))));
    } else if (block.kind === "table") {
      blocks.push(pluginTable(block, data[block.field]));
    }
  }
  box.replaceChildren(...blocks);
}

async function pluginAction(action, pluginId) {
  return pluginRequest("/api/plugin-manager/" + action, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({plugin_id: pluginId}),
  });
}

function pluginInstallPayload(file) {
  if (!file) return {ok: false, message: "Choose a plugin package first."};
  if (file.size > PLUGIN_MAX_PACKAGE_BYTES) {
    return {ok: false, message: "This package is larger than "
      + Math.floor(PLUGIN_MAX_PACKAGE_BYTES / 1048576) + " MB."};
  }
  return {ok: true};
}

function pluginSay(message, failed = false) {
  const status = el("plugin-status");
  if (!status) return;
  status.className = failed ? "note plugin-error" : "note";
  status.replaceChildren(text(message));
}

async function pluginRefresh() {
  const reply = await pluginRequest("/api/plugin-manager/plugins");
  if (!reply.ok) {
    pluginSay("Could not read plugins: " + pluginFailureText(reply), true);
    return false;
  }
  pluginSnapshot = {plugins: reply.plugins || [], bundled: reply.bundled || []};
  const nav = el("plugin-nav");
  if (nav) renderPluginNav(nav, pluginSnapshot, openPluginPage);
  const list = el("plugin-list");
  if (list) renderPluginList(list, pluginSnapshot, pluginAct);
  return true;
}

async function loadPluginNav() {
  // Called at boot; a plugin problem never stops the page from loading.
  try { await pluginRefresh(); } catch (e) { /* shown when the panel opens */ }
}

async function showPluginPage() {
  const box = el("plugin-page");
  if (!box) return;
  const current = pluginCurrent && pluginActive(pluginSnapshot).find(item =>
    item.plugin_id === pluginCurrent.plugin_id);
  const page = current && (current.pages || []).find(item =>
    item.page_id === pluginCurrent.page_id);
  if (!page) { box.hidden = true; box.replaceChildren(); return; }
  box.hidden = false;
  await renderPluginPage(box, current, page);
}

async function loadPlugins() {
  pluginSay("");
  if (await pluginRefresh()) await showPluginPage();
}

function openPluginPage(plugin, page) {
  pluginCurrent = {plugin_id: plugin.plugin_id, page_id: page.page_id};
  if (typeof selectPrimaryTab === "function") selectPrimaryTab("plugin");
  else loadPlugins();
}

async function pluginAct(action, plugin) {
  pluginSay(action + " " + String(plugin.plugin_id) + "…");
  const reply = await pluginAction(action, plugin.plugin_id);
  if (reply.ok) pluginSay(action + " " + String(plugin.plugin_id) + ": done.");
  else pluginSay(action + " " + String(plugin.plugin_id) + ": " + pluginFailureText(reply), true);
  await loadPlugins();
}

async function pluginInstall(file) {
  const checked = pluginInstallPayload(file);
  if (!checked.ok) { pluginSay(checked.message, true); return; }
  pluginSay("Installing…");
  const reply = await pluginRequest("/api/plugin-manager/install", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: await file.arrayBuffer(),
  });
  if (reply.ok) pluginSay("Installed " + String(reply.plugin_id) + ".");
  else pluginSay("Install failed: " + pluginFailureText(reply), true);
  await pluginRefresh();
}

if (typeof document.getElementById === "function" && document.getElementById("panel-plugin")) {
  el("plugin-install-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = el("plugin-file");
    pluginInstall(input.files && input.files[0])
      .catch(failure => pluginSay("Install failed: " + failure.message, true));
  });
  el("plugin-refresh").addEventListener("click", () => {
    loadPlugins().catch(failure => pluginSay(String(failure.message), true));
  });
  el("nav-plugins").addEventListener("click", () => {
    pluginCurrent = null;
    if (typeof selectPrimaryTab === "function") selectPrimaryTab("plugin");
  });
}
// -- end Feature plugins
""".replace("__MAX_PACKAGE_BYTES__", str(MAX_PACKAGE_BYTES)).replace(
    "__MAX_TABLE_ROWS__", str(MAX_TABLE_ROWS)
)
