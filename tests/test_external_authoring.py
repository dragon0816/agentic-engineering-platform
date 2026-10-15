"""External authoring: Claude Code, Codex or Copilot build Skills and Workflows
(owner 2026-10-08, docs/phases/EXTERNAL_AUTHORING.md).

They submit through the same candidates and approvals as the resident Agent,
never install or run a change themselves, and see statuses and codes only.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from test_chat_authoring import Echo, Out, Recorder, spec, workflow

from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from host_runtime.chat_authoring import ChatAuthoring
from host_runtime.cli import main
from host_runtime.external_authoring import (
    CREATORS,
    ExternalAuthoring,
    connect,
    creator_text,
)
from host_runtime.mcp_server import TOOLS, Server, dispatch
from workflow.dispatch import BridgeExecutor


def desk(tmp_path: Path, agent: str = "codex") -> tuple[ExternalAuthoring, Recorder]:
    recorder = Recorder()
    installed = InstalledCapabilities()
    for name, effect in (("read-it", "read"), ("write-it", "write")):
        installed.register(spec(name, effect), recorder, Echo, Out,
                           ExecutionDependencies(central_required=False))
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    chat = ChatAuthoring(
        tmp_path / "chat", bridge=lambda: bridge, namespace="engineering",
        workflows_dir=tmp_path / "workflows", grants_file=tmp_path / "grants.json",
        skills_dir=tmp_path / "skills",
    )
    return ExternalAuthoring(chat, "owner", agent), recorder


def skill(**extra: Any) -> dict[str, Any]:
    return {"name": "echo-helper", "alias": "echo",
            "instructions": "When asked to echo a month, run the read command.",
            "selector_hint": "echo month, 回聲",
            "commands": [{"name": "read", "kind": "capability",
                          "target": "lab/read-it@1.0.0"}],
            "default_command": "read", **extra}


def installed_skill(folder: Path, name: str, alias: str, owner: str, version: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    manifest = {
        "metadata": {"identity": {"namespace": "engineering", "name": name, "version": version},
                     "owner": {"type": "user", "id": owner}, "visibility": "private",
                     "lifecycle": "published"},
        "alias": alias, "instructions": "x"}
    (folder / f"engineering__{name}__{version}.json").write_text(
        json.dumps(manifest), encoding="utf-8")


# -- Workflows ------------------------------------------------------------------


def test_a_workflow_is_checked_submitted_and_its_read_only_run_returns_codes_only(
    tmp_path: Path,
) -> None:
    authoring, recorder = desk(tmp_path)
    refused = authoring.check_workflow(workflow("missing"))
    assert refused["ok"] is False and "not installed" in str(refused["problems"])
    assert authoring.check_workflow(workflow("read-it"))["ok"] is True
    assert authoring.chat.candidates("owner") == []  # checking keeps nothing
    submitted = authoring.submit_workflow(workflow("read-it"), "Echo")
    assert submitted["ok"] and submitted["read_only"] is True
    candidate = authoring.chat.candidate(str(submitted["candidate_id"]), "owner")
    assert candidate.source == "external:codex"
    ran = authoring.run_workflow(str(submitted["candidate_id"]), {"month": "SECRET-2026-09"})
    assert ran["ran"] is True and recorder.calls == ["SECRET-2026-09"]
    assert ran["run"]["status"] == "succeeded"  # type: ignore[index]
    assert "SECRET-2026-09" not in json.dumps(ran)


def test_a_writing_run_and_an_install_wait_for_the_owner_and_report_without_data(
    tmp_path: Path,
) -> None:
    authoring, recorder = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "Echo")
    candidate_id = str(submitted["candidate_id"])
    asked = authoring.run_workflow(candidate_id, {"month": "PRIVATE-08"})
    assert asked["ran"] is False and recorder.calls == []
    approval_id = str(asked["approval_id"])
    assert authoring.status(approval_id)["status"] == "pending"
    decided = authoring.chat.decide(approval_id, "owner", True)  # the owner's button
    assert decided.source == "external:codex" and recorder.calls == ["PRIVATE-08"]
    view = authoring.status(approval_id)
    assert view["status"] == "approved" and view["run"]["status"] == "succeeded"  # type: ignore[index]
    assert "PRIVATE-08" not in json.dumps(view)
    install = authoring.install_workflow(candidate_id)
    assert not (tmp_path / "workflows").exists()
    authoring.chat.decide(str(install["approval_id"]), "owner", True)
    assert authoring.status(str(install["approval_id"]))["installed_as"] == \
        "engineering/echo-month@1.0.0"
    listed = authoring.list()
    assert listed["workflows"][0]["status"] == "installed"  # type: ignore[index]


def test_another_actors_approvals_and_candidates_are_unknown(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "Echo")
    other = ExternalAuthoring(authoring.chat, "someone-else", "copilot")
    outcome = dispatch(other, "aep_get", {"candidate_id": submitted["candidate_id"]})
    assert outcome == {"ok": False, "code": "candidate_unknown"}


# -- Skills ---------------------------------------------------------------------


def test_a_skill_installs_only_after_approval_and_sets_earlier_versions_aside(
    tmp_path: Path,
) -> None:
    authoring, _ = desk(tmp_path)
    installed_skill(tmp_path / "skills", "echo-helper", "echo", "owner", "1.0.0")
    submitted = authoring.submit_skill(skill(), "Echo helper")
    assert submitted["ok"] and submitted["skill"] == "engineering/echo-helper@1.0.1"
    asked = authoring.install_skill(str(submitted["candidate_id"]))
    assert not (tmp_path / "skills" / "engineering__echo-helper__1.0.1.json").exists()
    pending = authoring.chat.approval(str(asked["approval_id"]), "owner")
    assert pending.kind == "install_skill" and "alias echo" in pending.summary
    authoring.chat.decide(pending.approval_id, "owner", True)
    written = tmp_path / "skills" / "engineering__echo-helper__1.0.1.json"
    data = json.loads(written.read_text(encoding="utf-8"))
    assert data["metadata"]["lifecycle"] == "published"
    assert data["metadata"]["owner"] == {"type": "user", "id": "owner"}
    assert data["metadata"]["business_approval"]["reviewer"] == "owner"
    assert sorted(p.name for p in (tmp_path / "skills").glob("*.json")) == [written.name]
    assert (tmp_path / "skills" / "disabled" / "engineering__echo-helper__1.0.0.json").exists()
    assert authoring.status(pending.approval_id)["installed_as"] == \
        "engineering/echo-helper@1.0.1"


@pytest.mark.parametrize(("change", "expected"), [
    ({"rules": [{"pattern": ".*", "command": "read"}]}, "rules"),
    ({"script_tools": [{"namespace": "lab", "name": "x", "version": "1.0.0"}]}, "script_tools"),
    ({"commands": [{"name": "w", "kind": "workflow", "target": "engineering/none@1.0.0"}],
      "default_command": "w"}, "is not installed"),
    ({"commands": [{"name": "r", "target": "lab/read-it"}], "default_command": "r"},
     "namespace/name@1.2.3"),
    ({"procedure": {"anything": 1}}, "only a Knowledge Skill"),
    ({"instructions": "use password=hunter2-secret-value always"}, "password"),
])
def test_what_an_authored_skill_may_not_carry_is_refused(
    tmp_path: Path, change: dict[str, Any], expected: str,
) -> None:
    authoring, _ = desk(tmp_path)
    outcome = authoring.check_skill(skill(**change))
    assert outcome["ok"] is False and expected in json.dumps(outcome["problems"])


def test_a_taken_skill_name_or_alias_is_refused(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    installed_skill(tmp_path / "skills", "echo-helper", "other_alias", "colleague", "1.0.0")
    taken = authoring.check_skill(skill())
    assert "already belongs to colleague" in json.dumps(taken["problems"])
    installed_skill(tmp_path / "skills", "shipped", "echo2", "team", "2.0.0")
    alias = authoring.check_skill(skill(name="fresh", alias="echo2"))
    assert "already used by engineering/shipped" in json.dumps(alias["problems"])


def test_a_skill_changed_after_its_request_is_not_installed(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    submitted = authoring.submit_skill(skill(), "Echo")
    candidate_id = str(submitted["candidate_id"])
    asked = authoring.install_skill(candidate_id)
    authoring.submit_skill(skill(instructions="Different now."), "Echo", candidate_id)
    decided = authoring.chat.decide(str(asked["approval_id"]), "owner", True)
    assert decided.status == "failed"
    assert not list((tmp_path / "skills").glob("*.json"))


# -- MCP server and CLI ------------------------------------------------------------


def exchange(server: Server, *messages: dict[str, Any]) -> list[dict[str, Any]]:
    source = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in messages))
    sink = io.BytesIO()
    server.serve(source, sink)
    return [json.loads(line) for line in sink.getvalue().splitlines()]


def test_the_mcp_server_speaks_json_rpc_and_calls_the_same_operations(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    server = Server(lambda: authoring, "test")
    replies = exchange(
        server,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "aep_submit_workflow",
                    "arguments": {"title": "Echo", "workflow": workflow("read-it")}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "aep_catalog", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
    )
    assert [r["id"] for r in replies] == [1, 2, 3, 4, 5]
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    assert {t["name"] for t in replies[1]["result"]["tools"]} == set(TOOLS)
    submitted = replies[2]["result"]["structuredContent"]
    assert submitted["ok"] and replies[2]["result"]["isError"] is False
    catalog = replies[3]["result"]["structuredContent"]
    targets = {c["target"]: c for c in catalog["capabilities"]}
    # The catalog is compact; the schema comes from aep_capability.
    assert targets["lab/read-it@1.0.0"]["inputs"] == ["value"]
    assert "input_schema" not in targets["lab/read-it@1.0.0"]
    assert replies[4]["error"]["code"] == -32601


def test_the_server_reports_a_host_that_cannot_start_as_a_code(tmp_path: Path) -> None:
    def broken() -> ExternalAuthoring:
        raise OSError("C:/secret/path")

    replies = exchange(Server(broken, "t"), {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "aep_list", "arguments": {}}})
    outcome = replies[0]["result"]["structuredContent"]
    assert outcome == {"ok": False, "code": "host_unavailable:OSError"}
    assert replies[0]["result"]["isError"] is True


def test_connect_installs_the_creators_for_each_agent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project).mkdir()
    (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    config = tmp_path / "host.json"
    connect("claude-code", project, config, "python.exe")
    for name in CREATORS:
        assert (project / ".claude" / "skills" / name / "SKILL.md").read_text(
            encoding="utf-8") == creator_text(name)
    servers = json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert set(servers) == {"other", "aep", "aep-assistant"}
    assert servers["aep"]["args"][:3] == ["-m", "host_runtime.cli", "mcp"]
    assert servers["aep-assistant"]["args"][:3] == ["-m", "host_runtime.cli", "assistant-mcp"]
    lines = connect("codex", project, config, "python.exe")
    assert "[mcp_servers.aep]" in lines and (project / ".agents" / "skills" / CREATORS[0]).is_dir()
    assert main(["assets", "--config", str(config), "connect", "--for", "copilot",
                 "--project", str(project)]) == 0
    assert (project / ".github" / "skills" / CREATORS[1] / "SKILL.md").is_file()


def test_each_creator_skill_has_the_frontmatter_agents_read() -> None:
    for name in CREATORS:
        text = creator_text(name)
        header = text.split("---")[1]
        assert f"\nname: {name}\n" in header
        description = header.split("description:", 1)[1].strip()
        assert 0 < len(description) <= 1024
        if name == "aep-knowledge":
            assert "aep_knowledge_search" in text and "Sources:" in text
        else:
            assert "aep_catalog" in text and "approval" in text


def test_the_catalog_names_installed_assets_without_what_people_wrote_about_them(
    tmp_path: Path,
) -> None:
    authoring, _ = desk(tmp_path)
    secret = dict(workflow("read-it"), description="Station Taipei-7 customer ACME cost report")
    submitted = authoring.submit_workflow(secret, "Echo")
    asked = authoring.install_workflow(str(submitted["candidate_id"]))
    authoring.chat.decide(str(asked["approval_id"]), "owner", True)
    installed_skill(tmp_path / "skills", "ncc", "ncc", "owner", "1.0.0")
    catalog = authoring.catalog()
    assert catalog["workflows"] == [{"target": "engineering/echo-month@1.0.0", "owner": "owner",
                                     "parameters": [{"name": "month", "kind": "text",
                                                     "required": True}]}]
    assert "ACME" not in json.dumps(catalog) and catalog["skills"][0]["alias"] == "ncc"  # type: ignore[index]


def test_an_installed_unchanged_workflow_runs_directly_for_an_external_agent(
    tmp_path: Path,
) -> None:
    authoring, recorder = desk(tmp_path)
    submitted = authoring.submit_workflow(workflow("write-it"), "Echo")
    candidate_id = str(submitted["candidate_id"])
    authoring.chat.decide(str(authoring.install_workflow(candidate_id)["approval_id"]),
                          "owner", True)
    ran = authoring.run_workflow(candidate_id, {"month": "SECRET-11"})
    assert ran["ran"] is True and recorder.calls == ["SECRET-11"]
    assert "SECRET-11" not in json.dumps(ran)


# -- compact catalog, one capability, formats (owner live test 2026-10-15) -------


def _many(tmp_path: Path, count: int) -> ExternalAuthoring:
    from capabilities.coding_change.run_python import RunPythonResult, RunPythonStepInput

    authoring, recorder = desk(tmp_path)
    for index in range(count):
        item = spec(f"tool-{index:03d}", "read").model_copy(update={
            "description": f"Tool {index} reads the station log and returns rows. " + "x" * 400})
        authoring.chat.installed.register(item, recorder, RunPythonStepInput, RunPythonResult,
                                          ExecutionDependencies(central_required=False))
    return authoring


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, indent=1))


def test_the_catalog_stays_under_the_agents_output_limit(tmp_path: Path) -> None:
    authoring = _many(tmp_path, 60)
    catalog = authoring.catalog()
    full = sum(_size(authoring.capability(str(c["target"]))) for c in catalog["capabilities"])
    assert full > 60_000  # what the old catalog carried
    assert _size(catalog) < 15_000 and "omitted" not in catalog
    entry = next(c for c in catalog["capabilities"] if c["target"] == "lab/tool-007@1.0.0")
    assert entry == {"target": "lab/tool-007@1.0.0",
                     "purpose": "Tool 7 reads the station log and returns rows.",
                     "side_effect": "read", "inputs": ["request", "arguments"]}
    assert "aep_capability" in str(catalog["how_to"])


def test_a_very_large_host_is_trimmed_and_says_what_was_left_out(tmp_path: Path) -> None:
    catalog = _many(tmp_path, 400).catalog()
    assert _size(catalog) <= 15_000
    assert catalog["omitted"]["capabilities"] > 0  # type: ignore[index]


def test_one_capability_and_the_formats_come_in_full(tmp_path: Path) -> None:
    authoring, _ = desk(tmp_path)
    one = dispatch(authoring, "aep_capability", {"target": "lab/read-it@1.0.0"})
    assert one["ok"] and one["input_schema"]["properties"]["value"]  # type: ignore[index]
    assert dispatch(authoring, "aep_capability", {"target": "read-it"})["ok"] is True
    assert dispatch(authoring, "aep_capability", {"target": "lab/none@1.0.0"})["code"] == (
        "capability_unknown")
    workflow_format = dispatch(authoring, "aep_workflow_format", {})["workflow_format"]
    assert "upload" in workflow_format["parameter kinds"]  # type: ignore[index]
    assert workflow_format["complete example"]["checks"]  # type: ignore[index]
    assert "not allowed" in dispatch(authoring, "aep_skill_format", {})["skill_format"]  # type: ignore[operator]
    assert {"aep_capability", "aep_workflow_format", "aep_skill_format"} <= set(TOOLS)


def test_the_cli_offers_the_same_new_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    import host_runtime.external_authoring as module

    authoring, _ = desk(tmp_path)
    monkeypatch.setattr(module, "build", lambda config, agent: authoring)
    config = str(tmp_path / "host.json")
    assert main(["assets", "--config", config, "capability", "--target", "lab/read-it@1.0.0"]) \
        == 0
    assert json.loads(capsys.readouterr().out)["input_schema"]["properties"]["value"]
    assert main(["assets", "--config", config, "workflow-format"]) == 0
    assert "parameter kinds" in json.loads(capsys.readouterr().out)["workflow_format"]
    assert main(["assets", "--config", config, "skill-format"]) == 0


def _tree(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def test_checking_has_no_side_effects_and_submitting_prepares_the_workspace(
    tmp_path: Path,
) -> None:
    from capabilities.coding_change.run_python import RunPythonResult, RunPythonStepInput

    root = tmp_path / "tasks"
    root.mkdir()
    authoring, recorder = desk(tmp_path / "host")
    authoring.chat.coding_workspace_roots = (str(root),)
    run_python = spec("run-python", "execute").model_copy(update={"identity": {
        "namespace": "coding", "name": "run-python", "version": "1.0.0"}})
    authoring.chat.installed.register(run_python, recorder, RunPythonStepInput, RunPythonResult,
                                      ExecutionDependencies(central_required=False))
    task = root / "csv-merge"
    draft = {"name": "csv-merge", "description": "Merge CSV files.", "parameters": [],
             "steps": [{"capability": "coding/run-python@1.0.0", "inputs": {"request": {
                 "source": "fixed", "value": {"workspace": str(task), "script": "print(1)"}}}}]}
    before = _tree(tmp_path)
    assert authoring.check_workflow(draft)["ok"] is True
    assert authoring.check_skill(skill())["ok"] is True
    assert _tree(tmp_path) == before and not task.exists()  # nothing created, nothing kept
    assert authoring.submit_workflow(draft, "Merge")["ok"] is True
    assert (task / "input").is_dir() and (task / "output").is_dir()
