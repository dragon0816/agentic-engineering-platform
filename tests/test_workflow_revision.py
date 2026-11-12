"""Revising an installed Workflow from a conversation (owner 2026-10-19).

"The Agent said it could not modify the installed Workflow because the
platform does not expose its source, so it rewrote a v2 from scratch."
The Agent now reads any installed Workflow it may see, copies it into a draft
one version up, edits that draft, and the person installs it from the card.
A shipped capability's Python source is readable, never editable.

Fixtures only: a Workflow modelled on the weekly report, never the real one.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_chat_authoring import Echo, Out, Recorder, spec

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import RequestContext, TraceIdentifiers
from host_runtime.chat_authoring import ChatAuthoring, digest
from host_runtime.draft_cards import DraftCards
from host_runtime.external_authoring import ExternalAuthoring
from host_runtime.mcp_server import dispatch
from host_runtime.workflow_revision import (
    MAX_VIEW_CHARS,
    capability_source,
    package_of,
    readable,
)
from workflow.dispatch import BridgeExecutor

ACTOR = "owner"
SCRIPT = (
    "import json, os\n"
    'params = json.load(open(os.environ["AEP_WORKFLOW_PARAMS"]))\n'
    "\n"
    "def issue_key(row):\n"
    '    return row.get("gtm") or "NO-KEY"\n'
    "\n"
    'print(issue_key({"title": params.get("week_start")}))\n'
)
EDITED = SCRIPT.replace(
    '    return row.get("gtm") or "NO-KEY"\n',
    "    # No GTM-xxx key: fall back to the tracking issue.\n"
    '    return row.get("gtm") or "GH-76"\n',
)


class Request(Contract):
    request: dict[str, Any] = {}
    arguments: dict[str, Any] = {}


def run_python_spec() -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": "coding", "name": "run-python", "version": "1.0.0"},
            "name": "coding.run-python",
            "description": "Run a Python script in a task folder.",
            "input_contract": "coding.run-python.in.v1",
            "output_contract": "coding.run-python.out.v1",
            "side_effect": "write",
            "policy": {
                "risk": "low",
                "required_permissions": ["coding.run"],
                "policy_refs": ["lab-policy"],
                "approval_required": True,
            },
        }
    )


def studio(tmp_path: Path) -> ChatAuthoring:
    installed = InstalledCapabilities()
    recorder = Recorder()
    installed.register(
        spec("read-it", "read"), recorder, Echo, Out, ExecutionDependencies(central_required=False)
    )
    installed.register(
        run_python_spec(), recorder, Request, Out, ExecutionDependencies(central_required=False)
    )
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    return ChatAuthoring(
        tmp_path / "chat",
        bridge=lambda: bridge,
        namespace="engineering",
        workflows_dir=tmp_path / "workflows",
        grants_file=tmp_path / "grants.json",
        coding_workspace_roots=(str(tmp_path / "tasks"),),
    )


def fixture_workflow(
    tmp_path: Path,
    *,
    name: str = "fixture-weekly-report",
    namespace: str = "engineering",
    owner: tuple[str, str] = ("user", ACTOR),
    visibility: str = "private",
    script: str = SCRIPT,
    refs: tuple[str, ...] = ("chat-candidate:wf-earlier:abc",),
    contributors: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "metadata": {
            "identity": {"namespace": namespace, "name": name, "version": "1.0.0"},
            "owner": {"type": owner[0], "id": owner[1]},
            "visibility": visibility,
            "lifecycle": "published",
            "contributors": list(contributors),
            "business_approval": {
                "status": "approved",
                "reviewer": owner[1],
                "evidence": "fixture",
            },
            "validation_refs": list(refs),
        },
        "kind": "workflow",
        "description": "Weekly report fixture: issues of the week into a workbook.",
        "execution": {"mode": "local"},
        "dependencies": {"central_required": False, "local_capabilities": ["coding.run-python"]},
        "input_contract": f"{namespace}.{name}.input.v1",
        "output_contract": f"{namespace}.{name}.output.v1",
        "parameters": [
            {
                "name": "week_start",
                "label": "First day of the week",
                "kind": "date",
                "scope": "runtime",
                "required": True,
            }
        ],
        "steps": [
            {
                "capability": {"namespace": "coding", "name": "run-python", "version": "1.0.0"},
                "inputs": {
                    "request": {
                        "source": "fixed",
                        "value": {
                            "workspace": str(tmp_path / "tasks" / "weekly"),
                            "script": script,
                        },
                    },
                    "arguments": {"source": "run", "path": []},
                },
            }
        ],
        "progress_steps": [{"id": "collect", "title": "Collect the week's issues"}],
        "occupies_machine": True,
        "checks": [
            {"check_id": "workbook", "step_index": 0, "kind": "files_nonempty", "pattern": "*.xlsx"}
        ],
    }


def install_fixture(chat: ChatAuthoring, body: dict[str, Any]) -> Path:
    manifest = WorkflowManifest.model_validate(body)
    identity = manifest.metadata.identity
    chat.workflows_dir.mkdir(parents=True, exist_ok=True)
    path = chat.workflows_dir / f"{identity.namespace}__{identity.name}__{identity.version}.json"
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def context(actor: str = ACTOR, session: str = "session-1") -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="t", request_id="r", span_id="s"),
        actor=actor,
        namespace="engineering",
        channel="local",
        session_id=session,
        message="x",
    )


def call(chat: ChatAuthoring, name: str, args: dict[str, Any], actor: str = ACTOR) -> Any:
    tool = next(t for t in chat.tools() if t.tool.name == name)

    async def invoke() -> Any:
        return await tool.handler(context(actor), args)

    return asyncio.run(invoke())


def edited_workflow(chat: ChatAuthoring, candidate_id: str, script: str) -> dict[str, Any]:
    """What a model sends back: the draft it read, with the script changed."""
    shown = call(chat, "authoring__get_workflow", {"candidate_id": candidate_id}).data
    steps = shown["steps"]
    steps[0]["inputs"]["request"]["value"]["script"] = script
    return {
        "name": shown["workflow"].split("/", 1)[1].split("@", 1)[0],
        "description": "Weekly report fixture: issues of the week into a workbook.",
        "parameters": shown["parameters"],
        "steps": steps,
        "checks": shown["checks"],
    }


# -- reading an installed Workflow by identity ---------------------------------------


def test_a_bundle_style_workflow_is_read_by_identity_with_its_embedded_script(
    tmp_path: Path,
) -> None:
    chat = studio(tmp_path)
    install_fixture(
        chat,
        fixture_workflow(
            tmp_path, owner=("team", "engineering"), visibility="organization", refs=()
        ),
    )
    for reference in (
        "engineering/fixture-weekly-report@1.0.0",
        "fixture-weekly-report",
        "engineering/fixture-weekly-report",
        "fixture-weekly-report@1.0.0",
    ):
        shown = call(chat, "authoring__get_workflow", {"workflow": reference})
        assert shown.status == "succeeded", reference
        data = shown.data
        assert data["workflow"] == "engineering/fixture-weekly-report@1.0.0"
        assert data["origin"] == "installed" and data["owner"] == "team:engineering"
        assert data["steps"][0]["inputs"]["request"]["value"]["script"] == SCRIPT
        assert [p["name"] for p in data["parameters"]] == ["week_start"]
        assert data["progress_steps"][0]["id"] == "collect"
        assert "business_approval" not in json.dumps(data)


def test_a_marketplace_style_workflow_is_read_and_the_highest_version_wins(
    tmp_path: Path,
) -> None:
    chat = studio(tmp_path)
    body = fixture_workflow(
        tmp_path, name="market-report", owner=("organization", "acme"), visibility="public"
    )
    install_fixture(chat, body)
    newer = json.loads(json.dumps(body))
    newer["metadata"]["identity"]["version"] = "1.2.0"
    install_fixture(chat, newer)
    shown = call(chat, "authoring__get_workflow", {"workflow": "market-report"})
    assert shown.data["workflow"] == "engineering/market-report@1.2.0"
    exact = call(chat, "authoring__get_workflow", {"workflow": "market-report@1.0.0"})
    assert exact.data["workflow"] == "engineering/market-report@1.0.0"
    missing = call(chat, "authoring__get_workflow", {"workflow": "market-reports"})
    assert missing.failure.code == "workflow_unknown"
    assert "engineering/market-report@1.2.0" in missing.failure.message


def test_a_long_workflow_comes_in_slices_with_a_notice(tmp_path: Path) -> None:
    chat = studio(tmp_path)
    long_script = SCRIPT + "".join(f"# filler line {n:05d} " + "x" * 60 + "\n" for n in range(600))
    install_fixture(chat, fixture_workflow(tmp_path, script=long_script))
    first = call(chat, "authoring__get_workflow", {"workflow": "fixture-weekly-report"}).data
    assert first["truncated"] is True and first["offset"] == 0
    assert len(first["json_text"]) == MAX_VIEW_CHARS
    assert "offset=" in first["notice"] and first["next_offset"] == MAX_VIEW_CHARS
    text, offset = first["json_text"], first["next_offset"]
    while offset is not None:
        part = call(
            chat,
            "authoring__get_workflow",
            {"workflow": "fixture-weekly-report", "offset": offset},
        ).data
        text, offset = text + part["json_text"], part["next_offset"]
    whole = json.loads(text)
    assert whole["steps"][0]["inputs"]["request"]["value"]["script"] == long_script


def test_another_actors_private_workflow_is_not_readable(tmp_path: Path) -> None:
    chat = studio(tmp_path)
    install_fixture(
        chat, fixture_workflow(tmp_path, name="colleague-report", owner=("user", "colleague"))
    )
    refused = call(chat, "authoring__get_workflow", {"workflow": "colleague-report"})
    assert refused.status == "failed"
    assert refused.failure.code == "workflow_unknown"
    assert "colleague-report" not in refused.failure.message
    revise = call(chat, "authoring__revise_workflow", {"workflow": "colleague-report"})
    assert revise.status == "failed" and revise.failure.code == "workflow_unknown"
    # Its owner reads it.
    assert (
        call(chat, "authoring__get_workflow", {"workflow": "colleague-report"}, actor="colleague")
        .data["workflow"]
        .endswith("colleague-report@1.0.0")
    )


def test_readability_rules() -> None:
    def metadata(owner: tuple[str, str], visibility: str, lifecycle: str = "published") -> Any:
        body = fixture_workflow(Path("C:/x"), owner=owner, visibility=visibility)
        body["metadata"]["lifecycle"] = lifecycle
        return WorkflowManifest.model_validate(body).metadata

    assert readable(metadata(("user", ACTOR), "private", "draft"), ACTOR)
    assert readable(metadata(("team", "engineering"), "team"), ACTOR)
    assert readable(metadata(("user", "colleague"), "organization"), ACTOR)
    assert not readable(metadata(("user", "colleague"), "private"), ACTOR)
    assert not readable(metadata(("user", "colleague"), "team"), ACTOR)
    assert not readable(metadata(("team", "engineering"), "organization", "draft"), ACTOR)


# -- forking an installed Workflow into a revision draft ----------------------------


def test_revise_makes_a_draft_one_version_up_with_its_base(tmp_path: Path) -> None:
    chat = studio(tmp_path)
    path = install_fixture(chat, fixture_workflow(tmp_path))
    base = WorkflowManifest.model_validate_json(path.read_text(encoding="utf-8"))
    revised = call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    assert revised.status == "succeeded", revised
    data = revised.data
    assert data["workflow"] == "engineering/fixture-weekly-report@1.0.1"
    assert data["revision_of"] == "engineering/fixture-weekly-report@1.0.0"
    assert data["forked"] is False and data["base_digest"] == digest(base)
    item = chat.candidate(data["candidate_id"], ACTOR)
    assert item.source == "revision:engineering/fixture-weekly-report@1.0.0"
    assert item.base_digest == digest(base) and item.status == "draft"
    assert item.draft.metadata.owner.id == ACTOR and item.draft.metadata.lifecycle == "draft"
    # What the draft format cannot express is kept from the original.
    assert item.draft.occupies_machine is True
    assert [p.id for p in item.draft.progress_steps] == ["collect"]
    assert item.draft.steps == base.steps and item.draft.parameters == base.parameters
    # Asking again continues the open revision instead of making a second one.
    again = call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    assert again.data["candidate_id"] == data["candidate_id"] and again.data["continued"]


def test_editing_the_script_then_the_cards_install_adds_1_0_1_and_keeps_1_0_0(
    tmp_path: Path,
) -> None:
    chat = studio(tmp_path)
    original = install_fixture(chat, fixture_workflow(tmp_path))
    before = original.read_bytes()
    candidate_id = call(
        chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"}
    ).data["candidate_id"]
    saved = call(
        chat,
        "authoring__draft_workflow",
        {
            "title": "Issue Key fallback",
            "workflow": edited_workflow(chat, candidate_id, EDITED),
            "candidate_id": candidate_id,
        },
    )
    assert saved.status == "succeeded", saved
    # Editing keeps the one version above the installed one.
    assert saved.data["workflow"] == "engineering/fixture-weekly-report@1.0.1"
    item = chat.candidate(candidate_id, ACTOR)
    assert item.source.startswith("revision:") and item.revision == 2
    # Nothing is installed by the model's tools.
    assert sorted(p.name for p in chat.workflows_dir.glob("*.json")) == [original.name]

    cards = DraftCards(tmp_path / "ws", chat=lambda: chat, actor=lambda: ACTOR)
    since = datetime.now(UTC) - timedelta(minutes=1)
    shown, _ = cards.for_turn("session-1", since)
    (card,) = shown
    preview = card["preview"]
    assert "Revision of engineering/fixture-weekly-report 1.0.0 → 1.0.1" in preview
    assert "request.script +2/−1 lines" in preview
    assert "keeps engineering/fixture-weekly-report@1.0.0 installed" in preview
    assert sorted(p.name for p in chat.workflows_dir.glob("*.json")) == [original.name]

    decided = cards.decide(card["card_id"], "install")
    assert decided["ok"], decided
    new = chat.workflows_dir / "engineering__fixture-weekly-report__1.0.1.json"
    installed = WorkflowManifest.model_validate_json(new.read_text(encoding="utf-8"))
    step: Any = installed.steps[0]
    assert step.inputs["request"].value["script"] == EDITED
    assert installed.metadata.lifecycle == "draft" and installed.occupies_machine
    assert installed.metadata.business_approval.status == "pending"
    # 1.0.0 stays installed, byte for byte, and remains readable by its exact version.
    assert original.read_bytes() == before
    old = call(chat, "authoring__get_workflow", {"workflow": "fixture-weekly-report@1.0.0"})
    assert old.data["steps"][0]["inputs"]["request"]["value"]["script"] == SCRIPT
    latest = call(chat, "authoring__get_workflow", {"workflow": "fixture-weekly-report"})
    assert latest.data["workflow"].endswith("@1.0.1")


def test_an_unchanged_revision_gets_no_card(tmp_path: Path) -> None:
    chat = studio(tmp_path)
    install_fixture(chat, fixture_workflow(tmp_path))
    call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    cards = DraftCards(tmp_path / "ws", chat=lambda: chat, actor=lambda: ACTOR)
    shown, _ = cards.for_turn("session-1", datetime.now(UTC) - timedelta(minutes=1))
    assert shown == []


def test_a_non_owner_forks_under_a_new_name_and_is_told(tmp_path: Path) -> None:
    chat = studio(tmp_path)
    install_fixture(
        chat,
        fixture_workflow(
            tmp_path, owner=("team", "engineering"), visibility="organization", refs=()
        ),
    )
    revised = call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    assert revised.status == "succeeded", revised
    data = revised.data
    assert data["forked"] is True
    assert data["workflow"] == "engineering/fixture-weekly-report-owner@1.0.0"
    assert "fork" in data["note"] and "fixture-weekly-report-owner" in data["note"]
    item = chat.candidate(data["candidate_id"], ACTOR)
    assert item.draft.metadata.owner.id == ACTOR
    edited = edited_workflow(chat, data["candidate_id"], EDITED)
    call(
        chat,
        "authoring__draft_workflow",
        {"title": "Fork", "workflow": edited, "candidate_id": data["candidate_id"]},
    )
    cards = DraftCards(tmp_path / "ws", chat=lambda: chat, actor=lambda: ACTOR)
    (card,), _ = cards.for_turn("session-1", datetime.now(UTC) - timedelta(minutes=1))
    assert (
        "Fork of engineering/fixture-weekly-report@1.0.0 as "
        "engineering/fixture-weekly-report-owner@1.0.0" in card["preview"]
    )


def test_a_co_editor_revises_in_place_and_the_owner_stays(tmp_path: Path) -> None:
    chat = studio(tmp_path)
    install_fixture(
        chat,
        fixture_workflow(
            tmp_path, owner=("user", "colleague"), visibility="team", contributors=(ACTOR,)
        ),
    )
    revised = call(chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"})
    assert revised.data["workflow"] == "engineering/fixture-weekly-report@1.0.1"
    assert revised.data["forked"] is False
    item = chat.candidate(revised.data["candidate_id"], ACTOR)
    assert item.draft.metadata.owner.id == "colleague"
    assert ACTOR in item.draft.metadata.contributors


# -- the read-only view of a shipped capability's source ----------------------------


@pytest.fixture
def package_tree(tmp_path: Path) -> Path:
    root = tmp_path / "capabilities"
    package = root / "fixture_report"
    (package / "__pycache__").mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "runtime.py").write_text("ROOT = 1\n", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "rules.py").write_text(
        'def issue_key(row):\n    return row.get("gtm") or "NO-KEY"\napi_key = "abc123"\n',
        encoding="utf-8",
    )
    (package / "manifest.json").write_text("{}", encoding="utf-8")
    (package / "notes.txt").write_text("private notes", encoding="utf-8")
    (package / "__pycache__" / "rules.cpython-312.pyc").write_bytes(b"\0")
    (tmp_path / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")
    return root


def test_capability_source_lists_and_reads_allowed_files(package_tree: Path) -> None:
    listed: Any = capability_source("fixture_report", None, 0, (), root=package_tree)
    assert listed["ok"] is True and listed["read_only"] is True
    files = [entry["file"] for entry in listed["files"]]
    assert files == ["__init__.py", "manifest.json", "rules.py"]
    assert "revise the Workflow" in str(listed["how_to_change"])
    read = capability_source("fixture_report", "rules.py", 0, (), root=package_tree)
    assert read["ok"] is True and "NO-KEY" in str(read["source"])
    assert "abc123" not in str(read["source"])  # looks like a credential: masked
    sliced = capability_source("fixture_report", "rules.py", 0, (), root=package_tree, limit=10)
    assert sliced["truncated"] is True and sliced["next_offset"] == 10


@pytest.mark.parametrize(
    "file",
    [
        "../runtime.py",
        "..\\runtime.py",
        "../../secret.py",
        "notes.txt",
        "__pycache__/rules.cpython-312.pyc",
        "C:/Windows/win.ini",
        "/etc/passwd",
        "sub/../rules.py",
        "missing.py",
    ],
)
def test_capability_source_refuses_traversal_and_other_files(package_tree: Path, file: str) -> None:
    refused = capability_source("fixture_report", file, 0, (), root=package_tree)
    assert refused["ok"] is False and refused["code"] == "capability_file_refused"
    assert "source" not in refused


def test_capability_source_refuses_what_is_not_a_capability_package(package_tree: Path) -> None:
    for reference in ("runtime", "..", "fixture_report/..", "nope"):
        refused = capability_source(reference, None, 0, (), root=package_tree)
        assert refused["ok"] is False and refused["code"] == "capability_package_unknown"


def test_the_shipped_package_is_found_by_name_or_by_an_installed_capability(
    tmp_path: Path,
) -> None:
    from capabilities.ncc_plan.manifest import plan_workflow

    assert package_of("ncc_plan", ()) == "ncc_plan"
    assert package_of("capabilities.ncc_plan", ()) == "ncc_plan"
    handlers = (("engineering/ncc-plan@1.0.0", "ncc.plan", plan_workflow),)
    assert package_of("engineering/ncc-plan@1.0.0", handlers) == "ncc_plan"
    assert package_of("files", ()) is None  # a module, not a capability package
    chat = studio(tmp_path)
    listed = call(chat, "authoring__show_capability_source", {"capability": "ncc_plan"})
    assert listed.status == "succeeded"
    assert "manifest.py" in [entry["file"] for entry in listed.data["files"]]
    read = call(
        chat,
        "authoring__show_capability_source",
        {"capability": "ncc_plan", "file": "manifest.py"},
    )
    assert "def plan_workflow" in read.data["source"]
    refused = call(
        chat,
        "authoring__show_capability_source",
        {"capability": "ncc_plan", "file": "../runtime.py"},
    )
    assert refused.status == "failed" and refused.failure.code == "capability_file_refused"


def test_direct_model_install_creates_new_version_and_preserves_original_bytes(
    tmp_path: Path,
) -> None:
    chat = studio(tmp_path)
    names = {tool.tool.name for tool in chat.tools()}
    assert {
        "authoring__get_workflow",
        "authoring__revise_workflow",
        "authoring__show_capability_source",
    } <= names
    get = next(t for t in chat.tools() if t.tool.name == "authoring__get_workflow")
    assert "installed" in get.tool.description and "Marketplace" in get.tool.description
    path = install_fixture(chat, fixture_workflow(tmp_path))
    before = path.read_bytes()
    candidate_id = call(
        chat, "authoring__revise_workflow", {"workflow": "fixture-weekly-report"}
    ).data["candidate_id"]
    call(
        chat,
        "authoring__draft_workflow",
        {
            "title": "x",
            "workflow": edited_workflow(chat, candidate_id, EDITED),
            "candidate_id": candidate_id,
        },
    )
    asked = call(chat, "authoring__install_workflow", {"candidate_id": candidate_id})
    assert asked.status == "succeeded"
    assert len(list(chat.workflows_dir.glob("*.json"))) == 2
    assert chat.approvals("owner") == []
    assert path.read_bytes() == before


# -- external agents (authoring MCP) --------------------------------------------------


def test_an_external_agent_reads_and_revises_only_what_was_drafted_here(tmp_path: Path) -> None:
    chat = studio(tmp_path)
    install_fixture(chat, fixture_workflow(tmp_path))
    install_fixture(
        chat,
        fixture_workflow(
            tmp_path,
            name="bundled-report",
            owner=("team", "engineering"),
            visibility="organization",
            refs=(),
        ),
    )
    agent = ExternalAuthoring(chat, ACTOR, "claude-code")
    shown: Any = dispatch(
        agent, "aep_show_installed_workflow", {"workflow": "fixture-weekly-report"}
    )
    assert shown["ok"] is True
    assert shown["steps"][0]["inputs"]["request"]["value"]["script"] == SCRIPT
    withheld = dispatch(agent, "aep_show_installed_workflow", {"workflow": "bundled-report"})
    assert withheld == {
        "ok": False,
        "code": "workflow_withheld",
        "next": withheld["next"],
    } and "Revise in chat" in str(withheld["next"])
    assert dispatch(agent, "aep_revise_workflow", {"workflow": "bundled-report"})["ok"] is False
    revised = dispatch(agent, "aep_revise_workflow", {"workflow": "fixture-weekly-report"})
    assert revised["ok"] is True
    assert revised["workflow"] == "engineering/fixture-weekly-report@1.0.1"
