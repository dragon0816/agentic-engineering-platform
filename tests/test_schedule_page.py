"""The Schedules panel: present in the page and safe with hostile text."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from host_runtime.web_page import PAGE

START = "// -- Schedules ---"
END = "// -- end Schedules renderers"


def _script() -> str:
    return PAGE.split("<script>", 1)[1].split("</script>", 1)[0]


def test_the_page_has_a_schedules_panel_wired_to_the_api() -> None:
    for expected in (
        'id="nav-schedules"',
        'id="panel-schedules"',
        'id="schedule-approvals"',
        'id="schedule-list"',
        'id="schedule-history"',
        'id="schedule-form"',
        'call("/api/schedules")',
        '"/api/schedules/create"',
        '"/api/schedules/grant"',
        '"/api/schedules/revoke"',
        '"/api/schedules/approve"',
        '"/api/schedules/deny"',
        '"/api/schedules/resolve"',
        "schedules: loadSchedules",
    ):
        assert expected in PAGE, expected
    script = _script()
    section = script.split(START, 1)[1].split("// -- Workspace navigation", 1)[0]
    assert "innerHTML" not in section
    assert "insertAdjacentHTML" not in section
    assert "outerHTML" not in section
    # Resolving an uncertain run is explicit and confirmed.
    assert "window.confirm(" in section and "confirm: true" in section


def test_schedule_renderers_keep_hostile_text_as_text(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed, so the renderers cannot be exercised")
    script = _script()
    renderers = START + script.split(START, 1)[1].split(END, 1)[0]
    hostile = "<img src=x onerror=alert(1)>"
    harness = r"""
const assert = require("node:assert/strict");
class FakeNode {
  constructor(tag, value = "") {
    this.tag = tag; this.value = value; this.children = []; this.attrs = {};
    this.listeners = {}; this.dataset = {};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attrs[name] = value; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
}
const document = {
  createElement: tag => new FakeNode(tag),
  createTextNode: value => new FakeNode("#text", value),
};
const text = value => document.createTextNode(value == null ? "" : String(value));
const api = new Function("document", "text", __SOURCE__ +
  "\nreturn {renderScheduleList, renderScheduleApprovals, renderScheduleHistory," +
  " scheduleResolveControl};")(document, text);
const all = (node) => [node, ...node.children.flatMap(all)];
const content = node => node.tag === "#text" ? node.value : node.children.map(content).join("");
const HOSTILE = __HOSTILE__;
const run = {schedule_id: "weekly", due_at: HOSTILE, status: "claimed",
  result_code: null, side_effect: "external_side_effect", idempotency_key: "schedule:abc"};
const waiting = {...run, status: "awaiting_approval", result_code: HOSTILE};
const calls = [];
const actions = {
  pause: () => calls.push("pause"), resume: () => calls.push("resume"),
  grant: (item, effect, days) => calls.push(["grant", effect]),
  revoke: () => calls.push("revoke"), history: () => calls.push("history"),
  approve: (item, note) => calls.push(["approve", item.idempotency_key, note]),
  deny: () => calls.push("deny"),
  resolve: (item) => api.scheduleResolveControl(item, () => calls.push("resolve")),
};
const list = new FakeNode("div");
api.renderScheduleList(list, {schedules: [{
  schedule_id: HOSTILE, status: "active", next_due_at: HOSTILE, target_kind: "workflow",
  target: {namespace: HOSTILE, name: "n", version: "1.0.0"},
  recurrence: {kind: "weekly", timezone: HOSTILE, at: "09:00:00", weekdays: [1, 5]},
  side_effect: "external_side_effect",
  grant: {max_side_effect: "external_side_effect", approved_by: HOSTILE, expires_at: null},
  runs: [waiting], blocked_by: "schedule:abc"}]}, actions);
const approvals = new FakeNode("div");
api.renderScheduleApprovals(approvals, [waiting], actions);
const history = new FakeNode("div");
api.renderScheduleHistory(history, {schedule_id: "weekly", runs: [run], decisions: [
  {decided_at: "now", kind: "resolve", outcome: "failed", decided_by: "engineer",
   note: HOSTILE}]}, actions);
for (const root of [list, approvals, history]) {
  const tags = all(root).map(item => item.tag);
  assert.ok(!tags.includes("img") && !tags.includes("script"), tags.join(","));
  assert.ok(content(root).includes(HOSTILE));
}
assert.match(content(list), /never automatic/);
assert.match(content(list), /Blocked by an unresolved run/);
assert.match(content(list), /weekly on Mon, Fri at 09:00/);
assert.match(content(approvals), /Nothing has been sent/);
const buttons = root => all(root).filter(item => item.tag === "button");
const approve = buttons(approvals).find(item => content(item) === "Approve and run");
const note = all(approvals).find(item => item.tag === "input");
note.value = "checked";
approve.listeners.click();
assert.deepEqual(calls.at(-1), ["approve", "schedule:abc", "checked"]);
assert.ok(buttons(history).some(item => content(item) === "Resolve"));
const empty = new FakeNode("div");
api.renderScheduleApprovals(empty, [], actions);
assert.match(content(empty), /Nothing is waiting/);
""".replace("__SOURCE__", json.dumps(renderers)).replace("__HOSTILE__", json.dumps(hostile))
    path = tmp_path / "schedule-dom.js"
    path.write_text(harness, encoding="utf-8")
    checked = subprocess.run(
        [node, str(path)], capture_output=True, check=False, text=True, timeout=20
    )
    assert checked.returncode == 0, checked.stderr
