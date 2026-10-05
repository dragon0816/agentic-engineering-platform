"""Generated forms (slice S2): one declaration, one renderer for every form."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from test_workflow_parameter_declaration import RICH, _manifest

from common.workflow_forms import form_fields
from host_runtime.web_page import PAGE


def test_fields_are_filtered_by_channel_identity_first_then_ordered() -> None:
    manifest = _manifest([
        {"name": "note", "label": "Note", "kind": "text", "order": 5},
        *RICH,
        {"name": "source", "label": "Source", "kind": "text", "scope": "static"},
    ])
    web = [field["name"] for field in form_fields(manifest, "web")]
    assert web[0] == "project"                       # identity group leads
    assert "source" not in web                       # static is never a run field
    assert "trace_level" not in web                  # channels=[] is internal
    assert web.index("note") < web.index("chipset")  # order 5 before order 20
    telegram = [field["name"] for field in form_fields(manifest, "telegram")]
    assert "output" not in telegram and "output" in web


def test_fields_carry_normalized_choices_help_and_defaults() -> None:
    manifest = _manifest([
        {"name": "legacy", "label": "Legacy", "kind": "select", "options": ["a", "b"],
         "description": "Old help"},
        *RICH,
    ])
    fields = {field["name"]: field for field in form_fields(manifest, "web")}
    assert fields["legacy"]["choices"] == [
        {"value": "a", "label": "a"}, {"value": "b", "label": "b"},
    ]
    assert fields["legacy"]["help"] == "Old help"
    assert fields["mode"]["choices"][1] == {"value": "full", "label": "Full"}
    assert fields["mode"]["default"] == "brief"
    assert fields["chipset"]["choices_source"] == "ref:chipsets"
    assert fields["project"]["help"] == "GitLab project path"
    assert fields["send"]["confirm"] is True


def _script() -> str:
    return PAGE.split("<script>", 1)[1].split("</script>", 1)[0]


def test_run_and_schedule_forms_share_one_renderer() -> None:
    script = _script()
    contract = script.split("function showWorkflowContract()", 1)[1].split("\n}\n", 1)[0]
    schedule = script.split("function showScheduleTargetFields()", 1)[1].split("\n}\n", 1)[0]
    assert "renderParameterForm(" in contract and "renderParameterForm(" in schedule
    for duplicated in ('createElement("select")', "field.options"):
        assert duplicated not in contract and duplicated not in schedule
    section = script.split("// -- Parameter forms", 1)[1].split("// -- end Parameter forms", 1)[0]
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in section


def test_parameter_renderer_keeps_hostile_text_as_text(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed")
    section = "// -- Parameter forms" + _script().split("// -- Parameter forms", 1)[1].split(
        "// -- end Parameter forms", 1
    )[0]
    hostile = "<img src=x onerror=alert(1)>"
    fields = form_fields(_manifest([
        {"name": "project", "label": hostile, "kind": "text", "group": "identity",
         "help": hostile, "default": hostile},
        {"name": "mode", "label": "Mode", "kind": "select",
         "choices": [{"value": "a", "label": hostile}], "default": "a"},
        {"name": "cc", "label": "CC", "kind": "emails", "default": ["a@example.com"]},
        {"name": "send", "label": "Send", "kind": "boolean", "default": True, "confirm": True},
    ]), "web")
    harness = r"""
const assert = require("node:assert/strict");
class FakeNode {
  constructor(tag, value = "") {
    this.tag = tag; this.value = value; this.children = []; this.attrs = {};
    this.listeners = {}; this.dataset = {}; this.tagName = tag.toUpperCase();
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
  "\nreturn {renderParameterForm};")(document, text);
const all = node => [node, ...node.children.flatMap(all)];
const content = node => node.tag === "#text" ? node.value : node.children.map(content).join("");
const HOSTILE = __HOSTILE__;
const box = new FakeNode("div");
api.renderParameterForm(box, __FIELDS__, "f-");
for (const item of all(box)) {
  assert.ok(!["img", "script"].includes(item.tag));
}
const text_ = content(box);
assert.ok(text_.includes(HOSTILE));
assert.ok(text_.includes("Identity"));
const byId = Object.fromEntries(all(box).filter(n => n.id).map(n => [n.id, n]));
assert.equal(byId["f-project"].value, HOSTILE);
assert.equal(byId["f-mode"].tag, "select");
assert.equal(byId["f-cc"].tag, "textarea");
assert.equal(byId["f-cc"].value, "a@example.com");
assert.equal(byId["f-send"].checked, true);
"""
    script = tmp_path / "forms.js"
    script.write_text(
        harness.replace("__SOURCE__", json.dumps(section))
        .replace("__HOSTILE__", json.dumps(hostile))
        .replace("__FIELDS__", json.dumps(fields)),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60
    )
    assert completed.returncode == 0, completed.stderr
