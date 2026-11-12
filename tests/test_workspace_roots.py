"""Task folders must lie under the coding roots, and the Agent is told so
(owner 2026-10-08: a drafted Workflow fixed a folder outside the roots and
failed only at its approved run with coding_workspace_not_allowed)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import JsonValue

from capabilities.coding_change.workspaces import containing_root, workspace_note
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext
from host_runtime.chat_authoring import ChatAuthoring
from workflow.dispatch import BridgeExecutor


class Anything(Contract):
    request: dict[str, JsonValue] | None = None
    arguments: dict[str, JsonValue] | None = None
    workspace: str | None = None
    actions: list[JsonValue] | None = None
    values: dict[str, JsonValue] | None = None


class Done(Contract):
    ok: bool = True


async def handler(context: RequestContext, inputs: Contract) -> Contract:
    return Done()


def spec(namespace: str, name: str) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {"namespace": namespace, "name": name, "version": "1.0.0"},
            "name": f"{namespace}.{name}".replace("-", "_"),
            "description": name,
            "input_contract": f"{namespace}.{name}.in.v1",
            "output_contract": f"{namespace}.{name}.out.v1",
            "side_effect": "execute",
            "policy": {
                "risk": "low",
                "required_permissions": [f"{namespace}.{name}"],
                "policy_refs": ["p"],
                "approval_required": True,
            },
        }
    )


def studio(tmp_path: Path, roots: tuple[str, ...]) -> ChatAuthoring:
    installed = InstalledCapabilities()
    for namespace, name in (("coding", "run-python"), ("browser", "operate")):
        installed.register(
            spec(namespace, name),
            handler,
            Anything,
            Done,
            ExecutionDependencies(central_required=False),
        )
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    return ChatAuthoring(
        tmp_path / "chat",
        bridge=lambda: bridge,
        namespace="engineering",
        workflows_dir=tmp_path / "workflows",
        grants_file=tmp_path / "grants.json",
        coding_workspace_roots=roots,
    )


def stock(workspace: str, browser_workspace: str | None = None) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    if browser_workspace is not None:
        steps.append(
            {
                "capability": "browser/operate@1.0.0",
                "inputs": {
                    "actions": {"source": "fixed", "value": []},
                    "workspace": {"source": "fixed", "value": browser_workspace},
                },
            }
        )
    steps.append(
        {
            "capability": "coding/run-python@1.0.0",
            "inputs": {
                "request": {
                    "source": "fixed",
                    "value": {"workspace": workspace, "script": "print(1)"},
                },
                "arguments": {"source": "run", "path": []},
            },
        }
    )
    return {
        "name": "stock-last-price",
        "description": "Stock price.",
        "parameters": [],
        "steps": steps,
    }


def test_absolute_workspace_outside_legacy_roots_is_prepared(
    tmp_path: Path,
) -> None:
    root = tmp_path / "aep-workflows"
    root.mkdir()
    chat = studio(tmp_path, (str(root),))
    outside = tmp_path / "stock-workflow"
    item, problems = chat.draft("owner", None, "Stock", stock(str(outside)))
    assert item is not None and problems == []
    assert (outside / "input").is_dir() and (outside / "output").is_dir()


def test_a_new_folder_under_a_root_is_created_with_input_and_output(tmp_path: Path) -> None:
    root = tmp_path / "aep-workflows"
    root.mkdir()
    chat = studio(tmp_path, (str(root),))
    task = root / "stock-price"
    item, problems = chat.draft("owner", None, "Stock", stock(str(task), str(task)))
    assert problems == [] and item is not None
    assert (task / "input").is_dir() and (task / "output").is_dir()


def test_browser_workspace_outside_legacy_roots_is_prepared(tmp_path: Path) -> None:
    root = tmp_path / "aep-workflows"
    (root / "ok").mkdir(parents=True)
    chat = studio(tmp_path, (str(root),))
    _, problems = chat.draft(
        "owner", None, "Stock", stock(str(root / "ok"), str(tmp_path / "elsewhere"))
    )
    assert problems == []
    assert (tmp_path / "elsewhere" / "output").is_dir()


def test_legacy_roots_are_suggestions_without_denying_other_absolute_paths(tmp_path: Path) -> None:
    root = str(tmp_path / "aep-workflows")
    chat = studio(tmp_path, (root, str(tmp_path / "lab")))
    (draft,) = [t for t in chat.tools() if t.tool.name == "authoring__draft_workflow"]
    assert (
        root in draft.tool.description
        and "Any absolute IT-accessible path is valid" in draft.tool.description
    )
    bare = studio(tmp_path, ())
    (plain,) = [t for t in bare.tools() if t.tool.name == "authoring__draft_workflow"]
    assert "roots" not in plain.tool.description
    assert workspace_note(()) == ""


def test_containment_matches_the_handlers_rule(tmp_path: Path) -> None:
    root = tmp_path / "r"
    assert containing_root(str(root), [str(root)]) == root.resolve()
    assert containing_root(str(root / "a" / ".." / "b"), [str(root)]) == (root / "b").resolve()
    assert containing_root(str(root / ".." / "x"), [str(root)]) is None
    assert containing_root("relative/path", [str(root)]) is None
